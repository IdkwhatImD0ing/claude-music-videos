"""finale, the desk part: the build-up (140.230-143.867) and kick 1 (143.867-144.776).

It starts from ilya's own world (ilya.build(): the desk as a puppet theatre, the paperclip audience, the researcher
on marionette strings, ilya's last camera), so the cut from ilya into the finale is the same shot carrying on.

 F0  140.230-143.867  ilya's pull-back keeps going over the house. It starts to rain paperclips over the stage and
                      the audience (the curtain call's confetti is clips); a tide of clips rises through the rows from
                      the front of the desk. On the downbeat 142.049 the marionette strings snap taut and the
                      researcher is hoisted up off the stage, legs dangling, as the flood covers the apron and the
                      footlights. The camera cranes up and tilts down over the flooded house.
 K1  143.867-144.776  The desk buried in clips, from high above its front: the theatre's gilded top, the lamp and
                      the laptop's lid stick out of a silver sea; clips spill over the desk's front edge onto a floor
                      that is clips too. The lamp's warm pool and the window's cool light; a slow rise back.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from pdoom import chars, kit
from pdoom import timeline
from pdoom import timing as tm
from pdoom.fx import clips as C
from pdoom.sets import geo as sgeo

from scenes import finale_common as F
from scenes.boot_common import key_mats

FPS = tm.FPS
V = Vector
K1, K2 = F.KICKS[0], F.KICKS[1]
T_HOIST = 142.049          # the downbeat: the strings snap taut
T_RAIN = 140.45


def build(sc_name='finale'):
    from scenes import ilya
    d, r, bx, th = ilya.build()
    sc = bpy.context.scene
    sc.name = sc_name
    f0, f1 = timeline.frames(sc_name)
    sc.frame_start, sc.frame_end = f0, f1
    sc.timeline_markers.clear()
    sc.frame_set(f0)
    world_objs = [o for o in bpy.data.objects]           # everything ilya built: the desk world
    coll = kit.collection('finale.desk')

    # ------------------------------------------------------------------ the researcher is hoisted by his strings
    chars.POSES['dangle'] = dict(chars.POSES['marionette_up'])
    chars.POSES['dangle'].update(thigh=((-10, 3, 0), (7, -3, 0)), shin=(22, 9), head=(-10, 0, 0))
    root0 = V(r.T['root.loc'].at(T_HOIST - 0.2))
    r.pose(T_HOIST - 0.3, 'marionette_up', dur=0.1)
    r.face(141.14, 'scared')
    r.pose(T_HOIST + 0.25, 'dangle', dur=0.2)
    r.face(T_HOIST + 0.4, 'awe')
    def hoist(t):
        u = (t - T_HOIST) / (K1 - T_HOIST)
        if u <= 0:
            return 0.0
        # a jerk up on the beat, then a haul that accelerates away (out of frame before K1)
        return 2.5 * min(1.0, u / 0.05) + 160.0 * u ** 2.2
    for k in range(0, 60):
        t = T_HOIST + k * 0.05
        r.T['root.loc'].set(t, (root0.x, root0.y, root0.z + hoist(t)), 0.05, 'linear')
    r.no_gait(T_HOIST - 0.1, K1 + 1.0)
    r._baked = False
    # the strings ride up with him on the same stop-motion grid
    strings = [o for o in bpy.data.objects if o.name.startswith('theatre.string')]
    for o in strings:                       # the strings run up out of every frame (to the flies)
        top = max(v.co.z for v in o.data.vertices)
        for v in o.data.vertices:
            if v.co.z > top - 0.05:
                v.co.z += 400.0
    rig_empty = kit.empty('finale.strings', (0, 0, 0), coll)
    for o in strings:
        o.parent = rig_empty
    key_mats(rig_empty, lambda t: _Tz(r.T['root.loc'].at(t)[2] - root0.z), T0(), K2 + 0.2, default='twos')

    # ------------------------------------------------------------------ the tide: a sea rising from the house
    lv = [(140.35, -0.5), (141.14, 1.2), (142.05, 3.2), (143.0, 6.5), (143.9, 9.0), (K2 + 0.3, 11.0)]
    sea0 = C.sea('f0.sea', area=((-80.0, -40.0), (80.0, 40.0)), base=0.0, depth=13.0, level=lv, density=0.85,
                 band=1.7, drop=3.0, origin=(6.0, -46.0, 0.0), slope=0.07, lod=2, seed=21, coll=coll)
    F.show([sea0['object']], None, F.edge(K1))
    # a rain of clips over the stage and the stalls (the curtain call's confetti)
    rain = F.stream('f0.rain', source=((6.0, -14.0, 58.0), (84.0, 46.0)), t0=T_RAIN, t1=K1 + 0.2, rate=1400.0,
                    direction=(0.02, 0.05, -1.0), speed=(10.0, 45.0), scale=1.0, floor=0.05, cone=12.0, seed=31,
                    coll=coll, drag=0.6)
    # rain vanishes into the sea (level at the stage is ~ level - slope * 40)
    F.cull_below(rain, [(t, h - 2.5) for t, h in lv])
    F.show([rain], None, F.edge(K1))
    # a quicker shutter while it rains (falling clips near the lens smeared into striped grey cards, EEVEE's 4 blur
    # steps showing as bands); from the rain's start (not on the seam with ilya's shot) to K1. run.py scales them for
    # 60 fps and moves the steps between exposures.
    for t, v in ((F.T0 - 1.0, 0.5), (F.edge(T_RAIN), 0.2), (F.edge(K1), 0.5)):
        sc.render.motion_blur_shutter = v
        sc.keyframe_insert('render.motion_blur_shutter', frame=t * FPS)
    for fc in kit.fcurves(sc):
        if fc.data_path == 'render.motion_blur_shutter':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'

    # ------------------------------------------------------------------ K1: the desk buried
    k1 = kit.collection('finale.k1')
    sea1 = C.sea('k1.sea', area=((-80.0, -40.0), (80.0, 40.0)), base=0.0, depth=16.0,
                 level=[(K1 - 0.2, 11.5), (K1, 11.8), (K2 + 0.2, 13.6)], density=0.85, band=1.7, drop=3.0,
                 origin=(0.0, -10.0, 0.0), slope=0.035, lod=2, seed=23, coll=k1)
    # the floor of the room: clips up to just under the desk top, and a talus spilling over the desk's front edge
    floor_z = -9.0
    fl = F.grid_mesh('k1.floorclips', (560.0, 300.0), (40, 20), coll=k1, loc=(0.0, -108.0, floor_z),
                     height=lambda x, y: 1.6 * math.sin(x * 0.05) * math.sin(y * 0.07 + 1.0))
    F.carpet('k1.floor', fl, scale=1.0, density=0.3, layers=2, lod=3, coll=k1, seed=41, core=F.core_mat())
    for side, (x0, x1, y0, y1) in {'front': (-82.0, 82.0, -40.5, -40.5)}.items():
        tal = _talus(f'k1.talus.{side}', k1, x0, x1, y0, 11.0, floor_z)
        F.carpet(f'k1.talus.{side}.clips', tal, scale=1.0, density=0.32, layers=2, lod=2, coll=k1, seed=43,
                 core=F.core_mat())
    for sx in (-1, 1):
        tal = _talus_side(f'k1.talus.{sx}', k1, sx * 80.5, -40.0, 40.0, 10.0, floor_z, sx)
        F.carpet(f'k1.talus.{sx}.clips', tal, scale=1.0, density=0.32, layers=2, lod=3, coll=k1, seed=47 + sx,
                 core=F.core_mat())
    # the cascade over the front edge
    pour = F.stream('k1.cascade', source=((0.0, -41.0, 12.0), (150.0, 1.0)), t0=K1 - 1.0, t1=K2 + 0.2, rate=900.0,
                    direction=(0.0, -1.0, -0.2), speed=(10.0, 40.0), scale=1.0, floor=floor_z + 0.5, cone=25.0,
                    seed=35, coll=k1, drag=0.3)
    k1_objs = F.objects_in(k1)
    F.show(k1_objs, F.edge(K1), F.edge(K2))

    # ------------------------------------------------------------------ light: the house lights come up after the show
    lc = kit.collection('finale.desk.lights')
    if d.room.bounce is not None:
        sgeo.keyp(d.room.bounce.data, 'energy', 140.9, 2000.0, interp='LINEAR')
        sgeo.keyp(d.room.bounce.data, 'energy', 141.9, 70000.0, interp='LINEAR')
    over = kit.area('finale.over', (0.0, 10.0, 170.0), (0.0, -8.0, 0.0), power=0.0, size=150.0, color='#B9C8E8',
                    shape='RECTANGLE', coll=lc)
    over.data.size_y = 90.0
    sgeo.keyp(over.data, 'energy', 141.0, 0.0, interp='LINEAR')
    sgeo.keyp(over.data, 'energy', 142.2, 260000.0, interp='LINEAR')
    over.data.volume_factor = 0.0
    warm = kit.area('finale.warm', (-120.0, -120.0, 90.0), (0.0, 0.0, 5.0), power=0.0, size=80.0, color='#FFC98A',
                    coll=lc)
    sgeo.keyp(warm.data, 'energy', 141.0, 0.0, interp='LINEAR')
    sgeo.keyp(warm.data, 'energy', 142.2, 90000.0, interp='LINEAR')
    warm.data.volume_factor = 0.0
    sgeo.keyp(d.room.moon.data, 'energy', 141.0, 22000.0, interp='LINEAR')
    sgeo.keyp(d.room.moon.data, 'energy', 142.5, 90000.0, interp='LINEAR')
    world_objs += [over, warm]

    # ------------------------------------------------------------------ the desk world ends at K2
    F.hide_after([o for o in world_objs if o.type != 'CAMERA'] + [rig_empty], F.edge(K2))

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('finale.cams')
    cam5 = bpy.data.objects.get('cam.5')
    _extend_ilya_pullback(cam5)
    kit.cut_to(cam5, F.T0)
    # K1: high above the desk's front, a slow rise back
    c1 = F.Cam('cam.k1', K1, K2, F.path((2.0, -172.0, 200.0), (3.0, -202.0, 236.0), K1, K2 + 0.1),
               F.path((0.0, 8.0, -8.0), (0.0, 10.0, -10.0), K1, K2 + 0.1), lens=40.0, fstop=2.2,
               focus=F.path((3.0, -6.0, 12.0), (3.0, -4.0, 12.0), K1, K2), coll=cams)
    return {'desk': d, 'researcher': r, 'theatre': th, 'world': world_objs, 'cams': [cam5, c1.cam]}


def T0():
    return F.T0


def _Tz(z):
    from mathutils import Matrix
    return Matrix.Translation((0.0, 0.0, z))


def _extend_ilya_pullback(cam):
    """ilya's last shot pulls back over the house (cam.5): keep it going, then crane up and tilt down."""
    tgt = bpy.data.objects.get(cam.name + '.target')
    # ilya's move at its end (e ~ 1): loc (CX + e, -26 - 44e, 9.5 + 9e), target (CX + 0.5e, 2 + 2e, 12 + 9e), lens
    # 32 - 6e, with e still growing ~0.155/s
    CX = 6.0

    def e_of(t):
        ta, tb = 137.797 - 0.1, 140.23 + 0.05
        u = min(1.0, max(0.0, (t - ta) / (tb - ta)))
        e = u * u * (3 - 2 * u)
        e = 0.6 * e + 0.4 * u
        if t > tb:
            e += 0.4 / (tb - ta) * (t - tb)
        return e

    def crane(t):
        u = (t - 140.9) / (K1 - 140.9)
        u = min(1.0, max(0.0, u))
        return u * u * (3 - 2 * u) * 0.7 + 0.3 * u * u

    f0 = int(math.floor(F.T0 * FPS)) - 1
    f1 = int(math.ceil(K1 * FPS)) + 2
    for f in range(f0, f1 + 1):
        t = f / FPS
        e = e_of(t)
        c = crane(t)
        cam.location = (CX + e + 1.0 * c, -26.0 - 44.0 * e - 10.0 * c, 9.5 + 9.0 * e + 30.0 * c)
        cam.keyframe_insert('location', frame=f)
        tgt.location = (CX + 0.5 * e, 2.0 + 2.0 * e - 6.0 * c, 12.0 + 9.0 * e - 12.0 * c)
        tgt.keyframe_insert('location', frame=f)
        cam.data.lens = 32.0 - 6.0 * min(e, 1.0) - 2.0 * c
        cam.data.keyframe_insert('lens', frame=f)
    for ob in (cam, tgt, cam.data):
        kit.set_interp(ob, 'LINEAR')


