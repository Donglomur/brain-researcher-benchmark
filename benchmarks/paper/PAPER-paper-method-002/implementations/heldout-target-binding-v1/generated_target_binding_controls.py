"""Generated target-binding controls; the fixed entry supplies source/artifact roots.

The eight test methods and all fixture/helper bodies are unchanged. This module
has no standalone dispatcher and accepts no original-data namespace.
"""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

HERE = Path(_CONTROL_ARTIFACT_ROOT)
W = Path(_CONTROL_IMPLEMENTATIONS_ROOT)
NUMPY_INIT = Path(np.__file__).resolve()
NUMPY_INIT_BODY = NUMPY_INIT.read_bytes()
bridge = _CONTROL_BRIDGE
SOURCES = {
    "input_binding": {"path": str(W / "original-input-programme-v1/input_binding.py"), "bytes": 10007,
                      "sha256": "f4bd10b4c40cef74835001937ce3dc5cb4bd16fcc061b4138696b39827a707d9"},
    "scorer": {"path": str(W / "retinal-heldout/score.py"), "bytes": 10745,
               "sha256": "b2ac5156fe01d600d32b35e0bbf716bd6dea69f59b6bd3a062a6a6c2b0bb126c"},
}
producer = bridge.source_module("input_binding", SOURCES["input_binding"])
scorer = bridge.source_module("scorer", SOURCES["scorer"])
WRITTEN_FIXTURE_BYTES = 0
FIXTURE_FILE_READ_BYTES = 0


def descriptor(array, order=False):
    out = {"shape": list(array.shape), "dtype": array.dtype.str, "bytes": array.nbytes,
           "sha256": hashlib.sha256(array.tobytes()).hexdigest()}
    if order:
        out["order"] = "C"
    return out


