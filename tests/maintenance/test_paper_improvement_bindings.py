"""Metadata-only binding checks: immutable provenance and fail-closed rewrites."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2] / "scripts/maintenance/bind_paper_improvement.py"
SPEC = importlib.util.spec_from_file_location("paper_improvement_binding", PATH)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def put(root, path, value):
    path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    body = value if isinstance(value, bytes) else builder.encode(value)
    path.write_bytes(body)
    return body


def load(root, path):
    return json.loads((root / path).read_bytes())


def contract(identifier):
    evidence = [{"id": "paper", "kind": "paper", "url": "https://example.invalid/paper",
                 "locator": "Synthetic test fixture table 1", "supports": "Fixture-only endpoint provenance"}]
    anchors = {field: {"status": "unresolved", "description": "Fixture " + field + " needs source verification",
                       "evidence_ids": []} for field in (
                           "target", "dataset", "cohort", "split", "inputs", "preprocessing", "metric", "aggregation")}
    baseline = {"status": "unresolved", "value": None, "description": "Fixture baseline is unknown", "evidence_ids": []}
    return {
        "schema_version": builder.VERSION, "task_id": identifier, "objective": builder.OBJECTIVE,
        "disposition": "source_unresolved", "disposition_reason": "Fixture endpoint provenance is unresolved",
        "source_paper": {"title": "Fixture source", "url": "https://example.invalid/paper"},
        "evidence": evidence, "same_task": anchors,
        "comparison": {"primary_metric": "Fixture held-animal error", "direction": "unresolved",
                       "published_baseline": copy.deepcopy(baseline), "reproduced_author_baseline": baseline,
                       "minimum_effect": {"status": "unresolved", "value": None, "rationale": "Unknown", "evidence_ids": []},
                       "uncertainty": {"status": "unresolved", "method": "Unknown", "independent_unit": "Unknown",
                                       "rationale": "Unknown", "evidence_ids": []},
                       "paper_win_requires": ["Verify the fixture held-animal error on the original animals and split."],
                       "current_sota": {"status": "not_claimed", "description": "No fixture SOTA claim", "evidence_ids": []}},
        "episode": {"improvement_loop": "Use fixture training/validation feedback", "candidate_freeze": "Freeze fixture candidate",
                    "final_evaluation": "Original fixture endpoint only", "access_budget": None,
                    "resource_budget": None, "baseline_policy": "Reconstruct source-author baseline before comparison"},
        "blocking_issues": ["Recover the fixture source metric"],
        "legacy": {"role": "calibration_only", "original_task": builder.HISTORY, "notes": "Fixture reconstruction is calibration"},
    }


def fixture(root, count=2):
    # The command dynamically imports the actual shared validator API. This
    # isolated source fixture lets maintenance tests run before/without installing
    # neurobench and exercises a late validation error without scientific data.
    put(root, "src/neurobench/paper_improvement.py", b'''def contract_validate(doc, task_id=None):
    errors = []
    if doc.get("task_id") != task_id:
        errors.append("task identity mismatch")
    if doc.get("disposition") not in ("improvement_ready", "design_ready", "source_unresolved", "ineligible"):
        errors.append("invalid disposition")
    if doc.get("invalid_fixture"):
        errors.append("fixture rejected by shared contract validator")
    return errors
''')
    rows, originals = [], {}
    for index in range(count):
        identifier = "PAPER-fixture-" + str(index + 1).zfill(3) if index != 1 else "paper-fixture-expansion"
        directory = "benchmarks/paper/" + identifier
        old = {"schema_version": 1, "id": identifier, "track": "paper", "title": "Source task " + str(index),
               "status": "specification_only", "source_id": "source-" + str(index),
               "paper_identity": {"url": "https://example.invalid/source"}, "paper": {"title": "Fixture source"},
               "input_assets": {"exact_asset_records": [{"name": "fixture.csv", "sha256": None}]},
               "data_contract": {"source_version": "fixture-v1"}, "participant_inputs": ["source fixture table"],
               "official_code": {"url": "https://example.invalid/code", "revision": "fixture"},
               "source_pins": [{"sha256": "f" * 64}], "source_rights": {"license": "fixture"},
               "provenance": {"source": "fixture-only"}, "resources": {"measured": None},
               "resource_estimate": {"hours": None}, "runtime_storage": {"bytes": None},
               "primary_outputs": ["Reproduce old coefficient"],
               "success_criteria": ["Numerical reconstruction is success"],
               "evaluation": {"success": "Numerical reconstruction is success"},
               "scoring": {"reward": "old reproduction success"}, "reproduction": {"pass": "old success"},
               "improvement": {"proposal": "different held-out population"},
               "readiness": {"runnable": True}, "admission": {"runnable": True, "research_qualified": True}}
        if index == 1:
            old.pop("schema_version")
            old.pop("status")
            old["schema"] = "expansion/v1"
            old["state"] = {"runnable": True, "stage": "historical source"}
        # Noncanonical whitespace is intentional: history must contain exact bytes.
        body = (json.dumps(old, indent=3, ensure_ascii=False) + "\r\n").encode()
        path = directory + "/task.json"
        put(root, path, body)
        originals[path] = body
        put(root, directory + "/improvement.v1.json", contract(identifier))
        runtime_path = directory + "/implementations/registered-runtime/manifest.json"
        runtime = put(root, runtime_path, b'{"historical_runtime":true}\n')
        put(root, directory + "/implementations/calibration/grader.py", b"# old grader stays byte-identical\n")
        rows.append({"id": identifier, "title": old["title"], "track": "paper", "task_directory": directory,
                     "specification_id": identifier, "specification_alias": False,
                     "registration_class": "expansion" if index == 1 else "canonical",
                     "declared_specification_status": old.get("status", old.get("state")),
                     "specification": builder.pin(path, body),
                     "original_specification": builder.pin("retired/source/" + identifier + ".json", body),
                     "source_specification": True, "registration_stage": "historical_registration",
                     "scientific_readiness": "unknown", "submission_readiness": "unknown",
                     "runtime_manifest": builder.pin(runtime_path, runtime), "runtime_package": str(Path(runtime_path).parent),
                     "runtime_manifest_status": "legacy_runner_verified"})
    rows.append({"id": "NEURAL-fixture", "track": "neural", "title": "Unchanged neural task"})
    implementations = [
        {"id": "paper-only", "owner_ids": [rows[0]["id"]], "related_task_ids": [], "role": "task_implementation",
         "scope_notes": "Original paper notes", "path": rows[0]["task_directory"] + "/implementations/calibration"},
        {"id": "shared", "owner_ids": [rows[0]["id"], "NEURAL-fixture"], "related_task_ids": [],
         "role": "shared_source_distribution", "scope_notes": "Keep original mixed owner notes",
         "evaluation_roles": {"NEURAL-fixture": "active_evaluation"}},
        {"id": "neural-only", "owner_ids": ["NEURAL-fixture"], "related_task_ids": [], "role": "neural_runtime"},
    ]
    registry = {"schema_version": 1, "kind": "neurobench-consolidated-registry", "source_counts": {"paper": count},
                "tasks": rows, "implementations": implementations, "interpretation": "Fixture registration metadata"}
    originals[builder.REGISTRY] = put(root, builder.REGISTRY, builder.encode(registry))
    return originals


class PaperBindingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.root = Path(self.tmp.name)
        self.originals = fixture(self.root)
        self.registry = load(self.root, builder.REGISTRY)
        self.paper_rows = self.registry["tasks"][:-1]

    def tearDown(self):
        self.tmp.cleanup()

    def bind(self, check=False):
        return builder.write_or_check(self.root, check=check, expected_count=2)

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def mutate_task(self, row, mutation):
        path = row["specification"]["path"]
        doc = load(self.root, path)
        mutation(doc)
        body = put(self.root, path, doc)
        registry = load(self.root, builder.REGISTRY)
        current_row = next(item for item in registry["tasks"] if item["id"] == row["id"])
        current_row["specification"] = builder.pin(path, body)
        current_row["original_specification"] = builder.pin(current_row["original_specification"]["path"], body)
        put(self.root, builder.REGISTRY, registry)
        return current_row

    def test_exact_history_and_registry_snapshot_are_preserved_and_referenced(self):
        result = self.bind()
        self.assertEqual(result["dispositions"], {"source_unresolved": 2})
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.originals[builder.REGISTRY])
        registry = load(self.root, builder.REGISTRY)
        self.assertTrue(registry["paper_improvement"]["coverage_required"])
        self.assertEqual(registry["paper_improvement"]["pre_improvement_registry"],
                         builder.pin(builder.SNAPSHOT, self.originals[builder.REGISTRY]))
        for old_row, row in zip(self.paper_rows, registry["tasks"]):
            history = old_row["task_directory"] + "/" + builder.HISTORY
            old_bytes = self.originals[old_row["specification"]["path"]]
            self.assertEqual((self.root / history).read_bytes(), old_bytes)
            self.assertEqual(row["original_specification"], old_row["original_specification"])
            self.assertEqual(row["specification_revision"]["previous_specification"], builder.pin(history, old_bytes))

    def test_repeat_and_check_are_byte_idempotent(self):
        self.bind()
        before = self.snapshot()
        self.assertEqual(self.bind()["changed_files"], 0)
        self.assertEqual(self.bind(check=True)["changed_files"], 0)
        self.assertEqual(self.snapshot(), before)

    def test_check_before_binding_never_writes(self):
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            self.bind(check=True)
        self.assertEqual(self.snapshot(), before)

    def test_current_success_is_improvement_and_old_evaluation_is_historical_only(self):
        self.bind()
        for old_row in self.paper_rows:
            current = load(self.root, old_row["specification"]["path"])
            old = json.loads(self.originals[old_row["specification"]["path"]])
            self.assertEqual(current["objective"], builder.OBJECTIVE)
            self.assertIn("Fixture target", current["goal"])
            self.assertIn("Fixture held-animal error", current["primary_outputs"][1])
            self.assertFalse(current["admission"]["runnable"])
            self.assertFalse(current["admission"]["research_qualified"])
            self.assertIsNone(current["evaluation"]["executor_ref"])
            self.assertIsNone(current["evaluation"]["scorer_ref"])
            self.assertEqual(current["evaluation"]["reproduction_role"], "calibration_only")
            for field in ("scoring", "reproduction", "improvement", "readiness", "state"):
                self.assertNotIn(field, current)
            self.assertNotIn("Numerical reconstruction is success", json.dumps(current))
            for field in builder.SOURCE_FIELDS:
                if field in old:
                    self.assertEqual(current[field], old[field])

    def test_neural_rows_and_all_implementation_runtime_bytes_remain_unchanged(self):
        before = {path: body for path, body in self.snapshot().items() if "/implementations/" in path}
        self.bind()
        after = {path: body for path, body in self.snapshot().items() if "/implementations/" in path}
        self.assertEqual(before, after)
        registry = load(self.root, builder.REGISTRY)
        self.assertEqual(registry["tasks"][-1], self.registry["tasks"][-1])
        self.assertEqual(registry["implementations"][-1], self.registry["implementations"][-1])
        for old, new in zip(self.paper_rows, registry["tasks"]):
            self.assertEqual(old["runtime_manifest"], new["runtime_manifest"])

    def test_paper_only_and_mixed_roles_are_scoped_correctly(self):
        self.bind()
        rows = load(self.root, builder.REGISTRY)["implementations"]
        self.assertEqual(rows[0]["role"], "calibration_only")
        self.assertIn("Original paper notes", rows[0]["scope_notes"])
        self.assertEqual(rows[1]["role"], self.registry["implementations"][1]["role"])
        self.assertEqual(rows[1]["scope_notes"], self.registry["implementations"][1]["scope_notes"])
        self.assertEqual(rows[1]["evaluation_roles"], {"NEURAL-fixture": "active_evaluation", self.paper_rows[0]["id"]: "calibration_only"})

    def test_related_neural_task_prevents_blanket_role_overwrite(self):
        registry = load(self.root, builder.REGISTRY)
        registry["implementations"][0]["related_task_ids"] = ["NEURAL-fixture"]
        put(self.root, builder.REGISTRY, registry)
        self.bind()
        row = load(self.root, builder.REGISTRY)["implementations"][0]
        self.assertEqual(row["role"], "task_implementation")
        self.assertEqual(row["scope_notes"], "Original paper notes")

    def test_later_neural_metadata_in_shared_implementation_is_preserved(self):
        self.bind()
        registry = load(self.root, builder.REGISTRY)
        shared = registry["implementations"][1]
        shared["evaluation_roles"]["NEURAL-fixture"] = "new_neural_evaluation"
        shared["role"] = "new_shared_role"
        shared["scope_notes"] = "Updated neural scope note"
        put(self.root, builder.REGISTRY, registry)
        self.bind()
        updated = load(self.root, builder.REGISTRY)["implementations"][1]
        self.assertEqual(updated, shared)

    def test_later_implementations_are_preserved_without_reclassifying_them(self):
        self.bind()
        registry = load(self.root, builder.REGISTRY)
        additions = [
            {"id": "future-neural", "owner_ids": ["NEURAL-fixture"], "related_task_ids": [], "role": "neural_runtime"},
            {"id": "future-paper", "owner_ids": [self.paper_rows[0]["id"]], "related_task_ids": [],
             "role": "future_improvement_evaluator", "scope_notes": "Explicitly outside the historical migration"},
        ]
        registry["implementations"].extend(additions)
        put(self.root, builder.REGISTRY, registry)
        self.bind(check=True)
        self.bind()
        self.assertEqual(load(self.root, builder.REGISTRY)["implementations"][-2:], additions)

    def test_historical_implementation_removal_or_owner_change_is_rejected(self):
        self.bind()
        registry = load(self.root, builder.REGISTRY)
        removed = copy.deepcopy(registry)
        removed["implementations"].pop(0)
        put(self.root, builder.REGISTRY, removed)
        with self.assertRaisesRegex(ValueError, "historical implementation removed"):
            self.bind()
        registry["implementations"][0]["owner_ids"] = ["NEURAL-fixture"]
        put(self.root, builder.REGISTRY, registry)
        with self.assertRaisesRegex(ValueError, "ownership changed"):
            self.bind()

    def test_expansion_missing_common_metadata_has_neutral_defaults(self):
        row = self.paper_rows[-1]
        def remove_common(doc):
            for field in ("input_assets", "resources", "provenance"):
                doc.pop(field)
        self.mutate_task(row, remove_common)
        self.bind()
        current = load(self.root, row["specification"]["path"])
        for field in ("input_assets", "resources", "provenance", "holds", "next_implementation_action"):
            self.assertIsInstance(current[field], dict)
        self.assertEqual(current["holds"]["task_specific"], current["blocking_issues"])
        self.assertFalse(current["next_implementation_action"]["execution_authorized_by_manifest"])

    def test_contract_update_rebuilds_using_original_history(self):
        self.bind()
        history_before = (self.root / builder.SNAPSHOT).read_bytes()
        row = self.paper_rows[0]
        contract_path = row["task_directory"] + "/improvement.v1.json"
        doc = load(self.root, contract_path)
        doc["disposition"] = "ineligible"
        doc["disposition_reason"] = "Fixture has no ordered endpoint"
        doc["same_task"]["target"]["description"] = "Updated fixture target"
        put(self.root, contract_path, doc)
        with self.assertRaisesRegex(ValueError, "stale or missing"):
            self.bind(check=True)
        self.bind()
        current = load(self.root, row["specification"]["path"])
        self.assertEqual(current["status"], "ineligible")
        self.assertIn("Updated fixture target", current["goal"])
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), history_before)
        self.assertEqual((self.root / (row["task_directory"] + "/" + builder.HISTORY)).read_bytes(),
                         self.originals[row["specification"]["path"]])
        self.bind(check=True)

    def test_late_invalid_contract_has_no_write_side_effects(self):
        path = self.paper_rows[-1]["task_directory"] + "/improvement.v1.json"
        doc = load(self.root, path)
        doc["invalid_fixture"] = True
        put(self.root, path, doc)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "shared contract validator"):
            self.bind()
        self.assertEqual(self.snapshot(), before)

    def test_default_requires_exactly_116_papers(self):
        with self.assertRaisesRegex(ValueError, "exactly 116"):
            builder.build_outputs(self.root)

    def test_full_roster_count_is_deterministic_with_fixture_metadata(self):
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as tmp:
            root = Path(tmp)
            fixture(root, count=116)
            one = builder.build_outputs(root)
            two = builder.build_outputs(root)
            self.assertEqual(one, two)
            registry = json.loads(one[builder.REGISTRY])
            self.assertEqual(registry["paper_improvement"]["registered_count"], 116)
            self.assertEqual(sum(row.get("track") == "paper" for row in registry["tasks"]), 116)

    def test_actual_116_historical_schemas_bind_without_rewriting_source_metadata(self):
        repository = PATH.parents[2]
        snapshot = repository / builder.SNAPSHOT
        original_registry = snapshot.read_bytes() if snapshot.is_file() else (repository / builder.REGISTRY).read_bytes()
        rows = json.loads(original_registry)["tasks"]
        papers = [row for row in rows if row.get("track") == "paper"]
        self.assertEqual(len(papers), 116)
        with tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve()) as tmp:
            root = Path(tmp)
            put(root, builder.REGISTRY, original_registry)
            put(root, "src/neurobench/paper_improvement.py",
                (self.root / "src/neurobench/paper_improvement.py").read_bytes())
            for row in papers:
                source = row["task_directory"] + "/" + builder.HISTORY if snapshot.is_file() else row["specification"]["path"]
                put(root, row["specification"]["path"], (repository / source).read_bytes())
                put(root, row["task_directory"] + "/improvement.v1.json", contract(row["id"]))
            outputs = builder.build_outputs(root)
            for row in papers:
                task_path = row["specification"]["path"]
                original = load(root, task_path)
                current = json.loads(outputs[task_path])
                self.assertEqual(current["title"], row["title"])
                self.assertEqual(current["id"], row["specification_id"])
                for field in builder.SOURCE_FIELDS:
                    if field in original:
                        self.assertEqual(current[field], original[field])
                self.assertEqual(outputs[row["task_directory"] + "/" + builder.HISTORY], (root / task_path).read_bytes())

    def test_missing_contract_or_unregistered_contract_is_rejected(self):
        path = self.root / (self.paper_rows[-1]["task_directory"] + "/improvement.v1.json")
        old = path.read_bytes()
        path.unlink()
        with self.assertRaisesRegex(ValueError, "exactly the registered"):
            self.bind()
        path.write_bytes(old)
        put(self.root, "benchmarks/paper/unregistered/improvement.v1.json", contract("unregistered"))
        with self.assertRaisesRegex(ValueError, "exactly the registered"):
            self.bind()

    def test_duplicate_case_colliding_ids_are_rejected(self):
        registry = load(self.root, builder.REGISTRY)
        registry["tasks"][-1]["id"] = registry["tasks"][0]["id"].lower()
        put(self.root, builder.REGISTRY, registry)
        with self.assertRaisesRegex(ValueError, "unique, including case"):
            self.bind()

    def test_duplicate_json_keys_and_nonfinite_values_are_rejected(self):
        path = self.paper_rows[-1]["task_directory"] + "/improvement.v1.json"
        for body in (b'{"task_id":"a","task_id":"b"}', b'{"n":NaN}', b'{"n":Infinity}', b'{"n":1e999}'):
            with self.subTest(body=body):
                put(self.root, path, body)
                before = self.snapshot()
                with self.assertRaises(ValueError):
                    self.bind()
                self.assertEqual(before, self.snapshot())

    def test_stale_current_specification_pin_is_rejected(self):
        path = self.root / self.paper_rows[0]["specification"]["path"]
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaisesRegex(ValueError, "stale pin"):
            self.bind()

    def test_tampered_history_or_snapshot_is_rejected_without_writes(self):
        self.bind()
        for path in (builder.SNAPSHOT, self.paper_rows[-1]["task_directory"] + "/" + builder.HISTORY):
            with self.subTest(path=path):
                original = (self.root / path).read_bytes()
                put(self.root, path, original + b" ")
                before = self.snapshot()
                with self.assertRaisesRegex(ValueError, "stale pin"):
                    self.bind()
                self.assertEqual(before, self.snapshot())
                put(self.root, path, original)

    def test_preexisting_different_history_is_never_clobbered(self):
        path = self.paper_rows[-1]["task_directory"] + "/" + builder.HISTORY
        put(self.root, path, b"an unrelated historical document")
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "refusing to clobber"):
            self.bind()
        self.assertEqual(before, self.snapshot())

    def test_preexisting_different_snapshot_is_never_clobbered(self):
        put(self.root, builder.SNAPSHOT, b'{"unrelated":true}\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "refusing to clobber"):
            self.bind()
        self.assertEqual(before, self.snapshot())

    def test_original_locator_and_hash_remain_separate_from_current_pin(self):
        self.bind()
        registry = load(self.root, builder.REGISTRY)
        row = registry["tasks"][0]
        self.assertTrue(row["original_specification"]["path"].startswith("retired/source/"))
        self.assertNotEqual(row["original_specification"]["sha256"], row["specification"]["sha256"])
        self.assertEqual(row["original_specification"]["sha256"], row["specification_revision"]["previous_specification"]["sha256"])

    def test_specification_alias_is_preserved(self):
        old_row = self.paper_rows[-1]
        self.mutate_task(old_row, lambda doc: doc.update(id="source-alias"))
        registry = load(self.root, builder.REGISTRY)
        registry["tasks"][1]["specification_id"] = "source-alias"
        registry["tasks"][1]["specification_alias"] = True
        put(self.root, builder.REGISTRY, registry)
        self.bind()
        current = load(self.root, old_row["specification"]["path"])
        row = load(self.root, builder.REGISTRY)["tasks"][1]
        self.assertEqual(current["id"], "source-alias")
        self.assertEqual(row["id"], old_row["id"])
        self.assertTrue(row["specification_alias"])

    def test_expansion_title_omission_uses_registry_title(self):
        row = self.paper_rows[-1]
        self.mutate_task(row, lambda doc: doc.pop("title"))
        self.bind()
        self.assertEqual(load(self.root, row["specification"]["path"])["title"], row["title"])

    def test_conflicting_title_and_unsafe_paths_fail_preflight(self):
        self.mutate_task(self.paper_rows[-1], lambda doc: doc.update(title="Conflicting title"))
        with self.assertRaisesRegex(ValueError, "title drift"):
            self.bind()
        for value in ("/absolute/path", "benchmarks/../outside", "benchmarks//paper", "benchmarks/./paper", "bad\\path"):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "unsafe"):
                builder.safe_path(self.root, value)

    def test_linked_output_parent_and_contract_are_rejected(self):
        destination = self.root / self.paper_rows[-1]["task_directory"] / "historical"
        target = self.root / "outside-history"
        target.mkdir()
        destination.symlink_to(target, target_is_directory=True)
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.bind()
        self.assertEqual(before, self.snapshot())
        destination.unlink()
        contract_path = self.root / self.paper_rows[-1]["task_directory"] / "improvement.v1.json"
        body = contract_path.read_bytes()
        contract_path.unlink()
        put(self.root, "outside-contract.json", body)
        contract_path.symlink_to(self.root / "outside-contract.json")
        with self.assertRaisesRegex(ValueError, "symlink"):
            self.bind()

    def test_missing_snapshot_after_binding_cannot_rebase_history(self):
        self.bind()
        (self.root / builder.SNAPSHOT).unlink()
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, "missing required file"):
            self.bind()
        self.assertEqual(before, self.snapshot())

    def test_missing_one_revision_after_binding_fails_coverage(self):
        self.bind()
        registry = load(self.root, builder.REGISTRY)
        registry["tasks"][1].pop("specification_revision")
        put(self.root, builder.REGISTRY, registry)
        with self.assertRaisesRegex(ValueError, "missing paper specification revision"):
            self.bind()

    def test_validator_is_required_and_cli_runs_under_isolated_stdlib_python(self):
        source = self.root / "src/neurobench/paper_improvement.py"
        source.unlink()
        with self.assertRaisesRegex(ValueError, "validator is required"):
            self.bind()
        result = subprocess.run([sys.executable, "-I", "-S", str(PATH), "--check", "--root", str(self.root)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("exactly 116", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_real_validator_accepts_fixture_when_available(self):
        source = PATH.parents[2] / "src/neurobench/paper_improvement.py"
        if not source.is_file():
            self.skipTest("shared validator arrives in the integration commit")
        validate = builder.load_validator(PATH.parents[2])
        self.assertEqual(validate(contract("PAPER-fixture-001"), task_id="PAPER-fixture-001"), [])


if __name__ == "__main__":
    unittest.main()
