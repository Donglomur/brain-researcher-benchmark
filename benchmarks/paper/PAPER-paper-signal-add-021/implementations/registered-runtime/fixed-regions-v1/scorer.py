"""Trusted fixed-region artifact scorer. Never mount this or answers in actors.

The delivery owner must freeze both closed submissions before loading reference
bytes. This module neither opens paths nor executes a participant program.
"""
from __future__ import annotations

import hashlib
import json
import math

MAX_BYTES = 2 * 1024 * 1024
SCHEMA = "tms_fixed_regions_submission_v1"
REGIONS = tuple(f"{r}/{b}/{w}" for r in ("primary6", "sensitivity7")
                for b in ("alpha", "beta") for w in ("early", "late", "extended_late"))
EFFECTS = ("pin_T_minus_NT", "pout_T_minus_NT", "location_interaction")
PAIRED = ("mean", "sample_sd", "standard_error", "t", "cohens_dz", "degenerate")
COMPONENTS = ("condition_means", "differences", "paired", "sign_flip", "bootstrap", "holm", "leave_one_out")
SCALES = {"dB": 1.0, "dimensionless_statistic": 1.0, "probability": 1.0, "assignment_count": 32768.0}


class InvalidSubmission(ValueError):
    """Malformed participant artifact; distinct from a finite wrong answer."""


class InvalidReference(ValueError):
    """Trusted-state failure: never convert this into a candidate score."""


def decode(body, error=InvalidSubmission):
    if type(body) is not bytes or not 0 < len(body) <= MAX_BYTES:
        raise error("artifact byte extent")
    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise error("duplicate JSON key")
            out[k] = v
        return out
    def integer(s):
        if len(s.lstrip("-")) > 310:
            raise error("integer extent")
        return int(s)
    def constant(_):
        raise error("nonfinite JSON constant")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                           parse_int=integer, parse_constant=constant)
        pending = [(value, 0)]; nodes = 0
        while pending:
            x, depth = pending.pop(); nodes += 1
            if depth > 24 or nodes > 100000:
                raise error("JSON depth/node extent")
            if type(x) is dict:
                if any(type(k) is not str or len(k) > 128 for k in x):
                    raise error("JSON key extent")
                pending.extend((v, depth + 1) for v in x.values())
            elif type(x) is list:
                pending.extend((v, depth + 1) for v in x)
            elif type(x) is str and len(x) > 1024:
                raise error("JSON string extent")
            elif type(x) is float and not math.isfinite(x):
                raise error("nonfinite JSON number")
        return value
    except (UnicodeError, json.JSONDecodeError, RecursionError, OverflowError) as exc:
        raise error("invalid bounded UTF8 JSON") from exc


def _keys(x, expected):
    if type(x) is not dict or set(x) != set(expected):
        raise InvalidSubmission("exact public field set required")


def _number(x, nullable=False):
    if nullable and x is None:
        return
    if type(x) not in (int, float):
        raise InvalidSubmission("finite numeric field; bool is not numeric")
    try:
        finite = math.isfinite(x)
    except OverflowError:
        finite = False
    if not finite:
        raise InvalidSubmission("finite binary64-representable numeric field")


def _vector(x, n):
    if type(x) is not list or len(x) != n:
        raise InvalidSubmission("complete fixed coordinate extent required")
    for v in x:
        _number(v)


def _paired(x):
    _keys(x, PAIRED)
    for k in PAIRED[:-1]:
        _number(x[k], k in ("t", "cohens_dz"))
    if x["degenerate"] is not None and (type(x["degenerate"]) is not str or x["degenerate"] not in ("all_zero", "constant_nonzero")):
        raise InvalidSubmission("declared degenerate category required")


