#!/usr/bin/env python3
"""Build independent original GA, COLI3 and console-compatible animation reference."""
from pathlib import Path
import re,sys
sys.path.insert(0,'tools')
from cc_ga_source import verify
verify() # Same original AnimateObject: no PC sentinel scan or delay clamp.
src=Path('build/audit/source/src')
ga=(src/'R3/GA3.C').read_text();ga=ga[ga.index('static char pchg0'):]
ga=re.sub(r'\w+->patbase = \w+;', '(void)0;',ga)
p=(src/'PLAYSUB.C').read_text().split('void patchg(sprite_status* patchgwk')[1]
p='void patchg(sprite_status* patchgwk'+p[:p.index('\n}')+2]
# PC scans for a sentinel not present in GA's timed emergence scripts. The
# verified console routine simply reloads the first byte and reads the pose.
p=re.sub(r'  while \(sprpat_adr\[search_end\+\+\] < 250\);[^\n]*','',p)
p=p.replace('sprpat_adr[search_end - 1] != 252 && *sprpat_adr <= 0 ? 1 : *sprpat_adr','*sprpat_adr')
c=(src/'R3/COLI3.C').read_text()
col=c[c.index('static unsigned char bCarry;'):c.index('short pcolitem(')]
col+=c[c.index('short pcolnomal('):c.index('short pcolplay2(')]
col=col.replace('  CollitblDataYchk(pActwk, pColliAct, iYposi, iColiNo, iD5);','  return CollitblDataYchk(pActwk, pColliAct, iYposi, iColiNo, iD5);')
col=col.replace('&actwk[32]','&actwk[100]').replace('i < 96','i < 28')
suicide=(src/'SUICIDE.C').read_text();suicide=suicide[suicide.index('short enemy_suicide('):suicide.index('short friend_suicide(')]
body=ga+p+col+suicide
header='''#include "EQU.H"
void actionsub(sprite_status*); int frameout_s(sprite_status*); void frameout(sprite_status*);
int actwkchk(sprite_status**); void soundset(short); void scoreup(int);
unsigned char CCset(unsigned short,unsigned short); unsigned char CSset(unsigned short,unsigned short);
short pcolplay(sprite_status*,sprite_status*); short pcolspecial(sprite_status*,sprite_status*); short pcolitem(sprite_status*,sprite_status*);
'''
prototypes=';\n'.join(re.findall(r'^(?:static )?(?:void|short) \w+\([^\n{]+\)',body,re.M))+';\n'
body=re.sub(r'\(\((unsigned short|short|int)\*\)(\w+)\)\[(\d+)\]',lambda m:f'(*({m[1]}*)((char*)({m[2]})->actfree+{(4 if m[1]=="int" else 2)*int(m[3])-46}))',body)
Path('build/cc1/ga/original.c').write_text(header+prototypes+body)
