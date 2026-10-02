"""AUTHORING ONLY: gated QA of known genuine artifacts, excluded from scoring.

No source/output access on import. No participant is required to preserve
acceptance after these perturbations, rounding changes or extra artifacts.
The source-once fixture is shared with the production case when both are run.
"""
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil

import numpy as np
import pytest

import artifact_reader as a
import proof_of_work as p
import spin_math as m


def fingerprint(root):
    return {name: hashlib.sha256(a.read_bytes(root/name, 64*2**20)).hexdigest() for name in a.REQUIRED}


def read_json(root, name):
    # Data has already passed the bounded reader and full validator in genuine.
    return json.loads(a.read_bytes(root/name, a.CAPS["json"]))


def write_json(path, value):
    path.write_text(json.dumps(value, allow_nan=False, indent=2)+"\n", encoding="utf-8")


def read_rows(root):
    return a.parse_csv(a.read_bytes(root/"parcels.csv", a.CAPS["csv"]))


def write_rows(root, rows):
    with (root/"parcels.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def arrays(root):
    return a.parse_npz(a.read_bytes(root/"spin_evidence.npz", a.CAPS["npz"]))


def canonical_mapping(root, ref):
    z = arrays(root)
    po = p.axis(z["parcel_ids"], ref["parcel_ids"].tolist(), "parcel")
    ro = p.axis(z["rotation_ids"], list(range(len(z["rotation_ids"]))), "rotation")
    return m.integers(z["spin_parcel_ids"], 2)[np.ix_(po, ro)]


@pytest.fixture(scope="session")
def genuine(original_reference):
    path = os.environ.get("REPAIR_ORACLE_OUTPUT")
    assert path, "Explicit REPAIR_ORACLE_OUTPUT required for authoring QA; never silently skip."
    root = a.guarded_path(path, directory=True)
    before = fingerprint(root)
    assert p.validate_output_directory(root, original_reference)["status"] == "accepted"
    baseline = dict(mapping=canonical_mapping(root, original_reference), results=read_json(root, "results.json"))
    yield root, original_reference, baseline
    assert fingerprint(root) == before, "Original artifacts changed during authoring QA."


@pytest.fixture
def candidate(tmp_path, genuine):
    root, ref, baseline = genuine
    owned = tmp_path/"detached-candidate"
    owned.mkdir()
    for name in a.REQUIRED:
        shutil.copyfile(root/name, owned/name)
        new, old = (owned/name).stat(), (root/name).stat()
        assert (new.st_dev, new.st_ino) != (old.st_dev, old.st_ino)
    try:
        yield owned, ref, baseline
    finally:
        # Only this fixture's exact fresh directory; not the root or originals.
        shutil.rmtree(owned)


def results_for_maps(root, ref, mapping, declaration):
    derived = m.replay(p.parcels(read_rows(root), ref), ref["maps"], ref["parcel_ids"], mapping)
    return p.expected_results(derived, declaration["spin_method"], declaration["seed"], declaration["n_permutations"])


@pytest.mark.parametrize("mode", ["baseline", "coherent_axes", "rounded_scalars", "metadata_records",
                                  "dtype_aliases", "harmless_extras", "sourceclose_own_replay"])
def test_authoring_equivalent_positive(candidate, mode, record_property):
    root, ref, baseline = candidate
    if mode == "coherent_axes":
        z = arrays(root); po = np.arange(399, -1, -1); ro = np.arange(len(z["rotation_ids"])-1, -1, -1)
        for key in ("parcel_ids", "hemisphere", "centroids"): z[key] = z[key][po]
        z["parcel_ids"] = z["parcel_ids"].astype(float)
        z["rotation_ids"] = z["rotation_ids"][ro].astype(float)
        z["spin_parcel_ids"] = z["spin_parcel_ids"][np.ix_(po, ro)]
        np.savez_compressed(root/"spin_evidence.npz", **z)
        write_rows(root, [{key: row[key] for key in reversed(row)} for row in read_rows(root)[::-1]])
        result = read_json(root, "results.json"); result["null_distribution"].reverse()
        write_json(root/"results.json", result)
    elif mode == "rounded_scalars":
        result = read_json(root, "results.json")
        for key in ("pearson_r", "p_spin"):
            if result[key] is not None: result[key] = round(result[key], 6)
        for row in result["null_distribution"]:
            if row["r"] is not None: row["r"] = round(row["r"], 6)
        write_json(root/"results.json", result)
    elif mode in ("metadata_records", "dtype_aliases"):
        metadata = read_json(root, "run_metadata.json")
        if mode == "metadata_records":
            metadata["source_files"].reverse(); metadata["analysis_observed"]["map_support"].reverse()
        else:
            for role in p.GIFTI_ROLES:
                for row in metadata["source_observed"][role]["arrays"]:
                    dtype = np.dtype(row["dtype"])
                    row["dtype"] = dtype.name if dtype.isnative else dtype.str
        write_json(root/"run_metadata.json", metadata)
    elif mode == "harmless_extras":
        z = arrays(root); z["optional_diagnostic"] = np.zeros((1,)*8)
        np.savez_compressed(root/"spin_evidence.npz", **z)
        (root/"findings.md").write_text("Descriptive signed association; any correct inference is permitted.\n")
        result = read_json(root, "results.json"); result["optional_note"] = "No required outcome."
        write_json(root/"results.json", result)
    elif mode == "sourceclose_own_replay":
        rows = read_rows(root)
        canonical = {int(pid): ref["maps"][i] for i, pid in enumerate(ref["parcel_ids"])}
        for row in rows:
            values = canonical[a.integer(row["parcel_id"])]*(1+1e-9)
            row.update(gradient2=repr(float(values[0])), thickness=repr(float(values[1])))
        write_rows(root, rows)
        write_json(root/"results.json", results_for_maps(root, ref, baseline["mapping"], baseline["results"]))
    assert p.validate_output_directory(root, ref)["status"] == "accepted"
    record_property("qa_classification", "equivalent_positive")


@pytest.mark.parametrize("mode", ["wrong_geometry", "hemisphere_shift", "wrong_mapping", "wrong_seed",
    "drop_parcel", "drop_rotation", "drop_null_record", "numeric_alias", "source_pin", "support_digest", "late_failure"])
def test_authoring_binding_mutation(candidate, mode, record_property):
    root, ref, baseline = candidate
    if mode in ("wrong_geometry", "hemisphere_shift", "wrong_mapping", "drop_rotation"):
        z = arrays(root)
        if mode == "wrong_geometry":
            before = float(z["centroids"][0, 0]); z["centroids"][0, 0] += 1.
            assert abs(float(z["centroids"][0, 0])-before) > m.GEOMETRY_ATOL+m.GEOMETRY_RTOL*abs(before)
        elif mode == "hemisphere_shift": z["hemisphere"] = 1-z["hemisphere"]
        elif mode == "wrong_mapping":
            first = int(z["spin_parcel_ids"][0, 0])
            replacement = next(int(pid) for pid in ref["parcel_ids"] if int(pid) != first)
            z["spin_parcel_ids"][0, 0] = replacement
        else:
            z["rotation_ids"] = z["rotation_ids"][:-1]; z["spin_parcel_ids"] = z["spin_parcel_ids"][:, :-1]
        np.savez_compressed(root/"spin_evidence.npz", **z)
        with pytest.raises(ValueError): p.spin_receipts(z, ref, baseline["results"]["n_permutations"], baseline["mapping"])
    elif mode == "drop_null_record":
        result = read_json(root, "results.json"); result["null_distribution"].pop()
        write_json(root/"results.json", result)
    elif mode == "wrong_seed":
        result = read_json(root, "results.json"); result["seed"] = (result["seed"]+1) % 2**32
        changed, _ = m.construct(ref["centroids"], ref["hemisphere"], ref["parcel_ids"], result["spin_method"], result["seed"], result["n_permutations"])
        if np.array_equal(changed, baseline["mapping"]):
            record_property("qa_classification", "not_discriminating")
            record_property("qa_reason", "Different seed has exactly the same complete canonical mapping.")
            return
        write_json(root/"results.json", result)
    elif mode in ("drop_parcel", "numeric_alias", "support_digest"):
        rows = read_rows(root)
        if mode == "drop_parcel": rows.pop()
        elif mode == "numeric_alias": rows[0]["parcel_id"] = "parcel_"+rows[0]["parcel_id"]
        else: rows[0]["support_sha256"] = "0"*64 if rows[0]["support_sha256"] != "0"*64 else "1"*64
        write_rows(root, rows)
    elif mode == "source_pin":
        metadata = read_json(root, "run_metadata.json")
        metadata["source_manifest_sha256"] = "0"*64 if metadata["source_manifest_sha256"] != "0"*64 else "1"*64
        write_json(root/"run_metadata.json", metadata)
    else: (root/"failure_report.json").symlink_to(root/"absent")
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)
    record_property("qa_classification", "effective_binding_rejection")


