"""Original complete programme CLI; qualification is verified, not synthesized."""
import argparse,os,math,time,signal,resource
from pathlib import Path
from .domain import fields,need,parse,uint,real,registry,limits
from .storage import read
from .runtime.budget import Budget
from .runtime.common import FailureCarrier
from .runtime.journal import Journal
from .admission import Authority
from .campaign import Campaign

LIMITS=('wall_seconds','cpu_seconds','read_bytes','write_bytes','live_bytes','files','model_calls','stream_bytes')

def selected_limits(value):
    return limits(value)

def original_file(path,digest,budget,maximum):
    p=Path(path);need(p.is_absolute() and p.is_file() and not p.is_symlink(),'literal original operator file')
    size=p.stat().st_size;need(0<size<=maximum,'bootstrap extent before reading')
    return read(p.parent,{'path':p.name,'bytes':size,'sha256':digest},budget,maximum)

def enforce_host(root,budget):
    p=root['native_profile'];uint(p['host_memory_bytes'],True)
    need(os.uname().sysname=='Linux','qualified Linux host required, no fallback')
    limit=p['host_memory_bytes'];soft,hard=resource.getrlimit(resource.RLIMIT_AS)
    need(hard==resource.RLIM_INFINITY or limit<=hard,'original selected host memory limit')
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
    cpu=math.ceil(budget.limits['cpu_seconds']+budget.cpu_origin);old=resource.getrlimit(resource.RLIMIT_CPU)
    need(old[1]==resource.RLIM_INFINITY or cpu+1<=old[1],'host CPU containment intersects existing bound')
    resource.setrlimit(resource.RLIMIT_CPU,(cpu,cpu+1))
    def timeout(signum,frame):raise TimeoutError('original whole host lifetime exhausted')
    signal.signal(signal.SIGALRM,timeout);signal.signal(signal.SIGXCPU,timeout)
    remaining=budget.deadline-budget.clock();need(remaining>0,'original deadline before host effects');signal.setitimer(signal.ITIMER_REAL,remaining)

def main(origin,cpu_origin):
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--root-sha256',required=True);ap.add_argument('--qualification',required=True);ap.add_argument('--qualification-sha256',required=True);ap.add_argument('--issuer-public-key',required=True);ap.add_argument('--issuer-public-key-sha256',required=True);ap.add_argument('--output',required=True)
    a=ap.parse_args();carrier=FailureCarrier();journal=None;report=None
    # This fixed bootstrap is part of the original lifetime, not a resettable job.
    bootstrap=dict(wall_seconds=120,cpu_seconds=120,read_bytes=33554432,write_bytes=1048576,live_bytes=1048576,files=16,model_calls=1,stream_bytes=1048576)
    budget=Budget(origin,bootstrap,cpu_origin=cpu_origin)
    try:
        raw=original_file(a.root,a.root_sha256,budget,16777216);root=parse(raw);limits=selected_limits(root['limits'])
        selected_limits(root['cell_limits'])
        # The externally pinned root sets the original campaign envelope once;
        # prior bootstrap reads/CPU/origin remain on the same object and are checked.
        budget.limits=limits;budget.global_limits=dict(limits);budget.deadline=origin+limits['wall_seconds'];budget.check('root envelope includes original bootstrap')
        journal=Journal(Path(a.output),budget,carrier)
        q=original_file(a.qualification,a.qualification_sha256,budget,1048576);key=original_file(a.issuer_public_key,a.issuer_public_key_sha256,budget,32)
        authority=Authority(raw,a.root_sha256,q,key,budget);enforce_host(root,budget)
        campaign=Campaign(authority,journal);report=campaign.run()
    except BaseException as exc:carrier.fail(exc,'complete programme')
    finally:
        if journal is not None:
            journal.complete_terminal(report)
    return 0 if report is not None and carrier.first is None and carrier.durable else 2
