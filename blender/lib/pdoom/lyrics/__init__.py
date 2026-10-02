"""In-picture lyrics for the Blender video: every sung word as a physical, lit, animated thing in the miniature.

    from pdoom import lyrics as ly

    ly.line(0, words='AGI', style='glow', place=ly.At((6, -20, 0), size=1.4))       # stage one idea
    ly.line(3, words='training loss', style='screen', place=ly.laptop(d))
    ly.skip(8)                                                                        # a line shown some other way
    ly.default('eat')                  # LAST: every other word of the scene on the automatic lyric stand
    ly.finish()                        # (also runs on save)

Docs: docs/lib/lyrics.md. Words reveal on their sung times from data/lyrics.json (letters of spelled words on their
syllables); rows exit before the next line. Everything is keyed by song time, on twos by default.
"""
from __future__ import annotations

import math
import os

import bpy
from mathutils import Euler, Matrix, Vector

from .. import timeline
from ..timing import FPS
from ..sets.geo import hash01
from . import core as C
from . import data as D
from . import mats, styles  # noqa: F401  (mats: re-exported for scenes)
from . import text as glyphs
from . import place as P
from . import supports as SUP
from .place import At, Auto, Lens, On, StageSpec, laptop, on_object  # noqa: F401
from .styles import STYLES  # noqa: F401

FRAME = 1.0 / FPS
_ST: dict = {}
# Revision 3 (2026-10-01): the user dropped the in-picture lyrics ("it was a bad idea") for burned-in subtitles, as in
# revision 1. Scenes stage their lyrics only when this is on: PDOOM_LYRICS=1 builds revision 2's in-picture lyrics again.
ENABLED = os.environ.get('PDOOM_LYRICS', '0') == '1'


def _state() -> dict:
    sc = bpy.context.scene
    sid = sc.get('ly_session')
    if sid is None or _ST.get('session') != sid:
        sid = f'{sc.name}.{len(bpy.data.objects)}.{id(sc)}'
        sc['ly_session'] = sid
        _ST.clear()
        _ST.update(session=sid, claimed=set(), stages={}, lyrics=[], n=0, dirty=False, accents={})
        _install_handler()
    return _ST


def collection() -> bpy.types.Collection:
    name = 'lyrics'
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


# ------------------------------------------------------------------------------------------------ handles


class Copy:
    """One on-screen instance of a lyric (one per shot for automatic and lens placements)."""

    def __init__(self, root, seat, pieces, supports):
        self.root, self.seat, self.pieces, self.supports = root, seat, pieces, supports

    @property
    def objects(self):
        out = [self.root] + [p.obj for p in self.pieces] + list(self.supports)
        for p in self.pieces:
            out += [x for x in p.extra if isinstance(x, bpy.types.Object)]
        return out


class Lyric:
    """What line() returns: the words, the style and the copies with their pieces (for extra keys or parenting)."""

    def __init__(self, i, words, style, place, name):
        self.line, self.words, self.style, self.place, self.name = i, words, style, place, name
        self.copies: list[Copy] = []
        self.t_show = self.t_exit = self.t_end = 0.0
        self.accents: dict = {}       # word index -> (Style, opts): words in another style inside this row

    @property
    def pieces(self):
        return [p for c in self.copies for p in c.pieces]

    @property
    def objects(self):
        return [o for c in self.copies for o in c.objects]

    def __repr__(self):
        txt = ' '.join(w.text for w in self.words)
        return f'Lyric({self.line}: {txt!r}, {self.style.name}, {len(self.copies)} copies)'


# ------------------------------------------------------------------------------------------------ timing


def exit_time(line_i: int, words: list, *, hold=0.6, gap=6 * FRAME, window=None) -> float:
    """When a line's row leaves by default: `gap` before the next line starts (so it is off the stand when the next
    line's first word lands), but not before its last word has had 0.3 s and not later than `hold` after its last
    word ends. The line's own last word counts even when another staging shows it (a row that shows part of a
    line stays up until the line is over)."""
    lines = D.lines()
    lw = lines[line_i]['words'][-1]
    last = words[-1]
    if lw['start'] > last.start:
        last = D.Word(line_i, len(lines[line_i]['words']) - 1, lw['w'], lw['w'], lw['start'], lw['end'])
    nxt = lines[line_i + 1]['words'][0]['start'] if line_i + 1 < len(lines) else 1e9
    t = min(nxt - gap, last.end + hold)
    t = max(t, last.start + 0.3)
    if window is not None:
        t = min(t, window[1])
    return t


# ------------------------------------------------------------------------------------------------ the stage (auto)


