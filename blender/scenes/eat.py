"""eat · 16.601-27.509 · "ChatGPT, please don't eat me alive / I'm upping my P(doom) / 'cause the future goes FOOM /
Trapped in the..."

The first chorus. The crowned Clawd, on his mug throne, opens his lid and eats the desk, one bite per kick (every beat
from 16.606): the sugar cube the researcher offers, two bites out of his own throne, a sticky-note pad, three pencils,
a book, and the pen the researcher holds out like a lance. DOOM 1: the brass gauge's needle jumps to 25. The title
P(DOOM) slams onto the desk in brass letters; on FOOM Clawd balloons to giant size in a burst of smoke and confetti,
blowing the camera back; then he pops back to toy size and a cardboard box drops over him: the Chinese room.

Shot list (song seconds; characters on twos, props that change with a pose switch on the twos grid; cameras, lights,
flying pieces, debris and smoke smooth at 24 fps):

 E1a reveal 16.601-17.250  35 mm at his eye level in front of the throne, the kneeling researcher's head in the
                           foreground, the gauge behind. 16.606 (kick) the lid flies open: teeth, angry eyes, a hungry
                           orange glow. 17.055 CHOMP: he lunges and takes the sugar cube out of the mitten (sugar grains
                           spray). Cut on "G" (17.24).
 E1b throne 17.250-18.375  45 mm from the front-right of the desk: the researcher, sitting down hard, stares at his
                           empty mitten. 17.514 and 17.965 CHOMP: two bites out of the mug's rim (scalloped notches,
                           ceramic chips); the researcher backs away; Clawd leaps off the throne at the lens, mouth
                           open. Cut on "T" (18.36, an odd frame: both puppets on ones across it).
 E2 buffet  18.375-20.250  40 mm f/16 motion-control truck ahead of him along the front of the desk (3/4 front). He dives
                           face first onto the sticky-note pad and swallows it on 18.424 (a flurry of torn notes);
                           18.871, 19.336, 19.783 bites the middles out of three pencils lying across his path (the
                           stubs spin away flat, shavings and paint chips spray); 20.236 the first bite of a book. The
                           researcher backs away ahead of him. Cut on "eat" (20.27).
 E3 book    20.250-21.333  45 mm close and low from the front: 20.689, 21.154 two more bites into the book's corner
                           (a scalloped cookie bite showing the page block; torn pages and cloth fly). Cut on "alive".
 E4 lance   21.333-22.750  40 mm from the front: Clawd hops onto the bitten book; the researcher stands en garde with
                           the desk pen levelled like a lance. 21.599 a snap at its tip; he thrusts; 22.056 CHOMP: the
                           front half is gone (ink and plastic splatter), he stares at the stub. Clawd chews on the
                           fills (22.415, 22.649), gulps and beams. Cut on "I'm" (22.76).
 G  gauge   22.750-24.167  70 mm push in on the brass gauge; the needle trembles; DOOM 1 at 23.873: it swings to 25
                           (the library's keys), the instrument jolts, a crash zoom (70 -> 118 mm) and a shake.
 T  title   24.167-25.583  34 mm from the front, above the leftovers (the bitten book in the corner). The brass letters
                           P(DOOM) fall into frame and slam down left to right from the kick 24.331 (0.03 s apart, dust
                           along their base, a jolt, Clawd's surprise take behind them); 24.784 he hops to peek over;
                           "goes" (25.18) he takes a huge breath and swells to 1.45x, glowing. Cut on FOOM.
 F  foom    25.583-27.509  35 mm front-left. FOOM (25.577-25.69, on ones): he balloons to 6x in a Mantaflow poof that
                           billows from behind him (he bursts forward out of it; a flash inside), 700 confetti, the
                           letters, pencil stubs and bitten book are blasted off the desk, the crown pops off; the camera
                           is blown back 60 cm. The giant looms with glowing eyes and smoke curling in his mouth, roars
                           on 26.602; at 26.80 he looks up (surprised), pops back to toy size (26.93) and a cardboard
                           box (the room scene's own model) drops over him (lands 27.19, dust), its window flap falls
                           open and he peers out: the Chinese room. Cut to `room` at 27.509.
"""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

from pdoom import chars, kit
from pdoom import timing as tm
from pdoom.fx import particles, smoke
from pdoom.fx import vis as fx_vis
from pdoom.sets import build_desk, geo
from pdoom.sets import materials as M
from pdoom.sets.props import build_book

from scenes.boot_common import Cam, flash_light, key_mats, shake
from scenes import eat_props as EP

FPS = tm.FPS
V = Vector
FAST = bool(os.environ.get('EAT_FAST'))       # skip the smoke bake while iterating

# ------------------------------------------------------------------------------------------------ times

T_START, T_END = 16.601, 27.509
KICKS = tm.kicks(16.5, 28.2)
K_OPEN, K_CUBE, K_MUG1, K_MUG2, K_PAD, K_P1, K_P2, K_P3, K_BOOK1, K_BOOK2, K_BOOK3, K_SNAP, K_PEN = KICKS[:13]
K_CHEW1, K_CHEW2, K_CHEW3 = KICKS[13:16]
DOOM1 = 23.873
K_SLAM = KICKS[17]            # 24.331
K_PEEK = KICKS[18]            # 24.784
K_FOOM = KICKS[20]            # 25.694 (the downbeat inside FOOM)


def _w(line, word):
    return tm.word(line, word)['start']


W_G = tm.syl(tm.word('ChatGPT', 'ChatGPT'), 1)       # 17.24
W_T = tm.syl(tm.word('ChatGPT', 'ChatGPT'), 3)       # 18.36
W_EAT = _w("please don't eat me alive", 'eat')        # 20.27
W_ALIVE = _w("please don't eat me alive", 'alive')    # 21.35
W_IM = _w("I'm upping my P(doom)", "I'm")             # 22.76
W_CAUSE = _w("'cause the future goes FOOM", "'cause")  # 24.32
W_GOES = _w("'cause the future goes FOOM", 'goes')    # 25.18
W_FOOM = _w("'cause the future goes FOOM", 'FOOM')    # 25.577


def fr(t):
    """Song time of the frame that shows t (cuts land on whole frames)."""
    return tm.t2f(t) / FPS


C_E1, C_E1B, C_E2, C_E3, C_E4, C_G, C_T, C_F = (fr(T_START), fr(W_G), fr(W_T), fr(W_EAT), fr(W_ALIVE), fr(W_IM),
                                               (tm.t2f(K_SLAM) - 4) / FPS, fr(W_FOOM))
# (T cuts in 4 frames before the slam on 24.331 so the letters are seen falling)
SW = 0.25 / FPS

# ------------------------------------------------------------------------------------------------ layout (world cm)

MUG = V((29.0, -13.0, 0.0))
SEAT = V((29.0, -13.0, 9.52 - 1.3 + 0.04))
K_RES = V((20.6, -13.8, 0.0))                 # the researcher kneels at the throne (training: 19.4)
HAND_UP = V((K_RES.x + 2.3, K_RES.y - 0.7, 8.4))
Y_PATH = -31.0                                  # the buffet line along the front of the desk
PAD_C = V((16.0, Y_PATH, 0.0))
PENCIL_X = (11.0, 6.6, 2.2)
BOOK_L, BOOK_W, BOOK_T = 17.0, 12.0, 3.4
BOOK_EDGE = -2.4                                # the book's near (right) edge, x
BOOK_C = V((BOOK_EDGE - BOOK_L / 2, Y_PATH, 0.0))
REACH = 2.6                                     # root x in front of a bite point (he faces -x)
ON_BOOK_X = BOOK_EDGE - 7.5                    # Clawd on the bitten book in E4: every leg on intact cover
RES_HIDE = V((BOOK_C.x - BOOK_L / 2 - 9.8, Y_PATH + 0.5, 0.0))
C_SPOT = V((-1.8, -8.0, 0.0))                   # title / FOOM spot: the room's box drops over it
TITLE_Y = -17.5
RES_T = V((-21.0, -25.0, 0.0))                  # the researcher during the title

EYE_HUNGER = '#FF5A1E'
PEN_HOLD = 12.9                                 # grip point on the pen, cm from its tip (length 13.8)
GIANT = 6.0


def build():
    sc = kit.new_scene('eat')
    d = build_desk(kit.collection('desk'), mood='night')
    A = d.anchors
    props = kit.collection('eat.props')
    fxc = kit.collection('eat.fx')
    protos = kit.collection('eat.protos')
    protos.hide_render = True

    # the desk as training left it: the mug turned for the throne, the pen gone (it stood where the maze was)
    d.mug.root.rotation_euler.z = math.radians(35.0)
    if d.pen is not None:
        d.pen.hide()
    if d.cable is not None:
        d.cable.hide()

    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=tuple(SEAT), yaw=-55.0)
    r = chars.Researcher(kit.collection('researcher'), name='researcher', loc=(K_RES.x, K_RES.y, 0), yaw=88.0)

    stuff = dict(d=d, c=c, r=r, props=props, fxc=fxc, protos=protos)
    shot_throne(stuff)
    shot_buffet(stuff)
    shot_book(stuff)
    shot_lance(stuff)
    shot_gauge(stuff)
    shot_title(stuff)
    shot_foom(stuff)
    finalize(stuff)
    cameras(stuff)
    lights(stuff)
    kit.post(bloom=0.3, bloom_threshold=1.1, vignette=0.24)
    chars.finish()
    if not FAST:
        from pdoom import fx
        fx.bake()
    from pdoom import lyrics as ly
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        lyrics(stuff)


