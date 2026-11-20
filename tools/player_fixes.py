"""68k-faithful fixes to the selected PC player core (prepare_player.py applies
them to the host and desktop-reference text alike).
  settle: ObjSonic_MoveGround .BalanceGround calls ObjGetFloorDist, whose
          `moveq #$D,d5` leaves 13 in d5 for .Settle (PC uses pladdspdwk).
  drag:   ObjSonic_MoveAir .CheckDrag uses asr.w #5 (floor); PC jumpmove uses /32.
  rwall:  Player_LvlColAir_Right copies the Y velocity into the ground velocity
          after a right-wall hit (scddisasm Sonic/Main.asm:2252-2254, as the
          left-wall case does); PC jumpcolchk case 192 copies the zeroed X
          velocity. Retail TT2B/TT3C traces keep mspeed = yspeed there.
  rollresist: ObjSonic_SlopeResistRoll (Sonic/Main.asm) quarters with asr.l #2
          (floor); PC keispd2 "/= 4" truncates (retail TT1C frame 3440 ground
          speed 1516, PC 1517).
  falloff: ObjSonic_CheckFallOff keeps ground contact at speed $280 (640),
          since the 68k bcc branches on an equal comparison too.
  spindash: Wacky Workbench's own ObjSonic_MoveRoll .Spindash charges by 50
          per update (Level/Wacky Workbench/Objects/Sonic/Main.asm). The shared
          Sonic object (Level/_Objects/Sonic/Main.asm) and the PC balllmove use
          75; retail TT parity matches 75, so only round 6 (stageno 4) uses 50."""
import re
def settle(src):
    # 68k ObjSonic_MoveGround: ObjGetFloorDist's `moveq #$D,d5` leaves d5=13 for .Settle.
    head='void levermove(void) {'
    i=src.index(head); j=src.index('\n',i)
    src=src[:j+1]+'  short settle_d5 = pladdspdwk;\n'+src[j+1:]
    for old,new in [('d1 = emycol_d(&actwk[0]);','d1 = emycol_d(&actwk[0]); settle_d5 = 13;'),
                    ('(actwk[0].mspeed.w -= pladdspdwk) < 0','(actwk[0].mspeed.w -= settle_d5) < 0'),
                    ('(actwk[0].mspeed.w += pladdspdwk) >= 0','(actwk[0].mspeed.w += settle_d5) >= 0')]:
        assert src.count(old)==1,old
        src=src.replace(old,new)
    return src
def drag(src):
    # 68k ObjSonic_MoveAir .CheckDrag: asr.w #5 floors; PC jumpmove's "/ 32" truncates toward zero.
    i=src.index('void jumpmove(void)'); j=src.index('\n}',i)
    body=src[i:j]; assert body.count('cal_speed / 32')==3
    return src[:i]+body.replace('cal_speed / 32','(cal_speed >> 5)')+src[j:]
def rwall(src):
    i=src.index('void jumpcolchk(void)'); i=src.index('case 192:',i); j=src.index('return;',i)
    body=src[i:j]; old='actwk[0].mspeed.w = actwk[0].xspeed.w;'
    assert body.count(old)==1
    return src[:i]+body.replace(old,'actwk[0].mspeed.w = actwk[0].yspeed.w;')+src[j:]
def rollresist(src):
    i=src.index('void keispd2(void)'); j=src.index('\n}',i)
    body=src[i:j]; assert body.count('sin_data /= 4')==2
    return src[:i]+body.replace('sin_data /= 4','sin_data >>= 2')+src[j:]
def falloff(src):
    i=src.index('void fallchk(void)'); j=src.index('\n}',i)
    body=src[i:j]
    old='actwk[0].mspeed.w > 640 || actwk[0].mspeed.w < -640'
    assert body.count(old)==1
    new='actwk[0].mspeed.w >= 640 || actwk[0].mspeed.w <= -640'
    return src[:i]+body.replace(old,new)+src[j:]
def spindash(src):
    i=src.index('void balllmove(void)'); j=src.index('\n}',i)
    body=src[i:j]; old='d0 = 75;'
    assert body.count(old)==1
    return src[:i]+body.replace(old,'d0 = stageno.b.h == 4 ? 50 : 75;')+src[j:]
def skidright(src):
    """ObjSonic_MoveGndRight .Skid (Sonic/Main.asm:1321-1327) loads oAngle into
    d0's low byte only, so cmpi.w #-$400 tests the ground speed's high byte:
    a right-press skid already starts below -768. Retail QQ1A seq 451 faces
    left at -873. Shared Sonic code: every zone."""
    i=src.index('void plwalk_r(void)'); j=src.index('\n}',i)
    body=src[i:j]; old='if (cal_speed > -1024) return;'
    assert body.count(old)==1
    return src[:i]+body.replace(old,'if ((short)(cal_speed & -256) > -1024) return;')+src[j:]
def patch(src):
    return skidright(spindash(falloff(rollresist(rwall(drag(settle(src)))))))
