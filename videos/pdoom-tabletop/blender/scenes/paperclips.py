"""paperclips · 89.324-102.051 · "Gato, please don't let me go / I'm upping my P(doom), as paperclips fill the room /
Killswitch guy's on PTO / Now there's nowhere left to go". THE simulation showcase.

Shot list (song seconds; characters on twos, cameras / clips / seas smooth at 24 fps):

 G1 gato     89.324-90.640  70 mm at his eye level: revision 2 (the user: "gato please let me go should be claude
                            letting the scientist go"): Clawd, in cat ears and a red collar, sits on the edge of the
                            drawer cabinet like a cat on a fridge, the researcher dangling upside down by his ankles
                            from his teeth in front of the drawers; smug ^^ eyes, a slow sway, a purr-squash on each
                            beat; his bowl beside him says GATO. Slow push. Cut on "please".
 G2 please   90.640-92.460  45 mm, close on the researcher's upside-down face and clasped hands, Clawd above; a
                            PLEASE sticky note slaps onto the drawer beside him; a slow cat blink (91.62).
 G3 dont     92.460-95.470  40 mm, the cabinet front: DON'T LET and ME GO notes slap on as he kicks and begs; Clawd
                            narrows his eyes, teases with his lid, and on "go" (94.3) opens it: the researcher drops,
                            flips and lands on the desk; the drawer behind him rattles (94.76, 95.12), Clawd jolts on
                            top of it. Cut on "I'm".
 P1 pdoom    95.470-96.840  70 -> 82 mm push in on the brass gauge; DOOM 3 (96.596): the needle slams to 75 into the
                            red, the gauge jolts on its plinth, the camera shakes. Cut on "as".
 B1 burst    96.840-97.505  21 mm, low at the cabinet: the top drawer BURSTS open (96.84) and a geyser of real
                            rigid-body clips erupts at the lens, surging on the kick (97.115). Shake. Quick shutter.
 B2 wave     97.505-98.160  22 mm on the desk behind the pencil cup: the flood pours round it and the mug; the cup
                            tips toward the lens (97.68-97.99) and its pencils (real bodies) spill out at us as the
                            camera backs away. Cut on "the".
 B3 room     98.160-98.820  26 mm high wide: the flood covers the left of the desk and pours off its edge onto the
                            floor, still gushing from the drawer; the mug topples (98.25-98.62); the researcher backs
                            away, Clawd sits calmly on top of the cabinet. Cut on "Killswitch".
 K1 pto      98.820-100.721 38 mm, low: the big red kill switch and beside it the killswitch guy's empty vacation spot
                            (a striped deck chair with sunglasses on it, a beach umbrella, a cocktail with a paper
                            umbrella, flip-flops) in a warm "sun". A front of real clips rushes in from the left
                            ("guy's" 99.3); P (99.74) the umbrella keels over, T (99.96) the chair tips back and goes
                            under, O (100.262) the red button sinks under the rising clips. Slow truck and rise.
 F1 nowhere  100.721-102.051 26 mm, low front left, craning up: a sea of clips; the researcher balances, arms out,
                            on the overturned mug, his back to us; before him a mound of clips rises and lifts Clawd,
                            sitting calmly with a toothy grin, up into the re-aimed lamp's light. Near-zero shutter.

Lyrics in the picture: GATO painted on his bowl; "please", "don't let", "me go" on sticky notes slapped onto the
drawer fronts round the dangling researcher; "I'm upping my P(doom)" on the lyric stand (P(DOOM) slammed in brass);
AS | PAPERCLIPS typed on label strips on the paperclip drawer as it bursts open at the lens; FILL on blocks in the
flood's path (B2); "fill the room" and "Now there's nowhere left" on the stand; KILLSWITCH GUY'S ON PTO hand-written on an out-of-office card on a stake by
the kill switch, going under with it. ("to go" is sung in `fuse`.) In B1 and B3 Clawd sits up on the cabinet.

The flood: ~8,500 Bullet clips from the drawer and ~1,700 in the kill switch's wave are baked, then converted to one
geometry-node instancer (paperclips_flood.to_instances) so frames render fast; instanced seas (fx.clips.sea) do the
rising: over the desk from the drawer, round the kill switch, and the mound under Clawd.
"""
from __future__ import annotations

import math
import os
import time

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.fx import vis as fxvis
from pdoom.sets import build_desk, geo

from scenes.boot_common import Cam, shake
from scenes import paperclips_flood as FL
from scenes import paperclips_props as PP

FPS = tm.FPS
V = Vector

# ------------------------------------------------------------------------------------------------ times
T0, T_END = 89.324, 102.051
T = {
    'please': 90.64, 'dont': 92.46, 'let': 92.94, 'me': 93.32, 'go': 94.3, 'im': 95.47,
    'doom3': 96.596, 'burst': 96.84, 'as': 96.84, 'kick2': 97.115, 'beat_b2': 97.505, 'kick3': 97.536,
    'the': 98.16, 'room': 98.4, 'ks': 98.82, 'guys': 99.3, 'on': 99.6, 'P': 99.74, 'T': 99.96, 'O': 100.262,
    'final': 100.721, 'end': T_END,
}
T['wave'] = 99.28            # the kill switch's front of real clips leaves its (off-screen) mouth
T['ks_rise'] = 99.5          # the sea starts rising round the vacation spot
T['sea0'] = 97.35            # the desk-wide sea starts spreading from the drawer

# ------------------------------------------------------------------------------------------------ layout (world cm)
C0 = V((-1.2, -5.6, 0.0))            # Clawd (the Gato shots, then the mound)
F_C = V((0.898, -0.439, 0.0)).normalized()     # Clawd faces the G3 camera; the drawer cabinet is behind him
LEFT_C = V((-F_C.y, F_C.x, 0.0))              # his left
R0 = C0 + LEFT_C * 7.4               # the researcher, kneeling at his left side, facing him
YAW_C = math.degrees(math.atan2(F_C.x, -F_C.y))
_FR = (-LEFT_C + F_C * 0.55).normalized()     # he faces Clawd, turned a little toward the G3 camera
YAW_R = math.degrees(math.atan2(_FR.x, -_FR.y))
MUG0 = V((-30.0, -12.0, 0.0))        # the mug, in the flood's path (it topples in B3)
CUP0 = V((-36.0, -22.0, 0.0))        # the pencil cup, in the wave's path (B2's foreground)
CHAIR = V((47.5, -17.5, 0.0))        # the vacation spot, left of the kill switch (59, -15)
F1A = V((-30.0, -56.0, 6.0))         # the last shot's camera (the researcher turns his back to it)
UMB = V((42.0, -9.5, 0.0))
DRINK = V((53.0, -21.5, 0.0))


