"""fx test: paperclips (hero clip look, static pile, the rigid-body avalanche, instanced seas). Window (1, 7):
the second before it is the rigid-body pre-roll where the drawer's clips settle.

FX_TEST=avalanche (default: on the desk world) | static (pile + sea) | ball | field | look | top
"""
import math
import os

from mathutils import Vector

from pdoom import kit
from pdoom.fx import clips, rigid
from pdoom.kit import PAL

from scenes import _test_fx_common as T


def avalanche_on_desk(sc):
    """THE SHOWCASE on the real desk: the top drawer of the card cabinet bursts at 2.0 and the flood pours out."""
    from pdoom.sets import build_desk, phys_fstop
    d = build_desk(kit.collection('desk'), mood='night', exclude={'haze'})
    n = int(os.environ.get('FX_N', '8000'))
    rigid.world(substeps=30, iterations=12)
    nc = rigid.desk(d)
    t_burst = 2.0
    d.drawer.burst(t_burst)
    # the lamp can't reach the drawer unit (arm ~65 cm): a warm key over it instead
    kit.spot('drawer.key', (-40, -30, 60), (-58, -8, 4), power=6e5, angle_deg=40, blend=0.5, radius=3.0,
             color=PAL['glow'])
    # the open tray, and the direction out of the cabinet (its yaw)
    out_dir = d.drawer.root.matrix_world.to_quaternion() @ Vector((0, -1, 0))
    tray = d.drawer.inside(0, 1.0)
    src = tray + out_dir * 3.8 + Vector((0, 0, 5.6))
    closed = d.drawer.inside(0, 0.0)
    size = d.drawer.inside_size(0)
    fill_box = ((closed.x - size.x / 2 + 1.5, closed.y - size.y / 2 + 1.5, closed.z + 0.2),
                (closed.x + size.x / 2 - 1.5, closed.y + size.y / 2 - 1.5, closed.z + size.z - 0.8))
    av = clips.avalanche('flood', count=n, t0=t_burst + 0.1, duration=3.0, source=(tuple(src), (18, 12)),
                         direction=tuple(out_dir * 0.75 + Vector((0, 0, 1))), speed=(40, 95), spread=15,
                         profile='flood', friction=0.9, fill=int(os.environ.get('FX_FILL', '350')),
                         fill_box=fill_box)
    rigid.bake(f'avalanche on desk ({nc} colliders)')
    cam, tgt = kit.camera('cam', lens=38, loc=(-108, -58, 24), target=(-52, -8, 5))
    cam.data.dof.aperture_fstop = phys_fstop(8)
    if os.environ.get('FX_CAM') == 'close':
        cam.location, tgt.location = (-52, -40, 5), (-58, -8, 4)
        cam.data.lens = 60
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)


def build():
    m = T.mode('avalanche')
    sc = kit.new_scene('_test_fx_clips', window=(1.0, 7.0))
    if m == 'avalanche':
        return avalanche_on_desk(sc)
    s = T.set_desk()
    if m == 'look':
        for i, (x, y, rz) in enumerate([(0, 0, 20), (4.5, 1.5, -35), (-3.5, 2.5, 80)]):
            clips.clip(f'clip{i}', (x, y, 0), rz=rz, lod=0)
        T.night_lights((0, 0, 0), key_power=6, fill_power=2, scale=0.5)
        T.look((2, -13, 9), (0.5, 1.0, 0), lens=60, fstop=8)
        return
    if m == 'top':
        clips.clip('clip0', (0, 0, 0), rz=0, lod=0)
        clips.clip('clip1', (0, 1.5, 0), rz=0, lod=2)
        T.night_lights((0, 0, 0), key_power=6, fill_power=2, scale=0.5)
        T.look((0, 0.7, 12), (0, 0.75, 0), lens=100, fstop=16)
        return
    if m == 'static':
        # a heap (static instances) in front, a sea rising from the cabinet around the props, the kill switch
        # half buried; everything a pure function of time (no simulation)
        coll = kit.collection('props')
        mug = kit.cylinder('mug', 4.2, 9.5, (-24, -6, 4.75), bevel=0.3,
                           m=kit.mat('test.mug', PAL['cream'], rough=0.2, coat=0.8), coll=coll)
        base = kit.box('killswitch', (8, 8, 3), (4, -18, 1.5), bevel=0.4,
                       m=kit.mat('test.ks', '#E0B400', rough=0.4), coll=coll)
        kit.cylinder('killswitch.btn', 2.4, 2.0, (4, -18, 3.8), bevel=0.3,
                     m=kit.mat('test.ksbtn', PAL['red'], rough=0.3, coat=0.6), coll=coll)
        clips.pile('heap', center=(-6, -28, 0), radius=7, height=3.2, lod=1)
        clips.clip('hero', (9, -33, 0), rz=35, lod=0)
        clips.sea('sea', area=((-60, -32), (60, 38)), depth=12, level=[(1.5, 0.0), (6.5, 7.0)],
                  origin=(0, 20, 0), slope=0.16, exclude=[mug, base], lod=2)
        T.night_lights((0, -5, 3), key_power=40, fill_power=12, scale=1.0)
        T.look((-30, -70, 22), (-2, -12, 2), lens=45, fstop=5.6)
        return
    if m == 'ball':
        kit.world_color('#02030A', 1.0)
        clips.ball('earth', center=(0, 0, 40), radius=30, scale=2.0, progress=[(1.5, 0.0), (6.0, 1.05)],
                   core_mat=kit.mat('test.earth', '#2E5E8A', rough=0.6))
        kit.sun('sun', (-0.6, 0.5, -0.3), strength=4.0, color='#FFF1DD')
        T.look((0, -140, 50), (0, 0, 40), lens=50, fstop=16)
        return
    if m == 'field':
        # millions of clips: a 20 x 20 m ground covered with lod-3 instances
        import bpy
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=40, size=2000, location=(0, 0, 0.01))
        grid = bpy.context.object
        grid.hide_render = True
        clips.field('carpet', surface=grid, density=float(os.environ.get('FX_DENS', '0.5')), layers=2, lod=3)
        T.night_lights((0, 0, 0), key_power=40, fill_power=10, scale=6.0)
        T.look((0, -200, 60), (0, 40, 0), lens=35, fstop=11)
        return
