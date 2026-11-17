"""Earlier Q capture and later R join; actual independently selected runtime facts."""
import os
import stat
import sys
from nb079_launch_contract import canonical,pin,fields,require
from nb079_entry_contract import validate_orchestration,selected_row
from nb079_authority_io import (Clock,Counters,Files,integer,descriptor,decode,check_pin,
    open_directory,close_all,ident,absolute)

R_FIELDS=('schema','canonical_task_id','condition','run_nonce','effective_parent_selection','parent_template','profile',
 'module_manifest','source_closure','original_clock','prepared_namespace_receipt','credential_route','external_authority',
 'central_source_selection','central_output_path','central_limits','orchestration_allocation','deployment_and_spend_selection')
EARLIER=('parent_template','profile','module_manifest','source_closure','prepared_namespace_receipt','central_source_selection','orchestration_allocation')
COMMON_POLICY=('schema','execution_enabled','kind','run_nonce','bootstrap','runtime','sources','roots','earlier','deployment','publication','limits')
AUTHORITY_EXTRA=('admission_base','bootstrap_program','binding_contract','initial_argv_template','protocol','central_observer_policy')
FEEDER_EXTRA=('source_fifo','reader_ready_request','writer_ack_name','spend_admission','reader_ready_protocol')


def bootstrap_capture(policy_descriptor,request_descriptor,enabled,bootstrap):
    # No clock, path, FD or environment operation precedes this flag check.
    require(enabled is True,'authority effects disabled before policy/request capture')
    fields(bootstrap,('original_clock','maximum_policy_bytes','maximum_request_bytes','maximum_bootstrap_read_bytes'))
    clock=Clock(bootstrap['original_clock'])
    for name in ('maximum_policy_bytes','maximum_request_bytes','maximum_bootstrap_read_bytes'):integer(bootstrap[name],1)
    descriptor(policy_descriptor);descriptor(request_descriptor)
    require(policy_descriptor['pin']['bytes']<=bootstrap['maximum_policy_bytes'] and
        request_descriptor['pin']['bytes']<=bootstrap['maximum_request_bytes'],'independently selected complete bootstrap extents')
    amount=policy_descriptor['pin']['bytes']+request_descriptor['pin']['bytes']+2
    require(amount<=bootstrap['maximum_bootstrap_read_bytes'],'bootstrap read charge before any read')
    maximum=max(bootstrap['maximum_policy_bytes'],bootstrap['maximum_request_bytes'])
    # Encoding limits are source-derived conservative maxima of the separately
    # selected byte ceilings; actual Q supplies its later finite work envelope.
    counters=Counters({'read_bytes':bootstrap['maximum_bootstrap_read_bytes'],'write_bytes':1,'log_bytes':1,'attempts':2,'pending_bytes':8*maximum},clock)
    limits={'file_bytes':maximum,'block_bytes':min(65536,maximum),'directory_entries':1,'path_chars':maximum,
        'encoding':{'bytes':8*maximum,'nodes':maximum,'depth':64,'string_chars':maximum}}
    io=Files(counters,clock,limits)
    try:
        qraw=io.read(policy_descriptor);q=decode(qraw,limits['encoding'])
        require(q.get('execution_enabled') is True,'independently enabled earlier policy required')
        rraw=io.read(request_descriptor);r=decode(rraw,limits['encoding'])
        clock.tick();return q,r,counters.snapshot(),io.reads
    except BaseException as error:error.authority_bootstrap_prefix=counters.snapshot();raise


