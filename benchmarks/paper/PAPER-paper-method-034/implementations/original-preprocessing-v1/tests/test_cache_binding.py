"""Independent bounded generated cache controls; no authentic data is opened."""
from __future__ import annotations

import copy
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
for name in ("inputs", "cache"):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
inputs, cache = sys.modules["inputs"], sys.modules["cache"]
GENERATED_BYTES_WRITTEN = 0
GENERATED_BYTES_RECLAIMED = 0


def write_generated(path, body):
    global GENERATED_BYTES_WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    GENERATED_BYTES_WRITTEN += len(body)


SMALL_LAYOUTS = {
    rat: {"neural": ((rows, channels), (channels, 1), 0, rows * channels),
          "continuous_index": ((rows, 3), (3, 1), 0, rows * 3)}
    for rat, rows, channels in (("achilles", 10, 3), ("buddy", 9, 2),
                               ("cicero", 8, 4), ("gatsby", 7, 5))
}


@contextmanager
def reduced_fixture():
    """Explicit generated-only geometry; never represents original full support."""
    global GENERATED_BYTES_RECLAIMED
    before = GENERATED_BYTES_WRITTEN
    try:
        with tempfile.TemporaryDirectory(prefix="marble-generated-cache-") as name:
            root = Path(name)
            with mock.patch.object(inputs, "LAYOUTS", SMALL_LAYOUTS):
                arrays, declarations = {}, []
                for ri, rat in enumerate(inputs.RATS):
                    rows, channels = SMALL_LAYOUTS[rat]["neural"][0]
                    neural = (np.arange(rows * channels, dtype="<f4").reshape(rows, channels) - 11) / 8
                    neural[0, 0] = np.float32(-0.0)
                    labels = (np.arange(rows * 3, dtype="<f4").reshape(rows, 3) + 2 * ri) / 4
                    arrays[rat] = {"neural": neural, "continuous_index": labels}
                    cut = int(rows * 0.8)
                    items = [(f"private/labels/{rat}.npy", labels),
                        (f"public/input/clean-{rat}-train.npy", neural[:cut]),
                        (f"public/input/clean-{rat}-test.npy", neural[cut:])]
                    for path, values in items:
                        body = generated_npy(values, shape=values.shape)
                        write_generated(root / path, body)
                        declarations.append({"path": path, "bytes": len(body),
                            "sha256": hashlib.sha256(body).hexdigest(),
                            "shape": list(values.shape), "dtype": "float32"})
                # The real predecessor also declares half-neuron extensions.
                # A declared-but-absent extra file must never be read here.
                declarations.append({"path": "public/input/half-achilles-train.npy",
                    "bytes": 100, "sha256": "0" * 64, "shape": [8, 2], "dtype": "float32"})
                assets = {"schema": "marble_preparation_v1", "input_sha256": inputs.SOURCE_SHA256,
                          "files": declarations}
                write_assets(root, assets)
                yield root, arrays, assets
            self_removed_path = root
        if self_removed_path.exists():
            raise AssertionError("generated cache fixture was not reclaimed")
    finally:
        GENERATED_BYTES_RECLAIMED += GENERATED_BYTES_WRITTEN - before


def write_assets(root, document):
    write_generated(root / "private/ASSETS.json", (json.dumps(document, sort_keys=True) + "\n").encode())


def generated_npy(values=None, *, shape=(3, 2), version=(1, 0),
                  descr="<f4", fortran=False, literal=None, suffix=b""):
    """Small independent writer; no np.save/load path is shared with producer."""
    if values is None:
        values = np.arange(np.prod(shape), dtype="<f4").reshape(shape)
    payload = np.asarray(values, dtype="<f4").tobytes(order="C")
    if literal is None:
        literal = repr({"descr": descr, "fortran_order": fortran, "shape": shape})
    size_format = "<H" if version == (1, 0) else "<I"
    prefix_size = 8 + struct.calcsize(size_format)
    header = literal.encode("latin1")
    padding = (-prefix_size - len(header) - 1) % 16
    header += b" " * padding + b"\n"
    return (b"\x93NUMPY" + bytes(version) + struct.pack(size_format, len(header))
            + header + payload + suffix)


