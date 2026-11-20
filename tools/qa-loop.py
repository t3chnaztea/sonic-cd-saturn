#!/usr/bin/env python3
"""Run full, fast, or partial QA; only a clean full pass can gate a package."""
import argparse, datetime, hashlib, json, pathlib, subprocess, time
import os
from qa_limits import atomic_json, cooldown, cooldown_seconds, worker_limit, emulator_limit, _sync_file
from power_guard import inputs as source_inputs
# Batch job: yield the CPU to foreground work (SCD_NICE=0 disables).
try:
    os.nice(int(os.environ.get('SCD_NICE', '20')))
except PermissionError:  # already at the lowest priority
    pass
ROOT=pathlib.Path(__file__).resolve().parents[1]
from zone_release_evidence import matrix_command, release_special, release_zones
release_scope=release_zones(ROOT)
p=argparse.ArgumentParser()
p.add_argument('mode',choices=['fast','full','targeted'])
p.add_argument('--from-report',type=pathlib.Path,help='failed or interrupted full-QA report for targeted mode')
p.add_argument('--list',action='store_true',help='print selected commands without running them')
p.add_argument('--resume',action='append',type=pathlib.Path,default=[],help='reuse verified completed checks from a matching fast/full report')
p.add_argument('--continue-prefix',type=pathlib.Path,help='continue only a verified contiguous prefix from a fresh same-epoch terminal report')
p.add_argument('--resume-matrix',type=pathlib.Path,help='resume an interrupted final zone matrix')
p.add_argument('--migration',type=pathlib.Path,help='explicit hash-bound initial orchestration upgrade')
args=p.parse_args()
try:
    session_limits=dict(host_workers=worker_limit(4),emulators=emulator_limit(2),cooldown_seconds=cooldown_seconds())
except ValueError as error:
    p.error(str(error))
if (args.mode=='targeted') != (args.from_report is not None):
    p.error('--from-report is required only with targeted mode')
if args.continue_prefix and (args.mode=='targeted' or args.migration):
    p.error('--continue-prefix is fast/full only and cannot use a migration')
if args.mode=='targeted' and (args.resume or args.resume_matrix or args.migration):
    p.error('checkpoint recovery uses fast/full mode, not targeted mode')
if args.resume_matrix and (args.mode!='full' or not args.resume):
    p.error('--resume-matrix needs full mode and a source --resume report')
suite_mode='full' if args.mode=='targeted' else args.mode
commands=[['python3','tools/test_assets.py'],['python3','tools/test_objects.py'],['python3','tools/test_sprite_priority.py'],['python3','tools/test_yaul_dma_queue.py'],['python3','tools/test_feedback.py'],['python3','tools/test_special.py'],['bash','tools/test-player.sh'],['bash','tools/test-spring-side.sh'],['bash','tools/test-chain-score.sh'],['bash','tools/test-limit.sh'],['bash','tools/test-spring-contacts.sh'],['bash','tools/test-swing.sh'],['bash','tools/test-boss.sh'],['bash','tools/test-title.sh']]
commands.insert(13,['bash','tools/test-boss6-full.sh'])
commands.insert(14,['python3','tools/test-boss6-retail.py'])
# Catch stored earned-route failures before the long Saturn matrix.
commands[15:15]=[['python3','tools/test_world_post_order.py'],['python3','tools/test_world_restart.py'],['python3','tools/test_ww_campaign_hosts.py']]
if suite_mode=='full':commands.insert(0,['bash','tools/build.sh'])
commands += [['python3','tools/test_hud.py'],['bash','tools/test-sound-bus.sh'],['bash','tools/test-title-scale.sh'],['bash','tools/test-cd-status.sh']]
# The zone table overlays on the CD equal the last link, and the heap ASSERT tracks the title state.
commands.append(['python3','tools/test_zone_tables.py'])
# The zone harvest is used only while its extractor, helpers and retail programs match.
commands.append(['python3','tools/test_install_zone_packs.py'])
# Zone code overlays: every overlay symbol carries its zone prefix, and resident code reaches
# overlay code only through a zone_ops table (heap plan B).
commands.append(['python3','tools/test_zone_code.py'])
# CD++ preset (docs/CDPP-PRESET-SPEC.md): host guard + traces, then the Saturn toggle and
# one emulator route per move. Classic stays protected by tools/test-player.sh.
commands.append(['python3','tools/test_cdpp_player.py'])
# CD++ host fuzz: every zone's Act 1 Present and Act 3 Good Future, no crash, map exit or stall (~30 s cold).
commands.append(['python3','tools/test_cdpp_fuzz.py'])
commands.append(['python3','tools/test_qa_campaign.py'])
commands.append(['python3','tools/test_qa_lifecycle.py'])
commands.append(['python3','tools/test_qa_campaign_emulator.py'])
commands.append(['python3','tools/test_power_guard.py'])
commands.append(['python3','tools/test_qa_limits.py'])
commands.append(['python3','tools/test_qa_dispatch_cooling.py'])
commands.append(['python3','tools/test_package_reuse.py'])
commands.append(['python3','tools/test_qa_os_watch.py'])
commands.append(['python3','tools/cdpp_fuzz.py','--classic'])
commands.append(['python3','tools/test_cdpp_routes.py'])
# Controller-only completion in every zone and boss era; missing routes fail.
if suite_mode=='full':commands.append(['python3','tools/test_cdpp_completion.py'])
# D.A. Garden: host state and lag after every V-INT of six retail routes; in full QA the Saturn
# route (unlock, tracks, retail pictures, exit; build/dagarden-qa/report.json).
commands.append(['python3','tools/test_dagarden.py'])
if suite_mode=='full':commands.append(['python3','tools/test_dagarden_emulator.py'])
# Boot smoke (about 10 s, reads dist/: run fast QA under the build lock): the disc reaches the
# title, the level select and 1,100 Palmtree Panic updates. A link-clean disc that cannot boot fails here.
# Zones 1-4 run CC/TT/QQ/WW code from their overlays: entering each proves no resident
# dispatch reaches a zone overlay that is not loaded (src/zone_code.h).
commands.append(['bash','tools/test-zones-emulator.sh',*[str(z) for z in range(len(release_scope))]])
if 'ss' in release_scope:
    commands += [
        ['python3','tools/test_ss_spring_allocator.py'],
        ['bash','tools/test-ss-actors.sh'],
        ['python3','tools/test-boss7.py'],
        ['bash','tools/test-camera-bounds.sh'],
        ['python3','tools/test_fcol_threshold.py'],
        ['python3','tools/test_lmovecol.py'],
        ['python3','tools/test_ss_campaign_evidence.py'],
    ]
