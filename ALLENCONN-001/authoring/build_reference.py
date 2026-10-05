"""Replace the bank only after raw-source and full-output validation.

No source data or scientific reference is invented by this builder. The retained
oracle receipt must agree with the complete frozen official API response set.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "solution"))
import compute


def build(output_dir, data_dir, reference_path):
    output_dir, reference_path = Path(output_dir), Path(reference_path)
    with np.load(output_dir / "analysis_arrays.npz", allow_pickle=False) as archive:
        receipt = {name: archive[name] for name in archive.files}
    source, contract, _ = compute.load_inputs(data_dir)
    for name, values in source.items():
        np.testing.assert_array_equal(receipt[name], values, err_msg=f"source receipt mismatch: {name}")
    matrix, n_observed, n_expected = compute.aggregate(source)
    for name, values in [("matrix", matrix), ("n_observed", n_observed), ("n_expected", n_expected)]:
        np.testing.assert_array_equal(receipt[name], values, err_msg=f"aggregation receipt mismatch: {name}")
        source[name] = values
    template = json.loads((TASK / "environment/method_contract.json").read_text())
    assert template == contract, "public template differs from source/method contract"
    metadata = json.loads((output_dir / "run_metadata.json").read_text())
    assert metadata == json.loads(str(receipt["metadata_json"])), "retained metadata differs from public output"
    results, _ = compute.describe(source)
    assert results["n_eligible_sources"] > 0, "cannot freeze an unidentified headline"
    assert results == json.loads((output_dir / "self_projection.json").read_text()), "incorrect public source-derived summary"
    for key, value in {**contract, **results}.items():
        assert metadata.get(key) == value, f"metadata mismatch: {key}"
    bank = {"ref_" + key: value for key, value in source.items()}
    bank["ref_stats"] = np.asarray(json.dumps({"pipeline_id": compute.PIPELINE_ID,
        "source_sha256": contract["source_sha256"], "metadata_contract": contract,
        "results": results}, allow_nan=False))
    reference_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=reference_path.parent, prefix=".source-verified-", suffix=".npz", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        np.savez_compressed(temporary, **bank)
        sys.path.insert(0, str(TASK / "tests"))
        import proof_of_work
        import matrix_contract
        reference = proof_of_work.load_reference(temporary)
        matrix_contract.validate_output_directory(output_dir, reference)
        temporary.replace(reference_path)
    finally:
        if temporary.exists():
            temporary.unlink()
    print(json.dumps({"reference": str(reference_path), "results": results}, allow_nan=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("/app/data/allen"))
    parser.add_argument("--reference", type=Path, default=TASK / "tests/reference.npz")
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.reference)
