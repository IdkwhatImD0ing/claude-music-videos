#!/bin/bash
# Cloud machine setup for the PARANOIA montage (Vast.ai, vastai/base-image, RTX 5090). Idempotent.
# Installs: a static ffmpeg with NVENC/NVDEC, a Python venv with CUDA torch, PyAV, librosa, demucs, beat_this,
# faster-whisper, and the RIFE frame-interpolation model. Work dir: /work/lm (clips in /work/lm/clips).
set -e
export DEBIAN_FRONTEND=noninteractive
mkdir -p /work/lm/clips /work/lm/out /work/lm/models
if ! command -v python3.12 >/dev/null 2>&1 && ! python3 -c 'import sys; assert sys.version_info >= (3, 10)' 2>/dev/null; then
  apt-get update -qq && apt-get install -y -qq python3 python3-venv >/dev/null
fi
apt-get update -qq >/dev/null 2>&1 || true
apt-get install -y -qq wget xz-utils git python3-venv libsndfile1 fonts-dejavu-core >/dev/null 2>&1 || true

# ffmpeg: BtbN static n8.1 build (master/9.0 need NVENC API 13.1 = driver 610+; Ubuntu's ffmpeg is old)
if [ ! -x /opt/ffmpeg/bin/ffmpeg ]; then
  mkdir -p /opt/ffmpeg && cd /opt/ffmpeg
  wget -q https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-n8.1-latest-linux64-gpl-8.1.tar.xz
  tar xf ffmpeg-n8.1-*.tar.xz --strip-components=1 && rm -f ffmpeg-n8.1-*.tar.xz
fi
# RIFE 4.25 weights (vs-rife release, MIT)
[ -s /work/lm/models/flownet_v4.25.pkl ] || wget -q -O /work/lm/models/flownet_v4.25.pkl   https://github.com/HolyWu/vs-rife/releases/download/model/flownet_v4.25.pkl
# CUDA forward-compat libs in the image break cuInit on some 5090 hosts: keep them out of the loader path
for f in /etc/ld.so.conf.d/*compat*; do [ -e "$f" ] && mv "$f" "$f.off"; done; ldconfig || true

if [ ! -x /work/venv/bin/python ]; then
  python3 -m venv /work/venv
  /work/venv/bin/pip install -q --upgrade pip
  /work/venv/bin/pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
  /work/venv/bin/pip install -q numpy scipy pillow av librosa soundfile soxr demucs faster-whisper \
    "https://github.com/CPJKU/beat_this/archive/main.zip"
fi
echo "--- versions"
/opt/ffmpeg/bin/ffmpeg -hide_banner -version | head -1
/work/venv/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.cuda.get_device_name(0))"
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
nproc
echo "--- nvenc test"
if /opt/ffmpeg/bin/ffmpeg -hide_banner -loglevel error -f lavfi -i testsrc=s=1920x1080:d=1 -c:v h264_nvenc -f null - ; then
  echo NVENC_OK; else echo NVENC_FAIL; fi
if /opt/ffmpeg/bin/ffmpeg -hide_banner -loglevel error -hwaccel cuda -f lavfi -i testsrc=s=640x360:d=1 -f null - ; then
  echo CUDA_FFMPEG_OK; fi
echo SETUP_OK
