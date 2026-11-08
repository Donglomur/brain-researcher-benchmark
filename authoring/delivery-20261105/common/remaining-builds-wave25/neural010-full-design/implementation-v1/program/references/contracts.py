"""Explicit worker normalization and source/context binding. No I/O on import."""
import hashlib
from pathlib import Path
from common import need,exact,ID,SHA,descriptor,canonical,parse,records,integer
from features import BASE

SOURCE_FILES=('common.py','contracts.py','features.py','learners.py','math_core.py','selection.py','reference_cli.py','event_protocol.py')

def check_context(context):
    exact(context,('panel_people','outer_person','inner_person'));people=context['panel_people']
    need(type(people) is list and len(people)==23 and people==sorted(set(people)) and all(type(p) is str and ID.fullmatch(p) for p in people),'complete23-person context')
    outer,inner=context['outer_person'],context['inner_person'];need(outer in people and (inner is None or (inner in people and inner!=outer)),'disjoint outer/inner identities')
    return [p for p in people if p not in (outer,inner)]

def normalized_view(view,condition,feature_bindings=None):
    """Parent calls this before serializing records. It never reads a feature body.

    feature_bindings: recording_id -> {feature_receipt, eeg_features} or
    {feature_receipt, signal_features}; must have exact membership. Metadata-only
    conditions require None. Validation needs no feature binding.
    """
    exact(view,('schema','task_id','outer_person','inner_person','role','records'))
    need(view['schema']=='neural010-detector-view-v1' and view['task_id']=='NEURAL-010','preparation view schema')
    need(condition in ('joint','matched_no_eeg','signal_reference','montage_only'),'condition')
    role={'training':'train','query':'query','validation_labels':'validation'}.get(view['role']);need(role is not None,'preparation view role')
    rows=[]
    if role=='validation':
        need(feature_bindings is None,'validation has labels only')
        for row in view['records']:
            exact(row,('recording_id','patient_id','duration_seconds','events'));rows.append(dict(row))
        rows.sort(key=lambda r:(r['patient_id'],r['recording_id']));result={'schema':'neural010-reference-validation-v1','records':rows};validation_rows(result);return result
    requires=condition in ('joint','signal_reference')
    if requires:
        need(type(feature_bindings) is dict and set(feature_bindings)=={r['recording_id'] for r in view['records']},'exact complete feature binding membership')
    else:need(feature_bindings is None,'no EEG descriptors in metadata-only authority')
    for row in view['records']:
        exact(row,set(BASE)|({'events'} if role=='train' else set()));item=dict(row)
        if requires:
            binding=feature_bindings[row['recording_id']];exact(binding,('feature_receipt','eeg_features' if condition=='joint' else 'signal_features'));item.update(binding)
        rows.append(item)
    rows.sort(key=lambda r:(r['patient_id'],r['recording_id']));result={'schema':'neural010-reference-records-v1','role':role,'records':rows};records(result,role,condition);return result

def validation_rows(doc):
    exact(doc,('schema','records'));need(doc['schema']=='neural010-reference-validation-v1','inner label schema')
    rows=doc['records'];need(type(rows) is list and 0<len(rows)<=686,'complete validation records');seen=set();order=[]
    for row in rows:
        exact(row,('recording_id','patient_id','duration_seconds','events'));rid,pid=row['recording_id'],row['patient_id'];d=row['duration_seconds']
        need(type(rid) is str and ID.fullmatch(rid) and rid not in seen and type(pid) is str and ID.fullmatch(pid) and integer(d,1,86400),'unique complete validation metadata');seen.add(rid);order.append((pid,rid))
        need(type(row['events']) is list and len(row['events'])<=d,'bounded original annotations');end=0
        for pair in row['events']:
            need(type(pair) is list and len(pair)==2 and all(integer(x) for x in pair),'integral interval');a,b=pair;need(end<=a<b<=d,'sorted disjoint annotations');end=b
    need(order==sorted(order) and len({r['patient_id'] for r in rows})==1 and sum(r['duration_seconds'] for r in rows)<=10000000,'one complete inner person')
    return rows

def verify_source(identity,io):
    """Authenticate all executable sibling bytes before any command/data work."""
    descriptor(identity,False);root=Path(__file__).resolve().parent;p=root/'SOURCE_MANIFEST.json'
    manifest=io.json({'path':str(p),'bytes':identity['bytes'],'sha256':identity['sha256']})
    exact(manifest,('schema','files','numerical_qualification','authentic_execution'))
    need(manifest['schema']=='neural010-reference-source-v1' and manifest['numerical_qualification'] is False and manifest['authentic_execution'] is False,'source-only manifest')
    need(type(manifest['files']) is list and len(manifest['files'])==len(SOURCE_FILES) and [x['name'] for x in manifest['files']]==sorted(SOURCE_FILES),'complete frozen source closure')
    for member in manifest['files']:
        exact(member,('name','bytes','sha256'));need(member['name'] in SOURCE_FILES,'ordinary pinned source');io.check({'path':str(root/member['name']),'bytes':member['bytes'],'sha256':member['sha256']})
    return manifest


def normalize_worker(io,prepared,feature_bindings,role,condition,context,out,identity):
    """Read labels only inside this admitted worker, at the handler's role barrier."""
    check_context(context);view=io.json(prepared)
    need(view.get('outer_person')==context['outer_person'] and view.get('inner_person')==context['inner_person'],'exact prepared view context')
    need(view.get('role')=={'train':'training','query':'query','validation':'validation_labels'}[role],'exact prepared read role')
    document=normalized_view(view,condition,feature_bindings)
    normalized=io.write_json(out/'NORMALIZED_RECORDS.json',document)
    normalization={'schema':'neural010-worker-normalization-v1','source_identity':identity,'prepared_view':prepared,'normalized_records':normalized,'context':context,'condition':condition,'role':role,'feature_bindings_sha256':hashlib.sha256(canonical(feature_bindings)).hexdigest(),'host_label_read_required':False}
    receipt=io.write_json(out/'NORMALIZATION.json',normalization)
    return document,normalized,receipt
