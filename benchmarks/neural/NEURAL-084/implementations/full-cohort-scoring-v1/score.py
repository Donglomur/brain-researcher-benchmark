"""Operator-only full54 scorer for the existing OpenBMI raw-score interface.

No arrays, candidate code, fitting, source acquisition, or clinical inference.
All four modes' complete predictions are captured before opening gold.
"""
import argparse
from collections import Counter
import importlib.util
import math
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "neural084_scoring_io", HERE.parent / "delivery-source/public/io_utils.py")
io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(io)
PEOPLE = tuple(range(1, 55))
SESSIONS = (1, 2)
PHASES = ("train", "test")
CLASSES = (1, 2, 3, 4)
MODES = ("candidate", "cca", "constant", "frequency-permuted")
JSON_CAP = 5000000
PRED_CAP = 262144


def generation(value):
    # Matches the existing producer contracts._generation interface.
    io.need(type(value) is str and 0 < len(value.encode("utf-8")) <= 256,
            "Bounded source generation")


def ids(values, count):
    io.need(type(values) is list and len(values) == count, "Complete ID support")
    previous = None
    for value in values:
        io.need(type(value) is str and re.fullmatch("[a-f0-9]{64}", value), "Opaque ID")
        io.need(previous is None or previous < value, "Strictly sorted unique IDs")
        previous = value


def pool_contract(raw):
    io.need(type(raw) is bytes and 0 < len(raw) <= JSON_CAP, "Bounded pool")
    pool = io.decode(raw)
    io.exact(pool, ("schema", "generation", "assets", "gold"))
    io.need(pool["schema"] == "neural084_pool_v1", "Existing pool schema")
    generation(pool["generation"])
    io.exact(pool["gold"], ("path", "bytes", "sha256"))
    io.need(pool["gold"]["path"] == "gold.json", "Original gold basename")
    gold_pin = {key: pool["gold"][key] for key in ("bytes", "sha256")}
    io.check_pin(gold_pin, JSON_CAP)
    expected = [(p, s, h) for p in PEOPLE for s in SESSIONS for h in PHASES]
    io.need(type(pool["assets"]) is list and len(pool["assets"]) == 216,
            "Full216 phase assets")
    seen = set()
    rows = []
    by_person = {person: [] for person in PEOPLE}
    for asset, key in zip(pool["assets"], expected):
        io.exact(asset, ("person", "session", "phase", "signals", "ids"))
        io.need(type(asset["person"]) is int and type(asset["session"]) is int
                and (asset["person"], asset["session"], asset["phase"]) == key,
                "Original full54x2x2 source order")
        io.exact(asset["signals"], ("path", "bytes", "sha256"))
        io.need(asset["signals"]["path"] == "p%02d-s%d-%s.npy" % key,
                "Original phase array basename")
        io.check_pin({k: asset["signals"][k] for k in ("bytes", "sha256")}, 1638400)
        ids(asset["ids"], 100)
        for identity in asset["ids"]:
            io.need(identity not in seen, "Disjoint complete query identities")
            seen.add(identity)
            rows.append((identity, *key))
            by_person[key[0]].append(identity)
    return pool["generation"], gold_pin, tuple(rows), {
        "fold%03d" % p: tuple(sorted(by_person[p])) for p in PEOPLE}


def prediction(raw, selected_generation, fold, expected_ids):
    io.need(type(raw) is bytes and 0 < len(raw) <= PRED_CAP, "Bounded prediction")
    value = io.decode(raw)
    io.exact(value, ("schema", "generation", "fold", "predictions"))
    io.need(value["schema"] == "neural084_scores_v1"
            and value["generation"] == selected_generation and value["fold"] == fold,
            "Exact supplied prediction schema/generation/fold")
    predictions = value["predictions"]
    io.need(type(predictions) is list and len(predictions) == 400, "All400 predictions")
    winners = []
    for expected_id, row in zip(expected_ids, predictions):
        io.exact(row, ("id", "scores"))
        io.need(row["id"] == expected_id, "Exact ordered query ID")
        scores = row["scores"]
        io.need(type(scores) is list and len(scores) == 4 and all(
            type(score) in (int, float) and math.isfinite(score) for score in scores),
            "Four finite nonboolean raw scores")
        # Python max retains the first index when equal; no softmax/calibration.
        winners.append(max(range(4), key=scores.__getitem__) + 1)
    return tuple(winners)


def gold_contract(raw, selected_generation, source_rows, expected_pin):
    io.need(type(raw) is bytes and io.pin(raw) == expected_pin, "Exact selected gold")
    gold = io.decode(raw)
    io.exact(gold, ("schema", "generation", "rows"))
    io.need(gold["schema"] == "neural084_gold_v1"
            and gold["generation"] == selected_generation, "Original gold generation")
    io.need(type(gold["rows"]) is list and len(gold["rows"]) == 21600,
            "Full21600 labels")
    counts = Counter()
    targets = {}
    for row, source_row in zip(gold["rows"], source_rows):
        io.exact(row, ("id", "person", "session", "phase", "label"))
        io.need(type(row["person"]) is int and type(row["session"]) is int
                and tuple(row[k] for k in ("id", "person", "session", "phase")) == source_row,
                "Exact source-order identity/person/session/phase join")
        label = row["label"]
        io.need(type(label) is int and label in CLASSES, "Original four source classes")
        key = source_row[1:]
        counts[key + (label,)] += 1
        targets[row["id"]] = (key, label)
    io.need(len(counts) == 864 and set(counts.values()) == {25},
            "Exactly25 labels per person/session/phase/class; no exclusions")
    return targets


