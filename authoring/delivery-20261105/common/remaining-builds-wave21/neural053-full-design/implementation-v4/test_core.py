"""Invented engineering controls only: never authentic source rows or outcomes."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
import subprocess
from unittest import mock
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
from cohort import (Profile, Refusal, ARMS, partition_images, make_aliaser,
                    make_case_metadata, validate_roster, inner_splits, study_plan,
                    validate_training_metadata)
from io_support import Budget, canonical_bytes, object_digest, admit_full_run
from preparation import neural_summary, eye_selection, prepare_full_original
from grading import (required_case_keys, grade_admitted_arrays, array_digest,
                     probability_check, case_metrics)
from study import CasePhases, fit_reference_case, author_all_candidates, predict_all_admitted
from reference import models
from storage import write_array_fresh, read_array_exact, write_json_fresh
from prediction_worker import run as worker_run
from selection import ReferenceSelection

PROFILE = Profile(classes=3, sessions=1, runs=1, engineering=True)


def invented_roster():
    images = {1000 + c * 12 + j: c for c in range(1, 4) for j in range(12)}
    query, _ = partition_images(images, PROFILE)
    rows = []
    for person in PROFILE.people:
        for epoch, (image, category) in enumerate(sorted(images.items())):
            rows.append({"person": person, "epoch_index": epoch, "session": 1, "run": 1,
                         "image_id": image, "category_id": category,
                         "partition": "query" if image in query else "training"})
    return rows


def budget(**limits):
    now = time.monotonic()
    return Budget(limits, now, now + 30)


def invented_reference_selection():
    """Typed primitive-test metadata, never authenticated training evidence.

    Production selection must be derived from actual admitted training outputs.
    This visibly invented object exercises the downstream immutable interface.
    """
    pin = {"path": "invented-reference-evidence-only", "bytes": 1, "sha256": "0" * 64}
    document = {"schema": "neural053_reference_selection_v2",
                "source_reference_program": dict(pin),
                "selection_phase": "training_only_before_query", "engineering_only": True,
                "criterion": "higher_equal_person_class_balanced_top1_then_lower_logloss_then_base_temperature_rank",
                "cases": [{"fold_ordinal": f, "arm": arm, "family": "ridge", "rank": 0,
                           "temperature": 0.1, "case_manifest": dict(pin), "training_evidence": dict(pin),
                           "final_plans": {family: dict(pin) for family in
                                           ("ridge", "lda", "fourier_ridge", "centroid")}}
                          for f in range(4) for arm in ARMS]}
    return ReferenceSelection(canonical_bytes(document))


def panels():
    records, descriptors, targets = {}, {}, {}
    selected = invented_reference_selection()
    selection_digest = selected.digest
    method_approved, execution_approved = set(), set()
    for position, key in enumerate(required_case_keys()):
        ids = [f"invented-{position}-{i}" for i in range(6)]
        descriptor = {"schema": "invented_query_support", "query_ids": ids, "classes": [1, 2, 3]}
        labels = np.array([1, 1, 2, 2, 3, 3], dtype=np.int32)
        p = np.eye(3, dtype=np.float32)[labels - 1]
        method = object_digest({"invented_method": list(key)})
        execution = {"schema": "neural053_prediction_execution_v1", "context_key": list(key),
                     "method_admission_digest": method, "query_descriptor_digest": object_digest(descriptor),
                     "reference_selection_digest": selection_digest,
                     "probabilities_digest": array_digest(p), "natural_exit_code": 0,
                     "source_state_unchanged": True, "engineering_only": True}
        method_approved.add(method)
        execution_approved.add(object_digest(execution))
        descriptors[key] = descriptor
        records[key] = {"context_key": list(key), "method_admission_digest": method,
                        "query_descriptor_digest": object_digest(descriptor), "query_ids": ids,
                        "classes": [1, 2, 3], "reference_selection_digest": selection_digest,
                        "probabilities": p, "execution_receipt": execution}
        targets[key] = labels
    return records, descriptors, frozenset(method_approved), selected, frozenset(execution_approved), targets


class RecorderReferenceEngine:
    """Known-label invented arithmetic stub, not a scientific/model comparison."""
    setting_grid = staticmethod(models.setting_grid)
    TrainingMetricAccumulator = models.TrainingMetricAccumulator
    select_setting = staticmethod(models.select_setting)

    @staticmethod
    def fit_reference(family, parameters, X, y, n_classes, fold_ordinal, arm):
        return {"family": family, "classes": n_classes, "n": len(X), "parameters": parameters}

    @staticmethod
    def score_reference(fitted, X):
        out = np.zeros((len(X), fitted["classes"]), dtype=np.float64)
        out[np.arange(len(X)), X[:, 0].astype(int) - 1] = 1
        return out

    @staticmethod
    def export_plan(fitted, temperature):
        return {"invented_stub_only": fitted["family"], "temperature": temperature}


class CoreControls(unittest.TestCase):
    def test_complete_grouped_splits_and_paired_aliases(self):
        rows = invented_roster()
        alias = make_aliaser(b"invented-fixture-key-only-32bytes!!")
        packet, query, train, held = make_case_metadata(rows, "BIGMEG1", "invented/paired", alias, PROFILE)
        packet2, query2, _, _ = make_case_metadata(rows, "BIGMEG1", "invented/paired", alias, PROFILE)
        self.assertEqual(packet, packet2)
        self.assertEqual(query, query2)
        changed, _, _, _ = make_case_metadata(rows, "BIGMEG1", "invented/another-rep", alias, PROFILE)
        self.assertNotEqual(packet["training_ids"], changed["training_ids"])
        self.assertEqual(len(train), 90)
        self.assertEqual(len(held), 6)
        splits = inner_splits(packet, PROFILE)
        self.assertEqual(len(splits), 15)
        self.assertTrue(all(len(x["fit_indices"]) == 48 and len(x["validation_indices"]) == 6 for x in splits))
        self.assertNotIn("query_ids", packet)
        self.assertTrue(all(set(g) == {"training_id", "person_group", "image_group", "image_block"} for g in packet["groups"]))

    def test_missing_image_person_or_bad_groups_refuse(self):
        rows = invented_roster()
        with self.assertRaises(Refusal):
            validate_roster(rows[:-1], PROFILE)
        alias = make_aliaser(b"invented-fixture-key-only-32bytes!!")
        packet, _, _, _ = make_case_metadata(rows, "BIGMEG1", "invented", alias, PROFILE)
        packet["groups"][0]["image_block"] = (packet["groups"][0]["image_block"] + 1) % 5
        with self.assertRaises(Refusal):
            validate_training_metadata(packet, PROFILE)

    def test_window_index_and_missingness(self):
        sensors = [f"invented-{i}" for i in range(271)]
        data = np.zeros((1, 271, 281), dtype=np.float32)
        data[:, :, 40:80] = 2
        data[0, 0, 40:80] = np.nan
        mean, coverage = neural_summary(data, np.arange(-20, 261) / 200, sensors, sensors)
        self.assertEqual(mean[0, 0], 0)
        self.assertEqual(coverage[0, 0], 0)
        self.assertTrue((mean[0, 1:] == 2).all())
        self.assertTrue((coverage[0, 1:] == 1).all())
        times = np.round(-100 + np.arange(1681) * 1000 / 1200)
        selected = eye_selection(times, 0)
        self.assertEqual(np.flatnonzero(selected).tolist(), list(range(240, 480)))
        with self.assertRaises(Refusal):
            eye_selection(times[::-1], 0)

    def test_mode_order_and_full_counts(self):
        phase = CasePhases("fixed_program", ("fixed_program", 0, 0, "neural"))
        with self.assertRaises(Refusal):
            phase.transition("training_admitted", "0" * 64)
        for event in ("program_sealed", "training_admitted", "model_sealed", "method_admitted", "query_completed"):
            phase.transition(event, "0" * 64)
        with self.assertRaises(Refusal):
            phase.transition("model_sealed", "0" * 64)
        plan = study_plan()
        self.assertEqual(plan["author_contexts"], 96)
        self.assertEqual(plan["prospective_reference_fits"], 3904)
        self.assertEqual(len(set(required_case_keys())), 160)

    def test_reference_orchestration_all244_training_only_operations(self):
        alias = make_aliaser(b"invented-fixture-key-only-32bytes!!")
        packet, _, _, _ = make_case_metadata(invented_roster(), "BIGMEG1", "invented", alias, PROFILE)
        X = np.asarray(packet["training_labels"], dtype=np.float64)[:, None]
        resource = budget(reference_fits=244)
        result = fit_reference_case(X, packet, 0, "ocular", resource, PROFILE, RecorderReferenceEngine)
        self.assertEqual(result["fits"], 244)
        self.assertEqual(resource.used["reference_fits"], 244)
        self.assertEqual(len(result["selection_records"]), 48)
        self.assertEqual(result["primary_family"], "ridge")
        self.assertEqual(result["unfitted_prior_controls"]["training_counts"], [30, 30, 30])
        self.assertEqual(result["unfitted_prior_controls"]["uniform_float32"],
                         result["unfitted_prior_controls"]["training_frequency_float32"])
        self.assertTrue(result["engineering_profile"])
        self.assertFalse(result["empirical_competence_established"])

    def test_all_panels_before_any_target_and_exact_outputs(self):
        records, descriptors, methods, selected, executions, targets = panels()
        called = []
        def loader(_):
            called.append(True)
            return targets
        result = grade_admitted_arrays(records, descriptors, methods, selected, executions, loader, PROFILE)
        self.assertEqual(len(called), 1)
        self.assertEqual(len(result["cases"]), 160)
        self.assertEqual(result["unfitted_prior_controls"]["uniform"]["top1"], 1 / 3)
        self.assertTrue(all(x["top1"] == 1 for x in result["cases"]))
        self.assertFalse(result["scientific_qualification_conferred"])
        called.clear()
        last = required_case_keys()[-1]
        records[last]["probabilities"][0] = 0
        with self.assertRaises(Refusal):
            grade_admitted_arrays(records, descriptors, methods, selected, executions, loader, PROFILE)
        self.assertFalse(called)

    def test_unapproved_completion_and_misordered_support_refuse_before_targets(self):
        records, descriptors, methods, selected, executions, targets = panels()
        def forbidden(_):
            self.fail("Target loader must not run")
        with self.assertRaises(Refusal):
            grade_admitted_arrays(records, descriptors, methods, selected, frozenset(), forbidden, PROFILE)
        records[required_case_keys()[0]]["query_ids"] = list(reversed(records[required_case_keys()[0]]["query_ids"]))
        with self.assertRaises(Refusal):
            grade_admitted_arrays(records, descriptors, methods, selected, executions, forbidden, PROFILE)

    def test_zero_probability_and_ties_preserved(self):
        p = np.tile(np.asarray([.5, .5, 0], dtype=np.float32), (6, 1))
        result = case_metrics(p, np.asarray([1, 1, 2, 2, 3, 3]), PROFILE)
        self.assertEqual(result["top1"], 1 / 3)
        self.assertTrue(np.isposinf(result["log_loss"]))
        with self.assertRaises(Refusal):
            probability_check(p * .5, 6, 3)

    def test_production_admission_refuses_before_original_operands(self):
        with self.assertRaises(Refusal):
            prepare_full_original("DO_NOT_OPEN", None, None, None, {}, {}, frozenset(), budget(source_read=0))
        with self.assertRaises(Refusal):
            admit_full_run({"pass": True}, {"profile": "invented_engineering"}, frozenset())
        with self.assertRaises((KeyError, FileNotFoundError)):
            worker_run({"schema": "neural053_prediction_worker_v1", "profile": "canonical",
                        "registry": {"path": "/nonexistent-invented-neural053-registry", "bytes": 1,
                                     "sha256": "0" * 64}}, budget(source_read=1))

    def test_exact_array_storage_and_budget_failure(self):
        with tempfile.TemporaryDirectory(prefix="neural053-invented-control-") as directory:
            path = Path(directory) / "invented.npy"
            x = np.arange(12, dtype=np.float32).reshape(4, 3)
            resources = budget(source_read=4096, artifact_write=4096)
            pin = write_array_fresh(path, x, resources)
            mapped = read_array_exact(path, pin, (4, 3), resources)
            np.testing.assert_array_equal(mapped, x)
            del mapped
            with self.assertRaises(Refusal):
                read_array_exact(path, pin, (3, 4), resources)
            with self.assertRaises(Refusal):
                write_array_fresh(Path(directory) / "refused.npy", x, budget(artifact_write=0))
            self.assertFalse((Path(directory) / "refused.npy").exists())

    def test_mocked96_context_route_preserves_sealing_order(self):
        """Pure routing control: no array/model/provider/namespace qualification."""
        ports = {}
        def factory(case):
            key = (case["mode"], case["replication"], case["fold_ordinal"], case["arm"])
            class Port:
                namespace_id = str(key)
                sealed = False
                closed = False
                def seal_program(self, spec):
                    self.sealed = True
                    return {"invented_program_metadata": True}
                def authored(self):
                    return {"plan": {"invented_dim": ARMS[case["arm"]]}, "training_lineage": {},
                            "final_source_seal": {}, "resource_receipt": {}}
                def train_fixed(self, seal, packet, matrix):
                    self.assertion = self.sealed
                    if not self.sealed:
                        raise AssertionError("training before fixed program seal")
                    return self.authored()
                def investigate(self, spec, packet, matrix):
                    return self.authored()
                def close(self):
                    self.closed = True
            ports[key] = Port()
            return ports[key]
        def loader(case):
            key = (case["mode"], case["replication"], case["fold_ordinal"], case["arm"])
            self.assertTrue(case["mode"] != "fixed_program" or ports[key].sealed)
            # Shape marker only: no55,620-row invented or authentic array exists.
            return SimpleNamespace(shape=(55620, ARMS[case["arm"]])), {"invented_metadata": True}
        def sink(case, authored, events):
            return {"context_key": [case["mode"], case["replication"], case["fold_ordinal"], case["arm"]],
                    "plan_sha256": "0" * 64}
        with mock.patch("study.admit_full_run"), mock.patch("study.validate_training_metadata"), \
             mock.patch("study.training_support_digest", return_value="0" * 64), \
             mock.patch("method.plan.load_plan", side_effect=lambda p: SimpleNamespace(
                 input_dim=p["invented_dim"], class_count=1854, digest="0" * 64)):
            result = author_all_candidates(factory, loader, sink, {}, {}, {}, frozenset(), budget(author_contexts=96))
        self.assertEqual(len(result), 96)
        self.assertEqual(len(ports), 96)
        self.assertTrue(all(p.closed for p in ports.values()))

    def test_mocked_last_method_failure_prevents_all_query_workers(self):
        """Pure sequencing control; real admission refusal/positive path is separately tested."""
        keys = required_case_keys()
        selected = invented_reference_selection()
        cases = {k: {"receipt": {"invented": list(k)}, "expected_context": {"key": list(k)},
                     "worker_request": {"profile": "canonical", "context_key": list(k),
                                        "reference_selection": {"sha256": selected.digest}}} for k in keys}
        manifest = [{"context_key": list(k), "expected_context": cases[k]["expected_context"],
                     "request": cases[k]["worker_request"], "receipt_digest": object_digest(cases[k]["receipt"])} for k in keys]
        count = []
        def admission(receipt, current, registry, plan):
            count.append(receipt)
            if len(count) == 160:
                raise Refusal("invented last-path method failure")
            return {"receipt_sha256": object_digest(receipt), "bindings_sha256": object_digest(current)}
        def forbidden(*args):
            self.fail("No query worker can run when one method is invalid")
        with mock.patch("study.admit_full_run"), mock.patch("method.admission.validate_admission", side_effect=admission):
            with self.assertRaises(Refusal):
                predict_all_admitted(cases, lambda k: {"context": cases[k]["expected_context"]},
                    lambda k: SimpleNamespace(digest="0" * 64), None, selected, forbidden, {},
                    {"prediction_case_manifest": object_digest(manifest),
                     "reference_selection_sha256": selected.digest}, frozenset(), budget(prediction_cases=160))
        self.assertEqual(len(count), 160)

    def test_worker_cli_with_explicitly_invented_registry_and_values(self):
        """Natural-zero tiny worker path; never canonical/runtime qualification."""
        from method.test_method import MethodControls
        from method.admission import QUALIFICATIONS
        helper = MethodControls()
        helper.setUp()
        receipt, bindings = helper._fixture_receipt()
        with tempfile.TemporaryDirectory(prefix="neural053-invented-worker-") as directory:
            root = Path(directory)
            resources = budget(source_read=2 * 1024 * 1024, artifact_write=512 * 1024)
            query_pin = write_array_fresh(root / 'invented_query.npy', helper.x, resources)
            bindings["artifacts"]["query_artifact"] = {k: query_pin[k] for k in ("bytes", "sha256")}
            descriptor = {"schema": "neural053_query_support_v2", "case_id": "invented-worker-case",
                          "classes": [1, 2, 3], "query_ids": [f"invented-worker-row-{i}" for i in range(5)]}
            descriptor_pin = write_json_fresh(root / 'invented_query_descriptor.json', descriptor, resources)
            bindings["artifacts"]["query_descriptor"] = {k: descriptor_pin[k] for k in ("bytes", "sha256")}
            receipt["bindings"] = copy.deepcopy(bindings)
            receipt["review"]["reviewed_bindings_sha256"] = object_digest(bindings)
            selected = invented_reference_selection()
            selection_pin = write_json_fresh(root / 'invented_reference_selection.json', selected.document, resources)
            key = required_case_keys()[0]
            # Other entries are visibly invented metadata; this checks the CLI
            # plumbing, not the real160-method proof or canonical data support.
            methods = [{"context_key": list(k), "receipt_sha256": "0" * 64,
                        "bindings_sha256": "0" * 64, "plan_sha256": "0" * 64}
                       for k in required_case_keys()]
            methods[0].update({"receipt_sha256": object_digest(receipt),
                               "bindings_sha256": object_digest(bindings), "plan_sha256": helper.plan.digest})
            whole = {"schema": "neural053_whole_method_gate_v1",
                     "reference_selection_sha256": selected.digest, "methods": methods}
            whole_pin = write_json_fresh(root / 'invented_whole_gate.json', whole, resources)
            registry = {"schema": "neural053_trusted_admission_registry_v1", "task_id": "NEURAL-053",
                        "profile": "invented_engineering", "approved_receipts": [object_digest(receipt)],
                        "approved_qualifications": sorted({bindings["artifacts"][x]["sha256"] for x in QUALIFICATIONS}
                                                          | {object_digest(whole)})}
            request = {"schema": "neural053_prediction_worker_v1", "profile": "invented_engineering",
                       "context_key": list(key), "query": query_pin, "whole_method_gate": whole_pin,
                       "reference_selection": selection_pin, "query_descriptor": descriptor_pin,
                       "registry": write_json_fresh(root / 'invented_registry.json', registry, resources),
                       "receipt": write_json_fresh(root / 'invented_receipt.json', receipt, resources),
                       "bindings": write_json_fresh(root / 'invented_bindings.json', bindings, resources),
                       "plan": write_json_fresh(root / 'invented_plan.json', helper.doc, resources),
                       "output_path": str(root / 'invented_probabilities.npy'),
                       "output_manifest_path": str(root / 'invented_output.json')}
            request_pin = write_json_fresh(root / 'invented_request.json', request, resources)
            completed = subprocess.run([sys.executable, '-I', '-B', str(Path(__file__).with_name('prediction_worker.py')),
                '--request', request_pin['path'], '--request-bytes', str(request_pin['bytes']),
                '--request-sha256', request_pin['sha256'], '--origin-monotonic', str(resources.origin_monotonic),
                '--deadline-monotonic', str(resources.deadline_monotonic), '--source-read-cap', str(2 * 1024 * 1024),
                '--artifact-write-cap', str(512 * 1024)], capture_output=True, text=True, timeout=10)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            summary = json.loads(completed.stdout)
            self.assertEqual(summary['profile'], 'invented_engineering')
            self.assertFalse(summary['scientific_qualification_conferred'])
            output = np.load(root / 'invented_probabilities.npy', allow_pickle=False)
            self.assertEqual(output.shape, (5, 3))
            probability_check(output, 5, 3)
            manifest = json.loads((root / 'invented_output.json').read_text())
            self.assertEqual(manifest['reference_selection_digest'], selected.digest)
            self.assertEqual(manifest['query_descriptor_digest'], object_digest(descriptor))
            request['profile'] = 'canonical'
            with mock.patch('prediction_worker.read_array_exact') as loader:
                with self.assertRaises(ValueError):
                    worker_run(request, resources)
                loader.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
