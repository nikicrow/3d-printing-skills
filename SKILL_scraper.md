---
name: playdoh-scraper
description: Generate a parametric, toddler-friendly Play-Doh / clay SCRAPER (preview PNG and printable STL) — a wide low wedge with a blunt (non-blade) front scraping edge and the child's NAME raised on the back platform. Companion to the playdoh-roller and playdoh-stamp skills; reuses the same fonts and watertight STL pipeline.
---

# Play-Doh Scraper Generator

Generates a custom dough scraper: seen from above it's a rectangle; seen from
the side it's an elongated, low-gradient **wedge** rising from a thin **blunt**
front scraping edge (deliberately not a blade — toddler-safe) up to a thicker
back. The thick back has a flat level platform with the child's **name raised
(bumping out)** on top. The flat base prints support-free and rests on the
table; you push the blunt front edge along a surface to scrape up dough.

Companion to [[playdoh-roller]] / [[playdoh-stamp]] — it **reuses the same**
chunky fonts and the same watertight, no-boolean STL pipeline that has
print-verified on the Bambu Lab A1.

> **Status: print-verified & in real use.** Printed and used on real Play-Doh —
> "quite effective". Locked-in size after iterating: **120 × 60 mm**, ~14° ramp,
> 1.5 mm blunt edge, 12 mm back.

## Location

- Script: `C:\Users\nikil\3d-printed-playdoh-roller\playdoh_scraper.py`
  (git mirror: `3d-printing-skills\playdoh_scraper.py`)
- Outputs are written next to the script, regardless of the working directory.

## Dependencies

```
pip install trimesh numpy pillow matplotlib pydantic --break-system-packages
```

Pure local Python 3 — no native cairo, no shapely, no boolean/manifold backend.
`trimesh` is only needed for `--stl`. It reuses `load_font` from
`svg_processing.py` and `build_prism_between` from `mesh_utils.py`, so keep
`playdoh_scraper.py`, `svg_processing.py` and `mesh_utils.py` side by side.

## How to run

```
# Preview (side profile + top view):
python playdoh_scraper.py --name "Ember" --preview

# Printable STL (flat base down, no supports):
python playdoh_scraper.py --name "Ember" --stl
```

At least one of `--preview` / `--stl` is required.

## Parameters (all optional CLI flags; defaults baked in)

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `Ember` | Name raised on the back platform |
| `--width` | `120` | Scraper width, mm (length of the scraping edge) |
| `--depth` | `60` | Front-to-back depth, mm |
| `--back-height` | `12` | Height of the thick back, mm |
| `--edge-height` | `1.5` | Blunt front-edge thickness, mm (bigger = safer/blunter) |
| `--platform-depth` | `18` | Depth of the flat name platform at the back, mm |
| `--name-relief` | `1.0` | How far the name bumps out of the platform, mm |
| `--letter-height` | `9` | Target cap height of the name, mm (auto-shrunk to fit) |
| `--name-margin` | `5` | Clear margin around the name on the platform, mm |
| `--ppm` | `6` | Heightfield resolution, px/mm (6 = crisp name; lower = smaller/rougher) |

The remaining depth after the platform is the **ramp** — the ramp angle is
derived (`atan((back_height − edge_height) / ramp_len)`) and printed on export.
At the locked-in 120 × 60 mm it is ~14°.

### Output file naming

- Preview: `preview_scraper_<name>.png`
- STL: `scraper_<name>.stl`

## Name orientation

The raised name is **mirrored on the part** so it **reads the right way up while
you scrape** (i.e. when the blunt edge is pushed away from you and the platform
is nearest you). The preview's top-view panel is drawn from that same scraping
viewpoint, so the name looks upright there.

## Second colour (name)

STL is a geometry-only format and **cannot store colour**; a generic 3MF from
this pipeline doesn't reliably carry colour into Bambu Studio either. But the
raised name is the **only geometry above the flat back platform**, so:

- **Add a single filament change at `Z = back_height` (12 mm at defaults)** in
  Bambu Studio → it colours *exactly* the name, nothing else. Works on the A1
  with one extruder (one swap). The exact Z is printed on `--stl` export.
- With an AMS you can instead height-range-assign the top layers to filament 2.

## 3D printing settings (Bambu Studio)

- **Orientation**: exported flat base down (as used) — print as oriented; it
  already sits on `z = 0`.
- **Supports**: **none**. The top is a single ramp/heightfield above a flat
  base — no overhangs. The raised name prints as the last layers.
- **Layer height**: 0.15 mm keeps the raised name and the blunt edge crisp.
- **Edge safety**: the front edge is a blunt vertical face (1.5 mm), not a
  blade. Raise `--edge-height` for an even blunter edge.
- **Material**: PLA is fine for Play-Doh (non-edible modelling compound).
- **File size**: ~52 MB at `ppm=6` (a big flat footprint). Drop `--ppm` to 4
  (~23 MB) if you want smaller files and can accept a slightly rougher name.

## Architecture

Matches the roller/stamp: all parameters live in a validated
**`ScraperConfig(BaseModel)`** pydantic model (`extra="forbid"`,
`validate_assignment=True`, `Field(gt=0)` ranges, a `model_validator` checking
`edge_height < back_height` and `platform_depth < depth`). The geometry is
delegated to the shared, project-agnostic module:

- `mesh_utils.build_prism_between` — a watertight solid between a flat base and
  a shaped top heightfield (the scraper's ramp + platform + raised name), added
  alongside the roller's `build_roller_mesh` and the stamp's `build_slab_relief`.
- `svg_processing.load_font` renders the chunky name.

## How it works (implementation notes)

- **Top heightfield** (`build_top_field`): the side profile along Y is a blunt
  front edge (`edge_height` at `y = 0`) ramping linearly up to `back_height`,
  then flat over the back `platform_depth`. The name is rendered to a mask,
  mirrored in X (`np.fliplr`) so it reads while scraping, and added as
  `name_relief` on the platform. Bottom is flat `z = 0`.
- **Solid** (`build_prism_between`): grids the flat bottom and the shaped top and
  stitches four vertical side walls into one watertight solid — no booleans, no
  supports. The front wall is the blunt `edge_height` face.
