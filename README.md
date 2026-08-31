# 🎨 Play-Doh & Name-Label Printing Toolkit

Small, parametric generators that turn a **kid's name** (and a theme) into
printable 3D models. The three Play-Doh tools each produce a **flat PNG preview**
and a **print-ready STL**; the newer **name-label** tool is a **two-colour
keychain** whose geometry is a parametric **OpenSCAD** file — so the same source
exports locally *and* uploads to MakerWorld as a customisable multicolour model.

| Tool | What it makes | Script |
|---|---|---|
| **Multicolour sign** | A scalable rounded plaque with centred, multiline Unkempt text: 4 mm black base, 1.5 mm white raised lettering, native two-part 3MF, separate STLs, and PNG preview. | [`generate-multicolour-sign/`](generate-multicolour-sign/) |
| 🐕 **Collar tag** | A two-sided **pet collar tag**: a rounded baby-blue plaque with black lettering **inlaid flush** into *both* faces, a chamfered collar hole and softened edges. Auto-wraps and auto-sizes the text; the back face is mirrored so it reads when flipped. | [`dogtag.py`](dogtag.py) |
| 🏷️ **Name label** | A cute, bubbly **two-colour keychain**: the name (+ optional theme icon) raised in one colour on a contrasting rounded "trace" border, with a clasp hole. Colours split by height to cut waste. Local **STL/3MF** *and* a MakerWorld parametric model. | [`label.scad`](label.scad) · [`namelabel.py`](namelabel.py) |
| 🌀 **Roller** | A barrel with the name embossed lengthways + a themed pattern (bees, dinos, shapes, cats, fruits, trucks) that rolls a repeating imprint into the dough. | [`playdoh_roller.py`](playdoh_roller.py) |
| 🔤 **Stamp** | A compact ~5 cm slab with a grippy cylinder handle that presses the name (and/or an icon) into the dough. Initial raised on the handle top. | [`playdoh_stamp.py`](playdoh_stamp.py) |
| 🧹 **Scraper** | A wide, low, toddler-safe wedge with a blunt front edge and the name raised on the back platform. | [`playdoh_scraper.py`](playdoh_scraper.py) |

> ✅ **The three Play-Doh tools are print-verified** on a Bambu Lab printer. A
> **v2 roller** (engraved → *raised* dough imprint, via `--engrave`) was also
> tried; the original was preferred, so v2 lives in [`archive/`](archive/). The
> **name label** exports as a single connected, watertight solid and is ready
> for its first test print.

---

## Quick start

```bash
# install dependencies (one time)
pip install trimesh numpy pillow matplotlib svgpathtools pydantic scipy --break-system-packages
pip install shapely manifold3d --break-system-packages   # dogtag.py only

# make a preview + printable STL (each tool takes --name; roller also takes --theme)
python playdoh_roller.py  --name "Imogen" --theme shapes --preview --stl
python playdoh_stamp.py    --name "Imogen" --preview --stl
python playdoh_scraper.py  --name "Imogen" --preview --stl

# two-colour keychain name label (needs OpenSCAD for --stl/--3mf; --preview doesn't)
python namelabel.py --name "Ember"  --icon flower --preview --stl
python namelabel.py --name "Imogen" --icon heart --font "Bagel Fat One" --preview --3mf

# two-sided pet collar tag (all outputs by default; --front is the only must)
python dogtag.py --front "Kip" --back "0450 572 596" --stem kip_name

# centred multiline sign (creates 3MF, separate STLs, and preview by default)
python generate-multicolour-sign/scripts/generate_sign.py --text "hand\nwashing\nstation"
```

`--preview` is fast (no `trimesh`); `--stl` builds the mesh and takes longer.
Outputs are **auto-filed** into the folders below — no matter which directory
you run from — so the repo root stays tidy.

Per-tool reference docs (all flags, printing settings, design constraints):
[`SKILL_dogtag.md`](SKILL_dogtag.md) · [`SKILL_label.md`](SKILL_label.md) ·
[`SKILL_roller.md`](SKILL_roller.md) ·
[`SKILL_stamp.md`](SKILL_stamp.md) · [`SKILL_scraper.md`](SKILL_scraper.md) ·
[`SKILL_roller_v2.md`](SKILL_roller_v2.md)

---

## Repo structure

