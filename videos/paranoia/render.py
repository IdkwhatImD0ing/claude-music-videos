#!/usr/bin/env python3
"""Render the montage (on the cloud machine: python tools/cloud/remote.py A run render.py ...).

  python render.py check                                         # shot list, coverage gaps, remap warnings
  python render.py stills --t 12.3,14 [--w 1920] --out out/wip/stills
  python render.py sheet --t 1,2,3,4 | --from 8 --to 12 --n 12  [--cols 4 --w 480] --out out/wip/s.jpg
  python render.py strip --from 30.0 --to 30.5 [--step 1 --cols 8 --w 320] --out out/wip/strip.jpg  # every frame
  python render.py video [--from 0 --to 60] [--w 1920 --fps 60] [--samples auto] --out out/wip/v.mp4
  python render.py audio --out out/wip/mix.wav

Options: --only s3,s4 loads only those sections; --samples N|auto (motion-blur sub-samples); --shutter 0.5;
--fast = 1 sample and no RIFE (layout checks). Sheets label each tile with t, shot and sample count.
"""
import argparse
import os
import subprocess
import sys
import time

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine import edit as ed            # noqa: E402
from engine.config import FPS, LENGTH, SHUTTER, SONG, SONG_START  # noqa: E402


def to_pil(img):
    a = (img.clamp(0, 1) * 255 + 0.5).to(torch.uint8).permute(1, 2, 0).cpu().numpy()
    return Image.fromarray(a)


def font(sz):
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/arialbd.ttf'):
        if os.path.exists(p):
            return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def times_arg(a):
    if a.t:
        return [float(x) for x in a.t.split(',')]
    if a.step:
        fps = a.fps
        i0, i1 = int(round(a.__dict__['from'] * fps)), int(round(a.to * fps))
        return [i / fps for i in range(i0, i1 + 1, a.step)]
    n = a.n
    return [a.__dict__['from'] + (a.to - a.__dict__['from']) * k / max(1, n - 1) for k in range(n)]


def render_t(E, t, a, W, H):
    fi = int(round(t * a.fps))
    samples = 1 if a.fast else a.samples
    if a.fast:
        for s in E.shots:
            s.interp = False
    img, n = E.frame(t, W, H, a.fps, samples if samples == 'auto' else int(samples), a.shutter, fi)
    return img, n


def label_of(E, t, n):
    s = E.shot_at(t)
    name = (getattr(s, 'section', '') + ':' + s.name[:24]) if s else '-'
    return f'{t:6.3f}s  {name}  x{n}'


def cmd_check(E, a):
    print(f'{len(E.shots)} shots, {len(E.layers)} layers, {len(E.transitions)} transitions, '
          f'{len(E.sfx_events)} sfx, {len(E.music_events)} music fx')
    last = 0.0
    for s in sorted(E.shots, key=lambda s: s.t0):
        if s.t0 > last + 1e-3:
            print(f'  GAP {last:.3f}-{s.t0:.3f}')
        w = s.remap.check() if hasattr(s.remap, 'check') else []
        s0, s1 = s.s(s.t0), s.s(s.t1 - 1e-3)
        bad = '' if (0 <= min(s0, s1) and max(s0, s1) <= s.clip.duration) else '  SOURCE OUT OF RANGE'
        print(f'  {s.t0:7.3f}-{s.t1:7.3f} {getattr(s, "section", ""):12s} {s.name[:40]:40s} src {s0:6.2f}->{s1:6.2f}'
              f'{bad} {"; ".join(w)}')
        last = max(last, s.t1)
    if last < LENGTH - 1e-3:
        print(f'  GAP {last:.3f}-{LENGTH:.3f}')