def _talus(name, coll, x0, x1, y_edge, z_top, z_toe, run=26.0):
    """A slope of clips from the desk's front edge (z_top) down and out to the floor clips (z_toe)."""
    import bmesh
    bm = bmesh.new()
    nx, ny = 40, 8
    rows = []
    for j in range(ny + 1):
        v = j / ny
        row = []
        for i in range(nx + 1):
            x = x0 + (x1 - x0) * i / nx
            y = y_edge - run * v + 1.5 * math.sin(x * 0.21) * v
            z = z_top + (z_toe - z_top) * (1 - (1 - v) ** 1.6) + 0.8 * math.sin(x * 0.37 + v * 3) * v * (1 - v)
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((rows[j][i], rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _talus_side(name, coll, x_edge, y0, y1, z_top, z_toe, sx, run=22.0):
    import bmesh
    bm = bmesh.new()
    ny, nx = 30, 8
    rows = []
    for j in range(nx + 1):
        v = j / nx
        row = []
        for i in range(ny + 1):
            y = y0 + (y1 - y0) * i / ny
            x = x_edge + sx * run * v
            z = z_top + (z_toe - z_top) * (1 - (1 - v) ** 1.6)
            row.append(bm.verts.new((x, y, z)))
        rows.append(row)
    for j in range(nx):
        for i in range(ny):
            q = (rows[j][i], rows[j + 1][i], rows[j + 1][i + 1], rows[j][i + 1])
            bm.faces.new(q if sx > 0 else tuple(reversed(q)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob
