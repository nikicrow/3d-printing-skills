#!/usr/bin/env python3
"""Generate the bunny trio and strawberry keychains from their source PNGs."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageColor
from scipy import ndimage

from mesh_utils import build_mask_prism, write_color_3mf


def largest(mask):
    labels, count = ndimage.label(mask)
    if not count:
        return mask
    sizes = ndimage.sum(mask, labels, range(1, count + 1))
    return labels == int(np.argmax(sizes) + 1)


def clean_small(mask, minimum):
    labels, count = ndimage.label(mask)
    result = mask.copy()
    for component_id in range(1, count + 1):
        component = labels == component_id
        if int(component.sum()) < minimum:
            result[component] = False
    return result


def scale_masks(masks, max_size_mm, ppm):
    height, width = masks[0].shape
    factor = max_size_mm * ppm / max(height, width)
    size = (max(2, round(width * factor)), max(2, round(height * factor)))
    scaled = []
    for mask in masks:
        image = Image.fromarray((mask * 255).astype(np.uint8)).resize(
            size, Image.Resampling.LANCZOS
        )
        scaled.append(np.asarray(image) >= 128)
    return scaled


def bunny_masks(sheet_path, ppm):
    rgb = np.asarray(Image.open(sheet_path).convert("RGB"))
    height, width = rgb.shape[:2]
    names = ("bunny_left", "bunny_middle", "bunny_right")
    edges = np.linspace(0, width, 4, dtype=int)
    for name, x0, x1 in zip(names, edges[:-1], edges[1:]):
        panel = rgb[:, x0:x1]
        nonwhite = np.min(panel, axis=2) < 244
        rows, cols = np.where(nonwhite)
        margin = 5
        r0, r1 = max(0, rows.min() - margin), min(height, rows.max() + margin + 1)
        c0, c1 = max(0, cols.min() - margin), min(panel.shape[1], cols.max() + margin + 1)
        crop = np.asarray(Image.fromarray(panel[r0:r1, c0:c1]).resize(
            ((c1 - c0) * 6, (r1 - r0) * 6), Image.Resampling.LANCZOS
        ))
        nonwhite = np.min(crop, axis=2) < 247
        outline = largest(nonwhite)
        silhouette = ndimage.binary_dilation(outline, iterations=3)
        silhouette = ndimage.binary_closing(silhouette, iterations=6)
        silhouette = ndimage.binary_fill_holes(largest(silhouette))
        silhouette = ndimage.gaussian_filter(silhouette.astype(float), 1.6) >= 0.5
        silhouette = ndimage.binary_fill_holes(silhouette)
        red, green, blue = (crop[..., i].astype(int) for i in range(3))
        pink_source = (
            (red > green + 12) & (red > blue + 8) & (red > 130) & nonwhite
        )
        pink = ndimage.gaussian_filter(pink_source.astype(float), 1.15) >= 0.38
        pink = clean_small(ndimage.binary_closing(pink, iterations=2), 72)
        black_source = (np.max(crop, axis=2) < 225) & ~ndimage.binary_dilation(
            pink_source, iterations=1
        )
        black = ndimage.gaussian_filter(black_source.astype(float), 1.15) >= 0.42
        black = clean_small(ndimage.binary_closing(black, iterations=2), 18)
        black &= ndimage.binary_dilation(silhouette, iterations=6)
        pink &= ndimage.binary_dilation(silhouette, iterations=3)
        silhouette |= black | pink
        white, black, pink = scale_masks([silhouette, black, pink], 55.0, ppm)
        yield name, [white, black, pink], ["#FFFFFF", "#111111", "#F59AA6"], [
            "white_bunny", "black_details", "pink_details"
        ]


def strawberry_masks(image_path, ppm):
    rgb = np.asarray(Image.open(image_path).convert("RGB"))
    red, green, blue = (rgb[..., i].astype(int) for i in range(3))
    red_mask = (red > 130) & (red > green * 1.45) & (red > blue * 1.35)
    green_mask = (green > 45) & (green > red * 1.25) & (green > blue * 1.1)
    rows, cols = np.where(red_mask | green_mask)
    margin = 8
    r0, r1 = max(0, rows.min() - margin), min(rgb.shape[0], rows.max() + margin + 1)
    c0, c1 = max(0, cols.min() - margin), min(rgb.shape[1], cols.max() + margin + 1)
    red_mask = red_mask[r0:r1, c0:c1]
    green_mask = green_mask[r0:r1, c0:c1]
    red_mask = ndimage.gaussian_filter(red_mask.astype(float), 1.0) >= 0.45
    green_mask = ndimage.gaussian_filter(green_mask.astype(float), 1.0) >= 0.45
    body = ndimage.binary_fill_holes(red_mask)
    seeds = clean_small(body & ~red_mask, 100)
    labels, count = ndimage.label(seeds)
    for component_id in range(1, count + 1):
        component = labels == component_id
        if int(component.sum()) > 2500:
            seeds[component] = False
    body, green_mask, seeds = scale_masks([body, green_mask, seeds], 55.0, ppm)
    return "strawberry", [body, green_mask, seeds], ["#CF3B48", "#2B6336", "#FFFFFF"], [
        "red_fruit", "green_leaves", "white_seeds"
    ]


def regularize(mask):
    result = mask.copy()
    for _ in range(10000):
        a, b = result[:-1, :-1], result[:-1, 1:]
        c, d = result[1:, :-1], result[1:, 1:]
        spots = np.argwhere((a & d & ~b & ~c) | (b & c & ~a & ~d))
        if not len(spots):
            break
        row, col = spots[0]
        candidates = (
            ((row, col), (row + 1, col + 1))
            if a[row, col] and d[row, col]
            else ((row, col + 1), (row + 1, col))
        )
        scores = []
        for rr, cc in candidates:
            scores.append(int(result[max(0, rr-1):rr+2, max(0, cc-1):cc+2].sum()))
        result[candidates[1 if scores[1] < scores[0] else 0]] = False
    return result


def layout(masks, ppm, border_mm, hole_diameter, hole_wall):
    height, width = masks[0].shape
    labels = np.full((height, width), -1, dtype=np.int16)
    for index, mask in enumerate(masks):
        labels[mask] = index
    border = round(border_mm * ppm)
    outer_radius = round((hole_diameter / 2 + hole_wall) * ppm)
    side = border + outer_radius + 4
    top = 2 * outer_radius + border + 4
    full = np.full((height + top + border + 8, width + 2 * side), -1, np.int16)
    full[top:top + height, side:side + width] = labels
    base = ndimage.binary_fill_holes(
        ndimage.binary_dilation(full >= 0, iterations=border)
    )
    rows, cols = np.where(base)
    top_row = rows.min()
    near = cols[rows <= top_row + max(2, ppm)]
    center_x = float(np.median(cols))
    cx = float(near[np.argmin(np.abs(near - center_x))])
    cy = float(top_row - outer_radius + round(hole_wall * ppm))
    yy, xx = np.ogrid[:base.shape[0], :base.shape[1]]
    base |= (xx - cx) ** 2 + (yy - cy) ** 2 <= outer_radius ** 2
    base &= ~((xx - cx) ** 2 + (yy - cy) ** 2 <= (hole_diameter * ppm / 2) ** 2)
    if ndimage.label(base)[1] != 1:
        raise RuntimeError("keyring did not connect to base")
    rows, cols = np.where(base)
    r0, r1 = max(0, rows.min()-2), min(base.shape[0], rows.max()+3)
    c0, c1 = max(0, cols.min()-2), min(base.shape[1], cols.max()+3)
    return full[r0:r1, c0:c1], base[r0:r1, c0:c1]


def crop_mesh(mask, z0, z1, ppm, bevel):
    rows, cols = np.where(mask)
    r0, r1 = max(0, rows.min()-1), min(mask.shape[0], rows.max()+2)
    c0, c1 = max(0, cols.min()-1), min(mask.shape[1], cols.max()+2)
    step = 1 / ppm
    x0 = c0 * step - mask.shape[1] * step / 2
    y0 = (mask.shape[0] - r1) * step - mask.shape[0] * step / 2
    mesh = build_mask_prism(mask[r0:r1, c0:c1], z0, z1, step, x0=x0, y0=y0, bevel=bevel)
    mesh.remove_unreferenced_vertices()
    return mesh


def write_obj(meshes, material_ids, colors, names, path):
    mtl = path.with_suffix(".mtl")
    with mtl.open("w", encoding="utf-8", newline="\n") as handle:
        for name, color in zip(names, colors):
            rgb = ImageColor.getrgb(color)
            handle.write(f"newmtl {name}\nKd {rgb[0]/255:.6f} {rgb[1]/255:.6f} {rgb[2]/255:.6f}\nillum 1\n\n")
    offset = 1
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(f"mtllib {mtl.name}\n")
        for index, (mesh, material_id) in enumerate(zip(meshes, material_ids), 1):
            handle.write(f"o part_{index}_{names[material_id]}\nusemtl {names[material_id]}\n")
            for x, y, z in mesh.vertices:
                handle.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            for a, b, c in mesh.faces + offset:
                handle.write(f"f {a} {b} {c}\n")
            offset += len(mesh.vertices)
    return mtl


def generate(name, masks, art_colors, art_names, output_dir, args):
    labels, base = layout(masks, args.ppm, args.border, args.hole_diameter, args.hole_wall)
    colors, names = ["#FFFFFF"], ["base_white"]
    for color, part_name in zip(art_colors, art_names):
        if color not in colors:
            colors.append(color); names.append(part_name)
    meshes = [crop_mesh(base, 0, args.base_height, args.ppm, args.bevel)]
    material_ids = [0]
    for art_index, color in enumerate(art_colors):
        components, count = ndimage.label(labels == art_index)
        for component_id in range(1, count + 1):
            clean_component = regularize(components == component_id)
            subs, subcount = ndimage.label(clean_component)
            for sub_id in range(1, subcount + 1):
                mask = subs == sub_id
                if mask.any():
                    meshes.append(crop_mesh(mask, args.base_height - 0.04, args.base_height + args.art_height, args.ppm, (0, args.bevel)))
                    material_ids.append(colors.index(color))
    if not all(mesh.is_watertight for mesh in meshes):
        raise RuntimeError(f"{name}: non-watertight output")
    output_dir.mkdir(parents=True, exist_ok=True)
    obj = output_dir / f"{name}_multicolour.obj"
    mtl = write_obj(meshes, material_ids, colors, names, obj)
    combined = trimesh.util.concatenate(meshes)
    face_material = np.concatenate([np.full(len(mesh.faces), mid, int) for mesh, mid in zip(meshes, material_ids)])
    threemf = output_dir / f"{name}_multicolour.3mf"
    write_color_3mf(combined, face_material, colors, str(threemf), names=names, object_name=name)
    pixels = np.full((*base.shape, 3), (232, 234, 239), np.uint8)
    pixels[base] = (255, 255, 255)
    for index, color in enumerate(art_colors):
        pixels[labels == index] = ImageColor.getrgb(color)
    preview = output_dir / f"{name}_preview.png"
    image = Image.fromarray(pixels)
    image.resize((image.width*3, image.height*3), Image.Resampling.NEAREST).save(preview)
    manifest = output_dir / f"{name}_manifest.json"
    manifest.write_text(json.dumps({
        "dimensions_mm": {"width": base.shape[1]/args.ppm, "depth": base.shape[0]/args.ppm, "height": args.base_height+args.art_height},
        "base_height_mm": args.base_height, "art_height_mm": args.art_height,
        "parts": len(meshes), "all_watertight": True, "materials": dict(zip(names, colors))
    }, indent=2) + "\n", encoding="utf-8")
    print(f"{name}: {base.shape[1]/args.ppm:.1f} x {base.shape[0]/args.ppm:.1f} x {args.base_height+args.art_height:.1f} mm; {len(meshes)} watertight parts")
    return preview, threemf, obj, mtl


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bunnies", type=Path, required=True)
    parser.add_argument("--strawberry", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("printable_files/keychains"))
    parser.add_argument("--base-height", type=float, default=3.5)
    parser.add_argument("--art-height", type=float, default=1.5)
    parser.add_argument("--border", type=float, default=3.0)
    parser.add_argument("--bevel", type=float, default=0.3)
    parser.add_argument("--hole-diameter", type=float, default=5.0)
    parser.add_argument("--hole-wall", type=float, default=2.5)
    parser.add_argument("--ppm", type=int, default=6)
    args = parser.parse_args()
    for job in bunny_masks(args.bunnies, args.ppm):
        generate(*job, args.output_root / "bunnies" / job[0], args)
    job = strawberry_masks(args.strawberry, args.ppm)
    generate(*job, args.output_root / "strawberry", args)


if __name__ == "__main__":
    main()
