"""Eight complete-input CNS influence tables, without a graph solve or native fit.

These are literal downstream consumers of declared complete full/no-neck output
rows. Caller declarations do not authenticate original bodies or prove native
solver output support. Fixed canonical annotations never come from a new fit.
"""
from dataclasses import dataclass, replace, field, asdict
from pathlib import Path
import hashlib
import json
import math
import re
from . import an_dn

HERE = Path(__file__).resolve().parent
CONTRACT_PIN = (3649, '9d9d9b88669e16b7f2cedc73366afc11dd11e2292634a4da34d5d64c86042870')
PANELS = ('sensory_to_cns', 'cns_to_effector_supercluster', 'cns_to_cns',
          'cns_to_cns_no_neck_drop', 'mb_cx_control_to_cns', 'supercluster_to_cns',
          'mb_cx_to_neck_supercluster', 'neck_supercluster_to_mb_cx')


def need(ok, code):
    if not ok: raise ValueError(code)


def source_contract(*, verify_primary=True):
    """Capture exact branch contract and both complete primary source files."""
    def checked(path, size, digest):
        with path.open('rb') as stream: raw = stream.read(size + 1)
        need(len(raw) == size and hashlib.sha256(raw).hexdigest() == digest,
             'captured_panel_source_changed:' + path.name)
        return raw
    value = json.loads(checked(HERE/'PANEL_CONTRACT.json', *CONTRACT_PIN))
    need(tuple(x['name'] for x in value['branches']) == PANELS, 'exact_eight_source_branches')
    if verify_primary:
        for d in value['primary_sources']:
            checked(HERE/d['path'], d['bytes'], d['sha256'])
    return value


@dataclass(frozen=True)
class RawInfluence:
    id: str
    seed: str | None
    level: str | None
    influence_original: float | int | None
    influence_norm_original: float | int | None
    influence_quantile: float | None = None
    quantile_column_present: bool = False


@dataclass(frozen=True)
class Annotation:
    id: str
    cell_type: str | None
    super_class: str | None
    cell_class: str | None
    cell_sub_class: str | None
    cluster: str | None
    super_cluster: str | None
    cns_network: str | None
    seed_07: str | None


@dataclass(frozen=True)
class FunctionRow:
    cell_type: str | None
    response: str | None


@dataclass(frozen=True)
class TableDeclarations:
    full_output_sha256: str
    no_neck_output_sha256: str
    cns_functions_sha256: str
    named_maps_sha256: str
    an_dn_metadata_sha256: str
    complete_producer_outputs_declared: bool


@dataclass(frozen=True)
class Inputs:
    full_rows: tuple[RawInfluence, ...]
    no_neck_rows: tuple[RawInfluence, ...]
    metadata: tuple[Annotation, ...]
    cns_functions: tuple[FunctionRow, ...]
    cns_cluster_names: tuple[tuple[str, str | None], ...]
    sensory_seed_map_detailed: tuple[tuple[str, str | None], ...]
    an_dn_ids: tuple[str, ...]
    cns_network_order: tuple[str, ...]
    eff_super_order: tuple[str, ...]
    super_cluster_order: tuple[str, ...]
    binding: an_dn.InputBinding
    declarations: TableDeclarations


@dataclass(frozen=True)
class PanelRow:
    id: str
    seed: str | None
    target: str | None
    level: str | None
    influence_original: float | int | None
    influence_norm_original: float | int | None
    annotation: Annotation | None
    source_indices: tuple[int, ...]
    seed_class: str | None = None
    influence_quantile: float | None = None
    quantile_column_present: bool = False
    metrics: tuple[tuple[str, float], ...] = ()


@dataclass(frozen=True)
class PanelSpec:
    name: str
    level_filter: tuple[str, ...] | None
    metric: str
    recalculate: bool
    diagonal: bool
    row_order: str | None
    col_order: str | None
    col_quantile: float | None
    reverse_display: bool
    source_lines: str

    def __getitem__(self, name): return getattr(self, name)


