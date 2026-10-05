"""Offline released-event/label selection-sensitivity oracle; no expected-outcome gates."""
import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import sys

import h5py
import numpy as np
import scipy
from scipy.stats import norm, rankdata

from source_reader import read_session, require

TASK = "MTLMEMORY-001"
METHOD_SHA256 = "7e2ed03d8887a62206db229e52024793852a55c1b34202965d4f4fec3038e37d"
MANIFEST_SHA256 = "3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9"
POPULATIONS = ("full_data_selected_same_trials", "crossfit_selected_at_least_five_splits")
REPEATS = 60


def load_inputs(data_dir, method_path):
    raw = Path(method_path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == METHOD_SHA256, "Public method checksum mismatch")
    method = json.loads(raw)
    paths = [Path(__file__).resolve().parents[1] / "environment/stage_data.py", Path("/opt/source/stage_data.py")]
    stager_path = next((p for p in paths if p.is_file()), None)
    require(stager_path is not None, "Source integrity helper not found")
    spec = importlib.util.spec_from_file_location("mtl_source_stage", stager_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    manifest = module.verify_staged(Path(data_dir))
    require(hashlib.sha256((Path(data_dir) / "source_manifest.json").read_bytes()).hexdigest() == MANIFEST_SHA256, "Source manifest checksum mismatch")
    require(manifest["version"] == "0.220126.1852" and len(manifest["files"]) == 87, "Wrong original source release")
    require(method["source_policy"]["source_manifest_sha256"] == MANIFEST_SHA256, "Method/source mismatch")
    return method, manifest


def rank_batch(new, old):
    """Rows are independent units/splits; exact count ranks and explicit asymptotic MWW."""
    new, old = np.asarray(new), np.asarray(old)
    require(new.ndim == old.ndim == 2 and len(new) == len(old), "Rank batch shape mismatch")
    require(new.dtype.kind in "iu" and old.dtype.kind in "iu" and np.all(new >= 0) and np.all(old >= 0), "Rank input must be nonnegative integer counts")
    n0, n1 = new.shape[1], old.shape[1]
    require(n0 > 0 and n1 > 0, "Rank batch requires both classes")
    pooled = np.concatenate([new, old], axis=1)
    ranks = rankdata(pooled, method="average", axis=1, nan_policy="raise")
    twice = 2 * np.sum(ranks[:, n0:], axis=1) - n1 * (n1 + 1)
    require(np.isfinite(twice).all() and np.all(twice == np.rint(twice)), "Nonintegral U2")
    u2 = twice.astype(np.int64)
    require(np.all((0 <= u2) & (u2 <= 2*n0*n1)), "Invalid rank statistic")
    auc = u2.astype(np.float64) / (2*n0*n1)
    tie_sum = np.empty(len(pooled), dtype=np.int64)
    all_tied = np.empty(len(pooled), dtype=bool)
    for row, values in enumerate(pooled):
        _, counts = np.unique(values, return_counts=True)
        tie_sum[row] = sum(int(x)**3-int(x) for x in counts)
        all_tied[row] = len(counts) == 1
    n = n0+n1
    variance = n0*n1/12 * (n+1 - tie_sum.astype(np.float64)/(n*(n-1)))
    require(np.all(variance[~all_tied] > 0), "Invalid tie-corrected rank variance")
    p = np.ones(len(pooled), dtype=np.float64)
    u = u2.astype(np.float64)/2
    z = (np.maximum(u[~all_tied], n0*n1-u[~all_tied]) - n0*n1/2 - .5) / np.sqrt(variance[~all_tied])
    p[~all_tied] = np.minimum(1., 2*norm.sf(z))
    sign = np.where(auc >= .5, 1, -1).astype(np.int64)
    require(np.isfinite(p).all() and np.all((0 <= p) & (p <= 1)), "Nonfinite rank probability")
    return dict(u2=u2, auc=auc, p=p, sign=sign, selected=p < .05, tie_sum=tie_sum, variance=variance)


def generate_membership(records):
    ends = np.cumsum([len(x["labels"]) for x in records], dtype=np.int64)
    bounds = np.r_[0, ends]
    masks = np.zeros((REPEATS, int(bounds[-1])), dtype=bool)
    rng = np.random.Generator(np.random.PCG64(0))
    for repeat in range(REPEATS):
        for index, record in enumerate(records):
            groups = [np.flatnonzero(record["labels"] == value) for value in [0, 1]]
            if min(map(len, groups)) < 4:
                continue
            for group in groups:
                chosen = rng.choice(group, size=len(group)//2, replace=False, shuffle=True)
                masks[repeat, bounds[index] + chosen] = True
    return masks, bounds


def analyze(records):
    masks, bounds = generate_membership(records)
    n_units = len(records)
    full = {key: np.full(n_units, np.nan) for key in ["u2", "auc", "p", "sign", "tie_sum", "variance"]}
    split = {key: np.full((n_units, REPEATS), np.nan) for key in ["train_u2", "train_auc", "train_p", "train_sign", "test_u2", "test_auc", "test_directed"]}
    full_selected = np.zeros(n_units, dtype=bool)
    train_selected = np.zeros((n_units, REPEATS), dtype=bool)
    class_groups = {}
    for index, record in enumerate(records):
        labels, counts = record["labels"], record["counts"]
        require(labels.ndim == counts.ndim == 1 and len(labels) == len(counts), "Count/label axis mismatch")
        require(np.all((labels == 0) | (labels == 1)), "Unexpected rank label")
        n0, n1 = int(np.count_nonzero(labels == 0)), int(np.count_nonzero(labels == 1))
        class_groups.setdefault((n0, n1), []).append(index)
    for (n0, n1), indices in class_groups.items():
        if min(n0, n1) == 0:
            continue
        new = np.stack([records[i]["counts"][records[i]["labels"] == 0] for i in indices])
        old = np.stack([records[i]["counts"][records[i]["labels"] == 1] for i in indices])
        stats = rank_batch(new, old)
        for key in full:
            full[key][indices] = stats[key]
        full_selected[indices] = stats["selected"]
        if min(n0, n1) < 4:
            continue
        for repeat in range(REPEATS):
            trains = [masks[repeat, bounds[i]:bounds[i+1]] for i in indices]
            vectors = {}
            for label, name in [(0, "new"), (1, "old")]:
                vectors["train_"+name] = np.stack([records[i]["counts"][train & (records[i]["labels"] == label)] for i, train in zip(indices, trains)])
                vectors["test_"+name] = np.stack([records[i]["counts"][~train & (records[i]["labels"] == label)] for i, train in zip(indices, trains)])
            train = rank_batch(vectors["train_new"], vectors["train_old"])
            test = rank_batch(vectors["test_new"], vectors["test_old"])
            for key in ["u2", "auc", "p", "sign"]:
                split["train_"+key][indices, repeat] = train[key]
            for key in ["u2", "auc"]:
                split["test_"+key][indices, repeat] = test[key]
            split["test_directed"][indices, repeat] = np.where(train["sign"] == 1, test["auc"], 1-test["auc"])
            train_selected[indices, repeat] = train["selected"]
    neurons, events = [], []
    for i, record in enumerate(records):
        n0 = int(np.count_nonzero(record["labels"] == 0)); n1 = len(record["labels"])-n0
        full_ok = min(n0, n1) >= 1; split_ok = min(n0, n1) >= 4
        n_selected = int(train_selected[i].sum())
        conditional = float(np.mean(split["test_directed"][i, train_selected[i]])) if n_selected else None
        def fvalue(key, integer=False):
            return (int(full[key][i]) if integer else float(full[key][i])) if full_ok else None
        neurons.append(dict(unit_key=record["unit_key"], asset_path=record["asset_path"], subject_id=record["subject_id"],
            unit_id=record["unit_id"], region=record["region"], n_trials=n0+n1, n_new=n0, n_old=n1,
            full_status="ok" if full_ok else "insufficient_class_support", u_old_twice=fvalue("u2", True),
            auc_old=fvalue("auc"), full_p=fvalue("p"), preferred_sign=fvalue("sign", True),
            same_trial_auc=max(float(full["auc"][i]), 1-float(full["auc"][i])) if full_ok else None,
            memory_selective=bool(full_selected[i]), n_usable_splits=REPEATS if split_ok else 0,
            n_selected_splits=n_selected, conditional_auc=conditional,
            conditional_status="defined" if n_selected else "no_selected_splits", heldout_eligible=n_selected >= 5))
        for repeat in range(REPEATS):
            def svalue(key, integer=False):
                return (int(split[key][i, repeat]) if integer else float(split[key][i, repeat])) if split_ok else None
            events.append(dict(unit_key=record["unit_key"], repeat=repeat, status="ok" if split_ok else "insufficient_class_support",
                n_train_new=n0//2 if split_ok else None, n_train_old=n1//2 if split_ok else None,
                n_test_new=n0-n0//2 if split_ok else None, n_test_old=n1-n1//2 if split_ok else None,
                train_u_old_twice=svalue("train_u2", True), train_auc_old=svalue("train_auc"), train_p=svalue("train_p"),
                train_selected=bool(train_selected[i, repeat]), train_preferred_sign=svalue("train_sign", True),
                test_u_old_twice=svalue("test_u2", True), test_auc_old=svalue("test_auc"), test_directed_auc=svalue("test_directed"),
                included_in_conditional_summary=bool(train_selected[i, repeat])))
    def concatenate(key, dtype):
        return np.concatenate([np.asarray(x[key], dtype=dtype) for x in records]) if records else np.empty(0, dtype=dtype)
    count_array = concatenate("counts", np.int64)
    primitive = dict(unit_key=np.asarray([x["unit_key"] for x in records], dtype=str),
        response_unit_index=np.repeat(np.arange(n_units, dtype=np.int64), np.diff(bounds)),
        source_trial_row=concatenate("source_trial_row", np.int64), trial_id=concatenate("trial_id", np.int64),
        source_label=concatenate("labels", np.int64), spike_count=count_array, rate_hz=count_array.astype(np.float64)/1.5,
        repeat_id=np.arange(REPEATS, dtype=np.int64), train_membership=masks)
    private = {"full_"+key: value for key, value in full.items()}
    private.update(split); private.update(full_selected=full_selected, train_selected=train_selected, response_bounds=bounds)
    return neurons, events, primitive, private


def summarize(sessions, neurons, headline):
    require(headline in POPULATIONS, "Unknown headline population")
    same = [x["same_trial_auc"] for x in neurons if x["memory_selective"]]
    conditional = [x["conditional_auc"] for x in neurons if x["heldout_eligible"]]
    def population(values):
        return dict(n_units=len(values), mean_auc=float(np.mean(values)) if values else None, status="defined" if values else "empty_population")
    populations = dict(zip(POPULATIONS, [population(same), population(conditional)]))
    overlap = dict(full_only=0, conditional_only=0, both=0, neither=0)
    for neuron in neurons:
        a, b = neuron["memory_selective"], neuron["heldout_eligible"]
        overlap["both" if a and b else "full_only" if a else "conditional_only" if b else "neither"] += 1
    return dict(status="complete", task_id=TASK, headline_population=headline, headline_status=populations[headline]["status"],
        memory_selective_new_old_auc=populations[headline]["mean_auc"], n_sessions=len(sessions),
        n_patients=len({x["subject_id"] for x in sessions}), n_source_units=sum(x["n_source_units"] for x in sessions),
        n_mtl_units=len(neurons), n_full_test_defined=sum(x["full_status"] == "ok" for x in neurons),
        n_full_test_undefined=sum(x["full_status"] != "ok" for x in neurons), n_memory_selective=len(same),
        proportion_memory_selective=len(same)/len(neurons) if neurons else None, n_crossfit_eligible=len(conditional),
        n_response_rows=sum(x["n_trials"] for x in neurons), n_split_events=REPEATS*len(neurons), populations=populations, population_overlap=overlap)


def make_metadata(manifest, method, sessions, observed, headline, pilot):
    return dict(status="resource_pilot" if pilot else "complete", task_id=TASK, dandiset_id="000004", published_version="0.220126.1852",
        source_manifest_sha256=MANIFEST_SHA256, method_contract_sha256=METHOD_SHA256,
        source_sha256={x["path"]: x["sha256"] for x in manifest["files"]}, method_contract=method, headline_population=headline,
        source_observed=dict(n_sessions=len(sessions), n_patients=len({x["subject_id"] for x in sessions}),
            n_source_trials=sum(x["n_source_trials"] for x in sessions), n_recognition_trials=sum(x["n_recognition_trials"] for x in sessions),
            n_source_units=sum(x["n_source_units"] for x in sessions), n_mtl_units=sum(x["n_mtl_units"] for x in sessions), sessions=observed),
        software_versions=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__, h5py=h5py.__version__))


def safe_path(path):
    path = Path(os.path.abspath(path))
    for part in [path, *path.parents]:
        require(not part.is_symlink(), f"Symlink destination/source ancestor: {part}")
    return path


def prepare_destinations(data_dir, output_dir, private_dir):
    source, output, private = map(safe_path, [data_dir, output_dir, private_dir])
    for a, b in [(source, output), (source, private), (output, private)]:
        require(a != b and a not in b.parents and b not in a.parents, "Source/output/private paths must be disjoint and nonnested")
    for path in [output, private]:
        require(not path.exists() or (path.is_dir() and not any(path.iterdir())), f"Refusing existing evidence: {path}")
    for path in [output, private]:
        path.mkdir(parents=True, exist_ok=True)
    return output, private


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False); stream.write("\n")


