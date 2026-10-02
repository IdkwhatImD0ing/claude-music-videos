"""coda · 151.139-156.651 · the ninth kick and the silence.

Space, a model's night: a paper moon (layered card, painted face) hangs on its string in the dark, lit like a stage
prop; the paperclip Earth hangs far behind it, lit by the sun; a star cloth all round. Clawd and the researcher sit
on the moon's lower inner edge, legs dangling over, looking at the Earth.

Shot list (song seconds; characters on twos, cameras smooth):

 C1  151.139-152.957  The ninth kick: the camera lands on the moon: a decelerating descent from behind and above the
                      pair, over their shoulders to the paperclip Earth beyond. Legs swing; the last notes ring out.
 C2  152.957-154.775  The silence. From the Earth's side, a slow push on the two-shot: Clawd turns to him and holds
                      up a single paperclip (153.30); he looks, wonders, reaches (153.62) and pinches its free end
                      (153.98); he holds it up beside his face, flat to the light, smiles; Clawd's eyes go ^^ and he
                      gives a little bounce (154.25).
 C3  154.775-156.651  Hold on the two of them from behind, the Earth beyond; the brass gauge hangs alone on its
                      thread in the foreground, reading 100 behind its cracked glass, turning slowly: the focus racks
                      to it (155.25). Fade to black (155.85-156.55).
"""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

from pdoom import chars, kit
from pdoom import timing as tm
from pdoom.fx import clips as C
from pdoom.sets import geo as sgeo

from scenes import coda_moon as CM
from scenes import finale_common as F

FPS = tm.FPS
V = Vector
T0, T_SIL, T_C3, T_END = 151.139, 152.957, 154.775, 156.651
T_TURN, T_OFFER, T_LOOK, T_REACH = 153.08, 153.30, 153.46, 153.62
T_TAKE = (3696 - 0.5) / FPS          # 153.979: a pose boundary on the twos grid (keys at even f - 0.5)
F_SWAP = 3696                        # the first frame (at 24 and 60 fps) that shows his copy of the clip
# Clawd's clip, in his hand.R socket frame (-x = out along the stub): held by its end, 0.35 inside the nub, tilted
# 30 deg up so the free end stands clear above the line of the researcher's reach.
CLIP_ROT = (90.0, 30.0, -15.0)
_CLIP_END = Vector((0.35, -0.1, 0.0))
CLIP_UP = Vector((-0.45, 0.45, 0.77)).normalized()   # where his clip points (world) once lifted: up, out, to camera
CLIP_OFF = _CLIP_END - Euler([math.radians(a) for a in CLIP_ROT], 'XYZ').to_matrix() @ Vector((C.LENGTH / 2, 0, 0))
T_JOY = 154.25
T_RACK, T_FADE0, T_FADE1 = 155.25, 155.85, 156.55
EARTH = V((-40.0, 430.0, 60.0))
GAUGE = V((37.0, -58.0, -30.5))              # the gauge's plinth centre (it hangs on its thread)
SUN_DIR = V((-0.82, -0.52, 0.26)).normalized()


