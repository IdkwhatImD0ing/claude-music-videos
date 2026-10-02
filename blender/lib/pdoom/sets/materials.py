"""Materials for the sets: true-scale PBR from the downloaded CC0 textures (assets/tex/<key>/) plus the desk's
hand-built surfaces (glazed ceramic, brass, enamel, plastic, rubber, glass, ink).

All texture materials read the object's 'UVMap' (the sets write UVs in cm) and scale by 1/tile_cm, so a texture shows at
its real size. If assets/ is missing (fetch_assets.py not run), texture materials fall back to flat colours and print
a warning, so builds never fail on a fresh checkout.
"""
from __future__ import annotations

import math
import os

import bpy

from .. import kit
from .geo import hash01

TEX = os.path.join(kit.ASSETS, 'tex')
_CACHE: dict[str, bpy.types.Material] = {}
_WARNED = set()

# ------------------------------------------------------------------------------------------------ node helpers


def node(nt, typ, loc=(0, 0), **props):
    n = nt.nodes.new(typ)
    n.location = loc
    for k, v in props.items():
        setattr(n, k, v)
    return n


def sin(n, name, typ=None):
    """Input socket by name (optionally by type, for nodes with duplicate names)."""
    for s in n.inputs:
        if s.name == name and (typ is None or s.type == typ) and s.enabled:
            return s
    for s in n.inputs:
        if s.name == name and (typ is None or s.type == typ):
            return s
    raise KeyError(f'{n.bl_idname} has no input {name!r} ({typ})')


def sout(n, name, typ=None):
    for s in n.outputs:
        if s.name == name and (typ is None or s.type == typ) and s.enabled:
            return s
    for s in n.outputs:
        if s.name == name and (typ is None or s.type == typ):
            return s
    raise KeyError(f'{n.bl_idname} has no output {name!r} ({typ})')


def link(nt, a, b):
    nt.links.new(a, b)


def setin(n, name, value, typ=None):
    sin(n, name, typ).default_value = value


def new_mat(name: str):
    if name in _CACHE and _CACHE[name].name in bpy.data.materials:
        return _CACHE[name], False
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    _CACHE[name] = m
    return m, True


def principled(m):
    return m.node_tree.nodes.get('Principled BSDF')


def col(c):
    return kit.srgb(c) if isinstance(c, str) else c


# ------------------------------------------------------------------------------------------------ textures


def tex_path(key: str, mp: str) -> str | None:
    p = os.path.join(TEX, key, f'{mp}.jpg')
    return p if os.path.exists(p) else None


def image(path: str, noncolor: bool):
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = 'Non-Color' if noncolor else 'sRGB'
    # name it after its texture set (assets/tex/<key>/<map>.jpg -> '<key>.<map>')
    key = os.path.basename(os.path.dirname(path))
    want = f'{key}.{os.path.splitext(os.path.basename(path))[0]}'
    if img.name != want and want not in bpy.data.images:
        img.name = want
    return img


def uv_mapping(nt, tile_cm: float, seed: str, rot_deg: float = 0.0, loc=(-900, 0)):
    tc = node(nt, 'ShaderNodeTexCoord', loc)
    mp = node(nt, 'ShaderNodeMapping', (loc[0] + 200, loc[1]))
    s = 1.0 / tile_cm
    setin(mp, 'Scale', (s, s, s))
    setin(mp, 'Location', (hash01(seed, 'u'), hash01(seed, 'v'), 0.0))
    setin(mp, 'Rotation', (0.0, 0.0, math.radians(rot_deg)))
    link(nt, sout(tc, 'UV'), sin(mp, 'Vector'))
    return mp


