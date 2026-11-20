#!/usr/bin/env python3
"""Tidal Tempest retail probe: tools/retail_probe.py with --round 4 by default.

usage: tt_retail_probe.py ACT ERA SCRIPT OUTPUT [UPDATES] [--native-unlock N] [--round 4|6]
"""
import sys

sys.path.insert(0, 'tools')
import retail_probe

if __name__ == '__main__':
    retail_probe.main(default_round=4)
