import importlib.util
from pathlib import Path
import numpy as np
import pytest

spec = importlib.util.spec_from_file_location("physical", Path(__file__).resolve().parents[1] / "solution/physical.py")
physical = importlib.util.module_from_spec(spec); spec.loader.exec_module(physical)

@pytest.mark.parametrize("zooms", [(1,1,1),(1,2,3),(2,2,2)])
def test_physical_width(zooms):
    got = physical.gaussian_sigma(1.25, zooms)
    assert np.allclose(np.asarray(got[:3]) * zooms * np.sqrt(8*np.log(2)), 1.25)
    assert got[-1] == 0

def test_invalid_header():
    with pytest.raises(ValueError):
        physical.gaussian_sigma(1.25, [1,0,1])
