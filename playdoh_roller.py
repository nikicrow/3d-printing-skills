#!/usr/bin/env python3
"""
playdoh_roller.py
=================
Parametric Play-Doh / clay texture roller generator.

Embosses a NAME lengthways along a cylinder and fills the rest of the surface
with a repeating themed decoration pattern (bees & flowers, dinosaurs, shapes,
cats, fruits). Raised features on the roller push DOWN into the Play-Doh, so
the imprint is the inverse of the roller surface.

Decorations are real, open-licensed silhouette icons rasterized from SVG files
in the ./assets folder (see assets/ATTRIBUTION.md) — NOT hand-drawn shapes.

USAGE
-----
    # Preview PNG of the flattened (unrolled) imprint:
    python playdoh_roller.py --name "Ember" --theme bees_and_flowers --preview

    # Printable STL (base cylinder + raised features + handles):
    python playdoh_roller.py --name "Ember" --theme bees_and_flowers --stl

    # Both at once, with overrides:
    python playdoh_roller.py --name "Mikey" --theme dinosaurs --preview --stl \
        --radius 17.5 --length 90 --emboss 1.8

DEPENDENCIES
------------
    pip install trimesh numpy pillow matplotlib svgpathtools --break-system-packages
    (trimesh is only needed for --stl)

----------------------------------------------------------------------------
3D PRINTING NOTES (read before slicing)
----------------------------------------------------------------------------
  * Print orientation : UPRIGHT / standing on its end — the exported STL is
                        already oriented this way (cylinder axis = Z, sitting on
                        the bed). Each layer is a ring with the relief on its
                        outer wall, so it prints clean with no supports.
  * Handles           : OFF by default (simple barrel only). Pass --handles to
                        add grip stubs at both ends.
  * Supports          : NONE needed. No overhangs in the upright orientation.
  * Layer height      : 0.15mm for best detail (0.20mm acceptable, less crisp).
  * Infill            : 40% (solid-ish body, stays rigid under rolling force).
  * Walls / perimeters: 3 walls minimum so emboss features are fully solid.
  * Material          : PLA recommended. PETG for extra durability / wear.
  * Bambu Studio tip  : Use the "Engineering plate" for adhesion and the
                        0.15mm layer-height preset. A short brim helps the
                        round body stick. Slow the first layer.
  * Emboss design rule: features are >=1.5mm wide and 1.8mm tall — within FFF
                        best practice (raised detail: >0.9mm wide, <2mm high).
----------------------------------------------------------------------------
"""

import argparse
import math
import os
import random

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# ---------------------------------------------------------------------------
# DEFAULT PARAMETERS  (override any of these via CLI args)
# ---------------------------------------------------------------------------
NAME = "Ember"                 # Name to emboss along the roller length
THEME = "bees_and_flowers"     # Decoration theme (see THEMES dict)

ROLLER_RADIUS_MM = 17.5        # 35 mm diameter
ROLLER_LENGTH_MM = 90          # usable imprint length
HANDLE_LENGTH_MM = 22          # each handle end
HANDLE_RADIUS_MM = 10          # comfortable grip
EMBOSS_HEIGHT_MM = 1.8         # raised above the cylinder surface
STAMP_RELIEF_MM = 2.5          # height of the top-end stamp icon (--top-stamp)
RESOLUTION_PPM = 12            # pixels per mm for the internal heightmap
                               # (>=10 keeps detailed icons like the dinos crisp)

# Decoration layout
DECO_GRID_MM = 15.0            # ~1 decoration per 15x15 mm area
DECO_SIZE_MM = 12.0            # longest dimension of a decoration (10-15 mm)
TEXT_DIAMETER_FRACTION = 0.40  # letter height = 40% of roller diameter
MIN_FEATURE_MM = 1.5           # min line width for printability

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(OUT_DIR, "assets")

# Play-Doh-ish preview colours
CREAM = (245, 232, 205)        # background (dough surface)
IMPRINT = (150, 120, 80)       # indentation colour

# Preferred chunky / rounded fonts to try, in order.
FONT_CANDIDATES = [
    "ARLRDBD.TTF",             # Arial Rounded MT Bold (Windows)
    "Arial Rounded MT Bold",
    "Nunito-Bold.ttf",
    "Nunito-ExtraBold.ttf",
    "comicbd.ttf",             # Comic Sans MS Bold (Windows)
    "comic.ttf",               # Comic Sans MS (Windows)
    "Comic Sans MS",
    "arialbd.ttf",             # Arial Bold (decent fallback)
    "DejaVuSans-Bold.ttf",     # cross-platform fallback (PIL ships this)
]

