"""Concrete role/mount/image and public information boundary."""
from pathlib import Path
import re
from core import need, descriptor, identity, PROFILES
from safe_io import strict
from staging import validate_files


def approve_image(role,image,inventory,audit,program_source_pin,forbidden_hashes):
    need(type(inventory) is dict and set(inventory)=={'schema','image','files','complete_filesystem','capture_receipt'} and inventory['schema']=='paper_i_image_inventory_v1','Complete independently captured image inventory')
    need(inventory['image']==image['digest'] and inventory['complete_filesystem'] is True,'Exact immutable whole image')
    descriptor(inventory['capture_receipt']);files=inventory['files']
    need(type(files) is list and files and len({x['path'] for x in files})==len(files),'Complete unique image member rows')
    for row in files:
        need(type(row) is dict and set(row)=={'path','bytes','sha256'} and type(row['path']) is str and row['path'].startswith('/'),'Absolute image member')
        descriptor({k:row[k] for k in ('bytes','sha256')},True)
    keys={'schema','role','image','inventory_sha256','program_source_sha256','complete_source_boundary_reviewed','no_private_data_or_credentials','operator_reference_excluded','author_source_excluded','shared_monotonic_clock','review_receipt','mounted_source_files'}
    need(type(audit) is dict and set(audit)==keys and audit['schema']=='paper_i_image_boundary_v1','Independent source/exposure audit')
    need(audit['role']==role and audit['image']==image['digest'] and audit['inventory_sha256']==image['inventory']['sha256'] and audit['program_source_sha256']==program_source_pin['sha256'],'Actual image/program/audit join')
    need(audit['complete_source_boundary_reviewed'] is True and audit['no_private_data_or_credentials'] is True and audit['shared_monotonic_clock'] is True,'External full source/data/clock boundary gate')
    descriptor(audit['review_receipt']);need(type(audit['mounted_source_files']) is dict and audit['mounted_source_files'],'Full reviewed mounted source inventory')
    for name,p in audit['mounted_source_files'].items():need(name.startswith('/'),'Absolute reviewed source');descriptor(p)
    if role in ('A','B'):
        need(audit['operator_reference_excluded'] is True,'No operator/reference source in candidate image')
        need(not ({f['sha256'] for f in files}&set(forbidden_hashes)),'No forbidden exact source bodies in candidate image')
    if role=='A':need(audit['author_source_excluded'] is True,'A full image excludes authenticated author implementation')
    return True


def public_payload(action,role,payload):
    need(role in ('A','B'),'Public candidate path only')
    need(type(payload) is dict,'Typed candidate request')
    if action=='fit':
        keys={'schema','train_path','train_pin','configuration','selected_cell_indices','selected_cell_tokens','namespace'}
        need(set(payload)==keys and payload['schema']=='paper_i_candidate_fit_v1','Small train-only candidate request')
        need(payload['train_path']=='TRAIN.json','Current public train mount only');descriptor(payload['train_pin'])
        need(type(payload['configuration']) is dict and set(payload['configuration'])=={'id','parameters'},'Precommitted candidate configuration')
    elif action=='query':
        keys={'schema','profile','record','cell_tokens','bundle_path','bundle_pin','namespace'}
        need(set(payload)==keys and payload['schema']=='paper_i_candidate_query_v1','One-record candidate ABI')
        legal_record(payload['record'],payload['profile']);descriptor(payload['bundle_pin'])
        need(payload['bundle_path']=='BUNDLE.json','Only sealed current-namespace model bundle')
    elif action=='reconstruct':
        keys={'schema','branch','native_seed','required_roots','input_manifest','output_format','namespace'}
        need(set(payload)==keys and payload['schema']=='paper_i_candidate_reconstruction_v1','Full selected native reconstruction ABI')
    else:raise ValueError('Candidate never executes private operator phase')
    need(type(payload['namespace']) is str and re.fullmatch('[0-9a-f]{32}',payload['namespace']),'Random opaque execution namespace, never a source ordinal')
    return payload


def legal_record(record,profile):
    need(profile in PROFILES and type(record) is dict,'Exact view')
    keys=set()
    if profile!='M':keys|={'time','measured_delay','categories'}
    if profile!='C':keys.add('movement')
    need(set(record)==keys,'No neural/history/other-query/identity/implicit clock fields')
    if 'categories' in record:need(set(record['categories'])=={'planned_delay','reinforcer','first_reward_order','delivered_outcome'},'Only source task context')
    if 'movement' in record:
        names={f'{v}_tap_{tap}' for v in ('position_0','position_1','velocity_0','velocity_1','speed') for tap in ('m4','m3','m2','m1','0','p1','p2','p3','p4')}|{'movement_duration','movement_length'}
        need(type(record['movement']) is dict and set(record['movement'])==names,'Exact 47 source-grounded movement values')
        for v in record['movement'].values():need(v is None or type(v) in (int,float) and __import__('math').isfinite(v),'Finite observed or explicitly missing feature')
    if 'time' in record:
        need(all(type(record[k]) in (int,float) and __import__('math').isfinite(record[k]) for k in ('time','measured_delay')),'Finite local clock')
        need(all(type(v) is str and v for v in record['categories'].values()),'Literal bounded category tokens')
    return record


def candidate_mounts(action,role,mounts,encoding_sealed):
    need(role in ('A','B'),'Exact arm')
    required={'/program','/input','/paper/article.xml','/contract'}
    if role=='B':required.add('/author')
    if action=='query':required.add('/models')
    if action=='reconstruct':
        need(encoding_sealed is True,'Every encoding namespace must be irreversibly closed before raw data exposure')
        required.add('/originals')
    need(set(mounts)==required,'Complete candidate mounts; no source/lineage/private truth/control roots')
    for target,row in mounts.items():
        need(type(row) is dict and set(row)=={'path','kind','purpose','files'},'Exact closed mount')
        validate_files(row['files'])
        if target=='/author':need(role=='B' and row['purpose']=='historical_author_source','Only B receives exact author files')
        else:need(row['purpose'] in ('paper','contract','input','program'),'No operator-purpose candidate mount')
    return True


def public_training(train):
    need(type(train) is dict and set(train)=={'schema','profile','feature_schema','cell_tokens','X','Y','weights','namespace'} and train['schema']=='paper_i_training_view_v1','Exact public-only training artifact')
    p=train['profile'];need(p in PROFILES,'Known information profile')
    keys={'profile'}|({'movement_features'} if p!='C' else set())|({'categorical_vocabulary','target_time_grid'} if p!='M' else set())
    need(set(train['feature_schema'])==keys and train['feature_schema']['profile']==p,'No masked metadata in feature schema')
    for record in train['X']:legal_record(record,p)
    need(train['X'] and len(set(train['cell_tokens']))==len(train['cell_tokens'])>0,'Complete public support')
    return train
