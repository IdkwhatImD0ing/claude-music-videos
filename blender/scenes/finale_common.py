"""Scene-local helpers for finale.py and coda.py (not library code).

- Times: the outro's nine kicks, and `edge(t)`: the frame boundary just before the frame a cut lands on (switch set
  visibility there, so motion-blur subframes on either side of a cut see only their own set).
- Visibility of whole sets: `show(objs, t_on, t_off)` for new objects, `hide_after(objs, t)` for objects that another
  build (ilya's desk world) already keyed.
- `Cam`: a motion-control camera keyed on every frame from functions of song time (position, aim, focus, lens).
- Clip dressing at any scale: `carpet()` (a field of clips on a mesh, the mesh can be keyed to rise), `stream()`
  (clips pouring from a window, gravity scaled for the model's size), `cull_below()`.
- Space: `stars()` (a star cloth of tiny bulbs that the lens turns into bokeh), `earth_material()` (a hand-painted
  globe with city lights on its night side), `clouds()` (cotton-wool clouds on the globe).
"""
from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from pdoom import kit
from pdoom import timing as tm
from pdoom.fx import _nodes as N
from pdoom.fx import clips as C
from pdoom.fx import particles as P
from pdoom.sets import geo, phys_fstop
from pdoom.sets import materials as M

FPS = tm.FPS
V = Vector

T0 = 140.230                     # finale start
KICKS = [143.867, 144.776, 145.685, 146.594, 147.503, 148.412, 149.321, 150.230, 151.139]
T_CODA = 151.139
T_END = 156.651


def edge(t: float) -> float:
    """Song time of the frame boundary before the frame a cut at t lands on (kit.cut_to rounds to a frame)."""
    return (tm.t2f(t) - 0.5) / FPS


def ease_out(u: float, p: float = 2.0) -> float:
    """1 - (1-u)^p on [0, 1]; linear (slope p) before 0 so a camera is already moving on the cut."""
    if u < 0:
        return p * u
    if u > 1:
        return 1.0
    return 1.0 - (1.0 - u) ** p


