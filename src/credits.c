/* "Thank You" ending screen: native port of TITLE/THANKS (see credits.h).
   Function names follow the PC reconstruction so each routine can be read
   against its source; tools/test_credits.py compares every frame. */
#include "credits.h"
#include <string.h>
#include "credits_tables.h"

typedef scd_credits_actor actor;

/* int_union.w.h / .w.l access on the 32-bit PC fields. */
#define HI(v) ((int16_t)((uint32_t)(v) >> 16))
static int32_t with_hi(int32_t v, int h) { return (int32_t)(((uint32_t)(uint16_t)h << 16) | ((uint32_t)v & 0xFFFFu)); }
static int32_t add32(int32_t a, int32_t b) { return (int32_t)((uint32_t)a + (uint32_t)b); }
#define SET_HI(field, h) ((field) = with_hi((field), (h)))
#define WRAP_X(a) SET_HI((a)->x, HI((a)->x) & 511)      /* XPOSI.w.h &= 511 */
#define TRIM_X(a) ((a)->x &= 0x1FFFFFF)                 /* XPOSI.l &= 33554431 */
/* sonic_ctrl, emie_ctrl and metals_ctrl end with XPOSI.w.h &= 511 on the PC; THANKS_M.MMD's
   ($FF4706, $FF4C46, $FF52A8) jump into the routine and never wrap there. */
#define CTRL_WRAP_X(st, a) do { if (!((st)->ending_type & SCD_CREDITS_SEGA_CD)) WRAP_X(a); } while (0)

/* ((short*)pActwk)[31] and ((char*)pActwk)[62]: PC byte 62 is free[4]. */
static int16_t pit_get(const actor *a) { return (int16_t)(a->free[4] | a->free[5] << 8); }
static void pit_set(actor *a, int v) { a->free[4] = (uint8_t)v; a->free[5] = (uint8_t)((unsigned)v >> 8); }
#define HEART_TIMER(a) (*(int8_t *)&(a)->free[4])

static int16_t first_timer(unsigned pattern) { return scd_credits_frames[scd_credits_patterns[pattern].first].timer; }
static void anim(actor *a, unsigned pattern) { a->pattern = (uint8_t)pattern; a->spr_timer = first_timer(pattern); a->pat_no = 0; }
#define PAT(name) SCD_CREDITS_PAT_##name

/* ETC_M.C */
int32_t scd_credits_random(scd_credits *st)
{
    uint32_t seed = st->ranum ? (uint32_t)st->ranum : 711800410u;
    uint32_t product = seed * 41u;
    uint16_t sum = (uint16_t)((product >> 16) + (product & 0xFFFFu));
    if (st->ending_type & SCD_CREDITS_SEGA_CD) {
        /* THANKS_M.MMD $FF3CF6: ranum keeps the product's low word under the sum;
           d0 returns the seed's high word over the sum. */
        st->ranum = (int32_t)((uint32_t)sum << 16 | (product & 0xFFFFu));
        return (int32_t)((seed & 0xFFFF0000u) | sum);
    }
    st->ranum = (int32_t)((uint32_t)sum << 16 | sum);
    return (int32_t)product;
}
/* random() & 32767, as the callers take it (ld0.w.l, 0..32767). */
static int rnd(scd_credits *st) { return scd_credits_random(st) & 32767; }

static int16_t sign16(int16_t d3)
{
    int16_t d4;
    d3 &= 511;
    d4 = d3;
    if (d3 & 128) d4 = (int16_t)~d4;
    d4 = scd_credits_sin[d4 & 127];
    if (d3 & 256) d4 = (int16_t)-d4;
    return d4;
}

/* ACT.C */
static int get_actwk(scd_credits *st)
{
    for (int i = 3; i <= 63; i++)
        if (!st->actors[i].act_no) return i;
    return -1;
}

static void soundset(scd_credits *st, uint16_t id)
{
    if (id == 171) return;
    if (st->sound_count < SCD_CREDITS_SOUNDS) st->sounds[st->sound_count++] = id;
}

static void eas_prset(scd_credits *st, int x, int y, unsigned index, unsigned link, unsigned flags)
{
    if (link >= SCD_CREDITS_SPRITES) { st->sprite_overflow++; return; }
    st->sprites[link] = (scd_credits_sprite){(int16_t)x, (int16_t)y, (uint16_t)index, (uint16_t)flags};
}

static void set_grid(scd_credits *st, int plane, int x, int y, int tile)
{
    if ((unsigned)x < SCD_CREDITS_PLANE_W && (unsigned)y < SCD_CREDITS_PLANE_H)
        st->plane[plane][y * SCD_CREDITS_PLANE_W + x] = (uint16_t)tile;
}

/* SPRMOVE.C helpers */
static void hbt_move(actor *a)
{
    a->x = add32(a->x, add32(a->x_speed, a->x_accel));
    a->y = add32(a->y, add32(a->y_speed, a->y_accel));
    a->x_accel = add32(a->x_accel, a->x_offset);
    a->y_accel = add32(a->y_accel, a->y_offset);
}

static void step(actor *a)
{
    a->x = add32(a->x, a->x_speed);
    a->y = add32(a->y, a->y_speed);
}

static int chk_sonicposi(const actor *a, const actor *other, int16_t *d5, int16_t *d6)
{
    *d5 = (int16_t)(HI(other->x) - HI(a->x));
    if (*d5 < 0) { *d5 = (int16_t)-*d5; *d6 = 1; return -1; }
    *d6 = 0;
    return 0;
}

static int myposichk(const actor *a)
{
    int16_t x = HI(a->x);
    if (x == 384) return -1;
    if (HI(a->x_speed) >= 0) {
        if (x < 264) return 0;
        if (x < 304) return -1;
        if (x < 448) return 0;
        if (x < 496) return -1;
        return 0;
    }
    if (x < 40) return -1;
    if (x < 304) return 0;
    if (x < 352) return -1;
    if (x > 496) return -1;
    return 0;
}

static int centerchk(actor *a)
{
    TRIM_X(a);
    int16_t x = HI(a->x);
    if (!(a->spr_flg & 128)) return x >= 112 && x <= 120 ? -1 : 0;
    return x >= 168 && x <= 176 ? -1 : 0;
}

static int dsplaychk(actor *a)
{
    TRIM_X(a);
    return HI(a->x) <= 304 ? 0 : -1;
}

static void waitmode(actor *a)
{
    hbt_move(a);
    WRAP_X(a);
    if (HI(a->x) >= 336 && HI(a->x) <= 352) {
        a->x_speed = a->y_speed = 0;
        a->x_offset = 0; a->x_accel = 0;
        a->y_offset = 0; a->y_accel = 0;
    }
    if (!(a->spr_flg & 4)) {
        a->spr_flg &= 251;
        a->exe_no = 1;
    }
}

