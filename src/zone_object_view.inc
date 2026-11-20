/* The special-stage UFO arena is free during normal gameplay. Restore this
   era's zone art on every load, including return from title/special modes. */
static scd_zone_art zone_art,zone_art_banks[2]; /* zone_art_banks: R83 slots 0/1, opened at stage load */
static const uint8_t *boss6_art_patch;
static unsigned boss6_art_applied_age;
static const uint8_t *cc_drum_frames[12];
#define ZONE_ART_LOOKUP_CAPACITY 512u
typedef struct { uint16_t kind,frame; const uint8_t *record; } zone_art_lookup_entry;
static zone_art_lookup_entry zone_art_lookup[ZONE_ART_LOOKUP_CAPACITY];
volatile uint32_t scd_zone_art_mailbox[16+SCD_OBJECT_CAPACITY*8];
static int zone_art_probe_active;
/* Multiplicative hash of kind:frame, top 9 bits. The former kind*257^frame
   kept only bit 0 of a ZAR3 subtype (kind bits 8-15), so every subtype of a
   Tidal Tempest type shared one cluster: 15 probes per hit, 42 per miss on
   the TT1 Present pack; this hash averages 1.3 and 1.8 there. */
static unsigned zone_art_lookup_slot(unsigned kind,unsigned frame){return ((kind<<16|frame)*0x9E3779B1u)>>23;}
_Static_assert(ZONE_ART_LOOKUP_CAPACITY==1u<<(32-23),"lookup hash yields 9 bits");
/* Largest distance of any part edge from its actor's origin in this pack, either flip
   (the records sit in slow low work RAM; the widest current pose reaches 97 pixels),
   and at least 33: sprite_draw's generic branch culls an actor 33+ pixels off screen. */
static int zone_art_reach;
static int zone_art_far(int x,int y){
    return x<=-zone_art_reach || x>=320+zone_art_reach || y<=-zone_art_reach || y>=224+zone_art_reach;
}
/* Decoded part records, direct mapped by record index. The records are
   big-endian bytes in slow low work RAM; a flower shower (79 actors, Tidal
   Tempest Act 3 capsule) re-read them byte by byte on every update. The
   cache holds the same fields and is cleared with each art load. */
