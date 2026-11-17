"""Actual parent invocation, full programme child, and interrupted-owner recovery."""
import base64,os,re,signal,sys,time
from pathlib import Path
from .common import *
from .source_loader import Captured
from .owner import NativeOwner
from .cgroup import Cgroup
from . import process

CONFIG_FIELDS=('schema','original_root','program_root','output_root','source_operands','programs','limits','native')
NATIVE_FIELDS=('parent_custody_root','custody_root','cgroup_root','image_id','image_python','device','docker','mount','umount','uid_base','campaign_seconds','cleanup_seconds','controller_read_bytes','controller_write_bytes','controller_native','isolation_read_bytes','isolation_write_bytes','isolation_cleanup_read_bytes','isolation_cleanup_write_bytes','recovery_read_bytes','recovery_write_bytes','work_bytes','work_inodes','proc_metadata_bytes','provider','host_site_packages')
def validate(cfg):
    fields(cfg,CONFIG_FIELDS);need(cfg['schema']=='n090-full-native-request-v1','exact native request');n=fields(cfg['native'],NATIVE_FIELDS)
    for k in('uid_base','campaign_seconds','cleanup_seconds','controller_read_bytes','controller_write_bytes','isolation_read_bytes','isolation_write_bytes','isolation_cleanup_read_bytes','isolation_cleanup_write_bytes','recovery_read_bytes','recovery_write_bytes','work_bytes','work_inodes','proc_metadata_bytes'):integer(n[k],1)
    need(n['uid_base']>=100000 and n['uid_base']+76800<2**31,'whole fresh numeric UID range')
    need(n['cleanup_seconds']>=2 and n['device']=='cpu','explicit supported CPU route and cleanup reserve; GPU not implemented')
    need(type(n['host_site_packages'])is list and len(n['host_site_packages'])<=8,'explicit qualified host scientific package paths')
    p=n['provider'];fields(p,('model','credential','input_tokens','output_tokens','request_bytes','response_bytes','max_calls','input_contract'))
    for k in('input_tokens','output_tokens','request_bytes','response_bytes','max_calls'):integer(p[k],1)
    need(p['request_bytes']<=65536 and p['response_bytes']<=65536,'provider frame fits fixed command custody cap')
    for k in('docker','mount','umount'):
        row=fields(n[k],('path','bytes','sha256'));regular_path(row['path']);integer(row['bytes'],1);need(re.fullmatch('[0-9a-f]{64}',row['sha256'])is not None,'selected executable digest')
    fields(n['controller_native'],('rss_bytes','pids','threads','cpu_seconds'))
    for v in n['controller_native'].values():integer(v,1)
    for k in('original_root','program_root','output_root'):regular_path(cfg[k])
    regular_path(n['parent_custody_root']);regular_path(n['custody_root']);regular_path(n['cgroup_root'])
    return cfg

def runtime(package,budget,selection):
    root=package/'runtime';m=parse(capture(root/'RUNTIME_SOURCE.json',budget,65536,selection['runtime/RUNTIME_SOURCE.json']));Captured(root,m['members'],budget).install();return root

def run_child(cfg,package,selection,timing):
    validate(cfg);n=cfg['native'];account=Budget(n['controller_read_bytes'],n['controller_write_bytes'],timing[2]);root=runtime(package,account,selection)
    for path in n['host_site_packages']:
        p=regular_path(path);s=p.stat();need(s.st_uid==0 and not s.st_mode&0o022,'trusted qualified host environment directory');sys.path.append(str(p))
    from programme.contracts import Asset,Pin
    from broad090.operator import run
    operands={k:Asset.parse(v)for k,v in cfg['source_operands'].items()};programs={k:Asset.parse(v)for k,v in cfg['programs'].items()}
    manifest_body=capture(root/'RUNTIME_SOURCE.json',account,65536);manifest=Asset('RUNTIME_SOURCE.json',Pin.parse(pin(manifest_body)))
    def stop(signum,frame):raise TimeoutError('original enclosing native controller interrupted')
    oldterm=signal.signal(signal.SIGTERM,stop);oldalarm=signal.signal(signal.SIGALRM,stop);signal.setitimer(signal.ITIMER_REAL,max(.001,timing[1]-time.monotonic()))
    owner=None;errors=Ledger();result=None
    try:
        owner=NativeOwner(n,package,cfg['original_root'],cfg['program_root'],cfg['output_root'],selection,timing)
        result=run(owner,cfg['original_root'],operands,root,manifest,programs,cfg['limits'],cfg['output_root'])
    except BaseException as error:errors.record('original-programme',error)
    finally:
        errors.attempt('alarm-disable',lambda:signal.setitimer(signal.ITIMER_REAL,0))
        if owner is not None:errors.attempt('owner-close',owner.close)
        errors.attempt('term-handler-restore',lambda:signal.signal(signal.SIGTERM,oldterm))
        errors.attempt('alarm-handler-restore',lambda:signal.signal(signal.SIGALRM,oldalarm))
    errors.raise_first();return result

