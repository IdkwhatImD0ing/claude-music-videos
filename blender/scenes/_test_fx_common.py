"""Shared stand-in set for the fx test scenes: a night desk (wood top, back wall), lamp key, screen fill, a camera.
Not part of the edit and not a library: the real desk lives in pdoom.sets."""
import math
import os

from pdoom import kit
from pdoom.kit import PAL


def desk_mat():
    m = kit.mat('test.desk', PAL['desk'], rough=0.42, coat=0.35, coat_rough=0.25)
    nt = m.node_tree
    b = nt.nodes.get('Principled BSDF')
    # wood grain: stretched noise -> colour ramp
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    mp.inputs['Scale'].default_value = (0.02, 0.5, 1.0)
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.inputs['Scale'].default_value = 0.6
    wave.inputs['Distortion'].default_value = 9.0
    wave.inputs['Detail'].default_value = 4.0
    wave.inputs['Detail Roughness'].default_value = 0.6
    nt.links.new(mp.outputs['Vector'], wave.inputs['Vector'])
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = kit.srgb('#3E2618')
    ramp.color_ramp.elements[1].color = kit.srgb('#7A4F33')
    nt.links.new(wave.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], b.inputs['Base Color'])
    return m


def set_desk(size=(160, 80), wall=True, coll=None):
    coll = coll or kit.collection('set')
    desk = kit.box('desk', (size[0], size[1], 4), (0, 0, -2), bevel=0.3, m=desk_mat(), coll=coll)
    out = {'desk': desk}
    if wall:
        out['wall'] = kit.box('wall', (size[0] + 100, 2, 120), (0, size[1] / 2 + 1, 56),
                              m=kit.mat('test.wall', '#2A2F3A', rough=0.9), coll=coll)
    return out


def night_lights(target=(0, 0, 3), key_power=40.0, fill_power=10.0, scale=1.0):
    """Warm desk-lamp key from front-left above, cool screen fill from the right, a warm rim.
    Light falloff is in Blender units: at 1 BU = 1 cm a lamp 30 cm away needs kilowatts (power ~ distance^2)."""
    key_power *= 50 * scale ** 2
    fill_power *= 50 * scale ** 2
    tx, ty, tz = target
    kit.spot('lamp.key', (tx - 28 * scale, ty - 22 * scale, tz + 38 * scale), target, power=key_power * 40,
             angle_deg=55, blend=0.6, radius=2.0, color=PAL['glow'])
    kit.area('screen.fill', (tx + 40 * scale, ty - 30 * scale, tz + 14 * scale), target, power=fill_power * 40,
             size=25 * scale, color=PAL['screen'])
    kit.area('rim', (tx + 10 * scale, ty + 40 * scale, tz + 30 * scale), target, power=key_power * 20,
             size=15 * scale, color='#FFE2C0')
    kit.world_color('#0B1018', 0.35)


def look(cam_loc, target, lens=85, fstop=4.0):
    cam, tgt = kit.camera('cam', lens=lens, loc=cam_loc, target=target, fstop=fstop)
    kit.post(bloom=0.3, vignette=0.25)
    return cam, tgt


def mode(default: str) -> str:
    """FX_TEST=<mode> selects a variant of a test scene while iterating."""
    return os.environ.get('FX_TEST', default)
