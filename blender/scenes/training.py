"""training · 5.692-16.601 · "Your circuits make me nervous, that's no surprise / There was a sudden drop in your
training loss, / now I'm your servant and you're my boss"

Shot list (song seconds; characters and toy props on twos, the plunge on ones; cameras smooth at 24 fps):

 T1  wake     5.692-7.040  85 mm on Clawd, still plugged in, eyes glowing from the boot, the researcher at the frame
                           edge. A slow sleepy blink puts the glow out (5.86); a huge yawn-and-stretch on "circuits"
                           (lid wide, arms up); the lid snaps shut on "make" (6.56); he looks left, then up at the
                           researcher and goes ^^ (6.98). Slow push in. Cut on "nervous" (7.04).
 T2  nervous  7.040-9.328  85 mm over Clawd's lid (a soft orange band along the bottom) at the researcher: nervous
                           face, sweat bead, hand-wringing, a gulp, while Clawd bounces happily on the beat; on
                           "surprise" (8.496) he adjusts his glasses, which glint (8.68). Slow push. Cut on 9.328.
 T3a maze     9.328-10.137 35 mm wide: the bead-maze toy (training_maze.py), a blue enamel wire bent into a loss curve
                           (fast decay, plateau, sudden drop, long low tail) with yellow and green toy wires behind;
                           the laptop behind shows the same curve; the researcher watches from behind the tail. Clawd
                           straddles a red barrel bead, swaying to the beat as it crawls along the plateau. Slow truck.
 T3b crest    10.137-10.66 28 mm from in front of the lip, the drop plunging away below him. "sudden": he startles
                           (eyes wide, pops up, arms fly), looks down the drop, eyes shrink; the bead creeps over.
 T3c drop     10.66-11.52  35 mm low at the foot of the drop: on "drop" (10.66) he plunges down the near-vertical wire
                           (on ones), rolled sideways, mouth open, arms up; swoops through the bottom grinning (^^) and
                           out along the tail as the camera tilts down and pans with him.
 T3d loss     11.52-12.965 50 mm on the tail: he glides in and crashes into the three resting beads on "loss" (12.06):
                           he lurches, the beads rattle, camera shake, dizzy spiral eyes, then star eyes and a cheer.
 T4a throne   12.965-14.783 35 mm low wide: Clawd sits in the mug's rim like a throne (the mug's handle turned away),
                           the researcher in profile below. "now" (13.16): a paper crown flutters down and lands on his
                           head (13.46), he beams ^^. The researcher bows and kneels on "servant" (13.72) and raises a
                           sugar cube. The lamp is re-aimed and a warm spot lights the throne.
 T4b offer    14.783-15.66 45 mm, the king's view from beside the mug, down at the kneeling researcher (revision 2: lower,
                           so the lyric stand in front of his knees is sharp): he beams up,
                           sugar cube held high; Clawd's shoulder at the frame edge leans in; rack focus cube -> face.
 T4c boss     15.66-16.601 Close on the crowned Clawd: on "boss" (15.66) his eyes narrow, he sits back and folds his
                           arms; a dolly zoom (40 -> 110 mm while dollying out) swells the gauge behind him; the lid
                           cracks open into a toothy smirk (16.1).
"""
import math

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom import timing as tm
from pdoom.sets import build_desk, geo
from pdoom.sets import materials as M

from scenes.boot_common import Cam, key_mats, shake
from scenes.training_maze import BEAD_R, build_maze, loss_image

EYE = '#FFB24A'
FPS = tm.FPS


