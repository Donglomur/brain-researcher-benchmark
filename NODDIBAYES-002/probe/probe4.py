"""Probe 4 (DECIDING TEST): on SINGLE-fibre voxels, does the spurious 2-stick f2
agree between two INDEPENDENT optimizers?  If it disagrees near the ARD threshold,
the COUNT is convention-fragile -> that voxel class must be handled so both methods
AGREE on the pruning decision. Test at several SNR + threshold choices."""
import numpy as np
import probe as PB

bvals, bvecs = PB.gradient_table([1000., 2000.], ndir=30, n_b0=6, seed=5)
unit = PB.unit


def count_decision(meas, F_MIN, method):
    fit = PB.fit_methodA if method == "A" else PB.fit_methodB
    r2 = fit(bvals, bvecs, meas, 2)
    _, st2 = PB.parse(r2.x, 2)
    f1, f2 = st2[0][0], st2[1][0]
    n = int(f1 >= F_MIN) + int(f2 >= F_MIN)
    return n, f1, f2


rng = np.random.default_rng(7)
for snr in [30, 40, 50]:
    print(f"\n===== SNR {snr} =====")
    # generate 60 single-fibre voxels
    disagree = {0.12: 0, 0.15: 0, 0.20: 0, 0.25: 0}
    f2A_all, f2B_all, dabs = [], [], []
    n_disagree_2stickfit = 0
    for i in range(60):
        f = rng.uniform(0.45, 0.70)
        v = PB.sphere_dirs(300, 10 + i)[rng.integers(0, 300)]
        meas = PB.simulate(bvals, bvecs, 1.7e-3, [(f, v)], snr, seed=900 + i)
        rA = PB.fit_methodA(bvals, bvecs, meas, 2)
        rB = PB.fit_methodB(bvals, bvecs, meas, 2)
        _, sA = PB.parse(rA.x, 2)
        _, sB = PB.parse(rB.x, 2)
        f2A, f2B = sA[1][0], sB[1][0]
        f2A_all.append(f2A); f2B_all.append(f2B); dabs.append(abs(f2A - f2B))
        for thr in disagree:
            nA = int(sA[0][0] >= thr) + int(f2A >= thr)
            nB = int(sB[0][0] >= thr) + int(f2B >= thr)
            if nA != nB:
                disagree[thr] += 1
    f2A_all = np.array(f2A_all); f2B_all = np.array(f2B_all); dabs = np.array(dabs)
    print(f"  spurious f2:  A median={np.median(f2A_all):.3f} p90={np.percentile(f2A_all,90):.3f} "
          f"max={np.max(f2A_all):.3f}")
    print(f"  |f2A-f2B|:    median={np.median(dabs):.4f} p90={np.percentile(dabs,90):.4f} "
          f"max={np.max(dabs):.4f}")
    print(f"  COUNT disagreements (A vs B) out of 60, by threshold: {disagree}")
