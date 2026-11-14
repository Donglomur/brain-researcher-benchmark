"""Horrocks source-construction interface. Import has no I/O or fitting.

Functions operate on owner-held metadata/predictions, not as an isolation boundary.
No dataset has been admitted and no scientific reference has been qualified.
"""
import hashlib
import json
import math
import os
import re
import stat
import zipfile
from collections import Counter, defaultdict
from pathlib import PurePosixPath

ROSTER = (("M22027", "20220517"), ("M22029", "20220607"),
          ("M22031", "20220524"), ("M22032", "20220621"),
          ("M22033", "20220706"))
STATES = ("stationary", "locomotion")
CLASSES = tuple(range(1, 7))
WINDOWS = tuple(range(10))  # [0,100), ..., [900,1000] ms; host bins once.
ARCHIVE_BYTES = 642313346
ARCHIVE_MD5 = "a7ca0cdb2c7665ac8bd547257d98fc72"
SHA = re.compile(r"[0-9a-f]{64}\Z")
OPAQUE = re.compile(r"[0-9a-f]{32}\Z")


class Refusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Refusal(message)


def exact(obj, keys, label):
    require(type(obj) is dict and set(obj) == set(keys), label + ": unexpected schema")


def integer(value, label):
    require(type(value) is int, label + ": integer required")
    return value


def finite(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + ": finite number required")
    return value


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


def strict_json(text):
    """Reject duplicate keys and nonfinite JSON before validating a protocol."""
    def pairs(rows):
        out = {}
        for key, value in rows:
            require(key not in out, "duplicate JSON key")
            out[key] = value
        return out
    def reject(value):
        raise Refusal("nonfinite JSON constant")
    return json.loads(text, object_pairs_hook=pairs, parse_constant=reject)


def authenticate_archive_inventory(path, max_unpacked_bytes):
    """Future selected intake only: stream exact archive, inspect ZIP; extract nothing.

    Caller must prospectively select this 642 MB read and an unpacked-byte limit.
    A successful result proves archive identity/index observations, not data rights,
    member contents, MATLAB schema, animal identity or scientific admission.
    """
    require(integer(max_unpacked_bytes, "unpacked cap") > 0, "positive cap required")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as handle:
        st = os.fstat(handle.fileno())
        require(stat.S_ISREG(st.st_mode) and st.st_size == ARCHIVE_BYTES, "archive type/size")
        md5, sha256 = hashlib.md5(), hashlib.sha256()
        total = 0
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            total += len(block)
            require(total <= ARCHIVE_BYTES, "archive grew")
            md5.update(block)
            sha256.update(block)
        require(total == ARCHIVE_BYTES and md5.hexdigest() == ARCHIVE_MD5, "archive digest")
        handle.seek(0)
        with zipfile.ZipFile(handle) as archive:
            infos = archive.infolist()
            require(len(infos) <= 10000, "ZIP member cap")
            seen, inventory, unpacked = set(), [], 0
            for info in infos:
                name = info.filename
                pp = PurePosixPath(name)
                require(name not in seen and name and not pp.is_absolute() and
                        ".." not in pp.parts and "\\" not in name and "\x00" not in name,
                        "unsafe/duplicate ZIP name")
                seen.add(name)
                mode = info.external_attr >> 16
                require(not stat.S_ISLNK(mode) and not (info.flag_bits & 1), "symlink/encrypted member")
                require(stat.S_IFMT(mode) in (0, stat.S_IFREG, stat.S_IFDIR), "special ZIP member")
                unpacked += info.file_size
                require(unpacked <= max_unpacked_bytes, "unpacked byte cap")
                inventory.append({"path": name, "bytes": info.file_size,
                                  "compressed_bytes": info.compress_size, "crc32": info.CRC})
            selected = {}
            for mouse, date in ROSTER:
                basename = f"{mouse}_{date}_basic.mat"
                matches = [x for x in inventory if PurePosixPath(x["path"]).name == basename]
                require(len(matches) == 1, "missing/ambiguous canonical session " + basename)
                selected[mouse] = matches[0]
        final = os.fstat(handle.fileno())
        require((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns) ==
                (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns, final.st_ctime_ns),
                "archive changed during intake")
    return {"schema": "horrocks-archive-index-v1", "sha256": sha256.hexdigest(),
            "md5": md5.hexdigest(), "bytes": total, "members": inventory,
            "selected_sessions": selected, "unpacked_bytes": unpacked,
            "scientifically_admitted": False, "member_content_hashes_verified": False}


