"""Snap shared upper-cell edges to local sculpt valleys, preserving shared curves."""
import numpy as np
from scipy.ndimage import gaussian_filter,distance_transform_edt,map_coordinates
def follow_grooves(regions,vertices,faces,md):
 step=.22;lo=vertices[:,:2].min(0)-3;hi=vertices[:,:2].max(0)+3
 shape=np.ceil((hi-lo)/step).astype(int)+1
 h=np.full(shape,-np.inf)
 # Rasterize actual triangles. Vertex-only sampling can mistake sparse top
 # areas for underside valleys and must not be used for seam fitting.
 triangles=vertices[faces];xy=(triangles[:,:,:2]-lo)/step
 ab=xy[:,1]-xy[:,0];ac=xy[:,2]-xy[:,0]
 determinant=ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
 triangles=triangles[determinant>1e-8];xy=xy[determinant>1e-8]
 for start in range(0,len(triangles),5000):
  tr=triangles[start:start+5000];p=xy[start:start+5000]
  minimum=np.ceil(p.min(1)).astype(int);maximum=np.floor(p.max(1)).astype(int)
  size=np.maximum(0,maximum-minimum+1);counts=size.prod(1)
  tri=np.repeat(np.arange(len(tr)),counts)
  if not len(tri):continue
  offset=np.arange(len(tri))-np.repeat(np.cumsum(counts)-counts,counts)
  gx=minimum[tri,0]+offset//size[tri,1];gy=minimum[tri,1]+offset%size[tri,1]
  a=p[tri,0];b=p[tri,1]-a;c=p[tri,2]-a;q=np.column_stack((gx,gy))-a
  det=b[:,0]*c[:,1]-b[:,1]*c[:,0]
  u=(q[:,0]*c[:,1]-q[:,1]*c[:,0])/det;w=(b[:,0]*q[:,1]-b[:,1]*q[:,0])/det
  inside=(u>=-1e-8)&(w>=-1e-8)&(u+w<=1+1e-8)
  z=tr[tri,0,2]+u*(tr[tri,1,2]-tr[tri,0,2])+w*(tr[tri,2,2]-tr[tri,0,2])
  np.maximum.at(h,(gx[inside],gy[inside]),z[inside])
 missing=~np.isfinite(h);nearest=distance_transform_edt(missing,return_distances=False,return_indices=True)
 h[missing]=h[tuple(nearest[:,missing])]
 smooth=gaussian_filter(h,.4/step);residual=smooth-gaussian_filter(smooth,2.0/step)
 def value(p):
  return map_coordinates(residual,((np.asarray(p)-lo)/step).T,order=1,mode='nearest')
 def enabled(p):return abs(p[0])<25 and -75<p[1]<118
 def key(p):return tuple(np.round(p,5))
 corners={};curves={};scores=[]
 def corner(p):
  k=key(p)
  if k not in corners:
   if enabled(p):
    offsets=np.array([(x,y) for x in np.arange(-1.1,1.101,.22) for y in np.arange(-1.1,1.101,.22) if x*x+y*y<1.22])
    score=value(p+offsets)+.32*np.sum(offsets**2,axis=1)
    corners[k]=p+offsets[np.argmin(score)]
   else:corners[k]=p
  return corners[k]
 def curve(a,b):
  ka,kb=key(a),key(b);reverse=ka>kb
  if reverse:a,b=b,a;ka,kb=kb,ka
  k=(ka,kb)
  if k not in curves:
   aa,bb=corner(a),corner(b);length=np.linalg.norm(bb-aa)
   if length<1e-5:return np.array([aa,bb])
   count=max(2,int(np.ceil(length/.6))+1);t=np.linspace(0,1,count)
   line=aa[None,:]+t[:,None]*(bb-aa);normal=np.array([-(bb-aa)[1],(bb-aa)[0]])/length
   if enabled((a+b)/2) and length<20:
    offsets=np.arange(-1.1,1.101,.11);points=line[:,None,:]+offsets[None,:,None]*normal
    costs=value(points.reshape(-1,2)).reshape(count,-1)+.3*offsets[None,:]**2
    zero=int(np.argmin(abs(offsets)));costs[0,:]=1e6;costs[0,zero]=0;costs[-1,:]=1e6;costs[-1,zero]=0
    previous=np.zeros(costs.shape,int);total=costs[0].copy()
    for i in range(1,count):
     transition=total[:,None]+1.3*(offsets[:,None]-offsets[None,:])**2
     previous[i]=transition.argmin(axis=0);total=costs[i]+transition.min(axis=0)
    path=[int(total.argmin())]
    for i in range(count-1,0,-1):path.append(int(previous[i,path[-1]]))
    path=path[::-1];line=points[np.arange(count),path];line[0]=aa;line[-1]=bb
    original=a[None,:]+t[:,None]*(b-a)
    scores.append([float(np.mean(value(original))),float(np.mean(value(line)))])
   curves[k]=line
  return curves[k][::-1] if reverse else curves[k]
 result={}
 for i,region in regions.items():
  poly=np.array(region.to_polygons()[0]);points=[]
  for a,b in zip(poly,np.roll(poly,-1,axis=0)):points.extend(curve(a,b)[:-1])
  result[i]=md.CrossSection([np.array(points)])
 import json
 from pathlib import Path
 means=np.mean(scores,axis=0)
 (Path(__file__).parent/'groove-fit.json').write_text(json.dumps(dict(adjusted_shared_edges=len(scores),mean_surface_residual_before_mm=float(means[0]),mean_surface_residual_after_mm=float(means[1]),note='Lower residual means a lower local groove relative to the smoothed sculpt; not a percentage of perfectly matched scales.'),indent=2))
 print('GROOVE_FOLLOWING',len(curves),'shared edges',flush=True)
 return result
