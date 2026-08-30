#!/usr/bin/env python3
"""Trace the dominant opaque colors of a flat PNG into simple SVG paths."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import numpy as np
from contourpy import contour_generator
from PIL import Image
from scipy import ndimage
from shapely.geometry import Polygon


def path_data(mask: np.ndarray, tolerance: float) -> str:
    generator = contour_generator(z=mask.astype(float), line_type="Separate")
    commands = []
    for line in generator.lines(0.5):
        if len(line) < 4:
            continue
        polygon = Polygon(line).buffer(0).simplify(tolerance, preserve_topology=True)
        geometries = list(polygon.geoms) if polygon.geom_type == "MultiPolygon" else [polygon]
        for geometry in geometries:
            rings = [geometry.exterior, *geometry.interiors]
            for ring in rings:
                points = list(ring.coords)
                if len(points) < 4:
                    continue
                commands.append(
                    "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points[:-1]) + " Z"
                )
    return " ".join(commands)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("png", type=Path)
    parser.add_argument("svg", type=Path)
    parser.add_argument("--colors", type=int, default=2)
    parser.add_argument(
        "--id", action="append", default=[],
        help="repeat in dominant-color order to name the generated SVG regions",
    )
    parser.add_argument("--alpha-threshold", type=int, default=96)
    parser.add_argument("--simplify", type=float, default=0.65)
    parser.add_argument("--min-component", type=int, default=12)
    parser.add_argument("--close", type=int, default=1)
    parser.add_argument("--fill-holes", action="store_true")
    args = parser.parse_args()

    rgba = np.asarray(Image.open(args.png).convert("RGBA"))
    visible = rgba[..., 3] >= args.alpha_threshold
    opaque_rgb = rgba[..., :3][rgba[..., 3] >= 250]
    colors, counts = np.unique(opaque_rgb, axis=0, return_counts=True)
    if len(colors) < args.colors:
        raise SystemExit("not enough opaque colors to trace")
    palette = colors[np.argsort(counts)[-args.colors:][::-1]]
    distance = ((rgba[..., None, :3].astype(float) - palette[None, None]) ** 2).sum(axis=3)
    labels = distance.argmin(axis=2)

    paths = []
    for index, color in enumerate(palette):
        mask = visible & (labels == index)
        if args.close:
            mask = ndimage.binary_closing(mask, iterations=args.close)
        if args.fill_holes:
            mask = ndimage.binary_fill_holes(mask)
        components, count = ndimage.label(mask)
        for component_id in range(1, count + 1):
            component = components == component_id
            if int(component.sum()) < args.min_component:
                mask[component] = False
        data = path_data(mask, args.simplify)
        hex_color = "#{:02X}{:02X}{:02X}".format(*color)
        region_id = args.id[index] if index < len(args.id) else f"color-{index + 1}"
        region_id = "".join(
            char if char.isalnum() or char in "_.-" else "-" for char in region_id
        ).strip("-") or f"color-{index + 1}"
        paths.append(
            f'  <path id="{html.escape(region_id, quote=True)}" fill="{hex_color}" '
            f'fill-rule="evenodd" d="{html.escape(data, quote=True)}"/>'
        )
    height, width = rgba.shape[:2]
    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">\n'
        + "\n".join(paths)
        + "\n</svg>\n"
    )
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(document, encoding="utf-8")
    for index, color in enumerate(palette):
        region_id = args.id[index] if index < len(args.id) else f"color-{index + 1}"
        print(f"{region_id}=#{color[0]:02X}{color[1]:02X}{color[2]:02X}")
    print(args.svg.resolve())


if __name__ == "__main__":
    main()
