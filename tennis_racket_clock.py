"""Parametric three-component tennis racket clock. Dimensions in millimetres."""
from pathlib import Path
import argparse
import json
import math
import zipfile
import xml.etree.ElementTree as ET

import numpy as np
import trimesh
import manifold3d
from shapely.geometry import Point, Polygon, LineString, box
from shapely.affinity import scale, translate
from shapely.ops import unary_union
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pydantic import BaseModel, ConfigDict, Field
from mesh_utils import write_color_3mf

ROOT = Path(__file__).resolve().parent


class ClockConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    face_height: float = Field(default=200, ge=180, le=220)
    face_thickness: float = Field(default=3, ge=2, le=6)
    frame_thickness: float = Field(default=12, ge=8, le=14)
    string_height: float = Field(default=2, ge=1, le=3)
    numeral_height: float = Field(default=2, ge=1, le=3)
    hub_above_strings: float = Field(default=1, ge=.5, le=2)
    hole_diameter: float = Field(default=9, ge=5, le=15)
    face_clearance: float = Field(default=.30, ge=.15, le=.6)
    joint_clearance: float = Field(default=.25, ge=.15, le=.6)
    font: str = 'C:/Windows/Fonts/BRUSHSCI.TTF'


def ellipse(rx, ry):
    return scale(Point(0, 0).buffer(1, quad_segs=128), rx, ry)


def extrude(poly, bottom, height):
    polys = list(poly.geoms) if poly.geom_type == 'MultiPolygon' else [poly]
    meshes = []
    for p in polys:
        if p.is_empty or p.area < 1e-8:
            continue
        m = trimesh.creation.extrude_polygon(p, height, engine='earcut')
        m.apply_translation([0, 0, bottom])
        meshes.append(m)
    return trimesh.util.concatenate(meshes)


def union(*meshes):
    return trimesh.boolean.union(list(meshes), engine='manifold')


def difference(a, b):
    return trimesh.boolean.difference([a, b], engine='manifold')


def component_count(mesh):
    parent = list(range(len(mesh.faces)))
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a,b in mesh.face_adjacency:
        parent[find(a)] = find(b)
    return len({find(i) for i in range(len(parent))})


def numerals(font, rx, ry):
    result = []
    for n in range(1, 13):
        contours = TextPath((0, 0), str(n), size=20,
                            prop=FontProperties(fname=font)).to_polygons()
        # XOR preserves glyph counters regardless of contour orientation.
        glyph = Polygon()
        for contour in contours:
            glyph = glyph.symmetric_difference(Polygon(contour).buffer(0))
        a, b, c, d = glyph.bounds
        glyph = scale(glyph, 15 / (d-b), 15 / (d-b), origin=(0, 0))
        a, b, c, d = glyph.bounds
        angle = n * math.pi / 6
        result.append(translate(glyph, rx*math.sin(angle)-(a+c)/2,
                                ry*math.cos(angle)-(b+d)/2))
    return unary_union(result)


