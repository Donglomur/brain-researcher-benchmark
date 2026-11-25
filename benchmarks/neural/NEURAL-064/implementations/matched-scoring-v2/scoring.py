"""NEURAL-064 numerical consumer; no source admission or execution authority.

This independently written component consumes operator-owned response rows from
the preserved assembly schema. It neither reads NWB nor runs/fits a model.
"""
import math
from collections import Counter
from fractions import Fraction

POLICIES = ("prestate_history", "outcome_conditioned_sensitivity")
CELL_TYPES = ("Slc17a7-IRES2-Cre", "Sst-IRES-Cre", "Vip-IRES-Cre")
SUBSETS = ("new_image", "already_familiar_image_control", "unknown_first_image_status")
PHASES = ("FIRST", "REPEAT")
ROLES = {"fit": 55, "validation": 11, "query": 14}
FAMILIES = ("hierarchical_mean", "hist_gradient_boosting")
ARMS = ("JOINT", "NUISANCE")


class ScoringError(ValueError):
    """Malformed or inconsistent operands cannot produce a score."""


def finite(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def number(value):
    if not finite(value):
        raise ScoringError("finite numeric value required; booleans are not responses")
    return float(value)


def mean(values):
    values = [number(v) for v in values]
    if not values:
        raise ScoringError("nonempty mean required")
    # Sum exact binary64 values before division so signed cancellation cannot
    # erase a small representable mean or overflow an intermediate total.
    return number(float(sum((Fraction(v) for v in values), Fraction()) / len(values)))


def _token(value):
    if not isinstance(value, str) or not value:
        raise ScoringError("nonempty opaque identity required")
    return value


def hierarchy(rows):
    """Validate complete phase pairs and fixed biological parent identities."""
    if not rows:
        raise ScoringError("empty response panel")
    groups = {}
    ids, parents, pair_contexts, mouse_contexts = set(), {}, {}, {}
    for row in rows:
        ident, mouse, container, pair = (_token(row.get(k)) for k in ("id", "mouse", "container", "pair"))
        if ident in ids:
            raise ScoringError("duplicate case identity")
        ids.add(ident)
        phase, split = row.get("phase"), row.get("split")
        celltype, subset = row.get("cre_line"), row.get("subset")
        if phase not in PHASES or split not in ROLES or celltype not in CELL_TYPES or subset not in SUBSETS:
            raise ScoringError("unknown phase, role, cell type or subset")
        if parents.setdefault(container, mouse) != mouse:
            raise ScoringError("container changes mouse")
        if mouse_contexts.setdefault(mouse, (split, celltype)) != (split, celltype):
            raise ScoringError("mouse changes role or cell type")
        context = (mouse, container, split, celltype, subset, _token(row.get("image")))
        if pair_contexts.setdefault(pair, context) != context:
            raise ScoringError("pair changes parent, image or response subset")
        phases = groups.setdefault(mouse, {}).setdefault(container, {}).setdefault(pair, {})
        if phase in phases:
            raise ScoringError("duplicate phase within pair")
        phases[phase] = row
    for containers in groups.values():
        for pairs in containers.values():
            if any(set(phases) != set(PHASES) for phases in pairs.values()):
                raise ScoringError("complete FIRST and REPEAT pair required")
    return groups


def weights(rows):
    """Equal mouse/container/pair/phase mass, never equal imaging-plane mass."""
    groups = hierarchy(rows)
    result = {}
    for containers in groups.values():
        for pairs in containers.values():
            for phases in pairs.values():
                for row in phases.values():
                    result[row["id"]] = 1.0 / len(groups) / len(containers) / len(pairs) / 2
    return result


def training_scale(rows):
    """Weighted population SD of FIT new-image responses, without an epsilon."""
    mass = weights(rows)
    if any(r["split"] != "fit" or r["subset"] != "new_image" for r in rows):
        raise ScoringError("scale uses FIT new-image responses only")
    values = [number(r.get("target")) for r in rows]
    lo, hi = min(values), max(values)
    if lo == hi:
        return None
    anchor = lo / 2 + hi / 2
    centered = [v - anchor for v in values]
    radius = max(map(abs, centered))
    z = [v / radius for v in centered]
    mu = math.fsum(mass[r["id"]] * v for r, v in zip(rows, z))
    variance = math.fsum(mass[r["id"]] * (v - mu) ** 2 for r, v in zip(rows, z))
    sd = number(radius * math.sqrt(variance))
    return sd if sd > 0 else None


def _ratio_product(a, b, denominator):
    """Compute a*b/denominator without overflowing a representable result."""
    if not a or not b:
        return 0.0
    am, ae = math.frexp(a)
    bm, be = math.frexp(b)
    dm, de = math.frexp(denominator)
    try:
        return number(math.ldexp(am * bm / dm, ae + be - de))
    except OverflowError as error:
        raise ScoringError("normalized error is not representable") from error


def macro_error(predictions, rows, sd):
    """Mean of mouse RMSE/SD; each mouse gives equal mass to its containers.

    A superset prediction map is allowed here for selecting a named subset. The
    policy consumer separately enforces exact full-query prediction identities.
    """
    sd = number(sd)
    if sd <= 0:
        raise ScoringError("positive FIT response scale required")
    groups = hierarchy(rows)
    mass = weights(rows)
    errors = []
    for containers in groups.values():
        rr = [r for pairs in containers.values() for phases in pairs.values() for r in phases.values()]
        try:
            pp = [number(predictions[r["id"]]) for r in rr]
        except KeyError as error:
            raise ScoringError("missing required prediction") from error
        yy = [number(r.get("target")) for r in rr]
        delta = [p - y for p, y in zip(pp, yy)]
        if all(math.isfinite(v) for v in delta):
            radius = max(map(abs, delta))
            normalized = [v / radius for v in delta] if radius else delta
        else:
            radius = max(abs(v) for v in pp + yy)
            normalized = [p / radius - y / radius for p, y in zip(pp, yy)]
        mse = math.fsum(mass[r["id"]] * len(groups) * v * v for r, v in zip(rr, normalized))
        errors.append(_ratio_product(radius, math.sqrt(mse), sd))
    return mean(errors)


def contrasts(values, rows):
    """Signed FIRST-minus-REPEAT, equal pairs then equal containers per mouse."""
    result = {}
    for mouse, containers in hierarchy(rows).items():
        container_means = []
        for pairs in containers.values():
            differences = []
            for phases in pairs.values():
                try:
                    first, repeat = (number(values[phases[p]["id"]]) for p in PHASES)
                except KeyError as error:
                    raise ScoringError("missing contrast value") from error
                differences.append(number(first - repeat))
            container_means.append(mean(differences))
        result[mouse] = mean(container_means)
    return result


def _predictions(candidate, expected, query_binding):
    if candidate.get("query_binding") != query_binding:
        raise ScoringError("query binding disagreement")
    records = candidate.get("predictions")
    if not isinstance(records, list) or len(records) != len(expected):
        raise ScoringError("complete query prediction list required")
    result = {arm: {} for arm in ARMS}
    for record in records:
        if not isinstance(record, dict) or set(record) != {"id", *ARMS}:
            raise ScoringError("exact paired prediction schema required")
        ident = _token(record["id"])
        if ident not in expected or ident in result["JOINT"]:
            raise ScoringError("extra or duplicate prediction identity")
        for arm in ARMS:
            result[arm][ident] = number(record[arm])
    return result


def _roster(records):
    if not isinstance(records, list):
        raise ScoringError("original full mouse support roster required")
    result = {}
    for record in records:
        mouse = _token(record.get("mouse"))
        if mouse in result or record.get("split") not in ROLES or not isinstance(record.get("status"), str):
            raise ScoringError("duplicate mouse or malformed mouse support")
        result[mouse] = record
    if Counter(r["split"] for r in records) != Counter(ROLES):
        raise ScoringError("original 55 FIT/11 validation/14 query roster required")
    return result


def _reference(reference, expected, policy, sd):
    freeze = reference["frozen_selection"]
    if freeze.get("policy") != policy or number(freeze.get("training_target_sd")) != sd:
        raise ScoringError("reference policy or FIT scale disagreement")
    selection = freeze["selection"]
    for arm in ARMS:
        item = selection[arm]
        losses = item["hgb_grid_validation_losses"]
        if not isinstance(losses, list) or len(losses) != 4:
            raise ScoringError("four frozen validation grid losses required")
        losses = [number(v) for v in losses]
        hierarchy_loss = number(item["hierarchical_validation_loss"])
        index = min(range(4), key=lambda i: (losses[i], i))
        family = FAMILIES[0] if hierarchy_loss <= losses[index] else FAMILIES[1]
        if (min(losses + [hierarchy_loss]) < 0 or type(item["hgb_grid_index"]) is not int
                or item["hgb_grid_index"] != index or item["validation_only_selected"] != family
                or item["fit_refit_on_validation"] is not False):
            raise ScoringError("inconsistent frozen validation selection")
    if freeze["primary_nuisance"] != selection["NUISANCE"]["validation_only_selected"]:
        raise ScoringError("primary reference must be the frozen nuisance selection")
    predictions = reference["predictions"]
    if set(predictions) != set(FAMILIES):
        raise ScoringError("both evaluator reference families required")
    for family in FAMILIES:
        if set(predictions[family]) != set(ARMS):
            raise ScoringError("both evaluator reference arms required")
        for arm in ARMS:
            pp = predictions[family][arm]
            if set(pp) != expected or any(not finite(v) for v in pp.values()):
                raise ScoringError("reference must share the exact finite query denominator")
    return freeze["primary_nuisance"]


def score_policy(policy, candidate, targets, reference, query_binding):
    """Score a complete protected query panel, or preserve null support limits.

    Structural validity is not proof of source membership, target isolation,
    model freezing or pre-query capture. Those remain external owner obligations.
    """
    if policy not in POLICIES:
        raise ScoringError("separate named analysis policy required")
    _token(query_binding)
    rows = targets["cases"]
    if not isinstance(rows, list):
        raise ScoringError("query case list required")
    if rows:
        hierarchy(rows)
    expected = {r["id"] for r in rows}
    predictions = _predictions(candidate, expected, query_binding)
    roster = _roster(targets["mouse_support"])
    query_mice = {m for m, r in roster.items() if r["split"] == "query"}
    if any(r["split"] != "query" or r["mouse"] not in query_mice for r in rows):
        raise ScoringError("query response belongs to another role or unknown mouse")
    for row in rows:
        number(row.get("target"))
    new = [r for r in rows if r["subset"] == "new_image"]
    reasons = []
    if targets.get("complete_primary_support") is not True:
        reasons.append("incomplete_source_or_matching_support")
    if any(r["status"] != "complete_supported" for r in roster.values()):
        reasons.append("missing_intended_mouse_support")
    if {r["mouse"] for r in new} != query_mice:
        reasons.append("incomplete_query_new_image_denominator")
    if any(r["subset"] == "unknown_first_image_status" for r in rows):
        reasons.append("unknown_new_image_denominator")
    sd = targets.get("training_target_sd")
    if not finite(sd) or sd <= 0:
        reasons.append("unavailable_fit_scale")
    if reference is None or reference.get("predictions") is None or reference.get("frozen_selection") is None:
        reasons.append("unavailable_frozen_evaluator_reference")
    output = {"policy": policy, "matched_denominator": sorted(expected), "mouse_support": targets["mouse_support"],
              "complete_primary_support": not reasons, "primary_prediction_error": None,
              "primary_fixed_reference_gain": None, "references": {}, "celltypes": {},
              "unsupported_primary_reasons": reasons, "observational_contrast": "FIRST-minus-REPEAT",
              "causal_effect": False, "confirmatory_interval": None, "superiority_claim": None}
    for subset in SUBSETS:
        for celltype in CELL_TYPES:
            rr = [r for r in rows if r["subset"] == subset and r["cre_line"] == celltype]
            output["celltypes"][subset + "/" + celltype] = {
                "status": "not_evaluated_incomplete_primary" if rr else "no_support",
                "supported_case_count": len(rr), "observed": None, "predicted": None}
    if reasons:
        return output
    selected = _reference(reference, expected, policy, sd)
    for family in FAMILIES:
        output["references"][family] = {
            arm: macro_error(reference["predictions"][family][arm], new, sd) for arm in ARMS}
    output["primary_prediction_error"] = macro_error(predictions["JOINT"], new, sd)
    output["primary_fixed_reference_gain"] = number(
        output["references"][selected]["NUISANCE"] - output["primary_prediction_error"])
    output["candidate_nuisance_error_descriptive"] = macro_error(predictions["NUISANCE"], new, sd)
    output["selection_source"] = "validation_only_frozen_before_query"
    for subset in SUBSETS:
        for celltype in CELL_TYPES:
            rr = [r for r in rows if r["subset"] == subset and r["cre_line"] == celltype]
            if not rr:
                continue
            observed = contrasts({r["id"]: r["target"] for r in rr}, rr)
            predicted = contrasts(predictions["JOINT"], rr)
            output["celltypes"][subset + "/" + celltype] = {
                "status": "observed_matched_support", "supported_case_count": len(rr),
                "mice": sorted(observed), "observed_per_mouse": observed, "predicted_per_mouse": predicted,
                "observed_equal_mouse": mean(observed.values()), "predicted_equal_mouse": mean(predicted.values()),
                "contrast_absolute_error_equal_mouse": mean(abs(predicted[m] - observed[m]) for m in observed),
                "preferred_sign": None}
    return output