def validate(x):
    _keys(x, ("schema", "regions"))
    if x["schema"] != SCHEMA or type(x["regions"]) is not list or len(x["regions"]) != 12:
        raise InvalidSubmission("complete twelve-region submission required")
    for region, rid in zip(x["regions"], REGIONS):
        _keys(region, ("id", "condition_means", "effects"))
        if region["id"] != rid or type(region["condition_means"]) is not list or len(region["condition_means"]) != 4:
            raise InvalidSubmission("exact region order and four conditions required")
        for means in region["condition_means"]:
            _vector(means, 15)
        if type(region["effects"]) is not list or len(region["effects"]) != 3:
            raise InvalidSubmission("all three effects required")
        for effect, eid in zip(region["effects"], EFFECTS):
            _keys(effect, ("id", "differences", "paired", "sign_flip", "bootstrap", "holm_p", "leave_one_out"))
            if effect["id"] != eid:
                raise InvalidSubmission("exact effect coordinate order required")
            _vector(effect["differences"], 15); _paired(effect["paired"])
            _keys(effect["sign_flip"], ("extreme", "p_two_sided"))
            if type(effect["sign_flip"]["extreme"]) is not int or abs(effect["sign_flip"]["extreme"]) > 10**9:
                raise InvalidSubmission("bounded integer sign count required")
            _number(effect["sign_flip"]["p_two_sided"])
            _keys(effect["bootstrap"], ("lower", "upper"))
            _number(effect["bootstrap"]["lower"]); _number(effect["bootstrap"]["upper"]); _number(effect["holm_p"])
            if type(effect["leave_one_out"]) is not list or len(effect["leave_one_out"]) != 15:
                raise InvalidSubmission("all fifteen fixed omissions required")
            for i, row in enumerate(effect["leave_one_out"]):
                _keys(row, ("excluded_position", "paired"))
                if type(row["excluded_position"]) is not int or row["excluded_position"] != i:
                    raise InvalidSubmission("exact omitted-position order required")
                _paired(row["paired"])
    return x


def submission_from_reference(reference):
    """Owner-only structural projection; no scientific arithmetic or fixture export."""
    try:
        if (reference["schema"] != "tms-paired-eeg-region-reference-v1" or
            [reference[k] for k in ("region_definitions", "paired_effects", "leave_one_out_summaries")] != [12, 36, 540] or
            reference["source_positions"] != list(range(15))):
            raise InvalidReference("wrong complete reference profile")
        output = {"schema": SCHEMA, "regions": []}
        for region in reference["regions"]:
            out = {"id": region["id"], "condition_means": region["condition_means_by_source_position"], "effects": []}
            for eid in EFFECTS:
                e = region["effects"][eid]
                if type(e["paired"]["n"]) is not int or e["paired"]["n"] != 15 or e["paired"]["df"] != 14:
                    raise InvalidReference("reference full paired support")
                if e["sign_flip"]["enumerated"] != 32768 or e["bootstrap"]["draws"] != 2000 or e["bootstrap"]["seed"] != 20261114:
                    raise InvalidReference("reference frozen inference protocol")
                omissions = []
                for i, row in enumerate(e["leave_one_position_out"]):
                    if row["excluded_position"] != i or row["paired"]["n"] != 14 or row["paired"]["df"] != 13:
                        raise InvalidReference("reference complete leave-one-out support")
                    omissions.append({"excluded_position": i, "paired": {k: row["paired"][k] for k in PAIRED}})
                out["effects"].append({"id": eid, "differences": e["differences_by_source_position"],
                    "paired": {k: e["paired"][k] for k in PAIRED},
                    "sign_flip": {k: e["sign_flip"][k] for k in ("extreme", "p_two_sided")},
                    "bootstrap": {k: e["bootstrap"][k] for k in ("lower", "upper")},
                    "holm_p": e["holm_all36_region_sensitivity_p"], "leave_one_out": omissions})
            output["regions"].append(out)
        # Copy ensures a returned owner fixture cannot mutate the trusted source.
        return validate(json.loads(json.dumps(output, allow_nan=False)))
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, InvalidReference):
            raise
        raise InvalidReference("invalid complete trusted reference") from exc


