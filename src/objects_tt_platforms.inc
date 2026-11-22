/* Tidal Tempest platforms, blocks, switches and doors: R4/UDBLK4.C, LRBLK4.C,
   RBLK4.C, ESCAL4.C, BRUNKO4.C, RENKETU4.C, KUZURE4.C, DAID4.C, BANEIWA.C,
   SW4.C, SWBLK4.C (swblkr4/switchr4), SWGUN4.C (swgun4/ring4/tensu4),
   TOBIRA4.C, TOBIRAS4.C, WALLS.C, WALL42.C, TEKKYU.C, TEKKYU4.C, TEKKYU1.C.
   Statement-for-statement ports of the PC reconstruction: routine order,
   scratch offsets (objects_tt_ride.inc byte helpers), child allocation and
   RIDECHK.C calls follow the originals. Sprite pattern tables are not
   ported; views use patno. tools/test-tt-platforms.sh compares every actor
   with the compiled originals. Included after objects_tt_ride.inc. */
static void udblk4_act(sprite_status* pActwk);
static void udblk4_sin_move(sprite_status* pActwk, short d2, short d3);
static void udblk4_type1(sprite_status* pActwk);
static void udblk4_type1_init(sprite_status* pActwk);
static void udblk4_type1_move(sprite_status* pActwk);
static void udblk4_type2(sprite_status* pActwk);
static void udblk4_type3(sprite_status* pActwk);
static void udblk4_type3_init(sprite_status* pActwk);
static void udblk4_type3_move(sprite_status* pActwk);
static void udblk4_type4(sprite_status* pActwk);
static void udblk4_type4_coset(sprite_status* pActwk, sprite_status* pNewActwk, unsigned char d0, short d1);
static void udblk4_type4_init(sprite_status* pActwk);
static void udblk4_type4_move(sprite_status* pActwk);
static void udblk4_type5(sprite_status* pActwk);
static void udblk4_type5_coset(sprite_status* pActwk, sprite_status* pNewActwk, unsigned char d0, short d1, unsigned char d2, short d3);
static void udblk4_type5_init(sprite_status* pActwk);
static void udblk4_type5_move(sprite_status* pActwk);
static void udblk4_type6(sprite_status* pActwk);
static void udblk4_type6_init(sprite_status* pActwk);
static void udblk4_type6_move(sprite_status* pActwk);
static void udblk4_type7(sprite_status* pActwk);
static void udblk4_type7_coset(sprite_status* pActwk, sprite_status* pNewActwk, unsigned char d0, short d1, unsigned char d2);
static void udblk4_type7_init(sprite_status* pActwk);
static void udblk4_type7_move(sprite_status* pActwk);
static void udblk4_type8(sprite_status* pActwk);
static void udblk4_type8_init(sprite_status* pActwk);
static void udblk4_type8_move(sprite_status* pActwk);
static void udblk4_type9(sprite_status* pActwk);
static void udblk4_type9_init(sprite_status* pActwk);
static void udblk4_type9_move(sprite_status* pActwk);
static void udblk4_typeA(sprite_status* pActwk);
static void udblk4_typeA_init(sprite_status* pActwk);
static void udblk4_typeA_move(sprite_status* pActwk);
static void udblk4_typeB(sprite_status* pActwk);
static void udblk4_typeB_init(sprite_status* pActwk);
static void udblk4_typeB_move(sprite_status* pActwk);
static void lrblk4_act(sprite_status* pActwk);
static void lrblk4_foutchk(sprite_status* pActwk);
static void lrblk4_type1(sprite_status* pActwk);
static void lrblk4_type1_init(sprite_status* pActwk);
static void lrblk4_type1_move(sprite_status* pActwk);
static void lrblk4_type2(sprite_status* pActwk);
static void lrblk4_type2_init(sprite_status* pActwk);
static void lrblk4_type2_move(sprite_status* pActwk);
static void lrblk4_type3(sprite_status* pActwk);
static void lrblk4_type3_init(sprite_status* pActwk);
static void lrblk4_type3_move(sprite_status* pActwk);
static void lrblk4_type4(sprite_status* pActwk);
static void lrblk4_type4_init(sprite_status* pActwk);
static void lrblk4_type4_move(sprite_status* pActwk);
static void lrblk4_type5(sprite_status* pActwk);
static void lrblk4_type5_init(sprite_status* pActwk);
static void lrblk4_type5_move(sprite_status* pActwk);
static void lrblk4_type5_end(sprite_status* pActwk);
static void lrblk4_type6(sprite_status* pActwk);
static void lrblk4_type6_init(sprite_status* pActwk);
static void lrblk4_type6_move(sprite_status* pActwk);
static void lrblk4_type8(sprite_status* pActwk);
static void lrblk4_type8_init(sprite_status* pActwk);
static void lrblk4_type8_move(sprite_status* pActwk);
static void rblk4_act(sprite_status* pActwk);
static void rblk4_init(sprite_status* pActwk);
static void rblk4_wait(sprite_status* pActwk);
static void rblk4_move(sprite_status* pActwk);
static void rblk4_push(sprite_status* pActwk);
static void rblk4_ract(sprite_status* pActwk);
static void rblk4_ract_init(sprite_status* pActwk);
static void rblk4_ract_move(sprite_status* pActwk);
static void escal4_act(sprite_status* pActwk);
static short escal4_ridechk(sprite_status* pActwk);
static void escal4_init(sprite_status* pActwk);
static void escal4_wait(sprite_status* pActwk);
static void escal4_moveup(sprite_status* pActwk);
static void brunko4_act(sprite_status* pActwk);
static void brunko4_ridechk(sprite_status* pActwk);
static void brunko4_brunko_init(sprite_status* pActwk);
static void brunko4_brunko_move(sprite_status* pActwk);
static void brunko4_posiset(sprite_status* pActwk);
static void renketu4_act(sprite_status* pActwk);
static void renketu4_ridechk(sprite_status* pActwk);
static void renketu4_init(sprite_status* pActwk);
static void renketu4_move(sprite_status* pActwk);
static void renketu4_swchk(sprite_status* pActwk);
static void kuzure4_act(sprite_status* pActwk);
static void kuzure4_main_ini(sprite_status* pActwk);
static void kuzure4_main_check(sprite_status* pActwk);
static void kuzure4_main_wait(sprite_status* pActwk);
static void kuzure4_main_break(sprite_status* pActwk);
static void kuzure4_parts(sprite_status* pActwk);
static void kuzure4_parts_ini(sprite_status* pActwk);
static void kuzure4_parts_wait(sprite_status* pActwk);
static void kuzure4_parts_fall(sprite_status* pActwk);
static void daid4_act(sprite_status* pActwk);
static void daid4_a_ini(sprite_status* pActwk);
static void daid4_a_born(sprite_status* pActwk);
static void daid4_a_off(sprite_status* pActwk);
static void daid4_a_off1(sprite_status* pActwk);
static void daid4_a_on(sprite_status* pActwk);
static void daid4_a_on1(sprite_status* pActwk);
static void baneiwa_act(sprite_status* pActwk);
static void baneiwa_init(sprite_status* pActwk);
static void baneiwa_move(sprite_status* pActwk);
static void sw4_act(sprite_status* pActwk);
static void sw4_act_init(sprite_status* pActwk);
static void sw4_act_move(sprite_status* pActwk);
static short sw4_hosei(sprite_status* pActwk, sprite_status* pActwk2);
static void swblk4_switchr4(sprite_status* pActwk);
static void swblk4_switchr4_init(sprite_status* pActwk);
static void swblk4_switchr4_move(sprite_status* pActwk);
static unsigned int swblk4_switchr4_colichk(sprite_status* pActwk, sprite_status* pPlayerwk);
static void swblk4_swblkr4(sprite_status* pActwk);
static void swblk4_swblkr4_init(sprite_status* pActwk);
static void swblk4_swblkr4_move(sprite_status* pActwk);
static void swgun4_act(sprite_status* pActwk);
static void swgun4_init(sprite_status* pActwk);
static void swgun4_move(sprite_status* pActwk);
static void swgun4_move1(sprite_status* pActwk);
static void swgun4_switch_move(sprite_status* pActwk);
static void swgun4_hariset(sprite_status* pActwk);
static void swgun4_awaset(sprite_status* pActwk);
static void swgun4_ring4set(sprite_status* pActwk);
static void swgun4_bp1000(sprite_status* pActwk);
static void swgun4_ring4(sprite_status* pActwk);
static void swgun4_ring4_init(sprite_status* pActwk);
static void swgun4_ring4_move(sprite_status* pActwk);
static void swgun4_ring4_get(sprite_status* pActwk);
static void swgun4_ring4_die(sprite_status* pActwk);
static void swgun4_ring4_erase(sprite_status* pActwk);
static void swgun4_tensu4(sprite_status* pActwk);
static void swgun4_tensu4_init(sprite_status* pActwk);
static void swgun4_tensu4_move(sprite_status* pActwk);
static void tobira4_act(sprite_status* pActwk);
static void tobira4_init(sprite_status* pActwk);
static void tobira4_move(sprite_status* pActwk);
static void tobira4_cl_type1(sprite_status* pActwk);
static void tobira4_cl_type2(sprite_status* pActwk);
static void tobira4_chek(sprite_status* pActwk);
static void tobira4_clse(sprite_status* pActwk);
static void tobira4_type1(sprite_status* pActwk);
static void tobira4_type2(sprite_status* pActwk);
static void tobira4_type3(sprite_status* pActwk);
static void tobira4_type4(sprite_status* pActwk);
static void tobira4_cnt(sprite_status* pActwk);
static void tobira4_sub(sprite_status* pActwk);
static void tobiras4_act(sprite_status* pActwk);
static void tobiras4_act_init(sprite_status* pActwk);
static void tobiras4_act_sense(sprite_status* pActwk);
static void tobiras4_act_down(sprite_status* pActwk);
static void tobiras4_act_disp(sprite_status* pActwk);
static void walls_act(sprite_status* pActwk);
static void walls_main_init(sprite_status* pActwk);
static void walls_main_move(sprite_status* pActwk);
static void walls_opt_check(sprite_status* pActwk);
static void wall42_act(sprite_status* pActwk);
static void wall42_act_init(sprite_status* pActwk);
static void wall42_act_wait(sprite_status* pActwk);
static void wall42_act_move(sprite_status* pActwk);
static void wall42_act_stop(sprite_status* pActwk);
static void tekkyu_act(sprite_status* pActwk);
static void tekkyu_main(sprite_status* pActwk);
static void tekkyu_act_init(sprite_status* pActwk);
static void tekkyu_act_move(sprite_status* pActwk);
static void tekkyu_opt(sprite_status* pActwk);
static void tekkyu_opt_act_init(sprite_status* pActwk);
static void tekkyu_opt_act_move(sprite_status* pActwk);
static void tekkyu4_act(sprite_status* pActwk);
static void tekkyu4init(sprite_status* pActwk);
static void tekkyu4_act_init_sub(sprite_status* pActwk, sprite_status* pNewactwk);
static void tekkyu4move(sprite_status* pActwk);
static void tekkyu1_act(sprite_status* pActwk);

