/* Quartz Quadrant code that runs from the R5 zone overlay (src/saturn.x .zone_R5,
 * cd/ZTR5.BIN, heap plan B): the actors (objects_qq*.inc, included by objects.c) and the
 * background (background_r5.c, included by background.c). Both files include this before
 * their first mention of these functions; in the Saturn build (SCD_ZONE_OVERLAY) each gets
 * the z5_ prefix, which places its .text.z5_* section in the overlay. Resident code reaches
 * them only through qq_zone_ops (src/objects_zone_ops.inc) and r5_background_zone_ops
 * (src/background.c); tools/test_zone_code.py checks both rules.
 * Kept resident (not listed): the QQ helpers the WW/SS/MM ports call (qq_l/qq_w accessors,
 * qq_link, qq_index, qq_explode, qq_enemy_suicide, qq_friend_suicide, qq_time_flag). */
#ifndef SCD_ZONE_R5_NAMES_H
#define SCD_ZONE_R5_NAMES_H
#ifdef SCD_ZONE_OVERLAY
/* objects_qq*.inc */
#define qq_contact_type z5_qq_contact_type
#define qq_enemy_scan z5_qq_enemy_scan
#define denden_act z5_denden_act
#define sasori_init_sub z5_sasori_init_sub
#define sasori_tail z5_sasori_tail
#define sasori_act z5_sasori_act
#define kemusi_com z5_kemusi_com
#define kemusi_step_x z5_kemusi_step_x
#define kemusi_move z5_kemusi_move
#define kemusi_move1 z5_kemusi_move1
#define kemusi_act z5_kemusi_act
#define kumo_jump1 z5_kumo_jump1
#define kumo_act z5_kumo_act
#define iwa5_act z5_iwa5_act
#define hari5f_act z5_hari5f_act
#define harir5_sub z5_harir5_sub
#define harir5_act z5_harir5_act
#define iwa5roll_act z5_iwa5roll_act
#define kuzure5_act z5_kuzure5_act
#define iwa5wave_com z5_iwa5wave_com
#define iwa5wave_fields z5_iwa5wave_fields
#define iwa5wave_act z5_iwa5wave_act
#define buranko5_act z5_buranko5_act
#define hasira5_act z5_hasira5_act
#define hashi5_posiset z5_hashi5_posiset
#define hashi5_ridechk1p z5_hashi5_ridechk1p
#define hashi5_act z5_hashi5_act
#define beltsw5_act z5_beltsw5_act
#define shoot5_route z5_shoot5_route
#define shoot5_div z5_shoot5_div
#define shoot5_spdset z5_shoot5_spdset
#define shoot5_act z5_shoot5_act
#define movie5_act z5_movie5_act
#define friend5_sproffset z5_friend5_sproffset
#define friend5_roll z5_friend5_roll
#define friend5_movie_gone z5_friend5_movie_gone
#define friend5_act z5_friend5_act
#define et5_act z5_et5_act
#define kowasi5_down z5_kowasi5_down
#define kowasi5_act z5_kowasi5_act
#define qq_type z5_qq_type
#define qq_reset z5_qq_reset
#define qq_step z5_qq_step
#define qq_reject z5_qq_reject
#define qq_init z5_qq_init
#define qq_zone_step z5_qq_zone_step
#define qq_view z5_qq_view
/* background_r5.c */
#define r5_program_at z5_r5_program_at
#define scd_r5_valid z5_scd_r5_valid
#define r5_log z5_r5_log
#define r5_show z5_r5_show
#define r5_scrbinit z5_r5_scrbinit
#define r5_enkei_for z5_r5_enkei_for
#define r5_init z5_r5_init
#define scd_r5_reset z5_scd_r5_reset
#define scd_r5_set_enkei z5_scd_r5_set_enkei
#define scd_r5_enkei z5_scd_r5_enkei
#define scd_r5_layers z5_scd_r5_layers
#define scd_r5_set_hz z5_scd_r5_set_hz
#define scd_r5_set_colrev z5_scd_r5_set_colrev
#define scd_r5_set_boss z5_scd_r5_set_boss
#define r5_enkeichg z5_r5_enkeichg
#define scd_r5_step z5_scd_r5_step
#define r5_body_at z5_r5_body_at
#define scd_r5_background_y z5_scd_r5_background_y
#define r5_layer z5_r5_layer
#define r5_layers_or z5_r5_layers_or
#define r5_builders z5_r5_builders
#define r5_row_x z5_r5_row_x
#define r5_keep_rows z5_r5_keep_rows
#define scd_r5_set_vy z5_scd_r5_set_vy
#define scd_r5_raster_x z5_scd_r5_raster_x
#define scd_r5_lines_layers z5_scd_r5_lines_layers
#define scd_r5_row_layer z5_scd_r5_row_layer
#define scd_r5_row_start z5_scd_r5_row_start
#define r5_colchg z5_r5_colchg
#define r5_clchgctr z5_r5_clchgctr
#define r5_zone z5_r5_zone
#define scd_r5_palette z5_scd_r5_palette
#define qq_at z5_qq_at
#define scd_r5_tile_run z5_scd_r5_tile_run
#define scd_r5_tile_limit z5_scd_r5_tile_limit
#define scd_r5_art z5_scd_r5_art
#define scd_r5_map_cell z5_scd_r5_map_cell
#define scd_r5_chunk z5_scd_r5_chunk
#define scd_r5_map_update z5_scd_r5_map_update
#endif
#endif
