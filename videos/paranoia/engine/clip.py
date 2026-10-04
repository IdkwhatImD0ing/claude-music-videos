"""Gameplay clips as GPU frames, sampled at any source time.

    from engine.clip import clip
    c = clip('League-of-Legends__2026-02-20__01-11-57.mp4')
    c.fps, c.w, c.h, c.duration
    img = c.at(31.25)            # float16 [3,H,W] 0..1 on the GPU, RIFE in-between frame when s falls between frames
    img = c.at(31.25, interp=False)   # nearest real frame (cheaper)

Decoding is PyAV on the CPU (forward decode, seek only on jumps), frames are cached on the GPU. In-between frames
come from RIFE 4.25 (Practical-RIFE weights via vs-rife, MIT) and are cached too. The in-between position is
quantised to 1/64 frame, so a frame is the same whatever order times are asked in.
"""
import collections
import math
import os
import sys

import av
import numpy as np
import torch
import torch.nn.functional as F

from .config import CLIPS, MODELS

DEV = torch.device('cuda')
Q = 64   # in-between quantisation (fractions of a frame)


class _Rife:
    def __init__(self):
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from .rife.IFNet_HDv3_v4_25 import IFNet
        sd = torch.load(os.path.join(MODELS, 'flownet_v4.25.pkl'), map_location='cpu')
        sd = {k.replace('module.', ''): v for k, v in sd.items() if 'module.' in k}
        net = IFNet(1, False)
        net.load_state_dict(sd, strict=False)
        self.net = net.eval().to(DEV, torch.half)
        self._grid = {}

    def grid(self, ph, pw):
        k = (ph, pw)
        if k not in self._grid:
            div = torch.tensor([(pw - 1.0) / 2.0, (ph - 1.0) / 2.0], dtype=torch.float, device=DEV)
            gx = torch.linspace(-1.0, 1.0, pw, dtype=torch.float, device=DEV).view(1, 1, 1, pw).expand(-1, -1, ph, -1)
            gy = torch.linspace(-1.0, 1.0, ph, dtype=torch.float, device=DEV).view(1, 1, ph, 1).expand(-1, -1, -1, pw)
            self._grid[k] = (div, torch.cat([gx, gy], 1))
        return self._grid[k]

    @torch.inference_mode()
    def pad(self, img):
        """img half [3,H,W] -> padded [1,3,ph,pw] and its encoding."""
        h, w = img.shape[1:]
        ph, pw = math.ceil(h / 64) * 64, math.ceil(w / 64) * 64
        x = F.pad(img[None], (0, pw - w, 0, ph - h))
        return x, self.net.encode(x)

    @torch.inference_mode()
    def between(self, a, b, t):
        """a, b: outputs of pad(); t in (0,1). Returns half [3,ph,pw]."""
        x0, f0 = a
        x1, f1 = b
        ph, pw = x0.shape[2:]
        div, grid = self.grid(ph, pw)
        ts = torch.full((1, 1, ph, pw), float(t), dtype=torch.half, device=DEV)
        return self.net(x0, x1, ts, div, grid, f0, f1)[0]


_rife = None


def rife():
    global _rife
    if _rife is None:
        _rife = _Rife()
    return _rife


