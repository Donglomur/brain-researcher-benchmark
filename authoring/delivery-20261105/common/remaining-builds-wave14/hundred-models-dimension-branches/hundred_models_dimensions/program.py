"""Bound branch-level source interface; no empirical provenance is inferred."""
from dataclasses import dataclass, asdict
from hashlib import sha256
from collections import Counter

from . import _catalog_gate as catalog
from . import _depth as depth
from . import consumers
from ._scope import ROIS, SUBJECTS, METHOD_FOLDERS


@dataclass(frozen=True)
class Limits:
    max_metadata_bytes: int = 4_000_000
    max_input_rows: int = 2_000_000
    max_output_rows: int = 2_000_000
    max_aggregate_cells: int = 200_000_000
    depth: "depth.Limits" = depth.Limits()


@dataclass(frozen=True)
class BoundBranch:
    branch: str
    protocol_raw: bytes
    inventory_raw: bytes
    graph_raw: bytes
    graph_pin: tuple
    run_raw: bytes
    run_pin: tuple
    limits: Limits


@dataclass(frozen=True)
class BranchComplete:
    branch: str
    models: tuple
    folders: tuple
    rois: tuple
    n_stimuli: int
    repetitions: int
    input_rows: int
    output_rows: int
    aggregate_cells: int
    catalog_global99_complete: bool
    input_test102_catalog_prerequisite: bool
    run_binding_sha256: str
    emitted_roi_sha256: str
    whole_branch_complete: bool = True
    historical_execution_proven: bool = False
    scientific_qualified: bool = False
    native_numeric_parity_qualified: bool = False
    renderer_qualified: bool = False


def _pin_tuple(value):
    catalog.descriptor(value)
    return value['bytes'],value['sha256']


def _descriptor(value):
    catalog.need(type(value) is tuple and len(value)==2,'immutable external admission pin')
    result={'bytes':value[0],'sha256':value[1]};catalog.descriptor(result)
    return result


def _limits(value):
    catalog.need(type(value) is Limits,'branch workload limits')
    for key in ('max_metadata_bytes','max_input_rows','max_output_rows','max_aggregate_cells'):
        catalog.need(type(getattr(value,key)) is int and getattr(value,key)>0,'positive workload limits')
    depth._check_limits(value.depth)


