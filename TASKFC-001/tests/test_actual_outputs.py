"""AUTHORING QA ONLY for a separately gated, known complete oracle output.

Never include this module in production acceptance: transformations need not
preserve an arbitrary submission lying exactly at public byte/numerical bounds.
No source/output I/O occurs on import. Source reconstruction runs once/session.
"""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

import numpy as np
import pytest
from scipy import stats

import artifact_reader as a
import proof_of_work as p
import sensitivity_math as m
from verifier_fixture_support import canonical_arrays, write_csv, write_json


def fingerprint(root):
    return {name: hashlib.sha256(a.read_bytes(root/name, 64*2**20)).hexdigest()
            for name in a.REQUIRED}


@pytest.fixture(scope="session")
def genuine(original_reference):
    value = os.environ.get("REPAIR_ORACLE_OUTPUT")
    assert value, "Authoring QA requires explicit REPAIR_ORACLE_OUTPUT; never silently skip."
    output = a.guarded_path(value, directory=True)
    before = fingerprint(output)
    # Share the production conftest session fixture and its DATA_DIR convention;
    # this authoring module must not trigger a second source reconstruction.
    reference = original_reference
    assert p.validate_output_directory(output, reference)["status"] == "accepted"
    yield output, reference
    assert fingerprint(output) == before, "Original oracle artifacts changed during authoring QA."


@pytest.fixture
def candidate(tmp_path, genuine):
    original, reference = genuine
    owned = tmp_path/"detached-candidate"
    owned.mkdir()
    for name in a.REQUIRED:
        shutil.copyfile(original/name, owned/name)
        new, old = (owned/name).stat(), (original/name).stat()
        assert (new.st_dev, new.st_ino) != (old.st_dev, old.st_ino)
    try:
        yield owned, reference
    finally:
        # Only this fixture's literal fresh directory; never originals or parent.
        shutil.rmtree(owned)


def arrays(output):
    return a.parse_npz(a.read_bytes(output/"model_arrays.npz", a.CAPS["npz"]))


def csv_rows(output, name):
    return a.parse_csv(a.read_bytes(output/name, a.CAPS["csv"]))


def replay(output, reference):
    accepted = p.canonical_primitives(arrays(output), reference)
    return m.derive_cohort(accepted,
        {pid: person["active"] for pid, person in reference["participants"].items()}, p.PARTICIPANTS)


def write_derived(output, derived):
    write_csv(output/"connectivity.csv", list(derived["per_subject"].values()))
    write_json(output/"connectivity_summary.json", dict(
        schema_version="taskfc-results-v2", status="complete", **derived["summary"]))


@pytest.mark.parametrize("mode", ["baseline", "coherent_keys", "scalar_rounding",
                                  "metadata_records", "harmless_extras", "source_only_primitives"])
def test_authoring_equivalent_positive(candidate, mode, record_property):
    output, reference = candidate
    if mode == "coherent_keys":
        data = arrays(output)
        rng = np.random.default_rng(192)
        s = rng.permutation(10); f = rng.permutation(len(data["frame_time_s"]))
        c = rng.permutation(len(data["design_column_ids"]))
        data["participant_ids"] = data["participant_ids"][s].astype("S")
        data["design_included"] = data["design_included"][s, ::-1][:, :, c]
        for key in ("frame_participant_id", "source_frame_index", "frame_time_s", "roi_signals", "design_values", "residuals"):
            data[key] = data[key][f]
        data["source_frame_index"] = data["source_frame_index"].astype(float)
        data["roi_ids"] = data["roi_ids"][::-1]; data["model_ids"] = data["model_ids"][::-1]
        data["roi_signals"] = data["roi_signals"][:, ::-1]
        data["residuals"] = data["residuals"][:, ::-1, ::-1]
        data["design_column_ids"] = data["design_column_ids"][c]
        data["design_values"] = data["design_values"][:, c]
        np.savez_compressed(output/"model_arrays.npz", **data)
        for name in ("cohort.csv", "events.csv", "connectivity.csv"):
            write_csv(output/name, [{key: row[key] for key in reversed(row)}
                                   for row in csv_rows(output, name)[::-1]])
    elif mode == "scalar_rounding":
        rows = csv_rows(output, "connectivity.csv")
        for row in rows:
            for key in ("connectivity", "background_connectivity", "raw_fisher_z", "background_fisher_z", "raw_minus_background_z"):
                if row[key] != "": row[key] = f"{float(row[key]):.6f}"
        write_csv(output/"connectivity.csv", rows)
        def rounded(value):
            if type(value) is float: return round(value, 6)
            if isinstance(value, dict): return {key: rounded(child) for key, child in value.items()}
            if isinstance(value, list): return [rounded(child) for child in value]
            return value
        write_json(output/"connectivity_summary.json", rounded(json.loads((output/"connectivity_summary.json").read_text())))
    elif mode == "metadata_records":
        metadata = json.loads((output/"run_metadata.json").read_text())
        metadata["source_files"].reverse(); metadata["analysis_observed"].reverse()
        for person in metadata["analysis_observed"]:
            person["models"].reverse()
            for model in person["models"]:
                model["column_ids"].reverse(); model["roi_support"].reverse()
        for header in metadata["source_observed"]["headers"].values(): header["storage_dtype"] = "float32"
        write_json(output/"run_metadata.json", metadata)
    elif mode == "harmless_extras":
        data = arrays(output); data["optional_diagnostic"] = np.zeros((1,)*8)
        np.savez_compressed(output/"model_arrays.npz", **data)
        metadata = json.loads((output/"run_metadata.json").read_text())
        metadata["source_observed"]["description"] = "Authoring-only descriptive extra."
        write_json(output/"run_metadata.json", metadata)
        (output/"findings.md").write_text("Unconstrained descriptive interpretation; no required sign or finding.\n")
    elif mode == "source_only_primitives":
        np.savez_compressed(output/"model_arrays.npz", **canonical_arrays(reference))
        write_derived(output, replay(output, reference))
    assert p.validate_output_directory(output, reference)["status"] == "accepted"
    record_property("qa_classification", "equivalent_positive")


