"""s05 STAR: the rapid highlight run (bars 14-17, video t 39.58-50.88). Register: ROCK STAR.

Chorus groove: kicks on 16ths 0, 3, 6, 9, 12 of every bar, claps on 16ths 4 and 12. 16th = 0.1756 s.
Grid used here (video s, from song.beat):
  bar 14  39.58 | 16th 3 40.105 | 6 40.64 | 9 41.175 | 12 41.70        "Mother, love, life at the top, boy"
  bar 15  42.42 | 16th 3 42.945 | 6 43.47 | 9 43.995 | 12 44.52        "Everybody hates it ever since you got born"
  bar 16  45.24 | 16th 3 45.765 | 6 46.29 | 9 46.82  | 12 47.36        "They're praying for the death of a rockstar"
  bar 17  48.06 drums OUT ("Hop on,") | 16th 4 48.76 clap, drums back | 6 49.12 | 9 49.655 | 12 50.18 "...you're born"

The plan, one idea per lyric line:
  bar 14  Darius dunks a triple under the turret: kills on 16ths 3-6-9, the turret explosion on 16th 12.
          Echo trails on the fast run between kills 2 and 3. TRIPLE KILL callout.
  bar 15  "Everybody hates it": a slanted 3-panel split-screen, Sejuani | Viego | Vayne. The panels slam home on the
          downbeat, then one kill per kick, left -> middle -> right -> left (16ths 3, 6, 9, 12); the scoring panel
          flashes and punches, the others dim, the sfx is panned to its side.
  bar 16  The middle panel IS the Viego shot (same clip, remap and camera), so on the downbeat the side panels fly
          off like doors and Viego fills the frame. Quadra on 16th 9 ("death"), penta 0.4 s of clip later on
          16th 12 ("ROCKstar") inside a kaleidoscope burst of his cyan blast. PENTAKILL slam.
  bar 17  The drums drop out for "Hop on,": freeze-frame, the song lowpasses, a riser; the clap on 16th 4 snaps
          back with an invert flash into Vayne: 2316 crit on 16th 6 (RGB time split), then a zoom-blur rush into
          the white-out explosion on 16th 12 ("born").

Seams: whip pan in from s04 over 39.40-39.76 (owned here, cut point 39.58 = bar 14 downbeat). The Vayne shot runs
to 51.06 under s06's zoom-through (50.70-51.06); this file's posts end by 50.78 and its screen moves by 50.88.
"""
import math

import torch

from engine.api import *

SPAN = (39.58, 50.88)

DARIUS = 'League-of-Legends__2026-03-03__00-18-26.mp4'   # 58.93 s
VIEGO = 'League-of-Legends__2026-09-29__22-41-54.mp4'    # 59.60 s
VAYNE = 'League-of-Legends__2026-02-25__01-03-33.mp4'    # 59.05 s
SEJU = 'League-of-Legends__2026-01-29__02-48-55.mp4'     # 58.70 s

RED = (1.0, 0.16, 0.22)
CYAN = (0.2, 0.95, 1.0)
BONE = (0.96, 0.94, 0.9)
GOLD = (1.0, 0.82, 0.3)
WHITE = (1.0, 1.0, 1.0)

# Clip times pinned from the 1/30 s kill strips (out/wip/kills): the frame where the killing blow / big number lands.
DAR_K1, DAR_K2, DAR_K3 = 52.65, 53.05, 54.35   # white burst + '439'; '640' crit; '508' + flash (blue ring)
DAR_EX = 54.62                                 # the big orange explosion ring right after the triple
VIE_TRIPLE = 43.683                            # Caitlyn: white flash, +399 gold
VIE_QUADRA = 47.083                            # zKeller: giant white '999' crit
VIE_PENTA = 47.483                             # Mordekaiser: the cyan Heartbreaker blast fills the upper centre
VIE_FREEZE = 47.75                             # blast ring + '1084' still on screen: the freeze frame
VAY_K1 = 49.40                                 # '999 / 291' gold pop + orange burst
VAY_CRIT = 53.00                               # '2316' crit + burst
VAY_WHITE = 54.55                              # white-out explosion, '999 / 585'
SEJ_TRIPLE = 51.11                             # Winter's Wrath white burst (gold +121 at 51.33)
SEJ_QUADRA = 54.34                             # white '136' burst (big '1197' at 54.45, green explosion 54.55)

