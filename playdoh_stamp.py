#!/usr/bin/env python3
"""
playdoh_stamp.py
================
Parametric toddler-friendly Play-Doh / clay NAME & MOTIF stamp generator.

A stamp is a chunky ~5 cm slab with a short, grippy cylinder handle on the back
(easy for a toddler to grasp) and chamfered edges (safer to hold, cleaner to
print). The stamping face carries a name (parametric text) and/or a motif
rasterized from an SVG icon. Press it into a flat slab of Play-Doh and it
leaves the design behind.

Like :mod:`playdoh_roller`, all tunable parameters are collected in a validated
:class:`StampConfig` (a pydantic model), and all the heavy lifting is delegated
to the shared, project-agnostic modules :mod:`svg_processing` (SVG/text →
raster mask) and :mod:`mesh_utils` (mask → watertight solid). This file only
holds the stamp-specific layout, colouring and CLI.

Two imprint modes (what the DOUGH looks like after stamping):

  * ``raised``   (default) : the stamp face is a solid raised plateau with the
                             name/motif ENGRAVED (recessed) into it, so the
                             dough comes out with the name standing UP
                             (embossed). Most print-robust: the whole stamping
                             face is one solid surface (no thin islands), so it
                             prints face-down with a perfect first layer.
  * ``indented``           : the stamp face carries RAISED mirrored letters, so
                             the dough comes out with the name pressed IN
                             (debossed / classic seal look). Letters print as
                             small first-layer islands (a brim helps them stick).

Everything on the stamp face is automatically MIRRORED so the dough reads the
right way round.

USAGE
-----
    # Preview PNG of the dough imprint:
    python playdoh_stamp.py --name "Ember" --preview

    # Printable STL (face-down, no supports, grippy cylinder on top):
    python playdoh_stamp.py --name "Ember" --stl

    # Name + little icon above it + a framing border, both outputs:
    python playdoh_stamp.py --name "Max" --icon apple.svg --border --preview --stl

    # A single-motif picture stamp from any approved SVG (no name), round plate:
    python playdoh_stamp.py --svg assets/flower.svg --shape circle --stl

    # Classic pressed-IN (debossed) name instead of raised:
    python playdoh_stamp.py --name "Zoey" --imprint indented --stl

DEPENDENCIES
------------
    pip install trimesh numpy pillow matplotlib svgpathtools pydantic \
        --break-system-packages
    (trimesh is only needed for --stl)

----------------------------------------------------------------------------
3D PRINTING NOTES (read before slicing)
----------------------------------------------------------------------------
  * Orientation   : the STL is exported FACE-DOWN (stamping face flat on the
                    bed, handle pointing UP). Print exactly as oriented.
  * Supports      : NONE. The cylinder grip prints as stacked rings and the
                    chamfered slab has only 45° bevels — no overhangs.
  * Layer height  : 0.15 mm for crisp letters (0.20 mm acceptable).
  * Walls/infill  : 3+ walls, 15-20% infill is plenty (stamps take little force).
  * First layer   : slow it down; a short brim helps adhesion (essential in
                    'indented' mode where letters are small islands).
  * Material      : PLA is fine for Play-Doh (non-edible modelling compound).
  * Depth/relief  : 1.0 mm default — enough for a clear dough impression while
                    shallow enough that the dough releases cleanly (deeper, e.g.
                    2 mm, packs dough into the letters and sticks).
----------------------------------------------------------------------------
"""

import argparse
import os
from typing import Literal, Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    model_validator,
)

from mesh_utils import build_slab_relief, dome_knob, grip_cylinder
from svg_processing import load_font, rasterize_svg

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(OUT_DIR, "assets")

# Play-Doh-ish preview colours (shared look with the roller previews)
CREAM = (245, 232, 205)        # dough surface
IMPRINT = (150, 120, 80)       # pressed / shadowed areas


