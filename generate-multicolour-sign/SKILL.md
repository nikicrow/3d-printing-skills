---
name: generate-multicolour-sign
description: Generate parametric, centred, multiline 3D-printable text signs in Google Fonts Unkempt, optionally with a corner keychain hole. Use for black-base/white-raised-text signs, scalable rounded plaques or keychain tags, native multicolour 3MF files, separate colour-part STLs, or sign previews where explicit newlines control the line layout.
---

# Generate Multicolour Sign

Create a rounded sign whose footprint scales around centred Unkempt text. Keep
the default 4 mm black base, 1.5 mm white text layer, and softened top edges
unless the user requests other dimensions or colours.

## Generate a sign

Run `scripts/generate_sign.py` from the repository. Install `numpy`, `pillow`,
`trimesh`, and `scipy` first if unavailable. The script also uses the library's
shared `mesh_utils.py` for watertight text extrusion and native colour 3MF.

Pass text with either actual newlines or literal `\n` sequences. Leading and
trailing spaces on each line are removed; blank lines remain vertical gaps.

```bash
python generate-multicolour-sign/scripts/generate_sign.py \
  --text "hand\nwashing\nstation" \
  --output-dir printable_files/signs
```

With no output flags, create all deliverables:

- `<stem>_multicolour.3mf`: one assembled object with `black_base` and
  `white_text` parts assigned to extruders 1 and 2.
- `<stem>_black_base.stl` and `<stem>_white_text.stl`: separate meshes for
  slicers that prefer manual part assembly.
- `<stem>_preview.png`: top-view colour and dimension preview.

Use `--preview`, `--3mf`, or `--stl-parts` to limit output. Useful parameters
include `--letter-height`, `--line-spacing`, `--padding-x`, `--padding-y`,
`--base-height`, `--text-height`, `--corner-radius`, `--base-bevel`,
`--text-bevel`, `--font-weight {400,700}`, and `--ppm`.

Add `--keychain-hole` for a chamfered 5 mm through-hole. Select its location
with `--hole-corner {top-left,top-right,bottom-left,bottom-right}` and adjust it
with `--hole-diameter` or `--hole-wall`. The layout automatically increases its
padding to keep centred text clear of the hole.

## Verify output

Confirm the command reports both meshes as watertight. Inspect the PNG for
centering and line breaks. Print flat with the text facing up; no supports are
required. Import the 3MF for a multi-material setup. Import both STLs at the
same origin when assigning colours manually.

## Assets

Use `assets/Unkempt-Regular.ttf` for weight 400 and
`assets/Unkempt-Bold.ttf` for weight 700. Keep `assets/LICENSE.txt` with the
fonts; they come from the official Google Fonts repository under Apache 2.0.
