"""ilya · 131.140-140.230 · "What did Ilya see? We'll never know / Was it all for show?". The quiet, eerie counterpoint
to disobey: a closed box, a peephole, a light we never see the source of; then a theatrical reveal.

Shots (song time):
 1 131.140-132.020  The dark desk (lamp off). A small closed walnut box glows from inside: coloured light leaks from
                    its lid seam and a beam pours out of a brass peephole into the haze. The researcher walks up to it.
 2 132.020-133.380  "What did Ilya see?": three-quarter close-up. He bends to the peephole ("did"); the light plays
                    over his face and glasses, drifting through blue, violet, magenta, gold ("Ilya" 132.52: awe).
 3 133.380-134.340  "We'll never know": extreme close-up on his glasses at the peephole; on "never" (133.88) the
                    light flares white in his lenses.
 4 134.340-137.380  "know": he recoils (a white burst on 134.34), backs away, stares, trembling. The box's light
                    stutters and dies on the downbeat (136.594). Darkness.
 5 137.380-140.230  "Was it all for show?": in the dark, footlights pop on one by one ("Was") under a red velvet
                    curtain in a gilded toy proscenium. The curtain gathers up in swags ("it" 137.8 -> 139.3): the desk
                    is a puppet-theatre stage. The researcher stands centre stage by the box, hanging on marionette
                    strings; the desk lamp snaps on as his spotlight (138.412 downbeat); on "for" (139.15) his head jerks
                    up to face the house. The camera pulls back over an audience of paperclips standing in rows. Hold
                    the wide stage at 140.23 for the finale.
"""
import math

import bpy
from mathutils import Vector

from pdoom import chars, kit
from pdoom import lyrics as ly
from pdoom import timing as tm
from pdoom.sets import build_desk, phys_fstop
from pdoom.sets import geo as sgeo

from scenes.ilya_box import PEEP_LOCAL, W_BOX
from scenes.ilya_box import animate as box_light
from scenes.ilya_box import build_box
from scenes.ilya_theatre import audience, build_theatre, hook_strings, marionette

FPS = tm.FPS
B = Vector((11.0, 7.0, 0.0))           # the box
CX, FRONT_Y = 6.0, -2.0                 # the proscenium: centre x, front face y
H_STAGE = Vector((0.5, 6.5, 0.0))       # the researcher, centre stage, for the reveal

T0 = 131.14
T_WHAT, T_DID, T_ILYA, T_SEE = 132.02, 132.284, 132.524, 132.818
T_WELL, T_NEVER, T_KNOW = 133.38, 133.88, 134.34
T_DIE = 136.594
T_WAS, T_IT, T_ALL, T_FOR, T_SHOW = 137.38, 137.797, 138.445, 139.149, 140.027
T_LAMP = 138.412
T_END = 140.23
T_K1 = 143.867 - 0.5 / FPS    # the finale's first kick (its first cut): the title card's board stays until it


def _poses():
    P = chars.POSES
    P['marionette'] = dict(hips=(0, 0, 0.1), spine=(2, 0, 0), head=(16, 9, 0),
                           hands=((1.95, -1.1, 4.7), (-1.95, -1.1, 4.7)), wrist=((-25, 0, -10), (-25, 0, 10)),
                           thigh=((-3, 2, 0), (2, -2, 0)), shin=(4, 0))
    P['marionette_up'] = dict(hips=(0, 0, 0.1), spine=(-2, 0, 0), head=(-3, 0, 0),
                              hands=((2.05, -1.2, 5.3), (-2.05, -1.2, 5.3)), wrist=((-40, 0, -10), (-40, 0, 10)),
                              thigh=((-3, 2, 0), (2, -2, 0)), shin=(4, 0))


