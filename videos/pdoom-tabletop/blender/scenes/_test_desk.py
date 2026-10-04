"""Test scene for the sets library: the desk from its marks, the lamp clicking on, the laptop screen changing, the
drawer bursting, the kill switch, and the gauge's four DOOM jumps with the crack. Not part of the edit.

Shots (song time -> mark):
   0-12   wide          lamp clicks on at 2.056; screen code -> loss (5.0-5.5), tinted orange 8-9; lamp flicker 10-10.8
  12-16   hero_low      (proxy Clawd; the gauge behind it)
  16-18   over_researcher
  18-20   two_shot
  20-28   gauge         DOOM 1 at 23.873 -> 25
  28-30   gauge_wide
  30-34   macro         the paperclip
  34-36   lamp
  36-38   laptop
  38-44   drawer        the top drawer bursts at 40.0, the middle one slides open 41.5-42.5
  44-48   killswitch    pressed at 46.0
  48-50   mug
  50-54   window        city bokeh
  54-58   establish
  58-64   gauge         DOOM 2 at 60.235 -> 50
  64-66   top
  66-76   books, pencils, notes, cable, over_clawd
  76-94   top
  94-100  gauge         DOOM 3 at 96.596 -> 75
 100-123  establish
 123-130  gauge         DOOM 4 at 125.686 -> 100 and the glass cracks
"""
import math

from pdoom import kit
from pdoom.kit import PAL
from pdoom.sets import build_desk
from pdoom.sets import geo
from pdoom.sets import materials as M

SHOTS = [(0, 'wide'), (12, 'hero_low'), (16, 'over_researcher'), (18, 'two_shot'), (20, 'gauge'), (28, 'gauge_wide'),
         (30, 'macro'), (34, 'lamp'), (36, 'laptop'), (38, 'drawer'), (44, 'killswitch'), (48, 'mug'), (50, 'window'),
         (54, 'establish'), (58, 'gauge'), (64, 'top'), (66, 'books'), (68, 'pencils'), (70, 'notes'), (72, 'cable'),
         (74, 'over_clawd'), (76, 'top'), (94, 'gauge'), (100, 'establish'), (123, 'gauge')]


def proxies(d, coll):
    """Stand-ins at real size so the set can be judged: Clawd (8 x 4.5 x 5 cm) and the researcher (12 cm peg doll)."""
    vinyl = M.solid('proxy.vinyl', PAL['clawd'], rough=0.38, sss=0.15, sss_radius=(1.0, 0.35, 0.2), coat=0.25,
                    coat_rough=0.3)
    ink = M.solid('proxy.ink', PAL['ink'], rough=0.15, coat=1.0, coat_rough=0.05)
    c = d.anchors['clawdSpot']
    root = geo.empty('proxy.clawd', c, coll, 2.0)
    body = geo.box('proxy.clawd.body', (8.0, 4.5, 4.1), (0, 0, 0), bev=0.7, segments=5, m=vinyl, coll=coll)
    geo.attach(body, root, (0, 0, 0.9 + 2.05))
    for i, x in enumerate((-3.0, -1.0, 1.0, 3.0)):
        for j, y in enumerate((-1.3, 1.3)):
            leg = geo.box(f'proxy.clawd.leg{i}{j}', (0.8, 0.8, 1.1), (0, 0, 0), bev=0.2, m=vinyl, coll=coll)
            geo.attach(leg, root, (x, y, 0.55))
    for s in (-1, 1):
        eye = geo.box(f'proxy.clawd.eye{s}', (0.55, 0.2, 1.1), (0, 0, 0), bev=0.1, m=ink, coll=coll)
        geo.attach(eye, root, (s * 1.6, -2.27, 3.6))
    wood = M.solid('proxy.wood', '#D8B48A', rough=0.5, coat=0.3, micro=(6.0, 0.05))
    coat = M.solid('proxy.coat', PAL['cream'], rough=0.8, sheen=0.4)
    r = d.anchors['researcherSpot']
    rr = geo.empty('proxy.researcher', r, coll, 2.0, rot=(0, 0, d.facing['researcherSpot']))
    body = geo.lathe('proxy.researcher.body', geo.rounded_profile([(0, 0), (2.1, 0), (2.3, 1.0), (1.9, 7.5), (1.2, 8.3),
                                                                   (0, 8.4)], 0.4), segs=48, coll=coll, m=coat)
    geo.attach(body, rr)
    head = kit.sphere('proxy.researcher.head', 2.0, (0, 0, 0), m=wood, coll=coll)
    geo.attach(head, rr, (0, 0, 10.0))
    for s in (-1, 1):
        e = kit.sphere(f'proxy.researcher.eye{s}', 0.18, (0, 0, 0), m=ink, coll=coll, subdiv=2)
        geo.attach(e, rr, (s * 0.7, -1.9, 10.2))
    return root, rr


def build(mood: str = 'night', scene_id: str = '_test_desk'):
    sc = kit.new_scene(scene_id, window=(0.0, 130.0))
    d = build_desk(kit.collection('desk'), mood=mood)
    proxies(d, kit.collection('proxies'))
    # lamp: dark until 2.056, clicks on; a flicker at 10-10.8
    if mood == 'night':
        d.lamp.click(2.056)
        d.lamp.flicker(10.0, 10.8, depth=0.8, rate=12, seed=3)
    # laptop: code -> loss curve, then an orange alarm tint and back
    d.laptop.screen(4.9, mix=0.0)
    d.laptop.screen(5.5, mix=1.0)
    d.laptop.screen(7.9, color='#FFFFFF', glow=d.laptop.glow)
    d.laptop.screen(8.2, color='#FF9A5A', glow=d.laptop.glow * 1.6)
    d.laptop.screen(9.0, color='#FFFFFF', glow=d.laptop.glow)
    # drawer and kill switch
    d.drawer.burst(40.0)
    d.drawer.open(41.5, 42.5, 0.6, k=1)
    d.killswitch.press(46.0)
    # cameras: one per shot, cut by markers
    made = {}
    for t, mk in SHOTS:
        if mk not in made:
            made[mk] = d.camera(mk, f'cam.{mk}')
        cam, tgt = made[mk]
        kit.cut_to(cam, t)
    # a slow push on the wide and on the gauge inserts (motion-control feel)
    cam, tgt = made['wide']
    kit.key(cam, 'location', 0.0)
    kit.key(cam, 'location', 12.0, tuple(d.marks['wide']['loc'] + (d.marks['wide']['target'] - d.marks['wide']['loc']) * 0.12))
    sc.camera = made['wide'][0]
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
    return d
