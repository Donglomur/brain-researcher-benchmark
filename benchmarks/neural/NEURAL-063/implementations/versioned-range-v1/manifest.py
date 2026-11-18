"""Compile saved fixed-version HEAD custody; never contact a provider."""
import base64
from collections import Counter
import email.parser
import hashlib
import json
from pathlib import Path
from urllib.parse import quote
from range_io import Asset, RangeContractError, canonical, one

SELECTION_BYTES = 9605316
SELECTION_SHA256 = "d484ac018c7b7a0cc9ed826de5977a9ec9724a82e68126ec7e13be23507c1ab7"
EXTENTS_BYTES = 1781016
EXTENTS_SHA256 = "941ca6a8f81f0d97a465cdde06bc548cd5af2c7b320bd1dec30cf5ccdc54f282"
EXPECTED = {"experiments": 1936, "mice": 107, "sessions": 703, "rois": 133066}
SPLITS = {"fit": 73, "validation": 15, "query": 19}


def unique_json(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise RangeContractError("duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise RangeContractError("nonfinite JSON")
    return json.loads(body, object_pairs_hook=pairs, parse_constant=invalid)


def read_pin(path, count, sha256):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size != count:
        raise RangeContractError("wrong named metadata input")
    body = p.read_bytes()
    if len(body) != count or hashlib.sha256(body).hexdigest() != sha256:
        raise RangeContractError("named metadata pin mismatch")
    return unique_json(body)


def full_scope(selection):
    rows = selection["experiments"]
    if (len(rows) != EXPECTED["experiments"] or
            len({r["ophys_experiment_id"] for r in rows}) != EXPECTED["experiments"] or
            len({r["mouse_id"] for r in rows}) != EXPECTED["mice"] or
            len({r["ophys_session_id"] for r in rows}) != EXPECTED["sessions"] or
            sum(len(r["rois"]) for r in rows) != EXPECTED["rois"]):
        raise RangeContractError("complete original cohort required")
    assignments = selection["mouse_assignments"]
    if Counter(assignments.values()) != SPLITS or set(assignments) != {r["mouse_id"] for r in rows}:
        raise RangeContractError("complete original mouse split required")
    if any(r["split"] != assignments[r["mouse_id"]] for r in rows):
        raise RangeContractError("plane/mouse split mismatch")
    sessions = {}
    for row in rows:
        sid, mid = row["ophys_session_id"], row["mouse_id"]
        if sessions.setdefault(sid, mid) != mid:
            raise RangeContractError("session assigned to multiple mice")
    return rows


def saved_asset(row, entry, record):
    eid = row["ophys_experiment_id"]
    target = entry["target"]
    if (target != record["target"] or target["experiment"] != eid or
            target["mouse_id"] != row["mouse_id"] or target["split"] != row["split"] or
            target["url"] != row["url"] or target["version_id"] != row["version_id"] or
            target["blake2b_512"] != row["blake2b_512"]):
        raise RangeContractError("original selection / saved HEAD identity mismatch")
    if (record["status"] != "observed_HEAD_extent" or record["curl_exit_code"] != 0 or
            record["body_requested"] is not False or record["full_object_hash_verified"] is not False):
        raise RangeContractError("successful metadata-only HEAD required")
    raw = base64.b64decode(record["headers_raw_base64"], validate=True)
    if len(raw) != record["header_bytes_captured"] or len(raw) >= 16384:
        raise RangeContractError("saved header extent mismatch")
    first, headers = raw.split(b"\r\n", 1)
    if first != b"HTTP/1.1 200 OK" or not headers.endswith(b"\r\n\r\n") or b"\r\n\r\n" in headers[:-4]:
        raise RangeContractError("one complete successful saved response required")
    h = email.parser.BytesParser().parsebytes(headers)
    extent = entry["extent_bytes"]
    if (one(h, "Content-Length") != str(extent) or
            one(h, "x-amz-version-id") != row["version_id"] or
            one(h, "Content-Encoding", optional=True) not in (None, "identity")):
        raise RangeContractError("saved HEAD response identity mismatch")
    url = row["url"] + "?versionId=" + quote(row["version_id"], safe="")
    status = record["curl_status"]
    if (status["url_effective"] != url or status["http_code"] != "200" or status["num_redirects"] != "0"
            or status["ssl_verify_result"] != "0" or status["exitcode"] != "0" or status["size_download"] != "0"):
        raise RangeContractError("saved exact URL/status mismatch")
    asset = Asset(eid, url, row["version_id"], one(h, "ETag"), extent, row["blake2b_512"]).validate()
    return {**vars(asset), "session": row["ophys_session_id"], "mouse": row["mouse_id"],
            "split": row["split"], "head_receipt": entry["attempt"],
            "accept_ranges_advertised": one(h, "Accept-Ranges", optional=True) == "bytes",
            "full_object_BLAKE2b_verified": False}


def build(selection_path, index_path):
    wrapped = read_pin(selection_path, SELECTION_BYTES, SELECTION_SHA256)
    selection = wrapped["original_selection"]
    rows = full_scope(selection)
    index = read_pin(index_path, EXTENTS_BYTES, EXTENTS_SHA256)
    entries = {e["target"]["experiment"]: e for e in index["entries"]}
    if (len(entries) != 1936 or len(index["entries"]) != 1936 or
            set(entries) != {r["ophys_experiment_id"] for r in rows} or
            index["resolved_targets"] != 1936 or index["unresolved_experiments"]):
        raise RangeContractError("complete saved extent index required")
    assets = []
    parent = Path(index_path).parent
    for row in rows:
        entry = entries[row["ophys_experiment_id"]]
        ref = entry["attempt"]
        name = ref["path"]
        if Path(name).parts != ("attempts", row["ophys_experiment_id"] + ".1.json") or ref["bytes"] > 32768:
            raise RangeContractError("unexpected saved attempt path/extent")
        record = read_pin(parent / name, ref["bytes"], ref["sha256"])
        assets.append(saved_asset(row, entry, record))
    if sum(a["extent_bytes"] for a in assets) != 855657138152:
        raise RangeContractError("original total extent mismatch")
    return {"schema": "neural063_versioned_range_assets_v1", "assets": assets,
            "selection_sha256": SELECTION_SHA256, "extent_index_sha256": EXTENTS_SHA256,
            "source_counts": EXPECTED, "mouse_splits": SPLITS,
            "full_object_BLAKE2b_verified": False,
            "custody": "Saved HEAD identity only; actual ranges and scientific equivalence remain unqualified"}


def validate_assets(manifest, selection):
    rows = full_scope(selection)
    if (manifest.get("schema") != "neural063_versioned_range_assets_v1" or
            manifest.get("selection_sha256") != SELECTION_SHA256 or
            manifest.get("extent_index_sha256") != EXTENTS_SHA256 or
            manifest.get("full_object_BLAKE2b_verified") is not False or
            manifest.get("source_counts") != EXPECTED or manifest.get("mouse_splits") != SPLITS):
        raise RangeContractError("wrong alternative source manifest")
    values = manifest["assets"]
    bank = {v["experiment"]: v for v in values}
    if len(values) != 1936 or len(bank) != 1936 or set(bank) != {r["ophys_experiment_id"] for r in rows}:
        raise RangeContractError("complete unique asset join required")
    result = {}
    for row in rows:
        value = bank[row["ophys_experiment_id"]]
        asset = Asset(**{k: value[k] for k in Asset.__dataclass_fields__}).validate()
        if (value["session"] != row["ophys_session_id"] or value["mouse"] != row["mouse_id"] or
                value["split"] != row["split"] or asset.version_id != row["version_id"] or
                asset.provider_blake2b != row["blake2b_512"] or
                asset.url != row["url"] + "?versionId=" + quote(row["version_id"], safe="")):
            raise RangeContractError("alternative asset changes original identity")
        result[asset.experiment] = asset
    return result
