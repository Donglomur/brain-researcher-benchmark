"""Generated source-format controls; no authentic recording or stimulus input."""
from contextlib import contextmanager
import argparse
import copy
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import tempfile
import unittest
import sys
from types import SimpleNamespace
from unittest.mock import patch

import h5py
import numpy as np

spec = importlib.util.spec_from_file_location("presentation_content", Path(__file__).with_name("presentation_content.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
MATERIALS_JOIN = Path(__file__).parent.parent / "materials-join-v1" / "materials_join.py"


def manifest():
    return {"schema": "zuco2-presentation-content-input/v1", "containers": [
        {"person": p, "condition": c, "path": f"/generated/{p}_{c}.mat", "bytes": 100,
         "sha256": "a" * 64, "sentence_group": "/sentenceData", "content_field": "content"}
        for p in module.PEOPLE for c in module.CONDITIONS]}


@contextmanager
def hdf(condition="NR", text='A "quoted" sentence; \U0001f9e0'):
    # Fileobj fixture lives only in RAM; no physiological array is present.
    stream = io.BytesIO()
    with h5py.File(stream, "w") as h:
        group = h.create_group("sentenceData")
        char = h.create_dataset("text", data=np.frombuffer(text.encode("utf-16-le"), dtype="<u2").reshape(-1, 1))
        char.attrs["MATLAB_class"] = np.bytes_("char")
        column = group.create_dataset("content", (module.COUNTS[condition], 1), dtype=h5py.ref_dtype)
        column[:] = char.ref
        # This deliberately unusable external rawData link must never be opened.
        group["rawData"] = h5py.ExternalLink("/definitely-unavailable/EEG.h5", "/waveform")
        row = manifest()["containers"][0].copy()
        row["condition"] = condition
        yield h, row, char


class ContentProjectionTests(unittest.TestCase):
    def test_exact_full_cohort_and_byte_ceiling_precede_io(self):
        d = manifest()
        rows = module.validate_manifest(d, 3600)
        self.assertEqual(len(rows), 36)
        with self.assertRaisesRegex(module.ContentError, "ceiling"):
            module.validate_manifest(d, 3599)
        for bad in (True, 0, -1):
            with self.assertRaises(module.ContentError):
                module.validate_manifest(d, bad)
        for mutate in (lambda x: x["containers"].pop(),
                       lambda x: x["containers"].__setitem__(1, x["containers"][0]),
                       lambda x: x["containers"][0].update(person="OTHER"),
                       lambda x: x["containers"][1].update(path=x["containers"][0]["path"]),
                       lambda x: x["containers"][0].update(answer="NR")):
            bad = copy.deepcopy(d); mutate(bad)
            with self.assertRaises(module.ContentError):
                module.validate_manifest(bad, 3600)

    def test_unsafe_manifest_paths_and_noncanonical_numbers(self):
        d = manifest()
        for key, value in (("path", "relative.mat"), ("path", "/data/../x.mat"),
                           ("sentence_group", "/sentenceData/../labels"),
                           ("content_field", "a/content"), ("sha256", "A" * 64), ("bytes", True)):
            bad = copy.deepcopy(d); bad["containers"][0][key] = value
            with self.assertRaises(module.ContentError):
                module.validate_manifest(bad, 3600)
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(module.ContentError):
                module.parse_json(raw)

    def test_complete_sentence_columns_preserve_literal_utf16_and_repeats(self):
        for condition in module.CONDITIONS:
            text = '  A "quoted" sentence; \U0001f9e0\t'
            with hdf(condition, text) as (h, row, _):
                result = module.project_hdf5(h, row)
            self.assertEqual(len(result["presentations"]), module.COUNTS[condition])
            self.assertEqual([x["source_index"] for x in result["presentations"]], list(range(module.COUNTS[condition])))
            self.assertTrue(all(x["text"] == text for x in result["presentations"]))
            self.assertEqual(set(result), {"person", "condition", "source_bytes", "source_sha256", "presentations"})

    def test_null_and_wrong_shape_reference_columns_refused(self):
        with hdf() as (h, row, _):
            h["sentenceData/content"][12, 0] = h5py.Reference()
            with self.assertRaisesRegex(module.ContentError, "null"):
                module.project_hdf5(h, row)
        with hdf() as (h, row, char):
            del h["sentenceData/content"]
            d = h["sentenceData"].create_dataset("content", (1, module.COUNTS["NR"]), dtype=h5py.ref_dtype)
            d[:] = char.ref
            with self.assertRaisesRegex(module.ContentError, "column"):
                module.project_hdf5(h, row)

    def test_soft_external_and_virtual_content_paths_refused(self):
        with hdf() as (h, row, _):
            del h["sentenceData/content"]
            h["sentenceData/content"] = h5py.SoftLink("/text")
            with self.assertRaisesRegex(module.ContentError, "links"):
                module.project_hdf5(h, row)
        with hdf() as (h, row, _):
            del h["sentenceData/content"]
            h["sentenceData/content"] = h5py.ExternalLink("/missing.mat", "/content")
            with self.assertRaisesRegex(module.ContentError, "links"):
                module.project_hdf5(h, row)
        with hdf() as (h, row, _):
            layout = h5py.VirtualLayout(shape=(2, 1), dtype="u2")
            layout[:] = h5py.VirtualSource("/missing.mat", "/text", shape=(2, 1))
            d = h.create_virtual_dataset("virtual_text", layout)
            d.attrs["MATLAB_class"] = np.bytes_("char")
            h["sentenceData/content"][:] = d.ref
            with self.assertRaisesRegex(module.ContentError, "virtual"):
                module.project_hdf5(h, row)

    def test_utf16_type_size_class_and_invalid_surrogate_refused(self):
        for field in ("type", "size", "class", "surrogate", "nul"):
            with hdf() as (h, row, char):
                if field == "class":
                    char.attrs["MATLAB_class"] = np.bytes_("double")
                else:
                    values = {"type": np.array([[65]], dtype="u4"),
                              "size": np.zeros((module.MAX_CODE_UNITS + 1, 1), dtype="u2"),
                              "surrogate": np.array([[0xD800]], dtype="u2"),
                              "nul": np.array([[0]], dtype="u2")}[field]
                    d = h.create_dataset("invalid_text", data=values)
                    d.attrs["MATLAB_class"] = np.bytes_("char")
                    h["sentenceData/content"][:] = d.ref
                with self.assertRaises((module.ContentError, UnicodeDecodeError)):
                    module.project_hdf5(h, row)

    def test_authentication_tampering_symlinks_and_inode_reuse(self):
        with tempfile.TemporaryDirectory() as td:
            td = str(Path(td).resolve())
            p = Path(td) / "source.mat"; raw = b"generated file for pin checks"
            p.write_bytes(raw)
            row = {"path": str(p), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            observed = set()
            with module.authenticated_file(row, observed) as f:
                self.assertEqual(f.read(), raw)
            with self.assertRaisesRegex(module.ContentError, "reused"):
                with module.authenticated_file(row, observed): pass
            bad = dict(row, sha256="0" * 64)
            with self.assertRaisesRegex(module.ContentError, "mismatch"):
                with module.authenticated_file(bad, set()): pass
            link = Path(td) / "link.mat"; link.symlink_to(p)
            with self.assertRaisesRegex(module.ContentError, "symlink"):
                with module.authenticated_file(dict(row, path=str(link)), set()): pass
            with self.assertRaisesRegex(module.ContentError, "changed"):
                with module.authenticated_file(row, set()):
                    p.write_bytes(raw + b"x")

    def test_complete_metadata_cohort_schema_and_no_partial_support(self):
        calls = []
        def generated(row, _observed):
            calls.append((row["person"], row["condition"]))
            return {"person": row["person"], "condition": row["condition"],
                    "source_bytes": row["bytes"], "source_sha256": row["sha256"],
                    "presentations": [{"source_index": i, "text": f"generated {row['condition']} {i}"}
                                      for i in range(module.COUNTS[row["condition"]])]}
        with patch.object(module, "project_container", side_effect=generated):
            result = module.project_cohort(manifest(), 3600)
        self.assertEqual(len(calls), 36)
        self.assertEqual(sum(len(c["presentations"]) for c in result["containers"]), 13302)
        self.assertEqual(set(result), {"schema", "containers"})
        with patch.object(module, "project_container", side_effect=generated), patch.object(module, "MAX_TEXT_BYTES", 1):
            with self.assertRaisesRegex(module.ContentError, "no partial"):
                module.project_cohort(manifest(), 3600)
        with patch.object(module, "project_container", side_effect=module.ContentError("missing original")):
            with self.assertRaisesRegex(module.ContentError, "missing original"):
                module.project_cohort(manifest(), 3600)

    def test_authenticated_file_to_hdf5_projection(self):
        with hdf() as (h, row, _):
            h.flush()
            image = h.id.get_file_image()
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "generated.mat"
            p.write_bytes(image)
            self.assertLess(len(image), 32768)
            row.update(path=str(p), bytes=len(image), sha256=hashlib.sha256(image).hexdigest())
            result = module.project_container(row, set())
            self.assertEqual(len(result["presentations"]), 349)
            self.assertEqual(result["presentations"][0]["text"], 'A "quoted" sentence; \U0001f9e0')

    def test_output_is_accepted_by_existing_complete_material_join(self):
        raw = MATERIALS_JOIN.read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), "f52f8136ce62eca4960b8a8442ffa7b36f2220cdd19996f3cddb7ea9f8f2c619")
        s = importlib.util.spec_from_file_location("materials_join", MATERIALS_JOIN)
        join = importlib.util.module_from_spec(s); s.loader.exec_module(join)
        def text(c, i):
            return f"shared generated {i}" if i < 40 else f"generated {c} {i}"
        def generated(row, _observed):
            return {"person": row["person"], "condition": row["condition"],
                    "source_bytes": row["bytes"], "source_sha256": row["sha256"],
                    "presentations": [{"source_index": i, "text": text(row["condition"], i)}
                                      for i in range(module.COUNTS[row["condition"]])]}
        materials = [{"condition": c, "text": text(c, i), "source_record_id": f"generated-{c}-{i}",
                      "legacy_prefix": False} for c in module.CONDITIONS for i in range(module.COUNTS[c])]
        with patch.object(module, "project_container", side_effect=generated):
            content = module.project_cohort(manifest(), 3600)
        result = join.join_presentations(materials, content)
        self.assertEqual(result["presentations"], 13302)
        self.assertEqual(len(result["containers"]), 36)
        self.assertTrue(result["all_content_joins_unique"])
        self.assertEqual(len(result["observed_exact_shared_items"]), 40)
        self.assertIs(result["source_extraction_custody_verified"], False)
        self.assertIs(result["paper_duplicate_obligations_reconciled"], False)

    def test_attribute_metadata_refused_before_value_materialization(self):
        invalid = (np.array([b"char", b"char"], dtype="S4"), np.bytes_(b"x" * 1024),
                   "char", np.array([b"char"] * 128, dtype="S4"))
        for value in invalid:
            with hdf() as (h, row, char):
                del char.attrs["MATLAB_class"]
                char.attrs["MATLAB_class"] = value
                with patch.object(h5py.AttributeManager, "__getitem__",
                                  side_effect=AssertionError("attribute value was materialized")):
                    with self.assertRaisesRegex(module.ContentError, "fixed-length"):
                        module.project_hdf5(h, row)
        with hdf() as (h, row, char):
            del char.attrs["MATLAB_class"]
            with self.assertRaisesRegex(module.ContentError, "binding"):
                module.project_hdf5(h, row)
        with hdf() as (h, row, _):
            self.assertEqual(len(module.project_hdf5(h, row)["presentations"]), 349)

    def test_manifest_read_bound_and_oversized_descriptor_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "manifest.json"
            p.write_bytes(b"{}")
            self.assertEqual(module.read_manifest(p), b"{}")
            with patch.object(module.os, "fstat", return_value=SimpleNamespace(st_mode=0o100600, st_size=65537)), \
                 patch.object(module.os, "fdopen", side_effect=AssertionError("oversized file was read")):
                with self.assertRaisesRegex(module.ContentError, "bounded regular"):
                    module.read_manifest(p)
            calls = []
            class GrownSource:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, count):
                    calls.append(count)
                    return b"x" * count
            with patch.object(module.os, "fdopen", return_value=GrownSource()):
                with self.assertRaisesRegex(module.ContentError, "bounded read"):
                    module.read_manifest(p)
            self.assertEqual(calls, [65537])
            link = p.parent / "link.json"; link.symlink_to(p)
            with self.assertRaisesRegex(module.ContentError, "ordinary"):
                module.read_manifest(link)

    def test_fifo_sources_and_manifests_refuse_before_blocking_read(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td).resolve() / "not-a-regular-file"
            os.mkfifo(p)
            row = {"path": str(p), "bytes": 1, "sha256": "a" * 64}
            with self.assertRaisesRegex(module.ContentError, "regular file"):
                with module.authenticated_file(row, set()): pass
            with self.assertRaisesRegex(module.ContentError, "regular input manifest"):
                module.read_manifest(p)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--materials-join", type=Path, default=MATERIALS_JOIN)
    args, remaining = parser.parse_known_args()
    MATERIALS_JOIN = args.materials_join
    unittest.main(argv=[sys.argv[0], *remaining])
