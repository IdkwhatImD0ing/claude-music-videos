#!/bin/bash
# Renders scenes in edit order (or the ones given), resumably. Run it with the Bash tool's run_in_background.
#   bash tools/render_all.sh                 # every scene in timeline.EDIT
#   bash tools/render_all.sh havoc legion    # just these
# A scene with no frames yet is rebuilt from the committed code first; a scene that already has frames renders the
# missing ones from its saved build (--reuse). So a stopped run picks up where it left off. If you changed a scene's
# code after its frames were rendered, move its out/frames/<scene>/ aside (or run `render.py build <scene>`) first.
# Stops at once if the STOP flag exists. Log: out/logs/render-all.log. Then: python tools/render.py assemble
cd "$(dirname "$0")/.." || exit 1
mkdir -p out/logs
STOP="${RENDER_STOP_FILE:-G:/video-renders/STOP}"
scenes=("$@")
if [ ${#scenes[@]} -eq 0 ]; then
  mapfile -t scenes < <(python -c "import sys; sys.path.insert(0, 'blender/lib'); from pdoom import timeline; print('\n'.join(s for s, _ in timeline.EDIT))" | tr -d '\r')
fi
for s in "${scenes[@]}"; do
  [ -f "$STOP" ] && { echo "STOP flag $STOP: stopping" | tee -a out/logs/render-all.log; exit 3; }
  n=$(ls "out/frames/$s" 2>/dev/null | wc -l)
  flag=""; [ "$n" -gt 0 ] && flag="--reuse"
  echo "=== $s $(date +%H:%M:%S) ($n frames already) $flag" | tee -a out/logs/render-all.log
  python tools/render.py range "$s" --workers 2 $flag 2>&1 | tr -d '\r' | grep -v '^\[run\]' | tail -3 | tee -a out/logs/render-all.log
done
echo "done $(date +%H:%M:%S)" | tee -a out/logs/render-all.log
