#!/usr/bin/env python3
"""Cut the in-game announcer's voice lines ("Quadra kill!", "Pentakill!", "Victory!") out of clips (cloud machine).

  python tools/announcer.py                 # every job below -> out/voice/*.wav + data/voice.json

For each job: decode the clip's Game track (never the Mic track) over a window, isolate the voice with Demucs
(htdemucs, vocals stem), transcribe it with faster-whisper (word timestamps), and save every announcer phrase as
its own WAV: starts at the voice onset (refined on the stem's energy), ends 0.45 s after the last word so the
announcer's own reverb tail stays. data/voice.json lists every line with its transcript, clip time and file, so
lines can be checked by text before anyone listens.
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
import soundfile as sf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from engine.audio import _decode_game_audio  # noqa: E402
from engine.config import CLIPS  # noqa: E402

SR = 48000
JOBS = [  # name, clip, window (clip seconds) around the user's own multikill banners
    ('kayn', 'League-of-Legends__2026-02-19__23-12-48.mp4', 41.0, 56.5),
    ('drop', 'League-of-Legends__2026-02-20__01-11-57.mp4', 51.5, 58.0),
    ('viego', 'League-of-Legends__2026-09-29__22-41-54.mp4', 45.0, 58.0),
    ('darius', 'League-of-Legends__2026-03-03__00-18-26.mp4', 54.0, 58.8),
    ('finale', 'League-of-Legends__2026-02-22__20-45-40.mp4', 19.0, 40.0),
]
PHRASE = re.compile(r'(double|triple|quadra|quadro|penta|pent|victory|ace|shut|legendary|unstoppable|godlike)')
PROMPT = ('Double kill. Triple kill. Quadra kill. Penta kill. Pentakill. Victory. Ace. Shut down. Legendary. '
          'An enemy has been slain. You have slain an enemy.')


def vocals(wav_in, outdir):
    subprocess.check_call([sys.executable, '-m', 'demucs', '-n', 'htdemucs', '--two-stems', 'vocals', '-o', outdir,
                           wav_in], stdout=subprocess.DEVNULL)
    stem = os.path.splitext(os.path.basename(wav_in))[0]
    return os.path.join(outdir, 'htdemucs', stem, 'vocals.wav')


def onset(x, sr, t_guess, search=0.2, thr_db=-30.0):
    """First 5 ms frame within +-search of t_guess whose level is within thr_db of the phrase peak."""
    m = x.mean(1) if x.ndim == 2 else x
    i0, i1 = max(0, int((t_guess - search) * sr)), min(len(m), int((t_guess + 1.2) * sr))
    hop = int(0.005 * sr)
    seg = m[i0:i1]
    rms = np.sqrt(np.convolve(seg ** 2, np.ones(hop) / hop, mode='same') + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    if len(db) == 0:
        return t_guess
    lim = db.max() + thr_db
    idx = int(np.argmax(db > lim))
    return (i0 + idx) / sr


def main():
    from faster_whisper import WhisperModel
    model = WhisperModel('large-v3', device='cuda', compute_type='float16')
    os.makedirs('out/voice/tmp', exist_ok=True)
    lines = []
    for name, clip, a, b in JOBS:
        audio, off = _decode_game_audio(os.path.join(CLIPS, clip), SR)
        i0, i1 = int((a - off) * SR), int((b - off) * SR)
        win = audio[max(0, i0):i1]
        raw = f'out/voice/tmp/{name}.wav'
        sf.write(raw, win, SR)
        voc_path = vocals(raw, 'out/voice/tmp')
        voc, vsr = sf.read(voc_path, always_2d=True)
        mono = voc.mean(1).astype(np.float32)
        if vsr != 16000:
            import soxr
            mono16 = soxr.resample(mono, vsr, 16000)
        else:
            mono16 = mono
        segs, _ = model.transcribe(mono16, language='en', word_timestamps=True, initial_prompt=PROMPT,
                                   vad_filter=False, beam_size=5, condition_on_previous_text=False)
        words = [(w.start, w.end, w.word.strip(), w.probability) for s in segs for w in (s.words or [])]
        print(f'== {name}: ' + ' | '.join(f'{a + w0:.2f} {txt}' for w0, w1, txt, p in words), flush=True)
        k = 0
        while k < len(words):
            w0, w1, txt, p = words[k]
            if PHRASE.search(txt.lower()):
                j = k
                if k + 1 < len(words) and 'kill' in words[k + 1][2].lower() and words[k + 1][0] - w1 < 0.5:
                    j = k + 1
                phrase = ' '.join(words[q][2] for q in range(k, j + 1)).strip(' .,!')
                w_start = w0
                if j > k and words[j][0] - w1 > 0.35:      # the first word is stranded far from "kill": likely a
                    w_start = words[j][0] - 0.7               # prompt-induced guess; the line is ~0.7 s before "kill"
                t_on = onset(voc, vsr, w_start)
                t_off = min(len(voc) / vsr, words[j][1] + 0.45)
                cut = voc[int(t_on * vsr):int(t_off * vsr)]
                f = int(0.004 * vsr)
                cut[:f] *= np.linspace(0, 1, f)[:, None]
                cut[-int(0.08 * vsr):] *= np.linspace(1, 0, int(0.08 * vsr))[:, None]
                peak = float(np.abs(cut).max())
                slug = re.sub(r'[^a-z]+', '', phrase.lower())[:16]
                out = f'out/voice/{name}_{slug}_{a + t_on:.2f}.wav'
                sf.write(out, cut / max(peak, 1e-6) * 0.9, vsr, subtype='PCM_24')
                # verify: transcribe the cut alone, with no prompt, and require the keyword back
                import soxr
                c16 = soxr.resample(cut.mean(1).astype(np.float32), vsr, 16000)
                vs, _ = model.transcribe(c16, language='en', vad_filter=False, beam_size=5,
                                         condition_on_previous_text=False)
                heard = ' '.join(x.text.strip() for x in vs).strip()
                key = PHRASE.search(phrase.lower()).group(1)[:4]
                ok = key in heard.lower().replace('quadro', 'quadra')
                lines.append({'job': name, 'clip': clip, 'phrase': phrase, 'heard': heard, 'ok': ok,
                              'clip_t': round(a + t_on, 3),
                              'dur': round(t_off - t_on, 3), 'prob': round(float(np.mean([words[q][3] for q in
                                                                                         range(k, j + 1)])), 3),
                              'peak_db': round(20 * np.log10(peak + 1e-9), 1), 'file': out})
                k = j + 1
            else:
                k += 1
    json.dump(lines, open('data/voice.json', 'w'), indent=1)
    for l in lines:
        print(f"{'OK ' if l['ok'] else 'BAD'} {l['job']:7s} {l['clip_t']:7.2f}  {l['phrase']:14s} heard '{l['heard']}' "
              f"p={l['prob']:.2f} {l['dur']:.2f}s  {l['file']}")


if __name__ == '__main__':
    main()