def _hide_between(objs, t_off, t_on=None):
    """Render-hide objects from t_off (and show again from t_on)."""
    sc = bpy.context.scene
    for o in objs:
        for t, h in ((sc.frame_start / FPS - 1, False), (t_off, True)) + (((t_on, False),) if t_on else ()):
            o.hide_render = h
            o.hide_viewport = h
            o.keyframe_insert('hide_render', frame=t * FPS)
            o.keyframe_insert('hide_viewport', frame=t * FPS)     # (the lyric stand's ray probes see it too)
        for fc in kit.fcurves(o):
            if fc.data_path in ('hide_render', 'hide_viewport'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
        o.hide_viewport = False


def _show_only(objs, t_on, t_off):
    sc = bpy.context.scene
    for o in objs:
        for t, h in ((sc.frame_start / FPS - 1, True), (t_on, False), (t_off, True)):
            o.hide_render = h
            o.hide_viewport = h
            o.keyframe_insert('hide_render', frame=t * FPS)
            o.keyframe_insert('hide_viewport', frame=t * FPS)     # (the lyric stand's ray probes see it too)
        for fc in kit.fcurves(o):
            if fc.data_path in ('hide_render', 'hide_viewport'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
        o.hide_viewport = False


def build():
    sc = kit.new_scene('training')
    d = build_desk(kit.collection('desk'), mood='night')
    A = d.anchors
    V = Vector

    # ------------------------------------------------------------------ times (from the lyrics)
    w = lambda ln, wd: tm.word(ln, wd)['start']
    t_circ = w('Your circuits', 'circuits')          # 5.991
    t_make = w('Your circuits', 'make')              # 6.56
    t_nerv = w('Your circuits', 'nervous')           # 7.04
    t_surp = w("that's no surprise", 'surprise')     # 8.496
    t_sudden = w('sudden drop', 'sudden')            # 10.137
    t_drop = w('sudden drop', 'drop')                # 10.66
    t_train = w('sudden drop', 'training')           # 11.52
    t_loss = w('sudden drop', 'loss')                # 12.06
    t_now = w('servant', 'now')                      # 13.16
    t_serv = w('servant', 'servant')                 # 13.719
    t_boss = w('servant', 'boss')                    # 15.66
    # cuts on exact frames; characters switch a quarter frame before a cut (and run on ones around the T4 cut,
    # which falls on an odd frame: on twos it would still show the previous pose)
    T3, T4 = tm.t2f(9.328) / FPS, tm.t2f(12.965) / FPS
    SW = 0.25 / FPS
    # cut-synchronised switches (lamp, lights, laptop, mug, set visibility): the old value is keyed a whole frame
    # before the cut (PRE) and the new one a quarter frame before it (SW), never on the cut frame itself (that would
    # half-fade the first frame under the motion-blur shutter). The two keys sit in different 24 fps frames, so the
    # 60 fps render's switch alignment (run.py: ceil(f) - 0.1) can't merge them and drop the pre-cut value.
    PRE = 1.0 / FPS
    T4b = 14.783
    t_end = 16.601

    # ------------------------------------------------------------------ the desk
    d.laptop.set_image('boot', 'A')
    d.laptop.set_image(loss_image(), 'B')
    d.laptop.screen(T3 - PRE, mix=0.0, interp='CONSTANT')
    d.laptop.screen(T3 - SW, mix=1.0, interp='CONSTANT')
    d.laptop.screen(5.6, glow=1.3)
    if d.pen is not None:
        _hide_between(d.pen.objects, T3 - SW)          # the pen lies where the bead maze stands

    # ------------------------------------------------------------------ Clawd (the one at the spot, then the throne)
    cs = A['clawdSpot']
    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=(cs.x, cs.y, 0), yaw=0)
    c.visible(None, T3 - SW)
    c.visible(T4 - SW, None)
    c.timing(T4 - 0.1, T4 + 0.1, 'ones')
    # T1 wake
    c.eyes(5.5, 'open', glow=5.0, color=EYE, dur=0.0)
    c.blink(5.84, dur=0.34)
    c.eyes(5.99, glow=0.0, dur=0.1)
    c.eyes(6.08, 'shut')
    c.lid(6.42, 0.95, dur=0.32, ease='inout')
    c.arms(6.36, 'high', dur=0.28)
    c.T['body.sq'].set(6.38, 0.13, 0.3)
    c.T['body.rot'].set(6.38, (-8.0, 0.0, 0.0), 0.3)
    c.lid(t_make + 0.04, 0.0, dur=0.07)
    c.T['body.sq'].set(t_make + 0.1, 0.0, 0.1)
    c.T['body.rot'].set(t_make + 0.1, (0.0, 0.0, 0.0), 0.1)
    c.squash(t_make + 0.06, 0.14, 0.5)
    c.arms(t_make + 0.08, 'rest', dur=0.12)
    c.eyes(t_make + 0.08, 'open')
    # T2 (he's in the foreground): bounces happily
    # ------------------------------------------------------------------ the researcher
    rs = V((15.0, -9.8, 0.0))
    face0 = c.anchor(6.0, 'face')
    dv = face0 - rs
    r = chars.Researcher(kit.collection('researcher'), name='researcher', loc=(rs.x, rs.y, 0),
                         yaw=math.degrees(math.atan2(dv.x, -dv.y)))
    r.pose(5.5, 'hold', dur=0.0)
    r.face(5.5, 'awe')
    r.look(5.6, face0, dur=0.0)
    c.look(6.72, V((-14.0, -20.0, 4.0)), turn=0.0, dur=0.16)
    c.look(6.92, r, turn=0.0, dur=0.14)
    c.eyes(6.98, 'happy')
    # T2: nervous
    r.pose(7.2, 'nervous', dur=0.22)
    r.look(7.25, face0, dur=0.2)
    r.fidget(7.2, 8.25, 1.2)
    r.sweat(7.3, 9.4)
    r.nod(7.95, n=1, amount=9.0, every=0.3)
    r.pose(t_surp + 0.05, 'adjust_glasses', dur=0.28, face=False)
    # (the library pose ends with his mitten on his chin: his short arm can't reach the lenses in front of his big
    # head. Here he turns and tilts his head toward the hand, and the mitten comes up beside his face to push the
    # right lens's outer rim)
    r.T['head'].set(t_surp + 0.05, (8.0, -14.0, -22.0), 0.28)
    r.T['hand.R'].set(t_surp + 0.05, (-1.9, -1.55, 8.95), 0.28)
    r.T['wrist.R'].set(t_surp + 0.05, (-160.0, 0.0, 0.0), 0.28)
    r.glasses_glint(t_surp + 0.18, dur=0.35, strength=16.0)
    r.pose(9.05, 'nervous', dur=0.25)
    c.eyes(7.5, 'open')
    c.dance(7.51, 9.25, 'bounce', amount=0.8)
    c.look(7.3, r, turn=0.0, dur=0.2)

    # ------------------------------------------------------------------ the bead maze (T3)
    mcoll = kit.collection('maze')
    mz = build_maze(mcoll, origin=(7.0, -26.0, 0.0), yaw=0.0)
    maze_objs = list(mcoll.objects)
    _show_only(maze_objs, T3 - SW, T4 - SW)
    su = mz.s_of_u
    s_a, s_b, s_lip = su(8.4), su(15.3), su(16.55)
    s_bot, s_hit = su(21.5), mz.s_hit
    t_a0, t_b, t_lip, t_d0, t_d1 = 9.0, 10.40, 10.62, t_drop, 10.98

    def s_of_t(t):
        if t < t_b:
            u = max(0.0, (t - t_a0) / (t_b - t_a0))
            return s_a + (s_b - s_a) * (u * 0.85 + 0.15 * (1 - math.cos(math.pi * u)) / 2 * 1.0)
        if t < t_lip:
            u = (t - t_b) / (t_lip - t_b)
            return s_b + (s_lip - s_b) * (1 - (1 - u) ** 2)
        if t < t_d0:
            return s_lip
        if t < t_d1:
            u = (t - t_d0) / (t_d1 - t_d0)
            return s_lip + (s_bot - s_lip) * (u ** 1.7)
        if t < t_loss:
            u = (t - t_d1) / (t_loss - t_d1)
            return s_bot + (s_hit - s_bot) * (4 * u - 1.5 * u * u) / 2.5
        x = t - t_loss                              # recoil off the cluster, settle
        return s_hit - 0.9 * math.exp(-x * 7.0) * math.sin(min(x, 0.5) * math.pi / 0.5) - 0.25 * min(1.0, x / 0.3)
    spans = [(10.58, 11.4, 'ones')]
    lift = BEAD_R - 0.9
    key_mats(mz.bead, lambda t: mz.frame(s_of_t(t)), T3 - 0.2, T4 + 0.1, spans)
    seat = kit.empty('maze.seat', (0, 0, 0), mcoll)
    key_mats(seat, lambda t: mz.frame(s_of_t(t)) @ Matrix.Translation((0, 0, lift)), T3 - 0.2, T4 + 0.1, spans)
    # the cluster rattles on the hit
    for k, (e, s0) in enumerate(zip(mz.cluster, mz.cluster_s)):
        def fr(t, s0=s0, k=k):
            x = t - t_loss - 0.02 * k
            if x < 0:
                return mz.frame(s0)
            j = 0.5 * math.exp(-x * 9) * abs(math.sin(x * 28 + k))
            ds = 0.35 * math.exp(-x * 10) * math.sin(x * 30) if k < 2 else 0.0
            return mz.frame(s0 + ds, lift=j) @ Matrix.Rotation(math.radians(25 * math.exp(-x * 8) *
                                                                            math.sin(x * 24 + k)), 4, 'Y')
        key_mats(e, fr, T3, T4)

    # Clawd on the bead (his own instance, parented to the seat)
    cr = chars.Clawd(mcoll, name='clawd.ride', loc=(0, 0, 0), yaw=0, glow_light=False)
    cr.rig.parent = seat
    cr.rig.matrix_parent_inverse = Matrix.Identity(4)
    cr.rig.location = (0, 0, 0)
    cr.visible(T3 - SW, T4 - SW)
    cr.timing(T4 - 0.1, T4 + 0.1, 'ones')
    cr.no_gait(0.0, 99.0)
    cr.timing(10.58, 11.4, 'ones')
    for i in range(8):
        cr.T[f'leg{i}'].set(0.0, (-38.0 if i % 2 == 0 else 38.0, 0.0, 0.0), 0.0)
    cr.T['hips.loc'].set(0.0, (0.0, 0.0, -0.35), 0.0)
    cr.eyes(T3 - 0.3, 'happy')
    cr.arms(T3 - 0.3, 'up', dur=0.0)
    cr.dance(T3, t_sudden - 0.05, 'sway', amount=0.9)
    # "sudden": he sees the drop
    cr.arms(t_sudden + 0.02, 'down', dur=0.1)
    ts_ = t_sudden + 0.02                          # a startle: pop up, arms fly, eyes wide (lid stays shut)
    cr.eyes(ts_, 'surprised')
    cr.T['hips.loc'].add(ts_ - 0.02, ts_ + 0.3, lambda x: (0.0, 0.0, 0.9 * math.sin(math.pi * (x - ts_ + 0.02) / 0.32)))
    cr.squash(ts_ - 0.02, -0.18, 0.5)
    cr.arms(ts_ + 0.05, 'high', dur=0.06)
    cr.arms(ts_ + 0.3, 'down', dur=0.12)
    cr.T['eyes.look'].set(t_sudden + 0.34, (0.3, -0.2), 0.1)       # eyes slide toward the drop (his left, down)
    cr.eyes(t_sudden + 0.3, 'small')
    cr.T['body.rot'].set(10.5, (0.0, -10.0, 0.0), 0.15)
    # the plunge
    cr.T['body.rot'].set(t_drop + 0.05, (0.0, 8.0, 0.0), 0.08)
    cr.lid(t_drop + 0.06, 0.42, dur=0.08)
    cr.eyes(t_drop + 0.02, 'surprised')
    cr.arms(t_drop + 0.05, 'high', dur=0.08)
    cr.T['eyes.look'].set(t_drop + 0.1, (0.0, 0.0), 0.08)
    cr.eyes(10.95, 'happy')
    cr.arms(10.98, 'cheer', dur=0.1)
    cr.T['body.rot'].set(11.2, (0.0, 0.0, 0.0), 0.3)
    cr.lid(11.75, 0.25, dur=0.25)
    cr.arms(11.8, 'up', dur=0.2)
    # the crash on "loss"
    cr.lid(t_loss + 0.02, 0.0, dur=0.05)
    # the lurch starts on the hit and ramps in over ~2 output frames (it used to start 0.02 s early at full tilt,
    # ahead of the beads' rattle and his dizzy face)
    cr.T['body.rot'].add(t_loss, t_loss + 0.7, lambda x: (0.0, 16.0 * (1 - math.exp(-(x - t_loss) * 60)) *
                                                          math.exp(-(x - t_loss) * 6) * math.cos((x - t_loss) * 18),
                                                          0.0))
    cr.squash(t_loss + 0.04, 0.2, 0.6)
    cr.eyes(t_loss + 0.02, 'dizzy')                  # (with the lid's snap, two frames into the lurch)
    cr.arms(t_loss + 0.04, 'out', dur=0.06)
    cr.eyes(12.55, 'star')
    cr.arms(12.6, 'cheer', dur=0.15)
    cr.hop(12.62, 0.6, dur=0.26)

    # the researcher watches the ride from behind the tail
    rw = V((17.0, -15.0, 0.0))
    r.place(T3 - SW, loc=(rw.x, rw.y), yaw=math.degrees(math.atan2(-6.0, 11.0)))
    r.no_gait(T3 - 0.05, T3 + 0.1)
    r.pose(T3 - SW, 'nervous', dur=0.0, face=False)
    r.face(T3 - SW, 'nervous')
    r.timing(T4 - 0.1, T4 + 0.1, 'ones')
    r.pose(t_drop + 0.1, 'gasp', dur=0.12)
    r.pose(t_loss + 0.12, 'cheer', dur=0.2)
    r.face(t_loss + 0.12, 'happy')

    # ------------------------------------------------------------------ the throne (T4)
    mt = A['mugTop']
    seat_z = mt.z - 1.3 + 0.04
    K = V((mt.x - 9.6, mt.y - 0.8, 0.0))                  # the researcher kneels left of the mug, facing it
    c.place(T4 - SW, loc=(mt.x, mt.y, seat_z), yaw=-55.0)
    c.no_gait(T4 - 0.1, T4 + 0.15)
    c.eyes(T4 - SW, 'open', glow=0.0)
    c.arms(T4 - SW, 'rest', dur=0.0)
    c.look(T4 + 0.3, V((K.x, K.y, 8.0)), turn=0.0, dur=0.2)
    r.place(T4 - SW, loc=(K.x, K.y), yaw=88.0)
    r.no_gait(T4 - 0.1, T4 + 0.15)
    r.pose(T4 - SW, 'stand', dur=0.0)
    r.face(T4 - SW, 'nervous')
    r.look(T4 + 0.2, c, dur=0.2)
    # the mug turns its handle away (to the back right) for the throne shots
    mr = d.mug.root
    y_mug = mr.rotation_euler.z
    geo.keyp(mr, 'rotation_euler', T4 - PRE, y_mug, index=2, interp='CONSTANT')
    geo.keyp(mr, 'rotation_euler', T4 - SW, math.radians(35.0), index=2, interp='CONSTANT')
    # the crown drops on "now" and lands at 13.5
    t_land = 13.46
    c.wear(t_land, 'crown')
    c.squash(t_land + 0.02, 0.16, 0.6)
    c.eyes(t_land + 0.02, 'happy')
    c.eyes(13.95, 'open')
    crown = chars.props.make('crown', kit.collection('training.props'), 'crown.falling')
    from pdoom.chars.clawd import BONES, TOP
    from pdoom.chars.props import _Ry, _T
    # the crown sits ON the lid (the library's rest pose, TOP - 0.12 tilted 9 deg, sinks its low side and the gem
    # into the lid): raise and level the worn crown's mesh, and land the falling one on the same pose
    Mlib = _T((0.35, 0.15, TOP - 0.12)) @ _Ry(9)
    Mrest = _T((0.35, 0.15, TOP + 0.16)) @ _Ry(6)
    for ob in c._prop('crown'):
        ob.data.transform(Mrest @ Mlib.inverted())

    def crown_world(t):
        fk = c._fk(t)
        return c.rig.matrix_world @ fk['hat'] @ _T(-V(BONES['hat'])) @ Mrest

    Mland = crown_world(t_land)

    def crown_fall(t):
        # a paper crown flutters down: rocking side to side, turning, settling onto his lid
        if t >= t_land:                 # landed: ride the lid exactly like the worn crown until the swap
            return crown_world(t)
        u = min(1.0, max(0.0, (t - t_now) / (t_land - t_now)))
        h = 7.5 * (1 - u) ** 1.15
        k = (1 - u)
        spin = math.radians(-160.0 * k)
        rock = math.radians(24.0 * math.sin(u * math.pi * 3.0) * k)
        sway = V((1.3 * math.sin(u * math.pi * 3.0) * k, 0.0, 0.0))
        loc, rot, _ = Mland.decompose()
        R = Matrix.Rotation(spin, 4, 'Z') @ Matrix.Rotation(rock, 4, 'Y') @ rot.to_matrix().to_4x4()
        return Matrix.Translation(loc + sway + V((0.0, 0.0, h))) @ R
    key_mats(crown, crown_fall, t_now - 0.2, t_land + 0.1)
    _show_only([crown], t_now, t_land + 0.5 / FPS)
    # the servant: bow and kneel, sugar cube raised
    sugar_m = M.solid('training.sugar', '#FBF8F2', rough=0.55, sss=0.4, sss_radius=(0.4, 0.4, 0.4), micro=(40.0, 0.25))
    cube = kit.box('sugar', (1.2, 1.2, 1.2), (0, 0, 0), bevel=0.09, segments=2, m=sugar_m,
                   coll=kit.collection('training.props'))
    r.attach(cube, 'hand.R', offset=(0.0, -0.15, 0.55))
    _show_only([cube], T4 - SW, t_end + 1)
    r.pose(t_serv - 0.12, 'kneel_offer', dur=0.3)
    r.face(t_serv, 'nervous')
    r.nod(t_serv + 0.15, n=1, amount=16.0, every=0.4)
    # held out toward the king at arm's length, in front of and below his face (about 3.3 cm from the head centre,
    # within reach so the arm isn't clamped); it used to sit 1.9 cm from the head centre, inside his cheek
    hand_up = V((K.x + 3.4, K.y - 1.9, 7.0))
    # raised from low in front, so the sugar cube never passes his chin on the way up
    r.hand(14.18, 'R', hand_up + V((0.4, 0.0, -1.0)), dur=0.18, wrist=(-100.0, 0.0, 0.0))
    r.hand(14.35, 'R', hand_up, dur=0.17, wrist=(-100.0, 0.0, 0.0))
    r.face(14.3, 'happy')
    r.look(14.4, c, dur=0.25)
    # Clawd inspects the offering, then: boss
    c.look(14.9, hand_up + V((0, 0, 0.6)), turn=0.0, dur=0.2)
    c.T['body.rot'].set(15.15, (22.0, 0.0, 0.0), 0.3)
    c.T['body.rot'].set(t_boss + 0.12, (-6.0, 0.0, 0.0), 0.16)
    c.eyes(t_boss, 'narrow')
    c.arms(t_boss + 0.1, 'fold', dur=0.16)
    c.look(t_boss + 0.05, None, dur=0.15)
    c.lid(16.12, 0.16, dur=0.2)
    r.face(t_boss + 0.1, 'scared')

    # ------------------------------------------------------------------ the lamp re-aimed on the cuts (maze, throne)
    lp = d.lamp
    lp.aim(T3 - PRE, A['lampPool'], interp='CONSTANT')
    lp.aim(T3 - SW, V((4.0, -24.0, 13.0)), reach=30.0, height=52.0, interp='CONSTANT')
    lp.aim(T4 - PRE, V((4.0, -24.0, 13.0)), reach=30.0, height=52.0, interp='CONSTANT')
    lp.aim(T4 - SW, V((mt.x - 4.0, mt.y - 2.0, 6.0)), interp='CONSTANT')
    if d.room.motes is not None:
        _hide_between([d.room.motes], T3 - SW)
    # a soft front fill for the maze (the lamp sits behind the toy and only rims it)
    fl = kit.area('training.mazefill', (-14.0, -62.0, 38.0), (5.0, -26.0, 14.0), power=26000.0, size=30.0,
                  color='#FFD6A0', coll=kit.collection('training.fx'))
    fl.data.specular_factor = 0.35
    geo.keyp(fl.data, 'energy', T3 - PRE, 0.0, interp='CONSTANT')
    geo.keyp(fl.data, 'energy', T3 - SW, 26000.0, interp='CONSTANT')
    geo.keyp(fl.data, 'energy', T4 - PRE, 26000.0, interp='CONSTANT')
    geo.keyp(fl.data, 'energy', T4 - SW, 0.0, interp='CONSTANT')
    # ------------------------------------------------------------------ light for the throne (the lamp pool is far)
    tl = kit.spot('training.throne', (mt.x - 9.0, mt.y - 16.0, 40.0), (mt.x - 3.5, mt.y - 2.5, 7.0), power=60000.0,
                  angle_deg=32, blend=0.7, radius=1.5, color='#FFC27A', coll=kit.collection('training.fx'))
    geo.keyp(tl.data, 'energy', T4 - PRE, 0.0, interp='CONSTANT')
    geo.keyp(tl.data, 'energy', T4 - SW, 60000.0, interp='CONSTANT')
    geo.keyp(tl.data, 'energy', t_end + 0.1, 60000.0, interp='CONSTANT')

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('training.cams')
    face_c = c.anchor(6.0, 'face')
    # T1 wake: close on Clawd from the front left, low
    bc = V((cs.x + 0.3, cs.y - 1.0, 3.9))
    k1 = Cam('cam.wake', 85, bc + V((-15.5, -42.0, 3.0)), bc + V((0, 0, 0.8)), fstop=11.0, focus=face_c,
             coll=cams)
    k1.key(5.6, loc=bc + V((-15.5, -42.0, 3.0)), target=bc + V((0, 0, 0.8)), interp='LINEAR')
    k1.key(7.1, loc=bc + V((-13.0, -35.5, 2.6)), target=bc + V((0.2, 0.0, 0.8)), interp='LINEAR')
    # T2 nervous: over Clawd's shoulder up at the researcher
    eyes_r = r.anchor(8.0, 'eyes')
    to_r = (eyes_r - face_c)
    to_r.z = 0
    to_r.normalize()
    sd = V((-to_r.y, to_r.x, 0.0))
    p0 = eyes_r - to_r * 31.0 + sd * 5.0 + V((0, 0, 3.4))
    p1 = eyes_r - to_r * 26.5 + sd * 4.4 + V((0, 0, 3.0))
    k2 = Cam("cam.nervous", 85, p0, eyes_r + V((0, 0, -0.4)), fstop=8.0, focus=eyes_r, coll=cams)
    k2.key(7.0, loc=p0, target=eyes_r + V((0, 0, -0.4)), interp="LINEAR")
    k2.key(9.4, loc=p1, target=eyes_r + V((0, 0, -0.2)), interp="LINEAR")
    # T3a maze wide
    k3 = Cam('cam.maze', 35, (0.0, -80.0, 19.0), (4.0, -24.0, 15.5), fstop=11.0, focus=mz.point(su(12.0)), coll=cams)
    k3.key(9.3, loc=(0.0, -80.0, 19.0), target=(4.0, -24.0, 15.5), focus=mz.point(su(10.0)), interp='LINEAR')
    k3.key(10.2, loc=(3.0, -75.5, 19.5), target=(5.0, -24.0, 15.8), focus=mz.point(su(15.0)), interp='LINEAR')
    # T3b crest close-up
    pc = mz.point(s_lip)
    k4 = Cam('cam.crest', 28, pc + V((8.5, -22.0, 6.0)), pc + V((2.0, 0.0, 1.6)), fstop=8.0,
             focus=pc + V((-0.5, -2.2, 5.5)), coll=cams)
    k4.key(10.1, loc=pc + V((8.5, -22.0, 6.0)), target=pc + V((2.0, 0.0, 1.6)), interp='LINEAR')
    k4.key(10.7, loc=pc + V((7.6, -19.5, 6.6)), target=pc + V((2.4, 0.0, 0.6)), interp='LINEAR')
    # T3c the plunge, from low at the foot of the drop
    pb = mz.point(s_bot)
    k5 = Cam('cam.drop', 35, pb + V((10.0, -28.0, 1.5)), pb + V((-1.0, 0.0, 9.0)), fstop=8.0,
             focus=pb + V((-0.5, -2.0, 8.0)), coll=cams)
    k5.key(10.62, loc=pb + V((10.0, -28.0, 1.5)), target=pb + V((-1.0, 0.0, 13.5)), focus=pb + V((-0.5, -2.0, 13.0)))
    k5.key(10.95, target=pb + V((0.5, 0.0, 4.0)), focus=pb + V((0.5, -2.0, 4.5)))
    k5.key(11.55, loc=pb + V((13.0, -27.0, 1.8)), target=pb + V((9.0, 0.0, 4.0)), focus=mz.point(su(28.0)) + V((0, -2, 3)))
    # T3d the tail and the crash
    ph = mz.point(s_hit)
    k6 = Cam('cam.loss', 50, ph + V((-4.0, -34.0, 5.0)), ph + V((-2.0, 0.0, 2.5)), fstop=11.0,
             focus=ph + V((-2.5, -2.0, 3.5)), coll=cams)
    k6.key(11.5, loc=ph + V((-5.0, -34.0, 5.0)), target=ph + V((-3.5, 0.0, 2.8)))
    k6.key(12.1, loc=ph + V((-2.5, -32.0, 5.0)), target=ph + V((-1.5, 0.0, 2.8)))
    k6.key(13.0, loc=ph + V((-1.8, -30.5, 5.2)), target=ph + V((-1.0, 0.0, 3.0)))
    shake(k6.cam, t_loss - 0.02, t_loss + 0.35, amp=0.18, freq=16.0, seed=5)
    # T4a throne wide
    mid = V((mt.x - 5.0, mt.y - 0.5, 8.8))
    k7 = Cam('cam.throne', 35, mid + V((-1.5, -37.0, 2.6)), mid, fstop=8.0, focus=V((mt.x - 5.0, mt.y - 1.0, 8.0)),
             coll=cams)
    k7.key(12.9, loc=mid + V((-1.5, -37.0, 2.6)), target=mid, interp='LINEAR')
    k7.key(14.85, loc=mid + V((-0.8, -32.0, 2.3)), target=mid + V((0.4, 0.0, 0.3)), interp='LINEAR')
    # T4b over the researcher's shoulder, up at Clawd
    cf = c.anchor(15.3, 'face')
    cube_p = hand_up + V((0.0, 0.0, 0.5))
    aimb = cube_p.lerp(cf, 0.5)
    rface = r.anchor(14.9, 'eyes')
    aimb = rface.lerp(cube_p, 0.45) + V((0.0, 0.0, -0.4))
    # (revision 2: lower than it was, so the lyric stand in front of his knees sits on the focus plane)
    hz = V((0.62, -0.78, 0.0))
    ob0 = aimb + hz * 16.0 + V((0.0, 0.0, 7.6))
    ob1 = aimb + hz * 14.6 + V((0.0, 0.0, 7.0))
    k8 = Cam('cam.offer', 45, ob0, aimb, fstop=5.6, focus=cube_p, coll=cams)
    k8.key(14.7, loc=ob0, target=aimb, focus=cube_p, interp='LINEAR')
    k8.key(15.0, focus=cube_p)
    k8.key(15.3, focus=rface)
    k8.key(15.7, loc=ob1, target=aimb + V((0.2, 0, 0.2)), interp='LINEAR')
    # T4c boss: dolly zoom on Clawd's face
    fb = c.anchor(15.9, 'face')
    dirb = V((-0.45, -1.0, 0.18)).normalized()
    k9 = Cam('cam.boss', 40, fb + dirb * 15.5, fb + V((0, 0, 0.9)), fstop=8.0, focus=fb, coll=cams)
    k9.key(15.6, loc=fb + dirb * 15.5, lens=40.0, target=fb + V((0, 0, 0.9)), interp='LINEAR')
    k9.key(16.65, loc=fb + dirb * 42.6, lens=110.0, target=fb + V((0, 0, 0.9)), interp='LINEAR')
    for kk in (k9,):
        for fc in kit.fcurves(kk.cam.data):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'

    k1.cut(5.692)
    k2.cut(t_nerv)
    k3.cut(T3)
    k4.cut(t_sudden)
    k5.cut(t_drop)
    k6.cut(t_train)
    k7.cut(T4)
    k8.cut(T4b)
    k9.cut(t_boss)
    sc.camera = k1.cam
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()
    from pdoom import lyrics as ly
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(mz, s_of_t, T3, T4, T4b)


class _LetterTimes:
    """Reveal a word's letters at our own times (inside the word's sung span): patches lyrics.data.word for one
    ly.line() call."""

    def __init__(self, ly, line, word, times):
        self.ly, self.key, self.times = ly, (line, word), list(times)

    def __enter__(self):
        self.orig = self.ly.D.word
        orig, key, times = self.orig, self.key, self.times

        def word(i, j, **kw):
            w = orig(i, j, **kw)
            if (i, j) == key:
                for L, t in zip(w.letters, times):
                    L.t = t
            return w
        self.ly.D.word = word
        return self

    def __exit__(self, *a):
        self.ly.D.word = self.orig


def lyrics(mz, s_of_t, T3, T4, T4b):
    """Revision 2: every sung word in the picture (docs/lib/lyrics.md).

    T1-T2      lines 1-2 on the lyric stand
    T3a-T3d    line 3 on the stand, except DROP: bent in the bead maze's yellow enamel wire, stepping down beside
               the drop on little struts, one letter after another as Clawd plunges (10.66-10.84)
    T4a        "now I'm your servant" on the stand in front of the throne
    T4b-T4c    "and you're my boss" on a stand of its own; BOSS (red-painted blocks) drops from above and slams onto
               the shelf on "boss" as his eyes narrow
    """
    from pdoom import lyrics as ly
    from pdoom.lyrics import styles as LS
    # ---- DROP down the drop
    wire_m = bpy.data.materials.get('maze.wire.yellow')

    class EnamelWire(LS.Wire):
        def mat(self):
            return wire_m if wire_m is not None else super().mat()
    size = 2.5
    y_l = -26.9
    # the drop wire's x at a height (sampled from the ride path between the lip and the foot)
    L = mz.path.length
    samp = [mz.point(L * i / 600.0) for i in range(601)]
    drop_pts = [p for p in samp if 0.5 <= p.x <= 3.8 and 5.0 <= p.z <= 19.7]

    def wire_x(z):
        best = min(drop_pts, key=lambda p: abs(p.z - z))
        return best.x
    zb = [15.3, 12.3, 9.3, 6.3]                      # baselines of D R O P
    times = [10.66, 10.72, 10.78, 10.84]             # racing down just ahead of him
    with _LetterTimes(ly, 3, 4, times):
        dr = ly.line(3, words='drop', style=EnamelWire(radius=0.12, case='upper'),
                     place=ly.At((0.0, y_l, 0.0), face=(0, -1, 0), size=size), reveal='grow',
                     reveal_opts=dict(dur=0.12), exit='none', t_show=T3, t_end=T4 - 0.5 / FPS)
    struts = kit.collection('training.lyrics')
    for k, pc in enumerate(dr.pieces):
        z = zb[k]
        xr = wire_x(z + 0.5 * size) - 0.75                     # the letter's right edge, a gap from the wire
        xc = xr - pc.w * size * 0.5
        pc.obj.location = (xc / size, pc.obj.location.y, z / size)
        # a strut of the same wire from the letter to the drop
        x0, x1 = xr - 0.1, wire_x(z + 0.5 * size) - 0.2
        st = kit.cylinder(f'training.dropstrut{k}', 0.12, x1 - x0, (0, 0, 0), verts=12, m=wire_m, coll=struts)
        st.rotation_euler = (0.0, math.radians(90.0), 0.0)
        st.location = ((x0 + x1) / 2, y_l + 0.45, z + 0.5 * size)
        kit.visible(st, times[k] - 0.5 / FPS, T4 - 0.5 / FPS)
    # ---- line 4 in two halves, one stand each
    ly.line(4, words=(0, 4), place='auto', t_end=T4b, spec=ly.StageSpec(cells=21.5, rows=1))
    ly.accent(4, 'boss', 'blocks', color='#B8322A', reveal='slam')
    ly.line(4, words=(4, 8), place='auto', t_show=T4b,
            spec=ly.StageSpec(cells=19.5, rows=1, u=(0.42, 0.36, 0.5), v=(0.11, 0.075, 0.15, 0.2, 0.26)))
    ly.default('training')
