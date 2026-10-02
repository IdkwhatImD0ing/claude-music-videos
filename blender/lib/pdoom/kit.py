"""Scene kit for the Blender video (Blender 5.2): scene setup, keyframes by song time, materials, cameras, lights.

Scene scripts import this and never touch raw render settings. Everything is keyed by SONG TIME: key(obj, 'location',
t=23.873, value=(0, 0, 1)) lands on the frame that shows 23.873 s (fractional frames allowed, so hits are exact and
motion blur samples between them).

Blender 5.2 API notes baked in here (LLM-written bpy trips on these):
- Actions are layered: there is no action.fcurves. Use fcurves(obj) below.
- The engine id is 'BLENDER_EEVEE'. Motion blur settings live on scene.render.
- Colour management: set view_transform = 'AgX' by name (enum listing is empty in background mode).
- The compositor is a node group assigned to scene.compositing_node_group.
- Material/World.use_nodes is deprecated (node trees exist already).
"""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

from . import timeline
from .timing import FPS, ROOT, t2f

OUT = os.path.join(ROOT, 'out')
ASSETS = os.path.join(ROOT, 'assets')

# ------------------------------------------------------------------------------------------------ palette (linear)


def srgb(h: str) -> tuple[float, float, float, float]:
    """'#RRGGBB' -> linear RGBA."""
    h = h.lstrip('#')
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return (lin[0], lin[1], lin[2], 1.0)


PAL = {
    'clawd': '#D97757',      # Clawd's orange (vinyl)
    'clawdDark': '#A8533A',
    'ink': '#1A1614',        # eyes, deep shadows
    'cream': '#F2EBDD',      # paper, lab coat
    'wood': '#8A5A3B',
    'desk': '#5B3A26',
    'brass': '#B8893A',
    'steel': '#9AA3AD',
    'clip': '#C9CED6',       # paperclip steel
    'red': '#D2382E',        # the P(doom) needle, the kill switch
    'teal': '#2F8F8A',
    'sky': '#9CC3E6',
    'night': '#14203A',
    'glow': '#FFB24A',       # warm practicals
    'screen': '#7FD6FF',     # laptop glow
}

# ------------------------------------------------------------------------------------------------ scene setup


def new_scene(scene_id: str, *, samples: int = 64, raytrace: bool = True, motion_blur: bool = True,
              look: str = 'AgX - Medium High Contrast', exposure: float = 0.0, volumetrics: bool = True,
              window: tuple[float, float] | None = None) -> bpy.types.Scene:
    """Empty file, render settings for the video, frame range = the scene's window (global frames).

    Scenes of the edit take their window from timeline.EDIT; test scenes (ids starting with '_') pass window=(t0, t1).
    """
    bpy.ops.wm.read_homefile(use_empty=True)
    sc = bpy.context.scene
    sc.name = scene_id
    r = sc.render
    r.engine = 'BLENDER_EEVEE'
    r.resolution_x, r.resolution_y, r.resolution_percentage = 1920, 1080, 100
    r.fps, r.fps_base = FPS, 1.0
    r.film_transparent = False
    r.use_motion_blur = motion_blur
    r.motion_blur_shutter = 0.5
    r.motion_blur_position = 'CENTER'
    r.image_settings.file_format = 'PNG'
    r.image_settings.color_mode = 'RGB'
    r.image_settings.color_depth = '8'
    ee = sc.eevee
    ee.taa_render_samples = samples
    ee.use_raytracing = raytrace
    ee.use_shadows = True
    ee.shadow_ray_count = 2
    ee.shadow_step_count = 8
    ee.use_fast_gi = True
    ee.fast_gi_method = 'GLOBAL_ILLUMINATION'
    ee.motion_blur_steps = 4
    if volumetrics:
        ee.volumetric_tile_size = '8'
        ee.volumetric_samples = 64
        ee.use_volumetric_shadows = True
    try:
        ee.ray_tracing_options.resolution_scale = '1'
        ee.ray_tracing_options.use_denoise = True
    except Exception:
        pass
    vs = sc.view_settings
    sc.display_settings.display_device = 'sRGB'
    vs.view_transform = 'AgX'
    try:
        vs.look = look
    except Exception:
        pass
    vs.exposure = exposure
    # WORLD SCALE: 1 BU = 1 cm (Clawd is 8 cm long). Physical DOF then reads as real macro/miniature photography,
    # and Bullet likes objects of 0.05-10 units (a paperclip is 3 BU). Gravity in cm/s^2.
    sc.unit_settings.system = 'METRIC'
    sc.unit_settings.scale_length = 0.01
    sc.unit_settings.length_unit = 'CENTIMETERS'
    sc.gravity = (0.0, 0.0, -981.0)
    # cm-scale EEVEE: volumes only between 1 and 450 cm from the camera (the default range is in metres), and room
    # for the large bokeh of macro DOF.
    ee.use_volume_custom_range = True
    ee.volumetric_start, ee.volumetric_end = 1.0, 450.0
    ee.bokeh_max_size = 320.0
    ee.shadow_pool_size = '1024'  # many small lights overflow the default 512 MB pool (blocky, missing shadows)
    if window is not None:
        f0, f1 = t2f(window[0]), t2f(window[1]) - 1
    else:
        f0, f1 = timeline.frames(scene_id)
    sc.frame_start, sc.frame_end = f0, f1
    sc.frame_set(f0)
    # a neutral world until the scene sets its own
    world_color('#20242C', 0.3)
    return sc


