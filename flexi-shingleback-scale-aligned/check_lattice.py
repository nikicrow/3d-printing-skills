from pathlib import Path
import json
ROOT=Path(__file__).parent
exec((ROOT/'build_mesh.py').read_text().split('parts=[];report=[]')[0])
actual={}
for name in groups:
 t=trimesh.load_mesh(ROOT/'parts'/(name+'.stl'),process=True)
 assert t.is_watertight and t.is_winding_consistent and len(t.split())==1,name
 actual[name]=md.Manifold(md.Mesh(t.vertices.astype(np.float32),t.faces.astype(np.uint32)))
owner={i:n for n,ids in groups.items() for i in ids}
edges=[];missing=[]
for i in active:
 for j in active:
  if i>=j or owner[i]==owner[j]:continue
  delta=seeds[j]-seeds[i]
  if abs(abs(delta[0])-dx)>.03 or abs(abs(delta[1])-dy)>.03:continue
  intact=True
  for a,b in [(i,j),(j,i)]:
   x,y=seeds[a];sx,sy=np.sign(seeds[b]-seeds[a])
   quarter=md.Manifold.cube((5.01,5.01,5.75)).translate((x if sx>0 else x-5.01,y if sy>0 else y-5.01,0))
   expected=placed[a]^quarter;loss=(expected-actual[owner[a]]).volume()
   if loss>.015:missing.append([owner[a],int(a),int(b),loss]);intact=False
  if intact:edges.append([owner[i],owner[j]])
seen={next(iter(groups))}
while True:
 new=seen|{b for a,b in edges if a in seen}|{a for a,b in edges if b in seen}
 if new==seen:break
 seen=new
r=dict(connected_parts=len(seen),total_parts=len(groups),complete_network=len(seen)==len(groups),intact_neighbor_links=len(edges),missing_joint_quarters=missing)
(ROOT/'lattice-validation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r),flush=True)
assert r['complete_network'] and not missing
