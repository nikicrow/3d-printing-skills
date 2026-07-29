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
font = "Grandstander"; // [Grandstander, Baloo 2, Bagel Fat One, Titan One, Chewy, Lilita One, Bubblegum Sans]

/* [Colours] */
// Top layer — the letters
name_color = "#2b2b2b";   // color
// Bottom layer — the border / trace
border_color = "#f2ead6"; // color

/* [Theme icon] */
// A little themed shape leading the name (none = name only)
icon = "none"; // [none, bee, heart, star, flower, paw, cat, apple, car, truck, banana, brontosaurus, trex, circle, square, triangle]
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
// 45° chamfer on the TOP face of both bands — the plate rim and the raised
// name. It takes the sharp arris off every edge a small hand touches. Both
// undersides deliberately stay square: a chamfer under the plate would shrink
// the first-layer footprint and cost bed adhesion, and one under the name would
// taper the letters away from the plate, leaving a groove around every glyph.
bevel = 0.3;           // [0:0.1:1.5]
// Facets used to approximate the chamfer. Each step adds two more inset slabs
// to the union, and that union is what costs render time — 1 gives a plain 45°
// facet, which is plenty at this size. Raise it only for a rounder edge, and
// only on the Manifold backend (OpenSCAD 2023+/MakerWorld); on the old CGAL
// backend each extra step roughly doubles the render.
bevel_steps = 1;       // [1:1:4]

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
// OpenSCAD imports an SVG at its viewBox units, so this is the divisor that
// scales the art into `icon_w` mm — and a wrong entry mis-sizes the icon by the
// ratio of the two (a 128-unit icon treated as 24 comes out >5x too big). Every
// bundled icon is listed; add a row whenever you add an SVG.
icon_vb_table = [
    ["apple", 128], ["banana", 128], ["bee", 32], ["brontosaurus", 128],
    ["car", 128], ["cat", 24], ["circle", 24], ["flower", 24], ["heart", 24],
    ["paw", 15], ["square", 24], ["star", 24], ["trex", 128],
    ["triangle", 24], ["truck", 128],
];
function icon_vb(n) =
    let (hit = search([n], icon_vb_table)[0])
    (is_undef(hit) || hit == []) ? 24 : icon_vb_table[hit][1];
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
        // OpenSCAD's SVG import already orients the art upright (Y is handled),
        // so scale uniformly — no extra mirror. Centre the icon footprint on
        // (content_left + icon_w/2, 0).
        translate([content_left + icon_w/2, 0])
            scale([s, s])
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

// A chamfered extrude that PRESERVES holes and concavity (unlike hull): each
// chamfered face's `c` mm is built as a short stack of inward-offset slabs,
// approximating a 45° bevel on every edge (outer rim and the keychain hole).
// `do_bottom` / `do_top` pick which faces get the chamfer. Both label bands use
// top-only (see the `bevel` note above), but the module stays general.
module bevel_extrude(h, c, steps = 1, do_bottom = true, do_top = true) {
    faces = (do_bottom ? 1 : 0) + (do_top ? 1 : 0);
    cc = (faces == 0) ? 0 : min(c, h / faces - 0.02);
    cb = do_bottom ? cc : 0;
    ct = do_top ? cc : 0;
    if (cc <= 0) {
        linear_extrude(height = h) children();
    } else {
        step = cc / steps;
        // Full-section core. It overlaps the chamfer slabs by 0.01 to avoid
        // coincident faces, but only on a face that HAS one — otherwise the
        // core would poke 0.01 mm past the model (and below Z=0 on the plate).
        z0 = do_bottom ? cb - 0.01 : 0;
        z1 = do_top ? h - ct + 0.01 : h;
        translate([0, 0, z0]) linear_extrude(height = z1 - z0) children();
        for (k = [0 : steps - 1]) {
            inset = cc - k * step;                 // most eroded at the faces
            if (do_bottom)
                translate([0, 0, k * step])            // bottom chamfer, rising
                    linear_extrude(height = step + 0.01) offset(r = -inset) children();
            if (do_top)                                // top chamfer, falling
                translate([0, 0, h - (k + 1) * step - 0.01])
                    linear_extrude(height = step + 0.01) offset(r = -inset) children();
        }
    }
}

// ---- 3D parts -----------------------------------------------------------
module base_shape2d() {
    difference() {
        plate2d();
        if (keychain) tab_hole();
    }
}

module base_part() {                     // bottom band = border colour
    bevel_extrude(border_h, bevel, bevel_steps, do_bottom = false)
        base_shape2d();
}

module name_part() {                     // top band = name colour (letters+icon)
    translate([0, 0, border_h - EPS])
        bevel_extrude(font_h + EPS, bevel, bevel_steps, do_bottom = false)
            content2d();
}

// ---- assembly (two coloured, top-level objects) -------------------------
color(border_color) base_part();
color(name_color)   name_part();
