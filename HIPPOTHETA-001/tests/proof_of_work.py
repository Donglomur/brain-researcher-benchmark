"""Complete fixed-source numerical verification, not a spectral-shape rubric."""
import csv
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path

import numpy as np

from state_contract import CONDITIONS, FS, PIPELINE_ID, WINDOW, peak, summarize, window_support

Q = 1.95e-7
FIELDS = {
    "behavior": "row_id timestamp_s x_cm y_cm position_valid block_id smoothed_x_cm smoothed_y_cm smoothed_valid speed_cm_s speed_valid selected_interval_to_next".split(),
    "blocks": "block_id start_row end_row_exclusive n_rows start_time_s last_time_s n_smoothed n_speed_valid".split(),
    "bouts": "bout_id block_id start_row end_row start_time_s stop_time_s start_sample end_sample n_samples n_windows status".split(),
    "windows": "condition bout_id window_index start_sample end_sample mean_volts mean_square_volts theta_power_v2".split(),
    "spectrum": "condition frequency_hz power_v2_per_hz".split(),
}
INTEGER_FIELDS = {"row_id", "block_id", "start_row", "end_row", "end_row_exclusive",
                  "n_rows", "n_smoothed", "n_speed_valid", "bout_id", "start_sample",
                  "end_sample", "n_samples", "n_windows", "window_index"}
BOOLEAN_FIELDS = {"position_valid", "smoothed_valid", "speed_valid", "selected_interval_to_next"}
NULLABLE_FIELDS = {"x_cm", "y_cm", "block_id", "smoothed_x_cm", "smoothed_y_cm", "speed_cm_s"}
TEXT_FIELDS = {"condition", "status"}
KEY_FIELDS = {"behavior": ("row_id",), "blocks": ("block_id",), "bouts": ("bout_id",),
              "windows": ("condition", "window_index"), "spectrum": ("condition", "frequency_hz")}
FILES = tuple(name + ".csv" for name in FIELDS) + ("results.json", "run_metadata.json", "findings.md")


def reject_constant(value):
    raise AssertionError("nonfinite JSON number: " + value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, "duplicate JSON key: " + key
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(), parse_constant=reject_constant, object_pairs_hook=unique_object)


def parse_number(value):
    assert not isinstance(value, bool) and value is not None, "expected finite number"
    if not isinstance(value, (str, int, float, np.integer, np.floating)):
        raise AssertionError("expected finite number")
    try:
        out = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise AssertionError("expected finite number") from exc
    assert math.isfinite(out), "expected finite number"
    return out


def parse_int(value):
    assert not isinstance(value, (bool, np.bool_)), "boolean is not an integer ID"
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as exc:
        raise AssertionError("invalid integer") from exc
    assert parsed.is_finite() and parsed == parsed.to_integral_value(), "invalid integer"
    return int(parsed)


def parse_bool(value):
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    token = str(value).strip().lower()
    if token in ("true", "false"):
        return token == "true"
    number = parse_int(value)
    assert number in (0, 1), "invalid boolean flag"
    return bool(number)


def close(actual, expected, *, atol, rtol, scale=1.0, label="number"):
    a, b = parse_number(actual) / scale, parse_number(expected) / scale
    assert abs(a - b) <= atol + rtol * abs(b), f"{label} mismatch: {actual!r} vs {expected!r}"