class Stage:
    """The automatic lyric stand of one shot: a seat found by place.auto_seat, a root and (when it floats or holds
    two rows) a little wooden stand. Lines placed with place='auto' in this shot sit on it."""

    def __init__(self, cam, t0, t1, spec: StageSpec, coll):
        self.cam, self.t0, self.t1, self.spec = cam, t0, t1, spec
        self.seat = P.auto_seat(cam, t0, t1, spec)
        k = len(_state()['stages'])
        self.root = bpy.data.objects.new(f'ly.stage{k:02d}.{cam.name}', None)
        coll.objects.link(self.root)
        self.root.empty_display_size = 1.0
        self.root.matrix_world = self.seat.matrix @ Matrix.Scale(self.seat.size, 4)
        self.row_gap = spec.row_gap
        self.rows = spec.rows
        self.objs = []
        self.shows: list[tuple[float, float]] = []
        self.flat = self.seat.flat
        needs = self.seat.mode in ('stand', 'float') or (spec.rows > 1 and not self.flat)
        if needs and spec.support != 'none':
            zs = [(self.row_z(r), spec.cells) for r in range(spec.rows)]
            self.objs = SUP.stand(f'ly.stage{k:02d}.stand', coll, self.root, zs, legs=self.seat.legs,
                                  lowest_plank=self.seat.mode != 'desk')
        if spec.light > 0:
            self.objs.append(self._light(k, coll))

    def _light(self, k, coll):
        """A soft warm spot from above the camera side onto the rows (a photographer's fill on the title): the
        desk lamp gives ~180 W/cm^2 at its pool (260 kW at 38 cm); this gives `light` of that on the letters."""
        import math as _m
        spec = self.spec
        h = 1.0 + (spec.rows - 1) * spec.row_gap
        loc = Vector((0.0, -4.5, h + 3.0))
        aim = Vector((0.0, -0.5, h * 0.5))
        dist_cm = (loc - aim).length * self.seat.size
        ld = bpy.data.lights.new(f'ly.stage{k:02d}.light', 'SPOT')
        ld.energy = spec.light * 180.0 * dist_cm ** 2
        ld.color = (1.0, 0.86, 0.68)
        half = 0.5 * spec.cells + 1.0
        ld.spot_size = min(2.6, 2.0 * _m.atan(half / (loc - aim).length) * 1.15)
        ld.spot_blend = 0.6
        ld.shadow_soft_size = 1.2 * self.seat.size
        try:
            ld.use_shadow = True
        except Exception:
            pass
        lo = bpy.data.objects.new(ld.name, ld)
        coll.objects.link(lo)
        lo.parent = self.root
        lo.location = loc
        lo.rotation_euler = (aim - loc).to_track_quat('-Z', 'Y').to_euler()
        return lo

    def row_z(self, r: int, n: int | None = None) -> float:
        """Shelf height of row r of an n-row line (single rows sit on the lowest shelf)."""
        n = self.rows if n is None else n
        off = self.rows - n
        return (self.rows - 1 - (r + off)) * self.row_gap

    def finish(self, keys: C.Keys):
        if not self.shows or not self.objs:
            return
        a = max(self.t0, min(s for s, _ in self.shows) - 0.35)
        b = min(self.t1, max(e for _, e in self.shows) + 0.25)
        for o in self.objs:
            keys.add(o, 'hide_render', -1, self.t0 * FPS - 2, True)
            keys.add(o, 'hide_viewport', -1, self.t0 * FPS - 2, True)
            for f, v in ((a * FPS - C.HALF, False), (b * FPS - C.HALF, True)):
                keys.add(o, 'hide_render', -1, f, v)
                keys.add(o, 'hide_viewport', -1, f, v)
            o.hide_render = o.hide_viewport = True


def _stage_for(t, spec, coll) -> Stage:
    """The lyric stand of the shot that shows time t (built on first use)."""
    st = _state()
    a, b, cam = P.shot_at(t)
    key = (cam.name, C.frame_of(a))
    stg = st['stages'].get(key)
    if stg is None:
        stg = Stage(cam, a, b, spec, coll)
        st['stages'][key] = stg
    return stg


# ------------------------------------------------------------------------------------------------ building a line


def _resolve_place(place, style, t):
    if place is None or place == 'auto':
        return Auto()
    if isinstance(place, P.Place):
        if isinstance(place, At) and place.flat is None:
            place.flat = style.flat
        return place
    if isinstance(place, (tuple, list, Vector)):
        return At(place, flat=style.flat, size=style.size)
    if place == 'lens':
        return Lens()
    raise TypeError(f'bad place {place!r}')