if 'mm' in release_scope:
    # Metallic Madness: R8 actors and BOSS_8/EMIE8 against the compiled originals.
    # (R8 palette, terrain and cache replay run in the asset block for every scope.)
    commands += [
        ['bash','tools/test-mm-actors.sh'],
        ['python3','tools/test-boss8.py'],
    ]
# Act 3 boss art against the retail fights (about 15 s): every TT3/QQ3 boss zone-art record
# equals the live retail actors' tiles, poses and palette in each fight phase.
commands.append(['python3','tools/boss_retail_capture.py'])
# R63C/D boss packs include three beam art states and 14 kinds. Recheck the
# uploaded VDP1 bytes and every original sprite pixel on the current BIN.
commands.append(['python3','tools/test_zone_art_emulator.py','R63C','R63D'])
commands.append(['python3','tools/test_ww_boss_plc_art.py'])
commands.append(['python3','tools/test_ww3_boss_entry_emulator.py'])
commands.append(['python3','tools/test_ww3_boss_full_emulator.py'])
commands.append(['python3','tools/test_japanese_music.py'])
commands.append(['bash','tools/test-save.sh'])
commands.append(['bash','tools/test-time-attack.sh'])
commands.append(['bash','tools/test-cc-bobin.sh'])
commands.append(['bash','tools/test-cc-platform.sh'])
commands.append(['bash','tools/test-cc-drum.sh'])
commands.append(['bash','tools/test-tt-platforms.sh'])
commands.append(['bash','tools/test-cc-movie.sh'])
commands.append(['bash','tools/test-cc-friend.sh'])
commands.append(['bash','tools/test-cc-mecasnc.sh'])
commands.append(['bash','tools/test-cc-mecasnc-original.sh'])
commands.append(['bash','tools/test-cc-sikake33.sh'])
commands.append(['bash','tools/test-tt-actors.sh'])
commands.append(['bash','tools/test-qq-actors.sh'])
commands.append(['bash','tools/test-ww-actors.sh'])
commands.append(['bash','tools/test-playsp5.sh'])
commands.append(['bash','tools/test-water.sh'])
commands.append(['bash','tools/test-water-player.sh'])
commands.append(['bash','tools/test-camera.sh'])
commands.append(['bash','tools/test-cc-traps.sh'])
commands.append(['bash','tools/test-cc-hari3x-mask.sh'])
# QQ2A R5 full redraw with the slave never notified: the 30 V-blank fallback draws both halves.
commands.append(['python3','tools/test_qq_route.py','--act','2','--era','A','--no-retail','--force-r5-fallback','--out','build/qq2/force-r5-fallback'])
commands.append(['bash','tools/test-cc-gandair.sh'])
commands.append(['bash','tools/test-cc-ga.sh'])
commands.append(['bash','tools/test-cc-tentou.sh'])
commands.append(['bash','tools/test-cc-kama.sh'])
commands.append(['bash','tools/test-cc-togeball.sh'])
commands.append(['bash','tools/test-cc-pocket.sh'])
commands.append(['python3','tools/test_pocket_audio.py'])
commands.append(['bash','tools/test-cc-generator.sh'])
commands.append(['python3','tools/prepare_cc_generator.py'])
commands.append(['python3','tools/test_cc_palette.py'])
commands.append(['python3','tools/test_cc_plane.py'])
commands.append(['python3','tools/test_cc_scroll.py']+(['--full'] if suite_mode=='full' else []))
commands.append(['python3','tools/test_cc_scroll.py','--act','2']+(['--full'] if suite_mode=='full' else []))
commands.append(['python3','tools/test_cc_scroll.py','--act','3']+(['--full'] if suite_mode=='full' else []))
commands.append(['python3','tools/test_cc_scroll_target.py'])
commands.append(['python3','tools/test_cc_entry_scene.py'])
if suite_mode=='fast':commands.append(['python3','tools/test_cc_emie_palette.py'])
commands.append(['python3','tools/test_cc_terrain.py'])
commands.append(['bash','tools/test-cc-cache-replay.sh'])
# Tidal Tempest backgrounds: IR tables, compiled-original + retail scroll, COL4A-D, cache pacing.
commands.append(['python3','tools/background_r4_assets.py','--check'])
commands.append(['python3','tools/tt_palette_assets.py','--check'])
commands.append(['python3','tools/test_r4_scroll.py']+(['--full'] if suite_mode=='full' else []))
commands.append(['python3','tools/test_tt_palette.py'])
commands.append(['python3','tools/test_r4_bgv.py'])
commands.append(['python3','tools/test_tt_terrain.py'])
commands.append(['bash','tools/test-tt-cache-replay.sh'])
# Quartz Quadrant backgrounds: IR tables + COL5 scripts, compiled-original + retail scroll, COL5A-D, cache pacing.
commands.append(['python3','tools/background_r5_assets.py','--check'])
commands.append(['python3','tools/test_r5_scroll.py']+(['--full'] if suite_mode=='full' else []))
commands.append(['python3','tools/test_r5_palette.py'])
commands.append(['bash','tools/test-qq-cache-replay.sh'])
commands.append(['python3','tools/test_qq_switch_margin.py'])
commands.append(['python3','tools/test_candidate_identity.py'])
commands.append(['python3','tools/test_zone_release_evidence.py'])
# Original-program emulator gates (about 17 s together).
commands += [['python3','tools/capture_r5_plane.py','--all'],['python3','tools/qq_terrain_assets.py','--check']]
commands += [['python3','tools/capture_r4_plane.py','--all'],['python3','tools/test_r4_scrchk.py'],['python3','tools/tt_terrain_assets.py','--check']]
# Wacky Workbench backgrounds: IR tables, compiled-original + retail scroll, COL6A-D, retail animated tiles, cache pacing, plane B.
commands.append(['python3','tools/background_r6_assets.py','--check'])
commands.append(['python3','tools/ww_palette_assets.py','--check'])
commands.append(['python3','tools/capture_r6_scroll.py','--all'])
commands.append(['python3','tools/test_r6_scroll.py']+(['--full'] if suite_mode=='full' else []))
commands.append(['python3','tools/test_ww_palette.py'])
commands.append(['python3','tools/ww_terrain_assets.py','--check'])
commands.append(['python3','tools/test_ww_terrain.py'])
commands.append(['bash','tools/test-ww-cache-replay.sh'])
commands.append(['python3','tools/capture_r6_plane.py','--all'])
# Stardust Speedway backgrounds: retail scroll() parse, retail captures, COL7A/D vs retail CRAM, cache pacing, plane B.
commands.append(['python3','tools/background_r7_assets.py','--check'])
commands.append(['python3','tools/ss_palette_assets.py','--check'])
commands.append(['python3','tools/capture_r7_scroll.py','--all'])
commands.append(['python3','tools/test_r7_scroll.py'])
commands.append(['python3','tools/test_ss_palette.py'])
commands.append(['python3','tools/test_zone_art_palette.py'])
commands.append(['bash','tools/test-ss-cache-replay.sh'])
commands.append(['python3','tools/capture_r7_plane.py','--all'])
# Metallic Madness backgrounds (same retail engine as R7): palette/tiles vs retail CRAM/VRAM, captures, cache, plane B.
commands.append(['python3','tools/mm_palette_assets.py','--check'])
commands.append(['python3','tools/mm_terrain_assets.py','--check'])
commands.append(['python3','tools/capture_r8_scroll.py','--all'])
commands.append(['python3','tools/test_r8_scroll.py'])
commands.append(['python3','tools/test_mm_palette.py'])
commands.append(['python3','tools/test_mm_terrain.py'])
commands.append(['bash','tools/test-mm-cache-replay.sh'])
commands.append(['python3','tools/capture_r8_plane.py','--all'])
commands += [['bash','tools/test-zone-objects.sh'],['python3','tools/test_object_layouts.py'],['python3','tools/test_zone_object_art.py'],['python3','tools/test_zone_stream.py'],['bash','tools/test-collapse-spawn.sh'],['python3','tools/test_cc_audio.py'],['python3','tools/test_tt_audio.py'],['bash','tools/test-playsp3.sh']]
commands.append(['python3','tools/test_hud_render.py'])
commands.append(['python3','tools/test_title_cycles.py'])
commands.append(['python3','tools/test_camera_pixels.py'])
commands.append(['python3','tools/test_sprite_composition.py'])
commands.append(['bash','tools/test-background-cache.sh'])
commands.append(['bash','tools/test-foreground-cache.sh'])
commands.append(['bash','tools/test-arrival-camera.sh'])
commands.append(['bash','tools/test-object-stream.sh'])
commands.append(['python3','tools/test_ring_allocator.py'])
commands.append(['bash','tools/test-sonic-animation.sh'])
commands.append(['python3','tools/test_player_animation.py'])
commands.append(['python3','tools/test_player_air_animation.py'])
commands.append(['python3','tools/test_player_arrival.py'])
commands.append(['python3','tools/test_player_checkpoint.py'])
commands.append(['python3','tools/test_checkpoint_clock.py'])
commands.append(['python3','tools/test_title_card.py'])
commands.append(['python3','tools/test_sprite_order.py'])
commands.append(['python3','tools/test_powerup_visual.py'])
commands.append(['bash','tools/test-powerup-runtime.sh'])
commands.append(['bash','tools/test-sonic-view.sh'])
commands.append(['bash','tools/test-act-pacing.sh'])
for script in ['tools/test-world.sh']:
    if (ROOT/script).exists():commands.append(['bash',script])
