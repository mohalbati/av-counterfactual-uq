"""
Concept and explanation figures for the report and slides (results/concepts/).
    python scripts/concept_figures.py   (~30 s)
"""
import os, sys, json
import numpy as np
import pandas as pd
from scipy.stats import norm, lognorm, qmc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cfuq import parameters as P
from cfuq.models import nominal, nieon_response_time, epistemic_from_unit, run, EPI_NAMES
from cfuq.simulate import simulate_history, ramp_up_time, DT
import cfuq.plots as plots
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(ROOT, "results", "concepts"); os.makedirs(OUT, exist_ok=True)
plots.style()
BLUE, ORANGE, INK, INK2 = plots.BLUE, plots.ORANGE, plots.INK, plots.INK2
LBLUE, GREY, RED = "#86b6ef", "#a8a59c", "#c0392b"
res = pd.read_csv(os.path.join(ROOT, "results", "scenario_results.csv")).set_index("id")
s2 = res.loc["S02"]; sc2 = dict(v0=s2.v0_ms, h=s2.headway_s, aL=s2.lead_decel_ms2); e2 = nominal(sc2)
save = lambda fig, n: (fig.savefig(os.path.join(OUT, n)), plt.close(fig))

# ---------------- c01 the question: deterministic vs probabilistic
fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.0))
axs[0].bar(["avoided", "collision"], [0, 1], color=[GREY, INK], width=0.55)
axs[0].set_ylim(0, 1.15); axs[0].set_ylabel("Probability"); axs[0].set_title("(a) Deterministic answer: one run", loc="left")
axs[0].text(1, 1.04, "100%", ha="center", fontsize=9)
pc = s2.nieon_p_coll_mean
axs[1].bar(["avoided", "collision"], [1 - pc, pc], color=[LBLUE, BLUE], width=0.55)
axs[1].errorbar([1], [pc], yerr=[[pc - s2.nieon_p_coll_p05], [s2.nieon_p_coll_p95 - pc]], color=INK, capsize=6, lw=1.4)
axs[1].set_ylim(0, 1.15); axs[1].set_title("(b) Probabilistic answer: many runs", loc="left")
axs[1].text(1.32, pc, f"{pc:.0%}\n(90% range\n{s2.nieon_p_coll_p05:.0%}–{s2.nieon_p_coll_p95:.0%})", fontsize=8.5, va="center")
for a in axs: a.grid(axis="x", visible=False)
fig.suptitle("Same crash (scenario S02), same reference driver: 'collision' vs 'collision 57% of the time'", fontsize=10, x=0.02, ha="left", y=1.02)
save(fig, "c01_det_vs_prob.png")

# ---------------- c02 counterfactual simulation idea (schematic)
fig, ax = plt.subplots(figsize=(10, 3.0)); ax.set_xlim(0, 10); ax.set_ylim(0, 3); ax.axis("off")
def car(x, y, c, lab, w=0.9):
    ax.add_patch(FancyBboxPatch((x, y), w, 0.38, boxstyle="round,pad=0.02,rounding_size=0.08", fc=c, ec=INK, lw=0.8))
    ax.text(x + w / 2, y + 0.19, lab, ha="center", va="center", fontsize=7.5, color="white" if c != "#f3f2ee" else INK, weight="bold")
def road(y):
    ax.plot([0.1, 3.0], [y - 0.06, y - 0.06], color=GREY, lw=1); ax.plot([0.1, 3.0], [y + 0.44, y + 0.44], color=GREY, lw=1)