def tex_mat(name: str, key: str, tile_cm: float, *, tint=None, tint_amount: float = 1.0, hue: float = 0.5,
            sat: float = 1.0, val: float = 1.0, rough=(0.0, 1.0), normal: float = 1.0, metal=0.0, coat: float = 0.0,
            coat_rough: float = 0.08, spec: float = 0.5, sheen: float = 0.0, rot_deg: float = 0.0,
            micro: tuple | None = None, fallback='#808080', sss: float = 0.0):
    """A PBR material from assets/tex/<key>/ at true scale.

    tint: '#hex' multiplied over the colour map (tint_amount 0..1). hue/sat/val: HueSaturation node (0.5 = no hue
    shift). rough: the roughness map is remapped to [lo, hi]. metal: a float, or 'map' for the metalness map.
    micro: (scale_per_cm, strength) adds a fine procedural bump (lacquer pores / fibres) that holds up in macro.
    """
    m, fresh = new_mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = principled(m)
    b.location = (400, 0)
    pd = tex_path(key, 'diff')
    if pd is None:
        if key not in _WARNED:
            print(f'[sets] WARNING: assets/tex/{key} missing (run python tools/fetch_assets.py); flat colour used')
            _WARNED.add(key)
        setin(b, 'Base Color', col(tint or fallback))
        setin(b, 'Roughness', (rough[0] + rough[1]) / 2)
        setin(b, 'Coat Weight', coat)
        return m
    mp = uv_mapping(nt, tile_cm, name, rot_deg)
    vec = sout(mp, 'Vector')
    # colour
    td = node(nt, 'ShaderNodeTexImage', (-500, 300), image=image(pd, False))
    link(nt, vec, sin(td, 'Vector'))
    hs = node(nt, 'ShaderNodeHueSaturation', (-250, 300))
    setin(hs, 'Hue', hue)
    setin(hs, 'Saturation', sat)
    setin(hs, 'Value', val)
    link(nt, sout(td, 'Color'), sin(hs, 'Color'))
    cur = sout(hs, 'Color')
    if tint is not None:
        mx = node(nt, 'ShaderNodeMix', (0, 300), data_type='RGBA', blend_type='MULTIPLY')
        setin(mx, 'Factor', tint_amount, 'VALUE')
        link(nt, cur, sin(mx, 'A', 'RGBA'))
        setin(mx, 'B', col(tint), 'RGBA')
        cur = sout(mx, 'Result', 'RGBA')
    link(nt, cur, sin(b, 'Base Color'))
    # roughness
    pr = tex_path(key, 'rough')
    if pr:
        tr = node(nt, 'ShaderNodeTexImage', (-500, 0), image=image(pr, True))
        link(nt, vec, sin(tr, 'Vector'))
        mr = node(nt, 'ShaderNodeMapRange', (-250, 0))
        setin(mr, 'To Min', rough[0], 'VALUE')
        setin(mr, 'To Max', rough[1], 'VALUE')
        link(nt, sout(tr, 'Color'), sin(mr, 'Value', 'VALUE'))
        link(nt, sout(mr, 'Result', 'VALUE'), sin(b, 'Roughness'))
    else:
        setin(b, 'Roughness', (rough[0] + rough[1]) / 2)
    # normal (+ micro bump)
    pn = tex_path(key, 'nor')
    ncur = None
    if pn and normal > 0:
        tn = node(nt, 'ShaderNodeTexImage', (-500, -300), image=image(pn, True))
        link(nt, vec, sin(tn, 'Vector'))
        nm = node(nt, 'ShaderNodeNormalMap', (-250, -300))
        setin(nm, 'Strength', normal)
        link(nt, sout(tn, 'Color'), sin(nm, 'Color'))
        ncur = sout(nm, 'Normal')
    if micro:
        ncur = micro_bump(nt, micro[0], micro[1], ncur, loc=(0, -450))
    if ncur is not None:
        link(nt, ncur, sin(b, 'Normal'))
    # metal
    if metal == 'map' and tex_path(key, 'metal'):
        tm = node(nt, 'ShaderNodeTexImage', (-500, -600), image=image(tex_path(key, 'metal'), True))
        link(nt, vec, sin(tm, 'Vector'))
        link(nt, sout(tm, 'Color'), sin(b, 'Metallic'))
    else:
        setin(b, 'Metallic', float(metal) if metal != 'map' else 1.0)
    setin(b, 'Specular IOR Level', spec)
    if coat:
        setin(b, 'Coat Weight', coat)
        setin(b, 'Coat Roughness', coat_rough)
        if ncur is not None and micro:
            pass
    if sheen:
        setin(b, 'Sheen Weight', sheen)
    if sss:
        setin(b, 'Subsurface Weight', sss)
        setin(b, 'Subsurface Scale', 0.1)
    m.diffuse_color = col(tint or fallback)
    return m


def micro_bump(nt, scale_per_cm: float, strength: float, normal_in=None, loc=(0, -450), coord='Object'):
    tc = node(nt, 'ShaderNodeTexCoord', (loc[0] - 600, loc[1]))
    nz = node(nt, 'ShaderNodeTexNoise', (loc[0] - 400, loc[1]))
    setin(nz, 'Scale', scale_per_cm)
    setin(nz, 'Detail', 6.0)
    setin(nz, 'Roughness', 0.6)
    link(nt, sout(tc, coord), sin(nz, 'Vector'))
    bp = node(nt, 'ShaderNodeBump', (loc[0] - 200, loc[1]))
    setin(bp, 'Strength', strength)
    setin(bp, 'Distance', 0.02)
    link(nt, sout(nz, 'Factor'), sin(bp, 'Height'))
    if normal_in is not None:
        link(nt, normal_in, sin(bp, 'Normal'))
    return sout(bp, 'Normal')