SL = 0.08   # slant of the split-screen dividers: x moves +0.04 at the top, -0.04 at the bottom


def h16(bar, n):
    """Video time of 16th n of bar `bar`."""
    return song.beat(4 * bar + n / 4.0)


def strobe(E, t, color, amt=0.45, dec=0.05):
    """Stage-light strobe: a short screen flash in `color` (only where it is the strongest flash)."""
    def f(P, tt):
        a = amt * env(tt, t, 0.0, dec)
        if a >= P['flash']:
            P['flash'] = a
            P['flash_color'] = color
    E.post(t, t + dec * 6, f)


def kick_shake(E, t, amt=0.006, dur=0.35, seed=0):
    def f(tt):
        ox, oy, r = shake(tt, amt * env(tt, t, 0.0, 0.09), 24.0, seed)
        return dict(ox=ox, oy=oy, rot=r * 0.5)
    E.screen(t, t + dur, f)


def edge(k, v):
    """x of split-screen divider k (1 or 2) at height v (float or tensor)."""
    return k / 3.0 + SL * (0.5 - v)


def build(E):
    # ---- grid ----------------------------------------------------------------------------------------------------
    B14, B15, B16, B17 = song.bar(14), song.bar(15), song.bar(16), song.bar(17)   # 39.58 42.42 45.24 48.06
    D1, D2, D3, DEX = h16(14, 3), h16(14, 6), h16(14, 9), h16(14, 12)            # 40.105 40.64 41.175 41.70
    PL1, PM, PR, PL2 = h16(15, 3), h16(15, 6), h16(15, 9), h16(15, 12)            # 42.945 43.47 43.995 44.52
    VQ, VP = h16(16, 9), h16(16, 12)                                              # 46.82 47.36
    CLAP = h16(17, 4)                                                             # 48.76: drums back after the gap
    AK2, AMID, AK3 = h16(17, 6), h16(17, 9), h16(17, 12)                          # 49.12 49.655 50.18
    WHIP0, WHIP1 = 39.40, 39.76      # seam window with s04 (s04's last shot runs to 39.76)
    END = 51.06                      # s06's zoom-through runs 50.70-51.06 over this file's last shot
    S06 = 50.70

    # ==== bar 14: DARIUS TRIPLE ===================================================================================
    # velocity(): kills at 0.3x on 16ths 3, 6, 9, explosion on 16th 12; cruise speeds (ease 0.25/0.5):
    #   39.40->40.105  clip 51.55->52.65  mean 1.56x  cruise 2.18x  (whip hides 39.40-39.58)
    #   40.105->40.64  52.65->53.05       mean 0.75x  cruise 1.02x
    #   40.64->41.175  53.05->54.35       mean 2.43x  cruise 3.71x  (echo trails on this run)
    #   41.175->41.70  54.35->54.62       mean 0.51x  cruise 0.64x
    #   41.70->42.42   54.62->55.09       (0.3x -> 1x aftermath; shot ends under the panels)
    r_dar = velocity([(D1, DAR_K1), (D2, DAR_K2), (D3, DAR_K3), (DEX, DAR_EX)], WHIP0, 51.55, B15, hit=0.3)

    def dar_cam(t):
        k = smooth((t - B14) / (DEX - B14))
        return Cam(zoom=lerp(1.10, 1.20, k), cx=0.5, cy=0.53)

    def dar_src(t, ctx, shot):
        # echo trails while Darius runs at ~3.7x between kill 2 and kill 3 (4 clip samples, ~0.4 s)
        c = shot.clip
        s = shot.s(t)
        w = smooth((t - (D2 + 0.08)) / 0.08) * (1 - smooth((t - (D3 - 0.16)) / 0.1))
        if w < 0.02:
            return c.at(s)
        acc = c.at(s).float()
        tot = 1.0
        for k, g in ((1, 0.7), (2, 0.45), (3, 0.25)):
            acc = acc + c.at(s - 0.05 * k).float() * (g * w)
            tot += g * w
        return acc / tot

    def dar_grade(P, t):
        # Butcher's Bridge is darker than the other clips: lift it to match
        k = smooth((t - (B14 - 0.02)) / 0.12) * (1 - smooth((t - (B15 - 0.14)) / 0.14))
        P['exposure'] += 0.16 * k
        P['lift'] += 0.015 * k

    E.shot(WHIP0, B15, DARIUS, r_dar, cam=dar_cam, src=dar_src, name='darius triple', hits=[D1, D2, D3])
    E.transition(WHIP0, WHIP1, T.whip(angle=0.0))          # s04 slides out left, Darius in from the right
    E.sfx('whoosh', B14, dur=0.4, direction='rl', gain_db=-4)
    strobe(E, B14, WHITE, 0.5, 0.05)                       # 16th 0: white strobe at the whip's cut point
    E.post(B14 - 0.02, B15, dar_grade)
    # screen positions of the kills: clip (0.48, 0.54) / (0.48, 0.50) / (0.52, 0.55) through Cam(~1.12, 0.5, 0.53)
    impact(E, D1, 0.85, 0.48, 0.51)                                        # bar 14 16th 3
    impact(E, D2, 0.95, 0.48, 0.47)                                        # bar 14 16th 6
    impact(E, D3, 1.25, 0.52, 0.52, flash=0.25, color=(1.0, 0.9, 0.85))    # bar 14 16th 9 (game flash is white)
    impact(E, DEX, 0.7, 0.5, 0.55, punch=0.06, color=(1.0, 0.72, 0.4), sfx=None)   # 16th 12 (clap): explosion
    E.sfx('boom', DEX, dur=0.9, gain_db=-9)
    # y 0.22: the letters drop in from 0.08 higher at 1.8x scale, so their tops stay below y 0.06
    E.layer(D3, D3 + 1.25, L.counter('TRIPLE KILL', D3, y=0.22, size=0.085, hold=1.0), z=8)   # 1.25 s on screen

    # ==== bar 15: "EVERYBODY HATES IT" split-screen ===============================================================
    # Left = Sejuani (giant boar), middle = Viego (the base shot itself), right = Vayne. Side panels are drawn by a
    # layer; the middle region is the Viego shot showing through, so it can become the full frame in bar 16.
    PK = {'L': (PL1, PL2), 'M': (PM,), 'R': (PR,)}
    START = {'L': 42.24, 'M': 42.27, 'R': 42.30}    # panels start sliding, all land on B15 = 42.42 (16th 0)
    FROM = {'L': -1.0, 'M': 1.0, 'R': -1.0}         # L and R drop from above, M rises from below
    VSTART = START['M']

    def hit(side, t, dec):
        return max(env(t, k, 0.0, dec) for k in PK[side])

    def kill_pop(img, e):
        # a panel's kill: mostly an exposure kick (bright, not milky) with a light flash; clean again within 0.15 s
        if e < 0.004:
            return img
        return fx.flash(img * (1 + 0.7 * e), 0.3 * e)

    def dim(side, t):
        return 0.32 * max(env(t, k, 0.0, 0.15) for s2, ks in PK.items() if s2 != side for k in ks)

    def slide_dy(side, t):
        u = clamp((t - START[side]) / (B15 - START[side]))
        return FROM[side] * 1.06 * (1 - u * u)      # accelerates into the landing (a slam, not a glide)

    def door_dx(side, t):
        if t < B16:
            return 0.0
        d = 0.47 * eout((t - B16) / 0.26)           # doors burst open on the bar 16 downbeat
        return -d if side == 'L' else d

    def panel_mask(side, u, v, dx, dy, W, H):
        ul, vl = u - dx, v - dy
        my = torch.clamp(vl * H + 0.5, 0, 1) * torch.clamp((1 - vl) * H + 0.5, 0, 1)
        if side == 'L':
            m = torch.clamp((edge(1, vl) - ul) * W, 0, 1)
        elif side == 'R':
            m = torch.clamp((ul - edge(2, vl)) * W, 0, 1)
        else:
            m = torch.clamp((ul - edge(1, vl)) * W, 0, 1) * torch.clamp((edge(2, vl) - ul) * W, 0, 1)
        return (m * my)[None]

    def divider(img, k, dx, dy, col):
        xt, xb = edge(k, 0.0) + dx, edge(k, 1.0) + dx
        y0, y1 = dy, 1.0 + dy
        img = fx.line(img, xt + 0.004, y0, xb + 0.004, y1, 0.004, RED, 0.75)
        img = fx.line(img, xt - 0.004, y0, xb - 0.004, y1, 0.004, CYAN, 0.75)
        return fx.line(img, xt, y0, xb, y1, 0.006, col, 1.0)

    def panel_edges(img, side, dx, dy, glow):
        col = tuple(lerp(a, b, glow) for a, b in zip(WHITE, GOLD))
        if side in ('L', 'M'):
            img = divider(img, 1, dx, dy, col)
        if side in ('R', 'M'):
            img = divider(img, 2, dx, dy, col)
        if abs(dy) > 0.002:                         # the leading horizontal edge while a panel slides in
            vl = 1.0 if dy < 0 else 0.0
            if side == 'L':
                lo, hi = -0.05, edge(1, vl) + dx
            elif side == 'M':
                lo, hi = edge(1, vl) + dx, edge(2, vl) + dx
            else:
                lo, hi = edge(2, vl) + dx, 1.05
            img = fx.line(img, lo, vl + dy, hi, vl + dy, 0.006, col, 0.95)
        return img

    # Sejuani panel: triple on 16th 3 (42.945), quadra on 16th 12 (44.52).
    #   42.24->42.945  clip 50.55->51.11  mean 0.79x  cruise 0.95x
    #   42.945->44.52  51.11->54.34       mean 2.05x  cruise 3.10x
    r_sej = velocity([(PL1, SEJ_TRIPLE), (PL2, SEJ_QUADRA)], START['L'], 50.55, B16 + 0.4, hit=0.3)
    # Vayne panel: first kill on 16th 9 (43.995).   42.24->43.995  clip 47.70->49.40  mean 0.97x  cruise 1.23x
    r_vyp = velocity([(PR, VAY_K1)], START['L'], 47.70, B16 + 0.4, hit=0.3)

    def panel_img(side, t, W, H, dx, dy):
        drift = 0.05 * smooth((t - B15) / 3.0)
        if side == 'L':
            z = (1.06 + drift) * (1 + 0.09 * hit('L', t, 0.12))
            cam = Cam(zoom=z, cx=0.5, cy=0.49, ox=-1 / 3.0 + dx, oy=dy)    # clip centre at the panel centre
            img = fx.camera(clip(SEJU).at(r_sej.s(t)), W, H, cam)
            pcx = 1 / 6.0 + dx
        else:
            z = (1.12 + drift) * (1 + 0.09 * hit('R', t, 0.12))
            cam = Cam(zoom=z, cx=0.5, cy=0.5, ox=1 / 3.0 + dx, oy=dy)
            img = fx.camera(clip(VAYNE).at(r_vyp.s(t)), W, H, cam)
            pcx = 5 / 6.0 + dx
        img = fx.chroma(img, 12.0 * hit(side, t, 0.12), pcx, 0.5 + dy)
        img = kill_pop(img, hit(side, t, 0.05))
        d = dim(side, t)
        if d > 0.004:
            img = img * (1 - d)
        return img

    def split_layer(img, t, ctx):
        H, W = img.shape[1:]
        u, v = fx._uv(H, W)
        out = img
        for side in ('L', 'R'):
            dx, dy = door_dx(side, t), slide_dy(side, t)
            if abs(dy) >= 1.05 or abs(dx) >= 0.45:
                continue
            out = fx.mix(out, panel_img(side, t, W, H, dx, dy), panel_mask(side, u, v, dx, dy, W, H))
            glow = max(hit(side, t, 0.15), hit('M', t, 0.15))
            out = panel_edges(out, side, dx, dy, glow)
        return out

    def mid_in(a, b, p, ctx):
        # Darius (a) -> Viego (b): Viego rises into the middle panel from below; Darius stays visible elsewhere
        # until the side panels cover him (they're drawn by split_layer on top).
        t = ctx['t']
        H, W = a.shape[1:]
        dy = slide_dy('M', t)
        if abs(dy) >= 1.05:
            return a
        bs = fx.camera(b, W, H, Cam(oy=dy))
        u, v = fx._uv(H, W)
        out = fx.mix(a, bs, panel_mask('M', u, v, 0.0, dy, W, H))
        return panel_edges(out, 'M', 0.0, dy, 0.0)

    E.layer(START['L'], B16 + 0.3, split_layer, z=2)
    E.transition(VSTART, B15, mid_in)
    E.samples(START['L'], B15 + 0.02, 12)            # layer motion isn't seen by auto motion blur
    E.sfx('whoosh', B15 - 0.05, dur=0.25, direction='in', gain_db=-6)
    impact(E, B15, 0.8, 0.5, 0.5, punch=0.04, shock=False, flash=0.45, chroma=10)   # panels slam home, 16th 0
    for side, t in (('L', PL1), ('M', PM), ('R', PR), ('L', PL2)):                  # 16ths 3, 6, 9, 12
        E.sfx('impact', t, gain_db=-6, pan={'L': -0.55, 'M': 0.0, 'R': 0.55}[side], strength=0.9)
        kick_shake(E, t, 0.006, seed=int(t * 10))

    # ==== bar 16: VIEGO QUADRA + PENTA ============================================================================
    # Explicit keys (speed v at each key):
    #   42.27->43.47  clip 42.40->43.683  mean 1.07x  cruise 1.39x   triple on bar 15 16th 6 (middle panel)
    #   43.47->46.82  43.683->47.083      mean 1.01x  cruise 1.49x   quadra on bar 16 16th 9 ("death")
    #   46.82->47.36  47.083->47.483      mean 0.74x  cruise 1.00x   penta on bar 16 16th 12 ("ROCKstar")
    #   47.36->48.06  47.483->47.75       mean 0.38x  cruise 0.59x   brakes to a freeze on the bar 17 downbeat
    #   48.06->48.76  hold 47.75 (freeze while the drums are out)
    r_vie = Remap([
        K(VSTART, 42.40, 1.0, (0.0, 0.0)),
        K(PM, VIE_TRIPLE, 0.3, (0.25, 0.5)),
        K(VQ, VIE_QUADRA, 0.3, (0.3, 0.5)),
        K(VP, VIE_PENTA, 0.3, (0.25, 0.5)),
        K(B17, VIE_FREEZE, 0.0, (0.2, 0.6)),
        K(CLAP + 0.2, VIE_FREEZE, 0.0, (0.0, 0.0)),
    ])
    KX, KY = 0.44, 0.25   # penta blast on screen: clip (0.41, 0.22) through Cam(1.2, 0.46, 0.43)

    def vie_cam(t):
        # split: zoom 1.10 at (0.54, 0.52) (the middle third shows clip x 0.39-0.69, the triple at 0.59 is inside);
        # after the doors, push to 1.2 at (0.46, 0.43) for the kills in the upper third. Bounds: cx, cy stay inside
        # [0.5/zoom, 1 - 0.5/zoom] all the way.
        k = smooth((t - B16) / (VQ - 0.2 - B16))
        z, cx, cy = lerp(1.10, 1.20, k), lerp(0.54, 0.46, k), lerp(0.52, 0.43, k)
        if t > B17:                                  # freeze: slow push toward the blast, a nervous tremble
            k2 = smooth((t - B17) / (CLAP - B17))
            z *= 1 + 0.07 * k2
            cx, cy = lerp(cx, 0.44, k2), lerp(cy, 0.41, k2)
        z *= 1 + 0.08 * hit('M', t, 0.12)           # middle-panel punch on the triple
        cam = Cam(zoom=z, cx=cx, cy=cy)
        if t > B17:
            ox, oy, r = shake(t, 0.004 * smooth((t - B17) / 0.6), 30.0, 7)
            cam = cam.add(ox, oy, r * 0.3)
        return cam

    def vie_fx(img, t, ctx):
        if t < B16 + 0.3:            # middle-panel duties: its own kill flash, dim when a side panel scores
            img = fx.chroma(img, 12.0 * hit('M', t, 0.12), 0.5, 0.5)
            img = kill_pop(img, hit('M', t, 0.05))
            d = dim('M', t)
            if d > 0.004:
                img = img * (1 - d)
        if VP <= t < VP + 0.42:      # kaleidoscope burst of the cyan blast: full for 0.12 s, gone by +0.42
            u = t - VP
            k = 1.0 if u < 0.12 else 1 - smooth((u - 0.12) / 0.3)
            if k > 0.01:
                kal = fx.kaleido(img, 6, KX, KY, rot=u * 220.0, zoom=1.0 + 0.25 * k)
                img = fx.mix(img, kal, k)
                # darken the ground around the mandala so it glows cyan on dark instead of washing the frame
                H, W = img.shape[1:]
                uu, vv = fx._uv(H, W)
                d = torch.sqrt(((uu - KX) * (W / H)) ** 2 + (vv - KY) ** 2)
                m = torch.clamp((d - 0.22) / 0.4, 0, 1)
                img = img * (1 - 0.4 * k * m)[None]
        return img

    def vie_speed(img, t, ctx):
        a = 0.3 * smooth((t - (B16 + 0.2)) / 0.5) * (1 - smooth((t - (VQ - 0.15)) / 0.15))
        return fx.speed_lines(img, 0.5, 0.5, seed=int(t * 15), amount=a, density=150, inner=0.32, color=BONE)

    def freeze_look(P, t):
        k = smooth((t - B17) / 0.3)
        P['sat'] *= 1 - 0.6 * k
        P['contrast'] *= 1 + 0.12 * k
        P['chroma'] += 7.0 * k
        P['chroma_cx'], P['chroma_cy'] = KX, KY
        P['vignette'] = max(P['vignette'], 0.3 + 0.35 * k)
        P['bloom'] *= 1 - 0.5 * k

    E.shot(VSTART, CLAP, VIEGO, r_vie, cam=vie_cam, fx=[vie_fx], name='viego penta', hits=[PM, VQ, VP])
    # doors open on the bar 16 downbeat (16th 0)
    impact(E, B16, 0.7, 0.5, 0.5, punch=0.05, shock=False, flash=0.3, chroma=10, sfx=None)
    E.sfx('whoosh', B16 + 0.08, dur=0.3, direction='out', gain_db=-4)
    E.samples(B16 - 0.01, B16 + 0.3, 10)
    strobe(E, h16(16, 3), RED, 0.4)                  # 16th 3 (45.765)
    strobe(E, h16(16, 6), WHITE, 0.4)                # 16th 6 (46.29)
    beat_pulse(E, B16 + 0.3, VQ - 0.05, amount=0.03)
    E.layer(B16 + 0.2, VQ, vie_speed, z=1)
    impact(E, VQ, 1.1, 0.46, 0.22)                                          # quadra, 16th 9
    # penta, 16th 12 (+ clap): a light cyan flash; the punch comes from the exposure kick, chroma and kaleidoscope
    impact(E, VP, 1.5, KX, KY, flash=0.12, color=(0.4, 1.0, 1.0), chroma=22)
    E.sfx('boom', VP, dur=1.2, gain_db=-6)
    look(E, VP, B17, 'hot', fade_out=0.25)

    def burst_grade(P, t):
        # while the kaleidoscope is up: colour and contrast instead of white haze. Bloom stays low and the impact's
        # exposure kick is trimmed (0.83 -> ~0.5 stops) so the blast stays cyan instead of clipping to white.
        k = 1 - smooth((t - (VP + 0.12)) / 0.25)
        P['exposure'] -= 0.33 * env(t, VP, 0.0, 0.045)
        P['bloom'] *= 1 - 0.6 * k
        P['bloom_threshold'] = lerp(P['bloom_threshold'], 0.9, k)
        P['contrast'] *= 1 + 0.08 * k
        P['sat'] *= 1 + 0.1 * k
        P['vignette'] = max(P['vignette'], 0.3 + 0.25 * k)
    E.post(VP, VP + 0.4, burst_grade)
    # from_scale 2.2: at its biggest the word spans x ~0.09-0.91, y ~0.57-0.88 (inside the text margins)
    E.layer(VP + 0.04, CLAP, L.slam('PENTAKILL', VP + 0.04, y=0.72, size=0.14, color=GOLD, hold=1.05, out=0.18,
                                    from_scale=2.2, glow=0.7, glow_color=CYAN, split=14.0, stroke=0.004),
            z=8)   # 47.40-48.73
    # "Hop on,": the drums are out from 48.06 to the clap at 48.76 -> freeze, lowpass, riser into the snap back
    E.post(B17, CLAP, freeze_look)
    E.sfx('shutter', B17, gain_db=-4)
    E.music('lowpass', B17, CLAP, cutoff_from=16000, cutoff_to=1500)
    E.sfx('riser', CLAP, dur=CLAP - B17, gain_db=-9)

    # ==== bar 17: VAYNE WHITE-OUT =================================================================================
    #   48.76->49.12  clip 52.55->53.00  mean 1.25x  cruise 1.60x  (enters at 1.4x)
    #   49.12->50.18  53.00->54.55       mean 1.46x  cruise 2.16x  crit on 16th 6, white-out on 16th 12 ("born")
    #   50.18->51.06  54.55->55.12       0.3x -> 1x aftermath under s06's zoom-through
    r_vay = velocity([(AK2, VAY_CRIT), (AK3, VAY_WHITE)], CLAP, 52.55, END, hit=0.3, v_in=1.4)

    def vay_cam(t):
        k = smooth((t - CLAP) / (AK3 - CLAP))
        return Cam(zoom=lerp(1.12, 1.22, k), cx=lerp(0.48, 0.52, k), cy=0.51)

    def vay_src(t, ctx, shot):
        # RGB time split on the 2316 crit: red from the future, blue from the past (3 clip samples, ~0.3 s)
        c = shot.clip
        s = shot.s(t)
        k = env(t, AK2, 0.04, 0.09)
        if k < 0.03:
            return c.at(s)
        d = 0.07 * k
        a, b, e = c.at(s + d), c.at(s), c.at(s - d)
        return torch.stack([a[0], b[1], e[2]], 0)

    def invert(P, t):
        P['invert'] = 1.0

    def suck(P, t):
        k = ein(clamp((t - (AK3 - 0.25)) / 0.25))
        P['zoom_blur'] = max(P['zoom_blur'], 0.2 * k)
        P['zoom_blur_cx'], P['zoom_blur_cy'] = 0.51, 0.49

    def whiteout(P, t):
        # full white for 2 frames (50.18-50.20), then gone fast: 0.6 at 50.217, 0.2 at 50.25, ~0.04 at 50.30,
        # so the game's own '999 / 585' blast and the orange fireball read clean well before 50.4
        u = t - AK3
        a = 1.0 if u < 0.022 else math.exp(-(u - 0.022) / 0.03)
        if a >= P['flash']:
            P['flash'] = a
            P['flash_color'] = WHITE

    def aftermath(P, t):
        # after the white-out: contrasty, saturated fireball without bloom haze; back to the base grade by 50.70
        # (s06's zoom-through starts from this section's plain grade, as before)
        k = smooth((S06 - t) / 0.3)
        P['contrast'] *= 1 + 0.1 * k
        P['sat'] *= 1 + 0.15 * k
        P['bloom'] *= 1 - 0.5 * k
        P['bloom_threshold'] = lerp(P['bloom_threshold'], 0.88, k)
        P['vignette'] = max(P['vignette'], lerp(P['vignette'], 0.4, k))

    E.shot(CLAP, END, VAYNE, r_vay, cam=vay_cam, src=vay_src, name='vayne white-out', hits=[AK2, AK3])
    E.post(CLAP, CLAP + 2.0 / 60, invert)                                    # invert flash on the clap, 2 frames
    impact(E, CLAP, 0.9, 0.5, 0.5, punch=0.07, shock=False, flash=0.0, chroma=14)
    # crit, 16th 6: clip (0.45, 0.53) -> screen (0.46, 0.52). Light flash (0.14): the kick and the RGB split carry it
    impact(E, AK2, 1.2, 0.46, 0.52, flash=0.12)
    E.sfx('zap', AK2, gain_db=-9)
    strobe(E, AMID, RED, 0.45)                       # 16th 9 (49.655)
    beat_pulse(E, AK2 + 0.25, AK3 - 0.3, amount=0.03)
    E.post(AK3 - 0.25, AK3, suck)                    # zoom-blur rush into the explosion
    E.sfx('reverse', AK3, dur=0.5, gain_db=-9)
    # white-out, 16th 12: clip (0.53, 0.50) -> screen (0.51, 0.49). decay 0.1 keeps its screen move inside 50.88.
    # The white itself comes only from whiteout() (2 frames), not from the impact.
    impact(E, AK3, 1.5, 0.51, 0.49, punch=0.12, decay=0.1, flash=0.0, chroma=22)
    E.post(AK3, S06, whiteout)
    E.sfx('boom', AK3, dur=1.4, gain_db=-3)
    E.post(AK3, S06, aftermath)
