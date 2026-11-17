"""Explicit, resumable full-grid/source-geometry producer. Never runs on import.

Authentic execution needs a separately admitted compute/storage protocol. A
partial range is a checkpoint, not a reduced benchmark or completed result.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import io
import json
import math
from pathlib import Path
import platform
import sys
import zipfile

import numpy as np
import glm_search as G
from native_inputs import PreparedPanel, bounded_bytes, checked_bytes, need, sha256

ROOT = Path(__file__).resolve().parent
MODERN_TREND_RUNTIME = {"statsmodels": "0.14.5", "pandas": "2.2.3", "patsy": "1.0.1"}
HOLDS = [
    "authentic full-grid fits and geometry/readouts have not been executed",
    "complete empirical comparator and independent paper qualification remain unavailable",
    "fixed figure basis is not an authenticated winner of all108 configurations",
    "source full-session transforms and alpha selection expose all session rows",
    "paper CA1=24 versus active code=19 neurons remains unresolved",
    "source glob order and parallel classifier RNG are not historically reconstructed",
    "source null-unit regional D2 aggregation and population targets remain unresolved",
    "data/source redistribution rights and protected evaluation policy remain separate",
]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def runtime():
    return {"python": platform.python_version(), **{p: importlib.metadata.version(p)
            for p in ("numpy", "scipy", "scikit-learn")}}


def require_runtime():
    observed = runtime()
    need(all(observed[p] == v for p, v in {"numpy": "2.2.6", "scipy": "1.15.3",
                                          "scikit-learn": "1.6.1"}.items()),
         "producer requires frozen NumPy2.2.6/SciPy1.15.3/scikit-learn1.6.1 runtime")
    return observed


def require_trend_runtime():
    """Explicit current backend, not recovery of the unpinned author runtime."""
    observed = require_runtime()
    observed.update({p: importlib.metadata.version(p) for p in MODERN_TREND_RUNTIME})
    need(all(observed[p] == version for p, version in MODERN_TREND_RUNTIME.items()),
         "trends require current statsmodels0.14.5/pandas2.2.3/patsy1.0.1 backend")
    return observed


def code_binding():
    paths = [ROOT / p for p in ("glm_search.py", "native_inputs.py", "producer.py",
                                "geometry_results.py", "RNG_POLICY.json")]
    paths += [ROOT.parent / "initial-evaluator-v1/evaluator.py",
              ROOT.parent / "oof-prediction-replay-v2/replay.py"]
    return {str(p.relative_to(ROOT.parent)): sha256(p.read_bytes()) for p in paths}


def execution_binding(panel, svc_policy="current_serial_seeded_v1"):
    return {"schema": "population_original_producer_binding_v1", "source_revision": G.K.SOURCE_REVISION,
            "design_sha256": panel.design_sha256, "code": code_binding(), "runtime": runtime(),
            "svc_policy": svc_policy, "coverage_sha256": getattr(panel, "coverage_sha256", None),
            "grid": [list(v) for v in G.GRID], "alphas_hex": [float(a).hex() for a in G.ALPHAS],
            "folds": 10, "cohort": {"animals": list(G.K.ANIMALS), "sessions": 8, "regions": list(G.K.REGIONS)},
            "qualification": False}


def encode_tree(value, arrays):
    if isinstance(value, np.ndarray):
        need(value.dtype.kind in "biufU", "only plain numeric/string arrays may be saved")
        key = f"array_{len(arrays):06d}"
        arrays[key] = np.array(value, copy=True, order="C")
        return {"__array__": key, "shape": list(value.shape), "dtype": value.dtype.str}
    if isinstance(value, np.generic):
        return encode_tree(value.item(), arrays)
    if isinstance(value, float) and not np.isfinite(value):
        return {"__nonfinite__": "nan" if np.isnan(value) else ("+inf" if value > 0 else "-inf")}
    if isinstance(value, dict):
        need(all(isinstance(k, str) for k in value), "JSON keys must be strings")
        need(not any(k.startswith("__") for k in value), "reserved artifact marker")
        return {k: encode_tree(v, arrays) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode_tree(v, arrays) for v in value]
    need(value is None or isinstance(value, (str, int, float, bool)), "unsupported artifact value")
    return value


def decode_tree(value, arrays):
    if isinstance(value, dict) and "__array__" in value:
        a = arrays[value["__array__"]]
        need(list(a.shape) == value["shape"] and a.dtype.str == value["dtype"], "saved array metadata differs")
        return a
    if isinstance(value, dict) and "__nonfinite__" in value:
        return {"nan": np.nan, "+inf": np.inf, "-inf": -np.inf}[value["__nonfinite__"]]
    if isinstance(value, dict):
        return {k: decode_tree(v, arrays) for k, v in value.items()}
    if isinstance(value, list):
        return [decode_tree(v, arrays) for v in value]
    return value


def save_result(directory, result, binding, *, max_bytes):
    """Exclusive two-file numeric checkpoint; failed/incomplete directories stay."""
    directory = Path(directory)
    need(type(max_bytes) is int and max_bytes > 0, "explicit per-result output ceiling required")
    arrays = {}
    tree = encode_tree(result, arrays)
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    payload = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        need(sum(i.file_size for i in archive.infolist()) <= max_bytes,
             "expanded result exceeds declared output ceiling")
    record = {"schema": "population_numeric_result_v1", "binding": binding, "result": tree,
              "arrays": {"path": "arrays.npz", "bytes": len(payload), "sha256": sha256(payload)}}
    encoded = canonical(record) + b"\n"
    need(len(payload) + len(encoded) <= max_bytes, "result exceeds declared output ceiling")
    directory.mkdir(parents=False, exist_ok=False)
    (directory / "arrays.npz").write_bytes(payload)
    (directory / "record.json").write_bytes(encoded)
    return {"path": directory.name, "bytes": len(payload) + len(encoded),
            "record_sha256": sha256(encoded), "array_sha256": sha256(payload)}


def load_result(directory, binding, *, max_bytes, arrays=True):
    directory = Path(directory)
    need(not directory.is_symlink(), "checkpoint directory cannot be a symlink")
    record_path = directory / "record.json"
    # Local checkpoint envelope is untrusted until its nested binding is checked.
    raw_record = bounded_bytes(record_path, limit=max_bytes)
    record = json.loads(raw_record)
    need(record.get("schema") == "population_numeric_result_v1" and record.get("binding") == binding,
         "checkpoint code/input/runtime binding differs")
    pin = record["arrays"]
    need(pin["path"] == "arrays.npz" and pin["bytes"] + len(raw_record) <= max_bytes,
         "checkpoint array path/ceiling differs")
    raw = checked_bytes(directory / "arrays.npz", pin["sha256"], pin["bytes"], max_bytes)
    if not arrays:
        return record["result"]
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        names = [i.filename for i in infos]
        need(len(names) == len(set(names)) and all(n.startswith("array_") and n.endswith(".npy")
             and "/" not in n for n in names), "checkpoint numeric member names differ")
        need(sum(i.file_size for i in infos) <= max_bytes, "checkpoint expanded arrays exceed ceiling")
        members = {}
        for info in infos:
            content = archive.read(info)
            stream = io.BytesIO(content)
            version = np.lib.format.read_magic(stream)
            need(version in ((1, 0), (2, 0)), "checkpoint NPY version unsupported")
            shape, fortran, dtype = np.lib.format._read_array_header(stream, version, max_header_size=16384)
            need(not fortran and dtype.kind in "biufU" and not dtype.hasobject
                 and all(type(v) is int and v >= 0 for v in shape), "checkpoint numeric dtype/shape")
            size = math.prod(shape) * dtype.itemsize
            need(size <= max_bytes and stream.tell() + size == len(content), "checkpoint NPY payload length")
            members[info.filename[:-4]] = content
        values = {key: np.load(io.BytesIO(content), allow_pickle=False) for key, content in members.items()}
    return decode_tree(record["result"], values)


def run_glm(panel, output, *, max_result_bytes, start=0, stop=13824):
    require_runtime()
    need(type(start) is int and type(stop) is int and 0 <= start < stop <= 13824,
         "valid chunk of complete13824-job plan required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binding = execution_binding(panel)
    pool_cache = {}
    written = []
    for index, job in enumerate(G.job_plan()):
        if not start <= index < stop:
            continue
        target = output / job["id"]
        if target.exists():
            saved = load_result(target, binding, max_bytes=max_result_bytes, arrays=False)
            need(saved.get("job") == job, "checkpoint job identity differs")
            continue
        animal, session, region = job["animal"], job["session_index"], job["region"]
        # Explicit paired check prevents different epoch rows from defining the
        # two regions while reusing the same pooled behavioral basis.
        panel.paired(animal, session)
        if animal not in pool_cache:
            pool_cache[animal] = G.pooled_latents(panel.load_session, animal)
        packet = panel.load_session(animal, session, region)
        result = G.fit_session(packet, pool_cache[animal], job["basis_index"])
        result.update(job=job, case_id=packet["case_id"], packet_pin=packet["packet_pin"],
                      source_asset_id=packet["source_asset_id"], source_epoch=packet["source_epoch"],
                      prediction_roles={"predictions": "original full-row selected-alpha refit",
                                        "oof_predictions": "additional selected-alpha refits; selection exposed all folds"})
        result["source_session_mean_selected_cv_d2"] = float(np.mean(
            result["test_scores"][np.arange(len(result["selected_alpha_indices"])), result["selected_alpha_indices"]]))
        written.append(save_result(target, result, binding, max_bytes=max_result_bytes))
    return {"schema": "population_grid_chunk_v1", "range": [start, stop], "written": written,
            "full_job_count": 13824, "qualification": False}


def geometry_id(job):
    return f"{job['region']}-r{job['repetition']:03d}-{job['case_id']}"


def restore_rng(rng, saved):
    rng.set_state((saved["algorithm"], np.asarray(saved["keys"], dtype=np.uint32),
                   saved["position"], saved["has_gauss"], saved["cached_gaussian"]))


def run_geometry(panel, output, *, max_result_bytes, svc_policy):
    import geometry_results as R
    require_runtime()
    need(svc_policy == "current_serial_seeded_v1", "resumable panel requires explicit reproducible current route")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    binding = execution_binding(panel, svc_policy)
    generators = {region: np.random.RandomState(seed) for region, seed in R.REGION_SEEDS.items()}
    for job in R.geometry_plan():
        target = output / geometry_id(job)
        rng = generators[job["region"]]
        before = R.state(rng)
        if target.exists():
            saved = load_result(target, binding, max_bytes=max_result_bytes)
            need(saved["job"] == job and saved["rng_before"] == before,
                 "geometry checkpoint does not continue identical source stream")
            restore_rng(rng, saved["rng_after"])
            continue
        packet = panel.load_session(job["animal"], job["session"] - 1, job["region"])
        prepared = R.prepare_geometry(packet, job["region"])
        result = R.geometry_repetition(prepared["x"], prepared["z"], prepared["row_ids"],
                                       prepared["unit_ids"], rng=rng, repetition=job["repetition"],
                                       svc_policy=svc_policy)
        result.update(job=job, case_id=job["case_id"], behavior=prepared["behavior"],
                      packet_pin=packet["packet_pin"], selected_times=prepared["t"][result["row_positions"]],
                      selected_trial_ids=prepared["trial"][result["row_positions"]])
        save_result(target, result, binding, max_bytes=max_result_bytes)
    return {"geometry_jobs": 64000, "qualification": False}


def validate_complete_grid(directory, binding, *, max_result_bytes):
    records = []
    cells = {(r, b): [] for r in G.K.REGIONS for b in range(108)}
    for job in G.job_plan():
        result = load_result(Path(directory) / job["id"], binding, max_bytes=max_result_bytes, arrays=False)
        need(result.get("job") == job, "complete grid contains a mismatched job")
        records.append(job["id"])
        cells[(job["region"], job["basis_index"])].append(
            decode_tree(result["source_session_mean_selected_cv_d2"], {}))
    scores = []
    import warnings
    for (region, index), values in cells.items():
        need(len(values) == 64, "configuration score requires all64 source cells")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            score = float(np.nanmean(values))
        scores.append({"region": region, "basis_index": index, "basis": list(G.GRID[index]),
                       "session_values": np.asarray(values), "score": score,
                       "aggregation": "source find_best_params nanmean of64 ordinary per-unit session means"})
    return {"jobs": records, "configuration_scores": scores, "winner": None}


def reduce_complete(panel, glm_directory, geometry_directory, output, *, max_result_bytes, glm_pr_seed):
    import geometry_results as R
    binding = execution_binding(panel)
    grid = validate_complete_grid(glm_directory, binding, max_result_bytes=max_result_bytes)
    need(type(glm_pr_seed) is int and 0 <= glm_pr_seed < 2**32,
         "explicit current GLM PR seed required; original figure seed unavailable")
    rng = np.random.RandomState(glm_pr_seed)
    sessions = []
    for animal in G.K.ANIMALS:
        for session in range(8):
            for region in G.K.REGIONS:
                cid = f"{animal}-s{session + 1:02d}-{region}"
                job_id = f"{region}-b{G.GRID.index(G.FIGURE_BASIS):03d}-{animal}-s{session + 1:02d}"
                fitted = load_result(Path(glm_directory) / job_id, binding, max_bytes=max_result_bytes)
                need(fitted["case_id"] == cid, "GLM fit case identity differs")
                pr = R.glm_pr_result(fitted["counts"], fitted["predictions"], fitted["cv_scores"],
                                     fitted["selected_alpha_indices"], fitted["unit_ids"], rng=rng,
                                     case_id=cid, row_ids=fitted["row_ids"])
                repetitions = []
                for repetition in range(500):
                    job = {"case_id": cid, "animal": animal, "session": session + 1,
                           "region": region, "repetition": repetition, "region_seed": R.REGION_SEEDS[region]}
                    result = load_result(Path(geometry_directory) / geometry_id(job), binding, max_bytes=max_result_bytes)
                    need(result["job"] == job and result["packet_pin"] == fitted["packet_pin"],
                         "geometry/GLM native case source binding differs")
                    repetitions.append(result)
                sessions.append(R.session_result(repetitions, pr, case_id=cid,
                                                  behavior=repetitions[0]["behavior"]))
    result = R.panel_result(sessions)
    result.update(grid_jobs=13824, geometry_jobs=64000, figure_basis=list(G.FIGURE_BASIS),
                  across_basis_winner=None, glm_pr_seed=glm_pr_seed, qualification=False,
                  configuration_scores=grid["configuration_scores"],
                  source_construction_holds=HOLDS)
    return save_result(output, result, binding, max_bytes=max_result_bytes)


def replay_module():
    spec = importlib.util.spec_from_file_location("_population_original_oof_replay",
                                                  ROOT.parent / "oof-prediction-replay-v2/replay.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def oof_session(panel, glm_directory, animal, session, basis_index, *, max_result_bytes):
    """Directly form the existing scorer's exact native-ID prediction contract."""
    replay = replay_module()
    raw = panel.paired(animal, session)
    reference = replay.prepare_reference(raw)
    parts = []
    for region in G.K.REGIONS:
        jid = f"{region}-b{basis_index:03d}-{animal}-s{session + 1:02d}"
        result = load_result(Path(glm_directory) / jid, execution_binding(panel), max_bytes=max_result_bytes)
        need(result["job"]["animal"] == animal and result["job"]["session_index"] == session
             and result["job"]["region"] == region and result["job"]["basis_index"] == basis_index,
             "OOF saved job identity differs")
        need(np.array_equal(result["row_ids"], reference["bin_ids"]), "OOF native row order differs")
        parts.append(result)
    predictions = {"predictions": np.column_stack([p["oof_predictions"] for p in parts]),
                   "bin_ids": parts[0]["row_ids"], "unit_ids": np.concatenate([p["unit_ids"] for p in parts]),
                   "fold_ids": parts[0]["fold_ids"]}
    need(np.array_equal(parts[0]["fold_ids"], parts[1]["fold_ids"]), "region OOF folds differ")
    replay.validate_predictions(predictions, reference, "source_selected_alpha_oof_extension")
    return raw, predictions


