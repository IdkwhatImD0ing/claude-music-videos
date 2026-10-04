"""The researcher's desk at night: the shared set most scenes happen on. See docs/lib/sets.md.

    from pdoom import kit
    from pdoom.sets import build_desk

    sc = kit.new_scene('boot')
    d = build_desk(kit.collection('desk'), mood='night')
    cam, tgt = d.camera('hero_low')          # a camera on a named mark
    d.lamp.click(2.056)                      # the lamp clicks on
    d.gauge.value_at(30.0)                   # 25.0 (the canonical DOOM history is keyed by default)
    d.anchors['clawdSpot']                   # where Clawd stands (world, cm)

Scale: 1 BU = 1 cm; the desktop surface is z = 0; +y goes away from the default camera towards the wall and window.
"""
from __future__ import annotations

import math

import bpy
from mathutils import Vector

from .. import kit
from ..timing import FPS
from . import geo
from . import materials as M
from . import props as P
from . import room as R
from .gauge import CRACK_T, DOOMS, build_gauge
from .lamp import build_lamp

ALL_PARTS = frozenset({'room', 'window', 'city', 'lamp', 'laptop', 'mug', 'books', 'pencils', 'notes', 'pen',
                       'drawers', 'killswitch', 'clip', 'cable', 'gauge', 'motes', 'haze'})

# fixed layout (world cm). Characters' spots face -y (towards the default camera) unless FACING says otherwise.
LAYOUT = {
    'clawdSpot': (8.0, -4.0, 0.0),
    'researcherSpot': (-6.0, -12.0, 0.0),
    'laptop': (-17.0, 15.0, 0.0),
    'lampBase': (50.0, 27.0, 0.0),
    'lampPool': (6.0, -4.0, 0.0),
    'gauge': (25.0, 13.0, 0.0),
    'mug': (29.0, -13.0, 0.0),
    'books': (-45.0, -17.0, 0.0),
    'pencilCup': (-40.0, 31.0, 0.0),
    'notes': (-22.0, -17.0, 0.0),
    'pen': (-16.0, -27.0, 0.0),
    'drawers': (-63.0, 18.0, 0.0),
    'killswitch': (59.0, -15.0, 0.0),
    'clip': (-3.0, -4.0, 0.0),
}


class Desk:
    """Handles to everything build_desk made. Attributes are None for parts that were not built."""

    def __init__(self):
        self.lamp = self.laptop = self.mug = self.books = self.pencilcup = self.notes = self.pen = None
        self.drawer = self.killswitch = self.clip = self.gauge = self.cable = None
        self.pencils = []
        self.room: R.Room | None = None
        self.window = None
        self.anchors: dict[str, Vector] = {}
        self.facing: dict[str, float] = {}
        self.marks: dict[str, dict] = {}
        self.colls: dict[str, bpy.types.Collection] = {}
        self.mood = None
        self.world = None

    # -------------------------------------------------------------------------------------------- cameras
    def camera(self, mark: str, name: str | None = None, *, coll=None):
        """A camera (+ target Empty with DOF focus) on a named mark; becomes the scene camera. Returns (cam, tgt).

        The mark's f-stop is a real-lens f-number; the camera gets phys_fstop() of it (EEVEE ignores the unit scale)."""
        mk = self.marks[mark]
        cam, tgt = kit.camera(name or f'cam.{mark}', lens=mk['lens'], loc=tuple(mk['loc']), target=tuple(mk['target']),
                              fstop=mk['fstop'], coll=coll or self.colls.get('cams'))
        cam.data.dof.aperture_fstop = phys_fstop(mk['fstop'])
        cam.data.dof.aperture_blades = 7
        cam.data.dof.aperture_rotation = math.radians(12)
        return cam, tgt

    def move(self, cam, tgt, mark: str, t: float, *, interp: str = 'BEZIER', lens: bool = True):
        """Key cam + target (and lens, f-stop) onto a mark at song time t (for dollies between marks)."""
        mk = self.marks[mark]
        kit.key(cam, 'location', t, tuple(mk['loc']), interp=interp)
        kit.key(tgt, 'location', t, tuple(mk['target']), interp=interp)
        if lens:
            geo.keyp(cam.data, 'lens', t, mk['lens'], interp=interp)
            geo.keyp(cam.data.dof, 'aperture_fstop', t, phys_fstop(mk['fstop']), interp=interp)
        return cam

    def mark(self, name: str, loc, target, lens: float = 50.0, fstop: float = 2.8):
        """Add or override a mark."""
        self.marks[name] = {'loc': Vector(loc), 'target': Vector(target), 'lens': lens, 'fstop': fstop}
        return self.marks[name]

    # -------------------------------------------------------------------------------------------- lighting
    def lighting(self, mood: str = 'night'):
        lighting(self, mood)
        return self

    def props(self) -> dict:
        return {k: v for k, v in (('lamp', self.lamp), ('laptop', self.laptop), ('mug', self.mug), ('books', self.books),
                                  ('pencilcup', self.pencilcup), ('notes', self.notes), ('pen', self.pen),
                                  ('drawer', self.drawer), ('killswitch', self.killswitch), ('clip', self.clip),
                                  ('gauge', self.gauge), ('cable', self.cable)) if v is not None}


