#!/usr/bin/env python3
"""
mesh_utils.py
=============
Generic, project-agnostic geometry helpers for turning a 2D grayscale
heightmap into a watertight, print-ready cylindrical solid.

Like :mod:`svg_processing`, nothing here knows about Play-Doh rollers or
themes — these are the reusable "back end" shared by any tool that wraps a
relief pattern around a barrel:

  * ``build_roller_mesh`` — wrap a heightmap onto a cylinder so raised texels
    bump the surface outward (or inward, for an engraved/negative roller),
    closed into a single watertight solid, with an optional raised icon stamp
    on one end.
  * ``polar_disk_relief`` — raise a silhouette mask out of a flat polar disk
    (the end-stamp primitive used by ``build_roller_mesh``).
  * ``axial_handles`` — grip cylinders that overlap the ends of an axis-aligned
    barrel.
  * ``stand_upright_on_end`` — rotate an X-axis barrel to stand on its end
    (axis → Z) and recentre it on the bed for support-free printing.

The displaced-cylinder construction is the efficient, watertight equivalent of
"add a radial prism per raised pixel": grid vertices on raised texels sit at
``radius + emboss`` while everything else sits at ``radius``, and both ends are
closed to a centre point so every bump is a real protrusion of one solid.

DEPENDENCIES
------------
    pip install trimesh numpy --break-system-packages
"""

import math

import numpy as np


