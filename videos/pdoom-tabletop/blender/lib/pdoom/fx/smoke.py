"""Mantaflow gas (smoke and fire) baked into kit.cache_dir, rendered by EEVEE as volumes; plus a procedural haze.

    from pdoom.fx import smoke
    fx = smoke.burst('foom', center=(8, -4, 4), t0=25.58, radius=3.0, size=(60, 60, 50), res=112)  # FOOM
    tr = smoke.trail('launch', emitter=rocket, t0=62.54, t1=64.1, box=((-30, -20, 0), (30, 20, 120)))
    smoke.haze('club', box=((-40, -30, 0), (40, 30, 50)), density=0.03, color='#6F8FD8')   # no simulation
    fx.bake()      # or smoke.bake_all(): bakes every fluid domain of the scene (after the rigid bodies)

Scale (1 BU = 1 cm, gravity 981): measured, a hot plume rises ~13 cm/s at alpha = beta = 1, which reads right for a
desk-sized puff; raise beta for faster, hotter smoke. Domains are boxes in world cm; `res` divisions along the
longest side (96-128 for a desk puff: 4-6 mm cells). Volume density is extinction per cm: 0.3-1 for a thick puff.
Keep every volume within 4.5 m of the camera (kit's EEVEE volume range).
"""
from __future__ import annotations

import math
import os
import shutil
import time

import bpy
from mathutils import Vector

from .. import kit
from ..timing import FPS
from . import log, vis


def _register(dom):
    sc = bpy.context.scene
    names = list(sc.get('fx_fluids', []))
    if dom.name not in names:
        names.append(dom.name)
    sc['fx_fluids'] = names


def _frames(t0: float, t1: float):
    return max(0, int(math.floor(t0 * FPS)) - 1), int(math.ceil(t1 * FPS)) + 1


def domain(name: str, box, *, t0: float, t1: float, res: int = 96, kind: str = 'GAS', coll=None,
           noise: int = 0, adaptive: bool = True, dissolve: float = 0.0, alpha: float = 1.0, beta: float = 1.0,
           vorticity: float = 0.15, material=None, time_scale: float = 1.0, borders: str = '',
           clean: bool = True):
    """A fluid domain covering box = ((x0, y0, z0), (x1, y1, z1)) cm, simulated from song time t0 to t1.
    kind 'GAS' or 'LIQUID'. noise: extra upres factor for smoke detail (2 doubles detail, ~3x bake time).
    dissolve: seconds for smoke to fade (0 = never). borders: letters of the sides fluid collides with
    ('xXyYzZ' = left right front back bottom top; default: bottom only). The domain is only visible in [t0, t1].
    The cache goes to out/cache/<scene>/<name>/ (wiped first when clean)."""
    (x0, y0, z0), (x1, y1, z1) = box
    coll = coll or kit.collection('fx.fluids')
    dom = kit.box(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2), coll=coll)
    dom.display_type = 'WIRE'
    md = dom.modifiers.new('fluid', 'FLUID')
    md.fluid_type = 'DOMAIN'
    ds = md.domain_settings
    ds.domain_type = kind
    ds.resolution_max = res
    ds.cache_type = 'ALL'
    ds.cache_data_format = 'OPENVDB'
    ds.openvdb_cache_compress_type = 'BLOSC'
    sc = bpy.context.scene
    cdir = os.path.join(kit.OUT, 'cache', sc.name, name)
    if clean and os.path.isdir(cdir):
        shutil.rmtree(cdir, ignore_errors=True)
    ds.cache_directory = kit.cache_dir(sc.name, name)
    f0, f1 = _frames(t0, t1)
    # end first: Blender clamps start to the current end (default 250), so a later start would silently bake from 250
    ds.cache_frame_end = f1
    ds.cache_frame_start = f0
    ds.cache_frame_end = f1
    ds.time_scale = time_scale
    b = borders or 'z'
    ds.use_collision_border_left = 'x' in b
    ds.use_collision_border_right = 'X' in b
    ds.use_collision_border_front = 'y' in b
    ds.use_collision_border_back = 'Y' in b
    ds.use_collision_border_bottom = 'z' in b
    ds.use_collision_border_top = 'Z' in b
    if kind == 'GAS':
        ds.alpha, ds.beta, ds.vorticity = alpha, beta, vorticity
        ds.use_adaptive_domain = adaptive
        if adaptive:
            ds.adapt_margin = 6
            ds.adapt_threshold = 0.004
        if dissolve > 0:
            ds.use_dissolve_smoke = True
            ds.dissolve_speed = max(1, int(dissolve * FPS))
            ds.use_dissolve_smoke_log = True
        if noise:
            ds.use_noise = True
            ds.noise_scale = noise
            ds.noise_strength = 1.0
        ds.clipping = 1e-4
    if material is not None:
        dom.data.materials.clear()
        dom.data.materials.append(material)
    vis(dom, f0 / FPS + 1 / FPS, f1 / FPS)
    dom['fx_t'] = (t0, t1)
    _register(dom)
    return dom


