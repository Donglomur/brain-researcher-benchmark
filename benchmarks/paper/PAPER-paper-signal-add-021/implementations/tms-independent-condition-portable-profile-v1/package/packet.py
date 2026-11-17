"""Fixed candidate material allowlist and original-input admission."""
import os
from pathlib import Path
import stat
from common import need,read,write,encode,decode,pin,admit_pin,plain
from source_projection import SHAPE,BYTES,CONDITIONS,FREQUENCIES,TIMES,SOURCE_PIN
from fixture import PROFILE as FIXTURE_PROFILE,CODE
from docker_owner import IMAGE

MANIFEST_KEYS={'schema','profile','dtype','shape','axis_order','conditions','labels',
 'source_frequency_indices','source_time_indices','frequency_coordinates','time_coordinates',
 'stored_positions','physical_person_mapping_claimed','original_source','values',
 'contains_reference_or_derived_target_fields'}
OFFICIAL=None
PAPER=None

def configure_portable(cfg):
    global OFFICIAL,PAPER
    need(OFFICIAL is None and PAPER is None,'one portable material configuration')
    a=cfg['assets'];PAPER=a['paper']
    OFFICIAL={'generateFigure2B.m':a['driver'],'publication__create_topo.m':a['helper']}

DOCS=('TASK.md','DATA_SCHEMA.md','TASK_CONTRACT.json')

def just_pin(entry):
    need(type(entry) is dict and set(entry)=={'path','bytes','sha256'},'locator_pin_keys')
    need(type(entry['path']) is str,'locator_path')
    return {k:entry[k] for k in ('bytes','sha256')}

def input_packet(manifest_entry,values_entry, *, budget, mode,identity=None):
    need(mode in ('inert','authentic'),'explicit_input_mode')
    manifest=decode(read(manifest_entry['path'],just_pin(manifest_entry),budget,65536,0o400))
    need(type(manifest) is dict and set(manifest)==MANIFEST_KEYS,'closed_raw_input_manifest')
    shape=manifest['shape']
    need(type(shape) is list and all(type(x) is int for x in shape) and shape==list(SHAPE),'full_input_shape')
    need(manifest['schema']=='tms_original_input_projection_v1' and
         manifest['dtype']=='little-endian-binary64' and manifest['axis_order']==
         ['condition','channel','window','frequency','time','stored_position'],'input_layout')
    need(manifest['conditions']==list(CONDITIONS) and manifest['source_frequency_indices']==list(FREQUENCIES) and
         manifest['source_time_indices']==[list(x) for x in TIMES],'exact_input_source_selectors')
    need(all(type(x) is int for x in manifest['source_frequency_indices']) and
         all(type(x) is int for row in manifest['source_time_indices'] for x in row),'strict_input_indices')
    need(manifest['stored_positions']==list(range(15)) and
         all(type(x) is int for x in manifest['stored_positions']) and
         manifest['physical_person_mapping_claimed'] is False and
         manifest['contains_reference_or_derived_target_fields'] is False,'raw_positions_only')
    labels=manifest['labels']
    need(type(labels) is list and len(labels)==62 and
         all(type(x) is str and 1<=len(x)<=64 for x in labels) and len(set(labels))==62,'all_source_labels')
    admit_pin(manifest['values'],BYTES)
    need(manifest['values']==just_pin(values_entry) and manifest['values']['bytes']==BYTES,'raw_payload_binding')
    if mode=='authentic':
        need(type(identity) is dict and manifest['profile']=='original_scientific_operands','authentic_never_fixture')
        admit_pin(manifest['original_source'],SOURCE_PIN['bytes'])
        need(manifest['original_source']==SOURCE_PIN and labels==identity['labels'] and
             manifest['frequency_coordinates']==[identity['frequency'][x] for x in FREQUENCIES] and
             manifest['time_coordinates']==[[identity['time'][x] for x in row] for row in TIMES],
             'authentic_original_metadata_join')
    else:
        need(manifest['profile']==FIXTURE_PROFILE and manifest['original_source'] is None,'explicit_inert_input')
    folder=plain(manifest_entry['path']).parent
    need(plain(values_entry['path'])==folder/'values.f64' and
         plain(manifest_entry['path'])==folder/'INPUT.json','exact_candidate_input_filenames')
    st=folder.lstat()
    need(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode)==0o500,'sealed_candidate_input')
    need({x.name for x in folder.iterdir()}=={'INPUT.json','values.f64'},'no_hidden_input_members')
    read(values_entry['path'],just_pin(values_entry),budget,BYTES,0o400)
    return {'folder':str(folder),'manifest':manifest_entry,'values':values_entry,'profile':manifest['profile'],
            'metadata':manifest}