/* ---- R4/UDBLK4.C ---- */
typedef struct {
  unsigned char kakudo;
  char xofst;
}
udblk4_kakudo_xofst;
typedef struct {
  char xofs;
  char yofs;
  short yspd;
}
udblk4_xofs_yofs_yspd;
static void udblk4_act(sprite_status* pActwk) {
  static void(*const tbl[12])(sprite_status*) =
  {
    &udblk4_type1,
    &udblk4_type1,
    &udblk4_type2,
    &udblk4_type3,
    &udblk4_type4,
    &udblk4_type5,
    &udblk4_type6,
    &udblk4_type7,
    &udblk4_type8,
    &udblk4_type9,
    &udblk4_typeA,
    &udblk4_typeB
  };
  tbl[pActwk->userflag.b.h](pActwk);
}
static void udblk4_sin_move(sprite_status* pActwk, short d2, short d3) {
  int_union ld0;
  int stk;
  short d0, d1;
  if (pActwk->yspeed.w < 0)
  {
    tp_ride_on_chk(pActwk, &actwk[0]);
  }
  stk = pActwk->yposi.l;
  sinset(pActwk->actfree[16], &d0, &d1);
  d1 = d0;
  d0 <<= d2;
  d1 <<= d3;
  d0 += d1;
  d0 >>= 8;
  ++pActwk->actfree[16];
  d0 += tp_w(pActwk,8);
  pActwk->yposi.w.h = d0;
  ld0.w.h = d0;
  ld0.w.l = 0;
  ld0.l -= stk;
  ld0.l >>= 8;
  pActwk->yspeed.w = ld0.w.l;
  if (pActwk->yspeed.w >= 0)
  {
    tp_ride_on_chk(pActwk, &actwk[0]);
  }
}
static void udblk4_type1(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type1_init,
    &udblk4_type1_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void udblk4_type1_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short i;
  unsigned char d0, d1;
  static udblk4_kakudo_xofst tbl[7] =
  {
    { 192,   0 },
    { 168, -32 },
    { 144, -64 },
    { 120, -96 },
    { 216,  32 },
    { 240,  64 },
    {   8,  96 }
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->yposi.w.h + 64);
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 64;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    d1 = 1;
    for (i = 0; i <= 5; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
        pNewActwk->userflag.b.h = 1;
        pNewActwk->xposi.w.h = pActwk->xposi.w.h;
        pNewActwk->yposi.w.h = pActwk->yposi.w.h;
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        pNewActwk->actfree[18] = d1;
      }
      ++d1;
    }
  }
  d0 = pActwk->actfree[18];
  pActwk->actfree[16] = tbl[d0].kakudo;
  pActwk->xposi.w.h += tbl[d0].xofst;
  udblk4_type1_move(pActwk);
}
static void udblk4_type1_move(sprite_status* pActwk) {
  udblk4_sin_move(pActwk, 6, 0);
}
static void udblk4_type2(sprite_status* pActwk) {
}
static void udblk4_type3(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type3_init,
    &udblk4_type3_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void udblk4_type3_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  tp_wset(pActwk,8,pActwk->yposi.w.h - 80);
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 96;
  pActwk->actfree[16] = 64;
  udblk4_type3_move(pActwk);
}
static void udblk4_type3_move(sprite_status* pActwk) {
  udblk4_sin_move(pActwk, 6, 4);
}
static void udblk4_type4(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type4_init,
    &udblk4_type4_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void udblk4_type4_coset(sprite_status* pActwk, sprite_status* pNewActwk, unsigned char d0, short d1) {
  tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
  pNewActwk->userflag.b.h = 4;
  pNewActwk->actfree[18] = d0;
  pNewActwk->yposi.w.h = pActwk->yposi.w.h;
  pNewActwk->xposi.w.h = pActwk->xposi.w.h + d1;
  tp_wset(pNewActwk,12,tp_w(pActwk,12));
}
static void udblk4_type4_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->yposi.w.h + 48);
  pActwk->sprhsize = 18;
  pActwk->sprvsize = 48;
  pActwk->actfree[16] = 192;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
  }
  if (tp_actwkchk(&pNewActwk) == 0)
  {
    tp_setactno(pNewActwk,SCD_OBJ_HARIR4);
    pNewActwk->xposi.w.h = pActwk->xposi.w.h;
    pNewActwk->yposi.w.h = pActwk->yposi.w.h;
    tp_wset(pNewActwk,12,tp_w(pActwk,12));
    tp_wset(pNewActwk,10,(unsigned short)(pActwk - actwk));
    pNewActwk->actfree[15] = 64;
    pNewActwk->userflag.b.h = 1;
  }
  if (pActwk->actfree[18] == 0)
  {
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type4_coset(pActwk, pNewActwk, 1, -80);
    }
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type4_coset(pActwk, pNewActwk, 2, 80);
    }
  }
  udblk4_type4_move(pActwk);
}
static void udblk4_type4_move(sprite_status* pActwk) {
  short stk;
  short d0, d1;
  stk = pActwk->yposi.w.h;
  sinset(pActwk->actfree[16], &d0, &d1);
  d0 *= 3;
  d0 >>= 4;
  d0 += tp_w(pActwk,8);
  pActwk->yposi.w.h = d0;
  ++pActwk->actfree[16];
  d1 = stk;
  d0 -= d1;
  d0 <<= 8;
  pActwk->yspeed.w = d0;
  d1 = tp_w(pActwk,10);
  if (d1)
  {
    actwk[d1].yspeed.w = d0;
  }
  tp_ride_on_chk(pActwk, &actwk[0]);
}
static void udblk4_type5(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type5_init,
    &udblk4_type5_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void udblk4_type5_coset(sprite_status* pActwk, sprite_status* pNewActwk, unsigned char d0, short d1, unsigned char d2, short d3) {
  tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
  pNewActwk->userflag.b.h = 5;
  pNewActwk->actfree[18] = d0;
  pNewActwk->actfree[16] = d2;
  pNewActwk->xposi.w.h = pActwk->xposi.w.h + d1;
  pNewActwk->yposi.w.h = pActwk->yposi.w.h + d3;
  tp_wset(pNewActwk,12,tp_w(pActwk,12));
}
static void udblk4_type5_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->yposi.w.h + 64);
  pActwk->sprhsize = 20;
  pActwk->sprvsize = 65;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    pActwk->actfree[16] = 0;
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type5_coset(pActwk, pNewActwk, 1, 32, 240, -32);
    }
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type5_coset(pActwk, pNewActwk, 1, 64, 224, -64);
    }
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type5_coset(pActwk, pNewActwk, 1, 96, 208, -96);
    }
  }
  udblk4_type5_move(pActwk);
}
static void udblk4_type5_move(sprite_status* pActwk) {
  udblk4_sin_move(pActwk, 6, 0);
}
static void udblk4_type6(sprite_status* pActwk) {
  if (pActwk->r_no0) udblk4_type6_move(pActwk);
  else udblk4_type6_init(pActwk);
}
static void udblk4_type6_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short i, d1;
  static udblk4_kakudo_xofst tbl[7] =
  {
    {   0,   0 },
    {  32, -32 },
    {  64, -64 },
    {  96, -96 },
    {  32,  32 },
    {  64,  64 },
    {  96,  96 }
  };
  pActwk->r_no0 += 2;
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  d1 = 0;
  for (i = 0; i <= 6; ++i)
  {
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
      pNewActwk->userflag.b.h = 9;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h;
      tp_wset(pNewActwk,10,(unsigned short)(pActwk - actwk));
      pNewActwk->actfree[19] = 255;
      pNewActwk->actfree[16] = tbl[d1].kakudo;
      pNewActwk->xposi.w.h = pActwk->xposi.w.h + (short)tbl[d1].xofst;
    }
    ++d1;
  }
  udblk4_type6_move(pActwk);
}
static void udblk4_type6_move(sprite_status* pActwk) {
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void udblk4_type7(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type7_init,
    &udblk4_type7_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void udblk4_type7_coset(sprite_status* pActwk, sprite_status* pNewActwk, unsigned char d0, short d1, unsigned char d2) {
  tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
  pNewActwk->userflag.b.h = 7;
  pNewActwk->actfree[18] = d0;
  pNewActwk->actfree[16] = d2;
  pNewActwk->yposi.w.h = pActwk->yposi.w.h;
  pNewActwk->xposi.w.h = pActwk->xposi.w.h + d1;
  tp_wset(pNewActwk,12,tp_w(pActwk,12));
}
static void udblk4_type7_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->yposi.w.h + 64);
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 64;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h + 48);
    pActwk->actfree[16] = 192;
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type7_coset(pActwk, pNewActwk, 1, 32, 224);
    }
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type7_coset(pActwk, pNewActwk, 1, 64, 0);
    }
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      udblk4_type7_coset(pActwk, pNewActwk, 1, 96, 32);
    }
  }
  udblk4_type7_move(pActwk);
}
static void udblk4_type7_move(sprite_status* pActwk) {
  udblk4_sin_move(pActwk, 6, 0);
}
static void udblk4_type8(sprite_status* pActwk) {
  short d0;
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type8_init,
    &udblk4_type8_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  d0 = tp_w(pActwk,10);
  if (d0)
  {
    if (actwk[d0].actno != SCD_OBJ_UDBLK4)
    {
      tp_frameout_s0(pActwk);
    }
  }
  else
  {
    tp_frameout_s00(pActwk, tp_w(pActwk,12));
  }
}
static void udblk4_type8_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short i;
  short d0;
  unsigned char d1;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->yposi.w.h - 32);
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 48;
  if (pActwk->actfree[19] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
  }
  if (pActwk->actfree[18] == 0)
  {
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
      pNewActwk->actfree[18] = 1;
      pNewActwk->userflag.b.h = 8;
      pNewActwk->xposi.w.h = pActwk->xposi.w.h;
      tp_wset(pNewActwk,12,tp_w(pActwk,12));
      pNewActwk->yposi.w.h = pActwk->yposi.w.h + 160;
      pNewActwk->actfree[16] = pActwk->actfree[16];
      pNewActwk->actfree[19] = pActwk->actfree[19];
      if (pActwk->actfree[19] == 0)
      {
        d1 = 1;
        for (i = 0; i <= 1; ++i)
        {
          if (tp_actwkchk(&pNewActwk) == 0)
          {
            tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
            pNewActwk->userflag.b.h = 8;
            pNewActwk->actfree[19] = d1;
            pNewActwk->actfree[16] = 128;
            d0 = -64;
            if (d1 != 1) d0 *= -1;
            pNewActwk->xposi.w.h = pActwk->xposi.w.h + d0;
            pNewActwk->yposi.w.h = pActwk->yposi.w.h;
            tp_wset(pNewActwk,12,tp_w(pActwk,12));
          }
          ++d1;
        }
      }
    }
  }
  udblk4_type8_move(pActwk);
}
static void udblk4_type8_move(sprite_status* pActwk) {
  short_union tmp;
  short stk;
  short d0, d1;
  stk = pActwk->yposi.w.h;
  sinset(pActwk->actfree[16], &d0, &d1);
  d0 = d0 * 2 >> 4;
  tmp.b.h = pActwk->actfree[16];
  tmp.b.l = pActwk->actfree[17];
  tmp.w += 128;
  pActwk->actfree[16] = tmp.b.h;
  pActwk->actfree[17] = tmp.b.l;
  pActwk->yposi.w.h = tp_w(pActwk,8) + d0;
  d0 -= stk;
  d0 <<= 8;
  pActwk->yspeed.w = d0;
  tp_ride_on_chk(pActwk, &actwk[0]);
}
static void udblk4_type9(sprite_status* pActwk) {
  short d0;
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_type9_init,
    &udblk4_type9_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  d0 = tp_w(pActwk,10);
  if (d0)
  {
    if (actwk[d0].actno == 0)
    {
      tp_frameout_s0(pActwk);
    }
  }
  else
  {
    tp_frameout_s00(pActwk, tp_w(pActwk,12));
  }
}
static void udblk4_type9_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short d1;
  unsigned char d0;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  tp_wset(pActwk,8,pActwk->yposi.w.h);
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 32;
  if (pActwk->actfree[18] == 0)
  {
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
      pNewActwk->actfree[18] = 1;
      pNewActwk->userflag.b.h = 9;
      pNewActwk->xposi.w.h = pActwk->xposi.w.h;
      d1 = 128;
      d0 = pActwk->actfree[16];
      if (pActwk->actfree[19] & 128)
      {
        d1 = 160;
        d0 -= 128;
      }
      pNewActwk->actfree[16] = d0;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h + d1;
    }
  }
}
static void udblk4_type9_move(sprite_status* pActwk) {
  udblk4_sin_move(pActwk, 5, 0);
}
static void udblk4_typeA(sprite_status* pActwk) {
  short d0;
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_typeA_init,
    &udblk4_typeA_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  d0 = tp_w(pActwk,10);
  if (d0)
  {
    if (actwk[d0].actno == 0)
    {
      tp_frameout_s0(pActwk);
    }
  }
  else
  {
    tp_frameout_s00(pActwk, tp_w(pActwk,12));
  }
}
static void udblk4_typeA_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short i;
  unsigned char d1;
  static udblk4_kakudo_xofst tbl[7] =
  {
    {   0,   0 },
    { 224, -32 },
    { 192, -64 },
    { 160, -96 },
    { 224,  32 },
    { 192,  64 },
    { 160,  96 }
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->yposi.w.h);
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 16;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    d1 = 1;
    for (i = 0; i <= 5; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
        pNewActwk->userflag.b.h = 10;
        pNewActwk->yposi.w.h = pActwk->yposi.w.h;
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        pNewActwk->actfree[18] = d1;
        pNewActwk->actfree[16] = tbl[d1].kakudo;
        pNewActwk->xposi.w.h = pActwk->xposi.w.h + (short)tbl[d1].xofst;
      }
      ++d1;
    }
  }
  udblk4_typeA_move(pActwk);
}
static void udblk4_typeA_move(sprite_status* pActwk) {
  udblk4_sin_move(pActwk, 5, 4);
}
static void udblk4_typeB(sprite_status* pActwk) {
  short d0;
  static void(*const tbl[2])(sprite_status*) =
  {
    &udblk4_typeB_init,
    &udblk4_typeB_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  d0 = tp_w(pActwk,10);
  if (d0)
  {
    if (actwk[d0].actno == 0)
    {
      tp_frameout_s0(pActwk);
    }
  }
  else
  {
    tp_frameout_s00(pActwk, tp_w(pActwk,12));
  }
}
static void udblk4_typeB_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  udblk4_xofs_yofs_yspd* a1;
  short i;
  unsigned char d1;
  static udblk4_xofs_yofs_yspd tbl[6] =
  {
    {    0,    0,  128 },
    {    0, -128,  128 },
    {  -80,   32, -256 },
    {  -80,  -96, -256 },
    {   80,   32, -256 },
    {   80,  -96, -256 }
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 32;
  pActwk->patno = 0;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    tp_wset(pActwk,8,pActwk->yposi.w.h);
    d1 = 1;
    for (i = 0; i <= 4; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_UDBLK4);
        pNewActwk->userflag.b.h = 11;
        pNewActwk->actfree[18] = d1;
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        tp_wset(pNewActwk,8,tp_w(pActwk,8));
      }
      ++d1;
    }
  }
  a1 = &tbl[pActwk->actfree[18]];
  pActwk->xposi.w.h = tp_w(pActwk,12) + (short)a1->xofs;
  pActwk->yposi.w.h = tp_w(pActwk,8) + (short)a1->yofs;
  pActwk->yspeed.w += a1->yspd;
}
static void udblk4_typeB_move(sprite_status* pActwk) {
  short d0;
  pActwk->yposi.l = pActwk->yposi.l + (pActwk->yspeed.w << 8);
  if (pActwk->yspeed.w < 0)
  {
    d0 = tp_w(pActwk,8);
    if (d0 < pActwk->yposi.w.h) return;
    d0 -= pActwk->yposi.w.h;
    if (d0 < 128) return;
    pActwk->yposi.w.h = tp_w(pActwk,8) + 128;
  }
  else
  {
    d0 = pActwk->xposi.w.h;
    if (d0 < tp_w(pActwk,8)) return;
    d0 -= tp_w(pActwk,8);
    if (d0 < 128) return;
    pActwk->yposi.w.h = tp_w(pActwk,8) - 128;
  }
}