@pytest.mark.parametrize("mode", ["affine_offset", "sign_flip"])
def test_authoring_signed_map_mutation(candidate, mode, record_property):
    root, ref, baseline = candidate
    own = p.parcels(read_rows(root), ref)
    changed = own.copy()
    changed[:, 0] = own[:, 0]+1 if mode == "affine_offset" else -own[:, 0]
    gaps = np.abs(changed-ref["maps"])
    effective = bool(np.any(gaps > m.MAP_ATOL+m.MAP_RTOL*np.abs(ref["maps"])))
    if not effective:
        record_property("qa_classification", "not_discriminating")
        record_property("qa_reason", "Requested map transformation does not violate the public pointwise envelope.")
        return
    rows = read_rows(root)
    values = {int(pid): changed[i, 0] for i, pid in enumerate(ref["parcel_ids"])}
    for row in rows: row["gradient2"] = repr(float(values[a.integer(row["parcel_id"])]))
    write_rows(root, rows)
    with pytest.raises(ValueError, match="signed pointwise"):
        m.map_fidelity(changed, ref["maps"], ref["parcel_ids"], baseline["mapping"])
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)
    record_property("qa_classification", "effective_signed_source_rejection")
    record_property("max_pointwise_gap", float(np.max(gaps)))


def scalar_candidate(original, mode):
    """Deliberately wrong numerical receipts only, unchanged maps and geometry."""
    changed = copy.deepcopy(original)
    if mode == "gaussian_null":
        if original["inference_status"] != "ok": return None, "complete null support unavailable"
        rng = np.random.RandomState(193)
        for row in changed["null_distribution"]: row["r"] = float(np.clip(rng.normal(0, .1), -1, 1))
    elif mode == "absolute_signed_r":
        if changed["pearson_r"] is not None: changed["pearson_r"] = abs(changed["pearson_r"])
        for row in changed["null_distribution"]:
            if row["r"] is not None: row["r"] = abs(row["r"])
    elif mode == "fabricated_null_support":
        row = changed["null_distribution"][0]
        if row["status"] == "ok": row.update(status="inactive_gradient", r=None)
        else: row.update(status="ok", r=0.)
        changed.update(m.summarize(changed["observed_status"], changed["pearson_r"], changed["null_distribution"]))
    elif mode in ("strict_greater_count", "rounded_rank", "no_plus_one", "wrong_count"):
        if original["inference_status"] != "ok": return None, "complete inference unavailable"
    else: raise ValueError("unknown authoring component")
    if changed["inference_status"] == "ok":
        observed = changed["pearson_r"]
        values = [row["r"] for row in changed["null_distribution"]]
        if mode == "strict_greater_count": count = sum(abs(value) > abs(observed) for value in values)
        elif mode == "rounded_rank": count = sum(abs(round(value, 6)) >= abs(round(observed, 6)) for value in values)
        else: count = sum(abs(value) >= abs(observed) for value in values)
        if mode == "wrong_count": count = (count+1) % (len(values)+1)
        denominator = len(values) if mode == "no_plus_one" else len(values)+1
        numerator = count if mode == "no_plus_one" else count+1
        changed.update(n_exceedances=count, p_spin_numerator=numerator, p_spin_denominator=denominator,
                       p_spin=numerator/denominator, significant_after_spatial_null=20*numerator < denominator)
    return changed, None


