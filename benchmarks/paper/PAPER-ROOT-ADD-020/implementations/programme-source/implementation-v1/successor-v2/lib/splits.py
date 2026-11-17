"""Exact outcome-independent global identity grouping. Supplied metadata only.

This module neither reads identity keys nor creates private aliases. Authentic
identity membership must already have independent source admission.
"""
from collections import Counter, defaultdict
from .strict import need, natural, text, exact_keys, encoded, schedule_hash, digest

DOMAIN = "PAPER-ROOT-ADD-020/full-design-v1"
ROW_KEYS = {"row_id", "group_id", "configuration", "source_set", "source_row",
            "stratum", "repeat_role"}


def validate_rows(rows, configurations=None):
    need(type(rows) is list and len(rows) > 0, "identity", "Nonempty complete row metadata required")
    seen = set()
    result = []
    by_case = defaultdict(list)
    same_source = {}
    for row in rows:
        exact_keys(row, ROW_KEYS, "identity row")
        for field in ("row_id", "group_id", "configuration"):
            text(row[field], field)
        need(row["row_id"] not in seen, "identity", "Duplicate row identifier")
        seen.add(row["row_id"])
        need(type(row["source_set"]) is int and row["source_set"] in (2, 3),
             "identity", "Original stimulus set required")
        natural(row["source_row"], "source row", zero=True)
        need(row["stratum"] in ("familiar", "unfamiliar"), "identity", "Original familiarity role required")
        need(row["repeat_role"] in ("standard", "low", "high"), "identity", "Original repeat role required")
        # Shared feature-file rows cannot be relabelled across animals or pools.
        source_key = (row["source_set"], row["source_row"])
        identity = (row["group_id"], row["stratum"], row["repeat_role"])
        need(source_key not in same_source or same_source[source_key] == identity,
             "identity", "Shared source row has inconsistent identity/role")
        same_source[source_key] = identity
        result.append(dict(row))
        by_case[row["configuration"]].append(row)
    if configurations is not None:
        case_map = {x["configuration"]: x for x in configurations}
        need(len(case_map) == 14 and set(by_case) == set(case_map),
             "coverage", "All fourteen original configurations required")
        for name, case in case_map.items():
            source_set = case["stimulus_set"]
            n = 1036 if source_set == 2 else 1080
            ordered = sorted(by_case[name], key=lambda x: x["source_row"])
            need(len(ordered) == n and [x["source_row"] for x in ordered] == list(range(n)),
                 "coverage", "Exact complete original face-row universe required")
            for row in ordered:
                i = row["source_row"]
                expected = (("unfamiliar", "standard") if i < 1000 else ("familiar", "standard")) if source_set == 2 else (
                    ("unfamiliar", "low") if i < 1008 else ("familiar", "high") if i < 1044 else ("unfamiliar", "high"))
                need(row["source_set"] == source_set and (row["stratum"], row["repeat_role"]) == expected,
                     "identity", "Original partition mismatch")
    return result


def _groups(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row["group_id"]].append(row)
    return groups


def _role_signature(group):
    return encoded([list(x) for x in sorted({(x["source_set"], x["stratum"], x["repeat_role"]) for x in group})])


def assign_folds(rows, folds, *, domain, outer=None):
    """Metadata-only helper; production caller supplies six outer/four inner."""
    rows = validate_rows(rows)
    natural(folds, "fold count")
    text(domain, "schedule domain")
    if outer is not None:
        natural(outer, "outer index", zero=True)
    buckets = defaultdict(list)
    for identity, group in _groups(rows).items():
        buckets[_role_signature(group)].append(identity)
    assignment = {}
    for signature, identities in sorted(buckets.items()):
        signature_text = signature.decode("utf-8")
        prefix = [domain] + ([] if outer is None else [str(outer)])
        offset = int.from_bytes(schedule_hash(*prefix, signature_text), "big") % folds
        order = sorted(identities, key=lambda g: (schedule_hash(*prefix, g), g.encode("utf-8")))
        for rank, identity in enumerate(order):
            assignment[identity] = (rank + offset) % folds
    need(set(assignment.values()) == set(range(folds)), "support", "Every declared fold requires identity support")
    return assignment


