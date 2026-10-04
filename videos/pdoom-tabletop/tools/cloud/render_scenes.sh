#!/bin/bash
# full-quality frames for the given scenes from their saved builds (the scenes' own 64 samples, motion blur).
# WORKERS (default 2), FPS (default 24) and SCALE (default 100; 200 = 4K) come from the environment:
#   FPS=60 SCALE=200 WORKERS=4 /work/render_scenes.sh eat moon      -> out/frames_2160p60/<scene>/
source /root/env.sh
W=${WORKERS:-2}
X=""; [ -n "$FPS" ] && X="$X --fps $FPS"; [ -n "$SCALE" ] && X="$X --scale $SCALE"
for s in "$@"; do
  echo "=== $s $(date +%H:%M:%S) start" >> out/logs/render-queue.txt
  python3 tools/render.py range $s --workers $W --reuse $X > out/logs/$s-range.log 2>&1
  echo "=== $s $(date +%H:%M:%S) rc=$? $(tail -1 out/logs/$s-range.log)" >> out/logs/render-queue.txt
done
echo QUEUEDONE >> out/logs/render-queue.txt
