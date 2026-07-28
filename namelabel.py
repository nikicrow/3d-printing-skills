#!/usr/bin/env python3
"""
namelabel.py
============
Parametric two-colour name **keychain label** generator — the multicolour
companion to the Play-Doh roller/stamp/scraper tools.

Unlike those tools (which emit an STL), the printable geometry here lives in a
single parametric OpenSCAD file, :file:`label.scad`, so the *same* source can be
uploaded to MakerWorld's Parametric Model Maker as a customisable, multicolour
model. This script is the local driver:

  * ``--preview`` renders a fast, colour-accurate PNG of the label (no OpenSCAD
    needed) so you can eyeball a name / font / colour / icon combination.
  * ``--stl`` / ``--3mf`` shell out to ``openscad`` to export a print-ready file
    from :file:`label.scad` with your parameters baked in.

The label splits its two colours **by height** to minimise second-colour waste:
a bottom *border* band (the rounded "trace" outline + keychain tab) and a top
*name* band (only the raised letters + optional icon). That clean split means
even a single-extruder Bambu prints it perfectly with ONE filament change at
``Z = border_h`` — the exact Z is printed on export.

USAGE
-----
    # colour preview PNG:
    python namelabel.py --name "Ember" --icon bee --preview

    # print-ready files (needs OpenSCAD on PATH):
    python namelabel.py --name "Imogen" --font "Bagel Fat One" --icon heart --stl
    python namelabel.py --name "Ember" --icon bee --3mf

DEPENDENCIES
------------
    pip install numpy pillow pydantic svgpathtools --break-system-packages
    OpenSCAD (only for --stl / --3mf); 2024+ exports colour into the 3MF.
"""

import argparse
import os
import shutil
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from svg_processing import rasterize_svg

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
SCAD_FILE = os.path.join(OUT_DIR, "label.scad")
FONT_DIR = os.path.join(OUT_DIR, "assets", "fonts")
ASSET_DIR = os.path.join(OUT_DIR, "assets")

PREVIEW_SUBDIR = os.path.join("previews", "labels")
PRINT_SUBDIR = os.path.join("printable_files", "labels")

# Bundled bubbly fonts: customiser family name -> TTF file (in assets/fonts).
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
# No viewBox table here on purpose: rasterize_svg reads each file's own viewBox
# and normalises the art to the requested size. Only label.scad needs one (see
# `icon_vb_table` there), because OpenSCAD imports an SVG at its viewBox units.


def _out_path(out_dir, subdir, filename):
    dest = os.path.join(out_dir, subdir)
    os.makedirs(dest, exist_ok=True)
    return os.path.join(dest, filename)