def phys_fstop(f_number: float) -> float:
    """The aperture_fstop value that gives a real f-number's depth of field in this cm-scale world.

    EEVEE (5.2) computes the aperture from the focal length in metres and ignores unit_settings.scale_length, so at
    1 BU = 1 cm an f/2.8 setting blurs ~100x less than a real f/2.8 lens. Multiplying by the scale restores physical
    depth of field (measured: far points at f/2, 50 mm, focus 30 cm blur 114 px at 960 wide; theory ~120 px)."""
    return f_number * bpy.context.scene.unit_settings.scale_length


# ------------------------------------------------------------------------------------------------ build


def _eevee_for_desk(sc):
    ee = sc.eevee
    # macro bokeh: allow big out-of-focus discs (default clamps at 100 px)
    ee.bokeh_max_size = 320.0
    ee.bokeh_threshold = 1.0
    ee.bokeh_neighbor_max = 20.0
    # volumes only near the camera (cm scale): the default range is set for metres and wastes the froxel grid
    ee.use_volume_custom_range = True
    ee.volumetric_start = 1.0
    ee.volumetric_end = 450.0
    ee.volumetric_light_clamp = 0.0
    ee.fast_gi_distance = 60.0
    ee.fast_gi_thickness_near = 1.0
    ee.clamp_surface_indirect = 10.0


