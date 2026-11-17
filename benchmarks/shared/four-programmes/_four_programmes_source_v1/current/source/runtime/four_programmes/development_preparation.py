"""Actual two-arm preparation, same-object promotion and truthful failure prefix.

Every filesystem effect is downstream of the exact admitted contract. This
module does not construct root/native qualifications, launch a worker, load a
model, or turn a descriptor into a live owner.
"""
import hashlib
import os
import time
from pathlib import PurePosixPath
from .common import Store, need, same, pin, integer, relative, bounded_size
from .backend_json import canonical
from .backend_capture import CanonicalPublisher, CapturedRecord
from .early_resources import EarlyResources, failure_observations
from .early_failure import _store_view, fail_after_selection_v3
from .early_construction import EarlyConstruction
from .early_issuer import AuthenticatedEarlyOpen
from .development_contract import DevelopmentContract, ContractAdmissionHandle, contract_identity_body, require_original_schedule
from .preparation_ownership import PreparationRawCustody, OwnedPreparationPath, OwnedParentAnchor
from .precommit_records import CONDITIONS, validate_type
from .source_closure_contract import require_prepared_source_closure_target

_PREPARED=object()

def _path_child(root,name):
    relative(name)
    return str(PurePosixPath(str(root))/name)

class ArmPreparationState:
    def __init__(self,handle,condition):
        self.handle=handle;self.condition=condition;self.meter=handle.owner.arms[condition]
        self.operations=[];self.cleanup=[];self.workspace=None;self.control=None
        self.entries=[];self.created_files=[];self.created_directories=[]
        self.identity=None;self.inventory=None;self.workspace_capture=None;self.state_capture=None
        self.request=None;self.exposure=None;self.launch=None
        self.workspace_closed='not_created';self.control_closed='not_created';self.descriptors_closed='not_created'
        self.publisher=None

