"""Preserve the pangolin link; partition the supplied lizard into independent tops."""
from pathlib import Path
import sys,json,math
OUT=Path(__file__).parent
sys.path.insert(0,str(OUT/'lib'))
import numpy as np, manifold3d as md, trimesh
from scipy.spatial import cKDTree

def load(name):
 d=np.load(OUT/name);return md.Manifold(md.Mesh(d['vertices'].astype(np.float32),d['faces'].astype(np.uint32)))
source=load('source-print.npz');base=load('reference-link.npz')
print('INPUT',source.status(),source.volume(),base.status(),flush=True)
assert source.volume()>0 and base.volume()>0
v=np.load(OUT/'source-print.npz')['vertices']
dx,dy=5.2277,5.0736
seeds=[]
for row in range(-18,19):
 y=row*dy
 band=v[(abs(v[:,1]-y)<2.5)&(v[:,2]>12)]
 if len(band)==0:continue
 width=max(abs(band[:,0]))
 for col in range(-4,5):
  if (col-row)%2:continue
  x=col*dx
  if abs(x)<max(2,width-3.0):seeds.append((x,y))
seeds=np.array(seeds)

def clip(poly,n,d):
 out=[]
 for a,b in zip(poly,np.roll(poly,-1,axis=0)):
  da,db=np.dot(a,n)-d,np.dot(b,n)-d
  if da<=1e-9:out.append(a)
  if (da<0)!=(db<0):out.append(a+(b-a)*da/(da-db))
 return np.array(out)

def group(i,p):
 x,y=p
 if y<-55:return 'Head_fixed'
 if y>81:return 'Tail_tip_fixed'
 if abs(x)>14 and -55<y<-25:return ('Left' if x<0 else 'Right')+'_foreleg_fixed'
 if abs(x)>9 and 40<y<72:return ('Left' if x<0 else 'Right')+'_hindleg_fixed'
 return f'Scale_link_{i:03d}'
groups={}
for i,p in enumerate(seeds):groups.setdefault(group(i,p),[]).append(i)
regions={}
for i,p in enumerate(seeds):
 poly=np.array([[-60,-110],[60,-110],[60,110],[-60,110]],float)
 for j,q in enumerate(seeds):
  if i!=j:poly=clip(poly,q-p,(np.dot(q,q)-np.dot(p,p))/2)
 regions[i]=md.CrossSection([poly])

# Rigid anatomy only needs anchors at its boundary with the moving sheet.
anchors={}
for name,ids in groups.items():
 others=[j for j in range(len(seeds)) if j not in ids]
 anchors[name]=[i for i in ids if 'fixed' not in name or any(np.linalg.norm(seeds[i]-seeds[j])<7.5 for j in others)]
active={i for ids in anchors.values() for i in ids}
placed={}
for i in active:
 x,y=seeds[i]
 # Keep full original geometry toward every linked neighbour; remove only unused outer arms.
 mask=md.Manifold.cylinder(7,2.6,2.6,32)
 for sx in (-1,1):
  for sy in (-1,1):
   if any(np.linalg.norm(seeds[j]-(seeds[i]+[sx*dx,sy*dy]))<.03 for j in active):
    mask=mask+md.Manifold.cube((5,5,7)).translate((0 if sx>0 else -5,0 if sy>0 else -5,0))
 placed[i]=(base^mask).translate((x,y,0))
upper=md.Manifold.cube((140,240,60)).translate((-70,-120,5.75))
keepouts=[md.Manifold.cube((9.12,9.12,6.1)).translate((seeds[i][0]-4.56,seeds[i][1]-4.56,-.1)) for i in active]
keepout=md.Manifold.batch_boolean(keepouts,md.OpType.Add)
# Keep the natural flank everywhere except the working joint quadrants.
working=[]
for i in active:
 x,y=seeds[i]
 for sx in [-1,1]:
  for sy in [-1,1]:
   if any(np.linalg.norm(seeds[j]-(seeds[i]+[sx*dx,sy*dy]))<.03 for j in active):
    working.append(md.Manifold.cube((4.58,4.58,5.85)).translate((x-.02 if sx>0 else x-4.56,y-.02 if sy>0 else y-4.56,-.1)))
