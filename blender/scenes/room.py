"""room · 27.509-38.418 · "Trapped in the Chinese room, with a bag of shrooms / See through the shoggoth's lies, with
your shinigami eyes", then the instrumental break.

The researcher posts a question in Chinese through the mail slot of a cardboard box; inside, Clawd looks it up in a
rulebook and stamps a perfect answer without understanding a word. His stamp knocks over a paper bag of mushrooms that
grow, glowing, across the floor and out over the desk while the light goes psychedelic. He holds a smiley mask up to
his face as the shoggoth (orange vinyl tentacles covered in blinking eyes) rises behind the box and stares at us. Revision 2:
the shinigami eyes are Clawd's ("with YOUR shinigami eyes", sung to the AI): he lowers the mask, his eyes flare red and
he stares through the wall at the researcher, over whose head a Death Note name and a lifespan counter float, ticking
down. The tentacles slip back behind the box, the lamp flickers, and one eye peeks out of the mail slot.

Shots (song s; cuts on beats / words)                                                              hit
 1 post     27.509-27.940  EXT, slot on the box's left wall, 50 mm, slow push. The researcher leans in and pushes a
                           note (你懂中文吗？ "do you understand Chinese?") through the slot; the brass flap swings in.  note gone on "room" 27.94
 2 stamp    27.940-29.327  INT through the knife-cut window, 50 mm, drift left (cut on "with"; the note sails in
                           and lands on the floor). Clawd squints at the rulebook,
                           raises the rubber stamp and slams it on the answer card (当然懂！ "of course I understand!"):
                           a red 懂 seal. The thump tips the paper bag over; he beams (^^) and flicks the card into
                           the slot.                                                               STAMP 28.873 (beat); bag lands 29.12
 3 shrooms  29.327-29.907  INT at floor level, 22 mm, creeping back. Glowing mushrooms sprout in a wave from the
                           bag's mouth across the floor toward the lens; hues cycle; Clawd's eyes go dizzy.   growth from "shrooms" 29.124
 4 mask     29.907-31.145  Front wide, 38 mm; tilts up and pulls back as the shoggoth rises. Clawd lifts a smiley
                           mask on a stick to his face (his real eyes narrow above it); the mushrooms spill out of
                           the window; tentacles and an eyed mass rise behind the box.             mask on "See" 29.907; rise on "shoggoth's" 30.576
 5 lies     31.145-32.963  Low angle from the desk, 26 mm, slow push and crane. The shoggoth towers over the box,
                           swaying; every eye pops open on "lies" and at 32.054 they all swivel to the lens.  eyes open 31.145; stare 32.054
 6 look     32.963-33.738  The shoggoth's POV down onto the researcher, 80 mm, push in. He looks up at it, scared,
                           claps his hands to his mouth; a glint runs across his glasses.
 6b glare   33.738-34.782  INT through the window, 50 mm, close on Clawd: the mask comes down, on "shinigami" his
                           eyes flare red (shinigami eyes) and he turns to stare through the wall at the researcher. red eyes 33.738
 7a name    34.782-35.691  Medium on the researcher at the slot from the front right, 45 mm: over his head float a
                           red name and a lifespan counter ticking down (what Clawd sees); he feels watched, sweats.
 7b retreat 35.691-36.600  Wide three-quarter, 35 mm. Eyes shut, the tentacles slip back behind the box, the mass
                           sinks; Clawd's red eyes go out; the researcher backs off.               retreat from 35.55
 8 peek     36.600-38.418  Close on the mail slot, 55 mm, slow push. The lamp flickers; then stillness; the brass
                           flap lifts and one eye peeks out, looks left, right, at us, blinks.     flicker 36.75-37.45; peek 37.62
"""
from __future__ import annotations

import colorsys
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom import timing as tm
from pdoom.chars import geo as cg
from pdoom.sets import build_desk, geo, phys_fstop

from . import room_box as RB
from . import room_shoggoth as SH
from . import room_shrooms as SR
from .room_nodes import input_id

FPS = tm.FPS
T0, T1 = 27.509, 38.418
BEATS = tm.beats_between(27.0, 39.0)

# word hits
W_ROOM = tm.word('Chinese room', 'room')['start']            # 27.52
W_BAG = tm.word('bag of shrooms', 'bag')['start']             # 28.38
W_SHROOMS = tm.word('bag of shrooms', 'shrooms')['start']     # 29.124
W_SEE = tm.word("shoggoth's lies", 'See')['start']            # 29.907
W_SHOG = tm.word("shoggoth's lies", "shoggoth's")['start']    # 30.576
W_LIES = tm.word("shoggoth's lies", 'lies')['start']          # 31.14
W_SHINI = tm.word('shinigami eyes', 'shinigami')['start']     # 33.738
W_EYES = tm.word('shinigami eyes', 'eyes')['start']           # 34.73

STAMP = 28.873             # the beat the stamp lands on
STARE = 32.054             # all eyes to the lens
RETREAT = 35.55            # (revision 2: was 34.95; the retreat now plays in its own wide shot)
W_WITH = tm.word('bag of shrooms', 'with')['start']            # 27.94
T_NAME, T_RET = 34.782, 35.691                                   # revision 2 cuts: the name shot, the retreat wide
EYE_RED = '#FF2A1E'
FLICK0, FLICK1 = 36.75, 37.45
PEEK = 37.62

RES_SPOT = Vector((-16.7, -9.5, 0.0))          # researcher at the slot, facing +x (0.8 back: his face cleared the wall)
RES_BACK = Vector((-22.0, -17.0, 0.0))         # where he backs off to
MASK_POSE = (40, 70, 0)
STAMP_POSE = (35, 40, 0)                       # hit pose (the stamp face on the card)
T_PUTDOWN = 29.40                              # the stamp is set down on the matchbox


def NOTE_X(t):
    """How far (cm, +x = into the box) the posted note's centre is past the slot while his hand pushes it."""
    return lerp(0.8, 1.6, smooth(t, 27.2, 27.8))


def smooth(t, a, b):
    return tm.smooth(t, a, b)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------------------------ keying helpers


def twos(ob, path, fn, t0, t1, index=-1, steps=()):
    """Key fn on twos (24 fps) or on every output frame, LINEAR (smooth 60 fps build): room_shoggoth.key_twos."""
    SH.key_twos(ob, path, fn, t0, t1, index=index, steps=steps)


def twos_vec(ob, path, fn, t0, t1, n=3, steps=()):
    for i in range(n):
        twos(ob, path, lambda t, i=i: fn(t)[i], t0, t1, index=i, steps=steps)


def every_frame(owner, prop, fn, t0, t1, *, index=-1, interp='LINEAR'):
    f0, f1 = int(math.floor(t0 * FPS)) - 1, int(math.ceil(t1 * FPS)) + 1
    for f in range(f0, f1 + 1):
        v = fn(f / FPS)
        if index >= 0:
            getattr(owner, prop)[index] = v
        else:
            setattr(owner, prop, v)
        owner.keyframe_insert(prop, frame=f, index=index)
    idb = owner.id_data
    try:
        full = owner.path_from_id(prop)
    except Exception:
        full = prop
    for fc in kit.fcurves(idb):
        if fc.data_path == full and (index < 0 or fc.array_index == index):
            for kp in fc.keyframe_points:
                kp.interpolation = interp


