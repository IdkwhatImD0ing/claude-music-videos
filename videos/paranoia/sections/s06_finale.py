"""s06 FINALE: Samira's 7%-HP pentakill (bars 18-21 + the song's tail, video t 50.88-62.50).

One continuous, velocity-edited take of clip 2026-02-22__20-45-40 (ARAM). Register: ROCK STAR, then the surveillance
callback and the end card.

  50.70-51.06   zoom-through in from s05 (owned here; cut on the bar-18 downbeat 50.88, kick 50.871)
  51.405        bar 18 16th 3 (kick): TRIPLE KILL (clip 14.983). Strobes on 16ths 6 and 9, speed lines that follow
                the footage's own speed (cruise 3.2x), then a 4-step zoom ladder on the snare roll (16ths 12-15)
  53.70         bar 19 16th 0: QUADRA KILL (clip 20.05). Fast-forward 2.9x while her HP crashes: an HP readout counts
                down with the clip (24% at clip 21.5 -> 9% at 24.0 -> 7% at 24.5), red low-HP pulses + heartbeat
                on the kicks of 16ths 6 and 9
  55.811        16th 12 ("born"): HP 7%. Colour drains to red-only, tunnel spotlight, the song muffles (lowpass),
                slow-mo 0.45x, reverse cymbal into
  56.54         bar 20 16th 0: PENTAKILL (clip 24.733; the recorded camera snaps onto the fight on this exact frame).
                2-frame invert, flash, 0.13 s hit-stop on the '999' frame, double rings, speed-line burst, zoom blur,
                boom + sub drop. Colour slams back 'hot'. PENTAKILL / AT 7% HP. Slow-mo afterglow with echo trails;
                last drum hits 16ths 3 + 4 (57.043 kick, 57.221 clap) get strobes
  57.70         the beat drops out (a cappella "death of a"): the world breathes (desat, slow 3D drift, letterbox)
  58.50         "ROCK": letters slam, colour snaps back, the footage ramps to 1.5x toward the big burst
  58.88         "STAR" (the 'st' sibilant): letters slam, speed lines + RGB split rush into
  59.32         bar 21 16th 0, where the song's vocal stops dead: the big red-orange burst (clip 26.20; not the Nexus, the game didn't end here). 3-frame white
                flash (0.6) + exposure blow-out, boom. ROCKSTAR scrambles and decodes into PARANOIA by 59.62 (same
                layout as s01's title: Anton 0.2 at y 0.56)
  60.02         freeze-frame (shutter), colour drained to red, surveillance HUD returns: REC / CAM 06, brackets
                lock onto Samira, 'SUBJECT: ALIVE' typed out; heartbeats on 60.72 and 61.42
  61.90-62.50   fade to black
"""
import math

import torch

from engine.api import *

SPAN = (50.88, 62.50)
CLIP = 'League-of-Legends__2026-02-22__20-45-40.mp4'

# --- palette (TREATMENT "Look") ---
RED = (1.0, 0.16, 0.22)
CYAN = (0.2, 0.95, 1.0)
BONE = (0.96, 0.94, 0.9)
INK = (0.02, 0.02, 0.04)
GOLD = (1.0, 0.82, 0.3)
WHITE = (1.0, 1.0, 1.0)

# --- pinned clip times (from out/wip/kills/*_14.95/_20.05/_24.65/_26.50.jpg, frame = clip time * 60) ---
S_IN = 14.42             # fight already on screen at (0.5, 0.37)
S_TRIPLE = 899 / 60      # 14.983: big white '999' crit + '+100' gold + LEVEL UP pop (14.950 has only the slash)
S_QUADRA = 1203 / 60     # 20.050: big '999' crit inside the red slash at (0.50, 0.29); QUADRA KILL banner 20.117
S_PENTA = 1484 / 60      # 24.733: recorded camera snaps onto the fight AND the big '999' + '+200' gold pop at
                         #         (0.42, 0.53); frame 1483 (24.717) is still the old framing (fight at the top-right,
                         #         0.70, 0.25). Round-1 review: frame 1484 (not in the 1/30 s kill strip) already shows
                         #         the snap, so with 1485 the '999' appeared 2 frames before the hit (56.517).
S_BOOM = 1572 / 60       # 26.200: the big burst's first frame (whole screen washes pink-white); white core
                         #         26.267 at (0.62, 0.29), red spray 26.333+, red fills the frame by 26.467
S_FREEZE = 1588 / 60     # 26.467: red spray everywhere, Samira (bar 'Art3m1s' at (0.555, 0.23)) at (0.555, 0.33)
JUMP_F0, JUMP_F1 = 1483, 1484   # the last old-framing frame and the snap frame: never RIFE-blend across them

# Samira's HP from the scouting notes (max 2716): 650 (24%) at 21.5, 235 (8.7%) at 24.0, ~190 (7%) from 24.5 on
HP_PTS = [(21.5, 24.0), (24.0, 8.65), (24.5, 7.0)]

# where things are in the CLIP (u, v) at the moments we hit them
P_TRIPLE = (0.50, 0.37)
P_QUADRA = (0.50, 0.30)
P_PENTA = (0.46, 0.47)          # between the dying enemy's '999' (0.42, 0.53) and the R ring centre (0.55, 0.42)
P_FIGHT_PRE = (0.70, 0.25)      # the fight before the camera snap (24.0-24.73)
P_BOOM = (0.62, 0.29)
SAMIRA_BOX = (0.50, 0.19, 0.61, 0.40)   # her HP bar + body on the frozen frame 26.467

A_WORD, B_WORD = 'ROCKSTAR', 'PARANOIA'
GLYPHS = 'ABCDEFGHJKLMNOPQRSTUVWXYZ0123456789#%&@'
TITLE_Y, TITLE_SIZE, TITLE_TRACK = 0.56, 0.2, 0.04      # = s01's title, so the end card answers the opening card


