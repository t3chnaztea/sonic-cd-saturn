#!/usr/bin/env python3
"""Gate: the linked libyaul sizes the VDP DMA indirect table for all 16 requests.

Unpatched libyaul 6012f79 allocates sizeof(dma_queue_t) * 16 = 128 bytes, but
each scu_dma_xfer_t is 12 bytes. The 11th vdp_dma_enqueue in a frame therefore
overwrote the next private-pool block (the DMA callback list), and the next
VBlank took a CPU address error (Tidal Tempest Act 1 route, seq 276).
tools/patches/libyaul-dma-queue-table.patch (applied by tools/fetch_sources.py)
sizes it with sizeof(scu_dma_xfer_t). This gate checks:
  1. .deps/libyaul carries the patch (git apply --reverse --check);
  2. the installed .toolchain/sh-elf/lib/libyaul.a allocates 192 bytes in
     __dma_queue_request_init (the memalign size argument, r5);
  3. src/vdp_dma_guard.h queues game requests up to DMA_QUEUE_REQUESTS_MAX_COUNT
     minus at least 2 slots reserved for Yaul's own enqueues.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'tools/patches/libyaul-dma-queue-table.patch'
LIB = ROOT / '.toolchain/sh-elf/lib/libyaul.a'
XFER_BYTES, REQUESTS = 12, 16


def fail(message):
    print(f'FAIL: libyaul DMA queue table: {message}')
    raise SystemExit(1)


def main():
    if subprocess.run(['git', '-C', ROOT / '.deps/libyaul', 'apply', '--reverse', '--check', PATCH],
                      capture_output=True).returncode:
        fail(f'.deps/libyaul lacks {PATCH.relative_to(ROOT)} (run python3 tools/fetch_sources.py, then reinstall libyaul)')
    header = (ROOT / '.deps/libyaul/libyaul/kernel/sys/dma-queue.h').read_text()
    requests = int(re.search(r'#define DMA_QUEUE_REQUESTS_MAX_COUNT \((\d+)\)', header)[1])
    text = (ROOT / 'src/vdp_dma_guard.h').read_text()
    queue = int(re.search(r'#define SCD_VDP_DMA_QUEUE (\d+)u', text)[1])
    reserved = int(re.search(r'#define SCD_VDP_DMA_RESERVED (\d+)u', text)[1])
    if 'SCD_VDP_DMA_CAPACITY (SCD_VDP_DMA_QUEUE-SCD_VDP_DMA_RESERVED)' not in text:
        fail('guard capacity is not SCD_VDP_DMA_QUEUE-SCD_VDP_DMA_RESERVED')
    guard = queue - reserved
    if requests != REQUESTS or queue != requests or reserved < 2:
        fail(f'capacity mismatch: yaul {requests}, guard queue {queue} reserved {reserved}, expected {REQUESTS} with >=2 reserved')
    with tempfile.TemporaryDirectory() as temp:
        subprocess.run([ROOT / '.toolchain/bin/sh-elf-ar', 'x', LIB, 'dma-queue-internal.o'], cwd=temp, check=True)
        listing = subprocess.check_output([ROOT / '.toolchain/bin/sh-elf-objdump', '-d', Path(temp) / 'dma-queue-internal.o'], text=True)
    body = listing.split('<___dma_queue_request_init>:', 1)
    if len(body) != 2:
        fail('___dma_queue_request_init not found in libyaul.a')
    body = body[1].split('\n\n', 1)[0]
    size = re.search(r'mov\.w\s+[^\n]*?,r5\s+!\s*([0-9a-f]+)', body)
    if not size:
        fail('memalign size argument (r5) not found')
    got, want = int(size[1], 16), XFER_BYTES * REQUESTS
    if got != want:
        fail(f'installed libyaul.a allocates {got} bytes, needs {want} (reinstall: gmake -C .deps/libyaul install-release)')
    print(f'PASS: libyaul DMA queue table {got} bytes for {requests} requests; guard capacity {guard} ({reserved} reserved)')


if __name__ == '__main__':
    main()
