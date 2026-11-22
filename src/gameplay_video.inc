/* A software clear is required with manual framebuffer changes: VBlank erase
   alone is time-limited. Start that clear before the CPU's simulation work,
   not as a full-screen polygon tacked onto the completed gameplay list.
   Only the currently idle draw bank is touched; the displayed bank remains
   intact until the completed sprite list and VDP2 state are ready to present. */
static vdp1_cmdt_t gameplay_clear_commands[4] __attribute__((aligned(16)));
static int gameplay_clear_initialized,gameplay_clear_started;

static void gameplay_clear_wait(void){
    if(!gameplay_clear_started)return;
    while(!vdp1_transfer_status_get().cef) {}
    gameplay_clear_started=0;
}

static void gameplay_clear_begin(void){
    if(gameplay_clear_started)return;
    if(!gameplay_clear_initialized){
        vdp1_cmdt_t *cmd=gameplay_clear_commands;
        vdp1_cmdt_system_clip_coord_set(cmd);
        vdp1_cmdt_vtx_system_clip_coord_set(cmd,INT16_VEC2(319,223));
        vdp1_cmdt_local_coord_set(cmd+1);
        vdp1_cmdt_vtx_local_coord_set(cmd+1,INT16_VEC2(0,0));
        vdp1_cmdt_polygon_set(cmd+2);
        const vdp1_cmdt_draw_mode_t mode={.color_mode=VDP1_CMDT_CM_RGB_32768,
            .end_code_disable=true,.trans_pixel_disable=true};
        vdp1_cmdt_draw_mode_set(cmd+2,mode);
        cmd[2].cmd_xb=cmd[2].cmd_xc=319;cmd[2].cmd_yc=cmd[2].cmd_yd=223;
        vdp1_cmdt_end_set(cmd+3);gameplay_clear_initialized=1;
    }
    /* The preceding SDK list has finished and swapped before this helper is
       called. No SDK list request is made for this clear-only command list;
       wait for its actual hardware end before the next SDK list transfer. */
    memcpy((void *)VDP1_VRAM(0),gameplay_clear_commands,sizeof(gameplay_clear_commands));
    MEMORY_WRITE(16,VDP1_IOREG_BASE+PTMR,1);
    gameplay_clear_started=1;
}
