"""DEV41A cg_change/cg_chg1 over source-parsed tables, without a C compiler.

Matches the pinned CC0 function's signed-char timer, counter advance and camera
gate. Bitmap identifiers come from the user's source tree, never this module.
"""
import re


class TidalSchedule:
    def __init__(self, source):
        source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
        art = {}
        for name, body in re.findall(r'static\s+int\s+(\w+)\[16\]\s*=\s*\{([^}]*)\}', source):
            values = [int(s) for s in re.findall(r'-?\d+', body)]
            if len(values) != 16:
                raise ValueError('Unexpected DEV41A bitmap row')
            art[name] = values
        self.scripts = []
        for slot in range(3):
            match = re.search(r'static\s+tile_changes\s+tbl_fir'+str(slot)+r'\s*=\s*\{(.*?)\n\};', source, re.S)
            if not match:
                raise ValueError('DEV41A fire script is missing')
            body = match[1]
            names = re.findall(r'\bfire\dcg\b', body)
            values = [int(s) for s in re.findall(r'-?\d+', re.sub(r'\bfire\dcg\b', '', body))]
            count = values[0]
            if count != 24 or len(names) != 8 or len(values) != 3+count*2:
                raise ValueError('Unexpected DEV41A script shape')
            self.scripts.append(dict(pairs=list(zip(values[2:-1:2], values[3:-1:2])),
                                     frames=[art[name] for name in names], start=values[-1]))
        self.init()

    def init(self):
        self.timers = [0]*3
        self.counters = [0]*3
        self.tiles = [-1]*2048

    def step(self, x, y):
        if x >= 640 or y >= 352:
            return
        for slot, script in enumerate(self.scripts):
            timer = self.timers[slot] = (self.timers[slot]-1)&255
            if timer < 128:
                continue
            index = self.counters[slot] = (self.counters[slot]+1)%len(script['pairs'])
            self.timers[slot], frame = script['pairs'][index]
            start = script['start']
            self.tiles[start:start+16] = script['frames'][frame]

    def tile(self, index):
        return self.tiles[index&2047]
