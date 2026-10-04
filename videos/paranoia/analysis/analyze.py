#!/usr/bin/env python3
"""Song analysis -> data/audio.json and a per-bar table (runs on the cloud machine; GPU for Demucs/whisper).

  python analysis/analyze.py                 # out/song/paranoia.wav
  python analysis/analyze.py --skip-stems    # reuse out/stems

Writes (all times in seconds of the full song):
  data/audio.json   bpm, beats, downbeats, kick/snare/hat onsets with strength 0..1, 100 fps envelopes
                    (mix, low, mid, high, drums, bass, vocals, other), per-bar stats, sung words
  data/bars.txt     one line per bar: energy of each stem, kicks/snares, words (for choosing the excerpt)
  out/wip/song.png  energy strip with bar numbers
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf
from scipy.signal import butter, find_peaks, sosfiltfilt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SONG = os.path.join(ROOT, 'out', 'song', 'paranoia.wav')
STEMS = os.path.join(ROOT, 'out', 'stems')
FPS = 100


def load_mono(path, sr=None):
    x, r = sf.read(path, always_2d=True)
    x = x.mean(axis=1).astype(np.float32)
    if sr and r != sr:
        import soxr
        x = soxr.resample(x, r, sr)
        r = sr
    return x, r


def band(x, sr, lo=None, hi=None, order=4):
    if lo and hi:
        sos = butter(order, [lo, hi], btype='band', fs=sr, output='sos')
    elif hi:
        sos = butter(order, hi, btype='low', fs=sr, output='sos')
    else:
        sos = butter(order, lo, btype='high', fs=sr, output='sos')
    return sosfiltfilt(sos, x).astype(np.float32)


def rms_env(x, sr, fps=FPS, win_s=0.03):
    hop = int(round(sr / fps))
    if abs(sr / hop - fps) > 1e-6:   # a rounded hop would drift every later time (0.35 s by 160 s at 44.1 kHz)
        raise ValueError(f'fps {fps} does not divide sample rate {sr}; resample first')
    win = max(hop, int(sr * win_s))
    pad = np.pad(x, (win // 2, win // 2))
    n = len(x) // hop
    sq = np.cumsum(np.concatenate([[0.0], pad.astype(np.float64) ** 2]))
    idx = np.arange(n) * hop
    e = np.sqrt(np.maximum(0, (sq[idx + win] - sq[idx]) / win))
    return e.astype(np.float32)


def smooth(e, fps=FPS, attack=0.01, release=0.12):
    a = np.exp(-1.0 / (attack * fps))
    r = np.exp(-1.0 / (release * fps))
    out = np.zeros_like(e)
    y = 0.0
    for i, v in enumerate(e):
        y = a * y + (1 - a) * v if v > y else r * y + (1 - r) * v
        out[i] = y
    return out


def norm01(e, pct=99.0):
    m = np.percentile(e, pct)
    return np.clip(e / (m + 1e-9), 0, 1)


def onsets(x, sr, lo, hi, min_gap=0.09, prom_db=6.0, hop_s=0.002):
    """Onsets of a band: rises of the log energy. Returns [(t, strength 0..1)]."""
    y = band(x, sr, lo, hi)
    fps = int(round(1 / hop_s))
    e = rms_env(y, sr, fps=fps, win_s=0.008)
    db = 20 * np.log10(e + 1e-6)
    # onset function: rise of energy over the last ~15 ms
    lag = max(1, int(0.015 * fps))
    rise = np.maximum(0, db[lag:] - db[:-lag])
    rise = np.concatenate([np.zeros(lag), rise])
    peaks, props = find_peaks(rise, height=prom_db, distance=int(min_gap * fps))
    out = []
    lvl = np.percentile(db, 98)
    for p in peaks:
        # level of the hit just after the rise
        seg = db[p:p + int(0.03 * fps)]
        pk = seg.max() if len(seg) else db[p]
        s = float(np.clip((pk - (lvl - 30)) / 30, 0, 1))
        out.append((round((p - lag * 0.5) / fps, 4), round(s, 3)))
    return [o for o in out if o[1] > 0.15]


def separate():
    if os.path.exists(os.path.join(STEMS, 'htdemucs', 'paranoia', 'vocals.wav')):
        return
    subprocess.check_call([sys.executable, '-m', 'demucs', '-n', 'htdemucs', '-o', STEMS, SONG])


def stem(name):
    return os.path.join(STEMS, 'htdemucs', 'paranoia', name + '.wav')


def words_from_whisper():
    from faster_whisper import WhisperModel
    m = WhisperModel('large-v3', device='cuda', compute_type='float16')
    vox, _ = load_mono(stem('vocals'), 16000)   # (faster-whisper's own decoder breaks on new PyAV)
    segs, info = m.transcribe(vox, word_timestamps=True, vad_filter=False, beam_size=5,
                              condition_on_previous_text=False)
    out = []
    for s in segs:
        for w in s.words or []:
            out.append({'w': w.word.strip(), 't0': round(w.start, 3), 't1': round(w.end, 3),
                        'p': round(w.probability, 3)})
    return out, info.language


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--skip-stems', action='store_true')
    ap.add_argument('--no-words', action='store_true')
    a = ap.parse_args()
    if not a.skip_stems:
        separate()
    mix, sr = load_mono(SONG)
    dur = len(mix) / sr

    from beat_this.inference import File2Beats
    f2b = File2Beats(checkpoint_path='final0', device='cuda', dbn=False)
    beats, downbeats = f2b(SONG)
    beats = [round(float(b), 4) for b in beats]
    downbeats = [round(float(b), 4) for b in downbeats]
    ibi = np.diff(beats)
    bpm = 60.0 / float(np.median(ibi))

    st = {n: load_mono(stem(n), sr)[0] for n in ('drums', 'bass', 'vocals', 'other')}
    env = {
        'mix': norm01(smooth(rms_env(mix, sr))),
        'low': norm01(smooth(rms_env(band(mix, sr, hi=180), sr))),
        'mid': norm01(smooth(rms_env(band(mix, sr, 180, 3000), sr))),
        'high': norm01(smooth(rms_env(band(mix, sr, lo=5000), sr))),
    }
    for n, x in st.items():
        env[n] = norm01(smooth(rms_env(x, sr)))
    d = st['drums']
    kicks = onsets(d, sr, None, 140, min_gap=0.12, prom_db=9)
    snares = onsets(d, sr, 180, 2500, min_gap=0.10, prom_db=9)
    hats = onsets(d, sr, 7000, None, min_gap=0.06, prom_db=8)
    vox_on = onsets(st['vocals'], sr, 150, 4000, min_gap=0.12, prom_db=10)

    words, lang = ([], None) if a.no_words else words_from_whisper()

    # per-bar stats
    bars = []
    edges = downbeats + [dur]
    for i in range(len(downbeats)):
        t0, t1 = edges[i], edges[i + 1]
        i0, i1 = int(t0 * FPS), max(int(t0 * FPS) + 1, int(t1 * FPS))
        row = {'i': i, 't0': t0, 't1': round(t1, 4)}
        for n in ('mix', 'low', 'high', 'drums', 'bass', 'vocals', 'other'):
            row[n] = round(float(env[n][i0:i1].mean()), 3)
        row['kicks'] = sum(1 for t, s in kicks if t0 <= t < t1)
        row['snares'] = sum(1 for t, s in snares if t0 <= t < t1)
        row['words'] = ' '.join(w['w'] for w in words if t0 <= w['t0'] < t1)
        bars.append(row)

    doc = {'song': 'HEARTSTEEL - PARANOIA', 'duration': round(dur, 4), 'bpm': round(bpm, 3), 'beats': beats,
           'downbeats': downbeats, 'kicks': kicks, 'snares': snares, 'hats': hats, 'vocal_onsets': vox_on,
           'env_fps': FPS, 'env': {k: [round(float(v), 3) for v in e] for k, e in env.items()},
           'bars': bars, 'words': words, 'language': lang}
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    with open(os.path.join(ROOT, 'data', 'audio.json'), 'w') as fh:
        json.dump(doc, fh)
    with open(os.path.join(ROOT, 'data', 'bars.txt'), 'w') as fh:
        fh.write(f'bpm {bpm:.2f}  beats {len(beats)}  downbeats {len(downbeats)}  duration {dur:.2f}\n')
        fh.write('bar   time   mix  low  high drum bass voc  oth  K  S  words\n')
        for b in bars:
            fh.write(f"{b['i']:3d} {b['t0']:7.2f}  {b['mix']:.2f} {b['low']:.2f} {b['high']:.2f} {b['drums']:.2f} "
                     f"{b['bass']:.2f} {b['vocals']:.2f} {b['other']:.2f} {b['kicks']:2d} {b['snares']:2d}  "
                     f"{b['words'][:70]}\n")
    plot(doc)
    print(f'bpm {bpm:.2f}, {len(beats)} beats, {len(downbeats)} bars, {len(kicks)} kicks, {len(snares)} snares, '
          f'{len(words)} words ({lang})')


def plot(doc):
    from PIL import Image, ImageDraw
    W, rowh = 2400, 60
    names = ['mix', 'drums', 'bass', 'vocals', 'other', 'high']
    H = rowh * len(names) + 60
    im = Image.new('RGB', (W, H), (16, 16, 20))
    dr = ImageDraw.Draw(im)
    dur = doc['duration']
    X = lambda t: int(t / dur * (W - 1))
    for k, n in enumerate(names):
        e = np.array(doc['env'][n])
        y0 = 40 + k * rowh
        xs = np.linspace(0, len(e) - 1, W).astype(int)
        for x in range(W):
            v = e[xs[x]]
            dr.line([(x, y0 + rowh - 4), (x, y0 + rowh - 4 - int(v * (rowh - 8)))], fill=(90 + 30 * k, 160, 220 - 25 * k))
        dr.text((4, y0 + 2), n, fill=(255, 255, 255))
    for b in doc['bars']:
        x = X(b['t0'])
        dr.line([(x, 30), (x, H)], fill=(60, 60, 70))
        if b['i'] % 4 == 0:
            dr.text((x + 2, 4), f"{b['i']}", fill=(255, 220, 120))
            dr.text((x + 2, 16), f"{b['t0']:.0f}s", fill=(160, 160, 160))
    for w in doc['words']:
        if 'aranoi' in w['w'].lower():
            dr.line([(X(w['t0']), 30), (X(w['t0']), H)], fill=(255, 60, 60))
    os.makedirs(os.path.join(ROOT, 'out', 'wip'), exist_ok=True)
    im.save(os.path.join(ROOT, 'out', 'wip', 'song.png'))


if __name__ == '__main__':
    main()
