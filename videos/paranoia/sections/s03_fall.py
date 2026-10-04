"""s03 FALL: the near-death break (bars 7-9, video t 19.82-28.28).

The drums drop out and the rock star nearly dies. Everything is grey except red (the 'paranoia' look), the footage
runs in RIFE slow-mo, and the song sits under a low-pass that opens back up as the drums return in bar 9.

  A  19.82-24.34  Ashe (2026-03-20__00-52-41): double kill, then the giant red rocket sweeps in and drops her from
                  888 to 69 HP. The surveillance brackets lock onto HER ('TARGET: ART3M1S'), then fall onto the
                  HUD HP readout. Echo trails behind the rocket. Heartbeats on the 808 hits.
  B  24.14-26.16  Master Yi (2026-04-07__21-21-36) at 65/1672 HP: "every time you POP UP" -> his kill on bar 9 heals
                  him and the colour bursts back for a moment. Glitch cut in (24.14-24.34).
  C  26.16-28.28  Ashe again, 54 -> 3 HP: step zooms on the pre-drop hits (bar 9 16ths 4, 6, 9), snap down to the
                  HUD as HP hits 3, freeze on 3/2305 ("FALL" 27.42 / "HARD" 27.68), ECG trace that flatlines,
                  riser + reverse cymbal, white-out from 28.18 into s04's drop.

Clip times pinned from the 1/30 s kill strips and full-res HUD crops:
  Ashe kill 1   32.867  '+183' gold pops right of centre; the red rocket and its grid burst in upper right
  Ashe kill 2   34.20   Kalista's bar empties, '+183' gold upper centre
  rocket hit    34.50   rocket over Ashe ('226' at 34.467); HUD HP 888 (34.480) -> 69/2305 (34.513)
  3 HP          35.11   HUD HP 50 (35.083) -> 3/2305 (35.117); stays 3 until 35.40
  Yi kill       52.575  white kill burst 52.55; camera jump + '999' + '+150' gold at 52.583; HP 65 -> 506

Grid: bar b, 16th s = song.beat(4b + s/4); hit(b, s) snaps to the measured kick/snare onset within 50 ms.
  bar 7 = 19.82 (808 on 16ths 0, 3, 6), bar 8 = 22.66 (808 on 0, 3, 6; hat roll; bass out at 24.8),
  bar 9 = 25.48 (silence, then clap 16th 4 = 26.163, kick 6 = 26.521, kick 9 = 27.049, clap 12 = 27.577).
"""
import math

import numpy as np

from engine.api import *

SPAN = (19.82, 28.28)
T_IN, T_OUT = SPAN

ASHE = 'League-of-Legends__2026-03-20__00-52-41.mp4'
YI = 'League-of-Legends__2026-04-07__21-21-36.mp4'

RED = (1.0, 0.16, 0.22)
BONE = (0.96, 0.94, 0.9)
INK = (0.02, 0.02, 0.04)
WHITE_C = (1.0, 1.0, 1.0)

# clip-space points (0..1 of the 2560x1440 source)
ASHE_XY = (0.42, 0.45)                       # Ashe's body (her overhead bar sits at ~0.41)
K1_XY = (0.61, 0.42)                         # kill 1, right of centre
K2_XY = (0.43, 0.33)                         # kill 2 (Kalista), upper centre
ASHE_HP = (0.476, 0.974)                     # HUD 'NNN / 2305' readout centre
ASHE_HP_BOX = (0.442, 0.960, 0.510, 0.988)
YI_HP_BOX = (0.428, 0.959, 0.494, 0.987)     # HUD '65 / 1672' readout (centre 0.461, 0.973)
YI_KILL_XY = (0.57, 0.42)                    # '999' / gold pop after the camera jump

# pinned clip times
A_IN, A_K1, A_K2, A_HIT = 32.62, 32.867, 34.20, 34.50
C_IN, C_3HP, C_FREEZE = 34.80, 35.11, 35.20
Y_IN, Y_KILL, Y_OUT = 51.90, 52.575, 52.85


def g(b, s):
    """Video time of bar b, 16th s on the beat grid."""
    return song.beat(4 * b + s / 4.0)


def hit(b, s, win=0.05):
    """Grid time snapped to the strongest measured kick/snare onset within +-win s (the audible hit)."""
    t = g(b, s)
    best, bs = t, 0.0
    for kind in ('kick', 'snare'):
        for tt, st in song.onsets_s(kind, t - win, t + win):
            if st > bs:
                best, bs = tt, st
    return best


