"""The `backprop` scene's computer sequence: the model's keyed teeter and fall off the shelf, the shatter (fx.fracture
+ fx.rigid, baked), the keyed pieces that must land where the cameras look (the VON NEUMANN plaque and the hero tube
that rolls into the domino), the sparks, the dying glow of lamps and filaments, and the stray marble's flight.

World layout: the shelf's left side at x 22 and front edge at y -10 (top at z 13.5); the model's plinth centre
starts at VN0. The model tips forward about the shelf's front edge (an axis along x).
"""
from __future__ import annotations

import math

import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import fracture, rigid, vis
from pdoom.sets import geo
from pdoom.timing import FPS

from scenes import backprop_computer as VN
from scenes import backprop_run as RUN

SHELF = Vector((22.0, -10.0, 0.0))          # the shelf's left side and front edge (world)
VN0 = Vector((29.0, -6.3, 13.5))            # the model's plinth bottom centre on the shelf
PIV_Y, PIV_Z = SHELF.y, 13.5                # the shelf's front edge (the tipping axis runs along x)
COM_LOCAL = Vector((0.0, 0.0, 5.0))
T_OFF, T_HIT = 77.735, 77.79                # the stray leaves its chute; hits the computer ("Now" 77.72)
T_TEETER, T_TIP = 77.93, 78.82              # rocking on the edge ("von" 78.16); tips over on "Neumann's"
F_BREAK = 1903                              # last keyed frame; the pieces hit the desk on 1904 (79.333, the beat)
DOMINO = Vector((44.0, -27.0, 0.0))
T_TAP = 81.87
T_COLLIDE = 79.46                           # the flying hero tube and plaque start to push shards (mid-air)
LANE_Y = (-28.75, -24.95)                   # the rolling hero tube's lane (its base face, pins and glass tip)
# The burst's velocity roll (0: the original seeds 7, 8, 9). The hero tube and the plaque are colliders, so the tube
# would shove any shard lying in its lane on into the domino (not a collider). Roll 3 was picked by a search over
# rolls 0-23 (a fresh build each; the sim is chaotic, so any change to the bodies needs a new search): the only rolls
# where no debris touches the domino, with one shard nudged as the tube lands. bake_burst logs the check each build.
BURST_ROLL = 3
LANE_MIN = 1.2                              # glass crumbs smaller than this may lie in the lane (the tube nudges them)
PLAQUE_LAND = Vector((32.6, -29.6, 0.07))
DOMINO_YAW = -60.0
PTS = [Vector((sx * 6.5, sy * 3.4, 0.0)) for sx in (-1, 1) for sy in (-1, 1)] + \
      [Vector((sx * 6.0, sy * 3.0, 9.5)) for sx in (-1, 1) for sy in (-1, 1)] + \
      [Vector((x, 0.3, 12.6)) for x in VN.TUBE_X]
G = Vector((0.0, 0.0, -981.0))


def frames(f0: int, f1: int):
    """Scene frames to key a per-frame motion on, f0..f1 inclusive: every whole frame at 24 fps, every output frame
    (fractional scene frames) in a smooth 60 fps build, so the render samples the real path, not 24 fps chords."""
    return tm.out_frames(f0, f1) if tm.SMOOTH else range(f0, f1 + 1)


def per_frame(owner, path, fn, t0, t1, *, index=-1, interp='LINEAR'):
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    for f in frames(f0, f1):
        geo.keyp(owner, path, f / FPS, fn(f / FPS), interp=interp, index=index)


def _ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def base_matrix(t):
    """The model on the shelf: the lurch from the hit, then a slow creep toward the edge while it rocks."""
    u = _ease_out((t - T_HIT) / 0.16)
    creep = 0.9 * min(max((t - T_TEETER) / (T_TIP - T_TEETER), 0.0), 1.0)
    loc = VN0 + Vector((1.3 * u, -1.7 * u - creep, 0.0))
    return Matrix.Translation(loc) @ Matrix.Rotation(math.radians(-10.0 * u), 4, 'Z')


