"""Everything a section file needs:  from engine.api import *

Timing      song (see engine/song.py), env(t, t0, attack, decay), ease helpers smooth/eout/ein
Footage     kill(clip, i) -> exact clip time of kill i (data/kills.json, else the Moments marker); kills(clip)
Remap       K, Remap, velocity(points, t_in, s_in, t_out, ...)  (sync kills to beats with speed ramps)
Camera      Cam, shake, follow(points) -> fn(t)->(cx, cy) through keyed focus points
Effects     fx (engine/fx.py), ty (engine/type.py)
Recipes     impact(E, t, ...)   punch-in + shake + flash + chroma + shockwave + sfx on one hit
            beat_pulse(E, t0, t1, ...)   small zoom pulses on every kick in a window
            T.flash/T.zoom/T.whip/T.spin/T.glitch/T.luma/T.slices/T.iris/T.ink/T.rgb   transitions for E.transition
            L.slam/L.counter/L.lock/L.rec/L.bars/L.words   layer builders for E.layer / E.top
"""
import bisect
import json
import math
import os

from . import fx
from . import type as ty
from .clip import clip
from .config import LENGTH, FPS
from .fx import Cam, shake, smooth, mix, hashf, noise1
from .remap import K, Remap
from .song import song

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

__all__ = ['panel', 'clip', 'LOOKS', 'look', 'song', 'fx', 'ty', 'Cam', 'shake', 'K', 'Remap', 'velocity', 'follow', 'env', 'eout', 'ein', 'smooth',
           'mix', 'hashf', 'noise1', 'impact', 'beat_pulse', 'T', 'L', 'kill', 'kills', 'LENGTH', 'FPS', 'clamp',
           'lerp', 'clip_info']


def clamp(x, a=0.0, b=1.0):
    return a if x < a else b if x > b else x


def lerp(a, b, k):
    return a + (b - a) * k


