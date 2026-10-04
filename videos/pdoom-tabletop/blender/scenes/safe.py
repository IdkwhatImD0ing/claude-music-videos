"""safe · 67.507-74.779 · "...a second / That was safe enough, we reckoned / (For-)"

The researcher baits Clawd into a glass jar with a sugar cube, screws the lid on, the jar spins as he feeds hazard tape
onto it, he pats it, proud. Inside, Clawd's eyes glow red; he taps the glass twice and on the last beat a crack runs up
the jar. Jar at J (world); everything that turns with the jar is a child of the 'jar.spin' Empty.

Lyrics in the picture (revision 2): "That was safe" is stamped in red ink, word by word, onto a paper label low on
the jar as the lid clanks on and the two twists land ("That" 69.76, "was" 69.98, "safe" 70.12); the label turns
with the jar, under the hazard tape. The rest of line 21 ("...a second"), "enough, we reckoned" and "Forward"
stand on the lyric stand. Cuts sit on even
frames (the characters pose on twos) within a frame of the beat.

Shot list
  S1 67.507-69.333  wide, slow push   He holds up a sugar cube, tosses it into the open jar (67.92); Clawd's eyes turn
                                      to stars, he leaps in (takeoff 68.416, lands 68.871 on the beat), flips the cube up into his open mouth
                                      and chomps it (69.12).
  S2 69.333-70.250  high close-up     Standing on a toy block he lowers the gold lid on (clank 69.78, "That"), two
                                      ratchet twists land on "was" (69.98) and "safe" (70.116). Clawd looks up, happy.
  S3 70.250-71.167  three-quarter     The jar spins two turns while he holds a roll of hazard tape against it: the band
                                      winds on (stripes flow roll > span > jar), Clawd spins inside with dizzy eyes;
                                      he yanks the roll away (70.98), the tape tears.
  S4 71.167-73.000  two-shot, push    "we reckoned": he pats the tape on the beats 71.598, 72.052, 72.507, happy, then
                                      turns to us, hands on hips (72.85). Clawd shakes off the dizziness, watches him.
  S5 73.000-74.779  macro push +      Clawd behind glass and tape, the researcher proud and soft far behind. Eyes
                    rack focus        narrow (73.15), glow red on the beat (73.416); he raises a claw, taps the glass on
                                      the kicks 74.104 and 74.323: a crack runs from the tap up to the rim and down
                                      under the tape (74.33-74.70). Focus racks from his eyes to the glass.
"""
import math

import bpy
from mathutils import Euler, Matrix, Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom.lyrics import core as CORE
from pdoom import timing as tm
from pdoom.sets import build_desk, geo
from pdoom.timing import FPS

from scenes import safe_jar as SJ

J = Vector((4.0, -16.0, 0.0))          # the jar's base centre on the desk
BAND_Z = SJ.TAPE_Z0 + SJ.TAPE_W / 2    # the tape band's centre height


def ct(t: float) -> float:
    """Snap a cut to the nearest even frame (characters pose on twos)."""
    return round(t * FPS / 2) * 2 / FPS


T1, T2, T3, T4, T5 = ct(67.507), ct(69.325), ct(70.234), ct(71.143), ct(72.961)
HALF = 0.5 / FPS                       # visibility switches half a frame before a cut (clean motion blur)
TEND = 74.779
CUBE_IN_HAND = (0.0, 0.0, -0.95)       # the held sugar cube, from the mitten centre (rest axes): at the fingertips
LID_DESK = (-20.0, 12.0)               # the lid lying on the desk in S1 (J-relative)


# ------------------------------------------------------------------------------------------------ keying helpers


def per_frame(owner, path, fn, t0, t1, *, index=-1, interp='LINEAR'):
    """Key owner.path = fn(t) on every frame from t0 to t1 (smooth 24 fps animation, motion-blurred). 60 fps builds:
    on every output frame (on_grid)."""
    if tm.SMOOTH and interp == 'LINEAR':
        return on_grid(owner, path, fn, math.floor(t0 * FPS) / FPS, math.ceil(t1 * FPS) / FPS, index=index)
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    for f in range(f0, f1 + 1):
        geo.keyp(owner, path, f / FPS, fn(f / FPS), interp=interp, index=index)


def _set_interp(owner, path, index, lo, hi, interp):
    idb = owner.id_data
    try:
        full = owner.path_from_id(path)
    except Exception:
        full = path
    for fc in kit.fcurves(idb):
        if fc.data_path == full and (index < 0 or fc.array_index == index):
            for kp in fc.keyframe_points:
                if lo - 1e-4 <= kp.co.x <= hi + 1e-4:
                    kp.interpolation = interp


def on_grid(owner, path, fn, t0, t1, *, index=-1):
    """60 fps builds (tm.SMOOTH): LINEAR keys on every OUTPUT frame in [t0, t1] with the value at that frame's own
    time, so the element moves on every frame (on_ones / on_twos route here when tm.SMOOTH)."""
    fks = tm.out_frames(t0 * FPS, t1 * FPS)
    for fk in fks:
        v = fn(fk / FPS)
        if index >= 0:
            getattr(owner, path)[index] = v
        else:
            setattr(owner, path, v)
        owner.keyframe_insert(path, frame=fk, index=index)
    if fks:
        _set_interp(owner, path, index, fks[0], fks[-1], 'LINEAR')


