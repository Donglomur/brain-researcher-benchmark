import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location("physical",Path(__file__).resolve().parents[1]/"solution/physical.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)

def test_physical_width_and_invalid_header():
    for z in [(1,1,1),(1,2,3)]:
        assert np.allclose(np.asarray(p.gaussian_sigma(1.25,z)[:3])*z*np.sqrt(8*np.log(2)),1.25)
    with pytest.raises(ValueError):p.gaussian_sigma(1.25,[1,0,1])
