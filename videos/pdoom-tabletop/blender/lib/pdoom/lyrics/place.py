"""Where lyric rows go: the scene's camera cuts, camera projection and depth of field, the automatic per-shot
"lyric stand" in the lower third, and explicit placements (a spot on the desk, a surface, the lens).

A placement answers one question for a row: for each span of time it is on screen, which world frame (origin, the
direction the letters face, the letters' up), how big (cm per unit) and, for camera-attached rows, which camera to
ride. Rows are built in units where a letter/block is ~1 tall (see text.py); the row root carries the size as scale.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field

import bpy
from mathutils import Matrix, Vector

from ..timing import FPS

WIDTH_PX = 1920
DEBUG = bool(os.environ.get('LYRICS_DEBUG'))


# ------------------------------------------------------------------------------------------------ frames


def frame_matrix(origin, front, up) -> Matrix:
    """World matrix of a row: local -Y = front (the way the letters face), +Z = the letters' up, +X = reading."""
    f = Vector(front).normalized()
    u = Vector(up)
    u = (u - f * u.dot(f)).normalized()
    r = u.cross(f).normalized()
    M = Matrix.Identity(4)
    M.col[0][:3] = r
    M.col[1][:3] = -f
    M.col[2][:3] = u
    M.col[3][:3] = Vector(origin)
    return M


@dataclass
class Seat:
    """One span of a row's life: [t0, t1) in song seconds, its world matrix (no scale), cm per unit, and optionally
    the object it rides (parent: the matrix is then local to it)."""
    t0: float
    t1: float
    matrix: Matrix
    size: float
    parent: object = None
    mode: str = 'free'          # 'desk' | 'stand' | 'float' | 'free' | 'lens' | 'surface'
    legs: float = 0.0           # stand legs down to the support (units)
    flat: bool = False
    cam: object = None
    info: dict = field(default_factory=dict)


# ------------------------------------------------------------------------------------------------ cameras


def cuts(sc=None) -> list[tuple[int, object]]:
    """[(first frame, camera)] of the scene's shots, from the timeline markers bound to cameras."""
    sc = sc or bpy.context.scene
    mk = sorted(((m.frame, m.camera) for m in sc.timeline_markers if m.camera is not None), key=lambda x: x[0])
    if not mk or mk[0][0] > sc.frame_start:
        mk = [(sc.frame_start, sc.camera)] + mk
    # drop markers superseded at the same frame (the last one wins, like Blender)
    out = []
    for f, c in mk:
        if out and out[-1][0] == f:
            out[-1] = (f, c)
        else:
            out.append((f, c))
    return out


def shots(t0: float, t1: float, sc=None) -> list[tuple[float, float, object]]:
    """The shots overlapping [t0, t1): [(start, end, camera)] clipped to it and to the scene's frame range."""
    sc = sc or bpy.context.scene
    ct = cuts(sc)
    s_end = (sc.frame_end + 1) / FPS
    out = []
    for k, (f, cam) in enumerate(ct):
        a = f / FPS
        b = ct[k + 1][0] / FPS if k + 1 < len(ct) else s_end
        a2, b2 = max(a, t0, sc.frame_start / FPS), min(b, t1, s_end)
        if b2 > a2 + 1e-6 and cam is not None:
            out.append((a2, b2, cam))
    return out


def shot_at(t: float, sc=None) -> tuple[float, float, object]:
    """The whole shot (start, end, camera) that shows song time t (clipped to the scene's frame range only)."""
    sc = sc or bpy.context.scene
    ct = cuts(sc)
    s_end = (sc.frame_end + 1) / FPS
    f = t * FPS
    for k, (fr, cam) in enumerate(ct):
        nxt = ct[k + 1][0] if k + 1 < len(ct) else sc.frame_end + 1
        if fr <= f + 1e-6 < nxt:
            return max(fr, sc.frame_start) / FPS, min(nxt / FPS, s_end), cam
    return sc.frame_start / FPS, s_end, sc.camera


