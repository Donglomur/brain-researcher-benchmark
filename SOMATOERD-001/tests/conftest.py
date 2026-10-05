"""Only graded-output collection requires the private evaluation bank."""
from pathlib import Path
import runpy
import pytest


def pytest_collect_file(file_path, parent):
    # Do not gate source-free authoring tests that happen to live under tests/.
    target = Path(file_path).resolve()
    selected = []
    for argument in parent.config.args:
        path = Path(argument.split("::", 1)[0])
        if not path.is_absolute():
            path = Path(parent.config.invocation_params.dir) / path
        selected.append(path.resolve())
    requested = any(path == target or path in target.parents for path in selected)
    if target == Path(__file__).with_name("test_outputs.py").resolve() and requested:
        guard = runpy.run_path(str(Path(__file__).with_name("private_reference.py")))
        try:
            guard["require_reference"]()
        except guard["PrivateReferenceError"] as error:
            raise pytest.UsageError("PROVISIONING_ERROR: " + str(error)) from error
