"""Future selected clean offline setup. Never invoked by package preparation.

Reuses the existing bounded stage observer and protected-runner process capture.
This source file is not authorization to build or launch any container.
"""
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import platform
import re
import resource
import signal
import sys
import time
import traceback


def need(ok,code):
    if not ok:raise ValueError(code)


def validate_owner(uid,gid,observed_uid,observed_gid):
    """Bind positive numeric request identities to this real nonroot owner."""
    need(type(uid) is int and type(gid) is int and
         1 <= uid <= 2147483647 and 1 <= gid <= 2147483647,
         'setup_positive_numeric_owner')
    need(type(observed_uid) is int and type(observed_gid) is int and
         uid==observed_uid and gid==observed_gid,'setup_actual_owner_mismatch')
    return str(uid)+':'+str(gid)


def verify_container_user(config,expected_user):
    need(type(config) is dict and type(expected_user) is str and
         type(config.get('User')) is str and config['User']==expected_user,
         'setup_container_user_identity')
    return True


def encoded(v):return (json.dumps(v,indent=2,allow_nan=False)+'\n').encode()


def pin(path):
    p=Path(path);b=p.read_bytes()
    return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}


def save(path,value):
    p=Path(path)
    with p.open('xb') as f:f.write(encoded(value))
    p.chmod(0o600);return pin(p)


def load(name,source):
    p=Path(source);spec=importlib.util.spec_from_file_location(name,p)
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module
    exec(compile(p.read_bytes(),str(p),'exec'),module.__dict__)
    return module


class SetupInterrupted(BaseException):
    """Owner cancellation or active deadline, preserved through owned unwind."""


class ActiveGuard:
    def __init__(self, active_seconds, cleanup_seconds):
        self.active_seconds=active_seconds;self.cleanup_seconds=cleanup_seconds
        self.started=time.monotonic();self.cleanup_started=None;self.events=[];self.previous={};self.installed=False

    def noted(self, signum, _frame):
        self.events.append({'signal':signum,'elapsed_seconds':time.monotonic()-self.started,
                            'phase':'cleanup_or_unwind' if self.cleanup_started is not None else 'active_unwind'})

    def protect_unwind(self):
        if self.installed:
            for sig in self.previous:signal.signal(sig,self.noted)

    def requested(self, signum, frame):
        self.noted(signum,frame);self.protect_unwind()
        raise SetupInterrupted('setup_active_deadline' if signum==signal.SIGALRM else 'setup_cancelled_signal_'+str(signum))

    def __enter__(self):
        for sig in (signal.SIGTERM,signal.SIGINT,signal.SIGALRM):
            self.previous[sig]=signal.getsignal(sig);signal.signal(sig,self.requested)
        self.installed=True;signal.setitimer(signal.ITIMER_REAL,self.active_seconds)
        return self

    def begin_cleanup(self):
        if self.cleanup_started is None:self.cleanup_started=time.monotonic()
        if self.installed:signal.setitimer(signal.ITIMER_REAL,0)
        self.protect_unwind()

    def remaining(self, requested, cleanup=False):
        start=self.cleanup_started if cleanup else self.started
        need(start is not None,'setup_cleanup_not_started')
        left=(self.cleanup_seconds if cleanup else self.active_seconds)-(time.monotonic()-start)
        need(left>0,'setup_cleanup_deadline' if cleanup else 'setup_active_deadline')
        return min(requested,left)

    def __exit__(self,*_):
        if self.installed:
            signal.setitimer(signal.ITIMER_REAL,0)
            for sig,old in self.previous.items():signal.signal(sig,old)
            self.installed=False