def _spec(value):
    return PanelSpec(**dict(value, level_filter=None if value['level_filter'] is None else tuple(value['level_filter'])))


@dataclass(frozen=True)
class PreparedPanel:
    name: str
    rows: tuple[PanelRow, ...]
    state: str
    spec: PanelSpec
    input_rows: int
    normalization_performed: bool
    origin: Inputs = field(repr=False, compare=False)


@dataclass(frozen=True)
class AxisOrder:
    """Explicit native dcast order; exact represented support, no extra zeros."""
    targets: tuple[str, ...]
    seeds: tuple[str, ...]


@dataclass(frozen=True)
class Matrix:
    targets: tuple[str, ...]
    seeds: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]
    represented: tuple[tuple[bool, ...], ...]


@dataclass(frozen=True)
class PanelResult:
    name: str
    prepared: PreparedPanel
    state: str
    full_source_cast: Matrix | None
    before_order: Matrix | None
    ordered_before_final_diagonal: Matrix | None
    returned_matrix_if_native_succeeds: Matrix | None
    display_matrix_if_native_succeeds: Matrix | None
    global_column_threshold: float | None
    column_annotation: tuple[tuple[str, str], ...]
    native_gaps: tuple[str, ...]
    scientific_qualification: bool = False


def _label(value, nullable=True):
    need((nullable and value is None) or type(value) is str, 'unchanged_string_or_explicit_missing')


def _labels(value):
    need(type(value) is tuple and all(type(x) is str for x in value), 'ordered_label_tuple')
    need(len(set(value)) == len(value), 'unique_order_labels')


def _map(value):
    need(type(value) is tuple, 'complete_named_map_tuple')
    result = {}
    for pair in value:
        need(type(pair) is tuple and len(pair) == 2, 'named_map_pair')
        _label(pair[0], False); _label(pair[1])
        result.setdefault(pair[0], pair[1])  # R named indexing takes first matching name.
    return result


def validate_inputs(inputs, max_input_rows):
    need(type(inputs) is Inputs, 'exact_complete_panel_inputs')
    an_dn.validate_binding(inputs.binding)
    d = inputs.declarations
    need(type(d) is TableDeclarations and d.complete_producer_outputs_declared is True,
         'declared_complete_full_and_no_neck_outputs_not_authenticated')
    for name in TableDeclarations.__dataclass_fields__:
        if name != 'complete_producer_outputs_declared':
            v = getattr(d, name)
            need(type(v) is str and re.fullmatch('[0-9a-f]{64}', v), 'declared_table_SHA256')
    tables = (inputs.full_rows, inputs.no_neck_rows, inputs.metadata, inputs.cns_functions,
              inputs.an_dn_ids, inputs.cns_cluster_names, inputs.sensory_seed_map_detailed)
    need(all(type(t) is tuple for t in tables), 'complete_ordered_input_tuples')
    need(type(max_input_rows) is int and max_input_rows >= 0 and
         sum(map(len, tables)) <= max_input_rows, 'whole_input_row_capacity_no_truncation')
    for rows in (inputs.full_rows, inputs.no_neck_rows):
        need(all(type(r) is RawInfluence for r in rows), 'exact_raw_influence_projection')
        need(len({r.quantile_column_present for r in rows})<=1, 'quantile_presence_is_table_level')
        for r in rows:
            need(type(r) is RawInfluence, 'exact_raw_influence_projection')
            _label(r.id, False); _label(r.seed); _label(r.level)
            for v in (r.influence_original, r.influence_norm_original):
                need(v is None or (type(v) in (int, float) and math.isfinite(v) and v >= 0),
                     'portable_nonnegative_finite_influence_domain')
            need(type(r.quantile_column_present) is bool, 'quantile_column_presence')
            need(r.influence_quantile is None or (type(r.influence_quantile) in (int,float)
                 and math.isfinite(r.influence_quantile)), 'finite_or_missing_carried_quantile')
    for m in inputs.metadata:
        need(type(m) is Annotation, 'complete_canonical_metadata_projection')
        for name in Annotation.__dataclass_fields__: _label(getattr(m, name), name != 'id')
    for f in inputs.cns_functions:
        need(type(f) is FunctionRow, 'complete_function_mapping_rows')
        _label(f.cell_type); _label(f.response)
    for value in inputs.an_dn_ids: _label(value, False)
    for value in (inputs.cns_network_order, inputs.eff_super_order, inputs.super_cluster_order): _labels(value)
    _map(inputs.cns_cluster_names); _map(inputs.sensory_seed_map_detailed)


