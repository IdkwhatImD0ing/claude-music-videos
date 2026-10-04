"""backprop · 74.779-82.052 · "Forward MLP, backward, repeat / Now von Neumann's obsolete / Sharp left..."

A three-layer marble run on the desk is the MLP (3-4-3 funnel cups on a plywood board, cardboard chutes, orange
flip-flop rockers, a bulb per node, the full net strung in cotton thread behind). Three glass cat's-eye marbles run the
forward pass one layer per letter, rewind up the run on "backward" (spin reversed, rockers un-flip, bulbs flash cool
blue), repeat faster; on the fast rewind one marble flies off the top of a chute and strikes the model vacuum-tube
computer on the shelf beside the run. It teeters, tips off the shelf and shatters on the desk (Voronoi fracture +
Bullet, glass tubes, sparks). A tube rolls out of the wreck, its glow dying, and knocks a domino at the frame edge:
the lead-in to `leftturn`.

Lyrics in the picture (revision 2): lines 23-24 on the lyric stand, M-L-P lighting up in it as the marbles hit the
input, hidden and output layers; OBSOLETE rubber-stamped in red across the fallen VON NEUMANN plaque; SHARP and
LEFT as painted blocks standing among the shards where the panning camera looks when each is sung.

Shot list
  B1 74.779-76.597  wide 3/4, slow push   Forward: marbles hit the input cups on M (74.84), hidden on L (75.244),
                                          output on P (75.66), drop into the tray (75.95). "backward" (76.12): they
                                          leap out of the tray and rewind up: output 76.30, hidden 76.48, input 76.656.
  B2 76.597-77.507  low, fast dolly       "repeat": forward again at ~2.7x (76.89-77.30) and back (77.38-77.68).
  B3 77.507-78.416  the right end + shelf The last marble shoots up its chute too fast (77.60) and flies off; it hits
                                          the computer on "Now" (77.72): the lamps stutter, it lurches to the edge.
  B4 78.416-78.870  close on the computer It teeters on the shelf edge ("von"), lamps blinking, tubes glowing.
  B5 78.870-79.875  desk level, low       "Neumann's": it tips over (78.82), falls and shatters on the beat 79.325:
                                          glass tubes burst, sparks, lamps scatter; filaments die.
  B6 79.875-82.052  aftermath close-up    "obsolete": the brass VON NEUMANN plaque face up among the shards (a shard
                                          settles on it) with the dying tube rolling past behind; from 80.35 the
                                          camera tracks the tube, glow fading, to the domino; it taps the domino's
                                          corner (81.87) and the domino tips as we cut to `leftturn`. (Revision 2's
                                          in-picture lyrics stamped OBSOLETE on the plaque; off since revision 3.)
"""
import math

import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import lyrics as ly
from pdoom.sets import build_desk, geo
from pdoom.timing import FPS

from scenes import backprop_fall as FALL
from scenes import backprop_run as RUN

T0, TEND = 74.779, 82.052
CUTS = [74.779, 76.597, 77.507, 78.416, 78.870, 79.875]     # B6 starts before "obsolete" (80.04): it is stamped there
BOARD = Vector((-10.0, -4.0, 0.0))            # the run's board: front face, bottom centre (world)


# ------------------------------------------------------------------------------------------------ keying helpers


def per_frame(owner, path, fn, t0, t1, *, index=-1, interp='LINEAR'):
    """Key fn(t) on every frame in [t0, t1]: whole frames at 24 fps, every output frame in a smooth 60 fps build
    (the fast passes cross a whole cup in about one 24 fps frame, so 24 fps chords would cut through cups and rockers)."""
    f0, f1 = int(math.floor(t0 * FPS)), int(math.ceil(t1 * FPS))
    for f in FALL.frames(f0, f1):
        geo.keyp(owner, path, f / FPS, fn(f / FPS), interp=interp, index=index)


def W(p) -> Vector:
    """Board-local -> world."""
    return BOARD + Vector(p)


# ------------------------------------------------------------------------------------------------ timing

M_, L_, P_ = 74.84, 75.244, 75.66
RT = RUN.Route


