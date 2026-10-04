"""s02 HUNT: the build (bars 3-6, video t 8.54-19.82). Drums + bass enter.

"my privacy so I can heal / And even rock stars got feelings that they feel / In reality, it's just a piece I could
drill / Always, oh-oh"

Story: the security feed that was watching Art3m1s (s01) flips: its brackets lock onto the ENEMIES, and every kill
is logged as an evidence photo that flies into a 4-slot hit list ("TARGETS") and gets crossed out. HEARTSTEEL Kayn
takes his quadra on CAM 02 / CAM 03 (the last two at ~12% HP, under a wiretap caption "EVEN ROCK STARS GOT
FEELINGS"). Then the feed can't keep up: the HUD flickers out and Samira's run tears through in colour (flaming
roll with echo trails, three kills, strobes on the 3-3-3 kicks of bar 6, a stepped crash-zoom on the snare roll).
The grade warms bar by bar from the surveillance look to full colour ('hot') by 19.82. Samira gets a contrast
grade (darker mids, crushed blacks, half bloom) and a de-purple correction so her violet map doesn't read milky.
Hits light the frame with short exposure kicks; white flashes are small and gone within ~3 frames.

Timing (bar b starts at song.bar(b); 16th n of bar b = song.beat(4b + n/4); on() snaps that to the measured drum
onset within +-60 ms, which is where the attack really is):
  8.540  bar 3 16th 0   SEAM (fixed). Kayn clip 35.85 at 0.6x. Sub drop, punch-in, RGB time-split converging,
                        grade snaps from surveil 1.0 (s01) to 0.78 with a saturation burst (no white flash).
                        Hit list pops in, lock on target 1.
  9.221  bar 3 16th 4   KAYN KILL 1  clip 36.25  ("+200" gold pops at 36.250, white burst 36.283)
 10.881  (kill 2 - 0.45) lock on target 2, once the 3.6x rush is braking
 11.331  bar 4 16th 0   KAYN KILL 2  clip 41.35  ("+200" + white flash at 41.350). Grade -> 0.60.
 12.055  bar 4 16th 4   glitch cut CAM 02 -> CAM 03 (window 12.005-12.105). Hides the game camera's hard reposition
                        between clip 41.717 and 41.750: CAM 02 stops at 41.70, CAM 03 starts at 41.77.
 12.753  bar 4 16th 8   KAYN KILL 3  clip 43.883 ("+106" + white burst at 43.883), Kayn at ~12% HP
 13.633  bar 4 16th 13  KAYN KILL 4 (quadra)  clip 45.383  ("+145" + red death icon at 45.383)
 14.181  bar 5 16th 0   slices transition to Samira (window 14.07-14.29); surveillance HUD flickers out by 14.54.
                        Grade -> 0.35.
 14.867  bar 5 16th 4   SAMIRA KILL 1  clip 31.383 (999/824 crit pops at 31.383)
 16.297  bar 5 16th 12  "drill": the flaming roll crosses frame centre (clip ~33.68) -> punch + whoosh, echo trails
 16.989  bar 6 16th 0   SAMIRA KILL 2  clip 34.717 (999/826 crit at 34.717). Grade -> 0.12.
 17.533 / 18.049 / 18.571   bar 6 16ths 3 / 6 / 9: strobes (bone/red/bone) with rotation kicks
 19.107  bar 6 16th 12  SAMIRA KILL 3  clip 38.783 (999/413): the biggest hit (one bright frame); grade -> 0 + 'hot'
 19.277 / 19.455 / 19.633   bar 6 16ths 13 / 14 / 15 (snare roll): stepped crash-zoom 1.05 -> 1.10 -> 1.15
 19.820  bar 7          SEAM: hard cut (s03). Reverse cymbal ends dead here.
"""
import math

import torch

from engine.api import *

SPAN = (8.54, 19.82)

KAYN = 'League-of-Legends__2026-02-19__23-12-48.mp4'
SAMI = 'League-of-Legends__2026-02-20__01-08-10.mp4'

RED = (1.0, 0.16, 0.22)
CYAN = (0.2, 0.95, 1.0)
BONE = (0.96, 0.94, 0.9)
INK = (0.02, 0.02, 0.04)

BOX = 0.15          # lock box / fresh photo size (fraction of frame height)
SLOT_H = 0.062      # hit-list thumbnail size (fraction of frame height)
HUD_END = 14.18     # surveillance HUD starts flickering out here (bar 5 downbeat) ...
HUD_GONE = 14.54    # ... and is gone here


# --- timing -----------------------------------------------------------------------------------------------------------
def on(bar, six, win=0.06):
    """Video time of 16th `six` of bar `bar`, snapped to the nearest strong drum onset within +-win s."""
    g = song.beat(4 * bar + six / 4.0)
    c = song.onsets('kick', g - win, g + win, min_s=0.75) + song.onsets('snare', g - win, g + win, min_s=0.85)
    return min(c, key=lambda x: abs(x - g)) if c else g


