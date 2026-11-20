/* Driver for the retail oracle (tools/scroll/R6/oracle.py).  Included at the
   end of a generated build/oracle_<name>.c, after the verbatim retail
   functions, with ORACLE_IR naming the draft IR of the same program.  Nothing
   here is specific to a program: the buffer height comes from the IR, the
   camera is moved the way play moves it, and every rendered line is
   compared.  See oracle.py for the walk and the line classes. */
#include <stdint.h>

static int_union render[512];
static unsigned frame_no;
static int cam_x;
static long long a_compared, a_mismatch, b_lines, b_mismatch, bgy_compared, bgy_mismatch, windows_done;
static int a_maxdiff;
static char first[256];

static void move_camera(int x_new) {
    int dx = x_new - cam_x;
    if (dx > 16 || dx < -16) { fprintf(stderr, "oracle: camera step %d > 16\n", dx); exit(2); }
    scra_h_posit.w.h = (short)x_new; scra_h_posit.w.l = 0;
    scra_hz = (short)(dx << 8);
    scra_v_posit.w.h = 0; scra_v_posit.w.l = 0;
    scroll_start.w = 0;
    lphscrollbuff = render;
    scroll();
    cam_x = x_new;
    frame_no++;
}

/* render the window whose background Y is `top`, at the current camera X */
static void window(int top) {
    const unsigned buffer = ORACLE_IR.buffer_lines, rows = buffer / 8;
    memset(render, 0xA5, sizeof render);
    scra_hz = 0;
    scra_v_posit.w.h = (short)(4 * top);
    scroll_start.w = 0;
    lphscrollbuff = render;
    scroll();
    windows_done++;
    if ((uint16_t)scrb_v_posit.w.h != (uint16_t)top) {
        fprintf(stderr, "oracle: camera Y %d gave background Y %d, expected %d\n", 4 * top, scrb_v_posit.w.h, top);
        exit(2);
    }
    for (int i = 0; i < 224; i++) {
        unsigned row = ((unsigned)(top & (int)(buffer - 8)) >> 3) + ((unsigned)(i + (top & 7)) >> 3);
        uint16_t retail = (uint16_t)render[i].w.l;
        uint16_t model = (uint16_t)(-scroll_ir_raster_x(&ORACLE_IR, cam_x, top + i, frame_no, 0));
        if (row >= rows) {           /* class B: render reads hscrollwork past the table rows */
            b_lines++;
            if (retail != model) b_mismatch++;
            continue;
        }
        a_compared++;
        if (retail != model) {
            int d = (int16_t)(uint16_t)(retail - model);
            if (d < 0) d = -d;
            if (d > a_maxdiff) a_maxdiff = d;
            if (!a_mismatch)
                snprintf(first, sizeof first, "x=%d top=%d line=%d bg_line=%d retail=%d model=%d",
                         cam_x, top, i, top + i, -(int16_t)retail, -(int16_t)model);
            a_mismatch++;
        }
    }
}

static int special(int x) {
    static const int xs[] = {0, 1, 2, 3, 7, 8, 15, 16, 255, 256, 257, 338, 339, 1000, 4095, 4096,
                             8855, 9111, 12345, 16382, 16383, -1, -256, -4096};
    for (unsigned i = 0; i < sizeof xs / sizeof xs[0]; i++)
        if (xs[i] == x) return 1;
    return 0;
}

static void check_here(void) {
    const int tops = 1024;
    if (special(cam_x) || frame_no % 512 == 0) {
        for (int t = 0; t < tops; t++) window(t);
    } else {
        for (int k = 0; k < 4; k++) window((int)((frame_no * 131u + (unsigned)k * 263u) & (tops - 1)));
    }
}

int main(void) {
    unsigned n = 0;
    lphscrollbuff = render;
    check_here();
    for (int x = 1; x <= 16383; x++) { move_camera(x); check_here(); }                /* walk 1 */
    while (cam_x > -4096) {                                                           /* walk 2 */
        int dx = 1 + (int)(n++ % 16), x = cam_x - dx;
        if (x < -4096) x = -4096;
        if ((cam_x > -1 && x < -1) || (cam_x > -256 && x < -256)) x = cam_x > -1 ? -1 : -256;
        move_camera(x); check_here();
    }
    while (cam_x < 0) {                                                               /* walk 3 */
        int dx = 1 + (int)(n++ % 16), x = cam_x + dx;
        if (x > 0) x = 0;
        move_camera(x); check_here();
    }
    for (int y = -32768; y <= 65535; y++) {                                           /* background Y */
        scra_hz = 0;
        scra_v_posit.w.h = (short)y;
        lphscrollbuff = render;
        scroll();
        bgy_compared++;
        if ((uint16_t)scrb_v_posit.w.h != (uint16_t)scroll_ir_background_y(&ORACLE_IR, y, 0)) bgy_mismatch++;
    }
    printf("{\"program\": \"%s\", \"frames\": %u, \"windows\": %lld, \"a_compared\": %lld, \"a_mismatch\": %lld, "
           "\"a_maxdiff\": %d, \"b_lines\": %lld, \"b_mismatch\": %lld, \"bgy_compared\": %lld, "
           "\"bgy_mismatch\": %lld, \"first\": \"%s\"}\n",
           ORACLE_PROGRAM, frame_no, windows_done, a_compared, a_mismatch, a_maxdiff, b_lines, b_mismatch,
           bgy_compared, bgy_mismatch, first);
    return (a_mismatch || bgy_mismatch) ? 1 : 0;
}
