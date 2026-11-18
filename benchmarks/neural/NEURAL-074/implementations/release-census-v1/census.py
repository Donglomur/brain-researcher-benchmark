"""NEURAL-074 declared-case census against a pinned, saved NeuroVault snapshot.

Operator metadata only: no neural payloads, fitting, selected support, or input
custody are issued. A unique FFX metadata candidate is not an admitted map.
"""
from collections import Counter, defaultdict
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import stat

SCHEMA = "neural074-release-census/v1"
MAX_METADATA_BYTES = 24 * 1024 * 1024
MAX_PAGE_BYTES = 3 * 1024 * 1024
MAX_OUTPUT_BYTES = 128 * 1024
TASK_TO_API = {
    "ArchiStandard": "archi_standard", "ArchiSpatial": "archi_spatial",
    "ArchiSocial": "archi_social", "ArchiEmotional": "archi_emotional",
    "HcpLanguage": "hcp_language", "HcpSocial": "hcp_social",
    "HcpGambling": "hcp_gambling", "HcpMotor": "hcp_motor",
    "HcpEmotion": "hcp_emotion", "HcpRelational": "hcp_relational",
    "HcpWm": "hcp_wm", "RSVPLanguage": "rsvp_language",
}
NAME = re.compile(r"^(sub-[0-9]+)_(ses-[0-9]+)_task-([a-z_]+)_(dir-ap|dir-pa|ffx)_(?:run-([0-9]+)_)?(.+)$")
HEX = re.compile(r"[0-9a-f]{64}\Z")


class CensusError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise CensusError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(CensusError("Nonfinite JSON")))


def read_pinned(path, extent, digest, maximum):
    require(type(extent) is int and 0 < extent <= maximum, "Unbounded selected metadata extent")
    require(type(digest) is str and HEX.fullmatch(digest), "Invalid selected SHA256")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_size == extent, "Selected metadata is not an exact regular file")
    with path.open("rb") as handle:
        body = handle.read(extent + 1)
    require(len(body) == extent, "Selected metadata changed extent")
    require(hashlib.sha256(body).hexdigest() == digest, "Selected metadata SHA256 mismatch")
    return body


def read_catalogue(body):
    """Extract the two literal declarations without importing author/operator code."""
    values = {}
    for node in ast.parse(body).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in ("DECLARED_PEOPLE", "DECLARED_ENDPOINTS"):
                require(name not in values, "Duplicate catalogue declaration")
                values[name] = ast.literal_eval(node.value)
    require(set(values) == {"DECLARED_PEOPLE", "DECLARED_ENDPOINTS"}, "Missing literal catalogue declarations")
    return values["DECLARED_PEOPLE"], values["DECLARED_ENDPOINTS"]


def census(records, people, endpoints, expected_records):
    """Preserve all 663 cells, retaining every FFX candidate and AP/PA counts.

    records yields (metadata page index, zero-based source row, original row).
    Explicit task aliases are not a cognitive-family taxonomy. No task labels
    or metadata in this report belong in a participant-facing query packet.
    """
    require(type(people) is tuple and len(people) == 13 and len(set(people)) == 13,
            "Expected the complete 13-person declaration")
    require(type(endpoints) is tuple and len(endpoints) == 51 and len(set(endpoints)) == 51,
            "Expected the complete 51-endpoint declaration")
    require(all(type(e) is tuple and len(e) == 3 and all(type(x) is str for x in e) for e in endpoints),
            "Invalid declared endpoint row")
    require(len({e[0] for e in endpoints}) == 51 and {e[1] for e in endpoints} == set(TASK_TO_API),
            "Incomplete or ambiguous endpoint catalogue")
    require(type(expected_records) is int and 0 < expected_records <= 10000, "Unbounded source record count")
    expected = {(TASK_TO_API[task], contrast): i for i, (_, task, contrast) in enumerate(endpoints)}
    require(len(expected) == 51, "Endpoint aliases collapse distinct cases")
    person_index = {person: i for i, person in enumerate(people)}
    selected = defaultdict(lambda: defaultdict(list))
    seen = set()
    ignored = Counter()
    for page, row_number, row in records:
        require(type(page) is int and page >= 0 and type(row_number) is int and row_number >= 0,
                "Invalid source locator")
        require(type(row) is dict and type(row.get("id")) is int and row["id"] > 0,
                "Missing source image identity")
        require(row["id"] not in seen, "Duplicate source image identity")
        seen.add(row["id"])
        require(len(seen) <= expected_records, "Snapshot exceeds declared source count")
        require(row.get("collection_id") == 6618, "Mixed NeuroVault collections")
        if row.get("task") not in TASK_TO_API.values():
            ignored["outside_declared_tasks"] += 1
            continue
        if row.get("subject_id") not in person_index:
            ignored["outside_declared_people"] += 1
            continue
        name = NAME.fullmatch(row.get("name", ""))
        require(name is not None, "Relevant source row has an unrecognized name; cannot infer absence")
        person, session, task, direction, run_id, contrast = name.groups()
        require(not contrast.startswith("run-"), "Unrecognized run tag; cannot infer endpoint absence")
        require(person == row["subject_id"] and task == row["task"], "Name/metadata identity disagreement")
        if (task, contrast) not in expected:
            ignored["outside_declared_contrasts"] += 1
            continue
        require(row.get("map_type") == "Z map" and row.get("analysis_level") == "single-subject"
                and row.get("modality") == "fMRI-BOLD" and row.get("data_origin") == "volume"
                and row.get("is_thresholded") is False and row.get("number_of_subjects") == 1,
                "Relevant row does not describe the selected statistical-map construction")
        require(type(row.get("is_valid")) is bool, "Missing platform validity flag")
        require(type(row.get("file_size")) is int and row["file_size"] > 0, "Missing advertised payload extent")
        key = person_index[person], expected[task, contrast]
        selected[key][direction].append((row["id"], session, run_id, row["is_valid"], row["file_size"], page, row_number))
    require(len(seen) == expected_records, "Incomplete source snapshot")
    cells = []
    counts = Counter()
    total_ffx = 0
    for p in range(13):
        for e in range(51):
            directions = selected[p, e]
            ffx = sorted(directions["ffx"])
            status = ("no_ffx_candidate" if not ffx else
                      "one_metadata_ffx_candidate" if len(ffx) == 1 else "multiple_metadata_ffx_candidates")
            counts[status] += 1
            candidates = []
            for candidate in ffx:
                session_run = candidate[1:3]
                candidates.append(list(candidate) + [sum(r[1:3] == session_run for r in directions["dir-ap"]),
                                                       sum(r[1:3] == session_run for r in directions["dir-pa"])])
            cells.append([p, e, status, candidates, len(directions["dir-ap"]), len(directions["dir-pa"])])
            total_ffx += len(ffx)
    return {
        "schema": SCHEMA,
        "scope": "operator_only_saved_metadata_census_not_selected_map_population",
        "people": people, "endpoints": endpoints, "explicit_task_aliases": TASK_TO_API,
        "cell_columns": ["person_index", "endpoint_index", "ffx_metadata_status", "ffx_candidates",
                         "ap_candidates_count", "pa_candidates_count"],
        "ffx_candidate_columns": ["image_id", "session", "run_id", "platform_is_valid", "advertised_bytes",
                                  "source_page_index", "source_row0", "same_session_run_ap_count", "same_session_run_pa_count"],
        "cells": cells, "counts": dict(counts), "declared_cases": len(cells),
        "source_records": len(seen), "ignored_non_target_rows": dict(ignored),
        "ffx_metadata_candidates": total_ffx,
        "content_sha256s_verified": False, "neural_arrays_read": 0, "readiness_promoted": False,
        "limitations": [
            "Metadata presence does not qualify neural content, geometry, biological units or input custody.",
            "All FFX session/run records remain candidates; repetitions are not silently averaged or selected.",
            "AP/PA counts describe metadata matches, not numerical fixed-effects provenance.",
            "Platform is_valid=False is preserved without automatic exclusion or approval.",
            "Explicit task aliases do not establish a cognitive-family/dependency taxonomy.",
            "No exact identifier match does not prove absence of a differently named semantic equivalent.",
            "Snapshot collection6618 is not asserted equivalent to accessionds000244 or later IBC releases.",
        ],
    }


