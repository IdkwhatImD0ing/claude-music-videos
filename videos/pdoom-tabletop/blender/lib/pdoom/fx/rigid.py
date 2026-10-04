"""Rigid-body plumbing shared by clips, fracture and dominoes (Bullet, Blender 5.2).

One rigid-body world per scene. Effects add their bodies; the scene calls fx.bake() once at the end of build() (or
rigid.bake()), which bakes every point cache (rigid bodies, cloth, particles) into the .blend. Render workers only
read the cache.

    from pdoom.fx import rigid
    rigid.world(substeps=30)                      # cache = the scene's frames (+ optional pre-roll)
    rigid.passive(desk, shape='BOX')              # colliders: prefer BOX / CONVEX_HULL, keep them THICK (>= 2 cm)
    rigid.passive(drawer, shape='MESH', animated=True)   # keyed by the scene (kit.key), pushes bodies around
    rigid.active(mug, mass=0.25)                  # props that get knocked over
    rigid.release(jar_piece, t=69.9)              # held (animated) until t, then falls; keeps its animated velocity
    rigid.blast((0, 0, 5), t=60.235, strength=4000, radius=15)    # a keyed force-field kick
    rigid.bake()

Scale notes (1 BU = 1 cm, gravity 981): Bullet tunnels when a body moves more than its own thickness per substep.
A clip (0.16 cm collision box) falling at 150 cm/s needs >= 30 substeps/frame (720 Hz). Keep colliders thick.
Kinematic -> dynamic switches happen on whole frames; the body keeps the velocity of its last animated frame.
"""
from __future__ import annotations

import math
import time

import bpy
from mathutils import Vector

from .. import kit
from . import log
from ..timing import FPS

PARK_LAYER = 19          # collision layer for parked / launching bodies (nothing else lives there)


def world(*, substeps: int = 20, iterations: int = 12, preroll: float = 0.0, split_impulse: bool = False,
          time_scale: float = 1.0):
    """Ensure the scene's rigid-body world. Its cache covers the scene's frames plus `preroll` seconds before the
    first one (settling happens there, off screen). Calling again only raises substeps/iterations/preroll."""
    sc = bpy.context.scene
    if sc.rigidbody_world is None:
        with bpy.context.temp_override(scene=sc):
            bpy.ops.rigidbody.world_add()
        rbw = sc.rigidbody_world
        rbw.collection = bpy.data.collections.new('RigidBodyWorld')
        rbw.substeps_per_frame = substeps
        rbw.solver_iterations = iterations
        sc['fx_rb_preroll'] = 0
    rbw = sc.rigidbody_world
    rbw.substeps_per_frame = max(rbw.substeps_per_frame, substeps)
    rbw.solver_iterations = max(rbw.solver_iterations, iterations)
    rbw.use_split_impulse = rbw.use_split_impulse or split_impulse
    rbw.time_scale = time_scale
    pre = max(int(sc.get('fx_rb_preroll', 0)), int(math.ceil(preroll * FPS)))
    if sc.frame_start - pre < 0:
        # a cache starting at a negative frame reads garbage at subframes (motion blur!); clamp the pre-roll
        log(f'rigid.world: pre-roll clamped to {sc.frame_start} frames (cache cannot start before 0)')
        pre = sc.frame_start
    sc['fx_rb_preroll'] = pre
    rbw.point_cache.frame_start = sc.frame_start - pre
    rbw.point_cache.frame_end = sc.frame_end
    return rbw


def _add(obj, kind: str):
    rbw = world()
    if obj.rigid_body is None:
        if obj.name not in rbw.collection.objects:
            rbw.collection.objects.link(obj)
        with bpy.context.temp_override(object=obj, active_object=obj, selected_objects=[obj],
                                       scene=bpy.context.scene):
            bpy.ops.rigidbody.object_add(type=kind)
    obj.rigid_body.type = kind
    return obj.rigid_body


def passive(obj, *, shape: str = 'BOX', friction: float = 0.6, bounce: float = 0.05, animated: bool = False,
            margin: float | None = None, source: str = 'DEFORM'):
    """A collider. shape 'BOX' | 'CONVEX_HULL' | 'MESH' (concave, e.g. a drawer or a bowl; slower). animated=True for
    colliders the scene keys (a drawer sliding, a hand)."""
    rb = _add(obj, 'PASSIVE')
    rb.collision_shape = shape
    rb.friction, rb.restitution = friction, bounce
    rb.kinematic = animated
    if shape == 'MESH':
        rb.mesh_source = source
    if margin is not None:
        rb.use_margin, rb.collision_margin = True, margin
    return rb


