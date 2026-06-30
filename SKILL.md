---
name: playdoh-roller
description: Generate a parametric, personalized Play-Doh roller (preview PNG and printable STL) with a name embossed lengthways and a themed decoration pattern (bees & flowers, dinosaurs, shapes, cats, fruits).
---

# Play-Doh Roller Generator

> **Status: working & print-verified.** The Ember / bees-and-flowers roller has
> been printed on a Bambu Lab printer (solid, upright, no handles) and came out
> great — crisp embossed name and decorations. The full pipeline (SVG icons →
> heightmap → upright STL → print) is confirmed end-to-end.

Generates a custom Play-Doh / clay texture roller: a cylinder with a kid's name
embossed lengthways along the barrel and a themed pattern of decorations (bees,
dinosaurs, etc.) filling the rest of the surface. Outputs either a flat PNG
preview of the dough imprint, or a printable STL of the actual roller.

Decorations are **real open-licensed silhouette icons** rasterized from SVG
files in `assets/` (NOT hand-drawn primitives) — see `assets/ATTRIBUTION.md`.

Raised features on the roller push DOWN into the dough, so the imprint is the
inverse of the roller surface (this is handled automatically — features are
raised outward from the barrel).

## Location

- Script: `C:\Users\nikil\3d-printed-playdoh-roller\playdoh_roller.py`
- Decoration SVGs: `C:\Users\nikil\3d-printed-playdoh-roller\assets\`
- Outputs (PNGs and STLs) are written next to the script in
  `C:\Users\nikil\3d-printed-playdoh-roller\`, regardless of the working
  directory it is invoked from.

## Dependencies

```
pip install trimesh numpy pillow matplotlib svgpathtools --break-system-packages
```

`numpy`, `pillow`, `matplotlib`, and `svgpathtools` are needed for `--preview`
(svgpathtools rasterizes the decoration SVGs). `trimesh` is only needed for
`--stl`. Pure local Python 3 — no native cairo and no internet needed at run
time (the SVG icons are already saved in `assets/`).

## How to run

```
python playdoh_roller.py --name "Ember" --theme bees_and_flowers --preview
python playdoh_roller.py --name "Ember" --theme bees_and_flowers --stl
```

Combine `--preview --stl` in one call to produce both. At least one of the two
flags is required.

### Parameters (all optional CLI flags; defaults baked in)

| Flag | Default | Meaning |
|---|---|---|
| `--name` | `Ember` | Name embossed lengthways along the roller |
| `--theme` | `bees_and_flowers` | One of: `bees_and_flowers`, `dinosaurs`, `shapes`, `cats`, `fruits` |
| `--radius` | `17.5` | Roller barrel radius in mm (35 mm diameter) |
| `--length` | `90` | Usable imprint length in mm |
| `--handle-length` | `22` | Length of each handle end, mm |
| `--handle-radius` | `10` | Handle grip radius, mm |
| `--emboss` | `1.8` | How far text/decorations rise above the barrel, mm |
| `--top-stamp` | off | Raise the theme's first icon out of the roller's **top end** so it doubles as a press-stamp (STL only) |
| `--stamp-relief` | `2.5` | Height of the top-end stamp icon, mm |
| `--ppm` | `12` | Heightmap resolution, pixels per mm (≥10 keeps detailed icons like the dinos crisp; lower = faster/rougher) |

### Top-end stamp (`--top-stamp`)

Turns the roller's top face into a cute press-stamp by raising the theme's first
icon (bee / T-Rex / circle / cat / banana) ~2.5 mm out of the **up** end (the
bed end stays flat for adhesion). It's built into the same single watertight
solid (a displaced polar disk that shares the body's end ring — no booleans), so
it stays print-clean. STL only — the flat preview doesn't show it. Adds geometry,
so STL generation takes a couple of minutes.

### Output file naming

- Preview: `preview_<name>_<theme>.png` (name lowercased, spaces -> `_`)
- STL: `roller_<name>_<theme>.stl`

## What the preview PNG shows

The unrolled cylinder surface (circumference × length), rendered Play-Doh
cream/beige with the imprinted areas in a darker "indented" colour — i.e. what
the imprint would look like pressed into Play-Doh, not the plastic roller
itself. The name reads lengthways (rotated 90°, read bottom-to-top). Title
("ROLLER PREVIEW — <name> / <theme>") and caption are baked into the image.

## 3D printing settings (Bambu Studio)

- **Orientation**: the STL is exported **standing upright on its end** (axis
  along Z, sitting on the bed) — no manual rotation needed. Each layer is a ring
  with the relief on its outer wall, so it prints clean with no overhangs.
- **Handles**: OFF by default (simple barrel). Pass `--handles` to add grip
  stubs at both ends (the old horizontal-with-handles style).
- **Plate**: Engineering plate adhesion preset. A brim helps the small circular
  footprint stick; slow the first layer.
- **Quality preset**: 0.15 mm layer height ("Fine" / fine-detail preset) for
  crisp letters and edges. 0.2 mm is an acceptable faster fallback but rounds
  off detail.
- **Infill**: 40%. Use 3+ walls so emboss features print fully solid.
- **Supports**: none needed in the upright orientation — no overhangs.
- **Material**: PLA for a quick, low-stress print; PETG for durability.

## Design constraints (why it prints well)

- Emboss height 1.8 mm (FFF best practice: raised detail >0.9 mm wide,
  <2 mm high).
- Minimum feature width 1.5 mm — enforced in code by the `_w()` helper, which
  clamps every line/outline width to `MIN_FEATURE_MM * RESOLUTION_PPM` px.
- Decorations are bold/chunky, ~10–15 mm in their longest dimension, with no
  isolated thin islands.
- Name letter height = 40% of the roller diameter (`TEXT_DIAMETER_FRACTION`),
  centred on the circumference and running along the length.

## Themes & decoration icons

Decorations are SVG icons in `assets/`, rasterized to bold silhouette stamps:

| Theme | Icons (file → mode) |
|---|---|
| `bees_and_flowers` | bee.svg (evenodd), flower.svg (evenodd) |
| `dinosaurs` | trex.svg (union), brontosaurus.svg (union) |
| `shapes` | circle, square, triangle, star, heart (evenodd) |
| `cats` | cat.svg (evenodd), paw.svg (evenodd) |
| `fruits` | banana.svg (union), apple.svg (union) |

`mode` controls fill: **evenodd** keeps interior holes (single-colour icons);
**union** flattens all sub-paths into one solid silhouette (used for multicolour
emoji art like the Noto dinosaurs/fruit).

## How to add a new theme

1. Find bold, simple, **chunky** silhouette SVGs (one per decoration). Good
   sources via the Iconify API (no key needed), e.g.:
   `https://api.iconify.design/<prefix>/<name>.svg`
   - Solid/silhouette sets work best: `game-icons`, `noto` /
     `fluent-emoji-high-contrast` (full-body emoji), `mdi`, `ion`.
   - Search names: `https://api.iconify.design/search?query=<term>&limit=40`
   - Download with PowerShell:
     `Invoke-WebRequest "https://api.iconify.design/noto/cat.svg" -OutFile assets\cat2.svg -UseBasicParsing`
