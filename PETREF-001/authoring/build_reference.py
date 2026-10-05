"""Build a bank only from a completed genuine source-data oracle receipt."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile

import numpy as np

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("petref_oracle", TASK / "solution/compute.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)


def build(output_dir, data_dir, destination):
    out = Path(output_dir)
    manifest, scans = oracle.load_source(data_dir)
    contract = oracle.metadata_contract(manifest)
    template = json.loads((TASK / "environment/method_contract.json").read_text())
    assert contract == template, "public method template differs from executed source contract"
    with np.load(out / "analysis_arrays.npz", allow_pickle=False) as receipt:
        arrays = {k: receipt[k].copy() for k in receipt.files if k.startswith("ref_")}
        candidates = json.loads(str(receipt["candidates_json"]))
    assert arrays["ref_params"].shape == (4, 3) and len(candidates) == 4
    assert arrays["ref_subject"].tolist() == [s for s, _ in oracle.SCANS]
    assert arrays["ref_session"].tolist() == [e for _, e in oracle.SCANS]
    source_arrays = {
        "ref_frame_scan": np.concatenate([np.full(len(s["mid"]), i) for i, s in enumerate(scans)]),
        "ref_frame_index": np.concatenate([np.arange(len(s["mid"])) for s in scans]),
        "ref_source_tacs": np.concatenate([s["tacs"] for s in scans]),
        "ref_reference_scale": np.array([s["scale"] for s in scans])}
    for key, name in [("frame_start_s", "start"), ("frame_end_s", "end"),
                      ("mid_time_min", "mid"), ("target", "target"), ("reference", "reference")]:
        source_arrays["ref_" + key] = np.concatenate([s[name] for s in scans])
    for key, expected in source_arrays.items():
        assert np.array_equal(arrays[key], expected), "source-derived receipt mismatch: " + key
    for i, (scan, params, attempts) in enumerate(zip(scans, arrays["ref_params"], candidates)):
        assert len(attempts) == 3
        valid = [v for v in attempts if v["success"]]
        assert valid, "no successful optimization attempt"
        selected = min(valid, key=lambda v: (v["normalized_sse"], v["start_index"]))
        assert np.array_equal(params, selected["params"])
        assert arrays["ref_selected_start_index"][i] == selected["start_index"]
        assert arrays["ref_optimizer_status"][i] == selected["optimizer_status"]
        assert arrays["ref_nfev"][i] == selected["nfev"]
        mask = arrays["ref_frame_scan"] == i
        prediction = oracle.srtm_predict(scan["mid"], scan["reference"], params)
        assert np.allclose(arrays["ref_prediction"][mask] / scan["scale"],
                           prediction / scan["scale"], atol=1e-12, rtol=1e-12)
        assert np.allclose(arrays["ref_residual"][mask], prediction - scan["target"],
                           atol=1e-9, rtol=1e-12)
        lower, upper = oracle.boundary_flags(params)
        assert np.array_equal(arrays["ref_lower_bound"][i], lower)
        assert np.array_equal(arrays["ref_upper_bound"][i], upper)
    results = oracle.summarize(arrays["ref_params"])
    assert results == json.loads((out / "pet_results.json").read_text())
    metadata = json.loads((out / "run_metadata.json").read_text())
    assert metadata == {**contract, "status": "ok", "per_scan_observations": oracle.observations(scans)}
    stats = {"pipeline_id": oracle.PIPELINE, "source_sha256": contract["source_sha256"],
             "metadata_contract": contract, "results": results,
             "per_scan_observations": oracle.observations(scans)}
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".npz", delete=False) as stream:
        temp = Path(stream.name)
    try:
        np.savez_compressed(temp, **arrays, ref_stats=json.dumps(stats, allow_nan=False))
        sys.path.insert(0, str(TASK / "tests"))
        from proof_of_work import load_reference
        from srtm_contract import validate_output_directory
        validate_output_directory(out, load_reference(temp))
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()
    print(json.dumps({"reference": str(destination), "n_frames": len(arrays["ref_target"]),
                      "results": results}, allow_nan=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--data-dir", default="/app/data/petref")
    parser.add_argument("--reference", default=str(TASK / "tests/reference.npz"))
    args = parser.parse_args()
    build(args.output_dir, args.data_dir, args.reference)