class PreparationHandle:
    def __init__(self,token,contract,construction,inputs,outputs,workspace_parent,control_parent):
        need(token is _PREPARED,'fixed actual preparation producer')
        self._token=token;self.contract=contract;self.owner=contract.owner;self.construction=construction
        self.inputs=inputs;self.outputs=outputs;self.workspace_parent=workspace_parent
        self.control_parent=control_parent;self.pair_nonce=self.owner.parent.nonce
        self.pair_id=None;self.phase='registered';self.promotion=None;self.pair_plan=None
        self.raw_first=None;self.raw_secondaries=[];self.report_attempted=False;self.outcome=None
        self.failure_capture=None;self.report_capture=None;self.failure_prefix=None
        self.shared_operations=[];self.custody=PreparationRawCustody(self.owner)
        self.arms={c:ArmPreparationState(self,c) for c in CONDITIONS}
        self.host_publisher=None;self.process_started=False;self.launches={}
        self.source_closure_capture=contract.source_closure_capture
        self.cleanup_started=False
        self.final_report=None
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.raw_secondaries.append(error)
        self.phase='failed';self.promotion=None
        self.custody.retain(error,site)
    def clock(self):
        self.owner.check();now=time.monotonic_ns();integer(now)
        need(now<self.owner.parent.original_deadline,'same original preparation evidence deadline')
        return now
    def _error(self,error):
        rows=failure_observations(self.owner.parent)
        for index,(actual,_,_,_) in enumerate(self.owner.parent.raw_errors):
            if actual is error:return rows[index]
        need(False,'raw error was retained before diagnostic projection')
    def begin(self,operation,condition=None,relative_path=None,handle_ordinal=None):
        need(self.raw_first is None and not self.process_started and self.phase!='promoted',
             'ordinary preparation stops globally on first failure; no process before promotion')
        rows=self.shared_operations if condition is None else self.arms[condition].operations
        need(len(rows)<(32 if condition is None else 64),'original bounded attempted operation prefix')
        row={'schema':'ci_preparation_operation_v1','ordinal':len(rows),'condition':condition,
             'operation':operation,'relative_path':relative_path,'handle_ordinal':handle_ordinal,
             'started_ns':None,'finished_ns':None,'state':'pending','identity':None,
             'output':None,'first_error':None,'cost_prefix':self.owner.cost_prefix()}
        rows.append(row)  # Own the slot before all observations and effects.
        try:
            meter=self.owner.host if condition is None else self.arms[condition].meter
            meter.charge('retained_bytes',4096);meter.charge('work_units',4096)
            row['started_ns']=self.clock()
            return row
        except BaseException as error:
            self.fail_operation(row,error);raise
    def finish(self,row,*,output=None,identity=None):
        try:
            if output is not None:
                need(type(output) is CapturedRecord and output.owner is self.owner,'actual completed same-owner output')
                row['output']=output.pin
            if identity is not None:
                need(type(identity) is CapturedRecord and identity.kind=='OwnedPathIdentity' and
                     identity.owner is self.owner,'actual captured original path identity')
                row['identity']=identity.pin
            row['finished_ns']=self.clock()
            need(row['started_ns'] is not None and row['finished_ns']>=row['started_ns'],'original ordered operation interval')
            row['state']='complete';row['cost_prefix']=self.owner.cost_prefix()
            validate_type('PreparationOperation',row)
        except BaseException as error:
            self.fail_operation(row,error);raise
    def fail_operation(self,row,error):
        self.retain(error,'Preparation.'+row['operation'])
        row['state']='unknown' if row['started_ns'] is None else 'failed'
        try:
            row['first_error']=self._error(error);row['cost_prefix']=self.owner.cost_prefix()
        except BaseException as secondary:self.retain(secondary,'Preparation.operation_diagnostic')
    def prefix(self,arm):
        return {'schema':'ci_prepared_arm_prefix_v1','condition':arm.condition,
                'operations':list(arm.operations),'cleanup':list(arm.cleanup),
                'workspace_observation':None if arm.workspace_capture is None else arm.workspace_capture.pin,
                'state_preparation':None if arm.state_capture is None else arm.state_capture.pin,
                'request':None if arm.request is None else arm.request.pin,
                'exposure':None if arm.exposure is None else arm.exposure.pin,
                'launch_request':None if arm.launch is None else arm.launch.pin,
                'workspace_closure':arm.workspace_closed,'control_closure':arm.control_closed,
                'descriptor_closure':arm.descriptors_closed,'cost_prefix':self.owner.cost_prefix()}
    def body(self,success):
        body={'schema':'ci_preparation_success_v1' if success else 'ci_preparation_failure_v1',
              'status':'prepared' if success else 'failed','owner_binding':self.owner.parent.binding_pin,
              'selection':self.contract.admitted_open.selection_pin,'development_contract':self.contract.identity_pin,
              'pair_id':self.pair_id,'pair_nonce':self.pair_nonce,
              'pair_plan':None if self.pair_plan is None else self.pair_plan.pin,
              'arms':[self.prefix(self.arms[c]) for c in CONDITIONS],
              'shared_operations':list(self.shared_operations),'process_started':False,
              'cost_prefix':self.owner.cost_prefix()}
        if success:body['same_private_handle_promoted']=True
        else:
            errors=failure_observations(self.owner.parent)
            need(1<=len(errors)<=1025,'original bounded raw diagnostic prefix; never drop errors')
            body.update(phase='failed',first_error=errors[0],secondary_errors=errors[1:],
                retained_unknowns=sorted(self.owner.parent.unknown),dependent_execution_allowed=False,
                eligible_for_seal=False)
        validate_type('PreparationSuccess' if success else 'PreparationFailure',body)
        return body

def _publisher(handle,condition=None,terminal=False):
    store=handle.outputs
    if terminal:
        store=_store_view(store,handle.owner.terminal_host)
    elif condition is not None:store=_store_view(store,handle.owner.arms[condition])
    return CanonicalPublisher(handle.owner,store,maximum_bytes=handle.owner.plan['maximum_output_bytes'],
        maximum_members=handle.owner.plan['maximum_members'],maximum_depth=handle.owner.plan['maximum_depth'],
        condition=condition)