for i, (tit, sub, follower, col) in enumerate([("1. Real crash", "human follower hits\nbraking lead car", "human", INK),
                                               ("2. Replay with reference driver", "NIEON: attentive,\nsober human model", "NIEON", BLUE),
                                               ("3. Replay with the ADS", "automated driving\nsystem under test", "ADS", ORANGE)]):
    x0 = i * 3.35
    ax.text(x0 + 1.5, 2.75, tit, ha="center", fontsize=9.5, weight="bold", color=INK)
    y = 1.6; ax.plot([x0 + 0.1, x0 + 3.0], [y - 0.06] * 2, color=GREY, lw=1); ax.plot([x0 + 0.1, x0 + 3.0], [y + 0.44] * 2, color=GREY, lw=1)
    car(x0 + 0.3, y, col, follower); car(x0 + 1.9, y, "#52514e", "lead")
    ax.annotate("", xy=(x0 + 1.85, y + 0.19), xytext=(x0 + 1.25, y + 0.19), arrowprops=dict(arrowstyle="->", color=INK2))
    ax.text(x0 + 2.35, y + 0.62, "brakes!", fontsize=7.5, color=RED, ha="center")
    ax.text(x0 + 1.5, 0.95, sub, ha="center", va="top", fontsize=8, color=INK2)
    out = ["crash happened", "avoided? (yes/no)", "avoided? (yes/no)"][i]
    ax.text(x0 + 1.5, 0.25, out, ha="center", fontsize=8.5, color=[RED, BLUE, ORANGE][i], weight="bold")
ax.text(5, -0.15, "Benchmark: the ADS should avoid at least as many conflicts as the reference driver", ha="center", fontsize=8.8, color=INK, style="italic")
save(fig, "c02_counterfactual_idea.png")

# ---------------- c03 looming geometry + looming trace
fig, axs = plt.subplots(1, 2, figsize=(10, 3.3), gridspec_kw=dict(width_ratios=[1.1, 1]))
ax = axs[0]; ax.set_xlim(0, 10); ax.set_ylim(-2.2, 2.2); ax.axis("off")
ax.add_patch(Rectangle((8.2, -0.9), 0.6, 1.8, fc="#52514e", ec=INK)); ax.text(8.5, 1.15, "lead car\nwidth W", ha="center", fontsize=8)
ax.plot(0.8, 0, "o", color=BLUE, ms=8); ax.text(0.8, -0.5, "driver's eye", ha="center", fontsize=8)
ax.add_patch(Polygon([[0.8, 0], [8.2, 0.9], [8.2, -0.9]], fc=LBLUE, ec=BLUE, alpha=0.35))
ax.text(2.2, 0.0, "θ", fontsize=14, color=BLUE, va="center")
ax.annotate("", xy=(8.2, -1.6), xytext=(0.8, -1.6), arrowprops=dict(arrowstyle="<->", color=INK2)); ax.text(4.5, -1.95, "distance D", ha="center", fontsize=8.5)
ax.text(0.2, 1.75, "θ = 2·arctan(W / 2D)   (Eq. 4)\nAs the gap closes, θ grows. Its rate θ̇ is 'looming' (Eq. 5).", fontsize=8.5, color=INK)
ax.set_title("(a) What the following driver sees", loc="left")
ax = axs[1]
v0, h, aL, jL = sc2["v0"], sc2["h"], sc2["aL"], e2["lead_jerk"]
t = np.arange(0, 3.0, DT); x = h * v0; vL = v0; L = []
for ti in t:
    D = max(x, 0.01) + P.EYE_TO_BUMPER; L.append(P.LEAD_WIDTH * (v0 - vL) / (D**2 + P.LEAD_WIDTH**2 / 4))
    a = min(ti * jL, aL); vL2 = max(vL - a * DT, 0); x += (0.5 * (vL + vL2) - v0) * DT; vL = vL2
ax.plot(t, L, color=BLUE, lw=2); ax.axhline(P.LOOMING_THRESHOLD, color=RED, ls="--", lw=1.2)
ax.text(0.05, P.LOOMING_THRESHOLD - 0.008, "threshold 0.05 rad/s (Engström et al. 2024)", fontsize=8, color=RED)
rut = s2.nieon_rut_s; ax.axvline(rut, color=INK2, ls=":"); ax.annotate("", xy=(rut, 0.085), xytext=(0, 0.085), arrowprops=dict(arrowstyle="<->", color=INK))
ax.text(rut / 2, 0.089, f"RUT = {rut:.2f} s", ha="center", fontsize=9, weight="bold")
ax.set_ylim(0, 0.1); ax.set_xlabel("Time after lead car starts braking (s)"); ax.set_ylabel("Looming θ̇ (rad/s)")
ax.set_title("(b) Ramp-up time, scenario S02 (Eq. 6)", loc="left")
fig.tight_layout(); save(fig, "c03_looming_rut.png")

