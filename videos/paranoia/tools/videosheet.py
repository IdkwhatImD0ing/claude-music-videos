#!/usr/bin/env python3
"""Contact sheets sampled from an encoded video (cloud machine), to check the real output.

  python tools/videosheet.py out/wip/paranoia_trial1.mp4 --step 0.5 --per 40 --cols 8 --w 240
  python tools/videosheet.py out/wip/paranoia_trial1.mp4 --t 8.50,8.52,8.54 --cols 6 --w 320 --name seams

Writes out/wip/vsheet/<name>_<k>.jpg, each tile labelled with its time.
"""
import argparse
import os

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def font(sz):
    p = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
    return ImageFont.truetype(p, sz) if os.path.exists(p) else ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('video')
    ap.add_argument('--step', type=float, default=0.5)
    ap.add_argument('--t', default='')
    ap.add_argument('--per', type=int, default=40)
    ap.add_argument('--cols', type=int, default=8)
    ap.add_argument('--w', type=int, default=240)
    ap.add_argument('--name', default='full')
    a = ap.parse_args()
    c = av.open(os.path.join(ROOT, a.video))
    vs = c.streams.video[0]
    vs.thread_type = 'AUTO'
    dur = float(c.duration / av.time_base)
    want = [float(x) for x in a.t.split(',')] if a.t else [round(k * a.step, 3) for k in range(int(dur / a.step) + 1)]
    want = sorted(t for t in want if t < dur)
    tb, st = float(vs.time_base), vs.start_time or 0
    got = {}
    wi = 0
    for f in c.decode(vs):
        t = (f.pts - st) * tb
        while wi < len(want) and t >= want[wi] - 1 / 120:
            got[want[wi]] = f.to_image().resize((a.w, a.w * 9 // 16), Image.BILINEAR)
            wi += 1
        if wi >= len(want):
            break
    os.makedirs(os.path.join(ROOT, 'out', 'wip', 'vsheet'), exist_ok=True)
    th = a.w * 9 // 16
    for k in range(0, len(want), a.per):
        chunk = want[k:k + a.per]
        rows = (len(chunk) + a.cols - 1) // a.cols
        S = Image.new('RGB', (a.cols * a.w, rows * th))
        for i, t in enumerate(chunk):
            im = got.get(t)
            if im is None:
                continue
            d = ImageDraw.Draw(im)
            f = font(max(10, a.w // 16))
            d.rectangle([0, 0, d.textlength(f'{t:.2f}', font=f) + 6, f.size + 4], fill=(0, 0, 0))
            d.text((3, 1), f'{t:.2f}', fill=(255, 255, 0), font=f)
            S.paste(im, ((i % a.cols) * a.w, (i // a.cols) * th))
        out = os.path.join(ROOT, 'out', 'wip', 'vsheet', f'{a.name}_{k // a.per + 1}.jpg')
        S.save(out, quality=85)
        print(out)


if __name__ == '__main__':
    main()
