import importlib.util
from pathlib import Path
import numpy as np
import pytest
import os
import json
import csv
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("selection",ROOT/"tests/selection_contract.py")
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def test_pinned_real_source_loads():
    z1,z2,zf,ids=m.check_source(ROOT/"environment/data/abide_cc200_pitt40.npz")
    assert len(ids)==40 and z1.shape==z2.shape==zf.shape
def test_corrupt_source_rejected(tmp_path):
    p=tmp_path/"data.npz";p.write_bytes(b"not authentic")
    with pytest.raises(AssertionError):m.check_source(p)
def test_equivalence_not_predetermined():
    a=np.linspace(.2,.3,40);p,e=m.tost_equivalent(a,.05)
    assert e is False
def test_signed_group_stats():
    assert m.group_stats(np.linspace(-.2,-.1,40))["delta_mean"]<0

@pytest.mark.skipif(not os.environ.get("REPAIR_ORACLE_OUTPUT"),reason="requires genuine retained local oracle outputs")
@pytest.mark.parametrize("defect",["fabricated_controls","heldout_in_training"])
def test_current_defect_on_real_outputs_rejected(defect):
    out=Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    z1,z2,zf,ids=m.check_source(ROOT/"environment/data/abide_cc200_pitt40.npz")
    rows=list(csv.DictReader((out/"stability.csv").open()))
    ev=json.loads((out/"selection_evidence.json").read_text())
    if defect=="fabricated_controls":
        for index,row in enumerate(rows):
            row["independent_delta"]=(index-19.5)*.001
            row["random_delta"]=(index-19.5)*.002
    else:
        ev[ids[0]]["training_subject_ids"].append(ids[0])
    with pytest.raises(AssertionError):
        m.check_selections(z1,z2,zf,ids,ev,rows)