def marble_keys(route: RUN.Route, stray: bool = False):
    """The t -> u map: forward on M-L-P, rewind on "backward", forward and rewind again ~2.7x faster on "repeat",
    then a third, faster run: the stray marble jumps its hidden cup at the end of the first chute."""
    k = [(70.0, route.U_HOP), (M_ + route.U_HOP, route.U_HOP), (M_, 0.0), (L_, RT.U_H), (P_, RT.U_O),
         (P_ + (RT.U_T - RT.U_O), RT.U_T), (P_ + (RT.U_END - RT.U_O), RT.U_END)]
    # backward: out of the tray at 76.12, output 76.30, hidden 76.48, input 76.656, back in the hopper
    k += [(76.12, RT.U_END), (76.19, RT.U_T), (76.30, RT.U_O), (76.48, RT.U_H), (76.656, 0.0),
          (76.70, route.U_HOP)]
    # repeat: forward then rewind
    k += [(76.86, route.U_HOP), (76.89, 0.0), (77.04, RT.U_H), (77.19, RT.U_O), (77.30, RT.U_T),
          (77.35, RT.U_END)]
    k += [(77.37, RT.U_END), (77.40, RT.U_T), (77.44, RT.U_O), (77.52, RT.U_H), (77.60, 0.0),
          (77.62, route.U_HOP)]
    # and again, faster still
    k += [(77.63, route.U_HOP), (77.655, 0.0)]
    if not stray:
        k += [(77.75, RT.U_H), (77.85, RT.U_O), (77.92, RT.U_T), (78.0, RT.U_END)]
    else:
        k += [(T_OFF, RT.U_H - RT.FLIGHT)]          # the end of the first chute: it flies off here
    return k


T_OFF, T_HIT = FALL.T_OFF, FALL.T_HIT


# ------------------------------------------------------------------------------------------------ build


