"""Generated full-roster controls; no authentic data or participant execution."""
from copy import deepcopy
import contextlib
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import grade

FIXTURE = HERE.parent / "prepared-support-v2/test_support.py"
body = FIXTURE.read_bytes()
if hashlib.sha256(body).hexdigest() != "4ad74a7b11a61c8ae13a4cf4b9c69c4a5895be6d64836f7896f201755a9d597a":
    raise ValueError("fixture_source_changed")
spec = importlib.util.spec_from_file_location("_direct_grading_generated_fixture", FIXTURE)
fixture_module = importlib.util.module_from_spec(spec)
exec(compile(body, str(FIXTURE), "exec"), fixture_module.__dict__)
LIMITS = {"max_input_bytes": 2_000_000, "max_packet_bytes": 10_000,
          "max_response_bytes": 1000, "max_total_response_bytes": 100_000}


def capture(sessions, variable=False):
    delivery = grade.dependencies()
    owner = delivery.DirectCollection(sessions, **LIMITS)
    animals = fixture_module.support.evaluation.ANIMAL_ORDER
    for index, session in enumerate(sessions):
        for case in [c for c in session["cases"] if c["split"] == "test"]:
            for condition in delivery.CONDITIONS:
                channel = owner.channel(index, condition)
                observation = channel.observation()
                q = .5
                if variable and condition == "SHN":
                    q = .6 + .02 * animals.index(session["subject_id"])
                if variable and condition == "SBHN":
                    q = .9
                p = q if case["y"] else 1 - q
                response = {"case_id": case["case_id"], "p_left": p,
                            "observation_sha256": hashlib.sha256(observation).hexdigest()}
                channel.answer(json.dumps(response).encode())
    return owner.finish()


class GradingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sessions = fixture_module.fixture()
        cls.capture = capture(cls.sessions, variable=True)

    def test_full_support_independent_arithmetic_and_direct_identity(self):
        result = grade.grade_capture(self.sessions, self.capture, **LIMITS)
        self.assertEqual(result["access_condition"], "direct_numerical_probability")
        self.assertNotIn("methods", result)
        self.assertFalse(result["scientific_qualification"])
        self.assertFalse(result["model_execution_proved"])
        self.assertFalse(result["participant_isolation_qualified"])
        self.assertEqual(result["expected_responses"], 232)
        conditions = {r["condition"]: r for r in result["conditions"]}
        for row in conditions.values():
            self.assertEqual(len(row["sessions"]), 29)
            self.assertEqual(len(row["animals"]), 13)
            self.assertEqual(row["equal_animal_primary"]["denominator"], 13)
        neural = conditions["SHN"]
        expected = math.fsum(-math.log(.6 + .02 * i) for i in range(13)) / 13
        self.assertAlmostEqual(neural["equal_animal_primary"]["scores"]["log_loss"], expected)
        self.assertNotAlmostEqual(neural["pooled_trial_secondary"]["scores"]["log_loss"], expected)
        self.assertEqual(neural["equal_animal_primary"]["scores"]["balanced_accuracy"], 1)
        self.assertEqual(neural["equal_animal_primary"]["scores"]["auc"], 1)
        self.assertAlmostEqual(conditions["SH"]["equal_animal_primary"]["scores"]["log_loss"], math.log(2))
        self.assertEqual(conditions["SH"]["equal_animal_primary"]["scores"]["auc"], .5)
        self.assertEqual(len(result["contrasts"]), 16)
        contrast = next(c for c in result["contrasts"]
                        if c["contrast_id"] == "neural:SH:SHN" and c["metric"] == "log_loss")
        self.assertAlmostEqual(contrast["complete_equal_animal"]["value"], math.log(2) - expected)
        self.assertEqual(len(contrast["leave_one_lab"]), 7)
        self.assertEqual(len(contrast["leave_one_animal"]), 13)
        self.assertEqual(contrast["conditional_spread"]["replicates"], 1999)
        self.assertIsNotNone(contrast["conditional_spread"]["lower_0.025"])

    def test_missing_duplicate_and_history_barrier_fail_before_grading(self):
        for kind in ("missing", "duplicate", "future"):
            bad = deepcopy(self.capture)
            if kind == "missing":
                bad["predictions"].pop()
            elif kind == "duplicate":
                bad["predictions"].insert(1, deepcopy(bad["predictions"][0]))
            else:
                bad["predictions"].insert(1, bad["predictions"].pop(4))
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                grade.grade_capture(self.sessions, bad, **LIMITS)

    def test_capture_metadata_hash_probability_and_response_tampering(self):
        for kind in ("probability", "observation", "response_hash", "schema", "claim", "bool_index"):
            bad = deepcopy(self.capture)
            row = bad["predictions"][0]
            if kind == "probability":
                row["p_left"] = .2
            elif kind == "observation":
                row["observation"]["sha256"] = "0" * 64
            elif kind == "response_hash":
                row["response"]["sha256"] = "0" * 64
            elif kind == "schema":
                row["extra"] = "unaccepted"
            elif kind == "claim":
                bad["scientific_qualification"] = True
            else:
                row["session_index"] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                grade.grade_capture(self.sessions, bad, **LIMITS)
        bad = deepcopy(self.capture)
        bad["predictions"][0]["response_utf8"] = '{"case_id":"x","p_left":true,"observation_sha256":"x"}'
        with self.assertRaises(ValueError):
            grade.grade_capture(self.sessions, bad, **LIMITS)

    def test_original_slot_omission_and_preparation_pin_fail(self):
        sessions = deepcopy(self.sessions)
        sessions[0]["cases"].pop()
        with self.assertRaisesRegex(ValueError, "eligible_slot_case_bijection"):
            grade.grade_capture(sessions, self.capture, **LIMITS)
        sessions = deepcopy(self.sessions)
        # A harmless protected extra field still changes the committed input.
        sessions[0]["new_operator_note"] = "different prepared artifact"
        with self.assertRaisesRegex(ValueError, "capture_replay_mismatch"):
            grade.grade_capture(sessions, self.capture, **LIMITS)

    def test_one_class_has_undefined_ba_auc_and_defined_losses(self):
        sessions = deepcopy(self.sessions)
        for session in sessions:
            case = session["cases"][-1]
            raw = session["slots"][-1]["normalized"]["raw"]
            raw.update(choice=1, contrastLeft=1., contrastRight=None)
            session["slots"][-1]["normalized"]["choice"] = 1
            case.update(y=1, S=fixture_module.one(8, 9))
        result = grade.grade_capture(sessions, capture(sessions), **LIMITS)
        for condition in result["conditions"]:
            scores = condition["equal_animal_primary"]["scores"]
            self.assertAlmostEqual(scores["log_loss"], math.log(2))
            self.assertEqual(scores["brier"], .25)
            self.assertIsNone(scores["balanced_accuracy"])
            self.assertIsNone(scores["auc"])
        for contrast in result["contrasts"]:
            if contrast["metric"] in ("balanced_accuracy", "auc"):
                self.assertIsNone(contrast["complete_equal_animal"]["value"])
                self.assertIsNone(contrast["conditional_spread"]["lower_0.025"])

    def test_cli_protected_output_no_overwrite_and_byte_ceilings(self):
        # A caller sets TMPDIR to its owned control directory before execution.
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "prepared.json").write_text(json.dumps(self.sessions))
            (root / "capture.json").write_text(json.dumps(self.capture))
            output = root / "grade.json"
            argv = ["--prepared", str(root / "prepared.json"), "--capture", str(root / "capture.json"),
                    "--output", str(output), "--max-output-bytes", "1000000"]
            for key, value in LIMITS.items():
                argv.extend(["--" + key.replace("_", "-"), str(value)])
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(grade.main(argv), 0)
                original = output.read_bytes()
                self.assertEqual(grade.main(argv), 2)
                self.assertEqual(output.read_bytes(), original)
                self.assertEqual(os.stat(output).st_mode & 0o777, 0o600)
                output.unlink()
                small = argv[:]
                small[small.index("--max-output-bytes") + 1] = "10"
                self.assertEqual(grade.main(small), 2)
                self.assertFalse(output.exists())
            (root / "duplicate.json").write_text('{"a":0,"a":1}')
            with self.assertRaisesRegex(ValueError, "duplicate_json_key"):
                grade.strict_json(root / "duplicate.json", 100)
            with self.assertRaisesRegex(ValueError, "aggregate_input_byte_limit"):
                grade.strict_json(root / "capture.json", 1)


if __name__ == "__main__":
    unittest.main(verbosity=1)
