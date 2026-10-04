#!/usr/bin/env python3
"""Front end for rendering the Blender video. Run from videos/pdoom-tabletop/ with the system Python (needs Pillow).

  python tools/render.py build   <scene>                         # build + save out/blend/<scene>.blend
  python tools/render.py stills  <scene> --t 1.2,3.4 [--scale 50] [--samples 16] [--nomb] [--reuse]
  python tools/render.py sheet   <scene> [--from A --to B --n 12 | --t 1,2,3] [--cols 4] [--scale 50] [--reuse]
  python tools/render.py strip   <scene> --from A --to B [--cols 6]     # every frame of a moment
  python tools/render.py range   <scene> [--workers 3] [--samples 64] [--reuse]   # all of the scene's frames
  python tools/render.py assemble [--out out/pdoom-blender.mp4] [--nosubs]   # every scene's frames + song + subtitles

--fps 60 (any mode): build for 60 fps output (env PDOOM_FPS=60: puppets and per-frame props sampled smooth on the 60 fps
grid; saved as out/blend60/<scene>.blend) and, for stills/sheet/strip/range, render OUTPUT frames (k shows t = k / 60).
Production (4K, 60 fps): `build <scene> --fps 60`, then `range <scene> --scale 200 --fps 60 --reuse` -> out/frames_2160p60/<scene>/f_<k>.png (output frame k
shows song time k / 60; blender/run.py --fps), then `assemble --scale 200 --fps 60`. Frames rendered on rented
GPUs come back as one lossless file per scene (tools/cloud/encode_scenes.sh): `assemble --fps 60 --from-enc DIR`.

Times are SONG SECONDS. --reuse renders from the saved .blend (skip the build). Outputs:
  stills/sheets/strips -> out/wip/<scene>/,  range -> out/frames/<scene>/f_<global frame>.png
Blender runs at below-normal priority (the user's CPU matters).
"""
from __future__ import annotations

import argparse
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, 'blender', 'lib'))
from pdoom import timeline  # noqa: E402  (pure python)
from pdoom.timing import FPS, t2f  # noqa: E402

sys.path.insert(0, HERE)
import procguard  # noqa: E402  (no ghost renders: job object + STOP flag + launcher watchdog)

BLENDER = os.environ.get('BLENDER', r'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe')
RUN = os.path.join(ROOT, 'blender', 'run.py')
OUT = os.path.join(ROOT, 'out')
BELOW_NORMAL = 0x00004000
# The user asked to keep one CPU free while rendering: every Blender process runs on logical CPUs 1..N-1 (CPU 0 stays
# free) at below-normal priority. Set RESERVE_CPU0=0 in the environment to use every core.
RESERVE_CPU0 = os.environ.get('RESERVE_CPU0', '1') != '0'


def _spare_cpu0(pid: int) -> None:
    if os.name != 'nt' or not RESERVE_CPU0:
        return
    try:
        import ctypes
        k32 = ctypes.windll.kernel32
        h = k32.OpenProcess(0x0200 | 0x0400, False, pid)  # PROCESS_SET_INFORMATION | PROCESS_QUERY_INFORMATION
        if h:
            n = os.cpu_count() or 1
            k32.SetProcessAffinityMask(h, ctypes.c_size_t(((1 << n) - 1) & ~1))
            k32.CloseHandle(h)
    except Exception:
        pass


def blender(args: list[str], log: str | None = None) -> int:
    cmd = [BLENDER, '-b', '--factory-startup', '-noaudio', '-P', RUN, '--'] + args
    kw = {}
    if os.name == 'nt':
        kw['creationflags'] = BELOW_NORMAL
    t0 = time.time()
    if log:
        with open(log, 'w', encoding='utf-8') as fh:
            pr = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT, **kw)
            _spare_cpu0(pr.pid)
            procguard.adopt(pr)
            pr.wait()
            p = subprocess.CompletedProcess(cmd, pr.returncode)
    else:
        pr = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                              errors='replace', **kw)
        _spare_cpu0(pr.pid)
        procguard.adopt(pr)
        out, _ = pr.communicate()
        p = subprocess.CompletedProcess(cmd, pr.returncode, out)
        lines = p.stdout.splitlines()
        keep = [ln for ln in lines if ln.startswith('[run]') or '[fx]' in ln or 'Error' in ln or 'Traceback' in ln
                or ln.startswith('  File') or 'error' in ln.lower()[:40]]
        print('\n'.join(keep[-60:]))
    if p.returncode != 0:
        print(f'blender exited {p.returncode} after {time.time() - t0:.0f}s', file=sys.stderr)
    return p.returncode