def smooth(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def lerp(a, b, u):
    return V(a).lerp(V(b), u)


# ------------------------------------------------------------------------------------------------ visibility


def objects_in(coll) -> list:
    out = list(coll.objects)
    for c in coll.children:
        out += objects_in(c)
    return out


def show(objs, t_on=None, t_off=None, viewport=True):
    """Show objects only between t_on and t_off (render + viewport, constant keys). New objects only."""
    for ob in objs:
        if ob.get('never_render'):
            continue
        if viewport:
            kit.visible(ob, t_on, t_off)
        else:
            from pdoom.fx import vis
            vis(ob, t_on, t_off)
    return objs


def _has_fc(ob, path):
    return any(fc.data_path == path for fc in kit.fcurves(ob))


def hide_after(objs, t: float):
    """Hide objects from t on, keeping whatever visibility they had before t (keyed or not)."""
    sc = bpy.context.scene
    for ob in objs:
        for path in ('hide_render', 'hide_viewport'):
            if not _has_fc(ob, path):
                ob.keyframe_insert(path, frame=sc.frame_start - 30)
            cur = getattr(ob, path)
            setattr(ob, path, True)
            ob.keyframe_insert(path, frame=t * FPS)
            setattr(ob, path, cur)
        for fc in kit.fcurves(ob):
            if fc.data_path in ('hide_render', 'hide_viewport'):
                for kp in fc.keyframe_points:
                    kp.interpolation = 'CONSTANT'


# ------------------------------------------------------------------------------------------------ cameras


def _call(f, t):
    return f(t) if callable(f) else f


class Cam:
    """A camera keyed on every frame of [t0, t1] (plus a margin) from functions of song time. loc / target /
    focus: Vector or callable(t) -> Vector; lens: float or callable. fstop is a real-lens f-number."""

    def __init__(self, name, t0, t1, loc, target, *, lens=35.0, fstop=5.6, focus=None, coll=None, blades=7,
                 clip=(0.5, 30000.0), cut=True):
        self.name, self.t0, self.t1 = name, t0, t1
        self.loc, self.target, self.focus, self.lens = loc, target, focus, lens
        cam, tgt = kit.camera(name, lens=_call(lens, t0), loc=tuple(_call(loc, t0)), target=tuple(_call(target, t0)),
                              fstop=fstop, coll=coll, clip=clip)
        cam.data.dof.use_dof = True
        cam.data.dof.aperture_fstop = phys_fstop(fstop)
        cam.data.dof.aperture_blades = blades
        cam.data.dof.aperture_rotation = math.radians(12)
        self.cam, self.tgt = cam, tgt
        self.foc = None
        if focus is not None:
            self.foc = kit.empty(name + '.focus', tuple(_call(focus, t0)), coll)
            cam.data.dof.focus_object = self.foc
        f0, f1 = int(math.floor(t0 * FPS)) - 2, int(math.ceil(t1 * FPS)) + 2
        for f in range(f0, f1 + 1):
            t = f / FPS
            cam.location = _call(loc, t)
            cam.keyframe_insert('location', frame=f)
            tgt.location = _call(target, t)
            tgt.keyframe_insert('location', frame=f)
            if self.foc is not None:
                self.foc.location = _call(focus, t)
                self.foc.keyframe_insert('location', frame=f)
            if callable(lens):
                cam.data.lens = lens(t)
                cam.data.keyframe_insert('lens', frame=f)
        for ob in (cam, tgt, self.foc, cam.data):
            if ob is not None:
                kit.set_interp(ob, 'LINEAR')
        if cut:
            kit.cut_to(cam, t0)


def path(a, b, t0, t1, p=2.0):
    """A move from a to b over [t0, t1], ease-out (already moving at t0)."""
    a, b = V(a), V(b)
    return lambda t: a.lerp(b, ease_out((t - t0) / (t1 - t0), p))


# ------------------------------------------------------------------------------------------------ materials


def mat_cache(name):
    return bpy.data.materials.get(name)


def painted(name, color, *, rough=0.6, coat=0.0, bump=0.03, scale=6.0):
    """Model-maker's acrylic paint on card or wood: flat colour with a faint brush texture."""
    m = mat_cache(name)
    if m:
        return m
    return M.solid(name, color, rough=rough, coat=coat, coat_rough=0.2, micro=(scale, bump), spec=0.35)


def emissive(name, color, strength):
    m = mat_cache(name)
    if m:
        return m
    return M.emissive(name, color, strength)


def window_glow(name, color='#FFC27A', strength=6.0, curtain='#E9D8B8'):
    """A lit model window: warm light through a paper 'curtain' (emissive with a soft vertical falloff)."""
    m = mat_cache(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', kit.srgb(curtain))
    M.setin(b, 'Roughness', 0.8)
    M.setin(b, 'Emission Color', kit.srgb(color))
    tc = M.node(nt, 'ShaderNodeTexCoord', (-800, 0))
    nz = M.node(nt, 'ShaderNodeTexNoise', (-600, 0))
    M.setin(nz, 'Scale', 0.6)
    M.link(nt, M.sout(tc, 'Object'), M.sin(nz, 'Vector'))
    mr = M.node(nt, 'ShaderNodeMapRange', (-400, 0))
    M.setin(mr, 'To Min', strength * 0.55, 'VALUE')
    M.setin(mr, 'To Max', strength * 1.25, 'VALUE')
    M.link(nt, M.sout(nz, 'Factor'), M.sin(mr, 'Value', 'VALUE'))
    M.link(nt, M.sout(mr, 'Result', 'VALUE'), M.sin(b, 'Emission Strength'))
    m.diffuse_color = kit.srgb(color)
    return m


def flocking(name='model.grass', color='#3F5A2A'):
    """Static-grass flock on a model baseboard: felt texture, green, rough."""
    m = mat_cache(name)
    if m:
        return m
    return M.tex_mat(name, 'felt', 6, tint=color, sat=0.0, rough=(0.85, 1.0), normal=1.2, sheen=0.5, fallback=color)


def glitter(name='clip.glitter', base='#3A3E44', tint='#C9CED6', scale=0.6):
    """Distant clip cover as a material: dark steel with a field of tiny anisotropic sparkles (for the parts of a
    far shot that are too small and too out of focus for instances)."""
    m = mat_cache(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Metallic', 1.0)
    tc = M.node(nt, 'ShaderNodeTexCoord', (-1000, 0))
    vor = M.node(nt, 'ShaderNodeTexVoronoi', (-800, 0))
    M.setin(vor, 'Scale', scale)
    M.link(nt, M.sout(tc, 'Object'), M.sin(vor, 'Vector'))
    ramp = M.node(nt, 'ShaderNodeValToRGB', (-600, 0))
    cr = ramp.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.0, kit.srgb(base)
    cr.elements[1].position, cr.elements[1].color = 1.0, kit.srgb(tint)
    M.link(nt, M.sout(vor, 'Color'), M.sin(ramp, 'Factor'))
    M.link(nt, M.sout(ramp, 'Color'), M.sin(b, 'Base Color'))
    rr = M.node(nt, 'ShaderNodeMapRange', (-400, -200))
    M.setin(rr, 'To Min', 0.12, 'VALUE')
    M.setin(rr, 'To Max', 0.45, 'VALUE')
    M.link(nt, M.sout(vor, 'Distance'), M.sin(rr, 'Value', 'VALUE'))
    M.link(nt, M.sout(rr, 'Result', 'VALUE'), M.sin(b, 'Roughness'))
    bp = M.node(nt, 'ShaderNodeBump', (-200, -400))
    M.setin(bp, 'Strength', 0.6)
    M.setin(bp, 'Distance', 0.05)
    M.link(nt, M.sout(vor, 'Distance'), M.sin(bp, 'Height'))
    M.link(nt, M.sout(bp, 'Normal'), M.sin(b, 'Normal'))
    m.diffuse_color = kit.srgb(tint)
    return m


# ------------------------------------------------------------------------------------------------ meshes


def grid_mesh(name, size, n, height=None, coll=None, loc=(0, 0, 0), mats=()):
    """A (sx, sy) grid of n x m quads centred on loc; height(x, y) -> z (local) displaces it."""
    sx, sy = size
    nx, ny = (n, n) if isinstance(n, int) else n
    bm = bmesh.new()
    vs = []
    for j in range(ny + 1):
        row = []
        for i in range(nx + 1):
            x = -sx / 2 + sx * i / nx
            y = -sy / 2 + sy * j / ny
            z = height(x, y) if height else 0.0
            row.append(bm.verts.new((x, y, z)))
        vs.append(row)
    for j in range(ny):
        for i in range(nx):
            bm.faces.new((vs[j][i], vs[j][i + 1], vs[j + 1][i + 1], vs[j + 1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    for m in mats:
        me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(ob)
    ob.location = loc
    return ob


def box(name, size, loc, m, coll, bev=0.0):
    return geo.box(name, size, loc, bev=bev, segments=2, m=m, coll=coll)


# ------------------------------------------------------------------------------------------------ clips at scale


def carpet(name, surface, *, scale=1.0, density=0.34, layers=2, lod=2, coll=None, seed=5, tilt=0.35, core=None,
           m=None):
    """Clips scattered on `surface` (a mesh object; hidden from render unless core is a material, then it renders as
    the dark heart of the pile). The field follows the surface's keyed transform (it can rise). Returns the field."""
    f = C.field(name, surface=surface, density=density, scale=scale, layers=layers, lod=lod, seed=seed, coll=coll,
                tilt=tilt, m=m)
    if core is None:
        surface.hide_render = True
        surface['never_render'] = True
    else:
        surface.data.materials.clear()
        surface.data.materials.append(core)
    f['object'].visible_shadow = True
    return f


def core_mat():
    return kit.mat('clip.core', '#3A3D42', rough=0.45, metal=0.8)


def stream(name, *, source, t0, t1, rate, direction, speed, scale, floor, gscale=1.0, cone=18.0, lod=2, seed=8,
           coll=None, spin=14.0, drag=0.3):
    """clips.pour with gravity scaled by gscale (a model house's clips fall as if the house were big)."""
    g0 = P.G
    try:
        P.G = 981.0 * gscale
        ob = P.stream(name, C.proto(lod), source=source, t0=t0, t1=t1, rate=rate, direction=direction, speed=speed,
                      cone=cone, scale=scale, floor=floor, seed=seed, coll=coll, spin=spin * gscale ** 0.5,
                      drag=drag, rest_lift=C.WIRE_R * scale)
    finally:
        P.G = g0
    return ob


def cull_below(ob, keys, *, pad=0.3, interp='BEZIER'):
    """Delete a stream's clips once they are below a keyed level (song t, z): rain vanishing into a rising sea.
    Edits the stream's own node tree (scene data): a Delete Geometry before the instancing."""
    mod = next(md for md in ob.modifiers if md.type == 'NODES')
    ng = mod.node_group
    it = ng.interface.new_socket('Cull', in_out='INPUT', socket_type='NodeSocketFloat')
    it.default_value = -1e6
    gin = next(n for n in ng.nodes if n.bl_idname == 'NodeGroupInput')
    inst = next(n for n in ng.nodes if n.bl_idname == 'GeometryNodeInstanceOnPoints')
    src = inst.inputs['Points'].links[0].from_socket
    pos = ng.nodes.new('GeometryNodeInputPosition')
    sep = ng.nodes.new('ShaderNodeSeparateXYZ')
    ng.links.new(pos.outputs[0], sep.inputs[0])
    sub = ng.nodes.new('ShaderNodeMath')
    sub.operation = 'SUBTRACT'
    ng.links.new(gin.outputs['Cull'], sub.inputs[0])
    sub.inputs[1].default_value = pad
    cmp = ng.nodes.new('FunctionNodeCompare')
    cmp.data_type = 'FLOAT'
    cmp.operation = 'LESS_THAN'
    ng.links.new(sep.outputs['Z'], N.Tree.inp(cmp, 'A'))
    ng.links.new(sub.outputs[0], N.Tree.inp(cmp, 'B'))
    dl = ng.nodes.new('GeometryNodeDeleteGeometry')
    dl.domain = 'POINT'
    ng.links.new(src, dl.inputs['Geometry'])
    ng.links.new(cmp.outputs['Result'], dl.inputs['Selection'])
    ng.links.new(dl.outputs[0], inst.inputs['Points'])
    for t, z in keys:
        N.key_input(ob, mod, 'Cull', t, z, interp=interp)
    return ob


def scale_points(ob, s):
    """Set the 'scale' point attribute of a clips.pile / clips.sea points object."""
    a = ob.data.attributes.get('scale')
    if a is not None:
        a.data.foreach_set('value', [s] * len(a.data))


# ------------------------------------------------------------------------------------------------ space


def star_mat():
    m = mat_cache('space.star')
    if m:
        return m
    m, _ = M.new_mat('space.star')
    nt = m.node_tree
    b = M.principled(m)
    M.setin(b, 'Base Color', (0, 0, 0, 1))
    at = M.node(nt, 'ShaderNodeAttribute', (-600, 0))
    at.attribute_type = 'INSTANCER'
    at.attribute_name = 'star'
    M.link(nt, M.sout(at, 'Color'), M.sin(b, 'Emission Color'))
    M.setin(b, 'Emission Strength', 1.0)
    return m


def stars(name, center, *, r0=600.0, r1=1400.0, count=2500, seed=4, size=(0.4, 1.6), coll=None, cone=None,
          twinkle=True):
    """A star cloth: tiny emissive bulbs scattered in a shell (r0..r1) around center. Colour and brightness per star
    (a named 'star' colour attribute, a few warm and blue ones), a slow twinkle. cone=(axis, deg) keeps only the
    stars in a cone around axis (behind the subject), so none are wasted."""
    import numpy as np
    rng = np.random.default_rng(seed)
    n = count * 3
    d = rng.normal(0, 1, (n, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    if cone is not None:
        ax = np.array(V(cone[0]).normalized())
        keep = d @ ax > math.cos(math.radians(cone[1]))
        d = d[keep]
    d = d[:count]
    n = len(d)
    r = r0 + (r1 - r0) * rng.random(n) ** 0.7
    co = np.array(center)[None] + d * r[:, None]
    mag = rng.random(n) ** 3.0
    col = np.ones((n, 3))
    kind = rng.random(n)
    col[kind < 0.12] = (1.0, 0.72, 0.45)
    col[(kind >= 0.12) & (kind < 0.22)] = (0.65, 0.8, 1.0)
    bright = 3.0 + 60.0 * mag
    col = col * bright[:, None]
    sz = size[0] + (size[1] - size[0]) * mag
    coll = coll or kit.collection(name)
    me = bpy.data.meshes.new(name)
    me.vertices.add(n)
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    a = me.attributes.new('star', 'FLOAT_VECTOR', 'POINT')
    a.data.foreach_set('vector', col.astype(np.float32).ravel())
    s = me.attributes.new('size', 'FLOAT', 'POINT')
    s.data.foreach_set('value', sz.astype(np.float32))
    ph = me.attributes.new('phase', 'FLOAT', 'POINT')
    ph.data.foreach_set('value', (rng.random(n) * 100).astype(np.float32))
    me.update()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    ob.visible_shadow = False
    g = N.Tree(f'{name}.gn')
    geo_in = g.input_geometry()
    ico = g.out(g.node('GeometryNodeMeshIcoSphere', inputs={'Radius': 1.0, 'Subdivisions': 1}))
    ico = g.set_material(ico, star_mat())
    size_a = g.out(g.node('GeometryNodeInputNamedAttribute', data_type='FLOAT', inputs={'Name': 'size'}), 'Attribute')
    if twinkle:
        pha = g.out(g.node('GeometryNodeInputNamedAttribute', data_type='FLOAT', inputs={'Name': 'phase'}),
                    'Attribute')
        tw = 1.0 + 0.18 * g.sin(g.time() * 5.3 + pha)
        size_a = size_a * tw
    inst = g.instance(geo_in, ico, scale=size_a)
    g.output(inst)
    N.modifier(ob, g, 'stars')
    ob.visible_diffuse = ob.visible_glossy = False
    return ob


def earth_material(name='earth.paint', night_lights=True):
    """A hand-painted papier-mache globe: poster-paint oceans (brush-streaked), continents from noise (greens,
    ochres, a white ice cap at each pole), a satin varnish, and tiny warm city lights painted in luminous paint that
    glow on the night side only (where the sun doesn't reach: mixed by the light's own direction, keyed input)."""
    m = mat_cache(name)
    if m:
        return m
    m, _ = M.new_mat(name)
    nt = m.node_tree
    b = M.principled(m)
    Nn, S, L = M.node, M.sin, M.sout
    tc = Nn(nt, 'ShaderNodeTexCoord', (-1800, 0))
    obj = L(tc, 'Object')
    nz = Nn(nt, 'ShaderNodeTexNoise', (-1500, 200))
    M.setin(nz, 'Scale', 0.055)
    M.setin(nz, 'Detail', 7.0)
    M.setin(nz, 'Roughness', 0.58)
    M.setin(nz, 'Lacunarity', 2.1)
    M.link(nt, obj, S(nz, 'Vector'))
    land = Nn(nt, 'ShaderNodeMapRange', (-1200, 200))
    M.setin(land, 'From Min', 0.5, 'VALUE')
    M.setin(land, 'From Max', 0.515, 'VALUE')
    M.link(nt, L(nz, 'Factor'), S(land, 'Value', 'VALUE'))
    # land colour: greens -> ochre by a second noise; poles white
    nz2 = Nn(nt, 'ShaderNodeTexNoise', (-1500, -150))
    M.setin(nz2, 'Scale', 0.09)
    M.setin(nz2, 'Detail', 3.0)
    M.link(nt, obj, S(nz2, 'Vector'))
    lr = Nn(nt, 'ShaderNodeValToRGB', (-1200, -150))
    cr = lr.color_ramp
    cr.elements[0].position, cr.elements[0].color = 0.35, kit.srgb('#4F7A3A')
    cr.elements[1].position, cr.elements[1].color = 0.65, kit.srgb('#B8964F')
    e = cr.elements.new(0.5)
    e.color = kit.srgb('#7C8A45')
    M.link(nt, L(nz2, 'Factor'), S(lr, 'Factor'))
    # ocean: two blues with brush streaks along longitude
    sep = Nn(nt, 'ShaderNodeSeparateXYZ', (-1500, -450))
    M.link(nt, obj, S(sep, 'Vector'))
    wave = Nn(nt, 'ShaderNodeTexWave', (-1200, -450))
    M.setin(wave, 'Scale', 0.35)
    M.setin(wave, 'Distortion', 6.0)
    M.setin(wave, 'Detail', 3.0)
    M.link(nt, obj, S(wave, 'Vector'))
    oc = Nn(nt, 'ShaderNodeMix', (-900, -450), data_type='RGBA', blend_type='MIX')
    M.setin(oc, 'A', kit.srgb('#1B4F8C'), 'RGBA')
    M.setin(oc, 'B', kit.srgb('#2A6BA8'), 'RGBA')
    M.link(nt, L(wave, 'Factor'), S(oc, 'Factor', 'VALUE'))
    mix = Nn(nt, 'ShaderNodeMix', (-600, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, L(land, 'Result', 'VALUE'), S(mix, 'Factor', 'VALUE'))
    M.link(nt, L(oc, 'Result', 'RGBA'), S(mix, 'A', 'RGBA'))
    M.link(nt, L(lr, 'Color'), S(mix, 'B', 'RGBA'))
    # ice caps: |z| / r > 0.82 (object space, radius-normalised by the Normal output)
    sepn = Nn(nt, 'ShaderNodeSeparateXYZ', (-1500, -700))
    M.link(nt, L(tc, 'Normal'), S(sepn, 'Vector'))
    ab = Nn(nt, 'ShaderNodeMath', (-1300, -700), operation='ABSOLUTE')
    M.link(nt, L(sepn, 'Z'), ab.inputs[0])
    ice = Nn(nt, 'ShaderNodeMapRange', (-1100, -700))
    M.setin(ice, 'From Min', 0.9, 'VALUE')
    M.setin(ice, 'From Max', 0.93, 'VALUE')
    M.link(nt, ab.outputs[0], S(ice, 'Value', 'VALUE'))
    # painted cloud swirls: soft white poster paint in drifting bands
    cz = Nn(nt, 'ShaderNodeTexNoise', (-1500, -950))
    M.setin(cz, 'Scale', 0.07)
    M.setin(cz, 'Detail', 6.0)
    M.setin(cz, 'Distortion', 0.9)
    M.link(nt, obj, S(cz, 'Vector'))
    cm = Nn(nt, 'ShaderNodeMapRange', (-1300, -950))
    M.setin(cm, 'From Min', 0.56, 'VALUE')
    M.setin(cm, 'From Max', 0.72, 'VALUE')
    M.setin(cm, 'To Min', 0.0, 'VALUE')
    M.setin(cm, 'To Max', 0.75, 'VALUE')
    M.link(nt, L(cz, 'Factor'), S(cm, 'Value', 'VALUE'))
    cmax = Nn(nt, 'ShaderNodeMath', (-1100, -800), operation='MAXIMUM')
    M.link(nt, L(ice, 'Result', 'VALUE'), cmax.inputs[0])
    M.link(nt, L(cm, 'Result', 'VALUE'), cmax.inputs[1])
    mix2 = Nn(nt, 'ShaderNodeMix', (-350, 0), data_type='RGBA', blend_type='MIX')
    M.link(nt, cmax.outputs[0], S(mix2, 'Factor', 'VALUE'))
    M.link(nt, L(mix, 'Result', 'RGBA'), S(mix2, 'A', 'RGBA'))
    M.setin(mix2, 'B', kit.srgb('#F2F0EA'), 'RGBA')
    M.link(nt, L(mix2, 'Result', 'RGBA'), S(b, 'Base Color'))
    # varnish: oceans glossier than land
    rg = Nn(nt, 'ShaderNodeMapRange', (-350, -250))
    M.setin(rg, 'To Min', 0.28, 'VALUE')
    M.setin(rg, 'To Max', 0.62, 'VALUE')
    M.link(nt, L(land, 'Result', 'VALUE'), S(rg, 'Value', 'VALUE'))
    M.link(nt, L(rg, 'Result', 'VALUE'), S(b, 'Roughness'))
    M.setin(b, 'Coat Weight', 0.35)
    M.setin(b, 'Coat Roughness', 0.18)
    # paint texture
    bump = Nn(nt, 'ShaderNodeBump', (-350, -500))
    M.setin(bump, 'Strength', 0.25)
    M.setin(bump, 'Distance', 0.08)
    M.link(nt, L(wave, 'Factor'), S(bump, 'Height'))
    M.link(nt, L(bump, 'Normal'), S(b, 'Normal'))
    if night_lights:
        # luminous-paint city dots on land: white-noise cells, a few percent lit
        vor = Nn(nt, 'ShaderNodeTexVoronoi', (-1200, 500))
        M.setin(vor, 'Scale', 1.3)
        M.link(nt, obj, S(vor, 'Vector'))
        dot = Nn(nt, 'ShaderNodeMapRange', (-1000, 500))
        M.setin(dot, 'From Min', 0.16, 'VALUE')
        M.setin(dot, 'From Max', 0.05, 'VALUE')
        M.link(nt, L(vor, 'Distance'), S(dot, 'Value', 'VALUE'))
        cl = Nn(nt, 'ShaderNodeTexNoise', (-1200, 750))
        M.setin(cl, 'Scale', 0.25)
        M.link(nt, obj, S(cl, 'Vector'))
        clm = Nn(nt, 'ShaderNodeMapRange', (-1000, 750))
        M.setin(clm, 'From Min', 0.52, 'VALUE')
        M.setin(clm, 'From Max', 0.62, 'VALUE')
        M.link(nt, L(cl, 'Factor'), S(clm, 'Value', 'VALUE'))
        m1 = Nn(nt, 'ShaderNodeMath', (-800, 500), operation='MULTIPLY')
        M.link(nt, L(dot, 'Result', 'VALUE'), m1.inputs[0])
        M.link(nt, L(clm, 'Result', 'VALUE'), m1.inputs[1])
        m2 = Nn(nt, 'ShaderNodeMath', (-600, 500), operation='MULTIPLY')
        M.link(nt, m1.outputs[0], m2.inputs[0])
        M.link(nt, L(land, 'Result', 'VALUE'), m2.inputs[1])
        # night side only: dot(normal, sun direction) < 0 (the 'earth.sun' value node holds the direction)
        sd = Nn(nt, 'ShaderNodeCombineXYZ', (-1200, 1000))
        sd.name = sd.label = 'earth.sun'
        sd.inputs[0].default_value, sd.inputs[1].default_value, sd.inputs[2].default_value = -1.0, 0.3, 0.2
        nw = Nn(nt, 'ShaderNodeNewGeometry', (-1200, 1200))
        dp = Nn(nt, 'ShaderNodeVectorMath', (-1000, 1100), operation='DOT_PRODUCT')
        M.link(nt, L(nw, 'Normal'), dp.inputs[0])
        M.link(nt, L(sd, 'Vector'), dp.inputs[1])
        night = Nn(nt, 'ShaderNodeMapRange', (-800, 1100))
        M.setin(night, 'From Min', 0.05, 'VALUE')
        M.setin(night, 'From Max', -0.2, 'VALUE')
        M.link(nt, L(dp, 'Value'), S(night, 'Value', 'VALUE'))
        m3 = Nn(nt, 'ShaderNodeMath', (-400, 500), operation='MULTIPLY')
        M.link(nt, m2.outputs[0], m3.inputs[0])
        M.link(nt, L(night, 'Result', 'VALUE'), m3.inputs[1])
        m4 = Nn(nt, 'ShaderNodeMath', (-200, 500), operation='MULTIPLY')
        M.link(nt, m3.outputs[0], m4.inputs[0])
        m4.inputs[1].default_value = 4.0
        M.link(nt, m4.outputs[0], S(b, 'Emission Strength'))
        M.setin(b, 'Emission Color', kit.srgb('#FFB65C'))
    m.diffuse_color = kit.srgb('#2A6BA8')
    return m


def set_earth_sun(m, direction):
    """Tell the globe's paint which way the sun is (world direction TO the sun), for the night-side lights."""
    nd = m.node_tree.nodes.get('earth.sun')
    if nd is not None:
        d = V(direction).normalized()
        for i in range(3):
            nd.inputs[i].default_value = d[i]


def clouds(name, center, radius, coll, *, seed=3, count=30):
    """Cotton-wool clouds glued onto the globe: small flat tufts pulled thin (subsurface white), in loose bands.
    The fluff is baked into the mesh (no modifiers to evaluate per frame)."""
    import random
    from mathutils import noise
    rng = random.Random(seed)
    m = mat_cache('earth.cotton')
    if m is None:
        m = M.solid('earth.cotton', '#F4F2EE', rough=0.95, sss=0.5, sss_radius=(1, 1, 1), sheen=0.8, spec=0.15)
    bm = bmesh.new()
    c0 = V(center)
    for i in range(count):
        # bands: mid-latitudes and the tropics
        lat = rng.choice((-1, 1)) * rng.uniform(0.15, 0.75) if rng.random() < 0.8 else rng.uniform(-0.1, 0.1)
        a = rng.uniform(0, 2 * math.pi)
        d = V((math.sqrt(1 - lat * lat) * math.cos(a), math.sqrt(1 - lat * lat) * math.sin(a), lat))
        rot = d.to_track_quat('Z', 'Y').to_matrix().to_4x4()
        s = rng.uniform(0.5, 1.0) * radius * 0.03
        stretch = rng.uniform(2.4, 4.2)
        for k in range(rng.randint(2, 5)):
            off = V((rng.uniform(-1.6, 1.6) * stretch, rng.uniform(-0.8, 0.8), 0)) * s
            res = bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
            r = s * rng.uniform(0.55, 1.0)
            for v in res['verts']:
                p = V((v.co.x * r * stretch * 0.7, v.co.y * r * 0.8, v.co.z * r * 0.16)) + off
                n = noise.noise(p * (3.0 / s) + V((i, k, 0)))
                p = p * (1.0 + 0.18 * n)
                v.co = c0 + rot @ (p + V((0, 0, radius + s * 0.18)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(m)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob
