"""The edit: shots, transitions, layers and post, rendered as a pure function of video time t.

Section files (sections/sNN_*.py) each define SPAN = (t0, t1) and build(E), and add to the shared Edit E:

    E.shot(t0, t1, clip, remap, cam=Cam()|fn(t)->Cam, fx=[fn(img, t, ctx)->img], src=None, name='')
        A gameplay shot visible in [t0, t1). remap: Remap (video t -> clip seconds). src(t, ctx, shot) may replace
        the source sampling (echo trails, RGB time split...): it returns a source frame [3,Hs,Ws].
    E.transition(t0, t1, fn(a, b, p, ctx)->img)     blend two overlapping shots; p goes 0->1 over [t0, t1)
    E.layer(t0, t1, fn(img, t, ctx)->img, z=0)      draws over the shots (text, graphics, flashes); shaken/blurred
                                                    with the frame
    E.screen(t0, t1, fn(t)->dict)                   whole-frame camera on top of everything: keys zoom (multiplies;
                                                    ax, ay = the frame point the zoom keeps still), ox, oy, rot,
                                                    lens (add) -> impact punches, global shakes
    E.post(t0, t1, fn(P, t)->None)                  edit post params P in place (grade, bloom, chroma, flash...)
    E.top(t0, t1, fn(img, t, ctx)->img, z=0)        drawn after motion blur and post: crisp UI that must not shake
    E.samples(t0, t1, n)                            force at least n motion-blur sub-samples in a window
    E.sfx(kind, t, **kw) / E.music(kind, t0, t1, **kw) / shot audio: see engine/audio.py (game audio follows each
                                                    shot's remap automatically; pass hits=[...] to E.shot)

ctx: dict(W, H, fps, frame, t, edit, shot, song). Times are video seconds (0..LENGTH).
"""
import importlib
import math
import os
import sys

import torch

from . import fx
from .clip import clip as get_clip
from .config import FPS, LENGTH, SHUTTER, W as DW, H as DH
from .remap import Remap
from .song import song

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

POST = dict(
    exposure=0.0, contrast=1.14, sat=1.28, temp=0.0, tint=0.0, lift=0.0, gamma=0.95, gain=1.0,
    shadows=(0.0, 0.0, 0.03), highlights=(0.03, 0.0, -0.02),
    bloom=0.4, bloom_threshold=0.82, bloom_radius=0.012, bloom_tint=(1.0, 1.0, 1.0),
    pop=0.0, pop_hue=0.0,
    chroma=0.0, chroma_cx=0.5, chroma_cy=0.5,
    flash=0.0, flash_color=(1.0, 1.0, 1.0), invert=0.0, zoom_blur=0.0, zoom_blur_cx=0.5, zoom_blur_cy=0.5,
    glitch=0.0, glitch_rate=12.0, duotone=0.0, duo_dark=(0.04, 0.0, 0.08), duo_light=(1.0, 0.22, 0.3),
    ink=0.0, ink_level=0.5, desat=0.0,
    vignette=0.3, vignette_radius=0.8, grain=0.02, letterbox=0.0, scanlines=0.0,
)


class Shot:
    def __init__(self, t0, t1, clip, remap, cam=None, fx=None, src=None, name='', interp=True, hits=(),
                 game_db=-15.0, audio=True):
        self.t0, self.t1, self.clip_name = t0, t1, clip
        self.remap = remap
        self.cam = cam
        self.fx = list(fx or [])
        self.src = src
        self.name = name or clip
        self.interp = interp
        self.hits = list(hits)
        self.game_db = game_db
        self.audio = audio

    @property
    def clip(self):
        return get_clip(self.clip_name)

    def s(self, t):
        return self.remap.s(t) if isinstance(self.remap, Remap) else self.remap(t)

    def speed(self, t, dt=1e-3):
        if isinstance(self.remap, Remap):
            return self.remap.speed(t)
        return (self.remap(t + dt) - self.remap(t - dt)) / (2 * dt)

    def camera_at(self, t):
        c = self.cam
        if c is None:
            return fx.Cam()
        return c(t) if callable(c) else c

    def image(self, t, ctx):
        ctx['shot'] = self
        src = self.src(t, ctx, self) if self.src else self.clip.at(self.s(t), self.interp)
        img = fx.camera(src, ctx['W'], ctx['H'], self.camera_at(t))
        for f in self.fx:
            img = f(img, t, ctx)
        return img

    def motion_px(self, t, dt, W, H):
        a, b = self.camera_at(t - dt), self.camera_at(t + dt)
        z = max(1e-3, (a.zoom + b.zoom) / 2)
        px = (abs(b.cx - a.cx) * W + abs(b.cy - a.cy) * H) * z + abs(b.ox - a.ox) * W + abs(b.oy - a.oy) * H
        px += abs(b.zoom - a.zoom) / z * W / 2 + abs(b.rot - a.rot) * math.pi / 180 * W / 2
        px += (abs(b.yaw - a.yaw) + abs(b.pitch - a.pitch)) * W / 90
        return px


