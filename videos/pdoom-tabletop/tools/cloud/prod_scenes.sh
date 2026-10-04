#!/bin/bash
# Production on one machine: build the scenes for 60 fps, render each at 4K60 once its build is done, pack them.
#   bash /work/prod_scenes.sh room fuse        (run detached; ends with PRODDONE in out/logs/prod.txt)
source /root/env.sh
rm -rf out/blend60 out/frames_2160p60 out/enc
rm -f out/logs/builds.txt out/logs/render-queue.txt out/logs/encode.txt out/logs/prod.txt
mkdir -p out/blend60 out/frames_2160p60 out/enc
FPS=60 /work/build_all.sh "$@" &
FPS=60 SCALE=200 WORKERS=4 /work/waitbuild_render.sh "$@"
wait
/work/encode_scenes.sh "$@"
echo PRODDONE >> out/logs/prod.txt