def _capture(handle,arm,suffix,kind,body):
    capture=arm.publisher.capture('development_'+arm.condition+'_'+suffix+'.json',kind,body)
    handle.owner.parent.known_records.append(capture.pin)
    return capture

def _effect(handle,arm,operation,path,method):
    # method is bound by the fixed callers below, not a public supplied provider.
    row=handle.begin(operation,arm.condition,path.name,path.ordinal)
    try:
        result=method()
        identity=None
        if operation.startswith('identify_'):
            identity=_capture(handle,arm,operation,'OwnedPathIdentity',result)
        handle.finish(row,identity=identity)
        return identity if identity is not None else result
    except BaseException as error:
        if row['first_error'] is None:handle.fail_operation(row,error)
        raise

def _admit_views(handle):
    construction=handle.construction
    result=construction.attempts['paired_views_manifest']
    need(result.complete and result.output_pin==handle.contract.admitted_open.issuance.result.product['paired_views'],
         'actual complete original paired-view capture is selected')
    raw=handle.outputs.read(result.output_pin,handle.owner.plan['maximum_input_bytes'],metadata=True)
    from .common import parse
    manifest=parse(raw,handle.owner.plan['maximum_input_bytes'])
    need(same(manifest,result.product),'same actual paired manifest bytes and original creator')
    # Fixed original source validator, bound to the same admitted SourceSession.
    # It is never a caller callback. No body is followed during validation.
    construction.public.validate_pair(manifest)
    return manifest

def _inventory(handle,arm,manifest):
    row=handle.begin('inventory',arm.condition,arm.workspace.name,arm.workspace.ordinal)
    try:
        members=manifest['common']+(manifest['author_code'] if arm.condition==CONDITIONS[1] else [])
        directories=handle.contract.recipe['empty_directories']
        for value in directories:relative(value)
        need(len(set(directories))==len(directories),'unique selected fresh directories')
        # Full list is retained and preadmitted; a capacity refusal never drops
        # source members or quietly changes the original 128-slot cleanup cap.
        component_names=set()
        for value in directories:
            for i in range(1,len(value.split('/'))+1):component_names.add('/'.join(value.split('/')[:i]))
        need(not any(m['destination'] in component_names for m in members),'no immutable member/directory collision')
        count=len(members)+len(component_names)
        cleanup_slots=6+4*len(members)+sum(len(name.split('/'))+3 for name in component_names)
        need(count<=8192 and count<=handle.contract.profile['maximum_files'] and cleanup_slots<=128,
             'complete selected view must fit original owned-resource cleanup slots before copying')
        arm.meter.charge('retained_bytes',count*4096)
        view_store=_store_view(handle.workspace_parent,arm.meter)
        for name in sorted(component_names,key=lambda s:(len(s.split('/')),s.encode('utf8'))):
            path=OwnedPreparationPath(handle.custody,arm.condition,view_store,arm.workspace.name+'/'+name,'directory')
            arm.created_directories.append(path)
            path.mkdir();path.open();path.identify()
            arm.entries.append({'schema':'ci_workspace_inventory_entry_v1','relative_path':name,
                'identity':path.identity,'content':None,'readonly':False})
        for member in members:
            expected=member['source'];arm.meter.charge('retained_bytes',expected['bytes']+1)
            source=(handle.outputs if expected==construction_abi_pin(handle) else handle.inputs)
            source=_store_view(source,arm.meter)
            raw=source.read(expected,manifest['member_cap_bytes'],metadata=False)
            path=OwnedPreparationPath(handle.custody,arm.condition,view_store,
                arm.workspace.name+'/'+member['destination'],'regular_file')
            arm.created_files.append(path);path.write_new(raw)
            arm.entries.append({'schema':'ci_workspace_inventory_entry_v1','relative_path':member['destination'],
                'identity':path.identity,'content':path.content,'readonly':path.readonly})
        arm.entries.sort(key=lambda r:r['relative_path'].encode('utf8'))
        # Observe the actual finite tree, not just the declared copy list.
        expected_children={name:[] for name in ['']+list(component_names)}
        for entry in arm.entries:
            parent,_,leaf=entry['relative_path'].rpartition('/')
            expected_children[parent].append(leaf)
        for name,children in expected_children.items():
            path=arm.workspace if not name else next(p for p in arm.created_directories if p.name==arm.workspace.name+'/'+name)
            path.assert_same_path();arm.meter.charge('work_units',4096+len(children)*256)
            actual=os.listdir(path.fd)
            need(type(actual) is list and all(type(x) is str for x in actual) and
                 sorted(actual)==sorted(children),'actual complete owned workspace inventory without extra entries')
        value={'schema':'ci_workspace_inventory_v1','condition':arm.condition,'pair_id':handle.pair_id,
            'workspace_identity':arm.workspace.identity,'entries':arm.entries,'observed_ns':handle.clock(),
            'complete':True,'cost_prefix':handle.owner.cost_prefix()}
        arm.inventory=_capture(handle,arm,'inventory','WorkspaceInventory',value)
        handle.finish(row,output=arm.inventory)
    except BaseException as error:
        if row['first_error'] is None:handle.fail_operation(row,error)
        raise

