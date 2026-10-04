"""Runs inside Blender (blender -b --factory-startup -P blender/run.py -- <args>). Builds a scene from its script, saves
it, and/or renders frames. tools/render.py is the front end; call this directly only for debugging.

  --scene ID          scene script blender/scenes/ID.py (must define build())
  --blend PATH        load a saved .blend instead of building (render workers)
  --save PATH         save the built scene
  --frames a,b,c      global frames to render (fractional allowed: 240.5 renders frame 240 at subframe 0.5)
  --range A:B         render frames A..B inclusive
  --out DIR           output folder (files f_00240.png)
  --scale P           resolution percentage (default 100; 200 = 3840x2160)
  --samples N         override EEVEE render samples
  --nomb              motion blur off (fast previews)
  --fps N             output frame rate (default 24, the scenes' own). With N != 24, --frames are OUTPUT frame
                      indices k: frame k shows song time k / N (scene frame k * 24 / N, so 60 fps samples every
                      0.4 scene frames), files are f_<k>.png, and the motion-blur shutter (static and keyed) is
                      scaled by 0.9 * 24 / N (0.5 -> 0.18 at 60 fps). The 0.9 keeps every exposure clear of the
                      puppets' pose changes, which sit on half frames (chars/rig.py): a shutter of 0.2 would touch
                      them at 60 fps and ghost the pose.
"""
import argparse
import importlib
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, 'lib'))
sys.path.insert(0, HERE)

import bpy  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
ap = argparse.ArgumentParser()
ap.add_argument('--scene')
ap.add_argument('--blend')
ap.add_argument('--save')
ap.add_argument('--frames', default='')
ap.add_argument('--range', default='')
ap.add_argument('--out', default='')
ap.add_argument('--scale', type=int, default=100)
ap.add_argument('--samples', type=int, default=0)
ap.add_argument('--nomb', action='store_true')
ap.add_argument('--fps', type=int, default=24)
a = ap.parse_args(argv)
SCENE_FPS = 24

t0 = time.time()
if a.blend:
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    print(f'[run] loaded {a.blend} in {time.time() - t0:.1f}s', flush=True)
else:
    mod = importlib.import_module(f'scenes.{a.scene}')
    mod.build()
    try:  # characters bake their on-twos poses (the library also does this at save/render time)
        from pdoom import chars
        chars.finish_all()
    except Exception as e:  # noqa: BLE001
        print(f'[run] chars.finish_all skipped: {e}', flush=True)
    print(f'[run] built {a.scene} in {time.time() - t0:.1f}s', flush=True)
    from pdoom import timing as _tm
    if _tm.SMOOTH:
        # built for 60 fps: per-frame props keyed through the scenes' stop-motion grids sit on the output grid; their
        # CONSTANT keys (set by the callers) become LINEAR so they move on every output frame. Discrete channels
        # (visibility) and anything off the output grid are left alone.
        from pdoom import kit as _kit
        step = _tm.FPS / _tm.OUT_FPS
        n_fc = 0
        ids = [*bpy.data.objects, *bpy.data.materials, *bpy.data.node_groups, *bpy.data.shape_keys, *bpy.data.lights,
               *bpy.data.cameras, *bpy.data.worlds, *bpy.data.curves, *bpy.data.meshes, *bpy.data.armatures]
        ids += [m.node_tree for m in [*bpy.data.materials, *bpy.data.worlds, *bpy.data.lights]
                if getattr(m, 'node_tree', None) is not None]
        from pdoom.chars.rig import STEPPED_PATHS as _STEP
        for idb in ids:
            for fc in _kit.fcurves(idb):
                if 'hide' in fc.data_path or any(p in fc.data_path for p in _STEP):
                    continue
                kps = fc.keyframe_points
                if len(kps) < 3 or any(kp.interpolation != 'CONSTANT' for kp in kps):
                    continue
                if all(abs(kp.co.y - round(kp.co.y)) < 1e-9 for kp in kps):
                    continue                  # whole-number values: an index or a switch, not motion
                if all(abs(kp.co.x / step - round(kp.co.x / step)) < 1e-3 for kp in kps):
                    for kp in kps:
                        kp.interpolation = 'LINEAR'
                    n_fc += 1
        print(f'[run] {_tm.OUT_FPS} fps build: {n_fc} stepped F-curves on the output grid made LINEAR', flush=True)
    if a.save:
        os.makedirs(os.path.dirname(a.save), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=a.save, compress=False)
        print(f'[run] saved {a.save}', flush=True)

sc = bpy.context.scene
frames = []
if a.frames:
    frames += [float(x) for x in a.frames.split(',') if x.strip()]
if a.range:
    lo, hi = (int(x) for x in a.range.split(':'))
    frames += list(range(lo, hi + 1))
