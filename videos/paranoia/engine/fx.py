"""GPU image effects for the montage. Images are float32 torch tensors [3,H,W] in 0..1 (sRGB-ish) on CUDA.
Every function is pure: same inputs (and seed) -> same pixels. Coordinates are fractions of the frame (0..1, origin
top-left) unless a name says px.

Camera
  Cam(zoom, cx, cy, rot, ox, oy, yaw, pitch, lens)   cx,cy = source point (0..1) at screen centre; ox,oy screen
                                                      offset (fraction of width/height); rot degrees; yaw/pitch 3D
                                                      tilt in degrees; lens = barrel (+) / pincushion (-)
  camera(src, W, H, cam)            source frame -> output frame (reflection padding: shakes never show black)
  shake(t, amount, freq=18, seed=0) -> (ox, oy, rot) seeded noise, amount = fraction of the frame

Blurs / motion          zoom_blur  dir_blur  blur  spin_blur
Light / colour          bloom  grade  vignette  flash  exposure  invert  duotone  ink  posterize  tint  color_pop
                        spotlight  light_leak  grain  scanlines  chroma (rgb_split)
Distortion              shockwave  glitch  pixelate  mirror  kaleido  ripple  slices
Graphics (SDF, crisp)   ring  disc  brackets  crosshair  line  rect  speed_lines  letterbox
Compositing             over(img, rgba)  place(img, rgba_sprite, x, y, scale, rot, alpha)  mix(a, b, k)
"""
import math
import random
from dataclasses import dataclass, replace

import torch
import torch.nn.functional as F

DEV = torch.device('cuda')
_grids = {}
# Pixel amounts in this module (chroma, dir_blur, glitch RGB, text split) are written for 1080p. Edit.frame sets
# PX[0] = H / 1080 so the same numbers give the same look at any resolution (1440p, 4K).
PX = [1.0]


# ---------------------------------------------------------------------------------------------------------------
# helpers

def _base(h, w):
    """Normalised pixel-centre coords x,y in [-1,1] (align_corners=False), each [h,w]."""
    k = (h, w)
    if k not in _grids:
        ys = (torch.arange(h, device=DEV, dtype=torch.float32) + 0.5) / h * 2 - 1
        xs = (torch.arange(w, device=DEV, dtype=torch.float32) + 0.5) / w * 2 - 1
        _grids[k] = (xs.view(1, w).expand(h, w), ys.view(h, 1).expand(h, w))
    return _grids[k]


def _uv(h, w):
    """Pixel-centre coords in 0..1."""
    x, y = _base(h, w)
    return (x + 1) / 2, (y + 1) / 2


def _sample(img, gx, gy, mode='bilinear', pad='reflection'):
    g = torch.stack([gx, gy], -1)[None]
    return F.grid_sample(img[None], g, mode=mode, padding_mode=pad, align_corners=False)[0]


def lum(img):
    return 0.2126 * img[0] + 0.7152 * img[1] + 0.0722 * img[2]


def _col(c, like):
    return torch.tensor(c, device=DEV, dtype=like.dtype).view(3, 1, 1)


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def mix(a, b, k):
    return a + (b - a) * k


def hashf(*xs):
    """Deterministic float in [0,1) from numbers (for per-event randomness)."""
    h = 2166136261
    for x in xs:
        for ch in repr(round(float(x), 6)).encode():
            h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 0x5bd1e995) & 0xFFFFFFFF
    h ^= h >> 15
    return h / 4294967296.0


def noise1(t, seed=0):
    """Smooth 1D value noise in [-1,1]."""
    i = math.floor(t)
    f = t - i
    a, b = hashf(seed, i) * 2 - 1, hashf(seed, i + 1) * 2 - 1
    return a + (b - a) * smooth(f)


# ---------------------------------------------------------------------------------------------------------------
# camera

