"""ilya's reveal: the desk is a puppet-theatre stage. A lacquered, gilded toy proscenium on the desk, a red velvet
festoon curtain that rises in swags, a row of footlights, an audience of paperclips standing on risers, and
marionette strings on the researcher.

    th = build_theatre(coll, cx=4, front_y=-2)
    th.visible(137.3)                      # hidden before (the reveal)
    th.footlights(137.38, 0.04)            # bulbs pop on left to right
    th.rise(137.8, 139.3)                  # the curtain gathers up into swags
    audience(coll, th)                     # rows of paperclips facing the stage
    marionette(coll, [head_top, hand_L, hand_R], top_z=34)
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.chars import geo as cgeo
from pdoom.chars import looks
from pdoom.chars.rig import hash01
from pdoom.sets import materials as SM

FPS = tm.FPS
NK = 12          # festoon shape-key states


def _T(p):
    return Matrix.Translation(Vector(p))


def _R(ex, ey, ez):
    from mathutils import Euler
    return Euler((math.radians(ex), math.radians(ey), math.radians(ez)), 'XYZ').to_matrix().to_4x4()


def velvet(name='theatre.velvet', color='#8A0F18'):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = kit.srgb(color)
    b.inputs['Roughness'].default_value = 0.85
    b.inputs['Sheen Weight'].default_value = 1.0
    b.inputs['Sheen Roughness'].default_value = 0.35
    b.inputs['Sheen Tint'].default_value = kit.srgb('#FF6A70')
    b.inputs['Specular IOR Level'].default_value = 0.25
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nz = nt.nodes.new('ShaderNodeTexNoise')
    nz.inputs['Scale'].default_value = 140.0
    nz.inputs['Detail'].default_value = 4.0
    bp = nt.nodes.new('ShaderNodeBump')
    bp.inputs['Strength'].default_value = 0.2
    bp.inputs['Distance'].default_value = 0.004
    nt.links.new(tc.outputs['Object'], nz.inputs['Vector'])
    nt.links.new(nz.outputs['Fac'], bp.inputs['Height'])
    nt.links.new(bp.outputs['Normal'], b.inputs['Normal'])
    m.diffuse_color = kit.srgb(color)
    return m


class Theatre:
    def __init__(self):
        self.objs = []
        self.bulbs = []
        self.spots = []

    def visible(self, t_on: float):
        for ob in self.objs:
            kit.visible(ob, t_on, None)
        return self

    def footlights(self, t0: float, step: float = 0.04, level: float = 1.0):
        """The footlight bulbs pop on one by one from t0 (left to right); the wash lights follow."""
        n = len(self.bulbs)
        for i, m in enumerate(self.bulbs):
            s = m.node_tree.nodes['glow'].outputs[0]
            ti = t0 + step * i + 0.012 * (hash01(71, i) - 0.5)
            for t, v in ((ti - 0.5 / FPS, 0.0), (ti, 9.0 * level), (ti + 1.0 / FPS, 4.5 * level),
                         (ti + 3.0 / FPS, 6.0 * level)):
                s.default_value = v
                s.keyframe_insert('default_value', frame=t * FPS)
            kit.set_interp(m.node_tree, 'LINEAR')
        for j, (L, e) in enumerate(self.spots):
            tj = t0 + step * (n - 1) * (j + 0.5) / len(self.spots)
            for t, v in ((tj - 0.5 / FPS, 0.0), (tj + 1.0 / FPS, e * 1.2 * level), (tj + 0.25, e * level)):
                L.energy = v
                L.keyframe_insert('energy', frame=t * FPS)
            kit.set_interp(L, 'LINEAR')
        return self

    def rise(self, t0: float, t1: float):
        """Raise the festoon curtain from t0 to t1 (keyed shape-key blend every frame)."""
        keys = self.curtain.data.shape_keys.key_blocks
        f0, f1 = int(math.floor(t0 * FPS)) - 1, int(math.ceil(t1 * FPS)) + 1
        for f in range(f0, f1 + 1):
            u = min(1.0, max(0.0, (f / FPS - t0) / (t1 - t0)))
            r = u * u * (3 - 2 * u)
            r = 0.72 * r + 0.28 * (1 - (1 - u) ** 3)   # a quicker start: the cords snap taut
            k = r * NK
            i = min(NK - 1, int(k))
            fr = k - i
            for j in range(1, NK + 1):
                v = 0.0
                if j == i:
                    v = 1.0 - fr
                if j == i + 1:
                    v = fr
                keys[j].value = v
                keys[j].keyframe_insert('value', frame=f)
        kit.set_interp(self.curtain.data.shape_keys, 'LINEAR')
        return self


def build_theatre(coll, *, cx: float = 4.0, front_y: float = -2.0, open_w: float = 56.0, open_h: float = 31.0):
    th = Theatre()
    maroon = looks.gloss('theatre.maroon', '#4E0E14', rough=0.3, coat=0.8, coat_rough=0.08, bump=0.05)
    gold = SM.brass('theatre.gold', '#D9AC4E', 0.2)
    red = velvet()
    X0, X1 = cx - open_w / 2, cx + open_w / 2
    PW, FT, HH = 6.5, 1.6, 11.0
    yb = front_y - FT / 2          # the facade's mid plane
    th.X0, th.X1, th.front_y, th.open_h, th.cx = X0, X1, front_y, open_h, cx

    def obj(bm, name, mats, sharp=40.0):
        ob = cgeo.to_object(bm, f'theatre.{name}', coll, mats, sharp=sharp)
        th.objs.append(ob)
        return ob

    # --- facade: pillars, header, pediment
    bm = bmesh.new()
    for x in (X0 - PW / 2, X1 + PW / 2):
        cgeo.rounded_box(bm, (PW, FT, open_h + 0.2), 0.3, (x, yb, (open_h + 0.2) / 2), seg=2, flat=(2, 1, 6))
        # fluting (raised strips)
        for k in (-1, 0, 1):
            cgeo.rounded_box(bm, (0.6, 0.35, open_h - 6), 0.15, (x + 1.6 * k, front_y - FT - 0.1, open_h / 2 + 0.6),
                             seg=2, flat=(0, 0, 4), mat=1)
    cgeo.rounded_box(bm, (open_w + 2 * PW, FT, HH), 0.35, (cx, yb, open_h + HH / 2), seg=2, flat=(6, 1, 2))
    # pediment: a shallow arch over the header
    prof = []
    for i in range(33):
        a = math.pi * i / 32
        prof.append((cx - 16 * math.cos(a), open_h + HH + 5.5 * math.sin(a)))
    pv = [bm.verts.new((x, front_y - 0.2, z)) for x, z in prof]
    pv2 = [bm.verts.new((x, front_y - FT + 0.2, z)) for x, z in prof]
    for i in range(len(prof) - 1):
        bm.faces.new((pv[i], pv[i + 1], pv2[i + 1], pv2[i]))
    bm.faces.new(pv2)
    bm.faces.new(list(reversed(pv)))
    obj(bm, 'facade', [maroon, gold])
    # --- gold trims: the opening's frame, capitals, bases, the header's rails
    bm = bmesh.new()
    yt = front_y - FT - 0.15
    pts = [(X0 - 0.2, yt, 0.9), (X0 - 0.2, yt, open_h + 0.25), (X1 + 0.2, yt, open_h + 0.25), (X1 + 0.2, yt, 0.9)]
    cgeo.tube(bm, pts, [0.32] * 4, segs=12)
    for x in (X0 - PW / 2, X1 + PW / 2):
        cgeo.rounded_box(bm, (PW + 0.9, FT + 0.8, 1.5), 0.3, (x, yb, open_h - 0.9), seg=2, flat=(2, 1, 0))
        cgeo.rounded_box(bm, (PW + 1.0, FT + 0.9, 1.3), 0.3, (x, yb, 0.65), seg=2, flat=(2, 1, 0))
    for z in (open_h + 1.2, open_h + HH - 1.0):
        cgeo.tube(bm, [(X0 - PW, yt, z), (X1 + PW, yt, z)], [0.22, 0.22], segs=10)
    prof2 = [(cx - 16 * math.cos(math.pi * i / 32), yt, open_h + HH + 5.5 * math.sin(math.pi * i / 32))
             for i in range(33)]
    cgeo.tube(bm, prof2, [0.3] * len(prof2), segs=10)
    obj(bm, 'gold', [gold])
    # the crest: a giant gilded paperclip in the pediment (the house's emblem)
    try:
        from pdoom.fx import clips as C
        me = C.clip_mesh(0, name='theatre.crestclip', collide_pad=False)
        me.materials.clear()
        me.materials.append(gold)
        cr = bpy.data.objects.new('theatre.crest', me)
        coll.objects.link(cr)
        cr.location = (cx, yt - 0.3, open_h + HH + 2.4)
        cr.rotation_euler = (math.radians(90), 0, 0)
        cr.scale = (2.4, 2.4, 2.4)
        th.objs.append(cr)
    except Exception as e:  # noqa: BLE001
        print(f'[run] theatre: no clip crest ({e})')
    # --- side drapes (static, pleated, tied back)
    for side, x in (('L', X0 + 2.2), ('R', X1 - 2.2)):
        bm = bmesh.new()
        nx, nz = 18, 40
        grid = []
        for j in range(nz + 1):
            z = open_h * j / nz
            row = []
            tie = 0.55 + 0.45 * abs(z - open_h * 0.42) / (open_h * 0.58)
            for i in range(nx + 1):
                s = (i / nx - 0.5) * 5.0 * tie
                sx = 1 if side == 'L' else -1
                row.append(bm.verts.new((x + sx * (s + 1.0 * (1 - tie)), front_y + 0.5 + 0.45 * math.sin(i * 1.9), z)))
            grid.append(row)
        for j in range(nz):
            for i in range(nx):
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
        # the tie-back: a gold cord looped round the gathered drape at its pinch (the drape spans
        # x + sx * (0.45 +- 1.375), y front_y + 0.05 .. + 0.95 there)
        sx = 1 if side == 'L' else -1
        c, zt, yc = x + sx * 0.45, open_h * 0.42, front_y + 0.5
        gx, gy = 2.5 * 0.55 + 0.22, 0.45 + 0.24
        loop = []
        for k in range(33):
            a = 2 * math.pi * k / 32
            loop.append((c + gx * math.cos(a), yc + gy * math.sin(a), zt + 0.12 * math.sin(2 * a)))
        cgeo.tube(bm, loop, [0.16] * len(loop), segs=8, mat=1, cap0=False, cap1=False)
        # a short tassel hanging from the front of the cord
        tx = c + sx * 0.3
        cgeo.tube(bm, [(tx, yc - gy * 0.85, zt - 0.05), (tx, yc - gy * 0.95, zt - 1.3)], [0.13, 0.26], segs=8,
                  mat=1)
        obj(bm, f'drape{side}', [red, gold], sharp=None)
    # --- the curtain (festoon)
    th.curtain = _festoon(coll, th, X0 - 0.6, X1 + 0.6, front_y + 1.1, open_h + 0.6, red, gold)
    th.objs.append(th.curtain)
    # --- the apron and the footlights
    bm = bmesh.new()
    cgeo.rounded_box(bm, (open_w + 2 * PW + 1.5, 3.2, 1.2), 0.2, (cx, front_y - FT - 1.6, 0.6), seg=2, flat=(6, 1, 0))
    obj(bm, 'apron', [maroon])
    bm = bmesh.new()
    yf = front_y - FT - 1.3
    cgeo.tube(bm, [(X0 + 1.0, yf - 0.6, 1.25), (X1 - 1.0, yf - 0.6, 1.25)], [0.6, 0.6], segs=16)
    obj(bm, 'trough', [gold])
    n = 13
    for i in range(n):
        x = X0 + 2.5 + (open_w - 5.0) * i / (n - 1)
        m = looks.emitter(f'theatre.bulb{i}', '#FFD08A', 0.0)
        bm = bmesh.new()
        cgeo.uv_sphere(bm, 0.36, segs=14, rings=8, M=_T((x, yf + 0.1, 1.55)))
        obj(bm, f'bulb{i}', [m], sharp=None)
        th.bulbs.append(m)
    for j, u in enumerate((0.12, 0.37, 0.63, 0.88)):
        x = X0 + open_w * u
        L = kit.spot(f'theatre.foot{j}', (x, yf + 0.2, 1.8), (x, front_y + 3.0, 16.0), power=0.0, angle_deg=100,
                     blend=0.9, radius=1.2, color='#FFC67A', coll=coll)
        L.data.energy = 0.0
        th.spots.append((L.data, 30000.0))
        th.objs.append(L)
    # house lights on the facade (the gilding catches them), low from the stalls
    for j, x in enumerate((X0 - 3.0, X1 + 3.0)):
        L = kit.spot(f'theatre.house{j}', (x + (14 if j == 0 else -14), front_y - 40, 24.0), (x, front_y, 26.0),
                     power=0.0, angle_deg=30, blend=0.8, radius=2.0, color='#FFB27A', coll=coll)
        L.data.energy = 0.0
        L.data.volume_factor = 0.0      # light the facade only: no cones hanging in the haze at the frame edges
        th.spots.append((L.data, 110000.0))
        th.objs.append(L)
    L = kit.spot('theatre.crestlight', (cx, front_y - 40, 30.0), (cx, front_y, open_h + HH + 2.5), power=0.0,
                 angle_deg=16, blend=0.7, radius=1.0, color='#FFD9A0', coll=coll)
    L.data.energy = 0.0
    L.data.volume_factor = 0.0
    th.spots.append((L.data, 70000.0))
    th.objs.append(L)
    return th


def _festoon(coll, th, x0, x1, y0, hc, red, gold, nx=170, nz=70, nswag=7):
    """A pleated velvet curtain with shape keys: key k gathers it to rise k/NK in swags between lift cords."""
    wc = x1 - x0
    w = wc / nswag
    bm = bmesh.new()
    rest = []
    grid = []
    for j in range(nz + 1):
        z = hc * j / nz
        row = []
        for i in range(nx + 1):
            x = x0 + wc * i / nx
            y = y0 + 0.55 * math.sin(2 * math.pi * (x - x0) / 2.7) + 0.18 * math.sin(2 * math.pi * (x - x0) / 1.13 + 0.7)
            v = bm.verts.new((x, y, z))
            row.append(v)
            rest.append((x, y, z))
        grid.append(row)
    for j in range(nz):
        for i in range(nx):
            f = bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
            f.material_index = 1 if j < 2 else 0
            f.smooth = True
    me = bpy.data.meshes.new('theatre.curtain')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(red)
    me.materials.append(gold)
    ob = bpy.data.objects.new('theatre.curtain', me)
    coll.objects.link(ob)
    sm = ob.modifiers.new('thick', 'SOLIDIFY')
    sm.thickness = 0.12
    sm.offset = 0.0
    ob.shape_key_add(name='down')
    for k in range(1, NK + 1):
        r = k / NK
        sk = ob.shape_key_add(name=f'r{k}')
        S = 0.46 * w * _ss(0.0, 0.3, r) * (1 - 0.25 * r)
        lift = r * (hc - 5.0)
        for idx, (x, y, z) in enumerate(rest):
            u = ((x - x0) / w) % 1.0
            bell = 0.5 - 0.5 * math.cos(2 * math.pi * u)
            hem = max(0.0, lift - S * bell)
            c = (hc - hem) / hc
            d = hc - z
            dn = d * c
            zn = hc - dn
            # gathered fabric: horizontal swag folds bulging toward the house, deepest mid-swag
            fold = 0.5 + 0.5 * math.sin(2 * math.pi * d / 2.9)
            bul = 1.5 * (1 - c) * (0.35 + 0.65 * bell) * fold + 0.9 * (1 - c) * bell * (dn / max(hc - hem, 1e-3))
            yn = y0 + (y - y0) * (0.35 + 0.65 * c) - bul
            # the cords pull the fabric toward them a little
            xn = x + (-(u - 0.5) * 0.0)
            sk.data[idx].co = (xn, yn, zn)
    return ob


def _ss(a, b, x):
    u = min(1.0, max(0.0, (x - a) / (b - a)))
    return u * u * (3 - 2 * u)


def audience(coll, th, rows: int = 5, per_row: int = 13, *, t_on: float | None = None):
    """Tiered risers in front of the stage and a paperclip standing on each seat, facing the stage."""
    wood = looks.satin('theatre.riser', '#2A1A14', rough=0.6)
    carpet = looks.felt('theatre.carpet', '#3A0C12')
    objs = []
    y_front = th.front_y - 7.0
    depth, rise_h = 5.2, 0.55
    x0, x1 = th.X0 - 2, th.X1 + 2
    for k in range(rows):
        y = y_front - depth * k
        top = rise_h * (k + 1)
        bm = bmesh.new()
        cgeo.rounded_box(bm, (x1 - x0, depth, top), 0.12, ((x0 + x1) / 2, y - depth / 2, top / 2), seg=1,
                         flat=(8, 1, 0))
        cgeo.rounded_box(bm, (x1 - x0 - 0.4, depth - 0.3, 0.06), 0.02, ((x0 + x1) / 2, y - depth / 2, top + 0.02),
                         seg=1, flat=(8, 1, 0), mat=1)
        ob = cgeo.to_object(bm, f'theatre.riser{k}', coll, [wood, carpet])
        objs.append(ob)
    try:
        from pdoom.fx import clips as C
        me = C.clip_mesh(1)
    except Exception:
        me = _own_clip_mesh()
    for k in range(rows):
        y = y_front - depth * k - depth * 0.45
        top = rise_h * (k + 1)
        n = per_row - (k % 2)
        span = (th.X1 - th.X0) - 4.0
        for i in range(n):
            x = th.X0 + 2.0 + span * (i + (0.5 if k % 2 else 0.0)) / (per_row - 1)
            ob = bpy.data.objects.new(f'theatre.patron{k}.{i}', me)
            coll.objects.link(ob)
            h = lambda s: hash01(k * 31 + i, s)
            tilt = math.radians(6 * (h(1) - 0.5))
            turn = math.radians(18 * (h(2) - 0.5))
            ob.rotation_euler = (tilt, math.radians(90), math.radians(90) + turn)
            ob.location = (x + 0.4 * (h(3) - 0.5), y + 0.4 * (h(4) - 0.5), top + 1.62)
            objs.append(ob)
    th.objs.extend(objs)
    return objs


def _own_clip_mesh():
    """Fallback paperclip (if pdoom.fx.clips is missing): a wire bent into the Gem shape, 3.3 cm."""
    me = bpy.data.meshes.get('theatre.clip')
    if me:
        return me
    bm = bmesh.new()
    pts = [(-0.6, -0.13, 0), (1.2, -0.13, 0), (1.35, 0.02, 0), (1.2, 0.17, 0), (-1.3, 0.17, 0), (-1.5, -0.1, 0),
           (-1.3, -0.38, 0), (1.25, -0.38, 0), (1.62, 0, 0), (1.25, 0.38, 0), (-1.05, 0.38, 0)]
    cgeo.tube(bm, pts, [0.045] * len(pts), segs=8)
    me = bpy.data.meshes.new('theatre.clip')
    bm.to_mesh(me)
    bm.free()
    me.materials.append(SM.steel('theatre.steel'))
    return me


def marionette(coll, pts, *, top_z: float = 36.0, converge=None, sway_t=None):
    """Marionette strings: a thin thread from each point straight up toward a control bar above (off-frame)."""
    m = looks.satin('theatre.thread', '#F3EEE2', rough=0.5)
    objs = []
    cxy = converge
    for i, p in enumerate(pts):
        p = Vector(p)
        q = Vector((p.x, p.y, top_z))
        if cxy is not None:
            q.x = cxy[0] + (p.x - cxy[0]) * 0.5
            q.y = cxy[1] + (p.y - cxy[1]) * 0.5
        bm = bmesh.new()
        # two rings only, so a hooked bottom end keeps the thread straight
        cgeo.tube(bm, [p, q], [0.018, 0.018], segs=5, cap0=False, cap1=False)
        ob = cgeo.to_object(bm, f'theatre.string{i}', coll, [m], sharp=None)
        objs.append(ob)
    return objs


def hook_strings(objs, rig, bones, t: float):
    """Tie each string's bottom ring to a bone of `rig` (Hook modifier), bound at song time t (when the strings were
    built from the puppet's anchors), so the threads follow the head and hands every frame afterwards.
    Call after the puppet is baked."""
    sc = bpy.context.scene
    keep = (sc.frame_current, sc.frame_subframe)
    f = t * FPS
    sc.frame_set(int(math.floor(f)), subframe=f - math.floor(f))
    dg = bpy.context.evaluated_depsgraph_get()
    re = rig.evaluated_get(dg)
    for ob, bone in zip(objs, bones):
        zb = min(v.co.z for v in ob.data.vertices)
        idx = [v.index for v in ob.data.vertices if v.co.z < zb + 0.05]
        hm = ob.modifiers.new('hook', 'HOOK')
        hm.object = rig
        hm.subtarget = bone
        hm.vertex_indices_set(idx)
        hm.falloff_type = 'NONE'
        hm.strength = 1.0
        M = re.matrix_world @ re.pose.bones[bone].matrix
        hm.matrix_inverse = M.inverted() @ ob.matrix_world
    sc.frame_set(keep[0], subframe=keep[1])
