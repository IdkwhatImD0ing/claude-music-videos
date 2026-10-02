"""fuse · 102.051-109.323 · "Too late now, we lit the fuse / Orthogonality thesis blues" (and the stutter lead-in).

The race: the desk is buried in paperclips (paperclips ends with Clawd on the mound under the lamp). Revision 2: WE
lit the fuse, so the researcher does it: up on the mound top beside Clawd, he strikes a big kitchen match on the
matchbox Clawd holds out for him, and lights a fuse cord that runs over the edge and down the mound's front slope in
joined script: the cord itself reads "fuse", and its spark writes the word in fire as it is sung. Then it races
across the sea of clips to a big red firecracker. We cut away before it blows, into a smoky blues club on the desk: a
blue spotlight in haze, Clawd on a thread-spool stool where two rulers cross at right angles (the axes of the
orthogonality thesis), playing the blues on a tiny cherry-red guitar under a blue neon sign; the researcher slumps at
a pencil-cup bar with a whisky, listening. The stutter ("just", 109.37 in disobey) starts on a punch-in on Clawd.

Shots (song seconds; characters on twos, cameras / flame / fuse / sparks smooth at 24 fps):
 F1 102.051-102.507  low on the mound top: the researcher holds the big match up like a torch; beside him Clawd holds
                     the matchbox out at his side, grinning; he winds up (102.36). Cut on the clap.
 F2 102.507-103.200  macro at the matchbox's front end: the head scrapes along the striker and FLARES on the clap
                     (102.507): sparks, a flash, the flame blooms; he lifts it to his face ("late now"), the camera
                     rising with it to his face lit by the flame, Clawd's sly eyes beside.
 F3 103.200-103.720  low three-quarter at the mound's edge: "we": they look at each other, Clawd nods; "lit" (103.40)
                     he leans in and touches the flame to the fuse's end; it catches (103.44) with a burst.
 F4 103.720-104.778  "fuse": high in front of the mound: the cord runs over the edge and down the slope in script, it
                     reads "fuse", and the spark writes the word in fire (glowing ash behind it); the pair peer down
                     from the top.
 F5 104.778-105.460  from beside the firecracker, low, looking back: the spark races at us across the sea, the pair
                     tiny and lit on their mound behind.
 F6 105.460-105.960  close on the firecracker's fuse hole: the spark arrives (105.84) and fizzes into it; CUT before it
                     blows.
 B1 105.960-106.962  "Orthogonality": high three-quarter onto the club: two rulers crossed at right angles in a blue
                     spotlight and haze, Clawd strumming on the spool stool at the origin; the bar and tealight aside.
 B2 106.962-107.505  "thesis": low, front right, on Clawd strumming on the beat, eyes shut, head bobbing.
 B3 107.505-108.414  "blues": the researcher slumped at the bar, head on his mitten, whisky in hand, swaying; Clawd
                     soft behind in the blue light.
 B4 108.414-108.869  close, front right on Clawd: the last big strum, his strumming arm straight up.
 B5 108.869-109.323  punch-in on Clawd's face: he stops dead, his eyes snap open and narrow, a faint orange glow
                     (disobey opens on him and the stutter).
"""
from __future__ import annotations

import math
import time

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.fx import particles
from pdoom.fx import smoke
from pdoom.fx import vis as fxvis
from pdoom.sets import build_desk, geo

from scenes import fuse_props as FP
from scenes.boot_common import Cam, flash_light, key_mats, shake

FPS = tm.FPS
V = Vector

T0, T_END = 102.051, 109.323
T_CLAP = 102.507          # the snare: the match flares
T_LATE = 102.72           # "late": cut to his face in the flame
T_WIND = 102.36
T_WE, T_LIT, T_IGN = 103.20, 103.40, 103.44
T_FUSE = 103.72
T_WORD = 104.66           # the spark leaves the word's e
T_F5, T_F6 = 104.778, 105.46
T_ARRIVE = 105.84
T_CLUB = 105.96
T_THESIS, T_BLUES = 106.962, 107.505
T_B4, T_B5 = 108.414, 108.869

C0 = FP.C0
CLUB = V((8.0, -14.0, 0.0))
FC = V((55.5, -8.5, 0.0))          # the firecracker
MS = 0.55                          # match and matchbox scale (sized for the researcher's mittens)
C_YAW = -12.0                      # Clawd on the mound top
L_EFF = 0.45 + 6.05 * MS           # wrist -> match head (the stick sits 0.45 into the mitten)
BOX_L, BOX_W, BOX_H = 5.6 * MS, 3.6 * MS, 1.7 * MS
WORD_K = 4.0                       # the script's x-height (cm)


def _yaw_to(src, dst):
    return math.degrees(math.atan2(dst[0] - src[0], -(dst[1] - src[1])))


def _poses():
    P = chars.POSES
    P['slump_bar'] = dict(hips=(0.0, 0.1, -0.05), spine=(16, 5, 0), head=(4, -12, 0),
                          hands=((1.0, -2.2, 6.0), (-1.1, -1.6, 3.6)), wrist=((-70, 0, 30), (10, 0, 0)),
                          thigh=((-4, 2, 0), (6, -2, 0)), shin=(4, 8), face='sad')


def _slerp_dirs(keys, t):
    """Direction at t from [(t, dir)] keys: slerped with a smoothstep between neighbours."""
    if t <= keys[0][0]:
        return V(keys[0][1]).normalized()
    if t >= keys[-1][0]:
        return V(keys[-1][1]).normalized()
    for (ta, da), (tb, db) in zip(keys[:-1], keys[1:]):
        if ta <= t <= tb:
            u = (t - ta) / (tb - ta) if tb > ta else 1.0
            u = u * u * (3 - 2 * u)
            qa = V((0, 0, 1)).rotation_difference(V(da).normalized())
            qb = V((0, 0, 1)).rotation_difference(V(db).normalized())
            return (qa.slerp(qb, u) @ V((0, 0, 1))).normalized()
    return V(keys[-1][1]).normalized()


