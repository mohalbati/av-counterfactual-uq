"""
Supplementary figures for the report: workflow diagram, example time histories,
and Monte Carlo convergence.  python scripts/supplementary.py   (~20 s)
"""
import os, sys
import numpy as np
import pandas as pd
from scipy.stats import qmc, norm
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cfuq.models import EPI_NAMES, epistemic_from_unit, nominal, run, nieon_response_time
from cfuq.simulate import simulate_history, ramp_up_time
import cfuq.plots as plots
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = os.path.join(os.path.dirname(__file__), "..", "results")
res = pd.read_csv(os.path.join(OUT, "scenario_results.csv"))
plots.style()
BLUE, ORANGE, INK, INK2 = plots.BLUE, plots.ORANGE, plots.INK, plots.INK2
S = "S02"
r = res.set_index("id").loc[S]
sc = dict(v0=r.v0_ms, h=r.headway_s, aL=r.lead_decel_ms2)

# ---------------------------------------------------------------- fig0 workflow
fig, ax = plt.subplots(figsize=(10, 3.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.6); ax.axis("off")
def box(x, y, w, h, t, fc="#e8eef8", ec="#1F3864", ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06", fc=fc, ec=ec, ls=ls, lw=1.1))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=8.2, color=INK)
def arr(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10, color=INK2, lw=1))
box(0.1, 1.45, 1.9, 1.0, "Epistemic inputs θ\n(reconstruction,\nmodel parameters)\nouter loop, 512 QMC", fc="#f3f2ee")
box(2.5, 2.6, 1.9, 0.85, "Aleatory input z\n(response-time scatter)\ninner loop, 200 draws", fc="#f3f2ee")
box(2.5, 1.45, 1.9, 1.0, "Scenario physics\nlead braking,\nlooming → RUT\n(Eqs. 1-6)")
box(4.75, 2.35, 1.9, 1.0, "Reference driver\nRT = (m + k·RUT)·ε\njerk-limited braking\n(Eqs. 7-12)")
box(4.75, 0.55, 1.9, 1.0, "Generic ADS\nfixed latency\njerk-limited braking\n(Eq. 13)")
box(7.0, 1.45, 1.35, 1.0, "Outcome\ncollision, closing\nspeed, P(MAIS3+)\n(Eqs. 14-18)")
box(8.6, 2.35, 1.35, 1.0, "P(collision | θ)\nper scenario\n(Eqs. 19-21)", fc="#fde8e4", ec="#c0392b")
box(8.6, 0.55, 1.35, 1.0, "Counts, flip prob.,\nSobol indices\n(Eqs. 22-27)", fc="#fde8e4", ec="#c0392b")
arr(2.0, 1.95, 2.5, 1.95); arr(4.4, 3.02, 4.75, 3.02)
arr(4.4, 2.1, 4.75, 2.75); arr(4.4, 1.8, 4.75, 1.15)
arr(6.65, 2.85, 7.0, 2.1); arr(6.65, 1.05, 7.0, 1.8)
arr(8.35, 2.1, 8.6, 2.75); arr(8.35, 1.8, 8.6, 1.15)
ax.text(5.0, 0.15, "θ also supplies the reference-driver, ADS and injury-model parameters.  Deterministic practice = one pass with θ at nominal values and no residual (the 'mean driver')",
        ha="center", fontsize=8.4, color=INK2, style="italic")
fig.savefig(os.path.join(OUT, "fig0_workflow.png")); plt.close(fig)

# ---------------------------------------------------- fig6 example time histories
e0 = nominal(sc)
rut0 = ramp_up_time(np.array([sc["v0"]]), np.array([sc["h"]]), np.array([sc["aL"]]), np.array([e0["lead_jerk"]]))[0]
rt0 = nieon_response_time(np.array([rut0]), e0["rt_m"], e0["rt_k"], e0["rt_cv"])[0]
U = qmc.Sobol(d=len(EPI_NAMES), scramble=True, seed=7).random(64)[:40]
E = epistemic_from_unit(U, sc)
z = np.random.default_rng(7).standard_normal(40)
fig, axs = plt.subplots(1, 2, figsize=(9.6, 3.5))
for i in range(40):
    rut = ramp_up_time(E["speed"][i:i+1], E["headway"][i:i+1], E["lead_decel"][i:i+1], E["lead_jerk"][i:i+1])
    rt = nieon_response_time(rut, E["rt_m"][i], E["rt_k"][i], E["rt_cv"][i], z[i:i+1])[0]
    t, g, vs, vl = simulate_history(E["speed"][i], E["headway"][i], E["lead_decel"][i], E["lead_jerk"][i],
                                    rt, E["nieon_amax"][i], E["nieon_jerk"][i])
    axs[0].plot(t, g, color=BLUE, lw=0.7, alpha=0.35)
    if g[-1] <= 0: axs[0].plot(t[-1], 0, "x", color=BLUE, ms=4, alpha=0.7)
t, g, vs, vl = simulate_history(sc["v0"], sc["h"], sc["aL"], e0["lead_jerk"], rt0, e0["nieon_amax"], e0["nieon_jerk"])
axs[0].plot(t, g, color=INK, lw=2, label=f"Deterministic NIEON (RT = {rt0:.2f} s)")
ta, ga, vsa, vla = simulate_history(sc["v0"], sc["h"], sc["aL"], e0["lead_jerk"], e0["ads_latency"], e0["ads_amax"], e0["ads_jerk"])
axs[0].plot(ta, ga, color=ORANGE, lw=2, label=f"Deterministic generic ADS (latency {e0['ads_latency']:.2f} s)")
axs[0].plot([], [], color=BLUE, lw=1, alpha=0.6, label="40 sampled NIEON realizations (x = contact)")
axs[0].set_xlabel("Time after lead vehicle starts braking (s)"); axs[0].set_ylabel("Gap to lead vehicle (m)")
axs[0].set_ylim(bottom=-1); axs[0].legend(fontsize=7.6, loc="upper right")
axs[0].set_title(f"(a) Gap, scenario {S}", loc="left")
axs[1].plot(t, vl * 3.6, color=INK2, lw=1.6, ls="--", label="Lead vehicle")
axs[1].plot(t, vs * 3.6, color=INK, lw=2, label="NIEON (deterministic)")
axs[1].plot(ta, vsa * 3.6, color=ORANGE, lw=2, label="Generic ADS (deterministic)")
axs[1].axvline(rut0, color=BLUE, lw=1, ls=":"); axs[1].text(rut0 + 0.05, 10, f"T2: looming\nreaches 0.05 rad/s\n(RUT = {rut0:.2f} s)", fontsize=7.4, color=INK2)
axs[1].set_xlabel("Time after lead vehicle starts braking (s)"); axs[1].set_ylabel("Speed (km/h)")
axs[1].legend(fontsize=7.6, loc="upper right"); axs[1].set_title("(b) Speeds, deterministic runs", loc="left")
fig.tight_layout(); fig.savefig(os.path.join(OUT, "fig6_time_histories.png")); plt.close(fig)

# ---------------------------------------------------------- fig7 convergence
NO, NI = 2048, 200
U = qmc.Sobol(d=len(EPI_NAMES), scramble=True, seed=11).random(NO)
e = epistemic_from_unit(U, sc)
Ex = {k: np.repeat(v, NI) for k, v in e.items()}
rn = run(Ex, np.random.default_rng(11).standard_normal(NO * NI), "nieon")
pc = rn["collided"].reshape(NO, NI).mean(1)
ns = np.unique(np.round(np.logspace(np.log10(16), np.log10(NO), 30)).astype(int))
fig, ax = plt.subplots(figsize=(6.4, 3.2))
ax.plot(ns, [pc[:n].mean() for n in ns], color=BLUE, lw=2, label="mean P(collision)")
ax.plot(ns, [np.quantile(pc[:n], .05) for n in ns], color=BLUE, lw=1.2, ls="--", label="5th / 95th percentile")
ax.plot(ns, [np.quantile(pc[:n], .95) for n in ns], color=BLUE, lw=1.2, ls="--")
ax.axvline(512, color=INK2, lw=1, ls=":"); ax.text(540, 0.05, "N used in study (512)", fontsize=8, color=INK2)
ax.set_xscale("log"); ax.set_ylim(0, 1); ax.set_xlabel("Number of epistemic samples (outer loop)")
ax.set_ylabel("P(collision)"); ax.legend(fontsize=8.2, loc="center right")
ax.set_title(f"Convergence of the outer loop, scenario {S}", loc="left")
fig.savefig(os.path.join(OUT, "fig7_convergence.png")); plt.close(fig)
conv = pd.DataFrame({"n_outer": ns, "mean": [pc[:n].mean() for n in ns],
                     "p05": [np.quantile(pc[:n], .05) for n in ns], "p95": [np.quantile(pc[:n], .95) for n in ns]})
conv.to_csv(os.path.join(OUT, "convergence_S02.csv"), index=False)
print("rut0 %.3f rt0 %.3f" % (rut0, rt0)); print(conv.tail(4).round(3).to_string(index=False))
print("mean at 512: %.3f, at 2048: %.3f" % (pc[:512].mean(), pc.mean()))
