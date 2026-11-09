"""Actual outer parent and finalizer. No execution occurs on import.

External authenticated configuration/issuer custody is mandatory. This source
constructs no admission, scientific result, native reference or tolerance.
"""
import hashlib
import os
import stat
from pathlib import PurePosixPath
from types import SimpleNamespace
from ach_resource_common import (require, fields, integer, check_pin, body_pin, bounded_encode,
    bounded_decode, collect_errors, close_all, Clock)
from ach_resource_model import profile, profile_pin, validate_snapshot
from ach_resource_admission import source_admission
from ach_resource_readers import identity, inventory, key_values
from n079_endpoint_owner import RoleEndpoints
from n079_outer_common import (AuditCounters, AuditIO, CountedReaders, CPUInterval,
    open_directory, signature, merge_endpoint_records, canonical_path, validate_initial_receipt)
from n079_outer_capture import StreamPump, FramedExchange, parse_terminal
from n079_outer_authority import FileAuthority
from n079_roles import OwnedRoles, ROLE_ORDER, DAEMONS
from n079_role_binding import role_map, validate_identity_slots, binding_contract
from n079_outer_common import configuration_projection

ONE_SHOTS = tuple(role for role in ROLE_ORDER if role not in DAEMONS)
FINISH_ORDER = ('provider','supervisor','issuer','observer')
LIMIT_FIELDS = ('file_bytes','artifact_bytes','stream_bytes','block_bytes','poll_ns',
                'maximum_audit_attempts','maximum_output_depth','maximum_output_path_chars')

class AtomicAuthorityIO:
    """Exact original audit interface; only protocol publication is adapted."""
    def __init__(self,base,selection,admitted):
        fields(selection,('publication','limits','request_root'),'earlier immutable atomic protocol selection')
        self.base=base;self.publisher=None;self.root=selection['request_root'];self.failed=None;self.returns={'source_read_bytes':0,'write_bytes':0}
        fields(self.root,('path','identity','owner_uid','mode'),'whole selected request-root custody')
        require(self.root['owner_uid']==admitted['observed_identity']['uid'] and self.root['mode']&0o022==0,'actual admitted finalizer owns protected request namespace')
        from n079_atomic_publication import AtomicPublication
        import n079_atomic_publication
        implementation=selection['publication']['implementation']
        require(implementation in admitted['selection']['sources'] and n079_atomic_publication.__file__==implementation['path'],'exact same admitted atomic implementation under parent-only namespace')
        base.audit.charge({'source_read_bytes':implementation['pin']['bytes']+selection['publication']['libc']['pin']['bytes']+2},'complete atomic implementation/libc capture before library loading')
        try:
            self.publisher=AtomicPublication(selection['publication'],
                {k:getattr(base.clock,k) for k in ('origin','scientific','closeout','outer')},
                selection['limits'],execution_enabled=True)
        except BaseException as error:
            self.failed=getattr(error,'atomic_prefix',None)
            raise collect_errors([('retain atomic constructor returns',lambda:self.sync_returns(self.failed))],error)
        self.sync_returns(self.publisher.prefix())
    def sync_returns(self,prefix):
        if prefix is None:return
        for category,key in (('source_read_bytes','returned_source_bytes'),('write_bytes','returned_write_bytes')):
            observed=integer(prefix[key]);require(observed>=self.returns[category],'monotone actual atomic returns')
            delta=observed-self.returns[category]
            if delta:self.base.audit.returned(category,delta)
            self.returns[category]=observed
    def __getattr__(self,name):return getattr(self.base,name)
    def write(self,root,name,raw,phase='scientific',log=False):
        require(identity(root)==self.root['identity'],'same original FileAuthority held request root')
        require(len(raw)<=self.base.limits['artifact_bytes'],'complete original artifact ceiling')
        delta={'write_bytes':len(raw)}
        if log:delta['log_bytes']=len(raw)
        self.base.audit.charge(delta,'whole atomic original authority request before publication',phase)
        first=None;result=None
        try:
            result=self.publisher.publish(self.root,name,raw,phase=phase)
            require(result['descriptor']=={'path':self.root['path']+'/'+name,'pin':body_pin(raw)},'same original request bytes and exact completed publication')
        except BaseException as error:self.failed=getattr(error,'atomic_prefix',None);first=error
        first=collect_errors([('retain complete or failed atomic returns',lambda:self.sync_returns(self.publisher.prefix()))],first)
        if first is not None:raise first
        return {'path':name,**body_pin(raw)}
    def prefix(self):return {'publisher':None if self.publisher is None else self.publisher.prefix(),'failed':self.failed,'joined_positive_returns':dict(self.returns)}


