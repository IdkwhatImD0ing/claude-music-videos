#!/usr/bin/env python3
"""Grade presets side by side on real frames (cloud machine): out/wip/grades.jpg

  python tools/gradetest.py --clip <file> --s 46.9
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import torch  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from engine import fx  # noqa: E402
from engine.clip import clip  # noqa: E402
from engine.edit import POST  # noqa: E402


def post(img, P, fi=0):
    img = fx.grade(img, P['exposure'], P['contrast'], 0.45, P['sat'], P['temp'], P['tint'], P['lift'], P['gamma'],
                   P['gain'], P['shadows'], P['highlights'])
    if P.get('desat'):
        l = fx.lum(img)[None]
        img = fx.mix(img, l.expand_as(img), P['desat'])
    if P.get('pop'):
        img = fx.color_pop(img, 0.0, 0.06, P['pop'])
    img = fx.bloom(img, P['bloom_threshold'], P['bloom'], P['bloom_radius'])
    if P.get('scanlines'):
        img = fx.scanlines(img, P['scanlines'])
    img = fx.vignette(img, P['vignette'], P['vignette_radius'])
    img = fx.grain(img, fi, P['grain'])
    return img.clamp(0, 1)


PRESETS = {
    'raw': None,
    'default': {},
    'rockstar': dict(contrast=1.14, sat=1.28, bloom=0.4, bloom_threshold=0.82, shadows=(0.0, 0.0, 0.03),
                     highlights=(0.03, 0.0, -0.02), vignette=0.3, grain=0.02, gamma=0.95),
    'surveil': dict(contrast=1.18, sat=0.35, temp=-0.35, tint=0.1, bloom=0.15, bloom_threshold=0.85,
                    shadows=(0.0, 0.03, 0.05), highlights=(-0.02, 0.02, 0.03), vignette=0.45, grain=0.06,
                    scanlines=0.12, exposure=-0.1),
    'paranoia': dict(contrast=1.3, sat=1.0, pop=1.0, exposure=-0.35, bloom=0.2, vignette=0.7, vignette_radius=0.62,
                     grain=0.05, shadows=(0.03, 0.0, 0.0)),
    'rockstar_hot': dict(contrast=1.2, sat=1.45, bloom=0.6, bloom_threshold=0.75, exposure=0.1,
                         shadows=(0.03, 0.0, 0.06), highlights=(0.05, 0.0, -0.03), vignette=0.25, grain=0.02),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', default='League-of-Legends__2026-02-20__01-11-57.mp4')
    ap.add_argument('--s', type=float, default=46.9)
    a = ap.parse_args()
    src = clip(a.clip).at(a.s, False)
    base = fx.camera(src, 960, 540, fx.Cam(zoom=1.15))
    tiles = []
    for name, p in PRESETS.items():
        P = dict(POST)
        if p is not None:
            P.update(p)
            img = post(base, P)
        else:
            img = base
        im = Image.fromarray((img.clamp(0, 1) * 255 + 0.5).byte().permute(1, 2, 0).cpu().numpy())
        ImageDraw.Draw(im).text((8, 8), name, fill=(255, 255, 0))
        tiles.append(im)
    S = Image.new('RGB', (960 * 3, 540 * 2))
    for i, im in enumerate(tiles):
        S.paste(im, ((i % 3) * 960, (i // 3) * 540))
    os.makedirs('out/wip', exist_ok=True)
    S.save('out/wip/grades.jpg', quality=88)
    print('out/wip/grades.jpg')


if __name__ == '__main__':
    main()