def camera_at(t: float, sc=None):
    sc = sc or bpy.context.scene
    f = t * FPS
    cam = sc.camera
    for fr, c in cuts(sc):
        if fr <= f + 1e-6:
            cam = c
    return cam


@dataclass
class CamState:
    t: float
    matrix: Matrix
    lens: float
    sw: float
    sh: float
    shift: tuple
    focus: float | None      # focus distance along the view axis (cm), None without DOF
    fnum: float | None       # physical f-number
    aim: float | None        # distance to a Track To / Damped Track target (cm)
    clip: tuple

    @property
    def loc(self) -> Vector:
        return self.matrix.translation

    @property
    def fwd(self) -> Vector:
        return (self.matrix.to_3x3() @ Vector((0, 0, -1))).normalized()

    @property
    def upv(self) -> Vector:
        return (self.matrix.to_3x3() @ Vector((0, 1, 0))).normalized()

    @property
    def right(self) -> Vector:
        return (self.matrix.to_3x3() @ Vector((1, 0, 0))).normalized()

    @property
    def pitch(self) -> float:
        return math.degrees(math.asin(max(-1.0, min(1.0, self.fwd.z))))

    @property
    def subject(self) -> float:
        return self.focus or self.aim or 30.0

    def frame_h(self, depth: float) -> float:
        return depth * self.sh / self.lens

    def frame_w(self, depth: float) -> float:
        return depth * self.sw / self.lens

    def project(self, p) -> tuple[float, float, float]:
        """World point -> (u, v, depth): u, v in 0..1 over the frame (v up), depth along the view axis (cm)."""
        q = self.matrix.inverted() @ Vector(p)
        d = -q.z
        if d <= 1e-6:
            return (float('nan'), float('nan'), d)
        x = q.x / d * self.lens / self.sw
        y = q.y / d * self.lens / self.sh
        return (0.5 + x - self.shift[0], 0.5 + y - self.shift[1] * self.sw / self.sh, d)

    def unproject(self, u: float, v: float, depth: float) -> Vector:
        x = (u - 0.5 + self.shift[0]) * self.sw / self.lens * depth
        y = (v - 0.5 + self.shift[1] * self.sw / self.sh) * self.sh / self.lens * depth
        return self.matrix @ Vector((x, y, -depth))

    def ray(self, u: float, v: float) -> Vector:
        return (self.unproject(u, v, 1.0) - self.loc).normalized()

    def blur_px(self, depth: float) -> float:
        """Circle of confusion (px across 1920) of a point at depth (cm): EEVEE matches the thin-lens formula once the
        f-stop is physical (sets.phys_fstop)."""
        if not self.focus or not self.fnum:
            return 0.0
        f = self.lens
        s = self.focus * 10.0
        d = max(depth * 10.0, 1e-3)
        if s <= f:
            return 0.0
        K = f * f / (self.fnum * (s - f))
        return K * abs(d - s) / d / self.sw * WIDTH_PX

    def depth_for_blur(self, px: float, near: bool = True) -> float:
        """The depth (cm) in front of (near) or behind the focus plane whose blur is px."""
        if not self.focus or not self.fnum:
            return self.subject * (0.85 if near else 1.15)
        f = self.lens
        s = self.focus * 10.0
        K = f * f / (self.fnum * max(s - f, 1e-3))
        c = px / WIDTH_PX * self.sw
        r = c / K
        if near:
            return s / (1.0 + r) / 10.0
        return (s / (1.0 - r) / 10.0) if r < 0.95 else 1e5


