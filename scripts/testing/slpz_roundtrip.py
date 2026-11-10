"""Round-trip real replays through the kernel encoder (host build) and the server decoder."""
import importlib.util
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KERNEL = REPO.parent / "slippi-nintendont" / "kernel"

spec = importlib.util.spec_from_file_location("slpz", REPO / "backend/app/services/slpz.py")
slpz = importlib.util.module_from_spec(spec)
spec.loader.exec_module(slpz)


def main() -> int:
    exe = Path(tempfile.gettempdir()) / "slpz_host"
    subprocess.run(
        ["gcc", "-O2", "-Wall", "-Wextra", "-DSLPZ_HOST_TEST", "-iquote", str(KERNEL), "-o", str(exe),
         str(HERE / "slpz_host.c"), str(KERNEL / "SlippiCompress.c")],
        check=True,
    )
    chunk = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1].isdigit() else "10000"
    files = [a for a in sys.argv[1:] if not a.isdigit()]
    total_in = total_out = 0
    for path in files:
        data = Path(path).read_bytes()
        with tempfile.NamedTemporaryFile(suffix=".slpz") as tmp:
            t0 = time.perf_counter()
            subprocess.run([str(exe), path, tmp.name, chunk], check=True, stderr=subprocess.DEVNULL)
            elapsed = time.perf_counter() - t0
            encoded = Path(tmp.name).read_bytes()
        decoded = slpz.decode_slpz(encoded)
        ok = decoded == data
        total_in += len(data)
        total_out += len(encoded)
        print(f"{Path(path).name:40} {len(data)/1e6:5.2f} MB -> {len(encoded)/1e6:5.2f} MB "
              f"({len(data)/len(encoded):.2f}x) {elapsed*1000:.0f} ms {'OK' if ok else 'MISMATCH'}")
        if not ok:
            first = next(i for i, (a, b) in enumerate(zip(decoded, data)) if a != b) if len(decoded) and decoded[:1] == data[:1] else 0
            print(f"  first mismatch at byte {first}, decoded {len(decoded)} vs {len(data)}")
            return 1
    print(f"TOTAL {total_in/total_out:.2f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
