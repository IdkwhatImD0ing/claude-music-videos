"""The `loom` scene's baby photo: "From masked pre-training days".

render_baby_photo() builds a tiny photo studio far below the room (a pastel paper sweep, a knitted cushion, a toy
block and a rattle), sits a small Clawd on it wearing the smiley mask with his arms up, renders it with EEVEE during
build() and ages the print with numpy (faded warm tones, lifted blacks, vignette, seeded grain). build_frame() puts
it in a little walnut picture frame with a cream mat and a glass front, standing on the desk on an easel strut.

Call render_baby_photo() FIRST in build(), right after kit.new_scene(), so nothing else is in the scene.
"""
from __future__ import annotations

import math
import os
import bpy
from mathutils import Matrix, Vector

from pdoom import chars, kit
from pdoom.sets import geo
from pdoom.sets import materials as M

OFF = Vector((0.0, 0.0, -3000.0))
PHOTO_W, PHOTO_H = 720, 900


def _sweep(coll, name, m, w=46.0, depth=26.0, h=30.0, r=8.0):
    """A photographer's paper sweep: floor, a curve, a back wall."""
    verts, faces = [], []
    prof = [(-depth, 0.0), (-r * 0.2, 0.0)]
    for k in range(1, 9):
        a = math.radians(90 * k / 8)
        prof.append((r * math.sin(a) - r * 0.2, r - r * math.cos(a)))
    prof.append((prof[-1][0], h))
    for i, (y, z) in enumerate(prof):
        verts += [(-w / 2, y, z), (w / 2, y, z)]
    for i in range(len(prof) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    o = geo.mesh_obj(name, verts, faces, coll, m, smooth=True)
    return o


def render_baby_photo(path: str, t_render: float):
    """Render the baby photo to `path` (PNG) and return an aged, packed bpy image of it."""
    import numpy as np
    sc = bpy.context.scene
    coll = kit.collection('photo.studio')
    o = OFF
    backdrop = M.solid('photo.paper', '#A8C6E6', rough=0.9)
    sw = _sweep(coll, 'photo.sweep', backdrop)
    sw.location = o + Vector((0, 8.0, 0))
    cush = kit.box('photo.cushion', (11.0, 7.5, 1.1), tuple(o + Vector((0, 0.5, 0.55))), bevel=0.45, segments=4,
                   m=M.solid('photo.knit', '#F3E3A4', rough=0.95, sheen=0.8, micro=(14.0, 0.12)), coll=coll)
    blk = kit.box('photo.block', (1.7, 1.7, 1.7), tuple(o + Vector((-4.4, -1.6, 1.1 + 0.85))), bevel=0.15,
                  segments=2, m=M.solid('photo.blockwood', '#E7C58F', rough=0.5, coat=0.3), coll=coll)
    blk.rotation_euler = (0, 0, math.radians(24))
    letter = geo.text_mesh('photo.block.A', 'A', 1.25, coll=coll, m=M.solid('photo.blockpaint', '#C8372D', rough=0.4),
                           extrude=0.03)
    letter.parent = blk
    letter.matrix_parent_inverse = Matrix.Identity(4)
    letter.location = (0.0, -0.86, 0.0)
    letter.rotation_euler = (math.radians(90), 0, 0)
    rat = kit.sphere('photo.rattle', 0.75, tuple(o + Vector((4.6, -1.2, 1.1 + 0.75))),
                     m=M.plastic('photo.rattle.m', '#6FB7A8', rough=0.25, coat=0.6), coll=coll, subdiv=3)
    stick = kit.cylinder('photo.rattle.stick', 0.16, 2.2, tuple(o + Vector((5.7, -2.3, 1.1 + 0.35))), verts=12,
                         m=M.plastic('photo.rattle.h', '#F2A5B6', rough=0.3), coll=coll,
                         rot=(math.radians(90), 0, math.radians(-45)))
    # the baby: a smaller Clawd sitting on the cushion, in the smiley mask, arms up
    c = chars.Clawd(kit.collection('photo.baby'), name='baby', loc=tuple(o + Vector((0.2, 0.6, 1.1))), yaw=-14.0,
                    scale=0.78, blink=False, glow_light=False)
    c.wear(t_render - 2.0, 'mask')
    c.arms(t_render - 1.5, (58, 18, 0))
    c.T['body.rot'].set(t_render - 1.5, (-5.0, 3.0, 0.0))
    c.bake()
    # lights: soft key, fill, a hair light
    lights = []
    lights.append(kit.area('photo.key', tuple(o + Vector((-16, -22, 18))), tuple(o + Vector((0, 0, 3))), power=9000.0,
                           size=16.0, color='#FFF1DE', coll=coll))
    lights.append(kit.area('photo.fill', tuple(o + Vector((20, -18, 8))), tuple(o + Vector((0, 0, 3))), power=3200.0,
                           size=20.0, color='#E8F0FF', coll=coll))
    lights.append(kit.area('photo.rim', tuple(o + Vector((6, 14, 16))), tuple(o + Vector((0, 0, 4))), power=5000.0,
                           size=6.0, color='#FFFFFF', coll=coll))
    cd = bpy.data.cameras.new('photo.cam')
    cd.lens, cd.sensor_width = 55, 36
    cam = bpy.data.objects.new('photo.cam', cd)
    coll.objects.link(cam)
    cam.location = o + Vector((0.4, -23.5, 6.0))
    kit.aim(cam, o + Vector((0.0, 0.0, 3.3)))
    cd.dof.use_dof = True
    cd.dof.focus_distance = (Vector(cam.location) - (o + Vector((0.2, -1.5, 4.0)))).length
    cd.dof.aperture_fstop = 4.0 * sc.unit_settings.scale_length
    # render it
    r = sc.render
    keep = (r.resolution_x, r.resolution_y, r.resolution_percentage, sc.eevee.taa_render_samples,
            r.use_motion_blur, sc.camera, r.filepath)
    r.resolution_x, r.resolution_y, r.resolution_percentage = PHOTO_W, PHOTO_H, 100
    sc.eevee.taa_render_samples = 48
    r.use_motion_blur = False
    sc.camera = cam
    sc.frame_set(int(round(t_render * 24)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    (r.resolution_x, r.resolution_y, r.resolution_percentage, sc.eevee.taa_render_samples, r.use_motion_blur,
     sc.camera, r.filepath) = keep
    for lo in lights + [cam]:
        bpy.data.objects.remove(lo, do_unlink=True)
    for ob in (sw, cush, blk, letter, rat, stick):
        ob.hide_render = True
    # age the print
    raw = bpy.data.images.load(path, check_existing=False)
    w, h = raw.size
    px = np.array(raw.pixels[:], dtype=np.float32).reshape(h, w, 4)[:, :, :3]
    gray = (px[:, :, 0] * 0.3 + px[:, :, 1] * 0.59 + px[:, :, 2] * 0.11)[:, :, None]
    px = px * 0.72 + gray * 0.28
    px = px * np.array([1.05, 0.99, 0.84], np.float32) + np.array([0.035, 0.018, 0.0], np.float32)
    px = 0.09 + 0.86 * px
    yy, xx = np.mgrid[0:h, 0:w]
    rr = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    px *= (1.0 - 0.32 * rr)[:, :, None]
    rng = np.random.default_rng(128)
    px += rng.normal(0.0, 0.022, (h, w, 1)).astype(np.float32)
    px = np.clip(px, 0.0, 1.0)
    im = bpy.data.images.new('loom.babyphoto', w, h, alpha=True)
    rgba = np.concatenate([px, np.ones((h, w, 1), np.float32)], axis=2)
    im.pixels.foreach_set(rgba.ravel())
    im.pack()
    bpy.data.images.remove(raw)
    return im, c


def build_frame(coll, loc, yaw_deg: float, img, name='photo.frame'):
    """A walnut picture frame (7.4 x 9.2 cm) with a cream mat, the photo behind glass, leaning back on an easel
    strut. Returns (root, glass)."""
    walnut = M.solid('photo.walnut', '#4B2E1C', rough=0.35, coat=0.7, coat_rough=0.08, micro=(10.0, 0.03))
    gilt = M.brass('photo.gilt', '#C8A45A', 0.25)
    mat_board = M.solid('photo.mat', '#EFE7D6', rough=0.85, micro=(30.0, 0.05))
    root = kit.empty(name, tuple(loc), coll, 'ARROWS', 3.0)
    root.rotation_euler = (0, 0, math.radians(yaw_deg))
    lean = kit.empty(f'{name}.lean', (0, 0, 0), coll, 'PLAIN_AXES', 1.0)
    geo.attach(lean, root, Vector((0, 0, 0)), (math.radians(-12), 0, 0))
    W, H, mw, t = 7.4, 9.2, 0.95, 0.7
    # the frame: four mitred bars in the local XZ plane (the face toward -Y)
    for nm, sx, sz, px_, pz in (('top', W, mw, 0, H - mw / 2), ('bottom', W, mw, 0, mw / 2),
                                ('left', mw, H, -W / 2 + mw / 2, H / 2), ('right', mw, H, W / 2 - mw / 2, H / 2)):
        b = geo.box(f'{name}.{nm}', (sx, t, sz), (0, 0, 0), bev=0.18, segments=3, m=walnut, coll=coll)
        geo.attach(b, lean, Vector((px_, 0, pz)))
    # a thin gilt slip inside the moulding
    for nm, sx, sz, px_, pz in (('slip.t', W - 2 * mw, 0.12, 0, H - mw - 0.06), ('slip.b', W - 2 * mw, 0.12, 0, mw + 0.06),
                                ('slip.l', 0.12, H - 2 * mw, -W / 2 + mw + 0.06, H / 2),
                                ('slip.r', 0.12, H - 2 * mw, W / 2 - mw - 0.06, H / 2)):
        b = geo.box(f'{name}.{nm}', (sx, t * 0.8, sz), (0, 0, 0), m=gilt, coll=coll)
        geo.attach(b, lean, Vector((px_, -0.02, pz)))
    # the mat with its window, and the photo behind it
    iw, ih = W - 2 * mw, H - 2 * mw
    ow, oh = 4.3, 5.4
    mat_v = [(-iw / 2, 0, -ih / 2), (iw / 2, 0, -ih / 2), (iw / 2, 0, ih / 2), (-iw / 2, 0, ih / 2),
             (-ow / 2, 0, -oh / 2 + 0.25), (ow / 2, 0, -oh / 2 + 0.25), (ow / 2, 0, oh / 2 + 0.25),
             (-ow / 2, 0, oh / 2 + 0.25)]
    mat_f = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    mo = geo.mesh_obj(f'{name}.mat', mat_v, mat_f, coll, mat_board)
    geo.attach(mo, lean, Vector((0, -0.05, H / 2)))
    pm = M.new_mat('photo.print')[0]
    b = M.principled(pm)
    tex = M.node(pm.node_tree, 'ShaderNodeTexImage', (-400, 0))
    tex.image = img
    M.link(pm.node_tree, tex.outputs['Color'], M.sin(b, 'Base Color'))
    M.setin(b, 'Roughness', 0.3)
    M.setin(b, 'Coat Weight', 0.3)
    pw, ph = 4.5, 4.5 * PHOTO_H / PHOTO_W
    po = geo.mesh_obj(f'{name}.photo', [(-pw / 2, 0, -ph / 2), (pw / 2, 0, -ph / 2), (pw / 2, 0, ph / 2),
                                         (-pw / 2, 0, ph / 2)], [(0, 1, 2, 3)], coll, pm,
                      uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    geo.attach(po, lean, Vector((0, 0.05, H / 2 + 0.25)))
    back = geo.box(f'{name}.back', (W - 0.4, 0.15, H - 0.4), (0, 0, 0), m=M.cardboard('photo.backing'), coll=coll)
    geo.attach(back, lean, Vector((0, 0.3, H / 2)))
    glass = geo.mesh_obj(f'{name}.glass', [(-iw / 2, 0, -ih / 2), (iw / 2, 0, -ih / 2), (iw / 2, 0, ih / 2),
                                           (-iw / 2, 0, ih / 2)], [(0, 1, 2, 3)], coll,
                         M.glass('photo.glass', tint='#FFFFFF', rough=0.02))
    geo.attach(glass, lean, Vector((0, -0.16, H / 2)))
    glass.visible_shadow = False
    # the easel strut behind
    strut = geo.box(f'{name}.strut', (1.1, 0.2, 7.0), (0, 0, 0), bev=0.05, m=M.cardboard('photo.backing'), coll=coll)
    geo.attach(strut, root, Vector((0, 2.4, 3.2)), (math.radians(28), 0, 0))
    return root, glass


def baby_bottle(coll, loc):
    """A tiny baby bottle standing on the desk (2 cm across, 5.6 tall): milky glass, a pastel ring and a teat."""
    body = geo.lathe('photo.bottle', [(0.0, 0.0), (0.95, 0.0), (1.0, 0.12), (1.0, 3.6), (0.9, 3.9), (0.0, 3.9)],
                     segs=32, coll=coll, m=M.solid('photo.milk', '#F4F1EA', rough=0.2, coat=0.9, coat_rough=0.05,
                                                     sss=0.4, sss_radius=(0.6, 0.6, 0.5)))
    body.location = loc
    ring = geo.lathe('photo.bottle.ring', [(0.0, 3.8), (1.05, 3.8), (1.08, 4.5), (0.0, 4.5)], segs=32, coll=coll,
                     m=M.plastic('photo.bottle.ringm', '#8FC7E8', rough=0.3, coat=0.5))
    geo.attach(ring, body)
    teat = geo.lathe('photo.bottle.teat', [(0.0, 4.5), (0.7, 4.5), (0.55, 4.9), (0.3, 5.1), (0.3, 5.4), (0.2, 5.6),
                                           (0.0, 5.62)], segs=24, coll=coll,
                     m=M.solid('photo.teat', '#E8B98C', rough=0.35, sss=0.3))
    geo.attach(teat, body)
    for k in range(3):
        tick = kit.box(f'photo.bottle.tick{k}', (0.5, 0.05, 0.04), (0, 0, 0), m=M.ink('photo.ink', '#6A8FB0'),
                       coll=coll)
        geo.attach(tick, body, Vector((0.0, -1.0, 1.2 + 0.7 * k)))
    return body
