"""Gated full-source receipts and output-only controls; no fitting or answer bank.

OUTPUT_DIR must explicitly identify the genuine complete output. This module is
excluded from source-free gates, and never skips a missing configured input.
One session reconstruction serves all its cases. The separate binary production
test reconstructs again. The source-only positive shares verifier ISC algebra,
not the oracle's extraction/cleaning implementation or generated source arrays.
"""
from __future__ import annotations

import copy
import csv
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

import artifact_reader as a
import isc_math as m
import proof_of_work as p
import source_reference as s


def json_write(path, value):
    def encode(item):
        if isinstance(item, Decimal):
            return float(item)
        raise TypeError(type(item).__name__)
    path.write_text(json.dumps(value, default=encode, allow_nan=False), encoding="utf-8")


def csv_write(path, rows):
    assert rows, "the complete source family must not be empty"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def npz_write(path, arrays):
    with path.open("wb") as stream:
        np.savez_compressed(stream, **arrays)


def hashes(root):
    return {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in a.REQUIRED}


@pytest.fixture(scope="session")
def actual():
    configured = os.environ.get("OUTPUT_DIR")
    assert configured, "full-source gate must supply OUTPUT_DIR explicitly"
    root = a.guarded_path(configured, directory=True)
    artifacts = a.read_artifacts(root)
    originals = {name: (root / name).read_bytes() for name in a.REQUIRED}
    before = hashes(root)
    reference = s.reconstruct()
    assert p.validate_output_directory(root, reference)["n_pairs"] == 2340
    x, support = p.canonical_arrays(artifacts["timecourses.npz"], reference)
    estimator = artifacts["isc_results.json"]["isc_estimator"]
    pairs, people, result = p.expected_tables_and_results(x, support, reference, estimator)
    yield dict(root=root, originals=originals, artifacts=artifacts, reference=reference,
               x=x, support=support, pairs=pairs, people=people, result=result)
    assert hashes(root) == before, "the suite modified a genuine original output"


def output_copy(actual, tmp_path):
    root = tmp_path / "output"
    root.mkdir()
    for name, payload in actual["originals"].items():
        with (root / name).open("xb") as stream:
            stream.write(payload)  # Detached files, never hard links to evidence.
    return root


def write_derived(root, pairs, people, result):
    csv_write(root / "isc_pairs.csv", pairs)
    csv_write(root / "isc_per_subject.csv", people)
    json_write(root / "isc_results.json", result)


def set_estimator(root, actual, estimator):
    pairs, people, result = p.expected_tables_and_results(
        actual["x"], actual["support"], actual["reference"], estimator)
    write_derived(root, pairs, people, result)
    metadata = copy.deepcopy(actual["artifacts"]["run_metadata.json"])
    metadata["isc_estimator"] = estimator
    json_write(root / "run_metadata.json", metadata)
    return pairs, people, result


@pytest.mark.parametrize("estimator", ["pairwise", "loo", "leave-one-out"])
def test_actual_each_declared_headline(actual, tmp_path, estimator):
    root = output_copy(actual, tmp_path)
    set_estimator(root, actual, estimator)
    assert p.validate_output_directory(root, actual["reference"])["isc_estimator"] == estimator


def test_independently_reconstructed_source_positive(actual, tmp_path):
    ref = actual["reference"]
    root = tmp_path / "independent-source-output"
    root.mkdir()
    arrays = {key: ref[key] for key in ("participant_ids", "map_ids", "map_labels", "frame_indices",
                                        "visual_map_ids", "raw_coefficients", "isc_inputs")}
    support = ref["canonical_support"]
    arrays.update({key: support[key] for key in ("person_active", "template_active")})
    npz_write(root / "timecourses.npz", arrays)
    csv_write(root / "cohort.csv", ref["cohort"])
    write_derived(root, *p.expected_tables_and_results(ref["isc_inputs"], support, ref, "loo"))
    metadata = copy.deepcopy(ref["metadata"])
    metadata["isc_estimator"] = "loo"
    json_write(root / "run_metadata.json", metadata)
    (root / "findings.md").write_text("Source reconstruction; no direction, ordering, or paper claim.\n")
    assert p.validate_output_directory(root, ref)["n_subjects"] == 40


