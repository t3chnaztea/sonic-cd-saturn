/* D.A. Garden program from DA Garden/Main.asm, Sub.asm and Objects (USA).
   Native C for the Saturn and the host test; the retail disc in the pinned Sega CD core
   is the QA oracle (tools/dagarden_retail.py, tools/test_dagarden.py).
   Every function and table carries the fe_dg_ prefix: in the Saturn build its section
   (.text.fe_* / .rodata.fe_*) lands in the front-end overlay (src/saturn.x .zone_R0),
   which resident code reaches only through fe_dagarden_zone_ops. */
#ifdef SCD_ZONE_OVERLAY
#define scd_dagarden_open fe_dagarden_open
#define scd_dagarden_start fe_dagarden_start
#define scd_dagarden_vint fe_dagarden_vint
#define scd_dagarden_render fe_dagarden_render
#define scd_dagarden_lag_frames fe_dagarden_lag_frames
#define scd_dagarden_track_music fe_dagarden_track_music
#endif
#include "dagarden.h"
#include <string.h>
#include "dagarden-parts.inc"
#define special_sines fe_dg_sines
#include "special-sine.inc"
#undef special_sines

static unsigned fe_dg_be16(const uint8_t *p){return ((unsigned)p[0]<<8)|p[1];}
static uint32_t fe_dg_be32(const uint8_t *p){return ((uint32_t)fe_dg_be16(p)<<16)|fe_dg_be16(p+2);}

int scd_dagarden_open(scd_dagarden_pack *pack,const void *data,size_t size){
    memset(pack,0,sizeof(*pack));const uint8_t *d=data;
    if(!d || size<8+8*SCD_DG_PARTS || memcmp(d,"DAG1",4) || fe_dg_be32(d+4)!=SCD_DG_PARTS || DG_PART_COUNT!=SCD_DG_PARTS)return -1;
    for(unsigned i=0;i<SCD_DG_PARTS;i++){
        uint32_t offset=fe_dg_be32(d+8+i*8),length=fe_dg_be32(d+12+i*8);
        if(offset>size || length>size-offset)return -1;
        pack->offset[i]=offset;pack->length[i]=length;
    }
    static const uint32_t fe_dg_fixed[][2]={{DG_PART_STAMPS_PRESENT,25600},{DG_PART_STAMPS_GOOD,27648},{DG_PART_STAMPS_BAD,26112},
        {DG_PART_STAMPS_ANIM,12800},{DG_PART_STAMPS_ANIM_BAD,12800},{DG_PART_STAMP_MAP_PRESENT,112},{DG_PART_STAMP_MAP_GOOD,112},
        {DG_PART_STAMP_MAP_BAD,112},{DG_PART_MAP_BACKGROUND,1792},{DG_PART_TABLES,DG_TABLES_BYTES}};
    for(unsigned i=0;i<sizeof(fe_dg_fixed)/sizeof(fe_dg_fixed[0]);i++)if(pack->length[fe_dg_fixed[i][0]]!=fe_dg_fixed[i][1])return -1;
    for(unsigned i=DG_PART_TITLE_FIRST;i<DG_PART_TITLE_FIRST+SCD_DG_TRACKS;i++)if(pack->length[i]>0x480)return -1;
    pack->data=d;pack->size=size;return 0;
}
static const uint8_t *fe_dg_part(const scd_dagarden *t,unsigned i){return t->pack->data+t->pack->offset[i];}
static const uint8_t *fe_dg_tab(const scd_dagarden *t,unsigned offset){return fe_dg_part(t,DG_PART_TABLES)+offset;}
static unsigned fe_dg_tabw(const scd_dagarden *t,unsigned offset){return fe_dg_be16(fe_dg_tab(t,offset));}

/* ---- Mega Drive VRAM ---------------------------------------------------------- */
static void fe_dg_vram_write(scd_dagarden *t,unsigned address,const uint8_t *data,unsigned length){
    if(address>=0x10000)return;
    if(length>0x10000-address)length=0x10000-address;
    memcpy(t->vram+address,data,length);
    for(unsigned a=address&~31u;a<address+length;a+=32){
        unsigned tile=a>>5;t->sprite_dirty[tile>>5]|=1u<<(tile&31);
        if(a<0xE000)t->tile_dirty[tile>>5]|=1u<<(tile&31);
        if(a>=0xC000 && a<0xD000)t->plane_dirty[0]|=1u<<((a-0xC000)>>7);
        else if(a>=0xE000 && a<0xF000)t->plane_dirty[1]|=1u<<((a-0xE000)>>7);
    }
}
static void fe_dg_vram_word(scd_dagarden *t,unsigned address,unsigned value){
    const uint8_t w[2]={(uint8_t)(value>>8),(uint8_t)value};fe_dg_vram_write(t,address,w,2);
}

/* ---- 68000 helpers -------------------------------------------------------------- */
static int32_t fe_dg_muls(int32_t a,int32_t b){return (int32_t)(int16_t)a*(int16_t)b;}
/* DIVS.W: remainder in the high word, quotient in the low word; on overflow the
   destination is unchanged. */
static uint32_t fe_dg_divs(uint32_t value,int16_t divisor){
    int32_t v=(int32_t)value;
    if(!divisor || (v==INT32_MIN && divisor==-1))return value;
    int32_t q=v/divisor,r=v%divisor;
    if(q<-32768 || q>32767)return value;
    return ((uint32_t)(uint16_t)r<<16)|(uint16_t)q;
}
static uint32_t fe_dg_divu(uint32_t value,uint16_t divisor){
    if(!divisor)return value;
    uint32_t q=value/divisor,r=value%divisor;
    if(q>0xFFFF)return value;
    return (r<<16)|q;
}
static uint32_t fe_dg_swap(uint32_t v){return v<<16|v>>16;}
/* move.w into d1: the high word stays (Main CPU code reads d1's high word in several
   DIVS, so the register is kept as the original leaves it). */
static void fe_dg_d1w(scd_dagarden *t,unsigned value);
/* Main.asm Random: returns d0 (high word: the seed's high word before the update). */
static uint32_t fe_dg_random(scd_dagarden *t){
    uint32_t d1=t->seed?t->seed:0x2A6D365Au,d0=d1;
    d1<<=2;d1+=d0;d1<<=3;d1+=d0;
    uint16_t lo=(uint16_t)(d1+(d1>>16));
    d0=(d0&0xFFFF0000u)|lo;
    t->seed=((uint32_t)lo<<16)|(d1&0xFFFF);
    return d0;
}
static int fe_dg_sine(unsigned value){
    value&=0x1FF;unsigned i=value&127;if(value&128)i^=127;
    return value&256?-fe_dg_sines[i]:fe_dg_sines[i];
}

/* ---- Art ------------------------------------------------------------------------ */
/* Main.asm LoadArt IDs 1..73: art part and VRAM address. */
static void fe_dg_load_art(scd_dagarden *t,unsigned id){
    static const uint8_t fe_dg_art_parts[9]={DG_PART_ART_FLICKY,DG_PART_ART_FLICKY,DG_PART_ART_STAR,DG_PART_ART_STAR,DG_PART_ART_UFO,DG_PART_ART_UFO,
        DG_PART_ART_EGGMAN,DG_PART_ART_METAL,DG_PART_ART_TAILS};
    static const uint8_t fe_dg_art_slot2[9]={0,1,0,1,0,1,0,0,0};
    unsigned part,address;
    if(id>=1 && id<=9){part=fe_dg_art_parts[id-1];address=fe_dg_art_slot2[id-1]?0xBB80:0xB700;}
    else if(id>=10 && id<10+2*SCD_DG_TRACKS){part=DG_PART_TITLE_FIRST+(id-10)%SCD_DG_TRACKS;address=id>=10+SCD_DG_TRACKS?0xBB80:0xB700;}
    else return;
    fe_dg_vram_write(t,address,fe_dg_part(t,part),t->pack->length[part]);
    static const uint16_t fe_dg_nem_bytes[DG_PART_COUNT]=DG_PART_NEM_BYTES;
    if(id>=10)t->title_bytes+=t->pack->length[part]+fe_dg_nem_bytes[part];
    else t->art_bytes+=t->pack->length[part]+fe_dg_nem_bytes[part];
    t->art_last=(uint8_t)id;
    t->d1=id;  /* LoadArt: moveq #0,d1; move.b d0,d1 (NemDec keeps d1) */
}
static void fe_dg_d1w(scd_dagarden *t,unsigned value){t->d1=(t->d1&0xFFFF0000u)|(uint16_t)value;}

/* ---- Objects -------------------------------------------------------------------- */
enum {OBJ_FLICKY=1,OBJ_STAR,OBJ_EGGMAN,OBJ_UFO,OBJ_METAL,OBJ_TAILS,OBJ_TITLE};
static int fe_dg_find_slot(scd_dagarden *t){
    for(unsigned i=0;i<SCD_DG_OBJECTS;i++)if(!t->objects[i].id)return (int)i;
    return -1;
}
static int fe_dg_objects_loaded(const scd_dagarden *t){
    for(unsigned i=0;i<SCD_DG_OBJECTS;i++)if(t->objects[i].id)return 1;
    return 0;
}
static int16_t fe_dg_hi(int32_t v){return (int16_t)((uint32_t)v>>16);}
static void fe_dg_set_hi(int32_t *v,int value){*v=(int32_t)(((uint32_t)(uint16_t)value<<16)|((uint32_t)*v&0xFFFF));}
static void fe_dg_add_hi(int32_t *v,int value){fe_dg_set_hi(v,fe_dg_hi(*v)+value);}
static void fe_dg_set_map(scd_dagarden *t,scd_dagarden_object *o,unsigned map){o->map=(uint16_t)map;(void)t;}