def make_protocol(intake):
    """Build an owner-side chronological extension from a separately authenticated index.

    The index is an OWNER argument, never candidate supplied. This function cannot
    authenticate its scientific lineage; an independent adapter/audit is still required.
    Cut the entire original trial sequence at its midpoint; omit one guard trial.
    Apply predeclared eligibility after partitioning. Never move cuts to obtain support.
    """
    exact(intake, ("schema", "archive_sha256", "sessions"), "intake")
    require(intake["schema"] == "horrocks-owner-trial-index-v1", "intake version")
    require(type(intake["archive_sha256"]) is str and SHA.fullmatch(intake["archive_sha256"]),
            "archive SHA256")
    sessions = intake["sessions"]
    require(type(sessions) is list and len(sessions) == 5, "all five sessions required")
    require({(s.get("mouse"), s.get("session")) for s in sessions if type(s) is dict} == set(ROSTER),
            "canonical animal/session roster")
    require(len({s["mouse"] for s in sessions}) == 5, "duplicate animal")
    result, global_ids = [], set()
    for session in sorted(sessions, key=lambda s: s["mouse"]):
        exact(session, ("mouse", "session", "member_sha256", "trials"), "session")
        require(type(session["member_sha256"]) is str and SHA.fullmatch(session["member_sha256"]),
                "member SHA256")
        trials = session["trials"]
        require(type(trials) is list and len(trials) >= 3, "trial census")
        cut = len(trials) // 2
        prior_onset = -math.inf
        rows = []
        for ordinal, trial in enumerate(trials):
            exact(trial, ("trial_id", "source_ordinal", "onset_s", "state", "visual_class"), "trial")
            tid = trial["trial_id"]
            require(type(tid) is str and OPAQUE.fullmatch(tid) and tid not in global_ids,
                    "duplicate/nonopaque trial id")
            global_ids.add(tid)
            require(integer(trial["source_ordinal"], "ordinal") == ordinal, "complete ordered census")
            onset = finite(trial["onset_s"], "onset")
            require(onset > prior_onset, "nonchronological/duplicate onset")
            prior_onset = onset
            state, label = trial["state"], trial["visual_class"]
            require((state is None and label is None) or
                    (state in STATES and type(label) is int and label in CLASSES), "state/class")
            partition = "calibration" if ordinal < cut else "guard" if ordinal == cut else "evaluation"
            rows.append({"trial_id": tid, "source_ordinal": ordinal, "onset_s": onset,
                         "state": state, "visual_class": label, "partition": partition})
        for partition, minimum in (("calibration", 6), ("evaluation", 1)):
            counts = Counter((t["state"], t["visual_class"]) for t in rows
                             if t["partition"] == partition and t["state"] is not None)
            for state in STATES:
                for label in CLASSES:
                    require(counts[state, label] >= minimum,
                            "insufficient complete support: " + session["mouse"] + "/" +
                            partition + "/" + state + "/" + str(label))
        # The fixed guard must separate full [-0.2,1.8]s source windows.
        # Never shift the cut to repair overlap or class support.
        require(rows[cut+1]["onset_s"] - 0.2 > rows[cut-1]["onset_s"] + 1.8,
                "fixed guard does not separate source response windows")
        result.append({"mouse": session["mouse"], "session": session["session"],
                       "member_sha256": session["member_sha256"], "trials": rows})
    canonical_intake = {**intake, "sessions": sorted(sessions, key=lambda s: s["mouse"])}
    body = {"schema": "horrocks-chronological-protocol-v1",
            "intake_sha256": canonical_sha(canonical_intake), "archive_sha256": intake["archive_sha256"],
            "sessions": result, "window_ms": [[100*i, 100*(i+1)] for i in WINDOWS],
            "training_window_ms": [100, 200], "n_animals": 5,
            "split_rule": "first floor(N/2) original trials; one original-trial guard; remaining trials",
            "minimum_calibration_per_class_state": 6,
            "source_lineage_admitted": False, "host_isolation_implemented": False}
    return {"body": body, "sha256": canonical_sha(body)}


