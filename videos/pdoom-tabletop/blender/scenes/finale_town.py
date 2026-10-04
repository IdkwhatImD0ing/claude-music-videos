"""finale, the town part: kicks 2-4, each a miniature on the modeller's cutting mat.

 K2  144.776-145.685  The room as a doll's-house model (1:6), front wall and ceiling left off: clips fill it to the
                      brim, rising; a paper lantern hangs from the ceiling beam and sinks into them; the tall night
                      window with the city behind, its curtains; clips spill out over the open front onto the mat.
 K3  145.685-146.594  The house (1:48 on a flocked baseboard): clips pour out of every lit window and the open front
                      door and heap up against the walls; picket fence, gravel path, street lamp, foam trees.
 K4  146.594-147.503  The street (1:100): two rows of houses, the middle ones pouring from their windows; the road is
                      a river of clips carrying a toy car along; street lamps. The tilt-shift view down the street.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import _nodes as N
from pdoom.sets import geo as sgeo
from pdoom.sets import materials as M

from scenes import finale_common as F
from scenes import finale_models as MD

FPS = tm.FPS
V = Vector
K2, K3, K4, K5 = F.KICKS[1], F.KICKS[2], F.KICKS[3], F.KICKS[4]
O2, O3, O4 = V((3000.0, 0.0, 0.0)), V((6000.0, 0.0, 0.0)), V((9000.0, 0.0, 0.0))


def build():
    room()
    house_set()
    street()


def _finish(coll, t_on, t_off):
    F.show(F.objects_in(coll), F.edge(t_on), F.edge(t_off))


def _table(name, coll, O, size=(600.0, 500.0), z=-1.5):
    t = F.grid_mesh(name, size, 1, coll=coll, loc=O + V((0.0, 0.0, z)), mats=[MD.cutting_mat()])
    return t


# ================================================================================================ K2: the room


def _mass_mesh(name, coll, O, x0, x1, y_back, y_front, level, run, toe_z, spread=6.0, nx=48, ny_top=30, ny_t=12):
    """The clip mass in the room: a flat-ish top at `level` from the back wall to the open front, then a talus
    spilling down to the table. Returns (bmesh verts coords list) for shape keys: call with different level/run."""
    rows = []
    for j in range(ny_top + 1):
        y = y_back - (y_back - y_front) * j / ny_top
        rows.append(('top', y, 0.0))
    for j in range(1, ny_t + 1):
        v = j / ny_t
        rows.append(('tal', y_front - run * v, v))
    co = []
    for kind, y, v in rows:
        for i in range(nx + 1):
            u = i / nx
            if kind == 'top':
                x = x0 + (x1 - x0) * u
                z = level + 0.5 * math.sin(x * 0.31 + y * 0.17) + 0.35 * math.sin(x * 0.11 - y * 0.23)
                # a slight dome toward the middle, lower at the walls (clips pile toward where they fall)
                z += 0.9 * (1 - (2 * u - 1) ** 2)
            else:
                xa, xb = x0 - spread * v, x1 + spread * v
                x = xa + (xb - xa) * u
                s = 1 - (1 - v) ** 1.7
                z = level + (toe_z - level) * s + 0.8 * math.sin(x * 0.27 + v * 4.0) * v * (1 - v)
            co.append((x + O.x, y + O.y, z + O.z))
    return co, len(rows), nx


def _grid_obj(name, coll, co, nrows, nx):
    bm = bmesh.new()
    vs = [bm.verts.new(c) for c in co]
    for j in range(nrows - 1):
        for i in range(nx):
            a = j * (nx + 1) + i
            bm.faces.new((vs[a], vs[a + 1], vs[a + nx + 2], vs[a + nx + 1]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob


def _shape(ob, name, co):
    if ob.data.shape_keys is None:
        ob.shape_key_add(name='Basis')
    sk = ob.shape_key_add(name=name)
    for i, c in enumerate(co):
        sk.data[i].co = c
    return sk


def room():
    coll = kit.collection('finale.k2')
    O = O2
    W, D, H, T = 70.0, 52.0, 42.0, 1.2
    x0, x1, y0, y1 = -W / 2, W / 2, -D / 2, D / 2
    _table('k2.table', coll, O)
    floorm = M.tex_mat('k2.floor', 'floor_wood', 28, val=0.6, sat=0.8, rough=(0.35, 0.7), normal=0.6, coat=0.2,
                       fallback='#3A2A20')
    F.box('k2.floor', (W + 2 * T, D + T, 1.5), O + V((0, T / 2, -0.75)), floorm, coll)
    paper = MD.wallpaper('k2.wallpaper', '#9FAE92', '#BCC6A8', stripe=1.3)
    trim = MD.paint('k2.trim', '#F1ECE0', 0.45)
    bm = bmesh.new()
    WX0, WX1, WZ0, WZ1 = -11.5, 11.5, 19.0, 39.0              # the tall window in the back wall
    MD.wall(bm, W + 2 * T, H, T, [(WX0 + W / 2 + T, WX1 + W / 2 + T, WZ0, WZ1)],
            M=Matrix.Translation(O + V((x0 - T, y1, 0))))
    MD.wall(bm, D + T, H, T, (), M=Matrix.Translation(O + V((x0, y0, 0))) @ Matrix.Rotation(math.radians(90), 4, 'Z'))
    MD.wall(bm, D + T, H, T, (), M=Matrix.Translation(O + V((x1, y1 + T, 0))) @ Matrix.Rotation(math.radians(-90), 4,
                                                                                                 'Z'))
    MD.obj(bm, 'k2.walls', coll, [paper])
    # crown moulding, skirting on the wall tops, window frame and glazing bars, curtain rod
    bm = bmesh.new()
    MD._box_bm(bm, O.x + x0 - T - 0.3, O.x + x1 + T + 0.3, O.y + y1 - 0.5, O.y + y1 + T + 0.3, H - 0.2, H + 0.9)
    for sx in (-1, 1):
        xa = O.x + (x0 - T - 0.3 if sx < 0 else x1 - 0.5)
        MD._box_bm(bm, xa, xa + T + 0.8, O.y + y0, O.y + y1 + T, H - 0.2, H + 0.9)
    fy0, fy1 = O.y + y1 - 0.3, O.y + y1 + T + 0.3
    for (a, b, c, d) in ((WX0 - 0.6, WX0, WZ0 - 0.6, WZ1 + 0.6), (WX1, WX1 + 0.6, WZ0 - 0.6, WZ1 + 0.6),
                         (WX0, WX1, WZ1, WZ1 + 0.6), (WX0 - 1.0, WX1 + 1.0, WZ0 - 1.0, WZ0),
                         (-0.25, 0.25, WZ0, WZ1), (WX0, WX1, (WZ0 + WZ1) / 2 - 0.25, (WZ0 + WZ1) / 2 + 0.25),
                         (WX0, WX1, WZ0 + (WZ1 - WZ0) * 0.25 - 0.2, WZ0 + (WZ1 - WZ0) * 0.25 + 0.2),
                         (WX0, WX1, WZ0 + (WZ1 - WZ0) * 0.75 - 0.2, WZ0 + (WZ1 - WZ0) * 0.75 + 0.2),
                         (WX0 + (WX1 - WX0) * 0.25 - 0.2, WX0 + (WX1 - WX0) * 0.25 + 0.2, WZ0, WZ1),
                         (WX0 + (WX1 - WX0) * 0.75 - 0.2, WX0 + (WX1 - WX0) * 0.75 + 0.2, WZ0, WZ1)):
        MD._box_bm(bm, O.x + a, O.x + b, fy0 + 0.4, fy1 - 0.4, c, d)
    MD.obj(bm, 'k2.trim', coll, [trim])
    rod = bmesh.new()
    cgeo_tube(rod, [O + V((WX0 - 5, y1 - 1.6, WZ1 + 1.4)), O + V((WX1 + 5, y1 - 1.6, WZ1 + 1.4))], 0.35)
    MD.obj(rod, 'k2.rod', coll, [M.brass('k2.brass', '#C8A15A', 0.3)])
    # curtains: pleated velvet panels either side of the window
    vel = M.solid('k2.velvet', '#8E3B4A', rough=0.85, sheen=1.0)
    for sx in (-1, 1):
        bm = bmesh.new()
        xa = WX0 - 5.0 if sx < 0 else WX1 - 1.0
        grid = []
        nxp, nzp = 18, 24
        for j in range(nzp + 1):
            z = WZ0 - 3 + (WZ1 + 1.2 - (WZ0 - 3)) * j / nzp
            row = []
            for i in range(nxp + 1):
                x = xa + 6.0 * i / nxp
                row.append(bm.verts.new(O + V((x, y1 - 1.3 - 0.45 * math.sin(i * 1.7) - 0.2, z))))
            grid.append(row)
        for j in range(nzp):
            for i in range(nxp):
                bm.faces.new((grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]))
        cur = MD.obj(bm, f'k2.curtain{sx}', coll, [vel], sharp=None)
        s = cur.modifiers.new('thick', 'SOLIDIFY')
        s.thickness = 0.15
    # the night outside the window: a painted backdrop card with a skyline of lit windows
    sky = F.grid_mesh('k2.sky', (56.0, 26.0), 1, coll=coll, loc=O + V((0, y1 + 13.0, 13.0)))
    sky.rotation_euler = (math.radians(90), 0, 0)
    sky.data.materials.append(_night_card('k2.skycard'))
    bm = bmesh.new()
    rng = random.Random(7)
    x = -30.0
    while x < 30:
        w = rng.uniform(4, 9)
        h = rng.uniform(9, 22)
        MD._box_bm(bm, O.x + x, O.x + x + w, O.y + y1 + 7 + rng.uniform(0, 3), O.y + y1 + 10, -2, h)
        x += w + rng.uniform(0.2, 1.5)
    MD.obj(bm, 'k2.skyline', coll, [MD.facade('k2.facade', '#14161B', cell=(1.1, 1.5), win=(0.5, 0.45), lit=0.3,
                                             strength=4.0)])
    # the ceiling beam, the lantern on its cord
    LZ, LR = 36.2, 2.8
    bm = bmesh.new()
    # a taut wire from wall top to wall top, the lantern's cord hanging from it
    cgeo_tube(bm, [O + V((x0 - T / 2, 0, H + 1.2)), O + V((0, 0, H + 0.8)), O + V((x1 + T / 2, 0, H + 1.2))], 0.07)
    cgeo_tube(bm, [O + V((0, 0, H + 0.8)), O + V((0, 0, LZ + LR - 0.2))], 0.07)
    MD.obj(bm, 'k2.cord', coll, [MD.paint('k2.cordm', '#1A1A1A', 0.6)])
    lant = kit.sphere('k2.lantern', LR, tuple(O + V((0, 0, LZ))), coll=coll, subdiv=4)
    lant.scale = (1.0, 1.0, 0.9)
    lant.data.materials.append(_lantern_mat())
    lant.visible_shadow = False
    # the clips: a mass to the brim, rising, spilling out of the open front
    lv0, lv1 = 30.5, 37.8
    co0, nr, nx = _mass_mesh('k2.mass', coll, O, x0 + 0.05, x1 - 0.05, y1 - 0.05, y0, lv0, 15.0, -1.5)
    co1, _, _ = _mass_mesh('k2.mass', coll, O, x0 + 0.05, x1 - 0.05, y1 - 0.05, y0, lv1, 23.0, -1.5)
    mass = _grid_obj('k2.mass', coll, co0, nr, nx)
    sk = _shape(mass, 'rise', co1)
    sgeo.keyp(sk, 'value', K2 - 0.3, -0.04, interp='LINEAR')
    sgeo.keyp(sk, 'value', K3 + 0.2, 1.04, interp='LINEAR')
    F.carpet('k2.clips', mass, scale=0.28, density=0.34, layers=2, lod=2, coll=coll, seed=61, core=F.core_mat())
    # clips pouring over the front lip
    F.stream('k2.spill', source=(tuple(O + V((0, y0 - 1.0, lv0 + 1.5))), (60.0, 1.0)), t0=K2 - 1.0, t1=K3 + 0.2,
             rate=420.0, direction=(0, -1, 0.1), speed=(6.0, 20.0), scale=0.28, floor=-1.5, gscale=0.4, cone=25.0,
             seed=62, coll=coll)
    # lights: the lantern, the moon through the window, the modeller's desk lamps
    L = kit.point('k2.lantern.light', tuple(O + V((0, 0, LZ))), power=5200.0, radius=2.4, color='#FFC27A', coll=coll)
    win = kit.area('k2.window.light', tuple(O + V((0, y1 + 10.0, 30.0))), tuple(O + V((0, 0, 20.0))), power=30000.0,
                   size=24.0, color='#8FA8E0', coll=coll)
    key = kit.area('k2.key', tuple(O + V((-70.0, -70.0, 150.0))), tuple(O + V((0, -5, 20))), power=110000.0,
                   size=90.0, color='#C7D2EE', coll=coll)
    rim = kit.area('k2.rim', tuple(O + V((95.0, 30.0, 90.0))), tuple(O + V((0, 0, 30))), power=40000.0, size=60.0,
                   color='#FFD3A0', coll=coll)
    back = kit.area('k2.back', tuple(O + V((0.0, 70.0, 95.0))), tuple(O + V((0, -12, 34))), power=90000.0,
                    size=70.0, color='#DCE4F4', coll=coll)
    for l in (win, key, rim, back):
        l.data.volume_factor = 0.0
    _finish(coll, K2, K3)
    # camera: high front, pulling back and up
    F.Cam('cam.k2', K2, K3, F.path(O + V((9.0, -70.0, 124.0)), O + V((12.0, -92.0, 156.0)), K2, K3 + 0.1),
          F.path(O + V((0.0, 10.0, 26.0)), O + V((0.0, 10.0, 24.0)), K2, K3 + 0.1), lens=45.0, fstop=2.8,
          focus=O + V((0.0, -4.0, 34.0)), coll=kit.collection('finale.cams'))


def cgeo_tube(bm, pts, r, segs=10):
    from pdoom.chars import geo as cgeo
    cgeo.tube(bm, [V(p) for p in pts], [r] * len(pts), segs=segs)


def _lantern_mat():
    m = bpy.data.materials.get('k2.lantern')
    if m:
        return m
    m = M.tex_mat('k2.lantern', 'paper', 8, tint='#FFE6C0', sat=0.2, rough=(0.7, 0.9), normal=0.4,
                  fallback='#FFE6C0')
    b = M.principled(m)
    M.setin(b, 'Emission Color', kit.srgb('#FFB866'))
    M.setin(b, 'Emission Strength', 7.0)
    return m


def _night_card(name):
    """A painted night sky: deep blue to a warmer glow near the horizon (emissive)."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (0, 0, 0, 1))
    tc = M.node(nt, 'ShaderNodeTexCoord', (-800, 0))
    sep = M.node(nt, 'ShaderNodeSeparateXYZ', (-600, 0))
    M.link(nt, M.sout(tc, 'Generated'), M.sin(sep, 'Vector'))
    ramp = M.node(nt, 'ShaderNodeValToRGB', (-400, 0))
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb('#4A3550')
    cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb('#070B18')
    e = cr.elements.new(0.3)
    e.color = kit.srgb('#1C2748')
    M.link(nt, M.sout(sep, 'Y'), M.sin(ramp, 'Factor'))
    M.link(nt, M.sout(ramp, 'Color'), M.sin(b, 'Emission Color'))
    M.setin(b, 'Emission Strength', 1.4)
    return m


