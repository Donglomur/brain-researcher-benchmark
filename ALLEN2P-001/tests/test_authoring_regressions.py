"""Packaging-only check; not original-source scientific evidence."""
from pathlib import Path

def test_python3_offline_verifier_entrypoint():
    value=Path(__file__).with_name("test.sh").read_text()
    assert "python3 -m pytest" in value
    for forbidden in ("uvx", "pip install", "apt-get", "curl", "wget", "source $HOME"):
        assert forbidden not in value