```
dogtag.py              pet collar tag: outline-based, text inlaid flush into both faces
label.scad             name-label geometry (parametric OpenSCAD, MakerWorld-ready)
namelabel.py           name-label MakerWorld pipeline: PIL preview + OpenSCAD export
playdoh_label.py       name-label standalone pipeline: pure-trimesh multicolour 3MF
playdoh_roller.py      roller generator   (RollerConfig)
playdoh_stamp.py       stamp generator    (StampConfig)
playdoh_scraper.py     scraper generator  (ScraperConfig)
svg_processing.py      shared: SVG → mask rasterizer + font loading
mesh_utils.py          shared: watertight mesh helpers (no booleans, no supports)
test_label_3mf.py      checks label 3MFs really are two-colour (lib3mf, strict)

assets/                decoration SVGs + ATTRIBUTION.md
assets/fonts/          bundled bubbly fonts for the label (OFL/Apache) + ATTRIBUTION.md
previews/              generated PNG previews  →  dogtags/ labels/ rollers/ stamps/ scrapers/
printable_files/       generated STL / 3MF     →  dogtags/ labels/ rollers/ stamps/ scrapers/
archive/               the v2 (engraved) roller experiment

SKILL_dogtag.md        per-tool reference docs (copies of the registered skills)
SKILL_label.md
SKILL_roller.md
SKILL_stamp.md
SKILL_scraper.md
SKILL_roller_v2.md
README.md              this file
sync.sh                keep the three copies of this project in step (see below)
```

