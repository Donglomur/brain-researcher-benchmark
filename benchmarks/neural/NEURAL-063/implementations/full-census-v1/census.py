"""Task-local N063 full-cohort layout, support and physical-chunk census.

Dependencies are injected by the source-pinned private wrapper. This module
imports no scientific reader, starts no transport, and has no projection path.
Representation reservations below are conservative admission models, not OS or
HDF5 allocator limits. Unknown VLEN payloads are never given a finite bound.
"""
from collections import defaultdict
import math


DATA = "processing/ophys/dff/traces/data"
TRACE = "processing/ophys/dff/traces/"
TABLE = "processing/ophys/image_segmentation/cell_specimen_table/"
STAGES = {"layouts", "metadata_support", "chunks"}
LIMIT_KEYS = {
    "max_interval_groups", "max_group_fields", "max_name_bytes",
    "max_presentation_tables", "max_metadata_elements", "max_fixed_metadata_bytes",
    "max_numeric_chunk_bytes", "max_plane_memory_estimate_bytes",
    "max_session_memory_estimate_bytes", "max_presentation_records",
    "max_supported_events", "max_chunk_coordinates", "max_chunk_index_bytes",
    "max_support_artifact_bytes", "max_json_nodes", "max_json_depth",
    "max_json_string_chars", "artifact_bytes", "total_artifact_reservation_bytes",
    "disposition_bytes",
}
RUNTIME = {"aiohttp": "3.14.3", "fsspec": "2026.6.0", "h5py": "3.16.0"}


class CensusError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CensusError(message)


def validate_profile(profile):
    require(isinstance(profile, dict) and set(profile) == LIMIT_KEYS | {
        "stage", "runtime_versions", "reject_unknown_vlen"}, "exact census profile fields required")
    require(profile["stage"] in STAGES, "projection/unknown stage forbidden")
    require(profile["runtime_versions"] == RUNTIME, "exact qualified reader versions required")
    require(profile["reject_unknown_vlen"] is True, "unknown VLEN admission forbidden")
    for key in LIMIT_KEYS:
        require(type(profile[key]) is int and 0 < profile[key] < 2**63,
                "finite positive integer profile cap required: " + key)
    return profile


def json_upper(value, profile):
    """Walk the bounded object BEFORE canonical serialization; do not encode it.

    Six bytes per Unicode codepoint also bounds JSON escaping and UTF-8. Numeric
    values are admitted only as finite binary64 or bounded integer scalars.
    This bounds serialized bytes, not the memory of the already constructed object.
    """
    nodes = 0
    def visit(obj, depth):
        nonlocal nodes
        nodes += 1
        require(nodes <= profile["max_json_nodes"] and depth <= profile["max_json_depth"],
                "JSON node/depth pre-serialization admission refused")
        if obj is None or type(obj) is bool:
            return 5
        if type(obj) is int:
            require(obj.bit_length() <= 128, "oversize JSON integer refused")
            return 41
        if type(obj) is float:
            require(math.isfinite(obj), "nonfinite JSON scalar refused")
            return 32
        if type(obj) is str:
            require(len(obj) <= profile["max_json_string_chars"], "oversize JSON string refused")
            return 2 + 6 * len(obj)
        if type(obj) in (list, tuple):
            return 2 + sum(1 + visit(v, depth + 1) for v in obj)
        if type(obj) is dict:
            require(all(type(k) is str for k in obj), "JSON keys must be strings")
            return 2 + sum(2 + visit(k, depth + 1) + visit(v, depth + 1)
                           for k, v in obj.items())
        raise CensusError("unsupported JSON value type")
    return visit(value, 0) + 1