def construction_abi_pin(handle):
    return handle.construction.attempts['public_ABI'].output_pin

def prepare_fresh_pair_v1(handle):
    need(type(handle) is PreparationHandle and handle._token is _PREPARED and
         handle.owner.parent.preparation is handle,'actual same provisional preparation owner')
    manifest=_admit_views(handle);handle.phase='workspace_work'
    for condition in CONDITIONS:
        arm=handle.arms[condition];arm.publisher=_publisher(handle,condition)
        workspace_store=_store_view(handle.workspace_parent,arm.meter)
        control_store=_store_view(handle.control_parent,arm.meter)
        name=handle.pair_id+'-'+condition
        arm.workspace=OwnedPreparationPath(handle.custody,condition,workspace_store,name,'directory')
        _effect(handle,arm,'mkdir_workspace',arm.workspace,arm.workspace.mkdir)
        arm.workspace_closed='open';arm.descriptors_closed='open'
        _effect(handle,arm,'open_workspace',arm.workspace,arm.workspace.open)
        arm.identity=_effect(handle,arm,'identify_workspace',arm.workspace,arm.workspace.identify)
        arm.control=OwnedPreparationPath(handle.custody,condition,control_store,name,'directory')
        _effect(handle,arm,'mkdir_control',arm.control,arm.control.mkdir);arm.control_closed='open'
        _effect(handle,arm,'open_control',arm.control,arm.control.open)
        _effect(handle,arm,'identify_control',arm.control,arm.control.identify)
        _inventory(handle,arm,manifest)
        row=handle.begin('publish_workspace',condition)
        try:
            body={'schema':'ci_prelaunch_workspace_observation_v1','condition':condition,'pair_id':handle.pair_id,
                'workspace':_path_child(workspace_store.root,name),'private_control':_path_child(control_store.root,name),
                'filesystem_identity':arm.identity.pin,'inventory':arm.inventory.pin,
                'recipe':handle.contract.recipe_pin,'process_exists':False,'cost_prefix':handle.owner.cost_prefix()}
            arm.workspace_capture=_capture(handle,arm,'workspace','WorkspaceObservation',body)
            handle.finish(row,output=arm.workspace_capture)
        except BaseException as error:
            if row['first_error'] is None:handle.fail_operation(row,error)
            raise
        row=handle.begin('publish_state',condition)
        try:
            need(require_prepared_source_closure_target(handle.contract,handle.outputs) is handle.source_closure_capture,
                 'both states consume the same earlier H admission capture; no arm recapture')
            body={'schema':'ci_prelaunch_backend_state_preparation_v1','condition':condition,'pair_id':handle.pair_id,
                'workspace':arm.workspace_capture.pin,'recipe':handle.contract.recipe_pin,
                'backend_profile':handle.contract.backend_pin,'artifact_selection':handle.contract.artifacts_pin,
                'initial_inputs':list(handle.contract.recipe['immutable_inputs']),
                'prepared_source_closure':handle.source_closure_capture.pin,
                'model_initialized':False,'live_backend_identity':None,'cost_prefix':handle.owner.cost_prefix()}
            arm.state_capture=_capture(handle,arm,'state','InitialStatePreparation',body)
            handle.finish(row,output=arm.state_capture)
        except BaseException as error:
            if row['first_error'] is None:handle.fail_operation(row,error)
            raise
    return handle