def word_t(sub, lo, hi, default):
    for w0, w1, w in song.words:
        if lo <= w0 < hi and sub in w.lower():
            return w0
    return default


def scr(c, x, y):
    """Clip point (x, y) -> screen point under camera c (no rotation)."""
    return 0.5 + c.ox + (x - c.cx) * c.zoom, 0.5 + c.oy + (y - c.cy) * c.zoom


def mix3(a, b, k):
    return tuple(lerp(x, y, k) for x, y in zip(a, b))


def build(E):
    # ------------------------------------------------------------------------------------------------ timing
    KILL1 = hit(7, 3)          # ~20.375  bar 7 16th 3 (808)
    HB1 = hit(7, 6)            # ~20.893  bar 7 16th 6 (808)
    LOCK0 = g(7, 8)            # ~21.24   bar 7 beat 3 ("oh" 21.20): brackets lock onto Ashe
    HB2 = g(7, 12)             # ~21.94   bar 7 beat 4
    KILL2 = hit(8, 0)          # ~22.633  bar 8 16th 0 (808)
    ROCKET = hit(8, 3)         # ~23.189  bar 8 16th 3 (808): the rocket hits Ashe
    HB3 = hit(8, 6)            # ~23.709  bar 8 16th 6 (808)
    CUT1 = g(8, 9)             # ~24.24   bar 8 16th 9 ("Every" 24.22): glitch cut to Yi, window +-0.1
    HB4 = g(8, 12)             # ~24.78   bar 8 beat 4: the bass drops out, heartbeat alone
    YIKILL = song.bar(9)       # 25.48    bar 9 16th 0 ("pop" 25.38 / "up" 25.60): Yi's kill
    CUT2 = hit(9, 4)           # ~26.163  bar 9 16th 4 (clap, "they"): hard cut back to Ashe
    STEP1 = hit(9, 6)          # ~26.521  bar 9 16th 6 (kick, "hoping"): step zoom onto Ashe
    STEP2 = hit(9, 9)          # ~27.049  bar 9 16th 9 (kick, "that"): snap to the HUD, HP hits 3
    CLAP = hit(9, 12)          # ~27.577  bar 9 16th 12 (clap)
    FALL_T = word_t('fall', 26.5, 28.3, 27.42)   # "fall" 27.42: freeze + FALL
    HARD_T = word_t('hard', 26.5, 28.3, 27.68)   # "hard" 27.68: HARD
    WHITE = 28.18              # full white from here to the seam
    WO0 = 27.92                # white-out ramp start
    A1 = CUT1 + 0.1            # end of shot A (end of the glitch window)
    B0 = CUT1 - 0.1            # start of shot B

    # ------------------------------------------------------------------------------------------------ cameras
    # Bottom-anchored framing (cy = 1 - 0.5/zoom) keeps the in-game HUD in frame while we push in.
    def camA(t):
        u = smooth((t - T_IN) / (ROCKET - T_IN))
        z = 1.07 + 0.13 * u + 0.06 * smooth((t - ROCKET) / 1.2)     # slow push: 1.07 -> 1.20 -> 1.26
        return Cam(zoom=z, cx=0.52 - 0.05 * u, cy=1 - 0.5 / z - 0.006)

    def camB(t):
        if t < YIKILL:
            z = 1.08 + 0.06 * smooth((t - B0) / (YIKILL - B0))
            cx = 0.52
        else:   # the game camera jumps with Alpha Strike at the kill; re-frame under the flash
            z = 1.14 + 0.06 * smooth((t - YIKILL) / 0.6)
            cx = 0.555                                                # <= 1 - 0.5/1.14 = 0.561
        return Cam(zoom=z, cx=cx, cy=1 - 0.5 / z - 0.006)

    def camC(t):
        # W1 wide (Ashe + HUD), W2 close on Ashe, W3 down on the HUD HP readout; 0.07 s snaps landing on the hits
        z1 = 1.22 + 0.04 * clamp((t - CUT2) / 0.36)
        w1 = (z1, 0.45, 1 - 0.5 / z1 - 0.006)
        z2 = 1.55 + 0.07 * clamp((t - STEP1) / 0.53)
        w2 = (z2, 0.43, 0.47)
        z3 = 2.3 + 0.25 * smooth((t - STEP2) / 1.2)                  # slow creep on the freeze
        w3 = (z3, 0.47, 1 - 0.5 / z3 - 0.006)
        k1 = smooth((t - (STEP1 - 0.045)) / 0.07)
        k2 = smooth((t - (STEP2 - 0.045)) / 0.07)
        z, cx, cy = (lerp(lerp(a, b, k1), c, k2) for a, b, c in zip(w1, w2, w3))
        return Cam(zoom=z, cx=cx, cy=cy)

    def ashe_A(t):
        return scr(camA(t), *ASHE_XY)

    # ------------------------------------------------------------------------------------------------ remaps
    # A: enter slow (0.35x) just before kill 1; velocity between the hits; 0.2x crawl after the rocket.
    #   19.82 -> 32.62                                  (purple volley flying right)
    #   KILL1 ~20.375 -> 32.867  mean 0.45x, cruise ~0.54x
    #   KILL2 ~22.633 -> 34.20   mean 0.59x, cruise ~0.77x  (rocket sits upper right, launches at ~33.87 = v~22.05)
    #   ROCKET ~23.189 -> 34.50  mean 0.54x, cruise ~0.74x  (HP 888 -> 69 one frame later)
    #   A1 ~24.34 -> 34.73       constant 0.2x (HP stays 69 until 34.767)
    rA = Remap([
        K(T_IN, A_IN, 0.35, (0.0, 0.0)),
        K(KILL1, A_K1, 0.25, (0.25, 0.5)),
        K(KILL2, A_K2, 0.3, (0.25, 0.5)),
        K(ROCKET, A_HIT, 0.2, (0.3, 0.5)),
        K(A1, A_HIT + 0.2 * (A1 - ROCKET), 0.2, (0.0, 0.0)),
    ])
    # B: 24.14 -> 51.90 (HP ~96, 65 from 52.0); kill 52.575 on bar 9 at 0.6x so the game's camera jump (52.57-52.58)
    #   passes in ~2 frames under the white flash; mean 0.50x, cruise ~0.47x. Then 0.6 -> 0.3x to 52.85 at the cut.
    rB = Remap([
        K(B0, Y_IN, 0.45, (0.0, 0.0)),
        K(YIKILL, Y_KILL, 0.6, (0.2, 0.55)),
        K(CUT2, Y_OUT, 0.3, (0.2, 0.3)),
    ])
    # C: 26.163 -> 34.80 (HP 54), HP 3 lands on STEP2 (35.11, mean 0.35x), brake to a freeze at 35.20 on "fall"
    #   (mean 0.24x, cruise ~0.36x), hold 35.20 (3/2305) to the white-out.
    rC = Remap([
        K(CUT2, C_IN, 0.3, (0.0, 0.0)),
        K(STEP2, C_3HP, 0.25, (0.25, 0.5)),
        K(FALL_T, C_FREEZE, 0.0, (0.2, 0.6)),
        K(T_OUT, C_FREEZE, 0.0, (0.0, 0.0)),
    ])

    # echo trails behind the rocket (max-blend of 2 earlier frames: only moving bright things ghost)
    def echo_k(t):
        a = smooth((t - 22.2) / 0.4) * (1 - smooth((t - (ROCKET - 0.12)) / 0.1))
        b = 0.7 * smooth((t - (ROCKET + 0.3)) / 0.25) * (1 - smooth((t - (A1 - 0.3)) / 0.15))
        return max(a, b)

    def src_A(t, ctx, shot):
        s = shot.s(t)
        c = shot.clip
        cur = c.at(s, shot.interp)
        k = echo_k(t)
        if k < 0.02:
            return cur
        import torch
        out = torch.maximum(cur, c.at(s - 0.045, False) * (0.72 * k))
        return torch.maximum(out, c.at(s - 0.09, False) * (0.45 * k))

    E.shot(T_IN, A1, ASHE, rA, cam=camA, src=src_A, name='s03 ashe rocket', hits=[KILL1, KILL2, ROCKET])
    E.shot(B0, CUT2, YI, rB, cam=camB, name='s03 yi 65hp', hits=[YIKILL])
    E.shot(CUT2, T_OUT, ASHE, rC, cam=camC, name='s03 ashe 3hp')
    E.transition(B0, A1, T.glitch(rate=30.0))

    # ------------------------------------------------------------------------------------------------ grade
    look(E, T_IN, T_OUT, 'paranoia')        # grey world, only reds survive, tunnel vignette (no fade: already drained)

    def tone(P, t):
        hud = smooth((t - (STEP2 - 0.04)) / 0.1)
        P['vignette'] = lerp(0.6, 0.3, hud)          # lighter tunnel so the HUD stays readable; open on the HUD close-up
        P['vignette_radius'] = 0.68
        P['contrast'] += 0.12 * hud
    E.post(T_IN, T_OUT, tone)

    # ------------------------------------------------------------------------------------------------ helpers
    def hit_fx(t, s=1.0, cx=0.5, cy=0.5, punch=0.09, shake_amt=0.012, flash=0.5, chroma=16.0, shock=True,
               color=WHITE_C, decay=0.14, fdecay=None, kick=0.3, cdecay=None):
        """engine impact() without the sound, every window clipped to this section's end, and a flash colour that
        only wins while this hit's flash is the brightest. fdecay = time constant of the flash and the exposure kick
        (default decay/2), kick = exposure stops per unit strength, cdecay = time constant of the RGB split (default
        decay). Short fdecay/cdecay keep a big hit from going milky: bright for a frame or two, clean by +0.15 s."""
        seed = int(hashf(t) * 1000)
        fd = decay * 0.5 if fdecay is None else fdecay
        cd = decay if cdecay is None else cdecay

        def scr_(tt):
            e = env(tt, t, 0.0, decay)
            ox, oy, r = shake(tt, shake_amt * s * env(tt, t, 0.0, decay * 1.6), 22.0, seed)
            return dict(zoom=1 + punch * s * e, ax=cx, ay=cy, ox=ox, oy=oy, rot=r * 0.6)
        E.screen(t, min(T_OUT, t + decay * 7), scr_)

        def post(P, tt):
            e = env(tt, t, 0.0, fd)
            f = flash * s * e
            if f > P['flash']:
                P['flash'], P['flash_color'] = f, color
            P['chroma'] += chroma * s * env(tt, t, 0.0, cd)
            P['chroma_cx'], P['chroma_cy'] = cx, cy
            P['exposure'] += kick * s * e
        E.post(t, min(T_OUT, t + decay * 6), post)
        if shock:
            def lay(img, tt, ctx):
                u = (tt - t) / 0.45
                if u < 0 or u > 1:
                    return img
                return fx.shockwave(img, cx, cy, radius=0.05 + 0.75 * eout(u), width=0.05 + 0.05 * u,
                                    strength=0.045 * s * (1 - u), ca=8 * s * (1 - u))
            E.layer(t, min(T_OUT, t + 0.45), lay, z=5)

    def heartbeat(t, cx=0.5, cy=0.5, amt=1.0, gain=-2.0):
        """Lub-dub sound (dub an eighth later) with a matching zoom thump, vignette squeeze and chroma pulse."""
        E.sfx('heartbeat', t, gain_db=gain, bpm=song.bpm)
        dub = 30.0 / song.bpm                          # 0.35 s
        for tt, a in ((t, 1.0), (t + dub, 0.6)):
            E.screen(tt, tt + 0.45, lambda x, tt=tt, a=a: dict(zoom=1 + 0.028 * amt * a * env(x, tt, 0.0, 0.08),
                                                               ax=cx, ay=cy))

            def post(P, x, tt=tt, a=a):
                e = env(x, tt, 0.0, 0.11) * a * amt
                P['vignette'] += 0.16 * e
                P['exposure'] -= 0.16 * e
                P['chroma'] += 5.0 * e
            E.post(tt, tt + 0.5, post)

    def tear(t0, dur, amt, n):
        def f(img, t, ctx):
            e = env(t, t0, 0.0, dur)
            if e < 0.03:
                return img
            return fx.slices(img, n=n, offset=amt * e, axis='x')
        return f

    def glitch_spike(t0, amt, dur):
        def f(P, t):
            e = amt * env(t, t0, 0.0, dur)
            if e > 0.03:
                P['glitch'] = max(P['glitch'], e)
        return f

    def hud_lock(t0, t1, camfn, box, close=0.22):
        """Red brackets closing onto a HUD readout (box in clip space), blinking once locked."""
        def f(img, t, ctx):
            if not (t0 <= t < t1):
                return img
            c = camfn(t)
            x0, y0 = scr(c, box[0], box[1])
            x1, y1 = scr(c, box[2], box[3])
            asp = ctx['W'] / ctx['H']
            k = eout((t - t0) / close)
            pad = (1 - k) * 0.07
            al = clamp((t - t0) / 0.05)
            if k > 0.995 and int((t - t0) * 7) % 2 == 1:
                al *= 0.6
            return fx.brackets(img, x0 - pad / asp, y0 - pad, x1 + pad / asp, min(0.994, y1 + pad), 0.3, 0.0035,
                               RED, al)
        return f

    # ------------------------------------------------------------------------------------------------ A: Ashe
    # 19.82 bar 7 16th 0: hard cut from s02's colour into grey slow-mo; the floor drops out (settle punch, dip)
    E.screen(T_IN, T_IN + 0.8, lambda t: dict(zoom=1 + 0.09 * env(t, T_IN, 0.0, 0.13), ax=0.45, ay=0.4))

    def enter(P, t):
        P['exposure'] -= 0.35 * env(t, T_IN, 0.0, 0.25)
        P['chroma'] += 12.0 * env(t, T_IN, 0.0, 0.1)
    E.post(T_IN, T_IN + 1.2, enter)
    E.sfx('subdrop', T_IN, gain_db=-3, dur=1.4)

    # kill 1 on bar 7 16th 3 (clip 32.867): red hit where the gold pops; the rocket appears at the same moment
    k1x, k1y = scr(camA(KILL1), *K1_XY)
    hit_fx(KILL1, 0.9, k1x, k1y, punch=0.07, flash=0.3, chroma=14, color=RED)
    E.sfx('impact', KILL1, gain_db=-5, strength=0.9)

    heartbeat(HB1, *ashe_A(HB1))                       # bar 7 16th 6 (808); dub at LOCK0
    # the brackets that hunted enemies in s02 flip onto the player as the rocket aims at her
    E.layer(LOCK0, ROCKET, L.lock(LOCK0, ROCKET, 0.5, 0.5, size=0.15, color=RED, label='TARGET: ART3M1S',
                                  follow_fn=ashe_A), z=4)
    E.sfx('tick', LOCK0, gain_db=-7)
    E.sfx('tick', LOCK0 + 0.35, gain_db=-4)
    heartbeat(HB2, *ashe_A(HB2), amt=0.8)              # bar 7 beat 4

    # kill 2 on bar 8 16th 0 (clip 34.20)
    k2x, k2y = scr(camA(KILL2), *K2_XY)
    hit_fx(KILL2, 0.8, k2x, k2y, punch=0.06, flash=0.28, chroma=12, color=RED)
    E.sfx('impact', KILL2, gain_db=-6, strength=0.8)

    # the rocket hits Ashe on bar 8 16th 3 (clip 34.50): biggest hit of the section
    ax_, ay_ = ashe_A(ROCKET)
    E.sfx('whoosh', ROCKET - 0.06, dur=1.2, direction='rl', gain_db=-7, bright=0.8)   # rocket sweeping right->left
    # round 2 (haze): red flash peak 0.45 (was 0.75) gone in ~3 frames, a +0.5-stop exposure kick instead of the long
    # lift, RGB split 27 px decaying fast (5 px at +0.15 s), lighter shake. +0.15 s (23.34) is a clean frame again.
    hit_fx(ROCKET, 1.5, ax_, ay_, punch=0.1, shake_amt=0.013, flash=0.3, chroma=18, color=RED, decay=0.17,
           fdecay=0.04, kick=0.35, cdecay=0.09)
    E.post(ROCKET, ROCKET + 0.3, glitch_spike(ROCKET, 0.55, 0.05))
    E.layer(ROCKET, ROCKET + 0.25, tear(ROCKET, 0.05, 0.03, 9), z=6)
    E.sfx('impact', ROCKET, gain_db=-2, strength=1.6)
    E.sfx('boom', ROCKET, gain_db=-5, dur=1.8)
    # the lock falls onto the HUD HP readout: 69 / 2305
    E.layer(ROCKET + 0.06, B0, hud_lock(ROCKET + 0.06, B0, camA, ASHE_HP_BOX), z=4)
    E.sfx('tick', ROCKET + 0.28, gain_db=-5)
    heartbeat(HB3, *ashe_A(HB3), amt=0.9)              # bar 8 16th 6 (808): still alive

    # ------------------------------------------------------------------------------------------------ B: Yi
    # Yi's jungle is much lighter than Ashe's lane and read flat grey: a little darker and harder while he's on screen
    # (eases in under the glitch cut, ends on the hard cut back at CUT2)
    def yi_grade(P, t):
        k = smooth((t - B0) / (A1 - B0))
        P['contrast'] += 0.1 * k
        P['exposure'] -= 0.1 * k
    E.post(B0, CUT2, yi_grade)
    E.sfx('glitch', B0, gain_db=-5, dur=0.22)
    E.layer(CUT1 + 0.12, YIKILL, hud_lock(CUT1 + 0.12, YIKILL, camB, YI_HP_BOX), z=4)   # 65 / 1672
    E.sfx('tick', CUT1 + 0.34, gain_db=-5)
    heartbeat(HB4, 0.5, 0.42, amt=1.1, gain=0.0)       # bar 8 beat 4: the bass drops out, only the heart is left

    # Yi's kill on bar 9 16th 0 ("pop up"): colour bursts back in. The game camera's jump (source 52.567 -> 52.583)
    # lands on 25.48 together with our re-frame, and clip.at() no longer morphs across it, so it is a clean hard cut
    # on the kill: no long white needed to hide it. Round 2 (25.52 was washed out): white pop 0.55 for ~2 frames
    # (was 0.94 decaying over ~8 frames), short exposure kick, RGB split 18 px decaying fast.
    yx, yy = scr(camB(YIKILL), *YI_KILL_XY)
    hit_fx(YIKILL, 1.1, yx, yy, punch=0.1, flash=0.5, chroma=16, color=WHITE_C, decay=0.15, fdecay=0.025,
           kick=0.4, cdecay=0.08)
    E.sfx('impact', YIKILL, gain_db=-2, strength=1.3)
    E.sfx('zap', YIKILL, gain_db=-7, dur=0.25)

    def burst(P, t):
        e = env(t, YIKILL, 0.0, 0.3)
        P['pop'] *= 1 - 0.92 * e
        P['sat'] += 0.35 * e
        P['contrast'] += 0.12 * e        # the colour comes back punchy, not flat olive
    E.post(YIKILL, CUT2, burst)

    # ------------------------------------------------------------------------------------------------ C: Ashe 3 HP
    # bar 9 16th 4 (clap, "they"): hard cut back, punch-out settle
    cx_, cy_ = scr(camC(CUT2), *ASHE_XY)
    hit_fx(CUT2, 0.9, cx_, cy_, punch=0.14, flash=0.35, chroma=16, shock=False, color=RED)
    E.sfx('impact', CUT2, gain_db=-6, strength=0.9)
    E.sfx('riser', T_OUT, gain_db=-4, dur=T_OUT - CUT2)        # ends dead at the drop (28.28)
    E.sfx('reverse', T_OUT, gain_db=-5, dur=0.9)

    # bar 9 16th 6 (kick, "hoping"): step zoom onto Ashe
    sx_, sy_ = scr(camC(STEP1 + 0.03), *ASHE_XY)
    hit_fx(STEP1, 0.6, sx_, sy_, punch=0.06, flash=0.0, chroma=12, shock=True)
    E.sfx('whoosh', STEP1 - 0.02, dur=0.2, direction='in', gain_db=-9)

    # bar 9 16th 9 (kick, "that"): snap down to the HUD as HP drops to 3/2305; brackets lock onto it
    hx, hy = scr(camC(STEP2 + 0.04), *ASHE_HP)
    hit_fx(STEP2, 0.8, hx, min(0.97, hy), punch=0.05, flash=0.3, chroma=14, color=RED)
    E.sfx('whoosh', STEP2 - 0.02, dur=0.2, direction='in', gain_db=-9)
    E.sfx('impact', STEP2, gain_db=-6, strength=0.8)
    E.layer(STEP2, T_OUT, hud_lock(STEP2, T_OUT, camC, ASHE_HP_BOX, close=0.18), z=4)

    # "fall" 27.42: freeze-frame (shutter + camera flash). Round 2 (haze): a photo-flash pop of 0.55 that is gone in
    # ~3 frames (was 0.75 with a 0.07 s tail that left 27.43-27.57 milky grey) plus a short exposure kick.
    def freeze(P, t):
        f = smooth((t - FALL_T) / 0.05)
        P['contrast'] += 0.15 * f
        P['grain'] = max(P['grain'], 0.07 * f)
        e = env(t, FALL_T, 0.0, 0.028)
        if 0.55 * e > P['flash']:
            P['flash'], P['flash_color'] = 0.55 * e, WHITE_C
        P['exposure'] += 0.3 * e
    E.post(FALL_T, T_OUT, freeze)
    E.sfx('shutter', FALL_T, gain_db=-2)

    # bar 9 16th 12 (clap): tear + shockwave out of the HP readout
    hx2, hy2 = scr(camC(CLAP), *ASHE_HP)
    hit_fx(CLAP, 0.7, hx2, min(0.97, hy2), punch=0.04, flash=0.22, chroma=18, color=RED, decay=0.12)
    E.layer(CLAP, CLAP + 0.2, tear(CLAP, 0.04, 0.025, 12), z=6)

    # "hard" 27.68
    hit_fx(HARD_T, 0.6, 0.5, 0.42, punch=0.035, flash=0.0, chroma=12, shock=False, decay=0.12)
    E.sfx('impact', HARD_T, gain_db=-7, strength=0.7)

    # white-out: ramp 27.92 -> 1.0 at 28.18, hold to the seam (vignette and grain off so it is pure white)
    def whiteout(P, t):
        k = smooth((t - WO0) / (WHITE - WO0))
        gl = 0.4 * smooth((t - (WO0 - 0.15)) / 0.25) * (1 - k)
        if gl > 0.03:
            P['glitch'] = max(P['glitch'], gl)
        if k <= 0:
            return
        if k >= P['flash']:
            P['flash'], P['flash_color'] = k, WHITE_C
        P['exposure'] += 0.5 * k
        P['vignette'] *= 1 - k
        P['grain'] *= 1 - k
        P['zoom_blur'] = max(P['zoom_blur'], 0.35 * k)
        P['zoom_blur_cx'], P['zoom_blur_cy'] = 0.5, 0.45
    E.post(WO0 - 0.15, T_OUT, whiteout)

    # ------------------------------------------------------------------------------------------------ overlays
    # ECG trace (crisp, top): spikes on the three pre-drop hits, then a flatline that runs into the white-out
    BEATS = (CUT2, STEP1, STEP2)
    E0 = CUT2 - 0.3
    XA, XB, Y0, AMP = 0.06, 0.94, 0.73, 0.075

    def qrs(u):
        return (math.exp(-(u / 0.011) ** 2) - 0.32 * math.exp(-((u - 0.03) / 0.012) ** 2)
                + 0.14 * math.exp(-((u - 0.16) / 0.045) ** 2) + 0.08 * math.exp(-((u + 0.1) / 0.03) ** 2))

    def ecg(img, t, ctx):
        if t < CUT2 or t >= T_OUT:
            return img
        import torch
        H, W = img.shape[1], img.shape[2]
        dev = img.device
        span = WHITE - E0
        xs = (torch.arange(W, device=dev, dtype=torch.float32) + 0.5) / W
        tau = E0 + (xs - XA) / (XB - XA) * span
        yv = torch.zeros_like(xs)
        for hb in BEATS:
            u = tau - hb
            yv = yv + (torch.exp(-(u / 0.011) ** 2) - 0.32 * torch.exp(-((u - 0.03) / 0.012) ** 2)
                       + 0.14 * torch.exp(-((u - 0.16) / 0.045) ** 2) + 0.08 * torch.exp(-((u + 0.1) / 0.03) ** 2))
        yp = (Y0 - AMP * yv) * H
        yl = torch.cat([yp[:1], yp[:-1]])
        yr = torch.cat([yp[1:], yp[-1:]])
        lo = torch.minimum(yp, torch.minimum((yp + yl) / 2, (yp + yr) / 2))
        hi = torch.maximum(yp, torch.maximum((yp + yl) / 2, (yp + yr) / 2))
        rows = (torch.arange(H, device=dev, dtype=torch.float32) + 0.5).view(H, 1)
        d = torch.relu(lo.view(1, W) - rows) + torch.relu(rows - hi.view(1, W))
        sc = H / 1080.0
        core = torch.clamp(1.3 * sc + 0.5 - d, 0, 1)
        glow = torch.clamp(1 - d / (12 * sc), 0, 1) ** 2 * 0.4
        xp = XA + (XB - XA) * clamp((t - E0) / span)
        vis = ((xs >= XA) & (xs <= xp)).float()
        fade = 0.3 + 0.7 * torch.clamp(1 - (xp - xs) / 0.85, 0, 1)
        a = clamp((t - CUT2) / 0.08)
        m = (torch.clamp(core + glow, 0, 1) * (vis * fade).view(1, W) * a)[None]
        col = torch.tensor(RED, device=dev, dtype=img.dtype).view(3, 1, 1)
        img = img * (1 - m) + col * m
        tp = min(t, WHITE)
        ypen = Y0 - AMP * sum(qrs(tp - hb) for hb in BEATS)
        img = fx.disc(img, xp, ypen, 0.022, RED, 0.35 * a, soft=0.02)
        return fx.disc(img, xp, ypen, 0.0065, (1.0, 0.8, 0.8), a)
    E.top(CUT2, T_OUT, ecg, z=1)

    # FALL / HARD lyric slams (crisp, top): one line, each word on its sung syllable; they turn to ink in the white
    TEXT_Y = 0.40

    def fallhard(img, t, ctx):
        if t < FALL_T or t >= T_OUT:
            return img
        size, gap, trk = 0.2, 0.025, 0.02
        wf = ty.width('FALL', size, 'anton', trk)
        wh = ty.width('HARD', size, 'anton', trk)
        tot = wf + gap + wh
        if tot > 0.84:
            k = 0.84 / tot
            size, wf, wh, gap = size * k, wf * k, wh * k, gap * k
            tot = 0.84
        x0 = 0.5 - tot / 2
        wo = smooth((t - WO0) / (WHITE - WO0))
        for word, tw, xc, ww, base in (('FALL', FALL_T, x0 + wf / 2, wf, BONE),
                                       ('HARD', HARD_T, x0 + wf + gap + wh / 2, wh, RED)):
            u = t - tw
            if u < 0:
                continue
            k = eout(u / 0.09)
            # slam-in scale: at most 2.2x, and never so big that a letter leaves x 0.07-0.93 / y 0.08-0.90 (the frame
            # rule is 0.05-0.95 / 0.06-0.92; the extra 0.02 covers the shake and the RGB split). Round 1 slammed from
            # 2.6x, which pushed HARD's right edge to ~0.98 on its first frame.
            s0 = min(2.2, (0.93 - xc) / (ww / 2), (xc - 0.07) / (ww / 2),
                     (0.90 - TEXT_Y) / (size / 2), (TEXT_Y - 0.08) / (size / 2))
            sc = lerp(max(1.0, s0), 1.0, k) * (1 + 0.03 * clamp((u - 0.09) / 0.8))
            al = clamp(u / 0.035)
            ox, oy, r = shake(t, 0.007 * env(t, tw + 0.07, 0.0, 0.16), 26.0, int(tw * 100))
            img = ty.text(img, word, xc + ox, TEXT_Y + oy, size, 'anton', mix3(base, INK, wo), sc, r, al,
                          tracking=trk, stroke=0.0035 * (1 - wo), stroke_color=INK, glow=0.9 * (1 - wo),
                          glow_color=RED, split=(4.0 + 14.0 * env(t, tw + 0.06, 0.0, 0.12)) * (1 - wo))
        return img
    E.top(FALL_T, T_OUT, fallhard, z=2)

    # ------------------------------------------------------------------------------------------------ music
    # muffle the song under the break and open it as the drums come back on bar 9 16th 4
    def muffle(tt):
        knots = [T_IN, 21.2, KILL2, 24.22, YIKILL, 26.05, CUT2]
        hz = [750.0, 950.0, 1300.0, 2300.0, 5000.0, 15000.0, 20000.0]
        return np.exp(np.interp(np.asarray(tt, dtype=np.float64), knots, np.log(hz)))
    E.music('lowpass', T_IN, CUT2, cutoff=muffle)
    # pre-drop: the end of "hard" gets sucked into the drop
    E.music('lowpass', 27.80, T_OUT - 0.005, cutoff_from=18000.0, cutoff_to=1600.0)
