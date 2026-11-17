"""Invented archive and full-scope composition controls; no authentic data/native run."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import stat
import struct
import sys
import tempfile
import time
import types
import unittest
from unittest import mock
import zipfile
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
MANIFEST = json.loads((ROOT / "benchmarks/integrity/current-closures/findlay-sleep/source-manifest.json").read_text())
PREFIX = MANIFEST["worker"]["path"].rsplit("/", 1)[0]
WAVE = Path(PREFIX).parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FRESH = load("fresh_test_source", ROOT / PREFIX / "fresh_intake.py")
CONTRACT = load("fresh_test_contract", ROOT / PREFIX / "external_contract.py")
INTAKE = load("fresh_test_intake", ROOT / WAVE / "intake-census/intake.py")
CENSUS = load("fresh_test_census", ROOT / WAVE / "identity-contrast/identity/census.py")
WORKER = load("fresh_test_worker", ROOT / MANIFEST["worker"]["path"])
INTEGRATION = load("fresh_existing_invented_fixture", ROOT / PREFIX / "test_integration.py")
OWNER = load("fresh_test_owner", ROOT / MANIFEST["entrypoint"]["path"])


def generated_archive():
    # A real classic ZIP with invented bytes; fake footer bodies are never decoded.
    class Sequential(io.BytesIO):
        def seekable(self): return False
        def seek(self, *args): raise io.UnsupportedOperation("invented non-seekable output")
    buffer = Sequential()
    bodies = {}
    for name in CENSUS.TABLES:
        footer = ("invented-footer-" + name).encode()
        bodies[name] = b"PAR1invented-no-observations" + footer + struct.pack("<I", len(footer)) + b"PAR1"
    bodies.update({"invented-metadata-%d.txt" % i: b"invented" for i in range(4)})
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, body in bodies.items():
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o444) << 16
            archive.writestr(info, body)
    data = buffer.getvalue()
    members = []
    for name, body in bodies.items():
        row = {"path": name, "bytes": len(body), "zip_compressed_bytes": len(body),
            "zip_method": 0, "zip_crc32": "%08x" % (zlib.crc32(body) & 0xffffffff),
            "unix_mode": format(stat.S_IFREG | 0o444, "o")}
        if name.endswith(".pqt"):
            n = struct.unpack("<I", body[-8:-4])[0]
            row["footer_sha256"] = hashlib.sha256(body[-8-n:-8]).hexdigest()
        members.append(row)
    ledger = {"archive_bytes": len(data), "expanded_bytes": sum(map(len, bodies.values())),
              "members": members, "member_count": 17, "parquet_member_count": 13}
    return data, ledger


def generated_contract(pin, ledger):
    """Explicit test seam, never a production-admissible metadata alternative."""
    def check(actual):
        if actual != pin: raise ValueError("invented fixture pin mismatch")
    return types.SimpleNamespace(validate_archive_pin=check)


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.data, self.ledger = generated_archive()
        self.path = self.root / "invented.zip";self.path.write_bytes(self.data)
        self.pin = {"path": str(self.path), "bytes": len(self.data),
                    "sha256": hashlib.sha256(self.data).hexdigest()}
        self.output = self.root / "output";self.output.mkdir()
        self.budget = INTAKE.Budget(self.output, time.monotonic() + 10, 1048576, 1048576)
        self.contract = generated_contract(self.pin, self.ledger)

    def tearDown(self): self.temp.cleanup()

    def test_production_refuses_generated_original_before_read(self):
        with mock.patch.object(INTAKE, "read_all", side_effect=AssertionError("no read on invalid pin")):
            with self.assertRaises(ValueError):
                FRESH.provision_original(self.pin, self.ledger, self.budget, INTAKE, CONTRACT)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_real_generated_zip_all17_and_all13_footer_bindings(self):
        copied, receipt = FRESH.provision_original(self.pin, self.ledger, self.budget, INTAKE, self.contract)
        members, integrity_pin = INTAKE.extract_verify(copied, self.ledger, self.budget)
        result = json.loads(Path(integrity_pin["path"]).read_text())
        self.assertEqual(len(result["members"]), 17)
        self.assertEqual(len(list(members.glob("*.pqt"))), 13)
        self.assertEqual(result["archive"]["sha256"], self.pin["sha256"])
        self.assertFalse((self.output / "HTTP.private.json").exists())
        value = json.loads(Path(receipt["path"]).read_text())
        self.assertEqual(value["new_GETs"], 0)
        self.assertFalse(value["prior_attempt_required"])

    def test_changed_archive_is_refused_before_copy_or_extraction(self):
        self.path.write_bytes(b"x" + self.data[1:])
        with self.assertRaisesRegex(ValueError, "SHA256"):
            FRESH.provision_original(self.pin, self.ledger, self.budget, INTAKE, self.contract)
        self.assertEqual(list(self.output.iterdir()), [])

    def test_missing_or_duplicate_member_does_not_reduce_scope(self):
        for mode in ("missing", "duplicate"):
            ledger = copy.deepcopy(self.ledger)
            if mode == "missing": ledger["members"].pop()
            else: ledger["members"][-1] = copy.deepcopy(ledger["members"][0])
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                FRESH.provision_original(self.pin, ledger, self.budget, INTAKE, self.contract)

    def test_corrupt_footer_is_retained_failure_not_census_success(self):
        self.ledger["members"][0]["footer_sha256"] = "0" * 64
        archive, _ = FRESH.provision_original(self.pin, self.ledger, self.budget, INTAKE, self.contract)
        with self.assertRaisesRegex(ValueError, "footer"):
            INTAKE.extract_verify(archive, self.ledger, self.budget)
        self.assertFalse((self.output / "INTEGRITY.private.json").exists())

    def test_duplicate_copy_destination_and_insufficient_budget_refuse(self):
        destination = self.output / "release.zip";destination.write_bytes(b"prior invented bytes")
        with self.assertRaises(FileExistsError):
            FRESH.provision_original(self.pin, self.ledger, self.budget, INTAKE, self.contract)
        self.assertEqual(destination.read_bytes(), b"prior invented bytes")
        destination.unlink()
        small = INTAKE.Budget(self.output, time.monotonic() + 10, 1048576, 0)
        with self.assertRaises(ValueError):
            FRESH.provision_original(self.pin, self.ledger, small, INTAKE, self.contract)
        self.assertFalse(destination.exists())

    def test_actual_fresh_composition_has_no_historical_or_HTTP_dependency(self):
        # Real archive provision/extraction/post-parity with invented metadata and
        # an explicitly mocked census/native seam. Not production metadata admission.
        output = self.root / "operation";output.mkdir()
        policy_value = {"invented": True}
        values = {"input_ledger": self.ledger, "published_families": {"invented": True},
                  "private_policy": policy_value}
        contract = self.contract
        contract.PINS = {k: {} for k in values}
        contract.authenticate = lambda key, body: copy.deepcopy(values[key])
        contract.join = lambda value: value
        task = {key: {"path": "/invented/" + key} for key in values}
        task.update(original_archive=self.pin, data_read_cap=33554432, worker_output_cap=33554432)
        admission = {"request": {"schema": "findlay-portable-first-intake-request/v1", "task": task},
            "source_capture": {"/invented/" + k: b"invented metadata" for k in values},
            "output_root": str(output), "work_deadline": time.monotonic() + 10,
            "source_read_bytes": 0, "runtime_join_read_bytes": 0, "receipt_read_bytes": 0}
        configured = []
        rules = types.SimpleNamespace(configure_private_policy=lambda p: configured.append(("rules", p)))
        policy = types.SimpleNamespace(configure_private_policy=lambda p: configured.append(("policy", p)))
        def full_census(members, inputs, families, budget, **kwargs):
            self.assertEqual(len(list(members.iterdir())), 17)
            self.assertTrue(all(len(x["sha256"]) == 64 for x in inputs["members"]))
            self.assertEqual(kwargs, {"rules_module": rules, "ordinary_module": "invented-ordinary", "ordinary_policy": policy})
            return {"status": "COMPLETE_INTAKE_CENSUS_WITH_GATES", "table_count": 13,
                "family_count": 98, "table_reports": ["invented"] * 13,
                "contrast_reports": ["invented-ordinary", "invented-regional"],
                "all_tables_and_families_accounted": True, "scientific_ready": False, "models_fitted": 0}
        with mock.patch.object(INTAKE, "acquire", side_effect=AssertionError("network forbidden")):
            result = FRESH.operate(admission, INTAKE, types.SimpleNamespace(census=full_census),
                rules, lambda: {"invented_native_seam": True}, "invented-ordinary", policy, contract)
        self.assertEqual(result["input_mode"], "fresh_local_original")
        self.assertNotIn("continuation_inputs", result)
        self.assertEqual(result["new_GETs"], 0)
        self.assertEqual(len(configured), 2)
        self.assertFalse(result["scientific_qualification"])


class CompositionTests(unittest.TestCase):
    def test_complete_first_census_scans13_and_routes98_and_both_reports(self):
        m, t, ms, ts = INTEGRATION.fixture()
        data = {name: [] for name in CENSUS.TABLES}
        data.update({"condition_measures.pqt": m, "condition_contrasts.pqt": t,
            "multicortical_condition_measures.pqt": [{"subject": "invented", "experiment": "Novelty",
                "acronym": "X", "spw_probe": False, "region": "X", "condition": "Early.REC.NREM", "Cortical.iEta": 1.0}],
            "multicortical_condition_contrasts.pqt": [{"subject": "invented", "experiment": "Novelty",
                "acronym": "X", "spw_probe": False, "region": "X", "Cortical.iEta.Rebound": 1.0}]})
        visited = []
        def scan(root, member, budget, factory, accumulators):
            name = member["path"];visited.append(name)
            return {"table": name, "rows": len(data[name]), "sessions": [], "groups": [],
                "schema": ms if name == "condition_measures.pqt" else ts if name == "condition_contrasts.pqt" else [],
                "readiness_gates": [], "all_decoded_rows_accounted": True}, data[name]
        class Accumulator:
            def finish(self): return {"census_rows_complete": True}
        class Book:
            ids = list(range(98))
            def new_accumulator(self, identifier): return Accumulator()
            def tables_for(self, identifier): return tuple(CENSUS.TABLES)
            def assess_schema(self, identifier): return {"invented": True}
        inputs = {"members": [{"path": name, "bytes": 12, "sha256": "0" * 64,
                    "footer_sha256": "0" * 64} for name in CENSUS.TABLES], "static_source_roster": []}
        budget = INTEGRATION.Budget()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(CENSUS, "_table_census", side_effect=scan):
            out = CENSUS.census(Path(tmp).resolve(), inputs, {}, budget,
                rules_module=types.SimpleNamespace(build_rules=lambda *args: Book()),
                ordinary_module=INTEGRATION.CORE, ordinary_policy=INTEGRATION.POLICY)
        self.assertEqual(set(visited), set(CENSUS.TABLES));self.assertEqual(len(visited), 13)
        self.assertEqual((out["table_count"], out["family_count"]), (13, 98))
        self.assertEqual(len(out["table_reports"]), 13);self.assertEqual(len(out["contrast_reports"]), 2)
        self.assertEqual(budget.written["condition-reconstruction.private.json"]["numeric_matches"], 770)
        self.assertEqual(budget.written["multicortical_condition-reconstruction.private.json"]["status_counts"],
                         {"unresolved_source_definition": 1})
        self.assertFalse(out["scientific_ready"])

    def test_worker_selects_first_intake_only_for_original_archive(self):
        admission = {"request": {"task": {"original_archive": {"invented": True}}}}
        received = []
        fresh = types.SimpleNamespace(operate=lambda *args: received.append(args) or {"invented": True})
        actual = WORKER.operate(admission, 1, 2, 3, 4, 5, 6, 7, fresh, 8)
        self.assertEqual(actual, {"invented": True})
        self.assertEqual(received, [(admission, 1, 2, 3, 5, 6, 7, 8)])
        with self.assertRaises(ValueError): WORKER.operate(admission, 1, 2, 3, 4, 5, 6, 7)

    def test_archive_contract_is_exact_and_not_a_provider_checksum(self):
        pin = {"path": "/invented/original.zip", **CONTRACT.ARCHIVE_PIN}
        CONTRACT.validate_archive_pin(pin)
        for key, replacement in (("bytes", True), ("sha256", "0" * 64), ("path", "relative.zip")):
            bad = {**pin, key: replacement}
            with self.subTest(key=key), self.assertRaises(ValueError): CONTRACT.validate_archive_pin(bad)

    def test_first_and_continuation_schema_cannot_swap_inputs(self):
        # Schema-only request check with invented external descriptor metadata.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            pin = {"path": str(root / "metadata.json"), "bytes": 1, "sha256": "0" * 64}
            request = {"schema": "findlay-portable-first-intake-request/v1",
                "execution": {"repository_root": str(ROOT), "output_root": str(ROOT / "artifacts-build/invented"),
                    "source_lock": pin, "runtime_manifest": pin,
                    "source_adoption": {"commit": "0" * 40, "worker": MANIFEST["worker"]},
                    "profile": OWNER.PROFILE},
                "task": {k: pin for k in CONTRACT.PINS}}
            request["task"].update(original_archive={"path": str(root / "original.zip"), **CONTRACT.ARCHIVE_PIN},
                data_read_cap=33554432, worker_output_cap=33554432)
            def check(value):
                p = root / "request.json";body = OWNER.canonical(value);p.write_bytes(body)
                return OWNER.load_request(p, hashlib.sha256(body).hexdigest())
            check(request)
            wrong = copy.deepcopy(request);wrong["schema"] = "findlay-portable-census-continuation-request/v1"
            with self.assertRaises(ValueError): check(wrong)
            wrong = copy.deepcopy(request);wrong["task"]["prior_attempt"] = pin
            with self.assertRaises(ValueError): check(wrong)


if __name__ == "__main__":
    unittest.main(verbosity=2)

