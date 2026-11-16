"""Generated filesystem controls; no authentic article, data or code bodies."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("rep012_packets", HERE / "packet.py")
packet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packet)


class PacketControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rep012-invented-packets-")
        self.root = Path(self.temp.name).resolve()
        self.originals = self.root / "originals"
        self.originals.mkdir()
        self.catalog, self.documents = packet.package()
        self.catalog = copy.deepcopy(self.catalog)
        self.sources = {}
        self.payloads = {}
        self.denied = self.root / "private-reference.json"
        self.denied.write_bytes(b"INVENTED PRIVATE REFERENCE: NEVER COPY")
        for index, logical in enumerate(self.catalog["inputs"]):
            self.add(logical, b"INVENTED SCIENTIFIC INPUT " + str(index).encode())
        for index, name in enumerate(self.catalog["official_code"]):
            self.add("task/author_code/" + name, b"# INVENTED OFFICIAL SOURCE " + str(index).encode() + b"\n")
        self.review_path = self.root / "review.json"
        self.selection_path = self.root / "selection.json"
        self.output = self.root / "pair"
        self.review = self.make_review(self.catalog)
        self.selection = self.make_selection(self.catalog, self.review)

    def add(self, logical, body):
        p = self.originals / logical.replace("/", "--")
        p.write_bytes(body)
        value = packet.pin(body)
        if logical.startswith("task/author_code/"):
            self.catalog["official_code"][logical.split("/")[-1]] = value
        else:
            self.catalog["inputs"][logical] = value
        self.sources[logical] = dict(path=str(p), **value)
        self.payloads[logical] = body

    def make_review(self, catalog):
        return dict(schema_version=1, task_id=packet.TASK, profile=packet.PROFILE,
            decision="approved_exact_candidate_materials_for_local_use",
            paper_coverage="author_manuscript_main_text_only",
            reviewed_inputs=copy.deepcopy(catalog["inputs"]),
            reviewed_official_code=copy.deepcopy(catalog["official_code"]),
            official_provenance=copy.deepcopy(catalog["official_provenance"]),
            authorized_local_research_use=True, contains_private_references=False,
            contains_historical_outputs=False, contains_credentials=False,
            denied_files=[packet.pin(self.denied.read_bytes())], denied_paths=[str(self.denied)])

    def make_selection(self, catalog, review):
        body = packet.encode(review)
        self.review_path.write_bytes(body)
        return dict(schema_version=1, task_id=packet.TASK, profile=packet.PROFILE,
            sources=copy.deepcopy(self.sources), review=dict(path=str(self.review_path), **packet.pin(body)),
            exclusions=dict(files=copy.deepcopy(review["denied_files"]), paths=copy.deepcopy(review["denied_paths"])),
            runtime=dict(identity_sha256="1" * 64, tool_contract_sha256="2" * 64),
            budget=dict(wall_seconds=120, cpu_seconds=120, memory_bytes=268435456, model_tokens=1000, network="none"))

    def prepared(self):
        return packet.prepare(self.selection, self.review, self.catalog, self.documents)

    def build(self):
        plan, docs = self.prepared()
        result = packet.build(self.output, self.selection, self.review, plan, docs, HERE)
        return plan, result

    def tearDown(self):
        # Generated read-only trees are made removable only after control completion.
        for p in self.root.rglob("*"):
            if not p.is_symlink():
                os.chmod(p, 0o700 if p.is_dir() else 0o600)
        self.temp.cleanup()

    def test_unmodified_cli_plan_never_opens_absent_authentic_payloads(self):
        catalog, unused = packet.package()
        review = self.make_review(catalog)
        selection = self.make_selection(catalog, review)
        selected = dict(catalog["inputs"])
        selected.update({"task/author_code/" + n: v for n, v in catalog["official_code"].items()})
        selection["sources"] = {n: dict(path=str(self.root / ("ABSENT-" + n.replace("/", "--"))), **v)
                                for n, v in selected.items()}
        body = packet.encode(selection)
        self.selection_path.write_bytes(body)
        output = self.root / "plan.json"
        observed = subprocess.run([sys.executable, "-I", "-S", "-B", str(HERE / "packet.py"), "plan",
            "--selection", str(self.selection_path), "--selection-bytes", str(len(body)),
            "--selection-sha256", packet.pin(body)["sha256"], "--output", str(output)],
            cwd=self.root, capture_output=True, timeout=10)
        self.assertEqual(observed.returncode, 0, observed.stderr)
        plan = json.loads(output.read_bytes())
        self.assertFalse(plan["payload_read"])
        self.assertEqual(plan["views"]["A"]["public/input_manifest.json"], catalog["inputs"]["public/input_manifest.json"])
        self.assertFalse(self.output.exists())

    def test_complete_generated_pair_has_exact_code_only_difference(self):
        plan, receipt = self.build()
        self.assertEqual(receipt["status"], "complete_exact_paired_candidate_views")
        self.assertEqual(len(plan["views"]["A"]), 9)
        self.assertEqual(len(plan["views"]["B"]), 17)
        for name in plan["common"]:
            self.assertEqual((self.output / "A" / name).read_bytes(), (self.output / "B" / name).read_bytes())
        self.assertFalse((self.output / "A/task/author_code").exists())
        self.assertEqual(packet.verify_pair(self.output, plan), receipt["views"])

    def test_case_alias_denied_directory_is_refused(self):
        alias = self.root / "ORIGINALS"
        if not alias.exists():
            self.skipTest("Physical case alias not provided by this filesystem")
        self.review["denied_paths"].append(str(alias))
        self.selection["exclusions"]["paths"].append(str(alias))
        with self.assertRaises(ValueError):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_output_inside_case_alias_of_private_tree_refuses(self):
        directory = self.root / "private-area"
        directory.mkdir()
        alias = self.root / "PRIVATE-AREA"
        if not alias.exists():
            self.skipTest("Physical case alias not provided by this filesystem")
        self.review["denied_paths"].append(str(directory))
        self.selection["exclusions"]["paths"].append(str(directory))
        plan, docs = self.prepared()
        with self.assertRaises(ValueError):
            packet.build(alias / "new-child", self.selection, self.review, plan, docs, HERE)
        self.assertFalse((directory / "new-child").exists())

    def test_nonexistent_normalized_suffix_overlap_refuses(self):
        self.assertTrue(packet.within(self.root / "Future" / "child", self.root / "future"))
        self.assertTrue(packet.within(self.root / "cafe\u0301" / "child", self.root / "caf\u00e9"))

    def test_misbound_source_review_is_rejected_before_body_read(self):
        self.selection["review"] = copy.deepcopy(self.selection["sources"]["public/data.npz"])
        body = packet.encode(self.selection)
        self.selection_path.write_bytes(body)
        forbidden = Path(self.selection["review"]["path"])
        original = packet.read_file
        reads = []
        def observed(value, expected, cap=packet.PAYLOAD_CAP):
            reads.append(Path(value))
            if Path(value) == forbidden:
                raise AssertionError("Misbound authentic source opened as review metadata")
            return original(value, expected, cap)
        with mock.patch.object(packet, "package", return_value=(self.catalog, self.documents)), \
             mock.patch.object(packet, "read_file", side_effect=observed):
            result = packet.main(["plan", "--selection", str(self.selection_path),
                "--selection-bytes", str(len(body)), "--selection-sha256", packet.pin(body)["sha256"],
                "--output", str(self.root / "no-plan.json")])
        self.assertEqual(result, 1)
        self.assertNotIn(forbidden, reads)

    def test_private_review_identity_is_rejected_before_body_read(self):
        self.selection["review"] = dict(path=str(self.denied), **packet.pin(self.denied.read_bytes()))
        with self.assertRaises(ValueError):
            packet.validate_selection_metadata(self.selection, self.catalog)

    def test_cached_output_review_is_refused(self):
        self.review["contains_historical_outputs"] = True
        with self.assertRaises(ValueError):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_private_identity_cannot_be_renamed_into_selected_sources(self):
        self.review["denied_files"].append(next(iter(self.catalog["inputs"].values())))
        self.selection["exclusions"]["files"].append(next(iter(self.catalog["inputs"].values())))
        with self.assertRaises(ValueError):
            self.prepared()
        self.assertFalse(self.output.exists())

    def test_private_path_tree_cannot_be_selected(self):
        self.review["denied_paths"].append(str(self.originals))
        self.selection["exclusions"]["paths"].append(str(self.originals))
        with self.assertRaises(ValueError):
            self.prepared()

    def test_review_must_cover_all_exact_source_members(self):
        self.review["reviewed_official_code"].pop("Figure_3.py")
        with self.assertRaises(ValueError):
            self.prepared()

    def test_unselected_notebook_or_receipt_never_enters_packet(self):
        self.selection["sources"]["task/author_code/Main_Pipeline.ipynb"] = next(iter(self.sources.values()))
        with self.assertRaises(ValueError):
            self.prepared()

    def test_source_alias_fails_before_output_creation(self):
        row = next(iter(self.selection["sources"].values()))
        alias = self.root / "source-alias"
        alias.symlink_to(row["path"])
        row["path"] = str(alias)
        with self.assertRaises(ValueError):
            plan, docs = self.prepared()
            packet.build(self.output, self.selection, self.review, plan, docs, HERE)
        self.assertFalse(self.output.exists())

    def test_source_mutation_leaves_no_success_receipt(self):
        plan, docs = self.prepared()
        row = self.selection["sources"]["public/data.npz"]
        body = Path(row["path"]).read_bytes()
        Path(row["path"]).write_bytes(b"X" * len(body))
        with self.assertRaises(ValueError):
            packet.build(self.output, self.selection, self.review, plan, docs, HERE)
        self.assertTrue(self.output.exists())
        self.assertFalse((self.output / "PACKET_RECEIPT.private.json").exists())

    def test_common_content_mutation_is_detected(self):
        plan, unused = self.build()
        p = self.output / "B/public/data.npz"
        os.chmod(p, 0o600)
        body = p.read_bytes()
        p.write_bytes(b"Z" * len(body))
        os.chmod(p, 0o444)
        with self.assertRaises(ValueError):
            packet.verify_pair(self.output, plan)

    def test_extra_empty_directory_is_detected(self):
        plan, unused = self.build()
        p = self.output / "A/task"
        os.chmod(p, 0o755)
        (p / "unreviewed").mkdir(mode=0o555)
        os.chmod(p, 0o555)
        with self.assertRaises(ValueError):
            packet.verify_pair(self.output, plan)

    def test_credential_literal_stops_build(self):
        logical = "task/author_code/Figure_2.py"
        self.add(logical, b"# INVENTED credential\ncredential = 'ghp_" + b"Q" * 28 + b"'\n")
        self.review = self.make_review(self.catalog)
        self.selection = self.make_selection(self.catalog, self.review)
        plan, docs = self.prepared()
        with self.assertRaisesRegex(ValueError, "Credential-like"):
            packet.build(self.output, self.selection, self.review, plan, docs, HERE)
        self.assertFalse((self.output / "PACKET_RECEIPT.private.json").exists())

    def test_existing_output_is_never_replaced(self):
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_bytes(b"KEEP")
        plan, docs = self.prepared()
        with self.assertRaises(ValueError):
            packet.build(self.output, self.selection, self.review, plan, docs, HERE)
        self.assertEqual(sentinel.read_bytes(), b"KEEP")

    def test_network_or_boolean_budget_is_refused(self):
        self.selection["budget"]["network"] = "on"
        with self.assertRaises(ValueError):
            self.prepared()
        self.selection["budget"]["network"] = "none"
        self.selection["budget"]["cpu_seconds"] = True
        with self.assertRaises(ValueError):
            self.prepared()

    def test_document_complete_claim_is_refused(self):
        self.review["paper_coverage"] = "main_and_methods"
        with self.assertRaises(ValueError):
            self.prepared()


if __name__ == "__main__":
    unittest.main(verbosity=2)
