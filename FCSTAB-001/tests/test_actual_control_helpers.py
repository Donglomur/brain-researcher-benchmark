"""Manufactured qualification of authoring helpers; excluded from scoring."""
import copy
import hashlib
from pathlib import Path

import numpy as np
import pytest

import actual_control_helpers as h
import fixture_support as fs
import output_contract as c
from test_actual_controls import detached,raw_snapshot,same_document


@pytest.fixture
def prepared(monkeypatch):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference()
    data = fs.artifacts(ref)
    return ref,data,h.prepare(data,ref)


def check(tmp_path,ref,candidate,details):
    if candidate is None:
        assert details["status"] in ("unavailable","not_constructed") and details["reason"]
        return
    root = fs.write_output(tmp_path/"output",candidate)
    if details["status"]=="effective":
        assert details["effect"]["n_changed"]>0
        with pytest.raises(ValueError): c.validate(root,ref)
    else:
        assert details["status"] in ("constructed","nondiscriminating")
        assert c.validate(root,ref)["status"]=="accepted"


@pytest.mark.parametrize("mode",h.POSITIVES)
def test_manufactured_equivalent_candidate(tmp_path,prepared,mode):
    ref,data,context = prepared
    original = copy.deepcopy(data)
    candidate,details = h.positive_candidate(mode,data,context)
    assert details["status"]=="constructed"
    assert same_document(data,original)
    check(tmp_path,ref,candidate,details)


@pytest.mark.parametrize("mode",h.NUMERICAL)
def test_component_classified_before_normal_validator(tmp_path,prepared,mode):
    ref,data,context = prepared
    original = copy.deepcopy(data)
    candidate,details = h.numerical_candidate(mode,data,context)
    assert same_document(data,original)
    if candidate is not None:
        for name in ("connectivity.npz","stability.csv","selection_evidence.json"):
            assert same_document(candidate[name],data[name])
        assert candidate["summary.json"]["source_observed"]==data["summary.json"]["source_observed"]
    check(tmp_path,ref,candidate,details)


@pytest.mark.parametrize("mode",h.BINDING)
def test_required_binding_mutations(tmp_path,prepared,mode):
    ref,data,context = prepared
    original = copy.deepcopy(data)
    candidate,details = h.binding_candidate(mode,data,context)
    assert same_document(data,original)
    assert details["status"]=="effective" and details["reason"].startswith("direct required binding discrepancy:")
    check(tmp_path,ref,candidate,details)


@pytest.mark.parametrize("mode",h.NUMERICAL)
def test_source_undefined_never_claimed_effective(tmp_path,monkeypatch,mode):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference(constant_edges=True)
    data = fs.artifacts(ref); context = h.prepare(data,ref)
    candidate,details = h.numerical_candidate(mode,data,context)
    assert details["status"] in ("unavailable","nondiscriminating")
    assert details["effect"]["n_changed"]==0
    check(tmp_path,ref,candidate,details)


def test_zero_signflip_is_honest_nondiscrimination(tmp_path,monkeypatch):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference(constant_edges=True); ref["fisher_z"][:] = 0
    data = fs.artifacts(ref); context = h.prepare(data,ref)
    candidate,details = h.binding_candidate("z_signflip",data,context)
    assert details["status"]=="nondiscriminating"
    check(tmp_path,ref,candidate,details)


def test_all_positive_reliability_absolute_control_is_nondiscriminating(tmp_path,monkeypatch):
    fs.freeze_manufactured_authority(monkeypatch)
    ref = fs.reference(zero_delta=True)
    data = fs.artifacts(ref); context = h.prepare(data,ref)
    candidate,details = h.numerical_candidate("absolute_reliability",data,context)
    assert details["status"]=="nondiscriminating"
    check(tmp_path,ref,candidate,details)


def test_opposite_tail_keeps_typed_own_boolean(prepared):
    _,data,context = prepared
    candidate,details = h.numerical_candidate("opposite_tost_tails",data,context)
    assert candidate is not None
    eq = candidate["summary.json"]["equivalence"]
    assert type(eq["equivalent_within_margin"]) is bool
    assert eq["equivalent_within_margin"] == (eq["tost_p"] < .05)


@pytest.mark.parametrize("actual,expected,changed",[(0.,0.,0),(5e-9,0.,0),(2e-8,0.,1),
    (None,0.,1),(0.,None,1),(True,1,1),(2,1,1),("1",1.,1)])
def test_effect_classification_typed_public_tolerance(actual,expected,changed):
    effect = h.numeric_effects({"x":actual},{"x":expected})
    assert effect["n_changed"]==changed


def test_effect_probability_domain_and_status():
    assert h.numeric_effects({"p":-5e-9},{"p":0.})["n_numeric_changes"]==1
    result = h.numeric_effects({"inference_status":"source_zero_variance"},{"inference_status":"ok"})
    assert result["n_status_changes"]==1 and result["n_numeric_changes"]==0


@pytest.mark.parametrize("function",[h.positive_candidate,h.numerical_candidate,h.binding_candidate])
def test_unknown_mode_refusal(function):
    with pytest.raises(ValueError,match="unknown"): function("unknown",{}, {})


def test_detached_copy_preserves_original_and_removes_only_owned_dir(tmp_path,prepared):
    ref,data,context = prepared
    original = fs.write_output(tmp_path/"original",data)
    genuine = dict(root=original,reference=ref,documents=data,raw=raw_snapshot(original),context=context)
    before = {name:hashlib.sha256(raw).hexdigest() for name,raw in genuine["raw"].items()}
    candidate,_ = h.numerical_candidate("population_sd",data,context)
    with detached(genuine,candidate,tmp_path) as root:
        owned = root
        assert root != original
        assert (root/"connectivity.npz").read_bytes()==genuine["raw"]["connectivity.npz"]
        assert (root/"stability.csv").read_bytes()==genuine["raw"]["stability.csv"]
        assert (root/"connectivity.npz").stat().st_ino != (original/"connectivity.npz").stat().st_ino
    assert not owned.exists() and original.is_dir()
    assert before=={name:hashlib.sha256(raw).hexdigest() for name,raw in raw_snapshot(original).items()}


def test_helper_has_no_source_or_network_imports():
    text = Path(h.__file__).read_text()
    assert "import source_reference" not in text and "reconstruct(" not in text
    assert "urllib" not in text and "requests." not in text


def test_detached_unexpected_failure_preserves_candidate(tmp_path,prepared):
    ref,data,context = prepared
    original = fs.write_output(tmp_path/"original",data)
    genuine = dict(root=original,reference=ref,documents=data,raw=raw_snapshot(original),context=context)
    with pytest.raises(RuntimeError,match="manufactured unexpected failure"):
        with detached(genuine,copy.deepcopy(data),tmp_path) as root:
            owned = root
            raise RuntimeError("manufactured unexpected failure")
    assert owned.is_dir() and owned != original
    assert raw_snapshot(owned) == raw_snapshot(original)
