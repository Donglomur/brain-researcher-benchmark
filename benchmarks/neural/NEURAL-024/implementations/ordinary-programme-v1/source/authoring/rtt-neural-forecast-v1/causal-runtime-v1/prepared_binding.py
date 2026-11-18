"""Exact existing two-root case admission; never imports or decodes neural arrays."""
import hashlib
import os
from pathlib import Path
import stat
import time
from common import HERE,ROOT,regular,strict,need,lock
import prepared_case_contract as contract
from programme_admission import selected,meta
RUN=Path(selected()['run'])

def packet():
    chosen=selected();row=chosen['case_manifest']
    custody=strict(meta(row['path'],32768,{k:row[k]for k in('bytes','sha256')}))
    need(type(custody)is dict and set(custody)=={'schema','public_root','private_root','metadata_paths'}
         and custody['schema']=='neural024-prepared-custody/v1','closed portable custody manifest')
    identity=strict(regular(HERE/'CASE_IDENTITY.json',32768));value={'new_run':chosen['run'],'public':{},'private':{}}
    for group in('public','private'):
        root=Path(custody[group+'_root']);need(root.is_absolute()and '..'not in root.parts,'absolute existing data custody')
        for name,p in identity[group].items():value[group][name]={'path':str(root/name),**p}
    need(type(custody['metadata_paths'])is dict and set(custody['metadata_paths'])==set(identity['metadata']),'closed provenance custody')
    for name,p in identity['metadata'].items():
        path=Path(custody['metadata_paths'][name]);need(path.is_absolute()and '..'not in path.parts,'absolute metadata custody')
        value[name]={'path':str(path),**p}
    value['case_stage_provenance']=identity['case_stage_provenance']
    need({name:{k:r[k]for k in('bytes','sha256')}for name,r in value['public'].items()}==contract.PUBLIC_PINS,'unchanged public bank identities')
    return value

def packet_private(name):
    value=packet();need(name in value['private'],'fixed private role')
    return Path(value['private'][name]['path'])

def metadata_record(row,read=regular):
    body=read(row['path'],row['bytes'])
    need(lock(body)=={k:row[k]for k in('bytes','sha256')},'authenticated closed-stage metadata')
    return strict(body)

def authentic_opaque(row,end):
    path=Path(row['path']);need(all(not p.is_symlink()for p in(path,*path.parents)),'unlinked exact artifact')
    before=path.lstat();need(stat.S_ISREG(before.st_mode)and before.st_nlink==1
         and stat.S_IMODE(before.st_mode)==0o444 and before.st_size==row['bytes'],'immutable bounded existing artifact')
    stamp=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mode,s.st_nlink,s.st_mtime_ns,s.st_ctime_ns)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);digest=hashlib.sha256();total=0
    try:
        need(stamp(before)==stamp(os.fstat(fd)),'same opened artifact')
        while total<before.st_size:
            need(time.monotonic()<end,'bounded opaque admission deadline')
            body=os.read(fd,min(65536,before.st_size-total));need(bool(body),'complete opaque artifact');total+=len(body);digest.update(body)
        need(not os.read(fd,1)and stamp(before)==stamp(os.fstat(fd))==stamp(path.lstat()),'stable complete opaque admission')
    finally:os.close(fd)
    need(digest.hexdigest()==row['sha256'],'exact existing artifact hash')
    return total

def admit(end,selection=None,read=regular,opaque=authentic_opaque):
    value=packet()if selection is None else selection
    # Production always obtains packet(); injection is only for generated metadata controls.
    prior=metadata_record(value['bank_qualification'],read);contract.prior_qualification(prior)
    need({k:value['bank_root_closure'][k]for k in('bytes','sha256')}==contract.ROOT_BANK_RESULT_PIN,'selected prior root closure')
    metadata_record(value['bank_root_closure'],read)
    outer=metadata_record(value['case_root_closure'],read)
    need(outer['status']=='original_remaining_case_prepared_and_external_closure_verified'
         and outer['case_packet_prepared']is True and outer['native_lease_free']is True
         and outer['candidate_invocations']==outer['scientific_fits']==0 and outer['scoring_performed']is False,
         'actual stopped case preparation, not inherited single-stage counters')
    receipt=metadata_record(value['private']['prepare_receipt.json'],read)
    stage=value['case_stage_provenance'];need(receipt['stage_provenance']==stage,'exact current split-stage provenance')
    fresh={name:{k:value['private'][name][k]for k in('bytes','sha256')}for name in('observations.jsonl','schedule.json','references.json')}
    contract.receipt(receipt,fresh,contract.CONFIG_PIN['sha256'],stage['admission_sha256'],stage['root_decision_pin'],stage['source_pins'])
    need(receipt['reference_scores_pin']==contract.REFERENCE_PIN and receipt['incomplete_operation_extent_unknown']is False,
         'full original case and frozen reference')
    observed={r['name']:{k:r[k]for k in('bytes','sha256')}for r in outer['outputs']}
    need(observed=={name:{k:r[k]for k in('bytes','sha256')}for name,r in value['private'].items()},'current operator output custody')
    total=0
    for group in('public','private'):
        for row in value[group].values():total+=opaque(row,end)
    files={name:{k:r[k]for k in('bytes','sha256')}for group in('public','private')for name,r in value[group].items()}
    return files,{'status':'exact_existing_case_admitted','old_prepare_invoked':False,'public_banks_copied':False,
        'current_stage_counters':receipt['counters'],'prior_bank_counters':prior['counters'],
        'opaque_existing_input_bytes':total,'host_neural_array_decodes':0,'files':files,
        'case_receipt':value['private']['prepare_receipt.json'],'whole_benchmark_ready':False}
