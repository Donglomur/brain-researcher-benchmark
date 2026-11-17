"""Independent generated controls for original ICNet input construction.

No real recordings or model are used. One test writes the complete original
geometry, then independently checks every prepared animal/sound/trial output.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("icnet_intake_under_test", HERE / "source.py")
source = importlib.util.module_from_spec(spec)
spec.loader.exec_module(source)
sys.modules["source"] = source
spec = importlib.util.spec_from_file_location("predictions", HERE / "predictions.py")
predictions = importlib.util.module_from_spec(spec)
sys.modules["predictions"] = predictions
spec.loader.exec_module(predictions)
spec = importlib.util.spec_from_file_location("icnet_grade_under_test", HERE / "grade.py")
grade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(grade)

ANIMALS = tuple(range(3, 10))
SOUNDS = ("speech_in_quiet", "speech_in_noise", "moving_ripples", "music")
N_BINS = 22784
N_SAMPLES = 729088
N_UNITS = 512
FS = 24414.0625
CONTROL_BYTES_CREATED = 0
POLICY = {"schema": "icnet-original-preparation-policy/v1",
          "measurement_time_sound_order": list(SOUNDS),
          "mask_policy": "finite_source_characteristic_frequencies",
          "mask_evidence_sha256": "1" * 64, "alignment_review_sha256": "2" * 64}


def element(kind, data, small=False):
    if small:
        assert 0 < len(data) <= 4
        return struct.pack("<I", kind | (len(data) << 16)) + data.ljust(4, b"\0")
    return struct.pack("<II", kind, len(data)) + data + b"\0" * (-len(data) % 8)


def prefix(name, shape, matlab_class, storage_type, payload_bytes):
    """MAT-v5 record writer, independent of the production reader."""
    flags = element(6, struct.pack("<II", matlab_class, 0))
    dimensions = element(5, struct.pack("<" + "i" * len(shape), *shape))
    encoded_name = name.encode("ascii")
    variable_name = element(1, encoded_name, small=len(encoded_name) <= 4)
    real_header = struct.pack("<II", storage_type, payload_bytes)
    body_length = len(flags) + len(dimensions) + len(variable_name) + 8 + payload_bytes + (-payload_bytes % 8)
    return struct.pack("<II", 14, body_length) + flags + dimensions + variable_name + real_header


def header():
    return b"MATLAB 5.0 MAT-file, independently generated test fixture".ljust(116, b" ") + b"\0" * 8 + b"\x00\x01IM"


def tiny_matrix(name="fs", array=None, matlab_class=6, storage_type=9):
    value = np.array([[FS]], dtype="<f8") if array is None else array
    body = value.tobytes(order="F")
    return prefix(name, value.shape, matlab_class, storage_type, len(body)) + body + b"\0" * (-len(body) % 8)


def write_small(path, matrices=None):
    body = header() + (tiny_matrix() if matrices is None else b"".join(matrices))
    path.write_bytes(body)
    return len(body), hashlib.md5(body).hexdigest()


def file_md5(path):
    digest = hashlib.md5()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cf_values():
    values = 1000.0 + 100.0 * np.arange(7)[:, None] + np.arange(N_UNITS)[None, :]
    values[:6, 496:] = -np.inf
    values[6, 500:] = -np.inf
    return values


def time_values(trial):
    return 1000.0 * trial + 100.0 * np.arange(7)[:, None] + 10.0 * np.arange(4)[None, :] + 0.25


def count_values(ai, times, units, trial, si):
    return ((ai + np.asarray(times) % 5 + np.asarray(units) % 7 + 2 * trial + 3 * si) % 16).astype(np.int8)


def write_trial(path, trial):
    with path.open("xb") as stream:
        stream.write(header())
        for si, sound in enumerate(SOUNDS):
            stream.write(prefix(sound, (7, N_BINS, N_UNITS), 8, 1, 7 * N_BINS * N_UNITS))
            for first in range(0, N_UNITS, 32):
                values = count_values(np.arange(7, dtype=np.int16)[:, None, None],
                                      np.arange(N_BINS, dtype=np.int16)[None, :, None],
                                      np.arange(first, first + 32, dtype=np.int16)[None, None, :], trial, si)
                stream.write(values.tobytes(order="F"))
        for name, value, cls, dtype in (
            ("measurement_times", time_values(trial), 6, 9),
            ("channel_CFs", cf_values(), 6, 9),
            ("animals", np.array([ANIMALS], dtype="<i8"), 14, 12),
            ("fs", np.array([[FS / 32]], dtype="<f8"), 6, 9),
        ):
            stream.write(tiny_matrix(name, value, cls, dtype))


def sound_values(si):
    return ((np.arange(N_SAMPLES, dtype=np.int32) % 101 - 50) * 1e-5 + si * 0.001).astype("<f4")


def write_audio(path):
    with path.open("xb") as stream:
        stream.write(header())
        for si, name in enumerate(SOUNDS):
            stream.write(tiny_matrix(name, sound_values(si)[None, :], 7, 7))
        stream.write(tiny_matrix("fs"))


def writable_rmtree(path):
    for directory, children, _ in os.walk(path):
        Path(directory).chmod(0o700)
        for child in children:
            (Path(directory) / child).chmod(0o700)
    shutil.rmtree(path)


def independent_json(path, document):
    global CONTROL_BYTES_CREATED
    path.write_text(json.dumps(document, sort_keys=True, allow_nan=False) + "\n")
    CONTROL_BYTES_CREATED += path.stat().st_size
    return hashlib.sha256(path.read_bytes()).hexdigest()


def independent_array(root, name, array):
    global CONTROL_BYTES_CREATED
    path = root / name
    with path.open("wb") as stream:
        np.save(stream, array, allow_pickle=False)
    CONTROL_BYTES_CREATED += path.stat().st_size
    return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def public_document(time_bins=N_BINS, audio_samples=N_SAMPLES):
    fake = {"path": "fixture.npy", "sha256": "0" * 64}
    return {"schema": "icnet-original-public-panel/v1", "animals": {
        str(animal): {"unit_ids": [f"animal_{animal}:original_column_{i}" for i in range(N_UNITS)],
                      "characteristic_frequencies": dict(fake)} for animal in ANIMALS},
        "cases": [{"animal": animal, "sound": sound, "time_bins": time_bins,
                   "measurement_times_seconds": [float(time_values(t)[ai, si]) for t in (1, 2)]}
                  for ai, animal in enumerate(ANIMALS) for si, sound in enumerate(SOUNDS)],
        "sounds": {sound: dict(fake) for sound in SOUNDS}, "fs_audio": FS, "fs_neural": FS / 32,
        "time_bins": time_bins, "audio_samples": audio_samples,
        "split": "original_four_sounds_held_out_from_training", "qualification": "input_preparation_only",
        "source_files": [{"filename": name, "bytes": row[0], "authenticated_md5": "0" * 32,
                          "sha256": "1" * 64} for name, row in source.SOURCE_FILES.items()]}


class DirectoryControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def parse(self, body):
        return source.mat_directory(io.BytesIO(body), len(body))

    def test_real_small_name_scalar_and_fortran_layout(self):
        values = np.arange(42, dtype=np.int8).reshape((7, 3, 2), order="C")
        path = self.root / "generated.mat"
        expected = write_small(path, [tiny_matrix("speech_in_quiet", values, 8, 1), tiny_matrix()])
        fields = {"speech_in_quiet": ((7, 3, 2), "i1", 8), "fs": ((1, 1), "<f8", 6)}
        with source.MatFile(path, expected, fields) as native:
            np.testing.assert_array_equal(native.array("speech_in_quiet"), values)
            self.assertEqual(float(native.array("fs")[0, 0]), FS)

    def test_non_original_header_and_compressed_container_refused(self):
        for body in (b"not MAT".ljust(128, b" "),
                     header()[:-2] + b"MI" + tiny_matrix(),
                     header() + element(15, b"zlib is not an admitted source format")):
            with self.subTest(body=body[:20]), self.assertRaises(source.InputError):
                self.parse(body)

    def test_truncation_bad_extent_and_unknown_variable_refused(self):
        valid = header() + tiny_matrix()
        too_long = bytearray(valid)
        struct.pack_into("<I", too_long, 132, 400000000)
        for body in (valid[:-1], bytes(too_long), header() + tiny_matrix("other"),
                     valid + b"trailing", valid + tiny_matrix()):
            with self.assertRaises(source.InputError):
                self.parse(body)

    def test_non_numeric_flags_and_inconsistent_storage_refused(self):
        for cls in (6 | 0x800, 6 | 0x200, 4, 2):
            with self.assertRaises(source.InputError):
                self.parse(header() + tiny_matrix(matlab_class=cls))
        wrong = header() + prefix("fs", (1, 2), 6, 9, 8) + struct.pack("<d", FS)
        with self.assertRaises(source.InputError):
            self.parse(wrong)

    def test_publisher_size_digest_and_schema_fail_closed(self):
        path = self.root / "generated.mat"
        expected = write_small(path)
        for admitted in ((expected[0] + 1, expected[1]), (expected[0], "0" * 32)):
            with self.assertRaises(source.InputError):
                source.MatFile(path, admitted, {"fs": ((1, 1), "<f8", 6)})
        with self.assertRaises(source.InputError):
            source.MatFile(path, expected, {"fs": ((1, 2), "<f8", 6)})
        with self.assertRaises(source.InputError):
            source.MatFile(path, expected, {"fs": ((1, 1), "<f8", 6), "animals": ((1, 7), "<i8", 14)})

    def test_open_descriptor_detects_subsequent_source_mutation(self):
        path = self.root / "generated.mat"
        expected = write_small(path)
        with source.MatFile(path, expected, {"fs": ((1, 1), "<f8", 6)}) as native:
            with path.open("r+b") as stream:
                stream.seek(-8, os.SEEK_END); stream.write(struct.pack("<d", 1.0))
            with self.assertRaises(source.InputError):
                native.array("fs")

    def test_symlink_and_hardlink_inputs_refused(self):
        path = self.root / "ordinary.json"
        path.write_text("{}")
        link = self.root / "symbolic.json"; link.symlink_to(path)
        with self.assertRaises((OSError, source.InputError)):
            source.read_json(link)
        hard = self.root / "hard.json"; os.link(path, hard)
        for candidate in (hard, path):
            with self.assertRaises(source.InputError):
                source.read_json(candidate)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "POSIX FIFO boundary")
    def test_fifo_refused_before_waiting_for_a_writer(self):
        fifo = self.root / "input.json"; os.mkfifo(fifo)
        code = ("import sys;sys.path.insert(0,sys.argv[1]);import source;"
                "source.read_json(sys.argv[2])")
        result = subprocess.run([sys.executable, "-B", "-c", code, str(HERE), str(fifo)],
                                capture_output=True, timeout=5)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b"ordinary", result.stderr)

    def test_bounded_duplicate_and_nonfinite_json_refused(self):
        for index, body in enumerate((b'{"a":1,"a":2}', b'{"a":NaN}', b" " * 100)):
            path = self.root / f"bad{index}.json"; path.write_bytes(body)
            with self.assertRaises(source.InputError):
                source.read_json(path, maximum=50)

    def test_policy_has_no_implicit_mapping_mask_or_extra_fields(self):
        source.validate_policy(POLICY)
        permutation = copy.deepcopy(POLICY)
        permutation["measurement_time_sound_order"].reverse()
        source.validate_policy(permutation)
        cases = []
        for order in ([*SOUNDS[:3]], [SOUNDS[0]] * 4, [*SOUNDS[:3], "foreign_sound"], "music", [True, *SOUNDS[:3]]):
            p = copy.deepcopy(POLICY); p["measurement_time_sound_order"] = order; cases.append(p)
        p = copy.deepcopy(POLICY); p["mask_policy"] = "select_from_test_reliability"; cases.append(p)
        p = copy.deepcopy(POLICY); p["mask_evidence_sha256"] = None; cases.append(p)
        p = copy.deepcopy(POLICY); p["allow_missing_animal"] = True; cases.append(p)
        for p in cases:
            with self.assertRaises(source.InputError):
                source.validate_policy(p)

    def test_existing_destination_is_never_overwritten(self):
        destination = self.root / "already"; destination.mkdir()
        sentinel = destination / "sentinel"; sentinel.write_text("unchanged")
        with self.assertRaises(source.InputError):
            source.prepare(self.root / "absent", destination, POLICY)
        self.assertEqual(sentinel.read_text(), "unchanged")


class MetadataBoundaryControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def run_bad(self, mutate):
        data = {}
        for ti in (1, 2):
            data[f"IC_data_trial{ti}.mat"] = {"animals": np.array([ANIMALS], dtype="<i8"),
                "fs": np.array([[FS / 32]]), "channel_CFs": cf_values(),
                "measurement_times": time_values(ti)}
        data["sound_data.mat"] = {"fs": np.array([[FS]])}
        mutate(data)
        class FakeNative:
            def __init__(self, path, *args): self.name = Path(path).name
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def array(self, name): return data[self.name][name]
        with mock.patch.object(source, "MatFile", FakeNative), self.assertRaises(source.InputError):
            source.prepare(self.root, self.root / "new", POLICY)
        self.assertFalse((self.root / "new").exists())

    def test_animal_axis_and_sample_rates_are_not_silently_rewritten(self):
        self.run_bad(lambda data: data["IC_data_trial1.mat"].update(animals=np.array([ANIMALS[::-1]])))
        self.run_bad(lambda data: data["IC_data_trial2.mat"].update(fs=np.array([[FS]])))
        self.run_bad(lambda data: data["sound_data.mat"].update(fs=np.array([[24000.0]])))

    def test_both_trials_must_share_exact_original_unit_metadata(self):
        def bad(data): data["IC_data_trial2.mat"]["channel_CFs"][0, 0] += 1.0
        self.run_bad(bad)

    def test_nonfinite_or_negative_metadata_and_wrong_mask_census_refused(self):
        for value in (-1.0, np.nan, np.inf):
            def bad(data, value=value):
                for ti in (1, 2): data[f"IC_data_trial{ti}.mat"]["channel_CFs"][0, 0] = value
            self.run_bad(bad)
        def less(data):
            for ti in (1, 2): data[f"IC_data_trial{ti}.mat"]["channel_CFs"][0, 0] = -np.inf
        self.run_bad(less)
        self.run_bad(lambda data: data["IC_data_trial2.mat"]["measurement_times"].__setitem__((6, 3), -0.25))

    def test_source_negative_infinity_mask_exports_all_columns_in_reduced_time_control(self):
        # The publisher-MD5-verified metadata established 108 negative-infinity
        # exclusions. Exercise this corrected branch without repeating the
        # already completed original-size MAT geometry control. The MAT file
        # boundary and only temporal constants are mocked explicitly here.
        class GeneratedNative:
            def __init__(self, path, *args): self.name = Path(path).name
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def check(self): pass
            def descriptor(self):
                return {"filename": self.name, "bytes": source.SOURCE_FILES[self.name][0],
                        "sha256": "1" * 64, "authenticated_md5": "0" * 32}
            def array(self, name):
                if self.name == "sound_data.mat":
                    return np.array([[FS]]) if name == "fs" else np.zeros((1, 256), dtype=np.float32)
                trial = 1 if self.name == "IC_data_trial1.mat" else 2
                metadata = {"animals": np.array([ANIMALS], dtype=np.int64), "fs": np.array([[FS / 32]]),
                            "channel_CFs": cf_values(), "measurement_times": time_values(trial)}
                if name in metadata: return metadata[name]
                return count_values(np.arange(7)[:, None, None], np.arange(8)[None, :, None],
                                    np.arange(N_UNITS)[None, None, :], trial, SOUNDS.index(name))
        destination = self.root / "reduced-source-mask"
        expected = {name: (row[0], "0" * 32) for name, row in source.SOURCE_FILES.items()}
        policy = copy.deepcopy(POLICY)
        policy["measurement_time_sound_order"] = list(reversed(SOUNDS))
        try:
            with mock.patch.object(source, "MatFile", GeneratedNative), mock.patch.object(source, "TIME_BINS", 8), \
                    mock.patch.object(source, "AUDIO_SAMPLES", 256):
                result = source.prepare(self.root, destination, policy, _expected_files=expected)
            private = source.read_json(result["private_reference"])
            self.assertEqual((result["n_animals"], result["n_cases"], result["n_trials"]), (7, 28, 56))
            self.assertEqual(result["eligible_units"], 3476)
            self.assertEqual(private["source_authentication"], "generated_test_descriptors")
            for ai, animal in enumerate(ANIMALS):
                self.assertEqual(private["animals"][str(animal)]["eligible_mask"], np.isfinite(cf_values()[ai]).tolist())
                actual = np.load(destination / "public" / f"animal_{animal}_cf.npy", allow_pickle=False)
                np.testing.assert_array_equal(actual, cf_values()[ai])
            self.assertEqual(int(np.isneginf(cf_values()).sum()), 108)
            for case in private["cases"]:
                ai, si = ANIMALS.index(case["animal"]), SOUNDS.index(case["sound"])
                time_column = policy["measurement_time_sound_order"].index(case["sound"])
                self.assertEqual(case["measurement_times_seconds"],
                                 [float(time_values(trial)[ai, time_column]) for trial in (1, 2)])
                for trial in (1, 2):
                    actual = np.load(destination / "private" / case["arrays"][f"recorded_trial{trial}"]["path"],
                                     allow_pickle=False)
                    expected_array = count_values(ai, np.arange(8)[:, None], np.arange(N_UNITS)[None, :], trial, si)
                    np.testing.assert_array_equal(actual, expected_array)
        finally:
            if destination.exists():
                generated_bytes = sum(path.stat().st_size for path in destination.rglob("*") if path.is_file())
                writable_rmtree(destination)
                report = os.environ.get("ICNET_NEGATIVE_CF_ACCOUNTING")
                if report:
                    with Path(report).open("x") as stream:
                        json.dump({"scope": "generated eight-bin source preparation; mocked MAT boundary",
                                   "sound_column_order": policy["measurement_time_sound_order"],
                                   "negative_infinity_exclusions": 108, "generated_logical_bytes": generated_bytes,
                                   "retained_fixture_bytes_after_cleanup": 0}, stream, indent=2)
                        stream.write("\n")


class ProbabilityControls(unittest.TestCase):
    def test_restore_original_columns_without_sorting_ambiguous_cf_ties(self):
        columns = np.roll(np.arange(N_UNITS)[::-1], 19).tolist()
        original = (np.arange(7)[:, None] + np.arange(N_UNITS)[None, :]) % 5
        p = np.eye(5, dtype=np.float32)[original[:, columns]]
        draws, means = predictions.convert_block(p, columns, np.random.default_rng(9))
        np.testing.assert_array_equal(draws, original)
        np.testing.assert_array_equal(means, original)
        self.assertEqual(draws.dtype, np.dtype("int8"))
        self.assertEqual(means.dtype, np.dtype("float64"))

    def test_expectation_is_weighted_mean_and_samples_remain_distinct(self):
        probabilities = np.broadcast_to(np.array([0.25, 0.125, 0.125, 0.25, 0.25]), (9, N_UNITS, 5))
        draws, means = predictions.convert_block(probabilities, list(range(N_UNITS)), np.random.default_rng(98))
        np.testing.assert_array_equal(means, np.full((9, N_UNITS), 2.125))
        self.assertTrue(np.all((draws >= 0) & (draws <= 4)))
        self.assertGreater(len(np.unique(draws)), 1)
        self.assertFalse(np.array_equal(means, draws))

    def test_categorical_draws_and_means_are_chunk_partition_invariant(self):
        rng = np.random.default_rng(73)
        p = rng.random((31, N_UNITS, 5)); p /= p.sum(axis=-1, keepdims=True)
        columns = rng.permutation(N_UNITS).tolist()
        whole = predictions.convert_block(p, columns, np.random.default_rng(674))
        streaming_rng = np.random.default_rng(674)
        parts = [predictions.convert_block(p[a:b], columns, streaming_rng)
                 for a, b in ((0, 1), (1, 8), (8, 27), (27, 31))]
        for index in (0, 1):
            np.testing.assert_array_equal(whole[index], np.concatenate([part[index] for part in parts]))

    def test_invalid_probabilities_and_column_permutations_refused(self):
        p = np.full((2, N_UNITS, 5), 0.2)
        cases = [p.astype("int8"), p[:, :511], p[:, :, :4], p[:0], np.full_like(p, 0.19)]
        for value in (np.nan, np.inf, -0.1, 1.1):
            altered = p.copy(); altered[0, 0, 0] = value; cases.append(altered)
        for value in cases:
            with self.assertRaises(source.InputError):
                predictions.convert_block(value, list(range(N_UNITS)), np.random.default_rng(1))
        for columns in (list(range(511)), [0] * 512, [True, *range(1, 512)], list(range(1, 513))):
            with self.assertRaises(source.InputError):
                predictions.convert_block(p, columns, np.random.default_rng(1))

    def test_per_case_rng_identity_changes_for_every_trial_animal_and_sound(self):
        seeds = {predictions._case_seed(123, animal, sound, trial)
                 for animal in ANIMALS for sound in SOUNDS for trial in (1, 2)}
        self.assertEqual(len(seeds), 56)
        self.assertNotIn(predictions._case_seed(124, 3, SOUNDS[0], 1), seeds)


class PublicBoundaryControls(unittest.TestCase):
    def test_complete_public_schema_accepts_original_geometry(self):
        predictions.validate_public(public_document())

    def test_reduced_support_missing_cases_private_fields_and_foreign_sources_refused(self):
        cases = [public_document(8, 256)]
        p = public_document(); p["cases"].pop(); cases.append(p)
        p = public_document(); p["cases"][-1] = p["cases"][0]; cases.append(p)
        p = public_document(); p["recorded_trial1"] = "secret.npy"; cases.append(p)
        p = public_document(); p["qualification"] = "paper_reproduced"; cases.append(p)
        p = public_document(); p["source_files"][0]["recorded_counts"] = [1, 2]; cases.append(p)
        p = public_document(); p["source_files"][0]["filename"] = "foreign.mat"; cases.append(p)
        p = public_document(); p["source_files"][0]["bytes"] += 1; cases.append(p)
        p = public_document(); p["animals"]["3"]["unit_ids"].reverse(); cases.append(p)
        for panel in cases:
            with self.assertRaises(source.InputError):
                predictions.validate_public(panel)

    def test_numpy_headers_hashes_extents_and_paths_are_checked_before_loading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = np.arange(8, dtype=np.float64).reshape(2, 4)
            descriptor = independent_array(root, "good.npy", original)
            np.testing.assert_array_equal(predictions.load_array(root, descriptor, (2, 4), "float64"), original)
            bad = dict(descriptor, sha256="0" * 64)
            with self.assertRaises(source.InputError): predictions.load_array(root, bad, (2, 4), "float64")
            with self.assertRaises(source.InputError): predictions.load_array(root, descriptor, (2, 4), "int64")
            with self.assertRaises(source.InputError): predictions.load_array(root, descriptor, (4, 2), "float64")
            forged = root / "huge.npy"
            with forged.open("wb") as stream:
                np.lib.format.write_array_header_1_0(stream, {"descr": "<f8", "fortran_order": False,
                                                             "shape": (2**40, 4)})
            forged_descriptor = {"path": forged.name, "sha256": hashlib.sha256(forged.read_bytes()).hexdigest()}
            with mock.patch.object(np, "load", side_effect=AssertionError("allocation attempted")):
                with self.assertRaises(source.InputError):
                    predictions.load_array(root, forged_descriptor, (2, 4), "float64")
            for relative in ("../outside.npy", "/absolute.npy"):
                with self.assertRaises((source.InputError, OSError)):
                    predictions.load_array(root, dict(descriptor, path=relative), (2, 4), "float64")
            alias = root / "alias.npy"; alias.symlink_to(root / "good.npy")
            with self.assertRaises(source.InputError):
                predictions.load_array(root, dict(descriptor, path=alias.name), (2, 4), "float64")


class ReducedTimeAllCasesRuntimeControls(unittest.TestCase):
    """Generated runtime controls: 8 bins, all 28 cases; never authentic/full-time."""
    @classmethod
    def setUpClass(cls):
        global CONTROL_BYTES_CREATED
        CONTROL_BYTES_CREATED = 0
        cls.temp = tempfile.TemporaryDirectory(prefix="icnet-reduced-time-")
        cls.root = Path(cls.temp.name)
        cls.public_root = cls.root / "public"; cls.public_root.mkdir()
        cls.private_root = cls.root / "private"; cls.private_root.mkdir()
        cls.prediction_root = cls.root / "predictions"
        cls.public = public_document(8, 256)
        for si, sound in enumerate(SOUNDS):
            cls.public["sounds"][sound] = independent_array(cls.public_root, sound + ".npy",
                                                            np.full(256, 0.001 * (si + 1), dtype=np.float32))
        for ai, animal in enumerate(ANIMALS):
            cls.public["animals"][str(animal)]["characteristic_frequencies"] = independent_array(
                cls.public_root, f"animal_{animal}_cf.npy", cf_values()[ai])
        cls.public_path = cls.public_root / "panel.json"
        pin = independent_json(cls.public_path, cls.public)
        cls.reference = {"schema": "icnet-original-private-panel/v1", "policy": copy.deepcopy(POLICY),
            "source_files": cls.public["source_files"], "source_authentication": "generated_test_descriptors",
            "qualification": "source_preparation_not_scientific_admission", "public_manifest_sha256": pin,
            "animals": {str(a): {"unit_ids": cls.public["animals"][str(a)]["unit_ids"],
                                "eligible_mask": np.isfinite(cf_values()[ai]).tolist()}
                        for ai, a in enumerate(ANIMALS)}, "cases": []}
        cls.requests = []
        for case in cls.public["cases"]:
            arrays = {f"recorded_trial{t}": independent_array(cls.private_root,
                f"animal_{case['animal']}_{case['sound']}_trial{t}.npy", cls.values(case)) for t in (1, 2)}
            cls.reference["cases"].append({**case, "arrays": arrays})
        cls.reference_path = cls.private_root / "reference.json"
        independent_json(cls.reference_path, cls.reference)
        with cls.reduced_constants():
            cls.prediction = predictions.run(cls.public_path, cls.prediction_root, cls.predictor,
                                             predictor_sha256="9" * 64, seed=1923)
        cls.predictions_path = cls.prediction_root / "predictions.json"

    @classmethod
    def tearDownClass(cls):
        produced_bytes = sum(p.stat().st_size for child in cls.root.iterdir()
                             if child.is_dir() and child.name not in ("public", "private")
                             for p in child.rglob("*") if p.is_file() and not p.name.startswith("mutant_"))
        created = CONTROL_BYTES_CREATED + produced_bytes
        cls.temp.cleanup()
        report = os.environ.get("ICNET_RUNTIME_ACCOUNTING")
        if report:
            with Path(report).open("x") as stream:
                json.dump({"scope": "generated reduced-time all-28-case runtime controls; eight bins",
                           "generated_logical_bytes_including_replaced_manifests": created,
                           "retained_fixture_bytes_after_cleanup": 0 if not cls.root.exists() else None,
                           "model_or_authentic_data_runs": 0}, stream, indent=2)
                stream.write("\n")

    @staticmethod
    @contextmanager
    def reduced_constants():
        with mock.patch.object(predictions, "TIME_BINS", 8), mock.patch.object(predictions, "AUDIO_SAMPLES", 256), \
                mock.patch.object(grade, "TIME_BINS", 8):
            yield

    @staticmethod
    def values(case):
        return ((np.arange(8)[:, None] + np.arange(N_UNITS)[None, :] + case["animal"]
                 + SOUNDS.index(case["sound"])) % 5).astype(np.int8)

    @classmethod
    def predictor(cls, request):
        cls.requests.append({key: value for key, value in request.items()
                             if key not in ("audio_pa", "characteristic_frequencies_hz", "unit_ids")})
        if set(request) != {"animal", "sound", "trial", "audio_pa", "fs_audio", "fs_neural", "time_bins",
                            "measurement_time_seconds", "characteristic_frequencies_hz", "unit_ids", "maximum_block_bins"}:
            raise AssertionError("private or unexpected predictor inputs")
        if request["audio_pa"].flags.writeable or request["characteristic_frequencies_hz"].flags.writeable:
            raise AssertionError("public arrays must be read only")
        columns = np.roll(np.arange(N_UNITS)[::-1], request["animal"]).tolist()
        values = cls.values(request)
        for start, stop in ((0, 3), (3, 8)):
            yield {"start_bin": start, "column_indices": columns,
                   "probabilities": np.eye(5, dtype=np.float32)[values[start:stop, columns]]}

    def assembled(self, public=None, reference=None, prediction=None, ddof=0):
        paths = []
        for name, document, original in (("public", public, self.public_path),
                                         ("reference", reference, self.reference_path),
                                         ("prediction", prediction, self.predictions_path)):
            if document is None:
                paths.append(original)
            else:
                path = original.parent / ("mutant_" + name + ".json")
                independent_json(path, document); paths.append(path)
        with self.reduced_constants():
            return grade.assemble(*paths, self.root, variance_ddof=ddof)

    def test_all_cases_trials_original_columns_and_equations_connected(self):
        self.assertEqual(len(self.requests), 56)
        self.assertEqual(len(self.prediction["cases"]), 28)
        for row in self.prediction["cases"]:
            for trial in (1, 2):
                for name in ("sampled", "expected"):
                    descriptor = row["arrays"][f"{name}_trial{trial}"]
                    actual = np.load(self.prediction_root / descriptor["path"], allow_pickle=False)
                    np.testing.assert_array_equal(actual, self.values(row))
                request = next(r for r in self.requests if (r["animal"], r["sound"], r["trial"]) ==
                               (row["animal"], row["sound"], trial))
                self.assertEqual(request["measurement_time_seconds"], row["measurement_times_seconds"][trial - 1])
        assembled = self.assembled()
        self.assertEqual(len(assembled["cases"]), 28)
        self.assertEqual(assembled["preparation"]["source_authentication"], "generated_test_descriptors")
        result = grade.grade(assembled, self.root)
        self.assertEqual((result["n_animals"], result["n_sounds"], result["eligible_units"]), (7, 4, 3476))
        self.assertEqual(result["published_text_aggregation"], "unresolved_no_scalar_reduction")
        self.assertFalse(result["reproduction_evaluated"])
        self.assertFalse(result["improvement_evaluated"])
        for row in result["cases"]:
            self.assertAlmostEqual(row["flattened"]["correlation_explained_percent"], 100.0, places=10)
            self.assertAlmostEqual(row["flattened"]["variance_explained_percent"], 100.0, places=10)
            self.assertEqual(row["time_bins"], 8)
        self.assertEqual(sum(len(row["by_unit"]) for row in result["cases"]), 3476 * 4)

    def test_unpatched_production_rejects_reduced_time_artifact(self):
        with self.assertRaises(source.InputError):
            predictions.validate_public(self.public)
        with self.assertRaises(source.InputError):
            grade.assemble(self.public_path, self.reference_path, self.predictions_path, self.root, variance_ddof=0)

    def test_incomplete_panel_frozen_hash_alignment_or_trials_refused(self):
        cases = []
        p = copy.deepcopy(self.prediction); p["cases"].pop(); cases.append(p)
        p = copy.deepcopy(self.prediction); p["complete"] = False; cases.append(p)
        p = copy.deepcopy(self.prediction); p["public_manifest_sha256"] = "0" * 64; cases.append(p)
        p = copy.deepcopy(self.prediction); p["cases"][0]["measurement_times_seconds"].reverse(); cases.append(p)
        p = copy.deepcopy(self.prediction); del p["cases"][0]["arrays"]["expected_trial2"]; cases.append(p)
        p = copy.deepcopy(self.prediction); p["cases"][0]["arrays"]["sampled_trial1"]["sha256"] = "0" * 64; cases.append(p)
        for p in cases:
            with self.assertRaises(source.InputError): self.assembled(prediction=p)
        with self.assertRaises(source.InputError): self.assembled(ddof=True)

    def test_source_mask_must_match_public_cf_and_publisher_authentication_cannot_be_forged(self):
        reference = copy.deepcopy(self.reference)
        mask = reference["animals"]["3"]["eligible_mask"]
        mask[0], mask[-1] = mask[-1], mask[0]
        with self.assertRaises(source.InputError): self.assembled(reference=reference)
        reference = copy.deepcopy(self.reference); reference["source_authentication"] = "publisher_bytes_md5"
        with self.assertRaises(source.InputError): self.assembled(reference=reference)

    def test_positive_infinity_public_cf_refused_before_predictor_or_scoring(self):
        public = copy.deepcopy(self.public)
        values = cf_values()[0].copy(); values[-1] = np.inf
        public["animals"]["3"]["characteristic_frequencies"] = independent_array(
            self.public_root, "wrong_positive_infinity.npy", values)
        path = self.public_root / "wrong_positive_infinity.json"
        public_pin = independent_json(path, public)
        predictor = mock.Mock(side_effect=AssertionError("predictor must not execute"))
        destination = self.root / "wrong_positive_infinity_predictions"
        with self.reduced_constants(), self.assertRaises(source.InputError):
            predictions.run(path, destination, predictor, predictor_sha256="7" * 64, seed=42)
        predictor.assert_not_called()
        self.assertFalse(destination.exists())
        reference, prediction = copy.deepcopy(self.reference), copy.deepcopy(self.prediction)
        reference["public_manifest_sha256"] = public_pin
        prediction["public_manifest_sha256"] = public_pin
        with self.assertRaises(source.InputError):
            self.assembled(public=public, reference=reference, prediction=prediction)

    def test_predictor_gaps_and_incomplete_stream_never_publish_complete_manifest(self):
        def gap(request):
            yield {"start_bin": 1, "column_indices": list(range(N_UNITS)),
                   "probabilities": np.broadcast_to(np.eye(5)[0], (1, N_UNITS, 5))}
        def short(request):
            yield {"start_bin": 0, "column_indices": list(range(N_UNITS)),
                   "probabilities": np.broadcast_to(np.eye(5)[0], (1, N_UNITS, 5))}
        for index, predictor in enumerate((gap, short)):
            destination = self.root / f"refused_prediction_{index}"
            with self.reduced_constants(), self.assertRaises(source.InputError):
                predictions.run(self.public_path, destination, predictor, predictor_sha256="8" * 64, seed=22)
            self.assertFalse((destination / "predictions.json").exists())


@unittest.skipUnless(os.environ.get("ICNET_FIXTURE_ROOT"),
                     "full original geometry requires an explicitly reserved ICNET_FIXTURE_ROOT")
class FullOriginalGeometryControl(unittest.TestCase):
    def test_complete_generated_sources_to_public_private_panel(self):
        # One complete pass, with native dimensions and all variables. This is
        # engineering evidence from explicitly generated source descriptors.
        declared_root = os.environ.get("ICNET_FIXTURE_ROOT")
        if declared_root:
            Path(declared_root).mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(prefix="icnet-generated-", dir=declared_root))
        generated_bytes = 0
        try:
            raw = root / "raw"; raw.mkdir()
            for ti in (1, 2): write_trial(raw / f"IC_data_trial{ti}.mat", ti)
            write_audio(raw / "sound_data.mat")
            expected = {path.name: (path.stat().st_size, file_md5(path)) for path in raw.iterdir()}
            self.assertEqual({key: row[0] for key, row in expected.items()},
                             {"IC_data_trial1.mat": 326661096, "IC_data_trial2.mat": 326661096,
                              "sound_data.mat": 11665880})
            result = source.prepare(raw, root / "prepared", POLICY, _expected_files=expected)
            self.assertEqual((result["n_animals"], result["n_cases"], result["n_trials"], result["eligible_units"]),
                             (7, 28, 56, 3476))
            self.assertFalse(result["native_model_or_candidate_run"])
            self.assertFalse(result["scientifically_qualified"])
            public = source.read_json(result["public_manifest"])
            private = source.read_json(result["private_reference"])
            self.assertEqual(private["source_authentication"], "generated_test_descriptors")
            public_root = Path(result["public_manifest"]).parent
            private_root = Path(result["private_reference"]).parent
            self.assertEqual({(row["animal"], row["sound"]) for row in public["cases"]},
                             {(animal, sound) for animal in ANIMALS for sound in SOUNDS})
            self.assertEqual(len(public["cases"]), 28)
            self.assertEqual(private["public_manifest_sha256"], source.sha256_file(public_root / "panel.json"))
            self.assertEqual({p.name for p in public_root.iterdir()},
                             {"panel.json", *(name + ".npy" for name in SOUNDS),
                              *(f"animal_{animal}_cf.npy" for animal in ANIMALS)})
            self.assertNotIn("eligible_mask", json.dumps(public))
            self.assertNotIn("recorded_trial", json.dumps(public))
            for descriptor in public["source_files"]:
                self.assertEqual(descriptor["authenticated_md5"], expected[descriptor["filename"]][1])
            for si, sound in enumerate(SOUNDS):
                array = np.load(public_root / public["sounds"][sound]["path"], mmap_mode="r", allow_pickle=False)
                np.testing.assert_array_equal(array, sound_values(si))
                self.assertEqual(array.shape, (N_SAMPLES,))
            for ai, animal in enumerate(ANIMALS):
                row = public["animals"][str(animal)]
                self.assertEqual(row["unit_ids"], [f"animal_{animal}:original_column_{i}" for i in range(N_UNITS)])
                actual_cf = np.load(public_root / row["characteristic_frequencies"]["path"], allow_pickle=False)
                np.testing.assert_array_equal(actual_cf, cf_values()[ai])
                self.assertEqual(private["animals"][str(animal)]["eligible_mask"], np.isfinite(cf_values()[ai]).tolist())
            for record in private["cases"]:
                ai, si = ANIMALS.index(record["animal"]), SOUNDS.index(record["sound"])
                self.assertEqual(record["time_bins"], N_BINS)
                self.assertEqual(record["measurement_times_seconds"],
                                 [float(time_values(ti)[ai, si]) for ti in (1, 2)])
                for ti in (1, 2):
                    descriptor = record["arrays"][f"recorded_trial{ti}"]
                    path = private_root / descriptor["path"]
                    self.assertEqual(source.sha256_file(path), descriptor["sha256"])
                    array = np.load(path, mmap_mode="r", allow_pickle=False)
                    self.assertEqual(array.shape, (N_BINS, N_UNITS))
                    self.assertEqual(array.dtype, np.dtype("i1"))
                    # Every value is checked in bounded blocks; no cherry-picked
                    # first-row/last-row substitute for complete coverage.
                    for start in range(0, N_BINS, 1024):
                        stop = min(start + 1024, N_BINS)
                        expected_values = count_values(ai, np.arange(start, stop)[:, None],
                                                       np.arange(N_UNITS)[None, :], ti, si)
                        np.testing.assert_array_equal(array[start:stop], expected_values)
                    self.assertGreater(int(array.max()), 4)
                    self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            for path in public_root.iterdir():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o444)
        finally:
            generated_bytes = sum(path.stat().st_size for path in root.rglob("*") if path.is_file())
            writable_rmtree(root)
            accounting = {"scope": "generated complete source geometry only", "generated_logical_bytes": generated_bytes,
                          "retained_fixture_bytes_after_cleanup": 0 if not root.exists() else None,
                          "source_files": 3, "model_or_authentic_data_runs": 0}
            report = os.environ.get("ICNET_FIXTURE_ACCOUNTING")
            if report:
                with Path(report).open("x") as stream: json.dump(accounting, stream, indent=2); stream.write("\n")


if __name__ == "__main__":
    unittest.main()
