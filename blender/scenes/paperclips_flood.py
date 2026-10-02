"""paperclips: the flood (rigid-body avalanches of real clips, then instanced seas).

Real Bullet clips pour from the burst drawer (a geyser, then surges on the kicks) and a second front washes over the
kill switch's vacation spot; instanced seas (fx.clips.sea) then fill the room: one spreading from the drawer over the
whole desk, one burying the kill switch, and a mound that rises under Clawd up to the lamp.

The rigid-body cache only covers the part of the scene that needs it (from a second before the burst): the Gato and
gauge shots before it have no simulation to step through, so the bake stays inside the budget.
"""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Vector

from pdoom import kit
from pdoom.fx import clips, rigid
from pdoom.fx import _nodes as N
from pdoom.fx import log
from pdoom.timing import FPS, t2f

V = Vector


def mode() -> str:
    """PC_SIM=1 (default: the full flood), lite (a few thousand clips, for looks), 0 (no rigid bodies)."""
    return os.environ.get('PC_SIM', '1')


def counts():
    m = mode()
    if m == 'lite':
        return {'geyser': 1600, 'pour': 1600, 'fill': 250, 'wave': 700}
    return {'geyser': 3700, 'pour': 4500, 'fill': 400, 'wave': 1700}


def _surges(hits, t0, dur, base=0.3, width=0.05):
    """An emission profile f(x in 0..1): a base flow plus a surge on each hit time."""
    def f(x):
        t = t0 + x * dur
        return base + sum(math.exp(-0.5 * ((t - h) / width) ** 2) * a for h, a in hits)
    return f


def colliders(d, *, extra_passive=(), active_pencils=True, pencil_release=None):
    """Make the desk solid, then adapt it for this scene: the lamp's arm moves (no collider but the base), the pencil
    cup is hollow (MESH) so its pencils can spill out as real bodies, the coffee is gone, a floor catches the clips
    that pour off the desk's edge."""
    n = rigid.desk(d)
    for o in list(bpy.data.objects):
        if o.rigid_body is None:
            continue
        nm = o.name
        if nm.startswith('lamp.') and nm != 'lamp.base':
            _remove_rb(o)
        elif nm in ('mug.coffee', 'mug.crema'):
            _remove_rb(o)
        elif nm == 'pencilcup.cup':
            o.rigid_body.collision_shape = 'MESH'
            o.rigid_body.mesh_source = 'BASE'
            o.rigid_body.use_margin, o.rigid_body.collision_margin = True, 0.04
    # a floor under the desk (clips pouring off its edge land there)
    fl = kit.box('pc.floor.collider', (400, 300, 4), (0, 0, -76), coll=kit.collection('pc.colliders'))
    fl.hide_render = True
    fl.display_type = 'WIRE'
    rigid.passive(fl, shape='BOX')
    for o in extra_passive:
        rigid.passive(o, shape='CONVEX_HULL', animated=True, friction=0.7)
    if active_pencils and d.pencilcup is not None:
        for pp in d.pencils:
            for o in pp.objects:
                if o.type != 'MESH':
                    continue
                mw = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = mw
                rigid.active(o, mass=0.012, shape='CONVEX_HULL', friction=0.55, bounce=0.1, damping=(0.1, 0.3),
                             margin=0.02)
                o.rigid_body.use_deactivation = False   # a held body released asleep would never fall
                if pencil_release is not None:          # they wait in the cup (held) until it starts to tip
                    rigid.release(o, pencil_release)
    return n


def _remove_rb(o):
    rbw = bpy.context.scene.rigidbody_world
    try:
        with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o], scene=bpy.context.scene):
            bpy.ops.rigidbody.object_remove()
    except Exception:
        if rbw and o.name in rbw.collection.objects:
            rbw.collection.objects.unlink(o)