def flow(obj, *, kind: str = 'SMOKE', t_on: float | None, t_off: float | None, density: float = 1.0,
         temperature: float = 1.0,
         fuel: float = 1.0, color: str = '#9A9A9A', normal_speed: float = 0.0, velocity=None,
         surface: float = 1.0, subframes: int = 0, source: str = 'MESH', behavior: str = 'INFLOW'):
    """Make obj (a mesh; hidden from render) emit into any gas/liquid domain it overlaps, from t_on to t_off.
    kind 'SMOKE' | 'FIRE' | 'BOTH' | 'LIQUID'. normal_speed: initial velocity along the emitter's normals
    (outward puff; Mantaflow units, ~1-3 reads as a punchy burst at desk scale); velocity: a fixed initial velocity
    vector. subframes > 0 for fast-moving emitters (a rocket) so the trail doesn't break into puffs."""
    md = obj.modifiers.new('fluid', 'FLUID')
    md.fluid_type = 'FLOW'
    fs = md.flow_settings
    fs.flow_type = kind
    fs.flow_behavior = behavior
    fs.flow_source = source
    fs.surface_distance = surface
    fs.subframes = subframes
    if kind != 'LIQUID':
        fs.density = density
        fs.temperature = temperature
        fs.smoke_color = kit.srgb(color)[:3]
        if kind in ('FIRE', 'BOTH'):
            fs.fuel_amount = fuel
    if normal_speed or velocity is not None:
        fs.use_initial_velocity = True
        fs.velocity_normal = normal_speed
        if velocity is not None:
            fs.velocity_coord = velocity
    obj.hide_render = True
    obj.display_type = 'WIRE'
    # emit only between t_on and t_off (None: always on)
    if t_on is not None or t_off is not None:
        fs.use_inflow = False
        fs.keyframe_insert('use_inflow', frame=0)
        if t_on is not None:
            fs.use_inflow = True
            obj.keyframe_insert(f'modifiers["{md.name}"].flow_settings.use_inflow', frame=t_on * FPS)
        if t_off is not None:
            fs.use_inflow = False
            obj.keyframe_insert(f'modifiers["{md.name}"].flow_settings.use_inflow', frame=t_off * FPS)
        for fc in kit.fcurves(obj):
            if fc.data_path.endswith('use_inflow'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'
    return fs


def collider(obj, *, surface: float = 0.0):
    """obj pushes smoke / liquid around (a fluid effector)."""
    md = obj.modifiers.new('fluid', 'FLUID')
    md.fluid_type = 'EFFECTOR'
    es = md.effector_settings
    es.effector_type = 'COLLISION'
    es.surface_distance = surface
    es.use_effector = True
    return es


def material(name: str = 'fx.smoke', *, color: str = '#BFBAB2', density: float = 0.6, anisotropy: float = 0.3,
             flame: str | None = None, flame_strength: float = 6.0, absorption: str = '#000000'):
    """A Principled Volume for a gas domain: density from the 'density' grid; flame (a hex colour) adds emission
    from the 'flame' grid through a black-red-orange-yellow ramp tinted by it. Volume density is per cm."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = kit.srgb(color)
    pv.inputs['Density'].default_value = density
    pv.inputs['Density Attribute'].default_value = 'density'
    pv.inputs['Anisotropy'].default_value = anisotropy
    pv.inputs['Absorption Color'].default_value = kit.srgb(absorption)
    if flame:
        at = nt.nodes.new('ShaderNodeAttribute')
        at.attribute_name = 'flame'
        ramp = nt.nodes.new('ShaderNodeValToRGB')
        cr = ramp.color_ramp
        cr.elements[0].position, cr.elements[0].color = 0.02, (0, 0, 0, 1)
        cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb('#FFF2B0')
        e = cr.elements.new(0.25)
        e.color = kit.srgb('#B3200A')
        e = cr.elements.new(0.55)
        e.color = kit.srgb(flame)
        nt.links.new(at.outputs['Fac'], ramp.inputs['Fac'])
        nt.links.new(ramp.outputs['Color'], pv.inputs['Emission Color'])
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.inputs[1].default_value = flame_strength
        nt.links.new(at.outputs['Fac'], mul.inputs[0])
        nt.links.new(mul.outputs[0], pv.inputs['Emission Strength'])
    nt.links.new(pv.outputs['Volume'], out.inputs['Volume'])
    return m


def volume_quality(tile: str = '4', samples: int = 96, shadows: int = 32):
    """Finer EEVEE volumes for shots where smoke or fire is the subject (the default 8-px froxels step visibly
    in flames). Scene-wide render settings: tile '4' costs ~2-3x the volume time of '8', '2' ~8x."""
    ee = bpy.context.scene.eevee
    ee.volumetric_tile_size = tile
    ee.volumetric_samples = samples
    ee.volumetric_shadow_samples = shadows


def _dir_size(d: str) -> int:
    tot = 0
    for root, _, files in os.walk(d):
        for f in files:
            tot += os.path.getsize(os.path.join(root, f))
    return tot


def bake(dom) -> float:
    """Bake one domain (all frames of its range). Prints time and cache size."""
    sc = bpy.context.scene
    t0 = time.time()
    with bpy.context.temp_override(scene=sc, object=dom, active_object=dom, selected_objects=[dom]):
        bpy.ops.fluid.bake_all()
    dt = time.time() - t0
    ds = dom.modifiers['fluid'].domain_settings
    size = _dir_size(bpy.path.abspath(ds.cache_directory)) / 1e6
    log(f'fluid bake {dom.name}: {dt:.1f}s, cache {size:.0f} MB, frames {ds.cache_frame_start}-'
        f'{ds.cache_frame_end}, res {ds.resolution_max}')
    return dt


def bake_all() -> float:
    """Bake every fluid domain the fx kit made in this scene, in creation order."""
    sc = bpy.context.scene
    tot = 0.0
    for nm in sc.get('fx_fluids', []):
        ob = bpy.data.objects.get(nm)
        if ob is not None:
            tot += bake(ob)
    return tot


# ------------------------------------------------------------------------------------------------ recipes


def burst(name: str = 'burst', *, center, t0: float, t_end: float | None = None, radius: float = 6.0,
          emit: float = 0.2, size=(70.0, 70.0, 60.0), res: int = 112, fire: bool = False, punch: float = 100.0,
          grow: float = 0.25, color: str = '#D6D0C6', density: float = 1.5, flame: str = '#FF7A1A',
          dissolve: float = 2.5, beta: float = 1.5, noise: int = 0, swirl: float = 3.0, coll=None) -> dict:
    """A puff (the FOOM): at t0 a sphere at center grows from `grow` x radius to `radius` over `emit` s, blasting
    smoke outward (its moving surface plus `punch`, Mantaflow caps that at 100), then the cloud billows up and
    thins over `dissolve` s. fire=True: a fireball with flames. The domain box is `size` cm, its floor on the desk
    under center. swirl: random velocity (0-10) for a ragged edge.
    Returns {'domain', 'emitter', 'material'}. Bake with fx.bake() / smoke.bake_all()."""
    c = Vector(center)
    t_end = t_end if t_end is not None else t0 + 3.0
    z0 = max(0.0, c.z - radius - 1.0) if c.z - radius < 6 else c.z - size[2] * 0.3
    box = ((c.x - size[0] / 2, c.y - size[1] / 2, z0), (c.x + size[0] / 2, c.y + size[1] / 2, z0 + size[2]))
    mat = material(f'{name}.mat', color=color, density=density, flame=flame if fire else None)
    dom = domain(name, box, t0=t0 - 1 / FPS, t1=t_end, res=res, material=mat, dissolve=dissolve, beta=beta,
                 vorticity=0.3, noise=noise, coll=coll)
    em = kit.sphere(f'{name}.emitter', radius, tuple(c), coll=coll or kit.collection('fx.fluids'), subdiv=3)
    kit.key(em, 'scale', t0 - 1 / FPS, (grow, grow, grow))
    kit.key(em, 'scale', t0 + emit, (1.0, 1.0, 1.0), interp='EXPO', easing='EASE_OUT')
    fs = flow(em, kind='BOTH' if fire else 'SMOKE', t_on=t0, t_off=t0 + emit, temperature=2.0 if fire else 1.3,
              color=color, normal_speed=min(punch, 100.0), density=1.0, fuel=1.2)
    fs.velocity_factor = 2.0
    fs.velocity_random = swirl
    return {'domain': dom, 'emitter': em, 'material': mat}


def trail(name: str = 'trail', *, emitter, t0: float, t1: float, box, res: int = 128, t_end: float | None = None,
          color: str = '#D8D4CC', density: float = 1.0, fire: bool = False, flame: str = '#FF8A2A',
          dissolve: float = 4.0, beta: float = 0.6, radius: float | None = None, down: float = 1.5,
          coll=None) -> dict:
    """A smoke trail behind a moving emitter (the rocket): `emitter` is an animated object; a small sphere
    (radius, default 1.6 cm) riding on it emits from t0 to t1 with a push `down` along -Z of the emitter (exhaust),
    subframed so the trail stays continuous. Returns {'domain', 'emitter', 'material'}."""
    t_end = t_end if t_end is not None else t1 + 2.0
    mat = material(f'{name}.mat', color=color, density=density, flame=flame if fire else None)
    dom = domain(name, box, t0=t0 - 1 / FPS, t1=t_end, res=res, material=mat, dissolve=dissolve, beta=beta,
                 vorticity=0.3, coll=coll)
    nozzle = kit.sphere(f'{name}.nozzle', radius or 1.6, (0, 0, 0), coll=coll or kit.collection('fx.fluids'),
                        subdiv=2)
    nozzle.parent = emitter
    fs = flow(nozzle, kind='BOTH' if fire else 'SMOKE', t_on=t0, t_off=t1, temperature=1.5, color=color,
              subframes=4, velocity=(0.0, 0.0, 0.0), fuel=1.0)
    fs.use_initial_velocity = True
    fs.velocity_factor = 1.0          # inherit the emitter's own motion
    return {'domain': dom, 'emitter': nozzle, 'material': mat}


def haze(name: str = 'haze', *, box, density: float = 0.03, color: str = '#B8C4D8', scale: float = 10.0,
         drift=(3.0, 0.0, 1.2), contrast: float = 3.0, coll=None, anisotropy: float = 0.45) -> bpy.types.Object:
    """Procedural, unsimulated haze filling box (a smoky club, a light shaft): a Principled Volume whose density
    is 4D noise (feature size ~`scale` cm) drifting by `drift` cm/s, a pure function of song time (keyed linearly
    across the scene). density: extinction per cm (0.01-0.05). Cheap: no bake, ~+30 % render time."""
    (x0, y0, z0), (x1, y1, z1) = box
    ob = kit.box(name, (x1 - x0, y1 - y0, z1 - z0), ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2),
                 coll=coll or kit.collection('fx.fluids'))
    m = bpy.data.materials.new(f'{name}.mat')
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    pv = nt.nodes.new('ShaderNodeVolumePrincipled')
    pv.inputs['Color'].default_value = kit.srgb(color)
    pv.inputs['Density Attribute'].default_value = ''
    pv.inputs['Anisotropy'].default_value = anisotropy
    tc = nt.nodes.new('ShaderNodeTexCoord')
    mp = nt.nodes.new('ShaderNodeMapping')
    nt.links.new(tc.outputs['Object'], mp.inputs['Vector'])
    noi = nt.nodes.new('ShaderNodeTexNoise')
    noi.noise_dimensions = '4D'
    noi.inputs['Scale'].default_value = 1.0 / scale
    noi.inputs['Detail'].default_value = 4.0
    noi.inputs['Roughness'].default_value = 0.55
    nt.links.new(mp.outputs['Vector'], noi.inputs['Vector'])
    # density = density * clamp((noise - 0.5) * contrast + 0.5)
    sub = nt.nodes.new('ShaderNodeMapRange')
    sub.inputs['From Min'].default_value = 0.5 - 0.5 / contrast
    sub.inputs['From Max'].default_value = 0.5 + 0.5 / contrast
    sub.inputs['To Max'].default_value = density
    nt.links.new(noi.outputs['Fac'], sub.inputs['Value'])
    nt.links.new(sub.outputs['Result'], pv.inputs['Density'])
    nt.links.new(pv.outputs['Volume'], out.inputs['Volume'])
    ob.data.materials.append(m)
    # time: the mapping offset drifts and W evolves, keyed linearly over the scene
    sc = bpy.context.scene
    ta, tb = sc.frame_start / FPS, sc.frame_end / FPS
    for t in (ta, tb):
        mp.inputs['Location'].default_value = (-drift[0] * t, -drift[1] * t, -drift[2] * t)
        mp.inputs['Location'].keyframe_insert('default_value', frame=t * FPS)
        noi.inputs['W'].default_value = t * 0.15
        noi.inputs['W'].keyframe_insert('default_value', frame=t * FPS)
    if nt.animation_data and nt.animation_data.action:
        for fc in kit.fcurves(nt):
            fc.extrapolation = 'LINEAR'
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return ob
