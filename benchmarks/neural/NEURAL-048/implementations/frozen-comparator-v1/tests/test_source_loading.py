"""Generated controls for authenticated evaluator loading; no animal data."""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
LOADERS = ("frozen-comparator-v1/scorer.py", "halfcycle-support-v1/support.py")


def load_copy(root, relative, *, replace_after_read=False, corrupt_before_read=False):
    dependency = root / "initial-evaluator-v1" / "evaluator.py"
    dependency.parent.mkdir(parents=True)
    source = (ROOT / "initial-evaluator-v1" / "evaluator.py").read_bytes()
    dependency.write_bytes(source + (b"\n" if corrupt_before_read else b""))
    target = root / relative
    target.parent.mkdir(parents=True)
    loader_body = (ROOT / relative).read_bytes()
    target.write_bytes(loader_body)
    original_read = Path.read_bytes
    replacements = []

    def consume_then_replace(path):
        body = original_read(path)
        if path == dependency and replace_after_read:
            dependency.write_bytes(source + b"\nUNAUTHENTICATED_REPLACEMENT = True\n")
            replacements.append(True)
        return body

    spec = importlib.util.spec_from_file_location("neural048_loader_control", target)
    module = importlib.util.module_from_spec(spec)
    with patch.object(Path, "read_bytes", consume_then_replace):
        exec(compile(loader_body, str(target), "exec"), module.__dict__)
    return module, dependency, replacements


class SourceLoadingTests(unittest.TestCase):
    def test_both_loaders_execute_the_authenticated_snapshot(self):
        for relative in LOADERS:
            with self.subTest(loader=relative), tempfile.TemporaryDirectory() as temporary:
                module, dependency, replacements = load_copy(
                    Path(temporary), relative, replace_after_read=True)
                self.assertEqual(replacements, [True])
                self.assertIn(b"UNAUTHENTICATED_REPLACEMENT", dependency.read_bytes())
                self.assertFalse(hasattr(module.legacy, "UNAUTHENTICATED_REPLACEMENT"),
                                 "unverified replacement source was executed")
                self.assertEqual(module.legacy.__file__, str(dependency))
                self.assertEqual(module.legacy.__spec__.origin, str(dependency))

    def test_both_loaders_reject_an_already_changed_dependency(self):
        for relative in LOADERS:
            with self.subTest(loader=relative), tempfile.TemporaryDirectory() as temporary:
                with self.assertRaisesRegex(RuntimeError, "independent review required"):
                    load_copy(Path(temporary), relative, corrupt_before_read=True)

    def test_stable_dependency_preserves_scoring_and_support_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            scorer, _, _ = load_copy(Path(temporary), LOADERS[0])
            reference = {
                "task_id": "NEURAL-048", "policy": copy.deepcopy(scorer.legacy.POLICY),
                "source_manifest_sha256": "a" * 64, "behavior_history_sha256": "b" * 64,
                "population_worm_ids": ["fit", "held"], "evaluation_worm_ids": ["held"],
                "folds": [{"id": "f", "train_worm_ids": ["fit"],
                           "validation_worm_ids": [], "test_worm_ids": ["held"]}],
                "episode_inventory": [{"worm_id": "held", "session_id": "s",
                                       "episode_id": "e", "observation_ids": ["q"]}],
                "observations": [{"id": "q", "worm_id": "held", "session_id": "s",
                                  "episode_id": "e", "fold_id": "f", "cutoff_ns": 1,
                                  "target_start_ns": 2, "target_end_ns": 3, "dorsal": 1}],
            }
            receipt = {"split_sha256": scorer.digest(reference["folds"]),
                       "behavior_history_sha256": "b" * 64, "frozen_recipe_sha256": "c" * 64,
                       "cpu_seconds": 0, "peak_memory_bytes": 1}
            comparator = scorer.freeze_behavior(
                reference, [{"id": "q", "behavior": .5}], receipt, "d" * 64)
            pin = scorer.digest(comparator)
            candidate = {"schema": scorer.CANDIDATE_SCHEMA, "task_id": "NEURAL-048",
                         "reference_sha256": scorer.digest(reference),
                         "policy_sha256": scorer.digest(scorer.legacy.POLICY),
                         "comparator_sha256": pin,
                         "arm_receipts": {arm: receipt for arm in scorer.NEURAL_ARMS},
                         "predictions": [{"id": "q", "neural_history": .75,
                                          "shifted_neural_history": .5}]}
            report = scorer.score(reference, comparator, candidate,
                                  expected_comparator_sha256=pin)
            self.assertAlmostEqual(report["primary"]["mean_nats_per_observation"], math.log(1.5))
            self.assertEqual(report["contrasts"]["behavior_minus_shifted"]["mean_nats_per_observation"], 0)
            self.assertEqual(report["comparator_sha256"], pin)
        with tempfile.TemporaryDirectory() as temporary:
            support, _, _ = load_copy(Path(temporary), LOADERS[1])
            with self.assertRaisesRegex(support.ContractError, "intervals required"):
                support.compile_samples([], [])


if __name__ == "__main__":
    unittest.main()
