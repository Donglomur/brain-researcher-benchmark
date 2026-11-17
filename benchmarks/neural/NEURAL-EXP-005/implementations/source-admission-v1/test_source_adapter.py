"""Independent generated controls; no authentic EEG or annotation values.

The complete-census control replaces only the source/reader boundary and uses
the public source duration roster. Numerical EDF controls use real pinned
Asset/Header classes with wholly invented files and independently calculated
calibration values. Nothing here authenticates a production data release.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import source_adapter as adapter
import source_loader as loader


def _field(value, size):
    raw = str(value).encode("ascii")
    if len(raw) > size:
        raise AssertionError("invalid invented EDF field")
    return raw.ljust(size, b" ")


def digital(record, sample, electrode_index, shift=0):
    return (record + sample % 17 + 3 * electrode_index + shift) % 101 - 50


def make_edf(path, source, *, records=32, shift=0):
    """Invent a standard EDF with unequal per-electrode physical gains/offsets."""
    electrodes = tuple(sorted(source.intake.ELECTRODES))
    labels = ["EEG " + name + "-Ref" for name in electrodes] + ["ECG", "Resp"]
    count = len(labels)
    header_bytes = 256 * (count + 1)
    fixed = b"".join((
        _field(0, 8), _field("invented", 80), _field("generated control", 80),
        _field("01.01.01", 8), _field("00.00.00", 8), _field(header_bytes, 8),
        _field("", 44), _field(records, 8), _field(1, 8), _field(count, 4),
    ))
    columns = (
        (labels, 16), ([""] * count, 80), (["uV"] * count, 8),
        ([-100 * (i + 1) + i for i in range(count)], 8),
        ([100 * (i + 1) + i for i in range(count)], 8),
        ([-100] * count, 8), ([100] * count, 8), ([""] * count, 80),
        ([256] * count, 8), ([""] * count, 32),
    )
    header = fixed + b"".join(_field(v, width) for values, width in columns for v in values)
    if len(header) != header_bytes:
        raise AssertionError("fixture header geometry")
    with Path(path).open("xb") as handle:
        handle.write(header)
        for record in range(records):
            for channel in range(count):
                handle.write(struct.pack("<256h", *(digital(record, j, channel, shift) for j in range(256))))
    raw = Path(path).read_bytes()
    row = {"name": Path(path).name, "bytes": len(raw), "md5": hashlib.md5(raw, usedforsecurity=False).hexdigest()}
    return row, electrodes


def expected_sample(index, electrodes, montage, shift=0):
    record, sample = divmod(index, 256)
    # This is the independent affine form of the invented header calibration,
    # rather than a call into Channel.physical or the adapter implementation.
    values = {name: digital(record, sample, i, shift) * (i + 1) + i
              for i, name in enumerate(electrodes)}
    return tuple(values[left] - values[right] for left, right in montage)


class PinnedSourceControls(unittest.TestCase):
    def test_exact_source_loader_preserves_global_import_path_and_montage(self):
        before = list(sys.path)
        sources = loader.load_sources()
        self.assertEqual(sys.path, before)
        self.assertEqual(tuple("-".join(pair) for pair in sources.intake.MONTAGE), sources.current.MONTAGE)
        self.assertEqual(sources.intake.FS, 256)
        self.assertEqual(sources.profile.PROTOCOL_ID, "helsinki_recorded_grid_quality_flags_v2")
        self.assertEqual(sources.current.PROTOCOL, "helsinki_full_timestamp_quality_flags_v1")
        self.assertNotEqual(sources.profile.PROTOCOL_ID, sources.current.PROTOCOL)
        self.assertEqual(len(sources.dependencies), 10)

    def test_read_pinned_accepts_only_exact_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(b"answer = 42\n")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(loader.read_pinned(path, sha), b"answer = 42\n")
            with self.assertRaises(loader.SourceError):
                loader.read_pinned(path, "0" * 64)

    def test_read_pinned_rejects_symlink_and_hardlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.py"
            path.write_bytes(b"pass\n")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            link = Path(directory) / "symbolic.py"
            link.symlink_to(path)
            with self.assertRaises((loader.SourceError, OSError)):
                loader.read_pinned(link, sha)
            link.unlink()
            hard = Path(directory) / "hard.py"
            os.link(path, hard)
            with self.assertRaises(loader.SourceError):
                loader.read_pinned(path, sha)

    def test_read_pinned_rejects_large_file_before_consumption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "too-large.py"
            # Sparse generated file: its declared extent exceeds the reader cap.
            with path.open("wb") as handle:
                handle.truncate(1024 * 1024 + 1)
            with self.assertRaises(loader.SourceError):
                loader.read_pinned(path, "0" * 64)


class NumericalReaderControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = loader.load_sources()
        cls.directory = tempfile.TemporaryDirectory()
        cls.root = Path(cls.directory.name)
        cls.row, cls.electrodes = make_edf(cls.root / "invented.edf", cls.source)
        cls.other_row, _ = make_edf(cls.root / "other.edf", cls.source, shift=1)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    @contextmanager
    def asset(self, row=None):
        asset = self.source.intake.Asset(self.root, self.row if row is None else row)
        try:
            header = self.source.intake.read_header(asset.handle, asset.size)
            yield asset, header
        finally:
            asset.close()

    def reader(self, asset, header, cache_records=31):
        return adapter.IntervalReader(lambda _rid: (asset, header), self.source.intake.MONTAGE,
                                      cache_records=cache_records)

    def assert_samples(self, actual, start, stop, shift=0):
        self.assertEqual(len(actual), stop - start)
        self.assertEqual([tuple(row) for row in actual],
                         [expected_sample(n, self.electrodes, self.source.intake.MONTAGE, shift)
                          for n in range(start, stop)])

    def test_calibration_is_per_electrode_before_bipolar_subtraction(self):
        with self.asset() as (asset, header):
            samples = adapter.read_calibrated_record(asset, header, 7, self.source.intake.MONTAGE)
            self.assert_samples(samples, 7 * 256, 8 * 256)
            self.assertEqual(len(samples[0]), 18)

    def test_cross_record_half_open_interval(self):
        with self.asset() as (asset, header):
            reader = self.reader(asset, header)
            self.assert_samples(reader("eeg1", 253, 261), 253, 261)
            self.assert_samples(reader("eeg1", 256, 257), 256, 257)

    def test_first_and_final_native_samples(self):
        with self.asset() as (asset, header):
            reader = self.reader(asset, header)
            end = header.records * 256
            self.assert_samples(reader("eeg1", 0, 1), 0, 1)
            self.assert_samples(reader("eeg1", end - 1, end), end - 1, end)

    def test_exact_thirty_record_window_can_span_thirty_one_records(self):
        with self.asset() as (asset, header):
            reader = self.reader(asset, header)
            self.assert_samples(reader("eeg1", 1, 7681), 1, 7681)
            self.assertLessEqual(len(reader._cache), 31)

    def test_active_payload_delivers_first_and_last_causal_windows_without_labels(self):
        # Exercise the unchanged payload function used by prepare_reference and
        # packet; do not manufacture a complete-source admission or Reference.
        with self.asset() as (asset, header):
            reader = self.reader(asset, header)
            description = {"assessment_id": "invented-payload-control", "representation_sha256": "1" * 64,
                           "detector_sha256": "2" * 64}
            record = {"recording_id": "eeg1", "sample_rate": {"num": 256, "den": 1},
                      "sample_count": header.records * 256, "units": "uV",
                      "labels": [[1] * header.records] * 3,
                      "quality_flags": [True] + [False] * (header.records - 2) + [True]}
            for second in (29, header.records - 1):
                payload = self.source.current._payload(description, b"generated-case-key" * 3,
                                                       record, second, 2, reader)
                self.assert_samples(payload["samples"], (second - 29) * 256, (second + 1) * 256)
                self.assertEqual(payload["sample_clock"], {"first_tick": 0, "step_ticks": 1,
                                                          "ticks_per_second": 256})
                self.assertEqual(payload["quality_flags"], record["quality_flags"][second - 29:second + 1])
                self.assertEqual(payload["prediction_interval_seconds"], [29, 30])
                self.assertNotIn("labels", payload)
                self.assertNotIn("source_lineage", payload)

    def test_cache_reads_only_the_requested_records_and_clear_reloads(self):
        with self.asset() as (asset, header):
            reader = self.reader(asset, header)
            with patch.object(adapter, "read_calibrated_record", wraps=adapter.read_calibrated_record) as read:
                reader("eeg1", 253, 261)
                reader("eeg1", 254, 260)
                self.assertEqual([call.args[2] for call in read.call_args_list], [0, 1])
                reader.clear()
                reader("eeg1", 256, 257)
                self.assertEqual([call.args[2] for call in read.call_args_list], [0, 1, 1])

    def test_zero_cache_and_bounded_eviction(self):
        with self.asset() as (asset, header):
            no_cache = self.reader(asset, header, cache_records=0)
            one = self.reader(asset, header, cache_records=1)
            self.assertEqual(no_cache("eeg1", 250, 270), one("eeg1", 250, 270))
            self.assertEqual(len(no_cache._cache), 0)
            self.assertEqual(len(one._cache), 1)

    def test_changed_lookup_asset_cannot_return_old_cached_values(self):
        with self.asset() as first, self.asset(self.other_row) as second:
            selected = [first]
            reader = adapter.IntervalReader(lambda _rid: selected[0], self.source.intake.MONTAGE)
            self.assert_samples(reader("eeg1", 0, 5), 0, 5)
            selected[0] = second
            try:
                actual = reader("eeg1", 0, 5)
            except (ValueError, OSError):
                return  # Explicitly refusing the changed source is also correct.
            self.assert_samples(actual, 0, 5, shift=1)

    def test_changed_lookup_header_cannot_reuse_old_cached_calibration(self):
        with self.asset() as (asset, header):
            selected = [header]
            reader = adapter.IntervalReader(lambda _rid: (asset, selected[0]), self.source.intake.MONTAGE)
            before = reader("eeg1", 0, 2)
            changed = list(header.channels)
            index = dict(header.electrode_indices)["Fp2"]
            channel = changed[index]
            changed[index] = replace(channel, minimum=channel.minimum + 10, maximum=channel.maximum + 10)
            selected[0] = replace(header, channels=tuple(changed))
            try:
                actual = reader("eeg1", 0, 2)
            except (ValueError, OSError):
                return
            expected = [list(row) for row in before]
            for row in expected:
                row[0] += 10
                row[8] += 10
            self.assertEqual([list(row) for row in actual], expected)

    def test_cached_source_mutation_is_refused(self):
        # A separate generated copy avoids changing another control's fixture.
        path = self.root / "mutable.edf"
        path.write_bytes((self.root / self.row["name"]).read_bytes())
        row = dict(self.row, name=path.name)
        try:
            with self.asset(row) as (asset, header):
                reader = self.reader(asset, header)
                reader("eeg1", 0, 2)
                with path.open("r+b") as handle:
                    handle.seek(-1, os.SEEK_END)
                    handle.write(b"\x7f")
                with self.assertRaises(ValueError):
                    reader("eeg1", 0, 2)
        finally:
            path.unlink()

    def test_interval_and_identifier_refusals(self):
        with self.asset() as (asset, header):
            reader = self.reader(asset, header)
            invalid = (("eeg0", 0, 1), ("eeg01", 0, 1), ("eeg80", 0, 1),
                       ("eeg1", True, 1), ("eeg1", 0, False), ("eeg1", -1, 1),
                       ("eeg1", 2, 2), ("eeg1", 3, 2), ("eeg1", 0, 7681),
                       ("eeg1", 8191, 8193), ("eeg1", 0.0, 1))
            for args in invalid:
                with self.subTest(args=args), self.assertRaises(loader.SourceError):
                    reader(*args)

    def test_montage_and_cache_bound_refusals(self):
        with self.asset() as (asset, header):
            for bound in (-1, 32, True, 1.0):
                with self.subTest(bound=bound), self.assertRaises(loader.SourceError):
                    self.reader(asset, header, cache_records=bound)
            with self.assertRaises(loader.SourceError):
                adapter.IntervalReader(lambda _rid: (asset, header), tuple(reversed(self.source.intake.MONTAGE)))


class QualityControls(unittest.TestCase):
    def test_zero_flat_and_varying_are_separate_states(self):
        zero = [[0] * 18 for _ in range(256)]
        flat = [[j + n for j in range(18)] for n in range(256)]
        for row in flat:
            row[3] = 7
        varying = [[j + n for j in range(18)] for n in range(256)]
        self.assertEqual(adapter.flags_for_record(zero), (True, True))
        self.assertEqual(adapter.flags_for_record(flat), (False, True))
        self.assertEqual(adapter.flags_for_record(varying), (False, False))

    def test_nonfinite_boolean_and_incomplete_record_refused(self):
        for value in (True, float("nan"), float("inf"), "0"):
            rows = [[1] * 18 for _ in range(256)]
            rows[10][4] = value
            with self.subTest(value=value), self.assertRaises(loader.SourceError):
                adapter.flags_for_record(rows)
        for rows in ([], [[0] * 18] * 255, [[0] * 17] * 256):
            with self.assertRaises(loader.SourceError):
                adapter.flags_for_record(rows)

    def test_exact_retained_quality_rule_parity_on_generated_records(self):
        source = loader.load_sources()
        sequences = []
        for second in range(30):
            if second == 3:
                rows = [[0] * 18 for _ in range(256)]
            else:
                rows = [[channel + sample for channel in range(18)] for sample in range(256)]
                if second == 29:
                    for row in rows:
                        row[5] = 12
            sequences.append(rows)
        channel_major = tuple(tuple(row[c] for block in sequences for row in block) for c in range(18))
        old = source.intake.derive_quality_flags(channel_major)
        self.assertEqual([adapter.flags_for_record(block)[0] for block in sequences], list(old.zero_bipolar))
        self.assertEqual([adapter.flags_for_record(block)[1] for block in sequences], list(old.any_flatline))


class CompleteAccountingControls(unittest.TestCase):
    """Plumbing control only: replace source custody with invented boundary data."""
    @classmethod
    def setUpClass(cls):
        cls.sources = loader.load_sources()
        profiles = cls.sources.profile.source_profiles()
        cls.durations = {i: row["declared_records"] for i, row in profiles["headers"].items()}
        asset_shas = {name: hashlib.sha256(("INVENTED:" + name).encode()).hexdigest()
                      for name in profiles["manifest"]}
        # Preserve public profile identities so the real lineage validator runs.
        # The patched Corpus below is explicitly NOT authentic source admission.
        asset_shas.update({name: row["actual_sha256"] for name, row in profiles["annotations"].items()})
        cls.lineage = {
            "manifest_sha256": cls.sources.profile.PINS["release_manifest.json"],
            "assets": asset_shas,
            "headers": {str(i): row["observed_header_sha256"] for i, row in profiles["headers"].items()},
            "durations": {str(i): n for i, n in cls.durations.items()},
            "profile": cls.sources.profile.profile_identity(), "support": cls.sources.profile.complete_support(),
        }
        cls.read_counts = {"eeg" + str(i): 0 for i in range(1, 80)}
        cls.clear_count = 0
        cls.close_count = 0
        cls.annotations = {i: [(i % 2, 0, 1)] * (n - 1) + [(0, 1, i % 2)]
                           for i, n in cls.durations.items()}

        class InventedCorpus:
            def __init__(self, *_):
                self.assets = {"eeg" + str(i) + ".edf": SimpleNamespace(
                    name="eeg" + str(i) + ".edf", sha256=asset_shas["eeg" + str(i) + ".edf"])
                    for i in range(1, 80)}
                self.headers = {i: SimpleNamespace(records=n, sha256=cls.lineage["headers"][str(i)])
                                for i, n in cls.durations.items()}
                self.annotations = cls.annotations

            def lineage(self):
                return cls.lineage

            def close(self):
                cls.close_count += 1

        class InventedReader:
            def __init__(self, lookup, montage):
                self.lookup = lookup

            def __call__(self, rid, start, stop):
                if start != cls.read_counts[rid] * 256 or stop != start + 256:
                    raise AssertionError("source seconds skipped, duplicated or reordered")
                cls.read_counts[rid] += 1
                return int(rid[3:]), start // 256

            def clear(self):
                cls.clear_count += 1

        def invented_flags(marker):
            infant, second = marker
            return second == 0, second in (0, cls.durations[infant] - 1)

        # Do not mock each call: recording 402,825 MagicMock calls needlessly
        # increases memory and obscures the actual one-pass coverage assertion.
        with patch.object(cls.sources.intake, "Corpus", InventedCorpus), \
                patch.object(adapter, "IntervalReader", InventedReader), \
                patch.object(adapter, "flags_for_record", invented_flags):
            cls.corpus = adapter.SourceCorpus("unused-generated-boundary")
            cls.census = cls.corpus.private_census()
            cls.corpus.close()
            cls.corpus.close()
        folds = cls.sources.current.fold_map(adapter.RECORD_IDS, "independent-generated-control-v1")
        cls.policy = {"schema": "helsinki-source-preparation-policy-v1",
                      "assessment_id": "generated-control-not-authentic",
                      "fold_seed": "independent-generated-control-v1",
                      "development_by_fold": {str(f): [next(rid for rid in adapter.RECORD_IDS
                                                            if folds[rid] != f)] for f in range(5)}}

    def test_complete_one_pass_keeps_every_infant_second_and_three_streams(self):
        census = self.census
        self.assertEqual((census["infants"], census["experts"], census["record_seconds"],
                          census["primary_cases"]), (79, 3, 402825, 400534))
        self.assertEqual(sum(self.read_counts.values()), 402825)
        self.assertEqual((self.clear_count, self.close_count), (2, 1))
        self.assertEqual([r["recording_id"] for r in census["records"]], list(adapter.RECORD_IDS))
        for i, row in enumerate(census["records"], 1):
            with self.subTest(infant=i):
                count = self.durations[i]
                self.assertEqual(self.read_counts["eeg" + str(i)], count)
                self.assertEqual(row["sample_count"], count * 256)
                self.assertEqual((row["primary_cases"], row["first_primary_record_second"],
                                  row["last_primary_record_second"]), (count - 29, 29, count - 1))
                self.assertEqual(row["zero_bipolar"], [True] + [False] * (count - 1))
                self.assertEqual(row["any_flatline"], [True] + [False] * (count - 2) + [True])
                for expert in range(3):
                    self.assertEqual(row["labels"][expert], [v[expert] for v in self.annotations[i]])
        self.assertFalse(census["physical_clock_verified"])
        self.assertFalse(census["clinical_or_TAL_continuity_verified"])
        self.assertFalse(census["quality_detector_validated"])
        with self.assertRaises(loader.SourceError):
            self.corpus.private_census()
        with self.assertRaises(loader.SourceError):
            self.corpus._lookup("eeg1")

    def test_projection_preserves_full_support_flags_and_current_fold_contract(self):
        description = adapter.current_description(self.census, self.policy)
        self.assertEqual(description["protocol_id"], self.sources.current.PROTOCOL)
        self.assertEqual(description["development_by_fold"], self.policy["development_by_fold"])
        self.assertEqual(description["fold_seed"], self.policy["fold_seed"])
        self.assertEqual(len(description["recordings"]), 79)
        self.assertEqual(sum(r["sample_count"] // 256 - 29 for r in description["recordings"]), 400534)
        for source, result in zip(self.census["records"], description["recordings"]):
            self.assertEqual(result["labels"], source["labels"])
            self.assertEqual(result["quality_flags"], [a or b for a, b in
                                                       zip(source["zero_bipolar"], source["any_flatline"])])
            self.assertEqual(result["sample_zero_annotation_second"], 0)
            self.assertEqual(result["sample_rate"], {"num": 256, "den": 1})
        description["recordings"][0]["labels"][0][0] = 9
        self.assertIn(self.census["records"][0]["labels"][0][0], (0, 1))

    def test_projection_refuses_missing_roster_changed_geometry_flags_labels_and_fold_leakage(self):
        def replace_first(**changes):
            rows = list(self.census["records"])
            rows[0] = dict(rows[0], **changes)
            return dict(self.census, records=rows)

        count = self.durations[1]
        invalid = [dict(self.census, records=self.census["records"][:-1]),
                   dict(self.census, record_seconds=402824),
                   dict(self.census, record_seconds=True),
                   dict(self.census, physical_clock_verified=True),
                   dict(self.census, quality_detector_validated=True),
                   replace_first(sample_count=count * 256 - 1),
                   replace_first(record_seconds=count - 1),
                   replace_first(source_sha256="0" * 64),
                   replace_first(header_sha256="0" * 64),
                   replace_first(any_flatline=[False] * count),
                   replace_first(zero_bipolar=[False] * (count - 1)),
                   replace_first(labels=[[0] * count, [0] * count]),
                   replace_first(labels=[[False] * count, [0] * count, [0] * count])]
        for index, census in enumerate(invalid):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                adapter.current_description(census, self.policy)
        folds = self.sources.current.fold_map(adapter.RECORD_IDS, self.policy["fold_seed"])
        development = dict(self.policy["development_by_fold"])
        development["0"] = [next(rid for rid in adapter.RECORD_IDS if folds[rid] == 0)]
        with self.assertRaises(ValueError):
            adapter.current_description(self.census, dict(self.policy, development_by_fold=development))

    def test_coordinate_binding_is_pinned_and_caller_cannot_override(self):
        import coordinate
        binding = coordinate.load_coordinate_binding()
        self.assertEqual(binding["source_coordinate"], adapter.COORDINATE)
        self.assertEqual(binding["exact_EDF_C_without_TAL_exceptions"], [4, 29, 50])
        self.assertFalse(binding["scientific_qualification"])
        with self.assertRaises(loader.SourceError):
            adapter.current_description(self.census, self.policy,
                                        dict(binding, clinical_clock_or_EDF_TAL_reconstruction="verified"))


class AnnotationControls(unittest.TestCase):
    """Retained parser controls with small invented values, never expert labels."""
    def rows(self):
        durations = {i: 30 + i % 2 for i in range(1, 80)}
        rows = [[str(i) for i in range(1, 80)]]
        rows.extend([[str((i + second) % 2) if second < durations[i] else ""
                      for i in range(1, 80)] for second in range(31)])
        return durations, rows

    @staticmethod
    def body(rows):
        return ("\n".join(",".join(row) for row in rows) + "\n").encode("ascii")

    def test_identifier_header_does_not_shift_second_zero_and_padding_is_not_a_label(self):
        source = loader.load_sources()
        durations, rows = self.rows()
        labels = source.intake.parse_recorded_grid_csv(io.BytesIO(self.body(rows)), durations, 31)
        self.assertEqual(set(labels), set(range(1, 80)))
        for i in range(1, 80):
            self.assertEqual(labels[i], tuple((i + second) % 2 for second in range(durations[i])))
            self.assertEqual(labels[i][0], i % 2)
            self.assertEqual(len(labels[i]), durations[i])

    def test_csv_refuses_header_guessing_interior_missingness_nonbinary_and_nonempty_padding(self):
        source = loader.load_sources()
        durations, rows = self.rows()
        invalid = [rows[1:], rows[:-1], [list(reversed(rows[0]))] + rows[1:]]
        for row_index, column_index, value in ((1, 0, ""), (1, 0, "2"), (31, 1, "0")):
            changed = [list(row) for row in rows]
            changed[row_index][column_index] = value
            invalid.append(changed)
        invalid.append([rows[0]] + [rows[1][:-1]] + rows[2:])
        for index, changed in enumerate(invalid):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                source.intake.parse_recorded_grid_csv(io.BytesIO(self.body(changed)), durations, 31)

    def test_corrected_a_name_and_complete_source_pins_cannot_be_replaced_by_generated_file(self):
        source = loader.load_sources()
        profiles = source.profile.source_profiles()
        self.assertEqual(set(profiles["annotations"]), {
            "annotations_2017_A_fixed.csv", "annotations_2017_B.csv", "annotations_2017_C.csv"})
        durations = {i: row["declared_records"] for i, row in profiles["headers"].items()}
        _, rows = self.rows()
        body = self.body(rows)
        with tempfile.TemporaryDirectory() as directory:
            for name in ("annotations_2017_A_fixed.csv", "annotations_2017_A.csv"):
                path = Path(directory) / name
                path.write_bytes(body)
                row = {"name": name, "bytes": len(body),
                       "md5": hashlib.md5(body, usedforsecurity=False).hexdigest()}
                asset = source.intake.Asset(directory, row)
                try:
                    with patch.object(source.intake, "parse_recorded_grid_csv",
                                      side_effect=AssertionError("unadmitted source reached parser")):
                        with self.subTest(name=name), self.assertRaises(ValueError):
                            source.intake.load_recorded_grid_annotations(asset, durations)
                finally:
                    asset.close()


class FileBoundaryControls(unittest.TestCase):
    def test_strict_json_accepts_valid_and_rejects_duplicate_nonfinite_and_large(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b'{"a": [1, false, null]}')
            self.assertEqual(adapter.bounded_json(path), {"a": [1, False, None]})
            for body in (b'{"a": 1, "a": 2}', b'{"a": NaN}', b'{"a": Infinity}', b'\xff'):
                path.write_bytes(body)
                with self.subTest(body=body), self.assertRaises(loader.SourceError):
                    adapter.bounded_json(path)
            path.write_bytes(b"[] " * 10)
            with self.assertRaises(loader.SourceError):
                adapter.bounded_json(path, limit=8)

    def test_json_symlink_and_hardlink_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input.json"
            path.write_bytes(b"{}")
            link = Path(directory) / "alias.json"
            link.symlink_to(path)
            with self.assertRaises((loader.SourceError, OSError)):
                adapter.bounded_json(link)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(loader.SourceError):
                adapter.bounded_json(path)

    def test_private_output_is_new_and_mode_0600_even_under_open_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.json"
            previous = os.umask(0)
            try:
                adapter.write_private_new(path, {"private": "generated"})
            finally:
                os.umask(previous)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            before = path.read_bytes()
            with self.assertRaises(loader.SourceError):
                adapter.write_private_new(path, {"private": "changed"})
            self.assertEqual(path.read_bytes(), before)

    def test_private_output_does_not_follow_dangling_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "victim.json"
            link = Path(directory) / "output.json"
            link.symlink_to(destination)
            with self.assertRaises((loader.SourceError, OSError)):
                adapter.write_private_new(link, {"x": 1})
            self.assertFalse(destination.exists())
            self.assertTrue(link.is_symlink())


if __name__ == "__main__":
    unittest.main()