def scene_window(scene_id: str) -> tuple[float, float]:
    return timeline.window(scene_id)


# ------------------------------------------------------------------------------------------------ collections


def collection(name: str, parent: bpy.types.Collection | None = None) -> bpy.types.Collection:
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    p = parent or bpy.context.scene.collection
    if c.name not in p.children:
        p.children.link(c)
    return c


def link(obj: bpy.types.Object, coll: bpy.types.Collection | None = None) -> bpy.types.Object:
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    (coll or bpy.context.scene.collection).objects.link(obj)
    return obj


# ------------------------------------------------------------------------------------------------ keyframes


def fcurves(idb) -> list:
    """All F-curves of an ID's action (layered actions in 5.x)."""
    ad = getattr(idb, 'animation_data', None)
    if not ad or not ad.action:
        return []
    out = []
    slot = ad.action_slot
    for layer in ad.action.layers:
        for strip in layer.strips:
            try:
                cb = strip.channelbag(slot)
            except Exception:
                cb = None
            if cb:
                out.extend(cb.fcurves)
    return out


def key(obj, path: str, t: float, value=None, *, index: int = -1, interp: str | None = None,
        easing: str | None = None, handle: str | None = None):
    """Set obj.<path> (or path[index]) to value and keyframe it at song time t (fractional frame t*FPS).

    interp: 'BEZIER' | 'LINEAR' | 'CONSTANT' | 'BACK' | 'ELASTIC' | 'BOUNCE' | 'EXPO' | 'SINE'...; applied to the
    new keys (the segment that STARTS at this key). easing: 'EASE_IN' | 'EASE_OUT' | 'EASE_IN_OUT' | 'AUTO'.
    """
    if value is not None:
        target, attr = _resolve(obj, path)
        if index >= 0:
            v = getattr(target, attr)
            v[index] = value
        else:
            setattr(target, attr, value)
    frame = t * FPS
    obj.keyframe_insert(data_path=path, frame=frame, index=index)
    if interp or easing or handle:
        for fc in fcurves(obj.id_data if hasattr(obj, 'id_data') else obj):
            if fc.data_path != path or (index >= 0 and fc.array_index != index):
                continue
            for kp in fc.keyframe_points:
                if abs(kp.co.x - frame) < 1e-4:
                    if interp:
                        kp.interpolation = interp
                    if easing:
                        kp.easing = easing
                    if handle:
                        kp.handle_left_type = kp.handle_right_type = handle
    return obj


def _resolve(obj, path: str):
    parts = path.split('.')
    target = obj
    for p in parts[:-1]:
        if p.endswith(']'):
            name, idx = p[:-1].split('[', 1)
            target = getattr(target, name)[idx.strip('"\'')] if not idx.isdigit() else getattr(target, name)[int(idx)]
        else:
            target = getattr(target, p)
    return target, parts[-1]


