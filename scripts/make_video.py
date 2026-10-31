"""
Render an MP4 of scenario S02: the same lead-car braking event met by three
NIEON-type reference drivers (10th percentile, mean, 90th percentile response
time) and the generic ADS. Uses the models of src/cfuq (Eqs. 1-11, 14-17).

    python scripts/make_video.py [--scenario S02] [--slow 0.5] [--out results/video_S02.mp4]
"""
import os, sys, argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FFMpegWriter
from matplotlib.patches import FancyBboxPatch, Rectangle
from scipy.stats import norm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cfuq.simulate import ramp_up_time, DT
from cfuq.models import nieon_response_time
from cfuq import parameters as P

ap = argparse.ArgumentParser()
ap.add_argument("--scenario", default="S02"); ap.add_argument("--slow", type=float, default=0.5)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "results", "video_S02.mp4"))
a = ap.parse_args()

import pandas as pd
res = pd.read_csv(os.path.join(os.path.dirname(__file__), "..", "results", "scenario_results.csv")).set_index("id")
r = res.loc[a.scenario]
v0, h, aL, jL = r.v0_ms, r.headway_s, r.lead_decel_ms2, 12.5
AMAX, JERK, CV = 7.5, 20.0, 0.40
rut = float(ramp_up_time(np.array([v0]), np.array([h]), np.array([aL]), np.array([jL]))[0])
rt_mean = float(nieon_response_time(np.array([rut]), P.RT_M, P.RT_K, CV)[0])
z10 = norm.ppf(0.10)
rt10 = float(nieon_response_time(np.array([rut]), P.RT_M, P.RT_K, CV, np.array([z10]))[0])
rt90 = float(nieon_response_time(np.array([rut]), P.RT_M, P.RT_K, CV, np.array([-z10]))[0])


def traj(rt, amax, jerk):
    dec = lambda t, t0, j, A: min(max((t - t0) * j, 0.0), A)
    xL, xS, vL, vS, t = h * v0, 0.0, v0, v0, 0.0
    out, contact = [], None
    while t <= 12:
        aLv = dec(t, 0, jL, aL) if vL > 0 else 0.0
        aSv = aLv if contact else (dec(t, rt, jerk, amax) if vS > 0 else 0.0)
        out.append((t, xL, xS, vL, vS, aSv, aLv))
        if vL <= 1e-9 and vS <= 1e-9:
            break
        vLn = max(vL - dec(t, 0, jL, aL) * DT, 0.0)
        vSn = vLn if contact else max(vS - dec(t, rt, jerk, amax) * DT, 0.0)
        xLn = xL + 0.5 * (vL + vLn) * DT; xSn = xS + 0.5 * (vS + vSn) * DT
        if contact is None and xLn - xSn <= 0:
            g0, g1 = xL - xS, xLn - xSn; f = g0 / max(g0 - g1, 1e-12)
            contact = (t + f * DT, max((vS + f * (vSn - vS)) - (vL + f * (vLn - vL)), 0.0))
        if contact:
            xSn, vSn = xLn, vLn
        xL, xS, vL, vS, t = xLn, xSn, vLn, vSn, t + DT
    return np.array(out), contact


lanes = [("Reference driver · 10th percentile (fast)", rt10, AMAX, JERK, "#6FA8F2"),
         ("Reference driver · mean (what one replay uses)", rt_mean, AMAX, JERK, "#2A78D6"),
         ("Reference driver · 90th percentile (slow)", rt90, AMAX, JERK, "#174A8F"),
         ("Generic ADS (illustrative, not Waymo)", 0.55, 8.0, 30.0, "#EB6834")]
runs = [traj(rt, am, jk) for _, rt, am, jk, _ in lanes]
T_SIM = max(R[:, 0].max() for R, _ in runs) + 0.5
INTRO, OUTRO = 2.5, 3.5
n_frames = int((INTRO + T_SIM / a.slow + OUTRO) * a.fps)

