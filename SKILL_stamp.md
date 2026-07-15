---
name: playdoh-stamp
description: Generate a parametric, toddler-friendly Play-Doh / clay STAMP (preview PNG and printable STL) — a compact ~5cm slab with a short grippy cylinder handle and chamfered edges that presses a child's NAME (and/or an SVG motif) into the dough. Companion to the playdoh-roller skills; reuses the same fonts, icon assets, and watertight STL pipeline.
---

# Play-Doh Name & Motif Stamp Generator

Generates a custom press-stamp for Play-Doh / clay: a compact (~5 cm wide) slab
with a short, grippy **cylinder handle** on the back (easy for a toddler to
grasp) and **chamfered edges** (safer to hold, cleaner to print), carrying a
kid's **name** (parametric text) and/or an **SVG motif** on the stamping face.
Kids press it into a flat slab of dough to stamp their creations with their
name. The name's **initial letter is raised on the top of the cylinder handle**
(readable from above) so it's easy to tell whose stamp is whose. Outputs a flat
PNG preview of the dough imprint, or a printable STL of the actual stamp.

Companion to [[playdoh-roller]] / [[playdoh-roller-v2]] — it **reuses the same**
chunky fonts, the same open-licensed silhouette icons in `assets/` (see
`assets/ATTRIBUTION.md`), and the same watertight displaced-grid STL technique
that has print-verified on the Bambu Lab A1.

Everything on the stamping face is **automatically mirrored** so the pressed
dough reads the right way round.

## Location

- Script: `C:\Users\nikil\3d-printed-playdoh-roller\playdoh_stamp.py`
  (git mirror: `3d-printing-skills\playdoh_stamp.py`)
- Motif SVGs: `C:\Users\nikil\3d-printed-playdoh-roller\assets\` (shared with the
  rollers), plus any SVG the user uploads/approves (`--svg` / `--icon` accept an
  absolute path too).
- Outputs are auto-filed next to the script, regardless of the working
  directory it is invoked from: previews go to `previews\stamps\` and STLs to
  `printable_files\stamps\` (the folders are created automatically).

## Dependencies

```
pip install trimesh numpy pillow matplotlib svgpathtools pydantic --break-system-packages
```

Pure local Python 3 — no native cairo, no shapely, no boolean/manifold backend,
no internet at run time. `trimesh` is only needed for `--stl`. It shares the
refactored modules with the roller: it imports `rasterize_svg` / `load_font`
from `svg_processing.py` and `build_slab_relief` / `dome_knob` from
`mesh_utils.py`, so keep `playdoh_stamp.py`, `svg_processing.py` and
`mesh_utils.py` side by side.

## How to run

```
# Preview the dough imprint (how the name will look pressed in the dough):
python playdoh_stamp.py --name "Ember" --preview

# Printable STL (face-down, no supports, grippy cylinder on top):
python playdoh_stamp.py --name "Ember" --stl

# Name + little icon above it + a framing border, both outputs:
python playdoh_stamp.py --name "Max" --icon apple.svg --border --preview --stl