def drawer_flood(d, T, *, direction, surge_hits):
    """The burst drawer's clips: a fast geyser (with the tray's own clips thrown out as it shoots open), then a
    sustained pour that surges on the kicks. Returns the avalanche dicts."""
    n = counts()
    out_dir = d.drawer.root.matrix_world.to_quaternion() @ V((0, -1, 0))
    tray = d.drawer.inside(0, 1.0)
    src = tray + out_dir * 3.0 + V((0, 0, 5.2))
    closed = d.drawer.inside(0, 0.0)
    size = d.drawer.inside_size(0)
    fill_box = ((closed.x - size.x / 2 + 1.5, closed.y - size.y / 2 + 1.5, closed.z + 0.2),
                (closed.x + size.x / 2 - 1.5, closed.y + size.y / 2 - 1.5, closed.z + size.z - 0.8))
    dvec = V(direction).normalized()
    t0 = T['burst'] + 2.0 / FPS
    g_dur = 0.55
    geyser = clips.avalanche('flood.geyser', count=n['geyser'], t0=t0, duration=g_dur,
                             source=(tuple(src), (17.0, 11.0)), direction=tuple(dvec), speed=(95.0, 205.0),
                             spread=17.0, spin=16.0, profile='burst', fill=n['fill'], fill_box=fill_box,
                             friction=0.9, seed=11)
    p0 = t0 + 0.25
    p_dur = 2.4
    pour_dir = (dvec + out_dir * 0.35 + V((0, 0, -0.25))).normalized()
    pour = clips.avalanche('flood.pour', count=n['pour'], t0=p0, duration=p_dur,
                           source=(tuple(src + V((0, 0, 0.6))), (17.0, 9.0)), direction=tuple(pour_dir),
                           speed=(60.0, 150.0), spread=19.0, spin=13.0,
                           profile=_surges(surge_hits, p0, p_dur), friction=0.9, seed=23)
    return geyser, pour


def wave(T, *, source, direction):
    """A second front of real clips that washes into the kill switch's vacation spot from off screen."""
    n = counts()
    return clips.avalanche('flood.wave', count=n['wave'], t0=T['wave'], duration=0.9,
                           source=source, direction=direction, speed=(55.0, 115.0), spread=12.0, spin=10.0,
                           profile='flood', friction=0.85, seed=37)


class CacheWindow:
    """Run the rigid-body setup with the scene's first frame moved to `t_start`, so rigid.world() puts the cache
    (and its fill pre-roll) there; restore() puts the scene range back after the bake."""

    def __init__(self, t_start: float):
        sc = bpy.context.scene
        self.f0 = sc.frame_start
        self.f_rb = t2f(t_start)
        sc.frame_start = self.f_rb

    def restore(self):
        bpy.context.scene.frame_start = self.f0


# ------------------------------------------------------------------------------------------------ the seas


def seas(T, A, *, exclude_flood=(), exclude_ks=(), exclude_mound=(), mound_center, mound_keys, ks_origin, flood_origin):
    """Instanced clip seas (no simulation):
    - flood: over the whole desk, spreading from the drawer (level falls off with distance from it);
    - ks: a quick local rise that buries the kill switch's vacation spot on P-T-O;
    - mound: a steep heap rising under Clawd to the lamp in the last shot.
    Returns the three sea dicts."""
    flood = clips.sea('sea.flood', area=((-80.0, -40.0), (80.0, 40.0)), depth=15.0,
                      level=[(T['sea0'], 0.0), (98.2, 1.8), (T['ks'], 3.6), (T['final'] - 0.1, 7.6),
                             (T['end'] + 0.1, 10.0)],
                      origin=tuple(flood_origin), slope=0.08, exclude=exclude_flood, density=0.95, band=3.6,
                      settle=0.4, drop=1.4, seed=5, interp='LINEAR')
    ks = clips.sea('sea.ks', area=((17.0, -40.0), (80.0, 27.0)), depth=15.0,
                   level=[(T['ks_rise'], 0.0), (T['T'], 5.5), (T['O'], 10.2), (T['final'], 11.0),
                          (T['end'] + 0.1, 11.5)],
                   origin=tuple(ks_origin), slope=0.34, exclude=exclude_ks, density=0.95, band=4.5, settle=0.4,
                   drop=1.5, seed=9, interp='LINEAR')
    cx, cy = mound_center[0], mound_center[1]
    mound = clips.sea('sea.mound', area=((cx - 42.0, cy - 36.0), (cx + 42.0, cy + 36.0)), depth=34.0,
                      level=mound_keys, origin=(cx, cy, 0.0), slope=0.95, exclude=exclude_mound, density=0.9,
                      band=4.0, settle=0.4,
                      drop=1.6, seed=13, interp='LINEAR')
    for sd in (flood, ks, mound):
        stable_ids(sd['modifier'].node_group)
    return flood, ks, mound


