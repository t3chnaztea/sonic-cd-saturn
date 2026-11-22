/* The movie player (src/fmv_saturn.c, src/fmv_stm.c) runs from the front-end overlay
   (src/saturn.x .zone_R0, cd/ZTR0.BIN): resident code reaches it only through
   fe_ending_zone_ops (src/ending.c) after scd_frontend_overlay_load().
   tools/test_zone_code.py checks both rules. Host builds keep the plain names. */
#ifndef SCD_FMV_FE_NAMES_H
#define SCD_FMV_FE_NAMES_H
#ifdef SCD_ZONE_OVERLAY
/* src/fmv_saturn.c */
#define be16 fe_fmv_be16
#define be32 fe_fmv_be32
#define vram_copy fe_fmv_vram_copy
#define vram_fill fe_fmv_vram_fill
#define palette_write fe_fmv_palette_write
#define pnd fe_fmv_pnd
#define md_name fe_fmv_md_name
#define nbg1_put fe_fmv_nbg1_put
#define layout_set fe_fmv_layout_set
#define frt_now fe_fmv_frt_now
#define slot_ca fe_fmv_slot_ca
#define audio_pos fe_fmv_audio_pos
#define slot_start fe_fmv_slot_start
#define slot_stop fe_fmv_slot_stop
#define wait_vblank fe_fmv_wait_vblank
#define sector_ready fe_fmv_sector_ready
#define cd_service fe_fmv_cd_service
#define gfx_loaded fe_fmv_gfx_loaded
#define credits_begin fe_fmv_credits_begin
#define prepare_next fe_fmv_prepare_next
#define credits_step fe_fmv_credits_step
#define ending_rs fe_fmv_ending_rs
#define display_init fe_fmv_display_init
#define stream_open fe_fmv_stream_open
#define stream_close fe_fmv_stream_close
#define publish fe_fmv_publish
#define start_pressed fe_fmv_start_pressed
#define start_held fe_fmv_start_held
#define cram_md fe_fmv_cram_md
#define card_step fe_fmv_card_step
#define card_fade fe_fmv_card_fade
#define card_play fe_fmv_card_play
#define card_publish fe_fmv_card_publish
#define ptest_fade fe_fmv_ptest_fade
#define ptest_prepare fe_fmv_ptest_prepare
#define ptest_play fe_fmv_ptest_play
#define fmv_play fe_fmv_play
#define fmv_play_stream fe_fmv_play_stream
#define fmv_test_boot fe_fmv_test_boot
#define fmv_stream_names fe_fmv_stream_names
/* src/fmv_stm.c */
#define fmv_stm_packet_count fe_fmv_stm_packet_count
#define fmv_stm_kind_packet_count fe_fmv_stm_kind_packet_count
#define tag_type fe_fmv_tag_type
#define fmv_stm_packet fe_fmv_stm_packet
#define fmv_packet_frame fe_fmv_packet_frame
#define fmv_frame_pixel fe_fmv_frame_pixel
#define fmv_frame_render_md fe_fmv_frame_render_md
#define fmv_md_to_rgb555 fe_fmv_md_to_rgb555
#define fmv_md_to_rgb888 fe_fmv_md_to_rgb888
#define fmv_stm_pcm fe_fmv_stm_pcm
#define fmv_pcm_sample fe_fmv_pcm_sample
#define md_levels fe_fmv_md_levels
#endif
#endif
