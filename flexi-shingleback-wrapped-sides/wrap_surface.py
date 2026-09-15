import numpy as np
from scipy.ndimage import maximum_filter1d,gaussian_filter1d
def smooth(t):
 t=np.clip(t,0,1);return t*t*(3-2*t)
def extended_surface(out,md,seeds,active):
 data=np.load(out/'source-print.npz');v=data['vertices'].copy()
 # Smoothly continue the sculpt's existing small lower scales. Above 20 mm
 # the deformation is exactly zero, preserving the accepted dorsal design.
 lower=smooth((20-v[:,2])/20)
 along=smooth((v[:,1]+82)/24)*smooth((125-v[:,1])/24)
 w=lower*along
 # Match the lower silhouette to the actual outside joint envelope. A fixed
 # scale factor under-covered narrower areas near the leg roots.
 ys=np.arange(-140,141,.5);profiles={}
 body_seeds=np.array([seeds[i] for i in active if abs(seeds[i][0])<23])
 desired=np.array([max([abs(x)+4.9+1.8 for x,sy in body_seeds if abs(sy-y)<5.4],default=0) for y in ys])
 desired=gaussian_filter1d(maximum_filter1d(desired,size=9),2)
 for side in [-1,1]:
  band=v[(v[:,0]*side>5)&(abs(v[:,0])<31)&(abs(v[:,2]-5)<.8)]
  width=np.array([max(abs(band[abs(band[:,1]-y)<1,0]),default=np.nan) for y in ys])
  good=np.isfinite(width);width=np.interp(ys,ys[good],width[good]);width=gaussian_filter1d(width,2)
  amplitude=np.clip((desired/np.maximum(width,10)-1)/.78,.16,.55)
  profiles[side]=amplitude
  mask=v[:,0]*side>0
  v[mask,0]*=1+np.interp(v[mask,1],ys,amplitude)*w[mask]
 v[:,2]-=7.5*w
 obj=md.Manifold(md.Mesh(v.astype(np.float32),data['faces'].astype(np.uint32)))
 assert obj.status()==md.Error.NoError
 obj=obj^md.Manifold.cube((180,330,80)).translate((-90,-165,0))
 print('WRAP_SURFACE',obj.status(),obj.volume(),flush=True)
 return obj
