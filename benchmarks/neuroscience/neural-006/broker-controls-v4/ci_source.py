"""Public CI source preparation, isolated image provisioning and result admission.
No operation is selected on import. Runtime/control sources are never loaded here.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import sys
import time

SELECTION_BYTES=3439
SELECTION_SHA='761b0cf536a52254be39de1d4e48aeaafd3a2f40a988306b9553ec22862f221e'
IMAGE_REFERENCE='python@sha256:6d10e720318bd84cc3d88af92bb5a47189222e17620a2fd214da6445e4afb679'
IMAGE_CONFIG='sha256:de8d79606beff46114d4abd5c392116c62142cbe582f8ede92cf4a64e1a10ff5'
SOURCE_CAP=2*1048576
BINARY_CAP=128*1048576
RETAIN_CAP=4*1048576
ROOT=Path(__file__).absolute().parent
spent=0
binary_spent=0

def need(ok,reason):
    if not ok:raise ValueError(reason)

def encoded(value):return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
def pin(body):return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
def identity(s):return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns'))
def ordinary(path):
    need(path.is_absolute() and not any(p.is_symlink() for p in (path,*path.parents)),'ordinary exact ancestry')

def read(path,expected=None,cap=1048576,binary=False):
    global spent,binary_spent
    path=Path(path);ordinary(path);fd=None;first=None;body=[];count=0;digest=hashlib.sha256()
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK);before=os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and 0<=before.st_size<=cap,'bounded ordinary single-link member')
        if binary:
            need(binary_spent+before.st_size+1<=BINARY_CAP,'binary admission cap');binary_spent+=before.st_size+1
        else:
            need(spent+before.st_size+1<=SOURCE_CAP,'source/evidence admission cap');spent+=before.st_size+1
        left=before.st_size
        while left:
            part=os.read(fd,min(65536,left));need(part,'complete source read');left-=len(part);count+=len(part);digest.update(part)
            if not binary:body.append(part)
        need(os.read(fd,1)==b'','exact EOF');after=os.fstat(fd)
        need(identity(before)==identity(after)==identity(path.lstat()),'stable descriptor and path identity')
        result={'path':str(path),'bytes':count,'sha256':digest.hexdigest()}
        if expected:need((count,result['sha256'])==(expected['bytes'],expected['sha256']),'selected content identity')
    except BaseException as e:first=e
    if fd is not None:
        try:os.close(fd)
        except BaseException as e:
            if first is None:first=e
            else:first.add_note('source close failure: '+type(e).__name__)
    if first is not None:raise first
    return b''.join(body),result

def parsed(body):
    def pairs(rows):
        value={}
        for k,v in rows:need(k not in value,'duplicate JSON key');value[k]=v
        return value
    return json.loads(body,object_pairs_hook=pairs,parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite JSON')))

def source():
    raw,_=read(ROOT/'CI_SOURCE_SELECTION.json',{'bytes':SELECTION_BYTES,'sha256':SELECTION_SHA})
    selected=parsed(raw);need(selected['schema']=='n006-public-ci-source-selection-v1' and len(selected['files'])==21,'exact21 CI operands')
    rows={};cache={}
    for row in selected['files']:
        p=Path(row['path']);need(not p.is_absolute() and '..' not in p.parts and p.as_posix()==row['path'] and row['path']not in rows,'canonical source membership')
        cache[row['path']]=read(ROOT/p,row)[0];rows[row['path']]=row
    fixed=parsed(cache['FIXED_SOURCES.json'])
    need(fixed['image_reference']==IMAGE_REFERENCE and fixed['image_config']==IMAGE_CONFIG and fixed['image_platform']=='linux/amd64','exact immutable image projection')
    need(len(fixed['files'])==17 and len(fixed['test_names'])==len(set(fixed['test_names']))==57,'full inert graph and exact57 names')
    for row in fixed['files']:need(row==rows[row['path']],'every runtime/harness/manifest pin joins')
    return rows,cache,fixed

def output():
    value=os.environ.get('RUNNER_TEMP');need(type(value)is str and value,'explicit CI temporary root')
    root=Path(value).absolute();ordinary(root);need(root.is_dir(),'existing CI temporary root')
    return root/'neural006-broker-controls-v4'

def retention(out):
    total=0;count=0
    if out.exists():
        for p in out.rglob('*'):
            s=p.lstat();need(not stat.S_ISLNK(s.st_mode),'no evidence symlinks')
            if stat.S_ISREG(s.st_mode):need(s.st_nlink==1,'single-link evidence');total+=s.st_size;count+=1
            else:need(stat.S_ISDIR(s.st_mode),'ordinary evidence namespace')
    need(total<=RETAIN_CAP and count<=128,'complete bounded evidence namespace');return total

def write(out,path,body):
    need(path.is_relative_to(out) and len(body)<=1048576 and retention(out)+len(body)<=RETAIN_CAP,'bounded owned evidence publication')
    ordinary(path);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600);first=None
    try:
        offset=0
        while offset<len(body):
            n=os.write(fd,memoryview(body)[offset:]);need(n>0,'complete evidence write');offset+=n
        os.fsync(fd)
    except BaseException as e:first=e
    try:os.close(fd)
    except BaseException as e:
        if first is None:first=e
        else:first.add_note('evidence close failure: '+type(e).__name__)
    if first is not None:raise first
    return {'path':str(path),**pin(body)}

def host():
    need(sys.platform=='linux' and platform.machine()=='x86_64' and sys.implementation.name=='cpython'
         and sys.version_info[:3]==(3,11,18),'selected Linux amd64 CPython3.11.18 host')
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode and not sys.flags.optimize,'actual unoptimized -I -S -B host')

def prepare():
    rows,cache,fixed=source();out=output();out.mkdir(mode=0o700)
    python=Path(sys.executable).resolve(strict=True)
    docker_name=shutil.which('docker',path='/usr/local/bin:/usr/bin:/bin');need(docker_name is not None,'existing Linux Docker CLI')
    docker=Path(docker_name).resolve(strict=True)
    python_row=read(python,cap=1048576,binary=True)[1];docker_row=read(docker,cap=64*1048576,binary=True)[1]
    owner_rows=[dict(rows[n],path=str(ROOT/n)) for n in ('owner.py','bootstrap.py','cli_ownership.py','FIXED_SOURCES.json')]
    selected=write(out,out/'OWNER_SELECTION.json',encoded({'schema':'n006_public57_owner_sources_v1','files':owner_rows}))
    config={'schema':'n006_public57_operator_v1','docker':docker_row,'host_python':python_row,
        'endpoint':'unix:///var/run/docker.sock','output_directory':str(out/'attempt'),
        'container_name':'n006-57-'+os.urandom(16).hex(),'owner_selection':selected}
    cfg=write(out,out/'CONFIG.json',encoded(config))
    result={'schema':'n006-public-ci-prepared-v1','configuration':cfg,'owner_selection':selected,
        'source_manifest':{'path':str(ROOT/'CI_SOURCE_SELECTION.json'),'bytes':SELECTION_BYTES,'sha256':SELECTION_SHA},
        'python_version':list(sys.version_info[:3]),'platform':sys.platform,'machine':platform.machine(),
        'image_reference':IMAGE_REFERENCE,'image_config':IMAGE_CONFIG,'source_reads':spent,'binary_reads':binary_spent,
        'runtime_qualification':False,'provider_credentials_selected':False}
    write(out,out/'PREPARED.json',encoded(result));print(json.dumps({'prepared':True,'image_reference':IMAGE_REFERENCE}))

def prepared(out):
    data=parsed(read(out/'PREPARED.json',cap=16384)[0]);need(data['schema']=='n006-public-ci-prepared-v1','prepared metadata')
    raw,_=read(out/'CONFIG.json',data['configuration']);config=parsed(raw)
    need(config['endpoint']=='unix:///var/run/docker.sock' and config['output_directory']==str(out/'attempt')
         and re.fullmatch('n006-57-[0-9a-f]{32}',config['container_name']),'exact prepared route')
    read(config['docker']['path'],config['docker'],cap=64*1048576,binary=True)
    read(config['host_python']['path'],config['host_python'],cap=1048576,binary=True)
    need(Path(config['host_python']['path'])==Path(sys.executable).resolve(),'same actual prepared interpreter')
    return data,config

def owner_module(cache):
    ns={'__name__':'authenticated_public_ci_owner','__file__':str(ROOT/'owner.py')}
    exec(compile(cache['owner.py'],str(ROOT/'owner.py'),'exec',dont_inherit=True),ns)
    return ns

def administrative_owner(out,cache,config,part):
    ns=owner_module(cache);o=ns['Owner'](time.monotonic());o.directory=out/part;o.directory.mkdir(mode=0o700)
    guard={'__name__':'authenticated_linux_exclusive_wait'}
    exec(compile(cache['cli_ownership.py'],'<authenticated-linux-cli-owner>','exec',dont_inherit=True),guard)
    o.ChildOwner=guard['ChildOwner'];o.guard,o.handlers=guard['exclusive_admission']()
    need(signal.getsignal(signal.SIGINT) is signal.default_int_handler,'caught SIGINT required before administrative CLI spawn')
    empty=o.directory/'empty-docker-config';empty.mkdir(mode=0o700)
    o.docker=[config['docker']['path'],'--host','unix:///var/run/docker.sock','--config',str(empty)]
    o.bootstrap=cache['bootstrap.py'];o.name=config['container_name']
    return o

def provision():
    rows,cache,fixed=source();out=output();data,config=prepared(out)
    o=administrative_owner(out,cache,config,'provision')
    try:
        o.checked(['pull','--platform','linux/amd64',IMAGE_REFERENCE],seconds=45,cap=196608)
        actual=parsed(o.checked(['image','inspect',IMAGE_REFERENCE]))
        need(len(actual)==1 and actual[0]['Id']==IMAGE_CONFIG and actual[0]['Os']=='linux'
             and actual[0]['Architecture']=='amd64' and not actual[0]['Config'].get('Volumes'),'actual provisioned immutable amd64 image')
    except BaseException as e:o.error('image_provision',e)
    result={'schema':'n006-public-image-provision-v1','success':not o.errors,'events':o.events,'errors':o.errors,
        'image_reference':IMAGE_REFERENCE,'image_config':IMAGE_CONFIG,'elapsed':time.monotonic()-o.start,
        'source_execution':False,'model_provider_science_calls':0,'automatic_retry':False}
    o.write('PROVISION.json',encoded(result));retention(out)
    need(not o.errors and time.monotonic()<o.end,'complete one-time bounded image provisioning')
    print(json.dumps({'image_provisioned':True,'execution_qualified':False}))

def launch():
    rows,cache,fixed=source();out=output();data,config=prepared(out)
    provision_result=parsed(read(out/'provision/PROVISION.json',cap=262144)[0])
    need(provision_result['success']is True and provision_result['image_reference']==IMAGE_REFERENCE,'completed image provisioning required')
    cfg=data['configuration']
    sys.argv=[str(ROOT/'owner.py'),'--config',str(out/'CONFIG.json'),'--config-bytes',str(cfg['bytes']),'--config-sha256',cfg['sha256']]
    # This compiles the exact captured owner, then its main starts the original60-second attempt.
    exec(compile(cache['owner.py'],str(ROOT/'owner.py'),'exec',dont_inherit=True),{'__name__':'__main__','__file__':str(ROOT/'owner.py')})
    raise RuntimeError('the exact owner main must exit')

def cleanup():
    rows,cache,fixed=source();out=output();data,config=prepared(out)
    attempt_path=out/'attempt/ATTEMPT.json'
    if not attempt_path.exists():
        write(out,out/'CLEANUP.json',encoded({'schema':'n006-public-post-attempt-closure-v1','success':False,
            'authority':'no complete original attempt record; no container operation authorized','original_attempt_promoted':False}))
        raise ValueError('original attempt authority absent')
    attempt=parsed(read(attempt_path,cap=32768)[0])
    need(attempt['config']==data['configuration'] and attempt['name']==config['container_name']
         and attempt['image']==IMAGE_CONFIG and attempt['image_reference']==IMAGE_REFERENCE
         and re.fullmatch('[0-9a-f]{32}',attempt['owner_nonce']),'original exact-container authority')
    o=administrative_owner(out,cache,config,'post-attempt-cleanup');o.nonce=attempt['owner_nonce']
    try:
        raw=o.checked(['container','ls','--all','--no-trunc','--filter','name=^/'+o.name+'$','--format','{{.ID}}'])
        if raw==b'':o.absent=True
        else:
            cid=raw.strip().decode();need(re.fullmatch('[0-9a-f]{64}',cid),'one matching exact owned container')
            o.inspect_identity(cid);o.created_requested=True;o.start_requested=True
            o.cleanup()
        need(o.absent,'owned container absence observed')
    except BaseException as e:o.error('post_attempt_closure',e)
    result={'schema':'n006-public-post-attempt-closure-v1','success':not o.errors and o.absent,
        'events':o.events,'errors':o.errors,'container_id':o.cid,'absent_observed':o.absent,
        'forced_container_kill':o.forced_container_kill,'original_attempt_promoted':False,
        'separate_cleanup_seconds':time.monotonic()-o.start}
    write(out,out/'CLEANUP.json',encoded(result));retention(out)
    need(result['success'] and time.monotonic()<o.end,'complete separately observed post-attempt closure')
    print(json.dumps({'post_attempt_absent':True,'original_attempt_promoted':False}))

def admit(owner_outcome,closure_outcome):
    rows,cache,fixed=source();out=output();data,config=prepared(out);first=None;admission={}
    try:
        need(owner_outcome=='success','original CI owner step succeeded without retry')
        need(closure_outcome=='success','post-attempt closure step reached original natural-zero completion')
        status=read(out/'OWNER_STATUS.txt',cap=16)[0];need(status==b'0\n','original timeout/owner command status zero')
        stdout=read(out/'owner.stdout',cap=65536)[0];stderr=read(out/'owner.stderr',cap=65536)[0]
        need(not stderr,'original owner stderr empty');terminal=parsed(stdout)
        need(terminal['success']is True and 0<=terminal['elapsed_seconds']<60,'original owner complete within unchanged deadline')
        result_pin=terminal['result'];need(result_pin['path']=='RESULT.json','exact owner result filename')
        result=parsed(read(out/'attempt/RESULT.json',result_pin)[0])
        need(result['success_before_final_transport']is True and result['errors']==[] and result['automatic_retry']is False
             and result['maximum_attempts']==1 and result['original_end']-result['original_start']==60
             and result['container_stopped_observed']is True and result['container_removed_observed']is True
             and result['container_absent_observed']is True and result['forced_container_kill']is False
             and result['native_or_scientific_or_actual_model_qualification']is False,'original complete container ownership evidence')
        streams={};total=0;attach=[]
        for i,event in enumerate(result['events'],1):
            owner=event['client_owner']
            need(event['returncode']==0 and event['forced_client_kill']is False and event['errors']==[]
                 and event['eof']=={'stdout':True,'stderr':True} and owner['state']=='reaped'
                 and owner['returncode']==0 and owner['group_probe']=='absent' and owner['stop_attempted']is False,
                 'every actual original CLI natural-zero/EOF/reaped/group-absent')
            pair={}
            for role in ('stdout','stderr'):
                row=event['stream_files'][role];name='CLI-%02d.%s'%(i,role);need(row['path']==name,'exact original stream name')
                raw=read(out/'attempt'/name,row,cap=262144)[0];total+=len(raw);pair[role]=raw
            streams[i]=pair
            if event['argv'][:4]==['container','start','--attach','--interactive']:attach.append(pair)
        need(len(result['events'])==8 and total==result['observed_stream_bytes']<=262144 and len(attach)==1,
             'complete exact8 CLI graph and bounded original streams')
        controls=parsed(attach[0]['stdout']);need(controls==result['control_result'],'original control body joins outer receipt')
        need(controls['tests_run']==57 and controls['all_passed']is True and controls['actual_model_qualification']is False
             and all(controls[k]==0 for k in ('failures','errors','model_calls','provider_network_calls','scientific_runs')),
             'all57 unchanged inert controls passed')
        lines=attach[0]['stderr'].decode().splitlines();names=[l.split(' (',1)[0] for l in lines if l.startswith('test_') and l.endswith(' ... ok')]
        need(names==fixed['test_names'] and len(set(names))==57,'exact complete ordered57 original oracle names')
        runtime=[parsed(l[len('N006_RUNTIME '):]) for l in lines if l.startswith('N006_RUNTIME ')]
        need(runtime==[result['container_runtime']] and runtime[0]['machine']=='x86_64'
             and runtime[0]['python_version']==[3,11,18] and runtime[0]['pid']==1,'actual Linux runtime and PID1 evidence')
        closure=parsed(read(out/'CLEANUP.json',cap=262144)[0]);need(closure['success']is True and closure['original_attempt_promoted']is False,'separate final absence observation')
        admission={'status':'PASS','controls':57,'names':names,'image_reference':IMAGE_REFERENCE,
                   'image_config':IMAGE_CONFIG,'original_owner':pin(stdout),'original_result':result_pin,
                   'model_provider_science_calls':0,'scientific_qualification':False}
    except BaseException as e:
        first=e;admission={'status':'FAIL','failure_type':type(e).__name__,'reason':str(e)[:2048],
                          'scientific_qualification':False,'original_attempt_promoted':False}
    write(out,out/'CI_ADMISSION.json',encoded({'schema':'n006-public57-ci-admission-v1',**admission}));retention(out)
    if first is not None:raise first
    print(json.dumps({'status':'PASS','exact_controls':57,'model_provider_science_calls':0,'scientific_qualification':False}))

def main():
    host();p=argparse.ArgumentParser();p.add_argument('operation',choices=('prepare','provision','launch','cleanup','admit'));p.add_argument('--owner-outcome');p.add_argument('--closure-outcome');a=p.parse_args()
    if a.operation=='admit':admit(a.owner_outcome,a.closure_outcome)
    else:globals()[a.operation]()
    return 0

if __name__=='__main__':raise SystemExit(main())
