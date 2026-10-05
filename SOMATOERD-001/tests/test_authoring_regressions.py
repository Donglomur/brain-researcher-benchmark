"""Do not recreate scientific positives by copying a reference bank.

Original sign-only fixtures are superseded by source-bound mechanical tests in
authoring/test_contract.py and genuine execution cases in test_real_outputs.py.
"""
from pathlib import Path


def test_no_runtime_download_or_implicit_python_binary():
    script=Path(__file__).with_name("test.sh").read_text()
    assert "python3 -m pytest" in script
    for forbidden in ("apt-get", "curl ", "uvx ", "pip install", "source $HOME"):
        assert forbidden not in script
