# Rendering on rented GPUs (Vast.ai)

Revision 3 (2026-10-01) was rendered on three Vast.ai RTX 5090s with these scripts. Each machine builds the scenes it
renders (Linux Blender 5.2.2, same binary as on the PC) and renders them at 1080p with the scenes' own settings.
The account rules (spend only existing credit, destroy instances when done) are in the repo CLAUDE.md, section
"Rendering on rented GPUs (Vast.ai)".

1. Rent (see CLAUDE.md for the API and the instance settings; `disk` 50-60 GB).
2. Upload and set up (from `videos/pdoom-tabletop/`):

       tar --exclude=__pycache__ -cf pdoom.tar blender data audio assets tools
       # winfonts.tar: a folder `winfonts/` with bahnschrift, segoeui, ariblk, simkai, simfang, simhei .ttf from
       # C:/Windows/Fonts (the gauge dials, the eat title and the Chinese room use them; geo.sysfont() finds them
       # through PDOOM_FONT_DIR)
       scp -P <port> pdoom.tar winfonts.tar tools/cloud/*.sh root@<ip>:/root/
       ssh -p <port> root@<ip> 'bash /root/setup.sh && cp /root/{build_all,render_scenes,sheets}.sh /work/'

   `setup.sh` installs Blender's libraries and Blender 5.2.2 (download.blender.org returned 403 to one machine: it
   falls back to the Berkeley mirror; compare `sha256sum /opt/blender/blender` across machines).
3. Build, check, render (each runs detached with `setsid nohup ... &`; logs in `/work/pdoom/out/logs/`):

       /work/build_all.sh eat moon room      # 9 builds at a time; a build's rc is always 0: grep the logs for Traceback
       /work/sheets.sh eat moon              # 16-frame review sheets -> out/wip/<scene>/sheet.png
       /work/render_scenes.sh eat moon       # every frame -> out/frames/<scene>/ (2 Blender workers)

4. Download `out/frames/<scene>/` into `out/frames/` here, run `python tools/render.py assemble`, destroy the machines.

Measured 2026-10-01: builds take 10 s to 8 min (paperclips' flood is the slowest, sydney's Mantaflow next); frames
take about 1-3 s each with two workers on one 5090 (singularity's 349 frames in under 4 minutes).

## Production (4K, 60 fps)

    FPS=60 SCALE=200 WORKERS=4 /work/waitbuild_render.sh eat moon   # each scene once its build is saved
    /work/encode_scenes.sh eat moon                                 # one lossless .mkv per scene (NVENC or x264rgb)

The 2026-10-01 run: nine 5090s, ~35-40 4K frames a minute each, ~1 hour. Check each machine's GPU is busy a minute
after starting (one host never got EGL). **Next time do the final encode on a cloud machine too** (the user asked):
gather the scene .mkv files on one machine with working NVENC, upload Georgia for the subtitles, run
`python3 tools/render.py assemble --fps 60 --from-enc out/enc --out out/pdoom-blender-4k60.mp4` there and download
only that file. Doing it on the PC meant 13 minutes of CPU decoding 34 GB of lossless 4K.