def hsv(h, s=0.85, v=1.0):
    return colorsys.hsv_to_rgb(h % 1.0, s, v)


# ------------------------------------------------------------------------------------------------ the mood


def psy(t):
    """0..1: how psychedelic the light is (mushrooms awake)."""
    return smooth(t, W_SHROOMS + 0.05, W_SHROOMS + 0.7) * (1 - 0.72 * smooth(t, RETREAT + 0.3, RETREAT + 1.6))


def hue_shift(t):
    return 0.16 * max(0.0, t - W_SHROOMS)


def beat_pulse(t):
    return tm.pulse(t, BEATS, half_life=0.11)


# ------------------------------------------------------------------------------------------------ build


def build():
    sc = kit.new_scene('room')
    sc.eevee.shadow_pool_size = '1024'     # many small lights at cm scale overflow the default 512 MB pool
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable', 'clip', 'notes', 'pen', 'mug'})
    # the desk lamp's head goes up and back, above the tentacles' arcs (tentacle 3 used to run through its shade);
    # it still aims at its usual pool
    d.lamp.aim(None, (6.0, -4.0, 0.0), reach=28.0, height=52.0)
    cs = kit.collection('set')
    b = RB.build_box(cs)
    RB.build_slot(cs, b)
    RB.build_bulb(cs, b)
    RB.build_book(cs, b)
    RB.build_table(cs, b)
    RB.build_bag(cs, b)
    look = kit.empty('shog.look', (0, -60, 10), kit.collection('fx'))

    c = chars.Clawd(kit.collection('clawd'), loc=tuple(RB.CLAWD), yaw=0)
    r = chars.Researcher(kit.collection('researcher'), loc=tuple(RES_SPOT), yaw=90)
    mask = RB.mask_on_stick(kit.collection('clawd'), c, MASK_POSE, side='L')

    cams = shots(d, b)
    act_clawd(c, b, mask)
    hit = stamp(c, b)
    notes_and_cards(b, cs, hit)
    act_researcher(r, cams)
    focus_pull(cams['glint'], lambda t: r.anchor(t, 'eyes'))      # the lenses, not the head's centre
    bag_tip(b)
    shrooms = grow_shrooms(b, cs)
    shoggoth(b, look)
    look_follow(look, cams)
    peek(b)
    lights(d, b, shrooms)
    kit.post(bloom=0.35, bloom_threshold=1.0, vignette=0.24)
    chars.finish()
    death_note(r, cams)
    from pdoom import lyrics as ly
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(d, b, c, r, cams)


def lyrics(d, b, c, r, cams):
    """Revision 2: every sung word in the picture (docs/lib/lyrics.md).

    1 post      "Trapped in the Chinese room" on the lyric stand ("room" 27.52)
    2 stamp     "with a bag of" on a stand inside the box; SHROOMS is a neon sign on the box's back wall behind
                Clawd, dark until "shrooms" (29.124), then cycling through the mushrooms' colours (and in shot 3)
    4-5         "See through the shoggoth's lies" sign-written in gold leaf on a glass pane set in the box's window:
                we see through it to Clawd's smiley mask and the shoggoth rising behind
    6-8         "with your shinigami eyes" in red light-up blocks on the stand, lit in Clawd's shinigami red
    """
    from pdoom import lyrics as ly
    from pdoom.lyrics import mats as LM
    # 2: with a bag of ... (the stand in the stamp shot only: shot 3 has the neon)
    ly.line(9, words=(0, 4), place='auto', t_end=29.327, spec=ly.StageSpec(cells=14.0, rows=1))
    # 2-3: SHROOMS, a neon sign on the back wall
    ly.line(9, words='shrooms', style='neon', place=ly.At((8.6, RB.Y1 - RB.T - 0.12, 4.3), face=(0, -1, 0), size=2.0),
            t_show=W_WITH, t_exit=29.8, t_end=29.907, color='#FF4FD0', strength=6.0)
    neon = bpy.data.materials.get('ly.neon.FF4FD0.6')
    if neon is not None:
        bsdf = neon.node_tree.nodes.get('Principled BSDF')
        for sock in ('Base Color', 'Emission Color'):
            for i in range(3):
                every_frame(bsdf.inputs[sock], 'default_value', lambda t, i=i: hsv(0.86 + hue_shift(t) * 1.3, 0.8)[i],
                            W_WITH - 0.1, 29.95, index=i)
    # 4-5: gold leaf on a pane of glass in the window (top of the opening, above Clawd's head)
    ly.line(10, style='goldleaf', place=ly.At((1.5, RB.Y0 - 0.35, 7.7), face=(0, -1, 0), size=1.45), max_chars=16,
            t_show=29.85, t_end=33.2)
    # 6-8: the shinigami red
    ly.line(11, style='glow', glow_color=EYE_RED, light=0, place='auto')
    ly.default('room')


def death_note(r, cams):
    """What Clawd's shinigami eyes see (revision 2): a red name and a lifespan counter floating over the researcher's
    head, the counter ticking down on twos. Red emission stays at 2 (AgX turns stronger reds pink)."""
    import os
    from pdoom import lyrics as ly
    coll = kit.collection('deathnote')
    font_p = os.path.join(os.path.dirname(ly.__file__), 'fonts', 'CourierPrime-Bold.ttf')
    font = bpy.data.fonts.load(font_p, check_existing=True) if os.path.exists(font_p) else None
    red = kit.emission_mat('room.deathnote', EYE_RED, 2.0)
    t0, t1 = T_NAME, 36.62
    root = kit.empty('deathnote.root', (0, 0, 0), coll)
    cam_p = cams['name'].at(35.2)

    def text(name, body, size, z):
        cd = bpy.data.curves.new(name, 'FONT')
        cd.body = body
        if font is not None:
            cd.font = font
        cd.size = size
        cd.align_x = 'CENTER'
        cd.align_y = 'BOTTOM'
        cd.space_character = 1.05
        o = bpy.data.objects.new(name, cd)
        coll.objects.link(o)
        cd.materials.append(red)
        o.parent = root
        o.location = (0.0, 0.0, z)
        o.rotation_euler = (math.radians(90.0), 0.0, 0.0)          # stands up, reads toward -Y (the root turns it)
        o.visible_shadow = False
        return o
    nm = text('deathnote.name', 'RESEARCHER', 0.72, 0.62)
    kit.visible(nm, t0 - 0.5 / FPS, t1)
    # the lifespan: an eight-digit count dropping by a few ten-thousand a pose
    n = 64781025
    t = t0
    k = 0
    while t < t1:
        o = text(f'deathnote.life{k:02d}', f'{n:,}'.replace(',', ' '), 0.5, 0.0)
        a = t - 0.5 / FPS if k else t0 - 0.5 / FPS
        kit.visible(o, a, t + 2.0 / FPS - 0.5 / FPS)
        n -= int(26000 + 71000 * geo.hash01('life', k))
        t += 2.0 / FPS
        k += 1

    # it floats 2.6 cm over his head, facing the name camera, and follows him (on twos, like the puppet)
    def pos(t):
        return r.anchor(t, 'head') + Vector((0.0, 0.0, 2.7))
    twos_vec(root, 'location', pos, t0 - 0.2, t1 + 0.1)
    dv = cam_p - pos(35.2)
    root.rotation_euler = (0.0, 0.0, math.atan2(dv.x, -dv.y))


