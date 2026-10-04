"""Global settings. Resolution and frame rate are render flags (render.py --w/--fps); these are the defaults."""
import os

SONG = 'out/song/paranoia.wav'
SONG_START = 135.70     # song time (s) at video t = 0: bar 48 (quiet bridge) -> the song's real ending (198.2)
# Beat-tracker glitches in the quiet bridge: (song t0, song t1, beats) -> evenly spaced beats, t0 and t1 are downbeats
GRID_FIX = [(135.70, 141.42, 8)]
LENGTH = 62.5           # video length (s): the song's last hit is t 59.32, then a 3 s end card over its tail
FPS = 60                # working frame rate (the footage is 60 fps)
W, H = 1920, 1080       # trial resolution; production is 3840x2160 at 60 fps
SHUTTER = 0.5           # motion-blur shutter as a fraction of a frame (180 degrees)
CLIPS = os.environ.get('LM_CLIPS', 'clips')
MODELS = os.environ.get('LM_MODELS', 'models')
