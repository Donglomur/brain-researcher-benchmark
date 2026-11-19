"""Complete raw-epoch panel collection and four-panel public custody admission.

Only trusted operator records are operands. Collections do not qualify their own
provider, image, runtime, identity provenance or native boundary. Every row is
rejoined to the maintained original Packet before a scientific target is read.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import raw_contract as C
import raw_programme as P
import raw_viewer as V
import raw_provider as B

ARMS=('viewer','programme')
PANELS=tuple((arm,modality) for arm in ARMS for modality in C.MODALITIES)
CONDITIONS={('viewer',m):C.VIEWER_CONDITIONS[m] for m in C.MODALITIES}
CONDITIONS.update({('programme',m):C.PROGRAMME_CONDITIONS[m] for m in C.MODALITIES})


def runtime(source, dependency_root=None):
    return {'viewer':V.load_runtime(source,dependency_root), 'programme':P.load_runtime(source,dependency_root)}


def record_manifest(descriptor):
    value=C.decode(C.capture(descriptor,8*2**20))
    C.need(type(value) is dict and set(value)=={'schema','arm','modality','records'}
           and value['schema']=='neural008_raw_records_v1' and value['arm'] in ARMS, 'Exact operator record manifest')
    C.checked_modality(value['modality']); C.checked_complete_rows(value['records'])
    C.need(all(set(row)=={'epoch_id','record'} for row in value['records']), 'One frozen first-final record descriptor per target')
    for row in value['records']: C.checked_pin(P.plain(row['record']))
    return value


def selected_knowledge(descriptor):
    raw=C.capture(descriptor,8192); value=C.checked_knowledge(C.decode(raw))
    C.need(C.encode(value)==raw,'Canonical shared declared prior')
    return value


def input_roots(value):
    C.need(type(value) is dict and set(value)==set(dict(C.CASES)), 'Exactly two complete exposed original people')
    return {case:C.ordinary_path(root) for case,root in value.items()}


def audit_row(rt,arm,modality,row,packet,knowledge):
    C.need(packet.modality==modality and row['epoch_id']==packet.epoch_id,'Exact first-final target/modality')
    record=C.decode(C.capture(row['record'],2**20))
    if arm=='viewer':
        C.need(type(record) is dict and set(record)=={'epoch_id','modality','session_root'}
               and record['epoch_id']==packet.epoch_id and record['modality']==modality, 'Viewer session record')
        checked=B.audit_session(record['session_root'],packet,rt['viewer'],knowledge)
        C.need(checked['epoch_id']==packet.epoch_id and checked['condition']==C.VIEWER_CONDITIONS[modality]
               and checked['modality']==modality and checked['family']==C.FAMILY, 'Actual raw-viewer condition binding')
        identities=[('session',checked['session_id'])]+[('response',x) for x in checked['response_ids']]
        definition=None
    else:
        checked=P.admit_phase(rt['programme'],record,packet,knowledge)
        identities=[('resource',r['name']) for r in checked['resources']]+[('phase',checked['phase_id'])]
        definition=checked['definition']
    return checked['probabilities'], identities, definition


def validate_collection(descriptor,source,knowledge):
    value=C.decode(C.capture(descriptor,32768))
    C.need(type(value) is dict and set(value)=={'schema','family','arm','modality','condition','source','knowledge',
           'records','submission','programme_definition','count','people','qualification'}
           and value['schema']=='neural008_raw_collection_v1' and value['family']==C.FAMILY
           and value['arm'] in ARMS and value['modality'] in C.MODALITIES
           and value['condition']==CONDITIONS[(value['arm'],value['modality'])]
           and value['source']==P.plain(source) and value['knowledge']==P.plain(knowledge)
           and value['count']==C.TOTAL and value['people']==2 and value['qualification'] is False,
           'Complete frozen task-local collection identity')
    manifest=record_manifest(value['records'])
    C.need((manifest['arm'],manifest['modality'])==(value['arm'],value['modality']), 'Collection/record arm binding')
    if value['arm']=='viewer': C.need(value['programme_definition'] is None,'Viewer has no programme definition')
    else: C.checked_pin(value['programme_definition'])
    return value,manifest


def collect(source,dependency_root,original_inputs,knowledge,records,output_root):
    # Validate complete metadata before any original Packet or retained session body.
    manifest=record_manifest(records); prior=selected_knowledge(knowledge)
    roots=input_roots(original_inputs); rt=runtime(source,dependency_root)
    arm,modality=manifest['arm'],manifest['modality']; answers=C.FirstAnswers(); identities=set(); definition=None; at=0
    for case,count in C.CASES:
        original=rt['viewer']['original_viewer'].Packet(roots[case],case)
        try:
            for index in range(count):
                packet=C.project_epoch(original,index,modality); row=manifest['records'][at]; at+=1
                values,seen,defined=audit_row(rt,arm,modality,row,packet,prior)
                for identity in seen:
                    C.need(identity not in identities,'Fresh session/response/resource per target'); identities.add(identity)
                if defined is not None:
                    if definition is None: definition=defined
                    C.need(defined==definition,'One frozen candidate across every programme target')
                answers.accept(packet.epoch_id,values,P.plain(row['record']))
        finally: original.close()
    rows=answers.complete(); root=C.ordinary_path(output_root); root.mkdir(mode=0o700)
    submission=C.write_new(root/'probabilities.npz',C.submission_bytes(rows))
    return C.write_new(root/'COLLECTION.json',C.encode({'schema':'neural008_raw_collection_v1','family':C.FAMILY,
        'arm':arm,'modality':modality,'condition':CONDITIONS[(arm,modality)],'source':P.plain(source),
        'knowledge':P.plain(knowledge),'records':records,'submission':submission,'programme_definition':definition,
        'count':C.TOTAL,'people':2,'qualification':False}))


def admit_four(config):
    """Public only: complete frozen panels, actual access custody and shared original signals."""
    C.need(type(config) is dict and set(config)=={'source','dependency_root','original_inputs','knowledge','collections'},
           'Exact public four-panel admission request')
    source=config['source']; knowledge=config['knowledge']; collections=config['collections']
    C.need(type(collections) is dict and set(collections)==set(CONDITIONS.values()), 'All four complete raw panels required')
    prior=selected_knowledge(knowledge); roots=input_roots(config['original_inputs'])
    validated={}; manifests={}; definitions=[]
    for arm,modality in PANELS:
        condition=CONDITIONS[(arm,modality)]
        value,manifest=validate_collection(collections[condition],source,knowledge)
        C.need((value['arm'],value['modality'])==(arm,modality),'No relabelled collection')
        validated[(arm,modality)]=value; manifests[(arm,modality)]=manifest
        if arm=='programme': definitions.append(value['programme_definition'])
    C.need(definitions[0]==definitions[1], 'Same frozen candidate definition across modalities')
    # Freeze all four panel bytes before original public evidence or private targets.
    submissions={key:C.capture(value['submission'],4_000_000) for key,value in validated.items()}
    rt=runtime(source,config['dependency_root']); identities=set(); answers={key:C.FirstAnswers() for key in PANELS}; at=0
    for case,count in C.CASES:
        original=rt['viewer']['original_viewer'].Packet(roots[case],case)
        try:
            for index in range(count):
                packets={m:C.project_epoch(original,index,m) for m in C.MODALITIES}
                C.check_shared_epoch(packets[C.EEG],packets[C.EEG_EOG])
                for arm,modality in PANELS:
                    key=(arm,modality); row=manifests[key]['records'][at]
                    values,seen,definition=audit_row(rt,arm,modality,row,packets[modality],prior)
                    if arm=='programme': C.need(definition==definitions[0],'Same frozen candidate for both modalities')
                    for identity in seen:
                        C.need(identity not in identities,'Fresh isolated context and resources across all four panels')
                        identities.add(identity)
                    answers[key].accept(row['epoch_id'],values,P.plain(row['record']))
                at+=1
        finally: original.close()
    for key in PANELS:
        C.need(C.submission_bytes(answers[key].complete())==submissions[key], 'Complete probabilities equal admitted first finals')
    return {'schema':'neural008_raw_four_public_freeze_v1','family':C.FAMILY,'source':P.plain(source),
        'knowledge':P.plain(knowledge),'collections':{k:P.plain(v) for k,v in collections.items()},
        'panels':{CONDITIONS[key]:validated[key]['submission'] for key in PANELS},
        'programme_definition':definitions[0],'count_per_panel':C.TOTAL,'people':2,'shared_eeg_and_clock_verified':True,
        'public_custody_complete':True,'provider_qualification':False,'scientific_qualification':False,
        'temporal_context_removed':True,'hidden_pretraining_verified':False,'population_inference':False}


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument('--operation',choices=('collect',),required=True)
    parser.add_argument('--config',required=True);parser.add_argument('--bytes',type=int,required=True);parser.add_argument('--sha256',required=True)
    a=parser.parse_args(argv); config=C.decode(C.capture({'path':a.config,'bytes':a.bytes,'sha256':a.sha256},2**20))
    result=collect(**config); print(C.encode({'status':'complete','collection':result,'qualification':False}).decode(),end='');return result


if __name__=='__main__':main()