def cam_state(cam, t: float, sc=None) -> CamState:
    """Evaluate a camera at song time t (frame_set to the frame that shows t; restores the frame)."""
    sc = sc or bpy.context.scene
    keep = (sc.frame_current, sc.frame_subframe)
    f = t * FPS
    fi = int(math.floor(f + 1e-6))
    sc.frame_set(fi, subframe=f - fi)
    dg = bpy.context.evaluated_depsgraph_get()
    ce = cam.evaluated_get(dg)
    M = ce.matrix_world.copy()
    cd = ce.data
    fwd = (M.to_3x3() @ Vector((0, 0, -1))).normalized()
    focus = fnum = None
    if cd.dof.use_dof:
        if cd.dof.focus_object is not None:
            fo = cd.dof.focus_object.evaluated_get(dg)
            focus = (fo.matrix_world.translation - M.translation).dot(fwd)
        else:
            focus = cd.dof.focus_distance          # scene units (cm)
        fnum = cd.dof.aperture_fstop / max(sc.unit_settings.scale_length, 1e-9)
        if focus is not None and focus <= 0.5:
            focus = None
    aim = None
    for c in cam.constraints:
        tg = getattr(c, 'target', None)
        if c.type in ('TRACK_TO', 'DAMPED_TRACK', 'LOCKED_TRACK') and tg is not None and c.influence > 0.5:
            aim = (tg.evaluated_get(dg).matrix_world.translation - M.translation).dot(fwd)
            break
    sw = cd.sensor_width
    ar = sc.render.resolution_x * sc.render.pixel_aspect_x / (sc.render.resolution_y * sc.render.pixel_aspect_y)
    if cd.sensor_fit == 'VERTICAL':
        sh = cd.sensor_height
        sw = sh * ar
    else:
        sh = sw / ar
    st = CamState(t, M, cd.lens, sw, sh, (cd.shift_x, cd.shift_y), focus, fnum, aim, (cd.clip_start, cd.clip_end))
    sc.frame_set(keep[0], subframe=keep[1])
    return st


# ------------------------------------------------------------------------------------------------ ray casts


_VOLUME_ONLY: dict[str, bool] = {}


def _volume_only(o) -> bool:
    """Objects to see through when probing the set: haze boxes and other volume-only materials, lyric pieces."""
    if o.name.startswith('ly.stage') or o.name.startswith('ly.tmp') or o.name.startswith('ly.focus'):
        return True
    k = o.name
    if k in _VOLUME_ONLY:
        return _VOLUME_ONLY[k]
    res = False
    n = o.name.lower()
    if 'haze' in n or 'motes' in n or 'volume' in n:
        res = True
    else:
        mats = [s.material for s in getattr(o, 'material_slots', []) if s.material is not None]
        if mats:
            vol = 0
            for m in mats:
                out = m.node_tree.nodes.get('Material Output') if m.node_tree else None
                if out is not None and out.inputs['Volume'].is_linked and not out.inputs['Surface'].is_linked:
                    vol += 1
            res = vol == len(mats)
    _VOLUME_ONLY[k] = res
    return res


def raycast(origin, direction, dist=1e4, ignore=()):
    """First solid hit along a ray: (distance, point, normal, object) or None. Skips haze, lyric pieces and
    `ignore`. Uses the depsgraph at the current frame."""
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    o = Vector(origin)
    d = Vector(direction).normalized()
    travelled = 0.0
    for _ in range(12):
        hit, loc, nor, idx, ob, mat = sc.ray_cast(dg, o, d, distance=dist - travelled)
        if not hit:
            return None
        step = (loc - o).length
        travelled += step
        orig = ob.original if ob is not None else None
        if orig is not None and (_volume_only(orig) or orig in ignore or orig.name in ignore):
            o = loc + d * 0.02
            travelled += 0.02
            continue
        return (travelled, loc, nor, orig)
    return None


class no_haze:
    """Context manager: hide volume-only objects (the desk haze box and friends) while probing the set with rays:
    their faces are coplanar with the desk top, so skipping them would skip the desk too."""
    def __enter__(self):
        self.hidden = []
        for o in bpy.context.scene.objects:
            if o.type == 'MESH' and not o.name.startswith('ly.') and _volume_only(o) and not o.hide_viewport:
                o.hide_viewport = True
                self.hidden.append(o)
        return self

    def __exit__(self, *a):
        for o in self.hidden:
            o.hide_viewport = False


