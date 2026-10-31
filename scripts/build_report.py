"""
Fill docs/report_template.md with numbers read from results/ and write
docs/technical_report.md. Every number in the report comes from the result
files, so the report cannot drift from the code.   python scripts/build_report.py
"""
import os, sys, json, re
import numpy as np
import pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cfuq.models import nominal
from cfuq.simulate import simulate_history

ROOT = os.path.join(os.path.dirname(__file__), "..")
R = lambda f: os.path.join(ROOT, "results", f)
summ = json.load(open(R("summary.json")))
res = pd.read_csv(R("scenario_results.csv"))
cnt = pd.read_csv(R("scenario_set_counts.csv"))
sob = pd.read_csv(R("sobol_indices.csv"))
src = pd.read_csv(R("count_by_uncertainty_source.csv"))
ref = pd.read_csv(R("reference_percentile.csv"))
conv = pd.read_csv(R("convergence_S02.csv"))

q = lambda s, p: int(np.quantile(s, p))
f2 = lambda x: f"{x:.2f}"
V = {}
V["N_SCEN"] = len(res)
V["DET_N"] = summ["deterministic_avoided"]["nieon"]
V["DET_ADS"] = summ["deterministic_avoided"]["ads"]
V["DET_COLL"] = int(res.nieon_collides.sum())
V["FLIP_N"] = summ["n_scenarios_flip_prob_over_20pct"]
V["FLIP_MD_N"] = summ["n_scenarios_mean_driver_flip_over_20pct"]
V["FLIP_MAX"] = f2(res.nieon_p_flip.max())
V["CNT_P05"], V["CNT_P50"], V["CNT_P95"] = (q(cnt.nieon_avoided, p) for p in (.05, .5, .95))
V["CNT_MEAN"] = f"{cnt.nieon_avoided.mean():.1f}"
V["MD_P05"], V["MD_P50"], V["MD_P95"] = (q(cnt.nieon_mean_driver_avoided, p) for p in (.05, .5, .95))
V["MD_MEAN"] = f"{cnt.nieon_mean_driver_avoided.mean():.1f}"
V["ADS_P05"], V["ADS_P50"], V["ADS_P95"] = (q(cnt.ads_avoided, p) for p in (.05, .5, .95))
V["ADS_MEAN"] = f"{cnt.ads_avoided.mean():.1f}"
V["P_EQ"] = f2((cnt.nieon_avoided == V["DET_N"]).mean())
V["P_EQ_MD"] = f2((cnt.nieon_mean_driver_avoided == V["DET_N"]).mean())
V["P_ADS_GT"] = f"{100 * (cnt.ads_avoided > cnt.nieon_avoided).mean():.1f}%"
V["P_ADS_GT_MD"] = f"{100 * (cnt.ads_avoided > cnt.nieon_mean_driver_avoided).mean():.1f}%"
for p in (10, 50, 90):
    V[f"REF{p}"] = int(ref.set_index("response_time_percentile").loc[p, "nieon_avoided_of_16"])