protect=md.Manifold.batch_boolean(working,md.OpType.Add)
parts=[];report=[]
(OUT/'parts').mkdir(exist_ok=True)
for name,ids in groups.items():
 region=regions[ids[0]]
 for i in ids[1:]:region=region+regions[i]
 region=region.offset(-.35)
 prism=region.extrude(50)
 sculpt=source^prism
 cap=sculpt^upper
 if 'fixed' in name:
  # Flat underside beneath the rigid head/feet/tail, avoiding all active joints.
  contact=sculpt.slice(.8)
  underside=contact.extrude(.85) if contact.area()>1e-6 else md.Manifold()
  rigid=sculpt+underside if contact.area()>1e-6 else sculpt
  # One subtraction avoids unioning coincident copies of the sculpt surface.
  otherguards=[keepouts[list(active).index(j)] for j in active if j not in ids]
  guard=md.Manifold.batch_boolean(otherguards,md.OpType.Add) if otherguards else md.Manifold()
  cap=rigid-(guard-upper)
 else:
  x,y=seeds[ids[0]]
  stem=md.CrossSection([[(2.7,0),(0,2.7),(-2.7,0),(0,-2.7)]]).extrude(6.3,scale_top=(2.1,2.1)).translate((x,y,5.7))
  crown=md.Manifold.cube((140,240,50)).translate((-70,-120,11.95))
  cap=cap^(stem+crown)
  outer=any(not any(np.linalg.norm(seeds[j]-(seeds[ids[0]]+[sx*dx,sy*dy]))<.03 for j in active) for sx in [-1,1] for sy in [-1,1])
  if outer:cap=sculpt-protect
 obj=md.Manifold.batch_boolean([cap]+[placed[i] for i in anchors[name]],md.OpType.Add)
 components=obj.decompose()
 big=[c for c in components if c.volume()>.3]
 if len(big)>1:
  print('DISCONNECTED',name,[round(c.volume(),3) for c in big],flush=True)
 obj=max(components,key=lambda c:c.volume())
 if 'leg_fixed' in name:
  # Strengthen small toe islands instead of dropping their source geometry.
  for c in components:
   if c.volume()<.3 or c.volume()==obj.volume():continue
   if c.volume()>obj.volume()/2:continue
   a=obj.to_mesh().vert_properties[:,:3];b=c.to_mesh().vert_properties[:,:3]
   distances,indices=cKDTree(a).query(b);k=int(np.argmin(distances));p,q=a[indices[k]],b[k]
   assert distances[k]<3,'Toe attachment unexpectedly distant'
   bridge=md.Manifold.batch_hull([md.Manifold.sphere(.7,16).translate(p),md.Manifold.sphere(.7,16).translate(q)])
   obj=obj+c+bridge
 obj=obj.simplify(.005)
 mesh=obj.to_mesh();tm=trimesh.Trimesh(mesh.vert_properties[:,:3],mesh.tri_verts,process=False)
 assert obj.volume()>0 and len(tm.faces)>0,(name,obj.status())
 tm.export(OUT/'parts'/f'{name}.stl')
 reload=trimesh.load_mesh(OUT/'parts'/f'{name}.stl',process=True)
 # STL float32 can collapse boolean slivers into zero-edge faces and opposing fins.
 ff=reload.faces
 reload.update_faces((ff[:,0]!=ff[:,1])&(ff[:,1]!=ff[:,2])&(ff[:,0]!=ff[:,2]))
 _,inverse,counts=np.unique(np.sort(reload.faces,axis=1),axis=0,return_inverse=True,return_counts=True)
 reload.update_faces(counts[inverse]==1)
 reload.remove_unreferenced_vertices()
 if not reload.is_watertight:
  import io
  for tol in [.01,.02,.04]:
   clean=obj.simplify(tol).to_mesh()
   trial=trimesh.Trimesh(clean.vert_properties[:,:3],clean.tri_verts,process=False)
   reload=trimesh.load_mesh(io.BytesIO(trial.export(file_type='stl')),file_type='stl',process=True)
   ff=reload.faces;reload.update_faces((ff[:,0]!=ff[:,1])&(ff[:,1]!=ff[:,2])&(ff[:,0]!=ff[:,2]))
   _,inverse,counts=np.unique(np.sort(reload.faces,axis=1),axis=0,return_inverse=True,return_counts=True);reload.update_faces(counts[inverse]==1);reload.remove_unreferenced_vertices()
   if reload.is_watertight:break
 if not reload.is_watertight:
  shells=reload.split(only_watertight=False)
  print('REPAIR',name,[(len(c.faces),c.volume,c.is_watertight) for c in shells],flush=True)
  reload=max(shells,key=lambda c:abs(c.volume));reload.fill_holes()
  if not reload.is_watertight:
   counts=np.bincount(reload.edges_unique_inverse)
   edges=reload.edges_unique[counts==1]
   print('BOUNDARY',reload.vertices[np.unique(edges)].tolist(),flush=True)
 assert reload.is_watertight,(name,'STL precision issue')
 tm=reload;tm.export(OUT/'parts'/f'{name}.stl')
 obj=md.Manifold(md.Mesh(tm.vertices.astype(np.float32),tm.faces.astype(np.uint32)))
 assert obj.status()==md.Error.NoError,(name,obj.status())
 parts.append((name,obj,tm,ids))
 report.append(dict(name=name,links=len(anchors[name]),volume_mm3=obj.volume(),watertight=bool(tm.is_watertight),discarded_volume_mm3=max(0,sum(c.volume() for c in components)-obj.volume())))
 print('BUILT',name,round(obj.volume(),1),flush=True)

