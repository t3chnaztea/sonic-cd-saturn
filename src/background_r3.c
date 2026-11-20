/* Collision Chaos Acts 1/2 deformation from SCR31A-D.C and SCR32A-D.C. The table data is
   generated from the checked scroll IR in tools/scroll/R3/ir. */
#include <stdint.h>
#include "background_r3.h"

enum { R3_ZERO, R3_LAYER, R3_CLOUD, R3_RAMP, R3_INTERP, R3_WAVE };
enum { R3_BGY_RATE, R3_BGY_CAMERA, R3_BGY_CLAMP };

typedef struct { int32_t C, U; } r3_layer;
typedef struct { uint8_t a, b, diff_bits; int32_t n, D, m; } r3_step;
typedef struct {
    uint8_t op, a, b, diff_bits, step_bits; int32_t k;
    int32_t n, m; uint8_t has_seed; r3_step seed;
    uint8_t table; int32_t scale, phase_speed, offset, mask;
} r3_expr;
typedef struct { uint16_t lines; r3_expr e; } r3_run;
typedef struct { uint16_t start, lines; r3_expr e; } r3_band;
typedef struct { uint16_t n; const int16_t *v; } r3_table;
typedef struct { uint8_t op; int32_t C, player_x_min, y_min, div, ref, base, shift, min; } r3_bgy;
typedef struct {
    const char *name; uint16_t buffer_lines; uint8_t nlayers; const r3_layer *layers;
    uint16_t nruns; const r3_run *runs; uint16_t nbands; const r3_band *bands;
    r3_bgy bgy; uint8_t ntables; const r3_table *tables;
} r3_ir;

#if defined(__clang__)
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wmissing-field-initializers"
#endif
#include "background_r3_tables.inc"
#if defined(__clang__)
#pragma clang diagnostic pop
#endif

static int64_t floor_div(int64_t a, int64_t b) {
    int64_t q=a/b;
    if(a%b && ((a<0)!=(b<0)))q--;
    return q;
}
static int64_t floor_65536(int64_t a){return a>=0?a>>16:-(((-a)+65535)>>16);}
static int64_t layer_x(const r3_ir *ir,unsigned i,int x,const int32_t *layers){
    if(i&&layers)return layers[i-1]>>16;
    int32_t value=ir->layers[i].C*x;return value>=0?value/256:-((-value+255)/256);
}
static int64_t step_q(const r3_ir *ir,unsigned a,unsigned b,unsigned bits,int32_t n,int32_t d,int x,const int32_t *layers){
    int32_t delta=(int32_t)(layer_x(ir,b,x,layers)-layer_x(ir,a,x,layers));if(bits==16)delta=(int16_t)delta;
    return n*delta/d;
}
static int expr_x(const r3_ir *ir,const r3_expr *e,int x,const int32_t *layers,unsigned frame,int k){
    switch(e->op){
    case R3_ZERO:return 0;
    case R3_LAYER:return (int)layer_x(ir,e->a,x,layers);
    case R3_CLOUD:return (int)(layer_x(ir,e->a,x,layers)+((uint32_t)(frame*(uint32_t)e->k)>>16));
    case R3_RAMP:{
        int64_t from=layer_x(ir,e->a,x,layers),delta=layer_x(ir,e->b,x,layers)-from;
        if(e->diff_bits==16)delta=(int16_t)delta;
        int64_t q=256*delta/e->k;if(e->step_bits==16)q=(int16_t)q;
        return (int)(from+floor_div((int64_t)k*q,256));
    }
    case R3_INTERP:{
        int64_t q=step_q(ir,e->a,e->b,e->diff_bits,e->n,e->k,x,layers),seed=0;
        if(e->has_seed){const r3_step *s=&e->seed;seed=(uint16_t)(s->m*step_q(ir,s->a,s->b,s->diff_bits,s->n,s->D,x,layers));}
        return (int)(layer_x(ir,e->a,x,layers)+floor_65536(seed+(int64_t)e->m*q));
    }
    case R3_WAVE:{
        unsigned phase=((uint32_t)frame*(uint32_t)e->phase_speed)>>8;
        unsigned index=(phase+(unsigned)e->offset+(unsigned)k)&(unsigned)e->mask;
        return (int)(layer_x(ir,e->a,x,layers)+(int64_t)e->scale*ir->tables[e->table].v[index]);
    }
    }
    return 0;
}
#define R3_PROGRAMS (sizeof r3_programs/sizeof r3_programs[0])
static const r3_ir *program(unsigned era){return era<R3_PROGRAMS?r3_programs[era]:0;}
static uint8_t entry_runs[R3_PROGRAMS][128],entry_runs_ready;
static void entry_runs_init(void){
    if(entry_runs_ready)return;
    for(unsigned era=0;era<R3_PROGRAMS;era++){
        const r3_ir *ir=r3_programs[era];unsigned entry=0;if(!ir)continue;
        for(unsigned run=0;run<ir->nruns;run++)
            for(unsigned n=0;n<ir->runs[run].lines/8&&entry<128;n++)entry_runs[era][entry++]=(uint8_t)run;
    }
    entry_runs_ready=1;
}
static const r3_band *band_at(const r3_ir *ir,int line){
    const unsigned tail_count=56,head_count=ir->nbands-tail_count;
    if(line>=704&&line<704+(int)tail_count)return &ir->bands[head_count+(unsigned)(line-704)];
    for(unsigned i=0;i<head_count;i++){const r3_band *b=&ir->bands[i];if(line>=b->start&&line<b->start+b->lines)return b;}
    return 0;
}
static int table_x(unsigned era,const r3_ir *ir,int x,const int32_t *layers,unsigned frame,int entry);
static int scalar_x(unsigned era,const r3_ir *ir,int x,const int32_t *layers,int y,unsigned frame){
    int line=y&(ir->buffer_lines-1),within=0;const r3_band *band=band_at(ir,line);
    if(band)return expr_x(ir,&band->e,x,layers,frame,line-band->start);
    (void)within;return table_x(era,ir,x,layers,frame,line/8);
}
int scd_r3_background_y(unsigned era,int y){
    const r3_ir *ir=program(era);if(!ir)return y/8;
    unsigned yu=(uint16_t)y;int v=ir->bgy.base;
    if(yu<=(unsigned)ir->bgy.ref)v=(int16_t)(ir->bgy.base-(int)((ir->bgy.ref-yu)>>ir->bgy.shift));
    return v<ir->bgy.min?ir->bgy.min:v;
}
int scd_r3_raster_x(unsigned era,int x,int y,unsigned frame){return scd_r3_raster_x_layers(era,x,0,y,frame);}
int scd_r3_raster_x_layers(unsigned era,int x,const int32_t *layers,int y,unsigned frame){const r3_ir *ir=program(era);return ir?scalar_x(era,ir,x,layers,y,frame):x/8;}

