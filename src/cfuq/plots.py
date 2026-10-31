"""Figures. Palette: validated default categorical slots 1 (blue) and 2 (orange)."""
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BLUE, ORANGE = "#2a78d6", "#eb6834"      # NIEON reference, generic ADS
INK, INK2, GRID = "#1b1b1a", "#52514e", "#e6e5e1"


def style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": INK2,
        "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.titlesize": 10.5, "axes.titleweight": "bold", "legend.frameon": False,
        "savefig.dpi": 200, "savefig.bbox": "tight"})


def fig_example(SC, scen, mc, det, curves, s, out):
    c = curves[s]
    d = det.set_index("id").loc[s]
    r = scen.set_index("id").loc[s]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.step(c, np.arange(1, c.size + 1) / c.size, where="post", color=BLUE, lw=2,
            label="Probabilistic: P(collision) under each state of knowledge")
    xdet = 1.0 if d.nieon_collides else 0.0
    ax.axvline(xdet, color=INK, lw=1.5, ls="--")
    ax.text(xdet + (-0.02 if xdet else 0.02), 0.08,
            "Deterministic point estimate:\n" + ("collision" if xdet else "no collision"),
            ha="right" if xdet else "left", va="bottom", color=INK, fontsize=8.5)
    m = mc.set_index("id").loc[s]
    ax.axvline(m.nieon_p_coll_mean, color=BLUE, lw=1, ls=":")
    ax.text(m.nieon_p_coll_mean + 0.015, 0.55, f"mean P = {m.nieon_p_coll_mean:.2f}", color=INK2,
            ha="left", va="center", fontsize=8.5)
    ax.set_xlim(-0.02, 1.02); ax.set_ylim(0, 1.08)
    ax.set_xlabel("Probability that the NIEON reference driver collides")
    ax.set_ylabel("Cumulative fraction of\nepistemic samples")
    ax.set_title(f"Scenario {s}: {r.v0_kph:.0f} km/h, {r.headway_s:.2f} s headway, "
                 f"lead braking {r.lead_decel_ms2:.1f} m/s²", loc="left")
    ax.legend(loc="upper left", fontsize=8.5)
    fig.savefig(os.path.join(out, "fig1_example_epistemic_cdf.png")); plt.close(fig)


def fig_scenarios(res, out):
    r = res.sort_values("nieon_p_coll_mean").reset_index(drop=True)
    x = np.arange(len(r))
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.vlines(x - 0.12, r.nieon_p_coll_p05, r.nieon_p_coll_p95, color=BLUE, lw=2)
    ax.plot(x - 0.12, r.nieon_p_coll_mean, "o", color=BLUE, ms=6, mec="white", mew=1.2,
            label="NIEON reference: mean P(collision), 5-95% epistemic range")
    ax.plot(x + 0.12, r.ads_p_coll, "s", color=ORANGE, ms=6, mec="white", mew=1.2,
            label="Generic ADS: P(collision) over epistemic samples")
    dn = r.nieon_collides.astype(float)
    ax.plot(x - 0.12, dn, "o", mfc="none", mec=INK, ms=9, mew=1.2,
            label="NIEON deterministic point estimate (0 = avoided, 1 = collision)")
    ax.set_xticks(x); ax.set_xticklabels(r.id, rotation=0, fontsize=8)
    ax.set_ylim(-0.06, 1.42); ax.set_yticks([0, 0.2, 0.4, 0.6, 0.8, 1.0]); ax.set_ylabel("P(collision)")
    ax.set_xlabel("Synthetic reconstructed rear-end conflicts, sorted by NIEON mean P(collision)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_title("Deterministic verdicts versus probabilistic outcomes, 16 scenarios", loc="left")
    fig.savefig(os.path.join(out, "fig2_scenarios_det_vs_prob.png")); plt.close(fig)


def fig_counts(counts, det_counts, out):
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    bins = np.arange(-0.5, 17.5, 1)
    for col, color, lab, key in (("nieon_avoided", BLUE, "NIEON reference", "nieon"),
                                 ("ads_avoided", ORANGE, "Generic ADS", "ads")):
        h, _ = np.histogram(counts[col], bins=bins)
        ax.bar(np.arange(17) + (-0.2 if key == "nieon" else 0.2), h / h.sum(), width=0.38,
               color=color, label=f"{lab} (probabilistic)", edgecolor="white", linewidth=1)
        ax.axvline(det_counts[key], color=color, lw=1.5, ls="--",
                   label=f"{lab} deterministic point estimate: {det_counts[key]}/16")
    ax.set_xticks(range(0, 17, 2)); ax.set_xlim(-0.8, 16.8)
    ax.set_xlabel("Number of the 16 conflicts in which the collision is avoided")
    ax.set_ylabel("Probability")
    ax.legend(loc="upper left", fontsize=8.5)
    ax.set_title("A count such as '10 of 16 avoided' is itself uncertain", loc="left")
    fig.savefig(os.path.join(out, "fig3_avoided_counts.png")); plt.close(fig)


def fig_sobol(df, s, out):
    g = df[(df.output == "collision") & (df.kind == "group")].copy()
    g = g.sort_values("ST")
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    y = np.arange(len(g))
    ax.barh(y + 0.18, g.ST, height=0.34, color=BLUE, label="Total effect (incl. interactions)")
    ax.errorbar(g.ST, y + 0.18, xerr=[g.ST - g.ST_lo, g.ST_hi - g.ST], fmt="none", ecolor=INK2, lw=1)
    ax.barh(y - 0.18, g.S1.clip(lower=0), height=0.34, color="#86b6ef", label="First order")
    ax.set_yticks(y); ax.set_yticklabels(g.input)
    ax.set_xlim(0, max(1.0, float(g.ST_hi.max()) * 1.05))
    ax.set_xlabel("Share of variance in the collision outcome (Sobol index)")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title(f"What drives the uncertainty? Scenario {s}", loc="left")
    fig.savefig(os.path.join(out, "fig4_sobol_groups.png")); plt.close(fig)


def fig_sources(variants_df, refpct, det_counts, out):
    fig, ax = plt.subplots(figsize=(6.6, 3.2))
    rows = list(variants_df.itertuples())
    labels = [r.variant for r in rows] + [f"reference driver = {int(p)}th-percentile response time"
                                          for p in refpct.response_time_percentile]
    y = np.arange(len(labels))[::-1]
    for yi, r in zip(y[:len(rows)], rows):
        ax.plot([r.nieon_p05, r.nieon_p95], [yi, yi], color=BLUE, lw=3, solid_capstyle="round")
        ax.plot(r.nieon_p50, yi, "o", color=BLUE, ms=7, mec="white", mew=1.2)
    for yi, r in zip(y[len(rows):], refpct.itertuples()):
        ax.plot(r.nieon_avoided_of_16, yi, "D", color=BLUE, ms=6, mec="white", mew=1.2)
    ax.axvline(det_counts["nieon"], color=INK, lw=1.2, ls="--")
    ax.text(det_counts["nieon"] + 0.2, y[0] + 0.55, f"deterministic: {det_counts['nieon']}/16",
            fontsize=8.2, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8.3)
    ax.set_xlim(-0.5, 16.5); ax.set_ylim(y[-1] - 0.7, y[0] + 1.0)
    ax.set_xlabel("NIEON collisions avoided out of 16 (median and 5-95% range)")
    ax.set_title("Which uncertainty moves the benchmark count?", loc="left")
    fig.savefig(os.path.join(out, "fig5_count_by_source.png")); plt.close(fig)
