"""Same-original N063 qualification; never a reduced-cohort benchmark.

Dependencies are the independently qualified range reader and the unchanged
original native/algorithm/custody modules. No native imports or reads on import.
"""
from bisect import bisect_left
import hashlib
from types import SimpleNamespace


class QualificationError(ValueError):
    pass


PROFILE_INTS = (
    "metadata_artifact_bytes", "projection_artifact_bytes", "comparison_artifact_bytes",
    "max_presentation_tables", "max_fixed_metadata_bytes", "max_numeric_chunk_bytes",
    "max_dff_slice_bytes", "max_supported_omissions",
)


def validate_profile(profile):
    for name in PROFILE_INTS:
        if type(profile.get(name)) is not int or profile[name] <= 0:
            raise QualificationError("positive finite qualification limit required: " + name)


def digest(value, deps):
    return hashlib.sha256(deps.io.canonical(value)).hexdigest()


def write(store, name, value, cap, deps):
    body = deps.io.canonical(value)
    if len(body) > cap:
        raise QualificationError("complete qualification artifact exceeds limit: " + name)
    ref = store.write(name + ".json", body, role="original_qualification_" + name,
                      visibility="operator", producer="neural063-original-qualification-v1").object()
    if not hasattr(store, "qualification_artifacts"):
        store.qualification_artifacts = []
    store.qualification_artifacts.append(ref)
    return ref


def admit_layout(layouts, profile):
    """Metadata admission only; VLEN heap expansion is explicitly unknown."""
    tables = {path.split("/")[1] for path in layouts if path.startswith("intervals/")}
    if not tables or len(tables) > profile["max_presentation_tables"]:
        raise QualificationError("all qualifying presentation tables exceed admitted count")
    fixed_metadata = 0
    variable = []
    for path, info in layouts.items():
        chunk = info["uncompressed_chunk_bytes"]
        if chunk is not None and chunk > profile["max_numeric_chunk_bytes"]:
            raise QualificationError("required numeric chunk exceeds admitted extent")
        if info["contains_variable_length_or_reference"]:
            variable.append(path)
        elif path != "processing/ophys/dff/traces/data":
            fixed_metadata += info["full_logical_array_bytes"]
    if fixed_metadata > profile["max_fixed_metadata_bytes"]:
        raise QualificationError("complete fixed-width metadata exceeds admitted extent")
    return {"qualifying_presentation_tables": len(tables),
            "fixed_metadata_logical_bytes": fixed_metadata,
            "variable_length_or_reference_fields": sorted(variable),
            "decoded_variable_length_heap_bytes": None,
            "resource_scope": "Fixed-width admission only; VLEN expansion requires the owned outer memory boundary."}


def original_support(records, info, row, alg, profile):
    """Reuse the original schedule/bins; do not claim session-wide consensus."""
    schedule = alg.schedule(records)
    clock = info["clock"]
    alg.validate_clock(clock)
    supported, unsupported = [], []
    for k in schedule["selected"]:
        event = records[k]
        try:
            spans = alg.native_bins(clock, event["start"])
        except alg.ClockUnsupported as exc:
            unsupported.append({"key": event["key"], "reason": str(exc),
                                "category": "clock_unsupported"})
            continue
        supported.append({"key": event["key"], "presentation_index": k,
                          "onset": event["start"], "spans": spans})
    if len(supported) > profile["max_supported_omissions"]:
        raise QualificationError("all supported omissions exceed admitted count; no truncation")
    privacy = {"scope": "not_query", "intersections": 0}
    if row["split"] == "query":
        histories = [[e["spans"][0][0], e["spans"][11][1]] for e in supported]
        targets = [[bisect_left(clock, records[k]["start"]),
                    bisect_left(clock, records[k]["start"] + .6)] for k in schedule["selected"]]
        alg.intersections(histories, targets)
        privacy = {"scope": "this_original_clock_and_all_its_scheduled_targets_only",
                   "history_intervals": len(histories), "target_intervals": len(targets),
                   "intersections": 0}
    result = {"supported_events": supported, "clock_unsupported_events": unsupported,
              "supported": len(supported), "clock_unsupported": len(unsupported),
              "privacy": privacy, **{k: schedule[k] for k in
              ("original_omissions", "timing_excluded", "thinning_excluded", "scheduled")}}
    if (result["original_omissions"] != result["timing_excluded"] + result["thinning_excluded"] + result["scheduled"]
            or result["scheduled"] != result["supported"] + result["clock_unsupported"]):
        raise QualificationError("complete disjoint omission accounting failed")
    return schedule, result


def admit_slices(dataset, support, profile):
    maximum = 0
    for event in support["supported_events"]:
        for left, right in event["spans"]:
            count = (right - left) * dataset.shape[1] * dataset.dtype.itemsize
            if not 0 < count <= profile["max_dff_slice_bytes"]:
                raise QualificationError("complete native bin/all-column slice exceeds admitted extent")
            maximum = max(maximum, int(count))
    return maximum