static void escape_chk(actor *a)
{
    WRAP_X(a);
    int16_t x = HI(a->x);
    if (a->x_speed >= 0) {
        if (x >= 304 && x <= 368) { a->spr_flg |= 16; return; }
    } else if (x >= 448 && x <= 480) {
        a->spr_flg |= 16;
        return;
    }
    step(a);
}

static void pit_in(actor *a)
{
    SET_HI(a->x, 390);
    if (pit_get(a) < 2) {
        pit_set(a, pit_get(a) - 1);
        SET_HI(a->x, a->x_speed >= 0 ? 400 : 368);
        a->exe_no = 2;
    } else {
        pit_set(a, pit_get(a) - 1);
    }
}

static void m_sndchk(actor *a)
{
    if (a->free[2]) return;
    if (a->x_speed >= 0) {
        if (HI(a->x) >= 6) return;
    } else if (HI(a->x) < 304 || HI(a->x) > 312) {
        return;
    }
    a->free[2] = 1;
}

static int killchk(const actor *a)
{
    int16_t x = HI(a->x), y = HI(a->y);
    return x < -31 || x >= 336 || y < -4 || y >= 224 ? -1 : 0;
}

static void sinhmove(scd_credits *st, actor *a)
{
    SET_HI(a->y, HI(a->y) - a->y_offset);
    int32_t product = (int32_t)sign16(a->sin_cnt) * a->y_wide;
    int16_t offset = (int16_t)(product >> 8);
    a->y_offset = offset;
    SET_HI(a->y, HI(a->y) + offset);
    a->sin_cnt = (int16_t)(a->sin_cnt + (int16_t)(rnd(st) % a->x_wide));
    if (a->sin_cnt >= 511) a->sin_cnt -= 511;
    step(a);
}

static void sinvmove(scd_credits *st, actor *a)
{
    SET_HI(a->x, HI(a->x) - a->x_offset);
    int32_t product = (int32_t)((uint32_t)(int32_t)sign16(a->sin_cnt) * (uint32_t)(int32_t)a->x_wide);
    int16_t offset = (int16_t)(product >> 8);
    a->x_offset = offset;
    SET_HI(a->x, HI(a->x) + offset);
    a->sin_cnt = (int16_t)(a->sin_cnt + (int16_t)(rnd(st) % a->y_wide));
    if (a->sin_cnt >= 511) a->sin_cnt -= 511;
    step(a);
}

static void spawn_heart(scd_credits *st, int set_heart_tm)
{
    int slot = get_actwk(st);
    if (slot < 0) return;
    if (set_heart_tm) st->heart_tm = 1;
    st->actors[slot].act_no = 7;
}

/* Heart spawn countdown in free[4] (emmykiss, emmyjump). */
static void heart_countdown(scd_credits *st, actor *a)
{
    HEART_TIMER(a)--;
    if (HEART_TIMER(a) < 0) {
        int slot = get_actwk(st);
        if (slot >= 0) { st->actors[slot].act_no = 7; HEART_TIMER(a) = 16; }
    }
}

#define SONIC (&st->actors[0])
#define EMMY (&st->actors[1])
#define METAL (&st->actors[2])

/* Sonic (ACT_NO 1) */
static void sonicinit(scd_credits *st, actor *a)
{
    scd_credits_random(st);   /* result discarded: the PC forces the right-hand start */
    SET_HI(a->x, 328);
    a->x_speed = -196608;
    a->spr_flg |= 128;
    SET_HI(a->y, 140);
    a->y_speed = 0;
    a->x_offset = a->y_offset = 0;
    a->x_accel = a->y_accel = 0;
    a->cgbase = 25127;
    a->free[0] = 1;
    anim(a, PAT(s_run_map));
    a->tm_cnt = (int16_t)(rnd(st) % 128 + 128);
    a->exe_no = 2;
}

static void s_runset(scd_credits *st, actor *a)
{
    TRIM_X(a);
    a->x_speed = 196608;
    if (a->spr_flg & 128) a->x_speed = -a->x_speed;
    a->y_speed = 0;
    a->x_offset = a->y_offset = 0;
    a->x_accel = a->y_accel = 0;
    anim(a, PAT(s_run_map));
    a->tm_cnt = (int16_t)(rnd(st) % 256 + 64);
    METAL->act_no = 3;
    a->exe_no = 2;
}

static int s_metalchk(scd_credits *st, actor *a)
{
    actor *m = METAL;
    if (m->exe_no < 2 || m->exe_no > 4) return 0;
    WRAP_X(a);
    WRAP_X(m);
    if (a->x_speed < 0) { if (m->x_speed < 0) return 0; }
    else if (m->x_speed >= 0) return 0;
    int16_t d5 = (int16_t)(HI(m->x) - HI(a->x));
    if (d5 < 0) d5 = (int16_t)-d5;
    return d5 > 8 ? 0 : -1;
}

static void sonicrun(scd_credits *st, actor *a)
{
    step(a);
    if (a->spr_flg & 4) { a->exe_no = 11; return; }
    if (HI(a->x) >= 376 && HI(a->x) <= 392) {
        pit_set(a, 128);
        a->exe_no = 12;
        return;
    }
    scd_credits_random(st);   /* % 1536, overwritten by the next draw */
    if (rnd(st) % 512 == 0) { a->exe_no = 9; return; }
    if (s_metalchk(st, a)) a->exe_no = 3;
    if (--a->tm_cnt <= 0 && centerchk(a)) a->exe_no = 3;
}

static void s_turnset(scd_credits *st, actor *a)
{
    TRIM_X(a);
    if (a->x_speed < 0) { a->x_offset = 10240; a->spr_flg &= 127; }
    else { a->x_offset = -10240; a->spr_flg |= 128; }
    anim(a, PAT(s_stop_map));
    if (dsplaychk(a) == 0) soundset(st, 144);
    a->exe_no = 4;
}

static void sonicturn(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    hbt_move(a);
    if (a->pat_no < 5) return;
    if (METAL->exe_no == 2) { a->exe_no = 1; return; }
    if (myposichk(a)) { a->exe_no = 9; return; }
    chk_sonicposi(a, METAL, &d5, &d6);
    a->exe_no = d5 <= 24 ? 9 : 5;
}

static void s_standset(scd_credits *st, actor *a)
{
    a->x_speed = 0;
    anim(a, PAT(s_stand1_map));
    a->tm_cnt = 127;
    a->free[3] = 0;
    EMMY->act_no = 2;
    a->exe_no = 6;
}

static void sonicstand(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    chk_sonicposi(a, METAL, &d5, &d6);
    if (--a->tm_cnt >= 0) return;
    if (a->free[3]) { EMMY->spr_flg &= 251; a->exe_no = 7; }
    a->pattern = PAT(s_stand2_map);   /* PAT_NO kept */
    a->spr_timer = first_timer(PAT(s_stand2_map));
    a->tm_cnt = 96;
    a->free[3] = 1;
}