def _publish_preparation(handle):
    owner=handle.owner;contract=handle.contract;opened=contract.admitted_open
    selection=opened.issuance.result.product;schedule=require_original_schedule(contract,selection['schedule'])
    handle.phase='publication'
    row=handle.begin('publish_pair_plan')
    try:
        body={'schema':'ci_developmentpairplan_v2','pair_id':handle.pair_id,'early_selection':opened.selection_pin,
            'owner_opened':opened.capture.pin,'profile':contract.profile_pin,'agent_policy':contract.policy_pin,
            'paired_views':selection['paired_views'],'public_ABI':selection['public_ABI'],'schedule':schedule,
            'host_subshare':owner.seed['host_subshare'],'equal_arm_subshare':owner.seed['arm_subshare'],
            'fresh_mutable_state_required':True,'outcome_retries_allowed':False}
        handle.pair_plan=handle.host_publisher.capture('development_pair_plan.json','DevelopmentPairPlan',body)
        owner.parent.known_records.append(handle.pair_plan.pin);handle.finish(row,output=handle.pair_plan)
    except BaseException as error:
        if row['first_error'] is None:handle.fail_operation(row,error)
        raise
    # Exact order: both requests, then both exposures, then both launch requests.
    for operation in ('publish_request','publish_exposure','publish_launch_request'):
        for condition in CONDITIONS:
            arm=handle.arms[condition];row=handle.begin(operation,condition)
            try:
                if operation=='publish_request':
                    body={'schema':'ci_developmentrequest_v2','condition':condition,'pair_plan':handle.pair_plan.pin,
                        'early_selection':opened.selection_pin,'owner_opened':opened.capture.pin,
                        'development_profile':contract.profile_pin,'agent_policy':contract.policy_pin,
                        'public_ABI':selection['public_ABI'],'public_interface':selection['public_interface'],
                        'view_inventory':arm.inventory.pin,'workspace_identity':arm.workspace_capture.pin,
                        'schedule':schedule,'subshare':owner.seed['arm_subshare']}
                    arm.request=_capture(handle,arm,'request','DevelopmentRequest',body);captured=arm.request
                elif operation=='publish_exposure':
                    raw=handle.outputs.read(arm.request.pin,owner.plan['maximum_output_bytes'],metadata=True)
                    need(raw==arm.request.raw,'actual original request exposure readback')
                    body={'schema':'ci_exposure_v1','condition':condition,'request':arm.request.pin,
                        'agent_policy':contract.policy_pin,'early_selection':opened.selection_pin,
                        'owner_opened':opened.capture.pin,'public_ABI':selection['public_ABI'],
                        'public_interface':selection['public_interface'],'view_inventory':arm.inventory.pin,
                        'original_readback':arm.request.pin,'observed_ns':handle.clock()}
                    arm.exposure=_capture(handle,arm,'exposure','Exposure',body);captured=arm.exposure
                else:
                    nonce=handle.pair_id+'-'+condition
                    body={'schema':'ci_developmentlaunchrequest_v2','condition':condition,'pair_plan':handle.pair_plan.pin,
                        'request':arm.request.pin,'exposure':arm.exposure.pin,'profile':contract.profile_pin,
                        'owner_binding':owner.parent.binding_pin,'argv':list(contract.profile['entry_argv']),
                        'cwd':_path_child(handle.workspace_parent.root,arm.workspace.name),
                        'environment':contract.profile['environment'],'group_name':nonce,'launch_nonce':nonce,
                        'source_closure':list(contract.policy['source_closure']),
                        'state_identity':arm.state_capture.pin,'workspace_identity':arm.workspace_capture.pin,
                        'run_deadline_ns':schedule['common_cutoff_ns'],
                        'evidence_deadline_ns':owner.parent.original_deadline,
                        'output_prefix':'development_'+condition}
                    arm.launch=_capture(handle,arm,'launch_request','DevelopmentLaunchRequest',body);captured=arm.launch
                handle.finish(row,output=captured)
            except BaseException as error:
                if row['first_error'] is None:handle.fail_operation(row,error)
                raise

