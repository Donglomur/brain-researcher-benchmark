"""Small literal source helpers for generated implementation comparisons only.

Source: Jing Cai, Sydney Cash, Ziv Williams, Zenodo record 20128462,
https://zenodo.org/records/20128462, analysis/computation/figure/Figure3.ipynb,
zero-based cells8 and14. Record license CC BY4.0.
Extracted without changes to the three function bodies; import and this
attribution were added. Parent may retain this small attributed test fixture.
This file contains no source results, data loading, fitting call or test run.
"""
import numpy as np

def perm_test_boot(vals1_, vals2_):
    pooled = np.hstack([vals1_,vals2_])
    np.random.shuffle(pooled)
    star_in = pooled[:len(vals1_)]
    star_out = pooled[-len(vals2_):]
    return star_in.mean()-star_out.mean()

def permutation_test_1side(vals1, vals2, nsamp=1000, seed=None):
    if seed is not None:
        np.random.seed(seed)
    vals1 = np.array(vals1)
    vals2 = np.array(vals2)
    delta = vals1.mean()-vals2.mean()
    est = np.array(list(map(lambda x: perm_test_boot(vals1, vals2),range(nsamp))))
    diff_count = len(np.where(est>=delta)[0])
    p2 = float(diff_count)/float(nsamp)
    return p2

def exponential_func(x, a, b, c):
    """
    Exponential model function for curve fitting.
    y = a * exp(b * x) + c
    """
    return a * np.exp(b * x) + c
