"""Generated metadata controls only; no neural data, fitting, or model inference."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("original_volume_binding", HERE / "binding.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class BindingControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.clean = [f"E{i}" for i in range(100)]
        self.plan = {"source_revision": b.REVISION, "endpoint": "rms", "subjects": {}}
        self.plan["clean_laplacian_json"] = self.write("clean.json", {s: self.clean for s in b.TRIALS})
        self.clean_sha = b.digest(Path(self.plan["clean_laplacian_json"]).read_bytes())
        for subject, trial in b.TRIALS.items():
            # Descending feature ordinal order catches accidental natural sorting.
            manifest = "".join(f"/generated/features/{subject}/{trial}/{19-i}.npy\t{subject}\n" for i in range(20))
            labels = "".join(f"{'True' if i % 2 else 'False'}\t{0.01*i}\n" for i in range(20))
            self.plan["subjects"][subject] = {
                "manifest_tsv": self.write(subject + "/manifest.tsv", manifest),
                "labels_tsv": self.write(subject + "/labels.tsv", labels),
                "splits_json": self.write(subject + "/splits.json", {"train": list(range(16)), "val": [17, 16], "test": [19, 18]}),
                "ordered_electrodes_json": self.write(subject + "/ordered.json", {subject: self.clean}),
                "selection_files": {str(c): self.write(f"{subject}/select-{c}.json", {subject: list(reversed(self.clean[:c]))}) for c in b.COUNTS}}

    def tearDown(self):
        self.temp.cleanup()

    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(exist_ok=True, parents=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        return str(path)

    def prepare(self):
        # Generated fixtures are explicitly not the pinned authentic clean list.
        with patch.object(b, "CLEAN_SHA256", self.clean_sha):
            return b.prepare(self.plan)

    def native(self, reference):
        result = {"binding_sha256": reference["binding_sha256"], "runs": {}}
        for subject in b.TRIALS:
            for count in b.COUNTS:
                high = count % 2
                data = reference["subjects"][subject]
                indices = data["splits"]["test"]
                result["runs"][f"{subject}/{count}"] = {
                    "label2idx": {"True": high, "False": 1-high},
                    "channels": data["ensembles"][str(count)]["channels"],
                    "manifest_indices": indices,
                    "labels": [high if data["rows"][i]["label_high_rms"] else 1-high for i in indices],
                    "predicts": [0.7, 0.2]}
        return result

    def bind(self, ref, native):
        with patch.object(b, "CLEAN_SHA256", self.clean_sha):
            return b.bind_native(ref, native)

    def test_source_order_retained_and_overlapping_onsets_allowed(self):
        reference = self.prepare()
        data = reference["subjects"]["sub_1"]
        self.assertEqual(data["splits"]["test"], [19, 18])
        self.assertEqual([data["rows"][i]["row_id"] for i in data["splits"]["test"]], ["sub_1/trial001/0.npy", "sub_1/trial001/1.npy"])
        self.assertEqual(data["ensembles"]["10"]["channels"], self.clean[:10])
        self.assertEqual(data["ensembles"]["10"]["feature_indices"], list(range(10)))
        self.assertNotIn("/generated/", json.dumps(reference))
        self.assertFalse(reference["word_onset_is_neural_support"])

    def test_full_panel_native_mapping_preserves_probabilities(self):
        reference = self.prepare()
        native = self.native(reference)
        tiny = 2.0 ** -60
        native["runs"]["sub_1/10"]["predicts"] = [tiny, 2*tiny]
        output = self.bind(reference, native)
        self.assertEqual(len(output["predictions"]), 98)
        rows = [r for r in output["predictions"] if r["subject"] == "sub_1" and r["electrode_count"] == 10]
        self.assertEqual([r["probability_native_index1"] for r in rows], [tiny, 2*tiny])
        self.assertTrue(all(r["native_high_rms_index"] == 0 for r in rows))
        self.assertNotIn("label_high_rms", json.dumps(output))

    def test_wrong_clean_source_digest_fails(self):
        with self.assertRaisesRegex(b.BindingError, "content pin"):
            b.prepare(self.plan)

    def test_manifest_label_truncation_fails(self):
        inputs = self.plan["subjects"]["sub_1"]
        Path(inputs["labels_tsv"]).write_text("True\t0\n")
        with self.assertRaisesRegex(b.BindingError, "lengths"):
            self.prepare()

    def test_duplicate_feature_and_wrong_trial_fail(self):
        path = Path(self.plan["subjects"]["sub_1"]["manifest_tsv"])
        original = path.read_text()
        path.write_text(original.replace("18.npy", "19.npy"))
        with self.assertRaisesRegex(b.BindingError, "duplicate source"):
            self.prepare()
        path.write_text(original.replace("trial001", "trial000"))
        with self.assertRaisesRegex(b.BindingError, "wrong subject/trial"):
            self.prepare()

    def test_saved_index_overlap_fewshot_and_boolean_fail(self):
        saved = {"train": list(range(16)), "val": [17, 16], "test": [19, 18]}
        for replacement in ([18, 18], [True, 18], [20, 18]):
            bad = copy.deepcopy(saved)
            bad["test"] = replacement
            with self.assertRaises(b.BindingError):
                b.bind_splits(20, bad)
        saved["train"].pop()
        with self.assertRaisesRegex(b.BindingError, "sizes"):
            b.bind_splits(20, saved)

    def test_fractional_split_rounding(self):
        result = b.bind_splits(21, {"train": list(range(16)), "val": [16, 17], "test": [20, 19, 18]})
        self.assertEqual(result["test"], [20, 19, 18])

    def test_incomplete_original_cohort_or_grid_fails(self):
        original = self.plan["subjects"].pop("sub_10")
        with self.assertRaisesRegex(b.BindingError, "seven-subject"):
            self.prepare()
        self.plan["subjects"]["sub_10"] = original
        del original["selection_files"]["20"]
        with self.assertRaisesRegex(b.BindingError, "Figure 3"):
            self.prepare()

    def test_unknown_or_duplicate_channels_fail(self):
        path = Path(self.plan["subjects"]["sub_1"]["selection_files"]["10"])
        for channels in (self.clean[:9] + ["X"], self.clean[:9] + ["E0"]):
            path.write_text(json.dumps({"sub_1": channels}))
            with self.assertRaises(b.BindingError):
                self.prepare()

    def test_native_mismatch_matrix(self):
        reference = self.prepare()
        native = self.native(reference)
        for key, value in (("manifest_indices", [18, 19]), ("manifest_indices", [19.0, 18.0]), ("labels", [0, 1]),
                           ("predicts", [0.5]), ("predicts", [float("nan"), 0.5]),
                           ("channels", ["E99"]), ("label2idx", {"True": True, "False": False})):
            bad = copy.deepcopy(native)
            bad["runs"]["sub_1/1"][key] = value
            with self.assertRaises(b.BindingError, msg=key):
                self.bind(reference, bad)
        native["runs"].pop("sub_1/20")
        with self.assertRaisesRegex(b.BindingError, "49"):
            self.bind(reference, native)

    def test_duplicate_json_and_nonfinite_onset_fail(self):
        with self.assertRaisesRegex(b.BindingError, "duplicate JSON"):
            b.read_json(self.write("bad.json", '{"a":1,"a":2}'))
        path = Path(self.plan["subjects"]["sub_1"]["labels_tsv"])
        path.write_text(path.read_text().replace("False\t0.0", "False\tnan", 1))
        with self.assertRaisesRegex(b.BindingError, "onset"):
            self.prepare()

    def test_rehashed_structurally_invalid_reference_fails(self):
        reference = self.prepare()
        reference["subjects"]["sub_1"]["ensembles"]["10"]["feature_indices"] = list(reversed(range(10)))
        reference.pop("binding_sha256")
        reference["binding_sha256"] = b.canonical_sha(reference)
        with self.assertRaisesRegex(b.BindingError, "feature indices"):
            self.bind(reference, self.native(reference))


if __name__ == "__main__":
    unittest.main(verbosity=2)
