# Flexi shingleback v2

Created from the supplied Meshy_AI_shingleback_lizard_v2_0913105224_image-to-3d-texture_obj.zip. The sculpt is uniformly sized to approximately 190 mm long and repaired at 0.22 mm voxel resolution. The head, all four complete feet, and tail tip are rigid sections; the body and remaining tail are separate moving scale clusters.

The underside uses the original pangolin interlocking sheet pattern, recovered directly from FLEXI+PANGOLIN+A1+MINI+BAMBU.3mf. Its original profile XY scale and separate Z scale are preserved. Diagonal anchor offsets are 5.2277 mm X and 5.0736 mm Y, matching the earlier shingleback. Working joint quadrants are retained; unused outer arms are trimmed. The natural flank surface is retained outside the working joint envelopes. Surface seams are 0.7 mm wide.

## Files

- flexi-shingleback-v2.blend: editable scene, one object per rigid piece, millimeter units.
- flexi-shingleback-v2.3mf: printable assembled geometry rotated 45 degrees and centered on a 180 mm bed, with one build item containing the separate shells.
- flexi-shingleback-v2.stl: complete assembly with length along Y.
- flexi-shingleback-v2-A1-mini.stl: rotated bed-oriented assembly.
- joint-test.stl / .3mf: 13-piece patch of the actual body and joints.
- side-edge-test.stl / .3mf: a flank patch with its inward connections.
- parts/: individual rigid pieces at their assembled positions. Do not independently arrange these for printing.
- shingleback-preview.png, shingleback-top.png, shingleback-side.png, shingleback-underside.png: inspection renders.
- validation.json and lattice-validation.json: geometric checks.

## Validation and print status

77 watertight, consistently wound, single-shell pieces. All 77 belong to one connected network, with 86 anchors and 138 intact neighbor connections. No detected pairwise intersections in the flat assembled pose. Minimum measured static clearance: 0.2978 mm. Every mating lower joint quadrant was compared against the recovered reference geometry; none is missing beyond the 0.015 cubic mm comparison tolerance.

Dimensions: 189.98 mm long, 85.56 mm wide, 27.91 mm high. Rotated bed footprint: 143.29 by 143.43 mm. The 3MF contains geometry only, with no printer profile or G-code. Preview colors are presentation materials.

This is an unprinted prototype. Static separation and intact connections do not prove two-direction range of motion, freedom from collisions during bending, or reliable printing. Print the small joint and edge samples at 100% scale before the full model; check both directions after cooling. Scaling changes the joint clearances. Review the layer preview using your printer and filament settings, and avoid supports or brim that bridge the moving gaps.

## Reproduction

Source files remain under reference/. Run prepare.py with Blender 5.2 in background mode. Run extract_link.py with Python and the project lib/ dependencies to recover the original mechanism. Then run build_mesh.py, package_print.py, and check_lattice.py with Python, followed by assemble_blender.py with Blender. package_print.py removes obsolete generated part files if the grouping changes. The extraction retains the source profile's nonuniform vertical scale; do not replace it with a uniform scale.

The unversioned flexi-shingleback.stl and flexi-shingleback.3mf are intermediate build outputs; use the v2-named delivery files above.

## Hind-leg correction

Both hind legs use one continuous anatomical region, including the thigh and all toes. Only the three body anchors at each leg root are fused; the tail-side anchors behind each leg are separate moving pieces again. The prior version is preserved in before-hindleg-fix/. See hindleg-detail.png for the corrected seam layout.