@dataclass
class Cam:
    zoom: float = 1.0
    cx: float = 0.5
    cy: float = 0.5
    rot: float = 0.0
    ox: float = 0.0
    oy: float = 0.0
    yaw: float = 0.0
    pitch: float = 0.0
    lens: float = 0.0
    fov: float = 50.0

    def but(self, **kw):
        return replace(self, **kw)

    def add(self, ox=0.0, oy=0.0, rot=0.0, zoom=1.0):
        return replace(self, ox=self.ox + ox, oy=self.oy + oy, rot=self.rot + rot, zoom=self.zoom * zoom)


def shake(t, amount, freq=18.0, seed=0, rot_deg=None):
    """Camera-shake offsets (ox, oy, rot) for Cam.add(); amount = max offset as a fraction of the frame."""
    ox = noise1(t * freq, seed * 3 + 1) * amount
    oy = noise1(t * freq, seed * 3 + 2) * amount
    r = noise1(t * freq * 0.8, seed * 3 + 3) * (amount * 60 if rot_deg is None else rot_deg)
    return ox, oy, r


def camera(src, W, H, cam=None, mode='bilinear'):
    """Render source frame `src` [3,Hs,Ws] (any float dtype) through `cam` into a [3,H,W] float32 frame."""
    cam = cam or Cam()
    src = src.float()
    Hs, Ws = src.shape[1:]
    zoom = max(cam.zoom, 1e-3)
    # antialias big downscales: shrink the source to ~1 source px per output px first
    k = min(1.0, (H * zoom) / Hs * 1.15)
    if k < 0.85:
        src = F.interpolate(src[None], size=(max(2, round(Hs * k)), max(2, round(Ws * k))), mode='bilinear',
                            antialias=True, align_corners=False)[0]
    asp = W / H
    x, y = _base(H, W)
    x = x - 2 * cam.ox
    y = y - 2 * cam.oy
    if cam.lens:
        r2 = (x * asp) ** 2 + y ** 2
        f = 1 + cam.lens * r2
        x, y = x * f, y * f
    px, py = x * asp, y
    if cam.rot:
        a = math.radians(-cam.rot)
        ca, sa = math.cos(a), math.sin(a)
        px, py = px * ca - py * sa, px * sa + py * ca
    if cam.yaw or cam.pitch:
        # ray from the eye through the screen point, intersected with the tilted image plane through the origin
        d = 1.0 / math.tan(math.radians(cam.fov) / 2)
        yw, pt = math.radians(cam.yaw), math.radians(cam.pitch)
        # plane basis after rotating by yaw (around y) then pitch (around x)
        cy_, sy_ = math.cos(yw), math.sin(yw)
        cp, sp = math.cos(pt), math.sin(pt)
        ux = (cy_, 0.0, -sy_)                     # plane x axis
        uy = (sy_ * sp, cp, cy_ * sp)             # plane y axis
        n = (sy_ * cp, -sp, cy_ * cp)             # plane normal
        # eye at (0,0,-d), direction (px, py, d)
        denom = px * n[0] + py * n[1] + d * n[2]
        tt = (d * n[2]) / denom                   # (0 - (-d)) * n.z / (dir . n)
        X, Y, Z = px * tt, py * tt, -d + d * tt
        px = X * ux[0] + Y * ux[1] + Z * ux[2]
        py = X * uy[0] + Y * uy[1] + Z * uy[2]
    sx = (2 * cam.cx - 1) + px / (asp * zoom) * (asp / (Ws / Hs))
    sy = (2 * cam.cy - 1) + py / zoom
    return _sample(src, sx, sy, mode=mode)


# ---------------------------------------------------------------------------------------------------------------
# blurs

def zoom_blur(img, amount, cx=0.5, cy=0.5, n=10):
    """Radial streaks out of (cx, cy): average of copies scaled 1 .. 1+amount."""
    if abs(amount) < 1e-4:
        return img
    H, W = img.shape[1:]
    x, y = _base(H, W)
    ccx, ccy = 2 * cx - 1, 2 * cy - 1
    acc = torch.zeros_like(img)
    for i in range(n):
        s = 1.0 / (1.0 + amount * i / max(1, n - 1))
        acc += _sample(img, ccx + (x - ccx) * s, ccy + (y - ccy) * s)
    return acc / n