/* ---- R4/LRBLK4.C ---- */
typedef struct {
  unsigned char cnt;
  unsigned char dummy;
  short speed;
}
lrblk4_move_data;
static void lrblk4_act(sprite_status* pActwk) {
  static void(*const tbl[9])(sprite_status*) =
  {
    &lrblk4_type1,
    &lrblk4_type1,
    &lrblk4_type2,
    &lrblk4_type3,
    &lrblk4_type4,
    &lrblk4_type5,
    &lrblk4_type6,
    &lrblk4_type1,
    &lrblk4_type8
  };
  tbl[pActwk->userflag.b.h](pActwk);
}
static void lrblk4_foutchk(sprite_status* pActwk) {
  short d0, d1;
  d0 = tp_w(pActwk,12);
  d0 &= -128;
  d1 = tp_scra_h();
  d1 -= 128;
  d1 &= -128;
  d0 -= d1;
  if ((unsigned short)d0 > 640)
  {
    tp_frameout_s0(pActwk); /* respawn bit cleared: reloads */
  }
}
static void lrblk4_type1(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &lrblk4_type1_init,
    &lrblk4_type1_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type1_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short i;
  unsigned short d0;
  unsigned char d1;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,8,pActwk->xposi.w.h);
  pActwk->sprhsize = 48;
  pActwk->sprvsize = 16;
  pActwk->patno = 1;
  if (pActwk->actfree[18])
  {
    lrblk4_type1_move(pActwk);
    return;
  }
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  if (pActwk->actfree[19] == 0)
  {
    d1 = 1;
    for (i = 0; i <= 4; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
        pNewActwk->userflag.b.h = 1;
        pNewActwk->actfree[19] = d1;
        pNewActwk->xposi.w.h = pActwk->xposi.w.h;
        pNewActwk->actfree[16] = (char)(d1 * 32) + 16;
        d0 = d1;
        d0 *= 96;
        d0 += pActwk->yposi.w.h;
        pNewActwk->yposi.w.h = d0;
      }
      ++d1;
    }
  }
  if (tp_actwkchk(&pNewActwk) == 0)
  {
    tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
    pNewActwk->userflag.b.h = 1;
    pNewActwk->actfree[18] = 1;
    tp_wset(pNewActwk,12,tp_w(pActwk,12));
    pNewActwk->yposi.w.h = pActwk->yposi.w.h;
    pNewActwk->xposi.w.h = pActwk->xposi.w.h + 224;
    pNewActwk->actfree[16] = pActwk->actfree[16];
  }
  lrblk4_type1_move(pActwk);
}
static void lrblk4_type1_move(sprite_status* pActwk) {
  short d0, d1, stk;
  stk = pActwk->xposi.w.h;
  sinset(pActwk->actfree[16], &d0, &d1);
  d0 >>= 3;
  ++pActwk->actfree[16];
  d0 += tp_w(pActwk,8);
  pActwk->xposi.w.h = d0;
  d1 = stk;
  d0 -= d1;
  d0 <<= 8;
  pActwk->xspeed.w = d0;
  tp_hitchk(pActwk, &actwk[0]);
}
static void lrblk4_type2(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &lrblk4_type2_init,
    &lrblk4_type2_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type2_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 16;
  if (pActwk->actfree[18])
  {
    lrblk4_type2_move(pActwk);
    return;
  }
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  tp_wset(pActwk,8,pActwk->xposi.w.h - 32);
  if (tp_actwkchk(&pNewActwk) == 0)
  {
    tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
    pNewActwk->userflag.b.h = 2;
    pNewActwk->actfree[18] = 1;
    tp_wset(pNewActwk,12,tp_w(pActwk,12));
    pNewActwk->yposi.w.h = pActwk->yposi.w.h;
    pNewActwk->xposi.w.h = pActwk->xposi.w.h + 64;
    tp_wset(pNewActwk,8,pNewActwk->xposi.w.h + 32);
    pNewActwk->actfree[16] = pActwk->actfree[16] - 128;
  }
  lrblk4_type2_move(pActwk);
}
static void lrblk4_type2_move(sprite_status* pActwk) {
  short d0, d1, stk;
  stk = pActwk->xposi.w.h;
  sinset(pActwk->actfree[16], &d0, &d1);
  d0 >>= 3;
  ++pActwk->actfree[16];
  d0 += tp_w(pActwk,8);
  pActwk->xposi.w.h = d0;
  d1 = stk;
  d0 -= d1;
  d0 <<= 8;
  pActwk->xspeed.w = d0;
  tp_hitchk(pActwk, &actwk[0]);
}
static void lrblk4_type3(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &lrblk4_type3_init,
    &lrblk4_type3_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type3_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short* a2;
  short i;
  unsigned char d0, d1;
  static short tbl[18] =
  {
       0,    0, -128,
    -144,    0, -128,
     144,    0, -128,
       0,   64,  128,
    -144,   64,  128,
     144,   64,  128
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 32;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    d1 = 1;
    for (i = 0; i <= 4; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
        pNewActwk->userflag.b.h = 3;
        pNewActwk->actfree[18] = d1;
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        pNewActwk->xposi.w.h = pActwk->xposi.w.h;
        pNewActwk->yposi.w.h = pActwk->yposi.w.h;
      }
      ++d1;
    }
  }
  d0 = pActwk->actfree[18] * 6;
  a2 = &tbl[d0 / 2];
  pActwk->xposi.w.h += *a2++;
  pActwk->yposi.w.h += *a2++;
  pActwk->xspeed.w = *a2++;
}
static void lrblk4_type3_move(sprite_status* pActwk) {
  sprite_status* pPlayerwk;
  int ld0;
  short d0;
  ld0 = pActwk->xspeed.w;
  ld0 <<= 8;
  pActwk->xposi.l += ld0;
  if (pActwk->xspeed.w < 0)
  {
    d0 = tp_w(pActwk,12);
    if ((unsigned short)d0 >= (unsigned short)pActwk->xposi.w.h)
    {
      d0 -= pActwk->xposi.w.h;
      if ((unsigned short)d0 >= 224)
      {
        d0 = tp_w(pActwk,12);
        d0 += 224;
        pActwk->xposi.w.h = d0;
      }
    }
  }
  else
  {
    d0 = pActwk->xposi.w.h;
    if ((unsigned short)d0 >= (unsigned short)tp_w(pActwk,12))
    {
      d0 -= tp_w(pActwk,12);
      if ((unsigned short)d0 >= 224)
      {
        d0 = tp_w(pActwk,12);
        d0 -= 224;
        pActwk->xposi.w.h = d0;
      }
    }
  }
  if (pActwk->actflg & 128)
  {
    pPlayerwk = &actwk[0];
    d0 = pPlayerwk->yposi.w.h;
    if ((unsigned short)d0 < (unsigned short)pActwk->yposi.w.h)
    {
      d0 -= pActwk->yposi.w.h;
      d0 *= -1;
    }
    else
    {
      d0 -= pActwk->yposi.w.h;
    }
    if ((unsigned short)d0 < 64)
    {
      tp_hitchk(pActwk, pPlayerwk);
    }
  }
}
static void lrblk4_type4(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &lrblk4_type4_init,
    &lrblk4_type4_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type4_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 64;
  pActwk->sprvsize = 64;
  if (pActwk->actfree[19])
  {
    pActwk->sprvsize = 16;
  }
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
      pNewActwk->userflag.b.h = 4;
      pNewActwk->actfree[18] = 1;
      pNewActwk->actfree[19] = pActwk->actfree[19];
      tp_wset(pNewActwk,12,tp_w(pActwk,12));
      pNewActwk->xposi.w.h = tp_w(pActwk,12) + 128;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h;
      pActwk->xposi.w.h = tp_w(pActwk,12) - 128;
    }
  }
  pActwk->xspeed.w = -512;
}
static void lrblk4_type4_move(sprite_status* pActwk) {
  short d0;
  pActwk->xposi.l += pActwk->xspeed.w << 8;
  tp_hitchk(pActwk, &actwk[0]);
  d0 = tp_w(pActwk,12);
  if (d0 >= pActwk->xposi.w.h)
  {
    d0 -= pActwk->xposi.w.h;
    if (d0 == 256)
    {
      pActwk->xposi.w.h = tp_w(pActwk,12) + 256;
    }
  }
}
static void lrblk4_type5(sprite_status* pActwk) {
  static void(*const tbl[3])(sprite_status*) =
  {
    &lrblk4_type5_init,
    &lrblk4_type5_move,
    &lrblk4_type5_end
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type5_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  unsigned char* a1;
  short i;
  unsigned short d0;
  unsigned char d1;
  static unsigned char tbl[14] =
  {
      0,   0,
     64,   1,
    128,   2,
    192,   3,
    128,   4,
     64,   5,
      0,   0
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 32;
  if (pActwk->actfree[18] == 0)
  {
    d1 = 1;
    for (i = 0; i <= 3; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
        pNewActwk->userflag.b.h = 5;
        pNewActwk->actfree[18] = d1;
        pNewActwk->xposi.w.h = pActwk->xposi.w.h;
        d0 = d1;
        d0 *= 64;
        pNewActwk->yposi.w.h = pActwk->yposi.w.h + (short)d0;
      }
      ++d1;
    }
  }
  a1 = &tbl[pActwk->actfree[18] * 2];
  pActwk->xposi.w.h += (unsigned short)*a1++;
  pActwk->actfree[17] = *a1++;
}
static void lrblk4_type5_move(sprite_status* pActwk) {
  lrblk4_move_data* a1;
  short d0;
  static lrblk4_move_data type5_mvtbl[6] =
  {
    { 128, 0,  128 },
    { 128, 0,  128 },
    { 128, 0,  128 },
    { 128, 0, -128 },
    { 128, 0, -128 },
    { 128, 0, -128 }
  };
label1:
  if (pActwk->actfree[16] == 0)
  {
    a1 = &type5_mvtbl[pActwk->actfree[17]];
    pActwk->actfree[16] = a1->cnt;
    tp_wset(pActwk,6,a1->speed);
  }
  else
  {
    d0 = tp_w(pActwk,6);
    pActwk->xspeed.w = d0;
    pActwk->xposi.l += d0 << 8;
    --pActwk->actfree[16];
    if (pActwk->actfree[16] == 0)
    {
      ++pActwk->actfree[17];
      if (pActwk->actfree[17] != 6) goto label1;
      pActwk->actfree[17] = 0;
      goto label1;
    }
  }
  lrblk4_type5_end(pActwk);
}
static void lrblk4_type5_end(sprite_status* pActwk) {
  tp_hitchk(pActwk, &actwk[0]);
}
static void lrblk4_type6(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &lrblk4_type6_init,
    &lrblk4_type6_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type6_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  uint_union dw;
  short i;
  short d0;
  unsigned char bd0;
  unsigned char d1;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprvsize = 16;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    d1 = 1;
    for (i = 0; i <= 2; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
        pNewActwk->userflag.b.h = 6;
        pNewActwk->actfree[18] = d1;
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        d0 = (char)d1 * 16;
        d0 *= -1;
        d0 += pActwk->xposi.w.h;
        pNewActwk->xposi.w.h = d0;
        dw.l = d1;
        dw.l <<= 5;
        d0 = dw.w.l;
        d0 += pActwk->yposi.w.h;
        pNewActwk->yposi.w.h = d0;
      }
      ++d1;
    }
  }
  bd0 = pActwk->actfree[18];
  pActwk->patno = bd0;
  ++bd0;
  pActwk->actfree[17] = bd0;
  bd0 = pActwk->actfree[18];
  d1 = 0;
  for (i = 0; i <= (short)(unsigned short)bd0; ++i)
  {
    d1 += 16;
  }
  pActwk->sprhsize = d1;
  d0 = pActwk->xposi.w.h;
  d0 += (unsigned short)d1;
  tp_wset(pActwk,8,d0);
  pActwk->actfree[16] = 128;
  lrblk4_type6_move(pActwk);
}
static void lrblk4_type6_move(sprite_status* pActwk) {
  short d0, d1, d3, stk;
  unsigned char d2;
  stk = pActwk->xposi.w.h;
  sinset(pActwk->actfree[16], &d0, &d1);
  d3 = 0;
  d2 = pActwk->actfree[17];
  if (d2)
  {
    do
    {
      d3 += d0;
      --d2;
    } while (d2 != 0);
  }
  d3 >>= 4;
  d0 = d3;
  d0 += tp_w(pActwk,8);
  pActwk->xposi.w.h = d0;
  d1 = stk;
  d0 -= d1;
  d0 <<= 8;
  pActwk->xspeed.w = d0;
  ++pActwk->actfree[16];
  tp_hitchk(pActwk, &actwk[0]);
}
static void lrblk4_type8(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &lrblk4_type8_init,
    &lrblk4_type8_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  lrblk4_foutchk(pActwk);
}
static void lrblk4_type8_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short d0;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 64;
  pActwk->sprvsize = 16;
  if (pActwk->actfree[18] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
      pNewActwk->userflag.b.h = 4;
      pNewActwk->actfree[19] = 8;
      pNewActwk->xposi.w.h = pActwk->xposi.w.h;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h - 96;
    }
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_LRBLK4);
      pNewActwk->userflag.b.h = 8;
      pNewActwk->actfree[18] = 1;
      tp_wset(pNewActwk,12,tp_w(pActwk,12));
      d0 = tp_w(pActwk,12);
      d0 -= 128;
      pNewActwk->xposi.w.h = d0;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h;
      d0 = tp_w(pActwk,12);
      d0 += 128;
      pActwk->xposi.w.h = d0;
    }
  }
  pActwk->xspeed.w = 512;
}
static void lrblk4_type8_move(sprite_status* pActwk) {
  short d0;
  pActwk->xposi.l += pActwk->xspeed.w << 8;
  tp_hitchk(pActwk, &actwk[0]);
  d0 = pActwk->xposi.w.h;
  if (d0 >= tp_w(pActwk,12))
  {
    d0 -= tp_w(pActwk,12);
    if (d0 == 256)
    {
      pActwk->xposi.w.h = tp_w(pActwk,12) - 256;
    }
  }
}