def line(q, *, words=None, style='blocks', place='auto', reveal=None, exit=None, preview='style', t_show=None,
         t_exit=None, t_end=None, hold=0.6, lead=0.35, size=None, max_chars=22, rows=2, align='center',
         support='style', reveal_opts=None, exit_opts=None, strings=False, name=None, window=None, spec=None,
         **style_opts) -> Lyric:
    """Stage (some words of) a lyric line.

    q: line index or a text fragment. words: None (all), 'text' (a run of words), (a, b) slice, index or list.
    style: a name from STYLES ('blocks', 'glow', 'tiles', 'brass', 'cardboard', 'stencil', 'stamp', 'typed',
    'screen', 'marker', 'chalk', 'wire', 'neon', 'tape', 'fog', 'goldleaf') or a styles.Style; extra keywords go to
    the style (color=, ink=, glow_color=, radius=, font=, case=...).
    place: 'auto' (the per-shot lyric stand), 'lens', At(...), On(...), Lens(...), laptop(desk), or a (x, y, z).
    reveal / exit: names from core.REVEALS / core.EXITS (default: the style's). preview: None | 'blank' | 'dim'
    (the unsung state shown from t_show; default: the style's). t_show: when the row (or its preview) appears
    (default: the first reveal - lead for previews). t_exit: when it starts to leave (default: exit_time()).
    t_end: when it is gone for good (default t_exit + 0.75; world-placed rows are seen by every camera until then,
    so end them on a cut if the next shot shouldn't see them).
    size: cm per unit (explicit placements). max_chars / rows: wrap long lines into up to `rows` rows.
    """
    st = _state()
    coll = collection()
    i = D.find_line(q)
    sel = D.select(i, words)
    fresh = [j for j in sel if (i, j) not in st['claimed']]
    if len(fresh) < len(sel):
        print(f'[run] lyrics: line {i}: words {sorted(set(sel) - set(fresh))} already staged, skipped', flush=True)
    sel = fresh
    sty = styles.get(style, **style_opts)
    if not sel:
        return Lyric(i, [], sty, place, name or f'L{i:02d}')
    for j in sel:
        st['claimed'].add((i, j))
    ws = [D.word(i, j, case=style_opts.get('case', sty.case), punct=style_opts.get('punct', sty.punct))
          for j in sel]
    ws = [w for w in ws if w.letters]
    if not ws:
        return Lyric(i, [], sty, place, name or f'L{i:02d}')
    st['n'] += 1
    nm = name or f'L{i:02d}.{st["n"]:02d}'
    ly = Lyric(i, ws, sty, place, nm)
    for (li, j), (aname, aopts) in st['accents'].items():
        if li == i and j in sel:
            so = {k: v for k, v in aopts.items()
                  if k not in ('reveal', 'exit', 'preview', 'reveal_opts', 'exit_opts')}
            ly.accents[j] = (styles.get(aname, **so), aopts)
    reveal = reveal or sty.reveal
    exit = exit or sty.exit
    preview = sty.preview if preview == 'style' else preview
    support = sty.support if support == 'style' else support
    t_first = min(L.t for w in ws for L in w.letters)
    sc = bpy.context.scene
    win = window or (sc.frame_start / FPS, (sc.frame_end + 1) / FPS)
    if t_show is None:
        t_show = t_first - (lead if preview else 0.0)
    t_show = max(t_show, win[0])
    if t_exit is None:
        t_exit = exit_time(i, ws, hold=hold, window=win)
    t_end = min(t_exit + 0.75 if t_end is None else t_end, win[1])
    ly.t_show, ly.t_exit, ly.t_end = t_show, t_exit, t_end
    rows_ = D.split_rows(ws, max_chars, rows)
    pl = _resolve_place(place, sty, t_show)
    keys = C.Keys()
    if isinstance(pl, Auto):
        sp = spec or StageSpec(**pl.spec)
        for a, b, cam in P.shots(t_show, t_end):
            if b - a < 1.5 * FRAME or a > t_exit - 0.05:
                continue                                  # a flicker before a cut, or a shot that starts as it leaves
            stg = _stage_for(0.5 * (a + b), sp, coll)
            stg.shows.append((max(a, t_show), min(b, t_end)))
            seat = P.Seat(a, b, Matrix.Identity(4), 1.0, parent=stg.root, mode=stg.seat.mode, flat=stg.seat.flat)
            _build_copy(ly, seat, rows_, t_show, t_exit, t_end, keys, coll, reveal, exit, preview, support='none',
                        align=align, reveal_opts=reveal_opts, exit_opts=exit_opts, stage=stg, strings=strings)
    else:
        spec2 = StageSpec(cells=max(_row_width(r, sty) for r in rows_), rows=len(rows_))
        for seat in pl.seats(t_show, t_end, spec2):
            if size is not None:
                seat.size = size
            _build_copy(ly, seat, rows_, t_show, t_exit, t_end, keys, coll, reveal, exit, preview, support=support,
                        align=align, reveal_opts=reveal_opts, exit_opts=exit_opts, stage=None, strings=strings)
    keys.flush()
    st['lyrics'].append(ly)
    st['dirty'] = True
    return ly


