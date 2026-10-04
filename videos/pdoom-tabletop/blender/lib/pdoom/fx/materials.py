"""Materials the effects share: glass (EEVEE ray-traced refraction), water, broken ceramic, embers."""
from __future__ import annotations

import bpy

from .. import kit


def glass(name: str = 'fx.glass', *, tint='#F4FAFF', rough: float = 0.02, ior: float = 1.5, thin: bool = True,
          absorb: float = 0.0) -> bpy.types.Material:
    """Clear glass for EEVEE: Principled transmission 1 with ray-traced refraction. thin=True models thin walls
    (a jar, a globe, a gauge cover) as a slab; False for solid glass (a cube, a marble). absorb > 0 greens it."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    col = kit.srgb(tint)
    if absorb:
        col = (col[0] * (1 - 0.35 * absorb), col[1], col[2] * (1 - 0.2 * absorb), 1.0)
    m = kit.mat(name, col, rough=rough, transmission=1.0, ior=ior, spec=0.5)
    m.use_raytrace_refraction = True
    m.thickness_mode = 'SLAB' if thin else 'SPHERE'
    m.surface_render_method = 'DITHERED'
    m.use_backface_culling = False
    m.diffuse_color = (*col[:3], 0.2)
    if thin:
        # a slab thickness of 3 mm
        out = m.node_tree.nodes.get('Material Output')
        v = m.node_tree.nodes.new('ShaderNodeValue')
        v.outputs[0].default_value = 0.3
        m.node_tree.links.new(v.outputs[0], out.inputs['Thickness'])
    return m


def water(name: str = 'fx.water', *, tint='#E8F4FF', rough: float = 0.01, thickness: float = 0.5
          ) -> bpy.types.Material:
    """Clear water (IOR 1.333), faint blue, ray-traced refraction, modelled as a SLAB `thickness` cm thick.
    Measured in EEVEE 5.2 on drops on the desk: SLAB reads as clear water; SPHERE (with or without a thickness),
    probe-only and BLENDED all render black against the dark room."""
    if name in bpy.data.materials:
        return bpy.data.materials[name]
    m = kit.mat(name, tint, rough=rough, transmission=1.0, ior=1.333, spec=0.5)
    m.use_raytrace_refraction = True
    m.thickness_mode = 'SLAB'
    m.surface_render_method = 'DITHERED'
    m.diffuse_color = (*kit.srgb(tint)[:3], 0.2)
    out = m.node_tree.nodes.get('Material Output')
    v = m.node_tree.nodes.new('ShaderNodeValue')
    v.outputs[0].default_value = thickness
    m.node_tree.links.new(v.outputs[0], out.inputs['Thickness'])
    return m


def ceramic_break(name: str = 'fx.ceramic.break', color='#E9E2D6') -> bpy.types.Material:
    """The rough, unglazed body a broken glazed ceramic shows on its fracture faces."""
    return kit.mat(name, color, rough=0.85, spec=0.3)
