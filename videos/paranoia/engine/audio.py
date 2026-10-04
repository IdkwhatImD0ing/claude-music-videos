"""Deterministic soundtrack mixer for the League montage: music + game audio + procedural sfx.

Every output sample is a pure function of the calls made on the Mixer. There is no global random
state and no clock: noise comes from ``np.random.default_rng(seed)`` with the seed derived (CRC32)
from the event's own parameters, so re-rendering gives bit-identical output.
Output is 48 kHz stereo float32 with peaks <= -1 dBFS.

Layers
------
music   song[song_start : song_start + length] at 0 dB, with music_fx applied in the order added.
game    one entry per shot: audio stream 0 of the clip (the "Game" track; stream 1 is the player's
        microphone and is never read), varispeed-read through the shot's time remap, -15 dB default.
sfx     procedural sound effects (numpy/scipy synthesis, no sample files).
master  music + game + sfx -> start/end fades -> soft-knee look-ahead limiter (ceiling -1 dBFS).

API
---
    m = Mixer(song_path, song_start, length, sr=48000, fade_in=0.0, fade_out=0.6)
    m.add_game(clip_path, t0, t1, src_of_t, speed_of_t, gain_db=-15.0, hits=(), hit_boost_db=9.0,
               hit_len=0.55, lowpass_below=0.7, edge_fade=0.012)
    m.sfx(kind, t, gain_db=0.0, pan=0.0, **kw)
    m.music_fx(kind, t0, t1, **kw)
    y = m.render()                      # float32 [round(length*sr), 2]
    y, stems = m.render(stems=True)     # stems 'music', 'game', 'sfx': the buses before the master
    m.write("out/audio/mix.wav")        # 24-bit WAV
    y, anchor = synth_sfx(kind, sr=48000, seed=0, **kw)   # one effect alone; y[anchor] sits at t

All times are video time in seconds. add_game's src_of_t / speed_of_t map an array of video times
to clip source times / playback speeds (speed 0 = freeze frame, negative = reverse). speed_of_t may
be None, in which case speed is the derivative of src_of_t. Tests can pass ``audio=<array>`` (and
``audio_sr=``) to add_game instead of decoding the clip.

sfx kinds (t is the moment the sound lands on)
----------------------------------------------
whoosh    t = peak, dur=0.35, direction='lr'|'rl'|'in'|'out', bright=1.0. Swept band-passed noise.
impact    t = hit, strength=1.0. Sub thump + noise crack + boomy body.
boom      t = hit, dur=1.6. Cinematic boom: sub drop, transient, long reverb-like rumble.
riser     t = end, dur=2.0. Noise + saw/sine sweep climbing to t, stops dead at t.
reverse   t = end, dur=0.8. Reverse cymbal swelling into t.
subdrop   t = start, dur=1.0. Pure sine 90 -> 30 Hz.
glitch    t = start, dur=0.25. Bit-crushed, sample-and-hold stutter of tones/noise.
tick      t = click. UI tick.
heartbeat t = first beat, bpm=None. Lub-dub; with bpm the dub lands an eighth note later.
zap       t = start, dur=0.18. Falling FM laser with electric crackle.
shutter   t = first click. Camera click-clack.
Every kind also takes seed= (default: derived from kind, t and the other arguments).

music_fx kinds (act only inside [t0, t1); ramps sit inside the region)
------------------------------------------------------------------------
lowpass   cutoff_from=18000, cutoff_to=400 (exponential sweep) or cutoff=callable(t_array) -> Hz.
          Crossfades a bank of zero-phase filtered copies, so it is fast and click-free.
tapestop  dur=min(t1-t0, 1.0), curve=2.0: rate falls 1 -> 0 over dur (ease-in), silence until t1,
          then the song resumes at its normal position (the stop eats that stretch).
stutter   div=0.125 s (or slice=...), xfade=0.003, decay_db=0: repeat the slice at t0 until t1.
reverse   xfade=0.01: play [t0, t1) backwards.
mute      fade=0.01.        gain   db=-6, fade=0.01.        duck   db=-10, attack=0.08, release=0.3.
Effects may overlap; they are applied in the order they were added.
"""

from __future__ import annotations

import inspect
import math
import zlib
from pathlib import Path

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view
from scipy import signal
from scipy.ndimage import distance_transform_edt

SR = 48000
CONTROL_RATE = 1000          # Hz: time remaps are evaluated here, then interpolated to audio rate
FREEZE_SPEED = 0.02          # |speed| below this is a freeze frame: game audio goes silent
FREEZE_FADE = 0.030          # s, fade that ends where a freeze starts and starts where it ends

MUSIC_FX_KINDS = ("lowpass", "tapestop", "stutter", "reverse", "mute", "gain", "duck")


# ---------------------------------------------------------------------------------------------
# Small DSP helpers
# ---------------------------------------------------------------------------------------------

def _db(db):
    return 10.0 ** (np.asarray(db, dtype=np.float64) / 20.0)


def _smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _seed(*parts) -> int:
    """Stable 32-bit seed from parameters (Python's hash() is salted per process; CRC32 is not)."""
    return zlib.crc32(repr(parts).encode("utf-8"))


def _stereo(x):
    """Any [n] / [n, c] array -> float64 [n, 2]."""
    x = np.asarray(x, dtype=np.float64)
    if x.ndim == 1:
        x = x[:, None]
    if x.shape[1] == 1:
        x = np.repeat(x, 2, axis=1)
    return np.ascontiguousarray(x[:, :2])