def spin_blur(img, deg, cx=0.5, cy=0.5, n=10):
    if abs(deg) < 1e-3:
        return img
    H, W = img.shape[1:]
    asp = W / H
    x, y = _base(H, W)
    ccx, ccy = 2 * cx - 1, 2 * cy - 1
    acc = torch.zeros_like(img)
    for i in range(n):
        a = math.radians(deg * (i / max(1, n - 1) - 0.5))
        ca, sa = math.cos(a), math.sin(a)
        dx, dy = (x - ccx) * asp, y - ccy
        acc += _sample(img, ccx + (dx * ca - dy * sa) / asp, ccy + dx * sa + dy * ca)
    return acc / n


def dir_blur(img, dx_px, dy_px, n=12):
    """Motion smear along (dx, dy) pixels at 1080p (scaled by PX), centred."""
    dx_px, dy_px = dx_px * PX[0], dy_px * PX[0]
    if abs(dx_px) + abs(dy_px) < 0.5:
        return img
    H, W = img.shape[1:]
    x, y = _base(H, W)
    acc = torch.zeros_like(img)
    for i in range(n):
        f = i / max(1, n - 1) - 0.5
        acc += _sample(img, x + 2 * dx_px * f / W, y + 2 * dy_px * f / H)
    return acc / n


def _gauss1d(sigma):
    r = max(1, int(math.ceil(sigma * 3)))
    k = torch.exp(-(torch.arange(-r, r + 1, device=DEV, dtype=torch.float32) ** 2) / (2 * sigma * sigma))
    return k / k.sum(), r


