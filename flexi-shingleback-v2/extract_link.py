from pathlib import Path
import sys,json
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT/'lib'))
import numpy as np,trimesh,manifold3d as md
s=trimesh.load(r'C:\Users\nikil\Downloads\FLEXI+PANGOLIN+A1+MINI+BAMBU.3mf')
print('TRANSFORMS',s.graph.to_flattened(),flush=True)
m=next(iter(s.geometry.values())).copy()
cs=m.split();print('raw components',[(i,c.bounds.tolist()) for i,c in enumerate(cs[:6])],flush=True)
# Profile transform is a uniform scale and plate rotation. Retain scale, discard plate pose.
T=s.graph[s.graph.nodes_geometry[0]][0];scale=np.linalg.norm(T[:3,0]);print('SCALE',scale,flush=True)
for c in cs:c.apply_scale([scale,scale,T[2,2]]);c.apply_translation([0,0,-m.bounds[0,2]*T[2,2]])
candidates=[c for c in cs if abs(c.centroid[0])<3 and 10<c.centroid[2]<30]
print('CANDIDATES',[(c.bounds.tolist(),c.centroid.tolist()) for c in candidates],flush=True)
c=min(candidates,key=lambda c:abs(c.bounds[0,1]+38.09565))
base=md.Manifold(md.Mesh(c.vertices.astype(np.float32),c.faces.astype(np.uint32)))
base=base^md.Manifold.cube((300,300,6)).translate((-150,-150,0))
v=base.to_mesh().vert_properties[:,:3].copy();f=base.to_mesh().tri_verts
v[:,:2]-=(v.min(0)[:2]+v.max(0)[:2])/2;v[:,2]-=v[:,2].min()
np.savez_compressed(OUT/'reference-link.npz',vertices=v,faces=f)
print('EXTRACTED',v.min(0),v.max(0),base.volume(),flush=True)