static int fe_dg_offscreen(const scd_dagarden_object *o){
    int x=fe_dg_hi(o->x),y=fe_dg_hi(o->y);
    return x<=-80 || x>=336 || y<=-5 || y>=224;
}
/* DeleteObject. */
static void fe_dg_delete(scd_dagarden *t,scd_dagarden_object *o){t->spawn_flags^=o->spawn_id;o->flags|=0x10;}
/* DelObjFromGroup. */
static void fe_dg_delete_group(scd_dagarden *t,scd_dagarden_object *o){
    unsigned id=o->id;o->id=0;int found=0;
    for(unsigned i=0;i<SCD_DG_OBJECTS;i++)if(t->objects[i].id==id){found=1;break;}
    if(!found){t->d1=(t->d1&0xFFFFFF00u)|o->spawn_id;t->spawn_flags^=o->spawn_id;}
    o->flags|=0x10;
}
/* FindOtherObjByID: the first other slot with the same ID. */
static scd_dagarden_object *fe_dg_find_other(scd_dagarden *t,scd_dagarden_object *o){
    for(unsigned i=0;i<SCD_DG_OBJECTS;i++)if(t->objects[i].id==o->id && t->objects+i!=o)return t->objects+i;
    return 0;
}
/* Float: Y offset from the float angle (amplitude in amp, or a fixed one), random angle step. */
static void fe_dg_float(scd_dagarden *t,scd_dagarden_object *o,int amp,int speed){
    fe_dg_add_hi(&o->y,-o->yoff);
    int32_t d3=fe_dg_muls(fe_dg_sine((unsigned)(uint16_t)o->float_angle),amp)>>8;
    o->yoff=(int16_t)d3;fe_dg_add_hi(&o->y,(int16_t)d3);
    uint32_t d0=fe_dg_divs(fe_dg_random(t)&0x7FFF,(int16_t)speed);
    o->float_angle=(int16_t)(o->float_angle+(int16_t)(d0>>16));
    if(o->float_angle>=0x1FF)o->float_angle=(int16_t)(o->float_angle-0x1FF);
}
/* ObjMoveFloat. Returns 1 when the object was deleted. */
static int fe_dg_move_float(scd_dagarden *t,scd_dagarden_object *o){
    if(fe_dg_offscreen(o)){fe_dg_delete_group(t,o);return 1;}
    fe_dg_d1w(t,(uint16_t)o->float_speed);
    fe_dg_float(t,o,o->float_amp,o->float_speed);
    int32_t vx=o->xvel;if(t->sel_flags)vx=(int32_t)((uint32_t)vx<<3);
    o->x+=vx;t->d1=(uint32_t)o->yvel;o->y+=o->yvel;
    return 0;
}
static void fe_dg_flicky_move(scd_dagarden *t,scd_dagarden_object *o){
    if(!((o->flags&2) && o->yvel>0))fe_dg_float(t,o,4,0x30);
    int32_t vx=o->xvel;if(t->sel_flags)vx=(int32_t)((uint32_t)vx<<3);
    o->x+=vx;o->y+=o->yvel;
}
static void fe_dg_flicky(scd_dagarden *t,scd_dagarden_object *o){
    switch(o->routine){
    case 0:
        o->tile+=0x4000;o->anim_frame=0;o->xoff=o->yoff=0;
        o->routine=(o->flags&2)?3:(o->flags&1)?2:1;return;
    case 1:if(fe_dg_offscreen(o)){fe_dg_delete_group(t,o);return;}
        fe_dg_flicky_move(t,o);return;
    case 2:{
        if(fe_dg_offscreen(o)){fe_dg_delete_group(t,o);return;}
        fe_dg_flicky_move(t,o);
        scd_dagarden_object *other=fe_dg_find_other(t,o);int d=0;
        if(other){d=(int16_t)(fe_dg_hi(o->x)-fe_dg_hi(other->x));if(d<0)d=(int16_t)-d;}
        if(!other || d>=72){
            fe_dg_set_map(t,o,DG_L_MapSpr_FlickyCatchUp);o->anim_frame=0;
            o->xvel=o->xvel>=0?0x30000:-0x30000;
        }else if(d<=32){
            fe_dg_set_map(t,o,DG_L_MapSpr_FlickySlow);o->anim_frame=0;
            o->xvel=o->xvel>=0?0xA000:-0xA000;
        }
        return;
    }
    case 3:{
        if(fe_dg_offscreen(o)){fe_dg_delete_group(t,o);return;}
        fe_dg_flicky_move(t,o);
        scd_dagarden_object *other=fe_dg_find_other(t,o);int d=0;
        if(other){d=(int16_t)(fe_dg_hi(o->y)-fe_dg_hi(other->y));if(d<=0)d=0;}
        if(!other || d>=58){
            fe_dg_set_map(t,o,DG_L_MapSpr_FlickyCatchUp);o->anim_frame=0;o->yvel=-0xB000;
        }else if(d<=8){
            fe_dg_set_map(t,o,DG_L_MapSpr_FlickyGlide);o->anim_frame=0;o->yvel=0xE000;
        }
        return;
    }
    }
}
static void fe_dg_star(scd_dagarden *t,scd_dagarden_object *o){
    if(!o->routine){
        o->tile+=0x4000;o->anim_frame=0;fe_dg_set_map(t,o,DG_L_MapSpr_Star);o->anim_time=(uint16_t)fe_dg_tabw(t,DG_L_MapSpr_Star+2);
        o->xoff=o->yoff=0;o->routine=1;return;
    }
    if(fe_dg_offscreen(o)){fe_dg_delete_group(t,o);return;}
    uint32_t d0=fe_dg_divs(fe_dg_random(t)&0x7FFF,0x28);
    o->float_angle=(int16_t)(o->float_angle+(int16_t)(d0>>16));
    if(o->float_angle>=0x1FF)o->float_angle=(int16_t)(o->float_angle-0x1FF);
    o->x+=o->xvel;o->y+=o->yvel;
}
/* GetObjDestX. */
static void fe_dg_dest_x(scd_dagarden *t,scd_dagarden_object *o){
    uint32_t d0=fe_dg_divs(fe_dg_random(t)&0x7FFF,32);
    int dist=(int16_t)((d0>>16)+64);
    int x=fe_dg_hi(o->x);
    x=(o->flags&0x80)?x-dist:x+dist;
    fe_dg_d1w(t,(uint16_t)x);o->dest_x=(int16_t)x;
}
/* ObjMoveToDest (UFO and Tails routine 3). */
static void fe_dg_move_to_dest(scd_dagarden *t,scd_dagarden_object *o){
    if(fe_dg_offscreen(o)){fe_dg_delete_group(t,o);return;}
    int32_t vx=o->xvel;if(t->sel_flags)vx=(int32_t)((uint32_t)vx<<3);
    o->x+=vx;int x=fe_dg_hi(o->x);
    int reached=o->xvel>=0?x>=o->dest_x:x<=o->dest_x;
    if(reached && o->timer>=0)o->routine=1;
    t->d1=(uint32_t)o->yvel;o->y+=o->yvel;int y=fe_dg_hi(o->y);fe_dg_d1w(t,(uint16_t)y);
    reached=o->yvel>=0?y>=o->dest_y:y<=o->dest_y;
    if(reached && o->timer>=0)o->routine=1;
}
static void fe_dg_ufo(scd_dagarden *t,scd_dagarden_object *o){
    switch(o->routine){
    case 0:{
        o->tile+=0x4000;o->anim_frame=0;fe_dg_set_map(t,o,DG_L_MapSpr_UFO);o->anim_time=(uint16_t)fe_dg_tabw(t,DG_L_MapSpr_UFO+2);
        o->xoff=o->yoff=0;
        uint32_t d0=fe_dg_random(t)&0x7FFF;fe_dg_d1w(t,d0);
        d0=fe_dg_divs(d0,5);o->timer=(int8_t)(((d0>>16)+1)&0xFF);
        t->d1=fe_dg_swap(fe_dg_divs(t->d1,64));o->timer2=(int8_t)t->d1;
        o->routine=2;return;
    }
    case 1:
        if(o->timer==3){
            o->routine=2;o->xvel=o->yvel=0;fe_dg_set_map(t,o,DG_L_MapSpr_UFO);o->anim_frame=0;o->timer2=24;
        }else{
            fe_dg_dest_x(t,o);
            /* ObjUFO_StartMoving. */
            o->routine=3;
            uint32_t d0=fe_dg_random(t)&0x7FFF;fe_dg_d1w(t,d0);
            d0=fe_dg_divs(d0,64)&0xFFFF0000u;d0=(uint32_t)((int32_t)d0>>4)+0x20000;
            o->xvel=(int32_t)d0;if(!(o->flags&8))o->xvel=-o->xvel;
            int32_t d7=o->yvel;
            uint32_t d1=fe_dg_divs(t->d1,96)&0xFFFF0000u;d1=(uint32_t)((int32_t)d1>>4);t->d1=d1;
            o->yvel=(int32_t)d1;fe_dg_set_hi(&o->yvel,fe_dg_hi(o->yvel)+5);
            uint32_t r=fe_dg_divs(fe_dg_random(t)&0x7FFF,56);int dy=(int16_t)(r>>16);
            if(d7>0){o->yvel=-o->yvel;o->dest_y=(int16_t)(dy+32);fe_dg_set_map(t,o,DG_L_MapSpr_UFOUp);}
            else{o->dest_y=(int16_t)(dy+160);fe_dg_set_map(t,o,DG_L_MapSpr_UFODown);}
            o->anim_frame=0;
        }
        if(o->timer>=0)o->timer--;
        return;
    case 2:
        o->float_speed=o->xvel?0x28:0x48;
        if(fe_dg_move_float(t,o))return;
        if(--o->timer2<=0)o->routine=1;
        return;
    case 3:fe_dg_move_to_dest(t,o);return;
    }
}
static void fe_dg_eggman(scd_dagarden *t,scd_dagarden_object *o){
    if(!o->routine){
        o->tile+=0x4000;o->anim_frame=0;fe_dg_set_map(t,o,DG_L_MapSpr_Eggman);o->anim_time=(uint16_t)fe_dg_tabw(t,DG_L_MapSpr_Eggman+2);
        o->xoff=o->yoff=0;o->timer=3;o->routine=1;return;
    }
    int check=1;
    if(o->timer>0){
        if(--o->timer>0)check=0;
        else fe_dg_set_map(t,o,DG_L_MapSpr_Eggman);
    }
    if(check){
        uint32_t d0=fe_dg_random(t)&0x7FFF;fe_dg_d1w(t,d0);
        d0=fe_dg_divs(d0,16);
        if(!(d0>>16&0xFFFF)){
            t->d1=fe_dg_swap(fe_dg_divs(t->d1,16));fe_dg_d1w(t,t->d1+32);
            o->timer=(int8_t)t->d1;fe_dg_set_map(t,o,DG_L_MapSpr_EggmanTurn);
        }
    }
    fe_dg_move_float(t,o);
}
static void fe_dg_metal(scd_dagarden *t,scd_dagarden_object *o){
    switch(o->routine){
    case 0:
        o->tile+=0x4000;o->anim_frame=0;fe_dg_set_map(t,o,DG_L_MapSpr_MetalSonic);o->anim_time=(uint16_t)fe_dg_tabw(t,DG_L_MapSpr_MetalSonic+2);
        o->routine=1;return;
    case 1:{
        if(fe_dg_offscreen(o)){fe_dg_delete(t,o);return;}
        int32_t d0=o->xvel,d1=o->yvel;t->d1=(uint32_t)d1;
        if(t->sel_flags){
            o->xvel=(o->flags&0x80)?-0x180000:0x180000;o->yvel=0;o->routine=4;return;
        }
        o->x+=d0;o->y+=d1;
        int x=fe_dg_hi(o->x),y=fe_dg_hi(o->y);
        if((o->flags&0x80)?x<=128:x>=128){fe_dg_set_hi(&o->x,128);o->xvel=0;}
        y=fe_dg_hi(o->y);
        if((o->flags&8)?y>=100:y<=100){fe_dg_set_hi(&o->y,100);o->yvel=0;}
        (void)x;
        if(fe_dg_hi(o->x)==128 && fe_dg_hi(o->y)==100){o->timer=64;o->timer2=8;o->routine=2;}
        return;
    }
    case 2:
        if(!t->sel_flags){
            if(o->timer<0){fe_dg_move_float(t,o);return;}
            if(!o->timer2){
                o->timer2=24;
                if(fe_dg_random(t)&1)o->flags|=0x80;else o->flags&=0x7F;
            }
            o->timer2--;
            if(--o->timer>=0){fe_dg_move_float(t,o);return;}
        }
        o->timer=48;o->float_speed=0x100;o->float_amp=2;fe_dg_set_map(t,o,DG_L_MapSpr_MetalSonicBackUp);o->anim_frame=0;
        o->xvel=(o->flags&0x80)?0x10000:-0x10000;o->routine=3;return;
    case 3:
        if(!t->sel_flags && --o->timer>0){fe_dg_move_float(t,o);return;}
        o->float_speed=0;o->float_amp=0;o->xvel=(o->flags&0x80)?-0x180000:0x180000;o->routine=4;return;
    case 4:{
        if(fe_dg_offscreen(o)){fe_dg_delete(t,o);return;}
        int32_t d0=o->xvel,d1=o->yvel;
        if(t->sel_flags){d0=(int32_t)((uint32_t)d0<<1);d1=(int32_t)((uint32_t)d1<<1);}
        t->d1=(uint32_t)d1;o->x+=d0;o->y+=d1;return;
    }
    }
}
static void fe_dg_tails(scd_dagarden *t,scd_dagarden_object *o){
    switch(o->routine){
    case 0:{
        o->tile+=0x4000;o->anim_frame=0;fe_dg_set_map(t,o,DG_L_MapSpr_Tails);o->anim_time=(uint16_t)fe_dg_tabw(t,DG_L_MapSpr_Tails+2);
        uint32_t d0=fe_dg_random(t)&0x7FFF;fe_dg_d1w(t,d0);
        d0=fe_dg_divs(d0,5);o->timer=(int8_t)(((d0>>16)+1)&0xFF);
        t->d1=fe_dg_swap(fe_dg_divs(t->d1,48));o->timer2=(int8_t)t->d1;
        o->routine=2;return;
    }
    case 1:
        fe_dg_dest_x(t,o);
        if(o->timer==3){
            o->xvel=0x20000;o->yvel=0;o->anim_frame=0;fe_dg_set_map(t,o,DG_L_MapSpr_Tails);
            if(o->flags&0x80){o->xvel=-o->xvel;o->yvel=-o->yvel;}
            o->timer2=24;o->routine=2;
        }else{
            o->routine=3;
            uint32_t d0=fe_dg_random(t)&0x7FFF;fe_dg_d1w(t,d0);
            d0=fe_dg_divs(d0,16)&0xFFFF0000u;d0=(uint32_t)((int32_t)d0>>4)+0x20000;
            o->xvel=(int32_t)d0;if(o->flags&0x80)o->xvel=-o->xvel;
            int32_t d7=o->yvel;
            uint32_t d1=fe_dg_divs(t->d1,0x28)&0xFFFF0000u;d1=(uint32_t)((int32_t)d1>>4);t->d1=d1;
            o->yvel=(int32_t)d1;fe_dg_set_hi(&o->yvel,fe_dg_hi(o->yvel)+1);
            uint32_t r=fe_dg_divs(fe_dg_random(t)&0x7FFF,56);int dy=(int16_t)(r>>16);
            int up=d7?d7>0:fe_dg_hi(o->y)>100;
            if(up){o->yvel=-o->yvel;o->dest_y=(int16_t)(dy+32);fe_dg_set_map(t,o,DG_L_MapSpr_TailsUp);}
            else{o->dest_y=(int16_t)(dy+160);fe_dg_set_map(t,o,DG_L_MapSpr_TailsDown);}
            o->anim_frame=0;
        }
        if(o->timer>=0)o->timer--;
        return;
    case 2:
        if(fe_dg_move_float(t,o))return;
        if(--o->timer2<=0)o->routine=1;
        return;
    case 3:fe_dg_move_to_dest(t,o);return;
    }
}
static void fe_dg_title_object(scd_dagarden *t,scd_dagarden_object *o){
    switch(o->routine){
    case 0:{
        o->anim_frame=0;
        unsigned id=t->sel_id;fe_dg_d1w(t,fe_dg_tabw(t,DG_L_MapSpr_TrackTitle+id*2));
        fe_dg_set_map(t,o,DG_L_MapSpr_TrackTitle+(t->d1&0xFFFF));
        if(t->sel_dir&0x100){fe_dg_set_hi(&o->x,-128);o->xvel=0x200000;o->flags|=8;}
        else{fe_dg_set_hi(&o->x,256);o->xvel=-0x200000;o->flags&=~8;}
        fe_dg_set_hi(&o->y,208);
        fe_dg_d1w(t,id*4);o->xoff=(int16_t)fe_dg_tabw(t,DG_L_TrackInfo+id*4+2);
        o->tile+=0xE000;o->routine=1;t->sel_routine=0;return;
    }
    case 1:{
        o->x+=o->xvel;int x=fe_dg_hi(o->x);
        if((o->flags&8)?x<o->xoff:x>o->xoff)return;
        o->xvel=0;fe_dg_set_hi(&o->x,o->xoff);o->routine=2;return;
    }
    case 2:
        if(t->hold&8){o->routine=3;o->xvel=0x200000;o->flags|=8;}
        if(t->hold&4){o->xvel=-0x200000;o->routine=3;o->flags&=~8;}
        return;
    case 3:
        o->x+=o->xvel;
        if(o->flags&8){
            if(fe_dg_hi(o->x)<0x120)return;
            t->sel_flags|=4;t->sel_dir|=0x100;  /* bset #0 on the word's first byte */t->spawn_flags^=o->spawn_id;o->flags|=0x10;
            if(!t->sel_id)t->sel_id=SCD_DG_TRACKS-1;else t->sel_id--;
        }else{
            if(fe_dg_hi(o->x)>-0x80)return;
            t->sel_flags|=4;t->sel_dir&=~0x100u;t->spawn_flags^=o->spawn_id;o->flags|=0x10;
            if(++t->sel_id>SCD_DG_TRACKS-1)t->sel_id=0;
        }
        return;
    }
}
static void fe_dg_run_objects(scd_dagarden *t){
    for(unsigned i=0;i<SCD_DG_OBJECTS;i++){
        scd_dagarden_object *o=t->objects+i;
        switch(o->id){
        case 0:continue;
        case OBJ_FLICKY:fe_dg_flicky(t,o);break;
        case OBJ_STAR:fe_dg_star(t,o);break;
        case OBJ_EGGMAN:fe_dg_eggman(t,o);break;
        case OBJ_UFO:fe_dg_ufo(t,o);break;
        case OBJ_METAL:fe_dg_metal(t,o);break;
        case OBJ_TAILS:fe_dg_tails(t,o);break;
        case OBJ_TITLE:fe_dg_title_object(t,o);break;
        default:break;
        }
        if(o->flags&0x10){memset(o,0,sizeof(*o));t->d1=0;}
    }
}
/* DrawObjects with AnimateObject. */
static void fe_dg_draw_objects(scd_dagarden *t){
    memset(t->sprites,0,8);
    uint8_t *s=t->sprites;unsigned link=0;
    for(unsigned i=0;i<SCD_DG_OBJECTS;i++){
        scd_dagarden_object *o=t->objects+i;
        if(!o->id)continue;
        const unsigned map=o->map;
        if(--o->anim_time==0 || o->anim_time==0xFFFF){
            unsigned frame=o->anim_frame+1u;
            if(frame>=fe_dg_tabw(t,map))frame=0;
            o->anim_frame=(uint16_t)frame;o->anim_time=(uint16_t)fe_dg_tabw(t,map+2+frame*4);
        }
        unsigned piece=map+fe_dg_tabw(t,map+4+o->anim_frame*4);
        unsigned count=fe_dg_tabw(t,piece);piece+=2;
        for(unsigned n=0;n<=count && link<80;n++,piece+=12){
            const uint8_t *p=fe_dg_tab(t,piece);unsigned flip=0;
            int x=fe_dg_hi(o->x);
            if(o->flags&0x80){x-=(int16_t)fe_dg_be16(p+6);flip|=0x800;}else x-=(int16_t)fe_dg_be16(p+4);
            x+=128;
            int y=fe_dg_hi(o->y);
            if(o->flags&0x40){y-=(int16_t)fe_dg_be16(p+10);flip|=0x1000;}else y-=(int16_t)fe_dg_be16(p+8);
            y+=128;
            link++;
            unsigned size=(link|fe_dg_be16(p))&0xFFFF;
            unsigned tile=o->tile;if(o->flags&0x20)tile|=0x8000;
            tile=((tile+fe_dg_be16(p+2))^flip)&0xFFFF;
            s[0]=(uint8_t)(y>>8);s[1]=(uint8_t)y;s[2]=(uint8_t)(size>>8);s[3]=(uint8_t)size;
            s[4]=(uint8_t)(tile>>8);s[5]=(uint8_t)tile;s[6]=(uint8_t)(x>>8);s[7]=(uint8_t)x;s+=8;
        }
    }
    if(link)s[-5]=0;
}
/* ---- Object spawns (UpdateObjSpawns) ---------------------------------------------- */
static void fe_dg_spawn_flickies(scd_dagarden *t){
    if(!(t->spawn_flags&1)){t->spawn_flags|=1;t->spawn_id=1;fe_dg_load_art(t,1);}
    else if(!(t->spawn_flags&2)){t->spawn_flags|=2;t->spawn_id=2;fe_dg_load_art(t,2);}
    else return;
    int16_t d7=(int16_t)fe_dg_random(t);
    int d5=d7>=0?-6:264;
    int d6=(int16_t)(fe_dg_divs(fe_dg_random(t)&0x7FFF,160)>>16)+16;
    unsigned group=fe_dg_divu((uint16_t)d7&0x7FFF,4)>>16;
    static const int8_t fe_dg_flicky_groups[4][2]={{3,0},{3,1},{5,2},{5,2}};
    static const int8_t fe_dg_flicky_pos[3][6][2]={{{0,0},{-24,8},{-48,-8},{-34,20}},{{0,0},{-16,-24},{-16,24},{-32,0}},
        {{0,0},{-16,-22},{-40,-28},{-32,16},{-16,24},{-48,-5}}};
    int d2=fe_dg_flicky_groups[group][0];const int8_t (*pos)[2]=fe_dg_flicky_pos[fe_dg_flicky_groups[group][1]];
    unsigned tile=(t->spawn_id&1)?0x5B8:0x5DC;
    for(;d2>=0;d2--,pos++){
        int slot=fe_dg_find_slot(t);if(slot<0)break;
        scd_dagarden_object *o=t->objects+slot;
        o->tile=(uint16_t)tile;o->spawn_id=t->spawn_id;fe_dg_set_hi(&o->x,d5);fe_dg_set_hi(&o->y,d6);o->float_speed=0x30;o->float_amp=4;
        unsigned map=DG_L_MapSpr_Flicky;int type=0;
        if(d2<=0){
            /* swap d0; beq.s .Normal tests the whole register: only remainder and quotient 0 is
               normal; remainder 1 is slow, anything else glides. */
            uint32_t r=fe_dg_swap(fe_dg_divs(fe_dg_random(t)&0x7FFF,3));
            type=!r?0:(r&0xFFFF)==1?1:2;
        }
        if(type==2){o->flags|=2;o->xvel=0x14000;o->yvel=0xE000;map=DG_L_MapSpr_FlickyGlide;}
        else if(type==1){o->flags|=1;o->xvel=0xA000;o->yvel=0;map=DG_L_MapSpr_FlickySlow;}
        else{o->xvel=0x14000;o->yvel=0;}
        fe_dg_set_map(t,o,map);o->anim_time=(uint16_t)fe_dg_tabw(t,map+2);
        o->flags|=8;o->id=OBJ_FLICKY;
        int dx=(*pos)[0];
        if(d7<0){o->flags|=0x80;o->flags&=~8;dx=-dx;o->xvel=-o->xvel;}
        fe_dg_add_hi(&o->x,dx);fe_dg_add_hi(&o->y,(*pos)[1]);
    }
    t->spawn_id=0;
}
static void fe_dg_spawn_stars(scd_dagarden *t){
    if((int16_t)t->cycle_index<=0xA || (int16_t)t->cycle_index>=0x18)return;
    if(!(t->spawn_flags&1)){t->spawn_flags|=1;t->spawn_id=1;fe_dg_load_art(t,3);}
    else if(!(t->spawn_flags&2)){t->spawn_flags|=2;t->spawn_id=2;fe_dg_load_art(t,4);}
    else return;
    uint32_t d7=fe_dg_random(t);
    int d3=0;int d5=(int16_t)(fe_dg_divs(fe_dg_random(t)&0x7FFF,128)>>16);
    if(!(d5>128))d3=1;
    unsigned tile=(t->spawn_id&1)?0x5B8:0x5DC;fe_dg_d1w(t,tile);
    unsigned group=fe_dg_divu(d7&0x7FFF,5)>>16;
    static const uint8_t fe_dg_star_counts[5]={2,2,1,0,2};
    static const int16_t fe_dg_star_offsets[6]={0,0,32,0,-32,0};
    int d2=fe_dg_star_counts[group];const int16_t *pos=fe_dg_star_offsets;
    for(;d2>=0;d2--){
        int slot=fe_dg_find_slot(t);if(slot<0)break;
        scd_dagarden_object *o=t->objects+slot;
        o->id=OBJ_STAR;o->tile=(uint16_t)tile;o->spawn_id=t->spawn_id;fe_dg_set_hi(&o->x,d5);fe_dg_set_hi(&o->y,0);
        o->xvel=0x20000;if(d3)o->xvel=-o->xvel;
        uint32_t d0=fe_dg_divs(fe_dg_random(t)&0x7FFF,0x80)&0x7FFF0000u;
        o->yvel=0x40000+(int32_t)((int32_t)d0>>4);
        d0=fe_dg_divs(fe_dg_random(t)&0x7FFF,240);
        fe_dg_add_hi(&o->x,(int16_t)(d0>>16));
        fe_dg_add_hi(&o->y,*pos++);
    }
    t->spawn_id=0;
}
static void fe_dg_spawn_ufos(scd_dagarden *t){
    if(!(t->spawn_flags&1)){t->spawn_flags|=1;t->spawn_id=1;fe_dg_load_art(t,5);}
    else if(!(t->spawn_flags&2)){t->spawn_flags|=2;t->spawn_id=2;fe_dg_load_art(t,6);}
    else return;
    int16_t d7=(int16_t)fe_dg_random(t);
    int d5=d7>=0?-6:264;
    int d6=(int16_t)(fe_dg_divs(fe_dg_random(t)&0x7FFF,160)>>16)+16;
    unsigned tile=(t->spawn_id&1)?0x5B8:0x5DC;fe_dg_d1w(t,tile);
    unsigned group=fe_dg_divu((uint16_t)d7&0x7FFF,5)>>16;
    static const uint8_t fe_dg_ufo_counts[5]={0,1,0,1,0};
    static const int16_t fe_dg_ufo_offsets[4]={0,0,0x10,0x30};
    int d2=fe_dg_ufo_counts[group];const int16_t *pos=fe_dg_ufo_offsets;
    for(;d2>=0;d2--){
        int slot=fe_dg_find_slot(t);if(slot<0)break;
        scd_dagarden_object *o=t->objects+slot;
        o->tile=(uint16_t)tile;o->spawn_id=t->spawn_id;fe_dg_set_hi(&o->x,d5);fe_dg_set_hi(&o->y,d6);
        o->float_speed=0x28;o->float_amp=6;o->xvel=0x20000;o->yvel=0;o->flags|=8;o->id=OBJ_UFO;
        int dx=*pos++;
        if(d7<0){o->flags|=0x80;o->flags&=~8;dx=-dx;o->xvel=-o->xvel;o->yvel=-o->yvel;}
        fe_dg_add_hi(&o->x,dx);fe_dg_add_hi(&o->y,*pos++);
    }
    t->spawn_id=0;
}
static void fe_dg_spawn_eggman(scd_dagarden *t){
    if(t->spawn_flags&3){t->spawn_id=0;return;}
    t->spawn_flags|=3;t->spawn_id=3;fe_dg_load_art(t,7);
    int16_t d7=(int16_t)fe_dg_random(t);
    int d5=d7>=0?264:-6;
    int d6=(int16_t)(fe_dg_divs(fe_dg_random(t)&0x7FFF,64)>>16)+128;
    int slot=fe_dg_find_slot(t);
    if(slot>=0){
        scd_dagarden_object *o=t->objects+slot;
        o->tile=0x5B8;o->spawn_id=t->spawn_id;fe_dg_set_hi(&o->x,d5);fe_dg_set_hi(&o->y,d6);
        o->float_speed=0x28;o->float_amp=0xA;o->xvel=-0x14000;o->yvel=-0x8000;o->id=OBJ_EGGMAN;
        if(d7<0){o->flags|=0x80;o->xvel=-o->xvel;}
    }
    t->spawn_id=0;
}
static void fe_dg_spawn_metal(scd_dagarden *t){
    if(t->spawn_flags&3){t->spawn_id=0;return;}
    t->spawn_flags|=3;t->spawn_id=3;fe_dg_load_art(t,8);
    uint32_t r=fe_dg_random(t);int16_t d7=(int16_t)r;
    int d5=(int16_t)(fe_dg_divs(r&0x7FFF,0x100)>>16);
    int d6=d7>=0?192:0;
    int slot=fe_dg_find_slot(t);
    if(slot>=0){
        scd_dagarden_object *o=t->objects+slot;
        o->tile=0x5B8;o->spawn_id=t->spawn_id;fe_dg_set_hi(&o->x,d5);fe_dg_set_hi(&o->y,d6);
        o->float_speed=0x28;o->float_amp=4;o->xvel=0x40000;o->yvel=0x50000;o->flags|=8;o->id=OBJ_METAL;
        if(fe_dg_hi(o->x)>=128){o->flags|=0x80;o->xvel=-o->xvel;}
        if(fe_dg_hi(o->y)>=100){o->flags&=~8;o->yvel=-o->yvel;}
    }
    t->spawn_id=0;
}
static void fe_dg_spawn_tails(scd_dagarden *t){
    if(t->spawn_flags&3){t->spawn_id=0;return;}
    t->spawn_flags|=3;t->spawn_id=3;fe_dg_load_art(t,9);
    int16_t d7=(int16_t)fe_dg_random(t);
    int d5=d7>=0?-6:264;
    int d6=(int16_t)(fe_dg_divs(fe_dg_random(t)&0x7FFF,160)>>16)+32;
    int slot=fe_dg_find_slot(t);
    if(slot>=0){
        scd_dagarden_object *o=t->objects+slot;
        o->tile=0x5B8;o->spawn_id=t->spawn_id;fe_dg_set_hi(&o->x,d5);fe_dg_set_hi(&o->y,d6);
        o->float_speed=0x24;o->float_amp=2;o->xvel=0x20000;o->yvel=0;o->id=OBJ_TAILS;
        if(d7<0){o->flags|=0x80;o->xvel=-o->xvel;o->yvel=-o->yvel;}
    }
    t->spawn_id=0;
}
static void fe_dg_update_spawns(scd_dagarden *t){
    if(t->sel_flags&1)return;
    static const uint16_t fe_dg_spawn_times[6][2]={{300,600},{360,660},{420,720},{480,780},{540,840},{600,900}};
    for(unsigned i=0;i<6;i++){
        unsigned d5=5-i;
        if(t->spawn_timers[i]--)continue;
        t->spawn_timers[i]=fe_dg_spawn_times[d5][0];
        uint32_t d0=fe_dg_random(t)&0xFFFF;t->d1=fe_dg_spawn_times[d5][1];
        d0=fe_dg_divs(d0,(int16_t)t->d1);t->spawn_timers[i]=(uint16_t)(t->spawn_timers[i]+(d0>>16));
        switch(d5){
        case 0:fe_dg_spawn_flickies(t);break;
        case 1:fe_dg_spawn_stars(t);break;
        case 2:fe_dg_spawn_ufos(t);break;
        case 3:fe_dg_spawn_eggman(t);break;
        case 4:fe_dg_spawn_metal(t);break;
        default:fe_dg_spawn_tails(t);break;
        }
        return;
    }
}
static void fe_dg_update_objects(scd_dagarden *t){fe_dg_update_spawns(t);fe_dg_run_objects(t);fe_dg_draw_objects(t);}