# ===========================================================================
# THEME REGISTRY
# Each theme is a list of (svg_filename, fill_mode) decoration stamps.
#   fill_mode "evenodd" : keep interior holes (single-colour icons)
#   fill_mode "union"   : flatten all sub-paths to one silhouette
#                         (used for multicolour emoji like the dinosaurs/fruit)
# To add a theme: drop bold silhouette SVGs in ./assets and add an entry here.
# ===========================================================================
THEMES = {
    "bees_and_flowers": [("bee.svg", "evenodd"), ("flower.svg", "evenodd")],
    "dinosaurs":        [("trex.svg", "union"), ("brontosaurus.svg", "union")],
    "shapes":           [("circle.svg", "evenodd"), ("square.svg", "evenodd"),
                         ("triangle.svg", "evenodd"), ("star.svg", "evenodd"),
                         ("heart.svg", "evenodd")],
    "cats":             [("cat.svg", "evenodd"), ("paw.svg", "evenodd")],
    "fruits":           [("banana.svg", "union"), ("apple.svg", "union")],
    "trucks":           [("truck.svg", "union"), ("dumptruck.svg", "evenodd")],
}


# ===========================================================================
# SVG -> MASK RASTERIZER  (pure Python; no native cairo needed)
# ---------------------------------------------------------------------------
# svgpathtools parses each <path> (and basic shapes) into segments. We flatten
# every continuous sub-path to a polygon, then composite:
#   even-odd  -> XOR of sub-path fills  (interior holes appear as gaps)
#   union     -> OR  of sub-path fills  (solid silhouette; for multicolour art)
# Rendered at a supersampled size then downscaled for clean, anti-aliased edges.
# ===========================================================================
def rasterize_svg(svg_file, target_px, mode="evenodd",
                  margin=0.06, supersample=3, samples=28):
    from svgpathtools import svg2paths2

    paths, _attrs, svg_attrs = svg2paths2(svg_file)
    vb = svg_attrs.get("viewBox")
    if vb:
        vx, vy, vw, vh = [float(x) for x in vb.replace(",", " ").split()]
    else:
        vx = vy = 0.0
        vw = float(svg_attrs.get("width", 512))
        vh = float(svg_attrs.get("height", 512))

    S = max(8, int(target_px * supersample))
    scale = S * (1 - 2 * margin) / max(vw, vh)
    ox = (S - vw * scale) / 2 - vx * scale
    oy = (S - vh * scale) / 2 - vy * scale

    def tx(p):
        return (p.real * scale + ox, p.imag * scale + oy)

    acc = Image.new("1", (S, S), 0)
    for path in paths:
        for sub in path.continuous_subpaths():
            pts = []
            for seg in sub:
                for i in range(samples):
                    pts.append(tx(seg.point(i / samples)))
            if len(pts) < 3:
                continue
            layer = Image.new("1", (S, S), 0)
            ImageDraw.Draw(layer).polygon(pts, fill=1)
            acc = (ImageChops.logical_or(acc, layer) if mode == "union"
                   else ImageChops.logical_xor(acc, layer))

    # Downscale with anti-aliasing, then re-threshold to a crisp mask.
    mask = acc.convert("L").resize((target_px, target_px), Image.LANCZOS)
    return mask.point(lambda v: 255 if v >= 128 else 0)


def load_theme_stamps(theme, ppm):
    """Rasterize each theme icon once at the decoration size (cached reuse)."""
    deco_px = max(8, int(DECO_SIZE_MM * ppm))
    stamps = []
    for fname, mode in THEMES[theme]:
        path = os.path.join(ASSET_DIR, fname)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing decoration asset: {path}\n"
                f"Expected SVG icons in {ASSET_DIR} (see assets/ATTRIBUTION.md).")
        mask = rasterize_svg(path, deco_px, mode=mode)
        # One gentle dilation step (~1px) to clean edges and nudge hairlines
        # toward the printable minimum WITHOUT blobbing detailed silhouettes.
        if deco_px >= 48:
            mask = mask.filter(ImageFilter.MaxFilter(3))
        # Rotate 90deg CCW so decorations share the name's orientation (the name
        # is rotated the same way to run lengthways along the roller).
        mask = mask.rotate(90, expand=True)
        stamps.append(mask)
    return stamps


