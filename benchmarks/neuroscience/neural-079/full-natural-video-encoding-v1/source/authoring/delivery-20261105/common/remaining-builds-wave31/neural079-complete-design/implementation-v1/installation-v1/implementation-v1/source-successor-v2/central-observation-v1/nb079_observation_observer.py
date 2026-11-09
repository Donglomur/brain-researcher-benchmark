"""Actual source-owned finalizer observer; imports perform no runtime effects."""
import fcntl
import os
import signal
import stat
import subprocess
import sys
import time
from pathlib import PurePosixPath
from nb079_observation_common import (require,fields,integer,check_pin,body_pin,bounded_encode,bounded_decode,
    encoding_limits,Clock,collect_errors,close_all,attach_secondary)
from nb079_observation_io import (descriptor,absolute,root_shape,verify_root,open_directory,ProtectedIO,
    OrchestrationLedger,LinuxIdentity,DIMENSIONS)
from nb079_observation_capture import FinalizerPump
from nb079_observation_physical import profile,profile_pin

LIMITS=('metadata_bytes','source_bytes','stream_bytes','block_bytes','publication_bytes','live_buffer_bytes',
        'maximum_files','maximum_owned_fds','poll_ns','release_bytes','proc_bytes','cleanup_ns','readback_bytes','metadata_total_bytes')
ROOTS=('central_scope','finalizer_scope','parent_report','parent_stream','features','assembler','grams','references','controller','grader','authority_operands')
MODULES=('nb079_observation_common','nb079_observation_io','nb079_observation_capture','nb079_observation_physical',
         'nb079_observation_readback','nb079_observation_observer','nb079_launch_contract','nb079_entry_contract')
STATIC_ID=('uid','gid','boot_id','executable','namespaces','cgroup')

def clock_shape(value):
    fields(value,('origin','scientific','closeout','outer'),'original four cutoffs')
    values=[integer(value[k]) for k in ('origin','scientific','closeout','outer')]
    require(values==sorted(set(values)),'strictly increasing original clock')


def static_identity(value):
    fields(value,STATIC_ID,'earlier static process expectations')
    integer(value['uid']);integer(value['gid']);require(type(value['boot_id']) is str and value['boot_id'],'actual selected boot')
    fields(value['executable'],('device','inode'),'selected executable inode');integer(value['executable']['device']);integer(value['executable']['inode'],1)
    fields(value['namespaces'],('mnt','pid','user','net','ipc','uts','cgroup'),'exact Linux namespace roster')
    for pair in value['namespaces'].values():
        require(type(pair) is list and len(pair)==2,'namespace dev/inode');integer(pair[0]);integer(pair[1],1)
    require(type(value['cgroup']) is str and value['cgroup'].startswith('0::/') and value['cgroup'].endswith('\n'),'unified exact scope membership')


def full_identity(value):
    fields(value,('pid','start_ticks',*STATIC_ID),'complete actual original Linux identity')
    integer(value['pid'],1);integer(value['start_ticks']);static_identity({k:value[k] for k in STATIC_ID})