def rock_pitch(t):
    """Teetering on the shelf edge: forward rocks (degrees) that fall back, the one on "von" the biggest."""
    ang = 0.0
    for tp, amp, w in ((78.0, 6.0, 0.09), (78.2, 11.0, 0.13), (78.47, 8.0, 0.12), (78.68, 12.0, 0.12)):
        x = (t - tp) / w
        if -1.0 < x < 1.6:
            ang = max(ang, amp * (math.cos(0.5 * math.pi * x) if x < 0 else max(0.0, 1 - (x / 1.6) ** 1.6)))
    return ang


def piv_rot(theta_deg, M):
    piv = Vector((0.0, PIV_Y, PIV_Z))
    return Matrix.Translation(piv) @ Matrix.Rotation(math.radians(theta_deg), 4, 'X') @ \
        Matrix.Translation(-piv) @ M


def make_pose(T_tip, theta_f=52.0):
    """Pose function of the model root (world matrix) and the time its lowest point reaches the desk."""
    B = base_matrix(T_TIP)
    t_f = T_TIP + T_tip

    def tip(t):
        tau = min(max(t - T_TIP, 0.0), T_tip)
        return piv_rot(theta_f * (tau / T_tip) ** 2, B)
    dt = 1e-3
    cf, cb = tip(t_f) @ COM_LOCAL, tip(t_f - dt) @ COM_LOCAL
    v = (cf - cb) / dt
    omega = 2 * theta_f / T_tip
    R_B = B.to_3x3().to_4x4()

    def fall(t):
        tau = t - t_f
        c = cf + v * tau + G * 0.5 * tau * tau
        R = Matrix.Rotation(math.radians(theta_f + omega * tau), 4, 'X') @ R_B
        return Matrix.Translation(c) @ R @ Matrix.Translation(-COM_LOCAL)

    def pose(t):
        if t < T_TIP:
            return piv_rot(rock_pitch(t), base_matrix(t))
        if t <= t_f:
            return tip(t)
        return fall(t)
    tc = None
    t = t_f
    while t < t_f + 1.0:
        if min((fall(t) @ p).z for p in PTS) <= 0.0:
            tc = t
            break
        t += 0.0005
    return pose, tc


def solve_pose():
    """The tip duration that lands the model on the desk between frames F_BREAK and F_BREAK + 1."""
    want = (F_BREAK + 0.7) / FPS
    lo, hi = 0.12, 0.6
    for _ in range(40):
        mid = (lo + hi) / 2
        _, tc = make_pose(mid)
        if tc is None or tc > want:
            hi = mid
        else:
            lo = mid
    return make_pose((lo + hi) / 2)


def key_matrix(obj, M, t):
    loc, rot, _ = M.decompose()
    obj.location = loc
    obj.rotation_euler = rot.to_euler('XYZ', obj.rotation_euler)
    obj.keyframe_insert('location', frame=t * FPS)
    obj.keyframe_insert('rotation_euler', frame=t * FPS)


def ballistic(p0, v0, t0, t):
    dt = t - t0
    return p0 + v0 * dt + G * 0.5 * dt * dt


def bounce_path(p0, v0, t0, radius, *, e=0.38, mu=2.5, n_bounce=3, floor=0.0):
    """A ballistic path from p0 with velocity v0 at t0 that bounces on z = floor + radius, then slides to rest
    (exponential horizontal decay mu per s). Returns pos(t)."""
    segs = []
    p, v, t = Vector(p0), Vector(v0), t0
    zf = floor + radius
    for _ in range(n_bounce + 1):
        a, b, c = -490.5, v.z, p.z - zf
        disc = b * b - 4 * a * c
        if disc < 0:
            break
        r1, r2 = (-b + math.sqrt(disc)) / (2 * a), (-b - math.sqrt(disc)) / (2 * a)
        dt = max(r1, r2)
        if dt <= 1e-4:
            break
        segs.append((t, t + dt, p.copy(), v.copy()))
        p = ballistic(p, v, 0.0, dt)
        p.z = zf
        vz = -(v.z - 981.0 * dt) * e
        v = Vector((v.x * 0.8, v.y * 0.8, vz))
        t += dt
        if vz < 10.0:
            break
    t_roll, p_roll, v_roll = t, p.copy(), Vector((v.x, v.y, 0.0))

    def pos(tt):
        if not segs or tt <= segs[0][0]:
            return Vector(p0)
        for ta, tb, pa, va in segs:
            if tt <= tb:
                return ballistic(pa, va, ta, tt)
        dt = tt - t_roll
        k = (1 - math.exp(-mu * dt)) / mu
        q = p_roll + v_roll * k
        q.z = zf
        return q
    return pos


