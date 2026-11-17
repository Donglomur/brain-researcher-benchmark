"""Generated complete-panel software controls; no EEG or authentic targets."""
import copy
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("n012_detector_score", ROOT / "score_detector.py")
scorer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scorer)
analysis, io = scorer.load_scoring()
ARMS = analysis.ARMS


def sha(value):
    return hashlib.sha256(io.encoded(value)).hexdigest()


def fixture():
    """727 synthetic records, 47 Siena events and conspicuously fake lineage.

    CHB has perfect predictions in every arm. Siena native detects one event in
    one of person zero's three files; harmonized detects all events; normalized
    additionally alarms once per file; timing detects nothing. Six other Siena
    people have one extra event. All source/phase pins are generated identities,
    not statements about actual acquisition, detector execution or provenance.
    """
    rows = []
    for cohort, count, people, offset in (("CHB", 686, 23, 1000), ("Siena", 41, 14, 2000)):
        for i in range(count):
            person = i % people
            rid = format(len(rows) + 1, "024x")
            events = [[100, 110]]
            if cohort == "Siena" and 1 <= i <= 6:
                events.append([400, 410])
            arms = {arm: copy.deepcopy(events) for arm in ARMS}
            if cohort == "Siena":
                arms = {"native": [[100, 110]] if i == 0 else [],
                        "harmonized": copy.deepcopy(events),
                        "normalized": copy.deepcopy(events) + [[800, 810]], "timing": []}
            rows.append({"recording_id": rid, "patient_id": format(offset + person, "024x"),
                         "cohort": cohort, "duration_seconds": 1000,
                         "montage_sha256": sha(["invented_montage", cohort]),
                         "signal": {"file": "signals/" + rid + ".h5", "bytes": 1,
                                    "sha256": sha(["no_signal_file_exists", rid])},
                         "annotations": events, "arms": arms})
    profile = {"schema": "neural012_scientific_profile_v1", "target": "T1_pinned_parser_intervals",
               "montage": "M1_fixed18_release_whitelist", "temporal": "E1_offline_whole_record",
               "fit": "F2_two_phase", "query": "Q1_whole_job", "comparison": "O1_reference_controlled",
               "qualification_status": "unissued", "label_profile": "C1_source_parser"}
    base = {"schema_version": 2, "task_id": "NEURAL-012", "scientific_profile": profile,
            "source_qualification_sha256": sha("generated_unqualified_source"),
            "records": [{k: v for k, v in row.items() if k not in ("arms", "annotations")} for row in rows]}
    programme = {arm: sha(["generated_program", arm]) for arm in ARMS}
    pin = {"bytes": 1, "sha256": sha("generated_artifact")}
    lineages = []
    for arm in ARMS:
        for person in [format(1000 + i, "024x") for i in range(23)] + [None]:
            job = arm + ":" + (person if person is not None else "full-target")
            lineages.append({"job_id": job, "arm": arm, "held_source_patient": person,
                             "fit_case_sha256": sha([job, "fit"]), "predict_case_sha256": sha([job, "predict"]),
                             "programme_sha256": programme[arm], "fit_state": dict(pin), "prediction": dict(pin),
                             "fit_container_id": sha([job, "synthetic_fit_container"]),
                             "predict_container_id": sha([job, "synthetic_predict_container"]),
                             "fit_captured_ns": 0, "predict_admitted_ns": 1,
                             "training_use_declaration": "no_fit", "complete": True})
    evidence = {"schema": "neural012_phase_execution_evidence_v1", "panel_sha256": sha(base),
                "source_targets_sha256": sha("generated_source_targets"), "plan_sha256": sha("generated_plan"),
                "scientific_profile_sha256": sha(profile), "programme_sha256": programme,
                "stream_pins": {arm: dict(pin) for arm in ARMS}, "logical_jobs": 96, "phase_invocations": 192,
                "lineages": lineages, "operational_phase_order_observed": True,
                "semantic_fit_use_verified": False, "native_isolation_qualified": False,
                "scientifically_qualified": False,
                "comparison": {"schema": "neural012_comparison_source_identity_v1",
                               "mode": "controlled_reference_preprocessing",
                               "arm_modes": {arm: "audited_fixed_reference" for arm in ARMS},
                               "timing": "fixed_elapsed_minute_reference",
                               "named_method_source_identity_verified": True, "runtime_qualified": False,
                               "protocol_sha256": sha("generated_protocol_identity")}}
    return dict(base, records=rows, execution_evidence=evidence, seal_sha256=sha("generated_seal"))


