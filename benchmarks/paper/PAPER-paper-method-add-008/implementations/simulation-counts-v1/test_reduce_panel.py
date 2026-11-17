"""Generated controls only; no simulation generator, matching or sorter is run."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("reduce_panel", Path(__file__).with_name("reduce_panel.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture(candidate=True):
    owner = {
        "schema": "figure7-native-counts-owner/v1", "dataset": m.DATASET,
        "candidate_method": "generated-control" if candidate else None,
        "evaluator_identity": {
            "spikeinterface_source_sha256": "a" * 64, "environment_sha256": "b" * 64,
            "effective_matching_parameters": {"generated_control_only": True},
            "effective_count_parameters": {"generated_control_only": True},
        },
        "seeds": [{
            "seed": seed, "sorting_sha256": str(i + 1) * 64,
            "recording_sha256": {"static": "c" * 64, "drifting": "d" * 64},
            "units": [{"unit_id": f"u{u}", "num_spikes": 10} for u in range(500)],
        } for i, seed in enumerate(m.SEEDS)],
    }
    cases = []
    for method in m.SORTERS + (("generated-control",) if candidate else ()):
        for motion in m.MOTIONS:
            for seed in owner["seeds"]:
                cases.append({
                    "method": method, "motion": motion, "seed": seed["seed"], "status": "computed",
                    "sorting_sha256": seed["sorting_sha256"], "recording_sha256": seed["recording_sha256"][motion],
                    "evaluator_identity_sha256": m.digest(owner["evaluator_identity"]),
                    "native_output_sha256": "e" * 64, "runtime_seconds": 12,
                    "unit_counts": dict(zip(m.COMPANIONS, (400, 20, 30, 40))),
                    "units": [{"unit_id": f"u{u}", "tp": 9 if method == "generated-control" else 8,
                               "fn": 1 if method == "generated-control" else 2, "fp": 2} for u in range(500)],
                })
    return owner, {"schema": "figure7-native-counts-export/v1", "owner_manifest_sha256": m.digest(owner), "cases": cases}


class CountsControls(unittest.TestCase):
    def run_panel(self, owner, export):
        return m.reduce_panel(owner, export, m.digest(owner))

    def test_corrected_denominator_and_complete_pairing(self):
        owner, export = fixture()
        report = self.run_panel(owner, export)
        self.assertEqual(len(report["cases"]), 50)
        self.assertEqual(sum(len(c["units"]) for c in report["cases"]), 25000)
        # Ni=10, Nj=10, TP=8 => 8/(10+10-8), not 8/20 or 8/(20+8).
        self.assertAlmostEqual(report["cases"][0]["units"][0]["accuracy"], 2 / 3)
        self.assertEqual(len(report["paired_candidate_minus_source"]), 40)
        self.assertAlmostEqual(report["paired_candidate_minus_source"][0]["units"][0]["accuracy_difference"], 1 / 12)
        self.assertEqual(report["cases"][0]["unit_counts"]["num_overmerged"], 40)

    def test_source_only_reproduction_component(self):
        owner, export = fixture(candidate=False)
        report = self.run_panel(owner, export)
        self.assertEqual(len(report["cases"]), 40)
        self.assertEqual(report["paired_candidate_minus_source"], [])

    def test_missing_case_or_false_success_rejected(self):
        owner, export = fixture(False)
        export["cases"].pop()
        with self.assertRaises(m.InvalidPanel): self.run_panel(owner, export)
        owner, export = fixture(False)
        export["cases"][0]["status"] = "failed"
        with self.assertRaises(m.InvalidPanel): self.run_panel(owner, export)

    def test_seed_recording_and_unit_identity(self):
        owner, original = fixture(False)
        for change in ("recording", "seed", "unit", "duplicate_case"):
            export = copy.deepcopy(original)
            if change == "recording": export["cases"][0]["recording_sha256"] = "d" * 64
            if change == "seed": export["cases"][0]["seed"] = 42
            if change == "unit": export["cases"][0]["units"][0]["unit_id"] = "u1"
            if change == "duplicate_case": export["cases"][-1] = copy.deepcopy(export["cases"][0])
            with self.subTest(change=change), self.assertRaises(m.InvalidPanel): self.run_panel(owner, export)

    def test_frozen_ground_truth_spike_conservation(self):
        owner, export = fixture(False)
        export["cases"][0]["units"][0]["fn"] = 1
        with self.assertRaises(m.InvalidPanel): self.run_panel(owner, export)
        for args in ((True, 0, 0), (-1, 1, 0), (1.0, 0, 0)):
            with self.assertRaises(m.InvalidPanel): m.accuracy(*args)

    def test_unmatched_and_empty_units_retained(self):
        owner, export = fixture(False)
        for case in export["cases"]:
            case["units"][0].update(tp=0, fn=10, fp=0)
        report = self.run_panel(owner, export)
        self.assertEqual(report["cases"][0]["units"][0]["accuracy"], 0)
        self.assertIsNone(m.accuracy(0, 0, 0))

    def test_manifest_and_evaluator_cannot_be_rebound(self):
        owner, export = fixture(False)
        with self.assertRaises(m.InvalidPanel): m.reduce_panel(owner, export, "0" * 64)
        export["cases"][0]["evaluator_identity_sha256"] = "0" * 64
        with self.assertRaises(m.InvalidPanel): self.run_panel(owner, export)

    def test_order_is_owner_identity_not_export_position(self):
        owner, export = fixture(False)
        export["cases"].reverse()
        for case in export["cases"]: case["units"].reverse()
        report = self.run_panel(owner, export)
        self.assertEqual(report["cases"][0]["seed"], 2205)
        self.assertEqual(report["cases"][0]["units"][0]["unit_id"], "u0")

    def test_duplicate_and_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            for content in ('{"a":1,"a":2}', '{"a":NaN}'):
                path.write_text(content)
                with self.assertRaises(m.InvalidPanel): m.read_json(path)


if __name__ == "__main__":
    unittest.main()