static int table_x(unsigned era,const r3_ir *ir,int x,const int32_t *layers,unsigned frame,int entry){
    if(entry<0||entry>=128)return 0;
    entry_runs_init();
    int within=0;const r3_expr *e=&ir->runs[entry_runs[era][entry]].e;
    /* SCR31A's reconstructed C describes a four-times-larger shift than the
       retail 68000 instructions execute. CPU captures prove the same n=64
       interpolation used by SCR31C, including the retained fraction seed. */
    if(ir==r3_programs[0]&&(entry<=5||(entry>=79&&entry<=87))){
        int32_t left=layers?layers[3]:0;
        if(entry<=5)return (int)(layer_x(ir,e->a,x,layers)+floor_65536(left+(int64_t)e->m*step_q(ir,e->a,e->b,e->diff_bits,64,e->k,x,layers)));
        const r3_step *sd=&e->seed;
        uint16_t seed=(uint16_t)(left+sd->m*step_q(ir,sd->a,sd->b,sd->diff_bits,64,sd->D,x,layers));
        return (int)(layer_x(ir,e->a,x,layers)+floor_65536(seed+(int64_t)e->m*step_q(ir,e->a,e->b,e->diff_bits,e->n,e->k,x,layers)));
    }
    /* The same leftover d3 high word (0 or 65535) seeds the first loop's
       seven rows in the C-shaped programs. */
    if((ir==r3_programs[2]||ir==r3_programs[4]||ir==r3_programs[6]||ir==r3_programs[10])&&entry<=5&&layers&&e->op==R3_INTERP&&!e->has_seed){
        int64_t q=step_q(ir,e->a,e->b,e->diff_bits,e->n,e->k,x,layers);
        return (int)(layer_x(ir,e->a,x,layers)+floor_65536(layers[3]+(int64_t)e->m*q));
    }
    /* SCR31C/SCR32A/SCR32C/SCR33C.C describe a <<11 ramp that starts at m=0 on
       entry 78; retail CPU captures prove m=(entry-77)*1024 with the seed. */
    if((ir==r3_programs[2]||ir==r3_programs[4]||ir==r3_programs[6]||ir==r3_programs[10])&&entry>=78&&entry<=87){
        /* The first loop sets only d3.w, so its high word starts with the
           leftover scroll X difference sign (as SCR31D) before the seed. */
        const r3_expr *first=&ir->runs[entry_runs[era][79]].e;const r3_step *sd=&first->seed;
        int64_t q=step_q(ir,first->a,first->b,first->diff_bits,64,first->k,x,layers);
        uint16_t seed=(uint16_t)((layers?layers[3]:0)+sd->m*step_q(ir,sd->a,sd->b,sd->diff_bits,sd->n,sd->D,x,layers));
        return (int)(layer_x(ir,first->a,x,layers)+floor_65536(seed+(int64_t)(entry-77)*1024*q));
    }
    if((ir==r3_programs[3]||ir==r3_programs[7]||(ir==r3_programs[11]&&entry<=86))&&entry>=79&&entry<=87&&layers&&layers[3]){
        int64_t q=step_q(ir,e->a,e->b,e->diff_bits,e->n,e->k,x,layers);
        return (int)(layer_x(ir,e->a,x,layers)+floor_65536(layers[3]+(int64_t)e->m*q));
    }
    return expr_x(ir,e,x,layers,frame,within);
}
typedef struct { int32_t layer[4],q_initial,q_later,seed; } r3_frame;
static r3_frame frame_init(unsigned era,int x,const int32_t *layers){
    static const int8_t initial_n[4]={64,32,64,0},initial_d[4]={28,12,28,1};
    static const int8_t later_d[4]={40,24,44,24};
    r3_frame f={{x,layers[0]>>16,layers[1]>>16,layers[2]>>16},0,0,layers[3]};
    int32_t delta=f.layer[0]-f.layer[1];
    if(initial_n[era])f.q_initial=initial_n[era]*delta/initial_d[era];
    f.q_later=64*(int16_t)delta/later_d[era];
    return f;
}
static inline __attribute__((always_inline)) int table_x_frame(unsigned era,const r3_ir *ir,
        const r3_frame *f,unsigned frame,int entry){
    if(entry<0||entry>=128)return 0;
    const r3_expr *e=&ir->runs[entry_runs[era][entry]].e;
    int32_t m=e->m,q=f->q_later;
    if(era==2&&entry>=78&&entry<=87){
        e=&ir->runs[entry_runs[era][79]].e;m=(entry-77)*1024;
    }
    switch(e->op){
    case R3_ZERO:return 0;
    case R3_LAYER:return f->layer[e->a];
    case R3_CLOUD:return f->layer[e->a]+(int)(((uint32_t)frame*(uint32_t)e->k)>>16);
    case R3_INTERP:
        if(!e->has_seed&&e->diff_bits==32)q=f->q_initial;
        if(era==3&&entry>=79&&entry<=87&&f->seed)
            return f->layer[e->a]+(int)floor_65536(f->seed+(int64_t)m*q);
        {   /* A/C-shaped retail loads only d3.w: its high word keeps the
               scroll X difference sign (see table_x). */
            int32_t left=(era==0||era==2)?f->seed:0;
            return f->layer[e->a]+(int)floor_65536((e->has_seed?(uint16_t)(left+e->seed.m*f->q_initial):left)+(int64_t)m*q);
        }
    default:return expr_x(ir,e,f->layer[0],0,frame,0);
    }
}
static inline __attribute__((always_inline)) void emit_repeat(int bg,int fg,int32_t *background,int32_t *foreground,
        unsigned count,unsigned *written,unsigned lines){
    unsigned available=*written<count?count-*written:0;
    if(lines>available)lines=available;
    int32_t bg_word=(int32_t)(bg&511)*65536,fg_word=(int32_t)(fg&511)*65536;
    unsigned end=*written+lines;
    if(foreground)while(*written<end){background[*written]=bg_word;foreground[*written]=fg_word;(*written)++;}
    else while(*written<end)background[(*written)++]=bg_word;
}
void scd_r3_lines(unsigned era,int x,int camera_y,int top,unsigned frame,int32_t *background,int32_t *foreground,unsigned count){
    scd_r3_lines_layers(era,x,0,camera_y,top,frame,background,foreground,count);
}
void scd_r3_lines_layers(unsigned era,int x,const int32_t *layers,int camera_y,int top,unsigned frame,int32_t *background,int32_t *foreground,unsigned count){
    const r3_ir *ir=program(era);if(!ir)return;
    r3_frame fast;int use_fast=layers!=0&&era<4;
    if(use_fast){entry_runs_init();fast=frame_init(era,x,layers);}
    /* z3?x_kawatbl: SCR33D.C moves the Bad Future water line to 24. */
    static const uint16_t kawatbl[4][3]={{56,592,32767},{64,528,32767},{56,592,32767},{8,32767,32767}};
    static const uint16_t kawatbl_33d[3]={24,32767,32767};
    const int16_t *sine=ir->tables[0].v;unsigned phase=((uint32_t)frame*64>>8)&255;
    unsigned variant=era&3,wave_span=variant==1?32:24;
    const uint16_t *boundaries_row=era==11?kawatbl_33d:kawatbl[variant];
    unsigned written=0,boundary=0;int entry=top/8,world=top,rows=87-entry,tail=variant==1?28:29,wave;
    if(rows>=27)rows=28;tail-=rows;
    /* Direct, bounded translation of zonescrsetsub0.  A wave consumes whole
       table entries even when the viewport begins part-way through it. */
    if(boundaries_row[boundary]<=world)goto wave_initial;
partial_row: {
        int partial=world&7,value=use_fast?table_x_frame(era,ir,&fast,frame,entry++):table_x(era,ir,x,layers,frame,entry++);world+=8-partial;
        emit_repeat(value,x,background,foreground,count,&written,(unsigned)(8-partial));
        if(--rows<0||written>=count)goto first_done;
    }
next_row:
    if(rows<0||written>=count)goto first_done;
    if(boundaries_row[boundary]<=world)goto wave_after_row;
plain_row: {
        int value=use_fast?table_x_frame(era,ir,&fast,frame,entry++):table_x(era,ir,x,layers,frame,entry++);world+=8;
        emit_repeat(value,x,background,foreground,count,&written,8);
        if(--rows>=0)goto next_row;
        goto first_done;
    }
wave_initial:
    wave=boundaries_row[boundary++]+wave_span-world;
    if(wave>0)goto emit_wave;
    if(boundaries_row[boundary]>world)goto partial_row;
    wave=boundaries_row[boundary++]+wave_span-world;
    if(wave>0)goto emit_wave;
    goto partial_row;
wave_after_row:
    wave=boundaries_row[boundary++]+wave_span-world;
    if(wave<=0)goto plain_row;
emit_wave: {
        int consume=(wave+7)/8,advance=consume,b=(int)layer_x(ir,1,x,layers);
        int32_t fg_word=(int32_t)(x&511)*65536;
        for(int n=0;n<wave&&written<count;n++){
            background[written]=(int32_t)((b+sine[(phase+(unsigned)n)&255])&511)*65536;
            if(foreground)foreground[written]=fg_word;
            written++;
        }
        world+=wave;entry+=advance;rows-=consume;
        goto next_row;
    }
first_done:
    if(written>=count)return;
    /* hscrollwork[30...] supplies one accumulator per line after world row
       87.  The generated IR stores its 56 one-line bands contiguously at the
       end of the band table, so do not search the entire table per line.  Its
       foreground half gains a second sine when the camera is low. */
    const unsigned tail_band_count=56,tail_band_first=ir->nbands-tail_band_count;
    int tail_base=(int)layer_x(ir,1,x,layers);
    const r3_expr *tail_first=&ir->bands[tail_band_first].e;
    uint32_t tail_phase=(uint32_t)frame*(uint32_t)tail_first->k;
    uint32_t tail_step=(uint32_t)frame*(uint32_t)
        (ir->bands[tail_band_first+1].e.k-tail_first->k);
    for(int n=0;n<tail*8&&written<count;n++){
        int bg=tail_base,fg=x;
        if((unsigned)n<tail_band_count){bg+=(int)(tail_phase>>16);tail_phase+=tail_step;}
        if(1472-camera_y<=(int)written){
            unsigned p=phase+(unsigned)n;
            fg=x+(era>=4?sine[p&255]*2:era?sine[p&255]*2:sine[(p&127)*2]);
        }
        background[written]=(int32_t)(bg&511)*65536;
        if(foreground)foreground[written]=(int32_t)(fg&511)*65536;
        written++;world++;
    }
    emit_repeat(0,x,background,foreground,count,&written,count-written);
}

/* The plane row a BG line shows is drawn by one layer (z3?x_wrttbl, per
   16-pixel row): id 0 draws x 0 across all 512 pixels, ids 2/4/6 draw around
   scrb/scrc/scrz. Line deformation only indexes that row modulo 512. */
int scd_r3_row_layer(unsigned era,int y){
    if(era>=R3_PROGRAMS||!r3_programs[era])return -1;
    unsigned row=((unsigned)(uint16_t)y/16+1)&127;
    return row<49?r3_wrttbl[era][row]/2:0;
}
int scd_r3_row_start(unsigned era,int x,const int32_t *layers,int y){
    const r3_ir *ir=program(era);int id=scd_r3_row_layer(era,y);
    if(!ir||id<=0)return 0;
    /* Any 64-tile window holding the 41 visible columns shows the same
       cells; keep 11 spare columns left and 12 right of the layer. */
    return (int)floor_div(layer_x(ir,(unsigned)id,x,layers),8)-11;
}
