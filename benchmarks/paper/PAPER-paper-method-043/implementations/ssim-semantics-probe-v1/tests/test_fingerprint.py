"""Focused review repairs: decorated source identities and nonnumeric output."""
import functools
import hashlib
import importlib.util
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("probe_repair", Path(__file__).resolve().parents[1]/"probe.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)


class FingerprintControls(unittest.TestCase):
    def wrapped_fixture(self, folder):
        implementation = folder/"implementation.py"
        wrapper = folder/"decorator.py"
        implementation.write_text("def calculate(x, y, **kw):\n    return 0.0\n")
        wrapper.write_text("def wrapped(x, y, **kw):\n    return target(x, y, **kw)\n")
        ns = {"__name__": "fixture_implementation"}
        exec(compile(implementation.read_bytes(), str(implementation), "exec"), ns)
        target = ns["calculate"]
        ns = {"__name__": "fixture_decorator", "target": target}
        exec(compile(wrapper.read_bytes(), str(wrapper), "exec"), ns)
        return functools.wraps(target)(ns["wrapped"]), implementation, wrapper

    def test_decorated_metadata_does_not_mislabel_wrapper_source(self):
        with tempfile.TemporaryDirectory() as directory:
            function, implementation, wrapper = self.wrapped_fixture(Path(directory))
            with patch.object(p.importlib.metadata, "version", side_effect=lambda name: "generated-version"):
                result = p.installed_runtime(function)
            self.assertEqual(result["called_callable"]["advertised_module"], "fixture_implementation")
            self.assertEqual(result["called_callable"]["source"]["path"], str(wrapper))
            self.assertEqual(result["unwrapped_implementation"]["source"]["path"], str(implementation))
            self.assertEqual(result["called_callable"]["code_filename"], str(wrapper))
            self.assertEqual(result["unwrapped_implementation"]["code_filename"], str(implementation))
            for record, path in zip(result["exposed_wrapped_chain"], (wrapper, implementation)):
                self.assertEqual(record["source"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(result["fingerprinted_unique_source_bytes"],
                             wrapper.stat().st_size + implementation.stat().st_size)

    def test_non_python_callable_has_explicit_unavailable_source(self):
        with patch.object(p.importlib.metadata, "version", return_value="generated-version"):
            result = p.installed_runtime(len)
        self.assertEqual(result["called_callable"]["source"]["status"], "unavailable")
        self.assertEqual(result["fingerprinted_unique_source_bytes"], 0)

    def test_wrapper_cycle_and_source_limit_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            function, _, _ = self.wrapped_fixture(Path(directory))
            with patch.object(p.importlib.metadata, "version", return_value="generated-version"):
                with patch.object(p.Path, "stat", return_value=SimpleNamespace(st_size=2*1024*1024+1)):
                    with self.assertRaisesRegex(p.ProbeError, "2MiB"):
                        p.installed_runtime(function)
                function.__wrapped__ = function
                with self.assertRaisesRegex(p.ProbeError, "cyclic"):
                    p.installed_runtime(function)

    def test_numeric_string_matching_reference_is_not_a_numeric_result(self):
        def fake(x, y, **kwargs):
            return str(p.reference_scores(x.tolist(), y.tolist())[p.MODES[0]])
        result = p.probe_callable(fake)
        self.assertIsNone(result["observed_semantics"])
        self.assertTrue(all(r["status"] == "rejected_or_raised" for r in result["observations"]))
        self.assertTrue(all("real numeric scalar" in r["exception_message"] for r in result["observations"]))


if __name__ == "__main__":
    unittest.main()
