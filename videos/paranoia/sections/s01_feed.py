"""s01 FEED: the CCTV intro. t 0.00-8.54, bars 0-2, the quiet bridge (no drums).

"Hoping that the Eiffel falls, of course / You don't understand the life we chose / My life's a pool, like / Need my
silence" -- we are a security system watching the player.

Beat map (video s; 85.71 BPM, bar 0 = 0.00, bar 1 = 2.86, bar 2 = 5.72, bar 3 = 8.54; 16th = 0.17875 in bars 0-1,
0.175 in bar 2). No drums until 8.51, so the hits sit on the bar grid, the vocal onsets and the instrumental accents
('other' stem peaks at 1.75 and 7.15):

  0.00          black -> static -> CRT power-on (0.10-0.50), music low-pass opens 600 Hz -> 18 kHz
  0.42-1.86     CAM 01: Kha'Zix crouched in the dark river in stealth, slow-mo 0.45x. Cyan brackets 'MOTION' hunt the
                shimmer; heartbeat lub-dub + tiny zoom pulse on beats 1 (0.715) and 2 (1.43)
  1.79          bar 0 16th 10 (1.7875) = vocal onset of "falls" (1.80): Kha'Zix DECLOAKS under a gold beam
                (clip 46.259, between frame 46.250 = shimmer and 46.267 = revealed). RGB time-split ghost, warm
                flash, zap, red brackets snap on, the virtual camera whips after him
  2.058         the player's own camera cut (clip 46.467) hidden under a glitch tear
  2.86          bar 1 16th 0: the KILL. White-pink explosion, clip 47.183 (pinned frame), +196 gold.
                Impact + boom; the title PARANOIA glitches in out of the flash (ink-on-white, then white)
  3.575         bar 1 16th 4: FREEZE-FRAME (clip 47.29) + shutter. Brackets 'ID: ART3M1S' lock on, cyan scan sweeps
  4.29, 5.005   bar 1 16ths 8 and 12: digital 'enhance' snaps (zoom step + pixelate -> sharp + tick), title glitches
  5.72          bar 2 16th 0: glitch cut to CAM 02 (window 5.60-5.84). Title holds to 5.95 (3.09 s), dies by 6.32
  5.72-8.54     CAM 02: HEARTSTEEL Kayn lurking in the bush (0.85x), OneTrickTony walks in and charges
                (clip 33.8-34.05 = t 6.29-6.55); brackets 'SUBJECT: ART3M1S' (label from 6.42 = bar 2 16th 4)
  7.12          bar 2 16th 8 (strongest instrumental accent, 'other' 1.0 at 7.15): AMBUSH. Kayn bursts out of the
                bush, first damage numbers at clip 34.34 (pinned); dash-out 34.25 starts on "pool" (6.89)
  8.24-8.54     last 0.3 s: glitch tear ramps up + red 'LIVE' flicker, reverse cymbal into the drums
  8.54          seam: Kayn clip at 35.85 moving 0.6x (agreed with s02)

Clip positions below are (u, v) fractions of the 2560x1440 source, read off 1/60 s frame grabs.
"""
import bisect
import math

from engine.api import *

SPAN = (0.0, 8.54)

KZ = 'League-of-Legends__2026-04-06__23-04-42.mp4'   # Kha'Zix, Summoner's Rift river at night  (CAM 01)
KY = 'League-of-Legends__2026-02-19__23-12-48.mp4'   # HEARTSTEEL Kayn, ARAM bridge              (CAM 02 -> s02)

# --- palette (TREATMENT "Look") ---
RED = (1.0, 0.16, 0.22)
CYAN = (0.2, 0.95, 1.0)
BONE = (0.96, 0.94, 0.9)
INK = (0.02, 0.02, 0.04)

