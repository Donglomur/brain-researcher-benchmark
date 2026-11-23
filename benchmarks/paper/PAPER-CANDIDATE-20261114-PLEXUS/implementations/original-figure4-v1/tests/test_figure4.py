"""Generated software controls, without authentic observations or classifier fitting."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import figure4 as f


def census():
    panels = []
    for family in f.FAMILIES:
        for donor in f.DONORS:
            observations = []
            # Deliberately unequal class counts and multiple control guides.
            for guide, gene, count in [("non-targeting_1", "non-targeting", 13),
                                       ("non-targeting_2", "non-targeting", 17),
                                       ("A_1", "A", 11), ("B_1", "B", 37),
                                       ("C_1", "C", 3), ("D_1", "D", 19)]:
                for well in range(4 if guide != "D_1" else 1):
                    for cell in range(count):
                        oid = f"{guide}:{well}:{cell}"
                        observations.append({"observation_id": oid, "guide_id": guide, "gene_id": gene,
                                             "well_id": f"{guide}-{well}", "zarr_file": "plate_1",
                                             "aggregate_by": f"plate_1_{oid}"})
            panels.append({"family": family, "donor": donor, "tau_status": "WT",
                           "observations_source_sha256": "1" * 64, "observations": observations})
    return {"schema": "plexus-figure4-observations/v1", "source_figure4_sha256": f.SOURCE_SHA256,
            "data_record": f.DATA_RECORD, "preprocessing_receipt_sha256": "2" * 64, "panels": panels}


def predictions(data):
    plan = f.prepare(data)
    scores = []
    for method, family in f.METHODS.items():
        for panel in plan["panels"]:
            if panel["family"] == family:
                for endpoint in panel["endpoints"]:
                    for fold in endpoint["folds"]:
                        for row in fold["test"]:
                            scores.append({"method": method, "donor": panel["donor"],
                                           "guide_id": endpoint["guide_id"], "fold": fold["fold"],
                                           "observation_id": row["observation_id"],
                                           "probability": row["label"] if method == "candidate" else 0.5})
    return {"schema": "plexus-figure4-predictions/v1", "plan_sha256": f.digest(plan), "scores": scores}


def reproduction_predictions(data):
    submission = predictions(data)
    submission["schema"] = "plexus-figure4-reproduction-predictions/v1"
    submission["scores"] = [r for r in submission["scores"] if r["method"] != "candidate"]
    return submission


class Controls(unittest.TestCase):
    def test_rank_auc_matches_independent_pairwise_oracle_with_ties(self):
        labels = [0, 1, 0, 1, 0, 1, 1]
        values = [0.4, 0.4, 0.7, 0.9, 0.1, 0.2, 0.4]
        pairs = [(a, b) for a, y in zip(values, labels) if y for b, z in zip(values, labels) if not z]
        expected = sum((a > b) + 0.5 * (a == b) for a, b in pairs) / len(pairs)
        self.assertAlmostEqual(f.auroc(labels, values), expected)
        self.assertEqual(f.auroc([0, 1], [0.5, 0.5]), 0.5)
        self.assertEqual(f.auroc([0, 1], [1, 0]), 0)

    def test_reciprocal_fold_is_balanced_subset_not_all_first_train_rows(self):
        plan = f.prepare(census())
        for panel in plan["panels"]:
            endpoints = {e["guide_id"]: e for e in panel["endpoints"]}
            self.assertEqual({s["guide_id"] for s in panel["skipped_guides"]}, {"C_1", "D_1"})
            self.assertTrue(endpoints["A_1"]["discarded_by_balance"])
            for endpoint in endpoints.values():
                first, reverse = endpoint["folds"]
                self.assertEqual(first["train"], reverse["test"])
                self.assertEqual(first["test"], reverse["train"])
                labels = [r["label"] for r in reverse["test"]]
                self.assertEqual(sum(labels), len(labels) // 2)
                self.assertFalse(set(endpoint["discarded_by_balance"]) & {r["observation_id"] for r in reverse["test"]})

    def test_non_targeting_control_guide_does_not_classify_itself_as_negative(self):
        panel = f.prepare(census())["panels"][0]
        for endpoint in panel["endpoints"]:
            if endpoint["gene_id"] == "non-targeting":
                for fold in endpoint["folds"]:
                    for row in fold["test"] + fold["train"]:
                        self.assertEqual(row["label"], int(row["observation_id"].startswith(endpoint["guide_id"] + ":")))

    def test_complete_vector_and_identical_candidate_population(self):
        data = census()
        report = f.evaluate(data, predictions(data), f.digest(data))
        self.assertEqual(len(report["auroc_vector"]), 3 * 2 * 4 * 2)
        self.assertEqual({r["candidate_minus_author_plexus"] for r in report["paired_descriptive_differences"]}, {0.5})
        self.assertEqual({r["donor"] for r in report["auroc_vector"]}, set(f.DONORS))

    def test_reproduction_scores_both_original_families_without_candidate(self):
        data = census()
        submission = reproduction_predictions(data)
        # Distinct values across families and observation IDs, including ties,
        # make the oracle sensitive to method mixing or row reordering.
        for row in submission["scores"]:
            cell = int(row["observation_id"].split(":")[-1])
            row["probability"] = ((cell % 3) / 2 if row["method"] == "author_plexus"
                                  else ((cell + 1) % 5) / 4)
        report = f.evaluate_reproduction(data, submission, f.digest(data))
        self.assertEqual(len(report["auroc_vector"]), 2 * 2 * 4 * 2)
        self.assertEqual({r["method"] for r in report["auroc_vector"]}, set(f.REPRODUCTION_METHODS))
        plan = f.prepare(data)
        probabilities = {(r["method"], r["donor"], r["guide_id"], r["fold"], r["observation_id"]): r["probability"]
                         for r in submission["scores"]}
        expected = {}
        for method, family in f.REPRODUCTION_METHODS.items():
            for panel in plan["panels"]:
                if panel["family"] != family:
                    continue
                for endpoint in panel["endpoints"]:
                    for fold in endpoint["folds"]:
                        key = method, panel["donor"], endpoint["guide_id"], fold["fold"]
                        positives = [probabilities[key + (r["observation_id"],)] for r in fold["test"] if r["label"]]
                        negatives = [probabilities[key + (r["observation_id"],)] for r in fold["test"] if not r["label"]]
                        expected[key] = sum((a > b) + 0.5 * (a == b) for a in positives for b in negatives) / (len(positives) * len(negatives))
        for row in report["auroc_vector"]:
            key = tuple(row[k] for k in ("method", "donor", "guide_id", "fold"))
            self.assertAlmostEqual(row["auroc"], expected[key])
        self.assertIsNone(report["reproduction_decision"])
        self.assertNotIn("paired_descriptive_differences", report)
        self.assertEqual(report["source_skips"], [
            {"family": p["family"], "donor": p["donor"], "guides": p["skipped_guides"]}
            for p in plan["panels"]])

    def test_reproduction_requires_complete_original_methods_and_rejects_candidate(self):
        data = census(); original = reproduction_predictions(data)
        bad = copy.deepcopy(original); bad["scores"].pop()
        with self.assertRaisesRegex(f.InputError, "coverage"):
            f.evaluate_reproduction(data, bad, f.digest(data))
        bad = copy.deepcopy(original)
        bad["scores"] = [r for r in bad["scores"] if r["method"] == "author_plexus"]
        with self.assertRaisesRegex(f.InputError, "coverage"):
            f.evaluate_reproduction(data, bad, f.digest(data))
        for method in ("candidate", "unrecognized"):
            bad = copy.deepcopy(original); bad["scores"][0]["method"] = method
            with self.assertRaisesRegex(f.InputError, "unexpected"):
                f.evaluate_reproduction(data, bad, f.digest(data))

    def test_reproduction_refuses_duplicated_and_outside_fold_identities(self):
        data = census(); original = reproduction_predictions(data)
        bad = copy.deepcopy(original); bad["scores"].append(bad["scores"][0])
        with self.assertRaisesRegex(f.InputError, "duplicate"):
            f.evaluate_reproduction(data, bad, f.digest(data))
        bad = copy.deepcopy(original); bad["scores"][0]["observation_id"] = "outside-original-fold"
        with self.assertRaisesRegex(f.InputError, "unexpected"):
            f.evaluate_reproduction(data, bad, f.digest(data))

    def test_reproduction_pins_and_probability_domain_are_not_relaxed(self):
        data = census(); original = reproduction_predictions(data)
        with self.assertRaisesRegex(f.InputError, "frozen pin"):
            f.evaluate_reproduction(data, original, "0" * 64)
        bad = copy.deepcopy(original); bad["plan_sha256"] = "0" * 64
        with self.assertRaisesRegex(f.InputError, "plan mismatch"):
            f.evaluate_reproduction(data, bad, f.digest(data))
        for value in (True, -1, 2, float("nan"), float("inf")):
            bad = copy.deepcopy(original); bad["scores"][0]["probability"] = value
            with self.assertRaises(f.InputError):
                f.evaluate_reproduction(data, bad, f.digest(data))

    def test_reproduction_and_improvement_schemas_cannot_be_misinterpreted(self):
        data = census(); original = reproduction_predictions(data)
        with self.assertRaisesRegex(f.InputError, "schema"):
            f.evaluate(data, original, f.digest(data))
        with self.assertRaisesRegex(f.InputError, "schema"):
            f.evaluate_reproduction(data, predictions(data), f.digest(data))
        original["schema"] = "plexus-figure4-predictions/v1"
        with self.assertRaisesRegex(f.InputError, "coverage"):
            f.evaluate(data, original, f.digest(data))

    def test_reproduction_cli_accepts_original_panel_and_preserves_undefined_decision(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); data = census()
            (p / "data.json").write_text(json.dumps(data))
            (p / "sub.json").write_text(json.dumps(reproduction_predictions(data)))
            run = subprocess.run([sys.executable, "-B", str(Path(f.__file__).resolve()),
                                  "score-reproduction", "--census", str(p / "data.json"),
                                  "--submission", str(p / "sub.json"), "--census-sha256", f.digest(data),
                                  "--output", str(p / "report.json")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads((p / "report.json").read_text())
            self.assertEqual(report["schema"], "plexus-figure4-reproduction-report/v1")
            self.assertEqual(len(report["auroc_vector"]), 32)
            self.assertIsNone(report["reproduction_decision"])

    def test_missing_duplicate_extra_and_training_predictions_rejected(self):
        data = census()
        base = predictions(data)
        bad = copy.deepcopy(base); bad["scores"].pop()
        with self.assertRaisesRegex(f.InputError, "coverage"):
            f.evaluate(data, bad, f.digest(data))
        bad = copy.deepcopy(base); bad["scores"].append(bad["scores"][0])
        with self.assertRaisesRegex(f.InputError, "duplicate"):
            f.evaluate(data, bad, f.digest(data))
        bad = copy.deepcopy(base); bad["scores"][0]["observation_id"] = "outside-roster"
        with self.assertRaisesRegex(f.InputError, "unexpected"):
            f.evaluate(data, bad, f.digest(data))
        bad = copy.deepcopy(base)
        train = f.prepare(data)["panels"][0]["endpoints"][0]["folds"][0]["train"][0]
        bad["scores"][0]["observation_id"] = train["observation_id"]
        with self.assertRaisesRegex(f.InputError, "unexpected"):
            f.evaluate(data, bad, f.digest(data))

    def test_untrusted_census_and_plan_pins_rejected(self):
        data = census(); sub = predictions(data)
        with self.assertRaisesRegex(f.InputError, "frozen pin"):
            f.evaluate(data, sub, "0" * 64)
        sub["plan_sha256"] = "0" * 64
        with self.assertRaisesRegex(f.InputError, "plan mismatch"):
            f.evaluate(data, sub, f.digest(data))

    def test_order_changes_are_pinned(self):
        data = census(); plan = f.prepare(data)
        changed = copy.deepcopy(data)
        changed["panels"][0]["observations"].reverse()
        other = f.prepare(changed)
        self.assertNotEqual(f.digest(plan), f.digest(other))
        self.assertNotEqual(plan["panels"][0]["endpoints"][0]["folds"], other["panels"][0]["endpoints"][0]["folds"])

    def test_source_population_versions_and_aggregations_are_checked(self):
        for alter in (lambda d: d["panels"].pop(),
                      lambda d: d["panels"][0].update(tau_status="Mutant"),
                      lambda d: d.update(data_record="10.5281/zenodo.14714574"),
                      lambda d: d["panels"][2]["observations"][1].update(aggregate_by=d["panels"][2]["observations"][0]["aggregate_by"])):
            data = census(); alter(data)
            with self.assertRaises(f.InputError):
                f.prepare(data)

    def test_literal_source_location_collision_is_rejected(self):
        data = census()
        rows = data["panels"][0]["observations"]
        rows[0].update(well_id="a_b", zarr_file="c")
        rows[1].update(well_id="a", zarr_file="b_c")
        with self.assertRaisesRegex(f.InputError, "concatenation collision"):
            f.prepare(data)

    def test_missing_controls_and_empty_endpoint_panel_are_not_ready(self):
        data = census()
        for row in data["panels"][0]["observations"]:
            if row["gene_id"] == "non-targeting":
                row["gene_id"] = "other"
        with self.assertRaisesRegex(f.InputError, "NTC wells"):
            f.prepare(data)
        data = census()
        data["panels"][0]["observations"] = data["panels"][0]["observations"][:1]
        with self.assertRaises(f.InputError):
            f.prepare(data)

    def test_invalid_probabilities_and_boolean_fold_rejected(self):
        data = census(); sub = predictions(data)
        for value in (float("nan"), float("inf"), -0.1, 1.1, True):
            bad = copy.deepcopy(sub); bad["scores"][0]["probability"] = value
            with self.assertRaises(f.InputError):
                f.evaluate(data, bad, f.digest(data))
        sub["scores"][0]["fold"] = True
        with self.assertRaises(f.InputError):
            f.evaluate(data, sub, f.digest(data))

    def test_cli_and_strict_json(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp); data = census()
            (p / "data.json").write_text(json.dumps(data))
            (p / "sub.json").write_text(json.dumps(predictions(data)))
            script = Path(f.__file__).resolve()
            run = subprocess.run([sys.executable, "-B", str(script), "score", "--census", str(p / "data.json"),
                                  "--submission", str(p / "sub.json"), "--census-sha256", f.digest(data),
                                  "--output", str(p / "report.json")], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(json.loads((p / "report.json").read_text())["auroc_vector"])
            (p / "bad.json").write_text('{"x": 1, "x": 2}')
            with self.assertRaises(f.InputError):
                f.read_json(p / "bad.json")
            (p / "bad.json").write_text('{"x": NaN}')
            with self.assertRaises(f.InputError):
                f.read_json(p / "bad.json")


if __name__ == "__main__":
    unittest.main()
