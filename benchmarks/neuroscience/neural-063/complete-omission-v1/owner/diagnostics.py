"""Frozen descriptive metadata and preceding-sequence support diagnostics.

These cells never alter the primary full-panel metric. Every source metadata
level and every FIT/validation/query sequence appears, including empty query
cells. Conditional cell scores retain the mouse/session/experiment/event
hierarchy among the observations present in that declared cell.
"""
from collections import defaultdict
from .io import ContractError, canonical
from . import scoring

FIELDS=('cre_line','targeted_structure','imaging_depth','image_set','passive','experience_level','session_number')


def counts(rows):
    return {'mice':len({r['mouse'] for r in rows}),'sessions':len({r['session'] for r in rows}),
            'experiments':len({r['experiment'] for r in rows}),'events':len(rows)}


def original_counts(experiments):
    return {'mice':len({r['mouse'] for r in experiments}),'sessions':len({r['session'] for r in experiments}),
            'experiments':len(experiments),'published_roi_rows':sum(r['published_valid_rois'] for r in experiments),
            'original_omissions':sum(r['original_omissions'] for r in experiments),
            'scheduled_omissions':sum(r['scheduled'] for r in experiments),
            'supported_events':sum(r['supported'] for r in experiments)}


def _cell(rows,predictions,sd):
    denominator=counts(rows)
    if not rows:
        return {'support':denominator,'status':'no_supported_query_observation','scores':None}
    ids={r['id'] for r in rows}
    scores={name:scoring.absolute({k:p[k] for k in ids},rows,sd,denominator['mice'])
            for name,p in predictions.items()}
    return {'support':denominator,'status':'descriptive','scores':scores}


def sequence(row):
    previous=row.get('previous')
    if not isinstance(previous,list) or len(previous)!=3:
        raise ContractError('three exact preceding stimulus tokens required for support diagnostics')
    value=[]
    for p in previous:
        if not isinstance(p.get('image'),str) or type(p.get('omitted')) is not bool:
            raise ContractError('exact image/omission token required')
        value.append([p['image'],p['omitted']])
    return value


def describe(rows,predictions,sd,census,fit,validation):
    for source in (rows,fit,validation):
        if any(set(r.get('context',{}))!=set(FIELDS) for r in source):
            raise ContractError('fixed seven-field context required for descriptive strata')
    experiments=census['experiments']
    if any(set(r.get('context',{}))!=set(FIELDS) for r in experiments):
        raise ContractError('all original experiment context rows required')
    metadata={}
    for field in FIELDS:
        levels={canonical(e['context'][field]):e['context'][field] for e in experiments}
        if any(canonical(r["context"][field]) not in levels for r in rows):
            raise ContractError("query diagnostic context is absent from original source roster")
        cells=[]
        for key,value in sorted(levels.items()):
            original=[e for e in experiments if canonical(e['context'][field])==key]
            query_original=[e for e in original if e['split']=='query']
            selected=[r for r in rows if canonical(r['context'][field])==key]
            cells.append({'value':value,'original_source':original_counts(original),
                          'original_query_source':original_counts(query_original),**_cell(selected,predictions,sd)})
        metadata[field]=cells
    by_split={}
    values={}
    for split,source in [('fit',fit),('validation',validation),('query',rows)]:
        groups=defaultdict(list)
        for row in source:
            value=sequence(row);key=canonical(value);values[key]=value;groups[key].append(row)
        by_split[split]=groups
    sequence_cells=[]
    refs={key:predictions[key] for key in ('reference:T','reference:N')}
    for key,value in sorted(values.items()):
        supports={split:counts(groups.get(key,[])) for split,groups in by_split.items()}
        sequence_cells.append({'preceding_tokens':value,'split_support':supports,
             'common_fit_validation_query_support':all(supports[s]['events']>0 for s in supports),
             'query_reference_errors':_cell(by_split['query'].get(key,[]),refs,sd)})
    common={key for key in values if all(by_split[s].get(key) for s in by_split)}
    return {'schema':'neural063_descriptive_support_diagnostics_v1','metadata_fields':list(FIELDS),
            'metadata':metadata,'preceding_sequence':sequence_cells,
            'common_sequence_support':{s:counts([r for k,rr in groups.items() if k in common for r in rr])
                                       for s,groups in by_split.items()},
            'all_sequence_support':{s:counts([r for rr in groups.values() for r in rr]) for s,groups in by_split.items()},
            'primary_observations_discarded':0,'interpretation':'Fixed descriptive overlapping strata; conditional hierarchy within each cell; no independent tasks, no multiplicity claims, no replacement of full-panel score.'}
