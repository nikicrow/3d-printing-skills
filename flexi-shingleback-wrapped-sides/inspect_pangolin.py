from pathlib import Path
import sys,json
OUT=Path(__file__).parent
sys.path.insert(0,str(OUT.parent/'flexi-shingleback-scale-aligned'/'lib'))
import numpy as np,trimesh
s=trimesh.load(r'C:\Users\nikil\Downloads\FLEXI+PANGOLIN+A1+MINI+BAMBU.3mf')
m=s.to_geometry();v=m.vertices.copy()
_,vec=np.linalg.eigh(np.cov(v[:,:2].T));long=vec[:,-1];across=np.array([long[1],-long[0]])
m.vertices[:,:2]=(v[:,:2]-v[:,:2].mean(0))@np.column_stack((across,long))
m.vertices[:,2]-=m.bounds[0,2]
m.apply_scale(275/m.extents[1]);m.export(OUT/'pangolin-reference.stl')
print('PANGOLIN',m.extents.tolist(),len(m.split()),flush=True)
