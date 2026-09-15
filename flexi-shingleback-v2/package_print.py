from pathlib import Path
import sys,json,zipfile,xml.etree.ElementTree as ET
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT/'lib'))
import numpy as np,trimesh
r=json.loads((OUT/'validation.json').read_text());layout=json.loads((OUT/'layout.json').read_text())
assert not r['collisions']
for p in (OUT/'parts').glob('*.stl'):
 if p.stem not in layout['groups']:p.unlink()
meshes={n:trimesh.load_mesh(OUT/'parts'/(n+'.stl'),process=True) for n in layout['groups']}
assert all(m.is_watertight and m.is_winding_consistent and len(m.split())==1 and m.volume>0 for m in meshes.values())
full=trimesh.util.concatenate(list(meshes.values()));full.export(OUT/'flexi-shingleback-v2.stl')
plate=full.copy();plate.apply_transform(trimesh.transformations.rotation_matrix(np.pi/4,[0,0,1]));plate.apply_translation([90-plate.bounds[:,0].mean(),90-plate.bounds[:,1].mean(),-plate.bounds[0,2]])
assert np.all(plate.bounds[0,:2]>0) and np.all(plate.bounds[1,:2]<180)
def write3mf(mesh,path):
 scene=trimesh.Scene();scene.add_geometry(mesh,geom_name=path.stem,node_name=path.stem)
 path.write_bytes(trimesh.exchange.threemf.export_3MF(scene))
 with zipfile.ZipFile(path) as z:
  doc=ET.fromstring(z.read('3D/3dmodel.model'));assert doc.get('unit')=='millimeter' and len(doc.findall('{*}build/{*}item'))==1
write3mf(plate,OUT/'flexi-shingleback-v2.3mf');plate.export(OUT/'flexi-shingleback-v2-A1-mini.stl')
sample=trimesh.load_mesh(OUT/'joint-test.stl',process=True);sample.apply_translation(-sample.bounds[0]);write3mf(sample,OUT/'joint-test.3mf')
seeds=np.array(layout['seeds'])
edge=[m for n,m in meshes.items() if n.startswith('Scale') and all(-11<seeds[i][1]<11 and seeds[i][0]>4 for i in layout['groups'][n])]
edge=trimesh.util.concatenate(edge);edge.export(OUT/'side-edge-test.stl');edge.apply_translation(-edge.bounds[0]);write3mf(edge,OUT/'side-edge-test.3mf')
r['export_checks']=dict(watertight_parts=len(meshes),single_shell_per_part=True,consistent_winding=True,assembly_build_items=1,unit='millimeter',plate_bounds_mm=plate.bounds.tolist(),plate_footprint_mm=plate.extents[:2].tolist(),sample_shells=len(sample.split()))
(OUT/'validation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r['export_checks']),flush=True)
