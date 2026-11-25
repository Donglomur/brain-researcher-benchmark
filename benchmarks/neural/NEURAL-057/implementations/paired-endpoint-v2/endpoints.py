"""Retain defined extended-real paired endpoints from a complete N057 report.

Operator-only postprocessing: no predictions, labels, fitting, phase execution,
or qualification authority. The registered campaign's protected barrier remains
the only producer of the source report. All comparisons keep all ten people.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

PEOPLE = tuple(f"sub-{i:02d}" for i in range(1, 11))
MODES = ("F", "I")
PANELS = ("IMAGE", "PRE", "BASE", "LATE")
UNIT = "nats_per_category"
REPEAT_UNIT = "one 80-repeat mean per original query image"
EXPECTED = {(p, m, x) for p in PEOPLE for m in MODES for x in PANELS}
CELL_FIELDS = {"cell", "loss", "concept_loss", "scored_concepts", "query_rows",
               "unsupported_query_ids", "categories", "unit", "repeat_unit"}


class EndpointError(ValueError):
    """The recorded cells cannot support this exact registered endpoint."""


def require(condition, message):
    if not condition:
        raise EndpointError(message)


def tag(value):
    if math.isinf(value):
        return {"status": "positive_infinity" if value > 0 else "negative_infinity",
                "value": None}
    require(math.isfinite(value), "undefined values need an explicit reason")
    return {"status": "finite", "value": value}


def undefined(reason):
    return {"status": "undefined", "value": None, "reason": reason}


def native_value(value):
    require(type(value) is dict and set(value) == {"status", "value"},
            "closed native loss tag")
    if value["status"] == "positive_infinity":
        require(value["value"] is None, "infinite loss has no numeric surrogate")
        return math.inf
    require(value["status"] == "finite" and type(value["value"]) in (int, float)
            and math.isfinite(value["value"])
            and 0 <= value["value"] <= -math.log(math.ulp(0.0)) + 1e-10,
            "native Bernoulli loss is finite nonnegative or positive infinity")
    return value["value"]


def mean_loss(values):
    require(bool(values), "nonempty complete endpoint support")
    if any(math.isinf(x) for x in values):
        return math.inf
    # Admitted Bernoulli losses are bounded by -log(minimum positive
    # binary64), with at most200 concepts or10 people. Their sum is finite.
    # Sum before division so representable subnormal means are not erased.
    return math.fsum(values) / len(values)


def difference(left, right):
    if math.isinf(left) and math.isinf(right):
        return undefined("positive_infinity_minus_positive_infinity")
    return tag(left - right)


def collection(rows):
    require(type(rows) is list and len(rows) == 80, "all 80 original cells per owner")
    out = {}
    support = None
    unsupported = {}
    for row in rows:
        require(type(row) is dict and set(row) == CELL_FIELDS, "closed native score cell")
        cell = row["cell"]
        require(type(cell) is dict and set(cell) == {"person", "mode", "panel"},
                "closed person/mode/panel identity")
        require(all(type(cell[k]) is str for k in cell), "string cell coordinates")
        key = (cell["person"], cell["mode"], cell["panel"])
        require(key in EXPECTED and key not in out, "unique original cell identity")
        require(type(row["query_rows"]) is int and row["query_rows"] == 200
                and type(row["categories"]) is int and row["categories"] == 53
                and row["unit"] == UNIT and row["repeat_unit"] == REPEAT_UNIT,
                "original query/category denominators and released units")
        concepts = row["concept_loss"]
        require(type(concepts) is dict and concepts
                and all(type(c) is str and c for c in concepts), "supported concept contributions")
        require(type(row["scored_concepts"]) is int
                and row["scored_concepts"] == len(concepts), "exact supported concept denominator")
        omitted = row["unsupported_query_ids"]
        require(type(omitted) is list and all(type(q) is str and q for q in omitted)
                and len(set(omitted)) == len(omitted), "explicit unique unsupported query IDs")
        require(len(concepts) + len(omitted) == 200,
                "one test image per concept; unsupported rows are never dropped silently")
        if support is None:
            support = set(concepts)
        require(set(concepts) == support, "same fixed supported concepts across all people and panels")
        person = key[0]
        if person not in unsupported:
            unsupported[person] = omitted
        require(omitted == unsupported[person], "same person-specific unsupported rows across panels/modes")
        values = {c: native_value(v) for c, v in concepts.items()}
        loss = native_value(row["loss"])
        calculated = mean_loss(list(values.values()))
        require((math.isinf(calculated) and math.isinf(loss)) or
                (math.isfinite(calculated) and math.isfinite(loss)
                 and math.isclose(loss, calculated, rel_tol=1e-12, abs_tol=1e-14)),
                "native loss agrees with equal-concept contributions")
        out[key] = {"loss": loss, "concepts": values, "unsupported": omitted}
    require(set(out) == EXPECTED, "complete exact mode/panel/person collection")
    return out


def contrast(index_left, index_right, mode, left_panel, right_panel):
    left = [index_left[p, mode, left_panel] for p in PEOPLE]
    right = [index_right[p, mode, right_panel] for p in PEOPLE]
    for a, b in zip(left, right):
        require(set(a["concepts"]) == set(b["concepts"])
                and a["unsupported"] == b["unsupported"], "matched independent reference support")
    concepts = sorted(left[0]["concepts"])
    persons = {p: difference(a["loss"], b["loss"])
               for p, a, b in zip(PEOPLE, left, right)}
    per_concept_person = {
        c: {p: difference(a["concepts"][c], b["concepts"][c])
            for p, a, b in zip(PEOPLE, left, right)} for c in concepts}
    concept_means = {
        c: difference(mean_loss([a["concepts"][c] for a in left]),
                      mean_loss([b["concepts"][c] for b in right])) for c in concepts}
    left_mean = mean_loss([a["loss"] for a in left])
    right_mean = mean_loss([b["loss"] for b in right])
    gain = difference(left_mean, right_mean)
    uncertainty = {"status": "unavailable", "reason": "nonfinite_or_undefined_paired_loss",
                   "person_sem_ddof1": None, "person_t9_descriptive_interval": None,
                   "concept_sem_ddof1": None}
    if all(x["status"] == "finite" for x in persons.values()):
        values = [persons[p]["value"] for p in PEOPLE]
        mean = math.fsum(values) / 10
        # The inputs originate as bounded finite Bernoulli losses. No subset
        # estimate is substituted if an actual endpoint is infinite/undefined.
        sem = math.sqrt(math.fsum((v - mean) ** 2 for v in values) / 90)
        cv = [concept_means[c]["value"] for c in concepts]
        n = len(cv)
        csem = None if n < 2 else math.sqrt(math.fsum((v - mean) ** 2 for v in cv) / (n * (n - 1)))
        uncertainty = {"status": "finite_descriptive", "reason": None,
                       "person_sem_ddof1": sem,
                       "person_t9_descriptive_interval": [mean - 2.2621571627409915 * sem,
                                                           mean + 2.2621571627409915 * sem],
                       "concept_sem_ddof1": csem}
    return {"mode": mode, "left_panel": left_panel, "right_panel": right_panel,
            "left_mean_loss": tag(left_mean), "right_mean_loss": tag(right_mean),
            "left_minus_right": gain, "person_contributions": persons,
            "concept_contributions": concept_means,
            "concept_person_contributions": per_concept_person,
            "uncertainty": uncertainty, "person_denominator": 10,
            "concept_denominator": len(concepts), "category_denominator": 53,
            "unit": UNIT, "unsupported_query_ids_by_person": {
                p: a["unsupported"] for p, a in zip(PEOPLE, left)},
            "interpretation": "descriptive paired loss; shared concepts and overlapping training folds; not a crossed-population interval"}


def build_endpoints(report):
    require(type(report) is dict and report.get("schema") == "neural057-complete-report-v1"
            and report.get("status") == "numerical_complete_pending_independent_semantic_qualification",
            "complete registered report producer format; not an execution credential")
    results = report.get("results")
    require(type(results) is dict and set(results) == {"reference", "participant"},
            "independent reference and participant collections")
    indexes = {}
    for owner in ("reference", "participant"):
        require(type(results[owner]) is dict and "cells" in results[owner], "native cells present")
        indexes[owner] = collection(results[owner]["cells"])
    comparisons = []
    for mode in MODES:
        for panel in ("BASE", "LATE"):
            item = contrast(indexes["reference"], indexes["participant"], mode, panel, "LATE")
            item.update(left_owner="reference", right_owner="participant",
                        participant_BASE_used_as_reward=False)
            comparisons.append(item)
    within = {}
    primary = {}
    for owner, index in indexes.items():
        within[owner] = [contrast(index, index, mode, "BASE", "LATE") for mode in MODES]
        primary[owner] = [{"mode": m, "primary_loss": tag(mean_loss([
            index[p, m, "LATE"]["loss"] for p in PEOPLE])), "unit": UNIT,
            "direction": "lower", "person_denominator": 10, "category_denominator": 53,
            "participant_BASE_not_a_reward_term": True} for m in MODES]
    return {"schema": "neural057-paired-endpoints-v2", "primary_native_loss": primary,
            "within_owner_descriptive_comparisons": within,
            "independent_comparisons": comparisons,
            "qualification": "postprocessing_only_no_execution_or_scientific_admission",
            "limitations": ["public corpus and taxonomy", "released all-session MVNN",
                            "200ms stimulus overlap", "no direct/viewer/per-query tool interpretation result",
                            "no finite-subset replacement for nonfinite complete endpoints"]}


def parse(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(_):
        raise EndpointError("nonfinite JSON token")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    raw = args.report.read_bytes()
    result = build_endpoints(parse(raw))
    result["source_report_sha256"] = hashlib.sha256(raw).hexdigest()
    body = (json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    # Never replace an original report or an existing endpoint receipt.
    with args.output.open("xb") as handle:
        handle.write(body)


if __name__ == "__main__":
    main()
