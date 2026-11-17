"""Generated request/effective namespace checks for the corrected verifier."""
import copy,json,os,resource,subprocess,sys,tempfile,time,types
from pathlib import Path
Q=Path(__file__).resolve().parent;raw=(Q/'test_generated.py').read_bytes()
t=types.ModuleType('_namespace078_fixture');t.__file__=str(Q/'test_generated.py');sys.modules[t.__name__]=t
exec(compile(raw,t.__file__,'exec'),t.__dict__)
subprocess.Popen=lambda *a,**k:(_ for _ in ()).throw(AssertionError('Native process dispatch prohibited'))
started=time.monotonic();observed=[]
with tempfile.TemporaryDirectory(prefix='n078-namespace-review-') as temp:
    root=Path(temp).resolve();gold=root/'GENERATED_GOLD.json';gold.write_bytes(b'generated metadata-only test\n')
    mounts={'/private/GOLD.json':gold};name='neural078-grade-generated-review';image='sha256:'+'c'*64
    command=t.GRADE.command(name,mounts,image);docker=t.FakeDocker();docker('generated',{},command,100,65536)
    assert '--pid' not in command and not any(x.startswith('--pid=') for x in command)
    assert command.count('--ipc')==1 and command[command.index('--ipc')+1]=='private'
    original=docker.items[name][0]
    for field,value,expected in [('PidMode','',True),('IpcMode','private',True),('PidMode','container:generated-peer',False),('IpcMode','container:generated-peer',False),('PidMode','host',False),('IpcMode','host',False),('PidMode','private',False),('PidMode',None,False),('PidMode',False,False),('IpcMode','shareable',False),('IpcMode','none',False),('IpcMode','',False),('IpcMode',None,False),('IpcMode',False,False)]:
        obj=copy.deepcopy(original);obj['HostConfig'][field]=value;accepted=False;error=None
        try:t.GRADE.verify(obj,name,mounts,image);accepted=True
        except ValueError as e:error=str(e)
        assert accepted is expected,(field,value,accepted,error)
        observed.append({'field':field,'value':value,'accepted_by_corrected_verifier':accepted,'error':error})
    for field in ('PidMode','IpcMode'):
        obj=copy.deepcopy(original);obj['HostConfig'].pop(field);accepted=False
        try:t.GRADE.verify(obj,name,mounts,image);accepted=True
        except ValueError:pass
        assert accepted is False,(field,'missing')
        observed.append({'field':field,'missing':True,'accepted_by_corrected_verifier':False})
print(json.dumps({'corrected_namespace_conjunction':True,'actual_frozen_verifier_exercised':True,'generated_only':True,'native_processes_started':0,'command_selects_pid_mode':'--pid' in command,'command_selects_ipc_mode':'--ipc' in command,'observations':observed,'explicit_source_generated_reads':t.READ_BYTES+len(raw),'peak_rss_darwin_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'elapsed_seconds':time.monotonic()-started,'pid':os.getpid(),'children':0}))
