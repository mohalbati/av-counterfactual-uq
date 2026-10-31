"""
Responder models and the uncertainty structure.

Uncertainty is split the way PRA separates it:
  * epistemic (state of knowledge): what the reconstruction really was, and
    the reference-model parameters. Sampled in the OUTER loop.
  * aleatory (variability): trial-to-trial response-time scatter of the
    NIEON driver population. Sampled in the INNER loop.
The deterministic 'point estimate' practice corresponds to setting every
epistemic quantity to its nominal value and the residual to zero.
"""
import numpy as np
from . import parameters as P
from .simulate import ramp_up_time, simulate


def nieon_response_time(rut, m, k, cv, z=None):
    """Response time = (m + k*RUT) * lognormal residual with unit mean.
    z=None gives the regression mean itself (the point-estimate 'mean driver')."""
    mu = m + k * np.where(np.isfinite(rut), rut, 10.0)
    if z is None:
        return mu
    s = np.sqrt(np.log(1 + cv**2))
    return mu * np.exp(s * z - 0.5 * s**2)


# ---------- epistemic sampling (outer loop) -------------------------------
EPI_NAMES = ["speed", "headway", "lead_decel", "lead_jerk",           # reconstruction
             "rt_m", "rt_k", "rt_cv", "nieon_amax", "nieon_jerk",     # NIEON model
             "ads_latency", "ads_amax", "ads_jerk", "inj_r50"]        # ADS model, injury
GROUP = {"speed": "reconstruction", "headway": "reconstruction",
         "lead_decel": "reconstruction", "lead_jerk": "reconstruction",
         "rt_m": "NIEON timing", "rt_k": "NIEON timing", "rt_cv": "NIEON timing",
         "nieon_amax": "NIEON braking", "nieon_jerk": "NIEON braking",
         "ads_latency": "ADS", "ads_amax": "ADS", "ads_jerk": "ADS", "inj_r50": "injury model"}


def epistemic_from_unit(u, sc, rec_scale=1.0, fix=()):
    """Map unit-hypercube samples u (N x 13) to physical values for scenario sc.
    rec_scale scales the reconstruction half-widths; names in `fix` are held at nominal."""
    from scipy.stats import norm
    lo_hi = lambda q, a, b: a + q * (b - a)
    e = {}
    e["speed"] = sc["v0"] * (1 + rec_scale * P.REC_SPEED_REL * (2 * u[:, 0] - 1))
    e["headway"] = sc["h"] * (1 + rec_scale * P.REC_HEADWAY_REL * (2 * u[:, 1] - 1))
    e["lead_decel"] = sc["aL"] * (1 + rec_scale * P.REC_LEAD_DECEL_REL * (2 * u[:, 2] - 1))
    e["lead_jerk"] = lo_hi(u[:, 3], *P.REC_LEAD_JERK_RANGE)
    e["rt_m"] = P.RT_M + P.RT_M_SE * norm.ppf(np.clip(u[:, 4], 1e-6, 1 - 1e-6))
    e["rt_k"] = np.maximum(P.RT_K + P.RT_K_SE * norm.ppf(np.clip(u[:, 5], 1e-6, 1 - 1e-6)), 0)
    e["rt_cv"] = lo_hi(u[:, 6], *P.RT_CV_RANGE)
    e["nieon_amax"] = lo_hi(u[:, 7], *P.NIEON_AMAX_RANGE)
    e["nieon_jerk"] = lo_hi(u[:, 8], *P.NIEON_JERK_RANGE)
    e["ads_latency"] = lo_hi(u[:, 9], *P.ADS_LATENCY_RANGE)
    e["ads_amax"] = lo_hi(u[:, 10], *P.ADS_AMAX_RANGE)
    e["ads_jerk"] = lo_hi(u[:, 11], *P.ADS_JERK_RANGE)
    e["inj_r50"] = lo_hi(u[:, 12], *P.R50_RANGE)
    if fix:
        nom = nominal(sc)
        for k in fix:
            e[k] = np.full(u.shape[0], nom[k], float)
    return e


def nominal(sc):
    """Point-estimate ('deterministic') values for scenario sc."""
    mid = lambda r: 0.5 * (r[0] + r[1])
    return {"speed": sc["v0"], "headway": sc["h"], "lead_decel": sc["aL"],
            "lead_jerk": mid(P.REC_LEAD_JERK_RANGE), "rt_m": P.RT_M, "rt_k": P.RT_K,
            "rt_cv": mid(P.RT_CV_RANGE), "nieon_amax": mid(P.NIEON_AMAX_RANGE),
            "nieon_jerk": mid(P.NIEON_JERK_RANGE), "ads_latency": mid(P.ADS_LATENCY_RANGE),
            "ads_amax": mid(P.ADS_AMAX_RANGE), "ads_jerk": mid(P.ADS_JERK_RANGE),
            "inj_r50": mid(P.R50_RANGE)}


def run(e, z, who):
    """
    Simulate responder `who` ('nieon' or 'ads') for arrays of epistemic values e
    (each length N) and standard-normal residuals z (length N; None = mean driver;
    ignored for ADS).
    """
    v0, h, aL, jL = e["speed"], e["headway"], e["lead_decel"], e["lead_jerk"]
    if who == "nieon":
        rut = ramp_up_time(v0, h, aL, jL)
        rt = nieon_response_time(rut, e["rt_m"], e["rt_k"], e["rt_cv"], z)
        out = simulate(v0, h, aL, jL, rt, e["nieon_amax"], e["nieon_jerk"])
        out["rt"], out["rut"] = rt, rut
    else:
        out = simulate(v0, h, aL, jL, e["ads_latency"], e["ads_amax"], e["ads_jerk"])
        out["rt"] = e["ads_latency"]
    out["p_mais3"] = P.injury_risk(out["closing_speed"], e["inj_r50"])
    return out
