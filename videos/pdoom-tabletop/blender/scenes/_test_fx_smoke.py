"""fx test: Mantaflow gas. Window (1, 5).

FX_TEST=burst (default: the FOOM puff on the desk) | fire (a fireball) | trail (a rocket's smoke trail) | haze
"""
import math
import os

from pdoom import fx, kit
from pdoom.fx import smoke
from pdoom.kit import PAL

from scenes import _test_fx_common as T


def build():
    m = T.mode('burst')
    sc = kit.new_scene('_test_fx_smoke', window=(1.0, 5.0))
    T.set_desk()
    res = int(os.environ.get('FX_RES', '112'))
    if m in ('burst', 'fire'):
        # a stand-in Clawd-sized block the puff blooms around
        kit.box('clawd', (8, 4.5, 5), (0, 0, 2.5), bevel=0.6, m=kit.mat('test.vinyl', PAL['clawd'], rough=0.4))
        smoke.burst('foom', center=(0, 0, 3.0), t0=1.5, radius=float(os.environ.get('FX_R', '7')), res=res,
                    fire=(m == 'fire'), t_end=5.0, density=float(os.environ.get('FX_DENS', '1.5')))
        if m == 'fire':
            smoke.volume_quality('4')
        T.night_lights((0, 0, 8), key_power=40, fill_power=12)
        T.look((10, -75, 22), (0, 0, 12), lens=40, fstop=16)
    elif m == 'trail':
        # a small rocket (a green board stack) launched diagonally up at 1.5 s
        rocket = kit.box('rocket', (4, 4, 9), (0, 0, 4.5), bevel=0.4, m=kit.mat('test.gpu', '#2E7D32', rough=0.4))
        kit.key(rocket, 'location', 1.4, (0, 0, 4.5))
        kit.key(rocket, 'location', 3.2, (18, 0, 95), interp='BEZIER', easing='EASE_IN')
        kit.key(rocket, 'rotation_euler', 1.4, (0, 0, 0))
        kit.key(rocket, 'rotation_euler', 3.2, (0, math.radians(12), 0))
        smoke.trail('launch', emitter=rocket, t0=1.5, t1=3.2, box=((-25, -20, 0), (45, 20, 110)), res=res,
                    fire=True, t_end=5.0)
        T.night_lights((0, 0, 40), key_power=60, fill_power=20, scale=1.6)
        T.look((20, -150, 40), (8, 0, 45), lens=35, fstop=16)
    elif m == 'haze':
        kit.world_color('#05070C', 0.2)
        kit.box('clawd', (8, 4.5, 5), (0, 0, 2.5), bevel=0.6, m=kit.mat('test.vinyl', PAL['clawd'], rough=0.4))
        smoke.haze('club', box=((-50, -35, 0), (50, 35, 45)), density=0.035, color='#9FB6E8')
        kit.spot('blue', (0, -6, 40), (0, 0, 0), power=4e5, angle_deg=22, blend=0.35, radius=1.0, color='#4F7BFF')
        T.look((0, -70, 14), (0, 0, 10), lens=40, fstop=16)
    fx.bake()