static void s_waitset(scd_credits *st, actor *a)
{
    TRIM_X(a);
    a->free[3] = 0;
    anim(a, PAT(s_wait_map));
    a->tm_cnt = (int16_t)(rnd(st) % 127 + 127);
    a->exe_no = 8;
}

static void sonicwait(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    actor *m = METAL;
    WRAP_X(m);
    if (chk_sonicposi(a, m, &d5, &d6)) a->spr_flg |= 128;
    else a->spr_flg &= 127;
    m->spr_flg &= 251;
    if (d5 > 8) { if (--a->tm_cnt <= 0) a->exe_no = 9; }
    else a->exe_no = 1;
}

static void s_ballset(scd_credits *st, actor *a)
{
    TRIM_X(a);
    a->x_speed = 0x20000;
    if (a->spr_flg & 128) a->x_speed = -a->x_speed;
    a->y_speed = -393216;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 16384; a->y_accel = 0;
    anim(a, PAT(s_ball_map));
    if (dsplaychk(a) == 0) soundset(st, 146);
    a->exe_no = 10;
}

static void sonicball(scd_credits *st, actor *a)
{
    (void)st;
    hbt_move(a);
    if (HI(a->y) >= 140) { a->y_accel = 0; a->exe_no = 1; }
}

static void sonicexit(scd_credits *st, actor *a)
{
    actor *e = EMMY, *m = METAL;
    waitmode(a);
    if (!st->animal_flg || a->x_speed) return;
    if (e->exe_no && (e->exe_no != 13 || e->x_speed)) return;
    if (m->exe_no && (m->exe_no != 13 || m->x_speed)) return;
    a->spr_flg &= 127;
    anim(a, PAT(s_run_map));
    a->free[1] = 0;
    a->tm_cnt = 96;
    a->exe_no = 13;
}

static void sonicpit(scd_credits *st, actor *a) { (void)st; pit_in(a); }

static void sonicesc(scd_credits *st, actor *a)
{
    if (a->free[1]) { escape_chk(a); return; }
    if (--a->tm_cnt > 0) return;
    SET_HI(a->x, 448);
    a->x_speed = 196608;
    a->y_speed = 0;
    st->animal_flg = 2;
    st->actset_tm[0] = 1800;
    for (int i = 1; i < 7; i++) st->actset_tm[i] = 0;
    st->actset_tm[7] = 1800;
    a->spr_flg &= 251;
    EMMY->spr_flg &= 251;
    METAL->spr_flg &= 251;
    a->free[1] = 1;
}

/* Amy (ACT_NO 2) */
static void emmy_exeset(scd_credits *st, actor *a, actor *sonic)
{
    int16_t d5 = 0, d6 = 0;
    if (a->exe_no != 2) return;
    if (!sonic->act_no) { a->exe_no = 15; return; }
    chk_sonicposi(a, sonic, &d5, &d6);
    if (d5 <= 40 && sonic->exe_no >= 5 && sonic->exe_no < 9) { a->exe_no = 5; return; }
    if (rnd(st) % 256 == 0) {
        if (HI(a->x) == 384) SET_HI(a->x, 394);
        chk_sonicposi(a, sonic, &d5, &d6);
        if (d5 >= 40 && myposichk(a) == 0) { a->tm_cnt = 64; a->exe_no = 11; return; }
    }
    if (d6 != (a->x_speed < 0 ? 1 : 0)) a->exe_no = 9;
}

static void emmyinit(scd_credits *st, actor *a)
{
    (void)st;
    SET_HI(a->x, -10);
    SET_HI(a->y, 141);
    a->x_speed = 147456;
    a->y_speed = 0;
    a->cgbase = 967;
    a->free[0] = 1;
    a->y_accel = 0;
    anim(a, PAT(erun_map));
    a->exe_no = 2;
}

static void e_runinit(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    TRIM_X(a);
    a->x_speed = 147456;
    a->y_speed = 0;
    if (chk_sonicposi(a, SONIC, &d5, &d6)) { a->x_speed = -a->x_speed; a->spr_flg |= 128; }
    else a->spr_flg &= 127;
    a->cgbase = 967;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    anim(a, PAT(erun_map));
    a->exe_no = 2;
}

static void emmymove(scd_credits *st, actor *a)
{
    (void)st;
    hbt_move(a);
    while (HI(a->x) == 384 && (a->x_speed || a->x_accel || a->x_offset)) hbt_move(a);
    if (a->spr_flg & 4) a->exe_no = 13;
}

static void e_kissset(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    TRIM_X(a);
    SET_HI(a->y, 141);
    a->x_speed = 0;
    a->y_speed = -196608;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 16384; a->y_accel = 0;
    anim(a, PAT(ekiss_map));
    if (chk_sonicposi(a, SONIC, &d5, &d6)) a->spr_flg |= 128;
    else a->spr_flg &= 127;
    a->free[4] = 12;
    spawn_heart(st, 1);
    a->exe_no = 4;
}

static void emmykiss(scd_credits *st, actor *a)
{
    hbt_move(a);
    if (HI(a->y) >= 140) a->y_accel = 0;
    if (--a->tm_cnt <= 0 && a->y_accel == 0) {
        SET_HI(a->y, 139);
        a->exe_no = 1;
        if (st->poseno == 2) {
            SONIC->spr_flg &= 251;
            METAL->spr_flg &= 251;
            st->poseno = 0;
        }
    }
    heart_countdown(st, a);
}

static void e_jumpset(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    TRIM_X(a);
    SET_HI(a->y, 141);
    a->x_speed = 98304;
    a->y_speed = -196608;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 16384; a->y_accel = 0;
    anim(a, PAT(ejump_map));
    if (chk_sonicposi(a, SONIC, &d5, &d6)) { a->x_speed = -a->x_speed; a->spr_flg |= 128; }
    else a->spr_flg &= 127;
    if (st->ending_type & SCD_CREDITS_SEGA_CD) {
        /* THANKS_M.MMD $FF4F24 tests Sonic's flip (a6), not Amy's: the speed drops to
           1 only when both face the same way, else 1.5 stays. */
        if (a->spr_flg & 128) { if (SONIC->spr_flg & 128) a->x_speed = -65536; }
        else if (!(SONIC->spr_flg & 128)) a->x_speed = 65536;
    } else a->x_speed = a->spr_flg & 128 ? -65536 : 65536;
    a->tm_cnt = 20;
    a->free[4] = 16;
    spawn_heart(st, 1);
    a->exe_no = 6;
}

static void emmyjump(scd_credits *st, actor *a)
{
    hbt_move(a);
    if (HI(a->y) >= 140) a->y_accel = 0;
    if (--a->tm_cnt <= 0 && a->y_accel == 0) { SET_HI(a->y, 139); a->exe_no = 7; }
    heart_countdown(st, a);
}

