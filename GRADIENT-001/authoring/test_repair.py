"""Source-free packaging checks; no historical numerical reference is loaded."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_retired_builder_is_import_safe_and_refuses_execution():
    path = ROOT / "authoring/build_reference_v2.py"
    spec = importlib.util.spec_from_file_location("retired_gradient_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit, match="retired"):
        module.main()


def test_no_packaged_historical_answer_banks():
    for name in ("reference.npz", "reference_v2.npz"):
        path = ROOT / "tests" / name
        assert not path.exists() and not path.is_symlink()


def test_final_public_source_contract_is_bound():
    env = ROOT / "environment"
    manifest_raw = (env / "source_manifest.json").read_bytes()
    manifest = json.loads(manifest_raw)
    method = json.loads((env / "method_contract.json").read_bytes())
    assert method["source"]["manifest_sha256"] == hashlib.sha256(manifest_raw).hexdigest()
    assert method["source"]["participant_ids"] == manifest["cohort"]["ordered_participant_ids"]
    assert len(set(method["source"]["participant_ids"])) == 20
    assert len(manifest["files"]) == manifest["n_files"] == 46
    assert sum(row["size_bytes"] for row in manifest["files"]) == manifest["total_bytes"] == 124132750
    assert method["source"]["n_frames"] == 168
    assert method["source"]["n_parcels"] == 400
    assert method["affinity"]["retained_per_row"] == 40


def test_complete_eight_artifact_schema():
    schema = json.loads((ROOT / "environment/output_schema.json").read_bytes())
    assert set(schema["files"]) == {"cohort.csv", "parcels.csv", "gradient_arrays.npz",
        "configurations.csv", "per_subject.csv", "results.json", "run_metadata.json", "findings.md"}
    assert schema["parcels_csv"]["rows"] == 8000
    assert schema["configurations_csv"]["rows"] == 35


def test_offline_pinned_build_and_no_answer_code_in_runtime():
    docker = (ROOT / "environment/Dockerfile").read_text()
    assert "ubuntu:24.04@sha256:" in docker
    assert "stage_data.py" in docker
    for line in docker.splitlines():
        if line.lstrip().upper().startswith("COPY "):
            assert "solution" not in line and "tests" not in line and "reference" not in line
    config = tomllib.loads((ROOT / "task.toml").read_text())
    assert config["environment"]["allow_internet"] is False
    assert config["environment"]["gpus"] == 0


def test_verifier_does_not_import_oracle_or_network_fetchers():
    blocked = {"solution", "compute", "core", "source_reader", "brainspace", "stage_data", "requests", "urllib"}
    for path in (ROOT / "tests").glob("*.py"):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                assert all(alias.name.split(".")[0] not in blocked for alias in node.names), path
            elif isinstance(node, ast.ImportFrom):
                assert (node.module or "").split(".")[0] not in blocked, path
