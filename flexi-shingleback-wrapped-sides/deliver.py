from pathlib import Path
import sys,json,zipfile,xml.etree.ElementTree as ET
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT.parent/'flexi-shingleback-scale-aligned'/'lib'))
import numpy as np,trimesh,manifold3d as md,io
r=json.loads((OUT/'validation.json').read_text());layout=json.loads((OUT/'layout.json').read_text())
lattice=json.loads((OUT/'lattice-validation.json').read_text())
assert not r['collisions'] and lattice['complete_network'] and not lattice['missing_joint_quarters']
(OUT/'print-parts').mkdir(exist_ok=True)
def clean_stl(m,expected,label):
 # Validate float32 STL coordinates after the final affine transform too.
 original=m.copy()
 for tolerance in [0,.005,.01,.02]:
  if tolerance:
   solid=md.Manifold(md.Mesh(original.vertices.astype(np.float32),original.faces.astype(np.uint32))).simplify(tolerance)
   raw=solid.to_mesh();m=trimesh.Trimesh(raw.vert_properties[:,:3],raw.tri_verts,process=False)
  m=trimesh.load_mesh(io.BytesIO(m.export(file_type='stl')),file_type='stl',process=True)
  ff=m.faces;m.update_faces((ff[:,0]!=ff[:,1])&(ff[:,1]!=ff[:,2])&(ff[:,0]!=ff[:,2]))
  _,inverse,counts=np.unique(np.sort(m.faces,axis=1),axis=0,return_inverse=True,return_counts=True)
  m.update_faces(counts[inverse]==1);m.remove_unreferenced_vertices()
  if m.is_watertight and m.is_winding_consistent and len(m.split(only_watertight=False))==expected:break
 assert m.is_watertight and m.is_winding_consistent and len(m.split(only_watertight=False))==expected,label
 return m
meshes={}
for n in layout['groups']:
 m=trimesh.load_mesh(OUT/'parts'/(n+'.stl'),process=True)
 m.apply_scale([1.3,1,1]);m=clean_stl(m,1,n)
 m.export(OUT/'print-parts'/(n+'.stl'));meshes[n]=m
full=trimesh.util.concatenate(list(meshes.values()));full.export(OUT/'flexi-shingleback-wrapped-sides.stl')
plate=full.copy();plate.apply_transform(trimesh.transformations.rotation_matrix(np.pi/4,[0,0,1]));plate.apply_translation([128-plate.bounds[:,0].mean(),128-plate.bounds[:,1].mean(),-plate.bounds[0,2]])
plate=clean_stl(plate,len(meshes),'bed assembly')
assert np.all(plate.bounds[0,:2]>0) and np.all(plate.bounds[1,:2]<256)
def write3mf(m,path):
 s=trimesh.Scene();s.add_geometry(m,geom_name=path.stem,node_name=path.stem);path.write_bytes(trimesh.exchange.threemf.export_3MF(s))
 with zipfile.ZipFile(path) as z:
  d=ET.fromstring(z.read('3D/3dmodel.model'));assert d.get('unit')=='millimeter' and len(d.findall('{*}build/{*}item'))==1
write3mf(plate,OUT/'flexi-shingleback-wrapped-sides.3mf')
plate.export(OUT/'flexi-shingleback-wrapped-sides-256mm-bed.stl')
for name in ['joint-test']:
 seeds=np.array(layout['seeds'])
 selected=[m.copy() for n,m in meshes.items() if n.startswith('Scale') and all(abs(seeds[i][0])<11 and abs(seeds[i][1])<11 for i in layout['groups'][n])]
 m=trimesh.util.concatenate(selected);m.apply_translation(-m.bounds[0]);m=clean_stl(m,len(selected),'joint sample');m.export(OUT/(name+'-final.stl'));write3mf(m,OUT/(name+'.3mf'))
# A flank sample contains the actual new covers and their inward neighbors.
seeds=np.array(layout['seeds'])
edge=[m.copy() for n,m in meshes.items() if n.startswith('Scale') and all(seeds[i][0]>8 and abs(seeds[i][1])<13 for i in layout['groups'][n])]
sample=trimesh.util.concatenate(edge);sample.apply_translation(-sample.bounds[0]);sample=clean_stl(sample,len(edge),'side wrap sample')
sample.export(OUT/'side-wrap-test.stl');write3mf(sample,OUT/'side-wrap-test.3mf')
r['side_wrap_sample_shells']=len(edge)
r['dimensions_mm']=full.extents.tolist();r['sculpt_uniform_scale_vs_v2']=1.45;r['joint_xy_scale_vs_reference']=[1.3,1]
r['min_gap_mm_before_x_stretch']=r.pop('min_gap_mm',r.get('min_gap_mm_before_x_stretch'));r['min_gap_mm_lower_bound']=r['min_gap_mm_before_x_stretch']
r['plate_footprint_mm']=plate.extents[:2].tolist();r['plate_bounds_mm']=plate.bounds.tolist();r['part_checks_normalized_coordinates']=r.pop('part_checks',r.get('part_checks_normalized_coordinates'))
r['joint']='Recovered pangolin mechanism, widened 30% in X, original Y/Z dimensions; static reference network verified before affine X stretch'
r['source']='SHA256-verified supplied Meshy v2 OBJ; existing 0.22 mm voxel repair uniformly enlarged 145%'
(OUT/'validation.json').write_text(json.dumps(r,indent=2));print(json.dumps({k:v for k,v in r.items() if k not in ['near_pairs','part_checks_normalized_coordinates']}),flush=True)
code=(OUT.parent/'flexi-shingleback-v2'/'assemble_blender.py').read_text().replace("OUT/'parts'","OUT/'print-parts'")
code=code.replace('225','330').replace('245','355').replace('220','320').replace('235','340').replace('view_distance=230','view_distance=340')
code=code.replace('flexi-shingleback-v2.blend','flexi-shingleback-wrapped-sides.blend').replace('[5.2277,5.0736]','[6.79601,5.0736]')
(OUT/'assemble_blender.py').write_text(code)
