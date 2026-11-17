"""Durable, launch-barrier ownership for one trusted controller process group.

No candidate code runs here. An unactivated child cannot create Docker resources;
an activated group is journaled first. Stop the group before Docker recovery.
"""
from pathlib import Path
import json,os,signal,stat,subprocess,sys,time,uuid
HERE=Path(__file__).resolve().parent
from trusted_controller import validate_controller


def read(path):
    path=Path(path);s=path.lstat()
    if path.is_symlink()or not stat.S_ISREG(s.st_mode)or s.st_nlink!=1 or not 0<s.st_size<=16384:raise ValueError('Bounded regular process journal')
    return json.loads(path.read_text())


def atomic(path,value):
    path=Path(path);tmp=path.with_suffix('.next');body=(json.dumps(value,allow_nan=False)+'\n').encode()
    if len(body)>16384:raise ValueError('Process metadata cap')
    with tmp.open('xb')as f:f.write(body);f.flush();os.fsync(f.fileno())
    os.chmod(tmp,0o400);os.rename(tmp,path)
    fd=os.open(path.parent,os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)


def launch(argv,folder,seconds,controller):
    folder=Path(folder).absolute()
    if not folder.is_dir()or any(p.is_symlink()for p in(folder,*folder.parents))or not 1<=seconds<=300:raise ValueError('Fixed bounded process ownership directory')
    validate_controller(controller,argv)
    owner=folder/'process_owner.json';gate=folder/'process_gate.json';token=uuid.uuid4().hex
    args=[sys.executable,'-I','-B',str(HERE/'group_bootstrap.py'),'--owner',str(owner),'--token',token,'--seconds',str(float(seconds))]
    atomic(folder/'process_intent.json',{'bootstrap_argv':args,'token':token,'activation_requires_fsynced_owner':True,'controller':controller})
    proc=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
    try:
        # The framework launcher may exec/rewrite argv before Python initializes.
        # Wait for this exact trusted bootstrap's atomic ready marker BEFORE ps.
        ready_path=folder/'process_ready.json';ready_deadline=time.monotonic()+min(1.5,seconds/2)
        while not ready_path.exists():
            if time.monotonic()>=ready_deadline:raise TimeoutError('Bounded initialized-bootstrap readiness')
            time.sleep(.01)
        ready=read(ready_path)
        if ready!={'token':token,'pid':proc.pid,'pgid':proc.pid,'python_initialized_before_identity_snapshot':True}:raise ValueError('Exact initialized-bootstrap readiness')
        observed=inspect_leader(proc.pid,time.monotonic()+1)
        suffix=' '.join(args[1:])
        if observed['pgid']!=proc.pid or not observed['command'].endswith(' '+suffix):raise ValueError('Observed exact bootstrap arguments')
        validate_controller(controller,argv)
        atomic(owner,{'controller':controller,'observed_leader':observed,'pid':proc.pid,'pgid':proc.pid,'token':token,'bootstrap_argv':args,'child_argv':argv,'seconds':float(seconds),'pid_recorded_before_activation':True})
        atomic(gate,{'token':token,'activate':True})
        return proc
    except BaseException:
        try:os.killpg(proc.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        try:proc.communicate(timeout=1)
        except Exception:pass
        raise


def expected(folder):
    folder=Path(folder).absolute();owner=read(folder/'process_owner.json');intent=read(folder/'process_intent.json')
    pid=owner['pid'];token=owner['token']
    if type(pid)is not int or pid<=1 or owner['pgid']!=pid or owner.get('pid_recorded_before_activation')is not True or type(token)is not str or len(token)!=32 or any(c not in'0123456789abcdef'for c in token):raise ValueError('Exact durable process identity')
    args=[sys.executable,'-I','-B',str(HERE/'group_bootstrap.py'),'--owner',str(folder/'process_owner.json'),'--token',token,'--seconds',str(float(owner['seconds']))]
    if owner['bootstrap_argv']!=args or intent['bootstrap_argv']!=args or intent['token']!=token or intent['activation_requires_fsynced_owner']is not True:raise ValueError('Exact bootstrap command identity')
    if owner['controller']!=intent['controller']:raise ValueError('Descriptor identity across intent/ownership')
    validate_controller(owner['controller'],owner['child_argv'],check_bytes=False)
    return owner,args


def inspect_leader(pid,end):
    p=subprocess.run(['/bin/ps','-ww','-p',str(pid),'-o','pid=','-o','pgid=','-o','lstart=','-o','stat=','-o','command='],capture_output=True,text=True,timeout=min(1,max(.001,end-time.monotonic())))
    if len(p.stdout)>8192 or len(p.stderr)>1024:raise ValueError('Untruncated process identity required')
    fields=p.stdout.strip().split(None,8)
    if p.returncode!=0 or len(fields)!=9:return None
    return {'pid':int(fields[0]),'pgid':int(fields[1]),'started':' '.join(fields[2:7]),'state':fields[7],'command':fields[8]}


def group_exists(pid):
    try:os.killpg(pid,0);return True
    except ProcessLookupError:return False


def stop(folder,end,proc=None):
    """Kill only the exact owned group; caller must then recover Docker resources."""
    folder=Path(folder);journal=folder/'process_owner.json'
    if not journal.exists():
        if(folder/'process_gate.json').exists():raise ValueError('Activation without ownership')
        return {'status':'never_activated','absence_verified':True,'no_group_identity_claim':True}
    owner,args=expected(folder);pid=owner['pid'];row={'pid':pid,'pgid':pid,'status':'checking','absence_verified':False}
    if group_exists(pid):
        if time.monotonic()>=end:raise TimeoutError('Process cleanup deadline')
        actual=inspect_leader(pid,end);row['leader_inspection']=actual;initial=owner['observed_leader']
        exact=actual is not None and actual['pid']==pid and actual['pgid']==pid and actual['started']==initial['started'] and (actual['command']==initial['command'] or actual['state'].startswith('Z'))
        if exact:
            try:os.killpg(pid,signal.SIGKILL);row['kill_sent']=True
            except ProcessLookupError:pass
        elif group_exists(pid):raise ValueError('Refuse nonmatching process-group leader')
    if proc is not None:
        stdout,stderr=proc.communicate(timeout=min(1,max(.001,end-time.monotonic())))
        if len(stdout)>65536 or len(stderr)>65536:raise ValueError('Bounded trusted controller logs')
        row.update(stdout=stdout.decode(errors='replace'),stderr=stderr.decode(errors='replace'),bootstrap_returncode=proc.returncode)
    while group_exists(pid)and time.monotonic()<end:time.sleep(.01)
    row['absence_verified']=not group_exists(pid);row['status']='owned_group_absent'if row['absence_verified']else'owned_group_absence_unverified'
    return row