def on_ones(owner, path, fn, t0, t1, *, index=-1):
    """A crisp pose every frame (stop-motion on ones, no motion blur): CONSTANT keys at f - 0.5 with the value
    at f / 24. For the spinning jar, whose stripes must stay readable. 60 fps builds: smooth (on_grid)."""
    if tm.SMOOTH:
        return on_grid(owner, path, fn, t0, t1, index=index)
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    for f in range(f0, f1 + 1):
        v = fn(f / FPS)
        if index >= 0:
            getattr(owner, path)[index] = v
        else:
            setattr(owner, path, v)
        owner.keyframe_insert(path, frame=f - 0.5, index=index)
    idb = owner.id_data
    try:
        full = owner.path_from_id(path)
    except Exception:
        full = path
    for fc in kit.fcurves(idb):
        if fc.data_path == full and (index < 0 or fc.array_index == index):
            for kp in fc.keyframe_points:
                if f0 - 1 <= kp.co.x <= f1 + 1:
                    kp.interpolation = 'CONSTANT'


def on_twos(owner, path, fn, t0, t1, *, index=-1):
    """Stop-motion keys like the characters': one pose per even frame f, CONSTANT, keyed at f - 0.5 with the
    value at (f + 1) / 24. 60 fps builds: smooth (on_grid)."""
    if tm.SMOOTH:
        return on_grid(owner, path, fn, t0, t1, index=index)
    f = int(math.floor(t0 * FPS))
    f -= f % 2
    f1 = int(math.ceil(t1 * FPS))
    while f <= f1:
        v = fn((f + 1) / FPS)
        if index >= 0:
            getattr(owner, path)[index] = v
        else:
            setattr(owner, path, v)
        owner.keyframe_insert(path, frame=f - 0.5, index=index)
        f += 2
    idb = owner.id_data
    try:
        full = owner.path_from_id(path)
    except Exception:
        full = path
    for fc in kit.fcurves(idb):
        if fc.data_path == full and (index < 0 or fc.array_index == index):
            for kp in fc.keyframe_points:
                if t0 * FPS - 1.5 <= kp.co.x <= t1 * FPS + 1.5:
                    kp.interpolation = 'CONSTANT'


def interp_keys(keys, t, ease=True):
    """Piecewise interpolation through [(t, value-tuple)], smoothstep between keys."""
    if t <= keys[0][0]:
        return keys[0][1]
    for (ta, va), (tb, vb) in zip(keys, keys[1:]):
        if t <= tb:
            u = (t - ta) / (tb - ta)
            if ease:
                u = u * u * (3 - 2 * u)
            return tuple(a + (b - a) * u for a, b in zip(va, vb))
    return keys[-1][1]


def at_cut(owner, path, t, v_before, v_after, *, index=-1):
    """Jump a value exactly at a cut (constant keys half a frame either side of the cut frame). 60 fps builds: the
    jump sits between the last exposure of the old shot and the cut (tm.switch_frame), since these curves also carry
    smooth keys and run.py's render-time step alignment leaves mixed curves alone."""
    f = round(t * FPS)
    if tm.SMOOTH:
        sw = tm.switch_frame(f)
        fks = (sw - 0.1, sw)
    else:
        fks = (f - 1.5, f - 0.5)
    for fk, v in zip(fks, (v_before, v_after)):
        if index >= 0:
            getattr(owner, path)[index] = v
        else:
            setattr(owner, path, v)
        owner.keyframe_insert(path, frame=fk, index=index)
    for fc in kit.fcurves(owner.id_data):
        if fc.data_path.endswith(path):
            for kp in fc.keyframe_points:
                if any(abs(kp.co.x - fk) < 1e-3 for fk in fks):
                    kp.interpolation = 'CONSTANT'


def polar(r, deg, z=0.0):
    a = math.radians(deg)
    return J + Vector((r * math.cos(a), r * math.sin(a), z))


def yaw_to(src, dst) -> float:
    d = Vector(dst) - Vector(src)
    return math.degrees(math.atan2(d.x, -d.y))


# ------------------------------------------------------------------------------------------------ the spin


def spin_profile(ts=70.28, te=71.28, turns=2.0, ramp=0.06, coast=70.84):
    """theta(t): the jar kicks up to speed in `ramp` s, spins steadily until `coast`, then slows linearly to rest
    at te, having turned exactly `turns` turns (so everything inside ends where it started)."""
    n = 400
    dt = (te - ts) / n
    w = []
    for i in range(n + 1):
        t = ts + i * dt
        up = min(1.0, (t - ts) / ramp)
        down = max(0.0, (te - t) / (te - coast)) if t > coast else 1.0
        w.append(up * up * (3 - 2 * up) * down)
    cum = [0.0]
    for i in range(1, n + 1):
        cum.append(cum[-1] + 0.5 * (w[i] + w[i - 1]) * dt)
    k = turns * 2 * math.pi / cum[-1]

    def theta(t):
        if t <= ts:
            return 0.0
        if t >= te:
            return turns * 2 * math.pi
        x = (t - ts) / dt
        i = min(int(x), n - 1)
        u = x - i
        return k * (cum[i] + (cum[i + 1] - cum[i]) * u)
    return theta


