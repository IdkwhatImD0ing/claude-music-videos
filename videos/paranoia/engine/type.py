"""Text for the montage: words rendered with PIL into cached RGBA sprites, drawn on the GPU with fx.place.

Fonts (assets/fonts, all SIL OFL): 'anton' (tall heavy condensed), 'bebas' (clean condensed caps), 'blackops'
(stencil), 'mono' (Share Tech Mono, HUD readouts), 'orbitron' (sci-fi, weight 400-900), 'glitch' (Rubik Glitch),
'cinzel' (League-like Roman capitals, weight 400-900).

    from engine import type as ty
    img = ty.text(img, 'PARANOIA', x=0.5, y=0.5, size=0.22, font='anton', color=(1,1,1),
                  scale=1.0, rot=0, alpha=1, tracking=0.02, stroke=0.0, stroke_color=(0,0,0),
                  shadow=0.0, glow=0.0, glow_color=(1,0.2,0.2), split=0.0, anchor=(0.5,0.5), weight=None)
        size = cap height as a fraction of frame height; split = RGB split in px; glow = bloom strength
    img = ty.letters(img, 'PARANOIA', x, y, size, per=lambda i, n: dict(dy=..., scale=..., alpha=..., rot=...), ...)
        per-letter animation (dx, dy in frame fractions)
    w = ty.width('PARANOIA', size, font)       # text width as a fraction of frame WIDTH (at the current frame)
"""
import functools
import os

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import fx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS = {
    'anton': 'Anton-Regular.ttf', 'bebas': 'BebasNeue-Regular.ttf', 'blackops': 'BlackOpsOne-Regular.ttf',
    'mono': 'ShareTechMono-Regular.ttf', 'orbitron': 'Orbitron[wght].ttf', 'glitch': 'RubikGlitch-Regular.ttf',
    'cinzel': 'Cinzel[wght].ttf',
}
_frame_h = [1080]


@functools.lru_cache(maxsize=64)
def _font(name, px, weight):
    f = ImageFont.truetype(os.path.join(ROOT, 'assets', 'fonts', FONTS[name]), px)
    if weight is not None:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def _cap_px(name, size_frac, H, weight):
    """Font px so that capital letters are size_frac * H tall."""
    probe = _font(name, 200, weight)
    b = probe.getbbox('H')
    cap = max(1, b[3] - b[1])
    return max(4, int(round(size_frac * H * 200 / cap)))


@functools.lru_cache(maxsize=256)
def sprite(text, name, px, tracking, stroke_px, weight):
    """Alpha masks of the text: [2,h,w] CUDA float (0 = fill, 1 = fill + stroke silhouette), and the caps' centre."""
    f = _font(name, px, weight)
    pad = stroke_px + 4
    widths = [f.getlength(ch) for ch in text]
    track = tracking * px
    tw = sum(widths) + track * max(0, len(text) - 1)
    asc, desc = f.getmetrics()
    w, h = int(tw + 2 * pad), int(asc + desc + 2 * pad)
    fill = Image.new('L', (max(1, w), max(1, h)), 0)
    sil = Image.new('L', (max(1, w), max(1, h)), 0)
    df, ds = ImageDraw.Draw(fill), ImageDraw.Draw(sil)
    x = pad
    for ch, cw in zip(text, widths):
        df.text((x, pad), ch, font=f, fill=255)
        if stroke_px:
            ds.text((x, pad), ch, font=f, fill=255, stroke_width=stroke_px, stroke_fill=255)
        x += cw + track
    m = np.stack([np.asarray(fill), np.asarray(sil if stroke_px else fill)])
    a = torch.from_numpy(m).to(fx.DEV).float() / 255.0
    b = f.getbbox('H')
    cap_mid = (pad + (b[1] + b[3]) / 2) / h
    return a, cap_mid


def width(text, size, font='anton', tracking=0.0, weight=None, H=None, W=None):
    H = H or _frame_h[0]
    W = W or H * 16 / 9
    px = _cap_px(font, size, H, weight)
    f = _font(font, px, weight)
    return (sum(f.getlength(ch) for ch in text) + tracking * px * max(0, len(text) - 1)) / W


