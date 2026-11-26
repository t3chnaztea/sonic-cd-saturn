ifeq ($(strip $(YAUL_INSTALL_ROOT)),)
  $(error Run: bash tools/build.sh)
endif
include $(YAUL_INSTALL_ROOT)/share/build.pre.mk
SH_PROGRAM:= sonic-cd-saturn-prototype
SH_SRCS:= src/title.c src/title_card.c src/special_main.c src/special_game.c src/special_modes.c src/ss8_credits.c src/special_ufo.c src/special_stage.c src/special_effects.c src/special_effects_runtime.c src/special_contacts.c src/special_sprite.c src/special_player.c src/special_player_qa.c src/special.c src/world_qa.c src/background.c src/background_r3.c src/world.c src/audio.c build/feedback/ponesound.c src/main.c src/stage.c src/core_probe.c src/act.c src/player.c src/player_replay.c src/objects.c src/boss.c src/boss_r3.c src/boss_r4.c src/boss_r5.c src/boss_r6.c src/boss_r7.c src/boss_r8.c build/probe-source/boss_1.c build/probe-source/boss_3.c build/probe-source/boss_4.c build/probe-source/boss_5.c build/probe-source/boss_6.c build/probe-source/boss_7.c build/probe-source/boss_8.c build/probe-source/ending_8.c build/probe-source/playsp3.c build/probe-source/interaction.c build/probe-source/movement.c build/probe-source/player.c build/probe-source/dircol.c build/probe-source/fcol.c build/probe-source/etc.c build/probe-source/equ.c
SH_BUILD_DIR:= build/saturn
SH_SRCS+= build/cd-block/cd-block_cmds.c
SH_SRCS+= src/cd_root.c
SH_SRCS+= src/frontend.c src/time_attack.c
# Visual Mode menu (src/visual_mode.c, cd/VISMODE.BIN from tools/visual_mode_assets.py): R0 code.
SH_SRCS+= src/visual_mode.c src/staff_times.c src/stage_select.c src/coming.c
# D.A. Garden (src/dagarden.c): fe_ code in the front-end overlay R0; src/dagarden_view.inc presents it.
SH_SRCS+= src/dagarden.c
SH_SRCS+= src/save.c src/save_saturn.c
# Optional CD++-style preset moves (docs/CDPP-PRESET-SPEC.md); Classic when its setting is 0.
SH_SRCS+= src/player_plus.c
SH_SRCS+= src/sonic_animation.c src/sonic_frames.c src/powerup_visual.c src/powerup_runtime.c
SH_SRCS+= src/water.c src/water_raster.c src/camera_v.c
# Ending movies (src/ending.c): the player runs from the front-end overlay R0 (src/fmv_fe_names.h).
SH_SRCS+= src/ending.c src/fmv_saturn.c src/fmv_stm.c
# "Thank You" screen (src/credits_saturn.h): R0 code, renamed into the overlay below.
SH_SRCS+= src/credits.c src/credits_saturn.c
SH_SRCS+= src/cdda_law.c src/cdda_provider/cdda_envelope_shadow.c src/cdda_provider/timer_c_shadow.c src/cdda_target_qa_shadow.c
SH_OUTPUT_DIR:= dist/iso
SH_CFLAGS+= -Os -Isrc -Iassets/generated -Ibuild/feedback -Ibuild/probe-source -fsigned-char -fwrapv -fno-strict-aliasing -ffunction-sections -fdata-sections -DR1 -DR11A
# Zone-only constant tables leave the program image (src/saturn.x): each zone's
# overlay becomes cd/ZTR<n>.BIN, which zone_tables_load() in src/main.c reads on a zone change.
# R0 is the front-end overlay (fe_ symbols, src/frontend.c), read by scd_frontend_overlay_load().
ZONE_TABLES:= R1 R3 R4 R5 R6 R7 R8 R0
SH_SPECS:= yaul.specs yaul-main.specs $(abspath src/saturn.specs)
# Keep relocations in the ELF (not the program image) for tools/test_zone_code.py's
# resident->overlay reference audit.
SH_LDFLAGS+= -Wl,--emit-relocs
# Quartz Quadrant's background (background_r5.c, qq_terrain.inc) is served from its overlay.
SH_CFLAGS+= -DSCD_ZONE_R5
# Every zone terrain include the program compiles must exist (src/background*.c #error).
SH_CFLAGS+= -DSCD_REQUIRE_ZONE_TERRAIN
# Zone code overlays (src/zone_r4_names.h, BOSS<n>_ZONE.H): z3_/z4_ names place CC/TT code in its overlay.
SH_CFLAGS+= -DSCD_ZONE_OVERLAY
# LTO's identical code/data folding would alias a resident function or table into an
# overlay body, or join two overlays (tools/test_zone_code.py, NOCROSSREFS). Per-function
# opt-outs are not honoured at LTO time, so folding is off for the whole program.
SH_CFLAGS+= -fno-ipa-icf
SH_LDFLAGS+= -fno-ipa-icf
BUILTIN_ASSETS+= assets/generated/sonic.bin;sonic_bitmap
BUILTIN_ASSETS+= assets/generated/hud-font.bin;hud_font
BUILTIN_ASSETS+= assets/generated/hud-original.bin;hud_original
BUILTIN_ASSETS+= assets/generated/title-card-art.bin;title_card_art
BUILTIN_ASSETS+= build/sound-driver/driver.bin;sound_driver
IP_VERSION:= V0.083
IP_RELEASE_DATE:= 20261123
IP_AREAS:= JTUBKAEL
IP_PERIPHERALS:= J
IP_TITLE:= SONIC CD SATURN FEASIBILITY
IP_MASTER_STACK_ADDR:= 0x06004000
IP_SLAVE_STACK_ADDR:= 0x06001E00
IP_1ST_READ_ADDR:= 0x06004000
IP_1ST_READ_SIZE:= 0
include $(YAUL_INSTALL_ROOT)/share/build.post.iso-cue.mk
# Validate cached firmware inputs/bytes on every consuming make; compile only
# when the exact accepted producer identity/output contract needs renewal.
.PHONY: prepare-sound-driver
prepare-sound-driver:
	$(ECHO)python3 tools/prepare_sound_driver.py