def export_oof_panel(panel, glm_directory, output, *, max_result_bytes, basis_index):
    need(type(basis_index) is int and 0 <= basis_index < 108, "explicit source basis index required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for animal in G.K.ANIMALS:
        for session in range(8):
            raw, prediction = oof_session(panel, glm_directory, animal, session, basis_index,
                                           max_result_bytes=max_result_bytes)
            paths = {}
            for role, arrays in (("reference", raw), ("author", prediction)):
                path = output / f"{animal}-s{session + 1:02d}-{role}.npz"
                buffer = io.BytesIO()
                np.savez_compressed(buffer, **arrays)
                data = buffer.getvalue()
                need(len(data) <= max_result_bytes, "OOF export per-file ceiling")
                path.write_bytes(data)
                paths[role] = {"path": path.name, "bytes": len(data), "sha256": sha256(data)}
            case = panel.by_key[(animal, session, "CA1")]
            rows.append({"animal": animal, "session_index": session,
                         "epoch_id": f"{case['source_asset_id']}:{case['source_epoch']}", **paths})
    manifest = {"source_revision": G.K.SOURCE_REVISION, "dandiset_version": "0.240511.0307",
                "basis_index": basis_index, "sessions": rows, "qualification": False,
                "exposure": "source full-session transforms and all-fold alpha selection; additional OOF refits"}
    (output / "OOF.json").write_bytes(canonical(manifest) + b"\n")
    for role in ("reference", "author"):
        compatible = {**manifest, "sessions": [{"animal": r["animal"], "session_index": r["session_index"],
                      "epoch_id": r["epoch_id"], **r[role]} for r in rows]}
        G.K.validate_panel_manifest(compatible)
        (output / f"{role.upper()}.json").write_bytes(canonical(compatible) + b"\n")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "glm", "geometry", "reduce", "oof", "trends"))
    parser.add_argument("--prepared-directory")
    parser.add_argument("--design")
    parser.add_argument("--design-sha256")
    parser.add_argument("--trial-coverage")
    parser.add_argument("--output")
    parser.add_argument("--glm-directory")
    parser.add_argument("--geometry-directory")
    parser.add_argument("--panel-result")
    parser.add_argument("--max-result-bytes", type=int)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--stop", type=int, default=13824)
    parser.add_argument("--glm-pr-seed", type=int)
    parser.add_argument("--basis-index", type=int)
    args = parser.parse_args()
    if args.operation == "plan":
        print(json.dumps({"glm_jobs": 13824, "geometry_jobs": 64000, "bases": 108,
                          "alphas": 10, "folds": 10, "sessions_regions": 128,
                          "fits_per_eligible_unit_per_basis": 111, "holds": HOLDS}))
        return
    need(all((args.prepared_directory, args.design, args.design_sha256, args.output,
              args.max_result_bytes)), "explicit inputs, output and result byte ceiling required")
    panel = PreparedPanel(args.prepared_directory, args.design, args.design_sha256, args.trial_coverage)
    if args.operation == "glm":
        result = run_glm(panel, args.output, max_result_bytes=args.max_result_bytes, start=args.start, stop=args.stop)
    elif args.operation == "geometry":
        result = run_geometry(panel, args.output, max_result_bytes=args.max_result_bytes,
                              svc_policy="current_serial_seeded_v1")
    elif args.operation == "reduce":
        need(args.glm_directory and args.geometry_directory, "both complete result directories required")
        result = reduce_complete(panel, args.glm_directory, args.geometry_directory, args.output,
                                 max_result_bytes=args.max_result_bytes, glm_pr_seed=args.glm_pr_seed)
    elif args.operation == "oof":
        need(args.glm_directory, "source GLM directory required")
        result = export_oof_panel(panel, args.glm_directory, args.output,
                                  max_result_bytes=args.max_result_bytes, basis_index=args.basis_index)
    else:
        import geometry_results as R
        observed = require_trend_runtime()
        need(args.panel_result, "complete reduced panel result required")
        binding = execution_binding(panel)
        reduced = load_result(args.panel_result, binding, max_bytes=args.max_result_bytes)
        result = R.source_trends(reduced)
        result["current_backend_runtime"] = observed
        result["historical_runtime_authenticated"] = False
        save_result(args.output, result, binding, max_bytes=args.max_result_bytes)
    print(json.dumps({"operation": args.operation, "finished_requested_operation": True,
                      "qualification": False, "result_keys": list(result)}))


if __name__ == "__main__":
    main()
