"""Literal CNS partner/distribution consumers on complete supplied joined rows.

No new community fit enters fixed annotations. Native tests/plots are returned
as explicit unresolved work; these functions perform only the source reductions.
"""
from dataclasses import dataclass
import re

REVISION = "2e78ce38e946ab80e120a42f504a019b3a567fef"
MAX_EXACT = (1 << 53) - 1


@dataclass(frozen=True)
class Binding:
    metadata_sha256: str
    edges_sha256: str
    producer_revision: str
    materialization: int
    synapse_source: str
    annotation_origin: str
    join_policy: str


@dataclass(frozen=True)
class Metadata:
    id: str
    super_class: str | None
    cell_type: str | None
    super_cluster: str | None
    cns_network: str | None


@dataclass(frozen=True)
class Edge:
    pre: str
    post: str
    count: int | None
    pre_cluster: str | None
    post_cluster: str | None
    pre_super_cluster: str | None
    post_super_cluster: str | None
    pre_cns_network: str | None
    post_cns_network: str | None
    pre_super_class: str | None
    post_super_class: str | None


def require(ok, message):
    if not ok:
        raise ValueError(message)


def validate(edges, binding):
    require(type(edges) is tuple and type(binding) is Binding, "complete_tuple_and_binding")
    require(binding.producer_revision == REVISION and type(binding.materialization) is int
            and binding.materialization == 888 and binding.synapse_source == "v2"
            and binding.annotation_origin == "canonical_enriched_metadata"
            and binding.join_policy == "supplied_complete_literal_left_joins",
            "explicit_fixed_source_binding")
    for digest in (binding.metadata_sha256, binding.edges_sha256):
        require(type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest), "declared_source_hash")
    for row in edges:
        require(type(row) is Edge and type(row.pre) is str and type(row.post) is str, "edge_row_and_ID_domain")
        require(row.count is None or type(row.count) is int and 0 <= row.count <= MAX_EXACT,
                "declared_portable_exact_integer_count_domain")
        for value in (row.pre_cluster, row.post_cluster, row.pre_super_cluster, row.post_super_cluster,
                      row.pre_cns_network, row.post_cns_network, row.pre_super_class, row.post_super_class):
            require(value is None or type(value) is str, "nullable_string_annotation")


def standalone_neck_ids(metadata):
    """Literal CNS standalone branch, not connectivity script's named exclusions."""
    require(type(metadata) is tuple, "complete_metadata_tuple")
    result = set()
    for row in metadata:
        require(type(row) is Metadata and type(row.id) is str, "metadata_row")
        for value in (row.super_class, row.cell_type, row.super_cluster, row.cns_network):
            require(value is None or type(value) is str, "nullable_string_metadata")
        # R grepl(pattern, NA_character_) is FALSE; NA cell_type is not excluded.
        if row.super_class in ("ascending", "descending") and not (
                row.cell_type is not None and re.search(r"^SA|^SN|^AN_4|AN_5|^IN", row.cell_type)):
            result.add(row.id)
    return frozenset(result)


