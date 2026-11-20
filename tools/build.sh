#!/bin/bash
set -euo pipefail
# Batch job: yield the CPU to foreground work (SCD_NICE=0 disables).
renice -n "${SCD_NICE:-20}" -p $$ >/dev/null
cd "$(dirname "$0")/.."
source tools/env.sh
mkdir -p build dist/iso
python3 tools/prepare_cd_block.py
python3 tools/convert_assets.py > build/assets.log
python3 tools/prepare_audio.py > build/audio.log
python3 tools/prepare_japanese_music.py >> build/audio.log
python3 tools/prepare_retail.py  # build/retail/sonic.iso and the programs tools read by path
python3 tools/extract_mmd.py > build/mmd-extract.log
python3 tools/prepare_demos.py > build/demos.log  # cd/DEMOS.BIN: attract demo input from the retail disc
python3 tools/convert_objects.py > build/objects.log
python3 tools/title_card_names.py > build/title-card-names.log
python3 tools/special_assets.py > build/special-assets.log
python3 tools/special_sonic_assets.py > build/special-sonic-assets.log
python3 tools/special_effect_assets.py > build/special-effects-assets.log
python3 tools/special_ufo_assets.py > build/special-ufo-assets.log
python3 tools/special_main_assets.py > build/special-main-assets.log
python3 tools/ss8_credits_assets.py > build/ss8-credits-assets.log
python3 tools/visual_mode_assets.py > build/visual-mode-assets.log  # cd/VISMODE.BIN: Visual Mode menu from VM____.MMD
python3 tools/staff_times_assets.py > build/staff-times-assets.log  # cd/STAFFTIM.BIN: original Best Staff Times
python3 tools/stage_select_assets.py > build/stage-select-assets.log  # cd/STAGESEL.BIN: original Stage Select
python3 tools/coming_assets.py > build/coming-assets.log  # cd/COMING.BIN: original Coming screen
python3 tools/secret_images_assets.py > build/secret-images-assets.log  # cd/SECRET1-5.BIN: sound test pictures from NISI.MMD, DUMMY0-3.MMD
python3 tools/credits_assets.py > build/credits-assets.log  # cd/THANKS.BIN, assets/generated/credits_tables.h
python3 tools/prepare_background.py
python3 tools/background_tables.py  # generated src/background_r*_{tables,palette}.inc (not in git)
python3 tools/inventory_objects.py
python3 tools/prepare_feedback.py > build/feedback.log
python3 tools/prepare_sound_driver.py > build/sound-driver.log  # exact reviewed PoneSound ae1 firmware
python3 tools/hud_assets.py > build/hud-assets.log
python3 tools/prepare_probe.py
python3 tools/prepare_player.py
python3 tools/water_assets.py > build/water-assets.log
python3 tools/camera_source.py > build/camera-source.log
python3 tools/prepare_boss.py
python3 tools/prepare_boss_r3.py
python3 tools/prepare_boss_r4.py
python3 tools/prepare_boss_r5.py
python3 tools/prepare_boss_r6.py
python3 tools/prepare_boss_r7.py
python3 tools/prepare_boss_r8.py
python3 tools/prepare_playsp3.py
python3 tools/title_assets.py > build/title-assets.log
python3 tools/dagarden_assets.py > build/dagarden-assets.log  # cd/DAGARDEN.BIN
python3 tools/sonic_animation_assets.py > build/sonic-animation-assets.log
python3 tools/sonic_frame_assets.py > build/sonic-frame-assets.log
python3 tools/powerup_assets.py > build/powerup-assets.log
# Zone terrain and object layouts come from the harvest in build/auto-extract
# (tools/extract_zone_auto.py); the installer checks every copy and regenerates
# the object layouts, so they cannot drift from the translator.
python3 tools/install_zone_packs.py > build/install-zone-packs.log
python3 tools/zone_object_assets.py > build/zone-object-assets.log
python3 tools/prepare_cc_generator.py > build/cc-generator.log
python3 tools/stage_packs.py > build/stage-packs.log
python3 tools/background_tables.py --terrain  # assets/generated/{tt,qq,ww,mm}_terrain.inc
# Ending movies: the user's STM streams to cd/GOODEND.FMV, BADEND.FMV (and OPN.FMV).
python3 tools/fmv_extract.py > build/fmv-extract.log
python3 tools/fmv_convert.py > build/fmv-convert.log
python3 tools/check_cd_root.py
gmake -j"${SCD_QA_MAX_WORKERS:-4}" "$@"
python3 tools/check_cd_sector_align.py  # libyaul cdfs _sector stays 4-aligned (aec6431)
if [ "$#" -eq 0 ]; then
    python3 tools/package.py
fi
