"""Sets test: the three lighting presets side by side in time (build_desk only lights one mood per scene, so this
scene builds 'night' and keys the other presets' values at 4 s and 8 s by calling lighting() and keying what it set).

  0-4  night    4-8  lamp_off    8-12  dawn     (cameras: wide 0-12, then establish 12-24 repeating the moods)
"""
from pdoom import kit
from pdoom.sets import build_desk, lighting
from pdoom.sets import geo

from scenes._test_desk import proxies


def key_state(d, t):
    """Key every value lighting() touches at time t (CONSTANT) so moods can be compared in one scene."""
    items = []
    if d.lamp:
        items += [(d.lamp.light.data, 'energy'), (d.lamp.bulb_socket, 'default_value'), (d.lamp.inner_socket, 'default_value')]
    if d.laptop:
        items += [(d.laptop.glow_socket, 'default_value'), (d.laptop.fill.data, 'energy')]
    r = d.room
    items += [(r.moon.data, 'energy'), (r.moon.data, 'color'), (r.bounce.data, 'energy'), (r.bounce.data, 'color'),
              (r.haze_density, 'default_value'), (r.sky_strength, 'default_value')]
    items += [(s, 'default_value') for s in r.city_sockets]
    for e in r.sky_nodes.elements:
        items.append((e, 'color'))
    for owner, prop in items:
        geo.keyp(owner, prop, t, interp='CONSTANT')


def build():
    sc = kit.new_scene('_test_desk_moods', window=(0.0, 24.0))
    d = build_desk(kit.collection('desk'), mood='night')
    proxies(d, kit.collection('proxies'))
    for t0, mood in ((0.0, 'night'), (4.0, 'lamp_off'), (8.0, 'dawn'), (12.0, 'night'), (16.0, 'lamp_off'),
                     (20.0, 'dawn')):
        lighting(d, mood)
        key_state(d, t0)
    w, _ = d.camera('wide')
    e, _ = d.camera('establish')
    kit.cut_to(w, 0.0)
    kit.cut_to(e, 12.0)
    sc.camera = w
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
    return d
