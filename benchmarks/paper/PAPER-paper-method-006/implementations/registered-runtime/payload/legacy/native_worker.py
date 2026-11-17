"""Pinned Kilosort4 v4.0.2 native adapter; not executed in source construction.

Exact external API: run_kilosort.py c4afd287564e22092c01f0032e75e885267118d1e221462654614497f2a69005.
Exports the saved, duplicate-filtered spike events, not pre-export st/clu.
No metrics or protected truth are inputs to this process.
"""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import traceback


def check(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path, cap):
    check(path.is_file() and not path.is_symlink(), "regular JSON required")
    check(path.stat().st_size <= cap, "metadata size cap")
    def pairs(items):
        result = {}
        for k, v in items:
            check(k not in result, "duplicate JSON key")
            result[k] = v
        return result
    return json.loads(path.read_bytes(), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def checked_pin(pin, prefix):
    path = Path(pin["path"])
    check(path.is_absolute() and path.is_relative_to(prefix), "pin outside admitted mount")
    check(not any(part.is_symlink() for part in [path, *path.parents]), "symlink in source/input")
    check(path.is_file() and path.stat().st_size == pin["bytes"], "source/input size mismatch")
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(block)
    check(hasher.hexdigest() == pin["sha256"], "source/input digest mismatch")


def run(request):
    check(request["operation"] == "sort_kilosort4_v4_0_2", "unsupported native operation")
    # The host selection is the final external document. Embedding its hash in
    # this request would recreate a request/selection content-hash cycle.
    context = request["execution_context"]
    check(set(context) == {"plan_digest", "job_digest", "producer_profile_digest", "job_id", "cell", "query_id"}
          and context["query_id"] == request["case_id"], "source-bound execution context required")
    check(request["profile"] in {"R_source20", "R_paper40", "I_bijective_full"}, "profile")
    check(request["source_version"] == "v4.0.2", "source version")
    source_root = Path("/opt/author")
    source_paths = set()
    for pin in request["source_pins"]:
        checked_pin(pin, source_root)
        source_paths.add(pin["path"])
    check("/opt/author/kilosort/run_kilosort.py" in source_paths, "native API source missing")
    expected_api = "c4afd287564e22092c01f0032e75e885267118d1e221462654614497f2a69005"
    check(next(x for x in request["source_pins"] if x["path"] ==
               "/opt/author/kilosort/run_kilosort.py")["sha256"] == expected_api,
          "native API source changed")
    actual_python = {str(p) for p in source_root.rglob("*.py")}
    check(actual_python <= source_paths, "unlisted author Python source")
    check(not any(p.suffix in {".pyc", ".pyo", ".so", ".pyd", ".dylib"}
                  for p in source_root.rglob("*")), "unadmitted compiled/cache author payload")
    check(request["library_versions"], "complete locked environment required")
    for package, version in request["library_versions"].items():
        check(importlib.metadata.version(package) == version, "library version mismatch: " + package)
    check(sys.version == request["python_version"], "Python runtime mismatch")
    # Import only after exact source and environment checks. Isolated interpreter
    # ignores ambient PYTHONPATH and user site packages.
    sys.path.insert(0, str(source_root))
    check(not any(k == "kilosort" or k.startswith("kilosort.") for k in sys.modules),
          "author package preloaded before source authentication")
    import numpy as np
    import torch
    from kilosort.parameters import DEFAULT_SETTINGS
    from kilosort.run_kilosort import run_kilosort
    settings = dict(request["effective_settings"])
    check(set(settings) == set(DEFAULT_SETTINGS), "all effective settings required; no hidden defaults")
    # JSON cannot represent the native positive-infinity tmax. Admit it as an
    # explicit tagged source value, never permit NaN or silently crop the run.
    if settings["tmax"] == {"native_float": "positive-infinity"}:
        settings["tmax"] = float("inf")
    check(settings["tmin"] == 0, "full-recording tmin required")
    check(isinstance(settings["tmax"], (int, float)) and settings["tmax"] >= request["duration_seconds"],
          "full-recording tmax required")
    check(type(request["do_CAR"]) is bool and type(request["invert_sign"]) is bool,
          "explicit preprocessing booleans required")
    signal_pin = request["signal_pin"]
    checked_pin(signal_pin, Path("/input"))
    probe_pin = request["probe_pin"]
    checked_pin(probe_pin, Path("/input"))
    probe_json = read_json(Path(probe_pin["path"]), request["metadata_cap_bytes"])
    check(set(probe_json) == {"chanMap", "xc", "yc", "kcoords", "n_chan"}, "explicit probe schema")
    channels = settings["n_chan_bin"]
    check(type(channels) is int and channels > 0, "binary channels")
    check(request["samples"] * channels * np.dtype(request["data_dtype"]).itemsize == signal_pin["bytes"],
          "complete binary shape/size mismatch")
    check(settings["fs"] == request["sample_frequency_hz"], "source clock mismatch")
    probe = {k: np.asarray(v) if isinstance(v, list) else v for k, v in probe_json.items()}
    check(len(probe["chanMap"]) == probe["n_chan"], "probe size")
    check(len(set(int(x) for x in probe["chanMap"])) == len(probe["chanMap"]), "duplicate channels")
    check(all(0 <= int(x) < channels for x in probe["chanMap"]), "channel outside binary")
    output = Path("/output/native")
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    ops, st, clu, tF, Wall, similar_templates, is_ref, est_contam_rate = run_kilosort(
        settings=settings, probe=probe, probe_name=None, filename=signal_pin["path"],
        data_dir=None, file_object=None, results_dir=output,
        data_dtype=request["data_dtype"], do_CAR=request["do_CAR"],
        invert_sign=request["invert_sign"], device=torch.device(request["device"]),
        progress_bar=None, save_extra_vars=True)
    # Preserve all native files including pre-export arrays. Normalize only the
    # declared saved-event view. Quality labels are never used as I ground truth.
    times = np.load(output / "spike_times.npy", allow_pickle=False, mmap_mode="r")
    labels = np.load(output / "spike_clusters.npy", allow_pickle=False, mmap_mode="r")
    check(times.ndim == labels.ndim == 1 and times.shape == labels.shape, "export shape mismatch")
    check(times.dtype.kind in "iu" and labels.dtype.kind in "iu", "integral source export required")
    check(len(times) <= request["max_events"], "event count cap")
    unit_count = int(Wall.shape[0])
    check(unit_count <= request["max_units"], "unit count cap")
    with open("/output/events.jsonl", "x") as stream:
        for row, (sample, unit) in enumerate(zip(times, labels)):
            check(0 <= int(sample) < request["samples"], "event outside complete source clock")
            check(0 <= int(unit) < unit_count, "unit outside declared source export roster")
            stream.write(json.dumps({"unit_id": str(int(unit)), "sample": int(sample),
                                     "original_row": row}, separators=(",", ":")) + "\n")
    receipt = {"schema": "kilosort4_native_sort_output_v1", "case_id": request["case_id"],
               "profile": request["profile"], "source_version": request["source_version"],
               "unit_ids": [str(x) for x in range(unit_count)],
               "event_count": len(times), "source_events": "native/spike_times.npy and spike_clusters.npy",
               "native_cleanup": "preserved exported duplicate cleanup; no extra scoring shift",
               "event_view": "events.jsonl", "clock": request["clock"],
               "source_native_wall_seconds": time.monotonic() - started,
               "source_settings": request["effective_settings"],
               "scientific_reproduction_pass": None, "source_model_quality_not_truth": True}
    Path("/output/NATIVE_OUTPUT.json").write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")


def main():
    try:
        check(len(sys.argv) == 2 and sys.argv[1] == "/run/request.json", "fixed request path required")
        request = read_json(Path(sys.argv[1]), 4 * 1024 * 1024)
        run(request)
    except BaseException as error:
        body = {"status": "native-failed", "type": type(error).__name__, "message": str(error),
                "traceback": traceback.format_exc()[-32768:], "no_retry": True,
                "scientific_pass": None}
        path = Path("/output/NATIVE_FAILURE.json")
        with path.open("x") as stream:
            json.dump(body, stream, indent=2, allow_nan=False)
        raise


if __name__ == "__main__":
    main()
