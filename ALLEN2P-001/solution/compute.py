"""Source-bound descriptive dF/F ratios, with explicit alternative estimators.

Neither method estimates unbiased biological prevalence. Import is I/O-free;
all scientific work is behind main or explicit functions. No runtime download.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
from pathlib import Path, PurePosixPath

import h5py
import numpy as np

PIPELINE_ID = "allen2p-original-trial-means-v2"
SOURCE_SHA256 = "7c9f26aea7f636126c7fe0c1fdf445229b1850601d03be7d30a13c3cda4578b1"
METHOD_SHA256 = "cc0d04e23708ceae550902212167a5ac46ca47652bd147880abb9d102693d7c5"
MANIFEST_SHA256 = "1b678f699e50065b16230d1206aa5459fec2132435882f62813004d6c5b12a29"
METHODS = ("same_trials", "repeated_split_mean_ratio")
BASE = "processing/brain_observatory_pipeline"
STIM = "stimulus/presentation/drifting_gratings_stimulus"
THRESHOLD = .5
PUBLIC_FILES = ("presentations.csv", "trial_responses.csv", "condition_means.csv",
                "estimates.csv", "per_neuron.csv", "results.json", "run_metadata.json", "findings.md")
COMPONENT_KEYS = ("n_selection_pref", "selection_pref_mean_dff", "n_measure_pref", "n_measure_orth_plus",
                  "n_measure_orth_minus", "n_measure_null", "r_pref", "r_orth_plus", "r_orth_minus",
                  "r_orth", "r_null", "osi_denominator", "dsi_denominator", "osi", "dsi")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_text(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def source_text(value):
    if isinstance(value, (bytes, np.bytes_)):
        return bytes(value).decode("utf-8")
    return str(value)


def scalar_text(value):
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError("Expected one source metadata value")
    return source_text(array.reshape(-1)[0])


def integer_array(value, name):
    value = np.asarray(value)
    if value.dtype.kind not in "iuf" or not np.isfinite(value).all():
        raise ValueError(f"{name} must contain finite integers")
    if np.any(value != np.floor(value)) or np.any(np.abs(value) > 2**53):
        raise ValueError(f"{name} must contain exact bounded integers")
    return value.astype(np.int64)


def finite_number(value, name):
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"Nonfinite {name}; no silent exclusion or replacement")
    return number


def software_versions():
    return dict(python=platform.python_version(), numpy=np.__version__, h5py=h5py.__version__)


def check_versions():
    versions = software_versions()
    if not versions["python"].startswith("3.12.") or versions["numpy"] != "2.2.6" or versions["h5py"] != "3.13.0":
        raise ValueError(f"Oracle requires pinned numerical stack; found {versions}")
    return versions


def load_inputs(source_dir, method_contract_path="/app/method_contract.json"):
    root, method_path = Path(source_dir), Path(method_contract_path)
    manifest_path = root / "source_manifest.json"
    if MANIFEST_SHA256 is None:
        raise ValueError("Source manifest has not been frozen")
    if root.is_symlink() or manifest_path.is_symlink() or method_path.is_symlink():
        raise ValueError("Symlinked source or contract")
    if sha256(manifest_path) != MANIFEST_SHA256:
        raise ValueError("Source manifest fingerprint mismatch")
    if sha256(method_path) != METHOD_SHA256:
        raise ValueError("Public method contract fingerprint mismatch")
    manifest = json.loads(manifest_path.read_text())
    contract = json.loads(method_path.read_text())
    hashes, paths = {}, {}
    for item in manifest["files"]:
        relative = PurePosixPath(item["path"])
        if relative.is_absolute() or ".." in relative.parts or not relative.parts:
            raise ValueError("Unsafe source path")
        path = root.joinpath(*relative.parts)
        if any(root.joinpath(*relative.parts[:i]).is_symlink() for i in range(1, len(relative.parts) + 1)):
            raise ValueError("Symlinked source member")
        if not path.is_file() or path.stat().st_size != item["size_bytes"]:
            raise ValueError(f"Original source size mismatch: {relative}")
        digest = sha256(path)
        if digest != item["sha256"]:
            raise ValueError(f"Original source hash mismatch: {relative}")
        if item["path"] in paths:
            raise ValueError("Duplicate source path")
        paths[item["path"]] = path
        hashes[item["path"]] = digest
    source_name = contract["input"]["file"]
    if hashes.get(source_name) != SOURCE_SHA256:
        raise ValueError("Original NWB identity mismatch")
    return dict(manifest=manifest, contract=contract, source_path=paths[source_name], source_sha256=hashes,
                source_manifest_sha256=MANIFEST_SHA256, source_nwb_sha256=SOURCE_SHA256,
                method_contract_sha256=METHOD_SHA256)


def prepare_presentations(stimulus_data, features, frame_duration, n_source_frames):
    """Preserve original row IDs; expose exact chronological RNG draw order."""
    data = np.asarray(stimulus_data, dtype=np.float64)
    names = [source_text(value) for value in features]
    bounds = integer_array(frame_duration, "frame_duration")
    if data.ndim != 2 or data.shape[1] != len(names) or len(set(names)) != len(names):
        raise ValueError("Invalid abstract-feature stimulus layout")
    if bounds.shape != (len(data), 2) or len(data) == 0:
        raise ValueError("Invalid stimulus frame bounds")
    if np.any(bounds[:, 0] < 0) or np.any(bounds[:, 1] <= bounds[:, 0]) or np.any(bounds[:, 1] > n_source_frames):
        raise ValueError("Invalid half-open source interval; cannot repair")
    try:
        direction = data[:, names.index("orientation")]
        frequency = data[:, names.index("temporal_frequency")]
        blank = data[:, names.index("blank_sweep")]
    except ValueError as error:
        raise ValueError("Missing required stimulus feature") from error
    if np.isinf(direction).any() or np.isinf(frequency).any() or not np.isfinite(blank).all():
        raise ValueError("Nonfinite stimulus feature other than defined blank NaN")
    original_ids = np.arange(len(data), dtype=np.int64)
    order = np.lexsort((original_ids, bounds[:, 1], bounds[:, 0]))
    direction, frequency, blank, bounds = direction[order], frequency[order], blank[order], bounds[order]
    included = ~((blank > 0) | np.isnan(direction) | np.isnan(frequency))
    if not included.any():
        raise ValueError("No nonblank tuning presentations")
    directions = np.unique(direction[included])
    frequencies = np.unique(frequency[included])
    if not np.array_equal(directions, np.arange(0., 360., 45.)) or np.any(frequencies <= 0):
        raise ValueError("Unexpected direction or positive temporal-frequency grid")
    rows = [dict(trial_index=index, source_row_id=int(order[index]), start_frame=int(a), end_frame=int(b),
                 n_frames=int(b - a), direction_deg=None if np.isnan(direction[index]) else float(direction[index]),
                 temporal_frequency_hz=None if np.isnan(frequency[index]) else float(frequency[index]),
                 blank_sweep=float(blank[index]), tuning_included=int(included[index]))
            for index, (a, b) in enumerate(bounds)]
    return dict(presentations=rows, source_row_ids=order, start_frame=bounds[:, 0], end_frame=bounds[:, 1],
                direction=direction, temporal_frequency=frequency, blank_sweep=blank,
                tuning_included=included, directions=directions, frequencies=frequencies)


def read_source(inputs, pilot_cells=None):
    if pilot_cells is not None and (isinstance(pilot_cells, bool) or pilot_cells not in range(1, 5)):
        raise ValueError("Pilot must process the first one through four source cells")
    with h5py.File(inputs["source_path"], "r") as nwb:
        dff = nwb[f"{BASE}/DfOverF/imaging_plane_1/data"]
        timestamps = np.asarray(nwb[f"{BASE}/DfOverF/imaging_plane_1/timestamps"][()], dtype=np.float64)
        ids = integer_array(nwb[f"{BASE}/ImageSegmentation/cell_specimen_ids"][()], "cell_specimen_ids")
        roi_ids = np.asarray([source_text(value) for value in nwb[f"{BASE}/ImageSegmentation/roi_ids"][()]])
        if dff.ndim != 2 or ids.ndim != 1 or dff.shape[0] != len(ids) or roi_ids.shape != ids.shape or not len(ids):
            raise ValueError("Source cell rows, cell IDs and ROI IDs do not align")
        if len(set(ids.tolist())) != len(ids) or len(set(roi_ids.tolist())) != len(ids) or np.any(ids <= 0):
            raise ValueError("Source cell/ROI identities must be unique and valid")
        if timestamps.shape != (dff.shape[1],) or not np.isfinite(timestamps).all() or np.any(np.diff(timestamps) <= 0):
            raise ValueError("Invalid original dF/F frame timestamps")
        experiment = int(scalar_text(nwb["general/session_id"][()]))
        region = scalar_text(nwb["general/optophysiology/imaging_plane_1/location"][()])
        session = scalar_text(nwb["general/session_type"][()])
        if (experiment, region, session) != (501271265, "VISp", "three_session_A"):
            raise ValueError("Original experiment/area/session mismatch")
        source = prepare_presentations(nwb[f"{STIM}/data"][()], nwb[f"{STIM}/features"][()],
                                       nwb[f"{STIM}/frame_duration"][()], dff.shape[1])
        count = len(ids) if pilot_cells is None else min(pilot_cells, len(ids))
        # Float64 conversion matches the public arithmetic; stored dF/F values
        # are not additionally rescaled using the legacy unit='frame' attribute.
        traces = np.asarray(dff[:count, :], dtype=np.float64)
        source.update(cell_ids=ids[:count], roi_ids=roi_ids[:count], source_cell_index=np.arange(count),
                      all_source_cell_ids=ids, n_neurons_source_total=len(ids),
                      n_source_frames=dff.shape[1], timestamps=timestamps, dff=traces,
                      source_dff_dtype=str(dff.dtype), source_dff_unit=source_text(dff.attrs.get("unit", "")),
                      ophys_experiment_id=experiment, targeted_structure=region, session_type=session,
                      status="ok" if pilot_cells is None else "resource_pilot")
    return source


def trial_responses(source):
    responses = np.empty((len(source["cell_ids"]), len(source["source_row_ids"])), dtype=np.float64)
    with np.errstate(over="raise", invalid="raise", divide="raise"):
        for index, (start, end) in enumerate(zip(source["start_frame"], source["end_frame"])):
            segment = source["dff"][:, start:end]
            if not np.isfinite(segment).all():
                raise ValueError("Nonfinite source response-window value")
            responses[:, index] = segment.mean(axis=1, dtype=np.float64)
    if not np.isfinite(responses).all():
        raise ValueError("Nonfinite trial response")
    return responses


def condition_means(responses, source, mask):
    responses = np.asarray(responses, dtype=np.float64)
    mask = np.asarray(mask, dtype=bool)
    if responses.shape != (len(source["cell_ids"]), len(source["source_row_ids"])) or mask.shape != (responses.shape[1],):
        raise ValueError("Trial response/mask identity mismatch")
    if not np.isfinite(responses).all():
        raise ValueError("Nonfinite trial response")
    means = np.full((responses.shape[0], len(source["directions"]), len(source["frequencies"])), np.nan)
    counts = np.zeros(means.shape[1:], dtype=np.int64)
    for d, direction in enumerate(source["directions"]):
        for f, frequency in enumerate(source["frequencies"]):
            selected = mask & source["tuning_included"] & (source["direction"] == direction) & (source["temporal_frequency"] == frequency)
            counts[d, f] = selected.sum()
            if counts[d, f]:
                with np.errstate(over="raise", invalid="raise"):
                    means[:, d, f] = responses[:, selected].mean(axis=1, dtype=np.float64)
                if not np.isfinite(means[:, d, f]).all():
                    raise ValueError("Nonfinite condition mean")
    return means, counts


def ratio(pref, comparator):
    if pref is None or comparator is None:
        return None, None, "missing_measurement_condition"
    denominator = finite_number(pref + comparator, "ratio denominator")
    if denominator == 0:
        return None, denominator, "zero_denominator"
    value = finite_number(finite_number(pref - comparator, "ratio numerator") / denominator, "ratio")
    return value, denominator, "ok"


def estimate_cell(cell_id, select, measure, n_select, n_measure, directions, frequencies,
                  replicate=0, selection_half="all", measurement_half="all"):
    row = dict(cell_specimen_id=int(cell_id), replicate=replicate, selection_half=selection_half,
               measurement_half=measurement_half, selection_status="no_selection_conditions",
               preferred_direction_deg=None, preferred_temporal_frequency_hz=None,
               **{key: None for key in COMPONENT_KEYS},
               osi_status="no_selection_conditions", dsi_status="no_selection_conditions")
    if np.isinf(select).any() or np.isinf(measure).any():
        raise ValueError("Infinite condition means")
    if not np.isfinite(select).any():
        return row
    # C-order first maximum implements direction-major, then frequency ties.
    direction, frequency = np.unravel_index(np.nanargmax(select), select.shape)
    row.update(selection_status="ok", preferred_direction_deg=float(directions[direction]),
               preferred_temporal_frequency_hz=float(frequencies[frequency]),
               n_selection_pref=int(n_select[direction, frequency]),
               selection_pref_mean_dff=finite_number(select[direction, frequency], "selection mean"))
    for name, offset in [("pref", 0), ("orth_plus", 2), ("orth_minus", -2), ("null", 4)]:
        index = (direction + offset) % 8
        count = int(n_measure[index, frequency])
        row["n_measure_" + name] = count
        row["r_" + name] = finite_number(measure[index, frequency], "measurement mean") if count else None
    if row["r_orth_plus"] is not None and row["r_orth_minus"] is not None:
        row["r_orth"] = finite_number((row["r_orth_plus"] + row["r_orth_minus"]) / 2., "orthogonal mean")
    row["osi"], row["osi_denominator"], row["osi_status"] = ratio(row["r_pref"], row["r_orth"])
    row["dsi"], row["dsi_denominator"], row["dsi_status"] = ratio(row["r_pref"], row["r_null"])
    return row


def flag(osi, dsi):
    return int((osi is not None and osi > THRESHOLD) or (dsi is not None and dsi > THRESHOLD))


def make_masks(n_presentations):
    rng = np.random.default_rng(0)
    return np.stack([rng.random(n_presentations) < .5 for _ in range(50)])


def analyze(source, responses, method="same_trials"):
    if method not in METHODS:
        raise ValueError("Unknown public method")
    n_cells, n_trials = responses.shape
    all_means, all_counts = condition_means(responses, source, np.ones(n_trials, dtype=bool))
    masks = np.zeros((0, n_trials), dtype=bool) if method == "same_trials" else make_masks(n_trials)
    estimates, split_fractions = [], []
    cases = [(0, "all", "all", all_means, all_means, all_counts, all_counts)]
    if method != "same_trials":
        cases = []
        for index, mask in enumerate(masks, start=1):
            means_a, counts_a = condition_means(responses, source, mask)
            means_b, counts_b = condition_means(responses, source, ~mask)
            cases.extend([(index, "A", "B", means_a, means_b, counts_a, counts_b),
                          (index, "B", "A", means_b, means_a, counts_b, counts_a)])
    for replicate, select_half, measure_half, select, measure, n_select, n_measure in cases:
        rows = [estimate_cell(cell_id, select[c], measure[c], n_select, n_measure,
                              source["directions"], source["frequencies"], replicate, select_half, measure_half)
                for c, cell_id in enumerate(source["cell_ids"])]
        estimates.extend(rows)
        split_fractions.append(sum(flag(row["osi"], row["dsi"]) for row in rows) / n_cells)
    by_cell = {int(cell_id): [] for cell_id in source["cell_ids"]}
    for row in estimates:
        by_cell[row["cell_specimen_id"]].append(row)
    neurons = []
    for c, cell_id in enumerate(source["cell_ids"]):
        row = dict(source_cell_index=int(source["source_cell_index"][c]), cell_specimen_id=int(cell_id), roi_id=str(source["roi_ids"][c]))
        for metric in ("osi", "dsi"):
            values = [estimate[metric] for estimate in by_cell[int(cell_id)] if estimate[metric] is not None]
            row["n_valid_" + metric] = len(values)
            row[metric] = finite_number(np.mean(values, dtype=np.float64), "aggregate ratio") if values else None
            row[metric + "_status"] = "defined" if values else "no_valid_estimates"
        row["selective"] = flag(row["osi"], row["dsi"])
        neurons.append(row)
    n_osi = sum(row["osi"] is not None for row in neurons)
    n_dsi = sum(row["dsi"] is not None for row in neurons)
    n_either = sum(row["osi"] is not None or row["dsi"] is not None for row in neurons)
    n_selective = sum(row["selective"] for row in neurons)
    results = dict(method=method, n_neurons_total=n_cells, n_selective=n_selective,
                   selective_fraction=n_selective / n_cells, threshold=THRESHOLD,
                   n_osi_defined=n_osi, n_dsi_defined=n_dsi, n_either_defined=n_either,
                   n_both_undefined=n_cells - n_either, n_osi_undefined=n_cells - n_osi,
                   n_dsi_undefined=n_cells - n_dsi, n_estimates_per_cell=len(cases))
    if method != "same_trials":
        paired = np.asarray(split_fractions, dtype=np.float64).reshape(50, 2).mean(axis=1)
        results.update(split_fraction_mean=float(paired.mean()), split_fraction_sd=float(paired.std(ddof=0)))
    return dict(all_condition_means=all_means, all_condition_counts=all_counts,
                masks=masks, estimates=estimates, neurons=neurons, results=results)


def make_metadata(inputs, source, method, versions=None):
    return dict(status=source["status"], task_id="ALLEN2P-001", method=method,
                **{key: inputs[key] for key in ("source_manifest_sha256", "source_nwb_sha256", "method_contract_sha256", "source_sha256")},
                **{key: source[key] for key in ("ophys_experiment_id", "targeted_structure", "session_type", "n_source_frames")},
                n_neurons_total=len(source["cell_ids"]), n_neurons_source_total=source["n_neurons_source_total"],
                n_presentations_total=len(source["source_row_ids"]),
                n_presentations_nonblank=int(source["tuning_included"].sum()),
                n_conditions=len(source["directions"]) * len(source["frequencies"]),
                directions_deg=source["directions"].tolist(), temporal_frequencies_hz=source["frequencies"].tolist(),
                source_dff_dtype=source["source_dff_dtype"], source_dff_unit_attribute=source["source_dff_unit"],
                source_dff_unit_interpretation="Archived dF/F numeric values unchanged as returned by AllenSDK; legacy unit attribute retained, not used as scaling.",
                software_versions=software_versions() if versions is None else versions,
                method_contract=inputs["contract"])


def ensure_fresh_outputs(output_dir, private_dir):
    output_dir, private_dir = Path(output_dir), Path(private_dir)
    for folder in {output_dir, private_dir}:
        if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
            raise FileExistsError(f"Unsafe evidence directory: {folder}")
    for path in [*(output_dir / name for name in PUBLIC_FILES), private_dir / "analysis_arrays.npz"]:
        if path.exists() or path.is_symlink():
            raise FileExistsError(f"Refusing to overwrite existing evidence: {path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)


def write_csv(path, fields, rows):
    with Path(path).open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(output_dir, private_dir, inputs, source, responses, analysis, metadata):
    output_dir, private_dir = Path(output_dir), Path(private_dir)
    schema = inputs["contract"]["outputs"]
    trial_rows = (dict(cell_specimen_id=int(cell_id), source_row_id=int(row_id), mean_dff=float(responses[c, t]))
                  for c, cell_id in enumerate(source["cell_ids"]) for t, row_id in enumerate(source["source_row_ids"]))
    condition_rows = (dict(cell_specimen_id=int(cell_id), direction_deg=float(direction), temporal_frequency_hz=float(frequency),
                           n_trials=int(analysis["all_condition_counts"][d, f]),
                           mean_dff=float(analysis["all_condition_means"][c, d, f]) if analysis["all_condition_counts"][d, f] else None)
                      for c, cell_id in enumerate(source["cell_ids"]) for d, direction in enumerate(source["directions"])
                      for f, frequency in enumerate(source["frequencies"]))
    for filename, rows in [("presentations.csv", source["presentations"]), ("trial_responses.csv", trial_rows),
                           ("condition_means.csv", condition_rows), ("estimates.csv", analysis["estimates"]),
                           ("per_neuron.csv", analysis["neurons"])]:
        write_csv(output_dir / filename, schema[filename], rows)
    results = analysis["results"]
    for filename, value in [("results.json", results), ("run_metadata.json", metadata)]:
        with (output_dir / filename).open("x") as stream:
            stream.write(json_text(value))
    with (output_dir / "findings.md").open("x") as stream:
        stream.write(f"# Archived-dF/F descriptive method result\n\n"
                     f"Method `{results['method']}` flags {results['n_selective']}/{results['n_neurons_total']} "
                     f"processed source cells ({results['selective_fraction']:.12g}); status `{metadata['status']}`. "
                     f"Both ratios are undefined for {results['n_both_undefined']} cells. "
                     "These signed ratio thresholds describe this recording and response definition, not unbiased "
                     "biological prevalence or the paper's responsive-event population. Preference selection, "
                     "limited repetitions, negative responses and small denominators affect interpretation; "
                     "not flagged does not mean biologically untuned.\n")
        if results["method"] == "repeated_split_mean_ratio":
            stream.write(f"\nThe separate paired split-fraction mean is {results['split_fraction_mean']:.12g} "
                         f"and population SD {results['split_fraction_sd']:.12g}. These overlapping splits "
                         "are not independent replicates and this SD is not a confidence interval.\n")
    arrays = {key: np.asarray(source[key]) for key in ("cell_ids", "roi_ids", "source_cell_index", "all_source_cell_ids",
              "source_row_ids", "start_frame", "end_frame", "direction", "temporal_frequency", "blank_sweep",
              "tuning_included", "directions", "frequencies")}
    arrays.update(pipeline_id=np.asarray(PIPELINE_ID), trial_response=responses,
                  all_condition_means=analysis["all_condition_means"], all_condition_counts=analysis["all_condition_counts"],
                  split_masks=analysis["masks"], estimates_json=np.asarray(json_text(analysis["estimates"])),
                  neurons_json=np.asarray(json_text(analysis["neurons"])), metadata_json=np.asarray(json_text(metadata)),
                  results_json=np.asarray(json_text(results)), presentations_json=np.asarray(json_text(source["presentations"])))
    with (private_dir / "analysis_arrays.npz").open("xb") as stream:
        np.savez_compressed(stream, **arrays)


def failure_outputs(output_dir, error):
    value = dict(status="failed_precondition", task_id="ALLEN2P-001", reason=f"{type(error).__name__}: {error}")
    for filename in ("results.json", "run_metadata.json"):
        path = Path(output_dir) / filename
        if not path.exists():
            with path.open("x") as stream:
                stream.write(json_text(value))
    path = Path(output_dir) / "findings.md"
    if not path.exists():
        with path.open("x") as stream:
            stream.write(f"# Failed precondition\n\n{value['reason']}\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", "--data-dir", dest="source_dir", type=Path, default=Path(os.environ.get("SOURCE_DIR", "/app/source")))
    parser.add_argument("--method-contract", type=Path, default=Path("/app/method_contract.json"))
    parser.add_argument("--method", choices=METHODS, default=os.environ.get("ALLEN2P_METHOD", "same_trials"))
    parser.add_argument("--output-dir", type=Path, default=Path(os.environ.get("OUTPUT_DIR", "/app/output")))
    parser.add_argument("--private-dir", type=Path, default=Path(os.environ.get("PRIVATE_DIR", "/app/oracle_private")))
    parser.add_argument("--pilot-cells", type=int, choices=range(1, 5))
    args = parser.parse_args(argv)
    private_dir = args.private_dir
    ensure_fresh_outputs(args.output_dir, private_dir)
    try:
        versions = check_versions()
        inputs = load_inputs(args.source_dir, args.method_contract)
        source = read_source(inputs, args.pilot_cells)
        responses = trial_responses(source)
        analysis = analyze(source, responses, args.method)
        metadata = make_metadata(inputs, source, args.method, versions)
        write_outputs(args.output_dir, private_dir, inputs, source, responses, analysis, metadata)
    except Exception as error:
        failure_outputs(args.output_dir, error)
        raise
    print(json.dumps(dict(status=metadata["status"], **analysis["results"]), allow_nan=False))


if __name__ == "__main__":
    main()
