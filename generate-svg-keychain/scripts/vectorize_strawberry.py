#!/usr/bin/env python3
"""Extract a flat red/green strawberry raster into printable SVG regions."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from vectorize_flat_png import path_data


def clean(mask: np.ndarray, minimum: int) -> np.ndarray:
    mask = ndimage.gaussian_filter(mask.astype(float), sigma=1.0) >= 0.45
    mask = ndimage.binary_closing(mask, iterations=1)
    labels, count = ndimage.label(mask)
    for component_id in range(1, count + 1):
        component = labels == component_id
        if int(component.sum()) < minimum:
            mask[component] = False
    return mask


def svg_path(region_id: str, color: str, mask: np.ndarray) -> str:
    data = path_data(mask, tolerance=1.25)
    return (
        f'  <path id="{region_id}" fill="{color}" fill-rule="evenodd" '
        f'd="{html.escape(data, quote=True)}"/>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("svg", type=Path)
    args = parser.parse_args()

    rgb = np.asarray(Image.open(args.image).convert("RGB"))
    red, green, blue = (rgb[..., channel].astype(int) for channel in range(3))
    red_mask = (red > 130) & (red > green * 1.45) & (red > blue * 1.35)
    green_mask = (green > 45) & (green > red * 1.25) & (green > blue * 1.1)
    colored = red_mask | green_mask
    rows, cols = np.where(colored)
    if not len(rows):
        raise SystemExit("no red/green strawberry artwork found")
    margin = 8
    r0, r1 = max(0, rows.min() - margin), min(rgb.shape[0], rows.max() + margin + 1)
    c0, c1 = max(0, cols.min() - margin), min(rgb.shape[1], cols.max() + margin + 1)
    red_mask = clean(red_mask[r0:r1, c0:c1], minimum=80)
    green_mask = clean(green_mask[r0:r1, c0:c1], minimum=80)

    # Seeds are the enclosed white islands inside the filled red fruit body.
    red_body = ndimage.binary_fill_holes(red_mask)
    seeds = red_body & ~red_mask
    seeds = clean(seeds, minimum=100)
    # Keep seed components modest so large open negative-space cutouts are not
    # mistaken for individual seed marks.
    labels, count = ndimage.label(seeds)
    for component_id in range(1, count + 1):
        component = labels == component_id
        if int(component.sum()) > 2500:
            seeds[component] = False

    document = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="0 0 {red_mask.shape[1]} {red_mask.shape[0]}">\n'
        + svg_path("red_fruit", "#CF3B48", red_body)
        + "\n"
        + svg_path("green_leaves", "#2B6336", green_mask)
        + "\n"
        + svg_path("white_seeds", "#FFFFFF", seeds)
        + "\n</svg>\n"
    )
    args.svg.parent.mkdir(parents=True, exist_ok=True)
    args.svg.write_text(document, encoding="utf-8")
    print(f"Seeds traced: {ndimage.label(seeds)[1]}")
    print(args.svg.resolve())


if __name__ == "__main__":
    main()