def with_frame(t: float):
    """Context manager: evaluate the scene at song time t (restores the frame afterwards)."""
    class _F:
        def __enter__(self):
            sc = bpy.context.scene
            self.keep = (sc.frame_current, sc.frame_subframe)
            f = t * FPS
            fi = int(math.floor(f + 1e-6))
            sc.frame_set(fi, subframe=f - fi)
            return self

        def __exit__(self, *a):
            bpy.context.scene.frame_set(self.keep[0], subframe=self.keep[1])
    return _F()


# ------------------------------------------------------------------------------------------------ faces to keep clear


def faces(t: float) -> list[tuple[Vector, float]]:
    """World points (and radii, cm) of the characters' faces at t, from the chars library if it's in use."""
    out = []
    try:
        from ..chars import REGISTRY
    except Exception:
        return out
    for p in REGISTRY:
        nm, r = ('eyes', 2.6) if type(p).__name__ == 'Researcher' else ('face', 3.2)
        try:
            pt = p.anchor(t, nm)
        except Exception:
            continue
        if pt is not None:
            sc = 1.0
            try:
                sc = float(getattr(p, 'scale', 1.0) or 1.0)
            except Exception:
                pass
            out.append((Vector(pt), r * sc))
    return out


# ------------------------------------------------------------------------------------------------ the automatic stand


@dataclass
class StageSpec:
    """What the automatic placement needs to know about the rows it seats."""
    cells: float = 24.0          # widest row, in units (letters + gaps)
    rows: int = 1                # rows of text (stacked shelves)
    height: float = 0.075        # a block's height as a fraction of the frame height
    max_width: float = 0.8       # the widest row as a fraction of the frame width
    blur: float = 2.0            # max depth-of-field blur (px at 1920) at the row
    v: tuple = (0.075, 0.11, 0.15, 0.2, 0.26, 0.33)   # candidate heights of the row's base (0 = frame bottom)
    u: tuple = (0.5, 0.4, 0.6, 0.32, 0.68)      # candidate horizontal centres
    row_gap: float = 1.6         # shelf spacing in units
    support: str = 'auto'        # 'auto' | 'stand' | 'float' | 'desk'
    flat_pitch: float = -55.0    # cameras looking down steeper than this get rows lying flat
    margin: float = 0.03
    light: float = 0.22          # a soft spot on the stand, as a fraction of the desk lamp's light (0: none)


