"""Generated controls only. No authentic recordings, targets, or model calls."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).absolute().parent
spec = importlib.util.spec_from_file_location("paired_stroop", HERE / "paired_stroop.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
SEED = "34" * 32


def opaque(value):
    return hashlib.sha256(("invented-paired-control:" + value).encode()).hexdigest()


def fixture(extra_neutral=0):
    people = [opaque("person-" + str(i)) for i in range(55)]
    folds = p.core.fold_assignment(people, "12" * 32)
    manifest = {
        "schema": "stroop55-private-labels-v1", "task": p.core.TASK,
        "partition_seed": "12" * 32,
        "cohort": [{"participant": person, "sessions": [1, 2, 3]} for person in people],
        "cases": [],
    }
    candidate = {"schema": "stroop55-predictions-v1", "task": p.core.TASK, "predictions": []}
    for i, person in enumerate(people):
        labels = [0, 1, 2] + ([0] * extra_neutral if i == 0 else [])
        for block, target in enumerate(labels):
            case_id = opaque("case-" + str(i) + "-" + str(block))
            manifest["cases"].append({
                "case_id": case_id, "participant": person, "session": 3,
                "block": block, "fold": folds[person], "target": target,
            })
            candidate["predictions"].append({
                "case_id": case_id, "probabilities": [int(k == target) for k in range(3)],
                "label": p.core.CLASSES[target],
            })
    comparator = copy.deepcopy(candidate)
    for case, row in zip(manifest["cases"], comparator["predictions"]):
        wrong = (case["target"] + 1) % 3
        row.update(probabilities=[int(k == wrong) for k in range(3)], label=p.core.CLASSES[wrong])
    return manifest, candidate, comparator


def run(manifest, candidate, comparator, **kwargs):
    return p.compare(manifest, candidate, comparator, bootstrap_seed=SEED, resamples=1000, **kwargs)


class Controls(unittest.TestCase):
    def test_exact_all_correct_versus_all_wrong(self):
        result = run(*fixture())
        expected = {"balanced_accuracy": 1, "brier_sum3": -2, "log_loss": math.log(1e-15)}
        self.assertEqual(result["participants"], 55)
        self.assertEqual(result["cases"], 165)
        self.assertEqual([f["participants"] for f in result["per_fold"]], [11] * 5)
        for metric, value in expected.items():
            delta = result["metrics"][metric]["candidate_minus_comparator"]
            self.assertAlmostEqual(delta["estimate"], value)
            for bound in delta["conditional_percentile_95"]:
                self.assertAlmostEqual(bound, value)

    def test_pairing_keeps_identical_methods_zero_with_varying_people(self):
        manifest, candidate, wrong = fixture()
        # Twenty people are completely wrong and 35 completely correct.
        candidate["predictions"][:60] = copy.deepcopy(wrong["predictions"][:60])
        result = run(manifest, candidate, copy.deepcopy(candidate))
        for metric in p.METRICS:
            stats = result["metrics"][metric]
            self.assertEqual(stats["candidate_minus_comparator"]["estimate"], 0)
            self.assertEqual(stats["candidate_minus_comparator"]["conditional_percentile_95"], [0, 0])
            self.assertEqual(stats["candidate"], stats["comparator"])
            lower, upper = stats["candidate"]["conditional_percentile_95"]
            self.assertLess(lower, upper)
        # Independent analytical reference: resampled correct-person count
        # follows Binomial(55, 35/55), not a 165-block distribution.
        cumulative = 0.0
        quantiles = []
        for count in range(56):
            cumulative += math.comb(55, count) * (35 / 55) ** count * (20 / 55) ** (55 - count)
            for probability in (0.025, 0.975):
                if len(quantiles) == (0 if probability == 0.025 else 1) and cumulative >= probability:
                    quantiles.append(count / 55)
        observed = result["metrics"]["balanced_accuracy"]["candidate"]["conditional_percentile_95"]
        self.assertEqual(len(quantiles), 2)
        for actual, exact in zip(observed, quantiles):
            self.assertLessEqual(abs(actual - exact), 2 / 55)

    def test_unequal_blocks_keep_person_and_class_weighting(self):
        manifest, candidate, comparator = fixture(extra_neutral=60)
        # One person's 60 additional neutral blocks are all wrong; existing
        # three observations remain correct. Compare against all wrong.
        candidate["predictions"][3:63] = copy.deepcopy(comparator["predictions"][3:63])
        result = run(manifest, candidate, comparator)
        expected = (54 + (1 / 61 + 1 + 1) / 3) / 55
        score = result["metrics"]["balanced_accuracy"]["candidate"]["estimate"]
        self.assertAlmostEqual(score, expected)
        self.assertNotAlmostEqual(score, 165 / 225)
        self.assertEqual(result["cases"], 225)
        self.assertEqual(max(row["blocks"] for row in result["per_participant"]), 63)

    def test_reordering_reproducibility_and_no_mutation(self):
        manifest, candidate, comparator = fixture()
        candidate["predictions"][:60] = copy.deepcopy(comparator["predictions"][:60])
        original = copy.deepcopy((manifest, candidate, comparator))
        expected = run(manifest, candidate, comparator)
        self.assertEqual((manifest, candidate, comparator), original)
        manifest["cohort"].reverse()
        manifest["cases"].reverse()
        candidate["predictions"].reverse()
        comparator["predictions"] = comparator["predictions"][12:] + comparator["predictions"][:12]
        self.assertEqual(run(manifest, candidate, comparator), expected)

    def test_complete_same_cases_required_for_both_methods(self):
        for arm in (1, 2):
            for defect in ("missing", "duplicate", "unknown", "nonfinite", "wrong_label"):
                operands = fixture()
                predictions = operands[arm]["predictions"]
                if defect == "missing": predictions.pop()
                if defect == "duplicate": predictions[1] = copy.deepcopy(predictions[0])
                if defect == "unknown": predictions[0]["case_id"] = "fe" * 32
                if defect == "nonfinite": predictions[0]["probabilities"] = [float("nan"), 0, 1]
                if defect == "wrong_label": predictions[0]["label"] = "invalid"
                with self.subTest(arm=arm, defect=defect), self.assertRaises(p.Invalid):
                    run(*operands)

    def test_missing_person_class_and_wrong_fold_refused(self):
        for defect in ("person", "class", "fold"):
            manifest, candidate, comparator = fixture()
            if defect == "person": manifest["cohort"].pop()
            if defect == "class":
                manifest["cases"].pop(1)
                candidate["predictions"].pop(1)
                comparator["predictions"].pop(1)
            if defect == "fold": manifest["cases"][0]["fold"] = (manifest["cases"][0]["fold"] + 1) % 5
            with self.subTest(defect=defect), self.assertRaises(p.Invalid):
                run(manifest, candidate, comparator)

    def test_resampling_policy_validation(self):
        operands = fixture()
        for count in (True, 1, 999, 20001, 1000.0):
            with self.subTest(count=count), self.assertRaises(p.Invalid):
                p.compare(*operands, bootstrap_seed=SEED, resamples=count)
        for seed in (None, 1, "00", "GG" * 32):
            with self.subTest(seed=seed), self.assertRaises(p.Invalid):
                p.compare(*operands, bootstrap_seed=seed, resamples=1000)

    def test_percentile_definition(self):
        self.assertEqual(p._interval(list(range(41))), [1, 39])
        self.assertEqual(p._interval([10, 0]), [0.25, 9.75])
        self.assertEqual(p._interval([7] * 1000), [7, 7])

    def test_cli_pins_every_operand_and_reports_hashes(self):
        with tempfile.TemporaryDirectory(dir=HERE) as directory:
            argv, identities = [], {}
            paths = {}
            for name, operand in zip(("manifest", "candidate", "comparator"), fixture()):
                path = Path(directory) / (name + ".json")
                body = json.dumps(operand).encode()
                path.write_bytes(body)
                digest = hashlib.sha256(body).hexdigest()
                argv.extend(["--" + name, str(path), "--" + name + "-sha256", digest])
                identities[name + "_sha256"] = digest
                paths[name] = path
            argv.extend(["--bootstrap-seed", SEED, "--resamples", "1000"])
            with contextlib.redirect_stdout(io.StringIO()) as output:
                p.main(argv)
            self.assertEqual(json.loads(output.getvalue())["input_byte_identities"], identities)
            for name, path in paths.items():
                original = path.read_bytes()
                path.write_bytes(original + b" ")
                with self.subTest(operand=name), self.assertRaises(p.Invalid):
                    p.main(argv)
                path.write_bytes(original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
