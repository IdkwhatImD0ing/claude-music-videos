"""Gallery for the lyrics library (not part of the edit): lines 10-22 on the real desk, one style or placement per
line, each on its sung words. Characters are left out so the letters can be judged on their own.

Shots (song s; cut on each line's first word)
  29.90  L10 fog        "See through the shoggoth's lies,"   wiped in a fogged pane standing on the desk
  33.40  L11 neon       "with your shinigami eyes"          neon script on a black board, unlit tubes light as sung
  38.62  L12 typed      "We had a stable training run,"     typewriter on paper strips lying on the desk (high)
  41.34  L13 chalk      "But now the singularity's begun"   chalk script drawing itself on a slate
  45.06  L14 wire       "And you're optimizing, accelerating," bent paperclip wire growing along its strokes
  49.56  L15 cardboard  "I feel my atoms rearranging"       cardboard letters tumbling in (on ones), landing on the word
  52.83  L16 marker     "Sydney, please let me free"        marker on sticky notes that slap down (high)
  59.13  L17 stencil    "I'm upping my P(doom)"             brass stencil plates sliding in
  60.58  L18 tape       "I hear the basilisk boom"          embossing tape punched letter by letter (high)
  62.54  L19 goldleaf   "NVDA to the moon"                  gilded letters on a pane in front of the lens; focus racks
                                                            to it for the line and back
  64.10  L20 strings    "The Omega Point's coming soon"     blocks hanging on threads above the desk
  66.22  L21 tiles      "One E thirty FLOPs a second"       tiles standing in a row, face down, flipping as sung
  69.76  L22 screen     "That was safe enough, we reckoned" typed on the laptop screen, dim until sung
  74.06  L23 blocks     "Forward MLP, backward, repeat"     the default blocks with the unsung state: blank blocks line up,
                                                            each spins round to show its letter as it's sung
  77.72  L24 tape       "Now von Neumann's obsolete"        a label on a box that slides across the desk (on_object)
"""
from pdoom import kit
from pdoom import lyrics as ly
from pdoom.sets import build_desk, phys_fstop
from pdoom.sets import materials as M

SPOT = (6.0, -24.0, 0.0)


def cam(d, name, loc, target, lens=50, fstop=8):
    c, t = kit.camera(name, lens=lens, loc=loc, target=target, fstop=fstop, coll=d.colls.get('cams'))
    c.data.dof.aperture_fstop = phys_fstop(fstop)
    return c


def build():
    kit.new_scene('_test_lyrics_gallery', window=(29.5, 81.5))
    d = build_desk(kit.collection('desk'), mood='night')
    low = cam(d, 'cam.low', (1.0, -54.0, 8.0), (6.0, -24.0, 2.6), 50, 8)
    high = cam(d, 'cam.high', (3.0, -46.0, 24.0), (6.0, -24.0, 0.0), 50, 8)
    lens = cam(d, 'cam.lens', (1.0, -54.0, 8.0), (6.0, -24.0, 2.6), 50, 5.6)
    lap, _ = d.camera('laptop', 'cam.laptop')
    cuts = [(29.5, low), (38.5, high), (41.2, low), (52.7, high), (59.0, low), (60.5, high), (62.45, lens),
            (64.05, low), (69.6, lap), (74.0, low)]
    for t, c in cuts:
        kit.cut_to(c, t)
    W = (29.5, 81.5)
    ly.line(10, style='fog', place=ly.At(SPOT, size=1.25), max_chars=16, window=W)
    ly.line(11, style='neon', place=ly.At(SPOT, size=1.9), max_chars=14, window=W)
    ly.line(12, style='typed', place=ly.At((6.0, -26.0, 0.0), flat=True, size=0.95), max_chars=16, window=W)
    ly.line(13, style='chalk', place=ly.At(SPOT, size=1.5), max_chars=16, window=W)
    ly.line(14, style='wire', place=ly.At(SPOT, size=1.25), max_chars=14, window=W)
    ly.line(15, style='cardboard', place=ly.At(SPOT, size=1.25), max_chars=14, window=W)
    ly.line(16, style='marker', place=ly.At((6.0, -27.0, 0.0), flat=True, size=0.95), max_chars=12, window=W)
    ly.line(17, style='stencil', place=ly.At(SPOT, size=1.2), max_chars=16, window=W)
    ly.line(18, style='tape', place=ly.At((6.0, -26.0, 0.0), flat=True, size=0.75), max_chars=14, window=W)
    ly.line(19, style='goldleaf', place=ly.Lens(dist=14.0, v=0.4, height=0.1), window=W, t_end=64.05)
    ly.rack(lens, 62.35, 63.95, 14.0, dur=0.25)
    ly.line(20, style='blocks', place=ly.At((6.0, -24.0, 3.0), size=1.1), strings=True, max_chars=16, window=W,
            exit='shrink')
    ly.line(21, style='tiles', place=ly.At(SPOT, size=1.5), max_chars=16, window=W)
    ly.line(22, style='screen', place=ly.laptop(d, u=0.5, v=0.45), size=1.0, max_chars=18, window=W,
            t_show=69.62, t_end=74.0)
    ly.line(23, style='blocks', preview='blank', place=ly.At(SPOT, size=1.25), max_chars=14, window=W,
            t_show=74.1, lead=0.0, t_exit=77.5, t_end=77.7)
    # a label on a moving object (scaled x2: on_object compensates the scale): embossing tape on a cardboard box
    # that slides across the desk
    box = kit.box('gallery.box', (5.0, 4.0, 4.0), (0, 0, 0), m=M.cardboard('gallery.cardboard'))
    box.scale = (2.0, 2.0, 2.0)
    kit.key(box, 'location', 77.6, (-6.0, -20.0, 4.0))
    kit.key(box, 'location', 81.5, (12.0, -20.0, 4.0))
    kit.visible(box, 77.55)
    ly.line(24, style='tape', place=ly.on_object(box, (0.0, -2.0, -0.9), (0, -1, 0), (0, 0, 1), size=0.45),
            max_chars=14, window=W, t_show=77.6)
    ly.finish()
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.2)
