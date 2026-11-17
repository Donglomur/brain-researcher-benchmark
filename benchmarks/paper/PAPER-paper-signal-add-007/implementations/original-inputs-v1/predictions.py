"""Stream complete ICNet probability predictions into sampled and expected counts.

The callable is a trusted operator-supplied model interface, not an isolation
boundary. It receives only the public prepared panel. No model is bundled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import types

import numpy as np

from source import (ANIMALS, SOUNDS, TIME_BINS, AUDIO_SAMPLES, UNITS, FS_AUDIO,
                    FS_NEURAL, SOURCE_FILES, InputError, is_sha, read_json_with_pin, regular_file,
                    require, sha256_file, write_json)

MAX_BLOCK_BINS = 1024


def inside(root, relative):
    require(type(relative) is str and relative and not Path(relative).is_absolute(),
            "array path must be relative")
    root = Path(root).resolve(strict=True)
    path = root / relative
    require(not path.is_symlink() and path.resolve(strict=True).is_relative_to(root),
            "array path escapes its declared root")
    return path.resolve(strict=True)


def load_array(root, descriptor, shape, dtype):
    require(type(descriptor) is dict and set(descriptor) == {"path", "sha256"}
            and is_sha(descriptor["sha256"]), "invalid array descriptor")
    path = inside(root, descriptor["path"])
    with regular_file(path) as stream:
        initial = os.fstat(stream.fileno())
        require(initial.st_size <= math.prod(shape) * np.dtype(dtype).itemsize + 4096,
                "array exceeds fixed shape byte bound")
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
        require(digest.hexdigest() == descriptor["sha256"], "array SHA256 mismatch")
        stream.seek(0)
        require(np.lib.format.read_magic(stream) == (1, 0), "only prepared NPY-v1 arrays are supported")
        header_shape, fortran, header_dtype = np.lib.format.read_array_header_1_0(stream, max_header_size=1024)
        require(header_shape == shape and header_dtype == np.dtype(dtype) and not fortran,
                "NPY header differs from original public shape/dtype/order")
        require(initial.st_size == stream.tell() + math.prod(shape) * np.dtype(dtype).itemsize,
                "NPY payload extent mismatch")
        stream.seek(0)
        array = np.load(stream, allow_pickle=False)
        final = os.fstat(stream.fileno())
        require((initial.st_size, initial.st_mtime_ns, initial.st_ctime_ns) ==
                (final.st_size, final.st_mtime_ns, final.st_ctime_ns), "array changed during bounded read")
    require(type(array) is np.ndarray and array.shape == shape and array.dtype == np.dtype(dtype),
            "array shape or dtype differs from original public panel")
    return array


def validate_public(panel):
    require(type(panel) is dict and set(panel) == {
        "schema", "animals", "cases", "sounds", "fs_audio", "fs_neural",
        "time_bins", "audio_samples", "split", "qualification", "source_files"},
        "unexpected public fields; private target fields are forbidden")
    require(panel["schema"] == "icnet-original-public-panel/v1", "unsupported public panel")
    require(panel["time_bins"] == TIME_BINS and type(panel["time_bins"]) is int
            and panel["audio_samples"] == AUDIO_SAMPLES and type(panel["audio_samples"]) is int,
            "complete original temporal support required")
    require(panel["fs_audio"] == FS_AUDIO and panel["fs_neural"] == FS_NEURAL,
            "source sampling rates differ")
    require(panel["split"] == "original_four_sounds_held_out_from_training", "source split changed")
    require(panel["qualification"] == "input_preparation_only", "public input qualification changed")
    require(type(panel["source_files"]) is list and len(panel["source_files"]) == 3,
            "exactly three source identities required")
    names = set()
    for descriptor in panel["source_files"]:
        require(type(descriptor) is dict and set(descriptor) == {"filename", "bytes", "sha256", "authenticated_md5"},
                "unexpected source descriptor fields")
        name = descriptor["filename"]
        require(type(name) is str and name in SOURCE_FILES and name not in names, "duplicate or foreign source file")
        names.add(name)
        require(type(descriptor["bytes"]) is int and descriptor["bytes"] == SOURCE_FILES[name][0]
                and is_sha(descriptor["sha256"]), "source byte extent or SHA256 invalid")
        md5 = descriptor["authenticated_md5"]
        require(type(md5) is str and len(md5) == 32 and all(c in "0123456789abcdef" for c in md5),
                "invalid authenticated MD5")
    require(set(panel["sounds"]) == set(SOUNDS) and set(panel["animals"]) == {str(a) for a in ANIMALS},
            "complete original animals and sounds required")
    for animal in ANIMALS:
        row = panel["animals"][str(animal)]
        require(set(row) == {"unit_ids", "characteristic_frequencies"}, "unexpected animal fields")
        require(row["unit_ids"] == [f"animal_{animal}:original_column_{i}" for i in range(UNITS)],
                "original column identity changed")
    require(type(panel["cases"]) is list and len(panel["cases"]) == 28, "all 28 cases are required")
    seen = set()
    for case in panel["cases"]:
        require(set(case) == {"animal", "sound", "time_bins", "measurement_times_seconds"},
                "unexpected public case fields")
        key = (case["animal"], case["sound"])
        require(type(key[0]) is int and key[0] in ANIMALS and key[1] in SOUNDS and key not in seen,
                "duplicate or foreign animal/sound case")
        seen.add(key)
        require(type(case["time_bins"]) is int and case["time_bins"] == TIME_BINS, "incomplete case duration")
        times = case["measurement_times_seconds"]
        require(type(times) is list and len(times) == 2
                and all(type(t) in (int, float) and math.isfinite(t) and t >= 0 for t in times),
                "two trial-specific measurement times in seconds required")


def convert_block(probabilities, column_indices, rng):
    """Restore original columns; derive expectation and categorical draws.

    The explicit NumPy RNG is not the author's TensorFlow RNG. At most eight
    input-dtype epsilons of row-sum error are accepted, then rows are normalized
    to remove storage/accumulation roundoff. No arbitrary logits are admitted.
    """
    p = np.asarray(probabilities)
    require(p.dtype in (np.dtype("float32"), np.dtype("float64")) and p.ndim == 3
            and 1 <= p.shape[0] <= MAX_BLOCK_BINS and p.shape[1:] == (UNITS, 5),
            "probability blocks must be 1..1024 by 512 by 5 float32/64")
    require(type(column_indices) is list and len(column_indices) == UNITS
            and all(type(i) is int for i in column_indices)
            and set(column_indices) == set(range(UNITS)), "exact original-column permutation required")
    require(np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all(), "invalid categorical probabilities")
    total = p.sum(axis=-1, dtype=np.float64)
    require(np.all(np.abs(total - 1.0) <= 8 * np.finfo(p.dtype).eps), "categorical rows must sum to one")
    # original column j occurs at inverse[j], even if CF sorting included ties.
    inverse = np.argsort(np.asarray(column_indices))
    p = np.asarray(p[:, inverse, :], dtype=np.float64)
    p /= total[:, inverse, None]
    expected = np.sum(p * np.arange(5, dtype=np.float64), axis=-1)
    cumulative = np.cumsum(p, axis=-1)
    cumulative[:, :, -1] = 1.0
    uniform = rng.random(p.shape[:2])
    sampled = np.sum(uniform[:, :, None] >= cumulative, axis=-1).astype(np.int8)
    return sampled, expected


def _case_seed(seed, animal, sound, trial):
    payload = json.dumps([seed, animal, sound, trial], separators=(",", ":")).encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:16], "little")


def run(public_manifest_path, destination, predictor, *, predictor_sha256, seed):
    require(callable(predictor) and is_sha(predictor_sha256), "callable and declared predictor source pin required")
    require(type(seed) is int and 0 <= seed < 2**63, "explicit nonnegative 63-bit sampling seed required")
    manifest_path = Path(public_manifest_path)
    panel, manifest_pin = read_json_with_pin(manifest_path)
    validate_public(panel)
    root, destination = manifest_path.parent.resolve(), Path(destination)
    require(not destination.exists(), "prediction destination must be new")
    # Authenticate all participant arrays before invoking any predictor.
    audio = {s: load_array(root, panel["sounds"][s], (AUDIO_SAMPLES,), "float32") for s in SOUNDS}
    cfs = {a: load_array(root, panel["animals"][str(a)]["characteristic_frequencies"], (UNITS,), "float64")
           for a in ANIMALS}
    require(all(np.isfinite(x).all() for x in audio.values()), "public audio contains invalid values")
    require(all(np.all((np.isfinite(x) & (x > 0)) | np.isneginf(x)) for x in cfs.values()),
            "public characteristic frequencies are invalid")
    for array in (*audio.values(), *cfs.values()):
        array.flags.writeable = False
    destination.mkdir(mode=0o700)
    output = {"schema": "icnet-original-predictions/v1", "public_manifest_sha256": manifest_pin,
              "predictor_sha256": predictor_sha256, "sampling_seed": seed,
              "sampling": "NumPy-PCG64-original-column-row-major-inverse-CDF",
              "cases": [], "complete": False,
              "qualification": "complete_prediction_artifact_not_protected_or_scientifically_qualified"}
    for case in sorted(panel["cases"], key=lambda c: (SOUNDS.index(c["sound"]), c["animal"])):
        animal, sound = case["animal"], case["sound"]
        entry = {**case, "arrays": {}, "trials": []}
        for trial in (1, 2):
            request = {"animal": animal, "sound": sound, "trial": trial,
                       "audio_pa": audio[sound], "fs_audio": FS_AUDIO, "fs_neural": FS_NEURAL,
                       "time_bins": TIME_BINS, "measurement_time_seconds": case["measurement_times_seconds"][trial - 1],
                       "characteristic_frequencies_hz": cfs[animal],
                       "unit_ids": tuple(panel["animals"][str(animal)]["unit_ids"]),
                       "maximum_block_bins": MAX_BLOCK_BINS}
            paths = {name: destination / f"animal_{animal}_{sound}_{name}_trial{trial}.npy"
                     for name in ("sampled", "expected")}
            sampled = np.lib.format.open_memmap(paths["sampled"], mode="w+", dtype="int8", shape=(TIME_BINS, UNITS))
            expected = np.lib.format.open_memmap(paths["expected"], mode="w+", dtype="float64", shape=(TIME_BINS, UNITS))
            rng = np.random.Generator(np.random.PCG64(_case_seed(seed, animal, sound, trial)))
            position, columns, blocks = 0, None, 0
            try:
                for block in predictor(request):
                    require(type(block) is dict and set(block) == {"start_bin", "probabilities", "column_indices"},
                            "invalid predictor block fields")
                    require(type(block["start_bin"]) is int and block["start_bin"] == position,
                            "prediction gaps, overlap or reordered bins are forbidden")
                    draws, means = convert_block(block["probabilities"], block["column_indices"], rng)
                    if columns is None:
                        columns = list(block["column_indices"])
                    require(columns == block["column_indices"], "prediction column order changed within a trial")
                    stop = position + draws.shape[0]
                    require(stop <= TIME_BINS, "prediction extends beyond released support")
                    sampled[position:stop] = draws; expected[position:stop] = means
                    position = stop; blocks += 1
                require(position == TIME_BINS, "predictor omitted original bins")
                sampled.flush(); expected.flush()
            finally:
                del sampled, expected
            for name, path in paths.items():
                path.chmod(0o600)
                entry["arrays"][f"{name}_trial{trial}"] = {"path": path.name, "sha256": sha256_file(path)}
            entry["trials"].append({"trial": trial, "blocks": blocks, "column_indices": columns})
        output["cases"].append(entry)
    require(sha256_file(manifest_path) == manifest_pin, "public manifest changed during prediction")
    output["complete"] = True
    write_json(destination / "predictions.json", output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-manifest", type=Path, required=True)
    parser.add_argument("--predictor", type=Path, required=True)
    parser.add_argument("--predictor-sha256", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    with regular_file(args.predictor) as stream:
        require(os.fstat(stream.fileno()).st_size <= 1024 * 1024, "predictor source exceeds one MiB")
        body = stream.read(1024 * 1024 + 1)
        require(len(body) <= 1024 * 1024, "predictor source exceeds one MiB")
    require(hashlib.sha256(body).hexdigest() == args.predictor_sha256, "predictor source SHA256 mismatch")
    module = types.ModuleType("icnet_operator_predictor")
    module.__file__ = str(args.predictor.resolve())
    exec(compile(body, module.__file__, "exec"), module.__dict__)
    output = run(args.public_manifest, args.output_root, module.predict,
                 predictor_sha256=args.predictor_sha256, seed=args.seed)
    print(json.dumps({"cases": len(output["cases"]), "complete": output["complete"],
                      "qualification": output["qualification"]}, indent=2))


if __name__ == "__main__":
    main()
