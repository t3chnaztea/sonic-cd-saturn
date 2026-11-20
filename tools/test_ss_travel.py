#!/usr/bin/env python3
"""Controller-only Stardust Speedway natural travel and Saturn arrival.

Five pairs per act: A->B, A->D, B->A, C->A, D->A. Host-only searches
prove warp commitment, not arrival or Saturn acceptance. The shared arrival
harness requires an explicitly matching SS BIN/ELF for target verification.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from test_qq_route import NATIVE, ORIGINAL, sha
from test_tt_travel import ROOT
import retail_parity
from test_qq_travel import host_source as qq_host_source
from test_tt_travel import once, run_travel


def host_source(want):
    # Retain the exact gameplay step, collision and streaming of ROUTE_SS.
    # Only the search objective and committed-warp termination differ.
    return once(qq_host_source(want), 'QQ natural travel:', 'SS natural travel:')


def main():
    # Keep shared CLI behavior. This optional SS-only mode checks prewarp
    # retail positions; it does not pretend to follow retail arrival.
    retail = '--retail-prefix' in sys.argv
    if retail:
        sys.argv.remove('--retail-prefix')
    if '--help' in sys.argv:
        print('SS option: --retail-prefix adds whole-prefix retail host comparison.')
    # music_routes.h: SS zone5 uses slot26+era; mailbox adds2.
    run_travel(dict(label='SS', zone=5, routes='tests/routes/ss/travel', prefix='ss',
                    host_source=host_source, native=NATIVE, original=ORIGINAL,
                    seed=51, limit=46000, track=28, vblank_timer=True,
                    defines=['-DROUTE_SS'], doc=__doc__))
    output_parser = argparse.ArgumentParser(add_help=False)
    output_parser.add_argument('--output', type=Path, required=True)
    args, _ = output_parser.parse_known_args()
    out = args.output.resolve()
    report_path = out/'report.json'
    report = json.loads(report_path.read_text())
    report['host_warp_passed'] = True
    paths = [ROOT/n for n in NATIVE]
    paths += [ROOT/'build/probe-source'/f'{n}.c' for n in ORIGINAL]
    paths += sorted((ROOT/'assets/generated').glob('ss*.bin'))
    report['ss_input_sha256'] = {str(p.relative_to(ROOT)): sha(p) for p in paths}
    if report['status'] == 'host-only':
        report['limits'] = ('Controller-only native warp commitment. No host arrival, '
                            'Saturn arrival, final-BIN gate or hardware acceptance.')
    try:
        if retail:
            act, era = report['act'], report['era']
            result = retail_parity.retail_parity(
                out/'search', lambda h, s, rows: [h, 'replay', f'{act-1}:{era}', s, '46000', rows],
                'QQ_ROUTE', 7, act, era, out/'script.txt', out,
                report['host_positions'], lag_sync=True)
            report['retail_prefix'] = result
            end = re.search(r'SS natural travel: sequence=(\d+) act=(\d+) era=(\d+) destination=(\d+) ticks=(\d+)',
                            result.get('native_end') or '')
            report['retail_prefix_passed'] = (result['compared'] > 0 and
                result['contiguous_all_fields'] == result['compared'] and end is not None and
                int(end[4]) == report['destination'] and int(end[5]) >= 230)
            report['retail_prefix_limits'] = (
                'Diagnostic source-era prefix only. Retail VBlank charge timing may '
                'commit earlier or later than the cold native route. A differing prefix '
                'does not establish a gameplay defect or a final-BIN travel failure.')
            verdict = 'matched' if report['retail_prefix_passed'] else 'differs or ends before commit'
            print(f'CHECK: SS{act}{era} retail prefix {verdict}; '
                  f'{result["contiguous_all_fields"]}/{result["compared"]} contiguous all fields; arrival pending')
    except BaseException as error:
        report.update(status='interrupted' if isinstance(error, KeyboardInterrupt) else 'failed',
                      passed=False, error=repr(error))
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
