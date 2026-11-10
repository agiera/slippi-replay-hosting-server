import glob
import struct
import sys
import zlib

import zstandard

CHUNK = 2000  # ~what the Wii uploader sends per 100 ms cycle in steady state


def raw_section(data: bytes) -> bytes:
    i = data.index(b"raw[$U#l") + 8
    n = struct.unpack(">I", data[i:i + 4])[0]
    return data[i + 4:i + 4 + n] if n else data[i + 4:]


def events(raw: bytes):
    assert raw[0] == 0x35
    psize = raw[1]
    sizes = {0x35: psize}
    for j in range(2, 1 + psize, 3):
        sizes[raw[j]] = struct.unpack(">H", raw[j + 1:j + 3])[0]
    pos = 0
    while pos < len(raw):
        cmd = raw[pos]
        n = sizes.get(cmd)
        if n is None:
            break
        yield cmd, raw[pos:pos + 1 + n]
        pos += 1 + n


def key_of(cmd: int, ev: bytes):
    if cmd in (0x37, 0x38) and len(ev) > 6:
        return (cmd, ev[5], ev[6])
    if cmd == 0x3B and len(ev) > 37:
        return (cmd, ev[34:38])
    return (cmd,)


def xor_delta(raw: bytes) -> bytes:
    prev = {}
    out = bytearray()
    for cmd, ev in events(raw):
        k = key_of(cmd, ev)
        p = prev.get(k)
        prev[k] = ev
        if p is not None and len(p) == len(ev) and cmd not in (0x35, 0x36, 0x10):
            out.append(cmd)
            out += bytes(a ^ b for a, b in zip(ev[1:], p[1:]))
        else:
            out += ev
    return bytes(out)


def zlib_stream(buf: bytes, wbits: int, level: int, strategy=zlib.Z_DEFAULT_STRATEGY, memlevel=8) -> int:
    c = zlib.compressobj(level, zlib.DEFLATED, -wbits, memlevel, strategy)
    total = 0
    for i in range(0, len(buf), CHUNK):
        total += len(c.compress(buf[i:i + CHUNK])) + len(c.flush(zlib.Z_SYNC_FLUSH))
    return total + len(c.flush())


def zstd_stream(buf: bytes, level: int) -> int:
    c = zstandard.ZstdCompressor(level=level).compressobj()
    total = 0
    for i in range(0, len(buf), CHUNK):
        total += len(c.compress(buf[i:i + CHUNK])) + len(c.flush(zstandard.COMPRESSOBJ_FLUSH_BLOCK))
    return total + len(c.flush())


def main():
    files = sys.argv[1:] or sorted(glob.glob("backend/uploads/uploads/**/*.slp", recursive=True))[:8]
    variants = {}
    tot_raw = 0
    for path in files:
        raw = raw_section(open(path, "rb").read())
        tot_raw += len(raw)
        d = xor_delta(raw)
        for name, fn in {
            "deflate w15 L6": lambda b: zlib_stream(b, 15, 6),
            "deflate w12 L6": lambda b: zlib_stream(b, 12, 6),
            "deflate w10 L6": lambda b: zlib_stream(b, 10, 6),
            "deflate w12 fixed-huff": lambda b: zlib_stream(b, 12, 6, zlib.Z_FIXED),
            "deflate w10 fixed-huff L1": lambda b: zlib_stream(b, 10, 1, zlib.Z_FIXED),
            "zstd L3 (reference)": lambda b: zstd_stream(b, 3),
        }.items():
            variants[("plain", name)] = variants.get(("plain", name), 0) + fn(raw)
            variants[("xor-delta", name)] = variants.get(("xor-delta", name), 0) + fn(d)

    print(f"{len(files)} replays, raw {tot_raw/1e6:.1f} MB, streamed in {CHUNK} B chunks with sync flush")
    for (pre, name), v in sorted(variants.items(), key=lambda kv: kv[1]):
        print(f"  {pre:10} {name:28} ratio {tot_raw/v:5.2f}x")


if __name__ == "__main__":
    main()