def _annotate(rows, metadata, names):
    lookup = {}
    for m in metadata: lookup.setdefault(m.id, m)
    mapping = _map(names)
    return tuple(PanelRow(r.id, mapping.get(r.seed, r.seed), None, r.level,
                          r.influence_original, r.influence_norm_original, lookup.get(r.id), (i,),
                          influence_quantile=r.influence_quantile,
                          quantile_column_present=r.quantile_column_present) for i, r in enumerate(rows))


def _field(row, field):
    return getattr(row.annotation, field) if row.annotation is not None else None


def _normal(rows, binding, *, quantile_null):
    if not rows: return ()
    normalized = an_dn.normalize_influence(tuple(an_dn.InfluenceRow(r.id, r.seed, r.target,
        r.influence_original, r.influence_norm_original, r.level) for r in rows), binding,
        rounding='portable_binary64_signif4')
    out = []
    for n in normalized.rows:
        first = rows[n.input_indices[0]]
        out.append(replace(first, metrics=n.metrics,
            source_indices=tuple(i for j in n.input_indices for i in rows[j].source_indices),
            influence_quantile=first.influence_quantile if quantile_null else n.influence_quantile,
            quantile_column_present=first.quantile_column_present if quantile_null else True))
    return tuple(out)


def _drop(full, no_neck, binding):
    """CNS1011–1035: first retained full level vs overwritten no-neck level."""
    a = tuple(replace(r, target=_field(r, 'cns_network')) for r in full)
    b = tuple(replace(r, target=_field(r, 'cns_network'), level='cns_network') for r in no_neck)
    eligible = lambda r: r.seed is not None and r.target is not None and r.level in ('cns_network','seed_02')
    a = _normal(tuple(r for r in a if eligible(r)), binding, quantile_null=False)
    b = _normal(tuple(r for r in b if eligible(r)), binding, quantile_null=False)
    right = {(r.target, r.seed, r.level): dict(r.metrics) for r in b}
    out = []
    # dplyr right_join preserves matching left-row order; unmatched right rows
    # have missing full metrics and are then removed by the literal filter.
    for r in a:
        q = right.get((r.target, r.seed, r.level))
        if q is None: continue
        metrics = dict(r.metrics)
        metrics.update(dropped_influence_log=q['influence_log'],
                       dropped_influence_norm_log=q['influence_norm_log'],
                       drop=metrics['influence_log']-q['influence_log'],
                       drop_norm=metrics['influence_norm_log']-q['influence_norm_log'])
        out.append(replace(r, metrics=tuple(metrics.items())))
    return tuple(out)