static void follow_sonic(actor *a, const actor *sonic, int flip_source)
{
    if (flip_source & 128) {
        a->spr_flg |= 128;
        a->x = sonic->x;
        SET_HI(a->x, HI(a->x) + 16);
        a->x_speed = -a->x_speed;
    } else {
        a->spr_flg &= 127;
        a->x = sonic->x;
        SET_HI(a->x, HI(a->x) - 16);
    }
}

static void e_catchset(scd_credits *st, actor *a)
{
    TRIM_X(a);
    SET_HI(a->y, 141);
    /* THANKS_M.MMD $FF4FC4 follows Sonic's flip (a6); the PC tests Amy's own. */
    follow_sonic(a, SONIC, st->ending_type & SCD_CREDITS_SEGA_CD ? SONIC->spr_flg : a->spr_flg);
    a->x_speed = a->y_speed = 0;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    anim(a, PAT(ecatch_map));
    a->free[0] = 0;
    a->free[4] = 12;
    spawn_heart(st, 1);
    a->exe_no = 8;
}

static void emmy_catch(scd_credits *st, actor *a)
{
    actor *sonic = SONIC;
    follow_sonic(a, sonic, sonic->spr_flg);
    if (sonic->exe_no >= 5 && sonic->exe_no < 9) {
        HEART_TIMER(a)--;
        if (HEART_TIMER(a) >= 0) return;
        int slot = get_actwk(st);
        if (slot >= 0) { st->actors[slot].act_no = 7; HEART_TIMER(a) = 16; return; }
    }
    a->tm_cnt = 40;
    a->exe_no = 3;
    a->free[0] = 1;
}

static void e_turnset(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    SET_HI(a->y, 141);
    a->x_speed = 147456;
    a->y_speed = 0;
    a->x_offset = -8192; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    anim(a, PAT(erun_map));
    a->spr_flg |= 128;
    if (chk_sonicposi(a, SONIC, &d5, &d6) == 0) {
        a->spr_flg &= 127;
        a->x_offset = (int16_t)-a->x_offset;
        a->x_speed = -a->x_speed;
    }
    a->exe_no = 10;
}

static void emmyturn(scd_credits *st, actor *a)
{
    hbt_move(a);
    if ((int16_t)(HI(a->x_speed) + HI(a->x_accel)) == 0) {
        a->tm_cnt = st->poseno == 2 ? 80 : 20;
        a->exe_no = 3;
    }
}

static void e_standset(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    TRIM_X(a);
    SET_HI(a->y, 141);
    a->x_speed = a->y_speed = 0;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    anim(a, rnd(st) % 2 == 0 ? PAT(estand_map) : PAT(estand2_map));
    if (chk_sonicposi(a, SONIC, &d5, &d6)) a->spr_flg |= 128;
    else a->spr_flg &= 127;
    a->free[4] = 16;
    spawn_heart(st, 1);
    a->exe_no = 12;
}

static void emmymoji(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    WRAP_X(a);
    WRAP_X(SONIC);
    if (chk_sonicposi(a, SONIC, &d5, &d6)) a->spr_flg |= 128;
    else a->spr_flg &= 127;
    if (--a->tm_cnt <= 0) a->exe_no = 1;
}

static void emmyexit(scd_credits *st, actor *a)
{
    waitmode(a);
    if (st->animal_flg != 2) return;
    SET_HI(a->x, 448);
    a->x_speed = 147456;
    a->y_speed = 0;
    a->spr_flg &= 127;
    anim(a, PAT(erun_map));
    a->exe_no = 15;
}

static void emmypose(scd_credits *st, actor *a)
{
    step(a);
    if (SONIC->x_speed == 0 && METAL->x_speed == 0 && centerchk(a)) a->exe_no = 9;
}

static void emmyesc(scd_credits *st, actor *a) { (void)st; escape_chk(a); }

/* Metal Sonic (ACT_NO 3) */
static void metalsinit(scd_credits *st, actor *a)
{
    SET_HI(a->x, 336);
    SET_HI(a->y, 132);
    a->x_speed = -237568;
    a->y_speed = 0;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    a->cgbase = 25785;
    a->free[0] = 3;
    a->spr_flg |= 128;
    anim(a, PAT(m_fly1_map));
    a->tm_cnt = (int16_t)(rnd(st) % 128 + 128);
    a->exe_no = 2;
}

static void m_flyset(scd_credits *st, actor *a)
{
    SET_HI(a->y, 132);
    a->x_speed = 237568;
    a->y_speed = 0;
    if (a->spr_flg & 128) a->x_speed = -a->x_speed;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    a->cgbase = 25785;
    a->free[0] = 3;
    anim(a, PAT(m_fly1_map));
    a->tm_cnt = (int16_t)(rnd(st) % 192 + 128);
    if (dsplaychk(a) == 0) a->free[2] = 1;
    a->exe_no = 2;
}

static void metalsfly(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    step(a);
    m_sndchk(a);
    if (a->spr_flg & 4) { a->free[2] = 0; a->exe_no = 13; return; }
    if (!SONIC->act_no) { a->free[2] = 0; a->exe_no = 15; return; }
    if (HI(a->x) >= 376 && HI(a->x) <= 392) {
        a->free[2] = 0;
        pit_set(a, 128);
        a->exe_no = 14;
        return;
    }
    if (--a->tm_cnt < 0) {
        TRIM_X(a);
        a->tm_cnt = 0;
        chk_sonicposi(a, SONIC, &d5, &d6);
        if (d5 < 40) return;
        chk_sonicposi(a, EMMY, &d5, &d6);
        if (d5 < 40) return;
        if (myposichk(a)) return;
        a->free[2] = 0;
        a->exe_no = 3;
    }
}

static void m_brakeset(scd_credits *st, actor *a)
{
    (void)st;
    SET_HI(a->y, 136);
    a->x_offset = -14336;
    if (a->spr_flg & 128) a->x_offset = (int16_t)-a->x_offset;
    a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
    anim(a, PAT(m_brake_map));
    a->exe_no = 4;
}

static void metalsbrake(scd_credits *st, actor *a)
{
    (void)st;
    hbt_move(a);
    if ((int16_t)(HI(a->x_speed) + HI(a->x_accel)) == 0) a->exe_no = 5;
}

static void still(actor *a)
{
    TRIM_X(a);
    a->x_speed = a->y_speed = 0;
    a->x_offset = 0; a->x_accel = 0;
    a->y_offset = 0; a->y_accel = 0;
}

static void m_stopset(scd_credits *st, actor *a)
{
    (void)st;
    TRIM_X(a);
    if (HI(a->x) == 384) SET_HI(a->x, 394);
    SET_HI(a->y, 140);
    still(a);
    anim(a, PAT(m_stop_map));
    a->tm_cnt = 32;
    a->exe_no = 6;
}

static void metalsstop(scd_credits *st, actor *a)
{
    if (--a->tm_cnt >= 0) return;
    uint16_t s = SONIC->exe_no;
    a->exe_no = s == 12 || (s >= 5 && s < 9) ? 11 : 7;
}

