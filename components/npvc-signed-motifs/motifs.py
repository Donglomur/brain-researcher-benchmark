"""NPvC signed-network endpoint; method-derived, no author code or native fits.

Labels are externally established IE(+1), IL(-1), or independent(0).
The module does not decide pair significance or recover historical bootstraps.
"""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path

TASK = "PAPER-CANDIDATE-20261114-NPVC"
SIGNS = (-1, 0, 1)
TYPES = tuple(itertools.combinations_with_replacement(SIGNS, 3))
MAX_NODES = 512
MAX_RECORD_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_CASES = 1024
MAX_SHUFFLES = 10000
MAX_PAIR_VISITS = 100_000_000
MAX_RESULT_BYTES = 8 * 1024 * 1024


class Invalid(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise Invalid(message)


def keys(obj, expected, where):
    require(type(obj) is dict and set(obj) == set(expected), where + ": exact keys required")


def identifier(x):
    require(type(x) is str and 0 < len(x) <= 200 and all(32 < ord(c) < 127 for c in x), "invalid identifier")
    return x


def integer(x, lo, hi):
    require(type(x) is int and lo <= x <= hi, "integer outside admitted bounds")
    return x


def real(x):
    require(type(x) in (int, float), "finite real required")
    try:
        finite = math.isfinite(x)
    except OverflowError:
        finite = False
    require(finite, "finite real required")
    return x


def key(t):
    return ",".join({-1: "-", 0: "0", 1: "+"}[v] for v in t)


def choose(n, k):
    return math.comb(n, k) if 0 <= k <= n else 0


def summarize(counts):
    total = sum(counts.values())
    require(total > 0, "at least three nodes required")
    cc = {}
    for sign, name in ((-1, "IL"), (1, "IE")):
        closed = counts[(sign, sign, sign)]
        opened = sum(v for t, v in counts.items() if t.count(sign) == 2)
        denominator = closed + opened
        cc[name] = {"closed": closed, "open": opened,
                    "coefficient": closed / denominator if denominator else None,
                    "undefined_reason": None if denominator else "no_open_or_closed_triplets"}
    return {"triplets": total,
            "counts": {key(t): counts[t] for t in TYPES},
            "probabilities": {key(t): counts[t] / total for t in TYPES},
            "independent_edge_triplets": sum(v for t, v in counts.items() if 0 in t),
            "clustering": cc}


def graph(n, labels):
    """Count each unordered three-node set once, retaining all ten sign types.

    Labels use lexicographic upper-triangle order (i,j), 0<=i<j<n.
    Bit intersections count k>j without enumerating or dropping triplets.
    """
    integer(n, 3, MAX_NODES)
    require(type(labels) is list and len(labels) == choose(n, 2), "incomplete upper triangle")
    adjacency = {s: [0] * n for s in SIGNS}
    frequencies = {s: 0 for s in SIGNS}
    for (i, j), s in zip(itertools.combinations(range(n), 2), labels):
        require(type(s) is int and s in SIGNS, "edge label must be -1, 0 or +1; bool refused")
        adjacency[s][i] |= 1 << j
        adjacency[s][j] |= 1 << i
        frequencies[s] += 1
    counts = {t: 0 for t in TYPES}
    all_bits = (1 << n) - 1
    for (i, j), edge in zip(itertools.combinations(range(n), 2), labels):
        later = all_bits ^ ((1 << (j + 1)) - 1)
        for a in SIGNS:
            ai = adjacency[a][i] & later
            for b in SIGNS:
                count = (ai & adjacency[b][j]).bit_count()
                counts[tuple(sorted((edge, a, b)))] += count
    require(sum(counts.values()) == choose(n, 3), "internal whole-triplet coverage failure")
    result = summarize(counts)
    m = len(labels)
    denominator = choose(m, 3)
    # Marginal expectation under uniform permutation of the COMPLETE fixed edge
    # label multiset. This is not a bootstrap interval or E[CC] approximation.
    expected = {}
    for t in TYPES:
        ways = math.prod(choose(frequencies[s], t.count(s)) for s in SIGNS)
        expected[key(t)] = ways / denominator
    result.update({"nodes": n, "pairs": m,
                   "edge_counts": {str(s): frequencies[s] for s in SIGNS},
                   "uniform_fixed_count_shuffle_expected_probabilities": expected,
                   "relative_to_exact_shuffle_expectation": {
                       k: result["probabilities"][k] - expected[k] for k in expected},
                   "exact_shuffle_expected_clustering": None})
    return result


def shuffled_labels(labels, permutation):
    m = len(labels)
    require(type(permutation) is list and len(permutation) == m, "shuffle must cover every pair slot")
    require(all(type(v) is int and 0 <= v < m for v in permutation), "invalid permutation index")
    require(len(set(permutation)) == m, "shuffle is not a bijection")
    return [labels[v] for v in permutation]


def relative(observed, shuffled):
    out = {"probabilities": {k: observed["probabilities"][k] - shuffled["probabilities"][k]
                              for k in observed["probabilities"]}, "clustering": {}}
    for name in ("IL", "IE"):
        a = observed["clustering"][name]["coefficient"]
        b = shuffled["clustering"][name]["coefficient"]
        out["clustering"][name] = {"difference": None if a is None or b is None else a - b,
                                    "undefined_reason": "observed_or_shuffle_has_no_triplets" if a is None or b is None else None}
    return out


def two_pool(n, p, delta1, delta2):
    """Finite-N Eq17 forward model; Bernoulli edges, NOT fixed-count shuffle.

    Pools have equal size; no inverse fit, chosen grid, confidence interval,
    information-per-motif weights or Figure6 information calculation is implied.
    """
    integer(n, 4, MAX_NODES)
    require(n % 2 == 0, "equal integer pools require even n")
    p, delta1, delta2 = real(p), real(delta1), real(delta2)
    q = n // 2
    p1, p2 = p + delta1, p + delta2
    pb = (p * choose(n, 2) - (p1 + p2) * choose(q, 2)) / (q * q)
    require(all(0 <= v <= 1 for v in (p, p1, p2, pb)), "inadmissible two-pool probabilities")
    probabilities = [0.0] * 4
    for weight, probs in ((choose(q, 3), (p1, p1, p1)),
                          (choose(q, 3), (p2, p2, p2)),
                          (choose(q, 2) * q, (p1, pb, pb)),
                          (choose(q, 2) * q, (p2, pb, pb))):
        for bits in itertools.product((0, 1), repeat=3):
            mass = math.prod(v if bit else 1 - v for v, bit in zip(probs, bits))
            probabilities[sum(bits)] += weight * mass / choose(n, 3)
    baseline = [choose(3, k) * p**k * (1 - p)**(3-k) for k in range(4)]
    return {"n": n, "pool_size": q, "p": p, "delta1": delta1, "delta2": delta2,
            "p1": p1, "p2": p2, "between_pool_p": pb,
            "order": ["-,-,-", "-,-,+", "-,+,+", "+,+,+"],
            "probabilities": probabilities, "homogeneous_Bernoulli_probabilities": baseline,
            "relative_to_homogeneous_Bernoulli": [a-b for a,b in zip(probabilities, baseline)]}


def validate_manifest(manifest):
    keys(manifest, ("schema", "task_id", "cases", "shuffle_ids", "two_pool_models"), "manifest")
    require(manifest["schema"] == "npvc-motif-input-v1" and manifest["task_id"] == TASK, "wrong task/schema")
    cases = manifest["cases"]
    require(type(cases) is list and 0 < len(cases) <= MAX_CASES, "case count outside limits")
    seen = set()
    for c in cases:
        keys(c, ("case_id", "animal_id", "session_id", "projection", "outcome", "task_variable", "neuron_ids", "classification_provenance"), "case")
        for field in ("case_id", "animal_id", "session_id", "classification_provenance"):
            identifier(c[field])
        require(c["case_id"] not in seen, "duplicate case")
        seen.add(c["case_id"])
        require(c["projection"] in ("ACC", "RSC", "contralateral_PPC", "unlabeled"), "unknown projection")
        require(c["outcome"] in ("correct", "incorrect"), "unknown outcome")
        require(c["task_variable"] in ("choice", "sample_cue", "test_cue"), "unknown task variable")
        ids = c["neuron_ids"]
        require(type(ids) is list and 3 <= len(ids) <= MAX_NODES, "neuron count outside limits")
        require(len(set(identifier(v) for v in ids)) == len(ids), "duplicate neuron")
    shuffles = manifest["shuffle_ids"]
    require(type(shuffles) is list and 0 < len(shuffles) <= MAX_SHUFFLES, "explicit nonempty shuffle roster required")
    require(len(set(identifier(x) for x in shuffles)) == len(shuffles), "duplicate shuffle")
    visits = sum(choose(len(c["neuron_ids"]), 2) for c in cases) * (1 + len(shuffles))
    require(visits <= MAX_PAIR_VISITS, "whole operation too large; refuse without truncation")
    models = manifest["two_pool_models"]
    require(type(models) is list and len(models) <= 10000, "model grid outside limits")
    mids = set()
    for x in models:
        keys(x, ("model_id", "n", "p", "delta1", "delta2"), "two-pool point")
        identifier(x["model_id"])
        require(x["model_id"] not in mids, "duplicate model point")
        mids.add(x["model_id"])
        two_pool(x["n"], x["p"], x["delta1"], x["delta2"])
    return visits


def evaluate(manifest, records):
    visits = validate_manifest(manifest)
    records = iter(records)
    results = []
    result_bytes = 0
    for case in manifest["cases"]:
        try:
            row = next(records)
        except StopIteration:
            raise Invalid("missing observed graph") from None
        keys(row, ("case_id", "kind", "labels"), "observed")
        require(row["case_id"] == case["case_id"] and row["kind"] == "observed", "observed case/order mismatch")
        labels = row["labels"]
        observed = graph(len(case["neuron_ids"]), labels)
        shuffled = []
        for sid in manifest["shuffle_ids"]:
            try:
                row = next(records)
            except StopIteration:
                raise Invalid("missing prescribed shuffle") from None
            keys(row, ("case_id", "kind", "shuffle_id", "permutation"), "shuffle")
            require(row["case_id"] == case["case_id"] and row["kind"] == "shuffle" and row["shuffle_id"] == sid, "shuffle case/order mismatch")
            counts = graph(len(case["neuron_ids"]), shuffled_labels(labels, row["permutation"]))
            item = {"shuffle_id": sid, "graph": counts, "relative": relative(observed, counts)}
            result_bytes += len(json.dumps(item, allow_nan=False).encode())
            require(result_bytes <= MAX_RESULT_BYTES, "complete results exceed memory envelope; refuse without omissions")
            shuffled.append(item)
        means = {"probabilities": {k: math.fsum(s["relative"]["probabilities"][k] for s in shuffled) / len(shuffled)
                                   for k in observed["probabilities"]}, "clustering": {}}
        for name in ("IL", "IE"):
            values = [s["relative"]["clustering"][name]["difference"] for s in shuffled]
            missing = sum(v is None for v in values)
            means["clustering"][name] = {"difference": None if missing else math.fsum(values) / len(values),
                                          "undefined_shuffles": missing,
                                          "policy": "no undefined shuffle is silently omitted"}
        item = {"case": case, "observed": observed, "shuffles": shuffled, "mean_relative": means}
        result_bytes += len(json.dumps({k: v for k, v in item.items() if k != "shuffles"}, allow_nan=False).encode())
        require(result_bytes <= MAX_RESULT_BYTES, "complete results exceed memory envelope; refuse without omissions")
        results.append(item)
    sentinel = object()
    require(next(records, sentinel) is sentinel, "extra graph records")
    return {"schema": "npvc-motif-output-v1", "task_id": TASK,
            "complete_relative_to_supplied_manifest": True,
            "authentic_population_verified": False, "historical_reproduction_established": False,
            "pair_classification_validated": False, "bootstrap_confidence_intervals": None,
            "numerical_pass": None, "whole_pair_visits": visits, "cases": results,
            "two_pool_models": [{"model_id": x["model_id"], **two_pool(x["n"], x["p"], x["delta1"], x["delta2"])} for x in manifest["two_pool_models"]]}


def unique_object(pairs):
    result = {}
    for k, v in pairs:
        require(k not in result, "duplicate JSON key")
        result[k] = v
    return result


def decode(data):
    return json.loads(data, object_pairs_hook=unique_object,
                      parse_constant=lambda value: (_ for _ in ()).throw(Invalid("nonfinite JSON constant")))


def run(manifest_path, records_path, output_path):
    require(not output_path.exists(), "fresh output destination required")
    total = 0
    digest = hashlib.sha256()
    with manifest_path.open("rb") as f:
        mb = f.read(MAX_RECORD_BYTES + 1)
    require(len(mb) <= MAX_RECORD_BYTES, "manifest exceeds byte limit")
    def records():
        nonlocal total
        with records_path.open("rb") as f:
            while True:
                line = f.readline(MAX_RECORD_BYTES + 1)
                if not line:
                    return
                total += len(line)
                require(len(line) <= MAX_RECORD_BYTES and total <= MAX_TOTAL_BYTES, "complete input exceeds byte limits")
                digest.update(line)
                yield decode(line)
    output = evaluate(decode(mb), records())
    output["input_custody"] = {"manifest_sha256": hashlib.sha256(mb).hexdigest(),
                                "records_sha256": digest.hexdigest(), "records_bytes": total}
    encoded = (json.dumps(output, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    require(len(encoded) <= MAX_TOTAL_BYTES, "complete output exceeds byte limit")
    with output_path.open("xb") as f:
        f.write(encoded)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        run(args.manifest, args.records, args.output)
    except (Invalid, OSError, ValueError) as exc:
        parser.exit(2, str(exc) + "\n")
