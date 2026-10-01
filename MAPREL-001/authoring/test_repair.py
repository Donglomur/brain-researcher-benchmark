import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("spin",ROOT/"tests/spin_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def fixture():
    rng=np.random.default_rng(2)
    pa=rng.normal(size=12);pb=rng.normal(size=12)
    cent=rng.normal(size=(12,3));hemi=np.repeat([0,1],6)
    samples=np.stack([np.r_[np.roll(np.arange(6),i),6+np.roll(np.arange(6),i)]
                      for i in range(100)],axis=1)
    null=[float(np.corrcoef(pa[samples[:,i]],pb)[0,1]) for i in range(100)]
    p=(1+np.count_nonzero(np.abs(null)>=abs(np.corrcoef(pa,pb)[0,1])))/101
    report={"null_family":"centroid_spin","spin_method":"original","seed":0,
            "n_permutations":100,"null_distribution":null,"p_spin":p,
            "significant_after_spatial_null":p<.05}
    ev={"centroids":cent,"hemisphere":hemi,"spin_indices":samples}
    geo={"schema_version":m.VERSION,"centroids":cent,"hemisphere":hemi}
    return pa,pb,ev,report,geo,lambda *a,**kw:samples
def test_authenticated_recomputation():
    m.validate_spin(*fixture())
def test_fake_two_point_null_reject():
    args=list(fixture());args[3]["null_distribution"]=[-.26,.26]*50
    with pytest.raises(AssertionError):m.validate_spin(*args)
def test_wrong_geometry_reject():
    args=list(fixture());args[4]["centroids"]=args[4]["centroids"]+1
    with pytest.raises(AssertionError):m.validate_spin(*args)
def test_stale_geometry_reject():
    args=list(fixture());args[4]["schema_version"]="v1"
    with pytest.raises(AssertionError):m.validate_spin(*args)
