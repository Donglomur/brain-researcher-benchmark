"""Concrete host observation, provisional sealing, and separate external admission.

No process, filesystem, protected operand or provider is touched at import.
"""
import hashlib
import os
import re
from pathlib import Path
import stat
import time
import common as c
from native import Bridge
from transport.process import ProcessObserver

class PhaseObservationFailure(RuntimeError):
    def __init__(self,message,evidence):super().__init__(message);self.evidence=evidence

PHASES=('fixed-authors','references','release','analysts','grade')
SPEC_FIELDS=('phase','source','source_files','public_inputs','request','child_authority','python','entry','cwd','env','seconds','cleanup_seconds','stream_cap','output_manifest_path','output_manifest_cap','child_output_root','expected_artifacts','provider_config','credential_names','original_origin','original_deadline')

def spec_document(spec,budget):
    c.exact(spec,SPEC_FIELDS);c.need(spec['phase']in PHASES,'one exact source-owned phase')
    for k in ('source','request','child_authority','python','entry'):c.descriptor(spec[k])
    c.need(type(spec['source_files'])is list and spec['source_files'] and type(spec['public_inputs'])is list,'explicit source/public input lists')
    c.need(type(spec['credential_names'])is list,'declared credential name list')
    if spec['phase']in('fixed-authors','analysts'):
        c.descriptor(spec['provider_config']);c.need(len(spec['credential_names'])==1,'one selected provider credential')
        name=spec['credential_names'][0]
        c.need(type(name)is str and re.fullmatch('[A-Z][A-Z0-9_]{0,63}',name)and not name.startswith(('PYTHON','LD_','DYLD_'))and name not in('PATH','HOME','SHELL','ENV','BASH_ENV','IFS','TMPDIR','LANG','LC_ALL'),'credential name cannot override interpreter/system environment')
    else:c.need(spec['provider_config']is None and spec['credential_names']==[],'no provider credentials for nonprovider phase')
    paths={}
    for d in [spec[k]for k in('source','request','child_authority','python','entry')]+spec['source_files']+spec['public_inputs']+([]if spec['provider_config']is None else[spec['provider_config']]):
        c.descriptor(d);c.need(d['path']not in paths or c.typed_equal(paths[d['path']],d),'consistent immutable descriptor');paths[d['path']]=d
    c.need(len({d['path']for d in spec['source_files']})==len(spec['source_files']),'unique complete source closure')
    c.need(any(c.typed_equal(d,spec['entry'])for d in spec['source_files']),'entry is one exact captured source')
    c.need(Path(spec['source']['path']).name=='SOURCE_MANIFEST.json' and Path(spec['entry']['path']).name=='entry.py','literal source-owned entry and manifest')
    c.need(Path(spec['source']['path']).parent==Path(spec['entry']['path']).parent,'same exact program closure')
    c.need(type(spec['env'])is dict and spec['env']=={'PATH':'/usr/bin:/bin','PYTHONDONTWRITEBYTECODE':'1'},'fixed clean child environment')
    c.absolute(spec['cwd']);root=c.absolute(spec['child_output_root']);manifest=c.absolute(spec['output_manifest_path'])
    c.need(manifest.is_relative_to(root)and manifest!=root,'source-owned child manifest inside output root')
    c.integer(spec['stream_cap'],1);c.integer(spec['output_manifest_cap'],1)
    for k in ('seconds','cleanup_seconds'):c.need(c.finite(spec[k],0)>0,'positive preselected phase interval')
    c.need(type(spec['original_origin'])is float and spec['original_origin']==float(budget.origin)and type(spec['original_deadline'])is float and spec['original_deadline']==float(budget.end),'unchanged original clock identity')
    c.need(type(spec['expected_artifacts'])is list and spec['expected_artifacts'],'complete explicit output roster')
    out=set()
    for row in spec['expected_artifacts']:
        c.exact(row,('path','max_bytes','kind'));p=c.absolute(row['path']);c.integer(row['max_bytes'],0)
        c.need(p.is_relative_to(root)and p!=root and p!=manifest and str(p)not in out,'unique confined output artifact')
        c.need(type(row['kind'])is str and row['kind'],'source-owned artifact role');out.add(str(p))
    return paths

