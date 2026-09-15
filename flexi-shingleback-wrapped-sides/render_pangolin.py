import bpy
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.stl_import(filepath=str(OUT/'pangolin-reference.stl'))
o=bpy.context.object
mat=bpy.data.materials.new('Clay');mat.diffuse_color=(.48,.32,.16,1);o.data.materials.append(mat)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_cavity=True;s.display.shading.cavity_type='BOTH'
s.render.resolution_x=1400;s.render.resolution_y=900;s.render.resolution_percentage=100
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.type='ORTHO';cam.data.clip_end=2000
for name,pos,target,scale in [('pangolin-side',(300,0,20),(0,0,20),300),('pangolin-under',(180,-60,-200),(0,0,10),300)]:
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.filepath=str(OUT/(name+'.png'));bpy.ops.render.render(write_still=True)