class RuntimeIdentity:
    def __init__(self,io):self.io=io;self.observations=[]
    def proc(self,path,phase):
        self.io.counters.charge({'read_bytes':self.io.limits['file_bytes']+1},'actual bounded Linux process identity',phase)
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW);first=None;raw=bytearray()
        try:
            eof=False
            while len(raw)<=self.io.limits['file_bytes']:
                self.io.clock.tick(phase);block=os.read(fd,min(self.io.limits['block_bytes'],self.io.limits['file_bytes']+1-len(raw)))
                self.io.counters.observed('read_bytes',len(block))
                if not block:eof=True;break
                raw.extend(block);require(len(raw)<=self.io.limits['file_bytes'],'complete proc extent')
            require(eof,'whole proc identity EOF');return bytes(raw)
        except BaseException as error:first=error;raise
        finally:close_all([('live identity descriptor',lambda:os.close(fd))],first)
    def capture(self,pid,phase='scientific'):
        integer(pid,1);self.io.clock.tick(phase)
        raw=self.proc('/proc/%d/stat'%pid,phase);tail=raw[raw.rfind(b')')+2:].split()
        require(len(tail)>=20 and tail[19].isdigit(),'actual proc start field');start=int(tail[19])
        rows=dict(line.split(':',1) for line in self.proc('/proc/%d/status'%pid,phase).decode('ascii').splitlines() if ':' in line)
        uid=[int(x) for x in rows['Uid'].split()];gid=[int(x) for x in rows['Gid'].split()]
        require(len(uid)==len(gid)==4,'actual complete credential fields')
        executable=os.stat('/proc/%d/exe'%pid);namespaces={}
        for name in ('mnt','pid','user','net','ipc','uts','cgroup'):
            st=os.stat('/proc/%d/ns/%s'%(pid,name));namespaces[name]=[st.st_dev,st.st_ino]
        result={'pid':pid,'uid':uid[1],'gid':gid[1],'start_ticks':start,
            'boot_id':self.proc('/proc/sys/kernel/random/boot_id',phase).decode('ascii').strip(),
            'executable':{'device':executable.st_dev,'inode':executable.st_ino},'namespaces':namespaces,
            'cgroup':self.proc('/proc/%d/cgroup'%pid,phase).decode('ascii')}
        again=self.proc('/proc/%d/stat'%pid,phase)
        require(int(again[again.rfind(b')')+2:].split()[19])==start,'same process during actual identity capture')
        self.observations.append({'identity':result,'phase':phase,'observed_ns':self.io.clock.tick(phase)});return result
    def verify(self,expected,phase='scientific'):
        require(self.capture(expected['pid'],phase)==expected,'same original live full identity, no PID substitution');return expected


