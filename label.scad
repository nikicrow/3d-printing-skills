// ============================================================================
// namelabel.scad  —  parametric two-colour name keychain label
// ============================================================================
// A cute, bubbly name tag for a kid's school bag / party favour, designed to
// waste as little filament as possible by splitting the two colours BY HEIGHT:
//
//   * BOTTOM band (0 .. border_h)            -> border colour: the full "trace"
//       outline (a rounded offset around the name + icon) plus the keychain
//       tab. It is the only thing in the bottom band, so it reads as the border.
//   * TOP band (border_h .. border_h+font_h) -> name colour: ONLY the letters
//       (and the optional theme icon) raised on top of the plate.
//
// Because the name colour exists only where the letters are, and only in the
// thin top band, it uses almost no second-colour filament. On a single-extruder
// Bambu (A1 / P1 / X1) this prints perfectly with ONE filament change at
// Z = border_h. In Bambu Studio / MakerWorld the two top-level color() objects
// at the bottom are exported as two coloured parts, each mapping to a filament.
//
// Layout: [ keychain hole ] [ optional icon ] [ NAME -> ]. The hole and icon
// sit on the left with fixed, known sizes; the name grows to the right, so the
// model never needs to measure text width and renders identically on the
// MakerWorld OpenSCAD and older local builds alike.
//
// MakerWorld: upload this file together with the assets/ folder to the
// Parametric Model Maker. Every variable in the labelled sections becomes a
// customiser control (type a name, pick a font, colours and an icon).
// ============================================================================

/* [Name] */
// The name to print
name = "Ember";
// Bubbly font (all bundled in assets/fonts, open licensed)
font = "Baloo 2"; // [Baloo 2, Bagel Fat One, Titan One, Chewy, Lilita One, Bubblegum Sans]

/* [Colours] */
// Top layer — the letters
name_color = "#2b2b2b";   // color
// Bottom layer — the border / trace
border_color = "#f2ead6"; // color

/* [Theme icon] */
// A little themed shape leading the name (none = name only)
icon = "none"; // [none, bee, heart, star, flower, paw, cat, apple, car, truck, banana]
// Icon size relative to the letter height (1 = same cap height)
icon_scale = 1.15; // [0.6:0.05:1.8]

/* [Size — mm] */
// Cap height of the letters
letter_height = 16;    // [8:1:40]
// How far the border extends past the letters (the trace thickness)
border_width = 3.0;    // [1.0:0.5:8.0]
// Rounding of the border outline (bubblier = higher)
corner_round = 1.5;    // [0:0.5:6]
// Bottom (border colour) layer thickness
border_h = 1.6;        // [0.8:0.2:4.0]
// Top (name colour) layer thickness
font_h = 2.0;          // [0.8:0.2:4.0]

/* [Keychain] */
// Add a tab with a hole for a clasp / split ring
keychain = true;
// Hole diameter for the clasp
hole_d = 5.0;          // [2:0.5:10]
// Ring wall between the hole edge and the tab edge
hole_wall = 2.5;       // [1.5:0.5:5]

/* [Quality] */
// Smoothness of curves (higher = smoother, slower)
smoothness = 72;       // [24:8:160]

/* [Hidden] */
$fn = smoothness;
EPS = 0.02;

// OpenSCAD text size is the font em, not the cap height. ~0.72·em ≈ cap height
// for these rounded faces, so scale the em to land letter_height on target.
CAP_RATIO = 0.72;
text_size = letter_height / CAP_RATIO;

// Bundled SVG icon viewBox size (px) so every icon normalises to letter height.
function icon_vb(n) = (n == "bee") ? 32 : 24;   // the rest are 24x24
icon_w = letter_height * icon_scale;             // ~square icon footprint (mm)
gap    = border_width;                           // small gap; the border merges

// Left edge of the "content" (name, or icon if present), in mm.
content_left = (icon == "none") ? 0 : -(icon_w + gap);
// Keychain tab geometry, anchored just left of the content.
tab_r  = hole_d/2 + hole_wall;
tab_cx = content_left - border_width - tab_r*0.6;

// ---- 2D building blocks -------------------------------------------------
module name2d() {
    // left edge on x=0, vertical centre on y=0; the name extends to +x.
    text(name, font = font, size = text_size,
         halign = "left", valign = "center", $fn = $fn);
}

module icon2d() {
    if (icon != "none") {
        s = icon_w / icon_vb(icon);              // px -> mm
        // SVG y-axis points down; mirror Y so the icon is upright. Centre the
        // icon footprint on (content_left + icon_w/2, 0).
        translate([content_left + icon_w/2, 0])
            scale([s, -s])
                import(str("assets/", icon, ".svg"), center = true);
    }
}

// Name + optional icon — the raised (name-colour) silhouette.
module content2d() {
    name2d();
    icon2d();
}

module tab_blob() { translate([tab_cx, 0]) circle(r = tab_r); }
module tab_hole() { translate([tab_cx, 0]) circle(d = hole_d); }

// A thin connector spine along the vertical centre (y=0). Offsetting it by the
// border width turns it into a smooth neck that fuses the keychain tab, the
// icon and the first letter into ONE plate — so connectivity never depends on
// exact glyph bearings or icon spacing. It is added to the base (border) layer
// only; the raised name layer stays as distinct letters + icon.
module connector2d() {
    if (keychain || icon != "none") {
        x0 = keychain ? tab_cx : content_left;
        x1 = text_size * 0.40;              // reach safely inside the 1st glyph
        translate([x0, -border_width * 0.25])
            square([x1 - x0, border_width * 0.5]);
    }
}

// Rounded outward offset of the content (+connector) = the border "trace".
module border2d() {
    offset(r = corner_round)
        offset(delta = border_width - corner_round)
            union() { content2d(); connector2d(); }
}

// Full bottom plate outline: the border trace, merged with the keychain tab.
module plate2d() {
    union() {
        border2d();
        if (keychain) tab_blob();
    }
}

// ---- 3D parts -----------------------------------------------------------
module base_part() {                     // bottom band = border colour
    linear_extrude(height = border_h)
        difference() {
            plate2d();
            if (keychain) tab_hole();
        }
}

module name_part() {                     // top band = name colour (letters+icon)
    translate([0, 0, border_h - EPS])
        linear_extrude(height = font_h + EPS)
            content2d();
}

// ---- assembly (two coloured, top-level objects) -------------------------
color(border_color) base_part();
color(name_color)   name_part();
