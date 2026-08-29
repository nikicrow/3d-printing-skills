#!/usr/bin/env bash
#
# sync.sh — keep the three copies of the Play-Doh toolkit in step.
#
# This project lives in three places (see README.md → "How this project is kept
# in sync"). To avoid the drift that comes from hand-editing more than one:
#
#   * source of truth for CODE + ASSETS  = this working copy
#   * source of truth for SKILL DOCS      = the registered ~/.claude/skills files
#
# Edit in the right place, then run this script once to propagate everywhere.
#
#   bash sync.sh
#
set -euo pipefail

ROOT="C:/Users/nikil/3d-printed-playdoh-roller"
MIRROR="$ROOT/3d-printing-skills"
SKILLS="C:/Users/nikil/.claude/skills"

# --- 1) code + assets + README  ->  git mirror --------------------------------
echo "1) code + assets + README  ->  git mirror"
for f in playdoh_roller.py playdoh_stamp.py playdoh_scraper.py dogtag.py \
         svg_processing.py mesh_utils.py README.md _batch.sh sync.sh; do
  cp -f "$ROOT/$f" "$MIRROR/$f"
done
mkdir -p "$MIRROR/assets"
cp -f "$ROOT"/assets/* "$MIRROR/assets/"

# --- 2) registered skill docs  ->  consistent repo copies (root + mirror) ------
echo "2) registered skill docs  ->  SKILL_<tool>.md (root + mirror)"
sync_doc () {  # <skill-dir-name> <dest-basename>
  cp -f "$SKILLS/$1/SKILL.md" "$ROOT/$2"
  cp -f "$SKILLS/$1/SKILL.md" "$MIRROR/$2"
}
sync_doc playdoh-roller    SKILL_roller.md
sync_doc playdoh-stamp     SKILL_stamp.md
sync_doc playdoh-scraper   SKILL_scraper.md
sync_doc playdoh-roller-v2 SKILL_roller_v2.md
sync_doc dogtag            SKILL_dogtag.md

# retire the old inconsistent roller doc name in the mirror, if present
rm -f "$MIRROR/SKILL.md"

echo "done."
echo "note: generated previews/ and printable_files/ are managed separately"
echo "      (large STLs) — they are not copied by this script."
