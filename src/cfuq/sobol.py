"""
Variance-based (Sobol) sensitivity indices with the Saltelli sampling scheme.

First-order: Saltelli et al. (2010) estimator
    S_i  = mean(f_B * (f_ABi - f_A)) / Var(Y)
Total-effect: Jansen (1999) estimator
    ST_i = 0.5 * mean((f_A - f_ABi)^2) / Var(Y)
Groups of inputs are handled by swapping all columns of the group at once,
which gives the closed first-order and total index of the group.
Confidence intervals come from bootstrapping the N base rows.
"""
import numpy as np
import pandas as pd
from scipy.stats import qmc


def sobol_indices(f, d, n, seed, names, groups=None, n_boot=200):
    base = qmc.Sobol(d=2 * d, scramble=True, seed=seed).random(n)
    A, B = base[:, :d], base[:, d:]
    blocks = [(nm, [i]) for i, nm in enumerate(names)]
    if groups:
        blocks += [(g, [names.index(c) for c in cols]) for g, cols in groups.items()]
    fA, fB = f(A), f(B)
    out_names = list(fA.keys())
    fAB = []
    for _, cols in blocks:
        ABi = A.copy(); ABi[:, cols] = B[:, cols]
        fAB.append(f(ABi))
    rng = np.random.default_rng(seed)
    boots = [rng.integers(0, n, n) for _ in range(n_boot)]
    rows = []
    for o in out_names:
        ya, yb = fA[o], fB[o]
        for (label, cols), fab in zip(blocks, fAB):
            yab = fab[o]

            def est(ix):
                v = np.var(np.concatenate([ya[ix], yb[ix]]))
                if v <= 0:
                    return np.nan, np.nan
                s1 = np.mean(yb[ix] * (yab[ix] - ya[ix])) / v
                st = 0.5 * np.mean((ya[ix] - yab[ix]) ** 2) / v
                return s1, st
            s1, st = est(np.arange(n))
            bs = np.array([est(ix) for ix in boots])
            rows.append(dict(output=o, input=label, kind="group" if len(cols) > 1 or label in (groups or {}) else "input",
                             S1=s1, S1_lo=np.nanquantile(bs[:, 0], .025), S1_hi=np.nanquantile(bs[:, 0], .975),
                             ST=st, ST_lo=np.nanquantile(bs[:, 1], .025), ST_hi=np.nanquantile(bs[:, 1], .975)))
    return pd.DataFrame(rows)


def ishigami(x, a=7.0, b=0.1):
    """Standard test function (inputs on [-pi, pi]); used in the unit tests."""
    return np.sin(x[:, 0]) + a * np.sin(x[:, 1]) ** 2 + b * x[:, 2] ** 4 * np.sin(x[:, 0])
