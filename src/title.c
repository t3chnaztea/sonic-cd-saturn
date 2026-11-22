/* Title screen program from Title Screen/Main.asm, Sub.asm and Objects (USA).
   Native C for the Saturn and the host test; the retail disc in the pinned
   Sega CD core is the QA oracle (tools/title_retail.py). */
#include "title.h"
#include <string.h>
#include "title_names.h"
#include "title-tables.inc"
#include "special-sine.inc"
static unsigned be16(const uint8_t *p){return ((unsigned)p[0]<<8)|p[1];}
static uint32_t be32(const uint8_t *p){return ((uint32_t)be16(p)<<16)|be16(p+2);}

int scd_title_open(scd_title_pack *pack,const void *data,size_t size){
    memset(pack,0,sizeof(*pack));const uint8_t *d=data;
    if(!d || size<8+8*SCD_TITLE_PARTS || memcmp(d,"TTL1",4) || be32(d+4)!=SCD_TITLE_PARTS)return -1;
    for(unsigned i=0;i<SCD_TITLE_PARTS;i++){
        uint32_t offset=be32(d+8+i*8),length=be32(d+12+i*8);
        if(offset>size || length>size-offset)return -1;
        pack->offset[i]=offset;pack->length[i]=length;
    }
    static const uint32_t fixed[][2]={{TITLE_PART_PALETTE_INIT,128},{TITLE_PART_PALETTE,128},{TITLE_PART_MAP_EMBLEM,988},{TITLE_PART_MAP_WATER,256},
        {TITLE_PART_MAP_MOUNTAINS,288},{TITLE_PART_STAMPS,16896},{TITLE_PART_STAMP_MAP,32768}};
    for(unsigned i=0;i<sizeof(fixed)/sizeof(fixed[0]);i++)if(pack->length[fixed[i][0]]!=fixed[i][1])return -1;
    pack->data=d;pack->size=size;return 0;
}
static const uint8_t *part(const scd_title *t,unsigned i){return t->pack->data+t->pack->offset[i];}

/* VRAM writes: tiles below $C000 and name table rows are marked for the display. */
static void vram_write(scd_title *t,unsigned address,const uint8_t *data,unsigned length){
    if(address>=0x10000)return;
    if(length>0x10000-address)length=0x10000-address;
    memcpy(t->vram+address,data,length);
    /* One pass per tile: every written tile, pattern tiles below $C000 and name table rows. */
    for(unsigned a=address&~31u;a<address+length;a+=32){
        unsigned tile=a>>5;t->sprite_dirty[tile>>5]|=1u<<(tile&31);
        if(a<0xC000)t->tile_dirty[tile>>5]|=1u<<(tile&31);
        else if(a>=0xC000 && a<0xD000)t->plane_dirty[0]|=1u<<((a-0xC000)>>7);
        else if(a>=0xE000 && a<0xF000)t->plane_dirty[1]|=1u<<((a-0xE000)>>7);
    }
}
static void vram_word(scd_title *t,unsigned address,unsigned value){
    const uint8_t w[2]={value>>8,value};vram_write(t,address,w,2);
}
static void load_art(scd_title *t,unsigned index,unsigned address){vram_write(t,address,part(t,index),t->pack->length[index]);}

/* Objects: kinds and resume points of the original bookmarks. */
enum {KIND_SONIC=1,KIND_ARM,KIND_BANNER,KIND_PLANET,KIND_MENU,KIND_ARROW,KIND_COPYRIGHT,KIND_TM};
enum {MAP_SONIC,MAP_BANNER,MAP_PLANET,MAP_MENU,MAP_ARROW,MAP_COPYRIGHT,MAP_TM};
static const unsigned map_parts[]={TITLE_PART_MAP_SONIC,TITLE_PART_MAP_BANNER,TITLE_PART_MAP_PLANET,TITLE_PART_MAP_MENU,TITLE_PART_MAP_ARROW,TITLE_PART_MAP_COPYRIGHT,TITLE_PART_MAP_TM};
static int spawn(scd_title *t,unsigned kind){
    for(unsigned i=0;i<SCD_TITLE_OBJECTS;i++)if(!t->objects[i].active){t->objects[i].active=0xff;t->objects[i].kind=kind;t->objects[i].resume=0;return (int)i;}
    return -1;
}
static void draw_object(scd_title *t,const scd_title_object *o){
    const uint8_t *m=part(t,map_parts[o->map]);unsigned length=t->pack->length[map_parts[o->map]];
    if((unsigned)o->frame*2+2>length)return;
    unsigned offset=be16(m+o->frame*2);if(offset>=length)return;
    const uint8_t *p=m+offset;unsigned count=*p++;
    if(offset+1+count*5>length)return;
    for(unsigned i=0;i<count;i++,p+=5){
        if(t->sprite_count>=64)break;
        uint8_t *s=t->sprites+t->sprite_slot;
        unsigned y=(uint16_t)((int8_t)p[0]+o->y+128),tile=(uint16_t)(((unsigned)p[2]<<8|p[3])+o->tile),x=((int8_t)p[4]+o->x+128)&0x1FF;
        /* Solid color tiles use the palette line below the object's. */
        if((tile&0x7FF)==0xBC20/0x20)tile=(uint16_t)(tile-0x2000);
        if(!x)x=1;
        s[0]=y>>8;s[1]=y;s[2]=p[1];s[3]=t->sprite_count++;s[4]=tile>>8;s[5]=tile;s[6]=x>>8;s[7]=x;
        t->sprite_slot+=8;
    }
}
static void clear_sprites(scd_title *t){memset(t->sprites,0,512);t->sprite_count=1;t->sprite_slot=0;}

