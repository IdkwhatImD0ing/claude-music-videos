#!/usr/bin/env python3
"""Record which SteelSeries clips this video uses, so later videos pick fresh footage.

  python tools/cloud/remote.py A run tools/ledger.py collect   # on the machine: data/used_clips.json from the edit
  python tools/ledger.py merge                                  # on the PC: merge into library/footage-ledger.json

`collect` builds the edit and lists, for every shot, the clip and the clip seconds shown on screen. `merge` (no
torch needed) replaces this video's entries in the shared ledger with data/used_clips.json, adding each clip's
Moments id from data/catalog.json. tools/catalog.py skips every clip in the ledger.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(os.path.dirname(ROOT))
VIDEO = 'league-montage'
LEDGER = os.path.join(REPO, 'library', 'footage-ledger.json')


def collect():
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)
    import numpy as np
    from engine import edit as ed
    E = ed.build()
    used = {}
    for s in E.shots:
        ts = np.linspace(s.t0, s.t1 - 1e-3, 200)
        ss = [float(s.s(t)) for t in ts]
        used.setdefault(s.clip_name, []).append([round(min(ss), 2), round(max(ss), 2)])
    # clips used only inside layers (split-screen panels, insets) have no shot: find them in the section sources
    import re
    for fn in os.listdir(os.path.join(ROOT, 'sections')):
        if fn.endswith('.py'):
            for name in re.findall(r'League-of-Legends__[0-9_-]+\.mp4', open(os.path.join(ROOT, 'sections', fn)).read()):
                used.setdefault(name, [])
    out = [{'file': f, 'src_ranges': sorted(r)} for f, r in sorted(used.items())]
    json.dump(out, open(os.path.join(ROOT, 'data', 'used_clips.json'), 'w'), indent=1)
    print(f'{len(out)} clips used')


def merge():
    used = json.load(open(os.path.join(ROOT, 'data', 'used_clips.json')))
    cat = {c['file']: c for c in json.load(open(os.path.join(ROOT, 'data', 'catalog.json')))['candidates']}
    led = json.load(open(LEDGER, encoding='utf-8'))
    led['used'] = [u for u in led['used'] if u.get('video') != VIDEO]
    for u in used:
        c = cat.get(u['file'], {})
        led['used'].append({'clip_id': c.get('clip_id'), 'file': u['file'], 'path': c.get('path'), 'video': VIDEO,
                            'src_ranges': u['src_ranges']})
    with open(LEDGER, 'w', encoding='utf-8') as fh:
        json.dump(led, fh, indent=1)
    print(f"ledger: {len(led['used'])} entries ({len(used)} from {VIDEO})")


if __name__ == '__main__':
    {'collect': collect, 'merge': merge}[sys.argv[1]]()
