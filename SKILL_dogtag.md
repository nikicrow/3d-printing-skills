---
name: dogtag
description: Generate a two-colour PET COLLAR TAG — a rounded plaque with the pet's name, phone number or a message INLAID FLUSH into BOTH faces, a chamfered collar hole and softened edges all round. Text comes from real glyph outlines (not a raster), auto-wraps and auto-sizes to fill the tag, and the back face is mirrored so it reads correctly when the tag is flipped. Exports a two-filament 3MF plus STLs; the body STL alone is a single-colour engraved tag. Companion to the namelabel / playdoh-roller / stamp / scraper skills.
---

# Two-Colour Pet Collar Tag Generator

Makes a collar tag that reads from **either side**: a rounded baby-blue plaque
with black lettering **inlaid flush** into the front *and* the back, a chamfered
hole for the collar ring, and a 45° chamfer on every outside edge.

## Why it is not the name label

[`SKILL_label.md`](SKILL_label.md) splits its two colours **by height** — a
border plate with the name standing proud on top. That is right for a bag tag,
but a collar tag gets dragged through grass, chewed and knocked against a bowl,
and it has to read from whichever side happens to be facing out. So this tool
splits the colours **in plan** instead:

- the plaque is one solid of the body colour with the lettering **recessed**
  `text_depth` into both faces, and
- the letters are separate solids of the text colour that fill those recesses
  **exactly flush** (verified: removed volume == inlay volume to 1e-5 mm³).

Nothing stands proud, so there is nothing to snag, wear off or catch a paw.

## Location

- Generator: `dogtag.py`
- Fonts: `assets/fonts/*.ttf` (the same seven bubbly faces the name label uses)
- Outputs auto-file next to the script regardless of working directory:
  previews → `previews/dogtags/`, printable files → `printable_files/dogtags/`.

## Dependencies

```
pip install numpy pillow trimesh scipy shapely manifold3d matplotlib pydantic \
    --break-system-packages
```

`manifold3d` is the one dependency the other tools in this repo do without: the
two face recesses are real mesh booleans. Everything else here is boolean-free.

## How to run

```
# all outputs (preview + STLs + 3MF) — the default when no output flag is given:
python dogtag.py --front "Kip" --back "0450 572 596" --stem kip_name

# a long message: grow the tag so it all fits on one face, and place the
# breaks yourself when the auto-wrapper orphans a word
python dogtag.py --front "I'm not good\nat meeting\nnew people,\nplease call\nmy dad" \
                 --height 44 --stem kip_shy

# limit the outputs, and recolour
python dogtag.py --front "Bosco" --preview \
                 --body-color "#f7c6d9" --text-color "#241f20"
```

`--front` is required; everything else has a default. `--preview` / `--stl` /
`--3mf` each restrict the run to that output.

## Parameters

| Flag | Default | Meaning |
|---|---|---|
| `--front` | *(required)* | Front-face text. `\n` forces a line break |
| `--back` | *(empty)* | Back-face text; mirrored in the model so it reads right when flipped |
| `--stem` | *(from front text)* | Output filename stem override |
| `--font` | `Grandstander` | One of the seven bundled bubbly fonts |
| `--body-color` | `#89CFF0` | Plaque colour (baby blue) |
| `--text-color` | `#1A1A1A` | Inlaid lettering colour |
| `--width` | `40` | Tag width, mm |
| `--height` | `30` | Tag height, mm |
| `--thickness` | `3.0` | Total thickness, mm |
| `--text-depth` | `0.6` | Inlay depth **per face**, mm |
| `--corner-radius` | `6.0` | Outline rounding, mm |
| `--bevel` | `0.5` | 45° chamfer on both faces of the rim *and* both mouths of the hole, mm |
| `--hole-d` | `4.5` | Collar hole diameter, mm |
| `--hole-wall` | `2.5` | Material between the hole and the top edge, mm |
| `--letter-height` | `11` | **Upper limit** on row height, mm — text shrinks below this to fit |
| `--line-gap` | `0.16` | Leading, as a fraction of a row height |
| `--pad-x` / `--pad-y` | `3.5` / `3.0` | Margin around the text block, mm |
| `--max-lines` | `6` | Most lines the auto-wrapper may use |

The hole sits **top-centre** so the tag hangs level off the collar ring, and the
text box automatically stops short of it (`hole_clear_mm`, 1.2 mm).

### Output files

| | file |
|---|---|
| Preview | `previews/dogtags/<stem>_preview.png` (front, back-as-flipped, side profile) |
| Two-colour 3MF | `printable_files/dogtags/<stem>.3mf` |
| Combined STL | `printable_files/dogtags/<stem>.stl` |
| Part STLs | `printable_files/dogtags/<stem>_body.stl`, `<stem>_text.stl` |

## Text layout

