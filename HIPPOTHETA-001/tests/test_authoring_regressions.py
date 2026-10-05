"""Packaging mechanics only; these are not original-source validation."""
from pathlib import Path


def test_verifier_entrypoint_is_offline_python3():
    script = Path(__file__).with_name("test.sh").read_text()
    assert "python3 -m pytest" in script
    assert all(token not in script for token in ("pip install", "apt-get", "curl", "uvx", "$HOME"))
    assert "1.0" in script and "0.0" in script