/* ---- Track selection --------------------------------------------------------------- */
static void fe_dg_play_track(scd_dagarden *t){
    t->spawn_flags=0;
    t->cmd_track=t->sel_id;
    fe_dg_d1w(t,fe_dg_tabw(t,DG_L_TrackInfo+t->sel_id*4));
    unsigned zone=t->d1&0xFFFF;
    if(zone!=3)t->zone=(uint16_t)zone;
    t->cmd_zone=(uint16_t)zone;
    t->main_flags&=~0x10;t->main_flags|=0x20;
}
static void fe_dg_check_text_spawn(scd_dagarden *t){
    if(!(t->sel_flags&4) || fe_dg_objects_loaded(t))return;
    t->main_flags|=0x10;t->sel_flags&=~4;t->sel_routine=1;
}
static void fe_dg_track_selection(scd_dagarden *t){
    if(t->sel_routine==1){
        int slot=fe_dg_find_slot(t);if(slot<0)return;
        t->sel_title=(uint16_t)slot;t->sel_flags|=2;t->sel_routine=2;return;
    }
    if(t->sel_routine)return;
    /* TrkSel_CheckPlay: C, then B, then A. */
    for(unsigned k=0;k<2;k++){
        const unsigned bit=k?0x10:0x20;
        if(t->hold&bit){t->button_flags|=bit;continue;}
        if(!(t->button_flags&bit))continue;
        if(!(t->sel_flags&1)){t->button_flags&=~bit;continue;}
        if(t->sel_flags&4)continue;
        t->button_flags&=~bit;fe_dg_play_track(t);return;
    }
    if(t->hold&0x40){t->button_flags|=0x40;return;}
    if(t->button_flags&0x40){
        if(!(t->sel_flags&1)){t->sel_flags|=5;t->button_flags&=~0x40;}
        else if(!(t->sel_flags&4)){t->button_flags&=~0x40;fe_dg_play_track(t);return;}
    }
    fe_dg_check_text_spawn(t);
}
static void fe_dg_check_title_spawn(scd_dagarden *t){
    if(!(t->sel_flags&2))return;
    t->sel_flags&=~2;
    scd_dagarden_object *o=t->objects+t->sel_title;
    o->id=OBJ_TITLE;
    if(!(t->spawn_flags&1)){t->spawn_flags|=1;o->tile=0x5B8;o->spawn_id=1;fe_dg_load_art(t,10+t->sel_id);}
    else{t->spawn_flags|=2;o->tile=0x5DC;o->spawn_id=2;fe_dg_load_art(t,10+SCD_DG_TRACKS+t->sel_id);}
}