def build(cfg):
    s = cfg.face_height / 200
    t = cfg.face_thickness
    frame_z = t-cfg.frame_thickness
    face = ellipse(75*s, 100*s)
    bore = Point(0, 0).buffer(cfg.hole_diameter/2, quad_segs=64)
    nums = numerals(cfg.font, 55*s, 78*s)
    # Continuous strings under the numerals; a round raised hub surrounds the bore.
    lines = [box(x-.55, -110*s, x+.55, 110*s) for x in np.arange(-68*s, 70*s, 8*s)]
    lines += [box(-85*s, y-.55, 85*s, y+.55) for y in np.arange(-92*s, 94*s, 8*s)]
    strings = unary_union(lines).intersection(face.buffer(-2)).difference(bore)
    hub = Point(0,0).buffer(10,quad_segs=64).difference(bore)
    color_change_z = t+cfg.string_height+cfg.hub_above_strings
    white = union(extrude(face.difference(bore), 0, t),
                  extrude(face.buffer(2).difference(bore), 0, 1.5),
                  extrude(strings, t, cfg.string_height),
                  extrude(hub,t,cfg.string_height+cfg.hub_above_strings),
                  extrude(nums,t,cfg.string_height+cfg.hub_above_strings))
    # Remove sub-micron slivers at glyph/grid crossings before slicer welding.
    simplified = manifold3d.Manifold(manifold3d.Mesh(
        np.asarray(white.vertices,dtype=np.float32),
        np.asarray(white.faces,dtype=np.uint32))).simplify(.0001).to_mesh()
    white = trimesh.Trimesh(vertices=simplified.vert_properties[:,:3],
                            faces=simplified.tri_verts)
    red = extrude(nums, color_change_z, cfg.numeral_height)
    solid_face = union(white, red)
    # Constant-width curved arms match the 12 mm head band in plan view.
    # The reference grip begins below the throat; its joint is hidden at the rear.
    def bezier(points):
        p = np.asarray(points)
        u = np.linspace(0,1,49)[:,None]
        return (1-u)**3*p[0]+3*(1-u)**2*u*p[1]+3*(1-u)*u**2*p[2]+u**3*p[3]
    right = bezier([(64,-67),(48,-97),(4,-132),(4,-178)])
    arms = [LineString(right*[sign,1]).buffer(6,quad_segs=24) for sign in (-1,1)]
    throat = scale(unary_union([*arms,box(-10,-190,10,-174)]),s,s,origin=(0,0))
    # Round the internal junctions without thinning either swept arm.
    outline = unary_union([face.buffer(12*s),throat]).buffer(1.5*s).buffer(-1.5*s)
    tenon = Polygon([(-5*s,-191*s),(5*s,-191*s),(7*s,-175*s),(-7*s,-175*s)])
    socket = tenon.buffer(cfg.joint_clearance, join_style=2)
    lower = outline.difference(face.buffer(2+cfg.face_clearance))
    upper = outline.difference(face.buffer(cfg.face_clearance))
    # The thin face's flange sits within its first 1.5 mm, not behind the face.
    # Its mating step is near the frame front, leaving clearance at the rear.
    frame = union(extrude(lower, frame_z, 1.5-frame_z),
                  extrude(upper, 1.5, t-1.5))
    frame = difference(frame,extrude(socket,frame_z-.1,cfg.frame_thickness-3.9))
    handle_shape = Polygon([(-11*s,-190.5*s),(11*s,-190.5*s),(12*s,-196*s),
                            (12*s,-282*s),(15*s,-286*s),(15*s,-290*s),
                            (-15*s,-290*s),(-15*s,-286*s),(-12*s,-282*s),(-12*s,-196*s)])
    handle = union(extrude(handle_shape, frame_z, cfg.frame_thickness),
                   extrude(tenon,frame_z,cfg.frame_thickness-4.25))
    # Shallow diagonal wrap grooves on the front of the grip.
    grooves = unary_union([LineString([(-19*s,y-5*s),(19*s,y+5*s)]).buffer(.6*s)
                           for y in np.arange(-278*s,-198*s,8*s)])
    handle = difference(handle, extrude(grooves, t-.65, 2))
    return {'white':white,'red':red,'face':solid_face,'frame':frame,'handle':handle}, {
        'face':face,'strings':strings,'nums':nums,'outline':outline,
        'frame':upper,'handle':handle_shape,'bore':bore,'tenon':tenon,'socket':socket,
        'lower':lower,'upper':upper,'hub':hub}


def patch(ax, poly, color, edge=None):
    for p in (poly.geoms if poly.geom_type == 'MultiPolygon' else [poly]):
        from shapely.geometry.polygon import orient
        p = orient(p)
        verts, codes = [], []
        for ring in [p.exterior, *p.interiors]:
            coords = list(ring.coords)
            verts.extend(coords)
            codes.extend([MplPath.MOVETO]+[MplPath.LINETO]*(len(coords)-2)+[MplPath.CLOSEPOLY])
        ax.add_patch(PathPatch(MplPath(verts,codes),facecolor=color,edgecolor=edge,lw=.45))


