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

ARCHITECTURE
------------
This file owns the roller-specific logic: the parameter schema
(:class:`RollerConfig`), the theme registry, the heightmap layout, and the two
output modes (preview PNG / printable STL). The reusable, project-agnostic
building blocks live in sibling modules so future generators can share them:

  * ``svg_processing`` — SVG → mask rasterizer and font loading.
  * ``mesh_utils``     — heightmap → watertight cylinder mesh, end stamps,
                         handles, and the upright print transform.

All tunable parameters are collected and validated up front in
:class:`RollerConfig` (a pydantic model). This catches bad inputs immediately —
important now that AI agents drive these generators — and gives every new tool
a consistent, self-documenting config surface.

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
    pip install trimesh numpy pillow matplotlib svgpathtools pydantic \
        --break-system-packages
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
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
)

from mesh_utils import axial_handles, build_roller_mesh, stand_upright_on_end
from svg_processing import load_font, rasterize_svg

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(OUT_DIR, "assets")

# Play-Doh-ish preview colours
CREAM = (245, 232, 205)        # background (dough surface)
IMPRINT = (150, 120, 80)       # indentation colour

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
    "trucks":           [("truck.svg", "union"), ("car.svg", "union")],
}


# ===========================================================================
# PARAMETER SCHEMA
# All tunable parameters, validated up front with sensible defaults. The old
# module-level constants now live here as fields so every value the roller
# pipeline needs is declared, type-checked and range-checked in one place.
# ===========================================================================
class RollerConfig(BaseModel):
    """Validated parameters for one Play-Doh roller generation run.

    Construct directly (``RollerConfig(name="Ember", theme="cats")``) or from
    parsed CLI args (see :func:`config_from_args`). Out-of-range or unknown
    values raise ``pydantic.ValidationError`` immediately, so a misconfigured
    run fails fast instead of producing a bad STL.

    Attributes
    ----------
    name : str
        Name embossed lengthways along the roller barrel. Must be non-empty.
    theme : str
        Decoration theme; one of the keys of :data:`THEMES`.
    radius_mm : float
        Roller barrel radius in mm (default 17.5 → 35 mm diameter).
    length_mm : float
        Usable imprint length in mm.
    handles : bool
        Add grip handles at both ends (off by default → simple barrel).
    handle_length_mm : float
        Length of each handle stub in mm.
    handle_radius_mm : float
        Handle grip radius in mm.
    emboss_mm : float
        How far text/decorations rise above (or, with ``engrave``, sink below)
        the barrel surface, in mm.
    engrave : bool
        v2 mode: recess the name/decorations INTO the roller so the dough
        imprint comes out RAISED. Outputs get a ``_v2`` suffix.
    top_stamp : bool
        Raise the theme's first icon out of the roller's top end so it doubles
        as a press-stamp (STL only).
    stamp_relief_mm : float
        Height of the top-end stamp icon in mm.
    stamp_icon : str or None
        Which asset to use for the top stamp (e.g. ``"star"``); defaults to the
        theme's first icon when ``None``.
    ppm : int
        Heightmap resolution in pixels per mm (>=10 keeps detailed icons crisp;
        lower is faster/rougher).
    deco_grid_mm : float
        Spacing of the decoration grid in mm (~1 decoration per cell).
    deco_size_mm : float
        Longest dimension of a single decoration in mm.
    text_diameter_fraction : float
        Letter height as a fraction of the roller diameter (0–1].
    min_feature_mm : float
        Minimum line width in mm, for printability.
    asset_dir : str
        Directory holding the decoration SVG files.
    out_dir : str
        Directory the preview PNG / STL files are written to.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # ---- decoration / identity ----
    name: str = Field("Ember", min_length=1)
    theme: str = "bees_and_flowers"

    # ---- barrel geometry ----
    radius_mm: float = Field(17.5, gt=0)
    length_mm: float = Field(90.0, gt=0)

    # ---- handles ----
    handles: bool = False
    handle_length_mm: float = Field(22.0, gt=0)
    handle_radius_mm: float = Field(10.0, gt=0)

    # ---- relief ----
    emboss_mm: float = Field(1.8, gt=0)
    engrave: bool = False

    # ---- top-end stamp ----
    top_stamp: bool = False
    stamp_relief_mm: float = Field(2.5, gt=0)
    stamp_icon: Optional[str] = None

    # ---- resolution / layout ----
    ppm: int = Field(12, ge=1)
    deco_grid_mm: float = Field(15.0, gt=0)
    deco_size_mm: float = Field(12.0, gt=0)
    text_diameter_fraction: float = Field(0.40, gt=0, le=1.0)
    min_feature_mm: float = Field(1.5, gt=0)

    # ---- paths ----
    asset_dir: str = ASSET_DIR
    out_dir: str = OUT_DIR

    @field_validator("theme")
    @classmethod
    def _known_theme(cls, v: str) -> str:
        if v not in THEMES:
            raise ValueError(
                f"unknown theme {v!r}; choose one of {sorted(THEMES)}")
        return v

    @property
    def safe_name(self) -> str:
        """str: ``name`` lowercased with spaces collapsed to underscores."""
        return self.name.lower().replace(" ", "_")

    @property
    def suffix(self) -> str:
        """str: filename suffix (``"_v2"`` in engrave mode, else ``""``)."""
        return "_v2" if self.engrave else ""


# ===========================================================================
# THEME STAMP LOADING
# ===========================================================================
def load_theme_stamps(cfg):
    """Rasterize each icon of a theme once, at the decoration size.

    Parameters
    ----------
    cfg : RollerConfig
        Run configuration; ``theme``, ``deco_size_mm``, ``ppm`` and
        ``asset_dir`` select and size the icons.

    Returns
    -------
    list of PIL.Image.Image
        One binary stamp mask per icon in the theme, dilated slightly when
        large and rotated 90° CCW so decorations share the name's lengthways
        orientation.

    Raises
    ------
    FileNotFoundError
        If a theme's SVG asset is missing from ``cfg.asset_dir``.
    """
    deco_px = max(8, int(cfg.deco_size_mm * cfg.ppm))
    stamps = []
    for fname, mode in THEMES[cfg.theme]:
        path = os.path.join(cfg.asset_dir, fname)
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Missing decoration asset: {path}\n"
                f"Expected SVG icons in {cfg.asset_dir} "
                f"(see assets/ATTRIBUTION.md).")
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
# HEIGHTMAP GENERATION
# ===========================================================================
def build_heightmap(cfg):
    """Render the full unrolled cylinder surface to a grayscale heightmap.

    255 = raised feature, 0 = base cylinder surface.

    The x axis (width) runs around the circumference and wraps/tiles; the y
    axis (height) runs along the roller length (the print axis). The name is
    rendered horizontally, auto-sized to fit, then rotated 90° so it reads
    lengthways and centred on the circumference; themed decorations fill a
    seeded, jittered grid everywhere the name is not, wrapping across the seam
    so the pattern tiles cleanly.

    Parameters
    ----------
    cfg : RollerConfig
        Run configuration (name, theme, geometry, resolution and layout).

    Returns
    -------
    img : PIL.Image.Image
        Mode-``"L"`` heightmap of size ``(W, H)``.
    font_name : str
        The font that was used to render the name.
    size : tuple of int
        ``(W, H)`` of the heightmap in pixels.
    n_deco : int
        Number of decoration cells placed (text-band cells excluded).
    """
    name = cfg.name
    radius_mm = cfg.radius_mm
    ppm = cfg.ppm

    circ_mm = 2 * math.pi * radius_mm
    W = int(round(circ_mm * ppm))
    H = int(round(cfg.length_mm * ppm))

    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)

    # ---- TEXT: runs lengthways (along y), centred on the circumference ----
    diameter_mm = 2 * radius_mm
    letter_h_px = cfg.text_diameter_fraction * diameter_mm * ppm
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
    text_margin = int(cfg.min_feature_mm * 2 * ppm)

    # ---- DECORATIONS: seeded grid in the regions where the name is NOT ----
    stamps = load_theme_stamps(cfg)
    deco_px = stamps[0].width
    step = int(cfg.deco_grid_mm * ppm)
    rng = random.Random(hash((name, cfg.theme)) & 0xFFFFFFFF)

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
def make_preview(cfg):
    """Render the flattened (unrolled) dough imprint to a PNG.

    Colours the unrolled surface Play-Doh cream with the imprinted areas in a
    darker "indented" tone (the mapping inverts under ``cfg.engrave``, where the
    design stands up out of the dough instead). Writes
    ``preview_<name>_<theme>[_v2].png`` to ``cfg.out_dir``.

    Parameters
    ----------
    cfg : RollerConfig
        Run configuration.

    Returns
    -------
    str
        Path to the written PNG.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    hm, font_name, (W, H), n_deco = build_heightmap(cfg)

    # Colour the flattened dough. v1 (raised roller): the design presses DOWN
    # into the dough -> shown dark/indented on cream. v2 (--engrave, recessed
    # roller): the design stands UP out of the dough -> shown light/raised on a
    # darker pressed background (the colour mapping is simply inverted).
    arr = np.asarray(hm, dtype=np.float32) / 255.0
    base_col, feat_col = (IMPRINT, CREAM) if cfg.engrave else (CREAM, IMPRINT)
    rgb = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = (base_col[c] * (1 - arr) + feat_col[c] * arr).astype(
            np.uint8)

    circ_mm = 2 * math.pi * cfg.radius_mm
    aspect = W / H
    fig_h = 7.0
    fig_w = max(5.0, min(14.0, fig_h * aspect))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=130)
    ax.imshow(rgb, extent=[0, circ_mm, 0, cfg.length_mm], origin="lower")
    ax.set_xlabel("around circumference (mm)")
    ax.set_ylabel("along roller length (mm)")
    tag = "  (v2 · raised imprint)" if cfg.engrave else ""
    ax.set_title(f"ROLLER PREVIEW — {cfg.name} / {cfg.theme}{tag}",
                 fontsize=15, fontweight="bold", pad=12)
    caption = ("This is the RAISED Play-Doh imprint from the engraved roller "
               "(shown flat)" if cfg.engrave else
               "This is what the Play-Doh imprint will look like (shown flat)")
    fig.text(0.5, 0.015, caption, ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(top=0.90, bottom=0.12)

    out = os.path.join(
        cfg.out_dir,
        f"preview_{cfg.safe_name}_{cfg.theme}{cfg.suffix}.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"[preview] font={font_name}  surface={W}x{H}px  "
          f"decorations={n_deco}")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# TOP-END STAMP ICON SELECTION
# ===========================================================================
def _resolve_stamp_icon(cfg):
    """Pick the (svg_filename, fill_mode) for the top-end stamp.

    Defaults to the theme's first icon; ``cfg.stamp_icon`` overrides it with any
    asset name (``.svg`` extension optional). An override that is not part of
    the theme is allowed and rasterized with ``"evenodd"`` fill.

    Parameters
    ----------
    cfg : RollerConfig
        Run configuration; ``theme`` and ``stamp_icon`` drive the choice.

    Returns
    -------
    fname : str
        SVG filename within ``cfg.asset_dir``.
    mode : {'evenodd', 'union'}
        Fill mode to rasterize the icon with.
    """
    fname, mode = THEMES[cfg.theme][0]
    if cfg.stamp_icon:
        want = (cfg.stamp_icon if cfg.stamp_icon.endswith(".svg")
                else cfg.stamp_icon + ".svg")
        for f, mo in THEMES[cfg.theme]:
            if f == want:
                return f, mo
        return want, "evenodd"   # allow any asset in assets/
    return fname, mode


# ===========================================================================
# OUTPUT MODE 2 — STL
# ===========================================================================
def make_stl(cfg):
    """Build and export the printable roller STL.

    Wraps the heightmap onto a watertight cylinder (raised features bump
    outward, or inward under ``cfg.engrave``), optionally raises a theme icon
    out of the top end (``cfg.top_stamp``) and adds grip handles
    (``cfg.handles``), then stands the whole thing upright for support-free
    printing. Writes ``roller_<name>_<theme>[_v2].stl`` to ``cfg.out_dir``.

    Parameters
    ----------
    cfg : RollerConfig
        Run configuration.

    Returns
    -------
    str
        Path to the written STL.
    """
    import trimesh

    hm, font_name, (W, H), n_deco = build_heightmap(cfg)
    height = np.asarray(hm, dtype=np.float32) / 255.0   # 0..1 raised mask

    R = cfg.radius_mm
    L = cfg.length_mm

    # Optional raised icon stamp on the top (x=0) end.
    stamp_mask = None
    stamp_n_rings = None
    if cfg.top_stamp:
        fname, mode = _resolve_stamp_icon(cfg)
        size_img = max(64, int(2 * R * cfg.ppm))
        stamp_mask = rasterize_svg(os.path.join(cfg.asset_dir, fname),
                                   size_img, mode=mode, margin=0.18)
        stamp_n_rings = max(8, int(R * cfg.ppm * 0.6))   # radial rings

    body = build_roller_mesh(
        height, R, L, cfg.emboss_mm, engrave=cfg.engrave,
        stamp_mask=stamp_mask, stamp_relief=cfg.stamp_relief_mm,
        stamp_n_rings=stamp_n_rings)
    parts = [body]

    # Optional grip handles beyond each end (off by default — kept simple).
    if cfg.handles:
        parts += axial_handles(L, cfg.handle_length_mm, cfg.handle_radius_mm)

    combined = trimesh.util.concatenate(parts) if len(parts) > 1 else body

    # Stand the roller UPRIGHT on its end (axis -> Z) for easy, support-free
    # printing: every layer is a ring with the relief on its outer wall, so
    # there are no overhangs and the round body never rests on the bed.
    stand_upright_on_end(combined)

    out = os.path.join(
        cfg.out_dir,
        f"roller_{cfg.safe_name}_{cfg.theme}{cfg.suffix}.stl")
    combined.export(out)
    wt = "watertight" if combined.is_watertight else "NOT watertight"
    print(f"[stl] font={font_name}  decorations={n_deco}  "
          f"verts={len(combined.vertices)}  faces={len(combined.faces)}  {wt}")
    print(f"[stl] saved -> {out}")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(args):
    """Build a validated :class:`RollerConfig` from parsed CLI arguments.

    Parameters
    ----------
    args : argparse.Namespace
        Namespace produced by the parser in :func:`main`.

    Returns
    -------
    RollerConfig
        The validated configuration (raises ``pydantic.ValidationError`` on
        bad input).
    """
    return RollerConfig(
        name=args.name,
        theme=args.theme,
        radius_mm=args.radius,
        length_mm=args.length,
        handles=args.handles,
        handle_length_mm=args.handle_length,
        handle_radius_mm=args.handle_radius,
        emboss_mm=args.emboss,
        engrave=args.engrave,
        top_stamp=args.top_stamp,
        stamp_relief_mm=args.stamp_relief,
        stamp_icon=args.stamp_icon,
        ppm=args.ppm,
        deco_grid_mm=args.deco_grid,
        deco_size_mm=args.deco_size,
        text_diameter_fraction=args.text_fraction,
        min_feature_mm=args.min_feature,
    )


def main():
    d = RollerConfig()   # field defaults for argparse
    p = argparse.ArgumentParser(description="Parametric Play-Doh roller maker")
    p.add_argument("--name", default=d.name)
    p.add_argument("--theme", default=d.theme, choices=list(THEMES.keys()))
    p.add_argument("--radius", type=float, default=d.radius_mm)
    p.add_argument("--length", type=float, default=d.length_mm)
    p.add_argument("--handles", action="store_true",
                   help="add grip handles at both ends (off by default)")
    p.add_argument("--handle-length", type=float, default=d.handle_length_mm)
    p.add_argument("--handle-radius", type=float, default=d.handle_radius_mm)
    p.add_argument("--emboss", type=float, default=d.emboss_mm)
    p.add_argument("--engrave", action="store_true",
                   help="v2: recess the name/decorations INTO the roller so the "
                        "dough imprint comes out RAISED. Outputs get a _v2 "
                        "suffix.")
    p.add_argument("--top-stamp", action="store_true",
                   help="raise the theme's first icon out of the roller's top "
                        "end so it doubles as a press-stamp")
    p.add_argument("--stamp-relief", type=float, default=d.stamp_relief_mm,
                   help="height of the top-end stamp icon in mm")
    p.add_argument("--stamp-icon", default=d.stamp_icon,
                   help="which asset to use for the top stamp (e.g. star, heart, "
                        "bee); defaults to the theme's first icon")
    p.add_argument("--ppm", type=int, default=d.ppm)
    p.add_argument("--deco-grid", type=float, default=d.deco_grid_mm,
                   help="decoration grid spacing in mm")
    p.add_argument("--deco-size", type=float, default=d.deco_size_mm,
                   help="longest dimension of a decoration in mm")
    p.add_argument("--text-fraction", type=float, default=d.text_diameter_fraction,
                   help="letter height as a fraction of the roller diameter")
    p.add_argument("--min-feature", type=float, default=d.min_feature_mm,
                   help="minimum printable feature width in mm")
    p.add_argument("--preview", action="store_true", help="write preview PNG")
    p.add_argument("--stl", action="store_true", help="write printable STL")
    args = p.parse_args()

    if not (args.preview or args.stl):
        p.error("choose at least one of --preview / --stl")

    try:
        cfg = config_from_args(args)
    except ValidationError as exc:
        # Turn pydantic's traceback into a concise, CLI-friendly message.
        problems = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors())
        p.error(f"invalid parameters -> {problems}")

    if args.preview:
        make_preview(cfg)
    if args.stl:
        make_stl(cfg)


if __name__ == "__main__":
    main()