def stable_ids(ng):
    """Give a sea's points a stable 'id' (their index in the candidate mesh) BEFORE the tree deletes the ones outside
    the band. Instances take their motion-blur identity from 'id'; without it the instance order shifts as the level
    passes clips, EEVEE pairs the wrong clips between blur steps and the sea turns to smeared fur."""
    gin = next(nd for nd in ng.nodes if nd.bl_idname == 'NodeGroupInput')
    src = gin.outputs['Geometry']
    outs = [lk.to_socket for lk in ng.links if lk.from_socket == src]
    sid = ng.nodes.new('GeometryNodeSetID')
    idx = ng.nodes.new('GeometryNodeInputIndex')
    ng.links.new(src, sid.inputs['Geometry'])
    ng.links.new(idx.outputs[0], sid.inputs['ID'])
    for lk in [lk for lk in ng.links if lk.from_socket == src and lk.to_node != sid]:
        ng.links.remove(lk)
    for sock in outs:
        ng.links.new(sid.outputs['Geometry'], sock)
    return sid


def mound_cap(center, keys, coll):
    """A rounded cap of clips under Clawd on top of the mound (the sea's cone is sharp at its tip): a static pile
    whose height is keyed with the mound's peak."""
    p = clips.pile('mound.cap', center=(center[0], center[1], 0.0), radius=7.5, height=2.6, lod=1, coll=coll,
                   shape=1.4, seed=17)
    core = bpy.data.objects.get('mound.cap.core')
    for ob in (p, core):
        if ob is None:
            continue
        for t, z in keys:
            ob.location.z = z
            ob.keyframe_insert('location', index=2, frame=t * FPS)
        for fc in kit.fcurves(ob):
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    return p, core


def bake_report(label=''):
    dt = rigid.bake(label)
    return dt


# ------------------------------------------------------------------------------------------------ bake -> instances


