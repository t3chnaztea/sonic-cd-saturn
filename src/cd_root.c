#include "cd_root.h"
/* Static, not automatic: the pool is 8,960 bytes and the callers run on the
   ordinary stack. */
static cdfs_filelist_entry_t cd_root_entries[CD_ROOT_ENTRIES];
static cdfs_filelist_t cd_root;
/* The root directory is read once and kept.  Walking it costs four sector reads
   and grows with the disc, and both the stage pack loader and the special stage
   loader ask for it while the player waits.  A read that comes back empty is not
   kept, so a call made before the drive is ready does not poison the listing. */
const cdfs_filelist_t *scd_cd_root_read(void){
    if(cd_root.entries_count)return &cd_root;
    cdfs_config_default_set();
    cdfs_filelist_init(&cd_root,cd_root_entries,CD_ROOT_ENTRIES);
    cdfs_filelist_root_read(&cd_root);
    return &cd_root;
}