class Writer:
    """One ordinary-artifact reservation plus the separate disposition reserve."""
    def __init__(self, deps, store, profile):
        self.deps, self.store, self.profile = deps, store, profile
        self.used = 0
        self.reserved = 0
        self.available = profile["total_artifact_reservation_bytes"]
        require(store.meter.write_limit - store.meter.write_bytes >=
                profile["total_artifact_reservation_bytes"], "shared writer allowance lacks census reserve")
        store.census_artifacts = []
        store.census_report = None
        store.census_bank = None
        store.census_complete = False
        store.census_write_failures = []
        self.ordinary_limit = store.meter.write_limit
        self.final_opened = False

    def reserve(self, count):
        require(type(count) is int and count >= 0 and self.reserved + count <= self.available,
                "complete artifact-growth reservation refused before work")
        self.reserved += count

    def write(self, name, value, role, cap=None, *, final=False):
        cap = self.profile["artifact_bytes"] if cap is None else cap
        bound = json_upper(value, self.profile)
        require(bound <= cap, "JSON upper bound exceeds artifact admission")
        if final:
            require(bound <= self.profile["disposition_bytes"], "disposition reserve too small")
            require(not self.final_opened and self.store.meter.write_limit == self.ordinary_limit,
                    "disposition reserve may be opened exactly once")
            self.final_opened = True
            self.store.meter.write_limit += self.profile["disposition_bytes"]
        else:
            require(self.used + bound <= self.reserved, "artifact has no prior complete reservation")
        require(self.store.meter.write_bytes + bound <= self.store.meter.write_limit,
                "shared output allowance exhausted before serialization")
        body = self.deps.range.canonical(value)
        require(len(body) <= bound, "JSON admission model violated")
        before = self.store.meter.write_bytes
        try:
            ref = self.store.write(name + ".json", body, role=role, visibility="operator",
                                   producer="neural063-full-census-v1").object()
        except Exception as exc:
            self.store.census_write_failures.append({"name": name + ".json", "role": role,
                "charged_bytes": self.store.meter.write_bytes - before,
                "failure_class": type(exc).__name__, "ordinary_file_custody": "uncertain_not_authenticated",
                "certified_artifact": False})
            raise
        finally:
            if not final:
                self.used += self.store.meter.write_bytes - before
        self.store.census_artifacts.append(ref)
        if final:
            self.store.census_report = ref
        return ref


def structure_admission(file, native, profile):
    """Bound discovery lists before the unchanged field_layouts materializes them."""
    root = native.internal(file, "intervals")
    require(hasattr(root, "keys"), "intervals group absent")
    groups = tables = 0
    for name in root:
        groups += 1
        require(groups <= profile["max_interval_groups"], "interval group-count admission refused")
        require(type(name) is str and len(name) * 4 <= profile["max_name_bytes"],
                "interval name byte upper bound refused")
        group = native.internal(file, "intervals/" + name)
        if not hasattr(group, "keys"):
            continue
        keys = set()
        for key in group:
            require(len(keys) < profile["max_group_fields"], "presentation field-count admission refused")
            require(type(key) is str and len(key) * 4 <= profile["max_name_bytes"],
                    "presentation field name bound refused")
            keys.add(key)
        if {"image_name", "omitted"} & keys:
            tables += 1
            require(tables <= profile["max_presentation_tables"], "presentation table-count admission refused")
    require(tables > 0, "no qualifying presentation table")
    return {"interval_groups": groups, "presentation_tables": tables}


def fixed_shape(field):
    shape = field.get("shape")
    require(type(shape) is list and 1 <= len(shape) <= 2 and
            all(type(x) is int and 0 <= x <= 2_000_000 for x in shape), "invalid bounded dataset shape")
    require(field.get("contains_variable_length_or_reference") is False and
            field.get("heap_payload_bytes") == 0, "unknown VLEN/reference payload is unadmitted")
    size = field.get("dtype_bytes")
    require(type(size) is int and 0 < size <= 512, "unsupported fixed element width")
    count = math.prod(shape)
    require(field.get("full_logical_array_bytes") == count * size and
            field.get("fixed_element_buffer_bytes") == count * size, "fixed layout byte identity mismatch")
    chunks = field.get("chunks")
    if chunks is not None:
        require(type(chunks) is list and len(chunks) == len(shape) and
                all(type(x) is int and x > 0 for x in chunks), "invalid nominal chunk shape")
        require(field.get("uncompressed_chunk_bytes") == math.prod(chunks) * size,
                "nominal decoded chunk byte identity mismatch")
    require(type(field.get("dataset_storage_bytes")) is int and field["dataset_storage_bytes"] >= 0,
            "invalid allocated storage metadata")
    return count, count * size


