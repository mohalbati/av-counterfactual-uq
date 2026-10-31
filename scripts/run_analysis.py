"""
Run all analyses and write results/ (CSV tables + PNG figures).

  python scripts/run_analysis.py            # full run (~2-4 min)
  python scripts/run_analysis.py --quick    # small sample sizes for testing
"""
import sys, os, json, time
import numpy as np
import pandas as pd
from scipy.stats import qmc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cfuq import parameters as P
from cfuq.models import EPI_NAMES, GROUP, epistemic_from_unit, nominal, run
from cfuq.sobol import sobol_indices
import cfuq.plots as plots

QUICK = "--quick" in sys.argv
OUT = os.path.join(os.path.dirname(__file__), "..", "results")
os.makedirs(OUT, exist_ok=True)
SEED = 2026
N_OUTER = 64 if QUICK else 512      # epistemic samples (scrambled Sobol QMC)
N_INNER = 32 if QUICK else 200      # aleatory response-time draws
N_COUNT = 500 if QUICK else 4000    # realizations for scenario-set counts
N_SOBOL = 2**9 if QUICK else 2**13  # Saltelli base sample size
t0 = time.time()

# ------------------------------------------------------------------ scenarios
# 16 synthetic 'reconstructed' rear-end conflicts (lead vehicle brakes hard).
# They stand in for police-report reconstructions; they are NOT real cases.
lhs = qmc.LatinHypercube(d=3, seed=SEED).random(16)
lo, hi = np.array([11.0, 0.3, 5.5]), np.array([31.0, 1.6, 9.5])   # v0 m/s, h s, aL m/s^2
X = lo + lhs * (hi - lo)
scen = pd.DataFrame({"id": [f"S{i+1:02d}" for i in range(16)],
                     "v0_ms": X[:, 0].round(1), "headway_s": X[:, 1].round(2),
                     "lead_decel_ms2": X[:, 2].round(2)})
scen["v0_kph"] = (scen.v0_ms * 3.6).round(0)
SC = [dict(v0=r.v0_ms, h=r.headway_s, aL=r.lead_decel_ms2) for r in scen.itertuples()]


def arr(e, n):
    return {k: np.full(n, v, float) for k, v in e.items()}


# ------------------------------------------------------- 1. deterministic
det = []
for s, sc in zip(scen.id, SC):
    e = arr(nominal(sc), 1)
    rn, ra = run(e, None, "nieon"), run(e, None, "ads")
    det.append(dict(id=s, nieon_collides=bool(rn["collided"][0]), nieon_closing_kph=rn["closing_speed"][0] * 3.6,
                    nieon_rt_s=rn["rt"][0], nieon_rut_s=rn["rut"][0], nieon_min_gap_m=rn["min_gap"][0],
                    ads_collides=bool(ra["collided"][0]), ads_closing_kph=ra["closing_speed"][0] * 3.6,
                    ads_min_gap_m=ra["min_gap"][0]))
det = pd.DataFrame(det)

# ------------------------------------------- 2. two-loop Monte Carlo per scenario
sob = qmc.Sobol(d=len(EPI_NAMES), scramble=True, seed=SEED)
U = sob.random(N_OUTER)
rng = np.random.default_rng(SEED)
rows, curves = [], {}
for s, sc in zip(scen.id, SC):
    e = epistemic_from_unit(U, sc)
    E = {k: np.repeat(v, N_INNER) for k, v in e.items()}          # outer x inner
    z = rng.standard_normal(N_OUTER * N_INNER)
    rn = run(E, z, "nieon")
    pc_n = rn["collided"].reshape(N_OUTER, N_INNER).mean(1)       # P(collision | epistemic)
    pinj_n = rn["p_mais3"].reshape(N_OUTER, N_INNER).mean(1)
    rm = run(e, None, "nieon")                       # 'mean driver' view: residual off
    pc_m = rm["collided"].astype(float)
    ra = run(e, np.zeros(N_OUTER), "ads")                         # ADS: no aleatory part
    pc_a = ra["collided"].astype(float)
    d = det.set_index("id").loc[s]
    flip_n = (1 - pc_n) if d.nieon_collides else pc_n
    rows.append(dict(id=s,
        nieon_p_coll_mean=pc_n.mean(), nieon_p_coll_p05=np.quantile(pc_n, .05),
        nieon_p_coll_p50=np.quantile(pc_n, .5), nieon_p_coll_p95=np.quantile(pc_n, .95),
        nieon_p_flip=flip_n.mean(), nieon_p_mais3_mean=pinj_n.mean(), nieon_p_mais3_p95=np.quantile(pinj_n, .95),
        nieon_mean_driver_p_coll=pc_m.mean(),
        nieon_mean_driver_p_flip=((1 - pc_m) if d.nieon_collides else pc_m).mean(),
        ads_p_coll=pc_a.mean(),
        p_ads_avoids_nieon_collides=(((1 - pc_a) * pc_n)).mean(),
        p_ads_collides_nieon_avoids=((pc_a * (1 - pc_n))).mean()))
    curves[s] = np.sort(pc_n)
