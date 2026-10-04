#!/usr/bin/env python3
"""Run PARANOIA commands on a rented cloud machine instead of this PC (the user: no rendering on the PC).

  python tools/cloud/remote.py A run render.py sheet --t 3,4,5 --out out/wip/sheet.jpg
  python tools/cloud/remote.py A run analysis/analyze.py
  python tools/cloud/remote.py A shell "ls clips | wc -l"          # any command in /work/lm
  python tools/cloud/remote.py A pull out/wip/foo data/audio.json   # copy files/dirs back

`run`: (1) copies engine/, sections/, tools/, analysis/, data/ and render.py from this folder to /work/lm on the
machine (a few MB; clips and models are already there), (2) runs `python <args>` there with the venv and streams its
output, (3) copies back every file the command wrote under out/wip/, data/ and the --out path, into the same place
here, so you Read images exactly as if they were made locally. Machines: out/cloud/machines.json
({"A": {"host": ..., "port": ...}}), written by the lead. Run from videos/paranoia/.
"""
import io
import json
import os
import subprocess
import sys
import tarfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
SYNC = ('engine', 'sections', 'tools', 'analysis', 'data', 'render.py', 'assets')
REMOTE = '/work/lm'
SSH = r'C:/Program Files/Git/usr/bin/ssh.exe' if os.path.exists(r'C:/Program Files/Git/usr/bin/ssh.exe') else 'ssh'
SSH_OPTS = ['-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', '-o', 'LogLevel=ERROR',
            '-o', 'ServerAliveInterval=30', '-o', 'ConnectTimeout=20']


def machine(letter):
    with open(os.path.join(ROOT, 'out', 'cloud', 'machines.json'), encoding='utf-8') as fh:
        m = json.load(fh)[letter]
    return [SSH, '-p', str(m['port'])] + SSH_OPTS + [f"root@{m['host']}"]


def push(ssh):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode='w') as tf:
        for d in SYNC:
            p = os.path.join(ROOT, d)
            if os.path.exists(p):
                tf.add(p, arcname=d, filter=lambda ti: None if '__pycache__' in ti.name or ti.name.endswith('.pyc')
                       else ti)
    r = subprocess.run(ssh + [f'mkdir -p {REMOTE} && cd {REMOTE} && rm -rf sections engine && tar xf - '
                              '&& find . -maxdepth 3 -name __pycache__ -prune -exec rm -rf {} +'],
                       input=buf.getvalue(), capture_output=True)
    if r.returncode:
        raise SystemExit('sync failed: ' + r.stderr.decode(errors='replace'))


def pull(ssh, dirs, since=None):
    """Copy back files under `dirs` (relative); only those changed after the marker file `since` if given."""
    find = ' '.join("'" + d + "'" for d in dirs)
    newer = f'-newer {since}' if since else ''
    cmd = (f'cd {REMOTE} && for d in {find}; do [ -e "$d" ] && find "$d" -type f {newer}; done '
           f'| tar cf - -T - 2>/dev/null; ' + (f'rm -f {since}' if since else 'true'))
    r = subprocess.run(ssh + [cmd], capture_output=True)
    n = 0
    if r.stdout:
        with tarfile.open(fileobj=io.BytesIO(r.stdout)) as tf:
            for m in tf.getmembers():
                if m.isfile():
                    dest = os.path.join(ROOT, *m.name.split('/'))
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with tf.extractfile(m) as src, open(dest, 'wb') as fh:
                        fh.write(src.read())
                    n += 1
    print(f'[remote] copied back {n} files', flush=True)


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    letter, mode, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    ssh = machine(letter)
    t0 = time.time()
    if mode == 'pull':
        pull(ssh, args)
        return
    push(ssh)
    if mode == 'shell':
        raise SystemExit(subprocess.call(ssh + ['source /root/env.sh >/dev/null; ' + ' '.join(args)]))
    if mode != 'run':
        raise SystemExit(__doc__)
    dirs = ['out/wip', 'data']
    if '--out' in args:
        out = args[args.index('--out') + 1].replace('\\', '/')
        if os.path.isabs(out) or ':' in out:
            raise SystemExit('--out must be a relative path (e.g. out/wip/drop/sheet.jpg)')
        dirs.append(out)
    since = f'/tmp/remote_{os.getpid()}_{int(t0)}'
    quoted = ' '.join("'" + a.replace("'", "'\\''") + "'" for a in args)
    rc = subprocess.call(ssh + [f'touch {since}; sleep 1; source /root/env.sh >/dev/null; python {quoted}'])
    pull(ssh, dirs, since)
    print(f'[remote] {letter}: rc={rc} in {time.time() - t0:.0f}s', flush=True)
    raise SystemExit(rc)


if __name__ == '__main__':
    main()
