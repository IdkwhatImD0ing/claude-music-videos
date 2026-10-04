"""Song timing for the montage, in VIDEO time.

Video time t runs 0..LENGTH; song time = t + SONG_START. Everything here is a pure function of t.

    from engine.song import song
    song.bpm, song.beat_len                    # tempo
    song.beats, song.downbeats                 # lists of video times (may start below 0 / end past LENGTH)
    song.beat(i)                               # video time of beat i (fractional i interpolates); beat 0 = first beat >= 0
    song.bar(b)                                # video time of downbeat b; bar 0 = first downbeat >= 0
    song.beat_index(t)                         # fractional beat number at t
    song.phase(t)                              # 0..1 position inside the current beat
    song.kicks, song.snares, song.hats         # [(t, strength 0..1)]
    song.pulse(t, 'kick', decay=0.12)          # 0..1 envelope: jumps to the onset strength, decays exponentially
    song.onsets('snare', t0, t1, min_s=0.3)    # onset times in [t0, t1)
    song.env('drums', t)                       # 100 fps normalised envelopes: mix low mid high drums bass vocals other
    song.words_like('paranoia')                # sung words matching, [(t0, t1, word)]
"""
import bisect
import json
import math
import os

from .config import SONG_START, LENGTH, GRID_FIX

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Song:
    def __init__(self, path=os.path.join(ROOT, 'data', 'audio.json'), start=SONG_START, length=LENGTH):
        with open(path) as fh:
            d = json.load(fh)
        self.start, self.length = start, length
        self.bpm = d['bpm']
        for a, b, n in GRID_FIX:   # replace a glitched stretch of the grid with even beats
            d['beats'] = sorted([x for x in d['beats'] if not a - 0.05 < x < b + 0.05]
                                + [a + (b - a) * k / n for k in range(n + 1)])
            d['downbeats'] = sorted([x for x in d['downbeats'] if not a - 0.05 < x < b + 0.05]
                                    + [a + (b - a) * k / n for k in range(0, n + 1, 4)])
        self.beat_len = 60.0 / self.bpm
        sh = lambda xs: [x - start for x in xs]
        self.all_beats = sh(d['beats'])
        self.all_downbeats = sh(d['downbeats'])
        self.beats = self.all_beats
        self.downbeats = self.all_downbeats
        self._b0 = bisect.bisect_left(self.all_beats, -1e-6)
        self._d0 = bisect.bisect_left(self.all_downbeats, -1e-6)
        self.kicks = [(t - start, s) for t, s in d['kicks']]
        self.snares = [(t - start, s) for t, s in d['snares']]
        self.hats = [(t - start, s) for t, s in d['hats']]
        self.vocal_onsets = [(t - start, s) for t, s in d.get('vocal_onsets', [])]
        self._ons = {'kick': self.kicks, 'snare': self.snares, 'hat': self.hats, 'vocal': self.vocal_onsets}
        self._ont = {k: [t for t, _ in v] for k, v in self._ons.items()}
        self.env_fps = d['env_fps']
        self._env = d['env']
        self.words = [(w['t0'] - start, w['t1'] - start, w['w']) for w in d.get('words', [])]

    # --- grid -----------------------------------------------------------------------------------------------
    def beat(self, i):
        """Video time of beat i (beat 0 = first beat at or after t=0). Fractional i interpolates."""
        k = self._b0 + i
        lo = math.floor(k)
        f = k - lo
        bt = self.all_beats
        if lo < 0:
            return bt[0] + (k) * self.beat_len
        if lo + 1 >= len(bt):
            return bt[-1] + (k - (len(bt) - 1)) * self.beat_len
        return bt[lo] + f * (bt[lo + 1] - bt[lo])

    def bar(self, b):
        k = self._d0 + b
        lo = math.floor(k)
        f = k - lo
        db = self.all_downbeats
        if lo < 0:
            return db[0] + k * 4 * self.beat_len
        if lo + 1 >= len(db):
            return db[-1] + (k - (len(db) - 1)) * 4 * self.beat_len
        return db[lo] + f * (db[lo + 1] - db[lo])

    def beat_index(self, t):
        bt = self.all_beats
        j = bisect.bisect_right(bt, t) - 1
        if j < 0:
            return (t - bt[0]) / self.beat_len - self._b0
        if j + 1 >= len(bt):
            return (len(bt) - 1 - self._b0) + (t - bt[-1]) / self.beat_len
        return j - self._b0 + (t - bt[j]) / (bt[j + 1] - bt[j])

    def phase(self, t):
        x = self.beat_index(t)
        return x - math.floor(x)

    def nearest_beat(self, t, sub=1):
        """Video time of the nearest beat (sub=2: nearest half beat)."""
        x = self.beat_index(t) * sub
        return self.beat(round(x) / sub)

    # --- onsets ---------------------------------------------------------------------------------------------
    def onsets(self, kind, t0, t1, min_s=0.0):
        ts = self._ont[kind]
        i, j = bisect.bisect_left(ts, t0), bisect.bisect_left(ts, t1)
        return [t for t, s in self._ons[kind][i:j] if s >= min_s]

    def onsets_s(self, kind, t0, t1, min_s=0.0):
        ts = self._ont[kind]
        i, j = bisect.bisect_left(ts, t0), bisect.bisect_left(ts, t1)
        return [(t, s) for t, s in self._ons[kind][i:j] if s >= min_s]

    def pulse(self, t, kind='kick', decay=0.12, min_s=0.0, attack=0.0):
        """Envelope that jumps to an onset's strength and decays exponentially (largest recent onset wins)."""
        ts = self._ont[kind]
        j = bisect.bisect_right(ts, t + attack)
        best = 0.0
        for k in range(j - 1, max(-1, j - 8), -1):
            tk, s = self._ons[kind][k]
            if s < min_s:
                continue
            dt = t - tk
            if dt > decay * 6:
                break
            if dt < 0:
                v = s * max(0.0, 1 + dt / attack) if attack > 0 else 0.0
            else:
                v = s * math.exp(-dt / decay)
            best = max(best, v)
        return best

    def env(self, name, t):
        e = self._env[name]
        x = (t + self.start) * self.env_fps
        i = int(math.floor(x))
        if i < 0:
            return e[0]
        if i + 1 >= len(e):
            return e[-1]
        f = x - i
        return e[i] * (1 - f) + e[i + 1] * f

    def words_like(self, sub):
        sub = sub.lower()
        return [w for w in self.words if sub in w[2].lower()]


_song = None


def get():
    global _song
    if _song is None:
        _song = Song()
    return _song


class _Lazy:
    def __getattr__(self, k):
        return getattr(get(), k)


song = _Lazy()