def build():
    sc = kit.new_scene('coda')
    coll = kit.collection('coda')
    p = kit.asset('hdri', 'office_night.hdr')
    if os.path.exists(p):
        kit.world_hdri(p, 0.06, 120.0, background=('#000000', 0.0))
    else:
        kit.world_color('#000000', 0.0)

    # ------------------------------------------------------------------ the world: moon, Earth, stars, gauge
    moon = CM.build_moon(coll, loc=(0.0, 0.0, 0.0), yaw=0.0)
    # the moon turns a hair on its string
    kit.key(moon.root, 'rotation_euler', T0 - 0.2, (0.0, 0.0, math.radians(-2.0)), interp='LINEAR')
    kit.key(moon.root, 'rotation_euler', T_END + 0.2, (0.0, 0.0, math.radians(1.5)), interp='LINEAR')
    E = CM.clip_earth(coll, EARTH, radius=30.0, progress=None, scale=0.3, layers=2, density=0.8, clouds=False)
    F.set_earth_sun(E['material'], SUN_DIR)
    kit.key(E['spin'], 'rotation_euler', T0 - 0.3, (math.radians(8), 0.0, math.radians(-2.0)), interp='LINEAR')
    kit.key(E['spin'], 'rotation_euler', T_END + 0.3, (math.radians(8), 0.0, math.radians(12.0)), interp='LINEAR')
    F.stars('coda.stars', (0.0, 200.0, 0.0), r0=1000.0, r1=2000.0, count=3200, seed=11, size=(0.8, 3.0), coll=coll)
    g, thread = CM.build_gauge_hung(coll, tuple(GAUGE), yaw=-6.0)
    kit.key(g.root, 'rotation_euler', T0, (0.0, 0.0, math.radians(-10.0)), interp='LINEAR')
    kit.key(g.root, 'rotation_euler', T_END, (0.0, 0.0, math.radians(14.0)), interp='LINEAR')
    for fc in kit.fcurves(g.root):
        if fc.data_path == 'rotation_euler':
            for kp in fc.keyframe_points:
                kp.interpolation = 'SINE'
    # it's only seen alone, in the last shot
    F.show([o for o in g.objects + [thread] if o.type != 'EMPTY'], F.edge(T_C3), None)

    # ------------------------------------------------------------------ the two of them, sitting on the edge
    seat_c, zc = moon.seat(0.22)             # x ~ 8.4
    seat_r, zr = moon.seat(0.70)             # x ~ 18
    # y 2.7: far enough forward that his knees clear the card's Earth-side face (y 3.0) and the shins hang in front of it
    r = chars.Researcher(kit.collection('coda.researcher'), loc=(seat_r.x, 2.7, zr), yaw=180.0)
    c = chars.Clawd(kit.collection('coda.clawd'), loc=(seat_c.x, 2.2, zc), yaw=180.0)
    _drape_coat(r)
    _sit(c, r)
    clips = _act(c, r)

    # ------------------------------------------------------------------ light: the sun, a stage spot, earthshine
    lc = kit.collection('coda.lights')
    kit.sun('coda.sun', direction=tuple(-SUN_DIR), strength=5.0, angle_deg=0.8, color='#FFF1DC', coll=lc)
    spot = kit.spot('coda.spot', (30.0, 170.0, 120.0), (12.0, 0.0, -18.0), power=3.2e6, angle_deg=24, blend=0.55,
                    radius=5.0, color='#FFD6A0', coll=lc)
    es = kit.area('coda.earthshine', tuple(EARTH + V((0, -60, 0))), (12.0, 0.0, -18.0), power=6e5, size=80.0,
                  color='#6F8FD8', coll=lc)
    rim = kit.spot('coda.rim', (-60.0, -160.0, 90.0), (12.0, 0.0, -16.0), power=1.4e6, angle_deg=22, blend=0.6,
                   radius=4.0, color='#CFD8FF', coll=lc)
    gl = kit.spot('coda.gaugekey', tuple(GAUGE + V((40.0, -110.0, 50.0))), tuple(GAUGE + V((0, 0, 8.6))), power=4.5e5,
                  angle_deg=12, blend=0.7,
                  radius=2.0, color='#FFD9A8', coll=lc)
    for L in (spot, es, rim, gl):
        L.data.volume_factor = 0.0

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('coda.cams')
    pair = V((13.0, 1.5, -19.0))
    # C1: lands from behind and above, over their shoulders to the Earth
    F.Cam('cam.c1', T0, T_SIL, F.path((-44.0, -238.0, 74.0), (0.0, -82.0, -6.0), T0, T_SIL + 0.25, p=2.6),
          F.path((0.0, 150.0, 8.0), (5.0, 120.0, -12.0), T0, T_SIL + 0.25, p=2.6), lens=32.0, fstop=4.0,
          focus=pair, coll=cams)
    # C2: from the Earth's side, the two-shot, a slow push
    F.Cam('cam.c2', T_SIL, T_C3, F.path((12.8, 60.0, -13.0), (13.0, 47.0, -14.0), T_SIL, T_C3 + 0.1, p=1.2),
          F.path((13.2, 0.0, -18.0), (13.2, 0.0, -18.3), T_SIL, T_C3 + 0.1), lens=72.0, fstop=11.0,
          focus=V((13.0, 2.0, -18.0)), coll=cams)
    # C3: behind them again, the gauge hanging in the foreground; rack focus pair -> gauge; fade to black
    gz = GAUGE + V((0.0, 0.0, 8.6))

    def foc(t):
        u = F.smooth((t - T_RACK) / 0.55)
        return pair.lerp(gz, u)
    F.Cam('cam.c3', T_C3, T_END, F.path((27.0, -152.0, -12.0), (25.0, -140.0, -14.0), T_C3, T_END, p=1.0),
          F.path((19.0, 20.0, -16.0), (20.0, 20.0, -17.0), T_C3, T_END), lens=50.0, fstop=3.2, focus=foc, coll=cams)
    # fade to black
    kit.key(sc, 'view_settings.exposure', T_FADE0, 0.0, interp='SINE')
    kit.key(sc, 'view_settings.exposure', T_FADE1, -10.0, interp='CONSTANT')
    kit.post(bloom=0.3, bloom_threshold=1.0, vignette=0.28)
    chars.finish()
    _hand_over(sc, c, r, *clips)          # his clip is parented after the bake
    return c, r, moon, g


