"""Generated protocol controls; no original observations or source fits."""
import copy
from dataclasses import FrozenInstanceError
import importlib.util
import json
from pathlib import Path
import sys
import unittest


spec = importlib.util.spec_from_file_location("rep009_protected_intake", Path(__file__).with_name("intake.py"))
intake = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = intake
spec.loader.exec_module(intake)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha(label):
    return intake.digest(label.encode())


def fixture(condition="paper_data"):
    """Small invented support with full17x2 structure, never a source manifest."""
    manifest = {
        "schema": "thalamus_3c_protected_support_v1", "task_id": intake.TASK,
        "information_condition": condition, "source_data_sha256": intake.DATA_SHA256,
        "source_analysis_sha256": intake.SCRIPT_SHA256,
        "qualification_evidence": {key: sha("generated-only/" + key) for key in (
            "original_trial_assignment", "figure_session_animal_join", "neural_input_membership",
            "original_shuffle_recipe", "source_metric_policy", "full_panel_comparison_policy",
            "protected_execution_policy")},
        "tone_ids": [f"tone-{x}" for x in range(6)], "animal_ids": [f"animal-{x}" for x in range(4)],
        "cells": [], "panels": []}
    for session in range(17):
        for condition_name in intake.CONDITIONS:
            manifest["cells"].append({
                "source_session": f"session-{session}", "animal_id": f"animal-{session % 4}",
                "condition": condition_name, "observations_sha256": sha(f"observations-{session}-{condition_name}"),
                "trials": [{"trial_id": f"trial-{trial}", "tone_id": f"tone-{trial}",
                            "partition": "train" if trial < 2 else "heldout"} for trial in range(6)]})
    for index, role in enumerate(("candidate", "author", "author_shuffle", "author_shuffle")):
        manifest["panels"].append({"panel_id": f"panel-{index}", "role": role,
            "program_sha256": sha("program-" + role), "producer_id": f"producer-{index}",
            "control_identity_sha256": None if index < 2 else sha(f"control-{index}")})
    return manifest


def bundle(manifest):
    raw = encoded(manifest)
    identity = intake.digest(raw)
    blobs, closures = {}, {}
    for meta in manifest["panels"]:
        panel = {"schema": "thalamus_3c_protected_predictions_v1", "task_id": intake.TASK,
                 "manifest_sha256": identity, "panel_id": meta["panel_id"],
                 "program_sha256": meta["program_sha256"], "cells": []}
        for cell in manifest["cells"]:
            held = [t["trial_id"] for t in cell["trials"] if t["partition"] == "heldout"]
            panel["cells"].append({"source_session": cell["source_session"], "condition": cell["condition"],
                "held_trial_ids": held, "probability_randomised": [.25 for _ in held]})
        body = encoded(panel)
        blobs[meta["panel_id"]] = body
        closures[meta["panel_id"]] = {"producer_id": meta["producer_id"], "closed": True,
            "exit_code": 0, "output_sha256": intake.digest(body), "receipt_sha256": sha("closure-" + meta["panel_id"])}
    return raw, identity, blobs, closures


def replace_panel(args, panel_id, transform):
    raw, identity, blobs, closures = args
    value = json.loads(blobs[panel_id])
    transform(value)
    blobs[panel_id] = encoded(value)
    closures[panel_id]["output_sha256"] = intake.digest(blobs[panel_id])
    return args


