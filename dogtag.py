#!/usr/bin/env python3
"""
dogtag.py
=========
Parametric two-colour **pet collar tag** generator — a rounded plaque with
*flush inlaid* text on **both** faces, a chamfered collar hole, and softened
edges all round.

The name-label tool (:file:`namelabel.py` / :file:`playdoh_label.py`) splits its
two colours **by height**: a border plate with the name raised on top. That is
perfect for a bag tag, but a collar tag has to read from *either* side and
should have nothing standing proud to snag or wear off. So this tool splits the
colours **in plan** instead:

* the plaque is one solid of the border colour, with the lettering **recessed**
  0.6 mm into the front *and* the back face, and
* the letters are separate solids of the text colour that fill those recesses
  exactly flush.

Print it as a two-filament 3MF and you get black text on a baby-blue tag with a
completely smooth surface. Print the ``_body`` STL on its own and the very same
geometry is a single-colour tag with **engraved** text — so a printer with no
AMS still gets a usable tag out of the same run.

Unlike the Play-Doh tools this one is **outline-based**, not raster-based: glyph
outlines come from the TTF via ``matplotlib.textpath`` and the plaque is lofted
from analytic rings, so the letters are smooth curves rather than stair-stepped
pixels and the meshes stay small (tens of thousands of triangles, not millions).
That costs one dependency the other tools avoid — ``manifold3d``, for the two
recess booleans.

USAGE
-----
    # both faces of one tag, all outputs:
    python dogtag.py --front "Kip" --back "0450 572 596"

    # long message, wrapped automatically to fit:
    python dogtag.py --front "I'm not good at meeting new people" \
                     --back "please call my dad\n0450 572 596" --stem kip_shy

DEPENDENCIES
------------
    pip install numpy pillow trimesh scipy shapely manifold3d matplotlib \
        pydantic --break-system-packages
"""

import argparse
import os
import re

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from mesh_utils import write_color_3mf

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(OUT_DIR, "assets", "fonts")
PREVIEW_SUBDIR = os.path.join("previews", "dogtags")
PRINT_SUBDIR = os.path.join("printable_files", "dogtags")

# Same bundled bubbly fonts as the name label, so a child's bag tag and the
# dog's collar tag can be printed in the matching face.
FONTS = {
    "Grandstander": "Grandstander.ttf",
    "Baloo 2": "Baloo2.ttf",
    "Bagel Fat One": "BagelFatOne.ttf",
    "Titan One": "TitanOne.ttf",
    "Chewy": "Chewy.ttf",
    "Lilita One": "LilitaOne.ttf",
    "Bubblegum Sans": "BubblegumSans.ttf",
}

# Reference string for the line grid: tall ascender + two descenders, so every
# row is the same height whether or not its own text has any.
ROW_REF = "Hgjp"

# Below roughly one and a bit 0.4 mm extrusions the inlay stops resolving as its
# own colour and smears into the body, so the layout is worth flagging.
MIN_STROKE_MM = 0.5


def _out_path(out_dir, subdir, filename):
    dest = os.path.join(out_dir, subdir)
    os.makedirs(dest, exist_ok=True)
    return os.path.join(dest, filename)