static void m_standset(scd_credits *st, actor *a)
{
    (void)st;
    still(a);
    anim(a, PAT(m_stand_map));
    a->tm_cnt = 64;
    a->exe_no = 8;
}

static void face_sonic(scd_credits *st, actor *a)
{
    int16_t d5, d6;
    if (chk_sonicposi(a, SONIC, &d5, &d6)) a->spr_flg |= 128;
    else a->spr_flg &= 127;
}

static void metalstand(scd_credits *st, actor *a)
{
    if (--a->tm_cnt < 0) a->exe_no = 9;
    face_sonic(st, a);
}

static void m_startset(scd_credits *st, actor *a)
{
    still(a);
    face_sonic(st, a);
    anim(a, PAT(m_furi_map));
    a->tm_cnt = 16;
    a->free[3] = 0;
    a->exe_no = 10;
}

static void metalstartcttbl(scd_credits *st, actor *a)
{
    if (--a->tm_cnt < 0) {
        if (!a->free[3]) {
            SET_HI(a->y, 136);
            anim(a, PAT(m_kamae_map));
            a->tm_cnt = 48;
            a->free[3] = 1;
        } else {
            a->exe_no = 1;
        }
    }
    face_sonic(st, a);
}

static void m_eraset(scd_credits *st, actor *a)
{
    (void)st;
    still(a);
    anim(a, PAT(m_era_map));
    a->tm_cnt = 32;
    a->free[3] = 0;
    a->exe_no = 12;
}

static void metalsera(scd_credits *st, actor *a)
{
    (void)st;
    if (--a->tm_cnt >= 0) return;
    if (!a->free[3]) {
        anim(a, PAT(m_era2_map));
        a->tm_cnt = 128;
        a->free[3] = 1;
    } else {
        a->exe_no = 9;
    }
}

static void metalsexit(scd_credits *st, actor *a)
{
    waitmode(a);
    if (st->animal_flg != 2) return;
    SET_HI(a->x, 448);
    a->x_speed = 237568;
    a->y_speed = 0;
    a->spr_flg &= 127;
    anim(a, PAT(m_fly1_map));
    a->exe_no = 15;
}

static void metalspit(scd_credits *st, actor *a) { (void)st; pit_in(a); }
static void metalsesc(scd_credits *st, actor *a) { (void)st; escape_chk(a); }

/* Heart (ACT_NO 7) */
static void heartinit(scd_credits *st, actor *a)
{
    SET_HI(a->x, HI(EMMY->x));
    SET_HI(a->y, HI(EMMY->y));
    a->x_speed = 0;
    a->y_speed = -32768;
    a->x_wide = 32;
    a->y_wide = 4;
    a->x_offset = a->y_offset = 0;
    a->cgbase = 967;
    a->free[0] = 3;
    a->pattern = PAT(eheart_map);   /* SPR_TIMER left at 0 */
    a->pat_no = 0;
    a->free[2] = 32;
    a->exe_no = 1;
}

static void heartmove(scd_credits *st, actor *a)
{
    sinvmove(st, a);
    if (a->pat_no >= 3) a->spr_flg |= 16;
}

/* Ground animals (ACT_NO 5, 6, 10, 11) */
static int32_t speed_jitter(scd_credits *st, int range) { return (int32_t)(rnd(st) % range) << 8; }

static void animal_init(scd_credits *st, actor *a, int y, int x_range, int y_range, int16_t gravity, unsigned pattern)
{
    SET_HI(a->x, -10);
    SET_HI(a->y, y);
    a->x_speed = 49152;
    a->x_speed += speed_jitter(st, x_range);
    a->y_speed = -229376;
    a->y_speed += speed_jitter(st, y_range);
    a->y_offset = gravity;
    a->y_accel = 0;
    a->cgbase = 25989;
    a->free[0] = 3;
    anim(a, pattern);
    a->exe_no = 1;
}

static void pockyinit(scd_credits *st, actor *a) { animal_init(st, a, 144, 512, 512, 14336, PAT(pocky_map)); }
static void peckyinit(scd_credits *st, actor *a) { animal_init(st, a, 144, 256, 256, 14336, PAT(pecky_map)); }
static void rickyinit(scd_credits *st, actor *a) { animal_init(st, a, 164, 256, 256, 14336, PAT(ricky_map)); }
static void sheepinit(scd_credits *st, actor *a) { animal_init(st, a, 164, 512, 256, 16384, PAT(sheep_map)); }

static void animalmove(scd_credits *st, actor *a)
{
    (void)st;
    if (killchk(a)) { a->spr_flg |= 16; return; }
    hbt_move(a);
    if (HI(a->y) >= 160) a->y_accel = 0;
}

/* Birds (ACT_NO 4, 8, 9) */
static void bird_init(scd_credits *st, actor *a, int32_t speed, int jitter, unsigned pattern)
{
    SET_HI(a->x, -10);
    SET_HI(a->y, rnd(st) % 120);
    a->x_speed = speed;
    if (jitter) a->x_speed += speed_jitter(st, 256);
    a->y_speed = 0;
    a->x_wide = 48;
    a->y_wide = 4;
    a->x_offset = a->y_offset = 0;
    a->cgbase = 25989;
    a->free[0] = 3;
    anim(a, pattern);
    /* THANKS_M.MMD's bird inits ($FF5A86, $FF5AFA, $FF5B86) leave SPR_TIMER 0, so the
       first sprite pass shows frame 1; the PC sets the first frame's timer. */
    if (st->ending_type & SCD_CREDITS_SEGA_CD) a->spr_timer = 0;
    a->exe_no = 1;
}

static void flickyinit(scd_credits *st, actor *a) { bird_init(st, a, 65536, 0, PAT(flick_map)); }
static void incoinit(scd_credits *st, actor *a) { bird_init(st, a, 32768, 1, PAT(inco_map)); }
static void hatoinit(scd_credits *st, actor *a) { bird_init(st, a, 32768, 1, PAT(hato_map)); }

static void birdmove(scd_credits *st, actor *a)
{
    if (killchk(a)) a->spr_flg |= 16;
    else sinhmove(st, a);
}

typedef void (*routine)(scd_credits *, actor *);

static const routine sonic_tbl[14] = {sonicinit, s_runset, sonicrun, s_turnset, sonicturn, s_standset, sonicstand,
                                      s_waitset, sonicwait, s_ballset, sonicball, sonicexit, sonicpit, sonicesc};
static const routine emie_tbl[16] = {emmyinit, e_runinit, emmymove, e_kissset, emmykiss, e_jumpset, emmyjump, e_catchset,
                                     emmy_catch, e_turnset, emmyturn, e_standset, emmymoji, emmyexit, emmypose, emmyesc};
static const routine metals_tbl[16] = {metalsinit, m_flyset, metalsfly, m_brakeset, metalsbrake, m_stopset, metalsstop,
                                       m_standset, metalstand, m_startset, metalstartcttbl, m_eraset, metalsera,
                                       metalsexit, metalspit, metalsesc};

