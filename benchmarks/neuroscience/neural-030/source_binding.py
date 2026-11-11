"""Declared source-identity contract; this validator does not certify authenticity."""
import hashlib
import re

SOURCE_SHA256 = "822e47a83f84e647e4f9571832f920663009e73bd2814d4118331d99792f4147"
SOURCE_BYTES = 807474431
SOURCE_FILE_ID = 3224109
SOURCE_VERSION = 298774
SOURCE_COMMIT = "124c83e1af83e9680e05f9827448579d02345fa3"
GROUPS = {1: ("one_second_expert", 1.0, 5),
          2: ("two_second_novice", 2.0, 5),
          3: ("two_second_expert", 2.0, 6)}


class Refusal(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Refusal(reason)


def closed(value, keys, reason):
    require(type(value) is dict and set(value) == set(keys), reason)


def text(value, reason):
    require(type(value) is str and 0 < len(value) <= 1024 and "\0" not in value, reason)
    return value


def digest(value, reason):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, reason)
    return value


def evidence(value):
    closed(value, ("artifact_sha256", "source_field_path", "description"), "identity_evidence_fields")
    digest(value["artifact_sha256"], "identity_evidence_hash")
    text(value["source_field_path"], "identity_evidence_source_path")
    text(value["description"], "identity_evidence_description")


def opaque(kind, value):
    return hashlib.sha256((kind + "\0" + value).encode("utf8")).hexdigest()[:32]


def validate_binding(binding):
    closed(binding, ("schema", "source_asset", "source_revision", "sessions", "evidence"), "binding_fields")
    require(binding["schema"] == "neural030_cerebellar_binding_v1", "binding_schema")
    asset = binding["source_asset"]
    closed(asset, ("file_id", "version", "bytes", "sha256"), "asset_fields")
    require(all(type(asset[k]) is int for k in ("file_id", "version", "bytes")), "asset_integer_types")
    require(asset == {"file_id": SOURCE_FILE_ID, "version": SOURCE_VERSION,
                      "bytes": SOURCE_BYTES, "sha256": SOURCE_SHA256}, "exact_source_asset")
    require(binding["source_revision"] == SOURCE_COMMIT, "exact_reference_revision")
    evidence(binding["evidence"])
    require(type(binding["sessions"]) is list and len(binding["sessions"]) == 16, "complete_16_sessions")
    by_position, session_ids, acquisition_ids, mouse_ids = {}, set(), set(), set()
    for row in binding["sessions"]:
        closed(row, ("group", "record", "mouse_id", "session_id", "acquisition_id", "identity_evidence"), "session_identity_fields")
        g, i = row["group"], row["record"]
        require(type(g) is int and g in GROUPS and type(i) is int and 1 <= i <= GROUPS[g][2], "source_position")
        require((g, i) not in by_position, "duplicate_source_position")
        for name in ("mouse_id", "session_id", "acquisition_id"):
            text(row[name], name)
        evidence(row["identity_evidence"])
        require(row["session_id"] not in session_ids, "duplicate_session_identity")
        require(row["acquisition_id"] not in acquisition_ids, "duplicate_acquisition_identity")
        session_ids.add(row["session_id"])
        acquisition_ids.add(row["acquisition_id"])
        mouse_ids.add(row["mouse_id"])
        by_position[(g, i)] = dict(row)
    expected = {(g, i) for g in GROUPS for i in range(1, GROUPS[g][2] + 1)}
    require(set(by_position) == expected, "complete_group_5_5_6_inverse")
    require(len(mouse_ids) == 5, "five_declared_mice_required")
    # Group-local indices are never used as animal identities. Authentic field
    # extraction and evidence custody remain a separate, currently closed gate.
    return by_position
