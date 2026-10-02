"""Song timing for the Blender video: beats, bars, lyric words, and the song-time <-> frame mapping.

Every frame of the video is a pure function of song time. Global frame f shows song time f / FPS; a scene's .blend
uses global frame numbers, so a keyframe put at time t lands on the same frame in every scene and in the final cut.
Pure Python (no bpy), so the outer tools can import it too.
"""
from __future__ import annotations

import json
import math
import os
import re
from functools import lru_cache

FPS = 24
# The OUTPUT frame rate the scene is built for (env PDOOM_FPS, read at build time). 24 (default) builds the stop-motion
# look of the trials: puppets on twos, CONSTANT keys. The production render (60 fps, the user: "Smooth everywhere")
# builds with PDOOM_FPS=60: puppets and per-frame props are sampled on the 60 fps grid (every 0.4 scene frames) with
# LINEAR keys, so everything moves on every output frame. Scene frames stay 24 fps either way (keys are in 24 fps frames).
OUT_FPS = int(os.environ.get('PDOOM_FPS', '24'))
SMOOTH = OUT_FPS != FPS
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))  # the repository root
DATA = os.path.join(ROOT, 'data')
DURATION = 156.651


def t2f(t: float) -> int:
    """Song time -> the global frame that shows it (nearest)."""
    return int(round(t * FPS))


def f2t(f: float) -> float:
    return f / FPS


def switch_frame(f: float) -> float:
    """Where a step (a visibility switch, a teleport, any CONSTANT change) that takes effect from 24 fps frame
    ceil(f) goes when rendering at another rate: 0.1 frame before that frame. Camera cuts are timeline markers on
    whole frames, and the 60 fps exposures (shutter +-0.09 around k * 0.4) never cover ceil(f) - 0.1, so every step
    lands between two exposures on the same side of the cut as at 24 fps."""
    return math.ceil(f - 1e-6) - 0.1


def out_frames(f0: float, f1: float) -> list[float]:
    """Scene frames (fractional) of every OUTPUT frame in [f0, f1]: k * FPS / OUT_FPS. At 24 fps these are whole frames."""
    lo = math.ceil(f0 * OUT_FPS / FPS - 1e-9)
    hi = math.floor(f1 * OUT_FPS / FPS + 1e-9)
    return [k * FPS / OUT_FPS for k in range(lo, hi + 1)]


@lru_cache(maxsize=None)
def audio() -> dict:
    with open(os.path.join(DATA, 'audio.json'), encoding='utf-8') as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def lyrics() -> list[dict]:
    with open(os.path.join(DATA, 'lyrics.json'), encoding='utf-8') as fh:
        return json.load(fh)['lines']


def beats() -> list[float]:
    return audio()['beats']


def downbeats() -> list[float]:
    return audio()['downbeats']


def beat_period() -> float:
    return audio()['beat_period']


def bar(k: int) -> float:
    """Downbeat of bar k (0-based over the downbeat list). Bar 13 is the first DOOM (23.873)."""
    return downbeats()[k]


def beat_after(t: float, n: int = 0) -> float:
    """The n-th beat at or after t (n = 0: the first one)."""
    b = beats()
    i = next((i for i, x in enumerate(b) if x >= t - 1e-6), len(b) - 1)
    return b[min(i + n, len(b) - 1)]


def beats_between(t0: float, t1: float) -> list[float]:
    return [x for x in beats() if t0 - 1e-6 <= x < t1 - 1e-6]


def kicks(t0: float = 0.0, t1: float = 1e9, min_strength: float = 0.0) -> list[float]:
    """Kick-drum onsets (seconds) in [t0, t1) with strength >= min_strength."""
    return [t for t, s in audio()['onsets'].get('kick', []) if t0 <= t < t1 and s >= min_strength]


def snares(t0: float = 0.0, t1: float = 1e9) -> list[float]:
    return [t for t, s in audio()['onsets'].get('snare', []) if t0 <= t < t1]


def envelope(name: str, t: float) -> float:
    """An audio envelope (rms low mid high vocal drums bass other), 0..1, sampled at 100 fps."""
    a = audio()
    arr = a[name]
    i = min(max(int(t * a['fps']), 0), len(arr) - 1)
    return arr[i]


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9()]", '', s.lower().replace('’', "'"))


def line(q) -> dict:
    """A lyric line by index or by a text fragment (case- and punctuation-insensitive)."""
    L = lyrics()
    if isinstance(q, int):
        return L[q]
    n = _norm(q)
    for ln in L:
        if n in _norm(ln['text']):
            return ln
    raise KeyError(f'no lyric line contains {q!r}')


def word(line_q, w) -> dict:
    """A word of a line, by index or by text (the first match): {'w', 'start', 'end', ...}."""
    ln = line(line_q)
    ws = ln['words']
    if isinstance(w, int):
        return ws[w]
    n = _norm(w)
    for x in ws:
        if _norm(x['w']) == n or _norm(x['w']).startswith(n):
            return x
    raise KeyError(f'no word {w!r} in line {ln["text"]!r}')


def syl(wd: dict, i: int) -> float:
    """Letter i of a spelled acronym (A-G-I, N-V-D-A...): its start, falling back to the word start."""
    s = wd.get('syl')
    if s and i < len(s):
        return s[i][0]
    return wd['start']


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def smooth(t: float, t0: float, t1: float) -> float:
    return ease((t - t0) / (t1 - t0)) if t1 > t0 else float(t >= t1)


def pulse(t: float, hits: list[float], half_life: float = 0.12) -> float:
    """Sum of exponential decays from each hit at or before t (a beat envelope), capped at 1."""
    k = 0.0
    for h in hits:
        if h <= t:
            k += math.exp(-(t - h) * math.log(2) / half_life)
    return min(k, 1.0)
