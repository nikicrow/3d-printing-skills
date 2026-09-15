"""Preserve the pangolin link; partition the supplied lizard into independent tops."""
from pathlib import Path
import sys,json,math
OUT=Path(__file__).parent
sys.path.insert(0,str(OUT/'lib'))
import numpy as np, manifold3d as md, trimesh

def load(name):
 d=np.load(OUT/name);return md.Manifold(md.Mesh(d['vertices'].astype(np.float32),d['faces'].astype(np.uint32)))
source=load('source-print.npz');base=load('reference-link.npz')
print('INPUT',source.status(),source.volume(),base.status(),flush=True)
assert source.volume()>0 and base.volume()>0
v=np.load(OUT/'source-print.npz')['vertices']
dx,dy=5.2277,5.0736
seeds=[]
for row in range(-17,18):
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
 if y<-60:return 'Head_fixed'
 if y>76:return 'Tail_tip_fixed'
 if abs(x)>14 and -60<y<-30:return ('Left' if x<0 else 'Right')+'_foreleg_fixed'
 if abs(x)>9 and 32<y<57:return ('Left' if x<0 else 'Right')+'_hindleg_fixed'
 return f'Scale_link_{i:03d}'
groups={}
for i,p in enumerate(seeds):groups.setdefault(group(i,p),[]).append(i)
regions={}
for i,p in enumerate(seeds):
 poly=np.array([[-60,-110],[60,-110],[60,110],[-60,110]],float)
 for j,q in enumerate(seeds):
  if i!=j:poly=clip(poly,q-p,(np.dot(q,q)-np.dot(p,p))/2)
 regions[i]=md.CrossSection([poly])

# Preserve ~0.7mm upper-surface seams independently of the original joint gap.
placed=[base.translate((x,y,0)) for x,y in seeds]
upper=md.Manifold.cube((140,240,60)).translate((-70,-120,5.75))
keepouts=[md.Manifold.cube((9.12,9.12,6.1)).translate((x-4.56,y-4.56,-.1)) for x,y in seeds]
keepout=md.Manifold.batch_boolean(keepouts,md.OpType.Add)
parts=[];report=[]
(OUT/'parts').mkdir(exist_ok=True)
for name,ids in groups.items():
 region=regions[ids[0]]
 for i in ids[1:]:region=region+regions[i]
 region=region.offset(-.35)
 prism=region.extrude(50)
 sculpt=source^prism
 cap=sculpt^upper
 if 'fixed' in name:cap=cap+(sculpt-keepout)
 obj=md.Manifold.batch_boolean([cap]+[placed[i] for i in ids],md.OpType.Add)
 components=obj.decompose()
 big=[c for c in components if c.volume()>.3]
 if len(big)>1:
  print('DISCONNECTED',name,[round(c.volume(),3) for c in big],flush=True)
 obj=max(components,key=lambda c:c.volume())
 mesh=obj.to_mesh();tm=trimesh.Trimesh(mesh.vert_properties[:,:3],mesh.tri_verts,process=False)
 tm.export(OUT/'parts'/f'{name}.stl')
 parts.append((name,obj,tm,ids))
 report.append(dict(name=name,links=len(ids),volume_mm3=obj.volume(),watertight=bool(tm.is_watertight),discarded_volume_mm3=sum(c.volume() for c in components)-obj.volume()))
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
summary=dict(dimensions_mm=full.extents.tolist(),parts=len(parts),link_count=len(seeds),upper_seam_mm=.7,collisions=collisions,min_gap_mm=min([r[2] for r in near],default=None),near_pairs=near,part_checks=report,source='User supplied Meshy OBJ, voxel-repaired at 0.22mm',joint='Actual pangolin central component 2 cropped at reference Z=6mm; original XY and Z scale retained')
(OUT/'validation.json').write_text(json.dumps(summary,indent=2))
(OUT/'layout.json').write_text(json.dumps(dict(seeds=seeds.tolist(),groups=groups),indent=2))
print('RESULT',json.dumps({k:v for k,v in summary.items() if k not in ['near_pairs','part_checks']}),flush=True)