def active(obj, *, mass: float = 0.1, shape: str = 'CONVEX_HULL', friction: float = 0.5, bounce: float = 0.1,
           damping=(0.04, 0.1), margin: float | None = None, sleep: bool = True):
    """A dynamic body. Masses are relative: a clip is 0.002, a domino 0.02, a mug 0.25."""
    rb = _add(obj, 'ACTIVE')
    rb.collision_shape = shape
    rb.mass, rb.friction, rb.restitution = mass, friction, bounce
    rb.linear_damping, rb.angular_damping = damping
    rb.use_deactivation = sleep
    if margin is not None:
        rb.use_margin, rb.collision_margin = True, margin
    return rb


DESK_PROPS = ('mug', 'books', 'book0', 'book1', 'book2', 'book3', 'killswitch', 'notes', 'pen', 'pencilcup',
              'laptop', 'gauge', 'lamp', 'cable')


def desk(d=None, *, props=DESK_PROPS, min_size: float = 2.0) -> int:
    """Make the desk world (pdoom.sets.build_desk) solid for rigid bodies: the desk top (BOX), the drawer cabinet
    (panels static; trays and fronts follow their keyed drawers), and every mesh of the named props bigger than
    `min_size` cm as a convex hull that follows the prop (the lamp aims, a pencil gets eaten).
    Returns the number of colliders. (d is unused: objects are found by the sets library's names.)"""
    n = 0
    top = bpy.data.objects.get('desk.top')
    if top is not None and top.rigid_body is None:
        passive(top, shape='BOX')
        n += 1
    for o in bpy.data.objects:
        if o.type != 'MESH' or o.rigid_body is not None:
            continue
        nm = o.name
        if nm.startswith('drawers.panel'):
            passive(o, shape='BOX')
        elif nm.startswith('drawers.front') or nm.startswith('drawers.tray'):
            passive(o, shape='BOX', animated=True)
        elif nm.split('.')[0] in props and max(o.dimensions) > min_size:
            passive(o, shape='CONVEX_HULL', animated=True)     # follows the prop if the scene keys it
        else:
            continue
        n += 1
    return n


def copies(proto, n: int, coll=None) -> list:
    """n copies of a rigid-body object (they share its mesh and join the world automatically). Fast: ~0.05 ms each."""
    coll = coll or proto.users_collection[0]
    out = []
    for _ in range(n):
        o = proto.copy()
        coll.objects.link(o)
        out.append(o)
    rbw = world()
    for o in out:
        if o.name not in rbw.collection.objects:
            rbw.collection.objects.link(o)
    return out


def _const(obj, path):
    for fc in kit.fcurves(obj):
        if fc.data_path == path:
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'


def release(obj, t: float):
    """Held (kinematic, following its keyframes) until song time t, dynamic from the next whole frame after t.
    Keep keying its location/rotation up to t: it leaves with that velocity."""
    rb = obj.rigid_body
    f = math.floor(t * FPS + 1e-6)
    sc = bpy.context.scene
    rb.kinematic = True
    rb.keyframe_insert('kinematic', frame=world().point_cache.frame_start)
    rb.keyframe_insert('kinematic', frame=f)
    rb.kinematic = False
    rb.keyframe_insert('kinematic', frame=f + 1)
    _const(obj, 'rigid_body.kinematic')
    return f + 1


def layers(obj, keys):
    """Key the collision layers: keys = [(frame, [layer ids])]. Only layers 0 and PARK_LAYER are keyed (two F-curves
    instead of twenty). Constant interpolation."""
    rb = obj.rigid_body
    for f, ids in keys:
        for i in (0, PARK_LAYER):
            rb.collision_collections[i] = i in ids
        for i in (0, PARK_LAYER):
            rb.keyframe_insert('collision_collections', index=i, frame=f)
    _const(obj, 'rigid_body.collision_collections')