class ProtectedIntakeChecks(unittest.TestCase):
    def rejected_before_private(self, args):
        calls = []
        with self.assertRaises(intake.IntakeError):
            intake.admit_then_derive(*args, lambda admitted: calls.append(admitted))
        self.assertEqual(calls, [])

    def test_complete_family_both_information_conditions(self):
        for condition in intake.INFORMATION:
            with self.subTest(condition=condition):
                calls = []
                result = intake.admit_then_derive(*bundle(fixture(condition)),
                    lambda admitted: calls.append(admitted) or {"status": "test_only"})
                self.assertEqual(len(calls), 1)
                self.assertEqual(result["intake"]["cell_count"], 34)
                self.assertEqual(result["intake"]["panel_count"], 4)
                self.assertEqual(result["intake"]["information_condition"], condition)
                self.assertIsNone(result["intake"]["paper_win"])
                self.assertIsNone(result["intake"]["source_auto_auc"])
                self.assertEqual(result["intake"]["scientific_qualification"], "not_established")

    def test_last_control_cell_omission_blocks_every_private_read(self):
        args = bundle(fixture())
        replace_panel(args, "panel-3", lambda p: p["cells"].pop())
        self.rejected_before_private(args)

    def test_missing_or_extra_panel(self):
        for extra in (False, True):
            args = bundle(fixture())
            if extra:
                args[2]["extra"] = b"{}"
            else:
                del args[2]["panel-3"]
            self.rejected_before_private(args)

    def test_trial_reordering_or_shortened_vector_is_rejected(self):
        for field in ("held_trial_ids", "probability_randomised"):
            args = bundle(fixture())
            replace_panel(args, "panel-2", lambda p: p["cells"][-1][field].pop())
            self.rejected_before_private(args)
        args = bundle(fixture())
        replace_panel(args, "panel-0", lambda p: p["cells"][0]["held_trial_ids"].reverse())
        self.rejected_before_private(args)

    def test_replaced_or_reordered_session_and_condition(self):
        for transform in (lambda p: p["cells"].reverse(),
                          lambda p: p["cells"][0].update(source_session="different"),
                          lambda p: p["cells"][0].update(condition="Laser_ON")):
            args = bundle(fixture())
            self.rejected_before_private(replace_panel(args, "panel-1", transform))

    def test_labels_or_reported_scores_are_not_submission_fields(self):
        for field, value in (("labels", ["Regular"] * 4), ("auc", .99)):
            args = bundle(fixture())
            self.rejected_before_private(replace_panel(args, "panel-0", lambda p: p["cells"][0].update({field: value})))

    def test_invalid_probability_types_and_domain(self):
        for value in (True, None, "0.5", -.01, 1.01, 10**500):
            args = bundle(fixture())
            replace_panel(args, "panel-0", lambda p: p["cells"][0]["probability_randomised"].__setitem__(0, value))
            self.rejected_before_private(args)

    def test_nonfinite_underflow_and_duplicate_keys(self):
        for old, new in ((b"0.25", b"NaN"), (b"0.25", b"1e9999"),
                         (b"0.25", b"1e-9999"),
                         (b'"task_id":', b'"task_id":"wrong","task_id":')):
            args = bundle(fixture())
            body = args[2]["panel-0"].replace(old, new, 1)
            args[2]["panel-0"] = body
            args[3]["panel-0"]["output_sha256"] = intake.digest(body)
            self.rejected_before_private(args)

    def test_closed_success_and_exact_output_required(self):
        for update in ({"closed": False}, {"exit_code": 1}, {"exit_code": False},
                       {"producer_id": "other"}, {"output_sha256": sha("other")},
                       {"receipt_sha256": None}):
            args = bundle(fixture())
            args[3]["panel-3"].update(update)
            self.rejected_before_private(args)

    def test_wrong_manifest_program_or_source(self):
        args = list(bundle(fixture()))
        args[1] = sha("not-frozen")
        self.rejected_before_private(args)
        args = bundle(fixture())
        self.rejected_before_private(replace_panel(args, "panel-0", lambda p: p.update(program_sha256=sha("other"))))
        manifest = fixture()
        manifest["source_data_sha256"] = sha("different source")
        self.rejected_before_private(bundle(manifest))

    def test_missing_qualification_and_unknown_original_shuffle_count_fail(self):
        manifest = fixture()
        del manifest["qualification_evidence"]["figure_session_animal_join"]
        self.rejected_before_private(bundle(manifest))
        manifest = fixture()
        manifest["panels"] = manifest["panels"][:2]
        self.rejected_before_private(bundle(manifest))
        manifest = fixture()
        manifest["panels"][2]["control_identity_sha256"] = None
        self.rejected_before_private(bundle(manifest))

    def test_training_and_held_trials_disjoint_and_complete_tones(self):
        for mutate in (lambda c: c["trials"][0].update(trial_id=c["trials"][-1]["trial_id"]),
                       lambda c: c["trials"][0].update(tone_id="tone-1"),
                       lambda c: c.update(trials=[dict(t, partition="heldout") for t in c["trials"]])):
            manifest = fixture()
            mutate(manifest["cells"][0])
            self.rejected_before_private(bundle(manifest))
        # All six tones are required over source support, not invented in every held partition.
        self.assertEqual(len(intake.admit(*bundle(fixture())).support[0][2]), 4)

    def test_four_animals_and_condition_pair_mapping_required(self):
        manifest = fixture()
        for cell in manifest["cells"]:
            if cell["animal_id"] == "animal-3":
                cell["animal_id"] = "animal-0"
        self.rejected_before_private(bundle(manifest))
        manifest = fixture()
        manifest["cells"][1]["animal_id"] = "animal-1"
        self.rejected_before_private(bundle(manifest))

    def test_same_source_shuffle_identity_or_producer_not_deduplicated(self):
        manifest = fixture()
        manifest["panels"][3]["producer_id"] = manifest["panels"][2]["producer_id"]
        manifest["panels"][3]["control_identity_sha256"] = manifest["panels"][2]["control_identity_sha256"]
        result = intake.admit(*bundle(manifest))
        self.assertEqual(len(result.panels), 4)
        self.assertEqual(result.panels[2][2], result.panels[3][2])

    def test_variable_original_held_counts_are_preserved(self):
        manifest = fixture()
        manifest["cells"][-1]["trials"].append({"trial_id": "last-extra", "tone_id": "tone-0", "partition": "heldout"})
        result = intake.admit(*bundle(manifest))
        self.assertEqual(result.receipt()["held_trial_counts"], [4] * 33 + [5])

    def test_admitted_representation_is_detached_and_immutable(self):
        args = bundle(fixture())
        result = intake.admit(*args)
        saved = copy.deepcopy(result.receipt())
        args[2].clear()
        args[3].clear()
        self.assertEqual(result.receipt(), saved)
        with self.assertRaises(FrozenInstanceError):
            result.panels = ()
        with self.assertRaises(TypeError):
            result.panels[0][2][0][0] = .9

    def test_private_failure_is_not_retried_or_relabelled(self):
        calls = []
        def fail(admitted):
            calls.append(admitted)
            raise RuntimeError("private derivation unavailable")
        with self.assertRaisesRegex(RuntimeError, "unavailable"):
            intake.admit_then_derive(*bundle(fixture()), fail)
        self.assertEqual(len(calls), 1)

    def test_bytes_and_resource_limits(self):
        args = list(bundle(fixture()))
        args[0] = bytearray(args[0])
        self.rejected_before_private(args)
        args = bundle(fixture())
        args[2]["panel-0"] = b" " * (intake.PANEL_CAP + 1)
        self.rejected_before_private(args)
        with self.assertRaises(intake.IntakeError):
            intake.strict_json(b"{}", 1)


