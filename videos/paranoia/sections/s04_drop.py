"""s04 DROP (bars 10-13, t 28.28-39.58): Samira's first pentakill, velocity-synced to the chorus kicks, then an
instant replay of the last kill from a new angle.

Music (video t): bar 10 = 28.28 (the drop), bar 11 = 31.12, bar 12 = 33.94, bar 13 = 36.76, bar 14 = 39.58.
Chorus kicks on 16ths 0, 3, 6, 9, 12 (+13 in bars 10 and 12), claps on 16ths 4 and 12; a 16th is ~0.177 s here.
Lyrics: "They praying for the death of a ROCK (30.26) STAR (30.54) / Everybody hates it, ever since you got MORE
(33.28) / They're praying for the death of a ROCKSTAR (35.90) / Ooh, they love you when you're lost, boy".

Beat sheet (video t, bar.16th, clip seconds in Samira clip 2026-02-20__01-11-57):
  28.28  10.0   kill 1 (46.717, '999/1123' pops) out of s03's white-out: the drop
  28.81  10.3   red strobe
  29.34  10.6   red '1559' crit burst + purple ring (48.583) on the kick, at 0.9x
  29.87  10.9   kill 2 DOUBLE (49.117: orange ring bursts, '+185' gold)
  30.26         "ROCK" slam
  30.40  10.12  clap: the in-game camera jump (50.38->50.42) used as a cut, under a white strobe
  30.54         "STAR" slam (slow-mo crawl into kill 3)
  31.10  11.0   kill 3 TRIPLE (50.650, '999' pops)
  31.63  11.3   second in-game camera jump (51.62->51.65) as a cut, red strobe
  32.16  11.6   kill 4 QUADRA (52.050, '999' + '+200')
  32.69  11.9   white strobe
  33.23  11.12  clap + "got MORE": kill 5 PENTAKILL (53.517, '999/1011'): invert flash, boom; the music tape-stops
  33.93  12.0   the picture stops dead on the downbeat, then REWINDS (VHS look) to 52.30
  34.99  12.6   slice wipe to the REPLAY: new angle (tight, Dutch tilt, slight yaw, echo trails), music muffled
  36.05  12.12  clap + "ROCKSTAR": the replayed kill 5 lands again, the filter opens, ROCKSTAR slam
  36.77  13.0   snap back to the wide live view; stage-light afterglow, strobes on the bar-13 kicks
  39.40-39.76   s05's whip pan out (owned by s05; this shot runs to 39.76)
"""
import math

from engine.api import *

SPAN = (28.28, 39.58)
CLIP = 'League-of-Legends__2026-02-20__01-11-57.mp4'

RED = (1.0, 0.16, 0.22)
CYAN = (0.2, 0.95, 1.0)
BONE = (0.96, 0.94, 0.9)
INK = (0.02, 0.02, 0.04)
GOLD = (1.0, 0.82, 0.3)
WHITE = (1.0, 1.0, 1.0)
ASP = 16 / 9

# Kill frames pinned on the 1/30 s strips (out/wip/kills/League-of-Legends__2026-02-20__01-11-57_<t>.jpg)
C_K1 = 46.717     # '999 / 1123' pop big (46.683 shows only '421')
C_BURST = 48.583  # red explosion + '1559' crit; purple ring from 48.617
C_K2 = 49.117     # orange ring bursts + '+185' gold (scoreboard 33->34 between 49.0 and 49.1)
C_J1 = 50.400     # in-game camera jumps between 50.383 and 50.417
C_K3 = 50.650     # '999' pops big (50.617 has nothing)
C_J2 = 51.633     # in-game camera jumps between 51.617 and 51.650
C_K4 = 52.050     # '999' + '+200' gold pop (52.017 has nothing)
C_K5 = 53.517     # '999 / 1011' pop big, 0.07 s after the white-green flash (53.45)
C_REW = 52.30     # the rewind stops here (after kill 4); the replay picks up from here

# where each kill happens in the clip frame (scouting.json)
P_K = [(0.48, 0.30), (0.50, 0.36), (0.58, 0.30), (0.43, 0.25), (0.53, 0.24)]


