"""pdoom.fx: the simulation and effects kit (docs/lib/fx.md).

Each module exposes functions a scene calls in build(); times are SONG SECONDS and every simulation is seeded.
Call fx.bake() once at the END of build(): it bakes the rigid bodies / particles (point caches, stored in the
.blend) and then every Mantaflow domain (to out/cache/<scene>/<name>/). Render workers never simulate.

Modules: clips (paperclips), rigid (Bullet plumbing), fracture, smoke, liquid, dominoes, particles, cubes,
materials (glass, water).
"""
import time


def log(msg: str):
    """Print a kit message that survives tools/render.py's output filter (it keeps '[run]' lines)."""
    print(f'[run] [fx] {msg}', flush=True)


def vis(obj, t_on=None, t_off=None):
    """Render visibility only between song times t_on and t_off (None = open-ended), by constant keys on
    hide_render. Unlike kit.visible it leaves viewport visibility alone, so bake operators can still act on it."""
    import bpy
    from .. import kit
    from ..timing import FPS
    sc = bpy.context.scene

    def setv(t, v):
        obj.hide_render = not v
        obj.keyframe_insert('hide_render', frame=t * FPS)
    setv(sc.frame_start / FPS - 1, t_on is None)
    if t_on is not None:
        setv(t_on, True)
    if t_off is not None:
        setv(t_off, False)
    for fc in kit.fcurves(obj):
        if fc.data_path == 'hide_render':
            for kp in fc.keyframe_points:
                kp.interpolation = 'CONSTANT'
    return obj


def bake() -> float:
    """Bake everything the fx kit set up in this scene: point caches first (rigid bodies, particles), then fluids
    (they may collide with baked rigid bodies). Returns seconds."""
    import bpy
    t0 = time.time()
    sc = bpy.context.scene
    if sc.rigidbody_world is not None or any(o.particle_systems for o in sc.objects if o.type == 'MESH'):
        from . import rigid
        rigid.bake('fx.bake')
    if sc.get('fx_fluids'):
        from . import smoke
        smoke.bake_all()
    sc.frame_set(sc.frame_start)
    dt = time.time() - t0
    log(f'bake total {dt:.1f}s')
    return dt