def environment_binding(spec,request_raw,child_authority_raw,provider_raw):
    """Pure public-metadata join. This function never reads an environment value."""
    child=c.parse(child_authority_raw)
    c.need(c.typed_equal(child.get('credential_names'),spec['credential_names'])and c.typed_equal(child.get('provider_config'),spec['provider_config']),'protected child authority selects the same credential names/provider')
    if spec['phase']in('fixed-authors','analysts'):
        request=c.parse(request_raw);provider=c.parse(provider_raw)
        nested=request['payload']['analyst_config']['provider']
        c.need(c.typed_equal(nested,spec['provider_config']),'actual worker request selects exact provider artifact')
        c.need(type(provider)is dict and provider.get('api_key_env')==spec['credential_names'][0],'provider requests the exact declared credential name')
    else:c.need(provider_raw is None,'no provider body for nonprovider phase')

def child_environment(spec):
    """Only called after all source/request/authority/input gates; never serialized."""
    result=dict(spec['env'])
    for name in spec['credential_names']:
        value=os.environ.get(name)
        c.need(type(value)is str and 0<len(value)<=16384 and '\x00'not in value,'selected provider credential unavailable or invalid; value withheld')
        result[name]=value
    return result

def literal_argv(spec,budget):
    return [spec['python']['path'],'-I','-B',spec['entry']['path'],'--phase',spec['phase'],
            '--source-bytes',str(spec['source']['bytes']),'--source-sha256',spec['source']['sha256'],
            '--request',spec['request']['path'],'--request-bytes',str(spec['request']['bytes']),'--request-sha256',spec['request']['sha256'],
            '--authority',spec['child_authority']['path'],'--authority-bytes',str(spec['child_authority']['bytes']),'--authority-sha256',spec['child_authority']['sha256'],
            '--origin',repr(float(budget.origin))]

def natural(observation,argv,budget):
    o=observation;c.need(type(o)is dict and c.typed_equal(o.get('argv'),argv),'exact observed argv')
    c.need(o.get('schema')=='neural053_host_process_observation_v3','unchanged original host observer schema')
    c.integer(o.get('pid'),1);c.integer(o.get('process_group'),1);c.need(o['pid']==o['process_group'],'observed new-session group leader')
    identity=o.get('leader_identity');c.need(type(identity)is dict and identity.get('state')=='present','original admitted leader identity')
    for key in ('pid','parent_pid','process_group','session'):c.integer(identity.get(key),1)
    c.integer(identity.get('birth_ticks'),0)
    c.need(identity['pid']==identity['process_group']==identity['session']==o['pid'],'same initial owned leader/session identity')
    for k in ('natural_exit_code','observed_leader_exit_code'):c.need(type(o.get(k))is int and o[k]==0,'strict original natural integer-zero exit')
    for k in ('process_reaped','process_group_absent','streams_closed','observer_selector_closed'):c.need(o.get(k)is True,'complete host observation '+k)
    c.need(o.get('stream_eof_observed')=={'stdout':True,'stderr':True} and all(type(x)is bool for x in o['stream_eof_observed'].values()),'two genuine stream EOFs')
    c.need(o.get('child_mutation_attempted')is False and o.get('failure')is None and o.get('quarantine_token')is None and o.get('separate_authorized_inspection_required')is False,'no mutation, cleanup-to-success or unknown child')
    group=o.get('group_observation');c.need(type(group)is dict and group.get('state')=='absent'and group.get('members')==[] and group.get('complete_scan')is True,'independent read-only absent group')
    start=c.finite(o.get('started_monotonic'),0);end=c.finite(o.get('ended_monotonic'),0);normal=c.finite(o.get('normal_deadline_monotonic'),0);whole=c.finite(o.get('original_deadline_monotonic'),0)
    c.need(float(budget.origin)<=start<=end<=normal<=whole==float(budget.end),'same original clock and on-time observed closure')
    return o

