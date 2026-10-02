#!/bin/bash
# wait for the running scene render (if any) to finish, then render the given scenes (render_scenes.sh's env applies)
while pgrep -f 'render[.]py range' >/dev/null; do sleep 5; done
/work/render_scenes.sh "$@"
