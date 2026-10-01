"""Recompute canonical-HRF sensitivity from authenticated ROI/design intermediates."""
import numpy as np
from scipy.stats import t

VERSION = "taskfc-residual-v2"

def residual(y, design):
    y = np.asarray(y, float); design = np.asarray(design, float)
    assert y.ndim == 2 and y.shape[1] == 2
    assert design.ndim == 2 and len(y) == len(design)
    assert np.isfinite(y).all() and np.isfinite(design).all()
    return y - design @ np.linalg.lstsq(design, y, rcond=None)[0]

def check_subject(data, reference, row):
    assert str(reference["schema_version"]) == VERSION, "genuine residual-v2 reference required"
    for key in ("roi_signals", "nuisance_design", "task_design"):
        assert np.allclose(data[key], reference[key], atol=1e-6, rtol=1e-5), key
    y,nuisance,task = data["roi_signals"],data["nuisance_design"],data["task_design"]
    raw = residual(y,nuisance)
    background = residual(y,np.column_stack([nuisance,task]))
    assert np.allclose(data["raw_residuals"],raw,atol=1e-6,rtol=1e-5)
    assert np.allclose(data["background_residuals"],background,atol=1e-6,rtol=1e-5)
    raw_r = float(np.corrcoef(raw.T)[0,1])
    bg_r = float(np.corrcoef(background.T)[0,1])
    assert abs(float(row[0])-raw_r)<=1e-6
    assert abs(float(row[1])-bg_r)<=1e-6
    return raw_r,bg_r

def paired_interval(raw, background):
    d = np.arctanh(np.clip(raw,-.999,.999))-np.arctanh(np.clip(background,-.999,.999))
    mean=float(d.mean()); h=float(t.ppf(.975,len(d)-1)*d.std(ddof=1)/np.sqrt(len(d)))
    return {"n":len(d), "mean_raw_minus_background_z":mean,"ci95":[mean-h,mean+h]}
