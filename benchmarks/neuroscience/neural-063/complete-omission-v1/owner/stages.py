"""Concrete target-last scoring, paired reporting and independent arithmetic audit."""
from __future__ import annotations

from .io import ContractError
from .model import StageResult
from . import scoring, independent_score, audit, diagnostics, resource_report


CONDITIONS = [f"{mode}-{view}-{tool}" for mode in ("F", "I")
              for view in ("T", "N") for tool in ("G", "R")]
CONTROL_IDS = ["zero", "fit_mean", "trend"] + [f"perturb_{seed}" for seed in range(63001, 63006)]


def _index(ctx):
    value = ctx.read_input("query_index", roles={"query_index"}, cap=100_000_000)
    if (value.get("schema") != "neural063_query_index_v2" or
            value.get("target_shape") != [3] or value.get("heldout_mouse_count") != 19):
        raise ContractError("exact original query index required")
    ids = value.get("ids")
    if (not isinstance(ids, list) or not ids or len(ids) > 1_000_000 or
            any(not isinstance(x, str) or not x for x in ids) or ids != sorted(set(ids))):
        raise ContractError("complete unique sorted query identity list required")
    return value, ctx.inputs["query_index"].sha256


def _all_predictions(ctx, ids, query_hash):
    """Admit every prediction table before requesting a private target artifact."""
    result = {}
    bundles = {}
    for name, role, field, expected in [
        ("candidate_predictions", "candidate_predictions", "conditions", CONDITIONS),
        ("reference_predictions", "reference_predictions", "views", ["T", "N"]),
        ("control_predictions", "control_predictions", "controls", CONTROL_IDS),
    ]:
        bundle = ctx.read_input(name, roles={role}, cap=1_500_000_000)
        if bundle.get("query_index_sha256") != query_hash or set(bundle.get(field, {})) != set(expected):
            raise ContractError("incomplete/mismatched prediction bundle: " + name)
        bundles[name] = bundle
        for label in expected:
            prefix = "candidate" if field == "conditions" else "reference" if field == "views" else "control"
            result[prefix + ":" + label] = scoring.admit_predictions(bundle[field][label], ids)
    if len(result) != 18:
        raise ContractError("all eight candidates/two references/eight distinct controls required")
    return result, bundles


def _private_rows(ctx, ids, query_hash):
    private = ctx.read_input("query_targets", roles={"query_targets"}, cap=1_500_000_000)
    if (private.get("schema") != "neural063_query_targets_v2" or
            private.get("query_index_sha256") != query_hash):
        raise ContractError("wrong operator target binding")
    rows = private.get("rows")
    if (not isinstance(rows, list) or [r.get("id") for r in rows] != ids or
            any(r.get("split") != "query" for r in rows)):
        raise ContractError("complete bound query target row set required")
    scale = ctx.read_input("fit_scale", roles={"fit_scale"}, cap=1_000_000)
    if (scale.get("schema") != "neural063_fit_scale_v2" or scale.get("fit_mice") != 73 or
            private.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256):
        raise ContractError("target scoring scale is not the bound FIT73 scalar")
    sd = scoring.number(scale.get("training_target_sd"))
    if sd <= 0:
        raise ContractError("positive FIT-only scale required")
    scoring.hierarchy(rows, 19)
    return rows, sd


def _support(ctx):
    census = ctx.read_input("support_census", roles={"support_census"}, cap=100_000_000)
    expected = {"mice": 107, "sessions": 703, "experiments": 1936, "published_roi_rows": 133066}
    if census.get("source_counts") != expected:
        raise ContractError("full original source census required")
    if census.get("supported_mice_by_split") != {"fit": 73, "validation": 15, "query": 19}:
        raise ContractError("all original mice must have supported omissions")
    experiments = census.get("experiments")
    if not isinstance(experiments, list) or len(experiments) != 1936:
        raise ContractError("every source experiment needs an explicit support disposition")
    for x in experiments:
        counts = [x.get(k) for k in ("original_omissions", "timing_excluded", "thinning_excluded",
                                     "scheduled", "supported", "clock_unsupported")]
        if any(type(n) is not int or n < 0 for n in counts):
            raise ContractError("exact nonnegative support counts required")
        if counts[0] != sum(counts[1:4]) or counts[3] != sum(counts[4:]):
            raise ContractError("full omission disposition equations do not reconcile")
    return census


