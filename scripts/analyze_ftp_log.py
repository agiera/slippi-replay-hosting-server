#!/usr/bin/env python3
"""Analyze backend.log (docker compose logs for the `backend` service) for FTP
live-upload health: finalize failures, how long each source's live preview
takes to populate after reconnecting, and how many sources were simultaneously
"connected but blank" (preview not yet resolved) -- the state that makes
`isLiveSourceVisible` on the frontend hide a row.

Log lines carry no wall-clock timestamp except the occasional pyftpdlib
`[I yyyy-mm-dd hh:mm:ss]` line (session open/login/STOR-complete/close), so
this script mixes those anchors with line order (log lines are printed in the
order events happen) to reconstruct approximate timelines. Treat "concurrent
blank" timing as an estimate, not an exact wall-clock reconstruction.

Usage:
    python3 scripts/analyze_ftp_log.py [LOG_PATH] [--date YYYY-MM-DD] [--json]
    python3 scripts/analyze_ftp_log.py backend.log --min-concurrent-blank 2
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

TS_RE = re.compile(r"\[I (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]")
LOGIN_RE = re.compile(
    r"\[FTP\]\[TRACE\] Login source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)'"
)
BOUND_STOR_RE = re.compile(
    r"\[FTP\]\[TRACE\] Bound STOR source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)' "
    r"file_key='(?P<file>[^']*)'"
)
RESOLVED_RE = re.compile(
    r"\[FTP\]\[TRACE\] Live partial parse resolved source='(?P<source>[^']*)' file='(?P<file>[^']*)' "
    r"attempts=(?P<attempts>\d+) bytes=(?P<bytes>\d+) stage=(?P<stage>\S+) players=(?P<players>\d+) "
    r"elapsed_s=(?P<elapsed>[\d.]+)"
)
PENDING_RE = re.compile(r"\[FTP\]\[TRACE\] Live partial parse (pending|waiting for bytes|stopped before first attempt) source='(?P<source>[^']*)'")
RECEIVED_RE = re.compile(
    r"\[FTP\]\[UPLOAD\] Received replay '(?P<file>[^']*)' source='(?P<source>[^']*)' "
    r"upload_session_id='(?P<sid>[^']*)' bytes=(?P<bytes>\d+) transfer_s=(?P<ts>[\d.]+)"
)
FINALIZE_FAIL_RE = re.compile(r"\[FTP\] Failed to finalize uploaded file '(?P<file>[^']*)': (?P<reason>.*)$")
TRUNCATED_RE = re.compile(
    r"\[FTP\]\[WARN\] Truncated stream '(?P<file>[^']*)'.*bytes=(?P<bytes>\d+) saved_to='(?P<saved_to>[^']*)': (?P<reason>.*)$"
)
INGEST_FAIL_RE = re.compile(r"\[FTP\] Failed to ingest uploaded file '(?P<path>[^']*)': (?P<reason>.*)$")
DISCONNECT_RE = re.compile(r"\[FTP\]\[TRACE\] Disconnect source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)'")
ERROR_RE = re.compile(r"\[FTP\]\[ERROR\] (?P<msg>.*)$")


@dataclass
class Session:
    source: str
    upload_session_id: str
    login_line: int
    last_ts: str | None = None
    stor_file: str | None = None
    resolved_elapsed_s: float | None = None
    resolved_attempts: int | None = None
    pending_hits: int = 0
    bytes_received: int | None = None
    transfer_s: float | None = None
    outcome: str | None = None  # completed / failed / disconnected-unresolved
    failure_reason: str | None = None
    disconnect_line: int | None = None

    def blank_window(self) -> float | None:
        """Approx seconds the source sat connected with an empty live preview."""
        return self.resolved_elapsed_s


def parse_log(path: Path, date_filter: str | None):
    sessions: dict[str, Session] = {}
    order: list[str] = []
    last_ts = None
    errors: list[tuple[int, str]] = []

    with path.open(errors="replace") as f:
        for lineno, line in enumerate(f, start=1):
            m = TS_RE.search(line)
            if m:
                last_ts = m.group(1)

            m = LOGIN_RE.search(line)
            if m:
                sid = m.group("sid")
                if date_filter and last_ts and not last_ts.startswith(date_filter):
                    continue
                sessions[sid] = Session(source=m.group("source"), upload_session_id=sid, login_line=lineno, last_ts=last_ts)
                order.append(sid)
                continue

            m = BOUND_STOR_RE.search(line)
            if m:
                sid = m.group("sid")
                sess = sessions.get(sid)
                if sess:
                    sess.stor_file = m.group("file")
                continue

            m = RESOLVED_RE.search(line)
            if m:
                source = m.group("source")
                # attribute to the most recently opened, still-unresolved session for this source
                for sid in reversed(order):
                    sess = sessions.get(sid)
                    if sess and sess.source == source and sess.resolved_elapsed_s is None:
                        sess.resolved_elapsed_s = float(m.group("elapsed"))
                        sess.resolved_attempts = int(m.group("attempts"))
                        break
                continue

            m = PENDING_RE.search(line)
            if m:
                source = m.group("source")
                for sid in reversed(order):
                    sess = sessions.get(sid)
                    if sess and sess.source == source and sess.resolved_elapsed_s is None:
                        sess.pending_hits += 1
                        break
                continue

            m = RECEIVED_RE.search(line)
            if m:
                sid = m.group("sid")
                sess = sessions.get(sid)
                if sess:
                    sess.bytes_received = int(m.group("bytes"))
                    sess.transfer_s = float(m.group("ts"))
                continue

            m = FINALIZE_FAIL_RE.search(line)
            if m:
                # Attach to the most recent session with this stor_file that has no outcome yet.
                file = m.group("file")
                for sid in reversed(order):
                    sess = sessions.get(sid)
                    if sess and sess.stor_file == file and sess.outcome is None:
                        sess.outcome = "failed"
                        sess.failure_reason = m.group("reason")
                        break
                continue

            m = TRUNCATED_RE.search(line)
            if m:
                file = m.group("file")
                for sid in reversed(order):
                    sess = sessions.get(sid)
                    if sess and sess.stor_file == file and sess.outcome is None:
                        sess.outcome = "failed"
                        sess.failure_reason = f"{m.group('reason')} (quarantined at {m.group('saved_to')})"
                        break
                continue

            m = INGEST_FAIL_RE.search(line)
            if m:
                errors.append((lineno, f"ingest failure: {m.group('reason')}"))
                continue

            m = ERROR_RE.search(line)
            if m and "Live partial parse failed" not in line:
                errors.append((lineno, m.group("msg")))
                continue

            m = DISCONNECT_RE.search(line)
            if m:
                sid = m.group("sid")
                sess = sessions.get(sid)
                if sess:
                    sess.disconnect_line = lineno
                    if sess.outcome is None:
                        sess.outcome = "completed" if sess.bytes_received is not None else "disconnected-unresolved"
                continue

    return sessions, order, errors


def summarize(sessions: dict[str, Session], order: list[str]) -> dict:
    by_date_outcome = defaultdict(lambda: defaultdict(int))
    failures = []
    unresolved_previews = []
    elapsed_values = []

    for sid in order:
        s = sessions[sid]
        date = (s.last_ts or "unknown")[:10]
        by_date_outcome[date][s.outcome or "in-progress"] += 1
        if s.outcome == "failed":
            failures.append(s)
        if s.resolved_elapsed_s is not None:
            elapsed_values.append(s.resolved_elapsed_s)
        elif s.stor_file is not None:
            unresolved_previews.append(s)

    return {
        "by_date_outcome": {d: dict(v) for d, v in by_date_outcome.items()},
        "failures": failures,
        "unresolved_previews": unresolved_previews,
        "elapsed_values": elapsed_values,
    }


def find_concurrent_blank_windows(sessions: dict[str, Session], order: list[str], min_concurrent: int):
    """Approximate, using login order, how many sources were simultaneously
    connected with an unresolved (blank) live preview. A session counts as
    "blank" from its login line until its resolved-preview line (or its
    disconnect line, if the preview never resolved).
    """
    events = []  # (lineno, +1/-1, source)
    for sid in order:
        s = sessions[sid]
        end_line = s.disconnect_line or (s.login_line + 1)
        if s.resolved_elapsed_s is not None:
            # We don't know the exact line the resolved event happened on; use
            # disconnect_line as a safe upper bound if available, else login+1.
            end_line = min(end_line, s.disconnect_line or end_line)
        events.append((s.login_line, 1, s.source))
        events.append((end_line, -1, s.source))

    events.sort(key=lambda e: (e[0], -e[1]))
    active = set()
    peak = 0
    peak_at = None
    peak_sources = []
    for lineno, delta, source in events:
        if delta == 1:
            active.add(source)
        else:
            active.discard(source)
        if len(active) > peak:
            peak = len(active)
            peak_at = lineno
            peak_sources = sorted(active)

    windows = []
    if peak >= min_concurrent:
        windows.append({"line": peak_at, "concurrent_sources": peak_sources, "count": peak})
    return peak, windows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("log_path", nargs="?", default="backend.log", type=Path)
    parser.add_argument("--date", help="Only consider sessions logged on this date (YYYY-MM-DD).")
    parser.add_argument("--min-concurrent-blank", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.log_path.exists():
        print(f"Log file not found: {args.log_path}", file=sys.stderr)
        return 1

    sessions, order, errors = parse_log(args.log_path, args.date)
    summary = summarize(sessions, order)
    peak_concurrent, blank_windows = find_concurrent_blank_windows(sessions, order, args.min_concurrent_blank)

    if args.json:
        out = {
            "by_date_outcome": summary["by_date_outcome"],
            "failure_count": len(summary["failures"]),
            "failures": [
                {
                    "source": f.source,
                    "file": f.stor_file,
                    "bytes": f.bytes_received,
                    "transfer_s": f.transfer_s,
                    "reason": f.failure_reason,
                }
                for f in summary["failures"]
            ],
            "unresolved_preview_count": len(summary["unresolved_previews"]),
            "unresolved_previews": [
                {"source": u.source, "file": u.stor_file, "login_line": u.login_line}
                for u in summary["unresolved_previews"]
            ],
            "preview_resolve_elapsed_s": summary["elapsed_values"],
            "peak_concurrent_blank_sources": peak_concurrent,
            "blank_windows": blank_windows,
            "other_errors": errors,
        }
        print(json.dumps(out, indent=2))
        return 0

    print(f"Sessions parsed: {len(order)}")
    print("\nOutcome counts by date:")
    for date, counts in sorted(summary["by_date_outcome"].items()):
        print(f"  {date}: {counts}")

    print(f"\nFinalize failures: {len(summary['failures'])}")
    for f in summary["failures"]:
        print(f"  source={f.source} file={f.stor_file} bytes={f.bytes_received} transfer_s={f.transfer_s} reason={f.failure_reason}")

    values = summary["elapsed_values"]
    if values:
        print(f"\nLive-preview resolve latency (s): n={len(values)} min={min(values):.2f} "
              f"max={max(values):.2f} avg={sum(values)/len(values):.2f}")
        slow = [v for v in values if v > 3]
        print(f"  sessions taking >3s to resolve: {len(slow)}")

    print(f"\nSessions whose live preview never resolved before disconnect/finalize: {len(summary['unresolved_previews'])}")
    for u in summary["unresolved_previews"][:20]:
        print(f"  source={u.source} file={u.stor_file} login_line={u.login_line}")

    print(f"\nPeak simultaneous 'connected but blank preview' sources (line-order estimate): {peak_concurrent}")
    for w in blank_windows:
        print(f"  near log line {w['line']}: sources={w['concurrent_sources']}")

    if errors:
        print(f"\nOther FTP errors/ingest failures: {len(errors)}")
        for lineno, msg in errors[:20]:
            print(f"  line {lineno}: {msg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
