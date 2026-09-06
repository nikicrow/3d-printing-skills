#!/usr/bin/env python3
"""
purge_frisbee.py
================
Parametric **purge frisbee** generator.

A frisbee for multicolour printing: a completely **flat top disc** with a
**thick, beveled rim** around the edge. It is designed to be used as a
"flush into this object" target in the slicer, so the filament wasted during
colour changes ends up inside a toy instead of in the poop bin.

The whole shape is a **solid of revolution**: a 2D cross-section (a list of
``(radius, z)`` points) spun around the Z axis by
:func:`trimesh.creation.revolve`. That makes it cheap to re-generate at any
size — everything below is driven by two numbers, the **diameter** and the
**height**, with every other dimension derived proportionally unless you
override it.

USAGE
-----
    # Default 120 mm across, 40 mm tall — preview PNG + printable STL:
    python purge_frisbee.py --preview --stl

    # A bigger, shallower one:
    python purge_frisbee.py --diameter 160 --height 30 --stl

    # Chunkier rim, thicker top disc:
    python purge_frisbee.py --rim-thickness 10 --top-thickness 3 --stl

DEPENDENCIES
------------
    pip install trimesh numpy pillow matplotlib pydantic --break-system-packages
    (trimesh is only needed for --stl; --preview is pure matplotlib)

----------------------------------------------------------------------------
3D PRINTING NOTES
----------------------------------------------------------------------------
  * Orientation : exported **flat top face down on the plate** (z = 0), rim
                  rising upwards. Print exactly as oriented, then flip it over
                  to use — the plate gives the flying surface a glass-smooth
                  finish. Turn it over in the slicer and you have overhangs;
                  as exported there are none.
  * Supports    : NONE. Every wall is vertical or a <=45 deg bevel/chamfer.
  * Brim        : not needed — the flat disc is the largest possible footprint.
  * Purging     : in Bambu Studio / OrcaSlicer tick "flush into this object"
                  for the frisbee and it soaks up the colour-change purge.
                  Higher infill = more purge absorbed (the printed
                  "purge capacity" below is the solid volume; infill scales it).
  * Material    : PLA is fine. PETG/PLA mixes fly just as badly.
----------------------------------------------------------------------------
"""

import argparse
import math
import os

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Generated outputs are auto-filed into per-tool subfolders so the repo root
# stays tidy: previews/frisbees/*.png and printable_files/frisbees/*.stl.
PREVIEW_SUBDIR = os.path.join("previews", "frisbees")
PRINT_SUBDIR = os.path.join("printable_files", "frisbees")

# Rough density of PLA, g/cm^3 — only used for the "purge capacity" printout.
PLA_DENSITY = 1.24


def _out_path(out_dir, subdir, filename):
    """Return ``<out_dir>/<subdir>/<filename>``, creating the folder if needed."""
    dest = os.path.join(out_dir, subdir)
    os.makedirs(dest, exist_ok=True)
    return os.path.join(dest, filename)


