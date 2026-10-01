import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("covariates",ROOT/"tests/covariate_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_honest_numeric_fields():
    e={"motion":{"n":80,"r":.1,"ci95":[-.2,.3],"subject_ids":["A","B"]}}
    m.compare_numeric(e,e)
@pytest.mark.parametrize("actual",[{"r":.9,"ci95":[-.2,.3]},{"r":.1,"ci95":[0,0]},{}])
def test_fake_or_missing_numeric_fields_rejected(actual):
    with pytest.raises(AssertionError):m.compare_numeric(actual,{"r":.1,"ci95":[-.2,.3]})
def test_site_unit_interval_wider_than_participant_unit():
    assert np.ptp(m.fisher_ci(.1,18))>np.ptp(m.fisher_ci(.1,1000))