def condition_bundles(manifests=None):
    if manifests is None:
        manifests = {condition: fixture(condition) for condition in intake.INFORMATION}
    names = ("manifest_raw", "expected_manifest_sha256", "panel_blobs", "operator_closures")
    return {condition: dict(zip(names, bundle(manifest)))
            for condition, manifest in manifests.items()}


class MatchedConditionChecks(unittest.TestCase):
    def rejected_before_private(self, args):
        calls = []
        with self.assertRaises(intake.IntakeError):
            intake.admit_matched_then_derive(args, lambda matched: calls.append(matched))
        self.assertEqual(calls, [])

    def test_both_complete_arms_call_private_once_and_keep_full_support(self):
        calls = []
        result = intake.admit_matched_then_derive(condition_bundles(),
            lambda matched: calls.append(matched) or {"status": "generated_only"})
        self.assertEqual(len(calls), 1)
        matched = calls[0]
        self.assertEqual(tuple(b.information_condition for b in matched.bundles), intake.INFORMATION)
        shared = json.loads(matched.common_support_raw)
        self.assertEqual(shared["cells"], fixture()["cells"])
        self.assertEqual(shared["animal_ids"], fixture()["animal_ids"])
        self.assertEqual(shared["tone_ids"], fixture()["tone_ids"])
        self.assertEqual(len(shared["reference_family"]), 3)
        self.assertIsNone(result["intake"]["paper_win"])
        self.assertEqual(result["intake"]["scientific_qualification"], "not_established")
        with self.assertRaises(FrozenInstanceError):
            matched.bundles = ()

    def test_individually_valid_changed_scientific_support_rejected_jointly(self):
        def change_partition(m):
            m["cells"][-1]["trials"][0]["partition"] = "heldout"
        changes = (
            lambda m: m["cells"][-1].update(observations_sha256=sha("changed-observations")),
            lambda m: m["cells"][-1]["trials"][0].update(trial_id="different-source-trial"),
            change_partition,
            lambda m: m["cells"][-1]["trials"].reverse(),
            lambda m: m["tone_ids"].reverse(),
            lambda m: m["animal_ids"].reverse(),
            lambda m: [cell.update(animal_id="animal-1") for cell in m["cells"][:2]],
            lambda m: m["qualification_evidence"].update(source_metric_policy=sha("different-metric")),
            lambda m: m["qualification_evidence"].update(protected_execution_policy=sha("different-exposure")),
        )
        for change in changes:
            with self.subTest(change=change):
                manifests = {condition: fixture(condition) for condition in intake.INFORMATION}
                change(manifests["paper_data_author_code"])
                args = condition_bundles(manifests)
                # Establish the actual gap: both arms pass existing single-arm admission.
                for arm in args.values():
                    self.assertEqual(len(intake.admit(**arm).support), 34)
                self.rejected_before_private(args)

    def test_reference_recipe_and_complete_ordered_shuffle_family_match(self):
        for change in (
            lambda m: m["panels"][1].update(program_sha256=sha("changed-author")),
            lambda m: m["panels"][2].update(control_identity_sha256=sha("changed-shuffle")),
            lambda m: m["panels"].pop(),
            lambda m: m["panels"].__setitem__(slice(2, None), list(reversed(m["panels"][2:]))),
        ):
            manifests = {condition: fixture(condition) for condition in intake.INFORMATION}
            change(manifests["paper_data_author_code"])
            args = condition_bundles(manifests)
            for arm in args.values():
                intake.admit(**arm)
            self.rejected_before_private(args)

    def test_different_candidate_methods_probabilities_and_producers_are_allowed(self):
        manifests = {condition: fixture(condition) for condition in intake.INFORMATION}
        changed = manifests["paper_data_author_code"]
        changed["panels"][0]["program_sha256"] = sha("independent-candidate-method")
        for panel in changed["panels"]:
            panel["panel_id"] += "-code-arm"
            panel["producer_id"] += "-code-arm"
        args = condition_bundles(manifests)
        arm = args["paper_data_author_code"]
        raw_args = tuple(arm.values())
        # Neither candidate nor author prediction bodies are equality targets.
        for panel_id in ("panel-0-code-arm", "panel-1-code-arm"):
            replace_panel(raw_args, panel_id,
                lambda p: p["cells"][0]["probability_randomised"].__setitem__(0, .8))
        matched = intake.admit_matched_conditions(args)
        self.assertNotEqual(matched.bundles[0].panels[0][2], matched.bundles[1].panels[0][2])
        self.assertNotEqual(matched.bundles[0].panels[1][2], matched.bundles[1].panels[1][2])

    def test_missing_extra_or_misnamed_information_arm(self):
        args = condition_bundles()
        del args["paper_data_author_code"]
        self.rejected_before_private(args)
        args = condition_bundles()
        args["extra"] = args["paper_data"]
        self.rejected_before_private(args)
        args = condition_bundles()
        args["paper_data_author_code"] = args["paper_data"]
        self.rejected_before_private(args)

    def test_late_output_or_closure_failure_blocks_paired_private_read(self):
        for failure in ("output", "closure"):
            args = condition_bundles()
            arm = args["paper_data_author_code"]
            if failure == "output":
                replace_panel(tuple(arm.values()), "panel-3", lambda p: p["cells"].pop())
            else:
                arm["operator_closures"]["panel-3"]["closed"] = False
            self.rejected_before_private(args)

    def test_equivalent_json_serialization_matches(self):
        args = condition_bundles()
        arm = args["paper_data_author_code"]
        manifest = json.loads(arm["manifest_raw"])
        # Rebind the complete second family to a differently serialized manifest.
        raw = json.dumps(manifest, indent=1).encode()
        old_identity = arm["expected_manifest_sha256"]
        arm["manifest_raw"] = raw
        arm["expected_manifest_sha256"] = intake.digest(raw)
        for panel_id, body in arm["panel_blobs"].items():
            body = body.replace(old_identity.encode(), arm["expected_manifest_sha256"].encode())
            arm["panel_blobs"][panel_id] = body
            arm["operator_closures"][panel_id]["output_sha256"] = intake.digest(body)
        matched = intake.admit_matched_conditions(args)
        self.assertNotEqual(matched.bundles[0].manifest_sha256, matched.bundles[1].manifest_sha256)

    def test_same_declared_shuffle_repetitions_are_preserved_in_both_arms(self):
        manifests = {condition: fixture(condition) for condition in intake.INFORMATION}
        for manifest in manifests.values():
            manifest["panels"][3]["control_identity_sha256"] = manifest["panels"][2]["control_identity_sha256"]
        matched = intake.admit_matched_conditions(condition_bundles(manifests))
        family = json.loads(matched.common_support_raw)["reference_family"]
        self.assertEqual(len(family), 3)
        self.assertEqual(family[1], family[2])

    def test_matched_private_failure_not_retried_or_relabelled(self):
        calls = []
        def fail(matched):
            calls.append(matched)
            raise RuntimeError("no qualified paired assessment")
        with self.assertRaisesRegex(RuntimeError, "no qualified"):
            intake.admit_matched_then_derive(condition_bundles(), fail)
        self.assertEqual(len(calls), 1)

    def test_pair_result_detached_and_receipts_not_shared(self):
        args = condition_bundles()
        matched = intake.admit_matched_conditions(args)
        saved = matched.receipt()
        args.clear()
        altered = matched.receipt()
        altered["conditions"].clear()
        self.assertEqual(matched.receipt(), saved)


if __name__ == "__main__":
    unittest.main()