def _run_contract(branch, protocol, layers, producer_layers, raw):
    """Declarations require separate caller admission; hashes are not execution."""
    run=catalog.strict(raw)
    catalog.need(type(run) is dict and set(run)=={'schema','branch','protocol','evidence_origin','split','brain','base_folder',
                          'comparison_folders','conditions'},'exact branch run-binding fields')
    catalog.need(run['schema']=='hundred_models_dimension_run_v1' and run['branch']==branch
                 and run['protocol']==catalog.PROTOCOL_PIN,'branch and protocol identity')
    catalog.need(run['evidence_origin'] in ('operator_admitted_run_metadata','invented_control'),
                 'declared admission origin, no historical proof inferred')
    split=run['split'];n,repetitions=(102,10) if branch=='figure16' else (1000,3)
    selection='test' if branch=='figure16' else 'train'
    catalog.need(type(split) is dict and set(split)=={'selection','ordered_ids','n_stimuli','repetitions','order_admission'},'split fields')
    ids=split['ordered_ids']
    catalog.need(split['selection']==selection and type(split['n_stimuli']) is int and split['n_stimuli']==n
                 and type(split['repetitions']) is int and split['repetitions']==repetitions
                 and type(ids) is list and len(ids)==n
                 and all(type(x) is str and 0<len(x)<=256 for x in ids) and len(set(ids))==n,'complete explicit split order/support')
    catalog.descriptor(split['order_admission'])
    if branch=='figure16':catalog.need(ids==protocol['stimuli'],'exact published test102 IDs')
    # Train IDs are admitted input, never inferred from 1000-row shape.
    order=catalog.pin(catalog.encoded(ids))
    brain=run['brain']
    catalog.need(type(brain) is dict and set(brain)=={'subjects','rois','n_stimuli','repetitions','average_external',
                             'operation_contract','shape_manifest','noise_ceiling_receipt'},'brain support fields')
    catalog.need(brain['subjects']==list(SUBJECTS) and brain['rois']==list(ROIS)
                 and type(brain['n_stimuli']) is int and brain['n_stimuli']==n
                 and type(brain['repetitions']) is int and brain['repetitions']==repetitions
                 and brain['average_external'] is False,'all ten subjects/all17 ROI/repetition support')
    for key in ('operation_contract','shape_manifest','noise_ceiling_receipt'):catalog.descriptor(brain[key])
    catalog.need(type(run['comparison_folders']) is list,'explicit comparison folder list')
    folders=tuple(run['comparison_folders'])+(run['base_folder'],)
    consumers.validate_folders(branch,folders)
    expected=tuple((model,folder,names) for model,names in layers for folder in folders)
    records=run['conditions']
    catalog.need(type(records) is list and len(records)==len(expected),'every branch model/condition witness')
    for record,(model,folder,names) in zip(records,expected):
        catalog.need(type(record) is dict and set(record)=={'model','folder','stimulus_order','layer_order','producer_layer_order',
            'n_stimuli','split_emission_receipt','operation_contract','score_provenance_receipt',
            'operation_profile','reduction'},'condition witness fields')
        catalog.need(record['model']==model and record['folder']==folder and record['stimulus_order']==order
                     and record['layer_order']==catalog.pin(catalog.encoded(names))
                     and record['producer_layer_order']==catalog.pin(catalog.encoded(producer_layers[model]))
                     and type(record['n_stimuli']) is int and record['n_stimuli']==n,
                     'full branch stimulus/emitted-layer support; test graph never proves train emission')
        for key in ('split_emission_receipt','operation_contract','score_provenance_receipt'):
            catalog.descriptor(record[key])
        method=dict(METHOD_FOLDERS)[folder] if branch=='figure16' else 'pca'
        spec=record['reduction']
        catalog.need(type(spec) is dict and set(spec)=={'method','n_samples_estim','n_components',
            'max_dim_allowed','standardize_on_dim','distance','sklearn_kwargs_policy'},'explicit reduction operation fields')
        catalog.need(spec['method']==method and spec['standardize_on_dim'] is None
                     and spec['distance']=='pearson'
                     and spec['sklearn_kwargs_policy']=='constructor-only-n_components;other-keywords-omitted',
                     'source transform/distance and omitted native kwargs preserved')
        if method=='pca':
            catalog.need(record['operation_profile']=='literal_held_script_pca100_fit102'
                         and type(spec['n_samples_estim']) is int and spec['n_samples_estim']==102
                         and type(spec['n_components']) is int and spec['n_components']==100
                         and spec['max_dim_allowed'] is None,
                         'literal held PCA remains fit102/components100 even on train1000')
        elif method=='srp':
            catalog.need(record['operation_profile']=='explicit_admitted_srp_run_metadata'
                         and type(spec['n_samples_estim']) is int and 1<=spec['n_samples_estim']<=n
                         and (spec['n_components'] is None or type(spec['n_components']) is int and spec['n_components']>=0)
                         and (spec['max_dim_allowed'] is None or type(spec['max_dim_allowed']) is int and spec['max_dim_allowed']>=0),
                         'SRP historical settings unknown: require explicit admitted spec, never choose defaults')
        else:
            catalog.need(record['operation_profile']=='explicit_admitted_no_reduction_run_metadata'
                         and all(value is None or type(value) is int and value>=0
                                 for value in (spec['n_samples_estim'],spec['n_components'],spec['max_dim_allowed'])),
                         'no-reduction retains declared ignored arguments but never fits a surrogate')
    return folders,n,repetitions


