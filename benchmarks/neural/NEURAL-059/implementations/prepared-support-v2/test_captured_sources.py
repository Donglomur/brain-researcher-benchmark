"""Generated source-custody controls; no recordings, targets or models."""
from contextlib import contextmanager
import hashlib
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
LOADER_PATH = HERE / "_retained.py"
LIVE_IMPL = HERE


def loader():
    spec = importlib.util.spec_from_file_location("_n059_source_control_loader", LOADER_PATH)
    module = importlib.util.module_from_spec(spec)
    exec(compile(LOADER_PATH.read_bytes(), str(LOADER_PATH), "exec"), module.__dict__)
    return module


@contextmanager
def namespace(name):
    names = (name, name + ".contracts", name + ".diagnostics", name + ".evaluation")
    missing = object()
    previous = {key: sys.modules.pop(key, missing) for key in names}
    try:
        yield names
    finally:
        for key, module in previous.items():
            if module is missing:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module


@contextmanager
def generated_sources():
    module = loader()
    with tempfile.TemporaryDirectory() as directory, namespace(module.NAME):
        root = Path(directory) / "retained"
        here = Path(directory) / "successor"
        root.mkdir()
        here.mkdir()
        bodies = {"__init__.py": b'"""Generated package."""\n',
                  "contracts.py": b'VALUE = "original-contracts"\n',
                  "diagnostics.py": b'VALUE = "original-diagnostics"\n',
                  "evaluation.py": b'VALUE = "unused-lineage"\n'}
        for name, body in bodies.items():
            (root / name).write_bytes(body)
        body = b'from .diagnostics import VALUE\n'
        (here / "evaluation.py").write_bytes(body)
        module.ROOT, module.HERE = root, here
        module.PINS = {name: hashlib.sha256(value).hexdigest() for name, value in bodies.items()}
        module.EVALUATION_SHA256 = hashlib.sha256(body).hexdigest()
        yield module


class CapturedSourceTests(unittest.TestCase):
    def test_unchanged_generated_dependencies(self):
        with generated_sources() as module:
            contracts, evaluation = module.load()
            self.assertEqual(contracts.VALUE, "original-contracts")
            self.assertEqual(evaluation.VALUE, "original-diagnostics")
            self.assertEqual(evaluation.__package__, module.NAME)
            self.assertEqual(evaluation.__file__, str(module.HERE / "evaluation.py"))

    def test_replacement_after_authentication_uses_captured_bytes(self):
        with generated_sources() as module:
            original_read = Path.read_bytes
            changed = []
            def replacing_read(path):
                body = original_read(path)
                if path == module.HERE / "evaluation.py":
                    (module.ROOT / "contracts.py").write_bytes(b'VALUE = "replacement"\n')
                    changed.append(True)
                return body
            with patch.object(Path, "read_bytes", replacing_read):
                contracts, _ = module.load()
            self.assertEqual(changed, [True])
            self.assertEqual(contracts.VALUE, "original-contracts")

    def test_preexisting_namespace_cannot_replace_authenticated_source(self):
        with generated_sources() as module:
            previous = {}
            for suffix in ("", ".contracts", ".diagnostics", ".evaluation"):
                name = module.NAME + suffix
                existing = types.ModuleType(name)
                existing.VALUE = "unrelated-cached-module"
                sys.modules[name] = previous[name] = existing
            contracts, evaluation = module.load()
            self.assertEqual(contracts.VALUE, "original-contracts")
            self.assertEqual(evaluation.VALUE, "original-diagnostics")
            for name, existing in previous.items():
                self.assertIs(sys.modules[name], existing)

    def test_changed_source_is_refused_before_execution(self):
        with generated_sources() as module:
            (module.ROOT / "contracts.py").write_bytes(b'raise AssertionError("must-not-execute")\n')
            with self.assertRaisesRegex(ValueError, "retained_scientific_source_changed:contracts.py"):
                module.load()
            self.assertNotIn(module.NAME, sys.modules)

    def test_execution_failure_restores_operator_namespace(self):
        with generated_sources() as module:
            body = b'raise RuntimeError("generated-execution-failure")\n'
            (module.HERE / "evaluation.py").write_bytes(body)
            module.EVALUATION_SHA256 = hashlib.sha256(body).hexdigest()
            prior = types.ModuleType(module.NAME + ".contracts")
            sys.modules[prior.__name__] = prior
            with self.assertRaisesRegex(RuntimeError, "generated-execution-failure"):
                module.load()
            self.assertNotIn(module.NAME, sys.modules)
            self.assertNotIn(module.NAME + ".diagnostics", sys.modules)
            self.assertNotIn(module.NAME + ".evaluation", sys.modules)
            self.assertIs(sys.modules[prior.__name__], prior)

    def test_real_source_generated_probability_arithmetic_unchanged(self):
        module = loader()
        module.HERE = LIVE_IMPL
        module.ROOT = LIVE_IMPL.parent / "registered-runtime/complete-process-v1/scientific"
        with namespace(module.NAME):
            _, evaluation = module.load()
            self.assertEqual(len(evaluation.ROSTER), 29)
            row = evaluation.trial_score(1, .25)
            self.assertEqual(row["brier"], .5625)
            self.assertEqual(row["log_loss"], -math.log(.25))
            result = evaluation.metrics_from_pairs([(0, .25), (1, .75)])
            self.assertEqual(result["scores"]["auc"], 1.)
            self.assertEqual(result["scores"]["balanced_accuracy"], 1.)
            self.assertEqual(result["scores"]["brier"], .0625)
            self.assertEqual(result["scores"]["log_loss"], -math.log(.75))


if __name__ == "__main__":
    unittest.main()
