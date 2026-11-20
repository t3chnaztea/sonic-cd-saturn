/* Optional persistent internal RAM for cold-boot tests. Beetle's BackupRAM is
   a static byte array, remains valid through retro_deinit, and the harness
   never dlcloses the core. Capture it on every normal process exit. */
static uint8_t *backup_bytes;
static size_t backup_size;
static void backup_flush(void){
    const char *path=getenv("SCD_BACKUP_OUTPUT");if(!path || !backup_bytes)return;
    FILE *f=fopen(path,"wb");if(!f || fwrite(backup_bytes,1,backup_size,f)!=backup_size){perror(path);_Exit(2);}
    if(fclose(f)){perror(path);_Exit(2);}
}
static int backup_open(void *(*data)(unsigned),size_t (*size)(unsigned)){
    backup_bytes=data(RETRO_MEMORY_SAVE_RAM);backup_size=size(RETRO_MEMORY_SAVE_RAM);
    if(!getenv("SCD_BACKUP_INPUT") && !getenv("SCD_BACKUP_OUTPUT"))return 0;
    if(!backup_bytes || backup_size!=32768){fprintf(stderr,"Expected 32 KiB internal backup RAM\n");return -1;}
    const char *path=getenv("SCD_BACKUP_INPUT");
    if(path){
        FILE *f=fopen(path,"rb");if(!f){perror(path);return -1;}
        if(fread(backup_bytes,1,backup_size,f)!=backup_size || fgetc(f)!=EOF){fclose(f);return -1;}
        fclose(f);
    }
    atexit(backup_flush);return 0;
}
static int save_report(const uint8_t *ram,size_t at,size_t trace){
    char path[4096];snprintf(path,sizeof(path),"%s/save.json",output_dir);
    FILE *f=fopen(path,"w");if(!f)return 2;
    fprintf(f,"{\"mailbox\":[");for(unsigned i=0;i<12;i++)fprintf(f,"%s%u",i?",":"",ram_word(ram,at+i*4));
    fprintf(f,"],\"trace\":[");for(unsigned i=0;i<24;i++)fprintf(f,"%s%u",i?",":"",ram_word(ram,trace+i*4));
    fprintf(f,"]}\n");fclose(f);screenshot("save-screen");return 0;
}
static int save_run(size_t trace,void *(*data)(unsigned),size_t (*size)(unsigned),void (*run)(void)){
    const char *address=getenv("SCD_SAVE_MAILBOX"),*action=getenv("SCD_SAVE_CASE");
    if(!address || !action)return 2;
    size_t at=0x100000+(strtoul(address,NULL,16)&0xfffff);
    if(at+48>size(RETRO_MEMORY_SYSTEM_RAM))return 2;
    unsigned gameplay=0,panel_frames=0,cancelled=0,confirmed=0,retry_return=0;
    int retry_mode=!strcmp(action,"full-retry");
    for(frame=0;frame<9000;frame++){
        const uint8_t *ram=data(RETRO_MEMORY_SYSTEM_RAM);
        if(ram_word(ram,at)!=0x53415645){button_mask=0;run();continue;}
        uint32_t magic=ram_word(ram,trace),state=ram_word(ram,trace+8);
        unsigned valid=ram_word(ram,at+8),panel=ram_word(ram,at+40);
        button_mask=0;
        if(magic==0x53434432 && !panel){
            gameplay++;
            if(retry_mode){
                /* A full-memory New Game is playable. Return through the game
                   over fixture, then use RAM DATA to retry that pending save. */
                if(gameplay>=120 && gameplay<124){
                    retry_return=1;button_mask=(1u<<RETRO_DEVICE_ID_JOYPAD_START)|(1u<<RETRO_DEVICE_ID_JOYPAD_R)|(1u<<RETRO_DEVICE_ID_JOYPAD_RIGHT);
                }
            }else if(gameplay==120)return save_report(ram,at,trace);
        }else if(panel){
            panel_frames++;
            if(!strcmp(action,"ram") && panel_frames==20)return save_report(ram,at,trace);
            if(panel_frames==20 && !strcmp(action,"cancel")){button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_A;cancelled=1;}
            /* Libretro B maps to Saturn A; libretro A maps to Saturn B. */
            if(panel_frames==20 && (!strcmp(action,"replace") || !strcmp(action,"retry") || retry_mode)){
                const char *freed=getenv("SCD_BACKUP_RETRY_INPUT");
                if(retry_mode && freed){
                    FILE *f=fopen(freed,"rb");if(!f)return 2;
                    if(fread(backup_bytes,1,backup_size,f)!=backup_size || fgetc(f)!=EOF){fclose(f);return 2;}
                    fclose(f);
                }
                button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_B;confirmed=1;
            }
            if(confirmed && (!strcmp(action,"retry") || retry_mode) && panel_frames==100)return save_report(ram,at,trace);
        }else if(magic==0x5449544c){
            unsigned selection=(state>>16)&255;
            if((state&255)==2 && !selection && frame%8<4)button_mask=1u<<RETRO_DEVICE_ID_JOYPAD_START;
            else if(state&256){
                if(!strcmp(action,"boot") || cancelled)return save_report(ram,at,trace);
                /* Menu/Main.asm order: New Game, Continue (save), Time Attack (titleFlags bit 5), RAM DATA.
                   Saved progress past zone 0 unlocks Time Attack (src/frontend.c fe_title_flags). */
                unsigned saved=ram_word(ram,at+20),flags=ram_word(ram,at+24);
                unsigned time_attack=valid && (saved&255)+(flags>>16&255)>0;
                unsigned target=(!strcmp(action,"ram") || !strcmp(action,"retry") || retry_return)?(valid?3:2)+time_attack:!strcmp(action,"continue")?2:1;
                if(!strcmp(action,"continue") && !valid){fprintf(stderr,"Continue unavailable\n");return 2;}
                if(frame%8<4)button_mask=1u<<(selection<target?RETRO_DEVICE_ID_JOYPAD_RIGHT:selection>target?RETRO_DEVICE_ID_JOYPAD_LEFT:RETRO_DEVICE_ID_JOYPAD_B);
            }
        }
        run();
    }
    screenshot("save-timeout");const uint8_t *ram=data(RETRO_MEMORY_SYSTEM_RAM);
    save_report(ram,at,trace);fprintf(stderr,"Save flow timed out\n");return 2;
}