mc = pd.DataFrame(rows)
res = scen.merge(det, on="id").merge(mc, on="id")
res.round(4).to_csv(os.path.join(OUT, "scenario_results.csv"), index=False)

# ----------------------------------- 3. scenario-set counts (like 12/16 vs 10/16)
# Model parameters are shared across scenarios within one realization (one
# 'state of knowledge'); reconstruction errors are independent per scenario.
cnt = np.zeros((N_COUNT, 3), int)
Um = qmc.Sobol(d=len(EPI_NAMES), scramble=True, seed=SEED + 1).random(N_COUNT)
for j, sc in enumerate(SC):
    Ur = Um.copy()
    Ur[:, :4] = rng.random((N_COUNT, 4))        # independent reconstruction error
    e = epistemic_from_unit(Ur, sc)
    cnt[:, 0] += ~run(e, rng.standard_normal(N_COUNT), "nieon")["collided"]
    cnt[:, 1] += ~run(e, np.zeros(N_COUNT), "ads")["collided"]
    cnt[:, 2] += ~run(e, None, "nieon")["collided"]
det_counts = dict(nieon=int((~det.nieon_collides).sum()), ads=int((~det.ads_collides).sum()))
counts = pd.DataFrame({"nieon_avoided": cnt[:, 0], "ads_avoided": cnt[:, 1], "nieon_mean_driver_avoided": cnt[:, 2]})
counts.to_csv(os.path.join(OUT, "scenario_set_counts.csv"), index=False)

# --------- 3b. which uncertainty matters for the count? (mean-driver view, no residual)
REC = ["speed", "headway", "lead_decel", "lead_jerk"]
MODEL = ["rt_m", "rt_k", "rt_cv", "nieon_amax", "nieon_jerk", "ads_latency", "ads_amax", "ads_jerk", "inj_r50"]
variants = {"reconstruction only": dict(fix=MODEL), "reconstruction only, half-width ranges": dict(fix=MODEL, rec_scale=0.5),
            "NIEON/ADS model only": dict(fix=REC), "both": dict()}
var_rows = []
for vname, kw in variants.items():
    cn = np.zeros(N_COUNT, int); ca = np.zeros(N_COUNT, int)
    for j, sc in enumerate(SC):
        Ur = Um.copy(); Ur[:, :4] = rng.random((N_COUNT, 4))
        e = epistemic_from_unit(Ur, sc, **kw)
        cn += ~run(e, None, "nieon")["collided"]
        ca += ~run(e, np.zeros(N_COUNT), "ads")["collided"]
    var_rows.append(dict(variant=vname, nieon_p05=int(np.quantile(cn, .05)), nieon_p50=int(np.quantile(cn, .5)),
                         nieon_p95=int(np.quantile(cn, .95)), ads_p05=int(np.quantile(ca, .05)),
                         ads_p50=int(np.quantile(ca, .5)), ads_p95=int(np.quantile(ca, .95)),
                         p_nieon_equals_deterministic=float((cn == det_counts["nieon"]).mean())))
