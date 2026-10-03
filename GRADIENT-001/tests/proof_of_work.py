"""Source-bound spectral certificates and accepted-coordinate report replay.

No historical bank or oracle imports. Valid repeated-block eigenbases and GPA
minimizers are accepted rather than requiring hidden reference coordinates.
"""
from __future__ import annotations

import copy
from decimal import Decimal
import numpy as np

import artifact_reader as a
import gradient_math as m
import gradient_reporting as r


def strings(values, name, ndim=1):
    a.require(isinstance(values, np.ndarray) and values.ndim == ndim and values.dtype.kind in "US", name + ": string axis")
    try: out = np.char.decode(values, "utf-8") if values.dtype.kind == "S" else values.astype(str)
    except UnicodeError as exc: raise a.ArtifactError(name + ": invalid text") from exc
    a.require(np.all(out != ""), name + ": empty ID")
    return out


def axis(values, expected, name, integer=False):
    a.require(isinstance(values, np.ndarray) and values.shape == (len(expected),), name + ": axis size")
    parsed = a.integer_array(values) if integer else strings(values, name)
    a.require(parsed.ndim == 1 and len(parsed) == len(expected), name + ": axis size")
    items = parsed.tolist()
    a.require(len(set(items)) == len(items) and set(items) == set(expected), name + ": exact unique membership")
    return np.asarray([items.index(x) for x in expected])


def numeric(actual, expected, name, atol=1e-6, rtol=1e-6):
    actual, expected = np.asarray(actual), np.asarray(expected)
    a.require(actual.shape == expected.shape and actual.dtype.kind in "iuf", name + ": numeric shape/type")
    a.require(not np.isinf(actual).any() and np.array_equal(np.isnan(actual), np.isnan(expected)), name + ": undefined mask")
    finite = np.isfinite(expected)
    a.require(np.isfinite(actual[finite]).all(), name + ": nonfinite")
    a.require(np.all(np.abs(actual[finite] - expected[finite]) <= atol + rtol * np.abs(expected[finite])), name + ": source/replay mismatch")


def boolean(actual, expected, name):
    actual = np.asarray(actual)
    a.require(actual.dtype.kind == "b" and np.array_equal(actual, expected), name + ": exact Boolean mask")


def canonical_arrays(submitted, reference):
    expected = reference["arrays"]
    method = reference["method"]
    people = expected["participant_ids"].tolist()
    groups = [x["id"] for x in method["configurations"]]
    embeddings = ["subject:" + x for x in people] + ["configuration:" + x for x in groups]
    quantities = groups + ["aligned_mean"]
    keys = set(reference["schema"]["gradient_arrays_npz"]["arrays"])
    a.require(keys <= set(submitted), "missing required NPZ array")
    dimensions = dict(person=axis(submitted["participant_ids"], people, "participant_ids"),
                      frame=axis(submitted["frame_indices"], expected["frame_indices"].tolist(), "frame_indices", True),
                      parcel=axis(submitted["parcel_ids"], expected["parcel_ids"].tolist(), "parcel_ids", True),
                      arm=axis(submitted["arm_ids"], ["nobp", "bp"], "arm_ids"),
                      config=axis(submitted["configuration_ids"], groups, "configuration_ids"),
                      embedding=axis(submitted["embedding_ids"], embeddings, "embedding_ids"),
                      quantity=axis(submitted["quantity_ids"], quantities, "quantity_ids"))
    layouts = dict(source_positions=("person",), configuration_membership=("config", "person"),
                   raw_means=("person", "frame", "parcel"), geometry_valid=("person", "parcel"),
                   raw_sample_sd=("person", "parcel"), activity_threshold=("person", "parcel"),
                   cleaned_series=("person", "arm", "frame", "parcel"),
                   clean_centered_l2=("person", "arm", "parcel"), person_parcel_active=("person", "arm", "parcel"),
                   fc=("person", "arm", "parcel", "parcel"), configuration_fc=("config", "parcel", "parcel"),
                   configuration_parcel_active=("config", "parcel"), operator_valid=("embedding",),
                   embedding_valid=("embedding",), principal_valid=("embedding",), retained_span_valid=("embedding",),
                   eigenvalues=("embedding", None), eigenvectors=("embedding", "parcel", None),
                   raw_diffusion=("embedding", "parcel", None), gpa_rotations=(None, "person", None, None),
                   gpa_reference_history=(None, "parcel", None), gpa_distances=(None,),
                   aligned_gradients=("person", "parcel", None), display_signs=("quantity", None),
                   display_coordinates=("quantity", "parcel", None), display_valid=("quantity", None))
    result = {}
    for key, layout in layouts.items():
        value = submitted[key]
        a.require(isinstance(value, np.ndarray) and value.ndim == len(layout), key + ": dimension count")
        for dimension, label in enumerate(layout):
            if label is not None:
                order = dimensions[label]
                a.require(value.shape[dimension] == len(order), key + ": axis length")
                value = np.take(value, order, axis=dimension)
        result[key] = value
    scalar = submitted["gpa_n_iterations"]
    a.require(isinstance(scalar, np.ndarray) and scalar.shape == (), "GPA scalar shape")
    result["gpa_n_iterations"] = a.integer_array(scalar).item()
    pairs = [(left, right) for i, left in enumerate(people) for right in people[i + 1:]]
    raw_pair_ids = submitted['pair_participant_ids']
    a.require(isinstance(raw_pair_ids, np.ndarray) and raw_pair_ids.shape == (len(pairs), 2), "complete pair axis")
    pair_ids = strings(raw_pair_ids, "pair IDs", 2)
    a.require(pair_ids.shape == (len(pairs), 2), "complete pair axis")
    supplied = [frozenset(row) for row in pair_ids.tolist()]
    a.require(all(len(row) == 2 for row in supplied) and len(set(supplied)) == len(pairs) and
              set(supplied) == {frozenset(row) for row in pairs}, "complete unique nonself pair identities")
    order = [supplied.index(frozenset(row)) for row in pairs]
    for key in ("signed_pair_consistency", "pair_consistency_valid"):
        a.require(submitted[key].shape == (len(pairs), 2), key + ": pair shape")
        result[key] = submitted[key][order]
    return result


