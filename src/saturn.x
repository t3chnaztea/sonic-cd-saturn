/*
 * Copyright (c)
 * See LICENSE for details.
 *
 * Joe Fenton <jlfenton65@gmail.com>
 * Israel Jacquez <mrkotfw@gmail.com>
 */

OUTPUT_FORMAT ("elf32-sh")
OUTPUT_ARCH (sh)
EXTERN (_start)
ENTRY (_start)
SEARCH_DIR ("$YAUL_INSTALL_ROOT/$YAUL_ARCH_SH_PREFIX/lib");

/* Copy of yaul's ldscripts/yaul.x (selected by src/saturn.specs) with the zone table
   overlay added. yaul.x's MEMORY region is dropped: its placement counter ignores OVERLAY. */

SECTIONS
{
  . = 0x06004000;
  .text :
  {
     *(.text)
     /* .text.* except the zone code sections .text.z1_* and .text.z3_* to .text.z6_*
        and the front-end code .text.fe_* (overlays below). */
     *(.text.[!zf]*)
     *(.text.f[!e]*)
     *(.text.fe[!_]*)
     *(.text.f .text.fe)
     *(.text.z[!1345678]*)
     *(.text.z[1345678][!_]*)
     *(.text.z .text.z1 .text.z3 .text.z4 .text.z5 .text.z6 .text.z7 .text.z8)
     *(.gnu.linkonce.t.*)

     INCLUDE ldscripts/yaul-c++.x

     . = ALIGN (4);
  }

  /* Zone-only constant tables (src/main.c zone_tables_load): one overlay per zone at a
     shared range; the build writes each to cd/ZTR<n>.BIN and strips it from the program.
     Index tables read across zones stay in .rodata (patterns below match first here).
     Zone code (heap plan B): functions named z1_/z3_/z4_/z5_/z6_ (src/zone_r<n>_names.h,
     build/probe-source/BOSS<n>_ZONE.H) run from their
     zone's overlay. Resident code calls them only through the zone_ops tables kept
     here, and tools/test_zone_code.py audits both rules on every link. */
  .zone_resident :
  {
     . = ALIGN (16);
     *(.rodata.r5_programs*)
     *(.rodata.tt_colitbl*)
     *(.rodata.qq_colitbl*)
     *(.rodata.*zone_ops*)
  }
  . = ALIGN (16);
  ___zone_tables_start = .;
  OVERLAY : NOCROSSREFS AT (0x22400000)
  {
     .zone_R1 { *(.text.z1_*) *(.rodata.placements*) *(.data.r1_b1_*) *(.rodata.r1_b1_*) }
     .zone_R3 { *(.text.z3_*) *(.rodata.r3_*) *(.rodata.cc2_*) *(.data.r3_b3_*) }
     .zone_R4 { *(.text.z4_*) *(.rodata.r4_*) *(.rodata.tt_*) *(.data.r4_b4_*) }
     .zone_R5 { *(.text.z5_*) *(.rodata.r5_*) *(.rodata.qq_*) }
     .zone_R6 { *(.text.z6_*) *(.rodata.r6_*) *(.rodata.ww*) *(.data.r6_b6_*) }
     .zone_R7 { *(.text.z7_*) *(.rodata.r7_*) *(.rodata.ss_*) *(.data.r7_b7_*) }
     .zone_R8 { *(.text.z8_*) *(.rodata.r8_*) *(.data.r8_b8_*) *(.rodata.mm*) }
     /* Front end (title, menus, Time Attack, sound test, ending): fe_ code and data,
        cd/ZTR0.BIN, loaded by scd_frontend_overlay_load (src/main.c). */
     .zone_R0 { *(.text.fe_*) *(.rodata.fe_*) *(.data.fe_*) }
  }
  . = ___zone_tables_start + ((. - ___zone_tables_start + 2047) & ~2047);
  ___zone_tables_end = .;

  /* An explicit address resets the load address to the run address after the overlay. */
  .rodata ___zone_tables_end : AT (___zone_tables_end)
  {
     . = ALIGN (16);

     *(.rdata)
     *(.rodata)
     *(.rodata.*)
     *(.gnu.linkonce.r.*)
  }

  .data :
  {
     . = ALIGN (16);

     *(.data)
     *(.data.*)
     *(.gnu.linkonce.d.*)
     SORT (CONSTRUCTORS)
     *(.sdata)
     *(.sdata.*)
     *(.gnu.linkonce.s.*)
  }

  .bss :
  {
     . = ALIGN (16);
     PROVIDE (___bss_start = .);

     /* libyaul cdfs.c's sector buffer is a __packed union (alignment 1); the CD block
        transfer stores words into it, so an odd address stops the boot (address error). */
     *(.bss._sector)
     . = ALIGN (4);
     *(.bss)
     *(.bss.*)
     *(.gnu.linkonce.b.*)
     *(.sbss)
     *(.sbss.*)
     *(.gnu.linkonce.sb.*)
     *(.scommon)
     *(COMMON)

     . = ALIGN (16);
     PROVIDE (___bss_end = .);
  }

  .uncached (0x20000000 | ___bss_end) : AT (___bss_end)
  {
     *(.uncached)
     *(.uncached.*)

     . = ALIGN (4);
  }

  /* Back to cached addresses */
  ___end = ___bss_end + SIZEOF (.uncached);
}

/* The title's malloc must find a free block of its TLSF class, not just its size. libyaul's
   tlsf.c (FL_INDEX_MAX 30, SL_INDEX_COUNT_LOG2 5, ALIGN 4) rounds a request up with
   mapping_search, (1 << (fls(size) - 5)) - 1, and takes a block from that class's list,
   whose members are at least the class's lower bound. scd_title (src/title.h, 218,776 B,
   malloc'd by src/title_view.inc) therefore needs one free block of 221,184 B.
   Heap use before that malloc (walked from a RAM dump at the title on bin 92b62023):
     3188    TLSF control_t at the pool start (FL 24 x SL 32)
     8       tlsf_pool_add overhead (two 4 B block headers)
     24700   BIOS backup library, src/save_saturn.c bios_memory ((4096+2048+30) x 4) + 4 B header
     16      vdp1_cmdt_list_t (8 B, TLSF minimum block 12 B) + 4 B header, src/main.c sprite_init
     9172    its commands, memalign(32 B vdp1_cmdt_t, (189 + SCD_OBJECT_CAPACITY 96) x 32 = 9,120)
             + alignment 32 + gap_minimum 16 + 4 B header (worst case; measured 9,144)
     221184  the title state's TLSF class bound
     3       tlsf_pool_add aligns the pool size down to 4
   tools/test_zone_tables.py recomputes each term from its source and prints the margin.
   Failing here replaces a disc that stops on BAD TITLE PACKAGE (bin 617bec35 missed by 104 B). */
ASSERT (0x06100000 - ___end >= 3188 + 8 + 24700 + 16 + 9172 + 221184 + 3, "heap cannot give the title state a free block of its TLSF class")