variants_df = pd.DataFrame(var_rows)
variants_df.to_csv(os.path.join(OUT, "count_by_uncertainty_source.csv"), index=False)

# ---------------------------- 4. reference-model choice: which NIEON percentile?
refpct = []
for q in [0.10, 0.50, 0.90]:
    from scipy.stats import norm
    zq = norm.ppf(q)
    n_av = sum(int(~run(arr(nominal(sc), 1), np.array([zq]), "nieon")["collided"][0]) for sc in SC)
    refpct.append(dict(response_time_percentile=int(q * 100), nieon_avoided_of_16=n_av,
                       ads_avoided_of_16=det_counts["ads"]))
refpct = pd.DataFrame(refpct)
refpct.to_csv(os.path.join(OUT, "reference_percentile.csv"), index=False)

# ------------------------------------------------- 5. Sobol sensitivity
# Most uncertain scenario for the NIEON outcome (P(collision) closest to 0.5)
s_star = mc.iloc[(mc.nieon_p_coll_mean - 0.5).abs().argmin()].id
sc_star = SC[list(scen.id).index(s_star)]
names = EPI_NAMES[:9] + ["rt_residual"]          # NIEON-relevant inputs + aleatory residual
groups = {"reconstruction": names[0:4], "NIEON timing (model)": names[4:7],
          "NIEON braking (model)": names[7:9], "response-time variability (aleatory)": ["rt_residual"]}


def f_nieon(u):
    full = np.hstack([u[:, :9], np.full((u.shape[0], 4), 0.5)])
    e = epistemic_from_unit(full, sc_star)
    from scipy.stats import norm
    z = norm.ppf(np.clip(u[:, 9], 1e-6, 1 - 1e-6))
    r = run(e, z, "nieon")
    return {"closing_kph": r["closing_speed"] * 3.6, "collision": r["collided"].astype(float)}


sob_ind = sobol_indices(f_nieon, len(names), N_SOBOL, SEED, names=names, groups=groups)
sob_ind.to_csv(os.path.join(OUT, "sobol_indices.csv"), index=False)

# ------------------------------------------------- figures
plots.style()
plots.fig_example(SC, scen, mc, det, curves, s_star, OUT)
plots.fig_scenarios(res, OUT)
plots.fig_counts(counts, det_counts, OUT)
plots.fig_sobol(sob_ind, s_star, OUT)
plots.fig_sources(variants_df, refpct, det_counts, OUT)

summary = dict(
    runtime_s=round(time.time() - t0, 1), quick=QUICK, n_outer=N_OUTER, n_inner=N_INNER,
    n_count=N_COUNT, n_sobol_base=N_SOBOL, seed=SEED,
    rt_k_se_derived=round(float(P.RT_K_SE), 4),
    deterministic_avoided=det_counts,
    count_nieon_avoided_p05_p50_p95=[int(np.quantile(cnt[:, 0], q)) for q in (.05, .5, .95)],
    count_nieon_mean_driver_avoided_p05_p50_p95=[int(np.quantile(cnt[:, 2], q)) for q in (.05, .5, .95)],
    p_ads_more_avoided_than_nieon=float((cnt[:, 1] > cnt[:, 0]).mean()),
    p_ads_more_avoided_than_nieon_mean_driver=float((cnt[:, 1] > cnt[:, 2]).mean()),
    n_scenarios_mean_driver_flip_over_20pct=int((mc.nieon_mean_driver_p_flip > 0.2).sum()),
    count_ads_avoided_p05_p50_p95=[int(np.quantile(cnt[:, 1], q)) for q in (.05, .5, .95)],
    p_nieon_count_equals_deterministic=float((cnt[:, 0] == det_counts["nieon"]).mean()),
    n_scenarios_flip_prob_over_20pct=int((mc.nieon_p_flip > 0.2).sum()),
    most_uncertain_scenario=s_star,
    reference_percentile=refpct.to_dict("records"),
    count_by_uncertainty_source=variants_df.to_dict("records"))
json.dump(summary, open(os.path.join(OUT, "summary.json"), "w"), indent=2)
print(json.dumps(summary, indent=2))
