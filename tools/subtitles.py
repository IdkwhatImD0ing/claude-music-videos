"""Lyric subtitles for the Blender video as an ASS file (libass, burned in by ffmpeg in `render.py assemble`).

One line at a time, lower third, a warm cream serif with a soft dark outline; each word lights up as it is sung
(karaoke \\kf sweeps from the word-level alignment in data/lyrics.json).
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Lyric,Georgia,46,&H00B8E6FF,&H00C8D6DE,&H64100C0A,&H96000000,0,1,0,0,100,100,1,0,1,2.2,1.5,2,120,120,64,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f'{h}:{m:02d}:{s:05.2f}'


def write_ass(dest: str, *, lead: float = 0.15, hold: float = 0.35) -> None:
    with open(os.path.join(ROOT, 'data', 'lyrics.json'), encoding='utf-8') as fh:
        lines = json.load(fh)['lines']
    ev = []
    for i, ln in enumerate(lines):
        start = ln['start'] - lead
        nxt = lines[i + 1]['start'] - lead if i + 1 < len(lines) else ln['end'] + 2
        end = min(ln['end'] + hold, nxt - 0.02)
        parts = []
        cur = start
        for w in ln['words']:
            gap = w['start'] - cur
            if gap > 0.005:
                parts.append(f'{{\\k{round(gap * 100)}}}')
            dur = max(1, round((w['end'] - w['start']) * 100))
            parts.append(f"{{\\kf{dur}}}{w['w']} ")
            cur = w['end']
        text = ''.join(parts).rstrip()
        ev.append(f'Dialogue: 0,{ts(start)},{ts(end)},Lyric,,0,0,0,,{{\\fad(120,160)}}{text}')
    with open(dest, 'w', encoding='utf-8') as fh:
        fh.write(HEADER + '\n'.join(ev) + '\n')
