import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("residual",ROOT/"tests/residual_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def fixture():
    rng=np.random.default_rng(4);y=rng.normal(size=(40,2))
    n=np.ones((40,1));task=np.sin(np.arange(40))[:,None]
    data={"roi_signals":y,"nuisance_design":n,"task_design":task,
          "raw_residuals":m.residual(y,n),"background_residuals":m.residual(y,np.c_[n,task])}
    ref=dict(data,schema_version=m.VERSION)
    row=(np.corrcoef(data["raw_residuals"].T)[0,1],np.corrcoef(data["background_residuals"].T)[0,1])
    return data,ref,row
def test_actual_residuals_accept():
    m.check_subject(*fixture())
def test_fabricated_noise_background_reject():
    d,r,row=fixture()
    with pytest.raises(AssertionError):
        m.check_subject(d,r,(row[0],row[0]-0.18))
def test_mismatched_residuals_reject():
    d,r,row=fixture();d["background_residuals"]=d["raw_residuals"]
    with pytest.raises(AssertionError):m.check_subject(d,r,row)
def test_stale_reference_reject():
    d,r,row=fixture();r["schema_version"]="v1"
    with pytest.raises(AssertionError):m.check_subject(d,r,row)
