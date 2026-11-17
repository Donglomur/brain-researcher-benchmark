"""Trusted original-model fitting dispatcher, distinct from a candidate sandbox.

Planning reads metadata only. Execution is explicit, one frozen coordinate at a
time; authentic fitting needs a separately admitted resource/exposure protocol.
"""
import argparse
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import sys

REPLAY_SHA = "bd207b15f14129d41b0c9998f712b569004498da95729796d8c97477c87cb1ee"
COHORT_SHA = "58a7baba4a984c17930fef5e733a385bbc4be02f8814ad4e0c9cc0be2b9b1a0f"
PLAN_SCHEMA = "temporal026-original-model-plan/v1"
RESULT_SCHEMA = "temporal026-original-model-result/v1"
VARIABLES = ("t", "cond_stim", "cond_temp", "timepoints_onepulse", "timepoints_twopulse")
SAMPLES = 819
MAX_FILE = 16 * 1024 * 1024


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def parse_json(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def bounded_read(path, limit=MAX_FILE):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as handle:
        before = os.fstat(handle.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
                "bounded regular single-link input required")
        raw = handle.read(limit + 1)
        after = os.fstat(handle.fileno())
    require(len(raw) == before.st_size and len(raw) <= limit and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
            "input changed during read")
    return raw


def load_replay(directory=None):
    directory = Path(directory) if directory else Path(__file__).parent.parent / "source-cv-replay-v1"
    code = bounded_read(directory / "replay.py", 65536)
    roster = bounded_read(directory / "cohort.json", 65536)
    require(hashlib.sha256(code).hexdigest() == REPLAY_SHA and
            hashlib.sha256(roster).hexdigest() == COHORT_SHA, "reviewed CV/cohort source identity mismatch")
    spec = importlib.util.spec_from_file_location("temporal_source_cv_reference", directory / "replay.py")
    module = importlib.util.module_from_spec(spec)
    # Execute the exact authenticated bytes, not a second path read.
    exec(compile(code, str(directory / "replay.py"), "exec"), module.__dict__)
    # The public helper otherwise reopens this metadata path on every call.
    # Bind its identical parsed value to the already authenticated bounded body.
    module.cohort = lambda: parse_json(roster)["selected"]
    return module


def validate_pin(pin, cap):
    require(type(pin) is dict and set(pin) == {"path", "bytes", "sha256"}, "complete input pin required")
    require(type(pin["path"]) is str, "input path must be text")
    path = PurePosixPath(pin["path"])
    require(pin["path"] and pin["path"] != "." and not path.is_absolute() and
            ".." not in path.parts and str(path) == pin["path"] and "\\" not in pin["path"],
            "input path must be canonical and relative")
    require(type(pin["bytes"]) is int and 0 < pin["bytes"] <= cap, "input extent outside bound")
    require(type(pin["sha256"]) is str and len(pin["sha256"]) == 64 and
            all(c in "0123456789abcdef" for c in pin["sha256"]), "input SHA256 required")


def read_member(root, pin):
    validate_pin(pin, MAX_FILE)
    # Traverse relative parents with directory descriptors; refuse aliases.
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = PurePosixPath(pin["path"]).parts
        for part in parts[:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        child = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        with os.fdopen(child, "rb") as handle:
            before = os.fstat(handle.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == pin["bytes"],
                    "input member extent/type/link mismatch")
            raw = handle.read(pin["bytes"] + 1)
            after = os.fstat(handle.fileno())
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "member changed during read")
    finally:
        os.close(fd)
    require(len(raw) == pin["bytes"] and hashlib.sha256(raw).hexdigest() == pin["sha256"], "input member hash mismatch")
    return raw


def validate_inputs(inputs, items):
    require(type(inputs) is dict and set(inputs) == {"schema", "variables", "responses"} and
            inputs["schema"] == "temporal026-original-input-bindings/v1", "original input envelope mismatch")
    require(type(inputs["variables"]) is dict and set(inputs["variables"]) == set(VARIABLES), "five original variables required")
    for pin in inputs["variables"].values():
        validate_pin(pin, 131072)
    require(type(inputs["responses"]) is dict and set(inputs["responses"]) == set(items), "all79 source response identities required")
    for name, pin in inputs["responses"].items():
        validate_pin(pin, 4 * 1024 * 1024)
        require(pin["sha256"] == items[name]["source_data_sha256"], "source table differs from frozen fold metadata")


def make_plan(manifest, manifest_sha256, inputs, branch, scalings=("none", "S"), replay=None):
    replay = replay or load_replay()
    items = replay.validate_manifest(manifest, manifest_sha256)
    require(branch in replay.BRANCHES, "explicit CV column interpretation required")
    require(type(scalings) in (tuple, list) and list(scalings) in [["none", "S"], ["none", "S", "P"]],
            "complete DN none/S required; optional P remains separately indexed")
    validate_inputs(inputs, items)
    jobs = []
    for row in replay.cohort():
        for scaling in scalings:
            for fold in [None] + list(range(12)):
                kind = "full" if fold is None else "cv"
                coordinate = "full" if fold is None else "fold%02d" % fold
                jobs.append({"id": row["id"] + "/DN-" + scaling + "/" + coordinate,
                             "electrode_id": row["id"], "model": "DN", "scaling": scaling,
                             "mode": kind, "fold": fold, "response_columns": "named_response_columns" if fold is None else branch})
    body = {"schema": PLAN_SCHEMA, "manifest_sha256": manifest_sha256,
            "replay_sha256": REPLAY_SHA, "cohort_sha256": COHORT_SHA,
            "input_bindings": inputs, "cv_column_branch": branch, "scalings": list(scalings),
            "jobs": jobs, "counts": {"electrodes": 79, "conditions": 72, "samples": SAMPLES,
                                       "cv_folds": 12, "training_conditions": 66, "query_conditions": 6,
                                       "full_fits": 79 * len(scalings), "cv_fits": 79 * 12 * len(scalings)},
            "fit_recipe": {"sample_rate": 512, "max_nfev": 500, "initialization": "fresh original x0 for every coordinate",
                           "objective": "source scalar summed squared error passed to scipy least_squares",
                           "full_data_exposure": "all72 named819 responses, never held-out prediction"},
            "qualification": "source_producer_only; no authentic fit, original RNG recovery or scientific qualification implied"}
    return {**body, "plan_sha256": digest(body)}


def validate_plan(plan, expected, manifest, replay=None):
    replay = replay or load_replay()
    require(type(plan) is dict and plan.get("plan_sha256") == expected and
            digest({k: v for k, v in plan.items() if k != "plan_sha256"}) == expected, "externally frozen plan digest mismatch")
    rebuilt = make_plan(manifest, plan["manifest_sha256"], plan["input_bindings"],
                        plan["cv_column_branch"], plan["scalings"], replay)
    require(rebuilt == plan, "complete source-coordinate plan differs")
    return replay


def read_variables(root, pins, replay):
    import numpy as np
    raw = {name: read_member(root, pin) for name, pin in pins.items()}
    categories = raw["cond_stim"].decode().split()
    require(categories == list(replay.CATEGORIES), "original category order mismatch")
    time = np.loadtxt(io.BytesIO(raw["t"]), dtype=float)
    conditions = np.loadtxt(io.BytesIO(raw["cond_temp"]), dtype=float)
    one = np.loadtxt(io.BytesIO(raw["timepoints_onepulse"]), dtype=float)
    two = np.loadtxt(io.BytesIO(raw["timepoints_twopulse"]), dtype=float)
    require(time.shape == (SAMPLES,) and np.isfinite(time).all() and (np.diff(time) > 0).all(), "819 finite ordered sample times required")
    require(conditions.shape == (6,) and np.array_equal(conditions, [17, 33, 67, 133, 267, 533]), "source temporal condition labels mismatch")
    for windows, shape in [(one, (6, 2)), (two, (6, 4))]:
        require(windows.shape == shape and np.isfinite(windows).all() and np.equal(windows, np.floor(windows)).all(), "integer original pulse windows required")
        require((windows >= 0).all() and (windows <= SAMPLES).all() and (np.diff(windows, axis=1) > 0).all(), "pulse windows outside ordered source grid")
    return {"t": time, "cond_temp": conditions.astype(int), "onepulse": one.astype(int), "twopulse_repeat": two.astype(int)}


def native_r2(observed, prediction):
    import numpy as np
    observed, prediction = np.asarray(observed, dtype=float), np.asarray(prediction, dtype=float)
    require(observed.shape == prediction.shape and observed.ndim == 1 and np.isfinite(observed).all() and np.isfinite(prediction).all(), "finite paired trace required")
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        ss = np.nansum((observed - np.nanmean(observed)) ** 2)
        value = 1.0 - np.nansum((observed - prediction) ** 2) / ss
    if not math.isfinite(float(value)):
        return {"value": None, "status": "undefined_source_r2", "zero_observed_variance": bool(ss == 0)}
    return {"value": float(value), "status": "finite"}


def run_job(plan, expected, manifest, job_id, input_root, replay=None, numerical=None):
    """Fit exactly one source coordinate; no warm start or hidden target plan."""
    import numpy as np
    replay = validate_plan(plan, expected, manifest, replay)
    jobs = [j for j in plan["jobs"] if j["id"] == job_id]
    require(len(jobs) == 1, "unknown source job coordinate")
    job = jobs[0]
    if numerical is None:
        # Own adjacent model source is authenticated by the component inventory.
        spec = importlib.util.spec_from_file_location("temporal_original_model", Path(__file__).with_name("model.py"))
        numerical = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = numerical
        spec.loader.exec_module(numerical)
    variables = read_variables(input_root, plan["input_bindings"]["variables"], replay)
    raw = read_member(input_root, plan["input_bindings"]["responses"][job["electrode_id"]])
    item = next(x for x in manifest["electrodes"] if x["electrode_id"] == job["electrode_id"])
    rows, responses = replay.parse_source_table(raw)
    require(rows == item["rows"], "ordered response identities differ from frozen source table")
    X = np.stack([numerical.stimulus_timecourse(row["trial_type"], row["temp_cond"],
                  variables["onepulse"], variables["twopulse_repeat"], SAMPLES) for row in rows])
    windows = [variables[row["trial_type"]][row["temp_cond"]].reshape(-1, 2).tolist() for row in rows]
    if job["mode"] == "full":
        train, query = list(range(72)), list(range(72))
        Y = np.asarray(responses, dtype=float)
    else:
        allocation = item["folds"][job["fold"]]
        train, query = allocation["train_rows"], allocation["test_rows"]
        Y = np.asarray(responses, dtype=float)
        if plan["cv_column_branch"] == "source_positional_cv":
            Y = np.column_stack(([row["temp_cond"] for row in rows], Y[:, :-1]))
    result = {"schema": RESULT_SCHEMA, "plan_sha256": expected, "job": job,
              "source_data_sha256": item["source_data_sha256"], "train_rows": train,
              "prediction_rows": query, "prediction_identities": [rows[i] for i in query],
              "qualification": "unqualified_original_model_output", "status": "numerical_failure"}
    try:
        fitted = numerical.fit(X[train], Y[train], scaling=job["scaling"],
                               categories=[rows[i]["img_cat"] for i in train],
                               pulse_windows=[windows[i] for i in train], sample_rate=512, max_nfev=500)
        result["fit"] = fitted.as_dict()
        predictions = []
        components = []
        for i in query:
            parts = numerical.predict(X[i], fitted.parameters, scaling=job["scaling"],
                                      category=rows[i]["img_cat"], pulse_windows=windows[i], sample_rate=512,
                                      components=(job["mode"] == "full"))
            if job["mode"] == "full":
                components.append({key: np.asarray(value).tolist() for key, value in parts.items()})
                prediction = np.asarray(parts["response"], dtype=float)
            else:
                prediction = np.asarray(parts, dtype=float)
            require(prediction.shape == (SAMPLES,) and np.isfinite(prediction).all(), "model returned invalid trace")
            predictions.append(prediction.tolist())
        result["predictions"] = predictions
        result["observations"] = Y[query].tolist()
        if job["mode"] == "full":
            result["components"] = components
            result["exposure"] = "all72 named819 responses used in fit; biological summaries, not held-out performance"
        else:
            result["condition_r2"] = [native_r2(Y[i], prediction) for i, prediction in zip(query, predictions)]
            if all(v["status"] == "finite" for v in result["condition_r2"]):
                rounded = np.round([v["value"] for v in result["condition_r2"]], 3)
                result["rounded_condition_r2"] = rounded.tolist()
                result["fold_r2"] = float(np.round(np.mean(rounded), 4))
            else:
                result["rounded_condition_r2"] = None
                result["fold_r2"] = None
            result["exposure"] = "66 source training conditions; six disjoint queries; fresh original initialization"
        result["status"] = "converged" if fitted.success else "nonconverged_source_parameters_retained"
        encoded(result)
    except (ValueError, FloatingPointError, OverflowError) as exc:
        result = {k: v for k, v in result.items() if k not in {"fit", "predictions", "observations", "components", "condition_r2", "rounded_condition_r2", "fold_r2"}}
        result.update(status="numerical_failure", error=type(exc).__name__ + ": " + str(exc))
    return result


def validate_result(result, plan, manifest):
    """Check complete coordinate identities and recompute exposed CV reduction.

    These are trusted operator outputs, not an adversarial prediction channel;
    input/output hashes and the source exposure boundary remain explicit.
    """
    import numpy as np
    require(type(result) is dict and result.get("schema") == RESULT_SCHEMA and
            result.get("plan_sha256") == plan["plan_sha256"], "result schema/plan mismatch")
    job = result.get("job", {})
    require(type(job) is dict and job in plan["jobs"], "foreign/mutated source result")
    item = next(x for x in manifest["electrodes"] if x["electrode_id"] == job["electrode_id"])
    allocation = item["folds"][job["fold"]] if job["mode"] == "cv" else None
    train = allocation["train_rows"] if allocation else list(range(72))
    query = allocation["test_rows"] if allocation else list(range(72))
    require(result.get("source_data_sha256") == item["source_data_sha256"] and
            result.get("train_rows") == train and result.get("prediction_rows") == query and
            result.get("prediction_identities") == [item["rows"][i] for i in query], "source result row/exposure identity mismatch")
    status = result.get("status")
    require(status in {"converged", "nonconverged_source_parameters_retained", "numerical_failure"}, "unknown fit status")
    if status == "numerical_failure":
        require(type(result.get("error")) is str and result["error"] and
                not any(k in result for k in ("predictions", "observations", "fold_r2", "components")), "failed fit must not advertise numerical outputs")
        return {"job": job, "status": status, "fold_r2": None}
    require(type(result.get("fit")) is dict and result["fit"].get("success") is (status == "converged"), "optimizer success/status mismatch")
    observed, predictions = np.asarray(result.get("observations"), dtype=float), np.asarray(result.get("predictions"), dtype=float)
    require(observed.shape == predictions.shape == (len(query), SAMPLES) and
            np.isfinite(observed).all() and np.isfinite(predictions).all(), "complete finite result traces required")
    score = None
    if job["mode"] == "cv":
        values = [native_r2(a, b) for a, b in zip(observed, predictions)]
        rounded = np.round([v["value"] for v in values], 3).tolist() if all(v["status"] == "finite" for v in values) else None
        score = float(np.round(np.mean(rounded), 4)) if rounded is not None else None
        require(result.get("condition_r2") == values and result.get("rounded_condition_r2") == rounded and
                result.get("fold_r2") == score, "CV source rounding/score differs from retained traces")
    else:
        parts = result.get("components")
        require(type(parts) is list and len(parts) == 72, "all full-fit model components required")
        for prediction, part in zip(predictions, parts):
            require(type(part) is dict and set(part) == {"response", "linear", "numerator", "drive", "normalization_pool", "denominator", "semisaturation", "category_scale"}, "complete DN component namespace required")
            for key in ("response", "linear", "numerator", "drive", "normalization_pool", "denominator"):
                a = np.asarray(part[key], dtype=float)
                require(a.shape == (SAMPLES,) and np.isfinite(a).all(), "finite DN component trace required")
            require(np.array_equal(part["response"], prediction) and np.array_equal(part["drive"], part["numerator"]), "DN component alias/response mismatch")
            require(all(type(part[k]) in (int, float) and math.isfinite(part[k]) for k in ("semisaturation", "category_scale")), "finite DN component scalar required")
    return {"job": job, "status": status, "fold_r2": score}


def collect(plan, expected, manifest, results, bootstrap_seed, replay=None):
    """Complete Figure3 source CV reduction; retain full-fit coordinates separately."""
    import numpy as np
    replay = validate_plan(plan, expected, manifest, replay)
    require(type(bootstrap_seed) is int and 0 <= bootstrap_seed < 2**32, "prospective bootstrap seed required")
    jobs = {j["id"]: j for j in plan["jobs"]}
    records = {}
    for result in results:
        require(len(records) < len(jobs), "too many source results")
        compact = validate_result(result, plan, manifest)
        name = compact["job"]["id"]
        require(name not in records, "duplicate source result")
        records[name] = compact
    require(set(records) == set(jobs), "all source jobs, including failures, required")
    failures = [{"job": name, "status": row.get("status")} for name, row in records.items() if row.get("status") != "converged"]
    electrode_scores = []
    for electrode in replay.cohort():
        for scaling in plan["scalings"]:
            scores = [records[electrode["id"] + "/DN-" + scaling + "/fold%02d" % fold].get("fold_r2") for fold in range(12)]
            valid = all(type(v) in (int, float) and math.isfinite(v) for v in scores) and all(
                records[electrode["id"] + "/DN-" + scaling + "/fold%02d" % fold]["status"] == "converged" for fold in range(12))
            electrode_scores.append({**electrode, "scaling": scaling, "fold_r2": scores,
                                     "r2": float(np.round(np.mean(scores), 4)) if valid else None})
    rng = np.random.RandomState(bootstrap_seed)
    regional = []
    for region in ("V1-V3", "VOTC", "LOTC"):
        for scaling in plan["scalings"]:
            rows = [x for x in electrode_scores if x["varea"] == region and x["scaling"] == scaling]
            values = [x["r2"] for x in rows]
            item = {"region": region, "scaling": scaling, "electrodes": [x["id"] for x in rows],
                    "participants": sorted({x["subject"] for x in rows}), "status": "undefined_incomplete_or_nonfinite"}
            if not failures and all(v is not None for v in values):
                a = np.asarray(values)
                draws = rng.choice(len(a), size=(1000, len(a)), replace=True)
                medians = np.median(a[draws], axis=1)
                item.update(status="finite_descriptive", median=float(np.median(medians)),
                            interval68=np.nanpercentile(medians, [16, 84]).tolist())
            regional.append(item)
    return {"schema": "temporal026-source-results-collection/v1", "plan_sha256": expected,
            "complete_job_count": len(records), "failures": failures, "electrode_cv": electrode_scores,
            "figure3_regional_cv": regional, "bootstrap": {"seed": bootstrap_seed, "resamples": 1000,
             "unit": "electrodes descriptively resampled within region; not independent participants",
             "historical_rng_recovered": False},
            "full_fit_jobs": [j["id"] for j in plan["jobs"] if j["mode"] == "full"],
            "full_fit_warning": "Full-fit parameter file r2 in author source is CV score; do not relabel as full-fit R2.",
            "biological_outputs": "Use the distinct full-fit response/components with biological.py; Figure3 is not the whole empirical family.",
            "scientific_qualification": False}


def write_new(path, value, limit=MAX_FILE):
    raw = encoded(value) + b"\n"
    require(len(raw) <= limit, "result exceeds explicit output bound")
    with open(path, "xb") as handle:
        handle.write(raw)
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-dir")
    sub = parser.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("plan")
    p.add_argument("--manifest", required=True); p.add_argument("--manifest-sha256", required=True)
    p.add_argument("--inputs", required=True); p.add_argument("--branch", choices=["source_positional_cv", "named_response_columns"], required=True)
    p.add_argument("--include-P-diagnostic", action="store_true"); p.add_argument("--output", required=True)
    p = sub.add_parser("run-coordinate")
    p.add_argument("--plan", required=True); p.add_argument("--plan-sha256", required=True)
    p.add_argument("--manifest", required=True); p.add_argument("--input-root", required=True)
    p.add_argument("--job", required=True); p.add_argument("--output", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--plan", required=True); p.add_argument("--plan-sha256", required=True)
    p.add_argument("--manifest", required=True); p.add_argument("--results", required=True)
    p.add_argument("--bootstrap-seed", type=int, required=True); p.add_argument("--output", required=True)
    args = parser.parse_args(argv); replay = load_replay(args.replay_dir)
    manifest = parse_json(bounded_read(args.manifest))
    if args.mode == "plan":
        result = make_plan(manifest, args.manifest_sha256, parse_json(bounded_read(args.inputs)), args.branch,
                           ["none", "S", "P"] if args.include_P_diagnostic else ["none", "S"], replay)
    else:
        plan = parse_json(bounded_read(args.plan))
        if args.mode == "run-coordinate":
            result = run_job(plan, args.plan_sha256, manifest, args.job, args.input_root, replay)
        else:
            # Index authenticates individual complete result bodies and bounds total reads.
            index = parse_json(bounded_read(args.results));require(type(index) is list and len(index) == len(plan["jobs"]), "complete result index required")
            require(sum(x["bytes"] for x in index) <= 4 * 1024**3, "result index exceeds finite operator read budget")
            for pin in index:
                validate_pin(pin, MAX_FILE)
            require(len({x["path"] for x in index}) == len(index), "duplicate result member")
            rows = (parse_json(read_member(Path(args.results).parent, pin)) for pin in index)
            result = collect(plan, args.plan_sha256, manifest, rows, args.bootstrap_seed, replay)
            result["result_index_sha256"] = hashlib.sha256(bounded_read(args.results)).hexdigest()
    print(json.dumps(write_new(args.output, result)))
    if result.get("status") in {"numerical_failure", "nonconverged_source_parameters_retained"}:
        return 2
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        raise SystemExit("temporal-original-producer: " + str(exc))
