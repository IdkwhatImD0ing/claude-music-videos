"""Model sheet for the character library: every researcher pose (with its face) in a lineup, and Clawd's expressions
and props, on a paper sweep. Not in the edit. Window 0-3 s. Each researcher has his own camera for one frame:
frame k (0-23) shows pose k from the front, frame 24 + k the same pose in profile; from 2.0 s the Clawd row.

    python tools/render.py sheet _test_chars_sheet --t <k/24 ...> --cols 6       (see POSE_ORDER)
    python tools/render.py stills _test_chars_sheet --t 2.5
"""
import math

from pdoom import chars, kit
from pdoom.chars.researcher import POSES

POSE_ORDER = ['stand', 'nervous', 'adjust_glasses', 'lean_in', 'kneel_offer', 'point', 'pat', 'peer', 'sit', 'gasp',
              'back_away', 'hold_leash', 'stand_on_mug', 'wave', 'think', 'proud', 'shrug', 'cower', 'cheer', 'type',
              'present', 'hold', 'arms_crossed', 'facepalm']
CLAWD_ROW = [('open', None, 'rest', 0.0), ('happy', 'crown', 'up', 0.0), ('angry', None, 'akimbo', 0.0),
             ('narrow', None, 'fold', 0.0), ('surprised', None, 'high', 0.25), ('heart', 'cat_ears', 'hug', 0.0),
             ('shut', 'party_hat', 'rest', 0.0), ('sad', None, 'down', 0.0), ('star', 'bowtie', 'cheer', 0.0),
             ('x', None, 'out', 0.0), ('open', 'mask', 'shrug', 0.0), ('happy', None, 'rest', 1.0)]


def build():
    kit.new_scene('_test_chars_sheet', window=(0.0, 3.0))
    coll = kit.collection('studio')
    paper = kit.mat('sweep', '#D8D2C6', rough=0.8)
    kit.box('floor', (400, 400, 1), (0, -140, -0.5), m=paper, coll=coll)
    kit.box('backdrop', (400, 2, 200), (0, 60, 100), m=paper, coll=coll)
    kit.area('key', (-60, -70, 90), (0, 0, 5), power=260000, size=40, color='#FFE7C8', coll=coll)
    kit.area('fill', (80, -50, 30), (0, 0, 5), power=60000, size=60, color='#CFE3FF', coll=coll)
    kit.area('rim', (0, 50, 60), (0, 0, 8), power=90000, size=30, color='#FFFFFF', coll=coll)
    kit.world_color('#30343C', 0.4)

    rc = kit.collection('researchers')
    n = len(POSE_ORDER)
    for i, name in enumerate(POSE_ORDER):
        x = (i - (n - 1) / 2) * 13.0
        y = 0.0
        cam, _ = kit.camera(f'cam.r{i}', lens=85, loc=(x + 1.5, -58, 8.0), target=(x, 0, 5.8), fstop=16)
        kit.cut_to(cam, i / 24)
        kit.cut_to(cam, 1 + i / 24)
        r = chars.Researcher(rc, name=f'r.{name}', loc=(x, y, 0.0), yaw=0.0, blink=False)
        r.pose(0.0, name, dur=0.0)
        r.place(1.0, yaw=90.0)
        if not POSES[name].get('face'):
            r.face(0.0, {'lean_in': 'talk', 'peer': 'awe', 'sit': 'happy', 'type': 'determined', 'think': 'neutral',
                         'hold': 'neutral', 'shrug': 'sad', 'stand': 'neutral', 'present': 'happy'}.get(name, 'neutral'))
    cc = kit.collection('clawds')
    for i, (eye, prop, arms, lid) in enumerate(CLAWD_ROW):
        x = (i - (len(CLAWD_ROW) - 1) / 2) * 11.0
        c = chars.Clawd(cc, name=f'c.{i}', loc=(x, -400, 0), blink=False)
        c.place(2.0, (x, -40, 0))
        c.eyes(0.0, eye)
        c.arms(0.0, arms, dur=0.0)
        if prop:
            c.wear(0.0, prop)
        if lid:
            c.lid(0.0, lid, dur=0.0)
    s = chars.sydney(cc, name='sydney', loc=(0, -400, 0), blink=False)
    s.place(2.0, (0, -52, 0))
    s.eyes(0.0, 'heart')

    crow, _ = kit.camera('cam.clawds', lens=50, loc=(6, -128, 22), target=(0, -40, 3.5), fstop=16)
    kit.cut_to(crow, 2.0)
    kit.post(vignette=0.15)
    chars.finish()
