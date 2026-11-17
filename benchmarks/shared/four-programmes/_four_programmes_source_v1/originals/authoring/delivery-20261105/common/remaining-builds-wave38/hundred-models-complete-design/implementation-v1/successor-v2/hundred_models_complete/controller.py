"""Owned-process lifetime and all-output custody. Scientific selection is external."""
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from .guard import need,encoded,bare,Publisher

def owned_group_exists(pgid):
    """Probe only the group allocated by this invocation, never a discovered PID."""
    try:os.killpg(pgid,0);return True
    except ProcessLookupError:return False


def cleanup_owned_group(child,pgid):
    """Group ownership is independent of leader liveness or return status.

    The external isolation contract must prevent group escape/reassignment. This
    does not enumerate/kill unrelated groups and never resumes a failed deadline.
    A bounded cleanup interval is reported separately from scientific work.
    """
    begin=time.monotonic_ns();report={'owned_pgid':pgid,'signal_sent':False,'leader_reaped':False,'group_absent':False,'uncertain':False}
    try:
        try:os.killpg(pgid,signal.SIGKILL);report['signal_sent']=True
        except ProcessLookupError:report['group_absent']=True
        except BaseException as e:report['signal_error']=type(e).__name__;report['uncertain']=True
        try:report['leader_returncode']=child.wait(timeout=1);report['leader_reaped']=True
        except BaseException as e:report['leader_wait_error']=type(e).__name__;report['uncertain']=True
        end=begin+1_000_000_000
        while time.monotonic_ns()<end:
            try:
                if not owned_group_exists(pgid):report['group_absent']=True;break
            except BaseException as e:report['probe_error']=type(e).__name__;report['uncertain']=True;break
            time.sleep(.01)
        if not report['group_absent']:report['uncertain']=True
    finally:report['elapsed_ns']=time.monotonic_ns()-begin
    return report


def run_owned(argv,cwd,env,budget,*,stream_limit,limits):
    """Real child launch. Never kill unrelated processes; no success after deadline."""
    need(type(argv)is list and argv and all(type(x)is str for x in argv),'explicit argv')
    need(type(stream_limit)is int and stream_limit>0,'stream bound')
    budget.charge('write_bytes',2*stream_limit);budget.check();child=None;selector=selectors.DefaultSelector();streams={'stdout':bytearray(),'stderr':bytearray()};completion=None;primary=None;owned_pgid=None
    def setlimits():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(limits['cpu_seconds'],limits['cpu_seconds']))
        resource.setrlimit(resource.RLIMIT_FSIZE,(limits['file_bytes'],limits['file_bytes']))
        resource.setrlimit(resource.RLIMIT_NOFILE,(limits['open_files'],limits['open_files']))
        resource.setrlimit(resource.RLIMIT_AS,(limits['address_space_bytes'],limits['address_space_bytes']))
    try:
        child=subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True,preexec_fn=setlimits)
        owned_pgid=child.pid
        for name,stream in (('stdout',child.stdout),('stderr',child.stderr)):
            os.set_blocking(stream.fileno(),False);selector.register(stream,selectors.EVENT_READ,name)
        while selector.get_map():
            budget.check()
            for key,_ in selector.select(timeout=min(.05,max(0,(budget.deadline_ns-time.monotonic_ns())/1e9))):
                block=os.read(key.fileobj.fileno(),65536)
                if not block:selector.unregister(key.fileobj);continue
                need(len(streams[key.data])+len(block)<=stream_limit,'complete original stream limit')
                streams[key.data].extend(block)
        remaining=max(0,(budget.deadline_ns-time.monotonic_ns())/1e9);code=child.wait(timeout=remaining);budget.check()
        completion={'returncode':code,'natural_completion':True,'pid':child.pid,'forced':False}
        need(code==0,'native child failed with original streams preserved')
        # EOF/leader exit is not completion if an owned descendant remains.
        need(not owned_group_exists(owned_pgid),'leader completed but owned process group remains; attempt refused')
        return {'completion':completion,'stdout':bytes(streams['stdout']),'stderr':bytes(streams['stderr'])}
    except BaseException as error:
        primary=error
        cleanup=None
        if child is not None and owned_pgid is not None:
            cleanup=cleanup_owned_group(child,owned_pgid)
            if cleanup['uncertain']:error.add_note('Owned process group cleanup uncertain; see original observation.')
        error.original_child_observation={'completion':completion,'pid':None if child is None else child.pid,'returncode':None if child is None else child.poll(),'stdout_hex':streams['stdout'].hex(),'stderr_hex':streams['stderr'].hex(),'forced_or_uncertain':completion is None or bool(cleanup and (cleanup['signal_sent'] or cleanup['uncertain'])),'owned_group_cleanup':cleanup,'budget':budget.snapshot()}
        raise
    finally:
        selector.close()
        if child is not None:
            for stream in (child.stdout,child.stderr):
                if stream:
                    try:stream.close()
                    except BaseException as cleanup:
                        if primary is not None:primary.add_note('Stream close uncertainty: '+type(cleanup).__name__)
                        else:raise

class Journal:
    def __init__(self,publisher,plan):
        self.publisher=publisher;self.plan=plan;self.completed={};self.failed=False
        publisher.write('plan.json',encoded(plan))
    def admit_job(self,job):
        self.publisher.budget.check();need(not self.failed,'terminal failed campaign')
        need(job['id'] not in self.completed and set(job['dependencies'])<=set(self.completed),'only complete causal predecessors')
    def complete(self,job,receipt,observation):
        self.admit_job(job);need(observation['completion']['natural_completion'] is True and observation['completion']['returncode']==0,'actual complete child')
        record={'job':job['id'],'plan':bare(encoded(self.plan)),'receipt':receipt,'observation':{'completion':observation['completion'],'stdout_hex':observation['stdout'].hex(),'stderr_hex':observation['stderr'].hex(),'stdout_pin':bare(observation['stdout']),'stderr_pin':bare(observation['stderr'])}}
        d=self.publisher.write(f'job_{len(self.completed):05}.json',encoded(record));self.completed[job['id']]=d;return d
    def final(self):
        need(not self.failed and list(self.completed)==[x['id'] for x in self.plan['jobs']],'every original job in complete order')
        self.publisher.budget.check();return self.publisher.write('COMPLETE.json',encoded({'plan':bare(encoded(self.plan)),'completed':self.completed,'scientific_qualified':False,'budget':self.publisher.budget.snapshot()}))