def build_desk(coll=None, mood: str = 'night', *, parts=None, exclude=(), gauge_history: bool = True,
               clawd_spot=None, researcher_spot=None) -> Desk:
    """Build the desk world into coll (sub-collections desk.room / desk.city / desk.props / desk.lights /
    desk.atmos / desk.cams). parts: the subset of ALL_PARTS to build (default all), exclude: parts to skip."""
    sc = bpy.context.scene
    coll = coll or kit.collection('desk')
    want = set(parts or ALL_PARTS) - set(exclude)
    d = Desk()
    for k in ('room', 'city', 'props', 'lights', 'atmos', 'cams'):
        d.colls[k] = kit.collection(f'desk.{k}', coll)
    cr, cp, cl, ca = d.colls['room'], d.colls['props'], d.colls['lights'], d.colls['atmos']
    lay = dict(LAYOUT)
    if clawd_spot is not None:
        lay['clawdSpot'] = tuple(clawd_spot)
    if researcher_spot is not None:
        lay['researcherSpot'] = tuple(researcher_spot)
    _eevee_for_desk(sc)
    room = R.Room()
    d.room = room
    if 'room' in want:
        R.build_desk_body(cr, room)
        R.build_wall(cr, room)
    if 'window' in want:
        R.build_window(cr, room)
        R.build_moonlight(cl, room)
    if 'room' in want:
        R.build_bounce(cl, room)
        d.window = room
    if 'city' in want:
        R.build_city(d.colls['city'], room)
    if 'lamp' in want:
        d.lamp = build_lamp(cp, base=lay['lampBase'], aim=lay['lampPool'])
    if 'laptop' in want:
        d.laptop = P.build_laptop(cp, lay['laptop'], yaw_deg=4.0)
    if 'mug' in want:
        d.mug = P.build_mug(cp, lay['mug'])
    if 'books' in want:
        d.books = P.build_books(cp, lay['books'])
    if 'pencils' in want:
        d.pencilcup = P.build_pencil_cup(cp, lay['pencilCup'])
        d.pencils = d.pencilcup.pencils
    if 'notes' in want:
        d.notes = P.build_notes(cp, lay['notes'])
        n1 = P.add_note(cp, d.notes.root, 'notes.loose1', '#F2A0B8', (9.5, 3.0, 0.02), (0, 0, math.radians(-24)), 0.4)
        n2 = P.add_note(cp, d.notes.root, 'notes.loose2', '#F2D54B', (2.0, 9.4, 0.02), (0, 0, math.radians(17)), 0.3)
        d.notes.loose = [n1, n2]
        if d.laptop is not None:
            n3 = P.add_note(cp, d.laptop.hinge, 'notes.onlaptop', '#A6E3C8', (-11.4, -0.56, 16.2),
                            (math.radians(90), math.radians(8), 0), 0.25)
            d.notes.loose.append(n3)
    if 'pen' in want:
        d.pen = P.build_pen(cp, lay['pen'])
    if 'drawers' in want:
        d.drawer = P.build_drawer_unit(cp, lay['drawers'])
    if 'killswitch' in want:
        d.killswitch = P.build_killswitch(cp, lay['killswitch'])
    if 'clip' in want:
        d.clip = P.build_paperclip(cp, 'clip', lay['clip'], yaw_deg=24.0)
    if 'gauge' in want:
        d.gauge = build_gauge(cp, lay['gauge'], yaw_deg=-16.0)
        if gauge_history:
            d.gauge.history()
    if 'motes' in want:
        cone = None
        if d.lamp is not None:
            bpy.context.view_layer.update()
            mw = d.lamp.light.matrix_world
            cone = (mw.translation.copy(), (mw.to_3x3() @ Vector((0, 0, -1))).normalized(), 24.0, 38.0)
        R.build_motes(ca, room, cone=cone)
    if 'haze' in want:
        R.build_haze(ca, room)
    bpy.context.view_layer.update()
    _anchors(d, lay)
    if 'cable' in want and d.laptop is not None:
        port = d.laptop.root.matrix_world @ Vector((15.3, 1.5, 0.75))
        d.cable = P.build_cable(cp, port, d.anchors['clawdPort'])
        d.anchors['cablePort'] = port
    _marks(d)
    lighting(d, mood)
    return d


def _anchors(d: Desk, lay):
    A = d.anchors
    V = Vector
    A['center'] = V((0, 0, 0))
    A['clawdSpot'] = V(lay['clawdSpot'])
    A['clawdPort'] = A['clawdSpot'] + V((-2.6, 2.3, 2.2))
    A['researcherSpot'] = V(lay['researcherSpot'])
    dv = (A['clawdSpot'] - A['researcherSpot'])
    d.facing['clawdSpot'] = 0.0
    d.facing['researcherSpot'] = math.atan2(dv.x, -dv.y)   # yaw so that local -y faces Clawd
    A['lampPool'] = V(lay['lampPool'])
    A['clipSpot'] = V(lay['clip'])
    A['deskFront'] = V((0, -40, 0))
    A['deskFrontLeft'] = V((-80, -40, 0))
    A['deskFrontRight'] = V((80, -40, 0))
    A['deskBackLeft'] = V((-80, 40, 0))
    A['deskBackRight'] = V((80, 40, 0))
    A['openCenter'] = V((6, -24, 0))       # clear desk for scene toys
    A['openLeft'] = V((-24, -30, 0))
    A['openRight'] = V((28, -28, 0))
    A['windowCenter'] = V((0, R.GLASS_Y, (R.WIN[2] + R.WIN[3]) / 2))
    A['windowSill'] = V((0, R.WALL_Y - 1.5, R.WIN[2] + 0.4))
    if d.laptop is not None:
        mw = d.laptop.root.matrix_world
        A['laptopFront'] = mw @ V((0, -13.5, 0))
        A['laptopKeys'] = mw @ V((0, 3.9, 1.62))
        A['laptopScreen'] = d.laptop.screen_point(0.5, 0.5)
        A['laptopTop'] = d.laptop.screen_point(0.5, 1.12)
    if d.lamp is not None:
        A['lampBase'] = V(d.lamp.base_loc)
        A['lampHead'] = d.lamp.head_point()
    if d.mug is not None:
        mw = d.mug.root.matrix_world
        A['mugTop'] = mw @ d.mug.top
        A['mugFront'] = mw.translation + V((0, -8, 0))
    if d.gauge is not None:
        A['gaugeCenter'] = d.gauge.center()
        A['gaugeFace'] = d.gauge.front(0.9)
        A['gaugeFront'] = d.gauge.root.matrix_world @ V((0, -9, 0))
    if d.drawer is not None:
        mw = d.drawer.root.matrix_world
        W, D, H = d.drawer.size
        A['drawerFront'] = mw @ V((0, -D / 2 - 8, -mw.translation.z))
        dr = d.drawer.drawers[0]
        A['drawerFace'] = mw @ V((0, -D / 2 - 0.3, dr.location.z + 3.0))
        A['drawerInside'] = d.drawer.inside(0, 1.0)
        A['drawerTop'] = mw @ V((0, 0, H))
    if d.killswitch is not None:
        mw = d.killswitch.root.matrix_world
        A['killswitchTop'] = mw @ d.killswitch.top
        A['killswitchSide'] = mw @ V((-10, -3, 0))
    if d.books is not None:
        A['booksTop'] = d.books.root.matrix_world @ d.books.top
    if d.pencilcup is not None:
        A['pencilCup'] = d.pencilcup.root.matrix_world @ d.pencilcup.top
    if d.notes is not None:
        A['notesPad'] = d.notes.root.matrix_world @ V((0, 0, 0.93))
    if d.pen is not None:
        A['penSpot'] = d.pen.root.matrix_world.translation.copy()


