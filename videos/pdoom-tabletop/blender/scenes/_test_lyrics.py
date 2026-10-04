"""Test scene for the lyrics library (not part of the edit): the first 30 s on the real desk, every lyric line in the
picture. The default presentation (painted wooden blocks popping up on the automatic lyric stand, one per shot)
carries lines 0-9, with one staged idea per line on top:

Shots (song s)
 1  0.000-2.739  two_shot      "I see sparks of AGI in your eyes" on the stand; A-G-I are smoked-acrylic blocks, dark
 2  2.739-5.880  hero_low      the stand again: A (3.677), G (4.06), I (4.355) light up one by one as Clawd's eyes do
 3  5.880-9.520  over_clawd    lines 1-2 on a two-shelf stand
 4  9.520-13.10  laptop        "There was a sudden drop in your" on the stand; "training loss" types itself on the
                               laptop screen (dim preview, each letter lights as it's sung)
 5  13.10-16.60  high angle    "now I'm your servant and you're my boss" rubber-stamped word by word on a paper card
 6  16.60-22.76  low 3/4       "ChatGPT, please don't eat me alive" as letter tiles face down on the desk; each flips
                               as it's sung; from "eat" Clawd eats them word by word on the beats
 7  22.76-24.32  gauge_wide    "I'm upping my" on the stand; P(DOOM) slams onto the same shelf in cast brass
 8  24.32-26.32  establish     "'cause the future goes" on the stand; FOOM slammed in giant brass
 9  26.32-30.000 two_shot      lines 8-9 on the stand
"""
import os

from mathutils import Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.sets import build_desk, phys_fstop


def cam(d, name, loc, target, lens, fstop):
    c, t = kit.camera(name, lens=lens, loc=loc, target=target, fstop=fstop, coll=d.colls.get('cams'))
    c.data.dof.aperture_fstop = phys_fstop(fstop)
    return c


def build():
    kit.new_scene('_test_lyrics', window=(0.0, 30.0))
    d = build_desk(kit.collection('desk'), mood='night')
    d.lamp.click(1.2)
    A = d.anchors
    c = chars.Clawd(kit.collection('clawd'), loc=A['clawdSpot'], yaw=0)
    r = chars.Researcher(kit.collection('researcher'), loc=A['researcherSpot'], yaw=120)

    # ---- cameras and cuts
    c1, _ = d.camera('two_shot', 'cam.two_shot')
    c2, _ = d.camera('hero_low', 'cam.hero_low')
    c3, _ = d.camera('over_clawd', 'cam.over_clawd')
    c4, _ = d.camera('laptop', 'cam.laptop')
    c5 = cam(d, 'cam.stamp', (-4, -52, 36), (-3, -25, 0), 50, 8)
    c6 = cam(d, 'cam.tiles', (-4, -40, 25), (7, -9, 1.0), 40, 8)
    c7, _ = d.camera('gauge_wide', 'cam.gauge_wide')
    c8, _ = d.camera('establish', 'cam.establish')
    c9, _ = d.camera('two_shot', 'cam.two_shot2')
    for cm, t in ((c1, 0.0), (c2, 2.739), (c3, 5.88), (c4, 9.52), (c5, 13.1), (c6, 16.6), (c7, 22.76), (c8, 24.32),
                  (c9, 26.32)):
        kit.cut_to(cm, t)

    # ---- a little acting
    agi = tm.word('AGI', 'AGI')
    c.eyes(0.0, 'shut', glow=0)
    for k, side in enumerate(('L', 'R', None)):
        c.eyes(tm.syl(agi, k), 'open', glow=5, side=side)
    r.pose(1.6, 'lean_in')
    r.pose(3.8, 'gasp')
    r.pose(6.2, 'nervous')
    r.pose(9.6, 'think')
    r.pose(13.6, 'kneel_offer')
    r.pose(16.4, 'stand')
    r.pose(18.0, 'back_away')
    c.look(16.8, Vector((7.0, -13.0, 0.0)))
    chomps = [20.691, 21.146, 21.6, 22.055, 22.415, 22.649]
    for t in chomps:
        c.chomp(t, wide=0.9)
    c.look(23.0, Vector(A['gaugeCenter']))
    c.take(25.58, hold=0.6)
    chars.finish()

    if os.environ.get('LYRICS_OFF'):             # cost baseline: the same shots without any lyrics
        kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.2)
        return
    # ---- staged lines (before default(): they claim their words)
    # 1-2  A-G-I as three light-up acrylic blocks inside the default row: dark (unsung) until each letter is sung
    ly.accent(0, 'AGI', 'glow')
    # 4  "training loss" typed on the laptop
    ly.line(3, words='training loss', style='screen', place=ly.laptop(d, u=0.5, v=0.42), size=1.05,
            t_show=9.6, t_exit=13.0)
    # 5  line 4 stamped on a card
    ly.line(4, style='stamp', place=ly.At((-3.0, -24.0, 0.0), flat=True, size=0.95), t_show=13.1, t_exit=16.6,
            max_chars=20)
    # 6  line 5 as tiles, eaten word by word on the beats
    eat_at = dict(zip(range(6), chomps))
    ly.line(5, style='tiles', place=ly.At((7.0, -13.5, 0.0), flat=True, size=1.2), t_show=16.62, max_chars=16,
            exit='eaten',
            exit_opts=dict(target=ly.mouth(c), t=lambda pc: eat_at[pc.word.index] - 6 / 24 - pc.k_index / 24))
    # 7  P(DOOM): cast brass letters slam onto the stand's shelf, inside the default row
    ly.accent(6, 'P(doom)', 'brass')
    # 8  FOOM, giant
    ly.line(7, words='FOOM', style='brass', place=ly.At((4.0, -22.0, 0.0), size=4.2), t_exit=26.3, t_end=26.32)

    # ---- everything else: the default presentation
    ly.default('_test_lyrics')
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.2)
