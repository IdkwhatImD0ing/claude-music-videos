#!/usr/bin/env python3
"""Render review sheets for every section in one go (cloud machine), from data/review.json:

  {"s01": {"times": [..], "strips": [[from, to], ..]}, ...}

writes out/wip/review/<id>_sheet.jpg (labelled frames, 4 per row, 480 px tiles rendered at 1920) and
out/wip/review/<id>_strip<k>.jpg (every frame of each window, 6 per row, 320 px tiles).
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from PIL import Image, ImageDraw  # noqa: E402

import render  # noqa: E402
from engine import edit as ed  # noqa: E402
from engine.config import FPS  # noqa: E402


def sheet(E, ts, out, tile_w, cols, render_w=1920):
    tiles = []
    for t in ts:
        img, n = E.frame(t, render_w, render_w * 9 // 16, FPS, 'auto', 0.5, int(round(t * FPS)))
        im = render.to_pil(img).resize((tile_w, tile_w * 9 // 16), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        lab = render.label_of(E, t, n)
        f = render.font(max(11, tile_w // 30))
        d.rectangle([0, 0, d.textlength(lab, font=f) + 8, f.size + 6], fill=(0, 0, 0))
        d.text((4, 2), lab, fill=(255, 255, 0), font=f)
        tiles.append(im)
    th = tile_w * 9 // 16
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * tile_w, rows * th))
    for k, im in enumerate(tiles):
        S.paste(im, ((k % cols) * tile_w, (k // cols) * th))
    S.save(out, quality=86)


def main():
    spec = json.load(open('data/review.json'))
    only = sys.argv[1].split(',') if len(sys.argv) > 1 else None
    E = ed.build()
    os.makedirs('out/wip/review', exist_ok=True)
    for sid, r in spec.items():
        if only and sid not in only:
            continue
        t0 = time.time()
        sheet(E, r['times'], f'out/wip/review/{sid}_sheet.jpg', 480, 4)
        for k, (a, b) in enumerate(r.get('strips', [])):
            ts = [i / FPS for i in range(int(round(a * FPS)), int(round(b * FPS)) + 1)]
            sheet(E, ts, f'out/wip/review/{sid}_strip{k + 1}.jpg', 320, 6, render_w=960)
        print(sid, f'{time.time() - t0:.1f}s', flush=True)


if __name__ == '__main__':
    main()
