"""Independent arithmetic for MICrONS Figure 5 / Extended Data 14.

No loaders, GLMM fitting, cohort selection, significance tests, tolerance,
improvement criterion, or scientific qualification is supplied by this module.
The expected support belongs to the operator, not a submitted programme.
"""
from __future__ import annotations

from itertools import combinations
import math

WEIGHTS = (
    "n_synapses", "dend_len", "pred_n_synapses", "pred_dend_len",
    "pred_n_synapses|dend_len",
)
EFFECTS = (
    ("total", "n_synapses", "pred_n_synapses"),
    ("axonal", "dend_len", "pred_dend_len"),
    ("synaptic", "n_synapses", "pred_n_synapses|dend_len"),
)
EDGE_FIELDS = frozenset(("post_id", "population", *WEIGHTS))
GROUP_FIELDS = frozenset(("projection", "pre_id", "edges", "post_pairs", "pre_post"))


def _id(value, name):
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{name} must be a nonempty exact string identifier")
    return value


def _number(value, name, *, correlation=False):
    # This interface accepts JSON-like built-in scalars only. Broad Real
    # coercion can turn a negative Fraction into -0.0, or a nonintegral value
    # just above one into 1.0 before range/integrality checks.
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a built-in int or float, excluding bool")
    if correlation and not -1 <= value <= 1:
        raise ValueError(f"{name} must lie in [-1,1]; no implicit clipping")
    if not correlation and value < 0:
        raise ValueError(f"{name} must be nonnegative")
    original = value
    try:
        value = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be representable as a finite real number") from None
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if type(original) is int and value != original:
        raise ValueError(f"{name} loses integer information when converted to float")
    return value


def _weighted(values, log_weights):
    # Normalizing log weights avoids overflow of two large edge weights.
    # This is mathematically the source weighted mean, not a claim of bitwise
    # agreement with NumPy's author implementation.
    if not values:
        return None
    maximum = max(log_weights)
    scaled = [math.exp(weight - maximum) for weight in log_weights]
    denominator = math.fsum(scaled)
    return math.fsum(value * weight for value, weight in zip(values, scaled)) / denominator


def _group_key(value):
    if not isinstance(value, tuple) or len(value) != 2:
        raise ValueError("operator group keys must be (projection, pre_id) tuples")
    return (_id(value[0], "projection"), _id(value[1], "pre_id"))


