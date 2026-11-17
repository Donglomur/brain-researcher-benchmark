"""Portable, metadata-only support for the conditional NEURAL-099 condition.

Callers supply already acquired metadata; this module performs no file or network
I/O. ``decode_pinned_json`` can authenticate raw metadata against an externally
trusted digest. ``build_support`` validates the joined metadata and selects all
source-labelled good and mua clusters in literal named regions. Passing Python
objects directly establishes consistency only, not source authenticity.

The result is a roster for future preparation, not a prepared neural dataset.
It never infers biological aliases, trial times, recording duration, physical
depth, or observed silence. Unit identifiers are scoped by their asset.
"""

from collections import Counter
from datetime import datetime
import hashlib
import json
import math
from pathlib import PurePosixPath
import re


NAMED_REGIONS = ("BIC", "MGd", "MGm", "MGv", "MZMG", "SG")
UNASSIGNED_REGION = " "
SOURCE_QUALITIES = ("good", "mua")
MAX_ASSETS = 1000
MAX_CLUSTERS_PER_ASSET = 100000
MAX_TRIAL_ROWS_PER_ASSET = 1000000

# This is a metadata consistency profile, not a readiness/exposure certificate.
MGN_001421_METADATA_PROFILE = {
    "source_manifest_sha256":
        "320eb843e01353ce59936393df37dd9eda1d12150f9fc9fc66f48aa968dc9966",
    "source_file_count": 26,
    "source_subject_count": 26,
    "source_trial_rows": 5238,
    "source_cluster_count": 2053,
    "eligible_cluster_count": 1387,
    "unassigned_cluster_count": 666,
    "nonempty_region_cell_count": 49,
    "quality_counts": {"good": 458, "mua": 1595},
    "region_cluster_counts": {
        " ": 666, "BIC": 81, "MGd": 96, "MGm": 143,
        "MGv": 948, "MZMG": 93, "SG": 26,
    },
    "region_file_support": {
        " ": 26, "BIC": 6, "MGd": 5, "MGm": 14,
        "MGv": 19, "MZMG": 3, "SG": 2,
    },
    "trial_row_count_histogram": {"200": 6, "201": 6, "202": 13, "206": 1},
}


class SupportError(ValueError):
    """Metadata is inconsistent with the source contract or selected profile."""


def _require(condition, message):
    if not condition:
        raise SupportError(message)


def _object(value, label):
    _require(type(value) is dict, label + " must be an object")
    return value


def _integer(value, label, minimum=0, maximum=None):
    _require(type(value) is int and value >= minimum,
             label + " must be an integer >= " + str(minimum))
    if maximum is not None:
        _require(value <= maximum, label + " exceeds supported metadata bound")
    return value


def _text(value, label):
    _require(type(value) is str and 0 < len(value) <= 4096,
             label + " must be nonempty bounded text")
    _require(all(ord(c) >= 32 for c in value), label + " contains control text")
    return value


def _digest(value, label):
    _require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
             label + " must be a lowercase SHA-256 digest")
    return value


def _field(obj, key, label):
    _object(obj, label)
    _require(key in obj, label + " is missing " + key)
    return obj[key]


def _unique_pairs(pairs):
    value = {}
    for key, item in pairs:
        _require(key not in value, "duplicate JSON key: " + key)
        value[key] = item
    return value


def _reject_constant(value):
    raise SupportError("non-finite JSON constant: " + value)


def _finite_float(value):
    number = float(value)
    _require(math.isfinite(number), "non-finite JSON number")
    return number


def decode_pinned_json(raw, expected_sha256, *, max_bytes=1048576):
    """Decode bounded UTF-8 JSON bytes after a caller-supplied digest check.

    The expected digest must come from the caller's trusted source evidence.
    No file is opened and no source digest is discovered by this function.
    """
    _require(type(raw) is bytes, "raw metadata must be bytes")
    _integer(max_bytes, "max_bytes", minimum=1)
    _require(len(raw) <= max_bytes, "metadata exceeds byte bound")
    _digest(expected_sha256, "expected_sha256")
    _require(hashlib.sha256(raw).hexdigest() == expected_sha256,
             "metadata SHA-256 mismatch")
    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs,
                            parse_constant=_reject_constant, parse_float=_finite_float)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise SupportError("invalid UTF-8 JSON metadata") from exc
    return _object(result, "metadata document")


