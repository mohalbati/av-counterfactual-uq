"""
Vectorised lead-vehicle-braking (rear-end, responder role) simulation.

The subject vehicle (SV) follows the lead vehicle (LV) at the same speed v0
with time headway h. At t = 0 the LV starts braking (the 'surprising stimulus
onset' T1 in Engstrom et al. 2024): deceleration ramps up with jerk jL to aL
and holds until the LV stops. The SV keeps its speed until its response time
RT, then brakes with a jerk-limited ramp (jerk j) to maximum deceleration amax.

All inputs are numpy arrays of equal length (one entry per sample), so tens of
thousands of samples are simulated at once.
"""
import numpy as np
from .parameters import LEAD_WIDTH, EYE_TO_BUMPER, LOOMING_THRESHOLD

DT = 0.005   # s
T_MAX = 12.0  # s


def _decel(t, t0, jerk, amax):
    """Jerk-limited deceleration magnitude starting at t0."""
    return np.clip((t - t0) * jerk, 0.0, amax)


def ramp_up_time(v0, h, aL, jL):
    """
    RUT = T2 - T1: time from LV brake onset until the visual looming seen from
    the SV (still at constant speed) first reaches 0.05 rad/s.
    Returns RUT (s); np.inf if never reached before the LV stops and the gap closes.
    """
    n = v0.size
    gap0 = h * v0
    x_rel = gap0.copy()   # LV rear bumper minus SV front bumper
    vL = v0.copy()
    rut = np.full(n, np.inf)
    done = np.zeros(n, bool)
    t = 0.0
    while t < T_MAX and not done.all():
        d = np.maximum(x_rel, 0.01) + EYE_TO_BUMPER
        closing = v0 - vL                          # SV at constant v0
        loom = LEAD_WIDTH * closing / (d**2 + LEAD_WIDTH**2 / 4.0)
        hit = (~done) & (loom >= LOOMING_THRESHOLD)
        rut[hit] = t
        done |= hit | (x_rel <= 0)
        a = _decel(t, 0.0, jL, aL)
        vL_new = np.maximum(vL - a * DT, 0.0)
        x_rel += (0.5 * (vL + vL_new) - v0) * DT
        vL = vL_new
        t += DT
    return rut


def simulate(v0, h, aL, jL, rt, amax, jerk):
    """
    Returns dict with:
      collided (bool), closing_speed at contact (m/s, 0 if avoided),
      min_gap (m), t_contact (s, nan if avoided)
    """
    n = v0.size
    x_rel = h * v0
    vL = v0.copy()
    vS = v0.copy()
    collided = np.zeros(n, bool)
    closing = np.zeros(n)
    t_contact = np.full(n, np.nan)
    min_gap = x_rel.copy()
    active = np.ones(n, bool)
    t = 0.0
    while t < T_MAX and active.any():
        aLv = _decel(t, 0.0, jL, aL)
        aSv = _decel(t, rt, jerk, amax)
        vL_new = np.maximum(vL - aLv * DT, 0.0)
        vS_new = np.maximum(vS - aSv * DT, 0.0)
        x_new = x_rel + (0.5 * (vL + vL_new) - 0.5 * (vS + vS_new)) * DT
        hit = active & (x_new <= 0)
        if hit.any():
            # linear interpolation to the contact instant
            frac = np.where(hit, x_rel / np.maximum(x_rel - x_new, 1e-12), 0)
            cv = (vS + frac * (vS_new - vS)) - (vL + frac * (vL_new - vL))
            closing[hit] = np.maximum(cv[hit], 0.0)
            t_contact[hit] = t + frac[hit] * DT
            collided |= hit
            min_gap[hit] = 0.0
            active &= ~hit
        min_gap = np.where(active, np.minimum(min_gap, x_new), min_gap)
        # stop tracking once the subject vehicle has stopped without contact
        settled = active & (vS_new <= 1e-9)
        active &= ~settled
        x_rel, vL, vS = x_new, vL_new, vS_new
        t += DT
    return {"collided": collided, "closing_speed": closing,
            "min_gap": np.maximum(min_gap, 0.0), "t_contact": t_contact}


def simulate_history(v0, h, aL, jL, rt, amax, jerk, t_end=6.0):
    """Single-sample time history (scalars in, arrays out) for plotting.
    Returns t, gap (m), vS, vL (m/s); the history stops at contact."""
    t = np.arange(0.0, t_end + DT, DT)
    x, vL, vS = h * v0, v0, v0
    g, s, l = [], [], []
    for ti in t:
        g.append(x); s.append(vS); l.append(vL)
        aLv = min(max(ti * jL, 0.0), aL)
        aSv = min(max((ti - rt) * jerk, 0.0), amax)
        vL2, vS2 = max(vL - aLv * DT, 0.0), max(vS - aSv * DT, 0.0)
        x += (0.5 * (vL + vL2) - 0.5 * (vS + vS2)) * DT
        vL, vS = vL2, vS2
        if x <= 0:
            g.append(0.0); s.append(vS); l.append(vL)
            return t[:len(g)], np.array(g), np.array(s), np.array(l)
    return t, np.array(g), np.array(s), np.array(l)