typedef struct {const uint8_t *f;uint16_t w,h;int16_t left,top;uint32_t offset,clut;uint8_t more;} zone_art_part;
static zone_art_part zone_art_parts[64];
static const zone_art_part *zone_art_part_get(const uint8_t *f){
    zone_art_part *d=&zone_art_parts[((unsigned)(f-zone_art.frames)/SCD_ZONE_ART_RECORD)&63];
    if(d->f!=f){
        const uint8_t *next=f+SCD_ZONE_ART_RECORD,*end=zone_art.frames+zone_art.count*SCD_ZONE_ART_RECORD;
        d->w=(uint16_t)scd_zone_art_u16(f+8);d->h=(uint16_t)scd_zone_art_u16(f+10);
        d->left=(int16_t)scd_zone_art_i16(f+12);d->top=(int16_t)scd_zone_art_i16(f+14);
        d->offset=scd_zone_art_bitmap(f);d->clut=scd_zone_art_clut(f);
        d->more=next<end && scd_zone_art_u16(next)==scd_zone_art_u16(f) && scd_zone_art_u16(next+2)==scd_zone_art_u16(f+2);
        d->f=f;
    }
    return d;
}
static void zone_art_lookup_build(void){
    memset(zone_art_lookup,0,sizeof(zone_art_lookup));
    memset(zone_art_parts,0,sizeof(zone_art_parts));
    zone_art_reach=33;
    for(unsigned i=0;i<zone_art.count;i++){
        const uint8_t *record=zone_art.frames+i*SCD_ZONE_ART_RECORD;
        int left=scd_zone_art_i16(record+12),top=scd_zone_art_i16(record+14);
        int edges[4]={left,left+(int)scd_zone_art_u16(record+8),top,top+(int)scd_zone_art_u16(record+10)};
        for(unsigned e=0;e<4;e++){int d=edges[e]<0?-edges[e]:edges[e];if(d>zone_art_reach)zone_art_reach=d;}
        unsigned kind=scd_zone_art_u16(record),frame=scd_zone_art_u16(record+2);
        /* Records after the first with the same kind and pose are further
           parts of that pose (per-piece families); only the first is indexed. */
        if(i && scd_zone_art_u16(record-SCD_ZONE_ART_RECORD)==kind && scd_zone_art_u16(record-SCD_ZONE_ART_RECORD+2)==frame)continue;
        unsigned slot=zone_art_lookup_slot(kind,frame);
        while(zone_art_lookup[slot].record){
            assert(zone_art_lookup[slot].kind!=kind || zone_art_lookup[slot].frame!=frame);
            slot=(slot+1)&(ZONE_ART_LOOKUP_CAPACITY-1);
        }
        zone_art_lookup[slot]=(zone_art_lookup_entry){kind,frame,record};
    }
}
static const uint8_t *zone_art_lookup_kind(unsigned kind,unsigned frame){
    unsigned slot=zone_art_lookup_slot(kind,frame);
    while(zone_art_lookup[slot].record){
        if(zone_art_lookup[slot].kind==kind && zone_art_lookup[slot].frame==frame)return zone_art_lookup[slot].record;
        slot=(slot+1)&(ZONE_ART_LOOKUP_CAPACITY-1);
    }
    return NULL;
}
static const uint8_t *zone_art_find(unsigned type,unsigned subtype,unsigned frame){
    /* ZAR3: a subtype with its own pattern table is type|subtype<<8. */
    if(zone_art.lz){
        /* AWA.C masters and the bubbles they release share one pattern table
           (sproffset 33930); the packs key it under the master subtype 0x80. */
        if(type==SCD_OBJ_AWA)subtype=0x80;
        const uint8_t *f=zone_art_lookup_kind((type&255)|(subtype&255)<<8,frame);
        return f?f:zone_art_lookup_kind(type,frame);
    }
    unsigned kind=scd_zone_art_kind(type,subtype),slot=zone_art_lookup_slot(kind,frame);
    while(zone_art_lookup[slot].record){
        if(zone_art_lookup[slot].kind==kind && zone_art_lookup[slot].frame==frame)return zone_art_lookup[slot].record;
        slot=(slot+1)&(ZONE_ART_LOOKUP_CAPACITY-1);
    }
    return NULL;
}
/* The Past bank is already in the common object atlas. Present has two
   separately captured withered poses; both use the original 80-pixel canvas. */
static void cc_generator_sprite(unsigned *count,scd_object_view o,int x,int y){
    unsigned frame=era==1?OBJECT_BASE_45+o.frame:OBJECT_BASE_86+(o.frame==2);
    int left=x-(int)object_widths[frame]/2,top=y-32-object_y_shifts[frame]+object_top(frame,o.flags);
    unsigned w=object_widths[frame],h=object_heights[frame];
    if(left>=320 || left+(int)w<=0 || top>=224 || top+(int)h<=0)return;
    object_sprite(count,frame,x,y,o.flags);
    unsigned n=scd_zone_art_mailbox[7];
    if(n<SCD_OBJECT_CAPACITY){
        volatile uint32_t *r=scd_zone_art_mailbox+16+n*8;
        r[0]=o.type;r[1]=o.frame;r[2]=left;r[3]=top;r[4]=o.flags&3;
        r[5]=w<<16|h;r[6]=OBJECT_ATLAS_BASE+object_raw_offsets[frame];r[7]=*count-1;
        scd_zone_art_mailbox[7]=n+1;
    }
}
/* COL4A-D cycle palette entries each update. High-priority zone pixels read
   them live through the CRAM 128+ alias; normal pixels read their CLUT, which
   zone_object_art_load fills once from the stage palette. zone_cycle_* keeps
   the CLUT slots that reference a scripted entry (at most 5 per R4 pack) and
   rewrites them when that entry changes, as the Mega Drive's CRAM would.
   Quartz Quadrant: the COL5A-D colchgsub scripts (A 42-44/56-62, B 35-37/
   62-63, C 42-44, D 42-44/54-57/60-63) and the entries enkeichg's colorset2
   changes between zone5color0 and zone5color1 (at most 15 slots per pack).
   tools/check_zone_object_target.py derives these masks from
   src/background_r5_palette.inc and asserts them. */
