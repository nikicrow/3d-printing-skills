from pathlib import Path
OUT=Path(__file__).parent;OLD=OUT.parent/'flexi-shingleback-scale-aligned'
for name in ['source-print.npz','reference-link.npz','scale-targets.json']:
 (OUT/name).write_bytes((OLD/name).read_bytes())
for name in ['build_mesh.py','groove_regions.py','check_lattice.py','check_final_joints.py','deliver.py','assemble_blender.py','render_alignment.py','finish_package.py']:
 code=(OLD/name).read_text().replace("str(OUT/'lib')","str(OUT.parent/'flexi-shingleback-scale-aligned'/'lib')")
 code=code.replace('flexi-shingleback-scale-aligned.', 'flexi-shingleback-wrapped-sides.').replace('flexi-shingleback-scale-aligned-', 'flexi-shingleback-wrapped-sides-')
 if name=='build_mesh.py':
  code=code.replace('parts=[];report=[]', '''# Continue the existing lower side-scale surface downward and slightly outward.
from wrap_surface import extended_surface
wrapped_source=extended_surface(OUT,md,seeds,active)
wrap_guards=md.Manifold.batch_boolean([md.Manifold.cube((9.8,9.8,6.45)).translate((seeds[j][0]-4.9,seeds[j][1]-4.9,-.1)) for j in active],md.OpType.Add)
parts=[];report=[]''')
  code=code.replace(' obj=md.Manifold.batch_boolean([cap]', ''' if name.startswith('Scale') and outer and abs(seeds[ids[0]][0])>10:
  extension=(wrapped_source^prism)-wrap_guards
  cap=cap+extension
 elif 'leg_fixed' in name:
  root_limit=md.Manifold.cube((57,330,21)).translate((-28.5,-165,0))
  extension=(wrapped_source^prism^root_limit)-wrap_guards
  cap=cap+extension
 obj=md.Manifold.batch_boolean([cap]''')
 if name=='deliver.py':
  code=code.replace("r['dimensions_mm']=full.extents.tolist()",'''# A flank sample contains the actual new covers and their inward neighbors.
seeds=np.array(layout['seeds'])
edge=[m.copy() for n,m in meshes.items() if n.startswith('Scale') and all(seeds[i][0]>8 and abs(seeds[i][1])<13 for i in layout['groups'][n])]
sample=trimesh.util.concatenate(edge);sample.apply_translation(-sample.bounds[0]);sample=clean_stl(sample,len(edge),'side wrap sample')
sample.export(OUT/'side-wrap-test.stl');write3mf(sample,OUT/'side-wrap-test.3mf')
r['side_wrap_sample_shells']=len(edge)
r['dimensions_mm']=full.extents.tolist()''')
 if name=='finish_package.py':
  code=code.replace("report={}","report={}\nside_count=json.loads((OUT/'validation.json').read_text())['side_wrap_sample_shells']")
  code=code.replace("('joint-test-final.stl',13)]", "('joint-test-final.stl',13),('side-wrap-test.stl',side_count)]")
  code=code.replace("'README.md','validation.json'", "'side-wrap-test.stl','side-wrap-test.3mf','belly-side-detail.png','belly-lower-detail.png','side-wrap-validation.json','README.md','validation.json'")
 (OUT/name).write_text(code)
print('Prepared a separate wrapped-side revision; the liked version is preserved.')