class PolicyCapture:
    def __init__(self,policy_descriptor,request_descriptor,kind,*,execution_enabled=False,bootstrap=None):
        self.bootstrap_prefix=None;self.counters=None;self.io=None;self.identity=None;self.allocation=None
        try:self.initialize(policy_descriptor,request_descriptor,kind,execution_enabled=execution_enabled,bootstrap=bootstrap)
        except BaseException as error:error.authority_policy_prefix=self.prefix();raise
    def initialize(self,policy_descriptor,request_descriptor,kind,*,execution_enabled=False,bootstrap=None):
        q,r,pre,reads=bootstrap_capture(policy_descriptor,request_descriptor,execution_enabled,bootstrap)
        self.bootstrap_prefix=pre
        extra=AUTHORITY_EXTRA if kind=='authority' else FEEDER_EXTRA
        fields(q,COMMON_POLICY+extra)
        require(q['schema']=='nb079_%s_policy_v1'%kind and q['kind']==kind and q['bootstrap']==bootstrap,'same earlier policy and separately selected bootstrap')
        fields(r,R_FIELDS)
        require(r['schema']=='n079_central_launch_request_v1' and r['canonical_task_id']=='NEURAL-079' and
            r['condition']=='full_natural_video_encoding_v1' and r['run_nonce']==q['run_nonce'] and
            r['original_clock']==bootstrap['original_clock'],'exact later complete request/source interval')
        require(type(q['run_nonce']) is str and q['run_nonce'] and len(q['run_nonce'])<=128 and
            all(c.isascii() and (c.isalnum() or c in '_-') for c in q['run_nonce']),'safe independently selected run nonce')
        target=r['external_authority'] if kind=='authority' else r['credential_route']['feeder_selection']
        require(target==policy_descriptor,'later R selects earlier Q; Q has no R/future hash field')
        fields(q['earlier'],EARLIER)
        require(all(q['earlier'][k]==r[k] for k in EARLIER),'same entirely earlier source/template/profile/root selections')
        fields(q['limits'],('counters','files','maximum_requests','poll_ns'));integer(q['limits']['maximum_requests'],1);integer(q['limits']['poll_ns'],1)
        self.policy_descriptor,self.request_descriptor=policy_descriptor,request_descriptor
        self.q,self.r,self.clock=q,r,Clock(bootstrap['original_clock'])
        self.counters=Counters(q['limits']['counters'],self.clock);self.io=Files(self.counters,self.clock,q['limits']['files'])
        self.counters.charge({'read_bytes':pre['attempted']['read_bytes']},'already attempted exact independent bootstrap reads; single transfer')
        self.counters.returned['read_bytes']=pre['positive_returns']['read_bytes'];self.bootstrap_prefix=pre;self.io.reads.extend(reads)
        self.identity=RuntimeIdentity(self.io);self.root_records={};self.source_records=[];self.objects={}
        for name,root in q['roots'].items():self.root_records[name]=self.io.directory(root)
        require(set(q['roots'])=={'request','response','operands','journal'},'fixed independently owned authority namespaces')
        from pathlib import PurePosixPath
        roots=[PurePosixPath(x['path']) for x in q['roots'].values()]
        require(len(set(roots))==4 and all(a not in b.parents for a in roots for b in roots if a!=b),'disjoint protected namespaces')
        require(type(q['sources']) is list and q['sources'],'complete authority source roster')
        paths=set()
        for source in q['sources']:
            descriptor(source);require(source['path'] not in paths,'unique selected source member');paths.add(source['path'])
            self.io.read(source);self.source_records.append(source)
        for name,item in q['earlier'].items():self.objects[name]=decode(self.io.read(item),self.io.encoding)
        allocation=self.objects['orchestration_allocation'];Qc=self.objects['central_source_selection']
        self.allocation_validation=validate_orchestration(allocation,Qc['source_pin'],r['original_clock'])
        self.allocation=selected_row(allocation,kind,q['limits'])
        fields(r['deployment_and_spend_selection'],('deployment','spend'))
        for item in r['deployment_and_spend_selection'].values():descriptor(item);self.io.read(item)
        self.validate_runtime()
        deployment=decode(self.io.read(q['deployment']),self.io.encoding)
        fields(deployment,('schema','kind','run_nonce','source_selection_pin','runtime_pin','roots_pin','bootstrap_pin','publication_pin','original_clock','capabilities'))
        require(deployment['schema']=='nb079_earlier_authority_deployment_v1' and deployment['kind']==kind and
            deployment['run_nonce']==q['run_nonce'] and deployment['source_selection_pin']==pin(canonical(q['sources'])) and
            deployment['runtime_pin']==pin(canonical(q['runtime'])) and deployment['roots_pin']==pin(canonical(q['roots'])) and
            deployment['bootstrap_pin']==pin(canonical(bootstrap)) and deployment['publication_pin']==pin(canonical(q['publication'])) and deployment['original_clock']==r['original_clock'],'actual earlier deployment selected exact source/runtime/root/bootstrap capability')
        needed=['issue_metadata'] if kind=='authority' else ['read_opaque_source_fd','sole_fifo_writer']
        require(deployment['capabilities']==needed,'closed earlier independently admitted capabilities')
        self.deployment=deployment
        require(q['publication']['implementation'] in q['sources'],'selected standalone atomic implementation in complete helper closure')
        for name in (('response','operands','journal') if kind=='authority' else ('request','journal')):
            require(q['roots'][name]['owner_uid']==self.actual_identity['uid'],'actual owning publisher UID for selected write roots')
        self.io.bind_publication(q['publication']);self.validate_loaded_sources();self.clock.tick()
    def validate_loaded_sources(self,extra=()):
        selected={item['path']:item for item in self.q['sources']}
        for item in extra:selected.setdefault(item['path'],item)
        for name,module in list(sys.modules.items()):
            if name.startswith('nb079_authority_') or name in ('nb079_launch_contract','nb079_entry_contract','nb079_atomic_publication','nb079_atomic_publication_authority','n079_role_binding') or (extra and name.startswith(('n079_','ach_'))):
                path=getattr(module,'__file__',None);require(path in selected,'every actual loaded helper/dependency module is independently source selected')
                self.io.read(selected[path])
    def validate_runtime(self):
        runtime=self.q['runtime'];fields(runtime,('uid','gid','boot_id','executable','namespaces','scope_membership','environment'))
        fields(runtime['executable'],('descriptor','identity'));self.io.read(runtime['executable']['descriptor'])
        stamp=self.io.reads[-1]['identity'];require({'device':stamp[0],'inode':stamp[1]}==runtime['executable']['identity'],'captured interpreter bytes are actual admitted executable inode')
        actual=self.identity.capture(os.getpid())
        require(actual['uid']==runtime['uid'] and actual['gid']==runtime['gid'] and actual['boot_id']==runtime['boot_id'] and
            actual['executable']==runtime['executable']['identity'] and actual['namespaces']==runtime['namespaces'] and
            actual['cgroup']==runtime['scope_membership'] and dict(os.environ)==runtime['environment'],'actual admitted authority runtime facts')
        self.actual_identity=actual
    def check_roots(self,phase='scientific'):
        for name,root in self.q['roots'].items():require(self.io.directory(root,phase)==self.root_records[name],'unchanged protected authority namespace')
    def prefix(self):return {'bootstrap':self.bootstrap_prefix,'counters':None if self.counters is None else self.counters.snapshot(),'reads':[] if self.io is None else list(self.io.reads),'writes':[] if self.io is None else list(self.io.writes),'identity_observations':[] if self.identity is None else list(self.identity.observations),'selected_original_allocation':self.allocation,'atomic_publication':None if self.io is None or self.io.publisher is None else self.io.publisher.prefix()}