def _yaw_to(src, dst):
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    return math.degrees(math.atan2(dx, -dy))


def _poses():
    P = chars.POSES
    P['kneel_pet'] = dict(hips=(0, 0.35, -1.12), spine=(4, 0, 0), head=(20, 0, 0),
                          hands=((1.45, -1.7, 3.95), (-0.6, -3.0, 5.4)), wrist=((-20, 0, -80), (-15, 0, 0)),
                          thigh=((-88, 0, 0), (-4, 0, 0)), shin=(88, 90), face='happy')
    P['kneel_hug'] = dict(hips=(0, 0.35, -1.12), spine=(8, 0, 0), head=(22, 0, 0),
                          hands=((1.45, -1.7, 3.95), (-0.6, -3.0, 5.0)), wrist=((-20, 0, -80), (-15, 0, 0)),
                          thigh=((-88, 0, 0), (-4, 0, 0)), shin=(88, 90), face='happy')
    P['flail'] = dict(spine=(-10, 0, 0), head=(-12, 0, 0), hands=((2.3, -0.4, 9.8), (-2.3, -0.6, 10.1)),
                      wrist=((-170, 0, 0), (-170, 0, 0)), thigh=((-30, 0, 0), (20, 0, 0)), shin=(30, 10),
                      face='shock')
    P['flee'] = dict(hips=(0, 0.3, -0.1), spine=(-10, 0, 0), head=(4, 0, 0),
                     hands=((1.4, -2.2, 7.2), (-1.4, -2.2, 7.2)), wrist=((-110, 0, 0), (-110, 0, 0)),
                     thigh=((-10, 0, 0), (16, 0, 0)), shin=(10, 16), face='scared')