def qualify(asset, source_descriptor, row, *, deps, store, ranges, profile):
    """Compare every selected field/event for one already acquired original.

The caller admits the exact original and execution/resource profile. A success
here never substitutes this original for the task's full original cohort.
"""
    validate_profile(profile)
    if row["ophys_experiment_id"] != asset.experiment:
        raise QualificationError("source experiment does not match selected original")
    ref = deps.io.Artifact.parse(source_descriptor)
    if (ref.bytes != asset.extent_bytes or ref.role != "native_source" or ref.visibility != "operator"):
        raise QualificationError("complete immutable operator native-source descriptor required")
    ctx = SimpleNamespace(require_scientific=lambda: None, store=store)
    with deps.native.opened(ctx, ref, asset.provider_blake2b) as file:
        local_layouts = deps.pipeline.field_layouts(file, deps.native)
        layout_admission = admit_layout(local_layouts, profile)
        dataset, info = deps.native.neural_metadata(file, row)
        records = deps.native.presentations(file)
        schedule, support = original_support(records, info, row, deps.alg, profile)
        largest_slice = admit_slices(dataset, support, profile)
        metadata_value = {"schema": "neural063_original_qualification_metadata_v1",
                          "experiment": asset.experiment, "asset_sha256": digest(vars(asset), deps),
                          "source": source_descriptor, "layout_admission": layout_admission,
                          "layouts": local_layouts, "neural_metadata": info,
                          "presentations": records, "schedule": schedule, "support": support,
                          "max_admitted_native_slice_bytes": largest_slice,
                          "all_plane_session_consensus_established": False}
        metadata_ref = write(store, "local_metadata", metadata_value,
                             profile["metadata_artifact_bytes"], deps)
        local_rows, local_hashes = deps.pipeline.project_events(dataset, info, records, support, deps.alg, row)
        projection_value = {"schema": "neural063_original_qualification_projection_v1",
                            "experiment": asset.experiment, "rows": local_rows,
                            "slice_hashes": local_hashes,
                            "local_full_object_BLAKE2b_verified": True}
        projection_ref = write(store, "local_projection", projection_value,
                               profile["projection_artifact_bytes"], deps)
    # The unchanged native context has now closed and checked same-FD identity.
    with deps.range.open_versioned(asset, ranges, profile["runtime_versions"]) as file:
        if deps.pipeline.field_layouts(file, deps.native) != local_layouts:
            raise QualificationError("same-original HDF5 layouts differ")
        dataset, actual_info = deps.native.neural_metadata(file, row)
        actual_records = deps.native.presentations(file)
        if (actual_info != info or actual_records != records or
                digest(actual_info, deps) != digest(info, deps) or
                digest(actual_records, deps) != digest(records, deps)):
            raise QualificationError("same-original clock/ROI/presentation metadata differ")
        actual_schedule, actual_support = original_support(actual_records, actual_info, row, deps.alg, profile)
        if actual_schedule != schedule or actual_support != support:
            raise QualificationError("same-original schedule/support/exclusions differ")
        admit_slices(dataset, actual_support, profile)
        actual_rows, actual_hashes = deps.pipeline.project_events(dataset, actual_info, actual_records,
                                                                actual_support, deps.alg, row)
        if actual_hashes != local_hashes:
            raise QualificationError("exact consumed native array bytes/dtypes/shapes differ")
        if actual_rows != local_rows:
            raise QualificationError("original stable population outputs or event context differ")
    if len(local_rows) != support["supported"] or len(local_hashes) != 15 * len(local_rows):
        raise QualificationError("complete native event/bin accounting differs")
    sufficient = bool(local_rows)
    result = {"schema": "neural063_same_original_reader_qualification_v1",
              "disposition": "same_original_projection_equivalence" if sufficient else "same_original_metadata_only",
              "experiment": asset.experiment, "asset_sha256": digest(vars(asset), deps),
              "native_source": source_descriptor, "local_metadata": metadata_ref,
              "local_projection": projection_ref,
              "all_required_layout_metadata_equal": True, "complete_native_metadata_equal": True,
              "complete_schedule_support_exclusions_equal": True,
              "all_consumed_slice_hashes_shapes_dtypes_equal": True,
              "all_original_population_outputs_equal": True,
              "compared_supported_omissions": len(local_rows), "compared_native_bins": len(local_hashes),
              "published_valid_rois": len(row["rois"]),
              "actual_projection_sha256": digest({"rows": actual_rows, "slice_hashes": actual_hashes}, deps),
              "local_projection_values_sha256": digest({"rows": local_rows, "slice_hashes": local_hashes}, deps),
              "projection_equivalence_qualified": sufficient,
              "local_full_object_BLAKE2b_verified": True,
              "range_full_object_BLAKE2b_verified": False,
              "all_plane_session_consensus_established": False,
              "full_cohort_scientific_equivalence_qualified": False,
              "full_benchmark_complete": False, "models_or_scoring": False,
              "fallback": None if sufficient else "No eligible omission: metadata-only evidence; no other original is selected."}
    return write(store, "comparison", result, profile["comparison_artifact_bytes"], deps)
