"""Mantaflow liquid: a body of water let go at a song time (the burst snow globe), a meshed FLIP surface in a
water material, colliding with the desk and any obstacles.

    from pdoom.fx import liquid
    w = liquid.spill('globe.water', body=water_sphere, t0=60.235, box=((-35, -30, 0), (35, 30, 25)), res=128,
                     burst=1.2, obstacles=[globe_base, gauge_plinth])
    fx.bake()          # rigid bodies first (moving shards can be obstacles), then the liquid

Before t0 show the scene's own still water (e.g. inside the intact globe); spill() hides `body` and the domain's
liquid mesh takes over from t0. Scale (1 BU = 1 cm): measured, Mantaflow liquid falls ~1.4x too fast with the
scene's 981 cm/s^2, so the domain's gravity weight defaults to 0.7 (a blob then falls 13 cm in 1/6 s, as in life).
"""
from __future__ import annotations

import bpy
from mathutils import Vector

from .. import kit
from ..timing import FPS
from . import log, materials, smoke, vis

GRAVITY_WEIGHT = 0.7


def spill(name: str = 'water', *, body, t0: float, t_end: float | None = None, box, res: int = 128,
          burst: float = 0.0, velocity=None, obstacles=(), mat=None, mesh_scale: int = 2, smooth: int = 2,
          particle_radius: float = 1.1, gravity: float = GRAVITY_WEIGHT, borders: str = '', coll=None,
          spray: bool = False, time_scale: float = 1.0, floor: float | None = 0.0, tension: float = 0.0,
          viscosity: float = 0.025) -> dict:
    """Release `body` (a closed mesh: the water's shape at t0) as liquid at song time t0 inside box
    ((x0, y0, z0), (x1, y1, z1)). floor: the height of the surface the water lands on (the desk top, z = 0): the
    domain is extended 3 cells below it and a hidden obstacle slab fills that, so the water rests ON the desk
    (a domain wall at the desk would float it half a cell up and eat thin films). None: no floor.
    burst: outward speed along the body's normals (Mantaflow units, capped at 100; 5 reads as a globe bursting),
    velocity: an extra fixed initial velocity. obstacles: meshes the water flows around (static or animated, rigid
    bodies included). res: divisions along the longest side (144 in a 72 cm box = 5 mm cells, mesh upres 2).
    viscosity: measured on the 776 cm^3 globe at res 144 over 3 s: 0 (inviscid, ~70-110 s bake) sprays into a
    film of droplets that runs to the domain walls; 0.025 (default, ~7 min) slumps into one coherent puddle
    ~30 cm across; 0.08 and up reads as gel. The viscosity solver is the cost.
    Returns {'domain', 'body', 'material', 'floor'}."""
    t_end = t_end if t_end is not None else t0 + 3.0
    mat = mat or materials.water('fx.water.spill', thickness=0.5)
    (x0, y0, z0), (x1, y1, z1) = box
    slab = None
    if floor is not None:
        cell = max(x1 - x0, y1 - y0, z1 - z0) / res
        z0 = min(z0, floor - 3 * cell)
        slab = kit.box(f'{name}.floor', (x1 - x0 + 2, y1 - y0 + 2, floor - z0 + 1),
                       ((x0 + x1) / 2, (y0 + y1) / 2, (z0 - 1 + floor) / 2), coll=coll or kit.collection('fx.fluids'))
        slab.hide_render = True
        slab.display_type = 'WIRE'
    # the domain starts one frame before t0: a GEOMETRY flow only fills on the domain's first frame
    dom = smoke.domain(name, ((x0, y0, z0), (x1, y1, z1)), t0=t0, t1=t_end, res=res, kind='LIQUID', material=mat,
                       borders=borders or 'xXyYz', time_scale=time_scale, coll=coll)
    ds = dom.modifiers['fluid'].domain_settings
    ds.effector_weights.gravity = gravity
    ds.simulation_method = 'FLIP'
    ds.use_mesh = True
    ds.mesh_scale = mesh_scale
    ds.mesh_generator = 'IMPROVED'
    ds.mesh_smoothen_pos = smooth
    ds.mesh_smoothen_neg = smooth
    ds.mesh_particle_radius = particle_radius
    ds.particle_radius = 1.0
    ds.use_speed_vectors = True
    ds.cache_mesh_format = 'BOBJECT'
    ds.use_fractions = False             # measured: fractions + the floor obstacle delete the water in 0.2 s
    if tension > 0:
        ds.use_diffusion = True
        ds.surface_tension = tension
    if viscosity > 0:
        ds.use_viscosity = True
        ds.viscosity_value = viscosity
    ds.particle_number = 3
    if spray:
        ds.use_spray_particles = True
    _empty_guard(dom)
    # the water body: emits its volume once at t0, then hides
    # a GEOMETRY flow keeps refilling its volume every frame it is on: on only for the domain's first two frames
    f_first = dom.modifiers['fluid'].domain_settings.cache_frame_start
    fs = smoke.flow(body, kind='LIQUID', t_on=0.0, t_off=(f_first + 1.5) / FPS, behavior='GEOMETRY',
                    normal_speed=burst, velocity=velocity)
    fs.use_plane_init = False
    vis(body, None, t0)          # the still water shows until the release, the simulation after
    for ob in ([slab] if slab is not None else []) + list(obstacles):
        smoke.collider(ob)
    log(f'liquid {name}: res {res} in {tuple(round(b1 - b0) for b0, b1 in zip(*box))} cm, from t={t0:.3f}')
    return {'domain': dom, 'body': body, 'material': mat, 'floor': slab}


def _empty_guard(dom):
    """When a frame has no liquid, the fluid modifier hands back the domain's own box (which would render as a
    wall of water). A geometry-nodes modifier after it deletes exactly that box (8 vertices)."""
    from . import _nodes as N
    g = N.Tree(f'{dom.name}.guard')
    geo = g.input_geometry()
    cnt = g.out(g.node('GeometryNodeAttributeDomainSize', component='MESH', inputs={'Geometry': geo}), 'Point Count')
    is_box = g.out(g.node('FunctionNodeCompare', data_type='INT', operation='LESS_EQUAL',
                          inputs={'A': cnt, 'B': 8}), 'Result')
    g.output(g.delete(geo, is_box, domain='POINT'))
    N.modifier(dom, g, 'fx.empty_guard')


def still(name: str, obj, *, mat=None):
    """Give a closed mesh the water material (the still water inside the globe before it bursts)."""
    obj.data.materials.clear()
    obj.data.materials.append(mat or materials.water('fx.water.still', thickness=1.5))
    return obj
