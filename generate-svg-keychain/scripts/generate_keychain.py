#!/usr/bin/env python3
"""Generate a beveled multicolour keychain from solid-color SVG artwork."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

try:
    import numpy as np
    import trimesh
    from PIL import Image, ImageColor, ImageDraw
    from scipy import ndimage
    from svgpathtools import svg2paths2
except ImportError as exc:
    raise SystemExit(
        "Missing dependency. Install numpy pillow scipy trimesh svgpathtools. "
        f"Original error: {exc}"
    ) from exc


SKILL_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from mesh_utils import build_mask_prism, write_color_3mf
except ImportError as exc:
    raise SystemExit(
        f"Could not import shared mesh_utils.py from {REPO_ROOT}: {exc}"
    ) from exc


INKSCAPE_LABEL = "{http://www.inkscape.org/namespaces/inkscape}label"
PAINT_KEYS = {"fill", "stroke", "stroke-width", "fill-rule", "display", "opacity"}
UNSUPPORTED_TAGS = {
    "image", "linearGradient", "radialGradient", "pattern", "mask",
    "clipPath", "filter", "text",
}
DRAWABLE_TAGS = {"path", "circle", "ellipse", "line", "polyline", "polygon", "rect"}


@dataclass
class Config:
    svg: Path
    output_dir: Path
    name: str
    max_art_size_mm: float = 55.0
    border_width_mm: float = 3.0
    base_height_mm: float = 3.0
    art_height_mm: float = 1.2
    bevel_mm: float = 0.3
    hole_diameter_mm: float = 5.0
    hole_wall_mm: float = 2.5
    hole_position: str = "top"
    base_color: str = "#FFFFFF"
    ppm: int = 5
    samples: int = 24
    fill_rule: str = "evenodd"
    keychain_hole: bool = True

    def validate(self) -> None:
        if not self.svg.is_file():
            raise ValueError(f"SVG does not exist: {self.svg}")
        positive = {
            "maximum artwork size": self.max_art_size_mm,
            "border width": self.border_width_mm,
            "base height": self.base_height_mm,
            "art height": self.art_height_mm,
            "hole diameter": self.hole_diameter_mm,
            "hole wall": self.hole_wall_mm,
        }
        for label, value in positive.items():
            if value <= 0:
                raise ValueError(f"{label} must be greater than zero")
        if self.bevel_mm < 0:
            raise ValueError("bevel cannot be negative")
        if self.bevel_mm * 2 >= min(self.base_height_mm, self.art_height_mm):
            raise ValueError("bevel must be less than half of both layer heights")
        if self.ppm < 3:
            raise ValueError("ppm must be at least 3")
        if self.samples < 8:
            raise ValueError("samples must be at least 8")
        self.base_color = normalize_color(self.base_color)


def normalize_color(value: str) -> str:
    value = value.strip()
    if value.lower() in {"none", "transparent"}:
        return "none"
    try:
        rgb = ImageColor.getrgb(value)
    except ValueError as exc:
        raise ValueError(f"invalid solid color {value!r}") from exc
    if len(rgb) == 4 and rgb[3] == 0:
        return "none"
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def style_dict(value: str | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for declaration in (value or "").split(";"):
        if ":" in declaration:
            key, val = declaration.split(":", 1)
            result[key.strip()] = val.strip()
    return result


def parse_simple_css(root: ET.Element) -> dict[str, dict[str, str]]:
    rules: dict[str, dict[str, str]] = {}
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] != "style" or not node.text:
            continue
        text = re.sub(r"/\*.*?\*/", "", node.text, flags=re.S)
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]+)\}", text):
            props = {k: v for k, v in style_dict(body).items() if k in PAINT_KEYS}
            for selector in selectors.split(","):
                selector = selector.strip()
                if re.fullmatch(r"[.#]?[A-Za-z_][\w.-]*", selector):
                    rules[selector] = {**rules.get(selector, {}), **props}
    return rules


def xml_style_index(
    svg: Path,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], list[str]]:
    root = ET.parse(svg).getroot()
    css = parse_simple_css(root)
    by_id: dict[str, dict[str, str]] = {}
    drawable_styles: list[dict[str, str]] = []
    unsupported: list[str] = []

    def visit(node: ET.Element, inherited: dict[str, str]) -> None:
        tag = node.tag.rsplit("}", 1)[-1]
        if tag in UNSUPPORTED_TAGS:
            unsupported.append(tag)
        current = dict(inherited)
        if tag in css:
            current.update(css[tag])
        for class_name in node.attrib.get("class", "").split():
            current.update(css.get(f".{class_name}", {}))
        elem_id = node.attrib.get("id", "")
        if elem_id:
            current.update(css.get(f"#{elem_id}", {}))
        current.update({k: v for k, v in node.attrib.items() if k in PAINT_KEYS})
        current.update({
            k: v for k, v in style_dict(node.attrib.get("style")).items()
            if k in PAINT_KEYS
        })
        if elem_id:
            current["id"] = elem_id
            current["label"] = node.attrib.get(INKSCAPE_LABEL, "")
            by_id[elem_id] = current
        if tag in DRAWABLE_TAGS:
            drawable = dict(current)
            drawable["id"] = elem_id
            drawable["label"] = node.attrib.get(INKSCAPE_LABEL, "")
            drawable_styles.append(drawable)
        for child in node:
            visit(child, current)

    visit(root, {"fill": "#000000", "stroke": "none"})
    return by_id, drawable_styles, sorted(set(unsupported))


def merged_style(
    attrs: dict[str, str],
    index: dict[str, dict[str, str]],
    fallback: dict[str, str] | None = None,
) -> dict[str, str]:
    elem_id = attrs.get("id", "")
    result = dict(fallback or {})
    result.update(index.get(elem_id, {}))
    result.update({k: v for k, v in attrs.items() if k in PAINT_KEYS or k == "id"})
    result.update(style_dict(attrs.get("style")))
    result.setdefault("fill", "#000000")
    result.setdefault("stroke", "none")
    result.setdefault("label", index.get(elem_id, {}).get("label", ""))
    return result


def parse_viewbox(svg_attrs: dict[str, str], paths) -> tuple[float, float, float, float]:
    value = svg_attrs.get("viewBox")
    if value:
        nums = [float(x) for x in re.split(r"[ ,]+", value.strip()) if x]
        if len(nums) == 4 and nums[2] > 0 and nums[3] > 0:
            return tuple(nums)  # type: ignore[return-value]
    width = re.sub(r"[^0-9eE+.-]", "", svg_attrs.get("width", ""))
    height = re.sub(r"[^0-9eE+.-]", "", svg_attrs.get("height", ""))
    if width and height and float(width) > 0 and float(height) > 0:
        return 0.0, 0.0, float(width), float(height)
    boxes = [path.bbox() for path in paths if len(path)]
    if not boxes:
        raise ValueError("SVG contains no drawable paths")
    xmin = min(box[0] for box in boxes)
    xmax = max(box[1] for box in boxes)
    ymin = min(box[2] for box in boxes)
    ymax = max(box[3] for box in boxes)
    return xmin, ymin, xmax - xmin, ymax - ymin


def parse_mapping(values: list[str]) -> list[tuple[str, str]]:
    mappings = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"invalid color mapping {value!r}; use selector=#RRGGBB")
        selector, color = value.rsplit("=", 1)
        mappings.append((selector.strip(), normalize_color(color)))
    return mappings


def mapped_color(source: str, elem_id: str, label: str,
                 mappings: list[tuple[str, str]]) -> str:
    source = normalize_color(source)
    result = source
    for selector, target in mappings:
        prefix, _, value = selector.partition(":")
        if prefix.lower() == "id" and value == elem_id:
            result = target
        elif prefix.lower() == "label" and value.casefold() == label.casefold():
            result = target
        elif prefix.lower() in {"fill", "stroke", "color"}:
            try:
                if normalize_color(value) == source:
                    result = target
            except ValueError:
                pass
        elif selector == elem_id or selector.casefold() == label.casefold():
            result = target
        else:
            try:
                if normalize_color(selector) == source:
                    result = target
            except ValueError:
                pass
    return result


def inspect_svg(svg: Path) -> None:
    paths, attrs, _ = svg2paths2(str(svg))
    index, drawable_styles, unsupported = xml_style_index(svg)
    print(f"Drawable paths: {len(paths)}")
    seen = set()
    for number, raw in enumerate(attrs, 1):
        fallback = drawable_styles[number - 1] if number <= len(drawable_styles) else None
        style = merged_style(raw, index, fallback)
        elem_id = style.get("id", "") or f"path-{number}"
        label = style.get("label", "")
        fill = style.get("fill", "#000000")
        stroke = style.get("stroke", "none")
        print(f"{number:>3}: id={elem_id!r} label={label!r} fill={fill!r} stroke={stroke!r}")
        for paint in (fill, stroke):
            try:
                color = normalize_color(paint)
            except ValueError:
                continue
            if color != "none":
                seen.add(color)
    print("Solid colors: " + (", ".join(sorted(seen)) or "none"))
    if unsupported:
        print("Warning: unsupported SVG features: " + ", ".join(unsupported))


def flattened_subpaths(path, samples: int) -> list[tuple[list[tuple[float, float]], bool]]:
    result = []
    for sub in path.continuous_subpaths():
        points: list[tuple[float, float]] = []
        for segment in sub:
            for i in range(max(2, samples)):
                point = segment.point(i / max(2, samples))
                points.append((float(point.real), float(point.imag)))
        if len(sub):
            point = sub[-1].point(1.0)
            points.append((float(point.real), float(point.imag)))
        if len(points) >= 2:
            first = complex(points[0][0], points[0][1])
            last = complex(points[-1][0], points[-1][1])
            result.append((points, abs(first - last) < 1e-6))
    return result


def render_svg(cfg: Config, mappings: list[tuple[str, str]]):
    paths, attrs, svg_attrs = svg2paths2(str(cfg.svg))
    if not paths:
        raise ValueError("SVG contains no drawable paths")
    index, drawable_styles, unsupported = xml_style_index(cfg.svg)
    vx, vy, vw, vh = parse_viewbox(svg_attrs, paths)
    scale = cfg.max_art_size_mm * cfg.ppm / max(vw, vh)
    pad = 2
    width = max(4, int(math.ceil(vw * scale)) + 2 * pad)
    height = max(4, int(math.ceil(vh * scale)) + 2 * pad)
    canvas = np.full((height, width), -1, dtype=np.int16)
    colors: list[str] = []
    names: dict[str, list[str]] = {}

    def material_index(color: str, name: str) -> int:
        if color not in colors:
            colors.append(color)
        names.setdefault(color, [])
        if name and name not in names[color]:
            names[color].append(name)
        return colors.index(color)

    def xy(point: tuple[float, float]) -> tuple[float, float]:
        return ((point[0] - vx) * scale + pad, (point[1] - vy) * scale + pad)

    for number, (path, raw) in enumerate(zip(paths, attrs), 1):
        fallback = drawable_styles[number - 1] if number <= len(drawable_styles) else None
        style = merged_style(raw, index, fallback)
        try:
            opacity = float(style.get("opacity", "1") or 1)
        except ValueError:
            opacity = 1.0
        if style.get("display", "").lower() == "none" or opacity <= 0:
            continue
        elem_id = style.get("id", "")
        label = style.get("label", "")
        display_name = label or elem_id or f"path_{number}"
        subpaths = flattened_subpaths(path, cfg.samples)

        try:
            source_fill = normalize_color(style.get("fill", "#000000"))
        except ValueError:
            source_fill = "none"
        if source_fill != "none":
            layer = np.zeros((height, width), dtype=bool)
            for points, closed in subpaths:
                if not closed or len(points) < 3:
                    continue
                polygon = [xy(point) for point in points]
                shape = Image.new("1", (width, height), 0)
                ImageDraw.Draw(shape).polygon(polygon, fill=1)
                shape_array = np.asarray(shape, dtype=bool)
                if cfg.fill_rule == "union":
                    layer |= shape_array
                else:
                    layer ^= shape_array
            if layer.any():
                target = mapped_color(source_fill, elem_id, label, mappings)
                canvas[layer] = material_index(target, display_name)

        try:
            source_stroke = normalize_color(style.get("stroke", "none"))
        except ValueError:
            source_stroke = "none"
        if source_stroke != "none":
            raw_width = re.sub(
                r"[^0-9eE+.-]", "", style.get("stroke-width", "1")
            ) or "1"
            stroke_px = max(1, round(float(raw_width) * scale))
            layer_image = Image.new("1", (width, height), 0)
            draw = ImageDraw.Draw(layer_image)
            for points, closed in subpaths:
                line = [xy(point) for point in points]
                if closed and line[0] != line[-1]:
                    line.append(line[0])
                draw.line(line, fill=1, width=stroke_px, joint="curve")
            layer = np.asarray(layer_image, dtype=bool)
            if layer.any():
                target = mapped_color(source_stroke, elem_id, label, mappings)
                canvas[layer] = material_index(target, f"{display_name}_stroke")

    if not (canvas >= 0).any():
        raise ValueError("SVG produced no solid filled or stroked artwork")
    return canvas, colors, names, unsupported


def disk(shape: tuple[int, int], center: tuple[float, float], radius: float) -> np.ndarray:
    yy, xx = np.ogrid[:shape[0], :shape[1]]
    return (xx - center[0]) ** 2 + (yy - center[1]) ** 2 <= radius ** 2


def compose_layout(cfg: Config, labels: np.ndarray):
    border = round(cfg.border_width_mm * cfg.ppm)
    outer_r = round((cfg.hole_diameter_mm / 2 + cfg.hole_wall_mm) * cfg.ppm)
    extra_top = 2 * outer_r + border + 4 if cfg.keychain_hole else border + 4
    side = border + outer_r + 4
    bottom = border + 4
    full = np.full(
        (labels.shape[0] + extra_top + bottom, labels.shape[1] + 2 * side),
        -1,
        dtype=np.int16,
    )
    y0, x0 = extra_top, side
    full[y0:y0 + labels.shape[0], x0:x0 + labels.shape[1]] = labels
    art = full >= 0
    base = ndimage.binary_dilation(art, iterations=border)
    base = ndimage.binary_fill_holes(base)
    hole_center = None
    if cfg.keychain_hole:
        rows, cols = np.where(base)
        top = rows.min()
        near = cols[rows <= top + max(2, cfg.ppm)]
        if cfg.hole_position == "top-left":
            cx = float(np.quantile(near, 0.15))
        elif cfg.hole_position == "top-right":
            cx = float(np.quantile(near, 0.85))
        else:
            # Pick a real top-edge column nearest the overall center. Averaging
            # two separated high points (such as bunny ears) can put the loop
            # in empty space between them and leave it detached.
            center_x = float(np.median(cols))
            cx = float(near[np.argmin(np.abs(near - center_x))])
        overlap = round(cfg.hole_wall_mm * cfg.ppm)
        cy = float(top - outer_r + overlap)
        outer = disk(base.shape, (cx, cy), outer_r)
        inner = disk(base.shape, (cx, cy), cfg.hole_diameter_mm * cfg.ppm / 2)
        base |= outer
        base &= ~inner
        hole_center = (cx, cy)
    components = ndimage.label(base)[1]
    if components != 1:
        raise ValueError(
            f"base has {components} disconnected islands; increase "
            "--border-width or join the SVG artwork"
        )
    rows, cols = np.where(base)
    r0, r1 = max(0, rows.min() - 2), min(base.shape[0], rows.max() + 3)
    c0, c1 = max(0, cols.min() - 2), min(base.shape[1], cols.max() + 3)
    full = full[r0:r1, c0:c1]
    base = base[r0:r1, c0:c1]
    if hole_center is not None:
        hole_center = (hole_center[0] - c0, hole_center[1] - r0)
    return full, base, hole_center


def crop_mesh(mask: np.ndarray, z0: float, z1: float, cfg: Config,
              bevel) -> trimesh.Trimesh:
    rows, cols = np.where(mask)
    if not len(rows):
        raise ValueError("cannot mesh an empty region")
    r0, r1 = max(0, rows.min() - 1), min(mask.shape[0], rows.max() + 2)
    c0, c1 = max(0, cols.min() - 1), min(mask.shape[1], cols.max() + 2)
    cropped = mask[r0:r1, c0:c1]
    step = 1.0 / cfg.ppm
    height, width = mask.shape
    x_world = c0 * step - width * step / 2
    y_world = (height - r1) * step - height * step / 2
    mesh = build_mask_prism(
        cropped, z0, z1, step, x0=x_world, y0=y_world, bevel=bevel
    )
    mesh.remove_unreferenced_vertices()
    return mesh


def regularize_component(mask: np.ndarray) -> np.ndarray:
    """Remove same-component diagonal pinches that share only one mesh vertex."""
    result = mask.copy()
    for _ in range(10000):
        a, b = result[:-1, :-1], result[:-1, 1:]
        c, d = result[1:, :-1], result[1:, 1:]
        ambiguous = np.argwhere((a & d & ~b & ~c) | (b & c & ~a & ~d))
        if not len(ambiguous):
            break
        row, col = ambiguous[0]
        if a[row, col] and d[row, col]:
            candidates = ((row, col), (row + 1, col + 1))
        else:
            candidates = ((row, col + 1), (row + 1, col))
        scores = []
        for rr, cc in candidates:
            r0, r1 = max(0, rr - 1), min(result.shape[0], rr + 2)
            c0, c1 = max(0, cc - 1), min(result.shape[1], cc + 2)
            scores.append(int(result[r0:r1, c0:c1].sum()))
        remove = candidates[int(scores[1] < scores[0])]
        result[remove] = False
    return result


def rgb_float(color: str) -> tuple[float, float, float]:
    color = normalize_color(color).lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def safe_name(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_")
    return value or "material"


def write_obj(meshes: list[trimesh.Trimesh], material_ids: list[int],
              colors: list[str], names: list[str], path: Path) -> Path:
    mtl_path = path.with_suffix(".mtl")
    material_names = [safe_name(name) for name in names]
    with mtl_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("# Solid-color materials generated for 3D printing\n")
        for name, color in zip(material_names, colors):
            r, g, b = rgb_float(color)
            handle.write(
                f"newmtl {name}\nKd {r:.6f} {g:.6f} {b:.6f}\n"
                "Ka 0 0 0\nKs 0 0 0\nd 1.0\nillum 1\n\n"
            )
    offset = 1
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"mtllib {mtl_path.name}\n")
        for part_number, (mesh, material_id) in enumerate(zip(meshes, material_ids)):
            part_name = f"part_{part_number + 1}_{material_names[material_id]}"
            handle.write(
                f"o {part_name}\ng {part_name}\n"
                f"usemtl {material_names[material_id]}\n"
            )
            for x, y, z in np.asarray(mesh.vertices):
                handle.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            for a, b, c in np.asarray(mesh.faces, dtype=int) + offset:
                handle.write(f"f {a} {b} {c}\n")
            offset += len(mesh.vertices)
    return mtl_path


def write_preview(labels: np.ndarray, base: np.ndarray, colors: list[str],
                  cfg: Config, path: Path) -> None:
    background = np.array((232, 234, 239), dtype=np.uint8)
    pixels = np.broadcast_to(background, (*base.shape, 3)).copy()
    pixels[base] = ImageColor.getrgb(cfg.base_color)[:3]
    for index, color in enumerate(colors):
        pixels[labels == index] = ImageColor.getrgb(color)[:3]
    image = Image.fromarray(pixels)
    scale = max(2, min(5, 900 // max(image.size)))
    image.resize(
        (image.width * scale, image.height * scale), Image.Resampling.NEAREST
    ).save(path)


def generate(cfg: Config, mappings: list[tuple[str, str]]) -> list[Path]:
    cfg.validate()
    cfg.output_dir.mkdir(parents=True, exist_ok=True)
    rendered, art_colors, source_names, unsupported = render_svg(cfg, mappings)
    labels, base_mask, hole_center = compose_layout(cfg, rendered)

    all_colors: list[str] = [cfg.base_color]
    for color in art_colors:
        if color not in all_colors:
            all_colors.append(color)
    material_names = ["base_white" if cfg.base_color == "#FFFFFF" else "base"]
    for color in all_colors[1:]:
        source_labels = source_names.get(color, [])
        material_names.append(
            source_labels[0] if source_labels else f"art_{color.lstrip('#')}"
        )

    meshes = [crop_mesh(
        base_mask, 0.0, cfg.base_height_mm, cfg, cfg.bevel_mm
    )]
    mesh_materials = [0]
    for source_index, color in enumerate(art_colors):
        region = labels == source_index
        if not region.any():
            continue
        # Four-connected components are meshed independently. If two islands
        # touch at only one pixel corner, sharing a vertex grid would otherwise
        # create a non-manifold point even though both solids are valid alone.
        components, component_count = ndimage.label(region)
        for component_id in range(1, component_count + 1):
            component = regularize_component(components == component_id)
            subcomponents, subcount = ndimage.label(component)
            for sub_id in range(1, subcount + 1):
                subcomponent = subcomponents == sub_id
                if not subcomponent.any():
                    continue
                meshes.append(crop_mesh(
                    subcomponent,
                    cfg.base_height_mm - min(0.04, cfg.art_height_mm / 10),
                    cfg.base_height_mm + cfg.art_height_mm,
                    cfg,
                    (0.0, cfg.bevel_mm),
                ))
                mesh_materials.append(all_colors.index(color))

    bad = [i + 1 for i, mesh in enumerate(meshes) if not mesh.is_watertight]
    if bad:
        raise RuntimeError(f"non-watertight generated parts: {bad}")

    stem = safe_name(cfg.name)
    obj_path = cfg.output_dir / f"{stem}_multicolour.obj"
    mtl_path = write_obj(meshes, mesh_materials, all_colors, material_names, obj_path)

    combined = trimesh.util.concatenate(meshes)
    face_material = np.concatenate([
        np.full(len(mesh.faces), material_id, dtype=int)
        for mesh, material_id in zip(meshes, mesh_materials)
    ])
    threemf_path = cfg.output_dir / f"{stem}_multicolour.3mf"
    write_color_3mf(
        combined,
        face_material,
        all_colors,
        str(threemf_path),
        names=material_names,
        object_name=stem,
    )

    preview_path = cfg.output_dir / f"{stem}_preview.png"
    write_preview(labels, base_mask, art_colors, cfg, preview_path)
    width_mm = base_mask.shape[1] / cfg.ppm
    depth_mm = base_mask.shape[0] / cfg.ppm
    manifest = {
        "source_svg": str(cfg.svg.resolve()),
        "dimensions_mm": {
            "width": round(width_mm, 3),
            "depth": round(depth_mm, 3),
            "height": round(cfg.base_height_mm + cfg.art_height_mm, 3),
        },
        "parameters": {
            **asdict(cfg),
            "svg": str(cfg.svg),
            "output_dir": str(cfg.output_dir),
        },
        "materials": [
            {"index": i + 1, "name": material_names[i], "color": color}
            for i, color in enumerate(all_colors)
        ],
        "parts": [
            {
                "name": f"part_{i + 1}",
                "material": material_names[mid],
                "watertight": bool(mesh.is_watertight),
            }
            for i, (mesh, mid) in enumerate(zip(meshes, mesh_materials))
        ],
        "hole_center_from_image_px": hole_center,
        "warnings": (
            ["Unsupported SVG features present: " + ", ".join(unsupported)]
            if unsupported else []
        ),
    }
    manifest_path = cfg.output_dir / f"{stem}_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        f"Size: {width_mm:.1f} x {depth_mm:.1f} x "
        f"{cfg.base_height_mm + cfg.art_height_mm:.1f} mm"
    )
    print(f"Parts: {len(meshes)}; all watertight: true")
    print("Materials: " + ", ".join(
        f"{name}={color}" for name, color in zip(material_names, all_colors)
    ))
    if unsupported:
        print("Warning: unsupported SVG features detected: " + ", ".join(unsupported))
    outputs = [obj_path, mtl_path, threemf_path, preview_path, manifest_path]
    for output in outputs:
        print(output.resolve())
    return outputs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("svg", type=Path)
    parser.add_argument(
        "--inspect", action="store_true",
        help="list SVG IDs, labels, fills, and strokes without generating",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path.cwd() / "keychain_output"
    )
    parser.add_argument("--name", help="output filename stem; defaults to SVG filename")
    parser.add_argument(
        "--color-map", action="append", default=[], metavar="SELECTOR=#RRGGBB"
    )
    parser.add_argument("--base-color", default="#FFFFFF")
    parser.add_argument("--max-art-size", type=float, default=55.0)
    parser.add_argument("--border-width", type=float, default=3.0)
    parser.add_argument("--base-height", type=float, default=3.0)
    parser.add_argument("--art-height", type=float, default=1.2)
    parser.add_argument("--bevel", type=float, default=0.3)
    parser.add_argument("--hole-diameter", type=float, default=5.0)
    parser.add_argument("--hole-wall", type=float, default=2.5)
    parser.add_argument(
        "--hole-position", choices=("top", "top-left", "top-right"), default="top"
    )
    parser.add_argument("--no-hole", action="store_true")
    parser.add_argument("--ppm", type=int, default=5, help="XY resolution in pixels/mm")
    parser.add_argument("--samples", type=int, default=24, help="curve samples per SVG segment")
    parser.add_argument(
        "--fill-rule", choices=("evenodd", "union"), default="evenodd"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.inspect:
            inspect_svg(args.svg)
            return
        cfg = Config(
            svg=args.svg,
            output_dir=args.output_dir,
            name=args.name or args.svg.stem,
            max_art_size_mm=args.max_art_size,
            border_width_mm=args.border_width,
            base_height_mm=args.base_height,
            art_height_mm=args.art_height,
            bevel_mm=args.bevel,
            hole_diameter_mm=args.hole_diameter,
            hole_wall_mm=args.hole_wall,
            hole_position=args.hole_position,
            base_color=args.base_color,
            ppm=args.ppm,
            samples=args.samples,
            fill_rule=args.fill_rule,
            keychain_hole=not args.no_hole,
        )
        generate(cfg, parse_mapping(args.color_map))
    except (ValueError, RuntimeError, ET.ParseError) as exc:
        raise SystemExit(f"error: {exc}") from exc


if __name__ == "__main__":
    main()
