#!/bin/bash
# On the encode machine: collect every scene's lossless file from the render machines (plan: /work/prod_plan.txt,
# "<ip> <port> <scenes...>", LOCAL for this machine), each as soon as that scene is packed ("<scene> rc=0" in the
# machine's out/logs/encode.txt), check its frame count, then assemble the 4K60 video with subtitles (NVENC).
# Scenes already in out/enc_all with the right frame count are kept.
source /root/env.sh
mkdir -p out/enc_all
LOG=out/logs/gather.txt
want() { python3 -c "import sys; sys.path.insert(0,'blender/lib'); from pdoom import timeline as T; a,b=T.frames_at('$1',60); print(b-a+1)"; }
count() { ffprobe -v error -count_packets -select_streams v:0 -show_entries stream=nb_read_packets -of csv=p=0 "$1" 2>/dev/null; }
SSHO="-i /root/.ssh/id_enc -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 -o LogLevel=ERROR"
declare -A have
for f in out/enc_all/*.mkv; do s=$(basename "$f" .mkv); [ "$(count "$f")" = "$(want $s)" ] && have[$s]=1; done
echo "$(date +%H:%M:%S) start; already have: ${!have[*]}" >> $LOG
while true; do
  missing=0
  while read -r ip port scenes; do
    for s in $scenes; do
      [ -n "${have[$s]}" ] && continue
      if [ "$ip" = "LOCAL" ]; then enc=$(cat out/logs/encode.txt 2>/dev/null); else enc=$(ssh -n $SSHO -p $port root@$ip "cat /work/pdoom/out/logs/encode.txt 2>/dev/null" 2>/dev/null); fi
      if echo "$enc" | grep -q "^$s rc=0"; then
        if [ "$ip" = "LOCAL" ]; then cp out/enc/$s.mkv out/enc_all/; else scp -q $SSHO -P $port root@$ip:/work/pdoom/out/enc/$s.mkv out/enc_all/; fi
        got=$(count out/enc_all/$s.mkv); w=$(want $s)
        echo "$(date +%H:%M:%S) $s got=$got want=$w from $ip:$port" >> $LOG
        [ "$got" = "$w" ] && have[$s]=1 || missing=$((missing + 1))
      else
        missing=$((missing + 1))
      fi
    done
  done < /work/prod_plan.txt
  [ $missing -eq 0 ] && break
  sleep 30
done
echo "$(date +%H:%M:%S) all scenes in; assembling" >> $LOG
python3 tools/render.py assemble --fps 60 --from-enc out/enc_all --out out/pdoom-blender-4k60.mp4 >> $LOG 2>&1
ffprobe -v error -show_entries format=duration:stream=codec_name,width,height,r_frame_rate,nb_frames -of compact out/pdoom-blender-4k60.mp4 >> $LOG 2>&1
echo "$(date +%H:%M:%S) GATHERDONE" >> $LOG
