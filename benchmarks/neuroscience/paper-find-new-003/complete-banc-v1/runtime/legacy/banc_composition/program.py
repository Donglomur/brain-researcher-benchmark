"""Complete explicit task branch registry and executable source composition.

Each stage is invoked independently on its full declared population. Nothing
feeds fresh community labels into fixed-label consumers. A full bundle must
account for every endpoint, including unselected native and missing-source work.
It is impossible to obtain a qualified/scientifically complete result here.
"""
from dataclasses import dataclass, replace
import re
import math
from .sources import component, capture
from . import consumers, influence

ARMS = ("paper_and_data", "paper_data_official_code")
ENDPOINTS = (
    "community_python", "community_R", "centrality_literal", "centrality_count5",
    "an_dn_direct", "an_dn_reciprocity", "an_dn_supercluster", "an_dn_shortest_chains",
    "an_dn_effector_upstream", "an_dn_influence", "cns_unsigned_all", "cns_unsigned_neck",
    "cns_signed_all", "cns_signed_supercluster_neck", "cns_partner_distribution",
    "cns_out_of_network", "influence_full", "influence_no_neck", "influence_normalization",
    "sensory_panel_3_5_10", "cns_influence_panel_sweeps", "source_binomial_null",
    "native_statistics_and_display", "randomized_graph_null_ensemble",
)
GAPS = {
    "randomized_graph_null_ensemble": "No randomized graph producer located in inspected exact source; binomial/label permutation are different nulls.",
    "native_statistics_and_display": "R KS/Holm, Wilcoxon, Type-III ANOVA, permutation, plotting/order helpers require separately selected native source/runtime; no inference fabricated.",
    "sensory_panel_3_5_10": "Existing public 17x19x3 contract retained; exact native influencer producer/output support and full frozen-GCS preparation are separate held dependencies.",
}


@dataclass(frozen=True)
class Stage:
    endpoint: str
    action: str
    arguments: dict
    reason: str | None = None
    declared_binding: object | None = None


@dataclass(frozen=True)
class TaskIdentity:
    """Declarations only. Different metadata namespaces are kept explicit."""
    original_edges_sha256: str
    metadata_sha256_by_endpoint: tuple[tuple[str, str], ...]
    materialization: int
    synapse_source: str


@dataclass(frozen=True)
class StageResult:
    endpoint: str
    state: str
    value: object
    reason: str | None


@dataclass(frozen=True)
class TaskResult:
    information_arm: str
    declared_identity: TaskIdentity
    stages: tuple[StageResult, ...]
    complete_branch_accounting: bool = True
    whole_paper_execution_complete: bool = False
    scientific_qualification: bool = False


def _need(ok, message):
    if not ok: raise ValueError(message)


def reciprocity_program(data, *, source_pair_string_order):
    """Reviewed long-form NT/rank consumer plus literal source233–255 tables.

    Plot membership uses source-formatted pair strings, not a silently repaired
    tuple key. Native factor/grouping order is explicit; plotting is unexecuted.
    """
    result = component("reciprocity").compute_reciprocity(data)
    directed = tuple(r.pre_cluster + " → " + r.post_cluster for r in result.directed_pairs)
    reciprocal = tuple(r.pre_cluster + " ↔ " + r.post_cluster for r in result.reciprocal_pairs)
    _need(len(set(directed)) == len(directed), "literal_directed_factor_levels_must_be_unique")
    dir_rows = tuple(r for r in result.transmitter_rows if r.pre_cluster + " → " + r.post_cluster in directed)
    rec_rows = tuple(r for r in result.transmitter_rows if r.pre_cluster + " ↔ " + r.post_cluster in reciprocal)
    strings = {r.pre_cluster + " ↔ " + r.post_cluster for r in rec_rows}
    _need(type(source_pair_string_order) is tuple and all(type(s) is str for s in source_pair_string_order)
          and len(set(source_pair_string_order)) == len(source_pair_string_order)
          and strings <= set(source_pair_string_order), "complete_native_pair_string_group_order")
    totals = {s: math.fsum(r.norm for r in rec_rows if r.pre_cluster + " ↔ " + r.post_cluster == s and not math.isnan(r.norm))
              for s in source_pair_string_order if s in strings}
    rec_order = tuple(sorted(totals, key=totals.get))
    return {"full_reciprocity": result, "directed_NT_rows": dir_rows,
            "reciprocal_NT_rows": rec_rows, "directed_factor_levels": tuple(reversed(directed)),
            "reciprocal_factor_levels": rec_order, "native_plot_executed": False,
            "scientific_qualification": False}


