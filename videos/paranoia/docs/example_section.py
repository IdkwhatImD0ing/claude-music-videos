"""Example section (the engine test). Real sections live in sections/sNN_*.py; this file is not loaded."""
from engine.api import *

SPAN = (0.0, 8.0)
A = 'League-of-Legends__2026-02-20__01-11-57.mp4'
B = 'League-of-Legends__2026-02-22__20-45-40.mp4'


def build(E):
    k = kills(A)
    b = [song.beat(i) for i in range(12)]
    r = velocity([(b[2], k[0]), (b[4], k[1]), (b[5], k[2])], 0.0, k[0] - 2.0, 4.2, hit=0.3)
    E.shot(0.0, 4.2, A, r, cam=lambda t: Cam(zoom=1.15 + 0.1 * song.pulse(t, 'kick'), cy=0.48), hits=[b[2], b[4]])
    for t in (b[2], b[4], b[5]):
        impact(E, t, 1.0)
    E.layer(b[1], b[3], L.slam('PARANOIA', b[1], size=0.22, glow=0.8))
    E.layer(b[3], b[6], L.lock(b[3], b[6], 0.5, 0.45))
    E.layer(b[4], b[6], L.counter('DOUBLE KILL', b[4]))
    E.top(0, 8, L.rec())
    E.shot(3.9, 8.0, B, Remap.constant(3.9, kills(B)[0] - 1.5, 0.6, 8.0), cam=Cam(zoom=1.1))
    E.transition(3.9, 4.2, T.zoom())
    E.sfx('whoosh', 4.05)