def text(img, s, x=0.5, y=0.5, size=0.1, font='anton', color=(1.0, 1.0, 1.0), scale=1.0, rot=0.0, alpha=1.0,
         tracking=0.0, stroke=0.0, stroke_color=(0.0, 0.0, 0.0), shadow=0.0, glow=0.0, glow_color=None,
         split=0.0, anchor=(0.5, 0.5), weight=None):
    if alpha <= 0 or not s:
        return img
    H, W = img.shape[1:]
    _frame_h[0] = H
    px = _cap_px(font, size, H, weight)
    stroke_px = int(round(stroke * H)) if stroke else 0
    masks, cap_mid = sprite(s, font, px, round(tracking, 4), stroke_px, weight)
    fill, sil = masks[0:1], masks[1:2]
    rgb = fx._col(stroke_color, fill) * (sil - fill).clamp(0, 1) + fx._col(color, fill) * fill
    spr = torch.cat([rgb / sil.clamp(min=1e-4), sil], 0)
    anc = (anchor[0], cap_mid if anchor[1] == 0.5 else anchor[1])
    if shadow > 0:
        sh = torch.cat([torch.zeros_like(spr[:3]), spr[3:4] * 0.8], 0)
        img = fx.place(img, sh, x + 0.006 * shadow, y + 0.01 * shadow, scale, rot, alpha * min(1, shadow), anc)
    if glow > 0:
        gl = fx.blur(spr, max(2.0, px * 0.12))
        gc = glow_color or color
        glr = torch.cat([fx._col(gc, gl).expand(3, *gl.shape[1:]), torch.clamp(gl[3:4] * 1.6, 0, 1)], 0)
        img = fx.place(img, glr, x, y, scale, rot, alpha * min(1, glow), anc)
    if split > 0:
        split = split * fx.PX[0]          # px at 1080p
        for ch, dx in ((0, -split), (2, split)):
            one = torch.zeros_like(spr)
            one[ch] = spr[ch]
            one[3] = spr[3] * 0.85
            img = _add(img, one, x + dx / W, y, scale, rot, alpha, anc)
    return fx.place(img, spr, x, y, scale, rot, alpha, anc)


def _add(img, spr, x, y, scale, rot, alpha, anc):
    """Additive draw of a single-channel sprite (for RGB split fringes)."""
    blank = torch.zeros_like(img)
    lay = fx.place(blank, spr, x, y, scale, rot, alpha, anc)
    return torch.clamp(img + lay * 0.9, 0, 1.5)


def letters(img, s, x=0.5, y=0.5, size=0.1, font='anton', per=None, tracking=0.0, weight=None, **kw):
    """Draw each letter separately so it can move on its own. per(i, n) -> dict(dx, dy, scale, rot, alpha, color)."""
    if not s:
        return img
    H, W = img.shape[1:]
    _frame_h[0] = H
    px = _cap_px(font, size, H, weight)
    f = _font(font, px, weight)
    widths = [f.getlength(ch) for ch in s]
    track = tracking * px
    total = sum(widths) + track * max(0, len(s) - 1)
    ax = kw.pop('anchor', (0.5, 0.5))
    left = x * W - ax[0] * total
    cur = left
    n = len(s)
    for i, (ch, cw) in enumerate(zip(s, widths)):
        p = per(i, n) if per else {}
        cxp = (cur + cw / 2) / W + p.get('dx', 0.0)
        args = dict(kw)
        if 'color' in p:
            args['color'] = p['color']
        if ch.strip():
            img = text(img, ch, cxp, y + p.get('dy', 0.0), size, font, scale=p.get('scale', 1.0) * kw.get('scale', 1.0),
                       rot=p.get('rot', 0.0), alpha=p.get('alpha', 1.0) * kw.get('alpha', 1.0), weight=weight,
                       anchor=(0.5, 0.5), **{k: v for k, v in args.items() if k not in ('scale', 'alpha', 'rot')})
        cur += cw + track
    return img
