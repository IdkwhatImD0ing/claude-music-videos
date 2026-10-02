"""boot · 0.000-5.692 · "I see sparks of AGI in your eyes"

Night, the desk. Clawd sits dormant, plugged into the laptop by the USB cable; the researcher leans over him.

Shot list (song seconds; characters on twos, cameras / light / sparks smooth at 24 fps):

 1  drift    0.000-1.601  35 mm macro, 2 cm off the desk, lamp OFF (only the laptop's cool spill). A motion-control
                          truck carries the single paperclip across the frame (sharp, f/3.2), then the camera tilts up
                          as the focus racks from the clip to the laptop screen: Clawd's orange boot logo and a
                          progress bar. Cut on the beat 1.601.
 2  lamp     1.601-2.739  24 mm, low in front of the pair, looking up past them to the lamp head against the window;
                          the researcher leans over the sleeping Clawd in the laptop's blue light. CLICK on the
                          downbeat 2.056: the bulb snaps on, the room goes warm, he glances up at the lamp (shock),
                          then back to Clawd and leans in to peer on "see" (2.35). Slow push in. Cut on "sparks".
 3  sparks   2.739-4.809  50 mm from the front left, low: the cable runs from the laptop across the desk into
                          Clawd's port; Clawd (eyes shut, drooping, arms limp) centre, the researcher peering in on the
                          right, the P(doom) gauge at 0 behind. Three electric sparks race along the cable (motion-blur
                          streaks, crackling embers, a flash and an ember burst at the plug) into Clawd: A (3.677) his
                          left eye pops open and glows, G (4.06) the right one, I (4.355) both flare, his vinyl flashes
                          orange, the lid pops, he stretches up awake; the researcher startles on A, leans back in on
                          G and gasps on I. Push in; camera shake on I. Cut on "in" 4.809.
 4  eyes     4.809-5.692  85 mm close-up from beside Clawd up into the researcher's face (awe), lit amber from below
                          by Clawd's eyes. "your eyes" (5.0): his round glasses reflect two glowing eyes. Slow push.
"""
import math

import bpy

from mathutils import Vector

from pdoom import chars, kit
from pdoom import timing as tm
from pdoom.chars import researcher as rsr
from pdoom.sets import build_desk, geo

from scenes.boot_common import Cam, embers, flash_light, shake, spark_run

EYE = '#FFB24A'          # Clawd's eye glow (warm amber)
SPARK_CORE = '#F2FCFF'
SPARK_HALO = '#8FDcFF'
HIT = 0.06               # Clawd's eye hits land just after the spark reaches the plug (the glow ramps up from it)

# 'peer' with reachable hands: the library pose puts both wrists inside the coat behind his back, so clear_arm pushed
# one arm out through the coat's side as a straight stick. Here the arms hang swept back beside the hips.
rsr.POSES.setdefault('boot_peer', dict(rsr.POSES['peer'], hands=((2.0, 0.9, 3.7), (-2.0, 0.9, 3.7)),
                                       wrist=((25, 0, 0), (25, 0, 0))))


def straighten_cable_tail(cab, radius=0.2):
    """Re-route the desk cable's last few cm so the wire runs straight out of the back of the plug (on its axis to
    ~1 cm past the boot) before it bends down to the desk in a smooth curve, and level the plug on that axis. The
    sparks shot is framed on this cable. Same control points as sets/props.build_cable apart from the tail."""
    if cab is None or cab.tube is None or cab.tube.type != 'CURVE' or len(cab.pts) < 2:
        print('[run] boot: cable tail left as built')
        return
    start, end = cab.pts[0].copy(), cab.pts[-1].copy()
    mid = start.lerp(end, 0.55) + Vector((6.0, -3.0, 0.0))
    mid.z = radius
    dirv = Vector((-0.9, 0.8, 0.0)).normalized()
    head = [start, start + Vector((2.2, 0, 0)), start + Vector((4.5, -1.5, radius - start.z)), mid]
    # on the plug axis to ~3.7 cm (the boot ends at 2.75), then a bend of ~1.5 cm radius down to the desk
    tail = [end + Vector((-6.4, 5.6, radius - end.z)), end + dirv * 4.6 + Vector((0, 0, -0.3)), end + dirv * 2.6, end]
    pts = geo.catmull(head + tail, 10)
    for i, p in enumerate(pts):
        if 2 < i < len(pts) - 3:
            p.z = max(radius, p.z)
    dev = max((a - b).length for a, b in zip(pts[:25], cab.pts[:25]))
    print(f'[run] boot: cable tail straightened ({len(cab.pts)} -> {len(pts)} points; laptop half moved {dev:.3f})')
    cd = cab.tube.data
    old = cd.splines[0]
    sp = cd.splines.new('POLY')
    sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        sp.points[i].co = (p.x, p.y, p.z, 1.0)
    sp.use_cyclic_u = False
    cd.splines.remove(old)
    cab.pts = [Vector(p) for p in pts]
    cab._prep()
    # build_cable aims the plug along the old curve's last 1% (which rose ~11 deg into the port); make it level, on
    # the same axis as the wire
    plug = bpy.data.objects.get('cable.plugB')
    if plug is not None and plug.parent is not None and plug.parent.matrix_world.is_identity:
        plug.location = end + dirv * 1.0
        plug.rotation_euler = (-dirv).to_track_quat('Y', 'Z').to_euler()
    else:
        print('[run] boot: cable plug left as built')


