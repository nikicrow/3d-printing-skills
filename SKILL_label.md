---
name: namelabel
description: Generate a cute, bubbly two-colour NAME KEYCHAIN LABEL — the child's name in a rounded/bubbly font raised on top of a contrasting "trace" border, with a clasp hole and an optional theme icon (bee, heart, star, ...). The printable geometry is a parametric OpenSCAD file (label.scad) so the SAME source is BOTH exported locally (STL / 3MF) AND uploadable to MakerWorld's Parametric Model Maker as a customisable multicolour model. Colours are split BY HEIGHT (border on the bottom band, name on the top band) to minimise second-colour filament waste. Companion to the playdoh-roller / stamp / scraper skills; reuses the same bundled icon SVGs.
---

# Two-Colour Name Keychain Label Generator

Makes a robust little **name tag / keychain** for a kid's school bag or a party
favour: the name in a **cute bubbly font** (Grandstander, Baloo 2, Bagel Fat One,
Titan One, Chewy, Lilita One, Bubblegum Sans) sits **raised on top** of a
contrasting rounded **"trace" border**, with a hole for a split-ring/clasp and an
optional **theme icon** (a flower on Ember's, a heart on Imogen's, ...).

There are **two interchangeable pipelines** for the same label design:

1. **MakerWorld pipeline** — the parametric OpenSCAD file
   [`label.scad`](label.scad), driven locally by [`namelabel.py`](namelabel.py)
   (fast colour preview PNG + `--stl` / `--3mf` export via OpenSCAD), and
   uploadable to MakerWorld's **Parametric Model Maker** so anyone can type a
   name, pick a font, colours and an icon — a remixable, multicolour model.
2. **Standalone pipeline** — [`playdoh_label.py`](playdoh_label.py), a pure
   `trimesh` generator like the roller/stamp/scraper (no OpenSCAD). It writes a
   **native multicolour 3MF** — one coloured part per filament, declared both as
   standard 3MF materials *and* as a Bambu/Orca `model_settings.config` — plus a
   plain STL and a colour preview. Reusable helpers live in
   `mesh_utils.build_mask_prism` / `mesh_utils.write_color_3mf`. Its outputs are
   `_mesh`-suffixed so the two pipelines never overwrite each other.

Both produce the same *design*; the sections below describe the parameters
(shared by both) and the MakerWorld flow.

> ⚠️ **Known bug: they do not produce the same SIZE.** `CAP_RATIO = 0.72`
> converts the requested cap height into a font size, but PIL and OpenSCAD do
> not mean the same thing by "size" — PIL takes it as the em, OpenSCAD as
> roughly the ascent. Measured with `letter_height = 16`, an `I` in Grandstander
> comes out **14.75 mm** from `playdoh_label.py` and **20.68 mm** from
> `label.scad`: a 40% divergence, and neither hits the requested 16 mm. Whole
> labels differ accordingly (Imogen + heart is 113 × 23 mm as a mesh, 144 × 34 mm
> from OpenSCAD). Until this is fixed, treat `--letter-height` as a relative
> dial, don't mix output from the two pipelines in one batch, and re-check the
> printed size before committing to a full run. Fixing it means calibrating a
> per-pipeline ratio from the font's real metrics (`fontTools` can read the OS/2
> `sCapHeight`), which will change the size of every label generated so far.

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
pip install numpy pillow pydantic svgpathtools --break-system-packages          # namelabel.py
pip install trimesh matplotlib scipy --break-system-packages                    # + playdoh_label.py
```

Plus **OpenSCAD** for `namelabel.py --stl` / `--3mf` (https://openscad.org).
`--preview` needs no OpenSCAD, and `playdoh_label.py` needs none at all.
**Colour inside a 3MF requires OpenSCAD 2024+** (older builds export a
single-colour mesh); MakerWorld's Parametric Model Maker uses a colour-capable
build, so the two `color()` parts come through there. On an older OpenSCAD, use
`playdoh_label.py --3mf` instead — it writes colour itself.

`scipy` is only used for the edge chamfer in the standalone pipeline; without
it `--bevel` silently becomes a no-op and the plate comes out square-edged.

## How to run

```
# fast colour preview PNG (no OpenSCAD needed):
python namelabel.py --name "Ember" --icon flower --preview

# print-ready files (needs OpenSCAD on PATH):
python namelabel.py --name "Imogen" --icon heart --font "Bagel Fat One" --stl
python namelabel.py --name "Ember"  --icon flower --3mf