def selected_index(result, selector):
    require(type(selector) is list and 0<len(selector)<=8 and all(type(s) is str and s for s in selector),'bounded named result key chain')
    value=result
    for name in selector:
        require(type(value) is dict and name in value,'selected actual output descriptor exists')
        value=value[name]
    fields(value,('path','bytes','sha256'),'actual output descriptor')
    check_pin({k:value[k] for k in ('bytes','sha256')})
    return value


def join_index(index, inventory_rows):
    matches=[row for row in inventory_rows if row['path']==index['path']]
    require(len(matches)==1 and {k:matches[0][k] for k in ('path','bytes','sha256')}==index,
            'returned index exactly matches independently observed whole output inventory')
    return matches[0]


def observe_outputs(root, io, pump, phase):
    fields(root,('path','identity','index_result_key','maximum_files','maximum_bytes'), 'selected actual role product root')
    maximum_files=integer(root['maximum_files'],1); maximum_bytes=integer(root['maximum_bytes'])
    fd=open_directory(root['path']); first=None; rows=[]; total=0; seen=set()
    try:
        require(identity(fd)==root['identity'],'same actual admitted role product root')
        def walk(directory,prefix,depth):
            nonlocal total
            require(depth<=io.limits['maximum_output_depth'],'complete product inventory depth bound')
            before=os.fstat(directory); iterator=os.scandir(directory); inner=None
            try:
                for entry in iterator:
                    pump.once(phase,0); name=entry.name; path=prefix+name
                    require(name not in ('.','..') and '/' not in name and '\x00' not in name and
                            len(path)<=io.limits['maximum_output_path_chars'],'bounded ordinary output path')
                    st=entry.stat(follow_symlinks=False)
                    if stat.S_ISDIR(st.st_mode):
                        child=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=directory); error=None
                        try:
                            require(identity(child)=={'device':st.st_dev,'inode':st.st_ino},'stable observed product directory')
                            walk(child,path+'/',depth+1)
                        except BaseException as exc:error=exc;raise
                        finally:close_all([('product subdirectory close',lambda:os.close(child))],error)
                        continue
                    require(stat.S_ISREG(st.st_mode) and st.st_nlink==1,'ordinary single-link produced artifacts only')
                    require(len(rows)<maximum_files and total+st.st_size<=maximum_bytes,'whole product inventory extent before reads')
                    total+=st.st_size; ident=(st.st_dev,st.st_ino);require(ident not in seen,'no output inode alias');seen.add(ident)
                    io.audit.charge({'data_read_bytes':st.st_size+1},'full independent producer artifact hash including EOF probe',phase)
                    child=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=directory);error=None;h=hashlib.sha256();count=0
                    try:
                        require(signature(os.fstat(child))==signature(st),'same enumerated output body')
                        while True:
                            pump.once(phase,0); block=os.read(child,min(io.limits['block_bytes'],st.st_size-count+1))
                            io.audit.returned('data_read_bytes',len(block))
                            if not block:break
                            count+=len(block);require(count<=st.st_size,'output grew during observed hash');h.update(block)
                        require(count==st.st_size and signature(os.fstat(child))==signature(st),'full stable output including empty EOF')
                        rows.append({'path':path,'bytes':count,'sha256':h.hexdigest(),'identity':list(signature(st))})
                    except BaseException as exc:error=exc;raise
                    finally:close_all([('observed product file close',lambda:os.close(child))],error)
            except BaseException as exc:inner=exc;raise
            finally:close_all([('product iterator close',iterator.close)],inner)
            after=os.fstat(directory)
            require((before.st_dev,before.st_ino,before.st_mtime_ns,before.st_ctime_ns)==
                    (after.st_dev,after.st_ino,after.st_mtime_ns,after.st_ctime_ns),'product directory unchanged during complete inventory')
        walk(fd,'',0)
        return sorted(rows,key=lambda row:row['path'])
    except BaseException as exc:first=exc;raise
    finally:close_all([('product root close',lambda:os.close(fd))],first)