def test_actual_coherent_axes_rows_columns_and_pair_orientation(actual, tmp_path):
    root = output_copy(actual, tmp_path)
    arrays = copy.deepcopy(actual["artifacts"]["timecourses.npz"])
    pi, ti, mi, vi = np.arange(40)[::-1], np.arange(168)[::-1], np.arange(39)[::-1], np.array([2, 0, 1])
    for key, ix in (("participant_ids", pi), ("frame_indices", ti), ("map_ids", mi),
                    ("map_labels", mi), ("visual_map_ids", vi)):
        arrays[key] = arrays[key][ix]
    arrays["raw_coefficients"] = arrays["raw_coefficients"][np.ix_(pi, ti, mi)]
    arrays["isc_inputs"] = arrays["isc_inputs"][np.ix_(pi, ti, vi)]
    for key in ("person_active", "template_active"):
        arrays[key] = arrays[key][np.ix_(pi, vi)]
    for key in ("frame_indices", "map_ids", "visual_map_ids"):
        arrays[key] = arrays[key].astype(np.float64)
    arrays["participant_ids"] = arrays["participant_ids"].astype("S")
    npz_write(root / "timecourses.npz", arrays)
    for name in ("cohort.csv", "isc_pairs.csv", "isc_per_subject.csv"):
        rows = copy.deepcopy(actual["artifacts"][name])[::-1]
        if name == "isc_pairs.csv":
            for row in rows:
                row["participant_a"], row["participant_b"] = row["participant_b"], row["participant_a"]
        csv_write(root / name, [dict(reversed(list(row.items()))) for row in rows])
    for name in ("isc_results.json", "run_metadata.json"):
        value = copy.deepcopy(actual["artifacts"][name])
        for key in ("per_subject", "per_region", "source_files"):
            if key in value:
                value[key].reverse()
        if "source_observed" in value:
            for key in ("participant_ids", "visual_map_ids", "map_labels", "headers"):
                value["source_observed"][key].reverse()
        json_write(root / name, value)
    assert p.validate_output_directory(root, actual["reference"])


def test_actual_six_decimal_derived_rounding(actual, tmp_path):
    root = output_copy(actual, tmp_path)
    pairs, people, result = copy.deepcopy((actual["pairs"], actual["people"], actual["result"]))
    for rows, keys in ((pairs, ["r"]), (people, ["isc_pairwise", "isc_loo"])):
        for row in rows:
            for key in keys:
                if row[key] is not None:
                    row[key] = format(row[key], ".6f")
    def rounded(value):
        if isinstance(value, float):
            return round(value, 6)
        if isinstance(value, list):
            return [rounded(item) for item in value]
        if isinstance(value, dict):
            return {key: rounded(item) for key, item in value.items()}
        return value
    write_derived(root, pairs, people, rounded(result))
    assert p.validate_output_directory(root, actual["reference"])


def test_actual_harmless_extras_and_free_findings(actual, tmp_path):
    root = output_copy(actual, tmp_path)
    arrays = copy.deepcopy(actual["artifacts"]["timecourses.npz"])
    arrays["extra_finite_diagnostic"] = np.zeros((1, 1, 1, 1))
    npz_write(root / "timecourses.npz", arrays)
    metadata = copy.deepcopy(actual["artifacts"]["run_metadata.json"])
    metadata["source_observed"]["description"] = "Released frame index, not a measured movie-onset clock."
    metadata["software_versions"]["nilearn"] = "not_used"
    json_write(root / "run_metadata.json", metadata)
    (root / "findings.md").write_text("A signed descriptive result with no hypothesis-direction claim.\n")
    # An invented extra file is not an authority and is never opened by the grader.
    npz_write(root / "reference.npz", {"invented_endpoint": np.array([-.75])})
    assert p.validate_output_directory(root, actual["reference"])