collisions=[];near=[]
for a,(na,ma,ta,ia) in enumerate(parts):
 for nb,mb,tb,ib in parts[a+1:]:
  if np.any(ta.bounds[0]>tb.bounds[1]+1) or np.any(tb.bounds[0]>ta.bounds[1]+1):continue
  overlap=(ma^mb).volume()
  if overlap>1e-5:collisions.append([na,nb,overlap])
  gap=ma.min_gap(mb,1.0)
  if gap<1:near.append([na,nb,gap])
full=trimesh.util.concatenate([p[2] for p in parts]);full.export(OUT/'flexi-shingleback.stl')
scene=trimesh.Scene()
for name,m,t,ids in parts:scene.add_geometry(t,node_name=name,geom_name=name)
(OUT/'flexi-shingleback.3mf').write_bytes(trimesh.exchange.threemf.export_3MF(scene))
sample=[p[2].copy() for p in parts if p[0].startswith('Scale') and all(abs(seeds[i][0])<11 and abs(seeds[i][1])<11 for i in p[3])]
samplemesh=trimesh.util.concatenate(sample);samplemesh.export(OUT/'joint-test.stl')
summary=dict(dimensions_mm=full.extents.tolist(),parts=len(parts),link_count=len(active),upper_seam_mm=.7,collisions=collisions,min_gap_mm=min([r[2] for r in near],default=None),near_pairs=near,part_checks=report,source='User supplied Meshy OBJ, voxel-repaired at 0.22mm',joint='Actual pangolin central component 2 cropped at reference Z=6mm; original XY and Z scale retained; unused perimeter arms trimmed')
(OUT/'validation.json').write_text(json.dumps(summary,indent=2))
(OUT/'layout.json').write_text(json.dumps(dict(seeds=seeds.tolist(),groups=groups),indent=2))
print('RESULT',json.dumps({k:v for k,v in summary.items() if k not in ['near_pairs','part_checks']}),flush=True)


