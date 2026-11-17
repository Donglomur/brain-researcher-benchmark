"""Original ICNet MAT intake and complete released-panel preparation.

This is an independently written, deliberately narrow uncompressed MAT-v5
reader. It does not implement the licensed author model or invent an original
crop, reliability mask, or published-score acceptance rule.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import struct

import numpy as np

ANIMALS = tuple(range(3, 10))
SOUNDS = ("speech_in_quiet", "speech_in_noise", "moving_ripples", "music")
TIME_BINS = 22784
AUDIO_SAMPLES = 729088
UNITS = 512
FS_AUDIO = 24414.0625
FS_NEURAL = FS_AUDIO / 32
SOURCE_FILES = {
    "IC_data_trial1.mat": (326661096, "440fe9fda52e09540b8d78379cdf96ed"),
    "IC_data_trial2.mat": (326661096, "34d6a3fab17cdd4157a06383299e40ab"),
    "sound_data.mat": (11665880, "835b3e1ff6815b16ad086eb7f8dcc6d6"),
}
TRIAL_FIELDS = {name: ((7, TIME_BINS, UNITS), "i1", 8) for name in SOUNDS}
TRIAL_FIELDS.update({"measurement_times": ((7, 4), "<f8", 6),
                     "channel_CFs": ((7, UNITS), "<f8", 6),
                     "animals": ((1, 7), "<i8", 14),
                     "fs": ((1, 1), "<f8", 6)})
SOUND_FIELDS = {name: ((1, AUDIO_SAMPLES), "<f4", 7) for name in SOUNDS}
SOUND_FIELDS["fs"] = ((1, 1), "<f8", 6)
_TYPES = {1: ("i1", 1), 7: ("<f4", 4), 9: ("<f8", 8), 12: ("<i8", 8)}


class InputError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise InputError(message)


def sha256_file(path):
    digest = hashlib.sha256()
    with regular_file(path) as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_sha(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def regular_file(path):
    """Open the final component without following a symlink; reject aliases."""
    fd = os.open(Path(path), os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        info = os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                "input must be an ordinary singly linked file")
        return os.fdopen(fd, "rb")
    except BaseException:
        os.close(fd)
        raise


def _identity(stream):
    s = os.fstat(stream.fileno())
    return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _exact(stream, count):
    value = stream.read(count)
    require(len(value) == count, "truncated MAT element")
    return value


def _tag(stream, limit):
    pos = stream.tell()
    require(pos + 8 <= limit, "MAT tag outside enclosing element")
    raw = _exact(stream, 8)
    word, size = struct.unpack("<II", raw)
    small_size = word >> 16
    if small_size:
        require(small_size <= 4, "invalid small MAT element")
        return word & 65535, small_size, pos + 4, pos + 8, raw[4:4 + small_size]
    require(pos + 8 + size <= limit, "MAT payload outside enclosing element")
    end = pos + 8 + ((size + 7) // 8) * 8
    require(end <= limit, "MAT padding outside enclosing element")
    return word, size, pos + 8, end, None


def _small_payload(stream, tag, maximum):
    kind, size, offset, end, embedded = tag
    require(size <= maximum, "oversized MAT metadata")
    stream.seek(offset)
    value = embedded if embedded is not None else _exact(stream, size)
    stream.seek(end)
    return kind, value


def mat_directory(stream, size):
    """Inspect only bounded metadata, never decompress or load count arrays."""
    require(128 <= size <= 400 * 1024**2, "source MAT size outside fixed input bound")
    stream.seek(0)
    header = _exact(stream, 128)
    require(header.startswith(b"MATLAB 5.0 MAT-file") and header[124:128] == b"\x00\x01IM",
            "only original little-endian uncompressed MAT-v5 is supported")
    result = {}
    while stream.tell() < size:
        require(len(result) < 8, "unexpected extra MAT variables")
        outer = _tag(stream, size)
        kind, length, start, outer_end, embedded = outer
        require(kind == 14 and embedded is None, "expected uncompressed numeric miMATRIX")
        matrix_end = start + length
        stream.seek(start)
        flags_kind, flags = _small_payload(stream, _tag(stream, matrix_end), 8)
        require(flags_kind == 6 and len(flags) == 8, "invalid MAT array flags")
        flags_value, extra = struct.unpack("<II", flags)
        require(flags_value in (6, 7, 8, 14) and extra == 0,
                "complex, logical, sparse or nonnumeric source arrays are unsupported")
        dim_kind, dim_bytes = _small_payload(stream, _tag(stream, matrix_end), 12)
        require(dim_kind == 5 and len(dim_bytes) in (8, 12), "invalid MAT dimensions")
        shape = struct.unpack("<" + "i" * (len(dim_bytes) // 4), dim_bytes)
        require(all(n > 0 for n in shape), "empty or negative source dimensions")
        name_kind, name_bytes = _small_payload(stream, _tag(stream, matrix_end), 64)
        require(name_kind == 1, "invalid MAT variable name encoding")
        try:
            name = name_bytes.decode("ascii")
        except UnicodeError as exc:
            raise InputError("invalid MAT variable name") from exc
        require(name not in result and name in TRIAL_FIELDS, "duplicate or unknown MAT variable")
        data = _tag(stream, matrix_end)
        require(data[0] in _TYPES and data[4] is None, "unsupported numeric data encoding")
        dtype, width = _TYPES[data[0]]
        require(data[1] == math.prod(shape) * width and data[3] == matrix_end,
                "numeric MAT payload size does not match complete dimensions")
        result[name] = {"shape": shape, "dtype": dtype, "class": flags_value,
                        "offset": data[2], "bytes": data[1]}
        stream.seek(outer_end)
    require(stream.tell() == size, "trailing or truncated MAT bytes")
    return result


class MatFile:
    def __init__(self, path, expected, fields):
        self.path = Path(path)
        self.stream = regular_file(path)
        try:
            self.identity = _identity(self.stream)
            self.expected_md5 = expected[1]
            require(self.identity[2] == expected[0], "publisher file size mismatch")
            md5, sha = hashlib.md5(), hashlib.sha256()
            for block in iter(lambda: self.stream.read(1024 * 1024), b""):
                md5.update(block); sha.update(block)
            require(md5.hexdigest() == expected[1], "publisher file MD5 mismatch")
            self.sha256 = sha.hexdigest()
            self.directory = mat_directory(self.stream, expected[0])
            require(set(self.directory) == set(fields), "incomplete original variable inventory")
            for name, (shape, dtype, cls) in fields.items():
                row = self.directory[name]
                require((row["shape"], row["dtype"], row["class"]) == (shape, dtype, cls),
                        "original variable shape/type mismatch: " + name)
            self.check()
        except BaseException:
            self.stream.close()
            raise

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stream.close()

    def check(self):
        require(_identity(self.stream) == self.identity, "source file changed during preparation")

    def array(self, name):
        self.check()
        row = self.directory[name]
        return np.memmap(self.stream, mode="r", dtype=row["dtype"],
                         offset=row["offset"], shape=row["shape"], order="F")

    def descriptor(self):
        return {"filename": self.path.name, "bytes": self.identity[2],
                "sha256": self.sha256, "authenticated_md5": self.expected_md5}


def read_json_with_pin(path, maximum=1024 * 1024):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    with regular_file(path) as stream:
        require(os.fstat(stream.fileno()).st_size <= maximum, "JSON exceeds read bound")
        body = stream.read(maximum + 1)
        require(len(body) <= maximum, "JSON exceeds read bound")
    document = json.loads(body, object_pairs_hook=pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(InputError("nonfinite JSON")))
    return document, hashlib.sha256(body).hexdigest()


def read_json(path, maximum=1024 * 1024):
    return read_json_with_pin(path, maximum)[0]


def write_json(path, value, public=False):
    with Path(path).open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
    Path(path).chmod(0o444 if public else 0o600)


def save_array(path, value, public=False):
    with Path(path).open("xb") as stream:
        np.save(stream, value, allow_pickle=False)
    Path(path).chmod(0o444 if public else 0o600)
    return {"path": Path(path).name, "sha256": sha256_file(path)}


def validate_policy(policy):
    require(set(policy) == {"schema", "measurement_time_sound_order", "mask_policy",
                            "mask_evidence_sha256", "alignment_review_sha256"}, "unexpected preparation policy fields")
    require(policy["schema"] == "icnet-original-preparation-policy/v1", "unknown preparation policy")
    order = policy["measurement_time_sound_order"]
    require(type(order) is list and len(order) == len(SOUNDS)
            and all(type(name) is str for name in order) and set(order) == set(SOUNDS),
            "explicit one-to-one original sound-column mapping must be reviewed")
    require(policy["mask_policy"] == "finite_source_characteristic_frequencies",
            "unsupported mask; evaluation-derived selection is forbidden")
    require(is_sha(policy["mask_evidence_sha256"]) and is_sha(policy["alignment_review_sha256"]),
            "independent mask/alignment review pins are required declarations")


def prepare(source_root, destination, policy, *, _expected_files=None):
    """Prepare all original source arrays; private test injection is not a CLI option.

    Review pins are operator declarations, not digital attestations. The source
    files themselves are authenticated against immutable publisher bytes/MD5.
    """
    validate_policy(policy)
    expected = SOURCE_FILES if _expected_files is None else _expected_files
    require(set(expected) == set(SOURCE_FILES), "exact three source files are required")
    source_root, destination = Path(source_root).resolve(), Path(destination)
    require(not destination.exists(), "preparation destination must be new")
    with ExitStack() as stack:
        files = {}
        for name in SOURCE_FILES:
            fields = SOUND_FIELDS if name == "sound_data.mat" else TRIAL_FIELDS
            files[name] = stack.enter_context(MatFile(source_root / name, expected[name], fields))
        t1, t2 = files["IC_data_trial1.mat"], files["IC_data_trial2.mat"]
        audio_file = files["sound_data.mat"]
        for trial in (t1, t2):
            require(np.array_equal(trial.array("animals"), np.array([ANIMALS], dtype=np.int64)),
                    "source animal order is not original animals 3 through 9")
            require(float(trial.array("fs")[0, 0]) == FS_NEURAL, "original neural rate mismatch")
        require(float(audio_file.array("fs")[0, 0]) == FS_AUDIO, "original audio rate mismatch")
        cf = np.array(t1.array("channel_CFs"), copy=True)
        require(np.array_equal(cf, t2.array("channel_CFs")), "trial characteristic-frequency identities disagree")
        # Both authenticated original trials use -inf for excluded channels.
        require(np.all((np.isfinite(cf) & (cf > 0)) | np.isneginf(cf)), "invalid source characteristic frequencies")
        mask = np.isfinite(cf)
        require(int(mask.sum()) == 3476 and mask.any(axis=1).all(), "source mask does not match original 3476 units")
        times = [np.array(t.array("measurement_times"), copy=True) for t in (t1, t2)]
        require(all(np.isfinite(x).all() and (x >= 0).all() for x in times), "invalid seconds measurement times")
        destination.mkdir(mode=0o700)
        public, private = destination / "public", destination / "private"
        public.mkdir(mode=0o700); private.mkdir(mode=0o700)
        public_manifest = {"schema": "icnet-original-public-panel/v1", "animals": {}, "cases": [],
                           "sounds": {}, "fs_audio": FS_AUDIO, "fs_neural": FS_NEURAL,
                           "time_bins": TIME_BINS, "audio_samples": AUDIO_SAMPLES,
                           "split": "original_four_sounds_held_out_from_training",
                           "qualification": "input_preparation_only", "source_files": [f.descriptor() for f in files.values()]}
        reference = {"schema": "icnet-original-private-panel/v1", "animals": {}, "cases": [],
                     "policy": policy, "source_files": public_manifest["source_files"],
                     "source_authentication": "publisher_bytes_md5" if _expected_files is None else "generated_test_descriptors",
                     "qualification": "source_preparation_not_scientific_admission"}
        for ai, animal in enumerate(ANIMALS):
            ids = [f"animal_{animal}:original_column_{column}" for column in range(UNITS)]
            public_manifest["animals"][str(animal)] = {"unit_ids": ids,
                "characteristic_frequencies": save_array(public / f"animal_{animal}_cf.npy", cf[ai], True)}
            reference["animals"][str(animal)] = {"unit_ids": ids, "eligible_mask": mask[ai].tolist()}
        for sound in SOUNDS:
            time_column = policy["measurement_time_sound_order"].index(sound)
            waveform = audio_file.array(sound)[0]
            require(np.isfinite(waveform).all(), "invalid calibrated source audio")
            public_manifest["sounds"][sound] = save_array(public / f"{sound}.npy", waveform, True)
            recorded = [t.array(sound) for t in (t1, t2)]
            for ai, animal in enumerate(ANIMALS):
                arrays = {}
                for ti, array in enumerate(recorded, start=1):
                    values = array[ai]
                    require((values >= 0).all(), "source recorded counts contain negative values")
                    arrays[f"recorded_trial{ti}"] = save_array(private / f"animal_{animal}_{sound}_trial{ti}.npy", values)
                identity = {"animal": animal, "sound": sound, "time_bins": TIME_BINS,
                            "measurement_times_seconds": [float(x[ai, time_column]) for x in times]}
                public_manifest["cases"].append(dict(identity))
                reference["cases"].append({**identity, "arrays": arrays})
            del recorded
        for file in files.values():
            file.check()
        write_json(public / "panel.json", public_manifest, True)
        reference["public_manifest_sha256"] = sha256_file(public / "panel.json")
        write_json(private / "reference.json", reference)
        public.chmod(0o555)
        return {"public_manifest": str(public / "panel.json"),
                "private_reference": str(private / "reference.json"),
                "public_manifest_sha256": reference["public_manifest_sha256"],
                "n_animals": 7, "n_cases": 28, "n_trials": 56, "eligible_units": 3476,
                "native_model_or_candidate_run": False, "scientifically_qualified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source_root, args.output_root, read_json(args.policy)), indent=2))


if __name__ == "__main__":
    main()
