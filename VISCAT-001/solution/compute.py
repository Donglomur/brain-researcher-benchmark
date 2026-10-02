"""Offline, source-authenticated VISCAT method control. Import performs no I/O."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import stat
import sys
import warnings

import h5py
import numpy as np
import scipy

import core
import source_reader

METHOD_SHA256 = "945f61392b72f065fd5c6067b8ae578a4168986dd01fe8c21e1c4900e51842ac"
SOURCE_SHA256 = "3819f2b5e9403f184b94be7d1374476c964c08c054763ec7b8d40cf6bbf7e7b9"
HELPER_SHA256 = "f844ab4e4bc6d3efccca3c4b19277b2fec5484685b93a2481ca9d882cc99bcf2"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(value):
    literal = os.fspath(value)
    require(isinstance(literal, str) and "\x00" not in literal and ".." not in literal.split("/"), "Unsafe parent traversal/path")
    path = Path(literal).absolute()
    for node in (path, *path.parents):
        require(not node.is_symlink(), "Symlink path or ancestor")
        if node.exists() and node != path:
            require(node.is_dir(), "Nondirectory ancestor")
    return path


def regular(path):
    path = safe_path(path)
    require(stat.S_ISREG(path.stat().st_mode), "Expected regular input file")
    return path


def json_value(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def bad(value):
        raise ValueError("Nonfinite JSON token: " + value)
    result = json.loads(body, object_pairs_hook=pairs, parse_constant=bad)
    json.dumps(result, allow_nan=False)
    return result


def load_method(path):
    body = regular(path).read_bytes()
    require(hashlib.sha256(body).hexdigest() == METHOD_SHA256, "Frozen method hash mismatch")
    method = json_value(body)
    require(method["source"]["manifest_sha256"] == SOURCE_SHA256 and method["task_id"] == "VISCAT-001", "Wrong source/method binding")
    return method


def load_inputs(data_dir, contract_path):
    method = load_method(contract_path)
    helper = Path(__file__).absolute().parents[1] / "environment/stage_data.py"
    if not helper.exists():
        helper = Path("/opt/source/stage_data.py")
    helper = regular(helper)
    body = helper.read_bytes()
    require(hashlib.sha256(body).hexdigest() == HELPER_SHA256, "Supplied source helper identity mismatch")
    # Execute exactly the checked source bytes; never import source-adjacent pyc.
    namespace = {"__name__": "viscat_source_staging", "__file__": str(helper)}
    exec(compile(body, str(helper), "exec"), namespace)
    manifest = namespace["verify_staged"](data_dir)
    require(len(manifest["files"]) == 87, "Incomplete authenticated source inventory")
    return method, manifest


def source_scope(data_dir, manifest, pilot=False):
    """Authenticate first in load_inputs; read canonical originals, not a bank."""
    entries = sorted(manifest["files"], key=lambda r: r["path"])
    require(entries, "No original assets")
    if pilot:
        entries = entries[:1]
    sessions, trials, units, records, observed = [], [], [], [], []
    for entry in entries:
        session, source_trials, source_units, source_records, source_observed = source_reader.read_session(
            regular(Path(data_dir) / entry["path"]), entry)
        sessions.append(session); trials.extend(source_trials); units.extend(source_units)
        records.extend(source_records); observed.append(source_observed)
    return sessions, trials, units, records, observed


def source_observed(sessions, observed):
    return dict(n_sessions=len(sessions), n_patients=len({s["subject_id"] for s in sessions}),
                n_source_trials=sum(s["n_source_trials"] for s in sessions),
                n_recognition_trials=sum(s["n_recognition_trials"] for s in sessions),
                n_source_units=sum(s["n_source_units"] for s in sessions),
                n_mtl_units=sum(s["n_mtl_units"] for s in sessions), sessions=observed)


def metadata(method, manifest, sessions, observed, headline, pilot, captured_warnings):
    result = dict(status="resource_pilot" if pilot else "complete", task_id="VISCAT-001", dandiset_id="000004",
                  published_version="0.220126.1852", source_manifest_sha256=SOURCE_SHA256,
                  method_contract_sha256=METHOD_SHA256, source_sha256={r["path"]: r["sha256"] for r in manifest["files"]},
                  method_contract=method, headline_population=headline, source_observed=source_observed(sessions, observed),
                  software_versions={"implementation": "source-h5py-scipy-ranks-rational-H",
                                     "python": platform.python_version(), "numpy": np.__version__,
                                     "scipy": scipy.__version__, "h5py": h5py.__version__},
                  warnings=captured_warnings)
    if pilot:
        result["resource_pilot_scope"] = dict(asset_path=sessions[0]["asset_path"], n_processed_assets=1)
    return result


def disjoint(a, b):
    require(a != b and a not in b.parents and b not in a.parents, "Source/code/evidence paths overlap")


def prepare_destinations(data_dir, contract_path, output_dir, private_dir=None):
    source, contract = safe_path(data_dir), safe_path(contract_path)
    code = safe_path(Path(__file__).absolute().parent)
    code_root = code.parent if (code.parent / "task.toml").is_file() else code
    helper_root = safe_path("/opt/source")
    destinations = [safe_path(output_dir)] + ([safe_path(private_dir)] if private_dir is not None else [])
    for path in destinations:
        require(not path.exists(), "Preserve existing output/private evidence")
        for protected in (source, contract, code_root, helper_root):
            disjoint(path, protected)
    if len(destinations) == 2:
        disjoint(*destinations)
    for path in destinations:
        path.mkdir(parents=True, exist_ok=False)
    return destinations[0], destinations[1] if len(destinations) == 2 else None


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_csv(path, rows, columns):
    with Path(path).open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="raise")
        writer.writeheader()
        for row in rows:
            require(set(row) == set(columns), "Oracle output schema mismatch: " + Path(path).name)
            writer.writerow({key: int(value) if isinstance(value, bool) else value for key, value in row.items()})


def write_outputs(output, private, method, sessions, trials, units, neurons, events, arrays, meta, results):
    for name, rows in (("sessions.csv", sessions), ("trials.csv", trials), ("units.csv", units),
                       ("neurons.csv", neurons), ("split_events.csv", events)):
        write_csv(output / name, rows, method["outputs"][name]["columns"])
    require(set(arrays) == set(method["outputs"]["responses.npz"]["arrays"]), "Response NPZ schema mismatch")
    with (output / "responses.npz").open("xb") as handle:
        np.savez_compressed(handle, **arrays)
    with (output / "findings.md").open("x", encoding="utf-8") as handle:
        handle.write("Descriptive category-selection sensitivity in released recorded units. "
                     "Both explicitly defined populations are reported; their membership and selection conditions differ. "
                     "Overlapping trial halves and within-patient clustering preclude an independent patient-level inference. "
                     "The response window, stored event multiplicities, source category dictionaries and source irregularities are retained.\n")
        handle.write(f"\nFull-data selected units: {results['n_category_selective']}/{results['n_mtl_units']}.\n")
        for name in core.POPULATIONS:
            population = results["populations"][name]
            mean = "undefined (empty population)" if population["mean_auc"] is None else format(population["mean_auc"], ".17g")
            handle.write(f"\n{name}: mean AUC {mean}; {population['n_units']} units.\n")
    if private is not None:
        tables = dict(sessions=sessions, trials=trials, units=units, neurons=neurons, split_events=events)
        with (private / "analysis_arrays.npz").open("xb") as handle:
            np.savez_compressed(handle, **arrays, tables_json=np.asarray(json.dumps(tables, allow_nan=False)),
                                metadata_json=np.asarray(json.dumps(meta, allow_nan=False)),
                                results_json=np.asarray(json.dumps(results, allow_nan=False)))
    write_json(output / "results.json", results)
    write_json(output / "run_metadata.json", meta)


def failure(output, error):
    result = dict(status="failed_precondition", task_id="VISCAT-001", reason=str(error) or type(error).__name__)
    write_json(output / "failure_report.json", result)
    for name in ("results.json", "run_metadata.json"):
        if not (output / name).exists():
            write_json(output / name, result)
    if not (output / "findings.md").exists():
        with (output / "findings.md").open("x", encoding="utf-8") as stream:
            stream.write("No complete scientific result: " + result["reason"] + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/app/data/viscat")
    parser.add_argument("--contract-path")
    parser.add_argument("--output-dir", default=os.environ.get("OUTPUT_DIR", "/app/output"))
    parser.add_argument("--private-dir")
    parser.add_argument("--pilot-first-asset", action="store_true")
    parser.add_argument("--headline-population", choices=core.POPULATIONS, default=core.POPULATIONS[1])
    parser.add_argument("--print-contract", action="store_true")
    args = parser.parse_args(argv)
    path = safe_path(args.contract_path) if args.contract_path else (Path("/app/method_contract.json") if Path("/app/method_contract.json").exists()
            else Path(__file__).absolute().parents[1] / "environment/method_contract.json")
    if args.print_contract:
        print(json.dumps(load_method(path), indent=2, allow_nan=False))
        return 0
    output, private = prepare_destinations(args.data_dir, path, args.output_dir, args.private_dir)
    try:
        require(np.__version__ == "2.2.6", "Supplied oracle RNG sequence requires NumPy2.2.6")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            method, manifest = load_inputs(args.data_dir, path)
            sessions, trials, units, records, observed = source_scope(args.data_dir, manifest, args.pilot_first_asset)
            neurons, events, arrays = core.analyze(records)
        captured = [str(item.message) for item in caught]
        meta = metadata(method, manifest, sessions, observed, args.headline_population, args.pilot_first_asset, captured)
        results = core.summarize(neurons, sessions, len(arrays["spike_count"]), args.headline_population, meta["status"])
        if args.pilot_first_asset:
            results["resource_pilot_scope"] = meta["resource_pilot_scope"]
        write_outputs(output, private, method, sessions, trials, units, neurons, events, arrays, meta, results)
        print(json.dumps(dict(status=meta["status"], n_sessions=len(sessions), n_mtl_units=len(neurons),
                              n_response_rows=len(arrays["spike_count"]), n_split_events=len(events),
                              warnings=captured), allow_nan=False))
    except Exception as error:
        failure(output, error)
        print(type(error).__name__ + ": " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