# --- timing helpers ---------------------------------------------------------------------------------------------
def g16(bar, n):
    """Grid time of 16th n in bar `bar`."""
    a, b = song.bar(bar), song.bar(bar + 1)
    return a + (b - a) * n / 16.0


def on(bar, n, tol=0.04):
    """The measured kick/snare onset nearest to 16th n of `bar` (downbeats use the bar time itself)."""
    t = g16(bar, n)
    if n == 0:
        return t
    best = None
    for kind in ('kick', 'snare'):
        for x in song.onsets(kind, t - tol, t + tol):
            if best is None or abs(x - t) < abs(best - t):
                best = x
    return t if best is None else best


def word_t(sub, lo, hi, default):
    for w0, w1, w in song.words:
        if lo <= w0 < hi and sub in w.lower():
            return w0
    return default


def hp_pct(s):
    if s <= HP_PTS[0][0]:
        return HP_PTS[0][1]
    for (s0, h0), (s1, h1) in zip(HP_PTS, HP_PTS[1:]):
        if s <= s1:
            return lerp(h0, h1, (s - s0) / (s1 - s0))
    return HP_PTS[-1][1]


def mix3(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


# --- local grades (round 2, HAZE note): 'hot' without the milk. The engine's 'hot' (bloom 0.6 from 0.75 up,
# exposure +0.1) stacked with flashes and exposure kicks into a white veil; these keep the colour and the contrast.
HOT_CLEAN = dict(contrast=1.26, sat=1.45, bloom=0.36, bloom_threshold=0.84, shadows=(0.03, 0.0, 0.06),
                 highlights=(0.05, 0.0, -0.03), vignette=0.25)
# the Nexus blast: the clip's own explosion is already pink-white, so push contrast and keep bloom low (the
# exposure dip is added separately, nexus_dim, so impact()'s exposure kick is not overwritten)
NEXUS_GRADE = dict(contrast=1.36, sat=1.4, bloom=0.22, bloom_threshold=0.9, shadows=(0.03, 0.0, 0.06), vignette=0.3)


def look2(E, t0, t1, preset, fade_in=0.0, fade_out=0.0, amount=1.0):
    """engine look() with a local preset dict (blends numbers/tuples from the current params)."""
    def f(P, t):
        k = amount
        if fade_in > 0:
            k *= smooth((t - t0) / fade_in)
        if fade_out > 0:
            k *= smooth((t1 - t) / fade_out)
        for key, v in preset.items():
            a = P[key]
            if isinstance(v, tuple):
                P[key] = tuple(x + (y - x) * k for x, y in zip(a, v))
            else:
                P[key] = a + (v - a) * k
    E.post(t0, t1, f)


def build(E):
    # =========================================== timing =============================================================
    # Bars: 18 -> 50.88, 19 -> 53.70, 20 -> 56.54, 21 -> 59.32 (16th = 0.176 s). Measured onsets in brackets.
    T_IN = 50.70                       # zoom-through window 50.70-51.06 (s05's last shot runs to 51.06)
    T_ZOUT = 51.06
    T_CUT = song.bar(18)               # 50.88 bar 18 16th 0 (kick 50.871): cut point of the zoom-through
    T_TRIPLE = on(18, 3)               # 51.405 bar 18 16th 3 (kick)
    T_S6 = on(18, 6)                   # 51.929 16th 6 (kick)
    T_S9 = on(18, 9)                   # 52.455 16th 9 (kick)
    LADDER = [on(18, 12), on(18, 13), on(18, 14), on(18, 15)]   # 52.987 53.161 53.339 53.517: the snare roll
    T_QUAD = song.bar(19)              # 53.70 bar 19 16th 0 (kick 53.709, snare 53.691)
    T_Q3 = on(19, 3)                   # 54.221 16th 3 (kick)
    T_HP0 = on(19, 6)                  # 54.753 16th 6 (kick): HP readout appears, heartbeat
    T_HP9 = on(19, 9)                  # 55.283 16th 9 (kick): heartbeat
    T_CRIT = on(19, 12)                # 55.811 16th 12 (kick, "born"): 7% HP
    T_C13 = on(19, 13)                 # 56.005 16th 13 (extra kick of the fill)
    HB = [T_HP0, T_HP9, T_CRIT, T_C13]
    T_PENTA = song.bar(20)             # 56.54 bar 20 16th 0 (kick 56.517, low-band peak 56.54)
    T_STOP = T_PENTA + 0.13            # 56.67 end of the hit-stop
    T_P3 = on(20, 3)                   # 57.043 16th 3 (kick): last kick of the song
    T_P4 = on(20, 4)                   # 57.221 16th 4 (clap): last drum hit
    T_ACAP = 57.70                     # measured: the beat and bass cut out (low band -10 -> -45 dB, 57.68-57.74)
    T_ROCK = word_t('rock', 58.0, 59.2, 58.50)   # 58.50 "rockstar" (sung 58.50-59.38)
    T_STAR = 58.88                     # measured: the 'st' sibilant of "star" (3 kHz+ band peak 58.86-58.94)
    T_END = song.bar(21)               # 59.32 bar 21: the a cappella "star" stops dead at 59.36-59.40, then silence
    T_FREEZE = g16(21, 4)              # 60.02 bar 21 beat 2 (no music left; keep the grid)
    T_TYPE = T_FREEZE + 0.28           # 60.30 label typing starts
    HEARTS = [g16(21, 8), g16(21, 12)]  # 60.72, 61.42 heartbeats under the end card
    GLITCHES = [g16(21, 6), g16(21, 10), g16(21, 14)]   # 60.37, 61.07, 61.77 title glitch flickers
    T_FADE = 61.90
    T_OUT = 62.50

    # =========================================== remap ==============================================================
    # One continuous take. Keys (video t -> clip s, speed):
    #   50.70 -> 14.420 @1.0          enter at real speed (only visible after the 50.88 cut)
    #   51.405 -> 14.983 @0.3         TRIPLE on bar 18 16th 3 (segment mean 0.80x, cruise 0.99x, brakes over 55%)
    #   51.585 -> 15.037 @0.3         hold the slow-mo one 16th
    #   53.70 -> 20.050 @0.3          QUADRA on bar 19 16th 0 (mean 2.37x, cruise 3.16x; brake starts 53.17, so the
    #                                 snare-roll ladder 52.99-53.52 rides the deceleration)
    #   53.88 -> 20.104 @0.3          hold one 16th
    #   55.811 -> 24.420 @0.45        HP 7.3% on 16th 12 (mean 2.24x, cruise 2.94x: the HP crash flies by)
    #   56.54 -> 24.733 @0.45         PENTA on bar 20 16th 0 (constant 0.43x: the near-death slow-mo; the
    #                                 camera snap, frame 1484, first shows on the 56.55 frame = the invert)
    #   56.67 -> 24.733 @0            hit-stop: 0.13 s freeze on the '999' frame
    #   57.70 -> 25.060 @0.3          afterglow (mean 0.32x, cruise 0.38x, eases out of the freeze)
    #   58.50 -> 25.300 @0.3          a cappella, constant 0.30x
    #   59.32 -> 26.200 @0.35         NEXUS on bar 21 (mean 1.10x, cruise 1.47x: the rush on "ROCK-STAR")
    #   60.02 -> 26.467 @0            constant 0.38x through the explosion, then a hard freeze (frame 1588)
    #   62.50 -> 26.467 @0            frozen end card
    R = Remap([
        K(T_IN, S_IN, 1.0, (0.0, 0.0)),
        K(T_TRIPLE, S_TRIPLE, 0.3, (0.2, 0.55)),
        K(T_TRIPLE + 0.18, S_TRIPLE + 0.18 * 0.3, 0.3, (0.0, 0.0)),
        K(T_QUAD, S_QUADRA, 0.3, (0.3, 0.25)),
        K(T_QUAD + 0.18, S_QUADRA + 0.18 * 0.3, 0.3, (0.0, 0.0)),
        K(T_CRIT, 24.42, 0.45, (0.25, 0.3)),
        K(T_PENTA, S_PENTA, 0.45, (0.0, 0.0)),
        K(T_STOP, S_PENTA, 0.0, (0.0, 0.0)),
        K(T_ACAP, 25.06, 0.3, (0.35, 0.0)),
        K(T_ROCK, 25.30, 0.3, (0.0, 0.0)),
        K(T_END, S_BOOM, 0.35, (0.3, 0.35)),
        K(T_FREEZE, S_FREEZE, 0.0, (0.0, 0.0)),
        K(T_OUT, S_FREEZE, 0.0, (0.0, 0.0)),
    ])

    # =========================================== camera =============================================================
    # cx, cy = clip point at screen centre, clamped so the frame never leaves the clip (cx in [0.5/z, 1 - 0.5/z]).
    F1 = follow([(T_IN, 0.50, 0.46), (T_QUAD, 0.50, 0.45), (54.70, 0.55, 0.43), (55.60, 0.61, 0.40),
                 (T_PENTA, 0.62, 0.39)])                      # before the camera snap: drift up-right with the fight
    F2 = follow([(T_PENTA, 0.50, 0.43), (T_ACAP, 0.53, 0.43), (T_ROCK, 0.57, 0.42), (T_END, 0.60, 0.42),
                 (T_FREEZE, 0.60, 0.45), (T_OUT, 0.60, 0.45)])  # after the snap: penta, then toward the Nexus

    def zoom_at(t):
        if t < T_QUAD:
            return 1.08                                                    # HUD mostly in frame for the run
        if t < T_CRIT:
            return lerp(1.08, 1.24, smooth((t - T_QUAD) / (T_CRIT - T_QUAD)))
        if t < T_PENTA:
            return lerp(1.24, 1.30, (t - T_CRIT) / (T_PENTA - T_CRIT))    # tunnel creep
        if t < T_ROCK:
            return lerp(1.22, 1.30, smooth((t - T_PENTA) / (T_ROCK - T_PENTA)))
        if t < T_END:
            return lerp(1.30, 1.45, ein((t - T_ROCK) / (T_END - T_ROCK)))   # the rush into the Nexus
        if t < T_END + 0.6:
            return lerp(1.45, 1.30, eout((t - T_END) / 0.6))                # blast recoil
        return lerp(1.30, 1.40, smooth((t - T_END - 0.6) / (T_OUT - T_END - 0.6)))   # slow push on the end card

    def tilt(t):
        """Slow 3D drift while the beat is gone (a cappella), snapping flat on 'ROCK'."""
        if T_ACAP <= t < T_ROCK:
            u = smooth((t - T_ACAP) / (T_ROCK - T_ACAP))
            return -2.5 * u, 3.5 * u, 1.0 + 0.03 * u
        return 0.0, 0.0, 1.0

    def cam(t):
        z = zoom_at(t)
        yaw, pitch, zk = tilt(t)
        z *= zk
        px, py = (F1 if t < T_PENTA else F2)(t)
        m = 0.5 / z
        return Cam(zoom=z, cx=clamp(px, m, 1 - m), cy=clamp(py, m, 1 - m), yaw=yaw, pitch=pitch)

    def scr(t, u, v):
        """Clip point (u, v) -> screen point at time t (ignores the small 3D tilt)."""
        c = cam(t)
        return (u - c.cx) * c.zoom + 0.5, (v - c.cy) * c.zoom + 0.5

    # screen points of the hits:
    #   triple  t 51.405: z 1.08, centre (0.50, 0.463) -> (0.50, 0.40)
    #   quadra  t 53.70 : z 1.08, centre (0.50, 0.463) -> (0.50, 0.32)
    #   penta   t 56.54 : z 1.22, centre (0.50, 0.43)  -> (0.45, 0.55)
    #   nexus   t 59.32 : z 1.45, centre (0.60, 0.42)  -> (0.53, 0.31)
    TX, TY = scr(T_TRIPLE, *P_TRIPLE)
    QX, QY = scr(T_QUAD, *P_QUADRA)
    PX, PY = scr(T_PENTA, *P_PENTA)
    NX, NY = scr(T_END, *P_BOOM)

    # =========================================== source sampling ====================================================
    def echo_w(t):
        if t < T_STOP + 0.08 or t >= T_ACAP:
            return 0.0
        return smooth((t - T_STOP - 0.08) / 0.25) * smooth((T_ACAP - t) / 0.25)

    def split_d(t):
        if t < T_END or t >= T_FREEZE - 0.02:
            return 0.0
        return 0.03 * env(t, T_END + 0.08, 0.08, 0.22)

    def src(t, ctx, shot):
        c = shot.clip
        s = shot.s(t)
        fi = s * c.fps
        if JUMP_F0 <= fi < JUMP_F1:
            # between frame 1483 (old framing) and the snap frame 1484: show the real frame 1483 (no RIFE morph
            # across the cut; clip.at() now guards this too); 1483.99+ (float error at S_PENTA) rounds onto 1484.
            # Frame times: 56.533 -> fi 1483.8 (old framing), 56.550 -> fi 1484.27 (snap, = the invert frame)
            return c.frame(JUMP_F1 if fi > JUMP_F1 - 0.01 else JUMP_F0)
        we = echo_w(t)
        if we > 0.01:
            # echo trails in the afterglow: the last 0.045 / 0.09 s of clip ghosted behind (never before the snap)
            acc = c.at(s).float()
            tot = 1.0
            for k, a in ((1, 0.6), (2, 0.35)):
                acc = acc + c.at(max(S_PENTA, s - 0.045 * k)).float() * (a * we)
                tot += a * we
            return acc / tot
        d = split_d(t)
        if d > 0.002:
            # RGB time split through the explosion: green and blue lag behind red
            r, gg, b = c.at(s), c.at(s - d), c.at(s - 2 * d)
            return torch.stack([r[0].float(), gg[1].float(), b[2].float()], 0)
        return c.at(s)

    E.shot(T_IN, T_OUT, CLIP, R, cam=cam, src=src, name='s06 samira 7% penta',
           hits=[T_TRIPLE, T_QUAD, T_PENTA, T_END])

    # =========================================== zoom-through in from s05 ===========================================
    # s05's white-out sits at screen (0.51, 0.49): rush into it, Samira's fight arrives zoomed-out on the downbeat
    E.transition(T_IN, T_ZOUT, T.zoom(0.51, 0.49, 2.4, 0.6))         # 50.70-51.06, cut at p = 0.5 = 50.88
    E.samples(T_IN, T_ZOUT, 8)
    E.sfx('whoosh', T_CUT, dur=0.45, direction='in', gain_db=-3)

    def cut_pop(P, t):
        e = 0.3 * env(t, T_CUT, 0.0, 0.05)
        if e > P['flash']:
            P['flash'] = e
            P['flash_color'] = WHITE
    E.post(T_CUT, T_CUT + 0.3, cut_pop)

    # =========================================== the hits ===========================================================
    # (impacts first: their posts set flash_color for their whole window; the strobes below are registered after)
    # Round 2 (HAZE): the white screen-blend flash lifted the blacks to grey for ~5 frames (51.42 and 53.72 read
    # milky). Triple/quadra now get a faint flash (0.11 / 0.15) and hit with impact()'s exposure kick, more RGB split
    # and a contrast kick instead. The penta (one of the video's 4 biggest hits) gets its own short flash after the
    # invert; the Nexus (not a top-4 hit) is capped at 0.6 and gone within 3 frames.
    impact(E, T_TRIPLE, 1.1, TX, TY, flash=0.1, chroma=20.0, end=SPAN[1])          # bar 18 16th 3
    impact(E, T_QUAD, 1.35, QX, QY, flash=0.11, chroma=19.0, end=SPAN[1])          # bar 19 16th 0
    # decay 0.15/0.16 keeps the big shakes' time constant (decay * 1.6) near the treatment's 0.25 s
    impact(E, T_PENTA, 2.2, PX, PY, punch=0.08, shake_amt=0.012, flash=0.0, chroma=12.0, decay=0.15,
           end=SPAN[1])                                                            # bar 20 (flash: penta_flash)
    impact(E, T_ROCK, 0.6, 0.5, 0.42, shock=False, flash=0.15, end=SPAN[1])        # "ROCK"
    impact(E, T_STAR, 0.5, 0.5, 0.42, shock=False, flash=0.15, end=SPAN[1])        # "STAR"
    impact(E, T_END, 2.4, NX, NY, punch=0.06, shake_amt=0.014, flash=0.0, chroma=14.0, decay=0.16,
           end=SPAN[1])                                                            # bar 21 (flash: whiteout)

    def kick(t0, amt, decay=0.08):
        """Contrast/saturation kick on a hit: the picture gets punchier, never greyer."""
        def f(P, t):
            e = amt * env(t, t0, 0.0, decay)
            P['contrast'] += 0.3 * e
            P['sat'] += 0.25 * e
        E.post(t0, t0 + decay * 6, f)
    kick(T_TRIPLE, 1.0)
    kick(T_QUAD, 1.1)

    def whiteout(P, t):
        # the Nexus flash: peak 0.6, time constant 0.035 s -> 0.41, 0.25, 0.16, 0.10 on the frames 59.333-59.383
        # (impact()'s exposure kick, +1.3 stops decaying in 0.05 s, does the rest of the blow-out without milk).
        # The title letters are drawn in ink while it burns.
        a = 0.6 * env(t, T_END, 0.0, 0.035)
        if a >= P['flash']:
            P['flash'] = a
            P['flash_color'] = WHITE
    E.post(T_END, T_END + 0.2, whiteout)

    def strobe(t0, amt, color, decay=0.045):
        # stage strobe: a short colour flash plus an exposure/contrast kick (bright, not milky)
        def f(P, t):
            e = env(t, t0, 0.0, decay)
            if amt * e > P['flash']:
                P['flash'] = amt * e
                P['flash_color'] = color
            P['exposure'] += 1.2 * amt * e
            P['contrast'] += 0.4 * amt * e
        E.post(t0, t0 + decay * 6, f)

    strobe(T_S6, 0.18, WHITE)            # bar 18 16th 6
    strobe(T_S9, 0.26, RED)              # bar 18 16th 9
    strobe(T_Q3, 0.15, WHITE)            # bar 19 16th 3
    strobe(T_CRIT, 0.30, RED, 0.06)      # bar 19 16th 12: HP 7%
    strobe(T_P3, 0.20, WHITE)            # bar 20 16th 3: last kick
    strobe(T_P4, 0.26, RED)              # bar 20 16th 4: last clap

    # =========================================== bar 18: TRIPLE -> run -> ladder ===================================
    E.top(T_TRIPLE, T_TRIPLE + 1.45, L.counter('TRIPLE KILL', T_TRIPLE, y=0.78, size=0.085, hold=1.2), z=10)
    beat_pulse(E, T_TRIPLE + 0.2, LADDER[0] - 0.02, amount=0.022)

    def run_lines(img, t, ctx):
        # speed lines that follow the footage's own speed (cruise 3.16x between the triple and the quadra)
        a = 0.32 * clamp((R.speed(t) - 1.6) / 1.2)
        if a <= 0.01:
            return img
        return fx.speed_lines(img, 0.5, 0.42, seed=int(t * 15), amount=a, density=130, inner=0.34, color=BONE,
                              thick=0.3)
    E.layer(T_TRIPLE + 0.2, LADDER[3], run_lines, z=4)

    def ladder(t):
        # 4-step zoom ladder on the snare roll (16ths 12-15), each step snapping in over 0.035 s, alternate rolls
        z, rot = 1.0, 0.0
        for j, x in enumerate(LADDER):
            k = smooth((t - x) / 0.035)
            z += 0.035 * k
            rot += (0.9 if j % 2 == 0 else -0.9) * k
        return dict(zoom=z, ax=QX, ay=QY, rot=rot)
    E.screen(LADDER[0], T_QUAD, ladder)

    def ladder_post(P, t):
        k = sum(smooth((t - x) / 0.035) for x in LADDER)
        P['chroma'] += 3.5 * k
        P['chroma_cx'], P['chroma_cy'] = QX, QY
    E.post(LADDER[0], T_QUAD, ladder_post)

    # =========================================== bar 19: QUADRA -> HP crash -> 7% ===================================
    E.top(T_QUAD, T_QUAD + 1.45, L.counter('QUADRA KILL', T_QUAD, y=0.78, size=0.085, hold=1.2), z=10)
    beat_pulse(E, T_QUAD + 0.35, T_CRIT - 0.02, amount=0.022)

    def low_hp(img, t, ctx):
        # in-game style low-HP screen edges: red vignette that thumps on each heartbeat kick
        base = 0.12 + 0.3 * smooth((t - T_HP0) / (T_PENTA - T_HP0))
        pulse = max(env(t, h, 0.02, 0.22) for h in HB)
        return fx.vignette(img, min(0.9, base + 0.45 * pulse), 0.62, 0.45, (0.55, 0.0, 0.04))
    E.layer(T_HP0 - 0.02, T_PENTA, low_hp, z=2)

    def hp_fn(img, t, ctx):
        if t < T_PENTA:
            # live readout: the number follows the clip time (HP_PTS), so it drains as fast as the footage runs
            u = t - T_HP0
            if u < 0:
                return img
            hp = hp_pct(R.s(t))
            a = clamp(u / 0.08)
            pulse = max(env(t, h, 0.0, 0.12) for h in HB)
            crit = eout((t - T_CRIT) / 0.1) if t >= T_CRIT else 0.0
            size = 0.034 * (1.0 + 0.6 * crit) * (1.0 + 0.1 * pulse)
            col = RED if hp < 12.0 else BONE
            img = ty.text(img, f'HP {int(round(hp))}%', 0.5, 0.86, size, 'mono', col, alpha=a, tracking=0.08,
                          stroke=0.002, stroke_color=INK, glow=0.25 + 0.75 * crit, glow_color=RED,
                          split=2.0 + 6.0 * pulse)
            bw = 0.16
            img = fx.rect(img, 0.5 - bw / 2, 0.905, 0.5 + bw / 2, 0.913, INK, 0.6 * a)
            return fx.rect(img, 0.5 - bw / 2, 0.905, 0.5 - bw / 2 + bw * hp / 100.0, 0.913, RED, a)
        # after the penta: the answer under PENTAKILL
        u = t - (T_PENTA + 0.2)
        if u < 0:
            return img
        k = eout(u / 0.1)
        al = k * clamp((T_PENTA + 1.5 - t) / 0.2)
        # y 0.872, scale 1.35 -> 1: caps 0.844-0.900 at the biggest (safe area ends at 0.92), under PENTAKILL (0.822)
        return ty.text(img, 'AT 7% HP', 0.5, 0.872, 0.042, 'anton', RED, scale=lerp(1.35, 1.0, k), alpha=al,
                       tracking=0.06, stroke=0.003, stroke_color=INK, glow=0.6, glow_color=RED)
    E.top(T_HP0, T_PENTA + 1.5, hp_fn, z=11)        # HP 54.75-56.54 (1.8 s), AT 7% HP 56.74-58.04 (1.3 s)

    for h, gdb in ((T_HP0, -4), (T_HP9, -3), (T_CRIT, -1)):
        E.sfx('heartbeat', h, gain_db=gdb, bpm=song.bpm)

    # 16th 12 -> the penta: near death. Red-only world, tunnel, muffled song, reverse cymbal into the drop
    def near_death(P, t):
        k = smooth((t - T_CRIT) / 0.06)
        P['pop'] = max(P['pop'], k)
        P['pop_hue'] = 0.0
        P['contrast'] = lerp(P['contrast'], 1.3, k)
        P['exposure'] -= 0.25 * k
        P['bloom'] = lerp(P['bloom'], 0.2, k)
        P['vignette'] = max(P['vignette'], 0.45 * k)
        P['grain'] = max(P['grain'], 0.05 * k)
        P['chroma'] += 9.0 * env(t, T_C13, 0.0, 0.07)          # 16th 13 kick
        P['chroma_cx'], P['chroma_cy'] = scr(t, *P_FIGHT_PRE)
    E.post(T_CRIT, T_PENTA, near_death)

    def tunnel(img, t, ctx):
        cx, cy = scr(t, *P_FIGHT_PRE)
        return fx.spotlight(img, cx, cy, r=0.2, soft=0.22, dim=0.55 * smooth((t - T_CRIT) / 0.12))
    E.layer(T_CRIT, T_PENTA, tunnel, z=3)

    E.music('lowpass', T_CRIT, T_PENTA, cutoff_from=6000.0, cutoff_to=450.0)
    E.sfx('reverse', T_PENTA, dur=0.7, gain_db=-4)

    # =========================================== bar 20: PENTAKILL ==================================================
    def invert(P, t):
        P['invert'] = 1.0          # 2-frame negative on the hit (56.55, 56.567); flash waits until it is over
        P['flash'] = 0.0
        P['exposure'] = 0.1        # the negative as in round 1 (impact()'s exposure kick starts after it)
    E.post(T_PENTA, T_PENTA + 2.0 / 60, invert)

    T_PF = T_PENTA + 2.0 / 60     # 56.573: the invert is over

    def penta_flash(P, t):
        # the biggest hit of the finale: white 0.85 right after the negative, time constant 0.03 s -> 0.61, 0.35,
        # 0.20, 0.12, 0.07 on the frames 56.583-56.650, so 56.69 (hit + 0.15) is clean again (round 1 was still
        # ~0.13 white there, plus bloom)
        a = 0.85 * env(t, T_PF, 0.0, 0.03)
        if a >= P['flash']:
            P['flash'] = a
            P['flash_color'] = WHITE
    E.post(T_PF, T_PF + 0.2, penta_flash)

    def penta_blur(P, t):
        P['zoom_blur'] = max(P['zoom_blur'], 0.25 * env(t, T_PENTA + 0.035, 0.0, 0.05))
        P['zoom_blur_cx'], P['zoom_blur_cy'] = PX, PY
        # a fast extra RGB split on top of impact()'s (26 px, slow): 44 px on the hit, ~10 px left at hit + 0.15
        P['chroma'] += 18.0 * env(t, T_PENTA, 0.0, 0.05)
    E.post(T_PENTA, T_PENTA + 0.35, penta_blur)

    def penta_rings(img, t, ctx):
        for t0, col, w0 in ((T_PENTA, BONE, 0.014), (T_PENTA + 0.07, GOLD, 0.010)):
            u = (t - t0) / 0.42
            if 0.0 <= u < 1.0:
                img = fx.ring(img, PX, PY, 0.04 + 0.62 * eout(u), w0 * (1 - u) + 0.002, col, 1.0 - u)
        return img
    E.layer(T_PENTA, T_PENTA + 0.5, penta_rings, z=6)

    def penta_lines(img, t, ctx):
        a = 0.45 * env(t, T_PENTA, 0.0, 0.12)
        return fx.speed_lines(img, PX, PY, seed=int(t * 20), amount=a, density=140, inner=0.18, color=BONE)
    E.layer(T_PENTA, T_PENTA + 0.45, penta_lines, z=4)

    look2(E, T_PENTA, T_ACAP, HOT_CLEAN, fade_out=0.35)
    # light leak (screen blend) kept faint: at 0.26 it was a warm veil over the whole afterglow
    E.layer(T_STOP, T_ACAP, lambda img, t, ctx: fx.light_leak(img, t, seed=6, amount=0.11 * echo_w(t) + 0.03),
            z=1)
    E.screen(T_P3, T_P4 + 0.4, lambda t: dict(zoom=1.0 + 0.02 * env(t, T_P3, 0.0, 0.08)
                                             + 0.02 * env(t, T_P4, 0.0, 0.08), ax=PX, ay=PY))
    # text safe area (y <= 0.92): cap height 0.12 x the slam's first scale must fit, so y 0.76 and from_scale 2.2
    # -> caps 0.628-0.892 at the biggest, 0.698-0.822 at rest; width 0.29 at rest, 0.64 at the biggest (x 0.18-0.82)
    E.top(T_PENTA + 0.04, T_PENTA + 1.5,
          L.slam('PENTAKILL', T_PENTA + 0.04, y=0.76, size=0.12, color=GOLD, hold=1.11, out=0.25, from_scale=2.2,
                 split=14.0, glow=0.8, glow_color=(1.0, 0.5, 0.1), stroke=0.003, stroke_color=INK), z=12)  # 1.46 s
    E.sfx('boom', T_PENTA, dur=2.0, gain_db=-2)
    E.sfx('subdrop', T_PENTA, dur=1.2, gain_db=-4)

    # =========================================== the a cappella: breathe, then ROCK - STAR ==========================
    def breath(P, t):
        k = smooth((t - T_ACAP) / 0.3)
        P['sat'] = lerp(P['sat'], 0.55, k)
        P['exposure'] -= 0.12 * k
        P['bloom'] = lerp(P['bloom'], 0.25, k)
        P['temp'] -= 0.25 * k
    E.post(T_ACAP, T_ROCK, breath)

    def bars(P, t):
        P['letterbox'] = max(P['letterbox'], 0.10 * eout((t - T_ACAP) / 0.35))
    E.post(T_ACAP, T_OUT, bars)
    E.sfx('whoosh', T_ACAP + 0.02, dur=0.7, direction='out', bright=0.5, gain_db=-12)

    look2(E, T_ROCK, T_END, HOT_CLEAN, amount=0.8)

    def rush(P, t):
        u = (t - T_STAR) / (T_END - T_STAR)
        P['chroma'] += 12.0 * ein(u)
        P['chroma_cx'], P['chroma_cy'] = scr(t, *P_BOOM)
    E.post(T_STAR, T_END, rush)

    def rush_lines(img, t, ctx):
        u = (t - T_STAR) / (T_END - T_STAR)
        cx, cy = scr(t, *P_BOOM)
        return fx.speed_lines(img, cx, cy, seed=int(t * 20), amount=0.45 * ein(u), density=150, inner=0.22,
                              color=BONE)
    E.layer(T_STAR, T_END, rush_lines, z=4)
    E.sfx('reverse', T_END, dur=0.8, gain_db=-4)
    E.sfx('whoosh', T_END, dur=0.5, direction='in', gain_db=-6)

    # =========================================== bar 21: the Nexus ==================================================
    E.sfx('boom', T_END, dur=3.0, gain_db=0)
    E.sfx('subdrop', T_END, dur=1.8, gain_db=-2)
    # round 1 used the 'hot' look here: its bloom on the clip's own pink-white blast kept 59.33-59.50 milky.
    # NEXUS_GRADE: hard contrast, little bloom; its exposure dip is additive (below) so impact()'s exposure kick
    # (+1.3 stops, gone in ~0.1 s) still blows the first frames out
    look2(E, T_END, T_END + 0.5, NEXUS_GRADE, fade_out=0.25)

    def nexus_dim(P, t):
        P['exposure'] -= 0.15 * smooth((T_END + 0.5 - t) / 0.25)
    E.post(T_END, T_END + 0.5, nexus_dim)

    def nexus_rings(img, t, ctx):
        for t0, col, w0 in ((T_END, WHITE, 0.016), (T_END + 0.08, RED, 0.012)):
            u = (t - t0) / 0.55
            if 0.0 <= u < 1.0:
                img = fx.ring(img, NX, NY, 0.05 + 0.85 * eout(u), w0 * (1 - u) + 0.002, col, 1.0 - u)
        return img
    E.layer(T_END, T_END + 0.65, nexus_rings, z=6)

    def ripple(img, t, ctx):
        a = 0.005 * math.exp(-(t - T_END) / 0.35)
        return fx.ripple(img, NX, NY, t - T_END, amp=a, freq=40.0, speed=3.0, decay=2.0)
    E.layer(T_END, T_FREEZE, ripple, z=5)

    # colour drains to red: red-only, then a red/ink duotone (the 'paranoia' callback) as the end card settles
    def drain(P, t):
        k = smooth((t - (T_END + 0.23)) / 0.75)
        P['pop'] = max(P['pop'], k)
        P['pop_hue'] = 0.0
        P['duotone'] = max(P['duotone'], 0.72 * k)
        P['duo_dark'], P['duo_light'] = INK, RED
        P['contrast'] *= 1.0 + 0.15 * k
        P['bloom'] = lerp(P['bloom'], 0.3, k)
    E.post(T_END + 0.23, T_OUT, drain)

    # =========================================== the end card =======================================================
    E.sfx('glitch', T_END + 0.06, dur=0.4, gain_db=-8)                      # ROCKSTAR decodes into PARANOIA
    E.sfx('shutter', T_FREEZE, gain_db=-2)                                  # freeze-frame
    LABEL = 'SUBJECT: ALIVE'
    for j, ch in enumerate(LABEL):
        if ch.strip():
            E.sfx('tick', T_TYPE + j / 24.0, gain_db=-14)
    E.sfx('heartbeat', HEARTS[0], gain_db=-5, bpm=song.bpm)
    E.sfx('heartbeat', HEARTS[1], gain_db=-8, bpm=song.bpm)

    def surveil(P, t):
        k = smooth((t - T_FREEZE) / 0.1)
        fo = 1.0 - smooth((t - T_FADE) / (T_OUT - T_FADE))
        P['scanlines'] = max(P['scanlines'], 0.14 * k * fo)
        P['grain'] = lerp(P['grain'], 0.06, k) * fo
        P['vignette'] = max(P['vignette'], 0.5 * k)
        P['flash'] = max(P['flash'], 0.35 * env(t, T_FREEZE, 0.0, 0.03))  # shutter blink: 0.22, 0.13, 0.07
    E.post(T_FREEZE, T_OUT, surveil)

    def rec_hud(img, t, ctx):
        # = L.rec('CAM 06'), moved inside the text safe area (x 0.05-0.95, y 0.06-0.92): the engine's puts the
        # CAM label's right edge at 0.955, 'REC' caps from y 0.055 and the timecode at y 0.93
        if int(t * 2) % 2 == 0:
            img = fx.disc(img, 0.062, 0.085, 0.012, (1.0, 0.2, 0.2), 0.95)
        img = ty.text(img, 'REC', 0.08, 0.085, 0.03, 'mono', WHITE, anchor=(0.0, 0.5), alpha=0.9, tracking=0.1)
        img = ty.text(img, 'CAM 06', 0.94, 0.085, 0.026, 'mono', WHITE, anchor=(1.0, 0.5), alpha=0.85, tracking=0.1)
        tc = f'{int(t // 3600):02d}:{int(t // 60) % 60:02d}:{int(t) % 60:02d}:{int((t % 1) * 60):02d}'
        return ty.text(img, tc, 0.94, 0.895, 0.026, 'mono', WHITE, anchor=(1.0, 0.5), alpha=0.85)
    E.top(T_FREEZE, T_OUT, rec_hud, z=20)

    # --- ROCK / STAR slams, then the decode into PARANOIA (one 8-slot word, layout like s01's ty.letters title) ---
    TA = [T_ROCK + 0.035 * i for i in range(4)] + [T_STAR + 0.035 * i for i in range(4)]
    SC = [T_END + 0.015 * i for i in range(8)]              # slot i starts scrambling (the blast hits it)
    # slot i locks into PARANOIA: 59.41 .. 59.62 (round 1 ran to 59.72; the lead wants it resolved by ~59.7, so the
    # mid-decode garble is now 0.3 s long and the word is whole from the 59.633 frame on)
    LK = [T_END + 0.09 + 0.03 * i for i in range(8)]
    _lay = {}

    def layout(word, W, H):
        key = (word, W, H)
        if key not in _lay:
            ws = [ty.width(ch, TITLE_SIZE, 'anton', 0.0, None, H, W) for ch in word]
            track = ty.width('II', TITLE_SIZE, 'anton', TITLE_TRACK, None, H, W) - 2 * ty.width(
                'I', TITLE_SIZE, 'anton', 0.0, None, H, W)
            tot = sum(ws) + track * (len(word) - 1)
            x, xs = 0.5 - tot / 2, []
            for w in ws:
                xs.append(x + w / 2)
                x += w + track
            _lay[key] = xs
        return _lay[key]

    def title(img, t, ctx):
        W, H = ctx['W'], ctx['H']
        xa, xb = layout(A_WORD, W, H), layout(B_WORD, W, H)
        hit = env(t, T_END, 0.0, 0.14)
        inv = env(t, T_END, 0.0, 0.05)                      # ink letters while the (now short) white-out burns
        hb = max(env(t, h, 0.0, 0.2) for h in HEARTS)
        gl = max(env(t, h, 0.0, 0.05) for h in GLITCHES)
        fr = int(t * 30)
        breathe = 1.0 + 0.03 * smooth((t - LK[7]) / (T_OUT - LK[7]))
        for i in range(8):
            if t < TA[i]:
                continue
            k = eout((t - TA[i]) / 0.09)
            ox, oy, r = shake(t, 0.012 * hit, 28.0, 40 + i)
            dy = -(1.0 - k) * 0.04
            if t < SC[i]:                                    # ROCKSTAR, slammed in on the sung syllables
                ch, x, col = A_WORD[i], xa[i], BONE
                sc = lerp(2.2, 1.0, k)
                spl, glow, gcol = 4.0 + 10.0 * (1.0 - k) + 14.0 * hit, 0.6, RED
            elif t < LK[i]:                                  # scrambling (deterministic glyph per slot and 1/40 s)
                n = int(t * 40)
                ch = GLYPHS[int(hashf(i, n) * len(GLYPHS)) % len(GLYPHS)]
                x = lerp(xa[i], xb[i], smooth((t - SC[i]) / (LK[i] - SC[i])))
                col = RED if hashf(i, n, 7) < 0.5 else CYAN
                sc, spl, glow, gcol = 1.0, 10.0, 0.4, col
            else:                                            # PARANOIA, locked
                ch, x = B_WORD[i], xb[i]
                pop = env(t, LK[i], 0.0, 0.07)
                col = BONE
                sc = (1.0 + 0.22 * pop + 0.03 * hb) * breathe
                spl, glow, gcol = 5.0 + 12.0 * pop + 22.0 * gl, 0.5 + 0.5 * hb, RED
                if gl > 0.2 and hashf(i, fr, 4) > 0.5:
                    ox += (hashf(i, fr, 3) - 0.5) * 0.03 * gl
            col = mix3(col, INK, inv)
            img = ty.text(img, ch, x + ox, TITLE_Y + oy + dy, TITLE_SIZE, 'anton', col, scale=sc, rot=r, alpha=k,
                          split=spl, glow=glow * (1.0 - inv), glow_color=gcol)
        return img
    E.top(T_ROCK, T_OUT, title, z=30)

    # --- the surveillance callback: brackets lock onto the frozen Samira, 'SUBJECT: ALIVE' types on above them ---
    def subject(img, t, ctx):
        u = (t - T_FREEZE) / 0.32
        if u < 0:
            return img
        k = eout(u)
        x0, y0 = scr(t, SAMIRA_BOX[0], SAMIRA_BOX[1])
        x1, y1 = scr(t, SAMIRA_BOX[2], SAMIRA_BOX[3])
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        s = lerp(2.0, 1.0, k)
        hw, hh = (x1 - x0) / 2 * s, (y1 - y0) / 2 * s
        al = clamp(u * 3)
        if k < 0.95 and int(t * 20) % 2:
            al *= 0.6
        img = fx.brackets(img, cx - hw, cy - hh, cx + hw, cy + hh, 0.25, 0.0035, BONE, al)
        img = fx.crosshair(img, cx, cy, 0.03, 0.01, 0.0025, BONE, al * 0.8, rot=(1.0 - k) * 90)
        n = int((t - T_TYPE) * 24) if t >= T_TYPE else 0
        if n > 0:
            txt = LABEL[:min(n, len(LABEL))]
            if int(t * 4) % 2 == 0:
                txt += '_'
            img = ty.text(img, txt, cx - hw, cy - hh - 0.03, 0.024, 'mono', BONE, anchor=(0.0, 0.5), tracking=0.12)
        return img
    E.top(T_FREEZE, T_OUT, subject, z=25)

    # --- fade to black by 62.50 ---
    def fade(img, t, ctx):
        return img * (1.0 - smooth((t - T_FADE) / (T_OUT - T_FADE - 1.0 / 60)))
    E.top(T_FADE, T_OUT, fade, z=100)
