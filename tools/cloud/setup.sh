#!/bin/bash
# Cloud render machine setup for pdoom-blender (Vast.ai, vastai/base-image). Idempotent.
set -e
export DEBIAN_FRONTEND=noninteractive
if [ ! -x /opt/blender/blender ]; then
  apt-get update -qq
  apt-get install -y -qq wget xz-utils python3 python3-pil libx11-6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxext6 \
    libxrandr2 libxinerama1 libxcursor1 libxkbcommon0 libxkbcommon-x11-0 libsm6 libice6 libdbus-1-3 libgl1 libegl1 \
    libglx0 libglvnd0 libvulkan1 libwayland-client0 libwayland-cursor0 libwayland-egl1 libfontconfig1 libfreetype6 ffmpeg >/dev/null
  cd /opt
  wget -q https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz || wget -q https://mirrors.ocf.berkeley.edu/blender/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz
  tar xf blender-5.2.2-linux-x64.tar.xz
  mv blender-5.2.2-linux-x64 blender
  rm blender-5.2.2-linux-x64.tar.xz
fi
mkdir -p /work/pdoom && cd /work/pdoom
[ -f /root/pdoom.tar ] && tar xf /root/pdoom.tar && rm /root/pdoom.tar
[ -f /root/winfonts.tar ] && tar xf /root/winfonts.tar -C /work && rm /root/winfonts.tar
mkdir -p out/blend out/cache out/frames out/wip out/logs
/opt/blender/blender --version | head -1
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
nproc
