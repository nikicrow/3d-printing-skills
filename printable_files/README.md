# Printable files

Ready-to-slice **STL files for the whole collection**, split by type:

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