def _sit(c, r):
    """Seated on the edge: the researcher in 'sit' (legs over the edge), Clawd's body lowered, his front legs
    dangling over, the rear ones folded; both swing their feet a little, like kids on a wall."""
    t = T0 - 1.0
    r.pose(t, 'sit', dur=0.0)
    r.face(t, 'neutral')
    for s, ph in (('L', 0.0), ('R', 2.2)):
        r.T[f'shin.{s}'].set(t, 68.0, 0.0)        # shins angled a little forward, clear of the card's face
        r.T[f'shin.{s}'].add(T0 - 1, T_END + 1, lambda x, ph=ph: 6.0 * math.sin(2 * math.pi * x / 1.9 + ph))
        r.T[f'thigh.{s}'].add(T0 - 1, T_END + 1, lambda x, ph=ph: (3.0 * math.sin(2 * math.pi * x / 1.9 + ph + 0.8),
                                                                    0.0, 0.0))
    c.T['hips.loc'].set(t, (0.0, 0.0, -0.95))
    for i in range(8):
        front = i % 2 == 0
        if front:
            c.T[f'leg{i}'].set(t, (-42.0, 0.0, 0.0))
            c.T[f'leg{i}'].add(T0 - 1, T_END + 1, lambda x, i=i: (14.0 * math.sin(2 * math.pi * x / 1.6 + i * 0.9),
                                                                   0.0, 0.0))
        else:
            c.T[f'leg{i}'].set(t, (20.0, 0.0, 0.9))
    c.T['body.rot'].set(t, (-5.0, 0.0, 0.0))
    c.eyes(t, 'open', glow=0.0)
    c.no_gait(T0 - 2, T_END + 2)
    r.no_gait(T0 - 2, T_END + 2)


def _drape_coat(r, z_hi=3.0, z_lo=2.25):
    """Seated, the library's coat skirt (thigh weights up to 0.6 from z 3.5 down) folds into its own front panels and
    pockets. Here only the band the thighs pass through (below z_hi) follows them: same 0.6 at the hem."""
    from pdoom.chars.rig import smoothstep
    ob = r.o_coat
    groups = {n: ob.vertex_groups[n] for n in ('spine', 'thigh.L', 'thigh.R')}
    for v in ob.data.vertices:
        k = 0.6 * smoothstep(z_hi, z_lo, v.co.z)
        side = smoothstep(-0.5, 0.5, v.co.x)
        for n, w in (('spine', 1 - k), ('thigh.L', k * side), ('thigh.R', k * (1 - side))):
            if w > 1e-4:
                groups[n].add([v.index], w, 'REPLACE')
            else:
                groups[n].remove([v.index])


def _act(c, r):
    earth_pt = EARTH
    # looking out at the Earth
    r.look(T0 + 0.1, earth_pt, dur=0.2, turn=0.0)
    c.look(T0 + 0.1, earth_pt, turn=0.0, dur=0.2)
    c.blink(152.3)
    # the offer
    c.look(T_TURN, r, turn=0.25, dur=0.3)
    c.arms(T_OFFER, (22.0, 18.0, 0.0), side='R', dur=0.3)
    c.lid(T_OFFER + 0.05, 0.12, 0.15)
    clip_c = C.clip('coda.clip.clawd', (0, 0, 0), rot=(0.0, 0.0, 0.0), lod=0, coll=kit.collection('coda.clawd'))
    c.attach(clip_c, 'hand.R', offset=tuple(CLIP_OFF), rot=CLIP_ROT)
    r.look(T_LOOK, c, dur=0.25)
    r.face(T_LOOK + 0.05, 'awe')
    # he reaches with his left mitten, comes down onto the clip's free end from above and pinches it (the mitten's
    # centre 0.3 in from the end, so the rest of the clip sticks out past his fingers)
    Rc = Euler([math.radians(a) for a in CLIP_ROT], 'XYZ').to_matrix().to_4x4()
    Mh = c.rig.matrix_world @ c._fk(T_TAKE)['hand.R'] @ Matrix.Translation(CLIP_OFF) @ Rc
    grip = Mh @ V((-C.HALF + 0.3, 0.0, 0.0))
    r.hand(T_REACH + 0.22, 'L', grip + V((0.5, 0.3, 0.9)), dur=0.22, wrist=(-40.0, 0.0, 0.0))
    r.hand(T_TAKE - 0.02, 'L', grip, dur=0.12, wrist=(-40.0, 0.0, 0.0))
    clip_r = C.clip('coda.clip.researcher', (0, 0, 0), rot=(0.0, 0.0, 0.0), lod=0,
                    coll=kit.collection('coda.researcher'))
    F.show([clip_c], F.edge(T_SIL), T_TAKE)          # he produces it on the cut into the silence
    F.show([clip_r], T_TAKE, None)
    # he brings it up to look at it; smiles
    eyes = r.anchor(T_TAKE + 0.5, 'eyes')
    lift = eyes + V((0.4, 3.2, -0.6))
    r.look(T_TAKE + 0.5, lift, dur=0.3)
    wl = _lift_wrist(r, T_TAKE, grip, (-40.0, 0.0, 0.0), Mh, T_TAKE + 0.55, lift,
                     (-70.0, 0.0, 30.0), CLIP_UP)
    r.hand(T_TAKE + 0.55, 'L', lift, dur=0.4, wrist=wl)
    r.face(T_TAKE + 0.4, 'happy')
    c.arms(T_TAKE + 0.45, 'rest', side='R', dur=0.3)     # lets go once his fingers have it (both hold over the swap)
    c.lid(T_TAKE + 0.3, 0.0, 0.2)
    c.eyes(T_JOY, 'happy')
    c.squash(T_JOY + 0.05, 0.12)
    # the hold: both look back out at the Earth
    r.look(T_C3 - 0.2, earth_pt, dur=0.5, turn=0.0)
    c.look(T_C3 - 0.1, earth_pt, turn=0.0, dur=0.5)
    return clip_c, clip_r