/* ---- R4/RBLK4.C ---- */
static void rblk4_act(sprite_status* pActwk) {
  static void(*const tbl[4])(sprite_status*) =
  {
    &rblk4_init,
    &rblk4_wait,
    &rblk4_move,
    &rblk4_push
  };
  if (pActwk->actfree[18] == 255)
  {
    rblk4_ract(pActwk);
  }
  else
  {
    tbl[pActwk->r_no0 / 2](pActwk);
    tp_draw(pActwk);
    tp_frameout_s(pActwk);
  }
}
static void rblk4_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sproffset = 17152;
  pActwk->sprvsize = 64;
  pActwk->sprhsize = 64;
  pActwk->patno = pActwk->userflag.b.h & 3;
  pActwk->actfree[19] = pActwk->patno;
  if (tp_actwkchk(&pNewActwk) != 0)
  {
    tp_frameout_s0(pActwk);
    return;
  }
  tp_setactno(pNewActwk,SCD_OBJ_RBLK4);
  tp_wset(pNewActwk,12,pActwk->xposi.w.h);
  tp_wset(pNewActwk,10,(unsigned short)(pActwk - actwk));
  pNewActwk->actfree[18] = 255;
  pNewActwk->actfree[19] = 0;
  tp_wset(pActwk,6,(unsigned short)(pNewActwk - actwk));
  if (tp_actwkchk(&pNewActwk) != 0)
  {
    tp_frameout_s0(pActwk);
    return;
  }
  tp_setactno(pNewActwk,SCD_OBJ_RBLK4);
  tp_wset(pNewActwk,12,pActwk->xposi.w.h);
  tp_wset(pNewActwk,10,(unsigned short)(pActwk - actwk));
  pNewActwk->actfree[18] = 255;
  pNewActwk->actfree[19] = 1;
  tp_wset(pActwk,10,(unsigned short)(pNewActwk - actwk));
}
static void rblk4_wait(sprite_status* pActwk) {
  sprite_status* pActwk_y;
  sprite_status* pPlayerwk;
  char* a4;
  short d0;
  short d1;
  unsigned char d3;
  pActwk_y = &actwk[tp_w(pActwk,6)];
  if (!(pActwk_y->actfree[20] & 128)) return;
  pPlayerwk = &actwk[0];
  if (pActwk->actfree[19] < 2)
  {
    d0 = pActwk->xposi.w.h;
    d1 = pPlayerwk->xposi.w.h + (short)(pPlayerwk->sprhsize + 2);
  }
  else
  {
    d1 = pActwk->xposi.w.h;
    d0 = pPlayerwk->xposi.w.h + (short)-((char)pPlayerwk->sprhsize + 2);
  }
  if (d0 < d1) return;
  d0 -= d1;
  a4 = dirstk;
  *a4 = 0;
  scdchk(pActwk, pActwk->yposi.w.h + d0, pActwk->xposi.w.h, 16, 0, 13, a4);
  d3 = dirstk[0];
  if (d3 & 1) d3 = 0;
  if (d1 >= 0)
  {
    if (d1 >= 16)
    {
      pActwk->r_no0 += 2;
      pActwk->actfree[16] = 16;
      pActwk->actfree[17] = 0;
      return;
    }
  }
  pPlayerwk = &actwk[tp_w(pActwk,10)];
  if (pPlayerwk->actfree[20])
  {
    pActwk->r_no0 = 6;
    pActwk->actfree[16] = 16;
    pActwk->actfree[17] = 0;
  }
}
static void rblk4_move(sprite_status* pActwk) {
  unsigned char d0;
  static unsigned char rkpchg0[16] =
  {
    0, 4, 1, 255,
    1, 5, 2, 255,
    2, 5, 1, 255,
    3, 6, 2, 255
  };
  d0 = pActwk->actfree[19];
  d0 *= 4;
  d0 = d0 + pActwk->actfree[17];
  d0 = rkpchg0[d0];
  if (d0 & 128)
  {
    pActwk->actfree[19] = pActwk->patno;
    pActwk->r_no0 -= 2;
    return;
  }
  pActwk->patno = d0;
  --pActwk->actfree[16];
  if (pActwk->actfree[16]) return;
  soundset(191);
  pActwk->actfree[16] = 4;
  ++pActwk->actfree[17];
}
static void rblk4_push(sprite_status* pActwk) {
  sprite_status* pPlayerwk;
  short sd0, sd1;
  unsigned char d0;
  static unsigned char pspchg0[16] =
  {
    0, 7, 3, 255,
    1, 4, 2, 255,
    2, 4, 1, 255,
    3, 7, 0, 255
  };
  d0 = pActwk->actfree[19];
  d0 *= 4;
  d0 = d0 + pActwk->actfree[17];
  d0 = pspchg0[d0];
  if (d0 & 128)
  {
    pActwk->actfree[19] = pActwk->patno;
    pActwk->r_no0 = 2;
    return;
  }
  pActwk->patno = d0;
  pPlayerwk = &actwk[0];
  sd0 = pActwk->yposi.w.h;
  sd1 = pActwk->sprvsize;
  sd0 -= sd1;
  sd1 = pPlayerwk->sprvsize;
  sd0 -= sd1;
  pPlayerwk->yposi.w.h = sd0;
  --pActwk->actfree[16];
  if (pActwk->actfree[16]) return;
  pActwk->actfree[16] = 8;
  ++pActwk->actfree[17];
  if (pActwk->actfree[17] == 1)
  {
    pPlayerwk->xposi.w.h = pActwk->xposi.w.h;
    return;
  }
  if (pActwk->actfree[17] == 2)
  {
    sd0 = 16;
    if (pActwk->actfree[19] & 2)
    {
      sd0 *= -1;
    }
    sd0 += pActwk->xposi.w.h;
    pPlayerwk->xposi.w.h = sd0;
  }
}
static void rblk4_ract(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &rblk4_ract_init,
    &rblk4_ract_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void rblk4_ract_init(sprite_status* pActwk) {
  unsigned char d0, d1;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sproffset = 17152;
  pActwk->patno = 8;
  d0 = 32;
  d1 = 16;
  if (pActwk->actfree[19])
  {
    d0 = 16;
    d1 = 16;
  }
  pActwk->sprhsize = d0;
  pActwk->sprvsize = d1;
  rblk4_ract_move(pActwk);
}
static void rblk4_ract_move(sprite_status* pActwk) {
  sprite_status* pRideact;
  char* a2;
  unsigned char d0;
  static char xyofset_tbl1[8] =
  {
    -16, 0,
    -16, 0,
     16, 0,
     16, 0
  };
  static char xyofset_tbl2[8] =
  {
    0, -32,
    0,  32,
    0,  32,
    0, -32
  };
  pRideact = &actwk[tp_w(pActwk,10)];
  d0 = pRideact->patno;
  if (d0 >= 4)
  {
    tp_ride_on_clr(pActwk, &actwk[0]);
    return;
  }
  d0 = d0 + d0;
  a2 = &xyofset_tbl1[d0];
  if (pActwk->actfree[19])
  {
    a2 = &xyofset_tbl2[d0];
  }
  pActwk->xposi.w.h = pRideact->xposi.w.h + (short)*a2++;
  pActwk->yposi.w.h = pRideact->yposi.w.h + (short)*a2++;
  tp_hitchk(pActwk, &actwk[0]);
  if (pActwk->actfree[19] == 0)
  {
    if (pActwk->cddat & 8) pActwk->actfree[20] = 255;
    else pActwk->actfree[20] = 0;
  }
  else
  {
    if (!(pActwk->cddat & 32))
    {
      pActwk->actfree[20] = 0;
      pActwk->actfree[21] = 0;
      return;
    }
    if (pActwk->actfree[21] == 0)
    {
      pActwk->actfree[20] = 255;
      pActwk->actfree[21] = 255;
      pActwk->cddat &= 223;
    }
  }
}

/* ---- R4/ESCAL4.C ---- */
static void escal4_act(sprite_status* pActwk) {
  static void(*const escal4_acttbl[3])(sprite_status*) = {
    &escal4_init,
    &escal4_wait,
    &escal4_moveup
  };
  escal4_acttbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  /* Retail R42A $20C9C6: cmpi.w #640,d0; bhi (unsigned): a passed escalator
     frames out (ESCAL4.C:82 compares signed; retail TT2A row 6821). */
  if ((unsigned short)((pActwk->xposi.w.h & 65408) - ((tp_scra_h() - 128) & 65408)) <= 640) return;
  tp_frameout_s0(pActwk); /* respawn bit cleared: reloads */
}
static short escal4_ridechk(sprite_status* pActwk) {
  return tp_hitchk(pActwk, &actwk[0]); /* d0 falls through as the result */
}
static void escal4_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17244;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 16;
}
static void escal4_wait(sprite_status* pActwk) {
  static short escal4_tbl[9] = {
     256, -256, 160,
     256, -256, 160,
     512, -512,  80
  };
  if (pActwk->actflg & 128) {
    if (escal4_ridechk(pActwk)) {
      pActwk->r_no0 += 2;
      pActwk->xspeed.w = escal4_tbl[(time_flag & 3) * 6 / 2];
      pActwk->yspeed.w = escal4_tbl[(time_flag & 3) * 6 / 2 + 1];
      tp_wset(pActwk,20,escal4_tbl[(time_flag & 3) * 6 / 2 + 2]);
    }
  }
}
static void escal4_moveup(sprite_status* pActwk) {
  escal4_ridechk(pActwk);
  if (tp_w(pActwk,20)) {
    pActwk->xposi.l += pActwk->xspeed.w << 8;
    pActwk->yposi.l += pActwk->yspeed.w << 8;
    if (!(tp_wset(pActwk,20,tp_w(pActwk,20)+-1))) {
      pActwk->xspeed.w = 0;
      pActwk->yspeed.w = 0;
    }
  }
}

/* ---- R4/BRUNKO4.C ---- */
static void brunko4_act(sprite_status* pActwk) {
  short wD0, wD1;
  static void(*const tbl[2])(sprite_status*) =
  {
    &brunko4_brunko_init,
    &brunko4_brunko_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  wD0 = tp_w(pActwk,12) & -128;
  wD1 = (tp_scra_h() - 128) & -128;
  wD0 -= wD1;
  if ((unsigned short)wD0 <= 640) return;
  tp_frameout(pActwk);
}
static void brunko4_ridechk(sprite_status* pActwk) {
  if (tp_ridechk(pActwk, &actwk[0]))
  {
    actwk[0].yposi.w.h = (pActwk->yposi.w.h - (short)pActwk->sprvsize) - (short)actwk[0].sprvsize + 2;
  }
}
static void brunko4_brunko_init(sprite_status* pActwk) {
  sprite_status* subActwk;
  unsigned char id;
  int i;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sprpri = 4;
  pActwk->sproffset = 832;
  if (pActwk->patno == 1)
    pActwk->sproffset += 16384;
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 10;
  pActwk->actfree[16] = 192;
  if (pActwk->actfree[18] == 6)
  {
    if (tp_actwkchk2(pActwk, &subActwk) == 0)
    {
      tp_setactno(subActwk,SCD_OBJ_SW4);
      tp_wset(subActwk,10,(unsigned short)(unsigned char)(pActwk - actwk));
      subActwk->actfree[15] = -16;
      subActwk->actfree[14] = 16;
      subActwk->userflag.b.h = (unsigned char)(pActwk->userflag.b.h & 15);
    }
  }
  if (!pActwk->actfree[18])
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    tp_wset(pActwk,8,pActwk->yposi.w.h);
    id = 6;
    for (i = 0; i < 6; ++i)
    {
      if (tp_actwkchk(&subActwk) == 0)
      {
        tp_setactno(subActwk,SCD_OBJ_BRUNKO4);
        tp_wset(subActwk,12,tp_w(pActwk,12));
        tp_wset(subActwk,8,tp_w(pActwk,8));
        subActwk->userflag.b.h = pActwk->userflag.b.h;
        subActwk->actfree[18] = id;
        subActwk->patno = 2;
        if (id == 6)
          subActwk->patno = 1;
      }
      --id;
    }
  }
  brunko4_brunko_move(pActwk);
}
static void brunko4_brunko_move(sprite_status* pActwk) {
  int_union xposi_bak, yposi_bak;
  int xposi_f, yposi_f;
  int i;
  xposi_bak.l = pActwk->xposi.l;
  yposi_bak.l = pActwk->yposi.l;
  brunko4_posiset(pActwk);
  if (pActwk->actfree[18] == 6)
  {
    xposi_bak.l = pActwk->xposi.l - xposi_bak.l;
    yposi_bak.l = pActwk->yposi.l - yposi_bak.l;
    xposi_f = xposi_bak.l & 0x80000000;
    yposi_f = yposi_bak.l & 0x80000000;
    for (i = 0; i < 8; ++i)
      xposi_bak.l = xposi_bak.l >> 1 | xposi_f;
    for (i = 0; i < 8; ++i)
      yposi_bak.l = yposi_bak.l >> 1 | yposi_f;
    pActwk->xspeed.w = xposi_bak.w.l;
    pActwk->yspeed.w = yposi_bak.w.l;
    brunko4_ridechk(pActwk);
  }
}
static void brunko4_posiset(sprite_status* pActwk) {
  short_union temp;
  unsigned short sin, cos, sinf, cosf, wD3, wD4;
  unsigned char bD0;
  int i;
  temp.b.h = ((int8_t)pActwk->actfree[16]);
  temp.b.l = ((int8_t)pActwk->actfree[17]);
  if (!(pActwk->userflag.b.h & 16))
    temp.w -= 128;
  else
    temp.w += 256;
  pActwk->actfree[16] = temp.b.h;
  pActwk->actfree[17] = temp.b.l;
  sinset(pActwk->actfree[16], (short*)&sin, (short*)&cos);
  wD3 = wD4 = 0;
  bD0 = pActwk->actfree[18];
  if (bD0)
  {
    do
    {
      wD3 += sin;
      wD4 += cos;
    } while (--bD0 != 0);
  }
  sinf = wD3 & 32768;
  cosf = wD4 & 32768;
  for (i = 4; i > 0; --i)
    wD3 = wD3 >> 1 | sinf;
  for (i = 4; i > 0; --i)
    wD4 = wD4 >> 1 | cosf;
  wD3 += tp_wu(pActwk,8);
  wD4 += tp_wu(pActwk,12);
  pActwk->yposi.w.h = wD3;
  pActwk->xposi.w.h = wD4;
}

/* ---- R4/RENKETU4.C ---- */
static void renketu4_act(sprite_status* pActwk) {
  unsigned short xwk1;
  unsigned short xwk2;
  static void(*const renketu4_acttbl[2])(sprite_status*) = {
    &renketu4_init,
    &renketu4_move
  };
  renketu4_acttbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  xwk1 = tp_wu(pActwk,12) & 65408;
  xwk2 = (unsigned short)tp_scra_h() - 128 & 65408;
  if ((unsigned short)(xwk1 - xwk2) > 640) {
    tp_frameout(pActwk);
  }
}
static void renketu4_ridechk(sprite_status* pActwk) {
  if (tp_ridechk(pActwk, &actwk[0])) {
    actwk[0].yposi.w.h = pActwk->yposi.w.h - (short)pActwk->sprvsize - (short)actwk[0].sprvsize + 2;
  }
}
static void renketu4_init(sprite_status* pActwk) {
  static char renketu4_tbl[18] = {
     32, 0,
      0, 0,
    -32, 0,
     24, 1,
     16, 1,
      8, 1,
     -8, 1,
    -16, 1,
    -24, 1
  };
  sprite_status* pNewactwk;
  unsigned char i;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  if (stageno.b.l == 2)
    pActwk->sproffset = 17408;
  else
    pActwk->sproffset = 17216;
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 8;
  if (!pActwk->actfree[18]) {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    tp_wset(pActwk,8,pActwk->yposi.w.h);
    for (i = 1; i <= 8; ++i) {
      if (tp_actwkchk(&pNewactwk) == 0) {
        tp_setactno(pNewactwk,SCD_OBJ_RENKETU4);
        pNewactwk->userflag.b.h = pActwk->userflag.b.h;
        pNewactwk->actfree[18] = i;
        tp_wset(pNewactwk,12,tp_w(pActwk,12));
        tp_wset(pNewactwk,8,tp_w(pActwk,8));
      }
    }
  }
  pActwk->actfree[21] = renketu4_tbl[pActwk->actfree[18] * 2];
  pActwk->patno = renketu4_tbl[pActwk->actfree[18] * 2 + 1];
  pActwk->sprpri = 1;
  if (pActwk->patno) {
    pActwk->sprpri = 3;
    pActwk->sproffset -= 16384;
  }
  if (pActwk->userflag.b.h & 16)
    tp_wset(pActwk,6,-256);
  else
    tp_wset(pActwk,6,256);
  renketu4_move(pActwk);
}
static void renketu4_move(sprite_status* pActwk) {
  unsigned short wD0, wD1;
  int_union lD0, lD1, lD4, lD5;
  short wk;
  renketu4_swchk(pActwk);
  tp_wset(pActwk,20,tp_w(pActwk,20)+(tp_w(pActwk,6)));
  sinset(pActwk->actfree[21], (short*)&wD0, (short*)&wD1);
  lD0.l = (short)wD0 * 6 >> 4;
  lD1.l = (short)wD1 * 6 >> 4;
  wk = lD0.w.h;
  lD0.w.h = lD0.w.l;
  lD0.w.l = wk;
  wk = lD1.w.h;
  lD1.w.h = lD1.w.l;
  lD1.w.l = wk;
  lD4.w.l = lD5.w.l = 0;
  lD4.w.h = tp_w(pActwk,8);
  lD5.w.h = tp_w(pActwk,12);
  lD0.l += lD4.l;
  lD1.l += lD5.l;
  pActwk->yspeed.w = (lD0.l - pActwk->yposi.l) << 8 >> 16;
  pActwk->xspeed.w = (lD1.l - pActwk->xposi.l) << 8 >> 16;
  pActwk->yposi.l = lD0.l;
  pActwk->xposi.l = lD1.l;
  if (!pActwk->patno) renketu4_ridechk(pActwk);
}
static void renketu4_swchk(sprite_status* pActwk) {
  if (!(pActwk->userflag.b.h & 128)) {
    if (switchflag[pActwk->userflag.b.h & 15] & 128) {
      if (pActwk->actfree[19]) return;
      tp_wset(pActwk,6,tp_w(pActwk,6)*(-1));
      pActwk->actfree[19] = 1;
      return;
    }
    pActwk->actfree[19] = 0;
  }
}

