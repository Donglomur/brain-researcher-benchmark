"""Generated software controls; no authentic biological observations or trials."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load("lep_context_reference", HERE / "reference.py")
packet_tests = load("lep_generated_packets", HERE.parent / "condition-packets" / "test_packets.py")
scorer = packet_tests.scorer
PIN = "a" * 64


def fixture():
    """Minimal complete-format packet for algebra tests, explicitly invented."""
    def case(i, labeled=True):
        value = {"id": "generated_%d" % i, "channels": [{"label": "Cz", "xyz_mm": None}],
                 "coordinate_system": "generated_mm", "samples_001uv": [[0] * 300],
                 "valid_mask": [[True] * 300],
                 "context": {"device": "ANT", "reference": "generated reference", "rating_protocol": "generated continuous"},
                 "delivered_energy_j": i, "stimulated_side": "left", "calibration_category": 7,
                 "quantization": {"max_abs_residual_uv": 0, "missing_samples": 0}}
        if labeled:
            value["rating"] = i
        return value
    return {"schema": "lep-query-packet-v1", "task_id": r.TASK_ID, "fold_id": "fold_generated",
            "protocol_sha256": PIN, "representation_sha256": PIN, "documentation": "GENERATED ONLY",
            "signal_grid": {"times_us": list(range(-1_000_000, 2_000_000, 10_000)),
                            "scale_uv": 0.01, "endpoint_convention": "right_open"},
            "training_support": [case(i) for i in range(8)], "calibration": [case(8), case(9)],
            "query": case(10, False)}


def run(doc):
    raw = r.encode(doc)
    return r.predict_packet(raw, expected_packet_sha256=hashlib.sha256(raw).hexdigest(),
                            protocol_sha256=PIN, representation_sha256=PIN)


class ReferenceTests(unittest.TestCase):
    def test_ridge_matches_independent_one_feature_closed_form(self):
        doc = fixture()
        doc["query"]["delivered_energy_j"] = 9
        result = run(doc)
        # ddof=0 scaling gives sum(z^2)=10. Unpenalized intercept is 4.5;
        # lambda=1 shrinks the original unit slope by exactly 10/(10+1).
        self.assertAlmostEqual(result["prediction"]["median"], 4.5 + (9 - 4.5) * 10 / 11, places=12)
        self.assertEqual(result["support_calibration_median"], 4.5)
        self.assertEqual(result["calibration_median"], 8.5)

    def test_query_never_fits_scale_vocabulary_or_imputation(self):
        doc = fixture()
        baseline = run(doc)
        doc["query"]["delivered_energy_j"] = 10_000
        doc["query"]["stimulated_side"] = "previously_unseen"
        doc["query"]["calibration_category"] = 1.25
        altered = run(doc)
        self.assertEqual(baseline["audit"]["fit"], altered["audit"]["fit"])
        self.assertEqual(altered["audit"]["query_unseen_categories"], ["stimulated_side", "calibration_category"])
        self.assertEqual(altered["prediction"]["median"], 10)
        self.assertTrue(altered["audit"]["prediction_projected"])

    def test_eeg_grid_documentation_and_coordinates_cannot_predict(self):
        doc = fixture()
        baseline = run(doc)
        for case in doc["training_support"] + doc["calibration"] + [doc["query"]]:
            case["samples_001uv"] = [[999999] * 300, [None] * 300]
            case["valid_mask"] = [[True] * 300, [False] * 300]
            case["channels"] = [{"label": "Cz", "xyz_mm": [1, 2, 3]}, {"label": "Fz", "xyz_mm": None}]
            case["quantization"] = {"max_abs_residual_uv": 0.001, "missing_samples": 300}
        doc["documentation"] = "Different reviewed source prose"
        changed = run(doc)
        self.assertEqual(changed["prediction"], baseline["prediction"])
        self.assertEqual(changed["audit"]["fit"], baseline["audit"]["fit"])

    def test_missing_energy_is_not_replaced_by_rating_calibration(self):
        doc = fixture()
        for case in doc["training_support"] + doc["calibration"] + [doc["query"]]:
            case["delivered_energy_j"] = None
        result = run(doc)
        self.assertAlmostEqual(result["prediction"]["median"], 4.5)
        self.assertIsNone(result["audit"]["fit"]["energy_imputation_j"])
        self.assertEqual(result["audit"]["fit"]["training_observed_energy"], 0)
        self.assertFalse(result["audit"]["all_eleven_energies_observed"])
        doc["query"]["delivered_energy_j"] = 500
        self.assertAlmostEqual(run(doc)["prediction"]["median"], 4.5)

    def test_missing_training_energy_uses_observed_training_mean(self):
        doc = fixture()
        doc["training_support"][0]["delivered_energy_j"] = None
        doc["query"]["delivered_energy_j"] = None
        result = run(doc)
        self.assertEqual(result["audit"]["fit"]["energy_imputation_j"], 5)
        self.assertEqual(result["audit"]["fit"]["training_observed_energy"], 9)
        self.assertEqual(result["audit"]["fit"]["feature_means"][:2], [5, 0.1])
        self.assertFalse(result["audit"]["query_energy_observed"])

    def test_decimal_zero_labels_and_constant_design(self):
        doc = fixture()
        for case in doc["training_support"] + doc["calibration"] + [doc["query"]]:
            case["delivered_energy_j"] = 1.5
        ratings = [0, 0.25, 0.5, 1, 2, 3, 4, 6, 9.25, 10]
        for case, rating in zip(doc["training_support"] + doc["calibration"], ratings):
            case["rating"] = rating
        result = run(doc)
        self.assertAlmostEqual(result["prediction"]["median"], sum(ratings) / 10)
        self.assertEqual(result["support_calibration_median"], 2.5)
        self.assertEqual(result["calibration_median"], 9.625)

    def test_stimulated_side_can_explain_rating(self):
        doc = fixture()
        for i, case in enumerate(doc["training_support"] + doc["calibration"]):
            case["delivered_energy_j"] = 1
            case["stimulated_side"] = "left" if i < 5 else "right"
            case["rating"] = 2 if i < 5 else 8
        doc["query"]["delivered_energy_j"] = 1
        doc["query"]["stimulated_side"] = "right"
        # Two standardized dummy columns give a single contrast eigenvalue 20.
        self.assertAlmostEqual(run(doc)["prediction"]["median"], 5 + 3 * 20 / 21, places=12)

    def test_support_order_does_not_change_ridge(self):
        doc = fixture()
        before = run(doc)
        doc["training_support"].reverse()
        doc["calibration"].reverse()
        after = run(doc)
        self.assertAlmostEqual(before["prediction"]["median"], after["prediction"]["median"], places=12)

    def test_query_answer_extra_inputs_duplicates_and_wrong_identity_refuse(self):
        edits = [lambda d: d["query"].update(rating=3),
                 lambda d: d["query"]["context"].update(answer=3),
                 lambda d: d["training_support"].pop(),
                 lambda d: d["calibration"].append(copy.deepcopy(d["calibration"][0])),
                 lambda d: d["query"].update(id=d["training_support"][0]["id"]),
                 lambda d: d.update(protocol_sha256="b" * 64),
                 lambda d: d["query"].update(delivered_energy_j=True),
                 lambda d: d["query"].update(delivered_energy_j=-1),
                 lambda d: d["query"].update(calibration_category=11)]
        for edit in edits:
            with self.subTest(edit=edit):
                doc = fixture()
                edit(doc)
                with self.assertRaises(r.ContractError):
                    run(doc)
        raw = r.encode(fixture())
        with self.assertRaises(r.ContractError):
            r.predict_packet(raw, expected_packet_sha256="0" * 64,
                             protocol_sha256=PIN, representation_sha256=PIN)
        for raw in (b'{"schema":1,"schema":2}', b'{"schema":NaN}'):
            with self.assertRaises(r.ContractError):
                r.predict_packet(raw, expected_packet_sha256=hashlib.sha256(raw).hexdigest(),
                                 protocol_sha256=PIN, representation_sha256=PIN)

    def test_complete_generated_packet_producer_and_existing_scorer(self):
        generated = packet_tests.GeneratedInputs()
        # One additional eligible query establishes that full coverage is data-
        # derived, rather than a hardcoded single prediction per nominal person.
        person = generated.person(1)
        trial = copy.deepcopy(person["trials"][-1])
        trial.update(trial_key="extra_generated", chronology=4, alias_group="extra_generated_alias", rating=0.25)
        person["trials"].append(trial)
        assay = generated.build()
        bodies = [(key, assay.query_packet(key)) for key in assay.query_ids]
        manifest = {key: hashlib.sha256(raw).hexdigest() for key, raw in bodies}
        args = dict(packet_sha256_by_id=manifest, protocol_sha256=assay.protocol_sha256,
                    representation_sha256=assay.representation_sha256, selection_receipt_sha256=PIN)
        comparator, controls, receipt = r.build_comparator(iter(bodies), **args)
        self.assertEqual(receipt["query_packets"], 679)
        self.assertEqual(receipt["folds"], 9)
        self.assertEqual(receipt["queries_with_any_missing_energy"], 0)
        report = scorer.grade(r.encode(comparator["prediction"]), lambda: (assay.private_targets(), comparator),
                              protocol_sha256=assay.protocol_sha256, representation_sha256=assay.representation_sha256)
        self.assertTrue(report["output_contract_passed"])
        # The retained scorer is the authority for full population denominators.
        self.assertEqual(len(comparator["prediction"]["predictions"]), 679)
        self.assertEqual(len(controls["calibration_median"]["predictions"]), 679)
        for stream in (bodies[:-1], bodies + [bodies[0]], [("unknown", bodies[0][1])] + bodies):
            with self.assertRaises(r.ContractError):
                r.build_comparator(stream, **args)
        changed = json.loads(bodies[-1][1])
        changed["training_support"][0]["rating"] = (changed["training_support"][0]["rating"] + 1) % 10
        raw = r.encode(changed)
        tampered = bodies[:-1] + [(bodies[-1][0], raw)]
        rehashed = {**manifest, bodies[-1][0]: hashlib.sha256(raw).hexdigest()}
        with self.assertRaisesRegex(r.ContractError, "supports changed"):
            r.build_comparator(tampered, **{**args, "packet_sha256_by_id": rehashed})


if __name__ == "__main__":
    unittest.main()
