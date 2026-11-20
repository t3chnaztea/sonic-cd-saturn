#!/usr/bin/env python3
"""Named spans of the user's retail disc, checked by SHA-256.

The repository holds no retail bytes. A tool that needs a known piece of
retail code or script data names it by disc file, offset, length and the
SHA-256 of those bytes. disc_span() reads the bytes from the user's disc and
raises AssertionError unless the digest matches, so the tool sees exactly
the bytes it expects or stops.
"""
import functools
import hashlib

from convert_assets import ROOT
from extract_mmd import disc_files


@functools.lru_cache(maxsize=None)
def disc():
    return disc_files((ROOT/'build/retail/sonic.iso').read_bytes())


def disc_span(name, offset, length, sha256):
    data = disc()[name][offset:offset+length]
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != length or digest != sha256:
        raise AssertionError(f'{name}+{offset:#x}/{length}: sha256 {digest} != {sha256}')
    return data
