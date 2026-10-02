"""A tiny expression builder for geometry-node trees (Blender 5.2), so effects read like maths instead of 200 lines of
nodes.new / links.new. Used by the fx kit's stateless particle systems and instanced fields.

    g = Tree('sparks')
    geo = g.input_geometry()
    t = g.time()                              # song seconds (Scene Time, includes the motion-blur subframe)
    k = g.param('Rate', 'FLOAT', 3.0)          # a modifier input (set_input / key_input)
    pts = g.points(500)
    i = g.index()
    v = g.vec(g.rand(-1, 1, i, 1), g.rand(-1, 1, i, 2), g.rand(2, 4, i, 3))
    pos = v * (t - 3.0) + g.vec(0, 0, -490.5) * (t - 3.0) ** 2
    g.output(g.set_position(pts, pos))

Sockets are wrapped in S; +, -, *, /, **, unary -, <, > build Math / Vector Math / Compare nodes. Numbers and tuples
are folded into socket default values. 5.2 notes: Math inputs all share the name 'Value' (use indices); Random Value,
Switch, Compare and Mix change their sockets with their data type (set the type first, then look sockets up by name
among the ENABLED ones).
"""
from __future__ import annotations

import bpy

_VEC = ('VECTOR', 'RGBA')


class S:
    """A node output socket inside a Tree."""

    __slots__ = ('g', 's')

    def __init__(self, g: 'Tree', s):
        self.g, self.s = g, s

    @property
    def type(self) -> str:
        return self.s.type

    # arithmetic -------------------------------------------------------------------------------------------------
    def _bin(self, other, op, rev=False):
        a, b = (other, self) if rev else (self, other)
        return self.g.op(op, a, b)

    def __add__(self, o): return self._bin(o, 'ADD')
    def __radd__(self, o): return self._bin(o, 'ADD', True)
    def __sub__(self, o): return self._bin(o, 'SUBTRACT')
    def __rsub__(self, o): return self._bin(o, 'SUBTRACT', True)
    def __mul__(self, o): return self._bin(o, 'MULTIPLY')
    def __rmul__(self, o): return self._bin(o, 'MULTIPLY', True)
    def __truediv__(self, o): return self._bin(o, 'DIVIDE')
    def __rtruediv__(self, o): return self._bin(o, 'DIVIDE', True)
    def __pow__(self, o): return self._bin(o, 'POWER')
    def __neg__(self): return self.g.op('MULTIPLY', self, -1.0)
    def __lt__(self, o): return self.g.compare('LESS_THAN', self, o)
    def __gt__(self, o): return self.g.compare('GREATER_THAN', self, o)
    def __le__(self, o): return self.g.compare('LESS_EQUAL', self, o)
    def __ge__(self, o): return self.g.compare('GREATER_EQUAL', self, o)

    # vector parts
    @property
    def x(self): return self.g.sep(self)[0]
    @property
    def y(self): return self.g.sep(self)[1]
    @property
    def z(self): return self.g.sep(self)[2]


def _is_vec(v) -> bool:
    if isinstance(v, S):
        return v.type in _VEC
    return isinstance(v, (tuple, list)) and len(v) == 3