def eout(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ein(x):
    x = clamp(x)
    return x ** 3


def env(t, t0, attack=0.0, decay=0.15):
    """0..1 envelope: rises over `attack` to t0, then decays exponentially with time constant `decay`."""
    if t < t0 - attack:
        return 0.0
    if t < t0:
        return smooth((t - (t0 - attack)) / attack) if attack > 0 else 1.0
    return math.exp(-(t - t0) / decay)


# --- looks ---------------------------------------------------------------------------------------------------------
LOOKS = {
    # cold security feed
    'surveil': dict(contrast=1.18, sat=0.35, temp=-0.35, tint=0.1, bloom=0.15, bloom_threshold=0.85,
                    shadows=(0.0, 0.03, 0.05), highlights=(-0.02, 0.02, 0.03), vignette=0.45, grain=0.06,
                    scanlines=0.12, exposure=-0.1),
    # grey world, only reds survive, tunnel vision
    'paranoia': dict(contrast=1.3, sat=1.0, pop=1.0, exposure=-0.35, bloom=0.2, vignette=0.7, vignette_radius=0.62,
                     grain=0.05, shadows=(0.03, 0.0, 0.0)),
    # the default chorus look (same as POST)
    'rockstar': dict(),
    # peak moments: hotter, more glow
    'hot': dict(contrast=1.2, sat=1.45, bloom=0.6, bloom_threshold=0.75, exposure=0.1, shadows=(0.03, 0.0, 0.06),
                highlights=(0.05, 0.0, -0.03), vignette=0.25),
}


def look(E, t0, t1, name, fade_in=0.0, fade_out=0.0, amount=1.0):
    """Apply a named look (LOOKS) over [t0, t1), blended in/out over fade_in/fade_out seconds. Numbers and tuples
    are interpolated from whatever the params were before this look."""
    preset = LOOKS[name]

    def f(P, t):
        k = amount
        if fade_in > 0:
            k *= smooth((t - t0) / fade_in)
        if fade_out > 0:
            k *= smooth((t1 - t) / fade_out)
        for key, v in preset.items():
            a = P[key]
            if isinstance(v, tuple):
                P[key] = tuple(x + (y - x) * k for x, y in zip(a, v))
            else:
                P[key] = a + (v - a) * k
    E.post(t0, t1, f)


# --- footage -------------------------------------------------------------------------------------------------------
_kills = None
_cat = None


def _load():
    global _kills, _cat
    if _cat is None:
        _cat = {c['file']: c for c in json.load(open(os.path.join(ROOT, 'data', 'catalog.json')))['candidates']}
        p = os.path.join(ROOT, 'data', 'kills.json')
        _kills = json.load(open(p)) if os.path.exists(p) else {}


def clip_info(clip):
    _load()
    return _cat.get(clip)


def kills(clip):
    """Exact kill times (clip seconds) of the clip's best chain: refined if data/kills.json has them."""
    _load()
    if clip in _kills:
        return list(_kills[clip])
    return list(_cat[clip]['chain'])


def kill(clip, i):
    return kills(clip)[i]


def panel(img, clip_name, s, x0, y0, x1, y1, cam=None, border=0.004, color=(1.0, 1.0, 1.0), alpha=1.0):
    """Draw clip `clip_name` at clip time s into the frame rectangle (x0, y0)-(x1, y1) (fractions), framed by `cam`
    (cx, cy, zoom pick the part of the clip; the panel's aspect crops it). For split-screens and picture-in-picture."""
    import torch
    H, W = img.shape[1:]
    a, b, c, d = int(round(x0 * W)), int(round(x1 * W)), int(round(y0 * H)), int(round(y1 * H))
    pw, ph = max(2, b - a), max(2, d - c)
    cam = cam or Cam()
    src = clip(clip_name).at(s)
    # fill the panel: zoom so the clip covers the panel's aspect
    asp_p, asp_s = pw / ph, src.shape[2] / src.shape[1]
    tile = fx.camera(src, pw, ph, cam.but(zoom=cam.zoom * max(1.0, asp_p / asp_s)))
    out = img.clone()
    a2, b2, c2, d2 = max(0, a), min(W, b), max(0, c), min(H, d)
    out[:, c2:d2, a2:b2] = fx.mix(out[:, c2:d2, a2:b2], tile[:, c2 - c:d2 - c, a2 - a:b2 - a], alpha)
    if border > 0:
        bw = max(1, int(border * H))
        col = torch.tensor(color, device=img.device).view(3, 1, 1)
        for (ya, yb, xa, xb) in ((c2, c2 + bw, a2, b2), (d2 - bw, d2, a2, b2), (c2, d2, a2, a2 + bw), (c2, d2, b2 - bw, b2)):
            out[:, max(0, ya):min(H, yb), max(0, xa):min(W, xb)] = col
    return out


# --- remaps --------------------------------------------------------------------------------------------------------
def velocity(points, t_in, s_in, t_out, s_out=None, hit=0.3, v_in=1.0, v_out=1.0, ease=(0.25, 0.5), hold=0.0):
    """Remap that puts each (t_video, s_clip) point exactly on time, moving at `hit` speed through it and fast
    between (the velocity look). hold > 0 keeps the slow speed for that long around each point. s_out defaults to
    continuing at v_out from the last point."""
    keys = [K(t_in, s_in, v_in, (0.0, 0.0))]
    lt, ls = t_in, s_in
    for t, s in points:
        if hold > 0:
            keys.append(K(t - hold / 2, s - hold / 2 * hit, hit, ease))
            keys.append(K(t + hold / 2, s + hold / 2 * hit, hit, (0.0, 0.0)))
            lt, ls = t + hold / 2, s + hold / 2 * hit
        else:
            keys.append(K(t, s, hit, ease))
            lt, ls = t, s
    if s_out is None:
        s_out = ls + (t_out - lt) * (hit + v_out) / 2
    keys.append(K(t_out, s_out, v_out, (min(0.6, ease[1]), 0.0)))
    return Remap(keys)


def follow(points, default=(0.5, 0.5)):
    """Focus path through keyed (t, cx, cy) points (smoothstep between), as fn(t) -> (cx, cy)."""
    pts = sorted(points)
    ts = [p[0] for p in pts]

    def f(t):
        if not pts:
            return default
        j = bisect.bisect_right(ts, t)
        if j == 0:
            return pts[0][1], pts[0][2]
        if j >= len(pts):
            return pts[-1][1], pts[-1][2]
        a, b = pts[j - 1], pts[j]
        k = smooth((t - a[0]) / max(1e-6, b[0] - a[0]))
        return lerp(a[1], b[1], k), lerp(a[2], b[2], k)
    return f


# --- recipes -------------------------------------------------------------------------------------------------------
def impact(E, t, strength=1.0, cx=0.5, cy=0.5, punch=0.09, shake_amt=0.012, flash=0.35, chroma=16.0, shock=True,
           sfx='impact', color=(1.0, 1.0, 1.0), decay=0.14, seed=None, end=None):
    """One big hit at t: screen punch-in toward (cx, cy), decaying shake, flash, RGB split, shockwave ring, sound.
    end = latest video time any of it may touch (pass your SPAN[1] so a late hit can't leak into the next section)."""
    end = 1e9 if end is None else end
    seed = int(hashf(t) * 1000) if seed is None else seed
    s = strength

    def scr(tt):
        e = env(tt, t, 0.0, decay)
        ox, oy, r = shake(tt, shake_amt * s * env(tt, t, 0.0, decay * 1.6), 22.0, seed)
        return dict(zoom=1 + punch * s * e, ax=cx, ay=cy, ox=ox, oy=oy, rot=r * 0.6)
    E.screen(t, min(end, t + decay * 7), scr)

    def post(P, tt):
        e = env(tt, t, 0.0, decay * 0.5)
        f = flash * s * e
        if f >= P['flash']:            # only recolour the flash while this hit's flash is the brightest
            P['flash'], P['flash_color'] = f, color
        P['chroma'] = P['chroma'] + chroma * s * env(tt, t, 0.0, decay)
        P['chroma_cx'], P['chroma_cy'] = cx, cy
        P['exposure'] += 0.55 * s * env(tt, t, 0.0, decay * 0.3)   # a short exposure kick: bright, not milky
    E.post(t, min(end, t + decay * 6), post)
    if shock:
        def lay(img, tt, ctx):
            u = (tt - t) / 0.45
            if u < 0 or u > 1:
                return img
            return fx.shockwave(img, cx, cy, radius=0.05 + 0.75 * eout(u), width=0.05 + 0.05 * u,
                                strength=0.045 * s * (1 - u), ca=8 * s * (1 - u))
        E.layer(t, min(end, t + 0.45), lay, z=5)
    if sfx:
        E.sfx(sfx, t, gain_db=-3 + 4 * (s - 1))


def beat_pulse(E, t0, t1, kind='kick', amount=0.035, min_s=0.4, decay=0.1):
    """Small zoom pulse on every onset of `kind` in [t0, t1)."""
    E.screen(t0, t1, lambda tt: dict(zoom=1 + amount * song.pulse(tt, kind, decay, min_s)))


class T:
    """Transitions: each returns fn(a, b, p, ctx) for E.transition(t0, t1, fn). Cut point is p = 0.5 unless noted."""

    @staticmethod
    def flash(color=(1.0, 1.0, 1.0)):
        def f(a, b, p, ctx):
            return fx.flash(a, smooth(p * 2), color) if p < 0.5 else fx.flash(b, 1 - smooth((p - 0.5) * 2), color)
        return f

    @staticmethod
    def zoom(cx=0.5, cy=0.5, amount=2.5, blur=0.6):
        """Zoom-through: A rushes in toward (cx, cy) with radial blur, B arrives from zoomed-out."""
        def f(a, b, p, ctx):
            W, H = ctx['W'], ctx['H']
            if p < 0.5:
                k = ein(p * 2)
                img = fx.camera(a, W, H, Cam(zoom=1 + (amount - 1) * k, cx=cx, cy=cy))
                return fx.zoom_blur(img, blur * k, cx, cy)
            k = 1 - eout((p - 0.5) * 2)
            img = fx.camera(b, W, H, Cam(zoom=1 / (1 + (amount - 1) * k * 0.5), cx=0.5, cy=0.5))
            return fx.zoom_blur(img, blur * k, 0.5, 0.5)
        return f

    @staticmethod
    def whip(angle=0.0, blur=0.12, blur_px=None):
        """Whip pan: A slides out along `angle` (deg, 0 = to the left) smeared, B slides in from the other side.
        blur = smear length at the cut as a fraction of the frame width."""
        def f(a, b, p, ctx):
            W, H = ctx['W'], ctx['H']
            ca, sa = math.cos(math.radians(angle)), math.sin(math.radians(angle))
            sp = math.sin(math.pi * p)
            if p < 0.5:
                d = ein(p * 2)
                img = fx.camera(a, W, H, Cam(ox=-ca * d * 0.6, oy=-sa * d * 0.6))
            else:
                d = 1 - eout((p - 0.5) * 2)
                img = fx.camera(b, W, H, Cam(ox=ca * d * 0.6, oy=sa * d * 0.6))
            bp = blur_px if blur_px is not None else blur * 1920    # in 1080p px; dir_blur scales by fx.PX
            return fx.dir_blur(img, ca * bp * sp, sa * bp * sp)
        return f

    @staticmethod
    def spin(deg=120.0):
        def f(a, b, p, ctx):
            W, H = ctx['W'], ctx['H']
            if p < 0.5:
                k = ein(p * 2)
                img = fx.camera(a, W, H, Cam(rot=deg * k / 2, zoom=1 + 0.4 * k))
                return fx.spin_blur(img, 50 * k)
            k = 1 - eout((p - 0.5) * 2)
            img = fx.camera(b, W, H, Cam(rot=-deg * k / 2, zoom=1 + 0.4 * k))
            return fx.spin_blur(img, 50 * k)
        return f

    @staticmethod
    def glitch(rate=30.0):
        def f(a, b, p, ctx):
            t = ctx['t']
            k = math.sin(math.pi * p)
            src = a if hashf(int(t * rate), 3) > p else b
            return fx.glitch(src, int(t * rate), 0.4 + 0.8 * k, rgb=18 * k)
        return f

    @staticmethod
    def luma(soft=0.12, invert=False):
        """B shows through A's dark (or bright) areas first."""
        def f(a, b, p, ctx):
            l = fx.lum(a)
            if invert:
                l = 1 - l
            m = torch_clamp((p * (1 + soft) - l) / soft)
            return fx.mix(a, b, m[None])
        return f

    @staticmethod
    def slices(n=10, axis='y'):
        """Strips of B slide in one after another."""
        def f(a, b, p, ctx):
            import torch
            H, W = a.shape[1:]
            out = a.clone()
            for i in range(n):
                k = eout(clamp(p * 1.6 - i / n * 0.6))
                if axis == 'y':
                    y0, y1 = H * i // n, H * (i + 1) // n
                    off = int((1 - k) * W) * (1 if i % 2 else -1)
                    seg = torch.roll(b[:, y0:y1], off, dims=2)
                    m = torch.zeros(1, 1, W, device=a.device)
                    if off >= 0:
                        m[..., off:] = 1
                    else:
                        m[..., :W + off] = 1
                    out[:, y0:y1] = fx.mix(a[:, y0:y1], seg, m)
                else:
                    x0, x1 = W * i // n, W * (i + 1) // n
                    off = int((1 - k) * H) * (1 if i % 2 else -1)
                    seg = torch.roll(b[:, :, x0:x1], off, dims=1)
                    m = torch.zeros(1, H, 1, device=a.device)
                    if off >= 0:
                        m[:, off:] = 1
                    else:
                        m[:, :H + off] = 1
                    out[:, :, x0:x1] = fx.mix(a[:, :, x0:x1], seg, m)
            return out
        return f

    @staticmethod
    def iris(cx=0.5, cy=0.5, color=(1.0, 0.15, 0.2), ring=True):
        """Circle of B grows out of (cx, cy), with a coloured rim."""
        def f(a, b, p, ctx):
            import torch
            H, W = a.shape[1:]
            u, v = fx._uv(H, W)
            d = torch.sqrt(((u - cx) * W / H) ** 2 + (v - cy) ** 2)
            r = ein(p) * 1.25
            m = torch.clamp((r - d) * H / 3, 0, 1)[None]
            out = fx.mix(a, b, m)
            if ring and 0 < p < 1:
                out = fx.ring(out, cx, cy, r, 0.012, color, 1.0)
            return out
        return f

    @staticmethod
    def ink(seed=1, soft=0.08, scale=6.0):
        """Organic noise-threshold reveal."""
        def f(a, b, p, ctx):
            import torch
            H, W = a.shape[1:]
            u, v = fx._uv(H, W)
            n = (torch.sin(u * scale * 6.3 + seed) * torch.sin(v * scale * 4.1 + seed * 2.3)
                 + 0.5 * torch.sin((u + v) * scale * 9.7 + seed * 5.1)) * 0.25 + 0.5
            m = torch.clamp((p * (1 + 2 * soft) - soft - n) / soft + 0.5, 0, 1)[None]
            return fx.mix(a, b, m)
        return f

    @staticmethod
    def rgb(delay=0.25):
        """B arrives one colour channel at a time (R, then G, then B)."""
        def f(a, b, p, ctx):
            import torch
            ks = [smooth(clamp((p - i * delay) / (1 - 2 * delay))) for i in range(3)]
            return torch.stack([fx.mix(a[i], b[i], ks[i]) for i in range(3)], 0)
        return f


def torch_clamp(x):
    import torch
    return torch.clamp(x, 0, 1)


class L:
    """Layer builders: each returns fn(img, t, ctx) for E.layer(t0, t1, fn) or E.top(...)."""

    @staticmethod
    def slam(text, t0, x=0.5, y=0.5, size=0.2, font='anton', color=(1, 1, 1), hold=0.6, out=0.2, from_scale=3.0,
             split=10.0, glow=0.0, glow_color=(1.0, 0.15, 0.2), stroke=0.0, rot=0.0, shake_amt=0.006, **kw):
        """Word slams in (scale from_scale -> 1 in ~0.1 s), holds, then fades/zooms out."""
        def f(img, t, ctx):
            u = t - t0
            if u < 0 or u > 0.1 + hold + out:
                return img
            if u < 0.1:
                k = eout(u / 0.1)
                sc, al = lerp(from_scale, 1.0, k), k
            elif u < 0.1 + hold:
                k = (u - 0.1) / max(1e-3, hold)
                sc, al = 1.0 + 0.04 * k, 1.0
            else:
                k = (u - 0.1 - hold) / max(1e-3, out)
                sc, al = 1.04 + 0.5 * ein(k), 1 - k
            ox, oy, r = shake(t, shake_amt * env(t, t0 + 0.1, 0, 0.2), 25, int(t0 * 100))
            return ty.text(img, text, x + ox, y + oy, size, font, color, sc, rot + r, al,
                           split=split * (0.3 + env(t, t0 + 0.1, 0, 0.15)), glow=glow, glow_color=glow_color,
                           stroke=stroke, **kw)
        return f

    @staticmethod
    def counter(label, t0, x=0.5, y=0.2, size=0.09, color=(1.0, 0.85, 0.3), hold=0.9, font='anton'):
        """Multikill call-out (e.g. 'TRIPLE KILL'): letters drop in one by one."""
        def f(img, t, ctx):
            u = t - t0
            if u < 0 or u > hold + 0.25:
                return img
            al = 1.0 if u < hold else 1 - (u - hold) / 0.25

            def per(i, n):
                k = eout((u - i * 0.018) / 0.09)
                return dict(dy=-(1 - k) * 0.08, scale=1 + (1 - k) * 0.8, alpha=k * al)
            return ty.letters(img, label, x, y, size, font, per=per, color=color, split=4.0)
        return f

    @staticmethod
    def lock(t0, t1, cx, cy, size=0.2, color=(1.0, 0.18, 0.2), label='TARGET LOCKED', follow_fn=None, width=0.006):
        """Targeting brackets that close in on (cx, cy) and lock with a label. follow_fn(t)->(cx, cy) to track."""
        def f(img, t, ctx):
            if not (t0 <= t < t1):
                return img
            px, py = follow_fn(t) if follow_fn else (cx, cy)
            u = (t - t0) / 0.35
            k = eout(u)
            s = size * (2.4 - 1.4 * k)
            asp = ctx['W'] / ctx['H']
            hw, hh = s / asp / 2, s / 2
            spin = (1 - k) * 90
            al = clamp(u * 3)
            img = fx.brackets(img, px - hw, py - hh, px + hw, py + hh, 0.28, width, color, al)
            img = fx.crosshair(img, px, py, s * 0.18, s * 0.06, width * 0.75, color, al * 0.9, rot=spin)
            if k > 0.95 and label:
                blink = 1.0 if int((t - t0) * 10) % 2 == 0 else 0.6
                img = ty.text(img, label, px, py + hh + 0.04, 0.028, 'mono', color, alpha=blink, tracking=0.12,
                              shadow=1.0)
            return img
        return f

    @staticmethod
    def rec(label='CAM 03', color=(1.0, 0.2, 0.2), base=None):
        """CCTV/surveillance HUD: blinking REC dot, camera label, running timecode."""
        def f(img, t, ctx):
            on = (int(t * 2) % 2) == 0
            if on:
                img = fx.disc(img, 0.055, 0.085, 0.012, color, 0.95)
            img = ty.text(img, 'REC', 0.075, 0.085, 0.03, 'mono', (1, 1, 1), anchor=(0.0, 0.5), alpha=0.9,
                          tracking=0.1)
            img = ty.text(img, label, 0.945, 0.085, 0.026, 'mono', (1, 1, 1), anchor=(1.0, 0.5), alpha=0.85,
                          tracking=0.1)
            tt = (base or 0.0) + t
            tc = f'{int(tt // 3600):02d}:{int(tt // 60) % 60:02d}:{int(tt) % 60:02d}:{int((tt % 1) * 60):02d}'
            img = ty.text(img, tc, 0.945, 0.9, 0.026, 'mono', (1, 1, 1), anchor=(1.0, 0.5), alpha=0.85)
            return img
        return f

    @staticmethod
    def bars(amount_fn):
        """Animated letterbox bars: amount_fn(t) -> fraction of height covered."""
        def f(img, t, ctx):
            return fx.letterbox(img, amount_fn(t))
        return f

    @staticmethod
    def words(t_from, t_to, x=0.5, y=0.82, size=0.055, font='bebas', color=(1, 1, 1), upper=True, **kw):
        """Each sung word in [t_from, t_to) pops on screen while it's sung (lyric punches)."""
        ws = [w for w in song.words if t_from <= w[0] < t_to]

        def f(img, t, ctx):
            for w0, w1, w in ws:
                if w0 - 0.02 <= t < max(w1, w0 + 0.18):
                    s = w.strip(',.!?').upper() if upper else w
                    k = eout((t - w0 + 0.02) / 0.06)
                    return ty.text(img, s, x, y, size, font, color, 1.25 - 0.25 * k, 0, k, **kw)
            return img
        return f
