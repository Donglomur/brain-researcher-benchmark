"""Fixed typed H carrier composition; no source, report or FD constructor ABI.

Consumes the actual original prepaid channel ledger. Its amounts are retained
allocations, never a new allowance or measured physical usage. A complete
control-schedule producer remains a separate required caller; smaller existing
reservations refuse before either inherited alias is acquired.
"""
from .common import need,same
from .backend_json import canonical
from .backend_capture import CanonicalPublisher,CapturedRecord
from .backend_native_v3_codec import validate_native_type
from .backend_linux_bootstrap_memfd import HBootstrapMemfdPhysical
from .backend_linux_bootstrap_fd import HWorkerEndpointAlias
from .backend_worker_bootstrap_physical_v3 import (
    INITIAL_READ_BOUND,INITIAL_RETAINED_BOUND,INITIAL_WORK_BOUND,INITIAL_MAXIMUM_FDS)

def _completed(cap,owner,kind):
    need(type(cap)is CapturedRecord and cap.owner is owner and cap.kind==kind and
         cap._attempt.complete is cap and cap._attempt.raw_first is None,'actual earlier original complete capture')
    return cap.body

def _reservation_source(root):
    from . import backend_native_reservations
    from .operator_entry import _code_identity
    prior=root.prior_static;prior.require_original()
    rows=[r for r in prior.invocation.intake.body['installed_closure']['members']if r['role']=='native_control_reservation']
    need(len(rows)==1,'exact earlier installed native_control_reservation source role')
    row=rows[0];parent=root.parent
    parent.share.charge('work_units',row['descriptor']['bytes']*128+4096)
    parent.share.charge('retained_bytes',row['descriptor']['bytes']*16+4096)
    current=prior.invocation.loaded_source_map.get(row['loaded_module'])
    need(current is not None and current[0]is backend_native_reservations and current[1]==row and
         _code_identity(backend_native_reservations)==row['loaded_code_sha256'],
         'actual fixed loaded original ledger source, never a supplied descriptor')
    return row['descriptor']

class HChannelSetupCaptureV4:
    def __init__(self,channel,publisher):
        from .backend_linux_channel import HNativeChannelOwner
        from .backend_native_reservations import NativeReservationLedger
        need(type(channel)is HNativeChannelOwner and type(channel.reservation_ledger)is NativeReservationLedger and
             channel.reservation_ledger.channel is channel,'actual original channel and retained control ledger')
        a=channel.attempt;a.require_live_original()
        need(type(publisher)is CanonicalPublisher and publisher.owner is a.owner and publisher.condition is None and
             a.native_observations.publisher is publisher and getattr(channel,'setup_capture_v4',None)is None,
             'same original H publisher and one retained channel capture attempt')
        self.channel=channel;self.attempt=a;self.publisher=publisher;self.ledger=channel.reservation_ledger
        self.reservation=None;self.open_capture=None;self.raw_first=None;self.secondaries=[]
        self.entered=False;self.complete=False;self.policy=None;self.anchor=None
        channel.setup_capture_v4=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.channel.retain(error,'setup_capture_'+site)
    def capture_v4(self):
        need(not self.entered,'one original channel evidence producer');self.entered=True
        try:
            a=self.attempt;c=self.channel;ledger=self.ledger;ledger.require_original()
            from .native_control_plan_v4 import NativeControlPlanV4
            need(type(a.native_control_plan)is NativeControlPlanV4 and ledger.source_control_plan is a.native_control_plan and
                 a.native_control_plan.ledger is ledger,'actual complete original control plan, no supplied vector authority')
            a.native_control_plan.require_original()
            need(ledger.control_host is not None and ledger.control_arm is not None and
                 ledger.control_host.complete and ledger.control_arm.complete and not c.setup_entered,
                 'complete actual control reservations precede socketpair')
            root=a.owner.parent.operator_root_admission;root.require_verified_root_v1()
            self.anchor=a.pair.contract.native_anchor;self.anchor.require_completed_policy_profile_v3()
            need(self.anchor.original_admission is root,'same earlier native qualification/source owner')
            self.policy=self.anchor.policy_profile_captures['native_context_policy'];policy=self.policy.body
            profile=a.pair.contract.profile;plan=a.owner.plan
            limit=min(65536,profile['maximum_metadata_bytes'],profile['maximum_request_bytes'],
                      plan['maximum_input_bytes'],plan['maximum_output_bytes'])
            need(limit>0,'positive intersection of unchanged source bounds')
            source=_reservation_source(root)
            body={'schema':'four_channel_budget_reservation_v1','condition':a.condition,
                'context_policy':self.policy.pin,'host_reserved':dict(ledger.control_host.maximum),
                'arm_reserved':dict(ledger.control_arm.maximum),'cleanup_reserved':dict(a.owner.terminal_reserve),
                'original_owner_binding':a.owner.parent.binding_pin,'original_clock_mapping':profile['clock_mapping'],
                'original_evidence_deadline_ns':a.evidence_deadline_ns,'packet_limit':limit,
                'logical_record_limit':limit,'maximum_sequences':min(4096,policy['sequence_ceiling']),
                'reservation_source':source,'schedule':a.arm.request.body['schedule'],'cost_prefix':a.owner.cost_prefix()}
            prefix=a.native_observations._prefix()
            self.reservation=self.publisher.capture(prefix+'_CHANNEL_RESERVATION.json','ChannelBudgetReservationV1',body)
            c.use_control_reservation(ledger);c.acquire(a.run_deadline_ns)
            need(c.setup_complete and c.nonblocking and c.host is not None and c.worker is not None and
                 c.host is c.raw_pair[0]and c.worker is c.raw_pair[1],'actual complete original ordered endpoint pair')
            opened={'schema':'four_channel_open_observation_v1','condition':a.condition,
                'host':a.owner.parent.identity,'reservation':self.reservation.pin,'policy':self.policy.pin,
                'host_endpoint_ordinal':0,'worker_endpoint_ordinal':1,'transport':'AF_UNIX_SOCK_SEQPACKET',
                'worker_fd':198,'passcred':True,'observed_ns':c._now(a.run_deadline_ns),'cost_prefix':a.owner.cost_prefix()}
            self.open_capture=self.publisher.capture(prefix+'_CHANNEL_OPEN.json','ChannelOpenObservationV1',opened)
            self.complete=True;return self
        except BaseException as error:self.retain(error,'capture');raise self.raw_first
    def require_original(self):
        if self.attempt.owner.parent.first_raw is not None:raise self.attempt.owner.parent.first_raw
        try:
            a=self.attempt;a.require_live_original()
            need(self.channel.setup_capture_v4 is self and self.channel.attempt is a and self.complete and
                 self.raw_first is None and not self.channel.poisoned,'same actual complete original channel producer')
            reservation=_completed(self.reservation,a.owner,'ChannelBudgetReservationV1')
            opened=_completed(self.open_capture,a.owner,'ChannelOpenObservationV1')
            need(reservation['host_reserved']==self.ledger.control_host.maximum and
                 reservation['arm_reserved']==self.ledger.control_arm.maximum and
                 opened['reservation']==self.reservation.pin and opened['policy']==self.policy.pin,
                 'complete retained original reservation and physical open inverse')
            return self
        except BaseException as error:
            self.retain(error,'require_original');raise self.raw_first

