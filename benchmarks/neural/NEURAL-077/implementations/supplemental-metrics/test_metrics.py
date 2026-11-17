"""Generated controls and independent scalar-oracle comparisons; no real NumPy."""
import builtins
import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import random
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location("generated_" + name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metric, scalar, evaluator = [load(name) for name in ("supplemental_metrics", "scalar_oracle", "evaluator")]
ANCHORS = json.loads((HERE / "SCALAR_ANCHORS.json").read_bytes())


class Truths(list):
    def all(self):
        return all(self)

    def __and__(self, other):
        return Truths(a and b for a, b in zip(self, other))


class GeneratedArray:
    """Tiny generated validation shim, not a numerical library or evaluator."""
    def __init__(self, values):
        self.values = list(values)
        self.ndim, self.shape = 1, (len(self.values),)
        kind = "f" if any(type(v) is float for v in self.values) else "i"
        self.dtype = SimpleNamespace(kind=kind, itemsize=8)

    def __len__(self):
        return len(self.values)

    def __iter__(self):
        return iter(self.values)

    def __ge__(self, other):
        return Truths(v >= other for v in self.values)

    def __le__(self, other):
        return Truths(v <= other for v in self.values)


def canonical_directory():
    override = os.environ.get("NEURAL077_CANONICAL_DIR")
    if override:
        return Path(override)
    if (HERE / "canonical" / "metrics.py").is_file():
        return HERE / "canonical"
    return HERE.parents[4] / "benchmarks/neuroscience/neural-077"


def canonical_scalar_source():
    directory = canonical_directory()
    body = (directory / "metrics.py").read_bytes()
    pin = evaluator.CANONICAL_PINS["metrics.py"]
    assert (len(body), hashlib.sha256(body).hexdigest()) == (pin["bytes"], pin["sha256"])
    fake_numpy = SimpleNamespace(
        all=lambda values: all(values),
        asarray=lambda v: v if isinstance(v, GeneratedArray) else GeneratedArray(v),
        isfinite=lambda v: Truths(math.isfinite(x) for x in v),
        isin=lambda v, choices: Truths(x in choices for x in v))
    original_import = builtins.__import__
    def generated_import(name, *args, **kwargs):
        return fake_numpy if name == "numpy" else original_import(name, *args, **kwargs)
    namespace = {"__builtins__": dict(vars(builtins), __import__=generated_import)}
    exec(compile(body, "pinned_canonical_metrics_generated_checks", "exec"), namespace)
    return namespace["score_candidate"]


def panel():
    cases = metric.CASES
    labels = {c: [1] * 40 + [0] * 160 for c in cases}
    probabilities = {cases[0]: [0.4] * 40 + [0.1] * 160,
                     cases[1]: [0.2] * 40 + [0.3] * 160}
    loss = -0.2 * math.log(0.2) - 0.8 * math.log(0.8)
    rows = [{"person_id": c, "n": 200, "n_target": 40, "n_non_target": 160,
             "balanced_accuracy": 0.5, "log_loss": loss} for c in cases]
    refs = {"arms": {name: {"per_person": copy.deepcopy(rows),
                            "participant_macro_balanced_accuracy": 0.5,
                            "participant_macro_log_loss": loss}
                     for name in ("prior", "eeg", "eog_site", "gross_amplitude", "behavioral_history", "eeg_history")}}
    return probabilities, labels, refs


class ArithmeticTests(unittest.TestCase):
    def test_all_independent_hand_anchors(self):
        for anchor in ANCHORS["valid"]:
            with self.subTest(anchor=anchor["name"]):
                expected = anchor["expected"]
                self.assertEqual(scalar.oracle(anchor["labels"], anchor["probabilities"]), expected)
                observed = metric.person(anchor["labels"], anchor["probabilities"])
                for key in expected:
                    self.assertAlmostEqual(observed[key], expected[key], places=15)

    def test_all_invalid_anchors_and_nonfinite_inputs(self):
        invalid = [(a["labels"], a["probabilities"]) for a in ANCHORS["invalid"]]
        invalid += [([0, 1], [0.1, v]) for v in (float("nan"), float("inf"), float("-inf"))]
        for y, p in invalid:
            for fn in (metric.person, scalar.oracle):
                with self.assertRaises(ValueError):
                    fn(y, p)

    def test_generated_tie_panels_match_independent_pairwise_oracle(self):
        rng = random.Random(77)
        grid = [0.0, 0.1, math.nextafter(0.2, 0.0), 0.2, math.nextafter(0.2, 1.0), 0.7, 1.0]
        for n in (2, 3, 8, 40, 200):
            for _ in range(16):
                labels = [0, 1] + [rng.randrange(2) for __ in range(n - 2)]
                values = [rng.choice(grid) for __ in range(n)]
                actual, expected = metric.person(labels, values), scalar.oracle(labels, values)
                self.assertEqual(actual, expected)

    def test_permutation_invariance_and_no_probability_mutation(self):
        y, p = [0, 1, 1, 0], [0.2, 0.2, 0.9, 0.1]
        original = p[:]
        self.assertEqual(metric.person(y, p), metric.person(y[::-1], p[::-1]))
        self.assertEqual(p, original)

    def test_equal_person_auc_is_not_pooled_trial_auc(self):
        p, y, _ = panel()
        summary = metric.summarize(p, y)
        self.assertEqual(summary["participant_macro_roc_auc"], 0.5)
        pooled = metric.person(y[metric.CASES[0]] + y[metric.CASES[1]], p[metric.CASES[0]] + p[metric.CASES[1]])
        self.assertEqual(pooled["roc_auc"], 0.75)
        self.assertEqual(summary["participant_macro_balanced_accuracy_at_0_2"], 0.75)

    def test_missing_or_undefined_person_never_dropped(self):
        p, y, _ = panel()
        for mode in ("missing", "one_class", "support", "short"):
            pp, yy = copy.deepcopy(p), copy.deepcopy(y)
            if mode == "missing":
                pp.pop(metric.CASES[1])
            elif mode == "one_class":
                yy[metric.CASES[1]] = [0] * 200
            elif mode == "support":
                yy[metric.CASES[1]][0] = 0
            else:
                pp[metric.CASES[1]].pop()
            with self.assertRaises(ValueError):
                metric.summarize(pp, yy)


class CompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.canonical_score = staticmethod(canonical_scalar_source())

    def test_exact_canonical_primary_preserved_with_only_two_private_loads(self):
        p, y, refs = panel()
        expected = self.canonical_score(p, lambda c: y[c], refs)
        calls = []
        def loader(case):
            calls.append(case)
            return y[case]
        result = evaluator._merge_supplemental(p, loader, refs, self.canonical_score)
        self.assertEqual({k: result[k] for k in expected}, expected)
        self.assertEqual(set(result) - set(expected), {"supplemental_metrics"})
        self.assertEqual(calls, list(metric.CASES))
        self.assertEqual(result["target_loader_invocations"], 2)
        self.assertEqual(result["supplemental_metrics"]["additional_private_loader_invocations"], 0)
        self.assertEqual(result["primary_metric"], "participant_macro_balanced_accuracy")
        self.assertEqual(result["decision_threshold"], 0.5)

    def test_float_labels_not_laundered_before_canonical_validation(self):
        p, y, refs = panel()
        calls = []
        def loader(case):
            calls.append(case)
            return [float(v) for v in y[case]]
        with patch.object(evaluator.supplemental, "summarize") as summary:
            with self.assertRaises(ValueError):
                evaluator._merge_supplemental(p, loader, refs, self.canonical_score)
            summary.assert_not_called()
        self.assertEqual(calls, [metric.CASES[0]])

    def test_invalid_second_public_vector_prevents_any_private_load(self):
        p, y, refs = panel()
        p[metric.CASES[1]][-1] = float("nan")
        with patch.object(self, "canonical_score") as score:
            with self.assertRaises(ValueError):
                evaluator._merge_supplemental(p, lambda c: self.fail("private access"), refs, score)
            score.assert_not_called()

    def test_invalid_second_private_case_returns_no_supplement(self):
        p, y, refs = panel()
        y[metric.CASES[1]][0] = 2
        calls = []
        def loader(case):
            calls.append(case)
            return y[case]
        with patch.object(evaluator.supplemental, "summarize") as summary:
            with self.assertRaises(ValueError):
                evaluator._merge_supplemental(p, loader, refs, self.canonical_score)
            summary.assert_not_called()
        self.assertEqual(calls, list(metric.CASES))

    def test_bad_reference_rejected_before_private_loading(self):
        p, _, _ = panel()
        with self.assertRaises(ValueError):
            evaluator._merge_supplemental(p, lambda c: self.fail("private access"), {}, self.canonical_score)

    def test_duplicate_loader_request_refused(self):
        p, y, refs = panel()
        calls = []
        def duplicate(ordered, loader, references):
            loader(metric.CASES[0])
            loader(metric.CASES[0])
        def loader(case):
            calls.append(case)
            return y[case]
        with self.assertRaises(ValueError):
            evaluator._merge_supplemental(p, loader, refs, duplicate)
        self.assertEqual(len(calls), 1)

    def test_resource_failure_propagates_without_second_private_load(self):
        p, _, refs = panel()
        calls = []
        def fail(case):
            calls.append(case)
            raise MemoryError("generated allocation failure")
        with self.assertRaises(MemoryError):
            evaluator._merge_supplemental(p, fail, refs, self.canonical_score)
        self.assertEqual(len(calls), 1)


class EntryBoundaryTests(unittest.TestCase):
    def test_canonical_override_works_at_shallow_component_path(self):
        with patch.dict(os.environ, {"NEURAL077_CANONICAL_DIR": "/generated/canonical"}), patch.dict(globals(), {"HERE": Path("/component")}):
            self.assertEqual(canonical_directory(), Path("/generated/canonical"))

    def test_observed_only_condition_rejects_before_file_or_private_access(self):
        with patch.object(evaluator, "pinned_bytes") as reader:
            with self.assertRaises(ValueError):
                evaluator.evaluate_submission("unused", {}, lambda c: self.fail("private access"), {}, "unused", submission_pin={}, condition="signal_reassigned")
            reader.assert_not_called()

    def test_whole_public_validation_and_recheck_precede_private_access(self):
        p, y, refs = panel()
        ids = {c: [f"{c}-{i:04d}" for i in range(200)] for c in metric.CASES}
        events = []
        def pin(*args):
            events.append("pin")
            return b"generated"
        def validate(*args):
            events.append("validate_all_public")
            return p
        def private(case):
            events.append("private:" + case)
            return y[case]
        modules = (SimpleNamespace(validate=validate), SimpleNamespace(score_candidate=canonical_scalar_source()))
        with patch.object(evaluator, "pinned_bytes", side_effect=pin), patch.object(evaluator, "load_canonical", return_value=modules):
            result = evaluator.evaluate_submission("generated", ids, private, refs, "generated", submission_pin={}, condition="observed_signal")
        self.assertEqual(events[:3], ["pin", "validate_all_public", "pin"])
        self.assertEqual(events[3:], ["private:" + c for c in metric.CASES])
        self.assertEqual(result["supplemental_metrics"]["participant_macro_roc_auc"], 0.5)

    def test_validation_failure_never_calls_private_loader(self):
        ids = {c: list(range(200)) for c in metric.CASES}
        def reject(*args):
            raise ValueError("generated bad NPZ")
        modules = (SimpleNamespace(validate=reject), SimpleNamespace(score_candidate=lambda *args: self.fail("score")))
        with patch.object(evaluator, "pinned_bytes", return_value=b"generated"), patch.object(evaluator, "load_canonical", return_value=modules):
            with self.assertRaises(ValueError):
                evaluator.evaluate_submission("unused", ids, lambda c: self.fail("private access"), {}, "unused", submission_pin={}, condition="observed_signal")

    def test_both_canonical_sources_authenticated_before_either_executes(self):
        with patch.object(evaluator, "pinned_bytes", side_effect=[b"raise AssertionError('premature execution')", ValueError("generated bad second source")]):
            with self.assertRaises(ValueError):
                evaluator.load_canonical("unused")

    def test_generated_pin_and_fifo_no_open(self):
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as directory:
            path = Path(directory) / "generated"
            body = b"generated source control"
            path.write_bytes(body)
            pin = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            self.assertEqual(evaluator.pinned_bytes(path, pin, 100), body)
            with self.assertRaises(ValueError):
                evaluator.pinned_bytes(path, {"bytes": len(body), "sha256": "0" * 64}, 100)
            fifo = Path(directory) / "fifo"
            os.mkfifo(fifo)
            with patch.object(evaluator.os, "open", side_effect=AssertionError("must not open FIFO")) as opened:
                with self.assertRaises(ValueError):
                    evaluator.pinned_bytes(fifo, {"bytes": 1, "sha256": "0" * 64}, 100)
                opened.assert_not_called()


def tearDownModule():
    if any(n == "numpy" or n.startswith("numpy.") or n == "scipy" or n.startswith("scipy.") for n in sys.modules):
        raise AssertionError("real numerical dependency imported during generated-only source checks")


if __name__ == "__main__":
    unittest.main(verbosity=2)
