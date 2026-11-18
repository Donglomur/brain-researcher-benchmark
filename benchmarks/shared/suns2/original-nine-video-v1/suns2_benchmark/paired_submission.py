"""Additive four-panel freeze/release adapter; no participant execution or new score.

Operator-supplied bindings, output receipts and expected freeze digest must stay
outside participant control. Tokens and matching hashes do not prove isolation,
pre-fold timing, policy execution, recreation or actual immutable storage.
"""
import hashlib
import json
import os
from pathlib import Path
import stat

from .constants import VIDEO_IDS, ASSISTANCE_CONDITIONS, TASK_SLUG
from .candidate_io import load_candidate_submission, _digest
from .candidate_mat5 import MAX_MAT_BYTES
from .grade import grade_submission, validate_reference_spec
from .paired_materials import validate_campaign_bindings

OUTCOME_KINDS = ("recreation", "improvement")

class PairedSubmissionError(ValueError):
    """Incomplete/mismatched paired artifacts; no partial grading result."""

def _need(ok, message):
    if not ok:
        raise PairedSubmissionError(message)

def _keys(value, names):
    _need(type(value) is dict and set(value) == set(names), "Exact paired record fields required")

def _pins(metadata, condition, procedure):
    _need(metadata.get("schema") == "suns2-verified-candidate-submission/v1" and
          metadata.get("condition") == condition and metadata.get("procedure_digest") == procedure and
          metadata.get("exact_support_and_file_census_verified") is True and
          _digest(metadata.get("manifest_sha256")), "Verified candidate identity mismatch")
    rows = metadata.get("cases")
    _need(type(rows) is list and len(rows) == len(VIDEO_IDS), "Complete candidate pin support required")
    by_video = {}
    for row in rows:
        video = row["video_id"]
        _need(video in VIDEO_IDS and video not in by_video, "Duplicate or wrong pinned video")
        _need(row["path"] == f"masks/{video}.mat" and _digest(row["sha256"]) and
              type(row["bytes"]) is int and 128 <= row["bytes"] <= MAX_MAT_BYTES,
              "Candidate case pins malformed")
        by_video[video] = {key:row[key] for key in ("video_id","path","sha256","bytes")}
    return {"condition":condition,"procedure_digest":procedure,
            "manifest_sha256":metadata["manifest_sha256"],"manifest_bytes":metadata["manifest_bytes"],
            "cases":[by_video[v] for v in VIDEO_IDS]}

def _receipt_map(receipts, bindings):
    _need(type(receipts) is list and len(receipts) == 18, "Exact eighteen trusted fold receipts required")
    expected = {(b["condition"],b["held_video"]):b for b in bindings}
    found = {}
    for row in receipts:
        _keys(row,("binding","outputs"))
        binding = row["binding"]
        _need(type(binding) is dict, "Fold receipt binding required")
        key = (binding.get("condition"),binding.get("held_video"))
        _need(key in expected and key not in found and binding == expected[key],
              "Missing, duplicate, swapped or cross-arm fold receipt")
        _keys(row["outputs"],OUTCOME_KINDS)
        outputs = {}
        for outcome in OUTCOME_KINDS:
            value = row["outputs"][outcome]
            _keys(value,("sha256","bytes"))
            _need(_digest(value["sha256"]) and type(value["bytes"]) is int and
                  128 <= value["bytes"] <= MAX_MAT_BYTES, "Fold output pin malformed")
            outputs[outcome] = dict(value)
        found[key] = {"binding":dict(binding),"outputs":outputs}
    _need(set(found) == set(expected), "Incomplete fold receipt support")
    return found

def _directories(submissions):
    _need(type(submissions) is list and len(submissions) == 4, "Exact four paired panels required")
    found, identities = {}, set()
    for row in submissions:
        _keys(row,("condition","outcome_kind","directory"))
        key = (row["condition"],row["outcome_kind"])
        _need(key[0] in ASSISTANCE_CONDITIONS and key[1] in OUTCOME_KINDS and key not in found,
              "Missing, duplicate or wrong arm/outcome panel")
        _need(type(row["directory"]) is str and 0 < len(row["directory"]) <= 4096,
              "Explicit submission directory required")
        root = Path(row["directory"])
        _need(root.is_absolute() and root == root.resolve(strict=True), "Submission directory alias refused")
        info = os.stat(root,follow_symlinks=False)
        identity = (info.st_dev,info.st_ino)
        _need(stat.S_ISDIR(info.st_mode) and identity not in identities,
              "Paired panels require four distinct directory identities")
        identities.add(identity)
        found[key] = {**row,"directory_identity":list(identity)}
    return found

