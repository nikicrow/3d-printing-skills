# Printable files

Ready-to-slice files for the whole collection, split by type:

- [`labels/`](labels) — two-colour **keychain name labels**, named
  `label_<name>[_<icon>].{stl,3mf}`. A single connected, watertight solid ~3.6 mm
  thick (border band + raised name band). Print the **STL** with a filament
  change at `Z = border_h` (1.6 mm), or the **3MF** as two colour parts on
  AMS/MakerWorld. Regenerate/add with `namelabel.py --stl` / `--3mf`.
- [`rollers/`](rollers) — texture rollers, named `roller_<name>_<theme>.stl`
  (plus Ember's `.3mf`). Each is a single watertight, upright, support-free
  solid with a top-end press-stamp. Large (~60 MB each). Regenerate/add with
  `playdoh_roller.py --stl`.
- [`stamps/`](stamps) — name stamps, named `stamp_<name>.stl`. Compact
  (~8–11 MB), face-down and support-free, with a cylinder grip and chamfered
  edges. Regenerate/add with `playdoh_stamp.py --stl`.
- [`scrapers/`](scrapers) — name scrapers, named `scraper_<name>.stl`. Low wedge
  with a blunt front edge and the name raised on the back platform; flat base,
  support-free (~52 MB at ppm=6). Regenerate/add with `playdoh_scraper.py --stl`.

Git LFS is an option if the roller STLs make the repo unwieldy.
