/* Public native title-card timeline; no duplicated state-machine reference. */
#include <stdio.h>
#include "title_card.h"

int main(void) {
    for (unsigned act=0;act<3;act++) {
        scd_title_card_start(act);
        for (unsigned tick=1;tick<=240;tick++) {
            int locked=scd_title_card_step();
            scd_title_card_view views[9];
            unsigned count=scd_title_card_views(views,9);
            printf("%u %u %d %d %u",act,tick,locked,scd_title_card_active(),count);
            for (unsigned i=0;i<count;i++)
                printf(" %d %d %u",views[i].x,views[i].y,views[i].frame);
            putchar('\n');
        }
    }
    return 0;
}