def validate_policy(value):
    fields(value,('schema','bootstrap','source_pin','parent_source_pin','sources','source_modules','python','prelude','profile','study_pin',
        'original_clock','environment','argv_template','central_expected','finalizer_expected','roots','output_roots',
        'central_output','receipts','descriptor_owners','detached_admission','readback_catalog'),'closed earlier central policy')
    require(value['schema']=='nb079_central_observer_policy_v1','earlier policy schema')
    clock_shape(value['original_clock']);check_pin(value['source_pin']);check_pin(value['parent_source_pin']);check_pin(value['study_pin'])
    boot=value['bootstrap'];fields(boot,('original_clock','owner_uids','encoding','limits','allocation','maximum_attempts'),'selected bounded bootstrap permission')
    require(boot['original_clock']==value['original_clock'],'no clock restart at policy capture');fields(boot['owner_uids'],('policy','request','admission'),'exact bootstrap descriptor owners');[integer(v) for v in boot['owner_uids'].values()];encoding_limits(boot['encoding'])
    fields(boot['limits'],LIMITS,'finite complete orchestration I/O caps')
    for x in boot['limits'].values():integer(x,1)
    limits=boot['limits'];require(limits['maximum_owned_fds']>=16,'complete fixed owned-FD floor before effects');require(limits['block_bytes']<=limits['stream_bytes'] and limits['release_bytes']<=limits['metadata_bytes'] and
        limits['metadata_bytes']<=boot['encoding']['bytes'] and 4*max(limits['metadata_bytes'],limits['block_bytes'])<=limits['live_buffer_bytes'],
        'preventive stream/metadata/temporary payload extents')
    fields(boot['allocation'],DIMENSIONS,'whole central allocation')
    for x in boot['allocation'].values():integer(x)
    integer(boot['maximum_attempts'],1)
    require(type(value['sources']) is list and value['sources'] and len(value['sources'])<=limits['maximum_files'],'complete finite source list')
    for item in value['sources']:descriptor(item)
    require(len({x['path'] for x in value['sources']})==len(value['sources']),'unique complete source files')
    require(body_pin(bounded_encode(value['sources'],boot['encoding']))==value['source_pin'],'exact complete central source list identity')
    fields(value['source_modules'],MODULES,'concrete loaded helper module bindings')
    for name,item in value['source_modules'].items():descriptor(item);require(item in value['sources'],'every actual helper in source closure')
    descriptor(value['python']);descriptor(value['prelude']);descriptor(value['profile']);require(value['prelude'] in value['sources'],'exact earlier prelude source in closure')
    require(type(value['environment']) is dict and all(type(k) is str and type(v) is str and k and '=' not in k and '\x00' not in k+v for k,v in value['environment'].items()),'exact clean process environment')
    argv=value['argv_template'];require(type(argv) is list and argv and all(type(x) is str and x and '\x00' not in x for x in argv),'literal selected argv')
    from nb079_entry_contract import validate_capture_argv
    validate_capture_argv(argv,value['python'],value['prelude'],value['original_clock'])
    require(int(argv[9])<=limits['source_bytes'],'captured prelude maximum fits earlier selected source cap')
    for token in ('@RELEASE_FD@','@READY_FD@','@CREDENTIAL_FD@'):require(sum(x.count(token) for x in argv)==1,'exact one source-owned FD placeholder')
    static_identity(value['central_expected']);static_identity(value['finalizer_expected'])
    fields(value['roots'],ROOTS,'all earlier prepared parent/scope roots')
    for root in value['roots'].values():root_shape(root)
    require(len({r['path'] for r in value['roots'].values()})==len(ROOTS) and
        len({(r['identity']['device'],r['identity']['inode']) for r in value['roots'].values()})==len(ROOTS),
        'distinct prepared scope/output roots, no inode aliases')
    fields(value['output_roots'],('features','assembler','grams','references','controller','grader'),'all six producer product roots')
    for role,root in value['output_roots'].items():
        fields(root,('path','identity','index_result_key','maximum_files','maximum_bytes'),'unchanged full product root')
        require(root['path']==value['roots'][role]['path'] and root['identity']==value['roots'][role]['identity'],'same protected original product root')
        keys=root['index_result_key'];require(type(keys) is list and 1<=len(keys)<=8 and all(type(k) is str and k for k in keys),'index key chain, not scalar string')
        integer(root['maximum_files'],1);integer(root['maximum_bytes'])
    output=value['central_output'];fields(output,('path','parent','owner_uid','mode'),'earlier fresh-output intent without future inode')
    absolute(output['path']);root_shape(output['parent']);integer(output['owner_uid']);integer(output['mode'])
    require(str(PurePosixPath(output['path']).parent)==output['parent']['path'] and output['mode']&0o022==0,'one protected intended output child')
    require(all(not(output['path']==r['path'] or output['path'].startswith(r['path'].rstrip('/')+'/') or
        r['path'].startswith(output['path'].rstrip('/')+'/')) for r in value['roots'].values()),
        'fresh central output separate from every original prepared private root')
    fields(value['receipts'],('issuer','custody','environment','history'),'independent earlier source/custody receipts')
    for item in value['receipts'].values():descriptor(item)
    require(type(value['descriptor_owners']) is dict,'exact earlier static descriptor owner lookup')
    for path,uid in value['descriptor_owners'].items():absolute(path);integer(uid)
    for item in value['sources']+[value['python'],value['prelude'],value['profile']]+list(value['receipts'].values()):
        require(item['path'] in value['descriptor_owners'],'every static descriptor owner explicitly selected')
    fields(value['detached_admission'],('path','owner_uid'),'fixed earlier future-admission namespace, no future hash')
    absolute(value['detached_admission']['path']);integer(value['detached_admission']['owner_uid'])
    require(value['detached_admission']['owner_uid']==boot['owner_uids']['admission'],'same selected later receipt owner')
    require(type(value['readback_catalog']) is list and len(value['readback_catalog'])<=limits['maximum_files'],'bounded typed optional source metadata catalog')
    require(len({(item['role'],item['path']) for item in value['readback_catalog']})==len(value['readback_catalog']),'unique selected metadata objects')
    for item in value['readback_catalog']:
        fields(item,('role','path','schema'),'selected source metadata catalog entry')
        require(item['role'] in value['output_roots'] and type(item['path']) is str and item['path'].endswith('.json') and
            type(item['schema']) is str and item['schema'].startswith('n079_'),'only source-selected JSON output metadata')
        relative=PurePosixPath(item['path']);require(not relative.is_absolute() and '..' not in relative.parts and str(relative)==item['path'],'safe catalog relative path')
    return value


