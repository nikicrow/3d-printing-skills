#!/usr/bin/env python3
"""
playdoh_label.py
================
Standalone (no-OpenSCAD) generator for the **two-colour name keychain label** —
the pure-``trimesh`` sibling of :mod:`namelabel` / ``label.scad``. It builds the
geometry directly in Python, exactly like the roller/stamp/scraper tools, and
writes a **genuine multicolour 3MF** that Bambu Studio parses natively (via the
standard 3MF material extension), plus a plain STL and a colour preview PNG.

Design (identical to ``label.scad``, so the two pipelines are interchangeable):
the child's **name** (+ optional theme icon) is raised in one colour on a
contrasting rounded **"trace" border**, with a keychain hole. The two colours
are split **by height** — bottom band = border, top band = name — so the second
colour uses almost no extra filament and prints either as two 3MF colour parts
(AMS / any slicer) or with a single filament change at ``Z = border_h``.

Everything fuses into ONE connected, watertight solid (a hidden connector web
in the base ties the tab, icon and name together).

USAGE
-----
    # colour preview PNG (top view + side profile):
    python playdoh_label.py --name "Ember" --icon flower --preview

    # printable multicolour 3MF (+ STL):
    python playdoh_label.py --name "Imogen" --icon heart --3mf --stl

DEPENDENCIES
------------
    pip install trimesh numpy pillow matplotlib svgpathtools pydantic scipy --break-system-packages

(``scipy`` powers the edge chamfer only; without it ``--bevel`` is a no-op and
the plate comes out square-edged.)

----------------------------------------------------------------------------
3D PRINTING NOTES
----------------------------------------------------------------------------
  * Orientation : flat on the bed, name up (as exported). No supports.
  * Edges       : the plate rim and the raised name each carry a 45° chamfer on
                  their TOP face (``--bevel``, 0.3 mm default), so there is no
                  sharp arris for small hands. Both undersides stay square: the
                  plate keeps its full first-layer footprint for bed adhesion,
                  and the letters meet the plate flush.
  * 2 colours   : the 3MF carries two materials (border, name). In Bambu Studio
                  assign a filament to each on import. Single-extruder: print the
                  STL with one filament change at Z = border_h (printed on export).
  * Material    : PLA is fine; PETG is tougher for a bag tag.
----------------------------------------------------------------------------
"""

import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mesh_utils import build_mask_prism, write_color_3mf
from svg_processing import rasterize_svg

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(OUT_DIR, "assets", "fonts")
ASSET_DIR = os.path.join(OUT_DIR, "assets")
PREVIEW_SUBDIR = os.path.join("previews", "labels")
PRINT_SUBDIR = os.path.join("printable_files", "labels")

FONTS = {
    "Grandstander": "Grandstander.ttf",
    "Baloo 2": "Baloo2.ttf",
    "Bagel Fat One": "BagelFatOne.ttf",
    "Titan One": "TitanOne.ttf",
    "Chewy": "Chewy.ttf",
    "Lilita One": "LilitaOne.ttf",
    "Bubblegum Sans": "BubblegumSans.ttf",
}
ICONS = ["none", "bee", "heart", "star", "flower", "paw", "cat", "apple",
         "car", "truck", "banana", "brontosaurus", "trex", "circle", "square",
         "triangle"]


def _out_path(out_dir, subdir, filename):
    dest = os.path.join(out_dir, subdir)
    os.makedirs(dest, exist_ok=True)
    return os.path.join(dest, filename)


