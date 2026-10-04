#!/usr/bin/env python3
"""Close-up strips around kills, to pin each kill to its exact frame (runs on the cloud machine).

  python tools/killstrip.py --clip League-of-Legends__2026-02-20__01-11-57.mp4 --t 46.9,48.6 --xy 0.5,0.45
  python tools/killstrip.py --from-picks             # every kill listed in data/picks.json

Each kill gets out/wip/kills/<stem>_<t>.jpg: 30 frames from t-0.6 to t+0.4 s, one every 2 source frames (1/30 s),
cropped to a 1280x720 window around the action point (x, y as frame fractions; default centre) so health bars and
gold pop-ups are readable, labelled with the exact clip time of each frame.
"""
import argparse
import json
import os

import av
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = os.environ.get('LM_CLIPS', os.path.join(ROOT, 'clips'))


def font(sz):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def strip(clip, t, x=0.5, y=0.5, before=0.6, after=0.4, step=2, tile=(480, 270), cols=6):
    path = os.path.join(CLIPS, clip)
    c = av.open(path)
    vs = c.streams.video[0]
    vs.thread_type = 'AUTO'
    tb, st, fps = float(vs.time_base), vs.start_time or 0, float(vs.average_rate)
    W, H = vs.codec_context.width, vs.codec_context.height
    cw, ch = 1280, 720
    x0 = int(min(max(0, x * W - cw / 2), W - cw))
    y0 = int(min(max(0, y * H - ch / 2), H - ch))
    c.seek(int(max(0, t - before - 0.3) / tb) + st, stream=vs, backward=True)
    tiles = []
    k = 0
    for f in c.decode(vs):
        ft = (f.pts - st) * tb
        if ft < t - before - 0.5 / fps:
            continue
        if ft > t + after + 0.5 / fps:
            break
        if k % step == 0:
            im = f.to_image().crop((x0, y0, x0 + cw, y0 + ch)).resize(tile, Image.BILINEAR)
            d = ImageDraw.Draw(im)
            lab = f'{ft:.3f}'
            fo = font(20)
            d.rectangle([0, 0, d.textlength(lab, font=fo) + 8, 26], fill=(0, 0, 0))
            d.text((4, 2), lab, fill=(255, 255, 0) if abs(ft - t) < 0.5 / fps * step else (255, 255, 255), font=fo)
            tiles.append(im)
        k += 1
    c.close()
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * tile[0], rows * tile[1]))
    for i, im in enumerate(tiles):
        S.paste(im, ((i % cols) * tile[0], (i // cols) * tile[1]))
    out = os.path.join(ROOT, 'out', 'wip', 'kills', f'{os.path.splitext(clip)[0]}_{t:.2f}.jpg')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    S.save(out, quality=85)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--clip', default='')
    ap.add_argument('--t', default='')
    ap.add_argument('--xy', default='0.5,0.5', help='x,y or x1,y1;x2,y2 per kill')
    ap.add_argument('--from-picks', action='store_true')
    a = ap.parse_args()
    jobs = []
    if a.from_picks:
        for clip, ks in json.load(open(os.path.join(ROOT, 'data', 'picks.json'))).items():
            for k in ks:
                jobs.append((clip, k['t'], k.get('x', 0.5), k.get('y', 0.5)))
    else:
        ts = [float(v) for v in a.t.split(',')]
        xys = [tuple(map(float, p.split(','))) for p in a.xy.split(';')]
        for i, t in enumerate(ts):
            x, y = xys[min(i, len(xys) - 1)]
            jobs.append((a.clip, t, x, y))
    for clip, t, x, y in jobs:
        print(strip(clip, t, x, y), flush=True)


if __name__ == '__main__':
    main()
