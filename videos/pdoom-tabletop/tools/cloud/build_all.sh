#!/bin/bash
# build the given scenes, 9 at a time (FPS=60 in the environment builds for 60 fps output: out/blend60/). A build that
# logs a Traceback (singularity's rare 'NoneType' error) is retried up to 3 times; builds.txt gets one line per scene.
source /root/env.sh
X=""; [ -n "$FPS" ] && X="--fps $FPS"
echo "$@" | tr " " "\n" | xargs -P 9 -I{} bash -c "t0=\$(date +%s); for try in 1 2 3; do python3 tools/render.py build {} $X > out/logs/{}-build.log 2>&1; grep -q Traceback out/logs/{}-build.log || break; done; tb=\$(grep -c Traceback out/logs/{}-build.log); echo \"{} done tries=\$try tracebacks=\$tb \$(( \$(date +%s) - t0 ))s\" >> out/logs/builds.txt"
echo ALLDONE >> out/logs/builds.txt