def validate_protocol(protocol):
    exact(protocol, ("body", "sha256"), "protocol")
    body = protocol["body"]
    require(protocol["sha256"] == canonical_sha(body), "protocol digest mismatch")
    # Reconstruct from the complete original census. A digest alone cannot legitimize
    # a changed partition, missing window, class or mouse.
    exact(body, ("schema", "intake_sha256", "archive_sha256", "sessions", "window_ms",
                 "training_window_ms", "n_animals", "split_rule",
                 "minimum_calibration_per_class_state", "source_lineage_admitted",
                 "host_isolation_implemented"), "protocol body")
    intake = {"schema": "horrocks-owner-trial-index-v1", "archive_sha256": body["archive_sha256"],
              "sessions": []}
    for s in body["sessions"]:
        exact(s, ("mouse", "session", "member_sha256", "trials"), "protocol session")
        rows = []
        for t in s["trials"]:
            exact(t, ("trial_id", "source_ordinal", "onset_s", "state", "visual_class", "partition"),
                  "protocol trial")
            rows.append({k: v for k, v in t.items() if k != "partition"})
        intake["sessions"].append({**{k: v for k, v in s.items() if k != "trials"}, "trials": rows})
    require(make_protocol(intake) == protocol, "noncanonical protocol")
    return body


def public_query_index(protocol, mouse):
    """Return identity/window schema only. Neural tensor transfer is not implemented.

    State, raw timestamps, source positions, labels and original IDs remain owner-side.
    The future adapter must attach the same causal neural features to both conditions;
    condition B alone also receives audited official code.
    """
    body = validate_protocol(protocol)
    require(mouse in dict(ROSTER), "mouse")
    s = next(s for s in body["sessions"] if s["mouse"] == mouse)
    # Trusted adapter must generate independent random128-bit IDs; syntax alone
    # cannot prove that they do not encode source position or a target.
    rows = [{"trial_id": t["trial_id"], "window": w}
            for t in s["trials"] if t["partition"] == "evaluation" and t["state"] is not None
            for w in WINDOWS]
    return sorted(rows, key=lambda row: (row["trial_id"], row["window"]))


def score_improvement(protocol, candidate_rows, full_lda_rows, diagonal_lda_rows):
    """Owner-only diagnostic scoring of frozen outputs. Does not certify provenance.

    Prediction row = exactly {trial_id, window, prediction}, prediction is integer 1..6.
    Candidate and both baselines must cover the identical complete owner case set.
    Both references are adapted pooled-state LDA: no privileged state dispatch.
    """
    body = validate_protocol(protocol)
    truth = {}
    for s in body["sessions"]:
        for t in s["trials"]:
            if t["partition"] == "evaluation" and t["state"] is not None:
                for w in WINDOWS:
                    truth[t["trial_id"], w] = (s["mouse"], t["state"], w, t["visual_class"])
    def score(rows):
        require(type(rows) is list and len(rows) == len(truth), "prediction count")
        predictions = {}
        for row in rows:
            exact(row, ("trial_id", "window", "prediction"), "prediction row")
            key = (row["trial_id"], integer(row["window"], "window"))
            require(key in truth and key not in predictions, "extra/duplicate case")
            pred = integer(row["prediction"], "prediction")
            require(pred in CLASSES, "invalid class")
            predictions[key] = pred
        require(predictions.keys() == truth.keys(), "missing cases")
        totals, correct = Counter(), Counter()
        for key, cell in truth.items():
            totals[cell] += 1
            correct[cell] += predictions[key] == cell[3]
        animal, cells = {}, {}
        for mouse, _ in ROSTER:
            values = []
            for state in STATES:
                for w in WINDOWS:
                    recalls = [correct[mouse, state, w, c] / totals[mouse, state, w, c] for c in CLASSES]
                    value = sum(recalls) / 6
                    cells[f"{mouse}/{state}/{w}"] = value
                    values.append(value)
            animal[mouse] = sum(values) / len(values)
        return {"per_animal": animal, "mean": sum(animal.values()) / 5, "cells": cells}
    candidate, full, diagonal = map(score, (candidate_rows, full_lda_rows, diagonal_lda_rows))
    delta = {mouse: candidate["per_animal"][mouse] - full["per_animal"][mouse]
             for mouse, _ in ROSTER}
    mean = sum(delta.values()) / 5
    sem = math.sqrt(sum((d-mean)**2 for d in delta.values()) / 4) / math.sqrt(5)
    return {"schema": "horrocks-improvement-diagnostic-v1", "protocol_sha256": protocol["sha256"],
            "candidate": candidate, "full_lda": full, "diagonal_lda": diagonal,
            "paired_delta_by_animal": delta, "mean_paired_delta": mean, "paired_animal_sem": sem,
            "n_independent_animals": 5, "chance": 1/6, "scientifically_qualified": False,
            "limitations": ["No neural adapter, authenticated member schema or isolated outer-loop runner.",
                            "Other four animals fix algorithm/tuning policy; held calibration alone fits its parameters.",
                            "Both LDA references are pooled-state adaptations with identical neural-only access.",
                            "No provenance is established by submitted predictions or a self-reported digest.",
                            "SEM uses five animal differences, never trials as independent observations."]}


