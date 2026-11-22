/* _Objects/Title Card/Main.asm with Palmtree Panic/Title Card Data.asm.
 * The card object slides in vertically, waits its timer, slides out and then
 * unlocks controls; its eight pieces slide in and out horizontally. The
 * original then waits for PLC 2 (the camera section 1 art) to finish decoding
 * before it unlocks (ObjTitleCard_WaitPLC). The native program has no PLC
 * queue but keeps the wait's length: VInt_Level decodes 18 tiles once per
 * level update (never in a lag V-INT), so the wait is a fixed number of
 * updates per program, plc2_batches below (tools/title_card_plc.py derives
 * and checks it from the retail R<zone><act><era> programs). */
#include "title_card.h"
#include <string.h>
enum {ROUTINE_NONE,ROUTINE_INIT,ROUTINE_IN_VERT=2,ROUTINE_IN_HORIZ=4,ROUTINE_OUT_VERT=6,ROUTINE_OUT_HORIZ=8,ROUTINE_WAIT=10};
typedef struct {int16_t x,y,in,out;uint8_t routine,frame,timer,drawn;} card_object;
static card_object objects[9];
static int locked;
static unsigned wait_updates;
/* sum(ceil(tiles / 18)) over PLC 2's entries, [native zone][act][era A-D];
   zones R1, R3-R8. Act 3 has only the Futures. */
static const uint8_t plc2_batches[7][3][4]={
    {{18,21,22,22},{22,23,22,21},{0,0,9,9}},
    {{3,21,21,21},{20,21,22,21},{0,0,35,34}},
    {{22,18,18,18},{19,19,20,20},{0,0,19,19}},
    {{28,27,27,27},{28,26,27,27},{0,0,15,15}},
    {{25,29,26,26},{26,27,27,27},{0,0,19,19}},
    {{29,31,30,30},{29,33,30,30},{0,0,29,29}},
    {{26,27,25,25},{19,19,19,17},{0,0,21,21}}};
/* The program whose card starts (src/world.c). Without it (component tests)
   the wait keeps its one update. */
__attribute__((weak)) int scd_title_card_program(unsigned *zone,unsigned *act,unsigned *era){(void)zone;(void)act;(void)era;return 0;}
unsigned scd_title_card_plc_wait(unsigned zone,unsigned act,unsigned era){
    /* Retail level frame f is native sequence f - 1, and the native card
       inits on sequence 1 (retail frame 2), one update after the original's
       frame-1 init. Of the original's T WaitPLC updates after the queueing
       one, T - 1 remain to wait and the late start already covers one: the
       native card waits T - 2 more updates. Measured against all 40 PPZ, CC,
       TT and QQ retail windows (held unlock = native unlock + T - 2). */
    if(zone>=7 || act>=3 || era>=4)return 0;
    unsigned t=plc2_batches[zone][act][era];return t>2?t-2:0;
}
/* Each piece is a dynamic actor in the original (FindObjSlot from the card's
   init, DeleteObject once it has slid out). src/objects.c mirrors that slot
   use in Tidal Tempest; the weak default keeps other links unchanged. */
__attribute__((weak)) void scd_title_card_piece(unsigned piece,int alive){(void)piece;(void)alive;}
/* ObjTitleCard_Data: y, x, target x, frame<<8 | timer per piece. Palmtree Panic's by
   default; R6 and R8 move pieces 1-4 (src/main.c title_card_name_load()). */
static uint16_t data[8][4]={
    {0x130,0x228,0x168,0x15A},{0x100,0x238,0x178,0x25A},{0x100,0x240,0x180,0x25A},{0x100,0x248,0x188,0x25A},
    {0x120,0x230,0x170,0x35A},{0x140,0x248,0x188,0x45A},{0x100,0x1D0,0x110,0x75A},{0x100,0x1D0,0x110,0x85A}};
void scd_title_card_layout(const uint16_t rows[8][4]){memcpy(data,rows,sizeof(data));}
void scd_title_card_start(unsigned act){
    objects[0]=(card_object){.x=0x118,.y=0x30,.in=0xF0,.out=0x30,.routine=ROUTINE_INIT,.frame=0,.timer=0x5A};
    for(unsigned i=0;i<8;i++){
        unsigned frame=data[i][3]>>8;if(i==5)frame+=act;
        objects[i+1]=(card_object){.x=data[i][1],.y=data[i][0],.in=data[i][2],.out=data[i][1],.routine=ROUTINE_IN_HORIZ,.frame=frame,.timer=data[i][3]&255};
    }
    locked=1;wait_updates=0;
    for(unsigned i=1;i<9;i++)scd_title_card_piece(i,1);
}
static int slide(int16_t *position,int target,int step){
    if(*position==target)return 1;
    *position+=target>=*position?step:-step;return 0;
}
void scd_title_card_prepare(void){for(unsigned i=1;i<9;i++)scd_title_card_piece(i,1);}
int scd_title_card_step(void){
    for(unsigned i=0;i<9;i++){
        card_object *o=&objects[i];
        o->drawn=0;
        switch(o->routine){
        /* Init does not draw the parent. Allocated children execute later in
           the same original RunObjects sweep, hence they move this update. */
        case ROUTINE_INIT:o->routine=ROUTINE_IN_VERT;break;
        case ROUTINE_IN_VERT:if(slide(&o->y,o->in,8))o->routine+=4;o->drawn=1;break;
        case ROUTINE_IN_HORIZ:if(slide(&o->x,o->in,8))o->routine+=4;o->drawn=1;break;
        case ROUTINE_OUT_VERT:
            if(o->timer){o->timer--;o->drawn=1;break;}
            if(slide(&o->y,o->out,16)){
                /* Slid out: the original queues PLC 2 of the level loaded now
                   (not at card start), so the debug era reload during a card
                   (src/main.c X) waits for the reloaded program's art. */
                unsigned zone,program_act,era;
                wait_updates=scd_title_card_program(&zone,&program_act,&era)?scd_title_card_plc_wait(zone,program_act,era):0;
                o->routine+=4;
            }
            else o->drawn=1;
            break;
        case ROUTINE_OUT_HORIZ:
            if(o->timer){o->timer--;o->drawn=1;break;}
            if(slide(&o->x,o->out,16))o->routine=ROUTINE_NONE;
            else{
                o->drawn=1;
                /* The native card runs one update behind the original's: the
                   original deletes a piece the update after it reaches its out
                   position, retail TT1C/TT2C row 128 = native sequence 127. */
                if(o->x==o->out)scd_title_card_piece(i,0);
            }
            break;
        case ROUTINE_WAIT:if(wait_updates){wait_updates--;break;}o->routine=ROUTINE_NONE;locked=0;break;
        default:break;
        }
    }
    return locked;
}
int scd_title_card_locked(void){return locked;}
void scd_title_card_stop(void){memset(objects,0,sizeof(objects));locked=0;wait_updates=0;}
int scd_title_card_active(void){for(unsigned i=0;i<9;i++)if(objects[i].routine)return 1;return 0;}
unsigned scd_title_card_views(scd_title_card_view *views,unsigned capacity){
    unsigned n=0;
    /* Submit exactly the objects that called DrawObject this update. */
    for(unsigned i=0;i<9 && n<capacity;i++)if(objects[i].drawn)
        views[n++]=(scd_title_card_view){objects[i].x-128,objects[i].y-128,objects[i].frame};
    return n;
}