def observable_differences(expected, changed, path=""):
    result = []
    if isinstance(expected, dict):
        for key in expected: result.extend(observable_differences(expected[key], changed[key], path+"/"+key))
    elif isinstance(expected, list):
        assert len(expected) == len(changed)
        for i, value in enumerate(expected): result.extend(observable_differences(value, changed[i], path+f"/{i}"))
    elif expected is None or changed is None:
        if expected is not changed: result.append(dict(path=path, kind="support", gap=None))
    elif type(expected) in (bool, int, str):
        if type(expected) is not type(changed) or expected != changed: result.append(dict(path=path, kind="exact", gap=None))
    elif abs(expected-changed) > m.SCALAR_ATOL:
        result.append(dict(path=path, kind="numeric", gap=abs(expected-changed)))
    return result


@pytest.mark.parametrize("mode", ["gaussian_null", "absolute_signed_r", "strict_greater_count", "rounded_rank",
                                  "no_plus_one", "wrong_count", "fabricated_null_support"])
def test_authoring_numerical_component(candidate, mode, record_property):
    root, ref, baseline = candidate
    expected = results_for_maps(root, ref, baseline["mapping"], baseline["results"])
    changed, unavailable = scalar_candidate(expected, mode)
    if changed is None:
        record_property("qa_classification", "control_not_constructed")
        record_property("qa_reason", unavailable)
        return
    gaps = observable_differences(expected, changed)
    if not gaps:
        p.validate_results(changed, expected)
        record_property("qa_classification", "not_discriminating")
        record_property("qa_reason", "Actual control receipts remain within public numeric/exact acceptance.")
        return
    before = {name: hashlib.sha256(a.read_bytes(root/name, 64*2**20)).hexdigest()
              for name in ("parcels.csv", "spin_evidence.npz", "run_metadata.json")}
    write_json(root/"results.json", changed)
    with pytest.raises(ValueError): p.validate_results(changed, expected)
    with pytest.raises(ValueError): p.validate_output_directory(root, ref)
    assert before == {name: hashlib.sha256(a.read_bytes(root/name, 64*2**20)).hexdigest() for name in before}
    record_property("qa_classification", "effective_numerical_rejection")
    record_property("observable_changes", json.dumps(gaps[:20], sort_keys=True))
