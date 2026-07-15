#!/usr/bin/env python3
"""
playdoh_scraper.py
==================
Parametric toddler-friendly Play-Doh / clay SCRAPER generator.

A scraper is a gentle wedge: seen from above it is a rectangle; seen from the
side it is an elongated, low-gradient ramp rising from a thin **blunt** front
scraping edge (deliberately not a blade — toddler-safe) up to a thicker back.
The thick back has a flat level platform with the child's **name raised
(bumping out)** on top. The flat base prints support-free and rests on the
table; you push the blunt front edge along a surface to scrape up dough.

Like :mod:`playdoh_roller` / :mod:`playdoh_stamp`, all parameters live in a
validated :class:`ScraperConfig` (pydantic), and the geometry is delegated to
the shared :mod:`mesh_utils` (here :func:`mesh_utils.build_prism_between` — a
watertight solid between a flat base and a shaped top heightfield).

USAGE
-----
    # Preview PNG (side profile + top view):
    python playdoh_scraper.py --name "Ember" --preview

    # Printable STL (flat base down, no supports):
    python playdoh_scraper.py --name "Ember" --stl

    # Gentler ramp / blunter edge:
    python playdoh_scraper.py --name "Leo" --depth 60 --edge-height 2.0 --stl

DEPENDENCIES
------------
    pip install trimesh numpy pillow matplotlib pydantic --break-system-packages
    (trimesh is only needed for --stl)

----------------------------------------------------------------------------
3D PRINTING NOTES
----------------------------------------------------------------------------
  * Orientation : exported flat base down (as used). Print as oriented.
  * Supports    : NONE. The top is a single ramp/heightfield above a flat base
                  — no overhangs. The raised name prints as the last layers.
  * Layer height: 0.15 mm keeps the raised name and the blunt edge crisp.
  * Edge safety : the front edge is a blunt vertical face (default 1.5 mm), not
                  a blade. Raise --edge-height for an even blunter edge.
  * 2nd colour  : STL cannot store colour. The raised name is the ONLY geometry
                  above the back platform, so to print the name in a different
                  colour just add a single filament change at Z = back_height
                  (printed on export) in Bambu Studio — no AMS or extra files
                  needed. (With an AMS you can instead height-range-assign the
                  top layers to filament 2.)
  * Material    : PLA is fine for Play-Doh (non-edible modelling compound).
----------------------------------------------------------------------------
"""

import argparse
import math
import os

import numpy as np
from PIL import Image, ImageDraw
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mesh_utils import build_prism_between
from svg_processing import load_font

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Generated outputs are auto-filed into per-tool subfolders so the repo root
# stays tidy: previews/scrapers/*.png and printable_files/scrapers/*.stl.
PREVIEW_SUBDIR = os.path.join("previews", "scrapers")
PRINT_SUBDIR = os.path.join("printable_files", "scrapers")


def _out_path(out_dir, subdir, filename):
    """Return ``<out_dir>/<subdir>/<filename>``, creating the folder if needed."""
    dest = os.path.join(out_dir, subdir)
    os.makedirs(dest, exist_ok=True)
    return os.path.join(dest, filename)


# Play-Doh-ish preview colours (shared look with the roller/stamp previews)
CREAM = (245, 232, 205)
IMPRINT = (150, 120, 80)
WEDGE = (214, 180, 138)
ACCENT = (40, 130, 200)        # 2nd-colour highlight for the raised name