/* ---- Palettes ----------------------------------------------------------------------- */
static const uint16_t fe_dg_cycle_tables[3][2]={{DG_L_PalCyc_PlanetPresent,DG_L_PalCyc_BgPresentGF},
    {DG_L_PalCyc_PlanetGoodFut,DG_L_PalCyc_BgPresentGF},{DG_L_PalCyc_PlanetBadFut,DG_L_PalCyc_BgBadFuture}};
static void fe_dg_words(const scd_dagarden *t,uint16_t *out,unsigned offset,unsigned count){
    for(unsigned i=0;i<count;i++)out[i]=(uint16_t)fe_dg_tabw(t,offset+i*2);
}
static void fe_dg_init_animation(scd_dagarden *t){
    t->cycle_index=0;t->cycle_timer=(uint16_t)fe_dg_tabw(t,DG_L_PalCycleTimes);
    t->volcano_index=0;t->volcano_timer=(uint16_t)fe_dg_tabw(t,DG_L_VolcanoAnimTimes);
    /* The volcano stamps InitAnimation writes go to Word RAM the Sub CPU holds here; the
       next UpdatePlanetData replaces the stamp map. */
    fe_dg_d1w(t,0xD8);
    t->sprite_cycle_timer=5;t->sprite_cycle_index=0;
}
/* ResetDAGarden's LoadPalette (with InitAnimation). */
static void fe_dg_load_palette(scd_dagarden *t){
    unsigned zone=t->zone<3?t->zone:0;
    unsigned planet=fe_dg_cycle_tables[zone][0],bg=fe_dg_cycle_tables[zone][1];
    planet+=fe_dg_tabw(t,planet);
    t->d1=(uint32_t)fe_dg_tabw(t,bg)<<16|fe_dg_tabw(t,bg+2);  /* BUG in the original: move.l reads two offsets */
    bg+=t->d1&0xFFFF;
    fe_dg_words(t,t->fade,bg,16);fe_dg_words(t,t->fade+16,planet,16);
    fe_dg_words(t,t->fade+32,DG_L_PalCyc_Sprites0,16);fe_dg_words(t,t->fade+48,DG_L_Pal_SelMenu,16);
    fe_dg_init_animation(t);
}
static void fe_dg_fade_to_white(scd_dagarden *t,uint16_t *p){
    for(unsigned i=0;i<=t->fade_len;i++){
        uint16_t *c=p+t->fade_start/2+i;unsigned v=*c;fe_dg_d1w(t,v);
        if(v==0xEEE)continue;
        if((v&0xE)!=0xE)*c=(uint16_t)(v+2);else if((v&0xE0)!=0xE0)*c=(uint16_t)(v+0x20);else if((v&0xE00)!=0xE00)*c=(uint16_t)(v+0x200);
    }
}
static void fe_dg_fade_from_white(scd_dagarden *t){
    for(unsigned i=0;i<=t->fade_len;i++){
        unsigned target=t->fade[t->fade_start/2+i];uint16_t *c=t->palette+t->fade_start/2+i;unsigned v=*c;
        if(v==target)continue;
        if(v>=0x200 && (uint16_t)(v-0x200)>=target){*c=(uint16_t)(v-0x200);fe_dg_d1w(t,*c);}
        else if(v>=0x20 && (uint16_t)(v-0x20)>=target){*c=(uint16_t)(v-0x20);fe_dg_d1w(t,*c);}
        else{fe_dg_d1w(t,v>=0x20?v-0x20:v-0x200);*c=(uint16_t)(v-2);}
    }
}
static void fe_dg_fade_from_black(scd_dagarden *t){
    for(unsigned i=0;i<=t->fade_len;i++){
        unsigned target=t->fade[t->fade_start/2+i];uint16_t *c=t->palette+t->fade_start/2+i;unsigned v=*c;
        if(v==target)continue;
        if((uint16_t)(v+0x200)<=target){*c=(uint16_t)(v+0x200);fe_dg_d1w(t,*c);}
        else if((uint16_t)(v+0x20)<=target){*c=(uint16_t)(v+0x20);fe_dg_d1w(t,*c);}
        else{fe_dg_d1w(t,v+0x20);*c=(uint16_t)(v+2);}
    }
}
static void fe_dg_fade_to_black(scd_dagarden *t,uint16_t *p){
    for(unsigned i=0;i<=t->fade_len;i++){
        uint16_t *c=p+t->fade_start/2+i;unsigned v=*c;
        if(!v)continue;
        fe_dg_d1w(t,v);
        if(v&0xE)*c=(uint16_t)(v-2);else if(v&0xE0)*c=(uint16_t)(v-0x20);else if(v&0xE00)*c=(uint16_t)(v-0x200);
    }
}
/* V-INT palette cycle and CRAM upload (VInt_Done). */
static void fe_dg_cram(scd_dagarden *t){for(unsigned i=0;i<64;i++)t->cram[i]=(uint16_t)(t->palette[i]&0xEEE);}
static void fe_dg_vint_palette(scd_dagarden *t){
    if(t->no_cycle){fe_dg_cram(t);return;}
    if(--t->cycle_timer==0 || t->cycle_timer==0xFFFF){
        if((int16_t)t->cycle_index>=0x1F)t->cycle_index=0;
        unsigned d0=t->cycle_index*2u;
        t->cycle_timer=(uint16_t)fe_dg_tabw(t,DG_L_PalCycleTimes+d0);t->cycle_index++;
        unsigned zone=t->zone<3?t->zone:0;
        unsigned planet=fe_dg_cycle_tables[zone][0],bg=fe_dg_cycle_tables[zone][1];
        planet+=fe_dg_tabw(t,planet+d0);bg+=fe_dg_tabw(t,bg+d0);
        fe_dg_words(t,t->palette,bg,16);fe_dg_words(t,t->palette+16,planet,16);
    }
    if((int16_t)--t->sprite_cycle_timer>0)return;
    unsigned d0=t->sprite_cycle_index;
    fe_dg_words(t,t->palette+32,DG_L_SprPalCycTable+fe_dg_tabw(t,DG_L_SprPalCycTable+d0),16);
    t->sprite_cycle_index=d0?0:2;t->sprite_cycle_timer=5;
    fe_dg_cram(t);
}

