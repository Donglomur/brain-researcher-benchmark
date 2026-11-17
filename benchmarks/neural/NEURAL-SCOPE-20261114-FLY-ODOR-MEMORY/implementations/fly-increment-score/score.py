"""Evaluator-only paired fly-macro scoring; no target preparation or model fitting."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re

TASK_ID = "NEURAL-SCOPE-20261114-FLY-ODOR-MEMORY"
MODES = {"direct_observation", "typed_viewer", "tool_assisted", "frozen_program"}
ROLES = {"primary", "no_odor_diagnostic", "no_wind_diagnostic"}
DEFINITION = "mean_goal_aligned_speed_over_(physical_offset,physical_offset+5s]"
MAX_BYTES = 16 * 1024 * 1024
MAX_EPISODES = 100_000


class InvalidEvaluation(ValueError):
    """Invalid evaluator operands or incomplete prediction output."""


def require(condition, message):
    if not condition:
        raise InvalidEvaluation(message)


def fields(value, required, context):
    require(isinstance(value, dict), f"{context}: expected object")
    require(set(value) == set(required), f"{context}: incorrect fields")


def identifier(value, context):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 256,
            f"{context}: expected nonempty identifier, at most 256 characters")
    return value


def digest(value, context):
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            f"{context}: expected lowercase SHA-256")


def number(value, context):
    require(type(value) in (int, float), f"{context}: expected finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise InvalidEvaluation(f"{context}: numeric range exceeded") from exc
    require(math.isfinite(result), f"{context}: expected finite number")
    return result


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "JSON: duplicate object key")
        result[key] = value
    return result


def read_json(path, expected_sha256):
    """Read a bounded operand once, authenticate those same bytes, then parse."""
    digest(expected_sha256, "expected digest")
    with Path(path).open("rb") as source:
        payload = source.read(MAX_BYTES + 1)
    require(len(payload) <= MAX_BYTES, "operand exceeds 16 MiB")
    require(hashlib.sha256(payload).hexdigest() == expected_sha256, "operand digest mismatch")
    try:
        value = json.loads(payload.decode("utf-8"), object_pairs_hook=no_duplicates,
                           parse_constant=lambda value: (_ for _ in ()).throw(
                               InvalidEvaluation("JSON: nonfinite numeric constant")))
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise InvalidEvaluation("operand is not valid bounded UTF-8 JSON") from exc
    return value


def validate_targets(targets):
    fields(targets, {"schema", "task_id", "target_definition", "target_units",
                     "evaluation_plan_sha256", "episodes"}, "targets")
    require(targets["schema"] == "fly-odor-evaluation-set/v1", "incorrect target schema")
    require(targets["task_id"] == TASK_ID, "incorrect task")
    require(targets["target_definition"] == DEFINITION, "incorrect target definition")
    require(targets["target_units"] == "mm/s", "target units must be mm/s")
    digest(targets["evaluation_plan_sha256"], "evaluation plan")
    rows = targets["episodes"]
    require(isinstance(rows, list) and 0 < len(rows) <= MAX_EPISODES,
            "targets must contain 1 to 100000 census episodes")
    seen = set()
    fly_genotypes = {}
    trial_context = {}
    for row in rows:
        fields(row, {"episode_id", "trial_id", "fly_id", "genotype", "condition",
                     "role", "eligible", "exclusion_reasons", "target_mm_s",
                     "future_reencounter"}, "episode")
        for key in ("episode_id", "trial_id", "fly_id", "genotype", "condition"):
            identifier(row[key], key)
        require(row["episode_id"] not in seen, "duplicate episode identity")
        seen.add(row["episode_id"])
        fly = row["fly_id"]
        require(fly_genotypes.setdefault(fly, row["genotype"]) == row["genotype"],
                "one fly has multiple genotypes")
        # trial_id is local within a fly; its condition/role must be coherent.
        trial_key = (fly, row["trial_id"])
        context = (row["condition"], row["role"])
        require(trial_context.setdefault(trial_key, context) == context,
                "one fly/trial has multiple condition or role assignments")
        require(isinstance(row["role"], str) and row["role"] in ROLES, "incorrect episode role")
        require(type(row["eligible"]) is bool, "eligibility must be boolean")
        reasons = row["exclusion_reasons"]
        require(isinstance(reasons, list), "exclusion reasons must be a list")
        for reason in reasons:
            identifier(reason, "exclusion reason")
        require(len(set(reasons)) == len(reasons), "duplicate exclusion reason")
        require(row["future_reencounter"] is None or type(row["future_reencounter"]) is bool,
                "future reencounter must be boolean or null")
        if row["eligible"]:
            require(not reasons, "eligible episode has exclusion reasons")
            number(row["target_mm_s"], "target")
        else:
            require(bool(reasons), "ineligible episode needs exclusion reason")
            require(row["target_mm_s"] is None, "ineligible episode must not supply a target")
    return rows


def validate_predictions(predictions, targets, targets_sha256, arm):
    fields(predictions, {"schema", "task_id", "arm", "access_mode", "method_id",
                         "targets_sha256", "evaluation_plan_sha256", "predictions"}, arm)
    require(predictions["schema"] == "fly-odor-predictions/v1", "incorrect prediction schema")
    require(predictions["task_id"] == TASK_ID, "incorrect prediction task")
    require(predictions["arm"] == arm, "incorrect prediction arm")
    require(isinstance(predictions["access_mode"], str) and predictions["access_mode"] in MODES,
            "incorrect access mode")
    identifier(predictions["method_id"], "method id")
    digest(predictions["targets_sha256"], "prediction target digest")
    require(predictions["targets_sha256"] == targets_sha256, "prediction target binding mismatch")
    require(predictions["evaluation_plan_sha256"] == targets["evaluation_plan_sha256"],
            "prediction plan binding mismatch")
    rows = predictions["predictions"]
    require(isinstance(rows, list) and len(rows) <= MAX_EPISODES, "invalid prediction row list")
    values = {}
    for row in rows:
        fields(row, {"episode_id", "prediction_mm_s"}, "prediction row")
        episode = identifier(row["episode_id"], "prediction episode")
        require(episode not in values, "duplicate prediction episode")
        values[episode] = number(row["prediction_mm_s"], "prediction")
    expected = {row["episode_id"] for row in targets["episodes"] if row["eligible"]}
    require(set(values) == expected,
            "prediction census mismatch: every eligible episode exactly once; no other episodes")
    return values


def finite_mean(values):
    """Avoid overflowing an otherwise representable mean solely in its sum."""
    try:
        result = math.fsum(value / len(values) for value in values)
    except (OverflowError, ValueError) as exc:
        raise InvalidEvaluation("loss aggregation exceeds numeric range") from exc
    require(math.isfinite(result), "loss aggregation exceeds numeric range")
    return result


def squared_error(prediction, target):
    difference = prediction - number(target, "target")
    result = difference * difference
    require(math.isfinite(result), "squared error exceeds numeric range")
    return result


def summarize(rows, losses):
    """Census denominator stays fixed; zero-eligible flies never receive zero loss."""
    by_fly = defaultdict(list)
    for row in rows:
        by_fly[row["fly_id"]].append(row)
    all_fly_effects = []
    for fly, fly_rows in sorted(by_fly.items()):
        eligible = [row for row in fly_rows if row["eligible"]]
        nuisance = [losses[row["episode_id"]][0] for row in eligible]
        neural = [losses[row["episode_id"]][1] for row in eligible]
        paired = [losses[row["episode_id"]][2] for row in eligible]
        all_fly_effects.append({
            "fly_id": fly,
            "census_episodes": len(fly_rows),
            "eligible_episodes": len(eligible),
            "excluded_episodes": len(fly_rows) - len(eligible),
            "nuisance_mse_mm2_s2": finite_mean(nuisance) if eligible else None,
            "neural_mse_mm2_s2": finite_mean(neural) if eligible else None,
            "paired_loss_reduction_mm2_s2": finite_mean(paired) if eligible else None,
        })
    scored_flies = [row for row in all_fly_effects if row["eligible_episodes"]]
    macro = {}
    for field in ("nuisance_mse_mm2_s2", "neural_mse_mm2_s2", "paired_loss_reduction_mm2_s2"):
        macro[field] = finite_mean([row[field] for row in scored_flies]) if scored_flies else None
    reasons = Counter(reason for row in rows for reason in row["exclusion_reasons"])
    return {
        "census_episodes": len(rows),
        "eligible_episodes": sum(row["eligible"] for row in rows),
        "excluded_episodes": sum(not row["eligible"] for row in rows),
        "census_flies": len(by_fly),
        "scored_flies": len(scored_flies),
        "exclusion_reason_counts": dict(sorted(reasons.items())),
        "fly_macro": macro,
        "all_fly_effects": all_fly_effects,
    }


def score(targets, nuisance, neural, *, targets_sha256):
    """Compute point scores on a complete frozen census. Inputs stay evaluator-only."""
    digest(targets_sha256, "target digest")
    rows = validate_targets(targets)
    nuisance_values = validate_predictions(nuisance, targets, targets_sha256, "nuisance")
    neural_values = validate_predictions(neural, targets, targets_sha256, "neural_plus_nuisance")
    require(nuisance["access_mode"] == neural["access_mode"], "paired access modes differ")
    losses = {}
    for row in rows:
        if row["eligible"]:
            episode = row["episode_id"]
            reference_loss = squared_error(nuisance_values[episode], row["target_mm_s"])
            neural_loss = squared_error(neural_values[episode], row["target_mm_s"])
            losses[episode] = (reference_loss, neural_loss, reference_loss - neural_loss)

    # Genotypes and diagnostic roles are never pooled into a nominal primary score.
    genotype_reports = []
    by_genotype = defaultdict(list)
    for row in rows:
        by_genotype[row["genotype"]].append(row)
    for genotype, genotype_rows in sorted(by_genotype.items()):
        primary = [row for row in genotype_rows if row["role"] == "primary"]
        conditions = []
        strata = defaultdict(list)
        for row in genotype_rows:
            strata[(row["role"], row["condition"])].append(row)
        for (role, condition), selected in sorted(strata.items()):
            # These descriptive strata are produced only after the complete primary score.
            descriptive = []
            for label, value in (("absent", False), ("present", True), ("unknown", None)):
                stratum = [row for row in selected if row["future_reencounter"] is value]
                if stratum:
                    descriptive.append({"future_reencounter": label, **summarize(stratum, losses)})
            conditions.append({"role": role, "condition": condition, **summarize(selected, losses),
                               "descriptive_future_reencounter_strata": descriptive})
        genotype_reports.append({"genotype": genotype, "primary": summarize(primary, losses),
                                 "condition_reports": conditions})
    return {
        "schema": "fly-odor-paired-score/v1", "task_id": TASK_ID,
        "access_mode": neural["access_mode"], "targets_sha256": targets_sha256,
        "evaluation_plan_sha256": targets["evaluation_plan_sha256"],
        "nuisance_method_id": nuisance["method_id"], "neural_method_id": neural["method_id"],
        "metric": "paired nuisance MSE minus neural+nuisance MSE; equal fly weight",
        "direction": "higher", "loss_units": "mm^2/s^2",
        "genotype_reports": genotype_reports,
        "scope": "Retrospective information conditional on released derivatives; point estimates only.",
        "not_verified": ["physical odor offset and coordinate calibration", "biological identity aliases",
                         "complete authentic source cohort", "training and information boundaries",
                         "competence and validation-only selection of nuisance reference",
                         "fly-level uncertainty and multiplicity protocol", "participant access delivery"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("targets", "nuisance", "neural"):
        parser.add_argument(f"--{name}", required=True, type=Path)
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path,
                        help="fresh evaluator-private JSON result; never candidate feedback")
    args = parser.parse_args(argv)
    try:
        operands = {name: read_json(getattr(args, name), getattr(args, f"{name}_sha256"))
                    for name in ("targets", "nuisance", "neural")}
        result = score(**operands, targets_sha256=args.targets_sha256)
        result["operand_sha256"] = {name: getattr(args, f"{name}_sha256")
                                   for name in ("targets", "nuisance", "neural")}
        # No output is created until all validation and arithmetic have succeeded.
        encoded = json.dumps(result, allow_nan=False, sort_keys=True, indent=2) + "\n"
        import os
        descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(encoded)
    except (InvalidEvaluation, OSError) as exc:
        parser.exit(2, f"scoring failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
