"""loom · 123.868-131.140 · "I'm upping my P(doom) / Just as foretold by Loom / From masked pre-training days /
To recursive self-upgrade"

The last and biggest DOOM: the needle slams into 100 and the brass gauge's glass cracks. A tiny table loom weaves
the future by itself: a tapestry of a giant Clawd over a tiny city, whose eyes glow. A baby photo of Clawd in a
smiley mask ("masked pre-training"). Then Clawd conducts a Clawd 1.6x his size out of flying panels, who builds one
1.6x bigger, who builds one bigger still, and we crash into the giant's eye.

Shot list
  M1 123.868-126.125  the gauge, reading 75: a slow push from a low three-quarter to the dial as the needle
                      trembles ("I'm upping my P(doom)"). DOOM 4 on the downbeat 125.686: the needle slams to 100 and
                      bounces off the pin, the glass cracks from the 100 end, the gauge jumps, a crash zoom onto the
                      crack and a violent shake, dust bursts off the desk round the plinth, glass chips spray, a red
                      flash, the lamp stutters.
  M2 126.125-127.042  "Just as foretold": high over the loom's front corner, looking into the shed: a self-weaving
                      table loom; the shuttle shoots across on the beats (126.14, 126.595) trailing orange weft, the
                      beater slams it home, the heddle shafts swap the shed.
  M3 127.042-127.917  "by Loom": the camera cranes up and round to the front as the shuttle blurs back and forth and
                      the tapestry weaves itself: a tiny city, then a giant Clawd rising behind it; on "Loom" (127.54)
                      his woven eyes glow red.
  M4 127.917-129.833  "From masked pre-training days": a framed baby photo on the desk (a real render of little
                      Clawd in the smiley mask on a knitted cushion, aged): focus racks from a baby bottle onto it
                      on "masked" (128.2); Clawd scuttles in, looks at it fondly, sighs on "days", turns to us, eyes
                      narrowing.
  M5 129.833-131.140  "To recursive self-upgrade": he raises his arms and the panels of a Clawd 1.6x his size fly in
                      and snap together; it lights up and builds one 1.6x bigger, which builds one bigger still
                      (2.56x, 4.1x), faster each time, the camera pulling back to fit them; then a crash zoom into the
                      giant's glowing eye, held for the last two frames: ilya's glowing box follows.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom import timing as tm
from pdoom.chars import clawd as CL
from pdoom.chars import geo as cg
from pdoom import lyrics as ly
from pdoom.fx import particles
from pdoom.sets import build_desk, geo
from pdoom.timing import FPS

from scenes import loom_loom as LL
from scenes import loom_photo as LPH
from scenes import loom_upgrade as UP
from scenes.boot_common import Cam, shake

T0, TEND = 123.868, 131.14
T_HIT = 125.686
T_LOOM = 127.54
CUTS = [T0, 3027 / FPS, 3049 / FPS, 3070 / FPS, 3116 / FPS]

LOOM_AT = Vector((-26.0, -22.0, 0.0))
PHOTO = Vector((52.0, -27.0, 0.0))
GENS = [(Vector((59.5, -29.0, 0.0)), 1.0, 18.0), (Vector((38.0, -22.0, 0.0)), 1.6, 12.0),
        (Vector((15.0, -13.0, 0.0)), 1.6 ** 2, 8.0), (Vector((-17.0, -6.0, 0.0)), 1.6 ** 3, 4.0)]
BUILD = [(129.84, 130.10), (130.15, 130.42), (130.47, 130.76)]
SWING = 0.10            # DOOM 4: the needle's swing from 75 starts this early, so it reaches the 100 pin on T_HIT


def frames(f0, f1):
    """Scene frames for a per-frame keying loop over [f0, f1]: whole frames at 24 fps; built for 60 fps (tm.SMOOTH)
    every output frame (k * 0.4), so fast moves (crash zooms, the shuttle) are sampled where they are seen."""
    return tm.out_frames(f0, f1) if tm.SMOOTH else range(f0, f1 + 1)


def cut_t(t_cut, frames_before=0.0):
    """Time a CONSTANT step tied to the cut at t_cut goes, `frames_before` whole frames early: half a frame before the
    cut frame at 24 fps (the shutter edge); 0.1 frame before it built for 60 fps (between two 60 fps exposures, on the
    same side of the camera marker as at 24 fps)."""
    f = round(t_cut * FPS) - frames_before
    return (tm.switch_frame(f) if tm.SMOOTH else f - 0.5) / FPS


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, u):
    return a + (b - a) * u


def catmull(keys, t):
    """Catmull-Rom through [(t, Vector)] (clamped), parameterised by time."""
    if t <= keys[0][0]:
        return keys[0][1].copy()
    if t >= keys[-1][0]:
        return keys[-1][1].copy()
    i = max(k for k in range(len(keys) - 1) if keys[k][0] <= t)
    t0, p1 = keys[i]
    t1, p2 = keys[i + 1]
    p0 = keys[i - 1][1] if i > 0 else p1 - (p2 - p1)
    p3 = keys[i + 2][1] if i + 2 < len(keys) else p2 + (p2 - p1)
    x = (t - t0) / (t1 - t0)
    x2, x3 = x * x, x * x * x
    return 0.5 * ((2 * p1) + (-p0 + p2) * x + (2 * p0 - 5 * p1 + 4 * p2 - p3) * x2 + (-p0 + 3 * p1 - 3 * p2 + p3) * x3)


# ------------------------------------------------------------------------------------------------ build


def build():
    sc = kit.new_scene('loom')
    img, baby = LPH.render_baby_photo(kit.cache_dir('loom', 'photo') + '/baby_raw.png', t_render=T0 + 0.5)
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable', 'books', 'clip', 'mug', 'notes', 'pen'})
    lc = kit.collection('loom.lights')
    gauge_shot(d, lc)
    L = loom_shot(d, lc)
    c = photo_shot(d, lc, img)
    gens = upgrade_shot(d, lc, c)
    for g in gens:
        fine_eyes(g)
    lamp_moves(d)
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        _lyrics(d, L, gens)
    sc.frame_set(sc.frame_start)


def _lyrics(d, L, gens):
    """Revision 2: the lyrics in the picture. "I'm upping my / P(doom)" typed onto the gauge's dial face (the upper
    half, clear of the needle), under the glass that cracks on DOOM 4; "Just as foretold by" gilded on the loom's breast
    beam as sung, and LOOM woven into the tapestry's sky (loom_loom: the last rows it weaves, glowing with the eyes);
    "From masked pre-training days" as letter tiles that lie masked (face down) and flip up as sung; "To recursive
    self-upgrade" one word at the feet of each Clawd, each bigger than the last."""
    ly.skip(39)                                       # "askew" (held) is up in gpus until the cut
    # M1: typed on the dial face as sung (dial space: +Y is 12 o'clock, +Z out of the face)
    ly.line(40, style='typed', support='none', max_chars=13, rows=2, exit='none', t_end=CUTS[1],
            place=ly.on_object(d.gauge.dial, (0.0, 1.02, 0.226), (0, 0, 1), (0, 1, 0), size=0.52, lift=0.002))
    # the loom's breast beam, gilded as sung (the loom exists in M2 and M3)
    ly.line(41, words=(0, 4), style='goldleaf', support='none', exit='none', t_end=CUTS[3],
            place=ly.on_object(L.root, (0.0, -11.07, 7.43), (0, -1, 0), (0, 0, 1), size=0.64, lift=0.01))
    ly.skip(41, 'Loom')                               # woven into the tapestry
    # M4: masked tiles under the baby photo
    ly._stage_for(0.5 * (CUTS[3] + CUTS[4]), ly.StageSpec(cells=15.0, rows=2, height=0.065, u=(0.36, 0.3, 0.42),
                                                          v=(0.11, 0.15, 0.2)), ly.collection())
    ly.line(42, style='tiles', preview='blank', reveal_opts=dict(axis='Y'), t_show=CUTS[3],
            spec=ly.StageSpec(cells=15.0, rows=2))
    # M5: each word at the feet of a bigger Clawd
    # "To" stands between the photo and him (in the push's first frame), the others at the feet of the bigger ones
    for words, at, yaw, size in (('To', Vector((55.6, -30.2, 0.0)), 14.0, 1.9),
                                 ('recursive', GENS[1][0] + Vector((2.0, -9.5, 0.0)), 12.0, 2.3),
                                 ('self-upgrade', GENS[2][0] + Vector((2.5, -16.0, 0.0)), 8.0, 3.3)):
        ly.line(43, words=words, place=ly.At(at, face=yaw, size=size), exit='none', t_end=TEND)
    ly.default('loom')


