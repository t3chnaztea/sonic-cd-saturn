/* Browser host glue for the pinned, offline Genesis Plus GX core. */
#include "shared.h"
#include "libretro.h"
#include <stdint.h>
static bool environment(unsigned command, void *data)
{
    if (command == 15) {
        struct retro_variable *v = data;
        if (!strcmp(v->key, "genesis_plus_gx_pcm_volume")) { v->value = "30"; return true; }
    }
    if (command == 9 || command == 31) { *(const char **)data = "/project/assets/private"; return true; }
    if (command == 10) return true;
    if (command == 3) { *(bool *)data = false; return true; }
    return false;
}
void patcher_init(void) { retro_set_environment(environment); retro_init(); }
uintptr_t patcher_symbol(const char *name)
{
    /* The Python fixture uses the native 64-bit struct's PRG-RAM offset.
       Preserve that fixture address convention over the actual WASM layout. */
    if (!strcmp(name, "ext")) return (uintptr_t)scd.prg_ram - 0x830088;
    if (!strcmp(name, "zram")) return (uintptr_t)zram;
    if (!strcmp(name, "work_ram")) return (uintptr_t)work_ram;
    if (!strcmp(name, "vram")) return (uintptr_t)vram;
    if (!strcmp(name, "cram")) return (uintptr_t)cram;
    if (!strcmp(name, "vsram")) return (uintptr_t)vsram;
    if (!strcmp(name, "reg")) return (uintptr_t)reg;
    return 0;
}
