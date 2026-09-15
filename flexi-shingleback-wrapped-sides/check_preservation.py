from pathlib import Path
import sys,json
OUT=Path(__file__).parent;OLD=OUT.parent/'flexi-shingleback-scale-aligned'
sys.path.insert(0,str(OLD/'lib'))
import numpy as np,trimesh,manifold3d as md
def load(path):
 t=trimesh.load_mesh(path,process=True)
 return md.Manifold(md.Mesh(t.vertices.astype(np.float32),t.faces.astype(np.uint32)))
upper=md.Manifold.cube((180,330,80)).translate((-90,-165,20.02))
rows=[];checks=[]
for path in sorted((OUT/'parts').glob('*.stl')):
 before=load(OLD/'parts'/path.name);after=load(path)
 added=(after-before).volume();removed=(before-after).volume()
 top=((after^upper)-(before^upper)).volume()+((before^upper)-(after^upper)).volume()
 # Boolean retriangulation / 0.005 mm simplification causes tiny surface
 # differences; allow 0.2 cubic mm per piece rather than require identical faces.
 assert top<.2 and removed<.2,(path.name,removed,top)
 checks.append([removed,top])
 if added>.2:rows.append(dict(piece=path.stem,added_volume_mm3_normalized=added,removed_volume_mm3_normalized=removed,upper_difference_mm3_normalized=top))
report=dict(extended_pieces=len(rows),dorsal_geometry_above_mm=20.02,dorsal_preserved_within_export_tolerance=True,original_piece_geometry_preserved_within_export_tolerance=True,max_removed_volume_mm3=max(c[0] for c in checks)*1.3,max_dorsal_difference_mm3=max(c[1] for c in checks)*1.3,added_volume_mm3=sum(r['added_volume_mm3_normalized'] for r in rows)*1.3,pieces=rows)
(OUT/'side-wrap-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps({k:v for k,v in report.items() if k!='pieces'}),flush=True)
