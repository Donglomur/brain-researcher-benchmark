"""Closed, complete-record BANC graph preparation; native execution is external.

Declared input hashes identify caller-supplied records: they are not an assertion
that authentic data were acquired, authenticated or scientifically evaluated.
Only run_centrality executes an algorithm, the reviewed portable Brandes kernel.
The native request contains actual ordered graph contributions and original input
records; it never substitutes a portable solve for the captured native producer.
"""
from dataclasses import dataclass
import math
import re
from . import centrality_portable as _centrality

PY_REVISION = '6b70294094ebcd97166ab646c5322eed957f8936'
R_REVISION = '2519c57b8389481e72bc52e93a9e45e770cd674a'
BANC_REVISION = '2e78ce38e946ab80e120a42f504a019b3a567fef'
PY_SOURCE = ('native-source/DrugowitschLab_ConnectomeInfluenceCalculator/InfluenceCalculator/InfluenceCalculator.py', 14594, 'cdfefac56797355d2ff8aeec8d587ee5841d87904a12321618c613bd9697121d')
R_SOURCE = ('native-source/natverse_influencer/R/influence-calculator-r.R', 19472, '8c8e468b3576110c11d24221e968cc586f6aa0bb98e583f420ad6419f9932583')
WRAPPER_SOURCE = ('native-source/natverse_influencer/R/python-wrapper.R', 11207, '00e38f9f1a328cdf9bd1907aa17ac5b6cbf0a7f7cfc3416cfc0ce06c6be2cda0')
OPERATOR_BRANCHES = (
    'paper_unsigned_equation', 'captured_Python_unsigned_literal',
    'captured_Python_signed_literal', 'captured_R_unsigned_literal',
    'captured_R_signed_labelled_literal', 'R_to_Python_literal_wrapper',
    'explicit_paper_equation_correction_future',
)
GRAPH_VARIANTS = (
    'full_CNS_source/sequential_supplied_calculator',
    'no_neck_CNS_source/sequential_supplied_calculator',
    'full_CNS_source/parallel_rebuild_default_global',
    'no_neck_CNS_source/parallel_rebuild_default_global',
)

class GraphRefusal(ValueError):
    """Input or resource domain refused before any completed result exists."""


def _need(ok, reason):
    if not ok:
        raise GraphRefusal(reason)


def _digest(value):
    return type(value) is str and re.fullmatch('[a-f0-9]{64}', value) is not None


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True, slots=True)
class Metadata:
    root_id: str
    super_class: str | None
    proofread: str | None
    roughly_proofread: str | None
    cell_type: str | None
    top_nt: str | None = None
    native_id: str | None = None


@dataclass(frozen=True, slots=True)
class Edge:
    pre: str
    post: str
    count: int | None
    norm: float | int | None
    pre_super_class: str | None = None
    post_super_class: str | None = None
    post_count: float | int | None = None


@dataclass(frozen=True, slots=True)
class RawTable:
    """Full admitted table, including extra columns, in the declared row order.

    This is a caller-supplied immutable decoded table, not a storage reader. The
    digest binds the original content by declaration; source byte authentication
    and native dtype/collation evidence are separate owner gates.
    """
    columns: tuple[str, ...]
    rows: tuple[tuple, ...]
    declared_content_sha256: str


@dataclass(frozen=True, slots=True)
class Binding:
    metadata_sha256: str
    edges_sha256: str
    annotation_profile: str = 'canonical_enriched_metadata'
    materialization: int = 888
    synapse_source: str = 'v2'
    id_cast_profile: str = 'already_plain_string_ids_no_missing_scalars'
    producer_revision: str = BANC_REVISION


@dataclass(frozen=True, slots=True)
class Limits:
    max_metadata_rows: int
    max_edge_rows: int
    max_nodes: int
    max_text_bytes: int
    max_source_sweeps: int
    max_work_items: int
    max_raw_cells: int


@dataclass(frozen=True, slots=True)
class NativeParameters:
    # Count threshold is explicit: CNS asks for 5; native R's default is 3.
    count_thresh: int
    syn_weight_measure: str = 'count'
    inhibitory_nts: tuple[str, ...] | None = None
    excluded_nts: tuple[str, ...] = ()
    lambda_max: float = 0.99
    const: float = 24.0
    wrapper_signed: bool = False
    r_collation_profile: str = 'unselected'
    r_neg_neurotransmitters: tuple[str, ...] = ('glutamate', 'gaba', 'serotonin', 'octopamine')


