"""Join both complete ZIP directories to all 49 public FUS roster rows.

No member bytes are read. This establishes filename candidates only. The caller
must retain the original complete directory results and authenticate transport.
"""
import hashlib
import json
from pathlib import PurePosixPath
import re

_DOPPLER = re.compile(r"doppler(?:Continuous)?_S([0-9]+)_R([0-9]+)(?:_allTrials)?(?:\+normcorre)?\.mat")
_SCHEMA_NAMES = {"DescriptionOfFiles.pdf", "DescriptionOfVariables.pdf"}
_ASSET_DIGEST = "934d1ecff61223e11e16e82b65c2840ef22cb71e52020a4b1ae65ad6dfe8ea01"
_ROSTER_DIGEST = "0dc8fcb3ee86958e0c12863cfc0c5432b86b1629f40aac1a2c9ab0f97a9576f9"


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def join_complete_directories(directories, assets, roster):
    """Return every roster row, every matching member and all other MAT names.

    Inputs are metadata dictionaries. Exactly two asset identities and exactly
    49 public roster rows are required. Missing or ambiguous forms are reported,
    never replaced by another member; zero-count rows are not dropped.
    """
    if type(directories) is not list or len(directories) != 2 or len(assets) != 2:
        raise ValueError("complete two-archive inventory required")
    if _digest(assets) != _ASSET_DIGEST or _digest(roster) != _ROSTER_DIGEST:
        raise ValueError("exact public asset/roster selection changed")
    expected = {a["file_id"]: a for a in assets}
    if len(expected) != 2 or {a["role"] for a in assets} != {"current", "upstream_rt"}:
        raise ValueError("two distinct current/upstream asset identities required")
    if len(roster) != 49 or len({r["record_id"] for r in roster}) != 49:
        raise ValueError("complete 49-record public roster required")
    if ({r["animal"] for r in roster} != {"L", "P"}
            or sum(r["declared_trials"] for r in roster) != 20622
            or [r["record_id"] for r in roster if r["declared_trials"] == 0] != ["L-S45-R1"]):
        raise ValueError("public roster support changed")
    seen, by_role, provenance = set(), {}, []
    for directory in directories:
        fid = directory["file_id"]
        if fid in seen or fid not in expected:
            raise ValueError("duplicate or unexpected archive identity")
        seen.add(fid)
        asset = expected[fid]
        if directory["bytes"] != asset["bytes"] or directory["filename"] != asset["filename"]:
            raise ValueError("archive extent/name mismatch")
        entries = directory["entries"]
        if not isinstance(entries, list) or len(entries) != directory["entries_count"]:
            raise ValueError("incomplete directory rows")
        names = [e["name"] for e in entries]
        if len(names) != len(set(names)):
            raise ValueError("duplicate directory name")
        tag = directory.get("etag")
        if (type(tag) is not str or len(tag) > 128
                or re.fullmatch(r'"[\x21\x23-\x7e\x80-\xff]*"', tag) is None):
            raise ValueError("caller must attach the transport-observed strong quoted ETag")
        files = sorted(e["name"] for e in entries if not e["directory"])
        by_role[asset["role"]] = files
        provenance.append({"file_id": fid, "filename": asset["filename"],
                           "etag": tag, "directory_result_sha256": _digest(directory),
                           "entries_count": len(entries),
                           "schema_document_candidates": [n for n in files if PurePosixPath(n).name in _SCHEMA_NAMES]})
    if seen != set(expected):
        raise ValueError("missing archive")
    matched = {role: set() for role in by_role}
    rows = []
    for r in roster:
        s, run = r["session"], r["run"]
        stem = f"doppler_S{s}_R{run}"
        continuous = f"dopplerContinuous_S{s}_R{run}"
        patterns = {
            "task_aligned_raw": stem + ".mat",
            "task_aligned_normcorre": stem + "+normcorre.mat",
            "continuous_raw": continuous + ".mat",
            "continuous_normcorre": continuous + "+normcorre.mat",
        }
        if r["recording_system"] == "prototypeRT":
            patterns.update(task_aligned_allTrials_raw=stem + "_allTrials.mat",
                            task_aligned_allTrials_normcorre=stem + "_allTrials+normcorre.mat")
        candidates = {}
        for form, basename in patterns.items():
            candidates[form] = [n for n in by_role["current"] if PurePosixPath(n).name == basename]
            matched["current"].update(candidates[form])
        upstream = []
        if r["recording_system"] == "prototypeRT":
            basename = f"rt_fUS_data_S{s}_R{run}.mat"
            upstream = [n for n in by_role["upstream_rt"] if PurePosixPath(n).name == basename]
            matched["upstream_rt"].update(upstream)
        possible_run99 = []
        if run == 99:
            for name in by_role["current"]:
                m = _DOPPLER.fullmatch(PurePosixPath(name).name)
                if m and int(m[1]) == s and int(m[2]) != 99:
                    possible_run99.append(name)
        rows.append({**r, "current_form_candidates": candidates,
                     "upstream_rt_candidates": upstream,
                     "same_session_other_run_candidates": possible_run99,
                     "Run99_constituent_lineage_proven": False if run == 99 else None,
                     "native_trial_count": None, "clock_semantics_established": False,
                     "zero_declared_count": r["declared_trials"] == 0})
    return {"schema": "fus_complete_directory_roster_join_v1", "status": "FILENAME_CENSUS_ONLY",
            "records": rows, "record_count": 49, "animals": 2, "positive_declared_records": 48,
            "directory_provenance": provenance,
            "unmatched_mat_members": {role: [n for n in files if n.lower().endswith('.mat') and n not in matched[role]]
                                      for role, files in by_role.items()},
            "native_ready": False, "interpretation": "Filename matches establish neither trial extent, Run99 lineage nor physical clocks."}
