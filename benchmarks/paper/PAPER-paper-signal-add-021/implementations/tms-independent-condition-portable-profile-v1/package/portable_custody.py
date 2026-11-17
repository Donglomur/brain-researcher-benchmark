"""Operator-selected, post-review custody. No candidate-selected reference API.

The descriptor pin must come from the trusted controller AFTER independent
original-outcome review, including original outer natural exit. A descriptor's
own hashes or an AdmittedBody instance alone are never custody authority.
Candidate programs are not run here or imported into this trusted process.
"""
from pathlib import Path
from dataclasses import dataclass
import json
import os
import stat
from kernel import require
from certificate import pin, keys, hash_text
from authentic import identity, context, admit_bytes, SUPPORT_BYTES, IDENTITY_PIN
from reader.contract import MASTER_PIN

_TOKEN=object()

def portable_reference_inputs(expected_lock):
    # Versioned relocation: accepted reference context remains owner-selected.
    # Complete executable source is authenticated by the portable source lock;
    # no historical constructor is imported or its old host path followed.
    from portable_config import current,read as owner_read
    cfg=current()
    require(expected_lock==cfg['reference']['source_lock_sha256'],'selected historical reference context')
    owner_read(cfg['assets']['reference_review'],1048576)
    identity_body=owner_read(cfg['assets']['identity'],65536)
    config={'attempt_identity':'authentic-interval-reference-01','input_pin':MASTER_PIN,
            'external_attempt':cfg['reference']['root']}
    # This is a new routing record, not a reconstructed historical CONFIG file.
    return config,identity_body


def ordinary(path,cap):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and stat.S_IMODE(before.st_mode)==0o400 and 0<=before.st_size<=cap,'private sealed ordinary reference body')
        parts=[];left=before.st_size
        while left:
            block=os.read(fd,min(left,65536));require(bool(block),'complete reference body');parts.append(block);left-=len(block)
        sig=lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        require(sig(before)==sig(os.fstat(fd)),'stable private reference body')
        return b''.join(parts)
    finally:os.close(fd)


def private_directory(path):
    st=path.lstat()
    require(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode)==0o500,'sealed ordinary private reference directory')


@dataclass(frozen=True)
class OperatorReference:
    admitted: object
    owner_descriptor_pin: dict
    source_context: dict
    _token: object


def capture(*, selected_source_lock_sha256, selected_descriptor_pin):
    """Controller-only source/descriptor selections, never candidate input.

    The portable owner configuration fixes relocated paths and exact approved
    descriptor/context identities. The reference bytes and original closure
    semantics are unchanged; no constructor is executed or reference discovered.
    The caller supplies this selection only after independent original review.
    """
    trusted_config,identity_body=portable_reference_inputs(selected_source_lock_sha256)
    identity(identity_body)
    require(trusted_config.get('attempt_identity')=='authentic-interval-reference-01'
            and trusted_config.get('input_pin')==MASTER_PIN,'fixed original-source configuration')
    keys(selected_descriptor_pin,{'bytes','sha256'})
    require(type(selected_descriptor_pin['bytes']) is int and 0<selected_descriptor_pin['bytes']<=65536,'strict independently selected descriptor length')
    hash_text(selected_descriptor_pin['sha256'])
    root=Path(trusted_config['external_attempt']);private_directory(root);private_directory(root/'work')
    runtime_body=ordinary(root/'work/RUNTIME_OBSERVED.json',65536)
    ctx=context({'source_lock_sha256':selected_source_lock_sha256,'runtime_sha256':pin(runtime_body)['sha256'],
                 'identity_sha256':IDENTITY_PIN['sha256'],'attempt_identity':trusted_config['attempt_identity'],
                 'input_sha256':MASTER_PIN['sha256']})
    require(not (root/'work/FAILURE.json').exists(),'no overriding worker failure')
    raw=ordinary(root/'OWNED_REFERENCE.json',65536)
    require(pin(raw)==selected_descriptor_pin,'independently selected owner descriptor, never candidate hash')
    descriptor=json.loads(raw)
    keys(descriptor,{'schema','source_context','files','worker_result_pin','owner_result_pin','requires_independent_original_outcome_selection','source_closed','worker_natural_zero'})
    require(descriptor['schema']=='tms_authentic_interval_owned_reference_v1'
            and descriptor['requires_independent_original_outcome_selection'] is True
            and descriptor['source_closed'] is True and descriptor['worker_natural_zero'] is True,'owner reference lifecycle scope')
    require(context(descriptor['source_context'])==ctx,'operator-selected context')
    keys(descriptor['files'],{'REFERENCE.private.json','SUPPORT.private.bin'})
    owner_raw=ordinary(root/'LAUNCH_RESULT.json',65536);worker_raw=ordinary(root/'work/RESULT.json',65536)
    require(pin(owner_raw)==descriptor['owner_result_pin'] and pin(worker_raw)==descriptor['worker_result_pin'],'exact original owner and worker result pins')
    owner=json.loads(owner_raw);worker=json.loads(worker_raw)
    require(owner.get('status')=='COMPLETED_AUTHENTIC_INTERVAL_REFERENCE_ONLY' and type(owner.get('returncode')) is int and owner['returncode']==0
            and owner.get('reaped') is True and owner.get('owned_group_absent') is True
            and owner.get('regular_capture_files_closed') is True and owner.get('complete_stream_capture_after_owner_closure') is True
            and owner.get('errors')==[] and owner.get('signals')==[] and owner.get('timed_out') is False,'complete source owner closure')
    require(worker.get('status')=='AUTHENTIC_INTERVAL_REFERENCE_COMPLETE' and context(worker.get('source_context'))==ctx
            and worker.get('source_closed') is True and worker.get('input_hash_authenticated') is True
            and worker.get('deadline_admitted_before_receipt') is True,'complete authentic producer closure')
    cleanup=worker.get('reader_cleanup')
    require(type(cleanup) is list and len(cleanup)==4,'complete four-resource reader closure record')
    for expected_role,row in zip(('slab','file','stream','fd'),cleanup):
        keys(row,{'role','attempted','close_returned','observed_closed','errors'})
        require(row['role']==expected_role and type(row['role']) is str and row['attempted'] is True
                and row['close_returned'] is True and row['observed_closed'] is True
                and type(row['errors']) is list and row['errors']==[],'independent clean reader-resource closure')
    require(owner.get('source_lock_sha256')==ctx['source_lock_sha256'] and worker.get('runtime_sha256')==ctx['runtime_sha256'],'source/runtime receipt joins')
    for key,number in [('channel_slabs',248),('group_vectors',97216),('scalar_contrasts',48608),('supplied_raw_entries',1458240),('map_slots',248),('support_entries',97216)]:
        require(type(worker.get(key)) is int and worker[key]==number,'complete actual producer census')
    certificate=ordinary(root/'work/REFERENCE.private.json',262144)
    support=ordinary(root/'work/SUPPORT.private.bin',SUPPORT_BYTES)
    admitted=admit_bytes(certificate,support,expected_certificate=descriptor['files']['REFERENCE.private.json'],
                         expected_support=descriptor['files']['SUPPORT.private.bin'],identity_body=identity_body,owned_context=ctx)
    return OperatorReference(admitted,dict(selected_descriptor_pin),ctx,_TOKEN)


def require_operator_reference(value):
    require(type(value) is OperatorReference and value._token is _TOKEN,'trusted post-review capture required')
    return value.admitted