@dataclass(frozen=True, slots=True)
class MatrixContribution:
    input_edge_index: int
    post_index: int
    pre_index: int
    weight: float | int
    count_after_native_sign_rule: float | int


@dataclass(frozen=True, slots=True)
class NativeRequest:
    graph_variant: str
    operator_branch: str
    complete_metadata: tuple[Metadata, ...]
    complete_edges: tuple[Edge, ...]
    raw_metadata: RawTable
    raw_edges: RawTable | None
    binding: Binding
    parameters: NativeParameters
    selected_edge_indices: tuple[int, ...]
    threshold_edge_indices: tuple[int, ...]
    matrix_edge_indices: tuple[int, ...]
    ordered_node_ids: tuple[str, ...]
    contributions: tuple[MatrixContribution, ...]
    source_ids: tuple[str, ...]
    target_ids: tuple[str, ...]
    silenced_ids: tuple[str, ...]
    effective_source_ids: tuple[str, ...]
    effective_silenced_ids: tuple[str, ...]
    missing_source_ids: tuple[str, ...]
    missing_target_ids: tuple[str, ...]
    constructor: tuple[tuple[str, object], ...]
    source_requirements: tuple[tuple, ...]
    node_order_rule: str
    scaling_rule: str
    response_rule: str
    output_support_rule: str
    holds: tuple[str, ...]
    expected_native_failure: str | None
    status: str
    neck_metadata_sha256: str | None
    native_executed: bool = False
    historical_producer_identified: bool = False
    scientific_qualification: bool = False

    @property
    def constructor_kwargs(self):
        """Real pinned constructor keywords; owner supplies filename or tables."""
        return tuple((key, value) for key, value in self.constructor
                     if key not in ('entrypoint', 'filename_binding'))

    @property
    def constructor_entrypoint(self):
        return dict(self.constructor).get('entrypoint')


def _validate_limits(limits):
    _need(type(limits) is Limits, 'explicit_limits_required')
    for field in Limits.__dataclass_fields__:
        _need(type(getattr(limits, field)) is int and getattr(limits, field) >= 0,
              'nonnegative_integer_resource_limit:' + field)


def _validate_inputs(metadata, edges, binding, limits):
    _validate_limits(limits)
    _need(type(metadata) is tuple and type(edges) is tuple, 'complete_immutable_input_tuples')
    _need(len(metadata) <= limits.max_metadata_rows, 'metadata_row_budget')
    _need(len(edges) <= limits.max_edge_rows, 'edge_row_budget')
    _need(type(binding) is Binding and _digest(binding.metadata_sha256) and _digest(binding.edges_sha256),
          'declared_full_input_bindings')
    _need(type(binding.materialization) is int and binding.materialization == 888
          and binding.synapse_source == 'v2' and binding.producer_revision == BANC_REVISION
          and binding.annotation_profile == 'canonical_enriched_metadata'
          and binding.id_cast_profile == 'already_plain_string_ids_no_missing_scalars',
          'explicit_source_input_profile')
    text_bytes = 0
    def text_value(value, nullable=False):
        nonlocal text_bytes
        _need(type(value) is str or (nullable and value is None), 'plain_string_or_explicit_missing')
        if value is not None:
            text_bytes += len(value.encode('utf-8'))
            _need(text_bytes <= limits.max_text_bytes, 'input_text_budget')
    for row in metadata:
        _need(type(row) is Metadata, 'compact_metadata_row_type')
        text_value(row.root_id)
        for field in ('super_class', 'proofread', 'roughly_proofread', 'cell_type', 'top_nt', 'native_id'):
            text_value(getattr(row, field), True)
    # Count and norm are admitted ordinary values here; literal centrality ignores
    # count, and native-only domain checks happen after graph selection.
    for row in edges:
        _need(type(row) is Edge, 'edge_row_type')
        text_value(row.pre); text_value(row.post)
        text_value(row.pre_super_class, True); text_value(row.post_super_class, True)
        _need(row.count is None or (type(row.count) is int and row.count >= 0), 'ordinary_nonnegative_integer_count')
        for val in (row.norm, row.post_count):
            _need(val is None or (_number(val) and val >= 0), 'finite_nonnegative_edge_numeric')
    return text_bytes


