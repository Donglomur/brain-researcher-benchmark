"""Complete-panel montage diagnostics from declared header metadata only.

No EEG is opened, no input is scientifically admitted, and no channel is filled,
deduplicated or reconstructed. The frozen M1 selector remains authoritative.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import types


RUNTIME = (Path(__file__).resolve().parent.parent / "registered-runtime" /
           "runtime/source/neural012/private")
CONTRACT_SHA256 = "558db102d0d8ab0bba545c231fe8df92720e8e1b5c37195bef662ea3834b7e08"
HEADER_SHA256 = "4a4afd825e50d3969318c0e0d854157dd9947acfa19f85e0e7b6e110fb3fc95b"
MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
ID = re.compile(r"[0-9a-f]{24}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, allow_nan=False,
                       separators=(",", ":")) + "\n").encode()


def load_contract(root=RUNTIME):
    """Compile the same source bytes that were checked, with no import alias."""
    root = Path(root)
    sources = {}
    for name, digest in (("scientific_contract.py", CONTRACT_SHA256),
                         ("source_header.py", HEADER_SHA256)):
        with (root / name).open("rb") as stream:
            raw = stream.read(100001)
        need(len(raw) <= 100000 and hashlib.sha256(raw).hexdigest() == digest,
             "preserved montage source mismatch: " + name)
        sources[name] = raw
    module = types.ModuleType("neural012_preserved_montage_contract")
    exec(compile(sources["scientific_contract.py"],
                 str(root / "scientific_contract.py"), "exec"), module.__dict__)
    return module


def strict(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(
                          ValueError("nonfinite JSON constant")))


def diagnose_record(row, contract):
    """Retain every M1 edge problem; indices refer to declared header order.

    Channel eligibility mirrors source_header.py's pinned label selector only.
    Sample rate, affine calibration and binary EDF geometry are not checked.
    """
    fields = {"recording_id", "patient_id", "cohort", "channel_labels",
              "release_eeg_labels", "header_sha256", "original_source_sha256"}
    need(type(row) is dict and set(row) == fields, "exact diagnostic record fields")
    for key in ("recording_id", "patient_id"):
        need(type(row[key]) is str and ID.fullmatch(row[key]), "opaque record/person identity")
    for key in ("header_sha256", "original_source_sha256"):
        need(type(row[key]) is str and SHA.fullmatch(row[key]), "declared source/header hash")
    cohort = row["cohort"]
    need(cohort in ("CHB", "Siena"), "known cohort")
    labels = row["channel_labels"]
    need(type(labels) is list and 0 < len(labels) <= 512 and
         all(type(x) is str and x.isascii() and 0 < len(x) <= 32 and
             not any(c in x for c in "\0\r\n") for x in labels),
         "complete bounded declared header labels")
    whitelist = row["release_eeg_labels"]
    need(type(whitelist) is list and len(whitelist) <= 512 and
         len(set(whitelist)) == len(whitelist) and
         all(type(x) is str and contract.EEG.fullmatch(x) for x in whitelist),
         "unique bounded release EEG whitelist")
    need((not whitelist) if cohort == "CHB" else bool(whitelist),
         "cohort-specific whitelist")
    selected, excluded = [], []
    for index, original in enumerate(labels):
        # EDF ASCII fields are stripped by the preserved header parser before
        # either cohort's eligibility check. Keep submitted text for diagnostics.
        header_label = original.strip()
        label = header_label
        if cohort == "Siena":
            label = header_label[4:].upper() if header_label.startswith("EEG ") else ""
            valid = bool(contract.EEG.fullmatch(label)) and label in whitelist
        else:
            parts = label.upper().split("-")
            valid = ((len(parts) == 1 and contract.EEG.fullmatch(parts[0])) or
                     (len(parts) == 2 and contract.EEG.fullmatch(parts[0]) and
                      (contract.EEG.fullmatch(parts[1]) or parts[1] in ("REF", "CS2"))))
        if valid:
            selected.append({"source_index": index, "label": label,
                             "declared_label": original,
                             "canonical_label": contract.normalized_label(label)})
        else:
            excluded.append({"source_index": index, "label": header_label,
                             "declared_label": original})
    issues = []
    if not selected:
        issues.append("no_selected_EEG_channels")
    if cohort == "Siena":
        observed = [x["label"] for x in selected]
        missing = sorted(set(whitelist) - set(observed))
        repeated = sorted({x for x in observed if observed.count(x) > 1})
        if missing:
            issues.append("missing_release_EEG_labels")
        if repeated:
            issues.append("duplicate_release_EEG_labels")
    else:
        missing, repeated = [], []
    edges = []
    for edge in contract.EDGES:
        a, b = edge.split("-")
        if cohort == "CHB":
            candidates = [{"source_index": x["source_index"],
                           "sign": 1 if x["canonical_label"] == edge else -1}
                          for x in selected if x["canonical_label"] in (edge, b + "-" + a)]
            status = "unique" if len(candidates) == 1 else ("missing" if not candidates else "ambiguous")
            edges.append({"edge": edge, "status": status, "measured_candidates": candidates})
        else:
            left = [x["source_index"] for x in selected if x["canonical_label"] == a]
            right = [x["source_index"] for x in selected if x["canonical_label"] == b]
            status = "unique" if len(left) == len(right) == 1 else (
                "missing" if not left or not right else "ambiguous")
            edges.append({"edge": edge, "status": status,
                          "left_source_indices": left, "right_source_indices": right})
    structural = not issues and all(x["status"] == "unique" for x in edges)
    # The original edge validator provides an independent acceptance cross-check;
    # diagnostic enumeration never changes its decisions or selects candidates.
    try:
        contract.edge_mapping([x["label"] for x in selected], cohort)
        edge_validator_accepts = True
    except ValueError:
        edge_validator_accepts = False
    need(edge_validator_accepts == all(x["status"] == "unique" for x in edges),
         "diagnostic and preserved edge validator disagree")
    return {"recording_id": row["recording_id"], "patient_id": row["patient_id"],
            "cohort": cohort, "declared_header_sha256": row["header_sha256"],
            "declared_original_source_sha256": row["original_source_sha256"],
            "selected_channels": selected, "excluded_channels": excluded,
            "record_issues": issues, "missing_release_labels": missing,
            "duplicate_release_labels": repeated, "edges": edges,
            "structural_label_support": structural}


def diagnose_panel(value, contract):
    need(type(value) is dict and set(value) == {"schema", "task_id", "records"} and
         value["schema"] == "neural012_declared_header_labels_v1" and
         value["task_id"] == "NEURAL-012", "exact panel diagnostic schema")
    rows = value["records"]
    need(type(rows) is list and len(rows) == 727, "complete 727-record panel required")
    reports, ids, patients = [], set(), {"CHB": set(), "Siena": set()}
    counts = {"CHB": 0, "Siena": 0}
    for row in rows:
        result = diagnose_record(row, contract)
        need(result["recording_id"] not in ids, "unique complete recording identities")
        ids.add(result["recording_id"])
        cohort = result["cohort"]
        counts[cohort] += 1
        patients[cohort].add(result["patient_id"])
        reports.append(result)
    need(counts == {"CHB": 686, "Siena": 41}, "complete cohort record support")
    need(len(patients["CHB"]) == 23 and len(patients["Siena"]) == 14 and
         patients["CHB"].isdisjoint(patients["Siena"]), "declared 23+14 disjoint people")
    failing = [r["recording_id"] for r in reports if not r["structural_label_support"]]
    return {"schema": "neural012_montage_diagnostics_v1", "task_id": "NEURAL-012",
            "record_counts": counts, "declared_patient_counts": {c: len(v) for c, v in patients.items()},
            "records": reports, "structural_failures": failing,
            "complete_panel_structural_label_support": not failing,
            "source_contract_sha256": CONTRACT_SHA256,
            "source_header_selector_sha256": HEADER_SHA256,
            "evidence_scope": "declared_header_label_metadata_only",
            "scientifically_qualified": False, "runnable": False,
            "unresolved": ["publisher_origin_and_actual_header_join", "full_EEG_sample_support",
                           "physical_calibration_and_native_rate", "Siena_common_reference_physics",
                           "clock_and_biological_identity_adjudication", "protected_execution"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    need(not args.output.exists() and not args.output.is_symlink(), "fresh output path")
    need(type(args.input_sha256) is str and SHA.fullmatch(args.input_sha256), "exact input SHA256")
    with args.input.open("rb") as stream:
        raw = stream.read(MAX_INPUT_BYTES + 1)
    need(len(raw) <= MAX_INPUT_BYTES and hashlib.sha256(raw).hexdigest() == args.input_sha256,
         "bounded exact input bytes")
    result = diagnose_panel(strict(raw), load_contract())
    result["input_sha256"] = args.input_sha256
    output = encoded(result)
    need(len(output) <= MAX_OUTPUT_BYTES, "bounded complete diagnostic output")
    with args.output.open("xb") as stream:
        stream.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