def write_csv(path, columns, rows):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader(); writer.writerows(rows)


def save_npz(path, arrays):
    with Path(path).open("xb") as stream:
        np.savez_compressed(stream, **arrays)


def findings(results, pilot):
    if pilot:
        return "# Resource pilot only\n\nOnly the first lexicographic source asset was analyzed. This is not a complete submission or a full-cohort estimate.\n"
    rows = ["# Released-event/label selection sensitivity", "", "| Population | Recorded units | Mean AUC |", "|---|---:|---:|"]
    for name, value in results["populations"].items():
        number = "undefined" if value["mean_auc"] is None else format(value["mean_auc"], ".12g")
        rows.append(f"| {name} | {value['n_units']} | {number} |")
    rows += ["", f"Full-data selection: {results['n_memory_selective']} / {results['n_mtl_units']} source-mapped MTL unit records; {results['n_sessions']} sessions from {results['n_patients']} released subject IDs.", "",
        "These are conditional descriptive method summaries, not unbiased outer validation, physical memory ground truth, an absence/equivalence test, or patient-population inference. Units cluster within sessions and repeated patients; the overlapping random halves are dependent.", "",
        "The fixed 0.2–1.7 s response includes post-stimulus-offset activity in some trials. All released label codes and timestamp occurrences are retained, including unresolved old-label exposure histories, unordered timestamps and exact multiplicities. Continuous observation support is unknown. No behavioral or quality exclusions, deduplication, label reversal, or expected-direction filter was applied."]
    return "\n".join(rows)+"\n"


