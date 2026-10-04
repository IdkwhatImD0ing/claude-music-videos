"""Shared characters for the Blender video: Clawd (vinyl toy), Sydney (jelly Clawd) and the peg-doll researcher.

    from pdoom import chars
    c = chars.Clawd(coll, loc=(0, 0, 0))
    r = chars.Researcher(coll, loc=(12, 4, 0), yaw=-30)
    ...                                   # API calls keyed by song time
    chars.finish()                        # bake the stop-motion keys (runs automatically on save/render too)

Docs: docs/lib/chars.md.
"""
from .rig import EASE, REGISTRY, finish_all  # noqa: F401
from .clawd import ARM_POSES, EYE_SHAPES, PROPS, Clawd, Path, sydney  # noqa: F401
from . import props  # noqa: F401


def finish():
    """Bake every character created in this build (call once at the end of build())."""
    finish_all()


def __getattr__(name):
    # the researcher module is imported lazily (it loads the face atlas)
    if name in ('Researcher', 'POSES', 'FACES'):
        from . import researcher
        return getattr(researcher, name)
    raise AttributeError(name)