# ---------------- c04 response time model
fig, axs = plt.subplots(1, 2, figsize=(10, 3.5))
ax = axs[0]; ru = np.linspace(0, 3, 100)
rng = np.random.default_rng(3); ks = P.RT_K + P.RT_K_SE * rng.standard_normal(300); ms = P.RT_M + P.RT_M_SE * rng.standard_normal(300)
band = np.array([m + k * ru for m, k in zip(ms, ks)])
ax.fill_between(ru, np.quantile(band, .05, 0), np.quantile(band, .95, 0), color=LBLUE, alpha=0.5, label="parameter uncertainty (90%): epistemic")
ax.plot(ru, P.RT_M + P.RT_K * ru, color=BLUE, lw=2.2, label="published fit RT = 0.63 + 0.47·RUT")
rr = rng.uniform(0, 2.8, 120); s = np.sqrt(np.log(1 + 0.4**2))
ax.plot(rr, (P.RT_M + P.RT_K * rr) * np.exp(s * rng.standard_normal(120) - s * s / 2), ".", color=INK2, ms=3.5, alpha=0.6,
        label="simulated individual drivers: aleatory")
ax.plot(ru, np.full_like(ru, 1.25), color=ORANGE, ls="--", lw=1.4, label="classic fixed 1.25 s (Green 2000)")
ax.set_xlabel("Ramp-up time RUT (s)"); ax.set_ylabel("Response time RT (s)"); ax.set_ylim(0, 4.2)
ax.legend(fontsize=7.4, loc="upper left"); ax.set_title("(a) Response time depends on the situation (Eq. 7)", loc="left")
ax = axs[1]; xx = np.linspace(0.01, 3.5, 400); mu = P.RT_M + P.RT_K * s2.nieon_rut_s
for cv, ls in ((0.25, ":"), (0.40, "-"), (0.55, "--")):
    ss = np.sqrt(np.log(1 + cv**2)); d = lognorm(s=ss, scale=mu * np.exp(-ss * ss / 2))
    ax.plot(xx, d.pdf(xx), color=BLUE, ls=ls, lw=1.8, label=f"CV = {cv}")
ss = np.sqrt(np.log(1 + 0.4**2)); d = lognorm(s=ss, scale=mu * np.exp(-ss * ss / 2))
for p in (0.1, 0.5, 0.9):
    v = d.ppf(p); ax.axvline(v, color=INK2, lw=0.8, ls=":"); ax.text(v, ax.get_ylim()[1] * 0.0 + 1.25, f"{int(p*100)}th\n{v:.2f} s", fontsize=7.5, ha="center")
ax.axvline(mu, color=INK, lw=1.4); ax.text(mu + 0.06, 0.62, f"mean\n{mu:.2f} s", fontsize=7.5)
ax.set_ylim(0, 1.45); ax.set_xlabel(f"Response time for S02, RUT = {s2.nieon_rut_s:.2f} s"); ax.set_ylabel("Probability density")
ax.legend(fontsize=7.6, loc="upper right"); ax.set_title("(b) Driver-to-driver spread (Eq. 10)", loc="left")
fig.tight_layout(); save(fig, "c04_response_time_model.png")

# ---------------- c05 braking profile and stopping distance
fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
ax = axs[0]; t = np.linspace(0, 4, 800)
ax.plot(t, np.minimum(t * jL, aL), color="#52514e", lw=2, label=f"lead car (jerk {jL:.1f}, max {aL:.1f})")
rt = s2.nieon_rt_s; ax.plot(t, np.clip((t - rt) * e2["nieon_jerk"], 0, e2["nieon_amax"]), color=BLUE, lw=2, label=f"NIEON (starts at RT = {rt:.2f} s)")
ax.plot(t, np.clip((t - e2["ads_latency"]) * e2["ads_jerk"], 0, e2["ads_amax"]), color=ORANGE, lw=2, label=f"generic ADS (starts at {e2['ads_latency']:.2f} s)")
ax.set_xlabel("Time (s)"); ax.set_ylabel("Deceleration (m/s²)"); ax.legend(fontsize=7.6, loc="lower right")
ax.set_title("(a) Jerk-limited braking (Eqs. 1 and 11)", loc="left")
ax = axs[1]; v0 = 20.0; a = 7.5; j = 20.0
parts = []
for RT in (0.6, 1.0, 1.5):
    tj = a / j; dr = v0 * tj - j * tj**3 / 6; v1 = v0 - 0.5 * j * tj**2; parts.append((v0 * RT, dr, v1**2 / (2 * a)))