# --- pinned clip times ---
KZ_IN = 45.45        # Kha'Zix crouched at (0.535, 0.37) on his red disc; prey SpreadDemThighs at (0.23, 0.64)
KZ_REVEAL = 46.259   # 46.250 last stealth-shimmer frame, 46.267 first frame revealed at (0.43, 0.51) under a gold beam
KZ_JUMP = 46.467     # the recorded camera jumps between frame 46.450 and 46.483
KZ_BOOM = 47.183     # the kill: big white-pink explosion at (0.30, 0.52), enemy HP bar black, +196 gold
KZ_FREEZE = 47.29    # Kha'Zix at (0.37, 0.42), '+196' / '72' floating at (0.33, 0.51)
KY_IN = 33.25        # Kayn hidden in the bush at (0.46, 0.47); OneTrickTony walking in at (0.70, 0.42)
KY_HIT = 34.34       # Kayn's burst on OneTrickTony: first big damage numbers '46 / 204' at (0.48, 0.47)
KY_SEAM = 35.85      # agreed with s02: t 8.54 shows clip 35.85 moving at 0.6x
KY_SEAM_V = 0.6

TITLE_Y, TITLE_SIZE = 0.56, 0.2      # Anton cap height 0.2 H -> 'PARANOIA' is 0.51 W wide (x 0.245-0.755)

# where Kha'Zix is (clip time -> clip u, v). Two jumps: the decloak teleport and the recorded camera cut.
# The decloak jump sits inside 46.2585-46.2595 (straddling KZ_REVEAL 46.259) so the brackets don't hop a frame early:
# frame t 1.783 samples clip 46.2573 (old spot), frame 1.800 samples 46.264 (new spot).
KZ_TRACK = [(45.45, 0.535, 0.37), (45.80, 0.53, 0.35), (46.250, 0.535, 0.36), (46.2585, 0.535, 0.36),
            (46.2595, 0.43, 0.51), (46.35, 0.42, 0.50), (46.40, 0.41, 0.46), (46.450, 0.39, 0.44), (46.466, 0.39, 0.44),
            (46.475, 0.55, 0.28), (46.60, 0.55, 0.19), (46.75, 0.49, 0.18), (46.90, 0.43, 0.31), (47.00, 0.40, 0.38),
            (47.08, 0.40, 0.44), (47.18, 0.37, 0.42), (47.29, 0.37, 0.42)]
KY_TRACK = [(33.20, 0.46, 0.47), (33.60, 0.45, 0.48), (33.85, 0.43, 0.51), (34.22, 0.43, 0.50), (34.34, 0.47, 0.48),
            (34.55, 0.46, 0.52), (34.70, 0.42, 0.55), (35.00, 0.39, 0.57), (35.30, 0.38, 0.58), (35.60, 0.37, 0.61),
            (35.85, 0.38, 0.58)]
TONY_TRACK = [(33.20, 0.70, 0.43), (33.60, 0.66, 0.46), (33.85, 0.55, 0.48), (34.22, 0.53, 0.49)]


