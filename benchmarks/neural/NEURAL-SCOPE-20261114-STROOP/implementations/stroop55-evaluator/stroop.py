"""Complete-cohort scoring and split logic for NEURAL-SCOPE-20261114-STROOP.

No signal processing, acquisition, fitting, candidate execution or authentic
label access is performed by importing this standard-library module.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

TASK = "NEURAL-SCOPE-20261114-STROOP"
CLASSES = ("neutral", "congruent", "incongruent")
PEOPLE = 55
FOLDS = 5
EPSILON = 1e-15
CAP = 16 * 1024 * 1024
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class Invalid(ValueError):
    """The complete primary score is unestablished for this input."""


def exact_keys(obj, keys, context):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise Invalid(context + ": incorrect fields")


def integer(value, low, high, context):
    if type(value) is not int or not low <= value <= high:
        raise Invalid(context + ": invalid integer")


def digest(value, context):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise Invalid(context + ": SHA-256 hex string required")


def fold_assignment(opaque_participants, seed_hex):
    """Rank all55 opaque source-mapped IDs by SHA256(domain||seed||UTF8ID).

    IDs must be frozen by the trusted assembler before any labels or outcomes
    inform partitioning. Hash ties break lexicographically; sorted consecutive
    groups of11 form folds0..4. This does not create an authentic roster.
    """
    digest(seed_hex, "partition seed")
    if (not isinstance(opaque_participants, list) or len(opaque_participants) != PEOPLE
            or any(not isinstance(p, str) or not HEX64.fullmatch(p) for p in opaque_participants)
            or len(set(opaque_participants)) != PEOPLE):
        raise Invalid("exactly55 distinct opaque participant IDs required")
    domain = b"stroop55-joint-holdout-v1\x00" + bytes.fromhex(seed_hex) + b"\x00"
    ranked = sorted(opaque_participants, key=lambda p: (hashlib.sha256(domain + p.encode('ascii')).digest(), p))
    return {person: index // 11 for index, person in enumerate(ranked)}


def training_roles(assignments, fold):
    integer(fold, 0, FOLDS - 1, "fold")
    # Session3 is absent globally; held participants contribute no training data.
    return [(person, session) for person in sorted(assignments)
            if assignments[person] != fold for session in (1, 2)]


def check_training_roles(assignments, fold, roles):
    """Check a declared training roster, not a running process's actual reads."""
    expected = set(training_roles(assignments, fold))
    if not isinstance(roles, list) or len(roles) != 88:
        raise Invalid("all44 permitted training people times two sessions required")
    actual = set()
    for role in roles:
        if not isinstance(role, (tuple, list)) or len(role) != 2:
            raise Invalid("invalid training role")
        person, session = role
        digest(person, "training participant")
        integer(session, 1, 2, "training session")
        if (person, session) not in expected or (person, session) in actual:
            raise Invalid("duplicate or forbidden training participant/session")
        actual.add((person, session))
    if actual != expected:
        raise Invalid("training roster differs from fixed fold")
    return True


def validate_manifest(manifest):
    exact_keys(manifest, ("schema", "task", "partition_seed", "cohort", "cases"), "manifest")
    if manifest['schema'] != "stroop55-private-labels-v1" or manifest['task'] != TASK:
        raise Invalid("manifest schema/task mismatch")
    cohort = manifest['cohort']
    if not isinstance(cohort, list) or len(cohort) != PEOPLE:
        raise Invalid("complete55-person cohort required")
    people, seen_sessions = [], set()
    for person in cohort:
        exact_keys(person, ("participant", "sessions"), "cohort member")
        digest(person['participant'], "opaque participant")
        if person['sessions'] != [1, 2, 3] or any(type(v) is not int for v in person['sessions']):
            raise Invalid("all three source sessions required")
        people.append(person['participant'])
        seen_sessions.update((person['participant'], s) for s in person['sessions'])
    assignments = fold_assignment(people, manifest['partition_seed'])
    if len(seen_sessions) != 165:
        raise Invalid("complete165 participant-session metadata required")
    cases = manifest['cases']
    if not isinstance(cases, list) or not cases:
        raise Invalid("precommitted full case census required")
    indexed, support = {}, {p: [0, 0, 0] for p in people}
    blocks = set()
    for case in cases:
        exact_keys(case, ("case_id", "participant", "session", "block", "fold", "target"), "case")
        digest(case['case_id'], "opaque case ID")
        if case['case_id'] in indexed:
            raise Invalid("duplicate case ID")
        digest(case['participant'], "case participant")
        if case['participant'] not in assignments:
            raise Invalid("case outside fixed cohort")
        integer(case['session'], 3, 3, "evaluation session")
        integer(case['block'], 0, 1000000, "source block index")
        integer(case['fold'], 0, 4, "case fold")
        integer(case['target'], 0, 2, "target class")
        if case['fold'] != assignments[case['participant']]:
            raise Invalid("case fold conflicts with precommitted partition")
        block = (case['participant'], case['session'], case['block'])
        if block in blocks:
            raise Invalid("duplicate source block")
        blocks.add(block)
        support[case['participant']][case['target']] += 1
        indexed[case['case_id']] = case
    if any(min(counts) == 0 for counts in support.values()):
        raise Invalid("every participant must have every class; denominator cannot shrink")
    return indexed, assignments, support