static const uint8_t sound_test_code[6]={2,2,2,4,8,0x40};
static const uint8_t fe_title_stage_select_code[6]={1,2,2,4,8,0x10};
static const uint8_t fe_title_best_times_code[6]={8,8,1,1,2,0x20};
static void set_menu_option(scd_title *t,scd_title_object *o){
    static const unsigned text[]={TITLE_PART_ART_PRESS_START,TITLE_PART_ART_PRESS_START,TITLE_PART_ART_NEW_GAME,TITLE_PART_ART_CONTINUE,
        TITLE_PART_ART_TIME_ATTACK,TITLE_PART_ART_RAM_DATA,TITLE_PART_ART_DA_GARDEN,TITLE_PART_ART_VISUAL_MODE};
    o->frame=o->option;if(o->option<8){load_art(t,text[o->option],0xD800);t->text_loaded=1;}
}
enum {
    SONIC_F0=1,SONIC_F1,SONIC_F2,SONIC_F3,SONIC_F4,SONIC_F5,SONIC_DONE,
    ARM_DELAY=1,ARM_ANIMATE,ARM_DONE,
    PLANET_LOAD=1,PLANET_HOVER,
    MENU_PRESS=1,MENU_RIGHT_WAIT,MENU_RIGHT_OUT,MENU_RIGHT_SET,MENU_RIGHT_IN,MENU_RIGHT_IN_CHECK,
    MENU_LEFT_WAIT,MENU_LEFT_OUT,MENU_LEFT_SET,MENU_LEFT_IN,MENU_WAIT,MENU_DONE,
    STATIC_DONE=1
};
static void menu_move_right(scd_title_object *o){o->tile=0xC000|0xD800/0x20;o->allow=0;o->resume=MENU_RIGHT_WAIT;}
static void menu_move_left(scd_title_object *o){o->tile=0xC000|0xD800/0x20;o->allow=0;o->resume=MENU_LEFT_WAIT;}
static void menu_wait_selection(scd_title_object *o){o->allow=3;o->resume=MENU_WAIT;}
static void arrow(scd_title *t,scd_title_object *o){
    const scd_title_object *parent=t->objects+o->parent;
    unsigned neighbor=o->side?(uint8_t)(t->menu_sel+1):(uint8_t)(t->menu_sel-1);
    if(!parent->allow || neighbor>=8 || t->menu_options[neighbor]==0xFF){o->frame=0;o->delay=o->index=0;return;}
    o->frame=title_arrow_frames[o->side][o->index];
    unsigned sum=o->delay+0x10;o->delay=sum;
    if(sum>0xFF && ++o->index>=3)o->index=0;
}
static void run_object(scd_title *t,unsigned slot){
    scd_title_object *o=t->objects+slot;
    switch(o->kind){
    case KIND_SONIC:
        switch(o->resume){
        case 0:o->map=MAP_SONIC;o->tile=0xE000|0x6D00/0x20;o->flags=3;o->x=91;o->y=15;o->delay=2;o->resume=SONIC_F0;return;
        case SONIC_F0:if(--o->delay)return;o->frame++;o->delay=3;o->resume=SONIC_F1;return;
        case SONIC_F1:if(--o->delay)return;load_art(t,TITLE_PART_ART_MOUNTAINS,0x6000);o->frame++;o->delay=2;o->resume=SONIC_F2;return;
        case SONIC_F2:if(--o->delay)return;load_art(t,TITLE_PART_ART_WATER,0x6B00);o->frame++;o->delay=1;o->resume=SONIC_F3;return;
        case SONIC_F3:{
            if(--o->delay)return;
            t->mode|=0x80;
            int arm=spawn(t,KIND_ARM);if(arm>=0)t->objects[arm].parent=slot;
            spawn(t,KIND_BANNER);
            o->frame++;o->delay=0x14;o->resume=SONIC_F4;return;
        }
        case SONIC_F4:if(--o->delay)return;o->frame++;o->delay=4;o->resume=SONIC_F5;return;
        case SONIC_F5:if(--o->delay)return;o->frame=4;o->resume=SONIC_DONE;return;
        default:return;
        }
    case KIND_ARM:
        switch(o->resume){
        case 0:o->map=MAP_SONIC;o->tile=0xE000|0x6D00/0x20;o->flags=3;o->x=140;o->y=104;o->frame=9;o->resume=ARM_DELAY;return;
        case ARM_DELAY:{unsigned sum=o->delay+0x12;o->delay=sum;if(sum<=0xFF)return;}
            __attribute__((fallthrough)); /* .Animate */
        case ARM_ANIMATE:{
            unsigned next=o->index+1u;o->frame=title_arm_frames[o->index];
            if(next>=16){o->resume=ARM_DONE;return;}
            o->index=next;o->resume=ARM_ANIMATE;return;
        }
        default:return;
        }
    case KIND_BANNER:
        if(!o->resume){o->map=MAP_BANNER;o->tile=0xA000|0xF000/0x20;o->flags=3;o->x=127;o->y=127;o->resume=STATIC_DONE;}
        return;
    case KIND_PLANET:
        switch(o->resume){
        case 0:o->resume=PLANET_LOAD;return;
        case PLANET_LOAD:load_art(t,TITLE_PART_ART_PLANET,0x8040);o->map=MAP_PLANET;o->tile=0x6000|0x8040/0x20;o->flags=1;o->x=226;o->y=24;
            __attribute__((fallthrough)); /* .Hover */
        case PLANET_HOVER:{
            unsigned sum=o->delay+0x40;o->delay=sum;
            if(sum>0xFF){o->y+=title_planet_offsets[o->index];o->index=(o->index+1)&0x1F;}
            o->resume=PLANET_HOVER;return;
        }
        default:return;
        }
    case KIND_MENU:
        switch(o->resume){
        case 0:o->map=MAP_MENU;o->tile=0xA000|0xD800/0x20;o->flags=1;o->x=83;o->y=180;t->timer=0x3FC;
            __attribute__((fallthrough)); /* ObjMenu_PressStart */
        case MENU_PRESS:{
            unsigned sum=o->delay+0x10;o->delay=sum;
            if(sum>0xFF)o->frame^=1;
            if(t->tap&0x80){
                t->hold=t->tap=0;o->frame=1;t->timer=0x1E0;
                /* titleFlags as Mega Drive Init/Main.asm sets them without save data (%10010000):
                   new game and RAM data. Continue, time attack, D.A. Garden and visual mode need saved progress. */
                /* Menu/Main.asm:75: titleFlags. Bits 5 (Time Attack), 3 (D.A. Garden) and 2 (Visual
                   Mode) come from the records file. */
                const unsigned flags=0x90|(t->save_available?0x40:0)|(t->title_flags&0x2C);unsigned n=0;
                t->menu_options[n++]=0xFF;t->menu_options[n++]=2;t->menu_sel=1;
                if(flags&0x40){t->menu_sel=2;t->menu_options[n++]=3;}
                for(unsigned bit=5,option=4;option<8;bit--,option++)if(flags>>bit&1)t->menu_options[n++]=option;
                t->menu_options[n]=0xFF;
                int left=spawn(t,KIND_ARROW);if(left>=0){t->objects[left].parent=slot;}
                int right=spawn(t,KIND_ARROW);if(right>=0){t->objects[right].parent=slot;t->objects[right].side=1;}
                menu_move_right(o);return;
            }
            /* ObjMenu_SoundTestCheat (Menu/Main.asm:356-391): taps Down, Down, Down, Left,
               Right, A; any other tap restarts it. Exit 7 is the sound test. */
            if(t->tap==sound_test_code[t->sound_test_index]){
                if(++t->sound_test_index==sizeof(sound_test_code)){t->exit_flag=7;o->resume=MENU_DONE;return;}
            }else if(t->tap)t->sound_test_index=0;
            /* ObjMenu_StageSelCheat (Menu/Main.asm:396-436), independent of
               Sound Test and Best Times. Start above keeps original priority. */
            if(t->tap==fe_title_stage_select_code[t->stage_select_index]){
                if(++t->stage_select_index==sizeof(fe_title_stage_select_code)){t->exit_flag=8;o->resume=MENU_DONE;return;}
            }else if(t->tap)t->stage_select_index=0;
            /* ObjMenu_BestTimesCheat (Menu/Main.asm:436-473), while the title
               still shows press-start: Right, Right, Up, Up, Down, C. */
            if(t->tap==fe_title_best_times_code[t->best_times_index]){
                if(++t->best_times_index==sizeof(fe_title_best_times_code)){t->exit_flag=9;o->resume=MENU_DONE;return;}
            }else if(t->tap)t->best_times_index=0;
            if(!t->timer){t->exit_flag=0xFF;o->resume=MENU_DONE;return;}
            o->resume=MENU_PRESS;return;
        }
        case MENU_RIGHT_WAIT:{
            unsigned sum=o->delay+0x80;o->delay=sum;
            if(sum<=0xFF){menu_move_right(o);return;}
            o->x+=0x20;o->resume=MENU_RIGHT_OUT;return;
        }
        case MENU_RIGHT_OUT:
            if((uint16_t)o->x<0x100){o->x+=0x20;return;}
            o->resume=MENU_RIGHT_SET;return;
        case MENU_RIGHT_SET:
            o->option=t->menu_options[t->menu_sel<8?t->menu_sel:0];set_menu_option(t,o);
            o->x=-0x2D;o->resume=MENU_RIGHT_IN;return;
        case MENU_RIGHT_IN:o->x+=0x10;o->resume=MENU_RIGHT_IN_CHECK;return;
        case MENU_RIGHT_IN_CHECK:
            if(o->x<0 || (uint16_t)o->x<0x53){o->x+=0x10;return;}
            o->x=0x53;o->tile=0xA000|0xD800/0x20;menu_wait_selection(o);return;
        case MENU_LEFT_WAIT:{
            unsigned sum=o->delay+0x80;o->delay=sum;
            if(sum<=0xFF){menu_move_left(o);return;}
            o->x-=0x20;o->resume=MENU_LEFT_OUT;return;
        }
        case MENU_LEFT_OUT:
            if(o->x>=0 || (uint16_t)o->x>=(uint16_t)-0x35){o->x-=0x20;return;}
            o->resume=MENU_LEFT_SET;return;
        case MENU_LEFT_SET:
            o->option=t->menu_options[t->menu_sel<8?t->menu_sel:0];set_menu_option(t,o);
            o->x=0xD3;o->resume=MENU_LEFT_IN;return;
        case MENU_LEFT_IN:
            o->x-=0x10;
            if((uint16_t)o->x>=0x53)return;
            o->x=0x53;o->tile=0xA000|0xD800/0x20;menu_wait_selection(o);return;
        case MENU_WAIT:{
            if(t->hold&4){
                t->timer=0x1E0;uint8_t sel=t->menu_sel-1;
                if(t->menu_options[sel&7]==0xFF)return;
                t->menu_sel=sel;menu_move_right(o);return;
            }
            if(t->hold&8){
                t->timer=0x1E0;uint8_t sel=t->menu_sel+1;
                if(t->menu_options[sel&7]==0xFF)return;
                t->menu_sel=sel;menu_move_left(o);return;
            }
            if(t->tap&0xF0){
                unsigned option=t->menu_options[t->menu_sel&7];
                t->exit_flag=option?option-1:1;o->resume=MENU_DONE;return;
            }
            if(!t->timer){t->exit_flag=0xFF;o->resume=MENU_DONE;}
            return;
        }
        default:return;
        }
    case KIND_ARROW:
        if(!o->resume){o->map=MAP_ARROW;o->tile=0xA000|0xDC00/0x20;o->flags=1;o->y=181;o->x=o->side?168:72;o->resume=STATIC_DONE;}
        arrow(t,o);return;
    case KIND_COPYRIGHT:
        if(!o->resume){o->map=MAP_COPYRIGHT;o->tile=0xE000|0xDE00/0x20;o->flags=1;o->y=208;o->x=80;o->frame=1;o->resume=STATIC_DONE;}
        return;
    case KIND_TM:
        if(!o->resume){o->map=MAP_TM;o->tile=0xE000|0xDFC0/0x20;o->flags=1;o->x=194;o->y=131;o->resume=STATIC_DONE;}
        return;
    }
}
/* RunObjects: run every active slot, then draw from the last slot to the first. */
static void run_objects(scd_title *t){
    for(unsigned i=0;i<SCD_TITLE_OBJECTS;i++)if(t->objects[i].active)run_object(t,i);
    for(int i=SCD_TITLE_OBJECTS-1;i>=0;i--)if(t->objects[i].active && (t->objects[i].flags&1))draw_object(t,t->objects+i);
}