def _validate(bound):
    catalog.need(type(bound) is BoundBranch,'bound branch program')
    _limits(bound.limits)
    for raw in (bound.protocol_raw,bound.inventory_raw,bound.graph_raw,bound.run_raw):
        catalog.need(type(raw) is bytes and len(raw)<=bound.limits.max_metadata_bytes,'bounded immutable binding bytes')
    catalog.need(catalog.pin(bound.graph_raw)==_descriptor(bound.graph_pin)
                 and catalog.pin(bound.run_raw)==_descriptor(bound.run_pin),'separately admitted exact metadata bytes')
    compiled=catalog.compile_catalog(bound.protocol_raw,bound.inventory_raw,bound.graph_raw,
                                     _descriptor(bound.graph_pin),require_complete=False)
    required=consumers.membership(bound.branch)
    catalog.need(all(compiled['models'][name]['metadata_closure_complete'] for name,_ in required),
                 'every selected branch model needs full frozen test102 graph/checkpoint/framework/emission metadata')
    layers=tuple((name,tuple(compiled['models'][name]['layers'])) for name,_ in required)
    producer_layers={record['model_id']:tuple(record['emitted_feature_keys'])
                     for record in catalog.strict(bound.graph_raw)['models']}
    protocol=catalog.strict(bound.protocol_raw)
    folders,n,repetitions=_run_contract(bound.branch,protocol,layers,producer_layers,bound.run_raw)
    counts={model:len(names) for model,names in layers};names_by_model=dict(layers)
    inputs=len(ROIS)*len(folders)*sum(counts.values())
    outputs=len(ROIS)*len(folders)*sum(max(count,2) for count in counts.values())
    work=len(ROIS)*len(folders)*sum(7*(count+max(count-2,0)*max(count-3,0)) for count in counts.values())
    catalog.need(inputs<=bound.limits.max_input_rows and outputs<=bound.limits.max_output_rows
                 and work<=bound.limits.max_aggregate_cells,'complete branch conservative workload bounds')
    leaf=bound.limits.depth
    # Combined normalization counts all conditions; no value iterator is touched.
    total_output=outputs//len(ROIS)
    total_text=0
    for group,kind,folder in consumers.groups(bound.branch,folders):
        models=tuple(name for name,type_ in required if type_==kind)
        after=[]
        for model in models:
            names=names_by_model[model]
            count=(len({(name.split('_lateral')[0].split('_')[-1] if '_lateral' in name else name.split('_')[-1])
                        for name in names}) if 'slowfast' in model else len(names))
            after.append(count)
        frequencies=Counter(after)
        modal=min(count for count,freq in frequencies.items() if freq==max(frequencies.values()))
        catalog.need(modal>1,'catalog-known source nontermination at modal depth one')
        rows=sum(counts[name] for name in models)
        row_output=sum(max(counts[name],2) for name in models)
        aggregate=sum(7*(counts[name]+max(counts[name]-2,0)*max(counts[name]-3,0)) for name in models)
        text=sum(max(counts[name],2)*(len(name)+max(map(len,names_by_model[name]))+len(group)+len(folder)+max(map(len,ROIS))) for name in models)
        total_text+=text
        catalog.need(max(rows,row_output)<=leaf.max_rows and 7*max(rows,row_output)<=leaf.max_scalar_cells
                     and aggregate<=leaf.max_aggregate_cells and text<=leaf.max_text_characters,
                     'per-group catalog-known conservative geometry')
    catalog.need(total_output<=leaf.max_rows and 8*total_output<=leaf.max_scalar_cells
                 and total_text<=leaf.max_text_characters,'combined cross-condition normalization geometry')
    return layers,folders,n,repetitions,compiled['complete']


def bind_branch(branch,protocol_raw,inventory_raw,graph_raw,admitted_graph_pin,run_raw,admitted_run_pin,*,limits=Limits()):
    bound=BoundBranch(branch,protocol_raw,inventory_raw,graph_raw,_pin_tuple(admitted_graph_pin),
                      run_raw,_pin_tuple(admitted_run_pin),limits)
    _validate(bound)
    return bound


def run_branch(bound,frames):
    """Yield17 explicitly partial ROI events then complete only after exact EOF."""
    layers,folders,n,repetitions,global_complete=_validate(bound)
    stream=iter(frames);digest=sha256();input_rows=output_rows=work=0
    for roi in ROIS:
        try:frame=next(stream)
        except StopIteration:raise ValueError('missing complete branch ROI frame') from None
        result=consumers.consume_roi(bound.branch,folders,layers,roi,frame,limits=bound.limits.depth)
        input_rows+=sum(len(record.layers) for record in frame.records)
        output_rows+=len(result.depth_rows)
        work+=sum(group.aggregate_cells for group in result.depth_traces)
        catalog.need(input_rows<=bound.limits.max_input_rows and output_rows<=bound.limits.max_output_rows
                     and work<=bound.limits.max_aggregate_cells,'actual cumulative branch workload limits')
        raw=catalog.encoded(asdict(result));digest.update(len(raw).to_bytes(8,'big'));digest.update(raw)
        yield result
    try:next(stream)
    except StopIteration:pass
    else:raise ValueError('extra ROI frame after full17 branch input')
    yield BranchComplete(bound.branch,tuple(name for name,_ in layers),folders,ROIS,n,repetitions,input_rows,
                         output_rows,work,global_complete,True,bound.run_pin[1],digest.hexdigest())