def static_match(actual, expected, path="metadata", *, exact_keys=False):
    """Semantically numeric static objects; no boolean-as-number or extra sources."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), path
        if exact_keys:
            assert set(actual) == set(expected), path + " keys"
        else:
            assert set(expected) <= set(actual), path + " missing keys"
        for key, value in expected.items():
            static_match(actual[key], value, path + "." + key, exact_keys=exact_keys)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), path
        for i, value in enumerate(expected):
            static_match(actual[i], value, f"{path}[{i}]", exact_keys=exact_keys)
    elif isinstance(expected, bool):
        assert isinstance(actual, bool) and actual is expected, path
    elif isinstance(expected, (int, float)):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), path
        assert math.isfinite(actual) and actual == expected, path
    else:
        assert actual == expected, path


def read_table(path, table):
    with Path(path).open(newline="") as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "duplicate/empty CSV headers"
        assert set(FIELDS[table]) <= set(reader.fieldnames), "missing " + table + " columns"
        rows = []
        for raw in reader:
            assert None not in raw, "malformed CSV row"
            row = {}
            for field in FIELDS[table]:
                assert raw[field] is not None, "short CSV row"
                token = raw[field].strip()
                if not token:
                    assert field in NULLABLE_FIELDS and table == "behavior", "unexpected undefined field: " + field
                    row[field] = None
                elif field in TEXT_FIELDS:
                    row[field] = token
                elif field in BOOLEAN_FIELDS:
                    row[field] = parse_bool(token)
                elif field in INTEGER_FIELDS:
                    row[field] = parse_int(token)
                else:
                    row[field] = parse_number(token)
            rows.append(row)
    return keyed(rows, KEY_FIELDS[table])


def keyed(rows, keys):
    result = {}
    for row in rows:
        key = tuple(row[field] for field in keys)
        assert key not in result, "duplicate table key: " + str(key)
        result[key] = row
    return result


def compare_row(actual, expected, table):
    for field, wanted in expected.items():
        value = actual[field]
        label = table + "." + field
        if wanted is None:
            assert value is None, label + " must be undefined"
        elif field in BOOLEAN_FIELDS or field in INTEGER_FIELDS or field in TEXT_FIELDS:
            assert value == wanted, label + " source identity/status mismatch"
        elif field in {"smoothed_x_cm", "smoothed_y_cm", "speed_cm_s"}:
            close(value, wanted, atol=1e-8, rtol=1e-7, label=label)
        elif field == "mean_volts":
            close(value, wanted, atol=1e-9, rtol=1e-7, scale=Q, label=label)
        elif field in {"mean_square_volts", "theta_power_v2", "power_v2_per_hz"}:
            assert value >= 0, label + " must be nonnegative"
            close(value, wanted, atol=1e-9, rtol=1e-6, scale=Q * Q, label=label)
        elif field == "frequency_hz":
            assert value == wanted, "frequency grid mismatch"
        else:
            close(value, wanted, atol=1e-9, rtol=1e-10, label=label)


def check_table(path, table, reference_rows):
    submitted = read_table(path, table)
    reference = keyed(reference_rows, KEY_FIELDS[table])
    assert set(submitted) == set(reference), table + " incomplete or foreign source keys"
    for key, wanted in reference.items():
        compare_row(submitted[key], wanted, table)
    return [submitted[key] for key in sorted(submitted)]


def spectrum_rows(frequencies, spectra):
    return [{"condition": condition, "frequency_hz": float(frequency),
             "power_v2_per_hz": float(spectra[i, j])}
            for i, condition in enumerate(CONDITIONS) for j, frequency in enumerate(frequencies)]


def check_summary(actual, expected, label="results"):
    assert isinstance(actual, dict) and set(expected) <= set(actual), label + " missing fields"
    for field, wanted in expected.items():
        value = actual[field]
        tag = label + "." + field
        if isinstance(wanted, dict):
            if field == "conditions":
                assert set(value) == set(CONDITIONS), "unexpected spectral condition"
            check_summary(value, wanted, tag)
        elif isinstance(wanted, bool):
            assert isinstance(value, bool) and value == wanted, tag
        elif isinstance(wanted, int):
            assert isinstance(value, (int, float)) and not isinstance(value, bool), tag
            assert parse_int(value) == wanted, tag
        elif isinstance(wanted, str):
            assert value == wanted, tag
        elif field == "theta_power_v2":
            assert parse_number(value) >= 0, tag
            close(value, wanted, atol=1e-9, rtol=1e-6, scale=Q * Q, label=tag)
        elif field == "theta_peak_grid_hz":
            assert parse_number(value) == wanted, tag
        elif field == "theta_peak_frequency_hz":
            close(value, wanted, atol=1e-6, rtol=0, label=tag)
        elif field == "peak_difference_hz":
            close(value, wanted, atol=2e-6, rtol=0, label=tag)
        else:
            close(value, wanted, atol=1e-8, rtol=1e-9, label=tag)


def check_metadata(actual, expected):
    assert isinstance(actual, dict), "metadata must be an object"
    for key, wanted in expected.items():
        if key == "software_versions":
            continue
        assert key in actual, "missing metadata field: " + key
        if key == "source_observed":
            assert isinstance(actual[key], dict) and set(actual[key]) == set(wanted), "source_observed keys"
            for field, value in wanted.items():
                tag = "source_observed." + field
                if field in {"lfp_conversion", "position_conversion"}:
                    close(actual[key][field], value, atol=0, rtol=1e-10, label=tag)
                elif field in {"lfp_start_seconds", "lfp_rate_hz", "position_first_timestamp_s", "position_last_timestamp_s"}:
                    close(actual[key][field], value, atol=1e-9, rtol=1e-10, label=tag)
                else:
                    static_match(actual[key][field], value, tag, exact_keys=True)
            continue
        static_match(actual[key], wanted, "metadata." + key,
                     exact_keys=key in {"method_contract", "source_sha256", "source_observed"})
    versions = actual.get("software_versions")
    assert isinstance(versions, dict) and versions, "software_versions must report actual implementation"
    assert all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
               for k, v in versions.items()), "software_versions must be nonempty strings"


def validate_algebra(behavior, blocks, bouts, windows, frequencies, spectra, result, reference):
    """Cross-file arithmetic without inventing classifications from rounded inputs."""
    for row in behavior:
        assert row["position_valid"] == (row["x_cm"] is not None and row["y_cm"] is not None)
        assert row["smoothed_valid"] == (row["smoothed_x_cm"] is not None and row["smoothed_y_cm"] is not None)
        assert row["speed_valid"] == (row["speed_cm_s"] is not None)
        if row["speed_valid"]:
            assert row["speed_cm_s"] >= 0, "negative speed"
    for block in blocks:
        rows = behavior[block["start_row"]:block["end_row_exclusive"]]
        assert len(rows) == block["n_rows"] and rows
        assert all(r["block_id"] == block["block_id"] for r in rows)
        assert sum(r["smoothed_valid"] for r in rows) == block["n_smoothed"]
        assert sum(r["speed_valid"] for r in rows) == block["n_speed_valid"]
    n_samples = reference["metadata"]["source_observed"]["n_lfp_samples"]
    expected_windows = window_support(bouts, n_samples)
    submitted_support = [{key: row[key] for key in expected_windows[0]} for row in windows]
    assert submitted_support == expected_windows, "window/bout support arithmetic mismatch"
    for row in windows:
        # This is a numerical identity, not a variance/quality exclusion rule.
        mean_square = row["mean_square_volts"] / (Q * Q)
        squared_mean = (row["mean_volts"] / Q) ** 2
        assert squared_mean <= mean_square + 1e-9 + 1e-6 * abs(mean_square), "window mean exceeds mean square"
    own = summarize(behavior, blocks, bouts, windows, frequencies, spectra)
    for condition in CONDITIONS:
        # Exact peak-grid/tie/edge classifications come from unrounded source.
        authoritative = reference["results"]["conditions"][condition]
        for field in ("theta_peak_grid_hz", "peak_at_band_edge", "peak_tie_count"):
            own["conditions"][condition][field] = authoritative[field]
        # Reuse the source-defined peak index rather than allowing harmless
        # rounded powers to choose a different maximum or exact-tie category.
        ci = CONDITIONS.index(condition)
        k = int(np.flatnonzero(frequencies == authoritative["theta_peak_grid_hz"])[0])
        interpolated = float(frequencies[k])
        if not authoritative["peak_at_band_edge"]:
            refp = reference["spectra"][ci]
            source_curvature = refp[k - 1] - 2 * refp[k] + refp[k + 1]
            a, b, c = spectra[ci, k - 1:k + 2]
            curvature = a - 2 * b + c
            if source_curvature != 0 and curvature != 0:
                interpolated += 0.5 * (a - c) / curvature * (frequencies[k + 1] - frequencies[k])
        own["conditions"][condition]["theta_peak_frequency_hz"] = interpolated
        values = [w["theta_power_v2"] for w in windows if w["condition"] == condition]
        close(math.fsum(values) / len(values), own["conditions"][condition]["theta_power_v2"],
              atol=1e-9, rtol=1e-6, scale=Q * Q, label="window/mean-spectrum theta integration")
    own["peak_difference_hz"] = (own["conditions"]["locomotion"]["theta_peak_frequency_hz"]
                                 - own["conditions"]["whole_session"]["theta_peak_frequency_hz"])
    check_summary(result, own, "submitted arithmetic")


def validate_output_directory(output, reference):
    output = Path(output)
    for filename in FILES:
        assert (output / filename).is_file(), "missing required output: " + filename
    assert (output / "findings.md").read_text().strip(), "empty findings"
    tables = {name: check_table(output / (name + ".csv"), name, reference[name])
              for name in ("behavior", "blocks", "bouts", "windows")}
    rows = check_table(output / "spectrum.csv", "spectrum",
                       spectrum_rows(reference["frequencies"], reference["spectra"]))
    indexed = keyed(rows, ("condition", "frequency_hz"))
    spectra = np.array([[indexed[(condition, float(f))]["power_v2_per_hz"]
                         for f in reference["frequencies"]] for condition in CONDITIONS])
    result = read_json(output / "results.json")
    check_summary(result, reference["results"])
    check_metadata(read_json(output / "run_metadata.json"), reference["metadata"])
    validate_algebra(**tables, frequencies=reference["frequencies"], spectra=spectra,
                     result=result, reference=reference)
    return result


def _default_contract_path():
    local = Path(__file__).resolve().parents[1] / "environment" / "method_contract.json"
    return local if local.exists() else Path("/app/method_contract.json")


def load_reference(path, *, method_contract_path=None):
    with np.load(path, allow_pickle=False) as archive:
        required = {"ref_behavior_json", "ref_blocks_json", "ref_bouts_json", "ref_windows_json",
                    "ref_frequencies", "ref_spectra", "ref_stats"}
        assert required <= set(archive.files), "obsolete or incomplete source reference; rebuild genuinely"
        stats = json.loads(str(archive["ref_stats"].item()), parse_constant=reject_constant,
                           object_pairs_hook=unique_object)
        assert stats.get("pipeline_id") == PIPELINE_ID, "obsolete reference pipeline"
        assert isinstance(stats.get("metadata"), dict) and isinstance(stats.get("results"), dict)
        reference = {name: json.loads(str(archive["ref_" + name + "_json"].item()),
                                     parse_constant=reject_constant, object_pairs_hook=unique_object)
                     for name in ("behavior", "blocks", "bouts", "windows")}
        reference.update(frequencies=archive["ref_frequencies"].copy(),
                         spectra=archive["ref_spectra"].copy(), metadata=stats["metadata"],
                         results=stats["results"], stats=stats)
    contract_path = Path(method_contract_path or _default_contract_path())
    contract = read_json(contract_path)
    assert contract["contract_id"] == PIPELINE_ID
    static_match(reference["metadata"]["method_contract"], contract, exact_keys=True)
    assert reference["metadata"]["method_contract_sha256"] == hashlib.sha256(contract_path.read_bytes()).hexdigest()
    sources = {row["path"]: row["sha256"] for row in contract["source"]["files"]}
    assert reference["metadata"]["source_sha256"] == sources == stats["source_sha256"]
    assert reference["metadata"]["pipeline_id"] == PIPELINE_ID
    assert reference["metadata"]["status"] == "ok" and reference["results"]["status"] == "ok"
    assert len(reference["behavior"]) == contract["behavior"]["shape"][0]
    assert [row["row_id"] for row in reference["behavior"]] == list(range(len(reference["behavior"])))
    assert np.array_equal(reference["frequencies"], np.fft.rfftfreq(WINDOW, 1.0 / FS)), "reference frequency grid"
    assert reference["spectra"].shape == (2, WINDOW // 2 + 1)
    assert np.isfinite(reference["spectra"]).all() and np.all(reference["spectra"] >= 0)
    for name in ("behavior", "blocks", "bouts", "windows"):
        keyed(reference[name], KEY_FIELDS[name])
    expected = summarize(reference["behavior"], reference["blocks"], reference["bouts"],
                         reference["windows"], reference["frequencies"], reference["spectra"])
    check_summary(reference["results"], expected, "reference arithmetic")
    validate_algebra(reference["behavior"], reference["blocks"], reference["bouts"], reference["windows"],
                     reference["frequencies"], reference["spectra"], reference["results"], reference)
    return reference