/* Sub.asm graphics operation: sines, trace table and the stamp renderer (32x32 stamps, 4096x4096 repeated map). */
static int sine(unsigned value){
    value&=0x1FF;unsigned i=value&127;if(value&128)i^=127;
    return value&256?-special_sines[i]:special_sines[i];
}
static int32_t muls(int32_t a,int32_t b){return (int32_t)(int16_t)a*(int16_t)b;}
/* DIVS: truncates toward zero; on overflow the destination is unchanged. */
static int16_t divs(int32_t value,int32_t divisor){
    int16_t d=(int16_t)divisor;if(!d)return (int16_t)value;
    if(value==INT32_MIN && d==-1)return (int16_t)value;
    int32_t q=value/d;return (q<-32768 || q>32767)?(int16_t)value:(int16_t)q;
}
static void trace_ray(scd_title *t){
    const int fov=0x80,center=-0x40;
    int ps=sine(t->pitch),pc=sine(t->pitch+0x80),ys=sine(t->yaw),yc=sine(t->yaw+0x80);
    uint16_t cx=(uint16_t)(t->cam_x<<3),cy=(uint16_t)(t->cam_y<<3);
    int16_t pcys=(int16_t)(muls(pc,ys)>>5),pcyc=(int16_t)(muls(pc,yc)>>5);
    int32_t psysfov=muls(muls(fov,ps),ys)>>5,psycfov=muls(muls(fov,ps),yc)>>5,pcfov=muls(fov,pc);
    int32_t a1=(int32_t)((uint32_t)muls(-128,yc)<<3),a2=(int32_t)((uint32_t)muls(-128,ys)<<3),a3=(int32_t)((uint32_t)muls(127,yc)<<3),a4=(int32_t)((uint32_t)muls(127,ys)<<3);
    int16_t centerx=(int16_t)(muls(fov+center,muls(ps,ys)>>5)>>8),centery=(int16_t)(muls(fov+center,muls(ps,yc)>>5)>>8);
    int line=-3;
    for(unsigned row=0;row<96;row++,line--){
        int32_t z=(muls(line,ps)+pcfov)>>5;if(!z)z=1;
        uint16_t *out=t->trace+row*4;
        out[0]=(uint16_t)(divs(muls((a3-muls(pcys,line)+psysfov)>>8,t->cam_z),z)+cx-centerx);
        out[1]=(uint16_t)(divs(muls((a4+muls(pcyc,line)-psycfov)>>8,t->cam_z),z)+cy+centery);
        out[2]=(uint16_t)(divs(muls((a1-muls(pcys,line)+psysfov)>>8,t->cam_z),z)+cx-centerx-out[0]);
        out[3]=(uint16_t)(divs(muls((a2+muls(pcyc,line)-psycfov)>>8,t->cam_z),z)+cy+centery-out[1]);
    }
}
static unsigned stamp_pixel(const scd_title *t,unsigned raw,unsigned px,unsigned py){
    unsigned index=(raw&0x7FC)>>2;if(!index)return 0;
    if((index+1)*512>t->pack->length[TITLE_PART_STAMPS])return 0;
    unsigned flags=raw>>13;
    if(flags&4)px^=31;
    if(flags&2){px^=31;py^=31;}
    if(flags&1){unsigned old=px;px=py^31;py=old;}
    unsigned offset=index*512+((px>>3)*4+(py>>3))*32+(py&7)*4+((px&7)>>1);
    unsigned pair=part(t,TITLE_PART_STAMPS)[offset];return (pair>>((px&1)?0:4))&15;
}
static void stamp_cache_fill(scd_title *t){
    const uint8_t *map=part(t,TITLE_PART_STAMP_MAP);uint16_t keys[SCD_TITLE_STAMP_SLOTS];t->stamp_slots=0;
    for(unsigned cell=0;cell<16384;cell++){
        unsigned raw=be16(map+cell*2),key=raw&0xE7FC;
        if(!(raw&0x7FC)){t->cells[cell]=0;continue;}
        unsigned slot=0;while(slot<t->stamp_slots && keys[slot]!=key)slot++;
        if(slot==t->stamp_slots){
            if(slot==SCD_TITLE_STAMP_SLOTS){t->cells[cell]=255;continue;}
            keys[slot]=key;t->stamp_slots++;
            for(unsigned y=0;y<32;y++)for(unsigned x=0;x<32;x++)t->stamp_cache[slot*1024+y*32+x]=stamp_pixel(t,raw,x,y);
        }
        t->cells[cell]=slot+1;
    }
}
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC push_options
#pragma GCC optimize ("O3")
#endif
/* Runs of pixels in one stamp column for a line's X start and step (the ASIC masks the position to the map before each pixel). */
static void sample_line(scd_title *t,unsigned row,uint16_t start,uint16_t step){
    uint32_t x=(uint32_t)start<<8;int32_t dx=(int16_t)step;unsigned count=0;
    for(unsigned n=0;n<256;n++){
        x&=0x7FFFFF;unsigned column=x>>16;
        if(!count || t->runs[row][count-1][0]!=column || t->runs[row][count-1][1]==255){t->runs[row][count][0]=column;t->runs[row][count][1]=0;count++;}
        t->runs[row][count-1][1]++;t->offsets[row][n]=(x>>11)&31;
        x+=dx;
    }
    t->sample_x[row]=start;t->sample_dx[row]=step;t->run_count[row]=count;
}
static void render(scd_title *t){
    static const uint8_t blank[32];
    const uint8_t *map=part(t,TITLE_PART_STAMP_MAP);uint8_t line[256];
    for(unsigned row=0;row<96;row++){
        const uint16_t *tr=t->trace+row*4;
        if(!tr[3]){
            if(t->sample_x[row]!=tr[0] || t->sample_dx[row]!=tr[2] || !t->run_count[row])sample_line(t,row,tr[0],tr[2]);
            uint32_t y=((uint32_t)tr[1]<<8)&0x7FFFFF;unsigned base=(y>>16)<<7,py=(y>>11)&31;
            const uint8_t *offsets=t->offsets[row];unsigned n=0;
            for(unsigned i=0;i<t->run_count[row];i++){
                unsigned column=t->runs[row][i][0],end=n+t->runs[row][i][1],code=t->cells[base+column];
                if(code==255)for(;n<end;n++)line[n]=stamp_pixel(t,be16(map+(base+column)*2),offsets[n],py);
                else{
                    const uint8_t *r=code?t->stamp_cache+(code-1)*1024+py*32:blank;
                    for(;n<end;n++)line[n]=r[offsets[n]];
                }
            }
        }else{
            uint32_t x=(uint32_t)tr[0]<<8,y=(uint32_t)tr[1]<<8;int32_t dx=(int16_t)tr[2],dy=(int16_t)tr[3];
            for(unsigned n=0;n<256;n++){
                x&=0x7FFFFF;y&=0x7FFFFF;
                line[n]=stamp_pixel(t,be16(map+(((y>>16)<<7)|(x>>16))*2),(x>>11)&31,(y>>11)&31);
                x+=dx;y+=dy;
            }
        }
        /* Image buffer cells are 8x8 pixels in columns of 12 (GAIMGVCELL), as DrawCloudsMap expects:
           this line fills the same row of cell row row/8 in each of the 32 cell columns. */
        uint8_t *cell=t->rendered+(row>>3)*32+(row&7)*4;const uint8_t *pixels=line;
        for(unsigned c=0;c<32;c++,cell+=12*32,pixels+=8){
            cell[0]=(uint8_t)(pixels[0]<<4|pixels[1]);cell[1]=(uint8_t)(pixels[2]<<4|pixels[3]);
            cell[2]=(uint8_t)(pixels[4]<<4|pixels[5]);cell[3]=(uint8_t)(pixels[6]<<4|pixels[7]);
        }
    }
}
#if defined(__GNUC__) && !defined(__clang__)
#pragma GCC pop_options
#endif
void scd_title_render(scd_title *t){render(t);}
/* RenderClouds: GetGfxSines, RunGfxOperation (from the current camera), ControlClouds. */
static void render_clouds(scd_title *t){
    trace_ray(t);
    if(t->render_start)t->render_start(t->render_context);else render(t);
    t->cam_y+=2;
}
/* GetCloudsImage. */
static void get_clouds_image(scd_title *t){
    if(t->render_wait)t->render_wait(t->render_context);
    memcpy(t->clouds_image,t->rendered,SCD_TITLE_IMAGE);
}

