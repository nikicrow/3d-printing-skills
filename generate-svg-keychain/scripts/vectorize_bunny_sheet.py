#!/usr/bin/env python3
"""Split a horizontal bunny raster sheet into white/black/pink SVG artwork."""

from __future__ import annotations

import argparse
import html
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from vectorize_flat_png import path_data


def largest_component(mask: np.ndarray) -> np.ndarray:
    labels, count = ndimage.label(mask)
    if not count:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, count + 1))
    return labels == int(np.argmax(sizes) + 1)


def clean_small(mask: np.ndarray, minimum: int = 2) -> np.ndarray:
    labels, count = ndimage.label(mask)
    result = mask.copy()
    for component_id in range(1, count + 1):
        component = labels == component_id
        if int(component.sum()) < minimum:
            result[component] = False
    return result


def smooth_mask(mask: np.ndarray, sigma: float, threshold: float = 0.45) -> np.ndarray:
    """Turn antialiased raster coverage into a smooth, solid printable mask."""
    return ndimage.gaussian_filter(mask.astype(float), sigma=sigma) >= threshold


def svg_path(region_id: str, color: str, mask: np.ndarray, tolerance: float) -> str:
    data = path_data(mask, tolerance=tolerance)
    return (
        f'  <path id="{region_id}" fill="{color}" fill-rule="evenodd" '
        f'd="{html.escape(data, quote=True)}"/>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument(
        "--supersample", type=int, default=6,
        help="trace resolution multiplier; higher values produce smoother curves",
    )
    parser.add_argument(
        "--line-smoothing", type=float, default=1.15,
        help="Gaussian smoothing radius at supersampled resolution",
    )
    args = parser.parse_args()

    rgb = np.asarray(Image.open(args.image).convert("RGB"))
    height, width = rgb.shape[:2]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    names = ["bunny_left", "bunny_middle", "bunny_right"]

    for index, (x0, x1) in enumerate(
        zip(np.linspace(0, width, args.count + 1, dtype=int)[:-1],
            np.linspace(0, width, args.count + 1, dtype=int)[1:])
    ):
        panel = rgb[:, x0:x1]
        nonwhite = np.min(panel, axis=2) < 244
        rows, cols = np.where(nonwhite)
        if not len(rows):
            continue
        margin = 5
        r0, r1 = max(0, rows.min() - margin), min(height, rows.max() + margin + 1)
        c0, c1 = max(0, cols.min() - margin), min(panel.shape[1], cols.max() + margin + 1)
        crop_image = Image.fromarray(panel[r0:r1, c0:c1]).resize(
            ((c1 - c0) * args.supersample, (r1 - r0) * args.supersample),
            Image.Resampling.LANCZOS,
        )
        crop = np.asarray(crop_image)

        nonwhite = np.min(crop, axis=2) < 247
        main_linework = largest_component(nonwhite)
        joined = ndimage.binary_dilation(
            main_linework, iterations=max(1, args.supersample // 2)
        )
        joined = ndimage.binary_closing(
            joined, iterations=max(2, args.supersample)
        )
        silhouette = ndimage.binary_fill_holes(joined)
        silhouette = largest_component(silhouette)
        silhouette = smooth_mask(
            silhouette, sigma=args.line_smoothing * 1.4, threshold=0.5
        )
        silhouette = ndimage.binary_closing(silhouette, iterations=2)
        silhouette = ndimage.binary_fill_holes(silhouette)

        red, green, blue = (crop[..., channel].astype(int) for channel in range(3))
        pink_source = (
            (red > green + 12)
            & (red > blue + 8)
            & (red > 130)
            & nonwhite
        )
        pink = smooth_mask(pink_source, sigma=args.line_smoothing, threshold=0.38)
        pink = ndimage.binary_closing(pink, iterations=2)
        pink = clean_small(pink, minimum=max(12, args.supersample ** 2 * 2))

        # Include antialiased edge pixels before smoothing. The old hard 185
        # cutoff traced only the darkest pixel cores and produced broken,
        # blocky lines when enlarged to keychain scale.
        black_source = (np.max(crop, axis=2) < 225) & ~ndimage.binary_dilation(
            pink_source, iterations=1
        )
        black = smooth_mask(black_source, sigma=args.line_smoothing, threshold=0.42)
        black = ndimage.binary_closing(black, iterations=2)
        black = clean_small(black, minimum=max(8, args.supersample ** 2 // 2))

        # Keep all colored details on the reconstructed printable silhouette.
        black &= ndimage.binary_dilation(silhouette, iterations=args.supersample)
        pink &= ndimage.binary_dilation(silhouette, iterations=args.supersample // 2)
        silhouette |= black | pink

        name = names[index] if index < len(names) else f"bunny_{index + 1}"
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {crop.shape[1]} {crop.shape[0]}">\n'
            + svg_path("white_bunny", "#FFFFFF", silhouette, tolerance=1.1)
            + "\n"
            + svg_path("black_details", "#111111", black, tolerance=0.85)
            + "\n"
            + svg_path("pink_details", "#F59AA6", pink, tolerance=0.85)
            + "\n</svg>\n"
        )
        output = args.output_dir / f"{name}.svg"
        output.write_text(svg, encoding="utf-8")
        print(output.resolve())


if __name__ == "__main__":
    main()
