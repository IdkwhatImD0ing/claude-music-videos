"""Proof on a real scene (not part of the edit): build one of the 18 scene scripts unchanged, then put its lyrics in
the picture with the one-call default presentation. The scene comes from the LYRICS_SCENE environment variable
(default 'training').

    LYRICS_SCENE=eat python tools/render.py sheet _test_lyrics_scene --from 16.7 --to 27.4 --n 16
"""
import importlib
import os

from pdoom import lyrics as ly


def build():
    sid = os.environ.get('LYRICS_SCENE', 'training')
    mod = importlib.import_module(f'scenes.{sid}')
    mod.build()
    try:
        from pdoom import chars
        chars.finish()
    except Exception:
        pass
    ly.default(sid)
