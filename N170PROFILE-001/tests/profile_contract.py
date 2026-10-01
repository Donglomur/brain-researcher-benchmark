"""Exact ERP CORE sample and participant-unit uncertainty."""
import numpy as np
from scipy.stats import t
IDS={str(i) for i in range(1,41)}-{"1","5","16"}
BAKE_SHA256="8d248b3dcbc7909277e3588c9c01b0f5ee81a24626ff2ff50d9113a3d1c61140"

def validate_cohort(rows):
    assert set(rows)==IDS and len(rows)==37, "exact37 unique analysis participants required"
    for sid in IDS:
        assert all(rows[sid].get(k) is not None and np.isfinite(rows[sid][k]) for k in ("amp","onset"))
    return [rows[s] for s in sorted(IDS,key=int)]

def summary(values):
    x=np.asarray(values,float)
    assert len(x)==37 and np.isfinite(x).all()
    mean=float(x.mean());h=float(t.ppf(.975,36)*x.std(ddof=1)/np.sqrt(37))
    return mean,np.array([mean-h,mean+h])

def validate_intervals(rows,report):
    ordered=validate_cohort(rows)
    assert report["n_subjects"]==37
    for key,mean_key,ci_key,tolerance in (("amp","amp_po8_uv","amp_po8_ci95",.0002),
                                          ("onset","onset_latency_ms","onset_ci95",.002)):
        mean,ci=summary([r[key] for r in ordered])
        assert abs(float(report[mean_key])-mean)<=tolerance
        assert np.allclose(report[ci_key],ci,atol=tolerance,rtol=0)