s_by = src.set_index("variant")
V["REC_P05"], V["REC_P95"] = s_by.loc["reconstruction only", ["nieon_p05", "nieon_p95"]]
V["REC_H_P05"], V["REC_H_P95"] = s_by.loc["reconstruction only, half-width ranges", ["nieon_p05", "nieon_p95"]]
V["MOD_P05"], V["MOD_P95"] = s_by.loc["NIEON/ADS model only", ["nieon_p05", "nieon_p95"]]
coll = res[res.nieon_collides]; av = res[~res.nieon_collides]
V["COLL_MIN"], V["COLL_MAX"] = f2(coll.nieon_p_coll_mean.min()), f2(coll.nieon_p_coll_mean.max())
V["AV_MIN"], V["AV_MAX"] = f2(av.nieon_p_coll_mean.min()), f2(av.nieon_p_coll_mean.max())
V["ADS_MAX"] = f2(res.ads_p_coll.max())
V["ADS_LOW_N"] = int((res.ads_p_coll <= 0.01 + 1e-9).sum())
V["INJ_MAX"] = f"{100 * res.nieon_p_mais3_mean.max():.1f}%"
V["INJ_P95"] = f"{100 * res.nieon_p_mais3_p95.max():.1f}%"
V["VC_MAX"] = f"{res.nieon_closing_kph.max():.0f}"
S = summ["most_uncertain_scenario"]; V["SOBOL_S"] = S
g = sob.set_index(["output", "input"])
V["ST_RES"] = f2(g.loc[("collision", "rt_residual"), "ST"])
V["ST_RES_V"] = f2(g.loc[("closing_kph", "rt_residual"), "ST"])
V["ST_RTK"] = f2(g.loc[("collision", "rt_k"), "ST"])
V["ST_AL"] = f2(g.loc[("collision", "lead_decel"), "ST"])
V["ST_V0"] = f2(g.loc[("collision", "speed"), "ST"])
ind = sob[sob.kind == "input"]
V["SUM_S1"] = f2(ind[ind.output == "collision"].S1.clip(lower=0).sum())
V["SUM_S1_V"] = f2(ind[ind.output == "closing_kph"].S1.clip(lower=0).sum())
r2 = res.set_index("id").loc["S02"]
V["S02_RUT"], V["S02_RT"] = f2(r2.nieon_rut_s), f2(r2.nieon_rt_s)
V["S02_VC"] = f"{r2.nieon_closing_kph:.0f}"
V["S02_MEAN"], V["S02_P05"], V["S02_P95"] = f2(r2.nieon_p_coll_mean), f2(r2.nieon_p_coll_p05), f2(r2.nieon_p_coll_p95)
e = nominal(dict(v0=r2.v0_ms, h=r2.headway_s, aL=r2.lead_decel_ms2))
t, gg, _, _ = simulate_history(r2.v0_ms, r2.headway_s, r2.lead_decel_ms2, e["lead_jerk"], r2.nieon_rt_s, e["nieon_amax"], e["nieon_jerk"])
V["S02_X0"] = f"{gg[0]:.0f}"; V["S02_GAPRT"] = f"{gg[int(round(r2.nieon_rt_s / 0.005))]:.0f}"; V["S02_TC"] = f"{t[-1]:.1f}"
_, ga, _, _ = simulate_history(r2.v0_ms, r2.headway_s, r2.lead_decel_ms2, e["lead_jerk"], e["ads_latency"], e["ads_amax"], e["ads_jerk"])
V["S02_ADSGAP"] = f"{ga.min():.0f}"
V["CONV_512"] = f"{conv.iloc[(conv.n_outer - 512).abs().argmin()]['mean']:.3f}"
V["CONV_2048"] = f"{conv.iloc[-1]['mean']:.3f}"

W = json.load(open(R("worked_example_S02.json")))
V.update(W_V0=f"{W['v0_kph']:.0f}", W_H=f"{W['h']:.2f}", W_X0=f"{W['x0']:.1f}", W_JL=f"{W['jL']:.1f}", W_AL=f"{W['aL']:.2f}",
         W_RUT=f"{W['rut']:.2f}", W_RT=f"{W['rt']:.2f}", W_REACTD=f"{W['v0_kph'] / 3.6 * W['rt']:.1f}",
         W_GAPRT=f"{W['gap_at_rt']:.1f}", W_SHRINK=f"{W['x0'] - W['gap_at_rt']:.1f}", W_TC=f"{W['t_contact']:.2f}",
         W_VC=f"{W['vc']:.1f}", W_DV=f"{W['dv']:.1f}", W_PINJ=f"{100 * W['pinj']:.1f}%", W_RT10=f"{W['rt10']:.2f}", W_RT90=f"{W['rt90']:.2f}")
import cfuq.parameters as PP
JS = json.load(open(R("simulators/verification_js.json")))
V.update(JS_RUT=f2(JS["rut"]), JS_RT=f2(JS["rt"]), JS_RT10=f2(JS["rt10"]), JS_RT90=f2(JS["rt90"]), JS_VC=f"{JS['vc_kph']:.1f}",
         JS_PINJ=f"{100 * JS['p_mais3']:.2f}%", JS_ADSGAP=f"{JS['ads_min_gap']:.1f}", JS_MC=f"{JS['mc']['p_coll']:.2f}",
         JS_MCB=JS["mc"]["band"], JS_FLIP=f"{JS['mc']['flip']:.2f}", JS_ADSP=f"{JS['mc']['ads']:.2f}",
         PY_PINJ=f"{100 * float(PP.injury_risk(W['vc'] / 3.6, 1.55)):.2f}%", PY_ADSGAP=f"{r2.ads_min_gap_m:.1f}",
         PY_FLIP=f2(r2.nieon_p_flip), PY_ADSP=f2(r2.ads_p_coll))
