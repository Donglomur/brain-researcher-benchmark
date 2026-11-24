"""Generated full-count handoff barriers; no authentic data or reference fits."""
import builtins
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import types
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
IMPL = HERE.parent


def load(name, path, dependencies=None):
    module = types.ModuleType(name)
    module.__file__ = str(path)
    original_import = builtins.__import__
    def imports(key, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and dependencies and key in dependencies:
            return dependencies[key]
        return original_import(key, globals, locals, fromlist, level)
    module.__dict__["__builtins__"] = dict(vars(builtins), __import__=imports)
    exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
    return module


grade = load("_spinal_grade_test", HERE / "grade.py")
contract = load("_spinal_contract_test", IMPL / "current-condition-delivery-v1/contract.py")
collector = load("_spinal_collect_test", IMPL / "current-condition-delivery-v1/collect.py", {"contract": contract})
materials = load("_spinal_materials_test", IMPL / "current-condition-delivery-v1/materials.py")
transport = load("_spinal_transport_test", IMPL / "current-condition-delivery-v1/transport.py",
                 {"contract": contract, "materials": materials, "collect": collector})
reader = load("_spinal_reader_test", IMPL / "current-condition-evaluator-v1/artifact_io.py")
profile = load("_spinal_profile_test", HERE / "profile.py",
               {"source": types.SimpleNamespace(BANK_SHA=grade.BANK_SHA, IMAGE=grade.IMAGE, need=grade.need)})


def generated_scores(neurons):
    """Fictional evaluator receipt for paired-report controls, never paper data."""
    return {"condition_id": grade.CONDITION, "bank_manifest_sha256": grade.BANK_SHA,
            "operator_reference_manifest_sha256": "c" * 64,
            "coverage": {"source_neurons": 44, "eligible_recordings": 116},
            "metrics": {"per_neuron": {identity: {
                "total_bins": 80, "scored_bins": 16, "sampling_rate_hz": 30.0,
                "methods": {"candidate": {
                    "correlation": {"value": None, "status": "constant_prediction"},
                    "rate_diagnostics": {"normalized_l1": 2.0, "signed_bias": -0.2, "status": "defined"}}}}
                for identity in neurons}}}


class PairedAccessSummaryTests(unittest.TestCase):
    def setUp(self):
        self.neurons = {f"n{i:02d}": "glutamatergic" if i < 21 else "gabaergic" for i in range(44)}
        self.results = {arm: generated_scores(self.neurons) for arm in grade.ARMS}

    def candidate(self, arm, identity):
        return self.results[arm]["metrics"]["per_neuron"][identity]["methods"]["candidate"]

    def correlation(self, arm, identity, value):
        self.candidate(arm, identity)["correlation"] = {"value": value,
            "status": "defined" if value is not None else "constant_prediction"}

    def summary(self):
        return grade.paired_access_summary(self.results, self.neurons)

    def test_pair_before_aggregation_when_each_arm_has_different_undefined_neurons(self):
        a, b = grade.ARMS
        for arm, identity, value in [(a, "n00", .2), (b, "n00", .6),
                                      (b, "n01", .9), (a, "n02", .8)]:
            self.correlation(arm, identity, value)
        result = self.summary()
        summary = result["cohorts"]["glutamatergic"]["metrics"]["correlation"]
        self.assertEqual((summary["expected_neurons"], summary["defined_neurons"], summary["undefined_neurons"]), (21, 1, 20))
        self.assertAlmostEqual(summary["mean"], .4)
        self.assertNotAlmostEqual(summary["mean"], (.6 + .9) / 2 - (.2 + .8) / 2)
        self.assertEqual(summary["status_counts"], {"defined": 1, "paper_data_undefined": 1,
            "paper_data_author_code_undefined": 1, "both_undefined": 18})
        self.assertEqual(result["per_neuron"]["n01"]["metrics"]["correlation"]["operands"][a],
                         {"value": None, "status": "constant_prediction"})
        self.assertEqual(len(result["per_neuron"]), 44)
        self.assertEqual(result["cohorts"]["gabaergic"]["metrics"]["correlation"]["expected_neurons"], 23)

    def test_rate_diagnostics_remain_separate_and_signed_bias_has_no_win_direction(self):
        for identity in self.neurons:
            self.candidate(grade.ARMS[1], identity)["rate_diagnostics"].update(normalized_l1=1.0, signed_bias=.2)
        result = self.summary()
        values = result["cohorts"]["glutamatergic"]["metrics"]
        self.assertEqual(values["normalized_l1"]["mean"], -1.0)
        self.assertAlmostEqual(values["signed_bias"]["mean"], .4)
        self.assertEqual(result["metric_directions"]["signed_bias"], "signed_change_only_not_an_improvement_direction")
        self.assertFalse(result["scientific_improvement_established"])
        self.assertFalse(result["uncertainty_or_superiority_rule_defined"])

    def test_unchanged_metric_kernel_outputs_preserve_calibration_change_at_equal_correlation(self):
        metrics = load("_spinal_pair_metric_control", IMPL / "original-endpoint-metrics-v1/metrics.py")
        for arm, scale in zip(grade.ARMS, (2.0, 1.0)):
            observations = [{"neuron_id": identity, "target_hz": [0., 1., 2., 3.],
                "support": [True] * 4,
                "controls": {method: metrics.Prediction((0., 1., 2., 3.),
                    "hz" if method in metrics.RATE_METHODS else "arbitrary")
                    for method in metrics.SOURCE_CONTROLS},
                "candidate": metrics.Prediction(tuple(scale * value for value in (0., 1., 2., 3.)), "hz")}
                for identity in self.neurons]
            self.results[arm]["metrics"] = metrics.score_condition(expected_neurons=self.neurons,
                observations=observations, sampling_rate_hz=30.)
        result = self.summary()
        for cohort in ("glutamatergic", "gabaergic"):
            summary = result["cohorts"][cohort]["metrics"]
            self.assertEqual(summary["correlation"]["mean"], 0.0)
            self.assertEqual(summary["normalized_l1"]["mean"], -1.0)
            self.assertEqual(summary["signed_bias"]["mean"], -1.0)

    def test_constant_control_retains_all_undefined_correlations_and_finite_json(self):
        result = self.summary()
        for cohort, count in (("glutamatergic", 21), ("gabaergic", 23)):
            row = result["cohorts"][cohort]["metrics"]["correlation"]
            self.assertEqual(row["undefined_neurons"], count)
            self.assertIsNone(row["mean"])
            self.assertEqual(row["status_counts"], {"both_undefined": count})
        json.dumps(result, allow_nan=False)

    def test_nonrepresentable_diagnostic_delta_remains_an_explicit_undefined_pair(self):
        self.candidate(grade.ARMS[0], "n00")["rate_diagnostics"]["signed_bias"] = -1.7e308
        self.candidate(grade.ARMS[1], "n00")["rate_diagnostics"]["signed_bias"] = 1.7e308
        result = self.summary()
        row = result["per_neuron"]["n00"]["metrics"]["signed_bias"]
        self.assertIsNone(row["delta"])
        self.assertEqual(row["status"], "unrepresentable_delta")
        self.assertEqual(result["cohorts"]["glutamatergic"]["metrics"]["signed_bias"]["undefined_neurons"], 1)
        json.dumps(result, allow_nan=False)

    def test_neuron_order_cannot_change_pairing(self):
        self.correlation(grade.ARMS[1], "n01", .7)
        before = self.summary()
        for arm in grade.ARMS:
            rows = self.results[arm]["metrics"]["per_neuron"]
            self.results[arm]["metrics"]["per_neuron"] = dict(reversed(list(rows.items())))
        self.neurons = dict(reversed(list(self.neurons.items())))
        self.assertEqual(before, self.summary())

    def test_missing_neuron_changed_coverage_or_support_cannot_form_a_pair(self):
        original = deepcopy(self.results)
        mutations = [
            lambda r: r["metrics"]["per_neuron"].pop("n43"),
            lambda r: r["coverage"].update(eligible_recordings=115),
            lambda r: r.update(operator_reference_manifest_sha256="d" * 64),
            lambda r: r["metrics"]["per_neuron"]["n00"].update(scored_bins=15)]
        for index, mutate in enumerate(mutations):
            self.results = deepcopy(original)
            mutate(self.results[grade.ARMS[1]])
            with self.subTest(index=index), self.assertRaises(ValueError):
                self.summary()

    def test_inconsistent_metric_status_cannot_be_counted_as_defined(self):
        self.candidate(grade.ARMS[1], "n00")["correlation"] = {"value": .5, "status": "constant_prediction"}
        with self.assertRaisesRegex(ValueError, "definition status"):
            self.summary()


class Fixture:
    """Real original material/binding/capture functions on fictional 132 rows."""
    root = Path("/generated/spinal")
    bank_root = Path("/generated/bank")
    reference_root = Path("/generated/reference")

    def __init__(self):
        self.files = {}
        self.trace = []
        self.source_pin = {"bytes": 123, "sha256": "a" * 64}
        self.delivery_pin = {"bytes": 124, "sha256": "b" * 64}
        self.plan = {"schema": "spinal_current_completion_plan_v1", "scope": "fixed_one_hz_nonlearning_engineering_pair",
                     "image": grade.IMAGE, "bank_manifest_sha256": grade.BANK_SHA, "output_unit": "hz", "purpose": "reproduction",
                     "candidate_seconds": 20, "memory_bytes": 536870912, "bank": str(self.bank_root),
                     "assets": "/generated/assets", "output": str(self.root), "docker": "/generated/docker",
                     "docker_socket": "/generated/docker.sock", "campaign_seconds": 1800, "other_reserve_bytes": 0}
        neurons = {f"n{i:02d}": "glutamatergic" if i < 21 else "gabaergic" for i in range(44)}
        rows = []
        for index, (neuron, cohort) in enumerate(neurons.items()):
            for ordinal in range(3):
                row = {"neuron_id": neuron, "cohort": cohort, "recording_id": f"{neuron}/recording-{ordinal:03d}",
                       "source_recording_index_zero_based": ordinal}
                if index < 16 and ordinal == 2:
                    row.update(status="unavailable", reason="native_noise_exceeds_requested_noise")
                else:
                    row.update(status="prepared", output_samples=65,
                               operator_payload={"path": "unused", "bytes": 1, "sha256": "0" * 64})
                rows.append(row)
        metadata = {"condition": {"name": "current_source_recipe_single_realization_v1", "nominal_rate_hz": 30,
                      "requested_noise_level": 7, "target_sigma_seconds": .05, "context_window_bins": 64,
                      "historical_paper_realization": False}, "expected_neurons": neurons,
                    "recordings": rows, "source_recordings": 132}
        self.bank = types.SimpleNamespace(metadata=metadata, manifest_sha256=grade.BANK_SHA,
                                          eligible=[r for r in rows if r["status"] == "prepared"])
        self.roster = {"bank_manifest_sha256": grade.BANK_SHA, "expected_neurons": neurons, "records": deepcopy(rows)}
        campaign = self.root / "campaign"
        plan_pin = self.put(self.root / "PLAN.json", self.plan)
        self.runtime = profile.runtime(self.plan, transport, self.source_pin, plan_pin, deadline=1900.0, now=100.2)
        self.put(self.root / "INTENT.json", {"schema": "spinal_current_completion_intent_v1",
             "completion_source": self.source_pin, "delivery_source": self.delivery_pin, "plan": plan_pin,
             "started_monotonic": 100.0, "deadline_monotonic": 1900.0, "all_88_contexts_required": True,
             "automatic_retry": False, "engineering_control": True, "scientific_scoring": False})
        runtime_pin = self.put(campaign / "RUNTIME.json", self.runtime)
        self.put(campaign / "OPERATOR_CENSUS.json", self.roster)
        self.pair = {"schema": "spinal_current_frozen_pair_v1", "condition_id": grade.CONDITION, "arms": {}}
        for arm in grade.ARMS:
            cfg = contract.configuration(arm, "reproduction", "hz")
            program = b"# fictional metadata-only fixture, never executed\n"
            seal = {"schema": "spinal_current_program_seal_v1", "entrypoint": "program.py",
                    "files": [{"path": "program.py", **contract.pin(program)}], "configuration": cfg,
                    "configuration_pin": contract.pin(contract.encoded(cfg))}
            self.pair["arms"][arm] = {"seal": seal, "seal_pin": contract.pin(contract.encoded(seal))}
            self.files[campaign / "programs" / arm / "program.py"] = program
            self.put(campaign / "programs" / arm / "config.json", cfg)
        self.pair["pair_pin"] = contract.pin(contract.encoded(self.pair))
        self.put(campaign / "PAIR_SEAL.json", self.pair)
        arm_results = {}
        self.bundles = {}
        for arm in grade.ARMS:
            candidate_rows = []
            for held in neurons:
                directory = campaign / arm / "folds" / held
                selected = materials.select_fold(self.bank, held)
                manifest = materials._participant_manifest(selected, arm, "reproduction")
                inputs = {"FOLD.json": contract.pin(contract.encoded(manifest)),
                          "training.npz": contract.pin((held + "training").encode()),
                          "query.npz": contract.pin((held + "query").encode()),
                          "paper.xml": contract.pin(b"same generated paper")}
                if arm == grade.ARMS[1]:
                    inputs["author-code/fixed.py"] = contract.pin(b"same generated author source")
                binding = {"schema": "spinal_current_program_binding_v1", "condition_id": grade.CONDITION,
                           "held_neuron": held, "arm": arm, "purpose": "reproduction", "output_unit": "hz",
                           "pair_pin": self.pair["pair_pin"], "program_seal": self.pair["arms"][arm]["seal_pin"],
                           "fold_manifest": inputs["FOLD.json"], "input_files": dict(sorted(inputs.items())),
                           "query_records": manifest["query_records"],
                           "training_policy": "eligible_same_cohort_except_entire_held_neuron",
                           "fresh_context_required": True}
                fold = {"schema": "spinal_current_fold_prediction_v1", "condition_id": grade.CONDITION,
                        "held_neuron": held, "arm": arm, "purpose": "reproduction",
                        "program_seal_sha256": binding["program_seal"]["sha256"],
                        "binding_sha256": contract.pin(contract.encoded(binding))["sha256"], "unit": "hz",
                        "query_recording_ids": [r["recording_id"] for r in manifest["query_records"]]}
                fold_pin = self.put(directory / "captured/fold.json", fold)
                buf = io.BytesIO(); np.save(buf, np.ones(sum(r["samples"] for r in manifest["query_records"])), allow_pickle=False)
                self.files[directory / "captured/predictions.npy"] = buf.getvalue()
                prediction_pin = contract.pin(buf.getvalue())
                lifecycle = {"schema": "cascade44_fold_lifecycle_v1", "status": "captured", "all_resources_closed": True,
                             "cli_reaped": True, "candidate_closed_before_capture": True,
                             "natural_exit": {"Status": "exited", "Running": False, "Dead": False,
                                              "Pid": 0, "ExitCode": 0, "OOMKilled": False},
                             "closures": [{"kind": kind, "closed": True} for kind in ("container", "container", "volume")],
                             "namespace": arm + ":" + held, "program_seal": binding["program_seal"],
                             "source_manifest": self.delivery_pin, "runtime_contract": runtime_pin,
                             "image": grade.IMAGE, "candidate_seconds": 20, "memory_bytes": 536870912,
                             "candidate_started": True, "private_scoring_called": False, "public_post_pin": inputs,
                             "outputs": [{"path": "fold.json", **fold_pin}, {"path": "predictions.npy", **prediction_pin}]}
                lifecycle_pin = self.put(directory / "LIFECYCLE.json", lifecycle)
                proof = {"held_neuron": held, "arm": arm, "binding": contract.pin(contract.encoded(binding)),
                         "input_files": inputs, "program_seal": binding["program_seal"], "lifecycle": lifecycle_pin,
                         "held_all_source_records_excluded": selected["held_source_excluded_ids"],
                         "query_recording_ids": fold["query_recording_ids"], "fresh_context_namespace": lifecycle["namespace"],
                         "candidate_closed_before_capture": True}
                self.put(directory / "FOLD_PROOF.json", proof)
                self.put(directory / "RETIRED.json", {"input_absent": True, "trusted_absent": True})
                for row in manifest["query_records"]:
                    payload = io.BytesIO(); np.savez(payload, candidate=np.ones(row["samples"]))
                    filename = f"prediction-{len(candidate_rows):03d}.npz"
                    self.files[campaign / arm / "candidate" / filename] = payload.getvalue()
                    candidate_rows.append({"recording_id": row["recording_id"], "payload": {"path": filename, **contract.pin(payload.getvalue())}})
            bundle = {"schema": "spinal_current_prediction_bundle_v1", "role": "candidate", "condition_id": grade.CONDITION,
                      "bank_manifest_sha256": grade.BANK_SHA, "methods": {"candidate": "hz"},
                      "recordings": candidate_rows, "provenance_note": "generated fixture"}
            pin = self.put(campaign / arm / "candidate/PREDICTIONS.json", bundle)
            self.bundles[arm] = types.SimpleNamespace(root=campaign / arm / "candidate", metadata=bundle,
                    by_id={r["recording_id"]: r["payload"] for r in candidate_rows}, manifest_sha256=pin["sha256"], role="candidate")
            arm_results[arm] = {"folds": 44, "eligible_recordings": 116, "program_seal": self.pair["arms"][arm]["seal_pin"],
                                "prediction_manifest": pin}
        done = {"schema": "spinal_current_transport_complete_v1", "condition_id": grade.CONDITION,
                "bank_manifest_sha256": grade.BANK_SHA, "pair_pin": self.pair["pair_pin"], "source_manifest": self.delivery_pin,
                "arms": arm_results, "source_recording_census": 132, "eligible_recordings": 116,
                "noise_exclusions": 16, "required_neurons": 44, "same_data_across_arms": True,
                "scientific_scoring_performed": False, "selected_fold_seconds": 88 * 440, "elapsed_seconds": 1.0}
        done_pin = self.put(campaign / "WORKER_COMPLETE.json", done)
        host = {"schema": "spinal_current_completion_host_exit_v1", "completion_source": self.source_pin,
                "delivery_source": self.delivery_pin, "campaign_relative_path": "campaign",
                "plan": contract.pin(self.files[self.root / "PLAN.json"]), "worker_complete": done_pin,
                "engineering_control": True, "scientific_scoring": False, "folds": 88, "eligible_recordings_per_arm": 116,
                "elapsed_seconds": 2.0,
                "candidate_manifests": {arm: value["prediction_manifest"] for arm, value in arm_results.items()},
                "worker_observation": {"natural_exit": True, "process_reaped": True, "streams_closed": True,
                    "exit_code": 0, "error_type": None, "kill_sent": False, "owned_host_group_absent": True}}
        stdout = contract.encoded({"complete": True, "completion_source": self.source_pin,
                     "delivery_source": self.delivery_pin, "plan": host["plan"], "folds": 88, "scientific_scoring": False})
        self.files[self.root / "worker.stdout"] = stdout
        self.files[self.root / "worker.stderr"] = b""
        host.update(stdout=contract.pin(stdout), stderr=contract.pin(b""))
        host["worker_observation"].update(stdout_bytes=len(stdout), stderr_bytes=0)
        self.put(self.root / "HOST_EXIT.json", host)
        fake_contract = types.SimpleNamespace(**{key: getattr(contract, key) for key in
             ("pin", "encoded", "configuration", "check_pair", "PROGRAM_LIMIT")}, capture=self.capture)
        current = types.SimpleNamespace(HERE=Path("/generated/evaluator"), ROSTER_SHA256="r" * 64,
              read_json=lambda *a, **k: (self.roster, "r" * 64), read_pinned=self.read_pinned,
              read_npz_bytes=reader.read_npz_bytes, load_bank=self.load_bank,
              load_predictions=self.load_predictions, _prediction_arrays=self.prediction_arrays, evaluate=self.evaluate)
        self.loaded = types.SimpleNamespace(contract=fake_contract, collector=collector, materials=materials,
              transport=types.SimpleNamespace(tree_pins=self.tree_pins, runtime_selection=transport.runtime_selection), current=current,
              source_pin=self.source_pin, delivery_source_pin=self.delivery_pin, profile=profile,
              manifest={"files": [{"path": "control/program.py", **contract.pin(program)}]})

    def put(self, path, value):
        raw = contract.encoded(value); self.files[path] = raw; return contract.pin(raw)

    def change(self, relative, mutate):
        path = self.root / relative; value = json.loads(self.files[path]); mutate(value); self.put(path, value)

    def capture(self, path, limit):
        raw = self.files[Path(path)]
        grade.need(len(raw) <= limit, "fixture obeys production byte cap")
        return raw

    def tree_pins(self, root, **unused):
        return {str(p.relative_to(root)): contract.pin(raw) for p, raw in self.files.items() if root in p.parents}

    def read_pinned(self, root, pin, **unused):
        raw = self.files[Path(root) / pin["path"]]
        grade.need(contract.pin(raw) == {k: pin[k] for k in ("bytes", "sha256")}, "fixture immutable public payload")
        return raw

    def load_bank(self, root):
        self.trace.append("bank_metadata"); return self.bank

    def load_predictions(self, root, bank, *, role, manifest_sha256):
        if role == "operator_reference":
            self.trace.append("reference_metadata")
            grade.need(root == self.reference_root and manifest_sha256 == "c" * 64, "operator reference freeze")
            return types.SimpleNamespace(manifest_sha256=manifest_sha256, role=role)
        arm = Path(root).parent.name
        raw = self.files[Path(root) / "PREDICTIONS.json"]
        grade.need(contract.pin(raw)["sha256"] == manifest_sha256, "complete candidate manifest identity")
        return self.bundles[arm]

    def prediction_arrays(self, bundle, row):
        self.trace.append("public_candidate_payload")
        raw = self.read_pinned(bundle.root, bundle.by_id[row["recording_id"]])
        return reader.read_npz_bytes(raw, {"candidate": ("numeric", row["output_samples"])})

    def evaluate(self, bank, reference, candidate):
        self.trace.append("protected_evaluate")
        grade.need(self.trace.count("public_candidate_payload") == 232, "both arms public validation must precede protected evaluation")
        result = generated_scores(bank.metadata["expected_neurons"])
        result.update(candidate_manifest_sha256=candidate.manifest_sha256, generated_only=True)
        return result

    def run(self, **extra):
        args = dict(host_exit_sha256=contract.pin(self.files[self.root / "HOST_EXIT.json"])["sha256"],
                    source_sha256=self.source_pin["sha256"], bank_root=self.bank_root,
                    reference_root=self.reference_root, reference_manifest_sha256="c" * 64, loaded=self.loaded)
        args.update(extra)
        with mock.patch.object(grade, "absent", side_effect=lambda path: path not in self.files):
            return grade.grade_pair(self.root, **args)


class ProtectedGradeTests(unittest.TestCase):
    def test_all_88_contexts_and_232_public_payloads_precede_both_scores(self):
        f = Fixture(); result = f.run()
        self.assertEqual(result["validated_recording_predictions"], 232)
        self.assertEqual(f.trace.count("protected_evaluate"), 2)
        self.assertEqual(f.trace.index("reference_metadata"), 233)
        self.assertFalse(result["paper_improvement_or_SOTA_established"])
        self.assertEqual(len(result["paired_access_summary"]["per_neuron"]), 44)
        self.assertEqual(result["paired_access_summary"]["cohorts"]["gabaergic"]["metrics"]["correlation"]["undefined_neurons"], 23)

    def test_failed_worker_never_opens_bank_or_reference(self):
        f = Fixture(); f.change("HOST_EXIT.json", lambda x: x["worker_observation"].update(exit_code=1))
        with self.assertRaisesRegex(ValueError, "natural zero"):
            f.run()
        self.assertEqual(f.trace, [])

    def test_partial_late_lifecycle_never_opens_bank(self):
        f = Fixture(); rel = "campaign/paper_data_author_code/folds/n43/LIFECYCLE.json"
        f.change(rel, lambda x: x.update(all_resources_closed=False))
        pin = contract.pin(f.files[f.root / rel])
        f.change("campaign/paper_data_author_code/folds/n43/FOLD_PROOF.json", lambda x: x.update(lifecycle=pin))
        with self.assertRaisesRegex(ValueError, "complete context closure"):
            f.run()
        self.assertEqual(f.trace, [])

    def test_retained_labelled_view_and_contradictory_failure_refused(self):
        for path in ("campaign/paper_data/folds/n00/input", "campaign/FAILED.json"):
            with self.subTest(path=path):
                f = Fixture(); f.files[f.root / path] = b"exists"
                with self.assertRaises(ValueError): f.run()
                self.assertEqual(f.trace, [])

    def test_wrong_arm_proof_or_reused_context_refused(self):
        f = Fixture(); f.change("campaign/paper_data_author_code/folds/n00/FOLD_PROOF.json", lambda x: x.update(arm="paper_data"))
        with self.assertRaisesRegex(ValueError, "whole held neuron"):
            f.run()
        self.assertEqual(f.trace, [])

    def test_wrong_retired_binding_refused_before_reference(self):
        f = Fixture(); f.change("campaign/paper_data_author_code/folds/n43/FOLD_PROOF.json",
                               lambda x: x["binding"].update(sha256="d" * 64))
        with self.assertRaisesRegex(ValueError, "retired binding"):
            f.run()
        self.assertNotIn("reference_metadata", f.trace)
        self.assertNotIn("protected_evaluate", f.trace)

    def test_changed_candidate_bytes_refused_before_reference(self):
        f = Fixture(); bundle = f.bundles[grade.ARMS[1]]; row = f.bank.eligible[-1]
        pin = bundle.by_id[row["recording_id"]]
        f.files[bundle.root / pin["path"]] += b"changed"
        with self.assertRaisesRegex(ValueError, "immutable public payload"):
            f.run()
        self.assertNotIn("reference_metadata", f.trace)

    def test_changed_candidate_values_refused_even_with_coherent_new_public_pin(self):
        f = Fixture(); bundle = f.bundles[grade.ARMS[1]]; row = f.bank.eligible[-1]
        pin = bundle.by_id[row["recording_id"]]; buf = io.BytesIO(); np.savez(buf, candidate=np.full(65, 2.0))
        f.files[bundle.root / pin["path"]] = buf.getvalue(); pin.update(contract.pin(buf.getvalue()))
        manifest_pin = f.put(bundle.root / "PREDICTIONS.json", bundle.metadata)
        bundle.manifest_sha256 = manifest_pin["sha256"]
        f.change("campaign/WORKER_COMPLETE.json", lambda x: x["arms"][grade.ARMS[1]].update(prediction_manifest=manifest_pin))
        done_pin = contract.pin(f.files[f.root / "campaign/WORKER_COMPLETE.json"])
        f.change("HOST_EXIT.json", lambda x: (x["candidate_manifests"].update({grade.ARMS[1]: manifest_pin}),
                                              x.update(worker_complete=done_pin)))
        with self.assertRaisesRegex(ValueError, "exactly match complete closed captures"):
            f.run()
        self.assertNotIn("reference_metadata", f.trace)

    def test_missing_or_swapped_reference_never_calls_evaluator(self):
        f = Fixture()
        with self.assertRaisesRegex(ValueError, "operator reference freeze"):
            f.run(reference_manifest_sha256="d" * 64)
        self.assertEqual(f.trace.count("public_candidate_payload"), 232)
        self.assertNotIn("protected_evaluate", f.trace)
        with self.assertRaisesRegex(ValueError, "mandatory"):
            Fixture().run(reference_manifest_sha256=None)

    def test_coherent_runtime_rebinding_cannot_change_aggregate_profile(self):
        changes = {"profile": "wrong", "completion_source": {"bytes": 1, "sha256": "0" * 64},
                   "plan": {"bytes": 1, "sha256": "0" * 64}, "selected_campaign_seconds": 1801,
                   "aggregate_deadline_monotonic": 1901.0, "worker_wall_seconds": 1738.8,
                   "partial_success_allowed": True}
        for field, bad in changes.items():
            with self.subTest(field=field):
                f = Fixture(); f.change("campaign/RUNTIME.json", lambda x: x.update({field: bad}))
                runtime_pin = contract.pin(f.files[f.root / "campaign/RUNTIME.json"])
                for arm in grade.ARMS:
                    for held in f.roster["expected_neurons"]:
                        rel = f"campaign/{arm}/folds/{held}/LIFECYCLE.json"
                        f.change(rel, lambda x: x.update(runtime_contract=runtime_pin))
                        lifecycle_pin = contract.pin(f.files[f.root / rel])
                        f.change(f"campaign/{arm}/folds/{held}/FOLD_PROOF.json", lambda x: x.update(lifecycle=lifecycle_pin))
                with self.assertRaisesRegex(ValueError, "aggregate profile"):
                    f.run()
                self.assertEqual(f.trace, [])

    def test_incomplete_stream_cleanup_never_opens_bank(self):
        for field, bad in (("cleanup_errors", {"pipe": "failed"}), ("output_overflow", True)):
            with self.subTest(field=field):
                f = Fixture(); f.change("HOST_EXIT.json", lambda x: x["worker_observation"].update({field: bad}))
                with self.assertRaisesRegex(ValueError, "natural zero"):
                    f.run()
                self.assertEqual(f.trace, [])

    def test_different_frozen_control_refused_before_bank(self):
        f = Fixture()
        f.change("campaign/PAIR_SEAL.json", lambda x: x["arms"][grade.ARMS[1]]["seal"]["files"][0].update(sha256="f" * 64))
        with self.assertRaisesRegex(ValueError, "source-frozen fixed control"):
            f.run()
        self.assertEqual(f.trace, [])


if __name__ == "__main__":
    unittest.main()
