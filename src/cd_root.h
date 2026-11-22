#ifndef SCD_CD_ROOT_H
#define SCD_CD_ROOT_H
#include <yaul.h>
/* One shared reading of the CD root directory.
   cdfs_filelist_init takes the pool it is handed as the hard limit on how many
   entries cdfs_filelist_root_read will store, and the read stops there without
   saying so.  Every caller here searches that list by name, so a pool smaller
   than the root makes the files past it invisible and the caller then reports a
   present file as missing.  The root carries one entry per stage pack, so it
   grows with every zone: tools/check_cd_root.py fails the build before the disc
   catches up with the pool. */
#define CD_ROOT_ENTRIES 320
const cdfs_filelist_t *scd_cd_root_read(void);
#endif
