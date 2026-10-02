"""External MAPREL source-basis proof: accepted maps are the sole r/p authority.

No original readers, oracle imports, bank or hidden outcome target. Construction
receives only private canonical geometry. Authoring transformations are not part
of this acceptance function.
"""
from __future__ import annotations

from copy import deepcopy
import os
from pathlib import Path

import numpy as np

import artifact_reader as a
import spin_math as m

PARCEL_FIELDS = ("parcel_id", "label", "network", "hemisphere", "n_vertices",
                 "support_sha256", "gradient2", "thickness")
SOURCE_FIELDS = ("path", "role", "size_bytes", "sha256")
PINS = ("source_manifest_sha256", "method_contract_sha256", "output_schema_sha256")
GIFTI_ROLES = ("gradient_l", "gradient_r", "thickness_l", "thickness_r", "sphere_l", "sphere_r")


def match(actual, expected, name, *, atol=1e-6, rtol=0., csv=False):
    if isinstance(expected, dict):
        a.require(isinstance(actual, dict) and set(expected) <= set(actual), name+": required fields")
        for key, value in expected.items(): match(actual[key], value, name+"."+key, atol=atol, rtol=rtol, csv=csv)
    elif isinstance(expected, (list, tuple, np.ndarray)):
        a.require(isinstance(actual, list) and len(actual) == len(expected), name+": list shape")
        for i, value in enumerate(expected): match(actual[i], value, name+f"[{i}]", atol=atol, rtol=rtol, csv=csv)
    elif expected is None:
        a.require(actual is None, name+": explicit null")
    elif isinstance(expected, (bool, np.bool_)):
        a.require(type(actual) is bool and actual == bool(expected), name+": Boolean exact")
    elif isinstance(expected, (int, np.integer)):
        a.require(a.integer(actual, json_number=not csv) == int(expected), name+": integer exact")
    elif isinstance(expected, str):
        a.require(type(actual) is str and actual == expected, name+": literal exact")
    else:
        value = a.real(actual, json_number=not csv)
        a.require(abs(value-float(expected)) <= atol+rtol*abs(float(expected)), name+": numerical receipt")


def axis(value, expected, name):
    value = m.integers(value, 1).tolist()
    a.require(len(value) == len(expected) and len(set(value)) == len(value)
              and set(value) == set(expected), name+": exact unique keys")
    index = {key: i for i, key in enumerate(value)}
    return np.asarray([index[key] for key in expected], dtype=np.int64)


def keyed_json(rows, key, *, integer=False):
    a.require(isinstance(rows, list), "keyed JSON records")
    result = {}
    for row in rows:
        a.require(isinstance(row, dict) and key in row, "record key")
        identity = a.integer(row[key], json_number=True) if integer else row[key]
        a.require((integer or type(identity) is str and identity) and identity not in result, "unique typed record key")
        result[identity] = row
    return result


def require_reference(reference):
    a.require(isinstance(reference, dict), "private source reference required")
    ids = m.integers(reference["parcel_ids"], 1)
    a.require(np.array_equal(ids, np.arange(1, 401)), "all400 canonical literal parcel IDs")
    hemi = m.integers(reference["hemisphere"], 1)
    a.require(hemi.shape == (400,) and set(hemi.tolist()) == {0, 1}, "canonical hemispheres")
    a.require(m.array(reference["maps"], 2).shape == (400, 2), "source two-map shape")
    a.require(m.array(reference["centroids"], 2).shape == (400, 3), "source centroid shape")
    for field in ("labels", "networks", "support_n", "support_sha256"):
        a.require(len(reference[field]) == 400, "complete source parcel facts")
    a.require(np.all(m.integers(reference["support_n"], 1) > 0), "nonempty canonical supports")
    a.require(set(PINS) <= set(reference["pins"]), "all private identity pins")