yn = lambda b: "collision" if b else "avoided"
rows = ["| ID | Speed (km/h) | Headway (s) | Lead decel. (m/s²) | RUT (s) | RT (s) | NIEON outcome | NIEON closing speed (km/h) | ADS outcome | ADS min. gap (m) |",
        "|---|---|---|---|---|---|---|---|---|---|"]
for x in res.itertuples():
    rows.append(f"| {x.id} | {x.v0_kph:.0f} | {x.headway_s:.2f} | {x.lead_decel_ms2:.2f} | {x.nieon_rut_s:.2f} | {x.nieon_rt_s:.2f} | "
                f"{yn(x.nieon_collides)} | {x.nieon_closing_kph:.0f} | {yn(x.ads_collides)} | {x.ads_min_gap_m:.1f} |")
V["SCEN_TABLE"] = "\n".join(rows)
rows = ["| ID | Det. NIEON | Mean P(coll.) | 5th–95th pct. | Flip prob. | Flip prob. (mean driver) | ADS P(coll.) | Mean P(MAIS3+) |",
        "|---|---|---|---|---|---|---|---|"]
for x in res.itertuples():
    rows.append(f"| {x.id} | {yn(x.nieon_collides)} | {x.nieon_p_coll_mean:.2f} | {x.nieon_p_coll_p05:.2f}–{x.nieon_p_coll_p95:.2f} | "
                f"{x.nieon_p_flip:.2f} | {x.nieon_mean_driver_p_flip:.2f} | {x.ads_p_coll:.2f} | {100 * x.nieon_p_mais3_mean:.2f}% |")
V["PROB_TABLE"] = "\n".join(rows)
lab = {"speed": "Initial speed *v*~0~", "headway": "Headway *h*", "lead_decel": "Lead deceleration *a*~L~",
       "lead_jerk": "Lead jerk *j*~L~", "rt_m": "RT intercept *m*", "rt_k": "RT slope *k*", "rt_cv": "Residual CV",
       "nieon_amax": "NIEON *a*~max~", "nieon_jerk": "NIEON jerk *j*", "rt_residual": "Driver residual *z* (aleatory)",
       "reconstruction": "**Group: reconstruction**", "NIEON timing (model)": "**Group: response-time model**",
       "NIEON braking (model)": "**Group: braking model**", "response-time variability (aleatory)": "**Group: driver variability (aleatory)**"}
rows = ["| Input | *S*~1~ collision | *S*~T~ collision | *S*~1~ closing speed | *S*~T~ closing speed |", "|---|---|---|---|---|"]
for inp in lab:
    a, b = g.loc[("collision", inp)], g.loc[("closing_kph", inp)]
    c = lambda r, k: f"{max(r[k], 0):.2f} [{max(r[k + '_lo'], 0):.2f}, {r[k + '_hi']:.2f}]"
    rows.append(f"| {lab[inp]} | {c(a, 'S1')} | {c(a, 'ST')} | {c(b, 'S1')} | {c(b, 'ST')} |")
V["SOBOL_TABLE"] = "\n".join(rows)
rows = ["| Case (mean-driver view unless stated) | 5th pct. | Median | 95th pct. | P(count = deterministic) |", "|---|---|---|---|---|"]
for x in src.itertuples():
    rows.append(f"| {x.variant} | {x.nieon_p05} | {x.nieon_p50} | {x.nieon_p95} | {x.p_nieon_equals_deterministic:.2f} |")
for x in ref.itertuples():
    rows.append(f"| Reference fixed at {x.response_time_percentile}th-percentile response time (other inputs nominal) | – | {x.nieon_avoided_of_16} | – | – |")
V["SRC_TABLE"] = "\n".join(rows)

tpl = open(os.path.join(ROOT, "docs", "report_template.md"), encoding="utf-8").read()
missing = sorted(set(re.findall(r"«([A-Z0-9_]+)»", tpl)) - set(V))
if missing:
    sys.exit(f"missing placeholders: {missing}")
out = re.sub(r"«([A-Z0-9_]+)»", lambda m: str(V[m.group(1)]), tpl)
left = re.findall(r"«|»", out)
assert not left, "unfilled placeholder"
open(os.path.join(ROOT, "docs", "technical_report.md"), "w", encoding="utf-8").write(out)
json.dump({k: (v if isinstance(v, (int, float, str)) else str(v)) for k, v in V.items() if "TABLE" not in k},
          open(R("report_numbers.json"), "w"), indent=1, default=str)
print("ok", len(out), "chars")