def run(snapshot_root, inventory_path, inventory_sha256, catalogue_path, catalogue_sha256, output):
    inventory_body = read_pinned(inventory_path, inventory_path.stat().st_size, inventory_sha256, 32768)
    inventory = decode(inventory_body)
    pages = inventory["inventory_pages"]
    require(type(pages) is list and 1 <= len(pages) <= 32, "Unbounded page roster")
    require(sum(p["bytes"] for p in pages) <= MAX_METADATA_BYTES, "Selected metadata exceeds read bound")
    require(len({p["path"] for p in pages}) == len(pages), "Duplicate page path")
    catalogue_body = read_pinned(catalogue_path, catalogue_path.stat().st_size, catalogue_sha256, 32768)
    people, endpoints = read_catalogue(catalogue_body)
    root = snapshot_root.resolve(strict=True)
    def records():
        for index, pin in enumerate(pages):
            relative = Path(pin["path"])
            require(not relative.is_absolute() and ".." not in relative.parts, "Unsafe selected metadata path")
            path = root / relative
            require(path.resolve(strict=True).is_relative_to(root), "Selected page escapes snapshot root")
            page = decode(read_pinned(path, pin["bytes"], pin["sha256"], MAX_PAGE_BYTES))
            require(page["count"] == inventory["collection_reported_rows"], "Source page count disagrees")
            require(type(page["results"]) is list and len(page["results"]) == pin["rows"], "Source page row count disagrees")
            for row_number, row in enumerate(page["results"]):
                yield index, row_number, row
    result = census(records(), people, endpoints, inventory["collection_reported_rows"])
    result["source_binding"] = {
        "inventory_sha256": inventory_sha256, "catalogue_sha256": catalogue_sha256,
        "pages": pages, "snapshot_metadata_bytes": sum(p["bytes"] for p in pages),
        "meaning": "Saved metadata body identities verified against the independently supplied inventory pin; no payload authentication.",
    }
    data = (json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    require(len(data) <= MAX_OUTPUT_BYTES, "Census output exceeds the selected evidence bound")
    with output.open("xb") as handle:
        handle.write(data)
    return {"counts": result["counts"], "declared_cases": result["declared_cases"],
            "ffx_metadata_candidates": result["ffx_metadata_candidates"],
            "output_bytes": len(data), "output_sha256": hashlib.sha256(data).hexdigest(),
            "metadata_bytes_read": len(inventory_body) + len(catalogue_body) + sum(p["bytes"] for p in pages)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot-root", type=Path, required=True)
    p.add_argument("--inventory", type=Path, required=True)
    p.add_argument("--inventory-sha256", required=True)
    p.add_argument("--catalogue", type=Path, required=True)
    p.add_argument("--catalogue-sha256", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(run(args.snapshot_root, args.inventory, args.inventory_sha256,
                         args.catalogue, args.catalogue_sha256, args.out), sort_keys=True))


if __name__ == "__main__":
    main()
