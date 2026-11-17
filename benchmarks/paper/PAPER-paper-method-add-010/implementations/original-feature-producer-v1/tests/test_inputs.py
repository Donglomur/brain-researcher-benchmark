"""Generated source-geometry controls; no authentic MEG arrays or native DBA.

The full integration fixture explicitly substitutes generated archive identity.
Its analytical DBA seam uses identical normalized series, where the barycenter
is known. It is not an installed-tslearn parity or scientific-result test.
"""
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import inputs
import producer


def value(ri, si, region, ms):
    return (ri + 1) * 100 + si * 10 + region * 10 + ms % (si + 4) + ms / 1000


def csv_rows(missing=()):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(inputs.FIELDS)
    for si, stimulus in enumerate(inputs.STIMULI):
        for ri, relevance in enumerate(inputs.RELEVANCES):
            if (relevance, stimulus) in missing:
                continue
            for ms in inputs.GRID_MS:
                writer.writerow([stimulus, relevance, "1000ms", ms / 1000,
                                 *(value(ri, si, region, ms) for region in range(4))])
    return stream.getvalue()


class SourceInputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.csv = csv_rows()
        cls.lines = cls.csv.splitlines(keepends=True)
        cls.person = inputs.roster()[0]

    def decode(self, content=None, person=None):
        return inputs.decode_csv(io.StringIO(self.csv if content is None else content), person or self.person)

    def test_full94_original_geometry_to_selected_features_and_score(self):
        """All94 parsing→376 values→188OOF rows→original ten-fold scorer."""
        special = {p: csv_rows(missing) for p, missing in inputs.SOURCE_MISSING_GROUPS.items()}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            archive = root / "generated.zip"
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                expanded = 0
                for person in inputs.roster():
                    body = special.get(person, self.csv).encode()
                    expanded += len(body)
                    zipped.writestr(inputs.source_member(person), body)
                for i in range(256):
                    zipped.writestr(f"generated_unselected_{i}.txt", b"fixture")
            identity = inputs.pin_file(archive, 60 * 1024**2)
            with patch.dict(inputs.ARCHIVE, identity, clear=True), patch.object(inputs, "SELECTED_EXPANDED_BYTES", expanded):
                result = inputs.prepare(archive, root / "prepared")
                self.assertEqual((result["participants"], result["category_windows"], result["model_fits"]), (94, 376, 0))
                binding = inputs.prepared_binding(root / "prepared")
                self.assertEqual(sum(r["source_rows"] for r in binding["files"]), (94 * 12 - 2) * 2501)
                self.assertEqual(len(list((root / "prepared").glob("*.npy"))), 94)
                for record in binding["files"]:
                    array = inputs.load_prepared(root / "prepared", record)
                    for si in range(4):
                        for region in range(4):
                            for ms in (0, 1, 998, 999):
                                self.assertEqual(array[si, region, ms], value(0, si, region, ms))
                calls = []
                def identical_series_dba(pair):
                    np.testing.assert_allclose(pair[0], pair[1], atol=2e-13, rtol=2e-13)
                    calls.append(1)
                    return ((pair[0] + pair[1]) / 2)[:, None]
                with patch.object(producer, "native_dba", return_value=identical_series_dba):
                    production = producer.produce(root / "prepared", root / "features")
                self.assertEqual(production["feature_calls"], 376)
                self.assertEqual(production["numerical_failures"], 0)
                self.assertEqual(len(calls), 2256)
                feature_path = root / "features" / "FEATURES.json"
                packet = inputs.read_json(feature_path, 2 * 1024**2)
                self.assertEqual(len(producer.source_feature_rows(packet)), 376)
                self.assertFalse(packet["historical_folds_authenticated"])
                fit = producer.classify(feature_path, root / "classification")
                self.assertEqual(fit["model_fits"], 10)
                result = inputs.read_json(root / "classification" / "OOF.json", 2 * 1024**2)
                self.assertEqual(len(result["observations"]), 188)
                self.assertEqual({r["participant"] for r in result["observations"]}, set(inputs.roster()))
                self.assertEqual({r["fold"] for r in result["observations"]}, set(range(10)))
                self.assertFalse(fit["historical_result_reproduced"])

    def test_source_boundaries_and_roi_axes(self):
        array, details = self.decode()
        self.assertEqual(array.shape, (4, 4, 1000))
        self.assertEqual(details["source_rows"], 12 * 2501)
        self.assertEqual(details["category_first_occurrence"], list(inputs.STIMULI))
        for si in range(4):
            for region in range(4):
                np.testing.assert_allclose(array[si, region], [value(0, si, region, ms) for ms in range(1000)], rtol=0, atol=0)

    def test_missing_observed_row_is_not_known_target_absence(self):
        with self.assertRaisesRegex(inputs.InputError, "incomplete"):
            self.decode("".join(self.lines[:-1]))
        # Remove time0 in an irrelevant condition, although the participant has
        # a permitted missing *target* group elsewhere.
        body = csv_rows(inputs.SOURCE_MISSING_GROUPS["CB027"])
        rows = body.splitlines(keepends=True)
        with self.assertRaisesRegex(inputs.InputError, "incomplete"):
            self.decode("".join(rows[:501] + rows[502:]), "CB027")

    def test_unexpected_census_absent_target_rows_are_rejected(self):
        with self.assertRaisesRegex(inputs.InputError, "census-absent"):
            self.decode(person="CB027")

    def test_duplicate_coordinate_rejected(self):
        with self.assertRaisesRegex(inputs.InputError, "duplicate"):
            self.decode(self.csv + self.lines[1])

    def test_bad_header_and_off_grid_time_rejected(self):
        with self.assertRaisesRegex(inputs.InputError, "header"):
            self.decode(self.csv.replace("times,", "timestamp,", 1))
        with self.assertRaisesRegex(inputs.InputError, "millisecond grid"):
            self.decode(self.csv.replace("1000ms,-0.5,", "1000ms,-0.5005,", 1))

    def test_nonfinite_signal_and_wrong_duration_rejected(self):
        first = self.lines[1].rstrip().split(",")
        first[4] = "nan"
        with self.assertRaisesRegex(inputs.InputError, "nonfinite source signal"):
            self.decode(self.lines[0] + ",".join(first) + "\n" + "".join(self.lines[2:]))
        with self.assertRaisesRegex(inputs.InputError, "duration"):
            self.decode(self.csv.replace("1000ms", "1500ms", 1))

    def test_archive_is_authenticated_before_body_parse(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "wrong.zip"
            path.write_bytes(b"not a valid archive")
            with self.assertRaisesRegex(inputs.InputError, "identity mismatch"):
                with inputs.authenticated_archive(path):
                    self.fail("unauthenticated archive accepted")

    def test_duplicate_archive_members_rejected_after_hash(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "duplicate.zip"
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zipped:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    zipped.writestr("duplicate", b"first")
                    zipped.writestr("duplicate", b"second")
            with patch.dict(inputs.ARCHIVE, inputs.pin_file(path, 10000), clear=True), patch.object(inputs, "ARCHIVE_ENTRIES", 2):
                with self.assertRaisesRegex(inputs.InputError, "uniqueness"):
                    with inputs.authenticated_archive(path):
                        self.fail("duplicate archive accepted")

    def test_prepared_array_checksum_and_payload_extent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "test.npy"
            with path.open("wb") as stream:
                np.save(stream, np.ones(inputs.SHAPE, dtype="<f8"), allow_pickle=False)
            record = {"file": path.name, "pin": inputs.pin_file(path, 130000)}
            self.assertEqual(inputs.load_prepared(temp, record).shape, inputs.SHAPE)
            with path.open("ab") as stream:
                stream.write(b"trailer")
            with self.assertRaisesRegex(inputs.InputError, "identity mismatch"):
                inputs.load_prepared(temp, record)
            record["pin"] = inputs.pin_file(path, 130000)
            with self.assertRaisesRegex(inputs.InputError, "payload extent"):
                inputs.load_prepared(temp, record)

    def test_json_duplicate_keys_and_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "duplicates.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaisesRegex(inputs.InputError, "duplicate JSON"):
                inputs.read_json(path, 100)
            with self.assertRaisesRegex(inputs.InputError, "fresh output"):
                inputs.fresh_directory(Path(temp).resolve())

    def test_json_identity_binds_same_open_descriptor_as_parse(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "first.json"
            path.write_text('{"payload":"first"}')
            expected = inputs.pin_file(path, 100)
            original_pin = inputs.pin_stream
            def replace_after_pin(stream):
                identity = original_pin(stream)
                path.rename(Path(temp) / "retained.json")
                path.write_text('{"payload":"second"}')
                return identity
            # Path replacement cannot make the new bytes masquerade as the
            # old parsed value: a metadata mutation aborts, or old descriptor
            # value and identity remain paired. It cannot return second+oldpin.
            try:
                with patch.object(inputs, "pin_stream", side_effect=replace_after_pin):
                    value, identity = inputs.read_json(path, 100, with_pin=True)
            except inputs.InputError as exc:
                self.assertIn("changed while reading", str(exc))
            else:
                self.assertEqual(value, {"payload": "first"})
                self.assertEqual(identity, expected)

    def test_feature_boundary_rejects_missing_duplicate_or_changed_condition(self):
        packet = {"schema": "meg_original_bary_sq_dtw_max_v1", "task_id": inputs.TASK,
                  "feature": producer.FEATURE, "relevance": "Irrelevant", "data_type": "Raw", "phase": "on",
                  "time_ms_inclusive": [0, 999], "regions": list(inputs.REGIONS), "archive": inputs.ARCHIVE,
                  "selected_pair": ["Category_Selective", "Prefrontal_Cortex"],
                  "rows": [{"id": producer.observation_id(p, s), "participant": p, "label": s.lower(), "value": 0.5}
                           for p in inputs.roster() for s in inputs.STIMULI]}
        self.assertEqual(len(producer.source_feature_rows(packet)), 376)
        with self.assertRaisesRegex(inputs.InputError, "94×4"):
            producer.source_feature_rows({**packet, "rows": packet["rows"][:-1]})
        with self.assertRaisesRegex(inputs.InputError, "duplicate"):
            producer.source_feature_rows({**packet, "rows": [packet["rows"][1], *packet["rows"][1:]]})
        with self.assertRaisesRegex(inputs.InputError, "condition"):
            producer.source_feature_rows({**packet, "data_type": "Abs"})


if __name__ == "__main__":
    unittest.main()
