import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location("rel",Path(__file__).resolve().parents[1]/"solution/reliability.py")
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)

def test_holm_keeps_family_and_subject_identity():
    assert np.allclose(r.holm_adjust([.02,.001,.5]),[.04,.003,.5])
    assert np.sum(r.holm_adjust([.04]*10)<.05)==0

def test_invalid_permutation_pvalues():
    with pytest.raises(ValueError):r.holm_adjust([1.2,.1])