#define ZONE_CYCLE_SLOTS 64u
uint64_t scd_r4_palette_entries(unsigned id);
uint64_t scd_r8_palette_entries(unsigned id);
static const uint64_t zone_cycle_r5[4]={0xffff1c0100000000ull,0xffff003900000000ull,
                                        0xffff1c0100000000ull,0xfffe1c0000000000ull};
static uint16_t zone_cycle_addr[ZONE_CYCLE_SLOTS],zone_cycle_last[64];
static uint8_t zone_cycle_ref[ZONE_CYCLE_SLOTS];
static unsigned zone_cycle_count;static uint64_t zone_cycle_entries;
static void zone_cycle_build(void){
    /* EMIE3 replaces line 1 during CC1 play. ZAR2 CLUTs must follow it. */
    zone_cycle_count=0;zone_cycle_entries=stage_zone==1?0x00000000ffff0000ull:
                                          !zone_art.lz?0:stage_zone==2?scd_r4_palette_entries(stage_act*4+era):
                                          stage_zone==3?zone_cycle_r5[era&3]:
                                          stage_zone==6?scd_r8_palette_entries(stage_act*4+era):0;
    /* Tidal Tempest CLUTs hold palette codes, which follow the cycled CRAM
       alias above the water and the static water bank below it (the R4 palette
       cycle never writes waterPalette). */
    if(water_raster_active())zone_cycle_entries=0;
    if(!zone_cycle_entries)return;
    for(unsigned i=0;i<64;i++)zone_cycle_last[i]=scd_zone_art_u16(stage.part[5]+i*2);
    for(unsigned i=0;i<zone_art.count;i++){
        /* Word offset inside the zone art arena (< 30720 fits 16 bits); the
           absolute VDP1 word address (0x388xx) does not. */
        const uint8_t *f=zone_art.frames+i*SCD_ZONE_ART_RECORD;unsigned clut=scd_zone_art_clut(f)/2;
        for(unsigned c=1;c<16;c++){
            unsigned ref=scd_zone_art_u16(f+16+c*2);
            if((ref&128) || !(zone_cycle_entries>>(ref&63)&1))continue;
            unsigned n=0;while(n<zone_cycle_count && zone_cycle_addr[n]!=clut+c)n++;
            if(n==zone_cycle_count && n<ZONE_CYCLE_SLOTS){zone_cycle_addr[n]=(uint16_t)(clut+c);zone_cycle_ref[n]=(uint8_t)ref;zone_cycle_count++;}
        }
    }
}
/* draw_stage, after scd_background_palette: only changed entries write. */
static void zone_cycle_cluts(const uint16_t *pal){
    uint64_t changed=0;
    for(uint64_t m=zone_cycle_entries;m;m&=m-1){unsigned i=(unsigned)__builtin_ctzll(m);if(pal[i]!=zone_cycle_last[i]){changed|=1ull<<i;zone_cycle_last[i]=pal[i];}}
    if(!changed)return;
    volatile uint16_t *vram=(volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE);
    for(unsigned n=0;n<zone_cycle_count;n++)if(changed>>zone_cycle_ref[n]&1)vram[zone_cycle_addr[n]]=pal[zone_cycle_ref[n]];
}
/* Metallic Madness Act 3's fight and Amy banks stream in over several updates,
   as retail's PLC queue loads PLC 4 and 5 (BOSS_8.C) while the game runs:
   decoding a whole bank at once costs four refreshes. Zone sprites stay hidden
   until the bank is complete. */
