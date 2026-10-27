#!/usr/bin/env python3
"""Analyze replay FTP TCP headers with tshark (Wireshark CLI required).

Usage:
    python3 scripts/analyze_pcap.py wii-ftp.pcap --log backend.log
    python3 scripts/analyze_pcap.py wii-ftp.pcap --log backend.log --json

Capture on the FTP receiver's tailscale0 interface. A 128-byte snap length
usually preserves TCP headers, but may truncate FTP commands. Burst rates are
observed goodput, not link capacity. Retransmission flags are Wireshark's
heuristics; duplicate capture observations can also repeat sequence bytes.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


FLAGS = (
    "retransmission", "fast_retransmission", "spurious_retransmission",
    "out_of_order", "lost_segment", "zero_window", "window_full", "duplicate_ack",
)
FIELDS = (
    "frame.time_epoch", "frame.len", "frame.cap_len", "tcp.stream", "ip.src", "ip.dst",
    "tcp.srcport", "tcp.dstport", "tcp.len", "tcp.seq_raw", "tcp.ack_raw",
    "tcp.flags.syn", "tcp.flags.fin", "tcp.flags.reset", "tcp.window_size",
    "tcp.analysis.ack_rtt", "tcp.analysis.bytes_in_flight",
) + tuple(f"tcp.analysis.{flag}" for flag in FLAGS)
COMMAND_FIELDS = (
    "frame.time_epoch", "tcp.stream", "ip.src", "ip.dst", "tcp.srcport", "tcp.dstport",
    "ftp.request.command", "ftp.request.arg", "ftp.response.arg",
)


def flag_set(value):
    return str(value).lower() in {"1", "true"}


def distribution(values):
    ordered = sorted(values)
    if not ordered:
        return {"count": 0, "median": None, "p95": None, "max": None}
    return {
        "count": len(ordered), "median": ordered[(len(ordered) - 1) // 2],
        "p95": ordered[int((len(ordered) - 1) * 0.95)], "max": ordered[-1],
    }


def add_range(ranges, start, end):
    overlap = sum(max(0, min(end, right) - max(start, left)) for left, right in ranges)
    merged = []
    for left, right in sorted([*ranges, (start, end)]):
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    ranges[:] = merged
    return end - start - overlap


def tshark_rows(executable, capture, fields, display_filter, control_port):
    command = [
        executable, "-n", "-r", str(capture), "-d", f"tcp.port=={control_port},ftp",
        "-Y", display_filter, "-T", "fields", "-E", "header=y", "-E", "separator=/t",
        "-E", "occurrence=f",
    ]
    for name in fields:
        command.extend(["-e", name])
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as process:
        yield from csv.DictReader(process.stdout, delimiter="\t", quoting=csv.QUOTE_NONE)
        if process.wait():
            raise RuntimeError("tshark failed; see its diagnostic output above")


@dataclass
class Transfer:
    stream: int
    client: str
    client_port: int
    server: str
    server_port: int
    start: float
    end: float
    filename: str = ""
    source: str = "unknown"
    ranges: list = field(default_factory=list)
    bins: dict = field(default_factory=lambda: {1: Counter(), 10: Counter()})
    flags: Counter = field(default_factory=Counter)
    server_flags: Counter = field(default_factory=Counter)
    sizes: Counter = field(default_factory=Counter)
    gaps: list = field(default_factory=list)
    ack_rtts: list = field(default_factory=list)
    local_acks: list = field(default_factory=list)
    pending: list = field(default_factory=list)
    windows: list = field(default_factory=list)
    bytes: int = 0
    repeated_bytes: int = 0
    data_packets: int = 0
    retransmitted_packets: int = 0
    max_inflight: int = 0
    origin: int | None = None
    acknowledged: int = 0
    first_data: float | None = None
    last_data: float | None = None
    syn_seen: bool = False
    fin_seen: bool = False
    reset_seen: bool = False

    def consume(self, packet):
        timestamp = float(packet["frame.time_epoch"])
        self.end = max(self.end, timestamp)
        incoming = packet["ip.dst"] == self.server
        flags = {name: flag_set(packet[f"tcp.analysis.{name}"]) for name in FLAGS}
        self.flags.update(name for name, enabled in flags.items() if enabled)
        if not incoming:
            self.server_flags.update(name for name, enabled in flags.items() if enabled)
        self.syn_seen |= flag_set(packet["tcp.flags.syn"])
        self.fin_seen |= flag_set(packet["tcp.flags.fin"])
        self.reset_seen |= flag_set(packet["tcp.flags.reset"])
        if not incoming:
            window = packet["tcp.window_size"]
            if window and not flag_set(packet["tcp.flags.syn"]) and not self.reset_seen:
                self.windows.append(int(window))
            if self.origin is not None:
                acknowledged = (int(packet["tcp.ack_raw"]) - self.origin) % (1 << 32)
                if acknowledged < (1 << 31):
                    self.acknowledged = max(self.acknowledged, acknowledged)
                    waiting = []
                    for end, sent in self.pending:
                        if end <= acknowledged:
                            self.local_acks.append(max(0, timestamp - sent) * 1000)
                        else:
                            waiting.append((end, sent))
                    self.pending = waiting
            return
        if packet["tcp.analysis.ack_rtt"]:
            self.ack_rtts.append(float(packet["tcp.analysis.ack_rtt"]) * 1000)
        size = int(packet["tcp.len"])
        if not size:
            return
        sequence = int(packet["tcp.seq_raw"])
        if self.origin is None:
            self.origin = sequence
        offset = (sequence - self.origin) % (1 << 32)
        if offset >= (1 << 31):
            offset -= 1 << 32
        fresh = add_range(self.ranges, offset, offset + size)
        self.bytes += fresh
        self.repeated_bytes += size - fresh
        self.data_packets += 1
        self.retransmitted_packets += any(flags[name] for name in FLAGS[:3])
        self.sizes[size] += 1
        self.max_inflight = max(self.max_inflight, int(packet["tcp.analysis.bytes_in_flight"] or 0))
        if fresh:
            if self.last_data is not None:
                self.gaps.append(max(0, timestamp - self.last_data) * 1000)
            if self.first_data is None:
                self.first_data = timestamp
            self.last_data = timestamp
            for scale, bins in self.bins.items():
                bins[int(timestamp * scale)] += fresh
        if offset + size > self.acknowledged:
            self.pending.append((offset + size, timestamp))

    def report(self):
        duration = (self.last_data - self.first_data) if self.first_data is not None else 0
        return {
            "stream": self.stream, "source": self.source, "filename": self.filename,
            "client": f"{self.client}:{self.client_port}", "server": f"{self.server}:{self.server_port}",
            "start_utc": utc(self.start), "end_utc": utc(self.end),
            "last_unique_data_utc": utc(self.last_data) if self.last_data is not None else None,
            "trailing_no_progress_ms": max(0, self.end - self.last_data) * 1000 if self.last_data is not None else None,
            "unique_bytes": self.bytes, "repeated_sequence_bytes": self.repeated_bytes,
            "data_packets": self.data_packets, "suspected_retransmitted_packets": self.retransmitted_packets,
            "average_KiB_s": self.bytes / 1024 / duration if duration else None,
            "peak_1s_KiB_s": max(self.bins[1].values(), default=0) / 1024,
            "peak_100ms_KiB_s": max(self.bins[10].values(), default=0) / 102.4,
            "arrival_gap_ms": distribution(self.gaps),
            "receiver_cumulative_ack_delay_ms": distribution(self.local_acks),
            "server_to_peer_ack_rtt_ms": distribution(self.ack_rtts),
            "server_window_min": min(self.windows, default=None),
            "server_window_max": max(self.windows, default=None),
            "max_bytes_in_flight": self.max_inflight,
            "tcp_analysis": {name: self.flags[name] for name in FLAGS},
            "server_tcp_analysis": {name: self.server_flags[name] for name in FLAGS},
            "top_payload_sizes": self.sizes.most_common(5),
            "syn_seen": self.syn_seen, "fin_seen": self.fin_seen, "reset_seen": self.reset_seen,
        }


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat()


def log_context(path):
    sources = defaultdict(set)
    timestamps = []
    if path is None:
        return {}, None, None
    with path.open(errors="replace") as handle:
        for line in handle:
            source = re.search(r"source='([^']+)'", line)
            mac = re.search(r"Game_([0-9A-Fa-f]{12})_", line)
            if source and mac:
                sources[mac[1].upper()].add(source[1])
            time_match = re.search(r"\b(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),\d+", line)
            if time_match:
                timestamps.append(datetime.strptime(time_match[1], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp())
    return {mac: next(iter(names)) for mac, names in sources.items() if len(names) == 1}, min(timestamps, default=None), max(timestamps, default=None)


def associate_commands(transfers, commands):
    passive = {}
    for packet in commands:
        control = packet["tcp.stream"]
        response = re.search(r"\((\d+),(\d+),(\d+),(\d+),(\d+),(\d+)\)", packet["ftp.response.arg"])
        if response:
            passive[control] = (packet["ip.src"], packet["ip.dst"], int(response[5]) * 256 + int(response[6]))
        if packet["ftp.request.command"] != "STOR" or control not in passive:
            continue
        server, client, port = passive[control]
        timestamp = float(packet["frame.time_epoch"])
        candidates = [transfer for transfer in transfers.values() if
                      (transfer.server, transfer.client, transfer.server_port) == (server, client, port)
                      and abs(transfer.start - timestamp) < 5]
        if candidates:
            transfer = min(candidates, key=lambda item: abs(item.start - timestamp))
            transfer.filename = packet["ftp.request.arg"]


def analyze(capture, log=None, tshark="tshark", control_port=2121, passive_start=22100, passive_end=22199):
    transfers = {}
    first = last = None
    packet_count = truncated = 0
    port_filter = f"tcp.port in {{{control_port}, {passive_start}..{passive_end}}}"
    for packet in tshark_rows(tshark, capture, FIELDS, port_filter, control_port):
        timestamp = float(packet["frame.time_epoch"])
        first = timestamp if first is None else min(first, timestamp)
        last = timestamp if last is None else max(last, timestamp)
        packet_count += 1
        truncated += int(packet["frame.cap_len"]) < int(packet["frame.len"])
        src_port, dst_port = int(packet["tcp.srcport"]), int(packet["tcp.dstport"])
        if control_port in {src_port, dst_port}:
            continue
        stream = int(packet["tcp.stream"])
        if stream not in transfers:
            incoming = passive_start <= dst_port <= passive_end
            transfers[stream] = Transfer(
                stream, packet["ip.src"] if incoming else packet["ip.dst"],
                src_port if incoming else dst_port,
                packet["ip.dst"] if incoming else packet["ip.src"],
                dst_port if incoming else src_port, timestamp, timestamp,
            )
        transfers[stream].consume(packet)
    commands = tshark_rows(tshark, capture, COMMAND_FIELDS,
                          'ftp.request.command == "STOR" || ftp.response.code == 227', control_port)
    associate_commands(transfers, commands)
    sources, log_first, log_last = log_context(log)
    for transfer in transfers.values():
        mac = re.search(r"Game_([0-9A-Fa-f]{12})_", transfer.filename)
        if mac:
            transfer.source = sources.get(mac[1].upper(), "unknown")
    warnings = [
        "Live-stream averages and fixed-bin burst peaks do not establish link capacity.",
        "Server-side capture cannot locate loss within Wii Wi-Fi, router, or tunnel hops.",
        "Cumulative ACK delays include gap recovery, not just delayed-ACK policy.",
        "Server-to-peer ACK RTT includes peer behavior; it is not a pure Wi-Fi RTT.",
        "FIN means TCP closed, not that the replay parsed or persisted successfully.",
    ]
    if not packet_count:
        warnings.append("No matching replay FTP packets: check capture interface and port options.")
    if truncated:
        warnings.append("Snapshot truncation prevents full payload validation and may truncate FTP filenames.")
    if first is not None and log_first is not None and (log_last < first or log_first > last):
        warnings.append("Backend log and capture do not overlap; source labels are historical MAC mappings only.")
    if any(not transfer.syn_seen for transfer in transfers.values()):
        warnings.append("Some connections began before capture; window scaling and complete byte totals may be unknown.")
    return {
        "capture": str(capture), "matched_packets": packet_count,
        "start_utc": utc(first) if first is not None else None,
        "end_utc": utc(last) if last is not None else None,
        "truncated_packets": truncated, "log_end_utc": utc(log_last) if log_last is not None else None,
        "warnings": warnings,
        "transfers": [transfer.report() for transfer in transfers.values() if transfer.bytes],
    }


def print_report(report):
    print(f"FTP capture: {report['start_utc']} to {report['end_utc']}")
    print(f"Matching packets: {report['matched_packets']}; data transfers: {len(report['transfers'])}")
    print("\nStream Source           MiB   Avg KiB/s  Peak 1s  Retrans  Server ZeroWin  Filename")
    for transfer in report["transfers"]:
        average = transfer["average_KiB_s"]
        rate = f"{average:.1f}" if average is not None else "n/a"
        print(f"{transfer['stream']:6} {transfer['source']:13} {transfer['unique_bytes']/1048576:6.2f} "
              f"{rate:>10} {transfer['peak_1s_KiB_s']:8.1f} "
              f"{transfer['suspected_retransmitted_packets']:8} "
              f"{transfer['server_tcp_analysis']['zero_window']:15} {transfer['filename'] or '(started before capture/unmapped)'}")
    print("\nInterpretation limits:")
    for warning in report["warnings"]:
        print(f"  {warning}")
    print("\nUse --json for ACK timing, arrival gaps, receive windows, payload sizes, and TCP flags.")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("capture", type=Path)
    parser.add_argument("--log", type=Path, help="Optional backend log for console labels and time-coverage checks")
    parser.add_argument("--tshark", default="tshark", help="Path to the tshark executable")
    parser.add_argument("--control-port", type=int, default=2121)
    parser.add_argument("--passive-start", type=int, default=22100)
    parser.add_argument("--passive-end", type=int, default=22199)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not (1 <= args.control_port <= 65535 and 1 <= args.passive_start <= args.passive_end <= 65535):
        parser.error("Ports must be 1..65535 and passive-start must not exceed passive-end")
    try:
        if not args.capture.is_file():
            raise FileNotFoundError(f"Capture not found: {args.capture}")
        report = analyze(args.capture, args.log, args.tshark, args.control_port, args.passive_start, args.passive_end)
    except (OSError, RuntimeError) as exc:
        print(f"Analysis failed: {exc}. Install Wireshark's tshark CLI if it is missing.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())