def score_stage(ctx):
    index, qhash = _index(ctx)
    predictions, _ = _all_predictions(ctx, index["ids"], qhash)
    # This import cannot be replaced by a candidate field asserting isolation.
    # The concrete runtime component interrogates its registered job backend.
    from runtime.custody import verify_scoring_barrier
    custody = verify_scoring_barrier(ctx)
    qualification = ctx.read_input("qualification", roles={"reference_qualification"}, cap=4_000_000)
    equivalence = ctx.read_input("query_equivalence", roles={"reference_query_equivalence"}, cap=4_000_000)
    if (equivalence.get("schema") != "neural063_query_equivalence_v2" or
            equivalence.get("primary_prediction_sha256") != ctx.inputs["reference_predictions"].sha256 or
            equivalence.get("query_index_sha256") != qhash or
            equivalence.get("fit_scale_sha256") != ctx.inputs["fit_scale"].sha256):
        raise ContractError("query equivalence belongs to another reference capture")
    if equivalence.get("status") != "equivalent":
        raise ContractError("independent query prediction equivalence not established")
    if any(qualification.get("views", {}).get(v, {}).get("empirical_status") != "met" for v in ("T", "N")):
        raise ContractError("reference competence failure blocks query scoring route")
    census = _support(ctx)
    # Exact target-last boundary: every table is admitted and all actual writers
    # are stopped before the first private target body is requested.
    rows, sd = _private_rows(ctx, index["ids"], qhash)
    scores = {name: scoring.absolute(p, rows, sd, 19) for name, p in predictions.items()}
    fit = ctx.read_input("fit_rows", roles={"fit_rows"}, cap=1_500_000_000)
    validation = ctx.read_input("validation_rows", roles={"validation_rows"}, cap=1_500_000_000)
    for split, value, mice in (("fit", fit, 73), ("validation", validation, 15)):
        if value.get("schema") != "neural063_rows_v2" or value.get("split") != split:
            raise ContractError("fixed development support envelope required for diagnostics")
        scoring.hierarchy(value["rows"], mice)
    strata = diagnostics.describe(rows, predictions, sd, census, fit["rows"], validation["rows"])
    strata_ref = ctx.write_json("support_diagnostics.json", strata, role="support_diagnostics")
    gains = {name: scoring.gain(scores["candidate:" + name]["primary"],
                               scores["reference:T"]["primary"], qualified=True)
             for name in CONDITIONS}
    value = {"schema": "neural063_score_bundle_v2", "query_index_sha256": qhash,
             "target_artifact_sha256": ctx.inputs["query_targets"].sha256,
             "fit_scale_sha256": ctx.inputs["fit_scale"].sha256,
             "scores": scores, "reference_gain": gains,
             "support_diagnostics": strata_ref.object(),
             "aliases": {"last_bin_persistence": "control:zero"},
             "source_counts": census["source_counts"],
             "supported_mice_by_split": census["supported_mice_by_split"],
             "custody": custody, "scientific_qualification": "requires_complete_independent_audit"}
    out = ctx.write_json("scores.json", value, role="score_bundle")
    return StageResult("complete", {"scores": out, "support_diagnostics": strata_ref}, {"score_tables": 18, "query_mice": 19})


def _comparison(scores, a, b):
    pair = scoring.paired(scores[a]["per_mouse"], scores[b]["per_mouse"], 19)
    bootstrap = scoring.bootstrap(pair, seed=63019)
    return {"a": a, "b": b, **pair, "uncertainty": bootstrap}


def reporting_stage(ctx):
    bundle = ctx.read_input("scores", roles={"score_bundle"}, cap=1_500_000_000)
    scores = bundle.get("scores", {})
    expected = {"candidate:" + x for x in CONDITIONS} | {"reference:T", "reference:N"} | {"control:" + x for x in CONTROL_IDS}
    if bundle.get("schema") != "neural063_score_bundle_v2" or set(scores) != expected:
        raise ContractError("complete original score bundle required")
    primary = _comparison(scores, "candidate:I-N-R", "candidate:F-N-R")
    secondary = {}
    for mode in ("F", "I"):
        for tool in ("G", "R"):
            secondary["information:" + mode + "-" + tool] = _comparison(
                scores, f"candidate:{mode}-N-{tool}", f"candidate:{mode}-T-{tool}")
    for mode in ("F", "I"):
        for view in ("T", "N"):
            secondary["tool:" + mode + "-" + view] = _comparison(
                scores, f"candidate:{mode}-{view}-R", f"candidate:{mode}-{view}-G")
    diagnostics = {"neural_reference_minus_timing": _comparison(scores, "reference:N", "reference:T")}
    for control in CONTROL_IDS:
        diagnostics[control + "_minus_neural_reference"] = _comparison(scores, "control:" + control, "reference:N")
    for condition in CONDITIONS:
        diagnostics[condition + "_minus_timing_reference"] = _comparison(scores, "candidate:" + condition, "reference:T")
    value = {"schema": "neural063_paired_report_v2", "scores_sha256": ctx.inputs["scores"].sha256,
             "primary": primary, "secondary": secondary, "diagnostics": diagnostics,
             "secondary_interpretation": "descriptive estimates/intervals only; no significance or best-arm substitution",
             "source_counts": bundle["source_counts"], "query_mice": 19,
             "bootstrap_unit": "whole_mouse_with_all_nested_observations_and_pairs",
             "reference_gain": bundle["reference_gain"], "support_diagnostics": bundle["support_diagnostics"],
             "limitations": ["retrospective provider dF/F/ROI processing", "omission-conditional prediction, not a causal omission effect",
                             "baseline-subtraction dependence", "public-data/model exposure unknown", "one checkpoint/run", "19 released mouse units"]}
    out = ctx.write_json("paired_report.json", value, role="paired_report")
    return StageResult("complete", {"paired_report": out}, {"primary_contrasts": 1, "secondary_contrasts": 8})


