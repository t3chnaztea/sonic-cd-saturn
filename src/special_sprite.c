/* Original Sonic animation selection and DrawObject frame/timer semantics. */
#include "special_sprite.h"
#include <string.h>
static unsigned word(const uint8_t *p){return ((unsigned)p[0]<<8)|p[1];}
static uint32_t longword(const uint8_t *p){return ((uint32_t)word(p)<<16)|word(p+2);}
int scd_special_art_open(scd_special_art *a,const void *buffer,size_t size){
    memset(a,0,sizeof(*a));const uint8_t *p=buffer;
    if(!p || size<40)return -1;
    unsigned effects=!memcmp(p,"SFX1",4),ufo=!memcmp(p,"UFX1",4);
    if(!effects && !ufo && memcmp(p,"SSA1",4))return -1;
    uint32_t v[9];for(unsigned i=0;i<9;i++)v[i]=longword(p+4+i*4);
    /* Counts come from the header; offsets below must chain exactly. */
    if(v[0]>size || v[0]<40 || !v[1] || v[1]>64 || !v[2] || v[2]>128 || !v[3] || v[3]>512 || v[4]!=40 || v[5]!=v[4]+v[1]*4 || v[6]!=v[5]+v[3]*4 || v[7]!=v[6]+v[2]*16 || v[8]!=((v[7]+((effects||ufo)?135:39))&~7u) || v[8]>v[0])return -1;
    for(unsigned i=0;i<v[1];i++){
        const uint8_t *row=p+v[4]+i*4;unsigned start=word(row+2);
        if(!row[0] || start>v[3] || row[0]>v[3]-start)return -1;
    }
    for(unsigned i=0;i<v[3];i++){const uint8_t *row=p+v[5]+i*4;if(word(row)>=v[2] || word(row+2)>3)return -1;}
    unsigned end=v[8];
    for(unsigned i=0;i<v[2];i++){
        const uint8_t *row=p+v[6]+i*16;unsigned offset=longword(row),width=word(row+8),height=word(row+10);
        if(!width || width>256 || (width&7) || !height || height>256 || longword(row+12)>63 || offset<end || (offset&7) || offset>v[0] || width*height/2>v[0]-offset)return -1;
        end=offset+width*height/2;
    }
    if(end!=v[0])return -1;
    *a=(scd_special_art){p,v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],v[8]};return 0;
}
void scd_special_sprite_set(scd_special_sprite *s,const scd_special_art *a,unsigned animation,int reset){
    if(animation>=a->animations)return;
    s->animation=animation;if(reset)s->frame=0;
    s->time=s->time_copy=a->data[a->animation_offset+animation*4+1];
}
void scd_special_sprite_tilt(scd_special_sprite *s,unsigned held){
    if(held&4){s->tilt--;if((int8_t)s->tilt<0)s->tilt=0;}
    else if(held&8){s->tilt++;if(s->tilt>=10)s->tilt=9;}
    else s->tilt=5; /* Original untilt loop reaches center in this update. */
}
void scd_special_sprite_choose(scd_special_sprite *s,scd_special_player *p,const scd_special_art *a,int inactive){
    static const uint8_t walk[20]={4,25,26,27,3,22,23,24,0,16,17,18,2,19,20,21,5,28,29,30};
    if(inactive)return;
    unsigned animation;int ground=0;
    if(p->flags&0x80)animation=6;
    else if(p->flags&0x40)animation=11;
    else if(!p->speed)animation=10;
    else if(p->speed>=0xb00)animation=1;
    else{
        unsigned offset=(s->tilt*2)&0x1c;
        /* Reachable tilt is 0..9, as in the source object. */
        if(offset>=20)offset=8;
        animation=walk[offset+(p->speed<0x300?3:p->speed<0x540?2:p->speed<0x780?1:0)];ground=1;
    }
    int reset=1;
    if(ground){reset=!(p->flags&0x10);p->flags|=0x10;}
    else if(animation!=1)p->flags&=~0x10;
    if(s->animation!=animation)scd_special_sprite_set(s,a,animation,reset);
}
int scd_special_sprite_advance(scd_special_sprite *s,const scd_special_player *p,const scd_special_art *a,scd_special_pose *pose){
    if(!a->data || s->animation>=a->animations)return -1;
    const uint8_t *animation=a->data+a->animation_offset+s->animation*4;
    if(!(p->flags&2)){
        s->time--;if((int8_t)s->time<0){s->time=animation[1];s->frame++;if(s->frame>=animation[0])s->frame=0;}
    }
    if(p->flags&4)return -1;
    if(s->frame>=animation[0])return -1;
    const uint8_t *entry=a->data+a->entry_offset+(word(animation+2)+s->frame)*4;
    unsigned index=word(entry),flip=word(entry+2);const uint8_t *row=a->data+a->pose_offset+index*16;
    int x=(int16_t)word(row+4),y=(int16_t)word(row+6);unsigned width=word(row+8),height=word(row+10);
    if(flip&1)x=-x-(int)width;if(flip&2)y=-y-(int)height;
    s->art=longword(row+12);*pose=(scd_special_pose){a->data+longword(row),x,y,width,height,flip,index};return 0;
}
