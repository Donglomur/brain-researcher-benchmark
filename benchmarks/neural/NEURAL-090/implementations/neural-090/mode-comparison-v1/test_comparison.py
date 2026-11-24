"""Generated complete scalar reports only; no models or authentic neural inputs."""
import argparse
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(add_help=False)
parser.add_argument("--source-root", type=Path, default=HERE.parent)
parser.add_argument("--scratch-root", type=Path, default=None)
args, remaining = parser.parse_known_args()
sys.argv = [sys.argv[0], *remaining]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


C = load("mode_comparison", HERE / "comparison.py")
C.VALIDATOR_PATH = args.source_root / "investigation-claims-v1" / "claims.py"
F = load("original_generated_report", args.source_root / "investigation-claims-v1" / "test_claims.py")


class ComparisonControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = C.compare(F.report())

    def test_all_four_exact_strata_and_full_paired_distributions(self):
        self.assertEqual({row["id"] for row in self.baseline["comparisons"]},
                         {axis + "/" + budget for axis, budget in C.PRIMARY_STRATA})
        self.assertEqual(self.baseline["denominator"]["invocations"], 76800)
        for row in self.baseline["comparisons"]:
            self.assertEqual(len(row["chapter_pairs"]), 640)
            self.assertEqual(len(row["person_seed_pairs"]), 320)
            self.assertEqual(len(row["seed_means"]), 10)
            self.assertEqual(len(row["person_means"]), 32)
            self.assertAlmostEqual(row["frozen_minus_adaptive"], -.01, places=12)
            self.assertAlmostEqual(row["frozen_log_loss"] - row["adaptive_log_loss"], -.01, places=12)
            self.assertEqual(row["unit"], "nats_per_prediction")
        for key in ("original_event_support_authenticated", "equal_information_authenticated",
                    "participant_policy_difference_authenticated", "direct_or_no_tools_comparison", "campaign_qualified"):
            self.assertIs(self.baseline[key], False)

    def test_heterogeneous_paired_losses_equal_weight_people_and_all_seeds(self):
        original_loss = F.loss

        def heterogeneous(g, seed, person, chapter):
            _, mode, track, arm = F.GROUPS[g]
            delta = .2 + person * .002 + seed * .001 - chapter * .001
            return original_loss(g, seed, person, chapter) + (
                delta if (mode, track, arm) == (C.MODES[1], "candidate", "neural") else 0)

        with mock.patch.object(F, "loss", heterogeneous):
            result = C.compare(F.report())
        for row in result["comparisons"]:
            # Analytic mean of indices: person 15.5, seed 4.5, chapter .5.
            expected = -.01 - (.2 + 15.5 * .002 + 4.5 * .001 - .5 * .001)
            self.assertAlmostEqual(row["frozen_minus_adaptive"], expected, places=12)
            self.assertAlmostEqual(row["chapter_pairs"][0]["frozen_minus_adaptive"], -.21, places=12)
            self.assertAlmostEqual(row["person_means"][0]["frozen_minus_adaptive"], -.214, places=12)
            self.assertAlmostEqual(row["person_means"][-1]["frozen_minus_adaptive"], -.276, places=12)
            # Original query counts vary from 1 to 32; these must not weight people.
            weighted_person = sum(p * (p + 1) for p in range(32)) / sum(range(1, 33))
            weighted_delta = -.01 - (.2 + weighted_person * .002 + 4.5 * .001 - .5 * .001)
            self.assertNotAlmostEqual(row["frozen_minus_adaptive"], weighted_delta, places=8)

    def test_counts_mismatch_rejected_even_when_original_scalar_arithmetic_is_valid(self):
        def changed():
            report = F.report()
            rows = F.chapters()
            first = next(rows)
            # Counts are individually well formed and do not change scalar means.
            first = dict(first, query_rows=2, per_class_support=[2] + [0] * 38)
            report["chapter_seed_distribution"] = itertools.chain([first], rows)
            return report

        self.assertEqual(len(C.validator().expected_claims(changed())), 348)
        with self.assertRaisesRegex(ValueError, "identical reported class support"):
            C.compare(changed())

    def test_missing_secondary_and_malformed_companion_refused(self):
        report = F.report()
        report["chapter_seed_distribution"] = (
            row for row in report["chapter_seed_distribution"] if row["axis"] != "exposed_person")
        with self.assertRaisesRegex(ValueError, "missing"):
            C.compare(report)
        report = F.report()
        report["candidate_neural_improvement"] = itertools.islice(report["candidate_neural_improvement"], 7679)
        with self.assertRaisesRegex(ValueError, "missing"):
            C.compare(report)

    def test_duplicate_and_nonfinite_json_create_no_output(self):
        with tempfile.TemporaryDirectory(dir=args.scratch_root) as root:
            source, output = Path(root) / "report.json", Path(root) / "comparison.json"
            for body in ('{"schema":"a","schema":"b"}', '{"x":NaN}', '{"x":Infinity}', '{}'):
                source.write_text(body)
                with self.assertRaises(ValueError):
                    C.main(["--report", str(source), "--output", str(output)])
                self.assertFalse(output.exists())

    def test_cli_complete_route_and_overwrite_refusal(self):
        with tempfile.TemporaryDirectory(dir=args.scratch_root) as root:
            output = Path(root) / "comparison.json"
            binding = dict(kind="generated_fixture_loader", exact_input_bytes_sha256=None,
                           caller_custody_required=True)
            with mock.patch.object(C, "read_report", return_value=(F.report(), binding)):
                C.main(["--report", "unused-generated-report", "--output", str(output)])
            expected = output.read_bytes()
            self.assertEqual(json.loads(expected), dict(self.baseline, input_binding=binding))
            # Output refusal is independent of repeated report parsing/validation.
            with mock.patch.object(C, "read_report", return_value=(None, binding)), mock.patch.object(C, "compare", return_value=dict(self.baseline)):
                with self.assertRaises(FileExistsError):
                    C.main(["--report", "unused-generated-report", "--output", str(output)])
            self.assertEqual(output.read_bytes(), expected)

    def test_reader_binds_the_exact_parsed_bytes(self):
        with tempfile.TemporaryDirectory(dir=args.scratch_root) as root:
            source = Path(root) / "report.json"
            body = b'{ "small": [1, 2.5, null] }\n'
            source.write_bytes(body)
            parsed, binding = C.read_report(source)
            self.assertEqual(parsed, {"small": [1, 2.5, None]})
            self.assertEqual(binding["bytes"], len(body))
            self.assertEqual(binding["exact_input_bytes_sha256"], hashlib.sha256(body).hexdigest())
            self.assertTrue(binding["caller_custody_required"])

    def test_source_pin_mismatch_refused(self):
        with mock.patch.object(C, "CLAIMS_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "source pin"):
                C.compare(F.report())


if __name__ == "__main__":
    unittest.main()
