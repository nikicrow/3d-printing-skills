import bpy,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).parent
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene;s.unit_settings.system='METRIC';s.unit_settings.scale_length=.001;s.unit_settings.length_unit='MILLIMETERS'
parts=[]
for i,p in enumerate(sorted((OUT/'parts').glob('*.stl'))):
 bpy.ops.wm.stl_import(filepath=str(p));o=bpy.context.object;o.name=p.stem;parts.append(o)
 mat=bpy.data.materials.new(p.stem);f=(i%3)*.025;mat.diffuse_color=(.40+f,.25+f,.12+f,1);o.data.materials.append(mat)
 for poly in o.data.polygons:poly.use_smooth=True
 o.data.set_sharp_from_angle(angle=.65)
s.render.engine='BLENDER_WORKBENCH';s.display.shading.light='STUDIO';s.display.shading.color_type='MATERIAL';s.display.shading.show_shadows=True;s.display.shading.show_cavity=True;s.display.shading.cavity_type='BOTH';s.display.shading.curvature_ridge_factor=1.4
s.display.shading.background_type='WORLD';s.world=bpy.data.worlds.new('World');s.world.color=(.12,.12,.12)
s.render.resolution_x=1400;s.render.resolution_y=1100;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG'
bpy.ops.object.camera_add();cam=bpy.context.object;s.camera=cam;cam.data.type='ORTHO';cam.data.clip_end=2000
for name,pos,target,scale in [('shingleback-preview.png',(145,-180,195),(0,0,10),225),('shingleback-top.png',(0,0,260),(0,0,0),245),('shingleback-side.png',(250,-25,38),(0,0,10),220),('shingleback-underside.png',(100,-140,-240),(0,0,5),235)]:
 cam.location=pos;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale;s.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
cam.location=(120,90,95);cam.rotation_euler=(Vector((15,53,10))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=93;s.render.filepath=str(OUT/'hindleg-detail.png');bpy.ops.render.render(write_still=True)
cam.location=(145,-180,195);cam.rotation_euler=(Vector((0,0,10))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=225
for area in bpy.context.screen.areas:
 if area.type=='VIEW_3D':
  area.spaces.active.region_3d.view_distance=230;area.spaces.active.region_3d.view_location=(0,0,12);area.spaces.active.region_3d.view_rotation=cam.rotation_euler.to_quaternion();area.spaces.active.shading.color_type='MATERIAL'
s['source_archive']='Meshy_AI_shingleback_lizard_v2_0913105224_image-to-3d-texture_obj.zip'
s['joint_pitch_mm']=[5.2277,5.0736];s['validation']='See validation.json; physical print test pending'
bpy.ops.object.select_all(action='DESELECT');bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'flexi-shingleback-v2.blend'))
print('SAVED',len(parts),'separate objects',flush=True)