# ===========================================================================
# PARAMETER SCHEMA
# ===========================================================================
class DogTagConfig(BaseModel):
    """Validated parameters for one collar-tag generation run."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    front_text: str = Field(..., min_length=1)
    back_text: str = ""
    stem_override: str = ""
    font: str = Field("Grandstander")

    body_color: str = Field("#89CFF0")     # baby blue plaque
    text_color: str = Field("#1A1A1A")     # inlaid lettering

    width_mm: float = Field(40.0, gt=0)
    height_mm: float = Field(30.0, gt=0)
    thickness_mm: float = Field(3.0, gt=0)
    text_depth_mm: float = Field(0.6, gt=0)     # inlay depth on each face
    corner_radius_mm: float = Field(6.0, ge=0)
    bevel_mm: float = Field(0.5, ge=0)          # 45° chamfer, both faces + hole

    hole_d_mm: float = Field(4.5, gt=0)
    hole_wall_mm: float = Field(2.5, gt=0)

    letter_height_mm: float = Field(11.0, gt=0)  # cap on the row height
    line_gap_frac: float = Field(0.16, ge=0)     # of a row height
    pad_x_mm: float = Field(3.5, ge=0)
    pad_y_mm: float = Field(3.0, ge=0)
    hole_clear_mm: float = Field(1.2, ge=0)      # gap between hole and text
    max_lines: int = Field(6, ge=1, le=12)

    arc_segments: int = Field(24, ge=4)          # per rounded corner
    hole_segments: int = Field(72, ge=12)

    out_dir: str = OUT_DIR

    @model_validator(mode="after")
    def _check(self) -> "DogTagConfig":
        if self.font not in FONTS:
            raise ValueError(f"font must be one of {list(FONTS)}")
        for label, value in (("body_color", self.body_color),
                             ("text_color", self.text_color)):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError(f"{label} must be #RRGGBB, got {value!r}")
        if 2 * self.text_depth_mm >= self.thickness_mm:
            raise ValueError("thickness must exceed twice the text depth")
        if self.bevel_mm >= self.text_depth_mm:
            # The chamfer eats into the face the text is inlaid in; keeping it
            # shallower than the inlay stops the rim ramp reaching the letters.
            raise ValueError("bevel must be smaller than the text depth")
        if self.corner_radius_mm > min(self.width_mm, self.height_mm) / 2:
            raise ValueError("corner radius cannot exceed half the short side")
        if self.hole_r + self.hole_wall_mm > self.height_mm / 2:
            raise ValueError("collar hole does not fit inside the tag")
        return self

    # -- derived -----------------------------------------------------------
    @property
    def hole_r(self) -> float:
        return self.hole_d_mm / 2

    @property
    def hole_center(self) -> tuple[float, float]:
        """Top-centre, so the tag hangs level off the collar ring."""
        return self.width_mm / 2, self.height_mm - self.hole_r - self.hole_wall_mm

    @property
    def font_path(self) -> str:
        return os.path.join(FONT_DIR, FONTS[self.font])

    @property
    def text_box(self) -> tuple[float, float, float, float]:
        """(x0, y0, x1, y1) of the area the lettering may occupy, in mm."""
        _, hcy = self.hole_center
        return (self.pad_x_mm, self.pad_y_mm,
                self.width_mm - self.pad_x_mm,
                hcy - self.hole_r - self.hole_clear_mm)

    @property
    def stem(self) -> str:
        if self.stem_override:
            source = self.stem_override
        else:
            source = self.front_text
        slug = re.sub(r"[^a-z0-9]+", "_", source.lower()).strip("_")[:40].strip("_")
        return f"dogtag_{slug or 'tag'}"


# ===========================================================================
# TEXT — glyph outlines straight from the TTF
# ===========================================================================
def _text_polygon(text, font_path, size, origin=(0.0, 0.0)):
    """Return the filled shapely geometry of ``text`` at ``size``.

    ``TextPath`` hands back the glyph contours as a flat list of closed rings
    with no nesting information: an "o" is two rings and nothing says which is
    the counter. Symmetric-difference across the rings *is* the even-odd fill
    rule TrueType uses, so it resolves counters into holes without us having to
    work out containment ourselves.
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    path = TextPath(origin, text, size=size,
                    prop=FontProperties(fname=font_path))
    rings = [r for r in path.to_polygons(closed_only=True) if len(r) >= 3]
    if not rings:
        return unary_union([])
    filled = Polygon(rings[0]).buffer(0)
    for ring in rings[1:]:
        filled = filled.symmetric_difference(Polygon(ring).buffer(0))
    return filled


def _bounds(text, font_path, size):
    geom = _text_polygon(text, font_path, size)
    return (0.0, 0.0, 0.0, 0.0) if geom.is_empty else geom.bounds