struct zone_art_stream_state {const uint8_t *r,*end;unsigned at,words,left,dist,kind,record,fresh;uint16_t v;uint32_t seen[SCD_ZONE_ART_CAPACITY/32/32];};
static struct zone_art_stream_state zone_art_stream;
static int zone_art_streaming;
/* 1 once LoadPLC(4)/(5) has replaced the stage art with the R83 fight or Amy
   bank. A death restarts the level, whose load restores the stage's art. */
static uint8_t zone_art_bank_loaded;
/* ZAR5: decode the shared arena's run/literal stream (sprite_unpack's format)
   once and keep only this era's spans, packed from era raw - span bytes up. */
static int zone_art_unpack_spans(const scd_zone_art *art,uint16_t *to){
    const uint8_t *r=art->packed,*end=art->packed+art->packed_bytes,*span=art->spans;
    unsigned words=0;for(unsigned i=0;i<art->span_count;i++)words+=scd_zone_art_u16(span+i*4+2);
    unsigned at=0,dst=art->raw_bytes/2-words,s=0,from=scd_zone_art_u16(span),left=scd_zone_art_u16(span+2);
    while(r<end){
        if(end-r<2)return -1;
        unsigned code=(unsigned)r[0]<<8|r[1];r+=2;
        unsigned count=code&32767,literal=code&32768;
        if(!count || count>art->arena_words-at || (unsigned)(end-r)<(literal?count*2:2))return -1;
        for(unsigned i=0;i<count;i++,at++){
            if(s<art->span_count && at>=from){
                to[dst++]=(uint16_t)(r[0]<<8|r[1]);
                if(!--left && ++s<art->span_count){from=scd_zone_art_u16(span+s*4);left=scd_zone_art_u16(span+s*4+2);}
            }
            if(literal)r+=2;
        }
        if(!literal)r+=2;
    }
    return at==art->arena_words && s==art->span_count && dst==art->raw_bytes/2?0:-1;
}
/* slot: the pack's era entry. Metallic Madness Act 3 keeps its fight and Amy
   banks in entries 0/1 (tools/zone_object_assets.py FIGHT_KINDS). */
