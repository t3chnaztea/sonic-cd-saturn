#include <stdio.h>
#include <string.h>
#include "cd-block_cmds.c"
#include "cd-block-init-test.inc"
#include "cd-status-original-test.inc"
uint16_t mock_registers[32];
static uint16_t response,commands[16];
static unsigned calls;
static int transport_error;
int cd_block_cmd_execute(struct cd_block_regs *request,struct cd_block_regs *reply){
    assert(calls<16);commands[calls++]=request->cr1;
    memset(reply,0,sizeof(*reply));reply->cr1=response;
    mock_registers[HIRQ/2]=0xffff;
    return transport_error;
}
static void reset(uint16_t cr1,int transport){
    response=cr1;transport_error=transport;calls=0;
    mock_registers[HIRQ/2]=0xffff;
}
int main(void){
    cd_block_regs_t old={0};
    old.cr1=0x0102;assert(original_status_check(&old)==-10 && scd_cd_response_error(old.cr1)==0);
    old.cr1=0x01ff;assert(original_status_check(&old)==-10 && scd_cd_response_error(old.cr1)==0);
    old.cr1=0x030e;assert(original_status_check(&old)==-10 && scd_cd_response_error(old.cr1)==0);
    old.cr1=0x0a00;assert(original_status_check(&old)==0 && scd_cd_response_error(old.cr1)==-10);
    /* All 65,536 response words. Independent status-code table, including
       healthy STANDBY/PLAY/RETRY and all low-byte report values. */
    const int states[16]={0,0,0,0,0,0,-6,-7,0,-9,-10,-11,-12,-13,-14,-15};
    for(unsigned word=0;word<=65535;word++){
        unsigned high=word>>8;
        int expected=high>=128?(int)high:states[high%16];
        assert(scd_cd_response_error(word)==expected);
    }
    /* Real generated SDK command wrappers and the unmodified SDK init sequence.
       Report 0xFF is allowed with a healthy status (invalid CD position), and
       0x02/0x0E used to be misreported as fatal by the low-byte bitmask bug. */
    for(unsigned low=0;low<256;low++){
        reset(0x0100|low,0);assert(cd_block_init()==0 && calls==4);
        assert(commands[0]==0x7500 && commands[1]==0x0400 && commands[2]==0x0600 && commands[3]==0x48fc);
        reset(0x0300|low,0);assert(cd_block_cmd_disk_play(15,150,450)==0);
        reset(0x0100|low,0);assert(cd_block_cmd_disk_seek(0xffffff)==0);
    }
    for(unsigned state=6;state<=10;state++)if(state!=8){
        reset(state<<8,0);assert(cd_block_init()==-(int)state && calls==1);
    }
    reset(0x0100,-1);assert(cd_block_init()==-1 && calls==1);
    reset(0x0100,0xff);assert(cd_block_init()==0xff && calls==1);
    reset(0x0100,0x81);assert(cd_block_init()==0x81 && calls==1);
    puts("CD status: original false-fatal/missed-fatal reproduced; 65536 responses, 256 init/play/seek reports, real-error and transport propagation passed");
}
