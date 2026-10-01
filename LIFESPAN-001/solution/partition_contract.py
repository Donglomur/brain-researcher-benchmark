import numpy as np
from sklearn.cluster import KMeans


def age_blind_partition(group_fisher_z):
    features = np.array(group_fisher_z, dtype=float, copy=True)
    assert features.ndim==2 and features.shape[0]==features.shape[1]
    np.fill_diagonal(features, 0)
    assert np.isfinite(features).all()
    return KMeans(n_clusters=7,n_init=10,random_state=0).fit(features).labels_