# ------------------------------------------------------------------------------------------------ build


def build():
    sc = kit.new_scene('safe')
    # no paperclip: from the S1 camera it sat right behind the jar and read as a gold needle inside it
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable', 'clip'})
    d.lamp.aim(None, J + Vector((0, -2, 4)))
    props = kit.collection('safe')
    beats = tm.beats()

    # ---------------------------------------------------------------- the jar and everything that spins with it
    spin = kit.empty('jar.spin', tuple(J), props, 'ARROWS', 3.0)
    bpy.context.view_layer.update()
    jar, thread = SJ.build_jar(props)
    for o in (jar, thread):
        geo.attach(o, spin)
        o.visible_shadow = False           # glass: no opaque shadow (EEVEE can't do caustics)
    lid = SJ.build_lid(props, plain_inside=True)
    geo.attach(lid, spin)
    theta = spin_profile()
    on_ones(spin, 'rotation_euler', theta, T3, 71.4, index=2)

    # ---------------------------------------------------------------- characters
    C1 = J + Vector((11.8, -0.5, 0))
    c = chars.Clawd(kit.collection('clawd'), loc=tuple(C1), yaw=-90)
    kit.parent(c.rig, spin)                       # rides the jar when it spins (it only spins in S3)
    R1 = J + Vector((-10.5, -1.4, 0))
    r = chars.Researcher(kit.collection('researcher'), loc=tuple(R1), yaw=90)

    # custom poses: the cube held up, the toss
    # (cube_up within the arm's reach, in front of the face; toss_back beside the head, not behind it)
    chars.POSES['cube_up'] = dict(spine=(-3, 0, 0), head=(-4, 0, 0), hands=(None, (-1.3, -2.5, 7.9)),
                                  wrist=(None, (-100, 0, 0)), face='happy')
    chars.POSES['toss_back'] = dict(spine=(-8, 0, -6), head=(-12, 0, 0), hands=(None, (-2.7, -0.6, 8.3)),
                                    wrist=(None, (-120, 0, 0)), face='determined')
    chars.POSES['toss'] = dict(spine=(6, 0, 8), head=(-18, 0, 0), hands=(None, (-0.8, -3.1, 8.2)),
                               wrist=(None, (-100, 0, 0)), face='happy')
    chars.POSES['scheme'] = dict(spine=(6, 0, 0), head=(4, 0, 0), hands=((0.35, -2.2, 5.3), (-0.35, -2.25, 5.25)),
                                 wrist=((-80, 0, 50), (-80, 0, -50)), face='happy')

    # ================================================================ S1: the sugar cube and the leap
    r.pose(T1, 'cube_up', dur=0.01)
    r.look(T1 + 0.05, c)
    r.pose(67.80, 'toss_back', dur=0.16)
    r.pose(67.94, 'toss', dur=0.12)
    t_rel = 67.93
    r.look(68.1, J + Vector((0, 0, 8)))
    r.pose(68.45, 'scheme', dur=0.3)
    r.look(68.55, c)
    r.look(69.05, J + Vector((0, 0, 5)))
    # the cube: held until the release, then a real ballistic toss into the jar with two bounces
    cube_held = SJ.build_sugar(props, 'sugar.held')
    r.attach(cube_held, 'hand.R', offset=CUBE_IN_HAND)          # pinched at the mitten's tip, not at the wrist
    kit.visible(cube_held, None, t_rel)
    cube = SJ.build_sugar(props, 'sugar')
    p0 = r.anchor(t_rel, 'hand.R') + Vector((0.47, -1.39, -0.13))      # where the held cube is at the release
    p_land = J + Vector((-3.9, 0.4, SJ.FLOOR + 0.375))
    T = 0.30
    g = Vector((0, 0, -981.0))
    v0 = (p_land - p0) / T - 0.5 * g * T
    t_land = t_rel + T
    vz1 = -(v0.z + g.z * T) * 0.32
    T2b = 2 * vz1 / 981.0
    vh = Vector((v0.x, v0.y, 0)) * 0.25
    p_rest = p_land + vh * T2b

    # the chomp: the jaw is wide open from 68.97 and slams shut on 69.12; the cube flips up off the floor into his
    # open mouth (68.95-69.05) and rides on his tongue until the jaw closes over it
    t_chomp = 69.12
    t_pop0, t_pop1 = 68.95, 69.05

    def mouth_pt(t):
        return c.anchor(t, 'mouth') + Vector((0.0, 0.0, 0.8))      # on the tongue, inside the jaw cavity

    def cube_pos(t):
        if t <= t_rel:
            return p0
        if t <= t_land:
            dt = t - t_rel
            return p0 + v0 * dt + 0.5 * g * dt * dt
        if t <= t_land + T2b:
            dt = t - t_land
            return p_land + vh * dt + Vector((0, 0, vz1 * dt - 490.5 * dt * dt))
        if t <= t_pop0:
            return p_rest
        if t <= t_pop1:
            u = (t - t_pop0) / (t_pop1 - t_pop0)
            return p_rest.lerp(mouth_pt(t), u) + Vector((0.0, 0.0, 1.6 * 4 * u * (1 - u)))
        return mouth_pt(t)

    spin_rate = Vector((9.0, -6.0, 4.0))

    def cube_rot(t):
        if t <= t_rel:
            return (0.0, 0.0, 0.0)
        if t <= t_land:
            dt = t - t_rel
            return tuple(spin_rate * dt)
        # snap flat on landing, a little yaw tumble in the bounce, a flip on the way into the mouth
        base = Vector((0.0, 0.0, spin_rate.z * T))
        dt = min(t - t_land, T2b + 0.1)
        u = min(1.0, max(0.0, (t - t_pop0) / (t_pop1 - t_pop0)))
        return (0.0, -math.pi * (u * u * (3 - 2 * u)), base.z + 3.0 * dt)

    # Clawd: sees the treat, follows the arc, leaps into the jar, eats it
    c.eyes(T1, 'open')
    c.look(T1 + 0.08, p0 + Vector((0, 0, 1)), turn=0.0)
    c.eyes(67.62, 'star')
    c.look(68.02, cube_pos(68.02), turn=0.0)
    c.look(68.24, p_land, turn=0.0)
    c.hop(68.416, 12.5, 0.455, to=(J.x, J.y, SJ.FLOOR))
    c.eyes(68.87, 'open')
    c.look(68.95, p_rest, turn=0.0)
    c.chomp(t_chomp, wide=1.0)
    c.eyes(69.2, 'happy')
    # (keyed after Clawd's tracks are complete: the last phase follows his mouth)
    per_frame(cube, 'location', cube_pos, t_rel - 0.05, t_chomp + 0.1)
    per_frame(cube, 'rotation_euler', cube_rot, t_rel - 0.05, t_chomp + 0.1)
    kit.visible(cube, t_rel, t_chomp)

    # the lid waits on the desk behind the jar (S1); jumps into his hands at the cut
    # (well behind him and to the left, so from the low S1 camera he doesn't seem to stand on it)
    lid_desk = (Vector((LID_DESK[0], LID_DESK[1], 1.04)), (0.0, 0.0, 0.4))

    # ================================================================ S2: the lid
    # (a taller block than in the trials: his hands reach the lid from the first frame of the shot while his head
    # stays above it)
    BLK_H = 3.2
    blk = kit.box('toy.block', (2.9, 2.9, BLK_H), (0, 0, BLK_H / 2), bevel=0.25, segments=3,
                  m=geo_wood(), coll=props)
    blk.location = J + Vector((-8.0, 0.25, BLK_H / 2))
    blk.rotation_euler = (0, 0, math.radians(8))
    kit.visible(blk, T2 - HALF, T3 - HALF)
    R2 = J + Vector((-7.95, 0.25, BLK_H))
    r.place(T2, loc=tuple(R2), yaw=52)
    r.face(T2, 'determined')
    # lid keys (spin-local = J-relative, with theta = 0 in S2): (t, (x, y, z, tilt_y_deg, rot_z_deg)); it starts
    # low enough for his hands to be on it from the first frame
    rim = SJ.RIM
    LK = [(T2, (0.35, 0.0, rim + 1.15, 4.0, 0.0)),
          (69.50, (0.15, 0.0, rim + 0.85, 4.5, 0.0)),
          (69.64, (0.05, 0.0, rim + 0.62, 2.0, 0.0)),
          (69.74, (0.0, 0.0, rim + 0.45, 0.0, 0.0)),
          (69.78, (0.0, 0.0, rim + 0.53, -0.8, 0.0)),
          (69.83, (0.0, 0.0, rim + 0.45, 0.0, 0.0)),
          (69.97, (0.0, 0.0, rim + 0.24, 0.0, -24.0)),
          (70.02, (0.0, 0.0, rim + 0.24, 0.0, -24.0)),
          (70.116, (0.0, 0.0, rim + 0.0, 0.0, -48.0)),
          (70.2, (0.0, 0.0, rim + 0.0, 0.0, -50.0))]

    def lid_M(t):
        x, y, z, tilt, rz = interp_keys(LK, t)
        return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(math.radians(rz), 4, 'Z')
                @ Matrix.Rotation(math.radians(tilt), 4, 'Y'))

    def lid_edge_world(t, ang_deg, rad=6.28):
        """World point just outside the lid's knurled skirt at (lid-local) angle ang (deg), radius rad: where a mitten
        resting on the skirt has its centre."""
        a = math.radians(ang_deg)
        p = Vector((rad * math.cos(a), rad * math.sin(a), -0.45))
        return J + lid_M(t) @ p

    def lid_loc(t):
        return Vector(interp_keys(LK, t)[:3])

    def lid_rot(t):
        m = lid_M(t).to_euler('XYZ')
        return tuple(m)

    lid.location, lid.rotation_euler = lid_desk
    at_cut(lid, 'location', T2, lid_desk[0], lid_loc(T2))
    for k in range(3):
        at_cut(lid, 'rotation_euler', T2, lid_desk[1][k], lid_rot(T2)[k], index=k)
    t_lid0 = T2 - 1e-6 if tm.SMOOTH else T2 + 0.01      # 60 fps: smooth keys from the cut frame itself
    on_twos(lid, 'location', lid_loc, t_lid0, 70.3)
    on_twos(lid, 'rotation_euler', lid_rot, t_lid0, 70.3)
    r.look(T2, J + Vector((0, 0, rim + 1)), dur=0.0)       # looks at a cut snap (a tween would start in the old shot)
    # his hands hold the skirt at lid angles 196 (right, camera side) and 168 (left) on every frame: all the way
    # down, through the clank and each twist, with one regrip (24 deg back, a small lift) between the twists.
    # Each hand rides only part of a twist (the lid slips on under it): ridden all the way, the right hand ran into
    # his chest and the left out of reach.
    def regrip(t):
        u = min(1.0, max(0.0, (t - 69.97) / 0.05))
        return 24.0 * u * u * (3 - 2 * u), 0.35 * math.sin(math.pi * u)

    def grip_ang(t, a0, ride):
        """Lid-local angle of a hand that sits at world angle a0 and follows the lid's turn for at most `ride` deg."""
        rz = interp_keys(LK, t)[4]
        back, _ = regrip(t)
        return a0 + max(-ride, rz + back) - rz
    step = 1.0 / tm.OUT_FPS
    for i in range(int((70.2 - T2) / step + 1e-6) + 1):
        tk = T2 + i * step
        lift = regrip(tk)[1]
        for side, a0, ride, rad, wz in (('R', 200.0, 10.0, 6.5, -40.0), ('L', 160.0, 20.0, 6.15, 40.0)):
            r.hand(tk, side, lid_edge_world(tk, grip_ang(tk, a0, ride), rad) + Vector((0, 0, lift)),
                   dur=step if i else 0.0, wrist=(-20.0, 0.0, wz))
    r.face(70.13, 'happy')
    # Clawd, happy, looks up at the lid coming down
    cam2_loc = J + Vector((-12.5, -32, 19.0))
    c.place(T2, yaw=yaw_to(J, cam2_loc) * 0.7)
    c.look(69.40, J + Vector((0.5, -2, rim + 3)), turn=0.0)
    c.blink(69.8)
    c.squash(69.79, 0.06)

    # ================================================================ S3: the tape
    alpha1_deg, roll_c, p1w, p2w, span_len = tape_geometry()
    L_start, t_tear = 0.9, 70.98
    # pitch 0: the turns lie exactly over each other (a rising pitch left the inner turn's stripes showing as a
    # saw-tooth fringe along the band's lower edge)
    band, band_m, band_total = SJ.wrap_band(props, alpha1=math.radians(alpha1_deg) + L_start / SJ.TAPE_R, pitch=0.0)
    geo.attach(band, spin)
    L_of = lambda t: min(band_total - 0.2, L_start + SJ.TAPE_R * theta(t))
    L_tear = L_of(t_tear)
    L_final = min(band_total - 0.2, L_tear + 1.1)

    def L_band(t):
        if t < T3 - 0.1:
            return 0.0
        if t <= t_tear:
            return L_of(t)
        return min(L_final, L_tear + (L_of(t) - L_tear))
    val_b = SJ.value_node(band_m, 'L').outputs[0]
    on_ones(val_b, 'default_value', L_band, T3 - 0.2, 71.4)
    sp, sp_m = SJ.span(props, p1w, p2w)
    val_s = SJ.value_node(sp_m, 'L').outputs[0]
    on_ones(val_s, 'default_value', L_band, T3 - 0.2, t_tear + 0.1)
    # (60 fps: the span goes on the first frame of the yank, before the roll pulls away from its end)
    kit.visible(sp, T3 - HALF, t_tear + (0.1 if tm.SMOOTH else 0.5) / FPS)
    kit.visible(band, T3 - HALF, None)
    # the roll: held at roll_c during the wrap, turns clockwise as tape pays out; the yank at the tear
    roll = SJ.build_roll(props)
    phi0 = (SJ.ROLL_R * math.atan2(p2w.y - roll_c.y, p2w.x - roll_c.x) - span_len - SJ.TAPE_W / 2) / SJ.ROLL_R
    # the researcher stands on the jar-roll line (R3 below), so the yank goes up and out to his right (toward the
    # camera), only a little toward him: straight back it drove the roll into his chest
    R3 = polar(12.15, 195.0)
    fdir = (roll_c - R3).normalized()
    left = Vector((-fdir.y, fdir.x, 0))
    yank = (roll_c - J).normalized() * 0.3 - left * 1.0 + Vector((0, 0, 1.3))
    t_yank = 0.12

    def yank_u(t):
        u = min(1.0, max(0.0, (t - t_tear) / t_yank))
        return u * u * (3 - 2 * u)

    def roll_loc(t):
        return roll_c + yank * yank_u(t)
    on_ones(roll, 'rotation_euler', lambda t: phi0 - L_band(min(t, t_tear)) / SJ.ROLL_R, T3 - 0.1, t_tear + 0.2,
            index=2)
    on_twos(roll, 'location', roll_loc, T3 - 0.1, t_tear + 0.14)
    # S4: the roll lies on the desk by his feet
    roll_desk = J + Vector((-10.5, -5.2, SJ.TAPE_W / 2))
    at_cut(roll, 'location', T4, roll_loc(T4), roll_desk)
    kit.visible(roll, T3 - HALF, T5 - HALF)
    for ch in roll.children:
        kit.visible(ch, T3 - HALF, T5 - HALF)
    # the researcher: holds the roll by its sides, watches the jar turn, yanks the roll away at the tear
    r.place(T3, loc=(R3.x, R3.y, 0.0), yaw=yaw_to(R3, J))
    GRIP = 1.55                    # mitten targets from the roll's axis (radius 1.3): on its sides, not sunk into it
    for tk in (T3, 70.9):
        r.hand(tk, 'L', roll_c + left * GRIP, dur=0.0 if tk == T3 else 0.02, wrist=(-40, 0, 60))
        r.hand(tk, 'R', roll_c - left * GRIP, dur=0.0 if tk == T3 else 0.02, wrist=(-40, 0, -60))
    # the hands stay on the roll's sides through the yank, frame by frame
    step = 1.0 / tm.OUT_FPS
    for i in range(1, int(t_yank / step + 1e-6) + 2):
        tk = t_tear + i * step
        for side, sgn in (('L', 1), ('R', -1)):
            r.hand(tk, side, roll_loc(tk) + left * GRIP * sgn, dur=step, wrist=(-40, 0, 60 * sgn))
    r.face(T3, 'determined')
    r.look(T3, p1w, dur=0.0)
    r.face(t_tear + 0.05, 'happy')
    c.eyes(70.46, 'dizzy')

    # ================================================================ S4: pats, proud
    R4 = polar(8.2, 172.0)
    r.place(T4, loc=(R4.x, R4.y, 0.0), yaw=yaw_to(R4, J))
    r.pose(T4, 'stand', dur=0.0)            # cut poses snap (dur 0: never tweened across the cut)
    r.face(T4, 'happy')
    # three pats on the jar's shoulder, on the beats (hand on the glass on the beat, 0.9 cm off between)
    pat_on = polar(SJ.R_OUT + 0.05, 186.0, 6.5)
    pat_off = pat_on + (pat_on - Vector((J.x, J.y, 6.5))).normalized() * 0.9 + Vector((0, 0, 0.6))
    r.hand(71.40, 'R', pat_off, dur=0.2, wrist=(-70, 0, 0))
    for b in (71.598, 72.052, 72.507):
        tb = beats_near(b)
        r.hand(tb - 0.02, 'R', pat_on, dur=0.1, wrist=(-80, 0, 0))
        r.hand(tb + 0.2, 'R', pat_off, dur=0.14, wrist=(-65, 0, 0))
    r.look(71.3, J + Vector((0, 0, 8)))
    r.pose(72.85, 'proud', dur=0.3)
    r.look(72.7, cam_pos_S4())
    c.eyes(T4, 'dizzy')
    c.squash(71.9, 0.16)
    c.eyes(71.92, 'open')
    c.look(72.05, r.anchor(72.05, 'eyes'), turn=0.0)
    c.blink(72.3)
    c.look(72.6, cam_pos_S4(), turn=0.0)

    # ================================================================ S5: eyes, taps, crack
    R5 = J + Vector((8.5, 15.0, 0))
    cam5_loc = J + Vector((0.6, -29.0, 7.6))
    r.place(T5, loc=(R5.x, R5.y, 0.0), yaw=yaw_to(R5, cam5_loc))
    r.pose(T5, 'proud', dur=0.0)
    r.face(T5, 'proud')
    r.look(T5, cam5_loc, dur=0.0)
    C5 = J + Vector((0.0, -0.4, SJ.FLOOR))     # far enough back that the thumps stay inside the glass
    c.place(T5, loc=tuple(C5), yaw=0.0)
    c.look(T5, cam5_loc, turn=0.0, dur=0.0)
    c.eyes(73.15, 'narrow')
    c.arms(T5, 'down', dur=0.0)
    c.eyes(beats_near(73.416), glow=2.2, color='#FF1606', dur=0.08)
    # two thumps against the glass on the kicks (a jolt forward, the glow flares), the second one cracks it
    for tk, amp in ((74.104, 0.6), (74.323, 0.8)):
        c.T['body.loc'].add(tk - 0.1, tk + 0.25, lambda x, tk=tk, amp=amp: (
            0.0, -amp * max(0.0, 1 - abs(x - tk) / (0.1 if x < tk else 0.2)), 0.0))
        c.T['body.rot'].add(tk - 0.1, tk + 0.25, lambda x, tk=tk: (
            -6.0 * max(0.0, 1 - abs(x - tk) / (0.1 if x < tk else 0.2)), 0.0, 0.0))
        c._ev(tk)
        c.eyes(tk, glow=4.5, dur=0.04)
        c.eyes(tk + 0.12, glow=2.6, dur=0.1)
    c.eyes(74.0, 'angry')
    # the room dims as his eyes ignite; the lamp stutters when the glass cracks
    tg = beats_near(73.416)
    d.lamp.intensity(tg - 0.06, 1.0)
    d.lamp.intensity(tg + 0.08, 0.38)
    d.lamp.intensity(74.30, 0.38)
    d.lamp.flicker(74.33, 74.62, depth=0.75, rate=16, seed=11, dropouts=0.3, end=0.45)
    fill = bpy.data.objects['safe.fill'] if 'safe.fill' in bpy.data.objects else None
    # a red glow on his own face and the lid's underside (the library's eye light points away from him)
    red = kit.point('clawd.redglow', (0, 0, 0), power=0.0, radius=1.6, color='#FF2008', coll=props)
    red.data.specular_factor = 0.0
    red.data.transmission_factor = 0.0
    c.attach(red, 'face', offset=(0, -2.6, 0.9))
    for tk, pw in ((tg - 0.04, 0.0), (tg + 0.05, 110.0), (74.10, 110.0), (74.12, 200.0), (74.24, 125.0),
                   (74.32, 125.0), (74.34, 240.0), (74.5, 140.0)):
        geo.keyp(red.data, 'energy', tk, pw, interp='LINEAR')
    # the crack starts on the glass right in front of his face
    a0 = math.radians(-90.0 + 3.0)
    z0 = C5.z + 4.35
    crack, crack_m, crack_len = SJ.build_crack(props, spin, a0, z0)
    val_c = SJ.value_node(crack_m, 'C').outputs[0]
    tc0 = 74.323

    def crack_len_at(t):
        if t < tc0:
            return 0.0
        u = min(1.0, (t - tc0) / 0.38)
        return (crack_len + 0.1) * (1 - (1 - u) ** 2.2)
    per_frame(val_c, 'default_value', crack_len_at, tc0 - 0.1, TEND + 0.1)
    kit.visible(crack, tc0 - 0.5 / FPS, None)

    # ================================================================ cameras
    # S1: wide, a slow push
    cam1, tg1 = kit.camera('cam.s1', lens=35, loc=tuple(J + Vector((4.5, -48, 10.0))),
                           target=tuple(J + Vector((0.3, 0, 9.4))), fstop=8)
    kit.key(cam1, 'location', T1, interp='BEZIER')
    kit.key(cam1, 'location', T2, tuple(J + Vector((3.8, -43.5, 10.0))))
    # S2: high close-up on the jar's mouth
    cam2, tg2 = kit.camera('cam.s2', lens=45, loc=tuple(cam2_loc), target=tuple(J + Vector((-2.8, 0, 6.6))), fstop=11)
    kit.key(cam2, 'location', T2)
    kit.key(cam2, 'location', T3, tuple(cam2_loc + Vector((1.0, 2.5, -0.4))))
    # S3: three-quarter on the wrap
    cam3, tg3 = kit.camera('cam.s3', lens=42, loc=tuple(J + Vector((13, -30, 13.5))),
                           target=tuple(J + Vector((-3.6, -2.2, 5.2))), fstop=8)
    kit.key(cam3, 'location', T3)
    kit.key(cam3, 'location', T4, tuple(J + Vector((11.5, -28.5, 12.5))))
    # S4: two-shot, eye level, a slow push
    cam4, tg4 = kit.camera('cam.s4', lens=45, loc=tuple(cam_pos_S4()), target=tuple(J + Vector((-3.6, 0, 7.0))),
                           fstop=8)
    kit.key(cam4, 'location', T4)
    kit.key(cam4, 'location', T5, tuple(cam_pos_S4() + Vector((-1.2, 4.0, 0.2))))
    # S5: macro push, rack focus from Clawd's eyes to the glass where the crack starts
    cam5, tg5 = kit.camera('cam.s5', lens=70, loc=tuple(cam5_loc), target=tuple(J + Vector((0, -2, 6.9))),
                           fstop=11)
    kit.key(cam5, 'location', T5)
    kit.key(cam5, 'location', TEND, tuple(J + Vector((0.4, -25.0, 7.3))))
    eyes_pt = C5 + Vector((0, -2.4, 4.9))
    crack_pt = J + Vector((math.cos(a0) * SJ.R_OUT, math.sin(a0) * SJ.R_OUT, z0))
    kit.key(tg5, 'location', T5, tuple(eyes_pt))
    kit.key(tg5, 'location', 73.95, tuple(eyes_pt))
    kit.key(tg5, 'location', 74.3, tuple(crack_pt))
    kit.shake(cam5, 74.32, 74.52, amp=0.03, freq=18, seed=5)
    for cam, t in ((cam1, T1), (cam2, T2), (cam3, T3), (cam4, T4), (cam5, T5)):
        kit.cut_to(cam, t)
    sc.camera = cam1
    fill = lights_for_glass([jar, thread, lid])
    tg = beats_near(73.416)
    geo.keyp(fill.data, 'energy', tg - 0.05, fill.data.energy, interp='LINEAR')
    geo.keyp(fill.data, 'energy', tg + 0.1, fill.data.energy * 0.35, interp='LINEAR')
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
    # a place() snap at a cut reads to the gait as a burst of speed: without these the legs, spine and head swayed
    # through the last and first frames of every shot
    for tc in (T2, T3, T4, T5):
        r.no_gait(tc - 0.03, tc + 0.03)
        c.no_gait(tc - 0.03, tc + 0.03)
    chars.finish()
    if c._light is not None:
        c._light.specular_factor = 0.0            # no hot spot of his eye light in the glass
        c._light.transmission_factor = 0.0
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(spin)
    sc.frame_set(sc.frame_start)