def source_receipts(arrays, reference):
    expected = reference["arrays"]
    a.require(np.array_equal(a.integer_array(arrays["source_positions"]), expected["source_positions"]), "source order positions")
    for key in ("geometry_valid", "person_parcel_active", "configuration_membership", "configuration_parcel_active"):
        boolean(arrays[key], expected[key], key)
    numeric(arrays["raw_means"], expected["raw_means"], "raw_means", 1e-5, 1e-7)
    for key in ("cleaned_series", "raw_sample_sd", "clean_centered_l2", "activity_threshold"):
        numeric(arrays[key], expected[key], key)
        if key != "cleaned_series": a.require(np.all(arrays[key][np.isfinite(arrays[key])] >= 0), key + ": nonnegative domain")
    for key in ("fc", "configuration_fc"): numeric(arrays[key], expected[key], key, 1e-8, 1e-7)


def certified_coordinates(arrays, reference):
    bases = reference["source_bases"]
    n, p = len(reference["arrays"]["participant_ids"]), len(reference["arrays"]["parcel_ids"])
    k = reference["method"]["diffusion"]["n_components"]
    e = len(bases)
    for key, shape in (("eigenvalues", (e, k + 1)), ("eigenvectors", (e, p, k)), ("raw_diffusion", (e, p, k))):
        a.require(arrays[key].shape == shape, key + ": fixed shape")
    gradients = []
    for index, basis in enumerate(bases):
        if basis is None:
            for key in ("eigenvalues", "eigenvectors", "raw_diffusion"):
                numeric(arrays[key][index], np.full_like(arrays[key][index], np.nan, dtype=float), key + ": unavailable source")
            gradients.append(None)
        else:
            lambdas = arrays["eigenvalues"][index]
            a.require(np.all(np.abs(lambdas) <= 1 + m.EIGEN_ATOL), "eigenvalue natural domain")
            saved = arrays["raw_diffusion"][index] if basis["multiscale_defined"] else None
            if saved is None: numeric(arrays["raw_diffusion"][index], np.full((p, k), np.nan), "undefined diffusion")
            gradients.append(m.validate_spectrum(arrays["eigenvectors"][index], lambdas, saved, basis))
    statuses = [r.embedding_status(basis, g) for basis, g in zip(bases, gradients)]
    boolean(arrays["operator_valid"], [b is not None for b in bases], "operator_valid")
    boolean(arrays["embedding_valid"], [g is not None for g in gradients], "embedding_valid")
    boolean(arrays["principal_valid"], [x[1] == "ok" for x in statuses], "principal_valid")
    boolean(arrays["retained_span_valid"], [x[2] == "ok" for x in statuses], "retained_span_valid")
    gpa_available = all(b is not None and b["gpa_eligible"] for b in bases[:n + 1])
    if gpa_available:
        gpa = m.validate_gpa_history(np.stack(gradients[:n]), gradients[n], arrays["gpa_rotations"],
                                     arrays["gpa_reference_history"], arrays["gpa_distances"],
                                     arrays["gpa_n_iterations"], arrays["aligned_gradients"])
    else:
        a.require(arrays["gpa_n_iterations"] == 0, "undefined GPA iteration count")
        for key, shape in (("gpa_rotations", (0, n, k, k)), ("gpa_reference_history", (0, p, k)), ("gpa_distances", (0,))):
            a.require(arrays[key].shape == shape and arrays[key].dtype.kind in "iuf", key + ": undefined shape")
        numeric(arrays["aligned_gradients"], np.full((n, p, k), np.nan), "undefined aligned gradients")
        gpa = None
    return gradients, gpa


