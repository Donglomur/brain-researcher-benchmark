import importlib.util
from pathlib import Path
import pytest
import numpy as np
import json
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gradient_contract", ROOT / "tests/gradient_contract.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def test_stale_reference_rejected(tmp_path):
    with pytest.raises(AssertionError, match="regenerate"):
        module.validate_evidence(tmp_path, {"schema_version": "v1"})
def test_public_version():
    assert module.VERSION == "gradient-config-v2"

def test_distinct_subjects_retained():
    array=np.random.default_rng(0).normal(size=(20,40,3))
    module.validate_distinct_subject_embeddings(array)

def test_repeated_template_rejected():
    array=np.random.default_rng(0).normal(size=(20,40,3))
    array[1]=array[0]
    with pytest.raises(AssertionError,match="identical subject"):
        module.validate_distinct_subject_embeddings(array)

def test_repeated_subject_with_tiny_roundoff_rejected():
    array=np.random.default_rng(0).normal(size=(20,40,3))
    array[1]=array[0]+1e-14
    with pytest.raises(AssertionError,match="identical subject"):
        module.validate_distinct_subject_embeddings(array)

@pytest.mark.skipif(not (ROOT/"tests/reference_v2.npz").exists(),reason="genuine v2 regeneration pending")
def test_repeated_genuine_v2_subject_rejected_by_full_contract(tmp_path):
    reference=np.load(ROOT/"tests/reference_v2.npz",allow_pickle=False)
    ids=[str(x) for x in reference["ref_ids"]]
    (tmp_path/"subject_ids.json").write_text(json.dumps(ids))
    aligned=reference["ref_aligned"]
    module.validate_distinct_subject_embeddings(aligned)
    np.save(tmp_path/"gradients_aligned.npy",np.repeat(aligned[0:1],20,axis=0))
    with pytest.raises(AssertionError,match="identical subject"):
        module.validate_evidence(tmp_path,reference)
