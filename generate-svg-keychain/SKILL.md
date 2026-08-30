---
name: generate-svg-keychain
description: Turn filled or stroked SVG artwork into a parametric, beveled, multicolour 3D-printable keychain with a reinforced top hole. Use when a user supplies an SVG and color choices and wants an OBJ/MTL or Bambu-ready 3MF.
---

# Generate SVG Keychain

Create a flat-backed keychain that follows the SVG silhouette. The base extends
around the artwork, the visible SVG regions rise above it, and a reinforced
loop is attached at the top. Use `scripts/generate_keychain.py`; it deterministically
creates the geometry and preserves separate material regions.

Install `scripts/requirements.txt` into the active Python environment if an
import is unavailable. The generator also imports the repository's shared
`mesh_utils.py` for watertight bevelled extrusion and color 3MF export.

## Gather only consequential inputs

The SVG is required. Use these defaults unless the user changes them:

- base/border color: white (`#FFFFFF`)
- artwork maximum dimension: 55 mm
- border width around artwork: 3 mm
- base height: 3 mm
- raised artwork height: 1.2 mm
- bevel: 0.3 mm
- keychain hole: 5 mm diameter with a 2.5 mm wall, centered at the top

Treat "border thickness" as the XY border width. Treat "base thickness" as the
Z height. If the user's wording could mean either but they gave only one value,
use it for the border width and retain the default base height.

When color-to-region mapping is not obvious from IDs, labels, or existing SVG
fills, inspect first and ask one concise question rather than guessing which
region is which:

```powershell
python generate-svg-keychain/scripts/generate_keychain.py artwork.svg --inspect
```

Do not ask for dimensions, bevel, or hole measurements when the defaults are
acceptable. If the user describes semantic regions such as "carrot body" or
"nose", match those descriptions to SVG `id` or Inkscape label values. A color
mapping selector may also be an existing SVG color.

## Generate

Pass repeatable mappings as `selector=#RRGGBB`. Selectors match an element ID,
an Inkscape label, or a source fill/stroke color. Quote arguments containing `#`.

```powershell
python generate-svg-keychain/scripts/generate_keychain.py carrot.svg `
  --output-dir printable_files/keychains/carrot `
  --color-map "body=#F47A20" `
  --color-map "fill:#55AA55=#36A852"
```

Useful overrides are `--max-art-size`, `--border-width`, `--base-height`,
`--art-height`, `--bevel`, `--hole-diameter`, `--hole-wall`, `--hole-position`,
`--base-color`, and `--ppm`. Use `--no-hole` only when explicitly requested.
Use `--fill-rule union` only for artwork whose subpaths incorrectly disappear
under the default even-odd interpretation.

For low-resolution raster line art that must be vectorized first, supersample
before tracing and smooth antialiased coverage rather than thresholding only
the darkest pixels. Keep printable detail strokes continuous and approximately
0.7 mm or wider at final size; inspect the preview for gaps, stair steps, or
blotchy corners before generating final meshes.

The command creates:

- `<name>_multicolour.obj` plus `<name>_multicolour.mtl`: separate named shells
  and material colors; keep both files together when importing the OBJ.
- `<name>_multicolour.3mf`: the preferred Bambu Studio import because part and
  filament assignments are more reliably preserved than OBJ materials.
- `<name>_preview.png`: top-view color preview.
- `<name>_manifest.json`: dimensions, colors, parts, parameters, and source SVG.

## Verify and hand off

Require the generator to report every part watertight. Inspect the PNG for
correct region mapping, silhouette, and hole placement. If colors or parts are
wrong, inspect the SVG and adjust mappings before delivery. Tell the user to
open the 3MF in Bambu Studio when possible; the OBJ and MTL remain available
for their requested OBJ workflow. Print flat, base down, without supports.

For SVG limitations and selector details, read
[references/svg-inputs.md](references/svg-inputs.md) only when inspection shows
unsupported or ambiguous artwork.