def match(actual, expected, name, *, csv=False, atol=1e-6, rtol=1e-6):
    if expected is None:
        a.require(actual == "" if csv else actual is None, name + ": null required")
    elif isinstance(expected, (bool, np.bool_)):
        value = a.csv_boolean(actual) if csv else actual
        a.require(type(value) is bool and value == expected, name + ": Boolean mismatch")
    elif isinstance(expected, (int, np.integer)):
        a.require(a.integer(actual, json_number=not csv) == expected, name + ": integer mismatch")
    elif isinstance(expected, (float, np.floating, Decimal)):
        value = a.real(actual, json_number=not csv)
        a.require(abs(value - float(expected)) <= atol + rtol * abs(float(expected)), name + ": numeric mismatch")
        if any(token in name for token in ("between_within", "_gap")): a.require(value >= 0, name + ": nonnegative domain")
        if name.endswith(("unaligned_signed", "aligned_signed", ".value")):
            a.require(abs(value) <= 1 + 2e-6, name + ": correlation domain")
    elif isinstance(expected, str):
        a.require(isinstance(actual, str) and actual == expected, name + ": literal mismatch")
    elif isinstance(expected, dict):
        a.require(isinstance(actual, dict) and set(expected) <= set(actual), name + ": required object fields")
        for key, value in expected.items(): match(actual[key], value, name + "." + key, csv=csv, atol=atol, rtol=rtol)
    elif isinstance(expected, (list, tuple)):
        a.require(isinstance(actual, list) and len(actual) == len(expected), name + ": list support")
        for index, (left, right) in enumerate(zip(actual, expected)): match(left, right, name + f"[{index}]", atol=atol, rtol=rtol)
    else: raise a.ArtifactError(name + ": unexpected internal expected type")


def table(actual, expected, keys, name, integer_keys=(), tolerance=(1e-6, 1e-6)):
    have = a.keyed_rows(actual, keys, integer_columns=integer_keys)
    want = {tuple(row[key] for key in keys): row for row in expected}
    a.require(set(have) == set(want), name + ": exact keyed membership")
    for key, row in want.items(): match(have[key], row, name, csv=True, atol=tolerance[0], rtol=tolerance[1])


def keyed_list(actual, expected, key, name):
    a.require(isinstance(actual, list) and all(isinstance(row, dict) and key in row for row in actual), name + ": keyed list")
    keys = [a.integer(row[key], json_number=True) if isinstance(expected[0][key], int) else row[key] for row in actual]
    a.require(len(keys) == len(set(keys)) and set(keys) == {row[key] for row in expected}, name + ": exact keyed membership")
    return [actual[keys.index(row[key])] for row in expected]


