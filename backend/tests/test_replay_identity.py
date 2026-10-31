"""Edge cases for recognizing which recording an .slp belongs to."""
from app.services.replay_identity import identify_slp
from tests.test_replay_partials import recording

HEADER = b"{U\x03raw[$U#l\x00\x00\x00\x00"


def test_game_key_depends_only_on_the_payload_table_and_game_start():
    a, _ = recording(5, 3, finished=False)
    b, _ = recording(5, 300, finished=False)
    assert identify_slp(a).game_key == identify_slp(b).game_key
    assert identify_slp(a).game_key != identify_slp(recording(6, 3, finished=False)[0]).game_key


def test_malformed_headers_are_not_identified():
    game_start = bytes([0x36]) + (1).to_bytes(4, "big")
    cases = {
        "first event is not Event Payloads": HEADER + bytes([0x36, 4]) + game_start,
        "payload table size is not 1 + 3n": HEADER + bytes([0x35, 5, 0x36, 0, 4, 0]) + game_start,
        "Game Start not declared in the table": HEADER + bytes([0x35, 4, 0x37, 0, 2]) + game_start,
        "event after the table is not Game Start": HEADER + bytes([0x35, 4, 0x36, 0, 4, 0x37, 0, 0, 0, 0]),
        "Game Start payload truncated": HEADER + bytes([0x35, 4, 0x36, 0, 4]) + game_start[:3],
        "empty payload table": HEADER + bytes([0x35, 0]) + game_start,
    }
    for label, data in cases.items():
        assert identify_slp(data) is None, label


def test_on_disk_partial_with_backfilled_length_but_no_footer_is_partial():
    streamed, _ = recording(8, 10, finished=False)
    patched = bytearray(streamed)
    patched[11:15] = (len(streamed) - len(HEADER)).to_bytes(4, "big")
    identity = identify_slp(bytes(patched))
    assert identity.is_partial is True
    assert identity.game_key == identify_slp(streamed).game_key


def test_footer_must_sit_exactly_at_the_declared_raw_length():
    _, on_disk = recording(8, 10, finished=True)
    wrong = bytearray(on_disk)
    wrong[11:15] = (int.from_bytes(on_disk[11:15], "big") - 1).to_bytes(4, "big")
    assert identify_slp(on_disk).is_partial is False
    assert identify_slp(bytes(wrong)).is_partial is True