def build():
    t_build = time.time()
    sc = kit.new_scene('fuse')
    d = build_desk(kit.collection('desk'), mood='night',
                   exclude={'books', 'cable', 'clip', 'notes', 'pen', 'pencils', 'drawers', 'killswitch', 'mug',
                            'gauge', 'motes'})
    _poses()
    race = kit.collection('fuse.race')
    club = kit.collection('fuse.club')
    lights = kit.collection('fuse.lights')
    fc = kit.collection('fuse.fx')

    # ================================================================== the race
    surf, fld = FP.build_land(race)
    TOPZ = FP.height(C0.x, C0.y) + FP.TOP - 0.1

    # ------------------------------------------------------------------ the pair on the mound top
    # the researcher at the front left of the top, the fuse's end at the edge in front of him; Clawd on his left
    RS = V((C0.x - 4.0, C0.y - 3.0, TOPZ))
    a_ign = math.radians(-26.0)
    IGN = V((C0.x + 8.3 * math.sin(a_ign), C0.y - 8.3 * math.cos(a_ign), 0.0))
    IGN.z = FP.height(IGN.x, IGN.y) + 1.15
    CL = RS + V((7.6, -0.4, 0.0))
    Rc = Matrix.Rotation(math.radians(C_YAW), 4, 'Z')
    Mc = Matrix.Translation(CL) @ Rc

    def Wc(p):                      # Clawd space -> world (he faces local -Y)
        return Mc @ V(p)
    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=tuple(CL), yaw=C_YAW)
    c.visible(None, T_CLUB - 0.01)
    c.no_gait(T0 - 1.0, T_CLUB)
    c.eyes(T0 - 1.0, 'happy')
    HOLD = (40.0, 70.0, 0.0)
    c.arms(T0 - 1.0, HOLD, side='R', dur=0.0)
    c.arms(T0 - 1.0, (15.0, 25.0, 0.0), side='L', dur=0.0)
    c.arms(102.74, (18.0, 55.0, 0.0), side='R', dur=0.16)          # lowers the box once it's struck
    c.timing(T_WIND - 0.1, T_CLAP + 0.35, 'ones')
    c.timing(T_WE - 0.05, T_FUSE + 0.1, 'ones')

    # the matchbox: on its long edge, striker up, long axis along his forward; its inner face on his right paw
    mb = FP.matchbox(race)
    R_box = Rc @ Matrix.Rotation(math.radians(-90), 4, 'Z') @ Matrix.Rotation(math.radians(90), 4, 'X')
    box_off = Rc.to_3x3() @ V((-0.1, -BOX_L / 2 + 0.55, 0.0))

    def box_M(t):
        return Matrix.Translation(c.anchor(t, 'hand.R') + box_off) @ R_box @ Matrix.Scale(MS, 4)
    key_mats(mb, box_M, T0 - 0.3, T_CLUB, spans=[(T_WIND - 0.1, T_CLAP + 0.35, 'ones'), (T_WE - 0.05, T_FUSE + 0.1,
                                                                                         'ones')], scale=True)
    ax = (Rc.to_3x3() @ V((0.0, -1.0, 0.0))).normalized()           # along the box, out front

    def striker(t, s):
        """World point on the striker's top at s cm along the box from its centre (+ = out front)."""
        top_c = c.anchor(t, 'hand.R') + box_off + Rc.to_3x3() @ V((-BOX_H / 2, 0.0, BOX_W / 2))
        return top_c + ax * s

    # ------------------------------------------------------------------ the researcher: faces the box, then the fuse
    box_c = striker(T_CLAP, 0.0)
    R_YAW = _yaw_to(RS, box_c) - 10.0
    YAW_LIT = _yaw_to(RS, IGN)
    rr = chars.Researcher(kit.collection('researcher.race'), name='researcher.race', loc=tuple(RS), yaw=R_YAW)
    rr.visible(None, T_CLUB - 0.01)
    rr.no_gait(T0 - 1.0, T_CLUB)
    rr.timing(T_WIND - 0.1, T_CLAP + 0.35, 'ones')
    rr.timing(T_WE - 0.05, T_FUSE + 0.1, 'ones')
    rr.face(T0 - 1.0, 'determined')
    r_yaw_rad = math.radians(R_YAW)
    Rr = Matrix.Rotation(r_yaw_rad, 4, 'Z')

    def Wr(p, yaw=None):            # researcher body space (upright, facing -Y) -> world
        R = Rr if yaw is None else Matrix.Rotation(math.radians(yaw), 4, 'Z')
        return Matrix.Translation(RS) @ R @ V(p)
    print(f'[run] fuse: Clawd {tuple(round(x, 1) for x in CL)}, researcher {tuple(round(x, 1) for x in RS)} '
          f'yaw {R_YAW:.0f} (lit {YAW_LIT:.0f}), fuse end {(IGN - RS).xy.length:.1f} cm in front of him', flush=True)

    # the match head path: (t, head point, wrist guess); the direction is from the guess to the head and the wrist
    # target sits L_EFF back along it (so the head lands where it should)
    HR = 0.46 * MS * 0.9
    up = V((0, 0, 1))
    pa, pb = striker(102.41, -0.95) + up * HR, striker(T_CLAP, 1.2) + up * HR
    face_pt = Wr((-0.35, -3.3, 8.9))
    hk = []

    def hkey(t, head, wguess):
        dvec = (head - wguess).normalized()
        hk.append((t, head - dvec * L_EFF, dvec))
    torch_w = Wr((-1.75, -1.3, 8.4))
    hkey(T0 - 1.0, torch_w + (Rr.to_3x3() @ V((-0.12, -0.3, 0.95))).normalized() * L_EFF, torch_w)
    hkey(102.28, torch_w + (Rr.to_3x3() @ V((-0.12, -0.3, 0.95))).normalized() * L_EFF, torch_w)
    hkey(T_WIND, pa + up * 1.0 - ax * 0.4, Wr((-0.4, -2.2, 6.8)))
    hkey(102.41, pa, Wr((-0.5, -2.3, 6.5)))
    hkey(T_CLAP, pb, Wr((-0.9, -2.6, 6.3)))
    hkey(102.57, pb + up * 1.3 + ax * 0.2, Wr((-1.0, -2.5, 6.0)))
    hkey(102.84, face_pt, Wr((-0.9, -2.4, 5.3)))
    hkey(T_WE + 0.02, face_pt + V((0, 0, -0.2)), Wr((-0.9, -2.4, 5.1)))
    hkey(T_LIT, IGN + up * 0.3, Wr((-0.55, -2.6, 4.2), YAW_LIT))
    hkey(T_IGN + 0.08, IGN + up * 0.4, Wr((-0.55, -2.6, 4.3), YAW_LIT))
    hkey(103.66, Wr((-0.5, -4.0, 8.2), YAW_LIT), Wr((-0.8, -2.4, 4.9), YAW_LIT))
    hkey(T_CLUB, Wr((-0.5, -4.0, 8.2), YAW_LIT), Wr((-0.8, -2.4, 4.9), YAW_LIT))
    # body first (the hand targets are stored in body space): the turn and lean to the fuse, the looks
    rr.look(T0 - 0.9, Wr((0.0, -8.0, 9.0)), dur=0.0)
    rr.look(102.3, Wr((0.0, -7.9, 4.0)), dur=0.16)       # eyes down on the striker, face still 3/4 to F1
    rr.look(102.62, face_pt + V((0, 0, 1.0)), dur=0.14)
    rr.look(103.12, c.anchor(103.2, 'face') + V((0, 0, 3.0)), dur=0.3)   # an eased, smaller nod to Clawd on "we"
    rr.turn(T_LIT - 0.12, YAW_LIT, dur=0.16)
    rr.T['spine'].set(T_LIT - 0.02, (20.0, 0.0, 0.0), 0.16)
    rr.T['thigh.L'].set(T_LIT - 0.02, (-6.0, 0.0, 0.0), 0.16)
    rr.T['thigh.R'].set(T_LIT - 0.02, (10.0, 0.0, 0.0), 0.16)
    rr.look(T_LIT - 0.02, IGN, dur=0.12)
    rr.T['spine'].set(103.7, (4.0, 0.0, 0.0), 0.2)
    rr.T['thigh.L'].set(103.7, (0.0, 0.0, 0.0), 0.2)
    rr.T['thigh.R'].set(103.7, (0.0, 0.0, 0.0), 0.2)
    rr.glasses_glint(102.66, '#FFC27A', dur=0.4, strength=10.0)
    rr.face(102.7, 'determined')
    rr.face(103.12, 'happy')
    rr.face(T_IGN + 0.06, 'awe')
    rr.face(103.9, 'nervous')
    rr.hand(T0 - 1.0, 'L', Wr((1.9, -0.3, 3.6)), dur=0.0)
    # then the match hand: wrist targets from the head keys (the palm target sits 0.55 past the wrist)
    prev_t = None
    for t, wrist, dvec in hk:
        yaw_now = YAW_LIT if t >= T_LIT - 0.2 else R_YAW
        sh = Wr((-1.4, 0.0, 6.42), yaw_now)
        palm = wrist + (wrist - sh).normalized() * 0.55
        rr.hand(t, 'R', palm, dur=0.0 if prev_t is None else min(0.14, t - prev_t),
               wrist=(-60.0, 0.0, 0.0) if t < T_WIND else (-20.0, 0.0, 0.0))
        prev_t = t
    dir_keys = [(t, dvec) for t, wrist, dvec in hk]

    def head_at(t):
        return rr.anchor(t, 'hand.R') + _slerp_dirs(dir_keys, t) * L_EFF

    # the match, its flame and the strike
    match_root, (m_head, m_tip), m_char = FP.match(race)
    match_root.scale = (MS, MS, MS)

    def match_M(t):
        dvec = _slerp_dirs(dir_keys, t)
        base = rr.anchor(t, 'hand.R') + dvec * 0.45
        return Matrix.Translation(base) @ V((0, 0, 1)).rotation_difference(dvec).to_matrix().to_4x4()
    spans = [(T_WIND - 0.1, T_CLAP + 0.35, 'ones'), (T_WE - 0.05, T_FUSE + 0.1, 'ones')]
    key_mats(match_root, match_M, T0 - 0.2, T_CLUB, spans=spans)
    for o in (m_head, m_tip):
        fxvis(o, None, T_CLAP)
    fxvis(m_char, T_CLAP, T_CLUB)
    err = (head_at(T_CLAP) - pb).length, (head_at(102.41) - pa).length, (head_at(T_LIT) - IGN).length
    print(f'[run] fuse: match head off target by {err[0]:.2f} (clap) {err[1]:.2f} (strike) {err[2]:.2f} (fuse) cm',
          flush=True)

    flame = FP.flame_mesh('match.flame', race, h=1.45, r=0.27)

    def flame_size(t):
        if t < T_CLAP - 0.5 / FPS:
            return 0.0
        x = t - T_CLAP
        flare = 0.75 * math.exp(-x / 0.06)
        return min(2.2, 1.0 * (1 - math.exp(-x / 0.05)) + flare * (x < 0.35)) if t < T_CLUB else 0.0
    fl_light = kit.point('match.flame.light', (0, 0, 0), power=0.0, radius=0.35, color='#FFA040', coll=lights)
    FP.key_flame(flame, fl_light, lambda t: head_at(t) + V((0, 0, 0.08)), T_CLAP - 0.1, T_CLUB, seed=3,
                 size_of=flame_size, base_power=1100.0, lean_k=0.0035)
    fxvis(flame, T_CLAP - 0.5 / FPS, T_CLUB)
    particles.burst('match.flare', center=tuple(head_at(T_CLAP) + V((0, 0, 0.15))), t0=T_CLAP, count=45,
                    speed=(10.0, 45.0), direction=tuple(ax * 0.5 + V((0, 0, 0.8))), cone=70.0, drag=3.0,
                    life=(0.08, 0.3), size=0.012, streak=0.009, seed=7, coll=fc, floor=None, strength=5.0)
    m_flash = flash_light('match.flash', head_at(T_CLAP) + V((0, 0, 1.2)), T_CLAP, lights, power=2200.0,
                          color='#FFD08A', decay=0.06)
    if tm.SMOOTH:                   # 60 fps: no warm glow on F1's last frames; the flash starts on F2's first frame
        _light_on_at(m_flash, tm.switch_frame(T_CLAP * FPS - 0.5) - 0.1)

    # Clawd: sly at the flame, a nod with him on "we", surprised when the fuse catches, delighted as it writes
    c.look(T0 - 0.9, Wr((0.0, -1.0, 8.5)), turn=0.0, dur=0.0)
    c.look(102.32, pa, turn=0.0, dur=0.12)
    c.eyes(102.6, 'narrow')
    c.look(102.7, face_pt + V((0, 0, 0.6)), turn=0.0, dur=0.14)
    c.lid(102.86, 0.12, dur=0.12)
    c.lid(103.12, 0.0, dur=0.1)
    c.eyes(103.1, 'happy')
    c.look(103.1, rr.anchor(103.2, 'eyes'), turn=0.0, dur=0.12)
    c.T['body.rot'].set(T_WE + 0.02, (9.0, 0.0, 0.0), 0.08)        # the nod on "we"
    c.T['body.rot'].set(T_WE + 0.14, (0.0, 0.0, 0.0), 0.08)
    c.look(T_LIT - 0.04, IGN, turn=0.0, dur=0.14)
    c.eyes(T_IGN + 0.04, 'surprised')

    # ------------------------------------------------------------------ the fuse: over the edge and down the slope in script
    # the camera the script is written for (F4), and the word projected from it onto the slope
    B = V((C0.x - 3.0, C0.y - 16.5, 0.0))
    B.z = FP.height(B.x, B.y) + 1.15
    f4_loc = B + V((1.5, -37.0, 25.0))
    f4_tgt = B + V((0.0, 4.0, 8.6))
    fwd = (f4_tgt - f4_loc).normalized()
    rgt = fwd.cross(V((0, 0, 1))).normalized()
    upv = rgt.cross(fwd).normalized()
    script, script_end = (FP.CURSIVE_FUSE, FP.WORD_END) if ly.ENABLED else (FP.SNAKE, FP.SNAKE_END)   # revision 3
    pts2d = FP.catmull2(script, 8)
    uc = 1.9
    base = V(B)
    for _ in range(4):              # slide the word so the f's crook starts just below the fuse end (1.4 cm down)
        p1 = FP.project_word([(script[0][0] - uc, script[0][1])], f4_loc, base, rgt, upv, WORD_K)[0]
        want = IGN + (V((IGN.x - C0.x, IGN.y - C0.y, 0.0)).normalized() * 1.9)
        dlt = want - p1
        base += rgt * dlt.dot(rgt) + upv * (dlt.z * 1.2)
    word = FP.project_word([(u - uc, v) for u, v in pts2d], f4_loc, base, rgt, upv, WORD_K)
    n_word = script_end * 8 + 1
    word_pts, exit_pts = word[:n_word], word[n_word:]
    # the lead-in: from the fuse's end on the top, over the edge, into the crook
    lead = []
    a, b_ = IGN, word_pts[0]
    for k in range(1, 6):
        u = k / 6
        q = a.lerp(b_, u)
        q.z = max(FP.height(q.x, q.y) + 1.15, a.z + (b_.z - a.z) * u)
        lead.append(q)
    # then away to the right, down to the sea and across it to the firecracker
    fc_root, hole_local = FP.firecracker(race)
    fz = FP.height(FC.x, FC.y) - 1.2
    ee = (exit_pts or word_pts)[-1]
    tail2d = [(ee.x, ee.y), (ee.x + 5.0, ee.y - 3.0), (16.5, -19.0), (24.0, -15.0), (31.0, -13.0), (38.0, -17.5),
              (45.0, -15.5), (50.0, -12.8)]
    last_dir = V((FC.x - tail2d[-1][0], FC.y - tail2d[-1][1], 0.0)).normalized()
    yaw_fc = math.atan2(-last_dir.x, last_dir.y)          # its front (-Y) faces the approaching cord
    fc_root.matrix_world = (Matrix.Translation((FC.x, FC.y, fz)) @ Matrix.Rotation(yaw_fc, 4, 'Z') @
                            Matrix.Rotation(math.radians(3.0), 4, 'X'))
    bpy.context.view_layer.update()
    hole = fc_root.matrix_world @ (hole_local + V((0, -0.35, 0)))
    tail = FP.lay_path(tail2d, end=hole)
    h_lit = head_at(T_LIT)
    cord0 = V((h_lit.x, h_lit.y, max(IGN.z, h_lit.z - 0.3)))
    pts = [cord0, IGN.lerp(cord0, 0.35) + V((0, 0, -0.1)), IGN] + lead + word_pts + exit_pts + tail[1:]
    # drop near-duplicates
    clean = [pts[0]]
    for p in pts[1:]:
        if (p - clean[-1]).length > 0.05:
            clean.append(p)
    pts = clean
    L_lead = FP.polyline_length(pts[:3] + lead + word_pts[:1])
    L_word = FP.polyline_length(pts[:3] + lead + word_pts)
    total = FP.polyline_length(pts)
    s_of = FP.profile_keys([(T_IGN, 0.0), (T_IGN + 0.14, 0.35), (T_FUSE - 0.02, L_lead * 0.85),
                            (T_FUSE + 0.12, L_lead + 5.0), (T_WORD, L_word), (T_ARRIVE, total)])
    print(f'[run] fuse: cord {total:.0f} cm (lead-in {L_lead:.1f}, word {L_word - L_lead:.0f} cm, '
          f'{(L_word - L_lead) / (T_WORD - T_FUSE - 0.12):.0f} cm/s; then {(total - L_word) / (T_ARRIVE - T_WORD):.0f} '
          f'cm/s)', flush=True)
    fu = FP.burn('fuse', pts, t_ign=T_IGN, t_end=T_ARRIVE, coll=kit.collection('fuse.cord'), seed=5, s_of=s_of,
                 glow_len=70.0, radius=0.26)
    c.look(T_FUSE + 0.12, fu['at'](fu['s'](103.95))[0], turn=0.0, dur=0.15)
    c.eyes(T_FUSE + 0.1, 'happy')
    c.look(104.3, fu['at'](fu['s'](104.5))[0], turn=0.0, dur=0.2)
    rr.look(T_FUSE + 0.1, fu['at'](fu['s'](103.95))[0], dur=0.15)
    rr.look(104.3, fu['at'](fu['s'](104.5))[0], dur=0.2)
    particles.burst('fuse.catch', center=tuple(IGN + V((0, 0, 0.3))), t0=T_IGN, count=90, speed=(15.0, 70.0),
                    direction=(0, 0, 1), cone=75.0, drag=2.4, life=(0.15, 0.55), size=0.03, seed=11, coll=fc,
                    floor=IGN.z - 0.9)
    particles.burst('fuse.arrive', center=tuple(hole + V((0, 0, 0.2))), t0=T_ARRIVE, count=110, speed=(25.0, 110.0),
                    direction=tuple(V(((hole - fc_root.matrix_world.translation).x,
                                       (hole - fc_root.matrix_world.translation).y, 0.0)).normalized() +
                                    V((0, 0, 0.6))),
                    cone=70.0, drag=2.5, life=(0.1, 0.4), size=0.026, emit=0.12, seed=13, coll=fc, floor=fz,
                    strength=6.0)
    a_flash = flash_light('fuse.arrive.flash', hole + V((0, -1.5, 1.0)), T_ARRIVE, lights, power=6000.0,
                          color='#FFB060', decay=0.2)
    f_club = T_CLUB * FPS - 0.5
    _light_off_at(a_flash, tm.switch_frame(f_club) if tm.SMOOTH else f_club)   # no glint on the club's desk
    word_c = sum(word_pts, V((0, 0, 0))) / len(word_pts)

    # ================================================================== the club
    rx, ry, rz = FP.rulers(club, CLUB, rot_deg=0.0)
    sp_root, sp_h = FP.spool(club, CLUB + V((0, 0, rz)))
    zs = rz + sp_h
    cc = chars.Clawd(kit.collection('clawd.club'), name='clawd.club', loc=(CLUB.x, CLUB.y, zs), yaw=12.0)
    cc.visible(T_CLUB - 0.01, None)
    cc.no_gait(T0 - 1.0, T_END + 1.0)
    cc.eyes(T0 - 1.0, 'shut')
    cc.T['hips.loc'].set(T0 - 1.0, (0.0, 0.0, -0.4), 0.0)
    for i in range(8):              # every leg splayed outward (clear of the spool's top)
        cc.T[f'leg{i}'].set(T0 - 1.0, (0.0, 26.0 if chars.clawd.LEG_XY[i][0] < 0 else -26.0, 0.0), 0.0)
    gt = FP.guitar(club, 'club.guitar')
    # the neck runs just clear of his face and past his left side, over the stub (which reaches only 1.4 cm forward)
    cc.attach(gt, 'body', offset=(-2.4, -2.9, 1.0), rot=(0.0, -11.0, 4.0))
    # arms: left on the neck, right strumming on the beat (down through the strings ON the beat, up off it)
    cc.arms(T0 - 1.0, (20.0, 88.0, 0.0), side='L', dur=0.0)
    cc.arms(T0 - 1.0, (-8.0, 78.0, 0.0), side='R', dur=0.0)
    per = tm.beat_period()
    t_stop = T_B5 + 0.02
    beats = tm.beats_between(T_CLUB - per, t_stop)

    def env(x, a, b, ra=0.1, rb=0.06):
        return max(0.0, min(1.0, (x - a) / ra, (b - x) / rb))
    b0 = beats[0]
    cc.T['arm.R'].add(T_CLUB - 0.3, t_stop, lambda x: (-16.0 * math.sin(2 * math.pi * (x - b0) / per) *
                                                       env(x, T_CLUB - 0.3, t_stop), 0.0, 0.0))
    cc.T['arm.L'].add(T_CLUB - 0.3, t_stop, lambda x: (3.0 * math.sin(4 * math.pi * (x - b0) / per) *
                                                       env(x, T_CLUB - 0.3, t_stop), 0.0, 0.0))
    # head bob and a sway on the half bar
    cc.T['body.rot'].add(T_CLUB - 0.3, t_stop, lambda x: (
        5.0 * max(0.0, math.cos(2 * math.pi * (x - b0) / per)) ** 2 * env(x, T_CLUB - 0.3, t_stop),
        4.0 * math.sin(math.pi * (x - b0) / per) * env(x, T_CLUB - 0.3, t_stop), 0.0))
    cc.T['hips.loc'].add(T_CLUB - 0.3, t_stop, lambda x: (0.0, 0.0, -0.12 * max(0.0, math.cos(2 * math.pi * (x - b0)
                                                                                              / per)) ** 4))
    # he sings the blues a little (the lid on the sung syllables)
    for w_t, w_e, amt in ((105.96, 106.3, 0.22), (106.42, 106.9, 0.18), (T_THESIS, 107.3, 0.2), (T_BLUES, 108.3, 0.3)):
        cc.lid(w_t + 0.06, amt, dur=0.1)
        cc.lid(w_e, 0.0, dur=0.12)
    cc.eyes(T_BLUES + 0.2, 'happy')
    # B4: the last big strum, arm up high
    cc.arms(T_B4 + 0.12, (82.0, 10.0, 0.0), side='R', dur=0.1)     # straight up beside his right side
    cc.arms(T_B4 + 0.3, (-10.0, 80.0, 0.0), side='R', dur=0.1)
    # B5: he stops dead, eyes snap open, then narrow, a faint glow
    cc.timing(T_B5 - 0.05, T_END + 0.1, 'ones')
    cc.eyes(T_B5 + 0.06, 'open')
    cc.T['body.rot'].set(T_B5 + 0.08, (-4.0, 0.0, 0.0), 0.06)
    cc.eyes(109.1, 'narrow', glow=1.1, color='#FF5A00', dur=0.1)
    cc.T['eyes.look'].set(109.1, (0.0, -0.02), 0.08)

    # the bar, the whisky, the tealight
    D3 = V((0.75, 1.0, 0.0)).normalized()            # B3 looks along this, past him to Clawd
    rpos = CLUB - D3 * 14.5
    ryaw = math.degrees(math.atan2(-D3.x, D3.y)) + 8.0
    r_left = V((math.cos(math.radians(ryaw)), math.sin(math.radians(ryaw)), 0.0))
    r_fwd = V((math.sin(math.radians(ryaw)), -math.cos(math.radians(ryaw)), 0.0))
    bar_loc = rpos + r_left * 5.8 + r_fwd * 0.9      # the cup's wall clear of his coat
    bar, bar_h = FP.bar_cup(club, bar_loc, h=5.2, away=math.degrees(math.atan2(r_left.y, r_left.x)))
    tl_root, tl_flame = FP.tealight(club, bar_loc + (r_left * 3.4 + r_fwd * 1.2).normalized() * 5.4)
    tflame = FP.flame_mesh('club.tealight.flame', club, h=1.25, r=0.26, m=FP.flame_material('club.flame', strength=8.0,
                                                                                               height_cm=1.25))
    tl_light = kit.point('club.tealight.light', tuple(tl_flame), power=0.0, radius=0.3, color='#FF9A40', coll=lights)
    FP.key_flame(tflame, tl_light, lambda t: tl_flame, T_CLUB - 0.1, T_END + 0.1, seed=9, base_power=900.0)
    fxvis(tflame, T_CLUB - 0.5 / FPS, None)

    # the researcher at the bar, slumped, listening
    r = chars.Researcher(kit.collection('researcher'), name='researcher', loc=(rpos.x, rpos.y, 0.0), yaw=ryaw)
    r.visible(T_CLUB - 0.01, None)
    r.pose(T0 - 1.0, 'slump_bar', dur=0.0)
    r.hand(T0 - 0.9, 'L', bar_loc - r_left * 3.2 + r_fwd * 1.6 + V((0, 0, bar_h + 0.6)), dur=0.0,
           wrist=(-80.0, 0.0, 0.0))     # just outside the cup's rim, in front of him (the glass shows in B3)
    r.look(T0 - 0.8, rpos + r_left * 0.6 + r_fwd * 8.0 + V((0, 0, 7.6)), dur=0.0)
    glass = FP.whisky(club)
    r.attach(glass, 'hand.L', offset=(0.45, -0.2, -0.1), rot=(0.0, 0.0, 0.0))
    r.T['head'].add(T_CLUB, T_END + 0.2, lambda x: (3.0 * math.sin(2 * math.pi * (x - b0) / (2 * per)), 0.0,
                                                    5.0 * math.sin(2 * math.pi * (x - b0) / (4 * per))))
    r.T['spine'].add(T_CLUB, T_END + 0.2, lambda x: (0.0, 2.5 * math.sin(2 * math.pi * (x - b0) / (4 * per)), 0.0))
    r.face(T_BLUES + 0.3, 'blink')
    r.face(T_BLUES + 0.5, 'sad')

    # club visibility: the whole club appears on the cut, the race disappears
    club_objs = [o for o in club.objects if o.type == 'MESH']
    for o in club_objs:
        fxvis(o, T_CLUB - 0.5 / FPS, None)
    fxvis(glass, T_CLUB - 0.5 / FPS, None)
    for o in [ch for ch in geo.descendants(glass) if ch.type == 'MESH']:
        fxvis(o, T_CLUB - 0.5 / FPS, None)
    race_objs = [o for o in race.objects if o.type in ('MESH', 'CURVE')] + \
        [o for o in kit.collection('fuse.cord').objects if o.type == 'MESH'] + \
        [o for o in fc.objects if o.type == 'MESH']
    for o in race_objs:
        if o.name.startswith('match.flame'):
            continue
        _vis_off(o, T_CLUB - 0.5 / FPS)

    # ================================================================== lights
    # the race: paperclips' last look: the lamp swung over the mound, dimmed, its bulb out of view; a warm front fill
    lp = d.lamp
    lp.aim(T0 - 1.0, V((C0.x, C0.y, 30.0)), reach=40.0, height=52.0, interp='CONSTANT')
    lp.intensity(T0 - 1.0, 0.32, 'CONSTANT')
    lp.intensity(T_CLUB - 0.5 / FPS, 0.0, 'CONSTANT')
    bulb = bpy.data.objects.get('lamp.bulb')
    if bulb is not None:
        bulb.visible_camera = False
    for o in lp.objects:
        if o.type == 'MESH':
            fxvis(o, None, T_CLUB - 0.5 / FPS)
    if d.laptop is not None:
        for o in d.laptop.root.children_recursive:
            if o.type == 'MESH':
                fxvis(o, None, T_CLUB - 0.5 / FPS)
        d.laptop.screen(T0 - 1.0, glow=0.3)
        d.laptop.screen(T_CLUB - 0.5 / FPS, glow=0.0)
    ff = kit.area('fuse.front.fill', (-40.0, -70.0, 40.0), (-2.0, -8.0, 26.0), power=5.0e4, size=40.0,
                  color='#FFD9B0', coll=lights)
    ff.data.specular_factor = 0.4
    for L, e0 in ((ff.data, 5.0e4), (d.room.bounce.data, None), (d.room.moon.data, None)):
        e0 = e0 if e0 is not None else L.energy
        geo.keyp(L, 'energy', T0 - 1.0, e0, interp='CONSTANT')
        if L is d.room.bounce.data:
            geo.keyp(L, 'energy', T_FUSE - 0.5 / FPS, e0 * 0.35, interp='CONSTANT')
            geo.keyp(L, 'energy', T_CLUB - 0.5 / FPS, 6000.0, interp='CONSTANT')
        elif L is d.room.moon.data:
            geo.keyp(L, 'energy', T0 - 1.0, e0 * 0.7, interp='CONSTANT')
            geo.keyp(L, 'energy', T_CLUB - 0.5 / FPS, e0 * 0.3, interp='CONSTANT')
        else:
            geo.keyp(L, 'energy', T_FUSE - 0.5 / FPS, e0 * 0.25, interp='CONSTANT')
            geo.keyp(L, 'energy', T_CLUB - 0.5 / FPS, 0.0, interp='CONSTANT')
    # a red kiss on the firecracker so it reads far away
    fk = kit.spot('fuse.fc.key', tuple(FC + V((-22.0, -30.0, 30.0))), tuple(FC + V((0, 0, 8.0))), power=3.0e4,
                  angle_deg=18, blend=0.6, radius=2.0, color='#FFB38A', coll=lights)
    # the club: a blue spotlight from above, a violet rim from behind, the tealight at the bar
    spot = kit.spot('club.spot', tuple(CLUB + V((3.0, 9.0, 58.0))), tuple(CLUB + V((0, -2.0, 3.0))), power=8.0e5,
                    angle_deg=30, blend=0.45, radius=1.5, color='#4A74FF', coll=lights)
    cfill = kit.area('club.fill', tuple(CLUB + V((-10.0, -45.0, 25.0))), tuple(CLUB + V((0, 0, 5.0))), power=1.2e4,
                     size=30.0, color='#8FA8FF', coll=lights)
    cfill.data.specular_factor = 0.5
    rim = kit.spot('club.rim', tuple(CLUB + V((-18.0, 30.0, 22.0))), tuple(CLUB + V((0, 0, 7.0))), power=6.0e4,
                   angle_deg=25, blend=0.6, radius=2.0, color='#9A5CFF', coll=lights)
    for L, e in ((spot.data, 8.0e5), (rim.data, 6.0e4), (fk.data, 3.0e4), (cfill.data, 1.2e4)):
        if L is fk.data:
            geo.keyp(L, 'energy', T0 - 1.0, 0.0, interp='CONSTANT')
            geo.keyp(L, 'energy', T_FUSE - 0.5 / FPS, e, interp='CONSTANT')
            geo.keyp(L, 'energy', T_CLUB - 0.5 / FPS, 0.0, interp='CONSTANT')
        else:
            geo.keyp(L, 'energy', T0 - 1.0, 0.0, interp='CONSTANT')
            geo.keyp(L, 'energy', T_CLUB - 0.5 / FPS, e, interp='CONSTANT')
    haze = smoke.haze('club.haze', box=(tuple(CLUB + V((-40.0, -34.0, 0.0))), tuple(CLUB + V((40.0, 40.0, 62.0)))),
                      density=0.012, color='#B8C8FF', scale=9.0, drift=(2.0, 0.5, 1.4), contrast=2.2,
                      coll=kit.collection('fuse.club.haze'))
    fxvis(haze, T_CLUB - 0.5 / FPS, None)

    # ================================================================== cameras
    cams = kit.collection('fuse.cams')
    upz = V((0, 0, 1))
    # F1: low on the mound top: the researcher with the match up like a torch, Clawd holding the matchbox out
    mid = (RS + CL) / 2
    eyes1 = rr.anchor(102.2, 'eyes')
    f1a = mid + V((-9.0, -36.0, 3.5))
    f1b = mid + V((-8.4, -33.5, 3.3))
    tg1 = mid + V((-0.8, 0.0, 6.2))
    k1 = Cam('cam.F1', 50, f1a, tg1, fstop=8.0, focus=eyes1 + (CL - eyes1) * 0.3, coll=cams)
    k1.key(T0 - 0.1, loc=f1a, target=tg1, interp='LINEAR')
    k1.key(T_CLAP + 0.1, loc=f1b, target=tg1 + V((0, 0, -0.3)), interp='LINEAR')
    # F2: macro at the matchbox's front end: the head comes along the striker and flares, then up to his face
    side = V((-ax.y, ax.x, 0.0))
    if side.y > 0:
        side = -side
    f2a = pb + ax * 12.0 + side * 6.0 + upz * 1.6
    fwd_r = V((math.sin(r_yaw_rad), -math.cos(r_yaw_rad), 0.0))
    eyes2 = rr.anchor(102.9, 'eyes')
    f2b = eyes2 + fwd_r * 13.0 + side * 3.0 + upz * 0.6
    k2 = Cam('cam.F2', 70, f2a, pb, fstop=11.0, focus=pb, coll=cams)
    acc = None
    for t in [f / FPS for f in range(tm.t2f(T_CLAP) - 2, tm.t2f(T_LATE) + 3)]:
        h = head_at(t) + V((0, 0, 0.35 * flame_size(t)))
        acc = h if acc is None else acc.lerp(h, 0.4)
        u = tm.smooth(t, 102.58, 102.95)
        tgt = acc.lerp((eyes2 + face_pt) / 2, 0.55 * u)
        k2.key(t, target=tgt, focus=acc.lerp(eyes2, 0.7 * u), interp='LINEAR')
        k2.key(t, loc=f2a.lerp(f2b, u), lens=70 - 26 * u, interp='LINEAR')
    # F2b ("late now"): his face in the match light, Clawd's sly eye at the edge; a slow push
    tg2 = (eyes2 + face_pt) / 2 + V((0, 0, -1.3))
    f2c = eyes2 + fwd_r * 16.5 + side * 3.0 + upz * 0.4
    cf2 = (tg2 - f2c).normalized()
    tg2 = tg2 - cf2.cross(upz).normalized() * 2.6
    k2b = Cam('cam.F2b', 45, f2c, tg2, fstop=8.0, focus=eyes2.lerp(face_pt, 0.4), coll=cams)
    k2b.key(T_LATE - 0.1, loc=f2c, target=tg2, interp='LINEAR')
    k2b.key(T_WE + 0.1, loc=f2c + (tg2 - f2c) * 0.12, target=tg2 + V((0, 0, 0.2)), interp='LINEAR')
    # F3: low three-quarter at the mound's edge: "we" they look at each other, he lights the fuse, it catches
    f3a = IGN + V((-11.0, -22.0, 0.0))
    f3a.z = TOPZ + 8.0
    f3b = f3a + (IGN - f3a) * 0.1
    tg3 = IGN.lerp(mid, 0.45) + V((0, 0, 4.2))
    k3 = Cam('cam.F3', 35, f3a, tg3, fstop=8.0, focus=IGN.lerp(mid, 0.3), coll=cams)
    k3.key(T_WE - 0.1, loc=f3a, target=tg3, interp='LINEAR')
    k3.key(T_FUSE + 0.1, loc=f3b, target=tg3 + V((0, 0, -0.4)), interp='LINEAR')
    # F4: high in front of the mound: the cord reads "fuse" down the slope; the spark writes it in fire
    k4 = Cam('cam.F4', 35, f4_loc - fwd * 4.0, f4_tgt, fstop=11.0, focus=word_c, coll=cams)
    k4.key(T_FUSE - 0.1, loc=f4_loc - fwd * 4.0, target=f4_tgt, interp='LINEAR')
    k4.key(T_F5 + 0.1, loc=f4_loc + fwd * 3.0 + rgt * 1.5, target=f4_tgt + rgt * 1.2 + V((0, 0, -0.8)),
           interp='LINEAR')
    # F5: from beside the firecracker, low, looking back at the spark racing in
    f5a = FC + V((9.0, -9.0, 0.0))
    f5a.z = FP.height(f5a.x, f5a.y) + 5.5
    tg5 = V((14.0, -11.0, 19.0))
    k5 = Cam('cam.F5', 30, f5a, tg5, fstop=8.0, coll=cams)
    k5.key(T_F5 - 0.1, loc=f5a, target=tg5, interp='LINEAR')
    k5.key(T_F6 + 0.1, loc=f5a + V((-1.5, 0.5, -0.8)), target=tg5 + V((8.0, -1.0, 0.0)), interp='LINEAR')
    for t in [f / FPS for f in range(tm.t2f(T_F5) - 2, tm.t2f(T_F6) + 3)]:
        p, _ = fu['at'](fu['s'](t))
        k5.key(t, focus=p, interp='LINEAR')
    # F6: close on the fuse hole, the spark fizzing into it
    hp = hole
    out = (hole - fc_root.matrix_world.translation)
    out.z = 0
    out.normalize()
    side = V((-out.y, out.x, 0.0))
    f6a = hp + out * 17.0 - side * 12.0 + V((0, 0, 3.5))
    k6 = Cam('cam.F6', 40, f6a, hp + V((0, 0, 3.5)) + side * 1.5, fstop=8.0, focus=hp, coll=cams)
    k6.key(T_F6 - 0.1, loc=f6a, target=hp + V((0, 0, 3.5)) + side * 1.5, interp='LINEAR')
    k6.key(T_CLUB + 0.1, loc=f6a + (hp - f6a) * 0.25, target=hp + V((0, 0, 2.5)) + side * 0.5, interp='LINEAR')
    shake(k6.cam, T_ARRIVE - 0.02, T_CLUB + 0.1, amp=0.08, freq=16.0, seed=6)
    # B1: high three-quarter onto the axes
    ctr = CLUB + V((0.0, 0.0, 2.0))
    b1a = CLUB + V((-3.0, -21.0, 50.0))
    b1b = CLUB + V((-1.5, -18.5, 43.0))
    b1t = ctr + V((2.2, -4.5, -2.0))                  # low enough that the bar and the tealight sit inside the frame
    kb1 = Cam('cam.B1', 30, b1a, b1t, fstop=8.0, focus=CLUB + V((0, 0, 5.0)), coll=cams)
    kb1.key(T_CLUB - 0.1, loc=b1a, target=b1t, interp='LINEAR')
    kb1.key(T_THESIS + 0.1, loc=b1b, target=b1t + V((-0.5, -1.5, 1.0)), interp='LINEAR')
    # B2: low front right on Clawd strumming
    cf = CLUB + V((0.0, 0.0, zs + 3.6))
    b2a = CLUB + V((9.0, -21.0, zs + 2.2))
    b2b = CLUB + V((7.6, -18.0, zs + 2.4))
    kb2 = Cam('cam.B2', 50, b2a, cf + V((-0.8, 0, -0.6)), fstop=5.6, focus=cf + V((0, -2.5, 0)), coll=cams)
    kb2.key(T_THESIS - 0.1, loc=b2a, target=cf + V((-0.8, 0, -0.6)), interp='LINEAR')
    kb2.key(T_BLUES + 0.1, loc=b2b, target=cf + V((-0.8, 0, -0.4)), interp='LINEAR')
    # B3: the researcher at the bar, Clawd soft behind
    rface = r.anchor(107.9, 'eyes')
    b3a = rface - D3 * 17.0 + V((0.0, 0.0, -0.6)) - r_left * 6.5
    b3b = rface - D3 * 14.8 + V((0.0, 0.0, -0.5)) - r_left * 5.8
    kb3 = Cam('cam.B3', 35, b3a, rface + D3 * 4.0 + V((0, 0, -1.2)), fstop=8.0, focus=rface - D3 * 1.2, coll=cams)
    kb3.key(T_BLUES - 0.1, loc=b3a, target=rface + D3 * 4.0 + V((0, 0, -1.2)), interp='LINEAR')
    kb3.key(T_B4 + 0.1, loc=b3b, target=rface + D3 * 4.0 + V((0, 0, -1.0)), interp='LINEAR')
    # B4: close, front right on Clawd, the last big strum
    # 55 deg round to his right (the raised strumming arm shows) and close, so the researcher at the bar (49 deg to
    # his right, 14.5 cm out) is behind the camera
    yb4 = math.radians(12.0)
    d4 = (V((math.sin(yb4), -math.cos(yb4), 0.0)) * math.cos(math.radians(55.0)) +
          V((-math.cos(yb4), -math.sin(yb4), 0.0)) * math.sin(math.radians(55.0)))
    b4a = CLUB + d4 * 12.5 + V((0.0, 0.0, zs + 4.0))
    b4b = CLUB + d4 * 11.6 + V((0.0, 0.0, zs + 4.1))
    kb4 = Cam('cam.B4', 30, b4a, cf + V((0.5, 0, 0.3)), fstop=5.6, focus=cf + V((0, -2.5, 0)), coll=cams)
    kb4.key(T_B4 - 0.1, loc=b4a, target=cf + V((0.5, 0, 0.3)), interp='LINEAR')
    kb4.key(T_B5 + 0.1, loc=b4b, target=cf + V((0.5, 0, 0.5)), interp='LINEAR')
    # B5: punch-in on his face
    ff5 = cc.anchor(109.0, 'face')
    yaw_c = math.radians(12.0 + 14.0)
    fwd = V((math.sin(yaw_c), -math.cos(yaw_c), 0.0))
    b5a = ff5 + fwd * 30.0 + V((0.0, 0.0, 0.5))
    b5b = ff5 + fwd * 23.0 + V((0.0, 0.0, 0.3))
    kb5 = Cam('cam.B5', 85, b5a, ff5 + V((0, 0, -0.2)), fstop=8.0, focus=ff5, coll=cams)
    kb5.key(T_B5 - 0.1, loc=b5a, target=ff5 + V((0, 0, -0.2)), interp='LINEAR')
    kb5.key(109.08, loc=b5a.lerp(b5b, 0.8), target=ff5 + V((0, 0, -0.1)), interp='LINEAR')
    kb5.key(T_END + 0.1, loc=b5b, target=ff5, interp='LINEAR')
    shake(kb5.cam, T_B5, T_B5 + 0.2, amp=0.06, freq=16.0, seed=9)

    for k, t in ((k1, T0), (k2, T_CLAP), (k2b, T_LATE), (k3, T_WE), (k4, T_FUSE), (k5, T_F5), (k6, T_F6), (kb1, T_CLUB),
                 (kb2, T_THESIS), (kb3, T_BLUES), (kb4, T_B4), (kb5, T_B5)):
        k.cut(t)
    sc.camera = k1.cam
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()

    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        # ================================================================== lyrics (revision 2: in the picture)
        ly.skip(31, (0, 4))            # "Now there's nowhere left" is up in paperclips until the cut: "to go" here
        ly.skip(32, 'fuse')            # the cord itself reads "fuse"
        ly.accent(32, 'we lit the', 'glow', preview=None)     # "we lit the" light up as they're sung
        # the stand probes rays: the clip field's instances make that slow, so it probes the core surface, lifted to
        # the clips' top while it does
        fld['object'].hide_viewport = True
        surf.location.z += FP.TOP
        # "too late now" beside his face in F2 (one row); in F3 the whole line so far, right of the pair (the lighting
        # stays clear), "we lit the" lighting up in it
        ly._stage_for(0.5 * (T_CLAP + T_LATE), ly.StageSpec(cells=13.0, rows=1, u=(0.78, 0.72, 0.84),
                                                           v=(0.62, 0.7, 0.55, 0.48)), ly.collection())
        ly._stage_for(0.5 * (T_LATE + T_WE), ly.StageSpec(cells=13.0, rows=1, u=(0.27, 0.22, 0.73), v=(0.11, 0.15, 0.2)),
                      ly.collection())
        ly._stage_for(0.5 * (T_WE + T_FUSE), ly.StageSpec(cells=13.0, rows=2, u=(0.7, 0.66, 0.74), v=(0.075, 0.11, 0.15),
                                                             height=0.06),
                      ly.collection())
        ly.line(32, words=(0, 3), t_end=T_WE, place=ly.Auto(cells=13.0, rows=1))
        for j in range(3):
            ly._state()['claimed'].discard((32, j))
        ly.line(32, words=(0, 6), t_show=T_WE, t_end=T_FUSE, place=ly.Auto(cells=13.0, rows=2))
        # the club's signage: the x axis is labelled ORTHOGONALITY in blue neon lying on the desk (read from B1 above),
        # the guitar's model name THESIS is gilded on its body (B2), the bar has a blue neon BLUES sign (B3)
        ly.line(33, words='Orthogonality', style='neon', color='#4FA3FF', strength=7.0,
                place=ly.At(CLUB + V((12.6, -4.9, 0.02)), face=0.0, flat=True, size=1.75), t_show=T_CLUB,
                exit='none', t_end=T_END, max_chars=30)
        ly.line(33, words='thesis', style='goldleaf', font='marker', support='none', exit='none', t_end=T_END,
                place=ly.on_object(gt, (-1.25, -0.39, 0.58), (0, -1, 0), (0, 0, 1), size=0.5, lift=0.012))
        to_cam3 = V(((b3a - bar_loc).x, (b3a - bar_loc).y, 0.0)).normalized()
        ly.line(33, words='blues', style='neon', color='#5AA8FF', strength=7.0, t_show=T_BLUES - 0.04, exit='none',
                t_end=T_END, place=ly.At(bar_loc + to_cam3 * 3.25 - r_left * 0.3 + V((0, 0, 2.9)), face=tuple(to_cam3),
                                        size=1.25))
        ly.default('fuse')
        fld['object'].hide_viewport = False
        surf.location.z -= FP.TOP
    print(f'[run] fuse: built in {time.time() - t_build:.1f}s', flush=True)