def reduce_common_inputs(expected_support, group_records):
    """Reduce complete operator-selected groups, without authenticating them.

    expected_support maps (projection, pre_id) to a sequence of distinct post
    identifiers. group_records must cover exactly those groups. Each record
    has projection, pre_id, edges, post_pairs and pre_post. Edges contain
    post_id, population and all five WEIGHTS. post_pairs contains all unique
    unordered (post1, post2, correlation) triples; pre_post contains exact
    (post_id, correlation) pairs. No diagonal or self-edge is permitted.

    Each group's eligibility is the source's >=10 Connected rows, before
    weight-specific positive filtering. All groups, including ineligible ones,
    remain visible. A group with fewer than two positive weights has undefined
    post-to-post similarity for that weight; it is not silently omitted or
    filled. Every mean and observed-minus-expected difference remains separate
    by presynaptic neuron, projection and relation. No aggregate score exists.
    """
    if not isinstance(expected_support, dict) or not expected_support:
        raise ValueError("nonempty operator support is required")
    support = {}
    for key, posts in expected_support.items():
        key = _group_key(key)
        if not isinstance(posts, (list, tuple)) or not posts:
            raise ValueError("each operator group needs a nonempty post roster")
        ids = tuple(_id(post, "post_id") for post in posts)
        if len(set(ids)) != len(ids) or key[1] in ids:
            raise ValueError("duplicate posts or presynaptic self-edge in operator support")
        support[key] = ids
    received = {}
    for record in group_records:
        if not isinstance(record, dict) or set(record) != GROUP_FIELDS:
            raise ValueError("group fields must be exact")
        key = _group_key((record["projection"], record["pre_id"]))
        if key not in support or key in received:
            raise ValueError("extra or duplicate group")
        received[key] = record
    if set(received) != set(support):
        raise ValueError("missing operator group")

    output = []
    for key, posts in support.items():
        record = received[key]
        edges = {}
        for row in record["edges"]:
            if not isinstance(row, dict) or set(row) != EDGE_FIELDS:
                raise ValueError("edge fields must be exact")
            post = _id(row["post_id"], "post_id")
            if post not in posts or post in edges:
                raise ValueError("extra or duplicate post edge")
            population = _id(row["population"], "population")
            weights = {name: _number(row[name], name) for name in WEIGHTS}
            if not weights["n_synapses"].is_integer():
                raise ValueError("observed synapse counts must be integral")
            # Population assignment is an upstream source decision. Do not
            # infer/relabel it from a different anatomical opportunity rule.
            edges[post] = (population, weights)
        if set(edges) != set(posts):
            raise ValueError("missing operator post edge")

        expected_pairs = {frozenset(pair) for pair in combinations(posts, 2)}
        pairs = {}
        for row in record["post_pairs"]:
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise ValueError("post pair must be (left,right,correlation)")
            left, right = _id(row[0], "left"), _id(row[1], "right")
            pair = frozenset((left, right))
            if len(pair) != 2 or pair not in expected_pairs or pair in pairs:
                raise ValueError("diagonal, extra or duplicate unordered post pair")
            pairs[pair] = _number(row[2], "post correlation", correlation=True)
        if set(pairs) != expected_pairs:
            raise ValueError("missing operator post correlation pair")
        pre_post = {}
        for row in record["pre_post"]:
            if not isinstance(row, (tuple, list)) or len(row) != 2:
                raise ValueError("pre-post row must be (post_id,correlation)")
            post = _id(row[0], "post_id")
            if post not in posts or post in pre_post:
                raise ValueError("extra or duplicate pre-post correlation")
            pre_post[post] = _number(row[1], "pre-post correlation", correlation=True)
        if set(pre_post) != set(posts):
            raise ValueError("missing operator pre-post correlation")

        n_connected = sum(pop == "Connected" for pop, _ in edges.values())
        result = {"projection": key[0], "pre_id": key[1],
                  "n_input_posts": len(posts), "n_connected": n_connected,
                  "eligible": n_connected >= 10,
                  "weight_summaries": [], "paired_differences": [],
                  "scientific_qualification": "not_established"}
        if n_connected < 10:
            result["status"] = "ineligible_source_connected_count"
            output.append(result)
            continue
        summaries = {}
        for name in WEIGHTS:
            active = [post for post in posts if edges[post][1][name] > 0]
            log_weights = {post: math.log(edges[post][1][name]) for post in active}
            post_pair_ids = list(combinations(active, 2))
            post_mean = _weighted(
                [pairs[frozenset(pair)] for pair in post_pair_ids],
                [log_weights[a] + log_weights[b] for a, b in post_pair_ids],
            )
            pre_mean = _weighted([pre_post[p] for p in active],
                                 [log_weights[p] for p in active])
            summaries[name] = {"weight": name, "n_positive_posts": len(active),
                               "n_post_pairs": len(post_pair_ids),
                               "post": post_mean, "pre_post": pre_mean}
            result["weight_summaries"].append(summaries[name])
        undefined = any(s[relation] is None for s in summaries.values()
                        for relation in ("post", "pre_post"))
        result["status"] = "undefined_weight_support" if undefined else "arithmetic_complete"
        for effect, observed, expected in EFFECTS:
            for relation in ("post", "pre_post"):
                a, b = summaries[observed][relation], summaries[expected][relation]
                result["paired_differences"].append({
                    "effect": effect, "relation": relation,
                    "observed_weight": observed, "expected_weight": expected,
                    "observed_minus_expected": None if a is None or b is None else a - b,
                })
        output.append(result)
    return output
