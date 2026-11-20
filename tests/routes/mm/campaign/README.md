# MM earned Good Future campaign

Entry: the earned SS3 backup (SS3's cold Continue reaches active MM1). Run
`tools/test_mm_campaign.py --act 1 --backup <earned-SS3-backup> --output <MM1>`;
MM2 consumes MM1's backup and MM3C consumes MM2's earned Good Future backup.
The zone gate (`tools/zone-gates.py --gates campaign`) chains them from SS3.

ET8 generators, from the retail layouts (production id 169): MM1 (6727,1153),
MM2 (1352,1408), Present/Past. ET8.C `m_wait` breaks only on an attack hit in the
Past. Each Act 1/2 recording makes exactly one natural Present-to-Past warp,
destroys the generator and finishes in the Past with Good Future set.

MM3 reuses `../mm3C.txt`. EMIE8 ends the game: the tool checks the completed
save, the ALL ZONES CLEAR screen, Start back to the title and a cold Continue
of the completed save.

`mm1-good.txt`: host search seed 41 (200,000 iterations), then 60,000 more from
its first 15,030 pads (Sonic beside the generator). Host: warp 9930, generator
15068, Past tally 17150. Saturn on BIN 2ff99f0f matches every position but has
two late intervals (8869, 10195), fixed by mm-chibi's pacing work; on BIN
36a70ac6 it passes with 0 late. It holds on bbe90b9 (time posts fixed).

`mm2-good.txt`: on bbe90b9 (BIN c275c432), from the first stage's
post-generator prefix with `MM_CAMPAIGN_BONUS` boxes along the MM2C path
(floor y~940, climb at x~6300, lower door 6600-6900/300-500, corridor y<=300
from x 6850; the upper TOBIRA at 6560,208 opens only from the right). Host:
arrival 3373, generator 9745, Past tally 23636.
Emulator evidence only; never hardware acceptance.