def at16(b, n, kind='kick'):
    """Video time of 16th n of bar b, snapped to the measured `kind` onset if one is within 60 ms."""
    g = song.bar(b) + n * (song.bar(b + 1) - song.bar(b)) / 16.0
    near = song.onsets(kind, g - 0.06, g + 0.06)
    return min(near, key=lambda x: abs(x - g)) if near else g


def word_at(sub, lo, hi, default):
    """Start time of the first sung word containing `sub` with t0 in [lo, hi)."""
    for w0, w1, w in song.words:
        if lo <= w0 < hi and sub in w.lower():
            return w0
    return default


def safe(z, cx, cy, rot=0.0, m=0.006):
    """Clamp a camera centre so the (rotated) view stays inside the clip (no mirrored edges)."""
    a = math.radians(abs(rot))
    hx = (math.cos(a) + math.sin(a) / ASP) / (2 * z) + m
    hy = (ASP * math.sin(a) + math.cos(a)) / (2 * z) + m
    cx = 0.5 if hx >= 0.5 else clamp(cx, hx, 1 - hx)
    cy = 0.5 if hy >= 0.5 else clamp(cy, hy, 1 - hy)
    return cx, cy


def mixc(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def on_screen(cam, p):
    """Where clip point p lands on screen through cam (inverse of fx.camera's zoom + rotation; yaw ignored)."""
    qx = (2 * p[0] - 2 * cam.cx) * ASP * cam.zoom
    qy = (2 * p[1] - 2 * cam.cy) * cam.zoom
    a = math.radians(-cam.rot)
    ca, sa = math.cos(a), math.sin(a)
    px, py = qx * ca + qy * sa, -qx * sa + qy * ca
    return 0.5 + px / ASP / 2 + cam.ox, 0.5 + py / 2 + cam.oy


def build(E):
    T0 = SPAN[0]
    END = 39.76                          # s05 whips out of this shot over 39.40-39.76

    # ---- timing ------------------------------------------------------------------------------------------------
    tK = [T0,                            # 28.28  bar 10, 16th 0   kill 1 (the drop; seam is fixed at 28.28)
          at16(10, 9),                   # 29.867 bar 10, 16th 9   kill 2 DOUBLE
          at16(11, 0),                   # 31.103 bar 11, 16th 0   kill 3 TRIPLE
          at16(11, 6),                   # 32.161 bar 11, 16th 6   kill 4 QUADRA
          at16(11, 12)]                  # 33.225 bar 11, 16th 12  kill 5 PENTA (kick + clap, "got MORE")
    t_burst = at16(10, 6)                # 29.339 crit burst
    t_j1 = at16(10, 12)                  # 30.401 clap: camera jump 1
    t_j2 = at16(11, 3)                   # 31.633 camera jump 2
    t_stop = at16(12, 0)                 # 33.933 dead stop -> rewind
    t_pk_out = at16(12, 3)               # 34.455 PENTAKILL scatters
    t_cut = at16(12, 6)                  # 34.989 wipe to the replay
    t_rk = at16(12, 12)                  # 36.049 replayed kill (kick + clap)
    t_snap = at16(13, 0)                 # 36.767 snap back to wide
    t_rs2_out = at16(13, 3)              # 37.283 ROCKSTAR blows out
    t_rock = word_at('rock', 30.0, 30.5, 30.26)
    t_star = word_at('star', 30.4, 30.8, 30.54)
    t_rs_out = at16(11, 4, 'snare')      # 31.811 clap: ROCK STAR blows out (ROCK 1.55 s, STAR 1.27 s on screen)
    t_rs2 = word_at('rock', 35.6, 36.2, 35.90)   # "rockstar"

    # ---- shot 1: the penta run (28.28 -> 35.11) -------------------------------------------------------------------
    # Velocity: 0.22x through each kill, 2-3x between. Cruise speeds (from remap.py's solve):
    #   28.28->29.34  46.717->48.583  mean 1.76x, cruise ~2.4x, eases to 0.9x on the crit burst
    #   29.34->29.87  48.583->49.117  mean 1.01x, cruise ~1.3x, brakes to 0.22x on kill 2
    #   29.87->30.40  49.117->50.400  mean 2.40x, cruise ~3.1x; the camera jump crosses at 1.6x on the clap
    #   30.40->31.10  50.400->50.650  mean 0.36x: drops to ~0.22x within ~0.14 s, slow crawl into kill 3
    #   31.10->31.63  50.650->51.633  mean 1.85x, cruise ~2.3x; jump 2 crosses at 2.0x on the kick
    #   31.63->32.16  51.633->52.050  mean 0.79x: 2.0x -> 0.77x -> 0.22x into kill 4
    #   32.16->33.23  52.050->53.517  mean 1.38x, cruise ~2.15x into the penta
    #   33.23->33.93  53.517->53.640  ~0.23x afterglow, brakes to a dead stop (0x) on the bar-12 downbeat
    #   33.93->34.99  53.640->52.300  rewind, mean -1.27x, cruise ~-1.8x
    r1 = Remap([
        K(tK[0], C_K1, 0.22, (0.0, 0.0)),
        K(t_burst, C_BURST, 0.9, (0.35, 0.35)),
        K(tK[1], C_K2, 0.22, (0.3, 0.45)),
        K(t_j1, C_J1, 1.6, (0.35, 0.3)),
        K(tK[2], C_K3, 0.22, (0.2, 0.6)),
        K(t_j2, C_J2, 2.0, (0.35, 0.3)),
        K(tK[3], C_K4, 0.22, (0.3, 0.6)),
        K(tK[4], C_K5, 0.22, (0.35, 0.45)),
        K(t_stop, C_K5 + 0.123, 0.0, (0.3, 0.5)),
        K(t_cut, C_REW, -1.0, (0.5, 0.25)),
        K(t_cut + 0.25, C_REW - 0.25, -1.0, (0.0, 0.0)),
    ])

    # camera: frames the next kill and pushes in (to ~1.13x) as the footage slows; full frame + HUD at speed.
    # The speed is averaged over +-0.12 s so the zoom breathes instead of snapping.
    foc = follow([(tK[i], P_K[i][0], P_K[i][1]) for i in range(5)] + [(t_cut, 0.52, 0.28)])

    def cam1(t):
        v = sum(abs(r1.speed(t + d)) for d in (-0.12, -0.06, 0.0, 0.06, 0.12)) / 5.0
        z = 1.0 + 0.15 * smooth(clamp((1.25 - v) / 1.0))
        cx, cy = safe(z, *foc(t))
        return Cam(zoom=z, cx=cx, cy=cy)

    def lines(img, t, ctx):
        """Speed lines while the footage rushes forward (> 1.5x)."""
        a = 0.4 * clamp((r1.speed(t) - 1.5) / 0.9)
        if t_rock - 0.1 < t < t_rs_out + 0.2:
            a *= 0.35                    # keep ROCK STAR readable
        if a < 0.02:
            return img
        return fx.speed_lines(img, 0.5, 0.47, seed=int(t * 30), amount=a, density=170, inner=0.34, color=BONE,
                              thick=0.32)

    E.shot(T0, t_cut + 0.12, CLIP, r1, cam=cam1, fx=[lines], name='s04 penta run', hits=list(tK))

    # ---- shot 2: instant replay + afterglow (34.87 -> 39.76) -----------------------------------------------------
    #   34.87->36.05  52.132->53.517  mean 1.18x: ~1.65x, then brakes to 0.18x: kill 5 again on 36.049 (bar 12.12)
    #                                 (at 34.989 it shows 52.30, where the rewind stopped)
    #   36.05->36.77  53.517->53.700  ~0.21x through "rockstar", 0.45x at the snap
    #   36.77->39.76  53.700->56.805  mean 1.04x (~1x, speeding to 1.6x into s05's whip); max clip time 56.8 < 58.2
    s2_0 = t_cut - 0.12
    r2 = Remap([
        K(s2_0, C_REW - 0.12 * 1.4, 1.4, (0.0, 0.0)),
        K(t_rk, C_K5, 0.18, (0.25, 0.6)),
        K(t_snap, C_K5 + 0.183, 0.45, (0.2, 0.4)),
        K(END, C_K5 + 0.183 + 3.105, 1.6, (0.3, 0.4)),
    ])

    def replay_view(t):
        """The 'other camera': tight, Dutch tilt, slight yaw orbit, slow push."""
        u = clamp((t - s2_0) / (t_snap - s2_0))
        z = 1.48 + 0.1 * smooth(u)
        rot = -4.5 + 2.5 * u
        yaw = 6.0 - 5.0 * u
        cx, cy = safe(z, 0.52, 0.30, rot, m=0.04)
        return z, cx, cy, rot, yaw

    def cam2(t):
        z, cx, cy, rot, yaw = replay_view(min(t, t_snap))
        k = eout(clamp((t - t_snap) / 0.2))          # snap back to the wide view on bar 13
        if k <= 0:
            return Cam(zoom=z, cx=cx, cy=cy, rot=rot, yaw=yaw)
        zw = 1.0 + 0.05 * smooth(clamp((t - t_snap - 0.2) / (END - t_snap - 0.2)))
        cxw, cyw = safe(zw, 0.5, 0.49)
        return Cam(zoom=lerp(z, zw, k), cx=lerp(cx, cxw, k), cy=lerp(cy, cyw, k), rot=rot * (1 - k),
                   yaw=yaw * (1 - k))

    def echo_w(t):
        if t < t_cut - 0.05:
            return 0.0
        if t < t_snap:
            return 0.7
        return lerp(0.7, 0.3, smooth((t - t_snap) / 0.8))

    def echo(t, ctx, shot):
        """Replay ghosting: the frame plus two trailing copies 0.04 and 0.08 clip-seconds back (the static HUD
        stays sharp, moving spells and champions trail). 3 clip samples per sub-sample."""
        s = shot.s(t)
        c = shot.clip
        a = c.at(s, shot.interp)
        w = echo_w(t)
        if w < 0.02:
            return a
        return (a * (1 - 0.5 * w) + c.at(s - 0.04, shot.interp) * (0.3 * w)
                + c.at(s - 0.08, shot.interp) * (0.2 * w))

    E.shot(s2_0, END, CLIP, r2, cam=cam2, src=echo, name='s04 replay', hits=[t_rk])
    E.transition(s2_0, t_cut + 0.12, T.slices(9, 'y'))      # broadcast slice wipe, centred on 34.989
    E.samples(s2_0, t_cut + 0.12, 4)

    # ---- grades ----------------------------------------------------------------------------------------------
    look(E, T0, T0 + 1.0, 'hot', fade_out=0.7)                     # the drop
    look(E, tK[4], t_stop, 'hot', fade_out=0.35, amount=0.45)      # the penta (half: the in-game flash is bright)
    look(E, t_snap, 39.45, 'hot', fade_in=0.15, fade_out=0.3, amount=0.55)   # afterglow

    # the penta's in-game white-green flash fills the frame for ~0.7 s: pull exposure and bloom down, push contrast,
    # so the picture and the PENTAKILL slam stay contrasty instead of a yellow-white wash
    def penta_grade(P, t):
        k = smooth((t - tK[4]) / 0.06) * (1 - smooth((t - (t_stop - 0.12)) / 0.2))
        if k <= 0:
            return
        P['exposure'] += -0.2 * k
        P['contrast'] += 0.14 * k
        P['bloom'] = lerp(P['bloom'], 0.22, k)
        P['vignette'] = max(P['vignette'], 0.5 * k)
    E.post(tK[4], t_stop + 0.1, penta_grade)

    # rewind: VHS tape look (33.93 -> 35.05)
    def vhs_k(t):
        return smooth((t - t_stop) / 0.06) * (1 - smooth((t - (t_cut - 0.04)) / 0.1))

    def vhs_post(P, t):
        k = vhs_k(t)
        if k <= 0:
            return
        v = abs(r1.speed(t))
        P['sat'] *= 1 - 0.45 * k
        P['temp'] += -0.3 * k
        P['contrast'] += 0.1 * k
        P['chroma'] += (4.0 + 3.0 * v) * k
        P['glitch'] = max(P['glitch'], (0.12 + 0.06 * v) * k)
        P['glitch_rate'] = 24.0
        P['scanlines'] = max(P['scanlines'], 0.16 * k)
        P['vignette'] = max(P['vignette'], 0.45 * k)
        P['grain'] = max(P['grain'], 0.05 * k)
    E.post(t_stop, t_cut + 0.08, vhs_post)

    def vhs_layer(img, t, ctx):
        k = vhs_k(t)
        if k <= 0.01:
            return img
        v = abs(r1.speed(t))
        img = fx.dir_blur(img, 16.0 * v * k, 0.0)                 # tape smear
        yb = 1.0 - ((t - t_stop) * 1.3) % 1.15                     # tracking band rolling up
        # (fx.rect with an end below 0 fills almost the whole frame, so skip/clip bands that have left the top)
        for y0, y1, a in ((yb, yb + 0.028, 0.10), (yb + 0.034, yb + 0.038, 0.18)):
            if y1 > 0.002 and y0 < 0.998:
                img = fx.rect(img, 0.0, max(0.0, y0), 1.0, min(1.0, y1), BONE, a * k)
        return img
    E.layer(t_stop, t_cut + 0.08, vhs_layer, z=1)

    def stop_hit(P, t):
        e = env(t, t_stop, 0.0, 0.1)
        P['chroma'] += 14.0 * e
        P['exposure'] += 0.15 * e
    E.post(t_stop, t_stop + 0.5, stop_hit)

    # replay: letterbox + contrast
    def replay_post(P, t):
        k = smooth((t - t_cut) / 0.1) * (1 - smooth((t - t_snap) / 0.15))
        P['letterbox'] = max(P['letterbox'], 0.12 * k)
        P['contrast'] += 0.06 * k
        P['vignette'] = max(P['vignette'], 0.42 * k)
    E.post(t_cut, t_snap + 0.16, replay_post)

    # snap back to wide on bar 13
    def snap_post(P, t):
        e = env(t, t_snap, 0.0, 0.09)
        P['zoom_blur'] = max(P['zoom_blur'], 0.28 * e)
        P['zoom_blur_cx'], P['zoom_blur_cy'] = 0.5, 0.5
        P['chroma'] += 8.0 * e
    E.post(t_snap, t_snap + 0.5, snap_post)
    E.samples(t_snap - 0.02, t_snap + 0.24, 8)

    # ---- the seam: start from s03's white-out (flash 1.0 at 28.28, gone by 28.53) ---------------------------------
    def seam_white(P, t):
        k = 1.0 - smooth((t - T0) / 0.25)
        if k > P['flash']:
            P['flash'], P['flash_color'] = k, WHITE
    E.post(T0, T0 + 0.26, seam_white)

    # ---- kill impacts (all on kicks) ---------------------------------------------------------------------------
    # Flashes stay low (peak flash = flash * strength: 0.15 / 0.20 / 0.14 / 0.34): the exposure kick, chroma and a
    # contrast punch carry each hit, so no frame goes milky and the picture is clean again 0.15 s after.
    cols = [WHITE, WHITE, RED, WHITE, (1.0, 0.92, 0.7)]
    strength = [1.3, 1.0, 1.1, 1.2, 1.7]
    flashes = [0.0, 0.15, 0.18, 0.12, 0.2]
    pts = []
    for i in range(5):
        sx, sy = on_screen(cam1(tK[i]), P_K[i])
        pts.append((sx, sy))
        impact(E, tK[i], strength[i], sx, sy, color=cols[i], flash=flashes[i],
               punch=(0.1 if i == 4 else 0.09), decay=(0.16 if i == 4 else 0.14), end=SPAN[1])

    def hit_grade(tk, amt=0.16):
        """Contrast + saturation punch on a hit (instead of a white flash)."""
        def f(P, t):
            e = env(t, tk, 0.0, 0.12)
            P['contrast'] += amt * e
            P['sat'] *= 1 + amt * e
        E.post(tk, tk + 0.6, f)
    for tk in tK[1:] + [t_rk]:
        hit_grade(tk)

    # penta extras: 2-frame negative on the clap, then the white flash; gold ring + speed-line burst
    def penta_invert(P, t):
        P['invert'] = 1.0
        P['flash'] = 0.0
    E.post(tK[4] - 0.004, tK[4] + 0.034, penta_invert)

    px5, py5 = pts[4]

    def penta_ring(img, t, ctx):
        u = (t - tK[4]) / 0.5
        if u < 0 or u > 1:
            return img
        img = fx.ring(img, px5, py5, 0.04 + 0.6 * eout(u), 0.002 + 0.012 * (1 - u), GOLD, 0.9 * (1 - u))
        return fx.speed_lines(img, px5, py5, seed=int(t * 40), amount=0.3 * (1 - u), density=120,
                              inner=0.16 + 0.3 * u, color=GOLD, thick=0.35)
    E.layer(tK[4], tK[4] + 0.5, penta_ring, z=2)

    # replayed kill
    rx, ry = on_screen(cam2(t_rk), P_K[4])
    impact(E, t_rk, 1.4, rx, ry, color=RED, flash=0.18, end=SPAN[1])      # peak flash 0.25

    # telestrator: a cyan circle draws itself round the victim from the 35.515 kick (bar 12, 16th 9), holds, and
    # pops outward on the replayed kill
    t_tele = at16(12, 9)

    def tele(img, t, ctx):
        x, y = on_screen(cam2(t), P_K[4])
        if t < t_rk:
            p = eout(clamp((t - t_tele) / 0.33))
            if p <= 0:
                return img
            return fx.ring(img, x, y, 0.085, 0.006, CYAN, 0.95, arc=(200.0, 200.0 + 359.0 * p))
        u = (t - t_rk) / 0.3
        if u >= 1:
            return img
        return fx.ring(img, x, y, 0.085 + 0.12 * eout(u), 0.001 + 0.006 * (1 - u), CYAN, 1 - u)
    E.layer(t_tele, t_rk + 0.3, tele, z=3)

    # ---- strobes on the non-kill kicks (white/red alternating) -------------------------------------------------
    # (added after the impacts so a strobe keeps its own colour; all <= 0.4: the jump cuts no longer need a bright
    # strobe to hide a morph frame, since the engine stops RIFE at camera snaps)
    strobes = [(at16(10, 3), RED, 0.3), (t_burst, WHITE, 0.25), (t_j1, WHITE, 0.4), (t_j2, RED, 0.4),
               (at16(11, 9), WHITE, 0.25),
               (at16(13, 3), RED, 0.22), (at16(13, 6), WHITE, 0.22), (at16(13, 9), RED, 0.22),
               (at16(13, 12), WHITE, 0.22)]

    def strobe(P, t):
        best, col = 0.0, WHITE
        for ts, c, a in strobes:
            e = a * env(t, ts, 0.012, 0.05)
            if e > best:
                best, col = e, c
        if best > P['flash']:
            P['flash'], P['flash_color'] = best, col
    E.post(T0, 39.3, strobe)

    # the two jump cuts get an exposure kick + RGB split instead of the old bright white/red strobe
    def jump_kick(P, t):
        for tj in (t_j1, t_j2):
            P['exposure'] += 0.35 * env(t, tj, 0.0, 0.035)
            P['chroma'] += 12.0 * env(t, tj, 0.0, 0.08)
    E.post(t_j1, t_j2 + 0.4, jump_kick)

    beat_pulse(E, T0 + 0.45, t_stop - 0.05, amount=0.025, min_s=0.5)
    beat_pulse(E, t_snap + 0.3, 39.35, amount=0.03, min_s=0.5)

    # ---- kill meter: 5 pips + DOUBLE/TRIPLE/QUADRA (top left, clear of the fight and the HUD) -----------------------
    # DOUBLE 1.24 s, TRIPLE 1.06 s, QUADRA 1.06 s on screen (one persistent widget; the word swaps on each kill)
    words = ['', 'DOUBLE KILL', 'TRIPLE KILL', 'QUADRA KILL', '']

    def meter(img, t, ctx):
        n = sum(1 for k in tK if t >= k - 1e-6)
        fade = 1.0 - smooth((t - (t_stop - 0.1)) / 0.2)
        if n == 0 or fade <= 0:
            return img
        for i in range(5):
            x, y = 0.07 + i * 0.024, 0.262
            if i < n:
                pop = env(t, tK[i], 0.0, 0.12)
                img = fx.disc(img, x, y, 0.0105 * (1 + 0.9 * pop), mixc(GOLD, WHITE, pop), fade)
            else:
                img = fx.ring(img, x, y, 0.0095, 0.0022, BONE, 0.5 * fade)
        w = words[n - 1]
        if w:
            u = t - tK[n - 1]

            def per(i, nn):
                k = eout((u - i * 0.014) / 0.08)
                return dict(dy=-(1 - k) * 0.05, scale=1 + (1 - k) * 0.6, alpha=k)
            # left edge at 0.064 so the first letter's overshoot (x1.6) stays right of x 0.05
            img = ty.letters(img, w, 0.064, 0.19, 0.06, 'anton', per=per, tracking=0.03, color=GOLD, alpha=fade,
                             split=3.0, stroke=0.0035, stroke_color=INK, anchor=(0.0, 0.5))
        return img
    E.layer(T0, t_stop + 0.12, meter, z=3)

    # ---- "ROCK" (30.26) "STAR" (30.54) lyric slam, lower third, blows out on the 31.81 clap ----------------------
    def rock_star(img, t, ctx):
        out = ein(clamp((t - t_rs_out) / 0.16))
        if out >= 1.0:
            return img
        for word, w0, ax, x in (('ROCK', t_rock, 1.0, 0.492), ('STAR', t_star, 0.0, 0.508)):
            u = t - w0
            if u < 0:
                continue
            k = eout(u / 0.09)
            sc = lerp(2.4, 1.0, k) + 0.03 * clamp(u / 1.5) + 0.6 * out
            ox, oy, r = shake(t, 0.007 * env(t, w0 + 0.09, 0.0, 0.18), 25.0, int(w0 * 100))
            sp = 3.0 + 12.0 * env(t, w0 + 0.05, 0.0, 0.15) + 25.0 * out
            img = ty.text(img, word, x + ox, 0.705 + oy, 0.125, 'anton', BONE, sc, r, k * (1 - out), tracking=0.02,
                          stroke=0.004, stroke_color=INK, glow=0.55, glow_color=RED, split=sp, anchor=(ax, 0.5))
        return img
    E.layer(t_rock, t_rs_out + 0.17, rock_star, z=4)

    # ---- PENTAKILL slam (33.26 -> 34.46, then the letters scatter as the rewind takes over) ----------------------
    def pentakill(img, t, ctx):
        u = t - (tK[4] + 0.035)
        if u < 0:
            return img
        out = clamp((t - t_pk_out) / 0.22)
        if out >= 1.0:
            return img

        def per(i, n):
            k = eout((u - i * 0.022) / 0.09)
            h = hashf(i, 7.0) - 0.5
            # scatter drifts up/sideways so no letter dips below y 0.88 (letters stay inside y 0.06-0.92)
            return dict(dx=out * (hashf(i, 3.0) - 0.5) * 0.2, dy=-(1 - k) * 0.12 + out * (h * 0.2 - 0.05),
                        scale=1 + (1 - k) * 1.6 + out * 0.4, rot=out * h * 40, alpha=k * (1 - out))
        thump = env(t, tK[4] + 0.25, 0.0, 0.2)
        # a dark ember halo + drop shadow (not a bright orange glow) separates the gold letters from the in-game
        # white-green flash behind them
        return ty.letters(img, 'PENTAKILL', 0.5, 0.72, 0.15, 'anton', per=per, tracking=0.04, color=GOLD,
                          scale=1 + 0.03 * clamp(u / 1.2), glow=0.85, glow_color=(0.32, 0.04, 0.0), shadow=0.9,
                          split=4.0 + 10.0 * thump, stroke=0.005, stroke_color=INK)
    E.layer(tK[4], t_pk_out + 0.23, pentakill, z=4)

    # ---- ROCKSTAR (35.90): R-O-C-K land on "rock", S-T-A-R land on the replayed kill (36.049); out on 37.283 ------
    def rockstar2(img, t, ctx):
        u = t - t_rs2
        if u < 0:
            return img
        out = ein(clamp((t - t_rs2_out) / 0.18))
        if out >= 1.0:
            return img
        kick = env(t, t_rk, 0.0, 0.12)

        # Letters drop in from above (overshoot grows upward). Size 0.15 at y 0.70: at the largest scale (x2.2 slam
        # x1.1 kick) a letter spans y 0.47-0.83, and the word sits in x 0.27-0.73, inside the letterbox too.
        def per(i, n):
            d = i * 0.025 if i < 4 else (t_rk - t_rs2) + (i - 4) * 0.025
            k = eout((u - d) / 0.08)
            return dict(dy=-(1 - k) * 0.05, scale=1 + (1 - k) * 1.2, alpha=k)
        ox, oy, r = shake(t, 0.01 * kick, 30.0, 77)
        return ty.letters(img, 'ROCKSTAR', 0.5 + ox, 0.70 + oy, 0.15, 'anton', per=per, tracking=0.03, color=RED,
                          scale=(1 + 0.1 * kick) * (1 + 0.25 * out), alpha=1 - out, glow=0.7, glow_color=RED,
                          split=3.0 + 16.0 * kick + 20.0 * out, stroke=0.005, stroke_color=BONE)
    E.layer(t_rs2, t_rs2_out + 0.19, rockstar2, z=4)

    # ---- stage lights in the afterglow ----------------------------------------------------------------------------
    def stage(img, t, ctx):
        k = smooth((t - t_snap) / 0.3) * (1 - smooth((t - 39.15) / 0.3))
        if k <= 0:
            return img
        return fx.light_leak(img, t * 1.6, seed=21, amount=0.28 * k, colors=(RED, CYAN, GOLD))
    E.layer(t_snap, 39.45, stage, z=0)

    # ---- broadcast UI (crisp, after post) ------------------------------------------------------------------------
    def rewind_badge(img, t, ctx):
        a = 1.0 if int((t - t_stop) * 7) % 2 == 0 else 0.5
        x, y = 0.05, 0.113
        for j in range(2):                                        # two '<' chevrons
            xx = x + j * 0.017
            img = fx.line(img, xx + 0.013, y - 0.021, xx, y, 0.0065, WHITE, a)
            img = fx.line(img, xx, y, xx + 0.013, y + 0.021, 0.0065, WHITE, a)
        return ty.text(img, 'REWIND', x + 0.05, y, 0.033, 'mono', WHITE, alpha=a, tracking=0.14, anchor=(0.0, 0.5),
                       shadow=0.7)
    E.top(t_stop, t_cut, rewind_badge, z=2)

    def replay_badge(img, t, ctx):
        # The red tab wipes open from x 0.05 (it used to slide in from off-screen, and fx.rect with a negative right
        # edge painted a full-width red bar for a frame at 35.00)
        k = eout((t - t_cut) / 0.14) - ein(clamp((t - (t_snap - 0.14)) / 0.14))
        if k <= 0.01:
            return img
        x0 = 0.05
        img = fx.rect(img, x0, 0.083, x0 + 0.108 * k, 0.143, RED, 0.92)
        img = ty.text(img, 'REPLAY', x0 + 0.054, 0.113, 0.033, 'anton', WHITE, alpha=clamp((k - 0.4) / 0.6),
                      tracking=0.1)
        if int((t - t_cut) * 4) % 2 == 0:
            img = fx.disc(img, x0 + 0.124, 0.113, 0.009, RED, k)
        return img
    E.top(t_cut, t_snap, replay_badge, z=2)

    # ---- sound design --------------------------------------------------------------------------------------------
    E.sfx('subdrop', T0, gain_db=-4.0, dur=1.0)                    # under the drop (impact() adds the hit)
    E.sfx('whoosh', t_j1, gain_db=-9.0, dur=0.3, direction='lr')   # jump cut 1
    E.sfx('whoosh', t_j2, gain_db=-9.0, dur=0.3, direction='rl')   # jump cut 2
    E.sfx('boom', tK[4], gain_db=-4.0, dur=1.8)                    # the penta
    E.music('tapestop', tK[4] + 0.27, t_stop)                      # song grinds to a halt with the picture...
    E.sfx('glitch', t_stop, gain_db=-7.0, dur=0.3)                 # ...and kicks back in on bar 12 as it rewinds
    E.sfx('whoosh', t_cut, gain_db=-7.0, dur=0.28, direction='lr')  # slice wipe
    E.music('lowpass', t_cut, t_rk, cutoff_from=1500.0, cutoff_to=14000.0)  # muffled replay, opens on the kill
    E.sfx('reverse', t_rk, gain_db=-7.0, dur=1.0)                  # reverse swell into the replayed kill
    E.sfx('whoosh', t_snap, gain_db=-9.0, dur=0.25, direction='out')  # snap back to wide