# ===========================================================================
# PARAMETER SCHEMA
# All tunable parameters, validated up front with sensible defaults — the same
# pattern as :class:`playdoh_roller.RollerConfig`.
# ===========================================================================
class StampConfig(BaseModel):
    """Validated parameters for one Play-Doh stamp generation run.

    Construct directly (``StampConfig(name="Ember", icon="flower.svg")``) or
    from parsed CLI args (see :func:`config_from_args`). Out-of-range or unknown
    values raise ``pydantic.ValidationError`` immediately, so a misconfigured
    run fails fast instead of producing a bad STL. Exactly one of ``name`` /
    ``svg`` (or both) must be supplied.

    Attributes
    ----------
    name : str or None
        Name on the stamping face. Omit for a motif-only stamp (with ``svg``).
    svg : str or None
        Approved/uploaded SVG for a single big centred motif, or a companion to
        a name. Accepts a bare filename (looked up in ``asset_dir``) or an
        absolute path.
    icon : str or None
        Small SVG placed above the name (e.g. ``"apple.svg"``, ``"star.svg"``).
    imprint : {'raised', 'indented'}
        ``raised`` (default): name pops UP out of the dough (engraved into a
        solid plateau; most print-robust). ``indented``: name pressed IN
        (classic seal; raised mirrored letters on the face).
    shape : {'rect', 'circle'}
        Plate footprint. ``circle`` is nice for single motifs.
    handle : {'cylinder', 'knob', 'bar', 'none'}
        Back-of-stamp grip. Default ``cylinder`` (a short upright grip that's
        easy for a toddler to grasp); ``knob`` is a dome, ``bar`` a rounded bar.
    border : bool
        Draw a framing border around the content.
    letter_height_mm : float
        Cap height of the name, in mm (chunky / toddler-legible).
    margin_mm : float
        Solid border of plate around the content, in mm.
    thickness_mm : float
        Solid slab thickness above the deepest relief, in mm.
    depth_mm : float
        How deep the name is engraved / raised, in mm.
    edge_chamfer_mm : float
        45° bevel on the plate's outer top/bottom edges, in mm (safer to
        handle, cleaner to print). ``0`` keeps square edges.
    cylinder_radius_mm, cylinder_height_mm : float
        Size of the default cylinder grip handle, in mm.
    top_initial : bool
        Raise the name's initial letter out of the top of the cylinder handle
        (identifies whose stamp it is). Only applies to the cylinder handle.
    top_initial_char : str or None
        Override the letter raised on the handle top (default: first char of
        ``name``, uppercased).
    top_relief_mm : float
        How far the initial letter bumps out of the handle top, in mm.
    knob_radius_mm : float
        Dome-knob (or bar) radius, in mm (``handle="knob"``/``"bar"``).
    knob_squash : float
        Dome height = radius x squash (flatter = comfier); in (0, 1].
    icon_fraction : float
        Icon height relative to the letter height.
    border_width_mm : float
        Framing-border line width, in mm.
    ppm : int
        Heightmap resolution in pixels per mm (6 default; >=10 for crisp icons).
    min_plate_w_mm : float
        Never make the plate narrower than this, in mm (grip + stability).
    min_plate_l_mm : float
        Never make the plate shorter than this, in mm.
    asset_dir : str
        Directory holding motif/icon SVG files.
    out_dir : str
        Directory the preview PNG / STL files are written to.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    # ---- content / identity ----
    name: Optional[str] = Field(None, min_length=1)
    svg: Optional[str] = None
    icon: Optional[str] = None

    # ---- modes ----
    imprint: Literal["raised", "indented"] = "raised"
    shape: Literal["rect", "circle"] = "rect"
    handle: Literal["cylinder", "knob", "bar", "none"] = "cylinder"
    border: bool = False

    # ---- geometry ----
    letter_height_mm: float = Field(8.5, gt=0)
    margin_mm: float = Field(6.0, gt=0)
    thickness_mm: float = Field(4.0, gt=0)
    depth_mm: float = Field(1.0, gt=0)
    edge_chamfer_mm: float = Field(1.0, ge=0)
    # cylinder handle (default) — short, easy for a toddler to grasp
    cylinder_radius_mm: float = Field(11.0, gt=0)
    cylinder_height_mm: float = Field(18.0, gt=0)
    # raised initial letter on the handle top (identifies whose stamp it is)
    top_initial: bool = True
    top_initial_char: Optional[str] = Field(None, min_length=1, max_length=1)
    top_relief_mm: float = Field(1.2, gt=0)
    # dome-knob handle (alternative)
    knob_radius_mm: float = Field(11.0, gt=0)
    knob_squash: float = Field(0.75, gt=0, le=1.0)
    icon_fraction: float = Field(0.9, gt=0)
    border_width_mm: float = Field(2.5, gt=0)

    # ---- resolution / layout ----
    ppm: int = Field(6, ge=1)
    min_plate_w_mm: float = Field(40.0, gt=0)
    min_plate_l_mm: float = Field(28.0, gt=0)

    # ---- paths ----
    asset_dir: str = ASSET_DIR
    out_dir: str = OUT_DIR

    @model_validator(mode="after")
    def _need_content(self) -> "StampConfig":
        if not self.name and not self.svg:
            raise ValueError("provide a name and/or an svg motif")
        return self

    @property
    def label(self) -> str:
        """str: human label for titles (the name, else the SVG basename)."""
        return self.name if self.name else os.path.basename(self.svg)

    @property
    def safe_name(self) -> str:
        """str: filename stem — name slug, else the SVG basename (no ext)."""
        if self.name:
            return self.name.lower().replace(" ", "_")
        return os.path.splitext(os.path.basename(self.svg))[0]

    @property
    def suffix(self) -> str:
        """str: filename suffix (``"_indented"`` in that mode, else ``""``)."""
        return "" if self.imprint == "raised" else "_indented"


# ===========================================================================
# FACE MASK  — the stamping-face content (255 = name/motif "ink").
# NOT mirrored (this is the dough-reading orientation, reused by the preview).
# ===========================================================================
def _resolve_svg(cfg, ref):
    """Resolve an SVG reference to an existing path (bare name -> asset_dir)."""
    path = ref if os.path.isabs(ref) else os.path.join(cfg.asset_dir, ref)
    if not path.endswith(".svg"):
        path += ".svg"
    if not os.path.exists(path):
        raise FileNotFoundError(f"SVG not found: {path}")
    return path


def _render_text_mask(name, letter_h_px):
    """Render ``name`` in a chunky font to a tight ``L`` mask (255 = ink)."""
    probe = ImageDraw.Draw(Image.new("L", (8, 8), 0))
    size_guess = letter_h_px
    font, font_name = load_font(size_guess)
    for _ in range(8):                                   # solve for cap height
        font, font_name = load_font(size_guess)
        bbox = probe.textbbox((0, 0), name, font=font)
        th = bbox[3] - bbox[1]
        if th <= 1:
            break
        scale = letter_h_px / th
        if abs(scale - 1.0) < 0.02:
            break
        size_guess *= scale

    bbox = probe.textbbox((0, 0), name, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = int(0.12 * th) + 4
    img = Image.new("L", (tw + 2 * pad, th + 2 * pad), 0)
    ImageDraw.Draw(img).text((pad - bbox[0], pad - bbox[1]), name,
                             font=font, fill=255)
    return img, font_name


def _icon_mask(cfg, ref, height_px):
    """Rasterize an SVG to a solid silhouette mask ``height_px`` tall."""
    mask = rasterize_svg(_resolve_svg(cfg, ref), int(height_px),
                         mode="union", margin=0.04)
    if height_px >= 48:
        mask = mask.filter(ImageFilter.MaxFilter(3))
    return mask


def _initial_mask(cfg, top_r):
    """Square mask of the name's initial letter, sized to the handle-top disk.

    The letter is centred and ~60 % of the disk diameter so it clears the rim.
    Read the right way up from above (not mirrored — the handle top is not a
    stamping surface).
    """
    ch = (cfg.top_initial_char or cfg.name[0]).upper()
    side = max(24, int(2 * top_r * cfg.ppm))
    letter_h_px = 0.60 * 2 * top_r * cfg.ppm
    img, _ = _render_text_mask(ch, letter_h_px)
    sq = Image.new("L", (side, side), 0)
    sq.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
    return sq


def build_face(cfg):
    """Build the stamping-face content mask and the plate footprint.

    Parameters
    ----------
    cfg : StampConfig
        Run configuration.

    Returns
    -------
    face : PIL.Image.Image
        Single-channel (``"L"``) mask, 255 where the name/motif/border is.
    font_name : str
        The font that rendered the name (``"-"`` for a motif-only stamp).
    plate_w_mm, plate_l_mm : float
        Plate footprint in mm.
    """
    ppm = cfg.ppm
    letter_h_px = cfg.letter_height_mm * ppm

    if cfg.svg and not cfg.name:
        # Single big motif filling the face.
        content = _icon_mask(cfg, cfg.svg, int(cfg.letter_height_mm * 2.4 * ppm))
        font_name = "-"
    else:
        text_img, font_name = _render_text_mask(cfg.name, letter_h_px)
        if cfg.icon:
            icon = _icon_mask(cfg, cfg.icon,
                              int(letter_h_px * cfg.icon_fraction))
            gap = int(0.35 * letter_h_px)
            cw = max(text_img.width, icon.width)
            ch = icon.height + gap + text_img.height
            content = Image.new("L", (cw, ch), 0)
            content.paste(icon, ((cw - icon.width) // 2, 0), icon)
            content.paste(text_img,
                          ((cw - text_img.width) // 2, icon.height + gap),
                          text_img)
        else:
            content = text_img

    cw, ch = content.width, content.height

    # Plate footprint = content + margins, clamped to a comfy minimum grip size.
    plate_w_mm = max(cfg.min_plate_w_mm, cw / ppm + 2 * cfg.margin_mm)
    plate_l_mm = max(cfg.min_plate_l_mm, ch / ppm + 2 * cfg.margin_mm)
    if cfg.shape == "circle":
        plate_w_mm = plate_l_mm = max(plate_w_mm, plate_l_mm)

    W = int(round(plate_w_mm * ppm))
    H = int(round(plate_l_mm * ppm))
    face = Image.new("L", (W, H), 0)
    face.paste(content, ((W - cw) // 2, (H - ch) // 2), content)

    if cfg.border:
        bw = max(1, int(cfg.border_width_mm * ppm))
        inset = max(2, int(cfg.margin_mm * ppm) // 2)
        d = ImageDraw.Draw(face)
        if cfg.shape == "circle":
            d.ellipse([inset, inset, W - inset, H - inset],
                      outline=255, width=bw)
        else:
            r = int(min(W, H) * 0.12)
            d.rounded_rectangle([inset, inset, W - inset, H - inset],
                                radius=r, outline=255, width=bw)

    return face, font_name, plate_w_mm, plate_l_mm


# ===========================================================================
# OUTPUT MODE 1 — PREVIEW PNG (shows the DOUGH imprint, correctly readable)
# ===========================================================================
def make_preview(cfg):
    """Render a flat PNG preview of the dough imprint for ``cfg``."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    face, font_name, pw, pl = build_face(cfg)
    ink = np.asarray(face, dtype=np.float32) / 255.0
    H, W = ink.shape

    # raised: name pops UP (rendered light). indented: name pressed IN (dark).
    if cfg.imprint == "raised":
        base_col, feat_col = IMPRINT, CREAM
    else:
        base_col, feat_col = CREAM, IMPRINT

    rgb = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = (base_col[c] * (1 - ink) + feat_col[c] * ink).astype(
            np.uint8)
    rgb = np.flipud(rgb)   # PIL rows are top-down; flip for origin="lower"

    aspect = W / H
    fig_h = 6.0
    fig_w = max(4.5, min(13.0, fig_h * aspect))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=130)
    ax.imshow(rgb, extent=[0, pw, 0, pl], origin="lower")
    ax.set_xlabel("width (mm)")
    ax.set_ylabel("height (mm)")
    tag = "raised imprint" if cfg.imprint == "raised" else "pressed-in imprint"
    ax.set_title(f"STAMP PREVIEW — {cfg.label}  ({tag})",
                 fontsize=14, fontweight="bold", pad=10)
    fig.text(0.5, 0.015, "This is what the Play-Doh imprint will look like",
             ha="center", fontsize=10, style="italic")
    fig.subplots_adjust(top=0.90, bottom=0.13)

    out = os.path.join(cfg.out_dir, f"preview_stamp_{cfg.safe_name}.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"[preview] font={font_name}  plate={pw:.0f}x{pl:.0f}mm  {W}x{H}px")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# OUTPUT MODE 2 — STL
# ===========================================================================
def make_stl(cfg):
    """Build and export the printable stamp STL for ``cfg``."""
    import math

    import trimesh

    face, font_name, pw, pl = build_face(cfg)
    D = cfg.depth_mm
    top_z = D + cfg.thickness_mm

    # Cap grid resolution so the triangle count stays sane on long names.
    W, H = face.width, face.height
    max_side = 900
    if max(W, H) > max_side:
        s = max_side / max(W, H)
        face = face.resize((max(2, int(W * s)), max(2, int(H * s))),
                           Image.LANCZOS)

    ink = np.fliplr(np.asarray(face) > 127)   # mirror in X so dough reads right

    if cfg.imprint == "raised":
        # Solid plateau presses the dough; name is ENGRAVED (recessed): the
        # background contacts the bed (z=0), the name sits up at z=D (a groove).
        bottom_z = np.where(ink, D, 0.0)
    else:
        # RAISED mirrored letters contact the bed (z=0); background recessed z=D.
        bottom_z = np.where(ink, 0.0, D)

    # Keep the edge chamfer within the plate margin so it never bites the name.
    chamfer = min(cfg.edge_chamfer_mm, cfg.margin_mm * 0.5,
                  cfg.thickness_mm * 0.5)
    plate = build_slab_relief(bottom_z.astype(np.float64), top_z, pw, pl,
                              chamfer=chamfer)
    parts = [plate]

    # ---- Handle (sits ON the top face, pointing +Z; no supports needed) ----
    cx, cy = pw / 2.0, pl / 2.0
    embed = 0.8                                # merge depth into the plate
    if cfg.handle == "cylinder":
        tc = min(2.0, cfg.cylinder_radius_mm * 0.35)     # top-rim chamfer
        top_mask = None
        if cfg.top_initial and cfg.name:
            top_mask = _initial_mask(cfg, cfg.cylinder_radius_mm - tc)
        grip = grip_cylinder(cfg.cylinder_radius_mm, cfg.cylinder_height_mm,
                             top_chamfer=tc, top_mask=top_mask,
                             top_relief=cfg.top_relief_mm)
        grip.apply_translation([cx, cy, top_z - embed])
        parts.append(grip)
    elif cfg.handle == "knob":
        knob = dome_knob(cfg.knob_radius_mm,
                         cfg.knob_radius_mm * cfg.knob_squash)
        knob.apply_translation([cx, cy, top_z - embed])
        parts.append(knob)
    elif cfg.handle == "bar":
        r = min(cfg.knob_radius_mm, pl * 0.30)
        length = max(pw * 0.55, 3 * r)
        bar = trimesh.creation.capsule(height=length - 2 * r, radius=r,
                                       count=[16, 16])
        bar.apply_transform(trimesh.transformations.rotation_matrix(
            math.pi / 2, [0, 1, 0]))            # lay it along X
        bar.apply_translation([cx, cy, top_z + r - embed])
        parts.append(bar)
    # handle == "none": bare slab

    combined = trimesh.util.concatenate(parts) if len(parts) > 1 else plate

    out = os.path.join(cfg.out_dir, f"stamp_{cfg.safe_name}{cfg.suffix}.stl")
    combined.export(out)
    wt = "watertight" if plate.is_watertight else "plate NOT watertight"
    print(f"[stl] font={font_name}  plate={pw:.0f}x{pl:.0f}mm  "
          f"verts={len(combined.vertices)}  faces={len(combined.faces)}  "
          f"({wt}; parts union in slicer)")
    print(f"[stl] saved -> {out}")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(args):
    """Build a validated :class:`StampConfig` from parsed CLI arguments."""
    return StampConfig(
        name=args.name,
        svg=args.svg,
        icon=args.icon,
        imprint=args.imprint,
        shape=args.shape,
        handle=args.handle,
        border=args.border,
        letter_height_mm=args.letter_height,
        margin_mm=args.margin,
        thickness_mm=args.thickness,
        depth_mm=args.depth,
        edge_chamfer_mm=args.edge_chamfer,
        cylinder_radius_mm=args.cylinder_radius,
        cylinder_height_mm=args.cylinder_height,
        top_initial=not args.no_initial,
        top_initial_char=args.initial,
        top_relief_mm=args.top_relief,
        knob_radius_mm=args.knob_radius,
        knob_squash=args.knob_squash,
        icon_fraction=args.icon_fraction,
        border_width_mm=args.border_width,
        ppm=args.ppm,
    )


def main():
    d = StampConfig(name="Ember")   # field defaults for argparse
    p = argparse.ArgumentParser(
        description="Parametric toddler Play-Doh name / motif stamp maker")
    p.add_argument("--name", default=None,
                   help="name on the stamp (omit for a motif-only stamp "
                        "with --svg)")
    p.add_argument("--svg", default=None,
                   help="approved/uploaded SVG for a single motif, or a "
                        "companion to a name")
    p.add_argument("--icon", default=None,
                   help="small SVG placed above the name (e.g. apple.svg, "
                        "star.svg, flower.svg)")
    p.add_argument("--imprint", choices=["raised", "indented"],
                   default=d.imprint,
                   help="raised (default): name pops UP out of the dough. "
                        "indented: name pressed IN (classic seal).")
    p.add_argument("--shape", choices=["rect", "circle"], default=d.shape,
                   help="plate footprint (circle is nice for single motifs)")
    p.add_argument("--handle", choices=["cylinder", "knob", "bar", "none"],
                   default=d.handle,
                   help="back-of-stamp grip (default: cylinder)")
    p.add_argument("--border", action="store_true",
                   help="add a framing border around the content")
    p.add_argument("--letter-height", type=float, default=d.letter_height_mm)
    p.add_argument("--margin", type=float, default=d.margin_mm)
    p.add_argument("--thickness", type=float, default=d.thickness_mm)
    p.add_argument("--depth", type=float, default=d.depth_mm)
    p.add_argument("--edge-chamfer", type=float, default=d.edge_chamfer_mm,
                   help="45° bevel on the plate's outer edges, mm")
    p.add_argument("--cylinder-radius", type=float,
                   default=d.cylinder_radius_mm)
    p.add_argument("--cylinder-height", type=float,
                   default=d.cylinder_height_mm)
    p.add_argument("--no-initial", action="store_true",
                   help="don't raise the name's initial letter on the handle top")
    p.add_argument("--initial", default=None,
                   help="letter to raise on the handle top (default: name's "
                        "first letter)")
    p.add_argument("--top-relief", type=float, default=d.top_relief_mm,
                   help="how far the handle-top initial bumps out, mm")
    p.add_argument("--knob-radius", type=float, default=d.knob_radius_mm)
    p.add_argument("--knob-squash", type=float, default=d.knob_squash)
    p.add_argument("--icon-fraction", type=float, default=d.icon_fraction)
    p.add_argument("--border-width", type=float, default=d.border_width_mm)
    p.add_argument("--ppm", type=int, default=d.ppm)
    p.add_argument("--preview", action="store_true", help="write preview PNG")
    p.add_argument("--stl", action="store_true", help="write printable STL")
    args = p.parse_args()

    if not (args.preview or args.stl):
        p.error("choose at least one of --preview / --stl")

    try:
        cfg = config_from_args(args)
    except ValidationError as exc:
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
