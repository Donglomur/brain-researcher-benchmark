"""Complete35 canonical HEAD metadata contract. No request or body read."""
import re
from urllib.parse import urljoin, urlsplit

TASK = "PAPER-CANDIDATE-20261114-CONSENSUS"
ANIMALS = ("MPV17_FB_5", "MPV18_FB_5", "MPV31_FF_5", "MPV33_FF_5",
           "MPV34_FF_5", "VL63_FF_5", "VL66_FB_5")
STEMS = {"all_lm_cells.npy", "all_v1_cells.npy", "all_times.npy",
         "stim_times.npy", "unique_ids.npy"}
REDIRECTS = {301, 302, 303, 307, 308}


def need(ok, why):
    if not ok:
        raise ValueError(why)


def validate_operands(document):
    need(document["schema"] == "consensus_complete35_header_operands_v1"
         and document["candidate_id"] == TASK
         and document["execution_authority"] is False, "exact inert complete operand contract")
    rows = document["files"]
    need(type(rows) is list and len(rows) == 35, "complete35 roster")
    ids, paths, expected = set(), set(), {a + "/" + s for a in ANIMALS for s in STEMS}
    for i, row in enumerate(rows):
        need(row["index"] == i and type(row["file_id"]) is int
             and row["file_id"] > 0 and row["file_id"] not in ids, "unique exact file order")
        need(row["relative_path"] in expected and row["relative_path"] not in paths
             and row["animal_id"] == row["relative_path"].split("/")[0], "complete seven-by-five")
        need(row["canonical_download_url"] ==
             "https://ndownloader.figshare.com/files/" + str(row["file_id"]),
             "canonical retained publisher URL")
        need(type(row["bytes"]) is int and row["bytes"] > 12
             and re.fullmatch("[a-f0-9]{32}", row["published_computed_md5"]),
             "retained extent and provider checksum metadata")
        need(row["current_entity_url"] is None and row["current_strong_etag"] is None
             and row["whole_original_sha256"] is None, "no invented current identity")
        ids.add(row["file_id"]); paths.add(row["relative_path"])
    need(paths == expected and sum(r["bytes"] for r in rows) == 1005824688,
         "complete original35 extent")
    return rows


def values(headers, name):
    return [v for k, v in headers if k.lower() == name.lower()]


def classify(row, status, response_url, headers):
    """Describe observed route metadata; this never authorizes a redirect or GET.

    Non-success status, weak/missing ETag or malformed redirect remain complete
    bounded observations when transport/framing/closure succeeded.
    """
    need(type(status) is int and 100 <= status <= 599, "HTTP response status")
    need(response_url == row["canonical_download_url"], "no followed or changed URL")
    need(type(headers) is list and len(headers) <= 100
         and all(type(x) in (list, tuple) and len(x) == 2
                 and all(type(v) is str for v in x) for x in headers),
         "complete bounded header pairs")
    names = ("ETag", "Content-Length", "Accept-Ranges", "Content-Encoding",
             "Transfer-Encoding", "Content-Range", "Location")
    observed = {name: values(headers, name) for name in names}
    duplicate = [name for name in names if len(observed[name]) > 1]
    def single(name):
        return observed[name][0] if len(observed[name]) == 1 else None
    etag = single("ETag")
    strong = bool(type(etag) is str and re.fullmatch(r'"[\x21\x23-\x7e]+"', etag))
    out = {"index": row["index"], "file_id": row["file_id"],
           "relative_path": row["relative_path"], "declared_bytes": row["bytes"],
           "canonical_url": row["canonical_download_url"], "response_url": response_url,
           "status": status, "observed_fields": observed,
           "duplicate_identity_headers": duplicate,
           "route_kind": "unresolved_status", "observed_strong_etag": etag if strong else None,
           "etag_scope": "canonical-response-only",
           "direct_entity_metadata_compatible": False,
           "redirect_target": None, "redirect_follow_authorized": False,
           "header_range_authorized": False, "whole_file_checksum_verified": False}
    if duplicate:
        out["route_kind"] = "ambiguous_headers"
        return out
    if status == 200:
        compatible = (strong and single("Content-Length") == str(row["bytes"])
                      and single("Accept-Ranges") == "bytes"
                      and single("Content-Encoding") in (None, "identity")
                      and single("Transfer-Encoding") is None
                      and single("Content-Range") is None
                      and single("Location") is None)
        out["route_kind"] = "direct_entity_metadata" if compatible else "incompatible_direct_metadata"
        out["direct_entity_metadata_compatible"] = compatible
        if compatible:
            out["etag_scope"] = "direct-canonical-entity-only"
        return out
    if status in REDIRECTS:
        location = single("Location")
        out["route_kind"] = "unresolved_redirect"
        if type(location) is str and 0 < len(location) <= 2048 and not any(
                ord(c) < 32 or ord(c) == 127 for c in location):
            target = urljoin(response_url, location)
            try:
                p = urlsplit(target)
                safe = (p.scheme == "https" and p.hostname and p.username is None
                        and p.password is None and not p.fragment
                        and p.port in (None, 443) and len(target) <= 2048)
            except ValueError:
                safe = False
            if safe:
                out["route_kind"] = "observed_https_redirect"
                out["redirect_target"] = target
                out["etag_scope"] = "redirect-response-not-target-entity"
        return out
    return out


def complete(rows, observations):
    need(len(rows) == len(observations) == 35, "all35 closed observations required")
    for row, value in zip(rows, observations):
        need(value["index"] == row["index"] and value["file_id"] == row["file_id"]
             and value["relative_path"] == row["relative_path"]
             and value["declared_bytes"] == row["bytes"]
             and value["response_closed"] is True
             and value["body_read_called"] is False
             and value["returned_entity_bytes"] == 0,
             "exact full original identity, closed response and zero body read")
    return {"schema": "consensus_complete35_head_observations_v1", "candidate_id": TASK,
            "complete_observations": True, "objects": 35, "animals": 7,
            "declared_original_bytes": 1005824688,
            "direct_metadata_count": sum(v["direct_entity_metadata_compatible"] for v in observations),
            "observed_https_redirect_count": sum(v["route_kind"] == "observed_https_redirect"
                                                  for v in observations),
            "observations": observations, "returned_entity_bytes": 0,
            "target_routes_approved": False, "header_ranges_authorized": False,
            "native_geometry_observed": False, "scientific_readiness": False}