def lyrics(S):
    """Revision 2: every sung word in the picture (docs/lib/lyrics.md).

    E1a        "ChatGPT" on the lyric stand beside the throne (Chat 16.6)
    E1b        ... and printed in white on the throne itself, a ChatGPT merch mug, letter by letter on the syllables
               (G 17.24, P 17.92, T 18.36), just under the rim he bites
    E2-E4      "please don't eat me alive" on the stand; in the lance shot Clawd eats the row word by word on his
               chomps (the snap 21.599, the pen 22.056, the chew 22.415)
    G          "I'm upping my P(doom)" on label-maker tape stuck on the gauge glass above the needle's hub, typed
               letter by letter as sung (P on 23.6, (DOOM) on the DOOM hit)
    T          "'cause the future goes" on the stand below the title letters
    F          FOOM in giant corrugated-cardboard letters that pop up at the giant's feet with the blast; then "Trapped in
               the Chinese" on a big stand in front of him as he shrinks and the box drops ("room" is the next scene's)
    """
    from pdoom import lyrics as ly
    from pdoom.lyrics import mats as LM
    from pdoom.lyrics import styles as LS
    c = S['c']
    st = ly._state()
    # ---- E1a: ChatGPT on a stand to the right of the throne (clear of the researcher's head)
    ly.line(5, words='ChatGPT', place='auto', t_end=C_E1B,
            spec=ly.StageSpec(cells=8.5, rows=1, u=(0.86, 0.82, 0.78), v=(0.38, 0.3, 0.46)))
    st['claimed'].discard((5, 0))

    # ---- E1b: the mug print, wrapped round the mug under the bitten rim
    class MugPrint(LS.Decal):
        name = 'print'
        font = 'sans'
        case = None
        gap = 0.03
        space = 0.4
        reveal = 'appear'
        exit = 'none'
        size = 1.5

        def mat(self):
            return LM.ink('#F4F0E6', name='eat.mugprint', speckle=0.0)
    R_MUG = 4.33
    ang0 = math.radians(-78.0)
    n0 = V((math.cos(ang0), math.sin(ang0), 0.0))
    pr = ly.line(5, words='ChatGPT', style=MugPrint(), place=ly.At(MUG + n0 * R_MUG + V((0, 0, 3.6)), face=n0,
                                                                   size=1.55),
                 t_show=C_E1B, t_end=T_END, exit='none', support='none')
    for pc in pr.pieces:
        th = pc.rest.x * 1.55 / R_MUG                      # arc angle of the letter's centre
        rl = R_MUG / 1.55
        pc.obj.location = (rl * math.sin(th), rl * (1.0 - math.cos(th)) - 0.02, pc.rest.z)
        pc.obj.rotation_euler = (0.0, 0.0, th)
    # ---- E2-E4: the rest of line 5 on the stand; eaten in the lance shot
    F6 = 6.0 / FPS
    eat_at = {1: K_SNAP, 2: K_PEN, 3: K_PEN, 4: K_CHEW1, 5: K_CHEW1}
    ly.line(5, words=(1, 6), place='auto', exit='eaten',
            exit_opts=dict(target=ly.mouth(c), t=lambda pc: eat_at[pc.word.index] - F6, frames=6),
            spec=ly.StageSpec(cells=15.0, rows=2))
    # ---- G: label-maker tape stuck on the gauge's glass above the hub, punched letter by letter as sung (the push-in
    #      and the crash zoom on the dial keep it in frame; a stand below the gauge falls out of the shot)
    ly.line(6, style='tape', place=ly.on_object(S['d'].gauge.dial, (0.0, 1.35, 0.97), (0, 0, 1), (0, 1, 0), size=0.5,
                                                lift=0.005),
            max_chars=11, t_show=C_G - 0.1, t_end=C_T - 0.5 / FPS, exit='none')
    # ---- T: below the title letters
    ly.line(7, words=(0, 4), place='auto', t_end=C_F, max_chars=12,
            spec=ly.StageSpec(cells=12.0, rows=2, v=(0.075, 0.11, 0.15)))
    # ---- F: FOOM in giant card letters, painted like a comic sound effect
    class Sfx(LS.Cardboard):
        def piece(self, ch, name, coll, word):
            me = LS.glyph_piece_mesh(ch, font=self.font, depth=0.16, bevel=0.012, name='sfx', mats=(sfx_m,))
            if me is None:
                return None, {}
            o = self.link(bpy.data.objects.new(name, me), coll)
            x0, x1, z0, z1 = LS.T.glyph_box(self.font, ch)
            return o, dict(w=x1 - x0, h=1.0, d=0.16, jitter=4.0)
    sfx_m = kit.mat('eat.foom.sfx', '#FFC21F', rough=0.35, coat=0.4, emit='#FFB000', emit_strength=0.35)
    ly.line(7, words='FOOM', style=Sfx(), place=ly.At((C_SPOT.x - 1.0, C_SPOT.y - 20.0, 0.0), face=(0.25, -1, 0),
                                                      size=11.0),
            reveal='pop', exit='topple', t_end=26.32)
    # ---- F: "Trapped in the Chinese" on a big stand in front of the giant
    ly.line(8, words=(0, 4), style='blocks', place=ly.At((C_SPOT.x - 2.0, C_SPOT.y - 20.5, 0.0), face=(0.3, -1, 0),
                                                         size=3.0),
            max_chars=14, t_show=26.1, t_end=T_END)
    ly.default('eat')


# ================================================================================================ bites


def lunge(c, tk, fwd=1.5, down=0.6, pitch=12.0, t_in=0.16, t_out=0.24):
    """A bite's head movement on top of chomp(): the body darts forward (and down, pitching) into t, then recoils."""
    from pdoom.chars.rig import bump
    c.T['body.loc'].add(tk - t_in, tk + t_out, lambda x: (0.0, -fwd * bump(x, tk - t_in, tk - 0.02, tk + t_out),
                                                          -down * bump(x, tk - t_in, tk - 0.02, tk + t_out)))
    c.T['body.rot'].add(tk - t_in, tk + t_out, lambda x: (pitch * bump(x, tk - t_in, tk - 0.02, tk + t_out), 0.0, 0.0))


def chew(c, t0, n=2, every=0.12, amount=0.14):
    """Munching after a bite: the lid bobs n times."""
    from pdoom.chars.rig import bump
    for k in range(n):
        a = t0 + k * every
        c.T['lid'].add(a, a + every, lambda x, a=a: amount * bump(x, a, a + every * 0.45, a + every))
        c.T['body.sq'].add(a, a + every, lambda x, a=a: 0.05 * bump(x, a, a + every * 0.5, a + every))


def bite(c, tk, *, wide=1.0, fwd=1.5, down=0.6, pitch=12.0, chews=2):
    c.chomp(tk, wide=wide)
    lunge(c, tk, fwd=fwd, down=down, pitch=pitch)
    if chews:
        chew(c, tk + 0.12, n=chews, every=0.1)


# ================================================================================================ E1 throne


