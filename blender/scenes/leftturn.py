"""leftturn · 82.052-89.324 · "Sharp left turn and there you are / Without a single CDR"

Backprop's last domino (tipped by the dying vacuum tube) starts a real rigid-body domino run: 71 black lacquered
dominoes snake up, round a U-turn and back along the front of the desk, take a SHARP LEFT TURN (a 115 deg hairpin on a
4 cm radius, a yellow SHARP LEFT TURN road sign at its outside) and race up toward the window, where the last one
clinks against the broken, empty jar lying on its side. Clawd is standing on top of it, free. He turns to us.

Revision 2 ("the cdr i think is talking about lisp"): "Without a single CDR" is Lisp. The researcher presents a toy
linked list built like an SICP box-and-pointer diagram between two big wooden parentheses: four wooden cons cells,
each car holding a word of the lyric in painted letter blocks, '(WITHOUT A SINGLE CDR), each cdr a black bead with a
bent-wire pointer arching into the next cell (the last cdr is nil, the slash). On C, D and R Clawd bites off the
three pointers one by one (spitting the first two aside, flinging the last over his shoulder); the cells, unlinked,
drift apart and the parentheses fall over: lone cars without a single cdr. Then he turns a sly cat's look on the
researcher and pounces: the lead-in to paperclips' "Gato".

Shot list (cuts on even frames: the puppets pose on twos)
  L1 82.052-83.833  one take, motion control. From a little above backprop's angle, backprop's domino (40 deg into
                    its fall) hits the run; the camera watches the wave run up and round the U-turn, swoops down to
                    domino height to race the last straight past the road sign ("turn"), WHIPS left with the wave at
                    the hairpin (the corner falls on the beat 82.506), then cranes up as the wave runs away up leg B
                    to the broken jar with Clawd standing on it against the window; the last domino clinks against
                    the jar on "there" (82.96, the beat); focus racks to Clawd, who hop-turns to face us on "you".
  L2 83.833-85.000  "are": close on Clawd on the jar, eyes happy (^^), he waves hello, then hops off the jar
                    toward us, out of the bottom of frame (84.6).
  L3 85.000-86.417  "Without a single": the camera trucks along the list from the researcher presenting it proudly
                    at its left end to Clawd behind its right end; the words pop into the cars as sung.
  L4 86.417-87.250  "C": closer on the last two cells: he bites off the last pointer on "C" (86.43), yanks it out
                    and spits it aside; the unlinked cells drift apart; he scuttles along to the middle pointer.
  L5 87.250-88.250  "D-R": wider, the whole run of cells: he bites off the middle pointer on "D" (87.28), hops to
                    the first and on "R" (87.66) flings it up over his shoulder; a smug look to us.
  L6 88.250-89.333  wide: the pointer clatters down behind him on the beat 88.415, the parentheses fall over
                    (88.87), the researcher is crestfallen; Clawd turns a sly cat's look on him and pounces.

Lyrics in the picture: SHARP LEFT TURN on the road sign at the hairpin; "and there you are" on the lyric stand;
WITHOUT, A, SINGLE and CDR are the list's cars (painted letter blocks popping in on the sung words, C-D-R on their
letters, just as Clawd bites each pointer).
"""
import math

import bpy
from mathutils import Matrix, Vector

from pdoom import chars, fx, kit
from pdoom.fx import rigid
from pdoom.sets import build_desk, geo
from pdoom.sets import materials as M
from pdoom.sets import materials as MATS     # (build_list's M is a matrix)
from pdoom import timing as tm
from pdoom.timing import FPS

from pdoom import lyrics as ly
from scenes import leftturn_lisp as LI
from scenes import leftturn_props as LP
from scenes import paperclips_props as PP
from scenes import leftturn_run as RUN
from scenes import safe_jar as SJ
from scenes.boot_common import Cam, shake

T0, TEND = 82.052, 89.324
T_CORNER, T_STRIKE = 82.506, 82.961
T_THERE, T_YOU, T_ARE = 82.96, 83.48, 83.93


def ct(t: float) -> float:
    """Snap a cut to the nearest even frame (characters pose on twos)."""
    return round(t * FPS / 2) * 2 / FPS


CUTS = [T0, ct(83.87), ct(85.0), ct(86.42), ct(87.25), ct(88.25)]


def sw(t: float) -> float:
    """A step meant to take effect from the 24 fps frame after song time t (keyed at t, usually a cut - 0.5/FPS).
    In a 60 fps build it goes to tm.switch_frame (0.1 frame before that frame: between two exposures, on the same
    side of the cut), so the outgoing shot's last 60 fps frame keeps the old value. 24 fps: unchanged."""
    return tm.switch_frame(t * FPS) / FPS if tm.SMOOTH else t