def parcels(rows, reference):
    have = a.keyed_rows(rows, ["parcel_id"], integer_columns=["parcel_id"])
    a.require(set(have) == {(i,) for i in range(1, 401)}, "complete parcel rows")
    own = np.empty((400, 2), dtype=np.float64)
    for i, pid in enumerate(reference["parcel_ids"]):
        row = have[(int(pid),)]
        a.require(set(PARCEL_FIELDS) <= set(row), "required parcel columns")
        want = dict(parcel_id=int(pid), label=str(reference["labels"][i]), network=str(reference["networks"][i]),
                    hemisphere="L" if reference["hemisphere"][i] == 0 else "R",
                    n_vertices=int(reference["support_n"][i]), support_sha256=str(reference["support_sha256"][i]))
        match(row, want, "source parcel", csv=True)
        own[i] = [a.real(row["gradient2"]), a.real(row["thickness"])]
    return own


def spin_receipts(submitted, reference, count, expected_mapping):
    required = {"parcel_ids", "rotation_ids", "centroids", "hemisphere", "spin_parcel_ids"}
    a.require(isinstance(submitted, dict) and required <= set(submitted), "required spin arrays")
    po = axis(submitted["parcel_ids"], reference["parcel_ids"].tolist(), "parcel axis")
    ro = axis(submitted["rotation_ids"], list(range(count)), "rotation axis")
    xyz, hemi = m.array(submitted["centroids"], 2), m.integers(submitted["hemisphere"], 1)
    a.require(xyz.shape == (400, 3) and hemi.shape == (400,), "geometry receipt shapes")
    xyz = xyz[po]
    a.require(np.all(np.abs(xyz-reference["centroids"]) <= m.GEOMETRY_ATOL+m.GEOMETRY_RTOL*np.abs(reference["centroids"])),
              "source geometry fidelity")
    a.require(np.array_equal(hemi[po], reference["hemisphere"]), "source hemisphere identity")
    mapped = m.integers(submitted["spin_parcel_ids"], 2)
    a.require(mapped.shape == (400, count), "complete spin assignment shape")
    mapped = mapped[np.ix_(po, ro)]
    a.require(np.array_equal(mapped, expected_mapping), "canonical method/seed/count assignments")
    return mapped


def metadata_expected(reference, mapped):
    raw = reference["maps"]
    positions = m.mapping_rows(reference["parcel_ids"], mapped)
    return dict(schema_version="maprel-metadata-v2", task_id="MAPREL-001", status="ok", **reference["pins"],
                source_files=[{k: row[k] for k in SOURCE_FIELDS} for row in reference["source_files"]],
                source_observed=reference["source_observed"],
                analysis_observed=dict(map_support=[dict(map_id=key, active=m.active(raw[:, i]))
                                                   for i, key in enumerate(("gradient2", "thickness"))],
                                       remapped_gradient=dict(n_expected=mapped.shape[1],
                                                              n_active=sum(m.active(raw[idx, 0]) for idx in positions.T))))


def source_metadata(actual, expected):
    """Dtype aliases only at declared GIFTI array dtype fields, not free metadata."""
    a.require(isinstance(actual, dict), "source observed record")
    normalized = deepcopy(actual)
    for role in GIFTI_ROLES:
        if role not in expected: continue
        want = expected[role]["arrays"]
        a.require(role in normalized and isinstance(normalized[role], dict), "source GIFTI role")
        have = normalized[role].get("arrays")
        a.require(isinstance(have, list) and len(have) == len(want), "source GIFTI arrays")
        for submitted, canonical in zip(have, want):
            a.require(isinstance(submitted, dict) and type(submitted.get("dtype")) is str, "source dtype string")
            try:
                dtype, target = np.dtype(submitted["dtype"]), np.dtype(canonical["dtype"])
            except (TypeError, ValueError) as exc:
                raise a.ArtifactError("invalid source dtype") from exc
            a.require(dtype.fields is None and dtype.subdtype is None and dtype.kind in "iuf"
                      and dtype == target, "semantic source dtype")
            submitted["dtype"] = canonical["dtype"]
    match(normalized, expected, "source observed", atol=1e-9, rtol=1e-9)