labs = ["RT 0.6 s", "RT 1.0 s", "RT 1.5 s"]; yy = np.arange(3)
for i, (a1, a2, a3) in enumerate(parts):
    ax.barh(i, a1, color=GREY, edgecolor="white"); ax.barh(i, a2, left=a1, color=LBLUE, edgecolor="white"); ax.barh(i, a3, left=a1 + a2, color=BLUE, edgecolor="white")
    ax.text(a1 + a2 + a3 + 0.8, i, f"{a1 + a2 + a3:.0f} m", va="center", fontsize=8.5)
ax.set_yticks(yy); ax.set_yticklabels(labs); ax.set_xlabel("Distance travelled at 72 km/h before stopping (m)")
ax.legend(["reaction (v·RT)", "brake build-up (jerk)", "full braking (v²/2a)"], fontsize=7.6, loc="lower right"); ax.set_xlim(0, 95)
ax.set_title("(b) Stopping distance parts (Eq. 12)", loc="left")
fig.tight_layout(); save(fig, "c05_braking_stopping.png")

# ---------------- c06 injury curve
fig, ax = plt.subplots(figsize=(6.6, 3.3)); dv = np.linspace(0, 140, 300)
for r50, ls in ((1.3, ":"), (1.55, "-"), (1.8, "--")):
    ax.plot(dv * 2, P.injury_risk(dv * 2 / 3.6, r50), color=BLUE, ls=ls, lw=1.8, label=f"R50 = {r50}")
ax.plot(126, 0.10, "o", color=RED, ms=7); ax.annotate("TARGET anchor:\n10% MAIS3+ at 126 km/h\nclosing speed (rear-end)", xy=(126, 0.1), xytext=(165, 0.03), fontsize=8, arrowprops=dict(arrowstyle="->", color=RED))
ax.axvspan(0, res.nieon_closing_kph.max(), color=GREY, alpha=0.2); ax.text(4, 0.9, "closing speeds\nseen in this\nstudy", fontsize=7.8, color=INK2)
ax.set_xlabel("Closing speed at impact (km/h)   [delta-v = closing speed / 2, Eq. 16]"); ax.set_ylabel("P(MAIS3+), struck occupant")
ax.legend(fontsize=8, loc="center right"); ax.set_title("Injury risk curve (Eqs. 16-18): anchor from data, slope assumed", loc="left")
save(fig, "c06_injury_curve.png")

# ---------------- c07 aleatory vs epistemic (family of curves)
fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
ax = axs[0]; xx = np.linspace(0, 4, 300)
for i in range(25):
    mu = 1.4 + 0.25 * rng.standard_normal(); cv = rng.uniform(0.25, 0.55); ss = np.sqrt(np.log(1 + cv**2))
    ax.plot(xx, lognorm(s=ss, scale=mu * np.exp(-ss**2 / 2)).cdf(xx), color=BLUE, lw=0.8, alpha=0.45)