def smoothstep(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def lerp(a, b, u):
    return a + (b - a) * u


# ------------------------------------------------------------------------------------------------ the wave front


class Front:
    """The domino wave front as a function of song time: the station each domino stands on, interpolated by the time
    it tips past 20 deg, smoothed over a few frames."""

    def __init__(self, stations, times, first_pos):
        pts = [first_pos] + [p for p, _, _ in stations]
        self.k = [(t, p) for t, p in zip(times, pts) if t is not None]
        self.k.sort(key=lambda x: x[0])

    def raw(self, t):
        k = self.k
        if t <= k[0][0]:
            return k[0][1].copy()
        for (ta, pa), (tb, pb) in zip(k, k[1:]):
            if t <= tb:
                u = (t - ta) / max(1e-6, tb - ta)
                return pa.lerp(pb, u)
        return k[-1][1].copy()

    def at(self, t, win=0.05):
        acc = Vector()
        n = 7
        for i in range(n):
            acc += self.raw(t + win * (i / (n - 1) - 0.5))
        return acc / n


# ------------------------------------------------------------------------------------------------ build


def build():
    sc = kit.new_scene('leftturn')
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable', 'books', 'clip', 'mug', 'killswitch'})
    props = kit.collection('lt.props')

    # ---------------------------------------------------------------- the run (physics) and the jar
    rigid.world(substeps=24, iterations=20, preroll=0.25)
    rigid.passive(bpy.data.objects['desk.top'], shape='BOX')
    run = RUN.build(kit.collection('lt.dominoes'), spacing_a=1.2, spacing_b=1.2, t_start=T0)
    hB = RUN.heading_b()
    u = Vector((hB.y, -hB.x, 0.0))                  # the jar's axis (base -> mouth), across leg B
    J = RUN.jar_center()
    col = LP.jar_collider(props, J, u)
    rigid.passive(col, shape='CONVEX_HULL', friction=0.5)
    # measure the wave (a throwaway bake) for the camera
    pc = sc.rigidbody_world.point_cache
    keep = pc.frame_end
    pc.frame_end = int(84.0 * FPS)
    rigid.bake('leftturn measure')
    objs = RUN.active(run)
    times = RUN.measure(objs, int(81.9 * FPS), pc.frame_end, 20.0)
    ic = run['legs'].index('C')
    t_strike = RUN.strike_time(objs[-1], int(82.5 * FPS), pc.frame_end)
    fx.log(f'leftturn: corner {times[ic]:.3f}, last domino strikes the jar at {t_strike}')
    with bpy.context.temp_override(scene=sc):
        bpy.ops.ptcache.free_bake_all()
    pc.frame_end = keep
    front = Front(run['stations'], times, RUN.BP_DOMINO + RUN.FALL_DIR * 0.0)

    top = Vector((J.x, J.y, 2 * SJ.R_OUT)) + u * 1.5   # on the lying jar, toward its base (the mouth is at -u): his
                                                    # feet stay clear of the torn tape band nearer the mouth
    P_C = J - hB * 11.0 - u * 6.0                    # where Clawd lands when he hops off the jar
    jr = LP.broken_jar(props, J, -u, -hB)          # the mouth toward the camera side (-u), the hole facing us
    L_C = Vector((30.0, -4.0, 0.0))                 # the Lisp list's centre (it stands along u, facing -hB), left of
    LM_ = list_frame(L_C, u, hB)                    # the domino run
    LP.scatter_shards(jr['loose'], J, hB, u, avoid=[(P_C, 5.5)])
    LP.torn_tape(props, jr['M'], jr['hole_angle'])
    LP.lid(props, J - u * 11.0 - hB * 2.5, yaw_deg=33.0, tilt_deg=3.0)
    lst = build_list(kit.collection('lt.list'), LM_)
    sign = road_sign(kit.collection('lt.sign'))

    c, r = act(J, u, hB, top, P_C, L_C, lst)

    # ---------------------------------------------------------------- lights
    lc = kit.collection('lt.lights')
    d.lamp.aim(None, J + Vector((0, -4, 6)), reach=13.0, height=42.0)
    d.lamp.intensity(sw(CUTS[1] - 1.5 / FPS), 1.0, interp='CONSTANT')
    d.lamp.intensity(sw(CUTS[1] - 0.5 / FPS), 0.72, interp='CONSTANT')
    d.lamp.intensity(sw(CUTS[2] - 1.5 / FPS), 0.72, interp='CONSTANT')
    d.lamp.intensity(sw(CUTS[2] - 0.5 / FPS), 0.5, interp='CONSTANT')
    kit.spot('lt.key', (22.0, -78.0, 62.0), (62.0, -14.0, 2.0), power=210000.0, angle_deg=46, blend=0.6,
             radius=4.0, color='#FFD2A0', coll=lc)
    fill = kit.area('lt.fill', (104.0, -46.0, 18.0), (62.0, -12.0, 3.0), power=26000.0, size=30.0, color='#9EC4FF',
                    coll=lc)
    fill.data.specular_factor = 0.2
    # the list's key: a warm spot from the front left onto the cells and the researcher (L3-L6)
    lkey = kit.spot('lt.list.key', tuple(L_C - hB * 40.0 - u * 18.0 + Vector((0, 0, 38.0))),
                    tuple(L_C + Vector((0, 0, 2.0))), power=150000.0, angle_deg=40, blend=0.6, radius=3.0,
                    color='#FFD8A8', coll=lc)
    geo.keyp(lkey.data, 'energy', T0 - 1, 0.0, interp='CONSTANT')
    geo.keyp(lkey.data, 'energy', sw(CUTS[2] - 0.5 / FPS), 150000.0, interp='CONSTANT')
    # the glossy black dominoes need something to reflect: a big soft box low on the camera side, and a warm rim
    # from behind the run that draws their top edges
    soft = kit.area('lt.soft', (58.0, -62.0, 14.0), (60.0, -20.0, 3.0), power=30000.0, size=40.0, color='#FFE6CC',
                    shape='RECTANGLE', coll=lc)
    soft.data.size_y = 14.0
    soft.data.diffuse_factor = 0.35
    rim = kit.area('lt.rim', (62.0, 4.0, 14.0), (62.0, -24.0, 1.0), power=26000.0, size=24.0, color='#FFC58A', coll=lc)
    rim.data.specular_factor = 1.0
    rim.data.diffuse_factor = 0.4
    dom_link = bpy.data.collections.new('lt.domino.receivers')     # these two only light the dominoes
    for o in RUN.active(run):
        dom_link.objects.link(o)
    for lo in (soft, rim):
        lo.light_linking.receiver_collection = dom_link
    geo.keyp(soft.data, 'energy', 82.6, 30000.0, interp='LINEAR')
    geo.keyp(soft.data, 'energy', 82.95, 0.0, interp='LINEAR')
    geo.keyp(rim.data, 'energy', 82.62, 26000.0, interp='LINEAR')
    geo.keyp(rim.data, 'energy', 82.94, 5000.0, interp='LINEAR')
    geo.keyp(rim.data, 'energy', sw(CUTS[1] - 1.5 / FPS), 5000.0, interp='CONSTANT')
    geo.keyp(rim.data, 'energy', sw(CUTS[1] - 0.5 / FPS), 0.0, interp='CONSTANT')
    glass_lights(jr, J, u, hB, lc)
    for lo in lc.objects:                       # the helpers don't need shadows (cheaper renders)
        if lo.name.startswith(('lt.strip', 'lt.soft', 'lt.rim', 'lt.fill')):
            lo.data.use_shadow = False

    # ---------------------------------------------------------------- cameras
    oner(front, run, J, u, hB, top)
    cams = shots(c, r, J, u, hB, top, P_C, L_C, lst)
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
    chars.finish()
    pointers_rig(c, lst, u, hB)
    fx.bake()
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(lst, sign, cams)
    sc.frame_set(sc.frame_start)


# ------------------------------------------------------------------------------------------------ the list

T_HOPDOWN = 84.6
BEATS3 = (85.233, 85.688, 86.142)
T_C, T_D, T_R = 86.429, 87.28, 87.66                 # C-D-R: a pointer bitten off on each
T_LAND = 88.415                                     # the last pointer clatters down (a beat)
T_PARENS = 88.87                                    # the parentheses fall over (a beat)
WORDS = ('Without', 'a', 'single', 'CDR')


def list_frame(L_C, u, hB):
    """World matrix of the list: origin at its centre on the desk, +X along it (u), +Y back (hB), +Z up."""
    M = Matrix.Identity(4)
    M.col[0][:3] = u
    M.col[1][:3] = hB
    M.col[2][:3] = (0.0, 0.0, 1.0)
    M.col[3][:3] = L_C
    return M


def build_list(coll, M):
    """The cells, the pointers and the parentheses, placed in the list frame. Returns a dict with the cells, the
    pointers (on the list), each cell's rest matrix and the pointers' midpoints (list x)."""
    cells, arrows, rest, a_mid = [], [], [], []
    for k in range(4):
        x = (k - 1.5) * LI.PITCH
        o = LI.cell(coll, f'lt.cons{k}', last=(k == 3))
        Mk = M @ Matrix.Translation((x, 0.0, 0.0))
        o.matrix_world = Mk
        cells.append(o)
        rest.append(Mk.copy())
        if k < 3:
            a = LI.arrow(coll, f'lt.ptr{k}')
            a.matrix_world = M @ Matrix.Translation((x + LI.CDR_X, 0.1, LI.BEAD_Z))
            arrows.append(a)
            a_mid.append(x + LI.CDR_X + LI.ARROW_L / 2)
    if not ly.ENABLED:
        # revision 3 (no lyrics in the picture): each car holds an atom, a painted wooden bead, instead of a word
        for k, (o, col) in enumerate(zip(cells, ('#C8452F', '#E0A82E', '#3F7FBF', '#4E9A5A'))):
            a = kit.sphere(f'lt.atom{k}', 0.78, (0, 0, 0), m=MATS.solid(f'lt.atom{k}', col, rough=0.35, coat=0.5,
                                                                       coat_rough=0.12), coll=coll, subdiv=3)
            a.parent = o
            a.matrix_parent_inverse = Matrix.Identity(4)
            a.location = (-LI.CELL_W / 2 + LI.CAR_W / 2 - LI.WALL * 0.25, 0.0, LI.WALL + 0.78)
    x_end = 2 * LI.PITCH - LI.GAP / 2 + 2.3      # clear of the end cells' feet after they drift apart (1.1 cm)
    parens = []
    for side in (-1, 1):
        pr = LI.paren(coll, f'lt.paren{"LR"[side > 0]}', side)
        pr.matrix_world = M @ Matrix.Translation((side * x_end, 0.0, 0.0))
        parens.append(pr)
    return {'M': M, 'cells': cells, 'arrows': arrows, 'rest': rest, 'a_mid': a_mid, 'parens': parens,
            'x_end': x_end}


def drift(lst):
    """Unlinked, the cells drift apart a little (a slide and a turn as each pointer comes off), smooth keys."""
    moves = {3: [(T_C + 0.05, 1.1, 6.0)], 2: [(T_C + 0.05, -0.3, -2.0), (T_D + 0.05, 0.5, 4.0)],
             1: [(T_D + 0.05, -0.3, -3.0), (T_R + 0.05, 0.4, 3.0)], 0: [(T_R + 0.05, -1.0, -5.0)]}
    for k, o in enumerate(lst['cells']):
        dx, rz = 0.0, 0.0
        keys = [(T0 - 1.0, 0.0, 0.0)]
        for t, ddx, drz in moves[k]:
            keys.append((t, dx, rz))
            dx += ddx
            rz += drz
            keys.append((t + 0.22, dx, rz))
        for t, x, a in keys:
            o.matrix_world = lst['rest'][k] @ Matrix.Translation((x, -0.15 * abs(x), 0.0)) @ \
                Matrix.Rotation(math.radians(a), 4, 'Z')
            o.keyframe_insert('location', frame=t * FPS)
            o.keyframe_insert('rotation_euler', frame=t * FPS)


def road_sign(coll):
    """A toy yellow diamond road sign on a post at the outside of the hairpin, facing the camera racing up the last
    straight. Returns an Empty on the sign's face (its local -Y faces the camera, +Z up) for the letters."""
    c0 = RUN.corner_points()[1]
    base = c0 + Vector((6.6, -3.2, 0.0))
    face = (Vector((61.0, -33.5, 0.0)) - base).normalized()
    yaw = math.atan2(face.x, -face.y)
    post = kit.cylinder('lt.sign.post', 0.16, 4.0, (0, 0, 2.0), verts=12,
                        m=M.solid('lt.sign.steel', '#9DA3AA', rough=0.3, metal=1.0), coll=coll)
    foot = kit.cylinder('lt.sign.foot', 1.1, 0.35, (0, 0, 0.175), verts=24,
                        m=M.solid('lt.sign.rubber', '#2A2A2C', rough=0.7), coll=coll)
    board = kit.box('lt.sign.board', (4.1, 0.12, 4.1), (0, 0, 0), bevel=0.25, segments=3,
                    m=M.solid('lt.sign.yellow', '#F2C230', rough=0.4, coat=0.4), coll=coll)
    rim_ = kit.box('lt.sign.rim', (4.45, 0.08, 4.45), (0, 0, 0), bevel=0.3, segments=3,
                   m=M.solid('lt.sign.black', '#1A1A1A', rough=0.4), coll=coll)
    root = kit.empty('lt.sign', (0, 0, 0), coll, 'ARROWS', 1.0)
    board.rotation_euler = (0.0, math.radians(45.0), 0.0)
    rim_.rotation_euler = (0.0, math.radians(45.0), 0.0)
    board.location = (0.0, -0.2, 5.7)
    rim_.location = (0.0, -0.12, 5.7)
    for o in (post, foot, board, rim_):
        o.parent = root
    root.location = base
    root.rotation_euler = (0.0, 0.0, yaw)
    face_o = kit.empty('lt.sign.face', (0.0, -0.27, 5.7), coll, 'PLAIN_AXES', 0.5)
    face_o.parent = root
    return face_o


# ------------------------------------------------------------------------------------------------ the acting


def act(J, u, hB, top, P_C, L_C, lst):
    """Clawd on the jar, the hop down, the list: three pointers bitten off, the pounce. The researcher presents it.
    Returns (clawd, researcher)."""
    yaw_away = math.degrees(math.atan2(-hB.x, hB.y)) + 180.0      # facing +dB (toward the window)
    yaw_front = math.degrees(math.atan2(-hB.x, hB.y))               # facing -hB (the camera side)
    c = chars.Clawd(kit.collection('clawd'), loc=tuple(top), yaw=yaw_away)
    c.eyes(T0, 'open')
    c.squash(T_STRIKE + 0.02, 0.1)                                  # the clink
    c.look(83.25, top - hB * 30 + Vector((0, 0, -6)), turn=0.0)      # glances over his shoulder
    c.hop(T_YOU, 2.4, dur=0.3, at='land', spin=180.0)
    c.eyes(T_YOU - 0.02, 'narrow')
    c.look(T_YOU + 0.1, None)
    # L2 "are": happy, a wave hello, then he hops off the jar's front
    c.eyes(T_ARE, 'happy')
    c.wave(84.02, 84.42, side='R')
    c.eyes(84.46, 'open')
    c.hop(T_HOPDOWN, 3.0, dur=0.36, to=(P_C.x, P_C.y, 0.0))
    c.squash(T_HOPDOWN + 0.36, 0.22)
    # L3: behind the list at the last pointer (the camera trucks along the list to him), eyeing it
    spots = [L_C + u * a + hB * 3.4 for a in lst['a_mid']]
    c.place(CUTS[2], loc=tuple(spots[2]), yaw=yaw_front)
    c.eyes(CUTS[2], 'open')
    c.T['eyes.look'].set(CUTS[2] + 0.02, (-0.3, -0.3), 0.0)
    for t, lk in ((85.5, (-0.2, -0.35)), (85.9, (0.0, -0.3)), (86.1, (0.3, -0.3))):
        c.T['eyes.look'].set(t, lk, 0.12)
    c.eyes(85.9, 'narrow')
    c.lid(86.15, 0.12, dur=0.1)
    # C: bite the last pointer, yank, spit it aside; scuttle to the middle one
    c.chomp(T_C, wide=1.0)
    c.T['eyes.look'].set(T_C + 0.05, (0.0, 0.0), 0.05)
    c.T['body.rot'].set(T_C + 0.14, (-12.0, 0.0, -14.0), 0.1)
    c.T['body.rot'].set(T_C + 0.26, (4.0, 0.0, 18.0), 0.08)       # the spit: a flick of the head
    c.T['body.rot'].set(T_C + 0.42, (0.0, 0.0, 0.0), 0.12)
    c.move(86.7, 87.12, [tuple(spots[1])], face='keep')
    # D: bite, spit it back; hop to the first
    c.chomp(T_D, wide=1.0)
    c.T['body.rot'].set(T_D + 0.1, (-14.0, 0.0, 10.0), 0.08)
    c.T['body.rot'].set(T_D + 0.2, (0.0, 0.0, 0.0), 0.08)
    c.hop(87.37, 1.4, dur=0.21, to=tuple(spots[0]))
    # R: bite and fling it up over his shoulder
    c.chomp(T_R, wide=1.05)
    c.timing(86.35, 87.9, 'ones')
    c.T['body.rot'].set(T_R + 0.06, (14.0, 0.0, 0.0), 0.06)
    c.T['body.rot'].set(T_R + 0.16, (-32.0, 0.0, 0.0), 0.08)
    c.T['body.rot'].set(T_R + 0.5, (0.0, 0.0, 0.0), 0.25)
    c.lid(T_R + 0.16, 0.6, dur=0.06)
    c.lid(T_R + 0.4, 0.0, dur=0.12)
    c.stretch(T_R + 0.16, 0.22)
    c.eyes(T_R + 0.2, 'narrow')
    c.T['eyes.look'].set(87.95, (0.0, 0.0), 0.1)
    # L6: the lead-in to "Gato": a sly look at the researcher, then the pounce
    R_PRES = L_C - u * (lst['x_end'] + 5.6) - hB * 2.0
    c.look(88.55, R_PRES + Vector((0, 0, 8.0)), turn=0.9, dur=0.2)
    c.eyes(88.6, 'narrow')
    c.lid(88.95, 0.3, dur=0.12)
    c.hop(89.06, 4.5, dur=0.32, to=tuple(R_PRES.lerp(spots[0], 0.3) - hB * 8.0))     # high over cell 0, in front of it
    c.lid(89.12, 0.85, dur=0.08)

    # ---------------------------------------------------------------- the researcher
    P = chars.POSES
    P['present_list'] = dict(spine=(-3, 0, 0), head=(8, 0, 0), hands=((2.1, -2.2, 6.4), (-1.3, -2.8, 5.6)),
                             wrist=((-30, 0, -35), (-35, 0, 40)), face='proud')
    fwd_p = u * 0.75 - hB * 0.65
    r = chars.Researcher(kit.collection('researcher'), loc=tuple(R_PRES), yaw=math.degrees(math.atan2(fwd_p.x, -fwd_p.y)))
    r.visible(CUTS[2] - 0.5 / FPS)
    r.pose(CUTS[2] - 0.05, 'present_list', dur=0.01)
    r.face(CUTS[2], 'proud')
    for tb in BEATS3:
        r.nod(tb, n=1, amount=6.0, every=0.3)
    r.look(85.3, L_C + Vector((0, 0, 3.0)))
    r.face(T_C + 0.05, 'shock')
    r.pose(T_C + 0.08, 'gasp', dur=0.1)
    r.face(T_D + 0.05, 'wince')
    r.pose(T_D + 0.1, 'facepalm', dur=0.12)
    r.pose(T_R + 0.1, 'gasp', dur=0.1)
    r.face(T_R + 0.08, 'shock')
    # L6: crestfallen at his end of the list; then the pounce
    r.pose(CUTS[5] + 0.1, 'nervous', dur=0.3)
    r.face(CUTS[5] + 0.1, 'sad')
    r.look(T_LAND + 0.05, spots[0] + hB * 12.0)
    r.look(88.7, spots[0] + Vector((0, 0, 4.0)))
    r.face(89.0, 'shock')
    r.pose(89.02, 'back_away', dur=0.12, face=False)
    return c, r


def pointers_rig(c, lst, u, hB):
    """After the characters are baked: each pointer is on the list until he bites it, then in his teeth, then
    thrown: a rigid body released with the head's velocity (the first two spat aside, the last flung high over his
    shoulder to land on T_LAND)."""
    sc = bpy.context.scene
    coll = kit.collection('lt.list')
    L = LI.ARROW_L
    up = LI.ARCH_Z - LI.BEAD_Z
    # (pointer, bite, release, where its bead lands (spat: forward and aside, onto the desk in front of the list,
    # never back through his head), flight time); the last one is flung over his shoulder to land on T_LAND
    a_mid = lst['a_mid']
    M_ = lst['M']
    plan = [(2, T_C, T_C + 0.26, M_ @ Vector((a_mid[2] + 5.5, -7.0, 0.3)), 0.3),
            (1, T_D, T_D + 0.1, M_ @ Vector((a_mid[1] + 4.0, -7.0, 0.3)), 0.28),
            (0, T_R, T_R + 0.16, None, None)]
    for k, t_bite, t_rel, land_at, t_fly in plan:
        A = lst['arrows'][k]
        heads = list(A.children)
        f_bite = int(round(t_bite * FPS))
        f_rel = int(round(t_rel * FPS))
        B = bpy.data.objects.new(f'lt.ptr{k}.mouth', A.data)
        coll.objects.link(B)
        # held crosswise in his lips: the top run lies along the front of the lip line (just outside the skin, at
        # the lid/jaw seam) and the two legs stick out forward and down at 30 deg, over the open trays, so the whole
        # pointer shows (hung straight down it was buried in his lower jaw)
        a = math.radians(-60.0)                       # local -Z (the legs) -> forward (-Y) and 30 deg down
        run = Vector((0.0, -2.35, 3.55 - 1.3))         # the top run's centre line, body-socket coordinates
        org = run - Vector((0.0, -up * math.sin(a), up * math.cos(a)))
        c.attach(B, 'body', offset=(-L / 2, org.y, org.z), rot=(-60.0, 0.0, 0.0))
        for h in heads:
            hb = bpy.data.objects.new(h.name + '.mouth', h.data)
            coll.objects.link(hb)
            hb.parent = B
            fx.vis(hb, sw(f_bite / FPS - 0.5 / FPS), sw(f_rel / FPS + 0.5 / FPS))
        for o in [A] + heads:
            fx.vis(o, None, sw(f_bite / FPS - 0.5 / FPS))
        fx.vis(B, sw(f_bite / FPS - 0.5 / FPS), sw(f_rel / FPS + 0.5 / FPS))
        # the thrown copy: follows B up to the release, then flies
        mats = {}
        for f in range(f_bite, f_rel + 1):
            sc.frame_set(f)
            mats[f] = B.matrix_world.copy()
        Cc = bpy.data.objects.new(f'lt.ptr{k}.thrown', A.data)
        coll.objects.link(Cc)
        for h in heads:
            hc = bpy.data.objects.new(h.name + '.thrown', h.data)
            coll.objects.link(hc)
            hc.parent = Cc
            fx.vis(hc, sw(f_rel / FPS + 0.5 / FPS), None)
        p0 = mats[f_rel].translation.copy()
        g = Vector((0, 0, -981.0))
        if land_at is not None:                  # spat: a ballistic arc onto the desk in front of the list
            vel = (land_at - p0) / t_fly - 0.5 * g * t_fly
        else:                                    # the fling lands behind him on T_LAND
            land = p0 + hB * 12.0 + u * 2.0
            land.z = 0.3
            T = T_LAND - f_rel / FPS
            g = Vector((0, 0, -981.0))
            vel = (land - p0) / T - 0.5 * g * T
        spin = Vector((-u.y, u.x, 0.0))
        R0 = mats[f_rel].to_quaternion()
        if land_at is not None:
            # spat: keyed, not simulated (a bent wire never settles as a rigid body: it rocked on its legs for
            # seconds and sank into the desk). A ballistic arc with one roll, landing flat on its side (the arch
            # pointing toward the camera, clear of the trays), one small bounce, then still.
            yaw = math.radians(-25.0 if k == 2 else 20.0)
            xd = (M_.to_3x3() @ Vector((math.cos(yaw), math.sin(yaw), 0.0))).normalized()
            yd = Vector((0.0, 0.0, 1.0))
            R1 = Matrix((xd, yd, xd.cross(yd))).transposed().to_quaternion()
            if R0.dot(R1) < 0:
                R1.negate()
            p1 = land_at.copy()
            p1.z = 0.2                                # the arrowhead's cone (r 0.24) rests on the desk
            t_bn = 0.16                               # the bounce
            Cc.rotation_mode = 'QUATERNION'
            fe = f_rel + (t_fly + t_bn + 0.1) * FPS
            fks = tm.out_frames(f_rel, fe) if tm.SMOOTH else list(range(f_rel, int(math.ceil(fe)) + 1))
            prev = None
            for f in [float(f_bite)] + [x for x in fks if x >= f_rel]:
                dt = max(0.0, f / FPS - f_rel / FPS)
                if dt <= t_fly:
                    sx = dt / t_fly
                    pos = p0.lerp(p1, sx) + Vector((0.0, 0.0, -0.5 * g.z * dt * (t_fly - dt)))
                    q = Matrix.Rotation(2 * math.pi * sx, 4, spin).to_quaternion() @ R0.slerp(R1, sx)
                else:
                    x = min(1.0, (dt - t_fly) / t_bn)
                    pos = p1 + Vector((0.0, 0.0, 0.7 * math.sin(math.pi * x)))
                    q = R1.copy()
                if prev is not None and prev.dot(q) < 0:
                    q.negate()
                prev = q
                Cc.location = pos
                Cc.rotation_quaternion = q
                Cc.keyframe_insert('location', frame=f)
                Cc.keyframe_insert('rotation_quaternion', frame=f)
            for fc in kit.fcurves(Cc):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
        else:
            for f in range(f_bite, f_rel + 1):
                if f < f_rel - 2:
                    Mx = mats[f]
                else:
                    dt = (f - f_rel) / FPS
                    q = Matrix.Rotation(14.0 * dt, 4, spin).to_quaternion() @ R0
                    Mx = Matrix.Translation(p0 + vel * dt) @ q.to_matrix().to_4x4()
                Cc.matrix_world = Mx
                Cc.keyframe_insert('location', frame=f)
                Cc.keyframe_insert('rotation_euler', frame=f)
            for fc in kit.fcurves(Cc):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
            rigid.active(Cc, mass=0.02, shape='CONVEX_HULL', friction=0.6, bounce=0.3, damping=(0.05, 0.12),
                         margin=0.02)
            rigid.release(Cc, f_rel / FPS)
            Cc.rigid_body.use_start_deactivated = False
        fx.vis(Cc, sw(f_rel / FPS + 0.5 / FPS), None)
        fx.log(f'pointer {k}: bite {f_bite}, release {f_rel}, v {tuple(round(x) for x in vel)}')
    drift(lst)
    # the parentheses fall over outward on the beat: the list is no more
    M = lst['M']
    for side, pr in zip((-1, 1), lst['parens']):
        # '(' falls back and outward, away from the researcher in front of it; ')' straight out (behind it, the
        # jar lid lies on the desk)
        out = (M.to_3x3() @ (Vector((-0.5, 1.0, 0.0)) if side < 0 else Vector((1.0, 0.0, 0.0)))).normalized()
        piv = pr.matrix_world.translation + out * 0.9
        dt = 0.06 if side > 0 else 0.0
        PP.tip(pr, T_PARENS - 0.28 - dt, T_PARENS - dt, direction=out, pivot=piv, angle=86.0, bounce=5.0)
    sc.frame_set(sc.frame_start)


# ------------------------------------------------------------------------------------------------ the other shots


def shots(c, r, J, u, hB, top, P_C, L_C, lst):
    V = Vector
    # L2 "are": close on Clawd on the jar, a slow push; he hops off out of the bottom of frame
    face0 = top + V((0, 0, 4.2))
    cam2 = Cam('lt.cam2', 58, face0 - hB * 30 - u * 4 + V((0, 0, 0.5)), face0, fstop=8.0)
    cam2.key(CUTS[1], loc=face0 - hB * 30 - u * 4 + V((0, 0, 0.5)), target=face0, interp='LINEAR')
    cam2.key(CUTS[2], loc=face0 - hB * 27.5 - u * 3.6 + V((0, 0, 0.5)), target=face0 + V((0, 0, -0.4)),
             interp='LINEAR')
    cam2.cut(CUTS[1])
    # L3 "Without a single": trucking along the list from the researcher at its left end to Clawd at its right,
    #    the words popping into the cars as the camera passes
    def P_(x, back=0.0, z=0.0):
        return L_C + u * x + hB * back + V((0, 0, z))
    cam3 = Cam('lt.cam3', 40, P_(-11.0, -27.0, 9.5), P_(-11.0, 0.0, 2.2), fstop=11.0, focus=P_(-11.0, -0.5, 1.6))
    cam3.key(CUTS[2], loc=P_(-18.5, -27.0, 11.0), target=P_(-18.5, 0.0, 4.2), focus=P_(-20.0, -1.5, 4.0))
    for t, x in ((85.5, -6.0), (86.0, 2.0), (CUTS[3], 5.0)):
        cam3.key(t, loc=P_(x, -27.0, 9.5), target=P_(x, 0.0, 2.2), focus=P_(x, -0.5, 1.6))
    cam3.cut(CUTS[2])
    a0, a1, a2 = lst['a_mid']
    # L4 "C": on the last two cells: the bite; pans left with him to the middle pointer
    cam4 = Cam('lt.cam4', 40, P_(a2 + 1.5, -24.0, 8.5), P_(a2 + 1.5, 0.0, 2.8), fstop=11.0,
               focus=P_(a2 + 1.0, 0.3, 2.4))
    cam4.key(CUTS[3], loc=P_(a2 + 1.5, -24.0, 8.5), target=P_(a2 + 1.5, 0.0, 2.8), focus=P_(a2 + 1.0, 0.3, 2.4))
    cam4.key(86.72, loc=P_(a2 + 1.0, -24.0, 8.4), target=P_(a2 + 1.0, 0.0, 2.8), focus=P_(a2, 0.3, 2.4))
    cam4.key(CUTS[4], loc=P_(a1 + 4.5, -24.5, 8.4), target=P_(a1 + 4.5, 0.0, 2.8), focus=P_(a1, 0.3, 2.4))
    cam4.cut(CUTS[3])
    # L5 "D-R": wider, the whole run of cells from the first pointer to CDR; he flings the last one high
    cam5 = Cam('lt.cam5', 32, P_(2.0, -30.0, 9.5), P_(2.0, 0.0, 3.0), fstop=11.0, focus=P_(0.0, 0.3, 2.4))
    cam5.key(CUTS[4], loc=P_(2.0, -30.0, 9.5), target=P_(2.0, 0.0, 3.0), interp='LINEAR')
    cam5.key(CUTS[5], loc=P_(1.0, -27.5, 9.2), target=P_(1.0, 0.0, 3.4), interp='LINEAR')
    cam5.cut(CUTS[4])
    # L6: wide from the front left: the pointer lands behind him, the parentheses fall, the pounce
    cam6 = Cam('lt.cam6', 30, P_(-9.0, -42.0, 15.0), P_(-8.0, 3.0, 3.5), fstop=11.0)
    cam6.key(CUTS[5], loc=P_(-9.0, -42.0, 15.0), interp='LINEAR')
    cam6.key(TEND, loc=P_(-10.0, -39.0, 14.0), interp='LINEAR')
    cam6.cut(CUTS[5])
    return {'l2': cam2.cam, 'l3': cam3.cam, 'l6': cam6.cam}


def lyrics(lst, sign, cams):
    """SHARP LEFT TURN on the road sign; WITHOUT A SINGLE CDR in the list's cars; "and there you are" on the
    stand."""
    ly.line(25, words='Sharp left turn', style='stamp', ink='#161412', reveal='appear', support='none',
            max_chars=5, rows=3, place=ly.on_object(sign, (0.0, 0.0, -1.3), (0, -1, 0), (0, 0, 1), size=0.62,
                                                    lift=0.0),
            t_end=83.5)
    cx = -LI.CELL_W / 2 + LI.CAR_W / 2 - LI.WALL * 0.25
    inner = LI.CAR_W - 1.5 * LI.WALL - 0.3
    for k, w in enumerate(WORDS):
        size = min(0.9, inner / (1.06 * len(w)))           # each word as big as its car allows
        ly.line(26, words=w, place=ly.on_object(lst['cells'][k], (cx, -0.4, LI.WALL), (0, -1, 0), (0, 0, 1),
                                                size=size, lift=0.0),
                exit='none', t_end=TEND)
    ly.default('leftturn')


# ------------------------------------------------------------------------------------------------ helpers


def catmull(keys, t):
    """Catmull-Rom through [(t, Vector)] (clamped at the ends), parameterised by time."""
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


def oner(front, run, J, u, hB, top):
    """L1: a motion-control one take. From a little above backprop's angle it watches the wave run up and round the
    U-turn, swoops down to domino height to race the last straight into the corner, whips left with the wave at the
    hairpin (82.50), then cranes up while the wave runs away up leg B to the broken jar and Clawd; the last domino
    strikes the jar (82.96), focus racks to Clawd, he hop-turns to face us on "you"."""
    V = Vector
    POS = [(T0, V((41.5, -40.5, 11.0))), (82.20, V((47.5, -40.5, 9.0))), (82.34, V((54.5, -37.5, 5.6))),
           (82.44, V((60.0, -34.4, 4.2))), (82.52, V((65.0, -33.0, 4.2))), (82.62, V((67.2, -31.2, 5.0))),
           (82.76, V((66.2, -28.2, 7.0))), (82.92, V((65.0, -25.6, 8.8))), (83.10, V((64.3, -23.6, 9.6))),
           (CUTS[1] + 0.05, V((63.1, -20.2, 9.8)))]
    cam = Cam('lt.cam1', 24, POS[0][1], J, fstop=5.6, focus=J)
    look_end = J + V((0.0, 0.0, 8.8))
    t_w0, t_w1 = 82.50, 82.62
    f0, f1 = int(math.floor(T0 * FPS)) - 1, int(math.ceil(CUTS[1] * FPS)) + 1
    for f in range(f0, f1 + 1):
        t = f / FPS
        pos = catmull(POS, t)
        fr = front.at(t)
        lead = front.at(t + 0.035) + V((0, 0, 1.8))
        if t < 82.24:
            # at the cut the aim eases off backprop's domino onto the running wave (no whip on the first frame)
            k = smoothstep((t - T0) / (82.24 - T0))
            lead = (RUN.BP_DOMINO + RUN.FALL_DIR * 4.0 + V((0, 0, 2.0))).lerp(front.at(t + 0.06, 0.12) + V((0, 0, 1.8)),
                                                                             0.35 + 0.65 * k)
        if t < t_w0:
            tgt = lead
        elif t < t_w1:
            w = smoothstep((t - t_w0) / (t_w1 - t_w0))
            a0 = math.atan2(lead.y - pos.y, lead.x - pos.x)
            aim_b = front.at(t + 0.1).lerp(J, 0.55) + V((0, 0, 4.0))
            a1 = math.atan2(aim_b.y - pos.y, aim_b.x - pos.x)
            da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
            a = a0 + da * w
            dist = 20.0
            tgt = pos + V((math.cos(a) * dist, math.sin(a) * dist, lerp(lead.z, aim_b.z, w) - pos.z))
        else:
            w = smoothstep((t - t_w1) / (83.05 - t_w1))
            tgt = (front.at(t + 0.1).lerp(J, 0.55) + V((0, 0, 4.0))).lerp(look_end, w)
        if t < T_STRIKE - 0.02:
            foc = fr + V((0, 0, 2.0))
        else:
            k = smoothstep((t - (T_STRIKE - 0.02)) / 0.4)
            foc = (fr + V((0, 0, 2.0))).lerp(top + V((0, 0, 3.5)), k)
        lens = 24.0 if t < 82.62 else lerp(24.0, 32.0, smoothstep((t - 82.62) / 0.6))
        cam.key(t, loc=pos, target=tgt, focus=foc, lens=lens, interp='LINEAR')
    shake(cam.cam, T_STRIKE - 0.02, T_STRIKE + 0.18, amp=0.04, freq=18, seed=3)
    cam.cut(T0)
    bpy.context.scene.camera = cam.cam
    return cam


def glass_lights(jr, J, u, hB, coll):
    """Two tall strip lights behind the jar that only show in its glass (light-linked): they draw its edges and the
    hole's jagged rim against the dark room."""
    link = bpy.data.collections.new('lt.glass.receivers')
    for o in jr['pieces'] + [jr['thread']]:
        link.objects.link(o)
    for name, off, pw in (('strip.L', -u * 16 + hB * 14, 22000.0), ('strip.R', u * 17 + hB * 10, 18000.0),
                          ('strip.T', hB * 4 + Vector((0, 0, 22)), 12000.0),
                          ('strip.F', -u * 14 - hB * 26, 16000.0)):
        o = kit.area(f'lt.{name}', tuple(J + off + Vector((0, 0, 9))), tuple(J + Vector((0, 0, 6))), power=pw,
                     size=2.2, color='#FFE9D0', shape='RECTANGLE', coll=coll)
        o.data.size_y = 24.0
        o.data.diffuse_factor = 0.0
        o.data.volume_factor = 0.0
        o.data.specular_factor = 1.0
        o.data.transmission_factor = 0.0
        o.light_linking.receiver_collection = link
