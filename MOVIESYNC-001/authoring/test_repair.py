"""Manufactured authoring regressions; no bank, source payload, or original fit."""
from pathlib import Path
import sys
import numpy as np
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tests"))
import artifact_reader as a
import isc_math as m
import proof_of_work as p


@pytest.mark.parametrize("estimator",["pairwise","loo","leave-one-out"])
def test_declared_estimators_without_bank(estimator):
    x=np.tile(np.arange(8.)[None,:,None],(3,1,1))
    ref=dict(participant_ids=np.array(["A","B","C"]),visual_map_ids=np.array([0]),map_ids=np.array([0]),map_labels=np.array(["visual"]))
    _,_,result=p.expected_tables_and_results(x,m.support(x),ref,estimator)
    assert result["isc_estimator"] == estimator
    assert result["visual_isc"] == pytest.approx(1., rel=0., abs=1e-14)


@pytest.mark.parametrize("estimator",[None,"custom","LOO"])
def test_undeclared_estimator_rejected_without_outcomes(estimator):
    with pytest.raises(a.ArtifactError,match="estimator enum"):
        p.expected_tables_and_results(None,None,None,estimator)


def test_literal_ids_and_duplicate_keys():
    rows=[{"participant_id":"sub-pixar001"},{"participant_id":"wrong001"}]
    assert len(a.keyed_rows(rows,["participant_id"]))==2
    with pytest.raises(a.ArtifactError,match="duplicate"):
        a.keyed_rows(rows[:1]*2,["participant_id"])


def test_no_bank_reader_in_production():
    assert not hasattr(p,"load_reference")
    text=(Path(__file__).resolve().parents[1]/"tests/test_outputs.py").read_text()
    assert "s.reconstruct()" in text and "reference.npz" not in text
