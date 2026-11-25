"""Compare two complete NEURAL-084 access conditions on identical source cases.

This operator-only scorer establishes matched cases, not participant isolation,
equal perceptual information, method provenance, or authentic-data qualification.
"""
import argparse
import hashlib
import os
from pathlib import Path
from types import ModuleType

HERE = Path(__file__).resolve().parent
SOURCE_PINS = {
    "full-cohort-scoring-v1/score.py":
        "da991b4fd0d8ce571ba9858703650db49e5aac9f42328ddb26ad69bee7a8742e",
    "delivery-source/public/io_utils.py":
        "9ba54409ff3aae8e17d2c0e96f1c5f335fa46cd33aeaf83d3be427a8ebf585d7",
}


def source():
    # The optional location is trusted operator configuration for source mirrors.
    root = Path(os.environ.get("NEURAL084_SOURCE_IMPLEMENTATIONS", HERE.parent))
    captured = {}
    extents = {"full-cohort-scoring-v1/score.py": 10715,
               "delivery-source/public/io_utils.py": 4396}
    for name, expected in SOURCE_PINS.items():
        with (root / name).open("rb") as stream:
            raw = stream.read(extents[name] + 1)
        if len(raw) != extents[name] or hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Exact reviewed scoring source required: " + name)
        captured[name] = raw
    path = root / "full-cohort-scoring-v1/score.py"
    module = ModuleType("neural084_paired_dependency")
    module.__file__ = str(path)
    # Execute the bytes whose identity was checked, never reopen their pathname.
    # The scorer independently captures, checks and executes its IO dependency.
    exec(compile(captured["full-cohort-scoring-v1/score.py"], str(path), "exec"),
         module.__dict__)
    return module


s = source()
io = s.io
MODES = ("restricted", "program", "cca", "constant", "frequency-permuted")


def difference(left, right):
    """Retain all original person/session/phase strata; never select by outcome."""
    result = {"mean": left["score"] - right["score"]}
    for field, keys in (("people", ("person",)),
                        ("sessions", ("person", "session")),
                        ("phases", ("person", "session", "phase"))):
        rows = []
        for a, b in zip(left[field], right[field]):
            io.need(all(a[key] == b[key] for key in keys), "Exact paired stratum")
            rows.append(dict({key: a[key] for key in keys},
                             difference=a["score"] - b["score"]))
        result[field] = rows
    return result


def paired_counts(predictions, folds, targets):
    """Descriptive within-case correctness; no independent-trial inference."""
    people = []
    names = ("both_correct", "restricted_only", "program_only", "neither_correct")
    total = dict.fromkeys(names, 0)
    for person, (fold, identities) in zip(s.PEOPLE, folds.items()):
        counts = dict.fromkeys(names, 0)
        for identity, restricted, program in zip(
                identities, predictions["restricted"][fold], predictions["program"][fold]):
            truth = targets[identity][1]
            category = ("both_correct" if restricted == truth and program == truth else
                        "restricted_only" if restricted == truth else
                        "program_only" if program == truth else "neither_correct")
            counts[category] += 1
        people.append(dict(person=person, queries=400, **counts))
        for name in names:
            total[name] += counts[name]
    return dict(queries=21600, people=people, **total)


def grade(pool_raw, prediction_loader, gold_loader):
    """Admit all270 supplied outputs before opening gold exactly once.

    Callbacks are trusted operator IO. Both candidate conditions and the three
    controls must use the exact existing generation/fold/ordered-ID interface.
    A mode name records the intended condition; it cannot prove its execution.
    """
    generation, gold_pin, source_rows, folds = s.pool_contract(pool_raw)
    predictions = {}
    receipts = {}
    for mode in MODES:
        predictions[mode] = {}
        receipts[mode] = {}
        for fold, identities in folds.items():
            raw = prediction_loader(mode, fold)
            predictions[mode][fold] = s.prediction(raw, generation, fold, identities)
            receipts[mode][fold] = io.pin(raw)
    targets = s.gold_contract(gold_loader(gold_pin), generation, source_rows, gold_pin)
    modes = {mode: s.aggregate(predictions[mode], folds, targets) for mode in MODES}
    comparisons = {"program_minus_restricted": difference(modes["program"], modes["restricted"])}
    for candidate in ("restricted", "program"):
        for control in MODES[2:]:
            comparisons[candidate + "_minus_" + control] = difference(modes[candidate], modes[control])
    return dict(schema="neural084_paired_access_scores_v1", task_id="NEURAL-084",
                metric="equal_person_session_phase_class_balanced_accuracy",
                classes=list(s.CLASSES), directions=["up", "left", "right", "down"],
                nominal_frequencies_hz=[60 / n for n in (5, 7, 9, 11)],
                counts=dict(people=54, phases=216, queries=21600, modes=5),
                source=dict(pool=io.pin(pool_raw), gold=gold_pin, predictions=receipts,
                            scoring_dependencies=SOURCE_PINS),
                comparison_scope=dict(case_support="same_pool_and_exact_ordered_ids",
                    information_equivalence="not_established_by_scoring",
                    access_enforcement="not_established_by_scoring",
                    method_provenance="not_established_by_scoring"),
                modes=modes, comparisons=comparisons,
                matched_correctness=paired_counts(predictions, folds, targets))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--pool-bytes", required=True, type=int)
    parser.add_argument("--pool-sha256", required=True)
    for mode in MODES:
        parser.add_argument("--" + mode, required=True,
                            help="Directory containing exactly54 foldNNN.json submissions")
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    pool_path = io.regular(args.pool)
    pool_raw = io.read(pool_path, s.JSON_CAP,
                       dict(bytes=args.pool_bytes, sha256=args.pool_sha256))
    roots = {mode: io.regular(getattr(args, mode.replace("-", "_"))) for mode in MODES}
    io.need(len(set(roots.values())) == len(MODES), "Five distinct condition/control directories")
    names = {"fold%03d.json" % person for person in s.PEOPLE}
    for root in roots.values():
        io.need(root.is_dir() and {p.name for p in root.iterdir()} == names,
                "Exactly54 prediction files per condition/control")
    report = grade(pool_raw,
        lambda mode, fold: io.read(roots[mode] / (fold + ".json"), s.PRED_CAP),
        lambda pin: io.read(pool_path.parent / "gold.json", s.JSON_CAP, pin))
    io.put(args.out, report, s.JSON_CAP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