def prepare_panels(inputs, *, max_input_rows):
    """All eight full-source row transformations, before native cast ordering."""
    contract = source_contract(); validate_inputs(inputs, max_input_rows)
    full = _annotate(inputs.full_rows, inputs.metadata, inputs.cns_cluster_names)
    no_neck = _annotate(inputs.no_neck_rows, inputs.metadata, inputs.cns_cluster_names)
    drops = _drop(full, no_neck, inputs.binding)
    vpn = {m.cell_type for m in inputs.metadata if m.super_class == 'visual_projection'}
    control = {m.cell_type for m in inputs.metadata if m.cell_class in
               ('mushroom_body_output_neuron','central_complex_output_neuron') or m.cell_type in ('EPG','EL')}
    functions = {}
    seed_class = {}
    for f in inputs.cns_functions: functions.setdefault(f.cell_type, f.response)
    for m in inputs.metadata: seed_class.setdefault(m.seed_07, m.cell_class)
    chosen_types = {m.cell_type for m in inputs.metadata if m.cell_type is not None and
        m.cell_class is not None and re.search('central_complex_input|mushroom_body|mushroom_body_dopamin', m.cell_class)}
    ad_ids = set(inputs.an_dn_ids); super_seeds = set(inputs.super_cluster_order)
    sensory = _map(inputs.sensory_seed_map_detailed)
    chosen_sensory = {v for _, v in inputs.sensory_seed_map_detailed}
    prepared = []
    for raw_spec in contract['branches']:
        spec = _spec(raw_spec)
        name = spec['name']; candidates = drops if name == PANELS[3] else full
        rows = []
        for r in candidates:
            if name == PANELS[0]:
                r = replace(r, target=_field(r,'cns_network'), seed=functions.get(r.seed) if r.seed in vpn else r.seed)
                keep = r.level in ('seed_02','seed_07') and r.seed not in (None,'0') and r.target not in (None,'0')
            elif name == PANELS[1]:
                keep = _field(r,'cluster') is not None and 'EFF' in _field(r,'cluster')
                r = replace(r, target=_field(r,'super_cluster'))
                keep = keep and r.seed not in (None,'0','') and r.target not in (None,'0','')
            elif name == PANELS[2]:
                r = replace(r, target=_field(r,'cns_network')); keep = r.seed is not None and r.target is not None
            elif name == PANELS[3]: keep = True
            elif name == PANELS[4]:
                r = replace(r, target=_field(r,'cns_network'))
                keep = r.seed in control and r.seed not in (None,'0') and r.target not in (None,'0')
            elif name == PANELS[5]:
                r = replace(r, target=_field(r,'cns_network'))
                keep = _field(r,'super_class') not in ('ascending','descending','motor','visceral_circulatory') and r.seed in super_seeds and r.seed is not None and r.target is not None
            elif name == PANELS[6]:
                cls = seed_class.get(r.seed)
                keep = r.seed is not None and r.id in ad_ids and cls is not None and re.search('central_complex|mushroom',cls) is not None
                r = replace(r, target=_field(r,'super_cluster'), seed=re.sub('_neuron|_', ' ', r.seed) if r.seed is not None else None, seed_class=cls)
                keep = keep and r.seed not in (None,'0','') and r.target not in (None,'0') and not r.seed.startswith('GFC')
            else:
                sub = _field(r,'cell_sub_class')
                keep = _field(r,'cell_type') in chosen_types and sub is not None and re.search('lateral_horn|mushroom_body_dopaminergic|mushroom_body_extrinsic',sub) is None
                r = replace(r,target=re.sub('_neuron|_',' ',sub) if sub is not None else None)
                keep = keep and r.seed not in (None,'0','') and r.target not in (None,'0')
            if keep: rows.append(r)
        input_count = len(rows)
        # Literal helper defaults: no implicit seed_12 level, quantile=NULL.
        rows = tuple(r for r in rows if r.seed is not None and r.target is not None and
                     (spec['level_filter'] is None or r.level in spec['level_filter']))
        if name == PANELS[0]: rows = tuple(replace(r, seed=sensory.get(r.seed,r.seed)) for r in rows)
        normalized_now = bool(rows) and spec['recalculate']
        if normalized_now:
            # Mapping can introduce missing labels. Native grouping permits NA;
            # this portable normalizer does not, so refuse rather than drop rows.
            need(all(r.seed is not None and r.target is not None for r in rows), 'mapped_missing_normalization_domain_held')
            rows = _normal(rows, inputs.binding, quantile_null=True)
        if name == PANELS[0]: rows = tuple(r for r in rows if r.seed in chosen_sensory)
        state = 'rows_ready' if rows else 'source_skip_empty_or_filtered_rows'
        prepared.append(PreparedPanel(name, rows, state, spec, input_count, normalized_now, inputs))
    return tuple(prepared)