# --- camera helpers ---------------------------------------------------------------------------------------------------
def fit(z, cx, cy):
    """Cam that never looks past the clip's edge: cx, cy clamped so the view stays inside the source."""
    m = max(0.0, 0.5 - 0.5 / z)
    return Cam(zoom=z, cx=clamp(cx, 0.5 - m, 0.5 + m), cy=clamp(cy, 0.5 - m, 0.5 + m))


def scr(cam, x, y):
    """Clip point (x, y) -> screen point under `cam` (both 16:9, so u = 0.5 + (x - cx) * zoom)."""
    return 0.5 + (x - cam.cx) * cam.zoom, 0.5 + (y - cam.cy) * cam.zoom


_path_a = follow([(8.54, 0.50, 0.52), (9.40, 0.48, 0.53), (10.70, 0.54, 0.45), (12.11, 0.54, 0.45)])
_path_b = follow([(12.00, 0.50, 0.53), (13.00, 0.49, 0.52), (13.70, 0.52, 0.49), (14.30, 0.52, 0.49)])
_path_s = follow([(14.07, 0.52, 0.46), (14.87, 0.53, 0.45), (15.80, 0.53, 0.47), (16.40, 0.51, 0.49),
                  (17.00, 0.50, 0.46), (19.10, 0.50, 0.45), (19.82, 0.50, 0.45)])


def cam_a(t):
    """CAM 02 (Kayn, continues s01's shot): CCTV push-in 1.12 -> 1.19 drifting toward the upcoming kills.
    At the seam 8.54: Cam(zoom 1.12, cx 0.50, cy 0.52)."""
    cx, cy = _path_a(t)
    return fit(1.12 + 0.07 * smooth((t - 8.54) / 3.5), cx, cy)


def cam_b(t):
    """CAM 03 (Kayn after the game camera's reposition): wider (1.06 -> 1.12), low enough to keep his HP bar."""
    cx, cy = _path_b(t)
    return fit(1.06 + 0.06 * smooth((t - 12.0) / 1.7), cx, cy)


def cam_s(t):
    """Samira: 1.08 -> 1.13 over bar 5, pushes to 1.19 through bar 6; the action sits in the upper middle."""
    cx, cy = _path_s(t)
    z = 1.08 + 0.05 * smooth((t - 14.07) / 1.5) + 0.06 * smooth((t - 17.0) / 2.1)
    return fit(z, cx, cy)


# --- one big hit (engine impact() with its windows clipped to this span, so nothing leaks into s03) -------------------
def hit(E, t, s=1.0, cx=0.5, cy=0.5, punch=0.09, shake_amt=0.012, flash=0.25, chroma=12.0, shock=True, sfx=True,
        color=(1.0, 1.0, 1.0), decay=0.14, kick=0.5, hold=0.0, fdecay=0.03):
    """Punch-in + shake + light + RGB split + shockwave + sound. The light is mostly a short exposure kick (`kick`
    stops x s, time constant 35 ms: brightens what is already bright and never lifts the blacks). The white
    screen-blend flash is small (flash x s, capped at 0.6), held `hold` s at full, then gone with time constant
    `fdecay`, so the frame 0.15 s after the hit is clean again (lead's haze rule)."""
    end = SPAN[1]
    seed = int(hashf(t) * 1000)
    fl = min(0.6, flash * s)

    def scr_fn(tt):
        e = env(tt, t, 0.0, decay)
        es = env(tt, t, 0.0, decay * 1.6)
        ox, oy, r = shake(tt, shake_amt * s * es, 22.0, seed)
        # zoom also covers the shake so the frame edge never shows the reflection padding
        return dict(zoom=1 + punch * s * e + 2.2 * shake_amt * s * es, ax=cx, ay=cy, ox=ox, oy=oy, rot=r * 0.6)
    E.screen(t, min(end, t + decay * 7), scr_fn)

    def post(P, tt):
        dt = tt - t
        if fl > 0:
            f = fl * (1.0 if dt < hold else math.exp(-(dt - hold) / fdecay))
            if f > P['flash']:          # only recolour the flash while this hit's flash is the brightest
                P['flash'], P['flash_color'] = f, color
        P['chroma'] = P['chroma'] + chroma * s * env(tt, t, 0.0, decay * 0.7)
        P['chroma_cx'], P['chroma_cy'] = cx, cy
        P['exposure'] += kick * s * env(tt, t, 0.0, 0.035)
    E.post(t, min(end, t + decay * 6), post)

    if shock:
        def lay(img, tt, ctx):
            u = (tt - t) / 0.45
            if u < 0 or u > 1:
                return img
            return fx.shockwave(img, cx, cy, radius=0.05 + 0.75 * eout(u), width=0.05 + 0.05 * u,
                                strength=0.045 * s * (1 - u), ca=8 * s * (1 - u))
        E.layer(t, min(end, t + 0.45), lay, z=5)
    if sfx:
        E.sfx('impact', t, gain_db=-3 + 4 * (s - 1), strength=s)