ax.axvline(1.9, color=RED, ls="--", lw=1.2); ax.text(1.95, 0.08, "response time that\nstill avoids the crash", fontsize=7.8, color=RED)
ax.set_xlabel("Response time (s)"); ax.set_ylabel("Fraction of drivers who have\nresponded by time x")
ax.set_title("(a) Each curve = one state of knowledge (epistemic);\nshape of each curve = driver spread (aleatory)", loc="left", fontsize=9.5)
ax = axs[1]
ax.text(0.02, 0.95, "Aleatory (variability)", fontsize=10, weight="bold", color=BLUE, transform=ax.transAxes)
ax.text(0.02, 0.88, "Differences between individual drivers.\nReal, irreducible: more data describes it\nbetter but does not remove it.\nHere: the response-time residual z.", fontsize=8.6, transform=ax.transAxes, va="top")
ax.text(0.02, 0.45, "Epistemic (lack of knowledge)", fontsize=10, weight="bold", color=ORANGE, transform=ax.transAxes)
ax.text(0.02, 0.38, "What the crash really was, and what the model\nparameters really are. Reducible with better data.\nHere: speed, headway, braking, m, k, CV, ...", fontsize=8.6, transform=ax.transAxes, va="top")
ax.axis("off"); ax.set_title("(b) The PRA distinction (Helton et al. 2004; NUREG-1855)", loc="left", fontsize=9.5)
fig.tight_layout(); save(fig, "c07_aleatory_epistemic.png")

