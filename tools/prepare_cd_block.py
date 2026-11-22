#!/usr/bin/env python3
"""Build a local override of pinned Yaul CD commands with correct status decoding.

Do not mutate the dependency or installed SDK. The application object supplies
the command symbols before libyaul.a; the remaining CD implementation is unchanged.
"""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'.deps/libyaul/libyaul/scu/bus/a/cs2/cd-block'
OUT=ROOT/'build/cd-block'
def write_if_changed(path,data):
    if not path.exists() or path.read_bytes()!=data:
        path.write_bytes(data)
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    code=(SRC/'cd-block_cmds.c').read_text()
    pattern=r'static int\n_return_status_check\(cd_block_regs_t \*status\)\n\{.*?\n\}'
    original=re.search(pattern,code,re.S)
    assert original and 'status->cr1 & 0xFF' in original[0] and 'status_flags & CD_STATUS_FATAL' in original[0]
    write_if_changed(OUT/'cd-status-original-test.inc',(original[0].replace('_return_status_check','original_status_check')+'\n').encode())
    replacement='''volatile uint16_t scd_cd_last_response;
static int
_return_status_check(cd_block_regs_t *status)
{
    assert(status != NULL);
    scd_cd_last_response = status->cr1;
    return scd_cd_response_error(status->cr1);
}'''
    code=code[:original.start()]+replacement+code[original.end():]
    code=code.replace('#include <cd-block.h>', '#ifdef SCD_CD_HOST_TEST\n#include "cd_block_mock.h"\n#else\n#include <yaul.h>\n#endif\n#include "cd_status.h"')
    code=code.replace('#include <smpc/smc.h>','')
    write_if_changed(OUT/'cd-block_cmds.c',code.encode())
    internal=(SRC/'cd-block-internal.h').read_text().replace('#include <scu-internal.h>','/* Public Yaul or the host mock supplies MMIO macros. */')
    write_if_changed(OUT/'cd-block-internal.h',internal.encode())
    write_if_changed(OUT/'cd-command-api.h',(SRC/'cd-block/cmd.h').read_bytes())
    init=(SRC/'cd-block_init.c').read_text()
    fn=re.search(r'int\ncd_block_init\(void\)\n\{.*?\n\}',init,re.S)
    assert fn
    write_if_changed(OUT/'cd-block-init-test.inc',(fn[0]+'\n').encode())
    write_if_changed(OUT/'LICENSE',(ROOT/'.deps/libyaul/LICENSE').read_bytes())
    report={'upstream_commands_sha256':hashlib.sha256((SRC/'cd-block_cmds.c').read_bytes()).hexdigest(),
            'generated_commands_sha256':hashlib.sha256(code.encode()).hexdigest(),
            'change':'Decode CR1 high-byte enumerated status, preserving report byte and genuine errors'}
    write_if_changed(OUT/'source-report.json',(json.dumps(report,indent=2)+'\n').encode())
    print('Prepared project-local CD command status fix; pinned SDK unchanged')
if __name__=='__main__':main()