def _row_width(row_words, sty) -> float:
    w = 0.0
    for k, wd in enumerate(row_words):
        if k:
            w += sty.space
            if wd.line == row_words[k - 1].line and wd.index - row_words[k - 1].index > 1:
                w += 2.0 * sty.space
        for L in wd.letters:
            w += sty.cell(L.ch) + sty.gap
    return w


def _layout(rows_, sty, align, acc=None):
    """[(row, word, letter, x_center, cell)] per row, centred (or aligned) on x = 0."""
    out = []
    acc = acc or {}
    for r, row in enumerate(rows_):
        items = []
        x = 0.0
        for k, wd in enumerate(row):
            ws = acc.get(wd.index, (sty,))[0]
            if k:
                x += sty.space
                if wd.line == row[k - 1].line and wd.index - row[k - 1].index > 1:
                    x += 2.0 * sty.space          # words staged elsewhere leave a gap
            for L in wd.letters:
                c = ws.cell(L.ch)
                items.append((r, wd, L, x + c / 2, c))
                x += c + ws.gap
        W = max(0.0, x - sty.gap)
        off = -W / 2 if align == 'center' else (0.0 if align == 'left' else -W)
        out.append([(r, wd, L, xc + off, c) for (r, wd, L, xc, c) in items])
    return out


def _build_copy(ly, seat, rows_, t_show, t_exit, t_end, keys, coll, reveal, exit, preview, *, support, align,
                reveal_opts, exit_opts, stage, strings):
    sty = ly.style
    k = len(ly.copies)
    root = bpy.data.objects.new(f'ly.{ly.name}.c{k}', None)
    coll.objects.link(root)
    root.empty_display_size = 0.5
    if seat.parent is not None:
        root.parent = seat.parent
        root.matrix_parent_inverse = Matrix.Identity(4)
    flat = seat.flat
    if stage is not None:
        root.matrix_basis = Matrix.Identity(4)
    else:
        ps = 1.0
        if seat.parent is not None and seat.parent.type != 'CAMERA':
            sc3 = _world_matrix(seat.parent).to_scale()      # (matrix_world is stale right after keying)
            ps = max((abs(sc3.x) + abs(sc3.y) + abs(sc3.z)) / 3.0, 1e-6)
        root.matrix_basis = seat.matrix @ Matrix.Scale(seat.size / ps, 4)
    vis = (max(seat.t0, t_show), min(seat.t1, t_end))
    acc = ly.accents
    lay = _layout(rows_, sty, align, acc)
    n = len(rows_)
    row_gap = sty.height + sty.descent + sty.leading
    sup_thick = {'paper': 0.03, 'strip': 0.02, 'panel': 0.012, 'notes': 0.016, 'slate': 0.0, 'pane': 0.0,
                 'glass': 0.0, 'backing': 0.0, 'tape': 0.042}.get(support or '', 0.0)
    pad = SUPPORT_PAD.get(support or '', 0.0)
    base_z = pad + sty.descent            # the lowest baseline: descenders and the support's margin stay above 0
    pieces = []
    idx = 0
    for r, items in enumerate(lay):
        z = stage.row_z(r, n) if stage is not None else base_z + (n - 1 - r) * row_gap
        for kk, (rr, wd, L, xc, c) in enumerate(items):
            nmp = f'ly.{ly.name}.c{k}.{wd.index}.{L.k}'
            wsty, wopts = acc.get(wd.index, (sty, {}))
            o, info = wsty.piece(L.ch, nmp, coll, wd)
            if o is None:
                continue
            o.parent = root
            pc = C.Piece(o, L.ch, wd, L, xc, info.get('w', c), info.get('h', 1.0), info.get('d', 1.0), row=r,
                         curve=info.get('curve'), extra=list(info.get('extra', [])))
            pc.rest = Vector((xc, -sup_thick, z))
            jit = info.get('jitter', {'blocks': 2.2, 'glow': 2.2, 'tiles': 1.2}.get(wsty.name, 0.0))
            if jit:
                a = math.radians(jit) * (2 * hash01(ly.name, wd.index, L.k, 'yaw') - 1)
                pc.rest_rot = Euler((0.0, 0.0, a)) if not flat else Euler((0.0, a, 0.0))
                pc.rest.x += 0.03 * (2 * hash01(ly.name, wd.index, L.k, 'x') - 1)
            pc.k_index = kk
            pc.n_row = len(items)
            pc.n_all = sum(len(it) for it in lay)
            idx += 1
            if strings:
                th = SUP.thread(nmp + '.thread', coll, o, info.get('h', 1.0))
                pc.extra.append(th)
            light = info.get('light')
            if light:
                lo = next((x for x in pc.extra if isinstance(x, bpy.types.Object) and x.type == 'LIGHT'), None)
                if lo is not None:
                    lo['ly_on'] = 0.0
                    pc.light = (lo, light)
            eo = dict(exit_opts or {})
            if exit == 'drop' and stage is not None and 'floor' not in eo:
                eo['floor'] = z + 0.2           # fall to the surface the stand stands on, not through it
            if wsty is sty:
                _animate(pc, sty, reveal, exit, preview, t_show, t_exit, flat, reveal_opts or {}, eo, root, idx)
            else:
                _animate(pc, wsty, wopts.get('reveal', wsty.reveal), wopts.get('exit', exit),
                         wopts.get('preview', wsty.preview), t_show, t_exit, flat, wopts.get('reveal_opts', {}),
                         wopts.get('exit_opts', exit_opts or {}), root, idx)
            pieces.append(pc)
    if (not support or support == 'none') and stage is None and n > 1 and not flat and sty.stack and not strings:
        support = 'shelves'               # standing rows need something to stand on: a little shelf unit
    sups = _supports(ly, support, lay, rows_, root, coll, k, pieces, t_show, vis, keys, row_gap, n, base_z, pad)
    if reveal == 'stamp':
        _stamp_tools(ly, pieces, root, coll, k, vis, keys, sup_thick)
    C.write(pieces, keys, t_start=vis[0], t_end=vis[1], vis=vis)
    for pc in pieces:
        if getattr(pc, 'light', None):
            lo, watts = pc.light
            for t, pose, mode in sorted(pc.ev, key=lambda e: e[0]):
                if 'on' in pose:
                    f = t * FPS
                    fk, ip = (round(f) - C.HALF, 'CONSTANT') if mode in ('twos', 'ones') else (f, 'LINEAR')
                    keys.add(lo.data, 'energy', -1, fk, watts * pose['on'] * seat.size ** 2, ip)
    for o in sups:
        if o.get('ly_own_vis'):
            continue
        keys.add(o, 'hide_render', -1, vis[0] * FPS - 2, True)
        keys.add(o, 'hide_viewport', -1, vis[0] * FPS - 2, True)
        for f, v in (((max(vis[0], t_show - 0.2)) * FPS - C.HALF, False), (vis[1] * FPS - C.HALF, True)):
            keys.add(o, 'hide_render', -1, f, v)
            keys.add(o, 'hide_viewport', -1, f, v)
        o.hide_render = o.hide_viewport = True
    ly.copies.append(Copy(root, seat, pieces, sups))


