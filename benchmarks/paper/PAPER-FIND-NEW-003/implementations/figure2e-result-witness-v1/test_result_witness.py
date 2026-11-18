"""Generated artifact controls; no source data, R execution or p-value replay."""
import csv
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest

import result_witness as subject


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def generated(diagonal=1.0, other=0.0, W="2548.0", p="< 0.001", matrix=None):
    inspector = subject.load_inspector()
    names = inspector.BODY_PARTS
    if matrix is None:
        matrix = [[diagonal if i == j else other for j in range(14)] for i in range(14)]
    out = io.StringIO(newline="")
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(inspector.COLUMNS)
    # Independent fixture cosine for these finite, bounded generated rows.
    for i in range(14):
        for j in range(14):
            a, b = matrix[i], matrix[j]
            denominator = math.sqrt(sum(x*x for x in a) * sum(x*x for x in b))
            cosine = sum(x*y for x,y in zip(a,b)) / denominator if denominator else 0.0
            writer.writerow((names[j], names[i], repr(cosine), repr(matrix[i][j]),
                             "TRUE" if i == j else "FALSE"))
    body = out.getvalue().encode()
    lines = [
        "Same vs Different Body Part Analysis", "="*70,
        "Date: 2026-11-18 00:00:00", "Metric: influence_log_minmax | Body parts: 14",
        "Test: Wilcoxon rank-sum (one-sided, on-diagonal > off-diagonal)",
        "Note: single test, no multiple comparisons correction needed", "", "Group summaries", "-"*70,
        "On-diagonal (same body part):      n=14, median=1.00, IQR=0.00, range=[1.00, 1.00]",
        "Off-diagonal (different body part): n=182, median=0.00, IQR=0.00, range=[0.00, 0.00]",
        "", "Test results", "-"*70, "W = "+W, "p = "+p,
        "Rank-biserial r = -1.000 (large effect)", "", "="*70,
        "FIGURE LEGEND (copy-paste ready)", "="*70,
        "A one-sided Wilcoxon rank-sum test generated fixture; not an author execution.", "="*70,
    ]
    report = ("\n".join(lines)+"\n").encode()
    binding = {
        "schema": "banc-figure2e-artifact-binding/v1", "metric": subject.METRIC,
        "source_commit": subject.SOURCE_COMMIT, "source_panel_sha256": subject.PANEL_SHA256,
        "inspector_sha256": subject.INSPECTOR_SHA256,
        "input": pin(b"generated input declaration, no authentic matrix"),
        "producer_receipt": pin(b"generated unverified receipt declaration"),
        "csv": dict(name=subject.METRIC+"_body_part_similarity_data.csv", **pin(body)),
        "report": dict(name=subject.METRIC+"_same_vs_different_body_part_test.txt", **pin(report)),
    }
    return body, report, binding


def bind(body, report, binding):
    return subject.witness(body, report, json.dumps(binding).encode())


def repin(binding, key, body):
    binding[key].update(pin(body))