static void palette_cycle(scd_title *t){
    unsigned sum=t->cycle_delay+0x40;t->cycle_delay=sum;
    if(sum<=0xFF)return;
    unsigned frame=t->cycle_frame+1u;if(frame>=3)frame=0;
    t->cycle_frame=frame;memcpy(t->palette+5,title_water_cycle+frame*4,4*sizeof(uint16_t));
}
/* ScrollBgBuf1/2: the cloud buffer on lines 0..87 and the water lines 160..223. */
static void scroll_background(scd_title *t,unsigned buffer){
    for(unsigned line=0;line<88;line++){t->hscroll_buffer[line*2]=0;t->hscroll_buffer[line*2+1]=buffer==2?0x100:0;}
    uint32_t speed=0x4000;
    for(unsigned i=0;i<64;i++){t->water[i]+=speed;speed+=0x1000;}
    for(unsigned i=0;i<64;i++){t->hscroll_buffer[(160+i)*2]=0;t->hscroll_buffer[(160+i)*2+1]=(uint16_t)(t->water[i]>>16);}
}
static void fade_from_black_frame(scd_title *t){
    for(unsigned i=0;i<t->fade_colors;i++){
        unsigned target=t->fade[t->fade_start+i],c=t->palette[t->fade_start+i];
        if(c==target)continue;
        if((uint16_t)(c+0x200)<=target)c+=0x200;else if((uint16_t)(c+0x20)<=target)c+=0x20;else c+=2;
        t->palette[t->fade_start+i]=(uint16_t)c;
    }
}
static void fade_from_white_frame(scd_title *t){
    for(unsigned i=0;i<t->fade_colors;i++){
        unsigned target=t->fade[t->fade_start+i],c=t->palette[t->fade_start+i];
        if(c==target)continue;
        if(c>=0x200 && c-0x200>=target)c-=0x200;else if(c>=0x20 && c-0x20>=target)c-=0x20;else c-=2;
        t->palette[t->fade_start+i]=(uint16_t)c;
    }
}
static void fade_to_black_frame(scd_title *t){
    for(unsigned i=0;i<t->fade_colors;i++){
        uint16_t *c=t->palette+t->fade_start+i;
        if(!*c)continue;
        if(*c&0xE)*c-=2;else if(*c&0xE0)*c-=0x20;else if(*c&0xE00)*c-=0x200;
    }
}
static void palette_word_copy(uint16_t *out,const uint8_t *in,unsigned count){for(unsigned i=0;i<count;i++)out[i]=(uint16_t)be16(in+i*2);}