def build():
    sc = kit.new_scene('ilya')
    d = build_desk(kit.collection('desk'), mood='lamp_off', exclude={'cable', 'pen', 'notes', 'mug', 'clip'})
    _poses()

    # ------------------------------------------------------------------ the researcher: find the peeping spot
    r = chars.Researcher(kit.collection('researcher'), loc=(0, 0, 0), yaw=90.0)
    T_PEER = T_DID
    r.pose(T_PEER, 'peer', dur=0.34)
    e_off = r.anchor(T_PEER + 0.3, 'eyes')
    peep = B + Vector((-3.55, 0.0, 0.0))
    peer_root = Vector((peep.x - 0.5 - e_off.x, peep.y - e_off.y, 0.0))
    start = peer_root + Vector((-13.0, -7.0, 0.0))
    r.place(T0 - 1.0, loc=tuple(start), yaw=60.0)
    r.walk(T0 + 0.1, T_WHAT - 0.08, [tuple(peer_root + Vector((-4, -2.5, 0))), tuple(peer_root)])
    r.turn(T_WHAT + 0.05, 90.0, dur=0.2)
    r.face(T0, 'neutral')
    r.look(T0 + 0.3, B + Vector((0, 0, 8)))
    r.face(T_ILYA, 'awe')
    r.glasses_glint(T_NEVER, '#FFFFFF', dur=0.35, strength=22.0)
    r.face(T_NEVER + 0.1, 'shock')
    # know: recoil, back away, frozen
    r.pose(T_KNOW + 0.02, 'gasp', dur=0.14)
    # backs away toward the camera, clear of the laptop's front edge (y ~5.25 here) and its front-right corner
    back = peer_root + Vector((-5.5, -5.0, 0.0))
    r.walk(T_KNOW + 0.35, T_KNOW + 1.05, [tuple(back)], face='keep')
    r.pose(T_KNOW + 0.9, 'back_away', dur=0.3)
    r.face(T_KNOW + 0.6, 'scared')
    r.fidget(T_KNOW + 1.2, T_DIE + 0.6, amount=0.6)
    # the reveal: centre stage, a marionette
    # the jump to the stage lands 0.1 frame before the cut's frame (between the last exposure of shot 4 and the first
    # of shot 5, at 24 or 60 fps), and the pose snaps with it: at 60 fps a pose tween before it showed him in the
    # marionette pose (and blurred across the jump) in shot 4's last frame
    t_sw = tm.switch_frame(T_WAS * FPS - 0.5) / FPS
    r.place(t_sw, loc=tuple(H_STAGE), yaw=-8.0)
    r.pose(t_sw, 'marionette', dur=0.0)
    r.face(t_sw, 'neutral')
    r.pose(T_FOR, 'marionette_up', dur=0.1, ease='out')
    r.face(T_SHOW, 'sad')

    # ------------------------------------------------------------------ the box
    bc = kit.collection('box')
    bx = build_box(bc, loc=tuple(B), peep_z=e_off.z)
    print(f'[run] ilya: peephole at {e_off.z:.2f} cm, books {bx.base:.2f} cm')

    def level(t):
        if t < T_WHAT:
            return 0.32 + 0.1 * math.sin(2 * math.pi * (t - T0) / 1.1)
        if t < T_ILYA:
            return 0.4 + 0.6 * (t - T_WHAT) / (T_ILYA - T_WHAT)
        if t < T_KNOW:
            return 1.0 + 0.15 * math.sin(2 * math.pi * (t - T_ILYA) / 0.45)
        if t < T_DIE - 0.3:
            return 0.95 - 0.35 * (t - T_KNOW) / (T_DIE - 0.3 - T_KNOW)
        if t < T_DIE:            # the stutter before it dies
            k = int((t - (T_DIE - 0.3)) * FPS)
            return 0.6 if k % 3 == 0 else (0.15 if k % 3 == 1 else 0.45)
        if t < T_DIE + 0.09:
            return 0.25 if int((t - T_DIE) * FPS) == 1 else 0.0
        return 0.0
    box_light(bx, T0 - 0.1, T_DIE + 0.3, level, flashes=[(T_NEVER, 1.6), (T_KNOW, 3.4)],
              white=[(T_NEVER - 0.02, T_NEVER + 0.25)])
    # haze around the box so the peephole's beam shows
    hz = _haze(bc, B + Vector((-10, 0, 9)), (34, 26, 20), 0.012)
    kit.visible(hz, None, T_WAS - 0.02)

    # ------------------------------------------------------------------ room light: eerie, then a blackout
    moon = d.room.moon.data
    sgeo.keyp(moon, 'energy', T0 - 0.1, 50000.0, interp='LINEAR')
    sgeo.keyp(moon, 'energy', T_DIE, 45000.0, interp='LINEAR')
    sgeo.keyp(moon, 'energy', T_DIE + 0.25, 6000.0, interp='LINEAR')
    sgeo.keyp(moon, 'energy', T_LAMP, 6000.0, interp='LINEAR')
    sgeo.keyp(moon, 'energy', T_LAMP + 0.6, 22000.0, interp='LINEAR')
    d.laptop.screen(T0 - 0.1, glow=0.7)
    d.laptop.screen(T_DIE, glow=0.7)
    d.laptop.screen(T_DIE + 0.25, glow=0.06)
    d.laptop.screen(T_LAMP, glow=0.06)
    d.laptop.screen(T_LAMP + 0.5, glow=0.45)
    if d.room.bounce is not None:
        sgeo.keyp(d.room.bounce.data, 'energy', T0 - 0.1, 14000.0, interp='LINEAR')
        sgeo.keyp(d.room.bounce.data, 'energy', T_DIE, 14000.0, interp='LINEAR')
        sgeo.keyp(d.room.bounce.data, 'energy', T_DIE + 0.25, 2000.0, interp='LINEAR')
    # the desk lamp becomes the stage's follow spot
    # its head raised behind the proscenium's header, so the lit shade isn't a white blob under the swags
    d.lamp.aim(T_WAS - 1.0, H_STAGE + Vector((0, 0, 5)), height=48.0)
    d.lamp.click(T_LAMP)

    # ------------------------------------------------------------------ the theatre
    tc = kit.collection('theatre')
    th = build_theatre(tc, cx=CX, front_y=FRONT_Y)
    audience(tc, th)
    t_str = T_ALL
    pts = [r.anchor(t_str, 'head') + Vector((0.0, 0.0, 1.95)), r.anchor(t_str, 'hand.L') + Vector((0, -0.2, -0.3)),
           r.anchor(t_str, 'hand.R') + Vector((0, -0.2, -0.3))]
    strings = marionette(tc, pts, top_z=th.open_h + 4.0, converge=(H_STAGE.x, H_STAGE.y))
    th.objs.extend(strings)
    th.visible(T_WAS - 0.02)
    th.footlights(T_WAS + 0.02, 0.035)
    th.rise(T_IT, T_FOR + 0.15)
    sgeo.keyp(d.room.haze_density, 'default_value', T_WAS - 0.05, 0.0004, interp='LINEAR')
    sgeo.keyp(d.room.haze_density, 'default_value', T_WAS, 0.0016, interp='LINEAR')

    # ------------------------------------------------------------------ cameras
    cc = kit.collection('ilya.cams')
    # 1: the box in the dark, he walks in
    c1, t1 = kit.camera('cam.1', lens=40, loc=tuple(B + Vector((-9, -44, 7.5))), target=tuple(B + Vector((-7, 0, 6.5))),
                        coll=cc)
    _dof(c1, 8.0)
    kit.key(c1, 'location', T0, tuple(B + Vector((-9, -44, 7.5))), interp='LINEAR')
    kit.key(c1, 'location', T_WHAT, tuple(B + Vector((-8.2, -38, 7.3))), interp='LINEAR')
    # 2: three-quarter on his face at the peephole
    E = r.anchor(T_PEER + 0.3, 'eyes')
    c2, t2 = kit.camera('cam.2', lens=45, loc=tuple(E + Vector((1.1, -13.0, -1.4))), target=tuple(E + Vector((-0.2, 0, -0.9))),
                        coll=cc)
    _dof(c2, 5.6)
    kit.key(c2, 'location', T_WHAT, tuple(E + Vector((1.1, -13.0, -1.4))), interp='LINEAR')
    kit.key(c2, 'location', T_WELL, tuple(E + Vector((1.0, -11.0, -1.2))), interp='LINEAR')
    # 3: extreme close-up on the glasses
    c3, t3 = kit.camera('cam.3', lens=64, loc=tuple(E + Vector((-0.6, -6.6, 0.4))), target=tuple(E + Vector((0.3, 0, -0.25))),
                        coll=cc)
    _dof(c3, 11.0)
    kit.key(c3, 'location', T_WELL, tuple(E + Vector((-0.6, -6.6, 0.4))), interp='LINEAR')
    kit.key(c3, 'location', T_KNOW, tuple(E + Vector((-0.45, -5.6, 0.35))), interp='LINEAR')
    # 4: low beside the box, him backing away into the dark
    mid = (peer_root + back) / 2
    c4, t4 = kit.camera('cam.4', lens=35, loc=tuple(B + Vector((1.5, -29, 5.0))), target=tuple(mid + Vector((3.0, 0, 6.0))),
                        coll=cc)
    _dof(c4, 8.0)
    kit.key(c4, 'location', T_KNOW, tuple(B + Vector((1.5, -29, 5.0))), interp='LINEAR')
    kit.key(c4, 'location', T_WAS, tuple(B + Vector((2.5, -33, 5.4))), interp='LINEAR')
    # 5: the house: from the curtain back over the paperclip audience
    c5, t5 = kit.camera('cam.5', lens=32, loc=(CX, -26, 9.5), target=(CX, 2, 12.0), coll=cc)
    _dof(c5, 8.0)
    _pullback(c5, t5, T_WAS, T_END + 0.05)

    for cam, t in ((c1, T0), (c2, T_WHAT), (c3, T_WELL), (c4, T_KNOW), (c5, T_WAS)):
        kit.cut_to(cam, t)
    sc.camera = c1
    kit.post(bloom=0.35, bloom_threshold=1.0, vignette=0.3)
    chars.finish()
    # the strings follow the puppet (the head jerk on "for", the finale's hoist): bottom ends hooked to his bones
    hook_strings(strings, r.rig, ('head', 'hand.L', 'hand.R'), t_str)
    _coat_smooth(r)
    if ly.ENABLED:                 # revision 3: subtitles instead (lyrics.ENABLED)
        _lyrics(bx)
    return d, r, bx, th