def phase_natural(observation,spec,budget):
    natural(observation,literal_argv(spec,budget),budget)
    expected=min(observation['started_monotonic']+spec['seconds'],float(budget.end)-spec['cleanup_seconds'])
    c.need(observation['normal_deadline_monotonic']==expected,'selected original phase normal endpoint')
    return observation

def stream_join(raw,entry):
    c.need(type(raw)is bytes and type(entry)is dict,'raw original stream and observation')
    for k in ('bytes','retained_bytes'):c.need(type(entry.get(k))is int and entry[k]==len(raw),'complete stream extent')
    h=hashlib.sha256(raw).hexdigest();c.need(entry.get('sha256')==h and entry.get('retained_sha256')==h,'complete original stream identity')

def fresh_manifest(path,cap,budget,root):
    p=c.within(path,[root]);st=p.lstat();c.need(stat.S_ISREG(st.st_mode)and st.st_nlink==1 and 0<st.st_size<=cap,'bounded ordinary child manifest')
    # Read bounded original bytes, never reconstruct a hash from a replacement object.
    budget.charge('read_bytes',cap+1);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        before=os.fstat(fd);parts=[];n=0
        while n<=cap:
            b=os.read(fd,min(65536,cap+1-n))
            if not b:break
            parts.append(b);n+=len(b);budget.check_clock()
        after=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        c.need(all(getattr(st,k)==getattr(before,k)==getattr(after,k)==getattr(named,k)for k in fields)and n==st.st_size,'stable complete child manifest')
    finally:os.close(fd)
    raw=b''.join(parts);budget.check_clock();return {'path':str(p),**c.pin(raw)},c.parse(raw)

def hash_artifact(d,budget,root,max_bytes):
    c.descriptor(d,allow_empty=True);c.need(d['bytes']<=max_bytes,'preselected output extent ceiling');p=c.within(d['path'],[root]);budget.charge('read_bytes',d['bytes']+1)
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        a=os.fstat(fd);c.need(stat.S_ISREG(a.st_mode)and a.st_nlink==1 and a.st_size==d['bytes'],'ordinary exact output artifact')
        h=hashlib.sha256();n=0
        while n<=d['bytes']:
            b=os.read(fd,min(1048576,d['bytes']+1-n))
            if not b:break
            n+=len(b);h.update(b);budget.check_clock()
        z=os.fstat(fd);named=p.lstat();fields=('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_mode','st_nlink')
        c.need(all(getattr(a,k)==getattr(z,k)==getattr(named,k)for k in fields)and n==d['bytes']and h.hexdigest()==d['sha256'],'whole stable output artifact identity')
    finally:os.close(fd)
    budget.check_clock()

def admit_output_manifest(value,spec,budget,root):
    c.exact(value,('schema','phase','source','request','original_origin','original_deadline','artifacts'))
    c.need(value['schema']=='neural010-observed-phase-output-v1'and value['phase']==spec['phase'],'exact phase output')
    for k in ('source','request','original_origin','original_deadline'):c.need(c.typed_equal(value[k],spec[k]),'phase source/request/clock '+k)
    artifacts=value['artifacts'];expected=spec['expected_artifacts']
    c.need(type(artifacts)is list and len(artifacts)==len(expected),'complete phase output roster')
    for actual,wanted in zip(artifacts,expected):
        c.exact(actual,('path','bytes','sha256','kind'));c.need(type(actual['kind'])is str and actual['kind']==wanted['kind']and actual['path']==wanted['path'],'ordered exact artifact role/path')
        hash_artifact({k:actual[k]for k in('path','bytes','sha256')},budget,root,wanted['max_bytes'])
    return artifacts

