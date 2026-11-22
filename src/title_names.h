/* Title screen code that runs from the front-end overlay (src/saturn.x .zone_R0,
 * cd/ZTR0.BIN). title.c includes this after its headers; in the Saturn build
 * (SCD_ZONE_OVERLAY) every function and table gets the fe_ prefix, which places its
 * .text.fe_* / .rodata.fe_* section in the overlay. Resident code (src/title_view.inc)
 * reaches the title only through fe_title_zone_ops; host tools keep the plain names. */
#ifndef SCD_TITLE_NAMES_H
#define SCD_TITLE_NAMES_H
#ifdef SCD_ZONE_OVERLAY
#define be16 fe_title_be16
#define be32 fe_title_be32
#define scd_title_open fe_title_open
#define part fe_title_part
#define vram_write fe_title_vram_write
#define vram_word fe_title_vram_word
#define load_art fe_title_load_art
#define spawn fe_title_spawn
#define draw_object fe_title_draw_object
#define clear_sprites fe_title_clear_sprites
#define set_menu_option fe_title_set_menu_option
#define menu_move_right fe_title_menu_move_right
#define menu_move_left fe_title_menu_move_left
#define menu_wait_selection fe_title_menu_wait_selection
#define arrow fe_title_arrow
#define run_object fe_title_run_object
#define run_objects fe_title_run_objects
#define sine fe_title_sine
#define muls fe_title_muls
#define divs fe_title_divs
#define trace_ray fe_title_trace_ray
#define stamp_pixel fe_title_stamp_pixel
#define stamp_cache_fill fe_title_stamp_cache_fill
#define sample_line fe_title_sample_line
#define render fe_title_render
#define scd_title_render fe_title_render_frame
#define render_clouds fe_title_render_clouds
#define get_clouds_image fe_title_get_clouds_image
#define palette_cycle fe_title_palette_cycle
#define scroll_background fe_title_scroll_background
#define fade_from_black_frame fe_title_fade_from_black_frame
#define fade_from_white_frame fe_title_fade_from_white_frame
#define fade_to_black_frame fe_title_fade_to_black_frame
#define palette_word_copy fe_title_palette_word_copy
#define main_program fe_title_main_program
#define scd_title_start fe_title_start
#define scd_title_vint fe_title_vint
#define scd_title_lag_frames fe_title_lag_frames
#define special_sines fe_title_special_sines
#define title_water_cycle fe_title_title_water_cycle
#define title_planet_offsets fe_title_title_planet_offsets
#define title_arm_frames fe_title_title_arm_frames
#define title_arrow_frames fe_title_title_arrow_frames
#define map_parts fe_title_map_parts
#define sound_test_code fe_title_sound_test_code
#endif
#endif
