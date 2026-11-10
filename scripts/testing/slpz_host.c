// Host harness for kernel/SlippiCompress.c: encodes a .slp the way the Wii streams it.
// Build: gcc -O2 -DSLPZ_HOST_TEST -I<nintendont>/kernel slpz_host.c <nintendont>/kernel/SlippiCompress.c
#include <stdio.h>
#include <stdlib.h>

#include "SlippiCompress.h"

static FILE* out_file;

static int sink(const u8* data, u32 len)
{
	return fwrite(data, 1, len, out_file) == len ? 0 : -1;
}

int main(int argc, char** argv)
{
	if (argc < 3) {
		fprintf(stderr, "usage: %s in.slp out.slpz [chunk]\n", argv[0]);
		return 2;
	}
	FILE* in = fopen(argv[1], "rb");
	out_file = fopen(argv[2], "wb");
	u32 chunk = argc > 3 ? (u32)atoi(argv[3]) : 10000;
	static u8 buf[1 << 24];
	size_t n = fread(buf, 1, sizeof(buf), in);
	// Like SlippiFileWriter: a 15-byte header write, then ring-buffer sized reads.
	slpz_reset();
	if (slpz_write(buf, n < 15 ? n : 15, sink) < 0)
		return 1;
	for (size_t pos = 15; pos < n; pos += chunk) {
		u32 len = n - pos < chunk ? n - pos : chunk;
		if (slpz_write(buf + pos, len, sink) < 0)
			return 1;
	}
	if (slpz_finish(sink) < 0)
		return 1;
	fclose(out_file);
	fprintf(stderr, "%zu -> %ld bytes (%.2fx)\n", n, ftell(in), 0.0);
	return 0;
}