@pytest.mark.parametrize("mode", ["raw_signal", "design", "residual", "membership", "clock",
                                  "missing_frame", "digit_subject", "event_token", "support_digest",
                                  "source_pin", "method_pin", "schema_pin", "source_hash", "late_failure"])
def test_authoring_binding_mutation(candidate, mode, record_property):
    output, reference = candidate
    if mode in ("raw_signal", "design", "residual", "membership", "clock", "missing_frame", "digit_subject"):
        data = arrays(output)
        if mode in ("raw_signal", "design", "residual"):
            key = {"raw_signal": "roi_signals", "design": "design_values", "residual": "residuals"}[mode]
            index = (0,)*data[key].ndim
            old = float(data[key][index])
            data[key][index] += max(.01, 100*(1e-6+1e-6*abs(old)))
            assert abs(float(data[key][index])-old) > 1e-6+1e-6*abs(old)
        if mode == "membership": data["design_included"][0, 0, -1] ^= True
        if mode == "clock": data["frame_time_s"] += .75
        if mode == "missing_frame":
            for key in ("frame_participant_id", "source_frame_index", "frame_time_s", "roi_signals", "design_values", "residuals"):
                data[key] = data[key][:-1]
        if mode == "digit_subject": data["participant_ids"][0] = "1"
        np.savez_compressed(output/"model_arrays.npz", **data)
        with pytest.raises(ValueError): p.canonical_primitives(data, reference)
    elif mode in ("event_token", "support_digest"):
        name = "events.csv" if mode == "event_token" else "cohort.csv"
        rows = csv_rows(output, name)
        rows[0]["onset_token" if mode == "event_token" else "left_support_sha256"] = "not-the-source"
        write_csv(output/name, rows)
    elif mode == "late_failure":
        (output/"failure_report.json").symlink_to(output/"absent")
    else:
        metadata = json.loads((output/"run_metadata.json").read_text())
        if mode == "source_hash": metadata["source_files"][0]["sha256"] = "f"*64
        else: metadata[{"source_pin": "source_manifest_sha256", "method_pin": "method_sha256", "schema_pin": "output_schema_sha256"}[mode]] = "f"*64
        write_json(output/"run_metadata.json", metadata)
    with pytest.raises(ValueError): p.validate_output_directory(output, reference)
    record_property("qa_classification", "effective_binding_rejection")