def scalar_cells(pairs, people, result):
    cells = {("pair", *sorted((r["participant_a"], r["participant_b"])), int(r["map_id"])): r["r"] for r in pairs}
    for row in people:
        for est in ("pairwise", "loo"):
            cells["person", row["participant_id"], int(row["map_id"]), est] = row["isc_" + est]
    cells["headline",] = result["visual_isc"]
    for est in ("pairwise", "loo"):
        cells["aggregate", est] = result["estimators"][est]["value"]
    for family, key in (("per_subject", "participant_id"), ("per_region", "map_id")):
        for row in result[family]:
            for est in ("pairwise", "loo"):
                cells[family, row[key], est] = row[est]["value"]
    return cells


def verify_component(root, actual, candidate, record_property, *, expected=None):
    """Effectiveness is decided from arithmetic, never inferred from rejection."""
    baseline = (actual["pairs"], actual["people"], actual["result"]) if expected is None else expected
    old, new = scalar_cells(*baseline), scalar_cells(*candidate)
    assert set(old) == set(new)
    gaps = [(key, abs(float(new[key]) - float(value))) for key, value in old.items()
            if value is not None and new[key] is not None]
    differences = [key for key, gap in gaps if gap > m.SCALAR_ATOL]
    differences += [key for key in old if (old[key] is None) != (new[key] is None)]
    record_property("n_scalars_outside_public_tolerance", len(differences))
    record_property("max_scalar_absolute_difference", max((gap for _, gap in gaps), default=0.))
    if differences:
        key = differences[0]
        with pytest.raises(a.ArtifactError, match="numeric mismatch|undefined null|JSON real must be numeric"):
            p.scalar(new[key], old[key], "actual control numerical component")
        with pytest.raises((a.ArtifactError, ValueError), match="numeric mismatch|undefined null|JSON real must be numeric"):
            p.validate_output_directory(root, actual["reference"])
        record_property("control_status", "effective_numerical_rejection")
    else:
        assert p.validate_output_directory(root, actual["reference"])
        record_property("control_status", "control_not_discriminating_within_public_tolerance")


def component(actual, mode):
    """Replace one estimator component, then propagate its reported means."""
    pairs, people, result = copy.deepcopy((actual["pairs"], actual["people"], actual["result"]))
    x, active = actual["x"], actual["support"]["person_active"]
    ids = actual["reference"]["participant_ids"].tolist()
    mids = actual["reference"]["visual_map_ids"].tolist()
    lookup = {person: i for i, person in enumerate(ids)}
    region = {mid: i for i, mid in enumerate(mids)}
    if mode == "region_pooled_series":
        pooled = np.asarray([[math.fsum(float(v) for v in frame) / 3 for frame in person] for person in x])
        if any(m.stable_l2(m.centered(person)) == 0 for person in pooled):
            return None, "control_not_constructed_constant_pooled_series"
        wrong_x = np.repeat(pooled[:, :, None], 3, axis=2)
        try:
            pairs, people, result = p.expected_tables_and_results(wrong_x, actual["support"], actual["reference"], result["isc_estimator"])
        except ValueError as exc:
            if "active Pearson input became constant" not in str(exc):
                raise
            return None, "control_not_constructed_constant_pooled_template"
        return (pairs, people, result), None
    if mode == "signed_to_absolute":
        for row in pairs:
            if row["r"] is not None:
                row["r"] = abs(row["r"])
        for row in people:
            if row["isc_loo"] is not None:
                row["isc_loo"] = abs(row["isc_loo"])
    if mode == "loo_self_inclusion":
        mean_all = np.asarray([[math.fsum(float(x[i, t, r]) for i in range(40)) / 40 for r in range(3)] for t in range(168)])
        for row in people:
            if row["isc_loo"] is not None:
                i, r = lookup[row["participant_id"]], region[row["map_id"]]
                if m.stable_l2(m.centered(mean_all[:, r])) == 0:
                    return None, "control_not_constructed_constant_self_inclusive_template"
                row["isc_loo"] = m.pearson(x[i, :, r], mean_all[:, r])
    keyed = {(*sorted((r["participant_a"], r["participant_b"])), r["map_id"]): r["r"] for r in pairs}
    for row in people:
        person, mid = row["participant_id"], row["map_id"]
        values = [keyed[(*sorted((person, other)), mid)] for other in ids if other != person]
        if mode == "pairwise_self_inclusion":
            values.append(1. if active[lookup[person], region[mid]] else None)
        elif mode == "dropped_partner_denominator":
            values = values[1:]
        row["isc_pairwise"] = m.complete_mean(values)
        # Source support/count receipts intentionally remain untouched: only
        # the actual arithmetic component above is wrong, not metadata.
    for row in result["per_subject"]:
        selected = [v for v in people if v["participant_id"] == row["participant_id"]]
        for est in ("pairwise", "loo"):
            row[est] = p.aggregate(v["isc_" + est] for v in selected)
    for row in result["per_region"]:
        mid = row["map_id"]
        selected = [v for v in people if v["map_id"] == mid]
        row["loo"] = p.aggregate(v["isc_loo"] for v in selected)
        row["pairwise"] = p.aggregate(v["r"] for v in pairs if v["map_id"] == mid)
        if mode in ("pairwise_self_inclusion", "dropped_partner_denominator"):
            row["pairwise"]["value"] = m.complete_mean(v["isc_pairwise"] for v in selected)
            row["pairwise"]["status"] = "ok" if row["pairwise"]["value"] is not None else "incomplete_support"
    for est in ("pairwise", "loo"):
        result["estimators"][est] = p.aggregate(row[est]["value"] for row in result["per_subject"])
    chosen = "loo" if result["isc_estimator"] == "leave-one-out" else result["isc_estimator"]
    result["visual_isc"] = result["estimators"][chosen]["value"]
    result["visual_isc_status"] = result["estimators"][chosen]["status"]
    return (pairs, people, result), None