static void zone_object_art_load_slot(unsigned slot){
    const uint8_t *pack=(const uint8_t *)(uintptr_t)stage_pack_regions[PACK_ZONE_ART].address;
    zone_art_streaming=0;zone_art_bank_loaded=0;
    if(stage_zone){
        int result=scd_zone_art_open(&zone_art,pack,stage_pack_bytes[PACK_ZONE_ART],slot);
        if(result)abort();
        /* R83: validate the fight and Amy banks (slots 0/1) here, off the
           gameplay clock; the LoadPLC(4)/(5) request then streams a cached bank. */
        if(stage_zone==6 && stage_act==2 && slot>=2)
            for(unsigned b=0;b<2;b++)
                if(scd_zone_art_open(&zone_art_banks[b],pack,stage_pack_bytes[PACK_ZONE_ART],b) || !zone_art_banks[b].lz || !zone_art_banks[b].count)abort();
    }
    else zone_art=(scd_zone_art){0};
    boss6_art_patch=NULL;boss6_art_applied_age=0;
    if(stage_zone==4 && stage_act==2){
        const uint8_t *p=zone_art.packed+zone_art.packed_bytes;
        const uint8_t *end=pack+stage_pack_bytes[PACK_ZONE_ART];
        if(p>end || end-p<8 || scd_zone_art_u32(p)!=0x57365054u)abort(); /* W6PT */
        unsigned ages=scd_zone_art_u16(p+4);
        if(ages!=(era==3?105u:106u) || (unsigned)(end-p-8)<(ages+1)*4)abort();
        unsigned bytes=scd_zone_art_u32(p+8+ages*4);
        if((unsigned)(end-p-8-(ages+1)*4)<bytes)abort();
        boss6_art_patch=p;
    }
    zone_art_lookup_build();
    memset(cc_drum_frames,0,sizeof(cc_drum_frames));
    if(stage_zone==1 && stage_act==1){
        for(unsigned frame=0;frame<12;frame++){
            cc_drum_frames[frame]=zone_art_find(SCD_OBJ_DRUMR3,0,frame);
            if(!cc_drum_frames[frame])abort();
        }
    }
    if(zone_art.count){
        if(zone_art.lz){
            if(scd_zone_art_lz_unpack(zone_art.packed,zone_art.packed_bytes,
                (volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE),zone_art.raw_bytes/2))abort();
        }
        else if(zone_art.spans){if(zone_art_unpack_spans(&zone_art,(uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE)))abort();}
        else sprite_unpack(zone_art.packed,zone_art.packed+zone_art.packed_bytes,
            (uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE),zone_art.raw_bytes/2,1);
        for(unsigned i=0;i<zone_art.count;i++){
            const uint8_t *f=zone_art.frames+i*SCD_ZONE_ART_RECORD;
            unsigned clut_offset=scd_zone_art_clut(f);
            volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE+clut_offset);
            clut[0]=0;
            for(unsigned c=1;c<16;c++){
                unsigned ref=scd_zone_art_u16(f+16+c*2);
                clut[c]=(ref&128)?0x4080+(ref&63):water_raster_active()?0x0080+(ref&63):scd_zone_art_u16(stage.part[5]+ref*2);
            }
        }
    }
    /* Tidal Tempest: stage-palette refs are palette codes into the CRAM alias
       (128..191) so the water line's bank switch recolours them, as retail's
       H-INT palette swap does for every sprite (water_raster.h). */
    zone_cycle_build();
    scd_zone_art_mailbox[0]=0x5a415254;
    scd_zone_art_mailbox[2]=stage_zone;scd_zone_art_mailbox[3]=stage_act;scd_zone_art_mailbox[4]=era;
    scd_zone_art_mailbox[5]=zone_art.count;scd_zone_art_mailbox[6]=zone_art.raw_bytes;
    scd_zone_art_mailbox[8]=SCD_ZONE_ART_BASE;
}
static void zone_object_art_load(void){zone_object_art_load_slot(era);}
/* After the decode: the streamed bank's CLUTs take the live CRAM image (boss and
   room lines included), each shared CLUT once, 48 records per update; then the
   cycle slots on an update of their own. */
