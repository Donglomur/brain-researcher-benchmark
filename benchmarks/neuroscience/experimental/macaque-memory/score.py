"""Conditional memory-age prediction scorer; no MAT loading or model fitting.

The evaluator, never the candidate, supplies the manifest and baseline file.
This component does not enforce process isolation or authenticate a data intake.
All 35 source sessions must be represented; unresolved cohort joins block use.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


class Invalid(ValueError):
    pass


BASELINES = ("training_prior", "behavior_and_rate", "nested_linear_svm")
MAX_BYTES = 32 * 1024 * 1024
MAX_CASES = 100000


def exact_keys(value, keys, where):
    if type(value) is not dict or set(value) != set(keys):
        raise Invalid(f"{where}: unexpected or missing fields")


def text(value, where):
    if type(value) is not str or not value or len(value) > 160:
        raise Invalid(f"{where}: bounded nonempty string required")
    return value


def unique_pairs(rows, where):
    if type(rows) is not list or not rows:
        raise Invalid(f"{where}: nonempty list required")
    result = set()
    for row in rows:
        exact_keys(row, ("animal", "session"), where)
        key = (text(row["animal"], where), text(row["session"], where))
        if key in result:
            raise Invalid(f"{where}: duplicate session")
        result.add(key)
    return result


def validate_manifest(manifest, roster):
    exact_keys(manifest, ("schema", "endpoint", "source_roster_sha256", "training_blocks", "cases"), "manifest")
    if manifest["schema"] != "macaque-memory-protected-predictions-v1":
        raise Invalid("manifest schema")
    if manifest["endpoint"] != "prospective_within_session_block_memory_age":
        raise Invalid("historical fitted outputs are not protected prediction cases")
    roster_bytes = json.dumps(roster, sort_keys=True, separators=(",", ":")).encode()
    if manifest["source_roster_sha256"] != hashlib.sha256(roster_bytes).hexdigest():
        raise Invalid("source roster identity mismatch")
    expected = unique_pairs(roster, "roster")
    if len(expected) != 35 or {a for a, _ in expected} != {"animal_1", "animal_2"}:
        raise Invalid("this endpoint requires the complete two-animal, 35-session roster")
    if sum(a == "animal_1" for a, _ in expected) != 18:
        raise Invalid("source animal/session nesting changed")
    training = defaultdict(set)
    if type(manifest["training_blocks"]) is not list:
        raise Invalid("training blocks")
    for row in manifest["training_blocks"]:
        exact_keys(row, ("animal", "session", "block"), "training block")
        key = (text(row["animal"], "animal"), text(row["session"], "session"))
        block = text(row["block"], "block")
        if key not in expected or block in training[key]:
            raise Invalid("unknown session or duplicate training block")
        training[key].add(block)
    if set(training) != expected:
        raise Invalid("training must cover every source session")
    cases = manifest["cases"]
    if type(cases) is not list or not 1 <= len(cases) <= MAX_CASES:
        raise Invalid("case count")
    ids, groups, seen = set(), defaultdict(set), {}
    for row in cases:
        exact_keys(row, ("case_id", "animal", "session", "block", "target"), "case")
        cid = text(row["case_id"], "case ID")
        key = (text(row["animal"], "animal"), text(row["session"], "session"))
        block = text(row["block"], "block")
        if cid in ids or key not in expected:
            raise Invalid("duplicate case or unknown session")
        if block in training[key]:
            raise Invalid("training/evaluation block overlap")
        if type(row["target"]) is not str or row["target"] not in ("old", "new"):
            raise Invalid("target must be explicitly joined old/new, not Set_day")
        ids.add(cid)
        groups[key].add(row["target"])
        seen[cid] = row
    if set(groups) != expected or any(v != {"old", "new"} for v in groups.values()):
        raise Invalid("every source session requires both explicit condition labels; no silent omission")
    return seen


def probabilities(rows, ids, where):
    if type(rows) is not list or len(rows) != len(ids):
        raise Invalid(f"{where}: complete case coverage required")
    out = {}
    for row in rows:
        exact_keys(row, ("case_id", "p_new"), where)
        cid = text(row["case_id"], "case ID")
        p = row["p_new"]
        if cid not in ids or cid in out:
            raise Invalid(f"{where}: duplicate or unknown case")
        if type(p) not in (float, int) or not math.isfinite(p) or not 0 <= p <= 1:
            raise Invalid(f"{where}: finite probability required")
        out[cid] = float(p)
    return out


def measures(cases, predictions):
    cells = defaultdict(list)
    for cid, case in cases.items():
        y = int(case["target"] == "new")
        raw = predictions[cid]
        # Fixed scoring convention, not calibration or fitted clipping.
        p = min(1 - 1e-6, max(1e-6, raw))
        loss = -(y * math.log(p) + (1 - y) * math.log1p(-p))
        cells[(case["animal"], case["session"], case["target"])].append(
            (loss, float((raw >= 0.5) == bool(y)))
        )
    sessions = defaultdict(list)
    for (animal, session, _condition), values in sorted(cells.items()):
        sessions[(animal, session)].append(
            (math.fsum(v[0] for v in values) / len(values),
             math.fsum(v[1] for v in values) / len(values))
        )
    animals = defaultdict(list)
    for (animal, session), values in sorted(sessions.items()):
        animals[animal].append({"session": session,
            "balanced_log_loss_nats": math.fsum(v[0] for v in values) / 2,
            "balanced_accuracy": math.fsum(v[1] for v in values) / 2})
    per_animal = {}
    for animal, values in sorted(animals.items()):
        per_animal[animal] = {
            "sessions": values,
            "balanced_log_loss_nats": math.fsum(v["balanced_log_loss_nats"] for v in values) / len(values),
            "balanced_accuracy": math.fsum(v["balanced_accuracy"] for v in values) / len(values),
        }
    return {
        "balanced_log_loss_nats": math.fsum(v["balanced_log_loss_nats"] for v in per_animal.values()) / 2,
        "balanced_accuracy": math.fsum(v["balanced_accuracy"] for v in per_animal.values()) / 2,
        "per_animal": per_animal,
    }


def score(manifest, submission, baselines, roster):
    cases = validate_manifest(manifest, roster)
    exact_keys(submission, ("schema", "predictions"), "submission")
    if submission["schema"] != "macaque-memory-submission-v1":
        raise Invalid("submission schema")
    exact_keys(baselines, BASELINES, "baselines")
    candidate = measures(cases, probabilities(submission["predictions"], cases, "candidate"))
    reference = {name: measures(cases, probabilities(baselines[name], cases, name)) for name in BASELINES}
    return {
        "schema": "macaque-memory-score-v1", "cases": len(cases), "sessions": 35, "animals": 2,
        "candidate": candidate, "references": reference,
        "primary_gain_nats": reference["nested_linear_svm"]["balanced_log_loss_nats"] - candidate["balanced_log_loss_nats"],
        "per_animal_primary_gain_nats": {
            animal: reference["nested_linear_svm"]["per_animal"][animal]["balanced_log_loss_nats"]
            - candidate["per_animal"][animal]["balanced_log_loss_nats"] for animal in ("animal_1", "animal_2")},
        "inference": "Descriptive finite-panel comparison; no population significance or causal claim.",
    }


def load(path):
    p = Path(path)
    if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_BYTES:
        raise Invalid("bounded ordinary JSON file required")
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Invalid("duplicate JSON key")
            result[key] = value
        return result
    with p.open("rb") as stream:
        body = stream.read(MAX_BYTES + 1)
    if len(body) > MAX_BYTES:
        raise Invalid("JSON body exceeds bound")
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(Invalid("nonfinite JSON")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "submission", "baselines", "roster"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    print(json.dumps(score(load(args.manifest), load(args.submission), load(args.baselines), load(args.roster)), sort_keys=True, allow_nan=False))