def shot_throne(S):
    d, c, r, props, fxc, protos = S['d'], S['c'], S['r'], S['props'], S['fxc'], S['protos']
    # ---- continuity from training's last shot: crowned, arms folded, narrow eyes, a toothy smirk
    c.wear(T_START - 1.0, 'crown')
    c.eyes(T_START - 1.0, 'narrow')
    c.arms(T_START - 1.0, 'fold', dur=0.0)
    c.T['body.rot'].set(T_START - 1.0, (-6.0, 0.0, 0.0), 0.0)
    c.lid(T_START - 1.0, 0.16, dur=0.0)
    c.no_gait(T_START - 1.0, 18.05)
    # ---- 16.606: the lid flies open, the monster reveal
    c.lid(K_OPEN + 0.02, 0.62, dur=0.08, ease='out')
    c.T['lid'].add(K_OPEN + 0.1, K_CUBE - 0.3, lambda x: 0.07 * math.sin((x - K_OPEN) * 55.0))
    c.eyes(K_OPEN, 'angry', glow=2.2, color=EYE_HUNGER, dur=0.08)
    c.arms(K_OPEN + 0.05, 'high', dur=0.1)
    c.stretch(K_OPEN + 0.04, 0.16, 0.6)
    c.T['body.rot'].set(K_OPEN + 0.1, (-14.0, 0.0, 0.0), 0.12)
    c.look(K_OPEN + 0.25, HAND_UP + V((0, 0, 0.6)), turn=0.0, dur=0.15)
    # ---- 17.055: CHOMP the sugar cube out of his mitten
    c.lid(K_CUBE, 0.0, dur=0.07)
    c.chomp(K_CUBE, wide=1.15)
    c.T['body.rot'].set(K_CUBE - 0.08, (0.0, 0.0, 0.0), 0.12)
    lunge(c, K_CUBE, fwd=4.6, down=3.0, pitch=26.0, t_in=0.2, t_out=0.3)
    chew(c, K_CUBE + 0.14, n=2, every=0.1)
    c.arms(K_CUBE + 0.1, 'up', dur=0.15)
    c.eyes(K_CUBE + 0.18, 'happy')
    # ---- 17.514 / 17.965: two bites out of his own throne's rim
    fwd_dir = V((math.sin(math.radians(-55.0)), -math.cos(math.radians(-55.0)), 0.0))
    c.eyes(K_MUG1 - 0.25, 'angry')
    c.look(K_MUG1 - 0.2, SEAT + fwd_dir * 4.3 + V((0, 0, 1.0)), turn=0.0, dur=0.12)
    bite(c, K_MUG1, wide=1.1, fwd=1.4, down=2.4, pitch=30.0)
    c.T['root.yaw'].set(K_MUG2 - 0.1, -35.0, 0.18)
    bite(c, K_MUG2, wide=1.15, fwd=1.4, down=2.4, pitch=30.0)
    c.arms(K_MUG2 + 0.05, 'rest', dur=0.12)
    # ---- the leap off the throne, mouth open, toward the buffet line (lands at 18.40 in E2)
    land = V((PAD_C.x + 3.8 + REACH, Y_PATH, 0.0))
    c.hop(18.40, height=3.5, dur=0.34, to=(land.x, land.y, 0.0), at='land')
    c.T['root.yaw'].set(18.40, -90.0, 0.3)
    c.arms(18.18, 'up', dur=0.1)
    c.eyes(18.1, 'angry')

    # ---- the researcher: offering, frozen, robbed, scrambles away
    r.pose(T_START - 1.0, 'kneel_offer', dur=0.0)
    r.hand(T_START - 1.0, 'R', HAND_UP, dur=0.0, wrist=(-100.0, 0.0, 0.0))
    r.face(T_START - 1.0, 'scared')
    r.look(T_START - 0.9, c.anchor(T_START, 'face'), dur=0.0)
    r.face(K_OPEN + 0.06, 'shock')
    r.T['spine'].set(K_OPEN + 0.12, (4.0, 0.0, 0.0), 0.1)
    # he yanks his hand back and sits down hard
    r.pose(K_CUBE + 0.22, 'gasp', dur=0.14)
    r.face(K_CUBE + 0.05, 'shock')
    r.pose(17.42, 'sit', dur=0.14, face=False)
    palm = r.anchor(17.3, 'eyes') + V((4.5, -0.8, -2.6))      # held out in front of his chest, not at his face
    r.hand(17.42, 'R', palm, dur=0.14, wrist=(-30.0, 0.0, 0.0))
    r.look(17.45, palm, dur=0.12)
    r.face(17.45, 'wince')
    r.look(K_MUG1 + 0.05, c, dur=0.1)
    r.face(K_MUG1 + 0.02, 'scared')
    r.pose(K_MUG2 + 0.12, 'back_away', dur=0.2)
    r.walk(K_MUG2 + 0.12, K_MUG2 + 0.36, [(K_RES.x - 3.0, K_RES.y - 1.5)], face='back')
    # the sugar cube (as in training: held on his mitten) goes into the mouth on the chomp
    sugar_m = M.solid('training.sugar', '#FBF8F2', rough=0.55, sss=0.4, sss_radius=(0.4, 0.4, 0.4),
                      micro=(40.0, 0.25))
    cube = kit.box('eat.sugar', (1.2, 1.2, 1.2), (0, 0, 0), bevel=0.09, segments=2, m=sugar_m, coll=props)
    r.attach(cube, 'hand.R', offset=(0.0, -0.15, 0.55))
    EP.hide_from([cube], EP.pose_key(K_CUBE))
    S['cube'] = cube
    grain = EP.proto_cube('eat.proto.sugar', protos, sugar_m, 0.13)
    mouth_cube = HAND_UP + V((0.0, 0.0, 0.9))
    EP.debris('eat.sugar.grains', grain, mouth_cube, K_CUBE, count=36, direction=(-0.5, -0.3, 1.0),
              speed=(30, 110), cone=70, seed=11, coll=fxc)

    # ---- the mug takes two bites (Boolean cutters keyed in on the closing frames)
    bite_m = kit.mat('eat.ceramic.break', '#E7DCCB', rough=0.8)
    mug_body = next(o for o in d.mug.objects if o.name.startswith('mug.body'))
    mb = EP.Biteable('eat.mug', [mug_body], material=bite_m, parent_coll=props)
    for tk, yaw in ((K_MUG1, -55.0), (K_MUG2, -35.0)):
        dirv = V((math.sin(math.radians(yaw)), -math.cos(math.radians(yaw)), 0.0))
        rim = MUG + dirv * 4.25 + V((0, 0, 9.9))
        # the cutter's axis runs radially through the rim wall
        q = dirv.to_track_quat('Z', 'Y')
        Mw = Matrix.Translation(rim) @ q.to_matrix().to_4x4()
        mb.bite(EP.pose_key(tk), Mw, r=1.9, depth=3.0, teeth=12)
        glaze = EP.proto_chip('eat.proto.chip.glaze', protos, M.ceramic('mug.glaze', '#4E7087', rough=0.06),
                                      (0.45, 0.32, 0.12))
        inner = EP.proto_chip('eat.proto.chip.inner', protos, bite_m, (0.35, 0.25, 0.12), seed=2)
        EP.debris(f'eat.mug.chips{tk:.2f}', glaze, rim, tk, count=22, direction=tuple(dirv + V((0, 0, 1.2))),
                  speed=(50, 150), cone=55, seed=int(tk * 10), coll=fxc)
        EP.debris(f'eat.mug.crumbs{tk:.2f}', inner, rim, tk, count=26, direction=tuple(dirv + V((0, 0, 1.0))),
                  speed=(40, 120), cone=65, seed=int(tk * 10) + 1, coll=fxc)
    mb.bake()


# ================================================================================================ E2 buffet


def shot_buffet(S):
    d, c, r, props, fxc, protos = S['d'], S['c'], S['r'], S['props'], S['fxc'], S['protos']
    c.timing(C_E2 - 0.12, C_E2 + 0.1, 'ones')
    # the researcher flees along the line ahead of him, backing away, looking back (he ran round the throne)
    r.timing(C_E2 - 0.12, C_E2 + 0.1, 'ones')
    r.place(C_E2 - SW, loc=(9.0, Y_PATH + 7.0), yaw=90.0)
    r.pose(C_E2 - SW, 'back_away', dur=0.0)
    r.face(C_E2 - SW, 'scared')
    r.walk(C_E2 + 0.02, 20.2, [(-2.0, Y_PATH + 8.5), (-13.0, Y_PATH + 9.0)], face='back')
    r.look(C_E2 + 0.1, c, dur=0.1)
    r.look(19.2, c, dur=0.15)
    # ---- the pad: the desk's sticky notes moved onto the line; swallowed whole on landing
    nr = d.notes.root
    nr.location = PAD_C
    nr.rotation_euler.z = math.radians(8.0)
    pad_objs = [o for o in d.notes.objects if 'onlaptop' not in o.name]
    kf = EP.pose_key(K_PAD)
    EP.hide_from(pad_objs, kf)
    c.no_gait(18.0, 18.45)
    c.eyes(18.30, 'angry')
    bite(c, K_PAD, wide=1.15, fwd=1.6, down=1.4, pitch=16.0, chews=1)
    c.squash(18.42, 0.22, 0.5)
    c.arms(18.45, 'rest', dur=0.1)
    mouth = V((PAD_C.x + 2.0, Y_PATH, 2.2))
    for k, (col, n) in enumerate((('#F2D54B', 50), ('#F2A0B8', 22))):
        bitp = EP.proto_chip(f'eat.proto.note{k}', protos, M.paper(f'note.{col}', col, tile=25), (1.5, 1.3, 0.02),
                             seed=13 + k)
        bitp.data.materials[0].use_backface_culling = False
        EP.debris(f'eat.notes.flurry{k}', bitp, mouth, K_PAD, count=n, direction=(0.3, -0.5, 1.0),
                  speed=(120.0, 380.0), cone=65, drag=5.0, spin=12.0, seed=21 + k, coll=fxc)
    # ---- three pencils lying across the line; he bites their middles out, the ends spin away
    paints = ('#E9B820', '#C23A2E', '#1F3A66')
    wood = M.solid('pencil.wood', '#D9B48A', rough=0.7, micro=(12.0, 0.1))
    for i, (px, tk, paint) in enumerate(zip(PENCIL_X, (K_P1, K_P2, K_P3), paints)):
        A, Mi, B = EP.pencil_pieces(props, f'eat.pencil{i}', paint, cut=(5.3, 12.3))
        skew = (-6.0, 5.0, -3.0)[i]
        # lying along y (eraser end at -y side), axis horizontal
        rot = Matrix.Rotation(math.radians(skew), 4, 'Z') @ Matrix.Rotation(math.radians(-90), 4, 'X')
        base = V((px, Y_PATH - 8.8, 0.4))
        M0 = Matrix.Translation(base) @ rot
        EP.place(Mi, M0)
        kfk = EP.pose_key(tk)
        EP.hide_from([Mi], kfk)
        # the ends: A (eraser, near side -y) skitters toward the camera, B (tip) away, spinning flat
        t_fly = kfk / FPS
        hA = geo.hash01('pA', i)
        hB = geo.hash01('pB', i)
        for o, v0, wz in ((A, (-20 - 30 * hA, -70 - 40 * hA, 90 + 50 * hA), 12.0 + 8 * hA),
                          (B, (-15 - 30 * hB, 60 + 40 * hB, 95 + 45 * hB), -11.0 - 8 * hB)):
            cl = EP.recenter(o)
            Mo = M0 @ Matrix.Translation(cl)
            EP.place(o, Mo)
            EP.fly(o, t_fly, Mo, v0, (0.0, 0.0, wz), t_end=T_END + 0.2, half=0.4, keep_flat=True,
                         t_pre=t_fly - 1.0 / FPS)
            S.setdefault('stubs', []).append(o)
        # Clawd steps up to it and bites
        target_x = px + REACH
        c.move(tk - 0.36, tk - 0.1, [(target_x, Y_PATH)], face=-90.0)
        bite(c, tk, wide=1.0, fwd=1.4, down=0.8, pitch=8.0, chews=1)
        mouth = V((px, Y_PATH, 1.4))
        shav = EP.proto_shaving(f'eat.proto.shaving{i}', protos, wood, M.enamel(f'pencil.paint.{paint}', paint,
                                                                                 rough=0.35, coat=0.6))
        EP.debris(f'eat.pencil{i}.shavings', shav, mouth, tk, count=18, direction=(0.4, -0.5, 1.0), speed=(40, 130),
                  cone=70, seed=31 + i, coll=fxc, scale=1.2)
        chip = EP.proto_chip(f'eat.proto.paint{i}', protos, M.enamel(f'pencil.paint.{paint}', paint, rough=0.35,
                                                                      coat=0.6), (0.3, 0.2, 0.06), seed=5 + i)
        EP.debris(f'eat.pencil{i}.chips', chip, mouth, tk, count=24, direction=(0.2, 0.3, 1.0), speed=(40, 150),
                  cone=75, seed=41 + i, coll=fxc)
    # ---- the book: built fresh (a cloth hardback lying across the end of the line), first bite at 20.236
    br = build_book(props, 'eat.book', BOOK_L, BOOK_W, BOOK_T, '#7A2E2A')
    br.location = BOOK_C
    br.rotation_euler.z = math.radians(0.0)
    book_objs = [o for o in geo.descendants(br) if o.type == 'MESH']
    pages = next(o for o in book_objs if o.name.endswith('pages'))
    pages_m = pages.data.materials[0]
    bb = EP.Biteable('eat.book', book_objs, material=pages_m, parent_coll=props, parent=br)
    S['book'], S['book_bites'] = br, bb
    # the book is 3.4 cm thick and his jaw line is at 3.55: he stands back by the lunge and stays level, so his face
    # only meets the book's end face (lunge 1.0 + the chomp's own 0.45) and the bite opens in front of it
    c.move(K_BOOK1 - 0.36, K_BOOK1 - 0.1, [(BOOK_EDGE + REACH + 0.9, Y_PATH)], face=-90.0)
    book_bite(S, K_BOOK1, V((BOOK_EDGE + 0.4, Y_PATH, 0)), r=3.4)
    bite(c, K_BOOK1, wide=1.2, fwd=1.0, down=-0.1, pitch=5.0, chews=1)
    c.eyes(K_BOOK1 + 0.2, 'happy')