def build():
    sc = kit.new_scene('backprop')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable', 'books', 'clip', 'mug'})
    d.lamp.aim(None, W((2, -6, 12)))
    coll = kit.collection('run')
    H = RUN.build(coll, BOARD)

    # ---------------------------------------------------------------- marbles
    mcoll = kit.collection('marbles')
    specs = [('orange', '#E0703E', (0, 0, 0), 1.0, -1.0), ('teal', '#1F9C94', (0, 1, 2), -1.0, 1.0),
             ('gold', '#F0C040', (0, 2, 3), 1.0, 1.0)]
    marbles = []
    for name, col, (_, i0, h), spin, roll in specs:
        route = RUN.Route(i0, h, {0: 0, 2: 1, 3: 2}[h], spin_dir=spin, roll_dir=roll)
        mb = RUN.build_marble(mcoll, name, col)
        stray = name == 'gold'
        keys = marble_keys(route, stray)
        umap = RUN.umap(keys)
        marbles.append((mb, route, keys, umap, stray))

    for mb, route, keys, umap, stray in marbles:
        t_last = T_OFF if stray else TEND
        per_frame(mb, 'location', lambda t, r=route, f=umap: W(r.pos(f(t))), T0 - 0.1, t_last)
        per_frame(mb, 'rotation_euler', lambda t, r=route, f=umap: r.spin(f(t)), T0 - 0.1, t_last, index=1)
    stray = [m for m in marbles if m[4]][0]

    # ---------------------------------------------------------------- the computer, its fall and the shatter
    C = FALL.sequence(kit.collection('vn'), stray, W, T0, TEND)

    # ---------------------------------------------------------------- rockers and bulbs follow the marbles
    TILT = RUN.TILT
    used = set()
    for mb, route, keys, umap, stray in marbles:
        for k in (0, 1):
            nd = route.nodes[k]
            nxt = route.nodes[k + 1]
            rk = H['rockers'].get(nd)
            if rk is None:
                continue
            used.add(nd)
            s0 = 1.0 if RUN.node(*nxt).x > RUN.node(*nd).x else -1.0
            ur = route.rocker_u(k)

            def ang(t, f=umap, ur=ur, s0=s0):
                x = (f(t) - ur) / 0.05
                if x <= 0:
                    return s0 * TILT
                if x >= 1:
                    g = 1.0 + 0.18 * math.exp(-(x - 1) * 1.2) * math.cos((x - 1) * 5.0)
                else:
                    g = x * x * (3 - 2 * x)
                return s0 * TILT * (1 - 2 * g)
            per_frame(rk, 'rotation_euler', ang, T0 - 0.1, TEND, index=1)
    for nd, rk in H['rockers'].items():
        if nd not in used:
            rk.rotation_euler[1] = TILT * (1 if nd[1] % 2 else -1)

    # bulbs: a flash each time a marble enters the cup; warm forward, cool on the rewind
    WARM, COOL = kit.srgb('#FFB24A'), kit.srgb('#7FD6FF')
    flashes = {}
    for mb, route, keys, umap, stray in marbles:
        for k in range(3):
            for tc, dr in RUN.crossings(keys, route.node_u(k) + 1e-4):
                flashes.setdefault(route.nodes[k], []).append((tc, dr))
    for nd, (bulb, bm_, lt) in H['bulbs'].items():
        ev = sorted(flashes.get(nd, []))
        b = bm_.node_tree.nodes['Principled BSDF']

        def level(t, ev=ev):
            v, c = 0.0, WARM
            for tc, dr in ev:
                if t >= tc - 0.02:
                    x = t - tc
                    e = (x + 0.02) / 0.02 if x < 0 else math.exp(-x / 0.22)
                    if e > v * 0.5:
                        c = WARM if dr > 0 else COOL
                    v = max(v, e)
            return v, c

        per_frame(b.inputs['Emission Strength'], 'default_value', lambda t, f=level: 16.0 * f(t)[0] + 0.15,
                  T0 - 0.1, TEND)
        per_frame(b.inputs['Emission Color'], 'default_value', lambda t, f=level: f(t)[1], T0 - 0.1, TEND)
        per_frame(lt.data, 'energy', lambda t, f=level: 180.0 * f(t)[0], T0 - 0.1, TEND)
        per_frame(lt.data, 'color', lambda t, f=level: tuple(f(t)[1][:3]), T0 - 0.1, TEND)

    # ---------------------------------------------------------------- light: the desk lamp is behind the board, so a
    # warm key from the front-left (off screen, like a second desk lamp) and a cool low fill from the right
    lc = kit.collection('bp.lights')
    key = kit.spot('bp.key', tuple(W((-34, -62, 58))), tuple(W((4, -3, 14))), power=240000.0, angle_deg=46,
                   blend=0.55, radius=4.0, color='#FFD2A0', coll=lc)
    fill = kit.area('bp.fill', tuple(W((48, -58, 10))), tuple(W((0, -3, 14))), power=40000.0, size=30.0,
                    color='#9EC4FF', coll=lc)
    fill.data.specular_factor = 0.15
    key2 = kit.spot('bp.key.crash', (58.0, -62.0, 48.0), (35.0, -24.0, 2.0), power=160000.0, angle_deg=38,
                    blend=0.6, radius=3.0, color='#FFD9B0', coll=lc)

    # ---------------------------------------------------------------- cameras
    cams = []
    c1, t1 = kit.camera('cam.b1', lens=38, loc=(-20, -94, 21), target=tuple(W((8, -2, 15))), fstop=8)
    kit.key(c1, 'location', CUTS[0])
    kit.key(c1, 'location', CUTS[1], (-15.0, -79, 19.5))
    cams.append(c1)
    c2, t2 = kit.camera('cam.b2', lens=40, loc=tuple(W((20, -40, 10))), target=tuple(W((2, -3, 14))), fstop=8)
    kit.key(c2, 'location', CUTS[1])
    kit.key(c2, 'location', CUTS[2], tuple(W((-4, -38, 11.5))))
    kit.key(t2, 'location', CUTS[1])
    kit.key(t2, 'location', CUTS[2], tuple(W((-6, -3, 15))))
    cams.append(c2)
    # B3: the right end of the run and the shelf: the stray flies off and hits the computer
    c3, t3 = kit.camera('cam.b3', lens=40, loc=(24.0, -54.0, 21.0), target=(19.0, -6.0, 16.5), fstop=8)
    kit.key(c3, 'location', CUTS[2])
    kit.key(c3, 'location', CUTS[3], (25.5, -49.0, 20.0))
    cams.append(c3)
    # B4: close on the computer teetering on the shelf edge
    c4, t4 = kit.camera('cam.b4', lens=50, loc=(12.0, -33.0, 11.0), target=(29.0, -9.5, 17.0), fstop=8)
    kit.key(c4, 'location', CUTS[3])
    kit.key(c4, 'location', CUTS[4], (13.5, -31.0, 11.2))
    cams.append(c4)
    # B5: desk level: it tips, falls and shatters
    c5, t5 = kit.camera('cam.b5', lens=32, loc=(52.0, -55.0, 9.0), target=(29.0, -13.0, 9.0), fstop=8)
    kit.key(c5, 'location', CUTS[4])
    kit.key(c5, 'location', CUTS[5], (50.0, -52.0, 7.5))
    cams.append(c5)
    # B6: the aftermath: down on the plaque, then tracking right with the dying tube to the domino
    P6 = C['plaque_rest']
    tube_at = C['tube_at']
    c6, t6 = kit.camera('cam.b6', lens=50, loc=tuple(P6 + Vector((-1.5, -13.0, 9.0))), target=tuple(P6), fstop=11)
    # it opens on the plaque with the dying tube rolling past behind it, and picks the tube up from 80.35 (the
    # plaque alone held for 1.1 s with nothing happening)
    for tk, loc, tgt in ((CUTS[5], P6 + Vector((-1.5, -13.0, 9.0)), P6 + Vector((0.8, 0.7, 0.0))),
                         (80.35, P6 + Vector((0.5, -12.5, 8.4)), P6 + Vector((1.8, 1.0, 0.0))),
                         (81.55, tube_at(81.55) + Vector((-1.5, -14.5, 7.0)), tube_at(81.55)),
                         (TEND, C['domino'] + Vector((-4.5, -19.5, 7.5)), C['domino'] + Vector((-0.8, 0, 1.8)))):
        kit.key(c6, 'location', tk, tuple(loc))
        kit.key(t6, 'location', tk, tuple(tgt))
    cams.append(c6)
    for cam, t in zip(cams, CUTS):
        kit.cut_to(cam, t)
    sc.camera = c1
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.22)
    FALL.bake_burst(C, TEND)
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(C, c6)
    sc.frame_set(sc.frame_start)