def keys(obj, path: str, pairs, *, interp: str | None = None, index: int = -1):
    """key() for a list of (t, value)."""
    for t, v in pairs:
        key(obj, path, t, v, interp=interp, index=index)
    return obj


def set_interp(obj, interp: str = 'LINEAR', path: str | None = None):
    for fc in fcurves(obj):
        if path and fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = interp


def cycles_modifier(obj, path: str | None = None):
    """Loop an F-curve (e.g. a walk cycle keyed once)."""
    for fc in fcurves(obj):
        if path and fc.data_path != path:
            continue
        if not any(m.type == 'CYCLES' for m in fc.modifiers):
            fc.modifiers.new('CYCLES')


def visible(obj, t_on: float | None = None, t_off: float | None = None):
    """Show an object only from t_on to t_off (render and viewport), by constant keys."""
    def setv(t, v):
        obj.hide_render = not v
        obj.hide_viewport = not v
        obj.keyframe_insert('hide_render', frame=t * FPS)
        obj.keyframe_insert('hide_viewport', frame=t * FPS)
    sc = bpy.context.scene
    start = sc.frame_start / FPS - 1
    setv(start, t_on is None)
    if t_on is not None:
        setv(t_on, True)
    if t_off is not None:
        setv(t_off, False)
    set_interp(obj, 'CONSTANT', 'hide_render')
    set_interp(obj, 'CONSTANT', 'hide_viewport')


# ------------------------------------------------------------------------------------------------ materials

_MATS: dict[str, bpy.types.Material] = {}


def mat(name: str, color='#808080', *, rough: float = 0.5, metal: float = 0.0, sss: float = 0.0,
        sss_radius=(1.0, 0.4, 0.25), coat: float = 0.0, coat_rough: float = 0.1, sheen: float = 0.0,
        emit=None, emit_strength: float = 0.0, transmission: float = 0.0, ior: float = 1.45,
        alpha: float = 1.0, spec: float = 0.5) -> bpy.types.Material:
    """A Principled material (cached by name). color: '#hex' (sRGB) or a linear RGBA tuple."""
    if name in _MATS and _MATS[name].name in bpy.data.materials:
        return _MATS[name]
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get('Principled BSDF')
    col = srgb(color) if isinstance(color, str) else color
    b.inputs['Base Color'].default_value = col
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metal
    b.inputs['Specular IOR Level'].default_value = spec
    if sss:
        b.inputs['Subsurface Weight'].default_value = sss
        b.inputs['Subsurface Radius'].default_value = sss_radius
        b.inputs['Subsurface Scale'].default_value = 0.05
    if coat:
        b.inputs['Coat Weight'].default_value = coat
        b.inputs['Coat Roughness'].default_value = coat_rough
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
    if emit is not None:
        b.inputs['Emission Color'].default_value = srgb(emit) if isinstance(emit, str) else emit
        b.inputs['Emission Strength'].default_value = emit_strength
    if transmission:
        b.inputs['Transmission Weight'].default_value = transmission
        b.inputs['IOR'].default_value = ior
    if alpha < 1:
        b.inputs['Alpha'].default_value = alpha
    m.diffuse_color = col
    _MATS[name] = m
    return m


def bsdf(m: bpy.types.Material):
    return m.node_tree.nodes.get('Principled BSDF')


def emission_mat(name: str, color='#FFFFFF', strength: float = 5.0) -> bpy.types.Material:
    return mat(name, '#000000', rough=1.0, emit=color, emit_strength=strength, spec=0.0)


def assign(obj, m: bpy.types.Material, slot: int | None = None):
    if slot is None:
        obj.data.materials.clear()
        obj.data.materials.append(m)
    else:
        while len(obj.data.materials) <= slot:
            obj.data.materials.append(m)
        obj.data.materials[slot] = m
    return obj


# ------------------------------------------------------------------------------------------------ primitives


