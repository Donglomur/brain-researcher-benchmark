"""Target-free, complete Figure 3C prediction-family admission.

This module does not authenticate the scientific contents of an operator's
manifest, observe processes, choose an AUC direction, or decide improvement.
It validates byte commitments and full support before a private derivation.
"""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re


TASK = "PAPER-FIND-REP-009"
DATA_SHA256 = "9346505621a11d2704126b1e9c2b45dd02d3f645487effd4ab719c1978c19bea"
SCRIPT_SHA256 = "4a52c0b0e57a6206fbdf9415ebbda485d99eddbc2f13f2e4b709bcba36687a54"
CONDITIONS = ("Laser_OFF", "Laser_ON")
INFORMATION = ("paper_data", "paper_data_author_code")
MANIFEST_CAP = 4 * 1024 * 1024
PANEL_CAP = 8 * 1024 * 1024
BUNDLE_CAP = 64 * 1024 * 1024
SHA = re.compile(r"[0-9a-f]{64}\Z")


class IntakeError(ValueError):
    """An input was not admitted; private derivation must not start."""


def need(value, message):
    if not value:
        raise IntakeError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def pin(value):
    return type(value) is str and SHA.fullmatch(value) is not None


def text(value):
    if type(value) is not str:
        return False
    try:
        return 0 < len(value.encode("utf-8", "strict")) <= 256 and not any(
            ord(c) < 32 or ord(c) == 127 for c in value)
    except UnicodeError:
        return False


def keys(value, expected, message):
    need(type(value) is dict and set(value) == set(expected), message)


def strict_json(raw, cap):
    need(type(raw) is bytes and 0 < len(raw) <= cap, "bounded immutable JSON bytes")

    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def real(token):
        value = float(token)
        need(math.isfinite(value), "finite JSON number")
        need(value != 0 or Decimal(token) == 0, "nonzero floating literal underflow")
        return value

    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=pairs,
                          parse_float=real,
                          parse_constant=lambda _: need(False, "nonfinite JSON constant"))
    except (UnicodeError, ValueError, RecursionError, OverflowError, InvalidOperation) as exc:
        raise IntakeError("invalid JSON: " + str(exc)[:120]) from exc


def _manifest(raw, expected):
    need(pin(expected) and digest(raw) == expected, "operator-frozen manifest digest")
    value = strict_json(raw, MANIFEST_CAP)
    keys(value, ("schema", "task_id", "information_condition", "source_data_sha256",
                 "source_analysis_sha256", "qualification_evidence", "tone_ids",
                 "animal_ids", "cells", "panels"), "exact manifest fields")
    need(value["schema"] == "thalamus_3c_protected_support_v1" and
         value["task_id"] == TASK and value["information_condition"] in INFORMATION,
         "selected Figure 3C task and information condition")
    need(value["source_data_sha256"] == DATA_SHA256 and
         value["source_analysis_sha256"] == SCRIPT_SHA256, "original source identities")
    evidence = value["qualification_evidence"]
    keys(evidence, ("original_trial_assignment", "figure_session_animal_join",
                    "neural_input_membership", "original_shuffle_recipe",
                    "source_metric_policy", "full_panel_comparison_policy",
                    "protected_execution_policy"), "all unresolved qualification references")
    need(all(pin(x) for x in evidence.values()), "explicit qualification evidence hashes")
    tones, animals = value["tone_ids"], value["animal_ids"]
    need(type(tones) is list and len(tones) == 6 and all(text(x) for x in tones)
         and len(set(tones)) == 6, "six distinct source tone identities")
    need(type(animals) is list and len(animals) == 4 and all(text(x) for x in animals)
         and len(set(animals)) == 4, "four source-reported animal identities require qualification")
    cells = value["cells"]
    need(type(cells) is list and len(cells) == 34, "complete seventeen by two panel")
    session_ids, used_animals, accepted = [], set(), []
    for index, cell in enumerate(cells):
        keys(cell, ("source_session", "animal_id", "condition", "observations_sha256", "trials"),
             "exact support cell fields")
        need(text(cell["source_session"]) and cell["animal_id"] in animals
             and cell["condition"] == CONDITIONS[index % 2]
             and pin(cell["observations_sha256"]), "ordered source support cell")
        if index % 2 == 0:
            need(cell["source_session"] not in session_ids, "seventeen distinct source sessions")
            session_ids.append(cell["source_session"])
        else:
            need(cell["source_session"] == cells[index - 1]["source_session"] and
                 cell["animal_id"] == cells[index - 1]["animal_id"], "paired condition session/animal")
        used_animals.add(cell["animal_id"])
        trials = cell["trials"]
        need(type(trials) is list and 2 <= len(trials) <= 100000, "bounded complete trial support")
        seen, present_tones, training, held = set(), set(), [], []
        for trial in trials:
            keys(trial, ("trial_id", "tone_id", "partition"), "target-free source trial fields")
            need(text(trial["trial_id"]) and trial["trial_id"] not in seen and
                 trial["tone_id"] in tones and trial["partition"] in ("train", "heldout"),
                 "unique declared trial, tone and partition")
            seen.add(trial["trial_id"])
            present_tones.add(trial["tone_id"])
            (training if trial["partition"] == "train" else held).append(trial["trial_id"])
        need(training and held and present_tones == set(tones), "both partitions and complete six-tone source support")
        accepted.append((cell["source_session"], cell["condition"], tuple(held)))
    need(used_animals == set(animals), "complete reported animal support")
    panels = value["panels"]
    need(type(panels) is list and 3 <= len(panels) <= 64,
         "candidate, author and nonempty source-declared shuffle family")
    panel_ids = []
    for index, panel in enumerate(panels):
        keys(panel, ("panel_id", "role", "program_sha256", "producer_id", "control_identity_sha256"),
             "exact frozen producer identity fields")
        need(text(panel["panel_id"]) and panel["panel_id"] not in panel_ids
             and text(panel["producer_id"])
             and pin(panel["program_sha256"]), "unique frozen panel and named producer")
        expected_role = "candidate" if index == 0 else "author" if index == 1 else "author_shuffle"
        need(panel["role"] == expected_role, "candidate, author then original shuffle outputs")
        need((panel["control_identity_sha256"] is None) if index < 2
             else pin(panel["control_identity_sha256"]), "original control identity required for each shuffle")
        panel_ids.append(panel["panel_id"])
    return value, tuple(accepted)


