import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("phase",ROOT/"tests/phase_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_shared_phase_preserves_cross_spectra():
    rng=np.random.default_rng(4);ts=rng.normal(size=(80,4));p=rng.uniform(0,2*np.pi,41);p[[0,-1]]=0
    sur=m.surrogate(ts,p);f=np.fft.rfft(ts,axis=0);g=np.fft.rfft(sur,axis=0)
    assert np.allclose(f[:,:,None]*f[:,None,:].conj(),g[:,:,None]*g[:,None,:].conj())
def test_independent_phase_shape_rejected():
    with pytest.raises(AssertionError):m.surrogate(np.ones((80,4)),np.zeros((41,4)))
def test_stale_reference_rejected():
    with pytest.raises(AssertionError,match="v2"):m.check_subject({},{"schema_version":"v1"},{})
def test_window_stat_finite():
    assert np.isfinite(m.edge_sd(np.random.default_rng(0).normal(size=(80,4)),20))