class HBootstrapCarrierOwnerV3:
    def __init__(self,kernel):
        from .development_worker_io import DevelopmentWorkerKernel
        from .backend_launch_start_v3 import HWorkerStartOwnerV3
        need(type(kernel)is DevelopmentWorkerKernel,'actual original H kernel')
        a=kernel.attempt;a.require_live_original()
        need(a.worker_kernel is kernel and a.bootstrap_carrier is None and
             type(a.start_observation)is HWorkerStartOwnerV3 and a.start_observation.kernel is kernel,
             'one actual original carrier owner after original start registration')
        self.kernel=kernel;self.attempt=a;self.channel=a.native_channel;self.start=a.start_observation
        self.setup=None;self.raw_first=None;self.secondaries=[];self.entered=False;self.complete=False
        self.body=None;self.raw=None;self.physical=None;self.alias=None;self.close_entered=False;self.closed=False
        self.schedule=None;self.original_descriptor=None
        a.bootstrap_carrier=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.kernel.retain(error,'bootstrap_carrier_'+site,'source_or_native_failure')
    def _reserve_prefix(self,extent):
        ledger=self.channel.reservation_ledger;ledger.require_original()
        # Finite source schedule for this carrier/import only. It does not
        # claim the remaining 4096-message programme schedule fits.
        self.schedule={'read_bytes':INITIAL_READ_BOUND+extent+1+8192,
            'write_bytes':extent,'retained_bytes':INITIAL_RETAINED_BOUND+extent*8+65536,
            'work_units':INITIAL_WORK_BOUND+extent*512+1048576,'maximum_transient_fds':INITIAL_MAXIMUM_FDS+8}
        slot=ledger.control_arm
        for dimension in ('read_bytes','write_bytes','retained_bytes','work_units'):
            need(slot.used[dimension]+self.schedule[dimension]<=slot.maximum[dimension],
                 'complete original carrier and fixed worker-prefix schedule before effects')
        # Worker initial budget is consumed from this actual retained slot
        # before exec; the observed descendant cost remains a separate datum.
        meter=ledger.arm_meter()
        for dimension,amount in (('read_bytes',INITIAL_READ_BOUND),('retained_bytes',INITIAL_RETAINED_BOUND),('work_units',INITIAL_WORK_BOUND)):
            meter.charge(dimension,amount)
    def prepare_v3(self):
        need(not self.entered,'one original carrier including failed attempt');self.entered=True
        try:
            a=self.attempt;c=self.channel;start=self.start
            start.require_original_capture_v3();need(start.complete and not self.kernel.spawn_entered,'actual earlier completed start before carrier')
            setup=getattr(c,'setup_capture_v4',None);need(type(setup)is HChannelSetupCaptureV4,'actual fixed channel capture owner')
            setup.require_original();self.setup=setup;root=a.owner.parent.operator_root_admission
            setup.anchor.require_completed_policy_profile_v3();entry=setup.anchor.selection_captures['bootstrap_entry']
            policy=setup.policy.body;profile=a.pair.contract.profile;mapping=a.host.mapping
            need(mapping['source']==profile['clock_mapping']==a.owner.parent.clock['mapping_source']and
                 mapping['boot_id']==a.owner.parent.identity['boot_id'],'same actual original host clock mapping')
            namespace=setup.anchor.namespace()
            need(all(namespace==x.namespace_observation for x in setup.anchor.final_handles.values()),'same original admitted host namespace')
            context={'schema':'four_context_identity_v1','condition':a.condition,
                'pair_id':a.pair.pair_plan.body['pair_id'],'launch_nonce':self.kernel.running.spec['nonce'],
                'original_attempt':a.prefix_capture.pin,'source_admission':profile['source_admission']}
            self.body={'schema':'four_worker_prehello_descriptor_v3','protocol':'four-native-context-v3',
                'bootstrap_fd':199,'channel_fd':198,'context':context,'context_policy':setup.policy.pin,
                'entry_selection':entry.pin,'canonical_publisher_source':setup.publisher.source_pin,
                'source_issuer':profile['launcher_source'],'host':a.owner.parent.identity,'host_namespace':namespace,
                'reservation':setup.reservation.pin,'reservation_body':setup.reservation.body,
                'channel_open':setup.open_capture.pin,'start_observation':start.capture.pin,'start_body':start.capture.body,
                'clock_mapping_source':mapping['source'],'boot_id':mapping['boot_id'],'clock_ticks':mapping['clock_ticks'],
                'tick_to_monotonic_offset_ns':mapping['tick_to_monotonic_offset_ns'],'prehello_deadline_ns':min(start.J,start.R)}
            limit=setup.reservation.body['logical_record_limit']
            # Capacity is admitted before canonical encoding; selected maximum
            # bounds this encoding attempt, and actual bytes are rechecked.
            self._reserve_prefix(limit)
            c.meter.charge('work_units',limit*64+4096);c.meter.charge('retained_bytes',limit*4+4096)
            validate_native_type('WorkerPreHelloDescriptorV3',self.body)
            self.raw=canonical(self.body,limit,maximum_depth=64)
            need(len(self.raw)<=limit and policy['canonical_publisher_source']==self.body['canonical_publisher_source'],
                 'exact whole carrier inside all original bounds and earlier source binding')
            self.original_descriptor=dict(self.body)
            self.alias=HWorkerEndpointAlias(c);self.alias.acquire(start.J)
            self.physical=HBootstrapMemfdPhysical(c);self.physical.prepare_bytes(self.raw,start.J)
            self.complete=True;return self.require_spawn_original_v3()
        except BaseException as error:
            self.retain(error,'prepare')
            try:self.close_parent_exec_aliases_once()
            except BaseException as later:self.retain(later,'failed_prepare_cleanup')
            raise self.raw_first
    def require_spawn_original_v3(self):
        if self.attempt.owner.parent.first_raw is not None:raise self.attempt.owner.parent.first_raw
        try:
            a=self.attempt;a.require_live_original()
            need(a.bootstrap_carrier is self and a.worker_kernel is self.kernel and self.complete and self.raw_first is None and
                 not self.close_entered and not self.channel.poisoned,'same live actual completed carrier, no replay')
            self.setup.require_original();self.start.require_original_capture_v3()
            self.physical.require_physical_complete();fds=self.alias.pass_fds()
            need(fds==(198,self.kernel.group.entry_fd)and self.physical.alias199_slot.fd==199 and
                 len({198,199,self.kernel.group.entry_fd,self.channel.host.fileno()})==4 and
                 self.body==self.original_descriptor and self.body['start_observation']==self.start.capture.pin and
                 self.body['start_body']==self.start.capture.body,'same original full alias/start/body lineage')
            need(self.kernel.running.spec['argv']==[self.setup.anchor.entry_handle.selection_capture.body['interpreter_absolute'],
                 '-I',self.setup.anchor.entry_handle.selection_capture.body['entry_absolute']],
                 'exact source-selected argv with no extra bootstrap argument or environment')
            return self
        except BaseException as error:
            self.retain(error,'require_spawn');raise self.raw_first
    def close_parent_exec_aliases_once(self):
        if self.close_entered:return self.closed
        self.close_entered=True;complete=True
        for obj in (self.physical,self.alias):
            if obj is not None:
                try:complete=obj.close_once()and complete
                except BaseException as error:complete=False;self.retain(error,'close_alias')
        try:
            result=self.channel.close_endpoint('worker');complete=result and complete
        except BaseException as error:complete=False;self.retain(error,'close_worker_endpoint')
        self.closed=complete
        need(complete,'original parent exec alias cleanup must be known; no retry')
        return True