def metadata(actual, reference):
    expected = reference["metadata"]
    actual = copy.deepcopy(actual)
    a.require(isinstance(actual, dict), "metadata object")
    actual["source_files"] = keyed_list(actual.get("source_files"), expected["source_files"], "path", "source_files")
    observed = actual.get("source_observed")
    want = expected["source_observed"]
    a.require(isinstance(observed, dict), "source_observed object")
    observed["atlas_labels"] = keyed_list(observed.get("atlas_labels"), want["atlas_labels"], "parcel_id", "atlas labels")
    supplied = observed.get("participant_ids")
    a.require(isinstance(supplied, list) and len(supplied) == len(set(supplied)) and set(supplied) == set(want["participant_ids"]), "metadata participant membership")
    observed["participant_ids"] = want["participant_ids"]
    for name in ("headers", "confound_column_names", "voxel_support_by_subject", "raw_clock_metadata"):
        a.require(isinstance(observed.get(name), dict) and set(observed[name]) == set(want[name]), "metadata exact participant map: " + name)
    for person in want["voxel_support_by_subject"]:
        observed["voxel_support_by_subject"][person] = keyed_list(observed["voxel_support_by_subject"][person], want["voxel_support_by_subject"][person], "parcel_id", "voxel support")
    for got, target in [(observed.get("atlas_header"), want["atlas_header"])] + [(observed["headers"][person], want["headers"][person]) for person in want["headers"]]:
        a.require(isinstance(got, dict) and isinstance(got.get("source_dtype"), str), "source dtype receipt")
        try: dtype = np.dtype(got["source_dtype"])
        except TypeError as exc: raise a.ArtifactError("source dtype receipt") from exc
        a.require(dtype == np.dtype(target["source_dtype"]), "source dtype mismatch")
        got["source_dtype"] = target["source_dtype"]
    a.require(isinstance(observed.get("frame_alignment"), str) and observed["frame_alignment"].strip(), "clock description required")
    observed["frame_alignment"] = want["frame_alignment"]
    filtered = {key: value for key, value in expected.items() if key != "software_versions"}
    match(actual, filtered, "metadata", atol=1e-9, rtol=1e-9)
    versions = actual.get("software_versions")
    a.require(isinstance(versions, dict) and set(expected["software_versions"]) <= set(versions) and
              all(isinstance(versions[key], str) and versions[key].strip() for key in expected["software_versions"]), "actual software strings required")
    a.require(isinstance(actual.get("warnings"), list), "warnings list required")
    amendment = actual.get("numerical_method_amendments")
    a.require(isinstance(amendment, str) and amendment.strip(), "method amendment description required")


def validate(output_dir, reference):
    a.require(reference.get("pilot") is False and reference.get("source_bases") is not None, "full source reconstruction required")
    a.require(reference["arrays"]["participant_ids"].shape == (20,) and reference["arrays"]["parcel_ids"].shape == (400,), "fixed full20/400 source")
    submitted = a.read_artifacts(output_dir)
    arrays = canonical_arrays(submitted["gradient_arrays.npz"], reference)
    source_receipts(arrays, reference)
    gradients, gpa = certified_coordinates(arrays, reference)
    derived = r.derive(reference, gradients, gpa)
    for key, expected in derived["arrays"].items():
        if key in ("quantity_ids", "pair_participant_ids"): continue
        if expected.dtype.kind == "b": boolean(arrays[key], expected, key)
        elif key == "display_signs": a.require(np.array_equal(a.integer_array(arrays[key]), expected), "display signs")
        else: numeric(arrays[key], expected, key)
    table(submitted["cohort.csv"], reference["cohort"], ("participant_id",), "cohort", tolerance=(1e-9, 1e-9))
    table(submitted["parcels.csv"], reference["parcels"], ("participant_id", "parcel_id"), "parcels", ("parcel_id",), (1e-9, 1e-9))
    table(submitted["configurations.csv"], derived["configurations"], ("quantity", "network"), "configurations")
    table(submitted["per_subject.csv"], derived["per_subject"], ("participant_id",), "per_subject")
    results = copy.deepcopy(submitted["results.json"])
    wanted = derived["results"]
    results["configuration_summaries"] = keyed_list(results.get("configuration_summaries"), wanted["configuration_summaries"], "config", "configuration summaries")
    for got, target in zip(results["configuration_summaries"], wanted["configuration_summaries"]):
        subjects = got.get("subject_ids")
        a.require(isinstance(subjects, list) and len(subjects) == len(set(subjects)) and set(subjects) == set(target["subject_ids"]), "configuration source membership")
        got["subject_ids"] = target["subject_ids"]
    match(results, wanted, "results")
    a.require(isinstance(results.get("claim_scope"), str) and results["claim_scope"].strip(), "nonempty claim scope description")
    metadata(submitted["run_metadata.json"], reference)
    a.check_inventory(output_dir)
    return dict(status="accepted", n_subjects=20, n_parcels=400, n_configurations=4,
                n_operator_valid=int(np.sum(arrays["operator_valid"])), gpa_defined=gpa is not None)


validate_output_directory = validate
