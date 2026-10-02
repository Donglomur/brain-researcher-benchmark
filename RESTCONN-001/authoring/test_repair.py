"""Packaging regressions; never read scientific source values or an answer bank."""
import ast
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_offline_task_and_harvest_contract():
    config = tomllib.loads((ROOT / "task.toml").read_text())
    assert config["environment"]["allow_internet"] is False
    assert config["environment"]["gpus"] == 0
    assert config["metadata"]["task_id"] == "RESTCONN-001"
    assert config["metadata"]["difficulty"] == "easy"
    assert set(config["artifacts"]) == {
        "/app/output", "/app/source_manifest.json", "/app/method_contract.json",
        "/app/output_schema.json"}
    script = (ROOT / "tests/test.sh").read_text()
    assert "python3 -I -B" in script and "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1" in script
    assert "apt-get" not in script and "curl" not in script and "uvx" not in script
    assert '"/tests/test_actual_outputs.py"' not in script
    assert '"/tests/test_outputs.py"' in script


def test_public_source_inventory_is_minimal_and_identity_bound():
    raw = (ROOT / "environment/source_manifest.json").read_bytes()
    manifest = json.loads(raw)
    assert hashlib.sha256(raw).hexdigest() == "465cfd8f113be362b39172782713c504432c51e529d82f222bda8ba9f1fb734e"
    assert manifest["n_files"] == len(manifest["files"]) == 10
    assert manifest["total_bytes"] == sum(r["size_bytes"] for r in manifest["files"]) == 66795095
    assert manifest["participant_ids"] == ["0010064"]
    assert len(manifest["archives"]) == 3
    assert sum(r["role"] == "bold" for r in manifest["files"]) == 1
    assert sum(r["role"] == "atlas_image" for r in manifest["files"]) == 1


def test_runtime_image_does_not_copy_solution_tests_or_answer_bank():
    dockerfile = (ROOT / "environment/Dockerfile").read_text()
    assert "ubuntu:24.04@sha256:" in dockerfile
    assert "FROM dependencies AS source" in dockerfile
    assert "COPY --from=source /app/data/restconn /app/data/restconn" in dockerfile
    for line in dockerfile.splitlines():
        if line.startswith("COPY "):
            assert all(word not in line for word in ("solution", "tests", "reference.npz"))
    assert not (ROOT / "tests/reference.npz").exists()


def test_grader_source_route_cannot_import_oracle_or_stager():
    for name in ("source_reference.py", "source_numerics.py", "proof_of_work.py"):
        tree = ast.parse((ROOT / "tests" / name).read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import): imports.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom): imports.append(node.module or "")
        assert not any(part in {"solution", "stage_data", "compute", "core"}
                       for module in imports for part in module.split("."))
