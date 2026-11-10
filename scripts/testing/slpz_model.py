"""Reference model of the Wii-side encoder: XOR-delta per event key + greedy LZ77 with fixed-Huffman deflate."""
import struct
import sys
import zlib

WBITS = 12
WSIZE = 1 << WBITS
HBITS = 12
MIN_MATCH, MAX_MATCH = 3, 258
CHAIN = int(__import__("os").environ.get("CHAIN", "1"))
LEN_BASE = [3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19, 23, 27, 31, 35, 43, 51, 59, 67, 83, 99, 115, 131, 163, 195, 227, 258]
LEN_EXTRA = [0] * 8 + [1] * 4 + [2] * 4 + [3] * 4 + [4] * 4 + [5] * 4 + [0]
DIST_BASE = [1, 2, 3, 4, 5, 7, 9, 13, 17, 25, 33, 49, 65, 97, 129, 193, 257, 385, 513, 769, 1025, 1537, 2049, 3073, 4097, 6145, 8193, 12289, 16385, 24577]
DIST_EXTRA = [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 5, 6, 6, 7, 7, 8, 8, 9, 9, 10, 10, 11, 11, 12, 12, 13, 13]


class Bits:
    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def put(self, value, nbits):  # LSB-first
        self.acc |= value << self.n
        self.n += nbits
        while self.n >= 8:
            self.out.append(self.acc & 0xFF)
            self.acc >>= 8
            self.n -= 8

    def put_rev(self, code, nbits):  # Huffman codes go MSB-first
        r = 0
        for _ in range(nbits):
            r = (r << 1) | (code & 1)
            code >>= 1
        self.put(r, nbits)

    def align(self):
        if self.n:
            self.put(0, 8 - self.n)


def lit(b: Bits, sym):
    if sym < 144:
        b.put_rev(0x30 + sym, 8)
    elif sym < 256:
        b.put_rev(0x190 + sym - 144, 9)
    elif sym < 280:
        b.put_rev(sym - 256, 7)
    else:
        b.put_rev(0xC0 + sym - 280, 8)


def put_match(b: Bits, length, dist):
    i = max(k for k in range(29) if LEN_BASE[k] <= length)
    lit(b, 257 + i)
    if LEN_EXTRA[i]:
        b.put(length - LEN_BASE[i], LEN_EXTRA[i])
    j = max(k for k in range(30) if DIST_BASE[k] <= dist)
    b.put_rev(j, 5)
    if DIST_EXTRA[j]:
        b.put(dist - DIST_BASE[j], DIST_EXTRA[j])


class Encoder:
    def __init__(self):
        self.hist = bytearray()  # stands in for the C ring buffer
        self.table = [-1] * (1 << HBITS)
        self.prev = [-1] * WSIZE
        self.bits = Bits()

    def _insert(self, p):
        hv = self._hash(p)
        self.prev[p & (WSIZE - 1)] = self.table[hv]
        self.table[hv] = p

    def _hash(self, p):
        h = self.hist
        return ((h[p] << 8) ^ (h[p + 1] << 4) ^ h[p + 2]) * 2654435761 >> (32 - HBITS) & ((1 << HBITS) - 1)

    def block(self, data: bytes):
        b = self.bits
        b.put(0, 1)  # BFINAL=0
        b.put(1, 2)  # fixed Huffman
        start = len(self.hist)
        self.hist += data
        h = self.hist
        end = len(h)
        p = start
        while p < end:
            best = best_pos = 0
            if p + MIN_MATCH <= end:
                cand = self.table[self._hash(p)]
                limit = min(MAX_MATCH, end - p)
                for _ in range(CHAIN):
                    if cand < 0 or p - cand > WSIZE - 1:
                        break
                    n = 0
                    while n < limit and h[cand + n] == h[p + n]:
                        n += 1
                    if n > best:
                        best, best_pos = n, cand
                        if n == limit:
                            break
                    cand = self.prev[cand & (WSIZE - 1)]
                self._insert(p)
            if best >= MIN_MATCH:
                put_match(b, best, p - best_pos)
                for q in range(p + 1, min(p + best, end - MIN_MATCH + 1)):
                    self._insert(q)
                p += best
            else:
                lit(b, h[p])
                p += 1
        lit(b, 256)
        # sync flush: empty stored block so every byte so far is decodable
        b.put(0, 3)
        b.align()
        b.out += b"\x00\x00\xff\xff"
        out = bytes(b.out)
        b.out.clear()
        return out

    def finish(self):
        b = self.bits
        b.put(1, 1)
        b.put(1, 2)
        lit(b, 256)
        b.align()
        out = bytes(b.out)
        b.out.clear()
        return out


if __name__ == "__main__":
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
    from slp_compress_survey import raw_section, xor_delta  # noqa: E402

    tot_raw = tot_out = 0
    for path in sys.argv[1:]:
        raw = raw_section(open(path, "rb").read())
        d = xor_delta(raw)
        enc = Encoder()
        out = b"".join(enc.block(d[i:i + 2000]) for i in range(0, len(d), 2000)) + enc.finish()
        assert zlib.decompress(out, -15) == d, path
        tot_raw += len(raw)
        tot_out += len(out)
        print(f"{path.rsplit('/', 1)[-1]:40} {len(raw)/1e6:5.2f} MB -> {len(out)/1e6:5.2f} MB ({len(raw)/len(out):.2f}x)")
    print(f"TOTAL {tot_raw/tot_out:.2f}x")
