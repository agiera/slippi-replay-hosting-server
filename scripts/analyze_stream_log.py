#!/usr/bin/env python3
"""Reconstruct live-stream session timelines from `docker compose logs` output.

The backend prints two families of log lines:
  * pyftpdlib lines, e.g. "[I 2026-09-22 21:07:55] ... FTP session opened",
    which carry a real wall-clock timestamp.
  * our own "[FTP][TRACE]"/"[FTP][EVENT]"/"[FTP][ERROR]" lines, which carry NO
    timestamp but usually embed one in a field (upload_started_at=,
    captured_upload_started_at=) or can be approximated from elapsed_s=
    relative to the nearest preceding Bound STOR for the same source.

Capture logs with `docker compose logs -t backend > backend.log` and every line
(uvicorn access logs, tracebacks, [FTP] prints) gets a precise timestamp that
this script prefers over the heuristics above.

This script builds a best-effort per-source timeline of game uploads
(login -> started -> [completed|failed] -> disconnect), then:
  * reports how many sources had a game "open" (started but not yet
    completed/failed) at every state change, flagging peaks of concurrency,
  * reports every footer/parse failure with byte count + transfer time,
  * reports every Python traceback / 5xx response found in the log,
  * reports SSE (`/stream/events`) connect churn, which is the best log-only
    proxy for "the live rows briefly disappeared in the browser" (that page
    only repopulates when it receives a fresh SSE snapshot/status frame).

Usage:
    python3 scripts/analyze_stream_log.py backend.log
    python3 scripts/analyze_stream_log.py backend.log --date 2026-09-22
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

PYFTP_TS_RE = re.compile(r"^\[I (?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\] (?P<rest>.*)$")
# `docker compose logs -t` prefix, e.g. "2026-09-22T21:07:55.123456789Z "
DOCKER_TS_RE = re.compile(r"^(?P<ts>\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z) (?P<rest>.*)$")
# Our own `logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")`,
# which since the 2026-09-26 logging migration covers EVERY line (including
# pyftpdlib's own connect/login/STOR/close messages) - the preferred anchor.
APP_LOG_TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+)\s+\S+\s+[\w.]+: (?P<rest>.*)$"
)

LOGIN_RE = re.compile(
    r"\[FTP\]\[TRACE\] Login source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)'"
)
BOUND_STOR_RE = re.compile(
    r"\[FTP\]\[TRACE\] Bound STOR source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)' "
    r"file_key='(?P<file>[^']*)' stream_game_id='(?P<game>[^']*)' upload_started_at='(?P<ts>[^']*)'"
)
FINALIZING_RE = re.compile(
    r"\[FTP\]\[TRACE\] Finalizing file='(?P<file>[^']*)' source='(?P<source>[^']*)' "
    r"upload_session_id='(?P<sid>[^']*)'.*captured_upload_started_at='(?P<ts>[^']*)'"
)
STATUS_RE = re.compile(
    r"\[FTP\]\[EVENT\] source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)' "
    r"stream_game_id='(?P<game>[^']*)' status='(?P<status>[a-z_]*)' repository='[^']*' "
    r"filename='(?P<file>[^']*)'"
)
RECEIVED_RE = re.compile(
    r"\[FTP\]\[UPLOAD\] Received replay '(?P<file>[^']*)' source='(?P<source>[^']*)' "
    r"upload_session_id='(?P<sid>[^']*)' bytes=(?P<bytes>\d+) transfer_s=(?P<transfer_s>[\d.]+)"
)
FAILURE_REASON_RE = re.compile(r"\[FTP\] Failed to finalize uploaded file '(?P<file>[^']*)': (?P<reason>.*)$")
TRUNCATED_WARN_RE = re.compile(r"\[FTP\]\[WARN\] Truncated stream '(?P<file>[^']*)'")
DISCONNECT_RE = re.compile(
    r"\[FTP\]\[TRACE\] Disconnect source='(?P<source>[^']*)' upload_session_id='(?P<sid>[^']*)' "
    r"transfer_attempted=(?P<attempted>\w+)"
)
SSE_OPEN_RE = re.compile(r'"GET /api/v1/replays/stream/events HTTP/1\.1" 200')
STATUS_POLL_RE = re.compile(r'"GET /api/v1/replays/stream/status HTTP/1\.1" (?P<code>\d+)')
HTTP_5XX_RE = re.compile(r'"(?:GET|POST|PUT|DELETE) [^"]*" (?P<code>5\d\d)')


@dataclass
class Session:
    source: str
    sid: str
    file: str | None = None
    game: str | None = None
    started_ts: datetime | None = None
    finalized_ts: datetime | None = None
    outcome: str | None = None  # completed / failed / open-at-eof
    bytes: int | None = None
    transfer_s: float | None = None
    reason: str | None = None
    disconnected: bool = False


def parse_ts(text: str) -> datetime | None:
    text = text.strip()
    m = DOCKER_TS_RE.match(text + " ")
    if m:
        iso = m.group("ts")
        # Python's fromisoformat only accepts up to 6 fractional digits.
        iso = re.sub(r"\.(\d{6})\d+Z$", r".\1Z", iso).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(iso)
        except ValueError:
            return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
        try:
            ts = datetime.strptime(text, fmt)
        except ValueError:
            continue
        # pyftpdlib timestamps have no tz suffix; the container clock is UTC, same
        # as the tz-aware upload_started_at/captured_upload_started_at fields.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    return None


def load_lines(path: str) -> list[str]:
    with open(path, errors="replace") as f:
        return f.readlines()


def strip_prefix(line: str) -> str:
    # docker-compose logs prefix every line with "<service>-<n>  | "
    idx = line.find("| ")
    return line[idx + 2 :].rstrip("\n") if idx != -1 else line.rstrip("\n")


def build_timeline(lines: list[str]) -> tuple[list[Session], list[dict], list[dict]]:
    sessions: dict[str, Session] = {}
    order: list[str] = []
    anomalies: list[dict] = []
    sse_opens: list[dict] = []  # {lineno, ts}
    last_anchor_ts: datetime | None = None

    for lineno, raw in enumerate(lines, start=1):
        content = strip_prefix(raw)

        m = DOCKER_TS_RE.match(content)
        if m:
            ts = parse_ts(m.group("ts"))
            if ts:
                last_anchor_ts = ts
            content = m.group("rest")

        m = APP_LOG_TS_RE.match(content)
        if m:
            ts = parse_ts(m.group("ts"))
            if ts:
                last_anchor_ts = ts
            content = m.group("rest")

        m = PYFTP_TS_RE.match(content)
        if m:
            ts = parse_ts(m.group("ts"))
            if ts:
                last_anchor_ts = ts
            content = m.group("rest")

        m = LOGIN_RE.search(content)
        if m:
            sid = m.group("sid")
            sessions.setdefault(sid, Session(source=m.group("source"), sid=sid))
            if sid not in order:
                order.append(sid)
            continue

        m = BOUND_STOR_RE.search(content)
        if m:
            sid = m.group("sid")
            sess = sessions.setdefault(sid, Session(source=m.group("source"), sid=sid))
            if sid not in order:
                order.append(sid)
            sess.file = m.group("file")
            sess.game = m.group("game")
            sess.started_ts = parse_ts(m.group("ts")) or sess.started_ts
            continue

        m = FINALIZING_RE.search(content)
        if m:
            sid = m.group("sid")
            sess = sessions.setdefault(sid, Session(source=m.group("source"), sid=sid))
            sess.finalized_ts = parse_ts(m.group("ts")) or sess.started_ts
            continue

        m = RECEIVED_RE.search(content)
        if m:
            sid = m.group("sid")
            sess = sessions.setdefault(sid, Session(source=m.group("source"), sid=sid))
            if sid not in order:
                order.append(sid)
            sess.bytes = int(m.group("bytes"))
            sess.transfer_s = float(m.group("transfer_s"))
            # Backfill a start time for sessions whose "started" status event
            # fell outside the analyzed window (or was logged below INFO level).
            if sess.started_ts is None and last_anchor_ts is not None:
                sess.started_ts = last_anchor_ts - timedelta(seconds=sess.transfer_s)
            continue

        m = STATUS_RE.search(content)
        if m:
            sid = m.group("sid")
            sess = sessions.setdefault(sid, Session(source=m.group("source"), sid=sid))
            if sid not in order:
                order.append(sid)
            status = m.group("status")
            if status == "started":
                # TRACE-level Bound STOR (which carries an embedded upload_started_at)
                # is suppressed at the prod default LOG_LEVEL=INFO; this status event
                # is the earliest INFO-level signal, so use the line's own timestamp.
                sess.file = sess.file or m.group("file")
                sess.game = sess.game or m.group("game")
                sess.started_ts = sess.started_ts or last_anchor_ts
            if status in ("completed", "failed"):
                sess.outcome = status
            continue

        m = FAILURE_REASON_RE.search(content)
        if m:
            # attach to most recently finalized session with this filename
            for sid in reversed(order):
                sess = sessions.get(sid)
                if sess and sess.file == m.group("file") and sess.reason is None:
                    sess.reason = m.group("reason")
                    break
            continue

        m = TRUNCATED_WARN_RE.search(content)
        if m:
            for sid in reversed(order):
                sess = sessions.get(sid)
                if sess and sess.file == m.group("file") and sess.reason is None:
                    sess.reason = "truncated stream (quarantined)"
                    break
            continue

        m = DISCONNECT_RE.search(content)
        if m:
            sid = m.group("sid")
            sess = sessions.get(sid)
            if sess:
                sess.disconnected = True
            continue

        if SSE_OPEN_RE.search(content):
            sse_opens.append({"lineno": lineno, "ts": last_anchor_ts})
            continue

        if "Traceback (most recent call last):" in content or HTTP_5XX_RE.search(content):
            anomalies.append({"lineno": lineno, "ts": last_anchor_ts, "line": content.strip()})
            continue

    return [sessions[sid] for sid in order], anomalies, sse_opens


def summarize(sessions: list[Session], anomalies: list[dict], sse_opens: list[int], date_filter: str | None):
    def in_scope(sess: Session) -> bool:
        if date_filter is None:
            return True
        ts = sess.started_ts or sess.finalized_ts
        return bool(ts and ts.strftime("%Y-%m-%d") == date_filter)

    scoped = [s for s in sessions if in_scope(s)]
    print(f"== Sessions in scope: {len(scoped)} ==")

    completed = [s for s in scoped if s.outcome == "completed"]
    failed = [s for s in scoped if s.outcome == "failed"]
    open_at_eof = [s for s in scoped if s.outcome is None]

    print(f"completed={len(completed)} failed={len(failed)} still-open-at-log-end={len(open_at_eof)}")

    if failed:
        print("\n-- Failed uploads --")
        for s in failed:
            print(
                f"  {s.started_ts} source={s.source} file={s.file} bytes={s.bytes} "
                f"transfer_s={s.transfer_s} reason={s.reason!r}"
            )

    # Concurrency: build start/end intervals and sweep. `finalized_ts` is NOT a
    # real end time (the Finalizing trace line just echoes the original
    # upload_started_at back); the true transfer end is started_ts + transfer_s.
    events: list[tuple[datetime, int, str]] = []
    for s in scoped:
        if s.started_ts is None:
            continue
        if s.transfer_s is not None:
            end = s.started_ts + timedelta(seconds=s.transfer_s)
        else:
            end = s.finalized_ts or s.started_ts
        events.append((s.started_ts, 1, s.source))
        events.append((end, -1, s.source))
    events.sort(key=lambda e: (e[0], -e[1]))

    concurrency = 0
    peak = 0
    peak_ts = None
    active: set[str] = set()
    peak_sources: set[str] = set()
    for ts, delta, source in events:
        if delta == 1:
            active.add(source)
        else:
            active.discard(source)
        concurrency = len(active)
        if concurrency > peak:
            peak = concurrency
            peak_ts = ts
            peak_sources = set(active)

    print(f"\n-- Peak concurrent live games: {peak} at {peak_ts} sources={sorted(peak_sources)} --")

    def concurrency_at(ts: datetime | None) -> int:
        if ts is None:
            return -1
        count = 0
        for ev_ts, delta, _source in events:
            if ev_ts > ts:
                break
            count += delta
        return count

    # SSE connect churn: repeated opens close together (by line distance) suggest
    # the browser's EventSource kept reconnecting instead of holding one stream
    # (e.g. it timed out waiting for the first snapshot byte and retried).
    scoped_sse = [
        e for e in sse_opens if date_filter is None or (e["ts"] and e["ts"].strftime("%Y-%m-%d") == date_filter)
    ]
    print(f"\n-- SSE '/stream/events' connections opened: {len(scoped_sse)} --")
    churn_events = []
    for i in range(1, len(scoped_sse)):
        if scoped_sse[i]["lineno"] - scoped_sse[i - 1]["lineno"] < 5:
            churn_events.append(scoped_sse[i])
    if churn_events:
        print(f"  {len(churn_events)} reconnects happened within 5 log lines of the previous one (possible churn)")
        print("  churn timestamps with concurrent-live-game count at that moment:")
        seen_ts = set()
        for e in churn_events:
            key = e["ts"]
            if key in seen_ts:
                continue
            seen_ts.add(key)
            print(f"    line {e['lineno']} ts~={e['ts']} concurrency~={concurrency_at(e['ts'])}")

    if anomalies:
        print(f"\n-- Anomalies (tracebacks / 5xx): {len(anomalies)} --")
        for a in anomalies[:40]:
            print(f"  line {a['lineno']} near_ts={a['ts']}: {a['line'][:160]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile")
    parser.add_argument("--date", help="Restrict to YYYY-MM-DD (matches session start time)")
    args = parser.parse_args()

    lines = load_lines(args.logfile)
    sessions, anomalies, sse_opens = build_timeline(lines)
    summarize(sessions, anomalies, sse_opens, args.date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