# ================================================================================================ K3: the house


def house_set():
    coll = kit.collection('finale.k3')
    O = O3
    _table('k3.table', coll, O)
    glow = F.window_glow('k3.win', '#FFC27A', 6.0)
    wins = [('front', -8.5, 12.5, 4.4, 5.4), ('front', 8.5, 12.5, 4.4, 5.4), ('front', -10.0, 2.6, 4.4, 5.4),
            ('front', 10.0, 2.6, 4.4, 5.4), ('left', 0.0, 12.5, 4.2, 5.2), ('left', 0.0, 2.6, 4.2, 5.2),
            ('right', -2.0, 12.5, 4.2, 5.2), ('right', -2.0, 2.6, 4.2, 5.2)]
    hs = MD.house('k3.house', coll, loc=O, size=(32.0, 20.0, 21.0), ridge=10.0, windows=wins, door=(0.0, 4.6, 8.6),
                  glow=glow)
    # baseboard: lawn, path, fence, pavement, road, a porch lamp, a street lamp, trees
    lawn = F.grid_mesh('k3.lawn', (130.0, 96.0), 1, coll=coll, loc=O + V((0, 2.0, 0.0)),
                       mats=[F.flocking('k3.grass', '#4F7A2A')])
    F.box('k3.board', (131.0, 97.0, 3.0), O + V((0, 2.0, -1.55)), MD.paint('k3.boardedge', '#2B2118', 0.7), coll)
    F.box('k3.path', (5.0, 28.0, 0.12), O + V((0, -24.0, 0.06)), MD.gravel(), coll)
    F.box('k3.pave', (130.0, 8.0, 0.4), O + V((0, -42.0, 0.2)), MD.paint('k3.paving', '#8E8C86', 0.85), coll)
    F.box('k3.road', (130.0, 10.0, 0.1), O + V((0, -51.0, 0.05)), MD.asphalt(), coll)
    MD.fence('k3.fence.l', coll, O + V((-62.0, -37.5, 0.0)), O + V((-3.5, -37.5, 0.0)))
    MD.fence('k3.fence.r', coll, O + V((3.5, -37.5, 0.0)), O + V((62.0, -37.5, 0.0)))
    MD.tree('k3.tree1', coll, tuple(O + V((-40.0, 16.0, 0.0))), height=30.0, radius=10.0, seed=3)
    MD.tree('k3.tree2', coll, tuple(O + V((44.0, -18.0, 0.0))), height=24.0, radius=8.0, seed=5, color='#4A6B34')
    MD.tree('k3.tree3', coll, tuple(O + V((34.0, 30.0, 0.0))), height=34.0, radius=11.0, seed=8)
    lamp_objs, head = MD.street_lamp('k3.lamp', coll, tuple(O + V((26.0, -40.0, 0.0))), height=13.0, arm=2.6,
                                     yaw=180.0)
    sl = kit.spot('k3.lamp.light', tuple(head), tuple(O + V((10.0, -18.0, 0.0))), power=26000.0, angle_deg=95,
                  blend=0.8, radius=0.6, color='#FFC77A', coll=coll)
    sl.data.volume_factor = 0.0
    porch = kit.point('k3.porch', tuple(O + V((0.0, -12.5, 9.8))), power=900.0, radius=0.4, color='#FFD08A',
                      coll=coll)
    # clips: out of every opening, heaping against the walls
    for k, (c, n, (w, h), kind) in enumerate(hs.openings):
        src = c + n * 0.7 - V((0, 0, h * 0.2))
        rate = 520.0 if kind == 'door' else 300.0
        d = n + V((0, 0, 0.12 if kind != 'door' else 0.0))
        F.stream(f'k3.pour{k}', source=(tuple(src), (w * 0.7, h * 0.3)), t0=K3 - 1.6, t1=K4 + 0.2,
                 rate=rate * 4.5, direction=tuple(d), speed=(9.0, 18.0) if kind != 'door' else (6.0, 12.0),
                 scale=0.16, floor=0.0, gscale=0.2, cone=14.0, seed=70 + k, coll=coll)
        # the room's light spilling out of the opening (one-sided: it lights the pour and the heap, not the wall)
        sp = kit.area(f'k3.spill{k}', tuple(c + n * 0.9), tuple(c + n * 3.0 - V((0, 0, 1.2))), power=500.0,
                      size=max(w, h), color='#FFC27A', coll=coll)
        sp.data.volume_factor = 0.0
    mound = _mound('k3.mound', coll, O, 16.0, 10.0, hs.openings, (2.0, 15.0), (4.8, 20.0))
    sk = _shape(mound['obj'], 'rise', mound['co1'])
    sgeo.keyp(sk, 'value', K3 - 0.3, -0.05, interp='LINEAR')
    sgeo.keyp(sk, 'value', K4 + 0.2, 1.05, interp='LINEAR')
    F.carpet('k3.clips', mound['obj'], scale=0.16, density=0.34, layers=2, lod=2, coll=coll, seed=66,
             core=F.core_mat())
    # the moon and a soft studio fill
    moon = kit.area('k3.moon', tuple(O + V((120.0, 140.0, 210.0))), tuple(O + V((0, 0, 8))), power=900000.0,
                    size=160.0, color='#8FA8E0', coll=coll)
    fill = kit.area('k3.fill', tuple(O + V((-90.0, -150.0, 170.0))), tuple(O + V((0, 0, 8))), power=150000.0,
                    size=120.0, color='#C8C8D0', coll=coll)
    for l in (moon, fill):
        l.data.volume_factor = 0.0
    _finish(coll, K3, K4)
    F.Cam('cam.k3', K3, K4, F.path(O + V((-34.0, -84.0, 62.0)), O + V((-45.0, -112.0, 86.0)), K3, K4 + 0.1),
          F.path(O + V((-1.0, -4.0, 11.0)), O + V((-1.0, -4.0, 9.0)), K3, K4 + 0.1), lens=50.0, fstop=3.2,
          focus=O + V((0.0, -11.0, 12.0)), coll=kit.collection('finale.cams'))


