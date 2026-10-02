#!/bin/bash
# Run tools/render.py for one scene on a rented review machine (never on the user's PC), with this checkout's code.
#   bash tools/cloud/remote.sh <scene> <mode> [render.py args...]
#   bash tools/cloud/remote.sh eat build --fps 60
#   bash tools/cloud/remote.sh eat stills --t 20.5,21.0 --scale 50 --samples 16 --reuse --fps 60
#   bash tools/cloud/remote.sh training strip --from 10.4 --to 10.8 --scale 25 --samples 8 --nomb --reuse --fps 60
# Machines: out/cloud_hosts.txt (git-ignored), one "<ip> <port> <scene> <scene>..." line per machine (set up with
# tools/cloud/setup.sh); each scene always runs on the machine that lists it. Before running, the current blender/ tree and the render tools
# are copied over (each file renamed into place, so concurrent runs never read a half-written file). Stills, sheets
# and strips come back into out/wip/<scene>/<mode>/ and out/wip/<scene>/<mode>.png. Log: out/logs/remote-<scene>.log.
# A build's exit code is always 0 even when the scene script raises: this prints a warning when the log has a Traceback.
cd "$(dirname "$0")/../.." || exit 1          # the repository root
scene=$1; mode=$2; shift 2
hosts=out/cloud_hosts.txt
read -r ip port _ < <(tr -d '\r' < "$hosts" | awk -v s="$scene" '{for (i = 3; i <= NF; i++) if ($i == s) print}' | head -1)
[ -z "$port" ] && { echo "no machine lists scene $scene in $hosts"; exit 1; }
OPT="-o ConnectTimeout=20 -o ServerAliveInterval=15 -o StrictHostKeyChecking=accept-new -o LogLevel=ERROR"
mkdir -p out/logs "out/wip/$scene"
for try in 1 2 3; do
  tar --exclude=__pycache__ -cf - blender tools/render.py tools/procguard.py tools/subtitles.py | \
    ssh $OPT -p "$port" "root@$ip" 'st=/work/stage.$$; mkdir -p $st && tar -xf - -C $st && cd $st && \
      find . -type f | while read -r f; do mkdir -p "/work/pdoom/$(dirname "$f")"; mv -f "$f" "/work/pdoom/$f"; done; \
      rm -rf $st' 2>/dev/null && break
  sleep 5
done
ssh -n $OPT -p "$port" "root@$ip" "source /root/env.sh; python3 tools/render.py $mode $scene $* 2>&1" 2>/dev/null \
  | grep -v "Welcome to vast\|Have fun\|authentication fails" > "out/logs/remote-$scene.log"
grep -v '^$' "out/logs/remote-$scene.log" | tail -40
if grep -q Traceback "out/logs/remote-$scene.log"; then echo "WARNING: Traceback in out/logs/remote-$scene.log (the run failed)"; fi
case $mode in
  stills|sheet|strip)
    ssh -n $OPT -p "$port" "root@$ip" "cd /work/pdoom/out/wip && tar -cf - $scene/$mode \$(ls $scene/$mode.png 2>/dev/null)" 2>/dev/null \
      | tar -xf - -C out/wip/
    echo "results: out/wip/$scene/$mode/ $( [ "$mode" != stills ] && echo "and out/wip/$scene/$mode.png")"
    ;;
esac