static void run(scd_credits *st, actor *a, const routine *table, unsigned count)
{
    if (a->exe_no < count) table[a->exe_no](st, a);
}

/* act_tbl: sonic, emie, metals, flick, pocky, ricky, heart, inco, hato, sheep, pecky. */
static void priact(scd_credits *st, actor *a)
{
    static const routine animal_init_tbl[12] = {0, 0, 0, 0, flickyinit, pockyinit, rickyinit, heartinit,
                                                incoinit, hatoinit, sheepinit, peckyinit};
    switch (a->act_no) {
    case 1:
        if (st->animal_flg) a->spr_flg |= 4;
        run(st, a, sonic_tbl, 14);
        CTRL_WRAP_X(st, a);
        break;
    case 2:
        if (st->animal_flg) a->spr_flg |= 4;
        emmy_exeset(st, a, SONIC);
        run(st, a, emie_tbl, 16);
        CTRL_WRAP_X(st, a);
        break;
    case 3:
        if (st->animal_flg) a->spr_flg |= 4;
        run(st, a, metals_tbl, 16);
        CTRL_WRAP_X(st, a);
        break;
    case 4: case 5: case 6: case 7: case 8: case 9: case 10: case 11:
        if (a->exe_no == 0) animal_init_tbl[a->act_no](st, a);
        else if (a->exe_no == 1) {
            if (a->act_no == 7) heartmove(st, a);
            else if (a->act_no == 4 || a->act_no == 8 || a->act_no == 9) birdmove(st, a);
            else animalmove(st, a);
        }
        break;
    default:
        a->act_no = 0;   /* dummy */
        break;
    }
    if (a->spr_flg & 16) memset(a, 0, sizeof(*a));
}

static void priset(scd_credits *st)
{
    unsigned fill[4] = {0, 0, 0, 0};
    /* The PC clears pribuf0[0..3] (not pribuf1..3[0]); a priority with no
       actors this frame keeps last frame's list. */
    memset(st->pribuf[0], 0, 4);
    for (int i = 0; i <= 63; i++) {
        const actor *a = &st->actors[i];
        if (!a->act_no) continue;
        unsigned p = a->free[0] & 3;
        st->pribuf[p][fill[p]++] = (uint8_t)(i + 1);
        st->pribuf[p][fill[p]] = 0;
    }
}

static void pattern_chg(actor *a)
{
    const scd_credits_pattern *p = &scd_credits_patterns[a->pattern];
    if (--a->spr_timer <= 0) {
        int16_t d0 = (int16_t)(a->pat_no + 1);
        if ((uint16_t)d0 >= p->count) d0 = 0;
        a->pat_no = d0;
        a->spr_timer = scd_credits_frames[p->first + d0].timer;
    }
}

static void spr_set(scd_credits *st)
{
    st->link = 0;
    for (int pri = 0; pri <= 3; pri++) {
        const uint8_t *list = st->pribuf[pri];
        for (int i = 0; i < 64 && list[i]; i++) {
            actor *a = &st->actors[list[i] - 1];
            if (!a->act_no) continue;
            pattern_chg(a);
            const scd_credits_pattern *p = &scd_credits_patterns[a->pattern];
            const scd_credits_mapping *m = &scd_credits_mappings[scd_credits_frames[p->first + a->pat_no].mapping];
            for (int j = m->count, k = 0; j > 0; j--, k++) {
                const scd_credits_piece *piece = &scd_credits_pieces[m->first + k];
                unsigned flags = 0;
                int16_t x = HI(a->x), y = HI(a->y);
                if (a->spr_flg & 128) { x = (int16_t)(x - piece->hrevoffs); flags |= 1; }
                else x = (int16_t)(x - piece->hoffs);
                x = (int16_t)(x + 128);
                if (a->spr_flg & 64) { y = (int16_t)(y - piece->vrevoffs); flags |= 2; }
                else y = (int16_t)(y - piece->voffs);
                y = (int16_t)(y + 128);
                flags ^= piece->etc;
                if (a->spr_flg & 32) flags |= 32768;
                eas_prset(st, x, y, (uint16_t)piece->index, st->link, flags);
                if (++st->link >= 80) break;
            }
        }
    }
}

static void action(scd_credits *st)
{
    for (int i = 0; i <= 63; i++)
        if (st->actors[i].act_no) priact(st, &st->actors[i]);
    priset(st);
    spr_set(st);
    for (int i = st->link; i < 80; i++) eas_prset(st, 0, 0, 0, (unsigned)i, 0);
}

/* CHRSET.C */
static void spawn(scd_credits *st, uint16_t act_no)
{
    int slot = get_actwk(st);
    if (slot >= 0) st->actors[slot].act_no = act_no;
}

static void sprinit(scd_credits *st)
{
    static const int16_t actset_tbl[16] = {120, 180, 180, 300, 240, 600, 720, 1800,
                                           840, 2280, 600, 2160, 240, 600, 300, 600};
    static const int16_t manyact_tbl[16] = {10, 25, 15, 20, 10, 25, 20, 50, 30, 60, 20, 60, 40, 70, 900, 1500};
    /* flick, inco, hato, pocky, pecky, ricky, sheep, sonic */
    static const uint16_t spawn_tbl[8] = {4, 8, 9, 5, 11, 6, 10, 0};
    int16_t d5 = st->animal_flg == 2 ? 6 : 7;
    int16_t *a2 = st->actset_tm;
    for (;;) {
        if (*a2 == 0) { --*a2; break; }
        --*a2;
        ++a2;
        if (d5-- == 0) return;
    }
    const int16_t *a1 = (st->animal_flg != 2 ? actset_tbl : manyact_tbl) + d5 * 2;
    *a2 = a1[0];
    *a2 = (int16_t)(*a2 + (int16_t)((scd_credits_random(st) & 65535) % a1[1]));
    if (d5 == 7) SONIC->act_no = 1;
    else spawn(st, spawn_tbl[d5]);
}

/* BM_M.C */
static void put_ascii(scd_credits *st, unsigned c, unsigned x, unsigned y)
{
    const uint16_t *map = scd_credits_glyph_words + scd_credits_glyph_first[c];
    unsigned rows = c == 27 ? 4 : 3;
    for (unsigned i = 0; i < rows; i++) {
        set_grid(st, 0, (int)x, (int)(y + i), *map++ + 32767 + 330);
        set_grid(st, 0, (int)x + 1, (int)(y + i), *map++ + 32767 + 330);
    }
}

static void pointcnt(scd_credits *st, const char *name, int16_t pts)
{
    for (int i = 0; i < SCD_CREDITS_NAMES; i++) {
        if (st->score[i].pts) {
            if (memcmp(st->score[i].name, name, 3)) continue;
            st->score[i].pts = (int16_t)(st->score[i].pts + pts);
            return;
        }
        st->score[i].pts = pts;
        memcpy(st->score[i].name, name, 3);
        st->score[i].name[3] = 0;
        return;
    }
}