def _wrap(words, n_lines, width_of):
    """Split ``words`` into exactly ``n_lines`` lines, narrowest widest line.

    A greedy fill packs the first line full and leaves a stub at the end, which
    then dictates how small the whole block has to shrink. This is the usual
    O(m^2 n) balancing DP instead: ``best[i][k]`` is the narrowest achievable
    widest line when the first ``i`` words are set in ``k`` lines.
    """
    m = len(words)
    if n_lines > m:
        return None
    inf = float("inf")
    best = [[inf] * (n_lines + 1) for _ in range(m + 1)]
    split = [[0] * (n_lines + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    for i in range(1, m + 1):
        for k in range(1, n_lines + 1):
            for j in range(k - 1, i):
                if best[j][k - 1] == inf:
                    continue
                cand = max(best[j][k - 1], width_of(" ".join(words[j:i])))
                if cand < best[i][k]:
                    best[i][k] = cand
                    split[i][k] = j
    if best[m][n_lines] == inf:
        return None
    lines, i = [], m
    for k in range(n_lines, 0, -1):
        j = split[i][k]
        lines.append(" ".join(words[j:i]))
        i = j
    return lines[::-1]


def layout_face(cfg, text):
    """Lay one face out: pick the line break-up and the largest size that fits.

    Returns ``(lines, size, geometry)`` where ``geometry`` is the shapely fill
    of the whole block, already positioned in tag coordinates (mm).
    """
    from shapely.affinity import translate
    from shapely.ops import unary_union

    fp = cfg.font_path
    x0, y0, x1, y1 = cfg.text_box
    box_w, box_h = x1 - x0, y1 - y0
    if box_w <= 0 or box_h <= 0:
        raise ValueError("no room left for text; reduce padding or hole size")

    _, ry0, _, ry1 = _bounds(ROW_REF, fp, 1.0)
    row_h, ascent = ry1 - ry0, ry1
    gap = cfg.line_gap_frac * row_h

    explicit = [ln.strip() for ln in text.replace("\\n", "\n").split("\n")]
    explicit = [ln for ln in explicit if ln]

    cache = {}

    def width_of(line):
        if line not in cache:
            b = _bounds(line, fp, 1.0)
            cache[line] = b[2] - b[0]
        return cache[line]

    def size_for(lines):
        block_h = len(lines) * row_h + (len(lines) - 1) * gap
        widest = max(width_of(ln) for ln in lines)
        if widest <= 0 or block_h <= 0:
            return 0.0
        return min(box_w / widest, box_h / block_h,
                   cfg.letter_height_mm / row_h)

    if len(explicit) > 1:
        candidates = [explicit]
    else:
        words = explicit[0].split()
        candidates = [c for c in
                      (_wrap(words, n, width_of)
                       for n in range(1, min(cfg.max_lines, len(words)) + 1))
                      if c]
    lines = max(candidates, key=size_for)
    size = size_for(lines)
    if size <= 0:
        raise ValueError(f"could not fit {text!r} on the tag")

    block_h = (len(lines) * row_h + (len(lines) - 1) * gap) * size
    top = (y0 + y1) / 2 + block_h / 2
    parts = []
    for i, line in enumerate(lines):
        baseline = top - i * (row_h + gap) * size - ascent * size
        geom = _text_polygon(line, fp, size)
        bx0, _, bx1, _ = geom.bounds
        parts.append(translate(geom, (x0 + x1) / 2 - (bx0 + bx1) / 2, baseline))
    block = unary_union(parts)

    # Optical centring: the uniform row grid keeps the baselines even, but a
    # block with no descender on its last line then sits high in the box.
    _, by0, _, by1 = block.bounds
    block = translate(block, 0.0, (y0 + y1) / 2 - (by0 + by1) / 2)
    return lines, size * row_h, block


# ===========================================================================
# GEOMETRY — analytic plaque, boolean recesses
# ===========================================================================
def _rounded_rect_ring(w, h, r, seg):
    """CCW ring of a rounded rectangle with its lower-left corner at origin."""
    r = max(min(r, w / 2, h / 2), 0.0)
    centres = ((w - r, r, -90.0), (w - r, h - r, 0.0),
               (r, h - r, 90.0), (r, r, 180.0))
    pts = []
    for cx, cy, start in centres:
        for a in np.linspace(np.deg2rad(start), np.deg2rad(start + 90),
                             seg, endpoint=False):
            pts.append((cx + r * np.cos(a), cy + r * np.sin(a)))
    return np.asarray(pts)


def _circle_ring(cx, cy, r, seg):
    a = np.linspace(0.0, 2 * np.pi, seg, endpoint=False)
    return np.column_stack([cx + r * np.cos(a), cy + r * np.sin(a)])


def build_plaque(cfg):
    """Loft the chamfered plaque: a rounded plate with a chamfered collar hole.

    Four levels — inset bottom, full, full, inset top — give a 45° chamfer on
    both faces of the rim *and* around both mouths of the hole, so no edge on
    the finished tag is a sharp arris. Every level is generated analytically at
    the same vertex count, so consecutive rings correspond one-to-one and the
    walls close into a watertight solid without a single boolean.
    """
    import trimesh
    from shapely.geometry import Polygon

    b = min(cfg.bevel_mm, cfg.corner_radius_mm * 0.8,
            cfg.thickness_mm / 2 - 1e-3)
    t = cfg.thickness_mm
    hcx, hcy = cfg.hole_center
    levels = ((b, 0.0), (0.0, b), (0.0, t - b), (b, t)) if b > 0 else \
             ((0.0, 0.0), (0.0, t))

    outer, inner = [], []
    for inset, z in levels:
        outer.append(_rounded_rect_ring(cfg.width_mm - 2 * inset,
                                        cfg.height_mm - 2 * inset,
                                        cfg.corner_radius_mm - inset,
                                        cfg.arc_segments) + inset)
        inner.append(_circle_ring(hcx, hcy, cfg.hole_r + inset,
                                  cfg.hole_segments))

    no, ni = len(outer[0]), len(inner[0])
    verts, faces = [], []
    for ring_o, ring_i, (_, z) in zip(outer, inner, levels):
        verts.append(np.column_stack([ring_o, np.full(no, z)]))
        verts.append(np.column_stack([ring_i, np.full(ni, z)]))
    verts = np.vstack(verts)
    stride = no + ni

    def o(level, i):
        return level * stride + i % no

    def h(level, i):
        return level * stride + no + i % ni

    for level in range(len(levels) - 1):
        for i in range(no):                       # outer wall, normals outward
            a, bb = o(level, i), o(level, i + 1)
            c, d = o(level + 1, i + 1), o(level + 1, i)
            faces += [(a, bb, c), (a, c, d)]
        for i in range(ni):                       # hole wall, normals inward
            a, bb = h(level, i), h(level, i + 1)
            c, d = h(level + 1, i + 1), h(level + 1, i)
            faces += [(a, c, bb), (a, d, c)]

    # Caps are the annulus between the outer and hole rings of the end levels.
    # Earcut triangulates using exactly the ring vertices we hand it, so the cap
    # shares its boundary with the walls and the solid closes.
    for level, flip in ((0, True), (len(levels) - 1, False)):
        poly = Polygon(outer[level], [inner[level]])
        cap_v, cap_f = trimesh.creation.triangulate_polygon(poly, engine="earcut")
        index = _match_ring_indices(cap_v, verts[level * stride:level * stride + stride])
        for tri in cap_f:
            a, bb, c = (index[tri[0]] + level * stride,
                        index[tri[1]] + level * stride,
                        index[tri[2]] + level * stride)
            faces.append((a, c, bb) if flip else (a, bb, c))

    mesh = trimesh.Trimesh(vertices=verts, faces=np.asarray(faces), process=False)
    if not mesh.is_watertight:
        raise RuntimeError("plaque loft did not close; check arc/hole segments")
    return mesh


def _match_ring_indices(cap_v, level_v):
    """Map earcut's cap vertices back onto the loft's ring vertices."""
    from scipy.spatial import cKDTree
    tree = cKDTree(level_v[:, :2])
    dist, idx = tree.query(np.asarray(cap_v)[:, :2])
    if dist.max() > 1e-6:
        raise RuntimeError("cap triangulation introduced new vertices")
    return idx


def _extrude(geom, z0, z1):
    import trimesh
    from shapely.geometry import MultiPolygon, Polygon
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    meshes = []
    for poly in polys:
        if not isinstance(poly, Polygon) or poly.is_empty:
            continue
        m = trimesh.creation.extrude_polygon(poly, height=z1 - z0, engine="earcut")
        m.apply_translation((0.0, 0.0, z0))
        meshes.append(m)
    return meshes


def build_meshes(cfg):
    """Return ``(body, text, info)`` — the blue plaque and the black inlay."""
    import trimesh
    from shapely.affinity import scale as sscale

    t, d = cfg.thickness_mm, cfg.text_depth_mm
    front_lines, front_size, front_geom = layout_face(cfg, cfg.front_text)
    info = {"front": (front_lines, front_size), "back": None}

    fills = _extrude(front_geom, t - d, t)
    # The cut is run past the face it opens onto: a boolean whose operands share
    # a face plane is the classic way to get a sliver or a missing facet, and
    # 0.5 mm of overshoot costs nothing because that volume is outside the tag.
    cuts = _extrude(front_geom, t - d, t + 0.5)

    if cfg.back_text:
        back_lines, back_size, back_geom = layout_face(cfg, cfg.back_text)
        info["back"] = (back_lines, back_size)
        # Mirror about the tag's vertical centre line so the back reads the
        # right way round once the tag is flipped over on the collar.
        mirrored = sscale(back_geom, xfact=-1.0, yfact=1.0,
                          origin=(cfg.width_mm / 2, 0))
        fills += _extrude(mirrored, 0.0, d)
        cuts += _extrude(mirrored, -0.5, d)
        info["back_geom"] = back_geom
    info["front_geom"] = front_geom
    info["stroke"] = {face: _mean_stroke(info[f"{face}_geom"])
                      for face in ("front", "back") if f"{face}_geom" in info}

    plaque = build_plaque(cfg)
    body = trimesh.boolean.difference([plaque] + cuts, engine="manifold")
    text = trimesh.util.concatenate(fills)
    return body, text, info


def _mean_stroke(geom):
    """Mean stroke width of a text block, mm.

    For a long thin shape the perimeter is about twice the centreline length,
    so ``2 * area / perimeter`` is a good estimate of how wide the strokes are —
    which is what decides whether the slicer can lay the inlay down as its own
    colour rather than smearing it into the body.
    """
    return 0.0 if geom.is_empty else 2 * geom.area / geom.length


def combine(body, text):
    """Stack the two parts into one mesh plus a per-face material index."""
    import trimesh
    verts = np.vstack([body.vertices, text.vertices])
    faces = np.vstack([body.faces, text.faces + len(body.vertices)])
    combo = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    face_mat = np.concatenate([np.zeros(len(body.faces), int),
                               np.ones(len(text.faces), int)])
    return combo, face_mat


# ===========================================================================
# OUTPUTS
# ===========================================================================
def make_preview(cfg, info):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle, PathPatch
    from matplotlib.path import Path
    from shapely.geometry import MultiPolygon, Point, Polygon

    def patch(geom, **kw):
        polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
        verts, codes = [], []
        for poly in polys:
            for ring in [poly.exterior, *poly.interiors]:
                pts = np.asarray(ring.coords)
                verts.extend(pts)
                codes.extend([Path.MOVETO] + [Path.LINETO] * (len(pts) - 1))
        return PathPatch(Path(np.asarray(verts), codes), **kw)

    plate = Polygon(_rounded_rect_ring(cfg.width_mm, cfg.height_mm,
                                       cfg.corner_radius_mm, cfg.arc_segments))
    plate = plate.difference(Point(*cfg.hole_center).buffer(cfg.hole_r,
                                                            quad_segs=32))

    fig, axes = plt.subplots(1, 3, figsize=(12, 4.6),
                             gridspec_kw={"width_ratios": [1, 1, 1.15]})
    faces = (("FRONT", info.get("front_geom"), info["front"]),
             ("BACK  (as seen when flipped)", info.get("back_geom"),
              info["back"]))
    for ax, (title, geom, meta) in zip(axes, faces):
        ax.add_patch(patch(plate, facecolor=cfg.body_color, edgecolor="0.55",
                           linewidth=1.0))
        if geom is not None and not geom.is_empty:
            ax.add_patch(patch(geom, facecolor=cfg.text_color, edgecolor="none"))
        ax.add_patch(Circle(cfg.hole_center, cfg.hole_r, facecolor="white",
                            edgecolor="0.55", linewidth=1.0))
        ax.set_xlim(-2, cfg.width_mm + 2)
        ax.set_ylim(-2, cfg.height_mm + 2)
        ax.set_aspect("equal"); ax.axis("off")
        sub = "" if meta is None else f"\n{len(meta[0])} line(s), {meta[1]:.1f} mm tall"
        ax.set_title(title + sub, fontsize=10)

    ax = axes[2]
    t, d = cfg.thickness_mm, cfg.text_depth_mm
    ax.add_patch(plt.Rectangle((0, 0), cfg.width_mm, t,
                               facecolor=cfg.body_color, edgecolor="0.55"))
    for z0 in (0.0, t - d):
        ax.add_patch(plt.Rectangle((8, z0), 10, d, facecolor=cfg.text_color,
                                   edgecolor="none"))
    ax.annotate(f"{t:.1f} mm", (cfg.width_mm + 1.5, t / 2), fontsize=9,
                color="0.3", va="center")
    ax.annotate(f"inlay {d:.1f} mm each face", (8, t + 0.8), fontsize=9,
                color="0.3")
    ax.set_xlim(-3, cfg.width_mm + 12)
    ax.set_ylim(-4, t + 5)
    ax.set_aspect("equal"); ax.axis("off")
    ax.set_title("side profile — text inlaid flush, both faces", fontsize=10)

    fig.suptitle(f"{cfg.width_mm:g} x {cfg.height_mm:g} x {t:g} mm collar tag "
                 f"- {cfg.font}", fontsize=12)
    fig.tight_layout()
    out = _out_path(cfg.out_dir, PREVIEW_SUBDIR, f"{cfg.stem}_preview.png")
    fig.savefig(out, dpi=150, facecolor="white")
    plt.close(fig)
    print(f"[preview] saved -> {out}")
    return out


def make_stl(cfg, body, text):
    combo, _ = combine(body, text)
    paths = []
    for mesh, suffix in ((combo, ""), (body, "_body"), (text, "_text")):
        out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"{cfg.stem}{suffix}.stl")
        mesh.export(out)
        paths.append(out)
        print(f"[stl] {os.path.basename(out)}  faces={len(mesh.faces)}  "
              f"{'watertight' if mesh.is_watertight else 'open'}")
    print("[stl] single colour: print the _body STL alone for an engraved tag.")
    return paths


def make_3mf(cfg, body, text):
    combo, face_mat = combine(body, text)
    out = _out_path(cfg.out_dir, PRINT_SUBDIR, f"{cfg.stem}.3mf")
    write_color_3mf(combo, face_mat, [cfg.body_color, cfg.text_color], out,
                    names=["body", "text"], object_name=cfg.stem)
    print(f"[3mf] {os.path.basename(out)}  2 coloured parts (body, text)  "
          f"{os.path.getsize(out) / 1e6:.1f} MB")
    print("[3mf] Bambu Studio: one object, body on extruder 1, text on 2.")
    return out


# ===========================================================================
# CLI
# ===========================================================================
def config_from_args(a):
    return DogTagConfig(
        front_text=a.front, back_text=a.back, stem_override=a.stem,
        font=a.font, body_color=a.body_color, text_color=a.text_color,
        width_mm=a.width, height_mm=a.height, thickness_mm=a.thickness,
        text_depth_mm=a.text_depth, corner_radius_mm=a.corner_radius,
        bevel_mm=a.bevel, hole_d_mm=a.hole_d, hole_wall_mm=a.hole_wall,
        letter_height_mm=a.letter_height, line_gap_frac=a.line_gap,
        pad_x_mm=a.pad_x, pad_y_mm=a.pad_y, max_lines=a.max_lines)


def main():
    d = DogTagConfig(front_text="Kip")
    p = argparse.ArgumentParser(
        description="Two-colour pet collar tag with flush inlaid text on both "
                    "faces")
    p.add_argument("--front", required=True, help="text for the front face")
    p.add_argument("--back", default="", help="text for the back face")
    p.add_argument("--stem", default="", help="output filename stem override")
    p.add_argument("--font", default=d.font, choices=list(FONTS))
    p.add_argument("--body-color", dest="body_color", default=d.body_color)
    p.add_argument("--text-color", dest="text_color", default=d.text_color)
    p.add_argument("--width", type=float, default=d.width_mm)
    p.add_argument("--height", type=float, default=d.height_mm)
    p.add_argument("--thickness", type=float, default=d.thickness_mm)
    p.add_argument("--text-depth", type=float, default=d.text_depth_mm)
    p.add_argument("--corner-radius", type=float, default=d.corner_radius_mm)
    p.add_argument("--bevel", type=float, default=d.bevel_mm,
                   help="45° chamfer on both faces of the rim and the hole, mm")
    p.add_argument("--hole-d", type=float, default=d.hole_d_mm)
    p.add_argument("--hole-wall", type=float, default=d.hole_wall_mm)
    p.add_argument("--letter-height", type=float, default=d.letter_height_mm,
                   help="upper limit on row height, mm (text shrinks to fit)")
    p.add_argument("--line-gap", type=float, default=d.line_gap_frac)
    p.add_argument("--pad-x", type=float, default=d.pad_x_mm)
    p.add_argument("--pad-y", type=float, default=d.pad_y_mm)
    p.add_argument("--max-lines", type=int, default=d.max_lines)
    p.add_argument("--preview", action="store_true")
    p.add_argument("--stl", action="store_true")
    p.add_argument("--3mf", dest="mf3", action="store_true")
    a = p.parse_args()

    try:
        cfg = config_from_args(a)
    except ValidationError as exc:
        raise SystemExit(f"bad parameters:\n{exc}")

    want_all = not (a.preview or a.stl or a.mf3)
    body, text, info = build_meshes(cfg)
    for face in ("front", "back"):
        if info[face]:
            lines, size = info[face]
            stroke = info["stroke"].get(face, 0.0)
            print(f"[layout] {face}: {lines}  row height {size:.1f} mm  "
                  f"mean stroke {stroke:.2f} mm")
            if stroke < MIN_STROKE_MM:
                print(f"[warn] {face} strokes are under {MIN_STROKE_MM} mm — "
                      "too thin to print as a separate colour. Shorten the "
                      "text, move some of it to the other face, or grow the "
                      "tag.")
    if not body.is_watertight:
        print("[warn] body mesh is not watertight")

    if a.preview or want_all:
        make_preview(cfg, info)
    if a.stl or want_all:
        make_stl(cfg, body, text)
    if a.mf3 or want_all:
        make_3mf(cfg, body, text)


if __name__ == "__main__":
    main()
