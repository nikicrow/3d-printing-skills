---
name: namelabel
description: Generate a cute, bubbly two-colour NAME KEYCHAIN LABEL — the child's name in a rounded/bubbly font raised on top of a contrasting "trace" border, with a clasp hole and an optional theme icon (bee, heart, star, ...). The printable geometry is a parametric OpenSCAD file (label.scad) so the SAME source is BOTH exported locally (STL / 3MF) AND uploadable to MakerWorld's Parametric Model Maker as a customisable multicolour model. Colours are split BY HEIGHT (border on the bottom band, name on the top band) to minimise second-colour filament waste. Companion to the playdoh-roller / stamp / scraper skills; reuses the same bundled icon SVGs.
---

# Two-Colour Name Keychain Label Generator

Makes a robust little **name tag / keychain** for a kid's school bag or a party
favour: the name in a **cute bubbly font** (Baloo 2, Bagel Fat One, Titan One,
Chewy, Lilita One, Bubblegum Sans) sits **raised on top** of a contrasting
rounded **"trace" border**, with a hole for a split-ring/clasp and an optional
**theme icon** (a bee on Ember's, a heart on Imogen's, ...).

There are **two interchangeable pipelines** for the same label design:

1. **MakerWorld pipeline** — the parametric OpenSCAD file
   [`label.scad`](label.scad), driven locally by [`namelabel.py`](namelabel.py)
   (fast colour preview PNG + `--stl` / `--3mf` export via OpenSCAD), and
   uploadable to MakerWorld's **Parametric Model Maker** so anyone can type a
   name, pick a font, colours and an icon — a remixable, multicolour model.
2. **Standalone pipeline** — [`playdoh_label.py`](playdoh_label.py), a pure
   `trimesh` generator like the roller/stamp/scraper (no OpenSCAD). It writes a
   **native multicolour 3MF** with per-triangle materials that Bambu Studio
   parses (Standard 3MF colour parsing), plus a plain STL and a colour preview.
   Reusable helpers live in `mesh_utils.build_mask_prism` /
   `mesh_utils.write_color_3mf`.

Both produce the identical design; the sections below describe the parameters
(shared by both) and the MakerWorld flow.

> **Waste-optimised two colours, by height.** The bottom band
> (`0 .. border_h`) is the border colour: the full rounded outline + keychain
> tab. The top band (`border_h .. border_h+font_h`) is the name colour: *only*
> the raised letters + icon. The second colour therefore exists only where the
> letters are, in a thin top layer, so it uses almost no extra filament. The
> clean split also means a **single-extruder Bambu prints it with ONE filament
> change** at `Z = border_h`.

> **Status: geometry print-ready & verified as a single connected solid.** Each
> label exports as one watertight, single-body piece (a connector web in the
> base layer fuses the tab, icon and name so nothing prints loose). Real-print
> tuning of the exact heights is expected on first run.

## Location

- OpenSCAD source: `label.scad`  (upload THIS + the `assets/` folder to MakerWorld)
- Local driver: `namelabel.py`
- Fonts: `assets/fonts/*.ttf` (bundled, open-licensed — see its `ATTRIBUTION.md`)
- Icons: `assets/<icon>.svg` (shared with the roller/stamp skills)
- Outputs auto-file next to the script regardless of working directory:
  previews → `previews/labels/`, printable files → `printable_files/labels/`.

## Dependencies

```
pip install numpy pillow pydantic svgpathtools --break-system-packages
```