Type the message as one string and let the tool break it. For every line count
from 1 to `--max-lines` it balances the words with an O(m²n) DP that minimises
the *widest* line — a greedy fill would stuff the first line and leave a stub,
and that stub is what forces the whole block to shrink — then keeps whichever
line count yields the largest type that still fits the box. Explicit `\n`
switches the wrapper off and uses your breaks verbatim.

Line spacing runs on a fixed row grid measured from `Hgjp`, so baselines stay
even whether or not a given line has an ascender or descender; the finished
block is then re-centred on its own ink so a last line with no descender does
not sit high.

Glyph outlines come from the TTF via `matplotlib.textpath`, and the counters
(the hole in an `o`) are resolved by symmetric-differencing the contours —
which *is* TrueType's even-odd fill rule, so no containment test is needed.
That means smooth curves rather than the stair-stepped raster the Play-Doh
tools use, and meshes measured in tens of thousands of triangles, not millions
(a five-line message tag is ~31 k faces / 0.3 MB).

**Watch the stroke width.** The type shrinks to fit, so a long message on a
small tag can thin the strokes below what the nozzle can resolve as a separate
colour. A five-line message on a 40 × 44 mm tag lands at a 5.4 mm row height
with a ~0.7 mm mean stroke — a comfortable two perimeters at 0.4 mm. Every run
prints the fitted stroke width per face and warns below 0.5 mm, where the colour
separation starts to break up: shorten the text, move some of it to the other
face, or grow the tag. Past a point extra height stops helping — once the widest
*line* is what limits the size, only a wider tag or a different break-up gains
anything.

## Geometry

The plaque is **lofted analytically**, not rasterised. Four levels — inset
bottom, full, full, inset top — are generated at a fixed vertex count so
consecutive rings correspond one-to-one, and the walls close into a watertight
solid with no booleans. That one loft produces the whole chamfer: the rim is
inset by `bevel` at both faces and the hole is `bevel` wider at both mouths, so
**no edge on the finished tag is a sharp arris**. The end caps are earcut
triangulations of the annulus between the outer ring and the hole ring, matched
back onto the loft's own vertices so the solid closes (a KD-tree check fails
loudly if the triangulator ever introduces a new point).

The two recesses are then subtracted with `manifold3d`. The cut solids overshoot
the face they open onto by 0.5 mm: a boolean whose operands share a face plane
is the classic way to get a sliver or a dropped facet, and the overshoot costs
nothing because that volume is outside the tag anyway.

Back-face text is mirrored about the tag's vertical centre line, so it reads the
right way round once the tag is flipped on the collar. The hole is top-centre
and the outline is symmetric, so only the text needs mirroring.

`mesh_utils.build_mask_prism` gained a `bevel_mask=` argument for this tool —
it lets a chamfer follow a mask *other* than the prism's own, so a rim can be
softened while inlaid letters stay square and flush. `dogtag.py` ended up
outline-based and does not use it, but it is there for any raster-based inlay.

## Printing (Bambu Studio)

Flat on the bed, no supports — every face is a flat extrusion.

- **AMS / multi-filament** — open `<stem>.3mf`. It is one object of two parts,
  `body` on extruder 1 and `text` on extruder 2, via Bambu's
  `model_settings.config` plus standard 3MF base materials as a fallback. No
  painting, no manual Z.
- **Single extruder (no AMS)** — a flush inlay puts two colours in the *same*
  layer, so a filament change cannot do it. Print `<stem>_body.stl` on its own
  instead: the identical geometry, minus the inlay, is a single-colour tag with
  **engraved** text. (Loading `<stem>.stl` gives a solid tag with no readable
  text — the inlay fills the recesses.)

Settings: 0.15–0.20 mm layers, 3+ walls, 40 %+ infill. **PETG, not PLA** — a
collar tag lives outdoors and PLA creeps in a hot car. Keep `text_depth` a
multiple of the layer height so the colour change lands on a layer boundary
(0.6 mm = 4 × 0.15 or 3 × 0.20).

The bottom face is a two-colour first layer, which is the easiest colour
transition there is; the top face is a two-colour flat inlay, equally easy.
Nothing bridges, nothing overhangs.

## Verifying output

`dogtag.py` prints the chosen line breaks and row height for each face, and
whether each mesh is watertight. Both committed tags export watertight and pass
the repo's reference-parser check:

```bash
python test_label_3mf.py printable_files/dogtags/*.3mf
```

That reads the 3MF back with **lib3mf** in strict mode and asserts two distinct
base materials, each part bound to one and manifold-and-oriented, a single build
item, and the Bambu extruder assignments — the same check the name labels pass.
Bambu Studio itself has not been run against these files; see
[`SKILL_label.md`](SKILL_label.md) for what that caveat covers.

> **Status: geometry verified, not yet print-verified.** Watertight, chamfered,
> volume-exact inlay, valid two-colour 3MF. No physical print has been made yet,
> so treat the first tag as a test of stroke width and hole size against your
> own printer and collar ring.