def dispatch_record(calls, argv, prefix, callback, stage_path=None):
    """Persist intent before dispatch; exceptional completion stays unobserved."""
    prefix=Path(prefix)
    record={'argv':list(argv),'state':'pending','exit_code':None,'reaped':False,'EOF':[],
            'reason':'dispatch_outcome_unobserved','truncated':None,'stdout':None,'stderr':None}
    calls.append(record)
    record['intent']=save(str(prefix)+'.intent.json',dict(record))
    try:
        returned=callback()
        need(returned['argv']==list(argv),'setup_returned_command_identity')
        record.update(returned);record['state']='returned'
        return record
    except BaseException as exc:
        record['state']='raised';record['exception']={'class':type(exc).__name__,'message':str(exc),
                                                    'traceback':traceback.format_exc()}
        # Partial original streams are evidence, never proof of exit/reap/EOF.
        for name in ('stdout','stderr'):
            path=Path(str(prefix)+'.'+name)
            if path.is_file() and not path.is_symlink():record[name]=pin(path)
        if stage_path is not None and Path(stage_path).is_file():record['original_stage']=pin(stage_path)
        raise
    finally:
        save(str(prefix)+'.outcome.json',dict(record))


def adapt_stage(value, original):
    """Only normalize the adapter EOF list; never mutate original observations."""
    return {'argv':value['argv'],'exit_code':value.get('exit_code'),'reaped':value['child_reaped'],
            'EOF':sorted(value['pipe_EOF']),'reason':value['termination_reason'],
            'truncated':value['termination_reason']=='transcript_budget_margin','original_stage':original,
            'stdout':next(x for x in value['logs'] if x['path'].endswith('.stdout')),
            'stderr':next(x for x in value['logs'] if x['path'].endswith('.stderr'))}


def run(request,request_pin):
    with ActiveGuard(5100,300) as guard:
        return _run(request,request_pin,guard)