def box(name: str, size=(1, 1, 1), loc=(0, 0, 0), *, bevel: float = 0.0, segments: int = 4, m=None,
        coll=None) -> bpy.types.Object:
    """A box with an optional bevel modifier (the toy look lives in the bevels). Size is the full extent."""
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new('bevel', 'BEVEL')
        mod.width, mod.segments, mod.limit_method = bevel, segments, 'ANGLE'
        mod.harden_normals = False
        smooth(o)
    if m:
        assign(o, m)
    if coll:
        link(o, coll)
    return o


def smooth(o, angle_deg: float = 40.0):
    """Smooth shading with sharp edges above angle (5.x: shade_auto_smooth adds a modifier)."""
    for p in o.data.polygons:
        p.use_smooth = True
    try:
        with bpy.context.temp_override(object=o, active_object=o, selected_objects=[o], selected_editable_objects=[o]):
            bpy.ops.object.shade_auto_smooth(angle=math.radians(angle_deg))
    except Exception:
        pass
    return o


def cylinder(name, r=0.5, depth=1.0, loc=(0, 0, 0), *, verts=48, bevel=0.0, m=None, coll=None, rot=(0, 0, 0)):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=depth, vertices=verts, location=loc, rotation=rot)
    o = bpy.context.object
    o.name = name
    if bevel:
        mod = o.modifiers.new('bevel', 'BEVEL')
        mod.width, mod.segments, mod.limit_method = bevel, 3, 'ANGLE'
    smooth(o)
    if m:
        assign(o, m)
    if coll:
        link(o, coll)
    return o


def sphere(name, r=0.5, loc=(0, 0, 0), *, m=None, coll=None, subdiv=4):
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, subdivisions=subdiv, location=loc)
    o = bpy.context.object
    o.name = name
    smooth(o, 180)
    if m:
        assign(o, m)
    if coll:
        link(o, coll)
    return o


def empty(name, loc=(0, 0, 0), coll=None, kind='PLAIN_AXES', size=0.2):
    o = bpy.data.objects.new(name, None)
    o.empty_display_type, o.empty_display_size = kind, size
    o.location = loc
    (coll or bpy.context.scene.collection).objects.link(o)
    return o


def parent(child, par, keep_transform=True):
    mw = child.matrix_world.copy()
    child.parent = par
    if keep_transform:
        child.matrix_world = mw
    return child


# ------------------------------------------------------------------------------------------------ camera


def camera(name='cam', lens: float = 50.0, loc=(0, -60, 20), target=(0, 0, 5), *, fstop: float | None = None,
           sensor: float = 36.0, coll=None, clip=(0.1, 20000.0)):
    """A camera that looks at an Empty target (animate both). Returns (cam, target). Sets it as the scene camera.

    fstop: depth of field focused on the target (miniature look: small scenes + low f-number = tilt-shift feel).
    """
    cd = bpy.data.cameras.new(name)
    cd.lens, cd.sensor_width = lens, sensor
    cd.clip_start, cd.clip_end = clip
    cam = bpy.data.objects.new(name, cd)
    (coll or bpy.context.scene.collection).objects.link(cam)
    cam.location = loc
    tgt = empty(name + '.target', target, coll)
    c = cam.constraints.new('TRACK_TO')
    c.target, c.track_axis, c.up_axis = tgt, 'TRACK_NEGATIVE_Z', 'UP_Y'
    if fstop:
        # EEVEE 5.2 ignores the unit scale for DOF: at 1 BU = 1 cm a set f-stop blurs ~100x too little. Scale it so
        # f/2.8 looks like a real f/2.8 macro lens (measured by the sets agent: 12 px as set, 114 px scaled, ~120 in
        # theory). sets.phys_fstop() does the same for cameras made elsewhere.
        cd.dof.use_dof = True
        cd.dof.focus_object = tgt
        cd.dof.aperture_fstop = fstop * bpy.context.scene.unit_settings.scale_length
    bpy.context.scene.camera = cam
    return cam, tgt


def cut_to(cam, t: float):
    """Switch the scene camera to cam at song time t (a timeline marker bound to the camera)."""
    sc = bpy.context.scene
    mk = sc.timeline_markers.new(f'{cam.name}@{t:.3f}', frame=t2f(t))
    mk.camera = cam
    return mk