def _animate(pc, sty, reveal, exit, preview, t_show, t_exit, flat, ropts, eopts, root, idx):
    L = pc.letter
    t = L.t
    if reveal == 'stamp':
        t = pc.word.start
    rfun = C.REVEALS[reveal]
    if preview == 'blank':
        C.reveal_blank(pc, t_show + round((idx - 1) * min(1.0, 12.0 / max(getattr(pc, 'n_all', 12), 1))) * FRAME,
                       flat=flat, axis=ropts.get('axis', 'Z'))
        C.reveal_flip(pc, t, flat=flat, axis=ropts.get('axis', 'Z'))
    elif preview == 'dim':
        if reveal == 'light':
            rfun(pc, t, preview=True, **{k: v for k, v in ropts.items() if k != 'preview'})
        else:
            rfun(pc, t, **ropts)
            pc.ev = [e for e in pc.ev if not (e[1].get('hide') and e[0] <= t + 1e-6)]
        pc.at(t_show, 'twos', on=0.0, wipe=1.0, hide=False, loc=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0),
              scl=(1.0, 1.0, 1.0))
    else:
        kw = dict(ropts)
        if reveal in ('pop', 'flip', 'slam', 'tumble'):
            kw.setdefault('flat', flat)
        if reveal == 'light':
            kw.setdefault('preview', False)
        rfun(pc, t, **kw)
    if exit and exit != 'none':
        ek = dict(eopts)
        tgt = ek.get('target')
        if tgt is not None and callable(tgt) and ek.pop('world', True):
            def conv(tt, f=tgt, root=root):
                Mi = _world_matrix(root).inverted()
                return Mi @ Vector(f(tt))
            ek['target'] = conv
        te = ek.pop('t', None)
        C.EXITS[exit](pc, te(pc) if callable(te) else (te if te is not None else t_exit), flat=flat, **ek)


def _world_matrix(o):
    M = o.matrix_basis.copy()
    p = o.parent
    while p is not None:
        M = p.matrix_basis @ M
        p = p.parent
    return M


