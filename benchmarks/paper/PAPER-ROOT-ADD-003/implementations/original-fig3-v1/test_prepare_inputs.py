"""Generated controls only; no authentic data or model execution."""
import copy
import csv
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

_spec = importlib.util.spec_from_file_location("fig3_prepare_inputs", Path(__file__).with_name("prepare_inputs.py"))
p = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = p
_spec.loader.exec_module(p)
e = p.e


class ForbiddenOutcome:
    def __float__(self):
        raise AssertionError("an evaluator-only outcome was converted")


def rows():
    for uid in p.TRAIN_PARTICIPANTS + e.PARTICIPANTS:
        for item in (p.TRAIN_ITEMS if uid in p.TRAIN_PARTICIPANTS else e.ITEMS):
            condition = "B" if item <= 1000 else "D" if item <= 1250 else "S"
            yield {"target_UID": str(uid), "roi": e.ROI, "item_id": str(item),
                   "sentence": "Generated sentence, \"item\" " + str(item),
                   "cond": condition, "cond_approach": "B" if condition == "B" else condition + "_search",
                   "response_target": str(uid + item / 1000) if uid in p.TRAIN_PARTICIPANTS else ForbiddenOutcome(),
                   "response_target_non_norm": ForbiddenOutcome(), "encoding_model_pred": ForbiddenOutcome()}


class PrepareInputsTests(unittest.TestCase):
    def test_complete_training_cells_and_source_order_are_preserved(self):
        source = list(rows())
        prepared = p._inputs_from_rows(source)
        self.assertEqual(prepared, p._inputs_from_rows(reversed(source)))
        self.assertEqual(len(prepared.sentences), 1500)
        self.assertEqual(tuple(map(len, prepared.training_responses)), (1000,) * 5)
        for uid, values in zip(p.TRAIN_PARTICIPANTS, prepared.training_responses):
            self.assertEqual(values[0], uid + .001)
            self.assertEqual(values[-1], uid + 1.)

    def test_evaluator_outcomes_and_other_cohorts_are_not_converted(self):
        other = [{"target_UID": "837", "roi": e.ROI, "response_target": ForbiddenOutcome()},
                 {"target_UID": "848", "roi": "lang_LH_IFG", "response_target": ForbiddenOutcome()}]
        self.assertEqual(p._inputs_from_rows(other + list(rows())), p._inputs_from_rows(rows()))

    def test_missing_duplicate_and_wrong_training_support_fail(self):
        source = list(rows())
        cases = [source[1:], source[:-1], source + [source[0]], source + [source[-1]]]
        for bad in cases:
            with self.subTest(length=len(bad)), self.assertRaises(e.InvalidPanel):
                p._inputs_from_rows(bad)
        for field, value in (("item_id", "1001"), ("response_target", "nan"),
                             ("response_target", True), ("cond_approach", "D_modify")):
            bad = copy.deepcopy(source)
            bad[0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(e.InvalidPanel):
                p._inputs_from_rows(bad)

    def test_training_and_evaluation_share_exact_sentence_identity(self):
        source = list(rows())
        for field, value in (("sentence", "different sentence"), ("cond", "S"),
                             ("cond_approach", "D_modify")):
            bad = copy.deepcopy(source)
            bad[6000][field] = value
            with self.subTest(field=field), self.assertRaises(e.InvalidPanel):
                p._inputs_from_rows(bad)

    def test_export_contains_only_permitted_inputs_and_does_not_overwrite(self):
        prepared = p._inputs_from_rows(rows())
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary) / "common"
            manifest = p.write_inputs(prepared, directory)
            self.assertEqual({f.name for f in directory.iterdir()},
                             {"sentences.csv", "training_responses.csv", "manifest.json"})
            with (directory / "sentences.csv").open(newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, ["item_id", "sentence"])
                sentences = list(reader)
            self.assertEqual([r["sentence"] for r in sentences], list(prepared.sentences))
            with (directory / "training_responses.csv").open(newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, ["target_UID", "item_id", "response_target"])
                responses = list(reader)
            self.assertEqual(len(responses), 5000)
            self.assertEqual({int(r["target_UID"]) for r in responses}, set(p.TRAIN_PARTICIPANTS))
            self.assertEqual({int(r["item_id"]) for r in responses}, set(p.TRAIN_ITEMS))
            for entry in manifest["files"]:
                data = (directory / entry["path"]).read_bytes()
                self.assertEqual(entry["bytes"], len(data))
                self.assertEqual(entry["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual(manifest, json.loads((directory / "manifest.json").read_text()))
            self.assertFalse(manifest["evaluation_responses_exported"])
            self.assertFalse(manifest["scientific_qualification"])
            with self.assertRaises(FileExistsError):
                p.write_inputs(prepared, directory)

    def test_public_loader_authenticates_before_parsing_and_uses_original_columns(self):
        # Generated archive admitted only by explicitly patched fixture pins.
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=e.SOURCE_COLUMNS)
        writer.writeheader()
        for row in rows():
            for key in ("response_target", "response_target_non_norm", "encoding_model_pred"):
                if isinstance(row[key], ForbiddenOutcome):
                    row[key] = "DO_NOT_CONVERT_EVALUATOR_OUTCOME"
            writer.writerow(row)
        payload = buffer.getvalue().encode()
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / "generated.tar"
            with tarfile.open(archive, "w") as handle:
                info = tarfile.TarInfo(e.MEMBER)
                info.size = len(payload)
                handle.addfile(info, io.BytesIO(payload))
            original = archive.read_bytes()
            with patch.multiple(e, ARCHIVE_BYTES=len(original), MEMBER_BYTES=len(payload),
                                ARCHIVE_SHA256=hashlib.sha256(original).hexdigest()):
                self.assertEqual(p.load_original_inputs(archive), p._inputs_from_rows(rows()))
                with archive.open("r+b") as handle:
                    handle.seek(512)
                    handle.write(b"x")
                with self.assertRaisesRegex(e.InvalidPanel, "SHA256"):
                    p.load_original_inputs(archive)


if __name__ == "__main__":
    unittest.main(verbosity=2)