def _energy_fc(lo):
    return next((fc for fc in kit.fcurves(lo.data) if fc.data_path == 'energy'), None)


def _drop_keys(fc, pred):
    for i in reversed(range(len(fc.keyframe_points))):
        if pred(fc.keyframe_points[i].co.x):
            fc.keyframe_points.remove(fc.keyframe_points[i])


def _light_off_at(lo, f):
    """Cut a keyed light's energy to 0 from scene frame f on (it keeps its keys before f)."""
    fc = _energy_fc(lo)
    if fc is None:
        return
    v = fc.evaluate(f - 0.005)
    _drop_keys(fc, lambda x: x >= f - 0.005)
    for x, y in ((f - 0.005, v), (f, 0.0)):
        kp = fc.keyframe_points.insert(x, y)
        kp.interpolation = 'LINEAR'
    fc.update()


def _light_on_at(lo, f):
    """Hold a keyed light's energy at 0 until scene frame f (drops the ramp-up keys before f)."""
    fc = _energy_fc(lo)
    if fc is None:
        return
    _drop_keys(fc, lambda x: x < f)
    kp = fc.keyframe_points.insert(f, 0.0)
    kp.interpolation = 'LINEAR'
    fc.update()


def _vis_off(o, t):
    """Hide o from t on. If o already has visibility keys (the fuse's bead and ash appear on ignition), only add
    the off key (fx.vis would re-key it visible from the scene start)."""
    if not any(fc.data_path == 'hide_render' for fc in kit.fcurves(o)):
        fxvis(o, None, t)
        return
    o.hide_render = True
    o.keyframe_insert('hide_render', frame=t * FPS)
    for fc in kit.fcurves(o):
        if fc.data_path == 'hide_render':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def _ride(k, fu, ta, tb):
    """The racing camera: behind and beside the burn point, low over the clips, looking ahead of it; smoothed like
    an operator on a motion-control arm. Keyed every frame (LINEAR)."""
    s_of, at, total = fu['s'], fu['at'], fu['total']
    acc_c = acc_t = None
    for f in range(int(math.floor(ta * FPS)), int(math.ceil(tb * FPS)) + 1):
        t = f / FPS
        s = s_of(t)
        p, tan = at(s)
        pa, _ = at(max(0.0, s - 10.0))
        pb, _ = at(min(total, s + 24.0))
        back = (p - pa)
        if back.length < 1e-3:
            back = tan * 10.0
        dirv = (pb - pa).normalized()
        side = V((-dirv.y, dirv.x, 0.0)).normalized()
        cam = p - dirv * 13.0 - side * 5.0 + V((0, 0, 7.0))
        cam.z = max(cam.z, FP.height(cam.x, cam.y) + FP.TOP + 3.5)
        tgt = pb + V((0, 0, 0.5))
        acc_c = cam if acc_c is None else acc_c.lerp(cam, 0.45)
        acc_t = tgt if acc_t is None else acc_t.lerp(tgt, 0.35)
        k.key(t, loc=acc_c, target=acc_t, interp='LINEAR')
        if k.foc is None:
            k.foc = kit.empty(k.name + '.focus', tuple(p), k.cam.users_collection[0])
            k.cam.data.dof.focus_object = k.foc
        k.key(t, focus=p, interp='LINEAR')