def build():
    sc = kit.new_scene('boot')
    d = build_desk(kit.collection('desk'), mood='night')
    A = d.anchors
    straighten_cable_tail(d.cable)
    fx = kit.collection('boot.fx')

    # ------------------------------------------------------------------ times
    wa = tm.word('I see sparks', 'AGI')
    tA, tG, tI = tm.syl(wa, 0), tm.syl(wa, 1), tm.syl(wa, 2)          # 3.677 4.06 4.355
    t_see = tm.word('I see sparks', 'see')['start']                     # 2.35
    t_sparks = tm.word('I see sparks', 'sparks')['start']               # 2.739
    t_in = tm.word('I see sparks', 'in')['start']                       # 4.809
    t_your = tm.word('I see sparks', 'your')['start']                   # 5.0
    t_click = 2.056
    t_end = 5.692

    # ------------------------------------------------------------------ the room: dark until the lamp clicks
    d.lamp.click(t_click)
    d.laptop.set_image('boot', 'A')
    SCR = 1.3
    d.laptop.screen(0.0, glow=2.4)
    d.laptop.screen(t_click - 0.5 / tm.FPS, glow=2.4)
    d.laptop.screen(t_click + 3 / tm.FPS, glow=SCR)
    bounce = d.room.bounce.data
    full_bounce = bounce.energy
    geo.keyp(bounce, 'energy', 0.0, full_bounce * 0.4, interp='CONSTANT')
    geo.keyp(bounce, 'energy', t_click - 0.5 / tm.FPS, full_bounce * 0.4, interp='LINEAR')
    geo.keyp(bounce, 'energy', t_click + 2 / tm.FPS, full_bounce, interp='LINEAR')
    # a cool spill from the screen that the dark opening needs (it goes out with the lamp click: the eye adapts)
    SPILL = 14000.0
    spill = kit.area('boot.spill', (-9.0, 10.0, 9.0), (2.0, -6.0, 1.0), power=SPILL, size=14.0, color='#8FC8FF',
                     coll=kit.collection('boot.fx'))
    spill.data.specular_factor = 0.0                    # no big white reflection of it on the lacquered desk
    geo.keyp(spill.data, 'energy', 0.0, SPILL, interp='CONSTANT')
    geo.keyp(spill.data, 'energy', t_click - 0.5 / tm.FPS, SPILL, interp='LINEAR')
    geo.keyp(spill.data, 'energy', t_click + 2 / tm.FPS, 0.0, interp='LINEAR')
    # the laptop pulses as it sends each spark
    for ts in (tA, tG, tI):
        d.laptop.screen(ts - 0.34, glow=SCR)
        d.laptop.screen(ts - 0.30, glow=2.6)
        d.laptop.screen(ts - 0.12, glow=SCR)

    # ------------------------------------------------------------------ Clawd: dormant, then booting
    cs = A['clawdSpot']
    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=(cs.x, cs.y, 0), yaw=0)
    c.eyes(0.0, 'shut', glow=0.0, color=EYE)
    c.arms(0.0, 'down', dur=0.0)
    c.T['body.rot'].set(0.0, (6.0, 0.0, 0.0), 0.0)          # powered down: nose drooping
    c.T['lid'].set(0.0, 0.04, 0.0)
    c.eyes(tA + HIT, 'open', glow=5.0, side='L', dur=0.06)
    c.squash(tA + HIT, 0.12, 0.5)
    c.eyes(tG + HIT, 'open', glow=5.0, side='R', dur=0.06)
    c.squash(tG + HIT, 0.12, 0.5)
    c.eyes(tI + HIT, glow=9.0, dur=0.05)
    c.eyes(tI + 0.35, glow=5.0, dur=0.3)
    c.eyes(t_your + 0.02, glow=8.0, dur=0.04)                # a flare on "your": his glasses catch it
    c.eyes(t_your + 0.35, glow=5.0, dur=0.3)
    c.T['body.rot'].set(tI + 0.1, (-3.0, 0.0, 0.0), 0.12)   # snaps upright, a little proud
    c.T['body.rot'].set(tI + 0.5, (0.0, 0.0, 0.0), 0.3)
    c.stretch(tI + 0.06, 0.22, 0.8)
    # only the near arm goes up: the far one stays under the lid seam, so it doesn't show through the open lid's
    # side gap (from c3's front-left angle it read as a stub poking up between his teeth)
    c.arms(tI + 0.1, 'up', side='R', dur=0.1)
    c.arms(tI + 0.1, 'out', side='L', dur=0.1)
    c.arms(tI + 0.55, 'rest', dur=0.25)
    c.lid(tI + 0.08, 0.2, 0.08)
    c.lid(tI + 0.4, 0.0, 0.15)

    # ------------------------------------------------------------------ the researcher, leaning over him
    face = c.anchor(0.0, 'face')
    R0 = Vector((15.0, -9.8, 0.0))
    dv = face - R0
    yaw = math.degrees(math.atan2(dv.x, -dv.y))
    r = chars.Researcher(kit.collection('researcher'), name='researcher', loc=(R0.x, R0.y, 0), yaw=yaw)
    r.pose(0.0, 'lean_in', dur=0.0)
    r.face(0.0, 'neutral')
    r.look(0.2, face, dur=0.2)
    r.look(t_click + 0.16, d.anchors['lampHead'], dur=0.14)      # the light comes on: he glances up at it
    r.face(t_click + 0.1, 'shock')
    r.face(t_see + 0.1, 'neutral')
    r.pose(t_see + 0.3, 'boot_peer', dur=0.45)
    r.look(t_see + 0.35, face, dur=0.4)
    r.face(2.9, 'nervous')
    # A: a startle, G: back in, I: recoil with a gasp
    r.pose(tA + 0.12, 'lean_in', dur=0.12)
    r.face(tA + 0.02, 'shock')
    r.pose(tG + 0.2, 'boot_peer', dur=0.18)
    r.face(tG + 0.1, 'awe')
    r.pose(tI + 0.14, 'gasp', dur=0.12)
    r.face(tI + 0.02, 'shock')
    r.pose(t_in + 0.1, 'hold', dur=0.35)
    r.look(t_in + 0.15, face, dur=0.25)
    # awe from the first frame of the close-up: c4's marker sits on the 24 fps frame nearest t_in (kit.cut_to), which
    # can be before t_in, so switch the face 0.3 frame before that frame
    r.face((round(t_in * tm.FPS) - 0.3) / tm.FPS, 'awe')
    # the reflection comes on with the flare on "your", bright within a frame or two (a 0.15 s fade showed flat
    # dull-ochre pills over his eyes for ~8 frames)
    r.glasses_reflect(t_your + 0.04, t_end + 0.3, EYE, strength=6.0, fade=0.05)

    # ------------------------------------------------------------------ sparks along the cable
    cab = d.cable
    run = 0.30
    for k, ts in enumerate((tA, tG, tI)):
        spark_run(f'spark{k}', cab.at, ts - run, ts, fx, core=SPARK_CORE, halo=SPARK_HALO,
                  ease=lambda u: u ** 1.35, seed=k + 1, crackle=5, light_power=1300.0)
        port = cab.at(1.0)
        embers(f'burst{k}', port + Vector((0, 0, 0.3)), ts, fx, n=16, seed=11 + k, speed=(25, 70),
               life=(0.15, 0.42), color='#CFF3FF', up=0.9)
        flash_light(f'flash{k}', port + Vector((-1.6, 1.4, 1.2)), ts, fx, power=3000.0 if k < 2 else 6000.0,
                    color='#BFEBFF', decay=0.09)
    # the vinyl flashes from inside on I (keyed on the body material's emission)
    try:
        b = c.m_body.node_tree.nodes['Principled BSDF']
        b.inputs['Emission Color'].default_value = kit.srgb('#FF6A20')
        s = b.inputs['Emission Strength']
        geo.keyp(s, 'default_value', tI - 1.0 / tm.FPS, 0.0, interp='LINEAR')
        geo.keyp(s, 'default_value', tI + 0.5 / tm.FPS, 0.45, interp='LINEAR')
        geo.keyp(s, 'default_value', tI + 0.22, 0.0, interp='LINEAR')
    except Exception as e:  # noqa: BLE001
        print(f'[run] boot: vinyl flash skipped: {e}')

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('boot.cams')
    clip = A['clipSpot']
    V = Vector
    # 1 drift: from the front right of the clip toward the laptop; a lateral truck carries the clip across the
    #   frame, then the camera tilts up to the screen as the focus racks from the clip to the boot logo
    scr = A['laptopScreen']
    ax = (scr - clip).to_2d().normalized()
    ax = V((ax.x, ax.y, 0.0))
    perp = V((ax.y, -ax.x, 0.0))                        # to the right of the view axis
    dA = clip - ax * 7.8 + perp * 3.2 + V((0, 0, 2.4))
    dB = clip - ax * 7.0 - perp * 2.6 + V((0, 0, 2.2))
    dC = clip - ax * 4.5 - perp * 6.0 + V((0, 0, 2.3))
    tA_ = clip + ax * 4.0 + perp * 3.0 + V((0, 0, 0.7))
    tB_ = clip + ax * 4.5 - perp * 2.8 + V((0, 0, 0.9))
    tC_ = clip.lerp(scr, 0.5) - perp * 3.0 + V((0, 0, 1.5))
    c1 = Cam('cam.drift', 35, dA, tA_, fstop=3.2, focus=clip + V((0.0, 0.0, 0.1)), coll=cams)
    c1.key(0.0, loc=dA, target=tA_, interp='LINEAR')
    c1.key(0.95, loc=dB, target=tB_)
    c1.key(1.65, loc=dC, target=tC_)
    c1.key(0.85, focus=clip + V((0.0, 0.0, 0.1)))
    c1.key(1.35, focus=scr)
    # 2 lamp: low in front of the pair, looking up past them to the lamp head against the window
    c2 = Cam('cam.lamp', 24, (-6.0, -30.0, 1.4), (8.6, 0.0, 13.0), fstop=5.6, focus=(11.0, -7.0, 5.0), coll=cams)
    c2.key(1.55, loc=(-6.0, -30.0, 1.4), target=(8.6, 0.0, 13.0), interp='LINEAR')
    c2.key(2.8, loc=(-4.8, -27.6, 1.6), target=(8.9, 0.0, 12.6), interp='LINEAR')
    # 3 sparks: from the front left, so the cable runs from the laptop into Clawd's port; push in over the sparks
    c3 = Cam('cam.sparks', 50, (-18.0, -38.0, 6.5), (7.0, 1.0, 5.0), fstop=16.0, focus=cs + V((-1.0, -2.2, 4.0)),
             coll=cams)
    c3.key(2.7, loc=(-18.0, -38.0, 6.5), target=(7.0, 1.0, 5.0))
    c3.key(3.3, loc=(-16.8, -36.0, 6.3), target=(7.2, 0.5, 5.0))
    c3.key(4.85, loc=(-11.0, -28.5, 5.6), target=(9.0, -2.5, 5.0))
    shake(c3.cam, tI - 0.02, tI + 0.4, amp=0.12, freq=14.0, seed=3)
    # 4 eyes: close on the researcher's glasses, from beside Clawd's face
    eyes = r.anchor(5.2, 'eyes')
    to_c = (face - eyes)
    to_c.z = 0
    to_c.normalize()
    side = V((-to_c.y, to_c.x, 0))
    p0 = eyes + to_c * 17.0 + side * 3.0 + V((0, 0, -2.4))
    p1 = eyes + to_c * 13.5 + side * 2.2 + V((0, 0, -1.8))
    c4 = Cam('cam.eyes', 85, p0, eyes, fstop=5.6, coll=cams)
    c4.key(4.78, loc=p0, target=eyes + V((0, 0, 0.05)), interp='LINEAR')
    c4.key(5.72, loc=p1, target=eyes + V((0, 0, 0.05)), interp='LINEAR')

    c1.cut(0.0)
    c2.cut(1.601)
    c3.cut(t_sparks)
    c4.cut(t_in)
    sc.camera = c1.cam
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()
    from pdoom import lyrics as ly
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(d, c3, c4, t_sparks, t_in)