def _mound_h(x, y, W, D, openings, H, R, O):
    """Heap height around a W x D footprint: highest against the walls, bumps under the openings."""
    dx = max(abs(x) - W / 2, 0.0)
    dy = max(abs(y) - D / 2, 0.0)
    d = math.hypot(dx, dy)
    inside = abs(x) < W / 2 and abs(y) < D / 2
    if inside:
        return -1.0
    r = R * (1.0 + 0.18 * math.sin(math.atan2(y, x) * 5.0) + 0.1 * math.sin(math.atan2(y, x) * 11.0 + 1.0))
    h = H * max(0.0, 1 - d / r) ** 1.6
    for (c, n, (w, hh), kind) in openings:
        p = V((x, y, 0)) - V((c.x - O.x, c.y - O.y, 0))
        q = p.length
        h += (H * 0.8 if kind == 'door' else H * 0.55) * math.exp(-(q / (6.0 if kind == 'door' else 4.5)) ** 2)
    return h


def _mound_co(O, W2, D2, openings, H, R, keep, sink=None):
    out = []
    for (x, y) in keep:
        h = _mound_h(x, y, 2 * W2, 2 * D2, openings, H, R, O)
        if sink is not None and -0.5 < h < 0.05:
            h = sink                     # not reached yet: under the lawn
        out.append((O.x + x, O.y + y, O.z + h))
    return out