class OuterFinalizer:
    def __init__(self,configuration,selected,clock,bootstrap_cost,held_peak_fd,configuration_admission):
        require(type(configuration) is dict and configuration.get('execution_enabled') is True,'outer source disabled before effects')
        fields(configuration,('execution_enabled','admission','launch','reader_admission','endpoint_selection',
            'allocation','budget_transport','authority','stream_root','output_roots','inventory_roots',
            'report_root','cpu','limits','shutdown_endpoints','composition','atomic_publication'), 'complete selected outer configuration')
        require(type(clock) is Clock,'actual source-owned original monotonic clock')
        self.cfg=configuration;self.selected=profile(selected);self.clock=clock
        self.owned=None;self.pump=None;self.readers=None;self.authority=None;self.cpu=None;self.report=None;self.stream=None
        self.observations={};self.exchanges=[];self.final=None;self.closed=False;self.audit=None;self.endpoints=None
        self.io=None;self.authority_io=None;self.builder=None;self.proposals={};self.baseline=None;self.admitted=None;self.context=None
        self.configuration_pin=body_pin(bounded_encode(configuration,selected['encoding_limits']));self.original_profile_pin=profile_pin(selected)
        try:
            fields(configuration['limits'],LIMIT_FIELDS,'finite outer source bounds')
            for value in configuration['limits'].values():integer(value,1)
            require(configuration['limits']['block_bytes']<=configuration['limits']['stream_bytes']<=selected['reader_limits']['stream_bytes'] and
                configuration['limits']['file_bytes']<=selected['reader_limits']['file_bytes'],'selected full byte bounds')
            self.audit=AuditCounters(configuration['allocation'],configuration['admission']['source_manifest_pin'],
                selected['encoding_limits'],clock,configuration['limits']['maximum_audit_attempts'])
            require(type(bootstrap_cost) is dict and bootstrap_cost,'honest actual outer bootstrap source/receipt byte record required')
            self.audit.charge({'source_read_bytes':sum(integer(n) for n in bootstrap_cost.values()),'process_starts':1},
                'actual known finalizer bootstrap bytes and its already-started process')
            source=configuration['admission'];maximum=selected['reader_limits']['file_bytes']+1
            self.audit.charge({'source_read_bytes':sum(row['pin']['bytes']+1 for row in source['sources'])+20*maximum},
                'complete source/four receipts/live identity admission read bounds')
            self.admitted=source_admission(source,selected,clock)
            require(source['role']=='finalizer','actual separately admitted parent finalizer')
            self.io=AuditIO(self.audit,clock,selected['encoding_limits'],configuration['limits'])
            fields(configuration_admission,('path','pin'),'independently selected detached initial B descriptor outside K')
            braw=self.io.read(configuration_admission['path'],configuration_admission['pin'])
            b=bounded_decode(braw,selected['encoding_limits'])
            validate_initial_receipt(b,self.configuration_pin,self.admitted,selected,clock,selected['encoding_limits'])
            self.configuration_admission={'descriptor':configuration_admission,'body':b}
            # B is independently selected by outer bootstrap and not part of K.
            # Hashes join that authority; source does not mint or authenticate
            # external issuer custody from a caller-supplied success flag.
            self.context=SimpleNamespace(role='finalizer',profile=selected,clock=clock,admission=self.admitted,
                source_pin=self.admitted['source_pin'],encoding_limits=selected['encoding_limits'],audit=self.audit)
            self.context.tick=clock.tick
            self.endpoints=RoleEndpoints(self.context,configuration['endpoint_selection'])
            require(set(configuration['endpoint_selection']['roles'].values())==set(ROLE_ORDER)|{'finalizer'},'all eleven actual source endpoint owners')
            require(set(configuration['output_roots'])==set(ONE_SHOTS),'all six complete one-shot output roots')
            require(set(configuration['shutdown_endpoints'])==DAEMONS,'all four actual service finish endpoints')
            for key in ('stream_root','report_root'):
                root=configuration[key];fields(root,('path','identity'),'selected private audit root')
                fd=open_directory(root['path']);setattr(self,'stream' if key=='stream_root' else 'report',fd)
                require(identity(fd)==root['identity'],'same protected audit root')
                iterator=os.scandir(fd);inner=None
                try:require(next(iterator,None) is None,'fresh owned audit output namespace')
                except BaseException as exc:inner=exc;raise
                finally:close_all([('audit emptiness iterator',iterator.close)],inner)
            report_path=PurePosixPath(configuration['report_root']['path'])
            for root in configuration['inventory_roots']:
                path=PurePosixPath(canonical_path(root['path']))
                require(path!=report_path and path not in report_path.parents and report_path not in path.parents,
                    'terminal reports outside selected retained inventory; no recursive audit total')
            self.pump=StreamPump(self.stream,configuration['stream_root']['path'],selected,clock,self.endpoints,self.audit,configuration['limits'])
            self.readers=CountedReaders(configuration['reader_admission'],selected,clock,self.audit,held_peak_fd=held_peak_fd)
            self.baseline=self.readers.establish_baseline() # BEFORE all Popen children.
            self.cpu=CPUInterval(self.readers,configuration['cpu'],self.audit,clock)
            self.validate_launch()
            self.owned=OwnedRoles(configuration['launch'],selected,clock,self.admitted,self.pump,self.io,
                {'baseline':self.baseline,'allocation':configuration['allocation'],'endpoint_selection':configuration['endpoint_selection'],'output_roots':configuration['output_roots'],'proposals':self.proposals})
            require({k:configuration['atomic_publication']['request_root'][k] for k in ('path','identity')}==configuration['authority']['request_root'],'same fixed original request namespace')
            self.authority_io=AtomicAuthorityIO(self.io,configuration['atomic_publication'],self.admitted)
            self.authority=FileAuthority(configuration['authority'],self.admitted['source_pin'],self.authority_io,self.pump)
            composition=configuration['composition'];fields(composition,('source_path','source_pin','configuration'),'fixed metadata builder source/config')
            require({'path':composition['source_path'],'pin':composition['source_pin']} in source['sources'],'fixed metadata builder belongs to full source admission')
            self.io.read(composition['source_path'],composition['source_pin'])
            from n079_composition import MetadataBuilder
            import n079_composition
            require(canonical_path(n079_composition.__file__)==composition['source_path'],'exact selected fixed builder module path')
            self.builder=MetadataBuilder(composition['configuration'],self.io,self.admitted,
                outer_bindings={'budget_transport':configuration['budget_transport'],'output_roots':configuration['output_roots']})
            require(type(self.builder) is MetadataBuilder,'actual named source metadata builder')
        except BaseException as error:
            self.failure(error,False);self.close(error);self.failure(error,False);raise

    def validate_launch(self):
        launch=self.cfg['launch'];common=PurePosixPath(canonical_path(launch['common_scope_path']))
        require(launch['common_scope_identity']==self.cfg['reader_admission']['scope_identity'] and
                launch['common_scope_path']==self.cfg['reader_admission']['scope_path'],'same admitted common ancestor')
        paths=[];ids=[];members=[]; endpoints=[]
        for role in ROLE_ORDER:
            scope=launch['role_scopes'][role];fields(scope,('path','identity','membership'),'distinct actual child scope')
            path=PurePosixPath(canonical_path(scope['path']));require(common in path.parents,'child under common included scope')
            require(path not in paths and all(path not in x.parents and x not in path.parents for x in paths),'disjoint role child scopes')
            fd=open_directory(scope['path']);first=None
            try:require(identity(fd)==scope['identity'],'same independently created child cgroup')
            except BaseException as error:first=error;raise
            finally:close_all([('role cgroup identity descriptor',lambda:os.close(fd))],first)
            require(scope['identity'] not in ids,'unique role scope inode');paths.append(path);ids.append(scope['identity']);members.append(scope['membership'])
            blueprint=launch['role_blueprints'][role]
            require(type(blueprint['environment']) is dict and all(type(k) is type(v) is str and '\x00' not in k+v for k,v in blueprint['environment'].items()),'exact selected role environment')
            require(blueprint['gate_message_bytes']<=self.cfg['limits']['file_bytes'],'complete release bound')
            endpoints.extend(blueprint[name+'_endpoint'] for name in ('stdout','stderr'))
            require(all(self.cfg['endpoint_selection']['roles'][blueprint[name+'_endpoint']]=='finalizer' for name in ('stdout','stderr')),'actual finalizer owns every pipe')
        require(len(set(endpoints))==20,'twenty distinct admitted full-stream endpoint IDs')
        require(len(set(members))==10 and all(type(m) is str and m.startswith('0::/') and m.endswith('\n') for m in members),'exact unified cgroup memberships')
        own=self.admitted['observed_identity']['cgroup']
        require(own not in members,'parent outside every child scope')
        # The common membership is independently selected because host mount
        # paths do not determine names inside the selected cgroup namespace.
        common_membership=launch['common_scope_membership']
        require(type(common_membership) is str and common_membership.startswith('0::/') and common_membership.endswith('\n'), 'exact common unified cgroup membership')
        common_name=common_membership[3:-1].rstrip('/')
        require(common_name and all(m[3:-1].startswith(common_name+'/') for m in members), 'all role memberships beneath same common cgroup namespace')
        require(own.startswith('0::/') and own.endswith('\n') and own[3:-1]!=common_name and not own[3:-1].startswith(common_name+'/'), 'actual finalizer identity outside common cgroup')

    def transport(self,role,endpoint):
        job=self.owned.jobs[role]; config=job['configuration']
        return {'socket':config['services']['listen']['socket'],'peer':job['initial_identity'],'endpoint':endpoint}

    def reserve_audit(self):
        selected=self.cfg['budget_transport'];fields(selected,('socket','endpoint','participant'),'selected one central reservation transport')
        transport=self.transport('observer',selected['endpoint'])
        require(transport['socket']==selected['socket'],'same actual observer budget listener')
        request=self.audit.reservation_request(selected['participant'])
        exchange=FramedExchange(self.pump,self.context,self.endpoints,transport,request,'scientific');self.exchanges.append(exchange)
        reply=exchange.run();self.audit.bind_reservation(request,reply,self.selected['encoding_limits'])

    def role_quiescent(self,role,phase):
        scope=self.cfg['launch']['role_scopes'][role];fd=open_directory(scope['path']);control=None;first=None
        try:
            require(identity(fd)==scope['identity'],'same role scope after actual wait')
            self.audit.charge({'source_read_bytes':self.selected['reader_limits']['file_bytes']+1},'postexit actual role population read',phase)
            control=os.open('cgroup.events',os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
            from ach_resource_common import read_fd
            raw=read_fd(control,self.selected['reader_limits']['file_bytes'],self.clock,phase)
            self.audit.returned('source_read_bytes',len(raw))
            require(key_values(raw).get('populated')==0,'all role descendants stopped before output observation')
            return {'raw_ascii':raw.decode('ascii'),'pin':body_pin(raw),'observed_ns':self.clock.tick(phase)}
        except BaseException as error:first=error;raise
        finally:close_all(([] if control is None else [('role population file',lambda:os.close(control))])+[('role scope directory',lambda:os.close(fd))],first)

    def observe_role(self,role,phase):
        self.pump.wait_role(role,phase)
        before=self.role_quiescent(role,phase)
        streams=self.pump.descriptors(role)
        for name in ('stdout','stderr'):
            row=streams[role+'/'+name]
            require(row['eof'] and row['durable'] and row['bytes']==row['retained_bytes'] and row['sha256']==row['retained_sha256'], 'full exact retained stream join')
        stdout=streams[role+'/stdout'];raw=self.io.read(stdout['path'],{k:stdout[k] for k in ('bytes','sha256')},phase,self.cfg['limits']['stream_bytes'])
        terminal=parse_terminal(raw,role,self.admitted['source_pin'],self.selected['encoding_limits'])
        observation={'schema':'n079_outer_actual_role_observation_v1','role':role,'source_pin':self.admitted['source_pin'],
            'process_identity':self.owned.jobs[role]['initial_identity'],'release_pin':self.owned.jobs[role]['release_pin'],
            'configuration_pin':self.owned.jobs[role]['configuration_pin'],'wait':self.pump.finished[role],
            'streams':streams,'terminal':terminal,'products':None,'index':None,'population_before':before,'population_after':None,'fresh_grade_input_observation':self.owned.jobs[role].get('grade_input_observation')}
        if role in ONE_SHOTS:
            root=self.cfg['output_roots'][role]
            actual_output=self.owned.jobs[role]['configuration']['output']
            require(actual_output=={k:root[k] for k in ('path','identity')},'released role writes exact independently selected output root')
            rows=observe_outputs(root,self.io,self.pump,phase);index=selected_index(terminal['result'],root['index_result_key'])
            join_index(index,rows); raw=self.io.read(root['path']+'/'+index['path'],{k:index[k] for k in ('bytes','sha256')},phase)
            observation.update(products=rows,index={'descriptor':index,'body':bounded_decode(raw,self.selected['encoding_limits'])})
            if role=='grader':
                grade=observation['index']['body'];require(grade.get('schema')=='n079_protected_numeric_grade_v1','actual full protected grade schema')
                expected=[index]
                for chain in (('point_array','object'),('bootstrap','estimator_array','object'),('bootstrap','contrast_array','object')):
                    item=selected_index(grade,list(chain));join_index(item,rows);expected.append(item)
                require(len({x['path'] for x in expected})==4 and {x['path'] for x in rows}=={x['path'] for x in expected},'all four exact grader output artifacts')
        observation['population_after']=self.role_quiescent(role,phase)
        self.observations[role]=observation
        self.io.write(self.report,role+'-OBSERVATION.json',bounded_encode(observation,self.selected['encoding_limits']),phase)
        return observation

    def finish_service(self,role):
        require(role in DAEMONS,'fixed named service finish')
        request={'schema':'n079_service_request_v1','sequence':1,'operation':'finish','source_pin':self.admitted['source_pin'],'payload':{},'phase':'closeout'}
        exchange=FramedExchange(self.pump,self.context,self.endpoints,self.transport(role,self.cfg['shutdown_endpoints'][role]),request,'closeout')
        self.exchanges.append(exchange);reply=exchange.run()
        fields(reply,('schema','request_pin','source_pin','status','payload'),'complete actual service finish reply')
        require(reply['schema']=='n079_service_response_v1' and reply['request_pin']==body_pin(bounded_encode(request,self.selected['encoding_limits'])) and
            reply['source_pin']==self.admitted['source_pin'] and reply['status']=='complete' and reply['payload']=={'source_pin':self.admitted['source_pin']},'actual exact service finish joined')
        return self.observe_role(role,'closeout')

    def validate_identity_binding(self,role,proposal,blocked):
        item=proposal['identity_binding'];fields(item,('path','pin'),'source-owned binding record descriptor')
        expected_root=self.cfg['composition']['configuration']['proposal_root']['path']
        expected_name='%02d-%s-IDENTITY-BINDING.json' % (ROLE_ORDER.index(role),role)
        require(item['path']==expected_root+'/'+expected_name,'fixed role binding record path')
        raw=self.io.read(item['path'],item['pin']);record=bounded_decode(raw,self.selected['encoding_limits'])
        H=role_map(self.admitted,blocked);cfg=self.cfg['composition']['configuration']
        actual={'schema':'n079_actual_role_identity_binding_v1',
            'contract_pin':body_pin(bounded_encode(binding_contract(),self.selected['encoding_limits'])),
            'effective_source_pin':self.admitted['source_pin'],
            'static_role_template_pin':body_pin(bounded_encode(cfg['role_templates'][role],self.selected['encoding_limits'])),
            'original_clock_pin':cfg['original_clock_pin'],'H':H,
            'H_pin':body_pin(bounded_encode(H,self.selected['encoding_limits'])),
            'baseline_pin':body_pin(bounded_encode(self.baseline,self.selected['encoding_limits'])),
            'previous_observations_pin':body_pin(bounded_encode(self.observations,self.selected['encoding_limits'])),
            'derived_configuration_projection_pin':body_pin(bounded_encode(configuration_projection(proposal['configuration'],self.selected['encoding_limits']),self.selected['encoding_limits']))}
        require(record==actual,'complete exact source-owned historical H/projection binding')
        validate_identity_slots(role,proposal['configuration'],cfg['role_templates'],self.cfg['budget_transport'],H)
        return record

    def run(self):
        primary=None; result=None
        try:
            blocked=self.owned.start()
            self.authority.exchange('blocked_roles',{'roles':blocked,'baseline':self.baseline,'cpu_baseline':self.cpu.baseline})
            for role in ROLE_ORDER:
                proposal=self.builder.propose(role,
                    bounded_decode(bounded_encode(self.observations,self.selected['encoding_limits']),self.selected['encoding_limits']),
                    bounded_decode(bounded_encode(blocked,self.selected['encoding_limits']),self.selected['encoding_limits']),
                    bounded_decode(bounded_encode(self.baseline,self.selected['encoding_limits']),self.selected['encoding_limits']))
                fields(proposal,('path','pin'),'exact written metadata proposal only')
                raw=self.io.read(proposal['path'],proposal['pin'])
                proposal_body=bounded_decode(raw,self.selected['encoding_limits'])
                fields(proposal_body,('schema','role','source_pin','baseline_pin','observations_pin','blocked_identity_pin','identity_binding','configuration'),'exact fixed source configuration proposal')
                require(proposal_body['schema']=='n079_role_configuration_proposal_v2' and proposal_body['role']==role and
                    proposal_body['source_pin']==self.admitted['source_pin'] and
                    proposal_body['baseline_pin']==body_pin(bounded_encode(self.baseline,self.selected['encoding_limits'])) and
                    proposal_body['observations_pin']==body_pin(bounded_encode(self.observations,self.selected['encoding_limits'])) and
                    proposal_body['blocked_identity_pin']==body_pin(bounded_encode(blocked[role]['initial_identity'],self.selected['encoding_limits'])),
                    'metadata proposal joins exact actual baseline/upstream observations/blocked child/source')
                self.validate_identity_binding(role,proposal_body,blocked)
                self.proposals[role]=proposal_body
                receipt=self.authority.exchange('release_role',{'role':role,'blocked':blocked[role],
                    'previous_observations':self.observations,'baseline':self.baseline,'metadata_proposal':proposal,
                    'metadata_proposal_body':proposal_body})
                self.owned.release(role,receipt)
                if role=='observer':self.reserve_audit()
                if role in ONE_SHOTS:
                    observation=self.observe_role(role,'scientific')
                    self.authority.exchange('observed_product',observation)
            require(self.audit.reservation is not None,'complete finalizer partition centrally reserved')
            for role in FINISH_ORDER:self.finish_service(role)
            require(all(self.pump.complete(role) for role in ROLE_ORDER),'all actual children waited and both streams EOF')
            actual=self.readers.snapshot('outer',closed=True)
            cpu=self.cpu.finish()
            # Recheck quiescence after the separately read CPU counter.
            require(key_values(self.readers.read_named('cgroup.events','outer')).get('populated')==0,'common scope remains empty after CPU read')
            logical,inventory_raw,retained=inventory(self.cfg['inventory_roots'],self.selected,self.clock,
                custody_receipt_pin=self.selected['custody_admission_pin'])
            # inventory() reads names/stats only, no file payloads; encode and
            # retention publication remain explicit metadata/logical work.
            self.audit.charge({'source_read_bytes':len(inventory_raw)},'serialized complete logical inventory metadata','outer')
            for item in self.cfg['admission']['sources']:self.io.read(item['path'],item['pin'],'outer')
            self.io.read(self.cfg['launch']['python'],self.cfg['launch']['python_pin'],'outer')
            require(body_pin(bounded_encode(self.cfg,self.selected['encoding_limits']))==self.configuration_pin and profile_pin(self.selected)==self.original_profile_pin,'same entire selected outer configuration/profile after execution')
            require(dict(os.environ)==self.cfg['admission']['environment'],'same finalizer runtime environment after all child returns')
            records={role:row['terminal']['endpoint_record'] for role,row in self.observations.items()}
            records['finalizer']=self.endpoints.closed_record()
            transfers=merge_endpoint_records(records,self.cfg['endpoint_selection'],self.selected)
            raw_evidence={'actual':actual,'cpu':cpu,'roles':self.observations,'inventory':logical,'transfers':transfers}
            evidence_raw=bounded_encode(raw_evidence,self.selected['encoding_limits'])
            evidence=self.io.write(self.report,'CLOSED_SCOPE.json',evidence_raw,'outer')
            snapshot={'schema':'ach_local_resource_snapshot_v1','scope_id':self.selected['scope_id'],
                'profile_pin':profile_pin(self.selected),'source_pin':self.admitted['source_pin'],'origin_ns':self.clock.origin,
                'observed_ns':self.clock.tick('outer'),'state':'closed_scope','scope_identity':actual['scope_identity'],
                'storage':actual['storage'],'memory':actual['memory'],'retention':retained,'transfers':transfers,'pending_endpoints':[],
                'remote':{'hardware':'excluded_unknown','usage_evidence_pins':[]},'selected_unknown':[],
                'raw_evidence_pin':body_pin(evidence_raw)}
            validate_snapshot(snapshot,self.selected,require_closed=True)
            final={'schema':'n079_source_owned_outer_grade_v1','grade':self.observations['grader']['index'],
                'detached_initial_configuration_admission':self.configuration_admission,
                'grader_output_inventory':self.observations['grader']['products'],'grader_return':self.observations['grader'],
                'closed_snapshot':snapshot,'cpu_interval':cpu,'closed_scope_evidence':evidence,
                'all_role_observations':{r:{'wait':v['wait'],'source_pin':v['source_pin'],'configuration_pin':v['configuration_pin']} for r,v in self.observations.items()},
                'actual_outer_owned_children':len(self.owned.jobs),'full_fresh_plan_counts':{'producers':3770,'service_roles_including_finalizer':7,'total':3777},
                'terminal_boundary':'finalizer outside common scope; logical audit partition is included in whole allocation; no recursive physical or GPU claim',
                'audit_before_terminal_publication':self.audit.snapshot(),'complete':True}
            self.authority.exchange('terminal_acknowledgement',{'grade_index':self.observations['grader']['index']['descriptor'],
                'closed_scope_evidence':evidence,'source_pin':self.admitted['source_pin']},'outer')
            self.io.write(self.report,'ATOMIC_AUTHORITY_CLOSED.json',bounded_encode({
                'schema':'n079_atomic_authority_closed_v1','source_pin':self.admitted['source_pin'],
                'original_clock':{k:getattr(self.clock,k) for k in ('origin','scientific','closeout','outer')},
                'prefix':self.authority_io.prefix(),'parent_report_excluded_from_physical_inventory':True},
                self.selected['encoding_limits']),'outer')
            # Durable publication follows all substantive source/return/scope
            # checks; late cleanup failures still refuse outer success.
            result=self.io.write(self.report,'FINAL_GRADE.json',bounded_encode(final,self.selected['encoding_limits']),'outer')
            self.final=result
        except BaseException as error:primary=error
        if primary is not None:
            self.failure(primary,True)
            if self.owned is not None:
                primary=collect_errors([('owned scope forced diagnostic cleanup',lambda:self.owned.abort(primary)),
                    ('owned diagnostic wait and stream drain',self.drain_failure)],primary)
        primary=collect_errors([('outer all owned cleanup',lambda:self.close(primary))],primary)
        if primary is None:primary=collect_errors([('original outer return deadline',lambda:self.clock.tick('outer'))])
        if primary is not None:self.failure(primary,False);raise primary
        return {'path':self.cfg['report_root']['path']+'/'+result['path'],'bytes':result['bytes'],'sha256':result['sha256'],
                'audit_after_cleanup':self.audit.snapshot(),'terminal_boundary':'post-publication local return counters; not recursively in grade artifact'}

    def drain_failure(self):
        if self.pump is None:return
        while any(not self.pump.complete(role) for role in self.pump.jobs):
            self.pump.once('closeout',self.cfg['limits']['poll_ns'])
        # Forced stops remain failures, never natural-zero success.

    def failure(self,error,publish):
        record={'schema':'n079_outer_failure_prefix_v1','complete':False,'type':type(error).__name__,
            'streams':{} if self.pump is None else self.pump.descriptors(),
            'waits':{} if self.pump is None else dict(self.pump.finished),'observations':self.observations,
            'cpu_prefix':None if self.cpu is None else {'baseline':self.cpu.baseline,'final':self.cpu.final,'record':getattr(self.cpu,'record',None)},
            'fresh_grade_input_reads':{} if self.owned is None else {role:job['grade_input_observation'] for role,job in self.owned.jobs.items() if 'grade_input_observation' in job},
            'unknown_streams':[] if self.owned is None else [role+'/'+name for role in self.owned.jobs for name in ('stdout','stderr') if self.pump is None or (role,name) not in self.pump.records],
            'audit':None if self.audit is None else self.audit.snapshot(),
            'exchanges':[x.record for x in self.exchanges],
            'authority':[] if self.authority is None else self.authority.records,
            'atomic_authority':getattr(error,'atomic_prefix',None) if self.authority_io is None else self.authority_io.prefix(),
            'secondary_errors':list(getattr(error,'typed_secondary_errors',[])),
            'publication':{'attempted':False,'durable':False},'provisional_final_artifact':self.final}
        prior=getattr(error,'n079_outer_failure',None)
        if prior is not None:record['previous_publication']=prior['publication']
        error.n079_outer_failure=record
        if publish and self.io is not None and self.report is not None:
            record['publication']['attempted']=True
            try:
                descriptor=self.io.write(self.report,'FAILURE_PREFIX.json',bounded_encode(record,self.selected['encoding_limits']),'outer')
                record['publication']={'attempted':True,'durable':True,'descriptor':descriptor}
            except BaseException as secondary:
                from ach_resource_common import attach_secondary
                attach_secondary(error,secondary,'outer failed-prefix publication')
                record['publication']={'attempted':True,'durable':False,'type':type(secondary).__name__}

    def close(self,primary=None):
        if self.closed:return
        self.closed=True;ops=[]
        if self.authority is not None:ops.append(('file authority descriptors',lambda:self.authority.close(primary)))
        if self.pump is not None:ops.append(('full stream capture descriptors',lambda:self.pump.close(primary)))
        if self.readers is not None:ops.append(('common readers descriptors',lambda:self.readers.close(primary)))
        if self.owned is not None:ops.append(('actual owned role descriptors',lambda:self.owned.close(primary)))
        for name in ('stream','report'):
            fd=getattr(self,name);setattr(self,name,None)
            if fd is not None:ops.extend([(name+' directory sync',lambda fd=fd:os.fsync(fd)),(name+' directory close',lambda fd=fd:os.close(fd))])
        close_all(ops,primary)


def run_outer(configuration,selected,clock,*,bootstrap_cost,configuration_admission,held_peak_fd=None):
    return OuterFinalizer(configuration,selected,clock,bootstrap_cost,held_peak_fd,configuration_admission).run()
