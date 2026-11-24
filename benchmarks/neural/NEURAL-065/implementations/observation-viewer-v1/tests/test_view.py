"""Generated observations only; no neural/model or browser qualification."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("neural065_view", ROOT / "view.py")
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def fixture(root):
    manifests, queries, original = [], [], {}
    for source_no, ids in enumerate((["a" * 32, "b" * 32], ["c" * 32])):
        source = root / ("source" + str(source_no)); source.mkdir(); (source / "assets").mkdir()
        rows = []
        for index, qid in enumerate(ids):
            values = [source_no + index + .125, -2e-6, 3e-6, -4e-6, 5e-6, 6e-6]
            raw = struct.pack("<6d", *values); original[qid] = raw
            path = "assets/" + qid + ".f64le"; (source / path).write_bytes(raw)
            rows.append({"query_id": qid, "neural_asset_sha256": sha(raw), "path": path, "bytes": len(raw), "shape": [3, 2]})
            queries.append({"query_id": qid, "neural_asset_sha256": sha(raw)})
        metadata = {"schema_version": 1, "task_id": v.TASK_ID, "modality": "EEG", "dtype": "float64",
                    "byte_order": "little", "axes": ["time", "channel"], "unit": "V", "sampling_frequency_hz": 500,
                    "time_origin_s": 0, "time_coordinate": v.TIME_COORDINATE,
                    "channel_ids": ["EEG000", "EEG001"], "observations": rows}
        manifest = source / "observations.json"; manifest.write_bytes(v.json_bytes(metadata))
        manifests.append([manifest, sha(manifest.read_bytes())])
    # Deliberately different query order from source order; retain evaluator order.
    public = {"schema_version": 1, "task_id": v.TASK_ID, "packet_sha256": "4" * 64, "queries": [queries[2], queries[0], queries[1]]}
    query_path = root / "queries.json"; query_path.write_bytes(v.json_bytes(public))
    return {"queries_path": query_path, "queries_sha256": sha(query_path.read_bytes()), "observations": manifests,
            "output": root / "view", "max_input_bytes": 100000, "max_output_bytes": 100000}, original


def edit_manifest(args, edit, index=0):
    path = args["observations"][index][0]; obj = json.loads(path.read_bytes()); edit(obj)
    path.write_bytes(v.json_bytes(obj)); args["observations"][index][1] = sha(path.read_bytes())


def edit_queries(args, edit):
    path = args["queries_path"]; obj = json.loads(path.read_bytes()); edit(obj)
    path.write_bytes(v.json_bytes(obj)); args["queries_sha256"] = sha(path.read_bytes())


class ViewerControls(unittest.TestCase):
    def test_complete_two_source_export_preserves_exact_binary_and_coordinates(self):
        with tempfile.TemporaryDirectory() as folder:
            args, original = fixture(Path(folder)); result = v.export(**args)
            out = args["output"]; receipt_bytes = (out / "collection.json").read_bytes(); receipt = json.loads(receipt_bytes)
            self.assertEqual(result["queries"], 3); self.assertEqual(result["collection_sha256"], sha(receipt_bytes))
            self.assertEqual(result["output_bytes"], sum(path.stat().st_size for path in out.iterdir()))
            self.assertEqual([row["path"] for row in receipt["files"]], ["c" * 32 + ".html", "a" * 32 + ".html", "b" * 32 + ".html", "index.html"])
            for row in receipt["files"]:
                raw = (out / row["path"]).read_bytes(); self.assertEqual(sha(raw), row["sha256"]); self.assertEqual(len(raw), row["bytes"])
            for qid, raw in original.items():
                page = (out / (qid + ".html")).read_text()
                payload = json.loads(re.search(r'<script id="observation" type="application/json">(.*?)</script>', page, re.S)[1])
                self.assertEqual(base64.b64decode(payload["data_base64"]), raw)
                self.assertEqual(payload["shape"], [3, 2]); self.assertEqual(payload["sampling_frequency_hz"], 500)
                self.assertEqual(payload["channel_ids"], ["EEG000", "EEG001"])
                self.assertNotIn(str(Path(folder)), page)
                for secret in ("source0", "source1", "target_text", "template_text", "recording_subject", "session_id"):
                    self.assertNotIn(secret, page)
            self.assertEqual(len(list(out.iterdir())), 5)

    def test_missing_duplicate_and_mismatched_query_support_fail_closed(self):
        edits = [lambda a: a["observations"].pop(),
                 lambda a: a["observations"].append(a["observations"][0]),
                 lambda a: edit_queries(a, lambda obj: obj["queries"][0].update(neural_asset_sha256="0" * 64)),
                 lambda a: edit_queries(a, lambda obj: obj["queries"].append(copy.deepcopy(obj["queries"][0]))),
                 lambda a: edit_queries(a, lambda obj: obj["queries"].append({"query_id": "d" * 32, "neural_asset_sha256": "1" * 64}))]
        for edit in edits:
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as folder:
                args, _ = fixture(Path(folder)); edit(args)
                with self.assertRaises(v.ViewError): v.export(**args)
                self.assertFalse(args["output"].exists()); self.assertFalse(list(Path(folder).glob(".neural065-view-*")))

    def test_nonquery_observations_never_read_or_exported(self):
        with tempfile.TemporaryDirectory() as folder:
            args, _ = fixture(Path(folder))
            # Preparation may include training/calibration windows, but this is query-only.
            edit_queries(args, lambda obj: obj.update(queries=[obj["queries"][0]]))
            (args["observations"][0][0].parent / "assets" / ("a" * 32 + ".f64le")).unlink()
            result = v.export(**args)
            self.assertEqual(result["queries"], 1)
            self.assertEqual(sorted(p.name for p in args["output"].iterdir()), ["c" * 32 + ".html", "collection.json", "index.html"])

    def test_target_fields_paths_shapes_units_and_channels_are_refused(self):
        edits = [lambda obj: obj.update(target_text="hidden"),
                 lambda obj: obj["observations"][0].update(path="../private/targets.json"),
                 lambda obj: obj["observations"][0].update(path="assets/answer.f64le"),
                 lambda obj: obj["observations"][0].update(bytes=47),
                 lambda obj: obj["observations"][0].update(shape=[3, 1]),
                 lambda obj: obj["observations"][0].update(shape=[True, 2]),
                 lambda obj: obj.update(channel_ids=["Fp1", "secret transcript"]),
                 lambda obj: obj.update(axes=["channel", "time"]),
                 lambda obj: obj.update(unit="uV"),
                 lambda obj: obj.update(sampling_frequency_hz=0),
                 lambda obj: obj.update(sampling_frequency_hz=1e-323),
                 lambda obj: obj.update(sampling_frequency_hz=10**400),
                 lambda obj: obj.update(time_origin_s=10),
                 lambda obj: obj.update(modality="MEG")]
        for edit in edits:
            with self.subTest(edit=edit), tempfile.TemporaryDirectory() as folder:
                args, _ = fixture(Path(folder)); edit_manifest(args, edit)
                with self.assertRaises(v.ViewError): v.export(**args)
                self.assertFalse(args["output"].exists())
        with tempfile.TemporaryDirectory() as folder:
            args, _ = fixture(Path(folder)); edit_queries(args, lambda obj: obj["queries"][0].update(target_classes=[1]))
            with self.assertRaises(v.ViewError): v.export(**args)

    def test_asset_tampering_nonfinite_and_partial_byte_outputs_refused(self):
        for kind in ("tamper", "nan", "short"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                args, _ = fixture(Path(folder)); path = args["observations"][1][0].parent / "assets" / ("c" * 32 + ".f64le")
                raw = path.read_bytes()
                changed = raw[:-1] if kind == "short" else struct.pack("<d", float("nan") if kind == "nan" else 1.0) + raw[8:]
                path.write_bytes(changed)
                if kind != "tamper":
                    edit_manifest(args, lambda obj: obj["observations"][0].update(neural_asset_sha256=sha(changed)), 1)
                    edit_queries(args, lambda obj: obj["queries"][0].update(neural_asset_sha256=sha(changed)))
                with self.assertRaises(v.ViewError): v.export(**args)
                self.assertFalse(args["output"].exists()); self.assertFalse(list(Path(folder).glob(".neural065-view-*")))

    def test_input_output_budgets_and_existing_output_are_preserved(self):
        for key in ("max_input_bytes", "max_output_bytes"):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as folder:
                args, _ = fixture(Path(folder)); args[key] = 10
                with self.assertRaisesRegex(v.ViewError, "byte limit"): v.export(**args)
                self.assertFalse(args["output"].exists()); self.assertFalse(list(Path(folder).glob(".neural065-view-*")))
        with tempfile.TemporaryDirectory() as folder:
            args, _ = fixture(Path(folder)); v.export(**args); before = (args["output"] / "collection.json").read_bytes()
            with self.assertRaisesRegex(v.ViewError, "already exists"): v.export(**args)
            self.assertEqual((args["output"] / "collection.json").read_bytes(), before)

    def test_symlink_asset_and_directory_are_refused(self):
        for kind in ("file", "directory"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as folder:
                args, _ = fixture(Path(folder)); assets = args["observations"][0][0].parent / "assets"
                if kind == "file":
                    path = assets / ("a" * 32 + ".f64le"); path.rename(assets / "original"); path.symlink_to(assets / "original")
                else:
                    assets.rename(assets.with_name("elsewhere")); assets.symlink_to(assets.with_name("elsewhere"), target_is_directory=True)
                with self.assertRaises((OSError, v.ViewError)): v.export(**args)
                self.assertFalse(args["output"].exists())

    def test_cli_success_and_failure_and_strict_json(self):
        with tempfile.TemporaryDirectory() as folder:
            args, _ = fixture(Path(folder)); cli = ["view.py", "--queries", str(args["queries_path"]), "--queries-sha256", args["queries_sha256"], "--output", str(args["output"]), "--max-input-bytes", "100000", "--max-output-bytes", "100000"]
            for path, pin in args["observations"]: cli.extend(["--observations", str(path), pin])
            output = io.StringIO()
            with mock.patch.object(sys, "argv", cli), contextlib.redirect_stdout(output): v.main()
            self.assertEqual(json.loads(output.getvalue())["queries"], 3)
            with mock.patch.object(sys, "argv", cli), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught: v.main()
            self.assertEqual(caught.exception.code, 2)
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b'[' * 1500 + b']' * 1500):
            with self.subTest(raw=raw[:20]), self.assertRaises(v.ViewError): v.parse_json(raw)


if __name__ == "__main__":
    unittest.main()