Plus **OpenSCAD** for `--stl` / `--3mf` (https://openscad.org). `--preview`
needs no OpenSCAD. **Colour inside a 3MF requires OpenSCAD 2024+** (older builds
export a single-colour mesh); MakerWorld's Parametric Model Maker uses a
colour-capable build, so the two `color()` parts come through there.

## How to run

```
# fast colour preview PNG (no OpenSCAD needed):
python namelabel.py --name "Ember" --icon bee --preview

# print-ready files (needs OpenSCAD on PATH):
python namelabel.py --name "Imogen" --icon heart --font "Bagel Fat One" --stl
python namelabel.py --name "Ember"  --icon bee   --3mf

# custom colours (top layer = letters, bottom layer = border):
python namelabel.py --name "Imogen" --name-color "#c0392b" --border-color "#ffffff" --preview
```

At least one of `--preview` / `--stl` / `--3mf` is required.

## Parameters (all optional CLI flags; defaults baked in)

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `Ember` | The name to print |
| `--font` | `Baloo 2` | One of the 6 bundled bubbly fonts |
| `--icon` | `none` | Theme icon leading the name (`bee`, `heart`, `star`, `flower`, `paw`, `cat`, `apple`, `car`, `truck`, `banana`) |
| `--name-color` | `#2b2b2b` | **Top** layer colour (the letters + icon) |
| `--border-color` | `#f2ead6` | **Bottom** layer colour (the trace/border) |
| `--letter-height` | `16` | Cap height of the letters, mm |
| `--border-width` | `3.0` | How far the border extends past the letters (trace thickness), mm |
| `--corner-round` | `1.5` | Rounding of the border outline (bubblier = higher), mm |
| `--border-h` | `1.6` | **Bottom** band thickness (border colour), mm |
| `--font-h` | `2.0` | **Top** band thickness (name colour), mm |
| `--bevel` | `0.6` | 45° chamfer on the plate's top/bottom edges, mm (0 = square). Eases printing (less elephant-foot, no sharp arris). Fast on OpenSCAD 2023+/MakerWorld; slow on the old 2021 CGAL backend. |
| `--icon-scale` | `1.15` | Icon size relative to letter height |
| `--no-keychain` | (off) | Omit the clasp tab + hole |
| `--hole-d` | `5.0` | Clasp hole diameter, mm |
| `--hole-wall` | `2.5` | Ring wall between the hole and the tab edge, mm |
| `--smoothness` | `72` | Curve facets (higher = smoother, slower) |

Total thickness = `border_h + font_h` (default **3.6 mm** = 1.6 + 2.0) — minimal
but robust enough to survive a school bag. Bump both a little for more strength.

### Output file naming

- Preview: `previews/labels/preview_label_<name>[_<icon>].png`
- STL: `printable_files/labels/label_<name>[_<icon>].stl`
- 3MF: `printable_files/labels/label_<name>[_<icon>].3mf`

## Printing the two colours (Bambu Studio)

The label is a clean height split, so there are two easy routes:

- **Single extruder (A1 / P1 / X1 with no AMS)** — import the **STL**, add **one
  filament change at `Z = border_h`** (default **1.6 mm**, printed on export).
  Everything below is the border colour, everything above is the name colour.
- **AMS / multi-filament** — export the **3MF from OpenSCAD 2024+** (or generate
  on MakerWorld). It contains two parts, `border` and `name`; assign a filament
  to each. No painting, no manual Z.

Print settings: flat on the bed (already oriented, name up), **no supports**
(everything is a flat extrusion above a flat base), 0.15–0.20 mm layers, 3+
walls, PLA or PETG (PETG is tougher for a bag tag). Keep `border_h` a multiple
of your layer height so the colour change lands exactly on a layer boundary.

## Theme icons

The icon leads the name (`[hole] [icon] [NAME]`). It is imported from
`assets/<icon>.svg` (the same open-licensed silhouettes the roller/stamp use),
normalised to the letter height, and raised in the name colour on top of the
border plate. To add an icon: drop a bold silhouette SVG in `assets/`, record it
in `assets/ATTRIBUTION.md`, and add its name to the `icon` lists in both
`label.scad` and `namelabel.py` (plus its viewBox size in `icon_vb` /
`ICON_VB` if it isn't 24×24).

## Fonts

Six bundled bubbly fonts live in `assets/fonts/` (all OFL/Apache — see the
`ATTRIBUTION.md` there). OpenSCAD resolves them by **family name**, so the local
runner sets `OPENSCAD_FONT_PATH` to that folder automatically. To add a font:
drop the `.ttf`, extend `FONTS` in `namelabel.py` and the `font` dropdown in
`label.scad`, and record it.

## Uploading to MakerWorld (parametric multicolour model)

1. Zip **`label.scad` together with the `assets/` folder** (fonts + icon SVGs),
   keeping the relative paths (`assets/fonts/...`, `assets/heart.svg`).
2. In MakerWorld → **Parametric Model Maker**, upload it. The `/* [section] */`
   comments and `// [choices]` become the customiser UI; `name_color` /
   `border_color` (tagged `// color`) become colour pickers.
3. Because the two top-level `color()` objects export as separate parts, the
   preview and the sliced model come out **multicolour** automatically.

Keep the number of distinct colours small (here: two) and the mesh modest — the
height-split design is deliberately light, which is exactly what the Parametric
Model Maker likes.

## Architecture

Mirrors the Play-Doh tools: all parameters live in a validated
**`LabelConfig(BaseModel)`** pydantic model (`extra="forbid"`,
`validate_assignment=True`, hex-colour + font/icon-choice validators). The
geometry, however, is **not** built in Python — it is delegated to `label.scad`,
which `namelabel.py` drives via `openscad -o <out> -D <param>=<value> ...`. The
fast preview is rendered directly in Pillow (a faithful raster mock-up of the
same `[hole] [icon] [NAME]` layout, offset border and connector web) so you can
iterate on names/fonts/colours without launching OpenSCAD.

## How it works (implementation notes)

- **Layout** is left-anchored: the keychain hole and the icon (fixed, known
  sizes) sit on the left; the name grows to the right into empty space. Nothing
  needs to measure text width, so the model renders identically on MakerWorld's
  OpenSCAD and on older local builds.
- **Border** = a rounded outward `offset()` of the name (+ icon) silhouette:
  `offset(r=corner_round) offset(delta=border_width-corner_round)`.
- **Connectivity** is guaranteed by a thin **connector spine** along `y = 0`
  that, once offset by the border width, becomes a smooth neck fusing the tab,
  icon and first letter into ONE plate — independent of glyph bearings or icon
  spacing (verified: every export is a single connected body).
- **Two colours** are two top-level objects: `color(border_color) base_part()`
  (the plate, `0..border_h`) and `color(name_color) name_part()` (letters+icon,
  `border_h..border_h+font_h`).