# ------------------------------------------------------------------------------------------------ cameras


class Cam:
    def __init__(self, name, t0, t1, loc_fn, tgt_fn, lens, fstop):
        self.name, self.t0, self.t1 = name, t0, t1
        self.loc_fn, self.tgt_fn = loc_fn, tgt_fn
        self.cam, self.tgt = kit.camera('cam.' + name, lens=lens, loc=tuple(loc_fn(t0)), target=tuple(tgt_fn(t0)),
                                        fstop=fstop, coll=kit.collection('cams'))
        self.cam.data.dof.aperture_fstop = phys_fstop(fstop)
        self.cam.data.dof.aperture_blades = 7
        every_frame(self.cam, 'location', lambda t: self.loc_fn(t)[0], t0 - 0.1, t1 + 0.1, index=0)
        every_frame(self.cam, 'location', lambda t: self.loc_fn(t)[1], t0 - 0.1, t1 + 0.1, index=1)
        every_frame(self.cam, 'location', lambda t: self.loc_fn(t)[2], t0 - 0.1, t1 + 0.1, index=2)
        for i in range(3):
            every_frame(self.tgt, 'location', lambda t, i=i: self.tgt_fn(t)[i], t0 - 0.1, t1 + 0.1, index=i)
        kit.cut_to(self.cam, t0)

    def at(self, t):
        return Vector(self.loc_fn(t))


def path(a, b_, t0, t1, ease=True):
    a, b_ = Vector(a), Vector(b_)
    return lambda t: a.lerp(b_, smooth(t, t0, t1) if ease else min(1, max(0, (t - t0) / (t1 - t0))))


def shots(d, b):
    cams = {}
    slot = RB.SLOT_C
    # 1 post: push toward the slot and his hand
    cams['post'] = Cam('post', 27.509, W_WITH, path((-36.0, -46.0, 12.0), (-25.5, -31.0, 7.6), 27.45, 28.3),
                       path((-11.0, -12.0, 5.2), (-12.7, -10.4, 4.1), 27.45, 28.3), 40, 8)
    # 2 stamp: through the window, drifting left as he stamps (revision 2: from "with", so the note lands inside)
    cams['stamp'] = Cam('stamp', W_WITH, 29.327, path((6.2, -41.2, 8.5), (5.0, -40.0, 7.8), 27.9, 29.5, False),
                        path((0.1, -7.7, 3.5), (0.8, -7.2, 3.0), 27.9, 29.5), 38, 11)
    # 3 shrooms: floor level inside the box, creeping back as the wave comes on
    cams['shrooms'] = Cam('shrooms', 29.327, 29.907, path((8.4, -17.0, 1.8), (8.9, -18.8, 2.1), 29.2, 30.0, False),
                          path((4.6, -10.5, 2.7), (4.2, -10.0, 3.1), 29.2, 30.0), 22, 11)   # (rev. 2: tilted up a touch)
    # 4 mask + rise: front, tilting up and pulling back as the shoggoth rises
    def loc4(t):
        u = smooth(t, 30.15, 31.4)
        return Vector((2.5, -57.0, 13.0)).lerp(Vector((3.5, -64.0, 17.0)), u)

    def tgt4(t):
        u = smooth(t, 30.15, 31.4)
        return Vector((2.0, -8.0, 9.0)).lerp(Vector((4.0, -3.0, 18.5)), u)
    cams['mask'] = Cam('mask', 29.907, 31.145, loc4, tgt4, 38, 11)
    focus_pull(cams['mask'], lambda t: (RB.CLAWD + Vector((0, -3, 5))).lerp(Vector((7, 8, 24)), smooth(t, 30.45, 30.95)))
    # 5 lies: low on the desk, looking up at the towering mass; slow push + crane
    cams['lies'] = Cam('lies', 31.145, 32.963, path((26, -58, 3.0), (21, -49, 5.5), 31.0, 33.1, False),
                       path((5, 3, 22), (5, 3, 24), 31.0, 33.1), 26, 11)
    # 6 glint: the shoggoth's POV down onto the researcher's face, pushing in
    face = RES_SPOT + Vector((0, 0, 9.9))
    pov0 = face + Vector((-3.0, -13.0, 11.5))
    cams['glint'] = Cam('glint', 32.963, W_SHINI, path(pov0, face + (pov0 - face) * 0.8, 32.9, 34.9, False),
                        path(face + Vector((0, 0, -0.9)), face + Vector((0, 0, -0.3)), 32.9, 34.9), 80, 8)
    # 6b glare: INT through the window, close on Clawd: the shinigami eyes (revision 2)
    cf = RB.CLAWD + Vector((0.0, -2.2, 5.0))
    cams['glare'] = Cam('glare', W_SHINI, T_NAME, path(cf + Vector((3.2, -24.0, 1.8)), cf + Vector((2.2, -20.5, 1.2)),
                                                       33.7, 34.85, False),
                        path(cf + Vector((-0.2, 0.0, 0.3)), cf + Vector((-0.8, 0.0, 0.1)), 33.7, 34.85), 50, 11)
    # 7a name: medium on the researcher at the slot, from the front right (revision 2)
    hd = RES_SPOT + Vector((0.0, 0.0, 11.4))
    cams['name'] = Cam('name', T_NAME, T_RET, path(hd + Vector((-2.4, -24.5, -2.2)), hd + Vector((-2.1, -22.5, -2.3)),
                                                   34.7, 35.8, False),
                       path(hd + Vector((0.4, 0.0, -1.3)), hd + Vector((0.35, 0.0, -1.35)), 34.7, 35.8), 45, 8)
    # 7b retreat: wide three-quarter
    cams['retreat'] = Cam('retreat', T_RET, 36.6, path((-49, -64.5, 35), (-47, -61, 33), 35.6, 36.7, False),
                          path((0.6, -6, 10.4), (0, -6, 9), 35.6, 36.7), 35, 8)
    # 8 peek: on the slot from the back-left, slow push
    cams['peek'] = Cam('peek', 36.6, 38.418, path((-33.0, -2.2, 5.6), (-25.0, -5.2, 4.3), 36.5, 38.5),
                       path(slot + Vector((-0.6, 0, 0.5)), slot + Vector((-1.3, 0, 0.12)), 36.5, 38.5), 58, 8)
    # a thump on the stamp and a rumble as it rises
    shake(cams['stamp'].cam, STAMP, STAMP + 0.22, amp=0.035, freq=10, seed=3)
    shake(cams['mask'].cam, 30.3, 31.15, amp=0.04, freq=7, seed=5)
    shake(cams['lies'].cam, 31.15, 31.45, amp=0.03, freq=7, seed=6)
    bpy.context.scene.camera = cams['post'].cam
    return cams


def shake(obj, t0, t1, amp=0.1, freq=12.0, seed=1):
    """Noise on an object's existing location F-curves over [t0, t1] (no new keys)."""
    for fc in kit.fcurves(obj):
        if fc.data_path != 'location':
            continue
        n = fc.modifiers.new('NOISE')
        n.scale, n.strength, n.phase = FPS / freq, amp * 2, seed * 7.3 + fc.array_index * 3.1
        n.use_restricted_range = True
        n.frame_start, n.frame_end = t0 * FPS, t1 * FPS
        n.blend_in = n.blend_out = min(3.0, (t1 - t0) * FPS / 4)


