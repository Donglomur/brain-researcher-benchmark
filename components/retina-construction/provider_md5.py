"""Validate declared provider-MD5 metadata for the complete frozen retina release.

This is additive to the unchanged SHA256-only contract. Supplying plausible
digests does not authenticate their provenance or verify any received payload.
"""
import copy
import re

from retina_contract import (ARCHIVES, BASE_URL, DATA_COMMIT, DATA_DOI,
                             closed, digest, positive_int, require)

LAST_CHANGE_COMMIT = "4cdeedc2e55ee84a8a8fa3b73ac6288eed5bcc9d"
MD5_HEX = re.compile(r"[0-9a-f]{32}\Z")


def validate_provider_md5_manifest(value):
    closed(value, ("schema", "data_doi", "data_commit", "last_change_commit",
                   "provider_metadata_sha256", "archives"), "provider_release")
    require(value["schema"] == "retina-provider-md5-intake-v1", "provider_release:schema_name")
    require(value["data_doi"] == DATA_DOI and value["data_commit"] == DATA_COMMIT,
            "provider_release:identity")
    require(value["last_change_commit"] == LAST_CHANGE_COMMIT, "provider_release:last_change")
    digest(value["provider_metadata_sha256"], "provider_release:metadata")
    require(type(value["archives"]) is list and len(value["archives"]) == 18,
            "provider_release:all18")
    seen = {}
    for row in value["archives"]:
        closed(row, ("name", "bytes", "provider_md5", "git_annex_key",
                     "metadata_evidence_sha256"), "provider_archive")
        name = row["name"]
        require(type(name) is str and name in ARCHIVES, "provider_archive:roster")
        require(name not in seen, "provider_archive:duplicate")
        positive_int(row["bytes"], "provider_archive")
        require(type(row["provider_md5"]) is str and MD5_HEX.fullmatch(row["provider_md5"]),
                "provider_archive:md5")
        expected_key = f'MD5-s{row["bytes"]}--{row["provider_md5"]}'
        require(row["git_annex_key"] == expected_key, "provider_archive:key_size_or_digest")
        digest(row["metadata_evidence_sha256"], "provider_archive:metadata")
        seen[name] = copy.deepcopy(row)
    require(set(seen) == set(ARCHIVES), "provider_release:all18")
    rows = [dict(seen[name], url=BASE_URL + name) for name in ARCHIVES]
    total = sum(row["bytes"] for row in rows)
    return {
        "schema": "retina-provider-md5-acquisition-plan-v1",
        "data_commit": DATA_COMMIT, "archives": rows, "integrity_mode": "provider_md5_observed_sha256",
        "total_archive_bytes": total, "maximum_observed_entity_bytes": total + 18,
        "requested_read_admission_bytes": 2 * total + 18 * 1048576,
        "maximum_retained_archive_bytes": total + 18,
        "metadata_authority_verified": False, "provider_payload_verified": False,
        "provider_sha256_available": False, "archive_extraction_selected": False,
        "scientific_qualification": False,
    }