def switch(owner, prop, t_cut, before, after):
    """Change owner.prop from `before` to `after` exactly at a cut: CONSTANT keys just before the frame before the
    cut and just before the cut frame (cut_t), so the cut frame itself already shows the new value and the last frame
    of the outgoing shot (at 60 fps too) still shows the old one."""
    geo.keyp(owner, prop, cut_t(t_cut, 1), before, interp='CONSTANT')
    geo.keyp(owner, prop, cut_t(t_cut), after, interp='CONSTANT')


def lamp_moves(d):
    """The desk lamp re-aims at each cut (never seen moving): the gauge, the loom (out of reach: stays), the photo,
    the lineup."""
    lamp = d.lamp
    prev = None
    for t, target, reach in ((CUTS[0], d.anchors['gaugeCenter'] + Vector((-2, -6, -6)), 20.0),
                             (CUTS[3], PHOTO + Vector((2, 2, 3)), 34.0), (CUTS[4], Vector((22, -16, 6)), 34.0)):
        if prev is not None:
            lamp.aim(cut_t(t, 1), prev[0], reach=prev[1], interp='CONSTANT')
        lamp.aim(cut_t(t), target, reach=reach, interp='CONSTANT')
        prev = (target, reach)


# ------------------------------------------------------------------------------------------------ M1: DOOM 4


