"""Task-specific ICNet lifecycle primitives reused from reviewed NEURAL075 source."""
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import time
from .io_guard import need,parse as decode
from .transport import bounded_call
LABEL="org.neurobench.neural067-context-owner"
SOURCE_LABEL="org.neurobench.neural067-program-sha256"

def ordinary(path):
    path=Path(path).absolute()
    need('..' not in path.parts and not any(p.is_symlink() for p in (path,*path.parents)),'No linked host path')
    need(not any(c in str(path) for c in ',\n\r\0'),'Unambiguous Docker mount path')
    return path


class CommandError(RuntimeError):pass


class Docker:
    """Exact local CLI wrapper; every attempted capped capture is reserved in advance."""
    def __init__(self,binary,env,check_socket,budget,*,call=bounded_call):
        need(type(binary)is str and binary.startswith('/')and type(env)is dict,'Explicit Docker operands')
        need(type(env.get('DOCKER_HOST'))is str and env['DOCKER_HOST'].startswith('unix:///')and 'DOCKER_CONTEXT'not in env,'Fixed local socket only')
        need(callable(check_socket),'Pinned local socket check required')
        self.binary,self.env,self.check_socket,self.budget,self.call=binary,dict(env),check_socket,budget,call
        self.records=[];self.attempts=0
    def __call__(self,args,deadline,phase,cap=32768):
        need(type(cap)is int and 0<cap<=131072 and self.attempts<128,'Bounded control command attempts/capture')
        need(time.monotonic()<deadline,'Absolute control deadline')
        self.attempts+=1;row={'sequence':self.attempts,'phase':phase,'argv':list(args),'reserved_capture_bytes':cap}
        try:
            self.budget.read(cap);self.budget.tick();self.check_socket()
            p=self.call(self.binary,self.env,args,deadline,cap)
            row.update(returncode=p.returncode,stdout_bytes=len(p.stdout),stderr_bytes=len(p.stderr))
            need(p.returncode==0,'Docker command failed')
            return p.stdout
        except BaseException as error:row['error_type']=type(error).__name__;raise
        finally:
            try:
                self.check_socket()
                need(time.monotonic()<deadline,'Control closure deadline')
            except BaseException as error:row.setdefault('error_type',type(error).__name__);raise
            finally:self.records.append(row)


def child_deadline(deadline,seconds=12):return min(deadline,time.monotonic()+seconds)


def inventory(docker,selector,deadline,phase):
    raw=docker(['container','ls','--all','--no-trunc','--filter',selector,'--format','{{.ID}}'],
               child_deadline(deadline,5),phase,4096)
    rows=raw.decode('ascii').splitlines()
    need(len(rows)==len(set(rows)) and all(re.fullmatch('[a-f0-9]{64}',x) for x in rows),'Exact inventory IDs')
    return rows


def inspected(docker,identifier,deadline,phase):
    rows=decode(docker(['container','inspect',identifier],child_deadline(deadline),phase))
    need(type(rows)is list and len(rows)==1 and type(rows[0])is dict,'One exact container inspection')
    return rows[0]


def ownership(value,identifier,name,owner,source=None):
    need(value['Id']==identifier and value['Name']=='/'+name
         and value['Config']['Labels'].get(LABEL)==owner,'Exact case container ownership')
    if source is not None:need(value['Config']['Labels'].get(SOURCE_LABEL)==source,'Exact committed program source selector')


def natural_exit(value):
    state=value['State']
    need(state['Status']=='exited' and state['Running'] is False and state['Pid']==0 and state['Dead'] is False
         and state['OOMKilled'] is False and state['ExitCode']==0 and not state.get('Error'),
         'Natural successful exit with no OOM')
    need(type(state['StartedAt'])is str and not state['StartedAt'].startswith('0001')
         and type(state['FinishedAt'])is str and not state['FinishedAt'].startswith('0001'),
         'Observed start and natural finish')
    return {k:state[k] for k in ('Status','Running','Dead','OOMKilled','ExitCode','StartedAt','FinishedAt')}


def cleanup(docker,identifier,name,owner,deadline,source=None):
    owned=inventory(docker,'label='+LABEL+'='+owner,deadline,'cleanup_owner_inventory')
    named=inventory(docker,'name=^/'+name+'$',deadline,'cleanup_name_inventory')
    need(len(owned)<=1 and owned==named,'Exact owned/name inventory agreement')
    if source is not None:need(inventory(docker,'label='+SOURCE_LABEL+'='+source,deadline,'cleanup_source_inventory')==owned,'Exact source/owner/name inventory agreement')
    forced=False;removed=False
    if owned:
        actual=owned[0];need(identifier is None or identifier==actual,'Known exact owned ID')
        value=inspected(docker,actual,deadline,'cleanup_inspect');ownership(value,actual,name,owner,source)
        if value['State']['Running']:
            docker(['container','kill','--signal','KILL',actual],child_deadline(deadline,5),'cleanup_kill',4096)
            docker(['container','wait',actual],child_deadline(deadline,5),'cleanup_wait',4096);forced=True
        docker(['container','rm',actual],child_deadline(deadline,5),'cleanup_remove',4096);removed=True
    # Successful empty inventories prove absence; no case-sensitive stderr heuristic.
    a=inventory(docker,'label='+LABEL+'='+owner,deadline,'absence_owner_inventory')
    b=inventory(docker,'name=^/'+name+'$',deadline,'absence_exact_name_inventory')
    need(a==b==[],'Independent owned-container absence')
    if source is not None:need(inventory(docker,'label='+SOURCE_LABEL+'='+source,deadline,'absence_source_inventory')==[],'Independent program-source absence')
    return {'owned_absence_confirmed':True,'owner_inventory':a,'exact_name_inventory':b,
            'removed':removed,'forced_stop':forced}