BG, ROAD, INK, MUTED = "#12161C", "#2A2F37", "#E8ECF1", "#9AA5B3"
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": MUTED,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": "#3A434F"})
fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
axR = fig.add_axes([0.03, 0.30, 0.94, 0.56]); axR.set_facecolor(BG); axR.axis("off")
axG = fig.add_axes([0.06, 0.06, 0.40, 0.18], facecolor=BG)
axV = fig.add_axes([0.56, 0.06, 0.40, 0.18], facecolor=BG)
title = fig.text(0.03, 0.955, f"Scenario {a.scenario}: lead car brakes from {v0*3.6:.0f} km/h, gap {h*v0:.1f} m ({h:.2f} s headway), {aL:.2f} m/s²",
                 fontsize=22, weight="bold")
sub = fig.text(0.03, 0.915, "", fontsize=16, color=MUTED)
clock = fig.text(0.97, 0.915, "", fontsize=24, ha="right", family="DejaVu Sans Mono")
VIEW = max(30.0, h * v0 + 4.6 * 2 + 8); LANE_H = 1.0; CAR_L, CAR_W = 4.6, 0.42
axR.set_xlim(0, VIEW); axR.set_ylim(-0.1, len(lanes) * LANE_H + 0.05)

for ax, lab in ((axG, "Gap (m)"), (axV, "Speed (km/h)")):
    ax.set_xlim(0, T_SIM); ax.set_xlabel("time since lead car starts braking (s)", fontsize=12); ax.set_title(lab, fontsize=14, color=INK, loc="left")
    ax.grid(color="#2A323C", lw=0.8)
axG.set_ylim(0, h * v0 * 1.12); axV.set_ylim(0, v0 * 3.6 * 1.08)
curG = axG.axvline(0, color=INK, lw=1, alpha=.6); curV = axV.axvline(0, color=INK, lw=1, alpha=.6)
axV.plot(runs[0][0][:, 0], runs[0][0][:, 3] * 3.6, "--", color="#A3ACB8", lw=1.5, label="lead car")
gl, vl = [], []
for (name, rt, *_ , col), (R, c) in zip(lanes, runs):
    gl.append(axG.plot([], [], color=col, lw=2.5)[0]); vl.append(axV.plot([], [], color=col, lw=2.5)[0])

def car_patch(color):
    body = FancyBboxPatch((0, 0), CAR_L, CAR_W, boxstyle="round,pad=0,rounding_size=0.12", fc=color, ec="none", zorder=5)
    lamp1 = Rectangle((0, 0), 0.18, 0.08, fc="#7A1F1A", zorder=6); lamp2 = Rectangle((0, 0), 0.18, 0.08, fc="#7A1F1A", zorder=6)
    win = Rectangle((0, 0), 1.0, CAR_W * 0.7, fc="#1E2630", zorder=6)
    for p in (body, lamp1, lamp2, win): axR.add_patch(p)
    return body, lamp1, lamp2, win

def place(parts, xfront, y, braking):
    body, l1, l2, win = parts; x0 = xfront - CAR_L
    body.set_x(x0); body.set_y(y - CAR_W / 2)
    l1.set_xy((x0, y - CAR_W / 2 + 0.03)); l2.set_xy((x0, y + CAR_W / 2 - 0.11))
    win.set_xy((x0 + CAR_L * 0.42, y - CAR_W * 0.35))
    c = "#FF3B30" if braking else "#7A1F1A"; l1.set_fc(c); l2.set_fc(c)

