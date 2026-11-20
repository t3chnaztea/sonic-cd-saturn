# Design note (c): Quartz Quadrant mapwrtb redraw on the slave SH-2

Status: implemented in the uncommitted V0.066 worktree. Focused emulator
evidence exists; final candidate QA and hardware acceptance remain open.
See `../../QUARTZ-QUADRANT-PLAN.md` for current gates. The sketch and estimates
below describe the original proposal, not the final implementation.

## Why

Option (a) is on the branch. The switch frame writes no BG rows, and frame N+1
does the full redraw, as GAME5.C:353 mapwrtb does. All 8 non-freezing QQ routes
now pass with 0 late intervals. The worst redraw frame is QQ2A seq 1692, at
47,502 FRT ticks. The lowest late frame measured is 49,355 ticks (QQ2A before
the fix), so the margin is 1,853 ticks. That is below the 2,000-tick gate. QQ2C
showed a 47,694-tick frame that pushed the next frame late, so the real margin
may be smaller.

The redraw frame's fill is 30 rows × 64 tiles and costs 11.3-12.6k ticks. C
tuning has reached a floor. Five loop rewrites all measure 11.3-12.2k. A
calibration run shows about 75 compute cycles per tile pair with GCC's SH code.
LWRAM and HWRAM have no room for a PND lookup table.

## Slave availability

`grep -rn "cpu_dual\|slave" src/` finds slave use only in the special stage
(`src/special_view.inc`, `src/special_game_view.inc`). `special_slave_stop()`
runs `cpu_dual_slave_clear(); smpc_smc_sshoff_call();` whenever gameplay
resumes. So the slave is off (SSHOFF) during zone gameplay, and the zone may use
it. The zone must start it with SSHON and stop it before a special stage starts
its own slave (see `special_slave_start`).

## Split

Master (unchanged order): map_update, then row_start/static for all 30 rows.
row_start reads R5 overlay state and must stay on the master. The master does
all cache bookkeeping (`bg_row_world`, `bg_row_keys`) and fills rows
by/8..by/8+14. The slave fills rows by/8+15..by/8+29 through
`scd_background_fill_row`, which is pure: it reads `stage` parts and writes one
64-word ring row. The master then waits for the slave and enqueues the one DMA
span.

Cache rules:
- The slave runs `cpu_cache_purge()` at job start. mapset2's chunk memcpy on
  frame N went through the master's write-through cache to LWRAM, but the slave
  may still hold old lines.
- The slave's writes to `maps[1]` are write-through, so memory is current. SCU
  DMA reads memory. The master never reads `maps[1]` rows back.
- Job parameters go in an uncached mailbox (address | 0x20000000), as the
  special stage does.

Expected cost on the redraw frame: master ~6k fill plus the wait for the
slave's ~6k, overlapped. That saves about 5-6k ticks and gives a margin of
roughly 7k.

## main.c patch (sketch, against the branch)

```c
/* file scope */
#include <cpu/dual.h>
typedef struct { const stage_t *stage; uint32_t *map; int n; int y[15],first[15],end[15],fixed[15],slot[15]; volatile uint32_t go,done; } bg_slave_job_t;
static bg_slave_job_t bg_slave_job_storage __aligned(16);
#define bg_slave_job ((volatile bg_slave_job_t *)((uintptr_t)&bg_slave_job_storage|0x20000000))
static int bg_slave_ready;
static void bg_slave_entry(void){
    cpu_cache_purge();
    for(int i=0;i<bg_slave_job->n;i++)
        scd_background_fill_row(bg_slave_job->stage,bg_slave_job->map+bg_slave_job->slot[i]*64,
            bg_slave_job->y[i],bg_slave_job->first[i],bg_slave_job->end[i],bg_slave_job->fixed[i]);
    bg_slave_job->done=bg_slave_job->go;
}
static void bg_slave_start(void){ /* zone entry, after special_slave_stop() */
    if(bg_slave_ready)return;
    input_ready=0;cpu_dual_comm_mode_set(CPU_DUAL_ENTRY_ICI);cpu_dual_slave_set(bg_slave_entry);input_ready=1;
    bg_slave_ready=1;
}
static void bg_slave_stop(void){ /* before special_slave_start() and on title return */
    if(!bg_slave_ready)return;
    input_ready=0;cpu_dual_slave_clear();smpc_smc_sshoff_call();input_ready=1;bg_slave_ready=0;
}

/* draw_stage: replaces the row loop when map_update invalidated the plane */
    int bg_rows=scd_background_map_update(...);int bg_hold=bg_rows<0;
    int split=bg_slave_ready && bg_rows>=30; /* mapwrtb frame */
    if(split)bg_slave_job->n=0;
    for(int row=by/8;!bg_hold&&row<by/8+30;row++){
        int fixed=...,sx=...,cache_row=...;
        if(split && row>=by/8+15 && bg_row_world[cache_row&63]!=cache_row){
            /* the full-refill bookkeeping of scd_background_cache_row_periodic, fill deferred */
            int i=bg_slave_job->n++;unsigned slot=(unsigned)cache_row&63;
            bg_slave_job->y[i]=stage.wrap_y?(cache_row*8)&2047:cache_row*8;
            bg_slave_job->first[i]=sx;bg_slave_job->end[i]=sx+64;bg_slave_job->fixed[i]=fixed;bg_slave_job->slot[i]=slot;
            bg_row_world[slot]=cache_row;bg_row_keys[slot]=sx;
            if(dirty_last<0)dirty_first=row;dirty_last=row;
            continue;
        }
        if(scd_background_cache_row_periodic(...)!=0){...}
    }
    if(split && bg_slave_job->n){
        bg_slave_job->stage=&stage;bg_slave_job->map=maps[1];bg_slave_job->go++;
        cpu_dual_slave_notify();
        /* ...but the master filled its 15 rows before this point: move the
           notify above the loop by first collecting all 30 row parameters,
           then notify, then fill the master half. */
        while(bg_slave_job->done!=bg_slave_job->go){}
    }
```

Open points before implementation:
1. Move `scd_background_fill_row`'s eligibility check (alignment, bounds)
   into a helper that both sides share. A row that fails it stays on the master.
2. Reorder so the slave is notified before the master fills its half: collect
   parameters for all 30 rows, notify, fill the master half, then wait.
3. `stage_packs_load` and CD reads with the slave running: the special stage
   stops the slave around loads. Check whether zone loads need the same.
4. Hardware: SSHON/SSHOFF timing and ICI entry on SAROO. The emulator does not
   prove it.
5. `tools/test_zone_code.py` and the heap ASSERT: the job block adds about
   300 bytes of .bss.

## Reviewed implementation constraints (2026-09-26)

Split only the N+1 full-redraw case (`scd_background_map_update(...) == 30`),
not ordinary cache fills. Collect all 30 immutable row descriptors first;
the master and slave write disjoint map rows, then the master commits
`bg_row_world`/`bg_row_keys` only after the slave completes. The current cache
helper commits those keys too early for an asynchronous fill, so it needs a
plan/fill/commit split (or the full-redraw path must call the pure row fill
directly). Purge `maps[1]` before dispatch as well as after completion: a
post-job purge must not write stale master cache lines over slave output.

Use the existing polling `cpu_dual` owner pattern, not a raw SSHON. Start only
after a completed QQ `load_era`; stop at `load_era` entry and before
`special_load` or `title_begin`, which otherwise install their own slave
handlers. Hardware behavior of that ownership transition remains a required
gate.