def auto_seat(cam, t0: float, t1: float, spec: StageSpec, *, quiet=False) -> Seat:
    """Find a spot for a lyric stand in one shot: in the lower third, on (or just in front of) the focus plane,
    in front of what the camera looks at, clear of faces, standing on whatever surface is under it (or on legs down
    to it). Candidates are scored by: collisions / occlusion / faces / leaving the frame (hard; checked at the
    start, middle and end of the shot), then blur, then how far from the bottom centre they are."""
    tm = 0.5 * (t0 + t1)
    times = sorted({min(t0 + 0.05, tm), tm, max(tm, t1 - 0.06)})
    S = cam_state(cam, tm)
    states = {t: (S if abs(t - tm) < 1e-6 else cam_state(cam, t)) for t in times}
    others = [st for t, st in states.items() if abs(t - tm) > 1e-6]
    flat = S.pitch < spec.flat_pitch
    if S.focus:
        depths = []
        for b in (spec.blur * 0.5, spec.blur, spec.blur * 2.0, spec.blur * 3.5, spec.blur * 6.0, spec.blur * 9.0):
            d = S.depth_for_blur(b, near=True)
            if not depths or abs(d - depths[-1]) > 0.2:
                depths.append(d)
    else:
        depths = [S.subject * k for k in (0.9, 0.8, 0.7, 0.6)]
    far = S.depth_for_blur(spec.blur * 2.0, near=False)
    fcs = {t: faces(t) for t in times}
    cands = []
    haze = no_haze().__enter__()
    with with_frame(tm):
        for d in depths:
            H = S.frame_h(d)
            W = S.frame_w(d)
            size = min(spec.height * H, spec.max_width * W / max(spec.cells, 1.0))
            stack_h = size * (1.0 + (spec.rows - 1) * spec.row_gap)
            for iv, v in enumerate(spec.v):
                for iu, u in enumerate(spec.u):
                    res = _try_seat(S, others, spec, u, v, d, size, stack_h, flat, far)
                    if res is not None:
                        seat, bad, blur, pts, corners = res
                        cands.append([seat, bad, blur, pts, corners, iv, iu])
    # occlusion, faces and other lyrics at each sample time (things that appear during the shot count too).
    # Branch and bound: those checks only add to a candidate's score, so evaluate the most promising first, in
    # batches, until the best full score beats every remaining preliminary score.
    def prelim(c):
        seat, bad, blur, iv, iu = c[0], c[1], c[2], c[5], c[6]
        return 10.0 * bad + 0.8 * blur + 0.6 * iv + 0.35 * iu + (0.0 if seat.mode == 'desk' else 0.4)
    cands.sort(key=prelim)
    best = None
    scored = []
    k = 0
    BATCH = 10
    while k < len(cands):
        batch = cands[k:k + BATCH]
        k += BATCH
        for t in times:
            st = states[t]
            w = 1.0 if abs(t - tm) < 1e-6 else 0.5
            with with_frame(t):
                boxes = lyric_boxes(st)
                for c in batch:
                    seat, pts, corners = c[0], c[3], c[4]
                    size = seat.size
                    for q in pts:
                        dvec = q - st.loc
                        L = dvec.length
                        hit = raycast(st.loc, dvec, dist=L + 1.6 * size)
                        if hit is not None and hit[0] < L + 1.4 * size:
                            c[1] += w * (2 if hit[0] < L - 0.2 * size else 1)
                    c[1] += w * _face_overlap(st, corners, fcs[t], seat.info['depth'], size)
                    c[1] += w * _box_overlap(st, corners, boxes)
        for c in batch:
            score = prelim(c)
            scored.append((score, c[0], c[1], c[2]))
            if best is None or score < best[0]:
                best = (score, c[0], c[1], c[2])
        if best is not None and (k >= len(cands) or best[0] <= prelim(cands[k])):
            break
    haze.__exit__()
    if DEBUG:
        for sc_, st_, bd, bl in sorted(scored, key=lambda x: x[0])[:12]:
            print(f'[run] lyrics.dbg {cam.name}: score {sc_:.1f} hits {bd} blur {bl:.1f} {st_.mode} '
                  f'uv {st_.info["uv"]} '
                  f'depth {st_.info["depth"]:.1f} size {st_.size:.2f}', flush=True)
        print(f'[run] lyrics.dbg {cam.name}: {len(cands)} candidates, depths {[round(x, 1) for x in depths]}',
              flush=True)
    if best is None:
        d = depths[0]
        size = min(spec.height * S.frame_h(d), spec.max_width * S.frame_w(d) / max(spec.cells, 1.0))
        p = S.unproject(spec.u[0], spec.v[-1], d)
        front = S.loc - p
        front.z = 0
        seat = Seat(t0, t1, frame_matrix(p, front if front.length > 1e-6 else -S.fwd, (0, 0, 1)), size,
                    mode='float', cam=cam, info={'uv': (spec.u[0], spec.v[-1]), 'depth': d})
        best = (99, seat, 9, 0.0)
    seat = best[1]
    seat.t0, seat.t1, seat.cam = t0, t1, cam
    if DEBUG:
        print(f'[run] lyrics.dbg {cam.name}: CHOSE {seat.mode} legs {seat.legs:.2f} at '
              f'{[round(x, 2) for x in seat.matrix.translation]} {seat.info}', flush=True)
    seat.info['blur'] = round(best[3], 1)
    seat.info['bad'] = best[2]
    if (best[2] or best[3] > spec.blur * 2.5) and not quiet:
        print(f'[run] lyrics: shot {cam.name} {t0:.2f}-{t1:.2f}: lyric stand compromised (hits {best[2]}, '
              f'blur {best[3]:.0f} px, {seat.mode} at u,v {seat.info.get("uv")}); stage these lines yourself?',
              flush=True)
    return seat


