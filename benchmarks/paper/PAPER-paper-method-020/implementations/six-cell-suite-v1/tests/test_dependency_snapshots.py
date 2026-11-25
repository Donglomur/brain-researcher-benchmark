"""Generated dependency-load replacements; no authentic traces or model calls."""
from copy import deepcopy
import hashlib
import importlib.machinery
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest import mock

SUITE_PATH = Path(__file__).resolve().parents[1] / "suite.py"
SENTINEL = "UNVERIFIED_DEPENDENCY_EXECUTED"


def load_suite():
    spec = importlib.util.spec_from_file_location("neurona_snapshot_control_suite", SUITE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fixture(suite_module):
    source = suite_module.source
    vocabulary = ["yes", "no", "ride"]
    queries = [
        {"id": "yes-query", "answer": "yes", "query_sha256": "a" * 64,
         "domain_functions": source.BUILTINS + ["cat"]},
        {"id": "ride-query", "answer": "ride", "query_sha256": "b" * 64,
         "domain_functions": source.BUILTINS + ["cat"]},
    ]
    manifest = {
        "schema": source.SCHEMA, "engineering_fixture": True,
        "source_code_revision": source.legacy.CODE_REVISION,
        "data_revision": source.legacy.DATA_REVISION,
        "training_manifest_sha256": "c" * 64,
        "train_domain_functions": source.BUILTINS + ["cat"],
        "records": [{"path": "CSI1/test/4804.npy", "source_sha256": "d" * 64,
                     "queries": queries}],
    }
    cells = []
    for access in suite_module.ACCESS:
        for condition in suite_module.CONDITIONS:
            run = {
                "manifest_sha256": source.digest(manifest), "train_hop": "all",
                "checkpoint_sha256": "e" * 64, "selection_policy": "generated-control",
                "access_condition": access, "neural_condition": condition,
                "vocabulary_sha256": source.digest(vocabulary),
                "training_monitor": [
                    {"id": "yes-query", "outcome": "returned", "execution": {"kind": "bool", "value": 1}},
                    {"id": "ride-query", "outcome": "returned", "execution": {"kind": "vocab", "value": [0, 0, 1]}},
                ],
                "posthoc": [
                    {"id": "yes-query", "outcome": "returned", "pred_answer": "yes"},
                    {"id": "ride-query", "outcome": "returned", "pred_answer": "ride"},
                ],
            }
            declarations = {name: "1" * 64 for name in suite_module.DECLARATIONS}
            declarations["author_code_sha256"] = None if access == "paper_data" else "2" * 64
            cells.append({"run": run, "declarations": declarations})
    suite = {"schema": suite_module.SCHEMA, "comparison_plan_sha256": "3" * 64,
             "control_design": suite_module.ABLATION_DESIGN, "cells": cells}
    return manifest, suite, vocabulary


class DependencySnapshotTests(unittest.TestCase):
    def changed_load(self, relative):
        target = SUITE_PATH.parent.parent / relative
        raw = target.read_bytes()
        changed = raw + ("\n" + SENTINEL + " = True\n").encode()
        original_get_code = importlib.machinery.SourceFileLoader.get_code

        def replacement(loader, fullname):
            if Path(loader.path) == target:
                return compile(changed, str(target), "exec")
            return original_get_code(loader, fullname)

        # The authentication reads the original bytes. Only a later path loader
        # sees the replacement, modelling a changed load after hash acceptance.
        with mock.patch.object(importlib.machinery.SourceFileLoader, "get_code", replacement):
            loaded = load_suite()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), loaded._PINS[relative])
        return loaded

    def test_source_scorer_executes_authenticated_snapshot(self):
        loaded = self.changed_load("source-scoring-v2/source_score.py")
        self.assertFalse(getattr(loaded.source, SENTINEL, False))

    def test_inherited_evaluator_executes_authenticated_snapshot(self):
        loaded = self.changed_load("initial-evaluator-v1/evaluator.py")
        self.assertFalse(getattr(loaded.source.legacy, SENTINEL, False))

    def test_wrong_dependency_hash_refused_before_execution(self):
        target = SUITE_PATH.parent.parent / "initial-evaluator-v1/evaluator.py"
        original_read = Path.read_bytes

        def changed_read(path):
            raw = original_read(path)
            return raw + b"\n# altered generated control\n" if path == target else raw

        with mock.patch.object(Path, "read_bytes", changed_read):
            with self.assertRaisesRegex(ValueError, "dependency identity differs"):
                load_suite()

    def test_valid_complete_suite_and_paired_diagnostics_are_preserved(self):
        loaded = load_suite()
        manifest, suite, vocabulary = fixture(loaded)
        report = loaded.compare_suites(manifest, suite, deepcopy(suite), vocabulary)
        for access in loaded.ACCESS:
            for condition in loaded.CONDITIONS:
                cell = report["candidate"]["cells"][access][condition]
                self.assertEqual(cell["posthoc"]["Overall"]["accuracy"], 1.0)
                self.assertEqual(cell["posthoc"]["Overall"]["queries"], 2)
                self.assertEqual(cell["training_monitor"]["accuracy"], 1.0)
                delta = report["candidate_minus_reference_by_cell"][access][condition]
                self.assertEqual(delta["posthoc"]["Overall"]["right_minus_left"], 0.0)
                self.assertFalse(report["improvement_established"])
        # The standalone scorer retains its normal source-loading route.
        source_path = SUITE_PATH.parent.parent / "source-scoring-v2/source_score.py"
        spec = importlib.util.spec_from_file_location("neurona_snapshot_standalone", source_path)
        standalone = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(standalone)
        self.assertEqual(standalone.score(manifest, suite["cells"][0]["run"], vocabulary)["posthoc"]["Overall"]["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
