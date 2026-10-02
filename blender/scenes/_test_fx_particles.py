"""fx test: stateless particles. Window (1, 5).

FX_TEST=sparks (default: three sparks run along a cable at 1.5 / 1.9 / 2.2 s, a spark burst at 3.0 s)
      | confetti (a confetti cannon at 1.5 s) | fuse (a fuse burns across a sea of clips 1.5-4.0 s) | motes
"""
import math

from pdoom import kit
from pdoom.fx import clips, particles as P, smoke
from pdoom.kit import PAL

from scenes import _test_fx_common as T


def cable_points():
    """A lazy S-curve of cable on the desk, from a laptop stand-in (left) to a Clawd stand-in (right)."""
    pts = []
    for i in range(41):
        u = i / 40
        x = -22 + 40 * u
        y = 6 * math.sin(u * math.pi * 1.5) - 2
        pts.append((x, y, 0.3))
    return pts


def build():
    m = T.mode('sparks')
    sc = kit.new_scene('_test_fx_particles', window=(1.0, 5.0))
    s = T.set_desk()
    if m == 'sparks':
        pts = cable_points()
        cd = kit.mat('test.cable', '#EDEDED', rough=0.4)
        import bpy
        cu = bpy.data.curves.new('cable', 'CURVE')
        cu.dimensions, cu.bevel_depth, cu.bevel_resolution = '3D', 0.3, 4
        sp = cu.splines.new('POLY')
        sp.points.add(len(pts) - 1)
        for i, p in enumerate(pts):
            sp.points[i].co = (*p, 1)
        ob = bpy.data.objects.new('cable', cu)
        sc.collection.objects.link(ob)
        ob.data.materials.append(cd)
        kit.box('laptop', (14, 10, 1.2), (-29, -2, 0.6), bevel=0.3, m=kit.mat('test.alu', '#9AA3AD', rough=0.3,
                                                                              metal=1.0))
        kit.box('clawd', (8, 4.5, 5), (22, -2, 2.5), bevel=0.6, m=kit.mat('test.vinyl', PAL['clawd'], rough=0.4))
        P.sparks_along('agi', points=pts, starts=[1.5, 1.9, 2.2], travel=0.4)
        P.burst('pop', center=(22, -2, 5.5), t0=3.0, count=400, speed=(80, 260), cone=70)
        T.night_lights((0, 0, 3), key_power=10, fill_power=4)
        T.look((-6, -52, 18), (0, 0, 1), lens=40, fstop=16)
    elif m == 'confetti':
        kit.box('clawd', (8, 4.5, 5), (0, 0, 2.5), bevel=0.6, m=kit.mat('test.vinyl', PAL['clawd'], rough=0.4))
        P.confetti('foom.confetti', center=(0, 0, 6), t0=1.5, count=700)
        T.night_lights((0, 0, 10), key_power=40, fill_power=14)
        T.look((0, -95, 30), (0, 0, 16), lens=35, fstop=16)
    elif m == 'fuse':
        clips.sea('sea', area=((-40, -25), (40, 25)), depth=3, level=[(0.0, 2.5)], lod=2)
        pts = [(-30 + 60 * i / 60, 8 * math.sin(i / 60 * math.pi * 2), 2.8) for i in range(61)]
        P.fuse('fuse', points=pts, t0=1.5, t1=4.0)
        T.night_lights((0, 0, 3), key_power=6, fill_power=2)
        T.look((-10, -60, 22), (0, 0, 2), lens=40, fstop=16)
    elif m == 'motes':
        kit.world_color('#05070C', 0.2)
        kit.spot('beam', (0, 10, 60), (0, -5, 0), power=6e5, angle_deg=18, blend=0.4, radius=1.0, color=PAL['glow'])
        smoke.haze('air', box=((-40, -30, 0), (40, 30, 65)), density=0.004, scale=30, contrast=1.2)
        P.motes('motes', box=((-15, -18, 0), (15, 14, 60)), count=1500)
        T.look((0, -90, 20), (0, -3, 25), lens=40, fstop=16)