class ResultWitnessTests(unittest.TestCase):
    def test_complete_operands_report_and_caveats(self):
        result = bind(*generated())
        self.assertEqual(result["serialized_operand_pairwise_U"], 2548.0)
        self.assertEqual(len(result["same_body_part_values"]), 14)
        self.assertEqual(len(result["different_body_part_values"]), 182)
        self.assertEqual(result["biological_specimens"], 1)
        for key in ("producer_and_input_lineage_authenticated", "p_value_computed_or_verified",
                    "R_runtime_parity_verified", "source_release_equivalence_verified",
                    "source_pipeline_reproduced", "readiness_promoted", "primary_endpoint_adopted"):
            self.assertIs(result[key], False)
        self.assertIsNone(result["scientific_reproduction"])
        self.assertIsNone(result["scientific_improvement"])

    def test_all_ties_assign_half_weight(self):
        self.assertEqual(bind(*generated(1.0, 1.0, "1274.0"))["serialized_operand_pairwise_U"], 1274.0)

    def test_single_cross_group_tie_retains_half_integer(self):
        matrix = [[1.0 if i == j else 0.0 for j in range(14)] for i in range(14)]
        matrix[0][0] = matrix[0][1] = 0.5
        result = bind(*generated(W="2547.5", matrix=matrix))
        self.assertEqual(result["serialized_operand_pairwise_U"], 2547.5)

    def test_reversed_values_have_zero_and_reject_forward_W(self):
        self.assertEqual(bind(*generated(0.0, 1.0, "0.0"))["serialized_operand_pairwise_U"], 0.0)
        with self.assertRaisesRegex(subject.WitnessError, "differs from serialized"):
            bind(*generated(0.0, 1.0, "2548.0"))

    def test_different_report_W_is_refused(self):
        for W in ("2535.5", "2547.5", "2548.5", "1.2", "NaN"):
            with self.subTest(W=W), self.assertRaises(subject.WitnessError):
                bind(*generated(W=W))

    def test_p_is_preserved_but_never_verified(self):
        for p in ("< 0.001", "0.999", "not recomputed here"):
            result = bind(*generated(p=p))
            self.assertEqual(result["reported_result"]["reported_p_text"], p)
            self.assertIs(result["p_value_computed_or_verified"], False)

    def test_stale_csv_and_report_pins_are_refused(self):
        for key in ("csv", "report"):
            body, report, binding = generated()
            binding[key]["sha256"] = "0"*64
            with self.subTest(key=key), self.assertRaisesRegex(subject.WitnessError, "artifact pin"):
                bind(body, report, binding)

    def test_metric_and_filename_identity_are_closed(self):
        for key, value in (("metric", "influence_log"), ("source_panel_sha256", "0"*64),
                           ("source_commit", "0"*40), ("inspector_sha256", "0"*64)):
            body, report, binding = generated(); binding[key] = value
            with self.subTest(key=key), self.assertRaises(subject.WitnessError):
                bind(body, report, binding)
        body, report, binding = generated(); binding["csv"]["name"] = "other.csv"
        with self.assertRaisesRegex(subject.WitnessError, "output name"):
            bind(body, report, binding)

    def test_test_direction_count_and_multiplicity_are_closed(self):
        replacements = ((b"on-diagonal > off-diagonal", b"on-diagonal < off-diagonal"),
                        (b"n=182", b"n=181"), (b"Body parts: 14", b"Body parts: 17"),
                        (b"single test, no multiple comparisons correction needed", b"Holm corrected"),
                        (b"Metric: influence_log_minmax", b"Metric: influence_log"))
        for old, new in replacements:
            body, report, binding = generated(); report = report.replace(old, new)
            repin(binding, "report", report)
            with self.subTest(old=old), self.assertRaises(subject.WitnessError):
                bind(body, report, binding)

    def test_missing_and_duplicate_support_use_accepted_inspector(self):
        for duplicate in (False, True):
            body, report, binding = generated(); lines=body.splitlines(keepends=True)
            body = b"".join(lines[:-1] + ([lines[1]] if duplicate else []))
            repin(binding, "csv", body)
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(subject.WitnessError, "inspector refused"):
                bind(body, report, binding)

    def test_repinning_changed_values_does_not_evade_W_check(self):
        body, report, binding = generated()
        changed, _, _ = generated(1.0, 1.0, "1274.0")
        repin(binding, "csv", changed)
        with self.assertRaisesRegex(subject.WitnessError, "differs from serialized"):
            bind(changed, report, binding)

    def test_duplicate_or_ambiguous_formatted_reports_are_refused(self):
        for extra in (b"W = 2548.0\n", b"\n", b"\x00"):
            body, report, binding = generated(); report += extra; repin(binding, "report", report)
            with self.subTest(extra=extra), self.assertRaises(subject.WitnessError):
                bind(body, report, binding)

    def test_unchecked_provenance_remains_explicit(self):
        body, report, binding = generated()
        binding["producer_receipt"] = pin(b"different caller assertion")
        result = bind(body, report, binding)
        self.assertIs(result["producer_and_input_lineage_authenticated"], False)
        self.assertEqual(result["binding_declarations"]["producer_receipt"], binding["producer_receipt"])
        binding["input"]["bytes"] = True
        with self.assertRaises(subject.WitnessError):
            bind(body, report, binding)

    def test_json_duplicate_keys_and_extra_authority_are_refused(self):
        body, report, binding = generated()
        serialized = json.dumps(binding).encode()
        with self.assertRaisesRegex(subject.WitnessError, "duplicate"):
            subject.witness(body, report, b'{"metric":"influence_log_minmax",'+serialized[1:])
        binding["scientifically_qualified"] = True
        with self.assertRaisesRegex(subject.WitnessError, "fields differ"):
            bind(body, report, binding)

    def test_dependency_bytes_checked_before_execution(self):
        # Only generated disk fixture, under64 bytes; no source copy or import.
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)/"fake.py"
            path.write_bytes(b'raise RuntimeError("must not execute")\n')
            with self.assertRaisesRegex(subject.WitnessError, "dependency pin"):
                subject.load_inspector(path)


if __name__ == "__main__":
    unittest.main()