if suite_mode=='full':commands += [['python3','tools/test_disc_dependency.py'],['python3','tools/package.py'],['bash','tools/test-emulator.sh'],['bash','tools/test-title-emulator.sh'],['bash','tools/test-stage-load-failure.sh'],['bash','tools/test-audio.sh'],['bash','tools/test-audio-diagnostics.sh'],['python3','tools/test_zone_music.py'],['bash','tools/test-world-emulator.sh'],['bash','tools/test-act-emulator.sh'],['bash','tools/test-act2-emulator.sh'],['bash','tools/test-act3-emulator.sh'],['bash','tools/test-sequence-emulator.sh'],['bash','tools/test-bigring-emulator.sh'],['bash','tools/test-special-emulator.sh'],['bash','tools/test-special-game-emulator.sh']]
# Pencil test (Visual Mode): PTEST.FMV against the retail PTEST.MMD run in the Sega CD core
# (tools/fmv_retail.py ptest): every picture, pacing, fades, screens, back to the menu.
if suite_mode=='full':commands.append(['python3','tools/test_fmv_emulator.py'])
# Visual Mode menu: cd/VISMODE.BIN drawn as the Mega Drive would, pixel for pixel against
# the retail VM____.MMD screens (tools/visual_mode_retail.py), all five selections.
commands.append(['python3','tools/visual_mode_pixels.py'])
# Visual Mode in the emulator: the menu screens against retail, input, fades, the opening
# (Start skip) and exit; then the good ending + "Thank You" hook, bad ending and pencil test.
if suite_mode=='full':commands.append(['python3','tools/test_frontend_emulator.py','visual-mode','visual-mode-movies','sound-test-images'])
if suite_mode=='full':commands.append(['python3','tools/test_ta_full_emulator.py'])
# RAM DATA can switch presets while the frontend overlay remains loaded.
if suite_mode=='full':commands.append(['python3','tools/test_frontend_preset_switch.py'])
# Credits audit (docs/CREDITS-AUDIT.md). "Thank You" screen: src/credits.c against the PC
# sources and, in its Sega CD mode, against the retail THANKS_M.MMD run (all 64 actors,
# sprites, colours, names). Full: the Saturn pictures against retail, and the staff roll,
# end screen and "PRESENTED BY SEGA" card of both endings against the retail ENDING.MMD.
commands.append(['python3','tools/test_credits.py'])
if suite_mode=='full':commands += [['python3','tools/test_credits_emulator.py'],['python3','tools/test_credits_roll_emulator.py']]
# The three era routes and the ring-loss stress route were in no driver, so
# nothing ran them between V0.037 and V0.057 and all four had gone red
# unnoticed. Keep them in full mode so that cannot happen again.
if suite_mode=='full':
    commands.append(['python3','tools/test_cc_generator_route.py','--act2'])
    # Tidal Tempest Act 3 boss fixture probe (C, D): BOSS_4.C/BOSS_4_2.C hits, capsule
    # and the Quartz Quadrant Act 1 handoff. Host parity runs in fast (tools/test-boss.sh).
    commands.append(['python3','tools/test_tt3_boss_emulator.py'])
    # Position-matched CC3 controller routes (C, D): boss under its track,
    # capsule, tally and the Tidal Tempest Act 1 handoff.
    commands.append(['python3','tools/test_cc3_route.py'])
    # probe_cc_route.py (exploratory Right/Jump heuristic, not acceptance) was
    # dropped here: PLAYSP3.C bumpers stop it, and test_cc2_route.py --act 2 below
    # proves era B into Act 3 with a position-matched controller route.
    # Position-matched level-select controller routes, all four eras: CC1 into
    # Act 2 and CC2 into Act 3 (A's cache-spike late frames are fixed).
    commands.append(['python3','tools/test_cc2_route.py','--act','1'])
    commands.append(['python3','tools/test_cc2_route.py','--act','2'])
    # Ring-scatter stress: seed 24's CC2 Good Future route loses at least 30
    # rings (up to 32 scattered) in one
    # update; it must stay within one refresh.
    commands.append(['python3','tools/test_cc2_route.py','--act','2','--era','C','--seed','24','--require-ring-loss','30'])
    # Host/Saturn regression: seed 28 (35-ring drop) split 4 px at sequence 5542
    # while CC explosions read their scripts from TT overlay bytes (2ae3255).
    commands.append(['python3','tools/test_cc2_route.py','--act','2','--era','C','--seed','28','--require-ring-loss','30'])
    commands.append(['python3','tools/prepare_cc_campaign_checkpoint.py'])
    # Earned CC3-entry saves (Good C and Bad D) from the checkpoint above (~15 min).
    commands.append(['python3','tools/test_cc_campaign_act3.py'])
    # Replay from the current-hash saves just earned by the campaign gate.
    commands.append(['python3','tools/test_cc3_route.py','--continue'])
    commands.append(['python3','tools/test_cc_campaign_generator.py','--milestone','continue'])
    commands += [['python3','tools/test_save_matrix.py'],['python3','tools/test_save_progression.py']]
    commands += [['bash','tools/test-zones-emulator.sh'],['python3','tools/test_zone_art_emulator.py']]
    commands += [['bash','tools/test-act2-era-emulator.sh',str(era)] for era in (1,2,3)]
    commands.append(['bash','tools/test-past-ring-loss.sh',
                     str(ROOT/'tests/routes/ppz/p1B.txt'),
                     str(ROOT/'build/act2-past-stress-qa-loop')])
    # Zones block: the per-zone bar (retail parity, stored routes, per-sprite
    # art, natural travel, campaign) for every finished zone, one driver call.
    # From V0.078 the same matrix also runs the special-stage cases (zone 'sp').
    commands.append([*matrix_command(release_scope, release_special(ROOT)), '--jobs', '1'])
