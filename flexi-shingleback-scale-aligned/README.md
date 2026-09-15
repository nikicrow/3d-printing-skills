# Scale-aligned flexi shingleback

New articulation layout using the supplied Meshy v2 shingleback. The OBJ inside the supplied ZIP was SHA-256 compared with the existing v2 source before reusing its repaired mesh. Earlier shingleback versions are preserved in their original folders.

The sculpt is uniformly enlarged to 145% of the previous 190 mm model: approximately **275.5 mm long, 124.1 mm wide and 40.5 mm high**. The recovered pangolin mechanism is widened 30% across the animal, retaining its original longitudinal and vertical dimensions. This brings the link proportions closer to the broad, short scales. This is a newly modified mechanism that still needs a physical test.

## Scale alignment

The middle row uses manually identified scale centres from the source model. Eighteen moving middle pieces are registered to these targets across the body and tail. One pair of shorter tail scales shares a cluster, and the final target lies in the rigid tail tip. This count describes registered pieces, not eighteen perfectly traced scales.

Upper cell spacing varies with the scale spacing independently of the regular lower joints. Shared upper boundaries are then nudged into nearby surface grooves, using a triangle-rasterized height map. The neighboring rows receive the same longitudinal registration and local groove fitting. Alignment is approximate, especially at the neck, flank, leg roots and short tail scales. The head, complete feet and tail tip remain rigid anatomical sections.

`scale-alignment-map.png` highlights the eighteen targeted moving middle pieces in alternating teal and amber. Those colors are inspection aids; the 3MF contains geometry only. `middle-scale-detail.png` shows the actual sculpt and seams without highlights.

## Print files

- `flexi-shingleback-scale-aligned.3mf`: one assembled build item containing all separate shells, rotated 45 degrees and centred on a 256 mm bed.
- `flexi-shingleback-scale-aligned.stl`: full assembly, length along Y.
- `flexi-shingleback-scale-aligned-256mm-bed.stl`: the same bed orientation as the 3MF.
- `scale-joint-test.stl` and `joint-test.3mf`: thirteen actual middle pieces for a small print test at the final joint dimensions.
- `flexi-shingleback-scale-aligned.blend`: editable scene with one object per rigid piece, millimeter units.
- `print-parts/`: individual final-size pieces at their assembled positions. Keep their relative positions when printing.

The rotated footprint is approximately **208 x 208 mm**. It fits a 256 x 256 mm bed, but does not fit an A1 mini's 180 mm square bed at the intended size. Reducing the entire model also reduces the joint gaps; the enlarged sculpt and widened joints are already built into the final files. Print the final files at 100%.

## Validation and prototype status

133 watertight, consistently wound, single-shell pieces; all belong to one connected network. The 151 retained anchors have 252 intact connections between moving pieces. Lower mating quadrants were compared with the reference mechanism, with no missing quadrant beyond the 0.015 cubic mm tolerance in normalized coordinates. No pairwise solid intersections were detected in the assembled flat pose. The measured minimum clearance before widening X is 0.2978 mm; widening X cannot reduce that Euclidean clearance. Upper seams are approximately 0.70-0.91 mm wide depending on their direction.

This is an **unprinted prototype**. Static checks do not establish bending range, freedom from collision while flexing, or successful printing. Print the included joint sample first and check movement in both directions after cooling. Inspect the slicer's layer preview for bridges and overhangs and prevent supports or brim from joining moving pieces. The files contain no printer profile or G-code.

`validation.json`, `lattice-validation.json`, `final-lattice-validation.json`, `groove-fit.json` and `export-validation.json` record the checks. The final lattice check repeats the joint comparison on the cleaned, final-size STL pieces. `groove-fit.json` measures proximity to lower surface grooves; it is not a scale-match percentage.

## Reproduction

Use Python with numpy, scipy, trimesh and manifold3d. Run `setup_design.py`, `build_mesh.py`, `check_lattice.py`, `deliver.py`, and `check_final_joints.py` in that order. Run `assemble_blender.py` and `render_alignment.py` with Blender in background mode, then `finish_package.py` with Python. The supplied ZIP and previous v2 repaired source are inputs to setup; their locations are explicit in that script.

The `parts/` folder, `source-print.npz`, unversioned `flexi-shingleback.stl` / `.3mf`, and `joint-test.stl` are intermediate geometry in normalized X coordinates. Use the named final files or the print ZIP for printing.