def frames_dir(fps: int = FPS, scale: int = 100) -> str:
    """out/frames for the 1080p24 trial; out/frames_<height>p<fps> otherwise (e.g. frames_2160p60)."""
    scale = scale or 100
    if fps == FPS and scale == 100:
        return os.path.join(OUT, 'frames')
    return os.path.join(OUT, f'frames_{1080 * scale // 100}p{fps}')


def blend_path(scene: str, fps: int = FPS) -> str:
    if fps != FPS:
        return os.path.join(OUT, f'blend{fps}', f'{scene}.blend')
    return os.path.join(OUT, 'blend', f'{scene}.blend')


def build(scene: str, fps: int = FPS) -> None:
    os.environ['PDOOM_FPS'] = str(fps)                      # read by pdoom.timing inside Blender (OUT_FPS)
    rc = blender(['--scene', scene, '--save', blend_path(scene, fps)])
    if rc:
        raise SystemExit(rc)


def render_frames(scene: str, frames: list[float], out: str, *, scale=100, samples=0, nomb=False, reuse=False,
                  fps: int = FPS):
    os.environ['PDOOM_FPS'] = str(fps)
    args = (['--blend', blend_path(scene, fps)] if reuse else ['--scene', scene])
    if fps != FPS:
        args += ['--fps', str(fps)]
    args += ['--frames', ','.join(f'{f:g}' for f in frames), '--out', out, '--scale', str(scale)]
    if samples:
        args += ['--samples', str(samples)]
    if nomb:
        args += ['--nomb']
    rc = blender(args)
    if rc:
        raise SystemExit(rc)


def frame_file(out: str, f: float) -> str:
    fi = int(f)
    sub = f - fi
    return os.path.join(out, f'f_{fi:05d}.png' if sub == 0 else f'f_{fi:05d}_{int(round(sub * 100)):02d}.png')