L = []
for k, (name, rt, am, jk, col) in enumerate(lanes):
    y0 = (len(lanes) - 1 - k) * LANE_H; yc = y0 + 0.45
    axR.add_patch(Rectangle((0, y0), VIEW, 0.9, fc=ROAD, ec="none", zorder=1))
    axR.add_patch(Rectangle((0, y0), VIEW, 0.015, fc="#E9E3C9", zorder=2)); axR.add_patch(Rectangle((0, y0 + 0.885), VIEW, 0.015, fc="#E9E3C9", zorder=2))
    dashes = [axR.add_patch(Rectangle((0, y0 + 0.08), 3.0, 0.02, fc="#8A919C", zorder=2)) for _ in range(int(VIEW // 12) + 3)]
    axR.text(0.3, y0 + 0.80, name, fontsize=16, weight="bold", color=INK, zorder=8, va="center")
    stat = axR.text(VIEW - 0.3, y0 + 0.16, "", fontsize=16, color=INK, ha="right", zorder=8, va="center", family="DejaVu Sans Mono")
    gaplab = axR.text(0, yc + 0.32, "", fontsize=15, color="#F2D16B", ha="center", zorder=8, family="DejaVu Sans Mono")
    gapline = axR.plot([], [], color="#F2D16B", lw=1.5, zorder=7)[0]
    boom = axR.plot([], [], marker="*", ms=0, color="#FF5A3C", zorder=9, ls="none")[0]
    L.append(dict(y0=y0, yc=yc, dashes=dashes, stat=stat, gaplab=gaplab, gapline=gapline, boom=boom,
                  lead=car_patch("#D9DEE4"), fol=car_patch(col), rt=rt))

def at(R, t):
    i = min(len(R) - 1, max(0, int(round(t / DT)))); return R[i], i

def update(f):
    ts = f / a.fps
    if ts < INTRO:
        t = 0.0; sub.set_text("Same crash, four responders. Only the response time differs between the three reference drivers.")
    else:
        t = min((ts - INTRO) * a.slow, T_SIM)
        sub.set_text(f"Shown at {a.slow:g}× speed · ramp-up time {rut:.2f} s · response times 10th / mean / 90th: {rt10:.2f} / {rt_mean:.2f} / {rt90:.2f} s · ADS 0.55 s")
    clock.set_text(f"t = {t:5.2f} s")
    xLead = at(runs[0][0], t)[0][1]; cam = xLead + CAR_L + 2 - VIEW
    for d, (R, c) in zip(L, runs):
        row, i = at(R, t); _, xL, xS, vL, vS, aS, aLv = row
        place(d["lead"], xL - cam + CAR_L, d["yc"], aLv > 0.3)
        hit = c is not None and t >= c[0]
        place(d["fol"], xS - cam, d["yc"], aS > 0.3 and not hit)
        off = xLead % 12
        for k2, p in enumerate(d["dashes"]):
            p.set_x(k2 * 12 - off)
        gap = xL - xS
        if gap > 0.3:
            xa, xb = xS - cam + 0.1, xL - cam - 0.1
            d["gapline"].set_data([xa, xb], [d["yc"] + 0.27] * 2); d["gaplab"].set_position(((xa + xb) / 2, d["yc"] + 0.31)); d["gaplab"].set_text(f"{gap:.1f} m")
        else:
            d["gapline"].set_data([], []); d["gaplab"].set_text("")
        if hit:
            d["boom"].set_data([xS - cam], [d["yc"]]); d["boom"].set_markersize(30 + 20 * min((t - c[0]) * 3, 1))
            d["stat"].set_text(f"IMPACT at {c[1]*3.6:.0f} km/h"); d["stat"].set_color("#FF8A80")
        elif vS <= 1e-6 and t > 0.1:
            d["stat"].set_text(f"stopped {gap:.1f} m short"); d["stat"].set_color("#7EE2A8")
        elif t < d["rt"]:
            d["stat"].set_text(f"{vS*3.6:5.1f} km/h · not braking yet"); d["stat"].set_color(INK)
        else:
            d["stat"].set_text(f"{vS*3.6:5.1f} km/h · braking {aS:.1f} m/s²"); d["stat"].set_color(INK)
    for (R, c), g, v in zip(runs, gl, vl):
        n = min(len(R), int(round(t / DT)) + 1)
        if c is not None:
            n = min(n, int(c[0] / DT) + 1)
        g.set_data(R[:n, 0], R[:n, 1] - R[:n, 2]); v.set_data(R[:n, 0], R[:n, 4] * 3.6)
    curG.set_xdata([t, t]); curV.set_xdata([t, t])

w = FFMpegWriter(fps=a.fps, codec="libx264", extra_args=["-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"])
with w.saving(fig, a.out, dpi=100):
    for f in range(n_frames):
        update(f); w.grab_frame()
print("wrote", a.out, n_frames, "frames", [(n, (c[0], c[1]*3.6) if c else None) for (n, *_), (_, c) in zip(lanes, runs)])