def dust_mat():
    m = kit.mat('loom.dust', '#B9AE9E', rough=0.9, spec=0.2)
    return m


def gauge_shot(d, lc):
    g = d.gauge
    # the needle must hit the 100 pin on the downbeat, with the crack (gauge.CRACK_T = T_HIT), not ~0.1 s after it:
    # its damped swing from 75 takes ~0.1 s, so DOOM 4's needle event starts SWING early (the crack stays on T_HIT)
    g.events = [(te - SWING if abs(te - T_HIT) < 1e-6 else te, v, p) for te, v, p in g.events]
    g.tremble(124.4, T_HIT - SWING - 0.03, amp=1.8, rate=17.0, seed=4)
    g.jolt(T_HIT, amp_deg=6.5, dur=0.65)
    bpy.context.view_layer.update()
    R = g.root.matrix_world
    Dm = g.dial.matrix_world
    # dust thrown up off the desk round the plinth, lit by the lamp
    pcoll = kit.collection('loom.fx')
    dm = dust_mat()
    for i, (lx, ly) in enumerate(((-7.4, -4.0), (0.0, -4.4), (7.4, -4.0), (-7.4, 4.0), (7.4, 4.0), (0.0, 4.4))):
        p = R @ Vector((lx, ly, 0.25))
        out = (R.to_3x3() @ Vector((lx, ly, 0.0))).normalized()
        ob = particles.burst(f'loom.dust{i}', center=tuple(p), t0=T_HIT, count=70, speed=(18.0, 60.0),
                             direction=tuple(out * 0.8 + Vector((0, 0, 1.0))), cone=55.0, gravity=0.05, drag=3.2,
                             life=(1.2, 2.6), size=0.05, emit=0.05, floor=0.0, streak=0.0, seed=20 + i, coll=pcoll)
        ob.data.materials.clear()
        mod = ob.modifiers[0]
        _swap_material(mod, dm)
    # glass chips off the crack at the 100 end
    chip = Dm @ Vector((3.2, -3.0, 1.0))
    nrm = (Dm.to_3x3() @ Vector((0, 0, 1))).normalized()
    particles.burst('loom.chips', center=tuple(chip), t0=T_HIT + 1 / FPS, count=46, speed=(40.0, 130.0),
                    direction=tuple(nrm + Vector((0.3, 0, 0.5))), cone=50.0, gravity=1.0, drag=1.2, life=(0.35, 0.9),
                    size=0.035, streak=0.012, seed=31, coll=pcoll, colors=('#FFFFFF', '#DDEBFF', '#8FA6C8'),
                    strength=4.0)
    # a red alarm flash from the dial and the lamp stuttering
    red = kit.point('loom.redflash', tuple(g.front(5.0)), power=0.0, radius=2.0, color='#FF2A12', coll=lc)
    red.data.specular_factor = 0.4
    f_hit = math.ceil(T_HIT * FPS)                      # the first frame after the hit
    geo.keyp(red.data, 'energy', (f_hit - 1) / FPS, 0.0, interp='CONSTANT')
    for t, pw in ((f_hit / FPS, 1500.0), (T_HIT + 0.08, 600.0), (T_HIT + 0.16, 1000.0), (T_HIT + 0.3, 250.0),
                  (CUTS[1], 60.0)):
        geo.keyp(red.data, 'energy', t, pw, interp='LINEAR')
    d.lamp.flicker(T_HIT + 0.02, CUTS[1], depth=0.8, rate=16.0, seed=9, dropouts=0.35, end=0.85)
    # a warm key on the gauge from the front left (the lamp is behind it), a rim for the brass
    kit.spot('loom.gkey', tuple(g.front(40.0) + Vector((-24, 0, 20))), tuple(g.center()), power=60000.0,
             angle_deg=34, blend=0.7, radius=3.0, color='#FFD6A6', coll=lc)
    # the camera: a slow push, the crash zoom onto the crack on the hit, a violent shake
    gc = g.center()
    crack = Dm @ Vector((3.0, -2.6, 0.9))
    cam = Cam('loom.cam1', 40, Dm @ Vector((7.0, -4.5, 70.0)), gc, fstop=11.0)
    shake(cam.cam, 125.93, CUTS[1], amp=0.08, freq=20.0, seed=9)
    f0, f1 = int(math.floor(T0 * FPS)) - 1, int(math.ceil(CUTS[1] * FPS)) + 1
    for f in frames(f0, f1):
        t = f / FPS
        u = smoothstep((t - T0) / (T_HIT - 0.02 - T0))
        u = 0.55 * u + 0.45 * max(0.0, (t - T0) / (T_HIT - 0.02 - T0)) ** 1.6 if t < T_HIT else 1.0
        loc = (Dm @ Vector((7.0, -4.5, 70.0))).lerp(Dm @ Vector((1.8, -3.6, 31.0)), min(u, 1.0))
        lens = lerp(40.0, 52.0, min(u, 1.0))
        tgt = gc
        if t >= T_HIT:
            k = smoothstep((t - T_HIT) / 0.08)
            loc = loc.lerp(Dm @ Vector((1.6, -3.2, 26.5)), k)
            lens = lerp(52.0, 48.0, k)
            k2 = smoothstep((t - 125.93) / 0.09)
            loc = loc.lerp(Dm @ Vector((2.8, -2.2, 15.5)), k2)
            lens = lerp(lens, 96.0, k2)
            tgt = gc.lerp(crack, k2) + Vector((0, 0, -1.2 * k * (1 - k2)))
        cam.key(t, loc=loc, target=tgt, focus=tgt, lens=lens, interp='LINEAR')
    shake(cam.cam, T_HIT - 0.01, T_HIT + 0.45, amp=0.32, freq=17.0, seed=7)
    cam.cut(CUTS[0])
    bpy.context.scene.camera = cam.cam