class DevelopmentOwner:
    @staticmethod
    def finish_pair_backend_v1(pair):
        from .development_completion import finish_pair_backend_v1
        return finish_pair_backend_v1(pair)

    @staticmethod
    def prepare_pair_v2(contract,construction,*,inputs,outputs,workspace_parent,control_parent):
        owner=contract.owner if type(contract) is DevelopmentContract else None
        handle=None
        try:
            need(type(owner) is EarlyResources and owner.parent.owner is owner,'actual original source owner')
            need(type(construction) is EarlyConstruction and construction.owner is owner,'same complete creator chain')
            need(type(contract.admitted_open) is AuthenticatedEarlyOpen and
                 contract.admitted_open.issuance.construction is construction,'same actual open and public creators')
            expected=contract_identity_body(contract,contract.admitted_open)
            need(type(contract.identity_capture) is CapturedRecord and contract.identity_capture.owner is owner and
                 contract.identity_capture.kind=='DevelopmentContractIdentity' and same(contract.identity_capture.body,expected),
                 'completed same private contract identity before pair allocation')
            need(type(inputs) is Store and type(outputs) is Store and inputs is construction.inputs and
                 outputs is construction.outputs,'exact earlier original input/output stores')
            need(outputs.read(contract.identity_pin,owner.plan['maximum_output_bytes'],metadata=True)==contract.identity_capture.raw,
                 'same actual earlier captured contract readback')
            require_prepared_source_closure_target(contract,outputs)
            for store,path in ((workspace_parent,contract.recipe['workspace_parent']),
                               (control_parent,contract.recipe['private_control_parent'])):
                need(type(store) is Store and store.meter is owner.host and str(store.root)==path,
                     'exact preselected original parent root and H store')
            w=workspace_parent.root;c=control_parent.root
            need(w!=c and w not in c.parents and c not in w.parents,'private control outside participant workspace')
            need(not hasattr(owner.parent,'preparation'),'one pair nonce/handle, including failed preparation')
            owner.host.charge('retained_bytes',16384);owner.host.charge('work_units',16384)
            handle=PreparationHandle(_PREPARED,contract,construction,inputs,outputs,workspace_parent,control_parent)
            owner.parent.preparation=handle
            raw=canonical([owner.parent.clock['campaign_id'],owner.parent.nonce,contract.identity_pin],
                          owner.plan['maximum_output_bytes'])
            owner.host.charge('work_units',len(raw));handle.pair_id='pair-'+hashlib.sha256(raw).hexdigest()
            handle.host_publisher=_publisher(handle)
            prepare_fresh_pair_v1(handle);_publish_preparation(handle)
            need(all(handle.arms[c].launch is not None for c in CONDITIONS),'both actual launch captures before promotion')
            handle.phase='promoted';handle.promotion=handle
            handle.outcome=handle.host_publisher.capture('preparation_success.json','PreparationSuccess',handle.body(True))
            owner.parent.known_records.append(handle.outcome.pin)
            return handle
        except BaseException as error:
            if handle is not None:
                handle.retain(error,'DevelopmentOwner.prepare_pair_v2')
                cleanup_preparation_v2(handle)
                return handle
            if owner is not None:
                # The pair handle does not exist yet. Keep the same original
                # admission/parent custody before fallible failure publication.
                first=owner.parent.first_raw if owner.parent.first_raw is not None else error
                admission=getattr(owner.parent,'contract_admission',None)
                if type(admission) is ContractAdmissionHandle:
                    admission.retain(first)
                    if error is not first:admission.retain(error)
                try:owner.parent.retain(error,'development_prepare','source_refusal','DevelopmentOwner.pre_handle')
                except BaseException as later:
                    if type(admission) is ContractAdmissionHandle:admission.retain(later)
                if type(outputs) is Store:
                    try:
                        fail_after_selection_v3(owner.parent,first,attempt=owner.parent.nonce,phase='development_prepare',
                            code='source_refusal',site='DevelopmentOwner.pre_handle',output_store=outputs)
                    except BaseException as later:
                        if type(admission) is ContractAdmissionHandle:admission.retain(later)
                        try:owner.parent.retain(later,'failure_publish','publication_failure','DevelopmentOwner.pre_handle.failure')
                        except BaseException as secondary:
                            if type(admission) is ContractAdmissionHandle:admission.retain(secondary)
                raise first
            raise