class DetectorScoreTests(unittest.TestCase):
    def setUp(self):
        self.packet = fixture()

    def score(self, packet=None):
        raw = io.encoded(self.packet if packet is None else packet)
        return scorer.score_bytes(raw, hashlib.sha256(raw).hexdigest(), analysis, io)

    def test_complete_panel_pooling_macro_and_pairing(self):
        result = self.score()
        self.assertEqual(result["recordings"], 727)
        self.assertEqual(result["biological_patients"], 37)
        self.assertEqual(sum(len(r["annotations"]) for r in self.packet["records"] if r["cohort"] == "Siena"), 47)
        native = result["primary_by_arm"]["native"]
        self.assertEqual(native["n"], 14)
        self.assertAlmostEqual(native["mean"], 1 / 28)
        self.assertAlmostEqual(native["standard_error"], 1 / 28)
        # These distinguish patient pooling from recording-macro and pooled-all.
        self.assertNotAlmostEqual(native["mean"], 1 / 41)
        self.assertNotAlmostEqual(native["mean"], 2 / 48)
        self.assertEqual(result["primary_by_arm"]["harmonized"]["mean"], 1)
        self.assertAlmostEqual(result["primary_by_arm"]["normalized"]["mean"], 160 / 231)
        self.assertEqual(result["primary_by_arm"]["timing"]["mean"], 0)
        delta = result["target_paired_contrasts"]["harmonized_minus_native"]["event_f1"]
        self.assertAlmostEqual(delta["mean"], 27 / 28)
        self.assertAlmostEqual(delta["standard_error"], 1 / 28)
        self.assertEqual((delta["positive"], delta["negative"], delta["zero"]), (14, 0, 0))
        shift = result["unpaired_cohort_shifts"]["native"]["event_f1"]
        self.assertEqual((shift["source_n"], shift["target_n"], shift["paired_people"]), (23, 14, False))
        self.assertAlmostEqual(shift["target_minus_source_mean"], -27 / 28)
        self.assertAlmostEqual(shift["descriptive_standard_error"], 1 / 28)

    def test_companion_metrics_and_no_qualification_promotion(self):
        result = self.score()
        secondary = result["secondary_by_arm"]
        self.assertAlmostEqual(secondary["native"]["event_sensitivity"]["mean"], 1 / 42)
        self.assertEqual(secondary["normalized"]["event_sensitivity"]["mean"], 1)
        self.assertAlmostEqual(secondary["normalized"]["false_alarms_per_24_observed_hours"]["mean"], 86.4)
        self.assertEqual(result["outcome_kind"], "frozen_detector_performance")
        self.assertEqual(result["evidence_scope"], "post_prediction_packet_recalculation_only")
        self.assertFalse(result["interpretation"]["scientifically_qualified"])
        self.assertFalse(result["frontier_improvement_established"])
        self.assertNotIn("maximum_scaled_reconstruction_error", io.encoded(result).decode())

    def test_missing_records_arms_phases_or_person_identity_fail(self):
        mutations = [lambda p: p["records"].pop(),
                     lambda p: p["records"][0]["arms"].pop("timing"),
                     lambda p: p["execution_evidence"]["lineages"].pop(),
                     lambda p: p["records"][-1].update(patient_id=p["records"][0]["patient_id"])]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                value = copy.deepcopy(self.packet)
                mutate(value)
                with self.assertRaises(ValueError):
                    self.score(value)

    def test_unfrozen_event_transform_and_false_qualification_fail(self):
        value = copy.deepcopy(self.packet)
        value["records"][0]["arms"]["native"] = [[100, 110], [120, 130]]
        with self.assertRaisesRegex(ValueError, "canonical"):
            self.score(value)
        value = copy.deepcopy(self.packet)
        value["execution_evidence"]["scientifically_qualified"] = True
        with self.assertRaises(ValueError):
            self.score(value)

    def test_input_hash_and_duplicate_json_key_fail(self):
        raw = io.encoded(self.packet)
        with self.assertRaisesRegex(ValueError, "SHA256"):
            scorer.score_bytes(raw, "0" * 64, analysis, io)
        duplicate = b'{"x":1,"x":2}'
        with self.assertRaisesRegex(ValueError, "duplicate"):
            scorer.score_bytes(duplicate, hashlib.sha256(duplicate).hexdigest(), analysis, io)

    def test_pinned_sources_and_import_alias_restoration(self):
        sentinel = types.ModuleType("analysis")
        prior = sys.modules.get("analysis")
        sys.modules["analysis"] = sentinel
        try:
            loaded, _ = scorer.load_scoring()
            self.assertIsNot(loaded, sentinel)
            self.assertIs(sys.modules["analysis"], sentinel)
        finally:
            if prior is None:
                sys.modules.pop("analysis", None)
            else:
                sys.modules["analysis"] = prior
        original = scorer.SOURCE_PINS["analysis"]
        scorer.SOURCE_PINS["analysis"] = "0" * 64
        try:
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                scorer.load_scoring()
        finally:
            scorer.SOURCE_PINS["analysis"] = original

    def test_cli_has_no_analyst_submission_dependency_and_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            packet, output = root / "synthetic_packet.json", root / "detector.json"
            raw = io.encoded(self.packet)
            packet.write_bytes(raw)
            argv = [sys.executable, "-I", "-B", str(ROOT / "score_detector.py"),
                    "--input", str(packet), "--input-sha256", hashlib.sha256(raw).hexdigest(),
                    "--output", str(output)]
            completed = subprocess.run(argv, capture_output=True, text=True, timeout=20)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            before = output.read_bytes()
            self.assertAlmostEqual(io.strict(before)["primary_by_arm"]["native"]["mean"], 1 / 28)
            again = subprocess.run(argv, capture_output=True, text=True, timeout=20)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(output.read_bytes(), before)
            bad = root / "bad.json"
            rejected = argv[:-1] + [str(bad)]
            rejected[rejected.index("--input-sha256") + 1] = "0" * 64
            self.assertNotEqual(subprocess.run(rejected, capture_output=True, timeout=20).returncode, 0)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
