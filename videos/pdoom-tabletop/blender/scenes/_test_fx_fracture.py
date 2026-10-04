"""fx test: fracture. Window (1, 5).

FX_TEST=jar (default: a crack runs up a glass jar from 1.5 s, it bursts from inside at 3.0 s)
      | ceramic (a glazed model computer topples off a shelf, keyed, and shatters as it hits the desk at 2.1 s)
"""
import math

import bpy
from mathutils import Vector

from pdoom import fx, kit
from pdoom.fx import fracture, materials, rigid
from pdoom.kit import PAL

from scenes import _test_fx_common as T


def jar(coll, r=5.0, h=13.0):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=64, location=(0, 0, h / 2))
    ob = bpy.context.object
    ob.name = 'jar'
    kit.link(ob, coll)
    # open top: delete the top cap, round the shoulder a little, give the wall 3 mm of glass
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    top = [f for f in bm.faces if f.normal.z > 0.9]
    bmesh.ops.delete(bm, geom=top, context='FACES')
    bm.to_mesh(ob.data)
    bm.free()
    sol = ob.modifiers.new('wall', 'SOLIDIFY')
    sol.thickness, sol.offset = 0.3, -1.0
    kit.smooth(ob, 35)
    ob.data.materials.append(materials.glass())
    lid = kit.cylinder('jar.lid', r + 0.25, 1.2, (0, 0, h + 0.62), bevel=0.2,
                       m=kit.mat('test.lid', '#B8893A', rough=0.3, metal=1.0), coll=coll)
    return ob, lid


def build():
    m = T.mode('jar')
    sc = kit.new_scene('_test_fx_fracture', window=(1.0, 5.0))
    s = T.set_desk()
    rigid.world(substeps=24, iterations=12)
    rigid.passive(s['desk'], shape='BOX')
    coll = kit.collection('props')
    if m == 'jar':
        j, lid = jar(coll)
        kit.box('clawd', (7, 4, 4.5), (0, 0, 2.3), bevel=0.6, m=kit.mat('test.vinyl', PAL['clawd'], rough=0.4),
                coll=coll)
        pieces = fracture.fracture(j, 60, seed=11, impact=(0, -5, 3), cluster=0.4, swap_at=3.0)
        cr = fracture.crack(pieces, 1.5, origin=(0, -5, 0.5), speed=10.0)
        fx.vis(cr, 1.5, 3.0)
        fracture.shatter(pieces, 3.0, impact=(0, 0, 4), speed=(20, 60), spin=10)
        rigid.active(lid, mass=0.08, shape='CYLINDER')
        T.night_lights((0, 0, 7), key_power=40, fill_power=14)
        T.look((10, -48, 14), (0, 0, 6), lens=50, fstop=16)
    else:
        shelf = kit.box('shelf', (30, 16, 30), (0, 14, 15), bevel=0.3, m=kit.mat('test.shelf', '#4A3326', rough=0.5),
                        coll=coll)
        rigid.passive(shelf, shape='BOX')
        glaze = kit.mat('test.glaze', '#E8E2D2', rough=0.15, coat=0.8, coat_rough=0.05)
        model = kit.box('computer', (10, 8, 12), (0, 11, 36.02), bevel=0.4, m=glaze, coll=coll)
        panel = kit.box('computer.panel', (7, 0.6, 5), (0, 6.8, 38), bevel=0.2,
                        m=kit.mat('test.panel', PAL['teal'], rough=0.3, coat=0.6), coll=coll)
        # join the panel into the model so it breaks as one piece of ceramic
        with bpy.context.temp_override(active_object=model, selected_editable_objects=[model, panel],
                                       selected_objects=[model, panel]):
            bpy.ops.object.join()
        # keyed topple over the shelf's front edge, landing flat on the desk exactly at 2.1 s
        hit = fracture.topple(model, 1.45, 2.1, direction=(0, -1, 0), floor=0.0)
        pieces = fracture.fracture(model, 40, seed=3, mode='volume', inner=materials.ceramic_break(),
                                   swap_at=2.1)
        fracture.shatter(pieces, 2.1, follow=model, impact=hit, speed=(40, 110), spin=8, mass_density=0.002)
        T.night_lights((0, 0, 10), key_power=40, fill_power=14)
        T.look((55, -70, 26), (0, 0, 12), lens=32, fstop=16)
    fx.bake()