def an_dn_chain_program(edges, binding, *, cell_type_order, path_selector, selection,
                        cluster_order, max_pair_checks, max_paths, combo_order):
    """Prepare the whole graph, select all-pair paths, consume and summarize.

    The explicit native/candidate selector gets the complete prepared graph.
    Its tied path choices are neither fabricated here nor silently truncated.
    """
    from . import an_dn
    _need(callable(path_selector), "explicit_whole_graph_path_selector")
    graph = an_dn.prepare_chains(edges, binding, cell_type_order=cell_type_order)
    paths = path_selector(graph)
    result = an_dn.consume_chains(graph, paths, cluster_order=cluster_order, selection=selection,
                                 max_pair_checks=max_pair_checks, max_paths=max_paths)
    return {"graph": graph, "complete_paths": result,
            "display": an_dn.chain_display(result, combo_order=combo_order),
            "scientific_qualification": False}


def normalized_influence_program(rows, binding, *, seed_order, target_order, metric,
                                 rounding):
    from . import an_dn
    result = an_dn.normalize_influence(rows, binding, rounding=rounding)
    return {"normalized": result,
            "complete_matrix": an_dn.influence_matrix(result, seed_order=seed_order,
                                                       target_order=target_order, metric=metric),
            "scientific_qualification": False}


def an_dn_influence_program(rows, metadata, binding, *, seed_order, target_order, metric,
                           rounding):
    from . import an_dn
    _need(metric == "influence_log", "literal_AN_DN_plot_metric_influence_log")
    mapped = an_dn.map_an_dn_influence(rows, metadata, binding)
    first_pass = an_dn.normalize_influence(mapped, binding, rounding=rounding)
    # Source735 normalizes once; plot helper3085 then filters seed_12 and
    # helper3118 recalculates from the retained ORIGINAL first-row values.
    retained = tuple(row for row in first_pass.rows if row.first_row.level == "seed_12")
    if not retained:
        return {"input_rows": len(rows), "mapped_rows": mapped, "first_pass": first_pass,
                "normalized": None, "complete_matrix": None,
                "source_plot_state": "skipped_no_seed12_rows", "scientific_qualification": False}
    second = an_dn.normalize_influence(tuple(row.first_row for row in retained), binding, rounding=rounding)
    # plot helper quantile=NULL leaves first-pass influence_quantile untouched.
    old_quantile = {(row.first_row.target, row.first_row.seed): row.influence_quantile for row in retained}
    second = replace(second, rows=tuple(replace(row, influence_quantile=old_quantile[(row.first_row.target, row.first_row.seed)])
                                        for row in second.rows))
    matrix = an_dn.influence_matrix(second, seed_order=seed_order, target_order=target_order, metric=metric)
    source_shape = (len({r.first_row.target for r in second.rows}), len({r.first_row.seed for r in second.rows}))
    return {"input_rows": len(rows), "mapped_rows": mapped, "first_pass": first_pass,
            "normalized": second, "complete_matrix": matrix,
            "source_plot_state": "skipped_matrix_smaller_than2x2" if min(source_shape) < 2 else "matrix_ready_native_plot_unexecuted",
            "scientific_qualification": False}