def _marks(d: Desk):
    A = d.anchors
    V = Vector
    C, Rs = A['clawdSpot'], A['researcherSpot']
    d.mark('wide', (6, -150, 58), (4, 6, 8), 35, 8.0)
    d.mark('establish', (-34, -84, 13), (8, 6, 8), 40, 5.6)
    d.mark('hero_low', C + V((-7, -30, 2.6)), C + V((0, 0, 3.4)), 65, 8.0)
    dv = (C - Rs)
    dv.z = 0
    dv.normalize()
    perp = V((-dv.y, dv.x, 0))
    d.mark('over_researcher', Rs - dv * 22 - perp * 12 + V((0, 0, 11.5)), C + V((0, 0, 3)), 55, 8.0)
    d.mark('over_clawd', C + dv * 13 + perp * 4 + V((0, 0, 7)), Rs + V((0, 0, 9)), 50, 8.0)
    d.mark('two_shot', (C + Rs) / 2 + V((4, -38, 7)), (C + Rs) / 2 + V((0, 0, 5)), 50, 8.0)
    if 'gaugeCenter' in A:
        gc = A['gaugeCenter']
        d.mark('gauge', d.gauge.front(48) + V((0, 0, -2.5)), gc, 70, 11.0)
        d.mark('gauge_wide', C + V((-12, -34, 6)), (C * 0.35 + gc * 0.65) + V((0, 0, 3)), 45, 11.0)
    if 'clipSpot' in A:
        cl = A['clipSpot']
        d.mark('macro', cl + V((5.5, -8.5, 3.0)), cl + V((-0.3, 0, 0.1)), 100, 16.0)
    if 'laptopScreen' in A:
        d.mark('laptop', A['laptopFront'] + V((-6, -24, 12)), A['laptopScreen'] + V((0, 0, -3)), 45, 8.0)
    if 'lampHead' in A:
        d.mark('lamp', C + V((-4, -26, 3)), A['lampHead'], 32, 5.6)
    if 'drawerFace' in A:
        d.mark('drawer', A['drawerFace'] + V((12, -36, 9)), A['drawerFace'], 50, 8.0)
    if 'killswitchTop' in A:
        d.mark('killswitch', A['killswitchTop'] + V((-12, -26, 5)), A['killswitchTop'] + V((0, 0, -3)), 60, 8.0)
    if 'mugTop' in A:
        d.mark('mug', A['mugTop'] + V((-8, -26, 2)), A['mugTop'] + V((0, 0, 1)), 60, 8.0)
    if 'booksTop' in A:
        d.mark('books', A['booksTop'] + V((20, -30, 4)), A['booksTop'] + V((0, 0, -4)), 50, 8.0)
    if 'pencilCup' in A:
        d.mark('pencils', A['pencilCup'] + V((12, -34, 4)), A['pencilCup'] + V((0, 0, 2.5)), 50, 8.0)
    if 'notesPad' in A:
        d.mark('notes', A['notesPad'] + V((10, -20, 9)), A['notesPad'] + V((1, 1, 0)), 50, 8.0)
    if d.cable is not None:
        mid = d.cable.at(0.5)
        d.mark('cable', mid + V((-22, -3, 5)), mid + V((2, -3, 0.5)), 50, 8.0)
    d.mark('window', (8, 4, 12), (0, 38, 17), 50, 2.8)
    d.mark('top', (0, -1, 230), (0, 0, 0), 32, 11.0)


