"""s90 VOICE: the game announcer's own lines ("Quadra kill!", "Pentakill!") on the kill callouts, whole video.

The lines are cut from the clips' Game tracks by tools/announcer.py (Demucs vocals + whisper, listed in
data/voice.json). Each starts 0.03 s after its hit so the punch lands first and the voice rides on it; the song
dips under every line (Mixer.voice duck_db), and the bigger lines get more slap-back echo. Adds no shots or pixels.
"""
import json
import os

from engine.api import *

SPAN = (0.0, LENGTH)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# One announcer line per kill streak, only at its peak (the on-screen counter does the counting; a "Quadra kill" a
# second before "Pentakill" would steal the climax). The three pentakills build up: Viego's quieter and drier, the
# drop's full, the finale's loudest with the longest echo and the deepest music dip.
# video t of the hit, announcer job, word, gain dB, echo level, echo repeats, room, duck dB
PLAN = [
    (13.633, 'kayn', 'quadra', -3.0, 0.22, 3, 0.18, -5.0),                  # s02 T_K4: Kayn's quadra, the top of his
                                                                            #     streak on screen; introduces the voice
    (33.228, 'drop', 'penta', 0.0, 0.38, 3, 0.18, -8.0),                    # s04 kill 5 (bar 11 16th 12): rings into
                                                                            #     the tape-stop at 33.495
    (song.beat(4 * 16 + 12 / 4), 'viego', 'penta', -3.0, 0.2, 2, 0.12, -6.0),  # s05 VP: Viego (bar 16 16th 12)
    (song.bar(20), 'finale', 'penta', 2.5, 0.55, 4, 0.26, -11.0),           # s06 T_PENTA (bar 20): the 7% HP penta
]


def _lines():
    p = os.path.join(ROOT, 'data', 'voice.json')
    return json.load(open(p)) if os.path.exists(p) else []


def pick(lines, job, word):
    """The job's own line for `word` (its clearest), else the same word from another clip (same announcer)."""
    lines = [l for l in lines if l.get('ok', True)]          # only lines that re-transcribed to the right words
    own = [l for l in lines if l['job'] == job and word in l['phrase'].lower().replace('quadro', 'quadra')]
    any_ = [l for l in lines if word in l['phrase'].lower().replace('quadro', 'quadra')]
    cands = own or any_
    return max(cands, key=lambda l: l['prob']) if cands else None


def build(E):
    lines = _lines()
    for t, job, word, gain, echo, repeats, room, duck in PLAN:
        l = pick(lines, job, word)
        if l is None:
            print(f'[s90] no "{word}" line for {job}; skipped', flush=True)
            continue
        E.voice(os.path.join(ROOT, l['file']), t + 0.03, gain_db=gain, echo=echo, echo_repeats=repeats, room=room,
                duck_db=duck)
