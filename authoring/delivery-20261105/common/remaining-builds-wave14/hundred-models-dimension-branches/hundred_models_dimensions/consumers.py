"""Pure figure-branch consumers, with no model/RDM fitting or renderer."""
from dataclasses import dataclass
from math import isfinite
from statistics import median

from . import _depth as depth
from ._catalog_gate import need
from ._scope import MAIN92, IMAGE51, ROIS, DISPLAY_DEPTH_ROIS, METHOD_FOLDERS


@dataclass(frozen=True)
class LayerScore:
    layer: str
    R: float


@dataclass(frozen=True)
class ModelCondition:
    model: str
    folder: str
    layers: tuple


@dataclass(frozen=True)
class NoiseCeiling:
    lower: float
    upper: float


@dataclass(frozen=True)
class ROIFrame:
    roi: str
    records: tuple
    noise_ceiling: NoiseCeiling


@dataclass(frozen=True)
class BestLayer:
    model: str
    folder: str
    group: str
    layer: str
    numeric_layer: int
    R: float


@dataclass(frozen=True)
class GroupSummary:
    group: str
    model_order: tuple
    median_best_R: float
    mean_best_R: float
    noise_ceiling: NoiseCeiling


@dataclass(frozen=True)
class DepthRow:
    model: str
    folder: str
    group: str
    output_ordinal: int
    layer_name: object
    adjusted_layer: int
    normalized_depth: float
    max_layer_across_conditions: int
    R: float


@dataclass(frozen=True)
class GroupTrace:
    group: str
    modal_depth: int
    layer_counts: tuple
    slowfast_groups: tuple
    middle_rounds: tuple
    aggregate_cells: int


@dataclass(frozen=True)
class ROIResult:
    roi: str
    best_layers: tuple
    summaries: tuple
    depth_rows: tuple
    depth_traces: tuple
    is_displayed_depth_roi: bool
    whole_branch_complete: bool = False
    native_numeric_parity_qualified: bool = False
    historical_execution_proven: bool = False
    renderer_qualified: bool = False


def membership(branch):
    need(branch in ('figure16', 'figure17'), 'exact published branch identifier')
    return MAIN92 if branch == 'figure16' else IMAGE51


def groups(branch, folders):
    """Source first appearance: model type then admitted comparison/base order."""
    types = tuple(dict.fromkeys(kind for _, kind in membership(branch)))
    return tuple((kind + '-' + folder if branch == 'figure16' else kind, kind, folder)
                 for kind in types for folder in folders)


def validate_folders(branch, folders):
    need(type(folders) is tuple and all(type(x) is str and 0 < len(x) <= 256 for x in folders),
         'explicit immutable source folder order')
    if branch == 'figure16':
        need(len(folders) == 3 and set(folders) == {x for x,_ in METHOD_FOLDERS},
             'all three exact published dimension folders, no default order')
    else:
        need(len(folders) == 1, 'one explicitly admitted train run folder')


def finite_R(value):
    return type(value) is float and isfinite(value) and -1 <= value <= 1


def validate_frame(branch, folders, layers, roi, frame):
    """All branch models and layers, no trimming to best layers before closure."""
    need(type(frame) is ROIFrame and frame.roi == roi, 'ordered full17 scientific ROI identity')
    need(type(frame.noise_ceiling) is NoiseCeiling and finite_R(frame.noise_ceiling.lower)
         and finite_R(frame.noise_ceiling.upper), 'declared finite signed brain noise ceilings')
    models = membership(branch)
    need(tuple(name for name,_ in layers) == tuple(name for name,_ in models), 'exact branch layer-axis identity')
    need(type(frame.records) is tuple and len(frame.records) == len(models)*len(folders),
         'complete model-by-condition support')
    by_key = {}
    index = 0
    for (model, kind), (_, names) in zip(models, layers):
        for folder in folders:
            record = frame.records[index]; index += 1
            need(type(record) is ModelCondition and (record.model,record.folder) == (model,folder),
                 'source model outer / comparison folders then base folder inner order')
            need(type(record.layers) is tuple and len(record.layers) == len(names), 'all catalog layers')
            for score,name in zip(record.layers,names):
                need(type(score) is LayerScore and score.layer == name and finite_R(score.R),
                     'exact ordered layer and finite floating signed subject-mean R')
            by_key[model,folder] = record
    return by_key


_COLUMNS = (depth.Column('Model','text'), depth.Column('Layer','integer'),
            depth.Column('Layer_FullNames','text'), depth.Column('R','real'),
            depth.Column('Group','text'), depth.Column('Folder','text'), depth.Column('ROI','text'))


def consume_roi(branch, folders, layers, roi, frame, *, limits=depth.Limits()):
    """Translate best-layer and depth-table consumers for one complete ROI.

    Noise ceilings are declared brain-side inputs, not computed or authenticated
    here. Box/strip plotting retains every best-model row; mean and median are
    separately named summaries. No native quantile, bootstrap or CI is invented.
    """
    validate_folders(branch, folders)
    by_key = validate_frame(branch,folders,layers,roi,frame)
    best = []
    for model,kind in membership(branch):
        for folder in folders:
            record = by_key[model,folder]
            index = max(range(len(record.layers)), key=lambda i: record.layers[i].R)
            score = record.layers[index]
            group = kind+'-'+folder if branch == 'figure16' else kind
            best.append(BestLayer(model,folder,group,score.layer,index,score.R))
    summaries, traces, adjusted_rows = [], [], []
    for group,kind,folder in groups(branch,folders):
        names = tuple(model for model,which in membership(branch) if which == kind)
        selected = tuple(row for row in best if row.group == group)
        scores = tuple(row.R for row in selected)
        summaries.append(GroupSummary(group,names,median(scores),sum(scores)/len(scores),frame.noise_ceiling))
        rows = tuple((model,i,score.layer,score.R,group,folder,roi)
                     for model in names for i,score in enumerate(by_key[model,folder].layers))
        adjusted = depth.adjust_layers(depth.Table(_COLUMNS,rows),limits=limits)
        traces.append(GroupTrace(group,adjusted.modal_depth,adjusted.layer_counts,
                                 adjusted.slowfast_groups,adjusted.middle_rounds,adjusted.aggregate_cells))
        adjusted_rows.extend(adjusted.table.rows)
    # Literal source composition: normalize AFTER concatenating adjusted groups.
    # MaxLayer is by Model only, intentionally shared across Fig16 conditions.
    adjusted_table = depth.Table(_COLUMNS,tuple(adjusted_rows))
    normalized = depth.normalize_to_model_depth(adjusted_table,limits=limits)
    need(not normalized.zero_max_models, 'undefined zero-depth source normalization')
    group_order = {name:i for i,(name,_,_) in enumerate(groups(branch,folders))}
    model_order = {name:i for i,(name,_) in enumerate(membership(branch))}
    pairs = sorted(zip(adjusted_table.rows,normalized.table.rows),
                   key=lambda pair:(group_order[pair[1][4]],model_order[pair[1][0]],pair[1][1]))
    rows,ordinals = [],{}
    for original,row in pairs:
        key = row[0],row[5]
        ordinal = ordinals.get(key,0);ordinals[key] = ordinal+1
        rows.append(DepthRow(row[0],row[5],row[4],ordinal,row[2],original[1],row[1],row[7],row[3]))
    return ROIResult(roi,tuple(best),tuple(summaries),tuple(rows),tuple(traces),roi in DISPLAY_DEPTH_ROIS)