def score_submission(candidate_bytes, reference_bytes, reference_sha256):
    """Both arguments are frozen owner-held bytes; callers enforce the pair barrier."""
    if (type(reference_bytes) is not bytes or type(reference_sha256) is not str or
        hashlib.sha256(reference_bytes).hexdigest() != reference_sha256):
        raise InvalidReference("trusted reference identity mismatch")
    expected = submission_from_reference(decode(reference_bytes, InvalidReference))
    got = validate(decode(candidate_bytes))
    groups = {k: [] for k in COMPONENTS}
    unit_errors = {k: [] for k in SCALES}
    undefined_mismatches = 0; category_mismatches = 0

    def loss(a, b, unit):
        nonlocal undefined_mismatches
        if a is None or b is None:
            if a is b:
                return 0.0
            undefined_mismatches += 1
            return 1.0
        d = abs(float(a) - float(b))
        unit_errors[unit].append(d)
        if not math.isfinite(d):
            return 1.0
        tolerance = 0.0 if unit in ("probability", "assignment_count") else max(1e-12, 1e-12 * abs(float(b)))
        if d <= tolerance:
            return 0.0
        ratio = d / SCALES[unit]
        return 1.0 if not math.isfinite(ratio) else 1.0 - 1.0 / (1.0 + ratio)

    def avg(xs):
        return math.fsum(xs) / len(xs)

    def paired_loss(a, b):
        nonlocal category_mismatches
        numeric = avg([avg([loss(a[k], b[k], "dB") for k in PAIRED[:3]]),
                       avg([loss(a[k], b[k], "dimensionless_statistic") for k in PAIRED[3:5]])])
        if a["degenerate"] != b["degenerate"]:
            category_mismatches += 1
            return 1.0
        return numeric

    for a, b in zip(got["regions"], expected["regions"]):
        groups["condition_means"].append(avg([loss(x, y, "dB") for ar, br in zip(a["condition_means"], b["condition_means"]) for x, y in zip(ar, br)]))
        for ae, be in zip(a["effects"], b["effects"]):
            groups["differences"].append(avg([loss(x, y, "dB") for x, y in zip(ae["differences"], be["differences"])]))
            groups["paired"].append(paired_loss(ae["paired"], be["paired"]))
            groups["sign_flip"].append(avg([loss(ae["sign_flip"]["extreme"], be["sign_flip"]["extreme"], "assignment_count"), loss(ae["sign_flip"]["p_two_sided"], be["sign_flip"]["p_two_sided"], "probability")]))
            groups["bootstrap"].append(avg([loss(ae["bootstrap"][k], be["bootstrap"][k], "dB") for k in ("lower", "upper")]))
            groups["holm"].append(loss(ae["holm_p"], be["holm_p"], "probability"))
            groups["leave_one_out"].append(avg([paired_loss(x["paired"], y["paired"]) for x, y in zip(ae["leave_one_out"], be["leave_one_out"])]))
    component_losses = {k: avg(v) for k, v in groups.items()}
    diagnostics = {}
    for unit, errors in unit_errors.items():
        overflow = any(not math.isfinite(x) for x in errors)
        maximum = None if overflow or not errors else max(errors)
        # Dividing each near-maximum error by n can round the subsequent sum
        # above binary64's finite range. Normalize by the maximum first: the
        # normalized mean is in [0, 1], including its rounding guard.
        mean_error = None
        if maximum is not None:
            mean_error = (0.0 if maximum == 0.0 else maximum * min(
                1.0, math.fsum(x / maximum for x in errors) / len(errors)))
        diagnostics[unit] = {"numeric_fields": len(errors), "binary64_error_overflow": overflow,
            "MAE": mean_error, "Linf": maximum}
    return {"schema": "tms_fixed_regions_score_v1", "valid_submission": True,
            "score": 1.0 - avg(list(component_losses.values())), "component_loss": component_losses,
            "by_unit_diagnostics": diagnostics, "undefined_mismatches": undefined_mismatches,
            "degenerate_category_mismatches": category_mismatches,
            "all_regions": 12, "all_effects": 36, "all_leave_one_out": 540,
            "scientific_significance_or_historical_reproduction_pass": None,
            "reference_values_exposed": False}
