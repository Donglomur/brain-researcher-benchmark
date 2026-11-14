"""Admit exact retained N074 engineering metadata; never rerun tests or read fixtures."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import sys
import time

MIB=1048576
SELECTION_PIN={'bytes': 6198, 'sha256': 'e1e1746c236a32418e20febe5368f6885de859b65aec7be4ad2adef23f8ff4f5'}
OWNER_PIN={'bytes': 28864, 'sha256': '234dcf73954abc00dc5ca5a6330097521f5ae560e2429dc779e258236bc334df'}
METHODS=['test_actual_submission_commit_and_separate_evaluation', 'test_late_candidate_disposition_rejected_before_target', 'test_changed_native_prediction_cannot_be_recommitted', 'test_failed_candidate_keeps_complete_roster_and_no_targets', 'test_unclosed_owner_preserves_exact_failure_evidence', 'test_wrong_training_selection_refused_before_workspace_creation', 'test_changed_budget_cannot_keep_the_same_policy_identity', 'test_overlapping_workspace_refused_before_mutation', 'test_changed_target_pin_rejected_at_owner_admission', 'test_reused_context_is_not_a_new_fold', 'test_late_reference_file_tamper_has_zero_target_calls']

def need(ok,why):
    if not ok: raise ValueError(why)

def pin(b):
    return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def encode(x):
    return (json.dumps(x,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()

def stamp(s):
    return tuple(getattr(s,k) for k in
                 ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))

class Admission:
    def __init__(self):
        self.origin=time.monotonic();self.end=self.origin+12.
        self.reserved=0;self.captures=[];self.errors=[];self.first=None;self.raw_errors=[]
    def check(self):
        need(time.monotonic()<self.end,'original metadata admission deadline')
    def fail(self,stage,e):
        if self.first is None:self.first=e
        self.raw_errors.append(e)
        self.errors.append({'stage':stage,'type':type(e).__name__,'message':str(e)[:2048]})
        for secondary in getattr(e,'secondary',()):
            self.raw_errors.append(secondary)
            self.errors.append({'stage':stage+'.close','type':type(secondary).__name__,
                                'message':str(secondary)[:2048]})
    def read(self,path,cap,expected=None):
        self.check()
        need(self.reserved+cap+1<=4*MIB,'cumulative metadata read reservation')
        self.reserved+=cap+1
        row={'path':str(path),'complete':False,'observed_bytes':0,
             'sha256_prefix':hashlib.sha256(b'').hexdigest()}
        self.captures.append(row)
        fd=None;first=None;extra=[];parts=[];h=hashlib.sha256()
        try:
            need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),
                 'ordinary metadata ancestry')
            before=os.lstat(path)
            need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size<=cap,
                 'bounded single-link metadata')
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            need(stamp(os.fstat(fd))==stamp(before),'opened metadata identity')
            left=before.st_size+1
            while left:
                self.check();b=os.read(fd,min(left,65536))
                row['observed_bytes']+=len(b);h.update(b);row['sha256_prefix']=h.hexdigest()
                if not b:break
                parts.append(b);left-=len(b)
            raw=b''.join(parts)
            need(len(raw)==before.st_size and stamp(os.fstat(fd))==stamp(before)==stamp(os.lstat(path)),
                 'stable complete metadata body')
            if expected is not None:need(pin(raw)==expected,'exact metadata identity')
            self.check()
        except BaseException as e:first=e
        if fd is not None:
            closing,fd=fd,None
            try:os.close(closing)
            except BaseException as e:extra.append(e)
        try:self.check()
        except BaseException as e:extra.append(e)
        if first is not None or extra:
            first=first if first is not None else extra.pop(0)
            first.secondary=tuple(extra);raise first
        row.update(complete=True,**pin(raw));return raw
    def publish(self,path,body):
        need(len(body)<=32768,'bounded metadata admission result')
        self.check();fd=None;first=None;extra=[]
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            off=0
            while off<len(body):
                self.check();n=os.write(fd,memoryview(body)[off:])
                need(type(n) is int and n>0,'admission write progress');off+=n
            self.check();os.fsync(fd)
        except BaseException as e:first=e
        if fd is not None:
            closing,fd=fd,None
            try:os.close(closing)
            except BaseException as e:extra.append(e)
        try:self.check()
        except BaseException as e:extra.append(e)
        if first is not None or extra:
            first=first if first is not None else extra.pop(0)
            first.secondary=tuple(extra);raise first
        return {'path':str(path),**pin(body)}

def verify(a,stage,base,owner_outcome):
    need(owner_outcome=='success','actual CI owner step must have succeeded')
    selected=json.loads(a.read(base/'controls/ENGINEERING_SELECTION.json',32768,SELECTION_PIN))
    need(selected['methods']==METHODS and selected['attempts']==1 and
         selected['native_scientific_execution'] is False,'exact selected controls')
    owner=json.loads(a.read(stage/'outer/SUPERVISOR.json',131072))
    control_raw=a.read(stage/'child/CONTROL_RESULT.json',3*MIB)
    control=json.loads(control_raw)
    stdout=a.read(stage/'outer/stdout.prefix',65536)
    stderr=a.read(stage/'outer/stderr.prefix',65536)
    attempt=json.loads(a.read(stage/'outer/ATTEMPT.json',16384))
    need(owner['schema']=='n074_public_operator_actual_engineering_supervisor_v1' and
         owner['group']=='all11' and owner['maximum_attempts']==1 and
         owner['automatic_retry'] is False and owner['native_or_scientific_execution'] is False,
         'exact original owner identity')
    need(owner['prepublication_success'] is True and owner['child_started'] is True and
         owner['natural_exit_observed'] is True and owner['returncode']==0 and
         owner['group_absent'] is True and owner['forced_kill_attempted'] is False and
         owner['streams_eof']=={'stdout':True,'stderr':True} and owner['errors']==[] and
         owner['first_error_type'] is None,'original child and cleanup closure')
    child_owner=owner['child_owner']
    need(child_owner['state']=='reaped' and child_owner['signal_authority'] is False and
         child_owner['stop_attempted'] is False and child_owner['raw_wait_status']==0 and
         child_owner['returncode']==0 and child_owner['group_probe']=='absent' and
         child_owner['signal_operations']==[],'exact sole wait and retired signal authority')
    origin=owner['original_monotonic_start']
    need(type(origin) is float and math.isfinite(origin) and
         owner['original_monotonic_end']==origin+180. and
         owner['actor_deadline']==origin+179. and owner['child_original_deadline']==origin+175.,
         'original clocks')
    need(owner['attempt_transfer_charge']==1024*MIB and owner['retained_envelope']==32*MIB and
         owner['combined_stream_cap']==65536 and owner['combined_observed_stream_bytes']<=65536,
         'original source-selected whole envelope')
    need(owner['captured_child_body']=={k:selected['launcher'][k] for k in ('bytes','sha256')},
         'captured child identity')
    charge=3*(SELECTION_PIN['bytes']+1)+OWNER_PIN['bytes']+1+selected['launcher']['bytes']+1
    charge+=sum(r['bytes']+1 for r in selected['modules'])
    need(owner['source_read_bytes']==charge and charge<=2*MIB,'exact source admission')
    argv=owner['argv']
    need(len(argv)==15 and argv[1:4]==['-I','-S','-B'] and
         argv[4]==str(base/'controls/run_controls.py') and
         argv[5:]==['--selection',str(base/'controls/ENGINEERING_SELECTION.json'),
                    '--selection-bytes',str(SELECTION_PIN['bytes']),
                    '--selection-sha256',SELECTION_PIN['sha256'],
                    '--source-root',str(base),'--output',str(stage/'child')],
         'literal unchanged caller')
    need(attempt['argv']==argv and attempt['original_monotonic_start']==origin and
         attempt['original_monotonic_end']==origin+180.,'same original attempt')
    for role,raw in [('stdout',stdout),('stderr',stderr)]:
        need(owner['prefix_files'][role]=={'path':role+'.prefix',**pin(raw)} and
             owner['observed_stream_bytes'][role]==len(raw) and
             owner['retained_stream_bytes'][role]==len(raw),'complete original stream prefixes')
    need(stderr==b'','no final child error transport')
    terminal=json.loads(stdout)
    need(terminal['schema']=='n074_control_terminal_v1' and terminal['status']=='passed' and
         terminal['counts']=={'passed':11} and terminal['first_error'] is None and
         terminal['later_events']==[] and
         terminal['record']=={'path':str(stage/'child/CONTROL_RESULT.json'),**pin(control_raw)},
         'exact post-publication child terminal')
    need(control['schema']=='n074_operator_engineering_result_v1' and control['status']=='passed' and
         control['scientifically_qualified'] is False and control['native_owner_execution'] is False and
         control['tests_run']==11 and control['counts']=={'passed':11} and
         control['lifecycle_errors']==[] and control['first_error'] is None,
         'complete exact engineering result')
    need([r['method'] for r in control['ordered_tests']]==METHODS and
         all(r['status']=='passed' for r in control['ordered_tests']),'all eleven ordered dispositions')
    need(control['custody']['events']==[] and control['custody']['origin']==origin and
         control['custody']['deadline']==origin+175. and
         control['custody']['observed_maxrss_raw_unit']=='KiB on selected Linux' and
         control['custody']['hard_RSS_bound'] is False,'actual child custody')
    need(control['captured_sources']==[{k:dict(r,path=str(base/r['path']))[k]
          for k in ('module','path','bytes','sha256')} for r in selected['modules']],
         'all twenty captured original task bodies')
    inventory=control['fixture_census']
    need(inventory['complete'] is True and inventory['unseen_extent']==0 and
         inventory['errors']==[] and inventory['files']<=8192 and
         inventory['directories']<=128 and inventory['bytes']<=24*MIB and
         len(inventory['rows'])==inventory['files'],'complete bounded retained fixture census')
    need(all(r['complete'] is True and r['observed_bytes']==r['bytes'] and
             r['sha256']==r['sha256_prefix'] for r in inventory['rows']),
         'known complete fixture hashes; body availability not checked here')
    need(control['runtime']['numpy_version']=='2.4.6' and
         control['runtime']['all_numpy_native_bytes_authenticated'] is False and
         control['runtime']['scientific_environment_parity'] is False,'runtime trust boundary')
    a.check()
    return {'passed':11,'source_admission_bytes':charge,'control_result':pin(control_raw),
            'fixtures_uploaded':False,'artifact_availability_verified':False,
            'scientific_qualification':False}

def main():
    a=Admission();p=argparse.ArgumentParser()
    p.add_argument('--output',required=True);p.add_argument('--owner-outcome',required=True)
    args=p.parse_args();stage=Path(args.output);base=Path(__file__).absolute().parent.parent
    result=None
    try:
        need(stage.is_absolute() and stage.name=='neural074-operator-ci-v1' and
             not any(x.is_symlink() for x in (stage,*stage.parents)),'exact ordinary output')
        result=verify(a,stage,base,args.owner_outcome)
    except BaseException as e:a.fail('admission',e)
    report={'schema':'n074_public_ci_admission_v1','status':'passed' if a.first is None else 'failed',
            'owner_step_outcome':args.owner_outcome,'result':result,'captures':a.captures,
            'errors':a.errors,'snapshot_before_own_publication':True,
            'success_requires_this_step_natural_zero':True,'scientific_qualification':False}
    record=None
    try:
        if stage.is_dir():record=a.publish(stage/'CI_ADMISSION.json',encode(report))
    except BaseException as e:a.fail('report_publication',e)
    try:
        a.check()
        b=encode({'status':'passed' if a.first is None else 'failed','record':record,
                  'errors':a.errors,'result':result})
        need(len(b)<=24576,'finite metadata terminal');sys.stdout.write(b.decode());sys.stdout.flush();a.check()
    except BaseException as e:
        a.fail('final_transport_or_clock',e)
        try:
            b=encode({'status':'failed','evidence_incomplete':True,'errors':a.errors})
            if len(b)<=24576:sys.stderr.write(b.decode());sys.stderr.flush()
        except BaseException:pass
    return 0 if a.first is None else 1

if __name__=='__main__':
    raise SystemExit(main())