@pytest.mark.parametrize("mode", ["pairwise_self_inclusion", "loo_self_inclusion", "region_pooled_series",
                                   "signed_to_absolute", "dropped_partner_denominator"])
def test_actual_component_controls(actual, tmp_path, record_property, mode):
    root = output_copy(actual, tmp_path)
    candidate, limitation = component(actual, mode)
    if limitation:
        record_property("control_status", limitation)
        assert p.validate_output_directory(root, actual["reference"])
        return
    write_derived(root, *candidate)
    for name in ("cohort.csv", "timecourses.npz", "run_metadata.json", "findings.md"):
        assert (root / name).read_bytes() == actual["originals"][name]
    verify_component(root, actual, candidate, record_property)


def test_actual_estimator_headline_mismatch_is_numerical(actual, tmp_path, record_property):
    root = output_copy(actual, tmp_path)
    expected = set_estimator(root, actual, "loo")
    candidate = copy.deepcopy(expected)
    candidate[2]["visual_isc"] = candidate[2]["estimators"]["pairwise"]["value"]
    candidate[2]["visual_isc_status"] = candidate[2]["estimators"]["pairwise"]["status"]
    write_derived(root, *candidate)
    verify_component(root, actual, candidate, record_property, expected=expected)


@pytest.mark.parametrize("mode", ["raw_changed", "global_sign_with_unchanged_isc", "invented_bank_replacement"])
def test_actual_source_numeric_binding(actual, tmp_path, record_property, mode):
    root = output_copy(actual, tmp_path)
    arrays = copy.deepcopy(actual["artifacts"]["timecourses.npz"])
    if mode == "raw_changed":
        arrays["raw_coefficients"] = arrays["raw_coefficients"].astype(np.float64)
        arrays["raw_coefficients"][0, 0, 0] += 1 + abs(arrays["raw_coefficients"][0, 0, 0])
        reason = "source raw coefficients: numeric mismatch"
    elif mode == "global_sign_with_unchanged_isc":
        arrays["isc_inputs"] = -arrays["isc_inputs"]
        # Global sign leaves pairwise and LOO ISC invariant, but not source data.
        try:
            m.source_fidelity(-actual["x"], actual["reference"]["isc_inputs"])
        except ValueError as exc:
            assert str(exc).startswith("source "), "unexpected non-fidelity failure"
        else:
            npz_write(root / "timecourses.npz", arrays)
            assert p.validate_output_directory(root, actual["reference"])
            record_property("control_status", "control_not_discriminating_within_public_source_precision")
            return
        reason = "source ISC input pointwise mismatch|source active .* centered fidelity mismatch"
    else:
        invented = np.broadcast_to(np.arange(168, dtype=float)[None, :, None] + 1000, (40, 168, 3)).copy()
        arrays["isc_inputs"] = invented
        support = m.support(invented)
        arrays.update({key: support[key] for key in ("person_active", "template_active")})
        write_derived(root, *p.expected_tables_and_results(invented, support, actual["reference"], actual["result"]["isc_estimator"]))
        npz_write(root / "reference.npz", {"invented_series": invented})
        reason = "source ISC input pointwise mismatch"
    npz_write(root / "timecourses.npz", arrays)
    with pytest.raises((ValueError, a.ArtifactError), match=reason):
        p.canonical_arrays(arrays, actual["reference"])
    with pytest.raises((ValueError, a.ArtifactError), match=reason):
        p.validate_output_directory(root, actual["reference"])
    record_property("control_status", "effective_source_numerical_rejection")