/* ---- R4/KUZURE4.C ---- */
static void(*const kuzure4_act_tbl[4])(sprite_status*) = {
  &kuzure4_main_ini,
  &kuzure4_main_check,
  &kuzure4_main_wait,
  &kuzure4_main_break
};
static void(*const parts_act_tbl[3])(sprite_status*) = {
  &kuzure4_parts_ini,
  &kuzure4_parts_wait,
  kuzure4_parts_fall
};
static void kuzure4_act(sprite_status* pActwk) {
  if (pActwk->userflag.b.l) {
    kuzure4_parts(pActwk);
  } else {
    kuzure4_act_tbl[pActwk->r_no0 / 2](pActwk);
  }
}
static void kuzure4_main_ini(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg = 4;
  pActwk->sproffset = 17252;
  pActwk->sprpri = 3;
  pActwk->sprvsize = 17;
  pActwk->patno = pActwk->userflag.b.h - 1;
  pActwk->sprhs = pActwk->sprhsize = pActwk->userflag.b.h * 8;
  kuzure4_main_check(pActwk);
}
static void kuzure4_main_check(sprite_status* pActwk) {
  if (tp_ridechk(pActwk, &actwk[0])) {
    pActwk->r_no0 += 2;
    tp_noreload(pActwk); /* KUZURE4 zeroes the respawn index */
    tp_wset(pActwk,0,8);
    if (actwk[0].xspeed.w < 0) {
      tp_wset(pActwk,2,-8);
    } else {
      tp_wset(pActwk,2,8);
    }
    soundset(163);
  }
  tp_draw(pActwk);
  tp_frameout_s(pActwk);
}
static void kuzure4_main_wait(sprite_status* pActwk) {
  tp_ridechk(pActwk, &actwk[0]);
  if (tp_wset(pActwk,0,tp_w(pActwk,0)+-1) < 0) {
    pActwk->r_no0 += 2;
  }
  tp_draw(pActwk);
}
static void kuzure4_main_break(sprite_status* pActwk) {
  unsigned char flagwk;
  short xwk;
  short ywk;
  sprite_status* pNewact;
  flagwk = 255;
  ywk = 8;
  xwk = ((short)pActwk->userflag.b.h - 1) * 8;
  if (tp_w(pActwk,2) >= 0) {
    xwk *= -1;
  }
  if (tp_actwkchk(&pNewact) == 0) {
    tp_setactno(pNewact,pActwk->actno);
    pNewact->actflg = pActwk->actflg;
    pNewact->sproffset = pActwk->sproffset;
    pNewact->xposi.l = pActwk->xposi.l;
    pNewact->yposi.l = pActwk->yposi.l;
    pNewact->userflag.b.l = flagwk;
    pNewact->yposi.w.h -= ywk;
    pNewact->xposi.w.h += xwk;
    tp_wset(pNewact,0,4);
    if (tp_actwkchk(&pNewact) == 0) {
      tp_setactno(pNewact,pActwk->actno);
      pNewact->actflg = pActwk->actflg;
      pNewact->sproffset = pActwk->sproffset;
      pNewact->xposi.l = pActwk->xposi.l;
      pNewact->yposi.l = pActwk->yposi.l;
      pNewact->userflag.b.l = flagwk;
      pNewact->yposi.w.h += ywk;
      pNewact->xposi.w.h += xwk;
    }
  }
  if (tp_ridechk(pActwk, &actwk[0])) {
    tp_ride_on_clr(pActwk, &actwk[0]);
  }
  if (--pActwk->userflag.b.h <= 0) {
    tp_frameout(pActwk);
  } else {
    pActwk->r_no0 -= 2;
    --pActwk->patno;
    pActwk->sprhs -= 8;
    pActwk->sprhsize -= 8;
    tp_wset(pActwk,0,7);
    pActwk->xposi.w.h += tp_w(pActwk,2);
    tp_ridechk(pActwk, &actwk[0]);
    tp_draw(pActwk);
  }
}
static void kuzure4_parts(sprite_status* pActwk) {
  parts_act_tbl[pActwk->r_no0 / 2](pActwk);
}
static void kuzure4_parts_ini(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->patno = 8;
  pActwk->sprpri = 3;
  pActwk->sprhs = pActwk->sprhsize = 8;
  pActwk->sprvsize = 8;
  tp_draw(pActwk);
}
static void kuzure4_parts_wait(sprite_status* pActwk) {
  if (tp_wset(pActwk,0,tp_w(pActwk,0)+-1) < 0) {
    pActwk->r_no0 += 2;
  }
  tp_draw(pActwk);
}
static void kuzure4_parts_fall(sprite_status* pActwk) {
  int spdwk;
  if (!(pActwk->actflg & 128)) {
    tp_frameout(pActwk);
  } else {
    spdwk = (long int)tp_l(pActwk,2) + 16384;
    if ((long int)spdwk > 1441792) {
      spdwk = 1441792;
    }
    tp_lset(pActwk,2,spdwk);
    pActwk->yposi.l += spdwk;
    tp_draw(pActwk);
  }
}

/* ---- R4/DAID4.C ---- */
static void daid4_act(sprite_status* pActwk) {
  static void(*const tbl[6])(sprite_status*) =
  {
    &daid4_a_ini,
    &daid4_a_born,
    &daid4_a_off,
    &daid4_a_off1,
    &daid4_a_on,
    &daid4_a_on1
  };
  tbl[pActwk->r_no0 / 2](pActwk);
}
static void daid4_a_ini(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sprhs = 32;
  pActwk->sprhsize = 32;
  pActwk->sproffset = 17168;
  tp_wset(pActwk,0,pActwk->yposi.w.h);
  pActwk->sprvsize = 33;
}
static void daid4_a_born(sprite_status* pActwk) {
  short d0;
  d0 = actwk[0].yposi.w.h;
  d0 -= 224;
  if (d0 > tp_w(pActwk,0))
  {
    pActwk->r_no0 += 2;
    pActwk->yposi.w.h = d0;
  }
  tp_frameout_s(pActwk);
}
static void daid4_a_off(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->sprvsize = 33;
  pActwk->patno &= 254;
  tp_lset(pActwk,2,0);
  pActwk->yspeed.w = 0;
  daid4_a_off1(pActwk);
}
static void daid4_a_off1(sprite_status* pActwk) {
  short d0;
  pActwk->yposi.l += tp_l(pActwk,2);
  tp_lset(pActwk,2,tp_l(pActwk,2)+(1024));
  if ((long int)tp_l(pActwk,2) > 65536)
  {
    tp_lset(pActwk,2,65536);
  }
  if (!(pActwk->actflg & 128))
  {
    d0 = pActwk->yposi.w.h;
    d0 -= actwk[0].yposi.w.h;
    if (d0 < 0)
    {
      d0 *= -1;
    }
    if (d0 > 224)
    {
      pActwk->r_no0 = 2;
      goto label1;
    }
  }
  if (tp_ridechk(pActwk, &actwk[0]))
  {
    pActwk->r_no0 = 8;
    tp_ride_on_clr(pActwk, &actwk[0]);
    pActwk->sprvsize = 31;
    pActwk->yposi.w.h += 2;
    actwk[0].yposi.w.h += 4;
    soundset(191);
  }
label1:
  tp_draw(pActwk);
  tp_frameout_s(pActwk);
}
static void daid4_a_on(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->patno |= 1;
  pActwk->sprvsize = 31;
  pActwk->yspeed.w = -512;
  daid4_a_on1(pActwk);
}
static void daid4_a_on1(sprite_status* pActwk) {
  short d0;
  d0 = pActwk->yposi.w.h;
  if (d0 <= tp_w(pActwk,0))
  {
    pActwk->r_no0 = 2;
  } else
  {
    if (tp_ridechk(pActwk, &actwk[0]) == 0)
    {
      pActwk->r_no0 = 4;
      pActwk->yposi.w.h -= 2;
      actwk[0].yposi.w.h -= 4;
    }
  }
  tp_draw(pActwk);
  pActwk->yposi.l -= 0x20000;
  tp_frameout_s(pActwk);
}

/* ---- R4/BANEIWA.C ---- */
typedef struct {
  unsigned char a;
  char b;
  short c;
}
baneiwa_move_data;
static void baneiwa_act(sprite_status* pActwk) {
  sprite_status* pRideAct;
  static void(*const tbl[2])(sprite_status*) =
  {
    &baneiwa_init,
    &baneiwa_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  if (pActwk->actfree[18])
  {
    pRideAct = &actwk[tp_w(pActwk,10)];
    if (pRideAct->actno != SCD_OBJ_BANEIWA)
    {
      tp_frameout(pActwk);
    }
  }
  else
  {
    tp_frameout_s(pActwk);
  }
}
static void baneiwa_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 32;
  if (pActwk->actfree[18] == 0)
  {
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_BANEIWA);
      pNewActwk->xposi.w.h = pActwk->xposi.w.h + 32;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h;
      pNewActwk->actfree[18] = 1;
      tp_wset(pNewActwk,10,(unsigned short)(pActwk - actwk));
    }
  }
}
static void baneiwa_move(sprite_status* pActwk) {
  short d0;
  short d1;
  unsigned char index;
  static baneiwa_move_data baneiwa_mvtbl[4] =
  {
    { 128, -4,  512 },
    { 128, -4,    0 },
    { 128,  4, -512 },
    { 128,  4,    0 }
  };
  if (pActwk->yspeed.w < 0)
  {
    tp_ride_on_chk(pActwk, &actwk[0]);
  }
  if (pActwk->actfree[16])
  {
    pActwk->yposi.l += pActwk->yspeed.w << 8;
    pActwk->yspeed.w += tp_w(pActwk,20);
    --pActwk->actfree[16];
    if (pActwk->actfree[16]) goto label1;
    ++pActwk->actfree[17];
    if (pActwk->actfree[17] != 4) goto label1;
    pActwk->actfree[17] = 0;
    goto label1;
  }
  index = pActwk->actfree[17];
  pActwk->actfree[16] = baneiwa_mvtbl[index].a;
  d0 = baneiwa_mvtbl[index].b;
  d1 = baneiwa_mvtbl[index].c;
  if (pActwk->actfree[18])
  {
    d0 *= -1;
    d1 *= -1;
  }
  tp_wset(pActwk,20,d0);
  pActwk->yspeed.w = d1;
label1:
  if (pActwk->yspeed.w >= 0)
  {
    tp_ride_on_chk(pActwk, &actwk[0]);
  }
}

/* ---- R4/SW4.C ---- */
static void sw4_act(sprite_status* pActwk) {
  if (pActwk->r_no0) sw4_act_move(pActwk);
  else sw4_act_init(pActwk);
}
static void sw4_act_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 16;
  pActwk->sproffset = 1290;
  pActwk->sprvsize = 10;
  tp_wset(pActwk,18,(unsigned short)pActwk->userflag.b.h);
  pActwk->actfree[20] = 0;
  pActwk->actfree[21] = 0;
  sw4_act_move(pActwk);
}
static void sw4_act_move(sprite_status* pActwk) {
  sprite_status* pActwk_a1;
  sprite_status* pPlayerwk;
  unsigned char* a4;
  short d0, d1, d3, d4;
  short z;
  d0 = tp_w(pActwk,10);
  if (d0)
  {
    pActwk_a1 = &actwk[d0];
    d1 = pActwk->xposi.w.h;
    d0 = ((int8_t)pActwk->actfree[14]);
    d0 += pActwk_a1->xposi.w.h;
    pActwk->xposi.w.h = d0;
    d0 -= d1;
    d0 <<= 8;
    pActwk->xspeed.w = d0;
    d0 = ((int8_t)pActwk->actfree[15]);
    d0 += pActwk_a1->yposi.w.h;
    pActwk->yposi.w.h = d0;
  }
  pActwk->actfree[20] = pActwk->actfree[21];
  d3 = pActwk->xposi.w.h;
  d4 = pActwk->yposi.w.h;
  (void)d3;(void)d4; /* retail dead stores */
  pPlayerwk = &actwk[0];
  if (tp_hitchk(pActwk, pPlayerwk))
  {
    z = sw4_hosei(pActwk, pPlayerwk);
  }
  else
  {
    z = 1;
  }
  a4 = &switchflag[tp_w(pActwk,18)];
  if (z == 0) pActwk->actfree[21] = 255;
  else pActwk->actfree[21] = 0;
  if (z)
  {
    *a4 &= 127;
  }
  else
  {
    sw4_hosei(pActwk, pPlayerwk);
    *a4 |= 128;
    *a4 |= 64;
  }
  if (pActwk->actfree[20] == 0 && pActwk->actfree[21] == 255)
  {
    if (pActwk->actflg & 128)
    {
      soundset(191);
    }
    *a4 ^= 32;
    pPlayerwk->yposi.w.h += 8;
    if (tp_w(pActwk,10))
    {
      pActwk->actfree[15] += 4;
    }
    else
    {
      pActwk->yposi.w.h += 4;
    }
    pActwk->patno = 1;
    pActwk->sprvsize -= 4;
  }
  if (pActwk->actfree[20] == 255 && pActwk->actfree[21] == 0)
  {
    pPlayerwk->yposi.w.h -= 8;
    if (tp_w(pActwk,10))
    {
      pActwk->actfree[15] -= 4;
    }
    else
    {
      pActwk->yposi.w.h -= 4;
    }
    pActwk->patno = 0;
    pActwk->sprvsize += 4;
  }
  tp_draw(pActwk);
  d0 = tp_w(pActwk,10);
  if (d0 == 0)
  {
    tp_frameout_s(pActwk);
    return;
  }
  pActwk_a1 = &actwk[d0];
  d0 = tp_w(pActwk_a1,12);
  d0 &= -128;
  d1 = tp_scra_h();
  d1 -= 128;
  d1 &= -128;
  d0 -= d1;
  if ((unsigned short)d0 > 640) tp_frameout_s0(pActwk);
}
static short sw4_hosei(sprite_status* pActwk, sprite_status* pActwk2) {
  short d0, d1;
  short z;
  d0 = pActwk->yposi.w.h;
  d1 = pActwk->sprvsize;
  d0 -= d1;
  d1 = pActwk2->sprvsize;
  d0 -= d1;
  ++d0;
  pActwk2->yposi.w.h = d0;
  if (d0) z = 0;
  else z = 1;
  return z;
}