def focus_pull(cm, point_fn):
    """Drive a camera's focus distance from a world point over its shot (instead of its target Empty)."""
    dof = cm.cam.data.dof
    dof.focus_object = None
    every_frame(dof, 'focus_distance', lambda t: (Vector(point_fn(t)) - cm.at(t)).length, cm.t0, cm.t1)


def look_follow(look, cams):
    """The shoggoth's eyes look at this Empty: it rides with whichever camera is live (on twos)."""
    order = sorted(cams.values(), key=lambda c: c.t0)

    def at(t):
        cur = order[0]
        for cm in order:
            if t >= cm.t0:
                cur = cm
        return cur.at(t)
    twos_vec(look, 'location', at, T0 - 0.2, T1 + 0.2, steps=[tm.t2f(cm.t0) for cm in order[1:]])


# ------------------------------------------------------------------------------------------------ notes, cards, stamp


def notes_and_cards(b, cs, hit):
    slot = RB.SLOT_C
    # the question: posted through the slot (27.3-27.94), sails over the matchbox (clear of the ink pad and the hanging
    # stamp), and drops onto the floor beyond it
    q = RB.note(cs, 'note.q', RB.QUESTION)
    land = Vector((-9.3, -3.7, RB.FLOOR + 0.02))

    def qpos(t):
        if t < 27.8:
            return slot + Vector((NOTE_X(t), 0.0, -0.05))
        if t < 27.94:
            return slot + Vector((lerp(1.6, 2.5, (t - 27.8) / 0.14), 0.0, -0.05))
        u = min(1.0, (t - 27.94) / 0.26)
        p = (slot + Vector((2.5, 0.0, -0.05))).lerp(land, u)
        z0 = slot.z - 0.05
        if u < 0.78:                       # floats level over the matchbox, a little lift
            p.z = z0 + 0.3 * math.sin(math.pi * u / 0.78)
        else:                              # then drops off its far edge
            p.z = lerp(z0, land.z, ((u - 0.78) / 0.22) ** 2)
        return p
    twos_vec(q, 'location', qpos, 27.0, 28.4)
    twos(q, 'rotation_euler', lambda t: math.radians(-25) * smooth(t, 27.94, 28.18), 27.0, 28.4, index=2)
    # the answer card: on the matchbox under the stamp; stamped (seal appears) on STAMP; flicked out 29.05-29.3
    # (sized and placed to clear the ink pad and Clawd's side, even squashed by the slam; the seal lands where the
    # stamp's face does)
    a = RB.note(cs, 'note.a', RB.ANSWER, size=0.56, w=2.8, d=1.8)
    a_home = Vector((hit.x - 0.4, hit.y - 0.3, RB.FLOOR + b.table_top + 0.03))
    seal = RB.seal(cs, 'note.a.seal')
    rz = math.radians(-8)                           # the card's rotation at the slam (below)
    dx_, dy_ = hit.x - a_home.x, hit.y - a_home.y
    geo.attach(seal, a, (dx_ * math.cos(rz) + dy_ * math.sin(rz), -dx_ * math.sin(rz) + dy_ * math.cos(rz), 0.02))
    for o in [seal] + list(seal.children):
        kit.visible(o, STAMP, None)
    out = slot + Vector((-3.0, 0.0, -0.1))
    floor = Vector((-13.8, -6.4, 0.02))               # (on the desk, clear of the box wall)

    def apos(t):
        if t < 29.05:
            return a_home
        if t < 29.3:
            u = smooth(t, 29.05, 29.3)
            p = a_home.lerp(slot + Vector((0.6, 0, -0.1)), u)
            p.z += 0.6 * math.sin(math.pi * u)          # skims up over the ink pad to the slot
            return p
        if t < 29.45:
            return (slot + Vector((0.6, 0, -0.1))).lerp(out, (t - 29.3) / 0.15)
        u = min(1.0, (t - 29.45) / 0.18)
        return out.lerp(floor, u)
    twos_vec(a, 'location', apos, 27.4, 29.8)
    twos(a, 'rotation_euler', lambda t: math.radians(-8) + math.radians(20) * smooth(t, 29.05, 29.3), 27.4, 29.8,
         index=2)
    twos(a, 'rotation_euler', lambda t: math.radians(-70) * (smooth(t, 29.45, 29.55) - smooth(t, 29.55, 29.66)),
         27.4, 29.8, index=1)
    b.card_q, b.card_a = q, a


# ------------------------------------------------------------------------------------------------ Clawd


def stamp(c, b):
    """The rubber stamp: hangs upright from his right mitten; its rubber face meets the answer card at the lowest point
    of the slam (squash included), so it never sinks into the matchbox. After the flick he sets it down where it hit
    (T_PUTDOWN) and a resting copy takes over, so it isn't in his swinging hand while he dances or turns. Returns the
    world point of the face at the hit (the card goes under it)."""
    st, off = RB.stamp_in_hand(kit.collection('clawd'), c, side='R')
    top = RB.FLOOR + b.table_top
    ts = [STAMP - 0.04 + 0.005 * k for k in range(23)]
    lows = [(c.anchor(t, 'hand.R'), t) for t in ts]
    h_hit, _ = min(lows, key=lambda q: q[0].z)
    off_z = top + 0.06 - h_hit.z                     # on the card (centre 0.03 up, 0.03 thick) + a hair
    for v in st.data.vertices:
        v.co.z += off_z - off.z
    off = Vector((off.x, off.y, off_z))
    # put down: the raise that sets the face on the table at T_PUTDOWN (the body as keyed then)
    lo, hi = 0.0, 60.0
    for _ in range(30):
        r_ = (lo + hi) / 2
        if RB.clawd_hand(c, T_PUTDOWN, (r_, 40, 0)).z + off_z > top + 0.02:
            hi = r_
        else:
            lo = r_
    put = ((lo + hi) / 2, 40, 0)
    c.arms(T_PUTDOWN - 0.03, put, side='R', dur=0.15)
    h_put = RB.clawd_hand(c, T_PUTDOWN, put)
    rest = st.copy()
    kit.collection('clawd').objects.link(rest)
    rest.name = 'stamp.rest'
    rest.constraints.clear()
    rest.matrix_world = Matrix.Translation(h_put)
    kit.visible(st, None, T_PUTDOWN)
    kit.visible(rest, T_PUTDOWN, None)
    print(f'[room] stamp: face {off_z:.2f} below the hand, hit at {tuple(round(x, 2) for x in h_hit + off)}, '
          f'put down at raise {put[0]:.1f}')
    return h_hit + off