def _verify_directory_identity(panel):
    root = Path(panel["directory"])
    _need(root == root.resolve(strict=True), "Submission directory alias changed")
    info = os.stat(root,follow_symlinks=False)
    _need(stat.S_ISDIR(info.st_mode) and [info.st_dev,info.st_ino] == panel["directory_identity"],
          "Submission directory identity changed during paired intake")

def freeze_paired_submissions(submissions, trusted_bindings, trusted_fold_receipts):
    """Authenticate all36 artifacts before protected reference grading is possible.

    The receipt is a content commitment, not a physical readonly freeze. A trusted
    controller retains its digest and establishes execution/custody independently.
    """
    bindings = validate_campaign_bindings(trusted_bindings)
    receipts = _receipt_map(trusted_fold_receipts,bindings)
    directories = _directories(submissions)
    panels = []
    for condition in ASSISTANCE_CONDITIONS:
        procedure = receipts[(condition,VIDEO_IDS[0])]["binding"]["procedure_digest"]
        for outcome in OUTCOME_KINDS:
            panel = directories[(condition,outcome)]
            arrays, metadata = load_candidate_submission(panel["directory"],condition,procedure)
            del arrays
            _verify_directory_identity(panel)
            pins = _pins(metadata,condition,procedure)
            for case in pins["cases"]:
                expected = receipts[(condition,case["video_id"])]["outputs"][outcome]
                _need(case["sha256"] == expected["sha256"] and case["bytes"] == expected["bytes"],
                      "Candidate output differs from trusted fold receipt")
            panels.append({**panel,"submission":pins})
    for panel in panels:
        _verify_directory_identity(panel)
    snapshot = {"schema":"suns2-paired-artifact-freeze/v1","task":TASK_SLUG,
        "bindings":[dict(b) for b in bindings],
        "fold_receipts":[receipts[(b["condition"],b["held_video"])] for b in bindings],
        "panels":panels}
    raw = json.dumps(snapshot,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    return {"status":"complete_36_output_content_commitment","snapshot":snapshot,
            "freeze_sha256":hashlib.sha256(raw).hexdigest(),
            "actual_readonly_storage_verified":False,"actual_fresh_state_isolation_verified":False,
            "procedure_pre_fold_timing_or_production_verified":False}

def grade_paired_submissions(reference_spec_path, reference_spec_sha256, submissions,
                            trusted_bindings, trusted_fold_receipts, expected_freeze_digest):
    """Re-admit every panel, grade privately, then release all four reports together.

    No intermediate reports, callbacks, report files or scores in failure messages.
    Recreation is a requested output kind, not a new numerical pass threshold.
    """
    try:
        _need(_digest(expected_freeze_digest), "Trusted freeze digest required")
        frozen = freeze_paired_submissions(submissions,trusted_bindings,trusted_fold_receipts)
        _need(frozen["freeze_sha256"] == expected_freeze_digest, "Paired freeze commitment changed")
        for panel in frozen["snapshot"]["panels"]:
            validate_reference_spec(reference_spec_path,reference_spec_sha256,panel["directory"])
        reports = []
        for panel in frozen["snapshot"]["panels"]:
            condition, outcome = panel["condition"], panel["outcome_kind"]
            procedure = panel["submission"]["procedure_digest"]
            report = grade_submission(reference_spec_path,reference_spec_sha256,
                                      panel["directory"],condition,procedure)
            _need(report["condition"] == condition and report["procedure_digest"] == procedure and
                  report["reference_spec_sha256"] == reference_spec_sha256 and
                  _pins(report["submission"],condition,procedure) == panel["submission"],
                  "Graded artifact pins differ from pre-reference commitment")
            reports.append({"condition":condition,"outcome_kind":outcome,"grading":report})
        return {"schema":"suns2-paired-artifact-grading/v1","task":TASK_SLUG,
                "status":"all_four_reports_released","freeze_sha256":expected_freeze_digest,
                "reports":reports,"new_benchmark_count":0,
                "recreation_label_proves_historical_reproduction":False,
                "execution_and_isolation_attested_by_this_adapter":False}
    except Exception:
        raise PairedSubmissionError("Paired grading refused; no partial reports released") from None
