"""Generated software controls; no authentic taxonomy, EEG, model or trial."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "registered-runtime" / "source"))
import endpoints as new
from neural057 import scoring as old
from neural057.domain import registry


def generated_report():
    # All 200 original row positions retained. Two generated supported concepts
    # and 198 explicitly unsupported rows avoid pretending to know real labels.
    ids = [f"generated-query-{i:03d}" for i in range(200)]
    private = [{"query_id": q, "concept_id": f"generated-concept-{i:03d}",
                "target": [i % 2] * 53 if i < 2 else None}
               for i, q in enumerate(ids)]
    results = {}
    for owner in ("reference", "participant"):
        rows = []
        for cell in registry():
            pred = {"schema": "neural057-prediction-v1", "cell": cell,
                    "fit_state_sha256": "a" * 64, "query_ids": ids,
                    "category_schema_sha256": "b" * 64,
                    "probabilities": [[.5] * 53 for _ in ids]}
            rows.append(old.score_cell(pred, ids, cell, "a" * 64, "b" * 64, private))
        results[owner] = {"cells": rows}
    return {"schema": "neural057-complete-report-v1",
            "status": "numerical_complete_pending_independent_semantic_qualification",
            "results": results}


def cell(report, owner="participant", person="sub-01", mode="F", panel="LATE"):
    return next(r for r in report["results"][owner]["cells"]
                if r["cell"] == dict(person=person, mode=mode, panel=panel))


def set_loss(row, values):
    row["concept_loss"] = {c: new.tag(v) for c, v in zip(row["concept_loss"], values)}
    row["loss"] = new.tag(new.mean_loss(values))


class EndpointControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = generated_report()

    def setUp(self):
        self.report = copy.deepcopy(self.template)

    def test_finite_primary_and_contrasts_match_registered_scorer(self):
        for row in self.report["results"]["participant"]["cells"]:
            p = int(row["cell"]["person"][-2:])
            offset = .3 if row["cell"]["panel"] == "BASE" else 0
            set_loss(row, [p / 10 + offset, p / 5 + offset])
        result = new.build_endpoints(self.report)
        rows = self.report["results"]["participant"]["cells"]
        for a, b in zip(result["primary_native_loss"]["participant"], old.native_summary(rows)):
            self.assertAlmostEqual(a["primary_loss"]["value"], b["primary_loss"]["value"])
        for a, b in zip(result["within_owner_descriptive_comparisons"]["participant"], old.paired_summary(rows)):
            self.assertAlmostEqual(a["left_minus_right"]["value"], b["gain_nats_per_category"])
            self.assertAlmostEqual(a["uncertainty"]["person_sem_ddof1"], b["person_sem_ddof1"])
            self.assertAlmostEqual(a["uncertainty"]["concept_sem_ddof1"], b["concept_sem_ddof1"])
            self.assertEqual(a["person_denominator"], 10)
            self.assertEqual(a["concept_denominator"], 2)

    def test_candidate_infinite_late_retains_defined_negative_contrast(self):
        set_loss(cell(self.report), [math.inf, .7])
        result = new.build_endpoints(self.report)
        paired = result["within_owner_descriptive_comparisons"]["participant"][0]
        self.assertEqual(paired["left_minus_right"]["status"], "negative_infinity")
        self.assertEqual(paired["person_contributions"]["sub-01"]["status"], "negative_infinity")
        self.assertEqual(paired["person_contributions"]["sub-02"]["status"], "finite")
        self.assertEqual(len(paired["person_contributions"]), 10)
        self.assertEqual(paired["uncertainty"]["status"], "unavailable")
        self.assertEqual(result["primary_native_loss"]["participant"][0]["primary_loss"]["status"], "positive_infinity")
        for item in result["independent_comparisons"][:2]:
            self.assertEqual(item["left_minus_right"]["status"], "negative_infinity")

    def test_infinite_base_does_not_improve_primary_or_independent_comparison(self):
        before = new.build_endpoints(self.report)
        set_loss(cell(self.report, panel="BASE"), [math.inf, .7])
        after = new.build_endpoints(self.report)
        self.assertEqual(after["primary_native_loss"], before["primary_native_loss"])
        self.assertEqual(after["independent_comparisons"], before["independent_comparisons"])
        paired = after["within_owner_descriptive_comparisons"]["participant"][0]
        self.assertEqual(paired["left_minus_right"]["status"], "positive_infinity")

    def test_infinity_minus_infinity_undefined_preserves_finite_people(self):
        set_loss(cell(self.report, panel="BASE"), [math.inf, .7])
        set_loss(cell(self.report), [math.inf, .4])
        paired = new.build_endpoints(self.report)["within_owner_descriptive_comparisons"]["participant"][0]
        self.assertEqual(paired["left_minus_right"]["status"], "undefined")
        self.assertEqual(paired["person_contributions"]["sub-01"]["status"], "undefined")
        self.assertEqual(paired["person_contributions"]["sub-02"]["status"], "finite")
        self.assertEqual(paired["concept_contributions"]["generated-concept-001"]["status"], "finite")
        self.assertEqual(paired["person_denominator"], 10)

    def test_opposing_infinite_person_gains_do_not_cancel(self):
        set_loss(cell(self.report, panel="BASE"), [math.inf, .7])
        set_loss(cell(self.report, person="sub-02"), [.7, math.inf])
        paired = new.build_endpoints(self.report)["within_owner_descriptive_comparisons"]["participant"][0]
        self.assertEqual(paired["left_minus_right"]["status"], "undefined")
        self.assertEqual(paired["person_contributions"]["sub-01"]["status"], "positive_infinity")
        self.assertEqual(paired["person_contributions"]["sub-02"]["status"], "negative_infinity")

    def test_independent_reference_infinite_loss_retains_positive_contrast(self):
        set_loss(cell(self.report, owner="reference", panel="BASE"), [math.inf, .7])
        result = new.build_endpoints(self.report)["independent_comparisons"][0]
        self.assertEqual(result["left_minus_right"]["status"], "positive_infinity")
        self.assertEqual(len(result["concept_person_contributions"]), 2)
        self.assertFalse(result["participant_BASE_used_as_reward"])

    def test_incomplete_duplicate_or_missing_control_cells_refused(self):
        for kind in ("missing", "duplicate", "wrong_panel"):
            report = copy.deepcopy(self.template)
            rows = report["results"]["reference"]["cells"]
            if kind == "missing":
                rows.pop()
            elif kind == "duplicate":
                rows[-1] = copy.deepcopy(rows[0])
            else:
                rows[0]["cell"]["panel"] = "UNKNOWN"
            with self.subTest(kind=kind), self.assertRaises(new.EndpointError):
                new.build_endpoints(report)

    def test_support_and_denominator_tampering_refused(self):
        for kind in ("concept", "unsupported", "categories", "units", "row_count", "false_mean"):
            report = copy.deepcopy(self.template)
            row = cell(report)
            if kind == "concept":
                row["concept_loss"]["other"] = row["concept_loss"].pop("generated-concept-000")
            elif kind == "unsupported":
                row["unsupported_query_ids"][0] = "changed-query"
            elif kind == "categories":
                row["categories"] = 52
            elif kind == "units":
                row["unit"] = "bits"
            elif kind == "row_count":
                row["query_rows"] = 199
            else:
                row["loss"]["value"] += 1
            with self.subTest(kind=kind), self.assertRaises(new.EndpointError):
                new.build_endpoints(report)

    def test_nonfinite_or_invalid_loss_tags_refused(self):
        for bad in ({"status": "finite", "value": True}, {"status": "finite", "value": math.nan},
                    {"status": "negative_infinity", "value": None}, {"status": "finite", "value": -1},
                    {"status": "finite", "value": 1e308}, {"status": "positive_infinity", "value": 0}):
            with self.subTest(bad=bad), self.assertRaises(new.EndpointError):
                new.native_value(bad)

    def test_cli_receipt_json_and_exclusive_output(self):
        set_loss(cell(self.report), [math.inf, .7])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "REPORT.json"
            dest = Path(directory) / "PAIRED_ENDPOINTS.json"
            source.write_text(json.dumps(self.report, allow_nan=False))
            original = source.read_bytes()
            new.main(["--report", str(source), "--output", str(dest)])
            result = json.loads(dest.read_text())
            self.assertEqual(len(result["source_report_sha256"]), 64)
            self.assertEqual(result["schema"], "neural057-paired-endpoints-v2")
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                new.main(["--report", str(source), "--output", str(dest)])
            self.assertEqual(source.read_bytes(), original)

    def test_duplicate_json_keys_and_nan_refused(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.subTest(raw=raw), self.assertRaises(new.EndpointError):
                new.parse(raw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
