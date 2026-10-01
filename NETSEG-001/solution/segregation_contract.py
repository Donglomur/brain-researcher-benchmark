import numpy as np


def system_segregation(fisher_z, networks, zero_clip=True):
    networks = np.asarray(networks)
    iu = np.triu_indices(len(networks), 1)
    values = np.asarray(fisher_z)[iu]
    assert np.isfinite(values).all(), "all prescribed ROI pairs must be finite"
    if zero_clip:
        values = np.maximum(values, 0)
    within = networks[iu[0]] == networks[iu[1]]
    assert within.any() and (~within).any()
    w, b = values[within].mean(), values[~within].mean()
    assert w > 0, "within-network mean must be positive"
    return float((w-b)/w)
