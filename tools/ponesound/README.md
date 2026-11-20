# Reviewed PoneSound firmware source

This directory contains source code, not Sega disc/audio/BIOS assets. Keep LICENSE and the original cWx/ponut64 credit in driver.c.

Upstream: https://github.com/ponut64/SCSP_poneSound, commit c2bd39e177e50549b10c3ca8ecb7776234764e89. The matched original main.c hash is ebb1d8e489dc78f01a43712a9e3137d0140a2859242ca3ba9cf7746b8899ef0f. driver.c is the independently reviewed five-write variant e54d13c8d30a89577fc77077c378b7c8ccdcabd9827369c3193fa1878c2e16e2. Only the pan_send RHS at original lines551,596,627,671,1086 preserve the existing lower byte before updating volume/pan. No other firmware logic changes. driver.ld is exact historical e78aeef39a95fcfe9af02140694e0fdcd049ec8eb304cb84189fa120f6ccf85c.

The accepted GCC13.4.0 recipe is fixed in ../prepare_sound_driver.py. It uses the original CPU/alignment/optimization/no-default-library flags. Do not add libgcc, change CPU options or alter source to accommodate an unexpected compiler failure. The required tools must already exist. No download, install, dependency mutation or target execution occurs.

The producer writes build/sound-driver/driver.elf, driver.bin and report.json. Make uses this persistent driver.bin as sound_driver. Raw output must be8740bytes with SHA ae1f243ab3b9be9ea66dc86904111c42feb8b9817229678f5433c41b80735c6a. ELF vectors/reset/arrays/communication and aligned end0xBD60 below0xC008 are checked by the exact reviewed pure ELF checker. Undefined helpers reject. An ELF hash can differ from the QA build because its source filename changes; the exact allocated firmware bytes must not differ.

By default the tool uses the existing private C-only m68k compiler and existing m68k binutils under this checkout. A fresh source checkout on the same computer may point SCD_M68K_CC, SCD_M68K_NM and SCD_M68K_OBJCOPY to the existing verified external installation. CLI --compiler/--nm/--objcopy is equivalent. Exact tool hashes remain mandatory. Missing tools fail clearly; the producer does not bootstrap them automatically.

The cache requires matching producer/source/helper/contract/tool/flags/stable-environment/OS inputs plus revalidated ELF and exact raw output. The per-job TMPDIR is recorded but excluded from cache identity; no debug/path/time source macro or target include is used. Failed outputs are not a cache pass. Build.sh runs the producer once; Make's order-only prerequisite checks it again and reuses the valid output without another compiler run.

Run the producer only through the existing guarded build workflow. Publication keeps the report pending until both output files are flushed/replaced and the directory is flushed. Failure keeps logs/work files and marks the report failed. The producer does not grant target audio or hardware acceptance.