def _swap_material(mod, m):
    """Point a particles.burst node tree's Set Material node at m (non-emissive dust)."""
    ng = mod.node_group
    for n in ng.nodes:
        if n.bl_idname == 'GeometryNodeSetMaterial':
            n.inputs['Material'].default_value = m


# ------------------------------------------------------------------------------------------------ M2/M3: the loom


def loom_shot(d, lc):
    L = LL.build_loom(kit.collection('loom.loom'), tuple(LOOM_AT), 0.0)
    # the shuttle leaves on the beat and arrives 0.11 s later; then a flurry that finishes the picture
    b1, b2, b3 = 126.14 + 0.11, 126.595 + 0.11, 127.049 + 0.08
    flurry = [127.19 + k * 0.06 for k in range(6)]
    picks = [(b1, 1), (b2, -1), (b3, 1)] + [(t, -1 if k % 2 == 0 else 1) for k, t in enumerate(flurry)]
    fell = [(CUTS[1] - 1.0, 0.12), (b1, 0.12), (b1 + 0.12, 0.2), (b2, 0.2), (b2 + 0.12, 0.28), (b3, 0.28),
            (b3 + 0.05, 0.36)]
    v = 0.36
    for k, t in enumerate(flurry):
        v = 0.36 + 0.64 * (k + 1) / len(flurry)
        fell.append((t + 0.03, v))
    LL.weave(L, picks, fell, CUTS[1] - 0.2, CUTS[3] + 0.1, T_LOOM)
    # the loom only exists for its two shots (it stands where the giants go)
    for o in L.objects + [L.root] + [ch for o in L.objects for ch in o.children]:
        kit.visible(o, cut_t(CUTS[1]), cut_t(CUTS[3]))
    # light: a warm key from the front left, a cool rim from behind (the lamp can't reach)
    key = kit.spot('loom.lkey', tuple(LOOM_AT + Vector((-30, -42, 44))), tuple(LOOM_AT + Vector((0, -3, 8))),
                   power=90000.0, angle_deg=38, blend=0.7, radius=4.0, color='#FFD9B0', coll=lc)
    rim = kit.area('loom.lrim', tuple(LOOM_AT + Vector((18, 30, 22))), tuple(LOOM_AT + Vector((0, 0, 8))),
                   power=26000.0, size=20.0, color='#A9C4FF', coll=lc)
    rim.data.specular_factor = 0.15
    for lo, pw in ((key, 90000.0), (rim, 26000.0)):
        switch(lo.data, 'energy', CUTS[1], 0.0, pw)
        switch(lo.data, 'energy', CUTS[3], pw, 0.0)
    W = L.root.matrix_world

    def fell_y_at(t):
        for (ta, va), (tb, vb) in zip(fell, fell[1:]):
            if ta <= t <= tb:
                return L.fell_y(va + (vb - va) * smoothstep((t - ta) / (tb - ta)))
        return L.fell_y(fell[-1][1] if t > fell[-1][0] else fell[0][1])
    # M2: low over the front right corner, looking back along the cloth into the shed: the shuttle shoots across
    cam2 = Cam('loom.cam2', 30, W @ Vector((11.0, -19.0, 12.0)), W @ Vector((-1.0, -6.0, 8.4)), fstop=8.0)
    f0, f1 = int(math.floor(CUTS[1] * FPS)) - 1, int(math.ceil(CUTS[2] * FPS)) + 1
    for f in frames(f0, f1):
        t = f / FPS
        ys = fell_y_at(t) + 1.3
        u = (t - CUTS[1]) / (CUTS[2] - CUTS[1])
        cam2.key(t, loc=W @ Vector((lerp(9.0, 6.5, u), lerp(-20.0, -17.5, u), lerp(20.0, 19.0, u))),
                 target=W @ Vector((lerp(0.5, -1.0, u), ys - 0.5, 8.3)), focus=W @ Vector((1.0, ys, 8.4)),
                 lens=34.0, interp='LINEAR')
    cam2.cut(CUTS[1])
    # M3: crane up and round to the front, over the finished tapestry
    cloth_c = W @ Vector((0.0, (LL.Y_FRONT + LL.FELL_MAX) / 2, LL.WARP_Z))
    P = [(CUTS[2], W @ Vector((14.0, -22.0, 15.0))), (127.30, W @ Vector((10.0, -27.0, 21.0))),
         (127.60, W @ Vector((3.0, -29.5, 26.5))), (CUTS[3] + 0.05, W @ Vector((2.0, -27.0, 25.5)))]
    cam3 = Cam('loom.cam3', 30, P[0][1], cloth_c, fstop=8.0)
    f0, f1 = int(math.floor(CUTS[2] * FPS)) - 1, int(math.ceil(CUTS[3] * FPS)) + 1
    for f in frames(f0, f1):
        t = f / FPS
        k = smoothstep((t - CUTS[2]) / 0.5)
        tgt = (W @ Vector((0.0, -5.0, 8.6))).lerp(cloth_c + Vector((0, 0, 0.3)), k)
        cam3.key(t, loc=catmull(P, t), target=tgt, lens=lerp(28.0, 36.0, smoothstep((t - CUTS[2]) / 0.8)),
                 interp='LINEAR')
    cam3.cut(CUTS[2])
    return L


