import importlib.util
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("profile",ROOT/"tests/profile_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def rows():
    return {sid:{"amp":-.1*int(sid),"onset":100+int(sid)} for sid in m.IDS}
def test_exact_signed_cohort_and_ci():
    values=rows();ordered=m.validate_cohort(values)
    am,aci=m.summary([r["amp"] for r in ordered]);on,oci=m.summary([r["onset"] for r in ordered])
    m.validate_intervals(values,{"n_subjects":37,"amp_po8_uv":am,"amp_po8_ci95":aci,
                                "onset_latency_ms":on,"onset_ci95":oci})
def test_omission_rejected():
    values=rows();values.pop("2")
    with pytest.raises(AssertionError):m.validate_cohort(values)
def test_fabricated_ci_rejected():
    values=rows();am,_=m.summary([r["amp"] for r in values.values()])
    with pytest.raises(AssertionError):m.validate_intervals(values,{"n_subjects":37,"amp_po8_uv":am,
                                                                 "amp_po8_ci95":[0,0]})
