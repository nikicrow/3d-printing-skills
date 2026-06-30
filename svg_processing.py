#!/usr/bin/env python3
"""
svg_processing.py
=================
Generic, project-agnostic helpers for turning vector art and text into the
raster masks that the 3D-printing tools in this repo consume.

These functions intentionally know nothing about Play-Doh rollers, themes or
any particular product. They are the reusable "front end" shared by every
parametric STL generator here:

  * ``rasterize_svg`` — pure-Python SVG → 1-bit silhouette mask (no native
    cairo required), used to convert open-licensed icon SVGs into stamps.
  * ``load_font``     — best-effort lookup of a chunky/rounded TrueType font,
    used to render embossed text.

Keeping them in one place means a new generator (cookie cutters, stamps,
stencils, ...) can ``from svg_processing import rasterize_svg, load_font`` and
get identical, print-tuned rasterization for free.

DEPENDENCIES
------------
    pip install pillow svgpathtools --break-system-packages
"""

from PIL import Image, ImageChops, ImageDraw, ImageFont

# Preferred chunky / rounded fonts to try, in order. Callers may pass their own
# list to :func:`load_font`; this is the sensible cross-platform default.
DEFAULT_FONT_CANDIDATES = [
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


def rasterize_svg(svg_file, target_px, mode="evenodd",
                  margin=0.06, supersample=3, samples=28):
    """Rasterize an SVG file to a crisp 1-bit silhouette mask.

    ``svgpathtools`` parses each ``<path>`` (and basic shapes) into segments.
    Every continuous sub-path is flattened to a polygon and the sub-paths are
    composited according to ``mode``:

    * ``"evenodd"`` — XOR of sub-path fills, so interior holes appear as gaps
      (best for single-colour line/silhouette icons).
    * ``"union"`` — OR of sub-path fills, flattening everything to one solid
      silhouette (best for multicolour emoji art such as the Noto dinosaurs).

    The shape is rendered on a supersampled canvas and then downscaled with
    anti-aliasing and re-thresholded, giving clean edges.

    Parameters
    ----------
    svg_file : str or path-like
        Path to the source ``.svg`` file. The file's ``viewBox`` (or, failing
        that, its ``width``/``height``) is used to scale the art into the
        target square.
    target_px : int
        Side length, in pixels, of the returned square mask.
    mode : {'evenodd', 'union'}, optional
        Sub-path compositing rule (see above). Defaults to ``'evenodd'``.
    margin : float, optional
        Fractional empty border kept around the art, as a fraction of
        ``target_px`` per side. Defaults to ``0.06``.
    supersample : int, optional
        Integer oversampling factor used while drawing, before the
        anti-aliased downscale. Higher is smoother but slower. Defaults to
        ``3``.
    samples : int, optional
        Number of straight-line samples used to flatten each curved path
        segment into polygon points. Defaults to ``28``.

    Returns
    -------
    PIL.Image.Image
        A single-channel (mode ``"L"``) image of size
        ``(target_px, target_px)`` whose pixels are ``255`` on the silhouette
        and ``0`` elsewhere.
    """
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


def load_font(px_size, candidates=None):
    """Load the first available chunky/rounded TrueType font.

    Each name in ``candidates`` is tried in order via
    :func:`PIL.ImageFont.truetype`; the first that loads wins. If none are
    available, PIL's built-in bitmap font is returned as a last resort.

    Parameters
    ----------
    px_size : float
        Desired font size in pixels (coerced to ``int`` for ``truetype``).
    candidates : list of str, optional
        Ordered font names / filenames to try. Defaults to
        :data:`DEFAULT_FONT_CANDIDATES`.

    Returns
    -------
    font : PIL.ImageFont.FreeTypeFont or PIL.ImageFont.ImageFont
        The loaded font object.
    name : str
        The candidate that loaded, or ``"PIL-default"`` if the fallback bitmap
        font was used.
    """
    if candidates is None:
        candidates = DEFAULT_FONT_CANDIDATES
    for cand in candidates:
        try:
            return ImageFont.truetype(cand, int(px_size)), cand
        except (OSError, IOError):
            continue
    return ImageFont.load_default(), "PIL-default"
