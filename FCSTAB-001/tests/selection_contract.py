"""Derive all selected-edge changes and uncertainty from the pinned real source arrays."""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy import stats

BAKED_SHA256="af2d08b5ded6471e0012fa993372a7eb6074898a095e94b2342644e54a122e59"
def edges_z(x):
    """Upper-triangle Fisher-z of the ROI x ROI correlation of a (T, R) array."""
    C = np.corrcoef(x, rowvar=False)
    iu = np.triu_indices(C.shape[0], k=1)
    return np.arctanh(np.clip(C[iu], -0.999999, 0.999999))


def group_stats(a):
    from scipy import stats
    a = np.asarray(a, float)
    n = a.size
    m = float(a.mean())
    sd = float(a.std(ddof=1))
    se = sd / np.sqrt(n)
    t, p = stats.ttest_1samp(a, 0.0)
    lo, hi = stats.t.interval(0.95, n - 1, loc=m, scale=se)
    return {"delta_mean": m, "delta_sd": sd, "delta_se": float(se),
            "ci95_lo": float(lo), "ci95_hi": float(hi),
            "t": float(t), "p": float(p), "n_negative": int((a < 0).sum()), "n": int(n)}


def tost_equivalent(a, margin):
    """Two one-sided tests that mean(a) lies within +/- margin. Returns (p_tost, equivalent)."""
    from scipy import stats
    a = np.asarray(a, float)
    n = a.size
    m = a.mean()
    se = a.std(ddof=1) / np.sqrt(n)
    dfree = n - 1
    p_lo = stats.t.sf((m - (-margin)) / se, dfree)   # H0: mean <= -margin
    p_hi = stats.t.sf((margin - m) / se, dfree)       # H0: mean >= +margin
    p_tost = float(max(p_lo, p_hi))
    return p_tost, bool(p_tost < 0.05)



def check_selections(z1,z2,zf,ids,evidence,rows,seed=0):
    rng=np.random.default_rng(seed);k=max(1,int(.1*z1.shape[1]))
    index={str(s):i for i,s in enumerate(ids)}
    changes={s:[] for s in ("forward","reverse","independent","random")}
    overlaps=[];spearmans=[];pearsons=[]
    assert len(rows)==len(ids) and len({str(r["subject_id"]) for r in rows})==len(ids)
    for row in rows:
        sid=str(row["subject_id"]);i=index[sid];ev=evidence[sid]
        training=[str(s) for s in ev["training_subject_ids"]]
        assert sid not in training and len(training)==len(set(training)) and len(training)>=10
        assert set(training)<=set(index)
        expected={"forward":np.argsort(z1[i])[-k:],"reverse":np.argsort(z2[i])[-k:],
                  "independent":np.argsort(zf[[index[s] for s in training]].mean(0))[-k:],
                  "random":rng.choice(z1.shape[1],size=k,replace=False)}
        for scheme,selected in expected.items():
            indices=np.asarray(ev[scheme+"_edge_indices"])
            assert np.array_equal(indices,selected), f"wrong/leaking {scheme} edges"
            delta=float((z2[i,indices]-z1[i,indices]).mean())
            assert abs(float(row[scheme+"_delta"])-delta)<2e-6
            changes[scheme].append(delta)
        overlaps.append(len(set(expected["forward"])&set(expected["reverse"]))/k)
        spearmans.append(stats.spearmanr(z1[i],z2[i]).statistic)
        pearsons.append(np.corrcoef(z1[i],z2[i])[0,1])
    summaries={scheme:group_stats(values) for scheme,values in changes.items()}
    p,equivalent=tost_equivalent(changes["independent"],.05)
    reliability={"top_decile_set_overlap_first_vs_second":float(np.mean(overlaps)),
                 "edge_rank_spearman_first_vs_second":float(np.mean(spearmans)),
                 "edge_pearson_first_vs_second":float(np.mean(pearsons))}
    return summaries,p,equivalent,reliability

def check_source(path):
    assert hashlib.sha256(path.read_bytes()).hexdigest()==BAKED_SHA256, "pinned source hash mismatch"
    data=np.load(path,allow_pickle=False);ts=np.asarray(data["timeseries"],float)
    ids=[str(int(x)) for x in data["subject_ids"]]
    assert ts.shape==(40,196,200) and len(set(ids))==40 and np.isfinite(ts).all()
    L=ts.shape[1]//2
    keep=np.ones(ts.shape[2],bool)
    for x in ts:
        keep &= (x.std(0)>1e-8)&(x[:L].std(0)>1e-8)&(x[-L:].std(0)>1e-8)
    z1=np.asarray([edges_z(x[:L,keep]) for x in ts])
    z2=np.asarray([edges_z(x[-L:,keep]) for x in ts])
    zf=np.asarray([edges_z(x[:,keep]) for x in ts])
    return z1,z2,zf,ids
