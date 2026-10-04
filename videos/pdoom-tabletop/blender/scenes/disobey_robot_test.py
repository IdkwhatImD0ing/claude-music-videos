"""Model/animation test for the transforming robot (scenes/disobey_robot.py). Not in the edit. Window 0-8 s.

  0.0-1.0  Clawd mode; the stutter (seam flashes at 0.35, 0.7)
  1.0-3.4  the transformation (default schedule)
  3.6 hero, 4.2 arms folded, 4.5 head shake, 5.3 punch, 6.0-7.6 walk toward camera, 7.7 stomp
"""
import math

from pdoom import chars, kit
from pdoom.sets import build_desk, phys_fstop

from scenes.disobey_robot import Robot, sparks


def build():
    sc = kit.new_scene('disobey_robot_test', window=(0.0, 16.0))
    d = build_desk(kit.collection('desk'), mood='night', exclude={'cable', 'clip', 'pen', 'notes'})
    x, y = 6.0, -12.0
    rb = Robot(kit.collection('robot'), loc=(x, y, 0), yaw=0, mode='clawd')
    rb.seam_flash(0.35)
    rb.seam_flash(0.7)
    rb.transform(1.0)
    rb.pose(3.6, 'hero', dur=0.3)
    rb.pose(4.2, 'fold', dur=0.3)
    rb.shake_head(4.5, 3)
    rb.eyes(4.5, narrow=0.45, angry=18, color='#FF3A2A')
    rb.pose(5.0, 'stand', dur=0.2)
    rb.punch(5.3, 'R')
    rb.walk(6.0, 7.5, [(x, y - 10)])
    rb.stomp(7.75, 'R')
    # a second robot built standing (mode='robot', as gpus uses it): walks, punches, stomps
    rb2 = Robot(kit.collection('robot2'), name='robot2', loc=(x + 16, y + 8, 0), yaw=0)
    rb2.walk(9.0, 10.6, [(x + 17, y - 2), (x + 14, y - 12)])
    rb2.punch(11.0, 'R')
    rb2.punch(11.5, 'L')
    rb2.stomp(12.2, 'L')
    rb2.pose(12.8, 'crouch', dur=0.3)
    rb2.pose(13.4, 'stand', dur=0.3)
    rb2.look(13.8, (x - 10, y - 30, 10))
    rb2.eyes(13.8, color='#FF1A0A', glow=2.0)
    walk_cam, _ = kit.camera('cam.walk', lens=35, loc=(x - 4, y - 52, 11), target=(x + 15, y - 6, 9), fstop=8)
    walk_cam.data.dof.aperture_fstop = phys_fstop(11)
    sp = kit.collection('sparks')
    for t, what in rb.hits:
        p = rb.anchor(t, what if what in ('hip', 'neck', 'reactor') or '.' in what else 'hip')
        sparks(sp, t, p, n=8, seed=int(t * 100) % 97)
    cam, tgt = kit.camera('cam.test', lens=40, loc=(x - 26, y - 44, 12), target=(x, y, 9), fstop=8)
    cam.data.dof.aperture_fstop = phys_fstop(11)
    kit.key(cam, 'location', 0.0, (x - 18, y - 30, 5), interp='BEZIER')
    kit.key(tgt, 'location', 0.0, (x, y, 4), interp='BEZIER')
    kit.key(cam, 'location', 3.4, (x + 20, y - 46, 14), interp='BEZIER')
    kit.key(tgt, 'location', 3.4, (x, y, 10), interp='BEZIER')
    kit.key(cam, 'location', 5.8, (x - 10, y - 50, 12), interp='BEZIER')
    kit.key(tgt, 'location', 5.8, (x, y - 4, 10), interp='BEZIER')
    kit.key(cam, 'location', 8.0, (x - 14, y - 58, 10), interp='BEZIER')
    kit.key(tgt, 'location', 8.0, (x, y - 10, 10), interp='BEZIER')
    hero, _ = kit.camera('cam.hero', lens=50, loc=(x - 22, y - 52, 13), target=(x, y, 10.5), fstop=8)
    hero.data.dof.aperture_fstop = phys_fstop(16)
    kit.cut_to(cam, 0.0)
    kit.cut_to(hero, 3.5)
    kit.cut_to(cam, 3.9)
    kit.cut_to(walk_cam, 8.0)
    kit.post(bloom=0.25, bloom_threshold=1.2, vignette=0.22)
    chars.finish()