def lyric_boxes(S) -> list[tuple[float, float, float, float]]:
    """Screen boxes (u0, u1, v0, v1) of the lyric pieces visible now (other rows the stand must not cover)."""
    out = []
    for o in bpy.context.scene.objects:
        if not o.name.startswith('ly.L') or o.type not in ('MESH', 'CURVE') or o.hide_render:
            continue
        mw = o.matrix_world
        pts = [S.project(mw @ Vector(c)) for c in o.bound_box]
        pts = [q for q in pts if q[0] == q[0] and q[2] > 0]
        if not pts:
            continue
        u0, u1 = min(q[0] for q in pts), max(q[0] for q in pts)
        v0, v1 = min(q[1] for q in pts), max(q[1] for q in pts)
        if u1 < 0 or u0 > 1 or v1 < 0 or v0 > 1:
            continue
        out.append((u0, u1, v0, v1))
    return out


def _box_overlap(S, corners, boxes) -> int:
    if not boxes:
        return 0
    uvs = [S.project(c) for c in corners]
    if any(not (q[0] == q[0]) for q in uvs):
        return 0
    x0, x1 = min(q[0] for q in uvs), max(q[0] for q in uvs)
    y0, y1 = min(q[1] for q in uvs), max(q[1] for q in uvs)
    n = 0
    for u0, u1, v0, v1 in boxes:
        if u1 > x0 and u0 < x1 and v1 > y0 and v0 < y1:
            n += 1
    return 3 if n else 0


def _face_overlap(S, corners, fc, dep, size) -> int:
    if not fc:
        return 0
    uvs = [S.project(c) for c in corners]
    if any(not (q[0] == q[0]) for q in uvs):
        return 0
    x0, x1 = min(q[0] for q in uvs), max(q[0] for q in uvs)
    y0, y1 = min(q[1] for q in uvs), max(q[1] for q in uvs)
    bad = 0
    for fp, rad in fc:
        fu, fv, fd = S.project(fp)
        if not (fu == fu) or fd <= 0:
            continue
        ru = rad / S.frame_w(fd)
        rv = rad / S.frame_h(fd)
        if fu + ru > x0 and fu - ru < x1 and fv + rv > y0 and fv - rv < y1 and fd > dep - size:
            bad += 4
    return bad