def validate_submission(submission, case_ids):
    exact_keys(submission, ("schema", "task", "predictions"), "submission")
    if submission['schema'] != "stroop55-predictions-v1" or submission['task'] != TASK:
        raise Invalid("submission schema/task mismatch")
    if not isinstance(submission['predictions'], list) or len(submission['predictions']) != len(case_ids):
        raise Invalid("one prediction per precommitted case required")
    predictions = {}
    for row in submission['predictions']:
        exact_keys(row, ("case_id", "probabilities", "label"), "prediction")
        case_id = row['case_id']
        digest(case_id, "case ID")
        if case_id not in case_ids or case_id in predictions:
            raise Invalid("unknown or duplicate prediction")
        p = row['probabilities']
        if not isinstance(p, list) or len(p) != 3:
            raise Invalid("three probabilities required")
        if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in p):
            raise Invalid("finite probabilities in[0,1] required")
        if abs(math.fsum(p) - 1) > 1e-9:
            raise Invalid("probabilities must sum to1; no renormalization")
        expected = CLASSES[max(range(3), key=lambda k: p[k])]
        if row['label'] != expected:
            raise Invalid("label must match argmax; ties use first class in fixed order")
        predictions[case_id] = p
    if set(predictions) != set(case_ids):
        raise Invalid("incomplete prediction coverage")
    return predictions


def evaluate(manifest, submission):
    cases, assignments, support = validate_manifest(manifest)
    predictions = validate_submission(submission, cases)
    grouped = {person: [] for person in assignments}
    for case_id, case in cases.items():
        p = predictions[case_id]
        target = case['target']
        prediction = max(range(3), key=lambda k: p[k])
        brier = math.fsum((p[k] - int(k == target)) ** 2 for k in range(3))
        # Clip only the true-class log argument. Do not re-normalize any vector.
        loss = -math.log(max(EPSILON, p[target]))
        grouped[case['participant']].append((target, prediction, brier, loss))
    persons = []
    for person in sorted(assignments):
        rows = grouped[person]
        confusion = [[0] * 3 for _ in range(3)]
        for target, prediction, _, _ in rows:
            confusion[target][prediction] += 1
        recalls = [confusion[k][k] / support[person][k] for k in range(3)]
        persons.append({"participant": person, "fold": assignments[person], "blocks": len(rows),
                        "class_support": support[person], "confusion_true_by_predicted": confusion,
                        "recall": recalls, "balanced_accuracy": math.fsum(recalls) / 3,
                        "brier_sum3": math.fsum(row[2] for row in rows) / len(rows),
                        "log_loss": math.fsum(row[3] for row in rows) / len(rows)})
    metrics = ("balanced_accuracy", "brier_sum3", "log_loss")
    macro = {metric: math.fsum(p[metric] for p in persons) / PEOPLE for metric in metrics}
    folds = [{"fold": fold, "participants": 11,
              **{m: math.fsum(p[m] for p in persons if p['fold'] == fold) / 11 for m in metrics}}
             for fold in range(FOLDS)]
    return {"task": TASK, "status": "complete_declared_census_scored",
            "participants": PEOPLE, "source_session_metadata_count": 165,
            "evaluation_session": 3, "cases": len(cases), "class_order": list(CLASSES),
            "primary": {"name": "mean_participant_balanced_accuracy", "value": macro['balanced_accuracy']},
            "secondary": {"participant_mean_brier_sum3": macro['brier_sum3'],
                          "participant_mean_log_loss": macro['log_loss'], "log_clip_epsilon": EPSILON},
            "per_participant": persons, "per_fold": folds,
            "limits": ["Declared census completeness is not source-data authenticity or eligibility validation.",
                       "Session3 is intended evaluation; protected exposure/independence is not established here.",
                       "No empirical baseline, confidence interval, model, clinical or cortical-specificity claim."]}


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Invalid("duplicate JSON key")
        result[key] = value
    return result


def load_json(path, expected_sha256=None):
    p = Path(path)
    if any(part.is_symlink() for part in (p, *p.parents)):
        raise Invalid("symlink operand or ancestor")
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_size > CAP or info.st_nlink != 1:
        os.close(fd)
        raise Invalid("bounded ordinary JSON file required")
    with os.fdopen(fd, 'rb') as f:
        body = f.read(CAP + 1)
    if len(body) > CAP:
        raise Invalid("file exceeded byte cap")
    if expected_sha256 is not None:
        digest(expected_sha256, "externally frozen manifest digest")
        if hashlib.sha256(body).hexdigest() != expected_sha256:
            raise Invalid("manifest bytes differ from external freeze")
    try:
        obj = json.loads(body, object_pairs_hook=strict_object,
                         parse_constant=lambda _: (_ for _ in ()).throw(Invalid("nonfinite JSON")))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise Invalid("invalid JSON") from exc
    return obj


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--submission', required=True)
    args = parser.parse_args()
    manifest = load_json(args.manifest, args.manifest_sha256)
    submission = load_json(args.submission)
    print(json.dumps(evaluate(manifest, submission), allow_nan=False, sort_keys=True, separators=(',', ':')))


if __name__ == '__main__':
    main()
