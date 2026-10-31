import socket
import struct

from app.services.ack_repeater import ACK, FIN, RST, SYN, AckRepeater, parse_segment, with_tcp_checksum

SERVER = socket.inet_aton("100.75.218.6")
WII = socket.inet_aton("100.102.146.120")
PORTS = range(22100, 22200)


def _packet(src, dst, sport, dport, *, seq=0, ack=0, flags=ACK, payload=b""):
    tcp = struct.pack("!HHIIBBHHH", sport, dport, seq, ack, 5 << 4, flags, 65535, 0, 0)
    ip = struct.pack("!BBHHHBBH4s4s", 0x45, 0, 40 + len(payload), 0, 0, 64, socket.IPPROTO_TCP, 0, src, dst)
    return ip + tcp + payload


def _server_ack(ack, *, port=22150, flags=ACK):
    return _packet(SERVER, WII, port, 40000, seq=1, ack=ack, flags=flags)


def _wii(seq, *, length=536, flags=ACK):
    return _packet(WII, SERVER, 40000, 22150, seq=seq, ack=1, flags=flags, payload=b"x" * length)


def test_parse_segment_reports_payload_length():
    seg = parse_segment(_wii(1000, length=536))
    assert (seg.sport, seg.dport, seg.seq, seg.payload_len) == (40000, 22150, 1000, 536)
    assert parse_segment(b"\x60" + bytes(39)) is None  # IPv6


def test_repeats_latest_ack_with_capped_backoff_while_wii_is_silent():
    rep = AckRepeater(PORTS, first_delay=0.3, max_interval=1.0)
    ack = with_tcp_checksum(_server_ack(5000))
    rep.observe(ack, outgoing=True, now=0.0)

    assert rep.due(0.29) == []
    assert rep.due(0.3) == [ack]
    rep.observe(ack, outgoing=True, now=0.3)  # the sniffer sees our own copy go out
    assert rep.due(0.8) == []
    assert rep.due(0.9) == [ack]  # interval doubled to 0.6
    assert rep.due(1.9) == [ack]  # capped at 1.0
    assert rep.due(2.9) == [ack]
    assert rep.stats["repeats"] == 4


def test_repeated_copy_carries_a_complete_tcp_checksum():
    # Offloaded packets are captured with only the pseudo-header sum in the checksum field.
    offloaded = bytearray(_server_ack(5000))
    offloaded[36:38] = b"\x12\x34"
    rep = AckRepeater(PORTS)
    rep.observe(bytes(offloaded), outgoing=True, now=0.0)

    [copy] = rep.due(1.0)

    pseudo = copy[12:20] + struct.pack("!BBH", 0, socket.IPPROTO_TCP, len(copy) - 20) + copy[20:]
    total = sum(struct.unpack(f"!{len(pseudo) // 2}H", pseudo))
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    assert total == 0xFFFF
    assert copy[:36] == bytes(offloaded[:36])


def test_wii_new_data_stops_repeats_and_counts_as_resumed():
    rep = AckRepeater(PORTS)
    rep.observe(_server_ack(5000), outgoing=True, now=0.0)
    rep.due(0.3)

    rep.observe(_wii(5000), outgoing=False, now=0.35)

    assert rep.stats["resumed"] == 1
    assert rep.due(100.0) == []


def test_wii_resending_acked_data_counts_as_missed():
    rep = AckRepeater(PORTS)
    rep.observe(_server_ack(5000), outgoing=True, now=0.0)
    rep.due(0.3)

    rep.observe(_wii(4464), outgoing=False, now=1.6)

    assert rep.stats["retransmitted_anyway"] == 1


def test_wii_data_before_first_repeat_is_not_counted():
    rep = AckRepeater(PORTS)
    rep.observe(_server_ack(5000), outgoing=True, now=0.0)
    rep.observe(_wii(5000), outgoing=False, now=0.1)

    assert rep.due(1.0) == []
    assert not rep.stats


def test_newer_ack_replaces_older_and_restarts_delay():
    rep = AckRepeater(PORTS, first_delay=0.3)
    rep.observe(_server_ack(5000), outgoing=True, now=0.0)
    newer = with_tcp_checksum(_server_ack(5536))
    rep.observe(newer, outgoing=True, now=0.2)

    assert rep.due(0.4) == []
    assert rep.due(0.5) == [newer]


def test_wii_pure_ack_does_not_cancel():
    rep = AckRepeater(PORTS)
    ack = with_tcp_checksum(_server_ack(5000))
    rep.observe(ack, outgoing=True, now=0.0)
    rep.observe(_wii(5000, length=0), outgoing=False, now=0.1)

    assert rep.due(0.3) == [ack]


def test_connection_teardown_and_give_up_stop_repeats():
    for teardown, outgoing in ((_wii(5000, length=0, flags=FIN | ACK), False),
                               (_wii(5000, length=0, flags=RST), False),
                               (_server_ack(5000, flags=FIN | ACK), True)):
        rep = AckRepeater(PORTS)
        rep.observe(_server_ack(5000), outgoing=True, now=0.0)
        rep.observe(teardown, outgoing=outgoing, now=0.1)
        assert rep.due(1.0) == []

    rep = AckRepeater(PORTS, give_up_after=10.0)
    rep.observe(_server_ack(5000), outgoing=True, now=0.0)
    assert rep.due(10.1) == []
    assert rep.armed_flows == 0


def test_ignores_control_port_handshakes_and_unrelated_traffic():
    rep = AckRepeater(PORTS)
    rep.observe(_server_ack(5000, port=2121), outgoing=True, now=0.0)
    rep.observe(_server_ack(5000, flags=SYN | ACK), outgoing=True, now=0.0)
    rep.observe(_packet(SERVER, WII, 443, 50000, ack=9), outgoing=True, now=0.0)

    assert rep.due(5.0) == []
