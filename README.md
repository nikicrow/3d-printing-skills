# 🎨 Play-Doh Printing Toolkit

Three small, parametric Python generators that turn a **kid's name** (and a
theme) into printable 3D models for Play-Doh / clay play. Each one produces a
**flat PNG preview** of the dough imprint and a **print-ready STL**.

| Tool | What it makes | Script |
|---|---|---|
| 🌀 **Roller** | A barrel with the name embossed lengthways + a themed pattern (bees, dinos, shapes, cats, fruits, trucks) that rolls a repeating imprint into the dough. | [`playdoh_roller.py`](playdoh_roller.py) |
| 🔤 **Stamp** | A compact ~5 cm slab with a grippy cylinder handle that presses the name (and/or an icon) into the dough. Initial raised on the handle top. | [`playdoh_stamp.py`](playdoh_stamp.py) |
| 🧹 **Scraper** | A wide, low, toddler-safe wedge with a blunt front edge and the name raised on the back platform. | [`playdoh_scraper.py`](playdoh_scraper.py) |

> ✅ **All three are print-verified** on a Bambu Lab printer. A **v2 roller**
> (engraved → *raised* dough imprint, via `--engrave`) was also tried; the
> original was preferred, so v2 lives in [`archive/`](archive/).

---

## Quick start

```bash
# install dependencies (one time)
pip install trimesh numpy pillow matplotlib svgpathtools pydantic --break-system-packages

# make a preview + printable STL (each tool takes --name; roller also takes --theme)
python playdoh_roller.py  --name "Imogen" --theme shapes --preview --stl
python playdoh_stamp.py    --name "Imogen" --preview --stl
python playdoh_scraper.py  --name "Imogen" --preview --stl
```

`--preview` is fast (no `trimesh`); `--stl` builds the mesh and takes longer.
Outputs are **auto-filed** into the folders below — no matter which directory
you run from — so the repo root stays tidy.

Per-tool reference docs (all flags, printing settings, design constraints):
[`SKILL_roller.md`](SKILL_roller.md) · [`SKILL_stamp.md`](SKILL_stamp.md) ·
[`SKILL_scraper.md`](SKILL_scraper.md) · [`SKILL_roller_v2.md`](SKILL_roller_v2.md)

---

## Repo structure

```
playdoh_roller.py      roller generator   (RollerConfig)
playdoh_stamp.py       stamp generator    (StampConfig)
playdoh_scraper.py     scraper generator  (ScraperConfig)
svg_processing.py      shared: SVG → mask rasterizer + font loading
mesh_utils.py          shared: watertight mesh helpers (no booleans, no supports)

assets/                decoration SVGs + ATTRIBUTION.md
previews/              generated PNG previews  →  rollers/  stamps/  scrapers/
printable_files/       generated STL / 3MF     →  rollers/  stamps/  scrapers/
archive/               the v2 (engraved) roller experiment

SKILL_roller.md        per-tool reference docs (copies of the registered skills)
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

## Adding a new name

Just pass `--name`. That's it — the preview and STL are named after it and land
in the right subfolder automatically:

```bash
python playdoh_roller.py --name "Freddie" --theme dinosaurs --preview --stl
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