static void zone_art_stream_finish(void){
    struct zone_art_stream_state *z=&zone_art_stream;
    if(!z->record){
        /* zone_cycle_build's slots, registered below: each CLUT is visited once,
           so its entries need no search. */
        zone_cycle_count=0;zone_cycle_entries=scd_r8_palette_entries(stage_act*4+era);
        for(unsigned i=0;i<64;i++)zone_cycle_last[i]=animated_palette[i];
    }
    for(unsigned n=0;n<48 && z->record<zone_art.count;n++,z->record++){
        const uint8_t *f=zone_art.frames+z->record*SCD_ZONE_ART_RECORD;
        unsigned at=scd_zone_art_clut(f),b=at/32;
        if(z->seen[b/32]>>(b%32)&1)continue;
        z->seen[b/32]|=1u<<(b%32);
        volatile uint16_t *clut=(volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE+at);
        clut[0]=0;
        for(unsigned c=1;c<16;c++){
            unsigned ref=scd_zone_art_u16(f+16+c*2);clut[c]=(ref&128)?0x4080+(ref&63):water_raster_active()?0x0080+(ref&63):animated_palette[ref&63];
            if(!(ref&128) && (zone_cycle_entries>>(ref&63)&1) && zone_cycle_count<ZONE_CYCLE_SLOTS){
                zone_cycle_addr[zone_cycle_count]=(uint16_t)(at/2+c);zone_cycle_ref[zone_cycle_count++]=(uint8_t)ref;
            }
        }
    }
    if(z->record==zone_art.count){
        zone_art_streaming=0;
        scd_zone_art_mailbox[5]=zone_art.count;scd_zone_art_mailbox[6]=zone_art.raw_bytes;
    }
}
static void zone_object_art_stream_slot(unsigned slot){
    if(slot>1 || !zone_art_banks[slot].count)abort();
    zone_art=zone_art_banks[slot];
    zone_art_bank_loaded=1;
    /* The old bank's cycle slots point into VRAM the decode now overwrites. */
    zone_cycle_count=0;
    zone_art_stream.r=zone_art.packed;zone_art_stream.end=zone_art.packed+zone_art.packed_bytes;
    zone_art_stream.at=zone_art_stream.left=zone_art_stream.record=0;zone_art_stream.words=zone_art.raw_bytes/2;
    zone_art_stream.fresh=1;memset(zone_art_stream.seen,0,sizeof(zone_art_stream.seen));
    zone_art_streaming=1;
}
/* scd_zone_art_lz_unpack, resumable: at most `budget` words per call. */
static void zone_art_stream_step(unsigned budget){
    volatile uint16_t *to=(volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE);
    struct zone_art_stream_state *z=&zone_art_stream;
    /* The request's update opened the bank; the next builds its lookup. */
    if(z->fresh){z->fresh=0;zone_art_lookup_build();return;}
    if(z->at==z->words && !z->left){if(z->r!=z->end)abort();zone_art_stream_finish();return;}
    while(budget){
        if(!z->left){
            if(z->at==z->words)break;
            if(z->end-z->r<2)abort();
            unsigned code=(unsigned)z->r[0]<<8|z->r[1];z->r+=2;
            if(code&0x8000){
                if(z->end-z->r<2)abort();
                z->left=code&0x7fff;z->dist=(unsigned)z->r[0]<<8|z->r[1];z->r+=2;z->kind=1;
                if(!z->left || z->dist>z->at || z->left>z->words-z->at)abort();
                if(!z->dist)z->kind=4; /* keep the resident bank's words: R83's Amy bank (slot 1)
                   is packed over the fight bank, which PLC 4 always streams first */
            }else if(code&0x4000){
                z->left=code&0x3fff;z->kind=2;
                if(!z->left || z->left>z->words-z->at || (unsigned)(z->end-z->r)<z->left*2)abort();
            }else{
                if(!code || code>z->words-z->at || z->end-z->r<2)abort();
                z->left=code;z->v=(uint16_t)(z->r[0]<<8|z->r[1]);z->r+=2;z->kind=3;
            }
        }
        unsigned n=z->left<budget?z->left:budget;
        if(z->kind==4)z->at+=n;
        else if(z->kind==1)for(unsigned k=0;k<n;k++,z->at++)to[z->at]=to[z->at-z->dist];
        else if(z->kind==2)for(unsigned k=0;k<n;k++,z->at++,z->r+=2)to[z->at]=(uint16_t)(z->r[0]<<8|z->r[1]);
        else for(unsigned k=0;k<n;k++)to[z->at++]=z->v;
        z->left-=n;budget-=n;
    }
}
/* Replay PLC 19's original three-tile updates into the packed entry poses.
   Each update stores changed VDP1 words only; missed draw calls catch up. */
