"""Owner-only exact Helsinki v4 recorded-grid identity; no fixture admission."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from types import MappingProxyType

PROTOCOL_ID = "helsinki_recorded_grid_quality_flags_v2"
COORDINATE_ID = "author_exported_record_sample_grid_v1"
FORMAT_PROFILE_ID = "helsinki_v4_fixed_record_export_compat_v1"
CSV_PROFILE_ID = "mandatory_study_id_header_1_to_79_v1"
PINS = MappingProxyType({
    "release_manifest.json": "84ad5381159c34a592a8177b2d2b2b03d6dc3a352a1e8e566201f5cd40f8aa8a",
    "HEADER_SOURCE_EXPECTATIONS.json": "2de359fbe43307261d03677a7a35682d4bb72e9b81b24c8f53832a86b3e31c67",
    "SOURCE_EXCEPTION_ALLOWLIST.json": "15a78c9f6e17ca17e9168186d94b1049c934f197db645ebbffdda1901122a160",
    "ANNOTATION_LAYOUT_PROFILE.json": "6758b1c968b67059e737c19422766ea39518d885be087a9d711917dda0b06778",
})


class Refusal(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise Refusal("noncanonical_profile_or_lineage") from exc


@lru_cache(maxsize=1)
def source_code_identity():
    """Capture immutable code-version hashes; the trusted launcher pins this source tree.

    This identifies this process's selected owner source version, not a sandbox.
    Production hosts must mount the selected owner source read-only.
    """
    digests = {}
    for name in ("helsinki_profile.py", "helsinki_intake.py", "helsinki_protocol.py", "helsinki_score.py", "helsinki_fixture.py"):
        path = Path(__file__).parent / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576,
                "source_module_file_type_or_size")
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return MappingProxyType(digests)


def profile_identity():
    identity = {"schema": "helsinki_recorded_grid_profile_v2", "protocol_id": PROTOCOL_ID,
        "coordinate_id": COORDINATE_ID, "format_profile_id": FORMAT_PROFILE_ID,
        "csv_profile_id": CSV_PROFILE_ID, "source_profile_pins": dict(PINS),
        "owner_source_module_sha256": dict(source_code_identity())}
    identity["profile_sha256"] = hashlib.sha256(_canonical(identity)).hexdigest()
    return identity


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    return value


@lru_cache(maxsize=1)
def source_profiles():
    """Authenticate exact public profiles once; nested values are immutable."""
    result = {}
    for name, expected in PINS.items():
        path = Path(__file__).parent / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576,
                "profile_file_type_or_size")
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == expected, "source_profile_pin_mismatch")
        result[name] = json.loads(raw)
    headers = result["HEADER_SOURCE_EXPECTATIONS.json"]["members"]
    exceptions = result["SOURCE_EXCEPTION_ALLOWLIST.json"]["exceptions"]
    csv = result["ANNOTATION_LAYOUT_PROFILE.json"]
    manifest = result["release_manifest.json"]
    require(manifest["record_id"] == 4940267 and manifest["version"] == "v4", "wrong_release_profile")
    require(len(headers) == 79 and {r["study_id"] for r in headers} == set(range(1, 80)),
            "header_profile_census")
    require(len(exceptions) == 3 and {r["study_id"] for r in exceptions} == {4, 29, 50},
            "exception_profile_census")
    require(csv["mandatory_first_record"] == list(map(str, range(1, 80))) and
            csv["data_records"] == 15416 and csv["outside_duration_lexeme"] == "", "csv_profile_schema")
    return _freeze({"headers": {r["study_id"]: r for r in headers},
        "exceptions": {r["study_id"]: r for r in exceptions},
        "annotations": {r["name"]: r for r in csv["expert_sources"]},
        "manifest": {r["name"]: r for r in manifest["files"]}, "csv": csv})


def complete_support():
    return {"schema": "helsinki_complete_recorded_grid_support_v2", "infants": 79,
        "experts": 3, "record_seconds": 402825, "primary_cases": 400534,
        "annotation_data_records": 15416, "annotation_header_records": 1,
        "complete_waveforms_authenticated": True, "all_three_streams_validated": True}


def validate_lineage(lineage):
    """Schema/identity validation, not a substitute for full trusted Corpus intake."""
    require(type(lineage) is dict and set(lineage) == {
        "manifest_sha256", "assets", "headers", "durations", "profile", "support"},
        "incomplete_or_foreign_recorded_grid_lineage")
    require(all(type(lineage[k]) is dict for k in ("assets", "headers", "durations", "profile", "support")),
            "invalid_lineage_container_types")
    require(_canonical(lineage["profile"]) == _canonical(profile_identity()) and
            _canonical(lineage["support"]) == _canonical(complete_support()) and
            lineage["manifest_sha256"] == PINS["release_manifest.json"], "recorded_grid_profile_or_support_mismatch")
    profiles = source_profiles()
    require(set(lineage["assets"]) == set(profiles["manifest"]), "lineage_asset_census")
    require(all(type(v) is str and len(v) == 64 and set(v) <= set("0123456789abcdef")
                for v in lineage["assets"].values()), "lineage_full_asset_sha_format")
    require(lineage["headers"] == {str(i): r["observed_header_sha256"] for i, r in profiles["headers"].items()} and
            lineage["durations"] == {str(i): r["declared_records"] for i, r in profiles["headers"].items()},
            "lineage_header_or_record_grid_changed")
    require(all(lineage["assets"][n] == r["actual_sha256"] for n, r in profiles["annotations"].items()),
            "lineage_expert_sources_changed")
    return lineage