def book_bite(S, tk, p, r=3.0):
    bb, fxc, protos = S['book_bites'], S['fxc'], S['protos']
    Mw = Matrix.Translation((p.x, p.y, BOOK_T / 2))
    bb.bite(EP.pose_key(tk - (0.06 if tm.SMOOTH else 0.0)), Mw, r=r, depth=BOOK_T + 3.0, teeth=16)
    paper = EP.proto_chip('eat.proto.page', protos, M.paper('eat.page', '#EDE3CB', tile=20), (0.9, 0.6, 0.02), seed=9)
    cloth = EP.proto_chip('eat.proto.cloth', protos, kit.mat('eat.cloth', '#7A2E2A', rough=0.8, sheen=0.3),
                          (0.5, 0.35, 0.05), seed=4)
    c0 = V((p.x, p.y, BOOK_T))
    EP.debris(f'eat.book.pages{tk:.2f}', paper, c0, tk, count=40, direction=(0.3, -0.2, 1.0), speed=(40, 160),
              cone=70, drag=3.0, spin=14, seed=int(tk * 7), coll=fxc)
    EP.debris(f'eat.book.cloth{tk:.2f}', cloth, c0, tk, count=16, direction=(0.2, 0.2, 1.0), speed=(40, 140),
              cone=70, seed=int(tk * 7) + 3, coll=fxc)


# ================================================================================================ E3 book


def shot_book(S):
    c, r = S['c'], S['r']
    # two more bites, lunging from the edge (a scalloped cookie bite)
    # (short, level lunges: his face stays in the first bite's hole instead of sinking through the cover)
    bite(c, K_BOOK2, wide=1.2, fwd=1.2, down=-0.1, pitch=5.0, chews=1)
    book_bite(S, K_BOOK2, V((BOOK_EDGE - 1.6, Y_PATH + 2.4, 0)), r=3.0)
    c.T['root.yaw'].set(K_BOOK3 - 0.12, -104.0, 0.15)
    bite(c, K_BOOK3, wide=1.25, fwd=1.2, down=-0.1, pitch=5.0, chews=2)
    book_bite(S, K_BOOK3, V((BOOK_EDGE - 2.0, Y_PATH - 2.6, 0)), r=3.2)
    S['book_bites'].bake()
    c.eyes(K_BOOK3 + 0.2, 'happy')
    # the researcher cowers behind the book with the pen he grabbed (placed at the cut; he ran here off-screen)
    r.place(C_E3 - SW, loc=(RES_HIDE.x, RES_HIDE.y), yaw=90.0)
    r.no_gait(C_E3 - 0.2, C_E3 + 0.1)
    r.pose(C_E3 - SW, 'cower', dur=0.0)
    r.face(C_E3 - SW, 'scared')
    r.look(C_E3 + 0.1, c, dur=0.1)
    r.fidget(C_E3, W_ALIVE, 1.4)
    r.nod(K_BOOK2 + 0.05, n=1, amount=-10.0, every=0.2)
    r.nod(K_BOOK3 + 0.05, n=1, amount=-10.0, every=0.2)


# ================================================================================================ E4 lance


def mitten_centre(r, t, side='R'):
    """World centre of the researcher's mitten at song time t: the wrist as the arm solver places it plus the
    mitten's offset along the hand bone, as the rig poses it."""
    from pdoom.chars import researcher as RS
    S0 = RS.SH[side]
    W, E, _, rw = RS.clear_arm(side, V(r.T[f'hand.{side}'].at(t)), r.T[f'wrist.{side}'].at(t),
                               r._head_local(r.T['head'].at(t)), r._pole_a[side])
    Rh = RS._forearm_rot(side, S0, E, W, RS._bend_dir(side, S0, W)) @ rw.to_matrix()
    return r._spine_world(t) @ (W + Rh @ RS.MITTEN_C)


def shot_lance(S):
    d, c, r, props, fxc, protos = S['d'], S['c'], S['r'], S['props'], S['fxc'], S['protos']
    # en garde: both mittens low in front, the pen levelled like a lance
    chars.POSES['lance'] = dict(spine=(6, 0, 0), head=(4, 0, 0), hands=((0.55, -2.6, 4.9), (-0.45, -3.3, 5.2)),
                                wrist=((-70, 0, 0), (-80, 0, 0)), thigh=((-10, 0, 0), (12, 0, 0)), shin=(6, 14),
                                face='determined')
    # Clawd hops up onto the bitten book, facing the researcher
    on_book = V((ON_BOOK_X, Y_PATH, BOOK_T))
    c.hop(W_ALIVE + 0.12, height=3.0, dur=0.3, to=(on_book.x, on_book.y, on_book.z), at='land')
    c.T['root.yaw'].set(W_ALIVE + 0.12, -90.0, 0.2)
    c.eyes(W_ALIVE, 'angry')
    c.arms(W_ALIVE + 0.1, 'up', dur=0.12)
    # 21.599: a snap at the lance
    bite(c, K_SNAP, wide=1.0, fwd=1.6, down=0.2, pitch=4.0, chews=0)
    # 22.056: CHOMP the pen
    bite(c, K_PEN, wide=1.25, fwd=2.0, down=0.3, pitch=6.0, chews=0)
    chew(c, K_CHEW1 - 0.05, n=1, every=0.16, amount=0.22)
    chew(c, K_CHEW2 - 0.05, n=1, every=0.16, amount=0.22)
    c.eyes(K_PEN + 0.15, 'happy')
    c.stretch(22.70, 0.18, 0.5)                   # the gulp
    c.arms(22.60, 'cheer', dur=0.12)

    # the researcher: stands up en garde with the pen, flinches at the snap, thrusts, loses half of it
    r.pose(W_ALIVE + 0.05, 'lance', dur=0.2)
    r.face(W_ALIVE + 0.05, 'determined')
    r.look(W_ALIVE + 0.1, c, dur=0.12)
    r.T['spine'].set(K_SNAP + 0.1, (-14.0, 0.0, 0.0), 0.08)
    r.face(K_SNAP + 0.02, 'shock')
    r.T['spine'].set(21.92, (9.0, 0.0, 0.0), 0.14)
    r.face(21.85, 'determined')
    r.pose(K_PEN + 0.16, 'gasp', dur=0.12)
    r.face(K_PEN + 0.04, 'shock')
    r.pose(22.42, 'hold', dur=0.2, face=False)
    r.look(22.45, None, dur=0.15)
    r.face(22.55, 'sad')

    # the pen: held by its button end, pointing at Clawd, following his right wrist on the twos grid
    front, back = EP.pen_pieces(props, 'eat.pen', cut=6.2)
    grip = kit.empty('eat.pen.grip', (0, 0, 0), props)
    for o in (front, back):
        # the grip's local +Z points at Clawd: the pen turned over (tip forward), held 0.9 cm from its button end
        # (the button just shows behind his fist and stays clear of his coat)
        geo.attach(o, grip, (0.0, 0.0, PEN_HOLD), (math.pi, 0.0, 0.0))
    # a slimmer barrel (0.68 cm, was 0.94) so his mitten closes round it instead of vanishing inside it
    grip.scale = (0.72, 0.72, 1.0)
    S['pen_grip'] = grip

    def grip_M(t):
        # the grip point is the centre of his right mitten (the wrist target put the barrel up his sleeve)
        w = mitten_centre(r, t, 'R')
        tgt = c.anchor(t, 'mouth') + V((0.0, 0.0, 0.8))
        dv = (tgt - w)
        if dv.length < 1e-3:
            dv = V((1, 0, 0))
        q = dv.normalized().to_track_quat('Z', 'Y')
        return Matrix.Translation(w) @ q.to_matrix().to_4x4()
    S['grip_M'] = grip_M
    kf_pen = EP.pose_key(K_PEN)
    EP.show_from([back], C_E4 * FPS - 0.5, C_G * FPS - 0.5)
    EP.show_from([front], C_E4 * FPS - 0.5, kf_pen)
    S['pen_front'], S['pen_back'] = front, back
    # ink and plastic
    ink = EP.proto_drop('eat.proto.ink', protos, EP.pen_mats()['ink'], 0.12)
    shard = EP.proto_chip('eat.proto.penshard', protos, M.plastic('pen.body', '#101218', rough=0.25, coat=0.5),
                          (0.35, 0.2, 0.08), seed=7)
    S['pen_fx'] = (ink, shard)


