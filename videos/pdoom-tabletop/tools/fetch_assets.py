#!/usr/bin/env python3
"""Download the CC0 textures and HDRIs the Blender video uses into assets/ (git-ignored).

  python tools/fetch_assets.py            # fetch whatever is missing (safe to re-run)
  python tools/fetch_assets.py --list     # show the manifest and what is on disk

Sources (both CC0, no attribution required; credited anyway in assets/README.md and docs/lib/sets.md):
  Poly Haven  https://polyhaven.com   (file URLs come from https://api.polyhaven.com/files/<id>)
  ambientCG   https://ambientcg.com   (zips from https://ambientcg.com/get?file=<id>_2K-JPG.zip; we keep only the
                                       colour / roughness / normal / metalness maps)

Layout: every texture set lands in assets/tex/<key>/ as diff.jpg, rough.jpg, nor.jpg (OpenGL normal) and, for metals,
metal.jpg; HDRIs in assets/hdri/<key>.hdr. Scenes load them with kit.asset('tex', 'desk_wood', 'diff.jpg') or through
the sets library's material helpers (pdoom.sets.materials). Real-world size of each set (cm) is in the manifest so
materials can map them at true scale.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, 'assets')
UA = {'User-Agent': 'pdoom-blender-fetch/1.0 (music video; CC0 assets)'}

# key -> (source, upstream id, resolution, real-world size in cm (width of one tile), what it is for)
TEXTURES = {
    'desk_wood':     ('polyhaven', 'dark_wood', '4k', 200, 'the desktop (dark walnut-like hardwood)'),
    'wall_plaster':  ('polyhaven', 'painted_plaster_wall', '2k', 200, 'the wall behind the desk'),
    'floor_wood':    ('polyhaven', 'wood_floor', '2k', 170, 'the floor (rarely seen)'),
    'linen':         ('polyhaven', 'rough_linen', '2k', 50, 'cloth (lab coat, curtains)'),
    'paper':         ('ambientcg', 'Paper001', '2K', 30, 'paper: sticky notes, book pages, the paper moon'),
    'cardboard':     ('ambientcg', 'Cardboard004', '2K', 50, 'corrugated cardboard: the Chinese room box'),
    'felt':          ('ambientcg', 'Fabric034', '2K', 30, 'felt: gauge base, desk pad'),
    'brushed_metal': ('ambientcg', 'Metal011', '2K', 50, 'brushed metal: laptop, lamp arm, drawer unit'),
}
HDRIS = {
    'office_night': ('polyhaven', 'unfinished_office_night', '2k', 'interior at night: reflections'),
    'city_night':   ('polyhaven', 'shanghai_bund', '2k', 'a night city skyline: reflections / window backdrop'),
}

PH_MAPS = {'diff': 'Diffuse', 'rough': 'Rough', 'nor': 'nor_gl'}
ACG_MAPS = {'diff': '_Color.jpg', 'rough': '_Roughness.jpg', 'nor': '_NormalGL.jpg', 'metal': '_Metalness.jpg'}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def get_json(url: str):
    return json.loads(get(url).decode('utf-8'))


def save(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + '.part'
    with open(tmp, 'wb') as fh:
        fh.write(data)
    os.replace(tmp, path)


def fetch_ph_texture(key: str, pid: str, res: str) -> list[str]:
    files = get_json(f'https://api.polyhaven.com/files/{pid}')
    out = []
    for short, m in PH_MAPS.items():
        dest = os.path.join(ASSETS, 'tex', key, f'{short}.jpg')
        out.append(dest)
        if os.path.exists(dest):
            continue
        info = files[m][res]['jpg']
        data = get(info['url'])
        if info.get('md5') and hashlib.md5(data).hexdigest() != info['md5']:
            raise SystemExit(f'md5 mismatch for {info["url"]}')
        save(dest, data)
        print(f'  {key}/{short}.jpg  {len(data) / 1e6:.1f} MB  <- {info["url"]}')
    return out


def fetch_acg_texture(key: str, aid: str, res: str) -> list[str]:
    want = {short: os.path.join(ASSETS, 'tex', key, f'{short}.jpg') for short in ACG_MAPS}
    if all(os.path.exists(p) for s, p in want.items() if s != 'metal') and (
            os.path.exists(want['metal']) or not aid.startswith('Metal')):
        return [p for p in want.values() if os.path.exists(p)]
    url = f'https://ambientcg.com/get?file={aid}_{res}-JPG.zip'
    data = get(url)
    print(f'  {key}: {aid} zip {len(data) / 1e6:.1f} MB  <- {url}')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for short, suffix in ACG_MAPS.items():
            names = [n for n in z.namelist() if n.endswith(suffix)]
            if not names:
                continue
            save(want[short], z.read(names[0]))
            print(f'    {key}/{short}.jpg')
    return [p for p in want.values() if os.path.exists(p)]


def fetch_ph_hdri(key: str, pid: str, res: str) -> str:
    dest = os.path.join(ASSETS, 'hdri', f'{key}.hdr')
    if os.path.exists(dest):
        return dest
    files = get_json(f'https://api.polyhaven.com/files/{pid}')
    info = files['hdri'][res]['hdr']
    data = get(info['url'])
    if info.get('md5') and hashlib.md5(data).hexdigest() != info['md5']:
        raise SystemExit(f'md5 mismatch for {info["url"]}')
    save(dest, data)
    print(f'  hdri/{key}.hdr  {len(data) / 1e6:.1f} MB  <- {info["url"]}')
    return dest


def page_url(src: str, uid: str) -> str:
    return f'https://polyhaven.com/a/{uid}' if src == 'polyhaven' else f'https://ambientcg.com/view?id={uid}'


def write_readme() -> None:
    lines = ['# Downloaded assets (git-ignored)', '',
             'Fetched by `python tools/fetch_assets.py`. Everything here is **CC0** (public domain): Poly Haven',
             '(https://polyhaven.com/license) and ambientCG (https://docs.ambientcg.com/license/). No attribution is',
             'required; we credit the sources anyway.', '',
             '| key | files | source | size of one tile | used for |', '|---|---|---|---|---|']
    for key, (src, uid, res, cm, what) in TEXTURES.items():
        lines.append(f'| `tex/{key}/` | diff, rough, nor{", metal" if uid.startswith("Metal") else ""} ({res}) | '
                     f'[{uid}]({page_url(src, uid)}) ({src}, CC0) | {cm} cm | {what} |')
    for key, (src, uid, res, what) in HDRIS.items():
        lines.append(f'| `hdri/{key}.hdr` | {res} HDR | [{uid}]({page_url(src, uid)}) ({src}, CC0) | - | {what} |')
    lines += ['', 'Normal maps are OpenGL convention (Blender\'s). Load paths with `kit.asset(...)`.', '']
    os.makedirs(ASSETS, exist_ok=True)
    with open(os.path.join(ASSETS, 'README.md'), 'w', encoding='utf-8') as fh:
        fh.write('\n'.join(lines))
    manifest = {'textures': {k: {'source': s, 'id': u, 'res': r, 'tile_cm': cm, 'use': w}
                             for k, (s, u, r, cm, w) in TEXTURES.items()},
                'hdris': {k: {'source': s, 'id': u, 'res': r, 'use': w} for k, (s, u, r, w) in HDRIS.items()},
                'license': 'CC0 1.0'}
    with open(os.path.join(ASSETS, 'manifest.json'), 'w', encoding='utf-8') as fh:
        json.dump(manifest, fh, indent=2)


def disk_usage() -> float:
    tot = 0
    for dp, _, fs in os.walk(ASSETS):
        tot += sum(os.path.getsize(os.path.join(dp, f)) for f in fs)
    return tot / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    if a.list:
        for key in TEXTURES:
            d = os.path.join(ASSETS, 'tex', key)
            print(f'tex/{key}: {sorted(os.listdir(d)) if os.path.isdir(d) else "missing"}')
        for key in HDRIS:
            p = os.path.join(ASSETS, 'hdri', f'{key}.hdr')
            print(f'hdri/{key}.hdr: {"ok" if os.path.exists(p) else "missing"}')
        print(f'{disk_usage():.0f} MB on disk')
        return
    print(f'fetching into {ASSETS}')
    for key, (src, uid, res, _, _) in TEXTURES.items():
        if src == 'polyhaven':
            fetch_ph_texture(key, uid, res)
        else:
            fetch_acg_texture(key, uid, res)
    for key, (src, uid, res, _) in HDRIS.items():
        fetch_ph_hdri(key, uid, res)
    write_readme()
    print(f'done: {disk_usage():.0f} MB in assets/')


if __name__ == '__main__':
    sys.exit(main())