Every tool stores its tunable parameters in one validated **pydantic `*Config`**
(`extra="forbid"`, so a typo'd flag fails fast with a clear message) and
delegates geometry to the two shared, project-agnostic modules. Adding a tool =
one new `*.py` with its own `Config` + a couple of shared calls.

---

## The two-colour name label (multicolour done the reliable way)

A naive 3MF from a mesh pipeline doesn't carry colour into Bambu Studio
reliably — which is why the earlier multicolour scraper attempt fell flat. The
name label solves that two ways: it **splits the two colours by height**, and it
writes each colour as its own 3MF part with *both* a standard material and a
Bambu-native extruder assignment. The height split is the important half:

- **Bottom band** (`0 .. border_h`) = the border colour — the full rounded
  "trace" outline + keychain tab.
- **Top band** (`border_h .. border_h+font_h`) = the name colour — *only* the
  raised letters + optional icon.

Because the second colour lives only where the letters are, in a thin top layer,
it barely adds any filament. And the clean split gives two dead-simple colour
routes:

- **One extruder** (A1/P1/X1, no AMS): print the **STL** with a single **filament
  change at `Z = border_h`** (printed on export, default 2.4 mm).
- **AMS**: `playdoh_label.py --3mf` writes *border* + *name* as two parts already
  pinned to extruder 1 and 2 — import and print. (The OpenSCAD route exports the
  same two `color()` parts but needs **2024+** for colour-in-3MF, which is what
  MakerWorld runs.)

`python test_label_3mf.py` re-reads the exported 3MFs with **lib3mf**, the 3MF
Consortium's reference implementation, and asserts the things that make them
print in two colours — two distinct base materials, each part bound to one and
manifold-and-oriented, one build item, and the Bambu extruder assignments. All
13 party labels pass in strict mode. (Bambu Studio itself has not been run
against them; see [`SKILL_label.md`](SKILL_label.md).)

The base plate is **one connected piece** (a hidden connector web in the base
ties the tab, icon and name together), so nothing prints loose. A small **45°
chamfer** on the top face of the plate rim and of the raised name (`bevel`,
default 0.3 mm) removes the sharp arris without touching either underside — the
plate keeps its full first-layer footprint for bed adhesion. It is free in
the standalone pipeline; on the OpenSCAD side it costs real render time — see
[`SKILL_label.md`](SKILL_label.md) before uploading to MakerWorld.

There are **two interchangeable pipelines** for the same design:

```bash
# 1) MakerWorld pipeline — parametric label.scad, exported via OpenSCAD:
python namelabel.py    --name "Ember"  --icon flower --preview --stl

# 2) Standalone pipeline — pure trimesh, writes a native multicolour 3MF
#    (two coloured parts Bambu Studio reads directly) with NO OpenSCAD needed:
python playdoh_label.py --name "Imogen" --icon heart --3mf
```

Use pipeline 1 to post a customisable model to MakerWorld; use pipeline 2 to get
a ready-to-slice two-colour 3MF locally. They share a naming scheme and pipeline
2 suffixes its outputs `_mesh`, so running both on one name is safe.

To generate a label for every child on the party list at once, see
[`_batch_labels.sh`](_batch_labels.sh).

### Post it on MakerWorld as a customisable model

`label.scad` is written for MakerWorld's **Parametric Model Maker**: the
`/* [section] */` comments and `// [choices]` become customiser controls, and the
two `// color` hex variables become colour pickers. Zip **`label.scad` with the
`assets/` folder** (keeping paths like `assets/fonts/…` and `assets/heart.svg`)
and upload — anyone can then type a name, pick a font/colours/icon and print in
colour. Full guidance in [`SKILL_label.md`](SKILL_label.md).

Seven bubbly fonts are bundled (Grandstander — the default, a static Bold
instance baked from the variable font — plus Baloo 2, Bagel Fat One, Titan One,
Chewy, Lilita One, Bubblegum Sans; all OFL/Apache, see
[`assets/fonts/ATTRIBUTION.md`](assets/fonts/ATTRIBUTION.md)).

---

## The pet collar tag (two colours split in *plan*, not by height)

The name label splits its colours **by height** — a border plate with the name
raised on top. A collar tag can't work that way: it has to read from whichever
side is facing out, and anything standing proud gets chewed, dragged through
grass and worn off. So [`dogtag.py`](dogtag.py) splits the colours **in plan**:
one baby-blue plaque with the lettering **recessed into both faces**, and black
letter solids that fill those recesses exactly flush (removed volume == inlay
volume to 1e-5 mm³). The back face is mirrored in the model, so it reads the
right way round once the tag is flipped on the collar.

```bash
python dogtag.py --front "Kip" --back "0450 572 596" --stem kip_name
python dogtag.py --front "I'm not good\nat meeting\nnew people,\nplease call\nmy dad" \
                 --height 44 --stem kip_shy
```

It is the one **outline-based** tool here: glyph outlines come straight from the
TTF and the plaque is lofted from analytic rings, so the letters are smooth
curves instead of stair-stepped pixels and a whole two-sided tag is ~31 k
triangles rather than the ~500 k a raster pipeline needs for the same area. Type
one long string and the layout engine picks the line breaks and the largest size
that fits. That loft also *is* the safety feature: the rim is inset at both
faces and the hole is widened at both mouths by `--bevel`, so no edge on the
finished tag is a sharp arris.

The trade is one dependency the rest of the repo does without — `manifold3d`,
for the two recess booleans — and the fact that a flush inlay puts two colours
in the **same layer**, so it needs an AMS. Single-extruder printers get the same
tag with **engraved** text by printing `<stem>_body.stl` on its own. Full flags,
printing settings and the stroke-width limit: [`SKILL_dogtag.md`](SKILL_dogtag.md).

---

## Adding a new name

Just pass `--name`. That's it — the preview and STL are named after it and land
in the right subfolder automatically:

```bash
python playdoh_roller.py --name "Freddie" --theme dinosaurs --preview --stl
python namelabel.py      --name "Freddie" --icon car --preview --stl
```

To regenerate the whole roller collection at once, see
[`_batch.sh`](_batch.sh).

## Adding a new roller theme

1. Find two **bold, chunky silhouette SVGs** (one per decoration). Solid emoji
   sets work best — e.g. Iconify: `https://api.iconify.design/noto/<name>.svg`.
2. Drop them in [`assets/`](assets/) and record the source in
   [`assets/ATTRIBUTION.md`](assets/ATTRIBUTION.md).
3. Add one line to the `THEMES` dict near the top of
   [`playdoh_roller.py`](playdoh_roller.py):
   `"robots": [("robot_a.svg", "evenodd"), ("robot_b.svg", "union")]`
   (`union` for multicolour emoji, `evenodd` for single-colour icons). The
   `--theme` choices update automatically.
4. Test with `--preview` first; bump `--ppm` if a detailed icon looks blobby.

Full guidance is in [`SKILL_roller.md`](SKILL_roller.md).

---

## Printing (Bambu Studio)

All models export **already oriented for support-free printing** (rollers stand
upright on an end; stamps print face-down; scrapers sit flat). 0.15 mm layers,
40 % infill, 3+ walls, brim for the small footprints, PLA (PETG for durability).
Per-tool specifics are in each `SKILL_*.md`.

---

## How this project is kept in sync

This project lives in **three places** (a legacy of how the skills are wired):

1. **Working copy** (source of truth, where outputs are written) — this folder,
   `C:\Users\nikil\3d-printed-playdoh-roller\`.
2. **Git mirror** — `3d-printing-skills\` (the versioned repo).
3. **Registered Claude skills** — `~/.claude/skills/playdoh-*/SKILL.md` (the
   frontmatter here is what makes each skill trigger; treat these as the
   authoritative doc source).

Editing in more than one place by hand is what let them drift. Instead:

- **Change code / assets** → edit them here in the working copy.
- **Change a skill doc** → edit the registered `~/.claude/skills/<tool>/SKILL.md`.
- Then run **[`sync.sh`](sync.sh)** once — it copies the scripts + assets out to
  the git mirror and pulls the registered `SKILL.md` files back in as the
  consistently-named `SKILL_<tool>.md` copies (here and in the mirror), so all
  three locations match.

```bash
bash sync.sh
```

---

## Credits

Decoration icons are open-licensed silhouettes (Game-icons.net, Google Noto
Emoji, Material Design Icons, Microsoft Fluent Emoji, Ionicons) via the
[Iconify](https://iconify.design) API. Per-icon sources and licenses:
[`assets/ATTRIBUTION.md`](assets/ATTRIBUTION.md).
