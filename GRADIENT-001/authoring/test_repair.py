"""Source-free PR200 packaging checks adapted from fixed PR190 4cf8f988.

Only public documents and code are read. Historical artifact names below are
absence checks, never inputs. The retired builder is inspected, not imported.
Install this file at GRADIENT-001/authoring/test_repair.py for qualification.
"""
import ast
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT_PINS = {
    "source_manifest.json": "6afac2a68c4ca4847265ac5f890d56aa53a658e78f13b32e0f15f74007ed91c7",
    "method_contract.json": "c6575d9cc8a9f8d422dc3ec88c2a7aefa6ca971757180517948d2466fefce872",
    "output_schema.json": "e9ceb1a15180ed086290c4c7f5eb079038302b4dd5feabc3e99c9acb688bcf16",
}


def test_retired_builder_is_inert_refusal_stub():
    path = ROOT / "authoring/build_reference_v2.py"
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "86ec95badf6a27c07de223cde11884703b0d0f9f967da172ab0b96f84b3be2ab"
    tree = ast.parse(raw, filename=str(path))
    assert len(tree.body) == 3
    assert isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant)
    main = tree.body[1]
    assert isinstance(main, ast.FunctionDef) and main.name == "main" and len(main.body) == 1
    refusal = main.body[0]
    assert isinstance(refusal, ast.Raise) and isinstance(refusal.exc, ast.Call)
    assert isinstance(refusal.exc.func, ast.Name) and refusal.exc.func.id == "SystemExit"
    assert "retired" in ast.literal_eval(refusal.exc.args[0])
    assert isinstance(tree.body[2], ast.If)


def test_no_packaged_historical_answer_banks():
    for name in ("reference.npz", "reference_v2.npz"):
        path = ROOT / "tests" / name
        assert not path.exists() and not path.is_symlink()


def test_final_public_source_contract_is_bound():
    env = ROOT / "environment"
    payloads = {name: (env / name).read_bytes() for name in DOCUMENT_PINS}
    for name, digest in DOCUMENT_PINS.items():
        assert hashlib.sha256(payloads[name]).hexdigest() == digest
        assert (ROOT / "tests" / name).read_bytes() == payloads[name]
    manifest = json.loads(payloads["source_manifest.json"])
    method = json.loads(payloads["method_contract.json"])
    assert method["source"]["manifest_sha256"] == DOCUMENT_PINS["source_manifest.json"]
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
