"""pdoom.sets: the shared desk world (docs/lib/sets.md).

    from pdoom.sets import build_desk
    d = build_desk(kit.collection('desk'), mood='night')
"""
from .desk import ALL_PARTS, LAYOUT, MOODS, Desk, build_desk, lighting, phys_fstop  # noqa: F401
from .gauge import CRACK_T, DOOMS, Gauge, build_gauge, dial_angle  # noqa: F401
from .lamp import Lamp, build_lamp  # noqa: F401
from . import geo, materials, props, room  # noqa: F401
