"""New adapter controls only; no original viewer suite or authentic corpus run."""
import argparse
import dataclasses
import gc
import hashlib
import importlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import MappingProxyType
import unittest
from unittest import mock
import weakref


HERE = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--runtime-root", type=Path,
                    default=HERE.parent / "registered-runtime/full-catalogue-v1")
parser.add_argument("--viewer-file", type=Path,
                    default=HERE.parent / "typed-map-viewer-v1/viewer.py")
parser.add_argument("--contract-file", type=Path,
                    default=HERE.parent / "registered-runtime/input-conversion-v1/CONTRACT.json")
parser.add_argument("--fixture-parent", type=Path, default=None)
ARGS, UNITTEST = parser.parse_known_args()


def module(name, path, *, package=False):
    spec = importlib.util.spec_from_file_location(
        name, path, submodule_search_locations=[str(path.parent)] if package else None)
    obj = importlib.util.module_from_spec(spec)
    sys.modules[name] = obj
    spec.loader.exec_module(obj)
    return obj


BINDINGS = json.loads((HERE / "SOURCE_BINDINGS.json").read_bytes())
for row in BINDINGS["runtime_import_closure"]:
    raw = (ARGS.runtime_root / row["relative_path"]).read_bytes()
    assert (len(raw), hashlib.sha256(raw).hexdigest()) == (row["bytes"], row["sha256"])
raw = ARGS.viewer_file.read_bytes()
assert (len(raw), hashlib.sha256(raw).hexdigest()) == (
    BINDINGS["viewer"]["bytes"], BINDINGS["viewer"]["sha256"])
module("n073_adapter_runtime", ARGS.runtime_root / "__init__.py", package=True)
c = importlib.import_module("n073_adapter_runtime.corpus")
custody = importlib.import_module("n073_adapter_runtime.runtime.core.custody")
v = module("n073_adapter_viewer", ARGS.viewer_file)
adapter = module("n073_corpus_viewer_input", HERE / "adapter.py")
CONTRACT = ARGS.contract_file.read_bytes()
assert (len(CONTRACT), hashlib.sha256(CONTRACT).hexdigest()) == (
    adapter.CONTRACT_BYTES, adapter.CONTRACT_SHA256)
a = c.admission


def pin(raw):
    return {"bytes": len(raw), "sha256": adapter.sha(raw)}