/* ---- Sub CPU: planet object, planet data, graphics operation --------------------------- */
static void fe_dg_planet(scd_dagarden *t){
    switch(t->planet_routine){
    case 0:
        t->planet_x=0;t->planet_y=0x18;t->planet_z=0x40;t->planet_angle=0;
        t->angle_dir=1;t->scale_dir=1;t->angle_speed=0x20000;  /* move.w #2,angleSpeed: the high word */t->planet_routine=1;
        __attribute__((fallthrough));
    case 1:{
        if(t->tap&0x80){t->sub_flags|=0x40;t->planet_routine=0;return;}
        if(t->main_flags&0x10)t->planet_routine=2;
        if(t->hold&0x10){
            int accel=1;
            if(t->angle_speed){if(!(t->planet_flags&0x10)){t->angle_speed=0;t->angle_dir=(int16_t)-t->angle_dir;accel=0;}}
            else if(t->planet_flags&0x10)accel=0;
            if(accel)t->angle_speed+=t->angle_dir<0?-0x8000:0x8000;
            t->planet_flags|=0x10;
        }else t->planet_flags&=~0x10;
        if(t->hold&0x20){
            int zoom_in;
            if(t->scale_dir>0)zoom_in=!(t->planet_flags&0x20);
            else zoom_in=(t->planet_flags&0x20)!=0;
            if(!zoom_in){t->scale_dir=1;if(!(t->planet_z>0x700))t->planet_z=(int16_t)(t->planet_z+8);}
            else{t->scale_dir=-1;if(!(t->planet_z<-0x70))t->planet_z=(int16_t)(t->planet_z-8);}
            t->planet_flags|=0x20;
        }else t->planet_flags&=~0x20;
        int d5=t->planet_z>>6,d6=(int16_t)-d5;
        if(t->hold&4)t->planet_x=(int16_t)(t->planet_x+8+d5);
        if(t->hold&8)t->planet_x=(int16_t)(t->planet_x-8+d6);
        if(t->hold&1)t->planet_y=(int16_t)(t->planet_y+8+d5);
        if(t->hold&2)t->planet_y=(int16_t)(t->planet_y-8+d6);
        int16_t b=(int16_t)(t->planet_z+0x150);if(!(b>t->planet_x))t->planet_x=b;
        b=(int16_t)(-t->planet_z-0x150);if(!(b<t->planet_x))t->planet_x=b;
        b=(int16_t)(t->planet_z+0x150);if(!(b>t->planet_y))t->planet_y=b;
        b=(int16_t)(-t->planet_z-0x150);if(!(b<t->planet_y))t->planet_y=b;
        break;
    }
    case 2:
        if(t->tap&0x80){t->sub_flags|=0x40;t->planet_routine=0;return;}
        if(!(t->main_flags&0x10))t->planet_routine=1;
        break;
    }
    t->planet_angle=(int16_t)((t->planet_angle+fe_dg_hi(t->angle_speed))&0x1FF);
}
static void fe_dg_planet_data(scd_dagarden *t){
    unsigned zone=t->cmd_zone;if(zone==3)return;
    if(zone>3)zone=0;
    static const uint8_t fe_dg_zone_parts[3][3]={{DG_PART_STAMPS_PRESENT,DG_PART_STAMPS_ANIM,DG_PART_STAMP_MAP_PRESENT},
        {DG_PART_STAMPS_GOOD,DG_PART_STAMPS_ANIM,DG_PART_STAMP_MAP_GOOD},{DG_PART_STAMPS_BAD,DG_PART_STAMPS_ANIM_BAD,DG_PART_STAMP_MAP_BAD}};
    memcpy(t->stamps+0x200,fe_dg_part(t,fe_dg_zone_parts[zone][0]),t->pack->length[fe_dg_zone_parts[zone][0]]);
    memcpy(t->stamps+0x6E00,fe_dg_part(t,fe_dg_zone_parts[zone][1]),t->pack->length[fe_dg_zone_parts[zone][1]]);
    const uint8_t *map=fe_dg_part(t,fe_dg_zone_parts[zone][2]);
    for(unsigned r=0;r<7;r++)for(unsigned c=0;c<8;c++)t->stamp_map[r][c]=(uint16_t)fe_dg_be16(map+(r*8+c)*2);
    for(unsigned r=0;r<7;r++)for(unsigned c=0;c<8;c++)t->cell_key[r][c]=0xFFFF;
    t->kos_zone=(uint8_t)(zone+1);
}
/* Stamp pixel of a 32x32 stamp: H flip, then the two rotation bits (ASIC). */
static unsigned fe_dg_stamp_pixel(const scd_dagarden *t,unsigned raw,unsigned px,unsigned py){
    unsigned index=(raw&0x7FC)>>2;if(!index || (index+1)*512>sizeof(t->stamps))return 0;
    unsigned flags=raw>>13;
    if(flags&4)px^=31;
    if(flags&2){px^=31;py^=31;}
    if(flags&1){unsigned old=px;px=py^31;py=old;}
    unsigned pair=t->stamps[index*512+((px>>3)*4+(py>>3))*32+(py&7)*4+((px&7)>>1)];
    return (pair>>((px&1)?0:4))&15;
}
static void fe_dg_cells_refresh(scd_dagarden *t){
    for(unsigned r=0;r<7;r++)for(unsigned c=0;c<8;c++){
        unsigned raw=t->stamp_map[r][c];
        if(t->cell_key[r][c]==raw)continue;
        t->cell_key[r][c]=(uint16_t)raw;uint8_t *cell=t->cells[r][c];
        for(unsigned y=0;y<32;y++)for(unsigned x=0;x<32;x++)cell[y*32+x]=(uint8_t)fe_dg_stamp_pixel(t,raw,x,y);
    }
}
/* GenGfxTraceTbl. */
static void fe_dg_trace(scd_dagarden *t){
    const int x_origin=0x80,y_origin=0x70;
    int16_t scale=(int16_t)fe_dg_divs((uint32_t)((int32_t)(int16_t)(t->planet_z+0x80)<<8),0x80);
    int16_t c=(int16_t)fe_dg_sine((unsigned)(t->planet_angle+0x80)),s=(int16_t)fe_dg_sine((unsigned)t->planet_angle);
    int16_t xdelta=(int16_t)(fe_dg_muls(c,scale)>>5),ydelta=(int16_t)(fe_dg_muls(s,scale)>>5);
    int16_t xs=(int16_t)(t->planet_x-x_origin),ys=(int16_t)(t->planet_y-y_origin+88);
    #define ROT_X() ((fe_dg_muls(xs,c)-fe_dg_muls(ys,s)+((int32_t)x_origin<<8))>>5)
    #define ROT_Y() ((fe_dg_muls(xs,s)+fe_dg_muls(ys,c)+((int32_t)y_origin<<8))>>5)
    int16_t xrot=(int16_t)(ROT_X()>>3),yrot=(int16_t)(ROT_Y()>>3);
    int16_t xt=(int16_t)((fe_dg_muls(c,0x80)>>8)+xrot),yt=(int16_t)((fe_dg_muls(s,0x80)>>8)+yrot);
    xs=(int16_t)(t->planet_x-x_origin);ys=(int16_t)(t->planet_y-y_origin);
    const int32_t xadd=((int32_t)xt*256-fe_dg_muls(xt,scale))>>5,yadd=((int32_t)yt*256-fe_dg_muls(yt,scale))>>5;
    for(unsigned line=0;line<176;line++){
        uint16_t *out=t->trace+line*4;
        int32_t d0=ROT_X();d0=(fe_dg_muls(d0,scale)>>8)+xadd;out[0]=(uint16_t)d0;
        d0=ROT_Y();d0=(fe_dg_muls(d0,scale)>>8)+yadd;out[1]=(uint16_t)d0;
        out[2]=(uint16_t)xdelta;out[3]=(uint16_t)ydelta;
        ys++;
    }
    #undef ROT_X
    #undef ROT_Y
}
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC push_options
#pragma GCC optimize ("O3")
#endif
/* The ASIC graphics operation: 32x32 stamps, 4096x4096 map, not repeated (outside the
   map and in stamp 0 the pixel is 0), 256x176 image in cells of 22 rows per column. */