# --- cheap pixel-aligned boxes for the small HUD pieces ---------------------------------------------------------------
def corners(img, x0, y0, x1, y1, arm, wpx, color, alpha):
    """Four corner brackets from thin rects (arm = fraction of the side)."""
    if alpha <= 0:
        return img
    H, W = img.shape[1:]
    wx, wy = wpx / W, wpx / H
    ax, ay = (x1 - x0) * arm, (y1 - y0) * arm
    for (px, sx) in ((x0, 1), (x1, -1)):
        for (py, sy) in ((y0, 1), (y1, -1)):
            xa, xb = sorted((px, px + sx * ax))
            ya, yb = sorted((py, py + sy * ay))
            ex0, ex1 = sorted((px, px + sx * wx))
            ey0, ey1 = sorted((py, py + sy * wy))
            img = fx.rect(img, xa, ey0, xb, ey1, color, alpha)      # horizontal arm
            img = fx.rect(img, ex0, ya, ex1, yb, color, alpha)      # vertical arm
    return img


def outline(img, x0, y0, x1, y1, wpx, color, alpha):
    return corners(img, x0, y0, x1, y1, 0.5, wpx, color, alpha)


def build(E):
    # ------------------------------------------------------------------------------------------------------------------
    # hit times (video s). Comments: bar / 16th, measured onset.
    T_SEAM = SPAN[0]          # 8.540  bar 3, 16th 0 (fixed by the seam; the drum entry onset is 8.513)
    T_K1 = on(3, 4)           # 9.221  bar 3, 16th 4   Kayn kill 1
    T_K2 = on(4, 0)           # 11.331 bar 4, 16th 0   Kayn kill 2
    T_CUT = on(4, 4)          # 12.055 bar 4, 16th 4   CAM 02 -> CAM 03
    T_K3 = on(4, 8)           # 12.753 bar 4, 16th 8   Kayn kill 3
    T_K4 = on(4, 13)          # 13.633 bar 4, 16th 13  Kayn kill 4 (quadra)
    T_B5 = on(5, 0)           # 14.181 bar 5, 16th 0   to Samira
    T_S1 = on(5, 4)           # 14.867 bar 5, 16th 4   Samira kill 1
    T_DR = on(5, 12)          # 16.297 bar 5, 16th 12  "drill", roll crosses centre
    T_S2 = on(6, 0)           # 16.989 bar 6, 16th 0   Samira kill 2
    T_ST = [on(6, 3), on(6, 6), on(6, 9)]      # 17.533 18.049 18.571  strobes
    T_S3 = on(6, 12)          # 19.107 bar 6, 16th 12  Samira kill 3 (last hit of s02, as the seam asks)
    T_ROLL = [on(6, 13), on(6, 14), on(6, 15)]  # 19.277 19.455 19.633  snare roll
    T_END = SPAN[1]           # 19.820 bar 7

    # pinned kill frames (clip s), from the 1/30 s strips, written as exact 60 fps source frames (n/60) so the hit's
    # first video frame shows the kill frame itself, not an 80 % RIFE morph toward it:
    #   36.25 = 2175/60, 41.35 = 2481/60, 43.883 = 2633/60 ('+106'), 45.383 = 2723/60 (death icon)
    #   31.383 = 1883/60 (999/824), 34.717 = 2083/60 (999/826), 38.783 = 2327/60 (999/413)
    K_K = [2175 / 60, 2481 / 60, 2633 / 60, 2723 / 60]
    K_S = [1883 / 60, 2083 / 60, 2327 / 60]
    S_ROLL = 33.68            # flaming roll at frame centre (~(0.54, 0.50)): 33.53 at (0.67, 0.36), 33.78 at (0.45, 0.60)

    # ------------------------------------------------------------------------------------------------------------------
    # SHOTS (cover 8.54-19.82; overlaps only inside the two transition windows)
    #
    # CAM 02, Kayn, 8.54-12.105. Remap keys (t, s, v):
    #   8.540 35.85 0.6   seam: exactly what s01 ends on (35.85 at 0.6x)
    #   9.221 36.25 0.3   kill 1. mean 0.40/0.681 = 0.59x; ease (.25,.5) -> cruise 0.70x
    #  11.331 41.35 0.3   kill 2. mean 5.10/2.110 = 2.42x; ease (.3,.4)  -> cruise 3.56x (the velocity rush)
    #  12.105 41.70 0.45  afterglow. mean 0.35/0.774 = 0.45x -> cruise 0.49x. Stays below 41.717 (camera jump).
    r_a = Remap([K(T_SEAM, 35.85, 0.6, (0.0, 0.0)),
                 K(T_K1, K_K[0], 0.3, (0.25, 0.5)),
                 K(T_K2, K_K[1], 0.3, (0.3, 0.4)),
                 K(T_CUT + 0.05, 41.70, 0.45, (0.3, 0.3))])

    def rgb_src(t, ctx, shot):
        """At the seam the colour channels arrive one after another: G and B lag behind R by up to 75 / 150 ms of
        clip time and converge over 0.34 s (the feed 'snapping' to colour)."""
        c = shot.clip
        s = shot.s(t)
        base = c.at(s, shot.interp)     # respects render.py --fast
        u = (t - T_SEAM) / 0.34
        if u >= 1.0:
            return base
        d = 0.075 * (1 - eout(max(0.0, u)))
        if d < 0.004:
            return base
        g = c.at(s - d, interp=False)
        b = c.at(s - 2 * d, interp=False)
        return torch.cat([base[0:1], g[1:2], b[2:3]], 0)

    E.shot(T_SEAM, T_CUT + 0.05, KAYN, r_a, cam=cam_a, src=rgb_src, name='s02 kayn CAM02', hits=[T_K1, T_K2])

    # CAM 03, Kayn, 12.005-14.30:
    #  12.005 41.77 1.6   enters fast, after the game camera's reposition
    #  12.753 43.883 0.3  kill 3. mean 2.11/0.748 = 2.82x; ease (.2,.45) -> cruise 3.84x
    #  13.633 45.383 0.3  kill 4. mean 1.50/0.880 = 1.70x; ease (.3,.4)  -> cruise 2.46x
    #  14.300 45.65 0.5   afterglow into the transition. mean 0.27/0.667 = 0.40x -> cruise 0.44x
    r_b = Remap([K(T_CUT - 0.05, 41.77, 1.6, (0.0, 0.0)),
                 K(T_K3, K_K[2], 0.3, (0.2, 0.45)),
                 K(T_K4, K_K[3], 0.3, (0.3, 0.4)),
                 K(14.30, 45.65, 0.5, (0.5, 0.0))])
    E.shot(T_CUT - 0.05, 14.30, KAYN, r_b, cam=cam_b, name='s02 kayn CAM03', hits=[T_K3, T_K4])
    E.transition(T_CUT - 0.05, T_CUT + 0.05, T.glitch(rate=40.0))

    # Samira, 14.07-19.82:
    #  14.070 30.60 1.2   into the fight
    #  14.867 31.383 0.3  kill 1. mean 0.78/0.797 = 0.98x; ease (.25,.5) -> cruise 1.21x
    #  16.297 33.68 0.8   roll at centre on "drill". mean 2.30/1.430 = 1.61x; ease (.3,.35) -> cruise 2.11x
    #  16.989 34.717 0.3  kill 2. mean 1.04/0.692 = 1.50x; ease (.2,.5) -> cruise 2.07x
    #  19.107 38.783 0.3  kill 3. mean 4.06/2.118 = 1.92x; ease (.3,.4) -> cruise 2.79x (her R spin, strobes)
    #  19.820 39.17 0.8   afterglow, ramping up. mean 0.39/0.713 = 0.55x -> cruise 0.63x
    r_s = Remap([K(14.07, 30.60, 1.2, (0.0, 0.0)),
                 K(T_S1, K_S[0], 0.3, (0.25, 0.5)),
                 K(T_DR, S_ROLL, 0.8, (0.3, 0.35)),
                 K(T_S2, K_S[1], 0.3, (0.2, 0.5)),
                 K(T_S3, K_S[2], 0.3, (0.3, 0.4)),
                 K(T_END, 39.17, 0.8, (0.5, 0.0))])

    E_IN, E_OUT = T_DR - 0.52, T_DR + 0.36     # echo window ~15.78-16.66: the roll is on screen ~15.82-16.64

    def echo_src(t, ctx, shot):
        """Lighten-blend echo trails while the flaming roll crosses (fire leaves a smear)."""
        c = shot.clip
        s = shot.s(t)
        base = c.at(s, shot.interp)     # respects render.py --fast
        w = smooth((t - E_IN) / 0.12) * smooth((E_OUT - t) / 0.14)
        if w < 0.02:
            return base
        out = base
        for k in (1, 2, 3):
            prev = c.at(s - 0.03 * k, interp=False)
            out = torch.maximum(out, prev * (w * 0.78 ** k))
        return out

    def depurple(img, t, ctx):
        """Colour-correct the Samira clip before the grade. Her map is violet-blue everywhere, which read purple and
        flat: pull down the blue that sticks out above red/green (ground (0.35, 0.31, 0.75) -> (0.34, 0.32, 0.61)).
        Whites, reds, oranges, pinks and her fire have no excess blue, so they are untouched."""
        r, g, b = img[0], img[1], img[2]
        ex = torch.clamp(b - torch.maximum(r, g), 0, 1)
        return torch.stack([r - 0.03 * ex, g + 0.03 * ex, b - 0.35 * ex], 0).clamp(0, 1)

    E.shot(14.07, T_END, SAMI, r_s, cam=cam_s, src=echo_src, fx=[depurple], name='s02 samira',
           hits=[T_S1, T_S2, T_S3])
    E.transition(14.07, 14.29, T.slices(n=10, axis='y'))

    # ------------------------------------------------------------------------------------------------------------------
    # GRADE: surveillance amount steps down bar by bar, each step on a hit; then 'hot' after the last kill.
    surv = LOOKS['surveil']
    steps = [(T_K2, 0.60, 0.12), (T_B5, 0.35, 0.10), (T_S2, 0.12, 0.12), (T_S3, 0.0, 0.15)]

    def warm(t):
        k = 0.78
        for t0, v, ramp in steps:
            if t >= t0:
                k = k + (v - k) * smooth((t - t0) / ramp)
        return k

    def warm_post(P, t):
        k = warm(t)
        for key, v in surv.items():
            a = P[key]
            if isinstance(v, tuple):
                P[key] = tuple(x + (y - x) * k for x, y in zip(a, v))
            else:
                P[key] = a + (v - a) * k
    E.post(T_SEAM, T_END, warm_post)

    # the seam: s01's grey feed snaps to colour on the drum entry. A saturation + contrast burst (decaying over ~0.4 s
    # to the 0.78 surveillance level) with the RGB time-split converging, instead of a white flash (which read milky).
    def seam_post(P, t):
        e = env(t, T_SEAM, 0.0, 0.2)
        P['sat'] += 0.8 * e
        P['contrast'] += 0.12 * e
    E.post(T_SEAM, T_SEAM + 1.0, seam_post)

    look(E, T_S3, T_END, 'hot', fade_in=0.3, amount=0.8)

    # Samira contrast (registered after the looks so it has the last word): darker mids, crushed blacks instead of the
    # surveillance/'hot' violet shadow lift, harder contrast, a touch warmer/greener against the purple, and half the
    # bloom (the haze). Ramps in with the slices transition.
    def sam_grade(P, t):
        k = smooth((t - 14.07) / 0.3)
        P['contrast'] *= 1 + 0.15 * k
        P['gamma'] += (0.86 - P['gamma']) * k
        P['shadows'] = tuple(x + (y - x) * k for x, y in zip(P['shadows'], (-0.015, -0.005, -0.03)))
        P['bloom'] *= 1 - 0.5 * k
        P['bloom_threshold'] += (max(P['bloom_threshold'], 0.88) - P['bloom_threshold']) * k
        P['temp'] += 0.25 * k
        P['tint'] += 0.25 * k
        P['vignette'] = max(P['vignette'], 0.4 * k)
    E.post(14.07, T_END, sam_grade)

    # kick pulse on every strong drum hit (bigger once colour arrives)
    E.screen(T_SEAM, T_END, lambda tt: dict(zoom=1 + (0.018 if tt < T_B5 else 0.03) * song.pulse(tt, 'kick', 0.09, 0.85)))

    # ------------------------------------------------------------------------------------------------------------------
    # KAYN: locks, kills, evidence photos, hit list
    # Locks start once the remap is braking into the kill (the target barely moves from there): kill 1 from the seam
    # (0.6x all the way), kill 2 from 10.88 (~2.2x and falling), kills 3/4 0.36 s before (brake phase) with a
    # faster 0.22 s close-in.
    KL = []
    for i, (t_k, s_k, x, y, t_on, close, cf) in enumerate([
            (T_K1, K_K[0], 0.44, 0.58, T_SEAM, 0.32, cam_a),         # inside the blue shield swirl, lower centre
            (T_K2, K_K[1], 0.63, 0.22, T_K2 - 0.45, 0.30, cam_a),    # '+200' top-right of centre
            (T_K3, K_K[2], 0.41, 0.55, T_K3 - 0.36, 0.22, cam_b),    # the effects blob, lower left of centre
            (T_K4, K_K[3], 0.55, 0.37, T_K4 - 0.36, 0.22, cam_b)]):  # upper right of centre
        c = cf(t_k)
        sx, sy = scr(c, x, y)
        KL.append(dict(t=t_k, s=s_k, x=x, y=y, on=t_on, close=close, cam=cf, zoom=c.zoom, sx=sx, sy=sy,
                       land=t_k + 0.46))

    # seam punch (no crack: the song's own drum entry is the hit; a sub drop adds weight under it)
    s0x, s0y = scr(cam_a(T_SEAM), 0.45, 0.55)
    hit(E, T_SEAM, 0.8, s0x, s0y, punch=0.08, flash=0.0, kick=0.45, chroma=14.0, sfx=False)   # light = seam_post
    E.sfx('subdrop', T_SEAM, gain_db=-7, dur=0.9)

    for i, k in enumerate(KL):
        quad = i == 3
        hit(E, k['t'], 1.2 if quad else 1.0, k['sx'], k['sy'], punch=0.08, flash=0.3 if quad else 0.22,
            chroma=16.0 if quad else 10.0, color=(1.0, 0.45, 0.45) if quad else (1.0, 1.0, 1.0))
        E.sfx('shutter', k['t'] + 0.05, gain_db=-6)          # the evidence photo is taken
        E.sfx('tick', k['on'] + k['close'], gain_db=-9)      # lock complete

    # glitch cut CAM 02 -> CAM 03 and the slices transition into Samira
    E.sfx('glitch', T_CUT - 0.05, gain_db=-9, dur=0.11)
    E.sfx('glitch', 14.07, gain_db=-6, dur=0.22)
    E.sfx('whoosh', T_B5, gain_db=-8, dur=0.3, direction='rl')

    def hud_a(t):
        """Surveillance HUD alpha: solid, then flickers out over 14.18-14.54 (the feed loses the rock star)."""
        if t < HUD_END:
            return 1.0
        u = (t - HUD_END) / (HUD_GONE - HUD_END)
        if u >= 1:
            return 0.0
        return (1 - smooth(u)) * (1.0 if hashf(int(t * 40), 9) > 0.25 else 0.25)

    rec2, rec3, rec4 = L.rec('CAM 02'), L.rec('CAM 03'), L.rec('CAM 04')

    def rec_top(img, t, ctx):
        a = hud_a(t)
        if a <= 0.001:
            return img
        fn = rec2 if t < T_CUT else (rec3 if t < T_B5 else rec4)
        out = fn(img, t, ctx)
        return out if a >= 0.999 else fx.mix(img, out, a)
    E.top(T_SEAM, HUD_GONE, rec_top, z=1)

    def slot_xy(i, W, H):
        hw = SLOT_H / 2 * H / W
        return 0.056 + hw + i * (2 * hw + 0.006), 0.168, hw     # left edge 0.056: inside the 0.05 text margin

    def hitlist_top(img, t, ctx):
        """'TARGETS' + four empty slots that pop in at the seam (filled by the photos below)."""
        a = hud_a(t)
        if a <= 0.001:
            return img
        W, H = ctx['W'], ctx['H']
        img = ty.text(img, 'TARGETS', 0.056, 0.118, 0.017, 'mono', BONE, anchor=(0.0, 0.5), alpha=0.85 * a,
                      tracking=0.15)
        hh = SLOT_H / 2
        for i in range(4):
            if t >= KL[i]['land']:
                continue
            ai = clamp((t - T_SEAM - 0.04 - i * 0.06) / 0.05) * a
            cx, cy, hw = slot_xy(i, W, H)
            img = fx.rect(img, cx - hw, cy - hh, cx + hw, cy + hh, INK, 0.35 * ai)
            img = corners(img, cx - hw, cy - hh, cx + hw, cy + hh, 0.3, 2, BONE, 0.6 * ai)
        return img
    E.top(T_SEAM, HUD_GONE, hitlist_top, z=2)

    def locks_top(img, t, ctx):
        """Red brackets close in on each target (0.32 s), 'TARGET LOCKED' blinks, then snap shut white on the kill."""
        W, H = ctx['W'], ctx['H']
        asp = W / H
        for k in KL:
            if not (k['on'] <= t < k['t'] + 0.12):
                continue
            sx, sy = scr(k['cam'](min(t, k['t'])), k['x'], k['y'])
            if t < k['t']:
                u = (t - k['on']) / k['close']
                e = eout(u)
                s = BOX * (2.3 - 1.3 * e)
                al = clamp(u * 3)
                spin = (1 - e) * 90
                col = RED
            else:
                v = (t - k['t']) / 0.12
                e = 1.0
                s = BOX * (1 - 0.2 * eout(v))
                al = clamp(1 - v)
                spin = 0.0
                col = BONE
            hw, hh = s / asp / 2, s / 2
            img = fx.brackets(img, sx - hw, sy - hh, sx + hw, sy + hh, 0.28, 0.0045, col, al)
            img = fx.crosshair(img, sx, sy, s * 0.2, s * 0.07, 0.003, col, al * 0.9, rot=spin)
            if t < k['t'] and e > 0.95:
                blink = 1.0 if int((t - k['on']) * 10) % 2 == 0 else 0.55
                ly = sy + hh + 0.032 if sy + hh + 0.045 < 0.92 else sy - hh - 0.032   # keep inside y 0.06-0.92
                img = ty.text(img, 'TARGET LOCKED', sx, ly, 0.02, 'mono', RED, alpha=blink, tracking=0.12)
        return img
    E.top(T_SEAM, T_K4 + 0.12, locks_top, z=3)

    sprites = {}

    def photo_sprite(i, H):
        """RGBA evidence photo of target i at its kill frame: the clip region inside the lock box, graded cold, with
        a white border. Pure function of (i, H), so it is cached."""
        key = (i, H)
        if key not in sprites:
            k = KL[i]
            P = max(8, int(round(BOX * H)))
            src = clip(KAYN).at(k['s'], interp=False)
            tile = fx.camera(src, P, P, Cam(zoom=k['zoom'] / BOX, cx=k['x'], cy=k['y']))
            tile = torch.clamp(fx.grade(tile, contrast=1.12, sat=0.6, temp=-0.2), 0, 1)
            b = max(2, int(round(P * 0.03)))
            spr = torch.ones(4, P + 2 * b, P + 2 * b, device=tile.device, dtype=tile.dtype)
            spr[:3, b:b + P, b:b + P] = tile
            sprites[key] = spr
        return sprites[key]

    def photos_top(img, t, ctx):
        """Each kill: 0.05 s after the hit the box becomes a photo (white camera flash), holds, then flies in an arc
        into its hit-list slot (0.16-0.46 s) and gets crossed out in red."""
        a = hud_a(t)
        if a <= 0.001:
            return img
        W, H = ctx['W'], ctx['H']
        hh = SLOT_H / 2
        for i, k in enumerate(KL):
            u = t - k['t']
            if u < 0.05:
                continue
            spr = photo_sprite(i, H)
            cx, cy, hw = slot_xy(i, W, H)
            f = smooth((u - 0.16) / 0.30)
            x = lerp(k['sx'], cx, f)
            y = lerp(k['sy'], cy, f) - 0.06 * math.sin(math.pi * f)
            h = lerp(BOX, SLOT_H, f)
            rot = 10.0 * math.sin(math.pi * f) * (1 if i % 2 else -1)
            sc = h * H / spr.shape[1]
            img = fx.place(img, spr, x, y, sc, rot, a)
            if u < 0.14:
                img = fx.place(img, torch.ones_like(spr), x, y, sc, rot, a * clamp(1 - (u - 0.05) / 0.09))
            if f >= 1.0:
                v = clamp((u - 0.46) / 0.08)
                if v > 0:
                    img = fx.line(img, cx - hw, cy - hh, cx - hw + 2 * hw * v, cy - hh + 2 * hh * v, 0.004, RED, a)
                    img = fx.line(img, cx + hw, cy - hh, cx + hw - 2 * hw * v, cy - hh + 2 * hh * v, 0.004, RED, a)
                img = outline(img, cx - hw, cy - hh, cx + hw, cy + hh, 2, RED, a)
        # all four down: the whole list flashes once
        d = t - KL[3]['land']
        if 0 <= d < 0.2:
            for i in range(4):
                cx, cy, hw = slot_xy(i, W, H)
                img = outline(img, cx - hw - 0.003, cy - hh - 0.005, cx + hw + 0.003, cy + hh + 0.005, 3, BONE,
                              a * (1 - d / 0.2))
        return img
    E.top(T_K1 + 0.05, HUD_GONE, photos_top, z=4)

    # wiretap caption: the sung words type out as they're sung (mono, ROCK STARS in red), 10.95-13.50
    words = [(w0, w1, w.strip(',.!?"').upper()) for (w0, w1, w) in song.words if 11.0 <= w0 < 12.9]
    if not words:   # fallback: the measured times
        words = [(11.16, 11.62, 'EVEN'), (11.62, 11.92, 'ROCK'), (11.92, 12.14, 'STARS'), (12.14, 12.42, 'GOT'),
                 (12.42, 12.82, 'FEELINGS')]
    line = ' '.join(w for _, _, w in words)
    rev, reds = [], set()
    for j, (w0, w1, w) in enumerate(words):
        if j > 0:
            rev.append(w0)                       # the space before the word
        for c in range(len(w)):
            if w.startswith('ROCK') or w.startswith('STAR'):
                reds.add(len(rev))
            rev.append(w0 + (w1 - w0) * 0.85 * c / max(1, len(w)))
    CAP_Y, CAP_SIZE, CAP_TRK = 0.835, 0.03, 0.08
    CAP_RED = (1.0, 0.36, 0.4)          # brighter than RED: thin mono strokes on a dark box
    CAP_ON, CAP_OFF = words[0][0] - 0.21, 13.38

    def cap_a(t):
        a = smooth((t - CAP_ON) / 0.08)
        if t > CAP_OFF:
            u = (t - CAP_OFF) / 0.12
            a *= clamp(1 - u) * (1.0 if hashf(int(t * 50), 5) > 0.35 else 0.0)
        return clamp(a)

    def cap_top(img, t, ctx):
        a = cap_a(t)
        if a <= 0.001:
            return img
        W, H = ctx['W'], ctx['H']
        adv = ty.width('M', CAP_SIZE, 'mono', 0.0, H=H, W=W)
        trk = ty.width('MM', CAP_SIZE, 'mono', CAP_TRK, H=H, W=W) - 2 * adv
        n = len(line)
        total = n * adv + (n - 1) * trk
        left = 0.5 - total / 2
        img = fx.rect(img, left - 0.012, CAP_Y - 0.03, left + total + 0.012, CAP_Y + 0.03, INK, 0.6 * a)
        img = ty.text(img, 'AUDIO INTERCEPT', left - 0.004, CAP_Y - 0.05, 0.015, 'mono', RED, anchor=(0.0, 0.5),
                      alpha=0.9 * a, tracking=0.15)

        def per(i, nn):
            return dict(alpha=1.0 if t >= rev[i] else 0.0, color=CAP_RED if i in reds else BONE)
        img = ty.letters(img, line, 0.5, CAP_Y, CAP_SIZE, 'mono', per=per, tracking=CAP_TRK, alpha=a)
        shown = sum(1 for r in rev if t >= r)
        if shown < n or int(t * 4) % 2 == 0:
            cxp = left + shown * (adv + trk) + adv / 2
            img = fx.rect(img, cxp - adv * 0.4, CAP_Y - CAP_SIZE * 0.6, cxp + adv * 0.4, CAP_Y + CAP_SIZE * 0.6, BONE,
                          0.85 * a)
        return img
    E.top(CAP_ON, CAP_OFF + 0.12, cap_top, z=5)
    for w0, _, _ in words:
        E.sfx('tick', w0, gain_db=-13)

    # ------------------------------------------------------------------------------------------------------------------
    # SAMIRA
    c1 = cam_s(T_S1)
    sx1, sy1 = scr(c1, 0.55, 0.33)
    hit(E, T_S1, 0.85, sx1, sy1, punch=0.08, flash=0.28, chroma=14.0)

    # the flaming roll: warm light leak while it crosses, punch toward it on "drill" (exposure kick only, no flash)
    rx, ry = scr(cam_s(T_DR), 0.54, 0.50)
    hit(E, T_DR, 0.55, rx, ry, punch=0.07, flash=0.0, kick=0.6, chroma=10.0)
    E.sfx('whoosh', T_DR, gain_db=-3, dur=0.7, direction='rl')

    def leak(img, t, ctx):      # kept low: the screen-blended blobs were part of the milky look
        w = smooth((t - (T_DR - 0.55)) / 0.2) * smooth((T_DR + 0.45 - t) / 0.3)
        return fx.light_leak(img, t, seed=5, amount=0.16 * w) if w > 0.01 else img
    E.layer(T_DR - 0.55, T_DR + 0.45, leak, z=2)

    c2 = cam_s(T_S2)
    sx2, sy2 = scr(c2, 0.48, 0.36)
    hit(E, T_S2, 1.1, sx2, sy2, punch=0.09, flash=0.32, kick=0.55, chroma=16.0, color=(1.0, 0.85, 0.7))
    E.sfx('subdrop', T_S2, gain_db=-9, dur=0.8)

    # bar 6, 16ths 3 / 6 / 9: strobes (bone, red, bone) with alternating rotation kicks (zoom covers the corners:
    # 2.5 deg needs 1.078, we give 1 + 0.125 at the peak)
    for i, ts in enumerate(T_ST):
        col = BONE if i % 2 == 0 else RED
        sgn = 1.0 if i % 2 == 0 else -1.0

        def pst(P, tt, ts=ts, col=col):
            # one bright frame, not a milky one: a short exposure kick carries the light, the colour flash is 0.38
            # and gone within ~3 frames (time constant 22 ms)
            f = 0.38 * env(tt, ts, 0.0, 0.022)
            if f > P['flash']:
                P['flash'], P['flash_color'] = f, col
            P['exposure'] += 0.5 * env(tt, ts, 0.0, 0.035)
            P['chroma'] += 12.0 * env(tt, ts, 0.0, 0.07)
        E.post(ts, ts + 0.3, pst)

        def rk(tt, ts=ts, sgn=sgn):
            e = env(tt, ts, 0.0, 0.09)
            r = 2.5 * sgn * e
            return dict(zoom=1 + 0.045 * e + 0.032 * abs(r), rot=r)
        E.screen(ts, ts + 0.45, rk)

    # kill 3: the biggest hit of the section, speed lines building into it from 16th 9, red ring out of it
    c3 = cam_s(T_S3)
    sx3, sy3 = scr(c3, 0.49, 0.25)
    # Light: flash 0.6 (the cap) held 18 ms, so the first frame after the hit (19.117) is the one bright frame, then gone
    # with a 12 ms time constant: ~0.3 on 19.133, ~0.07 on 19.150 (was 1.05 decaying over 75 ms = 6+ milky frames).
    hit(E, T_S3, 1.4, sx3, sy3, punch=0.11, flash=0.6, hold=0.018, fdecay=0.012, kick=0.5, chroma=18.0, decay=0.15)
    E.sfx('boom', T_S3, gain_db=-7, dur=0.9)

    def lines(img, t, ctx):
        if t < T_S3:
            a = 0.4 * smooth((t - T_ST[2]) / (T_S3 - T_ST[2]))
        else:
            a = 0.55 * env(t, T_S3, 0.0, 0.07)
        if a < 0.01:
            return img
        return fx.speed_lines(img, sx3, sy3, seed=int(t * 15), amount=a, density=170, inner=0.24, color=BONE)
    E.layer(T_ST[2], min(T_END, T_S3 + 0.45), lines, z=3)

    def red_ring(img, t, ctx):
        u = (t - T_S3) / 0.4
        if u < 0 or u >= 1:
            return img
        return fx.ring(img, sx3, sy3, 0.04 + 0.6 * eout(u), 0.012 * (1 - u) + 0.002, RED, 1 - u)
    E.layer(T_S3, T_S3 + 0.4, red_ring, z=6)

    # snare roll (16ths 13, 14, 15): stepped crash-zoom toward Samira + chroma steps, reverse cymbal into the cut
    def roll_scr(tt):
        n = sum(eout((tt - ts) / 0.05) for ts in T_ROLL if tt >= ts)
        sh = sum(env(tt, ts, 0.0, 0.06) for ts in T_ROLL)
        ox, oy, r = shake(tt, 0.004 * sh, 30.0, 77)
        return dict(zoom=1 + 0.05 * n + 0.01 * sh, ax=0.5, ay=0.45, ox=ox, oy=oy, rot=r * 0.5)
    E.screen(T_ROLL[0], T_END, roll_scr)

    def roll_post(P, tt):
        n = sum(1.0 for ts in T_ROLL if tt >= ts)
        P['chroma'] += 5.0 * n + sum(8.0 * env(tt, ts, 0.0, 0.05) for ts in T_ROLL)
        P['zoom_blur'] = max(P['zoom_blur'], sum(0.06 * env(tt, ts, 0.0, 0.05) for ts in T_ROLL))
        P['zoom_blur_cx'], P['zoom_blur_cy'] = 0.5, 0.45
    E.post(T_ROLL[0], T_END, roll_post)
    E.sfx('reverse', T_END, gain_db=-5, dur=0.7)
