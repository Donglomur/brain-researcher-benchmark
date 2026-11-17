"""Generated metadata controls; no scientific arrays, fits or observations."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("episode", Path(__file__).with_name("episode.py"))
episode = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(episode)


def generated_report(arm, contract, candidate_error=0.08):
    """Deliberately invented score numbers, never stored as empirical outcomes."""
    scores, hashes = {}, {}
    support = episode.support_manifest(contract)
    for method in episode.METHODS:
        hashes[method] = {r["filename"]: hashlib.sha256(
            (method + r["filename"]).encode()).hexdigest() for r in support["files"]}
        scores[method] = {}
        for condition in episode.CONDITIONS:
            error = candidate_error if method == "candidate" else 0.1
            rows = []
            for rat in contract["support"]:
                start, stop = rat["query_rows_zero_based_half_open"]
                rows.append({"rat": rat["rat"], "samples": stop - start,
                             "mae_m": error, "median_absolute_error_m": error * 0.5})
            scores[method][condition] = {
                "decoding_per_rat": rows, "equal_rat_mae_m": error,
                "consistency_12_directions": [
                    {"source": a, "target": b, "r2": 0.5}
                    for a in episode.RATS for b in episode.RATS if a != b],
                "mean_consistency_r2": 0.5, "undefined_consistency_reason": None,
            }
    return {"schema": "marble_fit_closed_grade_v1",
            "protocol_id": contract["existing_protocol_id"], "access_view": arm,
            "scores": scores, "captured_artifact_hashes": hashes,
            "protected_comparator_bank": {"bytes": 1234, "sha256": "a" * 64},
            "complete_native_provenance_admitted": True,
            "native_execution_or_method_qualification": False}


class EpisodeChecks(unittest.TestCase):
    def setUp(self):
        self.contract, self.baseline, self.current, self.identity = episode.load_contract()
        self.a = generated_report("A", self.contract)
        self.b = generated_report("B", self.contract)

    def compare(self):
        return episode.compare_reports(self.a, self.b, self.contract, self.identity, {})

    def test_exact_existing_support_and_no_target_slots(self):
        result = episode.support_manifest(self.contract)
        old = episode.parse(episode.capture(episode.TASK /
            "implementations/fit-closed-comparator/dependencies/protocol.json"))
        self.assertEqual([r["filename"] for r in result["files"]], old["output_files"])
        self.assertEqual(len(result["files"]), 32)
        self.assertFalse(result["query_targets_included"])
        self.assertEqual(next(r for r in result["files"] if r["filename"] ==
            "clean-buddy-test-d32.npy")["source_rows_zero_based_half_open"], [5261, 6576])

    def test_lower_mean_error_diagnostic_never_awards_scientific_win(self):
        result = self.compare()
        compare = result["comparisons"]["A"]["marble"]
        self.assertTrue(compare["existing_scorer_diagnostic"]["improvement_condition"])
        self.assertAlmostEqual(compare["per_rat_effects"][0]["candidate_minus_baseline_mae_m"], -0.02)
        self.assertIsNone(result["scientific_improvement_awarded"])
        self.assertIsNone(result["historical_paper_improvement"])
        self.assertIsNone(result["current_sota_improvement"])

    def test_improved_median_does_not_replace_primary_mean(self):
        self.a = generated_report("A", self.contract, candidate_error=0.2)
        for condition in episode.CONDITIONS:
            for row in self.a["scores"]["candidate"][condition]["decoding_per_rat"]:
                row["median_absolute_error_m"] = 0.00001
        result = self.compare()
        self.assertFalse(result["comparisons"]["A"]["marble"]
                         ["existing_scorer_diagnostic"]["improvement_condition"])

    def test_no_improvement_from_consistency_alone(self):
        self.a = generated_report("A", self.contract, candidate_error=0.1)
        for condition in episode.CONDITIONS:
            score = self.a["scores"]["candidate"][condition]
            score["mean_consistency_r2"] = 0.9
            for row in score["consistency_12_directions"]:
                row["r2"] = 0.9
        self.assertFalse(self.compare()["comparisons"]["A"]["marble"]
                         ["existing_scorer_diagnostic"]["improvement_condition"])

    def test_each_rat_and_condition_retained(self):
        mutations = [
            lambda r: r["scores"]["candidate"]["clean"]["decoding_per_rat"].reverse(),
            lambda r: r["scores"]["candidate"].pop("half"),
            lambda r: r["scores"]["candidate"]["clean"]["decoding_per_rat"][0].update(samples=2000),
            lambda r: r["captured_artifact_hashes"]["candidate"].pop("half-gatsby-test-d32.npy"),
            lambda r: r["scores"]["candidate"]["clean"].update(equal_rat_mae_m=0.001),
            lambda r: r.update(complete_native_provenance_admitted=False),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                changed = copy.deepcopy(self.a)
                mutate(changed)
                with self.assertRaises(ValueError):
                    episode.report_check(changed, "A", self.contract)

    def test_paired_baselines_cannot_differ(self):
        self.b["protected_comparator_bank"]["sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "same comparator"):
            self.compare()
        self.b = generated_report("B", self.contract)
        self.b["captured_artifact_hashes"]["marble"]["clean-achilles-train-d3.npy"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "identical"):
            self.compare()

    def test_undefined_consistency_blocks_existing_diagnostic(self):
        score = self.a["scores"]["candidate"]["clean"]
        score.update(mean_consistency_r2=None, consistency_12_directions=[],
                     undefined_consistency_reason="generated collapsed embedding control")
        self.assertFalse(self.compare()["comparisons"]["A"]["marble"]
                         ["existing_scorer_diagnostic"]["improvement_condition"])

    def test_consistency_r2_upper_bound_and_negative_values(self):
        score = self.a["scores"]["candidate"]["clean"]
        for value in (-2.0, 1.5):
            score["mean_consistency_r2"] = value
            for row in score["consistency_12_directions"]:
                row["r2"] = value
            if value < 0:
                episode.report_check(self.a, "A", self.contract)
            else:
                with self.assertRaisesRegex(ValueError, "cannot exceed one"):
                    episode.report_check(self.a, "A", self.contract)

    def test_duplicate_nonfinite_and_boolean_numbers_refused(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                episode.parse(text)
        for value in (True, float("inf"), float("nan"), -0.1):
            bad = copy.deepcopy(self.a)
            bad["scores"]["candidate"]["clean"]["decoding_per_rat"][0]["mae_m"] = value
            with self.assertRaises(ValueError):
                episode.report_check(bad, "A", self.contract)

    def test_prepare_is_metadata_only_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder).resolve() / "packet"
            episode.prepare(dest, self.contract, self.identity)
            self.assertEqual({p.name for p in dest.iterdir()}, {"OUTPUT_SUPPORT.json", "INTERFACE.json"})
            packet = json.loads((dest / "INTERFACE.json").read_text())
            self.assertFalse(packet["launch_permitted_by_this_component"])
            with self.assertRaises(ValueError):
                episode.prepare(dest, self.contract, self.identity)

    def test_pinned_capture_and_links_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            ordinary = Path(folder).resolve() / "report.json"
            ordinary.write_bytes(b"{}")
            self.assertEqual(episode.capture(ordinary, expected=episode.pin(b"{}")), b"{}")
            with self.assertRaises(ValueError):
                episode.capture(ordinary, expected=episode.pin(b"[]"))
            link = Path(folder).resolve() / "link.json"
            link.symlink_to(ordinary)
            with self.assertRaises(ValueError):
                episode.capture(link)

    def test_absent_author_sources_never_admitted(self):
        with tempfile.TemporaryDirectory() as folder:
            report = episode.audit_author(folder, self.baseline)
        self.assertFalse(report["all_selected_source_exact"])
        self.assertFalse(report["baseline_admitted"])
        self.assertEqual(len(report["files"]), 17)

    def test_require_ready_refuses_without_execution(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = episode.main(["require-ready"])
        self.assertEqual(code, 2)
        report = json.loads(output.getvalue())
        self.assertFalse(report["execution_ready"])
        self.assertFalse(report["labels_read"])


if __name__ == "__main__":
    unittest.main()