# ===========================================================================
# PARAMETER SCHEMA  (mirrors the customiser blocks in label.scad)
# ===========================================================================
class LabelConfig(BaseModel):
    """Validated parameters for one name-label generation run.

    The fields mirror the OpenSCAD customiser variables in ``label.scad`` so the
    local preview and the MakerWorld model stay in lock-step.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field("Ember", min_length=1)
    font: str = Field("Grandstander")
    icon: str = Field("none")

    name_color: str = Field("#2b2b2b")     # top layer (letters)
    border_color: str = Field("#f2ead6")   # bottom layer (trace/border)

    letter_height_mm: float = Field(16.0, gt=0)
    border_width_mm: float = Field(3.0, gt=0)
    corner_round_mm: float = Field(1.5, ge=0)
    border_h_mm: float = Field(1.6, gt=0)      # bottom band thickness
    font_h_mm: float = Field(2.0, gt=0)        # top band thickness
    bevel_mm: float = Field(0.6, ge=0)         # 45° chamfer on plate edges
    icon_scale: float = Field(1.15, gt=0)

    keychain: bool = True
    hole_d_mm: float = Field(5.0, gt=0)
    hole_wall_mm: float = Field(2.5, gt=0)

    smoothness: int = Field(72, ge=24)
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
        tag = f"_{self.icon}" if self.icon != "none" else ""
        return f"label_{self.safe_name}{tag}"


def _hex(c):
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


# ===========================================================================
# GEOMETRY (shared by the preview) — mirror of label.scad's 2D layout
# ===========================================================================
def _load_font(font_family, px):
    path = os.path.join(FONT_DIR, FONTS[font_family])
    f = ImageFont.truetype(path, int(px))
    return f


def _content_mask(cfg, ppm):
    """Rasterise the raised silhouette (icon then name) to an L mask, matching
    label.scad's ``[hole] [icon] [NAME ->]`` left-anchored layout."""
    cap_ratio = 0.72
    em = (cfg.letter_height_mm / cap_ratio) * ppm
    font = _load_font(cfg.font, em)
    probe = ImageDraw.Draw(Image.new("L", (4, 4)))
    bb = probe.textbbox((0, 0), cfg.name, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]

    icon_w = int(cfg.letter_height_mm * cfg.icon_scale * ppm)
    gap = int(cfg.border_width_mm * ppm)            # matches label.scad
    pad = int(cfg.border_width_mm * ppm) + 6

    lead = (icon_w + gap) if cfg.icon != "none" else 0
    W = lead + tw + 2 * pad
    H = max(th, icon_w) + 2 * pad
    img = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(img)
    # name
    d.text((pad + lead - bb[0], (H - th) // 2 - bb[1]), cfg.name, font=font,
           fill=255)
    # icon (left of the name)
    if cfg.icon != "none":
        svg = os.path.join(ASSET_DIR, f"{cfg.icon}.svg")
        im = rasterize_svg(svg, icon_w, mode="union", margin=0.02)
        iy = (H - icon_w) // 2
        img.paste(im, (pad, iy), im)
    return img


def _round_dilate(mask, grow_px, round_px):
    """Rounded outward offset ≈ label.scad's offset(r) offset(delta)."""
    arr = np.asarray(mask) > 127
    m = Image.fromarray((arr * 255).astype(np.uint8))
    # grow by (grow-round) hard-ish, then round by blurring ~round
    b = m.filter(ImageFilter.MaxFilter(_odd(max(1, grow_px - round_px))))
    if round_px > 0:
        b = b.filter(ImageFilter.GaussianBlur(round_px * 0.7))
    return np.asarray(b) > 60


def _odd(n):
    n = int(round(n))
    return n + 1 if n % 2 == 0 else max(1, n)


# ===========================================================================
# OUTPUT MODE 1 — colour PREVIEW PNG (no OpenSCAD required)
# ===========================================================================
def make_preview(cfg):
    ppm = 8
    content = _content_mask(cfg, ppm)
    cm = np.asarray(content) > 127
    icon_w = int(cfg.letter_height_mm * cfg.icon_scale * ppm)
    gap = int(cfg.border_width_mm * ppm)
    grow = int(cfg.border_width_mm * ppm)
    rnd = int(cfg.corner_round_mm * ppm)
    border = _round_dilate(content, grow, rnd)

    H, W = border.shape
    yy, xx = np.mgrid[0:H, 0:W]
    # keychain tab on the left + a connector band along y=0 that fuses tab,
    # icon and first letter into one plate (mirrors label.scad's connector).
    hole = np.zeros((H, W), bool)
    cys, cxs = np.where(cm if cm.any() else border)
    left = cxs.min()
    cy = int(np.median(cys))
    if cfg.keychain:
        tab_r = (cfg.hole_d_mm / 2 + cfg.hole_wall_mm) * ppm
        tab_cx = left - (cfg.border_width_mm * ppm) - tab_r * 0.6
        tab = (xx - tab_cx) ** 2 + (yy - cy) ** 2 <= tab_r ** 2
        border = border | tab
        hole = (xx - tab_cx) ** 2 + (yy - cy) ** 2 <= (cfg.hole_d_mm / 2 * ppm) ** 2
        conn_x0 = tab_cx
    else:
        conn_x0 = left
    if cfg.keychain or cfg.icon != "none":
        conn_h = max(1, cfg.border_width_mm * ppm)   # ~2·bw tall after this band
        band = (np.abs(yy - cy) <= conn_h) & (xx >= conn_x0) & (xx <= left + icon_w + gap)
        border = border | band

    # light rounding pass so the connector band / tab blend smoothly
    sm = Image.fromarray((border * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(ppm * 0.35))
    border = np.asarray(sm) > 110
    border = border & ~hole

    name_rgb = _hex(cfg.name_color)
    border_rgb = _hex(cfg.border_color)
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[border] = (*border_rgb, 255)
    rgba[cm] = (*name_rgb, 255)          # letters + icon on top
    rgba[hole] = (0, 0, 0, 0)            # punched clasp hole
    img = Image.fromarray(rgba, "RGBA")
    bbox = Image.fromarray(((border) & ~hole).astype(np.uint8) * 255).getbbox()
    m = int(4 * ppm)
    img = img.crop((max(0, bbox[0] - m), max(0, bbox[1] - m),
                    min(W, bbox[2] + m), min(H, bbox[3] + m)))

    # compose on a card with a soft drop shadow + a spec caption
    pw, ph = img.size
    card = Image.new("RGBA", (pw + 80, ph + 150), (250, 250, 252, 255))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow.putalpha(img.split()[3])
    shadow = shadow.filter(ImageFilter.GaussianBlur(10))
    card.alpha_composite(shadow, (46, 46))
    card.alpha_composite(img, (40, 40))
    d = ImageDraw.Draw(card)
    cap = _load_font("Baloo 2", 26)
    sub = _load_font("Baloo 2", 20)
    dims = (f"{cfg.name}  ·  {cfg.font}"
            + (f"  ·  {cfg.icon}" if cfg.icon != "none" else ""))
    specs = (f"letters {cfg.letter_height_mm:.0f} mm cap · border {cfg.border_width_mm:.1f} mm · "
             f"height {cfg.border_h_mm:.1f}+{cfg.font_h_mm:.1f} = {cfg.total_h_mm:.1f} mm · "
             f"filament change @ Z={cfg.border_h_mm:.1f} mm")
    d.text((30, ph + 66), dims, font=cap, fill=(40, 40, 50, 255))
    d.text((30, ph + 104), specs, font=sub, fill=(120, 120, 130, 255))
    # two colour swatches
    d.rectangle([pw + 8, ph + 66, pw + 34, ph + 92], fill=(*name_rgb, 255),
                outline=(200, 200, 210))
    d.rectangle([pw + 40, ph + 66, pw + 66, ph + 92], fill=(*border_rgb, 255),
                outline=(200, 200, 210))

    out = _out_path(cfg.out_dir, PREVIEW_SUBDIR, f"preview_{cfg.stem}.png")
    card.convert("RGB").save(out, quality=95)
    print(f"[preview] {cfg.name}  font={cfg.font}  icon={cfg.icon}  "
          f"H={cfg.total_h_mm:.1f}mm")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# OUTPUT MODE 2 — OpenSCAD export (STL / 3MF)
# ===========================================================================
def _openscad_defines(cfg):
    b = "true" if cfg.keychain else "false"
    return [
        "-D", f'name="{cfg.name}"',
        "-D", f'font="{cfg.font}"',
        "-D", f'icon="{cfg.icon}"',
        "-D", f'name_color="{cfg.name_color}"',
        "-D", f'border_color="{cfg.border_color}"',
        "-D", f"letter_height={cfg.letter_height_mm}",
        "-D", f"border_width={cfg.border_width_mm}",
        "-D", f"corner_round={cfg.corner_round_mm}",
        "-D", f"border_h={cfg.border_h_mm}",
        "-D", f"font_h={cfg.font_h_mm}",
        "-D", f"bevel={cfg.bevel_mm}",
        "-D", f"icon_scale={cfg.icon_scale}",
        "-D", f"keychain={b}",
        "-D", f"hole_d={cfg.hole_d_mm}",
        "-D", f"hole_wall={cfg.hole_wall_mm}",
        "-D", f"smoothness={cfg.smoothness}",
    ]


def _export(cfg, ext):
    exe = shutil.which("openscad") or shutil.which("openscad.exe")
    if not exe:
        raise SystemExit(
            "OpenSCAD not found on PATH. Install it (https://openscad.org) to "
            "export; --preview works without it. On MakerWorld, just upload "
            "label.scad + the assets/ folder to the Parametric Model Maker.")
    out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"{cfg.stem}.{ext}")
    env = dict(os.environ, OPENSCAD_FONT_PATH=FONT_DIR)
    cmd = [exe, "-o", out] + _openscad_defines(cfg) + [SCAD_FILE]
    print(f"[{ext}] running OpenSCAD ...")
    res = subprocess.run(cmd, cwd=OUT_DIR, env=env, capture_output=True,
                         text=True)
    if res.returncode != 0:
        raise SystemExit(f"OpenSCAD failed:\n{res.stderr}")
    print(f"[{ext}] {cfg.name}  font={cfg.font}  icon={cfg.icon}  "
          f"H={cfg.total_h_mm:.1f}mm")
    print(f"[{ext}] saved -> {out}")
    if ext == "3mf":
        print("[3mf] Colour in the 3MF needs OpenSCAD 2024+ (or MakerWorld). "
              "Two parts export as border + name; assign a filament to each.")
    print(f"[{ext}] single-extruder tip: add a filament change at "
          f"Z = {cfg.border_h_mm:.1f} mm to split border vs name colour.")
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
        hole_wall_mm=a.hole_wall, smoothness=a.smoothness)