def tile(files: list[tuple[str, str]], cols: int, dest: str, width: int = 480) -> None:
    from PIL import Image, ImageDraw
    ims = [(Image.open(f).convert('RGB'), label) for f, label in files if os.path.exists(f)]
    if not ims:
        raise SystemExit('nothing rendered')
    w = width
    h = round(ims[0][0].height * w / ims[0][0].width)
    rows = math.ceil(len(ims) / cols)
    sheet = Image.new('RGB', (cols * w, rows * (h + 18)), (24, 24, 24))
    d = ImageDraw.Draw(sheet)
    for i, (im, label) in enumerate(ims):
        x, y = (i % cols) * w, (i // cols) * (h + 18)
        sheet.paste(im.resize((w, h)), (x, y + 18))
        d.text((x + 4, y + 3), label, fill=(230, 230, 230))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    sheet.save(dest)
    print(f'wrote {dest}')


def times_arg(a) -> list[float]:
    if a.t:
        return [float(x) for x in a.t.split(',')]
    n = a.n
    return [a.from_ + (a.to - a.from_) * i / max(1, n - 1) for i in range(n)]


def main() -> None:
    procguard.start()
    ap = argparse.ArgumentParser()
    ap.add_argument('mode')
    ap.add_argument('scene', nargs='?')
    ap.add_argument('--t', default='')
    ap.add_argument('--from', dest='from_', type=float, default=0.0)
    ap.add_argument('--to', type=float, default=0.0)
    ap.add_argument('--n', type=int, default=12)
    ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--scale', type=int, default=0)
    ap.add_argument('--samples', type=int, default=0)
    ap.add_argument('--nomb', action='store_true')
    ap.add_argument('--reuse', action='store_true')
    ap.add_argument('--workers', type=int, default=3)
    ap.add_argument('--out', default='')
    ap.add_argument('--exact', action='store_true')
    ap.add_argument('--subs', action='store_true', help='assemble: burn the karaoke subtitles in (the default)')
    ap.add_argument('--fps', type=int, default=FPS, help='range/assemble: output frame rate (default 24)')
    ap.add_argument('--from-enc', dest='from_enc', default='',
                    help='assemble: a folder of per-scene lossless videos (<scene>.mkv) instead of frames')
    ap.add_argument('--nosubs', action='store_true', help='assemble: no subtitles (revision 2 had its lyrics in the '
                    'picture; build with PDOOM_LYRICS=1 for that)')
    a = ap.parse_args()
    if a.out:
        a.out = os.path.abspath(a.out)  # Blender resolves relative paths against its own cwd

    if a.mode == 'build':
        build(a.scene, a.fps)
    elif a.mode in ('stills', 'sheet', 'strip'):
        s = a.scene
        if a.fps != FPS:                     # output frames k at a.fps (t = k / fps)
            if a.mode == 'strip':
                frames = list(range(round(a.from_ * a.fps), round(a.to * a.fps) + 1))
            else:
                frames = [round(t * a.fps) for t in times_arg(a)]
            times = [k / a.fps for k in frames]
        elif a.mode == 'strip':
            frames = list(range(t2f(a.from_), t2f(a.to) + 1))
            times = [f / FPS for f in frames]
        else:
            times = times_arg(a)
            # whole frames: on-twos characters and keyed poses switch between frames, so a fractional frame shows
            # them mid-shutter (ghosted). --exact keeps the fractional frame of each time.
            frames = [round(t * FPS * 100) / 100 for t in times] if a.exact else [float(round(t * FPS)) for t in times]
        out = a.out or os.path.join(OUT, 'wip', s, a.mode)
        scale = a.scale or (100 if a.mode == 'stills' else 50)
        render_frames(s, frames, out, scale=scale, samples=a.samples, nomb=a.nomb, reuse=a.reuse, fps=a.fps)
        if a.mode != 'stills':
            files = [(frame_file(out, f), f'{t:.2f}s  f{f:g}') for f, t in zip(frames, times)]
            tile(files, a.cols if a.mode == 'sheet' else max(a.cols, 6), os.path.join(OUT, 'wip', s, f'{a.mode}.png'))
    elif a.mode == 'range':
        s = a.scene
        if not a.reuse:
            build(s, a.fps)
        f0, f1 = timeline.frames(s) if a.fps == FPS else timeline.frames_at(s, a.fps)
        out = a.out or os.path.join(frames_dir(a.fps, a.scale), s)
        os.makedirs(out, exist_ok=True)
        todo = [f for f in range(f0, f1 + 1) if not os.path.exists(frame_file(out, f))]
        print(f'{s}: frames {f0}-{f1}, {len(todo)} to render, {a.workers} workers')
        if not todo:
            return
        chunks = [todo[i::a.workers] for i in range(a.workers)]
        procs = []
        kw = {'creationflags': BELOW_NORMAL} if os.name == 'nt' else {}
        os.makedirs(os.path.join(OUT, 'logs'), exist_ok=True)
        for i, ch in enumerate(chunks):
            if not ch:
                continue
            args = ['--blend', blend_path(s, a.fps), '--frames', ','.join(map(str, ch)), '--out', out]
            if a.fps != FPS:
                args += ['--fps', str(a.fps)]
            if a.scale:
                args += ['--scale', str(a.scale)]
            if a.samples:
                args += ['--samples', str(a.samples)]
            log = open(os.path.join(OUT, 'logs', f'{s}-w{i}.log'), 'w', encoding='utf-8')
            pr = subprocess.Popen([BLENDER, '-b', '--factory-startup', '-noaudio', '-P', RUN, '--'] + args,
                                  stdout=log, stderr=subprocess.STDOUT, **kw)
            _spare_cpu0(pr.pid)
            procguard.adopt(pr)
            procs.append((pr, log))
            time.sleep(4)  # stagger shader compilation
        bad = 0
        for p, log in procs:
            bad |= p.wait()
            log.close()
        missing = [f for f in range(f0, f1 + 1) if not os.path.exists(frame_file(out, f))]
        print(f'{s}: {len(missing)} frames missing' if missing else f'{s}: all frames rendered')
        if bad or missing:
            raise SystemExit(1)
    elif a.mode == 'assemble':
        assemble(a.out or os.path.join(OUT, 'pdoom-blender.mp4'), subs=not a.nosubs, fps=a.fps, scale=a.scale,
                 from_enc=a.from_enc)
    else:
        raise SystemExit(f'unknown mode {a.mode}')


def assemble(dest: str, subs: bool = True, fps: int = FPS, scale: int = 100, from_enc: str = '') -> None:
    """Every scene's frames in edit order + the song -> H.264 on the GPU (NVENC constqp 17), with the karaoke
    subtitles burned in (revision 3, as in revision 1; `--nosubs` leaves them out)."""
    fdir = os.path.abspath(from_enc) if from_enc else frames_dir(fps, scale)
    lst = os.path.join(fdir, 'all.txt')
    missing = 0
    enc = []                                              # --from-enc: one lossless video per scene, in edit order
    with open(lst, 'w', encoding='utf-8') as fh:
        for sid, _ in timeline.EDIT:
            if from_enc:
                p = os.path.join(fdir, f'{sid}.mkv')
                if not os.path.exists(p):
                    raise SystemExit(f'missing {p}')
                enc.append(p)
                continue
            f0, f1 = timeline.frames(sid) if fps == FPS else timeline.frames_at(sid, fps)
            for f in range(f0, f1 + 1):
                p = frame_file(os.path.join(fdir, sid), f)
                if not os.path.exists(p):
                    missing += 1
                    continue
                fh.write(f"file '{p.replace(os.sep, '/')}'\nduration {1 / fps:.9f}\n")
    if missing:
        print(f'warning: {missing} frames missing (their neighbours hold)')
    ass = os.path.join(OUT, 'lyrics.ass')
    sys.path.insert(0, HERE)
    import subtitles  # noqa: E402
    subtitles.write_ass(ass)
    song = os.path.join(ROOT, 'audio', 'song.mp3')
    vf = (f"subtitles='{ass.replace(os.sep, '/').replace(':', chr(92) + ':')}'" if subs else 'null')
    if enc:
        # the concat FILTER (not the demuxer): the scene files may differ in codec (HEVC 4:4:4 or x264 RGB lossless)
        ins = [x for p in enc for x in ('-i', p)]
        fc = ''.join(f'[{i}:v]' for i in range(len(enc))) + f'concat=n={len(enc)}:v=1:a=0,{vf}[v]'
        src = ins + ['-i', song, '-filter_complex', fc, '-map', '[v]', '-map', f'{len(enc)}:a']
    else:
        src = ['-f', 'concat', '-safe', '0', '-i', lst, '-i', song, '-vf', vf]
    cmd = ['ffmpeg', '-y', '-loglevel', 'error'] + src + ['-r', str(fps), '-pix_fmt', 'yuv420p',
           '-c:v', 'h264_nvenc', '-preset', 'p7', '-tune', 'hq', '-rc', 'constqp', '-qp', '17',
           '-spatial-aq', '1', '-temporal-aq', '1', '-c:a', 'aac', '-b:a', '256k', '-shortest', dest]
    pr = subprocess.Popen(cmd)
    procguard.adopt(pr)
    if pr.wait():
        raise SystemExit(pr.returncode)
    print(f'wrote {dest}')


if __name__ == '__main__':
    main()