def cmd_stills(E, a):
    os.makedirs(a.out, exist_ok=True)
    for t in times_arg(a):
        img, n = render_t(E, t, a, a.w, a.w * 9 // 16)
        p = os.path.join(a.out, f't{t:07.3f}.png')
        to_pil(img).save(p)
        print(p, f'x{n}', flush=True)


def cmd_sheet(E, a):
    ts = times_arg(a)
    W = a.w
    H = W * 9 // 16
    RW = 1920 if not a.full else a.w
    tiles = []
    t0 = time.time()
    for t in ts:
        img, n = render_t(E, t, a, RW, RW * 9 // 16)
        im = to_pil(img).resize((W, H), Image.LANCZOS)
        d = ImageDraw.Draw(im)
        lab = label_of(E, t, n)
        f = font(max(11, W // 34))
        d.rectangle([0, 0, d.textlength(lab, font=f) + 8, f.size + 6], fill=(0, 0, 0))
        d.text((4, 2), lab, fill=(255, 255, 0), font=f)
        tiles.append(im)
    cols = a.cols
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new('RGB', (cols * W, rows * H), (0, 0, 0))
    for k, im in enumerate(tiles):
        S.paste(im, ((k % cols) * W, (k // cols) * H))
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    S.save(a.out, quality=88)
    print(a.out, f'{len(ts)} frames in {time.time() - t0:.1f}s', flush=True)


def build_audio(E, path, t_from=0.0, t_to=LENGTH):
    from engine.audio import Mixer
    from engine.config import CLIPS
    mx = Mixer(SONG, SONG_START, LENGTH)
    for s in E.shots:
        if not s.audio:
            continue
        mx.add_game(os.path.join(CLIPS, s.clip_name), s.t0, s.t1, lambda tt, s=s: s.remap.s(tt),
                    lambda tt, s=s: s.remap.speed(tt), gain_db=s.game_db, hits=s.hits)
    for kind, t, kw in E.sfx_events:
        mx.sfx(kind, t, **kw)
    for kind, t0, t1, kw in E.music_events:
        mx.music_fx(kind, t0, t1, **kw)
    for vpath, t, kw in E.voice_events:
        mx.voice(vpath, t, **kw)
    mx.write(path)
    return path


def cmd_audio(E, a):
    build_audio(E, a.out)
    print(a.out)


def cmd_video(E, a):
    W = a.w
    H = W * 9 // 16
    f0, f1 = int(round(a.__dict__['from'] * a.fps)), int(round(a.to * a.fps))
    os.makedirs(os.path.dirname(a.out) or '.', exist_ok=True)
    wav = None
    if not a.noaudio:
        wav = os.path.splitext(a.out)[0] + '.wav'
        build_audio(E, wav)
    enc = ['-c:v', 'libx264', '-preset', a.preset, '-crf', str(a.crf), '-pix_fmt', 'yuv420p']
    if a.nvenc:
        enc = ['-c:v', 'h264_nvenc', '-preset', 'p7', '-tune', 'hq', '-rc', 'constqp', '-qp', '17',
               '-spatial-aq', '1', '-temporal-aq', '1', '-pix_fmt', 'yuv420p']
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(a.fps), '-i', '-']
    if wav:
        cmd += ['-ss', f'{f0 / a.fps:.6f}', '-t', f'{(f1 - f0) / a.fps:.6f}', '-i', wav, '-c:a', 'aac', '-b:a', '256k']
    cmd += enc + ['-movflags', '+faststart', a.out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    t0 = time.time()
    tot = 0
    for i in range(f0, f1):
        t = i / a.fps
        img, n = render_t(E, t, a, W, H)
        tot += n
        p.stdin.write((img.clamp(0, 1) * 255 + 0.5).to(torch.uint8).permute(1, 2, 0).contiguous().cpu().numpy()
                      .tobytes())
        if (i - f0) % 60 == 0:
            el = time.time() - t0
            print(f'[video] frame {i} t={t:.2f} x{n}  {(i - f0 + 1) / max(el, 1e-3):.2f} fps', flush=True)
    p.stdin.close()
    p.wait()
    print(a.out, f'{f1 - f0} frames, avg {tot / max(1, f1 - f0):.1f} samples, {time.time() - t0:.0f}s', flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode')
    ap.add_argument('--t', default='')
    ap.add_argument('--from', type=float, default=0.0)
    ap.add_argument('--to', type=float, default=LENGTH)
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--step', type=int, default=0)
    ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--w', type=int, default=1920)
    ap.add_argument('--fps', type=int, default=FPS)
    ap.add_argument('--samples', default='auto')
    ap.add_argument('--shutter', type=float, default=SHUTTER)
    ap.add_argument('--only', default='')
    ap.add_argument('--out', default='out/wip/out.jpg')
    ap.add_argument('--fast', action='store_true')
    ap.add_argument('--full', action='store_true', help='sheet tiles rendered at --w instead of 1920')
    ap.add_argument('--crf', type=int, default=16)
    ap.add_argument('--preset', default='medium')
    ap.add_argument('--nvenc', action='store_true')
    ap.add_argument('--noaudio', action='store_true')
    a = ap.parse_args()
    if a.mode == 'strip' and not a.step:
        a.step = 1
    E = ed.build(a.only.split(',') if a.only else None)
    {'check': cmd_check, 'stills': cmd_stills, 'sheet': cmd_sheet, 'strip': cmd_sheet, 'video': cmd_video,
     'audio': cmd_audio}[a.mode](E, a)


if __name__ == '__main__':
    main()
