"""Generated controls only; toy IDs never represent authentic neurons."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("family", Path(__file__).with_name("family.py"))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def fixture():
    neurons = []
    for variant in F.VARIANTS:
        for i in (2, 1):  # Deliberately not lexicographic: operator order is retained.
            neurons.append({"neuron_id": variant + "-generated-" + str(i), "variant": variant,
                            "sample_ids": ["sample-3", "sample-7", "sample-8", "sample-11"]})
    manifest = {"schema": "gcamp8-figure1e-support/v1", "task_id": F.TASK,
                "source_manifest_sha256": "a" * 64,
                "condition": {"sampling_rate_hz": 30, "smoothing_seconds": 0.05,
                              "noise_level": 8, "target_rate_units": "generated-target-rate-units",
                              "alignment_source_sha256": "b" * 64}, "neurons": neurons,
                "eligibility": [{"method": m, "neuron_id": n["neuron_id"], "status": "evaluate",
                                 "reason": None, "source_sha256": "c" * 64,
                                 "output_units": "generated-method-output-units",
                                 "valid_mask": [True, True, True, False]}
                                for m in F.METHODS for n in neurons]}
    target = {n["neuron_id"]: {"sample_ids": list(n["sample_ids"]), "values": [0., 1., 3., None]}
              for n in neurons}
    predictions = {m: copy.deepcopy(target) for m in F.METHODS}
    return manifest, target, predictions


class FamilyTests(unittest.TestCase):
    def test_complete_family_preserves_identity_order_without_aggregation(self):
        m, t, p = fixture()
        result = F.assemble_family(m, t, p)
        self.assertEqual(len(result["members"]), 24)
        self.assertEqual([r["neuron_id"] for r in result["members"][0]["records"]],
                         ["gcamp8f-generated-2", "gcamp8f-generated-1"])
        self.assertIsNone(result["aggregate"])
        self.assertIsNone(result["paper_win"])
        self.assertFalse(result["scientific_qualification_added"])
        self.assertFalse(result["original_cohort_equivalence_established"])
        self.assertAlmostEqual(result["members"][0]["records"][0]["metrics"]["pearson"], 1.)

    def test_prediction_mapping_order_does_not_change_correspondence(self):
        m, t, p = fixture()
        expected = F.assemble_family(m, t, p)
        p = {method: dict(reversed(list(rows.items()))) for method, rows in p.items()}
        self.assertEqual(expected, F.assemble_family(m, t, p))

    def test_missing_extra_or_duplicate_support_rejected(self):
        for change in ("method", "prediction", "target", "eligibility", "duplicate_neuron"):
            with self.subTest(change=change):
                m, t, p = fixture()
                if change == "method":
                    p.pop(F.METHODS[0])
                elif change == "prediction":
                    p[F.METHODS[0]].pop(next(iter(t)))
                elif change == "target":
                    t["extra"] = next(iter(t.values()))
                elif change == "eligibility":
                    m["eligibility"].pop()
                else:
                    m["neurons"].append(copy.deepcopy(m["neurons"][0]))
                with self.assertRaises(ValueError):
                    F.assemble_family(m, t, p)

    def test_sample_reordering_rejected_even_with_same_values(self):
        m, t, p = fixture()
        n = next(iter(t))
        p[F.METHODS[0]][n]["sample_ids"].reverse()
        with self.assertRaisesRegex(ValueError, "sample identity/order"):
            F.assemble_family(m, t, p)

    def test_target_support_cannot_be_inferred_from_prediction(self):
        for value in (None, float("nan"), float("inf"), True):
            with self.subTest(value=value):
                m, t, p = fixture()
                p[F.METHODS[0]][next(iter(t))]["values"][1] = value
                with self.assertRaises(ValueError):
                    F.assemble_family(m, t, p)

    def test_operator_exclusion_preserved_and_not_model_selectable(self):
        m, t, p = fixture()
        row = m["eligibility"][0]
        row.update(status="source_excluded", reason="Generated source-eligibility fixture only", valid_mask=None)
        p[row["method"]].pop(row["neuron_id"])
        r = F.assemble_family(m, t, p)["members"][0]["records"]
        self.assertEqual(len(r), 2)
        self.assertEqual(r[0]["eligibility"], "source_excluded")
        self.assertIsNone(r[0]["metrics"])
        self.assertIsNotNone(r[1]["metrics"])
        p[row["method"]][row["neuron_id"]] = copy.deepcopy(t[row["neuron_id"]])
        with self.assertRaisesRegex(ValueError, "frozen eligible support"):
            F.assemble_family(m, t, p)

    def test_constant_prediction_retains_undefined_entry(self):
        m, t, p = fixture()
        p[F.METHODS[0]][next(iter(t))]["values"] = [1., 1., 1., None]
        records = F.assemble_family(m, t, p)["members"][0]["records"]
        self.assertEqual(len(records), 2)
        self.assertIsNone(records[0]["metrics"]["pearson"])
        self.assertEqual(records[0]["metrics"]["pearson_reason"], "constant_prediction")

    def test_method_specific_frozen_support_is_not_silently_intersected(self):
        m, t, p = fixture()
        m["eligibility"][0]["valid_mask"] = [True, False, True, False]
        p[F.METHODS[0]][next(iter(t))]["values"][1] = None
        result = F.assemble_family(m, t, p)
        first = result["members"][0]["records"][0]["metrics"]
        second_method = result["members"][3]["records"][0]["metrics"]
        self.assertEqual(first["samples_scored"], 2)
        self.assertEqual(second_method["samples_scored"], 3)
        self.assertNotEqual(first["support_sha256"], second_method["support_sha256"])

    def test_condition_substitutions_rejected(self):
        for key, value in (("sampling_rate_hz", 60), ("smoothing_seconds", .025),
                           ("noise_level", 2), ("sampling_rate_hz", True)):
            with self.subTest(key=key, value=value):
                m, t, p = fixture()
                m["condition"][key] = value
                with self.assertRaisesRegex(ValueError, "condition differs"):
                    F.assemble_family(m, t, p)

    def test_raw_fluorescence_uses_pearson_without_cross_unit_rate_error(self):
        m, t, p = fixture()
        n = next(iter(t))
        p["raw-fluorescence"][n]["values"] = [-5., -3., 1., None]
        m["eligibility"][0]["output_units"] = "generated-delta-F-over-F"
        record = F.assemble_family(m, t, p)["members"][0]["records"][0]
        self.assertAlmostEqual(record["metrics"]["pearson"], 1.)
        self.assertNotIn("smoothed_normalized_absolute_error", record["metrics"])
        self.assertNotIn("smoothed_normalized_bias", record["metrics"])
        self.assertEqual(record["output_units"], "generated-delta-F-over-F")

    def test_favorable_variant_omission_rejected(self):
        m, t, p = fixture()
        m["neurons"] = [n for n in m["neurons"] if n["variant"] != "gcamp8s"]
        with self.assertRaisesRegex(ValueError, "all three variants"):
            F.assemble_family(m, t, p)

    def test_metric_dependency_change_fails_closed(self):
        with patch.object(F, "METRIC_SHA256", "0" * 64):
            with self.assertRaisesRegex(ValueError, "dependency changed"):
                F.assemble_family(*fixture())

    def test_input_objects_are_not_mutated(self):
        args = fixture()
        before = copy.deepcopy(args)
        F.assemble_family(*args)
        self.assertEqual(args, before)

    def compare(self, m, t, p, candidate=None):
        return F.compare_family(m, t, p, copy.deepcopy(t) if candidate is None else candidate,
                                candidate_id="generated-candidate", candidate_output_units="generated-rate")

    def test_paired_family_retains_all_source_controls_and_both_gc8_baselines(self):
        m, t, p = fixture()
        candidate = copy.deepcopy(t)
        for packet in candidate.values():
            packet["values"] = [0., -1., -3., None]
        result = self.compare(m, t, p, candidate)
        self.assertEqual(result["author_family"], F.assemble_family(m, t, p))
        self.assertEqual(len(result["comparisons"]), 6)
        self.assertEqual({r["author_method"] for r in result["comparisons"]}, set(F.COMPARISON_BASELINES))
        for member in result["comparisons"]:
            self.assertEqual([r["neuron_id"] for r in member["records"]],
                             [n["neuron_id"] for n in m["neurons"] if n["variant"] == member["variant"]])
            for row in member["records"]:
                self.assertAlmostEqual(row["candidate_minus_author_pearson"], -2.)
                self.assertEqual(row["candidate"]["support_sha256"], row["author"]["support_sha256"])
                self.assertIsNone(row["difference_reason"])
        for field in ("aggregate", "uncertainty", "paper_win"):
            self.assertIsNone(result[field])
        self.assertFalse(result["scientific_qualification_added"])
        json.dumps(result, allow_nan=False)

    def test_paired_candidate_is_one_id_joined_vector_on_each_original_support(self):
        m, t, p = fixture()
        identity = next(iter(t))
        for policy in m["eligibility"]:
            if policy["neuron_id"] == identity and policy["method"] == F.COMPARISON_BASELINES[0]:
                policy["valid_mask"] = [True, False, True, False]
        candidate = copy.deepcopy(t)
        candidate[identity]["values"] = [0., 5., 3., None]
        a = self.compare(m, t, p, candidate)
        b = self.compare(m, t, p, dict(reversed(list(candidate.items()))))
        self.assertEqual(a, b)
        pooled = a["comparisons"][0]["records"][0]
        variant = a["comparisons"][3]["records"][0]
        self.assertEqual(pooled["candidate"]["samples_scored"], 2)
        self.assertEqual(variant["candidate"]["samples_scored"], 3)
        self.assertAlmostEqual(pooled["candidate_minus_author_pearson"], 0.)
        self.assertLess(variant["candidate_minus_author_pearson"], 0.)

    def test_paired_candidate_cannot_omit_add_or_reorder_support(self):
        for change in ("missing", "extra", "sample_order", "missing_value"):
            with self.subTest(change=change):
                m, t, p = fixture()
                candidate = copy.deepcopy(t)
                identity = next(iter(t))
                if change == "missing":
                    candidate.pop(identity)
                elif change == "extra":
                    candidate["extra"] = copy.deepcopy(t[identity])
                elif change == "sample_order":
                    candidate[identity]["sample_ids"].reverse()
                else:
                    candidate[identity]["values"][1] = None
                with self.assertRaises(ValueError):
                    self.compare(m, t, p, candidate)

    def test_paired_baseline_exclusion_does_not_remove_other_baseline(self):
        m, t, p = fixture()
        identity = next(iter(t))
        for policy in m["eligibility"]:
            if policy["neuron_id"] == identity and policy["method"] == F.COMPARISON_BASELINES[0]:
                policy.update(status="source_excluded", reason="Generated source exclusion", valid_mask=None)
                p[policy["method"]].pop(identity)
        result = self.compare(m, t, p)
        excluded = result["comparisons"][0]["records"][0]
        self.assertEqual(excluded["difference_reason"], "source_excluded")
        self.assertEqual(excluded["exclusion_reason"], "Generated source exclusion")
        self.assertIsNone(excluded["candidate"])
        self.assertIsNone(excluded["candidate_minus_author_pearson"])
        self.assertIsNotNone(result["comparisons"][3]["records"][0]["candidate"])
        candidate = copy.deepcopy(t)
        candidate.pop(identity)
        with self.assertRaisesRegex(ValueError, "eligibility union"):
            self.compare(m, t, p, candidate)

    def test_paired_dual_exclusion_retains_rows_without_candidate_packet(self):
        m, t, p = fixture()
        identity = next(iter(t))
        for policy in m["eligibility"]:
            if policy["neuron_id"] == identity and policy["method"] in F.COMPARISON_BASELINES:
                policy.update(status="source_excluded", reason="Generated source exclusion", valid_mask=None)
                p[policy["method"]].pop(identity)
        candidate = copy.deepcopy(t)
        candidate.pop(identity)
        result = self.compare(m, t, p, candidate)
        for i in (0, 3):
            self.assertEqual(result["comparisons"][i]["records"][0]["difference_reason"], "source_excluded")
        self.assertEqual(len(result["author_family"]["members"]), 24)

    def test_paired_undefined_arms_remain_separate_without_zero_filling(self):
        for mode in ("candidate", "author", "both"):
            with self.subTest(mode=mode):
                m, t, p = fixture()
                candidate = copy.deepcopy(t)
                identity = next(iter(t))
                if mode in ("candidate", "both"):
                    candidate[identity]["values"] = [1., 1., 1., None]
                if mode in ("author", "both"):
                    p[F.COMPARISON_BASELINES[0]][identity]["values"] = [2., 2., 2., None]
                row = self.compare(m, t, p, candidate)["comparisons"][0]["records"][0]
                self.assertEqual(row["difference_reason"], mode + "_pearson_undefined")
                self.assertIsNone(row["candidate_minus_author_pearson"])
                self.assertEqual(row["candidate"]["pearson_reason"] if mode != "author"
                                 else row["author"]["pearson_reason"], "constant_prediction")

    def test_paired_input_immutability_and_complete_author_family_required(self):
        args = fixture()
        candidate = copy.deepcopy(args[1])
        before = copy.deepcopy((args, candidate))
        self.compare(*args, candidate)
        self.assertEqual((args, candidate), before)
        args[2].pop("raw-fluorescence")
        with self.assertRaisesRegex(ValueError, "all eight named"):
            self.compare(*args, candidate)

    def test_paired_candidate_label_cannot_impersonate_source_method(self):
        m, t, p = fixture()
        with self.assertRaisesRegex(ValueError, "differ from source"):
            F.compare_family(m, t, p, t, candidate_id="gc8-pooled-cascade",
                             candidate_output_units="generated-rate")


if __name__ == "__main__":
    unittest.main()