static void fe_dg_render_image(scd_dagarden *t){
    uint8_t line[256];
    for(unsigned row=0;row<176;row++){
        const uint16_t *tr=t->trace+row*4;
        uint32_t x=(uint32_t)tr[0]<<8,y=(uint32_t)tr[1]<<8;
        const uint32_t dx=(uint32_t)(int32_t)(int16_t)tr[2],dy=(uint32_t)(int32_t)(int16_t)tr[3];
        for(unsigned n=0;n<256;n++){
            x&=0xFFFFFF;y&=0xFFFFFF;
            unsigned px=0;
            if(!((x|y)&0xFF800000u)){
                unsigned c=x>>16,r=y>>16;
                if(c<8 && r<7)px=t->cells[r][c][((y>>11)&31)*32+((x>>11)&31)];
            }
            line[n]=(uint8_t)px;x+=dx;y+=dy;
        }
        uint8_t *cell=t->rendered+(row>>3)*32+(row&7)*4;const uint8_t *pixels=line;
        for(unsigned col=0;col<32;col++,cell+=22*32,pixels+=8){
            cell[0]=(uint8_t)(pixels[0]<<4|pixels[1]);cell[1]=(uint8_t)(pixels[2]<<4|pixels[3]);
            cell[2]=(uint8_t)(pixels[4]<<4|pixels[5]);cell[3]=(uint8_t)(pixels[6]<<4|pixels[7]);
        }
    }
}
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC pop_options
#endif
void scd_dagarden_render(scd_dagarden *t){fe_dg_render_image(t);}
static void fe_dg_run_gfx(scd_dagarden *t){
    fe_dg_trace(t);fe_dg_cells_refresh(t);
    if(t->render_start)t->render_start(t->render_context);else fe_dg_render_image(t);
}
/* Sub CPU main loop, one GACOMCMD2 command: planet object, music and planet data change,
   graphics operation. The flag handshakes after the operation run in the Main CPU steps. */
