"""Authoring invariants only; never opens the recordings or a numerical bank."""
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / "environment"


def test_public_contract_bytes_and_source_complete():
    pins = {
        "source_manifest.json": "70000c5c93c2c43f1e7968feb38aaebb4e7622a5f6d2ec1167191337614ef950",
        "method_contract.json": "d86db9e607dfe1668b2aa6883c83a463895beb352712c8d6a53ebfe895e99234",
        "output_schema.json": "7beec618b63f86fbe66d6223be7e3702ca3bdb8bcc384ed2c651fbf02ccd8b8b",
    }
    for name, digest in pins.items():
        assert hashlib.sha256((ENV / name).read_bytes()).hexdigest() == digest
    source = json.loads((ENV / "source_manifest.json").read_bytes())
    assert len(source["files"]) == 131
    assert sum(row["size_bytes"] for row in source["files"]) == 2197402958
    assert all(len(row["sha256"]) == 64 for row in source["files"])


def test_offline_method_control_not_difficulty_claim():
    task = tomllib.loads((ROOT / "task.toml").read_text())
    assert task["environment"]["allow_internet"] is False
    assert task["environment"]["gpus"] == 0
    assert task["metadata"]["difficulty"] == "easy"
    assert "sensitivity" in task["metadata"]["title"]
    instruction = (ROOT / "instruction.md").read_text()
    assert "/app/method_contract.json" in instruction and "/app/output_schema.json" in instruction
    assert "Scoring is binary" in instruction


def test_no_shipped_numerical_bank_or_runtime_oracle_copy():
    assert not (ROOT / "tests/reference.npz").exists()
    dockerfile = (ENV / "Dockerfile").read_text()
    assert "FROM ubuntu:24.04@sha256:" in dockerfile
    for line in dockerfile.splitlines():
        if line.strip().startswith("COPY"):
            assert not any(name in line for name in ("solution/", "tests/", "reference.npz"))
    assert "allow_pickle=True" not in (ROOT / "tests/artifact_reader.py").read_text()


def test_consistent_source_and_method_claim():
    method = json.loads((ENV / "method_contract.json").read_bytes())
    schema = json.loads((ENV / "output_schema.json").read_bytes())
    assert len(method["participant_ids"]) == 20
    assert len(method["spatial"]["roi_ids"]) == 111
    assert method["design"]["initial_full_rank"] is False
    assert method["groups"]["significance_or_sign_requirement"] is False
    assert method["source_manifest_sha256"] == schema["source_manifest_sha256"]
    assert len(schema["serialization"]["required_files"]) == 8