def validate_admission(admission,policy,configuration,request,own,output):
    fields(admission,('schema','run_nonce','policy_pin','request_pin','central_start_request_pin','source_pin','profile_pin','study_pin',
        'original_clock','actual_central_identity','central_output_root','prepared_roots_pin','issuer_pin','custody_pin','decision'),'exact detached actual central admission')
    require(admission['schema']=='nb079_central_observer_admission_v1' and admission['decision']=='independently_admitted_actual_central',
        'independent actual central admission disposition')
    clock_shape(admission['original_clock']);full_identity(admission['actual_central_identity']);root_shape(admission['central_output_root'])
    for key in ('policy_pin','request_pin','central_start_request_pin','source_pin','profile_pin','study_pin','prepared_roots_pin','issuer_pin','custody_pin'):check_pin(admission[key])
    expected={'run_nonce':request['run_nonce'],'policy_pin':configuration['policy']['pin'],'request_pin':configuration['request']['pin'],
        'source_pin':policy['source_pin'],'profile_pin':policy['profile']['pin'],'study_pin':policy['study_pin'],
        'original_clock':policy['original_clock'],'actual_central_identity':own,'central_output_root':output,
        'prepared_roots_pin':body_pin(bounded_encode(policy['roots'],policy['bootstrap']['encoding'])),
        'issuer_pin':policy['receipts']['issuer']['pin'],'custody_pin':policy['receipts']['custody']['pin']}
    require(all(admission[k]==v for k,v in expected.items()),'whole independent admission/source/request/root/actual identity join')
    central_start={'schema':'nb079_central_start_request_v1','run_nonce':request['run_nonce'],
        'policy':configuration['policy'],'request':configuration['request'],'source_pin':policy['source_pin'],
        'profile_pin':policy['profile']['pin'],'study_pin':policy['study_pin'],'original_clock':policy['original_clock'],
        'actual_central_identity':own,'central_output_root':output,'prepared_roots_pin':expected['prepared_roots_pin']}
    require(body_pin(bounded_encode(central_start,policy['bootstrap']['encoding']))==admission['central_start_request_pin'],
        'canonical actual central_start publication joins exact earlier policy/request and observed current roots/identity')
    require({k:own[k] for k in STATIC_ID}==policy['central_expected'],'actual central matches earlier selected runtime facts')