def _validate_raw(table, digest, compact, kind, limits, already_text_bytes):
    _need(type(table) is RawTable and table.declared_content_sha256 == digest, 'raw_' + kind + '_binding')
    _need(type(table.columns) is tuple and type(table.rows) is tuple and len(table.rows) == len(compact),
          'complete_raw_' + kind + '_shape')
    _need(all(type(c) is str for c in table.columns) and len(table.columns) == len(set(table.columns)),
          'unique_string_raw_columns')
    _need(len(table.columns) * len(table.rows) <= limits.max_raw_cells, 'raw_cell_budget')
    required = ('root_id',) if kind == 'metadata' else ('pre', 'post', 'count', 'norm')
    _need(all(c in table.columns for c in required), 'native_required_' + kind + '_columns')
    columns = {key: i for i, key in enumerate(table.columns)}
    text_bytes = already_text_bytes + sum(len(c.encode('utf-8')) for c in table.columns)
    _need(text_bytes <= limits.max_text_bytes, 'raw_text_budget')
    compact_fields = ({'root_id':'root_id', 'super_class':'super_class', 'proofread':'proofread',
                       'roughly_proofread':'roughly_proofread', 'cell_type':'cell_type',
                       'top_nt':'top_nt', 'id':'native_id'} if kind == 'metadata'
                      else {'pre':'pre', 'post':'post', 'count':'count', 'norm':'norm',
                            'pre_super_class':'pre_super_class', 'post_super_class':'post_super_class',
                            'post_count':'post_count'})
    for raw, row in zip(table.rows, compact):
        _need(type(raw) is tuple and len(raw) == len(table.columns), 'immutable_raw_row_width')
        for value in raw:
            _need(value is None or type(value) in (str, bool, int) or
                  (type(value) is float and math.isfinite(value)), 'ordinary_raw_scalar_domain')
            if type(value) is str:
                text_bytes += len(value.encode('utf-8'))
                _need(text_bytes <= limits.max_text_bytes, 'raw_text_budget')
        for column, field in compact_fields.items():
            if column in columns:
                _need(type(raw[columns[column]]) is type(getattr(row, field)) and raw[columns[column]] == getattr(row, field),
                      'compact_raw_' + column + '_mismatch')
    return text_bytes


def run_centrality(metadata, edges, binding, *, branch, limits):
    """Run all sources, both endpoint-excluded directed modes, or refuse.

    The original byte-identical reviewed kernel retains parallel edge rows and
    self loops, omits metadata-only isolates and resolves duplicate annotation
    rows using the source's first eligible record. No candidate callback runs.
    """
    _validate_inputs(metadata, edges, binding, limits)
    _need(branch in _centrality.BRANCHES, 'explicit_centrality_branch')
    nodes = set()
    for row in edges:
        nodes.add(row.pre); nodes.add(row.post)
        _need(len(nodes) <= limits.max_nodes, 'all_input_endpoint_node_budget')
    source_binding = _centrality.InputBinding(
        binding.metadata_sha256, binding.edges_sha256, binding.id_cast_profile)
    inputs = _centrality.CompleteInputs(
        tuple(_centrality.MetadataRow(m.root_id, m.super_class, m.proofread,
                                     m.roughly_proofread, m.cell_type) for m in metadata),
        tuple(_centrality.EdgeRow(e.pre, e.post, e.count) for e in edges), source_binding)
    return _centrality.run_reference(inputs, branch=branch,
        budget=_centrality.WorkBudget(max_source_sweeps=limits.max_source_sweeps,
                                        max_work_items=limits.max_work_items))


def scaling_rule(operator_branch):
    _need(operator_branch in OPERATOR_BRANCHES, 'explicit_operator_branch')
    if operator_branch.startswith('captured_R_'):
        return 'largest_real_RSPECTRA_LR;scale_0.99/lambda_only_if_lambda>0.99;then_minus_identity'
    if operator_branch.startswith('captured_Python_') or operator_branch == 'R_to_Python_literal_wrapper':
        return 'largest_real_SLEPc;require_converged_eigenpair;scale_lambda_max/lambda_if_lambda>0;then_minus_identity'
    return 'paper_target_largest_real_0.99;zero_nonpositive_and_solver_contract_unresolved'


