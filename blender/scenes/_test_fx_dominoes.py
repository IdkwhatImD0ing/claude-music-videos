"""fx test: a domino run with a sharp left turn, pushed at 1.5 s, retimed so the last domino lands at 4.0 s.
Window (1, 5). FX_SPACING sets the spacing (cm); FX_LAND=0 skips the retiming."""
import os

from pdoom import fx, kit
from pdoom.fx import dominoes, rigid

from scenes import _test_fx_common as T


def build():
    sc = kit.new_scene('_test_fx_dominoes', window=(1.0, 5.0))
    s = T.set_desk()
    rigid.world(substeps=20, iterations=15)
    rigid.passive(s['desk'], shape='BOX')
    sp = float(os.environ.get('FX_SPACING', '2.3'))
    r = dominoes.run('run', points=[(-50, -18), (12, -18), (12, 28)], t0=1.5, spacing=sp)
    if os.environ.get('FX_LAND', '1') != '0':
        dominoes.land(r, index=-1, t=4.0)
    else:
        rigid.bake('dominoes')
        dominoes.measure(r)
    ft = [t for t in r['fall_times'] if t is not None]
    fx.log(f'dominoes: {len(ft)}/{len(r["objects"])} fell, first {ft[0]:.3f} last {ft[-1]:.3f} s, '
           f'{(len(ft) - 1) / max(1e-6, ft[-1] - ft[0]):.1f} per s at spacing {sp}')
    T.night_lights((-10, 0, 3), key_power=40, fill_power=12, scale=1.2)
    T.look((-62, -70, 30), (-4, -2, 2), lens=35, fstop=16)