def act_clawd(c, b, mask):
    book = RB.BOOK + Vector((0, 0, 1.4))
    card = RB.CLAWD + Vector((-5.2, -1.2, 2.0))
    c.eyes(27.3, 'narrow')
    c.look(27.4, book, turn=0.0)
    c.look(28.25, card, turn=0.0, dur=0.2)
    # stamp: wind up, SLAM on the beat, hold, lift
    # (the stamp hangs upright from his mitten: every pose that holds it keeps the rubber face above the matchbox)
    c.arms(27.3, (42, 30, 0), side='R')
    c.arms(28.62, (78, 34, 0), side='R', dur=0.2)
    c.arms(STAMP, STAMP_POSE, side='R', dur=0.08, ease='in')
    c.squash(STAMP, 0.2)
    c.arms(29.1, (48, 38, 0), side='R', dur=0.16)
    c.eyes(STAMP + 0.02, 'happy')
    c.hop(29.02, 0.6)
    # flicks the card toward the slot with a shimmy of pride, then the mushrooms get to him
    c.arms(29.22, (40, 62, 0), side='R', dur=0.12)
    # (and puts the stamp down on the matchbox at T_PUTDOWN: stamp())
    c.look(29.2, RB.SLOT_C, turn=0.0)
    c.eyes(29.45, 'dizzy')
    c.look(29.45, None)
    c.dance(29.4, 29.95, 'sway', amount=0.9)
    # See: the mask comes up
    c.arms(29.5, (-30, 20, 0), side='L', dur=0.2)
    c.arms(30.2, MASK_POSE, side='L', dur=0.3, ease='inout')
    c.eyes(W_SEE + 0.02, 'open')
    c.eyes(30.3, 'narrow')
    c.arms(30.0, (30, 45, 0), side='R', dur=0.2)
    c.look(30.3, (0, -60, 12), turn=0.0)
    # the reveal: his eyes narrow over the smile
    c.eyes(32.06, 'angry')
    c.eyes(33.0, 'narrow')
    # revision 2: the shinigami eyes are his. The mask comes down; on "shinigami" his eyes flare red and he turns to
    # stare through the wall at the researcher (the eye light throws red on the wall and the slot)
    c.arms(W_SHINI - 0.16, 'back', side='L', dur=0.14)                  # the lie goes behind his back
    c.eyes(W_SHINI - 0.08, 'narrow', glow=0.0)
    c.eyes(W_SHINI, 'open', glow=3.0, color=EYE_RED, dur=0.04)
    c.eyes(W_SHINI + 0.12, glow=2.0, dur=0.1)
    c.squash(W_SHINI, 0.1, 0.4)
    c.look(W_SHINI + 0.22, RES_SPOT + Vector((0.0, 0.0, 9.0)), turn=0.5, dur=0.28)
    c.eyes(34.4, 'angry', glow=2.0)
    # the retreat: the red goes out, innocent ^^
    c.eyes(T_RET + 0.22, 'happy', glow=0.0, dur=0.12)
    c.look(T_RET + 0.3, None, dur=0.25)
    c.eyes(36.3, 'open')
    c.look(36.4, RB.SLOT_C, turn=0.25)
    kit.visible(mask, W_SEE - 0.01, W_SHINI)          # gone with the glare cut (the arm is already behind him)


def act_researcher(r, cams):
    slot = RB.SLOT_C
    # posting the note
    # leans in from the hips with his head held back, so the arm reaches the slot while his face stays off the wall
    chars.POSES['post'] = dict(spine=(18, 0, 0), head=(-12, 0, 0), hands=((1.1, -1.8, 4.2), (-1.0, -3.0, 3.6)),
                               wrist=((20, 0, 0), (-10, 0, 0)))
    r.pose(27.2, 'post', dur=0.3)
    r.face(27.2, 'neutral')
    for t in (27.3, 27.5, 27.65, 27.8):
        r.hand(t, 'R', slot + Vector((NOTE_X(t) - 2.0, -0.25, 0.2)), dur=0.15)
    r.hand(28.05, 'R', slot + Vector((-2.6, -0.4, 0.8)), dur=0.2)
    r.pose(28.3, 'hold', dur=0.35)
    r.face(28.3, 'nervous')
    r.look(28.35, slot + Vector((0, 0, 1)))
    # the shoggoth rises: fear
    r.pose(30.7, 'back_away', dur=0.3)
    r.look(30.8, (6, 4, 26), turn=0.0)
    # POV shot: he looks up into the lens, pushes his glasses up, glint, points
    cam = cams['glint']
    cp = cam.at(33.4)
    r.turn(32.72, math.degrees(math.atan2(cp.x - RES_SPOT.x, -(cp.y - RES_SPOT.y))), dur=0.3)
    r.look(32.8, cp, turn=0.0, dur=0.2)
    r.face(32.95, 'scared')
    r.pose(33.28, 'gasp', dur=0.2)                  # hands to his mouth (the arms can't reach the glasses)
    r.glasses_glint(33.36)
    r.face(33.45, 'nervous')
    # revision 2: he's the one being seen. He turns from the box to the front, feels watched, sweats, glances at
    # the box beside him
    r.turn(W_SHINI + 0.3, 0.0, dur=0.35)
    r.pose(W_SHINI + 0.35, 'nervous', dur=0.3)
    r.look(W_SHINI + 0.4, cams['name'].at(34.9), turn=0.0, dur=0.25)
    r.face(34.3, 'scared')
    r.sweat(34.55, 35.9)
    r.fidget(34.9, 35.6, 1.2)
    r.look(35.15, RB.SLOT_C + Vector((0.0, -2.0, 6.0)), turn=0.0, dur=0.16)   # a glance at the box: who's watching?
    r.look(35.45, cams['name'].at(35.45), turn=0.0, dur=0.16)
    # the retreat: he backs off from the box
    r.pose(36.0, 'back_away', dur=0.3)
    r.walk(35.95, 36.55, [(RES_BACK.x, RES_BACK.y)], face='back')
    r.turn(36.8, math.degrees(math.atan2(slot.x - RES_BACK.x, -(slot.y - RES_BACK.y))), dur=0.3)
    r.look(37.0, slot)
    r.face(37.0, 'nervous')
    r.pose(37.7, 'gasp', dur=0.2)


# ------------------------------------------------------------------------------------------------ the bag


def bag_tip(b):
    """The stamp's thump tips the bag: a wobble, then it topples onto its side and bounces once."""
    piv = b.bag_pivot
    t_hit = STAMP + 0.02

    def ang(t):
        if t < t_hit:
            return 0.0
        x = t - t_hit
        wob = math.radians(9) * math.sin(x * 26) * math.exp(-x * 6) if x < 0.1 else 0.0
        fall = smooth(t, t_hit + 0.06, t_hit + 0.26) ** 1.6
        a = -math.radians(90) * fall
        if t > t_hit + 0.26:
            y = t - (t_hit + 0.26)
            a += math.radians(7) * math.sin(y * 30) * math.exp(-y * 12)
        return a + wob
    twos(piv, 'rotation_euler', ang, 27.4, 30.0, index=1)
    return piv


# ------------------------------------------------------------------------------------------------ mushrooms


def bag_mouth(b):
    bw, bd, bh = b.bag_size
    piv = b.bag_pivot
    yaw = piv.rotation_euler[2]
    return Vector(piv.location) + Matrix.Rotation(yaw, 3, 'Z') @ Vector((-bh, 0.0, 0.0))


