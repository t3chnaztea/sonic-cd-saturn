/* Wacky Workbench actor code runs from the R6 zone overlay
 * (src/saturn.x .zone_R6, heap plan B). objects.c includes this before its first
 * mention of these functions. The Saturn build (SCD_ZONE_OVERLAY) gives each the z6_
 * prefix, which places its .text.z6_* section in the overlay. Resident code reaches them
 * only through ww_zone_ops (src/objects_ww.inc, listed in src/objects_zone_ops.inc);
 * tools/test_zone_code.py audits those references.
 * Kept resident (not listed): scd_objects_ww_palette (src/background.c calls it every
 * frame), ww_reset (scd_objects_reset runs it, as tp_reset stays resident for R4), the
 * weak scd_r6_palette_count (src/background_r6.c defines the real one), and the QQ/TT
 * helpers the WW actors call (qq_w/qq_ws/qq_index/qq_time_flag, tp_* in
 * objects_tt_ride.inc). The WW data tables (ww_colitbl, ww_clrtbl*, ww_gaschg*, ...)
 * keep their names; which of them move is the linker script's choice. */
#ifndef SCD_ZONE_R6_NAMES_H
#define SCD_ZONE_R6_NAMES_H
#ifdef SCD_ZONE_OVERLAY
/* objects_ww.inc (dispatch; ww_zone_ops members) */
#define ww_type z6_ww_type
#define ww_contact_type z6_ww_contact_type
#define ww_step z6_ww_step
#define ww_scan z6_ww_scan
#define ww_reject z6_ww_reject
#define ww_init z6_ww_init
#define ww_zone_step z6_ww_zone_step
#define ww_view z6_ww_view
/* objects_ww_common.inc (COLI6 pcol, playdamageset) */
#define ww_playdamageset z6_ww_playdamageset
#define ww_enemy_scan z6_ww_enemy_scan
/* objects_ww_enemies.inc */
#define batta_lr z6_batta_lr
#define batta_patexg z6_batta_patexg
#define batta_wall z6_batta_wall
#define batta_fall z6_batta_fall
#define batta_act z6_batta_act
#define hachi6_turn z6_hachi6_turn
#define hachi6_move z6_hachi6_move
#define hachi6_tama z6_hachi6_tama
#define hachi6_act z6_hachi6_act
#define semi_check z6_semi_check
#define semi_bomb z6_semi_bomb
#define semi_act z6_semi_act
#define minomusi_body z6_minomusi_body
#define minomusi_act z6_minomusi_act
#define ww_pal z6_ww_pal
#define beem6_clrset0 z6_beem6_clrset0
#define beem6_clrset1 z6_beem6_clrset1
#define beem6_posiset z6_beem6_posiset
#define beem6_move z6_beem6_move
#define beem6_act z6_beem6_act
/* objects_ww_gimmicks.inc */
#define dair6_sub2 z6_dair6_sub2
#define dair6_x z6_dair6_x
#define dair6_act z6_dair6_act
#define kdai6_sub2 z6_kdai6_sub2
#define kdai6_act z6_kdai6_act
#define ww_yuka_chk z6_ww_yuka_chk
#define ww_yuka_ridechk z6_ww_yuka_ridechk
#define tobidai6_speedset z6_tobidai6_speedset
#define tobidai6_act z6_tobidai6_act
#define block6_set_slave z6_block6_set_slave
#define block6_act z6_block6_act
#define seesaw6_draw z6_seesaw6_draw
#define seesaw6_slave z6_seesaw6_slave
#define seesaw6_act z6_seesaw6_act
#define piston6_act z6_piston6_act
#define sw6_act z6_sw6_act
#define tobira6_cnt z6_tobira6_cnt
#define tobira6_move z6_tobira6_move
#define tobira6_act z6_tobira6_act
#define udblk6_movecnt z6_udblk6_movecnt
#define udblk6_act z6_udblk6_act
#define optbr6_ride z6_optbr6_ride
#define optbr6_cnt z6_optbr6_cnt
#define optbr6_act z6_optbr6_act
#define ww_new_explosion z6_ww_new_explosion
#define eggz6_act z6_eggz6_act
/* objects_ww_story.inc */
#define ww_random z6_ww_random
#define megami_act z6_megami_act
#define gas_ice_sub0 z6_gas_ice_sub0
#define gas_act z6_gas_act
#define catapalt_act z6_catapalt_act
#define shoot6_spdset z6_shoot6_spdset
#define shoot6_act z6_shoot6_act
#define togeball6_build z6_togeball6_build
#define togeball6_act z6_togeball6_act
#define et6_act z6_et6_act
#define movie6_act z6_movie6_act
#define friend6_sproffset z6_friend6_sproffset
#define friend6_roll z6_friend6_roll
#define friend6_movie_gone z6_friend6_movie_gone
#define friend6_act z6_friend6_act
#endif
#endif
