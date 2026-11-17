"""Owner-side chronological reward-relative decoding evaluation (construction only).

Only authenticated, already computed circular targets enter this module. It does
not guess the paper's position-to-angle transformation or load native pickles.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import math
import random
from pathlib import Path
from statistics import mean

TASK_ID = "PAPER-EXP-20261113-004"
SWITCH_DAYS = (3, 5, 7, 8, 10, 12, 14)
SWITCH_ANIMALS = ("GCAMP3", "GCAMP4", "GCAMP7", "GCAMP11", "GCAMP12", "GCAMP13",
                  "GCAMP14", "GCAMP15", "GCAMP17", "GCAMP18", "GCAMP19")
CODE_COMMIT = "adf0f9ed3defa22275d92fa0ed996f47008e05b3"
HOLDS = [
    "Historical paper code and individual authentic data identities unqualified",
    "Full cohort/session/cell membership and native safe-loader admission unqualified",
    "Historical circular coordinates, teleport policy and prospective odd-lap rounding unqualified",
    "Complete Figure 2/3 recomputation and independent reference/tolerances absent",
    "Official calibration-only decoder and occupancy-matched shuffle not qualified",
    "Authentic feature causality, calibration-only selection and protected execution require owner audit",
    "No authentic scientific evaluation, reproduction or submission qualification",
]


class ContractError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise ContractError(message)


def exact(obj, keys, where):
    require(isinstance(obj, dict), f"{where}: expected object")
    require(set(obj) == set(keys), f"{where}: keys must be {sorted(keys)}")


def identifier(value, where):
    require(isinstance(value, str) and 0 < len(value) <= 256, f"{where}: invalid identifier")
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def finite(value, where):
    require(type(value) in (int, float) and math.isfinite(value), f"{where}: expected finite number")
    return float(value)


def sha256(value, where):
    require(isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value), f"{where}: expected SHA256")


def opaque(secret, kind, *parts):
    payload = json.dumps([kind, *parts], separators=(",", ":")).encode()
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def split_session(session):
    """Partition original chronological laps; odd counts use prospective floor(n/2).

    Incomplete post-switch laps are excluded with explicit traces. All pre-switch
    observations are calibration; no samples from the complete guard lap leak.
    """
    exact(session, ("session_id", "animal_id", "day", "cell_ids", "feature_evidence", "laps"), "session")
    identifier(session["session_id"], "session_id")
    identifier(session["animal_id"], "animal_id")
    require(type(session["day"]) is int and session["day"] in SWITCH_DAYS, "invalid switch day")
    cells = session["cell_ids"]
    require(isinstance(cells, list) and cells and all(isinstance(x, str) and x for x in cells), "cell IDs required")
    require(len(set(cells)) == len(cells), "duplicate cell ID")
    require(isinstance(session["laps"], list) and session["laps"], "laps required")
    seen_laps, seen_samples = set(), set()
    previous_time, post_started = -math.inf, False
    pre, post, incomplete = [], [], []
    for lap in session["laps"]:
        exact(lap, ("lap_id", "phase", "complete", "samples"), "lap")
        lid = identifier(lap["lap_id"], "lap_id")
        require(lid not in seen_laps, "duplicate lap ID")
        seen_laps.add(lid)
        require(lap["phase"] in ("pre", "post"), "invalid lap phase")
        require(type(lap["complete"]) is bool, "complete must be boolean")
        require(not (post_started and lap["phase"] == "pre"), "pre-switch lap after post-switch lap")
        post_started |= lap["phase"] == "post"
        require(isinstance(lap["samples"], list) and lap["samples"], "empty lap")
        for sample in lap["samples"]:
            exact(sample, ("sample_id", "time_seconds", "neural", "theta_rr"), "sample")
            sid = identifier(sample["sample_id"], "sample_id")
            require(sid not in seen_samples, "duplicate sample ID")
            seen_samples.add(sid)
            time = finite(sample["time_seconds"], "clock")
            require(time > previous_time, "session clock must strictly increase")
            previous_time = time
            theta = finite(sample["theta_rr"], "theta_rr")
            require(-math.pi <= theta <= math.pi, "target must be admitted radians in [-pi, pi]")
            require(isinstance(sample["neural"], list) and len(sample["neural"]) == len(cells), "neural channel shape mismatch")
            for x in sample["neural"]:
                if x is not None:
                    finite(x, "neural feature")
        if lap["phase"] == "pre":
            pre.append(lap)
        elif lap["complete"]:
            post.append(lap)
        else:
            incomplete.append(lap)
    require(pre, "pre-switch calibration support missing")
    ncal = len(post) // 2
    require(ncal >= 1 and len(post) - ncal - 1 >= 1, "insufficient complete post-switch laps for calibration, guard and evaluation")
    calibration, guard, evaluation = pre + post[:ncal], [post[ncal]], post[ncal + 1:]
    for role, laps in (("calibration", calibration), ("evaluation", evaluation)):
        require(any(x is not None for lap in laps for s in lap["samples"] for x in s["neural"]),
                f"{role} window contains no observed neural features")
    cal_ids = {s["sample_id"] for lap in calibration for s in lap["samples"]}
    feature = session["feature_evidence"]
    exact(feature, ("kind", "evidence_sha256", "fitted_sample_ids"), "feature_evidence")
    require(feature["kind"] == "causal_neural", "only causal neural features admitted")
    sha256(feature["evidence_sha256"], "feature evidence")
    fitted = feature["fitted_sample_ids"]
    require(isinstance(fitted, list) and all(isinstance(x, str) for x in fitted), "fitted sample IDs must be list")
    require(len(fitted) == len(set(fitted)) and set(fitted) <= cal_ids, "feature or cell selection fitted outside calibration")
    return {"calibration": calibration, "guard": guard, "evaluation": evaluation, "incomplete_post": incomplete,
            "complete_post_laps": len(post), "calibration_post_laps": ncal,
            "odd_count_floor_used": bool(len(post) % 2)}


def prepare(bundle, secret):
    """Validate complete support before producing any candidate-visible object.

    `secret` stays with the evaluator. IDs, source paths, cells, reward/location
    metadata, guard samples and raw acquisition clocks never enter public output.
    Evidence hashes are owner attestations, not automatic scientific validation.
    """
    require(isinstance(secret, bytes) and len(secret) >= 32, "owner secret must contain at least 32 bytes")
    exact(bundle, ("schema", "animals", "coordinate_evidence", "sessions"), "bundle")
    require(bundle["schema"] == "rr-owner-input-v1", "invalid input schema")
    animals = bundle["animals"]
    require(isinstance(animals, list) and len(animals) == 11, "exactly 11 switching mice required")
    for a in animals:
        identifier(a, "animal")
    require(len(set(animals)) == 11, "duplicate mouse")
    require(set(animals) == set(SWITCH_ANIMALS), "mouse roster differs from pinned current source switching cohort")
    coordinate = bundle["coordinate_evidence"]
    exact(coordinate, ("admission", "units", "source_commit", "transform_evidence_sha256", "data_identity_sha256"), "coordinate evidence")
    require(coordinate["admission"] in ("engineering_control", "owner_attested"), "coordinate admission required")
    require(coordinate["units"] == "radians", "coordinate units must be radians")
    require(coordinate["source_commit"] == CODE_COMMIT, "current inspected source pin mismatch")
    sha256(coordinate["transform_evidence_sha256"], "transform evidence")
    sha256(coordinate["data_identity_sha256"], "data identity")
    require(isinstance(bundle["sessions"], list) and len(bundle["sessions"]) == 77, "complete 77-session support required")
    plans, slots, session_ids = [], set(), set()
    all_samples = set()
    for session in bundle["sessions"]:
        plan = split_session(session)
        slot = (session["animal_id"], session["day"])
        require(slot[0] in animals and slot not in slots, "duplicate or unknown mouse/day")
        require(session["session_id"] not in session_ids, "duplicate source session ID")
        ids = {s["sample_id"] for lap in session["laps"] for s in lap["samples"]}
        require(not (ids & all_samples), "sample IDs must be globally unique")
        all_samples |= ids
        slots.add(slot)
        session_ids.add(session["session_id"])
        plans.append((session, plan))
    require(slots == {(a, d) for a in animals for d in SWITCH_DAYS}, "missing complete cohort support")
    public = {"schema": "rr-candidate-input-v1", "task_id": TASK_ID, "sessions": [], "outer_folds": []}
    owner = {"schema": "rr-owner-evaluation-v1", "task_id": TASK_ID, "input_sha256": digest(bundle),
             "coordinate_evidence": coordinate, "animals": animals, "sessions": [], "holds": HOLDS,
             "odd_lap_policy": "prospective_floor_half_complete_post_laps", "scientifically_qualified": False}
    for session, plan in sorted(plans, key=lambda z: (z[0]["animal_id"], z[0]["day"])):
        raw_sid = session["session_id"]
        sid = opaque(secret, "session", raw_sid)
        fold = opaque(secret, "fold", session["animal_id"])
        visible = {"session_id": sid, "fold_id": fold, "calibration": [], "query": []}
        private = {"session_id": sid, "source_session_id": raw_sid, "animal_id": session["animal_id"],
                   "day": session["day"], "fold_id": fold, "targets": [], "calibration_sample_ids": [],
                   "feature_evidence": session["feature_evidence"], "trace": {}}
        for role, target_name in (("calibration", "calibration"), ("evaluation", "query")):
            origin = plan[role][0]["samples"][0]["time_seconds"]
            for lap in plan[role]:
                trial = opaque(secret, "trial", raw_sid, lap["lap_id"])
                for sample in lap["samples"]:
                    sample_token = opaque(secret, "sample", raw_sid, sample["sample_id"])
                    row = {"sample_id": sample_token, "trial_id": trial,
                           "time_seconds": finite(sample["time_seconds"] - origin, "relative sample clock"),
                           "neural": [0.0 if x is None else x for x in sample["neural"]],
                           "missing": [x is None for x in sample["neural"]]}
                    if role == "calibration":
                        row["theta_rr"] = sample["theta_rr"]
                        private["calibration_sample_ids"].append(sample_token)
                    else:
                        private["targets"].append({"sample_id": sample_token, "theta_rr": sample["theta_rr"]})
                    visible[target_name].append(row)
        for role in ("calibration", "guard", "evaluation", "incomplete_post"):
            private["trace"][role] = {"lap_ids": [x["lap_id"] for x in plan[role]],
                                      "sample_count": sum(len(x["samples"]) for x in plan[role])}
        private["trace"].update({k: plan[k] for k in ("complete_post_laps", "calibration_post_laps", "odd_count_floor_used")})
        public["sessions"].append(visible)
        owner["sessions"].append(private)
    # Do not expose the source animal/day sort order through opaque IDs.
    public["sessions"].sort(key=lambda s: s["session_id"])
    for animal in sorted(animals, key=lambda a: opaque(secret, "fold", a)):
        fid = opaque(secret, "fold", animal)
        public["outer_folds"].append({"fold_id": fid,
            "selection_session_ids": [s["session_id"] for s in public["sessions"] if s["fold_id"] != fid],
            "held_session_ids": [s["session_id"] for s in public["sessions"] if s["fold_id"] == fid]})
    owner["candidate_input_sha256"] = digest(public)
    owner["plan_sha256"] = digest(owner)
    return public, owner


def _predictions(submission, owner):
    exact(submission, ("schema", "task_id", "candidate_input_sha256", "sessions"), "submission")
    require(submission["schema"] == "rr-predictions-v1" and submission["task_id"] == TASK_ID, "submission identity mismatch")
    require(submission["candidate_input_sha256"] == owner["candidate_input_sha256"], "wrong candidate input identity")
    require(isinstance(submission["sessions"], list), "prediction sessions must be list")
    expected = {s["session_id"]: s for s in owner["sessions"]}
    results = {}
    for session in submission["sessions"]:
        exact(session, ("session_id", "predictions", "fit_receipt"), "prediction session")
        sid = session["session_id"]
        identifier(sid, "prediction session ID")
        require(sid in expected and sid not in results, "unknown/duplicate prediction session")
        reference = expected[sid]
        receipt = session["fit_receipt"]
        exact(receipt, ("calibration_sample_ids", "selection_session_ids", "artifact_sha256"), "fit receipt")
        sha256(receipt["artifact_sha256"], "fitted artifact")
        cal = receipt["calibration_sample_ids"]
        require(isinstance(cal, list) and all(isinstance(x, str) for x in cal), "calibration receipt IDs must be strings")
        require(isinstance(cal, list) and len(cal) == len(set(cal)) and set(cal) == set(reference["calibration_sample_ids"]), "candidate/comparator must use identical complete calibration support")
        selection = receipt["selection_session_ids"]
        require(isinstance(selection, list) and all(isinstance(x, str) for x in selection), "selection receipt IDs must be strings")
        allowed = {s["session_id"] for s in owner["sessions"] if s["animal_id"] != reference["animal_id"]}
        require(isinstance(selection, list) and len(selection) == len(set(selection)) and set(selection) <= allowed, "outer held mouse used for algorithm selection")
        predicted = {}
        require(isinstance(session["predictions"], list), "predictions must be list")
        for row in session["predictions"]:
            exact(row, ("sample_id", "theta_rr"), "prediction")
            token = row["sample_id"]
            require(isinstance(token, str) and token not in predicted, "duplicate/invalid prediction sample")
            angle = finite(row["theta_rr"], "prediction angle")
            require(-math.pi <= angle <= math.pi, "predictions must use radians in [-pi, pi]")
            predicted[token] = angle
        require(set(predicted) == {r["sample_id"] for r in reference["targets"]}, "prediction support mismatch")
        results[sid] = mean(math.cos(t["theta_rr"] - predicted[t["sample_id"]]) for t in reference["targets"])
    require(set(results) == set(expected), "prediction sessions incomplete")
    return results


def score(owner, candidate, comparator, *, bootstrap_repeats=2000, seed=0):
    """Session means -> animal means -> equal animal mean; paired animal bootstrap.

    Comparator must be independently supplied under the identical admitted split.
    A fit receipt is auditable provenance, not proof that its claims are true.
    """
    require(owner.get("schema") == "rr-owner-evaluation-v1" and owner.get("task_id") == TASK_ID, "invalid owner plan")
    require(owner.get("plan_sha256") == digest({k: v for k, v in owner.items() if k != "plan_sha256"}), "owner plan integrity mismatch")
    require(len(owner["animals"]) == 11 and len(set(owner["animals"])) == 11, "owner cohort invalid")
    require(set(owner["animals"]) == set(SWITCH_ANIMALS), "owner switching roster invalid")
    require(len(owner["sessions"]) == 77 and {(s["animal_id"], s["day"]) for s in owner["sessions"]} == {(a, d) for a in owner["animals"] for d in SWITCH_DAYS}, "owner session support invalid")
    require(type(bootstrap_repeats) is int and 1 <= bootstrap_repeats <= 100000, "invalid bootstrap repetition count")
    require(type(seed) is int, "bootstrap seed must be integer")
    cand, base = _predictions(candidate, owner), _predictions(comparator, owner)
    sessions, animals = [], []
    for ref in owner["sessions"]:
        sid = ref["session_id"]
        sessions.append({"session_id": sid, "animal_id": ref["animal_id"], "day": ref["day"],
                         "n_samples": len(ref["targets"]), "candidate": cand[sid], "comparator": base[sid], "gain": cand[sid] - base[sid]})
    for animal in sorted(owner["animals"]):
        rows = [r for r in sessions if r["animal_id"] == animal]
        animals.append({"animal_id": animal, "n_sessions": len(rows),
                        "candidate": mean(r["candidate"] for r in rows),
                        "comparator": mean(r["comparator"] for r in rows),
                        "gain": mean(r["gain"] for r in rows)})
    gains = [r["gain"] for r in animals]
    rng = random.Random(seed)
    boots = sorted(mean(rng.choices(gains, k=len(gains))) for _ in range(bootstrap_repeats))
    def quantile(q):
        loc = (len(boots) - 1) * q
        lo, hi = math.floor(loc), math.ceil(loc)
        return boots[lo] + (boots[hi] - boots[lo]) * (loc - lo)
    return {"schema": "rr-engineering-score-v1", "task_id": TASK_ID, "plan_sha256": owner["plan_sha256"],
            "candidate": mean(r["candidate"] for r in animals), "comparator": mean(r["comparator"] for r in animals),
            "paired_gain": mean(gains), "animal_effects": animals, "session_scores": sessions,
            "uncertainty": {"unit": "mouse", "method": "paired_percentile_bootstrap_prospective", "seed": seed,
                            "repeats": bootstrap_repeats, "confidence_level": 0.95, "gain_interval": [quantile(.025), quantile(.975)]},
            "scientifically_qualified": False, "reference_results_qualified": False,
            "admission": owner["coordinate_evidence"]["admission"], "holds": HOLDS}


def read_json(path):
    def reject(token):
        raise ContractError(f"nonstandard JSON number {token}")
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=reject, object_pairs_hook=unique)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--owner-input", required=True)
    prep.add_argument("--secret-file", required=True)
    prep.add_argument("--candidate-output", required=True)
    prep.add_argument("--owner-output", required=True)
    scoring = sub.add_parser("score")
    scoring.add_argument("--owner-plan", required=True)
    scoring.add_argument("--candidate", required=True)
    scoring.add_argument("--comparator", required=True)
    scoring.add_argument("--output", required=True)
    scoring.add_argument("--bootstrap-repeats", type=int, default=2000)
    scoring.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    if args.command == "prepare":
        require(Path(args.candidate_output).resolve() != Path(args.owner_output).resolve(), "owner and candidate output paths must differ")
        public, private = prepare(read_json(args.owner_input), Path(args.secret_file).read_bytes())
        write_json(args.owner_output, private)
        write_json(args.candidate_output, public)
    else:
        result = score(read_json(args.owner_plan), read_json(args.candidate), read_json(args.comparator), bootstrap_repeats=args.bootstrap_repeats, seed=args.seed)
        write_json(args.output, result)


if __name__ == "__main__":
    main()
