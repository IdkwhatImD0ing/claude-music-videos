"""Test scene for the character library (blender/lib/pdoom/chars): Clawd, Sydney and the researcher on the real desk
(pdoom.sets, night mood). Not in the edit. Window 0-24 s.

Clawd (camera 'hero_low' from 2.5 s):
  0.9-2.3   scuttles along a curve and back (two-shot)   7.8-9.6   dance: bounce, then shimmy
  2.6       hops                                         9.9       take (with the '!')
  3.2, 3.65 chomps                                       10.8-12.4 props: crown, cat ears, mask, party hat
  4.0-7.6   every eye shape, 0.3 s each                  12.6-13.6 eyes glow on one by one, then red
Researcher (his own camera from 14 s):
  14.0-15.6 walks in          17.8 kneel_offer   19.5 gasp        20.9 proud    22.5 red glint (held)
  15.8      nervous, sweat    18.8 point         20.2 back_away   21.5 wave     23.0 cheer, glasses reflect
  16.8      adjust_glasses + glint
Sydney (0-0.8, her own camera): hops in front of the laptop screen, heart eyes.
"""
from pdoom import chars, kit
from pdoom.sets import build_desk

SHAPES = ['open', 'happy', 'angry', 'narrow', 'surprised', 'shut', 'heart', 'sad', 'small', 'x', 'star', 'dizzy']


def build():
    kit.new_scene('_test_chars', window=(0.0, 24.0))
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable'})
    A = d.anchors
    cx, cy, _ = A['clawdSpot']
    rx, ry, _ = A['researcherSpot']

    # ------------------------------------------------------------------ Clawd
    c = chars.Clawd(kit.collection('clawd'), name='clawd', loc=(cx, cy, 0), yaw=0)
    c.move(0.9, 1.9, [(cx - 4, cy - 3), (cx + 3, cy - 5)])
    c.move(1.9, 2.3, [(cx, cy)], face='keep')
    c.turn(2.45, 0)
    c.hop(2.6, 2.4)
    c.chomp(3.2)
    c.chomp(3.65)
    for i, s in enumerate(SHAPES):
        c.eyes(4.0 + 0.3 * i, s)
    c.eyes(7.6, 'open')
    c.dance(7.8, 8.7, 'bounce')
    c.dance(8.7, 9.6, 'shimmy')
    c.take(9.9, mark=True)
    c.wear(10.8, 'crown')
    c.arms(10.8, 'up')
    c.wear(11.2, 'crown', False)
    c.wear(11.2, 'cat_ears')
    c.eyes(11.2, 'happy')
    c.arms(11.2, 'rest')
    c.wear(11.6, 'cat_ears', False)
    c.wear(11.6, 'mask')
    c.eyes(11.6, 'open')
    c.wear(12.0, 'mask', False)
    c.wear(12.0, 'party_hat')
    c.wave(12.0, 12.5)
    c.wear(12.5, 'party_hat', False)
    c.eyes(12.7, glow=4.0, side='L')
    c.eyes(13.0, glow=4.0, side='R')
    c.eyes(13.35, color='#FF3030')
    c.eyes(13.7, glow=0.0, color='#FFB24A')

    s = chars.sydney(kit.collection('sydney'), loc=(-12, -6, 0), yaw=-10)
    s.hop(0.15, 2.0)
    s.eyes(0.5, 'heart')
    s.arms(0.5, 'hug')
    s.visible(None, 0.8)

    # ------------------------------------------------------------------ researcher
    r = chars.Researcher(kit.collection('researcher'), loc=(rx - 16, ry - 10, 0), yaw=-60)
    c.look(14.3, r, turn=0.5)                  # Clawd watches him arrive
    r.walk(14.0, 15.6, [(rx - 8, ry - 7), (rx, ry)])
    r.turn(15.8, 0)
    r.pose(15.8, 'nervous')
    r.fidget(15.8, 16.7)
    r.sweat(15.9, 16.8)
    r.pose(16.8, 'adjust_glasses')
    r.glasses_glint(17.25)
    r.pose(17.8, 'kneel_offer')
    r.pose(18.8, 'point')
    r.pose(19.5, 'gasp')
    r.pose(20.2, 'back_away')
    r.pose(20.9, 'proud')
    r.pose(21.5, 'stand')
    r.face(21.5, 'happy')
    r.wave(21.5, 22.3)
    r.face(22.4, 'determined')
    r.glasses_glint(22.5, '#FF2A2A', hold=0.5)
    r.pose(23.0, 'cheer')
    r.face(23.3, 'awe')
    r.glasses_reflect(23.1, 23.9, '#FFB24A')
    c.eyes(22.9, glow=5.0)
    c.eyes(23.9, glow=0.0)

    # ------------------------------------------------------------------ cameras
    two, _ = d.camera('two_shot')
    hero, _ = d.camera('hero_low')
    cr, _ = kit.camera('cam.researcher', lens=85, loc=(rx + 3, ry - 70, 8.5), target=(rx, ry, 6.2), fstop=11)
    cs, _ = kit.camera('cam.sydney', lens=85, loc=(-2, -52, 6), target=(-12, -6, 3.6), fstop=11)
    kit.cut_to(cs, 0.0)
    kit.cut_to(hero, 0.8)
    kit.cut_to(cr, 14.0)
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
    chars.finish()