# ===========================================================================
# PARAMETER SCHEMA
# ===========================================================================
class LabelConfig(BaseModel):
    """Validated parameters for one name-label generation run (standalone tool).

    Mirrors :class:`namelabel.LabelConfig` / ``label.scad`` so the two pipelines
    produce the same label.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field("Ember", min_length=1)
    font: str = Field("Grandstander")
    icon: str = Field("none")

    name_color: str = Field("#2b2b2b")
    border_color: str = Field("#f2ead6")

    letter_height_mm: float = Field(16.0, gt=0)
    border_width_mm: float = Field(3.0, gt=0)
    corner_round_mm: float = Field(1.5, ge=0)
    border_h_mm: float = Field(2.4, gt=0)
    font_h_mm: float = Field(1.6, gt=0)
    bevel_mm: float = Field(0.3, ge=0)         # 45° chamfer on plate + name
    icon_scale: float = Field(1.15, gt=0)

    keychain: bool = True
    hole_d_mm: float = Field(5.0, gt=0)
    hole_wall_mm: float = Field(2.5, gt=0)

    ppm: int = Field(8, ge=3)
    out_dir: str = OUT_DIR

    @model_validator(mode="after")
    def _check(self) -> "LabelConfig":
        if self.font not in FONTS:
            raise ValueError(f"font must be one of {list(FONTS)}")
        if self.icon not in ICONS:
            raise ValueError(f"icon must be one of {ICONS}")
        if self.corner_round_mm > self.border_width_mm:
            raise ValueError("corner_round_mm must be <= border_width_mm")
        for c in (self.name_color, self.border_color):
            if not (c.startswith("#") and len(c) in (4, 7)):
                raise ValueError(f"colour {c!r} must be a #rgb or #rrggbb hex")
        return self

    @property
    def safe_name(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def total_h_mm(self) -> float:
        return self.border_h_mm + self.font_h_mm

    @property
    def stem(self) -> str:
        """Output basename, ``_mesh``-suffixed to stay out of OpenSCAD's way.

        ``namelabel.py`` writes ``label_ember_flower.{stl,3mf}`` from the same
        parameters, so without the suffix whichever tool ran last would silently
        clobber the other's export. The preview PNGs already separate the two
        pipelines this way.
        """
        tag = f"_{self.icon}" if self.icon != "none" else ""
        return f"label_{self.safe_name}{tag}_mesh"


def _hex(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# ===========================================================================
# MASKS  (shared by preview + mesh; same [hole][icon][NAME] layout as label.scad)
# ===========================================================================
def build_masks(cfg):
    """Return ``(content, base)`` boolean masks + ``ppm`` for the label.

    ``content`` = raised letters + icon (name-colour top band).
    ``base``    = rounded border trace + keychain tab + connector, minus the
                  clasp hole (border-colour bottom band).
    """
    ppm = cfg.ppm
    cap_ratio = 0.72
    em = (cfg.letter_height_mm / cap_ratio) * ppm
    font = ImageFont.truetype(os.path.join(FONT_DIR, FONTS[cfg.font]), int(em))
    probe = ImageDraw.Draw(Image.new("L", (4, 4)))
    bb = probe.textbbox((0, 0), cfg.name, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]

    icon_w = int(cfg.letter_height_mm * cfg.icon_scale * ppm) if cfg.icon != "none" else 0
    gap = int(cfg.border_width_mm * ppm)
    bw = int(cfg.border_width_mm * ppm)
    tab_r = (cfg.hole_d_mm / 2 + cfg.hole_wall_mm) * ppm
    # generous canvas; trimmed later
    padL = int(tab_r * 2 + bw * 3) + icon_w + gap
    padR = bw * 3 + 6
    padV = int(max(th, icon_w, tab_r * 2) * 0.5 + bw * 3) + 6
    lead = (icon_w + gap) if cfg.icon != "none" else 0

    W = padL + tw + padR
    H = max(th, icon_w) + 2 * padV
    name_org_x = padL                      # name left edge (x=0 world anchor)
    cy = H // 2

    content = Image.new("L", (W, H), 0)
    dc = ImageDraw.Draw(content)
    dc.text((name_org_x - bb[0], cy - th // 2 - bb[1]), cfg.name, font=font,
            fill=255)
    if cfg.icon != "none":
        svg = os.path.join(ASSET_DIR, f"{cfg.icon}.svg")
        im = rasterize_svg(svg, icon_w, mode="union", margin=0.02)
        content.paste(im, (name_org_x - lead, cy - icon_w // 2), im)
    cm = np.asarray(content) > 127

    # rounded outward offset (border trace) ≈ label.scad's offset(r)offset(delta)
    grow = bw
    rnd = int(cfg.corner_round_mm * ppm)
    m = Image.fromarray((cm * 255).astype(np.uint8))
    if grow - rnd >= 1:
        k = (grow - rnd) if (grow - rnd) % 2 == 1 else (grow - rnd + 1)
        m = m.filter(ImageFilter.MaxFilter(k))
    if rnd > 0:
        m = m.filter(ImageFilter.GaussianBlur(rnd * 0.7))
    border = np.asarray(m) > 60

    yy, xx = np.mgrid[0:H, 0:W]
    content_left = (name_org_x - lead) if cfg.icon != "none" else name_org_x
    if cfg.keychain:
        tab_cx = content_left - bw - tab_r * 0.6
        tab = (xx - tab_cx) ** 2 + (yy - cy) ** 2 <= tab_r ** 2
        border = border | tab
        conn_x0 = tab_cx
    else:
        conn_x0 = content_left
    if cfg.keychain or cfg.icon != "none":
        band = (np.abs(yy - cy) <= bw) & (xx >= conn_x0) & \
               (xx <= content_left + icon_w + gap)
        border = border | band
    # round the whole plate a touch so the connector/tab blend
    sm = Image.fromarray((border * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(ppm * 0.3))
    border = np.asarray(sm) > 110
    if cfg.keychain:
        hole = (xx - tab_cx) ** 2 + (yy - cy) ** 2 <= (cfg.hole_d_mm / 2 * ppm) ** 2
        border = border & ~hole

    # trim to used bounds (+ a small margin) so meshes stay lean
    used = border | cm
    ys, xs = np.where(used)
    mg = bw + 2
    y0, y1 = max(0, ys.min() - mg), min(H, ys.max() + mg + 1)
    x0, x1 = max(0, xs.min() - mg), min(W, xs.max() + mg + 1)
    return cm[y0:y1, x0:x1], border[y0:y1, x0:x1], ppm


# ===========================================================================
# OUTPUT MODE 1 — PREVIEW PNG (top view + side profile)
# ===========================================================================
def make_preview(cfg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    cm, base, ppm = build_masks(cfg)
    H, W = base.shape
    name_rgb = np.array(_hex(cfg.name_color)) / 255
    border_rgb = np.array(_hex(cfg.border_color)) / 255

    rgb = np.ones((H, W, 3))
    rgb[base] = border_rgb
    rgb[cm] = name_rgb                       # letters on top

    fig, (axt, axp) = plt.subplots(
        2, 1, figsize=(11, 6), dpi=130,
        gridspec_kw={"height_ratios": [3, 1]})
    axt.imshow(rgb, extent=[0, W / ppm, 0, H / ppm], origin="upper")
    axt.set_title(f"LABEL — {cfg.name}"
                  + (f"  ·  {cfg.icon}" if cfg.icon != "none" else "")
                  + f"   ({cfg.font})", fontsize=14, fontweight="bold")
    axt.set_xlabel("mm"); axt.set_ylabel("mm")

    # side profile: two colour bands (border then name), showing the height split
    # — and the 45° chamfers the mesh actually carries, on the TOP face of each
    # band only, both undersides staying square (flat on the bed / flush join)
    w, h = 10.0, cfg.border_h_mm
    b = min(cfg.bevel_mm, h)
    plate = [(0, 0), (w, 0), (w, h - b), (w - b, h), (b, h), (0, h - b)]
    axp.add_patch(plt.Polygon(plate, closed=True, color=border_rgb, ec="0.4"))

    nx0, nw, nt = 3.0, 4.0, cfg.total_h_mm
    n = min(cfg.bevel_mm, cfg.font_h_mm)
    name = [(nx0, h), (nx0 + nw, h), (nx0 + nw, nt - n), (nx0 + nw - n, nt),
            (nx0 + n, nt), (nx0, nt - n)]
    axp.add_patch(plt.Polygon(name, closed=True, color=name_rgb, ec="0.4"))
    if cfg.bevel_mm > 0:
        axp.annotate(f"{cfg.bevel_mm:.1f} mm 45° chamfer on both top faces — "
                     "undersides square, so the plate keeps full bed contact",
                     (0, -0.8), fontsize=8, color="0.45")
    axp.annotate(f"border band 0–{cfg.border_h_mm:.1f} mm",
                 (10.3, cfg.border_h_mm / 2), va="center", fontsize=9)
    axp.annotate(f"name band → {cfg.total_h_mm:.1f} mm",
                 (10.3, cfg.border_h_mm + cfg.font_h_mm / 2), va="center",
                 fontsize=9, color=tuple(name_rgb * 0.7))
    axp.annotate(f"filament change @ Z = {cfg.border_h_mm:.1f} mm",
                 (0, cfg.total_h_mm + 0.4), fontsize=9, color="0.3")
    axp.set_xlim(-1, 26); axp.set_ylim(-1.4, cfg.total_h_mm + 1.4)
    axp.set_aspect("equal"); axp.axis("off")
    axp.set_title("side profile — two colours split by height", fontsize=11)

    fig.tight_layout()
    out = _out_path(cfg.out_dir, PREVIEW_SUBDIR, f"preview_{cfg.stem}.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"[preview] {cfg.name}  font={cfg.font}  icon={cfg.icon}  "
          f"H={cfg.total_h_mm:.1f}mm")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# GEOMETRY — two mask-prism solids fused into one part
# ===========================================================================
def build_mesh(cfg):
    import trimesh
    cm, base, ppm = build_masks(cfg)
    s = 1.0 / ppm
    # Both bands are chamfered on their TOP face only. The plate keeps a square
    # underside so the first layer lays down its full footprint (a chamfer there
    # would shrink the bed contact patch and hurt adhesion), and the name keeps a
    # square base so the letters meet the plate flush instead of tapering away
    # from it and leaving a groove around every glyph.
    base_m = build_mask_prism(base, 0.0, cfg.border_h_mm, s,
                              bevel=(0.0, cfg.bevel_mm))
    # name overlaps the base plane slightly so the two fuse into one solid
    name_m = build_mask_prism(cm, cfg.border_h_mm - 0.01,
                              cfg.total_h_mm, s, bevel=(0.0, cfg.bevel_mm))
    combo = trimesh.util.concatenate([base_m, name_m])
    face_mat = np.concatenate([np.zeros(len(base_m.faces), int),
                               np.ones(len(name_m.faces), int)])
    combo.remove_unreferenced_vertices()
    return combo, face_mat


# ===========================================================================
# OUTPUT MODES 2/3 — STL and multicolour 3MF
# ===========================================================================
def make_stl(cfg):
    combo, _ = build_mesh(cfg)
    out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"{cfg.stem}.stl")
    combo.export(out)
    wt = "watertight" if combo.is_watertight else "manifold-repairable"
    print(f"[stl] {cfg.name}  verts={len(combo.vertices)}  "
          f"faces={len(combo.faces)}  {wt}")
    print(f"[stl] saved -> {out}")
    print(f"[stl] single-extruder tip: filament change at Z = "
          f"{cfg.border_h_mm:.1f} mm splits border vs name colour.")
    return out


def make_3mf(cfg):
    combo, face_mat = build_mesh(cfg)
    out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"{cfg.stem}.3mf")
    write_color_3mf(combo, face_mat, [cfg.border_color, cfg.name_color], out,
                    names=["border", "name"], object_name=cfg.stem)
    print(f"[3mf] {cfg.name}  2 coloured parts (border, name)  "
          f"faces={len(combo.faces)}  {os.path.getsize(out) / 1e6:.1f} MB")
    print(f"[3mf] saved -> {out}")
    print("[3mf] Bambu Studio: opens as one object of two parts, already "
          "pinned to extruder 1 (border) and 2 (name). No painting needed.")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(a):
    return LabelConfig(
        name=a.name, font=a.font, icon=a.icon,
        name_color=a.name_color, border_color=a.border_color,
        letter_height_mm=a.letter_height, border_width_mm=a.border_width,
        corner_round_mm=a.corner_round, border_h_mm=a.border_h,
        font_h_mm=a.font_h, bevel_mm=a.bevel, icon_scale=a.icon_scale,
        keychain=not a.no_keychain, hole_d_mm=a.hole_d,
        hole_wall_mm=a.hole_wall, ppm=a.ppm)


def main():
    d = LabelConfig()
    p = argparse.ArgumentParser(
        description="Standalone two-colour name keychain label maker (trimesh)")
    p.add_argument("--name", default=d.name)
    p.add_argument("--font", default=d.font, choices=list(FONTS))
    p.add_argument("--icon", default=d.icon, choices=ICONS)
    p.add_argument("--name-color", dest="name_color", default=d.name_color)
    p.add_argument("--border-color", dest="border_color", default=d.border_color)
    p.add_argument("--letter-height", type=float, default=d.letter_height_mm)
    p.add_argument("--border-width", type=float, default=d.border_width_mm)
    p.add_argument("--corner-round", type=float, default=d.corner_round_mm)
    p.add_argument("--border-h", type=float, default=d.border_h_mm)
    p.add_argument("--font-h", type=float, default=d.font_h_mm)
    p.add_argument("--bevel", type=float, default=d.bevel_mm,
                   help="45° chamfer on the plate's top/bottom edges, mm "
                        "(0 = square)")
    p.add_argument("--icon-scale", type=float, default=d.icon_scale)
    p.add_argument("--no-keychain", action="store_true")
    p.add_argument("--hole-d", type=float, default=d.hole_d_mm)
    p.add_argument("--hole-wall", type=float, default=d.hole_wall_mm)
    p.add_argument("--ppm", type=int, default=d.ppm,
                   help="mesh resolution, px/mm (higher = smoother edges)")
    p.add_argument("--preview", action="store_true", help="write preview PNG")
    p.add_argument("--stl", action="store_true", help="write STL")
    p.add_argument("--3mf", dest="threemf", action="store_true",
                   help="write multicolour 3MF")
    a = p.parse_args()

    if not (a.preview or a.stl or a.threemf):
        p.error("choose at least one of --preview / --stl / --3mf")

    try:
        cfg = config_from_args(a)
    except ValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(loc) for loc in e['loc'])}: {e['msg']}"
            for e in exc.errors())
        p.error(f"invalid parameters -> {problems}")

    if a.preview:
        make_preview(cfg)
    if a.stl:
        make_stl(cfg)
    if a.threemf:
        make_3mf(cfg)


if __name__ == "__main__":
    main()