enum {STEP_DISPLAY=1,STEP_DELAY_START,STEP_DELAY,STEP_FIRST_OBJECTS,STEP_SONIC_FADE,STEP_WAIT_TURN,STEP_FLASH,
    STEP_LOOP1,STEP_LOOP2,STEP_LOOP3,STEP_LOOP4,STEP_LOOP5,STEP_EXIT_FADE,STEP_EXIT_LOOP,STEP_DONE};
/* Main CPU code from the current step to the next VSync. */
static void main_program(scd_title *t){
    for(;;)switch(t->step){
    case STEP_DISPLAY:t->enable_display=1;t->routine=4;t->step=STEP_DELAY_START;return;
    case STEP_DELAY_START:t->count=48;t->step=STEP_DELAY;return;
    case STEP_DELAY:if(--t->count)return;
        run_objects(t);t->routine=5;t->step=STEP_FIRST_OBJECTS;return;
    case STEP_FIRST_OBJECTS:
        /* FadeFromBlack over Sonic's palette line 3. */
        palette_word_copy(t->fade+48,part(t,TITLE_PART_PALETTE)+96,16);t->fade_start=48;t->fade_colors=16;
        for(unsigned i=48;i<64;i++)t->palette[i]=0;
        t->count=22;t->step=STEP_SONIC_FADE;return;
    case STEP_SONIC_FADE:
        fade_from_black_frame(t);
        if(--t->count)return;
        t->step=STEP_WAIT_TURN;continue;
    case STEP_WAIT_TURN:
        t->mode=1;clear_sprites(t);run_objects(t);
        if(!(t->mode&0x80)){t->routine=5;return;}
        t->mode&=0x7F;load_art(t,TITLE_PART_ART_EMBLEM,0x6D80);
        /* FadeFromWhite2 over lines 0..2; line 2 color 14 starts black. */
        palette_word_copy(t->fade,part(t,TITLE_PART_PALETTE),64);t->fade_start=0;t->fade_colors=48;
        for(unsigned i=0;i<48;i++)t->palette[i]=0xEEE;
        t->palette[0x2E]=0;
        t->count=22;t->step=STEP_FLASH;return;
    case STEP_FLASH:
        fade_from_white_frame(t);
        if(--t->count)return;
        spawn(t,KIND_PLANET);spawn(t,KIND_MENU);spawn(t,KIND_COPYRIGHT);spawn(t,KIND_TM);
        t->step=STEP_LOOP1;continue;
    case STEP_LOOP1:
        t->mode=2;render_clouds(t);clear_sprites(t);run_objects(t);palette_cycle(t);scroll_background(t,2);
        t->routine=0;t->step=STEP_LOOP2;return;
    case STEP_LOOP2:clear_sprites(t);run_objects(t);t->routine=1;t->step=STEP_LOOP3;return;
    case STEP_LOOP3:
        get_clouds_image(t);
        if(t->exit_flag){t->step=STEP_EXIT_FADE;continue;}
        clear_sprites(t);run_objects(t);palette_cycle(t);render_clouds(t);scroll_background(t,1);
        t->routine=2;t->step=STEP_LOOP4;return;
    case STEP_LOOP4:clear_sprites(t);run_objects(t);t->routine=3;t->step=STEP_LOOP5;return;
    case STEP_LOOP5:
        get_clouds_image(t);
        if(t->exit_flag){t->step=STEP_EXIT_FADE;continue;}
        t->step=STEP_LOOP1;continue;
    case STEP_EXIT_FADE:
        t->routine=5;t->fade_start=0;t->fade_colors=64;t->count=22;t->step=STEP_EXIT_LOOP;return;
    case STEP_EXIT_LOOP:
        fade_to_black_frame(t);
        if(--t->count)return;
        t->exit_code=(t->exit_flag&0x80)?0:t->exit_flag;t->done=1;t->step=STEP_DONE;return;
    default:return;
    }
}
int scd_title_start(scd_title *t,const scd_title_pack *pack){
    if(!pack || !pack->data)return -1;
    memset(t,0,offsetof(scd_title,stamp_cache));t->pack=pack;
    /* InitMD: VRAM, VSRAM and the initialization palette. */
    palette_word_copy(t->palette,part(t,TITLE_PART_PALETTE_INIT),64);
    for(unsigned i=0;i<2;i++)t->plane_dirty[i]=0xFFFFFFFFu;
    for(unsigned i=0;i<48;i++)t->tile_dirty[i]=0xFFFFFFFFu;
    clear_sprites(t);
    /* DrawTilemaps: emblem on plane A, water and mountains on plane B. */
    const uint8_t *emblem=part(t,TITLE_PART_MAP_EMBLEM),*water=part(t,TITLE_PART_MAP_WATER),*mountains=part(t,TITLE_PART_MAP_MOUNTAINS);
    for(unsigned r=0;r<19;r++)for(unsigned c=0;c<26;c++){unsigned w=be16(emblem+(r*26+c)*2);vram_word(t,0xC206+r*128+c*2,w?(uint16_t)(w+(0xC000|0x6D80/0x20)):0);}
    for(unsigned side=0;side<2;side++)for(unsigned r=0;r<8;r++)for(unsigned c=0;c<32;c++){unsigned b=water[r*32+c];vram_word(t,0xEA00+side*0x40+r*128+c*2,b?0x300|b:0);}
    for(unsigned r=0;r<9;r++)for(unsigned c=0;c<32;c++){unsigned b=mountains[r*32+c];vram_word(t,0xE580+r*128+c*2,b?0x300|b:0);}
    load_art(t,TITLE_PART_ART_PRESS_START,0xD800);load_art(t,TITLE_PART_ART_ARROW,0xDC00);
    load_art(t,TITLE_PART_ART_COPYRIGHT,0xDE00);load_art(t,TITLE_PART_ART_TM,0xDFC0);
    load_art(t,TITLE_PART_ART_BANNER,0xF000);load_art(t,TITLE_PART_ART_SONIC,0x6D00);
    spawn(t,KIND_SONIC);
    load_art(t,TITLE_PART_ART_SOLID,0xBC20);
    /* DrawCloudsMap: buffer 1 on columns 0..31, buffer 2 on columns 32..63, 12 rows. */
    for(unsigned buffer=0;buffer<2;buffer++)for(unsigned r=0;r<12;r++)for(unsigned c=0;c<32;c++)
        vram_word(t,0xE000+buffer*0x40+r*128+c*2,(buffer?0x8181:0x8001)+c*12+r);
    /* Sub CPU: InitGfxParams and the cloud stamps. */
    t->cam_x=0x480;t->cam_y=0x480;t->cam_z=0x140;t->pitch=0x44;t->yaw=0x100;
    stamp_cache_fill(t);
    t->step=STEP_DISPLAY;
    return 0;
}
int scd_title_vint(scd_title *t,unsigned pad){
    if(t->done)return 1;
    if(t->enable_display){t->display=1;t->enable_display=0;}
    memcpy(t->cram,t->palette,sizeof(t->cram));memcpy(t->hscroll,t->hscroll_buffer,sizeof(t->hscroll));
    if(t->routine!=4)memcpy(t->sat,t->sprites,sizeof(t->sat));
    if(t->routine<4){
        /* COPYIMG: half of the last cloud image into buffer 1 (routines 0, 1) or 2 (2, 3). */
        unsigned half=t->routine&1,buffer=t->routine>>1;
        vram_write(t,0x20+buffer*SCD_TITLE_IMAGE+half*(SCD_TITLE_IMAGE/2),t->clouds_image+half*(SCD_TITLE_IMAGE/2),SCD_TITLE_IMAGE/2);
    }
    if(t->routine!=4){t->tap=(uint8_t)(pad&~t->hold);t->hold=(uint8_t)pad;}
    if(t->timer)t->timer--;
    t->vint++;t->text_loaded=0;
    main_program(t);
    return t->done;
}
unsigned scd_title_lag_frames(const scd_title *t){
    /* Startup and art decompression before the V-INTs that follow, the first cloud render,
       then one frame before each V-INT that shows a new image half pair (routines 0 and 2),
       before the exit fade and after a menu text load (tools/title_retail.py records). */
    switch(t->vint){case 0:return 67;case 77:return 5;case 79:return 1;case 80:return 10;case 103:return 9;}
    if(t->vint>103 && t->mode==2 && (t->routine==0 || t->routine==2 || (t->routine==5 && t->count==22)))return 1+t->text_loaded;
    return t->text_loaded;
}
#ifdef SCD_ZONE_OVERLAY
/* Resident (src/saturn.x .zone_resident keeps *zone_ops* out of the overlay). */
const scd_title_ops fe_title_zone_ops={scd_title_open,scd_title_start,scd_title_vint,scd_title_render,scd_title_lag_frames};
#endif
