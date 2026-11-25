"""Generated metadata controls for the declaration-to-prediction grading join.

No model, neural array, original evaluator, target or container is opened. The
existing transport/protocol admission boundaries are injected as admitted; the
actual grade function, captured-result checks, file pins and declaration join
remain real. These controls qualify only that join, not runtime containment.
"""
from contextlib import ExitStack
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


def load_episode(source):
    spec = importlib.util.spec_from_file_location("_smc_grade_binding", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


episode = load_episode(Path(__file__).with_name("episode.py"))


class GeneratedPair:
    """Tiny metadata-only closed pair with opaque, deliberately non-HDF5 files."""

    def __init__(self, api, outcome):
        self.api, self.outcome = api, outcome
        self.temporary = tempfile.TemporaryDirectory(prefix="smc-declaration-control-")
        self.root = Path(self.temporary.name).resolve()
        self.protocol_root = self.root / "protocol"
        self.execution = self.root / "execution"
        self.pair_root = self.root / "materials"
        for directory in (self.protocol_root, self.execution, self.pair_root):
            directory.mkdir()
        self.protocol_path = self.protocol_root / "PROTOCOL.json"
        self.closed_path = self.execution / "CLOSED.json"
        self.output = self.root / "report.json"
        self.target = self.root / "absent-target.h5"
        self.profile = {"generated_profile": True}
        source = {"sha256": "1" * 64, "bytes": 1}
        qualification = {"sha256": "2" * 64, "bytes": 2}
        self.runtime = {"qualification": qualification, "image": "generated-image"}
        self.protocol = {"source": source, "outcome": outcome, "programs": {},
                         "pair_path": str(self.pair_root / "pair_manifest.json"),
                         "task_path": str(self.pair_root / "task.json")}
        self.closed = {"schema": "smc_restricted_closed_pair_v1", "route": api.ROUTE,
                       "both_conditions_closed_before_private_grade": True,
                       "private_target_accessed": False, "conditions": {},
                       "protocol_path": str(self.protocol_path),
                       "protocol_sha256": "3" * 64, "source": source,
                       "outcome": outcome, "runtime_qualification": qualification}
        self.freezes = {}
        for condition in api.CONDITIONS:
            programme = self.protocol_root / condition
            programme.mkdir()
            code_pin = api.pin(b"# generated inert programme\n")
            declaration = {"schema": "smc_continuous_submission_declaration_v2",
                           "role": "construction_control", "method_id": "generated-" + condition,
                           "condition": condition, "outcome": outcome,
                           "methods": {key: {"source_sha256": code_pin["sha256"], "seed": 17,
                                             "recipe": None, "behavior_guided_fitting": False,
                                             "behavior_guided_selection": False, "asset_usage": []}
                                       for key in api.KEYS[outcome]}}
            declaration_pin = self.save(programme / "declaration.json", declaration)
            self.protocol["programs"][condition] = {"program": code_pin, "declaration": declaration_pin}
            job_root = self.execution / "jobs" / condition
            job_root.mkdir(parents=True)
            self.save(job_root / "EXECUTION.json", {"generated_job": condition})
            role = "A" if condition == api.CONDITIONS[0] else "B"
            exposure = {"mounts": [], "source": source, "image": self.runtime["image"],
                        "role": role, "command": api.COMMAND, "boundary_audit": qualification}
            exposure_pin = self.save(job_root / "EXPOSURE.json", exposure)
            request = {"phase_id": condition, "role": role, "image": self.runtime["image"],
                       "source": source, "command": api.COMMAND, "workdir": "/work",
                       "action": "held_attempt", "resources": self.profile,
                       "output": {"kind": "generic", "manifest": "OUTPUTS.json"},
                       "exposure": exposure_pin}
            request_raw = api.request_bytes(request)
            (job_root / "REQUEST.json").write_bytes(request_raw)
            quarantine = self.execution / "quarantine" / condition
            quarantine.mkdir(parents=True)
            predictions = {}
            inventory = {}
            for key in api.KEYS[outcome]:
                filename = quarantine / (key + ".h5")
                raw = ("opaque generated prediction: " + key).encode()
                filename.write_bytes(raw)
                inventory[filename.name] = api.pin(raw)
                predictions[key] = {"path": str(filename), "sha256": api.pin(raw)["sha256"]}
            result = {"schema": "smc_restricted_program_result_v1", "outcome": outcome,
                      "condition": condition, "program_sha256": code_pin["sha256"],
                      "declaration_sha256": declaration_pin["sha256"],
                      "submission_keys": api.KEYS[outcome]}
            inventory["RESULT.json"] = self.save(quarantine / "RESULT.json", result)
            inventory["OUTPUTS.json"] = self.save(quarantine / "OUTPUTS.json", {"generated": True})
            receipt = {"quarantine_root": str(quarantine), "output_inventory": {"complete": True, "files": inventory},
                       "exposure": exposure_pin, "input_before": [], "input_after": []}
            receipt_path = self.execution / "control" / condition / "RECEIPT.json"
            receipt_pin = self.save(receipt_path, receipt)
            frozen = {"condition": condition, "outcome": outcome, "submissions": predictions,
                      "declaration": declaration, "declaration_sha256": declaration_pin["sha256"],
                      "declaration_body_sha256": self.digest(declaration)}
            freeze_path = self.execution / "freezes" / (condition + ".json")
            freeze_pin = self.save(freeze_path, frozen)
            self.freezes[condition] = frozen
            self.closed["conditions"][condition] = {"receipt_path": str(receipt_path), "receipt": receipt_pin,
                "freeze_path": str(freeze_path), "freeze": freeze_pin, "request": api.pin(request_raw)}
        self.save(self.protocol_path, self.protocol)
        self.closed_pin = self.save(self.closed_path, self.closed)
        self.score = Mock(side_effect=self.generated_score)

    @staticmethod
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def save(self, filename, value):
        filename.parent.mkdir(parents=True, exist_ok=True)
        raw = self.api.encoded(value)
        filename.write_bytes(raw)
        return self.api.pin(raw)

    def rebind_freeze(self, condition):
        frozen = self.freezes[condition]
        # Preserve the continuous scorer's self-consistency check, exposing the
        # missing independent join to the declaration captured during execution.
        frozen["declaration_body_sha256"] = self.digest(frozen["declaration"])
        row = self.closed["conditions"][condition]
        row["freeze"] = self.save(Path(row["freeze_path"]), frozen)
        self.closed_pin = self.save(self.closed_path, self.closed)

    def generated_score(self, frozen_path, *args, **kwargs):
        frozen = self.api.read(frozen_path)
        return {"generated_measurement_stub": True, "declaration": frozen["declaration"],
                "condition": frozen["condition"], "submission_keys": list(frozen["submissions"])}

    def grade(self):
        api = self.api
        bench = types.SimpleNamespace(hash_file=lambda p, cap: hashlib.sha256(Path(p).read_bytes()).hexdigest(),
                                      score=self.score)
        with ExitStack() as stack:
            for name, value in (("admit_protocol", lambda *a: (self.protocol, self.runtime)),
                                ("public_context", lambda *a: ({}, {})),
                                ("resources", lambda *a: self.profile),
                                ("validate_closed", lambda *a: None),
                                ("job_for", lambda p, c: {"generated_job": c}),
                                ("mounts_for", lambda *a: []),
                                ("mount_identity", lambda *a: []),
                                ("benchmark", lambda: bench)):
                stack.enter_context(patch.object(api, name, value))
            return api.grade(self.closed_path, self.closed_pin["sha256"], self.target,
                             self.root / "absent-evaluator.py", self.output, 4096)

    def close(self):
        self.temporary.cleanup()


def change_declaration(fixture, condition, mode):
    frozen = fixture.freezes[condition]
    declaration = frozen["declaration"]
    first = fixture.api.KEYS[fixture.outcome][0]
    if mode == "method_id":
        declaration["method_id"] = "a-different-declared-method"
    elif mode == "seed":
        declaration["methods"][first]["seed"] += 1
    elif mode == "source":
        declaration["methods"][first]["source_sha256"] = "a" * 64
    elif mode == "raw_sha":
        frozen["declaration_sha256"] = "b" * 64
    elif mode == "both":
        declaration["method_id"] = "replacement-declaration"
        frozen["declaration_sha256"] = fixture.api.pin(fixture.api.encoded(declaration))["sha256"]
    else:
        raise AssertionError(mode)
    fixture.rebind_freeze(condition)


class DeclarationBindingTests(unittest.TestCase):
    def fixture(self, outcome="improvement"):
        fixture = GeneratedPair(episode, outcome)
        self.addCleanup(fixture.close)
        return fixture

    def test_unchanged_declarations_keep_both_outcomes_and_conditions(self):
        for outcome in ("reproduction", "improvement"):
            with self.subTest(outcome=outcome):
                fixture = self.fixture(outcome)
                report = fixture.grade()
                self.assertEqual(fixture.score.call_count, 2)
                self.assertEqual(set(report["conditions"]), set(episode.CONDITIONS))
                for condition, measurement in report["conditions"].items():
                    self.assertEqual(measurement["declaration"], fixture.freezes[condition]["declaration"])
                    self.assertEqual(set(measurement["submission_keys"]), set(episode.KEYS[outcome]))
                self.assertFalse(fixture.target.exists())

    def test_rebound_embedded_method_seed_and_source_are_rejected(self):
        for mode in ("method_id", "seed", "source"):
            with self.subTest(mode=mode):
                fixture = self.fixture("reproduction")
                change_declaration(fixture, episode.CONDITIONS[0], mode)
                with self.assertRaisesRegex(ValueError, "Frozen declaration must match"):
                    fixture.grade()
                fixture.score.assert_not_called()
                self.assertFalse((fixture.execution / "GRADE_STARTED.json").exists())
                self.assertFalse(fixture.output.exists())

    def test_rebound_raw_declaration_identity_is_rejected(self):
        fixture = self.fixture()
        change_declaration(fixture, episode.CONDITIONS[0], "raw_sha")
        with self.assertRaisesRegex(ValueError, "Frozen declaration must match"):
            fixture.grade()
        fixture.score.assert_not_called()

    def test_rebound_embedded_and_raw_identity_are_rejected(self):
        fixture = self.fixture()
        change_declaration(fixture, episode.CONDITIONS[0], "both")
        with self.assertRaisesRegex(ValueError, "Frozen declaration must match"):
            fixture.grade()
        fixture.score.assert_not_called()

    def test_second_condition_mismatch_refuses_before_first_condition_score(self):
        fixture = self.fixture()
        change_declaration(fixture, episode.CONDITIONS[1], "method_id")
        with self.assertRaisesRegex(ValueError, "Frozen declaration must match"):
            fixture.grade()
        fixture.score.assert_not_called()
        self.assertFalse((fixture.execution / "GRADE_STARTED.json").exists())
        self.assertFalse(fixture.output.exists())


if __name__ == "__main__":
    unittest.main()