def _try_seat(S, others, spec, u, v, d, size, stack_h, flat, far):
    """One candidate's geometry: (Seat, badness so far, blur px, occlusion probe points, corners) or None."""
    bad = 0
    ray = S.ray(u, v)
    p = S.loc + ray * (d / max(ray.dot(S.fwd), 1e-6))
    legs = 0.0
    if flat:
        # lying flat on whatever the camera sees there
        hit = raycast(S.loc, ray, dist=far * 1.5)
        if hit is None or hit[2].z < 0.7:
            return None
        pt = hit[1]
        dep = (pt - S.loc).dot(S.fwd)
        up = S.upv - Vector((0, 0, S.upv.z))
        if up.length < 1e-4:
            up = S.fwd - Vector((0, 0, S.fwd.z))
        M = frame_matrix(pt + Vector((0, 0, 0.02)), (0, 0, 1), up)
        seat = Seat(0, 0, M, size, mode='desk', flat=True, info={'uv': (u, v), 'depth': dep})
        r = Vector(M.col[0][:3])
        upw = Vector(M.col[2][:3])
        half = 0.5 * spec.cells * size
        corners = [pt - r * half, pt + r * half, pt - r * half + upw * stack_h, pt + r * half + upw * stack_h]
        pts = [pt + r * (x * half) + upw * (z * stack_h) + Vector((0, 0, 0.3 * size))
               for x in (-0.9, 0, 0.9) for z in (0.2, 0.8)]
        return seat, bad, S.blur_px(dep), pts, corners
    front = S.loc - p
    front.z = 0.0
    if front.length < 1e-6:
        front = -S.fwd
    r0 = Vector((0, 0, 1)).cross(front.normalized())
    half = 0.5 * spec.cells * size
    tops = []
    for x in (-0.85, 0.0, 0.85):
        q = p + r0 * (x * half)
        hit = raycast(Vector((q.x, q.y, q.z + stack_h + 2.0 * size)), (0, 0, -1), dist=500.0)
        if hit is not None and hit[2].z > 0.5:
            tops.append(hit[1].z)
    top = max(tops) if tops else None
    if top is not None and p.z < top + 0.35 * size:
        # (nearly) buried: stand it on the surface where the camera ray meets it
        hit = raycast(S.loc, ray, dist=far * 1.5)
        if hit is None or hit[2].z < 0.7:
            return None
        p = hit[1]
        mode = 'desk'
        front = S.loc - p
        front.z = 0.0
    elif top is not None:
        mode = 'stand' if spec.support in ('auto', 'stand') else 'float'
        legs = (p.z - top) / size
        if legs > 40:
            mode, legs = 'float', 0.0
    else:
        mode = 'float'
    if spec.support == 'desk' and mode != 'desk':
        return None
    if spec.support == 'float':
        mode, legs = 'float', 0.0
    dep = (p - S.loc).dot(S.fwd)
    if dep <= S.clip[0] * 2:
        return None
    M = frame_matrix(p, front, (0, 0, 1))
    r = Vector(M.col[0][:3])
    corners = [p - r * half, p + r * half, p - r * half + Vector((0, 0, stack_h)),
               p + r * half + Vector((0, 0, stack_h))]
    for st in [S] + others:
        for c in corners:
            uu, vv, dd = st.project(c)
            if not (uu == uu) or dd <= 0:
                return None
            if uu < spec.margin or uu > 1 - spec.margin or vv < spec.margin * 0.5 or vv > 0.66:
                bad += 1 if st is not S else 3
    fr = Vector(M.col[1][:3]) * -1.0          # toward the viewer
    pts = [p + r * (x * half) + Vector((0, 0, z * stack_h)) + fr * (0.6 * size)
           for x in (-0.9, -0.45, 0, 0.45, 0.9) for z in (0.3, 0.8)]
    seat = Seat(0, 0, M, size, mode=mode, legs=legs, info={'uv': (u, v), 'depth': dep})
    return seat, bad, S.blur_px(dep), pts, corners


# ------------------------------------------------------------------------------------------------ explicit placements


class Place:
    """Base class for placements. seats(t0, t1, spec) -> [Seat]."""
    def seats(self, t0, t1, spec):
        raise NotImplementedError


class Auto(Place):
    """The lyric stand: one per shot, found automatically (see auto_seat); rows in the same shot share it.
    Keywords override StageSpec fields (height=, blur=, u=, v=, support=...)."""
    def __init__(self, **spec):
        self.spec = spec


class At(Place):
    """A fixed spot in the world: loc = the row's base centre (cm). face: 'camera' (turn to the camera active at
    the reveal), a yaw in degrees, or a direction vector. flat=True lays it on the surface (letters up, their tops
    pointing away from `face`). size: cm per unit (a block's height / a letter's cap height)."""
    def __init__(self, loc, *, face='camera', flat=False, size=1.2, up=(0, 0, 1), parent=None, tilt=0.0):
        self.loc, self.face, self.flat, self.size, self.up, self.parent, self.tilt = \
            Vector(loc), face, flat, size, Vector(up), parent, tilt

    def matrix(self, t):
        f = self.face
        if isinstance(f, str) and f == 'camera':
            cam = camera_at(t)
            S = cam_state(cam, t)
            d = S.loc - self.loc
            d.z = 0
            fr = d if d.length > 1e-6 else Vector((0, -1, 0))
        elif isinstance(f, (int, float)):
            a = math.radians(f)
            fr = Vector((math.sin(a), -math.cos(a), 0.0))   # yaw 0 faces -Y (the default camera side)
        else:
            fr = Vector(f)
        if self.flat:
            M = frame_matrix(self.loc, self.up, fr * -1 if fr.length else Vector((0, 1, 0)))
        else:
            M = frame_matrix(self.loc, fr, self.up)
        if self.tilt:
            M = M @ Matrix.Rotation(math.radians(self.tilt), 4, 'X')
        return M

    def seats(self, t0, t1, spec):
        return [Seat(t0, t1, self.matrix(t0), self.size, parent=self.parent, mode='free', flat=self.flat)]


