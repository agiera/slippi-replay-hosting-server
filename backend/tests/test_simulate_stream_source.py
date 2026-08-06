import importlib.util
import io
import json
from pathlib import Path


def _load_simulator_module():
    base = Path(__file__).resolve()
    candidates = [
        base.parents[1] / "scripts" / "simulate_stream_source.py",
        base.parents[2] / "scripts" / "simulate_stream_source.py",
    ]
    script_path = next((path for path in candidates if path.is_file()), None)
    assert script_path is not None, "simulate_stream_source.py not found in expected locations"
    spec = importlib.util.spec_from_file_location("simulate_stream_source", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeFTP:
    def __init__(self):
        self.commands: list[tuple[str, bytes]] = []
        self.blocksizes: list[int | None] = []

    def storbinary(self, command: str, fileobj: io.BytesIO, blocksize: int | None = None) -> None:
        self.commands.append((command, fileobj.read()))
        self.blocksizes.append(blocksize)


def test_upload_replay_file_once_sends_generated_sidecar_before_replay(tmp_path):
    module = _load_simulator_module()
    ftp = FakeFTP()
    replay_path = tmp_path / "Game_20260721T193323.slp"
    replay_path.write_bytes(b"replay-bytes")

    module.upload_replay_file_once(ftp, replay_path, None, ubjson_hex="deadbeef")

    assert [command for command, _ in ftp.commands] == [
        "STOR Game_20260721T193323.slp.meta.json",
        "STOR Game_20260721T193323.slp",
    ]
    sidecar_payload = json.loads(ftp.commands[0][1].decode("utf-8"))
    assert sidecar_payload == {"ubjson_hex": "deadbeef"}
    assert ftp.commands[1][1] == b"replay-bytes"
    assert ftp.blocksizes == [None, 8192]


def test_upload_replay_file_once_prefers_explicit_sidecar_file(tmp_path):
    module = _load_simulator_module()
    ftp = FakeFTP()
    replay_path = tmp_path / "Game_20260721T193323.slp"
    replay_path.write_bytes(b"replay-bytes")
    sidecar_path = tmp_path / "seed.meta.json"
    sidecar_path.write_text('{"ubjson_hex":"cafebabe"}', encoding="utf-8")

    module.upload_replay_file_once(ftp, replay_path, sidecar_path, ubjson_hex="deadbeef")

    assert [command for command, _ in ftp.commands] == [
        "STOR Game_20260721T193323.slp.meta.json",
        "STOR Game_20260721T193323.slp",
    ]
    assert ftp.commands[0][1] == sidecar_path.read_bytes()
    assert ftp.commands[1][1] == b"replay-bytes"
    assert ftp.blocksizes == [None, 8192]


def test_upload_replay_file_once_uses_configured_blocksize(tmp_path):
    module = _load_simulator_module()
    ftp = FakeFTP()
    replay_path = tmp_path / "Game_20260721T193323.slp"
    replay_path.write_bytes(b"abcdefgh")

    module.upload_replay_file_once(
        ftp,
        replay_path,
        None,
        upload_chunk_bytes=3,
        upload_chunk_delay_seconds=0,
    )

    assert ftp.blocksizes == [3]


def test_paced_bytes_io_limits_each_read_to_chunk_size():
    module = _load_simulator_module()

    paced = module._paced_bytes_io(b"abcdef", 2, 0.01)

    assert paced.read(8192) == b"ab"
    assert paced.read(8192) == b"cd"
    assert paced.read(8192) == b"ef"