# ------------------------------------------------------------------------------------------------ the set's palette of materials


def desk_wood():
    """The desktop: dark hardwood, satin lacquer (coat) with faint smudges; real grain at ~1:1."""
    m = tex_mat('set.deskwood', 'desk_wood', 120, hue=0.49, sat=0.85, val=0.9, rough=(0.28, 0.55), normal=0.6,
                coat=0.55, coat_rough=0.07, micro=(18.0, 0.04), fallback='#5B3A26')
    _coat_smudges(m)
    return m


def _coat_smudges(m):
    """Vary the lacquer's roughness with a soft noise (fingerprints, wiped areas) so the lamp's reflection breaks up."""
    nt = m.node_tree
    b = principled(m)
    if b.inputs['Coat Weight'].default_value <= 0 or any(n.label == 'smudge' for n in nt.nodes):
        return
    tc = node(nt, 'ShaderNodeTexCoord', (-600, -800))
    nz = node(nt, 'ShaderNodeTexNoise', (-400, -800))
    nz.label = 'smudge'
    setin(nz, 'Scale', 0.08)
    setin(nz, 'Detail', 4.0)
    link(nt, sout(tc, 'Object'), sin(nz, 'Vector'))
    mr = node(nt, 'ShaderNodeMapRange', (-200, -800))
    setin(mr, 'From Min', 0.35, 'VALUE')
    setin(mr, 'From Max', 0.7, 'VALUE')
    setin(mr, 'To Min', 0.06, 'VALUE')
    setin(mr, 'To Max', 0.26, 'VALUE')
    link(nt, sout(nz, 'Factor'), sin(mr, 'Value', 'VALUE'))
    link(nt, sout(mr, 'Result', 'VALUE'), sin(b, 'Coat Roughness'))


def plaster(tint='#8E8A86'):
    return tex_mat('set.plaster', 'wall_plaster', 200, tint=tint, tint_amount=1.0, sat=0.6, val=1.0,
                   rough=(0.75, 0.95), normal=0.8, fallback=tint)


def floor_wood():
    return tex_mat('set.floor', 'floor_wood', 170, val=0.55, sat=0.8, rough=(0.35, 0.7), normal=0.6, coat=0.2,
                   fallback='#3A2A20')


def paper(name='set.paper', tint='#F4EFE4', tile=30):
    return tex_mat(name, 'paper', tile, tint=tint, sat=0.2, rough=(0.7, 0.9), normal=0.5, fallback=tint,
                   sheen=0.1, sss=0.05)


def cardboard(name='set.cardboard', tint=None):
    return tex_mat(name, 'cardboard', 50, tint=tint, rough=(0.75, 0.95), normal=1.0, fallback='#B98E5A')


def felt(name='set.felt', tint='#2F4A3C'):
    return tex_mat(name, 'felt', 25, tint=tint, sat=0.0, rough=(0.85, 1.0), normal=1.0, sheen=0.6, fallback=tint)


def brushed(name='set.brushed', tint='#B9BDC2', rough=(0.22, 0.4), tile=40, val=1.0):
    return tex_mat(name, 'brushed_metal', tile, tint=tint, sat=0.0, val=val, rough=rough, normal=0.3, metal=1.0,
                   fallback=tint)


def linen(name='set.linen', tint='#EDE6D6'):
    return tex_mat(name, 'linen', 40, tint=tint, sat=0.0, rough=(0.8, 1.0), normal=1.0, sheen=0.4, fallback=tint)


def solid(name, color, *, rough=0.5, metal=0.0, coat=0.0, coat_rough=0.05, spec=0.5, sss=0.0,
          sss_radius=(1.0, 0.5, 0.3), micro=None, emit=None, emit_strength=0.0, aniso=0.0, sheen=0.0):
    """A plain Principled material (cached), optional micro bump in object space."""
    m, fresh = new_mat(name)
    if not fresh:
        return m
    b = principled(m)
    setin(b, 'Base Color', col(color))
    setin(b, 'Roughness', rough)
    setin(b, 'Metallic', metal)
    setin(b, 'Specular IOR Level', spec)
    if coat:
        setin(b, 'Coat Weight', coat)
        setin(b, 'Coat Roughness', coat_rough)
    if sss:
        setin(b, 'Subsurface Weight', sss)
        setin(b, 'Subsurface Radius', sss_radius)
        setin(b, 'Subsurface Scale', 0.2)
    if aniso:
        setin(b, 'Anisotropic', aniso)
    if sheen:
        setin(b, 'Sheen Weight', sheen)
    if emit is not None:
        setin(b, 'Emission Color', col(emit))
        setin(b, 'Emission Strength', emit_strength)
    if micro:
        link(m.node_tree, micro_bump(m.node_tree, micro[0], micro[1]), sin(b, 'Normal'))
    m.diffuse_color = col(color)
    return m


