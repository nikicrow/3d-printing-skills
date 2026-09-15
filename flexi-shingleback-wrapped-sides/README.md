# Flexi shingleback with wrapped side scales

Revision of the accepted scale-aligned shingleback. The original version remains in `../flexi-shingleback-scale-aligned/`.

The local pangolin 3MF was inspected from the side and underneath. Its outer scales continue to the base and conceal the sides of the joint sheet, while the mechanism remains open underneath. This revision uses that arrangement with the shingleback's own scale texture.

## What changed

The existing lower side scales continue downward and gently outward to form individual curved covers. Their width follows the local joint envelope so that the narrower belly sections receive enough coverage. The extensions blend into the leg roots; the original feet, head, upper scales, middle-row registration and articulation layout are retained. The extensions are joined to their own rigid pieces, with gaps between adjacent pieces and clearance cavities around the joint mechanism.

The deformation reaches zero at 20 mm above the bed. Added geometry is limited to the outer moving pieces and the central part of each leg root. The original geometry is retained within mesh export tolerance. `side-wrap-validation.json` compares the revision against the accepted version.

## Files to print

- `flexi-shingleback-wrapped-sides.3mf`: full assembly, rotated and centred on a 256 mm bed, one build item containing 133 separate shells.
- `flexi-shingleback-wrapped-sides.stl`: full assembly with its length along Y.
- `flexi-shingleback-wrapped-sides-256mm-bed.stl`: bed-oriented STL.
- **`side-wrap-test.3mf` / `side-wrap-test.stl`**: eight actual flank pieces, including the new covers and their inward connections. Print this sample first.
- `scale-joint-test.stl` / `joint-test.3mf`: the previous thirteen-piece central joint sample at final dimensions.
- `flexi-shingleback-wrapped-sides.blend`: editable scene, one object per rigid piece.
- `print-parts/`: individual final-size parts at their assembled positions. Do not arrange these independently.

The animal remains approximately 275.5 x 124.1 x 40.5 mm overall. The rotated footprint is approximately 208 x 208 mm, suitable for a 256 mm bed and too large for the A1 mini at the intended size. Print the final files at 100%; the enlarged sculpt and widened joints are already incorporated.

`belly-side-detail.png` and `belly-lower-detail.png` show the new covers. `shingleback-preview.png`, `shingleback-side.png` and `shingleback-underside.png` show the complete animal. The colored inspection image is diagnostic only; the 3MF contains geometry, without printer settings or G-code.

## Validation and physical testing

The flat assembly has 133 separate connected pieces, 151 retained anchors and 252 intact connections between pieces. Static solid intersection checks and comparison of the lower mating quadrants are recorded in `validation.json` and `lattice-validation.json`. Final-size STL shell checks and joint checks are recorded in `export-validation.json` and `final-lattice-validation.json`. The minimum measured clearance before the 30% X stretch is approximately 0.298 mm; that stretch cannot reduce the Euclidean clearance.

This remains an unprinted prototype. The new covers may affect bending range; static checks do not prove motion or print success. Test the eight-piece side sample at 100% and check both bending directions after cooling before committing to the full print. Review the slicer layer preview and keep supports or brim from bridging moving gaps.

## Reproduction

Run `setup_wrapped.py`, `build_mesh.py`, `check_lattice.py`, `deliver.py`, `check_final_joints.py` and `check_preservation.py` with Python and the mesh libraries used by the accepted version. Run `assemble_blender.py`, `render_alignment.py` and `render_side_detail.py` with Blender in background mode, then `finish_package.py` with Python. `wrap_surface.py` controls the lower-scale continuation.

The normalized `parts/`, `source-print.npz`, unversioned `flexi-shingleback.stl` / `.3mf`, and `joint-test.stl` are intermediate files. Use the wrapped-sides delivery files or the print ZIP.