# custom colours (top layer = letters, bottom layer = border):
python namelabel.py --name "Imogen" --name-color "#c0392b" --border-color "#ffffff" --preview
```

At least one of `--preview` / `--stl` / `--3mf` is required.

## Parameters (all optional CLI flags; defaults baked in)

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `Ember` | The name to print |
| `--font` | `Grandstander` | One of the 7 bundled bubbly fonts |
| `--icon` | `none` | Theme icon leading the name (`bee`, `heart`, `star`, `flower`, `paw`, `cat`, `apple`, `car`, `truck`, `banana`, `brontosaurus`, `trex`, `circle`, `square`, `triangle`) |
| `--name-color` | `#2b2b2b` | **Top** layer colour (the letters + icon) |
| `--border-color` | `#f2ead6` | **Bottom** layer colour (the trace/border) |
| `--letter-height` | `16` | Cap height of the letters, mm |
| `--border-width` | `3.0` | How far the border extends past the letters (trace thickness), mm |
| `--corner-round` | `1.5` | Rounding of the border outline (bubblier = higher), mm |
| `--border-h` | `2.4` | **Bottom** band thickness (border colour), mm |
| `--font-h` | `1.6` | **Top** band thickness (name colour), mm |
| `--bevel` | `0.3` | 45° chamfer on the **top** face of the plate rim *and* of the raised name, mm (0 = square). Takes the sharp arris off every edge a small hand touches. Both undersides stay square — see below. Free in `playdoh_label.py`; **expensive on old OpenSCAD** — see the render-cost note. |
| `--icon-scale` | `1.15` | Icon size relative to letter height |
| `--no-keychain` | (off) | Omit the clasp tab + hole |
| `--hole-d` | `5.0` | Clasp hole diameter, mm |
| `--hole-wall` | `2.5` | Ring wall between the hole and the tab edge, mm |
| `--smoothness` | `72` | Curve facets (higher = smoother, slower) |

Total thickness = `border_h + font_h` (default **4.0 mm** = 2.4 + 1.6). The
border plate is 50% thicker than the original 1.6 mm design, while the raised
name stays slimmer for a cleaner, less bulky print.

`--smoothness` applies to `namelabel.py` only; `playdoh_label.py` takes `--ppm`
instead (mask resolution in px/mm, default `8`). `label.scad` additionally
exposes `bevel_steps` (chamfer facets, default `1` — see below).

### Output file naming

The two pipelines share a naming scheme and are separated by a `_mesh` suffix,
so you can run both on the same name without either clobbering the other:

| | `namelabel.py` (OpenSCAD) | `playdoh_label.py` (trimesh) |
|---|---|---|
| Preview | `previews/labels/preview_label_<name>[_<icon>].png` | `previews/labels/preview_label_<name>[_<icon>]_mesh.png` |
| STL | `printable_files/labels/label_<name>[_<icon>].stl` | `printable_files/labels/label_<name>[_<icon>]_mesh.stl` |
| 3MF | `printable_files/labels/label_<name>[_<icon>].3mf` | `printable_files/labels/label_<name>[_<icon>]_mesh.3mf` |

### Bevel render cost (OpenSCAD only)

The chamfer is the one parameter that costs real render time, and only in the
OpenSCAD pipeline. `bevel_extrude` approximates it by unioning inset slabs, and
that boolean union is slow on the pre-2023 **CGAL** backend. Measured on
OpenSCAD **2021.01**, exporting `Imogen` + heart:

| | render | STL |
|---|---|---|
| `bevel = 0` (square) | 22 s | 2.9 MB |
| **`bevel = 0.3`, `bevel_steps = 1` — the default** | **69 s** | **7.2 MB** |
| `bevel = 0.6`, `bevel_steps = 1`, plate both faces | 105 s | 6.4 MB |
| `bevel = 0.6`, `bevel_steps = 2`, plate both faces | 355 s | 9.9 MB |

Two things drive that cost, and both are one slab per chamfered face per step.
Going **top-face-only** removed a slab from the plate, which more than paid for
adding one to the name — so the current default chamfers *more* of the model in
*less* time than the earlier plate-only setting did. Extra `bevel_steps` are the
expensive axis: each one roughly triples the render, which is why it defaults to
**1**, a single 45° facet that is indistinguishable at 0.3 mm.

(Re-measured on a second 2021.01 machine: 14 s at `bevel = 0` vs 78 s at
`bevel = 0.6, bevel_steps = 1`. Absolute times are machine-dependent, but the
**~5× cost of turning the chamfer on** is consistent, and the exported geometry
is identical either way.)