def cleanup_preparation_v2(handle):
    need(type(handle) is PreparationHandle and handle.raw_first is not None,'actual failed preparation only')
    if handle.cleanup_started:return handle
    handle.cleanup_started=True;handle.owner.enter_terminal()
    # Each exact descriptor/removal owns an independent reserved terminal slot.
    def perform(arm,owned,operation,effect):
        if len(arm.cleanup)>=128:
            handle.owner.parent.unknown.add('work_units')
            return False  # Raw ownership remains; never perform an unreserved cleanup.
        row={'schema':'ci_preparation_cleanup_v1','operation_ordinal':len(arm.cleanup),
             'owned_handle_ordinal':owned.ordinal,'operation':operation,'started_ns':None,'finished_ns':None,
             'state':'pending','observed_identity':getattr(owned,'identity',None),'error':None,
             'cost_prefix':handle.owner.cost_prefix()}
        arm.cleanup.append(row)
        try:
            handle.owner.terminal_host.charge('work_units',8192)
            handle.owner.terminal_host.charge('retained_bytes',2048)
            row['started_ns']=handle.clock()
            effect()
            row['finished_ns']=handle.clock();row['state']='complete'
        except BaseException as error:
            handle.retain(error,'Preparation.cleanup.'+operation);row['state']='unknown'
            try:row['error']=handle._error(error)
            except BaseException as later:handle.retain(later,'Preparation.cleanup.diagnostic')
        row['cost_prefix']=handle.owner.cost_prefix()
        return row['state']=='complete'
    for condition in reversed(CONDITIONS):
        arm=handle.arms[condition]
        paths=[p for p in handle.custody.handles if type(p) is OwnedPreparationPath and p.condition==condition]
        for path in reversed(paths):
            # Deletion before anchor close, with observed original identity.
            if path.created and not path.removal_attempted:
                op='unlink_owned_file' if path.kind=='regular_file' else ('rmdir_control' if path is arm.control else 'rmdir_workspace')
                perform(arm,path,op,path.remove)
            if path.fd is not None:
                closing=path.fd
                def close_original(p=path,fd=closing):
                    need(p.fd==fd,'same unconsumed original fd slot');p.fd=None;os.close(fd)
                if not perform(arm,path,'close_fd',close_original):path.close_unknown=True
            while path.parents:
                closing=path.parents[-1]
                def close_anchor(p=path,fd=closing):
                    need(p.parents and p.parents[-1]==fd,'same unconsumed original parent fd slot')
                    p.parents.pop();os.close(fd)
                before=len(path.parents)
                if not perform(arm,path.anchor_handle,'close_fd',close_anchor):path.anchor_handle.close_unknown=True
                if len(path.parents)==before:break
        def closure(path):
            if path is None:return 'not_created'
            if path.removed:return 'known_closed'
            if path.created:return 'unknown' if path.removal_attempted else 'open'
            return 'unknown' if path.mkdir_entered or path.open_entered else 'not_created'
        arm.workspace_closed=closure(arm.workspace);arm.control_closed=closure(arm.control)
        arm.descriptors_closed=('unknown' if any(p.fd is not None or p.parents or p.close_unknown or
            p.anchor_handle.close_unknown for p in paths) else 'known_closed')
    return handle

