"""Actual source-owned role children, adapted from accepted ACh OwnedProcesses.

All ten children start blocked. Independent deployment custody installs dynamic
PID/configuration receipts before each ordered release. No scientific output is
accepted from a caller instead of the actual child and its complete streams.
"""
import os
import selectors
import subprocess
from ach_resource_common import require, fields, check_pin, integer, body_pin, bounded_encode, bounded_decode, read_body, write_all, close_all
from ach_resource_model import profile, profile_pin
from ach_resource_readers import identity
from ach_resource_admission import source_admission, live_identity
from n079_outer_common import configuration_projection, fresh_grade_input
from n079_role_binding import role_map
ROLE_ORDER = ('observer', 'issuer', 'supervisor', 'provider', 'features', 'assembler', 'grams', 'references', 'controller', 'grader')
DAEMONS = frozenset(('observer', 'issuer', 'supervisor', 'provider'))

class OwnedRoles:
    """Actual Popen ownership, gated source release, no supplied exit records.

Start creates blocked role gates. An independent issuer installs exact dynamic
PID/start/namespace/configuration receipts before release. That authority is an
explicit deployment interaction; neither bytes nor a caller Boolean establish
issuer authenticity. Existing environment custody must protect these files.
"""
    def __init__(self, configuration, selected, clock, admitted, pump, io, bindings):
        require(configuration.get('execution_enabled') is True, 'role launching disabled before effects')
        fields(configuration, ('execution_enabled','admission','role_blueprints','gate_source','gate_pin',
            'python','python_pin','common_scope_path','common_scope_identity','common_scope_membership','role_scopes'), 'complete source-owned role launch plan')
        self.cfg=configuration;self.selected=profile(selected);self.clock=clock;self.jobs={};self.closed=False
        self.admitted=admitted; self.pump=pump; self.io=io; self.bindings=bindings
        require(configuration['admission']==admitted['selection'], 'same independently observed finalizer admission')
        require(self.admitted['selection']['role']=='finalizer','independent finalizer role')
        io.read(configuration['gate_source'],configuration['gate_pin'])
        io.read(configuration['python'],configuration['python_pin'])
        require(set(configuration['role_blueprints']) == set(ROLE_ORDER) and set(configuration['role_scopes']) == set(ROLE_ORDER), 'all six service children and four complete trusted producers')

    def start(self):
        try:return self._start_owned()
        except BaseException as error:
            self.abort(error);raise

    def _start_owned(self):
        require(not self.jobs and not self.closed,'one source-owned process set')
        for role in ROLE_ORDER:
            blueprint = self.cfg['role_blueprints'][role]
            fields(blueprint,('argv','environment','stdout_endpoint','stderr_endpoint','gate_message_bytes','inherited_fds'), 'exact selected role blueprint')
            require(type(blueprint['argv']) is list and blueprint['argv'] and
                all(type(v) is str and '\x00' not in v for v in blueprint['argv']), 'exact selected command vector')
            require(blueprint['argv'][0]==self.cfg['python'],'same independently selected role interpreter')
            integer(blueprint['gate_message_bytes'],1)
            require(type(blueprint['inherited_fds']) is list and len(blueprint['inherited_fds'])==len(set(blueprint['inherited_fds'])),'exact separately admitted inherited FD roster')
            for inherited in blueprint['inherited_fds']:integer(inherited,3)
            require(role=='provider' or not blueprint['inherited_fds'],'only provider inherits separately admitted credential descriptors')
            for name in ('stdout_endpoint','stderr_endpoint'):
                endpoint=blueprint[name]
                require(self.selected['endpoint_owners'][endpoint]=='finalizer' and
                    self.selected['endpoint_layers'][endpoint]=='process_pipe_return_bytes','owned full-stream endpoint layer')
            require(blueprint['argv'].count('@READY_FD@')==(1 if role in DAEMONS else 0),'source-owned daemon startup-ready operand')
            gate_read,gate_write=os.pipe();ready_read=None;ready_write=None;startup_read=None;startup_write=None;process=None;primary=None
            job={'role':role,'released':False,'gate_write':gate_write,'process':None,'pidfd':None,
                'blueprint':blueprint,'initial_identity':None,'release_pin':None,'startup_read':None}
            self.jobs[role]=job
            try:
                ready_read,ready_write=os.pipe()
                if role in DAEMONS:startup_read,startup_write=os.pipe();job['startup_read']=startup_read
                target_argv=[str(startup_write) if item=='@READY_FD@' else item for item in blueprint['argv']]
                command=[self.cfg['python'],'-I','-B',self.cfg['gate_source'],str(gate_read),
                    str(blueprint['gate_message_bytes']),self.cfg['role_scopes'][role]['path'],
                    str(self.cfg['role_scopes'][role]['identity']['device']),str(self.cfg['role_scopes'][role]['identity']['inode']),
                    str(self.clock.origin),str(self.clock.scientific),'independently-enabled',str(ready_write),'--',*target_argv]
                self.io.audit.charge({'process_starts':1}, 'owned blocked role Popen attempt: '+role)
                process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                    env=blueprint['environment'],close_fds=True,pass_fds=tuple([gate_read,ready_write]+([] if startup_write is None else [startup_write])+blueprint['inherited_fds']),start_new_session=True)
                job['process']=process;self.pump.attach(role,job)
                job['pidfd']=os.pidfd_open(process.pid,0);self.pump.attach_pidfd(role)
                os.close(ready_write);ready_write=None
                if startup_write is not None:os.close(startup_write);startup_write=None
                self.pump.ready(ready_read,'scientific')
                self.io.audit.charge({'source_read_bytes':16*(self.selected['reader_limits']['file_bytes']+1)}, 'actual blocked child identity read bound')
                job['initial_identity']=live_identity(process.pid,self.selected,self.clock)
                require(job['initial_identity']['cgroup']==self.cfg['role_scopes'][role]['membership'], 'gate actually entered exact admitted child scope')
            except BaseException as error:primary=error;raise
            finally:
                operations=[('parent launch gate read close',lambda:os.close(gate_read))]
                if ready_read is not None:operations.append(('parent readiness read close',lambda:os.close(ready_read)))
                if ready_write is not None:operations.append(('parent readiness write close',lambda:os.close(ready_write)))
                if startup_write is not None:operations.append(('parent startup write close',lambda:os.close(startup_write)))
                close_all(operations,primary)
        return {role:{'initial_identity':job['initial_identity'],'blueprint_pin':body_pin(bounded_encode(job['blueprint'],self.selected['encoding_limits']))}
                for role,job in self.jobs.items()}

    def release(self,role,receipt_descriptor):
        try:return self._release_owned(role,receipt_descriptor)
        except BaseException as error:
            self.abort(error);raise

    def _release_owned(self,role,receipt_descriptor):
        """Read exact independent dynamic source selection, then release its gate."""
        order=ROLE_ORDER
        released=sum(1 for item in self.jobs.values() if item['released'])
        require(released<len(order) and role==order[released],'source-owned dependency-ready release order')
        job=self.jobs[role];require(not job['released'],'one dynamic admission release')
        fields(receipt_descriptor,('path','pin'),'independent role release receipt')
        raw=self.io.read(receipt_descriptor['path'],receipt_descriptor['pin'])
        receipt=bounded_decode(raw,self.selected['encoding_limits'])
        fields(receipt,('schema','role','pid','start_ticks','initial_identity','blueprint_pin','source_pin','profile_pin',
            'origin_ns','scientific_ns','issuer_receipt_pin','configuration_path','configuration_pin'),'exact dynamic role release')
        require(receipt['schema']=='ach_typed_role_release_v1' and receipt['role']==role and
            receipt['pid']==job['process'].pid and receipt['initial_identity']==job['initial_identity'] and
            receipt['start_ticks']==job['initial_identity']['start_ticks'] and
            receipt['blueprint_pin']==body_pin(bounded_encode(job['blueprint'],self.selected['encoding_limits'])) and
            receipt['source_pin']==self.admitted['source_pin'] and receipt['profile_pin']==profile_pin(self.selected) and
            receipt['origin_ns']==self.clock.origin and receipt['scientific_ns']==self.clock.scientific,'same actual blocked source-owned child')
        check_pin(receipt['issuer_receipt_pin'])
        # Authentication of the independent issuer/custody is part of admitted
        # deployment; this additionally reads and hashes the exact installed file.
        configuration_raw=self.io.read(receipt['configuration_path'],receipt['configuration_pin'])
        configuration=bounded_decode(configuration_raw,self.selected['encoding_limits'])
        require(role in self.bindings['proposals'], 'source-owned observed metadata proposal before release')
        proposed=self.bindings['proposals'][role]['configuration']
        require(configuration_projection(configuration,self.selected['encoding_limits'])==configuration_projection(proposed,self.selected['encoding_limits']), 'installed K preserves all exact proposed scientific/catalog/configuration fields')
        context=configuration['context']
        original_blocked={name:{'initial_identity':owned['initial_identity'],
            'blueprint_pin':body_pin(bounded_encode(owned['blueprint'],self.selected['encoding_limits']))}
            for name,owned in self.jobs.items()}
        H=role_map(self.admitted,original_blocked)
        require(context['source_admission']['peers']==H and
                context['source_admission']['role_identity']==H[role],
                'full original historical role roster, never substitute a reused or already exited PID')
        issuer_descriptor=context['source_admission']['issuer_receipt']
        fields(issuer_descriptor,('path','pin'),'actual later role issuer receipt')
        issuer_raw=self.io.read(issuer_descriptor['path'],issuer_descriptor['pin'])
        issuer_body=bounded_decode(issuer_raw,self.selected['encoding_limits'])
        fields(issuer_body,('schema','source_manifest_pin','profile_pin','environment_pin','custody_pin',
            'history_pin','origin_ns','scientific_ns','closeout_ns','outer_ns','roles'),'complete actual role issuer')
        require(receipt['issuer_receipt_pin']==issuer_descriptor['pin'] and
                issuer_body['schema']=='ach_typed_deployment_issuer_v1' and issuer_body['roles']==H and
                issuer_body['source_manifest_pin']==self.admitted['source_pin'] and
                issuer_body['profile_pin']==profile_pin(self.selected) and
                issuer_body['environment_pin']==self.selected['source_environment_pin'] and
                issuer_body['custody_pin']==self.selected['custody_admission_pin'] and
                issuer_body['history_pin']==self.selected['authoring_history_pin'] and
                all(issuer_body[k+'_ns']==getattr(self.clock,k) for k in ('origin','scientific','closeout','outer')),
                'fresh complete role issuer/source/profile/custody/original-clock body and exact release pin')
        require(context['role']==role and context['source_admission']['role_identity']==job['initial_identity'] and
            context['source_admission']['source_manifest_pin']==self.admitted['source_pin'] and
            context['clock']=={k:getattr(self.clock,k) for k in ('origin','scientific','closeout','outer')},
            'exact actual role/source/original clocks in dynamic configuration')
        require(receipt['configuration_pin']['bytes']<=job['blueprint']['gate_message_bytes'],'gate independently rereads full configuration within same selected cap')
        require(context['allocation']==self.bindings['allocation'] and configuration['endpoint_selection']==self.bindings['endpoint_selection'], 'same whole allocation and exact actual endpoint/source owners')
        require(context['source_admission']['environment']==job['blueprint']['environment'],'same exact configured execution environment')
        if role=='observer':require(configuration['role_payload']['baseline']==self.bindings['baseline'],'actual pre-child baseline in independently installed observer configuration')
        if role in self.bindings['output_roots']:
            root=self.bindings['output_roots'][role]
            require(configuration['output']=={k:root[k] for k in ('path','identity')},'independently selected exact output root before release')
        if role=='grader':job['grade_input_observation']=fresh_grade_input(configuration,self.admitted['source_pin'],self.io)
        job['configuration_pin']=receipt['configuration_pin'];job['configuration']=configuration
        self.io.audit.charge({'source_read_bytes':16*(self.selected['reader_limits']['file_bytes']+1)}, 'blocked child unchanged identity read bound')
        require(live_identity(job['process'].pid,self.selected,self.clock)==job['initial_identity'],'blocked child identity unchanged')
        require(len(raw)<=job['blueprint']['gate_message_bytes'],'complete release extent')
        # Nonblocking gate writes pump every other child stream throughout release.
        os.set_blocking(job['gate_write'],False);sent=0
        self.io.audit.charge({'write_bytes':len(raw)}, 'complete dynamic role release pipe')
        while sent<len(raw):
            self.pump.once('scientific',self.pump.limits['poll_ns'])
            try: amount=os.write(job['gate_write'],memoryview(raw)[sent:])
            except BlockingIOError: continue
            require(amount>0,'actual positive release write');sent+=amount
            self.io.audit.returned('gate_write_bytes',amount)
        fd=job['gate_write'];job['gate_write']=None;os.close(fd)
        job['released']=True;job['release_pin']=receipt_descriptor['pin']
        if job['startup_read'] is not None:
            ready=job['startup_read'];primary=None
            try:
                self.pump.ready(ready,'scientific')
                job['startup_ready_ns']=self.clock.tick('scientific')
            except BaseException as error:primary=error;raise
            finally:
                job['startup_read']=None
                close_all([('startup pipe close',lambda:os.close(ready))],primary)
        return configuration

    def close(self,primary=None):
        if self.closed:return
        self.closed=True;operations=[]
        for role,job in self.jobs.items():
            # Closing an unreleased gate makes its source-owned child refuse;
            # no other project's process is signalled or reaped here.
            for key in ('gate_write','pidfd','startup_read'):
                fd=job.get(key)
                if fd is not None:job[key]=None;operations.append((role+' '+key,lambda fd=fd:os.close(fd)))
            process=job.get('process')
            if process is not None:
                for stream in (process.stdout,process.stderr):
                    if stream is not None:operations.append((role+' stream close',stream.close))
        close_all(operations,primary)

    def abort(self,primary):
        # Diagnostic-only forced cleanup never restores a successful completion
        # or resets the scientific/producer cutoffs. Only the admitted owned
        # common scope is addressed, never a PID supplied by candidate code.
        if not self.jobs or all(job.get('forced_stop_requested') for job in self.jobs.values()):return
        try:
            primary.typed_owned_failure_prefix={'roles_started':list(self.jobs),
                'roles_released':[role for role,job in self.jobs.items() if job.get('released')],
                'stream_prefixes':self.pump.descriptors(),'actual_wait_prefixes':dict(self.pump.finished),
                'forced_cleanup_is_diagnostic_only':True}
        except BaseException:pass
        directory=None;control=None
        def stop_owned():
            nonlocal directory,control
            directory=os.open(self.cfg['common_scope_path'],os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            require(identity(directory)==self.cfg['common_scope_identity'],'same exclusively owned abort scope')
            control=os.open('cgroup.kill',os.O_WRONLY|os.O_NOFOLLOW,dir_fd=directory)
            actual=os.write(control,b'1');self.io.audit.returned('diagnostic_cgroup_write_bytes',actual)
            require(actual==1,'complete diagnostic owned-scope stop')
            for job in self.jobs.values():job['forced_stop_requested']=True
            self.io.audit.charge({'write_bytes':actual},'actual diagnostic owned-scope kill control return','outer')
        close_all([('diagnostic owned-scope stop',stop_owned)],primary)
        operations=[]
        if control is not None:operations.append(('owned stop descriptor close',lambda:os.close(control)))
        if directory is not None:operations.append(('owned scope descriptor close',lambda:os.close(directory)))
        close_all(operations,primary)