def execute(data_dir, method_path, output, private, pilot=False, headline=POPULATIONS[1]):
    method, manifest = load_inputs(data_dir, method_path)
    files = sorted(manifest["files"], key=lambda x: x["path"])
    if pilot:
        files = files[:1]
    sessions, trials, units, records, observed = [], [], [], [], []
    for index, source in enumerate(files):
        session, trial_rows, unit_rows, unit_records, source_observed = read_session(Path(data_dir)/source["path"], source)
        sessions.append(session); trials.extend(trial_rows); units.extend(unit_rows); records.extend(unit_records); observed.append(source_observed)
        print(f"Verified and counted source asset {index+1}/{len(files)}: {source['path']}", flush=True)
    neurons, splits, primitive, diagnostics = analyze(records)
    metadata = make_metadata(manifest, method, sessions, observed, headline, pilot)
    results = summarize(sessions, neurons, headline)
    if pilot:
        results.update(status="resource_pilot", scope="first lexicographic asset only; all numbers summarize this one asset, not the full cohort", asset_path=files[0]["path"])
    diagnostics.update(primitive)
    diagnostics.update(metadata_json=np.asarray(json.dumps(metadata, sort_keys=True, allow_nan=False)), results_json=np.asarray(json.dumps(results, sort_keys=True, allow_nan=False)))
    # Write evidence before publishing complete-status JSON markers.
    save_npz(private/"analysis_arrays.npz", diagnostics)
    for name, rows in [("sessions.csv", sessions), ("trials.csv", trials), ("units.csv", units), ("split_events.csv", splits), ("neurons.csv", neurons)]:
        write_csv(output/name, method["outputs"][name]["columns"], rows)
    save_npz(output/"trial_counts.npz", primitive)
    with (output/"findings.md").open("x", encoding="utf-8") as stream:
        stream.write(findings(results, pilot))
    write_json(output/"run_metadata.json", metadata)
    write_json(output/"results.json", results)
    print(json.dumps(results, allow_nan=False), flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("SOURCE_DIR", "/app/data/mtlmemory")))
    parser.add_argument("--method-contract", type=Path, default=Path(os.environ.get("METHOD_CONTRACT", "/app/method_contract.json")))
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--private-dir", type=Path, default=Path(os.environ.get("PRIVATE_DIR", "/app/oracle_private")))
    parser.add_argument("--pilot-first-asset", action="store_true")
    parser.add_argument("--headline-population", choices=POPULATIONS, default=POPULATIONS[1])
    args = parser.parse_args(argv)
    output = None
    try:
        output, private = prepare_destinations(args.data_dir, args.output_dir, args.private_dir)
        execute(args.data_dir, args.method_contract, output, private, args.pilot_first_asset, args.headline_population)
    except Exception as error:
        reason = str(error) or type(error).__name__
        if output is not None:
            failure = dict(status="failed_precondition", task_id=TASK, reason=reason, error_type=type(error).__name__)
            for name in ["results.json", "run_metadata.json", "failure.json"]:
                if not (output/name).exists():
                    write_json(output/name, failure)
            if not (output/"findings.md").exists():
                with (output/"findings.md").open("x", encoding="utf-8") as stream:
                    stream.write("# Failed precondition\n\n"+reason+"\n")
        print(f"{type(error).__name__}: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
