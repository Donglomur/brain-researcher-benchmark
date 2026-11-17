"""Import source decoder results and reconstruct both documented effect vectors.

Operator use only: the bundle contains targets. No fitting, acquisition, candidate
admission, or scientific qualification is performed. See README for the JSON API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median

REVISION = "118fc36cb3602934466ad2c6087c2b3b441f9f1f"
FREEZE = "2023_12_bwm_release"
# Author formatted tables use one-based run IDs, although raw fit outputs use 0.
ENDPOINTS = {"stimulus_side": (10, 200), "choice": (10, 200),
             "feedback": (10, 200), "wheel_speed": (2, 100),
             "wheel_velocity": (2, 100)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), "finite numeric value required")
    return float(value)


def unique_strings(values, name):
    require(isinstance(values, list) and values and
            all(isinstance(x, str) and x for x in values) and
            len(values) == len(set(values)), f"unique nonempty {name} required")
    return values


def cell_key(row):
    return tuple(row[x] for x in ("endpoint", "eid", "region"))


def balanced_accuracy(targets, probabilities):
    """Author prediction-recheck convention: exactly 0.5 selects class zero."""
    require(len(targets) == len(probabilities) and len(targets) > 0, "binary support mismatch")
    y = [float(x) if type(x) is bool else number(x) for x in targets]
    p = [number(x) for x in probabilities]
    require(set(y) == {0.0, 1.0}, "binary targets need both 0 and 1")
    require(all(0 <= x <= 1 for x in p), "probabilities outside [0,1]")
    return sum(sum((p[i] > 0.5) == c for i in range(len(y)) if y[i] == c) /
               y.count(c) for c in (0.0, 1.0)) / 2


def r_squared(targets, predictions):
    """Concatenated source sklearn 1.1.2 R2, including force_finite=True."""
    require(len(targets) == len(predictions) and len(targets) >= 2, "R2 needs >=2 aligned values")
    y, p = [number(x) for x in targets], [number(x) for x in predictions]
    mean = math.fsum(y) / len(y)
    denominator = math.fsum((v - mean) ** 2 for v in y)
    numerator = math.fsum((a - b) ** 2 for a, b in zip(y, p))
    require(math.isfinite(denominator) and math.isfinite(numerator), "R2 arithmetic overflow")
    if denominator == 0:
        return 1.0 if numerator == 0 else 0.0
    return 1.0 - numerator / denominator


def partition(folds, n_trials):
    require(isinstance(folds, list) and len(folds) == 5, "five outer folds required")
    flat = []
    for fold in folds:
        require(isinstance(fold, list) and fold and
                all(type(i) is int and 0 <= i < n_trials for i in fold), "invalid fold indices")
        flat.extend(fold)
    require(sorted(flat) == list(range(n_trials)), "outer folds must cover each trial exactly once")
    return [sorted(f) for f in folds]


def flatten_trials(values, counts, boolean_labels=False):
    require(isinstance(values, list) and len(values) == len(counts), "trial count mismatch")
    flat = []
    for values_in_trial, count in zip(values, counts):
        require(isinstance(values_in_trial, list) and len(values_in_trial) == count,
                "within-trial bin support mismatch")
        flat.extend(float(x) if boolean_labels and type(x) is bool else number(x) for x in values_in_trial)
    return flat


def score_real(row, cell):
    """Recompute a full run from original-order per-trial prediction vectors."""
    require(row["trial_ids"] == cell["trial_ids"], "retained trial identities/order changed")
    require(row["unit_ids"] == cell["unit_ids"], "population unit identities/order changed")
    require(row["pids"] == cell["pids"], "merged-probe identity changed")
    require(row["subject"] == cell["subject"], "mouse identity changed")
    require(type(row["n_units"]) is int and row["n_units"] == len(cell["unit_ids"]),
            "unit count mismatch")
    actual_folds = partition(row["idxes_test"], len(cell["trial_ids"]))
    expected = cell["outer_folds"][str(row["run_id"])]
    require(actual_folds == partition(expected, len(cell["trial_ids"])), "frozen fold membership changed")
    binary = ENDPOINTS[cell["endpoint"]][0] == 10
    target = flatten_trials(row["targets"], cell["bin_counts"], boolean_labels=binary)
    predicted = flatten_trials(row["predictions"], cell["bin_counts"])
    metric = balanced_accuracy if binary else r_squared
    score = metric(target, predicted)
    require(math.isclose(score, number(row["score"]), rel_tol=1e-9, abs_tol=1e-10),
            "stored score disagrees with concatenated out-of-fold predictions")
    return score, digest(row["targets"])


def fisher(pvalues):
    """Chi-square survival with 2k df via the integer gamma survival series."""
    require(pvalues and all(0 < p <= 1 for p in pvalues), "positive Fisher p values required")
    x = -math.fsum(math.log(p) for p in pvalues)
    if x == 0:
        return 1.0
    logs = [i * math.log(x) - math.lgamma(i + 1) for i in range(len(pvalues))]
    largest = max(logs)
    return min(1.0, math.exp(-x + largest + math.log(math.fsum(math.exp(v-largest) for v in logs))))


def bh(values):
    order = sorted(range(len(values)), key=lambda i: values[i])
    adjusted = [0.0] * len(values)
    running = 1.0
    for rank in range(len(values), 0, -1):
        index = order[rank - 1]
        running = min(running, values[index] * len(values) / rank)
        adjusted[index] = running
    return adjusted


def validate_roster(roster):
    require(roster["schema"] == "brainwide-decoder-roster/v1", "roster schema mismatch")
    require(roster["source_revision"] == REVISION and roster["freeze"] == FREEZE, "source pins changed")
    require(roster["evidence_kind"] in ("generated_control", "unverified_source_export"), "invalid evidence kind")
    cells = roster["cells"]
    require(isinstance(cells, list) and cells, "nonempty frozen roster required")
    keys = [cell_key(c) for c in cells]
    require(len(keys) == len(set(keys)), "duplicate endpoint/session/region")
    require({k[0] for k in keys} == set(ENDPOINTS), "all five original endpoints required")
    mice = {}
    unit_owners = {}
    regions = {}
    for c in cells:
        require(all(isinstance(c[x], str) and c[x] for x in ("eid", "region", "subject")), "invalid cell identity")
        require(c["eid"] not in mice or mice[c["eid"]] == c["subject"], "session maps to multiple mice")
        mice[c["eid"]] = c["subject"]
        unique_strings(c["trial_ids"], "trial IDs")
        unique_strings(c["unit_ids"], "unit IDs")
        unique_strings(c["pids"], "probe IDs")
        require(len(c["unit_ids"]) >= 5, "source figure requires >=5 merged population units")
        for u in c["unit_ids"]:
            owner = (c["eid"], c["region"])
            require(u not in unit_owners or unit_owners[u] == owner, "unit assigned to different session/region")
            unit_owners[u] = owner
        counts = c["bin_counts"]
        require(isinstance(counts, list) and len(counts) == len(c["trial_ids"]) and
                all(type(n) is int and n > 0 for n in counts), "invalid bin support")
        runs, _ = ENDPOINTS[c["endpoint"]]
        require(runs != 10 or set(counts) == {1}, "binary endpoints have one value per trial")
        require(set(c["outer_folds"]) == {str(i) for i in range(1, runs+1)}, "complete source runs required")
        for folds in c["outer_folds"].values():
            partition(folds, len(counts))
        regions.setdefault((c["endpoint"], c["region"]), set()).add(c["eid"])
    require(all(len(eids) >= 2 for eids in regions.values()), "source regional effect needs >=2 sessions")
    return {cell_key(c): c for c in cells}


def summarize_session(real_scores, null_scores):
    real = math.fsum(real_scores) / len(real_scores)
    nulls = [math.fsum(scores) / len(scores) for scores in null_scores]
    source_null = median([real, *nulls])
    paper_null = median(nulls)
    return {"real_score": real, "source_median_including_observed": source_null,
            "paper_null_only_median": paper_null,
            "paper_corrected_score": real - paper_null,
            "source_session_p": (1 + sum(v >= real for v in nulls)) / (1 + len(nulls)),
            "n_null": len(nulls), "n_runs": len(real_scores)}


def summarize_regions(sessions):
    groups = {}
    for row in sessions:
        groups.setdefault((row["endpoint"], row["region"]), []).append(row)
    output = []
    for (endpoint, region), rows in sorted(groups.items()):
        output.append({"endpoint": endpoint, "region": region, "n_sessions": len(rows),
                       "n_mice": len({r["subject"] for r in rows}),
                       "source_figure_effect": median(r["real_score"] for r in rows) -
                           median(r["source_median_including_observed"] for r in rows),
                       "paper_text_effect": median(r["paper_corrected_score"] for r in rows),
                       "source_fisher_p": fisher([r["source_session_p"] for r in rows]),
                       "source_fraction_significant_sessions": sum(r["source_session_p"] < .05 for r in rows)/len(rows)})
    for endpoint in ENDPOINTS:
        family = [r for r in output if r["endpoint"] == endpoint]
        for row, q in zip(family, bh([r["source_fisher_p"] for r in family])):
            row.update(source_bh_q=q, source_significant=q < .01, source_family_size=len(family))
    return output


def evaluate(roster, bundle):
    cells = validate_roster(roster)
    require(bundle["schema"] == "brainwide-decoder-formatted-export/v1", "bundle schema mismatch")
    require(bundle["roster_digest"] == digest(roster), "bundle bound to different frozen roster")
    indexed = {key: {} for key in cells}
    for row in bundle["records"]:
        key = cell_key(row)
        require(key in cells, "unexpected endpoint/session/region")
        runs, nulls = ENDPOINTS[key[0]]
        pseudo, run = row["pseudo_id"], row["run_id"]
        require(type(pseudo) is int and pseudo in [-1, *range(1, nulls+1)] and
                type(run) is int and 1 <= run <= runs, "invalid source pseudo/run ID")
        require((pseudo, run) not in indexed[key], "duplicate pseudo/run leaf")
        value = number(row["score"])
        require(value <= 1 and (runs != 10 or value >= 0), "score outside metric range")
        indexed[key][pseudo, run] = row
    sessions = []
    for key, cell in sorted(cells.items()):
        runs, nulls = ENDPOINTS[key[0]]
        records = indexed[key]
        require(len(records) == (nulls+1)*runs, "missing planned real/null run leaves")
        real, target_hashes = [], set()
        for run in range(1, runs+1):
            value, target_hash = score_real(records[-1, run], cell)
            real.append(value)
            target_hashes.add(target_hash)
        require(len(target_hashes) == 1, "real targets changed across CV repetitions")
        null = [[number(records[pseudo, run]["score"]) for run in range(1, runs+1)]
                for pseudo in range(1, nulls+1)]
        sessions.append({"endpoint": key[0], "eid": key[1], "region": key[2],
                         "subject": cell["subject"], "n_units": len(cell["unit_ids"]),
                         "n_trials": len(cell["trial_ids"]), **summarize_session(real, null)})
    return {"schema": "brainwide-decoder-score-report/v1", "task_id": "PAPER-FIND-005",
            "roster_digest": digest(roster), "bundle_digest": digest(bundle),
            "evidence_kind": roster["evidence_kind"], "sessions": sessions,
            "regions": summarize_regions(sessions), "scored_real_runs": sum(ENDPOINTS[k[0]][0] for k in cells),
            "null_score_verification": "recorded source scalar only; author settings do not save null predictions",
            "qualification": "software_component_only; no source-cohort authentication or paper improvement",
            "profile_adjudication": "unresolved; retain both source_figure_effect and paper_text_effect"}


def read_pinned(path, expected):
    raw = path.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected, "operator file SHA256 mismatch")
    return json.loads(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--roster", type=Path, required=True)
    parser.add_argument("--roster-sha256", required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--bundle-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(read_pinned(args.roster, args.roster_sha256), read_pinned(args.bundle, args.bundle_sha256))
    with args.output.open("x") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")


if __name__ == "__main__":
    main()