def lyrics(C, cam6):
    """M-L-P light up in the default row as the marbles hit the input, hidden and output layers; OBSOLETE is
    rubber-stamped in red across the fallen VON NEUMANN plaque on "obsolete"; everything else on the lyric stand."""
    ly.accent(23, 'MLP', 'glow')
    P = Vector(C['plaque_rest'])
    bpy.context.scene.frame_set(int(80.3 * FPS))
    to_cam = cam6.matrix_world.translation - P
    to_cam.z = 0.0
    a = math.radians(14.0)                              # a slightly skewed stamp
    fr = Matrix.Rotation(a, 3, 'Z') @ to_cam.normalized()
    ly.line(24, words='obsolete', style='stamp', support='none', flat=True,
            place=ly.At(tuple(P + Vector((0.2, 0.0, 0.1))), flat=True, face=tuple(fr), size=0.85),
            t_end=TEND)
    # "Sharp left": the aftermath camera pans fast from the plaque to the domino, so each word stands on the desk
    # where the camera looks when it is sung (painted blocks among the shards)
    for w, spot, t_look, t_ex in (('Sharp', (38.0, -30.0, 0.0), 81.3, 81.72), ('left', (41.0, -29.3, 0.0), 81.9, None)):
        bpy.context.scene.frame_set(int(t_look * FPS))
        fr = cam6.matrix_world.translation - Vector(spot)
        fr.z = 0.0
        ly.line(25, words=w, place=ly.At(spot, size=0.9, face=tuple(fr.normalized())), t_exit=t_ex,
                t_end=TEND if t_ex is None else t_ex + 0.5)
    ly.default('backprop')
