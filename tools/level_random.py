"""C text of the 68k Level Random (scddisasm Level/Functions (General).asm:14-33).

The retail game advances its seed with plain asl.l shifts and moves d1.w into
d0.w; the PC IO.C random keeps sign bits on its shifts and adds instead, so its
seed chain differs (retail TT parity, TIDAL-TEMPEST-PLAN.md). Compiled-original
fixtures use this in place of IO.C random, as src/ does."""


def level_random(name='random'):
    return f'''int {name}(void) {{
  unsigned int d1 = ranum ? (unsigned int)ranum : 0x2A6D365Au, d0 = d1;
  d1 <<= 2; d1 += d0; d1 <<= 3; d1 += d0;
  d0 = (d0 & 0xffff0000u) | (d1 & 0xffffu);
  d1 = d1 << 16 | d1 >> 16;
  d0 = (d0 & 0xffff0000u) | ((d0 + d1) & 0xffffu);
  d1 = (d1 & 0xffff0000u) | (d0 & 0xffffu);
  d1 = d1 << 16 | d1 >> 16;
  ranum = (int)d1;
  return (int)d0;
}}
'''
