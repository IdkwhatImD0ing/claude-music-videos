"""singularity: keep the things orbiting the hole out of each other.

Every captured item (sticky notes, clips, the pen, the ripped-up track pieces) follows its own closed-form orbit, and
nothing kept the paths apart, so the pen went through notes and the track pieces piled up through one another. This
pass takes the per-frame matrices of all of them, finds the frames where two items' boxes overlap, and nudges them
apart by the least amount that separates them (exact, from the separating-axis test), trying three directions: up /
down, in / out from the hole, and along the orbit. The nudges are smoothed in time so the items swerve round each
other instead of popping. Pure function of the inputs: no state, no randomness.

An item is a dict: ob, frames (scene frames), mats (world matrices, one per frame), free (song time from which it may
be moved; before that it rests where the scene put it and is an obstacle only), bins (boxes along its length).
"""
from __future__ import annotations

import math

import numpy as np
from mathutils import Vector

from pdoom import fx
from pdoom import timing as tm
from pdoom.sets import geo

FPS = tm.FPS
FLOOR_Z = 0.02          # the desk top (items never get pushed below it)
MARGIN = 0.05           # cm of clearance on every separation
GRACE = 0.12            # s after release during which touching a resting item is fine (peeling off the pad / rails)


def _local_boxes(ob, nbins):
    """Boxes (centre, half extents) in ob's local frame covering ob and its descendants' geometry, split into `nbins`
    slabs along the longest axis (a curved track piece is three boxes, not one loose one)."""
    Mi = ob.matrix_world.inverted()
    pts = []
    for o in [ob] + list(geo.descendants(ob)):
        M = Mi @ o.matrix_world
        if o.type == 'MESH' and len(o.data.vertices):
            co = np.empty(len(o.data.vertices) * 3)
            o.data.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3)
            A = np.array(M.to_3x3())
            pts.append(co @ A.T + np.array(M.translation))
        elif o.type not in ('EMPTY', 'LIGHT', 'CAMERA'):
            pts.append(np.array([tuple(M @ Vector(c)) for c in o.bound_box]))
    if not pts:
        return []
    P = np.concatenate(pts)
    lo, hi = P.min(0), P.max(0)
    ax = int(np.argmax(hi - lo))
    edges = np.linspace(lo[ax], hi[ax], nbins + 1)
    out = []
    for k in range(nbins):
        sel = P[(P[:, ax] >= edges[k] - 1e-6) & (P[:, ax] <= edges[k + 1] + 1e-6)]
        if len(sel) == 0:
            continue
        a, b = sel.min(0), sel.max(0)
        out.append(((a + b) / 2, np.maximum((b - a) / 2, 0.01)))
    return out


def _axes(Au, Bu):
    L = [Au[0], Au[1], Au[2], Bu[0], Bu[1], Bu[2]]
    for i in range(3):
        for j in range(3):
            c = np.cross(Au[i], Bu[j])
            n = np.linalg.norm(c)
            if n > 1e-6:
                L.append(c / n)
    return np.array(L)


def _interval(ca, Au, ea, cb, Bu, eb, U):
    """For each direction u in U (rows): the range [lo, hi] of d (box A moved by d*u) over which boxes A and B overlap,
    or None if they never do. Returns None overall when they don't overlap now. Au / Bu: rows = unit axes."""
    L = _axes(Au, Bu)
    R = np.abs(L @ Au.T) @ ea + np.abs(L @ Bu.T) @ eb + MARGIN
    D = L @ (ca - cb)
    if np.any(np.abs(D) > R):
        return None                         # separated now
    out = []
    for u in U:
        uL = L @ u
        lo, hi = -1e9, 1e9
        ok = True
        for d, z, r in zip(D, uL, R):
            if abs(z) < 1e-7:
                continue                    # (overlapping on this axis whatever d is)
            a, b = (-r - d) / z, (r - d) / z
            if a > b:
                a, b = b, a
            lo, hi = max(lo, a), min(hi, b)
        out.append((lo, hi) if ok else None)
    return out