static void boss6_art_apply(void){
    if(!boss6_art_patch)return;
    unsigned age=scd_boss6_art_age(),limit=scd_zone_art_u16(boss6_art_patch+4);
    if(age>limit)age=limit;
    const uint8_t *table=boss6_art_patch+8,*body=table+(limit+1)*4;
    volatile uint16_t *vram=(volatile uint16_t *)VDP1_VRAM(SCD_ZONE_ART_BASE);
    for(unsigned frame=boss6_art_applied_age+1;frame<=age;frame++){
        const uint8_t *p=body+scd_zone_art_u32(table+(frame-1)*4);
        const uint8_t *end=body+scd_zone_art_u32(table+frame*4);
        while(p<end){
            if(end-p<4)abort();
            unsigned at=scd_zone_art_u16(p),n=scd_zone_art_u16(p+2);p+=4;
            if(!n || at+n>zone_art.raw_bytes/2 || (unsigned)(end-p)<n*2)abort();
            for(unsigned i=0;i<n;i++,p+=2)vram[at+i]=scd_zone_art_u16(p);
        }
    }
    boss6_art_applied_age=age;
}
/* found: the pose record when the caller already looked it up, else NULL. */
static void zone_object_sprite_record(unsigned *count,scd_object_view o,int x,int y,const uint8_t *found){
    /* No part of a far actor reaches the screen: skip its lookup and part records. */
    if(zone_art_far(x,y) || zone_art_streaming)return;
    /* TRAP_R3.C's twelve poses are an R32-only table.  A stale/global view
       must never index its act-local cache after another zone has replaced
       the art pack. */
    const uint8_t *f=found?found:stage_zone==1 && stage_act==1 && o.type==SCD_OBJ_DRUMR3 && o.frame<12?
        cc_drum_frames[o.frame]:zone_art_find(o.type,o.subtype,o.frame);
    if(!f){
        scd_zone_art_mailbox[11]=0x4d495353; /* MISS */
        scd_zone_art_mailbox[12]=o.type;
        scd_zone_art_mailbox[13]=o.subtype;
        scd_zone_art_mailbox[14]=o.frame;
        scd_zone_art_mailbox[15]=(uint16_t)x<<16|(uint16_t)y;
        /* Metallic Madness actor art is not packed yet (METALLIC-MADNESS-PLAN.md
           art gate): record the miss above and draw nothing. */
        if(stage_zone==6){art_miss(o.type,o.subtype,o.frame);return;}
        abort();
    }
    int ox=x,oy=y;
    /* A pose is one record, or several consecutive part records (drawn back
       to front) when the pose is stored per original mapping piece. */
    for(const zone_art_part *d=NULL;!d || d->more;f+=SCD_ZONE_ART_RECORD){
    d=zone_art_part_get(f);
    if(*count+1>=189+SCD_OBJECT_CAPACITY)return;
    x=ox;y=oy;
    unsigned w=d->w,h=d->h,offset=d->offset,clut=d->clut;
    int left=d->left,top=d->top;
    left=o.flags&1?-left-(int)w:left;top=o.flags&2?-top-(int)h:top;
    x+=left;y+=top;
    if(x>=320 || x+(int)w<=0 || y>=224 || y+(int)h<=0)continue;
    vdp1_cmdt_t *cmd=sprite_commands->cmdts+(*count)++;
    memset(cmd,0,sizeof(*cmd));vdp1_cmdt_normal_sprite_set(cmd);
    const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_CLUT_16,.end_code_disable=true};
    vdp1_cmdt_draw_mode_set(cmd,mode);vdp1_cmdt_char_size_set(cmd,w,h);
    vdp1_cmdt_char_base_set(cmd,VDP1_VRAM(SCD_ZONE_ART_BASE+offset));
    cmd->cmd_colr=(SCD_ZONE_ART_BASE+clut)/8;
    vdp1_cmdt_char_flip_set(cmd,(vdp1_cmdt_char_flip_t)((o.flags&3)<<4));
    cmd->cmd_xa=x;cmd->cmd_ya=y;
    unsigned n=scd_zone_art_mailbox[7];
    if(n<SCD_OBJECT_CAPACITY){
        volatile uint32_t *r=scd_zone_art_mailbox+16+n*8;
        r[0]=o.type|(unsigned)o.subtype<<8;r[1]=o.frame;r[2]=x;r[3]=y;
        r[4]=o.flags&3;r[5]=w<<16|h;r[6]=SCD_ZONE_ART_BASE+offset;r[7]=*count-1;
        scd_zone_art_mailbox[7]=n+1;
    }
    }
}
static void zone_object_sprite(unsigned *count,scd_object_view o,int x,int y){zone_object_sprite_record(count,o,x,y,NULL);}
/* Emulator-only visual fixture. No controller sets this magic request. It
   uses the same command builder and uploaded textures as ordinary gameplay. */