def lyrics(d, c3, c4, t_sparks, t_in):
    """Revision 2: every sung word in the picture (docs/lib/lyrics.md).

    1 drift   the held "I" (1.407) types itself on the laptop's boot screen as the focus lands there
    2 lamp    "I see" on the lyric stand
    3 sparks  "sparks of" on the stand; A-G-I are three smoked-acrylic blocks standing beside the USB cable, dark until
              each spark runs past them into Clawd (A 3.677, G 4.06, I 4.355), lit in his eye colour
    4 eyes    "in your eyes" in the same amber light-up blocks under the researcher's chin as his glasses reflect the
              eyes
    """
    from pdoom import lyrics as ly
    st = ly._state()
    # 1: the boot screen types "I" (held to 2.35: the lamp shot and the stand take it over)
    ly.line(0, words='I', style='screen', place=ly.laptop(d, u=0.5, v=0.2), preview=None, t_end=1.601,
            color='#FFC48A', strength=5.0)
    st['claimed'].discard((0, 0))
    # 2: "I see": painted blocks hanging on threads beside the pair, dark until the lamp clicks on
    cam2 = Vector((-5.4, -29.0, 1.5))
    loc2 = Vector((-2.0, -0.4, 5.4))
    f2 = cam2 - loc2
    f2.z = 0.0
    ly.line(0, words='I see', style='blocks', place=ly.At(loc2, face=f2.normalized(), size=2.5), t_show=1.601,
            t_end=t_sparks, strings=True)
    # a small warm spot on them from the camera side once the lamp is on (the lamp only rims them from behind)
    aim = loc2 + Vector((0.0, 0.0, 1.2))
    sp = kit.spot('boot.lyricfill', tuple(aim + f2.normalized() * 22.0 + Vector((3.0, 0.0, 9.0))), tuple(aim),
                  power=0.0, angle_deg=22, blend=0.6, radius=2.0, color='#FFD9A8', coll=kit.collection('boot.fx'))
    sp.data.specular_factor = 0.3
    geo.keyp(sp.data, 'energy', 2.056 - 0.5 / tm.FPS, 0.0, interp='LINEAR')
    geo.keyp(sp.data, 'energy', 2.056 + 2 / tm.FPS, 9000.0, interp='CONSTANT')
    geo.keyp(sp.data, 'energy', t_sparks - 0.5 / tm.FPS, 0.0, interp='CONSTANT')
    st['claimed'].discard((0, 0))
    st['claimed'].discard((0, 1))
    # 3: A-G-I on three smoked-acrylic blocks hanging on threads over the cable where it rises into Clawd's port:
    #    the sparks run under them and each block lights in his eye colour as its spark goes in
    cam_p = Vector((-14.5, -33.0, 6.0))
    loc = Vector((1.2, -0.9, 3.4))
    to_cam = cam_p - loc
    to_cam.z = 0.0
    ly.line(0, words='AGI', style='glow', place=ly.At(loc, face=to_cam.normalized(), size=1.5), t_show=t_sparks,
            t_end=t_in, glow_color=EYE, light=0, strings=True)
    # 4: "in your eyes": light-up amber blocks on the stand of the close-up (clear of Clawd's lid in the foreground)
    ly.line(0, words='in your eyes', style='glow', place='auto', glow_color=EYE, t_show=t_in, light=0,
            spec=ly.StageSpec(cells=12.0, rows=1, u=(0.68, 0.64, 0.72)))
    # 3: everything else on the stand
    ly.default('boot', window=(t_sparks, t_in))