def _resample(x, sr_from, sr_to):
    sr_from, sr_to = int(sr_from), int(sr_to)
    if sr_from == sr_to:
        return x
    g = math.gcd(sr_from, sr_to)
    return signal.resample_poly(x, sr_to // g, sr_from // g, axis=0)


def _sos(kind, fc, sr, order=2):
    """Butterworth sections. kind: 'low' | 'high' | 'band' (fc = (lo, hi))."""
    top = 0.95 * 0.5 * sr
    if kind == "band":
        lo, hi = fc
        return signal.butter(order, [max(lo, 1.0), min(hi, top)], btype="bandpass", fs=sr, output="sos")
    return signal.butter(order, min(fc, top), btype=kind, fs=sr, output="sos")


def _filt(sos, x):
    """Causal filter along time (axis 0)."""
    return signal.sosfilt(sos, x, axis=0)


def _filtfilt(sos, x):
    """Zero-phase filter along time. Copies made this way can be crossfaded without comb filtering."""
    if x.shape[0] < 2:
        return x.copy()
    return signal.sosfiltfilt(sos, x, axis=0, padlen=min(x.shape[0] - 1, 3 * (2 * len(sos) + 1)))


def _norm(x, peak=1.0):
    m = float(np.max(np.abs(x))) if x.size else 0.0
    return x * (peak / m) if m > 0 else x


def _sat(x, drive):
    """tanh soft saturation, scaled so full scale stays full scale. Adds harmonics that let low
    thumps survive on small speakers."""
    return np.tanh(drive * x) / math.tanh(drive)


def _ramp_in(m):
    """Raised cosine 0 -> 1 over m samples (endpoints excluded)."""
    return 0.5 - 0.5 * np.cos(np.pi * (np.arange(m) + 0.5) / m)


def _ep_curve(u):
    """Equal-power fade-in for u in [0, 1]: sin(pi/2 * smoothstep(u)). Its partner fade-out is
    _ep_curve(1 - u) (squares sum to 1); the smoothstep makes both start and end with zero slope,
    so even very short crossfades leave no kink (a faint tick) in the waveform."""
    return np.sin(0.5 * np.pi * _smoothstep(u))


def _ep_in(m):
    """Equal-power 0 -> 1 over m samples; its reverse is the matching fade-out.
    Use it to crossfade unrelated material (sum of squares stays 1)."""
    return _ep_curve((np.arange(m) + 0.5) / m)


def _region_env(n, a, r):
    """0 -> 1 over the first a samples, 1, then 1 -> 0 over the last r samples; shrunk to fit n."""
    a, r = max(int(a), 0), max(int(r), 0)
    if a + r > n:
        s = n / float(a + r)
        a, r = int(a * s), int(r * s)
    e = np.ones(n)
    if a:
        e[:a] = _ramp_in(a)
    if r:
        e[n - r:] *= _ramp_in(r)[::-1]
    return e


def _pan_gains(p):
    """Equal-power pan law, unity at centre: p = -1 hard left, +1 hard right."""
    ang = (np.clip(p, -1.0, 1.0) + 1.0) * (np.pi / 4)
    return np.cos(ang) * math.sqrt(2.0), np.sin(ang) * math.sqrt(2.0)


def _read_linear(src, pos):
    """src[pos] with linear interpolation, zero outside the array. src [N, C], pos float [M]."""
    n = src.shape[0]
    if n < 2:
        return np.zeros((len(pos), src.shape[1]))
    i = np.floor(pos).astype(np.int64)
    f = (pos - i)[:, None]
    ok = (i >= 0) & (i < n - 1)
    ic = np.clip(i, 0, n - 2)
    out = src[ic] * (1.0 - f) + src[ic + 1] * f
    out[~ok] = 0.0
    return out


def _xfade_weights(x, nodes):
    """Yield (k, w_k): piecewise-linear weights of values x over ascending nodes (they sum to 1)."""
    x = np.clip(x, nodes[0], nodes[-1])
    j = np.clip(np.searchsorted(nodes, x, side="right") - 1, 0, len(nodes) - 2)
    f = (x - nodes[j]) / (nodes[j + 1] - nodes[j])
    for k in range(len(nodes)):
        w = np.where(j == k, 1.0 - f, 0.0) + np.where(j + 1 == k, f, 0.0)
        if np.any(w > 1e-6):
            yield k, w


def _add_at(bus, y, start):
    """bus[start : start + len(y)] += y, clipped to the bus."""
    a, b = max(start, 0), min(start + len(y), len(bus))
    if b > a:
        bus[a:b] += y[a - start:b - start]


def _shaped_noise(rng, n, sr, mask, channels=3, nper=1024):
    """White noise coloured by a time-varying magnitude mask(f [F,1], t [1,T]) -> [F,T].
    Returns [n, channels]. Shaping in the STFT domain makes sweeping filters cheap and smooth."""
    hop = nper // 4
    x = rng.standard_normal((channels, n))
    f, tt, z = signal.stft(x, fs=sr, nperseg=nper, noverlap=nper - hop)
    z = z * mask(f[:, None], tt[None, :])
    _, y = signal.istft(z, fs=sr, nperseg=nper, noverlap=nper - hop)
    y = y[:, :n]
    if y.shape[1] < n:
        y = np.pad(y, ((0, 0), (0, n - y.shape[1])))
    return y.T


def _band(f, fc, octaves):
    """Gaussian bump on a log-frequency axis centred on fc; std dev in octaves."""
    return np.exp(-0.5 * (np.log2(np.maximum(f, 1.0) / fc) / octaves) ** 2)


def _width(c, l, r, width):
    """Stereo from three noise channels: width 0 = mono, 1 = independent L/R (may vary in time)."""
    th = np.asarray(width, dtype=np.float64) * (np.pi / 2)
    a, b = np.cos(th), np.sin(th)
    return np.stack([a * c + b * l, a * c + b * r], axis=1)


def _onset(x, pre):
    """Attack ramp from x = -pre to x = 0 (x: seconds relative to the anchor)."""
    return _smoothstep((x + pre) / pre)


def _tail(x, end, length):
    """1 until end - length, then a smooth fall to 0 at end."""
    return 1.0 - _smoothstep((x - (end - length)) / length)


def _sweep_phase(freq, sr):
    """Phase (radians) of an oscillator following freq (Hz per sample), 0 at the first sample."""
    return 2.0 * np.pi * np.concatenate([[0.0], np.cumsum(freq[:-1])]) / sr


# ---------------------------------------------------------------------------------------------
# Procedural sound effects. Each returns (y [n, 2] or [n], anchor): y[anchor] is time t.
# ---------------------------------------------------------------------------------------------

def _sfx_whoosh(sr, rng, dur=0.35, direction="lr", bright=1.0):
    """Fast swish: noise through a band that sweeps up to ~3 kHz at t and back down, with a sharp
    level peak at t. lr/rl pan across the stereo field; in/out swell or recede in the middle."""
    split = {"lr": 0.55, "rl": 0.55, "in": 0.75, "out": 0.30}   # share of dur before the peak
    if direction not in split:
        raise ValueError(f"whoosh direction must be one of {sorted(split)}")
    pre, post = dur * split[direction], dur * (1.0 - split[direction])
    n = int(round(dur * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    tau = np.clip(np.where(x < 0, x / pre, x / post), -1.0, 1.0)
    bell = np.cos(0.5 * np.pi * tau) ** 2
    env = bell * (0.3 + 0.7 * np.exp(-np.abs(x) / (0.09 * dur)))
    f_lo, f_hi = (200.0 if direction == "out" else 260.0), 3200.0 * bright
    fc = f_lo * (f_hi / f_lo) ** (bell ** 1.3)
    ts = np.arange(n) / sr

    def mask(f, t):
        c = np.interp(t, ts, fc)
        return _band(f, c, 0.55) + 0.35 * _band(f, 2.3 * c, 0.2) + 0.5 * _band(f, c / 3.5, 0.75)

    nz = _shaped_noise(rng, n, sr, mask)
    if direction in ("lr", "rl"):
        y = _width(nz[:, 0], nz[:, 1], nz[:, 2], 0.3)
        p = 0.85 * np.sin(0.5 * np.pi * tau) * (1.0 if direction == "lr" else -1.0)
        gl, gr = _pan_gains(p)
        y[:, 0] *= gl
        y[:, 1] *= gr
    else:
        y = _width(nz[:, 0], nz[:, 1], nz[:, 2], 0.2 + 0.6 * bell)
    return y * env[:, None], a


def _impact_layers(sr, rng, strength=1.0, length=None):
    """Layers of a hit, each peaking at the anchor: (sub, body, knock, crack [n, 2], anchor)."""
    s = float(np.clip(strength, 0.2, 3.0))
    pre = 0.002
    length = 0.40 + 0.15 * s if length is None else length
    n = int(round((pre + length) * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    xp = np.maximum(x, 0.0)
    att = _onset(x, pre)
    f = 38.0 + 17.0 * np.exp(-xp / 0.12) + 70.0 * np.exp(-xp / 0.007)
    sub = np.sin(_sweep_phase(f, sr)) * att * np.exp(-xp / (0.09 + 0.03 * s)) * _tail(x, 0.35 + 0.05 * s, 0.12)
    nz = rng.standard_normal((n, 4))
    body = _norm(_filt(_sos("low", 170, sr, 4), nz[:, 0])) * att * np.exp(-xp / 0.04) * _tail(x, 0.12, 0.05)
    knock = _norm(_filt(_sos("band", (160, 1200), sr, 2), nz[:, 1])) * att * np.exp(-xp / 0.014)
    crack_env = _onset(x, 0.0004) * np.exp(-xp / 0.0035) * _tail(x, 0.015, 0.006)
    crack = _norm(_filt(_sos("high", 2200, sr, 4), nz[:, 2:4])) * crack_env[:, None]
    return _norm(sub), body, knock, crack, a


def _sfx_impact(sr, rng, strength=1.0):
    """Layered hit: kick-like sub (punch, then 55 -> 38 Hz over 0.35 s), 15 ms high-passed noise
    crack, 120 ms low-passed noise body and a short mid knock, softly saturated together."""
    s = float(np.clip(strength, 0.2, 3.0))
    sub, body, knock, crack, a = _impact_layers(sr, rng, s)
    low = _sat(sub + 0.45 * body + 0.3 * knock, 1.2 + 0.3 * s)
    xp = np.maximum((np.arange(len(sub)) - a) / sr, 0.0)
    shaper = 0.65 + 0.35 * np.exp(-xp / 0.02)              # transient shaper: punch at t, then body
    return (low[:, None] + 0.4 * crack) * shaper[:, None], a


def _sfx_boom(sr, rng, dur=1.6):
    """Cinematic boom: sub drop (~100 -> 30 Hz), an impact transient, and a long low tail made by
    convolving the transient with darkening, decaying stereo noise (a synthetic big room)."""
    dur = max(float(dur), 0.3)
    pre = 0.003
    n = int(round((pre + dur) * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    xp = np.maximum(x, 0.0)
    end = _tail(x, dur, 0.3 * dur)
    f = 30.0 + 40.0 * np.exp(-xp / 0.25) + 60.0 * np.exp(-xp / 0.012)
    sub_env = 0.6 * np.exp(-xp / 0.045) + 0.4 * np.exp(-xp / (0.28 * dur))     # punch, then body
    sub = _norm(np.sin(_sweep_phase(f, sr)) * _onset(x, pre) * sub_env * end)
    _, body_s, knock_s, crack_s, ca = _impact_layers(sr, rng, 1.5, length=0.2)   # transient only
    body, knock, crack = np.zeros(n), np.zeros(n), np.zeros((n, 2))
    for dst, src in ((body, body_s), (knock, knock_s), (crack, crack_s)):
        _add_at(dst, src, a - ca)
    hit = 0.6 * body + 0.4 * knock + 0.5 * crack.mean(axis=1)               # what the "room" hears
    ti = np.arange(n) / sr
    irn = rng.standard_normal((n, 4))
    tau = dur / 6.0
    ir = (_filt(_sos("low", 1400, sr, 2), irn[:, :2]) * np.exp(-ti / (0.5 * tau))[:, None]
          + _filt(_sos("low", 260, sr, 2), irn[:, 2:]) * np.exp(-ti / tau)[:, None])
    ir *= _smoothstep(ti / 0.03)[:, None]                                       # tail swells in late
    wet = _norm(signal.fftconvolve(hit[:, None], ir, axes=0)[:n]) * end[:, None]

    def mask(f, t):
        return _band(f, 70.0 + 150.0 * np.exp(-t / (0.3 * dur)), 0.9)

    rum = _shaped_noise(rng, n, sr, mask)
    rum = _norm(_width(rum[:, 0], rum[:, 1], rum[:, 2], 0.7))
    rum *= (_smoothstep(xp / 0.08) * np.exp(-xp / (0.3 * dur)) * end)[:, None]
    dry = _sat(sub + 0.6 * body + 0.35 * knock, 1.1)
    shaper = 0.7 + 0.3 * np.exp(-xp / 0.025)              # transient shaper: the hit stands out
    return (dry[:, None] + 0.45 * crack + 0.35 * wet + 0.28 * rum) * shaper[:, None], a


def _sfx_riser(sr, rng, dur=2.0):
    """Build-up into t: a detuned saw pair sweeping 110 -> 880 Hz with its filter opening, an
    octave sine, and noise climbing 500 Hz -> 9 kHz; level rises exponentially with a speeding
    tremolo, and everything stops dead at t (3 ms anti-click)."""
    dur = max(float(dur), 0.1)
    n = int(round(dur * sr))
    k = np.arange(n)
    u = (k + 0.5) / n
    level = np.expm1(4.0 * u) / math.expm1(4.0)
    level *= _smoothstep(u * dur / 0.05) * _smoothstep((n - k) / (0.003 * sr))
    f0 = 110.0 * 2.0 ** (3.0 * u ** 1.4)
    cut = 700.0 * (14000.0 / 700.0) ** u
    tone = np.zeros((n, 2))
    for ch, det in enumerate((-0.0035, 0.0035)):            # ~6 cents apart: wide and chorused
        fr = f0 * (1.0 + det)
        ph = _sweep_phase(fr, sr)
        for h in range(1, 25):                               # band-limited additive saw
            fh = h * fr
            amp = np.exp(-fh / cut) * np.clip((0.45 * sr - fh) / 2000.0, 0.0, 1.0) / h
            tone[:, ch] += amp * np.sin(h * ph)
        tone[:, ch] += 0.5 * np.sin(2.0 * ph)               # sine an octave up

    def mask(f, t):
        uu = np.clip(t / dur, 0.0, 1.0)
        c = 500.0 * (9000.0 / 500.0) ** (uu ** 1.1)
        return _band(f, c, 0.9) + 0.25 * uu * _band(f, 11000.0, 0.5)

    nz = _shaped_noise(rng, n, sr, mask)
    noise = _width(nz[:, 0], nz[:, 1], nz[:, 2], 0.6)
    rate = 4.0 + 20.0 * u ** 2
    depth = 0.3 * u * np.clip((n - k) / (0.12 * sr), 0.0, 1.0)     # tremolo off for the last 120 ms
    trem = 1.0 - depth * (0.5 + 0.5 * np.sin(_sweep_phase(rate, sr)))
    y = (0.5 * _norm(tone) + 0.6 * _norm(noise)) * (level * trem)[:, None]
    return y, n


def _sfx_reverse(sr, rng, dur=0.8):
    """Reverse cymbal: a synthetic crash (inharmonic partials 2.5-15 kHz plus bright hiss, high
    partials dying first) played backwards, so it swells and brightens into t and ends dead."""
    dur = max(float(dur), 0.05)
    n = int(round(dur * sr))
    tf = np.arange(n) / sr                                   # time of the forward (unreversed) hit
    fwd = np.zeros((n, 2))
    for ch in range(2):
        fr = np.exp(rng.uniform(math.log(2500.0), math.log(15000.0), 36))
        amp = rng.uniform(0.4, 1.0, 36) * (2500.0 / fr) ** 0.3
        ph = rng.uniform(0.0, 2.0 * np.pi, 36)
        taus = 0.30 * dur * np.sqrt(3000.0 / fr)
        for f_, a_, p_, t_ in zip(fr, amp, ph, taus):
            fwd[:, ch] += a_ * np.sin(2.0 * np.pi * f_ * tf + p_) * np.exp(-tf / t_)

    def mask(f, t):
        return (_band(f, 6500.0, 0.7) * np.exp(-t / (0.30 * dur))
                + 0.6 * _band(f, 11000.0, 0.5) * np.exp(-t / (0.15 * dur)))

    nz = _shaped_noise(rng, n, sr, mask)
    hiss = _width(nz[:, 0], nz[:, 1], nz[:, 2], 0.8)
    fwd = 0.5 * _norm(fwd) + 0.7 * _norm(hiss)
    fwd *= (_smoothstep(tf / 0.0015) * _tail(tf, dur, 0.2 * dur))[:, None]
    return fwd[::-1].copy(), n


def _sfx_subdrop(sr, rng, dur=1.0):
    """Pure sine dropping 90 -> 30 Hz with an exponential decay (felt more than heard)."""
    dur = max(float(dur), 0.1)
    pre = 0.004
    n = int(round((pre + dur) * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    xp = np.maximum(x, 0.0)
    f = 30.0 + 60.0 * np.exp(-xp / (0.22 * dur))
    y = np.sin(_sweep_phase(f, sr)) * _onset(x, pre) * np.exp(-xp / (0.45 * dur)) * _tail(x, dur, 0.3 * dur)
    return y, a


def _sfx_glitch(sr, rng, dur=0.25):
    """Digital stutter: 8-30 ms slices of square tones, noise, gaps and repeats, each sample-and-
    held and bit-crushed by a random amount and scattered across the stereo field. The first slice
    is the loudest so the glitch hits at t."""
    n = max(int(round(dur * sr)), 16)
    y = np.zeros((n, 2))
    fade = max(int(0.001 * sr), 1)
    pos, j, prev = 0, 0, None
    while pos < n:
        L = int(rng.uniform(0.015 if j == 0 else 0.008, 0.03) * sr)
        L = max(min(L, n - pos), 1)
        kind = 0 if j == 0 else int(rng.choice(4, p=[0.35, 0.3, 0.12, 0.23]))
        k = np.arange(L)
        if kind == 0:                                        # square tone
            f = math.exp(rng.uniform(math.log(150.0), math.log(2500.0)))
            seg = np.where(np.sin(2.0 * np.pi * f * k / sr + 0.5) >= 0.0, 1.0, -1.0)
        elif kind == 1:                                      # noise
            seg = rng.uniform(-1.0, 1.0, L)
        elif kind == 2:                                      # gap
            seg = np.zeros(L)
        else:                                                # repeat the previous slice
            seg = np.resize(prev if prev is not None else rng.uniform(-1.0, 1.0, L), L)
        prev = seg.copy()
        hold = int(rng.choice([1, 2, 4, 8, 16]))             # sample-and-hold (crude downsample)
        seg = seg[(k // hold) * hold]
        q = 2.0 ** (int(rng.integers(3, 7)) - 1)             # 3-6 bit crush
        seg = np.round(seg * q) / q
        level = 1.0 if j == 0 else rng.uniform(0.45, 0.85) * (1.0 - 0.55 * pos / n)
        gl, gr = _pan_gains(0.0 if j == 0 else rng.uniform(-0.7, 0.7))
        w = _region_env(L, fade, fade) * level
        y[pos:pos + L, 0] = seg * w * gl
        y[pos:pos + L, 1] = seg * w * gr
        pos += L
        j += 1
    y *= (0.5 + 0.5 * np.exp(-np.arange(n) / (0.04 * sr)))[:, None]
    return y, 0


def _sfx_tick(sr, rng):
    """UI tick: a few millisecond-long bright resonances (1.5, 3.1, 5.3 kHz) and a noise click."""
    pre = 0.0003
    n = int(round(0.03 * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    xp = np.maximum(x, 0.0)
    y = (np.sin(2 * np.pi * 3100 * x) * np.exp(-xp / 0.0018)
         + 0.6 * np.sin(2 * np.pi * 5300 * x) * np.exp(-xp / 0.0009)
         + 0.4 * np.sin(2 * np.pi * 1500 * x) * np.exp(-xp / 0.004))
    click = _norm(_filt(_sos("high", 4000, sr, 2), rng.standard_normal(n))) * np.exp(-xp / 0.0005)
    return (y + 0.35 * click) * _onset(x, pre) * _tail(x, 0.03 - pre, 0.006), a


def _sfx_heartbeat(sr, rng, bpm=None):
    """Lub-dub: two saturated low thumps (48 Hz then a softer 56 Hz). With bpm (the song tempo)
    the dub lands an eighth note after the lub (folded into 0.16-0.42 s), else 0.27 s later."""
    gap = 0.27
    if bpm:
        gap = 30.0 / float(bpm)
        while gap > 0.42:
            gap /= 2.0
        while gap < 0.16:
            gap *= 2.0
    pre = 0.004
    n = int(round((pre + gap + 0.34) * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    nz = _norm(_filt(_sos("low", 140, sr, 2), rng.standard_normal(n)))

    def thump(x0, f0, amp):
        xx = x - x0
        xp = np.maximum(xx, 0.0)
        i0 = int(np.argmax(xx >= -pre))
        ph = np.zeros(n)
        ph[i0:] = _sweep_phase(f0 + 30.0 * np.exp(-xp[i0:] / 0.025), sr)
        env = _onset(xx, pre) * np.exp(-xp / 0.07) * _tail(xx, 0.30, 0.1)
        return amp * env * (np.sin(ph) + 0.3 * nz * np.exp(-xp / 0.03))

    y = thump(0.0, 48.0, 1.0) + thump(gap, 56.0, 0.7)
    return _sat(_norm(y), 2.2), a


def _sfx_zap(sr, rng, dur=0.18):
    """Laser / electric zap: FM tone whose carrier falls 2.7 kHz -> 150 Hz while the modulation
    index decays, L/R detuned for width, plus sparse band-passed crackle."""
    dur = max(float(dur), 0.03)
    pre = 0.0005
    n = int(round((pre + dur) * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    xp = np.maximum(x, 0.0)
    fc = 150.0 + 2600.0 * np.exp(-xp / (0.22 * dur))
    index = 1.0 + 5.0 * np.exp(-xp / (0.3 * dur))
    env = _onset(x, pre) * np.exp(-xp / (0.35 * dur)) * _tail(x, dur, 0.25 * dur)
    y = np.zeros((n, 2))
    for ch, det in enumerate((-0.012, 0.012)):
        f = fc * (1.0 + det)
        y[:, ch] = np.sin(_sweep_phase(f, sr) + index * np.sin(_sweep_phase(1.41 * f, sr)))
    sparks = (rng.random((n, 2)) < 0.004) * rng.uniform(-1.0, 1.0, (n, 2))
    crackle = _norm(_filt(_sos("band", (2000, 9000), sr, 2), sparks)) * np.exp(-xp / (0.5 * dur))[:, None]
    return (0.8 * y + 0.35 * crackle) * env[:, None], a


def _sfx_shutter(sr, rng):
    """Camera shutter: a bright metallic click at t, a duller clack 75 ms later, a faint whirr
    of mechanism between them."""
    pre = 0.0003
    total = 0.17
    n = int(round(total * sr))
    a = int(round(pre * sr))
    x = (np.arange(n) - a) / sr
    nz = rng.standard_normal((n, 6))

    def click(x0, modes, ring, band, nz_tau, amp, cols):
        xx = x - x0
        xp = np.maximum(xx, 0.0)
        tone = sum(np.sin(2 * np.pi * m * xx) * np.exp(-xp / ring) / math.sqrt(i + 1) for i, m in enumerate(modes))
        burst = _norm(_filt(_sos("band", band, sr, 2), nz[:, cols])) * np.exp(-xp / nz_tau)[:, None]
        return amp * _onset(xx, pre)[:, None] * (0.5 * tone[:, None] + burst)

    y = (click(0.0, (1850, 3700, 5300), 0.004, (2000, 12000), 0.0015, 1.0, [0, 1])
         + click(0.075, (950, 2300, 4100), 0.007, (700, 5000), 0.003, 0.65, [2, 3]))
    whirr = _norm(_filt(_sos("band", (3000, 7000), sr, 2), nz[:, 4:6]))
    whirr *= (0.06 * _smoothstep((x - 0.004) / 0.01) * (1.0 - _smoothstep((x - 0.06) / 0.012)))[:, None]
    return (y + whirr) * _tail(x, total - pre, 0.02)[:, None], a


# kind -> (synth, nominal peak). Nominal peaks are set so gain_db=0 sits well over a mastered song.
_SFX = {
    "whoosh": (_sfx_whoosh, 0.45),
    "impact": (_sfx_impact, 0.85),
    "boom": (_sfx_boom, 0.9),
    "riser": (_sfx_riser, 0.45),
    "reverse": (_sfx_reverse, 0.45),
    "subdrop": (_sfx_subdrop, 0.75),
    "glitch": (_sfx_glitch, 0.32),
    "tick": (_sfx_tick, 0.3),
    "heartbeat": (_sfx_heartbeat, 0.75),
    "zap": (_sfx_zap, 0.35),
    "shutter": (_sfx_shutter, 0.4),
}
SFX_KINDS = tuple(_SFX)
_END_ANCHORED = ("riser", "reverse")     # t is where these end rather than where they hit


def synth_sfx(kind, sr=SR, seed=0, **kw):
    """Synthesize one effect. Returns (y float64 [n, 2], anchor): y[anchor] is the effect's time t
    (anchor == len(y) for riser/reverse, which end at t). Peak level is the kind's nominal peak."""
    if kind not in _SFX:
        raise ValueError(f"unknown sfx kind {kind!r}; expected one of {SFX_KINDS}")
    fn, peak = _SFX[kind]
    y, anchor = fn(int(sr), np.random.default_rng(seed), **kw)
    y = _stereo(y)
    if kind not in _END_ANCHORED:                           # room for the DC filter to ring out
        y = np.pad(y, ((0, int(0.02 * sr)), (0, 0)))
    y = _filt(_sos("high", 20.0, sr, 2), y)                 # no DC, no subsonic rumble
    if kind not in _END_ANCHORED:
        f = int(0.005 * sr)
        y[-f:] *= _ramp_in(f)[::-1, None]
    if kind == "impact":
        peak *= float(np.clip(kw.get("strength", 1.0), 0.2, 3.0)) ** 0.5
    return _norm(y, peak), int(anchor)


# ---------------------------------------------------------------------------------------------
# Game audio decoding
# ---------------------------------------------------------------------------------------------

def _decode_game_audio(path, sr):
    """Decode audio stream 0 (the "Game" track) of a clip to float32 [n, 2] at sr.

    Returns (samples, offset): offset is the source time (seconds, measured from the first video
    frame) of samples[0]. Stream 1 is the player's microphone and is deliberately never opened.
    PyAV is imported here so the rest of the module works without it.
    """
    import av  # noqa: PLC0415  (lazy: only needed for real clips)

    chunks, first = [], None
    with av.open(str(path)) as c:
        st = c.streams.audio[0]
        vst = c.streams.video[0] if c.streams.video else None
        origin = 0.0
        if vst is not None and vst.start_time is not None:
            origin = float(vst.start_time * vst.time_base)
        rs = av.AudioResampler(format="fltp", layout="stereo", rate=sr)
        for frame in c.decode(st):
            if first is None and frame.pts is not None:
                first = float(frame.pts * frame.time_base)
            for f in rs.resample(frame):
                chunks.append(f.to_ndarray())
        for f in rs.resample(None):
            chunks.append(f.to_ndarray())
    if not chunks:
        return np.zeros((0, 2)), 0.0
    a = np.concatenate([ch.reshape(2, -1) for ch in chunks], axis=1).T.astype(np.float32)
    return np.ascontiguousarray(a), (first or 0.0) - origin


# ---------------------------------------------------------------------------------------------
# Master limiter
# ---------------------------------------------------------------------------------------------

def _limit(x, sr, ceiling_db=-1.0, knee_db=4.0, lookahead=0.003, release=0.15, block=32):
    """Soft-knee look-ahead peak limiter; output sample peaks stay below ceiling_db.

    Gain is computed per block of `block` samples from the block peak (dilated by one block on
    each side), through a soft-knee curve (infinite ratio). The gain-reduction curve is then
    min-held over the look-ahead window, released exponentially, and smoothed with a moving
    average of the same window. Min-hold over W followed by a W-wide average can never exceed the
    reduction a block needs, so the attack ramps in ahead of each peak instead of clipping it.
    """
    n = x.shape[0]
    if n == 0:
        return x
    thr = ceiling_db - 0.02
    peak = np.max(np.abs(x), axis=1)
    nb = -(-n // block)
    pk = np.zeros(nb * block)
    pk[:n] = peak
    bm = pk.reshape(nb, block).max(axis=1)
    bm = np.maximum(bm, np.maximum(np.r_[bm[1:], 0.0], np.r_[0.0, bm[:-1]]))
    over = 20.0 * np.log10(np.maximum(bm, 1e-9)) - thr
    half = knee_db / 2.0
    gr = np.where(over <= -half, 0.0, np.where(over >= half, -over, -((over + half) ** 2) / (2.0 * knee_db)))
    if not np.any(gr < 0):
        return x.copy()
    w = max(1, int(round(lookahead * sr / block)))
    held = sliding_window_view(np.r_[gr, np.zeros(w - 1)], w).min(axis=1)       # min of gr[j : j+w]
    coef = math.exp(-block / (release * sr))
    rel = np.empty(nb)
    g = 0.0
    for k, v in enumerate(held.tolist()):           # exponential recovery in dB
        g *= coef
        if v < g:
            g = v
        rel[k] = g
    padded = np.r_[np.full(w - 1, rel[0]), rel]
    cs = np.cumsum(np.r_[0.0, padded])
    smooth = (cs[w:] - cs[:-w]) / w                  # mean of rel[k-w+1 .. k]
    centres = np.arange(nb) * block + (block - 1) / 2.0
    gain = _db(np.interp(np.arange(n), centres, smooth))
    y = x * gain[:, None]
    ceil = float(_db(ceiling_db))
    m = float(np.max(np.abs(y)))
    if m > ceil:                                     # numerical safety net; normally unreachable
        y *= ceil / m
    return y


# ---------------------------------------------------------------------------------------------
# Mixer
# ---------------------------------------------------------------------------------------------

class Mixer:
    """Collects music, game-audio and sfx events, then renders them deterministically.

    Nothing is computed until render(); render() can be called any number of times and always
    returns the same samples. Decoded clip audio and the song are cached on the instance.
    """

    def __init__(self, song_path, song_start, length, sr=SR, fade_in=0.0, fade_out=0.6, ceiling_db=-1.0):
        self.song_path = song_path
        self.song_start = float(song_start)
        self.length = float(length)
        self.sr = int(sr)
        self.n = int(round(self.length * self.sr))
        self.fade_in = float(fade_in)
        self.fade_out = float(fade_out)
        self.ceiling_db = float(ceiling_db)
        self._shots: list[dict] = []
        self._sfx: list[tuple] = []
        self._mfx: list[tuple] = []
        self._voices: list[tuple] = []
        self._clip_cache: dict[str, tuple[np.ndarray, float]] = {}
        self._song: np.ndarray | None = None

    # ----- events ----------------------------------------------------------------------------

    def add_game(self, clip_path, t0, t1, src_of_t, speed_of_t, gain_db=-15.0, hits=(), hit_boost_db=9.0,
                 hit_len=0.55, lowpass_below=0.7, edge_fade=0.012, *, lowpass_hz=700.0, audio=None,
                 audio_sr=None):
        """Game audio of one shot, audible only in [t0, t1) with edge_fade ramps inside the shot.

        src_of_t(t_array) -> clip source seconds; speed_of_t(t_array) -> playback speed (or None to
        differentiate src_of_t). The clip is read at s(t) for every output sample, so pitch
        follows speed like tape. Below |speed| 0.02 (freeze) the audio fades out over 30 ms.
        hits: video times of kills; the game audio rises by hit_boost_db around each (10 ms attack,
        hit_len hold, 150 ms release). When |speed| < lowpass_below it crossfades, with speed, to a
        copy low-passed at lowpass_hz (muffled, heavy slow-mo). audio/audio_sr: test hook that
        replaces decoding clip_path with a given [n] or [n, 2] array.
        """
        if not float(t1) > float(t0):
            raise ValueError("add_game needs t1 > t0")
        shot = dict(path=clip_path, t0=float(t0), t1=float(t1), src_of_t=src_of_t, speed_of_t=speed_of_t,
                    gain_db=float(gain_db), hits=tuple(float(h) for h in hits), hit_boost_db=float(hit_boost_db),
                    hit_len=float(hit_len), lowpass_below=float(lowpass_below or 0.0),
                    edge_fade=float(edge_fade), lowpass_hz=float(lowpass_hz), audio=None)
        if audio is not None:
            arr = _stereo(audio)
            if audio_sr and int(audio_sr) != self.sr:
                arr = _resample(arr, audio_sr, self.sr)
            shot["audio"] = (np.ascontiguousarray(arr), 0.0)
        elif clip_path is None:
            raise ValueError("add_game needs clip_path or audio=")
        self._shots.append(shot)
        return self

    def sfx(self, kind, t, gain_db=0.0, pan=0.0, **kw):
        """Add a procedural sound effect at video time t (see the module docstring for kinds)."""
        if kind not in _SFX:
            raise ValueError(f"unknown sfx kind {kind!r}; expected one of {SFX_KINDS}")
        seed = kw.pop("seed", None)
        inspect.signature(_SFX[kind][0]).bind(self.sr, None, **kw)      # reject bad kwargs now
        if seed is None:
            seed = _seed("sfx", kind, int(round(float(t) * self.sr)), sorted(kw.items()))
        self._sfx.append((kind, float(t), float(gain_db), float(pan), int(seed), dict(kw)))
        return self

    def voice(self, path, t, gain_db=0.0, echo=0.3, echo_delay=0.14, echo_repeats=3, room=0.18, duck_db=-6.0,
              pan=0.0):
        """Play a recorded line (e.g. the game announcer's "Pentakill!") whose first sample lands at video time t.
        echo: level of a darkened slap-back echo (montage style); room: level of a short synthetic room tail;
        duck_db: the song dips by this much while the line plays (0 = no duck)."""
        import soundfile as sf  # noqa: PLC0415
        x, sr = sf.read(str(path), always_2d=True)
        x = _stereo(x.astype(np.float64))
        if int(sr) != self.sr:
            x = _resample(x, sr, self.sr)
        # trim leading near-silence so the first syllable lands on t: first 5 ms block within 24 dB of the loudest
        hop = max(1, int(0.005 * self.sr))
        nb = len(x) // hop
        if nb > 2:
            rms = np.sqrt((x[:nb * hop].mean(1).reshape(nb, hop) ** 2).mean(1))
            first = int(np.argmax(rms > rms.max() * _db(-24.0)))
            x = x[max(0, first * hop - int(0.01 * self.sr)):]
            x[:hop] *= _ramp_in(hop)[:, None]
        y = x.copy()
        if echo > 0:
            d = int(echo_delay * self.sr)
            dark = _filt(_sos("low", 2500.0, self.sr, 2), x)
            y = np.pad(y, ((0, d * echo_repeats), (0, 0)))
            for k in range(1, echo_repeats + 1):
                y[k * d:k * d + len(x)] += dark * (echo * (0.55 ** (k - 1)))
        if room > 0:
            rng = np.random.default_rng(_seed("room", str(path)))
            n = int(0.6 * self.sr)
            ir = rng.standard_normal((n, 2)) * np.exp(-np.arange(n) / (0.12 * self.sr))[:, None]
            ir = _filt(_sos("low", 4000.0, self.sr, 2), ir)
            ir /= np.sqrt((ir ** 2).sum(0, keepdims=True)) + 1e-9
            from scipy.signal import fftconvolve  # noqa: PLC0415
            wet = np.stack([fftconvolve(y[:, c], ir[:, c]) for c in range(2)], 1)   # len(y) + n - 1
            y = np.pad(y, ((0, n), (0, 0)))
            y[:len(wet)] += wet * room
        y = _norm(y, 0.9) * _db(gain_db)
        if pan:
            gl, gr = _pan_gains(pan)
            y[:, 0] *= gl
            y[:, 1] *= gr
        self._voices.append((float(t), y))
        if duck_db:
            self.music_fx('duck', max(0.0, t - 0.04), min(self.length, t + len(x) / self.sr + 0.1), db=float(duck_db),
                          attack=0.04, release=0.25)
        return self

    def music_fx(self, kind, t0, t1, **kw):
        """Apply an effect to the song inside [t0, t1) of video time (see the module docstring)."""
        if kind not in MUSIC_FX_KINDS:
            raise ValueError(f"unknown music_fx kind {kind!r}; expected one of {MUSIC_FX_KINDS}")
        if not float(t1) > float(t0):
            raise ValueError("music_fx needs t1 > t0")
        inspect.signature(getattr(self, "_fx_" + kind)).bind(None, t0, t1, **kw)
        self._mfx.append((kind, float(t0), float(t1), dict(kw)))
        return self

    # ----- rendering -------------------------------------------------------------------------

    def render(self, stems=False):
        """Mix everything. Returns float32 [n, 2]; with stems=True also {'music','game','sfx'}."""
        music = self._song_segment().copy()
        for kind, t0, t1, kw in self._mfx:
            getattr(self, "_fx_" + kind)(music, t0, t1, **kw)

        game = np.zeros((self.n, 2))
        for shot in self._shots:
            self._render_shot(game, shot)

        fx = np.zeros((self.n, 2))
        for kind, t, gain_db, pan, seed, kw in self._sfx:
            y, anchor = synth_sfx(kind, self.sr, seed, **kw)
            y *= _db(gain_db)
            if pan:
                gl, gr = _pan_gains(pan)
                y[:, 0] *= gl
                y[:, 1] *= gr
            _add_at(fx, y, int(round(t * self.sr)) - anchor)
        for t, y in self._voices:
            _add_at(fx, y, int(round(t * self.sr)))

        mix = (music + game + fx) * self._master_env()[:, None]
        out = _limit(mix, self.sr, self.ceiling_db).astype(np.float32)
        if stems:
            return out, {"music": music.astype(np.float32), "game": game.astype(np.float32),
                         "sfx": fx.astype(np.float32)}
        return out

    def write(self, path, audio=None):
        """Render (unless `audio` is given) and write a 24-bit WAV. Returns the path."""
        import soundfile as sf  # noqa: PLC0415

        y = self.render() if audio is None else audio
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(path), y, self.sr, subtype="PCM_24")
        return path

    # ----- internals -------------------------------------------------------------------------

    def _span(self, t0, t1):
        i0 = min(max(int(round(t0 * self.sr)), 0), self.n)
        i1 = min(max(int(round(t1 * self.sr)), 0), self.n)
        return i0, i1

    def _song_segment(self):
        """song[song_start : song_start + length] as float64 [n, 2] at self.sr (cached)."""
        if self._song is None:
            import soundfile as sf  # noqa: PLC0415

            info = sf.info(str(self.song_path))
            fsr = int(info.samplerate)
            start = int(math.floor(max(0.0, self.song_start - 0.05) * fsr))
            stop = min(info.frames, int(math.ceil((self.song_start + self.length + 0.05) * fsr)) + 1)
            seg = np.zeros((self.n, 2))
            if stop > start:
                data, _ = sf.read(str(self.song_path), start=start, stop=stop, dtype="float64", always_2d=True)
                data = _resample(_stereo(data), fsr, self.sr)
                k0 = int(round((self.song_start - start / fsr) * self.sr))     # data index at video t = 0
                lo, hi = max(0, -k0), min(self.n, data.shape[0] - k0)
                if hi > lo:
                    seg[lo:hi] = data[k0 + lo:k0 + hi]
            self._song = seg
        return self._song

    def _master_env(self):
        """Start/end fades of the whole mix (at least 5 ms, so the first/last sample is silent)."""
        n, sr = self.n, self.sr
        e = np.ones(n)
        fi = min(n, max(int(round(self.fade_in * sr)), int(0.005 * sr)))
        fo = min(n, max(int(round(self.fade_out * sr)), int(0.005 * sr)))
        if fi:
            e[:fi] *= _ramp_in(fi)
        if fo:
            e[n - fo:] *= _ramp_in(fo)[::-1]
        return e

    def _clip_audio(self, shot):
        if shot["audio"] is not None:
            return shot["audio"]
        key = str(Path(shot["path"]).resolve())
        if key not in self._clip_cache:
            self._clip_cache[key] = _decode_game_audio(key, self.sr)
        return self._clip_cache[key]

    def _render_shot(self, bus, shot):
        sr, cr = self.sr, CONTROL_RATE
        i0, i1 = self._span(shot["t0"], shot["t1"])
        if i1 - i0 < 2:
            return
        src, offset = self._clip_audio(shot)
        if src.shape[0] < 2:
            return

        # Time remap at the control rate, then interpolated to every output sample.
        tc = np.arange(math.floor(i0 / sr * cr) - 2, math.ceil(i1 / sr * cr) + 3) / cr
        sc = np.broadcast_to(np.asarray(shot["src_of_t"](tc), dtype=np.float64), tc.shape)
        if shot["speed_of_t"] is None:
            vc = np.gradient(sc, tc)
        else:
            vc = np.broadcast_to(np.asarray(shot["speed_of_t"](tc), dtype=np.float64), tc.shape)
        avc = np.abs(vc)
        t = np.arange(i0, i1) / sr
        pos = (np.interp(t, tc, sc) - offset) * sr
        av = np.interp(t, tc, avc)

        # Varispeed read. Above 1x the source is pre-filtered (crossfaded zero-phase copies) so
        # sped-up audio does not alias.
        pad = int(0.05 * sr)
        lo = max(0, int(np.floor(pos.min())) - pad)
        hi = min(src.shape[0], int(np.ceil(pos.max())) + pad + 2)
        y = np.zeros((i1 - i0, 2))
        if hi - lo >= 2:
            part = src[lo:hi].astype(np.float64)
            p = pos - lo
            speeds = np.array([1.0, 1.5, 2.2, 3.2, 4.6, 6.6])
            for k, w in _xfade_weights(np.log(np.clip(av, 1.0, speeds[-1])), np.log(speeds)):
                copy = part if k == 0 else _filtfilt(_sos("low", 0.46 * sr / speeds[k], sr, 3), part)
                y += _read_linear(copy, p) * w[:, None]

        # Slow-mo: crossfade (with speed) to a muffled, slightly louder low-passed copy.
        if shot["lowpass_below"] > 0:
            k = 15                                            # 15 ms smoothing of |speed|
            avs = np.convolve(np.pad(avc, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
            wl = _smoothstep((shot["lowpass_below"] - np.interp(t, tc, avs)) / (0.5 * shot["lowpass_below"]))
            if np.any(wl > 0):
                ylp = _filtfilt(_sos("low", shot["lowpass_hz"], sr, 2), y) * _db(2.0)
                y = y * (1.0 - wl)[:, None] + ylp * wl[:, None]
        y = _filtfilt(_sos("high", 25.0, sr, 2), y)          # no DC / rumble from near-frozen reads

        # Gain (applied last, so a freeze is exact silence): freezes, very slow speeds, kill hits, shot edges, shot level.
        g = np.full(i1 - i0, float(_db(shot["gain_db"])))
        frozen = avc < FREEZE_SPEED
        if frozen.any():
            dist = distance_transform_edt(~frozen) / cr       # seconds to the nearest frozen instant
            g *= np.interp(t, tc, _smoothstep(dist / FREEZE_FADE))
        g *= _smoothstep((av - FREEZE_SPEED) / 0.08)
        if shot["hits"]:
            eh = np.zeros(i1 - i0)
            for h in shot["hits"]:
                att = _smoothstep((t - (h - 0.010)) / 0.010)
                rel = 1.0 - _smoothstep((t - (h + shot["hit_len"])) / 0.150)
                eh = np.maximum(eh, att * rel)
            g *= _db(shot["hit_boost_db"] * eh)
        edge = int(round(shot["edge_fade"] * sr))
        g *= _region_env(i1 - i0, edge, edge)
        bus[i0:i1] += y * g[:, None]

    # ----- music effects (each edits the music buffer in place) ------------------------------

    def _fx_lowpass(self, buf, t0, t1, cutoff_from=18000.0, cutoff_to=400.0, cutoff=None, edge=0.005):
        i0, i1 = self._span(t0, t1)
        if i1 - i0 < 2:
            return
        sr = self.sr
        a, b = max(0, i0 - int(0.25 * sr)), min(self.n, i1 + int(0.25 * sr))   # filter warm-up margins
        seg = buf[a:b].copy()
        t = np.arange(i0, i1) / sr
        if cutoff is None:
            u = np.clip((t - t0) / (t1 - t0), 0.0, 1.0)
            fc = cutoff_from * (cutoff_to / cutoff_from) ** u
        else:
            fc = np.broadcast_to(np.asarray(cutoff(t), dtype=np.float64), t.shape)
        nodes_hz = np.r_[np.geomspace(60.0, 16000.0, 11), 20000.0]           # last node = unfiltered
        wet = np.zeros((i1 - i0, 2))
        for k, w in _xfade_weights(np.log(np.clip(fc, 60.0, 20000.0)), np.log(nodes_hz)):
            copy = seg if k == len(nodes_hz) - 1 else _filtfilt(_sos("low", nodes_hz[k], sr, 2), seg)
            wet += copy[i0 - a:i1 - a] * w[:, None]
        e = _region_env(i1 - i0, edge * sr, edge * sr)[:, None]
        buf[i0:i1] = buf[i0:i1] * (1.0 - e) + wet * e

    def _fx_tapestop(self, buf, t0, t1, dur=None, curve=2.0, edge=0.008):
        i0, i1 = self._span(t0, t1)
        if i1 - i0 < 2:
            return
        sr = self.sr
        dur = min(t1 - t0, 1.0) if dur is None else float(dur)
        L = max(int(round(dur * sr)), 1)
        m = min(L, i1 - i0)
        src = buf[i0:min(self.n, i0 + L + 2)].copy()
        x = int(min(round(edge * sr), i1 - i0))
        resume = buf[i1 - x:i1].copy() if (x and i1 < self.n) else None
        rate = 1.0 - (np.arange(m) / L) ** curve                       # ease-in: slow start, fast end
        pos = np.concatenate([[0.0], np.cumsum(rate[:-1])])            # samples of song consumed
        y = _read_linear(src, pos) * _smoothstep(rate / 0.3)[:, None]  # fade as it grinds to a halt
        buf[i0:i1] = 0.0
        buf[i0:i0 + m] = y
        if resume is not None:                                         # song back in at t1, no click
            buf[i1 - x:i1] += resume * _ramp_in(x)[:, None]

    def _fx_stutter(self, buf, t0, t1, div=0.125, slice=None, xfade=0.003, decay_db=0.0):  # noqa: A002
        i0, i1 = self._span(t0, t1)
        sr = self.sr
        L = max(int(round((div if slice is None else slice) * sr)), 2)
        if i1 - i0 <= L:
            return
        x = max(1, min(int(round(xfade * sr)), L // 2))
        src = buf[i0:min(self.n, i0 + 2 * L + x)].copy()
        if src.shape[0] < 2 * L + x:
            src = np.pad(src, ((0, 2 * L + x - src.shape[0]), (0, 0)))
        resume = buf[i1 - x:i1].copy() if i1 < self.n else None
        starts = list(range(i0, i1, L))
        if len(starts) > 1 and i1 - starts[-1] < 2 * x:               # no slivers: lengthen the previous
            starts.pop()
        if len(starts) < 2:
            return
        fin, fout = _ep_in(x), _ep_in(x)[::-1]
        out = np.zeros((i1 - i0, 2))
        for r, s in enumerate(starts):
            last = r == len(starts) - 1
            ln = (i1 - s) if last else (L + x)                        # run x past the next start
            piece = src[:ln].copy()
            if r > 0:
                piece[:x] *= fin[:, None]
            piece[ln - x:] *= fout[:, None]
            piece *= _db(decay_db * r)
            out[s - i0:s - i0 + ln] += piece[:i1 - s]
        if resume is not None:
            out[-x:] += resume * fin[:, None]
        buf[i0:i1] = out

    def _fx_reverse(self, buf, t0, t1, xfade=0.01):
        i0, i1 = self._span(t0, t1)
        if i1 - i0 < 4:
            return
        seg = buf[i0:i1].copy()
        x = max(1, min(int(round(xfade * self.sr)), (i1 - i0) // 2))
        r = np.ones(i1 - i0)
        r[:x] = (np.arange(x) + 0.5) / x
        r[-x:] = r[:x][::-1]
        wet, dry = _ep_curve(r), _ep_curve(1.0 - r)
        buf[i0:i1] = seg * dry[:, None] + seg[::-1] * wet[:, None]

    def _fx_mute(self, buf, t0, t1, fade=0.01):
        i0, i1 = self._span(t0, t1)
        f = fade * self.sr
        buf[i0:i1] *= (1.0 - _region_env(i1 - i0, f, f))[:, None]

    def _fx_gain(self, buf, t0, t1, db=-6.0, fade=0.01):
        i0, i1 = self._span(t0, t1)
        f = fade * self.sr
        buf[i0:i1] *= _db(db * _region_env(i1 - i0, f, f))[:, None]

    def _fx_duck(self, buf, t0, t1, db=-10.0, attack=0.08, release=0.3):
        i0, i1 = self._span(t0, t1)
        buf[i0:i1] *= _db(db * _region_env(i1 - i0, attack * self.sr, release * self.sr))[:, None]
