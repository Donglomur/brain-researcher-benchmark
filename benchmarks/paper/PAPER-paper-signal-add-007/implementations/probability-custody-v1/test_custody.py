"""Small-time generated controls; original seven animals/four sounds/two trials."""
import contextlib
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("tested_icnet_custody", HERE / "custody.py")
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def dump(path, obj):
    path.write_text(json.dumps(obj, separators=(",", ":")) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def array(root, name, value):
    path = root / name
    with path.open("xb") as f:
        np.lib.format.write_array(f, np.asarray(value), version=(1, 0), allow_pickle=False)
    return {"path": name, "sha256": sha(path)}


class CustodyControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(sys.argv_fixture_root)
        cls.root.mkdir()
        c.p.TIME_BINS = c.g.TIME_BINS = 2
        c.p.AUDIO_SAMPLES = 64
        public = cls.root / "public"; private = cls.root / "private"
        public.mkdir(); private.mkdir()
        files = [{"filename": name, "bytes": values[0], "sha256": "a" * 64,
                  "authenticated_md5": values[1]} for name, values in c.p.SOURCE_FILES.items()]
        panel = {"schema": "icnet-original-public-panel/v1", "animals": {}, "cases": [], "sounds": {},
                 "fs_audio": c.p.FS_AUDIO, "fs_neural": c.p.FS_NEURAL, "time_bins": 2, "audio_samples": 64,
                 "split": "original_four_sounds_held_out_from_training", "qualification": "input_preparation_only",
                 "source_files": files}
        ref = {"schema": "icnet-original-private-panel/v1", "animals": {}, "cases": [],
               "policy": {"schema": "icnet-original-preparation-policy/v1", "measurement_time_sound_order": list(c.p.SOUNDS),
                          "mask_policy": "finite_source_characteristic_frequencies", "mask_evidence_sha256": "b" * 64,
                          "alignment_review_sha256": "c" * 64}, "source_files": files,
               "source_authentication": "generated_test_descriptors", "qualification": "source_preparation_not_scientific_admission"}
        for ai, animal in enumerate(c.p.ANIMALS):
            cf = np.full(512, -np.inf); cf[:497 if ai < 4 else 496] = np.arange(1, (497 if ai < 4 else 496) + 1)
            ids = [f"animal_{animal}:original_column_{u}" for u in range(512)]
            panel["animals"][str(animal)] = {"unit_ids": ids, "characteristic_frequencies": array(public, f"cf{animal}.npy", cf)}
            ref["animals"][str(animal)] = {"unit_ids": ids, "eligible_mask": np.isfinite(cf).tolist()}
        for sound in c.p.SOUNDS:
            panel["sounds"][sound] = array(public, sound + ".npy", np.arange(64, dtype=np.float32) / 100)
            for animal in c.p.ANIMALS:
                case = {"animal": animal, "sound": sound, "time_bins": 2, "measurement_times_seconds": [2.0, 9.0]}
                panel["cases"].append(case)
                observed = np.stack([np.arange(512) % 3, (np.arange(512) + 1) % 4]).astype(np.int8)
                ref["cases"].append({**case, "arrays": {
                    f"recorded_trial{t}": array(private, f"{animal}-{sound}-{t}.npy", observed) for t in (1, 2)}})
        cls.public = public / "panel.json"; dump(cls.public, panel)
        ref["public_manifest_sha256"] = sha(cls.public)
        cls.reference = private / "reference.json"; dump(cls.reference, ref)
        cls.calls = []
        cls.model = {"model_sha256": "d" * 64, "model_source_sha256": "e" * 64}
        cls.destination = cls.root / "valid"
        cls.result = c.capture(cls.public, cls.destination, cls.predictor, predictor_sha256="f" * 64,
                               model_binding=cls.model, seed=73, storage_budget_bytes=c.storage_plan()["required_bytes"])
        cls.capture = cls.destination / "capture.json"

    @classmethod
    def predictor(cls, request):
        cls.calls.append((request["animal"], request["sound"], request["trial"]))
        columns = list(reversed(range(512)))
        for start, dtype in [(0, np.float32), (1, np.float64)]:
            # Distinct means by original column prove that reordering matters.
            original = np.zeros((1, 512, 5), dtype=dtype)
            original[:, ::2, :3] = [.25, .5, .25]
            original[:, 1::2, 1:4] = [.25, .5, .25]
            # Small accepted roundoff must remain in raw bytes, before normalization.
            original[0, 0, 0] += np.finfo(dtype).eps
            yield {"start_bin": start, "probabilities": original[:, columns, :], "column_indices": columns}

    @contextlib.contextmanager
    def altered(self, *paths):
        original = {path: path.read_bytes() for path in paths}
        try:
            yield
        finally:
            for path, raw in original.items(): path.write_bytes(raw)

    def load(self): return json.loads(self.capture.read_text())
    def verify(self): return c.verify(self.public, self.capture)

    def test_01_full_capture_and_original_bytes(self):
        self.assertEqual(len(self.calls), 56)
        self.assertEqual(len(set(self.calls)), 56)
        self.assertEqual(self.result["derived_outputs_verified"], 112)
        self.assertFalse(self.result["scientifically_qualified"])
        doc = self.load(); self.assertEqual(len(doc["streams"]), 56)
        for number, dtype in [(0, np.float32), (1, np.float64)]:
            values = np.load(self.destination / f"probabilities/p-00-{number:05d}.npy")
            self.assertEqual(values.dtype, np.dtype(dtype))
            self.assertEqual(values[0, 511, 0], dtype(.25) + np.finfo(dtype).eps)
        count = np.load(self.destination / "counts/animal_3_speech_in_quiet_expected_trial1.npy")
        self.assertAlmostEqual(float(count[0, 0]), 1., places=6)
        self.assertEqual(float(count[0, 1]), 2.)
        before = len(self.calls); self.verify(); self.assertEqual(len(self.calls), before)

    def test_02_exact_existing_grader(self):
        report = c.verify_and_grade(self.public, self.reference, self.capture, self.root, variance_ddof=0)
        self.assertEqual(len(report["source_equation_report"]["cases"]), 28)
        self.assertFalse(report["reproduction_evaluated"])

    def test_03_count_only_refused(self):
        with self.assertRaises(ValueError): c.verify(self.public, self.destination / "counts/predictions.json")

    def test_04_missing_and_reordered_streams(self):
        for mode in ("missing", "reordered"):
            with self.subTest(mode=mode), self.altered(self.capture):
                doc = self.load()
                if mode == "missing": doc["streams"].pop()
                else: doc["streams"][:2] = reversed(doc["streams"][:2])
                dump(self.capture, doc)
                with self.assertRaises(ValueError): self.verify()

    def test_05_raw_byte_tamper(self):
        path = self.destination / "probabilities/p-00-00000.npy"
        with self.altered(path):
            raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "SHA256"): self.verify()

    def test_06_missing_raw_chunk(self):
        path = self.destination / "probabilities/p-00-00000.npy"
        saved = path.with_suffix(".saved"); path.rename(saved)
        try:
            with self.assertRaises((ValueError, OSError)): self.verify()
        finally: saved.rename(path)

    def test_07_reordered_or_missing_receipts_even_with_new_hash(self):
        receipt = self.destination / "probabilities/stream-00.jsonl"
        for mode in ("reverse", "missing"):
            with self.subTest(mode=mode), self.altered(receipt, self.capture):
                lines = receipt.read_bytes().splitlines(keepends=True)
                receipt.write_bytes(b"".join(lines[::-1] if mode == "reverse" else lines[:1]))
                doc = self.load(); doc["streams"][0]["receipt"]["sha256"] = sha(receipt); dump(self.capture, doc)
                with self.assertRaises(ValueError): self.verify()

    def test_08_stale_derived_outputs_with_updated_hashes(self):
        predictions = self.destination / "counts/predictions.json"
        for kind in ("expected", "sampled"):
            path = self.destination / f"counts/animal_3_speech_in_quiet_{kind}_trial1.npy"
            with self.subTest(kind=kind), self.altered(path, predictions, self.capture):
                values = np.load(path); values[0, 0] += 1
                with path.open("wb") as f: np.lib.format.write_array(f, values, version=(1, 0))
                pred = json.loads(predictions.read_text()); pred["cases"][0]["arrays"][f"{kind}_trial1"]["sha256"] = sha(path)
                dump(predictions, pred)
                doc = self.load(); doc["predictions"]["sha256"] = sha(predictions); dump(self.capture, doc)
                with self.assertRaisesRegex(ValueError, "disagree"): self.verify()

    def test_09_malformed_probabilities_even_with_updated_hashes(self):
        path = self.destination / "probabilities/p-00-00000.npy"
        receipt = self.destination / "probabilities/stream-00.jsonl"
        with self.altered(path, receipt, self.capture):
            values = np.load(path); values[0, 0, 0] = -.5
            with path.open("wb") as f: np.lib.format.write_array(f, values, version=(1, 0))
            rows = [json.loads(x) for x in receipt.read_text().splitlines()]
            rows[0]["array"]["sha256"] = sha(path)
            receipt.write_text(''.join(json.dumps(r,separators=(",", ":"))+'\n' for r in rows))
            doc=self.load();doc["streams"][0]["receipt"]["sha256"]=sha(receipt);dump(self.capture,doc)
            with self.assertRaisesRegex(ValueError, "invalid categorical"): self.verify()

    def test_10_preflight_budget_and_disk_before_predictor(self):
        for name, budget, disk in [("budget", 1, 10**12), ("disk", c.storage_plan()["required_bytes"], 0)]:
            dest = self.root / name
            with patch.object(c.shutil, "disk_usage", return_value=type("Usage", (), {"free": disk})()):
                with self.assertRaises(ValueError):
                    c.capture(self.public, dest, lambda _: self.fail("predictor called before admission"),
                              predictor_sha256="f"*64, model_binding=self.model, seed=73, storage_budget_bytes=budget)
            self.assertTrue((dest/"FAILURE.json").exists());self.assertFalse((dest/"COMPLETED.json").exists())

    def test_11_interrupted_capture_retained_no_retry(self):
        calls = []
        def interrupted(request):
            calls.append(request["animal"])
            yield next(self.predictor(request))
            raise RuntimeError("generated interruption")
        dest=self.root/"interrupted"
        with self.assertRaisesRegex(RuntimeError,"generated interruption"):
            c.capture(self.public,dest,interrupted,predictor_sha256="f"*64,model_binding=self.model,seed=73,
                      storage_budget_bytes=c.storage_plan()["required_bytes"])
        self.assertEqual(calls,[3]);self.assertTrue((dest/"probabilities/p-00-00000.npy").exists())
        self.assertTrue((dest/"FAILURE.json").exists());self.assertFalse((dest/"COMPLETED.json").exists())
        run=json.loads((dest/"RUN.json").read_text());self.assertEqual(run["model_binding"],self.model)
        self.assertEqual(run["sampling_seed"],73)
        header=json.loads((dest/"probabilities/stream-00.COLUMNS.json").read_text())
        self.assertEqual(header["identity"]["animal"],3);self.assertEqual(header["column_indices"],list(reversed(range(512))))

    def test_12_metadata_identity_controls(self):
        for key,value in [("sampling_seed",74),("numpy_version","different"),("public_manifest_sha256","0"*64)]:
            with self.subTest(key=key),self.altered(self.capture):
                doc=self.load();doc[key]=value;dump(self.capture,doc)
                with self.assertRaises(ValueError):self.verify()

    def test_13_replacement_after_verification_rejected_before_grading(self):
        original_verify=c.verify
        with self.altered(self.capture):
            def changed_capture(*args):
                result=original_verify(*args)
                doc=self.load();doc["model_binding"]["model_sha256"]="0"*64;dump(self.capture,doc)
                return result
            with patch.object(c,"verify",side_effect=changed_capture),patch.object(c.g,"grade") as grade:
                with self.assertRaisesRegex(ValueError,"capture changed"):
                    c.verify_and_grade(self.public,self.reference,self.capture,self.root,variance_ddof=0)
                grade.assert_not_called()
        original_assemble=c.g.assemble
        def changed_assembly(*args,**kwargs):
            manifest=original_assemble(*args,**kwargs)
            manifest["preparation"]["prediction_freeze_sha256"]="0"*64
            return manifest
        with patch.object(c.g,"assemble",side_effect=changed_assembly),patch.object(c.g,"grade") as grade:
            with self.assertRaisesRegex(ValueError,"grading inputs differ"):
                c.verify_and_grade(self.public,self.reference,self.capture,self.root,variance_ddof=0)
            grade.assert_not_called()

    def test_14_receipt_replaced_after_initial_hash(self):
        receipt=self.destination/"probabilities/stream-00.jsonl"
        original_hash=c.s.sha256_file
        changed=[False]
        with self.altered(receipt):
            def hash_then_replace(path):
                digest=original_hash(path)
                if Path(path)==receipt.resolve() and not changed[0]:
                    changed[0]=True
                    # Same semantics, different receipt bytes: replay must bind actual bytes consumed.
                    receipt.write_text(''.join(json.dumps(json.loads(x),separators=(",", ": "))+'\n'
                                               for x in receipt.read_text().splitlines()))
                return digest
            with patch.object(c.s,"sha256_file",side_effect=hash_then_replace):
                with self.assertRaisesRegex(ValueError,"receipt changed during replay"):
                    self.verify()
            self.assertTrue(changed[0])


if __name__ == "__main__":
    sys.argv_fixture_root = sys.argv.pop(1)
    unittest.main(verbosity=2)