OpenSCAD **2023+** and MakerWorld use the **Manifold** backend, where these
unions are dramatically cheaper. That is still **unverified**: modern OpenSCAD
ships only from `files.openscad.org`, which this environment's egress policy
blocks (HTTP 403), and the newest build in Ubuntu's archive — and the newest
release on OpenSCAD's GitHub — is 2021.01, which has no Manifold backend at all
(no `--enable=manifold`). So treat it as an assumption: when you upload to the
Parametric Model Maker, render once with the defaults, and if it times out set
`bevel = 0` — the chamfer is a nicety, not structural.

The standalone pipeline has no such problem: `build_mask_prism` chamfers by
ramping cap vertices along a distance transform, which adds **no** triangles and
no measurable time, so `playdoh_label.py --bevel` is always free.

## Printing the two colours (Bambu Studio)

The label is a clean height split, so there are two easy routes:

- **Single extruder (A1 / P1 / X1 with no AMS)** — import the **STL**, add **one
  filament change at `Z = border_h`** (default **2.4 mm**, printed on export).
  Everything below is the border colour, everything above is the name colour.
- **AMS / multi-filament** — use `playdoh_label.py --3mf` (any OpenSCAD, or
  none). The 3MF holds two parts, `border` and `name`, already pinned to
  extruder 1 and 2 via Bambu's `model_settings.config`, with standard 3MF
  materials as a fallback for other slicers. No painting, no manual Z. The
  OpenSCAD route also works but needs **2024+** (or MakerWorld) for colour.

### Is the colour actually valid? (`test_label_3mf.py`)

Bambu Studio itself still has not been run against these files — it was not
available in the build environment. But "round-trips through `trimesh`" was a
weak check, because `trimesh` also *wrote* the file, so it could not catch a
malformed package. The 3MFs are now read back with **lib3mf**, the 3MF
Consortium's reference implementation and the parser Bambu Studio's "Standard
3MF File Color Parsing" is built on:

```bash
pip install lib3mf
python test_label_3mf.py                 # checks every 3MF in printable_files/labels/
```

In lib3mf **strict** mode each file parses with zero warnings, and the reference
parser independently resolves **two distinct base materials** (`border`
`#F2EAD6`, `name` `#2B2B2B`), each mesh part correctly bound to one of them,
both parts manifold-and-oriented, assembled under a single build item — plus the
Bambu `model_settings.config` pinning the parts to extruder 1 and 2.

That check caught a real bug: the `BambuStudio:3mfVersion` metadata used a
namespace prefix that was never declared on the `<model>` element, which the 3MF
core spec forbids. lib3mf refused to load the file at all in strict mode. The
writer now declares `xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"`
(what Bambu Studio's own exports carry), and all 13 committed labels were
regenerated.

> So: verified conformant by the reference implementation, not yet eyeballed in
> Bambu Studio. If it ever imports single-colour anyway, the parts and their
> extruder assignments are in `Metadata/model_settings.config` inside the zip —
> that is the file to check first.

Print settings: flat on the bed (already oriented, name up), **no supports**
(everything is a flat extrusion above a flat base), 0.15–0.20 mm layers, 3+
walls, PLA or PETG (PETG is tougher for a bag tag). Keep `border_h` a multiple
of your layer height so the colour change lands exactly on a layer boundary.

## Theme icons

The icon follows the name (`[hole] [NAME] [icon]`) with a compact gap of about
2 mm at the default border width. It is imported from
`assets/<icon>.svg` (the same open-licensed silhouettes the roller/stamp use),
normalised to the letter height, and raised in the name colour on top of the
border plate. To add an icon: drop a bold silhouette SVG in `assets/`, record it
in `assets/ATTRIBUTION.md`, and add its name to the `icon` lists in **all three**
of `label.scad`, `namelabel.py` and `playdoh_label.py`. An SVG sitting in
`assets/` that is missing from those lists simply won't be offered.

Then add a row to **`icon_vb_table` in `label.scad`** with the SVG's `viewBox`
side. OpenSCAD imports an SVG at its viewBox units, so this is what normalises
the art to the letter height — a 128-unit icon left to the 24 default comes out
over five times too big and swallows the whole label. The Python pipelines need
no such table: `rasterize_svg` reads each file's viewBox itself.

The bundled icons are a mix of `128` (apple, banana, car, truck, trex,
brontosaurus), `32` (bee), `24` (cat, circle, flower, heart, square, star,
triangle) and `15` (paw), so don't assume.

> **The two pipelines don't composite icons identically.** `rasterize_svg` is
> called with `mode="union"`, flattening every sub-path into one solid
> silhouette. OpenSCAD's `import()` has no such option and fills by the SVG's own
> rule, so the multi-part Noto emoji art (apple, banana, car, truck, **trex**,
> **brontosaurus**) keeps its internal colour-separation paths as holes and reads
> as a fussier, more fragmented shape — most visibly on the dinosaurs. The
> single-path 24-unit icons (heart, star, circle, square, triangle, cat, flower)
> and the bee look the same either way. For a MakerWorld upload, prefer the
> single-path icons, or pre-flatten the art to one path before bundling it.

## Fonts

Seven bundled bubbly fonts live in `assets/fonts/` (all OFL/Apache — see the
`ATTRIBUTION.md` there). OpenSCAD resolves them by **family name**, so the local
runner sets `OPENSCAD_FONT_PATH` to that folder automatically. To add a font:
drop the `.ttf`, extend `FONTS` in `namelabel.py` **and** `playdoh_label.py`, add
it to the `font` dropdown in `label.scad`, and record it.

OpenSCAD cannot instance a **variable** font, so `Grandstander.ttf` is a static
Bold instance baked out of the upstream variable font. Do the same for any other
variable font you want to bundle.

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
`validate_assignment=True`, hex-colour + font/icon-choice validators), and both
pipelines carry the same one so their flags stay in step.

