# Bundled font attribution

The bubbly display fonts bundled here are all free/open-licensed (SIL Open Font
License 1.1 or Apache 2.0), so they are safe to redistribute with this repo and
to upload alongside `label.scad` to MakerWorld. Each is a Google Fonts family;
the TTF is the upstream file from the [google/fonts](https://github.com/google/fonts)
repository.

| File | Family | Designer | License |
|---|---|---|---|
| Baloo2.ttf | Baloo 2 | Ek Type | OFL 1.1 |
| BagelFatOne.ttf | Bagel Fat One | Snadhan / Fontfabric | OFL 1.1 |
| TitanOne.ttf | Titan One | Rodrigo Fuenzalida | OFL 1.1 |
| Chewy.ttf | Chewy | Sideshow | Apache 2.0 |
| LilitaOne.ttf | Lilita One | Juan Montoreano | OFL 1.1 |
| BubblegumSans.ttf | Bubblegum Sans | Angel Koziupa / Sorkin Type | OFL 1.1 |

To add another font: drop the `.ttf` here, add its family to `FONTS` in
`namelabel.py` and to the `font` dropdown in `label.scad`, and record it above.
The OpenSCAD `text(font=...)` call resolves the family **name** (e.g. "Baloo 2"),
so the string must match the font's internal family name, not the filename.
Set `OPENSCAD_FONT_PATH` to this folder (the runner does this automatically).