start_step=0
source_report=None
source_path=None
if args.mode=='targeted':
    source_path=args.from_report.resolve()
    source_report=json.loads(source_path.read_text())
    if source_report.get('mode') not in ('full','targeted') or source_report.get('passed') or source_report.get('partial_passed'):
        p.error('targeted mode needs a failed or interrupted full/targeted report')
    prior=source_report.get('steps',[])
    start_step=source_report.get('start_step',0)
    if not isinstance(start_step,int) or start_step<0 or start_step+len(prior)>len(commands):
        p.error('source report has an invalid step range')
    for offset,step in enumerate(prior):
        if step.get('command')!=commands[start_step+offset]:
            p.error(f'QA command list changed at step {start_step+offset}; start a clean full run')
        if offset<len(prior)-1 and step.get('exit_code')!=0:
            p.error('source report has a failure before its last step')
    if prior and prior[-1].get('exit_code')!=0:
        start_step+=len(prior)-1
    else:
        start_step+=len(prior)
    if start_step==len(commands):
        p.error('source report has no failed or uncompleted steps')
    source_disc=source_report.get('disc_sha256')
    disc=ROOT/'dist/sonic-cd-saturn-prototype.bin'
    current_disc=hashlib.sha256(disc.read_bytes()).hexdigest() if disc.exists() else None
    if source_disc and current_disc!=source_disc:
        # Older targeted reports recorded the input BIN only. A successful
        # package.py step regenerates it; accept that known output if its
        # package manifest still binds to the current BIN.
        packaged=any(step.get('command')==['python3','tools/package.py'] and step.get('exit_code')==0 for step in prior)
        manifest=ROOT/'dist/build-report.json'
        packaged_sha=(json.loads(manifest.read_text()).get('files',{}).get(disc.name,{}).get('sha256')
                      if packaged and manifest.exists() else None)
        if current_disc!=packaged_sha:
            p.error('disc changed since source report; start a clean full run')