def admit_layout(fields, profile):
    """Predict all metadata allocations/artifacts before any native array read.

    Fixed-width input bytes and JSON-size bounds are distinct from conservative
    Python representation estimates. The latter are not a hard RAM certificate.
    """
    base = {DATA, TRACE + "timestamps", TRACE + "rois",
            TABLE + "id", TABLE + "cell_specimen_id", TABLE + "valid_roi"}
    require(type(fields) is dict and base <= set(fields), "required layout fields absent")
    groups = defaultdict(dict)
    elements = fixed_bytes = largest_chunk = 0
    for path, field in fields.items():
        require(type(path) is str and len(path) * 4 <= 4 * profile["max_name_bytes"],
                "layout path bound refused")
        count, size = fixed_shape(field)
        chunk = field.get("uncompressed_chunk_bytes") or 0
        if path != DATA:
            largest_chunk = max(largest_chunk, chunk)
            require(chunk <= profile["max_numeric_chunk_bytes"], "decoded metadata chunk admission refused")
            require(len(field["shape"]) == 1, "metadata vector must be one-dimensional")
            elements += count
            fixed_bytes += size
        if path.startswith("intervals/"):
            parts = path.split("/")
            require(len(parts) == 3 and parts[2] in {"id", "start_time", "image_name", "omitted"},
                    "unexpected presentation layout path")
            groups[parts[1]][parts[2]] = field
        else:
            require(path in base, "unexpected metadata layout field")
    require(0 < len(groups) <= profile["max_presentation_tables"], "table-count admission refused")
    require(elements <= profile["max_metadata_elements"] and fixed_bytes <= profile["max_fixed_metadata_bytes"],
            "complete fixed metadata allocation admission refused")
    data = fields[DATA]
    require(len(data["shape"]) == 2 and 0 < data["shape"][0] <= 2_000_000 and
            0 < data["shape"][1] <= 20_000 and data["dtype"] in ("float32", "float64"),
            "unsupported original dF/F shape/type")
    frames, columns = data["shape"]
    require(fields[TRACE + "timestamps"]["shape"] == [frames] and
            fields[TRACE + "timestamps"]["dtype"] in ("float32", "float64"), "clock layout mismatch")
    require(fields[TRACE + "rois"]["shape"] == [columns], "ROI region layout mismatch")
    roi_rows = fields[TABLE + "id"]["shape"][0]
    require(0 < roi_rows <= 20_000 and all(fields[TABLE + k]["shape"] == [roi_rows]
            for k in ("cell_specimen_id", "valid_roi")), "ROI table shape mismatch")
    records = 0
    longest_image = 0
    longest_group = 0
    for name, values in groups.items():
        require(set(values) == {"id", "start_time", "image_name", "omitted"}, "incomplete presentation layout")
        count = values["id"]["shape"][0]
        require(count <= 200_000 and all(v["shape"] == [count] for v in values.values()),
                "complete presentation vector shape mismatch")
        image = values["image_name"]
        require(image["dtype"] == "|S" + str(image["dtype_bytes"]),
                "only explicitly fixed-width image strings are resource-admitted")
        records += count
        longest_image = max(longest_image, image["dtype_bytes"])
        longest_group = max(longest_group, len(name))
    require(records <= profile["max_presentation_records"], "all presentation rows exceed reservation")
    # Up to 32 JSON bytes per finite float, 1024 per ROI join, escaped names,
    # and generous fixed schema/path overhead. All events could be omissions.
    record_json = 512 + 6 * (longest_group + 21 + longest_image)
    metadata_json = 16_384 + frames * 32 + roi_rows * 1024 + records * record_json
    support_json = 16_384 + records * (2048 + 6 * (longest_group + 21))
    schedule_json = 16_384 + records * (record_json + 2048)
    memory = fixed_bytes + largest_chunk + 256 * elements + 8 * metadata_json
    require(metadata_json <= profile["artifact_bytes"], "complete metadata artifact reservation refused")
    require(support_json <= profile["max_support_artifact_bytes"] and
            schedule_json <= profile["max_support_artifact_bytes"], "complete support artifact reservation refused")
    require(memory <= profile["max_plane_memory_estimate_bytes"], "plane representation estimate unadmitted")
    return {"fixed_metadata_bytes": fixed_bytes, "metadata_elements": elements,
            "presentation_records": records, "largest_nominal_metadata_chunk_bytes": largest_chunk,
            "dff_nominal_chunk_bytes_for_future_projection_only": data.get("uncompressed_chunk_bytes"),
            "metadata_json_upper_bytes": metadata_json, "support_json_upper_bytes": support_json,
            "schedule_json_upper_bytes": schedule_json, "plane_memory_estimate_bytes": memory,
            "memory_is_hard_certificate": False, "vlen_payloads_admitted": False}


def session_admission(rows, admissions, profile):
    require(bool(rows), "complete nonempty original session required")
    aa = [admissions[r["ophys_experiment_id"]] for r in rows]
    # Consensus can fail, so admit every plane's full record count before equality.
    require(all(a["presentation_records"] <= profile["max_supported_events"] for a in aa),
            "worst-case all-omission support allocation refused")
    support = sum(a["support_json_upper_bytes"] for a in aa)
    schedule = max(a["schedule_json_upper_bytes"] for a in aa)
    estimate = sum(a["plane_memory_estimate_bytes"] for a in aa) + 8 * (support + schedule)
    require(estimate <= profile["max_session_memory_estimate_bytes"],
            "complete session representation estimate unadmitted")
    return {"session_memory_estimate_bytes": estimate, "memory_is_hard_certificate": False,
            "support_json_upper_bytes": support, "schedule_json_upper_bytes": schedule}