if frames:
    if not a.out:
        raise SystemExit('--out is required to render')
    os.makedirs(a.out, exist_ok=True)
    sc.render.resolution_percentage = a.scale
    if a.scale > 100:
        # 4K: EEVEE's virtual shadow maps ask for pages per screen pixel, and the many small lights overflowed the
        # (already maximum) shadow pool at 4K ("Shadow buffer full"): missing or blocky shadows. Scaling each light's
        # shadow resolution by 100/scale keeps the page count, and the shadow detail per scene unit, of the 1080p trial.
        n_l = 0
        for ld in bpy.data.lights:
            if hasattr(ld, 'shadow_resolution_scale'):
                ld.shadow_resolution_scale = ld.shadow_resolution_scale * 100.0 / a.scale
                n_l += 1
        print(f'[run] {a.scale}%: shadow resolution scaled on {n_l} lights', flush=True)
    if a.samples:
        sc.eevee.taa_render_samples = a.samples
    if a.nomb:
        sc.render.use_motion_blur = False
    if a.fps != SCENE_FPS:
        k_sh = 0.9 * SCENE_FPS / a.fps
        sc.render.motion_blur_shutter *= k_sh
        from pdoom import kit
        fcs = kit.fcurves(sc)
        for fc in fcs:
            if fc.data_path == 'render.motion_blur_shutter':
                for kp in fc.keyframe_points:
                    kp.co[1] *= k_sh
                    kp.handle_left[1] *= k_sh
                    kp.handle_right[1] *= k_sh
        print(f'[run] {a.fps} fps: shutter x{k_sh:.3f} ({len(fcs)} scene F-curves checked)', flush=True)
        # every step (an all-CONSTANT F-curve: visibility, lamp aims, light switches, shutter changes, stepped props)
        # moves to timing.switch_frame: between two exposures and on the same side of the camera cut as at 24 fps.
        # Keyed on the cut frame itself, a step would cross-fade the shot's first frame; keyed half a frame early, it
        # would show in the outgoing shot's last 60 fps frame. Simulation toggles keep their frames (their caches
        # were baked against them).
        from pdoom import timing as _tm
        ids = [*bpy.data.objects, *bpy.data.materials, *bpy.data.node_groups, *bpy.data.shape_keys, *bpy.data.lights,
               *bpy.data.cameras, *bpy.data.worlds, *bpy.data.curves, *bpy.data.meshes, *bpy.data.armatures,
               *bpy.data.scenes]
        ids += [m.node_tree for m in [*bpy.data.materials, *bpy.data.worlds, *bpy.data.lights]
                if getattr(m, 'node_tree', None) is not None]
        n_mv = 0
        for idb in ids:
            for fc in kit.fcurves(idb):
                if 'rigid_body' in fc.data_path or 'fluid' in fc.data_path.lower():
                    continue
                kps = fc.keyframe_points
                if not len(kps) or any(kp.interpolation != 'CONSTANT' for kp in kps):
                    continue
                moved = {}
                for kp in kps:
                    moved[_tm.switch_frame(kp.co.x)] = kp.co.y      # a later key landing on the same frame wins
                x0 = min(moved)
                if abs(moved[x0] - kps[0].co.y) > 1e-9:
                    # the first keys merged (a hold key at T - 0.5/FPS and the switch at T): keep the value the curve
                    # holds before them, which the merge would otherwise lose for the whole start of the scene
                    moved[x0 - 0.5] = kps[0].co.y
                if all(abs(x - kp.co.x) < 1e-6 for x, kp in zip(sorted(moved), kps)) and len(moved) == len(kps):
                    continue
                kps.clear()
                kps.add(len(moved))
                kps.foreach_set('co', [c for x, y in sorted(moved.items()) for c in (x, y)])
                kps.foreach_set('interpolation', [0] * len(moved))
                fc.update()
                n_mv += 1
        print(f'[run] {a.fps} fps: {n_mv} stepped F-curves aligned to the cuts', flush=True)
    stop_file = os.environ.get('RENDER_STOP_FILE', 'G:/video-renders/STOP')
    for f in frames:
        if os.path.exists(stop_file):  # the pause flag (tools/procguard.py): stop at the next frame
            print(f'[run] STOP flag {stop_file}: stopping', flush=True)
            sys.exit(3)
        if a.fps != SCENE_FPS:                  # output frame k -> scene frame k * 24 / fps, exactly
            k = int(round(f))
            fi, rem = divmod(k * SCENE_FPS, a.fps)
            sub = rem / a.fps
            name = f'f_{k:05d}.png'
        else:
            fi = int(f)
            sub = f - fi
            name = f'f_{fi:05d}.png' if sub == 0 else f'f_{fi:05d}_{int(round(sub * 100)):02d}.png'
        sc.frame_set(fi, subframe=sub)
        sc.render.filepath = os.path.join(a.out, name)
        t1 = time.time()
        bpy.ops.render.render(write_still=True)
        print(f'[run] frame {f} -> {name} in {time.time() - t1:.2f}s', flush=True)
print(f'[run] done in {time.time() - t0:.1f}s', flush=True)