def grow_shrooms(b, cs):
    coll = kit.collection('shrooms')
    protos_coll = kit.collection('shrooms.protos', coll)
    mats = SR.glow_mat()
    SR.build_protos(protos_coll, mats)
    protos_coll.hide_render = True
    protos_coll.hide_viewport = True
    mouth = bag_mouth(b)
    piv = Vector(b.bag_pivot.location)
    bw, bd, bh = b.bag_size

    def seg_d(p, a, c_):
        ap, ac = Vector((p[0], p[1])) - a.xy, c_.xy - a.xy
        u = max(0.0, min(1.0, ap.dot(ac) / max(1e-9, ac.length_squared)))
        return (ap - ac * u).length

    def rect(cx, cy, hx, hy, rot=0.0):
        cr, sr_ = math.cos(-rot), math.sin(-rot)

        def f(x, y):
            dx, dy = x - cx, y - cy
            lx, ly = dx * cr - dy * sr_, dx * sr_ + dy * cr
            return abs(lx) < hx and abs(ly) < hy
        return f
    cl, bk, mt = RB.CLAWD, RB.BOOK, RB.MATCH
    ex_in = [rect(cl.x, cl.y, 4.3, 2.6),
             rect(bk.x, bk.y, 6.0, 4.6, math.radians(6)),
             rect(mt.x, mt.y, 2.9, 2.0, math.radians(-8)),
             lambda x, y: seg_d((x, y), piv, mouth) < bd / 2 + 0.5,
             lambda x, y: (x - RB.X0) < 1.8 and abs(y - RB.SLOT_C.y) < 1.5]
    ex_out = [lambda x, y: seg_d((x, y), RES_SPOT, RES_BACK) < 2.8,
              lambda x, y: -33 < x < -1 and y > 2.5,
              lambda x, y: seg_d((x, y), Vector((-33.0, -2.2)), RB.SLOT_C) < 1.2 + 0.18 * (x + 33.0),
              lambda x, y: math.hypot(x - 59, y + 15) < 7]
    b.flap.data.update()
    bpy.context.view_layer.update()
    mw = b.flap.matrix_world.copy()
    fw, fh = b.flap_size

    def flap_pt(u, v):
        return mw @ Vector(((u - 0.5) * (fw - 1.2), RB.T / 2 + 0.01, 0.4 + v * (fh - 0.9)))
    pts = SR.layout(t_start=W_SHROOMS, mouth=(mouth.x, mouth.y), exclude_in=ex_in, exclude_out=ex_out,
                    flap_pts=flap_pt)
    # none right at the shot-3 floor camera (it creeps from (8.4,-17.0) to (8.9,-18.8)): a cap there filled the lens.
    # Filtered after the layout so every other mushroom keeps its place, size and birth time
    lens_a, lens_b = Vector((8.4, -17.0, 0.0)), Vector((8.9, -18.8, 0.0))
    pts = [q for q in pts if not (abs(q['co'][2] - RB.FLOOR) < 1e-6 and seg_d(q['co'], lens_a, lens_b) < 3.2)]
    field, mod = SR.build_field(coll, pts, protos_coll)
    # bob to the beat once awake
    path = f'modifiers["{mod.name}"].properties.inputs.{input_id(mod, "Beat")}.value'
    twos(field, path, lambda t: beat_pulse(t) * smooth(t, W_SHROOMS + 0.3, W_SHROOMS + 0.8), T0 - 0.1, T1 + 0.1)
    SR.key_mats(mats, hue_shift, lambda t: (0.25 + 0.75 * psy(t)) * (0.85 + 0.35 * beat_pulse(t) * psy(t)),
                T0 - 0.1, T1 + 0.1)
    # three liberty caps peeking out of the bag. They ride it down, and as it lands they slump onto its lower side
    # and spill half out of the mouth, lying on the floor (pivot local +x is up once the bag is on its side)
    t_hit = STAMP + 0.02
    for i, (x, y, s, rz, y_end) in enumerate(((0.2, 0.3, 1.05, 10, 1.05), (-0.7, -0.4, 0.95, 70, -0.05),
                                               (0.95, -0.75, 0.85, 140, -1.05))):
        bm = bmesh.new()
        SR.proto_liberty(bm)
        o = cg.to_object(bm, f'bag.shroom{i}', coll, mats, sharp=None)
        o.scale = (s, s, s * 1.25)
        z0 = bh - 2.1 * s * 1.25 + 0.6
        geo.attach(o, b.bag_pivot, (bw / 2 + x, y, z0), (0, 0, math.radians(rz)))

        def cap(t, x=x, y=y, s=s, z0=z0, y_end=y_end, i=i):
            u = smooth(t, t_hit + 0.12 + 0.03 * i, t_hit + 0.32 + 0.03 * i)
            w = smooth(t, t_hit + 0.2 + 0.03 * i, t_hit + 0.42 + 0.03 * i)
            return Vector((lerp(bw / 2 + x, 0.48 * s + 0.2, u), lerp(y, y_end, u), z0 + 0.4 * w))
        twos_vec(o, 'location', cap, 27.4, 30.0)
    return dict(field=field, mats=mats, pts=pts, mouth=mouth)


# ------------------------------------------------------------------------------------------------ shoggoth


TENTACLES = [
    # base (x, y), yaw offset from front (rad), lean, length, R0, curl, sway, freq, phase, twist, eyes, t_rise
    ((3.8, 6.8), -0.75, 0.22, 34, 4.2, 2.1, 0.34, 2.1, 0.0, 0.5, 14, 30.40),      # (bases 0 and 6 clear of the laptop)
    ((4.0, 12.5), -0.28, 0.12, 46, 5.2, 1.55, 0.3, 1.8, 1.3, 0.4, 18, 30.28),
    ((8.5, 7.6), 0.0, 0.14, 40, 5.9, 2.2, 0.28, 1.6, 2.2, 0.35, 20, 30.36),
    ((12.5, 12.5), 0.32, 0.12, 46, 4.9, 1.75, 0.32, 1.9, 3.1, 0.45, 17, 30.44),
    ((14.4, 5.8), 0.85, 0.2, 33, 4.0, 2.3, 0.36, 2.3, 4.0, 0.5, 14, 30.52),
    ((6.5, 16.5), 0.05, 0.05, 52, 4.3, 1.2, 0.26, 1.5, 5.2, 0.3, 16, 30.32),
    ((4.0, 16.0), -1.15, 0.2, 31, 3.2, 3.0, 0.4, 2.5, 0.7, 0.6, 11, 30.58),
    ((13.5, 16.5), 0.6, 0.2, 28, 3.2, 3.1, 0.4, 2.4, 1.9, 0.6, 11, 30.64),     # (pulled back off the P(doom) gauge)
    # three short ones that flop over the back wall onto the lid
    ((3.5, 4.0), -0.05, 0.0, 36, 2.8, 3.6, 0.18, 2.7, 2.6, 0.25, 9, 30.73),
    ((9.0, 4.2), 0.1, 0.0, 34, 2.9, 3.7, 0.18, 2.9, 3.7, 0.25, 9, 30.78),
    ((13.0, 4.0), 0.25, 0.0, 33, 2.5, 3.8, 0.2, 3.1, 4.6, 0.25, 8, 30.68),
]


def rise_curve(t, t_on, t_off):
    up = smooth(t, t_on, t_on + 0.62)
    over = 0.07 * math.sin(math.pi * min(1.0, max(0.0, (t - t_on - 0.45) / 0.5)))
    down = smooth(t, t_off, t_off + 0.6) ** 1.4
    return max(0.0, (up + over * (1 - down)) * (1 - down))


