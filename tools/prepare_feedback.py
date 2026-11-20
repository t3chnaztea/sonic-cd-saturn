#!/usr/bin/env python3
"""Generate prototype UI and copy pinned PCM driver."""
import math,re,struct,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'assets/generated'
# Original 5x7 bitmap glyphs, padded to Saturn's 8-pixel texture width.
patterns={
'0':['01110','10001','10011','10101','11001','10001','01110'],
'1':['00100','01100','00100','00100','00100','00100','01110'],
'2':['01110','10001','00001','00010','00100','01000','11111'],
'3':['11110','00001','00001','01110','00001','00001','11110'],
'4':['00010','00110','01010','10010','11111','00010','00010'],
'5':['11111','10000','10000','11110','00001','00001','11110'],
'6':['01110','10000','10000','11110','10001','10001','01110'],
'7':['11111','00001','00010','00100','01000','01000','01000'],
'8':['01110','10001','10001','01110','10001','10001','01110'],
'9':['01110','10001','10001','01111','00001','00001','01110'],
'A':['01110','10001','10001','11111','10001','10001','10001'],
'B':['11110','10001','10001','11110','10001','10001','11110'],
'C':['01111','10000','10000','10000','10000','10000','01111'],
'D':['11110','10001','10001','10001','10001','10001','11110'],
'E':['11111','10000','10000','11110','10000','10000','11111'],
'F':['11111','10000','10000','11110','10000','10000','10000'],
'G':['01111','10000','10000','10111','10001','10001','01111'],
'H':['10001','10001','10001','11111','10001','10001','10001'],
'I':['01110','00100','00100','00100','00100','00100','01110'],
'J':['00111','00010','00010','00010','00010','10010','01100'],
'K':['10001','10010','10100','11000','10100','10010','10001'],
'L':['10000','10000','10000','10000','10000','10000','11111'],
'M':['10001','11011','10101','10101','10001','10001','10001'],
'N':['10001','11001','11001','10101','10011','10011','10001'],
'O':['01110','10001','10001','10001','10001','10001','01110'],
'P':['11110','10001','10001','11110','10000','10000','10000'],
'Q':['01110','10001','10001','10001','10101','10010','01101'],
'R':['11110','10001','10001','11110','10100','10010','10001'],
'S':['01111','10000','10000','01110','00001','00001','11110'],
'T':['11111','00100','00100','00100','00100','00100','00100'],
'U':['10001','10001','10001','10001','10001','10001','01110'],
'V':['10001','10001','10001','10001','10001','01010','00100'],
'W':['10001','10001','10001','10101','10101','11011','10001'],
'X':['10001','10001','01010','00100','01010','10001','10001'],
'Y':['10001','10001','01010','00100','00100','00100','00100'],
'Z':['11111','00001','00010','00100','01000','10000','11111'],
':':['00000','00100','00100','00000','00100','00100','00000'],
'/':['00001','00001','00010','00100','01000','10000','10000'],
'+':['00000','00100','00100','11111','00100','00100','00000'],
'-':['00000','00000','00000','11111','00000','00000','00000'],
' ':['00000']*7}
font=bytearray()
for code in range(32,91):
    rows=patterns.get(chr(code),patterns[' ']);pixels=[0]*64
    for y,row in enumerate(rows):
        for x,v in enumerate(row):
            if v=='1':pixels[y*8+x]=0xffff
    font+=struct.pack('>64H',*pixels)
(OUT/'hud-font.bin').write_bytes(font)
folder=ROOT/'.deps/examples/scsp-ponesound-pcm8';generated=ROOT/'build/feedback';generated.mkdir(exist_ok=True)
for name in ['ponesound.c','ponesound.h']:shutil.copyfile(folder/name,generated/name)
# Use the driver's own ready handshake; never forge its initialization flag.
p=generated/'ponesound.c'
s=p.read_text().replace('m68k_com->start = 0xFFFF;', '')
s=s.replace('#include <string.h>', '#include <string.h>\n#include "sound_bus.h"\nint ponesound_driver_copy_ok;')
s=s.replace('unsigned short * master_volume = (unsigned short *)', 'volatile unsigned short * master_volume = (volatile unsigned short *)')
s=s.replace('memcpy((void *)SCSP_RAM(loadOffset),pcm_ptr,pcm_size);',
            'scd_sound_copy((volatile uint16_t *)SCSP_RAM(0),loadOffset,pcm_ptr,pcm_size);')
# Sega ST-241 2.1.1 download order: stop the 68000 before sound RAM is written
# (the upstream loader restarted it and then cleared RAM under running code),
# select the memory mode, clear the driver area and the SCSP DSP program left by
# earlier software (upstream driver fix), download, restart.
loader=re.search(r'(void ponesound_load_driver\(uint8_t \* driver_ptr, int driver_size, int master_adx_frequency\)\s*\{).*?(\n\})',s,re.S)
assert loader,'ponesound_load_driver not found'
s=s[:loader.start()]+loader[1]+'''
	smpc_smc_call(SMPC_SMC_SNDOFF);
	*(volatile unsigned short *)(SCSP(0x400)) = 0x0200;
	for(unsigned i = 0; i < 0xC000; i += 2) *(volatile unsigned short *)SCSP_RAM(i) = 0;
	for(unsigned i = 0; i < 0x400; i += 2) *(volatile unsigned short *)SCSP(0x800 + i) = 0;
	ponesound_set_master_volume(0xF);
	scd_sound_copy((volatile uint16_t *)SCSP_RAM(0),0,driver_ptr,driver_size);
	uint32_t hash=2166136261u;
	for(int i=0;i<driver_size;i++)hash=(hash^driver_ptr[i])*16777619u;
	ponesound_driver_copy_ok=scd_sound_hash((volatile uint16_t *)SCSP_RAM(0),driver_size)==hash;
	m68k_com->drv_adx_coef_1 = adx_coef_tbl[master_adx_frequency][0];
	m68k_com->drv_adx_coef_2 = adx_coef_tbl[master_adx_frequency][1];
	smpc_smc_call(SMPC_SMC_SNDON);'''+loader[2]+s[loader.end():]
p.write_text(s)
p=generated/'ponesound.h'
p.write_text(p.read_text().replace('volatile _PCM_CTRL * pcmCtrl;', 'volatile _PCM_CTRL * volatile pcmCtrl;'))
shutil.copyfile(folder/'assets/sdrv.bin' ,OUT/'sound-driver.bin')
print('HUD font:',len(font),'bytes; pinned Ponesound driver copied')