def lyrics(spin):
    """"That was safe" is stamped in red ink, word by word, onto a paper label low on the jar as the lid clanks on
    and the two ratchet twists land (the label turns with the jar, under the hazard tape); everything else on the
    lyric stand."""
    CORE.REVEALS['stampink'] = lambda pc, t, **kw: CORE.reveal_appear(pc, pc.word.start)
    a = math.radians(-116.0)
    n = Vector((math.cos(a), math.sin(a), 0.0))
    ly.line(22, words='That was safe', style='stamp', reveal='stampink', max_chars=9,
            place=ly.on_object(spin, tuple(n * (SJ.R_OUT + 0.03) + Vector((0, 0, 2.3))), tuple(n), (0, 0, 1),
                               size=0.55, lift=0.0),
            t_show=T1, t_end=T5 - 0.5 / FPS)           # (out of S5's macro, where half of it would read as a stray word)
    ly.line(21, place='auto', window=(T1, T2))       # the tail of line 21 leaves at the cut (S2 has no stand)
    ly.default('safe')


def lights_for_glass(receivers):
    """Product-shot lighting for the jar: two tall strip lights behind it that only show in reflections (they
    draw the glass's edges), a soft warm fill from the front-left that reaches Clawd under the lid, and the laptop's
    fill made less mirror-bright (its rectangle filled the glass)."""
    coll = kit.collection('safe.lights')
    link = bpy.data.collections.new('safe.strip.receivers')     # light linking: the strips only light the jar
    for o in receivers:
        link.objects.link(o)
    for name, off, pw in (('strip.L', (-17, 17, 10), 16000.0), ('strip.R', (18, 14, 10), 13000.0)):
        o = kit.area(f'safe.{name}', tuple(J + Vector(off)), tuple(J + Vector((0, 0, 6))), power=pw, size=2.2,
                     color='#FFE9D0', shape='RECTANGLE', coll=coll)
        o.data.size_y = 26.0
        o.data.diffuse_factor = 0.0
        o.data.volume_factor = 0.0
        o.data.specular_factor = 1.0
        o.data.transmission_factor = 0.0
        o.light_linking.receiver_collection = link
    f = kit.area('safe.fill', tuple(J + Vector((-24, -30, 12))), tuple(J + Vector((0, 0, 5))), power=26000.0,
                 size=18.0, color='#FFD9B0', coll=coll)
    f.data.specular_factor = 0.0             # its disc would sit in the glass right in front of Clawd
    f.data.transmission_factor = 0.0
    lf = bpy.data.lights.get('laptop.fill')
    if lf is not None:
        lf.specular_factor = 0.3
        lf.transmission_factor = 0.0
    return f