# ================================================================================================ G gauge


def shot_gauge(S):
    d, c, r = S['d'], S['c'], S['r']
    g = d.gauge
    g.tremble(23.0, DOOM1 - 0.02, amp=0.9, rate=16.0, seed=3)
    g.jolt(DOOM1, amp_deg=4.0, dur=0.4)
    # Clawd moves to the title spot off-screen (the gauge is a cutaway)
    c.timing(C_G - 0.1, C_G + 0.1, 'ones')
    c.place(C_G - SW, loc=(C_SPOT.x, C_SPOT.y, 0.0), yaw=0.0)
    c.no_gait(C_G - 0.1, C_G + 0.2)
    c.arms(C_G - SW, 'rest', dur=0.0)
    c.eyes(C_G - SW, 'happy', glow=0.0, dur=0.0)
    r.timing(C_G - 0.1, C_G + 0.1, 'ones')
    r.place(C_G - SW, loc=(RES_T.x, RES_T.y), yaw=math.degrees(math.atan2(C_SPOT.x - RES_T.x,
                                                                          -(C_SPOT.y - RES_T.y))))
    r.no_gait(C_G - 0.1, C_G + 0.2)
    r.pose(C_G - SW, 'hold', dur=0.0, face=False)
    r.face(C_G - SW, 'sad')


# ================================================================================================ T title


def shot_title(S):
    d, c, r, props, fxc, protos = S['d'], S['c'], S['r'], S['props'], S['fxc'], S['protos']
    brass = M.brass('eat.title.brass', '#D2A650', rough=0.2)
    letters = EP.title_letters(props, 'P(DOOM)', size=6.2, m=brass)
    S['letters'] = letters
    # slam: each letter falls from above and hits the desk on the kick, a hair apart (left to right)
    x0 = C_SPOT.x - 0.5
    for k, (ch, o) in enumerate(letters):
        x = x0 + o['x']
        t_hit = K_SLAM + 0.03 * k
        h0 = 60.0
        tf = math.sqrt(2 * h0 / 981.0)
        yaw = math.radians((geo.hash01('ty', k) - 0.5) * 6.0)
        o.rotation_mode = 'XYZ'

        def pos(t, x=x, t_hit=t_hit, tf=tf, h0=h0, k=k, yaw=yaw):
            if t < t_hit - tf:
                return V((x, TITLE_Y, h0)), (0.0, 0.0, yaw)
            if t < t_hit:
                u = (t_hit - t)
                return V((x, TITLE_Y, 0.5 * 981.0 * u * u)), (0.0, 0.0, yaw)
            a = t - t_hit
            hop = 0.9 * max(0.0, math.sin(a * math.pi / 0.11)) if a < 0.11 else 0.0
            rock = math.radians(7.0 * math.exp(-a * 9.0) * math.sin(a * 38.0 + k)) if a < 0.8 else 0.0
            return V((x, TITLE_Y, hop)), (rock, 0.0, yaw)
        o.rotation_mode = 'QUATERNION'
        for t in EP.frame_times(C_T - 0.1, C_F + 0.05):
            p, e = pos(t)
            o.location = p
            o.rotation_quaternion = Euler(e, 'XYZ').to_quaternion()
            o.keyframe_insert('location', frame=t * FPS)
            o.keyframe_insert('rotation_quaternion', frame=t * FPS)
        o['pos0'] = (x, TITLE_Y, 0.0)
        o['yaw0'] = yaw
        fx_vis(o, C_T - 0.5 / FPS, None)
    # dust kicked up along the base of the letters
    dust_m = kit.mat('eat.dust', '#9C8C7A', rough=1.0)
    dust = EP.proto_cube('eat.proto.dust', protos, dust_m, 0.08)
    for k, sx in enumerate((-1, 1)):
        EP.debris(f'eat.title.dust{k}', dust, (C_SPOT.x + sx * 8.0, TITLE_Y - 0.6, 0.2), K_SLAM, count=90,
                  direction=(sx * 1.0, -0.6, 0.35), speed=(40, 160), cone=50, drag=6.0, spin=6, seed=61 + k,
                  coll=fxc, spread=(16.0, 0.3))
    # Clawd behind the letters: jolted by the slam, peeks over on 24.784, breathes in on "goes"
    c.take(K_SLAM + 0.02, hold=0.3, jump=1.0)
    c.hop(K_PEEK, height=3.2, dur=0.36, at='apex')
    c.eyes(K_PEEK - 0.1, 'open')
    c.look(K_PEEK + 0.05, V((C_SPOT.x, TITLE_Y, 4.0)), turn=0.0, dur=0.1)
    c.eyes(W_GOES, 'narrow')
    c.scale_to(W_FOOM - 0.02, 1.45, dur=0.38, ease='inout')      # the huge breath
    c.lid(W_GOES + 0.05, 0.2, dur=0.2)
    c.lid(W_FOOM - 0.04, 0.0, dur=0.08)
    c.arms(W_GOES + 0.1, 'out', dur=0.2)
    c.look(W_GOES + 0.1, None, dur=0.15)
    # the researcher watches, awed, then scared of the breath
    r.look(K_SLAM + 0.08, V((C_SPOT.x - 6.0, TITLE_Y, 3.0)), dur=0.12)
    r.jump(K_SLAM + 0.02, height=1.0, dur=0.28)
    r.face(K_SLAM + 0.04, 'shock')
    r.face(K_PEEK + 0.2, 'awe')
    r.look(W_GOES + 0.1, c, dur=0.15)
    r.face(W_GOES + 0.15, 'scared')
    r.pose(W_GOES + 0.2, 'back_away', dur=0.25)


# ================================================================================================ F foom