def _mound(name, coll, O, W2, D2, openings, s0, s1, step=1.2):
    """A heap of clips around the house (a grid, trimmed to where the heap will reach): s0 = (height, radius) at
    the start, s1 at the end (the 'rise' shape key: co1)."""
    H, R = s1
    Rm = R * 1.35 + 2.0
    xs = [(-W2 - Rm) + step * i for i in range(int(2 * (W2 + Rm) / step) + 1)]
    ys = [(-D2 - Rm) + step * j for j in range(int(2 * (D2 + Rm) / step) + 1)]
    bm = bmesh.new()
    idx = {}
    keep = []
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            dx = max(abs(x) - W2, 0.0)
            dy = max(abs(y) - D2, 0.0)
            if math.hypot(dx, dy) < Rm:
                idx[(i, j)] = len(keep)
                keep.append((x, y))
    co = _mound_co(O, W2, D2, openings, H, R, keep)
    co0 = _mound_co(O, W2, D2, openings, s0[0], s0[1], keep, sink=-0.35)
    vs = [bm.verts.new(c) for c in co0]
    for (i, j), a in idx.items():
        b, c, d = idx.get((i + 1, j)), idx.get((i + 1, j + 1)), idx.get((i, j + 1))
        if b is None or c is None or d is None:
            continue
        zs = [co[k][2] - O.z for k in (a, b, c, d)]
        if max(zs) < 0.02 or min(zs) < -0.5:
            continue
        bm.faces.new((vs[a], vs[b], vs[c], vs[d]))
    # keep vertex order (shape keys index by vertex): loose verts stay (they don't render)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return {'obj': ob, 'keep': keep, 'co1': co}