class On(Place):
    """A surface frame: origin, the surface normal (front) and the letters' up, all world (or local to parent)."""
    def __init__(self, origin, normal, up, *, size=1.0, parent=None, lift=0.01):
        self.origin, self.normal, self.upv, self.size, self.parent, self.lift = \
            Vector(origin), Vector(normal), Vector(up), size, parent, lift

    def seats(self, t0, t1, spec):
        n = self.normal.normalized()
        M = frame_matrix(self.origin + n * self.lift, n, self.upv)
        return [Seat(t0, t1, M, self.size, parent=self.parent, mode='surface')]


class Lens(Place):
    """Camera-attached: a pane just in front of the lens of whichever camera is live, at `dist` cm (default: 45 % of
    the focus distance: soft unless the scene racks focus to it; see lyrics.rack). u, v: the row's base centre in the
    frame; height: a letter's height as a fraction of the frame height."""
    def __init__(self, *, dist=None, u=0.5, v=0.12, height=0.07, max_width=0.8, cells=None):
        self.dist, self.u, self.v, self.height, self.max_width, self.cells = dist, u, v, height, max_width, cells

    def seats(self, t0, t1, spec):
        out = []
        for a, b, cam in shots(t0, t1):
            S = cam_state(cam, 0.5 * (a + b))
            d = self.dist or 0.45 * S.subject
            cells = self.cells or spec.cells
            size = min(self.height * S.frame_h(d), self.max_width * S.frame_w(d) / max(cells, 1.0))
            x = (self.u - 0.5 + S.shift[0]) * S.frame_w(d)
            y = (self.v - 0.5 + S.shift[1] * S.sw / S.sh) * S.frame_h(d)
            M = frame_matrix(Vector((x, y, -d)), (0, 0, 1), (0, 1, 0))
            out.append(Seat(a, b, M, size, parent=cam, mode='lens', cam=cam, info={'dist': d}))
        return out


def laptop(desk, *, u=0.5, v=0.3, size=None, lift=0.02, follow=True):
    """The laptop's screen as a surface (desk = sets.build_desk's Desk): text at (u, v) of the screen, reading along
    its width. size: cm per unit (default: 7 % of the screen height). follow: ride the lid (it can open or close)."""
    lp = desk.laptop
    o = lp.screen_obj
    M3 = o.matrix_world.to_3x3()
    xw = (M3 @ Vector((1, 0, 0))).normalized()
    zw = (M3 @ Vector((0, 0, 1))).normalized()
    n = zw.cross(xw).normalized()      # screen normal toward the viewer if x is right and z is up
    sgn = 1.0
    if n.dot(Vector(desk.anchors['laptopKeys']) - Vector(desk.anchors['laptopScreen'])) < 0:
        n = -n
        sgn = -1.0
    sz = size or 0.07 * lp.sh
    if follow:
        # local frame of the screen object: x along the width, z up the screen, the normal along local y
        nl = Vector((0, 0, 1)).cross(Vector((1, 0, 0))) * sgn
        return On(Vector(((u - 0.5) * lp.sw, 0.0, (v - 0.5) * lp.sh)), nl, Vector((0, 0, 1)), size=sz, parent=o,
                  lift=lift)
    return On(lp.screen_point(u, v), n, zw, size=sz, lift=lift)


def on_object(obj, origin, normal, up, *, size=1.0, lift=0.01):
    """Text on any object's surface that follows it (a jar label, a notebook page, a box side): origin, normal and
    up in the object's LOCAL space; size in cm per unit (the object's scale is compensated)."""
    return On(Vector(origin), Vector(normal), Vector(up), size=size, parent=obj, lift=lift)

