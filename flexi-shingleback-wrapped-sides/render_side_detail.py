import bpy,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'flexi-shingleback-wrapped-sides.blend'))
s=bpy.context.scene;cam=s.camera
s.render.resolution_x=1600;s.render.resolution_y=900
for name,location,target,scale in [('belly-side-detail',(250,0,16),(0,0,16),135),('belly-lower-detail',(230,-90,-90),(0,0,12),130)]:
 cam.location=location;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
# Inspection pass: color actual lower joint faces red; external scale covers stay brown.
layout=json.loads((OUT/'layout.json').read_text());seeds=layout['seeds']
red=bpy.data.materials.new('Joint inspection');red.diffuse_color=(1,.03,.01,1)
for o in [o for o in bpy.data.objects if o.type=='MESH']:
 o.data.materials.append(red);index=len(o.data.materials)-1
 for face in o.data.polygons:
  if max(o.data.vertices[i].co.z for i in face.vertices)>6.05:continue
  p=face.center
  if any(abs(p.x-x*1.3)<4.6*1.3 and abs(p.y-y)<4.6 for x,y in seeds):face.material_index=index
cam.location=(250,0,3);cam.rotation_euler=(Vector((0,0,3))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=155;s.render.filepath=str(OUT/'joint-coverage-inspection.png');bpy.ops.render.render(write_still=True)