class Edit:
    def __init__(self):
        self.shots, self.transitions, self.layers, self.screens, self.posts, self.tops = [], [], [], [], [], []
        self.sample_hints, self.sfx_events, self.music_events, self.voice_events = [], [], [], []

    # --- authoring --------------------------------------------------------------------------------------------
    def shot(self, t0, t1, clip, remap, **kw):
        s = Shot(t0, t1, clip, remap, **kw)
        self.shots.append(s)
        return s

    def transition(self, t0, t1, fn):
        self.transitions.append((t0, t1, fn))

    def layer(self, t0, t1, fn, z=0):
        self.layers.append((t0, t1, fn, z))

    def screen(self, t0, t1, fn):
        self.screens.append((t0, t1, fn))

    def post(self, t0, t1, fn):
        self.posts.append((t0, t1, fn))

    def top(self, t0, t1, fn, z=0):
        self.tops.append((t0, t1, fn, z))

    def samples(self, t0, t1, n):
        self.sample_hints.append((t0, t1, n))

    def sfx(self, kind, t, **kw):
        self.sfx_events.append((kind, t, kw))

    def music(self, kind, t0, t1, **kw):
        self.music_events.append((kind, t0, t1, kw))

    def voice(self, path, t, **kw):
        """A recorded voice line starting at t (engine/audio.py Mixer.voice: gain_db, echo, room, duck_db, pan)."""
        self.voice_events.append((path, t, kw))

    # --- queries ----------------------------------------------------------------------------------------------
    def shots_at(self, t):
        return [s for s in self.shots if s.t0 <= t < s.t1]

    def shot_at(self, t):
        a = self.shots_at(t)
        return max(a, key=lambda s: s.t0) if a else None

    # --- rendering --------------------------------------------------------------------------------------------
    def _base(self, t, ctx):
        act = self.shots_at(t)
        if not act:
            return torch.zeros(3, ctx['H'], ctx['W'], device=fx.DEV)
        act.sort(key=lambda s: s.t0)
        if len(act) >= 2:
            for t0, t1, fn in self.transitions:
                if t0 <= t < t1:
                    a = act[-2].image(t, ctx)
                    b = act[-1].image(t, ctx)
                    return fn(a, b, (t - t0) / max(1e-6, t1 - t0), ctx)
        return act[-1].image(t, ctx)

    def _post_params(self, t):
        P = dict(POST)
        for t0, t1, fn in self.posts:
            if t0 <= t < t1:
                fn(P, t)
        return P

    def _screen(self, t):
        """Sum of active screen moves. A move may give an anchor (ax, ay): the frame point its zoom keeps still."""
        z, ox, oy, rot, lens = 1.0, 0.0, 0.0, 0.0, 0.0
        wsum, axs, ays = 0.0, 0.0, 0.0
        for t0, t1, fn in self.screens:
            if t0 <= t < t1:
                d = fn(t) or {}
                zz = d.get('zoom', 1.0)
                z *= zz
                w = abs(zz - 1.0)
                wsum += w
                axs += w * d.get('ax', 0.5)
                ays += w * d.get('ay', 0.5)
                ox += d.get('ox', 0.0)
                oy += d.get('oy', 0.0)
                rot += d.get('rot', 0.0)
                lens += d.get('lens', 0.0)
        ax, ay = (axs / wsum, ays / wsum) if wsum > 1e-9 else (0.5, 0.5)
        return fx.Cam(zoom=z, cx=ax - (ax - 0.5) / z, cy=ay - (ay - 0.5) / z, ox=ox, oy=oy, rot=rot, lens=lens)

    def subframe(self, t, ctx):
        ctx['t'] = t
        img = self._base(t, ctx)
        for t0, t1, fn, z in sorted(self.layers, key=lambda l: l[3]):
            if t0 <= t < t1:
                img = fn(img, t, ctx)
        sc = self._screen(t)
        if abs(sc.zoom - 1.0) > 1e-6 or sc.ox or sc.oy or sc.rot or sc.lens:
            img = fx.camera(img, ctx['W'], ctx['H'], sc)
        P = self._post_params(t)
        ctx['post'] = P
        img = fx.grade(img, P['exposure'], P['contrast'], 0.45, P['sat'], P['temp'], P['tint'], P['lift'],
                       P['gamma'], P['gain'], P['shadows'], P['highlights'])
        if P['desat']:
            l = fx.lum(img)[None]
            img = fx.mix(img, l.expand_as(img), P['desat'])
        if P['pop']:
            img = fx.color_pop(img, P['pop_hue'], 0.06, P['pop'])
        if P['duotone']:
            img = fx.duotone(img, P['duo_dark'], P['duo_light'], P['duotone'])
        if P['ink']:
            img = fx.ink(img, P['ink_level'], amount=P['ink'])
        img = fx.bloom(img, P['bloom_threshold'], P['bloom'], P['bloom_radius'], P['bloom_tint'])
        if P['zoom_blur']:
            img = fx.zoom_blur(img, P['zoom_blur'], P['zoom_blur_cx'], P['zoom_blur_cy'])
        if P['chroma']:
            img = fx.chroma(img, P['chroma'], P['chroma_cx'], P['chroma_cy'])
        if P['glitch']:
            img = fx.glitch(img, int(t * P['glitch_rate']), P['glitch'])
        if P['invert']:
            img = fx.invert(img, P['invert'])
        if P['flash']:
            img = fx.flash(img, P['flash'], P['flash_color'])
        return img

    def n_samples(self, t, W, H, fps, shutter, cap=16):
        dt = shutter / fps / 2
        n = 1.0
        for s in self.shots_at(t):
            src_frames = abs(s.speed(t)) * s.clip.fps * shutter / fps
            n = max(n, src_frames * 2 + 1, s.motion_px(t, dt, W, H) / 3)
        a, b = self._screen(t - dt), self._screen(t + dt)
        px = abs(b.ox - a.ox) * W + abs(b.oy - a.oy) * H + abs(b.zoom - a.zoom) * W / 2 + abs(b.rot - a.rot) * W / 100
        n = max(n, px / 3)
        for t0, t1, k in self.sample_hints:
            if t0 <= t < t1:
                n = max(n, k)
        return int(min(cap, max(1, math.ceil(n))))

    @torch.inference_mode()
    def frame(self, t, W=DW, H=DH, fps=FPS, samples='auto', shutter=SHUTTER, frame_index=None):
        fi = int(round(t * fps)) if frame_index is None else frame_index
        fx.PX[0] = H / 1080.0             # pixel-sized effects keep their 1080p look at any resolution
        ctx = dict(W=W, H=H, fps=fps, frame=fi, edit=self, song=song, t=t)
        n = self.n_samples(t, W, H, fps, shutter) if samples == 'auto' else max(1, int(samples))
        if n == 1 or shutter <= 0:
            img = self.subframe(t, ctx)
        else:
            img = torch.zeros(3, H, W, device=fx.DEV)
            for k in range(n):
                img += self.subframe(t + shutter / fps * ((k + 0.5) / n - 0.5), ctx)
            img /= n
        ctx['t'] = t
        for t0, t1, fn, z in sorted(self.tops, key=lambda l: l[3]):
            if t0 <= t < t1:
                img = fn(img, t, ctx)
        P = self._post_params(t)
        img = fx.vignette(img, P['vignette'], P['vignette_radius'])
        if P['scanlines']:
            img = fx.scanlines(img, P['scanlines'], t=t)
        img = fx.grain(img, fi * 7 + 3, P['grain'])
        if P['letterbox']:
            img = fx.letterbox(img, P['letterbox'])
        return torch.clamp(img, 0, 1), n


def build(only=None):
    """Load every section in sections/ (sorted) into one Edit."""
    sys.path.insert(0, ROOT)
    E = Edit()
    d = os.path.join(ROOT, 'sections')
    for f in sorted(os.listdir(d)):
        if f.startswith('s') and f.endswith('.py'):
            name = f[:-3]
            if only and not any(o in name for o in only):
                continue
            n0 = len(E.shots)
            lists = ('shots', 'transitions', 'layers', 'screens', 'posts', 'tops', 'sample_hints', 'sfx_events',
                     'music_events', 'voice_events')
            sizes = {k: len(getattr(E, k)) for k in lists}
            try:
                m = importlib.import_module(f'sections.{name}')
                m.build(E)
            except Exception:   # one broken section must not stop the others from rendering
                import traceback
                print(f'[edit] SECTION {name} FAILED:', flush=True)
                traceback.print_exc()
                for k in lists:
                    del getattr(E, k)[sizes[k]:]
                continue
            for s in E.shots[n0:]:
                s.section = name
    E.shots.sort(key=lambda s: s.t0)
    return E