def build():
    t_build = time.time()
    sc = kit.new_scene('paperclips')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'books', 'cable'})
    A = d.anchors
    _poses()
    fxc = kit.collection('pc.fx')
    props = kit.collection('pc.props')
    lights = kit.collection('pc.lights')

    # ------------------------------------------------------------------ desk dressing for the flood
    if d.clip is not None:
        d.clip.hide()
    for o in (bpy.data.objects.get('mug.coffee'), bpy.data.objects.get('mug.crema')):
        if o is not None:
            bpy.data.objects.remove(o, do_unlink=True)          # he drank it (the mug gets knocked over)
    drawer_src = d.drawer.inside(0, 1.0)
    fall = (MUG0 - V((drawer_src.x, drawer_src.y, 0))).normalized()
    side = V((-fall.y, fall.x, 0.0))
    mr = d.mug.root
    mr.location = MUG0
    mr.rotation_euler = (0, 0, math.atan2(side.y, side.x) + math.pi)    # handle points sideways, away from us
    d.pencilcup.root.location = CUP0
    bpy.context.view_layer.update()
    # the pencil cup tips toward B2's camera when the wave hits it (97.72); the mug falls in B3
    cup_dir = V((0.6, -0.8, 0.0)).normalized()
    PP.tip(d.pencilcup.root, 97.68, 97.99, direction=cup_dir, pivot=CUP0 + cup_dir * 3.9, angle=92.0, bounce=4.0)
    mug_final = PP.tip(mr, 98.25, 98.62, direction=fall, pivot=MUG0 + fall * 4.25, angle=90.0, bounce=5.0,
                       slide=1.2)

    # ------------------------------------------------------------------ the kill switch guy's vacation spot
    chair = PP.beach_chair(props)
    chair.location = CHAIR
    chair.rotation_euler = (0, 0, math.radians(-14.0))
    shades = PP.sunglasses(props)
    umb = PP.umbrella(props)
    umb.location = UMB
    umb.rotation_euler = (math.radians(-7.0), math.radians(9.0), math.radians(20.0))
    drink = PP.cocktail(props)
    drink.location = DRINK
    ff = PP.flipflops(props)
    ff.location = CHAIR + V((0.4, -5.2, 0.0))
    ff.rotation_euler = (0, 0, math.radians(-10.0))
    bpy.context.view_layer.update()
    shades.matrix_world = chair.matrix_world @ Matrix.Translation((0.3, -0.6, 0.95)) @ \
        Matrix.Rotation(math.radians(-8.0), 4, 'X') @ Matrix.Rotation(math.radians(24.0), 4, 'Z')
    kit.parent(shades, chair)
    # P: the umbrella keels over away from the wave; T: the chair is shoved and tips back; the drink goes over
    # (back and to the left, clear of the chair: the clips sweep its base right, so its top falls left)
    PP.tip(umb, T['P'] - 0.3, T['P'] + 0.12, direction=(-0.45, 0.89, 0), angle=78.0, bounce=4.0)
    PP.tip(chair, T['T'] - 0.22, T['T'] + 0.1, direction=(0.55, 0.8, 0), pivot=CHAIR + V((0.8, 2.2, 0)),
           angle=64.0, bounce=5.0, slide=1.5)
    PP.tip(drink, T['T'] - 0.1, T['T'] + 0.08, direction=(1, 0.2, 0), pivot=DRINK + V((0.65, 0.1, 0)),
           angle=90.0, bounce=6.0)

    # ------------------------------------------------------------------ the cabinet frame (revision 2 staging)
    CAB = d.drawer.root.matrix_world.copy()          # local: x right, y back, z up; its front face at y -13.03
    CR = CAB.to_3x3().normalized()
    cab_yaw = math.degrees(math.atan2(CR.col[0][1], CR.col[0][0]))

    def cw(x, y, z):
        return CAB @ V((x, y, z))

    # the cat's bowl on the cabinet top, beside him (GATO is written on it)
    bowl = PP.cat_bowl(props, cw(-7.2, -9.6, 17.72), cab_yaw)

    # ------------------------------------------------------------------ Clawd, the Gato: on top of the cabinet, the
    # researcher dangling upside down by his ankles from his teeth over the edge; he lets go on "go"
    C_TOP = cw(0.0, -12.3, 17.72)
    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=tuple(C_TOP), yaw=cab_yaw)
    c.wear(T0 - 1.0, 'cat_ears')
    col, ring_c = PP.collar(c, kit.collection('clawd'))
    c.eyes(T0 - 1.0, 'happy', glow=0.0)
    c.arms(T0 - 1.0, 'down', dur=0.0)
    c.no_gait(T0 - 1.0, T['go'] + 0.6)
    LEAN = 20.0
    c.T['body.rot'].set(T0 - 1.0, (LEAN, 0.0, 0.0), 0.0)
    per = tm.beat_period() * 2.0

    def env(x, t0, t1, a=0.3, b=0.25):
        return max(0.0, min(1.0, (x - t0) / a, (t1 - x) / b))
    # G1: smug, a slow sway on the half bar, a purr-squash on each beat
    c.T['body.rot'].add(T0 - 0.4, T['please'], lambda x: (
        0.0, 4.0 * math.sin(2 * math.pi * (x - T0) / per) * env(x, T0 - 0.4, T['please']), 0.0))
    for bt in tm.beats_between(T0, T['please']):
        c.squash(bt + 0.02, 0.04, 0.3)
    # G2 "please": he looks down at his catch, a slow cat blink
    c.eyes(T['please'] + 0.06, 'open')
    c.T['eyes.look'].set(T['please'] + 0.12, (0.0, -0.35), 0.12)
    c.blink(91.62, dur=0.42)
    # G3 "don't let me go": sly; teases with the lid; on "go" he opens it and lets him drop
    c.eyes(T['dont'] + 0.06, 'narrow')
    c.T['body.rot'].set(T['let'] + 0.1, (LEAN, 0.0, 9.0), 0.2)
    c.T['body.rot'].set(T['me'] + 0.1, (LEAN, 0.0, -7.0), 0.2)
    c.T['body.rot'].set(T['go'] - 0.04, (LEAN, 0.0, 0.0), 0.12)
    c.lid(93.6, 0.08, dur=0.08)
    c.lid(93.78, 0.0, dur=0.06)
    c.lid(T['go'], 0.62, dur=0.06)
    c.eyes(T['go'] + 0.04, 'happy')
    c.lid(T['go'] + 0.36, 0.0, dur=0.12)
    c.T['body.rot'].set(T['go'] + 0.4, (8.0, 0.0, 0.0), 0.25)
    c.T['eyes.look'].set(T['go'] + 0.1, (0.0, -0.4), 0.1)
    # the drawer under him rattles: he jolts, looks down, surprised
    for tr in (94.76, 95.12):
        c.squash(tr + 0.02, 0.14, 0.35)
    c.eyes(94.8, 'surprised')
    c.timing(T['go'] - 0.1, T['go'] + 0.5, 'ones')
    # off screen (P1) he shuffles back from the edge: in B1 the drawer bursts under him; in B3 he sits up there,
    # calm as a cat on a fridge, while the flood pours out below
    C_BACK = cw(0.0, -2.0, 17.72)
    c.place(T['im'] + 0.1, loc=tuple(C_BACK), yaw=cab_yaw)
    c.no_gait(T['im'], T['im'] + 0.3)
    c.T['body.rot'].set(T['im'] + 0.1, (0.0, 0.0, 0.0), 0.0)
    c.T['eyes.look'].set(T['im'] + 0.1, (0.0, 0.0), 0.0)
    c.eyes(T['im'] + 0.1, 'open')
    c.hop(T['burst'] + 0.03, 1.6, dur=0.26)
    c.eyes(T['burst'] + 0.04, 'star')
    c.eyes(T['kick2'] + 0.1, 'happy')

    # ------------------------------------------------------------------ the researcher, dangling (G1-G3)
    # a second rig, hung upside down by the ankles from an Empty at Clawd's teeth (it swings a little); on "go" the
    # Empty drops and flips him onto his bottom on the desk. The main rig takes over off screen for B3 and F1.
    GRIP = cw(0.0, -15.8, 20.25)        # far enough out that his coat and head clear the drawer pulls and labels
    hang = kit.empty('pc.hang', tuple(GRIP), kit.collection('researcher'), 'PLAIN_AXES', 1.0)
    hang.rotation_mode = 'XYZ'
    rh = chars.Researcher(kit.collection('researcher.hang'), name='researcher.hang', loc=(0.0, 0.0, -0.45), yaw=0.0)
    rh.rig.parent = hang
    rh.rig.matrix_parent_inverse = Matrix.Identity(4)
    P = chars.POSES
    P['hang_dangle'] = dict(spine=(0, 0, 0), head=(-18, 0, 0), hands=((1.3, -0.9, 9.3), (-1.3, -0.9, 9.3)),
                            wrist=((-170, 0, 0), (-170, 0, 0)), thigh=((0, 0, 0), (0, 0, 0)), shin=(0, 0),
                            face='scared')
    P['hang_plead'] = dict(spine=(6, 0, 0), head=(-26, 0, 0), hands=((0.35, -2.25, 6.6), (-0.35, -2.25, 6.6)),
                           wrist=((-80, 0, 40), (-80, 0, -40)), thigh=((0, 0, 0), (0, 0, 0)), shin=(0, 0),
                           face='sad')
    P['hang_kick'] = dict(spine=(-6, 0, 0), head=(-20, 0, 0), hands=((2.0, -0.4, 8.6), (-2.0, -0.4, 8.6)),
                          wrist=((-160, 0, 0), (-160, 0, 0)), thigh=((0, 0, 0), (-28, 0, 0)), shin=(0, 40),
                          face='scared')
    rh.pose(T0 - 1.0, 'hang_dangle', dur=0.0)
    rh.face(T0 - 1.0, 'scared')
    rh.pose(T['please'] - 0.12, 'hang_plead', dur=0.2)
    rh.face(T['please'], 'sad')
    rh.nod(T['please'] + 0.3, n=2, amount=7.0, every=0.35)
    rh.pose(T['dont'], 'hang_kick', dur=0.12)
    rh.face(T['dont'], 'scared')
    rh.pose(T['let'], 'hang_plead', dur=0.12)
    rh.pose(T['me'], 'hang_kick', dur=0.1)
    rh.pose(93.8, 'hang_plead', dur=0.15)
    rh.face(93.8, 'sad')
    rh.T['head'].add(T0 - 0.5, T['go'], lambda x: (0.0, 0.0, 10.0 * math.sin(2 * math.pi * (x - T0) / 1.6)))
    # the fall: flailing, a half flip, he lands on his bottom (the 'sit' pose puts his seat on the desk)
    t_fall0, t_land = T['go'] + 0.03, T['go'] + 0.25
    rh.pose(t_fall0, 'flail', dur=0.04)
    rh.face(t_fall0, 'shock')
    rh.T['root.loc'].set(t_land, (0.0, 0.0, 0.0), t_land - t_fall0)
    rh.pose(t_land, 'gasp', dur=0.02)
    rh.face(t_land, 'wince')
    rh.timing(t_fall0 - 0.05, t_land + 0.1, 'ones')
    # the drawer behind him rattles: he twists round to it, then scoots away on his bottom
    rh.T['head'].set(94.84, (-6.0, 0.0, 70.0), 0.1)
    rh.face(94.8, 'shock')
    rh.pose(95.08, 'back_away', dur=0.14, face=False)
    rh.move(95.1, 95.45, [(0.0, -4.5, 0.0)], face='keep', gait=True)
    rh.visible(None, T['im'] + 1.0 / FPS)          # gone just after the cut to P1 (the gauge close-up can't see him)
    # the hang Empty: at the teeth with a lazy swing (on twos at 24 fps, like the puppets; every output frame when
    # tm.SMOOTH), then the fall and the flip. The swing tilts him OUT from the drawers (a negative turn about the
    # cabinet's X), never into them, and fades out over the fall so the drop starts from where the swing left him.
    LAND = cw(0.0, -17.2, 0.0)
    Rcab = CAB.to_quaternion().to_matrix().to_4x4()

    def swing(ts):
        sw = 6.0 + 3.5 * math.sin(2 * math.pi * (ts - T0) / 1.9) + 2.0 * math.sin(2 * math.pi * (ts - T0) / 0.61)
        # each kick snaps up over ~0.05 s, then dies away (no one-frame jump)
        kick = sum(14.0 * (1.0 - math.exp(-(ts - k) * 40.0)) * math.exp(-(ts - k) * 6.0)
                   for k in (T['dont'], T['me']) if ts >= k)
        return sw + kick

    def hang_mx(t):
        if t < t_fall0:
            return Matrix.Translation(GRIP) @ Rcab @ Matrix.Rotation(math.radians(-swing(t)), 4, 'X') @ \
                Matrix.Rotation(math.radians(180.0), 4, 'Y')
        u = min(1.0, (t - t_fall0) / (t_land - t_fall0))
        p = GRIP.lerp(LAND, u * u)
        return Matrix.Translation(p) @ Rcab @ Matrix.Rotation(math.radians(-swing(t_fall0) * (1.0 - u)), 4, 'X') @ \
            Matrix.Rotation(math.radians(180.0 + 180.0 * min(1.0, u * 1.25)), 4, 'Y')

    f0 = int(T0 * FPS) - 2
    f0 -= f0 % 2
    f_end = int((T['im'] + 0.1) * FPS) + 2
    if tm.SMOOTH:
        samples = [(fk, fk / FPS) for fk in tm.out_frames(f0, f_end)]
    else:
        samples = []
        for f in range(f0, f_end):
            if f / FPS < t_fall0:
                if f % 2:
                    continue
                samples.append((f - 0.5, (f + 1) / FPS))
            else:
                samples.append((f - 0.5, f / FPS))
    hang.rotation_mode = 'QUATERNION'
    prev = None
    for fk, t in samples:
        loc, q, _ = hang_mx(t).decompose()
        if prev is not None and prev.dot(q) < 0:
            q.negate()                 # sign continuity: the 180 -> 360 flip interpolates the short way each step
        prev = q
        hang.location = loc
        hang.rotation_quaternion = q
        hang.keyframe_insert('location', frame=fk)
        hang.keyframe_insert('rotation_quaternion', frame=fk)
    for fc in kit.fcurves(hang):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR' if tm.SMOOTH else 'CONSTANT'

    # the main researcher: off screen until B3 (he fled the drawer)
    r = chars.Researcher(kit.collection('researcher'), name='researcher', loc=(R0.x, R0.y, 0.0), yaw=YAW_R)
    r.visible(T['the'] - 0.3 - 0.5 / FPS)

    # ------------------------------------------------------------------ B3: the flood reaches them
    t_b3 = T['the'] - 0.3
    r.place(t_b3, loc=(R0.x + 3.5, R0.y - 3.0), yaw=_yaw_to(R0, drawer_src) + 25.0)
    r.pose(t_b3, 'flee', dur=0.0)
    r.look(t_b3 + 0.05, drawer_src + V((0, 0, 10)), dur=0.0)
    r.move(T['the'] + 0.12, T['ks'], [(R0.x + 8.0, R0.y - 5.0)], face='keep', ease='inout')
    r.pose(T['room'], 'back_away', dur=0.2)
    c.place(t_b3, loc=tuple(C_BACK), yaw=cab_yaw - 25.0)           # still up on the cabinet, calm
    c.eyes(t_b3, 'happy')
    c.T['eyes.look'].set(t_b3, (0.0, 0.0), 0.0)
    c.T['body.rot'].set(t_b3, (0.0, 0.0, 0.0), 0.0)
    c.arms(t_b3, 'rest', dur=0.0)
    for i in range(8):
        c.T[f'leg{i}'].set(t_b3, (0.0, (-30.0 if i % 2 else 30.0), 0.0), 0.0)
    c.T['hips.loc'].set(t_b3, (0.0, 0.0, -0.45), 0.0)

    # ------------------------------------------------------------------ F1: on the mug; on the mound
    tf = tm.t2f(T['final']) / FPS - 0.25 / FPS
    # the standing line on top of the fallen mug
    top = None
    for k in range(48):
        a = 2 * math.pi * k / 48
        p = mug_final @ V((4.3 * math.cos(a), 4.3 * math.sin(a), 5.0))
        if top is None or p.z > top.z:
            top = p
    stand = top + V((0, 0, 0.02))
    peak = [(T['final'] - 0.1, 17.0), (T['final'] + 0.35, 21.5), (T['final'] + 0.8, 26.0), (T_END + 0.1, 29.5)]
    look_at = V((C0.x, C0.y, 26.0))
    r.timing(tf - 0.1, T_END + 0.2, 'ones')
    r.place(tf, loc=(stand.x, stand.y, stand.z), yaw=_yaw_to(F1A, stand) + 8.0)
    r.no_gait(tf - 0.1, T_END + 0.2)
    r.pose(tf, 'stand_on_mug', dur=0.0)
    r.face(tf, 'scared')
    r.look(tf + 0.02, look_at, dur=0.0)
    r.T['spine'].add(tf, T_END + 0.2, lambda x: (0.0, 5.0 * math.sin(2 * math.pi * (x - tf) / 0.62), 0.0))
    r.T['hips'].add(tf, T_END + 0.2, lambda x: (0.18 * math.sin(2 * math.pi * (x - tf) / 0.62 + 0.8), 0.0, 0.0))
    r.look(101.6, look_at + V((0, 0, 3.0)), dur=0.3)
    c.timing(tf - 0.1, T_END + 0.2, 'ones')
    c.no_gait(tf - 0.1, T_END + 0.2)
    sink = 1.1
    c.place(tf, loc=(C0.x, C0.y, peak[0][1] - sink), yaw=_yaw_to(C0, stand) - 10.0)
    for (tp, _), (t, z) in zip(peak[:-1], peak[1:]):
        c.T['root.loc'].set(t, (C0.x, C0.y, z - sink), t - max(tp, tf), 'linear')
    c.eyes(tf, 'happy')
    c.arms(tf, 'rest', dur=0.0)
    c.T['body.rot'].set(tf, (0.0, 0.0, 0.0), 0.0)
    c.lid(101.25, 0.18, dur=0.12)
    c.arms(101.2, 'think', side='R', dur=0.18)
    c.lid(101.5, 0.0, dur=0.1)
    c.lid(101.62, 0.16, dur=0.1)
    c.lid(101.78, 0.0, dur=0.1)
    c.arms(101.85, 'rest', side='R', dur=0.2)
    c.eyes(101.9, 'narrow')

    for o in d.pencilcup.objects + [o for pp in d.pencils for o in pp.objects]:
        if o.type == 'MESH':
            fxvis(o, None, T['final'] - 0.4 / FPS)

    # ------------------------------------------------------------------ the gauge, the drawer's warning, the burst
    d.gauge.jolt(T['doom3'], 3.5)
    dr0 = d.drawer.drawers[0]
    y0 = dr0['y0']
    for t, dy in ((94.70, 0.0), (94.76, -0.9), (94.82, 0.1), (94.88, -0.45), (94.95, 0.0),
                  (95.07, 0.0), (95.12, -1.2), (95.17, 0.12), (95.24, -0.4), (95.32, 0.0)):
        geo.keyp(dr0, 'location', t, y0 + dy, index=1, interp='LINEAR')
    d.drawer.burst(T['burst'])

    # ------------------------------------------------------------------ lights
    kit.spot('pc.drawer.key', (-30.0, -40.0, 62.0), (-50.0, -14.0, 3.0), power=6.5e5, angle_deg=52, blend=0.55,
                  radius=3.0, color=kit.PAL['glow'], coll=lights)
    rim = kit.spot('pc.drawer.rim', (-70.0, 34.0, 40.0), (-52.0, -10.0, 6.0), power=1.6e5, angle_deg=40, blend=0.6,
                   radius=2.0, color='#9DB8FF', coll=lights)
    rim.data.specular_factor = 1.4
    sun = kit.spot('pc.ks.sun', (72.0, -48.0, 58.0), (50.0, -14.0, 2.0), power=2.6e5, angle_deg=34, blend=0.5,
                   radius=2.5, color='#FFD58A', coll=lights)
    fill = kit.area('pc.ks.fill', (30.0, -70.0, 20.0), (50.0, -14.0, 4.0), power=2.4e4, size=30.0,
                    color='#FFE6C8', coll=lights)
    fill.data.specular_factor = 0.3
    for L, t_on, t_off, e in ((sun, T['ks'] - 0.5 / FPS, T['final'], 2.6e5), (fill, T['ks'] - 0.5 / FPS, T['final'],
                                                                              2.4e4)):
        geo.keyp(L.data, 'energy', T0 - 1.0, 0.0, interp='CONSTANT')
        geo.keyp(L.data, 'energy', t_on, e, interp='CONSTANT')
        geo.keyp(L.data, 'energy', t_off - 0.5 / FPS, 0.0, interp='CONSTANT')
    # F1: the lamp swings over the mound (a cut), a warm fill from the front
    lp = d.lamp
    lp.aim(T['final'] - 0.6 / FPS, A['lampPool'], interp='CONSTANT')
    lp.aim(T['final'] - 0.4 / FPS, V((C0.x, C0.y, 30.0)), reach=40.0, height=52.0, interp='CONSTANT')
    lp.intensity(T['final'] - 0.6 / FPS, 1.0, 'CONSTANT')
    lp.intensity(T['final'] - 0.4 / FPS, 0.32, 'CONSTANT')
    if d.room.motes is not None:
        fxvis(d.room.motes, None, T['final'] - 0.4 / FPS)
    bulb = bpy.data.objects.get('lamp.bulb')
    if bulb is not None:
        bulb.visible_camera = True
        bulb.keyframe_insert('visible_camera', frame=(T0 - 1.0) * FPS)
        bulb.visible_camera = False
        bulb.keyframe_insert('visible_camera', frame=(T['final'] - 0.4 / FPS) * FPS)
        for fc in kit.fcurves(bulb):
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    ff1 = kit.area('pc.final.fill', (-40.0, -70.0, 30.0), (-10.0, -12.0, 10.0), power=5.0e4, size=40.0,
                   color='#FFD9B0', coll=lights)
    ff1.data.specular_factor = 0.4
    geo.keyp(ff1.data, 'energy', T0 - 1.0, 0.0, interp='CONSTANT')
    geo.keyp(ff1.data, 'energy', T['final'] - 0.5 / FPS, 5.0e4, interp='CONSTANT')

    # ------------------------------------------------------------------ the flood
    sim = FL.mode()
    info = {}
    if sim != '0':
        win = FL.CacheWindow(T['burst'] - 0.5)
        from pdoom.fx import rigid
        rigid.world(substeps=30, iterations=12, preroll=1.0)
        extra = [chair, umb, drink]
        pencils = [o for pp in d.pencils for o in pp.objects if o.type == 'MESH']   # before they are unparented
        nc = FL.colliders(d, extra_passive=extra, pencil_release=97.6)
        heading = V((0.72, -0.69, 0.0)).normalized()
        jet = heading * math.cos(math.radians(54)) + V((0, 0, math.sin(math.radians(54))))
        surge = [(T['burst'] + 0.12, 1.4), (T['kick2'], 1.6), (T['kick3'], 1.3), (97.96, 1.0), (98.415, 1.1)]
        g, p = FL.drawer_flood(d, T, direction=jet, surge_hits=surge)
        w = FL.wave(T, source=((26.0, -16.0, 5.0), (20.0, 6.0)), direction=(1.0, 0.1, 0.26))
        tb = time.time()
        FL.bake_report(f'paperclips ({nc} colliders)')
        info['bake'] = time.time() - tb
        FL.to_instances([g, p, w], keyed=pencils, coll=kit.collection('flood.clips'))
        win.restore()
    # the seas (instanced; no bake)
    ks_box = bpy.data.objects.get('killswitch.box')
    # the fallen mug stays clear of the seas (its footprint where it lies at the end)
    mug_x = kit.box('pc.mug.footprint', (9.0, 9.0, 9.8), (0, 0, 0), coll=kit.collection('pc.colliders'))
    mug_x.matrix_world = mug_final @ Matrix.Translation((0, 0, 4.9))
    mug_x.hide_render = True
    mug_x.display_type = 'WIRE'
    bpy.context.view_layer.update()
    mound_keys = [(T['final'] - 0.35, 0.0), (T['final'] - 0.1, 17.0), (T['final'] + 0.35, 21.5),
                  (T['final'] + 0.8, 26.0), (T_END + 0.1, 29.5)]
    flood, ks, mound = FL.seas(T, A, exclude_ks=[ks_box] if ks_box else [], exclude_flood=[mug_x],
                               mound_center=C0, mound_keys=mound_keys,
                               exclude_mound=[mug_x], ks_origin=(57.0, -13.0, 0.0),
                               flood_origin=(drawer_src.x, drawer_src.y, 0.0))
    FL.mound_cap(C0, [(t, max(0.0, z - 2.4)) for t, z in mound_keys], kit.collection('sea.mound'))
    for s in (mound,):
        fxvis(s['object'], T['final'] - 0.4 / FPS, None)
    fxvis(bpy.data.objects['mound.cap'], T['final'] - 0.4 / FPS, None)
    if bpy.data.objects.get('mound.cap.core'):
        fxvis(bpy.data.objects['mound.cap.core'], T['final'] - 0.4 / FPS, None)

    # ------------------------------------------------------------------ cameras
    cams = kit.collection('pc.cams')
    # G1 the Gato: a little below, three-quarter: Clawd leaning over the cabinet's edge with the researcher dangling
    #    upside down from his teeth in front of the drawers; his bowl (GATO) beside him. Slow push.
    k1 = Cam('cam.gato', 70, cw(-7.0, -72.0, 21.5), cw(-1.5, -13.5, 17.0), fstop=11.0, focus=cw(0.0, -14.5, 16.0),
             coll=cams)
    k1.key(T0 - 0.1, loc=cw(-7.0, -72.0, 21.5), target=cw(-1.5, -13.5, 17.0), interp='LINEAR')
    k1.key(T['please'] + 0.1, loc=cw(-6.3, -65.0, 21.2), target=cw(-1.5, -13.5, 17.1), interp='LINEAR')
    # G2 "please": low and close on his upside-down pleading face and clasped hands, Clawd's face above; the PLEASE
    #    note on the drawer beside him
    k2 = Cam('cam.please', 45, cw(-12.0, -44.0, 17.0), cw(-3.0, -14.0, 15.4), fstop=11.0,
             focus=cw(-1.0, -15.0, 13.0), coll=cams)
    k2.key(T['please'] - 0.1, loc=cw(-12.0, -44.0, 17.0), target=cw(-3.0, -14.0, 15.4), interp='LINEAR')
    k2.key(T['dont'] + 0.1, loc=cw(-11.0, -40.0, 17.2), target=cw(-3.0, -14.0, 15.5), interp='LINEAR')
    # G3 "don't let me go": the whole cabinet front, the notes on its drawers, the drop onto the desk on "go", the
    #    drawer rattling behind him
    k3 = Cam('cam.dont', 40, cw(8.0, -57.0, 15.0), cw(-0.5, -13.0, 11.6), fstop=11.0, focus=cw(0.0, -15.5, 12.0),
             coll=cams)
    #    (framed high enough to keep Clawd's face and lid in shot: everything he does on "go" happens up there)
    k3.key(T['dont'] - 0.1, loc=cw(8.0, -61.0, 18.0), target=cw(-0.5, -13.0, 14.6), interp='LINEAR')
    k3.key(T['im'] + 0.1, loc=cw(7.5, -58.0, 17.0), target=cw(-0.5, -13.0, 13.6), interp='LINEAR')
    k3.key(T['go'], focus=cw(0.0, -15.5, 12.0))
    k3.key(T['go'] + 0.3, focus=cw(0.0, -16.5, 4.0))
    # P1 the gauge
    gc = A['gaugeCenter']
    k4 = Cam('cam.gauge', 70, d.gauge.front(52) + V((0, 0, -2.0)), gc, fstop=11.0, coll=cams)
    k4.key(T['im'] - 0.1, loc=d.gauge.front(52) + V((0, 0, -2.0)), target=gc + V((0, 0, -0.4)), lens=70,
           interp='LINEAR')
    k4.key(T['burst'] + 0.1, loc=d.gauge.front(30) + V((0, 0, -1.0)), target=gc, lens=82, interp='LINEAR')
    shake(k4.cam, T['doom3'] - 0.02, T['doom3'] + 0.3, amp=0.2, freq=15.0, seed=11)
    # B1 the burst: low, front right of the cabinet
    dface = A['drawerFace']
    b1a = dface + V((17.0, -46.0, -7.5))
    b1b = dface + V((15.5, -42.0, -7.0))
    k5 = Cam('cam.burst', 21, b1a, dface + V((6.0, -12.0, 6.0)), fstop=8.0, focus=dface + V((0, -10.0, 0)),
             coll=cams)
    k5.key(T['burst'] - 0.1, loc=b1a, target=dface + V((6.0, -12.0, 6.0)), interp='LINEAR')
    k5.key(T['beat_b2'] + 0.1, loc=b1b, target=dface + V((7.0, -13.0, 9.0)), interp='LINEAR')
    shake(k5.cam, T['burst'] - 0.02, T['burst'] + 0.35, amp=0.35, freq=16.0, seed=5)
    shake(k5.cam, T['kick2'] - 0.02, T['kick2'] + 0.25, amp=0.2, freq=16.0, seed=6)
    # B2 the wave: on the desk in the flood's path, backing away as it rolls in
    b2a = V((-22.0, -38.0, 1.6))
    b2b = V((-16.0, -40.5, 2.1))
    aim2 = V((-55.0, -6.0, 8.0))
    k6 = Cam('cam.wave', 22, b2a, aim2, fstop=5.6, focus=CUP0 + V((0, 0, 5)), coll=cams)
    k6.key(T['beat_b2'] - 0.1, loc=b2a, target=aim2, interp='LINEAR')
    k6.key(T['the'] + 0.1, loc=b2b, target=aim2 + V((3.0, -2.0, -2.0)), interp='LINEAR')
    shake(k6.cam, T['beat_b2'], T['the'] + 0.1, amp=0.12, freq=10.0, seed=7)
    # B3 the room: high wide
    b3a = V((14.0, -92.0, 64.0))
    b3b = V((10.0, -86.0, 70.0))
    k7 = Cam('cam.room', 26, b3a, V((-30.0, -6.0, 0.0)), fstop=11.0, focus=V((-24.0, -14.0, 2.0)), coll=cams)
    k7.key(T['the'] - 0.1, loc=b3a, target=V((-30.0, -6.0, 0.0)), interp='LINEAR')
    k7.key(T['ks'] + 0.1, loc=b3b, target=V((-28.0, -6.0, 0.0)), interp='LINEAR')
    # K1 the kill switch and the empty vacation spot
    ksp = V((52.0, -15.0, 4.0))
    k1a = ksp + V((-19.0, -42.0, 9.0))
    k1b = ksp + V((-17.0, -44.0, 13.5))
    k8 = Cam('cam.pto', 38, k1a, ksp, fstop=11.0, focus=CHAIR + V((2.0, 0, 3.0)), coll=cams)
    k8.key(T['ks'] - 0.1, loc=k1a, target=ksp, interp='LINEAR')
    k8.key(T['final'] + 0.1, loc=k1b, target=ksp + V((3.0, 0.0, 1.0)), interp='LINEAR')
    k8.key(T['T'], focus=CHAIR + V((2.0, 0, 3.0)))
    k8.key(T['O'] - 0.1, focus=A['killswitchTop'] + V((-4.0, -5.0, 0.0)))
    # F1 nowhere left to go: low front left, craning up
    f1a = F1A
    f1b = V((-28.5, -53.0, 12.5))
    tgt1 = V((-11.0, -8.0, 14.5))
    k9 = Cam('cam.nowhere', 26, f1a, tgt1, fstop=11.0, focus=stand + V((6.0, 6.0, 8.0)), coll=cams)
    k9.key(T['final'] - 0.1, loc=f1a, target=tgt1, interp='LINEAR')
    k9.key(T_END + 0.1, loc=f1b, target=tgt1 + V((0.0, 0.0, 5.5)), interp='LINEAR')   # his feet stay above the subtitles

    for k, t in ((k1, T0), (k2, T['please']), (k3, T['dont']), (k4, T['im']), (k5, T['burst']), (k6, T['beat_b2']),
                 (k7, T['the']), (k8, T['ks']), (k9, T['final'])):
        k.cut(t)
    sc.camera = k1.cam
    # a quicker shutter in the two close flood shots (clips at 1-2 m/s read as clips, not streaks)
    for t, v in ((T0 - 1.0, 0.5), (T['burst'] - 0.5 / FPS, 0.5), (T['burst'], 0.24), (T['the'] - 0.5 / FPS, 0.24),
                 (T['the'], 0.5)):
        sc.render.motion_blur_shutter = v
        sc.keyframe_insert('render.motion_blur_shutter', frame=t * FPS)
    # the last shot is all instanced seas settling (a few mm per frame) and puppets on ones: a near-zero shutter there
    # (EEVEE smears the big rising seas' instances under motion blur; use_motion_blur itself can't be keyed)
    for t, v in ((T['final'] - 0.5 / FPS, 0.5), (T['final'] - 0.4 / FPS, 0.02)):
        sc.render.motion_blur_shutter = v
        sc.keyframe_insert('render.motion_blur_shutter', frame=t * FPS)
    for fc in kit.fcurves(sc):
        if fc.data_path == 'render.motion_blur_shutter':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    if os.environ.get('PC_CAM') == 'top':               # debug: a top-down view of the whole desk for every frame
        dbg = Cam('cam.debug.top', 30, V((-5.0, -6.0, 240.0)), V((-5.0, -5.9, 0.0)), fstop=64.0, coll=cams)
        for mk in list(sc.timeline_markers):
            sc.timeline_markers.remove(mk)
        sc.camera = dbg.cam
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(d, bowl, {'wave': k6.cam})
    print(f'[run] paperclips: built in {time.time() - t_build:.1f}s (sim={sim}, bake={info.get("bake", 0):.1f}s)',
          flush=True)


