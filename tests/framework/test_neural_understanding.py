"""Synthetic binding controls; these tests do not evaluate neural data or models."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("neural_understanding_tests", ROOT / "src/neurobench/neural_understanding.py")
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


def put(root, path, value):
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(value if type(value) is bytes else (json.dumps(value, indent=2) + "\n").encode())


def digest(body):
    return hashlib.sha256(body).hexdigest()


def contract(task_id, original, source):
    home = "benchmarks/neural/" + task_id
    return {
        "schema_version": engine.VERSION, "task_id": task_id, "title": "Synthetic observation task",
        "objective": engine.OBJECTIVE, "disposition": "partial_delivery",
        "disposition_reason": "Synthetic scorer source with no scientific evaluation.",
        "scientific_target": {"question": "Can observed signal classify an independently recorded event?",
            "target_kind": "observation_decoding", "known_answer": "Recorded binary event class",
            "answer_origin": "Independent fixture event file", "case_unit": "One complete epoch",
            "independent_unit": "Participant", "inference_scope": "Association within fixture epoch observations",
            "exclusions": ["No human or model performance is measured."]},
        "observation_contract": {"inputs": ["Fixed epoch amplitude in microvolts"],
            "forbidden_inputs": ["Event class and event code"], "case_identity": "Synthetic epoch ID",
            "split": "Entire participants remain in one partition", "coverage": "Synthetic binding only"},
        "evaluation": {"primary": {"name": "Balanced accuracy", "direction": "higher",
                "aggregation": "Participant macro average", "rationale": "Avoid dominant-class accuracy"},
            "secondary": ["Log loss"], "comparators": [{"name": "Class prior", "inputs": "Training labels",
                "procedure": "Freeze training class frequencies before query access"}],
            "nuisance_controls": ["Event-code removal"], "uncertainty": "Participant bootstrap",
            "failure_policy": "Retain all cases; reject invalid probabilities"},
        "implementation": {"reviewed_paths": [home + "/task.json", home + "/scorer.py"],
            "scorer_target": "Event labels", "target_fidelity": "scoped_target",
            "delivered_scope": "Synthetic source only", "missing": ["Independent scientific evaluation"],
            "execution_evidence": "No model trials"},
        "access_modes": {mode: {"status": "source_available" if mode == "frozen_program" else "not_delivered",
                "representation": "Frozen numeric epoch source" if mode == "frozen_program" else "No delivered transport",
                "boundary": "No event labels enter query", "evidence_ids": ["scorer"] if mode == "frozen_program" else [],
                "missing": ["Execution qualification"]} for mode in engine.MODES},
        "evidence": [{"id": "original", "kind": "local_review", "path": home + "/task.json",
                "sha256": digest(original), "supports": "Original registered scientific question"},
            {"id": "scorer", "kind": "local_source", "path": home + "/scorer.py",
                "sha256": digest(source), "supports": "Synthetic numeric scorer source"},
            {"id": "paper", "kind": "primary_source", "url": "https://example.org/fixture-paper",
                "locator": "Synthetic source fixture", "supports": "Invented task only for binding tests"}],
        "empirical_claims": {"new_model_trials": 0, "new_human_results": 0,
            "scientific_qualification": "not_established_by_this_revision", "historical_evidence": "No model results",
            "excluded_claims": ["No readiness or scientific-result inference"]},
        "revision": {"date": "2026-11-16", "summary": ["Add synthetic scoped target"],
            "source_review": "Inspected synthetic source bytes"}}


class UnderstandingBindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.task_id = "NEURAL-TEST-001"
        self.home = "benchmarks/neural/" + self.task_id
        self.original = b'{ "candidate_id": "HOLD-ALIAS-001", "title": "Original title", "status": "draft", "evaluation": {} }\n'
        self.source = b"# Synthetic evaluator fixture; never executed.\n"
        put(self.root, self.home + "/task.json", self.original)
        put(self.root, self.home + "/scorer.py", self.source)
        self.row = {"id": self.task_id, "track": "neural", "specification_id": "HOLD-ALIAS-001",
            "specification_alias": True, "task_directory": self.home,
            "specification": {"path": self.home + "/task.json", "bytes": len(self.original), "sha256": digest(self.original)},
            "original_specification": {"path": "historical-source/task.json", "bytes": len(self.original), "sha256": digest(self.original)}}
        self.registry = {"source_counts": {"neural": 1}, "tasks": [self.row]}
        put(self.root, "benchmarks/registry.json", self.registry)
        self.contract = contract(self.task_id, self.original, self.source)
        put(self.root, self.home + "/" + engine.CONTRACT, self.contract)

    def apply(self):
        outputs = engine.build_outputs(self.root)
        for path, body in outputs.items():
            put(self.root, path, body)
        return outputs

    def test_authentic_history_alias_and_idempotence(self):
        outputs = self.apply()
        self.assertEqual(self.original, (self.root / self.home / engine.HISTORY).read_bytes())
        current = json.loads((self.root / self.home / "task.json").read_bytes())
        self.assertEqual(current["candidate_id"], "HOLD-ALIAS-001")
        self.assertEqual(current["id"], "HOLD-ALIAS-001")
        self.assertEqual(current["track"], "neural")
        self.assertEqual(current["status"], "specification_only")
        self.assertEqual(current["scientific_question"], self.contract["scientific_target"]["question"])
        self.assertEqual(engine.validate_neural_understanding(self.root), [])
        loaded = engine.load_neural_understanding(self.root, self.task_id)
        self.assertEqual(loaded["evidence"][0]["path"], self.home + "/" + engine.HISTORY)
        self.assertEqual(engine.build_outputs(self.root), outputs)
        self.assertEqual(engine.summary(loaded)["scientific_qualification"], "not_established_by_this_revision")

    def test_missing_registration_and_extra_contract(self):
        self.apply()
        put(self.root, "benchmarks/neural/NEURAL-UNREGISTERED/" + engine.CONTRACT, self.contract)
        self.assertTrue(any("Unregistered" in value for value in engine.validate_neural_understanding(self.root)))
        with self.assertRaisesRegex(ValueError, "Unregistered"):
            engine.build_outputs(self.root)

    def test_missing_registered_contract(self):
        self.apply()
        (self.root / self.home / engine.CONTRACT).unlink()
        errors = engine.validate_neural_understanding(self.root)
        self.assertTrue(any("Missing neural-understanding contract" in value for value in errors))

    def test_source_tampering(self):
        self.apply()
        put(self.root, self.home + "/scorer.py", self.source + b"# changed\n")
        with self.assertRaisesRegex(ValueError, "Evidence SHA-256 mismatch"):
            engine.load_neural_understanding(self.root, self.task_id)
        with self.assertRaisesRegex(ValueError, "Evidence SHA-256 mismatch"):
            engine.build_outputs(self.root)

    def test_stale_binding_and_intentional_contract_update(self):
        self.apply()
        path = self.root / self.home / engine.CONTRACT
        changed = json.loads(path.read_bytes())
        changed["revision"]["summary"].append("Intentional source-review correction")
        put(self.root, self.home + "/" + engine.CONTRACT, changed)
        with self.assertRaisesRegex(ValueError, "Stale or invalid"):
            engine.load_neural_understanding(self.root, self.task_id)
        self.apply()
        self.assertEqual(engine.validate_neural_understanding(self.root), [])

    def test_missing_history_after_revision(self):
        self.apply()
        (self.root / self.home / engine.HISTORY).unlink()
        with self.assertRaisesRegex(ValueError, "missing historical"):
            engine.build_outputs(self.root)

    def test_history_tampering_cannot_be_accepted_by_rebinding(self):
        self.apply()
        put(self.root, self.home + "/" + engine.HISTORY, self.original + b"\n")
        with self.assertRaisesRegex(ValueError, "Historical bytes differ"):
            engine.build_outputs(self.root)

    def test_initial_task_tampering(self):
        put(self.root, self.home + "/task.json", self.original + b"\n")
        with self.assertRaisesRegex(ValueError, "Historical bytes differ"):
            engine.build_outputs(self.root)

    def test_substituted_contract_id(self):
        self.contract["task_id"] = "NEURAL-SIBLING"
        put(self.root, self.home + "/" + engine.CONTRACT, self.contract)
        with self.assertRaisesRegex(ValueError, "does not match registration"):
            engine.build_outputs(self.root)

    def test_mode_claim_requires_source_and_known_evidence(self):
        for evidence_ids in (["absent"], ["paper"], ["original"], []):
            candidate = copy.deepcopy(self.contract)
            candidate["access_modes"]["frozen_program"]["evidence_ids"] = evidence_ids
            self.assertTrue(engine.validate_contract(candidate))
        candidate = copy.deepcopy(self.contract)
        del candidate["access_modes"]["typed_viewer"]
        self.assertTrue(engine.validate_contract(candidate))

    def test_duplicate_json_keys(self):
        body = (self.root / self.home / engine.CONTRACT).read_bytes()
        put(self.root, self.home + "/" + engine.CONTRACT, body.replace(b'"title":', b'"title":"extra", "title":', 1))
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            engine.build_outputs(self.root)

    def test_no_bool_counts_or_readiness_shortcuts(self):
        candidate = copy.deepcopy(self.contract)
        candidate["empirical_claims"]["new_model_trials"] = False
        self.assertTrue(engine.validate_contract(candidate))
        candidate = copy.deepcopy(self.contract)
        candidate["scientifically_qualified"] = True
        self.assertTrue(engine.validate_contract(candidate))
        candidate = copy.deepcopy(self.contract)
        candidate["evidence"].append({**candidate["evidence"][0], "supports": "Duplicate ID"})
        self.assertTrue(engine.validate_contract(candidate))

    def test_path_containment_symlinks_and_unpinned_review(self):
        for path in ("../outside", "/absolute", "benchmarks//nested", "benchmarks/./nested", "bad\\path", ".git/config", "nested/.GIT/config", "bad\npath"):
            candidate = copy.deepcopy(self.contract)
            candidate["evidence"][1]["path"] = path
            self.assertTrue(engine.validate_contract(candidate))
        candidate = copy.deepcopy(self.contract)
        candidate["implementation"]["reviewed_paths"].append("unpinned.py")
        self.assertTrue(engine.validate_contract(candidate))
        source_path = self.root / self.home / "scorer.py"
        source_path.unlink()
        put(self.root, "outside.py", self.source)
        source_path.symlink_to(self.root / "outside.py")
        with self.assertRaisesRegex(ValueError, "Symlink"):
            engine.build_outputs(self.root)

    def test_original_reference_rewrite_requires_original_hash(self):
        self.contract["evidence"][0]["sha256"] = "0" * 64
        put(self.root, self.home + "/" + engine.CONTRACT, self.contract)
        with self.assertRaisesRegex(ValueError, "does not pin the original"):
            engine.build_outputs(self.root)

    def test_current_projection_tampering(self):
        self.apply()
        path = self.root / self.home / "task.json"
        current = json.loads(path.read_bytes())
        current["primary_outputs"] = ["Substituted target not in bound contract"]
        put(self.root, self.home + "/task.json", current)
        with self.assertRaisesRegex(ValueError, "differs from its bound contract"):
            engine.load_neural_understanding(self.root, self.task_id)

    def test_dosei_native_successor_preserves_historical_projection(self):
        home = ROOT / "benchmarks/neural/clinical-dosei-responsiveness"
        original_body = (home / engine.HISTORY).read_bytes()
        original = json.loads(original_body)
        saved = copy.deepcopy(original)
        prior = home / "docs/understanding-pre-source-condition-v2"
        prior_contract_body = (prior / engine.CONTRACT).read_bytes()
        old_projection = engine._current(original, json.loads(prior_contract_body),
            engine._binding(prior_contract_body, original_body), "clinical-dosei-responsiveness")
        self.assertEqual(engine._bytes(old_projection), (prior / "task.json").read_bytes())
        contract_body = (home / engine.CONTRACT).read_bytes()
        current_contract = json.loads(contract_body)
        projected = engine._current(original, current_contract,
            engine._binding(contract_body, original_body), "clinical-dosei-responsiveness")
        for value in (projected["participant_inputs"], projected["complete_scope"]["input"],
                      projected["complete_scope"]["complete_compact_representation"],
                      projected["machine_output"]["coverage"],
                      projected["resources_and_remaining_gates"]["planning"]):
            self.assertNotIn("7,500 values", value)
            self.assertNotIn("7,328", value)
            self.assertNotIn("1,129", value)
        self.assertIn("relative native timestamps", projected["participant_inputs"])
        self.assertIn("not scoring denominators", projected["machine_output"]["coverage"])
        self.assertEqual(projected["provenance"], original["provenance"])
        self.assertEqual(projected["admission"], old_projection["admission"])
        self.assertEqual(original, saved)
        # The exact condition evidence must not alter another task's inherited fields.
        other_contract = copy.deepcopy(current_contract)
        other_contract["task_id"] = "NEURAL-UNRELATED"
        unrelated = engine._current(original, other_contract, {}, "NEURAL-UNRELATED")
        self.assertEqual(unrelated["participant_inputs"], original["participant_inputs"])

    def test_calcium_source_successor_keeps_original_holds_and_exposure_unknown(self):
        home = ROOT / "benchmarks/neural/NEURAL-025"
        original_body = (home / engine.HISTORY).read_bytes()
        original = json.loads(original_body)
        saved = copy.deepcopy(original)
        prior = home / "docs/understanding-pre-source-condition-v2"
        old_contract_body = (prior / engine.CONTRACT).read_bytes()
        old_contract = json.loads(old_contract_body)
        old_projection = engine._current(original, old_contract,
            engine._binding(old_contract_body, original_body), "NEURAL-025")
        self.assertEqual(engine._bytes(old_projection), (prior / "task.json").read_bytes())
        contract_body = (home / engine.CONTRACT).read_bytes()
        contract = json.loads(contract_body)
        projected = engine._current(original, contract,
            engine._binding(contract_body, original_body), "NEURAL-025")
        self.assertEqual(len(projected["holds"]), len(old_projection["holds"]))
        for index, hold in enumerate(old_projection["holds"]):
            self.assertEqual(projected["holds"][index]["id"], hold["id"])
            if index not in (0, 1, 7):
                self.assertEqual(projected["holds"][index], hold)
        self.assertIn("Historical author decoder PCA precedes CV", projected["holds"][1]["requirement"])
        self.assertIn("authentic inputs", projected["holds"][7]["requirement"])
        self.assertEqual(projected["reference"], old_projection["reference"])
        self.assertFalse(projected["reference"]["reference_executed_for_this_contract"])
        self.assertEqual(projected["admission"], old_projection["admission"])
        self.assertEqual(contract["scientific_target"], old_contract["scientific_target"])
        self.assertEqual(contract["evaluation"]["primary"], old_contract["evaluation"]["primary"])
        self.assertIn("Actual preprocessing/model input and fitted-trial exposure are separately unknown",
                      projected["allowed_inputs"]["inputs"][2])
        self.assertEqual(original, saved)
        unrelated = copy.deepcopy(contract)
        unrelated["task_id"] = "NEURAL-UNRELATED"
        self.assertEqual(engine._current(original, unrelated, {}, "NEURAL-UNRELATED")["holds"], original["holds"])

    def test_neural077_waveform_pair_successor_preserves_history_and_requires_exact_receipt(self):
        home = ROOT / "benchmarks/neural/NEURAL-077"
        original_body = (home / engine.HISTORY).read_bytes()
        original = json.loads(original_body)
        saved = copy.deepcopy(original)
        prior = home / "docs/understanding-pre-waveform-pair-v1"
        old_body = (prior / engine.CONTRACT).read_bytes()
        old_contract = json.loads(old_body)
        old = engine._current(original, old_contract,
            engine._binding(old_body, original_body), "NEURAL-077")
        self.assertEqual(engine._bytes(old), (prior / "task.json").read_bytes())
        body = (home / engine.CONTRACT).read_bytes()
        contract = json.loads(body)
        current = engine._current(original, contract,
            engine._binding(body, original_body), "NEURAL-077")
        self.assertEqual(engine._bytes(current), (home / "task.json").read_bytes())
        self.assertIn("accepted complete local adapter/transport", current["holds"][6]["requirement"])
        self.assertIn("completed finite local numerical pair", current["next_implementation_action"][0])
        self.assertEqual(current["admission"], old["admission"])
        self.assertEqual(current["status"], "specification_only")
        self.assertEqual(len(current["holds"]), len(old["holds"]))
        for index, hold in enumerate(old["holds"]):
            if index != 6:
                self.assertEqual(current["holds"][index], hold)
        self.assertEqual(current["next_implementation_action"][1:], old["next_implementation_action"][1:])
        self.assertEqual(contract["scientific_target"], old_contract["scientific_target"])
        self.assertEqual(contract["evaluation"]["primary"], old_contract["evaluation"]["primary"])
        self.assertEqual(contract["access_modes"]["typed_viewer"], old_contract["access_modes"]["typed_viewer"])
        for mode in engine.MODES:
            self.assertEqual(contract["access_modes"][mode]["status"], old_contract["access_modes"][mode]["status"])
        # The versioned snapshot and every unrelated prefix row stay immutable.
        # Only the maintained lifecycle source/test identities and the explicit
        # historical-proof limitation have declared current successors.
        self.assertEqual(digest(old_body),
                         "1c3a9e3ba4b6a88e7e79563aab50e54b344ae9a01693897cb22afe66e513f376")
        self.assertEqual(len(old_contract["evidence"]), 15)
        expected_prefix = copy.deepcopy(old_contract["evidence"])
        lifecycle_updates = {
            11: ("visual-transport",
                 "Current per-query framed PNG/action transport with unreaped child ownership. "
                 "Earlier execution receipts retain their original source identity and do not "
                 "qualify this lifecycle revision."),
            14: ("transport-controls", None),
        }
        for index, (evidence_id, supports) in lifecycle_updates.items():
            with self.subTest(lifecycle_evidence=evidence_id):
                expected = expected_prefix[index]
                historical_sha = expected["sha256"]
                self.assertEqual(expected["id"], evidence_id)
                self.assertEqual(expected["kind"], "local_source")
                source_body = (ROOT / expected["path"]).read_bytes()
                expected["sha256"] = digest(source_body)
                self.assertNotEqual(expected["sha256"], historical_sha)
                if supports is not None:
                    expected["supports"] = supports
                # Authenticate the real current file through the maintained
                # loader, then reject stale pins and altered source bytes.
                selected = {"evidence": [expected]}
                self.assertEqual(engine._source_errors(ROOT, selected), [])
                stale = copy.deepcopy(expected)
                stale["sha256"] = historical_sha
                error = ["Evidence SHA-256 mismatch: " + expected["path"]]
                self.assertEqual(engine._source_errors(ROOT, {"evidence": [stale]}), error)
                tampered = {expected["path"]: source_body + b"\n# generated source mutation\n"}
                self.assertEqual(engine._source_errors(ROOT, selected, tampered), error)
        self.assertEqual(contract["evidence"][:len(expected_prefix)], expected_prefix)
        self.assertEqual(contract["empirical_claims"]["scientific_qualification"],
                         "not_established_by_this_revision")
        for field, wrong in (("id", "unselected-control"), ("kind", "local_source"),
                             ("path", "benchmarks/neural/NEURAL-077/other.json"), ("sha256", "0" * 64)):
            changed = copy.deepcopy(contract)
            receipt = next(item for item in changed["evidence"] if item["id"] == "waveform-pair-control")
            receipt[field] = wrong
            unchanged = engine._current(original, changed, {}, "NEURAL-077")
            self.assertEqual(unchanged["holds"], original["holds"])
            self.assertEqual(unchanged["next_implementation_action"], original["next_implementation_action"])
        unrelated = copy.deepcopy(contract)
        unrelated["task_id"] = "NEURAL-UNRELATED"
        unchanged = engine._current(original, unrelated, {}, "NEURAL-UNRELATED")
        self.assertEqual(unchanged["holds"], original["holds"])
        self.assertEqual(unchanged["next_implementation_action"], original["next_implementation_action"])
        self.assertEqual(original, saved)

    def test_neural095_selected_routes_preserve_history_and_require_exact_evidence(self):
        home = ROOT / "benchmarks/neural/NEURAL-095"
        original_body = (home / engine.HISTORY).read_bytes()
        original = json.loads(original_body)
        saved = copy.deepcopy(original)
        prior = home / "docs/understanding-pre-participant-routes-v2"
        old_body = (prior / engine.CONTRACT).read_bytes()
        old_contract = json.loads(old_body)
        old = engine._current(original, old_contract,
            engine._binding(old_body, original_body), "NEURAL-095")
        self.assertEqual(engine._bytes(old), (prior / "task.json").read_bytes())
        body = (home / engine.CONTRACT).read_bytes()
        contract = json.loads(body)
        current = engine._current(original, contract,
            engine._binding(body, original_body), "NEURAL-095")
        self.assertEqual(engine._bytes(current), (home / "task.json").read_bytes())
        self.assertEqual(current["next_implementation_action"], contract["implementation"]["missing"])
        self.assertFalse(current["operator_route"]["execution_authority"])
        self.assertEqual(current["operator_route"]["selection"], "explicit_opt_in_source_route_only")
        self.assertEqual(current["admission"], old["admission"])
        self.assertEqual(contract["scientific_target"], old_contract["scientific_target"])
        self.assertEqual(contract["evaluation"], old_contract["evaluation"])
        for field, wrong in (("id", "unselected-route"), ("kind", "local_review"),
                             ("path", "benchmarks/neural/NEURAL-095/other.json"), ("sha256", "0" * 64)):
            changed = copy.deepcopy(contract)
            route = next(row for row in changed["evidence"] if row["id"] == "dmfc095-current-route-v1")
            route[field] = wrong
            refused = engine._current(original, changed, {}, "NEURAL-095")
            self.assertNotIn("operator_route", refused)
            self.assertEqual(refused["next_implementation_action"], original["next_implementation_action"])
        unrelated = copy.deepcopy(contract)
        unrelated["task_id"] = "NEURAL-UNRELATED"
        self.assertNotIn("operator_route", engine._current(original, unrelated, {}, "NEURAL-UNRELATED"))
        self.assertEqual(original, saved)

    def test_current_admission_cannot_be_promoted(self):
        self.apply()
        path = self.root / self.home / "task.json"
        current = json.loads(path.read_bytes())
        self.assertFalse(current["admission"]["runnable"])
        self.assertFalse(current["admission"]["research_qualified"])
        self.assertFalse(current["admission"]["submission_ready"])
        for flag in ("runnable", "research_qualified", "submission_ready"):
            promoted = copy.deepcopy(current)
            promoted["admission"][flag] = True
            put(self.root, self.home + "/task.json", promoted)
            with self.assertRaisesRegex(ValueError, "differs from its bound contract"):
                engine.load_neural_understanding(self.root, self.task_id)
        self.apply()
        self.assertEqual(engine.validate_neural_understanding(self.root), [])

    def test_malformed_metadata_yields_errors(self):
        candidate = copy.deepcopy(self.contract)
        candidate["evidence"][2]["url"] = "https://[invalid"
        self.assertTrue(engine.validate_contract(candidate))
        candidate = copy.deepcopy(self.contract)
        candidate["evidence"][0]["sha256"] += "\n"
        self.assertTrue(engine.validate_contract(candidate))
        for changes in ({"source_counts": []}, {"tasks": [{**self.row, "specification": []}]}):
            malformed = {**self.registry, **changes}
            put(self.root, "benchmarks/registry.json", malformed)
            self.assertTrue(engine.validate_neural_understanding(self.root))
            with self.assertRaises(ValueError):
                engine.build_outputs(self.root)
        put(self.root, "benchmarks/registry.json", self.registry)
        put(self.root, self.home + "/task.json", [])
        with self.assertRaisesRegex(ValueError, "must be an object"):
            engine.build_outputs(self.root)

    def test_registry_count_cannot_drop_a_task_silently(self):
        self.apply()
        self.registry["tasks"] = []
        put(self.root, "benchmarks/registry.json", self.registry)
        self.assertTrue(any("count disagrees" in value for value in engine.validate_neural_understanding(self.root)))


if __name__ == "__main__":
    unittest.main()