def test_actual_literal_id_not_digit_alias(actual, tmp_path):
    root = output_copy(actual, tmp_path)
    rows = copy.deepcopy(actual["artifacts"]["cohort.csv"])
    rows[0]["participant_id"] = rows[0]["participant_id"].removeprefix("sub-pixar")
    csv_write(root / "cohort.csv", rows)
    with pytest.raises(a.ArtifactError, match="cohort exact membership"):
        p.validate_output_directory(root, actual["reference"])


@pytest.mark.parametrize("mode", ["self_pair", "missing_pair", "duplicate_pair", "missing_person_region", "dropped_count"])
def test_actual_exact_families_and_denominators(actual, tmp_path, mode):
    root = output_copy(actual, tmp_path)
    pairs, people = copy.deepcopy((actual["pairs"], actual["people"]))
    if mode == "self_pair":
        pairs[0]["participant_b"] = pairs[0]["participant_a"]
    elif mode == "missing_pair":
        pairs.pop()
    elif mode == "duplicate_pair":
        pairs.append(copy.deepcopy(pairs[0]))
    elif mode == "missing_person_region":
        people.pop()
    else:
        people[0]["loo_n_expected"] = 38
    csv_write(root / "isc_pairs.csv", pairs)
    csv_write(root / "isc_per_subject.csv", people)
    with pytest.raises(a.ArtifactError, match="self pair|complete pair family|duplicate unordered pair|complete person-region family|integer mismatch"):
        p.validate_output_directory(root, actual["reference"])


@pytest.mark.parametrize("mode", ["source_hash", "source_file_hash", "header_clock", "failure_empty", "failure_dangling", "missing_artifact", "nonfinite"])
def test_actual_provenance_and_failure_states(actual, tmp_path, mode):
    root = output_copy(actual, tmp_path)
    if mode.startswith("failure"):
        if mode == "failure_empty":
            (root / "failure_report.json").write_text("")
        else:
            (root / "failure_report.json").symlink_to(root / "absent")
    elif mode == "missing_artifact":
        (root / "isc_pairs.csv").unlink()  # Disposable detached test copy only.
    elif mode == "nonfinite":
        arrays = copy.deepcopy(actual["artifacts"]["timecourses.npz"])
        arrays["isc_inputs"][0, 0, 0] = np.nan
        npz_write(root / "timecourses.npz", arrays)
    else:
        metadata = copy.deepcopy(actual["artifacts"]["run_metadata.json"])
        if mode == "source_hash":
            metadata["source_manifest_sha256"] = "0" * 64
        elif mode == "source_file_hash":
            metadata["source_files"][0]["sha256"] = "0" * 64
        else:
            metadata["source_observed"]["headers"][0]["raw_TR"] += 1
        json_write(root / "run_metadata.json", metadata)
    with pytest.raises((a.ArtifactError, ValueError)):
        p.validate_output_directory(root, actual["reference"])