def response_rule(operator_branch, *, wrapper_signed=False):
    _need(operator_branch in OPERATOR_BRANCHES, 'explicit_operator_branch')
    if operator_branch == 'captured_Python_signed_literal' or (operator_branch == 'R_to_Python_literal_wrapper' and wrapper_signed):
        return 'real_part_preserving_sign'
    if operator_branch.startswith('captured_') or operator_branch == 'R_to_Python_literal_wrapper':
        return 'absolute_real_part'
    return 'paper_response_contract_requires_adjudication'


def _validate_ids(ids, label, limits):
    _need(type(ids) is tuple and all(type(s) is str for s in ids), 'explicit_' + label + '_ids')
    _need(len(ids) <= limits.max_metadata_rows + limits.max_edge_rows * 2, label + '_id_budget')
    _need(sum(len(s.encode('utf-8')) for s in ids) <= limits.max_text_bytes, label + '_id_text_budget')


def prepare_native_request(metadata, edges, binding, *, graph_variant, operator_branch,
                           parameters, raw_metadata, source_ids, target_ids, limits,
                           raw_edges=None, silenced_ids=(), neck_metadata=None,
                           neck_metadata_sha256=None):
    """Prepare complete source-bound native input and a closed unexecuted request.

    Graph selection happens before the native count threshold. Matrix entries
    preserve duplicate edge contributions and their source order; they are not
    a portable aggregate claiming PETSc/Matrix summation parity. A request never
    claims historical/native/scientific qualification. Raw tables remain intact.
    """
    text_bytes = _validate_inputs(metadata, edges, binding, limits)
    _need(graph_variant in GRAPH_VARIANTS, 'explicit_graph_variant')
    _need(operator_branch in OPERATOR_BRANCHES, 'explicit_operator_branch')
    _need(type(parameters) is NativeParameters, 'closed_native_parameters')
    p = parameters
    _need(type(p.count_thresh) is int and p.count_thresh >= 0, 'native_count_threshold')
    _need(p.syn_weight_measure in ('count', 'norm'), 'native_weight_column')
    _need(_number(p.lambda_max) and 0 < p.lambda_max < 1 and _number(p.const), 'native_finite_constants')
    _need(type(p.wrapper_signed) is bool, 'wrapper_signed_boolean')
    _need(p.r_collation_profile in ('unselected', 'C_plain_string_ids'), 'R_collation_profile')
    for nts in (p.inhibitory_nts, p.excluded_nts, p.r_neg_neurotransmitters):
        _need(nts is None or (type(nts) is tuple and all(type(x) is str for x in nts)), 'immutable_transmitter_sets')
    _need(p.excluded_nts is not None and p.r_neg_neurotransmitters is not None, 'required_transmitter_tuples')
    text_bytes = _validate_raw(raw_metadata, binding.metadata_sha256, metadata, 'metadata', limits, text_bytes)
    if raw_edges is not None:
        text_bytes = _validate_raw(raw_edges, binding.edges_sha256, edges, 'edges', limits, text_bytes)
    for ids, label in ((source_ids, 'source'), (target_ids, 'target'), (silenced_ids, 'silenced')):
        _validate_ids(ids, label, limits)
    variant, loop = graph_variant.split('/')
    if variant == 'full_CNS_source':
        _need(neck_metadata is None and neck_metadata_sha256 is None, 'full_graph_has_no_neck_dependency')
        selected = tuple(range(len(edges)))
    else:
        _need(type(neck_metadata) is tuple and _digest(neck_metadata_sha256), 'explicit_full_neck_snapshot')
        _need(len(neck_metadata) <= limits.max_metadata_rows, 'neck_row_budget')
        _need(all(type(row) is tuple and len(row) == 2 and type(row[0]) is str
                  and (row[1] is None or type(row[1]) is str) for row in neck_metadata), 'neck_root_id_cell_type_domain')
        neck_ids = {row[0] for row in neck_metadata}
        selected = tuple(i for i, row in enumerate(edges) if row.pre not in neck_ids and row.post not in neck_ids
                         and not any(v is not None and re.search('ascending|descending', v)
                                     for v in (row.pre_super_class, row.post_super_class)))
    if loop == 'parallel_rebuild_default_global':
        # Literal source reconstructs global count>0 for both graph variants.
        selected = tuple(i for i, row in enumerate(edges) if row.count is not None and row.count > 0)
    _need(all(edges[i].count is not None for i in selected),
          'native_selected_missing_counts_unsupported_no_NA_row_substitution')
    threshold = tuple(i for i in selected if edges[i].count is not None and edges[i].count >= p.count_thresh)
    for i in threshold:
        _need(edges[i].norm is not None, 'native_selected_norm_required')
    seen = {}
    for field in ('post', 'pre'):
        for i in threshold:
            seen.setdefault(getattr(edges[i], field), None)
            _need(len(seen) <= limits.max_nodes, 'native_node_budget')
    is_r = operator_branch.startswith('captured_R_')
    is_py = operator_branch.startswith('captured_Python_')
    is_wrapper = operator_branch == 'R_to_Python_literal_wrapper'
    signed = operator_branch in ('captured_Python_signed_literal', 'captured_R_signed_labelled_literal') or (is_wrapper and p.wrapper_signed)
    holds = ['historical_operator_and_native_dtype_parity_unresolved', 'native_runtime_not_executed']
    failure = None
    if any(edges[i].norm == 0 for i in threshold):
        holds.append('selected_zero_norm_post_count_domain_unresolved')
    if not raw_edges:
        holds.append('full_edge_table_not_supplied_compact_required_columns_only')
    if is_r:
        _need(p.syn_weight_measure == 'norm', 'literal_R_constructor_uses_norm_no_public_weight_parameter')
        _need(p.inhibitory_nts is None and not p.excluded_nts and p.lambda_max == 0.99,
              'R_constructor_has_no_Python_only_parameter')
        node_ids = tuple(sorted(seen))
        order_rule = 'native_R_sort_unique_post_then_pre;preview_C_plain_string_order_only'
        if p.r_collation_profile != 'C_plain_string_ids':
            holds.append('R_character_collation_unselected_preview_order_not_native_evidence')
        elif any(any(ord(ch) > 127 for ch in node) for node in node_ids):
            holds.append('R_nonASCII_order_not_qualified_under_C_preview')
        sources = (R_SOURCE,)
        constructor = (('entrypoint', 'InfluenceCalculatorR$new'), ('sqlite', False), ('signed', signed),
                       ('count_thresh', p.count_thresh), ('const', p.const),
                       ('neg_neurotransmitters', p.r_neg_neurotransmitters))
    elif is_py or is_wrapper:
        node_ids = tuple(seen)
        order_rule = 'native_Python_unique_all_post_then_all_pre_first_appearance_before_exclusions'
        sources = (PY_SOURCE, WRAPPER_SOURCE) if is_wrapper else (PY_SOURCE,)
        if is_wrapper:
            _need(p.syn_weight_measure == 'count' and p.inhibitory_nts is None and not p.excluded_nts
                  and p.lambda_max == 0.99, 'literal_wrapper_cannot_forward_Python_optional_parameters')
            constructor = (('entrypoint', 'influencer::influence_calculator_py'), ('filename_binding', 'owner_materialized_selected_rows_sqlite'),
                           ('signed', signed), ('count_thresh', p.count_thresh))
        else:
            constructor = (('entrypoint', 'InfluenceCalculator.InfluenceCalculator'), ('filename_binding', 'owner_materialized_selected_rows_sqlite'),
                           ('signed', signed), ('count_thresh', p.count_thresh), ('syn_weight_measure', p.syn_weight_measure),
                           ('inhibitory_nts', p.inhibitory_nts), ('excluded_nts', p.excluded_nts), ('lambda_max', p.lambda_max))
        if signed and p.inhibitory_nts is None:
            failure = 'Python_ValueError_signed_requires_inhibitory_nts_before_SQL_read'
        elif (signed or p.excluded_nts) and 'top_nt' not in raw_metadata.columns:
            failure = 'Python_ValueError_top_nt_required_when_sign_or_exclusion_is_used'
    else:
        node_ids = tuple(seen)
        order_rule = 'unselected_paper_operator_preview_not_an_authorized_native_order'
        sources = ()
        constructor = ()
        holds.append('specification_only_no_selected_native_constructor')
        if operator_branch == 'explicit_paper_equation_correction_future':
            holds.append('future_correction_not_selected')
    if is_r and signed:
        # Missing id is NOT automatically asserted to cause a native error.
        # R's absent column lookup and resulting mask require native evidence.
        if 'id' not in raw_metadata.columns or 'top_nt' not in raw_metadata.columns:
            holds.append('R_signed_meta_id_top_nt_mask_native_outcome_unresolved')
        holds.append('R_signed_label_edits_count_while_default_matrix_consumes_norm')
    index = {node: j for j, node in enumerate(node_ids)}
    excluded = {m.root_id for m in metadata if m.top_nt in p.excluded_nts} if (is_py or is_wrapper) else set()
    py_inhibitory = {m.root_id for m in metadata if p.inhibitory_nts is not None and m.top_nt in p.inhibitory_nts}
    r_inhibitory = ({m.native_id for m in metadata if m.top_nt in p.r_neg_neurotransmitters and m.native_id is not None}
                    if 'id' in raw_metadata.columns and 'top_nt' in raw_metadata.columns else set())
    matrix_indices = tuple(i for i in threshold if edges[i].pre not in excluded)
    entries = []
    if (is_py or is_r or is_wrapper) and not failure:
        for i in matrix_indices:
            row = edges[i]
            value = getattr(row, 'norm' if is_r else p.syn_weight_measure)
            signed_count = row.count
            if signed and is_r and row.pre in r_inhibitory:
                signed_count = -signed_count
            elif signed and not is_r and row.pre in py_inhibitory:
                value = -value
                if p.syn_weight_measure == 'count': signed_count = -signed_count
            entries.append(MatrixContribution(i, index[row.post], index[row.pre], value, signed_count))
    node_set = set(node_ids)
    source_set, silenced_set = set(source_ids), set(silenced_ids)
    effective_sources = tuple(node for node in node_ids if node in source_set)
    effective_silenced = tuple(node for node in node_ids if node in silenced_set and node not in source_set)
    status = 'expected_native_failure_unexecuted' if failure else ('specification_held_unexecuted' if not (is_r or is_py or is_wrapper) else 'native_request_prepared_unexecuted')
    return NativeRequest(graph_variant, operator_branch, metadata, edges, raw_metadata, raw_edges, binding, p,
        selected, threshold, matrix_indices, node_ids, tuple(entries), source_ids, target_ids, silenced_ids,
        effective_sources, effective_silenced, tuple(x for x in source_ids if x not in node_set),
        tuple(x for x in target_ids if x not in node_set), constructor, sources, order_rule,
        scaling_rule(operator_branch), response_rule(operator_branch, wrapper_signed=p.wrapper_signed),
        'native_returns_every_matrix_node_in_native_order;requested_target_ids_preserved_separately_no_silent_filter_or_join',
        tuple(holds), failure, status, neck_metadata_sha256)


