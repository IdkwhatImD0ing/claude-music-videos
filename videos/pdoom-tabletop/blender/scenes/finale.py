"""finale · 140.230-151.139 · the outro's first eight kicks: the pull-back.

Each kick is a jump cut back in scale, and each scale is its own miniature set, shot like a tabletop model (high
angle, tilt-shift depth of field, a slow motion-control rise or pull back that carries across the cuts). The light
stays night (the desk lamp, lit windows, street lamps, city lights, the moon) until the sun comes up over the
planet's rim; from space it's the sun.

Shot list (song seconds; the cuts land on the kicks):

 F0  140.230-143.867  finale_desk: ilya's pull-back over the puppet theatre keeps going. Paperclips rain on the
                      stage and the stalls like curtain-call confetti, a tide of clips rises through the audience's
                      rows; on the downbeat 142.049 the marionette strings snap and haul the researcher up and away,
                      legs dangling; the camera cranes up and tilts down over the flooded house.
 K1  143.867-144.776  finale_desk: the desk buried in clips from high above: the theatre's gilded top, the lamp and
                      the laptop lid stick out of a silver sea that spills over the desk's front edge onto a floor
                      of clips. Slow rise back.
 K2  144.776-145.685  finale_town: the room as a doll's-house model (1:6, open front and top): clips to the brim of
                      the walls, rising; a paper lantern hanging from the ceiling beam sinks into them; the night
                      window with the city behind; clips spill over the room's open front. Pull back.
 K3  145.685-146.594  finale_town: the house (a 1:48 model on a flocked baseboard, night): clips pour from every lit
                      window and the open front door and heap up around the walls; a street lamp, a picket fence,
                      foam trees. Pull back and up.
 K4  146.594-147.503  finale_town: the street (1:150): two rows of houses, every window pouring; the road is a river
                      of clips carrying a toy car; street lamps. The classic tilt-shift view down the street.
 K5  147.503-148.412  finale_world: the city at night (1:1000): towers clad in paperclips with lit windows glowing
                      through, and landmark towers that are giant paperclips standing on end; red beacons blink on
                      the kick; the towers are still rising out of a sea of clips.
 K6  148.412-149.321  finale_world: the coast from the air (a relief model on a curved base): land that glitters
                      like steel, city lights along the shore, a black sea with the moon's path on it, the clip
                      tide spreading out over the water; the planet's rim with the first dawn light on it.
 K7  149.321-150.230  finale_world: space: a hand-painted globe (cotton-wool clouds, luminous-paint cities on its
                      night side) turns into a ball of paperclips in spreading patches; the sun from the left; a
                      star cloth behind. Pull back.
 K8  150.230-151.139  finale_world: the Earth fully clips, turning, rim-lit by the sun; a long pull back; the paper
                      moon on its string drifts into the foreground, soft (the coda lands on it).

Environment for iterating: FINALE_PARTS=desk,town,world (default all).
"""
from __future__ import annotations

import os

import bpy

from pdoom import chars, kit

from scenes import finale_common as F


def build():
    parts = set((os.environ.get('FINALE_PARTS') or 'desk,town,world').split(','))
    from scenes import finale_desk
    finale_desk.build('finale')
    sc = bpy.context.scene
    if 'town' in parts:
        from scenes import finale_town
        finale_town.build()
    if 'world' in parts:
        from scenes import finale_world
        finale_world.build()
    sc.frame_set(sc.frame_start)
    chars.finish()
    return sc
