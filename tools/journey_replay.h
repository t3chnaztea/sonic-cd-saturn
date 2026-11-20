/* Host-only, controller-only replay of exploration through natural time travel.
   Included after the libretro/screenshot helpers in emulator_test.c. */
typedef struct {int32_t result;uint32_t state[40];} journey_reference;
static journey_reference journey_rows[60000];
static int journey_run(size_t mailbox,size_t world_mailbox,FILE *trace,
        void *(*p_retro_get_memory_data)(unsigned),size_t (*p_retro_get_memory_size)(unsigned),void (*p_retro_run)(void)){
    const char *path=getenv("SCD_JOURNEY_STATES");if(!path || !world_mailbox)return 2;
    const char *flags_address=getenv("SCD_JOURNEY_GOOD_FLAGS");
    if(!flags_address || !*flags_address)return 2;
    size_t flags_at=0x100000+(strtoul(flags_address,NULL,16)&0xfffff);
    const char *effects_address=getenv("SCD_JOURNEY_EFFECTS");
    if(!effects_address || !*effects_address)return 2;
    size_t effects_at=0x100000+(strtoul(effects_address,NULL,16)&0xfffff);
    const char *profile_address=getenv("SCD_FRAME_PROFILE");
    size_t profile_at=profile_address && *profile_address?0x100000+(strtoul(profile_address,NULL,16)&0xfffff):0;
    unsigned profile_sequence=0,intro_start=1;
    FILE *input=fopen(path,"rb");if(!input)return 2;
    unsigned count=0;unsigned char bytes[164];size_t got;
    while((got=fread(bytes,1,sizeof(bytes),input))){
        if(got!=sizeof(bytes) || count==60000){fclose(input);return 2;}
        uint32_t values[41];
        for(unsigned n=0;n<41;n++)values[n]=(uint32_t)bytes[4*n]|(uint32_t)bytes[4*n+1]<<8|(uint32_t)bytes[4*n+2]<<16|(uint32_t)bytes[4*n+3]<<24;
        if(values[0] || values[29]!=count+1 || values[37]>31 || values[38]>31){fclose(input);return 2;}
        journey_rows[count].result=values[0];memcpy(journey_rows[count].state,values+1,160);count++;
    }
    if(ferror(input) || !count){fclose(input);return 2;}fclose(input);
    unsigned seq=0,previous_era=0,warps=0,arrivals=0,seen_warp=0,arrival_due=0,checked=0,generators=0;
    unsigned previous_tick=0,intervals=0,late=0,max_gap=0,boss_fight=0,boss_defeated=0,results_seen=0;
    const char *capture=getenv("SCD_JOURNEY_CAPTURE_ROW");
    unsigned capture_row=capture?(unsigned)strtoul(capture,NULL,10):0;
    for(frame=0;frame<count*3+12000;frame++){
        const uint8_t *ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);size_t size=p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM);
        if(!ram || mailbox+(24+64*21)*4>size || world_mailbox+560>size || flags_at+4>size || effects_at+40>size)return 2;
        if(profile_at){
            if(profile_at+(4+64*32)*4>size)return 2;
            if(ram_word(ram,profile_at)==0x46505246){
                unsigned latest_profile=ram_word(ram,profile_at+4);
                if(latest_profile-profile_sequence>64 || ram_word(ram,profile_at+8)!=32)return 2;
                while(profile_sequence<latest_profile){
                    size_t at=profile_at+(4+(++profile_sequence%64)*32)*4;
                    if(ram_word(ram,at)!=profile_sequence)return 2;
                    printf("Journey profile:");
                    for(unsigned i=0;i<32;i++)printf(" %u",ram_word(ram,at+i*4));
                    printf("\n");
                }
            }
        }
        unsigned latest=ram_word(ram,mailbox+4);
        if(latest-seq>64){fprintf(stderr,"Journey trace overflow\n");return 2;}
        while(seq<latest && seq<count){
            const uint32_t *expected=journey_rows[seq].state;size_t record=mailbox+(24+((seq+1)%64)*21)*4;
            if(ram_word(ram,record)!=seq+1 || ram_word(ram,record+4)!=0xffffffffu)return 2;
            unsigned buttons=ram_word(ram,record+8);
            fprintf(trace,"%u %u",seq+1,buttons);
            for(unsigned n=0;n<16;n++)fprintf(trace," %08x",ram_word(ram,record+12+n*4));fputc('\n',trace);
            if(buttons!=expected[37]){fprintf(stderr,"Journey pad mismatch row=%u actual=%u expected=%u\n",seq+1,buttons,expected[37]);return 1;}
            for(unsigned n=0;n<16;n++)if(ram_word(ram,record+12+n*4)!=expected[n]){
                fprintf(stderr,"Journey state mismatch row=%u word=%u target=%08x host=%08x\n",seq+1,n,ram_word(ram,record+12+n*4),expected[n]);return 1;
            }
            unsigned tick=ram_word(ram,record+80);
            printf("Journey timing: row=%u vblank=%u act=%u era=%u\n",seq+1,tick,expected[16],expected[17]);
            if(seq && expected[16]==journey_rows[seq-1].state[16] && expected[17]==journey_rows[seq-1].state[17]){
                unsigned gap=tick-previous_tick;intervals++;if(gap>1)late++;if(gap>max_gap)max_gap=gap;
                if(!gap){fprintf(stderr,"Journey non-increasing simulation tick\n");return 1;}
            }
            previous_tick=tick;
            seq++;
        }
        unsigned era=ram_word(ram,world_mailbox+8),warp=ram_word(ram,world_mailbox+28);
        if(seq>checked && seq==latest && ram_word(ram,effects_at)==0x504f5756 && ram_word(ram,effects_at+36)==journey_rows[seq-1].state[6]){
            /* The mailbox describes the latest simulation update. Check it
               only when a new update arrives, not during fade/load fields.
               The effect marker is cleared before trace publication and set
               after the world mailbox. A VBlank can interrupt between them. */
            const uint32_t *expected=journey_rows[seq-1].state;
            unsigned actual[]={ram_word(ram,world_mailbox+536),era,ram_word(ram,flags_at),ram_word(ram,world_mailbox+24),ram_word(ram,world_mailbox+92),ram_word(ram,world_mailbox+116)};
            unsigned indices[]={16,17,18,19,29,30};
            for(unsigned n=0;n<6;n++)if(actual[n]!=expected[indices[n]]){
                fprintf(stderr,"Journey progression mismatch row=%u field=%u target=%u host=%u\n",seq,indices[n],actual[n],expected[indices[n]]);return 1;
            }
            if(seq!=checked+1){fprintf(stderr,"Journey progression sample gap\n");return 1;}
            checked=seq;
            if(capture_row==seq)screenshot("journey-capsule-intact");
            if(seq==1 || expected[34])intro_start=seq;
            unsigned intro_tick=seq-intro_start+1;
            if(intro_tick<=191){
                printf("Journey intro: row=%u act=%u tick=%u elapsed=%u pad=%u score=%u rings=%u lives=%u era=%u\n",
                    seq,actual[0],intro_tick,actual[4],expected[37],actual[5],
                    ram_word(ram,world_mailbox+128),(ram_word(ram,world_mailbox+88)>>8)&255,era);
                if(intro_tick==120 || intro_tick==131 || intro_tick==191){
                    char name[64];snprintf(name,sizeof(name),"journey-intro-act%u-tick%u",actual[0]+1,intro_tick);screenshot(name);
                }
            }
            if(expected[32]){char name[64];generators++;snprintf(name,sizeof(name),"journey-generator-%02u",generators);screenshot(name);printf("Journey generator: row=%u act=%u era=%u good=%u score=%u\n",seq,actual[0],era,actual[3],actual[5]);}
            if(actual[0]==2){
                unsigned status=ram_word(ram,world_mailbox+556),routine=status>>8&255;
                if(status>>16 && routine==4 && !boss_fight){boss_fight=seq;screenshot("journey-boss-fight");printf("Journey boss fight: row=%u status=%u\n",seq,status);}
                if(status>>16 && routine==6 && !boss_defeated){boss_defeated=seq;screenshot("journey-boss-defeated");printf("Journey boss defeated: row=%u status=%u\n",seq,status);}
                if(expected[25] && !results_seen){results_seen=seq;screenshot("journey-capsule");}
            }
        }
        if(warp && !seen_warp){char name[64];warps++;snprintf(name,sizeof(name),"journey-warp-%02u",warps);screenshot(name);printf("Journey warp: row=%u frame=%u era=%u timer=%u\n",seq,frame,era,warp);}
        seen_warp=warp;
        if(era!=previous_era){arrivals++;arrival_due=frame+2;printf("Journey arrival: row=%u frame=%u era=%u transitions=%u\n",seq,frame,era,ram_word(ram,world_mailbox+16));}
        previous_era=era;
        if(arrival_due && frame==arrival_due){char name[64];snprintf(name,sizeof(name),"journey-era-change-%02u",arrivals);screenshot(name);arrival_due=0;}
        if(seq==count && checked==count){
            screenshot("journey-end");
            printf("Journey matched: states=%u words=%u frames=%u warps=%u arrivals=%u era=%u good=%u act=%u\n",seq,seq*16,frame,warps,arrivals,era,ram_word(ram,world_mailbox+24),ram_word(ram,world_mailbox+536));
            printf("Journey progression: samples=%u fields=6 generators=%u good_flags=%u\n",checked,generators,ram_word(ram,flags_at));
            printf("Journey pacing: intervals=%u late=%u max_gap=%u\n",intervals,late,max_gap);
            if(getenv("SCD_JOURNEY_SPECIAL")){
                const char *address=getenv("SCD_SPECIAL_GAME"),*routes=getenv("SCD_SPECIAL_ROUTES");
                if(!address || !routes)return 2;
                size_t game_at=0x100000+(strtoul(address,NULL,16)&0xfffff);
                game_load_pads(routes);
                if(game_route_count<2 || !game_route_win[1])return 2;
                unsigned touch=0,game_seen=0,results=0,returned=0,game_lead=2;
                button_mask=game_retro_mask(24);
                for(unsigned n=0;n<25000;n++){
                    p_retro_run();frame++;
                    ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
                    if(!ram || game_at+160>p_retro_get_memory_size(RETRO_MEMORY_SYSTEM_RAM))return 2;
                    unsigned special=ram_word(ram,world_mailbox+564);
                    if(!touch && special>>16){touch=n+1;screenshot("journey-special-touch");}
                    unsigned active=ram_word(ram,game_at)==0x5353474d && ram_word(ram,game_at+108);
                    if(active){
                        if(!game_seen){game_seen=n+1;screenshot("journey-special-stage");}
                        unsigned v=ram_word(ram,game_at+4),phase=ram_word(ram,game_at+8),index=v+game_lead;
                        if(phase>=6 && !results){results=n+1;screenshot("journey-special-results");}
                        button_mask=game_retro_mask(game_pads[1][phase>=5][index<16000?index:15999]);
                    }else button_mask=touch?0:game_retro_mask(24);
                    if(game_seen && !active && ram_word(ram,world_mailbox+568)==0 &&
                       ram_word(ram,world_mailbox+536)==2 && ram_word(ram,world_mailbox+8)==2 &&
                       ram_word(ram,world_mailbox+560)==1 && ram_word(ram,flags_at)==3){
                        if(++returned==180){
                            screenshot("journey-special-return");
                            printf("Journey special return: touch=%u stage=%u results=%u zone=0 act=3 era=2 stones=1 good_flags=3 score=%u lives=%u rings=%u\n",
                                   touch,game_seen,results,ram_word(ram,world_mailbox+116),
                                   (ram_word(ram,world_mailbox+88)>>8)&255,ram_word(ram,world_mailbox+128));
                            fflush(trace);return touch && results?0:1;
                        }
                    }else returned=0;
                }
                fprintf(stderr,"Journey special return failed: touch=%u stage=%u results=%u\n",touch,game_seen,results);
                return 1;
            }
            if(journey_rows[count-1].state[16]==2 && journey_rows[count-1].state[25]==6){
                unsigned next_zone=0,entry_frame=0,ready=0;
                if(!boss_fight || !boss_defeated || !results_seen)return 1;
                button_mask=0;
                for(unsigned n=0;n<1800;n++){
                    p_retro_run();frame++;
                    ram=p_retro_get_memory_data(RETRO_MEMORY_SYSTEM_RAM);
                    if(!ram)return 2;
                    if(ram_word(ram,world_mailbox+568)==1 && ram_word(ram,world_mailbox+536)==0 && ram_word(ram,world_mailbox+8)==0){
                        if(!next_zone){next_zone=1;entry_frame=n;}
                        if(n>=entry_frame+150){ready=1;screenshot("journey-next-zone");break;}
                    }else if(next_zone){fprintf(stderr,"Journey next zone regressed\n");return 1;}
                }
                if(!ready){fprintf(stderr,"Journey zone exit failed\n");return 1;}
                printf("Journey zone exit: next_zone=1 next_act=1 boss_fight=%u boss_defeated=%u capsule=%u\n",boss_fight,boss_defeated,results_seen);
            }
            fflush(trace);return 0;
        }
        /* SMPC normally consumes the previous field's poll. While a warp
           freezes simulation, hold the next state's pad through the load. */
        unsigned next=seq+(warp?0:1);if(next>=count)next=count-1;
        button_mask=act_pad_mask(journey_rows[next].state[36]);
        p_retro_run();
    }
    fprintf(stderr,"Journey timeout at %u/%u\n",seq,count);return 2;
}