def shoggoth(b, look):
    coll = kit.collection('shoggoth')
    protos = kit.collection('shoggoth.protos', coll)
    M = SH.mats()
    eye, ring, sucker = SH.build_protos(protos, M)
    protos.hide_render = True
    protos.hide_viewport = True
    tree = SH.tentacle_tree(eye, ring, sucker, M['vinyl'])
    obs = []
    for i, (xy, dyaw, lean, L, r0, curl, sway, fq, ph, tw, ne, t_on) in enumerate(TENTACLES):
        ob, mod = SH.tentacle(coll, tree, f'tentacle{i}', look, Base=(xy[0], xy[1], -0.5), Yaw=-math.pi / 2 + dyaw,
                              Lean=lean, Length=float(L), R0=r0, Curl=curl, Sway=sway, Freq=fq, Phase=ph, Twist=tw,
                              Eyes=ne, Seed=17 * i + 3, Suckers=16 if r0 > 2.5 else 12, Rise=0.0,
                              Unfurl=0.0 if i >= 8 else 2.4, CurlGrow=3.0 if i >= 8 else 0.0)
        t_off = RETREAT + 0.06 * i
        pth = lambda nm, mod=mod: f'modifiers["{mod.name}"].properties.inputs.{input_id(mod, nm)}.value'
        twos(ob, pth('Rise'), lambda t, a=t_on, b_=t_off: rise_curve(t, a, b_), T0 - 0.1, T1 + 0.1)
        twos(ob, pth('Open'), lambda t: smooth(t, W_LIES - 0.02, W_LIES + 0.12) * (1 - smooth(t, RETREAT - 0.1,
                                                                                           RETREAT + 0.12)),
             T0 - 0.1, T1 + 0.1)
        twos(ob, pth('Stare'), lambda t: smooth(t, STARE - 0.05, STARE + 0.1) * (1 - 0.45 * smooth(t, 33.0, 33.6)),
             T0 - 0.1, T1 + 0.1)
        kit.visible(ob, t_on - 0.05, t_off + 0.75)
        obs.append(ob)
    # the mass behind the box
    et = SH.blob_tree(eye, ring)
    body, eyes_ob, emod = SH.blob(coll, 'shog.mass', M, radius=8.0, squash=(1.2, 0.9, 1.6), n_eyes=52, seed=5,
                                  look=look, eyes_tree=et)
    rest = Vector((7.5, 13.5, 14.0))
    low = Vector((7.5, 13.5, -22.0))

    def mpos(t):
        u = smooth(t, 30.45, 31.05) - smooth(t, RETREAT + 0.15, RETREAT + 0.95)
        p = low.lerp(rest, u)
        p.z += 0.5 * math.sin((t - 30) * 3.1) * u      # breathing
        return p
    twos_vec(body, 'location', mpos, T0 - 0.1, T1 + 0.1)
    twos(body, 'scale', lambda t: 1.0 + 0.035 * math.sin((t - 30) * 4.3), T0 - 0.1, T1 + 0.1, index=2)
    epath = lambda nm: f'modifiers["{emod.name}"].properties.inputs.{input_id(emod, nm)}.value'
    twos(eyes_ob, epath('Open'), lambda t: smooth(t, W_LIES - 0.02, W_LIES + 0.12) * (1 - smooth(t, RETREAT - 0.1,
                                                                                                  RETREAT + 0.12)),
         T0 - 0.1, T1 + 0.1)
    twos(eyes_ob, epath('Stare'), lambda t: smooth(t, STARE - 0.05, STARE + 0.1) * (1 - 0.45 * smooth(t, 33.0, 33.6)),
         T0 - 0.1, T1 + 0.1)
    for o in (body, eyes_ob):
        kit.visible(o, 30.3, RETREAT + 1.1)
    return dict(tentacles=obs, mass=body)


# ------------------------------------------------------------------------------------------------ the peeking eye


def peek(b):
    """One eye on a stubby tentacle tip pushes the slot flap open from inside and looks around."""
    coll = kit.collection('peek')
    M = SH.mats()
    slot = RB.SLOT_C
    root = geo.empty('peek.root', slot + Vector((1.2, 0, -0.25)), coll, 0.5)
    bm = bmesh.new()
    cg.tube(bm, [Vector((3.0, 0, 0)), Vector((1.2, 0, 0.05)), Vector((0.0, 0, 0.08))], [0.46, 0.45, 0.43], segs=20,
            cap0=False)
    nub = cg.to_object(bm, 'peek.nub', coll, [M['vinyl']], sharp=None)
    geo.attach(nub, root)
    eye_bm = bmesh.new()
    cg.uv_sphere(eye_bm, 1.0, segs=28, rings=16)
    for f in eye_bm.faces:
        z = f.calc_center_median().z
        f.material_index = 2 if z > 0.93 else (1 if z > 0.74 else 0)
    eye = cg.to_object(eye_bm, 'peek.eye', coll, [M['sclera'], M['iris'], M['pupil']], sharp=None)
    eye.rotation_mode = 'XYZ'
    geo.attach(eye, root, (-0.28, 0, 0.1))
    eye.scale = (0.44, 0.44, 0.44)
    # push out through the slot: root x from inside to just past the flap
    out_x = slot.x - 0.95
    twos(root, 'location', lambda t: lerp(slot.x + 3.2, out_x, smooth(t, PEEK, PEEK + 0.22)) +
         0.15 * math.sin(max(0.0, t - PEEK - 0.22) * 18) * math.exp(-max(0.0, t - PEEK - 0.22) * 7) * (t > PEEK + 0.22),
         T0, T1 + 0.1, index=0)
    # the eye faces -x (out) then looks left, right, at the lens; eyes are +Z-forward protos
    base_rot = (0.0, math.radians(-90), 0.0)          # +Z -> -X

    def yaw(t):          # looks one way, the other, then straight into the lens
        return (math.radians(40) * smooth(t, 37.86, 37.94) - math.radians(85) * smooth(t, 38.02, 38.1) +
                math.radians(27) * smooth(t, 38.16, 38.22))
    twos(eye, 'rotation_euler', lambda t: base_rot[1], T0, T1, index=1)
    twos(eye, 'rotation_euler', yaw, T0, T1 + 0.1, index=0)

    def blink(t):
        return 0.44 * max(0.06, 1 - 0.95 * (smooth(t, 38.26, 38.29) - smooth(t, 38.31, 38.35)))
    twos(eye, 'scale', blink, T0, T1 + 0.1, index=0)
    # the flap lifts outward over the nub
    fl = b.slot_flap

    def flap(t):
        base = -math.radians(62) * smooth(t, 27.3, 27.5) * (1 - smooth(t, 27.9, 28.15))
        return base + math.radians(76) * smooth(t, PEEK - 0.02, PEEK + 0.18)
    geo.clear_keys(fl, 'rotation_euler')
    twos(fl, 'rotation_euler', flap, 27.0, T1 + 0.1, index=1)
    kit.visible(nub, PEEK - 0.1, None)
    kit.visible(eye, PEEK - 0.1, None)


# ------------------------------------------------------------------------------------------------ light