selected=commands[start_step:]
if args.list:
    for n,cmd in enumerate(selected,start_step):print(f'{n}: '+' '.join(cmd))
    raise SystemExit(0)
import shutil
if not args.resume and (args.mode=='full' or any(cmd[:2]==['bash','tools/test-past-ring-loss.sh'] for cmd in selected)):
    shutil.rmtree(ROOT/'build/act2-past-stress-qa-loop',ignore_errors=True)
(ROOT/'build').mkdir(exist_ok=True)
(ROOT/'build/qa-loops').mkdir(exist_ok=True)
out=ROOT/'build/qa-loops'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');out.mkdir()
report={'mode':args.mode,'steps':[],'passed':False,'status':'pending',
        'pid':os.getpid(),'session_limits':session_limits,'source_sha256':source_inputs()}
import qa_resume
report['bios_inputs']=qa_resume.bios_inputs(ROOT)
report['execution_environment']=qa_resume.execution_environment()
report['reference_inputs']=qa_resume.preserve_reference_inputs(ROOT,qa_resume.reference_inputs(ROOT))
migration=json.loads(args.migration.read_text()) if args.migration else None
report['checkpoint_context']=qa_resume.context(ROOT,report['source_sha256'])
report['orchestration_migration']=(dict(path=str(args.migration.resolve()),sha256=qa_resume.digest(args.migration))
                                   if args.migration else None)
report['prefix_continuation_protocol']=qa_resume.PREFIX_PROTOCOL
report['continued_prefix_checks']=0
atomic_json(out/'report.json',report)
try:
    prefix_cache=qa_resume.completed_prefix(ROOT,args.mode,commands,report,args.continue_prefix) if args.continue_prefix else {}
except BaseException as error:
    report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',passed=False,error=repr(error))
    try:atomic_json(out/'report.json',report)
    except BaseException as secondary:error.add_note('Prefix admission checkpoint failed: '+repr(secondary))
    raise
report['resume_enabled']=bool(args.resume)
resume_cache,resume_sources=qa_resume.cached_steps(ROOT,args.mode,commands,
    report['checkpoint_context'],args.resume,migration) if args.resume else ({},[])
matrix_source=args.resume[-1] if args.resume else None
if args.mode=='full' and args.resume and not args.resume_matrix:
    for source in reversed(args.resume):
        discovered=qa_resume.discover_matrix(ROOT,source,commands)
        if discovered:
            args.resume_matrix=discovered
            matrix_source=source
            break