def _lift_wrist(r, t_g, target_g, wrist_g, M_g, t_l, target_l, wrist_l, d_want, face=V((0.0, 1.0, 0.0))):
    """Wrist angles for the lift so the clip he took (world rotation M_g at t_g, his mitten at target_g with wrist
    wrist_g) points its long axis along d_want at t_l, its flat side turned to `face` (the camera). Mirrors
    Researcher.hand() and clear_arm (the mitten keeps the orientation of the old IK chain times the wrist angles)."""
    from mathutils import Euler as E
    from pdoom.chars import researcher as RS

    def frame(t, target, wrist):
        Ms = r._spine_world(t)
        local = Ms.inverted() @ target
        d = local - RS.SH['L']
        if d.length > 0.55:
            local = local - d.normalized() * 0.55
        Eo, Wo, no = RS._old_chain('L', local, r._pole_a['L'])
        F = RS._forearm_rot('L', RS.SH['L'], Eo, Wo, no)
        return Ms.to_3x3().normalized(), F, E([math.radians(x) for x in wrist], 'XYZ').to_matrix()
    Sg, Fg, Wg = frame(t_g, target_g, wrist_g)
    Mg = M_g.to_3x3().normalized()
    to_hand = (Fg @ Wg).transposed() @ Sg.transposed()
    d_hand, n_hand = to_hand @ (Mg @ V((1.0, 0.0, 0.0))), to_hand @ (Mg @ V((0.0, 0.0, 1.0)))
    Sl, Fl, Wl = frame(t_l, target_l, wrist_l)
    d_s = Sl.transposed() @ d_want
    R1 = (Fl @ Wl @ d_hand).rotation_difference(d_s).to_matrix() @ Fl @ Wl      # smallest turn onto d_want
    # then roll about the long axis so the clip's flat side faces `face` (either side: the smaller roll)
    n = (R1 @ n_hand)
    f = Sl.transposed() @ V(face)
    n, f = (n - d_s * n.dot(d_s)).normalized(), (f - d_s * f.dot(d_s)).normalized()
    if n.dot(f) < 0:
        f = -f
    a = n.angle(f) * (1 if n.cross(f).dot(d_s) > 0 else -1)
    R = Matrix.Rotation(a, 3, d_s) @ R1
    w = (Fl.transposed() @ R).to_euler('XYZ', E([math.radians(x) for x in wrist_l], 'XYZ'))
    return tuple(math.degrees(a) for a in w)


def _hand_over(sc, c, r, clip_c, clip_r):
    """Parent his clip to his mitten so that on F_SWAP (the first frame that shows it) it sits exactly where Clawd's
    clip is: the hand-over has no jump, and he holds it where his fingers closed on it."""
    sc.frame_set(F_SWAP)
    dg = bpy.context.evaluated_depsgraph_get()

    def bone_world(rig, bone):
        re = rig.evaluated_get(dg)
        pbn = re.pose.bones[bone]
        return re.matrix_world @ pbn.matrix @ Matrix.Translation((0.0, pbn.bone.length, 0.0))
    Mc = bone_world(c.rig, clip_c.parent_bone) @ clip_c.matrix_parent_inverse @ clip_c.matrix_basis
    clip_r.parent = r.rig
    clip_r.parent_type = 'BONE'
    clip_r.parent_bone = 'hand.L'
    clip_r.matrix_parent_inverse = bone_world(r.rig, 'hand.L').inverted()
    clip_r.matrix_basis = Mc
    print(f'[coda] hand-over at frame {F_SWAP}: clip centre {tuple(round(x, 3) for x in Mc.translation)}', flush=True)
    sc.frame_set(sc.frame_start)
