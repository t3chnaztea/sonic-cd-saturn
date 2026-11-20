/* Collision Chaos actor code that runs from the R3 zone overlay (src/saturn.x .zone_R3,
 * cd/ZTR3.BIN, heap plan B). objects.c includes this before its first mention of these
 * functions; in the Saturn build (SCD_ZONE_OVERLAY) each gets the z3_ prefix, which
 * places its .text.z3_* section in the overlay. Resident code reaches them only through
 * r3_zone_ops (src/objects_zone_ops.inc); tools/test_zone_code.py checks both rules.
 * Kept resident (not listed): the rider/draw helpers the TT and QQ actors share
 * (cc_object_draw, cc_ride, cc_solid) and what they call, and the tests objects.c runs
 * in every zone (cc_trap_parent, cc_bomb_explosion_step for explosion subtypes 3/4). */
#ifndef SCD_ZONE_R3_NAMES_H
#define SCD_ZONE_R3_NAMES_H
#ifdef SCD_ZONE_OVERLAY
#define cc_word z3_cc_word
#define for3_sink z3_for3_sink
#define for3_horizontal z3_for3_horizontal
#define for3_vertical z3_for3_vertical
#define for3_rise z3_for3_rise
#define for3_step z3_for3_step
#define cc_trap_child z3_cc_trap_child
#define harir3_motion z3_harir3_motion
#define harir3_step z3_harir3_step
#define frdr3_step z3_frdr3_step
#define trapdr3_step z3_trapdr3_step
#define getdair3_step z3_getdair3_step
#define gandair3_patchg z3_gandair3_patchg
#define gandair3_fires z3_gandair3_fires
#define gandair3_bullets z3_gandair3_bullets
#define gandair3_step z3_gandair3_step
#define cc_enemy_contact z3_cc_enemy_contact
#define cc_enemy_suicide z3_cc_enemy_suicide
#define drum_cntset z3_drum_cntset
#define drum_ride z3_drum_ride
#define drum_step z3_drum_step
#define mecasnc_face z3_mecasnc_face
#define mecasnc_anim z3_mecasnc_anim
#define emie_anim z3_emie_anim
#define mecasnc_parent z3_mecasnc_parent
#define mecasnc_finish z3_mecasnc_finish
#define heart3_step z3_heart3_step
#define emie_heart z3_emie_heart
#define emie3_step z3_emie3_step
#define mecasnc_fire_step z3_mecasnc_fire_step
#define mecasnc3_step z3_mecasnc3_step
#define hari3x_speed z3_hari3x_speed
#define hari3x_break z3_hari3x_break
#define hari3x_step z3_hari3x_step
#define sikake_patchg z3_sikake_patchg
#define sikake_child z3_sikake_child
#define sikake_actor z3_sikake_actor
#define kaitenban_check z3_kaitenban_check
#define kaitenban_step z3_kaitenban_step
#define sikake_orphan z3_sikake_orphan
#define light_step z3_light_step
#define stopper_move z3_stopper_move
#define stopper_step z3_stopper_step
#define sikake33_step z3_sikake33_step
#define ga_long z3_ga_long
#define ga_set_long z3_ga_set_long
#define ga_patchg z3_ga_patchg
#define ga_step z3_ga_step
#define tentou_long z3_tentou_long
#define tentou_set_long z3_tentou_set_long
#define tentou_patchg z3_tentou_patchg
#define tentou_hover z3_tentou_hover
#define tentou_bomb_die z3_tentou_bomb_die
#define tentou_step z3_tentou_step
#define kama_patchg z3_kama_patchg
#define kama_move_xy z3_kama_move_xy
#define kama_spawn_blades z3_kama_spawn_blades
#define kama_step z3_kama_step
#define kama_blade_step z3_kama_blade_step
#define banpa_step z3_banpa_step
#define togeball_position z3_togeball_position
#define togeball_step z3_togeball_step
#define pocket_allocate z3_pocket_allocate
#define cc_points_step z3_cc_points_step
#define pocket_child_step z3_pocket_child_step
#define pocket_step z3_pocket_step
#define cc_generator_patchg z3_cc_generator_patchg
#define cc_generator_step z3_cc_generator_step
#define cc_actor z3_cc_actor
#define cc_scan z3_cc_scan
#endif
#endif
