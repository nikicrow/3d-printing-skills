---
name: playdoh-roller-v2
description: Generate a Play-Doh roller whose name + decorations are ENGRAVED (recessed) INTO the barrel, so the dough imprint comes out RAISED/embossed instead of indented. Same names, fonts, themes, and printable STL pipeline as playdoh-roller — just the inverse relief. Outputs get a _v2 suffix.
---

# Play-Doh Roller Generator — v2 (engraved / raised imprint)

Same generator as [[playdoh-roller]], with one difference: the name and
decorations are **pushed INTO the roller** (recessed) instead of standing out.

- **v1 (playdoh-roller):** features bump OUT of the roller → they press DOWN into
  the dough → the dough imprint is **indented** (sunken).
- **v2 (this skill):** features are carved IN to the roller → the surrounding
  surface flattens the dough while the recesses leave material → the dough
  imprint is **raised** (embossed, stands up).

Everything else is identical — same names, same fonts, same decoration icons,
same themes, same upright/solid/print-ready STL. Outputs are suffixed `_v2`.

## How it works

It's the **same script** with the `--engrave` flag. Internally that flips one
line: feature pixels set the surface radius to `R - emboss` (recessed) instead
of `R + emboss` (raised). The result is still a single watertight solid
cylinder, just with grooves instead of bumps.

## Location

- Script: `C:\Users\nikil\3d-printed-playdoh-roller\playdoh_roller.py` (shared
  with v1; `--engrave` selects v2 behaviour)
- Decoration SVGs: `C:\Users\nikil\3d-printed-playdoh-roller\assets\`
- Outputs: written next to the script, named `preview_<name>_<theme>_v2.png`
  and `roller_<name>_<theme>_v2.stl`

## How to run

```
# v2 preview + STL
python playdoh_roller.py --name "Imogen" --theme shapes --engrave --preview --stl
```

Add `--engrave` to any normal invocation to get the v2 (recessed) version.
Without it you get the standard v1 (raised) roller.

### Parameters

Identical to v1 (`--name`, `--theme`, `--radius`, `--length`, `--emboss`,
`--ppm`, `--handles`) — see [[playdoh-roller]] for the full table and the themes
list (`bees_and_flowers`, `dinosaurs`, `shapes`, `cats`, `fruits`). The only
extra flag is `--engrave`.

## Preview

The v2 preview inverts the colours to show the raised result: the design appears
**light/raised** on a darker pressed background, titled "(v2 · raised imprint)".

## 3D printing

Same as v1 — exported **standing upright on its end**, prints with **no
supports** (each layer is a ring; the recesses are just missing material on the
outer wall, no overhangs). 0.15 mm layers, 40% infill, 3+ walls, brim for the
small circular footprint. PLA or PETG.

## Notes / when to use which

- Use **v1** for sunken designs (classic stamped-in look).
- Use **v2** for raised designs (the name/pictures pop UP out of the dough).
- Both are generated from the same code and assets, so any new theme added for
  v1 (drop SVGs in `assets/`, add to the `THEMES` dict) works for v2 too.
