"""Root of the scddisasm-layout data tree that build tools read.

Default: the pinned scddisasm checkout in .deps/scddisasm (unchanged).
SCD_DATA_ROOT=<dir> points the tools at another tree in the same layout,
such as build/retail-src made from the user's disc by tools/retail_src.py.
A relative value is resolved against the repository root.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCD = ROOT / (os.environ.get('SCD_DATA_ROOT') or '.deps/scddisasm')
SRC = SCD / 'src'
