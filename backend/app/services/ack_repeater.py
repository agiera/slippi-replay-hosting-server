"""Re-send the FTP data channel's latest ACK to a Wii that goes quiet.

Wiis ignore the ACK inside keepalive probes but resume within ~50 ms of an
ordinary in-window ACK, and individual ACKs to them are often lost on venue
Wi-Fi. Runs in the FTP server's network namespace, so copies take the same
route (and Docker NAT) as the originals. Needs CAP_NET_RAW, which Docker grants
by default.
"""

from __future__ import annotations

import collections
import logging
import select
import socket
import struct
import threading
import time
from dataclasses import dataclass

logger = logging.getLogger(__name__)

ETH_P_ALL = 0x0003
PACKET_OUTGOING = 4
FIN, SYN, RST, ACK = 0x01, 0x02, 0x04, 0x10


@dataclass(frozen=True)
class Segment:
    src: bytes
    dst: bytes
    sport: int
    dport: int
    seq: int
    ack: int
    flags: int
    payload_len: int


def parse_segment(packet: bytes) -> Segment | None:
    if len(packet) < 20 or packet[0] >> 4 != 4 or packet[9] != socket.IPPROTO_TCP:
        return None
    ihl = (packet[0] & 0x0F) * 4
    if len(packet) < ihl + 14:
        return None
    total_len = struct.unpack_from("!H", packet, 2)[0]
    sport, dport, seq, ack, offset, flags = struct.unpack_from("!HHIIBB", packet, ihl)
    return Segment(packet[12:16], packet[16:20], sport, dport, seq, ack, flags, total_len - ihl - (offset >> 4) * 4)


def with_tcp_checksum(packet: bytes) -> bytes:
    """Return the packet with a complete TCP checksum.

    Captured outgoing packets may carry only the partial sum left for checksum offload.
    """
    ihl = (packet[0] & 0x0F) * 4
    total_len = struct.unpack_from("!H", packet, 2)[0]
    segment = bytearray(packet[ihl:total_len])
    segment[16:18] = b"\x00\x00"
    data = packet[12:20] + struct.pack("!BBH", 0, socket.IPPROTO_TCP, len(segment)) + segment
    if len(data) % 2:
        data += b"\x00"
    total = sum(struct.unpack(f"!{len(data) // 2}H", data))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    segment[16:18] = struct.pack("!H", ~total & 0xFFFF)
    return packet[:ihl] + bytes(segment)


def seq_geq(a: int, b: int) -> bool:
    return (a - b) & 0xFFFFFFFF < 0x80000000


@dataclass
class _Pending:
    packet: bytes
    ack: int
    acked_at: float
    next_send: float
    interval: float
    repeated: bool = False


class AckRepeater:
    """Tracks each data flow's latest server pure ACK and when to repeat it."""

    def __init__(
        self,
        ports: range,
        first_delay: float = 0.3,
        max_interval: float = 4.0,
        give_up_after: float = 150.0,
    ) -> None:
        self.ports = ports
        self.first_delay = first_delay
        self.max_interval = max_interval
        self.give_up_after = give_up_after
        self.stats: collections.Counter[str] = collections.Counter()
        self._pending: dict[tuple[bytes, int, int], _Pending] = {}

    def observe(self, packet: bytes, outgoing: bool, now: float) -> None:
        seg = parse_segment(packet)
        if seg is None:
            return
        if outgoing and seg.sport in self.ports:
            key = (seg.dst, seg.dport, seg.sport)
            if seg.flags & (SYN | FIN | RST) or not seg.flags & ACK or seg.payload_len:
                self._pending.pop(key, None)
                return
            pending = self._pending.get(key)
            if pending is not None and packet == pending.packet:
                return  # our own copy seen on the way out
            self._pending[key] = _Pending(with_tcp_checksum(packet), seg.ack, now, now + self.first_delay, self.first_delay)
        elif not outgoing and seg.dport in self.ports:
            key = (seg.src, seg.sport, seg.dport)
            if seg.flags & (FIN | RST):
                self._pending.pop(key, None)
            elif seg.payload_len:
                pending = self._pending.pop(key, None)
                if pending is not None and pending.repeated:
                    # New data means a repeat (or a late original) got through; old data means it did not.
                    self.stats["resumed" if seq_geq(seg.seq, pending.ack) else "retransmitted_anyway"] += 1

    def due(self, now: float) -> list[bytes]:
        packets = []
        for key, pending in list(self._pending.items()):
            if now - pending.acked_at > self.give_up_after:
                del self._pending[key]
            elif now >= pending.next_send:
                packets.append(pending.packet)
                pending.repeated = True
                pending.interval = min(pending.interval * 2, self.max_interval)
                pending.next_send = now + pending.interval
                self.stats["repeats"] += 1
        return packets

    def next_deadline(self) -> float | None:
        return min((p.next_send for p in self._pending.values()), default=None)

    @property
    def armed_flows(self) -> int:
        return len(self._pending)


class AckRepeaterThread(threading.Thread):
    def __init__(self, ports: range, stats_every: float = 60.0) -> None:
        super().__init__(name="ack-repeater", daemon=True)
        self.repeater = AckRepeater(ports)
        self._stats_every = stats_every
        self._stopping = threading.Event()
        # Both raise PermissionError without CAP_NET_RAW.
        self._sniffer = socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(ETH_P_ALL))
        try:
            self._sender = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        except OSError:
            self._sniffer.close()
            raise

    def stop(self) -> None:
        self._stopping.set()
        self.join(timeout=2)
        self._sniffer.close()
        self._sender.close()

    def run(self) -> None:
        ports = self.repeater.ports
        logger.info("[FTP] ACK repeater watching passive ports %s-%s", ports.start, ports.stop - 1)
        stats = self.repeater.stats
        last_logged = None
        next_stats = time.monotonic() + self._stats_every
        while not self._stopping.is_set():
            deadline = self.repeater.next_deadline()
            timeout = 1.0 if deadline is None else min(1.0, max(0.0, deadline - time.monotonic()))
            if select.select([self._sniffer], [], [], timeout)[0]:
                packet, address = self._sniffer.recvfrom(65535)
                self.repeater.observe(packet, address[2] == PACKET_OUTGOING, time.monotonic())
            now = time.monotonic()
            for packet in self.repeater.due(now):
                try:
                    self._sender.sendto(packet, (socket.inet_ntoa(packet[16:20]), 0))
                except OSError as exc:
                    logger.debug("[FTP][TRACE] ACK repeat send failed: %s", exc)
            if now >= next_stats:
                snapshot = (stats["repeats"], stats["resumed"], stats["retransmitted_anyway"])
                if snapshot != last_logged:
                    logger.info(
                        "[FTP] ACK repeater repeats=%d resumed=%d retransmitted_anyway=%d armed_flows=%d",
                        *snapshot, self.repeater.armed_flows,
                    )
                    last_logged = snapshot
                next_stats = now + self._stats_every