def fixture():
    sites, ordinal = [], 0
    for field in range(1, 16):
        for branch in range(10 if field <= 12 else 9):
            ids = [2 * branch + 1, 2 * branch + 2] if ordinal < 85 else [2 * branch + 1]
            sites.append({"field": field, "branch": branch, "bin": 0, "raw_roi_ids": ids})
            ordinal += 1
    test = [field * 1024 + frame for field in range(15) for frame in range(8)]
    test += [field * 1024 + 8 for field in range(8)]
    held = set(test)
    remaining = [row for row in range(15360) if row not in held]
    splits = {"train": remaining[:12185], "val": remaining[12185:], "test": test}
    identities = {"sites": sites, "splits": splits}
    identity = hashlib.sha256(json.dumps(identities, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    frame = np.arange(1, 1025, dtype=np.float64)[None, :]
    observed = np.ascontiguousarray(frame**2 + (np.arange(147, dtype=np.float64)[:, None] + 1) * frame)
    fields = np.asarray([s["field"] for s in sites])
    mask = (np.arange(15360)[:, None] // 1024 + 1 == fields[None, :]).astype(np.float64)
    private = {"schema": "jaxley-private-pre-model-inputs-v1", "contains_all_private_targets": True,
               "cell_id": "20161028_1", "target_layout": bridge.TARGET_LAYOUT,
               "identity_sha256": identity, **identities,
               "arrays": {"observed_site_targets": descriptor(observed, order=True)}, "files": {}}
    participant = {"schema": "jaxley-original-model-operation-input-v1", "test_targets_included": False,
                   "cell_id": "20161028_1", "identity_sha256": identity, **copy.deepcopy(identities),
                   "arrays": {"images": {}, "currents": {}, "mask": descriptor(mask), "train_targets": {}, "val_targets": {}}}
    return observed, private, participant, identity


OBSERVED, PRIVATE, PARTICIPANT, IDENTITY = fixture()


def restored(observed=OBSERVED, private=PRIVATE, participant=PARTICIPANT, identity=IDENTITY):
    return bridge.restore_private_binding(observed, private, participant, identity, scorer)


class TargetBindingControls(unittest.TestCase):
    def test_real_file_bridge_existing_producer_and_existing_score(self):
        global WRITTEN_FIXTURE_BYTES, FIXTURE_FILE_READ_BYTES
        with tempfile.TemporaryDirectory(prefix="generated-targets-", dir=HERE) as directory:
            directory = Path(directory)
            stream = io.BytesIO()
            np.save(stream, OBSERVED, allow_pickle=False)
            observed_body = stream.getvalue()
            private = copy.deepcopy(PRIVATE)
            participant_body = (json.dumps(PARTICIPANT, sort_keys=True, separators=(",", ":")) + "\n").encode()
            private["files"] = {
                "observed_site_targets.npy": {"bytes": len(observed_body), "sha256": hashlib.sha256(observed_body).hexdigest()},
                "model_metadata.json": {"bytes": len(participant_body), "sha256": hashlib.sha256(participant_body).hexdigest()},
            }
            private_body = (json.dumps(private, sort_keys=True, separators=(",", ":")) + "\n").encode()
            inputs = {}
            for name, body in (("observed", observed_body), ("private_metadata", private_body), ("participant_metadata", participant_body)):
                path = directory / (name + ".generated")
                path.write_bytes(body)
                WRITTEN_FIXTURE_BYTES += len(body)
                inputs[name] = {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            manifest = {"schema": "jaxley-private-target-sidecar-binding-v1", "identity_sha256": IDENTITY,
                        "inputs": inputs, "sources": SOURCES}
            packet = bridge.load_operator(manifest)
            FIXTURE_FILE_READ_BYTES += sum(p["bytes"] for p in inputs.values())
            rows = PRIVATE["splits"]["test"]
            self.assertEqual(packet["splits"], PRIVATE["splits"])
            self.assertEqual(packet["sites"], PRIVATE["sites"])
            expected_predictions = []
            for i, row in enumerate(rows):
                frame = row % 1024 + 1
                expected_predictions.append([float(frame**2 + (j + 1) * frame) for j in range(147)])
                for j, site in enumerate(PRIVATE["sites"]):
                    active = row // 1024 + 1 == site["field"]
                    self.assertEqual(packet["mask"][i][j], float(active))
                    self.assertEqual(packet["labels"][i][j], expected_predictions[-1][j] if active else None)
            keys = [[s["field"], s["branch"], s["bin"]] for s in PRIVATE["sites"]]
            author = {"schema": "jaxley-retinal-prediction-v1", "cell_id": "20161028_1", "test_row_ids": rows,
                      "site_keys": keys, "predictions": expected_predictions}
            candidate = {**author, "test_row_ids": rows[::-1], "site_keys": keys[::-1],
                         "predictions": [[-value for value in row[::-1]] for row in expected_predictions[::-1]]}
            result = scorer.compare(packet, author, candidate)
            self.assertAlmostEqual(result["author_mean_pearson"], 1.0, places=14)
            self.assertAlmostEqual(result["candidate_mean_pearson"], -1.0, places=14)
            self.assertAlmostEqual(result["paired_delta"], -2.0, places=14)
            self.assertEqual(len(result["sites"]), 147)
            self.assertFalse(result["undefined_sites_dropped"])
            self.assertIsNone(result["paper_win"])
            self.assertIsNone(result["uncertainty"])
            self.assertEqual(bridge.digest_json({"sites": packet["sites"], "splits": packet["splits"]}), IDENTITY)

    def test_coherent_relabelled_split_and_site_orders_refuse_frozen_identity(self):
        for change in ("split", "sites"):
            with self.subTest(change=change):
                p, q = copy.deepcopy(PRIVATE), copy.deepcopy(PARTICIPANT)
                if change == "split":
                    for value in (p, q):
                        value["splits"]["train"][0], value["splits"]["val"][0] = value["splits"]["val"][0], value["splits"]["train"][0]
                else:
                    p["sites"] = p["sites"][::-1]
                    q["sites"] = q["sites"][::-1]
                changed = bridge.digest_json({"sites": p["sites"], "splits": p["splits"]})
                p["identity_sha256"] = q["identity_sha256"] = changed
                with self.assertRaisesRegex(ValueError, "frozen split and site identity"):
                    restored(private=p, participant=q)

    def test_target_bytes_shape_dtype_and_finiteness_are_bound(self):
        altered = OBSERVED.copy()
        altered[0, 0] += 1
        nonfinite = OBSERVED.copy()
        nonfinite[1, 0] = np.nan
        for array in (altered, nonfinite, OBSERVED[:-1], OBSERVED.astype(np.float32), np.asfortranarray(OBSERVED)):
            with self.subTest(shape=array.shape, dtype=str(array.dtype)):
                with self.assertRaises(ValueError):
                    restored(observed=array)

    def test_derived_mask_requires_exact_float64_descriptor(self):
        for field, value in (("dtype", "|b1"), ("sha256", "0" * 64)):
            q = copy.deepcopy(PARTICIPANT)
            q["arrays"]["mask"][field] = value
            with self.assertRaisesRegex(ValueError, "derived mask numeric identity"):
                restored(participant=q)

    def test_test_target_in_participant_or_wrong_private_layout_refuses(self):
        q = copy.deepcopy(PARTICIPANT)
        q["test_targets_included"] = True
        with self.assertRaisesRegex(ValueError, "participant target exclusion"):
            restored(participant=q)
        q = copy.deepcopy(PARTICIPANT)
        q["arrays"]["test_targets"] = {}
        with self.assertRaisesRegex(ValueError, "participant array roster"):
            restored(participant=q)
        p = copy.deepcopy(PRIVATE)
        p["target_layout"] = "different layout"
        with self.assertRaisesRegex(ValueError, "serialized target layout"):
            restored(private=p)

    def test_bounded_npy_decoder_rejects_wrong_headers_and_trailing_bytes(self):
        stream = io.BytesIO()
        np.save(stream, OBSERVED, allow_pickle=False)
        np.testing.assert_array_equal(bridge.decode_observed(stream.getvalue()), OBSERVED)
        for suffix in (b"x",):
            with self.assertRaisesRegex(ValueError, "exact NPY target payload extent"):
                bridge.decode_observed(stream.getvalue() + suffix)
        for shape, dtype, fortran in (((147, 1024), "|O", False), ((2**32, 1024), "<f8", False), ((147, 1024), "<f8", True)):
            header = io.BytesIO()
            np.lib.format.write_array_header_1_0(header, {"descr": dtype, "fortran_order": fortran, "shape": shape})
            with self.assertRaisesRegex(ValueError, "bounded NPY target header"):
                bridge.decode_observed(header.getvalue())

    def test_file_identity_links_and_strict_json_fail_closed(self):
        global WRITTEN_FIXTURE_BYTES, FIXTURE_FILE_READ_BYTES
        with tempfile.TemporaryDirectory(prefix="generated-pin-", dir=HERE) as directory:
            path = Path(directory) / "tiny"
            body = b"fixture\n"
            path.write_bytes(body)
            WRITTEN_FIXTURE_BYTES += len(body)
            pin = {"path": str(path), "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
            self.assertEqual(bridge.read_pinned(pin, 32), body)
            FIXTURE_FILE_READ_BYTES += len(body)
            with self.assertRaisesRegex(ValueError, "file identity"):
                bridge.read_pinned({**pin, "sha256": "0" * 64}, 32)
            FIXTURE_FILE_READ_BYTES += len(body)
            linked = Path(directory) / "linked"
            linked.symlink_to(path)
            with self.assertRaises(OSError):
                bridge.read_pinned({**pin, "path": str(linked)}, 32)
            hard = Path(directory) / "hard"
            os.link(path, hard)
            with self.assertRaisesRegex(ValueError, "ordinary exact file"):
                bridge.read_pinned(pin, 32)
        for body in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError):
                bridge.strict_json(body)

    def test_undefined_site_is_preserved_by_existing_producer_and_scorer(self):
        observed, private = OBSERVED.copy(), copy.deepcopy(PRIVATE)
        observed[0] = 1.0
        private["arrays"]["observed_site_targets"] = descriptor(observed, order=True)
        packet = producer.operator_packet(restored(observed=observed, private=private))
        rows = PRIVATE["splits"]["test"]
        frame = np.asarray(rows, dtype=np.float64)[:, None] % 1024 + 1
        values = frame**2 + (np.arange(147)[None, :] + 1) * frame
        prediction = {"schema": "jaxley-retinal-prediction-v1", "cell_id": "20161028_1", "test_row_ids": rows,
                      "site_keys": [[s["field"], s["branch"], s["bin"]] for s in PRIVATE["sites"]], "predictions": values.tolist()}
        result = scorer.compare(packet, prediction, prediction)
        self.assertIsNone(result["author_mean_pearson"])
        self.assertIsNone(result["candidate_mean_pearson"])
        self.assertIsNone(result["paired_delta"])
        self.assertFalse(result["undefined_sites_dropped"])
        self.assertEqual(result["recording_sites"], 147)

