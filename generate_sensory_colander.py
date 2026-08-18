"""Generate a robust toddler sensory-play colander as a printable STL.

The model is intentionally parameterized near the top of this file.  All units
are millimetres.  Boolean operations use manifold3d through trimesh.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw


# Overall proportions
BODY_HEIGHT = 46.0
OUTER_BOTTOM_RADIUS = 70.0
OUTER_TOP_RADIUS = 80.0
FLOOR_THICKNESS = 5.0

# Honeycomb openings.  HEX_RADIUS is centre-to-corner.
HEX_RADIUS = 5.0
HEX_LATTICE_RADIUS = 6.75  # larger than HEX_RADIUS to leave a sturdy web
HEX_FIELD_RADIUS = 58.0

OUTPUT = Path("printable_files/toddler_sensory_colander.stl")
PREVIEW = Path("previews/toddler_sensory_colander.png")


def render_preview(model: trimesh.Trimesh) -> None:
    """Save a lightweight orthographic isometric preview using painter sorting."""
    rz = trimesh.transformations.rotation_matrix(math.radians(32), [0, 0, 1])[:3, :3]
    rx = trimesh.transformations.rotation_matrix(math.radians(62), [1, 0, 0])[:3, :3]
    points = model.vertices @ (rx @ rz).T
    xy = points[:, :2]
    lo, hi = xy.min(axis=0), xy.max(axis=0)
    size = np.maximum(hi - lo, 1e-9)
    canvas = np.array([1100.0, 760.0])
    scale = min((canvas[0] - 80) / size[0], (canvas[1] - 80) / size[1])
    screen = (xy - lo) * scale + 40
    screen[:, 1] = canvas[1] - screen[:, 1]

    image = Image.new("RGB", tuple(canvas.astype(int)), (246, 244, 238))
    draw = ImageDraw.Draw(image)
    face_depth = points[model.faces, 2].mean(axis=1)
    normals = model.face_normals @ (rx @ rz).T
    for face_index in np.argsort(face_depth):
        face = model.faces[face_index]
        light = float(np.clip(0.50 + 0.42 * normals[face_index, 2], 0.22, 0.94))
        colour = (int(48 + 85 * light), int(104 + 105 * light), int(130 + 105 * light))
        polygon = [tuple(screen[index]) for index in face]
        draw.polygon(polygon, fill=colour)

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    image.save(PREVIEW)


def make_body() -> trimesh.Trimesh:
    """Revolve a chamfered radial section to form a flat-bottomed pot."""
    # (radius, z) loop around the solid cross-section.  Short diagonal runs
    # form the requested small bevels on the base, rim, and inside floor.
    profile = np.array(
        [
            [0.0, 0.0],
            [OUTER_BOTTOM_RADIUS, 0.0],
            [72.0, 2.0],
            [80.0, 42.0],
            [80.0, 44.0],
            [78.0, BODY_HEIGHT],
            [74.0, BODY_HEIGHT],
            [72.0, 44.0],
            [68.0, 7.0],
            [66.0, FLOOR_THICKNESS],
            [0.0, FLOOR_THICKNESS],
        ],
        dtype=float,
    )
    body = trimesh.creation.revolve(profile, sections=192)
    body.remove_unreferenced_vertices()
    return body


def honeycomb_centres() -> list[tuple[float, float]]:
    """Return a centred pointy-top hex lattice containing only full cells."""
    centres: list[tuple[float, float]] = []
    dx = math.sqrt(3.0) * HEX_LATTICE_RADIUS
    dy = 1.5 * HEX_LATTICE_RADIUS
    max_vertex_radius = HEX_FIELD_RADIUS - HEX_RADIUS

    for row in range(-8, 9):
        y = row * dy
        x_offset = 0.5 * dx if row % 2 else 0.0
        for col in range(-8, 9):
            x = col * dx + x_offset
            # The complete hex must fit inside the chosen circular field.
            vertices = [
                (
                    x + HEX_RADIUS * math.cos(math.radians(30 + 60 * k)),
                    y + HEX_RADIUS * math.sin(math.radians(30 + 60 * k)),
                )
                for k in range(6)
            ]
            if max(math.hypot(vx, vy) for vx, vy in vertices) <= HEX_FIELD_RADIUS:
                centres.append((x, y))

    # The lattice naturally includes a central complete opening.
    assert centres and any(abs(x) < 1e-8 and abs(y) < 1e-8 for x, y in centres)
    return centres


def make_hex_cutters() -> tuple[trimesh.Trimesh, int]:
    cutters = []
    centres = honeycomb_centres()
    for x, y in centres:
        cutter = trimesh.creation.cylinder(radius=HEX_RADIUS, height=9.0, sections=6)
        # Rotate 30 degrees for a pointy-top honeycomb and pass fully through
        # the 5 mm floor, with extra height for numerically clean subtraction.
        cutter.apply_transform(trimesh.transformations.rotation_matrix(math.radians(30), [0, 0, 1]))
        cutter.apply_translation([x, y, 3.5])
        cutters.append(cutter)
    return trimesh.util.concatenate(cutters), len(centres)


def main() -> None:
    body = make_body()
    cutters, hole_count = make_hex_cutters()
    model = trimesh.boolean.difference([body, cutters], engine="manifold")

    model.remove_unreferenced_vertices()
    model.merge_vertices()
    model.fix_normals()

    if not model.is_watertight:
        raise RuntimeError("Generated model is not watertight")
    if model.body_count != 1:
        raise RuntimeError(f"Expected one connected body, got {model.body_count}")
    if not model.is_winding_consistent:
        raise RuntimeError("Generated model has inconsistent face winding")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    model.export(OUTPUT)
    render_preview(model)

    extents = model.extents
    print(f"Wrote: {OUTPUT.resolve()}")
    print(f"Preview: {PREVIEW.resolve()}")
    print(f"Honeycomb holes: {hole_count}")
    print(f"Size: {extents[0]:.1f} x {extents[1]:.1f} x {extents[2]:.1f} mm")
    print(f"Triangles: {len(model.faces):,}")
    print(f"Volume: {model.volume / 1000.0:.1f} cm^3")
    print(f"Watertight: {model.is_watertight}; connected bodies: {model.body_count}")


if __name__ == "__main__":
    main()