class GeneratedCorpus:
    """Invented issued metadata plus real canonical loader; no load_corpus claim.

    The real load_corpus factory requires an authentic root selection and full
    admitted originals. Here only its bundle data class/internal seal is used
    to exercise this integration. All catalogue/observations/assessment/export
    capabilities use existing invented-domain factories. One deliberately
    repeated map is explicit negative-control data, with invented adjudications.
    """

    def __init__(self, root):
        self.root = root
        self.labels = tuple("Protocol_%02d" % i for i in range(25))
        records = [a.Record("invented:record-%d-%02d" % (p, label),
                    "invented-person:%d" % p, label, self.labels[label], "dir-ap",
                    "SECRET_SESSION", "SECRET_SOURCE_NAME", 4096)
                   for p in range(3) for label in range(25)]
        self.cat = a.invented_catalogue(records, self.labels)
        self.geometry = a.Geometry((8, 8, 4), (2, .25, 0, 12, 0, 3, .5, -7,
                                             0, 0, 4, 2, 0, 0, 0, 1), ("R", "A", "S"))
        self.body = struct.pack("<256d", *(i / 10 - 12 for i in range(256)))
        (root / "canonical").mkdir()
        self.path = root / "canonical/shared.f64"
        self.path.write_bytes(self.body)
        self.fixture_written_bytes = len(self.body)
        self.receipts, self.observations = {}, {}
        self.work = a.WorkCounter()
        values = tuple(x[0] for x in struct.iter_unpack("<d", self.body))
        for row in records:
            receipt = a.OriginalReceipt(row.record_id, a.INVENTED_DOMAIN,
                        "1"*64, 4096, "invented-source", "2"*64, "3"*64,
                        adapter.CONTRACT_SHA256, "4"*64)
            self.receipts[row.record_id] = receipt
            self.observations[row.record_id] = a.inspect_array(
                row.record_id, values, self.geometry, receipt, self.work)
        raw_values = {row.record_id: values for row in records}
        self.screen = a.screen_duplicates(self.cat, self.observations, raw_values, self.work)
        decisions = [a.Adjudication(f.flag_id, "independent_measurements_confirmed",
                                    "5"*64, "6"*64) for f in self.screen.flags]
        self.assessment = a.assess_corpus(self.cat, self.observations, self.receipts,
                                         self.screen, decisions)
        self.descriptors = {rid: a.OriginalDescriptor(rid, obs.decoded_sha256, "7"*64,
                                                      tuple(0.0 for _ in range(105)))
                            for rid, obs in self.observations.items()}
        self.context = a.ContextSpec("invented-person:1", "I", "original", 2, "8"*64)
        self.plan = a.prepare_context(self.cat, self.assessment, self.context,
                                      b"generated-export-key-not-secret!", self.descriptors)
        self.inventory_rows = [{"record_id": rid, "canonical": {
                    "path": "canonical/shared.f64", **pin(self.body)},
                    "original_receipt": dataclasses.asdict(self.receipts[rid])}
                    for rid in self.observations]
        self.inventory = a.catalogue.canonical_json({"schema": "n073_canonical_inventory_v1",
                                                    "records": self.inventory_rows})
        self.inventory_pin = {"path": "INVENTORY.json", **pin(self.inventory)}
        self.verifier = custody.AuthorityVerifier(issuer_id="invented-issuer",
            issuer_key=b"i"*32, root_id="invented-root", root_key=b"r"*32,
            expected_design="9"*64)
        self.limits = v.Limits(256, 64, 20000, 100, 2, 120)

    def authority(self, plan):
        raw = self.verifier.issue(role="export", domain="invented",
            context_id=plan.context.fingerprint, nonce="generated", bindings=plan.bindings)
        return self.verifier.verify(raw, role="export", domain="invented", bindings=plan.bindings)

    def bundle(self):
        limits = {"total_read_bytes": 4*1024*1024, "per_file_bytes": 2048,
                  "cache_bytes": 0, "max_array_elements": 256,
                  "max_workspace_bytes": 4*1024*1024}
        entries, receipts = c._parse_inventory(a.catalogue.strict_json(self.inventory),
                                               self.cat, self.geometry, limits)
        mapping = c.CanonicalMapping(self.root, entries, self.geometry, limits,
                                     c.Deadline(time.monotonic()+120), seal=c._BUNDLE_SEAL)
        return c.CorpusBundle(self.cat, self.geometry, mapping, MappingProxyType(receipts),
            MappingProxyType(self.observations), self.screen, self.assessment, a.WorkCounter(),
            {}, None, MappingProxyType({}), MappingProxyType({
                "inventory_pin_digest": c.digest(self.inventory_pin)}),
            "a"*64, 0, MappingProxyType({}), c._BUNDLE_SEAL)

    def result(self, units="micron"):
        return {"schema": "n073_conversion_result_v1", "domain": a.INVENTED_DOMAIN,
                "catalogue_digest": self.cat.fingerprint, "geometry": {
                    "shape": list(self.geometry.shape), "affine": list(self.geometry.affine),
                    "orientation": list(self.geometry.orientation)},
                "spatial_units": units, "unit_conversion_performed": False,
                "records": len(self.cat.records), "canonical_bytes": 2048*len(self.cat.records),
                "inventory": pin(self.inventory),
                "independent_fidelity_rights_identity_qualification": False,
                "deployment_enabled": False}

    def options(self, *, bundle=None, plan=None, result=None):
        bundle = self.bundle() if bundle is None else bundle
        plan = self.plan if plan is None else plan
        raw = adapter.canonical(self.result() if result is None else result)
        return dict(corpus_module=c, viewer_module=v, bundle=bundle, export_plan=plan,
                    export_authority=self.authority(plan), inventory_pin=dict(self.inventory_pin),
                    converter_contract=CONTRACT, conversion_result=raw,
                    conversion_result_pin=pin(raw), limits=self.limits)


class AdapterControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="n073-adapter-generated-", dir=ARGS.fixture_parent)
        cls.f = GeneratedCorpus(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        print("GENERATED_FIXTURE_CUMULATIVE_WRITTEN_BYTES=%d" % cls.f.fixture_written_bytes)
        cls.tmp.cleanup()

    def test_full_ordered_query_alias_roundtrip_and_separate_result_schema(self):
        f = self.f
        bundle = f.bundle()
        bridge = adapter.QueryInput(**f.options(bundle=bundle))
        expected = tuple(row[0] for row in f.plan.query_map)
        independent_aliases = tuple(hashlib.sha256(
            b"n073-query-viewer-alias-v1\0" + bytes.fromhex(f.context.fingerprint)
            + bytes.fromhex(key)).hexdigest()[:32] for key in expected)
        self.assertEqual(bridge._aliases, independent_aliases)
        self.assertNotEqual([r[1] for r in f.plan.query_map], sorted(r[1] for r in f.plan.query_map))
        with self.assertRaises(v.ViewerError):
            bridge.finish()
        probabilities = [None for _ in expected]
        probabilities[0] = [1.0 if index == 7 else 0.0 for index in range(25)]
        probabilities[1] = [0.25 if index == 3 else 0.75 if index == 18 else 0.0
                            for index in range(25)]
        for i, key in enumerate(expected):
            alias = bridge._aliases[i]
            self.assertEqual(len(key), 64)
            self.assertEqual(len(alias), 32)
            bridge.dispatch({"action": "answer", "case_id": alias,
                             "probabilities": probabilities[i]})
        result = bridge.finish()
        self.assertEqual(result["schema"], "n073-corpus-viewer-query-result/v1")
        original = result["viewer_collection"]
        self.assertEqual(original["schema"], "n073-typed-map-response-collection/v1")
        self.assertEqual([r["case_id"] for r in result["source_records"]], list(expected))
        self.assertEqual(result["source_records"],
                         [{"case_id": key, "probabilities": value}
                          for key, value in zip(expected, probabilities)])
        self.assertEqual(original["records"],
                         [{"case_id": alias, "probabilities": value}
                          for alias, value in zip(independent_aliases, probabilities)])
        self.assertEqual(original["response_sha256"],
                         adapter.sha(v.json_body(original["records"]).encode()))
        self.assertEqual(result["source_response_sha256"],
                         adapter.sha(adapter.canonical(result["source_records"])))
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)  # No viewing claimed.
        with self.assertRaises(adapter.InputError):
            bridge.finish()
        bundle.close()

    def test_canonical_backing_identity_native_geometry_units_and_public_projection(self):
        f = self.f
        bundle = f.bundle()
        bridge = adapter.QueryInput(**f.options(bundle=bundle))
        view = bridge.dispatch({"action": "describe"})
        self.assertEqual(view["shape"], [8, 8, 4])
        self.assertEqual(view["spatial_units"], "micron")
        self.assertEqual(view["class_labels"], list(f.labels))
        volume = bridge._session._map
        self.assertEqual(volume.body, f.body)
        self.assertEqual(volume.affine, tuple(tuple(f.geometry.affine[i:i+4]) for i in (0,4,8,12)))
        image = bridge.dispatch({"action": "slice", "case_id": view["case_id"],
                                 "axis": 2, "index": 1, "low": -12, "high": 14})
        self.assertIn("image/svg+xml", image["media_type"])
        public = json.dumps([view, image])
        for forbidden in ["SECRET_SOURCE", "SECRET_SESSION", "invented:record",
                          "invented-person:", "label_index", "original_sha256", "canonical/shared"]:
            self.assertNotIn(forbidden, public)
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 2048)
        bundle.close()

    def test_calibration_keys_and_foreign_context_never_reach_query_loader(self):
        f = self.f
        bundle = f.bundle()
        bridge = adapter.QueryInput(**f.options(bundle=bundle))
        training_key = f.plan.training_map[0][0]
        for bad in [training_key, adapter._display_key(f.context.fingerprint, training_key),
                    f.plan.query_map[0][0], "0"*32]:
            with self.assertRaises(adapter.InputError):
                bridge._load(bad)
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
        other_context = dataclasses.replace(f.context, repetition=1)
        other = a.prepare_context(f.cat, f.assessment, other_context,
                                  b"generated-export-key-not-secret!", f.descriptors)
        second = adapter.QueryInput(**f.options(plan=other))
        self.assertTrue(set(bridge._aliases).isdisjoint(second._aliases))
        bundle.close()
        second._bundle.close()

    def test_conditions_authority_assessment_and_ontology_rejected_before_reads(self):
        f = self.f
        mutations = [
            {"export_authority": object()},
            {"limits": dataclasses.replace(f.limits, max_actions=24)},
            {"export_plan": dataclasses.replace(f.plan, assessment_digest="f"*64)},
            {"export_plan": dataclasses.replace(f.plan, label_order=tuple(reversed(f.labels)))},
            {"export_plan": dataclasses.replace(f.plan, context=dataclasses.replace(f.context, condition="C_only"))},
            {"export_plan": dataclasses.replace(f.plan, context=dataclasses.replace(f.context, condition="spatial_scrambled"))},
        ]
        for changes in mutations:
            with self.subTest(fields=list(changes)):
                bundle = f.bundle(); options = f.options(bundle=bundle); options.update(changes)
                with self.assertRaises((adapter.InputError, custody.CustodyError)):
                    adapter.QueryInput(**options)
                self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
                bundle.close()

    def test_complete_partition_labels_and_display_collision_fail_closed(self):
        f = self.f
        wrong = list(f.plan.query_map)
        wrong[0] = (*wrong[0][:2], (wrong[0][2]+1) % 25)
        mutations = [dataclasses.replace(f.plan, query_map=f.plan.query_map[:-1]),
                     dataclasses.replace(f.plan, query_map=tuple(wrong)),
                     dataclasses.replace(f.plan, training_map=f.plan.training_map[:-1])]
        for plan in mutations:
            bundle = f.bundle()
            with self.assertRaises(adapter.InputError):
                adapter.QueryInput(**f.options(bundle=bundle, plan=plan))
            self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
            bundle.close()
        bundle = f.bundle()
        with mock.patch.object(adapter, "_display_key", return_value="a"*32):
            with self.assertRaisesRegex(adapter.InputError, "collision"):
                adapter.QueryInput(**f.options(bundle=bundle))
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
        bundle.close()

    def test_conversion_inventory_geometry_count_and_unit_joins(self):
        f = self.f
        cases = [dict(spatial_units="inferred-mm"), dict(records=74), dict(canonical_bytes=2048),
                 dict(catalogue_digest="a"*64), dict(inventory={"bytes": 1,"sha256":"b"*64}),
                 dict(unit_conversion_performed=True), dict(deployment_enabled=True)]
        for change in cases:
            bundle = f.bundle(); result = f.result(); result.update(change)
            with self.assertRaises(adapter.InputError):
                adapter.QueryInput(**f.options(bundle=bundle, result=result))
            self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
            bundle.close()
        bundle = f.bundle(); result = f.result(); result["geometry"]["affine"][3] += 1
        with self.assertRaises(adapter.InputError):
            adapter.QueryInput(**f.options(bundle=bundle, result=result))
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
        bundle.close()
        bridge = adapter.QueryInput(**f.options(result=f.result("unknown")))
        self.assertEqual(bridge.dispatch({"action":"describe"})["spatial_units"], "unknown")
        bridge._bundle.close()

    def test_pinned_metadata_and_decoder_identity_refused_before_array_reads(self):
        f = self.f
        for field in ("converter_contract", "conversion_result"):
            bundle = f.bundle(); options = f.options(bundle=bundle); options[field] += b" "
            with self.assertRaises(adapter.InputError):
                adapter.QueryInput(**options)
            self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
            bundle.close()
        bundle = f.bundle(); options = f.options(bundle=bundle)
        options["inventory_pin"]["sha256"] = "e"*64
        with self.assertRaises(adapter.InputError):
            adapter.QueryInput(**options)
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
        bundle.close()
        bundle = f.bundle(); receipts = dict(bundle.original_receipts)
        first = next(iter(receipts)); receipts[first] = dataclasses.replace(receipts[first], decoder_contract_digest="e"*64)
        changed = dataclasses.replace(bundle, original_receipts=MappingProxyType(receipts))
        with self.assertRaises(adapter.InputError):
            adapter.QueryInput(**f.options(bundle=changed))
        self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 0)
        bundle.close()

    def test_real_canonical_reader_rejects_changed_body_and_sanitizes_error(self):
        f = self.f
        bundle = f.bundle(); bridge = adapter.QueryInput(**f.options(bundle=bundle))
        try:
            f.path.write_bytes(b"x"*len(f.body)); f.fixture_written_bytes += len(f.body)
            with self.assertRaisesRegex(v.ViewerError, "^operator map unavailable$"):
                bridge.dispatch({"action":"describe"})
            self.assertEqual(bundle.values_by_id.ledger.actual_bytes, 2048)
            self.assertEqual(bundle.values_by_id.ledger.attempts[0]["status"], "failed")
        finally:
            f.path.write_bytes(f.body); f.fixture_written_bytes += len(f.body)
            bundle.close()

    def test_backing_owner_stays_reserved_until_escaped_map_is_released(self):
        f = self.f
        bundle = f.bundle(); bridge = adapter.QueryInput(**f.options(bundle=bundle))
        seen = []
        original = c.CanonicalMapping.__getitem__
        def observe(mapping, key):
            values = original(mapping, key); seen.append(weakref.ref(values)); return values
        with mock.patch.object(c.CanonicalMapping, "__getitem__", observe):
            volume = bridge._load(bridge._aliases[0])
        self.assertIs(volume.body, seen[0]()._raw)
        bundle.close(); gc.collect()
        self.assertIsNotNone(seen[0]())
        before = bundle.values_by_id.workspace.live
        self.assertGreaterEqual(before, len(f.body))
        del volume; gc.collect()
        self.assertIsNone(seen[0]())
        self.assertEqual(before - bundle.values_by_id.workspace.live, len(f.body))


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0], *UNITTEST])