def shake(obj, t0: float, t1: float, amp: float = 0.02, freq: float = 12.0, seed: int = 1, path='location'):
    """Noise modifier on an object's channel over [t0, t1] (camera shake), deterministic by seed.

    The channel must already be keyed (it only adds a modifier; keying here would break an existing keyed move)."""
    if not any(fc.data_path == path for fc in fcurves(obj)):
        obj.keyframe_insert(path, frame=t0 * FPS)
    for fc in fcurves(obj):
        if fc.data_path != path:
            continue
        n = fc.modifiers.new('NOISE')
        n.scale, n.strength, n.phase = FPS / freq, amp * 2, seed * 7.3 + fc.array_index * 3.1
        n.use_restricted_range = True
        n.frame_start, n.frame_end = t0 * FPS, t1 * FPS
        n.blend_in = n.blend_out = min(3.0, (t1 - t0) * FPS / 4)


# ------------------------------------------------------------------------------------------------ lights and world


def area(name, loc, target=(0, 0, 0), *, power=200.0, size=1.0, color='#FFFFFF', shape='DISK', coll=None,
         shadow_soft=True):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.shape, ld.size = power, shape, size
    ld.color = srgb(color)[:3]
    o = bpy.data.objects.new(name, ld)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    aim(o, target)
    return o


def spot(name, loc, target=(0, 0, 0), *, power=500.0, angle_deg=35, blend=0.3, radius=0.05, color='#FFFFFF', coll=None):
    ld = bpy.data.lights.new(name, 'SPOT')
    ld.energy, ld.spot_size, ld.spot_blend, ld.shadow_soft_size = power, math.radians(angle_deg), blend, radius
    ld.color = srgb(color)[:3]
    o = bpy.data.objects.new(name, ld)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    aim(o, target)
    return o


