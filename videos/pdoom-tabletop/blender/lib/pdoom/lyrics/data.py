"""Lyric data for the in-picture lyrics: words, per-letter reveal times, rows, and which scene shows which line.

Pure Python (no bpy): the timings come from data/lyrics.json through pdoom.timing, so every reveal lands on the sung
word. Letters of spelled words (A-G-I, N-V-D-A, ChatGPT's G-P-T, P(doom)'s P, the halves of hyphenated words) land on
their `syl` times; other words ripple in letter by letter over the start of the word.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .. import timeline
from .. import timing as tm

FPS = tm.FPS
FRAME = 1.0 / FPS

# characters dropped by the 'minimal' punctuation policy (commas, stops, quotes); apostrophes, brackets, hyphens,
# ! and ? stay because they change how a word reads
MINIMAL_DROP = set(',.;:"“”')
QUOTE_MAP = {'’': "'", '‘': "'", '“': '"', '”': '"'}

# syllable groups for spelled words whose letter count doesn't match their syl count
SYL_SPLIT = {'killswitch': ['Kill', 'switch']}


@dataclass
class Letter:
    ch: str            # the character as displayed (after case and punctuation policies)
    t: float           # reveal time (song seconds)
    k: int             # index in its word (after punctuation filtering)
    group: int = 0     # syllable group index (spelled words), else 0


@dataclass
class Word:
    line: int
    index: int         # word index in its line
    raw: str           # as in lyrics.json
    text: str          # displayed text
    start: float
    end: float
    letters: list[Letter] = field(default_factory=list)
    syl: list | None = None

    @property
    def key(self):
        return (self.line, self.index)

    def __repr__(self):
        return f'Word({self.line}.{self.index} {self.text!r} {self.start:.2f})'


def lines() -> list[dict]:
    return tm.lyrics()


def display_text(raw: str, *, case: str | None = None, punct: str = 'minimal') -> str:
    s = ''.join(QUOTE_MAP.get(c, c) for c in raw)
    if punct == 'minimal':
        s = ''.join(c for c in s if c not in MINIMAL_DROP)
    elif punct == 'none':
        s = ''.join(c for c in s if c.isalnum() or c == "'")
    elif punct == 'keep':
        pass
    if case == 'upper':
        s = s.upper()
    elif case == 'lower':
        s = s.lower()
    return s


def _syl_groups(raw: str, n_syl: int) -> list[str] | None:
    """Split a spelled word's raw text into n_syl groups (one per syllable time)."""
    low = re.sub(r'[^a-z]', '', raw.lower())
    if low in SYL_SPLIT and len(SYL_SPLIT[low]) == n_syl:
        return SYL_SPLIT[low]
    alnum = [c for c in raw if c.isalnum()]
    if len(alnum) == n_syl:                            # A-G-I, N-V-D-A, M-L-P, R-L-H-F ...
        out, cur = [], ''
        for c in raw:
            cur += c
            if c.isalnum():
                out.append(cur)
                cur = ''
        if cur:
            out[-1] += cur
        return out
    if '-' in raw and raw.count('-') == n_syl - 1:     # Post-Chinchilla, super-dense, pre-training, self-upgrade
        parts = raw.split('-')
        return [p + ('-' if i < len(parts) - 1 else '') for i, p in enumerate(parts)]
    if '(' in raw and n_syl == 2:                      # P(doom)
        i = raw.index('(')
        return [raw[:i], raw[i:]]
    m = re.match(r'^(.*?)([A-Z]+)(\W*)$', raw)          # ChatGPT, -> Chat G P T,
    if m and len(m.group(2)) >= n_syl - 1 and m.group(1):
        caps = m.group(2)
        head = m.group(1) + caps[:len(caps) - (n_syl - 1)]
        tail = list(caps[len(caps) - (n_syl - 1):])
        tail[-1] += m.group(3)
        return [head] + tail
    return None


def letter_times(wd: dict, text_letters: list[str], raw: str, *,
                 stagger: float | None = None) -> list[tuple[float, int]]:
    """Reveal time and syllable group of each displayed letter of a word."""
    n = len(text_letters)
    if n == 0:
        return []
    start, end = wd['start'], wd['end']
    syl = wd.get('syl')
    groups = _syl_groups(raw, len(syl)) if syl else None
    if groups:
        # map raw characters to groups, then displayed letters (same order, some dropped) to groups
        owner = []
        for gi, g in enumerate(groups):
            owner += [gi] * len(g)
        disp_owner = []
        j = 0
        for ch in text_letters:
            while j < len(raw) and display_char_match(raw[j], ch) is False:
                j += 1
            disp_owner.append(owner[min(j, len(owner) - 1)] if owner else 0)
            j += 1
        out = []
        for gi in range(len(groups)):
            idx = [k for k, g in enumerate(disp_owner) if g == gi]
            if not idx:
                continue
            g0, g1 = syl[gi][0], syl[gi][1] if len(syl[gi]) > 1 else syl[gi][0] + 0.2
            dt = stagger if stagger is not None else min(2 * FRAME, max(FRAME, 0.5 * (g1 - g0) / len(idx)))
            for m, k in enumerate(idx):
                out.append((k, g0 + m * dt, gi))
        out.sort()
        res, last = [], -1e9
        for _, t, g in out:                            # never reveal a letter before the one to its left
            last = max(last, t)
            res.append((last, g))
        return res
    dt = stagger if stagger is not None else min(2 * FRAME, max(FRAME, 0.55 * (end - start) / n))
    return [(start + k * dt, 0) for k in range(n)]


