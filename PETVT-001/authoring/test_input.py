import importlib.util
from pathlib import Path
import numpy as np
import pytest
spec=importlib.util.spec_from_file_location("input",Path(__file__).resolve().parents[1]/"solution/input_contract.py")
i=importlib.util.module_from_spec(spec);spec.loader.exec_module(i)

def test_decay_footing_does_not_double_correct():
    assert np.allclose(i.parent_input([10],[.5],[100],"pet_time_zero",.01),[5])
    assert np.allclose(i.parent_input([10],[.5],[100],"draw_time",.01),[5*np.e])
    with pytest.raises(ValueError):i.parent_input([10],[.5],[100],"unknown",.01)