SUPPORT_PAD = {'paper': 0.55, 'strip': 0.3, 'panel': 0.6, 'slate': 0.75, 'pane': 0.65, 'glass': 0.5,
               'backing': 0.65, 'notes': 0.4, 'tape': 0.35}


def _supports(ly, support, lay, rows_, root, coll, k, pieces, t_show, vis, keys, row_gap, n, base_z, pad):
    if not support or support == 'none':
        return []
    out = []
    sty = ly.style
    base = f'ly.{ly.name}.c{k}.{support}'
    xs = [(p.x - p.w / 2, p.x + p.w / 2) for p in pieces] or [(-1, 1)]
    x0 = min(a for a, _ in xs)
    x1 = max(b for _, b in xs)
    zt = base_z + (n - 1) * row_gap + sty.height + pad      # top edge; the bottom edge is z = 0
    if support == 'paper':
        out += SUP.card(base, coll, root, x0 - 0.6, x1 + 0.6, 0.0, zt)
    elif support == 'strip':
        for r in range(n):
            z = base_z + (n - 1 - r) * row_gap
            rx = [(p.x - p.w / 2, p.x + p.w / 2) for p in pieces if p.row == r]
            if rx:
                out += SUP.card(f'{base}{r}', coll, root, min(a for a, _ in rx) - 0.5, max(b for _, b in rx) + 0.5,
                                z - sty.descent - pad, z + sty.height + pad, thick=0.02)
    elif support == 'panel':
        out += SUP.panel(base, coll, root, x0 - 0.8, x1 + 0.8, 0.0, zt)
    elif support == 'slate':
        out += SUP.slate(base, coll, root, x0 - 0.8, x1 + 0.8, 0.28, zt)
    elif support == 'pane':
        out += SUP.pane(base, coll, root, x0 - 0.7, x1 + 0.7, 0.18, zt, frosted=True)
    elif support == 'glass':
        out += SUP.pane(base, coll, root, x0 - 0.6, x1 + 0.6, 0.0, zt, frosted=False, frame=False, thick=0.04)
    elif support == 'backing':
        out += SUP.backing(base, coll, root, x0 - 0.7, x1 + 0.7, 0.0, zt)
    elif support == 'shelves':
        rws = []
        for r in range(n):
            rx = [(p.x - p.w / 2, p.x + p.w / 2) for p in pieces if p.row == r]
            if rx:
                rws.append((base_z + (n - 1 - r) * row_gap, 2 * max(abs(min(a for a, _ in rx)),
                                                                     abs(max(b for _, b in rx)))))
        out += SUP.stand(base, coll, root, rws, depth=sty.depth, lowest_plank=False)
    elif support in ('notes', 'tape'):
        byw = {}
        for p in pieces:
            byw.setdefault((p.word.line, p.word.index, p.row), []).append(p)
        for (li, wi, r), ps in byw.items():
            z = base_z + (n - 1 - r) * row_gap
            a = min(p.x - p.w / 2 for p in ps)
            b = max(p.x + p.w / 2 for p in ps)
            wd = ps[0].word
            if support == 'notes':
                m = 0.35
                w_ = max(b - a + 2 * m, 1.9)
                c = (a + b) / 2
                zb, ztop = z - ly.style.descent - pad, z + ly.style.height + pad
                objs = SUP.note(f'{base}.{wi}', coll, root, c - w_ / 2, c + w_ / 2, zb, ztop,
                                color=ly.style.opts.get('note', '#F6E27A'))
                # slaps on just before the word: tilted up off the surface, then flat, on twos
                o = objs[0]
                o['ly_own_vis'] = 1
                t0 = wd.start - 4 * FRAME
                keys.add(o, 'hide_render', -1, vis[0] * FPS - 2, True)
                keys.add(o, 'hide_viewport', -1, vis[0] * FPS - 2, True)
                F0 = C.frame_of(max(t0, vis[0]))
                keys.add(o, 'hide_render', -1, F0 - C.HALF, False)
                keys.add(o, 'hide_viewport', -1, F0 - C.HALF, False)
                keys.add(o, 'hide_render', -1, vis[1] * FPS - C.HALF, True)
                keys.add(o, 'hide_viewport', -1, vis[1] * FPS - C.HALF, True)
                o.hide_render = o.hide_viewport = True
                if t0 >= vis[0]:
                    for kk, ang in enumerate((-0.9, -0.35, 0.05, 0.0)):
                        keys.add(o, 'rotation_euler', 0, F0 + 2 * kk - C.HALF, ang)
                    o.data.transform(Matrix.Translation((0, 0, -ztop)))
                    o.location = (0, 0, ztop)
                out += objs
            else:
                m = 0.35
                objs = SUP.tape(f'{base}.{wi}', coll, root, 0.0, b - a + 2 * m, z - 0.35, z + 1.35,
                                color=ly.style.opts.get('color', '#1F1F24'))
                o = objs[0]
                o.location.x = a - m
                full = b - a + 2 * m
                for p in sorted(ps, key=lambda p: p.letter.t):
                    f = C.frame_of(p.letter.t) - C.HALF
                    keys.add(o, 'scale', 0, f, (p.x + p.w / 2 + m - (a - m)) / full)
                keys.add(o, 'scale', 0, C.frame_of(ps[0].letter.t) - 1 - C.HALF, 0.05)
                out += objs
    return out


