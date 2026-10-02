"""Packaging checks without public-source or output reads."""
from pathlib import Path
import hashlib
import json
import tomllib

ROOT = Path(__file__).resolve().parents[1]

def test_public_contract_hashes_and_source_inventory():
    pins = {"source_manifest.json": "6a463aec353017c1c1b514fe2073b43088b1a9e8da4febcb0acfbd759ae397c6",
            "method_contract.json": "fb6a014e793013f41c80d8dcb3cbacd5d6567143dc6f8f8c93f339acd5eb136a",
            "output_schema.json": "6383d2043d09b8834a8b80133a877137111d904621a7777e1d7c5b4ee09a00c6"}
    for name, pin in pins.items():
        assert hashlib.sha256((ROOT/"environment"/name).read_bytes()).hexdigest() == pin
    manifest = json.loads((ROOT/"environment/source_manifest.json").read_text())
    assert len(manifest["files"]) == 48
    assert sum(row["size_bytes"] for row in manifest["files"]) == 749584263

def test_offline_cpu_and_harvest_contract():
    config = tomllib.loads((ROOT/"task.toml").read_text())
    assert config["environment"]["allow_internet"] is False
    assert config["environment"]["gpus"] == 0
    assert config["environment"]["cpus"] == 2
    assert config["metadata"]["difficulty"] == "easy"
    assert set(config["artifacts"]) == {"/app/output", "/app/source_manifest.json",
                                       "/app/method_contract.json", "/app/output_schema.json"}

def test_runtime_separates_private_assets_and_capture():
    docker = (ROOT/"environment/Dockerfile").read_text()
    runtime = docker.split("FROM dependencies AS runtime", 1)[1]
    assert "COPY --from=source /app/data/taskfc /app/data/taskfc" in runtime
    assert "/solution" not in runtime and "/tests" not in runtime and "/source_capture" not in runtime
    assert "1250s" in docker
    assert not (ROOT/"tests/reference.npz").exists()

def test_production_scoring_excludes_authoring_mutations_and_network_install():
    script = (ROOT/"tests/test.sh").read_text()
    assert "test_actual_outputs" not in script
    assert "test_source_bound_task_response_sensitivity" in (ROOT/"tests/test_outputs.py").read_text()
    assert not any(token in script for token in ("apt-get", "curl", "uvx", "pip install"))
    assert "python3 -I -B" in script and "failure" not in script.lower().split("if python3")[0]