# ------------------------------------------------------------------------------------------------ lighting presets

MOODS = ('night', 'lamp_off', 'dawn')


def _world(d: Desk, strength: float, bg: str, bg_strength: float):
    """HDRI world for reflections only (camera rays see a plain colour, e.g. through the room's gaps)."""
    p = kit.asset('hdri', 'office_night.hdr')
    import os
    if os.path.exists(p):
        kit.world_hdri(p, strength, 120.0, background=(bg, bg_strength))
    else:
        kit.world_color(bg, bg_strength)
    w = bpy.context.scene.world
    try:
        w.sun_threshold = 0.0
    except Exception:
        pass
    d.world = w


def lighting(d: Desk, mood: str = 'night'):
    """Set a lighting preset (static values; scenes key changes on top, e.g. d.lamp.click(t)).

    night:    warm lamp key, cool laptop fill, blue window rim, city bokeh, haze + motes in the lamp cone.
    lamp_off: the lamp dark; the laptop and the window light the desk (cold, lonely).
    dawn:     lamp off, the window a pale peach-to-blue dawn, the city's lights fading, a soft cool key.
    """
    if mood not in MOODS:
        raise ValueError(f'mood must be one of {MOODS}')
    d.mood = mood
    room = d.room
    lamp_level = {'night': 1.0, 'lamp_off': 0.0, 'dawn': 0.0}[mood]
    if d.lamp is not None:
        d.lamp.full_power = 260000.0
        d.lamp.bulb_full = 45.0
        d.lamp.inner_full = 1.4
        d.lamp.set_level(lamp_level)
    if d.laptop is not None:
        d.laptop.fill_power = {'night': 4500.0, 'lamp_off': 7000.0, 'dawn': 2500.0}[mood]
        d.laptop.screen(glow={'night': 1.0, 'lamp_off': 1.25, 'dawn': 0.7}[mood])
    if room is not None and room.moon is not None:
        ld = room.moon.data
        ld.energy = {'night': 90000.0, 'lamp_off': 120000.0, 'dawn': 420000.0}[mood]
        ld.color = kit.srgb({'night': '#6F8FD0', 'lamp_off': '#7C9BE0', 'dawn': '#FFD2B0'}[mood])[:3]
    if room is not None and room.bounce is not None:
        room.bounce.data.energy = {'night': 130000.0, 'lamp_off': 26000.0, 'dawn': 60000.0}[mood]
        room.bounce.data.color = kit.srgb({'night': '#C9C6D8', 'lamp_off': '#9FB4D8', 'dawn': '#FFE6D0'}[mood])[:3]
    if room is not None and room.city_sockets:
        k = {'night': 1.0, 'lamp_off': 1.0, 'dawn': 0.12}[mood]
        for s, b in zip(room.city_sockets, room.city_base):
            s.default_value = b * k
    if room is not None and room.sky_nodes is not None:
        cr = room.sky_nodes
        if mood == 'dawn':
            cols = ['#E8906A', '#8FA6CC', '#4A6AA8']
            room.sky_strength.default_value = 1.1
        else:
            cols = ['#3B2A3A', '#1B2438', '#04070F']
            room.sky_strength.default_value = 1.0
        els = sorted(cr.elements, key=lambda e: e.position)
        for e, c in zip(els, cols):
            e.color = kit.srgb(c)
    if room is not None and room.haze_density is not None:
        room.haze_density.default_value = {'night': 0.0006, 'lamp_off': 0.0004, 'dawn': 0.0005}[mood]
    wstr = {'night': 0.04, 'lamp_off': 0.03, 'dawn': 0.25}[mood]
    _world(d, wstr, {'night': '#05070C', 'lamp_off': '#04060A', 'dawn': '#8AA0C0'}[mood], 1.0 if mood == 'dawn' else 0.4)
    return d