def _stamp_tools(ly, pieces, root, coll, k, vis, keys, surface):
    """A rubber stamp per word: hovers in, slams down ON the word's time (the ink appears), lifts away, on twos."""
    byw = {}
    for p in pieces:
        byw.setdefault((p.word.index, p.row), []).append(p)
    for (wi, r), ps in byw.items():
        a = min(p.x - p.w / 2 for p in ps)
        b = max(p.x + p.w / 2 for p in ps)
        z = ps[0].rest.z
        wd = ps[0].word
        tr = bpy.data.objects.new(f'ly.{ly.name}.c{k}.stamp.{wi}', None)
        coll.objects.link(tr)
        tr.parent = root
        tr.empty_display_size = 0.3
        objs = SUP.stamp_tool(tr.name + '.tool', coll, tr, (b - a) + 0.45, 1.5)
        for o in objs:
            o.location.z -= 0.25
        F = C.frame_of(wd.start)
        rz = math.radians(3.0) * (2 * hash01(ly.name, wi, 'rz') - 1)
        seq = [(-8, -3.2, 0.12), (-6, -2.2, 0.08), (-4, -1.1, 0.04), (-2, -0.35, 0.01), (0, 0.0, 0.0),
               (2, -0.12, 0.0), (4, -0.9, -0.03), (6, -2.4, -0.06), (8, -4.0, -0.1)]
        for df, y, tilt in seq:
            f = F + df - C.HALF
            for i, v in enumerate(((a + b) / 2, -surface + y, z)):
                keys.add(tr, 'location', i, f, v)
            for i, v in enumerate((tilt, 0.0, rz)):
                keys.add(tr, 'rotation_euler', i, f, v)
        on, off = max(vis[0], (F - 8) / FPS), min(vis[1], (F + 10) / FPS)
        for o in objs:
            keys.add(o, 'hide_render', -1, vis[0] * FPS - 2, True)
            keys.add(o, 'hide_viewport', -1, vis[0] * FPS - 2, True)
            if off > on:
                for f, v in ((on * FPS - C.HALF, False), (off * FPS - C.HALF, True)):
                    keys.add(o, 'hide_render', -1, f, v)
                    keys.add(o, 'hide_viewport', -1, f, v)
            o.hide_render = o.hide_viewport = True


# ------------------------------------------------------------------------------------------------ default + skip


def accent(q, words, style, **opts):
    """Give some words of a line another style INSIDE whatever row shows them (e.g. A-G-I as light-up blocks in the
    default row). opts: style options, plus reveal=, preview=, exit=, reveal_opts=, exit_opts= for those words.
    Call before line() / default()."""
    st = _state()
    i = D.find_line(q)
    for j in D.select(i, words):
        st['accents'][(i, j)] = (style, dict(opts))


def skip(q, words=None):
    """Mark words as staged elsewhere (default() leaves them alone)."""
    st = _state()
    i = D.find_line(q)
    for j in D.select(i, words):
        st['claimed'].add((i, j))