def run_stage(stage):
    _need(type(stage) is Stage and stage.endpoint in ENDPOINTS and type(stage.arguments) is dict, "known_explicit_stage")
    name = stage.endpoint; a = dict(stage.arguments)
    if stage.action == "held":
        _need(type(stage.reason) is str and bool(stage.reason.strip()) and not a, "explicit_unexecuted_stage_reason")
        return StageResult(name, "held_not_executed", None, stage.reason)
    if name in GAPS:
        _need(stage.action == "source_gap" and not a, "unavailable_source_cannot_be_filled_by_generic_callback")
        return StageResult(name, "source_or_native_gap", None, GAPS[name])
    if stage.action == "source_gap":
        _need(name in ("influence_full", "influence_no_neck"), "source_gap_only_for_unbundled_influence_producer")
        variant = "full_CNS_source" if name == "influence_full" else "no_neck_CNS_source"
        _need(a.pop("variant", variant) == variant, "explicit_correct_influence_branch")
        prepared = influence.prepare_influence(variant=variant, **a)
        return StageResult(name, "requests_prepared_native_producer_gap", prepared, prepared.calculator_source_state)
    _need(stage.action in ("reference", "candidate", "consume", "source"), "explicit_execution_action")
    if name == "community_python":
        m = component("community")
        _need(stage.action in ("reference", "candidate"), "community_method_choice")
        value = (m.run_python_reference if stage.action == "reference" else m.run_candidate)(**a)
    elif name == "community_R":
        _need(stage.action == "source" and not a, "R_native_branch_remains_separate_source_entrypoint")
        path, raw = capture("community_R")
        return StageResult(name, "native_source_ready_not_executed", raw,
                           "Invoke banc_community_R with complete native tables and declared runtime under separate selection.")
    elif name in ("centrality_literal", "centrality_count5"):
        m = component("centrality")
        branch = "literal_producer_all_rows" if name == "centrality_literal" else "consumer_documented_count_ge5"
        _need(a.pop("branch", branch) == branch and stage.action in ("reference", "candidate"), "centrality_branch_and_method")
        value = (m.run_reference if stage.action == "reference" else m.run_candidate)(branch=branch, **a)
    elif name == "an_dn_reciprocity":
        _need(stage.action == "consume", "literal_reciprocity_consumer")
        value = reciprocity_program(**a)
    elif name.startswith("an_dn_") or name == "influence_normalization":
        from . import an_dn
        _need(stage.action == "consume", "literal_fixed_annotation_consumer")
        functions = {
            "an_dn_direct": an_dn.an_dn_direct,
            "an_dn_supercluster": an_dn.an_dn_supercluster_direct,
            "an_dn_shortest_chains": an_dn_chain_program,
            "an_dn_effector_upstream": an_dn.effector_upstream,
            "an_dn_influence": an_dn_influence_program,
            "influence_normalization": normalized_influence_program,
        }
        value = functions[name](**a)
    elif name == "cns_influence_panel_sweeps":
        from .cns_panels import run_all_panels
        _need(stage.action == "consume", "literal_all_eight_CNS_panel_consumers")
        value = run_all_panels(**a)
    elif name.startswith("cns_") and name not in ("cns_partner_distribution", "cns_out_of_network"):
        m = component("cns")
        branch = {"cns_unsigned_all": "unsigned_cns_all", "cns_unsigned_neck": "unsigned_cns_neck",
                  "cns_signed_all": "signed_cns_all", "cns_signed_supercluster_neck": "signed_supercluster_neck"}[name]
        _need(a.pop("branch", branch) == branch and stage.action == "consume", "fixed_CNS_consumer_branch")
        value = m.compute_cns(branch=branch, **a)
    elif name == "cns_partner_distribution":
        _need(stage.action == "consume", "literal_partner_consumer")
        value = consumers.partner_distribution(**a)
    elif name == "cns_out_of_network":
        _need(stage.action == "consume", "literal_home_away_consumer")
        value = consumers.out_of_network(**a)
    elif name == "source_binomial_null":
        from .nulls import source_binomial_summary
        _need(stage.action == "consume", "literal_binomial_null_is_not_random_graph_ensemble")
        value = source_binomial_summary(**a)
    elif name in ("influence_full", "influence_no_neck"):
        variant = "full_CNS_source" if name == "influence_full" else "no_neck_CNS_source"
        _need(stage.action == "candidate" and a.get("program").variant == variant, "explicit_matching_candidate_influence_variant")
        value = influence.run_candidate(**a)
    else:
        raise ValueError("unimplemented_stage_cannot_be_silently_completed")
    return StageResult(name, "computed_unqualified", value, None)


def _binding_identity(binding):
    edge_hash = getattr(binding, "edges_sha256", getattr(binding, "edge_sha256", None))
    return (getattr(binding, "metadata_sha256", None), edge_hash,
            getattr(binding, "materialization", None), getattr(binding, "synapse_source", None))


def run_program(stages, *, information_arm, identity):
    """Require all branches; never select a canonical producer or ignore a gap.

    Both arms expose the same scientific problem. Code access is enforced by
    an external artifact stager, not faked by this invocation metadata. Each
    explicit candidate callback retains its reviewed full-population contract.
    """
    _need(information_arm in ARMS, "unchanged_information_arm")
    _need(type(stages) is tuple and all(type(s) is Stage for s in stages)
          and tuple(s.endpoint for s in stages) == ENDPOINTS, "complete_ordered_task_branch_accounting")
    _need(type(identity) is TaskIdentity and type(identity.materialization) is int
          and identity.materialization == 888 and identity.synapse_source == "v2", "whole_task_original_version")
    _need(type(identity.metadata_sha256_by_endpoint) is tuple
          and tuple(k for k, v in identity.metadata_sha256_by_endpoint) == ENDPOINTS,
          "explicit_metadata_namespace_for_every_endpoint")
    hashes = (identity.original_edges_sha256,) + tuple(v for _, v in identity.metadata_sha256_by_endpoint)
    _need(all(type(v) is str and re.fullmatch(r"[0-9a-f]{64}", v) for v in hashes), "task_declared_original_input_hashes")
    meta = dict(identity.metadata_sha256_by_endpoint)
    # Complete preflight precedes every numerical consumer/callback. Hashes
    # remain declarations; this never reads authentic objects to verify them.
    for stage in stages:
        if stage.action in ("held", "source") or stage.endpoint in GAPS: continue
        expected = (meta[stage.endpoint], identity.original_edges_sha256, 888, "v2")
        a = stage.arguments
        binding = a.get("binding")
        for container in ("inputs", "program", "graph"):
            if container in a: binding = getattr(a[container], "binding", binding)
        if binding is None: binding = stage.declared_binding
        _need(_binding_identity(binding) == expected, "endpoint_uses_declared_complete_input_namespace:" + stage.endpoint)
        if stage.declared_binding is not None:
            _need(_binding_identity(stage.declared_binding) == expected, "conflicting_stage_input_declaration")
    return TaskResult(information_arm, identity, tuple(run_stage(stage) for stage in stages))
