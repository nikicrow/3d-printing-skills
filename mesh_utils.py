#!/usr/bin/env python3
"""
mesh_utils.py
=============
Generic, project-agnostic geometry helpers for turning a 2D grayscale
heightmap into watertight, print-ready solids — cylindrical rollers and flat
slab stamps.

Like :mod:`svg_processing`, nothing here knows about Play-Doh rollers, stamps
or themes — these are the reusable "back end" shared by any tool that turns a
relief pattern into printable geometry:

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
  * ``build_slab_relief`` — extrude a relief heightmap into a flat watertight
    slab (bumpy underside, flat top): the stamp/plate primitive.
  * ``dome_knob`` — a parametric watertight squashed hemisphere, used as a
    self-supporting grip handle.

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


def build_slab_relief(bottom_z, top_z, width, length):
    """Extrude a relief heightmap into a flat, watertight slab.

    The planar analogue of :func:`build_roller_mesh`: instead of wrapping the
    relief around a barrel, it displaces the **underside** of a rectangular
    plate. A grid of vertices (matching the shape of ``bottom_z``) spans
    ``[0, width] x [0, length]`` in X/Y; the bottom vertices sit at
    ``bottom_z`` and the top vertices at the constant plane ``top_z``. The two
    surfaces are stitched by four side walls into a single closed box, so
    features carved into / raised from the underside are real protrusions of
    one solid (no booleans).

    Built directly in print orientation: the plate lies flat with its stamping
    face down, so the lowest points of ``bottom_z`` (typically ``0``) rest on
    the bed and the flat top faces up (ready for a handle).

    Parameters
    ----------
    bottom_z : numpy.ndarray, shape (H, W)
        Underside height, in mm, at each grid node. Axis 0 (rows) runs along
        ``length`` (Y); axis 1 (columns) along ``width`` (X). Where this is
        higher than the surrounding contact plane, the face is recessed
        (a groove); where it is lower, it protrudes toward the bed.
    top_z : float
        Constant Z, in mm, of the flat top surface (must exceed
        ``bottom_z.max()`` for a solid plate).
    width : float
        Plate extent along X, in mm.
    length : float
        Plate extent along Y, in mm.

    Returns
    -------
    trimesh.Trimesh
        The slab as a single watertight mesh, built with ``process=False``
        (topology guarantees watertightness; normal winding is left for the
        slicer to auto-repair on import).
    """
    import trimesh

    H, Wg = bottom_z.shape
    xs = np.linspace(0.0, width, Wg)
    ys = np.linspace(0.0, length, H)
    gx, gy = np.meshgrid(xs, ys)

    n = H * Wg
    bottom = np.stack([gx.ravel(), gy.ravel(), bottom_z.ravel()], axis=1)
    top = np.stack([gx.ravel(), gy.ravel(), np.full(n, top_z)], axis=1)
    verts = np.vstack([bottom, top])            # [0:n]=bottom, [n:2n]=top

    def idx(j, i):
        return j * Wg + i

    J, I = np.meshgrid(np.arange(H - 1), np.arange(Wg - 1), indexing="ij")
    a = idx(J, I)
    b = idx(J, I + 1)
    c = idx(J + 1, I)
    d = idx(J + 1, I + 1)

    # Bottom surface (normals point DOWN, -Z).
    bot = np.concatenate([
        np.stack([a, b, d], -1).reshape(-1, 3),
        np.stack([a, d, c], -1).reshape(-1, 3)])
    # Top surface (flat, normals UP, +Z) — same grid + n, reversed winding.
    top_f = np.concatenate([
        np.stack([a + n, d + n, b + n], -1).reshape(-1, 3),
        np.stack([a + n, c + n, d + n], -1).reshape(-1, 3)])

    # Four side walls stitching the bottom boundary to the top boundary.
    walls = []
    for j, flip in ((0, True), (H - 1, False)):          # edges along X
        i = np.arange(Wg - 1)
        b0, b1 = idx(j, i), idx(j, i + 1)
        t0, t1 = b0 + n, b1 + n
        if flip:
            walls.append(np.stack([b0, b1, t1], -1))
            walls.append(np.stack([b0, t1, t0], -1))
        else:
            walls.append(np.stack([b0, t1, b1], -1))
            walls.append(np.stack([b0, t0, t1], -1))
    for i, flip in ((0, False), (Wg - 1, True)):         # edges along Y
        j = np.arange(H - 1)
        b0, b1 = idx(j, i), idx(j + 1, i)
        t0, t1 = b0 + n, b1 + n
        if flip:
            walls.append(np.stack([b0, b1, t1], -1))
            walls.append(np.stack([b0, t1, t0], -1))
        else:
            walls.append(np.stack([b0, t1, b1], -1))
            walls.append(np.stack([b0, t0, t1], -1))

    faces = np.concatenate([bot, top_f] + walls)
    return trimesh.Trimesh(vertices=verts, faces=faces, process=False)


def dome_knob(radius, height, n_theta=48, n_phi=14):
    """Build a watertight squashed hemisphere (a grip knob) on its flat base.

    A parametric dome — no shapely / boolean backend required — tessellated as
    ``n_phi`` latitude rings from the base (``z = 0``, radius ``radius``) up to
    a single apex at ``z = height``, closed underneath by a centre-fan base
    disk. Wide sturdy base + rounded, self-supporting top make it a good
    toddler-friendly handle that prints without supports. Place it by
    translating so its base sits (slightly embedded) on the part it grips.

    Parameters
    ----------
    radius : float
        Base radius of the dome, in mm.
    height : float
        Apex height above the base, in mm (``< radius`` gives a flatter, comfier
        knob; ``== radius`` is a true hemisphere).
    n_theta : int, optional
        Angular divisions around the dome. Defaults to ``48``.
    n_phi : int, optional
        Latitude rings from base to apex. Defaults to ``14``.

    Returns
    -------
    trimesh.Trimesh
        The dome as a single watertight mesh with its flat base on ``z = 0``,
        built with ``process=False``.
    """
    import trimesh

    phis = np.linspace(0.0, math.pi / 2, n_phi + 1)      # 0=base ring, pi/2=apex
    thetas = np.linspace(0.0, 2 * math.pi, n_theta, endpoint=False)
    ct, st = np.cos(thetas), np.sin(thetas)

    rings = phis[:-1]                                    # drop apex (a point)
    rr = radius * np.cos(rings)
    zz = height * np.sin(rings)
    V = np.empty((len(rings) * n_theta, 3))
    for k in range(len(rings)):
        base = k * n_theta
        V[base:base + n_theta, 0] = rr[k] * ct
        V[base:base + n_theta, 1] = rr[k] * st
        V[base:base + n_theta, 2] = zz[k]
    apex = len(V)
    base_c = apex + 1
    V = np.vstack([V, [[0, 0, height]], [[0, 0, 0.0]]])

    I = np.arange(n_theta)
    I2 = (I + 1) % n_theta
    faces = []
    for k in range(len(rings) - 1):                     # side quads
        b0, b1 = k * n_theta, (k + 1) * n_theta
        faces.append(np.stack([b0 + I, b1 + I, b1 + I2], -1))
        faces.append(np.stack([b0 + I, b1 + I2, b0 + I2], -1))
    top = (len(rings) - 1) * n_theta                    # fan to apex
    faces.append(np.stack([top + I, np.full(n_theta, apex), top + I2], -1))
    faces.append(np.stack([I, I2, np.full(n_theta, base_c)], -1))  # base disk
    return trimesh.Trimesh(vertices=V, faces=np.concatenate(faces),
                           process=False)
