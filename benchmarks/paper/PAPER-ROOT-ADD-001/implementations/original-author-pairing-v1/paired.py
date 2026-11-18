"""Thin admitted three-role connection to the existing selected task runner.

No alternative executor, supervisor, fit implementation, task ID or source scope.
The reference is operator calibration; the two participant arms remain separate.
Importing this file launches nothing. Every real invocation must use the already
implemented separately qualified fresh-exec provider, including the reference.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

HERE=Path(__file__).resolve().parent
ROLES=('executed_author_reference','paper_data','paper_data_author_code')
FEEDBACK={'development':'globally_frozen_programme_before_final_execution',
          'final_feedback':'none_until_all_roles_closed','cross_case_state':'fresh_exec_per_held_qid'}
PROTOCOL_KEYS={'schema','task_home','store_root','store_sha256','schedule_sha256','source_support_sha256',
 'output_root','roles','common_assets','author_code_assets','feedback','limits','store_read_limit',
 'store_working_limit','extra_read_limit','pairing_working_limit','output_limit','wall_seconds',
 'numpy_version','component_sha256','external_hard_deadline_required','operator_joint_admission_bytes','preflight_tree_read_limit'}
ROLE_KEYS={'role','config','native_admission','design_freeze_sha256','qualification_sha256'}


def need(ok,message):
    if not ok: raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()


def sha(raw): return hashlib.sha256(raw).hexdigest()


def _bootstrap(path, expected, limit):
    """Authenticate the private component before importing its source reader."""
    path=Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)),'No component aliases')
    fd=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
    with os.fdopen(fd,'rb') as stream:
        before=os.fstat(stream.fileno())
        stamp=lambda s:(s.st_dev,s.st_ino,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<before.st_size<=limit,'Bounded ordinary component')
        raw=stream.read(before.st_size+1)
        need(len(raw)==before.st_size and sha(raw)==expected and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.lstat()),'Stable exact component source')
    return raw


def load_component(source_sha256):
    descriptor_raw=_bootstrap(HERE/'SOURCE.json',source_sha256,32768)
    descriptor=json.loads(descriptor_raw)
    need(descriptor.get('schema')=='language-author-pairing-source/v1' and set(descriptor['files'])=={'author_programme.py','executed_reference.py','paired.py'},'Exact three-piece component descriptor')
    bodies={}
    for name,pin in descriptor['files'].items():
        need(set(pin)=={'bytes','sha256'} and type(pin['bytes']) is int and 0<pin['bytes']<=65536,'Bounded source member')
        bodies[name]=_bootstrap(HERE/name,pin['sha256'],65536)
        need(len(bodies[name])==pin['bytes'],'Exact source member extent')
    path=HERE/'executed_reference.py'
    spec=importlib.util.spec_from_file_location('_language_executed_reference',path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    exec(compile(bodies['executed_reference.py'],str(path),'exec'),module.__dict__)
    return module,descriptor


def file_records(records):
    need(type(records) is list and len(records)<=128,'Bounded frozen material set')
    seen=set()
    for row in records:
        need(type(row) is dict and set(row)=={'path','bytes','sha256','mode'} and type(row['path']) is str
             and row['path'] not in seen and not row['path'].startswith('/') and '..' not in Path(row['path']).parts
             and type(row['bytes']) is int and row['bytes']>=0 and row['mode'] in (0o444,0o555), 'Exact unique relative frozen material')
        need(type(row['sha256']) is str and len(row['sha256'])==64 and all(c in '0123456789abcdef' for c in row['sha256']),'Material content hash')
        seen.add(row['path'])
    return sorted(records,key=lambda v:v['path'])


def validate_arm_manifests(p, manifests, source_descriptor):
    """Exact material/budget differences; labels alone are never sufficient."""
    need(tuple(item['role'] for item in p['roles'])==ROLES and set(manifests)==set(ROLES),'Exactly calibration plus two independent participant arms')
    common,code=file_records(p['common_assets']),file_records(p['author_code_assets'])
    need(common and code and not ({v['path'] for v in common}&{v['path'] for v in code}),'Nonempty disjoint common and author-code materials')
    a,b=p['roles'][1:]
    for key in ('caps','provider_source_sha256','bwrap','python_path'):
        need(a['config'][key]==b['config'][key],'Matched participant resource/runtime rule: '+key)
    need(a['config']['runtime']['manifest_sha256']==b['config']['runtime']['manifest_sha256'], 'Same participant runtime contents')
    need(p['feedback']==FEEDBACK,'No fold feedback or persistent cross-case participant state')
    for entry in p['roles']:
        role=entry['role']; config=entry['config']; selected=manifests[role]
        condition='paper_data_author_code' if role=='executed_author_reference' else role
        need(config['condition']==condition,'Distinct role versus transport information label')
        need(set(selected)=={'candidate','assistance'},'Candidate and assistance manifests both authenticated')
        for kind in ('candidate','assistance'):
            doc=selected[kind]
            need(type(doc) is dict and set(doc)=={'schema','kind','condition','directories','files'}
                 and doc['kind']==kind and doc['condition']==condition,'Exact frozen tree role/condition')
            file_records(doc['files'])
        allowed=[] if role=='executed_author_reference' else common if role=='paper_data' else file_records(common+code)
        need(file_records(selected['assistance']['files'])==allowed,'Author code is the only additional participant assistance; calibration private')
        directories=sorted({str(parent) for member in allowed for parent in Path(member['path']).parents if str(parent)!='.'})
        need(selected['assistance']['directories']==directories,'Only declared material directory closure; no extra information-bearing directory names')
        if role=='executed_author_reference':
            recipe=source_descriptor['files']['author_programme.py']
            need(selected['candidate']['files']==[dict(path='candidate.py',bytes=recipe['bytes'],sha256=recipe['sha256'],mode=0o444)],
                 'Only literal historical Ridge programme in reference candidate tree')
            need(selected['candidate']['directories']==[],'No additional reference candidate directories')
    return True


def preflight_trees(p, provider, manifests):
    """Read-only/native-free verification of every role before the first child.

    The existing provider reauthenticates at actual use. These extra traversals
    have their own complete budget, not a subtraction from later provider I/O.
    """
    total=0
    for entry in p['roles']:
        config=entry['config'];meter=provider.Meter(config['caps'])
        # Refuse before a traversal whose maximum could exceed the remaining
        # allocation, including manifest/member reads and the pinned ELF.
        need(total+config['caps']['tree_read_bytes']<=p['preflight_tree_read_limit'],'Whole-role tree preflight allocation before reads')
        for kind in ('runtime','candidate','assistance'):
            fd=None
            try:
                fd,manifest,_=provider.authenticate_tree(config[kind],kind,meter,config['caps']['working_bytes'])
                if kind!='runtime':need(manifest==manifests[entry['role']][kind],'Actual tree matches previously classified material manifest')
                else:
                    need(manifest['condition']=='generic','Shared runtime has no participant condition payload')
                    need({'input','candidate','artifacts','executor','tmp','proc','dev'}<=set(manifest['directories'])
                         and config['python_path'][1:] in {row['path'] for row in manifest['files']},'Declared runtime interpreter and empty mount directories')
                    slots={'input/features.npy','input/responses.bin','input/request.json','executor/entry.py'}
                    slotfiles={row['path']:row for row in manifest['files'] if row['path'].split('/')[0] in {'input','candidate','artifacts','executor','tmp','proc','dev'}}
                    need(set(slotfiles)==slots and all(row['bytes']==0 for row in slotfiles.values()),'Exact empty mount-slot files; no private runtime payload')
            finally:
                if fd is not None:os.close(fd)
        binary=config['bwrap']
        need(4*binary['bytes']+4*1024**2<=config['caps']['working_bytes'],'Executable authentication memory admitted before read')
        raw,_=provider.read_owned(Path(binary['path']),binary['bytes'],binary['sha256'],meter,'tree_read_bytes',executable=True)
        need(raw.startswith(b'\x7fELF'),'Pinned non-setuid native executable profile')
        del raw
        total+=meter.values['tree_read_bytes']
    return total


def validate_protocol(p, admission, r, e, provider, source_sha256, *, now):
    need(type(p) is dict and set(p)==PROTOCOL_KEYS and p['schema']=='language-author-pairing-protocol/v1','Exact selected pairing protocol')
    need(type(admission) is dict and set(admission)=={'schema','protocol_sha256','component_sha256','root_admission_id','expires_unix','wall_seconds'}
         and admission['schema']=='language-author-pairing-admission/v1' and admission['protocol_sha256']==sha(encoded(p))
         and admission['component_sha256']==source_sha256==p['component_sha256']
         and type(admission['root_admission_id']) is str and 0<len(admission['root_admission_id'])<=128,
         'Separate exact root protocol/component admission')
    need(type(p['wall_seconds']) is int and 1<=p['wall_seconds']<=86400 and admission['wall_seconds']==p['wall_seconds']
         and type(admission['expires_unix']) is int and admission['expires_unix']>=now+p['wall_seconds']
         and p['external_hard_deadline_required'] is True,'Finite complete outer deadline, separately enforced by caller')
    for key in ('store_sha256','schedule_sha256','source_support_sha256','component_sha256'):r.digest(p[key])
    need(p['source_support_sha256']=='3d2d46bbc6534b282f97d29c51b1961c8d284cf7a9894839fb851550b7549e37','Exact original source support census')
    need(p['numpy_version']==e.np.__version__,'Frozen original scoring runtime')
    limits=e.limits_snapshot(p['limits'])
    for key in ('store_read_limit','store_working_limit','extra_read_limit','pairing_working_limit','output_limit','preflight_tree_read_limit'):
        need(type(p[key]) is int and 0<p[key]<=2**34,'Finite component allowance: '+key)
    need(256*1024**2<=p['pairing_working_limit']<=1024**3 and p['output_limit']<=16*1024**2,'Bounded pairing memory/output')
    for key in ('task_home','store_root','output_root'):
        need(type(p[key]) is str and Path(p[key]).is_absolute() and not any(x.is_symlink() for x in (Path(p[key]),*Path(p[key]).parents)), 'Ordinary explicit root: '+key)
    roots=[Path(p[k]) for k in ('task_home','store_root','output_root')]
    need(all(x!=y and x not in y.parents and y not in x.parents for i,x in enumerate(roots) for y in roots[i+1:]),'Disjoint source/store/output roots')
    need(not Path(p['output_root']).exists(),'Fresh entire three-role output root')
    need(type(p['roles']) is list and len(p['roles'])==3 and tuple(v.get('role') for v in p['roles'])==ROLES,'Exactly ordered reference/A/B roles')
    for entry in p['roles']:
        need(type(entry) is dict and set(entry)==ROLE_KEYS,'Exact frozen role descriptor')
        r.digest(entry['design_freeze_sha256']);r.digest(entry['qualification_sha256'])
        config=provider.config_snapshot(entry['config'])
        need(config['provider_source_sha256']==provider.identity() and config['store_sha256']==p['store_sha256']
             and config['schedule_sha256']==p['schedule_sha256'] and config['caps']['max_jobs']==42 and config['caps']['max_requests']==5685,
             'All roles use the pinned original fresh-exec42/5685 provider')
        native=provider.admission_snapshot(config,entry['native_admission'])
        need(native['qualification_sha256']==entry['qualification_sha256'] and native['admitted_until_unix']>=admission['expires_unix'], 'Native qualification/admission covers the complete paired envelope')
    # These are additive declared component ceilings, not measured RSS/time.
    joint=3*limits['working_bytes']+limits['cache_working_bytes']+p['store_working_limit']+p['pairing_working_limit']+max(v['config']['caps']['working_bytes'] for v in p['roles'])
    need(type(p['operator_joint_admission_bytes']) is int and joint<=p['operator_joint_admission_bytes']<=2**34,'Explicit additive operator memory admission, not a measured RSS claim')
    need(p['wall_seconds']>=sum(v['config']['caps']['run_seconds']+2*limits['wall_seconds'] for v in p['roles']), 'Complete additive role collection/recovery wall envelope')
    return p


def compare_products(reference, candidate, r):
    import numpy as np
    ref,cand=r.snapshot(reference),r.snapshot(candidate)
    need(ref['role']=='executed_author_reference' and ref['information_condition'] is None
         and cand['role'] in ROLES[1:] and cand['information_condition']==cand['role'],'Calibration cannot become either participant outcome')
    for key in ('store_sha256','schedule_sha256','source_support_sha256','jobs'):
        need(ref[key]==cand[key],'Complete original same-support pairing: '+key)
    need(len(ref['jobs'])==len(ref['scores'])==len(cand['scores'])==42 and sum(v['requests'] for v in ref['jobs'])==5685,'All42jobs/5685callbacks retained')
    need(ref['collection']['sha256']!=cand['collection']['sha256'] and ref['lifecycle']['sha256']!=cand['lifecycle']['sha256']
         and not (set(ref['invocation_groups'])&set(cand['invocation_groups'])),'Distinct completed invocations; no reused reference run as candidate')
    sessions=[]
    def mean(values):return float(np.asarray(values,dtype=np.float64).mean()) if all(v is not None for v in values) else None
    for index in range(14):
        aa,bb=ref['scores'][3*index:3*index+3],cand['scores'][3*index:3*index+3]
        need([v['context'] for v in aa]==[v['context'] for v in bb]==[v['context'] for v in ref['jobs'][3*index:3*index+3]],'Original coordinate order, no matching by favorable subset')
        rv,cv=[v['pearson_r'] for v in aa],[v['pearson_r'] for v in bb]
        need(all(x is None or type(x) in (float,int) and math.isfinite(x) and -1<=x<=1 for x in rv+cv),'Finite original Pearson or explicit null')
        rm,cm=mean(rv),mean(cv);sid=aa[0]['context']['session']
        sessions.append({'session':sid,'person':sid.split('_')[0],'author_lags':rv,'candidate_lags':cv,
                         'author_mean':rm,'candidate_mean':cm,'paired_delta':None if rm is None or cm is None else cm-rm})
    people=[]
    for person in ('p1','p2','p3','p4','p5','p6','p7','p8'):
        own=[v['paired_delta'] for v in sessions if v['person']==person]
        kept=[v['paired_delta'] for v in sessions if v['person']!=person]
        need(own,'All eight original participant clusters')
        people.append({'person':person,'contribution_to_equal_session_delta':float(np.asarray(own,dtype=np.float64).sum()/14) if all(v is not None for v in own) else None,
                       'leave_one_person_out_equal_remaining_session_delta':mean(kept),'remaining_sessions':len(kept)})
    return {'schema':'language-executed-author-paired-delta/v1','condition':cand['role'],
        'reference_role':'executed_author_reference','reference_collection':ref['collection'],
        'candidate_collection':cand['collection'],'sessions':sessions,'participants':people,
        'equal_session_paired_mean_delta':mean([v['paired_delta'] for v in sessions]),
        'historical_numerical_parity_established':False,'scientific_qualification':False,
        'binary_win':None,'minimum_effect':None,'population_inference':None,'current_sota':False,
        'provided_author_reference_replaced':False,'full224_reproduction_executed':False}


def run_pair(p, admission, r, descriptor, source_sha256):
    """Concrete native seam; only a separately admitted future call may execute."""
    e,reader_module,provider_module=r.load_stack(p['task_home'])
    p=validate_protocol(p,admission,r,e,provider_module,source_sha256,now=time.time())
    preflight=r.Meter(p['extra_read_limit']);manifests={}
    for entry in p['roles']:
        manifests[entry['role']]={}
        for kind in ('candidate','assistance'):
            desc=entry['config'][kind];path=Path(desc['manifest'])
            body=r.owned_bytes(path,{'bytes':path.stat().st_size,'sha256':desc['manifest_sha256']},262144,preflight)
            manifests[entry['role']][kind]=r.parse(body)
    validate_arm_manifests(p,manifests,descriptor)
    tree_preflight_bytes=preflight_trees(p,provider_module,manifests)
    provider_module.LinuxBackend.require_platform() # Before target reads/output.
    root=Path(p['output_root']);root.mkdir(mode=0o700)
    deadline=time.monotonic()+p['wall_seconds']; products=[];written=0
    def live():need(time.monotonic()<deadline,'Whole three-role cooperative deadline; caller supplies hard deadline')
    def write(name,value):
        nonlocal written
        raw=encoded(value);need(written+len(raw)<=p['output_limit'],'Cumulative paired receipt allocation')
        with (root/name).open('xb') as stream:stream.write(raw)
        written+=len(raw)
    try:
        for entry in p['roles']:
            live();role=entry['role'];parent=root/role;parent.mkdir(mode=0o700)
            native=reader=None
            try:
                native=provider_module.NativeProvider(entry['config'],entry['native_admission'],evidence_root=parent/'provider')
                reader=reader_module.StoreReader(p['store_root'],expected_store_sha256=p['store_sha256'],read_limit=p['store_read_limit'],working_limit=p['store_working_limit'])
                run=e.J.make_run(store_sha256=p['store_sha256'],candidate_sha256=entry['config']['candidate_sha256'],schedule_sha256=p['schedule_sha256'],
                    provider_source_sha256=entry['config']['provider_source_sha256'],condition=entry['config']['condition'],working_limit=p['limits']['working_bytes'])
                collection,pin=e.collect(reader,native,run,parent/'collection',limits=p['limits']);reader=native=None
                need(collection['provider']['admission']==entry['native_admission'],'Actual collection keeps exact admitted provider')
                live()
                product=r.recover_executed(e,reader_module,run,collection,{'bytes':pin['bytes'],'sha256':pin['sha256']},role,entry['config'],
                    store_root=p['store_root'],output_root=parent/'collection',evidence_root=parent/'provider',store_limit=p['store_read_limit'],
                    store_working=p['store_working_limit'],limits=p['limits'],support_sha256=p['source_support_sha256'],extra_read_limit=p['extra_read_limit'],working_limit=p['pairing_working_limit'])
                live();products.append(product);write(role+'.json',r.snapshot(product))
            finally:e.close_owned(native,reader)
        a,b=(compare_products(products[0],v,r) for v in products[1:])
        left,right=(r.snapshot(v) for v in products[1:])
        need(left['collection']['sha256']!=right['collection']['sha256'] and left['lifecycle']['sha256']!=right['lifecycle']['sha256']
             and not (set(left['invocation_groups'])&set(right['invocation_groups'])),'Independent participant-condition executions')
        report={'schema':'language-author-pairing-result/v1','protocol_sha256':sha(encoded(p)),
          'reference_role':'operator_calibration_not_AI','conditions':[a,b],'jobs':126,'software_callbacks':17055,
          'fresh_exec_invocations_required':17055,'preflight_metadata_bytes':preflight.used,
          'preflight_tree_read_bytes':tree_preflight_bytes,
          'provided_author_reference_untouched':True,'scientific_qualification':False,'binary_win':None,
          'limits':['Original retrospective PCA/centered smoothing and public exposure remain.',
                    'Historical reference parity and independent OS qualification are not inferred from these attributed receipts.',
                    'Participant contributions and leave-one-person-out results are diagnostics; no all-people-win requirement.',
                    'Full224 reproduction and567/579identity correspondence remain separate.'],
          'declared_costs':{'source_reader_traversals':9,'source_reader_read_ceiling_bytes':9*p['store_read_limit'],
             'operator_joint_admission_bytes':p['operator_joint_admission_bytes'],
             'extra_metadata_read_ceiling_bytes':4*p['extra_read_limit'],
             'additional_preflight_tree_read_ceiling_bytes':p['preflight_tree_read_limit'],
             'separate_counters':['collection cache/frozen/dispatched bundles','provider staging/kernel/visible input/journals',
                  'six authority-reader traversals','three packed recovery traversals','per-phase receipts'],
             'pairing_receipt_bytes_before_final':written,'external_hard_deadline_required':True}}
        live();write('PAIR_RESULT.json',report)
        return report
    except BaseException as exc:
        try:write('PAIR_FAILURE.json',{'schema':'language-author-pairing-failure/v1','completed_roles':len(products),'error_type':type(exc).__name__,'error':str(exc)[:512],'complete':False,'scientific_qualification':False})
        except BaseException:pass
        raise


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source-sha256','protocol','protocol-sha256','admission','admission-sha256'):parser.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    r,descriptor=load_component(args.source_sha256)
    meter=r.Meter(524290)
    def read(path,expected):
        path=Path(path);return r.parse(r.owned_bytes(path,{'bytes':path.stat().st_size,'sha256':expected},262144,meter))
    protocol,admission=read(args.protocol,args.protocol_sha256),read(args.admission,args.admission_sha256)
    need(sha(encoded(protocol))==args.protocol_sha256 and sha(encoded(admission))==args.admission_sha256,'Canonical externally pinned protocols')
    print(json.dumps(run_pair(protocol,admission,r,descriptor,args.source_sha256)))


if __name__=='__main__':main()