def lights(d, b, shrooms):
    lc = kit.collection('room.lights')
    # a soft warm key from the front-left (the tabletop's softbox); it takes on the trip's colours
    key = kit.area('room.key', (-38, -58, 46), (0, -12, 6), power=100000.0, size=35.0, color='#FFE4C8', coll=lc)
    warm = kit.srgb('#FFE4C8')[:3]

    def key_col(t, i):
        p = psy(t)
        h = hsv(0.36 + hue_shift(t) * 0.6, 0.7, 1.0)
        return warm[i] * (1 - 0.55 * p) + h[i] * 0.55 * p
    for i in range(3):
        every_frame(key.data, 'color', lambda t, i=i: key_col(t, i), T0, T1, index=i)
    every_frame(key.data, 'energy', lambda t: 100000.0 * (1 - 0.93 * psy(t)) * flick(t) *
                (1 - 0.85 * smooth(t, RETREAT + 0.6, RETREAT + 1.6)), T0, T1)
    # the room's own fill and window light drop while the trip is on, so the coloured light has deep shadows
    if d.room is not None and d.room.bounce is not None:
        e0 = d.room.bounce.data.energy
        every_frame(d.room.bounce.data, 'energy', lambda t: e0 * (1 - 0.65 * psy(t)) * flick(t) *
                    (1 - 0.5 * smooth(t, RETREAT + 0.6, RETREAT + 1.6)), T0, T1)
    if d.room is not None and d.room.moon is not None:
        e1 = d.room.moon.data.energy
        every_frame(d.room.moon.data, 'energy', lambda t: e1 * (1 - 0.4 * psy(t)), T0, T1)
    # the bulb inside: warm, then cycling with the mushrooms, pulsing on the beat
    bl = b.bulb_light
    bwarm = kit.srgb('#FFC27A')[:3]

    def bulb_col(t, i):
        p = psy(t)
        h = hsv(0.1 + hue_shift(t) * 1.3)
        return bwarm[i] * (1 - p) + h[i] * p
    for i in range(3):
        every_frame(bl.data, 'color', lambda t, i=i: bulb_col(t, i), T0, T1, index=i)
    every_frame(bl.data, 'energy', lambda t: 48000.0 * (1 - 0.85 * psy(t)) * (1 + 0.8 * beat_pulse(t) * psy(t)) * (
        1 - 0.85 * smooth(t, STAMP, STAMP + 0.04) * (1 - smooth(t, STAMP + 0.04, STAMP + 0.16))) *
        (0.25 + 0.75 * flick(t)), T0, T1)
    # the bulb swings after the thump and in the rumble (a damped pendulum about the ceiling), its glass matching
    # the light's colour
    piv = b.bulb_pivot

    def swing(t, axis):
        a = 0.0
        if t > STAMP:
            x = t - STAMP
            a += math.radians(9) * math.sin(x * 7.5 + axis * 1.3) * math.exp(-x * 1.6)
        if t > 30.3:
            x = t - 30.3
            a += math.radians(5) * math.sin(x * 7.5 + 2.0 + axis) * math.exp(-x * 1.2) * (0.6 if axis else 1.0)
        return a
    every_frame(piv, 'rotation_euler', lambda t: swing(t, 0), T0, T1, index=0)
    every_frame(piv, 'rotation_euler', lambda t: swing(t, 1) * 0.6, T0, T1, index=1)
    em = b.bulb_mat.node_tree.nodes.get('Principled BSDF').inputs['Emission Color']
    for i in range(3):
        every_frame(em, 'default_value', lambda t, i=i: bulb_col(t, i), T0, T1, index=i)
    # mushroom glow lights: coloured pools that wake with the wave
    pts = shrooms['pts']
    spots = [((6.5, -12.5, 1.3), 700), ((-1.0, -17.5, 1.3), 600), ((1.5, -29.0, 2.0), 9000),
             ((-21.0, -3.5, 2.0), 1600), ((16.0, -27.0, 2.0), 7000), ((-19.0, -24.0, 2.0), 6000),
             ((22.0, -8.0, 2.0), 5000)]
    for k, (p, e) in enumerate(spots):
        near = [q['birth'] for q in pts if (Vector(q['co']).xy - Vector(p).xy).length < 6.0]
        t_on = min(near) if near else W_SHROOMS + 1.0
        ld = kit.point(f'room.glow{k}', p, power=0.0, radius=1.5, color='#FF40C0', coll=lc)
        ld.data.use_shadow = False
        h0 = k * 0.21

        def en(t, e=e, t_on=t_on):
            return e * smooth(t, t_on, t_on + 0.5) * (0.35 + 0.65 * psy(t)) * (0.8 + 0.4 * beat_pulse(t))
        every_frame(ld.data, 'energy', en, T0, T1)
        for i in range(3):
            every_frame(ld.data, 'color', lambda t, i=i, h0=h0: hsv(h0 + hue_shift(t), 0.9)[i], T0, T1, index=i)
    # coloured rims on the shoggoth from behind
    for k, (p, h0) in enumerate((((-30, 30, 30), 0.83), ((40, 25, 28), 0.5))):
        sp = kit.spot(f'room.rim{k}', p, (7, 8, 30), power=0.0, angle_deg=30, blend=0.7, radius=3.0, coll=lc)
        every_frame(sp.data, 'energy', lambda t: 70000.0 * psy(t) * flick(t), T0, T1)
        for i in range(3):
            every_frame(sp.data, 'color', lambda t, i=i, h0=h0: hsv(h0 + hue_shift(t) * 0.6, 0.8)[i], T0, T1, index=i)
    # an uplight from the glowing carpet in front of the box: under-lights the shoggoth in the trip's colours
    # (a narrow spot from low in front, aimed above the lid so it never reaches into the box)
    up = kit.spot('room.uplight', (5, -46, 8.0), (7, 6, 35), power=0.0, angle_deg=16, blend=0.5, radius=2.0, coll=lc)
    every_frame(up.data, 'energy', lambda t: 160000.0 * psy(t) * (0.85 + 0.3 * beat_pulse(t)) * flick(t), T0, T1)
    for i in range(3):
        every_frame(up.data, 'color', lambda t, i=i: hsv(0.5 + hue_shift(t) * 0.8, 0.75)[i], T0, T1, index=i)
    # the desk lamp: a bad contact in the break
    d.lamp.flicker(FLICK0, FLICK1, depth=0.95, rate=14, seed=5, dropouts=0.4, end=1.0)
    # haze thickens while the trip is on (coloured shafts)
    if d.room is not None and d.room.haze_density is not None:
        every_frame(d.room.haze_density, 'default_value', lambda t: 0.0006 + 0.0002 * psy(t), T0, T1)


def flick(t):
    """The break's flicker applied to the extra lights too (same seed/rate as the lamp)."""
    if not (FLICK0 <= t < FLICK1 + 1.0 / FPS):
        return 1.0
    k = int(round((t - FLICK0) * FPS))
    n = max(1, int((FLICK1 - FLICK0) * FPS))
    if k >= n:
        return 1.0
    h = geo.hash01('flicker', 5, k // max(1, int(FPS / 14)))
    v = 1.0 - 0.95 * h
    if geo.hash01('drop', 5, k) < 0.4 * (1 - k / (n + 1)):
        v = 0.04
    return v
