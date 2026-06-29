# Archive

Experiments that were tried but are **not** the chosen design. Kept for
reference only — the active/production version lives at the repo root.

## `v2/` — engraved (raised-imprint) roller

An alternative where the name + decorations were **recessed into** the roller
(`--engrave`), so the Play-Doh came out **raised/embossed** instead of indented.

**Decision: we went with the original (v1).** After printing and trying both,
people preferred the original raised-roller / indented-imprint version. v2 is
archived here so the choice is clear when revisiting the repo.

Contents:
- `SKILL_v2.md` — the v2 skill doc
- `printable_files/` — the v2 STLs (`roller_*_v2.stl`)
- `previews/` — the v2 previews (`preview_*_v2.png`)

The code path still exists in `playdoh_roller.py` via the `--engrave` flag if you
ever want to regenerate a v2 roller, but the default (no flag) produces the
chosen original design.