def aggregate(winners, folds, targets):
    matrices = {(p, s, h): [[0] * 4 for _ in CLASSES]
                for p in PEOPLE for s in SESSIONS for h in PHASES}
    for fold, identities in folds.items():
        for identity, predicted in zip(identities, winners[fold]):
            key, truth = targets[identity]
            matrices[key][truth - 1][predicted - 1] += 1
    phases = []
    phase_scores = {}
    confusion = [[0] * 4 for _ in CLASSES]
    for key, matrix in matrices.items():
        support = [sum(row) for row in matrix]
        recall = [matrix[i][i] / support[i] for i in range(4)]
        score = math.fsum(recall) / 4
        phase_scores[key] = score
        phases.append(dict(person=key[0], session=key[1], phase=key[2],
                           confusion=matrix, support=support, recall=recall, score=score))
        for i in range(4):
            for j in range(4):
                confusion[i][j] += matrix[i][j]
    sessions = [dict(person=p, session=s, score=math.fsum(
        phase_scores[(p, s, h)] for h in PHASES) / 2) for p in PEOPLE for s in SESSIONS]
    people = [dict(person=p, score=math.fsum(
        row["score"] for row in sessions if row["person"] == p) / 2) for p in PEOPLE]
    return dict(score=math.fsum(row["score"] for row in people) / 54,
                people=people, sessions=sessions, phases=phases,
                confusion=confusion, support=[sum(row) for row in confusion],
                recall=[confusion[i][i] / sum(confusion[i]) for i in range(4)])


def grade(pool_raw, prediction_loader, gold_loader):
    """Load callbacks are trusted operator IO, never participant-supplied code.

    prediction_loader(mode, fold) returns the existing strict JSON bytes.
    gold_loader(pin) is called exactly once, only after all216 valid submissions.
    Only aggregate cells/person scores and content hashes leave this function.
    """
    selected_generation, gold_pin, source_rows, folds = pool_contract(pool_raw)
    predictions = {}
    receipts = {}
    for mode in MODES:
        predictions[mode] = {}
        receipts[mode] = {}
        for fold, expected_ids in folds.items():
            raw = prediction_loader(mode, fold)
            predictions[mode][fold] = prediction(raw, selected_generation, fold, expected_ids)
            receipts[mode][fold] = io.pin(raw)
    # Captured winners are immutable and do not reread candidate files after gold.
    targets = gold_contract(gold_loader(gold_pin), selected_generation, source_rows, gold_pin)
    results = {mode: aggregate(predictions[mode], folds, targets) for mode in MODES}
    paired = {}
    for comparator in MODES[1:]:
        differences = [dict(person=a["person"], difference=a["score"] - b["score"])
                       for a, b in zip(results["candidate"]["people"], results[comparator]["people"])]
        paired[comparator] = dict(mean=math.fsum(r["difference"] for r in differences) / 54,
                                  people=differences)
    return dict(schema="neural084_full_cohort_scores_v1", task_id="NEURAL-084",
                metric="equal_person_session_phase_class_balanced_accuracy",
                classes=list(CLASSES), directions=["up", "left", "right", "down"],
                nominal_frequencies_hz=[60 / n for n in (5, 7, 9, 11)],
                counts=dict(people=54, phases=216, queries=21600, modes=4),
                source=dict(pool=io.pin(pool_raw), gold=gold_pin, predictions=receipts),
                modes=results, candidate_minus=paired)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--pool-bytes", required=True, type=int)
    parser.add_argument("--pool-sha256", required=True)
    for mode in MODES:
        parser.add_argument("--" + mode, required=True, help="Directory with all54 foldNNN.json files")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    expected = dict(bytes=args.pool_bytes, sha256=args.pool_sha256)
    pool_path = io.regular(args.pool)
    pool_raw = io.read(pool_path, JSON_CAP, expected)
    roots = {mode: io.regular(getattr(args, mode.replace("-", "_"))) for mode in MODES}
    names = {"fold%03d.json" % person for person in PEOPLE}
    io.need(len(set(roots.values())) == 4, "Four distinct mode directories")
    for root in roots.values():
        io.need(root.is_dir() and {p.name for p in root.iterdir()} == names,
                "Exactly54 prediction files per mode")
    report = grade(pool_raw, lambda mode, fold: io.read(roots[mode] / (fold + ".json"), PRED_CAP),
                   lambda pin: io.read(pool_path.parent / "gold.json", JSON_CAP, pin))
    io.put(args.out, report, JSON_CAP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
