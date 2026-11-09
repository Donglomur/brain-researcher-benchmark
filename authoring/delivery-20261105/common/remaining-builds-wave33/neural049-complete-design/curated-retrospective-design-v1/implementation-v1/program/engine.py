"""Concrete inactive Docker Engine transport; no subprocess or numeric-PID signals.

Only independently qualified local Engine API v1.47 is selected. Container IDs
are immutable 64-hex daemon identities, never names. Unknown HTTP completion is
not retried. Failure retirement removes the exactly joined ID; an unknown create
is left explicitly unresolved for operator inspection, never reported stopped.
"""
import hashlib
import http.client
import os
from pathlib import Path
import socket
import math
import stat
import time
from urllib.parse import quote
from core import encoded, parse, pin, need, integer, finite, canonical, disjoint, capture, publish, cleanup_preserving


class UnixConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__('localhost', timeout=timeout); self.path = path
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.path)


class Engine:
    def __init__(self, selection, budget, record, gallery=None):
        self.gallery=gallery
        self.selection, self.budget, self.record = selection, budget, record
        canonical(selection['socket'])
        need(selection.get('api') == 'v1.47', 'exact qualified daemon API')
        self.used_cpu = 0; self.reserved_cpu = 0; self.reserved_gpu = 0.; self.operations = []; self.scope = None

    def begin_scope(self,identity,cutoff,limits):
        need(self.scope is None,'no nested or leaked candidate resource scope')
        now=self.budget.tick(cutoff)
        self.scope={'identity':identity,'cutoff':min(cutoff,self.budget.deadline),
                    'cpu_cap':integer(limits['native_cpu_ns'],1),'gpu_cap':finite(limits['gpu_device_seconds']),
                    'cpu_reserved':0,'gpu_reserved':0.,'entered_at':now,'operations':0}
        need(self.scope['gpu_cap']>=0,'nonnegative episode GPU-device allowance')
        self.record({'kind':'scope_started',**self.scope,'original_origin':self.budget.origin})

    def end_scope(self,identity):
        need(self.scope is not None and self.scope['identity']==identity,'same complete episode scope')
        self.budget.tick(self.scope['cutoff']);row=dict(self.scope)
        self.record({'kind':'scope_completed',**row,'observed_end':self.budget.tick(self.scope['cutoff'])})
        self.scope=None;return row

    def abort_scope(self):
        if self.scope is None:return None
        row=dict(self.scope);self.scope=None
        self.record({'kind':'scope_failed',**row,'unknown_child_or_cost_state':True})
        return row

    def request(self, method, path, body, deadline, statuses=(200,), limit=None, closeout=False):
        def check_clock():
            now=finite(time.monotonic())
            need(self.budget.origin <= now < min(deadline,self.budget.deadline), 'inherited Engine request cutoff')
            return now
        now=check_clock()
        limit=integer(self.selection.get('response_bytes',1<<20) if limit is None else limit,1)
        raw = encoded(body) if body is not None else b''
        # These are logical protocol ceilings; the daemon's internal disk/CPU
        # accounting is separately qualified, not inferred from JSON byte size.
        need(len(raw)<=integer(self.selection.get('request_bytes',1<<28),1),'qualified Engine request extent')
        self.budget.reserve_write(len(raw)); self.budget.reserve_read(limit + 1)
        conn = UnixConnection(self.selection['socket'], min(10., deadline-now))
        try:
            conn.request(method, '/v1.47'+path, body=raw,
                         headers={'Content-Type':'application/json','Connection':'close'})
            check_clock()
            response=conn.getresponse();check_clock();parts=[];n=0
            while True:
                need(time.monotonic()<deadline,'Engine body deadline')
                block=response.read(min(65536,limit+1-n));check_clock()
                if not block: break
                parts.append(block);n+=len(block);need(n<=limit,'Engine response ceiling')
            payload=b''.join(parts)
            need(response.status in statuses,'Engine status '+str(response.status))
            check_clock()
            return response.status,payload
        finally:
            cleanup_preserving(conn.close)
            cleanup_preserving(check_clock)

    @staticmethod
    def container_id(value):
        need(type(value) is str and len(value)==64 and all(c in '0123456789abcdef' for c in value),
             'full immutable container identity')
        return value

    def inspect(self, cid, deadline):
        _,raw=self.request('GET','/containers/'+self.container_id(cid)+'/json',None,deadline)
        obj=parse(raw);need(obj.get('Id')==cid,'daemon exact container ID')
        return obj

    def close_owned(self, cid, expected_labels, deadline):
        """Force-remove the exact verified ID; no reuse of a name or PID.

        Removal closes a concurrent delayed start by retiring the ID itself.
        Failed/ambiguous remove or absent confirmation remains unresolved.
        """
        result={'container':cid,'attempted':False,'removed':False,'absence_confirmed':False,'successful_clock_custody':False}
        try:
            obj=self.inspect(cid,deadline)
            need(obj['Config']['Labels']==expected_labels,'exact owned labels before retirement')
            result['attempted']=True
            self.request('DELETE','/containers/'+cid+'?force=true&v=false',None,deadline,statuses=(204,))
            result['removed']=True
            status,_=self.request('GET','/containers/'+cid+'/json',None,deadline,statuses=(404,),limit=65536)
            result['absence_confirmed']=status==404
            result['observed_end']=finite(time.monotonic())
            result['cutoff']=deadline
            need(self.budget.origin <= result['observed_end'] < min(deadline,self.budget.deadline),'complete owned retirement clock')
            result['successful_clock_custody']=True
        except BaseException as error:
            result['error_type']=type(error).__name__;result['unknown_state']=True
        return result

    def execute(self, operation, argv, mounts, output, limits, cutoff, source_pin, expected_artifacts, *, optional_artifacts=None, output_target='/output'):
        """Run the actual fixed worker; callbacks can only record events.

        Candidate model bytes remain sandbox-side; host captures bounded opaque
        artifact hashes after complete natural process closure, never unpickles.
        """
        if self.scope is not None:cutoff=min(cutoff,self.scope['cutoff'])
        start=self.budget.tick(cutoff)
        need(type(operation) is str and operation and operation not in self.operations,'unique scheduled operation')
        need(type(argv) is list and argv and all(type(x) is str and x and '\x00' not in x for x in argv),'literal worker argv')
        need(type(mounts) is list and mounts,'exact input mounts')
        output=canonical(output)
        optional_artifacts={} if optional_artifacts is None else optional_artifacts
        need(type(expected_artifacts)is dict and type(optional_artifacts)is dict
             and not set(expected_artifacts)&set(optional_artifacts),'disjoint required/conditional output plan')
        all_artifacts={**expected_artifacts,**optional_artifacts}
        from core import relative
        for name,cap in all_artifacts.items(): relative(name);integer(cap,1)
        operation_hash=hashlib.sha256(operation.encode()).hexdigest()
        need(output_target in ('/output','/artifacts/'+operation_hash),'stable exact output namespace')
        need(self.selection.get('whole_output_quota_qualified') is True
             and self.selection['whole_output_quota_root']==self.selection['output_root']
             and canonical(self.selection['output_root']) in output.parents,
             'actual independently evidenced hard quota for complete attempt output root')
        integer(self.selection['whole_output_quota_bytes'],1)
        # Per-file extents are checked on complete closure. A malicious producer
        # may exhaust the independently enforced whole-root quota first; that is
        # a failed study with uncertain writes, never a successful per-file claim.
        cpu=integer(limits['cpu_ns'],1); nano=integer(limits['cpu_rate_ns'],1)
        lag=finite(limits['qualified_enforcement_lag_seconds'])
        need(lag>0 and self.selection.get('enforcement_lag_qualified') is True, 'actual finite daemon/host enforcement lag qualification')
        # CPU is bounded by rate times running wall time, plus the separately
        # qualified scheduling/API/cgroup enforcement lag. Observed threshold
        # overrun fails; its conservative maximum is reserved prospectively.
        cutoff=min(cutoff,start+cpu/nano)
        reservation=cpu+math.ceil(nano*lag)
        gpu_reservation=len(self.selection['gpu_ids'])*(cutoff-start+lag)
        if self.scope is not None:
            need(self.scope['cpu_reserved']+reservation<=self.scope['cpu_cap']
                 and self.scope['gpu_reserved']+gpu_reservation<=self.scope['gpu_cap'],
                 'prospective whole episode native reservation before effects')
            self.scope['cpu_reserved']+=reservation;self.scope['gpu_reserved']+=gpu_reservation;self.scope['operations']+=1
        self.reserved_cpu+=reservation
        self.reserved_gpu+=gpu_reservation
        need(self.reserved_gpu<=finite(self.selection['whole_gpu_device_seconds']), 'prospective whole GPU-device-time reservation')
        need(self.reserved_cpu<=integer(self.selection['whole_cpu_ns'],1),'prospective full CPU reservation')
        need(len(self.operations)<integer(self.selection['operations'],1),'native operation cap')
        self.operations.append(operation)
        bind=[]; destinations=set()
        for row in mounts:
            need(set(row)=={'source','destination','pin','bytes_cap'},'complete immutable input descriptor')
            src=canonical(row['source']);dst=row['destination']
            need(type(dst) is str and dst.startswith(('/inputs/','/artifacts/')) and str(canonical(dst))==dst
                 and dst not in destinations and disjoint(src,output) and disjoint(dst,output_target),'bounded disjoint native input')
            destinations.add(dst)
            shared=self.gallery is not None and self.gallery.contains(src)
            if shared:self.gallery.verify(src,row['pin'])
            capture(src,row['pin'],row['bytes_cap'],self.budget,retain=False,readonly=True)
            if shared:self.gallery.verify(src,row['pin'])
            bind.append({'Type':'bind','Source':str(src),'Target':dst,'ReadOnly':True,
                         'BindOptions':{'Propagation':'rprivate'}})
        need(output.is_dir() and not list(output.iterdir()),'fresh empty native output directory')
        bind.append({'Type':'bind','Source':str(output),'Target':output_target,'ReadOnly':False,
                     'BindOptions':{'Propagation':'rprivate'}})
        nonce=hashlib.sha256(encoded([self.selection['study'],operation,source_pin])).hexdigest()
        labels={'neural049.study':self.selection['study'],'neural049.operation':operation,'neural049.nonce':nonce}
        config={'Image':self.selection['image_id'],'Cmd':argv,'Env':['PYTHONHASHSEED=0','OMP_NUM_THREADS=1',
                  'OPENBLAS_NUM_THREADS=1','MKL_NUM_THREADS=1','HOME=/scratch'],
                'WorkingDir':'/scratch','User':self.selection['uid_gid'],'AttachStdout':False,'AttachStderr':False,
                'NetworkDisabled':True,'Labels':labels,'HostConfig':{'NetworkMode':'none','ReadonlyRootfs':True,
                  'CapDrop':['ALL'],'SecurityOpt':['no-new-privileges:true'],'Privileged':False,
                  'PidsLimit':integer(limits['pids'],1),'Memory':integer(limits['memory_bytes'],1),
                  'MemorySwap':integer(limits['memory_bytes'],1),'NanoCpus':nano,
                  'AutoRemove':False,'Mounts':bind,'DeviceRequests':[{'Driver':'nvidia','DeviceIDs':self.selection['gpu_ids'],
                  'Capabilities':[['gpu']]}] if self.selection['gpu_ids'] else [],'Tmpfs':{'/scratch':'rw,noexec,nosuid,nodev,size='+str(integer(limits['scratch_bytes'],1))},
                  'LogConfig':{'Type':'local','Config':{'max-size':'1m','max-file':'1'}},
                  'Ulimits':[{'Name':'nofile','Soft':1024,'Hard':1024}]}}
        # A source-owned worker is mounted as an authenticated file. It can
        # interpret Python via the selected interpreter despite noexec scratch.
        intent={'kind':'native_intent','operation':operation,'config':pin(encoded(config)),'source':source_pin,
                'argv':argv,'mounts':mounts,'output':str(output),'limits':limits,'original_origin':self.budget.origin,
                'cutoff':cutoff,'started':start,'expected_artifacts':expected_artifacts,'optional_artifacts':optional_artifacts,'output_target':output_target,
                'cpu_reservation_including_enforcement_lag_ns':reservation,
                'gpu_device_seconds_reservation':gpu_reservation,'candidate_scope':None if self.scope is None else self.scope['identity'],
                'physical_daemon_io_and_gpu_telemetry':None}
        self.record(intent);cid=None;natural=False;retirement=None;last_state=None;observed_cpu=0;cpu_committed=False
        try:
            _,raw=self.request('POST','/containers/create',config,cutoff,statuses=(201,))
            created=parse(raw);cid=self.container_id(created['Id'])
            obj=self.inspect(cid,cutoff)
            need(obj['Image']==self.selection['image_id'] and obj['Config']['Labels']==labels
                 and obj['State']['Status']=='created','created exact image/ownership/state')
            self.record({'kind':'native_created','operation':operation,'container':cid,'config':intent['config'],
                         'original_origin':self.budget.origin,'cutoff':cutoff})
            self.request('POST','/containers/'+cid+'/start',None,cutoff,statuses=(204,))
            self.record({'kind':'native_started','operation':operation,'container':cid,'config':intent['config'],
                         'observed':self.budget.tick(cutoff)})
            observed_cpu=0
            while True:
                self.budget.tick(cutoff)
                obj=self.inspect(cid,cutoff)
                need(obj['Config']['Labels']==labels and obj['Image']==self.selection['image_id'],'owned running container identity')
                state=obj['State'];last_state={k:state.get(k) for k in ('Status','Running','Pid','ExitCode','OOMKilled','Error','StartedAt','FinishedAt')}
                if state['Status']=='exited' and state['Running'] is False and state['Pid']==0:
                    need(type(state['ExitCode']) is int and state['ExitCode']==0 and not state['OOMKilled']
                         and state.get('Error','')=='','natural successful zero exit')
                    natural=True;break
                need(state['Status'] in ('running','created'),'unexpected native status')
                _,statsraw=self.request('GET','/containers/'+cid+'/stats?stream=false&one-shot=true',None,cutoff)
                stats=parse(statsraw);current=integer(stats['cpu_stats']['cpu_usage']['total_usage'])
                need(current>=observed_cpu,'monotone container CPU counter');observed_cpu=current
                self.record({'kind':'native_cpu','operation':operation,'container':cid,'cpu_ns':current,
                             'observed':self.budget.tick(cutoff)})
                need(current<=cpu,'native CPU allowance exceeded')
                time.sleep(min(.05,max(0.,cutoff-time.monotonic())))
            # Total CPU includes the final interval; qualification must establish
            # retained exited-container statistics and finite enforcement lag.
            _,statsraw=self.request('GET','/containers/'+cid+'/stats?stream=false&one-shot=true',None,cutoff)
            stats=parse(statsraw);final_cpu=integer(stats['cpu_stats']['cpu_usage']['total_usage'])
            need(observed_cpu<=final_cpu<=cpu,'complete final CPU below allowance')
            self.used_cpu+=final_cpu;observed_cpu=final_cpu;cpu_committed=True
            artifacts={}
            actual=set();pending=[output]
            parents={str(relative(name).parent) for name in all_artifacts}
            parents|={str(parent) for name in all_artifacts for parent in relative(name).parents}
            while pending:
                directory=pending.pop()
                with os.scandir(directory) as scanner:
                    entries=list(scanner)
                for entry in entries:
                    path=Path(entry.path);name=str(path.relative_to(output));st=entry.stat(follow_symlinks=False)
                    need(not stat.S_ISLNK(st.st_mode),'no output symlink or indirect payload')
                    if stat.S_ISDIR(st.st_mode):
                        need(name in parents,'unplanned output directory');pending.append(path)
                    else:
                        need(stat.S_ISREG(st.st_mode) and name in all_artifacts,'exact planned regular output')
                        need(st.st_size<=all_artifacts[name],'native output cap');actual.add(name)
            need(set(expected_artifacts)<=actual<=set(all_artifacts),'required/conditional native output membership')
            for name in sorted(actual):
                path=output/relative(name);before=os.lstat(path)
                from core import seal_output
                artifacts[name]=seal_output(path,all_artifacts[name],(before.st_dev,before.st_ino),self.budget)
            natural_end=self.budget.tick(cutoff)
            retirement=self.close_owned(cid,labels,min(self.budget.deadline,cutoff+finite(limits['retirement_seconds'])))
            need(retirement.get('removed') is True and retirement.get('absence_confirmed') is True
                 and retirement.get('successful_clock_custody') is True and not retirement.get('unknown_state',False),
                 'successful phase requires bounded owned resource retirement')
            result={'kind':'native_completed','operation':operation,'container':cid,'config':intent['config'],
                    'source':source_pin,'artifacts':artifacts,'output':str(output),'cpu_ns':final_cpu,
                    'natural_exit':True,'exit_code':0,'retirement':retirement,'last_state':last_state,'original_origin':self.budget.origin,
                    'observed_end':natural_end,'retired_at':self.budget.tick(retirement['cutoff']),'cutoff':cutoff}
            for row in mounts:
                if self.gallery is not None and self.gallery.contains(row['source']):self.gallery.verify(row['source'],row['pin'])
            result['retired_at']=self.budget.tick(retirement['cutoff'])
            self.record(result);return result
        except BaseException as error:
            if cid is not None and retirement is None:
                retirement=self.close_owned(cid,labels,min(self.budget.deadline,cutoff+finite(limits['retirement_seconds'])))
            failure={'kind':'native_failed','operation':operation,'container':cid,'error_type':type(error).__name__,
                         'natural_observed':natural,'retirement':retirement,'last_state':last_state,
                         'unknown_created_resource':cid is None,'usage_may_be_incomplete':True,'observed_cpu_ns':observed_cpu,
                         'unknown_written_bytes_upper_bound':self.selection['whole_output_quota_bytes']}
            if not cpu_committed:self.used_cpu+=observed_cpu
            try:
                self.record(failure)
            except BaseException as publication:
                combined=BaseExceptionGroup('native operation and failure accounting publication failed',[error,publication])
                combined.failure_record=failure
                raise combined from None

            raise