static void zone_object_probe(unsigned *count){
    /* Record index: bits 0-7, high byte in bits 16-23 (packs hold up to 512). */
    uint32_t request=scd_zone_art_mailbox[9];unsigned index=(request&255)|((request>>16)&255)<<8;
    /* 0xa8/0xa9: Metallic Madness Act 3's fight/Amy bank (BOSS_8.C PLC 4/5). */
    if(((request>>24)==0xa8 || (request>>24)==0xa9) && stage_zone==6 && stage_act==2 && scd_zone_art_mailbox[10]!=request){
        zone_object_art_load_slot((request>>24)-0xa8);scd_zone_art_mailbox[10]=request;return;
    }
    if((request>>24)==0xa6 && stage_zone==1 && stage_act<2 && era<2 && index<(era==1?6u:2u)){
        static const uint8_t poses[2][6]={{0,2},{1,3,4,5,6,7}};
        scd_object_view o={0,0,SCD_OBJ_CC_GENERATOR,0,(request>>8)&3,poses[era][index]};
        *count=2;scd_zone_art_mailbox[7]=0;cc_generator_sprite(count,o,160,112);
        vdp2_scrn_display_set(0);zone_art_probe_active=1;scd_zone_art_mailbox[10]=request;
    }else if((request>>24)==0xa7 && stage_zone==0 && index<OBJECT_FRAME_COUNT){
        /* Palmtree Panic draws from the common object atlas: one atlas frame
           through the gameplay object_sprite builder (tools/test_ppz_art_emulator.py). */
        *count=2;scd_zone_art_mailbox[7]=0;
        object_sprite(count,index,160,112,(request>>8)&3);
        volatile uint32_t *r=scd_zone_art_mailbox+16;const vdp1_cmdt_t *cmd=sprite_commands->cmdts+*count-1;
        r[0]=0;r[1]=index;r[2]=(uint32_t)(int32_t)cmd->cmd_xa;r[3]=(uint32_t)(int32_t)cmd->cmd_ya;r[4]=(request>>8)&3;
        r[5]=object_widths[index]<<16|object_heights[index];r[6]=OBJECT_ATLAS_BASE+object_raw_offsets[index];r[7]=*count-1;
        scd_zone_art_mailbox[7]=1;
        vdp2_scrn_display_set(0);zone_art_probe_active=1;scd_zone_art_mailbox[10]=request;
    }else if((request>>24)==0xa5 && index<zone_art.count){
        const uint8_t *f=zone_art.frames+index*SCD_ZONE_ART_RECORD;
        unsigned kind=scd_zone_art_u16(f),sub=kind==168?128:kind==178 || kind==179 || kind==180 || kind==183 || kind==184?255:kind==278 || kind==279 || kind==189 || kind==193?1:kind==293?254:0;
        /* ZAR3 (Tidal Tempest) kinds are type|subtype<<8. */
        if(zone_art.lz){sub=kind>>8;kind&=255;}
        scd_object_view o={0,0,zone_art.lz?kind:kind==168?68:kind==178 || kind==179 || kind==180 || kind==183 || kind==184?kind-100:kind==278 || kind==279 || kind==293?kind-200:kind==189 || kind==193?kind-100:kind,sub,(request>>8)&3,scd_zone_art_u16(f+2)};
        *count=2;scd_zone_art_mailbox[7]=0;zone_object_sprite(count,o,160,112);
        vdp2_scrn_display_set(0);zone_art_probe_active=1;
        scd_zone_art_mailbox[10]=request;
    }else if(zone_art_probe_active){
        vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0|VDP2_SCRN_DISPTP_NBG1|VDP2_SCRN_DISPTP_NBG3);
        zone_art_probe_active=0;
    }
}