def _axes(order, rows):
    need(type(order) is AxisOrder, 'explicit_native_dcast_axis_order')
    _labels(order.targets); _labels(order.seeds)
    need(set(order.targets) == {r.target for r in rows} and set(order.seeds) == {r.seed for r in rows},
         'exact_complete_represented_cast_support')


def _matrix(targets, seeds, cells, mask):
    return Matrix(tuple(targets), tuple(seeds), tuple(tuple(cells[t,s] for s in seeds) for t in targets),
                  tuple(tuple(mask[t,s] for s in seeds) for t in targets))


def _subset(matrix, targets, seeds):
    ti = {x:i for i,x in enumerate(matrix.targets)}; si = {x:i for i,x in enumerate(matrix.seeds)}
    return Matrix(tuple(targets),tuple(seeds),tuple(tuple(matrix.values[ti[t]][si[s]] for s in seeds) for t in targets),
                  tuple(tuple(matrix.represented[ti[t]][si[s]] for s in seeds) for t in targets))


def _diagonal(matrix, value):
    return replace(matrix,values=tuple(tuple(value if i==j else x for j,x in enumerate(row)) for i,row in enumerate(matrix.values)))


def _transpose(matrix):
    return Matrix(matrix.seeds,matrix.targets,tuple(zip(*matrix.values)),tuple(zip(*matrix.represented)))