def retain_failure_streams(evidence,directory,budget,stream_cap):
    c.need(type(evidence)is dict,'original failure observation')
    values=evidence.get('retained_failure_streams_hex')
    c.need(type(values)is dict and set(values)=={'stdout','stderr'},'original retained failure stream fields')
    out={};total=0;all_full=True
    for name in ('stdout','stderr'):
        value=values[name];c.need(type(value)is str and len(value)%2==0 and len(value)<=2*stream_cap and all(x in '0123456789abcdef'for x in value),'bounded original failure stream encoding')
        raw=bytes.fromhex(value);total+=len(raw);c.need(total<=stream_cap,'aggregate retained failure stream bound')
        d=evidence['streams'][name];c.need(type(d.get('bytes'))is int and type(d.get('retained_bytes'))is int and d['bytes']>=d['retained_bytes']==len(raw)and d['retained_sha256']==hashlib.sha256(raw).hexdigest(),'retained original failure buffer identity')
        full=d['bytes']==len(raw)and d['sha256']==d['retained_sha256']and evidence['stream_eof_observed'].get(name)is True
        all_full=all_full and full
        out[name]=c.publish(directory/('failed_'+name+'.bin'),raw,budget)
    c.need(type(evidence.get('failure_streams_complete'))is bool and evidence['failure_streams_complete']==all_full,'honest complete-versus-partial failure buffers')
    return {'streams':out,'complete':all_full,'natural_closure':False}

def observe_phase(spec,*,budget,authority,capture_roots,output_root):
    # Independent qualification and exact spec binding precede launch and artifacts.
    c.source_authority(authority,spec.get('source'))
    c.need(c.typed_equal(authority.get('observation_spec'),c.pin(c.encoded(spec))),'independently selected exact phase observation')
    selected=spec_document(spec,budget);roots=[c.absolute(str(r))for r in capture_roots]
    directory=c.new_directory(output_root,budget);c.sync_directory(directory)
    argv=literal_argv(spec,budget);record={'schema':'neural010-independent-phase-observation-v1','phase':spec['phase'],'spec':c.pin(c.encoded(spec)),'source':spec['source'],'request':spec['request'],'argv':argv,'original_origin':float(budget.origin),'original_deadline':float(budget.end),'status':'entered','observer_own_exit':'not_yet_independently_observed','qualification_created':False,'declared_environment':dict(spec['env']),'credential_names':list(spec['credential_names']),'provider_config':spec['provider_config']}
    intent=c.publish_json(directory/'INTENT.json',record,budget);record['intent']=intent
    result=None
    try:
        captured={}
        wanted={spec['request']['path'],spec['child_authority']['path']}
        if spec['provider_config']is not None:wanted.add(spec['provider_config']['path'])
        for d in selected.values():
            raw=c.capture(d,budget,roots)
            if d['path']in wanted:captured[d['path']]=raw
        environment_binding(spec,captured[spec['request']['path']],captured[spec['child_authority']['path']],None if spec['provider_config']is None else captured[spec['provider_config']['path']])
        actual_env=child_environment(spec)
        budget.charge('host_processes',1)
        result=ProcessObserver().run(argv,cwd=spec['cwd'],env=actual_env,budget=Bridge(budget),seconds=spec['seconds'],cleanup_seconds=spec['cleanup_seconds'],stream_cap=spec['stream_cap'])
        # Retain original successful raw streams before any post-child admission can fail.
        stdout=c.publish(directory/'stdout.bin',result['stdout'],budget);stderr=c.publish(directory/'stderr.bin',result['stderr'],budget)
        observation_pin=c.publish_json(directory/'CHILD_OBSERVATION.json',result['observation'],budget)
        record.update(stdout=stdout,stderr=stderr,child_observation=observation_pin,observation=result['observation'])
        phase_natural(result['observation'],spec,budget)
        for name in ('stdout','stderr'):stream_join(result[name],result['observation']['streams'][name])
        for d in selected.values():c.capture(d,budget,roots)
        childroot=c.absolute(spec['child_output_root'])
        manifest_pin,manifest=fresh_manifest(spec['output_manifest_path'],spec['output_manifest_cap'],budget,childroot)
        artifacts=admit_output_manifest(manifest,spec,budget,childroot)
        record.update(status='provisional_child_complete',output_manifest=manifest_pin,artifacts=artifacts,raw_streams_complete=True,child_natural_completion=True,observer_own_exit='requires_separate_root_natural_exit',cost_snapshot=budget.snapshot())
        receipt=c.publish_json(directory/'OBSERVATION.json',record,budget);budget.check_clock()
        return {'receipt':receipt,'body':record,'complete_release_or_grade_authorized':False}
    except BaseException as error:
        record.update(status='failed_or_interrupted',failure_type=type(error).__name__,original_failure_evidence=getattr(error,'evidence',None),child_natural_completion=False,unknown_survivors=True,cost_snapshot=budget.snapshot())
        if result is None:
            record['raw_failure_streams']='original bounded failure buffers preserved when available; no completion inferred'
            evidence=getattr(error,'evidence',None)
            if type(evidence)is dict and 'retained_failure_streams_hex'in evidence:
                try:record['retained_failure_streams']=retain_failure_streams(evidence,directory,budget,spec['stream_cap'])
                except BaseException as stream_error:record['failure_stream_publication_uncertain']=type(stream_error).__name__
            else:record['failure_stream_bodies_unavailable']=True
        else:
            record['raw_failure_streams']='exact returned bounded buffers retained below; publication failure remains uncertain'
            if all(type(result.get(n))is bytes for n in ('stdout','stderr'))and sum(len(result[n])for n in ('stdout','stderr'))<=spec['stream_cap']:
                record['original_returned_streams_hex']={n:result[n].hex()for n in ('stdout','stderr')}
            else:record['returned_stream_retention_uncertain']=True
        try:c.publish_json(directory/'FAILURE.json',record,budget)
        except BaseException:record['failure_publication_uncertain']=True
        raise PhaseObservationFailure('phase failed; original evidence retained, no complete admission',record)from error