def desk_spot(cam, t, u, v, z=0.0):
    """The point on the plane z (the desk) under frame position (u, v) of cam at song time t (logs its blur)."""
    from pdoom.lyrics import place as LP
    S = LP.cam_state(cam, t)
    r = S.ray(u, v)
    p = S.loc + r * ((z - S.loc.z) / r.z)
    print(f'[run] desk_spot {cam.name} t={t} ({u}, {v}) -> {tuple(round(x, 1) for x in p)}, '
          f'blur {S.blur_px(S.project(p)[2]):.1f} px', flush=True)
    return p


def best_spot(cam, t, avoid=(), u_rng=(0.5, 0.9), v_rng=(0.12, 0.4)):
    """The desk point with the least depth-of-field blur that shows inside the frame window (u_rng, v_rng) of cam
    at t, away from the `avoid` [(point, radius)] footprints."""
    from pdoom.lyrics import place as LP
    S = LP.cam_state(cam, t)
    best = None
    for i in range(-40, 41):
        for j in range(-40, 41):
            p = S.loc + V((i * 1.0, j * 1.0, 0.0))
            p.z = 0.0
            if any((V((p.x, p.y, 0)) - V((a.x, a.y, 0))).length < r for a, r in avoid):
                continue
            u, v, dep = S.project(p)
            if not (u_rng[0] <= u <= u_rng[1] and v_rng[0] <= v <= v_rng[1]) or dep < 6.0:
                continue
            b = S.blur_px(dep)
            if best is None or b < best[0]:
                best = (b, p.copy(), u, v)
    print(f'[run] best_spot {cam.name} t={t}: {tuple(round(x, 1) for x in best[1])} at ({best[2]:.2f}, {best[3]:.2f}),'
          f' blur {best[0]:.1f} px', flush=True)
    return best[1]


