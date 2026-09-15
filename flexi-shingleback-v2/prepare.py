import bpy,bmesh,numpy as np,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=str(next((OUT/'reference').glob('*.obj'))))
o=bpy.context.object;bpy.ops.object.transform_apply(location=True,rotation=True,scale=True)
v=np.array([tuple(p.co) for p in o.data.vertices]);print('RAW',v.min(0),v.max(0),flush=True)
scale=190/(v[:,1].max()-v[:,1].min());center=(v.min(0)+v.max(0))/2
zmin=v[:,2].min()
for p in o.data.vertices:p.co=Vector(((p.co.x-center[0])*scale,(p.co.y-center[1])*scale,(p.co.z-zmin)*scale))
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'source-study.blend'))
mod=o.modifiers.new('Surface repair','REMESH');mod.mode='VOXEL';mod.voxel_size=.22;bpy.ops.object.modifier_apply(modifier=mod.name)
mod=o.modifiers.new('Triangulation reduction','DECIMATE');mod.ratio=.65;bpy.ops.object.modifier_apply(modifier=mod.name)
mod=o.modifiers.new('Triangles','TRIANGULATE');bpy.ops.object.modifier_apply(modifier=mod.name)
v=np.array([tuple(p.co) for p in o.data.vertices]);f=np.array([tuple(p.vertices) for p in o.data.polygons]);np.savez_compressed(OUT/'source-print.npz',vertices=v,faces=f)
print('SOURCE',v.min(0),v.max(0),len(f),flush=True)
o.data.materials.clear();mat=bpy.data.materials.new('Clay');mat.diffuse_color=(.48,.27,.10,1);o.data.materials.append(mat)
s=bpy.context.scene;s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.render.resolution_x=1100;s.render.resolution_y=900;s.render.resolution_percentage=100
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.type='ORTHO';cam.data.clip_end=2000
for n,pos in [('source-top',(0,0,260)),('source-side',(250,-20,40)),('source-preview',(145,-180,195))]:
 cam.location=pos;cam.rotation_euler=(Vector((0,0,10))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=235;s.render.filepath=str(OUT/(n+'.png'));bpy.ops.render.render(write_still=True)