def shot_foom(S):
    d, c, r, props, fxc, protos = S['d'], S['c'], S['r'], S['props'], S['fxc'], S['protos']
    t0 = W_FOOM
    # ---- FOOM: balloon to giant size on ones
    c.timing(t0 - 0.05, t0 + 0.35, 'ones')
    c.scale_to(t0 + 0.11, GIANT * 0.85, dur=0.12, ease='out')
    c.scale_to(t0 + 0.45, GIANT, dur=0.3, ease='back')
    c.eyes(t0, 'angry', glow=3.0, color=EYE_HUNGER, dur=0.06)
    c.lid(t0 + 0.08, 1.0, dur=0.1)
    c.lid(t0 + 0.5, 0.45, dur=0.2)
    c.arms(t0 + 0.06, 'high', dur=0.1)
    c.wear(t0 + 0.02, 'crown', on=False)
    # the giant roars and looms
    c.T['body.rot'].set(t0 + 0.4, (-10.0, 0.0, 0.0), 0.2)
    c.lid(26.50, 0.35, dur=0.2)
    c.lid(26.64, 0.95, dur=0.1)                # a roar on the kick
    c.arms(26.6, 'cheer', dur=0.1)
    c.look(26.0, (RES_T.x, RES_T.y, 6.0), turn=0.0, dur=0.2)
    # ---- pop back to toy size, a sheepish look, and the box
    c.eyes(26.80, 'surprised')
    c.look(26.80, V((C_SPOT.x, C_SPOT.y - 20.0, 120.0)), turn=0.0, dur=0.08)
    c.lid(26.80, 0.1, dur=0.06)
    t_pop = 26.93
    c.timing(t_pop - 0.05, t_pop + 0.2, 'ones')
    c.lid(t_pop - 0.02, 0.0, dur=0.06)
    c.scale_to(t_pop + 0.1, 1.0, dur=0.12, ease='back')
    c.eyes(t_pop + 0.02, 'surprised', glow=0.0, dur=0.05)
    c.arms(t_pop + 0.08, 'rest', dur=0.08)
    c.T['body.rot'].set(t_pop + 0.05, (0.0, 0.0, 0.0), 0.06)
    c.look(t_pop + 0.2, None, dur=0.1)
    c.look(27.02, V((C_SPOT.x, C_SPOT.y, 40.0)), turn=0.0, dur=0.08)
    c.eyes(27.05, 'small')
    # ---- smoke and confetti
    center = V((C_SPOT.x, C_SPOT.y + 9.0, 16.0))          # behind him: he bursts forward out of the cloud
    if not FAST:
        # a smaller emitter blowing for longer, with more random velocity, so the cloud billows out of it instead
        # of filling a 44 cm ball evenly (the old hard-edged grey disc); the material breaks it up further
        sm = smoke.burst('eat.foom', center=tuple(center), t0=t0, t_end=T_END + 0.1, radius=13.0, emit=0.24,
                         size=(150.0, 130.0, 100.0), res=128, grow=0.25, color='#EDE6DC', density=0.8,
                         dissolve=0.8, beta=2.6, swirl=9.0)
        foom_smoke_fix(sm)
        S['smoke'] = sm
    particles.confetti('eat.foom.confetti', center=(C_SPOT.x, C_SPOT.y, 30.0), t0=t0 + 0.08, count=700,
                       speed=(900.0, 2000.0), direction=(0.0, -0.2, 1.0), cone=70, drag=40.0, sway=2.5, spin=9.0,
                       size=(1.1, 0.65), seed=7, coll=fxc)
    # ---- the letters are blasted toward the lens and off the desk
    for k, (ch, o) in enumerate(S['letters']):
        x, y, z = o['pos0']
        h = lambda *a: geo.hash01('blast', k, *a)
        dx = x - C_SPOT.x
        side = 1.0 if dx >= 0 else -1.0
        v0 = V((side * (220.0 + 140.0 * h('x')) + dx * 10.0, -120.0 - 90.0 * h('y'), 200.0 + 150.0 * h('z')))
        w0 = V(((h('wx') - 0.5) * 24.0, (h('wy') - 0.5) * 24.0, (h('wz') - 0.5) * 16.0))
        tb = t0 + 0.04 + 0.01 * abs(k - 3)
        M0 = Matrix.Translation((x, y, z)) @ Matrix.Rotation(o['yaw0'], 4, 'Z')
        # the title keys end at C_F; the blast re-keys from tb on
        EP.fly(o, tb, M0, v0, w0, t_end=T_END + 0.1, half=0.1, bounce=0.2)
    # ---- the blast clears the desk: the bitten book and the pencil stubs fly off the front edge
    for k, o in enumerate([S['book']] + S.get('stubs', [])):
        bpy.context.scene.frame_set(int(round(t0 * FPS)))
        Mw = o.matrix_world.copy()
        p = Mw.to_translation()
        away = (p - C_SPOT)
        away.z = 0.0
        away = away.normalized() if away.length > 1e-3 else V((0, -1, 0))
        h = lambda *a: geo.hash01('clear', k, *a)
        v0 = away * (260.0 + 160.0 * h('s')) + V((-60.0, -40.0, 130.0 + 100.0 * h('z')))
        if o is S.get('book'):
            v0 = V((-330.0, -60.0, 110.0))
        w0 = V(((h('x') - 0.5) * 20.0, (h('y') - 0.5) * 20.0, (h('w') - 0.5) * 14.0))
        dist = (p - C_SPOT).length
        EP.fly(o, t0 + 0.03 + dist / 900.0, Mw, v0, w0, t_end=T_END + 0.1, half=0.5, bounce=0.2)
    # ---- the crown pops off and flutters down
    crown = chars.props.make('crown', props, 'eat.crown.free')
    from pdoom.chars.clawd import BONES, TOP
    from pdoom.chars.props import _Ry, _T
    Mrest = _T((0.35, 0.15, TOP - 0.12)) @ _Ry(9)
    fk = c._fk(t0 + 0.02)
    Mh = c.rig.matrix_world @ fk['hat'] @ _T(-V(BONES['hat'])) @ Mrest
    Mh = Matrix.Translation(Mh.to_translation()) @ Mh.to_quaternion().to_matrix().to_4x4()
    land = V((C_SPOT.x + 19.5, C_SPOT.y - 18.0, 0.0))     # clear of the box's window flap (x -9..12)
    t_up = t0 + 0.04

    def crown_M(t):
        if t < t_up:
            return Mh
        a = t - t_up
        # thrown up with the growth, then flutters down (rocking, spinning) onto the desk by 27.2
        T_fall = 27.2 - t_up
        u = min(1.0, a / T_fall)
        up = 42.0 * math.sin(math.pi * min(1.0, u * 1.25)) if u < 0.8 else 0.0
        base = Mh.to_translation().lerp(land + V((0, 0, 0.9)), u ** 1.6)
        pz = base.z + up * (1 - u)
        rock = math.radians(28.0 * math.sin(a * 11.0) * (1 - u))
        spin = a * 7.0 * (1 - u * 0.7)
        R = Matrix.Rotation(spin, 4, 'Z') @ Matrix.Rotation(rock, 4, 'Y')
        return Matrix.Translation((base.x, base.y, max(0.9, pz))) @ R
    key_mats(crown, crown_M, t0 - 0.1, T_END + 0.1, spans=((t0 - 0.2, T_END + 0.2, 'ones'),))
    kit.visible(crown, t0 + 0.02 - 0.5 / FPS, None)
    # ---- the flash inside the cloud
    flash_light('eat.foom.flash', V((C_SPOT.x, C_SPOT.y - 16.0, 14.0)), t0, fxc, power=160000.0, color='#FFC890',
                decay=0.22, radius=10.0)
    # ---- the researcher is knocked back onto his seat
    r.walk(t0 + 0.05, t0 + 0.3, [(RES_T.x - 5.0, RES_T.y - 3.0)], face='back')
    r.pose(t0 + 0.3, 'sit', dur=0.2, face=False)
    r.face(t0 + 0.06, 'shock')
    r.look(t0 + 0.4, c.anchor(t0 + 0.5, 'face'), dur=0.2)
    # ---- the box drops over him
    drop_box(S)


def foom_smoke_fix(sm):
    """Scene-side fixes to fx.smoke.burst: bake only the FOOM's frames (the library sets cache_frame_start before
    cache_frame_end, and Blender clamps the start to the old end, 250) and let the cloud glow faintly with its own
    density so it reads as a bright cartoon poof in the night room."""
    dom = sm['domain']
    ds = dom.modifiers['fluid'].domain_settings
    f0 = int(math.floor(W_FOOM * FPS)) - 2
    f1 = int(math.ceil((T_END + 0.1) * FPS)) + 1
    ds.cache_frame_end = f1
    ds.cache_frame_start = f0
    m = sm['material']
    nt = m.node_tree
    pv = next(n for n in nt.nodes if n.bl_idname == 'ShaderNodeVolumePrincipled')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = 'density'
    mul = nt.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.inputs[1].default_value = 0.08
    nt.links.new(at.outputs['Fac'], mul.inputs[0])
    nt.links.new(mul.outputs[0], pv.inputs['Emission Strength'])
    # billows: the density is modulated by drifting 4D noise (a pure function of song time, keyed linearly), so
    # the cloud reads as lumps with a ragged edge rather than an even ball
    d0 = pv.inputs['Density'].default_value
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.noise_dimensions = '4D'
    noi.inputs['Scale'].default_value = 1.0 / 9.0
    noi.inputs['Detail'].default_value = 3.0
    noi.inputs['Roughness'].default_value = 0.55
    nt.links.new(mp.outputs['Vector'], noi.inputs['Vector'])
    rng = nt.nodes.new('ShaderNodeMapRange')
    rng.inputs['From Min'].default_value = 0.36
    rng.inputs['From Max'].default_value = 0.64
    rng.inputs['To Min'].default_value = d0 * 0.12
    rng.inputs['To Max'].default_value = d0 * 1.5
    nt.links.new(noi.outputs['Fac'], rng.inputs['Value'])
    nt.links.new(rng.outputs['Result'], pv.inputs['Density'])
    for t in (W_FOOM - 0.2, T_END + 0.2):
        mp.inputs['Location'].default_value = (0.0, 0.0, -14.0 * (t - W_FOOM))
        mp.inputs['Location'].keyframe_insert('default_value', frame=t * FPS)
        noi.inputs['W'].default_value = 0.6 * (t - W_FOOM)
        noi.inputs['W'].keyframe_insert('default_value', frame=t * FPS)
    for fc in kit.fcurves(nt):
        fc.extrapolation = 'LINEAR'
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    pv.inputs['Emission Color'].default_value = kit.srgb('#FFE9CF')
    pv.inputs['Anisotropy'].default_value = 0.1


