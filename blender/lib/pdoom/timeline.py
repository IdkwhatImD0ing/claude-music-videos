"""The edit: one scene per window. Windows are the same downbeat-aligned sections the donghua used (tuned to the
music); the contents are this video's (docs/TREATMENT.md). A scene script renders exactly its window's global frames.
"""
from .timing import DURATION, t2f

EDIT = [
    ('boot', 0.0),
    ('training', 5.692),
    ('eat', 16.601),
    ('room', 27.509),
    ('singularity', 38.418),
    ('sydney', 52.962),
    ('moon', 62.053),
    ('safe', 67.507),
    ('backprop', 74.779),
    ('leftturn', 82.052),
    ('paperclips', 89.324),
    ('fuse', 102.051),
    ('disobey', 109.323),
    ('gpus', 116.595),
    ('loom', 123.868),
    ('ilya', 131.140),
    ('finale', 140.230),
    ('coda', 151.139),
]


def window(scene_id: str) -> tuple[float, float]:
    ids = [e[0] for e in EDIT]
    i = ids.index(scene_id)
    t0 = EDIT[i][1]
    t1 = EDIT[i + 1][1] if i + 1 < len(EDIT) else DURATION
    return t0, t1


def frames(scene_id: str) -> tuple[int, int]:
    """[first, last] global frames of a scene (inclusive). Consecutive scenes tile the song without gaps."""
    t0, t1 = window(scene_id)
    return t2f(t0), t2f(t1) - 1


def frames_at(scene_id: str, fps: int) -> tuple[int, int]:
    """[first, last] output frames of a scene at another frame rate (output frame k shows scene frame k * 24 / fps).
    A scene owns every output frame whose scene frame falls in [its first 24 fps frame, the next scene's first), so
    the cuts land where they do at 24 fps and consecutive scenes tile without gaps."""
    f0, f1 = frames(scene_id)
    lo = -(-f0 * fps // 24)                       # ceil(f0 * fps / 24)
    hi = -(-(f1 + 1) * fps // 24) - 1
    return lo, hi


def scene_at(t: float) -> str:
    cur = EDIT[0][0]
    for sid, t0 in EDIT:
        if t >= t0:
            cur = sid
    return cur