def _count_map(value, allowed, label):
    _object(value, label)
    _require(set(value) <= set(allowed), label + " has an unknown category")
    for key, count in value.items():
        _integer(count, label + "." + key, minimum=1)
    return value


def _shape_length(schema, path, maximum):
    item = _object(_field(schema, path, "schema"), path)
    shape = _field(item, "shape", path)
    _require(type(shape) is list and len(shape) == 1,
             path + " must have a one-dimensional header shape")
    return _integer(shape[0], path + " row count", minimum=1, maximum=maximum)


def _clock(identity):
    start = _text(_field(identity, "session_start_time", "identity"),
                  "session_start_time")
    reference = _field(identity, "timestamps_reference_time", "identity")
    _require(type(reference) is list and reference == [start],
             "timestamp reference must exactly match the declared session start")
    try:
        parsed = datetime.fromisoformat(start)
    except ValueError as exc:
        raise SupportError("invalid declared session start") from exc
    _require(parsed.tzinfo is not None and parsed.utcoffset() is not None,
             "declared session start must include a timezone")
    return {
        "session_start_time": start,
        "timestamps_reference_time": reference[0],
        "common_reference_declared": True,
        "actual_event_times_authenticated": False,
        "observation_intervals_available": False,
    }


def _asset_identity(asset):
    _object(asset, "source asset")
    asset_id = _text(_field(asset, "asset_id", "source asset"), "asset_id")
    path = _text(_field(asset, "path", "source asset"), "source path")
    parts = path.split("/")
    _require(not PurePosixPath(path).is_absolute()
             and all(part not in ("", ".", "..") for part in parts)
             and "\\" not in path, "source path must be a relative POSIX asset path")
    return {
        "asset_id": asset_id,
        "path": path,
        "bytes": _integer(_field(asset, "bytes", "source asset"),
                          "source asset bytes", minimum=1),
        "sha256": _digest(_field(asset, "sha256", "source asset"),
                          "source asset SHA-256"),
        "subject_id": _text(_field(asset, "subject_id", "source asset"),
                            "source subject_id"),
    }


def _check_profile(profile, summary, source_manifest_sha256):
    _object(profile, "qualification_profile")
    required = set(MGN_001421_METADATA_PROFILE)
    _require(set(profile) == required,
             "metadata profile must supply every declared count and source digest")
    _require(_digest(profile["source_manifest_sha256"], "profile source digest")
             == source_manifest_sha256, "metadata profile source digest mismatch")
    map_keys = {"quality_counts", "region_cluster_counts", "region_file_support",
                "trial_row_count_histogram"}
    for key in required - {"source_manifest_sha256"}:
        if key in map_keys:
            expected = _object(profile[key], "profile " + key)
            for category, count in expected.items():
                _text(category, "profile category")
                _integer(count, "profile " + key + "." + category)
        else:
            _integer(profile[key], "profile " + key)
        _require(profile[key] == summary[key], "metadata profile mismatch: " + key)


