#!/usr/bin/env python3
"""Index the user's SteelSeries Moments clips into data/catalog.json and rank montage candidates.

  python tools/catalog.py                 # writes data/catalog.json, prints the top candidates
  python tools/catalog.py --top 80        # how many candidates to keep (default 70)

Reads Moments' database read-only (never writes to it). Each clip gets its kill/assist/death/objective markers
(clip-relative seconds; Moments rounds them to whole game seconds), its biggest kill chain (kills <= 10 s apart,
League's multikill window) and a score. Clips already used by a video (library/footage-ledger.json) are skipped, and
clips that recorded the same fight twice (same game, kills at the same absolute times) keep only the copy where the
chain sits best inside the clip. Clips this same video already uses (by folder name) stay in, so re-running here is safe.
"""
import argparse
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(ROOT))
DB = 'C:/ProgramData/SteelSeries/GG/apps/moments/db/database.db'
LEDGER = os.path.join(REPO, 'library', 'footage-ledger.json')
CHAIN_GAP = 10.0   # League: the next kill within 10 s extends a multikill

EVENT_KEYS = {'CHAMPION-KILLS': 'kills', 'CHAMPION-ASSISTS': 'assists', 'CHAMPION-DEATHS': 'deaths',
              'DRAGON-KILL': 'objectives', 'BARON-KILL': 'objectives', 'HERALD-KILL': 'objectives'}


def file_start(path):
    """Clip start time from the file name (League-of-Legends__2026-02-20__01-11-57.mp4)."""
    m = re.search(r'__(\d{4}-\d{2}-\d{2})__(\d{2})-(\d{2})-(\d{2})', os.path.basename(path))
    return datetime.strptime(f'{m[1]} {m[2]}:{m[3]}:{m[4]}', '%Y-%m-%d %H:%M:%S') if m else None


def chains(kills):
    out, cur = [], []
    for t in kills:
        if cur and t - cur[-1] > CHAIN_GAP:
            out.append(cur)
            cur = []
        cur.append(t)
    if cur:
        out.append(cur)
    return out


VIDEO = os.path.basename(ROOT)   # this video's own clips stay available to it; other videos' clips are skipped


def load_ledger():
    if not os.path.exists(LEDGER):
        return set()
    with open(LEDGER, encoding='utf-8') as fh:
        return {u['clip_id'] for u in json.load(fh).get('used', []) if u.get('video') != VIDEO}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--top', type=int, default=70)
    ap.add_argument('--lowhp', type=int, default=8, help='extra low-health-kill clips (near-death plays)')
    a = ap.parse_args()
    used = load_ledger()
    con = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
    con.row_factory = sqlite3.Row
    clips = []
    for r in con.execute("select * from moments_clips where last_game_name='League of Legends' and is_deleted=0"):
        if not os.path.exists(r['path']):
            continue
        ev = {'kills': [], 'assists': [], 'deaths': [], 'objectives': []}
        names = []
        for e in json.loads(r['gamesense_events'] or '[]') or []:
            k = EVENT_KEYS.get(e.get('unlocalized_display_name'))
            if k:
                ev[k].append(round(e['clip_timestamp'], 3))
            if k == 'objectives':
                names.append(e.get('unlocalized_display_name'))
        for k in ev:
            ev[k].sort()
        ch = chains(ev['kills'])
        best = max(ch, key=len) if ch else []
        start = file_start(r['path'])
        L = r['full_length'] or 60.0
        # how well the best chain sits inside the clip: lead-in before it, tail after it
        lead = best[0] if best else 0.0
        tail = (L - best[-1]) if best else 0.0
        span = (best[-1] - best[0]) if best else 0.0
        trig = r['trigger_name'] or ''
        score = (len(best) ** 2) * 10 + len(ev['kills']) * 2 + len(ev['objectives']) * 15 \
            + (12 if 'steal' in trig else 0) + (5 if trig == 'low_health_kill' else 0) \
            + (6 if best and span / max(1, len(best) - 1) < 3 else 0) - len(ev['deaths']) * 2
        clips.append({
            'clip_id': r['id'], 'file': os.path.basename(r['path']), 'path': r['path'].replace('\\', '/'),
            'start': start.isoformat() if start else None, 'session': r['session_id'],
            'length': round(L, 3), 'fps': r['framerate'], 'w': r['file_resolution_width'],
            'h': r['file_resolution_height'], 'trigger': trig, 'objective_names': names,
            'events': ev, 'chain': best, 'chain_size': len(best), 'chain_span': round(span, 3),
            'lead': round(lead, 3), 'tail': round(tail, 3), 'score': score, 'used': r['id'] in used,
        })
    # duplicates: two clips of one game whose best chains happen at the same wall-clock time
    clips.sort(key=lambda c: -c['score'])
    kept, seen = [], []
    for c in clips:
        if c['used'] or not c['chain'] or not c['start']:
            continue
        st = datetime.fromisoformat(c['start'])
        abs_kills = [st + timedelta(seconds=t) for t in c['chain']]
        dup = None
        for k in seen:
            if k['session'] == c['session'] and any(abs(((x - y).total_seconds())) < 2.5
                                                    for x in abs_kills for y in k['_abs']):
                dup = k
                break
        if dup:
            dup.setdefault('duplicates', []).append(c['file'])
            continue
        c['_abs'] = abs_kills
        seen.append(c)
        kept.append(c)
    for c in kept:
        c.pop('_abs', None)
    cands = [c for c in kept if c['fps'] >= 60][:a.top]
    have = {c['file'] for c in cands}
    cands += [c for c in kept if c['fps'] >= 60 and c['trigger'] == 'low_health_kill' and c['file'] not in have
              ][:a.lowhp]
    os.makedirs(os.path.join(ROOT, 'data'), exist_ok=True)
    out = {'source_db': DB, 'clips_indexed': len(clips), 'excluded_used': sum(c['used'] for c in clips),
           'candidates': cands}
    with open(os.path.join(ROOT, 'data', 'catalog.json'), 'w', encoding='utf-8') as fh:
        json.dump(out, fh, indent=1)
    sizes = {}
    for c in cands:
        sizes[c['chain_size']] = sizes.get(c['chain_size'], 0) + 1
    print(f"indexed {len(clips)} clips, {out['excluded_used']} already used; {len(cands)} candidates; chain sizes {sizes}")
    for c in cands[:15]:
        print(f"  {c['score']:4d}  {c['file']}  chain {c['chain_size']} over {c['chain_span']:.0f}s  "
              f"kills {len(c['events']['kills'])}  {c['trigger']} {' '.join(c['objective_names'])}")


if __name__ == '__main__':
    main()