# ---------------- c08 nested Monte Carlo concept
fig, ax = plt.subplots(figsize=(10, 3.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.6); ax.axis("off")
ax.text(0.1, 3.35, "Outer loop: 512 epistemic samples θ₁…θ₅₁₂  (crash reconstruction + model parameters)", fontsize=9.5, weight="bold")
for i in range(5):
    y = 2.6 - i * 0.52; lab = f"θ{i+1}" if i < 4 else "θ512"
    ax.text(0.15, y + 0.1, lab, fontsize=9, color=ORANGE, weight="bold")
    outc = rng.random(20) < [0.85, 0.35, 0.6, 0.15, 0.55][i]
    for k in range(20):
        ax.add_patch(Rectangle((0.9 + k * 0.24, y), 0.2, 0.28, fc=(BLUE if outc[k] else "#e6e5e1"), ec="white"))
    ax.text(5.85, y + 0.1, f"→ P(coll. | θ) = {outc.mean():.2f}", fontsize=8.6)
    if i == 3: ax.text(3.0, y - 0.25, "⋮", fontsize=12, ha="center")
ax.text(0.9, 0.05, "Inner loop: 200 drivers per θ (only 20 drawn), blue = collision   (Eq. 19)", fontsize=8.5, color=INK2)
ax.add_patch(FancyBboxPatch((8.05, 0.6), 1.85, 2.3, boxstyle="round,pad=0.03", fc="#fde8e4", ec=RED))
ax.text(8.97, 2.65, "Result", ha="center", fontsize=9.5, weight="bold")
ax.text(8.97, 1.75, "512 probabilities\n↓\nmean, 5th, 95th\npercentile\n(Eq. 20)", ha="center", va="center", fontsize=8.6)
save(fig, "c08_nested_mc.png")

# ---------------- c09 Sobol concept
fig, axs = plt.subplots(1, 2, figsize=(10, 3.3))
ax = axs[0]; ax.set_xlim(0, 10); ax.set_ylim(0, 4); ax.axis("off")
from matplotlib.patches import Circle
for (cx, cy, c, lab) in ((3.2, 2.2, BLUE, "X₁ alone\n(S₁)"), (5.2, 2.2, ORANGE, "X₂ alone\n(S₂)")):
    ax.add_patch(Circle((cx, cy), 1.45, fc=c, alpha=0.3, ec=c)); ax.text(cx + (-0.6 if c == BLUE else 0.6), cy, lab, ha="center", va="center", fontsize=8.5)
ax.text(4.2, 2.2, "inter-\naction", ha="center", va="center", fontsize=8)
ax.text(4.2, 0.25, "Total effect of X₁ (S_T1) = X₁ alone + all its interactions", ha="center", fontsize=8.5)
ax.set_title("(a) Splitting the output variance (Eqs. 24-25)", loc="left")
ax = axs[1]
from cfuq.sobol import sobol_indices
import pandas as pd
sob = pd.read_csv(os.path.join(ROOT, "results", "sobol_indices.csv"))
g = sob[(sob.output == "collision") & (sob.kind == "group")].sort_values("ST")
y = np.arange(len(g))
ax.barh(y, g.S1.clip(lower=0), color=BLUE, label="first order (alone)")
ax.barh(y, g.ST - g.S1.clip(lower=0), left=g.S1.clip(lower=0), color=LBLUE, label="interactions")
ax.set_yticks(y); ax.set_yticklabels([s.replace(" (aleatory)", "\n(aleatory)").replace(" (model)", "\n(model)") for s in g.input], fontsize=8)
ax.set_xlabel("Share of variance, collision outcome, S02"); ax.legend(fontsize=7.8, loc="lower right")
ax.set_title("(b) Result: interactions dominate", loc="left")
fig.tight_layout(); save(fig, "c09_sobol_concept.png")

# ---------------- c10 literature timeline
fig, ax = plt.subplots(figsize=(10.5, 3.4)); ax.set_xlim(2010.5, 2027); ax.set_ylim(-2.4, 2.6); ax.axis("off")
ax.axhline(0, color=INK2, lw=1.2)
ev = [(2012, "Kusano & Gabler: FCW/AEB\nrear-end benefits", 1, GREY), (2016, "Markkula et al.: brake\ntiming depends on kinematics", -1, BLUE),
      (2016.2, "Kalra & Paddock (RAND):\nbillions of miles needed", 1.7, GREY), (2017, "Scanlon et al.: intersection\nADAS, probabilistic recon.", -1.8, GREY),
      (2019, "Bareiss et al.: LTAP/OD\nbenefit estimates", 1, GREY), (2020, "Webb et al.: Waymo\nsafety framework", -1, ORANGE),
      (2021, "Scanlon et al.: Waymo in\n72 fatal crashes; UQ out of scope", 1.7, ORANGE), (2022, "Kusano et al.: CAT,\n13,000+ scenarios vs NIEON", -1.8, ORANGE),
      (2023, "Favarò et al.: safety\ncase, confidence growth", 1, ORANGE), (2024, "Engström et al.: surprise-\nbased response timing", -1, BLUE),
      (2025, "Campolettano et al.:\nTARGET thresholds", 1.7, ORANGE), (2026, "Scanlon et al.: NIEON in\nfatal crashes; UQ still future work", -1.8, ORANGE)]
for yr, txt, yy, c in ev:
    ax.plot([yr, yr], [0, yy * 0.6], color=c, lw=1); ax.plot(yr, 0, "o", color=c, ms=6)
    ax.text(yr, yy * 0.68, txt, ha="center", va="bottom" if yy > 0 else "top", fontsize=7.4)
for yr in range(2012, 2027, 2): ax.text(yr, -0.18, str(yr), ha="center", va="top", fontsize=7.5, color=INK2)
ax.text(2010.6, 2.45, "grey: driver-assistance & statistics   orange: Waymo safety research   blue: human response timing", fontsize=7.8, color=INK2)
save(fig, "c10_literature_timeline.png")

# ---------------- c11 worked example numbers
s = s2; rt = s.nieon_rt_s; v0 = s.v0_ms; ss = np.sqrt(np.log(1 + 0.4**2))
t, gg, vs, vl = simulate_history(v0, s.headway_s, s.lead_decel_ms2, e2["lead_jerk"], rt, e2["nieon_amax"], e2["nieon_jerk"])
W = dict(v0_kph=s.v0_kph, h=s.headway_s, x0=gg[0], aL=s.lead_decel_ms2, jL=e2["lead_jerk"], rut=s.nieon_rut_s, rt=rt,
         gap_at_rt=gg[int(round(rt / DT))], t_contact=t[-1], vc=s.nieon_closing_kph, dv=s.nieon_closing_kph / 2,
         pinj=float(P.injury_risk(np.array([s.nieon_closing_kph / 3.6]), 1.55)[0]),
         rt10=float(lognorm(s=ss, scale=(P.RT_M + P.RT_K * s.nieon_rut_s) * np.exp(-ss**2 / 2)).ppf(0.1)),
         rt90=float(lognorm(s=ss, scale=(P.RT_M + P.RT_K * s.nieon_rut_s) * np.exp(-ss**2 / 2)).ppf(0.9)))
json.dump({k: float(v) for k, v in W.items()}, open(os.path.join(ROOT, "results", "worked_example_S02.json"), "w"), indent=1)
print(json.dumps({k: round(float(v), 3) for k, v in W.items()}))