def sequence(coll, stray, W, t0: float, t_end: float):
    """Build and animate everything. stray = (marble, route, ...); W maps board-local to world."""
    sc = bpy.context.scene
    shelf_objs, shelf_top = VN.build_shelf(coll, SHELF)
    P = VN.build_model(coll)
    root = P['root']
    pose, t_contact = solve_pose()
    t_break = (F_BREAK + 0.02) / FPS
    for f in frames(int(t0 * FPS) - 2, F_BREAK + 2):
        key_matrix(root, pose(f / FPS), f / FPS)
    for fc in kit.fcurves(root):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    sc.frame_set(sc.frame_start)
    bpy.context.view_layer.update()
    t_swap = (F_BREAK + 0.5) / FPS

    # ---------------------------------------------------------------- rigid bodies (baked by fx.bake in build())
    rigid.world(substeps=30, iterations=14)
    rigid.passive(bpy.data.objects['desk.top'], shape='BOX', friction=0.55, bounce=0.2)
    for o in shelf_objs:
        rigid.passive(o, shape='BOX', friction=0.6)
    rigid.passive(bpy.data.objects['run.board'], shape='BOX')
    rbc = kit.collection('vn.rb')
    impact = pose(t_contact) @ Vector((0, -3.0, 11.0))
    shards = fracture.fracture(P['cabinet'], 64, seed=5, impact=tuple(impact), cluster=0.5, mode='surface',
                               inner=VN.balsa(), coll=rbc, swap_at=t_swap)
    glass_shards = []
    for i, (base, glass, inner) in enumerate(P['tubes']):
        if i == VN.HERO_TUBE:
            continue
        glass_shards += fracture.fracture(glass, 6, seed=20 + i, mode='volume', coll=rbc, swap_at=t_swap)
    whole = [P['plinth'], P['panel']] + P['lamps'] + P['reels'] + \
        [b for i, (b, g, inner) in enumerate(P['tubes']) if i != VN.HERO_TUBE]
    copies = []
    for o in whole:
        c = VN.world_copy(o, rbc)
        copies.append(c)
        for x in [o] + VN.all_children(o):
            vis(x, None, t_swap)
        for x in [c] + list(c.children):
            vis(x, t_swap, None)

    def shatter_all(k: int = 0):
        """The burst; k > 0 re-rolls the pieces' velocities (BURST_ROLL)."""
        s0 = 7 if k == 0 else 100 + 3 * k
        fracture.shatter(shards, t_break, impact=tuple(impact), speed=(10.0, 45.0), spin=10.0, follow=root,
                         mass_density=0.0006, friction=0.6, bounce=0.2, seed=s0)
        fracture.shatter(glass_shards, t_break, impact=tuple(impact), speed=(30.0, 90.0), spin=25.0, follow=root,
                         mass_density=0.0025, friction=0.4, bounce=0.3, seed=s0 + 1)
        fracture.shatter(copies, t_break, impact=tuple(impact), speed=(10.0, 50.0), spin=12.0, follow=root,
                         mass_density=0.0012, friction=0.5, bounce=0.25, seed=s0 + 2)
    shatter_all(BURST_ROLL)

    # ---------------------------------------------------------------- the plaque: pops out, lands face up in front
    sc.frame_set(F_BREAK)
    bpy.context.view_layer.update()
    plq = P['plaque']
    M_plq = plq.matrix_world.copy()
    base, glass, inner = P['tubes'][VN.HERO_TUBE]
    M_tube = base.matrix_world.copy()
    sc.frame_set(sc.frame_start)
    plaque = VN.world_copy(plq, coll, '.fly')
    for x in [plq] + VN.all_children(plq):
        vis(x, None, t_swap)
    for x in [plaque] + list(plaque.children):
        vis(x, t_swap, None)
    p0 = M_plq.translation.copy()
    T_pl = 0.36
    v_pl = (PLAQUE_LAND - p0) / T_pl - G * 0.5 * T_pl
    path = bounce_path(p0, v_pl, t_break, 0.07, e=0.2, mu=11.0)
    R_rest = Matrix.Rotation(math.radians(12), 4, 'Z') @ Matrix.Rotation(math.radians(-90), 4, 'X')
    e0 = M_plq.to_euler('XYZ')
    e1 = R_rest.to_euler('XYZ', e0)
    e1 = (e1[0] - 2 * math.pi, e1[1], e1[2])          # one extra flip in the air
    for f in frames(F_BREAK, int(80.5 * FPS) - 1):
        t = f / FPS
        s = min(1.0, max(0.0, (t - t_break) / 0.45))
        k = 1 - (1 - s) ** 2
        q = path(t)
        plaque.location = q
        plaque.rotation_euler = [a + (b - a) * k for a, b in zip(e0, e1)]
        plaque.keyframe_insert('location', frame=f)
        plaque.keyframe_insert('rotation_euler', frame=f)
    plaque_rest = path(80.5)

    # ---------------------------------------------------------------- the hero tube: out, down, rolls to the domino
    tube = VN.world_copy(base, coll, '.hero')
    gl = glass.copy()
    gl.animation_data_clear()
    coll.objects.link(gl)
    gl.name = glass.name + '.hero'
    gl.parent = tube
    gl.matrix_parent_inverse = Matrix.Identity(4)
    gl.matrix_basis = Matrix.Identity(4)
    for x in [base, glass] + VN.all_children(base):
        vis(x, None, t_swap)
    for x in [tube, gl] + list(tube.children):
        vis(x, t_swap, None)
    R_TUBE = 0.47
    land = Vector((33.5, DOMINO.y, R_TUBE))
    t_land = 79.62
    pt0 = M_tube @ Vector((0, 0, 1.4))
    T = t_land - t_break
    vt = (land - pt0) / T - G * 0.5 * T
    # it taps the domino's nearest feature: the rounded vertical edge at its local (-1.2, -0.4) corner (bevel 0.12),
    # which lies along the tube's glass (radius 0.42)
    corner = Matrix.Rotation(math.radians(DOMINO_YAW), 3, 'Z') @ Vector((-1.2 + 0.12, -0.4 + 0.12, 0.0))
    x_hit = DOMINO.x + corner.x - 0.12 - 0.42 + 0.01
    t_roll0 = t_land + 0.12
    D, TT, v1 = x_hit - (land.x + 0.4), T_TAP - t_roll0, 1.5
    v0r = 2 * D / TT - v1
    acc = (v0r - v1) / TT
    e_t0 = M_tube.to_euler('XYZ')
    lying = Matrix.Rotation(math.radians(-90), 4, 'X')        # tube axis along +y, lying on its side

    def tube_M(t):
        if t < t_land:
            s = (t - t_break) / T
            p = ballistic(pt0, vt, t_break, t)
            e = [a + (b - a) * s for a, b in zip(e_t0, (math.radians(-90) - 2 * math.pi, 0.0, 0.0))]
            return Matrix.Translation(p) @ Matrix.Rotation(e[2], 4, 'Z') @ Matrix.Rotation(e[1], 4, 'Y') @ \
                Matrix.Rotation(e[0], 4, 'X') @ Matrix.Translation((0, 0, -1.4))
        if t < t_roll0:
            s = (t - t_land) / (t_roll0 - t_land)
            x = land.x + 0.4 * s
            p = Vector((x, land.y, R_TUBE + 0.45 * math.sin(math.pi * s)))
        else:
            tau = min(t - t_roll0, TT)
            x = land.x + 0.4 + v0r * tau - 0.5 * acc * tau * tau
            if t > T_TAP:
                x -= 0.3 * math.sin(min(1.0, (t - T_TAP) / 0.3) * math.pi * 0.5)
            p = Vector((x, land.y, R_TUBE))
        # the axis of a lying tube is 1.4 above its base origin: roll about the axis through the glass centre
        ax = Vector((p.x, p.y, p.z))
        return Matrix.Translation(ax) @ Matrix.Rotation((x - land.x) / R_TUBE, 4, 'Y') @ lying @ \
            Matrix.Translation((0, 0, -1.4))
    for f in frames(F_BREAK, int(t_end * FPS) + 2):
        key_matrix(tube, tube_M(f / FPS), f / FPS)
    # the keyed tube and plaque push the shards aside in the sim (kinematic colliders): no shard settles across the
    # tube's lane or inside the plaque. The tube's collider is a plain cylinder round its base and glass.
    col = geo.lathe('vn.tube.hero.collider', [(0.0, 0.1), (0.47, 0.1), (0.47, 3.0), (0.0, 3.0)], segs=16, coll=coll)
    col.hide_render = True
    col.display_type = 'WIRE'
    for f in frames(F_BREAK, int(t_end * FPS) + 2):
        key_matrix(col, tube_M(f / FPS), f / FPS)
    rigid.passive(col, shape='CONVEX_HULL', animated=True, friction=0.4)
    rigid.passive(plaque, shape='CONVEX_HULL', animated=True, friction=0.6)
    # they collide only from mid-flight (high above the debris) on: until then they sit in the park layer, so they
    # don't kick the pieces apart as they break free inside the model
    f_on = int(math.floor(T_COLLIDE * FPS))
    for o in (col, plaque):
        rigid.layers(o, [(rigid.world().point_cache.frame_start, [rigid.PARK_LAYER]), (f_on, [0])])

    # ---------------------------------------------------------------- the domino (toppling: th'' = 3g/2h sin th)
    dom = VN.build_domino(coll, DOMINO, yaw_deg=DOMINO_YAW)
    th, w, t, dt = 0.02, 0.9, T_TAP, 1.0 / (FPS * 16)
    samples = []
    while t < t_end + 0.2:
        samples.append((t, th))
        w += 306.0 * math.sin(th) * dt
        th = min(math.radians(84), th + w * dt)
        t += dt
    piv = Vector((0.0, 0.4, 0.0))
    for f in frames(int(T_TAP * FPS) - 1, int(t_end * FPS) + 2):
        tt = f / FPS
        a = 0.0
        if tt > T_TAP:
            a = min(samples, key=lambda s: abs(s[0] - tt))[1]
        Mw = Matrix.Translation(DOMINO) @ Matrix.Rotation(math.radians(DOMINO_YAW), 4, 'Z') @ \
            Matrix.Translation(piv) @ Matrix.Rotation(-a, 4, 'X') @ Matrix.Translation(-piv)
        key_matrix(dom, Mw, tt)

    # ---------------------------------------------------------------- glow: lamps and filaments
    lm = VN.lamp_mat()
    clk = lm.node_tree.nodes['clock'].outputs[0]
    pw = lm.node_tree.nodes['power'].outputs[0]
    per_frame(clk, 'default_value', lambda t: 6.0 * t if t < T_HIT else 6.0 * T_HIT + 17.0 * (t - T_HIT),
              t0 - 0.1, t_end)
    for tk, v in ((t0, 1.0), (T_HIT, 1.0), (T_HIT + 0.04, 0.2), (T_HIT + 0.08, 1.3), (T_HIT + 0.2, 1.0),
                  (t_break, 1.0), (t_break + 0.03, 1.8), (79.40, 0.15), (79.45, 0.9), (79.52, 0.0), (79.62, 0.5),
                  (79.68, 0.0)):
        geo.keyp(pw, 'default_value', tk, v, interp='LINEAR')
    fg = P['fm'].node_tree.nodes['glow'].outputs[0]
    for tk, v in ((t0, 1.0), (T_HIT, 1.0), (T_HIT + 0.03, 0.3), (T_HIT + 0.07, 1.4), (T_HIT + 0.15, 1.0),
                  (78.16, 1.0), (78.18, 0.5), (78.22, 1.1), (t_break, 1.0), (t_break + 0.02, 3.5), (79.40, 0.4),
                  (79.46, 0.0)):
        geo.keyp(fg, 'default_value', tk, v, interp='LINEAR')
    hg = P['fm_hero'].node_tree.nodes['glow'].outputs[0]
    hk = [(t0, 1.0), (T_HIT, 1.0), (T_HIT + 0.03, 0.3), (T_HIT + 0.07, 1.4), (T_HIT + 0.15, 1.0),
          (t_break, 1.0), (t_break + 0.02, 3.0), (79.45, 1.1)]
    for i in range(26):
        tk = 79.5 + i * 0.1
        hk.append((tk, max(0.02, 1.0 - (tk - 79.5) / 2.5) * (0.55 + 0.45 * geo.hash01('fl', i))))
    for tk, v in hk:
        geo.keyp(hg, 'default_value', tk, v, interp='LINEAR')
    # warm light the tubes throw around (rides the model, dies at the break)
    tl = kit.point('vn.tubelight', (0, 0, 0), power=0.0, radius=1.5, color='#FF9A40', coll=coll)
    geo.attach(tl, root, Vector((0, -1.5, 12.0)))
    for tk, v in ((t0, 700.0), (T_HIT + 0.03, 250.0), (T_HIT + 0.08, 900.0), (T_HIT + 0.2, 700.0),
                  (t_break, 700.0), (t_break + 0.02, 0.0)):
        geo.keyp(tl.data, 'energy', tk, v, interp='LINEAR')
    # and the hero tube's own little light as it rolls, fading with its filament
    hl = kit.point('vn.herolight', (0, 0, 0), power=0.0, radius=0.6, color='#FF8A2A', coll=coll)
    geo.attach(hl, tube, Vector((0, 0, 1.45)))
    for tk, v in hk:
        geo.keyp(hl.data, 'energy', max(tk, t_break + 0.03), 90.0 * v if tk > t_break else 0.0, interp='LINEAR')

    # ---------------------------------------------------------------- sparks at the impact
    spark_coll = kit.collection('vn.sparks')
    sm = VN.spark_mat()
    rnd = geo.rng(31)
    t_imp = (F_BREAK + 1) / FPS
    tubes_at = [pose(t_contact) @ Vector((x, 0.3, 11.5)) for x in VN.TUBE_X]
    for k in range(48):
        src = tubes_at[k % len(tubes_at)]
        src = Vector((src.x, src.y, max(0.4, src.z)))
        ang = rnd() * 2 * math.pi
        sp = 60 + 150 * rnd()
        v0s = Vector((math.cos(ang) * sp, math.sin(ang) * sp * 0.8 - 20, 60 + 160 * rnd()))
        life = 0.25 + 0.5 * rnd()
        o = kit.sphere(f'spark.{k:02d}', 0.045, (0, 0, 0), m=sm, coll=spark_coll, subdiv=1)
        o.visible_shadow = False
        pth = bounce_path(src, v0s, t_imp, 0.045, e=0.45, mu=6.0, n_bounce=2)
        for f in frames(F_BREAK, int((t_imp + life + 0.1) * FPS) + 1):
            t = f / FPS
            o.location = pth(max(t, t_imp))
            fade = 1.0 if t < t_imp + life * 0.6 else max(0.0, 1 - (t - t_imp - life * 0.6) / (life * 0.4))
            s = fade if t >= t_imp else 0.0
            o.scale = (s, s, s)
            o.keyframe_insert('location', frame=f)
            o.keyframe_insert('scale', frame=f)
        vis(o, t_imp - 0.5 / FPS, t_imp + life + 0.05)

    # ---------------------------------------------------------------- the stray marble: off the chute, into the side
    mb, route, keys, umap, _ = stray
    RT = RUN.Route
    p_off = W(route.pos(RT.U_H - RT.FLIGHT))
    p_hit = pose(T_HIT) @ Vector((-6.0 - RUN.R_MARBLE, 0.0, 3.6))
    p_hit.y = p_off.y
    Tf = T_HIT - T_OFF
    vf = (p_hit - p_off) / Tf - G * 0.5 * Tf
    ric = bounce_path(p_hit, Vector((-38.0, -26.0, 45.0)), T_HIT, RUN.R_MARBLE, e=0.4, mu=2.2)
    th0 = route.spin(RT.U_H - RT.FLIGHT)

    def stray_pos(t):
        if t <= T_HIT:
            return ballistic(p_off, vf, T_OFF, t)
        return ric(t)
    per_frame(mb, 'location', stray_pos, T_OFF, t_end)
    per_frame(mb, 'rotation_euler', lambda t: th0 + 40.0 * min(t - T_OFF, 0.055) - 20.0 * (1 - math.exp(
        -max(0.0, t - T_HIT) * 1.5)), T_OFF, t_end, index=1)
    return {'plaque_rest': plaque_rest, 'domino': DOMINO, 't_contact': t_contact, 'root': root, 'pose': pose,
            'tube': tube, 'tube_at': lambda t: tube_M(t) @ Vector((0, 0, 1.4)), 'x_hit': x_hit}


