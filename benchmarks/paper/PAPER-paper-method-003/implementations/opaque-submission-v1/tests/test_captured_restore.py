"""Captured prediction custody over all 1,803 generated test events.

No arrays, targets, models, provider dispatch or native processes are used.
The existing complete metadata fixture is reused without running its tests.
"""
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "test_adapter.py"
assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == "de716dd790fa9e6e9456e5e66dfd0ccf1a068813a17dde26fd7734095a1dbbcf"
spec = importlib.util.spec_from_file_location("reve_captured_metadata_fixture", FIXTURE)
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)
a, m = f.a, f.m
CREATED = 0
WRITE_CAP = 5 * 1024**2


def charge(size):
    global CREATED
    CREATED += size
    if CREATED > WRITE_CAP:
        raise AssertionError("generated metadata write allocation exceeded")


def write(path, body):
    charge(len(body))
    path.write_bytes(body)
    path.chmod(0o600)


class CapturedRestoration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="reve-captured-restoration-")
        cls.root = Path(cls.temp.name).resolve()
        cls.private = cls.root / "private"
        cls.packet = cls.root / "packet"
        cls.private.mkdir(mode=0o700)
        cls.packet.mkdir(mode=0o700)
        cls.panel = cls.private / "panel.json"
        cls.mapping = cls.private / "map.json"
        cls.materials = cls.packet / "materials.json"
        for path, document in ((cls.panel, f.PANEL), (cls.mapping, f.MAP), (cls.materials, f.DOCS[0])):
            write(path, m.canonical(document) + b"\n")
        cls.expectations = dict(expected_panel_identity=f.PANEL["panel_identity"],
            expected_mapping_identity=f.MAP["mapping_identity"],
            expected_materials_identity=f.INFOS[0]["materials_identity"])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.output = self.private / (self._testMethodName + ".json")
        self.result_path = self.private / (self._testMethodName + "-result.json")
        original = m._write_private_json

        def metered(path, value):
            charge(len(m.canonical(value)) + 1)
            return original(path, value)

        self.writer = patch.object(m, "_write_private_json", side_effect=metered)
        self.writer.start()
        self.addCleanup(self.writer.stop)

    def submission(self, scores=False):
        rows = []
        for i, record in enumerate(f.MAP["records"]):
            value = {"scores": [i, i + 1, -i, i / 4096]} if scores else {"prediction": i % 4}
            rows.append({"event_id": record["event_id"], **value})
        return {"schema": "reve-candidate-predictions-v1",
                "materials_identity": f.INFOS[0]["materials_identity"], "predictions": list(reversed(rows))}

    def expected(self, document):
        by_id = {row["event_id"]: row for row in document["predictions"]}
        return [{"event_id": record["source_event_id"],
                 **{k: v for k, v in by_id[record["event_id"]].items() if k != "event_id"}}
                for record in f.MAP["records"]]

    def restore_bytes(self, body, output=None, **overrides):
        return m.restore_prediction_bytes(self.panel, self.mapping, self.materials, body,
            output or self.output, **(self.expectations | overrides))

    def restore_collected(self, collected):
        with patch.object(a, "materials_module", return_value=m):
            return a.restore_private(collected, panel_path=self.panel, mapping_path=self.mapping,
                materials_path=self.materials, output=self.output, **self.expectations)

    def assert_preserved(self, document, receipt):
        restored = json.loads(self.output.read_bytes())
        self.assertEqual(receipt["test_predictions"], 1803)
        self.assertEqual(restored["predictions"], self.expected(document))
        self.assertEqual(restored["candidate_submission_identity"], m.identity(document))
        self.assertEqual(len({row["event_id"] for row in restored["predictions"]}), 1803)
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)

    def test_complete_classes_equal_path_api(self):
        document = self.submission()
        body = m.canonical(document) + b"\n"
        write(self.result_path, body)
        receipt = self.restore_bytes(body)
        other = self.private / "path-classes.json"
        path_receipt = m.restore_predictions(self.panel, self.mapping, self.materials,
            self.result_path, other, **self.expectations)
        self.assertEqual(receipt, path_receipt)
        self.assertEqual(self.output.read_bytes(), other.read_bytes())
        self.assert_preserved(document, receipt)

    def test_complete_scores_equal_path_api(self):
        document = self.submission(scores=True)
        body = json.dumps(document, indent=1).encode()
        write(self.result_path, body)
        receipt = self.restore_bytes(body)
        other = self.private / "path-scores.json"
        path_receipt = m.restore_predictions(self.panel, self.mapping, self.materials,
            self.result_path, other, **self.expectations)
        self.assertEqual(receipt, path_receipt)
        self.assertEqual(self.output.read_bytes(), other.read_bytes())
        self.assert_preserved(document, receipt)

    def test_replacement_after_closed_capture_uses_authenticated_scores(self):
        document = self.submission(scores=True)
        body = m.canonical(document) + b"\n"
        write(self.result_path, body)
        replacement = self.submission()
        original_regular = m.regular
        reads = []

        @contextmanager
        def replace_after_close(path, cap):
            with original_regular(path, cap) as opened:
                yield opened
            if Path(path) == self.result_path:
                reads.append(str(path))
                write(self.result_path, m.canonical(replacement) + b"\n")

        with patch.object(m, "regular", replace_after_close):
            receipt = self.restore_collected({"result_path": str(self.result_path),
                "result_pin": a.pin(body), "private_restoration_pending": True})
        self.assertEqual(reads, [str(self.result_path)])
        self.assertEqual(json.loads(self.result_path.read_bytes()), replacement)
        self.assert_preserved(document, receipt)

    def test_removed_path_after_closed_capture_uses_authenticated_classes(self):
        document = self.submission()
        body = m.canonical(document) + b"\n"
        write(self.result_path, body)
        original_regular = m.regular

        @contextmanager
        def remove_after_close(path, cap):
            with original_regular(path, cap) as opened:
                yield opened
            if Path(path) == self.result_path:
                self.result_path.unlink()

        with patch.object(m, "regular", remove_after_close):
            receipt = self.restore_collected({"result_path": str(self.result_path),
                "result_pin": a.pin(body), "private_restoration_pending": True})
        self.assertFalse(self.result_path.exists())
        self.assert_preserved(document, receipt)

    def test_mismatched_capture_pin_or_pending_state_refused(self):
        body = m.canonical(self.submission())
        write(self.result_path, body)
        for key, value in (("result_pin", {"bytes": len(body), "sha256": "0" * 64}),
                           ("private_restoration_pending", False)):
            collected = {"result_path": str(self.result_path), "result_pin": a.pin(body),
                         "private_restoration_pending": True, key: value}
            with self.subTest(key=key), patch.object(m, "restore_prediction_bytes") as restore:
                with self.assertRaises(a.Refusal):
                    self.restore_collected(collected)
                restore.assert_not_called()
                self.assertFalse(self.output.exists())

    def test_malformed_captured_json_refused_without_output(self):
        for body in (b"", bytearray(b"{}"), "{}", b"[]", b'{"x":1,"x":2}',
                     b'{"x":NaN}', b'{"x":Infinity}', b"\xff", b"{"):
            with self.subTest(body=repr(body)), self.assertRaises(m.MaterialError):
                self.restore_bytes(body)
            self.assertFalse(self.output.exists())

    def test_captured_json_size_bound_refuses_before_parsing(self):
        with self.assertRaisesRegex(m.MaterialError, "bounded bytes"):
            self.restore_bytes(b" " * (m.MAX_JSON_BYTES + 1))
        self.assertFalse(self.output.exists())

    def test_prediction_membership_and_values_remain_strict(self):
        for change in ("missing", "duplicate", "foreign", "boolean_class", "two_values", "bad_scores"):
            document = self.submission()
            rows = document["predictions"]
            if change == "missing": rows.pop()
            elif change == "duplicate": rows[-1] = deepcopy(rows[0])
            elif change == "foreign": rows[0]["event_id"] = "foreign"
            elif change == "boolean_class": rows[0]["prediction"] = True
            elif change == "two_values": rows[0]["scores"] = [0, 1, 2, 3]
            else: rows[0] = {"event_id": rows[0]["event_id"], "scores": [0, 1, 2]}
            with self.subTest(change=change), self.assertRaises(m.MaterialError):
                self.restore_bytes(m.canonical(document))
            self.assertFalse(self.output.exists())

    def test_selected_private_identities_and_existing_output_remain_protected(self):
        body = m.canonical(self.submission())
        for key in self.expectations:
            with self.subTest(key=key), self.assertRaises(m.MaterialError):
                self.restore_bytes(body, **{key: "0" * 64})
            self.assertFalse(self.output.exists())
        write(self.output, b"preserve\n")
        with self.assertRaises(FileExistsError):
            self.restore_bytes(body)
        self.assertEqual(self.output.read_bytes(), b"preserve\n")

    def test_runtime_entrypoints_remain_closed_before_provider_access(self):
        with patch.object(a, "transport_package", side_effect=AssertionError("provider access")):
            with self.assertRaises(a.RuntimeUnavailable): a.run()
            with self.assertRaises(a.RuntimeUnavailable):
                a._compose_owned_phase(None, None, None, None, None)


if __name__ == "__main__":
    unittest.main(verbosity=2)
