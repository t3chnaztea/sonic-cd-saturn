# Third-party components and notices

This repository's own code is MIT-licensed (see [LICENSE](LICENSE)). It
contains no third-party source trees. The builder fetches the dependencies
below at the revisions pinned in [sources.lock.json](sources.lock.json). Each
one keeps its own license and notices.

| Component | Upstream | License | How it is used |
| --- | --- | --- | --- |
| Yaul (libyaul) | https://github.com/yaul-org/libyaul | MIT | Saturn SDK, linked into the Saturn executable |
| PoneSound | via https://github.com/yaul-org/libyaul-examples | MIT | Sound driver and access layer, compiled into the Saturn executable |
| Sonic CD C decompilation | https://github.com/nfroggy/soniccddecompilation | CC0 1.0 | Reference for game logic, reimplemented in `src/` |
| scddisasm | https://github.com/sonicretro/scddisasm | No license file; contains SEGA-owned data | Downloaded by the build. Its data files are the current source of stage art, layouts, palettes, mappings and other game data. Nothing from it is redistributed here. See below. |
| Genesis Plus GX | https://github.com/libretro/Genesis-Plus-GX | Custom non-commercial license (some parts GPL) | Local test and audio-preparation tooling only. Not linked into the game. Not distributed. |
| Beetle Saturn | https://github.com/libretro/beetle-saturn-libretro | GPL-2.0-or-later | Local emulator validation and host-side CD sector encoding only. Not linked into the game. Not distributed. |

Sonic Z-Treme (GPL-3.0) is mentioned in the hardware notes as a behavioral
comparison only. No code from it is used in this repository.

## scddisasm (build-time download, not redistributed)

- Upstream: https://github.com/sonicretro/scddisasm (Sonic Retro), pinned in
  `sources.lock.json` at `f8cf3f0af7bf419d18182ba98554f09307ad3cc6`.
- `tools/bootstrap.sh` runs `tools/fetch_sources.py`, which downloads it into
  `.deps/scddisasm/` on the user's machine at build time.
- The repository contains SEGA-owned data. At the pinned commit, about 676 of
  its 1,266 `src/` files are binary game data (art, palettes, mappings,
  layouts, collision and similar). It has no license file.
- This project does not redistribute it. No scddisasm file is committed here,
  and `.deps/` is ignored by Git. Users fetch it themselves as part of the
  build and are responsible for owning an original copy of Sonic CD.
- Build parts that depend on it: `tools/convert_assets.py`,
  `tools/title_assets.py`, `tools/special_assets.py`,
  `tools/inventory_objects.py`, the other `special_*_assets.py` scripts,
  `tools/convert_objects.py`, `tools/extract_mmd.py` and related asset
  scripts, plus QA scripts that compare against its assembly source. A traced
  run of the asset scripts opens at least 414 distinct scddisasm files; the
  first four scripts named above open 138 of them.
- A later version plans to extract these assets from the user's own disc
  instead.

## Notices for components compiled into the Saturn executable

### Yaul

```
Copyright (c) 2012-2023 Israel Jacquez <mrkotfw@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining
a copy of this software and associated documentation files (the
"Software"), to deal in the Software without restriction, including
without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to
permit persons to whom the Software is furnished to do so, subject to
the following conditions:

The above copyright notice and this permission notice shall be
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
```

### PoneSound

```
MIT License

Copyright (c) 2020 ponut64

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Disclaimer

This is an unofficial fan project. It is not affiliated with, endorsed by, or
sponsored by SEGA. Sonic the Hedgehog, Sonic CD and all related names, marks
and content are the property of SEGA.

This repository contains no SEGA assets: no graphics, music, sound, level
data, disc images or BIOS files. Small game-logic tables in `src/` (such as
animation timings) are reimplemented from the CC0 decompilation. Test tools locate
retail code on the user's own disc by short byte patterns and SHA-256 digests.

The build does use SEGA-owned data from two places. Audio, sound drivers and
retail game programs come from a Sonic CD disc image and BIOS files that you
supply. Stage graphics, layouts, palettes, mappings and other game data
currently come from scddisasm, which the build downloads at build time (see
above). Not all assets come from your disc yet.

You must own an original copy of Sonic CD and a Sega Saturn, and make your
own dumps of them. Do not ask for, or share, disc images, BIOS files, built
images or `tools/bundle.py` output in this project. `tools/bundle.py` makes a
local-only test ZIP that contains SEGA data; it is for personal use on your
own hardware and must never be distributed.

The project accepts no donations or payment of any kind.