class Clip:
    def __init__(self, name, cache=150):
        self.name = name
        self.path = name if os.path.isabs(name) else os.path.join(CLIPS, name)
        c = av.open(self.path)
        vs = c.streams.video[0]
        self.fps = float(vs.average_rate)
        self.tb = float(vs.time_base)
        self.start_pts = vs.start_time or 0
        self.w, self.h = vs.codec_context.width, vs.codec_context.height
        self.duration = float(c.duration / av.time_base) if c.duration else float(vs.frames / self.fps)
        self.n = int(math.floor(self.duration * self.fps))
        c.close()
        self._c = None
        self._it = None
        self._last = -10 ** 9
        self.cache = collections.OrderedDict()   # i -> uint8 [3,H,W] cuda
        self.cap = cache
        self.pads = collections.OrderedDict()    # i -> RIFE padded input + encoding
        self.mids = collections.OrderedDict()    # (i, q) -> half [3,H,W]
        self._cut = {}                           # i -> True if frames i and i+1 are a camera snap

    # --- decoding -------------------------------------------------------------------------------------------
    def _seek(self, i):
        if self._c is None:
            self._c = av.open(self.path)
            self._vs = self._c.streams.video[0]
            self._vs.thread_type = 'AUTO'
        t = max(0.0, i / self.fps - 0.1)
        self._c.seek(int(t / self.tb) + self.start_pts, stream=self._vs, backward=True, any_frame=False)
        self._it = self._c.decode(self._vs)
        self._last = -10 ** 9

    def _put(self, i, arr):
        self.cache[i] = torch.from_numpy(arr).to(DEV, non_blocking=True).permute(2, 0, 1).contiguous()
        self.cache.move_to_end(i)
        while len(self.cache) > self.cap:
            self.cache.popitem(last=False)

    def frame_u8(self, i):
        i = min(max(int(i), 0), self.n - 1)
        if i in self.cache:
            self.cache.move_to_end(i)
            return self.cache[i]
        if not (self._last < i <= self._last + 150):
            self._seek(i)
        got = None
        for f in self._it:
            k = int(round((f.pts - self.start_pts) * self.tb * self.fps))
            self._last = k
            if k >= i - 2:
                self._put(k, f.to_ndarray(format='rgb24'))
            if k >= i:
                got = k
                break
        if i in self.cache:
            return self.cache[i]
        # past the end of the stream, or a gap: nearest cached frame
        if got is None and self.cache:
            k = min(self.cache, key=lambda x: abs(x - i))
            return self.cache[k]
        raise RuntimeError(f'{self.name}: cannot decode frame {i}')

    def frame(self, i):
        return self.frame_u8(i).to(torch.half) / 255.0

    # --- sampling -------------------------------------------------------------------------------------------
    def _pad(self, i):
        if i not in self.pads:
            self.pads[i] = rife().pad(self.frame(i))
            while len(self.pads) > 24:
                self.pads.popitem(last=False)
        return self.pads[i]

    def at(self, s, interp=True):
        """Frame at source time s (seconds), float16 [3,H,W]."""
        x = s * self.fps
        x = min(max(x, 0.0), self.n - 1.0)
        i = math.floor(x)
        q = int(round((x - i) * Q))
        if q >= Q:
            i, q = i + 1, 0
        if not interp:
            return self.frame(min(i + (1 if q >= Q // 2 else 0), self.n - 1))
        if q == 0 or i + 1 >= self.n:
            return self.frame(i)
        if self.is_cut(i):                       # RIFE would morph across a camera snap: take the nearer frame
            return self.frame(i if q < Q // 2 else i + 1)
        key = (i, q)
        if key in self.mids:
            self.mids.move_to_end(key)
            return self.mids[key]
        mid = rife().between(self._pad(i), self._pad(i + 1), q / Q)[:, :self.h, :self.w].clamp(0, 1)
        self.mids[key] = mid
        while len(self.mids) > 48:
            self.mids.popitem(last=False)
        return mid

    def is_cut(self, i, thresh=0.16):
        """True when source frames i and i+1 differ like a camera snap (mean abs difference of 1/8-size greys)."""
        if i not in self._cut:
            a = self.frame_u8(i)[:, ::8, ::8].float().mean(0)
            b = self.frame_u8(i + 1)[:, ::8, ::8].float().mean(0)
            self._cut[i] = bool(((a - b).abs().mean() / 255.0) > thresh)
        return self._cut[i]

    def close(self):
        if self._c is not None:
            self._c.close()
            self._c = None
        self.cache.clear()
        self.pads.clear()
        self.mids.clear()


_open = collections.OrderedDict()


def clip(name, keep=6):
    """Shared Clip instances; keeps the `keep` most recently used open."""
    if name in _open:
        _open.move_to_end(name)
        return _open[name]
    c = Clip(name)
    _open[name] = c
    while len(_open) > keep:
        _, old = _open.popitem(last=False)
        old.close()
    return c
