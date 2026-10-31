"""Header repair for .slp files streamed live (raw length left as a zero placeholder)."""
import pytest

from app.services.replay_identity import identify_slp
from app.services.slp_stream import (
    STREAMED_SLP_HEADER,
    finalize_streamed_slp,
    finalize_streamed_slp_raw_length,
    is_slp_complete,
    patch_partial_slp_raw_length,
)
from tests.test_replay_partials import FOOTER, recording

EVENTS = b"\x35\x01\x36frames"


def _raw_length(data: bytes) -> int:
    return int.from_bytes(data[11:15], "big")


def test_complete_stream_gets_length_up_to_the_metadata_footer():
    streamed = STREAMED_SLP_HEADER + EVENTS + FOOTER
    finalized = finalize_streamed_slp(streamed)
    assert _raw_length(finalized) == len(EVENTS)
    assert finalized[15:] == streamed[15:], "only the header length changes"
    assert is_slp_complete(streamed)


def test_partial_stream_treats_every_received_byte_as_raw_payload():
    streamed = STREAMED_SLP_HEADER + EVENTS
    finalized = finalize_streamed_slp(streamed)
    assert _raw_length(finalized) == len(EVENTS)
    assert not is_slp_complete(streamed)


def test_non_streamed_and_header_only_inputs_pass_through_unchanged():
    on_disk = b"{U\x03raw[$U#l\x00\x00\x00\x06" + EVENTS
    assert finalize_streamed_slp(on_disk) is on_disk
    assert is_slp_complete(on_disk)
    assert finalize_streamed_slp(b"not a replay") == b"not a replay"
    assert patch_partial_slp_raw_length(STREAMED_SLP_HEADER) == STREAMED_SLP_HEADER


def test_strict_finalize_rejects_a_stream_without_its_footer():
    with pytest.raises(ValueError):
        finalize_streamed_slp_raw_length(STREAMED_SLP_HEADER + EVENTS + b"U\x08metadata")


def test_finalized_streams_are_identified_as_complete_or_partial():
    finished, on_disk = recording(3, 20, finished=True)
    cut_short, _ = recording(3, 5, finished=False)
    assert finalize_streamed_slp(finished) == on_disk
    assert identify_slp(finalize_streamed_slp(finished)).is_partial is False
    assert identify_slp(finalize_streamed_slp(cut_short)).is_partial is True


def test_stream_cut_off_inside_the_metadata_footer_is_kept_as_a_partial():
    finished, _ = recording(4, 20, finished=True)
    cut_mid_footer = finished[: len(finished) - len(FOOTER) + 14]
    assert b"U\x08metadata" in cut_mid_footer

    finalized = finalize_streamed_slp(cut_mid_footer)
    assert identify_slp(finalized).is_partial is True
