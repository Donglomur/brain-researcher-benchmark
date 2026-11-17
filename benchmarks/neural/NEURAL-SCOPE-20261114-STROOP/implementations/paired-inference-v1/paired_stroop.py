"""Same-case Stroop55 comparisons and conditional participant bootstrap.

Evaluator-only: this consumes the private manifest and already frozen outputs.
It does not fit models, access signals, establish authenticity, or enforce access.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import types


CORE_SHA256 = "6f41c9fb318ce079e0d83ceb9fd480d503e96df42ea24ab1a62e2f949745af3e"


def _load_core():
    path = Path(__file__).absolute().parent.parent / "stroop55-evaluator" / "stroop.py"
    body = path.read_bytes()
    if hashlib.sha256(body).hexdigest() != CORE_SHA256:
        raise RuntimeError("Stroop55 dependency differs from the reviewed source")
    module = types.ModuleType("stroop55_pinned_core")
    module.__file__ = str(path)
    # Execute exactly the authenticated bytes, without a second path read.
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


core = _load_core()
Invalid = core.Invalid
METRICS = ("balanced_accuracy", "brier_sum3", "log_loss")
DOMAIN = b"stroop55-paired-conditional-bootstrap-v1\x00"
MIN_RESAMPLES = 1000
MAX_RESAMPLES = 20000


def _indices(seed_hex):
    """Uniform 0..54 stream, independent of Python's random implementation.

    SHA256(domain || 32 seed bytes || 16-byte big-endian counter), counter
    starting at zero. Read four big-endian uint64 words per digest. Reject
    the top incomplete modulo-55 interval; accepted word modulo 55 is an index.
    """
    prefix = DOMAIN + bytes.fromhex(seed_hex)
    limit = (2 ** 64 // core.PEOPLE) * core.PEOPLE
    counter = 0
    while True:
        block = hashlib.sha256(prefix + counter.to_bytes(16, "big")).digest()
        counter += 1
        for offset in range(0, 32, 8):
            word = int.from_bytes(block[offset:offset + 8], "big")
            if word < limit:
                yield word % core.PEOPLE


def _interval(values):
    """95% percentile interval, linear interpolation at (n-1)*q (type 7)."""
    ordered = sorted(values)

    def quantile(numerator):
        position, remainder = divmod((len(ordered) - 1) * numerator, 40)
        lower = ordered[position]
        if remainder == 0:
            return lower
        return lower + (ordered[position + 1] - lower) * (remainder / 40)

    return [quantile(1), quantile(39)]


def compare(manifest, candidate, comparator, *, bootstrap_seed, resamples=10000):
    """Score both complete outputs against one manifest; resample whole people.

    Every draw samples 55 people with replacement, using the same draw for
    every metric and both arms. Neither blocks nor the five dependent folds
    are treated as independent replicates. Raw deltas are candidate minus
    comparator, so negative Brier/log-loss deltas favor the candidate.
    """
    core.digest(bootstrap_seed, "bootstrap seed")
    core.integer(resamples, MIN_RESAMPLES, MAX_RESAMPLES, "bootstrap resamples")
    # Reuse the unchanged complete-census, probability, split and metric rules.
    # The same private labels and case census admit both methods, with no join
    # by row order, intersection-only scoring, dropped cases, or changed target.
    left = core.evaluate(manifest, candidate)
    right = core.evaluate(manifest, comparator)
    right_people = {p["participant"]: p for p in right["per_participant"]}
    persons = []
    for p in left["per_participant"]:
        q = right_people[p["participant"]]
        persons.append({
            "participant": p["participant"], "fold": p["fold"],
            "blocks": p["blocks"], "class_support": p["class_support"],
            "candidate": {m: p[m] for m in METRICS},
            "comparator": {m: q[m] for m in METRICS},
            "candidate_minus_comparator": {m: p[m] - q[m] for m in METRICS},
        })

    arms = ("candidate", "comparator", "candidate_minus_comparator")
    vectors = {(a, m): [p[a][m] for p in persons] for a in arms for m in METRICS}
    samples = {key: [] for key in vectors}
    stream = _indices(bootstrap_seed)
    for _ in range(resamples):
        draw = [next(stream) for _ in range(core.PEOPLE)]
        for key, vector in vectors.items():
            samples[key].append(math.fsum(vector[index] for index in draw) / core.PEOPLE)

    metrics = {}
    for metric in METRICS:
        metrics[metric] = {
            "direction": "higher" if metric == "balanced_accuracy" else "lower",
            **{arm: {
                "estimate": math.fsum(vectors[arm, metric]) / core.PEOPLE,
                "conditional_percentile_95": _interval(samples[arm, metric]),
            } for arm in arms},
        }
    folds = []
    for fold in range(core.FOLDS):
        members = [p for p in persons if p["fold"] == fold]
        folds.append({
            "fold": fold, "participants": len(members),
            **{arm: {m: math.fsum(p[arm][m] for p in members) / len(members)
                     for m in METRICS} for arm in arms},
        })
    return {
        "schema": "stroop55-paired-conditional-v1", "task": core.TASK,
        "status": "complete_declared_census_paired_scored",
        "participants": core.PEOPLE, "cases": left["cases"],
        "source_session_metadata_count": 165, "evaluation_session": 3,
        "class_order": list(core.CLASSES),
        "primary_metric": "balanced_accuracy", "metrics": metrics,
        "delta_definition": "candidate_minus_comparator; negative error-metric deltas favor candidate",
        "per_participant": persons, "per_fold": folds,
        "bootstrap": {
            "unit": "participant", "participants_per_resample": core.PEOPLE,
            "replacement": True, "paired_across_methods_and_metrics": True,
            "resamples": resamples, "seed": bootstrap_seed,
            "stream": "sha256-counter-uint64-rejection-v1",
            "participant_order": "ascending opaque participant ID",
            "interval": "percentile_2.5_97.5_linear_type7",
            "scope": "descriptive_conditional_on_fixed_predictions_cohort_folds_and_observed_session3_schedule",
        },
        "log_clip_epsilon": core.EPSILON, "scorer_source_sha256": CORE_SHA256,
        "limits": [
            "Declared complete census is not source authenticity, biological identity or eligibility proof.",
            "No refitting, training-set, model-fitting, prompt-selection or new-schedule uncertainty is included.",
            "Overlapping outer-fold training sets preclude unconditional independent-replication inference.",
            "The comparator is supplied; its competence, train-only fitting and matched information require separate audit.",
            "No superiority decision, multiplicity correction, causal tool benefit or cortical-specificity claim is made.",
            "Program performance cannot establish direct or viewer interpretation; access modes remain separate.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "candidate", "comparator"):
        parser.add_argument("--" + name, required=True)
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--bootstrap-seed", required=True)
    parser.add_argument("--resamples", type=int, default=10000)
    args = parser.parse_args(argv)
    operands = {}
    identities = {}
    for name in ("manifest", "candidate", "comparator"):
        digest = getattr(args, name + "_sha256")
        operands[name] = core.load_json(getattr(args, name), digest)
        identities[name + "_sha256"] = digest
    result = compare(**operands, bootstrap_seed=args.bootstrap_seed, resamples=args.resamples)
    result["input_byte_identities"] = identities
    print(json.dumps(result, allow_nan=False, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
