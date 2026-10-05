"""The verifier must start in the declared Ubuntu Python3-only image."""
from pathlib import Path
import shutil
import subprocess


def test_offline_verifier_uses_installed_python3():
    script = Path(__file__).parents[1] / "tests/test.sh"
    text = script.read_text()
    assert shutil.which("python3")
    assert "if python3 -m pytest " in text
    assert "if python -m pytest " not in text
    assert not any(command in text for command in ("apt-get", "curl ", "uvx "))
    subprocess.run(["bash", "-n", str(script)], check=True)