class CentralObserver:
    def __init__(self,configuration):
        # This gate precedes reads, clocks, directories, host/process or FD effects.
        require(type(configuration) is dict and configuration.get('execution_enabled') is True,'central observer disabled before every effect')
        fields(configuration,('schema','execution_enabled','policy','request','admission','bootstrap'),'exact observer invocation')
        require(configuration['schema']=='nb079_central_observer_config_v1','central observer version')
        for name in ('policy','request','admission'):descriptor(configuration[name])
        boot=configuration['bootstrap'];fields(boot,('original_clock','owner_uids','encoding','limits','allocation','maximum_attempts'),'finite earlier bootstrap permission')
        clock_shape(boot['original_clock']);encoding_limits(boot['encoding']);fields(boot['limits'],LIMITS,'finite initial capture caps')
        for x in boot['limits'].values():integer(x,1)
        require(boot['limits']['maximum_owned_fds']>=16,'complete owned-FD floor before effects')
        require(4*max(boot['limits']['metadata_bytes'],boot['limits']['block_bytes'])<=boot['limits']['live_buffer_bytes'],'initial read/live cap before first capture')
        self.clock=Clock(**boot['original_clock']);self.ledger=OrchestrationLedger(boot['allocation'],self.clock,boot['maximum_attempts'])
        fields(boot['owner_uids'],('policy','request','admission'),'explicit initial descriptor ownership');[integer(v) for v in boot['owner_uids'].values()]
        self.io=ProtectedIO(self.clock,self.ledger,boot['limits'],boot['encoding'],boot['owner_uids']['policy'])
        self.configuration=bounded_decode(bounded_encode(configuration,boot['encoding']),boot['encoding'])
        self.policy=None;self.request=None;self.admission=None;self.root_fd=None;self.process=None;self.pidfd=None;self.pump=None
        self.release_write=None;self.ready_read=None;self.blocked=None;self.release_body=None;self.returned=None
        self.closed=False;self.forced=False;self.cleanup_errors=[];self.phase='bootstrap';self.credential_fd=None
        self.readback_done=False;self.failure_artifact=None;self.placement=None;self.pipe_observations=None
        try:self._construct(boot)
        except BaseException as error:self.close(error);self._carry(error);raise
    def _construct(self,boot):
        policy=self.io.json(self.configuration['policy'],owner_uid=boot['owner_uids']['policy']);validate_policy(policy)
        require(policy['bootstrap']==boot,'initial bootstrap caps/clock exactly earlier selected, no reset')
        self.policy=policy
        self.request=self.io.json(self.configuration['request'],owner_uid=boot['owner_uids']['request'])
        require(self.configuration['admission']['path']==policy['detached_admission']['path'],'fixed selected detached admission path')
        self.admission=self.io.json(self.configuration['admission'],owner_uid=boot['owner_uids']['admission'])
        require(self.request['schema']=='n079_central_launch_request_v1' and self.request['canonical_task_id']=='NEURAL-079' and
            self.request['condition']=='full_natural_video_encoding_v1' and self.request['central_source_selection']==self.configuration['policy'] and
            self.request['original_clock']==policy['original_clock'] and self.request['profile']==policy['profile'] and
            self.request['central_output_path']==policy['central_output']['path'],'actual separately captured earlier R/Qc/profile/output')
        from nb079_entry_contract import validate_orchestration,selected_row
        orchestration=self.json(self.request['orchestration_allocation'])
        self.orchestration=validate_orchestration(orchestration,policy['source_pin'],policy['original_clock'])
        require(selected_row(orchestration,'observer',policy['bootstrap'])==self.ledger.limits,
            'same original reserved observer allocation, including already attempted bootstrap reads')
        self.parent_sources=self.json(self.request['source_closure'])
        require(type(self.parent_sources) is list and self.parent_sources and len(self.parent_sources)<=boot['limits']['maximum_files'],
            'complete bounded original parent source closure')
        for item in self.parent_sources:descriptor(item)
        require(len({item['path'] for item in self.parent_sources})==len(self.parent_sources) and
            body_pin(bounded_encode(self.parent_sources,boot['encoding']))==policy['parent_source_pin'],
            'exact canonical original parent source-list identity')
        for item in self.parent_sources:self.io.capture(item,keep=False,maximum=boot['limits']['source_bytes'],owner_uid=self.owner(item['path']))
        for item in policy['receipts'].values():self.io.capture(item,owner_uid=self.owner(item['path']))
        for item in policy['sources']:self.io.capture(item,keep=False,maximum=boot['limits']['source_bytes'],owner_uid=self.owner(item['path']))
        self.io.capture(policy['python'],keep=False,maximum=boot['limits']['source_bytes'],owner_uid=self.owner(policy['python']['path']))
        for name,item in policy['source_modules'].items():
            module=sys.modules.get(name);require(module is not None and getattr(module,'__file__',None)==item['path'],'exact already source-closed named module; no fallback import')
        raw=self.io.capture(policy['profile'],owner_uid=self.owner(policy['profile']['path']));self.profile=profile(bounded_decode(raw,boot['encoding']))
        require(self.profile['memory_mode']=='fresh_lifetime' and raw==bounded_encode(self.profile,self.profile['encoding_limits']) and
                profile_pin(self.profile)==policy['profile']['pin'],'unchanged canonical typed profile, fresh_lifetime route only')
        require(dict(os.environ)==policy['environment'],'actual central exact admitted environment')
        self.identity=LinuxIdentity(self.clock,self.ledger,boot['limits']['proc_bytes'])
        own=self.identity.observe(os.getpid());output=self.admission['central_output_root'];root_shape(output)
        expected=policy['central_output'];require(all(output[k]==expected[k] for k in ('path','owner_uid','mode')),'actual fresh output matches earlier intended path/custody')
        parent=open_directory(expected['parent']['path']);first=None
        try:verify_root(parent,expected['parent'])
        except BaseException as error:first=error;raise
        finally:close_all([('prepared output parent',lambda:os.close(parent))],first)
        for root in policy['roots'].values():
            fd=open_directory(root['path']);first=None
            try:verify_root(fd,root)
            except BaseException as error:first=error;raise
            finally:close_all([('prepared static root',lambda fd=fd:os.close(fd))],first)
        validate_admission(self.admission,policy,self.configuration,self.request,own,output)
        self.root_fd=open_directory(output['path']);verify_root(self.root_fd,output)
        iterator=os.scandir(self.root_fd);first=None
        try:require(next(iterator,None) is None,'fresh central audit output before observer writes')
        except BaseException as error:first=error;raise
        finally:close_all([('fresh output inventory iterator',iterator.close)],first)
        self.central_identity=own;self.phase='admitted';self.clock.tick('scientific')
    def owner(self,path):
        if path in self.policy['descriptor_owners']:return self.policy['descriptor_owners'][path]
        matches=[r for r in self.policy['roots'].values() if path.startswith(r['path'].rstrip('/')+'/')]
        require(len(matches)==1,'one exact earlier selected descriptor/root owner; no fallback')
        return matches[0]['owner_uid']
    def json(self,item,phase='scientific'):
        return self.io.json(item,phase,owner_uid=self.owner(item['path']))
    def _carry(self,error):
        try:error.nb079_central_prefix=self.snapshot()
        except BaseException as secondary:
            attach_secondary(error,secondary,'central failure-prefix attachment')
    def snapshot(self):
        return {'phase':self.phase,'request':self.configuration['request'],'policy':self.configuration['policy'],
            'admission':self.configuration['admission'],'blocked':self.blocked,'release':self.release_body,
            'placement':self.placement,'pipe_observations':self.pipe_observations,'wait':None if self.pump is None else self.pump.finished,'streams':{} if self.pump is None else self.pump.descriptors(),
            'forced_cleanup':self.forced,'ledger':self.ledger.snapshot(),'read_observations':list(self.io.observations),
            'cleanup_errors':list(self.cleanup_errors),'closed':self.closed,'failure_artifact':self.failure_artifact,
            'credential_content_read':False,'caller_credential_fd_owned':False,'physical_total_claim':False}
    def launch(self,argv_template,environment,credential_fd):
        require(self.phase=='admitted' and self.process is None and not self.closed,'one admitted launch attempt')
        self.clock.tick('scientific')
        require(argv_template==self.policy['argv_template'] and environment==self.policy['environment'],'exact earlier selected command/environment')
        integer(credential_fd,0);fdstat=os.fstat(credential_fd);flags=fcntl.fcntl(credential_fd,fcntl.F_GETFL)
        require(stat.S_ISFIFO(fdstat.st_mode) and flags&os.O_ACCMODE==os.O_RDONLY and flags&os.O_NONBLOCK,
                'actual inherited opaque read-only nonblocking FIFO metadata only')
        fifo=self.request['credential_route']['fifo'];require({'device':fdstat.st_dev,'inode':fdstat.st_ino}==fifo['identity'] and
                fdstat.st_uid==fifo['owner_uid'] and stat.S_IMODE(fdstat.st_mode)==fifo['mode'],'same selected existing FIFO inode/custody')
        self.credential_fd=credential_fd
        self.credential_observation={'fd':credential_fd,'device':fdstat.st_dev,'inode':fdstat.st_ino,'owner_uid':fdstat.st_uid,
            'mode':stat.S_IMODE(fdstat.st_mode),'access_mode':flags&os.O_ACCMODE,'nonblocking':bool(flags&os.O_NONBLOCK),
            'observed_ns':self.clock.tick('scientific')}
        release_read=None;ready_write=None;primary=None
        self.phase='launch_attempted'
        try:
            release_read,self.release_write=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
            self.ready_read,ready_write=os.pipe2(os.O_CLOEXEC|os.O_NONBLOCK)
            require(len({release_read,self.release_write,self.ready_read,ready_write,credential_fd})==5,'disjoint owned ready/release and caller credential descriptors')
            # Retain original pipe identity before parent copies close and the
            # prelude closes READY after R. Later issuance must not stat READY.
            pipe_observations={};self.pipe_observations=pipe_observations
            for name,child_fd in (('release',release_read),('ready',ready_write)):
                pipe_stat=os.fstat(child_fd)
                require(stat.S_ISFIFO(pipe_stat.st_mode),'owned original source gate pipe')
                pipe_observations[name]={'child_fd':child_fd,'device':pipe_stat.st_dev,'inode':pipe_stat.st_ino}
            require(pipe_observations['release']['inode']!=pipe_observations['ready']['inode'] or pipe_observations['release']['device']!=pipe_observations['ready']['device'],'distinct source gate pipe identities')
            substitutions={'@RELEASE_FD@':str(release_read),'@READY_FD@':str(ready_write),'@CREDENTIAL_FD@':str(credential_fd)}
            argv=list(argv_template)
            for marker,value in substitutions.items():argv=[item.replace(marker,value) for item in argv]
            self.ledger.charge({'process_starts':1},'exact owned prelude/finalizer Popen attempted')
            self.process=subprocess.Popen(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                env=environment,close_fds=True,pass_fds=(release_read,ready_write,credential_fd),start_new_session=True)
            self.pidfd=os.pidfd_open(self.process.pid,0)
            self.pump=FinalizerPump(self.root_fd,self.admission['central_output_root']['path'],self.clock,self.ledger,self.policy['bootstrap']['limits'])
            self.pump.attach(self.process,self.pidfd);self.actual_argv=argv
            self._place_and_unblock_prelude()
        except BaseException as error:primary=error
        owned=[]
        if release_read is not None:owned.append(('parent copy child release reader',lambda fd=release_read:os.close(fd)))
        if ready_write is not None:owned.append(('parent copy child readiness writer',lambda fd=ready_write:os.close(fd)))
        primary=collect_errors(owned,primary)
        if primary is not None:self.close(primary);self._carry(primary);raise primary
        try:return self.wait_ready()
        except BaseException as error:self.close(error);self._carry(error);raise
    def _place_and_unblock_prelude(self):
        """Move only this owned live child, then release its source-owned P gate."""
        require(self.process is not None and self.pidfd is not None and self.release_write is not None,
                'actual owned process/pidfd/release before scope placement')
        before=self.identity.observe(self.process.pid);full_identity(before)
        expected=self.policy['finalizer_expected'];root=self.policy['roots']['finalizer_scope']
        require(before['cgroup']==self.policy['central_expected']['cgroup'] and
            all(before[k]==expected[k] for k in STATIC_ID if k!='cgroup'),
            'actual owned child inherits admitted central scope and selected runtime before placement')
        raw=(str(self.process.pid)+'\n').encode('ascii')
        self.ledger.charge({'write_bytes':len(raw)+1},'owned child scope PID and one-byte P gate before writes')
        self.placement={'before':before,'selected_scope':root,'pid_write_bytes':0,'P_write_bytes':0,'after':None,
                        'scope_write_complete':False,'prelude_gate_complete':False}
        root_fd=None;member_fd=None;first=None
        try:
            root_fd=open_directory(root['path']);verify_root(root_fd,root)
            member_fd=os.open('cgroup.procs',os.O_WRONLY|os.O_NOFOLLOW,dir_fd=root_fd)
            observed=os.fstat(member_fd)
            require(stat.S_ISREG(observed.st_mode) and observed.st_uid==root['owner_uid'],
                    'actual selected scope membership interface')
            self.clock.tick('scientific');written=os.write(member_fd,raw)
            integer(written);self.placement['pid_write_bytes']=written;self.ledger.returned('scope_membership_write_bytes',written)
            require(written==len(raw),'one complete bounded cgroup membership write; partial refuses')
            self.placement['scope_write_complete']=True
        except BaseException as error:first=error
        ops=[]
        if member_fd is not None:ops.append(('owned scope membership descriptor',lambda:os.close(member_fd)))
        if root_fd is not None:ops.append(('owned scope root descriptor',lambda:os.close(root_fd)))
        first=collect_errors(ops,first)
        if first is not None:raise first
        after=self.identity.observe(self.process.pid);full_identity(after)
        require(after['pid']==before['pid'] and after['start_ticks']==before['start_ticks'] and
            {k:after[k] for k in STATIC_ID}==expected,'same original live child in exact selected finalizer scope')
        self.placement['after']=after;self.clock.tick('scientific')
        written=os.write(self.release_write,b'P');integer(written);self.placement['P_write_bytes']=written
        self.ledger.returned('prelude_placement_gate_write_bytes',written)
        require(written==1,'exact one source-owned P byte before readiness and later L descriptor')
        self.placement['prelude_gate_complete']=True
    def wait_ready(self):
        if self.blocked is not None:return bounded_decode(bounded_encode(self.blocked,self.io.encoding),self.io.encoding)
        require(self.process is not None and self.ready_read is not None and not self.closed,'actual launched source-owned readiness path')
        fd,self.ready_read=self.ready_read,None;first=None
        try:self.pump.ready(fd)
        except BaseException as error:first=error;raise
        finally:close_all([('parent readiness reader',lambda:os.close(fd))],first)
        actual=self.identity.observe(self.process.pid)
        require({k:actual[k] for k in STATIC_ID}==self.policy['finalizer_expected'],'actual blocked finalizer matches earlier selected runtime/scope')
        observations=self.identity.argv_environment(self.process.pid,self.actual_argv,self.policy['environment'])
        self.blocked={'schema':'nb079_actual_blocked_finalizer_v1','identity':actual,'initial_argv':self.actual_argv,
            'argv_template':self.policy['argv_template'],'source_pin':self.policy['source_pin'],'request_pin':self.configuration['request']['pin'],
            'original_clock':self.policy['original_clock'],'ready_byte':'R','ready_eof':True,'observed_ns':self.clock.tick('scientific'),
            'process_observation':observations,'placement':self.placement,'pipe_observations':self.pipe_observations,'credential_fd':self.credential_fd,'credential_observation':self.credential_observation,'credential_content_read':False}
        self.phase='blocked_ready';return bounded_decode(bounded_encode(self.blocked,self.io.encoding),self.io.encoding)
    def release(self,descriptor_):
        require(self.phase=='blocked_ready' and self.release_write is not None and not self.closed,'one actual blocked release')
        descriptor(descriptor_);release=self.json(descriptor_)
        expected=('schema','run_nonce','launch_request_pin','request_pin','source_pin','original_clock','actual_blocked_identity',
            'initial_argv','logical_bootstrap_argv','template_pin','profile_pin','reader_ready_request_pin','writer_open_ack_pin',
            'inherited_fifo_observation','I0','A0','K','B0','output_bindings','decision')
        fields(release,expected,'exact source-owned immutable L')
        clock_shape(release['original_clock']);full_identity(release['actual_blocked_identity'])
        for key in ('launch_request_pin','request_pin','source_pin','template_pin','profile_pin','reader_ready_request_pin','writer_open_ack_pin'):check_pin(release[key])
        require(release['schema']=='n079_blocked_finalizer_release_v1' and release['decision']=='issued_exact_source_owned_release' and
            release['run_nonce']==self.request['run_nonce'] and release['request_pin']==self.configuration['request']['pin'] and
            release['source_pin']==self.policy['parent_source_pin'] and release['original_clock']==self.policy['original_clock'] and
            release['actual_blocked_identity']==self.blocked['identity'] and release['initial_argv']==self.actual_argv and
            release['template_pin']==self.request['parent_template']['pin'] and release['profile_pin']==self.policy['profile']['pin'],
            'whole actual L/blocked/source/request/original clock join')
        fifo_observation=release['inherited_fifo_observation']
        fields(fifo_observation,tuple(self.credential_observation),'complete actual inherited FIFO metadata')
        for key in ('fd','device','inode','owner_uid','mode','access_mode','observed_ns'):integer(fifo_observation[key])
        require(type(fifo_observation['nonblocking']) is bool,'typed actual nonblocking flag')
        require(all(fifo_observation[k]==v for k,v in self.credential_observation.items() if k!='observed_ns') and
            self.clock.origin<=fifo_observation['observed_ns']<=self.credential_observation['observed_ns'],
            'same actual inherited opaque descriptor metadata, no key content')
        operands={name:self.json(release[name]) for name in ('I0','A0','K','B0')}
        template=self.json(self.request['parent_template'])
        from nb079_launch_contract import validate_pre_k
        validate_pre_k(template,operands['K'],operands['A0'],self.credential_fd)
        require(operands['A0']['role_identity']==self.blocked['identity'] and operands['A0']['source_manifest_pin']==self.policy['parent_source_pin'] and
                operands['I0']['roles']=={'finalizer':self.blocked['identity']} and operands['A0']['issuer_receipt']==release['I0'] and
                operands['A0']['profile_pin']==self.policy['profile']['pin'],'actual initial finalizer-only issuer/admission/profile join')
        require(operands['K']['output_roots']==self.policy['output_roots'] and
            operands['K']['report_root']=={k:self.policy['roots']['parent_report'][k] for k in ('path','identity')} and
            operands['K']['stream_root']=={k:self.policy['roots']['parent_stream'][k] for k in ('path','identity')},
            'whole original selected output roots and caps, not projected-away ceilings')
        require(operands['B0']['configuration_pin']==body_pin(bounded_encode(operands['K'],self.profile['encoding_limits'])) and
                operands['B0']['clock']==self.policy['original_clock'],'exact detached K/original-clock admission')
        require(self.identity.observe(self.process.pid)==self.blocked['identity'],'same still-blocked actual finalizer before release')
        raw=bounded_encode(descriptor_,self.io.encoding);require(len(raw)<=self.policy['bootstrap']['limits']['release_bytes'],'complete finite source release frame')
        self.ledger.charge({'write_bytes':len(raw)},'complete actual finalizer release pipe before write')
        sent=0;fd,self.release_write=self.release_write,None;first=None
        try:
            while sent<len(raw):
                self.pump.once('scientific',0)
                try:n=os.write(fd,memoryview(raw)[sent:])
                except BlockingIOError:continue
                require(type(n) is int and 0<n<=len(raw)-sent,'positive complete release write');sent+=n;self.ledger.returned('release_write_bytes',n)
        except BaseException as error:first=error;error.nb079_release_prefix={'sent_bytes':sent,'descriptor':descriptor_};raise
        finally:close_all([('owned release writer',lambda:os.close(fd))],first)
        self.release_body={'descriptor':descriptor_,'body':release,'operands':operands};self.phase='released';self.clock.tick('scientific')
    def finish(self):
        require(self.phase=='released' and not self.closed,'actual released finalizer completion only')
        try:
            wait=self.pump.finish()
            root=self.policy['roots']['finalizer_scope'];fd=open_directory(root['path']);first=None
            try:verify_root(fd,root)
            except BaseException as error:first=error;raise
            finally:close_all([('finalizer scope identity descriptor',lambda:os.close(fd))],first)
            raw=self.identity.proc(root['path']+'/cgroup.events','outer')
            rows=dict(line.split() for line in raw.decode('ascii').splitlines())
            require(rows.get('populated')=='0','owned finalizer scope quiescent, no unknown live descendants')
            self.returned={'schema':'nb079_original_finalizer_return_v1','blocked':self.blocked,'release':self.release_body['descriptor'],
                'wait':dict(wait),'streams':self.pump.descriptors(),'quiescence':{'raw_ascii':raw.decode('ascii'),'pin':body_pin(raw)},
                'original_clock':self.policy['original_clock'],'source_pin':self.policy['source_pin'],'forced_cleanup':False,
                'finished_ns':self.clock.tick('outer')}
            self.phase='finished';return bounded_decode(bounded_encode(self.returned,self.io.encoding),self.io.encoding)
        except BaseException as error:self.close(error);self._carry(error);raise
    def readback(self,observed_return):
        require(self.phase=='finished' and observed_return==self.returned and not self.readback_done and not self.closed,'actual original return only; one selected readback')
        self.readback_done=True;self.phase='readback'
        try:
            from nb079_observation_readback import Readback
            result=Readback(self).run();self.phase='published';self.clock.tick('outer');return result
        except BaseException as error:self.close(error);self._carry(error);raise
    def close(self,primary=None):
        if self.closed:return
        self.closed=True;ops=[]
        if self.process is not None and self.process.returncode is None:
            self.forced=True
            def stop():
                if self.pidfd is not None:signal.pidfd_send_signal(self.pidfd,signal.SIGKILL)
                else:self.process.kill()
            ops.append(('owned child forced diagnostic stop',stop))
            ops.append(('owned child diagnostic reap',lambda:self.process.wait(timeout=self.policy['bootstrap']['limits']['cleanup_ns']/1e9)))
        if self.pump is not None:ops.append(('full stream pump cleanup',lambda:self.pump.close(primary)))
        if self.process is not None:
            for name in ('stdout','stderr'):
                stream=getattr(self.process,name,None)
                if stream is not None:setattr(self.process,name,None);ops.append(('owned '+name+' pipe close',stream.close))
        for key in ('release_write','ready_read','pidfd','root_fd'):
            fd=getattr(self,key);setattr(self,key,None)
            if fd is not None:ops.append((key+' close',lambda fd=fd:os.close(fd)))
        first=collect_errors(ops,primary)
        if first is not None:
            self.cleanup_errors=list(getattr(first,'typed_secondary_errors',[]));self._carry(first)
            if primary is None:raise first
        self.clock.tick('outer') if primary is None else None
