#!/usr/bin/env python3
"""Generate a centred, multiline, two-colour 3D printable sign."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw, ImageFont

SKILL_DIR = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = SKILL_DIR.parent
sys.path.insert(0, str(LIBRARY_ROOT))
from mesh_utils import build_mask_prism, write_color_3mf  # noqa: E402

FONT_FILES = {
    400: SKILL_DIR / "assets" / "Unkempt-Regular.ttf",
    700: SKILL_DIR / "assets" / "Unkempt-Bold.ttf",
}


@dataclass(frozen=True)
class SignConfig:
    text: str
    output_dir: Path
    font_weight: int = 700
    letter_height_mm: float = 14.0
    line_spacing_mm: float = 3.0
    padding_x_mm: float = 7.0
    padding_y_mm: float = 6.0
    base_height_mm: float = 4.0
    text_height_mm: float = 1.5
    corner_radius_mm: float = 4.0
    base_bevel_mm: float = 0.4
    text_bevel_mm: float = 0.25
    keychain_hole: bool = False
    hole_corner: str = "top-left"
    hole_diameter_mm: float = 5.0
    hole_wall_mm: float = 2.0
    ppm: int = 5
    base_color: str = "#000000"
    text_color: str = "#FFFFFF"

    @property
    def lines(self) -> list[str]:
        normalized = self.text.replace("\\r\\n", "\n").replace("\\n", "\n")
        return [line.strip() for line in normalized.split("\n")]

    @property
    def total_height_mm(self) -> float:
        return self.base_height_mm + self.text_height_mm

    @property
    def stem(self) -> str:
        words = "_".join(line for line in self.lines if line)
        slug = re.sub(r"[^a-z0-9]+", "_", words.lower()).strip("_")
        suffix = "_keychain" if self.keychain_hole else ""
        return f"sign_{slug or 'text'}{suffix}"

    def validate(self) -> None:
        if not any(self.lines):
            raise ValueError("text must contain at least one visible character")
        if self.font_weight not in FONT_FILES:
            raise ValueError("font weight must be 400 or 700")
        positive = {
            "letter height": self.letter_height_mm,
            "base height": self.base_height_mm,
            "text height": self.text_height_mm,
            "padding x": self.padding_x_mm,
            "padding y": self.padding_y_mm,
            "corner radius": self.corner_radius_mm,
            "hole diameter": self.hole_diameter_mm,
            "hole wall": self.hole_wall_mm,
        }
        for label, value in positive.items():
            if value <= 0:
                raise ValueError(f"{label} must be greater than zero")
        if self.line_spacing_mm < 0 or self.base_bevel_mm < 0 or self.text_bevel_mm < 0:
            raise ValueError("spacing and bevels cannot be negative")
        if self.ppm < 3:
            raise ValueError("ppm must be at least 3")
        if self.base_bevel_mm >= self.base_height_mm:
            raise ValueError("base bevel must be smaller than base height")
        if self.text_bevel_mm >= self.text_height_mm:
            raise ValueError("text bevel must be smaller than text height")
        if self.hole_corner not in {
            "top-left", "top-right", "bottom-left", "bottom-right"
        }:
            raise ValueError("invalid hole corner")
        for value in (self.base_color, self.text_color):
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
                raise ValueError(f"invalid colour {value!r}; use #RRGGBB")


def _font_for_visual_height(path: Path, target_px: int) -> ImageFont.FreeTypeFont:
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    low, high = 4, max(12, target_px * 3)
    while low < high:
        mid = (low + high + 1) // 2
        font = ImageFont.truetype(str(path), mid)
        box = probe.textbbox((0, 0), "Hgj", font=font)
        if box[3] - box[1] <= target_px:
            low = mid
        else:
            high = mid - 1
    return ImageFont.truetype(str(path), low)


def _heal_diagonal_pinches(mask: np.ndarray) -> np.ndarray:
    """Fill the corners where two glyph pixels touch only diagonally.

    Such a corner extrudes into a pinch point: four wall quads meet on one
    vertical edge, so the prism is no longer edge-manifold and the watertight
    check fails. Filling one of the two empty pixels turns the touch into a
    proper edge; at 5 px/mm that is a 0.2 mm nub inside an already stair-stepped
    outline, which the slicer cannot resolve. Repeat until stable, because a
    fill can create a new diagonal touch next door.
    """
    healed = mask.copy()
    for _ in range(8):
        a = healed[:-1, :-1]
        b = healed[:-1, 1:]
        c = healed[1:, :-1]
        d = healed[1:, 1:]
        down_right = a & d & ~b & ~c
        down_left = b & c & ~a & ~d
        if not (down_right.any() or down_left.any()):
            break
        healed[:-1, 1:] |= down_right
        healed[:-1, :-1] |= down_left
    return healed


def build_layout(cfg: SignConfig) -> tuple[np.ndarray, float, float]:
    """Return a centred text mask and the matching base dimensions."""
    ppm = cfg.ppm
    font = _font_for_visual_height(
        FONT_FILES[cfg.font_weight], round(cfg.letter_height_mm * ppm)
    )
    probe = ImageDraw.Draw(Image.new("L", (8, 8)))
    ref = probe.textbbox((0, 0), "Hgj", font=font)
    row_h = ref[3] - ref[1]
    gap = round(cfg.line_spacing_mm * ppm)
    boxes, max_w = [], 0
    for line in cfg.lines:
        box = probe.textbbox((0, 0), line or " ", font=font)
        boxes.append(box)
        if line:
            max_w = max(max_w, box[2] - box[0])

    content_h = len(cfg.lines) * row_h + max(0, len(cfg.lines) - 1) * gap
    padding_x, padding_y = cfg.padding_x_mm, cfg.padding_y_mm
    if cfg.keychain_hole:
        clearance = 1.5
        padding_x = max(
            padding_x,
            cfg.corner_radius_mm + cfg.hole_wall_mm
            + cfg.hole_diameter_mm + clearance,
        )
        padding_y = max(
            padding_y, cfg.hole_wall_mm + cfg.hole_diameter_mm + clearance
        )
    px, py = round(padding_x * ppm), round(padding_y * ppm)
    width_px, height_px = max_w + 2 * px, content_h + 2 * py
    image = Image.new("L", (width_px, height_px), 0)
    draw = ImageDraw.Draw(image)
    y = py
    for line, box in zip(cfg.lines, boxes):
        if line:
            line_w, line_h = box[2] - box[0], box[3] - box[1]
            x = (width_px - line_w) / 2 - box[0]
            baseline_y = y + (row_h - line_h) / 2 - box[1]
            draw.text((round(x), round(baseline_y)), line, font=font, fill=255)
        y += row_h + gap
    mask = _heal_diagonal_pinches(np.asarray(image) >= 128)
    return mask, width_px / ppm, height_px / ppm


def _rounded_rectangle_points(
    width: float, height: float, radius: float, arc_segments: int = 12
) -> np.ndarray:
    radius = min(radius, width / 2, height / 2)
    arcs = (
        (width - radius, radius, -90.0, 0.0),
        (width - radius, height - radius, 0.0, 90.0),
        (radius, height - radius, 90.0, 180.0),
        (radius, radius, 180.0, 270.0),
    )
    points = []
    for cx, cy, start, stop in arcs:
        for angle in np.linspace(start, stop, arc_segments, endpoint=False):
            a = np.deg2rad(angle)
            points.append((cx + radius * np.cos(a), cy + radius * np.sin(a)))
    return np.asarray(points)


def _keychain_hole_center(
    cfg: SignConfig, width: float, height: float
) -> tuple[float, float]:
    edge = cfg.hole_diameter_mm / 2 + cfg.hole_wall_mm
    x = cfg.corner_radius_mm + edge
    y = height - edge
    if cfg.hole_corner.endswith("right"):
        x = width - x
    if cfg.hole_corner.startswith("bottom"):
        y = edge
    return x, y


def _radial_boundary(
    polygon: np.ndarray, center: tuple[float, float], angles: np.ndarray
) -> np.ndarray:
    """Intersect rays from an interior point with a convex polygon."""
    c = np.asarray(center, dtype=float)
    result = []
    for angle in angles:
        d = np.array([np.cos(angle), np.sin(angle)])
        best = np.inf
        for p, q in zip(polygon, np.roll(polygon, -1, axis=0)):
            s = q - p
            den = d[0] * s[1] - d[1] * s[0]
            if abs(den) < 1e-12:
                continue
            pc = p - c
            t = (pc[0] * s[1] - pc[1] * s[0]) / den
            u = (pc[0] * d[1] - pc[1] * d[0]) / den
            if t >= 0 and -1e-9 <= u <= 1 + 1e-9:
                best = min(best, t)
        if not np.isfinite(best):
            raise RuntimeError("could not place keychain hole inside base")
        result.append(c + best * d)
    return np.asarray(result)


def build_rounded_base(cfg: SignConfig, width: float, height: float) -> trimesh.Trimesh:
    """Build a rounded base with a top-only 45-degree bevel."""
    bevel = min(
        cfg.base_bevel_mm, cfg.corner_radius_mm * 0.8, width / 4, height / 4
    )
    outer = _rounded_rectangle_points(width, height, cfg.corner_radius_mm)
    inner = (
        _rounded_rectangle_points(
            width - 2 * bevel,
            height - 2 * bevel,
            max(0.01, cfg.corner_radius_mm - bevel),
        )
        + bevel
        if bevel > 0
        else outer.copy()
    )
    if cfg.keychain_hole:
        return _build_base_with_hole(cfg, width, height, outer, inner, bevel)
    n = len(outer)
    vertices = np.vstack(
        [
            np.column_stack([outer, np.zeros(n)]),
            np.column_stack([outer, np.full(n, cfg.base_height_mm - bevel)]),
            np.column_stack([inner, np.full(n, cfg.base_height_mm)]),
            [[width / 2, height / 2, 0.0]],
            [[width / 2, height / 2, cfg.base_height_mm]],
        ]
    )
    bottom_center, top_center = 3 * n, 3 * n + 1
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.extend(
            [
                (bottom_center, j, i),
                (i, j, n + j), (i, n + j, n + i),
                (n + i, n + j, 2 * n + j), (n + i, 2 * n + j, 2 * n + i),
                (top_center, 2 * n + i, 2 * n + j),
            ]
        )
    return trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)


def _build_base_with_hole(
    cfg: SignConfig,
    width: float,
    height: float,
    outer_polygon: np.ndarray,
    top_polygon: np.ndarray,
    bevel: float,
) -> trimesh.Trimesh:
    """Build a rounded plaque and keychain hole without mesh booleans."""
    count = 96
    angles = np.linspace(0, 2 * np.pi, count, endpoint=False)
    center = _keychain_hole_center(cfg, width, height)
    outer = _radial_boundary(outer_polygon, center, angles)
    top_outer = _radial_boundary(top_polygon, center, angles)
    directions = np.column_stack([np.cos(angles), np.sin(angles)])
    hole_radius = cfg.hole_diameter_mm / 2
    hole_bottom = np.asarray(center) + hole_radius * directions
    hole_top = np.asarray(center) + (hole_radius + bevel) * directions
    z_wall = cfg.base_height_mm - bevel
    n = count
    vertices = np.vstack(
        [
            np.column_stack([outer, np.zeros(n)]),
            np.column_stack([outer, np.full(n, z_wall)]),
            np.column_stack([top_outer, np.full(n, cfg.base_height_mm)]),
            np.column_stack([hole_bottom, np.zeros(n)]),
            np.column_stack([hole_bottom, np.full(n, z_wall)]),
            np.column_stack([hole_top, np.full(n, cfg.base_height_mm)]),
        ]
    )
    ob, ow, ot, hb, hw, ht = (0, n, 2 * n, 3 * n, 4 * n, 5 * n)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.extend(
            [
                # Bottom annulus, outer wall, outer top bevel.
                (hb + i, ob + j, ob + i), (hb + i, hb + j, ob + j),
                (ob + i, ob + j, ow + j), (ob + i, ow + j, ow + i),
                (ow + i, ow + j, ot + j), (ow + i, ot + j, ot + i),
                # Top annulus, hole wall, and chamfer around the hole rim.
                (ht + i, ot + i, ot + j), (ht + i, ot + j, ht + j),
                (hb + i, hw + j, hb + j), (hb + i, hw + i, hw + j),
                (hw + i, ht + j, hw + j), (hw + i, ht + i, ht + j),
            ]
        )
    return trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)


def build_meshes(cfg: SignConfig) -> tuple[trimesh.Trimesh, trimesh.Trimesh, float, float]:
    text_mask, width, height = build_layout(cfg)
    base = build_rounded_base(cfg, width, height)
    text = build_mask_prism(
        text_mask,
        cfg.base_height_mm - 0.02,
        cfg.total_height_mm,
        1.0 / cfg.ppm,
        bevel=(0.0, cfg.text_bevel_mm),
    )
    text.remove_unreferenced_vertices()
    return base, text, width, height


def _rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))


def write_preview(cfg: SignConfig, path: Path) -> None:
    text_mask, width, height = build_layout(cfg)
    base = Image.new("RGB", text_mask.shape[::-1], (238, 238, 238))
    base_draw = ImageDraw.Draw(base)
    base_draw.rounded_rectangle(
        (0, 0, base.width - 1, base.height - 1),
        radius=round(cfg.corner_radius_mm * cfg.ppm),
        fill=_rgb(cfg.base_color),
    )
    if cfg.keychain_hole:
        cx, cy = _keychain_hole_center(cfg, width, height)
        cx *= cfg.ppm
        cy = base.height - cy * cfg.ppm
        radius = cfg.hole_diameter_mm * cfg.ppm / 2
        base_draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=(238, 238, 238),
        )
    pixels = np.asarray(base).copy()
    pixels[text_mask] = _rgb(cfg.text_color)
    image = Image.fromarray(pixels).resize(
        (base.width * 3, base.height * 3), Image.Resampling.LANCZOS
    )
    canvas = Image.new("RGB", (image.width + 80, image.height + 120), "#EEEEF2")
    canvas.paste(image, (40, 40))
    ImageDraw.Draw(canvas).text(
        (40, image.height + 62),
        f"{width:.1f} x {height:.1f} x {cfg.total_height_mm:.1f} mm  |  "
        f"base {cfg.base_height_mm:.1f} + text {cfg.text_height_mm:.1f} mm",
        fill="#303038",
    )
    canvas.save(path)


def generate(cfg: SignConfig, preview: bool, threemf: bool, stl_parts: bool) -> list[Path]:
    cfg.validate()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    created = []
    if preview:
        path = cfg.output_dir / f"{cfg.stem}_preview.png"
        write_preview(cfg, path)
        created.append(path)

    if threemf or stl_parts:
        base, text, width, height = build_meshes(cfg)
        if not base.is_watertight or not text.is_watertight:
            raise RuntimeError("generated mesh is not watertight")
        if threemf:
            combo = trimesh.util.concatenate([base, text])
            materials = np.concatenate(
                [np.zeros(len(base.faces), dtype=int), np.ones(len(text.faces), dtype=int)]
            )
            path = cfg.output_dir / f"{cfg.stem}_multicolour.3mf"
            write_color_3mf(
                combo, materials, [cfg.base_color, cfg.text_color], str(path),
                names=["black_base", "white_text"], object_name=cfg.stem,
            )
            created.append(path)
        if stl_parts:
            base_path = cfg.output_dir / f"{cfg.stem}_black_base.stl"
            text_path = cfg.output_dir / f"{cfg.stem}_white_text.stl"
            base.export(base_path)
            text.export(text_path)
            created.extend([base_path, text_path])
        print(
            f"Size: {width:.1f} x {height:.1f} x {cfg.total_height_mm:.1f} mm; "
            f"base/text watertight: {base.is_watertight}/{text.is_watertight}"
        )
    for path in created:
        print(path.resolve())
    return created


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a centred multiline Unkempt sign as multicolour 3MF."
    )
    parser.add_argument("--text", required=True, help="Use real newlines or literal \\n sequences")
    parser.add_argument("--output-dir", type=Path, default=Path.cwd() / "sign_output")
    parser.add_argument("--font-weight", type=int, choices=(400, 700), default=700)
    parser.add_argument("--letter-height", type=float, default=14.0)
    parser.add_argument("--line-spacing", type=float, default=3.0)
    parser.add_argument("--padding-x", type=float, default=7.0)
    parser.add_argument("--padding-y", type=float, default=6.0)
    parser.add_argument("--base-height", type=float, default=4.0)
    parser.add_argument("--text-height", type=float, default=1.5)
    parser.add_argument("--corner-radius", type=float, default=4.0)
    parser.add_argument("--base-bevel", type=float, default=0.4)
    parser.add_argument("--text-bevel", type=float, default=0.25)
    parser.add_argument("--keychain-hole", action="store_true")
    parser.add_argument(
        "--hole-corner",
        choices=("top-left", "top-right", "bottom-left", "bottom-right"),
        default="top-left",
    )
    parser.add_argument("--hole-diameter", type=float, default=5.0)
    parser.add_argument("--hole-wall", type=float, default=2.0)
    parser.add_argument("--ppm", type=int, default=5, help="XY resolution in pixels/mm")
    parser.add_argument("--base-color", default="#000000")
    parser.add_argument("--text-color", default="#FFFFFF")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--3mf", dest="threemf", action="store_true")
    parser.add_argument("--stl-parts", action="store_true")
    args = parser.parse_args()
    if not (args.preview or args.threemf or args.stl_parts):
        args.preview = args.threemf = args.stl_parts = True
    return args


def main() -> None:
    args = parse_args()
    try:
        cfg = SignConfig(
            text=args.text, output_dir=args.output_dir, font_weight=args.font_weight,
            letter_height_mm=args.letter_height, line_spacing_mm=args.line_spacing,
            padding_x_mm=args.padding_x, padding_y_mm=args.padding_y,
            base_height_mm=args.base_height, text_height_mm=args.text_height,
            corner_radius_mm=args.corner_radius, base_bevel_mm=args.base_bevel,
            text_bevel_mm=args.text_bevel, keychain_hole=args.keychain_hole,
            hole_corner=args.hole_corner, hole_diameter_mm=args.hole_diameter,
            hole_wall_mm=args.hole_wall, ppm=args.ppm,
            base_color=args.base_color, text_color=args.text_color,
        )
        generate(cfg, args.preview, args.threemf, args.stl_parts)
    except (ValueError, RuntimeError) as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