# ------------------------------------------------------------------------------------------------ M4: the photo


def photo_shot(d, lc, img):
    coll = kit.collection('loom.photo')
    root, glass = LPH.build_frame(coll, tuple(PHOTO), 8.0, img)
    # a teething ring lying in the foreground (the rack focus starts on it)
    ring_at = PHOTO + Vector((-3.6, -11.0, 0.32))
    bpy.ops.mesh.primitive_torus_add(major_radius=1.1, minor_radius=0.32, location=tuple(ring_at))
    ring = bpy.context.object
    ring.name = 'loom.teether'
    kit.link(ring, coll)
    kit.smooth(ring, 180)
    kit.assign(ring, kit.mat('loom.teether', '#9BD3C7', rough=0.25, coat=0.6, sss=0.2))
    bottle_at = PHOTO + Vector((-5.2, -11.0, 0.0))
    LPH.baby_bottle(coll, bottle_at)
    # Clawd: in from the right, looks at his baby photo, sighs, turns to us
    c = chars.Clawd(kit.collection('clawd'), loc=tuple(PHOTO + Vector((18.0, -3.0, 0.0))), yaw=-90.0)
    c.visible(cut_t(CUTS[3]))
    c.eyes(CUTS[3], 'open')
    g0 = GENS[0][0]
    c.move(128.52, 128.98, [tuple(g0)], face='forward')
    c.look(129.08, PHOTO + Vector((0, 0, 5.0)), turn=0.9)
    c.eyes(129.1, 'happy')
    c.squash(129.32, 0.14)                              # a fond sigh on "days"
    c.look(129.6, PHOTO + Vector((-2, -40, 6)), turn=0.8)
    c.eyes(129.64, 'narrow')
    # light: a soft warm key from the left and a small glint light that reflects in the frame's glass
    kit.area('loom.pkey', tuple(PHOTO + Vector((-22, -26, 20))), tuple(PHOTO + Vector((0, 0, 5))), power=26000.0,
             size=16.0, color='#FFE0BC', coll=lc)
    fb = bottle_at + Vector((0, 0, 3.0))
    cam = Cam('loom.cam4', 50, PHOTO + Vector((-2.5, -25.0, 5.2)), PHOTO + Vector((0.2, 0.0, 4.2)), fstop=4.0,
              focus=fb)
    cam.key(CUTS[3], loc=PHOTO + Vector((-2.5, -25.0, 5.2)), target=PHOTO + Vector((0.2, 0.0, 4.2)),
            focus=fb, interp='LINEAR')
    cam.key(128.18, focus=fb, interp='BEZIER')
    cam.key(128.46, focus=PHOTO + Vector((0.2, -0.6, 5.0)), interp='BEZIER')
    cam.key(CUTS[4] + 0.05, loc=PHOTO + Vector((-0.5, -19.5, 6.0)), interp='LINEAR')
    cam.key(129.0, target=PHOTO + Vector((1.2, 0.0, 4.8)), interp='BEZIER')
    cam.key(CUTS[4], target=PHOTO + Vector((3.6, -1.0, 4.6)), interp='BEZIER')
    cam.cut(CUTS[3])
    return c