static void fe_dg_update_sub(scd_dagarden *t){
    fe_dg_planet(t);
    if(t->sub_flags&0x10){
        t->music=(uint8_t)t->cmd_track;t->music_changed=1;
        fe_dg_planet_data(t);
        t->sub_flags&=~0x10;
    }
    fe_dg_run_gfx(t);
}
/* After the operation: the music change request and the exit acknowledgement. */
static void fe_dg_get_image(scd_dagarden *t){
    if(t->render_wait)t->render_wait(t->render_context);
    memcpy(t->planet_image,t->rendered,SCD_DG_IMAGE);
}
static void fe_dg_animate_volcano(scd_dagarden *t){
    if(t->volcano_timer)return;
    if((int16_t)t->volcano_index>=0xC)t->volcano_index=0;
    unsigned d0=t->volcano_index*2u;
    t->volcano_timer=(uint16_t)fe_dg_tabw(t,DG_L_VolcanoAnimTimes+d0);t->volcano_index++;
    unsigned frame=DG_L_VolcanoAnimStamps+fe_dg_tabw(t,DG_L_VolcanoAnimStamps+d0);
    fe_dg_d1w(t,0xD8);
    for(unsigned r=0;r<2;r++)for(unsigned c=0;c<2;c++){
        unsigned v=fe_dg_tabw(t,frame+(r*2+c)*2);
        t->stamp_map[r][6+c]=(uint16_t)(v?v+0xD8:0);
    }
}

/* ---- Main CPU program ------------------------------------------------------------------- */
enum {STEP_INIT1=1,STEP_INIT2,STEP_INIT3,STEP_INIT4,STEP_FADE_IN,STEP_LOOP,STEP_LOOP2,STEP_LOOP3,
    STEP_REFRESH_WHITE,STEP_REFRESH_R0,STEP_REFRESH_R1,STEP_REFRESH_R2,STEP_REFRESH_R3,STEP_REFRESH_FADE,
    STEP_EXIT_FADE,STEP_DONE};
/* UpdateSubCPU, then (WaitWordRAMAccess) GetPlanetImage. */
static void fe_dg_render_cycle(scd_dagarden *t){fe_dg_update_sub(t);fe_dg_get_image(t);}
/* ExitFadeOut: FadeToBlack (22 VSyncs), LoadPalette, the exit handshake. */
static void fe_dg_exit(scd_dagarden *t){
    t->no_cycle=1;t->fade_start=0;t->fade_len=0x3F;t->count=22;t->step=STEP_EXIT_FADE;
}
/* Frames the retail Main CPU program misses before the next V-INT, as tools/dagarden_retail.py
   records them: the V-INT's planet DMA holds the 68000 for about a frame and a half, GetPlanetImage
   copies $5800 bytes; a Nemesis art load costs about one frame per 840 bytes (decoded plus
   compressed) past the slack left in that half (687 before V-INTs 0 and 2, 558 before 1 and 3),
   fitted to every art load in the six retail routes. */
static unsigned fe_dg_art_lag(const scd_dagarden *t,unsigned slack){
    return t->art_bytes>slack?(t->art_bytes-slack+839)/840:0;
}
/* Track title art loads in ChkTrkTitleSpawn, with interrupts masked, before GetPlanetImage:
   one frame per 500 bytes past 640 (fitted to the US and Japanese title loads). */