def checked_intervals(intervals, shape, profile):
    require(type(intervals) is list and len(intervals) <= 15 * profile["max_supported_events"],
            "complete supported interval count refused")
    for span in intervals:
        require(type(span) is list and len(span) == 2 and all(type(x) is int for x in span) and
                0 <= span[0] < span[1] <= shape[0], "invalid original supported interval")


def chunk_plan(shape, chunks, intervals, profile):
    checked_intervals(intervals, shape, profile)
    if chunks is None:
        touches = len(intervals)
    else:
        require(len(chunks) == 2 and all(type(x) is int and x > 0 for x in chunks), "invalid chunk dimensions")
        ct, cc = chunks
        nc = (shape[1] + cc - 1) // cc
        touches = sum(((right - 1) // ct - left // ct + 1) * nc for left, right in intervals)
    require(touches <= profile["max_chunk_coordinates"], "chunk-coordinate allocation refused before enumeration")
    upper = 16_384 + touches * 2048
    require(upper <= profile["max_chunk_index_bytes"], "chunk-index growth reservation refused before enumeration")
    estimate = upper * 8 + len(intervals) * 128
    require(estimate <= profile["max_plane_memory_estimate_bytes"], "chunk-index representation estimate refused")
    return {"coordinate_touches": touches, "chunk_json_upper_bytes": upper,
            "chunk_memory_estimate_bytes": estimate, "memory_is_hard_certificate": False}


def chunk_census(dataset, intervals, *, profile, extent_bytes, block_bytes, check_time=None):
    """Dataset-ID metadata only; all source columns of each original read slice.

    get_chunk_info_by_coord obtains compressed extents without decoding chunks.
    The union footprint is not a cache-miss/transfer upper bound. Contiguous
    layout and unallocated fill regions are represented explicitly.
    """
    shape = list(dataset.shape)
    require(len(shape) == 2 and all(type(x) is int and x > 0 for x in shape), "two-dimensional data required")
    require(str(dataset.dtype) in ("float32", "float64"), "fixed floating dF/F required")
    require(type(extent_bytes) is int and extent_bytes > 0 and type(block_bytes) is int and block_bytes > 0,
            "positive original extent/cache block required")
    checked_intervals(intervals, shape, profile)
    width = int(dataset.dtype.itemsize)
    chunks = dataset.chunks
    admission = chunk_plan(shape, chunks, intervals, profile)
    entries = []
    ranges = []
    touches = 0
    coordinates = {}
    if chunks is not None:
        ct, cc = chunks
        nc = (shape[1] + cc - 1) // cc
        touches = admission["coordinate_touches"]
        for left, right in intervals:
            for tr in range(left // ct, (right - 1) // ct + 1):
                for cr in range(nc):
                    coordinate = (tr * ct, cr * cc)
                    coordinates[coordinate] = coordinates.get(coordinate, 0) + 1
        for coordinate in sorted(coordinates):
            if check_time is not None:
                check_time()
            info = dataset.id.get_chunk_info_by_coord(coordinate)
            offset, count = info.byte_offset, int(info.size)
            require(count >= 0, "negative chunk allocation")
            if offset is None:
                require(count == 0 and (info.chunk_offset is None or tuple(info.chunk_offset) == coordinate),
                        "unallocated chunk has inconsistent identity")
                disposition = "unallocated_fill"
            else:
                require(tuple(info.chunk_offset) == coordinate, "chunk-coordinate identity mismatch")
                offset = int(offset)
                require(count > 0 and 0 <= offset < offset + count <= extent_bytes,
                        "chunk extent outside fixed original body")
                ranges.append((offset, offset + count))
                disposition = "allocated"
            entries.append({"coordinate": list(coordinate), "byte_offset": offset,
                            "stored_bytes": count, "filter_mask": int(info.filter_mask),
                            "original_slice_accesses": coordinates[coordinate], "disposition": disposition})
        layout_kind = "chunked"
    else:
        offset = dataset.id.get_offset()
        stored = int(dataset.id.get_storage_size())
        if offset is None:
            require(stored == 0, "non-addressable allocated storage refused")
            layout_kind = "contiguous_unallocated_fill"
        else:
            offset = int(offset)
            require(stored == math.prod(shape) * width and 0 <= offset < offset + stored <= extent_bytes,
                    "contiguous fixed-size extent mismatch")
            layout_kind = "contiguous"
        for left, right in intervals:
            start = None if offset is None else offset + left * shape[1] * width
            count = 0 if offset is None else (right - left) * shape[1] * width
            if count:
                ranges.append((start, start + count))
            entries.append({"rows": [left, right], "byte_offset": start,
                            "stored_bytes": count, "disposition":
                            "unallocated_fill" if offset is None else "allocated", "original_slice_accesses": 1})
        touches = len(intervals)
    # Merge block intervals rather than expanding possibly enormous block sets.
    blocks = sorted((start // block_bytes, (end - 1) // block_bytes + 1) for start, end in ranges)
    merged = []
    for start, end in blocks:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(end, merged[-1][1])
        else:
            merged.append([start, end])
    body_union = sum(min(extent_bytes, end * block_bytes) - start * block_bytes for start, end in merged)
    result = {"schema": "neural063_physical_chunk_census_v1", "layout": layout_kind,
              "shape": shape, "dtype": str(dataset.dtype), "all_source_columns": True,
              "supported_intervals": len(intervals), "coordinate_touches_before_union": touches,
              "entries": entries, "cache_block_intervals": merged,
              "unique_payload_cache_blocks": sum(end - start for start, end in merged),
              "unique_payload_cache_bytes": body_union,
              "stored_chunk_bytes_sum": sum(e["stored_bytes"] for e in entries),
              "stored_bytes_counting_repeated_slice_accesses":
                  sum(e["stored_bytes"] * e["original_slice_accesses"] for e in entries),
              "dff_values_decoded": False, "full_object_BLAKE2b_verified": False,
              "includes_hdf5_index_metadata": False, "is_actual_transfer_upper_bound": False,
              "fill_value_decoded": False}
    require(json_upper(result, profile) <= profile["max_chunk_index_bytes"], "chunk-index JSON bound refused")
    return result


def read_artifact(deps, store, ref, role, cap, schema, profile):
    require(type(ref) is dict and ref.get("visibility") == "operator" and
            type(ref.get("bytes")) is int and ref["bytes"] <= cap, "bounded operator artifact required")
    require(ref["bytes"] * 32 <= profile["max_plane_memory_estimate_bytes"],
            "decoded saved JSON representation estimate refused before parse")
    value = deps.pipeline.read_value(store, ref, role, cap, schema)
    require(json_upper(value, profile) <= cap * 8, "decoded artifact representation exceeds admission")
    return value


def bank_identity(bank, deps, assets_manifest, rows, schema):
    require(type(bank) is dict and bank.get("schema") == schema and
            bank.get("selection_sha256") == deps.pipeline.SELECTION_SHA256 and
            bank.get("assets_sha256") == deps.pipeline.digest(assets_manifest) and
            bank.get("source_counts") == deps.pipeline.EXPECTED,
            "complete bank source/selection identity mismatch")
    entries = bank.get("entries")
    require(type(entries) is list and len(entries) == len(rows), "complete bank row count required")
    joined = {e["experiment"]: e for e in entries}
    require(len(joined) == len(rows) and set(joined) == {r["ophys_experiment_id"] for r in rows},
            "complete unique original bank join required")
    return joined


def new_dispositions(rows, stage):
    return {r["ophys_experiment_id"]: {"experiment": r["ophys_experiment_id"],
            "session": r["ophys_session_id"], "status": "unattempted", "stage": stage,
            "reason": None, "artifacts": []} for r in rows}


def compact_ref(ref):
    name = ref["path"].rsplit("/", 1)[-1]
    require(len(name) <= 96 and len(ref["role"]) <= 64, "compact artifact identity bound refused")
    return {"name": name, "bytes": ref["bytes"], "sha256": ref["sha256"], "role": ref["role"]}


def mark_failure(states, eid, exc):
    states[eid]["status"] = "failed"
    states[eid]["reason"] = (type(exc).__name__ + ": " + str(exc))[:160]


def support_for_chunks(indexed, row, schedule_refs, deps, store, profile):
    eid = row["ophys_experiment_id"]
    support = read_artifact(deps, store, indexed[eid]["support"], "range_experiment_support",
                            profile["max_support_artifact_bytes"], "neural063_range_support_v1", profile)
    deps.pipeline.identity_matches(support, row)
    require(support["metadata"] == indexed[eid]["metadata"] and
            support["schedule"] == schedule_refs[row["ophys_session_id"]], "support lineage differs from full bank")
    events = support["supported_events"]
    require(type(events) is list and len(events) == support["supported"] and
            len(events) <= profile["max_supported_events"], "all supported events required")
    require(all(type(e.get("spans")) is list and len(e["spans"]) == 15 for e in events),
            "every original supported event needs 15 bins")
    return events, [span for event in events for span in event["spans"]]


def run_census(selection, assets_manifest, *, deps, store, ranges, profile, input_bank=None):
    """Run one selected stage; return a complete or explicitly incomplete report.

    The wrapper owns its separate final budget/failure receipt. This core retains
    every original disposition and successful artifact, and never creates a
    complete bank after a failed or unattempted required plane/session.
    """
    store.census_complete = False
    store.census_report = store.census_bank = None
    store.census_artifacts = []
    validate_profile(profile)
    rows = deps.pipeline.full_scope(selection)
    assets = deps.pipeline.validate_assets(assets_manifest, selection)
    require(len(rows) == 1936 and len(assets) == 1936, "full original 1936-plane scope required")
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["ophys_session_id"]].append(row)
    require(len(grouped) == 703, "full original 703-session scope required")
    require(profile["disposition_bytes"] >= 8192 + 4096 * len(rows) + 2048 * len(grouped),
            "complete failure disposition reserve required before provider access")
    writer = Writer(deps, store, profile)
    stage = profile["stage"]
    states = new_dispositions(rows, stage)
    bank_ref = None
    error = None
    current = None
    layouts = {}
    metadata_refs = {}
    support_refs = {}
    schedule_refs = {}
    entries = []
    admissions = {}
    session_estimates = {}
    complete_sessions = set()
    try:
        if stage == "layouts":
            require(input_bank is None, "layout stage has no reusable input bank")
            # Each required layout is bounded before its value is built. The
            # 4096-per-field allowance covers all fixed layout schema values.
            layout_upper = 8192 + (6 + 4 * profile["max_presentation_tables"]) * 4096
            require(layout_upper <= profile["artifact_bytes"], "layout artifact reservation refused")
            writer.reserve(len(rows) * layout_upper + profile["artifact_bytes"])
            for row in rows:
                current = eid = row["ophys_experiment_id"]
                with deps.range.open_versioned(assets[eid], ranges, profile["runtime_versions"]) as file:
                    structure_admission(file, deps.native, profile)
                    fields = deps.pipeline.field_layouts(file, deps.native)
                value = {"schema": "neural063_range_layout_v1", "experiment": eid,
                         "asset_sha256": deps.pipeline.digest(vars(assets[eid])), "fields": fields,
                         "array_values_decoded": False, "full_object_BLAKE2b_verified": False}
                ref = writer.write("layout_" + eid, value, "range_layout", layout_upper)
                entries.append({"experiment": eid, "layout": ref})
                states[eid].update(status="complete", artifact_sha256=ref["sha256"])
                states[eid]["artifacts"].append(compact_ref(ref))
                del fields, value
            current = None
            bank = {"schema": "neural063_range_layout_bank_v1", "entries": entries,
                    "selection_sha256": deps.pipeline.SELECTION_SHA256,
                    "assets_sha256": deps.pipeline.digest(assets_manifest), "source_counts": deps.pipeline.EXPECTED,
                    "array_values_decoded": False, "full_object_BLAKE2b_verified": False}
            current = None
            bank_ref = writer.write("layout_bank", bank, "range_layout_bank")
            del bank
            complete_sessions = set(grouped)
        else:
            schema = ("neural063_range_layout_bank_v1" if stage == "metadata_support"
                      else "neural063_census_metadata_support_bank_v1")
            indexed = bank_identity(input_bank, deps, assets_manifest, rows, schema)
            if stage == "chunks":
                require(input_bank.get("complete") is True and input_bank.get("response_projection_performed") is False,
                        "complete metadata/support bank required")
                ss = input_bank.get("sessions")
                require(type(ss) is list and len(ss) == 703 and
                        {s["session"] for s in ss} == set(grouped), "complete unique session bank required")
                schedule_refs = {s["session"]: s["schedule"] for s in ss}
            # Complete layout admission precedes ANY original metadata array.
            for row in rows:
                current = eid = row["ophys_experiment_id"]
                ref = indexed[eid]["layout"]
                value = read_artifact(deps, store, ref, "range_layout", profile["artifact_bytes"],
                                      "neural063_range_layout_v1", profile)
                require(value["experiment"] == eid and value["asset_sha256"] == deps.pipeline.digest(vars(assets[eid])),
                        "layout original identity mismatch")
                layouts[eid] = ref
                admissions[eid] = admit_layout(value["fields"], profile)
                del value
            if stage == "metadata_support":
                for sid, session_rows in grouped.items():
                    current = session_rows[0]["ophys_experiment_id"]
                    session_estimates[sid] = session_admission(session_rows, admissions, profile)
                required = sum(a["metadata_json_upper_bytes"] + a["support_json_upper_bytes"] for a in admissions.values())
                required += sum(a["schedule_json_upper_bytes"] for a in session_estimates.values())
                current = None
                writer.reserve(required + profile["artifact_bytes"])
                for row in rows:
                    current = eid = row["ophys_experiment_id"]
                    expected = read_artifact(deps, store, layouts[eid], "range_layout", profile["artifact_bytes"],
                                             "neural063_range_layout_v1", profile)
                    with deps.range.open_versioned(assets[eid], ranges, profile["runtime_versions"]) as file:
                        structure_admission(file, deps.native, profile)
                        require(deps.pipeline.field_layouts(file, deps.native) == expected["fields"],
                                "same-version layout changed before metadata")
                        dataset, info = deps.native.neural_metadata(file, row)
                        records = deps.native.presentations(file)
                        native_layout = deps.pipeline.layout(dataset)
                    value = {"schema": "neural063_range_native_metadata_v1", "experiment": eid,
                             "mouse": row["mouse_id"], "session": row["ophys_session_id"], "split": row["split"],
                             "asset_sha256": deps.pipeline.digest(vars(assets[eid])), "neural_metadata": info,
                             "presentations": records, "presentation_sha256": deps.pipeline.digest(records),
                             "layout": native_layout, "response_projection_performed": False,
                             "full_object_BLAKE2b_verified": False}
                    ref = writer.write("metadata_" + eid, value, "range_native_metadata",
                                       admissions[eid]["metadata_json_upper_bytes"])
                    metadata_refs[eid] = ref
                    states[eid].update(status="unattempted", progress="metadata_complete_support_unattempted",
                                       artifact_sha256=ref["sha256"])
                    states[eid]["artifacts"].append(compact_ref(ref))
                    # No previous plane's clock/records survive into the next
                    # native read. The retained dictionaries contain refs only.
                    del dataset, info, records, native_layout, value, expected
                for sid, session_rows in sorted(grouped.items()):
                    current = session_rows[0]["ophys_experiment_id"]
                    planes = {r["ophys_experiment_id"]: read_artifact(deps, store, metadata_refs[r["ophys_experiment_id"]],
                              "range_native_metadata", admissions[r["ophys_experiment_id"]]["metadata_json_upper_bytes"],
                              "neural063_range_native_metadata_v1", profile) for r in session_rows}
                    schedule, supports = deps.pipeline.derive_session(session_rows, planes, deps.alg)
                    schedule["schema"] = "neural063_range_session_schedule_v1"
                    sr = writer.write("schedule_" + sid, schedule, "range_session_schedule",
                                      session_estimates[sid]["schedule_json_upper_bytes"])
                    schedule_refs[sid] = sr
                    for row in session_rows:
                        current = eid = row["ophys_experiment_id"]
                        value = {"schema": "neural063_range_support_v1", **supports[eid],
                                 "metadata": metadata_refs[eid], "schedule": sr}
                        ref = writer.write("support_" + eid, value, "range_experiment_support",
                                           admissions[eid]["support_json_upper_bytes"])
                        support_refs[eid] = ref
                        states[eid].update(status="complete", artifact_sha256=ref["sha256"],
                                           supported_events=value["supported"])
                        states[eid]["artifacts"].append(compact_ref(ref))
                    complete_sessions.add(sid)
                    del planes, schedule, supports, value
                current = None
                entries = [{"experiment": r["ophys_experiment_id"], "layout": layouts[r["ophys_experiment_id"]],
                            "metadata": metadata_refs[r["ophys_experiment_id"]], "support": support_refs[r["ophys_experiment_id"]]}
                           for r in rows]
                bank = {"schema": "neural063_census_metadata_support_bank_v1", "complete": True,
                        "entries": entries, "sessions": [{"session": s, "schedule": schedule_refs[s]} for s in sorted(grouped)],
                        "selection_sha256": deps.pipeline.SELECTION_SHA256,
                        "assets_sha256": deps.pipeline.digest(assets_manifest), "source_counts": deps.pipeline.EXPECTED,
                        "layout_bank_sha256": deps.pipeline.digest(input_bank),
                        "response_projection_performed": False, "full_object_BLAKE2b_verified": False}
                current = None
                bank_ref = writer.write("metadata_support_bank", bank, "census_metadata_support_bank")
                del bank
            else:
                chunk_admissions = {}
                for row in rows:
                    current = eid = row["ophys_experiment_id"]
                    events, spans = support_for_chunks(indexed, row, schedule_refs, deps, store, profile)
                    expected = read_artifact(deps, store, layouts[eid], "range_layout", profile["artifact_bytes"],
                                             "neural063_range_layout_v1", profile)
                    data_layout = expected["fields"][DATA]
                    chunk_admissions[eid] = chunk_plan(data_layout["shape"], data_layout["chunks"], spans, profile)
                    del events, spans, expected, data_layout
                current = None
                writer.reserve(sum(a["chunk_json_upper_bytes"] for a in chunk_admissions.values()) + profile["artifact_bytes"])
                for row in rows:
                    current = eid = row["ophys_experiment_id"]
                    events, spans = support_for_chunks(indexed, row, schedule_refs, deps, store, profile)
                    expected = read_artifact(deps, store, layouts[eid], "range_layout", profile["artifact_bytes"],
                                             "neural063_range_layout_v1", profile)
                    with deps.range.open_versioned(assets[eid], ranges, profile["runtime_versions"]) as file:
                        structure_admission(file, deps.native, profile)
                        require(deps.pipeline.field_layouts(file, deps.native) == expected["fields"],
                                "same-version layout changed before chunk metadata")
                        value = chunk_census(deps.native.internal(file, DATA), spans, profile=profile,
                                             extent_bytes=assets[eid].extent_bytes, block_bytes=ranges.limits.block_bytes,
                                             check_time=ranges.check_time)
                    value.update(experiment=eid, session=row["ophys_session_id"], mouse=row["mouse_id"], split=row["split"],
                                 asset_sha256=deps.pipeline.digest(vars(assets[eid])), support=indexed[eid]["support"],
                                 zero_eligible_events=not events)
                    ref = writer.write("chunks_" + eid, value, "census_physical_chunks",
                                       chunk_admissions[eid]["chunk_json_upper_bytes"])
                    entries.append({"experiment": eid, "chunks": ref})
                    states[eid].update(status="complete", artifact_sha256=ref["sha256"], supported_events=len(events))
                    states[eid]["artifacts"].append(compact_ref(ref))
                    del events, spans, expected, value
                complete_sessions = set(grouped)
                current = None
                bank = {"schema": "neural063_census_chunk_bank_v1", "complete": True, "entries": entries,
                        "selection_sha256": deps.pipeline.SELECTION_SHA256,
                        "assets_sha256": deps.pipeline.digest(assets_manifest), "source_counts": deps.pipeline.EXPECTED,
                        "metadata_support_bank_sha256": deps.pipeline.digest(input_bank),
                        "dff_values_decoded": False, "full_object_BLAKE2b_verified": False}
                current = None
                bank_ref = writer.write("chunk_bank", bank, "census_chunk_bank")
                del bank
    except Exception as exc:
        error = (type(exc).__name__ + ": " + str(exc))[:160]
        if current is not None:
            mark_failure(states, current, exc)
    sessions = []
    for sid, session_rows in sorted(grouped.items()):
        complete = all(states[r["ophys_experiment_id"]]["status"] == "complete" for r in session_rows)
        # A metadata session needs its successful unchanged all-plane consensus.
        if stage == "metadata_support":
            complete = complete and sid in complete_sessions
        sessions.append({"session": sid, "status": "complete" if complete else "held",
                         "required_planes": len(session_rows), "artifacts":
                         [compact_ref(schedule_refs[sid])] if stage == "metadata_support" and sid in schedule_refs else []})
    complete = error is None and bank_ref is not None and all(s["status"] == "complete" for s in sessions)
    if not complete:
        bank_ref = None
    result = {"schema": "neural063_full_census_report_v1", "stage": stage, "complete": complete,
              "cohort_status": "complete_for_selected_census_stage" if complete else "held_incomplete",
              "selection_sha256": deps.pipeline.SELECTION_SHA256, "source_counts": deps.pipeline.EXPECTED,
              "bank": bank_ref, "error": error, "planes": list(states.values()), "sessions": sessions,
              "failure_scope": None if error is None else ("cohort_admission_or_finalization" if current is None else "plane_or_session"),
              "uncertified_write_attempts": store.census_write_failures,
              "ordinary_artifact_bytes_charged_including_failures": writer.used,
              "ordinary_artifact_bytes_reserved": writer.reserved,
              "dff_values_decoded": False, "full_object_BLAKE2b_verified": False,
              "finite_dff_values_established": False,
              "memory_is_hard_certificate": False, "benchmark_ready": False}
    ref = writer.write("census_report", result, "census_dispositions", profile["disposition_bytes"], final=True)
    store.census_complete = complete
    store.census_bank = bank_ref
    return ref