def blur(img, sigma_px):
    """Gaussian blur; big radii run on a downscaled copy."""
    if sigma_px < 0.3:
        return img
    H, W = img.shape[1:]
    down = 1
    while sigma_px / down > 6 and min(H, W) / down > 16:
        down *= 2
    x = img[None]
    if down > 1:
        x = F.interpolate(x, size=(H // down, W // down), mode='bilinear', antialias=True, align_corners=False)
    k, r = _gauss1d(sigma_px / down)
    c = x.shape[1]
    x = F.conv2d(F.pad(x, (r, r, 0, 0), mode='replicate'), k.view(1, 1, 1, -1).expand(c, 1, 1, -1), groups=c)
    x = F.conv2d(F.pad(x, (0, 0, r, r), mode='replicate'), k.view(1, 1, -1, 1).expand(c, 1, -1, 1), groups=c)
    if down > 1:
        x = F.interpolate(x, size=(H, W), mode='bilinear', align_corners=False)
    return x[0]


# ---------------------------------------------------------------------------------------------------------------
# light and colour

def bloom(img, threshold=0.72, strength=0.7, radius=0.012, tint=(1.0, 1.0, 1.0)):
    """Glow on bright parts; radius as a fraction of frame height, several octaves."""
    if strength <= 0:
        return img
    H = img.shape[1]
    l = lum(img)
    bright = img * (torch.clamp((l - threshold) / max(1e-3, 1 - threshold), 0, 1) ** 1.5)[None]
    acc = torch.zeros_like(img)
    for i, w in enumerate((0.5, 0.3, 0.2)):
        acc += blur(bright, H * radius * (2.5 ** i)) * w
    return img + acc * strength * _col(tint, img)


def grade(img, exposure=0.0, contrast=1.0, pivot=0.45, sat=1.0, temp=0.0, tint=0.0, lift=0.0, gamma=1.0, gain=1.0,
          shadows=(0.0, 0.0, 0.0), highlights=(0.0, 0.0, 0.0)):
    """Colour grade. temp>0 warmer, tint>0 greener; shadows/highlights = RGB push for split toning."""
    x = img
    if exposure:
        x = x * (2.0 ** exposure)
    if temp or tint:
        x = x * _col((1 + 0.1 * temp - 0.03 * tint, 1 + 0.06 * tint, 1 - 0.1 * temp - 0.03 * tint), x)
    if lift or gain != 1.0:
        x = x * gain + lift * (1 - x)
    if gamma != 1.0:
        x = torch.clamp(x, 0, None) ** (1.0 / gamma)
    if contrast != 1.0:
        x = (x - pivot) * contrast + pivot
    if sat != 1.0:
        l = lum(x)[None]
        x = l + (x - l) * sat
    if any(shadows) or any(highlights):
        l = torch.clamp(lum(x), 0, 1)[None]
        x = x + _col(shadows, x) * (1 - l) ** 2 + _col(highlights, x) * l ** 2
    return x


def vignette(img, amount=0.3, radius=0.75, soft=0.5, color=(0.0, 0.0, 0.0)):
    if amount <= 0:
        return img
    H, W = img.shape[1:]
    x, y = _base(H, W)
    r = torch.sqrt((x * W / H) ** 2 + y ** 2) / math.sqrt((W / H) ** 2 + 1)
    m = torch.clamp((r - radius + soft) / max(1e-3, soft), 0, 1)
    m = (m * m * (3 - 2 * m)) * amount
    return img * (1 - m) + _col(color, img) * m


def flash(img, amount, color=(1.0, 1.0, 1.0)):
    """Screen-blend toward a colour (white flash). amount 0..1."""
    if amount <= 0:
        return img
    c = _col(color, img) * amount
    return 1 - (1 - img) * (1 - c)


def exposure(img, stops):
    return img * (2.0 ** stops)


def invert(img, amount=1.0):
    return mix(img, 1 - img, amount) if amount > 0 else img


def duotone(img, dark=(0.05, 0.0, 0.1), light=(1.0, 0.2, 0.25), amount=1.0, gamma=1.0):
    if amount <= 0:
        return img
    l = torch.clamp(lum(img), 0, 1)[None] ** gamma
    return mix(img, _col(dark, img) * (1 - l) + _col(light, img) * l, amount)


def ink(img, level=0.5, soft=0.06, amount=1.0, dark=(0.0, 0.0, 0.0), light=(1.0, 1.0, 1.0)):
    """High-contrast two-tone (manga / photocopy) look."""
    if amount <= 0:
        return img
    l = lum(img)[None]
    m = torch.clamp((l - level + soft) / (2 * soft), 0, 1)
    return mix(img, _col(dark, img) * (1 - m) + _col(light, img) * m, amount)


def posterize(img, levels=4, amount=1.0):
    return mix(img, torch.round(torch.clamp(img, 0, 1) * (levels - 1)) / (levels - 1), amount)


def tint(img, color, amount):
    return mix(img, img * _col(color, img), amount)


def color_pop(img, hue=0.0, width=0.07, amount=1.0, keep_sat=1.3):
    """Desaturate everything except colours near `hue` (0 red, 0.33 green, 0.66 blue)."""
    if amount <= 0:
        return img
    r, g, b = img[0], img[1], img[2]
    mx, _ = img.max(0)
    mn, _ = img.min(0)
    d = mx - mn + 1e-6
    h = torch.where(mx == r, ((g - b) / d) % 6, torch.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) / 6
    s = d / (mx + 1e-6)
    dh = torch.minimum((h - hue).abs(), 1 - (h - hue).abs())
    keep = torch.clamp(1 - (dh - width) / width, 0, 1) * torch.clamp((s - 0.25) / 0.25, 0, 1)
    l = lum(img)[None]
    pop = l + (img - l) * keep_sat
    return mix(img, l * (1 - keep[None]) + pop * keep[None], amount)


def spotlight(img, cx, cy, r=0.12, soft=0.08, dim=0.75):
    if dim <= 0:
        return img
    H, W = img.shape[1:]
    u, v = _uv(H, W)
    d = torch.sqrt(((u - cx) * W / H) ** 2 + (v - cy) ** 2)
    m = torch.clamp((d - r) / max(1e-3, soft), 0, 1)
    return img * (1 - dim * m)[None]


def light_leak(img, t, seed=0, amount=0.5, colors=((1.0, 0.45, 0.15), (1.0, 0.15, 0.35), (0.9, 0.8, 0.4))):
    """Soft drifting blobs of warm light, screen-blended."""
    if amount <= 0:
        return img
    H, W = img.shape[1:]
    u, v = _uv(H, W)
    acc = torch.zeros_like(img)
    for i, c in enumerate(colors):
        px = 0.5 + 0.7 * noise1(t * 0.3 + i * 7.1, seed + i)
        py = 0.5 + 0.6 * noise1(t * 0.25 + i * 3.3, seed + 11 + i)
        rad = 0.35 + 0.15 * noise1(t * 0.2, seed + 21 + i)
        d2 = ((u - px) * W / H) ** 2 + (v - py) ** 2
        acc += torch.exp(-d2 / (rad * rad))[None] * _col(c, img)
    return 1 - (1 - img) * (1 - torch.clamp(acc * amount, 0, 1))


def grain(img, seed, amount=0.035, size=1.0, mono=True):
    """Film grain; `seed` must change every frame (e.g. the frame index) and is reproducible."""
    if amount <= 0:
        return img
    H, W = img.shape[1:]
    g = torch.Generator(device=DEV)
    g.manual_seed(int(seed) & 0x7FFFFFFF)
    h, w = max(1, int(H / size)), max(1, int(W / size))
    n = torch.randn((1 if mono else 3, h, w), generator=g, device=DEV)
    if size != 1.0:
        n = F.interpolate(n[None], size=(H, W), mode='bilinear', align_corners=False)[0]
    l = lum(img)[None]
    return img + n * amount * (0.4 + 0.6 * (1 - (2 * l - 1) ** 2))


def scanlines(img, amount=0.15, period=3.0, t=0.0, roll=0.0):
    if amount <= 0:
        return img
    H, W = img.shape[1:]
    yy = torch.arange(H, device=DEV, dtype=torch.float32).view(H, 1) + roll * t * H
    m = 0.5 + 0.5 * torch.cos(yy / period * 2 * math.pi)
    return img * (1 - amount * m)[None]


def chroma(img, amount_px, cx=0.5, cy=0.5, angle=None):
    """RGB split. Radial around (cx, cy) by default (red pushed out, blue pulled in); `angle` (deg) = straight shift."""
    amount_px = amount_px * PX[0]
    if abs(amount_px) < 0.2:
        return img
    H, W = img.shape[1:]
    x, y = _base(H, W)
    if angle is None:
        ccx, ccy = 2 * cx - 1, 2 * cy - 1
        rmax = math.sqrt((W / H) ** 2 + 1)
        s = 2 * amount_px / H / rmax
        r = _sample(img[0:1], ccx + (x - ccx) * (1 - s), ccy + (y - ccy) * (1 - s))
        b = _sample(img[2:3], ccx + (x - ccx) * (1 + s), ccy + (y - ccy) * (1 + s))
    else:
        a = math.radians(angle)
        dx, dy = 2 * amount_px * math.cos(a) / W, 2 * amount_px * math.sin(a) / H
        r = _sample(img[0:1], x - dx, y - dy)
        b = _sample(img[2:3], x + dx, y + dy)
    return torch.cat([r, img[1:2], b], 0)


rgb_split = chroma


# ---------------------------------------------------------------------------------------------------------------
# distortion

def shockwave(img, cx, cy, radius, width=0.04, strength=0.03, ca=6.0):
    """Expanding ring that pushes pixels outward (radius/width/strength as fractions of frame height)."""
    if strength == 0 or radius <= 0:
        return img
    H, W = img.shape[1:]
    asp = W / H
    x, y = _base(H, W)
    dx, dy = (x - (2 * cx - 1)) * asp / 2, (y - (2 * cy - 1)) / 2
    r = torch.sqrt(dx * dx + dy * dy) + 1e-6
    z = (r - radius) / width
    d = strength * torch.exp(-z * z) * z * -1
    ox, oy = dx / r * d, dy / r * d
    out = _sample(img, x + 2 * ox / asp, y + 2 * oy)
    if ca:
        ring = torch.exp(-z * z)
        out = mix(out, chroma(out, ca, cx, cy), ring[None])
    return out


def ripple(img, cx, cy, t, amp=0.006, freq=40.0, speed=6.0, decay=3.0):
    H, W = img.shape[1:]
    asp = W / H
    x, y = _base(H, W)
    dx, dy = (x - (2 * cx - 1)) * asp / 2, (y - (2 * cy - 1)) / 2
    r = torch.sqrt(dx * dx + dy * dy) + 1e-6
    d = amp * torch.sin(r * freq - t * speed * 2 * math.pi) * torch.exp(-r * decay)
    return _sample(img, x + 2 * dx / r * d / asp, y + 2 * dy / r * d)


def glitch(img, seed, amount=1.0, bands=14, max_shift=0.08, rgb=10.0, blocks=6):
    """Digital glitch: torn horizontal bands, per-band RGB offsets, displaced blocks. `seed` picks the pattern
    (e.g. int(t*12) for 12 new patterns a second)."""
    if amount <= 0:
        return img
    H, W = img.shape[1:]
    R = random.Random(int(seed) * 7919 + 17)
    x, y = _base(H, W)
    shift = torch.zeros(H, device=DEV)
    for _ in range(bands):
        if R.random() > 0.7 * amount + 0.15:
            continue
        y0 = R.randrange(H)
        hh = int(H * (0.005 + 0.06 * R.random() ** 2))
        shift[y0:y0 + hh] += (R.random() * 2 - 1) * max_shift * amount * 2
    sx = x + shift.view(H, 1)
    out = _sample(img, sx, y, pad='border')
    if rgb:
        k = rgb * PX[0] * amount * (R.random() * 0.5 + 0.5)
        r = _sample(out[0:1], sx - 0 + 2 * k / W, y, pad='border')
        b = _sample(out[2:3], sx - 2 * k / W, y, pad='border')
        out = torch.cat([r, out[1:2], b], 0)
    for _ in range(int(blocks * amount)):
        bw, bh = int(W * (0.05 + 0.2 * R.random())), int(H * (0.02 + 0.08 * R.random()))
        x0, y0 = R.randrange(max(1, W - bw)), R.randrange(max(1, H - bh))
        sx0 = min(max(0, x0 + int((R.random() * 2 - 1) * W * 0.1)), W - bw)
        sy0 = min(max(0, y0 + int((R.random() * 2 - 1) * H * 0.05)), H - bh)
        out[:, y0:y0 + bh, x0:x0 + bw] = out[:, sy0:sy0 + bh, sx0:sx0 + bw].clone()
    return out


def slices(img, n=8, offset=0.1, axis='x', seed=0):
    """Frame cut into n strips, alternately offset (a "slice" hit)."""
    H, W = img.shape[1:]
    x, y = _base(H, W)
    if axis == 'x':
        band = torch.floor((y + 1) / 2 * n)
        sgn = torch.where(band % 2 == 0, 1.0, -1.0)
        return _sample(img, x + sgn * offset * 2, y, pad='reflection')
    band = torch.floor((x + 1) / 2 * n)
    sgn = torch.where(band % 2 == 0, 1.0, -1.0)
    return _sample(img, x, y + sgn * offset * 2, pad='reflection')


def pixelate(img, block_px):
    if block_px <= 1:
        return img
    H, W = img.shape[1:]
    s = F.interpolate(img[None], size=(max(1, int(H / block_px)), max(1, int(W / block_px))), mode='area')
    return F.interpolate(s, size=(H, W), mode='nearest')[0]


def mirror(img, mode='x'):
    """'x': left half mirrored onto the right; 'y': top onto bottom; 'quad': both."""
    H, W = img.shape[1:]
    x, y = _base(H, W)
    if mode in ('x', 'quad'):
        x = -x.abs()
    if mode in ('y', 'quad'):
        y = -y.abs()
    return _sample(img, x, y)


def kaleido(img, n=6, cx=0.5, cy=0.5, rot=0.0, zoom=1.0):
    H, W = img.shape[1:]
    asp = W / H
    x, y = _base(H, W)
    dx, dy = (x - (2 * cx - 1)) * asp, y - (2 * cy - 1)
    a = torch.atan2(dy, dx) + math.radians(rot)
    r = torch.sqrt(dx * dx + dy * dy) / zoom
    seg = 2 * math.pi / n
    a = torch.remainder(a, seg)
    a = torch.where(a > seg / 2, seg - a, a)
    return _sample(img, (2 * cx - 1) + r * torch.cos(a) / asp, (2 * cy - 1) + r * torch.sin(a))


# ---------------------------------------------------------------------------------------------------------------
# graphics (signed distance fields, antialiased); positions in frame fractions, sizes in fractions of height

def _paint(img, cov, color, alpha):
    a = torch.clamp(cov, 0, 1)[None] * alpha
    return img * (1 - a) + _col(color, img) * a


def _xy(img):
    H, W = img.shape[1:]
    u, v = _uv(H, W)
    return u * W / H, v, W / H, H


def ring(img, cx, cy, r, width=0.006, color=(1, 1, 1), alpha=1.0, arc=None):
    """Circle outline; arc=(a0, a1) degrees draws only part of it (0 = right, clockwise)."""
    if alpha <= 0 or r <= 0:
        return img
    X, Y, asp, H = _xy(img)
    dx, dy = X - cx * asp, Y - cy
    d = (torch.sqrt(dx * dx + dy * dy) - r).abs() - width / 2
    cov = 0.5 - d * H
    if arc is not None:
        a = torch.rad2deg(torch.atan2(dy, dx)) % 360
        a0, a1 = arc[0] % 360, arc[1] % 360
        inside = ((a >= a0) & (a <= a1)) if a0 <= a1 else ((a >= a0) | (a <= a1))
        cov = cov * inside
    return _paint(img, cov, color, alpha)


def disc(img, cx, cy, r, color=(1, 1, 1), alpha=1.0, soft=0.0):
    if alpha <= 0:
        return img
    X, Y, asp, H = _xy(img)
    d = torch.sqrt((X - cx * asp) ** 2 + (Y - cy) ** 2) - r
    cov = 0.5 - d * H if soft <= 0 else 1 - torch.clamp(d / soft + 0.5, 0, 1)
    return _paint(img, cov, color, alpha)


def line(img, x0, y0, x1, y1, width=0.004, color=(1, 1, 1), alpha=1.0):
    if alpha <= 0:
        return img
    X, Y, asp, H = _xy(img)
    ax, ay, bx, by = x0 * asp, y0, x1 * asp, y1
    pax, pay = X - ax, Y - ay
    bax, bay = bx - ax, by - ay
    h = torch.clamp((pax * bax + pay * bay) / max(1e-9, bax * bax + bay * bay), 0, 1)
    d = torch.sqrt((pax - bax * h) ** 2 + (pay - bay * h) ** 2) - width / 2
    return _paint(img, 0.5 - d * H, color, alpha)


def rect(img, x0, y0, x1, y1, color=(0, 0, 0), alpha=1.0):
    H, W = img.shape[1:]
    a, b = max(0, min(W, int(round(x0 * W)))), max(0, min(W, int(round(x1 * W))))
    c, d = max(0, min(H, int(round(y0 * H)))), max(0, min(H, int(round(y1 * H))))
    if b <= a or d <= c:            # entirely off-frame (or empty): nothing to draw
        return img
    out = img.clone()
    out[:, c:d, a:b] = mix(out[:, c:d, a:b], _col(color, img), alpha)
    return out


def brackets(img, x0, y0, x1, y1, arm=0.25, width=0.004, color=(1, 0.2, 0.2), alpha=1.0):
    """Targeting brackets (four corners of a box); arm = corner length as a fraction of the box side."""
    ax, ay = (x1 - x0) * arm, (y1 - y0) * arm
    for (px, py, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        img = line(img, px, py, px + sx * ax, py, width, color, alpha)
        img = line(img, px, py, px, py + sy * ay, width, color, alpha)
    return img


def crosshair(img, cx, cy, r=0.04, gap=0.012, width=0.003, color=(1, 0.2, 0.2), alpha=1.0, rot=0.0):
    asp = img.shape[2] / img.shape[1]
    for k in range(4):
        a = math.radians(rot + 90 * k)
        ca, sa = math.cos(a), math.sin(a)
        img = line(img, cx + ca * gap / asp, cy + sa * gap, cx + ca * r / asp, cy + sa * r, width, color, alpha)
    return img


def speed_lines(img, cx=0.5, cy=0.5, seed=0, amount=1.0, density=160, inner=0.28, color=(1, 1, 1), thick=0.35):
    """Anime speed lines radiating from (cx, cy). Change seed a few times a second for flicker."""
    if amount <= 0:
        return img
    H, W = img.shape[1:]
    X, Y, asp, _ = _xy(img)
    dx, dy = X - cx * asp, Y - cy
    a = (torch.atan2(dy, dx) / (2 * math.pi) + 0.5) * density
    i = torch.floor(a)
    f = a - i
    rnd = torch.frac(torch.sin(i * 12.9898 + seed * 78.233) * 43758.5453)
    on = (rnd > 0.55).float()
    w = thick * (0.3 + rnd)
    prof = torch.clamp(1 - (f - 0.5).abs() / (w / 2 + 1e-4), 0, 1) * on
    r = torch.sqrt(dx * dx + dy * dy)
    rad = torch.clamp((r - inner * (0.7 + 0.6 * rnd)) / 0.25, 0, 1)
    return _paint(img, prof * rad, color, amount)


def letterbox(img, amount=0.12, color=(0, 0, 0)):
    """Black bars; amount = fraction of the height covered (split top/bottom)."""
    if amount <= 0:
        return img
    H = img.shape[1]
    h = int(round(H * amount / 2))
    out = img.clone()
    c = _col(color, img)
    out[:, :h] = c
    out[:, H - h:] = c
    return out


# ---------------------------------------------------------------------------------------------------------------
# compositing

def over(img, rgba):
    """Alpha-composite an RGBA tensor [4,H,W] (straight alpha) over img."""
    a = rgba[3:4]
    return img * (1 - a) + rgba[:3] * a


def place(img, sprite, x, y, scale=1.0, rot=0.0, alpha=1.0, anchor=(0.5, 0.5), mode='bilinear'):
    """Draw an RGBA sprite [4,h,w] with its anchor at frame point (x, y) (fractions), scaled and rotated."""
    if alpha <= 0 or scale <= 0:
        return img
    H, W = img.shape[1:]
    h, w = sprite.shape[1:]
    X, Y = _uv(H, W)
    px, py = (X - x) * W, (Y - y) * H              # output px relative to the anchor point
    a = math.radians(-rot)
    ca, sa = math.cos(a), math.sin(a)
    qx, qy = (px * ca - py * sa) / scale, (px * sa + py * ca) / scale
    sx = (qx + anchor[0] * w) / w * 2 - 1
    sy = (qy + anchor[1] * h) / h * 2 - 1
    s = _sample(sprite, sx, sy, mode=mode, pad='zeros')
    return img * (1 - s[3:4] * alpha) + s[:3] * s[3:4] * alpha