class PreparationReporter:
    @staticmethod
    def capture_failure_v2(handle):
        need(type(handle) is PreparationHandle and handle.raw_first is not None and handle.promotion is None,
             'same actual failed preparation; no reconstructed wire handle')
        if handle.report_attempted:return handle
        handle.report_attempted=True;handle.owner.enter_terminal()
        try:
            publisher=_publisher(handle,terminal=True)
            handle.failure_capture=publisher.capture('preparation_failure.json','PreparationFailure',handle.body(False))
            handle.owner.parent.known_records.append(handle.failure_capture.pin)
            # The exact completed preparation failure exists before optional
            # FailurePrefix. Failure of that diagnostic cannot erase it.
            handle.failure_prefix=fail_after_selection_v3(handle.owner.parent,handle.raw_first,
                attempt=handle.pair_nonce,phase='development_prepare',code='source_refusal',
                site='PreparationReporter',output_store=handle.outputs)
            prefix=handle.failure_prefix.publication
            prefix_pin=None if prefix is None else prefix['prefix_record']
            report={'schema':'ci_preparation_report_v1','outcome':handle.failure_capture.body,
                'failure_prefix':prefix_pin,'failure_publication':'complete','pair_eligible':False}
            # Use a separate fixed slot; any failed canonical publication is
            # terminal for its publisher and never retried with a new name.
            handle.report_capture=publisher.capture('preparation_report.json','PreparationReport',report)
        except BaseException as error:handle.retain(error,'PreparationReporter.capture_failure_v2')
        return handle

class DevelopmentCoordinator:
    @staticmethod
    def dispatch_preparation_v2(handle):
        need(type(handle) is PreparationHandle and handle.owner.parent.preparation is handle,
             'actual source-owned preparation outcome')
        if handle.raw_first is not None:
            PreparationReporter.capture_failure_v2(handle)
            from .preparation_report import FourFinalReport
            if handle.final_report is None:handle.final_report=FourFinalReport(handle)
            handle.final_report.add_preparation_failure_v2(handle)
            return handle
        need(handle.promotion is handle and handle.phase=='promoted' and
             type(handle.outcome) is CapturedRecord and handle.outcome.kind=='PreparationSuccess',
             'only completed same-handle two-arm promotion may reach a worker launcher')
        saved=handle.outcome.body
        need(saved['development_contract']==handle.contract.identity_pin and
             saved['pair_plan']==handle.pair_plan.pin and saved['owner_binding']==handle.owner.parent.binding_pin,
             'same earlier captured contract/pair/owner; cost snapshots retain their original observation time')
        for condition,prefix in zip(CONDITIONS,saved['arms']):
            arm=handle.arms[condition]
            need(prefix['condition']==condition and prefix['launch_request']==arm.launch.pin and
                 prefix['request']==arm.request.pin and prefix['exposure']==arm.exposure.pin and
                 prefix['workspace_observation']==arm.workspace_capture.pin and
                 prefix['state_preparation']==arm.state_capture.pin,
                 'every actual same-arm completed capture survives promotion')
        return handle

