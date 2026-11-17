"""Generated analytical controls only; no native recordings or solver trial."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("neural028_claims", HERE / "claims.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def packet():
    """D-prime equals each declared effect: arms both have SD exactly one.

    Four animals have after fractions 1/2, 0, 1, 1/2 and before fractions zero.
    Their regime means are 1/4 and 3/4, hence sup-minus-unsup is 1/2.
    """
    out = {"schema_version": 1, "task_id": "NEURAL-028",
           "protocol": {"source_revision": "ba64ac697f5d9914926baac79399e80707a5f3a6",
                        "data_scope": "public_development_only", "phase_mapping_evidence": "generated",
                        "calibration_evidence": "generated", "selection_frozen_before_outcomes": True,
                        "activity_kind": "calcium_derived_activity", "fit_phases": ["before"],
                        "position_edges": [0, 20], "movement_edges": [0, 2],
                        "bootstrap_replicates": 100, "shuffle_replicates": 10, "seed": 7},
           "session_manifest": [], "sessions": []}
    effects = ([0.5, 0], [0, 0], [-0.5, 0.8], [0.5, 0])
    for animal, regime in enumerate(("unsup", "unsup", "sup", "sup")):
        for phase in ("before", "after"):
            key = f"m{animal}-{phase}"
            labels = [0, 2] * 4
            effect = list(effects[animal]) + [0.9] if phase == "after" else [0, 0, 0]
            activity = [[10 + animal + (label == 2) * effect[n] + noise
                         for label in labels for noise in (-1, 1, 0)] for n in range(3)]
            out["session_manifest"].append({"session_id": key, "mname": f"m{animal}",
                "datexp": phase, "blk": "1", "regime": regime, "phase": phase,
                "source_asset_sha256": "0" * 64, "mapping_evidence": "generated"})
            out["sessions"].append({"session_id": key, "activity": activity, "area_ids": [8, 8, 7],
                "trial_id": [t for t in range(8) for _ in range(3)],
                "stimulus_id": [label for label in labels for _ in range(3)],
                "trial_stimulus_id": labels, "position": [5, 5, 45] * 8,
                "movement": [1] * 24, "corridor": [True, True, False] * 8,
                "gray": [False, False, True] * 8, "sound_del_pos": [0, 5, 0, 10, 0, 30, 0, 35],
                "position_activity": [[[float(trial)] * 60 for trial in range(8)] for _ in range(3)],
                "interpolation_evidence": "generated"})
    return out


class AnalyticalReferenceTests(unittest.TestCase):
    def test_hand_derived_cells_animals_and_contrast(self):
        reference = c.build_reference(packet())
        effects = ([0.5, 0], [0, 0], [-0.5, 0.8], [0.5, 0])
        for animal, effect in enumerate(effects):
            for phase in ("before", "after"):
                row = reference["sessions"][f"m{animal}-{phase}"]
                expected = list(effect) + [0.9] if phase == "after" else [0, 0, 0]
                for index, value in enumerate(expected):
                    cell = row["neurons"][str(index)]
                    self.assertAlmostEqual(cell["matched_dprime"], value)
                    self.assertAlmostEqual(cell["raw_dprime"], value)
                    self.assertAlmostEqual(cell["reward_location_dprime"], 4)
                self.assertEqual(row["matched_regions"]["V1"]["n_neurons"], 2)
                self.assertEqual(row["unmatched_companions"]["excluded_nonvisual_neurons"], 1)
                self.assertEqual(row["support_by_stimulus"]["stimulus_2"], {
                    "eligible_frames": 8, "retained_frames": 8, "coverage": 1.0, "retained_trials": 4})
            self.assertEqual(reference["animals"][f"m{animal}"]["regions"]["V1"]["delta"],
                             (0.5, 0, 1, 0.5)[animal])
        regimes = reference["regimes_by_region"]["V1"]
        self.assertEqual(regimes["unsup"]["mean_delta"], 0.25)
        self.assertEqual(regimes["sup"]["mean_delta"], 0.75)
        self.assertEqual(reference["sup_minus_unsup_by_region"]["V1"]["estimate"], 0.5)
        self.assertEqual(reference["common_support"]["strata"], [0])
        self.assertFalse(reference["scope"]["reward_location_behavior_matched"])

    def test_complete_undefined_denominators_and_partial_animal_phase(self):
        p = packet()
        p["sessions"][0]["activity"][0] = [0.1] * 24
        r = c.build_reference(p)
        session = r["sessions"]["m0-before"]
        self.assertIsNone(session["neurons"]["0"]["matched_dprime"])
        self.assertEqual(session["matched_regions"]["V1"]["undefined_neurons"], 1)
        self.assertEqual(session["matched_regions"]["V1"]["n_neurons"], 2)
        self.assertIsNone(session["matched_regions"]["V1"]["fraction"])
        animal = r["animals"]["m0"]
        self.assertEqual(animal["regions"]["V1"], {"before": None, "after": 0.5, "delta": None})
        self.assertEqual(animal["n_before_sessions"], 1)
        self.assertEqual(r["regimes_by_region"]["V1"]["unsup"]["undefined_animals"], ["m0"])
        self.assertIsNone(r["sup_minus_unsup_by_region"]["V1"]["estimate"])
        self.assertTrue(c.grade(p, r)["all_numerical_claims_correct"])

    def test_session_means_then_mouse_means(self):
        p = packet()
        extra = copy.deepcopy(p["sessions"][1])  # m0 after becomes mean (0.5 + 0) / 2.
        extra["session_id"] = "m0-after-extra"
        extra["activity"] = copy.deepcopy(p["sessions"][0]["activity"])
        meta = copy.deepcopy(p["session_manifest"][1])
        meta.update(session_id=extra["session_id"], blk="2")
        p["session_manifest"].append(meta)
        p["sessions"].append(extra)
        r = c.build_reference(p)
        self.assertEqual(r["animals"]["m0"]["regions"]["V1"]["after"], 0.25)
        self.assertEqual(r["regimes_by_region"]["V1"]["unsup"]["mean_delta"], 0.125)
        self.assertEqual(r["regimes_by_region"]["V1"]["unsup"]["n_animals"], 2)
        self.assertEqual(r["sup_minus_unsup_by_region"]["V1"]["estimate"], 0.625)

    def test_negative_and_null_effects_are_valid_answers(self):
        for make_null in (False, True):
            p = packet()
            for item in p["session_manifest"]:
                item["regime"] = "sup" if item["regime"] == "unsup" else "unsup"
            if make_null:
                for item in p["sessions"]:
                    item["activity"] = [[10 + noise for _ in range(8) for noise in (-1, 1, 0)]] * 3
            r = c.build_reference(p)
            self.assertEqual(r["sup_minus_unsup_by_region"]["V1"]["estimate"], 0 if make_null else -0.5)
            self.assertTrue(c.grade(p, r)["all_numerical_claims_correct"])

    def test_bootstrap_intervals_retain_backend_random_sequence(self):
        e = c._backend()
        p = packet()
        reference = c.build_reference(p)
        old = e.evaluate(p)["contrasts"]["matched_selectivity"]
        for area in e.AREAS:
            self.assertEqual(reference["regimes_by_region"][area], old[area]["regimes"])
            self.assertEqual(reference["sup_minus_unsup_by_region"][area], old[area]["between_regime"])


class SubmissionTests(unittest.TestCase):
    def setUp(self):
        self.packet = packet()
        self.report = c.build_reference(self.packet)

    def test_complete_report_and_reordered_maps(self):
        self.report["sessions"] = dict(reversed(list(self.report["sessions"].items())))
        result = c.grade(self.packet, self.report)
        self.assertTrue(result["all_numerical_claims_correct"])
        self.assertNotIn("expected", json.dumps(result))
        self.assertIn("free_text_reasoning", result["not_graded"])

    def test_sign_scope_companion_coverage_and_interval_errors_are_checked(self):
        mutations = [
            lambda r: r["sup_minus_unsup_by_region"]["V1"].update(estimate=-0.5),
            lambda r: r["scope"].update(reward_location_behavior_matched=True),
            lambda r: r["sessions"]["m0-before"]["neurons"]["0"].update(reward_location_dprime=0),
            lambda r: r["sessions"]["m0-before"]["support_by_stimulus"]["stimulus_2"].update(retained_trials=3),
            lambda r: r["sup_minus_unsup_by_region"]["V1"].update(ci95=[-100., 100.]),
        ]
        for mutate in mutations:
            report = copy.deepcopy(self.report)
            mutate(report)
            result = c.grade(self.packet, report)
            self.assertFalse(result["all_numerical_claims_correct"])
            self.assertTrue(result["incorrect_claim_paths"])

    def test_missing_extra_or_renamed_id_rejected(self):
        for mutate in (
            lambda r: r["sessions"].pop("m0-before"),
            lambda r: r["sessions"].update(undeclared=r["sessions"]["m0-before"]),
            lambda r: r["sessions"]["m0-before"]["neurons"].pop("2"),
            lambda r: r["animals"]["m0"]["regions"].pop("aHV"),
            lambda r: r.update(targets={}),
        ):
            report = copy.deepcopy(self.report)
            mutate(report)
            with self.assertRaises(c.ClaimError):
                c.grade(self.packet, report)

    def test_no_private_reference_or_wrong_packet_can_be_substituted(self):
        self.report["packet_sha256"] = "f" * 64
        with self.assertRaisesRegex(c.ClaimError, "wrong report identity"):
            c.grade(self.packet, self.report)
        self.report = c.build_reference(self.packet)
        self.packet["sessions"][0]["activity"][0][0] += 1
        with self.assertRaisesRegex(c.ClaimError, "wrong report identity"):
            c.grade(self.packet, self.report)

    def test_nonfinite_bool_as_number_string_number_rejected(self):
        for value in (float("nan"), float("inf"), True, "0.5", 10**400):
            report = copy.deepcopy(self.report)
            report["sup_minus_unsup_by_region"]["V1"]["estimate"] = value
            with self.assertRaises(c.ClaimError):
                c.grade(self.packet, report)

    def test_zero_cannot_replace_undefined_and_null_cannot_replace_zero(self):
        self.report["sup_minus_unsup_by_region"]["aHV"]["estimate"] = 0
        self.report["sessions"]["m0-before"]["neurons"]["0"]["matched_dprime"] = None
        result = c.grade(self.packet, self.report)
        self.assertEqual(len(result["incorrect_claim_paths"]), 2)

    def test_fixed_numeric_tolerance_and_exact_counts(self):
        self.report["sup_minus_unsup_by_region"]["V1"]["estimate"] += 1e-8
        self.assertTrue(c.grade(self.packet, self.report)["all_numerical_claims_correct"])
        self.report["sup_minus_unsup_by_region"]["V1"]["estimate"] += 1e-4
        self.assertFalse(c.grade(self.packet, self.report)["all_numerical_claims_correct"])
        self.report["regimes_by_region"]["V1"]["unsup"]["n_animals"] = 2.0
        with self.assertRaises(c.ClaimError):
            c.grade(self.packet, self.report)

    def test_duplicate_keys_nonfinite_tokens_and_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, report, score = root / "packet.json", root / "report.json", root / "score.json"
            source.write_text(json.dumps(self.packet))
            report.write_text(json.dumps(self.report))
            subprocess.run([sys.executable, "-B", str(HERE / "claims.py"), "--packet", str(source),
                            "--submission", str(report), "--output", str(score)], check=True)
            self.assertTrue(json.loads(score.read_text())["all_numerical_claims_correct"])
            for text in ('{"a": 1, "a": 2}', '{"x": NaN}', '{"x": 1e400}'):
                report.write_text(text)
                if "1e400" in text:
                    with self.assertRaises(c.ClaimError):
                        c._check_json(c.read_json(report))
                else:
                    with self.assertRaises(c.ClaimError):
                        c.read_json(report)


if __name__ == "__main__":
    unittest.main()
