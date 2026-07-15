set -e
gen() { # name theme [stampicon]
  if [ -n "$3" ]; then ic="--stamp-icon $3"; else ic=""; fi
  python playdoh_roller.py --name "$1" --theme "$2" --top-stamp $ic --preview --stl >/dev/null 2>&1 && echo "OK  $1 / $2"
}
gen Ember   bees_and_flowers
gen Imogen  shapes star
gen Leo     trucks
gen Mikey   dinosaurs
gen Zoey    cats
gen Lincoln dinosaurs
gen Hazel   shapes star
gen Caleb   trucks
gen Grace   bees_and_flowers
gen Beau    shapes star
gen Billie  cats
gen Indie   shapes star
gen Annie   bees_and_flowers
echo "BATCH DONE"
