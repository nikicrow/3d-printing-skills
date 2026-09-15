from pathlib import Path
import sys,json,zipfile
OUT=Path(__file__).parent;sys.path.insert(0,str(OUT/'lib'))
import trimesh
report={}
for name,expected in [('flexi-shingleback-scale-aligned.stl',133),('flexi-shingleback-scale-aligned-256mm-bed.stl',133),('joint-test-final.stl',13)]:
 mesh=trimesh.load_mesh(OUT/name,process=True);shells=mesh.split(only_watertight=False)
 assert mesh.is_watertight and mesh.is_winding_consistent and len(shells)==expected,(name,len(shells))
 assert all(s.volume>0 for s in shells)
 report[name]=dict(watertight=True,consistent_winding=True,shells=len(shells),dimensions_mm=mesh.extents.tolist())
(OUT/'scale-joint-test.stl').write_bytes((OUT/'joint-test-final.stl').read_bytes())
(OUT/'export-validation.json').write_text(json.dumps(report,indent=2))
files=['flexi-shingleback-scale-aligned.3mf','flexi-shingleback-scale-aligned.stl','flexi-shingleback-scale-aligned-256mm-bed.stl','scale-joint-test.stl','joint-test.3mf','README.md','validation.json','lattice-validation.json','groove-fit.json','export-validation.json','shingleback-preview.png','shingleback-top.png','shingleback-underside.png','middle-scale-detail.png','scale-alignment-map.png']
if (OUT/'final-lattice-validation.json').exists():files.append('final-lattice-validation.json')
with zipfile.ZipFile(OUT/'flexi-shingleback-scale-aligned-print-package.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for name in files:z.write(OUT/name,name)
print(json.dumps(report),flush=True)