def _clear(ivs):
    """Smallest d >= 0 and largest d <= 0 outside the union of intervals (each contains 0)."""
    up = 0.0
    for a, b in sorted(ivs):
        if a <= up + 1e-9 and b > up:
            up = b
    down = 0.0
    for a, b in sorted(ivs, key=lambda x: -x[1]):
        if b >= down - 1e-9 and a < down:
            down = a
    return up, down


def _gauss(x, sigma):
    r = max(1, int(math.ceil(sigma * 3)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    xp = np.concatenate([np.full(r, x[0]), x, np.full(r, x[-1])])
    return np.convolve(xp, k, mode='valid')


def _maxf(x, w):
    xp = np.concatenate([np.full(w, x[0]), x, np.full(w, x[-1])])
    return np.array([xp[i:i + 2 * w + 1].max() for i in range(len(x))])


def _smooth_signed(x, reach, sigma):
    """Smooth a signed track so its peaks survive (max filter, then Gaussian, for each sign)."""
    return _gauss(_maxf(np.maximum(x, 0.0), reach), sigma) - _gauss(_maxf(np.maximum(-x, 0.0), reach), sigma)


def separate(items, center, *, iters=12, sigma_s=0.05, reach_s=0.07, max_push=4.0, max_total=6.0, label='sep'):
    """Adds the separating offsets into each item's mats in place. center: the hole (radial / orbit directions).
    Returns the number of overlapping (item pair, frame)s left."""
    if not items:
        return 0
    frames = items[0]['frames']
    for it in items:
        assert len(it['frames']) == len(frames)
    nf, n = len(frames), len(items)
    ts = np.array(frames) / FPS
    step = (ts[-1] - ts[0]) / max(1, nf - 1)
    sigma, reach = max(0.7, sigma_s / step), max(1, int(round(reach_s / step)))
    C = np.array(tuple(center))
    boxes = [_local_boxes(it['ob'], it.get('bins', 1)) for it in items]
    loc = np.zeros((n, nf, 3))
    rot = np.zeros((n, nf, 3, 3))          # rows: the item's unit axes in world
    sxyz = np.ones((n, nf, 3))             # scale along them (the cars stretch on the spiral)
    for i, it in enumerate(items):
        for f, M in enumerate(it['mats']):
            A = np.array(M.to_3x3())
            ln = np.maximum(np.linalg.norm(A, axis=0), 1e-6)
            loc[i, f] = tuple(M.translation)
            rot[i, f] = (A / ln).T
            sxyz[i, f] = ln
    scl = sxyz.max(2)
    rad = np.array([max((np.linalg.norm(c) + np.linalg.norm(h) for c, h in bx), default=0.0) for bx in boxes])
    free = np.array([it['free'] for it in items])
    until = np.array([it.get('until', 1e9) for it in items])
    act = ts[None, :] >= free[:, None]
    young = ts[None, :] < free[:, None] + GRACE
    alive = (sxyz.min(2) > 0.05) & (rad[:, None] > 0) & (ts[None, :] < until[:, None])
    mask = np.clip((ts[None, :] - free[:, None]) / GRACE, 0.0, 1.0)
    mask = mask * mask * (3 - 2 * mask)
    raw = np.zeros((n, nf, 3))
    off = np.zeros((n, nf, 3))
    Z = np.array([0.0, 0.0, 1.0])

    def world_boxes(i, f):
        Ax = rot[i, f]
        s = sxyz[i, f]
        c0 = loc[i, f] + off[i, f]
        return [(c0 + Ax.T @ (c * s), Ax, h * s) for c, h in boxes[i]]

    left = 0
    stats = {}
    for it_n in range(iters + 1):
        need = np.zeros((n, nf, 3))
        left = 0
        stats = {}
        tbin = {}
        for f in range(nf):
            idx = [i for i in range(n) if alive[i, f]]
            if len(idx) < 2:
                continue
            P = loc[idx, f] + off[idx, f]
            rr = rad[idx] * scl[idx, f]
            wb = {}
            for a in range(len(idx)):
                i = idx[a]
                for b in range(a + 1, len(idx)):
                    j = idx[b]
                    wi, wj = float(act[i, f]), float(act[j, f])
                    if wi + wj == 0:
                        continue
                    if np.linalg.norm(P[a] - P[b]) > rr[a] + rr[b] + MARGIN:
                        continue
                    if (wi == 0 and young[j, f]) or (wj == 0 and young[i, f]):
                        continue
                    for k in (i, j):
                        if k not in wb:
                            wb[k] = world_boxes(k, f)
                    # directions: up, out from the hole, along the orbit (at the pair's midpoint)
                    mid = (P[a] + P[b]) / 2 - C
                    rh = np.array([mid[0], mid[1], 0.0])
                    rh = rh / np.linalg.norm(rh) if np.linalg.norm(rh) > 1e-6 else np.array([1.0, 0.0, 0.0])
                    tg = np.cross(Z, rh)
                    U = np.array([Z, rh, tg])
                    per = [[], [], []]
                    hit = False
                    for ca, Au, ea in wb[i]:
                        for cb, Bu, eb in wb[j]:
                            r_ = _interval(ca, Au, ea, cb, Bu, eb, U)
                            if r_ is None:
                                continue
                            hit = True
                            for q in range(3):
                                per[q].append(r_[q])
                    if not hit:
                        continue
                    left += 1
                    tbin[int(ts[f] * 2) / 2] = tbin.get(int(ts[f] * 2) / 2, 0) + 1
                    if it_n in (0, iters):
                        key = (items[i]['ob'].name, items[j]['ob'].name)
                        stats[key] = stats.get(key, 0) + 1
                    dpos = P[a] - P[b]
                    zi = min(c[2] - np.abs(Au[:, 2]) @ e for c, Au, e in wb[i])
                    zj = min(c[2] - np.abs(Au[:, 2]) @ e for c, Au, e in wb[j])
                    best = None
                    for q in range(3):
                        up, down = _clear(per[q])
                        pref_up = dpos @ U[q] >= 0          # i is already on the + side: keep it there
                        for d in (up, down):
                            cost = abs(d) * (1.0 if (d > 0) == pref_up else 1.6) * (1.0 if q == 0 else 1.15)
                            if q == 0:
                                # neither may end up below the desk
                                di, dj = d * wi / (wi + wj), -d * wj / (wi + wj)
                                if (di < 0 and zi + di < FLOOR_Z) or (dj < 0 and zj + dj < FLOOR_Z):
                                    continue
                            if best is None or cost < best[0]:
                                best = (cost, q, d)
                    if best is None or abs(best[2]) > max_push:
                        continue
                    _, q, d = best
                    v = U[q] * d
                    need[i, f] += v * wi / (wi + wj)
                    need[j, f] -= v * wj / (wi + wj)
        fx.log(f'singularity: {label} pass {it_n}: {left} overlapping pair-frames')
        if left == 0 or it_n == iters:
            break
        raw += need * 1.15
        for i in range(n):
            if not raw[i].any():
                continue
            for c in range(3):
                off[i, :, c] = _smooth_signed(raw[i, :, c], reach, sigma) * mask[i]
            m = np.linalg.norm(off[i], axis=1)
            k = np.minimum(1.0, max_total / np.maximum(m, 1e-9))
            off[i] *= k[:, None]                     # a swerve, never a shove across the frame
    fx.log(f'singularity: {label} left by time: ' + ' '.join(f'{k:.1f}:{v}' for k, v in sorted(tbin.items())))
    if stats:
        top = sorted(stats.items(), key=lambda kv: -kv[1])[:10]
        fx.log(f'singularity: {label} left: ' + ', '.join(f'{a}/{b} {c}' for (a, b), c in top))
    mag = np.linalg.norm(off, axis=2)
    big = sorted(range(n), key=lambda i: -mag[i].max())[:6]
    fx.log(f'singularity: {label} biggest swerves: ' + ', '.join(
        f"{items[i]['ob'].name} {mag[i].max():.1f}@{ts[int(mag[i].argmax())]:.2f}" for i in big))
    for i, it in enumerate(items):
        if not off[i].any():
            continue
        for f in range(nf):
            if off[i, f].any():
                M = it['mats'][f].copy()
                M.translation += Vector(tuple(off[i, f]))
                it['mats'][f] = M
    fx.log(f'singularity: {label}: {int((mag.max(1) > 1e-3).sum())} of {n} items swerve, {left} pair-frames left')
    return left
