"""fx test: liquid (and fracture): a snow globe bursts at 2.0 s, glass flies, the water spills across the desk.
Window (1, 5). FX_RES sets the liquid resolution (default 128)."""
import math
import os

import bpy

from pdoom import fx, kit
from pdoom.fx import fracture, liquid, materials, rigid
from pdoom.kit import PAL

from scenes import _test_fx_common as T

T_BURST = 2.0


def globe(coll, base_top=3.0, r=6.0):
    """A snow globe: turned wooden base, a 2.5 mm glass shell, water inside, a tiny blue figure."""
    wood = kit.mat('test.globe.base', '#5A3A24', rough=0.35, coat=0.6)
    base = kit.cylinder('globe.base', 5.2, base_top, (0, 0, base_top / 2), bevel=0.4, m=wood, coll=coll)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, segments=64, ring_count=32, location=(0, 0, base_top + r - 1.2))
    glass = bpy.context.object
    glass.name = 'globe.glass'
    kit.link(glass, coll)
    kit.smooth(glass, 180)
    sol = glass.modifiers.new('wall', 'SOLIDIFY')
    sol.thickness, sol.offset = 0.25, -1.0
    glass.data.materials.append(materials.glass())
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r - 0.3, segments=48, ring_count=24,
                                         location=(0, 0, base_top + r - 1.2))
    water = bpy.context.object
    water.name = 'globe.water'
    kit.link(water, coll)
    kit.smooth(water, 180)
    liquid.still('globe.water', water)
    fig = kit.box('sydney', (3.2, 1.8, 2.0), (0, 0, base_top + 1.0), bevel=0.4,
                  m=kit.mat('test.jelly', '#5AA8FF', rough=0.15, sss=0.4, coat=0.5), coll=coll)
    return base, glass, water, fig


def build():
    sc = kit.new_scene('_test_fx_liquid', window=(1.0, 5.0))
    s = T.set_desk()
    coll = kit.collection('globe')
    base, glass, water, fig = globe(coll)
    rigid.world(substeps=24, iterations=12)
    rigid.passive(s['desk'], shape='BOX')
    rigid.passive(base, shape='CONVEX_HULL')
    center = (0, 0, 3.0 + 6.0 - 1.2)
    pieces = fracture.fracture(glass, 48, seed=5, impact=(0, -6, center[2] + 1), cluster=0.5,
                               swap_at=T_BURST - 0.5 / 24)
    fracture.shatter(pieces, T_BURST, impact=center, speed=(25, 70), spin=12)
    res = int(os.environ.get('FX_RES', '144'))
    liquid.spill('globe.spill', body=water, t0=T_BURST, t_end=5.0, box=((-36, -36, 0), (36, 36, 20)), res=res,
                 burst=float(os.environ.get('FX_BURST', '5')), obstacles=[base, fig],
                 borders=os.environ.get('FX_BORDERS', ''), tension=float(os.environ.get('FX_TENSION', '0')),
                 viscosity=float(os.environ.get('FX_VISC', '0.025')))
    T.night_lights((0, 0, 6), key_power=40, fill_power=14)
    T.look((14, -58, 20), (0, -4, 4), lens=45, fstop=11)
    fx.bake()
