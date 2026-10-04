#!/usr/bin/env python3
"""Drum pattern per 16th note for a range of bars (cloud machine): low (kick) / mid (snare) / high (hat) energy rise
at each 16th position, averaged over the bars. Prints a grid and writes data/pattern.json.

  python analysis/pattern.py --bars 59-68 --name chorus --bars2 52-55 --name2 build
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze import ROOT, band, load_mono, rms_env, stem  # noqa: E402


def grid(x, sr, beats, downbeats, b0, b1):
    out = {}
    bands = {'kick': (None, 120), 'snare': (180, 2500), 'hat': (7000, None)}
    for name, (lo, hi) in bands.items():
        y = band(x, sr, lo, hi)
        fps = 500
        e = 20 * np.log10(rms_env(y, sr, fps=fps, win_s=0.01) + 1e-6)
        lag = 8
        rise = np.concatenate([np.zeros(lag), np.maximum(0, e[lag:] - e[:-lag])])
        acc = np.zeros(16)
        n = 0
        for b in range(b0, b1 + 1):
            t0, t1 = downbeats[b], downbeats[b + 1]
            for k in range(16):
                t = t0 + (t1 - t0) * k / 16
                i = int(t * fps)
                acc[k] += rise[max(0, i - 25):i + 25].max()
            n += 1
        out[name] = (acc / max(1, n)).round(1).tolist()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sets', default='build:52-55,tension:56-58,chorus:59-68')
    a = ap.parse_args()
    d = json.load(open(os.path.join(ROOT, 'data', 'audio.json')))
    x, sr = load_mono(stem('drums'), 48000)   # 48 kHz: 500 fps divides it exactly
    res = {}
    for item in a.sets.split(','):
        name, rng = item.split(':')
        b0, b1 = map(int, rng.split('-'))
        g = grid(x, sr, d['beats'], d['downbeats'], b0, b1)
        res[name] = g
        print(f'== {name} (bars {b0}-{b1}); columns = 16ths, | = beat')
        for k, v in g.items():
            cells = ''.join(('|' if i % 4 == 0 else ' ') + f'{int(round(c)):2d}' for i, c in enumerate(v))
            print(f'{k:6s}{cells}')
    json.dump(res, open(os.path.join(ROOT, 'data', 'pattern.json'), 'w'))


if __name__ == '__main__':
    main()
