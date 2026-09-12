#!/usr/bin/env python3
"""
u_bracket.py
============
Parametric **U-bracket** (U-hook / U-clip) generator.

Seen from the side the part is a **U**: a **circular** bend at one end joining
two **straight parallel legs**. The bend's inner diameter is the width of the
slot between the legs (default **20 mm**), each leg is **50 mm** long, and the
band of material is a constant **4 mm** thick, so the finished part is stiff
rather than springy. The whole **outer** surface carries **shallow transverse
ridges** — a gentle ripple, not a saw-tooth — so the part is easy to grip and
does not look like a plain bent strip.

The geometry is a **swept band**, built in three steps:

  1. a **centreline** through the middle of the material — leg, semicircular
     arc, leg — sampled at even arc-length steps;
  2. an **inner** and an **outer** wall, offset +-``thickness/2`` along the
     2D normal of that centreline (the outer one additionally displaced by the
     ridge ripple);
  3. a rectangular ``thickness x width`` cross-section swept along the path and
     closed with a flat cap at each leg tip — one watertight solid, no
     booleans.

Because both walls are offsets of the same path, wall thickness is exactly
constant all the way round the bend, which is what makes the part rigid.

USAGE
-----
    # Default 20 mm slot, 50 mm legs, 4 mm wall — preview PNG + printable STL:
    python u_bracket.py --preview --stl

    # A wider, deeper bracket:
    python u_bracket.py --inner-diameter 25 --leg-length 60 --stl

    # Beefier band, smoother (no ridges):
    python u_bracket.py --thickness 5 --width 16 --ridge-height 0 --stl

DEPENDENCIES
------------
    pip install trimesh numpy matplotlib pydantic --break-system-packages
    (trimesh is only needed for --stl; --preview is pure numpy + matplotlib)

----------------------------------------------------------------------------
3D PRINTING NOTES
----------------------------------------------------------------------------
  * Orientation : exported **lying flat on its side** — the U shape is in the
                  bed plane and the 12 mm width is the print height. Print
                  exactly as oriented.
  * Supports    : NONE. Lying flat, every wall is vertical; the arch is a
                  flat-on-the-bed curve, not an overhang. (Stood upright the
                  bend becomes a bridge and would need supports — don't.)
  * Layer lines : the layers stack across the width, so the U is being asked
                  to bend *in the plane of the layers*. That is the strong
                  direction for a bent part like this.
  * Walls       : 4 mm at a 0.4 mm nozzle is 5 perimeters a side — set
                  perimeters/walls to 4-5 and the part is effectively solid,
                  infill barely matters.
  * Material    : PLA is fine and stiff. PETG if it needs to survive being
                  flexed or left in a hot car.
----------------------------------------------------------------------------
"""

import argparse
import math
import os

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# Generated outputs are auto-filed into per-tool subfolders so the repo root
# stays tidy: previews/brackets/*.png and printable_files/brackets/*.stl.
PREVIEW_SUBDIR = os.path.join("previews", "brackets")
PRINT_SUBDIR = os.path.join("printable_files", "brackets")

# Rough density of PLA, g/cm^3 — only used for the printed mass estimate.
PLA_DENSITY = 1.24


def _out_path(out_dir, subdir, filename):
    """Return ``<out_dir>/<subdir>/<filename>``, creating the folder if needed."""
    dest = os.path.join(out_dir, subdir)
    os.makedirs(dest, exist_ok=True)
    return os.path.join(dest, filename)


def _smoothstep(x):
    """Smooth 0 -> 1 ramp on ``x in [0, 1]`` (flat at both ends)."""
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


