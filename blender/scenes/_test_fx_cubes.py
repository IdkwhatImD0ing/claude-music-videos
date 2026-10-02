"""fx test: atoms rearranging. A wooden mitten hand dissolves into cubes at 1.5 s and reassembles, shuffled, by
3.5 s. Window (1, 5). FX_CUBE sets the cube edge (cm)."""
import os

import bpy

from pdoom import kit
from pdoom.fx import cubes

from scenes import _test_fx_common as T


def build():
    sc = kit.new_scene('_test_fx_cubes', window=(1.0, 5.0))
    T.set_desk()
    wood = kit.mat('test.handwood', '#D9A66B', rough=0.45, coat=0.3)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16, location=(0, 0, 6))
    hand = bpy.context.object
    hand.name = 'hand'
    hand.scale = (2.2, 1.2, 3.2)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    kit.smooth(hand, 180)
    hand.data.materials.append(wood)
    # a stubby thumb, joined into one closed mesh (no overlap: it pokes out of the side)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=24, ring_count=12, location=(2.4, 0, 5.2))
    th = bpy.context.object
    th.scale = (1.1, 0.8, 1.4)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    th.data.materials.append(wood)
    cubes.dissolve('hand.atoms', hand, t0=1.5, t1=3.5, cube=float(os.environ.get('FX_CUBE', '0.3')),
                   shuffle=True)
    cubes.dissolve('thumb.atoms', th, t0=1.6, t1=3.6, cube=float(os.environ.get('FX_CUBE', '0.3')),
                   shuffle=True, seed=7)
    T.night_lights((0, 0, 6), key_power=40, fill_power=14)
    T.look((6, -40, 12), (0.5, 0, 6), lens=50, fstop=16)