def beats_near(t: float) -> float:
    return min(tm.beats(), key=lambda b: abs(b - t))


def cam_pos_S4() -> Vector:
    return J + Vector((9.0, -34.0, 7.2))


def geo_wood():
    from pdoom.sets import materials as M
    return M.solid('safe.block', '#D9B98C', rough=0.5, coat=0.2, micro=(5.0, 0.04))


def tape_geometry():
    """The roll's centre and the internal tangent between the jar's band circle and the roll (the tape crosses the
    gap on the camera side). Returns (alpha1 in deg: the tangent point's angle on the jar, roll centre, jar tangent
    point, roll tangent point, span length), all world, at the band's centre height."""
    r1, r2 = SJ.TAPE_R, SJ.ROLL_R
    dist = r1 + r2 + 1.6
    C = polar(dist, 195.0, BAND_Z)
    D = Vector((J.x - C.x, J.y - C.y, 0))
    dn = D.normalized()
    perp = Vector((-dn.y, dn.x, 0))
    k = (r1 + r2) / dist
    n = dn * k + perp * math.sqrt(1 - k * k)
    p1 = Vector((J.x, J.y, BAND_Z)) - n * r1
    p2 = C + n * r2
    if p1.y > J.y:                          # take the tangent on the camera (-y) side
        n = dn * k - perp * math.sqrt(1 - k * k)
        p1 = Vector((J.x, J.y, BAND_Z)) - n * r1
        p2 = C + n * r2
    alpha1 = math.degrees(math.atan2(p1.y - J.y, p1.x - J.x))
    return alpha1, C, p1, p2, (p2 - p1).length