def admit_external_closure(receipt,external,*,expected_spec,receipt_descriptor,budget,external_authority):
    """Protected caller supplies separately authenticated root authority and body.

This validates identities; it does not create the authority or certify its own
future process exit. No protected assessment/key operand is opened here.
"""
    c.descriptor(receipt_descriptor)
    c.need(c.pin(c.encoded(receipt))=={k:receipt_descriptor[k]for k in('bytes','sha256')},'exact provisional receipt body')
    c.exact(external_authority,('schema','external_body','observer_argv','observer_source','observer_request','receipt','original_origin','original_deadline','phase'))
    c.need(external_authority['schema']=='neural010-root-external-observer-authority-v1','separate protected root authority type')
    for key in ('observer_source','observer_request'):c.descriptor(external_authority[key])
    c.need(c.typed_equal(external_authority['observer_source'],expected_spec['source']),'same complete externally observed program source')
    c.need(c.typed_equal(external_authority['external_body'],c.pin(c.encoded(external))),'exact independently issued external body pin')
    c.need(c.typed_equal(external_authority['receipt'],receipt_descriptor),'root-selected observer receipt')
    for k in ('phase','original_origin','original_deadline'):c.need(c.typed_equal(external_authority[k],expected_spec[k]),'external authority phase/original clock')
    c.exact(external,('schema','observer_source','observer_request','receipt','stdout','stderr','observation'))
    c.need(external['schema']=='neural010-root-observer-exit-v1','independent root exit schema')
    for k in ('observer_source','observer_request','receipt'):c.need(c.typed_equal(external[k],external_authority[k]),'external exact '+k)
    c.exact(receipt,('schema','phase','spec','source','request','argv','original_origin','original_deadline','status','observer_own_exit','qualification_created','declared_environment','credential_names','provider_config','intent','stdout','stderr','child_observation','observation','output_manifest','artifacts','raw_streams_complete','child_natural_completion','cost_snapshot'))
    receipt_root=Path(receipt_descriptor['path']).parent
    c.need(Path(receipt_descriptor['path']).name=='OBSERVATION.json','fixed provisional receipt name')
    for key,name in (('stdout','stdout.bin'),('stderr','stderr.bin'),('child_observation','CHILD_OBSERVATION.json'),('intent','INTENT.json')):
        c.need(receipt[key]['path']==str(receipt_root/name),'confined original observer artifact '+key)
    c.need(receipt['output_manifest']['path']==expected_spec['output_manifest_path'],'exact source-owned child manifest')
    c.need(c.typed_equal(receipt['declared_environment'],expected_spec['env'])and c.typed_equal(receipt['credential_names'],expected_spec['credential_names'])and c.typed_equal(receipt['provider_config'],expected_spec['provider_config']),'receipt declares names/public environment only')
    c.need(receipt['observer_own_exit']=='requires_separate_root_natural_exit'and receipt['qualification_created']is False,'receipt cannot self-certify external completion')
    c.need(receipt.get('schema')=='neural010-independent-phase-observation-v1' and receipt.get('status')=='provisional_child_complete'and receipt.get('raw_streams_complete')is True and receipt.get('child_natural_completion')is True,'provisional complete child, never failure')
    c.need(c.typed_equal(receipt.get('spec'),c.pin(c.encoded(expected_spec))),'same exact phase spec')
    for k in ('phase','source','request','original_origin','original_deadline'):c.need(c.typed_equal(receipt.get(k),expected_spec[k]),'receipt exact '+k)
    spec_document(expected_spec,budget)
    phase_natural(receipt['observation'],expected_spec,budget)
    natural(external['observation'],external_authority['observer_argv'],budget)
    for name in ('stdout','stderr'):
        d=external[name];c.descriptor(d,allow_empty=True);o=external['observation']['streams'][name]
        c.need(type(o.get('bytes'))is int and type(o.get('retained_bytes'))is int and o['bytes']==o['retained_bytes']==d['bytes'] and o['sha256']==o['retained_sha256']==d['sha256'],'external complete raw stream descriptor join')
    c.need(type(receipt['artifacts'])is list and len(receipt['artifacts'])==len(expected_spec['expected_artifacts']),'external complete output roster')
    for a,e in zip(receipt['artifacts'],expected_spec['expected_artifacts']):
        c.exact(a,('path','bytes','sha256','kind'));c.need(a['path']==e['path']and a['kind']==e['kind'],'external exact ordered artifacts');c.descriptor({k:a[k]for k in('path','bytes','sha256')},allow_empty=True);c.need(a['bytes']<=e['max_bytes'],'external artifact bound')
    # Reauthenticate only the explicit admitted public/source and output operands.
    selected=spec_document(expected_spec,budget)
    captured={}
    wanted={expected_spec['request']['path'],expected_spec['child_authority']['path']}
    if expected_spec['provider_config']is not None:wanted.add(expected_spec['provider_config']['path'])
    for d in selected.values():
        raw=c.capture(d,budget,[Path(d['path']).parent])
        if d['path']in wanted:captured[d['path']]=raw
    environment_binding(expected_spec,captured[expected_spec['request']['path']],captured[expected_spec['child_authority']['path']],None if expected_spec['provider_config']is None else captured[expected_spec['provider_config']['path']])
    c.capture(receipt_descriptor,budget,[receipt_root])
    intent=c.parse(c.capture(receipt['intent'],budget,[receipt_root]))
    c.need(intent.get('status')=='entered'and intent.get('schema')==receipt['schema'],'original prelaunch intent')
    for key in ('phase','spec','source','request','argv','original_origin','original_deadline','declared_environment','credential_names','provider_config'):c.need(c.typed_equal(intent.get(key),receipt[key]),'same durable prelaunch intent '+key)
    for name in ('stdout','stderr'):
        for d in (receipt[name],external[name]):c.capture(d,budget,[Path(d['path']).parent],empty=True)
    childbody=c.capture(receipt['child_observation'],budget,[Path(receipt['child_observation']['path']).parent])
    c.need(c.typed_equal(c.parse(childbody),receipt['observation']),'captured original child observation body')
    root=c.absolute(expected_spec['child_output_root'])
    manifest_body=c.capture(receipt['output_manifest'],budget,[root])
    admit_output_manifest(c.parse(manifest_body),expected_spec,budget,root)
    budget.check_clock()
    return {'phase':expected_spec['phase'],'child_and_observer_natural_exit_admitted':True,'receipt':receipt_descriptor,'external_body':external_authority['external_body'],'assessment_or_grade_semantic_gates_still_required':True,'this_admitter_own_future_exit_not_certified':True}
