import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("social",ROOT/"tests/social_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_fisher_average_not_raw_average():
    assert m.fisher_mean([.9,.1])!=pytest.approx(.5)
def test_partial_rank_motion_adjustment():
    rng=np.random.default_rng(1);motion=rng.normal(size=80)
    age=motion+rng.normal(size=80)*.1;values=motion+rng.normal(size=80)*.1
    r,p=m.partial_rank_corr(age,values,motion)
    assert abs(r)<.5 and 0<=p<=1
def test_new_reference_version():
    assert m.VERSION=="socialbrain-fisher-id-v2"