def launch(obj, t: float, pos, vel, *, spin=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0), park=(0.0, 0.0, -5000.0),
           lead: int = 2, show: bool = True):
    """Emit a parked body at song time t: it waits (kinematic, hidden, in the park layer) at `park`, jumps behind
    `pos`, slides to `pos` over `lead` frames with velocity `vel` (cm/s) and spin (rad/s, Euler rates), then
    becomes dynamic in the normal layer on the next frame, keeping that velocity. Returns the release frame."""
    sc = bpy.context.scene
    rbw = world()
    f0 = rbw.point_cache.frame_start
    F = max(int(round(t * FPS)), f0 + lead + 2)
    rb = obj.rigid_body
    vel, pos, rot, spin = Vector(vel), Vector(pos), Vector(rot), Vector(spin)
    back = pos - vel * (lead / FPS)
    rback = rot - spin * (lead / FPS)
    # location/rotation: park (constant) -> back at F-lead -> pos at F (linear)
    obj.location, obj.rotation_euler = park, rback
    obj.keyframe_insert('location', frame=f0)
    obj.keyframe_insert('rotation_euler', frame=f0)
    obj.keyframe_insert('location', frame=F - lead - 1)
    obj.location = back
    obj.keyframe_insert('location', frame=F - lead)
    obj.keyframe_insert('rotation_euler', frame=F - lead)
    obj.location, obj.rotation_euler = pos, rot
    obj.keyframe_insert('location', frame=F)
    obj.keyframe_insert('rotation_euler', frame=F)
    for fc in kit.fcurves(obj):
        if fc.data_path in ('location', 'rotation_euler'):
            kps = fc.keyframe_points
            for kp in kps:
                kp.interpolation = 'LINEAR'
            if fc.data_path == 'location':
                kps[0].interpolation = 'CONSTANT'
                if len(kps) > 1:
                    kps[1].interpolation = 'CONSTANT'
    rb.kinematic = True
    rb.keyframe_insert('kinematic', frame=f0)
    rb.keyframe_insert('kinematic', frame=F)
    rb.kinematic = False
    rb.keyframe_insert('kinematic', frame=F + 1)
    _const(obj, 'rigid_body.kinematic')
    layers(obj, [(f0, [PARK_LAYER]), (F + 1, [0])])   # the step F -> F+1 is the first dynamic one
    if show:
        obj.hide_render = True
        obj.keyframe_insert('hide_render', frame=f0)
        obj.hide_render = False
        obj.keyframe_insert('hide_render', frame=F - 1)
        _const(obj, 'hide_render')
    return F + 1


def blast(loc, t: float, *, strength: float = 3000.0, radius: float = 20.0, dur: float = 0.2, kind: str = 'FORCE',
          direction=None, name: str = 'fx.blast', falloff: float = 2.0, coll=None):
    """A force field that kicks rigid bodies (and particles) for `dur` seconds from song time t.
    kind 'FORCE' pushes radially out of loc; 'WIND' pushes along direction. Strength is Blender's field strength
    (tune by eye: ~2000-8000 throws clips 10-30 cm). Deterministic (keyed)."""
    o = bpy.data.objects.new(name, None)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    if direction is not None:
        o.rotation_euler = Vector(direction).to_track_quat('Z', 'Y').to_euler()
    o.field.type = kind
    f = o.field
    f.shape = 'POINT'
    f.falloff_type = 'SPHERE'
    f.use_max_distance, f.distance_max = True, radius
    f.falloff_power = falloff
    f.strength = 0.0
    kit.key(o, 'field.strength', t - 1 / FPS, 0.0)
    kit.key(o, 'field.strength', t, strength)
    kit.key(o, 'field.strength', t + dur, strength * 0.3)
    kit.key(o, 'field.strength', t + dur + 2 / FPS, 0.0)
    for fc in kit.fcurves(o):
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    return o


def bake(label: str = '') -> float:
    """Bake every point cache of the scene (rigid bodies, cloth, particles). Prints and returns the seconds taken."""
    t0 = time.time()
    kit.bake_all()
    dt = time.time() - t0
    rbw = bpy.context.scene.rigidbody_world
    n = len(rbw.collection.objects) if rbw and rbw.collection else 0
    log(f'rigid bake {label}: {dt:.1f}s ({n} bodies)')
    return dt


def settle(objs, seconds: float = 1.0):
    """Drop objs from where they are and let them come to rest in a throwaway bake from the cache's first frame;
    their resting transforms become their start transforms. Everything else in the world simulates too (its
    results are thrown away). Use before keying any animation on objs."""
    sc = bpy.context.scene
    rbw = world()
    pc = rbw.point_cache
    f0, f1 = pc.frame_start, pc.frame_end
    n = max(2, int(seconds * FPS))
    pc.frame_end = f0 + n
    t0 = time.time()
    with bpy.context.temp_override(scene=sc):
        bpy.ops.ptcache.free_bake_all()
        bpy.ops.ptcache.bake_all(bake=True)
    sc.frame_set(f0 + n)
    mats = [o.matrix_world.copy() for o in objs]
    with bpy.context.temp_override(scene=sc):
        bpy.ops.ptcache.free_bake_all()
    pc.frame_end = f1
    sc.frame_set(f0)
    for o, m in zip(objs, mats):
        o.matrix_world = m
    log(f'settle {len(objs)} bodies over {seconds:.2f}s: {time.time() - t0:.1f}s')
    return mats