def build_support(census, sources, *, source_manifest_sha256,
                  qualification_profile=None):
    """Return selected ragged anatomy support from joined source metadata.

    ``source_manifest_sha256`` is the digest of the raw ``SOURCES.json`` bytes,
    not the manifest's upstream ``source_manifest_sha256`` field. The census
    must declare this same digest. Call ``decode_pinned_json`` before this
    function when source authentication is required.

    Regions contain only nonempty named source support. Missing region cells
    are listed separately and must never become zero responses or denominators.
    ``source_trial_rows`` is a header count; a row ordinal is not a source trial
    ID or a timestamp. ``animal_id`` remains unbound for subsequent identity
    qualification. No temporal, split, baseline, or score defaults are selected.
    """
    _object(census, "census")
    _object(sources, "sources")
    _digest(source_manifest_sha256, "source_manifest_sha256")
    _require(_field(census, "source_manifest_sha256", "census")
             == source_manifest_sha256, "census/source manifest linkage mismatch")
    _require(_field(census, "response_array_values_opened", "census") is False,
             "expected a metadata-only census")
    _require(_field(census, "scientific_qualified", "census") is False,
             "this adapter accepts the unqualified source census only")
    assets_in = _field(sources, "assets", "sources")
    records = _field(census, "records", "census")
    _require(type(assets_in) is list and 0 < len(assets_in) <= MAX_ASSETS,
             "source assets must be a nonempty bounded list")
    _require(type(records) is list and len(records) == len(assets_in),
             "census must cover each source asset exactly once")
    assets = {}
    paths = set()
    for item in assets_in:
        asset = _asset_identity(item)
        _require(asset["asset_id"] not in assets, "duplicate source asset_id")
        _require(asset["path"] not in paths, "duplicate source asset path")
        assets[asset["asset_id"]] = asset
        paths.add(asset["path"])
    _require(_integer(_field(census, "source_files", "census"), "source_files")
             == len(assets), "census source file count mismatch")
    _require(_integer(_field(census, "source_bytes", "census"), "source_bytes")
             == sum(a["bytes"] for a in assets.values()),
             "census source byte count mismatch")
    seen = set()
    result = []
    all_quality = Counter()
    all_regions = Counter()
    region_support = Counter()
    trial_histogram = Counter()
    for record in records:
        _object(record, "census record")
        asset_id = _text(_field(record, "asset_id", "record"), "record asset_id")
        _require(asset_id in assets and asset_id not in seen,
                 "unknown or duplicate census asset_id")
        seen.add(asset_id)
        asset = assets[asset_id]
        for key in ("path", "bytes", "sha256"):
            value = _field(record, key, "record")
            _require(type(value) is type(asset[key]) and value == asset[key],
                     "source identity mismatch for " + asset_id + ": " + key)
        _require(_field(record, "nwb_version", "record") == "2.7.0",
                 "unsupported source NWB metadata version")
        _require(_field(record, "response_array_values_opened", "record") is False,
                 "record is not metadata-only")
        _require(_field(record, "obs_intervals_present", "record") is False,
                 "observation metadata changed; revise the exposure contract")
        identity = _object(_field(record, "identity", "record"), "identity")
        subject = _text(_field(identity, "general/subject/subject_id", "identity"),
                        "record source subject_id")
        _require(subject == asset["subject_id"], "source subject identity mismatch")
        clock = _clock(identity)
        schema = _object(_field(record, "schema", "record"), "schema")
        trials = [_shape_length(schema, "intervals/trials/" + key,
                                MAX_TRIAL_ROWS_PER_ASSET)
                  for key in ("id", "start_time", "stop_time")]
        _require(len(set(trials)) == 1, "trial header row counts disagree")
        trial_count = trials[0]
        trial_histogram[str(trial_count)] += 1
        units = _field(record, "unit_assignments", "record")
        declared_count = _integer(_field(record, "declared_unit_count", "record"),
                                  "declared_unit_count", minimum=1,
                                  maximum=MAX_CLUSTERS_PER_ASSET)
        _require(type(units) is list and len(units) == declared_count,
                 "unit assignment count mismatch")
        _require(_shape_length(schema, "units/spike_times_index",
                               MAX_CLUSTERS_PER_ASSET) == declared_count,
                 "unit index header count mismatch")
        coordinate_support = _object(_field(record, "coordinate_support", "record"),
                                     "coordinate_support")
        electrode_counts = []
        for axis in ("x", "y", "z"):
            electrode_counts.append(_shape_length(coordinate_support, axis, 100000))
        _require(len(set(electrode_counts)) == 1,
                 "electrode coordinate header counts disagree")
        electrode_count = electrode_counts[0]
        region_units = {r: [] for r in (UNASSIGNED_REGION,) + NAMED_REGIONS}
        region_quality = {r: Counter() for r in region_units}
        seen_units = set()
        quality_counts = Counter()
        for unit in units:
            _object(unit, "unit assignment")
            uid = _integer(_field(unit, "unit_id", "unit assignment"), "unit_id")
            _require(uid not in seen_units, "duplicate unit_id within asset")
            seen_units.add(uid)
            _integer(_field(unit, "electrode_row", "unit assignment"),
                     "electrode_row", maximum=electrode_count - 1)
            region = _field(unit, "location_literal", "unit assignment")
            quality = _field(unit, "quality_literal", "unit assignment")
            _require(type(region) is str and region in region_units,
                     "unknown literal region; no normalization or broad-MGN fallback")
            _require(type(quality) is str and quality in SOURCE_QUALITIES,
                     "unknown source quality; source policy requires explicit review")
            region_units[region].append(uid)
            region_quality[region][quality] += 1
            quality_counts[quality] += 1
        region_counts = {r: len(ids) for r, ids in region_units.items() if ids}
        _require(_count_map(_field(record, "source_anatomy_unit_counts", "record"),
                            region_units, "source_anatomy_unit_counts") == region_counts,
                 "declared source anatomy counts disagree with assignments")
        _require(_count_map(_field(record, "source_quality_unit_counts", "record"),
                            SOURCE_QUALITIES, "source_quality_unit_counts")
                 == dict(quality_counts),
                 "declared source quality counts disagree with assignments")
        all_quality.update(quality_counts)
        all_regions.update(region_counts)
        region_support.update(region_counts.keys())
        named = [{"region": r, "cluster_ids": sorted(region_units[r]),
                  "cluster_count": len(region_units[r]),
                  "quality_counts": dict(sorted(region_quality[r].items()))}
                 for r in NAMED_REGIONS if region_units[r]]
        _require(named, "asset has no named source support under the selected policy")
        result.append({
            "asset_id": asset_id,
            "source_subject_id": subject,
            "animal_id": None,
            "source_asset": {k: asset[k] for k in ("path", "bytes", "sha256")},
            "source_trial_rows": trial_count,
            "trial_row_addressing": "zero_based_ordinal_not_source_trial_id",
            "regions": named,
            "unsupported_named_regions": [r for r in NAMED_REGIONS if not region_units[r]],
            "unassigned_cluster_ids": sorted(region_units[UNASSIGNED_REGION]),
            "unassigned_cluster_count": len(region_units[UNASSIGNED_REGION]),
            "unassigned_quality_counts": dict(sorted(region_quality[UNASSIGNED_REGION].items())),
            "clock": clock,
        })
    _require(seen == set(assets), "source asset coverage mismatch")
    summary = {
        "source_file_count": len(result),
        "source_subject_count": len({a["source_subject_id"] for a in result}),
        "source_trial_rows": sum(a["source_trial_rows"] for a in result),
        "source_cluster_count": sum(all_quality.values()),
        "eligible_cluster_count": sum(c["cluster_count"] for a in result for c in a["regions"]),
        "unassigned_cluster_count": all_regions[UNASSIGNED_REGION],
        "nonempty_region_cell_count": sum(len(a["regions"]) for a in result),
        "quality_counts": dict(sorted(all_quality.items())),
        "region_cluster_counts": dict(sorted(all_regions.items())),
        "region_file_support": dict(sorted(region_support.items())),
        "trial_row_count_histogram": dict(sorted(trial_histogram.items())),
    }
    if qualification_profile is not None:
        _check_profile(qualification_profile, summary, source_manifest_sha256)
    return {
        "schema": "neural099-conditional-source-support/v1",
        "source_manifest_sha256": source_manifest_sha256,
        "cluster_policy": "all_source_good_and_mua_with_literal_named_anatomy",
        "cluster_id_scope": "asset_id",
        "support_kind": "categorical_metadata_roster_for_future_preparation",
        "assets": sorted(result, key=lambda a: a["asset_id"]),
        "summary": summary,
        "qualification": {
            "metadata_profile_matched": qualification_profile is not None,
            "trial_values_authenticated": False,
            "biological_identity_reverified": False,
            "observation_coverage_verified": False,
            "scientific_protocol_bound": False,
            "ready_for_scoring": False,
        },
    }