def consume_panel(prepared, inputs, order, *, max_matrix_cells):
    """Pure cast/filter/order tables; native clustering/display stays explicit."""
    need(type(prepared) is PreparedPanel and prepared.name in PANELS, 'prepared_source_panel')
    need(prepared.origin is inputs, 'prepared_panel_originating_inputs_identity')
    expected=next(_spec(v) for v in source_contract(verify_primary=False)['branches'] if v['name']==prepared.name)
    need(type(prepared.spec) is PanelSpec and json.dumps(asdict(prepared.spec),sort_keys=True)==json.dumps(asdict(expected),sort_keys=True),
         'prepared_exact_immutable_source_spec')
    _axes(order, prepared.rows)
    need(type(max_matrix_cells) is int and max_matrix_cells >= 0 and
         len(order.targets)*len(order.seeds) <= max_matrix_cells, 'whole_matrix_capacity_no_truncation')
    spec = prepared.spec
    def result(state, full=None, before=None, ordered=None, final=None, display=None, threshold=None, annotation=(), gaps=()):
        return PanelResult(prepared.name,prepared,state,full,before,ordered,final,display,threshold,annotation,gaps)
    if not prepared.rows: return result(prepared.state)
    metric = spec['metric']; first = {}
    for row in prepared.rows: first.setdefault((row.target,row.seed), row)
    cells = {}; mask = {}
    for t in order.targets:
        for s in order.seeds:
            row=first.get((t,s)); value=dict(row.metrics).get(metric) if row is not None else None
            cells[t,s] = float(value) if value is not None and math.isfinite(value) else 0.0
            mask[t,s] = row is not None
    full = _matrix(order.targets,order.seeds,cells,mask)
    if min(len(order.targets),len(order.seeds)) < 2:
        return result('source_skip_matrix_smaller_than2x2',full=full)
    before = full
    if not spec['diagonal']: before = _diagonal(before,min(x for row in before.values for x in row))
    threshold = None
    if spec['col_quantile'] is not None:
        need(spec['col_quantile']==.5,'only_released_global_median_threshold')
        values=sorted(x for row in before.values for x in row); n=len(values)
        threshold=values[n//2] if n%2 else (values[n//2-1]+values[n//2])/2
        keep=tuple(s for j,s in enumerate(before.seeds) if any(row[j]>threshold for row in before.values))
        before=_subset(before,before.targets,keep)
        if min(len(before.targets),len(before.seeds))<2:
            return result('native_R_dimension_drop_after_threshold_boundary',full=full,before=before,threshold=threshold,
                          gaps=('R matrix subset drops a dimension; subsequent native behavior is not replaced.',))
    annotation=()
    if prepared.name==PANELS[6]:
        seen={}
        for row in prepared.rows: seen.setdefault(row.seed,row.seed_class if row.seed_class is not None else 'other')
        annotation=tuple((s,v) for s,v in seen.items() if s in before.seeds)
    ordered=before; gaps=[]
    for axis,field in (('rows','row_order'),('columns','col_order')):
        selection=spec[field]
        if selection is None:
            gaps.append('native_'+axis+'_euclidean_ward.D2_clustering_unexecuted');continue
        values=getattr(inputs,selection)
        if axis=='rows': ordered=_subset(ordered,tuple(x for x in values if x in ordered.targets),ordered.seeds)
        else: ordered=_subset(ordered,ordered.targets,tuple(x for x in values if x in ordered.seeds))
        if min(len(ordered.targets),len(ordered.seeds))<2:
            return result('native_R_dimension_drop_after_explicit_order_boundary',full,before,ordered,
                          threshold=threshold,annotation=annotation,gaps=tuple(gaps)+('R subset dimension loss retained.',))
    final=ordered if spec['diagonal'] else _diagonal(ordered,None)
    display=_transpose(final) if spec['reverse_display'] else final
    return result('pure_panel_tables_ready_native_execution_unqualified',full,before,ordered,final,display,
                  threshold,annotation,tuple(gaps)+('Native heatmap/color/statistical execution unselected.',))


def run_all_panels(inputs, *, cast_orders, max_input_rows, max_matrix_cells, max_total_matrix_cells):
    """Prepare/consume all eight branches with no omitted support or sampling.

    Capacities refuse whole operations; they never select a smaller graph. Six
    logical matrix stages per full rectangle conservatively bound stored cells.
    Python object/RSS and future solver/native work require separate enclosure.
    """
    need(type(max_matrix_cells) is int and max_matrix_cells>=0 and type(max_total_matrix_cells) is int and max_total_matrix_cells>=0,
         'typed_complete_matrix_capacity')
    prepared=prepare_panels(inputs,max_input_rows=max_input_rows)
    need(type(cast_orders) is tuple and tuple(name for name,_ in cast_orders)==PANELS, 'all_eight_cast_orders_required')
    need(type(max_matrix_cells) is int and max_matrix_cells>=0 and type(max_total_matrix_cells) is int and max_total_matrix_cells>=0,
         'typed_complete_matrix_capacity')
    total=0
    for panel,(_,order) in zip(prepared,cast_orders):
        _axes(order,panel.rows);n=len(order.targets)*len(order.seeds)
        need(n<=max_matrix_cells,'whole_matrix_capacity_no_truncation');total+=6*n
    need(total<=max_total_matrix_cells,'all_eight_matrix_stage_capacity_no_truncation')
    return {'panels':tuple(consume_panel(panel,inputs,order,max_matrix_cells=max_matrix_cells)
                          for panel,(_,order) in zip(prepared,cast_orders)),
            'binding':inputs.binding,'declared_tables':inputs.declarations,
            'full_input_rows':len(inputs.full_rows),'no_neck_input_rows':len(inputs.no_neck_rows),
            'logical_matrix_stage_cell_bound':total,'all_eight_pure_branches_accounted':True,
            'native_producer_support_authenticated':False,'whole_paper_execution_complete':False,
            'scientific_qualification':False}