static void get_usrname(scd_credits *st)
{
    static const char none[4];
    const char (*names)[4] = st->config->names;
    memset(st->score, 0, sizeof(st->score));
    if (st->ending_type & SCD_CREDITS_SEGA_CD) {
        /* THANKS_M.MMD $FF2142 counts every first place (3 points), then every second
           (2), then every third (1); the PC goes record by record. */
        for (int rank = 0; rank < 3; rank++)
            for (int i = rank; i < SCD_CREDITS_NAMES; i += 3)
                pointcnt(st, names ? names[i] : none, (int16_t)(3 - rank));
    } else
        for (int i = 0; i < SCD_CREDITS_NAMES; i++)
            pointcnt(st, names ? names[i] : none, (int16_t)(3 - i % 3));
    int gp = 0;
    for (int i = 0; i < SCD_CREDITS_NAMES && st->score[i].pts; i++)
        if (st->score[i].pts >= st->score[gp].pts) gp = i;
    strcpy(st->greatest, st->score[gp].name);
}

static void dsp_usrname(scd_credits *st)
{
    for (int i = 0; i < 3; i++) {
        int ch = st->greatest[i];
        unsigned c;
        if (ch >= '0' && ch <= '9') c = (unsigned)(ch - 47);
        else if (ch >= 'A' && ch <= 'Z') c = (unsigned)(ch - 54);
        else continue;
        put_ascii(st, c & 0xFFFF, (unsigned)(i * 2 + 17), 12);
    }
}

static void mainloop(scd_credits *st)
{
    if (st->prg_mode == 0) {   /* get_tmdata */
        get_usrname(st);
        dsp_usrname(st);
        st->actset_tm[0] = 600;
        for (int i = 1; i < 7; i++) st->actset_tm[i] = 0;
        st->actset_tm[7] = 600;
        st->prg_mode = 1;
        return;
    }
    if (st->ending_type & SCD_CREDITS_SEGA_CD) {
        /* $FF2266 only ever sets the quit flag. */
        if (st->swdata1 & SCD_CREDITS_PAD_BUTTONS) st->quit_flg = 1;
    } else st->quit_flg = st->swdata1 & SCD_CREDITS_PAD_BUTTONS ? 1 : 0;   /* player */
    sprinit(st);
    action(st);
}

/* GAME.C */
static void copy_palette(scd_credits *st, int first, const uint8_t (*src)[3], int count)
{
    memcpy(st->palette[first], src, (size_t)count * 3);
}

static void v_int(scd_credits *st)
{
    if (st->animal_flg == 2 && --st->animal_timer <= 0) st->animal_flg = 0;
    if (--st->posetimer <= 0) {
        if (SONIC->act_no) st->animal_flg = 1;
        st->animal_timer = 900;
        st->posetimer = (int16_t)(rnd(st) % 4096 + 8192);
    }
    /* THANKS_M.MMD's V-int ($FF3AE2) skips both palette cycles once the quit flag is set. */
    if (!((st->ending_type & SCD_CREDITS_SEGA_CD) && st->quit_flg) && --st->coltimer <= 0) {
        if (st->colorno >= 31) st->colorno = 0;
        int16_t d0 = st->colorno++;
        st->coltimer = (int16_t)scd_credits_lpbs_timer[d0];
        if (st->ending_type & SCD_CREDITS_SEGA_CD) {
            /* $FF3B12 copies all 24 colours (16-39) into the buffer shown; the PC 16. */
            copy_palette(st, 16, scd_credits_good[scd_credits_good_cycle[d0]], 24);
#if SCD_CREDITS_MD_TABLES
            memcpy(st->md_cram + 16, scd_credits_md_good[d0], sizeof(scd_credits_md_good[d0]));
#endif
        } else copy_palette(st, 16, scd_credits_good[scd_credits_good_cycle[d0]], 16);
    }
    if (!((st->ending_type & SCD_CREDITS_SEGA_CD) && st->quit_flg) && --st->coltimer2 <= 0) {
        if (st->colorno2 >= 2) st->colorno2 = 0;
        st->coltimer2 = 20;
#if SCD_CREDITS_MD_TABLES
        if (st->ending_type & SCD_CREDITS_SEGA_CD)
            memcpy(st->md_cram + 40, scd_credits_md_asc[st->colorno2], sizeof(scd_credits_md_asc[0]));
#endif
        copy_palette(st, 40, scd_credits_asc_col[st->colorno2++], 8);
    }
    if (--st->end_timer <= 0) st->quit_flg = 1;
}

static void cgmwrt(scd_credits *st, int plane, const int16_t *map, int shift, int limit)
{
    for (int y = 0; y < 28; y++)
        for (int x = 0; x < 40; x++) {
            int tile = map ? map[y * 64 + x] : 0;
            if (tile & 1023) tile += shift;
            if ((tile & 1023) >= limit) tile = 0;
            set_grid(st, plane, x, y, tile);
        }
}

/* EndingMes: the PC's ending message (sprites 75-77) before the screen.
   Returns 1 while the message holds the frame. */
static int ending_mes(scd_credits *st)
{
    if (st->ending_type & SCD_CREDITS_SEGA_CD) return 0;
    if (++st->message_timer > 360) { st->message_timer = 360; return 0; }
    int good = st->ending_type & SCD_CREDITS_MESSAGE_GOOD, bad = st->ending_type & SCD_CREDITS_MESSAGE_BAD;
    if (!good && !bad) return 1;
    if (st->message_timer == 1) eas_prset(st, good ? 224 : 252, 288, good ? 76 : 75, 0, 0);
    else if (st->message_timer == 180) eas_prset(st, 208, 228, 77, 0, 0);
    else if (st->message_timer == 360) {
        if (!(st->swdata1 & SCD_CREDITS_PAD_BUTTONS)) st->message_timer--;
        else if (good) copy_palette(st, 0, scd_credits_colortbl, 64);   /* vdpinit */
        else memset(st->palette, 0, sizeof(st->palette));
    }
    return 1;
}

/* Sega CD presentation (THANKS_M.MMD). */
static uint16_t md_colour(const uint8_t rgb[3])
{
    return (uint16_t)((rgb[0] / 32 * 2) | (rgb[1] / 32 * 2) << 4 | (rgb[2] / 32 * 2) << 8);
}

void scd_credits_md_fade_in(uint16_t cram[64], const uint16_t target[64])
{
    for (int i = 0; i < 64; i++) {
        uint16_t c = cram[i], t = target[i];
        if (c == t) continue;
        if ((uint16_t)(c + 0x200) <= t) c = (uint16_t)(c + 0x200);
        else if ((uint16_t)(c + 0x020) <= t) c = (uint16_t)(c + 0x020);
        else c = (uint16_t)(c + 2);
        cram[i] = c;
    }
}

