"""Title menu entries by identity, for the emulator gates that walk the menu.

The menu holds its options in retail order (Menu/Main.asm:75, src/title.c): NEW GAME,
CONTINUE (saved progress), TIME ATTACK (titleFlags bit 5), RAM DATA, D.A. GARDEN
(bit 3) and VISUAL MODE (bit 2); the cursor opens on CONTINUE when there is saved
progress, else on NEW GAME. A gate boots its fixture once with PROBE, reads the
cursor and the records' titleFlags, and gets the Right presses to an option from
that list, so a newly unlocked entry cannot shift the route.

PROBE needs the harness symbols 'trace' (_scd_trace_mailbox) and 'rec' (_fe_ta_rec:
titleFlags is byte 592, src/time_attack.h).
"""
NEW_GAME, CONTINUE, TIME_ATTACK, RAM_DATA, DA_GARDEN, VISUAL_MODE = 2, 3, 4, 5, 6, 7
NAMES = {NEW_GAME: 'NEW GAME', CONTINUE: 'CONTINUE', TIME_ATTACK: 'TIME ATTACK', RAM_DATA: 'RAM DATA',
         DA_GARDEN: 'D.A. GARDEN', VISUAL_MODE: 'VISUAL MODE'}
PROBE = ('run 200\nuntil TITL 3000\nrun 240\nhold START 4\nrun 90\n'
         'peek menu_cursor trace 0 4\npeek menu_flags rec 588 2\n')
STEP = 'hold RIGHT 4\nrun 60\n'


def options(peeks):
    """(cursor, options by position) from a PROBE run's peeks."""
    cursor = peeks['menu_cursor'][2] >> 16 & 255
    title_flags = peeks['menu_flags'][1] >> 24
    flags = 0x90 | (0x40 if cursor == 2 else 0) | (title_flags & 0x2C)
    menu = [None, NEW_GAME] + ([CONTINUE] if flags & 0x40 else [])
    menu += [option for bit, option in ((5, TIME_ATTACK), (4, RAM_DATA), (3, DA_GARDEN), (2, VISUAL_MODE))
             if flags >> bit & 1]
    return cursor, menu


def route(peeks, option):
    """(script that moves the open menu's cursor to option, its position)."""
    cursor, menu = options(peeks)
    if option not in menu:
        raise ValueError(f'{NAMES[option]} is not on this fixture\'s menu: {[NAMES[o] for o in menu[1:]]}')
    position = menu.index(option)
    if position < cursor:
        return 'hold LEFT 4\nrun 60\n' * (cursor - position), position
    return STEP * (position - cursor), position