build/sound-driver/driver.bin: | prepare-sound-driver
	@test -f $@
# The disc image carries every file tools/stage_packs.py puts in cd/, not only
# the program. The rule above lists only the program, so a change to a stage
# pack or an object layout alone left dist/iso holding the previous files.
$(SH_OUTPUT_PATH)/$(SH_PROGRAM).iso: $(filter-out cd/A.BIN,$(wildcard cd/*))
$(SH_BUILD_PATH)/$(SH_PROGRAM).elf: src/saturn.x src/saturn.specs
# Replaces build.post.bin.mk's recipe: strip the zone overlays from the program and
# write each one to the CD root before the image is assembled.
$(SH_BUILD_PATH)/$(SH_PROGRAM).bin: $(SH_BUILD_PATH)/$(SH_PROGRAM).elf
	$(ECHO)$(SH_OBJCOPY) -O binary $(foreach z,$(ZONE_TABLES),-R .zone_$(z)) $< $@
	$(ECHO)$(foreach z,$(ZONE_TABLES),$(SH_OBJCOPY) -O binary -j .zone_$(z) $< cd/ZT$(z).BIN &&) true
	@# Link-time guard: overlay prefixes, resident->overlay code refs only through zone_ops,
	@# and only reviewed resident->overlay data refs (tests/zone_data_refs.txt).
	$(ECHO)python3 tools/test_zone_code.py || { rm -f $@; exit 1; }
# Front-end overlay code outside the LTO unit (yaul.specs adds -flto -ffat-lto-objects):
# the object keeps only its real code, so its size cannot move resident inlining
# decisions, and nothing of it can be inlined into resident callers.
SPECIAL_MODES_O:=$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/special_modes.o))
$(SPECIAL_MODES_O): src/special_modes.c
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
VISUAL_MODE_O:=$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/visual_mode.o))
$(VISUAL_MODE_O): src/visual_mode.c
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
STAFF_TIMES_O:=$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/staff_times.o))
$(STAFF_TIMES_O): src/staff_times.c
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
STAGE_SELECT_O:=$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/stage_select.o))
$(STAGE_SELECT_O): src/stage_select.c
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
COMING_O:=$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/coming.o))
$(COMING_O): src/coming.c
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
SS8_CREDITS_O:=$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/ss8_credits.o))
$(SS8_CREDITS_O): src/ss8_credits.c
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
# The "Thank You" screen (src/credits.c, src/credits_saturn.c) is front-end overlay code
# outside LTO; tools/credits_sections.py renames its sections and symbols into .zone_R0.
CREDITS_O:=$(foreach f,credits credits_saturn,$(SH_BUILD_PATH)/$(subst /,@,$(abspath src/$(f).o)))
$(CREDITS_O): $(SH_BUILD_PATH)/$(subst /,@,$(abspath src))@%.o: src/%.c tools/credits_sections.py
	$(ECHO)$(SH_CC) -MT $@ -MF $(basename $@).d -MD $(SH_CFLAGS) $(foreach specs,$(SH_SPECS),-specs=$(specs)) -c -o $@ $<
	$(ECHO)$(SH_OBJCOPY) --remove-section='.gnu.lto_*' $@
	$(ECHO)python3 tools/credits_sections.py $@