/* ---- R4/SWBLK4.C ---- */
static void(*const switchr4_jmp_tbl[2])(sprite_status*) = {
  &swblk4_switchr4_init,
  &swblk4_switchr4_move
};
static void(*const swblkr4_jmp_tbl[2])(sprite_status*) = {
  &swblk4_swblkr4_init,
  &swblk4_swblkr4_move
};
static void swblk4_switchr4(sprite_status* pActwk) {
  sprite_status* pRideact;
  short actidx;
  switchr4_jmp_tbl[pActwk->r_no0 / 2](pActwk);
  tp_ride_on_chk(pActwk, &actwk[0]);
  if ((actidx = tp_w(pActwk,10)) != 0) {
    pRideact = &actwk[actidx];
    pActwk->xposi.w.h = (short)(char)pActwk->actfree[14]
                      + pRideact->xposi.w.h;
    pActwk->yposi.w.h = (short)(char)pActwk->actfree[15]
                      + pRideact->yposi.w.h;
  }
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void swblk4_switchr4_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 1290;
  pActwk->sprpri = 3;
  if (!tp_w(pActwk,12)) {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
  }
  pActwk->sprhsize = 14;
  pActwk->sprvsize = 5;
  swblk4_switchr4_move(pActwk);
}
static void swblk4_switchr4_move(sprite_status* pActwk) {
  if (swblk4_switchr4_colichk(pActwk, &actwk[0]) != 0) {
    pActwk->userflag.b.h |= 1;
  } else {
    pActwk->userflag.b.h &= -2;
  }
  if (pActwk->userflag.b.h) {
    pActwk->patno = 1;
  } else {
    pActwk->patno = 0;
  }
}
static unsigned int swblk4_switchr4_colichk(sprite_status* pActwk, sprite_status* pPlayerwk) {
  short szwk;
  short poswk;
  szwk = (short)(char)pActwk->sprhsize + 8;
  poswk = szwk + (pPlayerwk->xposi.w.h - pActwk->xposi.w.h);
  if (poswk < 0 || poswk >= szwk * 2) {
    return 0;
  }
  poswk = (short)(char)pPlayerwk->sprvsize + pPlayerwk->yposi.w.h;
  szwk = pActwk->yposi.w.h - 16 - poswk;
  if (szwk > 0 || szwk < -16) {
    return 0;
  }
  return 1;
}
static void swblk4_swblkr4(sprite_status* pActwk) {
  short actidx, xwk, hwk;
  sprite_status* pRideact;
  swblkr4_jmp_tbl[pActwk->r_no0 / 2](pActwk);
  tp_ride_on_chk(pActwk, &actwk[0]);
  if (pActwk->actfree[18]) {
    if ((actidx = tp_w(pActwk,10)) != 0) {
      pRideact = &actwk[actidx];
      if (pRideact->actno != SCD_OBJ_SWBLKR4) {
        tp_frameout(pActwk);
        return;
      }
      pActwk->xposi.w.h = pRideact->xposi.w.h - 32;
      pActwk->yposi.w.h = pRideact->yposi.w.h + 32;
    }
  }
  tp_draw(pActwk);
  xwk = tp_w(pActwk,12) & -128;
  hwk = tp_scra_h() - 128 & -128;
  if ((unsigned short)(xwk - hwk) > 640) {
    tp_frameout(pActwk);
  }
}
static void swblk4_swblkr4_init(sprite_status* pActwk) {
  sprite_status* pNewact;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprpri = 3;
  if (!pActwk->actfree[18]) {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    tp_wset(pActwk,8,pActwk->yposi.w.h);
    pActwk->xposi.w.h += 16;
    pActwk->sprhsize = 16;
    pActwk->sprvsize = 64;
    pActwk->patno = 1;
    if (tp_actwkchk2(pActwk, &pNewact) != 0) {
      tp_frameout(pActwk);
      return;
    }
    tp_setactno(pNewact,pActwk->actno);
    tp_wset(pNewact,12,tp_w(pActwk,12));
    tp_wset(pNewact,8,tp_w(pActwk,8));
    pNewact->sprhsize = 16;
    pNewact->sprvsize = 32;
    pNewact->actfree[18] = 1;
    pNewact->yposi.w.h = pActwk->yposi.w.h + 32;
    pNewact->xposi.w.h = pActwk->xposi.w.h - 32;
    tp_wset(pNewact,10,pActwk - actwk);
    tp_wset(pActwk,10,pNewact - actwk);
    pNewact->patno = 2;
    if (tp_actwkchk2(pActwk, &pNewact) != 0) {
      tp_frameout(pActwk);
      return;
    }
    tp_setactno(pNewact,SCD_OBJ_SWITCHR4);
    tp_wset(pNewact,10,pActwk - actwk);
    tp_wset(pActwk,6,pNewact - actwk);
    pNewact->actfree[15] = 188;
    tp_wset(pNewact,12,tp_w(pActwk,12));
    tp_wset(pNewact,8,tp_w(pActwk,8));
  }
  swblk4_swblkr4_move(pActwk);
}
static void swblk4_swblkr4_move(sprite_status* pActwk) {
  int ysv;
  sprite_status* pRideact;
  if (pActwk->actfree[18]) return;
  ysv = pActwk->yposi.l;
  if (pActwk->yspeed.w < 0) {
    pActwk->yposi.w.h -= 64;
    if (emycol_u(pActwk) < 0) {
      pActwk->yspeed.w = 0;
    }
  }
  else if (emycol_d(pActwk) < 0) {
    pActwk->yspeed.w = 0;
  }
  pActwk->yposi.l = ysv;
  pActwk->yposi.l += pActwk->yspeed.w << 8;
  pRideact = &actwk[tp_w(pActwk,10)];
  if (pRideact->actno == SCD_OBJ_SWBLKR4) {
    pRideact->yspeed.w = pActwk->yspeed.w;
  }
  pRideact = &actwk[tp_w(pActwk,6)];
  if (pRideact->actno != SCD_OBJ_SWITCHR4) return;
  if (pRideact->userflag.b.h & 3) {
    if ((pActwk->yspeed.w -= 8) < -256) {
      pActwk->yspeed.w = -256;
    }
  }
  else {
    if ((pActwk->yspeed.w += 8) > 256) {
      pActwk->yspeed.w = 256;
    }
  }
}

/* ---- R4/SWGUN4.C ---- */
static void swgun4_act(sprite_status* pActwk) {
  static void(*const tbl[3])(sprite_status*) =
  {
    &swgun4_init,
    &swgun4_move,
    &swgun4_move1
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s00(pActwk, tp_w(pActwk,12));
}
static void swgun4_init(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  short* a2;
  short i;
  unsigned char d1;
  static short tbl[12] =
  {
       0,    0,
     -64,   64,
    -128,  128,
      64,  -64,
      96, -128,
     128, -128
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 1290;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 14;
  pActwk->sprvsize = 8;
  if (pActwk->actfree[10] == 0)
  {
    tp_wset(pActwk,12,pActwk->xposi.w.h);
    tp_wset(pActwk,8,pActwk->yposi.w.h);
    tp_wset(pActwk,16,(unsigned short)(pActwk - actwk));
    d1 = 1;
    for (i = 0; i <= 4; ++i)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_SWGUN4);
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        tp_wset(pNewActwk,16,(unsigned short)(pActwk - actwk));
        pNewActwk->actfree[10] = d1;
        a2 = &tbl[d1 * 2];
        pNewActwk->xposi.w.h = pActwk->xposi.w.h + *a2++;
        pNewActwk->yposi.w.h = pActwk->yposi.w.h + *a2++;
        tp_wset(pNewActwk,8,pNewActwk->yposi.w.h);
      }
      ++d1;
    }
  }
}
static void swgun4_move(sprite_status* pActwk) {
  sprite_status* a1;
  short d0;
  swgun4_switch_move(pActwk);
  a1 = &actwk[tp_w(pActwk,16)];
  d0 = tp_w(a1,18);
  if (d0 == 0) return;
  if (pActwk->actfree[4] == 0)
  {
    soundset(191);
    pActwk->actfree[4] = 255;
  }
  if ((unsigned short)((unsigned short)pActwk->actfree[5] + 16) < 256)
  {
    pActwk->actfree[5] += 16;
    return;
  }
  pActwk->actfree[5] += 16;
  pActwk->r_no0 += 2;
  tp_ride_on_clr(pActwk, &actwk[0]);
  pActwk->actfree[15] = pActwk->actfree[14] = 0;
  pActwk->patno = 2;
}
static void swgun4_move1(sprite_status* pActwk) {
  sprite_status* a1;
  static void(*const tbl[4])(sprite_status*) =
  {
    &swgun4_hariset,
    &swgun4_bp1000,
    &swgun4_awaset,
    &swgun4_ring4set
  };
  a1 = &actwk[tp_w(pActwk,16)];
  tbl[a1->actfree[11]](pActwk);
}
static void swgun4_switch_move(sprite_status* pActwk) {
  sprite_status* pPlayerwk;
  sprite_status* pActwk_m;
  unsigned short d0, d1;
  short r;
  static unsigned char tbl[42] =
  {
    2, 1, 0, 3, 3, 2,
    1, 0, 3, 3, 2, 2,
    0, 3, 3, 2, 2, 1,
    2, 2, 1, 0, 3, 3,
    3, 2, 2, 1, 0, 3,
    3, 3, 2, 2, 1, 0,
    0, 0, 0, 0, 0, 0
  };
  pActwk->actfree[6] = pActwk->actfree[7];
  pPlayerwk = &actwk[0];
  r = tp_hitchk_u(pActwk, pPlayerwk);
  if (r)
  {
    pActwk->actfree[7] = 255;
  }
  else
  {
    pActwk->actfree[7] = 0;
    goto label1;
  }
  if (pPlayerwk->yspeed.w < 0) goto label1;
  if (pActwk->actfree[4]) goto label1;
  pActwk_m = &actwk[tp_w(pActwk,16)];
  tp_wset(pActwk_m,18,(unsigned short)(pActwk - actwk));
  d0 = pActwk->actfree[10];
  d0 *= 6;
  d1 = tp_pltime_b3();
  d1 &= 255;
  d1 /= 10;
  d1 &= 7;
  d0 += d1;
  pActwk->actfree[11] = tbl[d0];
  pActwk_m->actfree[11] = pActwk->actfree[11];
label1:
  if (pActwk->actfree[6] == 0 && pActwk->actfree[7] == 255)
  {
    pPlayerwk->yposi.w.h += 8;
    pActwk->yposi.w.h += 4;
    pActwk->patno = 1;
    pActwk->sprvsize -= 4;
  }
  if (pActwk->actfree[6] == 255 && pActwk->actfree[7] == 0)
  {
    pPlayerwk->yposi.w.h -= 8;
    pActwk->yposi.w.h -= 4;
    pActwk->patno = 0;
    pActwk->sprvsize += 4;
  }
}
static void swgun4_hariset(sprite_status* pActwk) {
  sprite_status* pMaster;
  sprite_status* pSlave;
  sprite_status* pNewActwk;
  if (pActwk->actfree[14])
  {
    tp_frameout(pActwk);
    return;
  }
  pMaster = &actwk[tp_w(pActwk,16)];
  pSlave = &actwk[tp_w(pMaster,18)];
  if (pActwk != pSlave)
  {
    if (pActwk->actfree[10] != 4)
    {
      if (tp_actwkchk(&pNewActwk) == 0)
      {
        tp_setactno(pNewActwk,SCD_OBJ_HARIR4);
        pNewActwk->xposi.w.h = pActwk->xposi.w.h;
        tp_wset(pNewActwk,12,tp_w(pActwk,12));
        pNewActwk->yposi.w.h = tp_w(pActwk,8);
      }
    }
  }
  ++pActwk->actfree[14];
}
static void swgun4_awaset(sprite_status* pActwk) {
  sprite_status* pMaster;
  sprite_status* pSlave;
  sprite_status* pNewActwk;
  pMaster = &actwk[tp_w(pActwk,16)];
  pSlave = &actwk[tp_w(pMaster,18)];
  if (pActwk == pSlave)
  {
    if ((unsigned short)((unsigned short)pActwk->actfree[14] + 1) > 255)
    {
      tp_frameout(pActwk);
    }
    ++pActwk->actfree[14];
    return;
  }
  if ((unsigned short)((unsigned short)pActwk->actfree[15] + 4) <= 255)
  {
    pActwk->actfree[15] += 4;
    return;
  }
  pActwk->actfree[15] += 4;
  if (tp_actwkchk(&pNewActwk) == 0)
  {
    tp_setactno(pNewActwk,SCD_OBJ_AWA);
    pNewActwk->xposi.w.h = pActwk->xposi.w.h;
    pNewActwk->yposi.w.h = tp_w(pActwk,8);
    pNewActwk->userflag.b.h = 2;
  }
  ++pActwk->actfree[14];
  if (pActwk->actfree[14] >= 2)
  {
    tp_frameout(pActwk);
  }
}
static void swgun4_ring4set(sprite_status* pActwk) {
  sprite_status* pMaster;
  sprite_status* pNewActwk;
  short d0;
  static char tbl[22] =
  {
    -32, 0, 32, 64, 96, 127, 96, 64, 32, 0, -32,
    -32, 0, 32, 64, 96, 127, 96, 64, 32, 0, -32
  };
  pMaster = &actwk[tp_w(pActwk,16)];
  if (pActwk != pMaster)
  {
    tp_frameout(pActwk);
    return;
  }
  if ((unsigned short)pActwk->actfree[14] + 16 < 256)
  {
    pActwk->actfree[14] += 16;
    return;
  }
  pActwk->actfree[14] += 16;
  if (pActwk->actfree[15] >= 21)
  {
    tp_frameout(pActwk);
    return;
  }
  if (tp_actwkchk(&pNewActwk) == 0)
  {
    tp_setactno(pNewActwk,SCD_OBJ_RING4);
    d0 = pActwk->yposi.w.h;
    d0 -= 384;
    pNewActwk->yposi.w.h = d0;
    d0 = tbl[pActwk->actfree[15]];
    d0 += pActwk->xposi.w.h;
    pNewActwk->xposi.w.h = d0;
  }
  ++pActwk->actfree[15];
}
static void swgun4_bp1000(sprite_status* pActwk) {
  sprite_status* pMaster;
  sprite_status* pSlave;
  sprite_status* pNewActwk;
  if (pActwk->actfree[14])
  {
    tp_frameout(pActwk);
    return;
  }
  pMaster = &actwk[tp_w(pActwk,16)];
  pSlave = &actwk[tp_w(pMaster,18)];
  if (pMaster != pSlave)
  {
    tp_scoreup(100);
    if (tp_actwkchk(&pNewActwk) == 0)
    {
      tp_setactno(pNewActwk,SCD_OBJ_TENSU4);
      pNewActwk->xposi.w.h = pActwk->xposi.w.h;
      pNewActwk->yposi.w.h = pActwk->yposi.w.h;
    }
  }
  ++pActwk->actfree[14];
}
static const unsigned char ring4_pchg0[6] = { 5, 4, 5, 6, 7, 252 };
static const unsigned char* const ring4_chg[1] = { ring4_pchg0 };
static void swgun4_ring4(sprite_status* pActwk) {
  static void(*const tbl[5])(sprite_status*) =
  {
    &swgun4_ring4_init,
    &swgun4_ring4_move,
    &swgun4_ring4_get,
    &swgun4_ring4_die,
    &swgun4_ring4_erase
  };
  tbl[pActwk->r_no0 / 2](pActwk);
}
static void swgun4_ring4_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->sprvsize = 8;
  pActwk->sprhs = 8;
  pActwk->sproffset = 42926;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->colino = 71;
  pActwk->sprhsize = 8;
  tp_wset(pActwk,14,2048);
  pActwk->yspeed.w = 256;
  pActwk->actfree[16] = 255;
  pActwk->actfree[17] = 48;
  swgun4_ring4_move(pActwk);
}
static void swgun4_ring4_move(sprite_status* pActwk) {
  short d0, d1;
  speedset2(pActwk);
  pActwk->yspeed.w += 24;
  if (pActwk->actfree[17])
  {
    --pActwk->actfree[17];
    if (pActwk->actfree[17]) goto label1;
  }
  d1 = emycol_d(pActwk);
  if (d1 < 0)
  {
    pActwk->yposi.w.h += d1;
    d0 = pActwk->yspeed.w;
    d0 >>= 2;
    pActwk->yspeed.w -= d0;
    pActwk->yspeed.w *= -1;
  }
label1:
  d0 = tp_w(pActwk,12);
  d0 += tp_w(pActwk,14);
  tp_wset(pActwk,12,d0);
  d0 >>= 12;
  d0 &= 3;
  pActwk->patno = d0;
  tp_wset(pActwk,14,tp_w(pActwk,14)-(8));
  --pActwk->actfree[16];
  if (pActwk->actfree[16] == 0)
  {
    swgun4_ring4_erase(pActwk);
    return;
  }
  d0 = scralim_down;
  d0 += 224;
  if (d0 < pActwk->yposi.w.h)
  {
    swgun4_ring4_erase(pActwk);
    return;
  }
  tp_draw(pActwk);
}
static void swgun4_ring4_get(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->colino = 0;
  pActwk->sprpri = 1;
  tp_ringgetsub();
  swgun4_ring4_die(pActwk);
}
static void swgun4_ring4_die(sprite_status* pActwk) {
  tp_patchg(pActwk, ring4_chg);
  tp_draw(pActwk);
}
static void swgun4_ring4_erase(sprite_status* pActwk) {
  tp_frameout(pActwk);
}
static void swgun4_tensu4(sprite_status* pActwk) {
  static void(*const tbl[2])(sprite_status*) =
  {
    &swgun4_tensu4_init,
    &swgun4_tensu4_move
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
}
static void swgun4_tensu4_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->sproffset = 878;
  pActwk->actflg = 4;
  pActwk->sprpri = 1;
  pActwk->sprhsize = 8;
  pActwk->yspeed.w = -768;
  swgun4_tensu4_move(pActwk);
}
static void swgun4_tensu4_move(sprite_status* pActwk) {
  if (pActwk->yspeed.w >= 0)
  {
    tp_frameout(pActwk);
  }
  else
  {
    speedset2(pActwk);
    pActwk->yspeed.w += 24;
  }
}