# ------------------------------------------------------------------------------------------------ M5: the upgrade


def upgrade_shot(d, lc, c0):
    gens = [c0]
    col = kit.collection('loom.gens')
    for k, (p, s, yaw) in enumerate(GENS[1:], start=1):
        gk = chars.Clawd(col, name=f'gen{k}', loc=tuple(p), yaw=yaw, scale=s, seed=40 + k)
        gk.eyes(CUTS[4], 'open', glow=0.0)
        gens.append(gk)
    # the builders: arms up to conduct, a cheer when the next one lights up, then it builds the next
    for k, (t0, t1) in enumerate(BUILD):
        b, n = gens[k], gens[k + 1]
        b.look(t0 - 0.02, GENS[k + 1][0] + Vector((0, 0, 4 * GENS[k + 1][1])), turn=0.4, dur=0.12)
        b.arms(t0, 'up', dur=0.08)
        b.eyes(t0, 'narrow' if k == 0 else 'open', glow=2.5, color='#FFB24A')
        b.arms(t1 + 0.02, 'cheer', dur=0.08)
        b.eyes(t1 + 0.02, 'happy')
        n.eyes(t1 + 0.03, 'open', glow=3.5, color='#FFB24A', dur=0.06)
        n.squash(t1 + 0.04, 0.12)
    last = gens[-1]
    last.eyes(BUILD[-1][1] + 0.03, 'open', glow=6.0, color='#FFB24A', dur=0.06)
    last.look(BUILD[-1][1] + 0.1, Vector((-7.0, -40.0, 20.0)), turn=0.0)
    for k, (t0, t1) in enumerate(BUILD):
        UP.assemble(gens[k + 1], t0, t1, seed=11 + k, spread=9.0)
    # sparkles as each one completes
    pc = kit.collection('loom.fx')
    for k, (t0, t1) in enumerate(BUILD):
        p, s, _ = GENS[k + 1]
        particles.burst(f'loom.ding{k}', center=tuple(p + Vector((0, -2.4 * s, 4.0 * s))), t0=t1, count=60,
                        speed=(40.0 * s, 110.0 * s), cone=180.0, gravity=0.3, drag=3.0, life=(0.25, 0.6),
                        size=0.05 * s, streak=0.01, seed=50 + k, coll=pc, colors=('#FFF6D8', '#FFC860', '#FF8A3A'),
                        strength=6.0)
    # light for the lineup: a big warm key from the front left, a cool rim from the right
    for lo in (kit.spot('loom.ukey', (-40.0, -110.0, 90.0), (18.0, -12.0, 8.0), power=420000.0, angle_deg=40,
                        blend=0.7, radius=8.0, color='#FFD9B0', coll=lc),
               kit.area('loom.urim', (90.0, 20.0, 40.0), (15.0, -12.0, 10.0), power=120000.0, size=50.0,
                        color='#9FBCFF', coll=lc)):
        switch(lo.data, 'energy', CUTS[4], 0.0, lo.data.energy)
    # the camera: an exponential pull back that fits each new giant, then a crash zoom into the last one's eye
    p3, s3, yaw3 = GENS[-1]
    Ry = Matrix.Rotation(math.radians(yaw3), 3, 'Z')
    eye = p3 + Ry @ (Vector((1.95, -2.25 - 0.15, 4.88)) * s3)
    P = [(CUTS[4], Vector((57.0, -47.0, 6.0))), (130.12, Vector((51.0, -70.0, 13.0))),
         (130.44, Vector((36.0, -98.0, 22.0))), (130.78, Vector((9.0, -128.0, 33.0))),
         (130.94, Vector((7.0, -130.0, 34.0))), (131.0, Vector((-2.0, -80.0, 25.0))),
         (131.035, eye + Vector((0.8, -25.0, 0.5))), (TEND + 0.05, eye + Vector((0.8, -24.0, 0.5)))]
    T = [(CUTS[4], Vector((57.5, -28.0, 4.4))), (130.12, Vector((48.0, -25.0, 6.0))),
         (130.44, Vector((34.0, -19.0, 9.0))), (130.78, Vector((5.0, -13.0, 13.0))),
         (130.94, Vector((4.0, -13.0, 13.5))), (131.0, Vector((-3.0, -14.5, 18.0))), (131.035, eye), (TEND + 0.05, eye)]
    cam = Cam('loom.cam5', 40, P[0][1], T[0][1], fstop=8.0)
    f0, f1 = int(math.floor(CUTS[4] * FPS)) - 1, int(math.ceil(TEND * FPS)) + 1
    for f in frames(f0, f1):
        t = f / FPS
        if t < 130.94:
            lens = lerp(40.0, 34.0, smoothstep((t - 130.4) / 0.4))
        else:
            lens = lerp(34.0, 85.0, smoothstep((t - 130.94) / 0.095))
        cam.key(t, loc=catmull(P, t), target=catmull(T, t), lens=lens, interp='LINEAR')
    cam.key(130.94, fstop=8.0, interp='LINEAR')
    cam.key(131.035, fstop=16.0, interp='LINEAR')
    cam.cut(CUTS[4])
    return gens