def preview(meshes, shapes, cfg, path):
    fig = plt.figure(figsize=(14,11), facecolor='#e9edf0')
    ax = fig.add_axes([.04,.08,.33,.82],facecolor='#e9edf0')
    patch(ax,shapes['frame'],'#cc172c')
    patch(ax,shapes['handle'],'#26313a')
    patch(ax,shapes['face'].difference(shapes['bore']),'#ffffff','#b9c0c5')
    patch(ax,shapes['strings'],'#dce1e5')
    patch(ax,shapes['hub'],'#ffffff','#b9c0c5')
    patch(ax,shapes['nums'],'#d4142b')
    for y in np.arange(-278,-198,8):
        ax.plot([-11,11],[y-3,y+3],color='#59636a',lw=1)
    ax.set_aspect('equal'); ax.set_xlim(-115,115); ax.set_ylim(-320,130); ax.axis('off')
    ax.set_title('FRONT · 200 × 150 mm face',fontsize=12)
    ax3 = fig.add_axes([.39,.20,.59,.68],projection='3d',facecolor='#e9edf0')
    triangles, colors = [], []
    camera_direction = np.array([math.cos(math.radians(47))*math.cos(math.radians(-70)),
                                 math.cos(math.radians(47))*math.sin(math.radians(-70)),
                                 math.sin(math.radians(47))])
    for key,color in [('white','#fafafa'),('red','#dc1830'),('frame','#c71d32'),('handle','#303a44')]:
        mesh=meshes[key]
        visible = mesh.face_normals @ camera_direction > 0
        triangles.extend(mesh.triangles[visible])
        colors.extend([color]*int(visible.sum()))
    # One collection permits depth sorting across all material boundaries.
    coll=Poly3DCollection(triangles,facecolors=colors,linewidths=0,shade=True,
                         lightsource=matplotlib.colors.LightSource(azdeg=310,altdeg=55))
    ax3.add_collection3d(coll)
    ax3.set_xlim(-105,105);ax3.set_ylim(-315,125);ax3.set_zlim(-14,16)
    ax3.set_box_aspect((210,440,30));ax3.view_init(elev=47,azim=-70);ax3.set_axis_off()
    ax3.set_title('ASSEMBLED · actual printable geometry',fontsize=12)
    fig.text(.055,.945,'TENNIS RACKET CLOCK',fontsize=25,weight='bold',color='#21313e')
    fig.text(.42,.14,'3 mm base · strings top at 5 mm · white hub top at 6 mm\nRed numerals: 6–8 mm · single colour change at 6 mm\n8 mm total face depth / 12 mm frame / Ø9 mm hole',fontsize=12,linespacing=1.7,color='#374550')
    fig.text(.055,.025,'White/red face · Red frame with open throat · Charcoal grip with sliding dovetail',fontsize=11,color='#374550')
    fig.savefig(path,dpi=150);plt.close(fig)


