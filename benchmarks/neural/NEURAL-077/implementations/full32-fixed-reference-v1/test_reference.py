"""Generated source controls, not a successful production reference or study.

The tiny positive exercises new ordering/report orchestration with explicit
test-only memory callbacks. Production negatives retain6400/32 and use the real
entry guards. Their placeholder roster must never reach public-data dispatch.
No original EEG, demonstrations, private labels or joins are opened.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
FIXTURE_CAP = 2 * 1024**2
GENERATED_FIXTURE_ONLY = "generated-memory-reference-control; never production admission"


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


class Artifacts:
    def __init__(self, sources):
        explicit = os.environ.get("ARTIFACT_DIR")
        parent = (Path(explicit) if explicit else Path(tempfile.gettempdir()).resolve() /
                  ("erp-reference-controls-" + secrets.token_hex(8)))
        if (not parent.is_absolute() or ".." in parent.parts or
                any(p.is_symlink() for p in (parent, *parent.parents))):
            raise ValueError("Absolute ordinary ARTIFACT_DIR required")
        if any(parent.is_relative_to(p) or p.is_relative_to(parent) for p in sources):
            raise ValueError("Artifacts and authenticated source trees must be disjoint")
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = parent / "erp-fixed-reference-generated-controls"
        self.root.mkdir(mode=0o700)
        self.written = 0; self.sequence = 0

    def area(self, name):
        self.sequence += 1
        result = self.root / (str(self.sequence) + "-" + name)
        result.mkdir(mode=0o700)
        return result

    def emit(self, path, body):
        if (not path.is_relative_to(self.root) or any(p.is_symlink() for p in (path, *path.parents)) or
                self.written + len(body) > FIXTURE_CAP):
            raise ValueError("Generated output path or byte ceiling")
        self.written += len(body)
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open("xb") as stream:
            stream.write(body)
        return pin(body)


class FixedReferenceControls(unittest.TestCase):
    maxDiff = 1000

    @classmethod
    def setUpClass(cls):
        path = HERE / "reference.py"
        spec = importlib.util.spec_from_file_location("erp_fixed_reference_control", path)
        cls.reference = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.reference
        spec.loader.exec_module(cls.reference)
        cls.modules = cls.reference.dependencies()
        cls.pair = cls.modules["pair"]; cls.core = cls.modules["core"]
        cls.artifacts = Artifacts((HERE, cls.modules["repository_root"]))
        cls.observations = []
        if (cls.reference.COUNT, cls.reference.PEOPLE, cls.pair.COUNT) != (6400, 32, 6400):
            raise ValueError("Production cardinalities changed")

    @classmethod
    def tearDownClass(cls):
        cls.artifacts.emit(cls.artifacts.root / "GENERATED_SCOPE.json", encoded({
            "schema": "erp-fixed-reference-generated-control-scope-v1",
            "authority": GENERATED_FIXTURE_ONLY, "original_payload_reads": 0,
            "original_private_loader_calls": 0, "provider_calls": 0,
            "production_positive": False, "original_metric_observations": cls.observations,
            "fixture_write_charge_before_receipt": cls.artifacts.written, "fixture_write_cap": FIXTURE_CAP}))

    def study(self):
        """Source operands valid; placeholder roster is only for pre-data refusals."""
        area = self.artifacts.area("study")
        frozen = area / "frozen"; frozen.mkdir()
        manifest = json.loads(self.modules["source_bodies"]["baseline_manifest"])
        programme_root = self.modules["repository_root"] / self.reference.BASELINE / "programme"
        captured = self.modules["bundle"].capture(programme_root, manifest)
        programme_body = self.modules["bundle"].encoded(captured)
        programme_pin = self.artifacts.emit(frozen / "PROGRAMME.json", programme_body)
        exposure = {"schema": "erp-full32-fixed-reference-exposure-v1",
            "declared_authoring_inputs": ["Generated source control metadata; no original data access."],
            "remaining32_query_or_answer_tuning_declared": False, "six_person_feature_training_declared": False,
            "prior_ungraded_query_count": 1, "prior_query_labels_opened": False,
            "programme_changed_since_prior_query": False, "pretraining_exposure": "unknown",
            "notes": "Fixture declaration only; no independent exposure attestation."}
        exposure_pin = self.artifacts.emit(frozen / "EXPOSURE.json", encoded(exposure))
        roster_pin = self.artifacts.emit(frozen / "ROSTER.json", encoded({
            "generated_placeholder": True, "must_not_reach_prequery_metadata": True}))
        contract = {"schema": "erp-full32-fixed-reference-contract-v1", "selected": True,
            "condition_id": "erp-core-remaining-persons-released-marker-v1", "condition": self.reference.CONDITION,
            "query_count": 6400, "people": 32, "public_root": str(area / "input" / "public"),
            "public_manifest": pin(b"unopened-generated-manifest"), "roster": roster_pin,
            "frozen_roster": {"path": str(frozen / "ROSTER.json"), "file": roster_pin},
            "programme": {"path": str(frozen / "PROGRAMME.json"), "file": programme_pin,
                          "bundle_identity": captured["bundle_identity"]},
            "authoring_exposure": {"path": str(frozen / "EXPOSURE.json"), "file": exposure_pin},
            "interpreter": {"path": str(area / "unexecuted-interpreter"), **pin(b"unexecuted-fixture")},
            "sandbox": {"path": "/usr/bin/sandbox-exec", **pin(b"unexecuted-fixture")},
            "limits": {"episode_work_seconds": 30, "episode_cleanup_seconds": 5,
                       "campaign_seconds": 180, "read_bytes": 32 * 1024**3, "write_bytes": 1024**2},
            "information_policy": self.reference.POLICY, "metric_policy": self.reference.METRIC_POLICY,
            "source_bindings": self.modules["source_binding_pin"], "adapter_sources": self.modules["source_members"],
            "freeze_stage": {"query_records_opened": 0}}
        self.reference.verify_frozen(contract, self.modules)
        return area, contract, exposure

    def header(self, contract, commitment):
        return {"schema": "erp-full6400-numeric-arm-v1", "reference_scope": "full32_fixed_reference_only",
            "status": "closed_unscored_arm", "condition": self.reference.CONDITION, "contract": commitment,
            "public_manifest": contract["public_manifest"], "study_source_bindings": contract["source_bindings"],
            "source_bindings": pin(self.modules["core_bindings_body"]),
            "programme_identity": contract["programme"]["bundle_identity"],
            "bundle_identity": contract["programme"]["bundle_identity"],
            "authoring_exposure": contract["authoring_exposure"]["file"],
            "query_count": 6400, "attempt_inventory_count": 6400, "private_target_reads": 0,
            "scoring_performed": False,
            "episodes": [{"trial_id": "q-" + format(i, "032x"), "status": "ok"} for i in range(6400)]}

    def refused_before_data(self, area, contract, arm, expected):
        private = mock.Mock(side_effect=AssertionError("Private descriptor opened"))
        forbidden = AssertionError("Rejected reference reached original data/labels")
        with mock.patch.object(self.reference, "prequery_metadata", side_effect=forbidden) as metadata, \
             mock.patch.object(self.modules["consumer"], "PacketSession", side_effect=forbidden) as packet, \
             mock.patch.object(self.core, "load_private_people", side_effect=forbidden) as labels:
            with self.assertRaisesRegex(ValueError, expected):
                self.reference.evaluate_reference(contract, pin(self.reference.encode(contract)), arm, private,
                                                  area / "unwritten-result", modules=self.modules)
            private.assert_not_called(); metadata.assert_not_called(); packet.assert_not_called(); labels.assert_not_called()

    def test_generated_complete_reference_orders_labels_and_preserves_person_metrics(self):
        authority = GENERATED_FIXTURE_ONLY
        ids = ["q-" + format(i, "032x") for i in range(1, 7)]
        values = [0.2, 0.4, 0.8, 0.4, 0.8, 0.2]
        rows = b"".join(encoded({"trial_id": identifier, "target_probability": value})
                        for identifier, value in zip(ids, values))
        people = {"generated-A": [(ids[0], 0), (ids[1], 0), (ids[2], 1), (ids[3], 1)],
                  "generated-B": [(ids[4], 0), (ids[5], 1)]}
        order = []
        def admit():
            self.assertEqual(authority, GENERATED_FIXTURE_ONLY); order.append("admit")
            return self.core.parse_prediction_rows(rows, ids)
        def labels(admitted_ids):
            self.assertEqual(order, ["admit"]); self.assertEqual(admitted_ids, set(ids)); order.append("labels")
            return copy.deepcopy(people)
        with mock.patch.object(self.core, "load_private_people", side_effect=AssertionError("Original labels forbidden")) as original:
            scores = self.reference._ordered_metrics(admit, labels, self.core)
            self.assertEqual(order, ["admit", "labels"])
            self.assertEqual([r["balanced_accuracy"] for r in scores["participants"]], [0.75, 0.0])
            expected_a = -(2 * math.log(0.8) + math.log(0.6) + math.log(0.4)) / 4
            expected_b = -math.log(0.2)
            self.assertAlmostEqual(scores["participants"][0]["natural_log_loss"], expected_a, places=14)
            self.assertAlmostEqual(scores["participants"][1]["natural_log_loss"], expected_b, places=14)
            self.assertEqual(scores["participant_macro_balanced_accuracy"], 0.375)
            self.assertAlmostEqual(scores["participant_macro_natural_log_loss"], (expected_a + expected_b) / 2, places=14)
            self.assertNotAlmostEqual(scores["participant_macro_natural_log_loss"], (4 * expected_a + 2 * expected_b) / 6, places=6)
            invalid_panels = []
            missing = copy.deepcopy(people); missing.pop("generated-B"); invalid_panels.append((missing, "Every admitted prediction"))
            single = copy.deepcopy(people); single["generated-B"] = [(identifier, 0) for identifier, _ in single["generated-B"]]
            invalid_panels.append((single, "Both classes required"))
            undefined = copy.deepcopy(people); undefined["generated-B"][0] = (ids[4], None)
            invalid_panels.append((undefined, "Binary class labels"))
            for panel, expected in invalid_panels:
                with self.subTest(refusal=expected), self.assertRaisesRegex(ValueError, expected):
                    self.reference._ordered_metrics(lambda: self.core.parse_prediction_rows(rows, ids),
                                                    lambda _ids, panel=panel: panel, self.core)
            original.assert_not_called()
        self.observations.append({"authority": authority, "order": order, "generated_people": 2,
            "generated_queries": 6, "participant_macro_balanced_accuracy": scores["participant_macro_balanced_accuracy"],
            "participant_macro_natural_log_loss": scores["participant_macro_natural_log_loss"],
            "production_status": None})

    def test_partial_duplicate_tampered_and_failed_reference_refuse_before_labels(self):
        area, contract, _ = self.study(); commitment = pin(self.reference.encode(contract))
        original = self.header(contract, commitment)
        # Header-only acceptance is not complete source/context/frame admission.
        self.reference.validate_reference_header(original, commitment, contract, self.modules)
        original_root = area / "original-arm"
        original_pin = self.artifacts.emit(original_root / "ARM.json", self.reference.encode(original))
        altered_commitment = {"root": str(original_root), "receipt": pin(b"changed-arm-commitment")}
        self.refused_before_data(area, contract, altered_commitment, "Committed input changed")
        partial = copy.deepcopy(original); partial["episodes"].pop()
        duplicate = copy.deepcopy(original); duplicate["episodes"][1]["trial_id"] = duplicate["episodes"][0]["trial_id"]
        failed = copy.deepcopy(original); failed["episodes"][0]["status"] = "failed"
        for name, value, expected in (("partial", partial, "Incomplete attempt inventory"),
                                      ("duplicate", duplicate, "Every unique first response"),
                                      ("failed", failed, "Every unique first response")):
            root = area / (name + "-arm")
            arm = {"root": str(root), "receipt": self.artifacts.emit(root / "ARM.json", self.reference.encode(value))}
            with self.subTest(refusal=name):
                self.refused_before_data(area, contract, arm, expected)
        self.assertEqual(pin((original_root / "ARM.json").read_bytes()), original_pin)

    def test_changed_sources_programme_configuration_and_exposure_refuse(self):
        area, contract, exposure = self.study()
        unopened_arm = {"root": str(area / "unopened-arm"), "receipt": pin(b"unopened-reference")}
        changed = copy.deepcopy(contract); changed["source_bindings"] = pin(b"changed-source-bindings")
        self.refused_before_data(area, changed, unopened_arm, "Reference source changed after freeze")
        for selected in ("candidate", "config"):
            author = area / ("changed-" + selected); author.mkdir()
            candidate = self.modules["source_bodies"]["baseline_candidate"]
            config = self.modules["source_bodies"]["baseline_config"]
            if selected == "candidate":
                candidate += b"\n# Generated source-change refusal fixture.\n"
            else:
                value = json.loads(config); value["temperature"] = 2.0; config = encoded(value)
            self.artifacts.emit(author / "erp_template.py", candidate)
            self.artifacts.emit(author / "config.json", config)
            alternate = self.modules["bundle"].capture(author, json.loads(self.modules["source_bodies"]["baseline_manifest"]))
            body = self.modules["bundle"].encoded(alternate)
            path = area / (selected + "-PROGRAMME.json")
            selected_pin = self.artifacts.emit(path, body)
            changed = copy.deepcopy(contract)
            changed["programme"] = {"path": str(path), "file": selected_pin, "bundle_identity": alternate["bundle_identity"]}
            with self.subTest(changed=selected):
                self.refused_before_data(area, changed, unopened_arm, "Only unchanged baseline source/config")
        for field, value in (("prior_ungraded_query_count", 0), ("programme_changed_since_prior_query", True)):
            changed_exposure = copy.deepcopy(exposure); changed_exposure[field] = value
            path = area / (field + ".json")
            selected_pin = self.artifacts.emit(path, encoded(changed_exposure))
            changed = copy.deepcopy(contract); changed["authoring_exposure"] = {"path": str(path), "file": selected_pin}
            with self.subTest(changed=field):
                self.refused_before_data(area, changed, unopened_arm, "Prior ungraded query must remain explicit")

    def test_paired_entrypoint_still_requires_second_arm(self):
        area, reference, _ = self.study()
        contract = {"schema": "erp-full32-provider-pair-contract-v1", "selected": True,
            "condition_id": "erp-core-remaining-persons-released-marker-v1",
            **{k: reference[k] for k in ("public_root", "public_manifest", "programme", "authoring_exposure", "interpreter", "sandbox", "limits")},
            "provider": {"model": "generated-unused-provider", "max_output_tokens": 128},
            "information_policy": self.pair.POLICY, "source_bindings": self.modules["binding_pin"],
            "adapter_sources": self.modules["bindings"],
            "freeze_stage": {"query_records_opened": 0, "authoring_exposure_is_declaration": True}}
        arm = {self.reference.CONDITION: {"root": str(area / "unopened-arm"), "receipt": pin(b"unopened-reference")}}
        private = mock.Mock(side_effect=AssertionError("Private descriptor opened"))
        packet = mock.Mock(side_effect=AssertionError("Packet constructed"))
        with mock.patch.object(self.core, "load_private_people", side_effect=AssertionError("Original labels forbidden")) as labels:
            with self.assertRaisesRegex(ValueError, "Both paired arms required"):
                self.pair.evaluate_pair(contract, pin(self.pair.encode(contract)), arm, private,
                                        area / "unwritten-paired-result", modules=self.modules, session_factory=packet)
            private.assert_not_called(); packet.assert_not_called(); labels.assert_not_called()


if __name__ == "__main__":
    unittest.main()