def partner_distribution(edges, metadata, binding, *, population_branch, supplied_neck_ids,
                         source_pair_order):
    """Source70–151: exact distinct, row counts, supercluster proportions.

    Both standalone initialization and pre-existing AN/DN cohort are explicit.
    Source grouping order is supplied; no locale sorting or plot filtering.
    """
    validate(edges, binding)
    standalone = standalone_neck_ids(metadata)
    if population_branch == "standalone_CNS_source":
        require(supplied_neck_ids is None, "standalone_does_not_accept_external_cohort")
        neck = standalone
    else:
        require(population_branch == "preexisting_explicit_AN_DN_cohort" and type(supplied_neck_ids) is frozenset
                and all(type(x) is str for x in supplied_neck_ids), "explicit_source_initialization_branch")
        neck = supplied_neck_ids
    require(type(source_pair_order) is tuple and len(set(source_pair_order)) == len(source_pair_order)
            and all(type(p) is tuple and len(p) == 2 and all(type(x) is str for x in p) for p in source_pair_order),
            "explicit_supercluster_network_group_order")
    distinct = {}; selected = []
    for i, row in enumerate(edges):
        if row.pre not in neck and row.post not in neck:
            continue
        if all(v is None for v in (row.pre_cluster, row.post_cluster, row.pre_cns_network, row.post_cns_network)):
            continue
        key = (row.post, row.pre, row.pre_cns_network, row.pre_cluster, row.pre_super_cluster,
               row.post_cns_network, row.post_cluster, row.post_super_cluster, row.count)
        if key not in distinct:
            distinct[key] = row; selected.append(i)
    counts = {"output": {}, "input": {}}
    for row in distinct.values():
        if row.count is None or row.count < 3:
            continue
        candidates = (("output", row.pre_super_cluster, row.post_cns_network, row.post),
                      ("input", row.post_super_cluster, row.pre_cns_network, row.pre))
        for direction, cluster, network, outside in candidates:
            if cluster is not None and network is not None and outside not in neck:
                key = (cluster, network)
                counts[direction][key] = counts[direction].get(key, 0) + 1
    require(set().union(*(set(v) for v in counts.values())) <= set(source_pair_order), "all_groups_in_source_order")
    population = {}; seen = set()
    for row in metadata:
        if row.super_class not in ("ascending", "descending") or row.id in seen:
            continue
        seen.add(row.id)
        if row.super_cluster is not None:
            key = (row.super_cluster, row.cns_network)
            population[key] = population.get(key, 0) + 1
    population_totals = {}
    for (cl, _), n in population.items(): population_totals[cl] = population_totals.get(cl, 0) + n
    rows = []
    for direction, values in counts.items():
        totals = {}
        for (cl, _), count in values.items(): totals[cl] = totals.get(cl, 0) + count
        for cl, net in source_pair_order:
            if (cl, net) not in values: continue
            n = population.get((cl, net))
            rows.append((direction, cl, net, values[(cl, net)], values[(cl, net)] / totals[cl],
                         n or 0, n / population_totals[cl] if n is not None else None))
    return {"rows": tuple(rows), "retained_distinct_row_indices": tuple(selected), "neck_ids": neck,
            "population_branch": population_branch, "binding": binding, "scientific_qualification": False}


def out_of_network(edges, binding, *, source_id_order):
    """Source226–305, including literal incoming post-label check twice."""
    validate(edges, binding)
    require(type(source_id_order) is tuple and all(type(i) is str for i in source_id_order)
            and len(set(source_id_order)) == len(source_id_order), "explicit_native_arrange_ID_order")
    directional = []
    for direction in ("outgoing", "incoming"):
        groups = {}
        for row in edges:
            survives = (row.pre_cns_network is not None or row.post_cns_network is not None) if direction == "outgoing" else row.post_cns_network is not None
            if not survives or row.count is None or row.count < 3: continue
            identity = row.pre if direction == "outgoing" else row.post
            groups.setdefault(identity, []).append(row)
        for identity, rows in groups.items():
            home = sum(r.pre_cns_network == r.post_cns_network for r in rows
                       if r.pre_cns_network is not None and r.post_cns_network is not None)
            away = sum(r.pre_cns_network != r.post_cns_network for r in rows
                       if r.pre_cns_network is not None and r.post_cns_network is not None)
            types = dict.fromkeys((r.pre_super_class if direction == "outgoing" else r.post_super_class)
                                 if (r.pre_super_class if direction == "outgoing" else r.post_super_class) in ("ascending", "descending")
                                 else "other" for r in rows)
            # distinct(type,id,home,away,prop) retains inconsistent type rows.
            directional.extend((kind, identity, home, away) for kind in types)
    totals = {}; first_type = {}
    for kind, identity, home, away in directional:
        prior = totals.get(identity, (0, 0))
        totals[identity] = (prior[0] + home, prior[1] + away)
        first_type.setdefault(identity, kind)
    require(set(totals) <= set(source_id_order), "complete_source_ID_order")
    rows = tuple((identity, first_type[identity], totals[identity][0], totals[identity][1],
                  totals[identity][1] / sum(totals[identity])) for identity in source_id_order
                 if identity in totals and all(totals[identity]))
    return {"rows": rows, "directional_rows": tuple(directional), "binding": binding,
            "native_statistics": ("stats::ks.test_default_each_type_vs_other", "stats::p.adjust_holm", "write_nonparam_summary"),
            "native_statistics_executed": False, "scientific_qualification": False}
