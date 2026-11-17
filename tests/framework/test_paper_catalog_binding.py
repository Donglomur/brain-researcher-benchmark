"""Independent paper binding/catalog/CLI controls using synthetic metadata only."""
from contextlib import redirect_stdout
import copy
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


catalog_fixture = module("paper_catalog_fixture", ROOT / "tests/framework/test_catalog.py")
binding_fixture = module("paper_binding_fixture", ROOT / "tests/maintenance/test_paper_improvement_bindings.py")
admission_fixture = module("paper_admission_fixture", ROOT / "tests/framework/test_paper_improvement.py")
catalog, cli = catalog_fixture.catalog, catalog_fixture.cli
builder, engine = binding_fixture.builder, admission_fixture.paper


class PaperCatalogBindingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        catalog_fixture.fixture(self.root)
        self.original_registry = (self.root / builder.REGISTRY).read_bytes()
        registry = json.loads(self.original_registry)
        self.original_tasks = {}
        for row in registry["tasks"]:
            if row["track"] == "paper":
                self.original_tasks[row["id"]] = (self.root / row["specification"]["path"]).read_bytes()
                binding_fixture.put(self.root, row["task_directory"] + "/improvement.v1.json",
                                    binding_fixture.contract(row["id"]))
        builder.write_or_check(self.root, validator=engine.contract_validate)

    def registry(self):
        return json.loads((self.root / builder.REGISTRY).read_bytes())

    def save_registry(self, value):
        binding_fixture.put(self.root, builder.REGISTRY, value)

    def snapshot_mutation(self, mutate):
        doc = json.loads((self.root / builder.SNAPSHOT).read_bytes())
        mutate(doc)
        body = binding_fixture.put(self.root, builder.SNAPSHOT, doc)
        current = self.registry()
        current["paper_improvement"]["pre_improvement_registry"] = builder.pin(builder.SNAPSHOT, body)
        self.save_registry(current)

    def ready_result(self):
        contract, result = admission_fixture.fixture()
        contract["task_id"] = result["task_id"] = "PAPER-001"
        admission_fixture.refreeze(contract, result)
        binding_fixture.put(self.root, "benchmarks/paper/PAPER-001/improvement.v1.json", contract)
        builder.write_or_check(self.root, validator=engine.contract_validate)
        return contract, result

    def result_file(self, value):
        path = self.root / "comparison.json"
        path.write_bytes(value if isinstance(value, bytes) else json.dumps(value).encode())
        return path

    def test_full_116_coverage_preserves_original_bytes_without_readiness(self):
        discovered = catalog.discover(self.root)
        self.assertEqual(discovered["paper_improvement_counts"], {
            "registered": 116, "covered": 116, "eligible": 0, "improvement_ready": 0,
            "design_ready": 0, "source_unresolved": 116, "ineligible": 0, "not_audited": 0,
        })
        self.assertEqual(discovered["scientific_readiness"], "unknown")
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.original_registry)
        for identifier, body in self.original_tasks.items():
            self.assertEqual((self.root / "benchmarks/paper" / identifier / builder.HISTORY).read_bytes(), body)
        checked = builder.write_or_check(self.root, check=True, validator=engine.contract_validate)
        self.assertEqual(checked["changed_files"], 0)

    def test_missing_or_tampered_snapshot_cannot_pass_catalog_or_contract_cli(self):
        path = self.root / builder.SNAPSHOT
        original = path.read_bytes()
        for replacement in (None, b'{"tampered":true}\n'):
            with self.subTest(replacement=replacement):
                if replacement is None:
                    path.unlink()
                else:
                    path.write_bytes(replacement)
                for operation in (lambda: catalog.discover(self.root), lambda: cli.paper_contract("PAPER-001", self.root)):
                    with self.assertRaises(ValueError):
                        operation()
                path.write_bytes(original)

    def test_coverage_metadata_is_required_and_semantic_fields_are_checked(self):
        original = self.registry()
        mutations = [
            lambda r: r.pop("paper_improvement"),
            lambda r: r["paper_improvement"].pop("coverage_required"),
            lambda r: r["paper_improvement"].update(coverage_required=False),
            lambda r: r["paper_improvement"].update(schema_version="other-version"),
            lambda r: r["paper_improvement"].update(objective="reproduce_source"),
            lambda r: r["paper_improvement"].update(registered_count=115),
            lambda r: r["paper_improvement"].update(registered_count=True),
        ]
        for index, mutate in enumerate(mutations):
            with self.subTest(index=index):
                current = copy.deepcopy(original)
                mutate(current)
                self.save_registry(current)
                with self.assertRaises(ValueError):
                    catalog.discover(self.root)
        self.save_registry(original)

    def test_every_registered_paper_requires_revision_and_contract(self):
        original = self.registry()
        paper = next(row for row in original["tasks"] if row["track"] == "paper")
        changed = copy.deepcopy(original)
        next(row for row in changed["tasks"] if row["id"] == paper["id"]).pop("specification_revision")
        self.save_registry(changed)
        with self.assertRaisesRegex(ValueError, "requires every paper contract"):
            catalog.discover(self.root)
        self.save_registry(original)
        (self.root / paper["specification_revision"]["improvement_contract"]["path"]).unlink()
        with self.assertRaises(ValueError):
            catalog.discover(self.root)

    def test_rehashed_snapshot_roster_drift_is_rejected(self):
        self.snapshot_mutation(lambda doc: doc["tasks"].pop())
        with self.assertRaisesRegex(ValueError, "original registration roster"):
            catalog.discover(self.root)

    def test_later_neural_expansion_does_not_invalidate_paper_history(self):
        current = self.registry()
        row = copy.deepcopy(next(row for row in current["tasks"] if row["id"] == "NEURAL-EXP-0-0"))
        spec = json.loads((self.root / row["specification"]["path"]).read_bytes())
        row["id"] = row["specification_id"] = spec["id"] = "NEURAL-NEW-001"
        row["task_directory"] = "benchmarks/neural/NEURAL-NEW-001"
        relative = row["task_directory"] + "/task.json"
        body = binding_fixture.put(self.root, relative, spec)
        row["specification"] = builder.pin(relative, body)
        row["original_specification"] = builder.pin("former-source/NEURAL-NEW-001.json", body)
        current["tasks"].append(row)
        for key in ("neural", "total", "expansion_drafts"):
            current["source_counts"][key] += 1
        self.save_registry(current)
        checked = builder.write_or_check(self.root, check=True, validator=engine.contract_validate)
        self.assertEqual(checked["changed_files"], 0)
        discovered = catalog.discover(self.root)
        self.assertEqual(discovered["counts"]["neural"], 119)
        self.assertEqual(discovered["paper_improvement_counts"]["covered"], 116)
        self.assertEqual((self.root / builder.SNAPSHOT).read_bytes(), self.original_registry)

    def test_rehashed_snapshot_original_pin_drift_is_rejected(self):
        def change(doc):
            row = next(row for row in doc["tasks"] if row["track"] == "paper")
            row["original_specification"]["sha256"] = "f" * 64
        self.snapshot_mutation(change)
        with self.assertRaisesRegex(ValueError, "lineage differs"):
            catalog.discover(self.root)

    def test_rehashed_current_original_and_history_cannot_replace_snapshot_identity(self):
        current = self.registry()
        row = next(row for row in current["tasks"] if row["track"] == "paper")
        relative = row["specification_revision"]["previous_specification"]["path"]
        body = (self.root / relative).read_bytes() + b" "
        (self.root / relative).write_bytes(body)
        row["specification_revision"]["previous_specification"] = builder.pin(relative, body)
        row["original_specification"] = builder.pin(row["original_specification"]["path"], body)
        self.save_registry(current)
        with self.assertRaisesRegex(ValueError, "lineage differs"):
            catalog.discover(self.root)

    def test_catalog_total_read_budget_is_enforced(self):
        with patch.object(catalog, "READ_LIMIT", 1), self.assertRaisesRegex(ValueError, "read limit"):
            catalog.discover(self.root)

    def test_catalog_reader_reads_with_a_byte_limit(self):
        path = self.root / "bounded.json"
        path.write_bytes(b'{"public":true}')
        real_open = Path.open
        requested = []

        class TrackedStream:
            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *args):
                self.handle.close()

            def read(self, size=-1):
                requested.append(size)
                return self.handle.read(size)

        def tracked_open(target, *args, **kwargs):
            handle = real_open(target, *args, **kwargs)
            return TrackedStream(handle) if target == path else handle

        with patch.object(Path, "open", tracked_open):
            doc, _ = catalog.Reader(self.root).read(path)
        self.assertEqual(doc, {"public": True})
        self.assertEqual(requested, [4 * 1024 * 1024 + 1])

    def test_contract_cli_parses_verified_bytes_without_permissive_reread(self):
        with patch.object(cli, "read", side_effect=AssertionError("Do not reread pinned metadata")), \
             patch.object(cli, "_program_pin", wraps=cli._program_pin) as pinned:
            contract = cli.paper_contract("PAPER-001", self.root)
        self.assertEqual(contract["task_id"], "PAPER-001")
        self.assertTrue(pinned.call_args.kwargs["return_bytes"])

    def test_compare_result_rejects_duplicate_nonfinite_and_oversized_json(self):
        self.ready_result()
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b" " * (2 * 1024 * 1024 + 1)):
            with self.subTest(length=len(raw)):
                with self.assertRaises(ValueError):
                    cli.compare_paper("PAPER-001", self.result_file(raw), self.root)

    def test_compare_result_rejects_linked_file_parent_and_hardlink(self):
        _, result = self.ready_result()
        path = self.result_file(result)
        linked_file = self.root / "linked-result.json"
        linked_file.symlink_to(path)
        real_directory = self.root / "result-directory"
        real_directory.mkdir()
        real_result = real_directory / "result.json"
        real_result.write_text(json.dumps(result))
        linked_parent = self.root / "linked-directory"
        linked_parent.symlink_to(real_directory, target_is_directory=True)
        for linked in (linked_file, linked_parent / "result.json"):
            with self.subTest(path=linked), self.assertRaises(ValueError):
                cli.compare_paper("PAPER-001", linked, self.root)
        hardlink = self.root / "hardlink-result.json"
        hardlink.hardlink_to(path)
        with self.assertRaises(ValueError):
            cli.compare_paper("PAPER-001", hardlink, self.root)

    def test_actual_comparison_cli_distinguishes_admission_from_verified_win(self):
        _, result = self.ready_result()
        for phase, expected_code in (("final", 0), ("validation", 2)):
            result["phase"] = phase
            output = io.StringIO()
            with self.subTest(phase=phase), redirect_stdout(output):
                code = cli.main(["compare-paper", "PAPER-001", "--result", str(self.result_file(result))], root=self.root)
            response = json.loads(output.getvalue())
            self.assertEqual(code, expected_code)
            self.assertEqual(response["comparison_admitted"], phase == "final")
            self.assertIsNot(response["paper_win"], True)
            self.assertEqual(response["paper_win_verification"], "unverified")
            self.assertEqual(response["current_sota"], "not_assessed")


if __name__ == "__main__":
    unittest.main()