static unsigned fe_dg_title_lag(const scd_dagarden *t){
    return t->title_bytes>640?(t->title_bytes-640+499)/500:0;
}
static void fe_dg_main_steps(scd_dagarden *t);
static void fe_dg_main_program(scd_dagarden *t){
    unsigned from=t->step;
    fe_dg_main_steps(t);
    switch(t->step){
    case STEP_INIT2:case STEP_INIT4:case STEP_FADE_IN:case STEP_REFRESH_R1:case STEP_REFRESH_R3:case STEP_REFRESH_FADE:t->lag=1;break;
    case STEP_INIT3:case STEP_REFRESH_R2:t->lag=4;break;
    case STEP_REFRESH_R0:t->lag=19;break;
    case STEP_LOOP2:t->lag=(from==STEP_REFRESH_FADE?1:2)+fe_dg_art_lag(t,687)+fe_dg_title_lag(t);break;
    case STEP_LOOP3:t->lag=1+fe_dg_art_lag(t,558);break;
    case STEP_REFRESH_WHITE:case STEP_EXIT_FADE:t->lag=from==STEP_LOOP3 || from==STEP_INIT2 || from==STEP_INIT4?2:1;break;
    default:t->lag=0;break;
    }
}
static void fe_dg_main_steps(scd_dagarden *t){
    for(;;)switch(t->step){
    /* InitPlanetRender after its first VSync. */
    case STEP_INIT1:t->routine=1;t->step=STEP_INIT2;return;
    case STEP_INIT2:
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        fe_dg_render_cycle(t);fe_dg_animate_volcano(t);
        t->routine=2;t->step=STEP_INIT3;return;
    case STEP_INIT3:t->routine=3;t->step=STEP_INIT4;return;
    case STEP_INIT4:
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        /* Pal_DAGarden, then FadeFromBlack. */
        fe_dg_words(t,t->fade,DG_L_Pal_DAGarden,64);
        t->fade_start=0;t->fade_len=0x3F;t->d1=0;memset(t->palette,0,sizeof(t->palette));
        t->count=22;t->step=STEP_FADE_IN;return;
    case STEP_FADE_IN:
        fe_dg_fade_from_black(t);
        if(--t->count)return;
        t->no_cycle=0;t->buf_count=1;t->routine=0;t->step=STEP_LOOP;continue;
    /* MainLoop: one image per two V-INTs. */
    case STEP_LOOP:
        if(t->buf_count<0){t->buf_count=1;t->routine=0;}
        fe_dg_update_sub(t);fe_dg_track_selection(t);fe_dg_update_objects(t);
        t->step=STEP_LOOP2;return;
    case STEP_LOOP2:
        t->routine++;fe_dg_track_selection(t);fe_dg_update_objects(t);
        /* The Sub CPU's operation ends after this: it sees a music request made here. */
        if(t->main_flags&0x20)t->sub_flags|=0x20;
        t->step=STEP_LOOP3;return;
    case STEP_LOOP3:
        /* The Sub CPU checks the music request after its operation. */
        if(t->main_flags&0x20)t->sub_flags|=0x20;
        fe_dg_check_title_spawn(t);fe_dg_get_image(t);fe_dg_animate_volcano(t);
        if(t->sub_flags&0x20){
            /* RefreshScreen: FadeToWhite. */
            t->fade_start=0;t->fade_len=0x3F;t->count=22;t->step=STEP_REFRESH_WHITE;return;
        }
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->buf_count--;t->routine++;t->step=STEP_LOOP;continue;
    case STEP_REFRESH_WHITE:
        fe_dg_fade_to_white(t,t->palette);fe_dg_fade_to_white(t,t->fade);
        if(--t->count)return;
        memset(t->objects,0,sizeof(t->objects));
        fe_dg_load_palette(t);
        /* bclr #5,GAMAINFLAG: the Sub CPU marks the music change, then makes it on the next command. */
        t->main_flags&=~0x20;t->sub_flags&=~0x20;t->sub_flags|=0x10;
        do fe_dg_render_cycle(t);while(!(t->sub_flags&0x40) && (t->sub_flags&0x10));
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->routine=0;fe_dg_render_cycle(t);
        t->step=STEP_REFRESH_R0;return;
    case STEP_REFRESH_R0:
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->routine=1;t->step=STEP_REFRESH_R1;return;
    case STEP_REFRESH_R1:
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->routine=2;fe_dg_render_cycle(t);t->step=STEP_REFRESH_R2;return;
    case STEP_REFRESH_R2:
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->routine=3;t->step=STEP_REFRESH_R3;return;
    case STEP_REFRESH_R3:
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->sel_flags&=~1;t->spawn_flags=0;
        t->fade_start=0;t->fade_len=0x3F;
        for(unsigned i=0;i<64;i++)t->palette[i]=0xEEE;
        t->count=22;t->step=STEP_REFRESH_FADE;return;
    case STEP_REFRESH_FADE:
        fe_dg_fade_from_white(t);
        if(--t->count)return;
        t->buf_count=0;t->routine=-1;
        if(t->sub_flags&0x40){fe_dg_exit(t);return;}
        t->buf_count--;t->routine++;t->step=STEP_LOOP;continue;
    case STEP_EXIT_FADE:
        fe_dg_fade_to_black(t,t->palette);
        if(--t->count)return;
        fe_dg_load_palette(t);
        t->sub_flags&=~0x40;t->no_cycle=0;
        t->done=1;t->step=STEP_DONE;return;
    default:return;
    }
}

int scd_dagarden_start(scd_dagarden *t,const scd_dagarden_pack *pack){
    if(!pack || !pack->data)return -1;
    memset(t,0,offsetof(scd_dagarden,cells));t->pack=pack;
    /* Sub CPU: InitRAM, InitPlanetData (Present). */
    t->cmd_zone=0;fe_dg_planet_data(t);t->kos_zone=0;
    t->hold=0x80;t->tap=0;   /* move.w #$8000,ctrlData */
    t->music=22;t->music_changed=1;   /* SPCmd_LoadDAGarden: the D.A. Garden track */
    /* InitMD. */
    for(unsigned a=0xC000;a<0xD000;a+=2)fe_dg_vram_word(t,a,0xE6FF);
    for(unsigned a=0xE000;a<0xF000;a+=2)fe_dg_vram_word(t,a,0x06FE);
    t->vsram[0]=0;t->vsram[1]=0xFFE0;
    for(unsigned i=0;i<56;i++)t->tile_dirty[i]=0xFFFFFFFFu;
    t->plane_dirty[0]=t->plane_dirty[1]=0xFFFFFFFFu;
    /* DrawPlanetMap: buffer 1 tiles from $2000 on columns 0..31, buffer 2 from $22C0 on 32..63, rows 3..24. */
    for(unsigned buffer=0;buffer<2;buffer++)for(unsigned r=0;r<22;r++)for(unsigned c=0;c<32;c++)
        fe_dg_vram_word(t,0xC180+buffer*0x40+r*128+c*2,(buffer?0x22C0:0x2000)+c*22+r);
    /* DrawBackground. */
    const uint8_t *map=fe_dg_part(t,DG_PART_MAP_BACKGROUND);
    for(unsigned r=0;r<22;r++)for(unsigned c=0;c<32;c++)fe_dg_vram_word(t,0xE000+r*128+c*2,(fe_dg_be16(map+(r*32+c)*2)+0x580)&0xFFFF);
    fe_dg_vram_write(t,0xB000,fe_dg_part(t,DG_PART_ART_BACKGROUND),t->pack->length[DG_PART_ART_BACKGROUND]);
    {uint8_t fill[64];memset(fill,0xDD,32);memset(fill+32,0xFF,32);fe_dg_vram_write(t,0xDFC0,fill,64);}
    t->no_cycle=1;t->display=1;
    /* InitPlanetRender up to its first VSync. */
    fe_dg_render_cycle(t);fe_dg_animate_volcano(t);
    t->art_bytes=0;
    t->step=STEP_INIT1;t->lag=64;
    return 0;
}
int scd_dagarden_vint(scd_dagarden *t,unsigned pad){
    if(t->done)return 1;
    t->art_bytes=t->title_bytes=0;t->art_last=0;
    if(t->routine>=0 && t->routine<4){
        unsigned half=(unsigned)t->routine&1,buffer=(unsigned)t->routine>>1;
        if(!half)t->hscroll_a=buffer?0:0x100;
        fe_dg_vram_write(t,buffer*SCD_DG_IMAGE+half*(SCD_DG_IMAGE/2),t->planet_image+half*(SCD_DG_IMAGE/2),SCD_DG_IMAGE/2);
        if(!half){t->tap=(uint8_t)(pad&~t->hold);t->hold=(uint8_t)pad;}
    }
    fe_dg_vram_write(t,0xEC00,t->sprites,sizeof(t->sprites));
    fe_dg_vint_palette(t);
    if((int16_t)t->volcano_timer>0)t->volcano_timer--;
    if(t->timer)t->timer--;
    t->vint++;
    if(t->after_vint)t->after_vint(t);
    fe_dg_main_program(t);
    return t->done;
}
unsigned scd_dagarden_lag_frames(const scd_dagarden *t){return t->lag;}
unsigned scd_dagarden_track_music(unsigned track){
    /* Sub.asm PlayCDDAMusic: zone songs (present, good future, bad future of rounds 1, 3..8),
       then final, D.A. Garden, game over, results, boss, invincible, speed shoes, title,
       special stage, opening, ending as src/music_routes.h cues (src/frontend.c fe_st_da). */
    static const uint8_t fe_dg_eras[3]={0,2,3};
    static const uint8_t fe_dg_cues[11]={10,13,12,4,8,6,5,9,7,14,15};
    if(track<21)return (track/3)<<4|fe_dg_eras[track%3];
    if(track<SCD_DG_TRACKS)return 0x100|fe_dg_cues[track-21];
    return 0x100|13;
}
#ifdef SCD_ZONE_OVERLAY
/* Resident (src/saturn.x .zone_resident keeps *zone_ops* out of the overlay). */
const scd_dagarden_ops fe_dagarden_zone_ops={scd_dagarden_open,scd_dagarden_start,scd_dagarden_vint,scd_dagarden_render,scd_dagarden_lag_frames,scd_dagarden_track_music};
#endif