def recovery(cfg,package,budget,end):
    """Source-owned intent recovery after child retirement, not Boolean issuance.

    No normal-path deletion of retained capture/source/history. Only exact daemon
    objects, tmpfs mount and cgroup named by owned durable intents are retired.
    """
    n=cfg['native'];root=Path(n['custody_root']);errors=Ledger();observed=[]
    if not root.exists():return {'root_absent':True,'intents':[]}
    private_directory(root)
    campaign=parse(capture(root/'CAMPAIGN.json',budget,4096))['campaign'];need(re.fullmatch('[0-9a-f]{64}',campaign),'exact owned campaign nonce')
    # Use the same command closure implementation, not a second subprocess path.
    host=NativeOwner.__new__(NativeOwner);host.cfg=n;host.root=root;host.end=end;host.command_records=[];host.command_count=1000000000;host.errors=errors
    initial_mounts=errors.attempt('initial-mount-observation',lambda:{line.split()[4]for line in kernel_body('/proc/self/mountinfo',budget,2**20).decode().splitlines()})
    entries,inventory_errors=bounded_names(root,153608,budget)
    for where,error in inventory_errors.events:errors.record('root:'+where,error)
    def recover_one(token):
        if re.fullmatch('[0-9a-f]{64}',token)is None:return
        folder=root/token;private_directory(folder);intent=parse(capture(folder/'INTENT.json',budget,4096))
        need(intent['token']==token and intent['work']==str(folder/'work')and intent['cgroup']==str(Path(n['cgroup_root'])/('n090-'+token)),'exact source-derived native intent')
        if (folder/'CLOSED.json').exists():
            closed=parse(capture(folder/'CLOSED.json',budget,4096));need(closed=={'token':token,'cgroup_empty_removed':True,'tmpfs_unmounted':True,'containers_removed':True},'actual child close record shape')
            need(not Path(intent['cgroup']).exists(),'closed child cgroup absent')
            need(initial_mounts is not None and intent['work']not in initial_mounts,'closed child mount absence must be observed')
            observed.append({'token':token,'normal_closed':True});return
        # Container roster is durable before every create, including unknown ack.
        tools=cfg['limits']['actor']['tool_calls'];pc=n['provider'];models=min(pc['max_calls'],cfg['limits']['actor']['model_tokens']//(pc['input_tokens']+pc['output_tokens']))
        full_entry_cap=6+4*tools+5*models
        all_names,inventory_errors=bounded_names(folder,full_entry_cap,budget)
        for where,error in inventory_errors.events:errors.record(token+':'+where,error)
        names=[x for x in all_names if re.fullmatch(r'CONTAINER-[0-9]+\.json',x)]
        providers=[x for x in all_names if re.fullmatch(r'PROVIDER-[0-9]+\.json',x)]
        def recover_container_intent(name):
            row=parse(capture(folder/name,budget,4096));need(row['token']==token and re.fullmatch('n090-'+token+'-[0-9]+',row['name']),'exact owned container name')
            def retire(row=row):
                listing=host.docker(['ps','-a','--filter','name=^/'+row['name']+'$','--format','{{.ID}}'],end-.1,end,budget)
                if not base64.b64decode(listing['stdout_base64']).strip():return
                obj=parse(base64.b64decode(host.docker(['inspect',row['name']],end-.1,end,budget)['stdout_base64']))[0]
                need(obj['Config']['Labels'].get('n090.invocation')==token and obj['Config']['Labels'].get('n090.campaign')==campaign,'refuse foreign recovery object')
                host.docker(['rm','-f',row['name']],end-.1,end,budget)
            errors.attempt('recovery-container',retire)
        for name in sorted(names):errors.attempt("recover-container-intent:"+name,lambda name=name:recover_container_intent(name))
        cg=Path(intent['cgroup'])
        if cg.exists():
            group=Cgroup(n['cgroup_root'],cg.name,budget,cfg['limits']['actor']);s=cg.stat();group.identity=(s.st_dev,s.st_ino)
            errors.attempt('recovery-cgroup-kill',group.kill)
            def retire_provider(name):
                row=parse(capture(folder/name,budget,4096));fields(row,('token','name','call'))
                need(row['token']==token and type(row['call'])is int and 1<=row['call']<=tools+models and row['name']=='provider-'+str(row['call']),'exact preselected provider leaf intent')
                child=cg/row['name']
                if not child.exists():return
                leaf=Cgroup(cg,row['name'],budget,cfg['limits']['actor']);stat_=child.stat();leaf.identity=(stat_.st_dev,stat_.st_ino)
                errors.attempt('recovery-provider-kill',leaf.kill);errors.attempt('recovery-provider-retire',leaf.finish)
            for name in sorted(providers):errors.attempt('recover-provider-intent:'+name,lambda name=name:retire_provider(name))
            errors.attempt('recovery-cgroup-finish',group.finish)
        raw=kernel_body('/proc/self/mountinfo',budget,2**20)
        mountrows=[line.split()for line in raw.decode().splitlines()if line.split()[4]==intent['work']]
        if mountrows:
            need(len(mountrows)==1 and mountrows[0][mountrows[0].index('-')+1:mountrows[0].index('-')+3]==['tmpfs','n090-'+token],'only the actual source-owned tmpfs may be unmounted')
            errors.attempt('recovery-unmount',lambda:host.command([n['umount']['path'],intent['work']],end-.1,end,budget))
        observed.append({'token':token,'normal_closed':False})
    for token in entries:errors.attempt("recover-intent:"+token,lambda token=token:recover_one(token))
    def mounts_absent():
        final_mounts={line.split()[4]for line in kernel_body('/proc/self/mountinfo',budget,2**20).decode().splitlines()}
        need(not any(p.startswith(str(root)+'/')for p in final_mounts),'all owned mount descendants retired')
    errors.attempt('whole-campaign-mount-absence',mounts_absent)
    def daemon_absent():
        result=host.docker(['ps','-a','--filter','label=n090.campaign='+campaign,'--format','{{.ID}}'],end-.1,end,budget)
        need(not base64.b64decode(result['stdout_base64']).strip(),'all owned daemon objects absent')
    errors.attempt('whole-campaign-daemon-absence',daemon_absent)
    errors.raise_first(observed);return {'root_absent':False,'intents':observed}

def invoke(cfg,package,selection,config_path,config_pin,manifest_pin):
    """Callable enclosing owner: returns only after actual child/native retirement.

    A shell caller must also observe this CLI's natural zero. This function does
    not claim to prove its own future caller's OS exit.
    """
    validate(cfg);n=cfg['native'];need(sys.platform=='linux'and os.geteuid()==0,'actual supported Linux root host')
    start=time.monotonic();work_end=start+n['campaign_seconds'];end=work_end+n['cleanup_seconds'];timing=(start,work_end,end)
    budget=Budget(n['controller_read_bytes'],n['controller_write_bytes'],work_end);cleanup_budget=Budget(n['recovery_read_bytes'],n['recovery_write_bytes'],end);errors=Ledger();record=None;retirement=None
    parent=regular_path(n['parent_custody_root']);need(not parent.exists(),'fresh enclosing parent custody');parent.mkdir(mode=0o700)
    save(parent/'SELECTION.json',encoded({'config':config_pin,'source_manifest':manifest_pin,'timing':timing}),cleanup_budget)
    process.PROC_READ_CAP=n['proc_metadata_bytes']
    name='n090-controller-'+hashlib.sha256(str(config_path).encode()+str(start).encode()).hexdigest()[:32]
    cg=Cgroup(n['cgroup_root'],name,budget,n['controller_native'])
    budget.read(8193);budget.write(16384+32) # fixed placement readback/record/PID writes precharged before dispatch
    budget.read(n['proc_metadata_bytes']+262145);budget.write(524290)
    child_argv=[sys.executable,'-I','-S','-B',str(package/'entry.py'),'child',str(config_path),config_pin['sha256'],manifest_pin['sha256'],*[repr(x)for x in timing]]
    try:
        cg.create(branch=False)
        row=selection['place_entry.py'];body=capture(package/'place_entry.py',budget,row['bytes'],row);save(parent/'trusted-place.py',body,budget)
        placement=parent/'PLACEMENT.json'
        argv=[sys.executable,'-I','-S','-B',str(parent/'trusted-place.py'),str(cg.path),str(cg.identity[0]),str(cg.identity[1]),str(placement),repr(work_end),'--',*child_argv]
        record=process._run_owned(argv,normal_end=work_end,cleanup_end=work_end+n['cleanup_seconds']/3,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'},metadata_read=budget.read,stream_cap=262144,monitor=cg.monitor)
        admit_placement(placement,cg.path,cg.identity,record,budget)
    except BaseException as e:errors.record('whole-programme-child',e)
    finally:
        cg.budget=cleanup_budget
        if cg.identity is not None:
            errors.attempt('controller-cgroup-kill',cg.kill);errors.attempt('controller-cgroup-retirement',cg.finish)
        try:retirement=recovery(cfg,package,cleanup_budget,end)
        except BaseException as e:errors.record('native-intent-recovery',e)
    if errors.events:
        failure={'schema':'n090-enclosing-failure-v1','errors':errors.metadata(),'child':record,'retirement':retirement,'original_carriers':[getattr(e,'record',None)for _,e in errors.events]}
        try:save(parent/'FAILED.json',encoded(failure),cleanup_budget)
        except BaseException as e:errors.record('enclosing-failure-publication',e)
        errors.raise_first({'child':record,'retirement':retirement})
    need(record is not None and all(x['normal_closed']for x in retirement['intents'])and len(retirement['intents'])==76800,'complete natural full campaign; recovery never converts failure to success')
    report=Path(cfg['output_root'])/'point-report.json';body=capture(report,cleanup_budget,n['controller_read_bytes']);result={'schema':'n090-enclosed-programme-support-v1','point_report':pin(body),'actual_child':record,'retirement':retirement,'managed_controller':budget.report(),'managed_recovery':cleanup_budget.report(),'qualification':False}
    save(parent/'ENCLOSED_SUPPORT.json',encoded(result),cleanup_budget);cleanup_budget.tick();return result
