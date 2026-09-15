from pathlib import Path
import sys, json, zipfile, hashlib
OUT=Path(__file__).parent
sys.path.insert(0,str(OUT/'lib'))
import numpy as np
OLD=OUT.parent/'flexi-shingleback-v2'
archive=Path(r'C:\Users\nikil\Downloads\Meshy_AI_shingleback_lizard_v2_0913105224_image-to-3d-texture_obj.zip')
with zipfile.ZipFile(archive) as z:
    member=next(n for n in z.namelist() if n.endswith('.obj'))
    digest=hashlib.sha256(z.read(member)).hexdigest()
assert digest==hashlib.sha256(next((OLD/'reference').glob('*.obj')).read_bytes()).hexdigest()
d=np.load(OLD/'source-print.npz')
np.savez_compressed(OUT/'source-print.npz',vertices=d['vertices']*[1.45/1.3,1.45,1.45],faces=d['faces'])
(OUT/'reference-link.npz').write_bytes((OLD/'reference-link.npz').read_bytes())
# Middle-scale centres picked on the orthographic source render. Coordinates
# use its 235 mm horizontal field of view and original 1100 pixel width.
pixels=np.array([[550,647],[548,621],[550,591],[550,558],[550,524],[550,489],
 [548,456],[553,421],[550,388],[550,353],[550,319],[551,284],[550,250],
 [548,220],[545,190],[537,164],[537,138],[540,111],[539,86],[543,64]],float)
centres=np.column_stack(((pixels[:,0]-550)*235/1100*1.45/1.3,(450-pixels[:,1])*235/1100*1.45))
# Continuous body row -12..12; shorter tail scales use nearest available row.
rows=list(range(-12,14,2))+[14,16,18,20,22,24]
# Last two tail scales share the fixed tip; limit unique central assignments.
centres=np.delete(centres,16,axis=0) # One short tail scale shares a cluster.
mapping={int(r):c.tolist() for r,c in zip(rows,centres)}
(OUT/'scale-targets.json').write_text(json.dumps(dict(source_obj_sha256=digest,sculpt_scale=1.45,joint_x_scale=1.3,centre_targets=mapping),indent=2))
code=(OLD/'build_mesh.py').read_text()
code=code.replace('range(-18,19)','range(-27,28)').replace('range(-4,5)','range(-6,7)')
code=code.replace('x,y=p\n if y<-55','x,y=p/[1.45/1.3,1.45]\n if y<-55')
code=code.replace('regions={}\nfor i,p in enumerate(seeds):', '''# Top cells follow the middle scales independently of the regular lower joints.
target=json.loads((OUT/'scale-targets.json').read_text())['centre_targets']
rr=np.array(sorted(int(k) for k in target))
yy=np.array([target[str(k)][1] for k in rr])
xx=np.array([target[str(k)][0] for k in rr])
top_seeds=seeds.copy()
for k,(x,y) in enumerate(seeds):
 row=y/dy
 if rr.min()<=row<=rr.max():
  top_seeds[k,1]=np.interp(row,rr,yy)
  top_seeds[k,0]+=np.interp(row,rr,xx)*max(0,1-abs(x)/30)
regions={}
for i,p in enumerate(top_seeds):''')
code=code.replace('for j,q in enumerate(seeds):','for j,q in enumerate(top_seeds):')
code=code.replace('[[-60,-110],[60,-110],[60,110],[-60,110]]','[[-90,-165],[90,-165],[90,165],[-90,165]]')
code=code.replace('(140,240,60)','(180,330,80)').replace('(-70,-120,5.75)','(-90,-165,5.75)')
code=code.replace('(140,240,50)','(180,330,80)').replace('(-70,-120,11.95)','(-90,-165,11.95)')
code=code.replace('(-60,-18.8) if side<0 else (18.8,60)','(-90,-18.8*1.45/1.3) if side<0 else (18.8*1.45/1.3,90)')
code=code.replace('[(lo,32),(hi,32),(hi,78),(lo,78)]','[(lo,32*1.45),(hi,32*1.45),(hi,78*1.45),(lo,78*1.45)]')
code=code.replace('dict(seeds=seeds.tolist(),groups=groups)','dict(seeds=seeds.tolist(),top_seeds=top_seeds.tolist(),groups=groups)')
code=code.replace('# Rigid anatomy only needs anchors', "from groove_regions import follow_grooves\nregions=follow_grooves(regions,v,np.load(OUT/'source-print.npz')['faces'],md)\n\n# Rigid anatomy only needs anchors")
code=code.replace(' obj=md.Manifold.batch_boolean([cap]', ''' # A shifted upper cell must never enter another anchor's working envelope.
 otherguards=[md.Manifold.cube((9.8,9.8,6.45)).translate((seeds[j][0]-4.9,seeds[j][1]-4.9,-.1)) for j in active if j not in ids]
 if otherguards:cap=cap-md.Manifold.batch_boolean(otherguards,md.OpType.Add)
 obj=md.Manifold.batch_boolean([cap]''')
(OUT/'build_mesh.py').write_text(code)
(OUT/'check_lattice.py').write_text((OLD/'check_lattice.py').read_text())
print('Prepared 275.5 mm sculpt; widened joint X by 30%; source hash verified.')
