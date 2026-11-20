/* Special Stage Main CPU routines from Main.asm. Section offsets refer to
   tools/special_main_assets.py; values and tables are original. */
#include "special_main.h"
#include <string.h>
static uint16_t word(const uint8_t *p){return (uint16_t)((p[0]<<8)|p[1]);}
static uint32_t longword(const uint8_t *p){return ((uint32_t)word(p)<<16)|word(p+2);}
static uint16_t rol(uint16_t v,unsigned n){return (uint16_t)(((uint32_t)v<<n)|((uint32_t)v>>(16-n)));}
static uint16_t ror(uint16_t v,unsigned n){return (uint16_t)(((uint32_t)v>>n)|((uint32_t)v<<(16-n)));}
int scd_special_main_open(scd_special_main_pack *k,const void *buffer,size_t size){
    static const uint32_t minimum[11]={848,2,0x4f*8,0,48,40,1008,10,398,572,2};
    enum {HEADER=12+11*8};
    memset(k,0,sizeof(*k));const uint8_t *p=buffer;
    if(!p || size<HEADER || memcmp(p,"SSM2",4) || longword(p+8)!=11)return -1;
    uint32_t total=longword(p+4);if(total>size || total<HEADER)return -1;
    for(unsigned i=0;i<11;i++){
        uint32_t o=longword(p+12+i*8),n=longword(p+16+i*8);
        if(o<HEADER || o>total || n>total-o || n<minimum[i])return -1;
        k->offset[i]=o;k->length[i]=n;
    }
    if(k->length[0]!=848 || k->length[4]!=48 || k->length[5]!=40 || k->length[6]!=1008 || k->length[7]!=10 || k->length[3]&1 || k->length[8]!=398 || k->length[9]!=572)return -1;
    k->stage=word(p+k->offset[10]);if(k->stage<1 || k->stage>8)return -1;
    for(unsigned id=0;id<0x4f;id++){
        const uint8_t *e=p+k->offset[2]+id*8;unsigned address=word(e),cells=e[2]*e[3];uint32_t words=longword(e+4);
        if(words==0xffffffffu)continue;
        unsigned base=address>=0xe000?0xe000:0xc000;
        if(address&1 || address<0xc000 || (address>=0xd000 && address<0xe000) || address>=0xf000 || (address-base)/2+cells>2048 || words>k->length[3]/2 || cells>k->length[3]/2-words)return -1;
    }
    const uint8_t *t=p+k->offset[1];unsigned count=word(t),at=2;
    for(unsigned i=0;i<count;i++){
        if(at+6>k->length[1])return -1;
        unsigned first=word(t+at),tiles=word(t+at+2),group=word(t+at+4);
        if(first+tiles>2048 || group>1 || tiles*32u>k->length[1]-at-6)return -1;
        at+=6+tiles*32;
    }
    if(at!=k->length[1])return -1;
    k->data=p;k->size=total;return 0;
}
static const uint8_t *section(const scd_special_main_pack *k,unsigned i){return k->data+k->offset[i];}
static void draw_tilemap(scd_special_main *m,const scd_special_main_pack *k,unsigned id){
    if(!id || id>0x4f)return;
    const uint8_t *e=section(k,2)+(id-1)*8;unsigned address=word(e),width=e[2],height=e[3];uint32_t offset=longword(e+4);
    if(offset==0xffffffffu)return;
    uint16_t *plane=address>=0xe000?m->plane_b:m->plane_a;unsigned cell=(address-(address>=0xe000?0xe000:0xc000))/2;
    const uint8_t *w=section(k,3)+offset*2;
    for(unsigned r=0;r<height;r++)for(unsigned c=0;c<width;c++)plane[cell+r*64+c]=word(w+(r*width+c)*2);
    for(unsigned r=cell/64;r<cell/64+height && r<32;r++)m->dirty[address>=0xe000]|=1u<<r;
}
static void draw_tilemaps(scd_special_main *m,const scd_special_main_pack *k,uint32_t ids){
    for(unsigned i=0;i<4;i++){draw_tilemap(m,k,ids&255);ids>>=8;}
}
static void prep_fade_from_white(scd_special_main *m){
    memcpy(m->fade,m->palette,sizeof(m->fade));
    for(unsigned i=0;i<64;i++)m->palette[i]=0xeee;
}
int scd_special_main_stage(scd_special_main *m,const scd_special_main_pack *k,unsigned stage,int time_attack){
    /* LoadSS1Data..LoadSS8Data DrawTilemaps arguments. */
    static const uint32_t maps[8][2]={{0x17161514u,0x43},{0x4030201u,5},{0x9080706u,0x280b0a},{0xf0e0d0cu,0x1110},
        {0x1b1a1918u,0x1c},{0x201f1e1du,0x4d},{0x24232221u,0x272625},{0x4f4e,0}};
    if(!k->data || stage<1 || stage>8 || stage!=k->stage)return -1;
    uint32_t score=m->score,next=m->next_life;uint8_t lives=m->lives;
    memset(m,0,sizeof(*m));m->score=score;m->next_life=next;m->lives=lives;m->stage=stage;m->time_attack=!!time_attack;
    for(unsigned i=0;i<64;i++)m->palette[i]=word(section(k,0)+i*2);
    /* DrawStageMap: column-major image tiles; the rightmost column has priority. */
    for(unsigned buffer=0;buffer<2;buffer++)for(unsigned r=0;r<12;r++)for(unsigned c=0;c<32;c++)
        m->plane_a[(16+r)*64+buffer*32+c]=(buffer?0x2181:0x2001)+r+c*12+(c==31?0x8000:0);
    draw_tilemaps(m,k,maps[stage-1][0]);draw_tilemaps(m,k,maps[stage-1][1]);
    draw_tilemaps(m,k,0x12);if(m->time_attack)draw_tilemaps(m,k,0x13);
    /* InitBGLineHScroll: stage 5 starts plane B at -$80; stages 1, 6 and 8 at 0. */
    if(stage==5)for(unsigned line=0;line<128;line++)m->hscroll[line*2+1]=0xff80;
    for(unsigned i=0;i<32;i++)m->palette[16+i]=word(section(k,0)+256+(stage-1)*64+i*2);
    m->shift=0x100;m->stone_delay=20;m->dirty[0]=m->dirty[1]=0xffffffffu;
    prep_fade_from_white(m);
    return 0;
}
static void apply_ss1(scd_special_main *m,unsigned line,unsigned count,uint32_t shift,uint32_t step,uint16_t a){
    for(unsigned i=0;i<count;i++,line++){
        m->hscroll[line*2]=a;m->hscroll_frac[line*2]=0;
        uint32_t b=((uint32_t)m->hscroll[line*2+1]<<16)|m->hscroll_frac[line*2+1];
        b=m->scroll_mode?b-shift:b+shift;
        m->hscroll[line*2+1]=(uint16_t)(b>>16);m->hscroll_frac[line*2+1]=(uint16_t)b;
        shift-=step;
    }
}
/* GetScrollSpeed: left keeps the base speed, right negates it, neither is 0. */
static int32_t scroll_speed(const scd_special_main *m,int32_t base){
    return m->scroll_flags&4?base:m->scroll_flags&8?-base:0;
}
/* ApplyBGScroll_SS5: mode 2 resets plane B to -$80, 0 leaves the lines alone. */
static void apply_ss5(scd_special_main *m,const scd_special_main_pack *k,unsigned line,unsigned count,unsigned speed,uint16_t a){
    const uint8_t *speeds=section(k,9)+speed*4;
    if(!m->scroll_mode)return;
    for(unsigned i=0;i<count;i++,line++){
        m->hscroll[line*2]=a;m->hscroll_frac[line*2]=a;
        if(m->scroll_mode==2){m->hscroll[line*2+1]=0xff80;m->hscroll_frac[line*2+1]=0;continue;}
        uint32_t b=((uint32_t)m->hscroll[line*2+1]<<16)|m->hscroll_frac[line*2+1],step=longword(speeds+i*4);
        b=m->scroll_mode==1?b+step:b-step;
        m->hscroll[line*2+1]=(uint16_t)(b>>16);m->hscroll_frac[line*2+1]=(uint16_t)b;
    }
}
/* ApplyBGScroll_SS6: plane B follows SS6BGWave from the stored table offset. */
static void apply_ss6(scd_special_main *m,const scd_special_main_pack *k,unsigned line,unsigned count,uint16_t a,unsigned index){
    const uint8_t *wave=section(k,9)+444;
    for(unsigned i=0;i<count;i++,line++){
        m->hscroll[line*2]=a;m->hscroll[line*2+1]=(uint16_t)(int16_t)(int8_t)wave[index];
        index=(index+1)&0x7f;
    }
    m->wave=(uint16_t)index;
}
void scd_special_main_scroll(scd_special_main *m,const scd_special_main_pack *k,unsigned section,int stage_over){
    if(stage_over || m->scroll_disable || !scd_special_main_line_scroll(m->stage))return;
    uint16_t offset1=(uint16_t)(m->scroll_offset[0]>>16);
    if(m->stage==5){
        if(section==1){
            m->scroll_offset[0]+=(uint32_t)scroll_speed(m,0x40000);
            m->scroll_mode=0;
            if(m->scroll_flags&4){m->scroll_mode=1;m->wave=(m->wave+1)&15;if(!m->wave)m->scroll_mode=2;}
            if(m->scroll_flags&8){m->scroll_mode=0xff;m->wave=(m->wave-1)&15;if(!m->wave)m->scroll_mode=2;}
            for(unsigned line=0;line<17;line++)m->hscroll[line*2]=m->hscroll[line*2+1]=m->hscroll_frac[line*2]=m->hscroll_frac[line*2+1]=0;
            apply_ss5(m,k,17,7,0,0);
        }else if(section==2)apply_ss5(m,k,24,56,7,offset1);
        else apply_ss5(m,k,80,48,63,offset1);
    }else if(m->stage==6){
        if(section==1){
            m->scroll_offset[0]+=(uint32_t)scroll_speed(m,0x40000);
            m->wave=(m->wave+1)&0x7f;apply_ss6(m,k,0,24,0,m->wave);
        }else if(section==2)apply_ss6(m,k,24,56,offset1,m->wave);
        else apply_ss6(m,k,80,48,offset1,m->wave);
    }else if(section==1){
        int32_t speed=scroll_speed(m,0x80000);
        m->scroll_offset[1]+=(uint32_t)speed;m->scroll_offset[0]+=(uint32_t)(speed>>1);
        if(!m->scroll_mode){m->shift++;if(m->shift>=0x200){m->shift=0x1ff;m->scroll_mode=1;}}
        else{m->shift--;if((int16_t)m->shift<0){m->shift=0;m->scroll_mode=0;}}
        apply_ss1(m,0,24,0x10000,0x400,0);
    }else if(section==2)apply_ss1(m,24,72,0xa000,0x400,(uint16_t)(m->scroll_offset[1]>>16));
    else apply_ss1(m,96,32,(uint32_t)-0x8000,0x400,offset1);
    if(section==1)memcpy(m->display,m->hscroll,sizeof(m->display)); /* VInt CopyHScroll_Line */
}
/* Scroll<n>Rows with auto-increment $20: one table entry per 8-line row. */
static unsigned rows(uint16_t *table,unsigned line,unsigned plane,unsigned count,uint32_t offset){
    for(unsigned i=0;i<count;i++,line+=8)table[line*2+plane]=(uint16_t)(offset>>16);
    return line;
}
void scd_special_main_copy_hscroll(scd_special_main *m,unsigned stage,uint16_t *t){
    uint32_t *o=m->scroll_offset;
    if(stage==2 || stage==4){
        /* DefaultBGScroll */
        int32_t d=scroll_speed(m,0x40000);
        o[2]+=(uint32_t)d;d>>=1;o[1]+=(uint32_t)d;d>>=1;o[0]+=(uint32_t)d;
        rows(t,24,0,13,o[1]);
        if(stage==2)rows(t,0,1,16,o[2]);
        else rows(t,rows(t,0,1,11,o[0]),1,5,o[2]);
    }else if(stage==3 || stage==7){
        /* GetScrollSpeed negates the step with the speed. */
        int32_t d=scroll_speed(m,0x80000),step=scroll_speed(m,stage==3?0x10000:0x18000);
        for(unsigned i=0;i<(stage==3?6u:4u);i++){o[i]+=(uint32_t)d;d-=step;}
        if(stage==3){
            rows(t,24,0,13,o[4]);
            unsigned line=rows(t,0,1,6,0);line=rows(t,line,1,3,o[1]);line=rows(t,line,1,1,o[2]);line=rows(t,line,1,4,o[3]);rows(t,line,1,2,o[5]);
        }else{
            rows(t,rows(t,24,0,11,o[1]),0,2,o[3]);
            rows(t,rows(t,0,1,10,o[0]),1,6,o[2]);
        }
    }
}
/* Plane A cell write that records a changed row for the display. */
static void put_tile(scd_special_main *m,unsigned cell,uint16_t tile){
    if(m->plane_a[cell]!=tile){m->plane_a[cell]=tile;m->dirty[0]|=1u<<(cell/64);}
}
/* DrawNumber: repeated subtraction per decimal place, then two tile rows. */
static void draw_number(scd_special_main *m,const uint8_t *tables,unsigned cell,uint32_t value,uint32_t divisor,unsigned digits){
    for(unsigned i=0;i<digits;i++,divisor/=10){
        unsigned digit=0;while(value>=divisor){value-=divisor;digit++;}
        if(digit>11)digit=11; /* Unreachable for HUD values; stay inside the table. */
        put_tile(m,cell+i,word(tables+digit*2));put_tile(m,cell+64+i,word(tables+24+digit*2));
    }
}
void scd_special_main_hud(scd_special_main *m,const scd_special_main_pack *k,uint16_t rings,uint8_t ufo_count){
    draw_number(m,section(k,4),64+27,rings,100,3);
    draw_number(m,section(k,4),64+5,ufo_count,10,2);
}
void scd_special_main_timer(scd_special_main *m,const scd_special_main_pack *k,uint32_t timer){
    if(!m->time_attack){draw_number(m,section(k,4),64+16,timer,100,3);return;}
    draw_number(m,section(k,4),64+13,(timer>>16)&255,10,2);
    draw_number(m,section(k,4),64+16,(timer>>8)&255,10,2);
    draw_number(m,section(k,4),64+19,(uint16_t)(((timer&255)*100)/60),10,2);
}
void scd_special_main_stone_palette(scd_special_main *m,const scd_special_main_pack *k,uint8_t ufo_count){
    if(ufo_count || !m->stone_delay)return;
    if(--m->stone_delay)return;
    for(unsigned i=0;i<5;i++)m->palette[0x31+i]=word(section(k,0)+768+(m->stage-1)*10+i*2);
}
/* IncValue: add, wrap to the minimum past the (unsigned) maximum. */
static uint16_t inc_value(uint16_t *value,unsigned add,uint16_t min,uint16_t max){
    uint16_t v=(uint16_t)(*value+add);if(v>max)v=min;return *value=v;
}
int scd_special_main_cycle(scd_special_main *m,const scd_special_main_pack *k,unsigned stage){
    /* Word offsets of the PalCycle_SS2..SS7 tables in section 8. */
    enum {SS2=0,SS3A=8,SS3B=32,SS4A=38,SS4B=54,SS5A=62,SS5B=69,SS5C=95,SS5D=121,SS6A=149,SS6B=175,SS7=187};
    const uint8_t *t=section(k,8);uint16_t *s=m->cycle[(stage-1)&7],*p=m->palette;
    #define CYCLE(i) word(t+(i)*2)
    switch(stage){
    case 1:{
        uint16_t index=inc_value(&m->cycle_index,8,0,1000);
        const uint8_t *row=section(k,6)+(index&0xfff0);
        for(unsigned i=0;i<16;i++){uint16_t c=row[i];p[32+i]=c>=16?c<<4:c;}
        return 1;
    }
    case 2:{unsigned d=s[0];s[0]=(s[0]+2)&7;for(unsigned i=0;i<4;i++)p[0x1a+i]=CYCLE(SS2+d/2+i);return 1;}
    case 3:{
        unsigned d=inc_value(&s[0],2,0,0x2e)&0xfff8;for(unsigned i=0;i<4;i++)p[0x1a+i]=CYCLE(SS3A+d/2+i);
        if(!inc_value(&s[1],1,0,4))p[0x21]=CYCLE(SS3B+inc_value(&s[2],2,0,0xa)/2);
        return 1;
    }
    case 4:{
        unsigned d=s[0]&0x18;s[0]+=2;for(unsigned i=0;i<4;i++)p[0x1a+i]=CYCLE(SS4A+d/2+i);
        if(!inc_value(&s[1],1,0,2)){d=s[2]&0xe;s[2]+=2;p[0x28]=CYCLE(SS4B+d/2);}
        return 1;
    }
    case 5:
        p[0x1a]=CYCLE(SS5A+inc_value(&s[0],2,0,0xc)/2);p[0x2d]=CYCLE(SS5B+inc_value(&s[1],2,0,0x32)/2);
        p[0x2e]=CYCLE(SS5C+(inc_value(&s[2],1,0,0x33)&~1u)/2);p[0x2f]=CYCLE(SS5D+(inc_value(&s[3],1,0,0x37)&~1u)/2);
        return 1;
    case 6:{
        unsigned d=inc_value(&s[0],2,0,0x18);for(unsigned i=0;i<13;i++)p[0x21+i]=CYCLE(SS6A+d/2+i);
        d=inc_value(&s[1],2,0,0x16)&~3u;p[0x1d]=CYCLE(SS6B+d/2);p[0x1e]=CYCLE(SS6B+d/2+1);
        return 1;
    }
    case 7:p[0x1f]=CYCLE(SS7+(inc_value(&s[0],1,0,0x17)&~1u)/2);return 1;
    }
    #undef CYCLE
    return 0;
}
void scd_special_main_fade(scd_special_main *m,int from_white,unsigned step){
    static const uint8_t channels[3]={1,5,9};
    unsigned d1=channels[(step/8)%3];
    for(unsigned i=0;i<64;i++){
        uint16_t c;
        if(!from_white){
            c=ror(rol(m->palette[i],1),d1);uint16_t d=c&0xeee0;c&=0xe;c+=2;if(c>0xe)c=0xe;
            m->palette[i]=rol(ror(c|d,1),d1);
        }else{
            uint16_t target=ror(rol(m->fade[i],1),d1)&0xe,current=ror(rol(m->palette[i],1),d1)&0xeee0;
            uint16_t intensity=14-2*(step%8);if(target<intensity)target=intensity;
            m->palette[i]=ror(rol(target|current,d1),1);
        }
    }
}
void scd_special_main_add_score(scd_special_main *m,uint32_t points){
    uint32_t value=m->score+points;
    while(value>=m->next_life){m->next_life+=5000;m->lives++;m->extra_players++;if(m->lives>=250)m->lives=249;}
    m->score=value>=1000000?999999:value;
}
void scd_special_main_results(scd_special_main *m,const scd_special_main_pack *k,uint16_t rings,uint32_t timer,uint8_t time_stones){
    m->ring_bonus=(uint32_t)rings*20u;m->time_bonus=(uint32_t)(uint16_t)timer*20u;m->time_stones=time_stones;
    /* Results clears the variable area, not program data such as bonuses. */
    memset(m->palette,0,sizeof(m->palette));memset(m->fade,0,sizeof(m->fade));
    memset(m->plane_a,0,sizeof(m->plane_a));memset(m->plane_b,0,sizeof(m->plane_b));
    memset(m->hscroll,0,sizeof(m->hscroll));memset(m->hscroll_frac,0,sizeof(m->hscroll_frac));memset(m->display,0,sizeof(m->display));
    memset(m->scroll_offset,0,sizeof(m->scroll_offset));m->results_timer=0;m->extra_players=0;m->dirty[0]=m->dirty[1]=0xffffffffu;
    for(unsigned i=0;i<64;i++)m->palette[i]=word(section(k,0)+128+i*2);
    draw_tilemaps(m,k,!m->time_bonus?0x3d:time_stones==0x7f?0x3f:0x3e);
    for(unsigned i=0;i<7;i++)if(time_stones&(1u<<i))draw_tilemaps(m,k,0x29+i);
    draw_tilemaps(m,k,0x33323130u);draw_tilemaps(m,k,0x363534u);
    prep_fade_from_white(m);
}
/* DrawResultsNum: value*10, eight digits, leading zeros blank. */
static void results_number(scd_special_main *m,const uint8_t *tables,unsigned cell,uint32_t value){
    value*=10u;
    if(!value){
        for(unsigned i=0;i<7;i++){put_tile(m,cell+i,0);put_tile(m,cell+64+i,0);}
        put_tile(m,cell+7,0x402d);put_tile(m,cell+71,0x402e);return;
    }
    uint32_t divisor=10000000;int lead=0;
    for(unsigned i=0;i<8;i++,divisor/=10){
        unsigned digit=0;while(value>=divisor){value-=divisor;digit++;}
        if(!lead && !digit){put_tile(m,cell+i,0);put_tile(m,cell+64+i,0);continue;}
        lead=1;if(digit>9)digit=9;
        put_tile(m,cell+i,word(tables+digit*2));put_tile(m,cell+64+i,word(tables+20+digit*2));
    }
}
void scd_special_main_results_vint(scd_special_main *m,const scd_special_main_pack *k){
    results_number(m,section(k,5),14*64+24,m->score);
    results_number(m,section(k,5),20*64+24,m->time_bonus);
    results_number(m,section(k,5),17*64+24,m->ring_bonus);
    m->icon_timer=(m->icon_timer+1)&7;
    if(!m->icon_timer){
        m->icon_frame=(m->icon_frame+1)&1;
        if(m->extra_players){
            unsigned last=m->extra_players-1;if(last>=5)last=4;
            for(int icon=last;icon>=0;icon--)draw_tilemaps(m,k,section(k,7)[icon*2+m->icon_frame]);
        }
    }
    if(m->results_timer)m->results_timer--;
}
unsigned scd_special_main_tally(scd_special_main *m){
    if(m->ring_bonus){scd_special_main_add_score(m,20);m->ring_bonus-=20;return 0xbd;}
    if(m->time_bonus){m->time_bonus-=20;scd_special_main_add_score(m,20);return 0xbd;}
    return 0;
}
unsigned scd_special_main_tally_check(scd_special_main *m,unsigned tapped){
    unsigned result=0;
    if(!m->score_tallied && !(m->time_bonus+m->ring_bonus)){m->score_tallied=1;result=1;}
    if((tapped&0x80) || !m->results_timer)result|=2;
    return result;
}
static uint32_t fnv(uint32_t h,const uint16_t *p,unsigned n){
    while(n--){h=(h^(*p>>8))*16777619u;h=(h^(*p&255))*16777619u;p++;}
    return h;
}
uint32_t scd_special_main_hash(const scd_special_main *m){
    uint32_t h=fnv(2166136261u,m->palette,64);h=fnv(h,m->fade,64);h=fnv(h,m->plane_a,2048);h=fnv(h,m->plane_b,2048);
    h=fnv(h,m->hscroll,256);h=fnv(h,m->hscroll_frac,256);h=fnv(h,m->display,256);
    const uint16_t values[]={m->scroll_offset[0]>>16,m->scroll_offset[0],m->scroll_offset[1]>>16,m->scroll_offset[1],m->shift,m->cycle_index,m->results_timer,m->extra_players,m->icon_frame,m->icon_timer,
        m->scroll_mode,m->scroll_flags,m->stone_delay,m->scroll_disable,m->time_attack,m->stage,m->score_tallied,m->time_stones,
        m->ring_bonus>>16,m->ring_bonus,m->time_bonus>>16,m->time_bonus,m->score>>16,m->score,m->next_life>>16,m->next_life,m->lives,
        m->scroll_offset[2]>>16,m->scroll_offset[2],m->scroll_offset[3]>>16,m->scroll_offset[3],m->scroll_offset[4]>>16,m->scroll_offset[4],m->scroll_offset[5]>>16,m->scroll_offset[5],m->wave};
    return fnv(fnv(h,values,sizeof(values)/sizeof(values[0])),m->cycle[0],sizeof(m->cycle)/sizeof(m->cycle[0][0]));
}
