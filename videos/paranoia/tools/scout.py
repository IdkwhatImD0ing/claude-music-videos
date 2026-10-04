#!/usr/bin/env python3
"""Contact sheets for choosing clips, and a kill-frame estimate from the kill banner (runs on the cloud machine).

  python tools/scout.py                 # every candidate in data/catalog.json whose clip is uploaded
  python tools/scout.py --only a.mp4,b.mp4 --force

For each clip writes
  out/wip/scout/<stem>_a.jpg   overview: 16 frames from 4 s before the first kill of its best chain to 2 s after
                               the last, labelled with clip time; kill markers in red
  out/wip/scout/<stem>_b.jpg   one row per kill: 6 frames from 1.0 s before the marker to 0.25 s after
and data/scout/<stem>.json with banner_t per kill: the clip time (s) where the top-centre kill banner changes most
within -1.5..+1.0 s of the marker (League shows "DOUBLE KILL!" etc. there the moment the kill happens). It's an
estimate; check it on a strip before syncing a cut to it.
"""
import argparse
import concurrent.futures as cf
import json
import os

import av
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLIPS = os.environ.get('LM_CLIPS', os.path.join(ROOT, 'clips'))
BANNER = (1000, 90, 1560, 190)     # x0 y0 x1 y1 in 2560x1440 source pixels


def font(size):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def decode_times(path, want, band=None):
    """Frames nearest to each time in `want` (sorted), plus (t, banner diff) for times inside `band` windows."""
    c = av.open(path)
    vs = c.streams.video[0]
    vs.thread_type = 'AUTO'
    tb = float(vs.time_base)
    st = vs.start_time or 0
    fps = float(vs.average_rate)
    out = {}
    diffs = []
    t_first = min(want + [w[0] for w in (band or [])])
    c.seek(int(max(0, t_first - 0.5) / tb) + st, stream=vs, backward=True)
    prev = None
    wi = 0
    t_last = max(want + [w[1] for w in (band or [])])
    for f in c.decode(vs):
        t = (f.pts - st) * tb
        if t > t_last + 0.1:
            break
        need_img = wi < len(want) and t >= want[wi] - 0.5 / fps
        in_band = band and any(a <= t <= b for a, b in band)
        if not (need_img or in_band):
            continue
        arr = f.to_ndarray(format='rgb24')
        if in_band:
            x0, y0, x1, y1 = BANNER
            reg = arr[y0:y1:2, x0:x1:2].astype(np.int16)
            if prev is not None:
                diffs.append((round(t, 4), float(np.abs(reg - prev).mean())))
            prev = reg
        while wi < len(want) and t >= want[wi] - 0.5 / fps:
            out[want[wi]] = Image.fromarray(arr)
            wi += 1
    c.close()
    return out, diffs


def label(im, text, color=(255, 255, 255), size=22):
    d = ImageDraw.Draw(im)
    f = font(size)
    d.rectangle([0, 0, d.textlength(text, font=f) + 10, size + 8], fill=(0, 0, 0))
    d.text((5, 3), text, fill=color, font=f)


def sheet(tiles, cols, w, h):
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * w, rows * h), (10, 10, 10))
    for k, im in enumerate(tiles):
        S.paste(im, ((k % cols) * w, (k // cols) * h))
    return S


def scout(c, force=False):
    stem = os.path.splitext(c['file'])[0]
    path = os.path.join(CLIPS, c['file'])
    js = os.path.join(ROOT, 'data', 'scout', stem + '.json')
    if not os.path.exists(path):
        return None
    if os.path.exists(js) and not force:
        return stem
    L = c['length']
    chain = c['chain']
    kills = c['events']['kills']
    t0 = max(0.0, chain[0] - 4.0)
    t1 = min(L - 0.05, chain[-1] + 2.0)
    over = [round(t0 + (t1 - t0) * k / 15, 3) for k in range(16)]
    rows = []
    for kt in chain:
        rows.append([round(min(L - 0.05, max(0.0, kt + d)), 3) for d in (-1.0, -0.75, -0.5, -0.25, 0.0, 0.25)])
    want = sorted(set(over + [x for r in rows for x in r]))
    band = [(max(0, kt - 1.5), min(L, kt + 1.0)) for kt in chain]
    try:
        imgs, diffs = decode_times(path, want, band)
    except (av.error.InvalidDataError, KeyError, OSError) as e:   # e.g. a clip still uploading
        print('skip', c['file'], type(e).__name__, flush=True)
        return None
    # banner estimate per kill
    est = []
    for kt in chain:
        cand = [(t, d) for t, d in diffs if kt - 1.5 <= t <= kt + 1.0]
        bt = max(cand, key=lambda x: x[1]) if cand else (None, 0)
        est.append({'marker': kt, 'banner_t': bt[0], 'banner_diff': round(bt[1], 2)})
    tiles = []
    for t in over:
        im = imgs[t].resize((640, 360), Image.BILINEAR)
        near = [k for k in kills if abs(k - t) < (t1 - t0) / 30]
        label(im, f'{t:6.2f}s' + ('  KILL' if near else ''), (255, 80, 80) if near else (255, 255, 255))
        tiles.append(im)
    os.makedirs(os.path.join(ROOT, 'out', 'wip', 'scout'), exist_ok=True)
    sheet(tiles, 4, 640, 360).save(os.path.join(ROOT, 'out', 'wip', 'scout', stem + '_a.jpg'), quality=82)
    tiles = []
    for r, kt, e in zip(rows, chain, est):
        for t in r:
            im = imgs[t].resize((427, 240), Image.BILINEAR)
            mark = abs(t - kt) < 1e-3
            bt = e['banner_t']
            lab = f'{t:6.2f}' + (' MARK' if mark else '') + (' BANNER' if bt and abs(t - bt) < 0.13 else '')
            label(im, lab, (255, 80, 80) if mark else (255, 255, 255), size=18)
            tiles.append(im)
    sheet(tiles, 6, 427, 240).save(os.path.join(ROOT, 'out', 'wip', 'scout', stem + '_b.jpg'), quality=82)
    os.makedirs(os.path.dirname(js), exist_ok=True)
    with open(js, 'w') as fh:
        json.dump({'file': c['file'], 'chain': chain, 'kills': est}, fh, indent=1)
    return stem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--only', default='')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--workers', type=int, default=12)
    a = ap.parse_args()
    cands = json.load(open(os.path.join(ROOT, 'data', 'catalog.json')))['candidates']
    if a.only:
        keep = set(a.only.split(','))
        cands = [c for c in cands if c['file'] in keep]
    done = 0
    with cf.ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(scout, cands, [a.force] * len(cands)):
            if r:
                done += 1
    print(f'scouted {done} of {len(cands)} candidates')


if __name__ == '__main__':
    main()