@dataclass(frozen=True)
class AdmittedBundle:
    """Immutable artifact facts, not evidence of scientific qualification."""
    manifest_sha256: str
    information_condition: str
    support: tuple
    panels: tuple
    byte_commitments: tuple
    closure_receipts: tuple

    def receipt(self):
        return {"schema": "thalamus_3c_protected_intake_receipt_v1", "task_id": TASK,
                "manifest_sha256": self.manifest_sha256,
                "information_condition": self.information_condition,
                "cell_count": len(self.support), "panel_count": len(self.panels),
                "held_trial_counts": [len(cell[2]) for cell in self.support],
                "panel_sha256": dict(self.byte_commitments),
                "closure_receipt_sha256": dict(self.closure_receipts),
                "scientific_qualification": "not_established", "paper_win": None,
                "source_auto_auc": None, "predictive_auc": None,
                "current_sota": "not_assessed"}


def admit(manifest_raw, expected_manifest_sha256, panel_blobs, operator_closures):
    """Admit all immutable bytes without reading targets or fitting/scoring.

    `operator_closures` belongs to the trusted operator, never a contestant.
    This checks its exact producer/output binding but does not observe OS state.
    The caller must independently qualify its evidence and scientific manifest.
    """
    need(type(manifest_raw) is bytes and 0 < len(manifest_raw) <= MANIFEST_CAP,
         "bounded manifest bytes")
    manifest, support = _manifest(manifest_raw, expected_manifest_sha256)
    specs = manifest["panels"]
    expected_ids = {p["panel_id"] for p in specs}
    need(type(panel_blobs) is dict and set(panel_blobs) == expected_ids, "all and only frozen output panels")
    need(type(operator_closures) is dict and set(operator_closures) == expected_ids,
         "all and only operator closure records")
    need(all(type(raw) is bytes and 0 < len(raw) <= PANEL_CAP for raw in panel_blobs.values())
         and sum(map(len, panel_blobs.values())) <= BUNDLE_CAP, "bounded entire prediction family")
    admitted, commitments, closures = [], [], []
    for spec in specs:
        panel_id = spec["panel_id"]
        raw = panel_blobs[panel_id]
        body_sha = digest(raw)
        closure = operator_closures[panel_id]
        keys(closure, ("producer_id", "closed", "exit_code", "output_sha256", "receipt_sha256"),
             "exact operator closure fields")
        need(closure["producer_id"] == spec["producer_id"] and closure["closed"] is True
             and type(closure["exit_code"]) is int and closure["exit_code"] == 0
             and closure["output_sha256"] == body_sha and pin(closure["receipt_sha256"]),
             "operator-observed successful closure and complete output identity")
        value = strict_json(raw, PANEL_CAP)
        keys(value, ("schema", "task_id", "manifest_sha256", "panel_id", "program_sha256", "cells"),
             "exact target-free prediction envelope")
        need(value["schema"] == "thalamus_3c_protected_predictions_v1" and value["task_id"] == TASK
             and value["manifest_sha256"] == expected_manifest_sha256
             and value["panel_id"] == panel_id and value["program_sha256"] == spec["program_sha256"],
             "frozen task, support, panel and program identities")
        cells = value["cells"]
        need(type(cells) is list and len(cells) == 34, "complete output panel")
        probabilities = []
        for cell, (session, condition, trial_ids) in zip(cells, support):
            keys(cell, ("source_session", "condition", "held_trial_ids", "probability_randomised"),
                 "exact target-free prediction cell fields")
            need(cell["source_session"] == session and cell["condition"] == condition
                 and type(cell["held_trial_ids"]) is list
                 and cell["held_trial_ids"] == list(trial_ids), "exact ordered original held-trial support")
            values = cell["probability_randomised"]
            need(type(values) is list and len(values) == len(trial_ids)
                 and all(type(x) in (int, float) and 0 <= x <= 1 and math.isfinite(x) for x in values),
                 "complete finite Randomised probability vector")
            probabilities.append(tuple(values))
        admitted.append((panel_id, spec["role"], tuple(probabilities)))
        commitments.append((panel_id, body_sha))
        closures.append((panel_id, closure["receipt_sha256"]))
    return AdmittedBundle(expected_manifest_sha256, manifest["information_condition"],
                          support, tuple(admitted), tuple(commitments), tuple(closures))


def admit_then_derive(manifest_raw, expected_manifest_sha256, panel_blobs,
                      operator_closures, private_derivation):
    """Call one trusted private derivation only after the whole family passes.

    The callback must implement a separately qualified source metric and full-
    panel scientific policy. No callback result is relabelled as a paper win.
    Exceptions propagate; there is no automatic retry or hidden second read.
    """
    need(callable(private_derivation), "private derivation callback")
    admitted = admit(manifest_raw, expected_manifest_sha256, panel_blobs, operator_closures)
    return {"intake": admitted.receipt(), "private_derivation": private_derivation(admitted)}