def require_authentic_delivery(selection,projection, *, budget):
    # This is an owner-selected record; candidates cannot supply it or alter
    # its independently pinned invocation/evidence graph.
    required={'schema','private_delivery_selected','image_content_selected','image',
              'projection_receipt','projection_original_outcome','projection_independent_review'}
    need(type(selection) is dict and set(selection)==required and
         selection['schema']=='tms_p16_private_delivery_selection_v1' and
         selection['private_delivery_selected'] is True and selection['image_content_selected'] is True and
         selection['image']==IMAGE,'separate_authentic_delivery_and_image_selection')
    bodies={}
    for key in ('projection_receipt','projection_original_outcome','projection_independent_review'):
        e=selection[key]
        bodies[key]=read(e['path'],just_pin(e),budget,1048576)
    receipt=decode(bodies['projection_receipt'])
    need(receipt['schema']=='tms_original_projection_owner_receipt_v1' and
         just_pin(receipt['manifest'])==just_pin(projection['manifest']) and
         just_pin(receipt['values'])==just_pin(projection['values']) and
         receipt['source_closed'] is True and receipt['input_origin']=='original_source_only' and
         type(receipt['reference_reads']) is int and receipt['reference_reads']==0,'selected_original_input_provenance')
    # The two external outcome/review pins are root-selected evidence, not
    # self-issued candidate proofs; semantic selection happens before this call.
    return {'owner_selection':selection,'projection_receipt_sha256':pin(bodies['projection_receipt'])['sha256']}

def stage_materials(root, *, arm,mode,document_bodies,budget,delivery=None,projection=None):
    need(arm in ('A','B') and mode in ('inert','authentic'),'fixed_arm_mode')
    need(type(document_bodies) is dict and set(document_bodies)==set(DOCS) and
         all(type(x) is bytes and 0<len(x)<=65536 for x in document_bodies.values()),'complete_locked_candidate_documents')
    if mode=='authentic':
        require_authentic_delivery(delivery,projection,budget=budget)
    root=plain(root);root.mkdir(mode=0o700)
    shared={};extra={}
    for name in DOCS:
        shared[name]=write(root/name,document_bodies[name],budget)
    if mode=='inert':
        shared['ARTICLE_FIXTURE.txt']=write(root/'ARTICLE_FIXTURE.txt',
            b'Invented engineering material. No original paper or scientific result.\n',budget)
    else:
        body=read(PAPER['path'],just_pin(PAPER),budget,2097152)
        shared['article.pdf']=write(root/'article.pdf',body,budget)
    if arm=='B':
        code=root/'released-code';code.mkdir(mode=0o700)
        if mode=='inert':
            extra['fixture_assistance.py']=write(code/'fixture_assistance.py',CODE,budget)
        else:
            for name,entry in OFFICIAL.items():
                body=read(entry['path'],just_pin(entry),budget,65536)
                extra[name]=write(code/name,body,budget)
        os.chmod(code,0o500)
    os.chmod(root,0o500)
    return {'folder':str(root),'arm':arm,'mode':mode,
            'shared':{k:just_pin(v) for k,v in shared.items()},
            'code':{k:just_pin(v) for k,v in extra.items()},
            'exact_top_level':sorted([*shared]+(['released-code'] if arm=='B' else []))}

def paired_materials(a,b):
    need(a['arm']=='A' and b['arm']=='B' and a['mode']==b['mode'] and a['shared']==b['shared'],
         'same_complete_contract_and_shared_materials')
    need(a['code']=={} and bool(b['code']),'only_released_code_exposure_delta')
    return True