def relative_generalization(matrix, convention):
    """Fig4e owner diagnostic: paper equation and source clipping kept separate."""
    require(convention in ("paper_eq21_unclipped", "publication_analysis_clipped"), "convention")
    require(type(matrix) is list and len(matrix) == 20, "20 training windows required")
    for row in matrix:
        require(type(row) is list and len(row) == 20, "20 testing windows required")
        for value in row:
            require(0 <= finite(value, "accuracy") <= 1, "accuracy range")
    def adjust(value):
        corrected = value - 1/6
        return max(0, corrected) if convention == "publication_analysis_clipped" else corrected
    stimulus = range(2, 12)  # MATLAB 3:12, exactly [0,1] seconds.
    denominator = sum(adjust(matrix[i][i]) for i in stimulus)
    require(denominator > 0, "nonpositive chance-corrected reference: undefined/unqualified")
    return {"convention": convention, "early_train_window_ms": [100, 200],
            "relative_performance": sum(adjust(matrix[3][i]) for i in stimulus) / denominator,
            "qualification": False, "reason": "Paper/code convention must be adjudicated before reference grading."}


def compare_reproduction(candidate, reference, absolute_tolerance=None):
    """Compare complete five-animal numerical outputs against an OWNER rebuild.

    Both inputs: {mouse: {state: {within_time: 191 accuracies,
                                 cross_time: 20x20 accuracies}}}.
    Reference provenance and tolerance calibration are not established here.
    Neither successful array validation nor matching numbers qualifies a paper result.
    """
    def validate(value):
        exact(value, dict(ROSTER), "reproduction animal roster")
        for mouse in dict(ROSTER):
            exact(value[mouse], STATES, "reproduction states")
            for state in STATES:
                cell = value[mouse][state]
                exact(cell, ("within_time", "cross_time"), "reproduction outputs")
                curve, matrix = cell["within_time"], cell["cross_time"]
                require(type(curve) is list and len(curve) == 191, "all 191 sliding windows")
                require(type(matrix) is list and len(matrix) == 20, "all 20 cross-time rows")
                for row in matrix:
                    require(type(row) is list and len(row) == 20, "all 20 cross-time columns")
                for v in curve + [v for row in matrix for v in row]:
                    require(0 <= finite(v, "reproduction accuracy") <= 1, "accuracy range")
    validate(candidate)
    validate(reference)
    if absolute_tolerance is not None:
        require(0 <= finite(absolute_tolerance, "owner tolerance") <= 1, "tolerance range")
    errors = {}
    for mouse, _ in ROSTER:
        for state in STATES:
            for component in ("within_time", "cross_time"):
                c, r = candidate[mouse][state][component], reference[mouse][state][component]
                if component == "cross_time":
                    c, r = [v for row in c for v in row], [v for row in r for v in row]
                delta = [a-b for a, b in zip(c, r)]
                errors[f"{mouse}/{state}/{component}"] = {
                    "values": len(delta), "max_absolute_error": max(abs(v) for v in delta),
                    "root_mean_squared_error": math.sqrt(sum(v*v for v in delta)/len(delta))}
    maximum = max(e["max_absolute_error"] for e in errors.values())
    return {"components": errors, "maximum_absolute_error": maximum,
            "within_owner_tolerance": None if absolute_tolerance is None else maximum <= absolute_tolerance,
            "tolerance_calibrated_here": False, "n_independent_animals": 5,
            "scientifically_qualified": False,
            "remaining_evidence": ["Authenticated independent full reference and tolerance calibration",
                                   "Complete original trial/unit census and fold/repeat raw predictions",
                                   "Adjudicated paper/code conventions, seeds and environment",
                                   "Original statistics, deviations and protected execution provenance"]}