void scd_credits_md_fade_out(uint16_t cram[64])
{
    for (int i = 0; i < 64; i++) {
        uint16_t c = cram[i];
        if (!c) continue;
        if (c & 0x00E) c = (uint16_t)(c - 0x002);
        else if (c & 0x0E0) c = (uint16_t)(c - 0x020);
        else if (c & 0xE00) c = (uint16_t)(c - 0x200);
        cram[i] = c;
    }
}

/* THANKS_M.MMD after game_init and get_tmdata. Its V-int ($FF3A40) sends the sprite
   table, runs v_int (whose palette cycles write the buffer shown), then sends that
   buffer; so one call here is the main program's work for a frame (a fade step or a
   main loop pass) followed by the next V-int's v_int, and its picture is what that
   V-int shows. The fade from black ($FF3E48, 22 steps) starts after one V-int; the
   first main loop pass ($FF2128) follows the last step in the same frame. After the
   pass that sets the quit flag come one idle frame and the 22 steps of the fade to
   black ($FF3EE4); the call with the last step returns -1. */
static int sega_cd_frame(scd_credits *st)
{
    switch (st->md_phase) {
    case 0:
        scd_credits_md_fade_in(st->md_cram, st->md_target);
        if (++st->md_count < SCD_CREDITS_MD_FADE_STEPS) break;
        st->md_phase = 1;
        st->md_count = 0;
        __attribute__((fallthrough));   /* the first pass */
    case 1:
        mainloop(st);
        if (st->quit_flg) st->md_phase = 2;
        break;
    case 2:
        /* The pass ended on a V-int wait; the fade waits for the next before each step. */
        if (st->md_count++) scd_credits_md_fade_out(st->md_cram);
        if (st->md_count == SCD_CREDITS_MD_FADE_STEPS + 1) st->md_phase = 3;
        break;
    default:
        return -1;
    }
    v_int(st);
    /* The end timer sets the quit flag in the V-int: the loop ends before another pass. */
    if (st->md_phase == 1 && st->quit_flg) st->md_phase = 2;
    return st->md_phase == 3 ? -1 : 0;
}

void scd_credits_init(scd_credits *st, const scd_credits_config *config)
{
    memset(st, 0, sizeof(*st));   /* WorkRamClear */
    st->config = config;
    st->ending_type = config->ending_type;
    st->swdata1 = 0xF000;
    cgmwrt(st, 0, config->map_a, 174, 461);
    cgmwrt(st, 1, config->map_b, -154, 329);
    if (st->ending_type & SCD_CREDITS_SEGA_CD) copy_palette(st, 0, scd_credits_colortbl, 64);
    else copy_palette(st, 0, scd_credits_endingcol, 64);   /* EndingMesColor */
    st->coltimer = (int16_t)scd_credits_lpbs_timer[0];
    st->colorno = 0;
    st->coltimer2 = 20;
    st->colorno2 = 1;
    st->posetimer = 1536;
    st->heart_tm = 1;
    st->end_timer = 10800;
    if (st->ending_type & SCD_CREDITS_SEGA_CD) {
        /* get_tmdata (mode 0) and the name run before the fade from black. */
        mainloop(st);
#if SCD_CREDITS_MD_TABLES
        memcpy(st->md_target, scd_credits_md_colortbl, sizeof(st->md_target));
#else
        for (int i = 0; i < 64; i++) st->md_target[i] = md_colour(st->palette[i]);
#endif
        v_int(st);   /* the V-int before the first fade step */
    }
}

int scd_credits_frame(scd_credits *st, uint16_t pad)
{
    st->swdata1 = pad;
    st->sound_count = 0;
    if (st->ending_type & SCD_CREDITS_SEGA_CD) return sega_cd_frame(st);
    if (ending_mes(st)) return 0;
    if (st->ending_type & SCD_CREDITS_MESSAGE_BAD) return -1;
    mainloop(st);
    v_int(st);
    return st->quit_flg ? -1 : 0;
}

/* Sega CD presentation (THANKS_M.MMD). */
void scd_credits_md_frame(const scd_credits *st, scd_credits_md *out)
{
    memset(out, 0, sizeof(*out));
    for (int i = 0; i < 64; i++)
        out->cram[i] = st->ending_type & SCD_CREDITS_SEGA_CD ? st->md_cram[i] & 0x0EEE : md_colour(st->palette[i]);
    for (int r = 0; r < 4; r++)
        for (int c = 0; c < 6; c++) {
            uint16_t v = st->plane[0][(12 + r) * SCD_CREDITS_PLANE_W + 17 + c];
            /* put_ascii adds 32767 + 330; THANKS_M.MMD adds SCD_CREDITS_MD_GLYPH_BASE. */
#if SCD_CREDITS_MD_TABLES
            out->names[r][c] = v ? (uint16_t)(v - (32767 + 330) + SCD_CREDITS_MD_GLYPH_BASE) : 0;
#else
            out->names[r][c] = 0;
            (void)v;
#endif
        }
#if SCD_CREDITS_MD_TABLES
    /* spr_set over the same priority lists, with the retail pieces. */
    unsigned link = 0;
    for (int pri = 0; pri <= 3; pri++) {
        const uint8_t *list = st->pribuf[pri];
        for (int i = 0; i < 64 && list[i]; i++) {
            const actor *a = &st->actors[list[i] - 1];
            if (!a->act_no) continue;
            const scd_credits_pattern *p = &scd_credits_patterns[a->pattern];
            unsigned frame = (uint16_t)a->pat_no < scd_credits_md_count[a->pattern] ? (uint16_t)a->pat_no : 0;
            const scd_credits_mapping *m = &scd_credits_md_maps[scd_credits_md_frame_map[p->first + frame]];
            for (unsigned k = 0; k < m->count && link < SCD_CREDITS_MD_SPRITES; k++) {
                const scd_credits_md_piece *piece = &scd_credits_md_pieces[m->first + k];
                unsigned flags = 0;
                int16_t x = HI(a->x), y = HI(a->y);
                if (a->spr_flg & 128) { x = (int16_t)(x - piece->hrevoffs); flags |= 1; }
                else x = (int16_t)(x - piece->hoffs);
                if (a->spr_flg & 64) { y = (int16_t)(y - piece->vrevoffs); flags |= 2; }
                else y = (int16_t)(y - piece->voffs);
                flags ^= piece->etc;
                uint16_t attr = (uint16_t)((uint16_t)(a->cgbase + piece->tile) ^ (flags & 3) << 11);
                if (a->spr_flg & 32) attr |= 0x8000;
                uint16_t *e = out->sat[link];
                e[0] = (uint16_t)(y + 128);
                e[1] = (uint16_t)(piece->size << 8 | (link + 1));
                e[2] = attr;
                e[3] = (uint16_t)(x + 128);
                link++;
            }
        }
    }
    if (link) out->sat[link - 1][1] &= 0xFF00;
    out->sprites = (uint8_t)link;
#endif
}