def audit_stage(ctx):
    index, qhash = _index(ctx)
    predictions, _ = _all_predictions(ctx, index["ids"], qhash)
    from runtime.custody import verify_scoring_barrier
    custody = verify_scoring_barrier(ctx)
    rows, sd = _private_rows(ctx, index["ids"], qhash)
    scores = ctx.read_input("scores", roles={"score_bundle"}, cap=1_500_000_000)
    paired = ctx.read_input("paired_report", roles={"paired_report"}, cap=1_500_000_000)
    if paired.get("scores_sha256") != ctx.inputs["scores"].sha256:
        raise ContractError("paired report does not bind these scored outputs")
    reconstructions = {}
    for name, p in predictions.items():
        independent = independent_score.reconstruct(p, rows, sd, 19)
        agreements = independent_score.compare(scores["scores"][name], independent)
        reconstructions[name] = {"independent": independent, "agreements": agreements}
    narratives = ctx.read_input("narrative_receipts", roles={"narrative_receipts"}, cap=100_000_000)
    if set(narratives.get("reports", {})) != set(CONDITIONS):
        raise ContractError("all eight candidate report terminal outcomes required")
    incomplete = [name for name, record in narratives["reports"].items() if record.get("status") != "complete"]
    costs = resource_report.controllers(ctx, set(index["ids"]))
    cost_ref = ctx.write_json("resource_report.json", costs, role="resource_report")
    # A qualified independent human/scientific audit is a distinct signed input,
    # not something arithmetic reproduction can synthesize.
    scientific = ctx.read_input("scientific_review", roles={"independent_scientific_review"}, cap=4_000_000)
    census = _support(ctx)
    native_bytes = audit.source_bytes(ctx, census)
    inventory, inventory_hash, available = audit.ancestor_inventory(ctx)
    outstanding = audit.review_findings(scientific, ctx=ctx, inventory_hash=inventory_hash,
                                         available=available)
    primary_unavailable = paired["primary"]["contrast"]["status"] != "finite"
    disposition = ("interpretation_artifacts_incomplete" if incomplete else
                   "independent_scientific_obligations_open" if outstanding else
                   "primary_contrast_unavailable" if primary_unavailable else "full_attempt_verified")
    value = {"schema": "neural063_independent_audit_v2", "disposition": disposition,
             "source_counts": census["source_counts"], "custody": custody,
             "arithmetic_reconstructions": reconstructions,
             "narrative_failures": incomplete, "scientific_obligations_open": outstanding,
             "primary_contrast_unavailable": primary_unavailable,
             "scientific_review_sha256": ctx.inputs["scientific_review"].sha256,
             "ancestor_inventory_sha256": inventory_hash,
             "complete_resource_failure_inventory": inventory, "runtime_resource_report": cost_ref.object(),
             "raw_source_bytes": native_bytes["bytes"], "raw_source_provenance": native_bytes,
             "query_events": len(rows), "no_causal_or_online_claim": True}
    out = ctx.write_json("independent_audit.json", value, role="independent_audit")
    # Completing the audit records a disposition; it does not retroactively make
    # every scientific obligation pass, or replace failed candidate reports.
    return StageResult("complete", {"independent_audit": out, "resource_report": cost_ref}, {"disposition": disposition}, outstanding + incomplete)


def run(stage, ctx):
    ctx.require_scientific()
    handlers = {"E00": score_stage, "E01": reporting_stage, "E02": audit_stage}
    if stage not in handlers:
        raise ContractError("not an owner scoring/reporting stage")
    return handlers[stage](ctx)
