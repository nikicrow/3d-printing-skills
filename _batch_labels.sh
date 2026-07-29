#!/usr/bin/env bash
# Generate a name keychain label for every guest on the party list.
#
# Icons follow each child's roller theme in _batch.sh (dinosaurs -> trex /
# brontosaurus, and so on), varied a little within a theme so siblings don't end
# up with identical tags. The bees_and_flowers children all take the flower: at
# label scale the bee's legs and antennae read as a fussy blob rather than a bee.
#
# Writes previews/labels/preview_*.png and printable_files/labels/*_mesh.3mf.
# Add --stl if you also want a single-extruder STL (print it with a filament
# change at Z = border_h).
set -e

gen() { # name icon
  python playdoh_label.py --name "$1" --icon "$2" --preview --3mf \
    >/dev/null 2>&1 && echo "OK  $1 / $2"
}

gen Ember   flower         # bees_and_flowers
gen Imogen  heart          # shapes
gen Leo     truck          # trucks
gen Mikey   trex           # dinosaurs
gen Zoey    cat            # cats
gen Lincoln brontosaurus   # dinosaurs
gen Hazel   star           # shapes
gen Caleb   car            # trucks
gen Grace   flower         # bees_and_flowers
gen Beau    triangle       # shapes
gen Billie  paw            # cats
gen Indie   heart          # shapes (same as Imogen, by request)
gen Annie   flower         # bees_and_flowers
echo "BATCH DONE"