def default(scene_id: str | None = None, *, window=None, style='blocks', place='auto', max_chars=22, rows=2,
            spec: StageSpec | None = None, **kw) -> list[Lyric]:
    """Every word of the scene's window that no line() / skip() has claimed, line by line, as painted wooden letter
    blocks popping up on twos on the automatic lyric stand (one per shot: lower third, on the focus plane, on the
    desk or on its legs). Call it LAST in build(), after the cameras and cuts exist (and after chars.finish() so
    the stand can see the puppets' real poses)."""
    st = _state()
    sc = bpy.context.scene
    if window is None:
        window = timeline.window(scene_id) if scene_id and not scene_id.startswith('_') else \
            (sc.frame_start / FPS, (sc.frame_end + 1) / FPS)
    sel = D.scene_words(scene_id, window)
    plan = []
    for i, js in sorted(sel.items()):
        js = [j for j in js if (i, j) not in st['claimed']]
        if not js:
            continue
        sty = styles.get(style, **{k: v for k, v in kw.items() if k in ('color', 'font', 'case')})
        ws = [D.word(i, j, case=sty.case, punct=sty.punct) for j in js]
        plan.append((i, js, ws, sty))
    # size every shot's stand for the widest line it will hold
    if place == 'auto':
        need: dict = {}
        for i, js, ws, sty in plan:
            rws = D.split_rows(ws, max_chars, rows)
            t_first = min(L.t for w in ws for L in w.letters)
            t_ex = exit_time(i, ws, window=window)
            for a, b, cam in P.shots(max(t_first, window[0]), min(t_ex + 0.75, window[1])):
                if b - a < 1.5 * FRAME or a > t_ex - 0.05:
                    continue
                a, b, cam = P.shot_at(0.5 * (a + b))
                key = (cam.name, C.frame_of(a))
                cells = max(_row_width(r, sty) for r in rws)
                c0, r0 = need.get(key, (0.0, 1))
                need[key] = (max(c0, cells), max(r0, len(rws)))
        base = spec or StageSpec()
        for (cn, fa), (cells, nr) in need.items():
            if (cn, fa) in st['stages']:
                continue
            a, b, cam = P.shot_at(fa / FPS + 0.5 * FRAME)
            sp = StageSpec(**{**base.__dict__, 'cells': max(cells, 8.0), 'rows': nr})
            st['stages'][(cn, fa)] = Stage(cam, a, b, sp, collection())
    out = []
    for i, js, ws, sty in plan:
        out.append(line(i, words=js, style=style, place=place, max_chars=max_chars, rows=rows, window=window, **kw))
    finish()
    return out


def finish():
    """Write the stands' visibility (call at the end of build(); also runs on save)."""
    st = _state()
    keys = C.Keys()
    for stg in st['stages'].values():
        if not getattr(stg, '_done', False):
            stg.finish(keys)
            stg._done = True
    keys.flush()
    glyphs.drop_work_scene()
    st['dirty'] = False


def _on_save(*_):
    try:
        if _ST.get('dirty'):
            finish()
    except Exception as e:  # noqa: BLE001
        print(f'[run] lyrics: finish on save failed: {e}', flush=True)


def _install_handler():
    hs = bpy.app.handlers.save_pre
    if not any(getattr(h, '__name__', '') == '_ly_on_save' for h in hs):
        def _ly_on_save(*a):
            _on_save(*a)
        hs.append(_ly_on_save)


# ------------------------------------------------------------------------------------------------ helpers for scenes


def lines_in(scene_id: str, window=None) -> dict:
    """{line index: [word indices]} that default(scene_id) would show (see data.scene_words), with the text:
    for i, js in ly.lines_in('eat').items(): print(i, ly.text(i))."""
    return D.scene_words(scene_id, window)


def text(q) -> str:
    return D.lines()[D.find_line(q)]['text']


def mouth(char, name='mouth'):
    """A target for exit='eaten': the world point of a character's socket over time (Clawd's jaw)."""
    return lambda t: char.anchor(t, name)


def rack(cam, t0: float, t1: float, dist: float, *, dur=0.3):
    """Rack a camera's focus to `dist` cm in front of the lens over [t0, t0 + dur], hold, and back by t1 (for lens
    panes). A camera that focuses on an object gets a new focus Empty riding the camera, blended between the old
    focus object and the near point by a keyed Copy Location influence; one that uses a focus distance gets that
    distance keyed."""
    cd = cam.data
    old = cd.dof.focus_object
    name = f'ly.focus.{cam.name}'
    fo = bpy.data.objects.get(name)
    if old is None and fo is None:
        d0 = cd.dof.focus_distance
        for t, v in ((t0, d0), (t0 + dur, dist), (t1 - dur, dist), (t1, d0)):
            cd.dof.focus_distance = v
            cd.dof.keyframe_insert('focus_distance', frame=t * FPS)
        cd.dof.focus_distance = d0
        return None
    if fo is None:
        fo = bpy.data.objects.new(name, None)
        collection().objects.link(fo)
        fo.parent = cam
        c = fo.constraints.new('COPY_LOCATION')
        c.target = old
        c.influence = 1.0
        cd.dof.focus_object = fo
    c = fo.constraints.get('Copy Location')
    fo.location = (0, 0, -dist)
    for t, v in ((t0, 1.0), (t0 + dur, 0.0), (t1 - dur, 0.0), (t1, 1.0)):
        c.influence = v
        c.keyframe_insert('influence', frame=t * FPS)
    c.influence = 1.0
    return fo


__all__ = ['line', 'default', 'skip', 'accent', 'finish', 'At', 'On', 'Lens', 'Auto', 'laptop', 'on_object',
           'StageSpec', 'STYLES', 'mouth', 'rack', 'collection', 'Lyric', 'lines_in', 'text']