# ================================================================================================ K4: the street


HOUSE_COLS = [('#E9DFC6', '#3B4048'), ('#C9D3C0', '#4A3A34'), ('#B5543E', '#33363C'), ('#D8C99A', '#4E4038'),
              ('#AFC3D1', '#3B4048'), ('#E6D4C4', '#5A3B30'), ('#F0E8D8', '#2F3338')]


def street():
    coll = kit.collection('finale.k4')
    O = O4
    _table('k4.table', coll, O, size=(900.0, 700.0))
    rng = random.Random(12)
    F.box('k4.base', (330.0, 90.0, 1.2), O + V((0, 0, -0.6)), F.flocking('k4.grass', '#34502A'), coll)
    F.box('k4.pave.n', (330.0, 2.6, 0.35), O + V((0, 6.9, 0.18)), MD.paint('k4.paving', '#8E8C86', 0.85), coll)
    F.box('k4.pave.s', (330.0, 2.6, 0.35), O + V((0, -6.9, 0.18)), MD.paint('k4.paving', '#8E8C86', 0.85), coll)
    road = F.box('k4.road', (330.0, 11.2, 0.1), O + V((0, 0, 0.05)), F.glitter('k4.glitter', scale=9.0), coll)
    glow = F.window_glow('k4.win', '#FFC27A', 6.0)
    pour_houses = []
    for side in (-1, 1):
        x = -150.0 + rng.uniform(0, 4)
        i = 0
        while x < 150.0:
            w = rng.uniform(6.2, 8.6)
            d = rng.uniform(6.0, 7.5)
            hgt = rng.uniform(5.2, 7.2)
            wall_c, roof_c = HOUSE_COLS[rng.randrange(len(HOUSE_COLS))]
            cx = x + w / 2
            y = side * (8.6 + d / 2)
            yaw = 0.0 if side > 0 else 180.0
            near = abs(cx) < 42.0
            name = f'k4.h{side}.{i}'
            if near:
                wins = [('front', -w * 0.24, hgt * 0.58, 1.3, 1.5), ('front', w * 0.24, hgt * 0.58, 1.3, 1.5),
                        ('front', -w * 0.24, hgt * 0.12, 1.3, 1.5)]
                hs = MD.house(name, coll, loc=O + V((cx, y, 0.0)), yaw=yaw, size=(w, d, hgt), ridge=hgt * 0.45,
                              windows=wins, door=(w * 0.22, 1.3, hgt * 0.4), glow=glow,
                              wall_mat=MD.clapboard(f'k4.clap.{wall_c}', wall_c, board=0.3),
                              roof_mat=MD.brickish(f'k4.roof.{roof_c}', roof_c, roof_c, mortar='#1E2024',
                                                   size=(0.3, 0.2), msize=0.02),
                              chimney=rng.random() < 0.6, over=0.4, thick=0.3, recess=0.2)
                pour_houses.append(hs)
            else:
                fac = MD.facade(f'k4.fac.{wall_c}', wall_c, cell=(1.8, 2.2), win=(0.42, 0.42), lit=0.5,
                                strength=5.0, seed=rng.random() * 10)
                MD.house(name, coll, loc=O + V((cx, y, 0.0)), yaw=yaw, size=(w, d, hgt), ridge=hgt * 0.45,
                         windows=None, door=None, glow=glow, wall_mat=fac,
                         roof_mat=MD.brickish(f'k4.roof.{roof_c}', roof_c, roof_c, mortar='#1E2024',
                                              size=(0.3, 0.2), msize=0.02),
                         chimney=rng.random() < 0.6, over=0.4, thick=0.3, frames=False)
            if rng.random() < 0.35:
                MD.tree(f'k4.tree{side}.{i}', coll, tuple(O + V((x + w + 0.9, side * 13.0, 0.0))), height=9.0,
                        radius=2.6, seed=i * 7 + side)
                x += 2.2
            x += w + rng.uniform(0.3, 1.2)
            i += 1
    for side in (-1, 1):
        x = -150.0 + rng.uniform(0, 6)
        i = 0
        while x < 150.0:
            w = rng.uniform(6.0, 9.0)
            d = rng.uniform(6.0, 7.5)
            hgt = rng.uniform(5.0, 7.6)
            wall_c, roof_c = HOUSE_COLS[rng.randrange(len(HOUSE_COLS))]
            fac = MD.facade(f'k4.fac.{wall_c}', wall_c, cell=(1.8, 2.2), win=(0.42, 0.42), lit=0.5, strength=5.0,
                            seed=rng.random() * 10)
            MD.house(f'k4.b{side}.{i}', coll, loc=O + V((x + w / 2, side * (8.6 + 7.5 + 7.0 + d / 2), 0.0)),
                     yaw=180.0 if side > 0 else 0.0, size=(w, d, hgt), ridge=hgt * 0.45, windows=None, door=None,
                     glow=glow, wall_mat=fac,
                     roof_mat=MD.brickish(f'k4.roof.{roof_c}', roof_c, roof_c, mortar='#1E2024', size=(0.3, 0.2),
                                          msize=0.02),
                     chimney=rng.random() < 0.6, over=0.4, thick=0.3, frames=False)
            if rng.random() < 0.5:
                MD.tree(f'k4.btree{side}.{i}', coll, tuple(O + V((x + w + 1.0, side * 19.5, 0.0))), height=10.0,
                        radius=3.0, seed=i * 11 + side)
                x += 2.5
            x += w + rng.uniform(0.3, 1.2)
            i += 1
    # pours from the near houses' windows and doors
    k = 0
    for hs in pour_houses:
        for (c, n, (w, h), kind) in hs.openings:
            if rng.random() < 0.25:
                continue
            F.stream(f'k4.pour{k}', source=(tuple(c + n * 0.3), (w * 0.7, h * 0.3)), t0=K4 - 1.5, t1=K5 + 0.2,
                     rate=110.0 if kind != 'door' else 180.0, direction=tuple(n + V((0, 0, 0.1))), speed=(4.0, 10.0),
                     scale=0.08, floor=0.4, gscale=0.1, cone=25.0, seed=100 + k, coll=coll)
            k += 1
    # the river of clips: a heaped strip along the street that flows toward +x
    riv = F.grid_mesh('k4.river', (96.0, 16.2), (96, 12), coll=coll, loc=O + V((0.0, 0.0, 0.0)),
                      height=lambda x, y: 0.45 + 0.55 * (1 - (y / 8.1) ** 2) + 0.12 * math.sin(x * 0.9 + y * 1.3))
    kit.key(riv, 'location', K4 - 0.2, tuple(O + V((-1.2, 0.0, 0.0))), interp='LINEAR')
    kit.key(riv, 'location', K5 + 0.2, tuple(O + V((6.0, 0.0, 0.0))), interp='LINEAR')
    F.carpet('k4.clips', riv, scale=0.08, density=0.34, layers=1, lod=3, coll=coll, seed=91, core=F.core_mat())
    car = MD.toy_car('k4.car', coll, (0, 0, 0), yaw=8.0, size=0.9)
    carp = kit.empty('k4.car.root', tuple(O + V((-8.0, -1.6, 0.25))), coll)
    for ob in car:
        ob.parent = carp
    kit.key(carp, 'location', K4 - 0.2, tuple(O + V((-9.2, -1.7, 0.25))), interp='LINEAR')
    kit.key(carp, 'location', K5 + 0.2, tuple(O + V((-2.0, -1.2, 0.3))), interp='LINEAR')
    kit.key(carp, 'rotation_euler', K4 - 0.2, (0.05, -0.08, math.radians(8)), interp='LINEAR')
    kit.key(carp, 'rotation_euler', K5 + 0.2, (-0.06, 0.05, math.radians(19)), interp='LINEAR')
    # street lamps both sides, warm pools on the clip river
    for j, x in enumerate(range(-126, 127, 18)):
        side = 1 if j % 2 else -1
        objs, head = MD.street_lamp(f'k4.lamp{j}', coll, tuple(O + V((x, side * 7.4, 0.35))), height=4.6, arm=1.2,
                                    yaw=0.0 if side > 0 else 180.0, glow=16.0)
        if abs(x) < 80:
            kit.point(f'k4.lamp{j}.light', tuple(head - V((0, 0, 0.3))), power=900.0, radius=0.35,
                      color='#FFC77A', coll=coll)
    moon = kit.area('k4.moon', tuple(O + V((220.0, 60.0, 150.0))), tuple(O + V((0, 0, 0))), power=1.3e6,
                    size=120.0, color='#8FA8E0', coll=coll)
    fill = kit.area('k4.fill', tuple(O + V((-100.0, -120.0, 160.0))), tuple(O + V((0, 0, 0))), power=200000.0,
                    size=120.0, color='#B8C4E0', coll=coll)
    for l in (moon, fill):
        l.data.volume_factor = 0.0
    _finish(coll, K4, K5)
    F.Cam('cam.k4', K4, K5, F.path(O + V((-92.0, -40.0, 52.0)), O + V((-116.0, -50.0, 68.0)), K4, K5 + 0.1),
          F.path(O + V((6.0, 0.5, 0.0)), O + V((6.0, 0.5, -1.0)), K4, K5 + 0.1), lens=50.0, fstop=2.8,
          focus=O + V((-6.0, 0.0, 2.0)), coll=kit.collection('finale.cams'))
