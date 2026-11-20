# V0.051 — correct actor overlap ordering

Focused checks pass; not complete-zone or physical-console acceptance.
BIN SHA-256:
`8e21f5b6346d74a6d6a05936e132f6c42b279fa825f4e55c4e4fe11207e15209`.

- Sonic, ordinary objects and boss parts now share original draw-priority
  ordering. TVs and the projector no longer paint over Sonic's shoes; equal
  priorities follow reversed source submission order for Saturn's painter.
- State-dependent priorities cover checkpoint orbs, capsule seeds, holographic
  animals, Tamabboh missiles and ramp plants. Earlier TV-icon, title-VRAM,
  camera alignment, sprite-composition and Sonic-animation fixes are retained.
- Independent checks execute 39,881 untouched retail 68000 queue calls and
  compare 159,744 source-derived priority cases. Pixel tests retain full TV
  coverage, including Sonic overlap, and reject six preserved pre-fix pictures.

All 26 fast gates and focused target checks pass. The 16,800-state main replay
and 16,116-state three-act route preserve every gameplay word and input from
V0.050. Main rendering retains 195 source-exact Sonic pictures / 54 mappings.
World, title, music/effects, isolated diagnostics and special-stage return pass.
Opening, standalone Act 1 and all three sequence acts have zero measured late
intervals. Audio/CD code still matches hardware-confirmed V0.040.

Generated shield/invincibility/time-star effects are not yet in the merged
actor queue. Broader same-priority/lifecycle coverage, all-era routes and
console checks remain open. Original hardware overflow limits are not
emulated. See SPRITE-ORDER.md for exact scope and retained evidence.

The card is unchanged; V0.044 remains the last console-tested build. No new
level or CD++ gameplay change is included, and no recurring job was installed.