def make_outer_assignment(rows):
    return assign_folds(rows, 6, domain=DOMAIN + "/outer")


def fold_view(rows, outer_assignment, fold, regime):
    rows = validate_rows(rows)
    natural(fold, "outer index", zero=True)
    need(fold < 6 and regime in ("calibrated_held_face", "unfamiliar_to_familiar_transfer"),
         "schema", "Exact regime and six-fold index required")
    groups = set(_groups(rows))
    need(type(outer_assignment) is dict and set(outer_assignment) == groups,
         "identity", "Complete group assignment required")
    need(all(type(x) is int and 0 <= x < 6 for x in outer_assignment.values()),
         "identity", "Exact outer fold integers required")
    queries = [r for r in rows if outer_assignment[r["group_id"]] == fold]
    training = [r for r in rows if outer_assignment[r["group_id"]] != fold and
                (regime == "calibrated_held_face" or r["stratum"] == "unfamiliar")]
    need(training and queries, "support", "Complete nonempty fit and query views required")
    need(not ({x["group_id"] for x in queries} & {x["group_id"] for x in training}),
         "leakage", "A query identity entered training")
    inner = assign_folds(training, 4, domain=DOMAIN + "/inner", outer=fold)
    case_names = {r["configuration"] for r in rows}
    for case in case_names:
        tr = [r for r in training if r["configuration"] == case]
        qu = [r for r in queries if r["configuration"] == case]
        need(tr and qu, "support", "Every original configuration requires train/query support")
        need({r["stratum"] for r in qu} == {"familiar", "unfamiliar"},
             "support", "Both query familiarity strata required in every fold")
        expected = {"unfamiliar"} if regime == "unfamiliar_to_familiar_transfer" else {"familiar", "unfamiliar"}
        for k in range(4):
            for side in (True, False):
                subset = [r for r in tr if (inner[r["group_id"]] == k) is side]
                need({r["stratum"] for r in subset} == expected, "support",
                     "Every inner train/validation side requires complete regime strata")
    return {"fold": fold, "regime": regime, "training": training, "queries": queries,
            "inner_folds": inner, "assignment_digest": digest(outer_assignment)}


def training_permutation(training_rows, fold, regime, repetition):
    """Return row->source-row correspondence; never inspect a response value."""
    rows = validate_rows(training_rows)
    natural(fold, "outer index", zero=True)
    natural(repetition, "null repetition", zero=True)
    need(fold < 6 and repetition < 20, "schema", "Frozen full null schedule required")
    need(regime in ("calibrated_held_face", "unfamiliar_to_familiar_transfer"), "schema", "Exact regime required")
    groups = _groups(rows)
    buckets = defaultdict(list)
    for identity, group in groups.items():
        occurrences = Counter((r["configuration"], r["source_set"], r["stratum"], r["repeat_role"]) for r in group)
        signature = encoded([[list(k), v] for k, v in sorted(occurrences.items())])
        buckets[signature].append(identity)
    mapping = {}
    for signature, identities in sorted(buckets.items()):
        need(len(identities) >= 2, "support", "Full compatible permutation support unavailable")
        original = sorted(identities, key=lambda g: g.encode("utf-8"))
        shuffled = sorted(identities, key=lambda g: (schedule_hash(DOMAIN + "/null", str(fold), regime,
                                                                  str(repetition), g), g.encode("utf-8")))
        def position(row):
            return (row["configuration"], row["source_set"], row["stratum"], row["repeat_role"], row["source_row"])
        for before, after in zip(original, shuffled):
            left, right = sorted(groups[before], key=position), sorted(groups[after], key=position)
            need(len(left) == len(right), "support", "Permutation multiplicity mismatch")
            for x, y in zip(left, right):
                need(position(x)[:-1] == position(y)[:-1], "support", "Permutation role mismatch")
                mapping[x["row_id"]] = y["row_id"]
    need(set(mapping) == {r["row_id"] for r in rows} and len(set(mapping.values())) == len(rows),
         "coverage", "Permutation must cover all training rows bijectively")
    return mapping
