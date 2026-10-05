"""Offline image/entrypoint contract without downloading any scientific data."""
from pathlib import Path
import re
import tomllib

TASK = Path(__file__).resolve().parents[1]


def test_runtime_offline_and_honest_role():
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["environment"]["allow_internet"] is False
    assert config["environment"]["gpus"] == 0
    assert config["metadata"]["difficulty"] == "easy"
    assert "/app/data/somato/data_manifest.json" in config["artifacts"]


def test_runtime_only_copies_selected_source_and_public_contract():
    docker = (TASK / "environment" / "Dockerfile").read_text()
    assert "ubuntu:24.04@sha256:" in docker
    runtime = docker.split("FROM dependencies AS runtime\n", 1)[1]
    assert runtime.splitlines() == [
        "COPY --from=source /app/data/somato /app/data/somato",
        "COPY method_contract.json /app/method_contract.json",
    ]
    assert "pytest==8.4.1 pytest-json-ctrf==0.3.5" in docker


def test_verifier_uses_python3_and_no_runtime_install():
    script = (TASK / "tests" / "test.sh").read_text()
    assert re.search(r"\bpython3\s+-m\s+pytest\b", script)
    assert not re.search(r"\b(python|pip|pip3|uvx|curl|wget|apt-get)\b", script)
    assert "/logs/verifier/reward.txt" in script


def test_no_hidden_difficulty_or_sign_claims_in_proposal():
    proposal = (TASK / "proposal.md").read_text()
    for old in ("un-cued", "25x", "hard`", "443.6", "−17.7"):
        assert old not in proposal
    assert "difficulty unmeasured" in proposal