def main():
    d = LabelConfig()
    p = argparse.ArgumentParser(
        description="Parametric two-colour name keychain label maker")
    p.add_argument("--name", default=d.name)
    p.add_argument("--font", default=d.font, choices=list(FONTS))
    p.add_argument("--icon", default=d.icon, choices=ICONS)
    p.add_argument("--name-color", dest="name_color", default=d.name_color,
                   help="top layer (letters) hex colour")
    p.add_argument("--border-color", dest="border_color",
                   default=d.border_color, help="bottom layer (border) hex")
    p.add_argument("--letter-height", type=float, default=d.letter_height_mm)
    p.add_argument("--border-width", type=float, default=d.border_width_mm)
    p.add_argument("--corner-round", type=float, default=d.corner_round_mm)
    p.add_argument("--border-h", type=float, default=d.border_h_mm,
                   help="bottom (border colour) band thickness, mm")
    p.add_argument("--font-h", type=float, default=d.font_h_mm,
                   help="top (name colour) band thickness, mm")
    p.add_argument("--bevel", type=float, default=d.bevel_mm,
                   help="45° chamfer on plate edges, mm (0 = square; slower to "
                        "render on old OpenSCAD, fast on 2023+/MakerWorld)")
    p.add_argument("--icon-scale", type=float, default=d.icon_scale)
    p.add_argument("--no-keychain", action="store_true",
                   help="omit the clasp tab + hole")
    p.add_argument("--hole-d", type=float, default=d.hole_d_mm)
    p.add_argument("--hole-wall", type=float, default=d.hole_wall_mm)
    p.add_argument("--smoothness", type=int, default=d.smoothness)
    p.add_argument("--preview", action="store_true", help="write preview PNG")
    p.add_argument("--stl", action="store_true", help="export STL via OpenSCAD")
    p.add_argument("--3mf", dest="threemf", action="store_true",
                   help="export 3MF via OpenSCAD")
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
        _export(cfg, "stl")
    if a.threemf:
        _export(cfg, "3mf")


if __name__ == "__main__":
    main()