2. Save the SVGs into `assets\`. Prefer single-`<path>` icons with no
   `transform`/`<g>` (the rasterizer flattens paths but does not apply group
   transforms).
3. Add an entry to the `THEMES` dict near the top of `playdoh_roller.py`:
   `"robots": [("robot_a.svg", "evenodd"), ("robot_b.svg", "union")]`
   Use `"union"` for multicolour emoji, `"evenodd"` for single-colour icons.
   `--theme` choices and the alternation pattern update automatically.
4. Record the source/licence in `assets/ATTRIBUTION.md`.
5. Test with `--preview` first. If a detailed icon looks blobby, raise `--ppm`
   (e.g. 12–14); if it looks thin/fragile, it may not be chunky enough — pick a
   bolder icon.

## Tips on choosing printable icons

- Solid silhouettes print best; avoid icons with hairline strokes or tiny
  isolated dots (they fall below the 1.5 mm minimum feature size).
- Full-body emoji (Noto/Fluent) flattened with `union` give chunky, kid-friendly
  shapes. Outline icons (thin strokes) generally print poorly.
- The code applies a gentle 1-px dilation to clean edges; it does **not** fix a
  fundamentally thin icon.

## Font handling

Tries a list of chunky/rounded fonts (`FONT_CANDIDATES`) in order — Arial
Rounded MT Bold, Nunito, Comic Sans MS Bold, Arial Bold, DejaVu Sans Bold —
and falls back to PIL's default if none are found. The chosen font is printed
in the run log.

## Implementation notes

- The pattern (name + decorations) is built once as a 2D grayscale heightmap
  via PIL/numpy (255 = raised), reused for both outputs.
- **SVG rasterizer** (`rasterize_svg`): pure-Python, no native cairo. It parses
  each icon with `svgpathtools`, flattens every continuous sub-path to a
  polygon, composites them (XOR for even-odd holes / OR for union silhouettes),
  supersamples ×3 then downsamples for clean edges, and returns a 1-bit mask.
  Each theme icon is rasterized once at the decoration size and reused.
- **Decorations** are placed on a seeded grid (seed derived from
  `(name, theme)`, so re-runs are reproducible) with slight jitter so it looks
  natural but still tiles. Stamps alternate by `(col + row) % len(stamps)`
  (not random). Cells overlapping the central text band are skipped, and each
  icon mask is also pasted wrapped at ±circumference so the pattern tiles
  cleanly across the seam.
- **STL** uses a displaced-cylinder grid (the efficient, watertight equivalent
  of "add a radial prism per raised pixel"): grid vertices on raised texels sit
  at `R + emboss`, the rest at `R`, so features extrude outward. The grid is
  capped at 720×720 to keep the triangle count sane. A plain solid core
  cylinder is concatenated under the textured shell to guarantee
  watertightness, plus two narrower handle cylinders at the ends (slightly
  overlapping the body).