def display_char_match(raw_c: str, disp_c: str) -> bool:
    r = QUOTE_MAP.get(raw_c, raw_c)
    return r.lower() == disp_c.lower()


def word(line_i: int, word_i: int, *, case=None, punct='minimal', stagger=None) -> Word:
    ln = lines()[line_i]
    wd = ln['words'][word_i]
    text = display_text(wd['w'], case=case, punct=punct)
    letters = list(text)
    times = letter_times(wd, letters, wd['w'], stagger=stagger)
    w = Word(line_i, word_i, wd['w'], text, wd['start'], wd['end'], syl=wd.get('syl'))
    w.letters = [Letter(ch, t, k, g) for k, (ch, (t, g)) in enumerate(zip(letters, times))]
    return w


def select(line_i: int, words=None) -> list[int]:
    """Word indices of a line: None = all; 'text' = the run of words matching (e.g. 'training loss'); (a, b) = the
    slice a..b-1; an int; or a list of ints."""
    ws = lines()[line_i]['words']
    n = len(ws)
    if words is None:
        return list(range(n))
    if isinstance(words, int):
        return [words if words >= 0 else n + words]
    if isinstance(words, tuple) and len(words) == 2 and all(isinstance(x, int) for x in words):
        return list(range(words[0], words[1]))
    if isinstance(words, (list, range)):
        return [int(x) for x in words]
    if isinstance(words, str):
        want = [tm._norm(x) for x in words.split()]
        have = [tm._norm(w['w']) for w in ws]
        for i in range(n - len(want) + 1):
            if all(have[i + k] == want[k] or have[i + k].startswith(want[k]) for k in range(len(want))):
                return list(range(i, i + len(want)))
        raise KeyError(f'no words {words!r} in line {line_i}: {lines()[line_i]["text"]!r}')
    raise TypeError(f'bad words selector {words!r}')


def find_line(q) -> int:
    if isinstance(q, int):
        return q
    ln = tm.line(q)
    return lines().index(ln)


# ------------------------------------------------------------------------------------------------ rows


def split_rows(words: list[Word], max_chars: int, max_rows: int = 2) -> list[list[Word]]:
    """Split words into at most max_rows balanced rows (by character count), preferring breaks after punctuation."""
    total = sum(len(w.text) for w in words) + max(0, len(words) - 1)
    if total <= max_chars or len(words) < 2 or max_rows < 2:
        return [words]
    best = None
    for k in range(1, len(words)):
        a = sum(len(w.text) for w in words[:k]) + k - 1
        b = sum(len(w.text) for w in words[k:]) + len(words) - k - 1
        gap = words[k].line == words[k - 1].line and words[k].index - words[k - 1].index > 1
        score = max(a, b) - (2.5 if re.search(r'[,;:!?]$', words[k - 1].raw) else 0) - (6.0 if gap else 0)
        if best is None or score < best[0]:
            best = (score, k)
    k = best[1]
    first, rest = words[:k], words[k:]
    if max_rows > 2 and sum(len(w.text) for w in rest) + len(rest) - 1 > max_chars:
        return [first] + split_rows(rest, max_chars, max_rows - 1)
    return [first, rest]


# ------------------------------------------------------------------------------------------------ scenes


def owner(line_i: int) -> str:
    """The scene that shows most of a line (by overlap of its sung span with the scene windows)."""
    ln = lines()[line_i]
    a, b = ln['words'][0]['start'], max(ln['words'][-1]['end'], ln['words'][-1]['start'] + 0.3)
    best = None
    for sid, _ in timeline.EDIT:
        w0, w1 = timeline.window(sid)
        ov = min(b, w1) - max(a, w0)
        if best is None or ov > best[0]:
            best = (ov, sid)
    return best[1]


def scene_words(scene_id: str | None = None, window: tuple[float, float] | None = None, *,
                tail_skip: float = 0.25) -> dict[int, list[int]]:
    """{line: [word indices]} a scene shows by default: every line with a word sung (or still held) inside its window,
    from its first word (words sung before the window are already up on the first frame, so a line that straddles a
    cut reads whole on both sides) up to the window's end. Words starting in the last `tail_skip` seconds are left
    to the next scene
    (a word popping up for three frames before a cut only flickers)."""
    if window is None:
        window = timeline.window(scene_id)
    w0, w1 = window
    out: dict[int, list[int]] = {}
    for i, ln in enumerate(lines()):
        starts = [wd['start'] for wd in ln['words']]
        live = any(s < w1 - tail_skip and max(wd['end'], s + 0.3) > w0 + 0.3 for s, wd in zip(starts, ln['words']))
        if not live:
            continue
        out[i] = [j for j, s in enumerate(starts) if s < w1 - tail_skip]
    return out


def line_span(line_i: int) -> tuple[float, float]:
    ln = lines()[line_i]
    return ln['words'][0]['start'], ln['words'][-1]['end']