def to_instances(avs, *, keyed=(), name='flood.clips', coll=None, lod=1):
    """Replace the baked rigid-body clips by ONE geometry-node instancer, then drop the simulation.

    Every clip's transform on every cached frame is written into a points mesh (position, local X and Z axes, a
    visibility flag); the node tree samples the two frames around the current (sub)frame, interpolates, and instances
    the clip there, with a stable ID per clip so motion blur works. `keyed` objects (the spilled pencils) get
    per-frame keys instead. Rendering then syncs one object instead of ~10k (the frames render several times faster
    and the .blend drops the point cache). Pure function of the frame: nothing is simulated at render time."""
    import time
    import numpy as np
    t0 = time.time()
    sc = bpy.context.scene
    rbw = sc.rigidbody_world
    pc = rbw.point_cache
    F0, F1 = pc.frame_start, pc.frame_end
    objs = [o for av in avs for o in av['objects']]
    n, K = len(objs), F1 - F0 + 1
    pos = np.zeros((K, n, 3), np.float32)
    ax = np.zeros((K, n, 3), np.float32)
    az = np.zeros((K, n, 3), np.float32)
    vis = np.zeros((K, n), np.float32)
    kmats = {o.name: [] for o in keyed}
    for k, f in enumerate(range(F0, F1 + 1)):
        sc.frame_set(f)
        for j, o in enumerate(objs):
            m = o.matrix_world
            pos[k, j] = m.translation
            ax[k, j] = m.col[0].xyz
            az[k, j] = m.col[2].xyz
            vis[k, j] = 0.0 if o.hide_render else 1.0
        for o in keyed:
            kmats[o.name].append(o.matrix_world.copy())
    log(f'to_instances: read {n} clips x {K} frames in {time.time() - t0:.1f}s')
    # while a clip is still parked (hidden, 30 m under the desk) hold it where it first shows, so the motion blur
    # between a hidden and a visible step doesn't smear it across the frame
    shown = vis > 0.5
    first = np.where(shown.any(0), shown.argmax(0), 0)
    early = np.arange(K)[:, None] < first[None, :]
    for arr in (pos, ax, az):
        held = arr[first, np.arange(n)]
        arr[early] = np.broadcast_to(held[None, :, :], arr.shape)[early]
    # the visual clip (no collision padding) the tree instances
    proto = clips.proto(lod)
    # points: frame-major (index = k * n + j)
    co = pos.reshape(-1, 3)
    ob = clips._points_object(name, co, {'ax': ('FLOAT_VECTOR', ax.reshape(-1, 3)),
                                          'az': ('FLOAT_VECTOR', az.reshape(-1, 3)),
                                          'vis': ('FLOAT', vis.reshape(-1))}, coll or kit.collection(name))
    g = N.Tree(f'{name}.gn')
    src = g.input_geometry()
    fr = g.out(g.node('GeometryNodeInputSceneTime'), 'Frame')
    x = g.clamp(fr - float(F0), 0.0, float(K) - 1.0001)
    i0 = g.floor(x)
    u = x - i0
    i = g.index()
    idx0 = i0 * float(n) + i
    idx1 = idx0 + float(n)

    def samp(value, index, kind='FLOAT_VECTOR'):
        nd = g.node('GeometryNodeSampleIndex', data_type=kind, domain='POINT',
                    inputs={'Geometry': src, 'Value': value, 'Index': index})
        return g.out(nd, 'Value')

    def attr(nm, kind='FLOAT_VECTOR'):
        return g.out(g.node('GeometryNodeInputNamedAttribute', data_type=kind, inputs={'Name': nm}), 'Attribute')
    P = g.position()
    p = g.mix(samp(P, idx0), samp(P, idx1), u)
    vx = g.normalize(g.mix(samp(attr('ax'), idx0), samp(attr('ax'), idx1), u))
    vz = g.normalize(g.mix(samp(attr('az'), idx0), samp(attr('az'), idx1), u))
    visv = samp(attr('vis', 'FLOAT'), idx0, 'FLOAT')
    rot = g.align(vz, 'Z')
    rot = g.align(vx, 'X', rotation=rot, pivot='Z')
    pts = g.points(n, position=p)
    pts = g.out(g.node('GeometryNodeSetID', inputs={'Geometry': pts, 'ID': g.index()}))
    inst = g.object_geo(proto, as_instance=True, relative=False)
    g.output(g.instance(pts, inst, rotation=rot, scale=visv))
    N.modifier(ob, g, 'clips')
    # the pencils: per-frame keys
    for o in keyed:
        o.rotation_mode = 'QUATERNION'
        prev = None
        for k, M in enumerate(kmats[o.name]):
            loc, q, _ = M.decompose()
            if prev is not None and prev.dot(q) < 0:
                q.negate()
            prev = q
            o.location, o.rotation_quaternion = loc, q
            o.keyframe_insert('location', frame=F0 + k)
            o.keyframe_insert('rotation_quaternion', frame=F0 + k)
        for fc in kit.fcurves(o):
            if fc.data_path in ('location', 'rotation_quaternion'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'LINEAR'
    # drop the simulation: the clip objects and the rigid-body world (every other body is keyed or static)
    sc.frame_set(sc.frame_start)
    with bpy.context.temp_override(scene=sc):
        bpy.ops.ptcache.free_bake_all()
    bpy.data.batch_remove(objs)
    for o in list(bpy.data.objects):
        if o.rigid_body is not None:
            _remove_rb(o)
    with bpy.context.temp_override(scene=sc):
        try:
            bpy.ops.rigidbody.world_remove()
        except Exception as e:  # noqa: BLE001
            log(f'to_instances: world_remove failed: {e}')
    log(f'to_instances: {n} clips x {K} frames -> one instancer ({len(co)} points) in {time.time() - t0:.1f}s')
    return ob