def _lyrics(bx):
    """Revision 2: the lyrics in the picture. "What did Ilya see?" chalked on the box's front as sung; "We'll never"
    gilded under the peephole (the extreme close-up); "know" on a dimly lit lyric stand that goes dark with the box;
    "Was it all for show?" a neon title card hanging in front of the curtain, lighting word by word (it carries on
    into the finale's first shot, the same camera, and fades as the house lights come up)."""
    h = W_BOX / 2
    q = ly.line(44, words=(0, 4), style='chalk', support='none', max_chars=9, exit='none', t_end=T_WAS,
                place=ly.on_object(bx.root, (-1.95, -h - 0.02, 0.95), (0, -1, 0), (0, 0, 1), size=0.35, lift=0.01))
    # "We'll never": a little black museum label with gold letters beside the peephole, angled to the close-up
    cam3 = bpy.data.objects['cam.3']
    lab = bx.root.matrix_basis @ Vector((-h - 0.3, -1.0, PEEP_LOCAL - 1.02))
    to_cam = cam3.location - lab
    to_cam.z = 0.0
    g = ly.line(44, words=(4, 6), style='goldleaf', support='backing', exit='none', t_end=T_WAS, max_chars=5,
                place=ly.At(lab, face=tuple(to_cam.normalized()), size=0.185))
    # the chalk and the gilding catch a little of the box's glow (a faint self-light so they read on the dark walnut)
    done = set()
    for lyr, col, k in ((q, (0.75, 0.82, 1.0, 1.0), 0.35), (g, (1.0, 0.72, 0.35, 1.0), 0.6)):
        for pc in lyr.pieces:
            for o in [pc.obj] + [x for x in pc.extra if isinstance(x, bpy.types.Object)]:
                for sl in o.material_slots:
                    m = sl.material
                    if m is None or m.name in done or not m.use_nodes:
                        continue
                    done.add(m.name)
                    b = m.node_tree.nodes.get('Principled BSDF')
                    if b is not None:
                        b.inputs['Emission Color'].default_value = col
                        b.inputs['Emission Strength'].default_value = k
    # "know": the stand in the recoil shot, lit only faintly (it goes dark with the box)
    ly._stage_for(0.5 * (T_KNOW + T_WAS), ly.StageSpec(cells=6.0, rows=1, light=0.05), ly.collection())
    # the title card (explicit window: the finale builds this scene and keeps the shot going)
    card = ly.line(45, style='neon', color='#FFD27A', strength=6.0, max_chars=11, window=(T0, 145.0),
                   place=ly.At(Vector((CX + 7.2, FRONT_Y - 2.4, 10.4)), face=0.0, size=1.6), t_show=T_WAS - 0.02,
                   exit='fade', exit_opts=dict(dur=0.5), t_exit=140.95, t_end=T_K1)
    boards = [o for cp in card.copies for o in cp.supports if o.type == 'MESH']
    if boards:
        bpy.context.view_layer.update()
        pts = [o.matrix_world @ Vector(c) for o in boards for c in o.bound_box]
        x0, x1 = min(p.x for p in pts), max(p.x for p in pts)
        zt = max(p.z for p in pts)
        yc = sum(p.y for p in pts) / len(pts) + 0.05
        m = kit.mat('ilya.cardstring', '#E8E2D4', rough=0.8)
        for k, x in enumerate((x0 + 1.2, x1 - 1.2)):
            st = kit.cylinder(f'ilya.cardstring{k}', 0.025, 70.0, (x, yc, zt + 35.0), verts=6, m=m,
                              coll=ly.collection())
            kit.visible(st, T_WAS - 0.02, T_K1)
    ly.default('ilya')


