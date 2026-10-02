"""Pipeline smoke test and first look-dev: a vinyl Clawd on a desk, hopping. Not part of the edit."""
import math

from pdoom import kit
from pdoom.kit import PAL


def clawd(coll):
    vinyl = kit.mat('clawd.vinyl', PAL['clawd'], rough=0.38, sss=0.15, sss_radius=(1.0, 0.35, 0.2), coat=0.25, coat_rough=0.3)
    ink = kit.mat('clawd.eye', PAL['ink'], rough=0.15, coat=1.0, coat_rough=0.05)
    root = kit.empty('clawd', (0, 0, 0), coll, 'ARROWS', 0.3)
    body = kit.box('clawd.body', (1.6, 0.9, 1.0), (0, 0, 0.75), bevel=0.09, segments=5, m=vinyl, coll=coll)
    kit.parent(body, root)
    for i, x in enumerate((-0.6, -0.2, 0.2, 0.6)):
        for j, y in enumerate((-0.25, 0.25)):
            leg = kit.box(f'clawd.leg{i}{j}', (0.16, 0.16, 0.34), (x, y, 0.17), bevel=0.04, m=vinyl, coll=coll)
            kit.parent(leg, root)
    for s in (-1, 1):
        arm = kit.box(f'clawd.arm{s}', (0.3, 0.16, 0.16), (s * 0.93, 0, 0.72), bevel=0.04, m=vinyl, coll=coll)
        arm.rotation_euler = (0, math.radians(-12 * s), 0)
        kit.parent(arm, body)
    for s in (-1, 1):
        eye = kit.box(f'clawd.eye{s}', (0.11, 0.04, 0.22), (s * 0.33, -0.455, 0.9), bevel=0.02, m=ink, coll=coll)
        kit.parent(eye, body)
    return root, body


def build():
    sc = kit.new_scene('_smoke', window=(0.0, 3.0))
    coll = kit.collection('set')
    desk = kit.box('desk', (8, 5, 0.3), (0, 0, -0.15), bevel=0.02, m=kit.mat('desk', PAL['desk'], rough=0.35, coat=0.4), coll=coll)
    wall = kit.box('wall', (10, 0.2, 5), (0, 2.8, 2.5), m=kit.mat('wall', '#3A3F4A', rough=0.9), coll=coll)
    mug = kit.cylinder('mug', 0.45, 0.9, (1.9, 0.9, 0.45), bevel=0.02, m=kit.mat('mug', PAL['cream'], rough=0.25, coat=0.6), coll=coll)
    root, body = clawd(kit.collection('clawd'))
    # a hop on the beat: squash, jump, land
    kit.key(body, 'scale', 0.0, (1, 1, 1))
    kit.key(body, 'scale', 0.6, (1.12, 1.12, 0.82))
    kit.key(root, 'location', 0.6, (0, 0, 0))
    kit.key(root, 'location', 1.0, (0, 0, 0.9))
    kit.key(body, 'scale', 0.75, (0.9, 0.9, 1.15))
    kit.key(root, 'location', 1.4, (0, 0, 0))
    kit.key(body, 'scale', 1.4, (1.15, 1.15, 0.8))
    kit.key(body, 'scale', 1.7, (1, 1, 1))
    kit.key(root, 'rotation_euler', 0.6, (0, 0, 0))
    kit.key(root, 'rotation_euler', 1.4, (0, 0, math.radians(20)))
    # light: warm desk lamp key, cool screen fill, rim
    kit.area('key', (-2.5, -2.5, 3.5), (0, 0, 0.6), power=450, size=1.2, color=PAL['glow'])
    kit.area('fill', (3, -3, 1.5), (0, 0, 0.6), power=120, size=2.5, color=PAL['screen'])
    kit.area('rim', (1.5, 3.0, 3.0), (0, 0, 0.8), power=300, size=1.0, color='#FFE2C0')
    kit.world_color('#0E1420', 0.25)
    cam, tgt = kit.camera('cam', lens=65, loc=(1.8, -5.2, 1.6), target=(0, 0, 0.7), fstop=2.2)
    kit.key(cam, 'location', 0.0, (1.8, -5.2, 1.6))
    kit.key(cam, 'location', 3.0, (1.2, -4.6, 1.4))
    kit.post(bloom=0.4, vignette=0.25)
