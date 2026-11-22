#include "player_replay.h"
#include "scd_objects.h"
/* Place the loop fixture on its entry floor with enough ground speed. */
void scd_replay_begin(unsigned test) {
    scd_objects_reset(scd_replay_era(test),test==19);
    if(test>=24)return;
    if(test==7)scd_player_place(1740,724,2048,0,0);
    if(test<8)return;
    scd_player_place(80,488,0,0,2);
    if(test==8 || test==9)scd_objects_spawn(SCD_OBJ_SPRING,80,508,test==9?2:0,0);
    if(test==10 || test==11) {
        scd_player_place(test==10?80:120,493,test==10?256:-256,0,0);
        scd_objects_spawn(SCD_OBJ_SPRING,100,493,4,test==11?1:0);
    }
    if(test==12) {
        scd_player_place(80,493,0,0,0);
        scd_objects_spawn(SCD_OBJ_SPRING,80,442,0,2);
    }
    if(test==13)scd_objects_spawn(SCD_OBJ_SPRING,80,512,8,0);
    if(test==14)scd_objects_spawn(SCD_OBJ_RING,80,488,0,0);
    if(test==15 || test==16) {
        if(test==16)scd_player_inventory(5,1);
        /* Preserve the fixture top at Y=502 with the source radius 8. */
        scd_objects_spawn(SCD_OBJ_SPIKES,80,510,0,0);
    }
    if(test==17) {
        scd_objects_reset(1,1);
        scd_player_place(148,418,0,0,2);
    }
    if(test==20) {
        scd_player_place(80,465,0,0,2);
        scd_objects_spawn(SCD_OBJ_BOULDER,80,500,0,0);
    }
    if(test==21) {
        scd_player_place(60,493,1536,0,0);
        scd_objects_spawn(SCD_OBJ_BOULDER,100,493,0,0);
    }
    if(test==22) {
        scd_player_place(80,493,0,0,0);
        scd_objects_spawn(SCD_OBJ_SPIKES,80,442,0,2);
    }
    if(test==23)scd_player_inventory(40,0);
    if(test==18) {
        for(unsigned n=0;n<SCD_OBJECT_CAPACITY+4;n++)scd_objects_spawn(SCD_OBJ_RING,300+n,350,0,0);
        scd_objects_spawn(255,80,488,0,0);
    }
}
void scd_replay_tick(unsigned test,unsigned frame) {
    if(test==23 && frame==0)scd_objects_hurt(88);
    if(test==14 && (frame==3 || frame==4 || frame==50)) {
        scd_player_state p=scd_player_get();
        scd_objects_hurt(p.x/65536+8);
    }
    if(test==17 && (frame==40 || frame==80))scd_player_place(frame==40?3000:148,418,0,0,2);
}
unsigned scd_replay_era(unsigned test) { return test<4?test:(test==24 || test==26)?0:1; }
unsigned scd_replay_buttons(unsigned test,unsigned frame) {
    if(test>=24) {
        unsigned end=test==27?40:100;
        if(frame>=30 && frame<end)return SCD_DOWN|((test!=26 && frame<34)?SCD_JUMP:0);
        return 0;
    }
    if(test<4) {
        unsigned buttons=frame>=60 && frame<240?SCD_RIGHT:frame>=350 && frame<450?SCD_LEFT:0;
        if(frame>=150 && frame<175)buttons|=SCD_JUMP;
        return buttons;
    }
    if(test==4) {
        if(frame>=30 && frame<90)return SCD_DOWN|(frame>=35 && frame<38?SCD_JUMP:0);
        return frame>=90 && frame<300?SCD_RIGHT:0;
    }
    if(test==5 || test==6) {
        return frame>=60 && frame<(test==5?61:90)?SCD_JUMP:0;
    }
    if(test==7 || test==19)return SCD_RIGHT;
    if(test==12 || test==22)return frame<10?SCD_JUMP:0;
    return 0;
}
void scd_replay_words_snapshot(scd_player_state s,uint32_t words[16],scd_object_stats *snapshot) {
    words[0]=s.x;words[1]=s.y;
    words[2]=((uint32_t)(uint16_t)s.vx<<16)|(uint16_t)s.vy;
    words[3]=((uint32_t)(uint16_t)s.speed<<16)|((uint32_t)s.flags<<8)|s.angle;
    words[4]=((uint32_t)s.animation<<24)|((uint32_t)s.path<<16)|((uint32_t)s.charge<<8);
    words[5]=s.lock;words[6]=s.frame;words[7]=s.resets;
    scd_object_stats o=scd_objects_get();
    if(snapshot)*snapshot=o;
    words[8]=((uint32_t)s.rings<<16)|s.hurt;
    words[9]=((uint32_t)s.routine<<24)|((uint32_t)s.shield<<16)|s.lives;
    words[10]=((uint32_t)o.springs<<16)|o.hits;
    words[11]=((uint32_t)o.deaths<<16)|o.lost;
    words[12]=((uint32_t)o.active<<16)|o.collected;
    words[13]=((uint32_t)o.spawned<<16)|o.despawned;
    words[14]=o.hash;words[15]=((uint32_t)o.dropped<<16)|o.unsupported;
}
void scd_replay_words(scd_player_state s,uint32_t words[16]) {
    scd_replay_words_snapshot(s,words,0);
}
void scd_replay_visual_words(scd_player_state s,uint32_t words[2]){
    words[0]=((uint32_t)s.mapping<<24)|((uint32_t)s.render_flags<<16)|((uint32_t)s.animation<<8)|s.animation_previous;
    words[1]=((uint32_t)s.animation_cursor<<24)|((uint32_t)s.animation_timer<<16)|((uint32_t)s.control<<8)|s.disc_frame;
}