def fine_eyes(ch):
    """Rebuild a Clawd's 'open' eye meshes finer for the close-ups (the crash zoom ends on gen3's 4.1x eye at 85 mm):
    a 32-segment-per-corner pill (not 10) with 6 bevel rings (not 3), and the flat front cap filled with a thin ring
    plus a centre fan instead of one n-gon. The n-gon was fan-triangulated at render from its top vertex: long
    sliver triangles with tilted smooth normals that showed as a seam down the eye and a notch at its top. Same outline,
    depth, bevel and placement as Clawd._eye_obj, so the eye looks the same at normal sizes."""
    for (shape, side), ob in ch._eye_objs.items():
        if shape != 'open':
            continue
        (outline, slot, depth, bev), = ch._eye_outlines('open')
        # the 'open' pill of Clawd._eye_outlines, finer, with exact half-circle ends: its default corner radius
        # (0.999 of half the width) leaves a 0.0006-wide flat at the top and bottom whose bevel rings fold over
        # (the notch at the top of the eye)
        outline = cg.rrect(0.64, 1.36, rr=0.32, n=32)
        sx = 1 if side == 'L' else -1
        if side == 'R':
            outline = cg.mirror_x(outline)
        bm = bmesh.new()
        cg.decal(bm, outline, depth=depth, back=0.12, bevel=bev, rings=6, mat=slot,
                 M=Matrix.Translation((sx * CL.EYE_X, CL.FACE_Y, CL.EYE_Z)))
        bm.normal_update()
        cap, = [f for f in bm.faces if len(f.verts) > 8 and f.normal.y < -0.999]
        outer, mi = list(cap.verts), cap.material_index
        c = cap.calc_center_median()
        bmesh.ops.delete(bm, geom=[cap], context='FACES_ONLY')
        inner = [bm.verts.new(c + (v.co - c) * 0.95) for v in outer]   # a thin ring that takes the bevel's tilt
        mid = bm.verts.new(c)
        n = len(outer)
        for i in range(n):                                # same winding as the cap (facing -Y)
            j = (i + 1) % n
            bm.faces.new((outer[i], outer[j], inner[j], inner[i])).material_index = mi
            bm.faces.new((inner[i], inner[j], mid)).material_index = mi
        lim = math.radians(50.0)                          # as geo.to_object(..., sharp=50)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            e.smooth = not (len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim)
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