# ===========================================================================
# FONT LOADING
# ===========================================================================
def load_font(px_size):
    """Try chunky/rounded fonts; fall back to PIL default."""
    for cand in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(cand, int(px_size)), cand
        except (OSError, IOError):
            continue
    return ImageFont.load_default(), "PIL-default"


# ===========================================================================
# HEIGHTMAP GENERATION
# ===========================================================================
def build_heightmap(name, theme, radius_mm, length_mm, ppm):
    """
    Render the full unrolled cylinder surface to a grayscale heightmap.
    255 = raised feature, 0 = base cylinder surface.

    x axis (width)  = around the circumference (wraps / tiles)
    y axis (height) = along the roller length (the print axis)
    """
    circ_mm = 2 * math.pi * radius_mm
    W = int(round(circ_mm * ppm))
    H = int(round(length_mm * ppm))

    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)

    # ---- TEXT: runs lengthways (along y), centred on the circumference ----
    diameter_mm = 2 * radius_mm
    letter_h_px = TEXT_DIAMETER_FRACTION * diameter_mm * ppm
    length_px = H

    # Find a font size whose rendered text fits: cap height ~ letter_h_px and
    # the word length fits within ~92% of the roller length.
    font, font_name = load_font(letter_h_px)
    size_guess = letter_h_px
    for _ in range(8):
        font, font_name = load_font(size_guess)
        bbox = d.textbbox((0, 0), name, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if th <= 1 or tw <= 1:
            break
        scale_h = letter_h_px / th
        scale_w = (0.92 * length_px) / tw
        scale = min(scale_h, scale_w)
        if abs(scale - 1.0) < 0.02:
            break
        size_guess *= scale

    # Render text horizontally on its own tight canvas, then rotate 90 deg so
    # the word reads ALONG the roller length.
    bbox = d.textbbox((0, 0), name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(0.15 * th) + 4
    timg = Image.new("L", (tw + 2 * pad, th + 2 * pad), 0)
    td = ImageDraw.Draw(timg)
    td.text((pad - bbox[0], pad - bbox[1]), name, font=font, fill=255)
    timg = timg.rotate(90, expand=True)

    # Paste centred on the surface.
    px = (W - timg.width) // 2
    py = (H - timg.height) // 2
    img.paste(timg, (px, py), timg)

    # The circumference band occupied by the text (used to avoid decorations).
    text_x0, text_x1 = px, px + timg.width
    text_margin = int(MIN_FEATURE_MM * 2 * ppm)

    # ---- DECORATIONS: seeded grid in the regions where the name is NOT ----
    stamps = load_theme_stamps(theme, ppm)
    deco_px = stamps[0].width
    step = int(DECO_GRID_MM * ppm)
    rng = random.Random(hash((name, theme)) & 0xFFFFFFFF)

    n_cols = max(1, W // step)            # around circumference (tiles evenly)
    n_rows = max(1, H // step)            # along length
    col_step = W / n_cols
    row_step = H / n_rows
    jitter = 0.18 * step

    for gy in range(n_rows):
        for gx in range(n_cols):
            cx = (gx + 0.5) * col_step
            cy = (gy + 0.5) * row_step
            # Skip cells overlapping the central text band.
            if (text_x0 - text_margin) < cx < (text_x1 + text_margin):
                continue
            jx = rng.uniform(-jitter, jitter)
            jy = rng.uniform(-jitter, jitter)
            stamp = stamps[(gx + gy) % len(stamps)]   # alternation, not random
            tlx = int(cx + jx - deco_px / 2)
            tly = int(cy + jy - deco_px / 2)
            # Paste, wrapping across the circumference seam for clean tiling.
            for wrap in (-W, 0, W):
                img.paste(255, (tlx + wrap, tly), stamp)

    n_deco = sum(
        1 for gy in range(n_rows) for gx in range(n_cols)
        if not ((text_x0 - text_margin) < (gx + 0.5) * col_step
                < (text_x1 + text_margin)))
    return img, font_name, (W, H), n_deco


# ===========================================================================
# OUTPUT MODE 1 — PREVIEW PNG
# ===========================================================================
def make_preview(name, theme, args):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hm, font_name, (W, H), n_deco = build_heightmap(
        name, theme, args.radius, args.length, args.ppm)

    # Colour the flattened dough. v1 (raised roller): the design presses DOWN
    # into the dough -> shown dark/indented on cream. v2 (--engrave, recessed
    # roller): the design stands UP out of the dough -> shown light/raised on a
    # darker pressed background (the colour mapping is simply inverted).
    arr = np.asarray(hm, dtype=np.float32) / 255.0
    base_col, feat_col = (IMPRINT, CREAM) if args.engrave else (CREAM, IMPRINT)
    rgb = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = (base_col[c] * (1 - arr) + feat_col[c] * arr).astype(
            np.uint8)

    circ_mm = 2 * math.pi * args.radius
    aspect = W / H
    fig_h = 7.0
    fig_w = max(5.0, min(14.0, fig_h * aspect))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=130)
    ax.imshow(rgb, extent=[0, circ_mm, 0, args.length], origin="lower")
    ax.set_xlabel("around circumference (mm)")
    ax.set_ylabel("along roller length (mm)")
    tag = "  (v2 · raised imprint)" if args.engrave else ""
    ax.set_title(f"ROLLER PREVIEW — {name} / {theme}{tag}",
                 fontsize=15, fontweight="bold", pad=12)
    caption = ("This is the RAISED Play-Doh imprint from the engraved roller "
               "(shown flat)" if args.engrave else
               "This is what the Play-Doh imprint will look like (shown flat)")
    fig.text(0.5, 0.015, caption, ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(top=0.90, bottom=0.12)

    suffix = "_v2" if args.engrave else ""
    safe_name = name.lower().replace(" ", "_")
    out = os.path.join(OUT_DIR, f"preview_{safe_name}_{theme}{suffix}.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"[preview] font={font_name}  surface={W}x{H}px  "
          f"decorations={n_deco}")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# TOP-END STAMP  — raise one theme icon out of the upright roller's top face,
# turning that end into a cute press-stamp. Built as a displaced polar disk that
# SHARES the body's end ring, so it stays part of the single watertight solid
# (no booleans needed). The top face is the x=0 end (which becomes the UP end
# once the roller is stood upright); the icon bumps OUTWARD to x = -relief.
# ===========================================================================
def _top_stamp_geometry(theme, R, relief, ppm, n_theta, thetas, start_index,
                        stamp_icon=None):
    # default to the theme's first icon; --stamp-icon picks a specific one
    fname, mode = THEMES[theme][0]
    if stamp_icon:
        want = stamp_icon if stamp_icon.endswith(".svg") else stamp_icon + ".svg"
        for f, mo in THEMES[theme]:
            if f == want:
                fname, mode = f, mo
                break
        else:
            fname, mode = want, "evenodd"   # allow any asset in assets/
    size_img = max(64, int(2 * R * ppm))
    mask = rasterize_svg(os.path.join(ASSET_DIR, fname), size_img,
                         mode=mode, margin=0.18)   # extra margin -> fits disk
    M = np.asarray(mask) > 127
    himg, wimg = M.shape
    K = max(8, int(R * ppm * 0.6))          # number of radial rings
    ct = np.cos(thetas)
    st = np.sin(thetas)

    # Interior rings k=1..K-1 (radius R -> 0), vectorised.
    ks = np.arange(1, K)
    r_k = (R * (K - ks) / K)[:, None]       # (K-1, 1)
    Y = r_k * ct[None, :]                    # (K-1, n_theta)
    Z = r_k * st[None, :]
    U = np.clip(np.round((0.5 + 0.5 * (Y / R)) * (wimg - 1)).astype(int),
                0, wimg - 1)
    V = np.clip(np.round((0.5 + 0.5 * (Z / R)) * (himg - 1)).astype(int),
                0, himg - 1)
    Xr = np.where(M[V, U], -relief, 0.0)     # raised outward from the x=0 end
    verts = np.stack([Xr.ravel(), Y.ravel(), Z.ravel()], axis=1)
    center_on = M[(himg - 1) // 2, (wimg - 1) // 2]
    verts = np.vstack([verts, [[-relief if center_on else 0.0, 0.0, 0.0]]])
    center_idx = start_index + (K - 1) * n_theta

    def ring_base(k):
        return 0 if k == 0 else start_index + (k - 1) * n_theta

    I = np.arange(n_theta)
    I2 = (I + 1) % n_theta
    parts = []
    for k in range(K - 1):                   # ~K iters of vectorised stacks
        b0, b1 = ring_base(k), ring_base(k + 1)
        a, b = b0 + I, b0 + I2
        c, d = b1 + I, b1 + I2
        parts.append(np.stack([a, d, b], axis=1))   # winding fixed by normals
        parts.append(np.stack([a, c, d], axis=1))
    bK = ring_base(K - 1)
    parts.append(np.stack([bK + I, np.full(n_theta, center_idx), bK + I2],
                          axis=1))
    return verts, np.concatenate(parts)


# ===========================================================================
# OUTPUT MODE 2 — STL
# ===========================================================================
def make_stl(name, theme, args):
    import trimesh

    hm, font_name, (W, H), n_deco = build_heightmap(
        name, theme, args.radius, args.length, args.ppm)
    height = np.asarray(hm, dtype=np.float32) / 255.0   # 0..1 raised mask

    R = args.radius
    L = args.length
    E = args.emboss

    # Displaced-cylinder grid. (This is the efficient, watertight equivalent of
    # "add a radial prism per raised pixel": vertices on raised texels sit at
    # R+E, everything else at R, so features extrude OUTWARD as required.)
    n_theta = min(W, 720)        # around circumference (wrapped)
    n_z = min(H, 720)            # along the axis (X)

    thetas = np.linspace(0.0, 2 * math.pi, n_theta, endpoint=False)
    zs = np.linspace(0.0, L, n_z)

    # Sample the heightmap onto the grid (nearest).
    sx = (np.linspace(0, W - 1, n_theta)).astype(int)   # circumference -> x
    sy = (np.linspace(0, H - 1, n_z)).astype(int)       # length -> y
    samp = height[np.ix_(sy, sx)]                        # shape (n_z, n_theta)
    # v1: features bump OUTWARD (R+E). v2 (--engrave): features are recessed
    # INWARD (R-E) so the dough comes out raised instead of indented.
    sign = -1.0 if args.engrave else 1.0
    radii = R + sign * E * (samp > 0.5)                  # (n_z, n_theta)
    if args.top_stamp:
        radii[0, :] = R   # clean circular ring on the stamped (x=0) end

    # Build vertices (vectorised). Axis = X, cross-section in (Y, Z). A centre
    # point is added at each end so the textured surface CLOSES INTO A SINGLE
    # WATERTIGHT SOLID. (The earlier design left this as an open tube on a
    # separate core, which slicers saw as zero-thickness "floating" features
    # that didn't print. Capping the ends makes every bump a real protrusion.)
    ct = np.cos(thetas)
    st = np.sin(thetas)
    grid = np.empty((n_z * n_theta, 3), dtype=np.float64)
    grid[:, 0] = np.repeat(zs, n_theta)
    grid[:, 1] = (radii * ct[None, :]).ravel()
    grid[:, 2] = (radii * st[None, :]).ravel()
    c0 = n_z * n_theta            # centre of the x=0 end
    c1 = n_z * n_theta + 1        # centre of the x=L end
    verts = np.vstack([grid, [[0.0, 0.0, 0.0]], [[L, 0.0, 0.0]]])

    # Side faces (quads -> 2 triangles), wrapping in theta (vectorised).
    J, I = np.meshgrid(np.arange(n_z - 1), np.arange(n_theta), indexing="ij")
    I2 = (I + 1) % n_theta
    a = J * n_theta + I
    b = J * n_theta + I2
    c = (J + 1) * n_theta + I
    dd = (J + 1) * n_theta + I2
    side = np.concatenate([
        np.stack([a, b, dd], axis=-1).reshape(-1, 3),
        np.stack([a, dd, c], axis=-1).reshape(-1, 3)])

    # Bed end (x=L) -> flat fan to its centre point.
    Iv = np.arange(n_theta)
    Iv2 = (Iv + 1) % n_theta
    top = (n_z - 1) * n_theta
    bed = np.stack([np.full(n_theta, c1), top + Iv2, top + Iv], axis=1)

    face_parts = [side, bed]
    # Stamp end (x=0): either a raised icon stamp disk, or a plain flat fan.
    if args.top_stamp:
        sv, sf = _top_stamp_geometry(theme, R, args.stamp_relief, args.ppm,
                                     n_theta, thetas, start_index=c1 + 1,
                                     stamp_icon=args.stamp_icon)
        verts = np.vstack([verts, sv])
        face_parts.append(sf)
    else:
        face_parts.append(np.stack([np.full(n_theta, c0), Iv, Iv2], axis=1))

    faces = np.concatenate(face_parts)
    # Watertightness comes from topology (every edge is shared by 2 faces via
    # shared vertex indices), so we skip trimesh's expensive normal/merge passes
    # (fix_normals builds a face-adjacency graph over >1M faces -> minutes).
    # Normal winding is left for the slicer to auto-repair on import.
    body = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    parts = [body]

    # Optional grip handles beyond each end (off by default — kept simple).
    if args.handles:
        hl, hr = args.handle_length, args.handle_radius
        h1 = trimesh.creation.cylinder(radius=hr, height=hl, sections=64)
        h1.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi / 2, [0, 1, 0]))
        h1.apply_translation([-hl / 2 + 0.5, 0, 0])     # slight overlap
        h2 = trimesh.creation.cylinder(radius=hr, height=hl, sections=64)
        h2.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi / 2, [0, 1, 0]))
        h2.apply_translation([L + hl / 2 - 0.5, 0, 0])
        parts += [h1, h2]

    combined = trimesh.util.concatenate(parts) if len(parts) > 1 else body

    # Stand the roller UPRIGHT on its end (axis -> Z) for easy, support-free
    # printing: every layer is a ring with the relief on its outer wall, so
    # there are no overhangs and the round body never rests on the bed.
    combined.apply_transform(trimesh.transformations.rotation_matrix(
        math.pi / 2, [0, 1, 0]))
    b = combined.bounds
    combined.apply_translation([-(b[0, 0] + b[1, 0]) / 2,     # centre X
                                -(b[0, 1] + b[1, 1]) / 2,     # centre Y
                                -b[0, 2]])                    # sit on z=0

    suffix = "_v2" if args.engrave else ""
    safe_name = name.lower().replace(" ", "_")
    out = os.path.join(OUT_DIR, f"roller_{safe_name}_{theme}{suffix}.stl")
    combined.export(out)
    wt = "watertight" if combined.is_watertight else "NOT watertight"
    print(f"[stl] font={font_name}  decorations={n_deco}  "
          f"verts={len(combined.vertices)}  faces={len(combined.faces)}  {wt}")
    print(f"[stl] saved -> {out}")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def main():
    p = argparse.ArgumentParser(description="Parametric Play-Doh roller maker")
    p.add_argument("--name", default=NAME)
    p.add_argument("--theme", default=THEME, choices=list(THEMES.keys()))
    p.add_argument("--radius", type=float, default=ROLLER_RADIUS_MM)
    p.add_argument("--length", type=float, default=ROLLER_LENGTH_MM)
    p.add_argument("--handles", action="store_true",
                   help="add grip handles at both ends (off by default)")
    p.add_argument("--handle-length", type=float, default=HANDLE_LENGTH_MM)
    p.add_argument("--handle-radius", type=float, default=HANDLE_RADIUS_MM)
    p.add_argument("--emboss", type=float, default=EMBOSS_HEIGHT_MM)
    p.add_argument("--engrave", action="store_true",
                   help="v2: recess the name/decorations INTO the roller so the "
                        "dough imprint comes out RAISED. Outputs get a _v2 "
                        "suffix.")
    p.add_argument("--top-stamp", action="store_true",
                   help="raise the theme's first icon out of the roller's top "
                        "end so it doubles as a press-stamp")
    p.add_argument("--stamp-relief", type=float, default=STAMP_RELIEF_MM,
                   help="height of the top-end stamp icon in mm")
    p.add_argument("--stamp-icon", default=None,
                   help="which asset to use for the top stamp (e.g. star, heart, "
                        "bee); defaults to the theme's first icon")
    p.add_argument("--ppm", type=int, default=RESOLUTION_PPM)
    p.add_argument("--preview", action="store_true", help="write preview PNG")
    p.add_argument("--stl", action="store_true", help="write printable STL")
    args = p.parse_args()

    if not (args.preview or args.stl):
        p.error("choose at least one of --preview / --stl")

    if args.preview:
        make_preview(args.name, args.theme, args)
    if args.stl:
        make_stl(args.name, args.theme, args)


if __name__ == "__main__":
    main()