if args.resume_matrix and migration:
    sealed_source=migration.get('legacy_matrices',{}).get(str(args.resume_matrix.resolve()),{}).get('source_report')
    if sealed_source:
        if pathlib.Path(sealed_source).resolve() not in [s.resolve() for s in args.resume]:
            p.error('legacy matrix source must be included in --resume reports')
        matrix_source=pathlib.Path(sealed_source)
report['resume_sources']=resume_sources
report['reused_checks']=0
report['consumer_input_protocol']=qa_resume.CONSUMER_PROTOCOL
if args.resume_matrix:
    report['resume_matrix']=str(args.resume_matrix.resolve())
    report['resume_matrix_source']=str(matrix_source.resolve())
    report['migration']=str(args.migration.resolve()) if args.migration else None
if args.mode=='targeted':
    disc=ROOT/'dist/sonic-cd-saturn-prototype.bin'
    report.update({'start_step':start_step,'source_report':str(source_path),'source_report_sha256':hashlib.sha256(source_path.read_bytes()).hexdigest(),
                   'disc_sha256':current_disc,'input_disc_sha256':current_disc,
                   'qa_loop_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
                   'partial_passed':False,'release_eligible':False})
atomic_json(out/'report.json',report)
last_job_finished=time.monotonic()
for n,cmd in enumerate(selected,start_step):
    report['active_step']=n
    if 'bios_inputs' in report:
        qa_resume.checkpoint_bios_inputs(ROOT,report,lambda:atomic_json(out/'report.json',report))
    if n in prefix_cache:
        try:
            continued=qa_resume.consume_prefix_step(ROOT,args.mode,commands,report,prefix_cache[n],n)
        except BaseException as error:
            report.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',failed_step=n,error=repr(error))
            try:atomic_json(out/'report.json',report)
            except BaseException as secondary:error.add_note('Prefix consumer checkpoint failed: '+repr(secondary))
            raise
        report['steps'].append(continued)
        report['continued_prefix_checks']+=1
        atomic_json(out/'report.json',report)
        print(f'CONTINUE {n}: '+ ' '.join(cmd),flush=True)
        continue
    if report.get('resume_enabled') and n in resume_cache:
        reused=qa_resume.consume_cached_step(ROOT,args.mode,commands,
            report['checkpoint_context'],resume_cache[n],n,migration)
        if reused is not None:
            report['steps'].append(reused)
            report['reused_checks']+=1
            atomic_json(out/'report.json',report)
            print(f'REUSE {n}: '+ ' '.join(cmd),flush=True)
            continue
    report.update(status='cooling',active_step=n)
    atomic_json(out/'report.json',report)
    if session_limits['cooldown_seconds']:print(f'COOLING: {session_limits["cooldown_seconds"]:g}s before step {n}',flush=True)
    try:
        cooldown(last_job_finished,seconds=session_limits['cooldown_seconds'])
    except KeyboardInterrupt:
        report.update(status='interrupted',interrupted_step=n)
        atomic_json(out/'report.json',report)
        print(f'INTERRUPTED: {out}/report.json',flush=True)
        raise SystemExit(130)
    except Exception as error:
        report.update(status='failed',failed_step=n,passed=False,error=repr(error))
        try:atomic_json(out/'report.json',report)
        except BaseException as secondary:error.add_note('Failed command checkpoint: '+repr(secondary))
        raise
    if 'bios_inputs' in report:
        qa_resume.checkpoint_bios_inputs(ROOT,report,lambda:atomic_json(out/'report.json',report))
    try:
        qa_resume.publish_consumer_context(ROOT,report['checkpoint_context'])
        # Finite source-defined setup, with its own log/receipt. These jobs are
        # not canonical QA commands or evidence for a window's functional pass.
        for setup_command in qa_resume.fixed_setup_commands(ROOT,report['checkpoint_context'],[cmd]):
            cooldown(last_job_finished,seconds=session_limits['cooldown_seconds'])
            qa_resume.verify_execution_inputs(ROOT,report['bios_inputs'],report['execution_environment'],report['reference_inputs'])
            step=dict(command=setup_command,status='running',counts_as_qa=False,
                retained_outputs=qa_resume.preserve_fixed_producer_outputs(ROOT,setup_command))
            report.setdefault('input_preparations',[]).append(step)
            atomic_json(out/'report.json',report)
            setup_log=out/('input-preparation-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.log')
            try:
                setup_before=qa_resume.consumer_inputs(ROOT,qa_resume.consumer_spec(ROOT,[setup_command]),context=report['checkpoint_context'])
                if any(d['command']==setup_command for d in qa_resume._FIXED_PRODUCERS.values()) and not setup_before['complete']:
                    raise ValueError('Fixed producer inputs incomplete: '+str(setup_before['unsupported']))
                with setup_log.open('x') as stream:
                    setup_result=subprocess.run(setup_command,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
                    stream.flush();_sync_file(stream.fileno())
                step['exit_code']=setup_result.returncode
                qa_resume.verify_consumer_inputs(ROOT,setup_before)
                if setup_result.returncode!=0:raise ValueError('Fixed consumer preparation failed')
                step['producer_outputs']=qa_resume.producer_outputs(ROOT,setup_command,context=report['checkpoint_context'],consumer=setup_before,
                    log=dict(path=str(setup_log.relative_to(ROOT)),sha256=qa_resume.digest(setup_log)),exit_code=setup_result.returncode)
                step['status']='passed'
            except BaseException as error:
                step.update(status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',error=repr(error))
                last_job_finished=time.monotonic()
                try:
                    if setup_log.exists():step.update(log=str(setup_log.relative_to(ROOT)),log_sha256=qa_resume.digest(setup_log))
                    atomic_json(out/'report.json',report)
                except BaseException as secondary:error.add_note('Preparation terminal checkpoint failed: '+repr(secondary))
                raise
            step.update(log=str(setup_log.relative_to(ROOT)),log_sha256=qa_resume.digest(setup_log))
            last_job_finished=time.monotonic()
            atomic_json(out/'report.json',report)
        if qa_resume.fixed_producer_requirements([cmd]):
            cooldown(last_job_finished,seconds=session_limits['cooldown_seconds'])
            qa_resume.verify_execution_inputs(ROOT,report['bios_inputs'],report['execution_environment'],report['reference_inputs'])
        recipe=qa_resume.consumer_spec(ROOT,[cmd])
        consumer=qa_resume.consumer_inputs(ROOT,recipe,
            context=report['checkpoint_context'])
        if ((recipe['native'] or cmd==['python3','tools/test_cc_palette.py'] or qa_resume.fixed_producer_requirements([cmd]))
                and any(reason!=qa_resume._ALTERNATE_SOURCE_LIMIT for reason in consumer['unsupported'])):
            raise ValueError('Known native/producer input identity incomplete: '+str(consumer['unsupported']))
        consumer_seal=qa_resume.preserve_consumer_inputs(ROOT,consumer)
    except BaseException as error:
        report.update(passed=False,status='interrupted' if isinstance(error,KeyboardInterrupt) else 'failed',
                      failed_step=n,error=repr(error))
        try:atomic_json(out/'report.json',report)
        except BaseException as secondary:error.add_note('Consumer checkpoint failed: '+repr(secondary))
        raise
    report['status']='running'
    atomic_json(out/'report.json',report)
    start=time.monotonic();log=out/f'{n:02d}.log'
    if report.get('resume_enabled') and cmd[:2]==['bash','tools/test-past-ring-loss.sh']:
        prior_output=ROOT/'build/act2-past-stress-qa-loop'
        if prior_output.exists():
            prior_output.rename(prior_output.with_name(prior_output.name+'.interrupted-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
    actual_cmd=cmd
    if report.get('resume_matrix') and cmd[:2]==['python3','tools/zone-gates.py']:
        actual_cmd=[*cmd,'--resume',report['resume_matrix'],'--resume-source-report',report['resume_matrix_source']]
        if report.get('migration'):actual_cmd+=['--migration',report['migration']]
    print('RUN '+' '.join(actual_cmd),flush=True)
    if 'bios_inputs' in report:
        qa_resume.checkpoint_bios_inputs(ROOT,report,lambda:atomic_json(out/'report.json',report))
    try:
        with log.open('w') as f:
            result=subprocess.run(actual_cmd,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,
                                  env=qa_resume.consumer_environment(report['checkpoint_context'],cmd))
            f.flush();_sync_file(f.fileno())
    except KeyboardInterrupt:
        report.update({'status':'interrupted','interrupted_step':n})
        atomic_json(out/'report.json',report)
        print(f'INTERRUPTED: {out}/report.json',flush=True)
        raise SystemExit(130)
    except Exception as error:
        report.update(status='failed',failed_step=n,passed=False,error=repr(error))
        try:atomic_json(out/'report.json',report)
        except BaseException as secondary:error.add_note('Failed command checkpoint: '+repr(secondary))
        raise
    if 'bios_inputs' in report:
        qa_resume.checkpoint_bios_inputs(ROOT,report,lambda:atomic_json(out/'report.json',report))
    try:
        qa_resume.verify_consumer_inputs(ROOT,consumer)
    except (OSError,ValueError,TypeError) as error:
        report.update(passed=False,status='failed',failed_step=n,error=str(error))
        report['steps'].append(dict(command=actual_cmd,canonical_command=cmd,
            exit_code=result.returncode,log=str(log.relative_to(ROOT)),
            log_sha256=qa_resume.digest(log),consumer_inputs=consumer_seal,
            input_identity_complete=False,input_error=str(error)))
        atomic_json(out/'report.json',report)
        print(f'FAIL: consumer input identity: {error}; {out}/report.json',flush=True)
        raise SystemExit(1)
    report['steps'].append({'command':actual_cmd,'canonical_command':cmd,'exit_code':result.returncode,'seconds':round(time.monotonic()-start,2),'log':str(log.relative_to(ROOT)),'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),
                          'consumer_inputs':consumer_seal,'input_identity_complete':consumer['complete'],
                          **({'bios_inputs':report['bios_inputs']} if 'bios_inputs' in report else {}),
                          **({'execution_environment':report['execution_environment']} if 'execution_environment' in report else {}),
                          **({'reference_inputs':report['reference_inputs']} if 'reference_inputs' in report else {})})
    if result.returncode==0:
        try:
            produced=qa_resume.producer_outputs(ROOT,cmd,context=report['checkpoint_context'],consumer=consumer,
                log=dict(path=str(log.relative_to(ROOT)),sha256=hashlib.sha256(log.read_bytes()).hexdigest()),exit_code=result.returncode)
            if produced is not None:
                if any(not value['present'] for value in produced['files'].values()):
                    raise ValueError('Successful producer omitted required input output')
                report['steps'][-1]['producer_outputs']=produced
        except Exception as error:
            report.update(passed=False,status='failed',failed_step=n,error=str(error))
            atomic_json(out/'report.json',report)
            raise
    if suite_mode=='full' and result.returncode==0 and cmd in (['bash','tools/build.sh'],['python3','tools/package.py']):
        report['disc_sha256']=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest()
        if report.get('checkpoint_context'):
            report['checkpoint_context']['bin_sha256']=report['disc_sha256']
    if suite_mode=='full' and result.returncode==0 and cmd[:2]==['python3','tools/zone-gates.py']:
        try:
            lines=log.read_text().splitlines()
            matrix_line=next((line for line in reversed(lines) if line.startswith('PASS: ')),None)
            if matrix_line:
                matrix_path=pathlib.Path(matrix_line.removeprefix('PASS: '))
                matrix_path=(ROOT/matrix_path).resolve()
                report['zone_gates_report']=str(matrix_path.relative_to(ROOT))
                report['zone_gates_report_sha256']=hashlib.sha256(matrix_path.read_bytes()).hexdigest()
        except (OSError,ValueError) as error:
            report.update(passed=False,status='failed',failed_step=n,error=str(error))
            atomic_json(out/'report.json',report)
            print(f'FAIL: matrix evidence: {error}; {out}/report.json',flush=True)
            raise SystemExit(1)
    atomic_json(out/'report.json',report)
    last_job_finished=time.monotonic()
    if result.returncode:
        report.update({'status':'failed','failed_step':n})
        atomic_json(out/'report.json',report)
        print(log.read_text()[-6000:]);print(f'FAIL: {log}',flush=True);raise SystemExit(result.returncode)
if args.mode=='targeted':
    report.update({'partial_passed':True,'status':'partial_passed'})
else:
    report.update({'passed':True,'status':'passed'})
try:
    qa_resume.checkpoint_bios_inputs(ROOT,report,lambda:atomic_json(out/'report.json',report))
    qa_resume.verify_stable_consumer_inputs(ROOT,[row['consumer_inputs'] for row in report['steps']
                                               if row.get('consumer_inputs')])
    report['cache_identity_incomplete_steps']=[i for i,row in enumerate(report['steps'])
                                             if row.get('input_identity_complete') is not True]
    if report.get('orchestration_migration'):
        if qa_resume.digest(args.migration)!=report['orchestration_migration']['sha256']:
            raise SystemExit('Orchestration migration changed during the run')
    if args.mode=='full':
        report['disc_sha256']=hashlib.sha256((ROOT/'dist/sonic-cd-saturn-prototype.bin').read_bytes()).hexdigest()
        report['hardware_tested']=False
        report['report_hashes']={}
        for name in ['player-report.json','emulator-report.json','audio-report.json','audio-diagnostic-report.json','world-report.json','act-report.json','act2-report.json','act3-report.json','sequence-report.json','bigring-report.json','title-report.json','special-report.json','special-game-report.json']:
            path=ROOT/'dist'/name
            if json.loads(path.read_text()).get('disc_sha256')!=report['disc_sha256']:
                raise SystemExit(f'{name} does not match the final disc')
            report['report_hashes'][name]=hashlib.sha256(path.read_bytes()).hexdigest()
        campaign=ROOT/'build/cc1/generator/campaign-generated/report.json'
        campaign_report=json.loads(campaign.read_text())
        if not campaign_report['passed'] or campaign_report['disc_sha256']!=report['disc_sha256']:
            raise SystemExit('CC1 campaign report does not match the final disc')
        report['campaign_report_sha256']=hashlib.sha256(campaign.read_bytes()).hexdigest()
        # CC2 Past into Act 3: the position-matched controller route
        # (tools/test_cc2_route.py --act 2), which replaced the heuristic probe.
        cc2=ROOT/'build/cc2/controller/B/report.json'
        cc2_report=json.loads(cc2.read_text())
        if (not cc2_report['passed'] or cc2_report['respawns'] or cc2_report['late_gameplay_intervals'] or
            len(cc2_report['stage_transitions'])!=1 or cc2_report['stage_transitions'][0]['after'][:2]!=[1,2] or
            cc2_report['disc_sha256']!=report['disc_sha256']):
            raise SystemExit('CC2 Past handoff report does not match the final disc')
        report['cc2_past_handoff_report_sha256']=hashlib.sha256(cc2.read_bytes()).hexdigest()
        from zone_release_evidence import audit
        audit(ROOT,report,report['disc_sha256'])
        atomic_json(ROOT/'dist/qa-report.json',report)
except (Exception,SystemExit) as error:
    report.update(passed=False,status='failed',error=str(error))
    atomic_json(out/'report.json',report)
    print(f'FAIL: final report validation: {error}; {out}/report.json',flush=True)
    raise
atomic_json(out/'report.json',report)
print(f'{"PARTIAL PASS" if args.mode=="targeted" else "PASS"}: {out}/report.json')
