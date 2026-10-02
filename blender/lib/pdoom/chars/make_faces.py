"""Paints the researcher's face atlas (faces.png): 12 painted peg-doll expressions in a 4 x 3 grid of 512 px slots.

Run with the system Python (Pillow): python blender/lib/pdoom/chars/make_faces.py
Deterministic; re-run after changing a face. Each slot maps angles on the head sphere: x = yaw -60..60 deg (0 = the
front), y = pitch 45 (top) .. -75 (bottom) deg, both at 512 px per 120 deg (looks.face_head does the inverse in the shader). The glasses' lenses
are centred at yaw +-21, pitch 0 with an angular radius of ~17 deg, so eyes sit inside them and brows just above.
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFilter

FACES = ['neutral', 'blink', 'nervous', 'happy', 'proud', 'shock', 'scared', 'sad', 'talk', 'determined', 'awe', 'wince']
SLOT, SS = 512, 3
PPD = SLOT / 120.0 * SS           # supersampled pixels per degree
INK = (27, 20, 17, 255)
WHITE = (251, 247, 239, 255)
BROW = (58, 42, 32, 255)
LIP = (112, 40, 36, 255)
MOUTH = (70, 18, 20, 255)
TONGUE = (214, 104, 104, 255)
BLUSH = (242, 128, 120, 110)
SWEAT = (140, 200, 255, 235)
EX, EZ = 21.0, 0.0                # eye centres (deg)
BZ = 22.5                         # brow height
MZ = -25.5                        # mouth height
K = 1.3                           # feature scale


def P(yaw, pitch):
    return ((yaw + 60) * PPD, (45 - pitch) * PPD)


class Face:
    def __init__(self):
        self.im = Image.new('RGBA', (SLOT * SS, SLOT * SS), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.blush_layer = Image.new('RGBA', self.im.size, (0, 0, 0, 0))

    def oval(self, cx, cz, w, h, fill):
        x0, y0 = P(cx - w / 2, cz + h / 2)
        x1, y1 = P(cx + w / 2, cz - h / 2)
        self.d.ellipse((x0, y0, x1, y1), fill=fill)

    def line(self, pts, width, fill):
        q = [P(*p) for p in pts]
        wpx = width * PPD
        self.d.line(q, fill=fill, width=int(round(wpx)), joint='curve')
        for p in (q[0], q[-1]):
            r = wpx / 2
            self.d.ellipse((p[0] - r, p[1] - r, p[0] + r, p[1] + r), fill=fill)

    def poly(self, pts, fill):
        self.d.polygon([P(*p) for p in pts], fill=fill)

    def blush(self, k=1.0):
        d = ImageDraw.Draw(self.blush_layer)
        for s in (-1, 1):
            cx, cz, r = s * 33, -12, 6.0
            x0, y0 = P(cx - r, cz + r)
            x1, y1 = P(cx + r, cz - r)
            c = BLUSH[:3] + (int(BLUSH[3] * k),)
            d.ellipse((x0, y0, x1, y1), fill=c)

    def done(self):
        bl = self.blush_layer.filter(ImageFilter.GaussianBlur(4 * PPD))
        out = Image.alpha_composite(bl, self.im)
        return out.resize((SLOT, SLOT), Image.LANCZOS)


def arc(cx, cz, rx, rz, a0, a1, n=24):
    return [(cx + rx * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cz + rz * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


# ---------------------------------------------------------------------------------------------- features


def eyes_dot(f, w=7.0, h=9.5, dz=0.0, look=(0.0, 0.0), hl=True):
    w, h = w * K, h * K
    for s in (-1, 1):
        cx, cz = s * EX + look[0], EZ + dz + look[1]
        f.oval(cx, cz, w, h, INK)
        if hl:
            f.oval(cx - w * 0.2, cz + h * 0.22, w * 0.34, w * 0.34, WHITE)


def eyes_wide(f, r=6.8, pupil=2.6, look=(0.0, 0.0), sparkle=False):
    r, pupil = r * K * 0.95, pupil * K
    for s in (-1, 1):
        cx, cz = s * EX, EZ
        f.oval(cx, cz, 2 * r + 1.2, 2 * r + 1.2, INK)
        f.oval(cx, cz, 2 * r, 2 * r, WHITE)
        f.oval(cx + look[0], cz + look[1], pupil * 2, pupil * 2, INK)
        if sparkle:
            f.oval(cx + look[0] - pupil * 0.4, cz + look[1] + pupil * 0.45, pupil * 0.7, pupil * 0.7, WHITE)


def eyes_closed(f, up=False, w=9.0, depth=3.2, width=1.9):
    w, depth, width = w * K, depth * K, width * K
    for s in (-1, 1):
        cx = s * EX
        if up:   # happy ^ (arch)
            f.line(arc(cx, EZ - depth * 0.6, w / 2, depth, 10, 170), width, INK)
        else:    # relaxed/closed (a smile-shaped curve)
            f.line(arc(cx, EZ + depth * 0.5, w / 2, depth, 190, 350), width, INK)


def eyes_squeeze(f):
    for s in (-1, 1):
        cx = s * EX
        k = -s  # '>' on the left eye, '<' on the right (pointing inward)
        f.line([(cx - k * 4.2, EZ + 3.6), (cx + k * 3.0, EZ), (cx - k * 4.2, EZ - 3.6)], 2.0, INK)


def brows(f, lift=0.0, tilt=0.0, curve=1.6, w=12.0, width=2.2):
    w, width = w * 1.15, width * 1.25
    """tilt > 0: inner ends up (worried); tilt < 0: inner ends down (angry)."""
    for s in (-1, 1):
        cx = s * EX
        pts = []
        for i in range(13):
            u = i / 12 - 0.5          # -0.5 inner .. 0.5 outer for the right side (s=1)
            x = cx + s * u * w
            z = BZ + lift + curve * (1 - (2 * u) ** 2) - tilt * u * 2
            pts.append((x, z))
        f.line(pts, width, BROW)


def mouth_smile(f, w=11.0, depth=3.2, width=1.8, dz=0.0, tilt=0.0):
    w, depth, width = w * K, depth * K, width * K
    pts = arc(0, MZ + depth + dz, w / 2, depth, 200, 340)
    pts = [(x, z + tilt * x / w) for x, z in pts]
    f.line(pts, width, LIP)


def mouth_frown(f, w=9.0, depth=2.4, width=1.8):
    w, depth, width = w * K, depth * K, width * K
    f.line(arc(0, MZ - depth * 0.8, w / 2, depth, 20, 160), width, LIP)


def mouth_flat(f, w=8.0, width=1.8):
    w, width = w * K, width * K
    f.line([(-w / 2, MZ), (w / 2, MZ)], width, LIP)


def mouth_wavy(f, w=11.0, amp=1.0, width=1.7, open_=False):
    w, amp, width = w * K, amp * K, width * K
    pts = [(-w / 2 + w * i / 30, MZ + amp * math.sin(i / 30 * 3 * 2 * math.pi)) for i in range(31)]
    if open_:
        top = [(x, z + 1.6) for x, z in pts]
        f.poly(top + list(reversed([(x, z - 1.6) for x, z in pts])), MOUTH)
        f.line(top, 1.2, LIP)
        f.line([(x, z - 1.6) for x, z in pts], 1.2, LIP)
    else:
        f.line(pts, width, LIP)


def mouth_open(f, w=12.0, h=7.0, dz=0.0, tongue=True):
    w, h = w * K, h * K
    """A D-shaped open grin: flat top, round bottom."""
    top = MZ + 2.0 + dz
    pts = [(-w / 2, top), (w / 2, top)] + arc(0, top, w / 2, h, 0, -180, 30)[1:-1]
    f.poly(pts, MOUTH)
    if tongue:
        f.oval(0, top - h * 0.72, w * 0.5, h * 0.45, TONGUE)
    f.line([(-w / 2, top), (w / 2, top)], 1.2, LIP)


def mouth_o(f, w=5.5, h=7.5, dz=0.0):
    w, h = w * K, h * K
    f.oval(0, MZ + dz, w + 1.2, h + 1.2, LIP)
    f.oval(0, MZ + dz, w, h, MOUTH)
    f.oval(0, MZ + dz - h * 0.25, w * 0.6, h * 0.35, TONGUE)


def mouth_grimace(f, w=12.0, h=4.2):
    w, h = w * K, h * K
    x0, x1, z0, z1 = -w / 2, w / 2, MZ - h / 2, MZ + h / 2
    f.poly([(x0, z1), (x1, z1), (x1, z0), (x0, z0)], LIP)
    f.poly([(x0 + 0.7, z1 - 0.7), (x1 - 0.7, z1 - 0.7), (x1 - 0.7, z0 + 0.7), (x0 + 0.7, z0 + 0.7)], WHITE)
    for k in range(1, 4):
        x = x0 + w * k / 4
        f.line([(x, z1 - 0.6), (x, z0 + 0.6)], 0.6, LIP)
    f.line([(x0 + 0.6, MZ), (x1 - 0.6, MZ)], 0.6, LIP)


def sweat(f, cx=41.0, cz=16.0, s=1.0):
    f.poly([(cx, cz + 5.5 * s)] + arc(cx, cz, 2.7 * s, 2.9 * s, 25, -205, 30), SWEAT)
    f.oval(cx - 0.8 * s, cz + 0.6 * s, 1.1 * s, 1.5 * s, (255, 255, 255, 220))


# ---------------------------------------------------------------------------------------------- expressions


def paint(name):
    f = Face()
    if name == 'neutral':
        f.blush(0.8); eyes_dot(f); brows(f); mouth_smile(f, w=9.0, depth=1.8)
    elif name == 'blink':
        f.blush(0.8); eyes_closed(f, depth=2.2); brows(f); mouth_smile(f, w=9.0, depth=1.8)
    elif name == 'nervous':
        f.blush(0.5); eyes_dot(f, w=6.0, h=8.0); brows(f, lift=1.5, tilt=3.2, curve=0.6); mouth_wavy(f); sweat(f)
    elif name == 'happy':
        f.blush(1.3); eyes_closed(f, up=True, depth=3.4); brows(f, lift=2.2); mouth_open(f, w=13.0, h=7.0)
    elif name == 'proud':
        f.blush(1.1); eyes_closed(f, depth=2.6); brows(f, lift=3.0, curve=2.2); mouth_smile(f, w=13.0, depth=3.4, width=2.0, tilt=1.5)
    elif name == 'shock':
        f.blush(0.3); eyes_wide(f); brows(f, lift=5.0, curve=2.8); mouth_o(f)
    elif name == 'scared':
        f.blush(0.2); eyes_wide(f, r=6.2, pupil=1.8, look=(1.2, -0.8)); brows(f, lift=3.5, tilt=4.0, curve=0.4)
        mouth_wavy(f, w=12.0, amp=0.9, open_=True); sweat(f, s=1.1)
    elif name == 'sad':
        f.blush(0.4); eyes_dot(f, w=6.5, h=8.0, dz=-1.0); brows(f, lift=0.5, tilt=4.0, curve=0.2); mouth_frown(f)
    elif name == 'talk':
        f.blush(0.8); eyes_dot(f); brows(f, lift=0.8); mouth_o(f, w=6.5, h=5.2, dz=0.5)
    elif name == 'determined':
        f.blush(0.5); eyes_dot(f, w=7.0, h=8.2); brows(f, lift=-1.5, tilt=-3.6, curve=0.2, width=2.6); mouth_flat(f, w=9.0)
    elif name == 'awe':
        f.blush(1.2); eyes_wide(f, r=6.0, pupil=3.6, look=(0, 1.0), sparkle=True); brows(f, lift=3.5, curve=2.4)
        mouth_o(f, w=4.2, h=5.0, dz=1.0)
    elif name == 'wince':
        f.blush(0.6); eyes_squeeze(f); brows(f, lift=-0.5, tilt=2.5, curve=0.5); mouth_grimace(f)
    else:
        raise KeyError(name)
    return f.done()


def main():
    cols, rows = 4, 3
    atlas = Image.new('RGBA', (cols * SLOT, rows * SLOT), (0, 0, 0, 0))
    for k, name in enumerate(FACES):
        atlas.paste(paint(name), ((k % cols) * SLOT, (k // cols) * SLOT))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'faces.png')
    atlas.save(out, optimize=True)
    print(f'wrote {out}')


if __name__ == '__main__':
    main()
