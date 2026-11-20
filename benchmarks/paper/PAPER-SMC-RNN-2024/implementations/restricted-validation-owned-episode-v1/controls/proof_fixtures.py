"""Generated one-phase closure metadata; no actual process or scope proof."""
import copy
from pathlib import Path


class ProofFiles:
    def __init__(self, common, charge):
        self.common, self.charge = common, charge
        self.files = {}
        self.trace = []

    def put(self, path, value):
        raw = self.common.encoded(value)
        self.charge('generated_metadata_bytes', len(raw))
        self.files[str(path)] = raw
        return self.common.pin(raw)

    def body(self, path, expected=None, cap=2 * 1024**2):
        raw = self.files[str(path)]
        self.charge('generated_read_bytes', len(raw))
        self.common.need(len(raw) <= cap and (expected is None or self.common.pin(raw) == expected),
                         'Generated saved metadata authentication')
        self.trace.append(('read', str(path)))
        return raw

    def read(self, path, expected=None, cap=2 * 1024**2):
        return self.common.parse(self.body(path, expected, cap))


class ClosureFixture:
    """Rehash mutations so real semantic guards, not stale outer hashes, refuse."""
    def __init__(self, common, charge, mutation=None):
        self.files = ProofFiles(common, charge)
        self.common = common
        self.root, self.output = Path('/generated/owner'), Path('/generated/output')
        mutate = mutation or (lambda stage, doc: None)
        self.source = common.pin(b'generated selected owner source')
        self.component_source = common.pin(b'generated selected VALID component')
        self.phase = 'validation_reference'
        self.resources = {'cpu_seconds':60000,'producer_seconds':10800,
            'memory_bytes':8589934592,'cpu_nanos':6000000000,'pids':32,'scratch_bytes':536870912}
        self.invocation = {'owner':str(self.root),'output':str(self.output),
            'protocol_path':'/generated/protocol/PROTOCOL.json','protocol_pin':common.pin(b'generated protocol'),
            'source':self.source,'legacy_source':self.component_source,'aggregate_nonce':'a'*32,'deployment_pin':common.pin(b'generated deployment'),
            'clock':{'origin':1.0,'deadline':11281.0,'controller_deadline':11221.0,
                     'outcome':'restricted_validation_reference','clock_identity':'linux:generated'}}
        mutate('invocation', self.invocation)
        self.invocation_pin = self.files.put(self.root/'INVOCATION.json', self.invocation)
        clock = self.invocation['clock']
        closure = {'schema':'smc_parent_observed_controller_closure_v1','source':self.source,
            'invocation_pin':self.invocation_pin,'clock':clock,
            'future_controller_and_acknowledged_cli_release_closed':True,
            'controller_group':{'absence_verified':True},
            'acknowledged_cli':{'all_acknowledged_cli_absent':True}}
        mutate('controller_closure', closure)
        closure_pin = self.files.put(self.root/'CONTROLLER_CLOSED.json', closure)
        phase = self.phase
        name = 'smc-' + 'a'*32 + '-b'
        plan = {'schema':'smc_cgroup_plan_v1','phase_id':phase,'name':name,
            'parent':'/generated/cgroup','path':'/generated/cgroup/'+name,
            'cgroup_parent':'/cgroup/'+name,'deployment_pin':self.invocation['deployment_pin'],
            'invocation_pin':self.invocation_pin}
        request = {'schema':'smc_aggregate_phase_request_v1','phase_id':phase,
            'resources':self.resources,'aggregate':plan,
            'clock':{'origin':clock['origin'],'phase_deadline':clock['controller_deadline']}}
        mutate('request',request)
        request_pin = self.files.put(self.output/'jobs'/phase/'REQUEST.json',request)
        owner = {'schema':'smc_aggregate_scope_owner_v1','phase_id':phase,'source':self.source,
            'invocation_pin':self.invocation_pin,'clock':clock,'request_pin':request_pin,
            'plan':request['aggregate'],'limits':request['resources']}
        mutate('owner',owner)
        owner_pin = self.files.put(self.root/('CGROUP-'+phase+'-OWNER.json'),owner)
        attached = {'source':self.source,'invocation_pin':self.invocation_pin,'clock':clock,
            'request_pin':request_pin,'owner_pin':owner_pin,
            'event':{'pid':1234,'container_id':'c'*64,'cgroup_parent':plan['cgroup_parent']}}
        mutate('attached',attached)
        self.files.put(self.root/('CGROUP-'+phase+'-ATTACHED.json'),attached)
        counter = {'cpu_usage_usec':1000,'cpu_stat':{'usage_usec':1000,'user_usec':800,'system_usec':200},
            'memory_peak_bytes':1024,'memory_events':{'low':0,'high':0,'max':0,'oom':0,'oom_kill':0,'oom_group_kill':0},
            'pids_events':{'max':0},'cgroup_events_before':{'populated':0,'frozen':0},
            'cgroup_events':{'populated':0,'frozen':0}}
        receipts = {}
        for stage in ('finished','closed'):
            receipt = {'schema':'smc_aggregate_scope_receipt_v1','phase_id':phase,'source':self.source,
                'invocation_pin':self.invocation_pin,'clock':clock,'request_pin':request_pin,
                'plan':request['aggregate'],'limits':request['resources'],'owner_pin':owner_pin,
                'producer':attached,'counters':copy.deepcopy(counter),'empty':True,'within_limits':True,
                'complete':True,'errors':[],'zero_cpu_overshoot_claim':False,
                'resource_policy':'measured_caps_and_oom_kill_v1'}
            mutate(stage,receipt)
            receipt_pin = self.files.put(self.root/('CGROUP-'+phase+'-'+stage.upper()+'.json'),receipt)
            receipts[stage] = {**copy.deepcopy(receipt),'receipt_pin':receipt_pin}
        ownership_pin = common.pin(common.encoded({'generated_provider_owner':phase}))
        transport = {'schema':'smc_aggregate_phase_receipt_v1','phase_id':phase,
            'request_sha256':request_pin['sha256'],'ownership_pin':ownership_pin,'all_native_resources_closed':True}
        mutate('provider_receipt',transport)
        transport_path = self.output/'control'/phase/'RECEIPT.json'
        transport_pin = self.files.put(transport_path,transport)
        provider = {'schema':'smc_aggregate_provider_closure_v1','invocation_pin':self.invocation_pin,
            'source':self.source,'clock':clock,'controller_closure_pin':closure_pin,'recovery_cli_absent':True,
            'phases':{phase:{'request_pin':request_pin,'ownership_pin':ownership_pin,'receipt_pin':transport_pin,
                'receipt_path':str(transport_path),'all_resources_closed':True,'producer_container_id':'c'*64}}}
        mutate('provider_document',provider)
        provider_pin = self.files.put(self.root/'PROVIDER_CLOSED.json',provider)
        aggregate = {'schema':'smc_aggregate_closed_v1','invocation_pin':self.invocation_pin,
            'source':self.source,'clock':clock,'controller_closure_pin':closure_pin,
            'value':{'controller_closure_pin':closure_pin,'scopes':{phase:receipts['closed']},
                'complete':True,'all_scopes_empty':True,'counters_complete':True,'within_limits':True}}
        mutate('closed_wrapper',aggregate)
        aggregate_pin = self.files.put(self.root/'AGGREGATE_CLOSED.json',aggregate)
        removed = {'schema':'smc_aggregate_removed_v1','invocation_pin':self.invocation_pin,
            'source':self.source,'clock':clock,'provider_closure_pin':provider_pin,
            'value':{'provider_closure_pin':provider_pin,'scopes':{phase:True},'complete':True,'all_scopes_removed':True}}
        mutate('removed_wrapper',removed)
        removed_pin = self.files.put(self.root/'AGGREGATE_REMOVED.json',removed)
        pair = {'owner_invocation_pin':self.invocation_pin,'owner_source':self.source,
            'protocol_path':self.invocation['protocol_path'],'protocol_sha256':self.invocation['protocol_pin']['sha256'],
            'outcome':clock['outcome']}
        mutate('pair',pair)
        pair_pin = self.files.put(self.output/'PAIR_CLOSED.json',pair)
        self.result = {'status':'closed_pair','error':None,'recovery_error':None,'cleanup_errors':[],
            'source':self.source,'invocation_pin':self.invocation_pin,'controller_closure_pin':closure_pin,
            'pair_closed_pin':pair_pin,'recovery_cli':{'all_acknowledged_cli_absent':True},
            'controller_execution':{'natural_exit':True},'aggregate':{'close_pin':aggregate_pin,
                'remove_pin':removed_pin,'provider_closure_pin':provider_pin,'phase_proofs':{phase:receipts['finished']}}}
        mutate('result',self.result)
        self.result_pin = self.files.put(self.root/'RESULT.json',self.result)
