#!/bin/bash
# review sheets: 16 frames across each scene window, 16 samples, no motion blur, 50%
source /root/env.sh
for s in "$@"; do
  read a b < <(python3 -c "import sys; sys.path.insert(0,\"blender/lib\"); from pdoom import timeline as T; a,b=T.window(\"$s\"); print(a+0.06, b-0.06)")
  echo "$s $a $b"
done | xargs -P 4 -L 1 bash -c "python3 tools/render.py sheet \$0 --from \$1 --to \$2 --n 16 --cols 4 --reuse --samples 16 --nomb --scale 50 > out/logs/\$0-sheet.log 2>&1; echo \"\$0 sheet rc=\$?\" >> out/logs/sheets.txt"
echo SHEETSDONE >> out/logs/sheets.txt
