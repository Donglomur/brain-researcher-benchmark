"""Concrete protected-file authority. Earlier Q and later R are separate operands."""
import copy
import base64
import stat
import os
import time
from pathlib import PurePosixPath
from nb079_launch_contract import (canonical,pin,fields,require,resolve_pre_k,validate_pre_k,
    fixed_pre_k_projection,root_reference)
from n079_role_binding import ROLE_ORDER,role_map,validate_identity_slots,binding_contract
from nb079_authority_io import (integer,check_pin,descriptor,decode,absolute,relative,open_directory,
    ident,close_all,cleanup,secondary)
from nb079_authority_policy import PolicyCapture
from nb079_authority_validation import (SERVICES,ONE_SHOTS,projection,required_live,completed,
    observe_completion,remote_fifo,validate_issuer,validate_baseline,require_time,process_environment,process_argv,validate_blocked_observation)

INITIAL=('central_start','reader_ready','writer_open','blocked_finalizer')
LEGACY=('blocked_roles','release_role','observed_product','terminal_acknowledgement')


class AuthorityService:
    def __init__(self,policy_descriptor,request_descriptor,*,execution_enabled=False,bootstrap=None):
        self.capture=None;self.records=[];self.initial_done=[];self.released=[];self.observed={};self.H=None;self.terminal=None
        try:self.initialize(policy_descriptor,request_descriptor,execution_enabled=execution_enabled,bootstrap=bootstrap)
        except BaseException as error:error.authority_prefix=self.prefix();raise
    def initialize(self,policy_descriptor,request_descriptor,*,execution_enabled=False,bootstrap=None):
        self.capture=PolicyCapture(policy_descriptor,request_descriptor,'authority',execution_enabled=execution_enabled,bootstrap=bootstrap)
        self.q,self.r,self.io,self.clock=self.capture.q,self.capture.r,self.capture.io,self.capture.clock
        self.T=self.capture.objects['parent_template'];self.P=self.capture.objects['profile']
        self.source=self.q['admission_base']['source_manifest_pin'];self.profile_pin=pin(canonical(self.P))
        self.initial_done=[];self.sequence=0;self.released=[];self.observed={};self.records=[];self.closed=False;self.failed=False
        self.A0=None;self.K=None;self.H=None;self.blocked=None;self.baseline=None;self.terminal=None
        self.central=None;self.reader=None;self.writer=None;self.installed={}
        fields(self.q['protocol'],('issuer_pin','initial_requests','initial_responses','parent_nonce'))
        check_pin(self.q['protocol']['issuer_pin']);fields(self.q['protocol']['initial_requests'],INITIAL);fields(self.q['protocol']['initial_responses'],INITIAL)
        for names in (self.q['protocol']['initial_requests'],self.q['protocol']['initial_responses']):
            require(len(set(names.values()))==4 and all(type(x) is str and '/' not in x and x not in ('','.','..') for x in names.values()),'fixed unique initial protocol leaves')
        require(self.q['protocol']['parent_nonce']==self.T['authority']['nonce']==self.r['run_nonce'],'same original parent authority nonce')
        require(self.T['authority']['issuer_pin']==self.q['protocol']['issuer_pin'],'same earlier issuer policy identity')
        for which in ('request','response'):
            require(self.T['authority'][which+'_root']=={k:self.q['roots'][which][k] for k in ('path','identity')},'same exact parent protected namespace')
        fields(self.T['atomic_publication'],('publication','limits','request_root'))
        require(self.T['atomic_publication']['publication']==self.q['publication'] and self.T['atomic_publication']['request_root']==self.q['roots']['request'],'same earlier whole atomic publication selection and protected request root')
        require(self.T['authority']['response_owner_uid']==self.q['roots']['response']['owner_uid'],'same independently trusted response owner')
        require(self.P['memory_mode']==self.T['reader_admission']['memory_mode']=='fresh_lifetime' and
            self.T['composition']['configuration']['role_templates']['observer']['role_payload']['reader_admission']['memory_mode']=='fresh_lifetime',
            'only actual admitted fresh-lifetime reader route')
        fixed_pre_k_projection(self.T)
        self.validate_base()
        fields(self.q['bootstrap_program'],('python','bootstrap','max_source_bytes','max_bootstrap_metadata_bytes'))
        for key in ('python','bootstrap'):self.io.read(self.q['bootstrap_program'][key])
        for key in ('max_source_bytes','max_bootstrap_metadata_bytes'):integer(self.q['bootstrap_program'][key],1)
        require(self.q['central_observer_policy']==self.r['central_source_selection'],'same earlier Qc')
        require(decode(self.io.read(self.q['binding_contract']),self.io.encoding)==binding_contract(),'actual fixed source identity binding contract')
        self.request_stamps={};self.capture.check_roots();self.clock.tick()

    def validate_base(self):
        base=self.q['admission_base'];fields(base,('source_environment_receipt','custody_receipt','history_receipt','sources','source_manifest_pin','profile_pin','boot_id','environment'))
        require(base['boot_id']==self.q['runtime']['boot_id'],'same earlier admitted local boot identity')
        require(base['profile_pin']==self.profile_pin and pin(canonical(base['sources']))==base['source_manifest_pin'],'exact full source/profile base closure')
        require(type(base['sources']) is list and base['sources'],'full source set')
        for item in base['sources']:self.io.read(item)
        self.base_receipts={}
        for name,expected in (('source_environment_receipt',self.P['source_environment_pin']),('custody_receipt',self.P['custody_admission_pin']),('history_receipt',self.P['authoring_history_pin'])):
            require(base[name]['pin']==expected,'same earlier base admission receipt')
            self.base_receipts[name]=decode(self.io.read(base[name]),self.io.encoding)
        closure=self.capture.objects['source_closure']
        require(type(closure) is list and closure==base['sources'] and pin(canonical(closure))==self.source,'R original bare complete effective source closure')
        manifest=self.capture.objects['module_manifest'];require(all(item in base['sources'] for item in manifest['modules'].values()),'every actual parent module source in full closure')
        for role,template in self.T['composition']['configuration']['role_templates'].items():
            require(template['context']['clock']==self.r['original_clock'] and template['context']['role']==role,'all original selected role clocks')
        # Preserve full caps; root references are projections, never coercions.
        for role,root in self.T['output_roots'].items():
            ref=root_reference(root)
            require(self.T['composition']['configuration']['output_roots'][role]==ref and
                self.T['composition']['configuration']['role_templates'][role]['output']==ref,'same complete product/root projection')

    def emit(self,name,value,phase='scientific',response=False):
        root=self.q['roots']['response' if response else 'operands']
        result=self.io.write(root,name,value,phase)
        require(decode(self.io.read(result,phase,owner=root['owner_uid']),self.io.encoding)==value,'actual durable immutable issued body reread')
        return result

    def issue_admission(self,role,identity,roles,environment):
        base=self.q['admission_base'];clock=self.r['original_clock']
        issuer={'schema':'ach_typed_deployment_issuer_v1','source_manifest_pin':self.source,'profile_pin':self.profile_pin,
            'environment_pin':base['source_environment_receipt']['pin'],'custody_pin':base['custody_receipt']['pin'],
            'history_pin':base['history_receipt']['pin'],**{k+'_ns':v for k,v in clock.items()},'roles':roles}
        validate_issuer(issuer,roles,base,self.P,clock)
        I=self.emit(role+'-ISSUER.json',issuer)
        # Fresh body validation, not self-asserted pin equality.
        validate_issuer(decode(self.io.read(I),self.io.encoding),roles,base,self.P,clock)
        A={'schema':'ach_typed_source_admission_v1','execution_enabled':True,'issuer_receipt':I,
            **{k:copy.deepcopy(base[k]) for k in ('source_environment_receipt','custody_receipt','history_receipt','sources','source_manifest_pin','profile_pin')},
            'role':role,'role_identity':identity,'peers':({} if role=='finalizer' else roles),
            'scope_membership':identity['cgroup'],'boot_id':identity['boot_id'],'environment':environment}
        return I,self.emit(role+'-ADMISSION.json',A),A,issuer

    def central_start(self,body,request):
        fields(body,('schema','run_nonce','policy','request','source_pin','profile_pin','study_pin','original_clock','actual_central_identity','central_output_root','prepared_roots_pin'))
        require(body['schema']=='nb079_central_start_request_v1' and body['policy']==self.q['central_observer_policy'] and body['request']==self.capture.request_descriptor and
            body['run_nonce']==self.r['run_nonce'] and body['original_clock']==self.r['original_clock'],'exact original actual central start request')
        Qc=decode(self.io.read(body['policy']),self.io.encoding)
        require(body['source_pin']==Qc['source_pin']==pin(canonical(Qc['sources'])) and body['profile_pin']==Qc['profile']['pin'] and
            body['study_pin']==Qc['study_pin'] and body['prepared_roots_pin']==pin(canonical(Qc['roots'])) and
            Qc['original_clock']==body['original_clock'],'actual earlier central source/profile/study/prepared roots')
        for item in Qc['sources']:self.io.read(item,owner=Qc['descriptor_owners'][item['path']])
        self.io.read(Qc['python'],owner=Qc['descriptor_owners'][Qc['python']['path']])
        stamp=self.io.reads[-1]['identity'];require({'device':stamp[0],'inode':stamp[1]}==Qc['central_expected']['executable'],'actual central executable body/inode join')
        self.io.read(Qc['profile'],owner=Qc['descriptor_owners'][Qc['profile']['path']])
        for item in Qc['receipts'].values():self.io.read(item,owner=Qc['descriptor_owners'][item['path']])
        for root in Qc['roots'].values():self.io.directory(root)
        actual=self.capture.identity.verify(body['actual_central_identity'])
        require({k:actual[k] for k in Qc['central_expected']}==Qc['central_expected'],'actual central runtime matches earlier static fields')
        environment=self.capture.identity.proc('/proc/%d/environ'%actual['pid'],'scientific')
        observed=process_environment(environment)
        require(observed==Qc['environment'],'actual clean central environment; mismatched bytes never logged')
        expected=Qc['central_output'];fields(expected,('path','parent','owner_uid','mode'))
        root=body['central_output_root'];require(root['path']==expected['path']==self.r['central_output_path'] and
            root['owner_uid']==expected['owner_uid'] and root['mode']==expected['mode'] and
            str(PurePosixPath(root['path']).parent)==expected['parent']['path'],'actual fresh direct-child output path/owner/mode')
        self.io.directory(expected['parent']);self.io.directory(root)
        require(root['identity'] not in [r['identity'] for r in Qc['roots'].values()],'fresh central root not a prepared-root alias')
        Ac={'schema':'nb079_central_observer_admission_v1','run_nonce':body['run_nonce'],'policy_pin':body['policy']['pin'],
            'request_pin':body['request']['pin'],'central_start_request_pin':request['pin'],
            **{k:body[k] for k in ('source_pin','profile_pin','study_pin','original_clock','actual_central_identity','central_output_root','prepared_roots_pin')},
            'issuer_pin':Qc['receipts']['issuer']['pin'],'custody_pin':Qc['receipts']['custody']['pin'],'decision':'independently_admitted_actual_central'}
        require(Qc['detached_admission']=={'path':self.q['roots']['response']['path']+'/'+self.q['protocol']['initial_responses']['central_start'],'owner_uid':self.q['roots']['response']['owner_uid']},'earlier exact detached Ac namespace/owner')
        result=self.emit(self.q['protocol']['initial_responses']['central_start'],Ac,response=True)
        self.central={'request':body,'descriptor':request,'admission':Ac,'policy':Qc};return result

    def reader_ready(self,body,request):
        fields(body,('schema','run_nonce','request_pin','central_source_pin','original_clock','fifo_identity','reader_fd_observation','feeder_selection_pin'))
        require(body['schema']=='n079_opaque_reader_ready_request_v1' and body['run_nonce']==self.r['run_nonce'] and
            body['request_pin']==self.capture.request_descriptor['pin'] and body['central_source_pin']==self.central['policy']['source_pin'] and
            body['original_clock']==self.r['original_clock'] and body['fifo_identity']==self.r['credential_route']['fifo']['identity'] and
            body['feeder_selection_pin']==self.r['credential_route']['feeder_selection']['pin'],'exact postCLI reader-ready joins')
        observed=remote_fifo(self.capture,self.central['request']['actual_central_identity'],body['reader_fd_observation'],self.r['credential_route']['fifo'],os.O_RDONLY)
        self.reader={'descriptor':request,'body':body,'actual':observed}
        return self.emit(self.q['protocol']['initial_responses']['reader_ready'],{'schema':'nb079_reader_ready_admission_v1',
            'reader_ready_request_pin':request['pin'],'request_pin':self.capture.request_descriptor['pin'],'original_clock':self.r['original_clock'],
            'actual':observed,'decision':'verified_actual_read_only_fifo'},response=True)

    def writer_open(self,body,request):
        fields(body,('schema','run_nonce','reader_ready_request_pin','source_pin','feeder_selection_pin','original_clock','fifo_identity',
            'actual_writer_identity','writer_open_observation','deployment_selection_pin','spend_selection_pin','decision'))
        Qf=decode(self.io.read(self.r['credential_route']['feeder_selection']),self.io.encoding)
        require(body['schema']=='n079_opaque_writer_open_ack_v1' and body['decision']=='sole_selected_writer_opened' and
            body['run_nonce']==self.r['run_nonce'] and body['reader_ready_request_pin']==self.reader['descriptor']['pin'] and
            body['source_pin']==pin(canonical(Qf['sources'])) and body['feeder_selection_pin']==self.r['credential_route']['feeder_selection']['pin'] and
            body['original_clock']==self.r['original_clock'] and body['fifo_identity']==self.r['credential_route']['fifo']['identity'] and
            body['deployment_selection_pin']==Qf['deployment']['pin'] and body['spend_selection_pin']==Qf['spend_admission']['pin'],'exact actual independently selected writer-open')
        for item in Qf['sources']:self.io.read(item)
        deployment=decode(self.io.read(Qf['deployment']),self.io.encoding)
        require(deployment['schema']=='nb079_earlier_authority_deployment_v1' and deployment['kind']=='feeder' and deployment['capabilities']==['read_opaque_source_fd','sole_fifo_writer'] and deployment['source_selection_pin']==pin(canonical(Qf['sources'])) and deployment['runtime_pin']==pin(canonical(Qf['runtime'])) and deployment['roots_pin']==pin(canonical(Qf['roots'])) and deployment['bootstrap_pin']==pin(canonical(Qf['bootstrap'])) and deployment['publication_pin']==pin(canonical(Qf['publication'])) and deployment['original_clock']==self.r['original_clock'] and deployment['run_nonce']==self.r['run_nonce'],'earlier full independently selected feeder capability body')
        spend=decode(self.io.read(Qf['spend_admission']),self.io.encoding)
        require(spend['schema']=='nb079_earlier_opaque_key_access_v1' and spend['deployment_pin']==Qf['deployment']['pin'] and spend['original_clock']==self.r['original_clock'] and spend['source_fifo']==Qf['source_fifo'] and spend['destination_fifo']==self.r['credential_route']['fifo'] and spend['maximum_credential_bytes']==self.r['credential_route']['maximum_credential_bytes'] and spend['key_access_authorized'] is True and spend['provider_spend_selection_pin']==self.r['deployment_and_spend_selection']['spend']['pin'],'actual earlier full opaque source capability before issuer approves writer')
        actual=self.capture.identity.verify(body['actual_writer_identity']);runtime=Qf['runtime']
        require(actual['uid']==runtime['uid'] and actual['gid']==runtime['gid'] and actual['boot_id']==runtime['boot_id'] and
            actual['executable']==runtime['executable']['identity'] and actual['namespaces']==runtime['namespaces'] and
            actual['cgroup']==runtime['scope_membership'],'actual selected sole-writer runtime')
        environment=self.capture.identity.proc('/proc/%d/environ'%actual['pid'],'scientific')
        require(process_environment(environment)==runtime['environment'],'actual earlier feeder environment; no content logged')
        observed=remote_fifo(self.capture,actual,body['writer_open_observation'],self.r['credential_route']['fifo'],os.O_WRONLY)
        self.writer={'descriptor':request,'body':body,'actual':observed}
        return self.emit(self.q['protocol']['initial_responses']['writer_open'],{'schema':'nb079_writer_open_admission_v1',
            'writer_open_ack':request,'request_pin':self.capture.request_descriptor['pin'],'original_clock':self.r['original_clock'],
            'actual':observed,'decision':'verified_live_sole_writer'},response=True)

    def blocked_finalizer(self,body,request):
        fields(body,('schema','run_nonce','request_pin','source_pin','template_pin','profile_pin','original_clock',
            'reader_ready_request_pin','writer_open_ack_pin','actual_blocked_identity','actual_initial_argv','inherited_fifo_observation','blocked_observation'))
        require(body['schema']=='n079_blocked_finalizer_request_v1' and body['run_nonce']==self.r['run_nonce'] and
            body['request_pin']==self.capture.request_descriptor['pin'] and body['source_pin']==self.source and
            body['template_pin']==self.r['parent_template']['pin'] and body['profile_pin']==self.profile_pin and
            body['original_clock']==self.r['original_clock'] and body['reader_ready_request_pin']==self.reader['descriptor']['pin'] and
            body['writer_open_ack_pin']==self.writer['descriptor']['pin'],'actual existing blocked launch joins')
        actual=self.capture.identity.verify(body['actual_blocked_identity'])
        Qc=self.central['policy'];require({k:actual[k] for k in Qc['finalizer_expected']}==Qc['finalizer_expected'],'actual earlier finalizer static identity')
        environment=self.capture.identity.proc('/proc/%d/environ'%actual['pid'],'scientific')
        require(process_environment(environment)==Qc['environment']==self.q['admission_base']['environment'],'actual exact finalizer environment')
        fd=body['inherited_fifo_observation']['fd'];require(fd==self.reader['body']['reader_fd_observation']['fd'],'actual same inherited FD number after pass_fds')
        remote_fifo(self.capture,actual,body['inherited_fifo_observation'],self.r['credential_route']['fifo'],os.O_RDONLY)
        original=process_argv(self.capture.identity.proc('/proc/%d/cmdline'%actual['pid'],'scientific'))
        require(original==body['actual_initial_argv'],'actual original literal prelude argv')
        template=self.q['initial_argv_template'];require(type(template) is list and template==Qc['argv_template'] and all(template.count(k)==1 for k in ('@CREDENTIAL_FD@','@RELEASE_FD@','@READY_FD@')),'exact preselected prelude argv')
        # Release/ready descriptors are independently observed command operands;
        # the central source validates them against its actual owned pipes.
        require(len(template)==len(original),'whole actual prelude argv extent')
        for selected,value in zip(template,original):
            if selected=='@CREDENTIAL_FD@':require(value==str(fd),'actual inherited credential operand')
            elif selected in ('@RELEASE_FD@','@READY_FD@'):require(value.isdecimal() and int(value)>=3 and int(value)!=fd,'distinct actual private gate operand')
            else:require(selected==value,'all fixed original prelude command bytes')
        validate_blocked_observation(self.capture,body,Qc,actual,original,template,fd,self.r['credential_route']['fifo'])
        I,A,A_body,I_body=self.issue_admission('finalizer',actual,{'finalizer':actual},self.q['admission_base']['environment'])
        self.A0={'selection':A_body,'receipts':{**self.base_receipts,'issuer_receipt':I_body},'observed_identity':actual,'source_pin':self.source}
        K=resolve_pre_k(self.T,A_body,fd);validate_pre_k(self.T,K,A_body,fd)
        Kd=self.emit('FINALIZER-K.json',K);self.K=K
        B={'schema':'n079_detached_outer_configuration_admission_v1','configuration_pin':Kd['pin'],'source_pin':self.source,
            'profile_pin':self.profile_pin,'base_source_admission_pin':pin(canonical(A_body)),
            'custody_receipt_pin':A_body['custody_receipt']['pin'],'issuer_receipt_pin':I['pin'],'clock':self.r['original_clock'],
            'decision':'independently_selected_outer_configuration'}
        Bd=self.emit('FINALIZER-B0.json',B)
        argv=[self.q['bootstrap_program']['bootstrap']['path'],'--entry-mode','outer','--independently-enabled']
        for flag,item in (('role-config',Kd),('source-manifest',self.r['module_manifest']),('outer-profile',self.r['profile']),('configuration-admission',Bd)):
            argv.extend(['--'+flag,item['path'],'--'+flag+'-bytes',str(item['pin']['bytes']),'--'+flag+'-sha256',item['pin']['sha256']])
        argv.extend(['--max-source-bytes',str(self.q['bootstrap_program']['max_source_bytes']),
            '--max-bootstrap-metadata-bytes',str(self.q['bootstrap_program']['max_bootstrap_metadata_bytes'])])
        L={'schema':'n079_blocked_finalizer_release_v1','run_nonce':self.r['run_nonce'],'launch_request_pin':request['pin'],
            'request_pin':self.capture.request_descriptor['pin'],'source_pin':self.source,'original_clock':self.r['original_clock'],
            'actual_blocked_identity':actual,'initial_argv':original,'logical_bootstrap_argv':argv,'template_pin':self.r['parent_template']['pin'],
            'profile_pin':self.profile_pin,'reader_ready_request_pin':self.reader['descriptor']['pin'],'writer_open_ack_pin':self.writer['descriptor']['pin'],
            'inherited_fifo_observation':body['inherited_fifo_observation'],'I0':I,'A0':A,'K':Kd,'B0':Bd,
            'output_bindings':{k:K[k] for k in ('stream_root','report_root','output_roots')},'decision':'issued_exact_source_owned_release'}
        return self.emit(self.q['protocol']['initial_responses']['blocked_finalizer'],L,response=True)

    def verify_gate(self,role):
        actual=self.H[role];self.capture.identity.verify(actual);blueprint=self.K['launch']['role_blueprints'][role]
        env=self.capture.identity.proc('/proc/%d/environ'%actual['pid'],'scientific')
        require(process_environment(env)==blueprint['environment'],'actual selected blocked role environment')
        argv=process_argv(self.capture.identity.proc('/proc/%d/cmdline'%actual['pid'],'scientific'))
        launch=self.K['launch'];scope=launch['role_scopes'][role];clock=self.r['original_clock']
        require(len(argv)==14+len(blueprint['argv']) and argv[:4]==[launch['python'],'-I','-B',launch['gate_source']] and argv[5:12]==[str(blueprint['gate_message_bytes']),scope['path'],str(scope['identity']['device']),str(scope['identity']['inode']),str(clock['origin']),str(clock['scientific']),'independently-enabled'] and argv[13]=='--','actual original immutable blocked-gate command')
        require(all(argv[i].isdecimal() and int(argv[i])>=3 for i in (4,12)) and argv[4]!=argv[12],'actual distinct gate/ready descriptor operands')
        for selected,value in zip(blueprint['argv'],argv[14:]):
            if selected=='@READY_FD@':require(value.isdecimal() and int(value)>=3,'actual daemon ready operand')
            else:require(selected==value,'all immutable target argv tokens before release')
        if role=='provider':
            route=self.r['credential_route']['fifo'];fd=self.K['composition']['configuration']['role_templates']['provider']['role_payload']['credential_fd']
            remote_fifo(self.capture,actual,{'fd':fd,'device':route['identity']['device'],'inode':route['identity']['inode'],'owner_uid':route['owner_uid'],'mode':route['mode'],'access_mode':os.O_RDONLY,'nonblocking':True,'observed_ns':self.clock.tick()},route,os.O_RDONLY)

    def legacy(self,kind,body,request):
        fields(body,('schema','kind','sequence','nonce','source_pin','issuer_pin','clocks','payload'))
        phase='outer' if kind=='terminal_acknowledgement' else 'scientific'
        require(body['schema']=='n079_outer_authority_request_v1' and body['kind']==kind and type(body['sequence']) is int and
            body['sequence']==self.sequence+1 and body['nonce']==self.q['protocol']['parent_nonce'] and body['source_pin']==self.source and
            body['issuer_pin']==self.q['protocol']['issuer_pin'] and body['clocks']==self.r['original_clock'],'actual original parent wire fields/once-only sequence')
        self.sequence+=1;payload=body['payload']
        if kind=='blocked_roles':
            require(self.sequence==1 and self.blocked is None,'actual full blocked roster first')
            fields(payload,('roles','baseline','cpu_baseline'));self.blocked=payload['roles'];self.baseline=validate_baseline(payload['baseline'],self.K,self.r['original_clock'])
            self.H=role_map(self.A0,self.blocked)
            for role,value in self.H.items():
                self.capture.identity.verify(value)
                if role!='finalizer':require(value['cgroup']==self.K['launch']['role_scopes'][role]['membership'] and
                    self.blocked[role]['blueprint_pin']==pin(canonical(self.K['launch']['role_blueprints'][role])),'original actual blocked scope/blueprint')
            admitted={'payload_pin':pin(canonical(payload))}
        elif kind=='release_role':
            require(self.H is not None and len(self.released)<10,'complete original H before release')
            fields(payload,('role','blocked','previous_observations','baseline','metadata_proposal','metadata_proposal_body'))
            role=ROLE_ORDER[len(self.released)];require(payload['role']==role and payload['blocked']==self.blocked[role] and
                payload['baseline']==self.baseline and payload['previous_observations']==self.observed and
                set(self.observed)=={r for r in self.released if r in ONE_SHOTS},'exact role order and all completed original prerequisites')
            for live in required_live(role):self.capture.identity.verify(self.H[live])
            self.verify_gate(role)
            for old,row in self.observed.items():observe_completion(self.capture,row,old,self.H,self.source,self.K)
            from nb079_authority_verifier import verify_proposal
            self.capture.validate_loaded_sources(self.q['admission_base']['sources'])
            verified=verify_proposal(self.K['composition']['configuration'],self.A0,
                {'budget_transport':self.K['budget_transport'],'output_roots':self.K['output_roots']},role,self.observed,self.blocked,self.baseline,payload['metadata_proposal'],self.io)
            self.capture.validate_loaded_sources(self.q['admission_base']['sources'])
            proposal=verified['body'];require(proposal==payload['metadata_proposal_body'] and verified['H']==self.H,'actual whole proposal/body/full historical H')
            identity_record=decode(self.io.read(proposal['identity_binding']),self.io.encoding)
            require(identity_record['H']==self.H and identity_record['H_pin']==pin(canonical(self.H)) and
                identity_record['derived_configuration_projection_pin']==pin(canonical(projection(proposal['configuration']))), 'actual complete binding record and exact proposal projection')
            I,A,Ab,Ib=self.issue_admission(role,self.H[role],self.H,self.K['launch']['role_blueprints'][role]['environment'])
            installed=copy.deepcopy(proposal['configuration']);installed['context']['source_admission']=Ab
            effect=self.emit(role+'-EFFECT.json',{'schema':'nb079_role_effect_issuance_v1','role':role,'H_pin':pin(canonical(self.H)),
                'proposal_pin':payload['metadata_proposal']['pin'],'source_pin':self.source,'original_clock':self.r['original_clock']})
            installed['context']['effect_admission']['issuer_evidence']=effect['pin']
            require(projection(installed)==projection(proposal['configuration']),'only two fixed installed admission differences')
            validate_identity_slots(role,installed,self.K['composition']['configuration']['role_templates'],self.K['budget_transport'],self.H)
            require(Ab['peers']==self.H and Ab['role_identity']==self.H[role],'whole installed historical H')
            validate_issuer(decode(self.io.read(I),self.io.encoding),self.H,self.q['admission_base'],self.P,self.r['original_clock'])
            Kd=self.emit(role+'-K.json',installed)
            release={'schema':'ach_typed_role_release_v1','role':role,'pid':self.H[role]['pid'],'start_ticks':self.H[role]['start_ticks'],
                'initial_identity':self.H[role],'blueprint_pin':self.blocked[role]['blueprint_pin'],'source_pin':self.source,'profile_pin':self.profile_pin,
                'origin_ns':self.r['original_clock']['origin'],'scientific_ns':self.r['original_clock']['scientific'],
                'issuer_receipt_pin':I['pin'],'configuration_path':Kd['path'],'configuration_pin':Kd['pin']}
            admitted=self.emit(role+'-RELEASE.json',release);self.installed[role]={'issuer':I,'admission':A,'configuration':Kd,'release':admitted}
            self.released.append(role)
        elif kind=='observed_product':
            role=payload['role'];require(self.released and role==self.released[-1] and role in ONE_SHOTS and role not in self.observed,'one actual preceding produced completion')
            require(payload['release_pin']==self.installed[role]['release']['pin'] and payload['configuration_pin']==self.installed[role]['configuration']['pin'],'same source-owned admitted original process/configuration')
            self.capture.identity.verify(self.H['finalizer'])
            observe_completion(self.capture,payload,role,self.H,self.source,self.K);self.observed[role]=payload
            admitted={'payload_pin':pin(canonical(payload))}
        else:
            require(self.released==list(ROLE_ORDER) and set(self.observed)==set(ONE_SHOTS),'all six complete producers and all ten actual releases')
            self.capture.identity.verify(self.H['finalizer'],'outer')
            fields(payload,('grade_index','closed_scope_evidence','source_pin'));require(payload['source_pin']==self.source and
                payload['grade_index']==self.observed['grader']['index']['descriptor'],'actual target-last grade index')
            item=payload['closed_scope_evidence'];fields(item,('path','bytes','sha256'))
            require(item['path']=='CLOSED_SCOPE.json','source-owned closed-scope output leaf')
            closed=decode(self.io.read({'path':self.K['report_root']['path']+'/'+item['path'],'pin':{k:item[k] for k in ('bytes','sha256')}},'outer',owner=self.H['finalizer']['uid']),self.io.encoding)
            require(set(closed['roles'])==set(ROLE_ORDER),'all original complete role observations in closed scope')
            for role,row in closed['roles'].items():observe_completion(self.capture,row,role,self.H,self.source,self.K,'outer')
            admitted={'payload_pin':pin(canonical(payload))};self.terminal={'closed_scope':item,'grade_index':payload['grade_index']}
        response={'schema':'n079_outer_authority_response_v1','kind':kind,'sequence':self.sequence,'nonce':body['nonce'],
            'request_pin':request['pin'],'source_pin':self.source,'issuer_pin':body['issuer_pin'],'clocks':body['clocks'],
            'decision':'independently_approved_exact_request','admitted':admitted}
        return self.emit('%s-%04d.json'%(body['nonce'],self.sequence),response,phase,response=True)

    def handle_request(self,kind,request):
        try:
            require(not self.closed and not self.failed and kind in INITIAL+LEGACY,'live closed source-owned request kind');descriptor(request)
            phase='outer' if kind=='terminal_acknowledgement' else 'scientific'
            require(str(PurePosixPath(request['path']).parent)==self.q['roots']['request']['path'],'actual previously published protected request root')
            require(len(self.records)<self.q['limits']['maximum_requests'],'finite whole issuance work')
        except BaseException as error:
            self.failed=True;error.authority_prefix=self.prefix();raise
        record={'kind':kind,'request':request,'response':None,'status':'attempted'};self.records.append(record)
        try:
            self.capture.check_roots(phase);raw=self.io.read(request,phase,owner=self.q['roots']['request']['owner_uid']);record['raw_request_base64']=base64.b64encode(raw).decode('ascii');body=decode(raw,self.io.encoding)
            stamp=os.stat(request['path'],follow_symlinks=False)
            self.request_stamps[PurePosixPath(request['path']).name]=(stamp.st_dev,stamp.st_ino,stamp.st_size,stamp.st_mtime_ns,stamp.st_ctime_ns)
            require(raw==canonical(body),'actual published request uses exact source-owned ASCII canonical encoding')
            record['body']=body;record['raw_request_base64']=base64.b64encode(raw).decode('ascii')
            if kind in INITIAL:
                require(kind==INITIAL[len(self.initial_done)] and PurePosixPath(request['path']).name==self.q['protocol']['initial_requests'][kind],'fixed actual initial issuance order/leaf')
                result=getattr(self,kind)(body,request);self.initial_done.append(kind)
            else:
                require(self.initial_done==list(INITIAL),'all actual earlier initial admissions before parent issuance')
                require(PurePosixPath(request['path']).name=='%s-%04d.json'%(self.q['protocol']['parent_nonce'],self.sequence+1),'same actual parent sequence filename')
                result=self.legacy(kind,body,request)
            response_raw=self.io.read(result,phase,owner=self.q['roots']['response']['owner_uid'])
            record.update(response=result,raw_response_base64=base64.b64encode(response_raw).decode('ascii'),status='durably_issued')
            self.io.write(self.q['roots']['journal'],'EXCHANGE-%04d.json'%len(self.records),record,phase,log=True)
            self.clock.tick(phase);return result
        except BaseException as error:
            self.failed=True;record.update(status='failed_or_unknown',failure_type=type(error).__name__);error.authority_prefix=self.prefix();raise

    def inspect_request_namespace(self,next_name,phase='scientific'):
        self.capture.counters.charge({},'bounded request namespace enumeration before discovery effects',phase)
        fd=open_directory(self.q['roots']['request']['path']);first=None
        try:
            require(ident(fd)==self.q['roots']['request']['identity'],'same actual request root')
            names=[]
            with os.scandir(fd) as entries:
                for entry in entries:
                    require(len(names)<self.io.limits['directory_entries'],'finite actual request namespace')
                    require(entry.name in self.request_stamps or entry.name in (next_name,'.nb079-pending-'+next_name),'unknown, premature or replayed request refuses')
                    names.append(entry.name)
                    if entry.name in self.request_stamps:
                        st=entry.stat(follow_symlinks=False)
                        require((st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)==self.request_stamps[entry.name],'immutable completed request identity')
            require(set(self.request_stamps)<=set(names),'no removed historical request')
        except BaseException as error:first=error;raise
        finally:close_all([('request namespace close',lambda:os.close(fd))],first)

    def serve(self):
        first=None;terminal=None
        try:
            while self.terminal is None:
                phase='scientific' if len(self.released)<10 or 'grader' not in self.observed else 'outer'
                self.clock.tick(phase);self.capture.check_roots(phase)
                if len(self.initial_done)<len(INITIAL):kind=INITIAL[len(self.initial_done)];name=self.q['protocol']['initial_requests'][kind]
                else:kind=None;name='%s-%04d.json'%(self.q['protocol']['parent_nonce'],self.sequence+1)
                self.inspect_request_namespace(name,phase)
                path=self.q['roots']['request']['path']+'/'+name
                try:item,raw=self.io.unpinned(path,self.io.limits['file_bytes'],phase,owner=self.q['roots']['request']['owner_uid'])
                except FileNotFoundError:
                    now=self.clock.tick(phase);time.sleep(min(self.q['limits']['poll_ns'],self.r['original_clock'][phase]-now)/1e9);continue
                if kind is None:kind=decode(raw,self.io.encoding)['kind']
                self.handle_request(kind,item)
            terminal={'schema':'nb079_authority_terminal_v1','request_pin':self.capture.request_descriptor['pin'],
                'source_pin':pin(canonical(self.q['sources'])),'parent_source_pin':self.source,'original_clock':self.r['original_clock'],
                'complete':True,'actual_records':len(self.records),'closure':self.terminal,'prefix':self.prefix()}
            item=self.io.write(self.q['roots']['journal'],'AUTHORITY_TERMINAL.json',terminal,'outer',log=True)
            self.clock.tick('outer');terminal['artifact']=item
        except BaseException as error:first=error
        first=cleanup([('authority close',lambda:self.close(first))],first)
        if first is None:first=cleanup([('original authority return cutoff',lambda:self.clock.tick('outer'))])
        if first is not None:
            self.failed=True;first.authority_prefix=self.prefix()
            try:self.io.write(self.q['roots']['journal'],'AUTHORITY_FAILURE.json',first.authority_prefix,'outer',log=True)
            except BaseException as error:secondary(first,error,'authority failed-prefix publication')
            raise first
        return terminal

    def prefix(self):return {'records':list(self.records),'initial_done':list(self.initial_done),'released':list(self.released),
        'completed':list(self.observed),'H':self.H,'capture':None if self.capture is None else self.capture.prefix(),'terminal':self.terminal}
    def close(self,primary=None):self.closed=True