class Tree:
    """A geometry-node group being built. Nodes are laid out on a loose grid so the tree is inspectable in the UI."""

    def __init__(self, name: str):
        self.ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        self.n = 0
        self._gin = self.ng.nodes.new('NodeGroupInput')
        self._gout = self.ng.nodes.new('NodeGroupOutput')
        self._gin.location = (-400, 0)
        self._time = None
        self._sep_cache: dict = {}

    # plumbing -----------------------------------------------------------------------------------------------------
    def node(self, idname: str, *, inputs: dict | None = None, **props):
        nd = self.ng.nodes.new(idname)
        nd.location = ((self.n % 24) * 220, -(self.n // 24) * 320)
        self.n += 1
        for k, v in props.items():
            setattr(nd, k, v)
        for k, v in (inputs or {}).items():
            self.feed(self.inp(nd, k), v)
        return nd

    @staticmethod
    def inp(nd, key):
        """Input socket by index or by name (first ENABLED socket with that name, else first with that name)."""
        if isinstance(key, int):
            return nd.inputs[key]
        cands = [s for s in nd.inputs if s.name == key or s.identifier == key]
        if not cands:
            raise KeyError(f'{nd.bl_idname} has no input {key!r}: {[s.name for s in nd.inputs]}')
        en = [s for s in cands if getattr(s, 'enabled', True)]
        return (en or cands)[0]

    def out(self, nd, key=0) -> S:
        if isinstance(key, int):
            en = [s for s in nd.outputs if getattr(s, 'enabled', True)]
            return S(self, en[key])
        cands = [s for s in nd.outputs if s.name == key or s.identifier == key]
        if not cands:
            raise KeyError(f'{nd.bl_idname} has no output {key!r}: {[s.name for s in nd.outputs]}')
        en = [s for s in cands if getattr(s, 'enabled', True)]
        return S(self, (en or cands)[0])

    def feed(self, sock, v):
        """Link an S into sock, or set its default value from a number/tuple/bool/ID."""
        if v is None:
            return
        if isinstance(v, S):
            self.ng.links.new(v.s, sock)
            return
        if sock.type == 'VECTOR' and isinstance(v, (int, float)):
            v = (v, v, v)
        if sock.type == 'ROTATION' and isinstance(v, (tuple, list)):
            v = tuple(v)
        if sock.type == 'RGBA' and isinstance(v, (tuple, list)) and len(v) == 3:
            v = (*v, 1.0)
        sock.default_value = v

    # group interface ------------------------------------------------------------------------------------------------
    def input_geometry(self) -> S:
        self.ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        return S(self, self._gin.outputs['Geometry'])

    def param(self, name: str, kind: str = 'FLOAT', default=None, *, lo=None, hi=None) -> S:
        """A group input (shows up on the modifier; set or key it with set_input / key_input)."""
        st = {'FLOAT': 'NodeSocketFloat', 'INT': 'NodeSocketInt', 'VECTOR': 'NodeSocketVector',
              'BOOLEAN': 'NodeSocketBool', 'OBJECT': 'NodeSocketObject', 'COLLECTION': 'NodeSocketCollection',
              'MATERIAL': 'NodeSocketMaterial', 'GEOMETRY': 'NodeSocketGeometry', 'COLOR': 'NodeSocketColor',
              'ROTATION': 'NodeSocketRotation'}[kind]
        it = self.ng.interface.new_socket(name, in_out='INPUT', socket_type=st)
        if default is not None and hasattr(it, 'default_value'):
            it.default_value = default
        if lo is not None and hasattr(it, 'min_value'):
            it.min_value = lo
        if hi is not None and hasattr(it, 'max_value'):
            it.max_value = hi
        return S(self, self._gin.outputs[name])

    def output(self, geo: S, name: str = 'Geometry'):
        if name not in [i.name for i in self.ng.interface.items_tree if getattr(i, 'in_out', '') == 'OUTPUT']:
            self.ng.interface.new_socket(name, in_out='OUTPUT', socket_type='NodeSocketGeometry')
        self.ng.links.new(geo.s, self._gout.inputs[name])

    # values ---------------------------------------------------------------------------------------------------------
    def f(self, v: float) -> S:
        nd = self.node('ShaderNodeValue')
        nd.outputs[0].default_value = v
        return self.out(nd)

    def vec(self, x, y=None, z=None) -> S:
        if y is None and _is_vec(x) and not isinstance(x, S):
            x, y, z = x
        return self.out(self.node('ShaderNodeCombineXYZ', inputs={'X': x, 'Y': y if y is not None else 0,
                                                                     'Z': z if z is not None else 0}))

    def sep(self, v: S):
        key = id(v.s)
        if key not in self._sep_cache:
            nd = self.node('ShaderNodeSeparateXYZ', inputs={'Vector': v})
            self._sep_cache[key] = (self.out(nd, 'X'), self.out(nd, 'Y'), self.out(nd, 'Z'))
        return self._sep_cache[key]

    def time(self) -> S:
        """Song seconds (global frame / 24, with the render subframe)."""
        if self._time is None:
            self._time = self.out(self.node('GeometryNodeInputSceneTime'), 'Seconds')
        return self._time

    def index(self) -> S:
        return self.out(self.node('GeometryNodeInputIndex'))

    def position(self) -> S:
        return self.out(self.node('GeometryNodeInputPosition'))

    def rand(self, lo, hi, id_=None, seed: int = 0, kind: str = 'FLOAT') -> S:
        """Random Value (FLOAT or FLOAT_VECTOR or INT or BOOLEAN), deterministic by (ID, seed)."""
        nd = self.node('FunctionNodeRandomValue', data_type=kind)
        if kind == 'BOOLEAN':
            self.feed(self.inp(nd, 'Probability'), lo)
        else:
            self.feed(self.inp(nd, 'Min'), lo)
            self.feed(self.inp(nd, 'Max'), hi)
        if id_ is not None:
            self.feed(self.inp(nd, 'ID'), id_)
        self.feed(self.inp(nd, 'Seed'), seed)
        return self.out(nd, 0)

    # maths ----------------------------------------------------------------------------------------------------------
    def op(self, op: str, a, b=None, c=None) -> S:
        vec = _is_vec(a) or _is_vec(b)
        if vec:
            if op == 'MULTIPLY' and not (_is_vec(a) and _is_vec(b)):
                v, s = (a, b) if _is_vec(a) else (b, a)
                nd = self.node('ShaderNodeVectorMath', operation='SCALE')
                self.feed(nd.inputs[0], v)
                self.feed(nd.inputs['Scale'], s)
                return self.out(nd, 'Vector')
            if op == 'DIVIDE' and _is_vec(a) and not _is_vec(b):
                if isinstance(b, (int, float)):
                    return self.op('MULTIPLY', a, 1.0 / b)
                return self.op('MULTIPLY', a, self.op('DIVIDE', 1.0, b))
            if op == 'POWER':
                raise ValueError('vector power')
            nd = self.node('ShaderNodeVectorMath', operation=op)
            self.feed(nd.inputs[0], a if _is_vec(a) or a is None else (a, a, a))
            if b is not None:
                self.feed(nd.inputs[1], b if _is_vec(b) else (b, b, b) if isinstance(b, (int, float)) else b)
            if c is not None:
                self.feed(nd.inputs[2], c)
            return self.out(nd, 'Vector')
        nd = self.node('ShaderNodeMath', operation=op)
        self.feed(nd.inputs[0], a)
        if b is not None:
            self.feed(nd.inputs[1], b)
        if c is not None:
            self.feed(nd.inputs[2], c)
        return self.out(nd, 'Value')

    def vop(self, op: str, a, b=None, *, out='Vector') -> S:
        nd = self.node('ShaderNodeVectorMath', operation=op)
        self.feed(nd.inputs[0], a)
        if b is not None:
            self.feed(nd.inputs[1], b)
        return self.out(nd, out)

    def length(self, v): return self.vop('LENGTH', v, out='Value')
    def normalize(self, v): return self.vop('NORMALIZE', v)
    def dot(self, a, b): return self.vop('DOT_PRODUCT', a, b, out='Value')
    def cross(self, a, b): return self.vop('CROSS_PRODUCT', a, b)
    def sin(self, a): return self.op('SINE', a)
    def cos(self, a): return self.op('COSINE', a)
    def exp(self, a): return self.op('EXPONENT', a)
    def sqrt(self, a): return self.op('SQRT', a)
    def abs(self, a): return self.op('ABSOLUTE', a)
    def floor(self, a): return self.op('FLOOR', a)
    def fract(self, a): return self.op('FRACT', a)
    def min(self, a, b): return self.op('MINIMUM', a, b)
    def max(self, a, b): return self.op('MAXIMUM', a, b)
    def mod(self, a, b): return self.op('FLOORED_MODULO', a, b)

    def clamp(self, a, lo=0.0, hi=1.0) -> S:
        return self.min(self.max(a, lo), hi)

    def smooth(self, a, lo=0.0, hi=1.0) -> S:
        """Smoothstep of a from lo to hi (Map Range, SMOOTHSTEP)."""
        nd = self.node('ShaderNodeMapRange', interpolation_type='SMOOTHSTEP', clamp=True,
                       inputs={'Value': a, 'From Min': lo, 'From Max': hi, 'To Min': 0.0, 'To Max': 1.0})
        return self.out(nd, 'Result')

    def remap(self, a, lo, hi, to_lo=0.0, to_hi=1.0, clamp=True) -> S:
        nd = self.node('ShaderNodeMapRange', clamp=clamp,
                       inputs={'Value': a, 'From Min': lo, 'From Max': hi, 'To Min': to_lo, 'To Max': to_hi})
        return self.out(nd, 'Result')

    def mix(self, a, b, t) -> S:
        """a + (b - a) * t for floats or vectors."""
        return self.op('ADD', a, self.op('MULTIPLY', self.op('SUBTRACT', b, a), t))

    def compare(self, op, a, b) -> S:
        nd = self.node('FunctionNodeCompare', data_type='FLOAT', operation=op)
        self.feed(self.inp(nd, 'A'), a)
        self.feed(self.inp(nd, 'B'), b)
        return self.out(nd, 'Result')

    def bool_and(self, a, b) -> S:
        return self.out(self.node('FunctionNodeBooleanMath', operation='AND', inputs={0: a, 1: b}))

    def bool_or(self, a, b) -> S:
        return self.out(self.node('FunctionNodeBooleanMath', operation='OR', inputs={0: a, 1: b}))

    def bool_not(self, a) -> S:
        return self.out(self.node('FunctionNodeBooleanMath', operation='NOT', inputs={0: a}))

    def switch(self, cond, false, true, kind='FLOAT') -> S:
        nd = self.node('GeometryNodeSwitch', input_type=kind)
        self.feed(self.inp(nd, 'Switch'), cond)
        self.feed(self.inp(nd, 'False'), false)
        self.feed(self.inp(nd, 'True'), true)
        return self.out(nd, 0)

    def noise(self, vec, scale=1.0, detail=2.0, *, w=None, color=False) -> S:
        """Noise Texture; w given -> 4D noise (animate by time). color=True returns the Color output (0..1 vector)."""
        nd = self.node('ShaderNodeTexNoise', noise_dimensions='4D' if w is not None else '3D',
                       inputs={'Vector': vec, 'Scale': scale, 'Detail': detail})
        if w is not None:
            self.feed(self.inp(nd, 'W'), w)
        return self.out(nd, 'Color' if color else 'Factor')

    def euler(self, v) -> S:
        return self.out(self.node('FunctionNodeEulerToRotation', inputs={'Euler': v}))

    def axis_angle(self, axis, angle) -> S:
        return self.out(self.node('FunctionNodeAxisAngleToRotation', inputs={'Axis': axis, 'Angle': angle}))

    def align(self, vector, axis='Z', rotation=None, pivot='AUTO') -> S:
        nd = self.node('FunctionNodeAlignRotationToVector', axis=axis, pivot_axis=pivot,
                       inputs={'Vector': vector})
        if rotation is not None:
            self.feed(self.inp(nd, 'Rotation'), rotation)
        return self.out(nd)

    def rotate(self, rot, by, space='LOCAL') -> S:
        return self.out(self.node('FunctionNodeRotateRotation', rotation_space=space,
                                  inputs={'Rotation': rot, 'Rotate By': by}))

    # geometry -------------------------------------------------------------------------------------------------------
    def points(self, count, position=None, radius=0.05) -> S:
        return self.out(self.node('GeometryNodePoints', inputs={'Count': count, 'Position': position,
                                                                'Radius': radius}))

    def set_position(self, geo, position=None, offset=None, selection=None) -> S:
        return self.out(self.node('GeometryNodeSetPosition', inputs={'Geometry': geo, 'Position': position,
                                                                     'Offset': offset, 'Selection': selection}))

    def instance(self, points, instance, rotation=None, scale=None, selection=None, pick=False,
                 instance_index=None) -> S:
        nd = self.node('GeometryNodeInstanceOnPoints', inputs={'Points': points, 'Instance': instance,
                                                              'Rotation': rotation, 'Scale': scale,
                                                              'Selection': selection})
        if pick:
            self.feed(self.inp(nd, 'Pick Instance'), True)
            self.feed(self.inp(nd, 'Instance Index'), instance_index)
        return self.out(nd)

    def realize(self, geo) -> S:
        return self.out(self.node('GeometryNodeRealizeInstances', inputs={'Geometry': geo}))

    def delete(self, geo, selection, domain='POINT') -> S:
        return self.out(self.node('GeometryNodeDeleteGeometry', domain=domain,
                                  inputs={'Geometry': geo, 'Selection': selection}))

    def join(self, *geos) -> S:
        nd = self.node('GeometryNodeJoinGeometry')
        for gg in geos:
            self.ng.links.new(gg.s, nd.inputs[0])
        return self.out(nd)

    def object_geo(self, ob, as_instance=False, relative=True) -> S:
        nd = self.node('GeometryNodeObjectInfo', transform_space='RELATIVE' if relative else 'ORIGINAL',
                       inputs={'Object': ob, 'As Instance': as_instance})
        return self.out(nd, 'Geometry')

    def collection_geo(self, coll, separate=True, reset=True) -> S:
        nd = self.node('GeometryNodeCollectionInfo', transform_space='ORIGINAL',
                       inputs={'Collection': coll, 'Separate Children': separate, 'Reset Children': reset})
        return self.out(nd)

    def store(self, geo, name: str, value, kind='FLOAT', domain='POINT') -> S:
        nd = self.node('GeometryNodeStoreNamedAttribute', data_type=kind, domain=domain,
                       inputs={'Geometry': geo, 'Name': name})
        self.feed(self.inp(nd, 'Value'), value)
        return self.out(nd)

    def set_material(self, geo, material) -> S:
        return self.out(self.node('GeometryNodeSetMaterial', inputs={'Geometry': geo, 'Material': material}))

    def radius(self, pts, r) -> S:
        return self.out(self.node('GeometryNodeSetPointRadius', inputs={'Points': pts, 'Radius': r}))

    def sample_curve(self, curve, factor=None, length=None, mode='FACTOR'):
        """Sample Curve: returns (position, tangent, normal)."""
        nd = self.node('GeometryNodeSampleCurve', mode=mode, use_all_curves=True,
                       inputs={'Curves': curve})
        if mode == 'FACTOR':
            self.feed(self.inp(nd, 'Factor'), factor)
        else:
            self.feed(self.inp(nd, 'Length'), length)
        return self.out(nd, 'Position'), self.out(nd, 'Tangent'), self.out(nd, 'Normal')


def modifier(obj, tree: Tree | bpy.types.NodeTree, name: str = 'fx', **inputs):
    """Add a geometry-nodes modifier running tree on obj, setting inputs by interface NAME."""
    ng = tree.ng if isinstance(tree, Tree) else tree
    mod = obj.modifiers.new(name, 'NODES')
    mod.node_group = ng
    for k, v in inputs.items():
        set_input(mod, k, v)
    return mod


def input_id(mod, name: str) -> str:
    for it in mod.node_group.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def set_input(mod, name: str, value) -> str:
    """Set a geometry-nodes modifier input by interface NAME. Blender 5.2 moved inputs off the modifier's ID
    properties: they live at mod.properties.inputs.<Socket_N>.value. Returns the data path (for keyframes)."""
    ident = input_id(mod, name)
    sock = getattr(mod.properties.inputs, ident)
    if isinstance(value, (tuple, list)):
        cur = sock.value
        for i, x in enumerate(value):
            cur[i] = x
    else:
        sock.value = value
    return f'modifiers["{mod.name}"].properties.inputs.{ident}.value'


def key_input(obj, mod, name: str, t: float, value, interp: str | None = None):
    """Keyframe a geometry-nodes modifier input at song time t."""
    from .. import kit
    path = set_input(mod, name, value)
    kit.key(obj, path, t, None, interp=interp)