In `namelabel.py` the geometry is **not** built in Python — it is delegated to
`label.scad`, driven via `openscad -o <out> -D <param>=<value> ...`. The fast
preview is rendered directly in Pillow (a faithful raster mock-up of the same
`[hole] [NAME] [icon]` layout, offset border and connector web) so you can
iterate on names/fonts/colours without launching OpenSCAD.

`playdoh_label.py` builds the geometry itself. It rasterises the same layout to
two boolean masks — `content` (letters + icon) and `base` (the offset border,
tab and connector, minus the clasp hole) — and extrudes each with
`mesh_utils.build_mask_prism`, which walks the mask's corner grid and emits caps
plus a wall at every on/off boundary. That yields a watertight solid with real
through-holes and no booleans at all. The **chamfer** rides on the same grid: a
`scipy` distance transform gives each corner its distance to the nearest
silhouette edge, and the caps are ramped down by `bevel - distance`, so a 45°
edge costs one distance transform and **zero** extra triangles.

## How it works (implementation notes)

- **Layout** is left-anchored: the keychain hole sits on the left, followed by
  the name and then the optional icon. The Python pipelines use the rendered
  text bounds for exact placement. For compatibility with older OpenSCAD builds
  that lack `textmetrics()`, `label.scad` uses a calibrated name-width estimate.
- **Border** = a rounded outward `offset()` of the name (+ icon) silhouette:
  `offset(r=corner_round) offset(delta=border_width-corner_round)`.
- **Connectivity** is guaranteed by a thin **connector spine** along `y = 0`
  that runs beneath the full name and stops near the trailing icon's centre.
  Once offset by the border width, it fuses the tab, every glyph and the icon into
  one plate—even when an SVG has transparent inset around its visible artwork
  (verified: every export is a single connected body).
- **Two colours** are two top-level objects: `color(border_color) base_part()`
  (the plate, `0..border_h`) and `color(name_color) name_part()` (letters+icon,
  `border_h..border_h+font_h`). The mesh pipeline mirrors this exactly, as two
  mask prisms overlapping by 0.01 mm so they fuse into one printed body while
  staying separable as two coloured 3MF parts.
- **Icon orientation**: OpenSCAD auto-orients an imported SVG upright, so the
  icons must *not* be Y-mirrored to compensate. (They once were, which flipped
  every icon upside down.)
- **Chamfers are top-face only, on both bands.** The undersides are square on
  purpose: a chamfer under the plate would shrink the first-layer footprint and
  cost bed adhesion, and one under the name would taper the letters away from
  the plate they stand on, leaving a groove around every glyph. `build_mask_prism`
  takes `bevel` as either a scalar (both caps) or a `(bottom, top)` pair, and
  `bevel_extrude` in `label.scad` takes matching `do_bottom` / `do_top` flags.
  Keep the chamfer well under half the stroke width. At the default 16 mm cap
  height, Grandstander strokes measure ~1.8 mm across (0.88 mm from centre to
  edge, median), so a 0.3 mm chamfer still leaves ~1.2 mm of full-height top
  face on the thinnest stroke. Push `--bevel` past ~0.8 mm and thin strokes
  start meeting in a ridge instead of a flat top, and fine icon detail (the
  bee's legs and antennae) tapers away entirely.