/* ---- R4/TOBIRA4.C ---- */
static void tobira4_act(sprite_status* pActwk) {
  static void(*const tbl[4])(sprite_status*) =
  {
    &tobira4_init,
    &tobira4_move,
    &tobira4_chek,
    &tobira4_clse
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s(pActwk);
}
static void tobira4_init(sprite_status* pActwk) {
  unsigned char d0, d1;
  static unsigned char tbl[20] =
  {
    64,  8, 128, 2,
    64,  8, 128, 2,
     8, 32,  64, 1,
     8, 64, 128, 0,
     8, 64, 128, 0
  };
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17472;
  pActwk->sprpri = 2;
  tp_wset(pActwk,12,pActwk->xposi.w.h);
  tp_wset(pActwk,8,pActwk->yposi.w.h);
  d1 = d0 = pActwk->userflag.b.h;
  d1 &= 15;
  pActwk->actfree[6] = d1;
  d0 >>= 4;
  d0 &= 15;
  pActwk->actfree[7] = d0;
  d0 <<= 2;
  pActwk->sprhsize = tbl[d0];
  pActwk->sprvsize = tbl[d0 + 1];
  pActwk->actfree[17] = tbl[d0 + 2];
  pActwk->patno = tbl[d0 + 3];
}
static void tobira4_move(sprite_status* pActwk) {
  unsigned char d0;
  d0 = pActwk->actfree[6];
  if (!(switchflag[d0] & 128))
  {
    pActwk->actfree[18] = 255;
  }
  else
  {
    pActwk->actfree[18] = 0;
  }
  if (pActwk->actfree[7] != 4)
  {
    if (pActwk->actfree[16])
    {
      pActwk->actfree[18] = 0;
    }
  }
  tp_wset(pActwk,14,actwk[0].xposi.w.h);
  tp_wset(pActwk,20,actwk[0].yposi.w.h);
  tobira4_cnt(pActwk);
  tp_hitchk(pActwk, &actwk[0]);
  if (pActwk->actfree[7] != 4)
  {
    if (pActwk->actfree[16] == pActwk->actfree[17])
    {
      pActwk->r_no0 += 2;
    }
  }
}
static void tobira4_cl_type1(sprite_status* pActwk) {
  sprite_status* pPlayerwk;
  short d0;
  pPlayerwk = &actwk[0];
  d0 = pActwk->yposi.w.h;
  if (d0 < tp_w(pActwk,20))
  {
    d0 = pPlayerwk->sprvsize;
    d0 += pPlayerwk->yposi.w.h;
    if (d0 >= pActwk->yposi.w.h) return;
    d0 -= pActwk->yposi.w.h;
    d0 *= -1;
    if (d0 < 16) return;
  }
  else
  {
    d0 = -pPlayerwk->sprvsize;
    d0 += pPlayerwk->yposi.w.h;
    if (d0 < pPlayerwk->yposi.w.h) return;
    d0 -= pPlayerwk->yposi.w.h;
    if (d0 < 8) return;
  }
  pActwk->r_no0 += 2;
}
static void tobira4_cl_type2(sprite_status* pActwk) {
  sprite_status* pPlayerwk;
  short d0;
  pPlayerwk = &actwk[0];
  d0 = pActwk->xposi.w.h;
  if (d0 < tp_w(pActwk,14))
  {
    d0 = pPlayerwk->sprhs;
    d0 += pPlayerwk->xposi.w.h;
    if (d0 >= pActwk->xposi.w.h) return;
    d0 -= pActwk->xposi.w.h;
    d0 *= -1;
    if (d0 < 8) return;
  }
  else
  {
    d0 = -pPlayerwk->sprhs;
    d0 += pPlayerwk->xposi.w.h;
    if (d0 < pActwk->xposi.w.h) return;
    d0 -= pActwk->xposi.w.h;
    if (d0 < 8) return;
  }
  pActwk->r_no0 += 2;
}
static void tobira4_chek(sprite_status* pActwk) {
  static void(*const tbl[5])(sprite_status*) =
  {
    &tobira4_cl_type1,
    &tobira4_cl_type1,
    &tobira4_cl_type2,
    &tobira4_cl_type2,
    &tobira4_cl_type2
  };
  tbl[pActwk->actfree[7]](pActwk);
  tp_hitchk(pActwk, &actwk[0]);
}
static void tobira4_clse(sprite_status* pActwk) {
  pActwk->actfree[18] = 255;
  tobira4_cnt(pActwk);
  if (pActwk->actfree[16] == 0)
  {
    pActwk->r_no0 = 2;
  }
  tp_hitchk(pActwk, &actwk[0]);
}
static void tobira4_type1(sprite_status* pActwk) {
  short d0;
  tobira4_sub(pActwk);
  d0 = (unsigned short)pActwk->actfree[16];
  d0 *= -1;
  d0 += tp_w(pActwk,12);
  pActwk->xposi.w.h = d0;
}
static void tobira4_type2(sprite_status* pActwk) {
  short d0;
  tobira4_sub(pActwk);
  d0 = (unsigned short)pActwk->actfree[16];
  d0 += tp_w(pActwk,12);
  pActwk->xposi.w.h = d0;
}
static void tobira4_type3(sprite_status* pActwk) {
  short d0;
  tobira4_sub(pActwk);
  d0 = (unsigned short)pActwk->actfree[16];
  d0 *= -1;
  d0 += tp_w(pActwk,8);
  pActwk->yposi.w.h = d0;
}
static void tobira4_type4(sprite_status* pActwk) {
  short d0;
  tobira4_sub(pActwk);
  d0 = (unsigned short)pActwk->actfree[16];
  d0 += tp_w(pActwk,8);
  pActwk->yposi.w.h = d0;
}
static void tobira4_cnt(sprite_status* pActwk) {
  static void(*const tbl[5])(sprite_status*) =
  {
    &tobira4_type1,
    &tobira4_type2,
    &tobira4_type3,
    &tobira4_type4,
    &tobira4_type3
  };
  tbl[pActwk->actfree[7]](pActwk);
}
static void tobira4_sub(sprite_status* pActwk) {
  if (pActwk->actfree[18])
  {
    if (pActwk->actfree[16] >= 8)
    {
      pActwk->actfree[16] -= 8;
      return;
    }
    pActwk->actfree[16] = 0;
  }
  else
  {
    pActwk->actfree[16] += 8;
    if (pActwk->actfree[16] < pActwk->actfree[17]) return;
    pActwk->actfree[16] = pActwk->actfree[17];
  }
}

/* ---- R4/TOBIRAS4.C ---- */
static void tobiras4_act(sprite_status* pActwk) {
  static void(*const tbl[3])(sprite_status*) =
  {
    &tobiras4_act_init,
    &tobiras4_act_sense,
    &tobiras4_act_down
  };
  tbl[pActwk->r_no0 / 2](pActwk);
}
static void tobiras4_act_init(sprite_status* pActwk) {
  unsigned char* p;
  p = &switchflag[pActwk->userflag.b.h];
  if (*p)
  {
    tp_frameout(pActwk);
    return;
  }
  tp_lset(pActwk,6,pActwk->userflag.b.h); /* retail stores &switchflag[n] */
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sproffset = 17514;
  pActwk->sprvsize = 64;
  pActwk->sprhsize = 64;
  pActwk->sprpri = 3;
  pActwk->sprhs = 64;
}
static void tobiras4_act_sense(sprite_status* pActwk) {
  sprite_status* pNewActwk;
  unsigned char* p;
  short d5, d6;
  p = &switchflag[tp_l(pActwk,6)];
  if (*p == 0)
  {
    tp_hitchk(pActwk, &actwk[0]);
    tp_draw(pActwk);
    tp_frameout_s(pActwk);
    return;
  }
  pActwk->r_no0 += 2;
  pActwk->sprhs = 16;
  pActwk->sprhsize = 16;
  tp_wset(pActwk,0,128);
  tp_lset(pActwk,2,-65536);
  ++pActwk->patno;
  pActwk->xposi.w.h -= 48;
  d6 = 2;
  d5 = pActwk->xposi.w.h;
  do
  {
    if (tp_actwkchk2(pActwk, &pNewActwk) != 0)
    {
      tp_frameout(pActwk);
      return;
    }
    tp_copyact(pNewActwk, pActwk, sizeof(*pActwk));
    d5 += 32;
    pNewActwk->xposi.w.h = d5;
    if (!(d6 & 1))
    {
      tp_lset(pNewActwk,2,tp_l(pNewActwk,2)*(-1));
      ++pNewActwk->patno;
    }
  } while (--d6 >= 0);
  tobiras4_act_disp(pActwk);
}
static void tobiras4_act_down(sprite_status* pActwk) {
  /* Retail R42A $20CFBE: subq.w #1 then bmi to frameout, so the door goes on
     the 129th update, one before the C order (TOBIRAS4.C:143-148; retail
     TT2A row 5466 drops the pieces, 5467 the parent). */
  if (tp_wset(pActwk,0,tp_w(pActwk,0)+-1) < 0)
  {
    tp_frameout(pActwk);
    return;
  }
  /* Retail R42A adds the speed (TOBIRAS4.C line 149 reads "-="): TT2A row
     5339, the parent at speed -$10000 rises 1472 -> 1471, the pieces with
     +$10000 sink. */
  pActwk->yposi.l += tp_l(pActwk,2);
  tobiras4_act_disp(pActwk);
}
static void tobiras4_act_disp(sprite_status* pActwk) {
  tp_hitchk(pActwk, &actwk[0]);
  tp_draw(pActwk);
}

/* ---- R4/WALLS.C ---- */
static unsigned char walls_patno_tbl[9][8] = {
  { 2, 1, 1, 2, 2, 1, 1, 2 },
  { 0, 3, 1, 2, 2, 1, 3, 0 },
  { 3, 0, 0, 3, 3, 0, 0, 3 },
  { 1, 2, 0, 0, 0, 0, 2, 1 },
  { 2, 1, 1, 2, 1, 2, 2, 1 },
  { 0, 3, 2, 0, 2, 0, 0, 3 },
  { 3, 0, 0, 0, 0, 0, 0, 3 },
  { 2, 1, 1, 2, 3, 0, 0, 3 },
  { 1, 2, 1, 1, 1, 1, 2, 1 }
};
static int walls_data_tbl[8] = {
  60, 0,  48, 131072,
  60, 0, 192, -32768
};
static void walls_act(sprite_status* pActwk) {
  if (pActwk->userflag.b.h & 128) {
    walls_opt_check(pActwk);
    return;
  } else if (!pActwk->r_no0) {
    walls_main_init(pActwk);
  }
  walls_main_move(pActwk);
}
static void walls_main_init(sprite_status* pActwk) {
  unsigned char *pOptwk, *pPatno, patnowk;
  int i, j;
  sprite_status* pNewact;
  pActwk->r_no0 += 2;
  tp_wset(pActwk,6,pActwk->xposi.w.h);
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sprhs = 16;
  pActwk->sprhsize = 16;
  pActwk->sprvsize = 16;
  pActwk->sproffset = 17514;
  pActwk->patno = 4;
  tp_wset(pActwk,8,pActwk - actwk);
  tp_wset(pActwk,0,192);
  tp_lset(pActwk,2,-32768);
  pOptwk = &pActwk->actfree[14];
  pPatno = walls_patno_tbl[pActwk->userflag.b.h + 1];
  for (i = 3; i >= 0; --i) {
    for (j = 1; j >= 0; --j) {
      if (tp_actwkchk2(pActwk, &pNewact) != 0) {
        tp_frameout(pActwk);
        return;
      }
      *pOptwk++ = pNewact - actwk;
      pNewact->userflag.b.h = (j - 2) & 255;
      pNewact->yposi.w.h = pActwk->yposi.w.h - 48 + (short)(i * 32);
      pNewact->patno = patnowk = *--pPatno;
      pNewact->sprhsize = pNewact->sprhs = (patnowk + 1) * 16;
      if (j != 0) {
        pNewact->xposi.w.h = pActwk->xposi.w.h + 64 - (short)(patnowk * 16);
      } else {
        pNewact->xposi.w.h = pActwk->xposi.w.h - 64 + (short)(patnowk * 16);
      }
      tp_wset(pNewact,8,pActwk - actwk);
      tp_setactno(pNewact,pActwk->actno);
      /* The pieces (userflag -2/-1) draw poses 0-3 of the parent's table. */
      pool[tp_slot(pNewact)].subtype = pool[tp_slot(pActwk)].subtype;
      pNewact->actflg = pActwk->actflg;
      pNewact->sprpri = pActwk->sprpri;
      pNewact->sprvsize = pActwk->sprvsize;
      pNewact->sproffset = pActwk->sproffset;
    }
  }
  walls_main_move(pActwk);
}
static void walls_main_move(sprite_status* pActwk) {
  unsigned char* pOptwk;
  int i;
  int spdwk;
  sprite_status* pChildact;
  pOptwk = &pActwk->actfree[14];
  spdwk = tp_l(pActwk,2);
  for (i = 3; i >= 0; --i) {
    pChildact = &actwk[*pOptwk++];
    pChildact->xposi.l -= spdwk;
    pChildact->xspeed.w = -(spdwk >> 8);
    pChildact = &actwk[*pOptwk++];
    pChildact->xposi.l += spdwk;
    pChildact->xspeed.w = spdwk >> 8;
  }
  if (tp_wset(pActwk,0,tp_w(pActwk,0)+-1) == 0) {
    tp_wset(pActwk,0,walls_data_tbl[tp_w(pActwk,10) / 4]);
    tp_lset(pActwk,2,walls_data_tbl[tp_w(pActwk,10) / 4 + 1]);
    tp_wset(pActwk,10,tp_w(pActwk,10)+(8));
    tp_wset(pActwk,10,tp_w(pActwk,10)&(31));
  }
  tp_frameout_s00(pActwk, tp_w(pActwk,6));
}
static void walls_opt_check(sprite_status* pActwk) {
  if (actwk[tp_w(pActwk,8)].actno != SCD_OBJ_WALLS) {
    tp_frameout(pActwk);
  } else {
    tp_hitchk(pActwk, &actwk[0]);
    tp_draw(pActwk);
  }
}

/* ---- R4/WALL42.C ---- */
static void wall42_act(sprite_status* pActwk) {
  short d0, d1;
  unsigned char* a1;
  static void(*const tbl[4])(sprite_status*) =
  {
    &wall42_act_init,
    &wall42_act_wait,
    &wall42_act_move,
    &wall42_act_stop
  };
  tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  d0 = pActwk->xposi.w.h & -128;
  d1 = tp_scra_h() - 128 & -128;
  d0 -= d1;
  /* Retail R42A__.MMD $F04E: cmpi.w #640,d0; bls (unsigned), so a wall
     left behind the camera frames out too (the PC decompile's signed test
     kept passed walls alive and shifted later actwkchk slots). */
  if ((unsigned short)d0 > 640)
  {
    a1 = &tp_flagwork[tp_l(pActwk,2)];
    *a1 &= 127;
    tp_frameout_s0(pActwk);
  }
}
static void wall42_act_init(sprite_status* pActwk) {
  short index;
  unsigned char* a1;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 32;
  pActwk->sprvsize = 64;
  pActwk->sproffset = 17514;
  index = tp_cdsts(pActwk);
  index *= 3;
  index += (unsigned short)time_flag;
  a1 = &tp_flagwork[index];
  tp_lset(pActwk,2,index); /* retail stores the byte's address */
  if (!(*a1 & 1))
  {
    *a1 |= 1;
    tp_wset(pActwk,0,60);
    pActwk->r_no0 += 2;
  }
  else
  {
    pActwk->xposi.w.h += 192;
    pActwk->r_no0 += 6;
  }
}
/* Retail R42?__.MMD (Sega CD) differs from the PC WALL42.C decompile here:
   act_wait/act_move decrement $2A first and advance when it reaches 0
   ("addi.w #-1,$2A(a0); bne.s"), so the wall waits 60 updates and moves 384
   (PC: test -1 before the decrement, 62 and 386). act_move writes
   0x8000 >> 8 = 128 to Sonic's ground speed ("move.l #$8000,d0; asr.l #8,d0";
   PC decompile: << 8, i.e. 0). R42A__.MMD offsets $EFF4-$F02C. */
static void wall42_act_wait(sprite_status* pActwk) {
  tp_wset(pActwk,0,tp_w(pActwk,0)+-1);
  if (tp_w(pActwk,0) == 0)
  {
    tp_wset(pActwk,0,384);
    pActwk->r_no0 += 2;
  }
  wall42_act_stop(pActwk);
}
static void wall42_act_move(sprite_status* pActwk) {
  int d0;
  if (tp_hitchk(pActwk, &actwk[0]))
  {
    d0 = 32768;
    d0 >>= 8;
    actwk[0].mspeed.w = d0 & 65535;
  }
  pActwk->xposi.l += 32768;
  tp_wset(pActwk,0,tp_w(pActwk,0)+-1);
  if (tp_w(pActwk,0) == 0)
  {
    pActwk->r_no0 += 2;
  }
}
static void wall42_act_stop(sprite_status* pActwk) {
  tp_hitchk(pActwk, &actwk[0]);
}

/* ---- R4/TEKKYU.C ---- */
static void(*const tekkyu_act_tbl[2])(sprite_status*) = {
  &tekkyu_act_init,
  &tekkyu_act_move
};
static void(*const tekkyu_opt_act_tbl[2])(sprite_status*) = {
  &tekkyu_opt_act_init,
  &tekkyu_opt_act_move
};
static void tekkyu_act(sprite_status* pActwk) {
  if (pActwk->userflag.b.h & 128) {
    tekkyu_opt(pActwk);
  } else {
    tekkyu_main(pActwk);
  }
}
static void tekkyu_main(sprite_status* pActwk) {
  tekkyu_act_tbl[pActwk->r_no0 / 2](pActwk);
  tp_draw(pActwk);
  tp_frameout_s(pActwk);
}
static void tekkyu_act_init(sprite_status* pActwk) {
  sprite_status* pNewact;
  unsigned pActidx;
  int i;
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  pActwk->sprpri = 3;
  pActwk->sprhsize = 8;
  pActwk->sprvsize = 8;
  pActwk->sproffset = 872;
  if (pActwk->userflag.b.h == 0) {
    tp_wset(pActwk,2,256);
  } else {
    tp_wset(pActwk,2,-256);
  }
  pActidx = 4; /* ((short*)pActwk)[25..30] */
  for (i = 0; i < 6; ++i) {
    if (tp_actwkchk(&pNewact) != 0) {
      tp_frameout(pActwk);
      return;
    }
    tp_wset(pActwk,pActidx,pNewact - actwk);pActidx += 2;
    tp_setactno(pNewact,pActwk->actno);
    pNewact->userflag.b.h = -1;
    pNewact->sprhsize = 8;
    pNewact->sprvsize = 8;
    tp_wset(pNewact,20,pActwk - actwk);
  }
  pNewact->userflag.b.h = -2;
  tekkyu_act_move(pActwk);
}
static void tekkyu_act_move(sprite_status* pActwk) {
  int_union ldSin, ldCos;
  int sinsv1, sinsv2, cossv1, cossv2;
  sprite_status* pSubact;
  tp_wset(pActwk,0,tp_w(pActwk,0)+(tp_w(pActwk,2)));
  sinset(pActwk->actfree[1], &ldSin.w.h, &ldCos.w.h);
  ldSin.w.l = ldCos.w.l = 0;
  ldSin.l >>= 2;
  ldCos.l >>= 2;
  sinsv1 = ldSin.l;
  cossv1 = ldCos.l;
  ldSin.l >>= 1;
  ldCos.l >>= 1;
  sinsv2 = ldSin.l;
  cossv2 = ldCos.l;
  ldSin.l >>= 1;
  ldCos.l >>= 1;
  pSubact = &actwk[tp_w(pActwk,4)];
  tp_lset(pSubact,4,pActwk->yposi.l + ldSin.l);
  tp_lset(pSubact,0,pActwk->xposi.l + ldCos.l);
  pSubact = &actwk[tp_w(pActwk,6)];
  tp_lset(pSubact,4,pActwk->yposi.l + sinsv2);
  tp_lset(pSubact,0,pActwk->xposi.l + cossv2);
  pSubact = &actwk[tp_w(pActwk,8)];
  tp_lset(pSubact,4,pActwk->yposi.l + ldSin.l + sinsv2);
  tp_lset(pSubact,0,pActwk->xposi.l + ldCos.l + cossv2);
  pSubact = &actwk[tp_w(pActwk,10)];
  tp_lset(pSubact,4,pActwk->yposi.l + sinsv1);
  tp_lset(pSubact,0,pActwk->xposi.l + cossv1);
  pSubact = &actwk[tp_w(pActwk,12)];
  tp_lset(pSubact,4,pActwk->yposi.l + ldSin.l + sinsv1);
  tp_lset(pSubact,0,pActwk->xposi.l + ldCos.l + cossv1);
  pSubact = &actwk[tp_w(pActwk,14)];
  tp_lset(pSubact,4,pActwk->yposi.l + sinsv2 + sinsv1);
  tp_lset(pSubact,0,pActwk->xposi.l + cossv2 + cossv1);
}
static void tekkyu_opt(sprite_status* pActwk) {
  tekkyu_opt_act_tbl[pActwk->r_no0 / 2](pActwk);
  if (actwk[tp_w(pActwk,20)].actno != SCD_OBJ_TEKKYU) {
    tp_frameout(pActwk);
  } else {
    tp_draw(pActwk);
  }
}
static void tekkyu_opt_act_init(sprite_status* pActwk) {
  pActwk->r_no0 += 2;
  pActwk->actflg |= 4;
  if (pActwk->userflag.b.h == -1) {
    pActwk->sprpri = 3;
    pActwk->sproffset = 872;
  }
  else {
    pActwk->sprpri = 2;
    pActwk->sproffset = 880;
    pActwk->colino = 169;
  }
  tekkyu_opt_act_move(pActwk);
}
static void tekkyu_opt_act_move(sprite_status* pActwk) {
  pActwk->xposi.w.h = tp_w(pActwk,2);
  pActwk->yposi.w.h = tp_w(pActwk,6);
}

/* ---- R4/TEKKYU4.C ---- */
static void tekkyu4_act(sprite_status* pActwk) {
  sprite_status* pMainactwk;
  static void(*const tekkyu4_acttbl[2])(sprite_status*) = {
    &tekkyu4init,
    &tekkyu4move
  };
  if (tp_w(pActwk,20)) {
    pMainactwk = &actwk[tp_w(pActwk,20)];
    if (pMainactwk->actno != SCD_OBJ_TEKKYU4) {
      tp_frameout(pActwk);
      return;
    }
  }
  tekkyu4_acttbl[pActwk->r_no0 / 2](pActwk);
}
static void tekkyu4init(sprite_status* pActwk) {
  sprite_status *pNewactwk1, *pNewactwk2, *pNewactwk3;
  short wD0;
  tp_wset(pActwk,10,pActwk->xposi.w.h);
  if (tp_actwkchk(&pNewactwk3) != 0) {
    tp_frameout(pActwk);
    return;
  }
  tp_setactno(pNewactwk3,pActwk->actno);
  pNewactwk3->r_no0 = 2;
  tp_wset(pNewactwk3,20,pActwk - actwk);
  if (tp_actwkchk(&pNewactwk2) != 0) {
    tp_frameout(pActwk);
    return;
  }
  tp_setactno(pNewactwk2,pActwk->actno);
  pNewactwk2->r_no0 = 2;
  tp_wset(pNewactwk2,20,pActwk - actwk);
  if (tp_actwkchk(&pNewactwk1) != 0) {
    tp_frameout(pActwk);
    return;
  }
  tp_setactno(pNewactwk1,pActwk->actno);
  pNewactwk1->r_no0 = 2;
  tp_wset(pNewactwk1,20,pActwk - actwk);
  wD0 = -2048;
  if (pActwk->userflag.b.h & 128) wD0 *= -1;
  tp_wset(pNewactwk1,4,(int)wD0);
  tp_wset(pNewactwk2,4,wD0 * 2);
  tp_wset(pNewactwk3,4,wD0 * 3);
  tp_wset(pActwk,6,256);
  if (pActwk->userflag.b.h & 128) tp_wset(pActwk,6,tp_w(pActwk,6)*(-1));
  if ((wD0 = pActwk->userflag.b.h) & 128) wD0 *= -1;
  tp_wset(pActwk,8,wD0 & 127);
  pActwk->sprpri = 1;
  pNewactwk1->sprpri = 2;
  pNewactwk2->sprpri = 3;
  pNewactwk3->sprpri = 4;
  tekkyu4_act_init_sub(pActwk, pActwk);
  tekkyu4_act_init_sub(pActwk, pNewactwk1);
  tekkyu4_act_init_sub(pActwk, pNewactwk2);
  tekkyu4_act_init_sub(pActwk, pNewactwk3);
}
static void tekkyu4_act_init_sub(sprite_status* pActwk, sprite_status* pNewactwk) {
  pNewactwk->actflg |= 4;
  pNewactwk->colino = 169;
  pNewactwk->sprhs = 16;
  pNewactwk->sprhsize = 16;
  pNewactwk->sprvsize = 16;
  pNewactwk->sproffset = 880;
  pNewactwk->r_no0 = 2;
  tp_wset(pNewactwk,0,pActwk->xposi.w.h);
  tp_wset(pNewactwk,2,pActwk->yposi.w.h);
  tp_wset(pNewactwk,6,tp_w(pActwk,6));
  tp_wset(pNewactwk,8,tp_w(pActwk,8));
}
static void tekkyu4move(sprite_status* pActwk) {
  unsigned short wD0, wD1;
  tp_wset(pActwk,4,tp_wu(pActwk,4)+(tp_wu(pActwk,6)));
  sinset(tp_w(pActwk,4) >> 8, (short*)&wD0, (short*)&wD1);
  wD0 = (short)wD0 >> tp_wu(pActwk,8);
  wD1 = (short)wD1 >> tp_wu(pActwk,8);
  pActwk->xposi.w.h = tp_w(pActwk,0) + (short)wD1;
  pActwk->yposi.w.h = tp_w(pActwk,2) + (short)wD0;
  tp_draw(pActwk);
  if (!tp_w(pActwk,20)) tp_frameout_s(pActwk);
}

/* ---- R4/TEKKYU1.C ---- */
static void tekkyu1_act(sprite_status* pActwk) {
  if (pActwk->r_no0 == 0) {
    pActwk->r_no0 += 2;
    pActwk->actflg |= 4;
    pActwk->sprpri = 3;
    pActwk->colino = 169;
    pActwk->sprhs = 16;
    pActwk->sprhsize = 16;
    pActwk->sprvsize = 16;
    pActwk->sproffset = 880;
  }
  tp_draw(pActwk);
  tp_frameout_s(pActwk);
}

/* ACT41A-43C act_tbl dispatch for the ported R4 actors. */
static int tp_step(unsigned i){
    sprite_status *o=&actwk[i+1];
    switch(pool[i].type){
    case SCD_OBJ_UDBLK4:udblk4_act(o);break;
    case SCD_OBJ_LRBLK4:lrblk4_act(o);break;
    case SCD_OBJ_RBLK4:rblk4_act(o);break;
    case SCD_OBJ_ESCAL4:escal4_act(o);break;
    case SCD_OBJ_BRUNKO4:brunko4_act(o);break;
    case SCD_OBJ_RENKETU4:renketu4_act(o);break;
    case SCD_OBJ_KUZURE4:kuzure4_act(o);break;
    case SCD_OBJ_DAID4:daid4_act(o);break;
    case SCD_OBJ_BANEIWA:baneiwa_act(o);break;
    case SCD_OBJ_SW4:sw4_act(o);break;
    case SCD_OBJ_SWBLKR4:swblk4_swblkr4(o);break;
    case SCD_OBJ_SWITCHR4:swblk4_switchr4(o);break;
    case SCD_OBJ_SWGUN4:swgun4_act(o);break;
    case SCD_OBJ_RING4:swgun4_ring4(o);break;
    case SCD_OBJ_TENSU4:swgun4_tensu4(o);break;
    case SCD_OBJ_TOBIRA4:tobira4_act(o);break;
    case SCD_OBJ_TOBIRAS4:tobiras4_act(o);break;
    case SCD_OBJ_WALLS:walls_act(o);break;
    case SCD_OBJ_WALL42:wall42_act(o);break;
    case SCD_OBJ_TEKKYU:tekkyu_act(o);break;
    case SCD_OBJ_TEKKYU4:tekkyu4_act(o);break;
    case SCD_OBJ_TEKKYU1:tekkyu1_act(o);break;
    default:return 0;
    }
    return 1;
}