# ===========================================================================
# CONFIG
# ===========================================================================
class FrisbeeConfig(BaseModel):
    """All tunable parameters for one frisbee, validated up front.

    Only ``diameter_mm`` and ``height_mm`` really matter — every other
    dimension defaults to ``None`` and is then filled in *proportionally* by
    :meth:`_derive_defaults`, so a 200 mm frisbee automatically gets a chunkier
    rim than a 90 mm one. Pass any of them explicitly to override.

    Attributes
    ----------
    diameter_mm : float
        Outside diameter of the frisbee, in mm.
    height_mm : float
        Total height from the flat top face to the lip of the rim, in mm.
    rim_thickness_mm : float | None
        Radial wall thickness of the rim, in mm (default: 6% of the diameter).
    top_thickness_mm : float | None
        Thickness of the flat top disc, in mm (default: 2% of the diameter).
    rim_bevel_mm : float | None
        Size of the 45 deg bevels on the outer and inner top edges of the rim,
        in mm (default: 30% of the rim thickness).
    base_bevel_mm : float | None
        Small 45 deg chamfer around the flat face on the plate, in mm
        (default: 15% of the rim thickness). Kills the "elephant foot" and
        gives the finished frisbee a soft outer edge.
    inner_fillet_mm : float | None
        45 deg chamfer where the inside of the rim meets the top disc, in mm
        (default: 60% of the rim thickness). This is what stops the rim
        snapping off the disc.
    segments : int
        Number of facets around the circumference (higher = rounder + heavier).
    out_dir : str
        Directory the preview PNG / STL files are written to.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    diameter_mm: float = Field(120.0, gt=0)
    height_mm: float = Field(40.0, gt=0)

    rim_thickness_mm: float | None = Field(None, gt=0)
    top_thickness_mm: float | None = Field(None, gt=0)
    rim_bevel_mm: float | None = Field(None, ge=0)
    base_bevel_mm: float | None = Field(None, ge=0)
    inner_fillet_mm: float | None = Field(None, ge=0)

    segments: int = Field(256, ge=24)
    out_dir: str = OUT_DIR

    # -- derived defaults ---------------------------------------------------
    @model_validator(mode="after")
    def _derive_defaults(self) -> "FrisbeeConfig":
        """Fill in any dimension left as ``None``, then sanity-check the lot."""
        # ``validate_assignment=True`` would re-run this validator on every
        # ``self.x = ...``, so build a plain dict of updates and poke the values
        # straight into ``__dict__`` (this is the documented escape hatch).
        derived = {}
        if self.rim_thickness_mm is None:
            derived["rim_thickness_mm"] = round(0.06 * self.diameter_mm, 2)
        if self.top_thickness_mm is None:
            derived["top_thickness_mm"] = round(0.02 * self.diameter_mm, 2)
        self.__dict__.update(derived)

        rim = self.rim_thickness_mm
        derived = {}
        if self.rim_bevel_mm is None:
            derived["rim_bevel_mm"] = round(0.30 * rim, 2)
        if self.base_bevel_mm is None:
            derived["base_bevel_mm"] = round(0.15 * rim, 2)
        if self.inner_fillet_mm is None:
            derived["inner_fillet_mm"] = round(0.60 * rim, 2)
        self.__dict__.update(derived)

        # -- geometry has to actually close up ------------------------------
        if self.rim_thickness_mm + self.inner_fillet_mm >= self.radius_mm:
            raise ValueError(
                "rim_thickness_mm + inner_fillet_mm must be less than the "
                "radius (diameter_mm / 2) — the rim would swallow the disc")
        if 2 * self.rim_bevel_mm >= self.rim_thickness_mm:
            raise ValueError(
                "rim_bevel_mm must be less than half rim_thickness_mm, "
                "otherwise the two bevels meet and the rim has no flat top")
        if self.base_bevel_mm >= self.rim_thickness_mm:
            raise ValueError("base_bevel_mm must be less than rim_thickness_mm")
        if (self.top_thickness_mm + self.inner_fillet_mm + self.rim_bevel_mm
                >= self.height_mm):
            raise ValueError(
                "height_mm is too small for this top disc + fillet + bevel "
                "(try a taller frisbee or a thinner rim)")
        if self.base_bevel_mm >= self.top_thickness_mm:
            raise ValueError(
                "base_bevel_mm must be less than top_thickness_mm, or the "
                "chamfer eats through the flat top disc")
        return self

    # -- handy read-only derivations ---------------------------------------
    @property
    def radius_mm(self) -> float:
        """float: outer radius, in mm."""
        return self.diameter_mm / 2.0

    @property
    def inner_radius_mm(self) -> float:
        """float: radius of the inside face of the rim, in mm."""
        return self.radius_mm - self.rim_thickness_mm

    @property
    def slug(self) -> str:
        """str: filename stem, e.g. ``d120_h40``."""
        return f"d{self.diameter_mm:g}_h{self.height_mm:g}"

    def profile(self) -> np.ndarray:
        """Return the cross-section to revolve, as ``(radius, z)`` points.

        The loop starts at the centre of the flat top face (which sits on the
        build plate at ``z = 0``), runs out to the rim, up and over the rim,
        back down its inside face, and in along the underside of the disc:

        ::

              z
              ^                 6 ______ 5
              |                  /      \\
              |               7 |        | 4        (rim, thick + beveled)
              |                 |        |
              |     10 _________|8       |
              |      |    9 \\___|        |          (top disc + fillet)
              |      |__________________ | 3
              |      1                 2               <- flat face, on plate
              +-------------------------------> r
        """
        R = self.radius_mm
        H = self.height_mm
        rim = self.rim_thickness_mm
        top = self.top_thickness_mm
        bev = self.rim_bevel_mm
        base = self.base_bevel_mm
        fil = self.inner_fillet_mm
        Ri = self.inner_radius_mm

        return np.array(
            [
                [0.0, 0.0],              # 1  centre of the flat top face
                [R - base, 0.0],         # 2  flat face out to the chamfer
                [R, base],               # 3  small chamfer on the plate edge
                [R, H - bev],            # 4  outer wall of the rim
                [R - bev, H],            # 5  bevel on the outer lip
                [Ri + bev, H],           # 6  flat top of the rim
                [Ri, H - bev],           # 7  bevel on the inner lip
                [Ri, top + fil],         # 8  inside face of the rim
                [Ri - fil, top],         # 9  chamfer into the disc
                [0.0, top],              # 10 underside of the disc, to centre
            ],
            dtype=float,
        )

    @property
    def volume_cm3(self) -> float:
        """float: solid volume, in cm^3, from Pappus's centroid theorem.

        ``V = 2 * pi * r_centroid * A`` for a plane area A spun about the Z
        axis — no mesh needed, so ``--preview`` can report it too.
        """
        pts = self.profile()
        r, z = pts[:, 0], pts[:, 1]
        r2, z2 = np.roll(r, -1), np.roll(z, -1)
        cross = r * z2 - r2 * z                      # shoelace terms
        area = cross.sum() / 2.0
        r_centroid = ((r + r2) * cross).sum() / (6.0 * area)
        return abs(2.0 * math.pi * r_centroid * area) / 1000.0

    @property
    def mass_g(self) -> float:
        """float: solid mass in grams of PLA (100% infill upper bound)."""
        return self.volume_cm3 * PLA_DENSITY


# ===========================================================================
# GEOMETRY
# ===========================================================================
def build_mesh(cfg):
    """Revolve :meth:`FrisbeeConfig.profile` into a watertight solid."""
    import trimesh  # imported lazily: --preview must work without trimesh

    body = trimesh.creation.revolve(cfg.profile(), sections=cfg.segments)
    body.merge_vertices()
    body.remove_unreferenced_vertices()
    body.fix_normals()

    if not body.is_watertight:
        raise RuntimeError("Generated frisbee is not watertight")
    if body.body_count != 1:
        raise RuntimeError(f"Expected one connected body, got {body.body_count}")
    if not body.is_winding_consistent:
        raise RuntimeError("Generated frisbee has inconsistent face winding")
    return body


# ===========================================================================
# OUTPUT MODE 1 — PREVIEW PNG
# ===========================================================================
def make_preview(cfg):
    """Write a two-panel PNG: the cross-section and the view from above."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, Polygon

    pts = cfg.profile()
    # Mirror the half-profile through the axis for a full cross-section.
    mirrored = (pts[::-1] * [-1.0, 1.0])[1:-1]      # drop the two axis points
    section = np.vstack([pts, mirrored])

    fig, (axs, axt) = plt.subplots(1, 2, figsize=(13, 5.6))

    # --- cross-section -----------------------------------------------------
    axs.add_patch(Polygon(section, closed=True, facecolor="#5aa7d6",
                          edgecolor="#1b3b52", linewidth=1.6))
    axs.axhline(0, color="#999", linewidth=1.0, linestyle="--")
    axs.text(cfg.radius_mm * 1.30, -0.02 * cfg.height_mm,
             "build plate (flat top face down)",
             ha="right", va="top", fontsize=9, color="#555")
    dim_y = -0.17 * cfg.height_mm
    axs.annotate("", xy=(-cfg.radius_mm, dim_y), xytext=(cfg.radius_mm, dim_y),
                 arrowprops=dict(arrowstyle="<->", color="black"))
    axs.text(0, dim_y + 0.02 * cfg.height_mm, f"{cfg.diameter_mm:g} mm",
             ha="center", va="bottom", fontsize=10)
    axs.annotate("", xy=(cfg.radius_mm * 1.16, 0),
                 xytext=(cfg.radius_mm * 1.16, cfg.height_mm),
                 arrowprops=dict(arrowstyle="<->", color="black"))
    axs.text(cfg.radius_mm * 1.20, cfg.height_mm / 2, f"{cfg.height_mm:g} mm",
             va="center", fontsize=10, rotation=90)
    axs.annotate(f"rim {cfg.rim_thickness_mm:g} mm, beveled "
                 f"{cfg.rim_bevel_mm:g} mm",
                 xy=(cfg.radius_mm - cfg.rim_thickness_mm / 2, cfg.height_mm),
                 xytext=(0, cfg.height_mm * 0.86), ha="center", fontsize=9,
                 arrowprops=dict(arrowstyle="->", color="black"))
    axs.annotate(f"flat top disc {cfg.top_thickness_mm:g} mm",
                 xy=(-cfg.radius_mm * 0.35, cfg.top_thickness_mm / 2),
                 xytext=(-cfg.radius_mm * 0.30, cfg.height_mm * 0.45),
                 ha="center", fontsize=9,
                 arrowprops=dict(arrowstyle="->", color="black"))
    axs.set_xlim(-cfg.radius_mm * 1.35, cfg.radius_mm * 1.35)
    axs.set_ylim(-cfg.height_mm * 0.34, cfg.height_mm * 1.25)
    axs.set_aspect("equal")
    axs.set_title("cross-section (as printed)")
    axs.axis("off")

    # --- from above --------------------------------------------------------
    axt.add_patch(Circle((0, 0), cfg.radius_mm, facecolor="#5aa7d6",
                         edgecolor="#1b3b52", linewidth=1.6))
    axt.add_patch(Circle((0, 0), cfg.inner_radius_mm, facecolor="#bfe0f2",
                         edgecolor="#1b3b52", linewidth=1.2))
    axt.text(0, 0, f"purge here\n{cfg.volume_cm3:.0f} cm³ solid\n"
                   f"≈ {cfg.mass_g:.0f} g PLA",
             ha="center", va="center", fontsize=10, color="#1b3b52")
    axt.set_xlim(-cfg.radius_mm * 1.15, cfg.radius_mm * 1.15)
    axt.set_ylim(-cfg.radius_mm * 1.15, cfg.radius_mm * 1.15)
    axt.set_aspect("equal")
    axt.set_title("from above (rim shaded dark)")
    axt.axis("off")

    fig.suptitle(f"PURGE FRISBEE — {cfg.diameter_mm:g} mm across, "
                 f"{cfg.height_mm:g} mm tall", fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = _out_path(cfg.out_dir, PREVIEW_SUBDIR, f"preview_frisbee_{cfg.slug}.png")
    fig.savefig(out, facecolor="white", dpi=110)
    plt.close(fig)
    print(f"[preview] {cfg.diameter_mm:g}mm dia x {cfg.height_mm:g}mm tall  "
          f"rim={cfg.rim_thickness_mm:g}mm  top={cfg.top_thickness_mm:g}mm")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# OUTPUT MODE 2 — STL
# ===========================================================================
def make_stl(cfg):
    body = build_mesh(cfg)
    out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"frisbee_{cfg.slug}.stl")
    body.export(out)

    ex = body.extents
    print(f"[stl] size={ex[0]:.1f} x {ex[1]:.1f} x {ex[2]:.1f} mm  "
          f"rim={cfg.rim_thickness_mm:g}mm  bevel={cfg.rim_bevel_mm:g}mm  "
          f"verts={len(body.vertices)}  faces={len(body.faces)}  "
          f"{'watertight' if body.is_watertight else 'NOT watertight'}")
    print(f"[stl] purge capacity: {body.volume / 1000.0:.1f} cm³ solid "
          f"(≈ {body.volume / 1000.0 * PLA_DENSITY:.0f} g PLA at 100% infill)")
    print(f"[stl] saved -> {out}")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(args):
    return FrisbeeConfig(
        diameter_mm=args.diameter,
        height_mm=args.height,
        rim_thickness_mm=args.rim_thickness,
        top_thickness_mm=args.top_thickness,
        rim_bevel_mm=args.rim_bevel,
        base_bevel_mm=args.base_bevel,
        inner_fillet_mm=args.inner_fillet,
        segments=args.segments,
    )


def main():
    d = FrisbeeConfig()
    p = argparse.ArgumentParser(
        description="Parametric purge frisbee: flat top, thick beveled rim")
    p.add_argument("--diameter", type=float, default=d.diameter_mm,
                   help="outside diameter, mm (default: %(default)s)")
    p.add_argument("--height", type=float, default=d.height_mm,
                   help="total height / rim depth, mm (default: %(default)s)")
    p.add_argument("--rim-thickness", type=float, default=None,
                   help="rim wall thickness, mm (default: 6%% of diameter)")
    p.add_argument("--top-thickness", type=float, default=None,
                   help="flat top disc thickness, mm (default: 2%% of diameter)")
    p.add_argument("--rim-bevel", type=float, default=None,
                   help="bevel on the rim lip, mm (default: 30%% of the rim)")
    p.add_argument("--base-bevel", type=float, default=None,
                   help="chamfer around the flat face, mm (default: 15%% of the rim)")
    p.add_argument("--inner-fillet", type=float, default=None,
                   help="chamfer rim->disc, mm (default: 60%% of the rim)")
    p.add_argument("--segments", type=int, default=d.segments,
                   help="facets around the circumference (default: %(default)s)")
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
