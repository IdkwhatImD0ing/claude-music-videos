#!/usr/bin/env python3
"""Print the scouting results as a casting table (PC, no torch): data/scouting.json + data/catalog.json.

  python tools/cast_table.py                 # all clips, best first
  python tools/cast_table.py --use finale    # only clips scouted for one section
"""
import argparse
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--use', default='')
    a = ap.parse_args()
    sc = json.load(open(os.path.join(ROOT, 'data', 'scouting.json')))['clips']
    cat = {c['file']: c for c in json.load(open(os.path.join(ROOT, 'data', 'catalog.json')))['candidates']}
    rows = []
    for s in sc:
        c = cat.get(s['file'], {})
        score = s['hype'] * 1.0 + s['readability'] * 0.8 + s['spectacle'] * 0.7
        rows.append((score, s, c))
    rows.sort(key=lambda r: -r[0])
    for score, s, c in rows:
        if a.use and s['best_use'] != a.use:
            continue
        print(f"{score:5.1f} H{s['hype']} R{s['readability']} S{s['spectacle']} {s['best_use']:7s} "
              f"{s['file'][19:38]} chain{c.get('chain_size', '?')} {s['champion'][:14]:14s} {s['map'][:10]:10s} "
              f"in {s['best_in']:.1f} out {s['best_out']:.1f}")
        print(f"      {s['summary'][:150]}")
        if s['low_hp']:
            print(f"      LOW HP: {s['low_hp'][:140]}")
        print(f"      notes: {s['editor_notes'][:160]}")


if __name__ == '__main__':
    main()
