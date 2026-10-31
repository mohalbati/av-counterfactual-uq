"""Run with:  python -m pytest tests   (or: python tests/test_core.py)"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cfuq import parameters as P
from cfuq.simulate import simulate, ramp_up_time
from cfuq.models import nieon_response_time
from cfuq.sobol import sobol_indices, ishigami


def test_slope_standard_error_matches_reported_significance():
    # SE(k) derived from r = 0.55 and n = 36; t = k/SE must exceed the
    # two-sided p = 0.001 critical value (~3.6 for 34 dof) as reported.
    assert abs(P.RT_K_SE - 0.1224) < 1e-3
    assert P.RT_K / P.RT_K_SE > 3.6


def test_injury_curve_anchored_on_target_threshold():
    v = np.array([126.0 / 3.6])                    # TARGET rear-end closing speed
    for r50 in P.R50_RANGE:
        assert abs(P.injury_risk(v, r50)[0] - 0.10) < 1e-9
    assert P.injury_risk(np.array([0.0]), 1.5)[0] == 0.0


def test_stopping_distance_matches_closed_form():
    # Lead vehicle stops instantly at t = 0 (effectively a stationary obstacle);
    # SV at v0 reacts after rt
    # and brakes with jerk j to amax. Closed-form travel distance:
    v0, rt, a, j = 20.0, 1.0, 8.0, 20.0
    tj = a / j
    d_ramp = v0 * tj - j * tj**3 / 6.0
    v1 = v0 - 0.5 * j * tj**2
    d_total = v0 * rt + d_ramp + v1**2 / (2 * a)
    # Put a stationary obstacle just beyond / just short of that distance
    for margin, expect_hit in ((+0.5, False), (-0.5, True)):
        gap = d_total + margin
        out = simulate(np.array([v0]), np.array([gap / v0]), np.array([1e9]), np.array([1e12]),
                       np.array([rt]), np.array([a]), np.array([j]))
        assert bool(out["collided"][0]) == expect_hit


def test_identical_braking_and_instant_response_never_collides():
    out = simulate(np.array([25.0]), np.array([0.3]), np.array([7.0]), np.array([20.0]),
                   np.array([0.0]), np.array([7.0]), np.array([20.0]))
    assert not out["collided"][0]


def test_response_time_mean_and_lognormal_residual():
    rut = np.full(200000, 1.0)
    z = np.random.default_rng(0).standard_normal(rut.size)
    rt = nieon_response_time(rut, 0.63, 0.47, 0.4, z)
    assert abs(rt.mean() - 1.10) < 0.01                       # unit-mean residual
    assert abs(nieon_response_time(rut[:1], 0.63, 0.47, 0.4)[0] - 1.10) < 1e-12
    assert (rt > 0).all()


def test_ramp_up_time_is_shorter_for_harder_braking():
    v0, h = np.array([20.0, 20.0]), np.array([1.0, 1.0])
    rut = ramp_up_time(v0, h, np.array([3.0, 9.0]), np.array([20.0, 20.0]))
    assert rut[1] < rut[0]


def test_sobol_on_ishigami_analytic_values():
    # Analytic: S1 = (0.314, 0.442, 0), ST = (0.558, 0.442, 0.244)
    f = lambda u: {"y": ishigami(-np.pi + 2 * np.pi * u)}
    df = sobol_indices(f, 3, 2**14, 1, names=["x1", "x2", "x3"], n_boot=20)
    s1, st = df.S1.values, df.ST.values
    assert np.allclose(s1, [0.314, 0.442, 0.0], atol=0.03)
    assert np.allclose(st, [0.558, 0.442, 0.244], atol=0.03)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn(); print("PASS", name)