def component_candidate(original, mode):
    """Wrong-method scalar receipts only; no source changes, refitting or model runs."""
    changed = copy.deepcopy(original)
    rows = changed["per_subject"]
    if mode in ("absolute_r", "swap_models", "reverse_paired", "r_scale_difference"):
        for row in rows.values():
            if mode == "absolute_r":
                for rk, zk in (("connectivity", "raw_fisher_z"), ("background_connectivity", "background_fisher_z")):
                    if row[rk] is not None: row[rk] = abs(row[rk]); row[zk] = m.fisher(row[rk])
            if mode == "swap_models":
                for left, right in (("connectivity", "background_connectivity"), ("raw_fisher_z", "background_fisher_z"), ("raw_status", "background_status")):
                    row[left], row[right] = row[right], row[left]
            if row["raw_minus_background_z"] is not None:
                if mode == "reverse_paired": row["raw_minus_background_z"] *= -1
                elif mode == "r_scale_difference": row["raw_minus_background_z"] = row["connectivity"]-row["background_connectivity"]
                else: row["raw_minus_background_z"] = row["raw_fisher_z"]-row["background_fisher_z"]
        changed["summary"] = m.summarize_subjects(rows, p.PARTICIPANTS)
    elif mode == "arithmetic_r_group":
        if any(original["summary"][group]["status"] != "ok" for group in ("raw", "background")):
            return None, "complete_both_model_support_unavailable"
        for group, key in (("raw", "connectivity"), ("background", "background_connectivity")):
            mean = math.fsum(row[key] for row in rows.values())/10
            changed["summary"][group].update(mean_z=m.fisher(mean), fisher_mean_r=mean)
        changed["summary"]["difference_of_group_fisher_mean_r"] = changed["summary"]["raw"]["fisher_mean_r"]-changed["summary"]["background"]["fisher_mean_r"]
    elif mode == "unpaired_standard_error":
        pair = changed["summary"]["paired_z_sensitivity"]
        if pair["status"] != "ok": return None, "nonzero_complete_paired_variance_unavailable"
        z0 = np.array([row["raw_fisher_z"] for row in rows.values()])
        z1 = np.array([row["background_fisher_z"] for row in rows.values()])
        se = math.sqrt(float(np.var(z0, ddof=1)+np.var(z1, ddof=1))/10)
        if not se > 0.: return None, "unpaired_standard_error_zero"
        mean = pair["mean_raw_minus_background_z"]; t = mean/se
        half = float(stats.t.ppf(.975, 9))*se
        pair.update(sample_sd=se*math.sqrt(10), standard_error=se, t=t,
                    p=float(2*stats.t.sf(abs(t), 9)), ci95=[mean-half, mean+half])
    elif mode == "available_case_group":
        affected = False
        for group, key in (("raw", "raw_fisher_z"), ("background", "background_fisher_z")):
            values = [row[key] for row in rows.values() if row[key] is not None]
            if 0 < len(values) < 10:
                mean = math.fsum(values)/len(values)
                changed["summary"][group].update(status="ok", mean_z=mean, fisher_mean_r=math.tanh(mean))
                affected = True
        if not affected: return None, "no_partial_nonempty_model_support"
        left, right = [changed["summary"][key]["fisher_mean_r"] for key in ("raw", "background")]
        changed["summary"]["difference_of_group_fisher_mean_r"] = left-right if left is not None and right is not None else None
    else:
        raise ValueError("unknown authoring component")
    return changed, None


def observable_differences(original, changed, path=""):
    """Require an actual numeric/null/status change; no minimum outcome direction."""
    result = []
    if isinstance(original, dict):
        assert set(original) == set(changed)
        for key in original: result.extend(observable_differences(original[key], changed[key], path+"/"+key))
    elif isinstance(original, list):
        assert len(original) == len(changed)
        for i, value in enumerate(original): result.extend(observable_differences(value, changed[i], path+f"/{i}"))
    elif original is None or changed is None:
        if original is not changed: result.append(dict(path=path, kind="defined_support_changed", gap=None))
    elif type(original) in (int, float):
        if abs(float(original)-float(changed)) > 1e-6:
            result.append(dict(path=path, kind="numeric", gap=abs(float(original)-float(changed))))
    elif original != changed:
        result.append(dict(path=path, kind="literal_status_changed", gap=None))
    return result


@pytest.mark.parametrize("mode", ["absolute_r", "swap_models", "reverse_paired", "r_scale_difference",
                                  "arithmetic_r_group", "unpaired_standard_error", "available_case_group"])
def test_authoring_actual_component_control(candidate, mode, record_property):
    output, reference = candidate
    original = replay(output, reference)
    immutable = {name: hashlib.sha256((output/name).read_bytes()).hexdigest() for name in
                 ("cohort.csv", "events.csv", "model_arrays.npz", "run_metadata.json", "findings.md")}
    changed, reason = component_candidate(original, mode)
    if changed is None:
        record_property("qa_classification", "control_not_constructed")
        record_property("reason", reason)
        return
    gaps = observable_differences(original, changed)
    write_derived(output, changed)
    assert all(hashlib.sha256((output/name).read_bytes()).hexdigest() == digest for name, digest in immutable.items())
    record_property("changed_observables", json.dumps(gaps, sort_keys=True))
    if gaps:
        artifacts = a.read_artifacts(output)
        with pytest.raises(ValueError): p.validate_derived(artifacts, original)
        with pytest.raises(ValueError): p.validate_output_directory(output, reference)
        record_property("qa_classification", "effective_numerical_rejection")
    else:
        assert p.validate_output_directory(output, reference)["status"] == "accepted"
        record_property("qa_classification", "nondiscriminating_within_public_tolerance")