def polar_disk_relief(mask, radius, relief, n_theta, thetas, start_index,
                      n_rings):
    """Raise a silhouette mask out of a flat polar disk of radius ``radius``.

    The disk is tessellated as ``n_rings`` concentric rings (radius ``radius``
    down to ``0``) sharing an outer ring of ``n_theta`` vertices with the body
    it caps, plus a single centre vertex. Wherever the mask is set, the
    corresponding disk vertex is displaced outward (to ``x = -relief``); the
    rest stay at ``x = 0``. The result shares the body's end ring, so the whole
    thing remains one watertight solid with no booleans.

    Vertices are returned ready to ``np.vstack`` onto an existing vertex array;
    faces are returned as absolute indices assuming the new vertices start at
    ``start_index`` and the body's end ring occupies indices ``0..n_theta-1``.

    Parameters
    ----------
    mask : PIL.Image.Image or numpy.ndarray
        Square icon mask; truthy (``> 127``) pixels are raised. Sampled in
        polar coordinates across the disk.
    radius : float
        Disk radius, in mm (matches the barrel radius it caps).
    relief : float
        How far, in mm, raised pixels bump outward from the flat end.
    n_theta : int
        Number of angular divisions; must equal the body end-ring count so the
        outer ring vertices line up.
    thetas : numpy.ndarray
        Length-``n_theta`` array of angles (radians) for the outer ring,
        matching the body's cross-section.
    start_index : int
        Vertex index at which the returned interior vertices will be appended
        to the body's vertex array.
    n_rings : int
        Number of radial rings used to tessellate the disk (higher = finer).

    Returns
    -------
    verts : numpy.ndarray, shape (n_rings * n_theta - n_theta + 1, 3)
        Interior + centre vertices to append to the body (the outer ring is the
        body's existing end ring and is *not* duplicated here).
    faces : numpy.ndarray, shape (M, 3)
        Triangle indices (into the combined vertex array) tessellating the
        disk.
    """
    M = np.asarray(mask) > 127
    himg, wimg = M.shape
    K = n_rings                              # number of radial rings
    ct = np.cos(thetas)
    st = np.sin(thetas)

    # Interior rings k=1..K-1 (radius R -> 0), vectorised.
    ks = np.arange(1, K)
    r_k = (radius * (K - ks) / K)[:, None]   # (K-1, 1)
    Y = r_k * ct[None, :]                     # (K-1, n_theta)
    Z = r_k * st[None, :]
    U = np.clip(np.round((0.5 + 0.5 * (Y / radius)) * (wimg - 1)).astype(int),
                0, wimg - 1)
    V = np.clip(np.round((0.5 + 0.5 * (Z / radius)) * (himg - 1)).astype(int),
                0, himg - 1)
    Xr = np.where(M[V, U], -relief, 0.0)      # raised outward from the x=0 end
    verts = np.stack([Xr.ravel(), Y.ravel(), Z.ravel()], axis=1)
    center_on = M[(himg - 1) // 2, (wimg - 1) // 2]
    verts = np.vstack([verts, [[-relief if center_on else 0.0, 0.0, 0.0]]])
    center_idx = start_index + (K - 1) * n_theta

    def ring_base(k):
        return 0 if k == 0 else start_index + (k - 1) * n_theta

    I = np.arange(n_theta)
    I2 = (I + 1) % n_theta
    parts = []
    for k in range(K - 1):                    # ~K iters of vectorised stacks
        b0, b1 = ring_base(k), ring_base(k + 1)
        a, b = b0 + I, b0 + I2
        c, d = b1 + I, b1 + I2
        parts.append(np.stack([a, d, b], axis=1))   # winding fixed by normals
        parts.append(np.stack([a, c, d], axis=1))
    bK = ring_base(K - 1)
    parts.append(np.stack([bK + I, np.full(n_theta, center_idx), bK + I2],
                          axis=1))
    return verts, np.concatenate(parts)


def build_roller_mesh(height, radius, length, emboss, engrave=False,
                      n_theta_max=720, n_z_max=720,
                      stamp_mask=None, stamp_relief=2.5, stamp_n_rings=None):
    """Wrap a heightmap onto a cylinder as one watertight, print-ready solid.

    The heightmap is sampled onto a ``n_z`` x ``n_theta`` grid (capped by
    ``n_z_max`` / ``n_theta_max`` to keep the triangle count sane). Grid
    vertices on raised texels (``height > 0.5``) sit at ``radius + emboss`` and
    the rest at ``radius``, so features extrude outward and press *into* the
    dough. With ``engrave=True`` the displacement is inverted (``radius -
    emboss``) for a negative/engraved roller whose dough imprint comes out
    raised. Both ends are closed to a centre point so the textured shell is a
    single watertight solid.

    The cylinder axis is **X**; its cross-section lies in the ``(Y, Z)`` plane,
    with the bed end at ``x = length`` and the stamp end at ``x = 0``.

    Parameters
    ----------
    height : numpy.ndarray, shape (H, W)
        Grayscale heightmap in ``[0, 1]``; ``> 0.5`` marks a raised feature.
        Axis 0 (rows) runs along the roller length; axis 1 (columns) runs
        around the circumference and tiles.
    radius : float
        Barrel radius in mm.
    length : float
        Barrel length in mm.
    emboss : float
        Feature height in mm (added to / subtracted from ``radius``).
    engrave : bool, optional
        If ``True``, recess features inward (``radius - emboss``) instead of
        raising them. Defaults to ``False``.
    n_theta_max : int, optional
        Cap on angular divisions around the circumference. Defaults to ``720``.
    n_z_max : int, optional
        Cap on divisions along the length. Defaults to ``720``.
    stamp_mask : PIL.Image.Image or numpy.ndarray, optional
        If given, an icon silhouette raised out of the ``x = 0`` end via
        :func:`polar_disk_relief`, turning that end into a press-stamp. The end
        ring is flattened to a clean circle first. ``None`` (default) leaves a
        plain flat end cap.
    stamp_relief : float, optional
        Height in mm of the raised end stamp. Defaults to ``2.5``. Ignored when
        ``stamp_mask`` is ``None``.
    stamp_n_rings : int, optional
        Number of radial rings for the stamp disk tessellation. Required when
        ``stamp_mask`` is given; ignored otherwise.

    Returns
    -------
    trimesh.Trimesh
        The barrel as a single mesh, axis along X, built with
        ``process=False`` (topology guarantees watertightness; normal winding
        is left for the slicer to auto-repair on import).
    """
    import trimesh

    H, W = height.shape
    n_theta = min(W, n_theta_max)        # around circumference (wrapped)
    n_z = min(H, n_z_max)                # along the axis (X)

    thetas = np.linspace(0.0, 2 * math.pi, n_theta, endpoint=False)
    zs = np.linspace(0.0, length, n_z)

    # Sample the heightmap onto the grid (nearest).
    sx = (np.linspace(0, W - 1, n_theta)).astype(int)   # circumference -> x
    sy = (np.linspace(0, H - 1, n_z)).astype(int)       # length -> y
    samp = height[np.ix_(sy, sx)]                        # shape (n_z, n_theta)
    # v1: features bump OUTWARD (R+E). v2 (engrave): features are recessed
    # INWARD (R-E) so the dough comes out raised instead of indented.
    sign = -1.0 if engrave else 1.0
    radii = radius + sign * emboss * (samp > 0.5)        # (n_z, n_theta)
    if stamp_mask is not None:
        radii[0, :] = radius   # clean circular ring on the stamped (x=0) end

    # Build vertices (vectorised). Axis = X, cross-section in (Y, Z). A centre
    # point is added at each end so the textured surface closes into a single
    # watertight solid.
    ct = np.cos(thetas)
    st = np.sin(thetas)
    grid = np.empty((n_z * n_theta, 3), dtype=np.float64)
    grid[:, 0] = np.repeat(zs, n_theta)
    grid[:, 1] = (radii * ct[None, :]).ravel()
    grid[:, 2] = (radii * st[None, :]).ravel()
    c0 = n_z * n_theta            # centre of the x=0 end
    c1 = n_z * n_theta + 1        # centre of the x=L end
    verts = np.vstack([grid, [[0.0, 0.0, 0.0]], [[length, 0.0, 0.0]]])

    # Side faces (quads -> 2 triangles), wrapping in theta (vectorised).
    J, I = np.meshgrid(np.arange(n_z - 1), np.arange(n_theta), indexing="ij")
    I2 = (I + 1) % n_theta
    a = J * n_theta + I
    b = J * n_theta + I2
    c = (J + 1) * n_theta + I
    dd = (J + 1) * n_theta + I2
    side = np.concatenate([
        np.stack([a, b, dd], axis=-1).reshape(-1, 3),
        np.stack([a, dd, c], axis=-1).reshape(-1, 3)])

    # Bed end (x=L) -> flat fan to its centre point.
    Iv = np.arange(n_theta)
    Iv2 = (Iv + 1) % n_theta
    top = (n_z - 1) * n_theta
    bed = np.stack([np.full(n_theta, c1), top + Iv2, top + Iv], axis=1)

    face_parts = [side, bed]
    # Stamp end (x=0): either a raised icon stamp disk, or a plain flat fan.
    if stamp_mask is not None:
        sv, sf = polar_disk_relief(stamp_mask, radius, stamp_relief, n_theta,
                                   thetas, start_index=c1 + 1,
                                   n_rings=stamp_n_rings)
        verts = np.vstack([verts, sv])
        face_parts.append(sf)
    else:
        face_parts.append(np.stack([np.full(n_theta, c0), Iv, Iv2], axis=1))

    faces = np.concatenate(face_parts)
    # Watertightness comes from topology (every edge is shared by 2 faces via
    # shared vertex indices), so we skip trimesh's expensive normal/merge
    # passes (fix_normals builds a face-adjacency graph over >1M faces ->
    # minutes). Normal winding is left for the slicer to auto-repair on import.
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def axial_handles(body_length, handle_length, handle_radius, sections=64):
    """Build two grip cylinders that overlap the ends of an X-axis barrel.

    Each handle is a cylinder oriented along X, slightly overlapping the body
    (by 0.5 mm) so the union stays watertight after concatenation.

    Parameters
    ----------
    body_length : float
        Length in mm of the barrel the handles attach to (its ends are at
        ``x = 0`` and ``x = body_length``).
    handle_length : float
        Length in mm of each handle stub.
    handle_radius : float
        Radius in mm of each handle (typically smaller than the barrel).
    sections : int, optional
        Number of facets around each handle cylinder. Defaults to ``64``.

    Returns
    -------
    list of trimesh.Trimesh
        ``[low_end_handle, high_end_handle]`` positioned beyond ``x = 0`` and
        ``x = body_length`` respectively.
    """
    import trimesh

    hl, hr = handle_length, handle_radius
    h1 = trimesh.creation.cylinder(radius=hr, height=hl, sections=sections)
    h1.apply_transform(trimesh.transformations.rotation_matrix(
        math.pi / 2, [0, 1, 0]))
    h1.apply_translation([-hl / 2 + 0.5, 0, 0])             # slight overlap
    h2 = trimesh.creation.cylinder(radius=hr, height=hl, sections=sections)
    h2.apply_transform(trimesh.transformations.rotation_matrix(
        math.pi / 2, [0, 1, 0]))
    h2.apply_translation([body_length + hl / 2 - 0.5, 0, 0])
    return [h1, h2]


def stand_upright_on_end(mesh):
    """Rotate an X-axis barrel to stand on its end and sit it on the bed.

    The mesh is rotated so its axis points along **Z**, then translated so it
    is centred in X/Y and its lowest point rests on ``z = 0``. In this upright
    orientation every print layer is a ring with the relief on its outer wall,
    so the part prints support-free with no overhangs. Mutates ``mesh`` in
    place.

    Parameters
    ----------
    mesh : trimesh.Trimesh
        Barrel whose axis currently runs along X. Modified in place.

    Returns
    -------
    trimesh.Trimesh
        The same ``mesh`` object, now standing upright on ``z = 0``.
    """
    import trimesh

    mesh.apply_transform(trimesh.transformations.rotation_matrix(
        math.pi / 2, [0, 1, 0]))
    b = mesh.bounds
    mesh.apply_translation([-(b[0, 0] + b[1, 0]) / 2,     # centre X
                            -(b[0, 1] + b[1, 1]) / 2,     # centre Y
                            -b[0, 2]])                    # sit on z=0
    return mesh