# ===========================================================================
# PARAMETER SCHEMA
# ===========================================================================
class ScraperConfig(BaseModel):
    """Validated parameters for one Play-Doh scraper generation run.

    Attributes
    ----------
    name : str
        Name raised on the back platform.
    width_mm : float
        Scraper width, in mm (length of the scraping edge, along X).
    depth_mm : float
        Front-to-back depth, in mm (along Y).
    back_height_mm : float
        Height of the thick back, in mm.
    edge_height_mm : float
        Thickness of the blunt front scraping edge, in mm (kept well above a
        blade for toddler safety).
    platform_depth_mm : float
        Depth of the flat level platform at the back (holds the name), in mm.
        The remaining depth is the ramp.
    name_relief_mm : float
        How far the name bumps out of the platform, in mm.
    letter_height_mm : float
        Target cap height of the name, in mm (auto-shrunk to fit the platform).
    name_margin_mm : float
        Clear margin kept around the name on the platform, in mm.
    ppm : int
        Heightfield resolution in pixels per mm.
    out_dir : str
        Directory the preview PNG / STL files are written to.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    name: str = Field("Ember", min_length=1)

    width_mm: float = Field(120.0, gt=0)
    depth_mm: float = Field(60.0, gt=0)
    back_height_mm: float = Field(12.0, gt=0)
    edge_height_mm: float = Field(1.5, gt=0)
    platform_depth_mm: float = Field(18.0, gt=0)

    name_relief_mm: float = Field(1.0, gt=0)
    letter_height_mm: float = Field(9.0, gt=0)
    name_margin_mm: float = Field(5.0, ge=0)

    ppm: int = Field(6, ge=1)
    out_dir: str = OUT_DIR

    @model_validator(mode="after")
    def _check(self) -> "ScraperConfig":
        if self.edge_height_mm >= self.back_height_mm:
            raise ValueError("edge_height_mm must be less than back_height_mm")
        if self.platform_depth_mm >= self.depth_mm:
            raise ValueError("platform_depth_mm must be less than depth_mm "
                             "(the rest is the ramp)")
        return self

    @property
    def safe_name(self) -> str:
        return self.name.lower().replace(" ", "_")

    @property
    def ramp_len_mm(self) -> float:
        """float: horizontal length of the ramp (front to platform), in mm."""
        return self.depth_mm - self.platform_depth_mm

    @property
    def ramp_angle_deg(self) -> float:
        """float: ramp angle above horizontal, in degrees."""
        rise = self.back_height_mm - self.edge_height_mm
        return math.degrees(math.atan2(rise, self.ramp_len_mm))


# ===========================================================================
# GEOMETRY FIELDS
# ===========================================================================
def _text_mask(name, letter_h_px):
    """Render ``name`` in a chunky font to a tight ``L`` mask (255 = ink)."""
    probe = ImageDraw.Draw(Image.new("L", (8, 8), 0))
    size = letter_h_px
    font, font_name = load_font(size)
    for _ in range(8):
        font, font_name = load_font(size)
        bb = probe.textbbox((0, 0), name, font=font)
        th = bb[3] - bb[1]
        if th <= 1:
            break
        s = letter_h_px / th
        if abs(s - 1.0) < 0.02:
            break
        size *= s
    bb = probe.textbbox((0, 0), name, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = int(0.12 * th) + 4
    img = Image.new("L", (tw + 2 * pad, th + 2 * pad), 0)
    ImageDraw.Draw(img).text((pad - bb[0], pad - bb[1]), name, font=font,
                             fill=255)
    return img, font_name


def build_top_field(cfg):
    """Build the scraper's top-surface heightfield (ramp + raised name).

    Returns
    -------
    top : numpy.ndarray, shape (H, W)
        Top height in mm at each grid node.
    font_name : str
        The font used for the name.
    grid : tuple(int, int)
        ``(W, H)`` grid size in pixels.
    """
    ppm = cfg.ppm
    W = max(2, int(round(cfg.width_mm * ppm)))
    H = max(2, int(round(cfg.depth_mm * ppm)))
    ys = np.linspace(0.0, cfg.depth_mm, H)

    # Side profile along Y: blunt front edge (y=0) ramps up to the back height,
    # then a flat platform over the back `platform_depth_mm`.
    y_pl = cfg.ramp_len_mm                        # ramp ends / platform starts
    ramp = cfg.edge_height_mm + (
        (cfg.back_height_mm - cfg.edge_height_mm) * (ys / max(y_pl, 1e-6)))
    prof = np.where(ys <= y_pl, ramp, cfg.back_height_mm)
    top = np.repeat(prof[:, None], W, axis=1)     # (H, W)

    # Name raised on the platform (read the right way up from above).
    j_pl = int(round(y_pl * ppm))
    marg = int(cfg.name_margin_mm * ppm)
    plat_h = H - j_pl
    target_h = min(cfg.letter_height_mm * ppm, max(4, plat_h - 2 * marg))
    img, font_name = _text_mask(cfg.name, target_h)
    max_w = max(4, W - 2 * marg)
    if img.width > max_w:                          # shrink long names to fit
        s = max_w / img.width
        img = img.resize((max(1, int(img.width * s)),
                          max(1, int(img.height * s))), Image.LANCZOS)
    arr = np.asarray(img) > 127
    arr = np.fliplr(arr)                            # face the user as they scrape
                                                    # (reads with the edge away)
    ah, aw = arr.shape
    ax = (W - aw) // 2
    ay = j_pl + (plat_h - ah) // 2
    ay = max(0, min(ay, H - ah))
    mask = np.zeros((H, W), dtype=bool)
    mask[ay:ay + ah, ax:ax + aw] = arr
    top = top + cfg.name_relief_mm * mask

    return top, font_name, (W, H)


# ===========================================================================
# OUTPUT MODE 1 — PREVIEW PNG (side profile + top view)
# ===========================================================================
def make_preview(cfg):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top, font_name, (W, H) = build_top_field(cfg)
    wedge_c = tuple(v / 255 for v in WEDGE)
    imprint_c = tuple(v / 255 for v in IMPRINT)
    fig, (axp, axt) = plt.subplots(
        1, 2, figsize=(12, 5), dpi=130,
        gridspec_kw={"width_ratios": [1.15, 1.0]})

    # --- side profile (Y-Z), a representative slice through the ramp ---
    ys = np.linspace(0.0, cfg.depth_mm, H)
    prof = top[:, W // 4]                          # slice away from the name
    axp.fill_between(ys, 0, prof, color=wedge_c, edgecolor=imprint_c,
                     linewidth=2)
    axp.annotate("blunt scraping edge", xy=(0, cfg.edge_height_mm),
                 xytext=(cfg.depth_mm * 0.22, cfg.back_height_mm * 0.75),
                 fontsize=9, ha="left",
                 arrowprops=dict(arrowstyle="->", color="black"))
    axp.annotate(f"name platform\n(name bumps out)",
                 xy=(cfg.depth_mm - cfg.platform_depth_mm / 2,
                     cfg.back_height_mm),
                 xytext=(cfg.depth_mm * 0.30, cfg.back_height_mm * 1.15),
                 fontsize=9, ha="center",
                 arrowprops=dict(arrowstyle="->", color="black"))
    axp.set_title(f"side profile — ~{cfg.ramp_angle_deg:.0f}° ramp",
                  fontsize=12, fontweight="bold")
    axp.set_xlabel("front → back (mm)")
    axp.set_ylabel("height (mm)")
    axp.set_aspect("equal")
    axp.set_ylim(-1, cfg.back_height_mm + cfg.name_relief_mm + 3)

    # --- top view with the raised name ---
    raised = (top > (np.repeat(
        np.where(np.linspace(0, cfg.depth_mm, H) <= cfg.ramp_len_mm,
                 cfg.edge_height_mm + (cfg.back_height_mm - cfg.edge_height_mm)
                 * (np.linspace(0, cfg.depth_mm, H) / max(cfg.ramp_len_mm, 1e-6)),
                 cfg.back_height_mm)[:, None], W, axis=1)) + 1e-6)
    rgb = np.empty((H, W, 3), dtype=np.uint8)
    for c in range(3):
        rgb[..., c] = np.where(raised, ACCENT[c], WEDGE[c])
    # Show it from the user's scraping viewpoint (standing at the back, edge
    # pushed away): a 180° view of the bird's-eye, so the raised name — which is
    # mirrored on the part so it reads while scraping — appears upright here.
    axt.imshow(np.rot90(rgb, 2), extent=[0, cfg.width_mm, 0, cfg.depth_mm],
               origin="lower")
    axt.set_title("top view (name in 2nd colour, reads as you scrape)",
                  fontsize=12, fontweight="bold")
    axt.set_xlabel("width (mm)")
    axt.set_ylabel("distance from back edge (mm)")
    axt.annotate("blunt scraping edge (far side)",
                 xy=(cfg.width_mm / 2, cfg.depth_mm),
                 xytext=(cfg.width_mm / 2, cfg.depth_mm * 0.9),
                 ha="center", fontsize=9,
                 arrowprops=dict(arrowstyle="->", color="black"))

    fig.suptitle(f"SCRAPER — {cfg.name}", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    out = _out_path(cfg.out_dir, PREVIEW_SUBDIR,
                    f"preview_scraper_{cfg.safe_name}.png")
    fig.savefig(out, facecolor="white")
    plt.close(fig)
    print(f"[preview] font={font_name}  {cfg.width_mm:.0f}x{cfg.depth_mm:.0f}mm  "
          f"ramp={cfg.ramp_angle_deg:.0f}deg")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# OUTPUT MODE 2 — STL
# ===========================================================================
def make_stl(cfg):
    top, font_name, (W, H) = build_top_field(cfg)
    body = build_prism_between(0.0, top, cfg.width_mm, cfg.depth_mm)

    out = _out_path(cfg.out_dir, PRINT_SUBDIR,
                    f"scraper_{cfg.safe_name}.stl")
    body.export(out)
    wt = "watertight" if body.is_watertight else "NOT watertight"
    print(f"[stl] font={font_name}  {cfg.width_mm:.0f}x{cfg.depth_mm:.0f}mm  "
          f"ramp={cfg.ramp_angle_deg:.0f}deg  edge={cfg.edge_height_mm:.1f}mm  "
          f"verts={len(body.vertices)}  faces={len(body.faces)}  {wt}")
    print(f"[stl] saved -> {out}")
    # The raised name is the ONLY geometry above the platform, so a single
    # filament change at this Z colours exactly the name (2nd colour).
    print(f"[stl] 2nd-colour tip: add a filament change at Z = "
          f"{cfg.back_height_mm:.1f} mm to print the name in another colour.")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(args):
    return ScraperConfig(
        name=args.name,
        width_mm=args.width,
        depth_mm=args.depth,
        back_height_mm=args.back_height,
        edge_height_mm=args.edge_height,
        platform_depth_mm=args.platform_depth,
        name_relief_mm=args.name_relief,
        letter_height_mm=args.letter_height,
        name_margin_mm=args.name_margin,
        ppm=args.ppm,
    )


def main():
    d = ScraperConfig()
    p = argparse.ArgumentParser(
        description="Parametric toddler Play-Doh scraper maker")
    p.add_argument("--name", default=d.name)
    p.add_argument("--width", type=float, default=d.width_mm)
    p.add_argument("--depth", type=float, default=d.depth_mm)
    p.add_argument("--back-height", type=float, default=d.back_height_mm)
    p.add_argument("--edge-height", type=float, default=d.edge_height_mm,
                   help="blunt front-edge thickness, mm (bigger = safer/blunter)")
    p.add_argument("--platform-depth", type=float, default=d.platform_depth_mm,
                   help="depth of the flat name platform at the back, mm")
    p.add_argument("--name-relief", type=float, default=d.name_relief_mm)
    p.add_argument("--letter-height", type=float, default=d.letter_height_mm)
    p.add_argument("--name-margin", type=float, default=d.name_margin_mm)
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