def validate_metadata(actual, reference, mapped):
    expected = metadata_expected(reference, mapped)
    a.finite_json(actual)
    for key in ("schema_version", "task_id", "status", *PINS):
        a.require(key in actual, "metadata identity fields")
        match(actual[key], expected[key], key)
    have_files, want_files = keyed_json(actual.get("source_files"), "path"), keyed_json(expected["source_files"], "path")
    a.require(set(have_files) == set(want_files), "closed source file identities")
    for key in want_files: match(have_files[key], want_files[key], "source file")
    source_metadata(actual.get("source_observed"), expected["source_observed"])
    have_analysis = actual.get("analysis_observed")
    a.require(isinstance(have_analysis, dict), "analysis observed record")
    have_maps = keyed_json(have_analysis.get("map_support"), "map_id")
    want_maps = keyed_json(expected["analysis_observed"]["map_support"], "map_id")
    a.require(set(have_maps) == set(want_maps), "both canonical map supports")
    for key in want_maps: match(have_maps[key], want_maps[key], "canonical activity")
    match(have_analysis.get("remapped_gradient"), expected["analysis_observed"]["remapped_gradient"], "remap support")
    software, warnings = actual.get("software_versions"), actual.get("warnings")
    a.require(isinstance(software, dict) and software and all(type(k) is str and k and type(v) is str and v.strip()
              for k, v in software.items()), "actual descriptive software record")
    a.require(isinstance(warnings, list) and all(type(v) is str for v in warnings), "warning string list")


def expected_results(derived, method, seed, count):
    return dict(schema_version="maprel-results-v2", status="complete", n_parcels=400,
                null_family="centroid_spin", spin_method=method, seed=seed, n_permutations=count, **derived)


def validate_results(actual, expected):
    a.finite_json(actual)
    a.require(isinstance(actual, dict) and set(expected) <= set(actual), "required result fields")
    for key, value in expected.items():
        if key != "null_distribution": match(actual[key], value, key, atol=m.SCALAR_ATOL)
    have = keyed_json(actual["null_distribution"], "rotation_id", integer=True)
    want = keyed_json(expected["null_distribution"], "rotation_id", integer=True)
    a.require(set(have) == set(want), "all rotation records retained")
    for key in want: match(have[key], want[key], "own null replay", atol=m.SCALAR_ATOL)
    for value in [actual["pearson_r"], *(row["r"] for row in have.values())]:
        if value is not None: a.require(-1 <= a.real(value, json_number=True) <= 1, "signed correlation domain")
    if actual["p_spin"] is not None: a.require(0 <= a.real(actual["p_spin"], json_number=True) <= 1, "p domain")


def validate_output_directory(output_dir, reference):
    require_reference(reference)
    artifacts = a.read_artifacts(output_dir)
    result = artifacts["results.json"]
    a.require(isinstance(result, dict), "result object")
    method, seed, count = m.declaration(result.get("spin_method"), result.get("seed"), result.get("n_permutations"))
    mapping, _ = m.construct(reference["centroids"], reference["hemisphere"], reference["parcel_ids"], method, seed, count)
    mapped = spin_receipts(artifacts["spin_evidence.npz"], reference, count, mapping)
    own = parcels(artifacts["parcels.csv"], reference)
    derived = m.replay(own, reference["maps"], reference["parcel_ids"], mapped)
    validate_results(result, expected_results(derived, method, seed, count))
    validate_metadata(artifacts["run_metadata.json"], reference, mapped)
    a.require(not os.path.lexists(Path(output_dir)/a.FAILURE), "authoritative failure_report.json appeared during validation")
    return dict(status="accepted", n_parcels=400, n_permutations=count,
                inference_status=derived["inference_status"], source_bound=True)