# --- helpers ---------------------------------------------------------------------------------------------------
def mix3(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def keyed(keys):
    """Smoothstep path through (t, a, b, c, ...) keys -> fn(t) -> (a, b, c, ...)."""
    keys = sorted(keys)
    ts = [k[0] for k in keys]

    def f(t):
        j = bisect.bisect_right(ts, t)
        if j == 0:
            return tuple(keys[0][1:])
        if j >= len(keys):
            return tuple(keys[-1][1:])
        a, b = keys[j - 1], keys[j]
        k = smooth((t - a[0]) / max(1e-6, b[0] - a[0]))
        return tuple(x + (y - x) * k for x, y in zip(a[1:], b[1:]))
    return f


def fcam(zoom, cx, cy):
    """A Cam that never looks past the clip's edge (zoom >= 1, centre clamped to the visible window)."""
    zoom = max(1.0, zoom)
    h = 0.5 / zoom
    return Cam(zoom=zoom, cx=clamp(cx, h, 1 - h), cy=clamp(cy, h, 1 - h))


def to_screen(cam, u, v):
    """Clip point (u, v) -> screen point under `cam` (no rotation/offset used in this section)."""
    return 0.5 + (u - cam.cx) * cam.zoom, 0.5 + (v - cam.cy) * cam.zoom


def solve_t(remap, s_target, t0, t1):
    """Video time at which a rising remap reaches clip time s_target (bisection)."""
    for _ in range(50):
        m = (t0 + t1) / 2
        if remap.s(m) < s_target:
            t0 = m
        else:
            t1 = m
    return (t0 + t1) / 2


def win(t, t0, t1):
    """0 -> 1 -> 0 sine bump over [t0, t1]."""
    if t <= t0 or t >= t1:
        return 0.0
    return math.sin(math.pi * (t - t0) / (t1 - t0))


def clock(h, m, s):
    return f'{int(h) % 24:02d}:{int(m) % 60:02d}:{int(s) % 60:02d}'


# --- the section ---------------------------------------------------------------------------------------------------
def build(E):
    bar0, b1, b2 = song.bar(0), song.bar(1), song.bar(2)                   # 0.00 2.86 5.72 (bar 3 = 8.54)
    beat = [song.beat(i) for i in range(13)]                               # 0.715 1.43 2.145 2.86 3.575 4.29 ...
    b5, b6, b7 = beat[5], beat[6], beat[7]       # 3.575 4.29 5.005 = bar 1 16ths 4, 8, 12
    b9, b10 = beat[9], beat[10]                  # 6.42 7.12 = bar 2 16ths 4, 8
    t_reveal = bar0 + 10 * (b1 - bar0) / 16      # 1.7875 = bar 0 16th 10; "falls" sung at 1.80
    t_boom = b1                                  # 2.86 = bar 1 16th 0
    t_ambush = b10                               # 7.12 = bar 2 16th 8
    t_end = SPAN[1]                              # 8.54 (= bar 3, the drums enter)
    T1_END = 5.84                                # CAM 01 runs past the bar-2 cut for the glitch transition
    T2_IN = 5.60                                 # CAM 02 starts inside the transition window 5.60-5.84

    kz_track = follow(KZ_TRACK)
    ky_track = follow(KY_TRACK)
    tony_track = follow(TONY_TRACK)

    # the grade goes first: posts run in the order they are added, and the look SETS exposure/sat/bloom, so the
    # impact() punches and my grade() below must come after it
    look(E, 0.0, t_end, 'surveil')

    # ============================== SHOT 1: CAM 01, Kha'Zix (0.00 -> 5.84) ==================================
    # Remap keys (checked with engine.remap; cruise speeds 0.45x / 1.15x / 0.30x, no warnings):
    #   t 0.00   clip 45.45   0.5x     ominous slow-mo through the stealth crouch (cruise 0.45x)
    #   t 1.79   clip 46.259  0.4x     decloak on "falls" (bar 0 16th 10)
    #   t 2.058  clip 46.467           recorded camera cut, hidden under a tear (computed below)
    #   t 2.86   clip 47.183  0.3x     the kill explosion on bar 1 (cruise 1.15x between: leap 46.9 = t 2.44,
    #                                  Q burst 47.083 = t 2.63)
    #   t 3.575  clip 47.29   0x       brakes smoothly 0.3x -> 0 over one beat: freeze-frame on bar 1 16th 4
    #   t 5.84   clip 47.29   0x       held to the end of the transition
    r1 = Remap([K(0.0, KZ_IN, 0.5, (0.0, 0.0)),
                K(t_reveal, KZ_REVEAL, 0.4, (0.3, 0.3)),
                K(t_boom, KZ_BOOM, 0.3, (0.25, 0.45)),
                K(b5, KZ_FREEZE, 0.0, (0.0, 1.0)),
                K(T1_END, KZ_FREEZE, 0.0, (0.0, 0.0))])
    t_jump = solve_t(r1, KZ_JUMP, t_reveal, t_boom)    # ~2.058

    # virtual camera. Before the recorded cut: slow push onto the stealth shimmer, then whip after the decloak.
    pre = keyed([(0.0, 1.06, 0.50, 0.46),
                 (t_reveal, 1.24, 0.535, 0.42),          # shimmer (0.535, 0.36) sits at screen (0.50, 0.44)
                 (t_reveal + 0.26, 1.20, 0.42, 0.47)])   # follow him to (0.39, 0.44) -> screen (0.46, 0.46)
    # after the cut: frame Kha'Zix (0.55, 0.28) and his prey (0.36, 0.42), drift onto the kill point, then reframe
    # during the afterglow so the frozen subject sits top-left (0.25, 0.28) and the title owns the centre.
    post = keyed([(t_jump, 1.12, 0.46, 0.446),
                  (2.50, 1.14, 0.45, 0.45),
                  (t_boom, 1.18, 0.43, 0.47),            # explosion (0.30, 0.52) at screen (0.35, 0.56)
                  (b5, 1.25, 0.57, 0.596)])

    def freeze_zoom(t):
        # two digital 'enhance' snaps (bar 1 16ths 8 and 12) plus a slow creep
        return 1.25 + 0.06 * eout((t - b6) / 0.1) + 0.06 * eout((t - b7) / 0.1) + 0.012 * (t - b5)

    def cam1(t):
        if t < t_jump:
            z, x, y = pre(t)
        elif t < b5:
            z, x, y = post(t)
        else:
            z = freeze_zoom(t)                           # keep Kha'Zix (0.37, 0.42) pinned at screen (0.25, 0.28)
            x, y = 0.37 + 0.25 / z, 0.42 + 0.22 / z
        return fcam(z, x, y)

    def kz_screen(t):
        return to_screen(cam1(t), *kz_track(r1.s(t)))

    def src1(t, ctx, shot):
        """RGB time split for 0.25 s after the decloak: red shows him revealed, green/blue lag in the shimmer."""
        c = shot.clip
        s = shot.s(t)
        d = 0.05 * win(t, t_reveal - 0.02, t_reveal + 0.24)
        if d < 0.004:
            return c.at(s, shot.interp)
        import torch
        a = c.at(s, shot.interp)
        g = c.at(s - d, shot.interp)
        b = c.at(s - 2 * d, shot.interp)
        return torch.cat([a[0:1], g[1:2], b[2:3]], 0)

    def fx1(img, t, ctx):
        img = fx.chroma(img, 2.5)                        # cheap CCTV lens fringe
        for bt in (b6, b7):                              # 'enhance': pixel blocks resolve to sharp in 0.16 s
            u = (t - bt) / 0.16                          # (sharp again by 0.15 s after the beat)
            if 0.0 <= u < 1.0:
                img = fx.pixelate(img, 1.0 + 22.0 * (1.0 - smooth(u)) * ctx['H'] / 1080.0)
        return img

    E.shot(0.0, T1_END, KZ, r1, cam=cam1, fx=[fx1], src=src1, name='s01 CAM01 khazix',
           hits=[t_reveal, t_boom])

    # ============================== SHOT 2: CAM 02, Kayn (5.60 -> 8.54) =====================================
    # Remap keys:
    #   t 5.60   clip 33.25  0.7x     Kayn hidden in the bush (cruise 0.85x); OneTrickTony walks in and charges
    #                                 (clip 33.80-34.05 = t 6.29-6.55)
    #   t 7.12   clip 34.34  0.35x    AMBUSH on bar 2 16th 8: first damage numbers; the dash-out (34.25) lands
    #                                 on "pool" at t 6.89
    #   t 8.54   clip 35.85  0.6x     the seam (cruise 1.32x through the blue-swirl fight, easing to 0.6x)
    r2 = Remap([K(T2_IN, KY_IN, 0.7, (0.0, 0.0)),
                K(t_ambush, KY_HIT, 0.35, (0.3, 0.45)),
                K(t_end, KY_SEAM, KY_SEAM_V, (0.3, 0.3))])

    cam2_path = keyed([(T2_IN, 1.08, 0.52, 0.47),
                       (7.00, 1.16, 0.49, 0.49),
                       (7.30, 1.17, 0.47, 0.50),
                       (t_end, 1.20, 0.43, 0.55)])       # at 8.54 the fight (0.38, 0.58) sits at screen (0.44, 0.54)

    def cam2(t):
        return fcam(*cam2_path(t))

    def ky_screen(t):
        return to_screen(cam2(t), *ky_track(r2.s(t)))

    E.shot(T2_IN, t_end, KY, r2, cam=cam2, fx=[lambda img, t, ctx: fx.chroma(img, 2.5)],
           name='s01 CAM02 kayn', hits=[t_ambush])

    # glitch cut on bar 2 (5.72 = middle of the window)
    E.transition(T2_IN, T1_END, T.glitch(30.0))

    # ============================== hits ==========================================================================
    # Haze rules: flash peaks stay small (decloak 0.24, ambush 0.23) and lean on impact()'s exposure kick + chroma.
    rx, ry = kz_screen(t_reveal + 0.03)                  # revealed Kha'Zix ~ screen (0.37, 0.61)
    impact(E, t_reveal, 0.6, rx, ry, punch=0.06, shake_amt=0.008, flash=0.4, chroma=12.0, color=(1.0, 0.92, 0.75),
           end=SPAN[1])
    # the title kill (one of the video's allowed big flashes): impact() keeps the punch, shake, chroma and exposure
    # kick, but its flash is off; boom_flash() below gives a hard 2-frame white-pink burst that is gone by ~2.95
    ex, ey = to_screen(cam1(t_boom), 0.30, 0.52)         # explosion ~ screen (0.35, 0.56)
    impact(E, t_boom, 1.4, ex, ey, punch=0.1, shake_amt=0.014, flash=0.0, chroma=18.0, color=(1.0, 0.86, 0.95),
           decay=0.16, end=SPAN[1])
    ax, ay = to_screen(cam2(t_ambush), 0.48, 0.47)       # Kayn's burst ~ screen (0.49, 0.48)
    impact(E, t_ambush, 0.75, ax, ay, punch=0.07, shake_amt=0.01, flash=0.3, chroma=12.0, color=(0.9, 0.8, 1.0),
           end=SPAN[1])

    def boom_flash(t):
        """Kill flash: 0.95 for 0.03 s (frames 2.867, 2.883), then a 0.03 s fall. Frame values with the 0.5 shutter:
        2.900 ~0.68, 2.917 ~0.39, 2.933 ~0.23, 2.950 ~0.13, 3.000 ~0.02 -> clean image 0.15 s after the hit."""
        u = t - t_boom
        if u < 0.0 or u > 0.25:
            return 0.0
        return 0.95 if u < 0.03 else 0.95 * math.exp(-(u - 0.03) / 0.03)

    # heartbeat pulses while we hunt the shimmer: lub on beats 1 and 2, dub an eighth note (0.35 s) later
    hb_beats = (beat[1], beat[2])
    dub = 30.0 / song.bpm

    def hb_screen(t):
        z = 0.0
        for bt in hb_beats:
            z += 0.016 * env(t, bt, 0.0, 0.09) + 0.009 * env(t, bt + dub, 0.0, 0.09)
        return dict(zoom=1.0 + z)
    E.screen(0.6, 2.2, hb_screen)

    # ============================== grade (after look + impacts) ====================================================
    def grade(P, t):
        # boot: the picture arrives torn
        if t < 0.6:
            P['glitch'] = max(P['glitch'], 0.55 * (1.0 - smooth((t - 0.15) / 0.45)))
            P['glitch_rate'] = 24.0
        # decloak: the gold beam's colour bleeds through the grey feed
        e = env(t, t_reveal, 0.0, 0.3)
        P['sat'] = lerp(P['sat'], 1.0, 0.7 * e)
        # the recorded camera cut, hidden under a tear
        g = win(t, t_jump - 0.07, t_jump + 0.09)
        if g > 0:
            P['glitch'] = max(P['glitch'], 0.9 * g)
            P['glitch_rate'] = 30.0
            P['chroma'] += 10.0 * g
        # the kill: a 2-frame white-pink burst (boom_flash), then pink bleeds through with a short glow
        f = boom_flash(t)
        if f > 0.0 and f >= P['flash']:
            P['flash'], P['flash_color'] = f, (1.0, 0.86, 0.95)
        e = env(t, t_boom, 0.0, 0.45)
        P['sat'] = lerp(P['sat'], 1.3, e)
        P['bloom'] += 0.45 * env(t, t_boom, 0.0, 0.3)
        # freeze-frame: shutter flash (small, quick, plus an exposure tick), darker and colder while the title holds;
        # gone after the bar-2 cut
        if b5 <= t < T1_END:
            k = smooth((t - b5) / 0.3) * (1.0 - smooth((t - T2_IN) / (T1_END - T2_IN)))
            P['exposure'] -= 0.12 * k
            P['exposure'] += 0.3 * env(t, b5, 0.0, 0.04)
            P['sat'] *= 1.0 - 0.3 * k
            P['vignette'] += 0.12 * k
            P['flash'] = max(P['flash'], 0.45 * env(t, b5, 0.0, 0.05))
            P['flash_color'] = (1.0, 1.0, 1.0)
            P['chroma'] += 8.0 * (env(t, b6, 0.0, 0.12) + env(t, b7, 0.0, 0.12))
        # the seam: the feed starts tearing as the drums come in
        if t >= t_end - 0.30:
            k = clamp((t - (t_end - 0.30)) / 0.30)
            P['glitch'] = max(P['glitch'], 0.15 + 0.6 * k)
            P['glitch_rate'] = 30.0
            P['chroma'] += 8.0 * k
    E.post(0.0, t_end, grade)

    # ============================== UI (crisp, after post) ==========================================================
    # CRT power-on: black -> static -> a bright line -> the line opens into the picture
    def boot(img, t, ctx):
        seed = ctx['frame'] * 7 + 11
        if t < 0.10:
            img = fx.rect(img, 0.0, 0.0, 1.0, 1.0, INK, 1.0)
            return fx.grain(img, seed, 0.30 * smooth(t / 0.10))
        if t < 0.20:
            k = eout((t - 0.10) / 0.10)
            img = fx.rect(img, 0.0, 0.0, 1.0, 1.0, INK, 1.0)
            img = fx.grain(img, seed, 0.30)
            w = 0.02 + 0.98 * k
            return fx.line(img, 0.5 - w / 2, 0.5, 0.5 + w / 2, 0.5, 0.004, (0.85, 0.97, 1.0), 1.0)
        k = eout((t - 0.20) / 0.30)
        h = 0.004 + 0.996 * k
        img = fx.flash(img, 0.85 * (1.0 - k), (0.85, 0.95, 1.0))
        img = fx.rect(img, 0.0, 0.0, 1.0, 0.5 - h / 2, INK, 1.0)
        img = fx.rect(img, 0.0, 0.5 + h / 2, 1.0, 1.0, INK, 1.0)
        return fx.grain(img, seed, 0.30 * (1.0 - k) + 0.02)
    E.top(0.0, 0.5, boot, z=100)

    # REC HUD (shared L.rec so it continues into s02's CAM 02 HUD), plus a real date/time stamp of the recording
    E.top(0.48, b2, L.rec('CAM 01'), z=0)
    E.top(b2, t_end, L.rec('CAM 02'), z=0)

    def stamp(date, hh, mm, ss, remap):
        def f(img, t, ctx):
            tot = hh * 3600 + mm * 60 + ss + remap.s(t)          # the clock runs at clip speed: it stops on the freeze
            txt = f'{date}  {clock(tot // 3600, tot // 60, tot)}'
            return ty.text(img, txt, 0.055, 0.115, 0.02, 'mono', BONE, anchor=(0.0, 0.5), alpha=0.8, tracking=0.06)
        return f
    E.top(0.48, b2, stamp('2026-04-06', 23, 4, 42, r1), z=1)     # Kha'Zix game: recorded 23:04:42
    E.top(b2, t_end, stamp('2026-02-19', 23, 12, 48, r2), z=1)   # Kayn game: recorded 23:12:48

    # brackets
    def ghost(t):                                                # unsure lock: jitters on the shimmer
        x, y = kz_screen(t)
        return x + 0.008 * noise1(t * 5.0, 3), y + 0.008 * noise1(t * 5.0, 4)
    E.top(0.42, 1.86, L.lock(0.42, 1.86, 0.5, 0.45, size=0.15, color=CYAN, label='MOTION', follow_fn=ghost), z=5)
    E.top(t_reveal, t_boom, L.lock(t_reveal, t_boom, 0.5, 0.5, size=0.14, color=RED, label='', follow_fn=kz_screen),
          z=5)
    E.top(b5, b2, L.lock(b5, b2, 0.25, 0.28, size=0.18, color=RED, label='', follow_fn=kz_screen), z=5)

    def id_label(img, t, ctx):
        # drawn ABOVE the box (L.lock puts labels below, where the game's '+196 / 72' numbers float)
        if eout((t - b5) / 0.35) <= 0.95:                # same 'locked' moment as L.lock: 0.22 s after b5
            return img
        px, py = kz_screen(t)
        blink = 1.0 if int((t - b5) * 10) % 2 == 0 else 0.6
        return ty.text(img, 'ID: ART3M1S', px, py - 0.09 - 0.035, 0.022, 'mono', RED, alpha=blink, tracking=0.12)
    E.top(b5, b2, id_label, z=6)
    lock_in = b9 - 0.22                                          # label appears 0.22 s after the lock starts -> 6.42
    E.top(lock_in, t_end, L.lock(lock_in, t_end, 0.5, 0.5, size=0.17, color=RED, label='SUBJECT: ART3M1S',
                                 follow_fn=ky_screen), z=5)

    # cyan crosshair on the enemy walking into Kayn's bush (clip 33.6 -> 34.05 = t 6.05 -> 6.55), tethered to the
    # subject; snaps off as Kayn leaps out (clip 34.25 = t 6.89)
    def tether(img, t, ctx):
        a = smooth((t - 6.05) / 0.15) * (1.0 - smooth((t - 6.75) / 0.12))
        if a <= 0.0:
            return img
        c = cam2(t)
        s = r2.s(t)
        ex_, ey_ = to_screen(c, *tony_track(s))
        kx_, ky_ = to_screen(c, *ky_track(s))
        img = fx.line(img, kx_, ky_, ex_, ey_, 0.0016, CYAN, 0.45 * a)
        return fx.crosshair(img, ex_, ey_, 0.03, 0.01, 0.0025, CYAN, 0.9 * a, rot=t * 120.0)
    E.top(6.05, 6.9, tether, z=5)

    # freeze-frame analysis: a cyan scan line sweeps down the frozen picture on each beat
    def sweeps(img, t, ctx):
        for bt in (b5, b6, b7):
            u = (t - bt) / 0.6
            if 0.0 <= u < 1.0:
                y = 0.06 + 0.86 * smooth(u)
                a = 1.0 - u
                img = fx.rect(img, 0.0, y - 0.06, 1.0, y, CYAN, 0.05 * a)
                img = fx.line(img, 0.0, y, 1.0, y, 0.0022, CYAN, 0.6 * a)
        return img
    E.top(b5, b2, sweeps, z=4)

    # the title: glitches in out of the explosion on bar 1, holds 3.09 s, tears apart after the bar-2 cut
    T_IN, T_OUT0, T_OUT1 = t_boom, 5.95, 6.32
    glitch_beats = (b5, b6, b7, b2)

    def title(img, t, ctx):
        u = t - T_IN
        if u < 0 or t >= T_OUT1:
            return img
        fr = int(t * 30)
        # ink-on-white while the explosion flash burns (flash >= 0.65: frames 2.867-2.900), bone once it drops
        inv = smooth((boom_flash(t) - 0.35) / 0.3)
        col = mix3(BONE, INK, inv)
        g = max(env(t, bt, 0.0, 0.07) for bt in glitch_beats)
        out = clamp((t - T_OUT0) / (T_OUT1 - T_OUT0))
        split = 5.0 + 36.0 * env(t, T_IN, 0.0, 0.1) + 26.0 * g + 30.0 * out
        sc = lerp(1.16, 1.0, eout(u / 0.16))

        def per(i, n):
            land = T_IN + 0.16 * hashf(i, 11)            # letters flicker on in random order over 0.16 s
            a = 1.0
            if t < land:
                a = 0.85 if hashf(i, fr, 1) > 0.45 else 0.0
            die = T_OUT0 + (T_OUT1 - T_OUT0 - 0.06) * hashf(i, 12)
            if t >= die:
                a = 0.0
            elif t >= T_OUT0:
                a *= 1.0 if hashf(i, fr, 2) > 0.35 else 0.2
            jit = max(g, 1.0 - eout(u / 0.25), out)
            dx = (hashf(i, fr, 3) - 0.5) * 0.035 * jit if hashf(i, fr, 4) > 0.5 else 0.0
            return dict(dx=dx, alpha=a)
        return ty.letters(img, 'PARANOIA', 0.5, TITLE_Y, TITLE_SIZE, 'anton', per=per, tracking=0.04, color=col,
                          scale=sc, split=split, glow=0.6 * (1.0 - inv), glow_color=RED)
    E.top(T_IN, T_OUT1, title, z=30)

    # tears that also rip the HUD: on the bar-2 cut and in the last 0.3 s before the drums
    E.top(T2_IN, T1_END, lambda img, t, ctx: fx.glitch(img, int(t * 30) + 7, 0.6 * win(t, T2_IN, T1_END), rgb=12.0),
          z=50)
    E.top(t_end - 0.30, t_end,
          lambda img, t, ctx: fx.glitch(img, int(t * 40) + 3, 0.2 + 0.6 * smooth((t - (t_end - 0.30)) / 0.30),
                                        rgb=14.0), z=50)

    def live(img, t, ctx):
        if int(t * 24) % 3 == 2:                          # flicker
            return img
        img = fx.rect(img, 0.465, 0.059, 0.535, 0.105, RED, 0.9)      # letters at y 0.069-0.095 (inside 0.06)
        return ty.text(img, 'LIVE', 0.5, 0.082, 0.026, 'mono', BONE, tracking=0.15)
    E.top(t_end - 0.30, t_end, live, z=60)

    # ============================== sound ===========================================================================
    E.music('lowpass', 0.0, 0.55, cutoff_from=600.0, cutoff_to=18000.0)   # the feed's speaker warms up
    E.sfx('tick', 0.0, gain_db=-6)
    E.sfx('glitch', 0.10, gain_db=-8, dur=0.35)                           # static burst
    E.sfx('tick', 0.48, gain_db=-6)                                       # feed on
    for bt in hb_beats:
        E.sfx('heartbeat', bt, gain_db=-8, bpm=song.bpm)                  # beats 1 and 2
    E.sfx('zap', t_reveal, gain_db=-6, dur=0.25)                          # the gold beam (impact() adds the thump)
    E.sfx('glitch', t_jump - 0.04, gain_db=-8, dur=0.12)                  # the hidden camera cut
    E.sfx('boom', t_boom, gain_db=-3, dur=2.4)                            # title drop (impact() adds the crack)
    E.sfx('shutter', b5, gain_db=-3)                                      # freeze-frame
    E.sfx('tick', b6, gain_db=-4)                                         # enhance
    E.sfx('tick', b7, gain_db=-4)                                         # enhance
    E.sfx('glitch', T2_IN, gain_db=-6, dur=0.22)                          # cut to CAM 02
    E.sfx('tick', b9, gain_db=-8)                                         # subject locked
    E.sfx('glitch', t_end - 0.30, gain_db=-6, dur=0.30)                   # the feed tears
    E.sfx('reverse', t_end, gain_db=-6, dur=0.8)                          # reverse cymbal ends exactly on 8.54
