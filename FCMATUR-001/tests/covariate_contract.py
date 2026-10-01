"""Recompute participant/site-unit uncertainty and measured covariate sensitivities."""
import numpy as np
import pandas as pd
from scipy import stats
MIN_PER_SITE = 5

def fisher_ci(r, dof, alpha=0.05):
    """Fisher-z 95% CI for a (partial) correlation with `dof` effective degrees of freedom.
    dof = n - 2 for a simple correlation; n - k - 2 for a partial correlation on k covariates."""
    r = float(np.clip(r, -0.999999, 0.999999))
    if dof <= 1:
        return (float("nan"), float("nan"))
    z = np.arctanh(r)
    se = 1.0 / np.sqrt(dof - 1)
    zc = stats.norm.ppf(1 - alpha / 2)
    return (float(np.tanh(z - zc * se)), float(np.tanh(z + zc * se)))


def partial_corr(y, x, controls):
    """Partial correlation of y and x controlling for `controls` (2D design incl. intercept).
    Returns (r, p, dof) with dof = n - k - 2 (k = # non-intercept controls)."""
    y = np.asarray(y, float); x = np.asarray(x, float)
    D = np.asarray(controls, float)

    def resid(v):
        beta, *_ = np.linalg.lstsq(D, v, rcond=None)
        return v - D @ beta
    ry, rx = resid(y), resid(x)
    k = D.shape[1] - 1  # drop the intercept from the covariate count
    dof = len(y) - k - 2
    r = float(np.corrcoef(ry, rx)[0, 1])
    if not np.isfinite(r) or dof <= 1:
        return float("nan"), float("nan"), dof
    t = r * np.sqrt(dof / max(1e-12, 1 - r * r))
    p = float(2 * stats.t.sf(abs(t), dof))
    return r, p, dof