# ===========================================================================
# CONFIG
# ===========================================================================
class UBracketConfig(BaseModel):
    """All tunable parameters for one U-bracket, validated up front.

    The four numbers that define the part are ``inner_diameter_mm``,
    ``leg_length_mm``, ``thickness_mm`` and ``width_mm``; the ridge fields only
    decorate the outer surface and can be switched off with
    ``ridge_height_mm=0``.

    Attributes
    ----------
    inner_diameter_mm : float
        Inner diameter of the circular bend, in mm — i.e. the clear gap
        between the two legs, since the legs run tangent to the bend.
    leg_length_mm : float
        Length of each straight leg, in mm, measured from where the bend ends
        to the leg tip. (Overall height is this plus the bend's outer radius.)
    thickness_mm : float
        Thickness of the band of material, in mm. Constant everywhere,
        including around the bend.
    width_mm : float
        Width of the band, in mm — the third dimension, and the print height
        in the exported orientation.
    ridge_height_mm : float
        How far the ridges stand proud of the outer surface, in mm. These sit
        *on top of* the nominal thickness, so the wall is never thinner than
        ``thickness_mm``. Set to 0 for a smooth outer face.
    ridge_pitch_mm : float
        Distance from one ridge crest to the next, measured along the outer
        surface, in mm.
    ridge_taper_mm : float
        Length at each leg tip over which the ridges fade out to nothing, in
        mm, so the tips end in clean flat faces.
    arc_segments : int
        Number of facets around the 180 deg bend (higher = rounder + heavier).
    out_dir : str
        Directory the preview PNG / STL files are written to.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    inner_diameter_mm: float = Field(20.0, gt=0)
    leg_length_mm: float = Field(50.0, gt=0)
    thickness_mm: float = Field(4.0, gt=0)
    width_mm: float = Field(12.0, gt=0)
    ridge_height_mm: float = Field(0.6, ge=0)
    ridge_pitch_mm: float = Field(4.0, gt=0)
    ridge_taper_mm: float = Field(5.0, ge=0)
    arc_segments: int = Field(160, ge=24, le=2000)
    out_dir: str = OUT_DIR

    @model_validator(mode="after")
    def _check_proportions(self):
        if self.ridge_height_mm > self.thickness_mm / 2.0:
            raise ValueError(
                "ridge_height_mm should stay under half the wall thickness — "
                f"got {self.ridge_height_mm} mm on a {self.thickness_mm} mm wall")
        if 2.0 * self.ridge_taper_mm > self.leg_length_mm:
            raise ValueError(
                "ridge_taper_mm is too long for these legs — the ridges would "
                "never reach full height")
        return self

    # --- derived dimensions ------------------------------------------------
    @property
    def inner_radius_mm(self) -> float:
        """float: radius of the inner face of the bend."""
        return self.inner_diameter_mm / 2.0

    @property
    def centre_radius_mm(self) -> float:
        """float: radius of the swept centreline (mid-thickness) of the bend."""
        return self.inner_radius_mm + self.thickness_mm / 2.0

    @property
    def outer_radius_mm(self) -> float:
        """float: radius of the outer face of the bend (before ridges)."""
        return self.inner_radius_mm + self.thickness_mm

    @property
    def span_mm(self) -> float:
        """float: overall width across the outside of the two legs, in mm."""
        return 2.0 * self.outer_radius_mm

    @property
    def height_mm(self) -> float:
        """float: overall height, leg tip to the crown of the bend, in mm."""
        return self.leg_length_mm + self.outer_radius_mm

    @property
    def arc_length_mm(self) -> float:
        """float: centreline length of the 180 deg bend, in mm."""
        return math.pi * self.centre_radius_mm

    @property
    def path_length_mm(self) -> float:
        """float: total centreline length, leg tip to leg tip, in mm."""
        return 2.0 * self.leg_length_mm + self.arc_length_mm

    @property
    def volume_cm3(self) -> float:
        """float: solid volume in cm^3, ridges ignored (Pappus on the centreline).

        Sweeping a ``thickness x width`` rectangle along its own centroid path
        gives ``area * path length`` exactly — the extra material on the
        outside of the bend cancels the material missing from the inside.
        """
        return self.thickness_mm * self.width_mm * self.path_length_mm / 1000.0

    @property
    def mass_g(self) -> float:
        """float: solid mass in grams of PLA (100% infill upper bound)."""
        return self.volume_cm3 * PLA_DENSITY

    @property
    def slug(self) -> str:
        """str: filename-safe summary of the geometry."""
        def n(v):
            return f"{v:g}".replace(".", "p")
        return (f"id{n(self.inner_diameter_mm)}_leg{n(self.leg_length_mm)}"
                f"_t{n(self.thickness_mm)}_w{n(self.width_mm)}")

    # --- the path ----------------------------------------------------------
    def centreline(self):
        """Sample the centreline: leg up, 180 deg bend, leg down.

        Returns
        -------
        points : (n, 2) float array
            Centreline points in the XY plane (the plane the U is drawn in).
        normals : (n, 2) float array
            Unit normals, always pointing *outwards* (away from the slot).
        s : (n,) float array
            Arc length along the path at each point, starting at 0.
        """
        r = self.centre_radius_mm
        leg = self.leg_length_mm
        arc = self.arc_length_mm

        # Even arc-length sampling, fine enough to resolve a ridge smoothly.
        step = min(self.arc_length_mm / self.arc_segments,
                   self.ridge_pitch_mm / 16.0 if self.ridge_height_mm else 1e9,
                   0.5)
        n = max(int(round(self.path_length_mm / step)) + 1, 64)
        s = np.linspace(0.0, self.path_length_mm, n)

        points = np.zeros((n, 2))
        tangents = np.zeros((n, 2))

        on_leg_a = s <= leg                         # left leg, travelling up
        on_arc = (s > leg) & (s < leg + arc)        # over the bend
        on_leg_b = s >= leg + arc                   # right leg, travelling down

        # left leg: x = -r, y climbs from -leg to 0
        points[on_leg_a] = np.column_stack([
            np.full(on_leg_a.sum(), -r), s[on_leg_a] - leg])
        tangents[on_leg_a] = (0.0, 1.0)

        # bend: theta sweeps pi -> 0, so the arc passes over the top (+y)
        theta = math.pi * (1.0 - (s[on_arc] - leg) / arc)
        points[on_arc] = np.column_stack([r * np.cos(theta), r * np.sin(theta)])
        tangents[on_arc] = np.column_stack([np.sin(theta), -np.cos(theta)])

        # right leg: x = +r, y drops from 0 to -leg
        points[on_leg_b] = np.column_stack([
            np.full(on_leg_b.sum(), r), -(s[on_leg_b] - leg - arc)])
        tangents[on_leg_b] = (0.0, -1.0)

        # Rotating the tangent 90 deg counter-clockwise points outwards
        # everywhere along this path: (tx, ty) -> (-ty, tx).
        normals = np.column_stack([-tangents[:, 1], tangents[:, 0]])
        return points, normals, s

    def ridge_offset(self, s):
        """Extra outward displacement from the ridges at arc length ``s``, in mm.

        A raised-cosine ripple (always >= 0, so it only ever *adds* material),
        faded out over ``ridge_taper_mm`` at each leg tip so the tips are flat.
        """
        if self.ridge_height_mm <= 0:
            return np.zeros_like(s)
        ripple = 0.5 * (1.0 - np.cos(2.0 * math.pi * s / self.ridge_pitch_mm))
        if self.ridge_taper_mm > 0:
            total = self.path_length_mm
            window = (_smoothstep(s / self.ridge_taper_mm)
                      * _smoothstep((total - s) / self.ridge_taper_mm))
        else:
            window = 1.0
        return self.ridge_height_mm * ripple * window

    def walls(self):
        """Return the ``(inner, outer)`` wall polylines as ``(n, 2)`` arrays."""
        points, normals, s = self.centreline()
        half = self.thickness_mm / 2.0
        inner = points - half * normals
        outer = points + (half + self.ridge_offset(s))[:, None] * normals
        return inner, outer


# ===========================================================================
# GEOMETRY
# ===========================================================================
def build_geometry(cfg):
    """Sweep the cross-section along the path into raw ``(vertices, faces)``.

    Pure numpy, no trimesh — so the preview can draw the very same triangles
    that get exported.

    At every step ``i`` along the path the cross-section is the rectangle
    ``A(inner, z=0) -> B(outer, z=0) -> C(outer, z=w) -> D(inner, z=w)``.
    Joining ring ``i`` to ring ``i+1`` with four quads gives the tube walls,
    and the rectangles at the two ends cap it off, so the result is closed.
    """
    inner, outer = cfg.walls()
    n = len(inner)
    w = cfg.width_mm

    # 4 vertices per ring, in the order A, B, C, D.
    verts = np.empty((n * 4, 3))
    verts[0::4, :2], verts[0::4, 2] = inner, 0.0
    verts[1::4, :2], verts[1::4, 2] = outer, 0.0
    verts[2::4, :2], verts[2::4, 2] = outer, w
    verts[3::4, :2], verts[3::4, 2] = inner, w

    faces = []
    for i in range(n - 1):
        a, b = 4 * i, 4 * (i + 1)               # this ring, next ring
        for k in range(4):                       # the four sides of the tube
            k2 = (k + 1) % 4
            faces.append([a + k, a + k2, b + k2])
            faces.append([a + k, b + k2, b + k])

    last = 4 * (n - 1)
    faces.append([0, 2, 1])                      # cap on the first leg tip
    faces.append([0, 3, 2])
    faces.append([last + 0, last + 1, last + 2])  # cap on the second leg tip
    faces.append([last + 0, last + 2, last + 3])

    # Centre the U on the plate; the width sits from z = 0 upwards.
    verts[:, 0] -= 0.5 * (verts[:, 0].min() + verts[:, 0].max())
    verts[:, 1] -= 0.5 * (verts[:, 1].min() + verts[:, 1].max())
    return verts, np.array(faces, dtype=np.int64)


def build_mesh(cfg):
    """Build the swept solid and check it really is one watertight body."""
    import trimesh  # imported lazily: --preview must work without trimesh

    verts, faces = build_geometry(cfg)
    body = trimesh.Trimesh(vertices=verts, faces=faces, process=True)
    body.merge_vertices()
    body.remove_unreferenced_vertices()
    body.fix_normals()

    if not body.is_watertight:
        raise RuntimeError("Generated bracket is not watertight")
    if body.body_count != 1:
        raise RuntimeError(f"Expected one connected body, got {body.body_count}")
    if not body.is_winding_consistent:
        raise RuntimeError("Generated bracket has inconsistent face winding")
    if body.volume <= 0:
        raise RuntimeError("Generated bracket has non-positive volume")
    return body


# ===========================================================================
# OUTPUT MODE 1 — PREVIEW PNG
# ===========================================================================
def make_preview(cfg):
    """Write a two-panel PNG: the dimensioned side view and a 3D view."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    inner, outer = cfg.walls()
    section = np.vstack([outer, inner[::-1]])     # closed outline of the U

    fig = plt.figure(figsize=(13, 6.2))
    axs = fig.add_subplot(1, 2, 1)
    ax3 = fig.add_subplot(1, 2, 2, projection="3d")

    # --- side view, dimensioned -------------------------------------------
    axs.add_patch(Polygon(section, closed=True, facecolor="#5aa7d6",
                          edgecolor="#1b3b52", linewidth=1.4))
    r_i, r_o = cfg.inner_radius_mm, cfg.outer_radius_mm
    crown = r_o + cfg.ridge_height_mm        # top of the bend
    foot = -cfg.leg_length_mm                # the leg tips

    # inner diameter of the circular bend, measured across the arc centre
    axs.annotate("", xy=(-r_i, 0.0), xytext=(r_i, 0.0),
                 arrowprops=dict(arrowstyle="<->", color="#1b3b52"))
    axs.text(0, 1.2, f"{cfg.inner_diameter_mm:g} mm inner dia",
             ha="center", va="bottom", fontsize=10, color="#1b3b52")

    # leg length, from the end of the bend down to the tip
    x_dim = r_o + 7.0
    axs.annotate("", xy=(x_dim, foot), xytext=(x_dim, 0.0),
                 arrowprops=dict(arrowstyle="<->", color="black"))
    axs.text(x_dim + 1.4, foot / 2, f"{cfg.leg_length_mm:g} mm legs",
             va="center", ha="left", fontsize=10, rotation=90)

    # overall height, tip to crown
    x_tot = -r_o - 7.0
    axs.annotate("", xy=(x_tot, foot), xytext=(x_tot, crown),
                 arrowprops=dict(arrowstyle="<->", color="#888"))
    axs.text(x_tot - 1.4, (foot + crown) / 2, f"{cfg.height_mm:g} mm overall",
             va="center", ha="right", fontsize=9, color="#555", rotation=90)

    # wall thickness
    axs.annotate(f"{cfg.thickness_mm:g} mm wall",
                 xy=(-cfg.centre_radius_mm, foot * 0.75),
                 xytext=(-r_o - 12.0, foot * 0.95), ha="right", fontsize=10,
                 arrowprops=dict(arrowstyle="->", color="black"))
    if cfg.ridge_height_mm > 0:
        axs.annotate(f"ridges {cfg.ridge_height_mm:g} mm proud,\n"
                     f"{cfg.ridge_pitch_mm:g} mm apart",
                     xy=(r_o * 0.72, r_o * 0.72), xytext=(r_o + 12.0, crown),
                     ha="left", va="center", fontsize=10,
                     arrowprops=dict(arrowstyle="->", color="black"))
    axs.set_xlim(-r_o - 34.0, r_o + 34.0)
    axs.set_ylim(foot - 6.0, crown + 8.0)
    axs.set_aspect("equal")
    axs.set_title("side view — the U", fontsize=12)
    axs.axis("off")

    # --- 3D view -----------------------------------------------------------
    verts, faces = build_geometry(cfg)
    ax3.add_collection3d(Poly3DCollection(
        verts[faces], facecolors="#5aa7d6", edgecolors="#2d6f9e",
        linewidth=0.05, shade=True))
    lo, hi = verts.min(axis=0), verts.max(axis=0)
    pad = 1.0
    ax3.set_xlim(lo[0] - pad, hi[0] + pad)
    ax3.set_ylim(lo[1] - pad, hi[1] + pad)
    ax3.set_zlim(lo[2] - pad, hi[2] + pad)
    ax3.set_box_aspect(hi - lo + 2 * pad)     # true proportions, no squashing
    ax3.view_init(elev=24, azim=-56)
    ax3.set_axis_off()
    ax3.set_title(f"3D view — {cfg.width_mm:g} mm wide band "
                  f"(printed lying like this)", fontsize=12)

    fig.suptitle(f"U-BRACKET — {cfg.inner_diameter_mm:g} mm bend, "
                 f"{cfg.leg_length_mm:g} mm legs, {cfg.thickness_mm:g} mm wall",
                 fontsize=15, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    out = _out_path(cfg.out_dir, PREVIEW_SUBDIR, f"preview_u_bracket_{cfg.slug}.png")
    fig.savefig(out, facecolor="white", dpi=110)
    plt.close(fig)
    print(f"[preview] {cfg.span_mm:g}mm across x {cfg.height_mm:g}mm tall x "
          f"{cfg.width_mm:g}mm wide  slot={cfg.inner_diameter_mm:g}mm  "
          f"wall={cfg.thickness_mm:g}mm")
    print(f"[preview] saved -> {out}")
    return out


# ===========================================================================
# OUTPUT MODE 2 — STL
# ===========================================================================
def make_stl(cfg):
    body = build_mesh(cfg)
    out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"u_bracket_{cfg.slug}.stl")
    body.export(out)

    ex = body.extents
    print(f"[stl] size={ex[0]:.1f} x {ex[1]:.1f} x {ex[2]:.1f} mm  "
          f"slot={cfg.inner_diameter_mm:g}mm  wall={cfg.thickness_mm:g}mm  "
          f"verts={len(body.vertices)}  faces={len(body.faces)}  "
          f"{'watertight' if body.is_watertight else 'NOT watertight'}")
    print(f"[stl] material: {body.volume / 1000.0:.1f} cm³ solid "
          f"(≈ {body.volume / 1000.0 * PLA_DENSITY:.0f} g PLA at 100% infill)")
    print(f"[stl] saved -> {out}")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(args):
    return UBracketConfig(
        inner_diameter_mm=args.inner_diameter,
        leg_length_mm=args.leg_length,
        thickness_mm=args.thickness,
        width_mm=args.width,
        ridge_height_mm=args.ridge_height,
        ridge_pitch_mm=args.ridge_pitch,
        arc_segments=args.arc_segments,
    )


def main():
    d = UBracketConfig()
    p = argparse.ArgumentParser(
        description="Parametric U-bracket: circular bend, two straight legs, "
                    "ridged outer face")
    p.add_argument("--inner-diameter", type=float, default=d.inner_diameter_mm,
                   help="inner diameter of the bend / slot width, mm "
                        "(default: %(default)s)")
    p.add_argument("--leg-length", type=float, default=d.leg_length_mm,
                   help="length of each straight leg, mm (default: %(default)s)")
    p.add_argument("--thickness", type=float, default=d.thickness_mm,
                   help="wall thickness of the band, mm (default: %(default)s)")
    p.add_argument("--width", type=float, default=d.width_mm,
                   help="width of the band / print height, mm "
                        "(default: %(default)s)")
    p.add_argument("--ridge-height", type=float, default=d.ridge_height_mm,
                   help="depth of the outer ridges, mm; 0 for smooth "
                        "(default: %(default)s)")
    p.add_argument("--ridge-pitch", type=float, default=d.ridge_pitch_mm,
                   help="spacing between ridges, mm (default: %(default)s)")
    p.add_argument("--arc-segments", type=int, default=d.arc_segments,
                   help="facets around the bend (default: %(default)s)")
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
