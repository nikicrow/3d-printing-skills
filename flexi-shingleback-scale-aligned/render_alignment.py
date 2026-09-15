import bpy,json
from pathlib import Path
from mathutils import Vector
OUT=Path(__file__).parent
bpy.ops.wm.open_mainfile(filepath=str(OUT/'flexi-shingleback-scale-aligned.blend'))
s=bpy.context.scene;cam=s.camera
s.render.resolution_x=1400;s.render.resolution_y=1400
cam.location=(0,0,300);cam.rotation_euler=(Vector((0,0,0))-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=178
s.render.filepath=str(OUT/'middle-scale-detail.png');bpy.ops.render.render(write_still=True)
# Color the deliberately registered middle row to make individual pieces clear.
layout=json.loads((OUT/'layout.json').read_text());targets=json.loads((OUT/'scale-targets.json').read_text())['centre_targets']
rows={int(k) for k in targets}
count=0
for name,ids in layout['groups'].items():
 if not name.startswith('Scale'):continue
 x,y=layout['seeds'][ids[0]];row=round(y/5.0736)
 if abs(x)<.01 and row in rows:
  o=bpy.data.objects[name];o.data.materials[0].diffuse_color=(.18,.55,.50,1) if count%2 else (.75,.47,.12,1);count+=1
cam.data.ortho_scale=300;s.render.resolution_y=1800;s.render.filepath=str(OUT/'scale-alignment-map.png');bpy.ops.render.render(write_still=True)
print('HIGHLIGHTED_MIDDLE_PIECES',count)