def compute_sensitivity(df):
    n = len(df)
    vc = df.site_id.value_counts()
    w = df[df.site_id.isin(vc[vc >= MIN_PER_SITE].index)].reset_index(drop=True)
    sens = {}
    
    # (1) Motion / QC — pooled and within-site associations adjusting for mean framewise displacement.
    mo = w[np.isfinite(w.mean_fd)].reset_index(drop=True)
    if len(mo) > 50:
        Dm = np.column_stack([np.ones(len(mo)), mo.mean_fd.to_numpy()])
        rp_m, pp_m, _ = partial_corr(mo.connectivity.to_numpy(), mo.age.to_numpy(), Dm)
        Dsm = pd.get_dummies(mo.site_id, drop_first=True).astype(float).to_numpy()
        Dsm = np.column_stack([np.ones(len(mo)), Dsm, mo.mean_fd.to_numpy()])
        rw_m, pw_m, _ = partial_corr(mo.connectivity.to_numpy(), mo.age.to_numpy(), Dsm)
        sens["motion"] = {"n": int(len(mo)), "pooled_r_adj_motion": rp_m, "pooled_p_adj_motion": pp_m,
                          "within_site_r_adj_motion": rw_m, "within_site_p_adj_motion": pw_m,
                          "note": "connectivity–age association adjusting for mean framewise displacement"}
    
    # (2) Diagnosis — restrict to typical controls (DX_GROUP == 2 in ABIDE) and recompute both levels.
    ctrl = w[w.dx_group == 2].reset_index(drop=True)
    if len(ctrl) > 50 and ctrl.site_id.nunique() >= 2:
        rp_c, pp_c = stats.pearsonr(ctrl.connectivity, ctrl.age)
        Dc = np.column_stack([np.ones(len(ctrl)),
                              pd.get_dummies(ctrl.site_id, drop_first=True).astype(float).to_numpy()])
        rw_c, pw_c, _ = partial_corr(ctrl.connectivity.to_numpy(), ctrl.age.to_numpy(), Dc)
        sens["diagnosis"] = {"n_controls": int(len(ctrl)), "pooled_r_controls": float(rp_c),
                             "pooled_p_controls": float(pp_c), "within_site_r_controls": rw_c,
                             "within_site_p_controls": pw_c,
                             "note": "restricted to typical controls (DX_GROUP==2)"}
    
    # (3) Sex — pooled and within-site adjusting for sex.
    sx = w[np.isfinite(w.sex)].reset_index(drop=True)
    if len(sx) > 50:
        Dx = np.column_stack([np.ones(len(sx)), sx.sex.to_numpy()])
        rp_s, pp_s, _ = partial_corr(sx.connectivity.to_numpy(), sx.age.to_numpy(), Dx)
        Dxs = pd.get_dummies(sx.site_id, drop_first=True).astype(float).to_numpy()
        Dxs = np.column_stack([np.ones(len(sx)), Dxs, sx.sex.to_numpy()])
        rw_s, pw_s, _ = partial_corr(sx.connectivity.to_numpy(), sx.age.to_numpy(), Dxs)
        sens["sex"] = {"n": int(len(sx)), "pooled_r_adj_sex": rp_s, "pooled_p_adj_sex": pp_s,
                       "within_site_r_adj_sex": rw_s, "within_site_p_adj_sex": pw_s,
                       "note": "connectivity–age association adjusting for sex"}
    
    # (4) Nonlinear age — does a quadratic age term add anything (pooled)?
    a = df.age.to_numpy(); c = df.connectivity.to_numpy()
    az = (a - a.mean()) / a.std()
    Xlin = np.column_stack([np.ones(n), az])
    Xquad = np.column_stack([np.ones(n), az, az ** 2])
    bl, *_ = np.linalg.lstsq(Xlin, c, rcond=None)
    bq, *_ = np.linalg.lstsq(Xquad, c, rcond=None)
    rss_l = float(((c - Xlin @ bl) ** 2).sum())
    rss_q = float(((c - Xquad @ bq) ** 2).sum())
    df1, df2 = 1, n - 3
    F = ((rss_l - rss_q) / df1) / (rss_q / df2)
    p_nl = float(stats.f.sf(F, df1, df2)) if np.isfinite(F) and F > 0 else float("nan")
    sens["nonlinear_age"] = {"quadratic_beta": float(bq[2]), "F_added_quadratic": float(F),
                             "p_added_quadratic": p_nl,
                             "note": "pooled test that an age^2 term improves the connectivity model"}
    
    # (5) Site-specific slopes — the per-site connectivity~age relationship is heterogeneous.
    per_site = []
    for s, g in w.groupby("site_id"):
        if len(g) >= MIN_PER_SITE and g.age.std() > 0 and g.connectivity.std() > 0:
            rr, pp = stats.pearsonr(g.connectivity, g.age)
            slope = float(np.polyfit(g.age, g.connectivity, 1)[0])
            per_site.append({"site_id": str(s), "n": int(len(g)), "r": float(rr), "p": float(pp),
                             "slope": slope})
    ps_r = np.array([d["r"] for d in per_site], dtype=float)
    sens["site_specific_slopes"] = {
        "n_sites": len(per_site),
        "median_within_site_r": float(np.median(ps_r)) if len(ps_r) else float("nan"),
        "frac_sites_positive": float(np.mean(ps_r > 0)) if len(ps_r) else float("nan"),
        "min_r": float(ps_r.min()) if len(ps_r) else float("nan"),
        "max_r": float(ps_r.max()) if len(ps_r) else float("nan"),
        "per_site": per_site,
        "note": "per-site connectivity–age correlation; heterogeneous, not a single common slope"}
    samples = {"motion": w[np.isfinite(w.mean_fd)], "diagnosis": w[w.dx_group == 2],
               "sex": w[np.isfinite(w.sex)], "nonlinear_age": df, "site_specific_slopes": w}
    for name, subset in samples.items():
        if name in sens:
            sens[name]["subject_ids"] = sorted(subset.subject.astype(str).tolist())
    return sens

def uncertainty(df):
    n = len(df)
    pooled_r,pooled_p = stats.pearsonr(df.connectivity, df.age)
    vc=df.site_id.value_counts()
    w=df[df.site_id.isin(vc[vc>=MIN_PER_SITE].index)]
    controls=np.column_stack([np.ones(len(w)),pd.get_dummies(w.site_id,drop_first=True).astype(float)])
    within_r,within_p,dof=partial_corr(w.connectivity.to_numpy(),w.age.to_numpy(),controls)
    site=df.groupby("site_id").agg(n=("subject","size"),c=("connectivity","mean"),a=("age","mean"))
    site=site[site.n>=MIN_PER_SITE]
    between_r,between_p=stats.pearsonr(site.c,site.a)
    return {"pooled_ci95":fisher_ci(pooled_r,n-2),"pooled_p":pooled_p,
            "within_site_ci95":fisher_ci(within_r,dof),"within_site_p":within_p,
            "between_site_ci95":fisher_ci(between_r,len(site)-2),"between_site_p":between_p}

def compare_numeric(actual, expected):
    if isinstance(expected, dict):
        for key,value in expected.items():
            if key == "note": continue
            assert key in actual, f"missing {key}"
            compare_numeric(actual[key],value)
    elif isinstance(expected,(list,tuple)):
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected): compare_numeric(a,b)
    elif isinstance(expected,str):
        assert actual==expected
    elif isinstance(expected,(int,float,np.number)):
        assert np.isfinite(expected) and np.isfinite(actual)
        assert np.isclose(actual,expected,atol=1e-6,rtol=1e-5)