def _run(request,request_pin,guard):
    need(type(request) is dict and set(request)=={'schema','source_pins','archive_paths','output_root',
         'name','target_contract','owner_uid','owner_gid'} and request['schema']=='nider_portable_native_setup_request_v2','setup_request')
    kit=Path(__file__).resolve().parents[1]
    required_sources={'owner/owner_package.py','owner/PACKAGE_LOCK.json','configuration/configuration.py','configuration/authoring_gateway.py','configuration/LOCK.json', 'setup/native_setup.py','setup/stage_dependencies.py','setup/stage_observer.py','setup/audit_image_export.py','setup/build_spec.py','setup/install_locked.R','setup/offline_install.sh','setup/runtime_inventory.R','setup/DEPENDENCIES.json', *('runtime/'+n for n in ('custody.py','build_spec.py','runtime_policy.py','reporting_core.py','scientific_score.py','owner_binding.py','protected_runner.py','observe_protected_runner.py','DEPENDENCIES.json'))}
    need(type(request['source_pins']) is dict and set(request['source_pins'])==required_sources,'complete_setup_source_closure')
    for relative,identity in request['source_pins'].items():
        p=kit/relative
        need(not Path(relative).is_absolute() and '..' not in Path(relative).parts and
             not any(x.is_symlink() for x in (p,*p.parents)),'setup_source_path')
        need(pin(p)=={'path':str(p),**identity},'setup_source_identity')
    selected_user=validate_owner(request['owner_uid'],request['owner_gid'],os.geteuid(),os.getegid())
    need(request['target_contract']=='nider-clean-linux-arm64-selected-owner-v2' and
         platform.system()=='Linux' and platform.machine() in ('aarch64','arm64') and
         not any(k in os.environ for k in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH')),
         'setup_actual_clean_target_identity')
    root=Path(request['output_root']);need(root.is_absolute() and not root.exists(),'setup_fresh_root')
    root.mkdir(mode=0o700);(root/'logs').mkdir(mode=0o700)
    owner=load('nider_setup_owner',kit/'owner/owner_package.py')
    cfg,_=owner.configuration(str(kit/'configuration'));modules,_=cfg.load_runtime(str(kit/'runtime'))
    c=modules['custody'];runner=modules['protected_runner'];rp=modules['runtime_policy']
    stage=load('nider_setup_stage',kit/'setup/stage_dependencies.py')
    observer=load('nider_setup_observer',kit/'setup/stage_observer.py')
    auditor=load('nider_setup_auditor',kit/'setup/audit_image_export.py')
    began=guard.started;start_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()
    timing=save(root/'INITIAL_TIMING.json',{'start_utc':start_utc,'base_size_bytes':0})
    calls=[];owned=[];cleaned=[];principals=[];failure=None;image=None;metadata={};plan_pin=None;counter=0
    save(root/'ATTEMPT_GUARD.json',{'request':request_pin,'maximum_attempts':1})

    def small(argv,seconds=10,cleanup=False):
        nonlocal counter
        seconds=guard.remaining(min(seconds,5) if cleanup else seconds,cleanup)
        counter+=1;prefix=root/'logs'/('%03d'%counter)
        record=dispatch_record(calls,argv,prefix,lambda:runner.bounded_process(
            argv,seconds,Path(str(prefix)+'.stdout'),Path(str(prefix)+'.stderr')))
        runner.validate_outcome(record)
        need(sum(p.stat().st_size for p in (root/'logs').iterdir() if p.is_file())<=16777216,'setup_log_cap')
        return record

    def raw(record):return c.read_pin(record['stdout'],maximum=16777216)
    def obj(argv):return c.decode(raw(small(argv)))

    def long(argv,label,seconds,container):
        nonlocal counter
        seconds=guard.remaining(seconds)
        counter+=1;name='%03d-%s'%(counter,label);prefix=root/'logs'/name
        original_path=root/'logs'/(name+'.json')
        def invoke():
            old=sys.argv;capture=io.StringIO()
            sys.argv=[str(kit/'setup/stage_observer.py'),'--external',str(root),'--name',name,
                      '--seconds',str(seconds),'--selection',timing['path'],'--container',container,
                      '--disk-root',str(root),'--',*argv]
            try:
                with contextlib.redirect_stdout(capture):status=observer.main()
            finally:
                sys.argv=old
                with (root/'logs'/(name+'.observer.stdout')).open('x') as f:f.write(capture.getvalue())
            original=pin(original_path);value=c.decode(c.read_pin(original))
            record=adapt_stage(value,original);record['observer_exit_code']=status
            return record
        record=dispatch_record(calls,argv,prefix,invoke,original_path)
        need(record['observer_exit_code']==0,'setup_stage_failure');runner.validate_outcome(record)
        return record

    def create(argv,name,principal=False):
        need(not raw(small(['docker','ps','-aq','--no-trunc','--filter','name=^/'+name+'$'])).strip(),'setup_fresh_container_name')
        slot={'name':name,'cid':None};owned.append(slot)
        record=small(argv);cid=raw(record).decode().strip()
        need(re.fullmatch('[0-9a-f]{64}',cid),'setup_created_CID');slot['cid']=cid
        if principal:principals.append(record)
        return cid

    def verify_created(cid,name,image_id,mounts,memory,cpus,pids,entrypoint,cmd,readonly,expected_user):
        values=obj(['docker','inspect',cid]);need(type(values) is list and len(values)==1,'setup_container_inspection')
        v=values[0];h=v['HostConfig'];conf=v['Config'];state=v['State']
        verify_container_user(conf,expected_user)
        need(v['Id']==cid and v['Image']==image_id and v['Name']=='/'+name and
             conf['Labels'].get('nider.build_owner')==name and conf['Entrypoint']==entrypoint and
             (conf['Cmd']==cmd or cmd==[] and conf['Cmd'] is None) and state['Status']=='created' and not state['Running'], 'setup_container_identity')
        need(h['Memory']==h['MemorySwap']==memory and h['NanoCpus']==cpus and h['PidsLimit']==pids and
             h['NetworkMode']=='none' and h['ReadonlyRootfs'] is readonly and h['LogConfig']['Type']=='none' and
             h['Privileged'] is False and h['UsernsMode']=='','setup_container_resources')
        need({(x['Source'],x['Destination'],x['RW']) for x in v['Mounts'] if x['Type']=='bind'}==mounts and
             all(x['Type'] in ('bind','tmpfs') for x in v['Mounts']),'setup_exact_mounts')
        return save(root/(name+'.created.json'),values)

    try:
        context=obj(['docker','context','inspect']);info=obj(['docker','info','--format','{{json .}}'])
        need(len(context)==1 and context[0]['Endpoints']['docker']['Host']=='unix:///var/run/docker.sock' and
             context[0]['Endpoints']['docker'].get('SkipTLSVerify') is False and info['OSType']=='linux' and
             info['Architecture'] in ('aarch64','arm64') and not any('rootless' in x.lower() or 'userns' in x.lower() for x in info['SecurityOptions']) and
             info['NCPU']>=2 and info['MemTotal']>=8589934592,'setup_live_target_mapping_capacity')
        need(not raw(small(['docker','ps','-q'])).strip(),'setup_clean_target_no_running_containers')
        save(root/'HOST_CONTEXT.json',{'context':context,'info':info,'uname':list(platform.uname()),
                                     'owner_uid':os.geteuid(),'owner_gid':os.getegid()})
        fixed=rp.dependencies();base=obj(['docker','image','inspect',fixed['base']])
        need(len(base)==1 and fixed['base'] in base[0]['RepoDigests'] and base[0]['Os']=='linux' and
             base[0]['Architecture']=='arm64','setup_base_identity')
        metadata['base_image_inspection']=save(root/'BASE_IMAGE.json',base)
        timing=save(root/'BUILD_TIMING.json',{'start_utc':start_utc,'base_size_bytes':base[0]['Size']})
        staging=stage.stage({'schema':'nider_dependency_staging_request_v1','archive_paths':request['archive_paths'],
                             'output_root':str(root/'dependency_stage')})
        save(root/'STAGING.json',staging)
        plan=stage.build_plan(staging,str(root),request['name']);plan_pin=save(root/'BUILD_PLAN.json',plan)
        cid=create(plan['create_argv'],plan['owned_name'],True)
        verify_created(cid,plan['owned_name'],base[0]['Id'],{(staging['root'],'/provision',False)},
                       6442450944,2000000000,256,['/bin/sh'],['/provision/offline_install.sh'],False,base[0]['Config'].get('User',''))
        principals.append(long(plan['start_argv'],'install',4500,plan['owned_name']))
        ended=obj(['docker','inspect','--size',cid]);need(not ended[0]['State']['Running'] and ended[0]['State']['ExitCode']==0 and
             not ended[0]['State']['OOMKilled'] and not ended[0]['State']['Error'],'setup_install_exit')
        commit=small(plan['commit_argv'],seconds=120);principals.append(commit)
        lines=raw(commit).decode().splitlines();ids=[x.strip() for x in lines if re.fullmatch('sha256:[0-9a-f]{64}',x.strip())]
        need(len(ids)==1,'setup_unique_committed_image');image=ids[0]
        inspection=obj(['docker','image','inspect',image]);rp.image_observation(inspection,image)
        metadata['image_inspection']=save(root/'IMAGE.json',inspection)
        timing=save(root/'POSTBUILD_TIMING.json',{'start_utc':start_utc,'base_size_bytes':base[0]['Size']+inspection[0]['Size']+ended[0]['SizeRw']})
        history=raw(small(['docker','image','history','--no-trunc','--format','{{json .}}',image])).splitlines()
        metadata['image_history']=save(root/'HISTORY.json',[c.decode(x) for x in history if x.strip()])
        # One metadata-only R container, never a metacor/native scientific call.
        out=root/'inventory';out.mkdir(mode=0o700);name=request['name']+'-metadata'
        argv=['docker','create','--pull=never','--name',name,'--network=none','--read-only','--cpus=1',
              '--memory=2g','--memory-swap=2g','--pids-limit=64','--log-driver=none','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--user='+selected_user,'--label','nider.build_owner='+name,
              '--tmpfs=/tmp:rw,nosuid,nodev,size=134217728,mode=1777',
              '--mount','type=bind,src='+str(kit/'setup/runtime_inventory.R')+',dst=/inventory.R,readonly',
              '--mount','type=bind,src='+str(kit/'setup/DEPENDENCIES.json')+',dst=/dependencies.json,readonly',
              '--mount','type=bind,src='+str(out)+',dst=/out',
              '--entrypoint=/usr/local/bin/Rscript',image,'--vanilla','/inventory.R','/dependencies.json',image,'/out/RUNTIME_INVENTORY.json']
        metadata_cid=create(argv,name)
        verify_created(metadata_cid,name,image,{(str(kit/'setup/runtime_inventory.R'),'/inventory.R',False),
                       (str(kit/'setup/DEPENDENCIES.json'),'/dependencies.json',False),(str(out),'/out',True)},
                       2147483648,1000000000,64,['/usr/local/bin/Rscript'],
                       ['--vanilla','/inventory.R','/dependencies.json',image,'/out/RUNTIME_INVENTORY.json'],True,selected_user)
        long(['docker','start','-a',metadata_cid],'metadata',300,name)
        need((out/'RUNTIME_INVENTORY.json').stat().st_size<=1048576,'setup_inventory_extent')
        metadata['runtime_inventory']=pin(out/'RUNTIME_INVENTORY.json')
        # Export a separate never-started, mount-free container of that image.
        name=request['name']+'-export'
        argv=['docker','create','--pull=never','--name',name,'--network=none','--read-only','--cpus=1',
              '--memory=512m','--memory-swap=512m','--pids-limit=16','--log-driver=none','--cap-drop=ALL',
              '--security-opt=no-new-privileges','--user='+selected_user,'--label','nider.build_owner='+name,
              '--entrypoint=/bin/true',image]
        export_cid=create(argv,name)
        verify_created(export_cid,name,image,set(),536870912,1000000000,16,['/bin/true'],[],True,selected_user)
        exported=root/'IMAGE_FILESYSTEM.tar'
        small(['docker','export','--output',str(exported),export_cid],seconds=180)
        staged_names=[str(p.relative_to(root/'dependency_stage')) for p in (root/'dependency_stage').rglob('*') if p.is_file()]
        for entry in staging['files']:
            need(pin(root/'dependency_stage'/entry['path'])=={'path':str(root/'dependency_stage'/entry['path']),
                 'bytes':entry['bytes'],'sha256':entry['sha256']},'setup_staging_postidentity')
        audit=auditor.audit(exported,image,rp.DEPENDENCIES_SHA256,plan_pin['sha256'],rp.FORBIDDEN_ASSET_SHA256S,
                            staged_names,[x['path'] for x in fixed['expected_staging_files']])
        metadata['filesystem_audit']=save(root/'FILESYSTEM_AUDIT.json',audit)
        private=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
        need(private+base[0]['Size']+inspection[0]['Size']+ended[0]['SizeRw']<=8589934592,'setup_observed_disk_budget')
    except BaseException as exc:
        failure={'class':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
    finally:
        guard.begin_cleanup()
        for slot in reversed(owned):
            try:
                if slot['cid'] is None:
                    body=raw(small(['docker','ps','-aq','--no-trunc','--filter','name=^/'+slot['name']+'$',
                                    '--filter','label=nider.build_owner='+slot['name']],cleanup=True)).decode().strip()
                    if body:
                        need(re.fullmatch('[0-9a-f]{64}',body),'setup_recovery_unique_CID');slot['cid']=body
                if slot['cid'] is None:continue
                identity=c.decode(raw(small(['docker','inspect',slot['cid']],cleanup=True)))
                need(len(identity)==1 and identity[0]['Id']==slot['cid'] and
                     identity[0]['Config']['Labels'].get('nider.build_owner')==slot['name'],'setup_cleanup_owned_identity')
                small(['docker','rm','-f',slot['cid']],cleanup=True)
                by_id=raw(small(['docker','ps','-aq','--no-trunc','--filter','id='+slot['cid']],cleanup=True))
                by_name=raw(small(['docker','ps','-aq','--no-trunc','--filter','name=^/'+slot['name']+'$'],cleanup=True))
                need(not by_id.strip() and not by_name.strip(),'setup_cleanup_absence')
                cleaned.append(dict(slot,removed_and_absence_verified=True))
            except BaseException as exc:
                failure={'class':'SetupCleanupFailure','message':str(exc),'traceback':traceback.format_exc(),'preceding':failure}
        life={'schema':'nider_clean_offline_build_lifecycle_v1','plan_sha256':plan_pin['sha256'] if plan_pin else None,
              'request':request_pin,'image':image,'attempts':1,'exit_code':0 if failure is None else 1,
              'reaped':bool(calls) and all(x['reaped'] is True and x['state']=='returned' for x in calls),'failure':failure,
              'owned_cleanup_verified':all(x['cid'] is None or x['cid'] in {z['cid'] for z in cleaned} for x in owned),
              'pipe_EOF':['stdout','stderr'] if calls and all(set(x['EOF'])=={'stdout','stderr'} and x['state']=='returned' for x in calls) else [],
              'commands':principals,'all_calls':calls,'owned':owned,'cleanup':cleaned,
              'retained_metadata_sha256':[v['sha256'] for v in metadata.values()],
              'elapsed_seconds':time.monotonic()-began,'no_scientific_or_candidate_calls':True,
              'cancellation_events':guard.events,'active_limit_seconds':guard.active_seconds,
              'cleanup_dispatch_limit_seconds':guard.cleanup_seconds,
              'cleanup_elapsed_seconds':time.monotonic()-guard.cleanup_started,
              'host_peak_RSS_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024),
              'limits_note':'Signal-driven5100s active deadline covers host staging/audit as well as children; cleanup admits calls only within300s with5s capture+bounded kill/reap tails. Original events and actual elapsed retained. Metadata preservation adds a finite source-bounded tail; no uninterruptible-OS hard wall guarantee.'}
        lifecycle=save(root/'BUILD_LIFECYCLE.json',life)
    if failure is None:
        evidence={'schema':'nider_clean_dependency_image_evidence_v1','build_plan':plan_pin,
                  'build_lifecycle':lifecycle,**metadata,'setup_lock_sha256':rp.DEPENDENCIES_SHA256,
                  'image':image,'base_manifest':rp.dependencies()['base']}
        evidence_pin=save(root/'IMAGE_EVIDENCE.json',evidence)
        try:rp.image_evidence(evidence_pin,image)
        except BaseException as exc:
            save(root/'EVIDENCE_ADMISSION_FAILURE.json',{'class':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()})
            return 1
        save(root/'RESULT.json',{'image_evidence':evidence_pin,'runtime_policy_not_yet_issued':True,
                                'scientific_qualification':False,'native_route_runs':0})
    return 0 if failure is None else 1


if __name__=='__main__':
    os.umask(0o077);resource.setrlimit(resource.RLIMIT_AS,(2147483648,2147483648));need(len(sys.argv)==3,'setup_request_and_digest')
    p=Path(sys.argv[1]);b=p.read_bytes();need(len(b)<=1048576 and hashlib.sha256(b).hexdigest()==sys.argv[2],'setup_request_identity')
    raise SystemExit(run(json.loads(b),pin(p)))
