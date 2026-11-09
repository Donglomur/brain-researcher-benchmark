"""Full and no-neck source influence requests; no invented graph solver.

The literal R loop needs influencer::influence_calculator_py and
calculate_influence_py. This package builds every request from all supplied
rows; the missing pinned native producer is a hard reference boundary.
"""
from dataclasses import dataclass
import re
from .consumers import Binding, REVISION, require


@dataclass(frozen=True)
class Metadata:
    root_id: str
    cell_type: str | None
    super_class: str | None
    cell_class: str | None
    seed_02: str | None
    seed_07: str | None
    super_cluster: str | None
    cns_network: str | None


@dataclass(frozen=True)
class Edge:
    pre: str
    post: str
    count: object
    pre_super_class: str | None
    post_super_class: str | None


@dataclass(frozen=True)
class SeedRequest:
    level: str
    seed: str
    seed_ids: tuple[str, ...]


@dataclass(frozen=True)
class InfluenceProgram:
    variant: str
    loop_mode: str
    complete_metadata: tuple[Metadata, ...]
    complete_edges: tuple[Edge, ...]
    selected_edge_indices: tuple[int, ...]
    target_ids: tuple[str, ...]
    requests: tuple[SeedRequest, ...]
    count_thresh: int
    binding: Binding
    neck_metadata_sha256: str | None
    calculator_source_state: str = "exact_native_producer_source_not_bundled"
    historical_or_numerical_qualification: bool = False


def prepare_influence(metadata, edges, binding, *, variant, loop_mode, neck_metadata,
                      neck_metadata_sha256):
    """Literal CNS868–927, with all target rows and complete per-level seeds.

    No count>=3 global filter. Sequential full graph keeps every edge. Sequential
    no-neck drops endpoints by regex OR explicit neck root ID. Literal parallel
    loop ignores the supplied calculator and rebuilds from full global count>0
    edges for BOTH variants. The execution branch must be explicitly declared.
    Neck metadata rows are (root_id,cell_type), preserving the original scope.
    """
    require(type(metadata) is tuple and type(edges) is tuple and type(binding) is Binding,
            "complete_immutable_inputs")
    require(binding.producer_revision == REVISION and type(binding.materialization) is int
            and binding.materialization == 888 and binding.synapse_source == "v2"
            and binding.annotation_origin == "canonical_enriched_metadata"
            and binding.join_policy == "supplied_complete_literal_left_joins", "fixed_input_binding")
    for digest in (binding.metadata_sha256, binding.edges_sha256):
        require(type(digest) is str and re.fullmatch(r"[a-f0-9]{64}", digest), "declared_input_hash")
    for row in metadata:
        require(type(row) is Metadata and type(row.root_id) is str, "metadata_domain")
        for value in (row.cell_type, row.super_class, row.cell_class, row.seed_02, row.seed_07, row.super_cluster, row.cns_network):
            require(value is None or type(value) is str, "nullable_source_annotations")
    for row in edges:
        require(type(row) is Edge and type(row.pre) is str and type(row.post) is str, "edge_domain")
        for value in (row.pre_super_class, row.post_super_class):
            require(value is None or type(value) is str, "nullable_endpoint_class")
        # Count is opaque here: native calculator's actual dtype/domain is held.
    require(variant in ("full_CNS_source", "no_neck_CNS_source"), "explicit_influence_variant")
    require(loop_mode in ("sequential_supplied_calculator", "parallel_rebuild_default_global"),
            "explicit_scientifically_distinct_loop_mode")
    if variant == "full_CNS_source":
        require(neck_metadata is None and neck_metadata_sha256 is None, "full_variant_has_no_neck_dependency")
        selected = tuple(range(len(edges)))
        levels = ("seed_02", "seed_07", "super_cluster", "cns_network")
        neck_types = set()
    else:
        require(type(neck_metadata) is tuple and type(neck_metadata_sha256) is str
                and re.fullmatch(r"[a-f0-9]{64}", neck_metadata_sha256), "complete_declared_neck_snapshot")
        require(all(type(r) is tuple and len(r) == 2 and type(r[0]) is str
                    and (r[1] is None or type(r[1]) is str) for r in neck_metadata), "neck_root_ID_cell_type_rows")
        ids = {r[0] for r in neck_metadata}; neck_types = {r[1] for r in neck_metadata}
        selected = tuple(i for i, row in enumerate(edges) if row.pre not in ids and row.post not in ids
                         and not any(v is not None and re.search("ascending|descending", v)
                                     for v in (row.pre_super_class, row.post_super_class)))
        levels = ("seed_02", "cns_network")
    if loop_mode == "parallel_rebuild_default_global":
        # Source loop112–113/189–190: default elist_df is full global count>0;
        # supplied ic_no_neck is ignored by the parallel worker constructor.
        require(all(r.count is None or type(r.count) in (int, float) for r in edges),
                "declared_portable_parallel_count_predicate_domain")
        selected = tuple(i for i, r in enumerate(edges) if r.count is not None and r.count > 0)
    seeds07 = {r.cell_type for r in metadata if r.super_class == "visual_projection"
               or r.cell_class in ("mushroom_body_output_neuron", "central_complex_output_neuron")
               or r.cell_type in ("EPG", "EL")}
    requests = []
    for level in levels:
        values = dict.fromkeys(getattr(r, level) for r in metadata if getattr(r, level) is not None)
        for seed in values:
            if level == "seed_07" and seed not in seeds07: continue
            if variant == "no_neck_CNS_source" and seed in neck_types: continue
            ids = tuple(dict.fromkeys(r.root_id for r in metadata if getattr(r, level) == seed))
            requests.append(SeedRequest(level, seed, ids))
    return InfluenceProgram(variant, loop_mode, metadata, edges, selected, tuple(r.root_id for r in metadata),
                            tuple(requests), 5, binding, neck_metadata_sha256)


def run_reference(program):
    require(type(program) is InfluenceProgram, "prepared_complete_influence_program")
    raise RuntimeError("exact_influencer_native_producer_and_runtime_not_bundled_no_solver_substitution")


def run_candidate(program, *, method_id, method):
    """Candidate receives every row and every request, not reference intermediates.

    Returned records remain candidate-declared. Completeness means every source
    seed request is represented; native target support cannot be inferred from
    the missing producer. Normalization is a separate concrete consumer API.
    """
    require(type(program) is InfluenceProgram and type(method_id) is str and method_id.strip()
            and method_id != "source_reference" and callable(method), "explicit_candidate_method")
    records = method(program)
    require(type(records) is tuple and len(records) == len(program.requests), "all_seed_requests_returned")
    expected = tuple((r.level, r.seed) for r in program.requests)
    require(all(type(r) is tuple and len(r) == 3 and type(r[2]) is tuple for r in records)
            and tuple(r[:2] for r in records) == expected, "ordered_complete_seed_request_support")
    return {"program": program, "method_id": method_id, "per_seed_records": records,
            "candidate_output_support_qualified": False, "scientific_qualification": False}
