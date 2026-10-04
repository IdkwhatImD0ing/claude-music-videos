#!/bin/bash
# render the scenes in order, each once its build has finished (build_all.sh logs "<scene> done ..." to builds.txt);
# render_scenes.sh's environment (FPS, SCALE, WORKERS) applies
for s in "$@"; do
  until grep -q "^$s " /work/pdoom/out/logs/builds.txt 2>/dev/null; do sleep 5; done
  /work/render_scenes.sh $s
done
