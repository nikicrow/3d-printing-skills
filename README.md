# 🎨 Play-Doh & Name-Label Printing Toolkit

Small, parametric generators that turn a **kid's name** (and a theme) into
printable 3D models. The three Play-Doh tools each produce a **flat PNG preview**
and a **print-ready STL**; the newer **name-label** tool is a **two-colour
keychain** whose geometry is a parametric **OpenSCAD** file — so the same source
exports locally *and* uploads to MakerWorld as a customisable multicolour model.

| Tool | What it makes | Script |
|---|---|---|
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
pip install trimesh numpy pillow matplotlib svgpathtools pydantic --break-system-packages

# make a preview + printable STL (each tool takes --name; roller also takes --theme)
python playdoh_roller.py  --name "Imogen" --theme shapes --preview --stl
python playdoh_stamp.py    --name "Imogen" --preview --stl
python playdoh_scraper.py  --name "Imogen" --preview --stl

# two-colour keychain name label (needs OpenSCAD for --stl/--3mf; --preview doesn't)
python namelabel.py --name "Ember"  --icon bee   --preview --stl
python namelabel.py --name "Imogen" --icon heart --font "Bagel Fat One" --preview --3mf
```

`--preview` is fast (no `trimesh`); `--stl` builds the mesh and takes longer.
Outputs are **auto-filed** into the folders below — no matter which directory
you run from — so the repo root stays tidy.

Per-tool reference docs (all flags, printing settings, design constraints):
[`SKILL_label.md`](SKILL_label.md) · [`SKILL_roller.md`](SKILL_roller.md) ·
[`SKILL_stamp.md`](SKILL_stamp.md) · [`SKILL_scraper.md`](SKILL_scraper.md) ·
[`SKILL_roller_v2.md`](SKILL_roller_v2.md)

---

## Repo structure

```
label.scad             name-label geometry (parametric OpenSCAD, MakerWorld-ready)
namelabel.py           name-label driver  (LabelConfig): PIL preview + OpenSCAD export
playdoh_roller.py      roller generator   (RollerConfig)
playdoh_stamp.py       stamp generator    (StampConfig)
playdoh_scraper.py     scraper generator  (ScraperConfig)
svg_processing.py      shared: SVG → mask rasterizer + font loading
mesh_utils.py          shared: watertight mesh helpers (no booleans, no supports)

assets/                decoration SVGs + ATTRIBUTION.md
assets/fonts/          bundled bubbly fonts for the label (OFL/Apache) + ATTRIBUTION.md
previews/              generated PNG previews  →  labels/ rollers/ stamps/ scrapers/
printable_files/       generated STL / 3MF     →  labels/ rollers/ stamps/ scrapers/
archive/               the v2 (engraved) roller experiment

SKILL_label.md         per-tool reference docs (copies of the registered skills)
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

Generic 3MFs from a mesh pipeline don't carry colour into Bambu Studio
reliably — which is why the earlier multicolour scraper attempt fell flat. The
name label sidesteps that entirely by being **parametric OpenSCAD** and by
**splitting the two colours by height**:

- **Bottom band** (`0 .. border_h`) = the border colour — the full rounded
  "trace" outline + keychain tab.
- **Top band** (`border_h .. border_h+font_h`) = the name colour — *only* the
  raised letters + optional icon.

Because the second colour lives only where the letters are, in a thin top layer,
it barely adds any filament. And the clean split gives two dead-simple colour
routes:

- **One extruder** (A1/P1/X1, no AMS): print the **STL** with a single **filament
  change at `Z = border_h`** (printed on export, default 1.6 mm).
- **AMS / MakerWorld**: the **two `color()` parts** export as *border* + *name*;
  assign a filament to each (needs OpenSCAD **2024+** for colour-in-3MF, which is
  what MakerWorld runs).

Everything fuses into **one connected, watertight solid** (a hidden connector
web in the base ties the tab, icon and name together), so nothing prints loose.

```bash
python namelabel.py --name "Ember"  --icon bee   --preview --stl
python namelabel.py --name "Imogen" --icon heart --font "Bagel Fat One" --3mf
```

### Post it on MakerWorld as a customisable model

`label.scad` is written for MakerWorld's **Parametric Model Maker**: the
`/* [section] */` comments and `// [choices]` become customiser controls, and the
two `// color` hex variables become colour pickers. Zip **`label.scad` with the
`assets/` folder** (keeping paths like `assets/fonts/…` and `assets/heart.svg`)
and upload — anyone can then type a name, pick a font/colours/icon and print in
colour. Full guidance in [`SKILL_label.md`](SKILL_label.md).

Six bubbly fonts are bundled (Baloo 2, Bagel Fat One, Titan One, Chewy, Lilita
One, Bubblegum Sans — all OFL/Apache, see
[`assets/fonts/ATTRIBUTION.md`](assets/fonts/ATTRIBUTION.md)).

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
