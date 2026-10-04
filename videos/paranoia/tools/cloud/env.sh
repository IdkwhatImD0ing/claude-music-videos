export PATH=/opt/ffmpeg/bin:/work/venv/bin:$PATH
export LM_CLIPS=/work/lm/clips
export LM_MODELS=/work/lm/models
export PYTHONUNBUFFERED=1
cd /work/lm
# CUDA 12 libs that ctranslate2 (faster-whisper) needs ship inside the venv (torch cu128 wheels); not every image has them
export LD_LIBRARY_PATH=$(ls -d /work/venv/lib/python3*/site-packages/nvidia/*/lib 2>/dev/null | tr "\n" ":")$LD_LIBRARY_PATH
