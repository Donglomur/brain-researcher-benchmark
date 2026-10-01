import importlib.util
from pathlib import Path
import numpy as np


def test_zero_clipping_keeps_full_pair_denominators():
    p = Path(__file__).parents[1]/"solution/segregation_contract.py"
    spec = importlib.util.spec_from_file_location("seg_contract", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    matrix = np.array([[0,1,.2,-.2],[1,0,.2,-.2],[.2,.2,0,-1],[-.2,-.2,-1,0]])
    assert abs(m.system_segregation(matrix, ["a","a","b","b"]) - .8) < 1e-12