class HeaderControls(unittest.TestCase):
    def test_independent_npy_versions_one_and_two_are_header_only(self):
        for version in ((1, 0), (2, 0)):
            body = generated_npy(version=version)
            with mock.patch.object(np, "load", side_effect=AssertionError("no array decode")):
                with mock.patch.object(np, "frombuffer", side_effect=AssertionError("header only")):
                    result = cache.inspect_npy(body, (3, 2))
            self.assertIsInstance(result, dict)
            self.assertEqual(list(result["shape"]), [3, 2])

    def test_wrong_magic_version_truncation_extent_and_trailing_bytes_refused(self):
        good = generated_npy()
        failures = (b"not NPY", b"\x93NUMPY\x03\x00" + good[8:],
                    b"\x93NUMPY\x01\x01" + good[8:], good[:9],
                    good[:-1], good + b"\0", good.replace(b"NUMPY", b"NUMPX", 1))
        for body in failures:
            with self.subTest(size=len(body), prefix=body[:10]):
                with self.assertRaises((ValueError, TypeError)):
                    cache.inspect_npy(body, (3, 2))

    def test_exact_dtype_order_shape_and_dictionary_keys_required(self):
        failures = [generated_npy(descr=descr) for descr in ("f4", ">f4", "<f8", "|O", "<i4")]
        failures += [generated_npy(fortran=True), generated_npy(fortran=0),
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':(True,6)}"),
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':[3,2]}"),
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':(3,2),'extra':1}"),
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':(3,2),'shape':(3,2)}"),
            generated_npy(literal="{'descr':'<f4','shape':(3,2)}"),
            generated_npy(literal="dict(descr='<f4',fortran_order=False,shape=(3,2))")]
        for body in failures:
            with self.subTest(header=body[10:130]):
                with self.assertRaises((ValueError, TypeError)):
                    cache.inspect_npy(body, (3, 2))
        with self.assertRaises((ValueError, TypeError)):
            cache.inspect_npy(generated_npy(), (2, 3))

    def test_huge_declared_header_shape_or_nested_expression_refused(self):
        failures = [b"\x93NUMPY\x02\x00" + struct.pack("<I", 2**31) + b"\n",
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':(10**30,2)}"),
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':(-3,2)}"),
            generated_npy(literal="{'descr':'<f4','fortran_order':False,'shape':(0,2)}")]
        for body in failures:
            with self.assertRaises((ValueError, TypeError)):
                cache.inspect_npy(body, (3, 2))