def verify(meshes, shapes, cfg):
    report = {'configuration':cfg.model_dump(),'meshes':{}}
    for key,m in meshes.items():
        assert m.is_watertight and m.is_winding_consistent and m.volume>0, key
        components = component_count(m)
        if key != 'red':
            assert components==1,(key,components)
        report['meshes'][key]={'watertight':True,'components':components,
                               'bounds_mm':m.bounds.tolist(),'volume_mm3':float(m.volume),'triangles':len(m.faces)}
    for a,b in [('face','frame'),('frame','handle'),('face','handle'),('white','red')]:
        overlap=trimesh.boolean.intersection([meshes[a],meshes[b]],engine='manifold')
        assert abs(overlap.volume)<.001,(a,b,overlap.volume)
    assert shapes['socket'].contains(shapes['tenon'])
    color_change_z = cfg.face_thickness+cfg.string_height+cfg.hub_above_strings
    assert abs(meshes['face'].extents[2]-(color_change_z+cfg.numeral_height))<.001
    assert meshes['face'].extents[2] < cfg.frame_thickness
    assert abs(meshes['white'].bounds[1,2]-color_change_z)<.001
    assert abs(meshes['red'].bounds[0,2]-color_change_z)<.001
    report['color_change_z_mm'] = color_change_z
    report['hub_diameter_mm'] = 20
    # Every string and numeral has white support up to its intended layer.
    grid_probe=extrude(shapes['strings'],cfg.face_thickness+.01,cfg.string_height-.02)
    assert abs(difference(grid_probe,meshes['white']).volume)<.001
    support_probe=extrude(shapes['nums'],color_change_z-.1,.09)
    assert abs(difference(support_probe,meshes['white']).volume)<.001
    probe=extrude(shapes['bore'].buffer(-.01),-1,color_change_z+cfg.numeral_height+2)
    assert abs(trimesh.boolean.intersection([meshes['face'],probe],engine='manifold').volume)<.001
    report['checks']=['All physical parts connected, watertight, positive volume',
                      'Zero assembled part intersections','Clear 9 mm through-bore',
                      'Dovetail contained by clearance socket','White and red materials do not overlap',
                      'Continuous white strings under all numerals; supported red numeral bases',
                      'Single height-separated colour change; white hub 1 mm above strings by default']
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path)
    parser.add_argument('--font',type=Path)
    args=parser.parse_args()
    values=json.loads(args.config.read_text()) if args.config else {}
    if args.font: values['font']=str(args.font)
    cfg=ClockConfig(**values)
    if not Path(cfg.font).is_file(): raise FileNotFoundError('Supply a script font with --font')
    out=ROOT/'printable_files'/'tennis_racket_clock';out.mkdir(parents=True,exist_ok=True)
    pic=ROOT/'previews'/'tennis_racket_clock';pic.mkdir(parents=True,exist_ok=True)
    meshes,shapes=build(cfg)
    report=verify(meshes,shapes,cfg)
    for key in ('face','frame','handle'):
        m=meshes[key].copy()
        # Frame prints front-down: the locating recess opens upwards.
        if key=='frame': m.apply_transform(trimesh.transformations.rotation_matrix(math.pi,[1,0,0]))
        m.apply_translation([-m.centroid[0],-m.centroid[1],-m.bounds[0,2]])
        target=out/f'{key}.stl';m.export(target)
        check=trimesh.load_mesh(target)
        assert check.is_watertight and check.is_winding_consistent and component_count(check)==1
    combo=trimesh.util.concatenate([meshes['white'],meshes['red']])
    fm=np.r_[np.zeros(len(meshes['white'].faces),int),np.ones(len(meshes['red'].faces),int)]
    write_color_3mf(combo,fm,['#FFFFFF','#D4142B'],str(out/'face_white_red.3mf'),
                    names=['White face, strings and hub','Red script numerals'],
                    object_name='Tennis racket clock face',precision=8)
    with zipfile.ZipFile(out/'face_white_red.3mf') as package:
        xml=ET.fromstring(package.read('3D/3dmodel.model'))
        ns={'m':'http://schemas.microsoft.com/3dmanufacturing/core/2015/02'}
        assert len(xml.findall('m:build/m:item',ns))==1
        assert len(xml.findall('.//m:component',ns))==2
        materials=xml.findall('.//m:base',ns)
        assert [x.attrib['displaycolor'] for x in materials]==['#FFFFFFFF','#D4142BFF']
        for obj in xml.findall('.//m:object',ns):
            if obj.find('m:mesh',ns) is None: continue
            vertices=[[float(v.attrib[k]) for k in ('x','y','z')] for v in obj.findall('.//m:vertex',ns)]
            faces=[[int(f.attrib[k]) for k in ('v1','v2','v3')] for f in obj.findall('.//m:triangle',ns)]
            assert trimesh.Trimesh(vertices=vertices,faces=faces).is_watertight
    report['checks'].append('Reopened STLs and 3MF; closed meshes, two colours, one face build object')
    # Material STLs retain common coordinates for slicers that prefer multipart import.
    for key in ('white','red'): meshes[key].export(out/f'face_{key}_material.stl')
    (out/'validation.json').write_text(json.dumps(report,indent=2))
    preview(meshes,shapes,cfg,pic/'assembled.png')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