def lyrics(d, bowl, cams):
    """GATO painted on his bowl; "please", "don't let", "me go" on sticky notes slapped onto the drawer fronts
    round the dangling researcher; P(DOOM) slams in brass on the stand; AS | PAPERCLIPS typed on label strips on the
    paperclip drawer as it bursts open at the lens; FILL on blocks in the flood's path in B2; KILLSWITCH GUY'S ON PTO hand-written on an out-of-office card
    in front of the kill switch; the rest on the lyric stand."""
    from pdoom.lyrics import core as CORE
    ly.line(27, words='Gato', style='stamp', ink='#2C5AC8', reveal='appear', support='none',
            place=ly.on_object(bowl, (0.0, -PP.BOWL_R - 0.03, 0.42), (0, -1, 0), (0, 0, 1), size=0.72, lift=0.0),
            t_end=T['please'] + 0.1, window=(T0, T['please'] + 0.1))
    dr = d.drawer.drawers
    for words, k, x, z in (('please', 0, -6.6, 1.0), ("don't let", 0, 6.6, 1.0), ('me go', 1, 6.4, 2.6)):
        ly.line(27, words=words, style='marker', size=0.98,
                place=ly.on_object(dr[k], (x, -13.06, z), (0, -1, 0), (0, 0, 1), size=0.98, lift=0.0),
                t_end=T['im'], window=(T0, T['im']))
    ly.accent(28, 3, 'brass')
    ly.line(28, place=ly.Auto(v=(0.25, 0.3, 0.34)), t_exit=T['burst'] - 0.05,     # clear of the push-in's crop;
            window=(T0, T['burst']))                                             # P(DOOM) stays to the cut
    # AS | PAPERCLIPS typed on label strips either side of the paperclip drawer's pull and card holder, the whole
    # word struck at once (the drawer bursts open at the lens)
    CORE.REVEALS['typeword'] = lambda pc, t, **kw: CORE.reveal_type(pc, pc.word.start + 0.5 * pc.k_index / FPS)
    for w, x, sz in (('as', -6.2, 1.0), ('paperclips', 6.1, 0.72)):
        ly.line(29, words=w, style='typed', reveal='typeword', size=sz, case='upper',
                place=ly.on_object(dr[0], (x, -13.07, 1.55), (0, -1, 0), (0, 0, 1), size=sz, lift=0.0),
                exit='none', t_end=T['beat_b2'], window=(T0, T['beat_b2']))
    # "fill" in B2: blocks on the desk where the low camera looks (the flood pours round them); then B3's stand
    # shows the whole of "fill the room"
    S2 = cams['wave']
    p_fill = best_spot(S2, 97.95, avoid=[(CUP0, 4.8), (MUG0, 5.5)])
    bpy.context.scene.frame_set(int(97.9 * FPS))
    fr = S2.matrix_world.translation - p_fill
    fr.z = 0.0
    ly.line(29, words='fill', place=ly.At(tuple(p_fill), size=2.0, face=tuple(fr.normalized())),
            t_end=T['the'], window=(T['beat_b2'], T['the']))
    st = ly._state()
    st['claimed'].discard((29, 2))
    ly.line(29, words='fill the room', place='auto', window=(T['the'], T_END))
    ks = d.killswitch.root.matrix_world.translation
    card_at = ks + V((-2.5, -9.5, 8.4))
    face = (V((33.0, -57.0, 0.0)) - card_at)
    face.z = 0.0
    face.normalize()
    stake = kit.cylinder('pc.pto.stake', 0.14, 9.0, tuple(card_at + face * -0.25 - V((0, 0, 3.9))), verts=10,
                         m=PP.M.solid('pc.stake', '#C9A57A', rough=0.6), coll=kit.collection('pc.props'))
    base = kit.cylinder('pc.pto.base', 0.9, 0.3, tuple(V((card_at.x, card_at.y, 0.15)) + face * -0.25), verts=16,
                        m=PP.M.solid('pc.stake', '#C9A57A', rough=0.6), coll=kit.collection('pc.props'))
    for o in (stake, base):
        kit.visible(o, T['ks'] - 0.5 / FPS, T['final'] - 0.5 / FPS)
    ly.line(30, style='marker', support='paper', size=0.82, max_chars=16,
            place=ly.At(tuple(card_at), size=0.82, face=tuple(face.normalized()), tilt=-10.0),
            t_end=T['final'], window=(T0, T['final']))
    ly.default('paperclips')