def _coat_smooth(r):
    """Shot 2 looks at the coat from ~12 cm: one level of subdivision rounds its faceted shoulders (render only)."""
    ob = getattr(r, 'o_coat', None)
    if ob is None:
        return
    sm = ob.modifiers.new('smooth', 'SUBSURF')
    sm.levels = 0
    sm.render_levels = 1
    sm.quality = 2
    sm.boundary_smooth = 'PRESERVE_CORNERS'


def _dof(cam, f):
    cam.data.dof.aperture_fstop = phys_fstop(f)
    cam.data.dof.aperture_blades = 7


def _pullback(cam, tgt, ta, tb):
    """Hold on the curtain while the footlights come on, then a slow pull back over the house as it rises."""
    f0, f1 = int(math.floor(ta * FPS)), int(math.ceil(tb * FPS))
    for f in range(f0, f1 + 1):
        t = f / FPS
        u = min(1.0, max(0.0, (t - (T_IT - 0.1)) / (tb - (T_IT - 0.1))))
        e = u * u * (3 - 2 * u)
        e = 0.6 * e + 0.4 * u
        cam.location = (CX + 1.0 * e, -26.0 - 44.0 * e, 9.5 + 9.0 * e)
        cam.keyframe_insert('location', frame=f)
        tgt.location = (CX + 0.5 * e, 2.0 + 2.0 * e, 12.0 + 9.0 * e)
        tgt.keyframe_insert('location', frame=f)
        cam.data.lens = 32.0 - 6.0 * e
        cam.data.keyframe_insert('lens', frame=f)
    kit.set_interp(cam, 'LINEAR')
    kit.set_interp(tgt, 'LINEAR')
    kit.set_interp(cam.data, 'LINEAR')


def _haze(coll, center, size, density):
    """A local box of haze (volume scatter) so light beams show."""
    m = bpy.data.materials.new('ilya.haze')
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.remove(nt.nodes['Principled BSDF'])
    vs = nt.nodes.new('ShaderNodeVolumePrincipled')
    vs.inputs['Density'].default_value = density
    vs.inputs['Anisotropy'].default_value = 0.45
    vs.inputs['Color'].default_value = (0.9, 0.9, 0.95, 1.0)
    nt.links.new(vs.outputs[0], nt.nodes['Material Output'].inputs['Volume'])
    ob = kit.box('ilya.haze', size, tuple(center), m=m, coll=coll)
    return ob