# Single-motif picture stamp from any approved SVG (no name), round plate:
python playdoh_stamp.py --svg assets/flower.svg --shape circle --stl
```

At least one of `--preview` / `--stl` is required, and at least one of
`--name` / `--svg`.

## Imprint modes (`--imprint`) — the key design choice

| Mode | Dough result | On the stamp | Printability |
|---|---|---|---|
| `raised` (default) | Name stands **UP** out of the dough (embossed) | Name is **engraved** into a solid raised plateau | **Best** — the whole face is one solid surface, perfect first layer |
| `indented` | Name pressed **IN** to the dough (debossed / seal look) | **Raised mirrored letters** on the face | Letters print as small first-layer islands — **use a brim** |

Default is `raised` because it is the most reliable print (no thin islands) and
looks great for toddlers (the name pops up out of the dough).

## Parameters (all optional CLI flags; defaults baked in)

| Flag | Default | Meaning |
|---|---|---|
| `--name` | — | Name on the stamp (omit for a motif-only stamp with `--svg`) |
| `--svg` | — | Approved/uploaded SVG for a single big motif, or used with `--icon` |
| `--icon` | — | Small SVG placed above the name (e.g. `apple.svg`, `star.svg`, `flower.svg`) |
| `--imprint` | `raised` | `raised` (pop-up) or `indented` (pressed-in) — see table above |
| `--shape` | `rect` | Plate footprint: `rect` or `circle` (circle is nice for single motifs) |
| `--handle` | `cylinder` | Back grip: `cylinder` (toddler grip), `knob` (dome), `bar`, or `none` |
| `--border` | off | Add a framing border around the content |
| `--letter-height` | `8.5` | Cap height of the name, mm (tuned so names land ~5 cm wide) |
| `--margin` | `6` | Solid border of plate around the content, mm |
| `--thickness` | `4` | Solid slab thickness above the deepest relief, mm |
| `--depth` | `1.0` | How deep the name is engraved / raised, mm (deeper packs dough in and sticks) |
| `--edge-chamfer` | `1.0` | 45° bevel on the plate's outer top/bottom edges, mm |
| `--cylinder-radius` | `11` | Cylinder grip radius, mm (22 mm dia) |
| `--cylinder-height` | `18` | Cylinder grip height, mm |
| `--no-initial` | off | Don't raise the name's initial letter on the handle top |
| `--initial` | — | Override the handle-top letter (default: name's first char) |
| `--top-relief` | `1.2` | How far the handle-top initial bumps out, mm |
| `--knob-radius` | `11` | Dome-knob (or bar) radius, mm (`--handle knob`/`bar`) |
| `--knob-squash` | `0.75` | Dome height = radius × squash (flatter = comfier) |
| `--icon-fraction` | `0.9` | Icon height relative to letter height |
| `--border-width` | `2.5` | Framing-border line width, mm |
| `--ppm` | `6` | Heightmap resolution, px/mm (6 = compact files; ≥10 for crisp icons) |

### Output file naming

- Preview: `previews/stamps/preview_stamp_<name>.png` (name lowercased, spaces →
  `_`; motif-only uses the SVG's basename)
- STL: `printable_files/stamps/stamp_<name>.stl` — `indented` mode appends `_indented`

## What the preview PNG shows

The stamping face rendered as the **dough imprint** (correctly readable, not
mirrored): Play-Doh cream/beige with the name/motif region highlighted. `raised`
mode shows the name light (popped up); `indented` shows it darker (pressed in).
Title and caption are baked into the image.

## 3D printing settings (Bambu Studio)

- **Orientation**: the STL is exported **face-down** — stamping face flat on the
  bed, handle pointing **up**. Print exactly as oriented; the STL already sits on
  `z = 0`.
- **Supports**: **none**. The cylinder grip prints as stacked rings and the
  slab's edges are 45° chamfers — no overhangs.
- **Layer height**: 0.15 mm for crisp letters (0.20 mm acceptable).
- **Walls / infill**: 3+ walls, 15–20 % infill is plenty — stamps take little
  force.
- **First layer**: slow it down; a short **brim** helps adhesion. A brim is
  effectively required in `indented` mode (the letters are small islands).
- **Material**: PLA is fine for Play-Doh (non-edible modelling compound); wash
  before/after play.

## Architecture

Matches the refactored roller (`origin/main`): all tunable parameters live in a
validated **`StampConfig(BaseModel)`** pydantic model (`extra="forbid"`,
`validate_assignment=True`, `Field(gt=0)` ranges, a `model_validator` requiring
a name and/or svg). Bad inputs raise `ValidationError`, turned into a concise
CLI error — a misconfigured run fails fast instead of producing a bad STL. The
generic work is delegated to the shared, project-agnostic modules:

- `svg_processing.py` → `rasterize_svg`, `load_font` (identical to the roller's)
- `mesh_utils.py` → `build_slab_relief` (flat watertight slab from a relief
  heightmap, with optional 45° edge chamfers), `grip_cylinder` (toddler cylinder
  handle) and `dome_knob` (alternative hemisphere handle) — all added alongside
  the roller's `build_roller_mesh` etc.

`playdoh_stamp.py` itself only holds stamp-specific layout, colouring and CLI.

## How it works (implementation notes)

- **Face heightmap** (`build_face`): renders the name in a chunky font at a
  target cap height (iterative font-size solve, same approach as the roller),
  optionally stacks a small icon above it and/or draws a rounded-rect / circle
  border. Letter height (default 8.5 mm) is tuned so names land ~5 cm wide.
  Plate footprint = content + margins, clamped to a comfy minimum grip size
  (≥ 40 × 28 mm, so the cylinder handle always fits). Motif-only mode rasterizes
  one big centred silhouette.
- **Mirroring**: for the STL the face mask is flipped in X (`np.fliplr`) so the
  pressed dough reads correctly. The preview is left un-mirrored (dough-reading).
- **Slab mesh** (`mesh_utils.build_slab_relief`): the same **watertight
  displaced-grid** trick the roller uses, but on a flat plate. A grid of
  vertices has its **bottom surface follow the relief heightmap** and its **top
  surface flat**, closed into one solid. In `raised` mode the background
  contacts the bed (`z = 0`) and the name is a recessed groove at `z = depth`;
  in `indented` mode the raised letters contact the bed. The outer top/bottom
  edges are bevelled 45° (`chamfer`): the flat faces inset and the rim runs
  bottom-bevel → vertical wall → top-bevel (safer + no elephant-foot).
- **Cylinder grip** (`mesh_utils.grip_cylinder`): a short upright cylinder
  (default 22 mm dia × 18 mm) with a chamfered top edge — prints as stacked
  rings, no supports, easy for a toddler to grasp. Its flat top optionally
  **raises the name's initial letter** (`top_mask` / `top_relief`, default 1.2
  mm) via a polar relief disk that shares the top rim — the planar cousin of the
  roller's `polar_disk_relief`, read the right way up (not mirrored). `dome_knob`
  (hemisphere) and a horizontal `bar` remain as alternatives. `bar` builds a
  horizontal
  `trimesh` capsule resting on the plate.
- **Assembly**: the plate and handle are concatenated (they overlap slightly);
  the slicer unions overlapping solids at slice time — the same approach the
  roller uses for its core + handles. The plate alone is watertight.
- Grid resolution is capped (~900 px/side) to keep the triangle count sane on
  long names.

## How to add new motif themes (fruits, animals, flowers, bugs…)

Motifs are just SVGs in `assets/` — identical sourcing to the rollers:

1. Find a bold, **chunky** silhouette SVG (solid, no hairline strokes). Good
   sources via the Iconify API (no key needed):
   `https://api.iconify.design/<prefix>/<name>.svg` — sets `noto`,
   `fluent-emoji-high-contrast`, `game-icons`, `mdi`, `ion`.
   Search: `https://api.iconify.design/search?query=<term>&limit=40`
   Download (PowerShell):
   `Invoke-WebRequest "https://api.iconify.design/noto/strawberry.svg" -OutFile assets\strawberry.svg -UseBasicParsing`
2. Save into `assets\` and record the source/licence in `assets/ATTRIBUTION.md`.
3. Use it directly: `--svg assets\strawberry.svg --shape circle` for a picture
   stamp, or `--icon strawberry.svg` above a name.
4. Preview first. If a detailed icon looks blobby, raise `--ppm`; if it looks
   thin/fragile, pick a bolder icon (solid silhouettes print best).

## Status

**Working & mesh-verified** (watertight, sits on the bed, no supports). The
Ember demo (`--name Ember --icon flower.svg --border`) is the reference output.
Not yet print-verified on the physical A1 — first physical print pending.