def _score_roll(C, t_end: float) -> tuple[dict, dict, int]:
    """After a bake: the pieces that ever touch the domino (it is not a collider, so they would pass through it), the
    pieces lying in the rolling tube's lane ahead of it (it shoves them), as {name: (first frame, size cm)}, and how
    many pieces bigger than 1 cm lie around the plaque at the end (B6 opens on the plaque among the shards)."""
    sc = bpy.context.scene
    bodies = [o for o in sc.rigidbody_world.collection.objects
              if o.rigid_body is not None and o.rigid_body.type == 'ACTIVE' and o.type == 'MESH']
    local = {o.name: [v.co.copy() for v in o.data.vertices] for o in bodies}
    R_dom = Matrix.Rotation(math.radians(-DOMINO_YAW), 3, 'Z')
    P6 = C['plaque_rest']
    dom, lane = {}, {}
    near = 0
    t = 79.70
    while t <= t_end + 1e-6:
        f = int(round(t * FPS))
        sc.frame_set(f)
        x0 = C['tube_at'](t).x + 0.3 if t < T_TAP else None
        last = t + 0.1 > t_end + 1e-6
        for o in bodies:
            M = o.matrix_world
            pts = [M @ v for v in local[o.name]]
            size = max((pts[0] - b).length for b in pts)
            if size >= 0.3 and o.name not in dom:
                for p in pts:
                    q = R_dom @ (p - DOMINO)
                    if -1.4 <= q.x <= 1.4 and -0.6 <= q.y <= 2.2 and q.z < 5.0:
                        dom[o.name] = (f, size)
                        break
            if x0 is not None and size >= LANE_MIN and o.name not in lane and any(
                    x0 <= p.x <= C['x_hit'] + 0.6 and LANE_Y[0] <= p.y <= LANE_Y[1] and p.z < 1.1 for p in pts):
                lane[o.name] = (f, size)
            if last and size > 1.0:
                c = M.translation
                if abs(c.x - P6.x) < 6.0 and -3.0 < c.y - P6.y < 5.0:
                    near += 1
        t += 0.1
    sc.frame_set(sc.frame_start)
    return dom, lane, near


def bake_burst(C, t_end: float):
    """Bake the burst and log what its debris does to the tube's lane and the domino (see BURST_ROLL)."""
    from pdoom import fx
    fx.bake()
    dom, lane, near = _score_roll(C, t_end)
    for nm, (f, size) in sorted(dom.items()):
        kit_log(f'  on the domino from f{f}: {nm} ({size:.2f} cm)')
    for nm, (f, size) in sorted(lane.items()):
        kit_log(f'  in the lane at f{f}: {nm} ({size:.2f} cm)')
    kit_log(f'backprop: burst roll {BURST_ROLL}: {len(dom)} pieces touch the domino, {len(lane)} lie in the tube lane, '
            f'{near} around the plaque' + (' WARNING: debris passes through the domino' if dom else ''))


def kit_log(msg):
    print('', flush=True)            # (after Blender's bake progress line, which has no newline)
    print(f'[run] {msg}', flush=True)