def point(name, loc, *, power=50.0, radius=0.05, color='#FFFFFF', coll=None):
    ld = bpy.data.lights.new(name, 'POINT')
    ld.energy, ld.shadow_soft_size = power, radius
    ld.color = srgb(color)[:3]
    o = bpy.data.objects.new(name, ld)
    (coll or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    return o


def sun(name, direction=(0.3, -0.4, -1.0), *, strength=3.0, angle_deg=2.0, color='#FFFFFF', coll=None):
    ld = bpy.data.lights.new(name, 'SUN')
    ld.energy, ld.angle = strength, math.radians(angle_deg)
    ld.color = srgb(color)[:3]
    o = bpy.data.objects.new(name, ld)
    (coll or bpy.context.scene.collection).objects.link(o)
    d = Vector(direction).normalized()
    o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()
    return o


def aim(o, target):
    d = Vector(target) - Vector(o.location)
    if d.length > 1e-9:
        o.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()


def world_color(color='#20242C', strength: float = 1.0):
    w = bpy.context.scene.world or bpy.data.worlds.new('world')
    bpy.context.scene.world = w
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = srgb(color) if isinstance(color, str) else color
    bg.inputs['Strength'].default_value = strength
    return w


def world_hdri(path: str, strength: float = 1.0, rotation_deg: float = 0.0, *, background: tuple | None = None):
    """An HDRI world. background: optional (color, strength) seen by the camera instead of the HDRI."""
    w = bpy.context.scene.world or bpy.data.worlds.new('world')
    bpy.context.scene.world = w
    nt = w.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputWorld')
    env = nt.nodes.new('ShaderNodeTexEnvironment')
    env.image = bpy.data.images.load(path, check_existing=True)
    mapn = nt.nodes.new('ShaderNodeMapping')
    mapn.inputs['Rotation'].default_value[2] = math.radians(rotation_deg)
    tc = nt.nodes.new('ShaderNodeTexCoord')
    nt.links.new(tc.outputs['Generated'], mapn.inputs['Vector'])
    nt.links.new(mapn.outputs['Vector'], env.inputs['Vector'])
    bg = nt.nodes.new('ShaderNodeBackground')
    bg.inputs['Strength'].default_value = strength
    nt.links.new(env.outputs['Color'], bg.inputs['Color'])
    if background:
        bg2 = nt.nodes.new('ShaderNodeBackground')
        col, st = background
        bg2.inputs['Color'].default_value = srgb(col) if isinstance(col, str) else col
        bg2.inputs['Strength'].default_value = st
        lp = nt.nodes.new('ShaderNodeLightPath')
        mix = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(lp.outputs['Is Camera Ray'], mix.inputs['Fac'])
        nt.links.new(bg.outputs['Background'], mix.inputs[1])
        nt.links.new(bg2.outputs['Background'], mix.inputs[2])
        nt.links.new(mix.outputs['Shader'], out.inputs['Surface'])
    else:
        nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
    return w


def asset(*parts) -> str:
    """Path under assets/ (git-ignored; tools/fetch_assets.py downloads them)."""
    return os.path.join(ASSETS, *parts)


# ------------------------------------------------------------------------------------------------ compositor


def post(*, bloom: float = 0.0, bloom_threshold: float = 1.0, bloom_size: float = 0.5, vignette: float = 0.0,
         grain: float = 0.0):
    """Compositor finish: bloom (Glare 'Bloom') and a soft vignette. Keep subtle: EEVEE is already filmic."""
    sc = bpy.context.scene
    ng = bpy.data.node_groups.new('post', 'CompositorNodeTree')
    sc.compositing_node_group = ng
    rl = ng.nodes.new('CompositorNodeRLayers')
    out = ng.nodes.new('NodeGroupOutput')
    ng.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    cur = rl.outputs['Image']
    if bloom > 0:
        g = ng.nodes.new('CompositorNodeGlare')
        _set_input_or_prop(g, 'Type', 'glare_type', 'Bloom')
        _set_input_or_prop(g, 'Threshold', 'threshold', bloom_threshold)
        _set_input_or_prop(g, 'Size', 'size', bloom_size)
        _set_input_or_prop(g, 'Strength', 'mix', bloom)
        ng.links.new(cur, g.inputs['Image'])
        cur = g.outputs['Image']
    if vignette > 0:
        ell = ng.nodes.new('CompositorNodeEllipseMask')
        _set_input_or_prop(ell, 'Size', 'width', (0.95, 0.85))
        blur = ng.nodes.new('CompositorNodeBlur')
        _set_input_or_prop(blur, 'Size', 'size_x', (300, 300))
        ng.links.new(ell.outputs[0], blur.inputs['Image'])
        # darken the edges: multiply by mix(1, mask, vignette)
        mixn = ng.nodes.new('ShaderNodeMix')
        mixn.data_type, mixn.blend_type = 'RGBA', 'MULTIPLY'
        sock = {x.identifier: x for x in mixn.inputs}
        sock['Factor_Float'].default_value = vignette
        ng.links.new(cur, sock['A_Color'])
        ng.links.new(blur.outputs[0], sock['B_Color'])
        cur = next(x for x in mixn.outputs if x.identifier == 'Result_Color')
    ng.links.new(cur, out.inputs[0])
    return ng


def _set_input_or_prop(node, input_name, prop, value):
    """5.x moved many compositor node properties to inputs; set whichever exists."""
    if input_name in node.inputs:
        s = node.inputs[input_name]
        try:
            s.default_value = value
            return
        except Exception:
            pass
    if hasattr(node, prop):
        try:
            setattr(node, prop, value if not isinstance(value, str) else value.upper())
        except Exception:
            try:
                setattr(node, prop, value)
            except Exception:
                pass


# ------------------------------------------------------------------------------------------------ bake / save


def bake_all():
    """Bake every point cache (rigid bodies, cloth, particles) for the scene's frame range."""
    sc = bpy.context.scene
    with bpy.context.temp_override(scene=sc):
        bpy.ops.ptcache.free_bake_all()
        bpy.ops.ptcache.bake_all(bake=True)


def cache_dir(scene_id: str, what: str) -> str:
    d = os.path.join(OUT, 'cache', scene_id, what)
    os.makedirs(d, exist_ok=True)
    return d
