#!/usr/bin/env python3
"""Smoke test of every engine helper (cloud machine): renders one tile per helper into out/wip/apitest.jpg."""
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import torch  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from engine.api import *  # noqa: E402,F403
from engine import edit as ed  # noqa: E402

A = 'League-of-Legends__2026-02-20__01-11-57.mp4'
B = 'League-of-Legends__2026-09-29__22-41-54.mp4'
C = 'League-of-Legends__2026-03-03__00-18-26.mp4'
W, H = 640, 360


def base(clipname=A, s=46.7, cam=None):
    return fx.camera(clip(clipname).at(s), W, H, cam or Cam(zoom=1.2, cy=0.4))


ctx = dict(W=W, H=H, fps=60, frame=0, t=1.0, song=song)
tests = {
    'camera tilt': lambda: fx.camera(clip(A).at(46.7), W, H, Cam(zoom=1.3, yaw=20, pitch=15, rot=5)),
    'lens': lambda: fx.camera(clip(A).at(46.7), W, H, Cam(zoom=1.2, lens=0.15)),
    'zoom_blur': lambda: fx.zoom_blur(base(), 0.3, 0.5, 0.4),
    'spin_blur': lambda: fx.spin_blur(base(), 20),
    'dir_blur': lambda: fx.dir_blur(base(), 80, 0),
    'bloom hot': lambda: fx.bloom(base(), 0.6, 1.2),
    'chroma': lambda: fx.chroma(base(), 14),
    'shockwave': lambda: fx.shockwave(base(), 0.5, 0.4, 0.25, 0.05, 0.05),
    'glitch': lambda: fx.glitch(base(), 7, 1.0),
    'slices': lambda: fx.slices(base(), 8, 0.05),
    'kaleido': lambda: fx.kaleido(base(), 6, 0.5, 0.4),
    'mirror quad': lambda: fx.mirror(base(), 'quad'),
    'ink': lambda: fx.ink(base(), 0.45),
    'duotone': lambda: fx.duotone(base()),
    'color_pop': lambda: fx.color_pop(base(), 0.0),
    'spotlight': lambda: fx.spotlight(base(), 0.5, 0.4),
    'light_leak': lambda: fx.light_leak(base(), 1.0, 1, 0.6),
    'speed_lines': lambda: fx.speed_lines(base(), 0.5, 0.4, 3, 0.8),
    'pixelate': lambda: fx.pixelate(base(), 12),
    'graphics': lambda: fx.crosshair(fx.brackets(fx.ring(base(), 0.5, 0.4, 0.15, 0.006, (1, .2, .2), 1, (0, 270)),
                                                 0.4, 0.25, 0.6, 0.55), 0.5, 0.4),
    'text': lambda: ty.text(base(), 'PARANOIA', 0.5, 0.5, 0.2, 'anton', (1, 1, 1), glow=0.8, split=8, stroke=0.006,
                            stroke_color=(1, 0.1, 0.2)),
    'letters': lambda: ty.letters(base(), 'PENTAKILL', 0.5, 0.5, 0.12, 'anton',
                                  per=lambda i, n: dict(dy=0.02 * ((-1) ** i), rot=5 * ((-1) ** i)), color=(1, .85, .3)),
    'fonts': lambda: [img := base()] and [img := ty.text(img, f, 0.5, 0.12 + 0.12 * k, 0.07, f) for k, f in
                                         enumerate(['bebas', 'blackops', 'mono', 'orbitron', 'glitch', 'cinzel'])][-1],
    'panel split': lambda: panel(panel(panel(base(), A, 47.0, 0, 0, 0.333, 1), B, 47.4, 0.333, 0, 0.667, 1,
                                       Cam(cx=0.43, cy=0.3)), C, 53.0, 0.667, 0, 1, 1),
    'T.zoom': lambda: T.zoom()(base(), base(B, 47.4), 0.3, ctx),
    'T.whip': lambda: T.whip()(base(), base(B, 47.4), 0.4, ctx),
    'T.spin': lambda: T.spin()(base(), base(B, 47.4), 0.6, ctx),
    'T.glitch': lambda: T.glitch()(base(), base(B, 47.4), 0.5, ctx),
    'T.luma': lambda: T.luma()(base(), base(B, 47.4), 0.5, ctx),
    'T.slices': lambda: T.slices()(base(), base(B, 47.4), 0.5, ctx),
    'T.iris': lambda: T.iris()(base(), base(B, 47.4), 0.5, ctx),
    'T.ink': lambda: T.ink()(base(), base(B, 47.4), 0.5, ctx),
    'T.rgb': lambda: T.rgb()(base(), base(B, 47.4), 0.5, ctx),
    'T.flash': lambda: T.flash()(base(), base(B, 47.4), 0.4, ctx),
    'L.slam': lambda: L.slam('ROCK STAR', 0.9, glow=0.8)(base(), 1.0, ctx),
    'L.counter': lambda: L.counter('TRIPLE KILL', 0.8)(base(), 1.0, ctx),
    'L.lock': lambda: L.lock(0.5, 2.0, 0.5, 0.4)(base(), 1.0, ctx),
    'L.rec': lambda: L.rec()(base(), 1.0, ctx),
    'L.bars': lambda: L.bars(lambda t: 0.2)(base(), 1.0, ctx),
}


def main():
    tiles = []
    fails = []
    for name, fn in tests.items():
        try:
            img = fn()
            assert img.shape == (3, H, W), img.shape
            assert torch.isfinite(img).all()
        except Exception as e:
            traceback.print_exc()
            fails.append(name)
            img = torch.zeros(3, H, W, device=fx.DEV)
        im = Image.fromarray((img.clamp(0, 1) * 255 + 0.5).byte().permute(1, 2, 0).cpu().numpy())
        ImageDraw.Draw(im).text((6, 6), name, fill=(255, 255, 0))
        tiles.append(im)
    cols = 6
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * W, rows * H))
    for i, im in enumerate(tiles):
        S.paste(im, ((i % cols) * W, (i // cols) * H))
    S.save('out/wip/apitest.jpg', quality=85)
    # look() and the post pipeline through a tiny edit
    E = ed.Edit()
    E.shot(0, 2, A, Remap.constant(0, 46.0, 1.0, 2), cam=Cam(zoom=1.2))
    look(E, 0, 2, 'surveil', 0.5, 0.5)
    impact(E, 1.0, 1.0)
    img, n = E.frame(1.02, W, H)
    print('edit frame ok', tuple(img.shape), 'samples', n)
    print('FAILS:', fails or 'none')


if __name__ == '__main__':
    main()