class CacheBindingControls(unittest.TestCase):
    def test_exact_original_twelve_file_roles_and_row_intervals(self):
        rows = cache.expected_files()
        self.assertEqual(len(rows), 12)
        self.assertEqual(len({row["path"] for row in rows}), 12)
        original = {"achilles": (10000, 120, 8000), "buddy": (6577, 48, 5261),
                    "cicero": (10000, 55, 8000), "gatsby": (10000, 66, 8000)}
        by_path = {row["path"]: row for row in rows}
        for rat, (n, channels, cut) in original.items():
            label = by_path[f"private/labels/{rat}.npy"]
            self.assertEqual(label["shape"], [n, 3])
            self.assertEqual(label["source_row_interval"], [0, n])
            self.assertEqual(label["role"], "operator_private_labels")
            for segment, start, stop in (("train", 0, cut), ("test", cut, n)):
                neural = by_path[f"public/input/clean-{rat}-{segment}.npy"]
                self.assertEqual(neural["shape"], [stop - start, channels])
                self.assertEqual(neural["source_row_interval"], [start, stop])
                self.assertEqual(neural["role"], "participant_neural_input")

    def test_generated_inventory_is_header_only_and_not_source_attestation(self):
        with reduced_fixture() as (root, arrays, assets):
            with mock.patch.object(np, "frombuffer", side_effect=AssertionError("metadata only")):
                with mock.patch.object(np, "load", side_effect=AssertionError("metadata only")):
                    inventory = cache.inspect_cache(root)
            self.assertEqual(len(inventory["files"]), 12)
            self.assertFalse(inventory["source_binding_verified"])
            self.assertFalse(inventory["numeric_values_decoded"])
            self.assertFalse(inventory["half_neuron_files_read"])
            self.assertFalse(inventory["label_isolation_verified"])
            self.assertEqual(inventory["file_bytes_hashed"], sum(row["bytes"] for row in inventory["files"]))
            self.assertEqual(inventory["assets_sha256"], hashlib.sha256((root / "private/ASSETS.json").read_bytes()).hexdigest())

    def test_generated_complete_binding_preserves_every_row_and_creates_no_files(self):
        with reduced_fixture() as (root, arrays, assets):
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            inventory = cache.inspect_cache(root)
            # Explicitly generated in-process object injection; not read_release.
            result = cache.bind_cache(root, inputs.SourceViews(arrays), inventory)
            self.assertTrue(result["source_binding_verified"])
            self.assertEqual(result["complete_original_views"], 8)
            self.assertEqual(result["new_numeric_files_written"], 0)
            self.assertFalse(result["figure5d_2000_query_eligible"])
            self.assertFalse(result["historical_source_qualified"])
            self.assertFalse(result["smoothing_PCA_models_or_scoring_run"])
            self.assertFalse(result["label_isolation_verified"])
            for row in result["files"]:
                start, stop = row["source_row_interval"]
                self.assertTrue(row["bitwise_original_view_match"])
                self.assertEqual(row["first_row_id"], inputs.row_id(row["rat"], start))
                self.assertEqual(row["last_row_id"], inputs.row_id(row["rat"], stop - 1))
                self.assertEqual(row["source_layout"]["shape"], list(SMALL_LAYOUTS[row["rat"]][row["source_field"]][0]))
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)

    def test_inventory_schema_missing_duplicate_role_and_shape_declarations_refused(self):
        with reduced_fixture() as (root, arrays, assets):
            bad_assets = []
            for key, value in (("schema", "unknown"), ("input_sha256", "0" * 64), ("files", {})):
                bad_assets.append({**assets, key: value})
            bad_assets += [{**assets, "files": assets["files"][1:]},
                           {**assets, "files": assets["files"] + [assets["files"][0]]}]
            for key, value in (("path", "public/input/labels-achilles.npy"), ("dtype", "object"),
                               ("shape", [3, 10]), ("bytes", True), ("sha256", "G" * 64)):
                bad = copy.deepcopy(assets)
                bad["files"][0][key] = value
                bad_assets.append(bad)
            for document in bad_assets:
                write_assets(root, document)
                with self.assertRaises(inputs.InputError):
                    cache.inspect_cache(root)

    def test_file_hash_or_manifest_pin_change_refused(self):
        with reduced_fixture() as (root, arrays, assets):
            inventory = cache.inspect_cache(root)
            altered = copy.deepcopy(inventory)
            altered["files"][0]["role"] = "participant_neural_input"
            with self.assertRaises(inputs.InputError):
                cache.bind_cache(root, inputs.SourceViews(arrays), altered)
            path = root / assets["files"][0]["path"]
            original = path.read_bytes()
            write_generated(path, original[:-1] + bytes([original[-1] ^ 1]))
            with self.assertRaises(inputs.InputError): cache.inspect_cache(root)
            with self.assertRaises(inputs.InputError):
                cache.bind_cache(root, inputs.SourceViews(arrays), inventory)

    def test_source_mutation_and_arbitrary_untyped_views_refused(self):
        with reduced_fixture() as (root, arrays, assets):
            inventory = cache.inspect_cache(root)
            with self.assertRaises(inputs.InputError): cache.bind_cache(root, arrays, inventory)
            views = inputs.SourceViews(arrays)
            arrays["achilles"]["neural"][0, 0] = 2.0
            with self.assertRaises(inputs.InputError): cache.bind_cache(root, views, inventory)

    def test_declared_valid_cache_with_signed_zero_or_final_row_change_is_not_source_match(self):
        for signed_zero in (True, False):
            with self.subTest(signed_zero=signed_zero):
                with reduced_fixture() as (root, arrays, assets):
                    path = "public/input/clean-achilles-train.npy" if signed_zero else "private/labels/gatsby.npy"
                    values = arrays["achilles"]["neural"][:8].copy() if signed_zero else arrays["gatsby"]["continuous_index"].copy()
                    if signed_zero:
                        values[0, 0] = np.float32(+0.0)
                    else:
                        values[-1, -1] += np.float32(0.25)
                    body = generated_npy(values, shape=values.shape)
                    write_generated(root / path, body)
                    row = next(row for row in assets["files"] if row["path"] == path)
                    row["sha256"] = hashlib.sha256(body).hexdigest()
                    write_assets(root, assets)
                    inventory = cache.inspect_cache(root)
                    with self.assertRaises(inputs.InputError):
                        cache.bind_cache(root, inputs.SourceViews(arrays), inventory)


if __name__ == "__main__":
    try:
        unittest.main()
    finally:
        if os.environ.get("MARBLE_CACHE_ACCOUNTING"):
            Path(os.environ["MARBLE_CACHE_ACCOUNTING"]).write_text(json.dumps({
                "scope": "tiny generated reduced-geometry cache controls; original source never opened",
                "generated_logical_bytes_written": GENERATED_BYTES_WRITTEN,
                "generated_logical_bytes_reclaimed": GENERATED_BYTES_RECLAIMED,
                "retained_generated_bytes": GENERATED_BYTES_WRITTEN - GENERATED_BYTES_RECLAIMED,
                "authentic_payload_decodes": 0,
                "full_original_geometry_exports": 0,
                "scientific_scores_or_fits": 0}, indent=2) + "\n")