def ceramic(name, color, *, rough=0.12):
    """Glazed ceramic: glossy coat over a slightly soft base, faint handmade waviness."""
    return solid(name, color, rough=0.35, coat=1.0, coat_rough=rough, spec=0.5, sss=0.03, micro=(0.6, 0.05))


def brass(name='set.brass', color='#C8A15A', rough=0.28):
    m, fresh = new_mat(name)
    if not fresh:
        return m
    nt = m.node_tree
    b = principled(m)
    setin(b, 'Base Color', col(color))
    setin(b, 'Metallic', 1.0)
    # patina: roughness and colour vary softly
    tc = node(nt, 'ShaderNodeTexCoord', (-800, 0))
    nz = node(nt, 'ShaderNodeTexNoise', (-600, 0))
    setin(nz, 'Scale', 0.9)
    setin(nz, 'Detail', 5.0)
    link(nt, sout(tc, 'Object'), sin(nz, 'Vector'))
    mr = node(nt, 'ShaderNodeMapRange', (-400, 0))
    setin(mr, 'To Min', rough * 0.6, 'VALUE')
    setin(mr, 'To Max', rough * 1.5, 'VALUE')
    link(nt, sout(nz, 'Factor'), sin(mr, 'Value', 'VALUE'))
    link(nt, sout(mr, 'Result', 'VALUE'), sin(b, 'Roughness'))
    mx = node(nt, 'ShaderNodeMix', (-200, 200), data_type='RGBA', blend_type='MIX')
    link(nt, sout(nz, 'Factor'), sin(mx, 'Factor', 'VALUE'))
    setin(mx, 'A', col(color), 'RGBA')
    setin(mx, 'B', col('#9C7B45'), 'RGBA')
    link(nt, sout(mx, 'Result', 'RGBA'), sin(b, 'Base Color'))
    link(nt, micro_bump(nt, 30.0, 0.03, loc=(0, -400)), sin(b, 'Normal'))
    m.diffuse_color = col(color)
    return m


def chrome(name='set.chrome'):
    return solid(name, '#D8DCE0', rough=0.08, metal=1.0)


def steel(name='set.steel', rough=0.18):
    return solid(name, kit.PAL['clip'], rough=rough, metal=1.0, micro=(60.0, 0.02))


def enamel(name, color, *, rough=0.32, coat=0.35):
    return solid(name, color, rough=rough, coat=coat, coat_rough=0.12, micro=(4.0, 0.03))


def plastic(name, color, *, rough=0.35, coat=0.0):
    return solid(name, color, rough=rough, coat=coat, coat_rough=0.1, spec=0.5, micro=(8.0, 0.015))


def rubber(name='set.rubber', color='#141414'):
    return solid(name, color, rough=0.62, spec=0.35, micro=(20.0, 0.03))


def ink(name='set.ink', color='#1A1614', rough=0.45):
    return solid(name, color, rough=rough)


def glass(name='set.glass', *, tint='#FFFFFF', rough=0.02, ior=1.5, thin=True):
    """Clear glass for EEVEE: transmission with ray-traced refraction (sees the objects behind it)."""
    m, fresh = new_mat(name)
    if not fresh:
        return m
    b = principled(m)
    setin(b, 'Base Color', col(tint))
    setin(b, 'Roughness', rough)
    setin(b, 'Transmission Weight', 1.0)
    setin(b, 'IOR', ior)
    if thin:
        setin(b, 'Thin Wall', True)
    glassify(m)
    return m


def glassify(m, thickness=0.0):
    """EEVEE settings a see-through material needs (ray-traced refraction, slab thickness)."""
    for attr, v in (('use_raytrace_refraction', True), ('thickness_mode', 'SLAB'), ('surface_render_method', 'DITHERED'),
                    ('use_transparent_shadow', True)):
        try:
            setattr(m, attr, v)
        except Exception:
            pass
    out = m.node_tree.nodes.get('Material Output')
    if out is not None and 'Thickness' in out.inputs:
        out.inputs['Thickness'].default_value = thickness
    m.use_backface_culling = False
    return m


def emissive(name, color='#FFFFFF', strength=5.0):
    m, fresh = new_mat(name)
    if not fresh:
        return m
    b = principled(m)
    setin(b, 'Base Color', (0, 0, 0, 1))
    setin(b, 'Roughness', 0.4)
    setin(b, 'Emission Color', col(color))
    setin(b, 'Emission Strength', strength)
    m.diffuse_color = col(color)
    return m