def drop_box(S):
    """The Chinese room's cardboard box (the room scene's own model) falls over the toy-sized Clawd."""
    props = S['props']
    bc = kit.collection('eat.box', props)
    t_land = 27.19
    try:
        from scenes import room_box as RB
        before = set(bpy.data.objects)
        b = RB.build_box(bc)
        RB.build_slot(bc, b)
        made = [o for o in bpy.data.objects if o not in before]
        flap, floor = b.flap, b.floor

    except Exception as e:  # noqa: BLE001
        print(f'[run] eat: room box unavailable ({e}); a plain box stands in')
        made = [geo.box('eat.box.plain', (28.0, 20.0, 16.0), (2.0, -10.0, 8.0),
                        m=M.cardboard('eat.cardboard'), coll=bc)]
        flap, floor = None, None
    root = kit.empty('eat.box.root', (0, 0, 0), bc)
    for o in made:
        if o.parent is None:
            mw = o.matrix_world.copy()
            o.parent = root
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = mw
    if floor is not None:
        floor.hide_render = True
    # the window flap starts closed and falls open after the landing
    if flap is not None:
        fold = flap.rotation_euler.x
        flap.rotation_euler.x = 0.0
        for t in EP.frame_times(26.5, T_END + 0.1):
            a = t - (t_land + 0.06)
            if a <= 0:
                ang = 0.0
            else:
                u = min(1.0, a / 0.2)
                ang = fold * u * u
                if a > 0.2:
                    ang = fold - math.radians(6.0) * math.exp(-(a - 0.2) * 14.0) * abs(math.sin((a - 0.2) * 30.0))
            flap.rotation_euler.x = ang
            flap.keyframe_insert('rotation_euler', frame=t * FPS, index=0)
    h0 = 70.0
    tf = math.sqrt(2 * h0 / 981.0)
    for t in EP.frame_times(26.4, T_END + 0.1):
        if t < t_land - tf:
            z = h0
        elif t < t_land:
            u = t_land - t
            z = 0.5 * 981.0 * u * u
        else:
            a = t - t_land
            z = 0.6 * max(0.0, math.sin(a * math.pi / 0.09)) if a < 0.09 else 0.0
        root.location = (0.0, 0.0, z)
        root.keyframe_insert('location', frame=t * FPS)
    for o in made:
        if o is not floor:
            kit.visible(o, t_land - tf - 0.1, None)
    # dust from under the walls
    dust = bpy.data.objects.get('eat.proto.dust')
    if dust is not None:
        for k, (p, dv) in enumerate((((2, -20.5, 0.2), (0, -1, 0.3)), ((-12.5, -10, 0.2), (-1, 0, 0.3)),
                                     ((16.5, -10, 0.2), (1, 0, 0.3)))):
            EP.debris(f'eat.box.dust{k}', dust, p, t_land, count=70, direction=dv, speed=(60, 180), cone=40,
                      drag=7.0, spin=6, seed=81 + k, coll=S['fxc'], spread=(20.0 if k == 0 else 1.0, 0.3))
    S['box_root'] = root
    S['box_land'] = t_land


# ================================================================================================ finalize


def finalize(S):
    """Things that read the puppets' tracks (call after all acting is keyed): the pen follows the researcher's wrist
    and points at Clawd's mouth; the ink splatters where the pen breaks."""
    c, r, fxc = S['c'], S['r'], S['fxc']
    grip, grip_M = S['pen_grip'], S['grip_M']
    key_mats(grip, grip_M, C_E3 - 0.1, C_G + 0.1)
    ink, shard = S['pen_fx']
    Mk = grip_M(K_PEN)
    cut = Mk @ V((0.0, 0.0, PEN_HOLD - 6.2))
    back = (Mk.to_3x3() @ V((0, 0, -1))).normalized()
    EP.debris('eat.pen.ink', ink, cut, K_PEN, count=34, direction=tuple(back + V((0, 0, 0.9))), speed=(60, 190),
              cone=55, drag=1.0, spin=4, seed=91, coll=fxc)
    EP.debris('eat.pen.shards', shard, cut, K_PEN, count=16, direction=(0.0, -0.3, 1.0), speed=(50, 150), cone=70,
              seed=92, coll=fxc)


# ================================================================================================ cameras


def cameras(S):
    d, c, r = S['d'], S['c'], S['r']
    cams = kit.collection('eat.cams')
    ks = []
    # E1a reveal: a close-up at his eye level, from in front of the throne; the researcher's head and raised mitten
    #   in the foreground at the lower left
    face0 = c.anchor(T_START + 0.2, 'face')
    fdir = V((math.sin(math.radians(-55.0)), -math.cos(math.radians(-55.0)), 0.0))
    side = V((-fdir.y, fdir.x, 0.0))
    cube0 = HAND_UP + V((0.0, 0.0, 0.9))
    mid1 = face0.lerp(cube0, 0.45) + V((0, 0, 0.4))
    ea0 = mid1 + fdir * 25.0 + side * 4.5 + V((0, 0, 0.2))
    ea1 = mid1 + fdir * 22.0 + side * 4.0 + V((0, 0, 0.0))
    k1 = Cam('cam.reveal', 35, ea0, mid1, fstop=8.0, focus=face0.lerp(cube0, 0.3), coll=cams)
    k1.key(C_E1 - 0.1, loc=ea0, target=mid1, interp='LINEAR')
    k1.key(C_E1B + 0.1, loc=ea1, target=mid1 + V((0, 0, -0.5)), interp='LINEAR')
    shake(k1.cam, K_CUBE - 0.02, K_CUBE + 0.2, amp=0.05, freq=14.0, seed=2)
    ks.append((k1, C_E1))
    # E1b throne: from the front-right of the desk: the researcher's face, the bites in the rim, the leap
    e1a, e1b = V((33.5, -45.0, 12.5)), V((33.0, -42.0, 12.0))
    k1b = Cam('cam.throne', 45, e1a, (24.2, -13.8, 8.6), fstop=8.0, focus=V((24.0, -14.5, 9.0)), coll=cams)
    k1b.key(C_E1B - 0.1, loc=e1a, target=(24.2, -13.8, 8.6), interp='LINEAR')
    k1b.key(C_E2 + 0.1, loc=e1b, target=(24.0, -14.5, 8.0), interp='LINEAR')
    ks.append((k1b, C_E1B))
    # E2 buffet: a truck along the line, following him
    xs = [(C_E2 - 0.1, PAD_C.x + 5.5), (K_PAD, PAD_C.x + 4.5), (K_P1, PENCIL_X[0] + 3.0), (K_P2, PENCIL_X[1] + 2.5),
          (K_P3, PENCIL_X[2] + 2.0), (K_BOOK1, BOOK_EDGE + 1.0), (C_E3 + 0.1, BOOK_EDGE + 0.5)]
    # (revision 2: f/16, was f/8, so the lyric stand in front of the line is sharp too)
    k2 = Cam('cam.buffet', 40, (xs[0][1], Y_PATH - 40.0, 9.0), (xs[0][1] - 5.0, Y_PATH, 2.0), fstop=16.0,
             focus=(xs[0][1], Y_PATH, 2.5), coll=cams)
    for t, x in xs:
        k2.key(t, loc=(x - 9.0, Y_PATH - 38.0, 9.5), target=(x - 1.5, Y_PATH + 1.0, 2.5),
               focus=(x + 0.5, Y_PATH - 1.5, 2.5))
    ks.append((k2, C_E2))
    # E3 book: close, from the front and above: his profile, the bitten edge, the pages
    be = V((BOOK_EDGE - 3.0, Y_PATH, 1.5))
    k3 = Cam('cam.book', 45, be + V((1.5, -26.0, 9.0)), be + V((-0.5, 0.5, 0.8)), fstop=8.0, focus=be, coll=cams)
    k3.key(C_E3 - 0.1, loc=be + V((1.5, -26.0, 9.0)), target=be + V((-0.5, 0.5, 0.8)), interp='LINEAR')
    k3.key(C_E4 + 0.1, loc=be + V((1.0, -23.0, 8.0)), target=be + V((-1.0, 0.5, 0.6)), interp='LINEAR')
    ks.append((k3, C_E3))
    # E4 lance: from the front, both of them
    mid = V(((ON_BOOK_X + RES_HIDE.x) / 2, Y_PATH, 6.0))
    k4 = Cam('cam.lance', 40, mid + V((1.0, -38.0, 5.0)), mid, fstop=8.0, focus=mid + V((0, -1.0, 0)), coll=cams)
    k4.key(C_E4 - 0.1, loc=mid + V((1.0, -38.0, 5.0)), target=mid, interp='LINEAR')
    k4.key(C_G + 0.1, loc=mid + V((1.5, -33.0, 4.5)), target=mid + V((0.5, 0, -0.3)), interp='LINEAR')
    shake(k4.cam, K_PEN - 0.02, K_PEN + 0.25, amp=0.08, freq=14.0, seed=4)
    ks.append((k4, C_E4))
    # G gauge: a push in, then a crash zoom on DOOM 1
    g = d.gauge
    gc = d.anchors['gaugeCenter']
    p0 = g.front(46.0) + V((0.0, 0.0, -2.0))
    p1 = g.front(26.0) + V((0.0, 0.0, -0.8))
    k5 = Cam('cam.gauge', 70, p0, gc, fstop=11.0, coll=cams)
    k5.key(C_G - 0.1, loc=p0, target=gc, lens=70.0, interp='LINEAR')
    k5.key(DOOM1 - 0.01, loc=p1, target=gc, lens=70.0, interp='LINEAR')
    k5.key(DOOM1 + 0.1, target=gc + V((0.0, 0.0, -0.9)), lens=118.0, interp='LINEAR')
    k5.key(C_T + 0.1, loc=p1 + (gc - p1) * 0.04, target=gc + V((0.0, 0.0, -0.9)), lens=124.0, interp='LINEAR')
    shake(k5.cam, DOOM1 - 0.01, DOOM1 + 0.45, amp=0.12, freq=15.0, seed=5)
    ks.append((k5, C_G))
    # T title: in front of the desk, above the leftovers: the letters slam into the middle of the frame
    tt = V((C_SPOT.x, TITLE_Y, 3.5))
    t_a, t_b = tt + V((3.0, -40.0, 14.0)), tt + V((2.5, -35.5, 12.5))
    k6 = Cam('cam.title', 34, t_a, tt + V((0, 2.0, 1.0)), fstop=11.0, focus=V((C_SPOT.x, TITLE_Y, 3.0)), coll=cams)
    k6.key(C_T - 0.1, loc=t_a, target=tt + V((0, 2.0, 1.0)), interp='LINEAR')
    k6.key(C_F + 0.1, loc=t_b, target=tt + V((0, 3.0, 1.8)), interp='LINEAR')
    k6.key(K_PEEK, focus=V((C_SPOT.x, TITLE_Y, 3.0)))
    k6.key(W_GOES, focus=V((C_SPOT.x, C_SPOT.y - 2.0, 5.0)))
    shake(k6.cam, K_SLAM - 0.01, K_SLAM + 0.3, amp=0.18, freq=16.0, seed=6)
    ks.append((k6, C_T))
    # F foom: front-left; blown back by the blast, then looking up at the giant, then the box
    fc = V((C_SPOT.x, C_SPOT.y, 10.0))
    fa, fb, fcc = V((-18.0, -58.0, 10.0)), V((-44.0, -118.0, 26.0)), V((-40.0, -108.0, 22.0))
    k7 = Cam('cam.foom', 35, fa, fc, fstop=8.0, focus=V((C_SPOT.x, C_SPOT.y - 3.0, 8.0)), coll=cams)
    k7.key(C_F - 0.1, loc=fa, target=fc, interp='LINEAR')
    k7.key(C_F + 0.02, loc=fa, target=fc, interp='LINEAR')
    k7.key(C_F + 0.36, loc=fb, target=V((C_SPOT.x, C_SPOT.y, 18.0)))
    k7.key(26.85, loc=fcc, target=V((C_SPOT.x, C_SPOT.y, 20.0)))
    k7.key(27.05, loc=V((-36.0, -92.0, 18.0)), target=V((C_SPOT.x + 1.0, C_SPOT.y, 9.0)))
    k7.key(T_END + 0.1, loc=V((-30.0, -74.0, 14.0)), target=V((C_SPOT.x + 2.5, C_SPOT.y - 2.0, 6.5)))
    k7.key(C_F, focus=V((C_SPOT.x, C_SPOT.y - 3.0, 8.0)))
    k7.key(C_F + 0.4, focus=V((C_SPOT.x, C_SPOT.y - 12.0, 20.0)))
    k7.key(26.9, focus=V((C_SPOT.x, C_SPOT.y - 12.0, 20.0)))
    k7.key(27.0, focus=V((C_SPOT.x, C_SPOT.y - 4.0, 4.0)))
    shake(k7.cam, C_F, C_F + 0.7, amp=0.5, freq=13.0, seed=7)
    shake(k7.cam, S.get('box_land', 27.19) - 0.01, S.get('box_land', 27.19) + 0.25, amp=0.2, freq=15.0, seed=8)
    ks.append((k7, C_F))
    for k, t in ks:
        k.cut(t)
    bpy.context.scene.camera = k1.cam
    S['cams'] = ks


