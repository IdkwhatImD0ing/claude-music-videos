"""Self-test for engine/audio.py.  Run:  python tools/audio_check.py

Builds a Mixer on a synthetic 20 s test song (written to the system temp dir at 44.1 kHz, so the
resampling path runs too), adds two fake game shots from a synthetic clip-audio array (slow-mo,
freeze, reverse and speed-up), triggers every sfx kind and every music_fx kind, renders, and checks:

  * no NaN / inf, right length, peak <= -1 dBFS
  * determinism: two renders of one Mixer and a render of a fresh Mixer are bit-identical
  * every sfx peaks within 20 ms of its t (riser/reverse: end at t), alone and in the sfx stem
  * sfx have no DC and start/end silent
  * tapestop is silent after the stop, stutter is periodic, music edits add no clicks or kinks
    (checked on a smooth sine pad, where any discontinuity stands out)
  * game audio: silent during the freeze, louder on kills, muffled in slow-mo

Light on purpose (a few seconds of CPU, no video decoding, no GPU). Exit code 1 if anything fails.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("league_audio", ROOT / "engine" / "audio.py")
audio = importlib.util.module_from_spec(_spec)
sys.modules["league_audio"] = audio
_spec.loader.exec_module(audio)

SR = 48000
OUT = Path(tempfile.gettempdir()) / "league_audio_check"
LENGTH = 16.0
SONG_START = 2.0

# sfx schedule (kind, t, kwargs); spaced so each one can be found alone in the sfx stem
SFX = [
    ("whoosh", 0.8, {"direction": "lr"}),
    ("whoosh", 1.6, {"direction": "rl"}),
    ("whoosh", 2.4, {"direction": "in"}),
    ("whoosh", 3.2, {"direction": "out"}),
    ("impact", 4.0, {}),
    ("boom", 5.0, {}),
    ("riser", 8.6, {}),
    ("reverse", 9.6, {}),
    ("subdrop", 10.0, {}),
    ("glitch", 11.2, {}),
    ("tick", 11.7, {}),
    ("heartbeat", 12.1, {"bpm": 120}),
    ("zap", 12.9, {}),
    ("shutter", 13.3, {}),
]
TAPE = (6.0, 7.4, 1.0)         # t0, t1, dur  -> stopped (silent) from 7.0 to 7.4
STUTTER = (8.0, 9.0, 0.125)
FREEZE = (4.6, 5.2)
HIT = 1.0                       # a kill in shot A, at normal speed
SLOWMO = (1.85, 2.75)           # shot A at 0.3x

results: list[bool] = []


def check(name, ok, detail=""):
    results.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f": {detail}" if detail else ""))


# ---------------------------------------------------------------------------------------------
# Synthetic inputs
# ---------------------------------------------------------------------------------------------

def make_song(path, sr=44100, dur=20.0, bpm=120.0):
    """Sine chord pad (Am F C G, 2 s each) + kick on beats + quiet hats on eighths."""
    rng = np.random.default_rng(1)
    n = int(dur * sr)
    t = np.arange(n) / sr
    y = np.zeros(n)
    chords = [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (261.63, 329.63, 392.0), (196.0, 246.94, 293.66)]
    for c in range(int(dur / 2)):
        a, b = int(c * 2 * sr), int((c + 1) * 2 * sr)
        env = np.ones(b - a)
        r = int(0.05 * sr)
        env[:r] = np.linspace(0, 1, r)
        env[-r:] = np.linspace(1, 0, r)
        for f in chords[c % 4]:
            y[a:b] += 0.16 * env * (np.sin(2 * np.pi * f * t[a:b]) + 0.3 * np.sin(4 * np.pi * f * t[a:b]))
    beat = 60.0 / bpm
    kl = int(0.25 * sr)
    kt = np.arange(kl) / sr
    kick = np.sin(2 * np.pi * np.cumsum(45 + 40 * np.exp(-kt / 0.03)) / sr) * np.exp(-kt / 0.08)
    kick *= np.minimum(1, kt / 0.002)
    hl = int(0.03 * sr)
    hat = rng.standard_normal(hl) * np.exp(-np.arange(hl) / (0.005 * sr)) * np.minimum(1, np.arange(hl) / 48)
    hat = np.diff(np.r_[0.0, hat])
    for k in range(int(dur / beat)):
        i = int(k * beat * sr)
        y[i:i + kl] += 0.5 * kick[:n - i]
        for j in (0, 1):
            ih = int((k + 0.5 * j) * beat * sr)
            y[ih:ih + hl] += 0.02 * hat[:max(0, n - ih)]
    y = 0.95 * y / np.max(np.abs(y))
    stereo = np.stack([y, np.roll(y, 7)], axis=1)
    sf.write(str(path), stereo, sr, subtype="PCM_24")


def make_pad(path, sr=SR, dur=20.0):
    """Smooth three-sine chord: any discontinuity an edit adds stands out against it."""
    t = np.arange(int(dur * sr)) / sr
    y = 0.3 * np.sin(2 * np.pi * 220 * t) + 0.25 * np.sin(2 * np.pi * 277.2 * t + 1) + 0.2 * np.sin(2 * np.pi * 329.6 * t + 2)
    sf.write(str(path), np.stack([y, y], axis=1), sr, subtype="FLOAT")


def make_game_audio(sr=SR, dur=30.0):
    """Fake game track: ambience bed, tonal ability blips and bright sizzles."""
    rng = np.random.default_rng(2)
    n = int(dur * sr)
    bed = np.cumsum(rng.standard_normal((n, 2)), axis=0)
    bed -= np.linspace(bed[0], bed[-1], n)
    bed = 0.05 * bed / np.max(np.abs(bed))
    y = bed + 0.03 * rng.standard_normal((n, 2))
    t = 0.0
    while t < dur - 0.2:
        i = int(t * sr)
        L = int(0.12 * sr)
        k = np.arange(L) / sr
        f = rng.uniform(400, 2000)
        blip = np.sin(2 * np.pi * f * k) * np.exp(-k / 0.04) * np.minimum(1, k / 0.002)
        y[i:i + L] += 0.3 * blip[:, None]
        sz = rng.standard_normal((L, 2))
        sz = np.diff(np.vstack([np.zeros((1, 2)), sz]), axis=0)
        y[i:i + L] += 0.12 * sz * np.exp(-k / 0.02)[:, None]
        t += rng.uniform(0.08, 0.2)
    return y / np.max(np.abs(y)) * 0.8


def remap(t0, t1, s0, knots):
    """Piecewise-linear speed knots [(t, v)] -> (src_of_t, speed_of_t), integrated from s0 at t0."""
    grid = np.arange(t0 - 0.05, t1 + 0.05, 1e-4)
    kt, kv = zip(*knots)
    v = np.interp(grid, kt, kv)
    s = np.concatenate([[0.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * np.diff(grid))])
    s += s0 - np.interp(t0, grid, s)
    return (lambda tt: np.interp(tt, grid, s)), (lambda tt: np.interp(tt, grid, v))


def build(song_path, clip):
    m = audio.Mixer(song_path, SONG_START, LENGTH)
    a_src, a_v = remap(0.3, 3.6, 5.0, [(0.3, 1), (1.6, 1), (1.8, 0.3), (2.8, 0.3), (3.0, 1), (3.6, 1)])
    m.add_game("fake_clip_a.mp4", 0.3, 3.6, a_src, a_v, hits=[HIT, 3.3], audio=clip)
    b_src, b_v = remap(3.6, 7.0, 12.0, [(3.6, 1), (4.6, 1), (4.601, 0), (5.2, 0), (5.201, 1), (5.6, 1),
                                         (5.601, -1), (5.9, -1), (5.901, 2.5), (7.0, 2.5)])
    m.add_game("fake_clip_b.mp4", 3.6, 7.0, b_src, b_v, hits=[4.2], audio=clip)
    for kind, t, kw in SFX:
        m.sfx(kind, t, **kw)
    add_music_fx(m)
    return m


def add_music_fx(m):
    """One of every music_fx kind (two lowpass styles), with one overlap."""
    m.music_fx("lowpass", 0.5, 2.5, cutoff_from=18000, cutoff_to=400)
    m.music_fx("duck", 3.8, 5.2, db=-10)
    m.music_fx("tapestop", TAPE[0], TAPE[1], dur=TAPE[2])
    m.music_fx("stutter", STUTTER[0], STUTTER[1], div=STUTTER[2])
    m.music_fx("reverse", 9.5, 10.5)
    m.music_fx("mute", 11.0, 11.4)
    m.music_fx("gain", 12.0, 13.0, db=-6)
    m.music_fx("lowpass", 13.0, 15.0, cutoff=lambda tt: 300.0 * 60.0 ** ((tt - 13.0) / 2.0))
    m.music_fx("gain", 14.0, 15.0, db=-3)          # overlaps the second lowpass


# ---------------------------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------------------------

def energy(y, win=0.020):
    """Short-time energy (both channels), centred moving average. 20 ms is about one cycle of a
    50 Hz sub; shorter windows judge sub-heavy hits by where a single sine crest happens to fall."""
    p = (np.asarray(y, dtype=np.float64) ** 2).sum(axis=1)
    w = max(1, int(win * SR))
    return np.convolve(p, np.ones(w) / w, mode="same")


def rms(x):
    return float(np.sqrt(np.mean(np.asarray(x, dtype=np.float64) ** 2)))


def hf_share(x, f_split):
    """Share of energy above f_split (Hann window, so strong lows don't leak into the highs)."""
    mono = np.asarray(x, dtype=np.float64).mean(axis=1)
    spec = np.abs(np.fft.rfft(mono * np.hanning(len(mono)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return float(spec[f > f_split].sum() / max(spec.sum(), 1e-20))


def sl(t0, t1):
    return slice(int(round(t0 * SR)), int(round(t1 * SR)))


def main():
    cpu0, wall0 = time.process_time(), time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    song_path = OUT / "test_song.wav"
    make_song(song_path)
    make_pad(OUT / "test_pad.wav")
    clip = make_game_audio()

    m = build(song_path, clip)
    y, stems = m.render(stems=True)
    y2 = m.render()
    y3, stems3 = build(song_path, clip).render(stems=True)
    peak = float(np.max(np.abs(y)))

    print(f"engine/audio.py check  (song {song_path}, {LENGTH:.0f} s mix)\n")
    check("finite", np.all(np.isfinite(y)) and all(np.all(np.isfinite(s)) for s in stems.values()))
    check("length", y.shape == (int(round(LENGTH * SR)), 2) and y.dtype == np.float32, f"{y.shape} {y.dtype}")
    check("peak <= -1 dBFS", peak <= 10 ** (-1 / 20), f"{20 * np.log10(peak):.2f} dBFS")
    check("deterministic", np.array_equal(y, y2) and np.array_equal(y, y3)
          and all(np.array_equal(stems[k], stems3[k]) for k in stems), "render twice + fresh Mixer: identical")

    # --- sfx alone: peak timing, DC, silent edges (3 seeds each) ---
    worst = {}
    for kind, _, kw in SFX:
        for seed in (0, 1, 2):
            s, anchor = audio.synth_sfx(kind, SR, seed, **kw)
            pk = float(np.max(np.abs(s)))
            e = energy(s)
            label = kind + (f"/{kw['direction']}" if "direction" in kw else "")
            if kind in audio._END_ANCHORED:
                off_ms = (anchor - int(np.argmax(e))) / SR * 1000      # how long before t the peak is
                ok_t = anchor == len(s) and 0 <= off_ms <= 20
            else:
                off_ms = (int(np.argmax(e)) - anchor) / SR * 1000
                ok_t = abs(off_ms) <= 20
            dc = abs(float(np.mean(s))) / pk
            edges = max(np.max(np.abs(s[:2])), np.max(np.abs(s[-2:]))) / pk
            prev = worst.get(label, (True, 0.0, 0.0, 0.0))
            worst[label] = (prev[0] and ok_t and dc < 0.01 and edges < 0.02,
                            max(prev[1], abs(off_ms)), max(prev[2], dc), max(prev[3], edges))
    for label, (ok, off, dc, edges) in worst.items():
        check(f"sfx {label:13s} alone", ok, f"peak {off:4.1f} ms from t, DC {dc:.4f}, edge level {edges:.4f}")

    # --- sfx in the stem ---
    fx = stems["sfx"]
    e = energy(fx)
    for kind, t, kw in SFX:
        if kind in audio._END_ANCHORED:
            w = sl(t - 0.3, t)
            off = (int(round(t * SR)) - (w.start + int(np.argmax(e[w])))) / SR * 1000
            after = float(np.max(np.abs(fx[sl(t + 0.002, t + 0.08)])))
            ok = 0 <= off <= 20 and after < 1e-3
            detail = f"peak {off:4.1f} ms before t, max after t {after:.1e}"
        else:
            w = sl(t - 0.1, t + 0.1)
            off = ((w.start + int(np.argmax(e[w]))) - int(round(t * SR))) / SR * 1000
            ok = abs(off) <= 20
            detail = f"peak {off:+5.1f} ms from t"
        check(f"sfx {kind:9s} at {t:5.2f}s in stem", ok, detail)

    # --- music fx ---
    mu = stems["music"]
    orig = m._song_segment()
    stop0, stop1 = TAPE[0] + TAPE[2], TAPE[1]
    silent = float(np.max(np.abs(mu[sl(stop0 + 0.002, stop1 - 0.010)])))
    resumed = rms(mu[sl(stop1 + 0.005, stop1 + 0.2)])
    check("tapestop silent after the stop", silent == 0.0 and resumed > 0.01,
          f"max {silent:.1e} in {stop0:.2f}-{stop1:.2f} s, resumes at rms {resumed:.3f}")
    i0, L = int(round(STUTTER[0] * SR)), int(round(STUTTER[2] * SR))
    reps = [mu[i0 + k * L:i0 + (k + 1) * L] for k in range(1, 6)]
    diff = max(float(np.max(np.abs(r - reps[0]))) for r in reps[1:])
    check("stutter periodic", diff < 1e-6 and rms(reps[0]) > 0.01, f"max diff between repeats {diff:.1e}")
    # clicks: the same effects on a smooth pad; a click or kink shows up as a spike in the
    # second difference of the waveform
    pad = audio.Mixer(OUT / "test_pad.wav", SONG_START, LENGTH)
    add_music_fx(pad)
    pmu = pad.render(stems=True)[1]["music"].astype(np.float64)
    d2 = lambda x: float(np.max(np.abs(np.diff(x, 2, axis=0))))     # noqa: E731
    ratio = d2(pmu) / d2(pad._song_segment())
    check("music edits click-free", ratio <= 1.5, f"sharpest kink {ratio:.2f}x the untouched pad's")
    lp = hf_share(mu[sl(2.2, 2.5)], 2000) / max(hf_share(orig[sl(2.2, 2.5)], 2000), 1e-12)
    check("lowpass sweep closes", lp < 0.05, f"energy above 2 kHz at the end of the sweep: x{lp:.4f}")

    # --- game audio ---
    gm = stems["game"]
    fz = float(np.max(np.abs(gm[sl(FREEZE[0] + 0.005, FREEZE[1] - 0.005)])))
    check("game silent during freeze", fz < 1e-4, f"max {fz:.1e}")
    boost = 20 * np.log10(rms(gm[sl(HIT + 0.01, HIT + 0.5)]) / rms(gm[sl(0.4, HIT - 0.05)]))
    check("game louder on the kill", boost > 5.0, f"{boost:+.1f} dB around the hit")
    hf_n, hf_s = hf_share(gm[sl(0.4, 0.95)], 1500), hf_share(gm[sl(*SLOWMO)], 1500)
    check("slow-mo muffled", hf_s < 0.02 and hf_n > 0.1, f"energy above 1.5 kHz: {hf_n:.1%} at 1x, {hf_s:.2%} at 0.3x")
    check("game stem bounded", float(np.max(np.abs(gm))) < 1.0, f"peak {np.max(np.abs(gm)):.3f}")

    out = m.write(OUT / "mix.wav", y)
    sf.write(str(OUT / "sfx_stem.wav"), stems["sfx"], SR, subtype="PCM_24")
    cpu, wall = time.process_time() - cpu0, time.perf_counter() - wall0
    print(f"\nwrote {out}\n      {OUT / 'sfx_stem.wav'}")
    print(f"{sum(results)}/{len(results)} checks passed in {wall:.1f} s ({cpu:.1f} s CPU)")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
