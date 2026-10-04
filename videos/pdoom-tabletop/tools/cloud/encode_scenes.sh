#!/bin/bash
# Pack each scene's production frames into one lossless video for download:
#   /work/encode_scenes.sh eat moon       -> out/enc/<scene>.mkv  (frames_2160p60 by default; DIR= to override)
# NVENC HEVC 4:4:4 lossless (52 dB against the PNG: RGB -> YUV rounding; ~2.6x smaller than PNG). Some hosts' ffmpeg
# can't open NVENC ("OpenEncodeSessionEx failed: unsupported device" on driver 580.95): those fall back to libx264rgb
# -qp 0 (true RGB lossless, ~1.7x bigger, fast on many cores). tools/render.py assemble --from-enc takes either.
source /root/env.sh
DIR=${DIR:-out/frames_2160p60}
FPS=${FPS:-60}
mkdir -p out/enc
for s in "$@"; do
  first=$(ls $DIR/$s | sort | head -1 | sed 's/f_0*\([0-9][0-9]*\)\.png/\1/')
  n=$(ls $DIR/$s | wc -l)
  IN="-framerate $FPS -start_number $first -i $DIR/$s/f_%05d.png -frames:v $n"
  ffmpeg -y -loglevel error $IN -c:v hevc_nvenc -preset p7 -tune lossless -pix_fmt yuv444p out/enc/$s.mkv
  rc=$?; codec=hevc_nvenc
  if [ $rc != 0 ]; then
    ffmpeg -y -loglevel error $IN -c:v libx264rgb -qp 0 -preset veryfast out/enc/$s.mkv
    rc=$?; codec=libx264rgb
  fi
  echo "$s rc=$rc $codec frames=$n first=$first $(du -h out/enc/$s.mkv | cut -f1)" >> out/logs/encode.txt
done
echo ENCODEDONE >> out/logs/encode.txt