def normalization_factor(operator_branch, largest_real, *, lambda_max=0.99):
    """Literal scalar rule for an explicitly supplied eigenvalue, NOT a solver.

    The caller must supply native eigenpair convergence evidence separately.
    This helper neither obtains that eigenvalue nor certifies matrix stability.
    """
    _need(operator_branch in OPERATOR_BRANCHES and _number(largest_real), 'finite_declared_largest_real')
    _need(_number(lambda_max) and 0 < lambda_max < 1, 'finite_target_eigenvalue')
    if operator_branch.startswith('captured_R_'):
        _need(lambda_max == 0.99, 'literal_R_fixed_target_0.99')
        return 0.99 / largest_real if largest_real > 0.99 else 1.0
    if operator_branch.startswith('captured_Python_') or operator_branch == 'R_to_Python_literal_wrapper':
        if operator_branch == 'R_to_Python_literal_wrapper':
            _need(lambda_max == 0.99, 'literal_wrapper_does_not_forward_lambda_max')
        return lambda_max / largest_real if largest_real > 0 else 1.0
    raise GraphRefusal('paper_equation_zero_nonpositive_and_native_method_not_selected')


def transform_response(operator_branch, values, *, wrapper_signed=False):
    """Captured real-part/magnitude transform on an ordinary complete tuple.

    Does not imply any values came from a native solve; does not apply the
    separate log-plus-constant display column.
    """
    rule = response_rule(operator_branch, wrapper_signed=wrapper_signed)
    _need(rule != 'paper_response_contract_requires_adjudication', 'paper_response_unresolved')
    _need(type(values) is tuple, 'immutable_response_tuple')
    _need(all(type(v) in (int, float, complex) and math.isfinite(v.real)
              and math.isfinite(v.imag) for v in values), 'finite_ordinary_response_values')
    return tuple(v.real if rule == 'real_part_preserving_sign' else abs(v.real) for v in values)