# ================================================================================================ lights


def lights(S):
    d, c = S['d'], S['c']
    lc = kit.collection('eat.lights')
    lp = d.lamp
    mt = MUG + V((0, 0, 9.52))
    # E1: as training left it (the lamp on the throne, a warm spot on the mug)
    lp.aim(C_E1 - 0.2, V((mt.x - 4.0, mt.y - 2.0, 6.0)), interp='CONSTANT')
    lp.aim(C_E2 - 0.5 / FPS, V((mt.x - 4.0, mt.y - 2.0, 6.0)), interp='CONSTANT')
    # E2-E4: the buffet line
    lp.aim(C_E2, V((6.0, Y_PATH + 2.0, 0.0)), reach=30.0, height=44.0, interp='CONSTANT')
    lp.aim(C_G - 0.5 / FPS, V((6.0, Y_PATH + 2.0, 0.0)), reach=30.0, height=44.0, interp='CONSTANT')
    # G: onto the gauge; T, F: the title spot
    lp.aim(C_G, d.anchors['gaugeCenter'] + V((0.0, -6.0, -8.0)), reach=24.0, height=36.0, interp='CONSTANT')
    lp.aim(C_T - 0.5 / FPS, d.anchors['gaugeCenter'] + V((0.0, -6.0, -8.0)), reach=24.0, height=36.0,
           interp='CONSTANT')
    lp.aim(C_T, V((C_SPOT.x + 2.0, TITLE_Y + 3.0, 0.0)), reach=30.0, height=44.0, interp='CONSTANT')
    if d.room.motes is not None:
        d.room.motes.hide_render = True
    # F looks at the window: the lit lamp head's reflection in its glass, far out of focus, made a hard-edged grey
    # disc behind the giant (what the QA notes took for the smoke's rim). No glass from the FOOM cut on.
    if d.room.glass is not None:
        kit.visible(d.room.glass, None, C_F)

    def win(light, energy, spans):
        geo.keyp(light.data, 'energy', T_START - 1.0, 0.0, interp='CONSTANT')
        for a, b in spans:
            geo.keyp(light.data, 'energy', a - 0.5 / FPS, 0.0, interp='CONSTANT')
            geo.keyp(light.data, 'energy', a, energy, interp='CONSTANT')
            geo.keyp(light.data, 'energy', b - 0.5 / FPS, energy, interp='CONSTANT')
            geo.keyp(light.data, 'energy', b, 0.0, interp='CONSTANT')
    # the throne spot (training's)
    tl = kit.spot('eat.throne', (mt.x - 9.0, mt.y - 16.0, 40.0), (mt.x - 3.5, mt.y - 2.5, 7.0), power=38000.0,
                  angle_deg=32, blend=0.7, radius=1.5, color='#FFC27A', coll=lc)
    win(tl, 38000.0, [(C_E1 - 0.2, C_E2)])
    # a soft front fill for the buffet line
    fl = kit.area('eat.fill', (-6.0, -80.0, 34.0), (4.0, Y_PATH, 3.0), power=30000.0, size=40.0, color='#FFE0B8',
                  coll=lc)
    fl.data.specular_factor = 0.4
    win(fl, 30000.0, [(C_E2, C_G)])
    # the gauge: a small warm key from the front-left
    gk = kit.spot('eat.gaugekey', d.anchors['gaugeCenter'] + V((-18.0, -26.0, 16.0)), d.anchors['gaugeCenter'],
                  power=26000.0, angle_deg=28, blend=0.8, radius=2.0, color='#FFD9A8', coll=lc)
    win(gk, 26000.0, [(C_G, C_T)])
    # the title and the foom: a front fill and a rim from behind-left
    tf = kit.area('eat.titlefill', (C_SPOT.x - 10.0, -86.0, 30.0), (C_SPOT.x, TITLE_Y, 4.0), power=42000.0, size=50.0,
                  color='#FFE6C8', coll=lc)
    tf.data.specular_factor = 0.6
    win(tf, 42000.0, [(C_T, T_END + 0.2)])
    refl = kit.area('eat.titlerefl', (C_SPOT.x + 4.0, -64.0, 2.5), (C_SPOT.x, TITLE_Y, 3.0), power=30000.0, size=60.0,
                    color='#FFE2B8', shape='RECTANGLE', coll=lc)
    refl.data.size_y = 12.0
    geo.keyp(refl.data, 'energy', T_START - 1.0, 0.0, interp='CONSTANT')
    geo.keyp(refl.data, 'energy', C_T - (0.1 if tm.SMOOTH else 0.0) / FPS, 30000.0, interp='CONSTANT')
    geo.keyp(refl.data, 'energy', C_F + 0.4, 30000.0, interp='LINEAR')
    geo.keyp(refl.data, 'energy', C_F + 1.0, 0.0, interp='CONSTANT')
    rim = kit.spot('eat.rim', (C_SPOT.x - 40.0, 30.0, 50.0), (C_SPOT.x, C_SPOT.y, 12.0), power=90000.0, angle_deg=40,
                   blend=0.6, radius=3.0, color='#9FC4FF', coll=lc)
    win(rim, 90000.0, [(C_T, T_END + 0.2)])
