"""Fixed H preparation/Hello/grant producer over original live source owners.

The receiver can exist before Hello, but the peer observation and full grant
cannot: they consume the actual first authenticated recvmsg. Selected ordinary
input reads retain their original identities; no new Pin aliases a selected
profile. All delivered handles are transport views of those actual originals.
"""
import hashlib
import os
import stat
import struct
from .common import need,Store
from .backend_json import canonical,parse
from .backend_capture import CapturedRecord,CanonicalPublisher
from .backend_native_v3_codec import validate_native_type
from .worker_context_schema_v3 import BOOTSTRAP_ORDER, require_bootstrap_roster_v3

_DELIVERY=object()
class HBootstrapObjectV3:
    def __init__(self,token,owner,kind,descriptor,raw,origin):
        need(token is _DELIVERY,'fixed original H bootstrap delivery factory')
        self.owner=owner;self.kind=kind;self._pin=dict(descriptor);self.raw=raw;self.origin=origin
        self.complete=False;self.raw_first=None
        owner.deliveries.append(self)
        value=parse(raw,len(raw),maximum_depth=64,maximum_members=len(raw),maximum_string_bytes=len(raw))
        validate_native_type(kind,value)
        need(canonical(value,len(raw))==raw and len(raw)==descriptor['bytes']and
             hashlib.sha256(raw).hexdigest()==descriptor['sha256'],
             'same complete canonical original selected bytes, never relabelled publication')
        self.complete=True
    @property
    def pin(self):return dict(self._pin)
    @property
    def body(self):return parse(self.raw,len(self.raw),maximum_depth=64,maximum_members=len(self.raw),maximum_string_bytes=len(self.raw))
    def require_original(self):
        need(self.complete and self.raw_first is None and any(x is self for x in self.owner.deliveries),
             'actual retained complete original delivery observation')
        if type(self.origin)is CapturedRecord:
            need(self.origin._attempt.complete is self.origin and self.origin._attempt.raw_first is None and
                 self.origin.pin==self.pin and self.origin.raw==self.raw,'same actual original completed capture')
        else:
            need(type(self.origin)is HBootstrapInputReadV3 and self.origin.delivery is self and
                 self.origin.owner is self.owner and self.origin.raw is self.raw and self.origin.complete,
                 'same actual original selected Store read occurrence')
        return self

class HBootstrapInputReadV3:
    def __init__(self,owner,kind,descriptor,expected):
        self.owner=owner;self.kind=kind;self.descriptor=dict(descriptor);self.expected=expected
        self.raw=None;self.entered=False;self.complete=False;self.delivery=None;self.raw_first=None
        owner.input_reads.append(self)
    def run(self):
        need(not self.entered,'one original selected input read including failure');self.entered=True
        try:
            c=self.owner.attempt.pair.contract;store=c.input_store
            need(type(store)is Store and store.meter is c.owner.host,'same original admitted input Store and H payer')
            limit=self.owner.setup.reservation.body['logical_record_limit']
            c.owner.host.charge('retained_bytes',self.descriptor['bytes']*16+4096)
            self.raw=store.read(self.descriptor,limit,metadata=True)
            observed=parse(self.raw,limit,maximum_depth=64,maximum_members=limit,maximum_string_bytes=limit)
            need(observed==self.expected,'same previously admitted complete original selected input body')
            self.delivery=HBootstrapObjectV3(_DELIVERY,self.owner,self.kind,self.descriptor,self.raw,self)
            self.complete=True;return self.delivery
        except BaseException as error:self.raw_first=error;self.owner.retain(error,'input_read');raise

class HWorkerBootstrapOwnerV3:
    def __init__(self,attempt,publisher):
        from .development_handles import DevelopmentAttemptHandle
        from .backend_bootstrap_carrier_v3 import HBootstrapCarrierOwnerV3
        need(type(attempt)is DevelopmentAttemptHandle,'actual original H development attempt')
        attempt.require_live_original();pipeline=attempt.native_launch_pipeline
        need(pipeline is not None and pipeline.complete and pipeline.attempt is attempt and
             type(attempt.bootstrap_carrier)is HBootstrapCarrierOwnerV3 and
             attempt.bootstrap_carrier.closed and attempt.bootstrap_carrier.raw_first is None,
             'actual completed original launch and parent alias closure before receiver setup')
        need(type(publisher)is CanonicalPublisher and publisher is pipeline.publisher,
             'same original H canonical publisher')
        self.attempt=attempt;self.publisher=publisher;self.channel=attempt.native_channel
        need(self.channel.receiver_activation is None and getattr(self.channel,'bootstrap_owner_v3',None)is None,
             'one actual original H bootstrap attempt including failed prefix')
        self.setup=attempt.bootstrap_carrier.setup;self.anchor=self.setup.anchor
        self.deliveries=[];self.input_reads=[];self.roots=[];self.bundle=None;self.peer=None
        self.table=None;self.activation=None;self.receiver=None;self.raw_first=None;self.secondaries=[]
        self.prepared=False;self.hello_entered=False;self.complete=False;self.native_observations=[]
        self.channel.bootstrap_owner_v3=self
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.channel.retain(error,'HWorkerBootstrapOwnerV3.'+site)
    def captured(self,cap,kind):
        a=self.attempt
        need(type(cap)is CapturedRecord and cap.kind==kind and cap._attempt.complete is cap and
             cap._attempt.raw_first is None and (cap.owner is a.owner or cap.owner is a.owner.parent),
             'same actual original ancestor/arm completed capture')
        return HBootstrapObjectV3(_DELIVERY,self,kind,cap.pin,cap.raw,cap)
    def _root_captures(self):
        anchor=self.anchor;anchor.require_completed_policy_profile_v3();a=self.attempt
        policy=anchor.selection_captures['native_root_policy'];selection=anchor.selection_captures['artifact_roots']
        for root_id in sorted(anchor.final_handles):
            root=anchor.final_handles[root_id];root.require_original();slot=root.anchor_fds[0]
            need(slot.parent_slot is not None and slot.entry_name not in ('','/'),
                 'actual retained original root open parent occurrence')
            self.publisher.meter.charge('work_units',4096);self.publisher.meter.charge('retained_bytes',4096)
            observed=os.fstat(slot.fd);filesystem=os.fstatvfs(slot.fd)
            self.native_observations.append(('root',slot,observed,filesystem))
            need(stat.S_ISDIR(observed.st_mode)and filesystem.f_flag&os.ST_RDONLY and
                 (observed.st_dev,observed.st_ino,observed.st_uid,observed.st_mode)==
                 (root.actual_identity.st_dev,root.actual_identity.st_ino,root.actual_identity.st_uid,root.actual_identity.st_mode),
                 'same actual original readonly opened root occurrence')
            namespace=anchor.namespace();mount=anchor.mount_id(slot)
            need(namespace==root.namespace_observation and mount==root.mount_observation,'same actual native root mount/namespace')
            now=self.channel._now(a.start_observation.J)
            identity={'schema':'ci_owned_path_identity_v1','device':observed.st_dev,'inode':observed.st_ino,
                'kind':'directory','mode':observed.st_mode,'uid':observed.st_uid,'observed_ns':now,
                'parent_handle_ordinal':slot.parent_slot.ordinal,'relative_path':slot.entry_name}
            body={'schema':'four_native_root_observation_v1','absolute_mount':root.definition['absolute_mount'],
                'cost_prefix':a.owner.cost_prefix(),'host':a.owner.parent.identity,'identity':identity,
                'mount_id':mount,'namespace_identity':namespace,'native_qualification':policy.body['native_qualification'],
                'observed_ns':now,'readonly':True,'root_id':root_id,'root_policy':policy.pin,
                'source_admission':a.pair.contract.profile['source_admission']}
            cap=self.publisher.capture(a.native_observations._prefix()+'_ROOT_'+root_id+'.json','NativeRootObservationV1',body)
            self.roots.append(self.captured(cap,'NativeRootObservationV1'))
        body={'schema':'four_native_artifact_root_bundle_v1','cost_prefix':a.owner.cost_prefix(),
            'host':a.owner.parent.identity,'roots':[x.pin for x in self.roots],'selection':selection.pin,
            'source_admission':a.pair.contract.profile['source_admission']}
        self.bundle=self.captured(self.publisher.capture(a.native_observations._prefix()+'_ROOT_BUNDLE.json',
            'NativeArtifactRootBundleV1',body),'NativeArtifactRootBundleV1')
    def prepare_receiver(self):
        from .backend_host_receiver import HReceiverActivation,HChannelReceiver,_ACTIVATION
        from .backend_native_boundary import HWorkerLaunchAdmission,_NATIVE
        try:
            a=self.attempt;a.require_live_original();self.setup.require_original()
            self.anchor.require_completed_policy_profile_v3()
            need(a.native_launch_admission is None and a.launch_ack is not None,'actual original Ack before H receiver capability')
            admission=HWorkerLaunchAdmission(_NATIVE,owner=a.owner,condition=a.condition,ack=a.launch_ack,
                request=a.arm.request,preparation=a.arm.state_capture,workspace=a.arm.workspace_capture,
                profile=a.pair.contract.backend,native=None,consumed=False,backend_handle=None)
            # H-only routing capability. native=None cannot be used by the old
            # worker BackendAttemptHandle, which requires its actual native owner.
            a.native_launch_admission=admission
            self.channel.bind_returned_worker();self._root_captures()
            c=a.pair.contract;selected=self.anchor.selection_captures;policies=self.anchor.policy_profile_captures
            self.ordered_prefix=[self.captured(a.launch_ack,'WorkerLaunchAck'),self.captured(a.arm.request,'DevelopmentRequest'),
                self.captured(a.arm.state_capture,'InitialStatePreparation'),self.captured(a.arm.workspace_capture,'WorkspaceObservation'),
                HBootstrapInputReadV3(self,'LocalBackendProfile',c.backend_pin,c.backend).run(),
                HBootstrapInputReadV3(self,'LocalArtifactSelection',c.artifacts_pin,c.artifacts).run(),
                self.captured(policies['native_context_policy'],'NativeContextPolicyV2'),
                self.captured(selected['artifact_roots'],'NativeArtifactRootSelectionV1'),self.bundle,
                self.captured(selected['bootstrap_entry'],'BootstrapEntrySelectionV1'),
                self.captured(policies['agent_policy'],'NativeAgentPolicyV4'),
                HBootstrapInputReadV3(self,'AgentInputSelectionV1',
                    self.anchor.original_selection['agent_input_selection']['descriptor'],
                    self.anchor.original_selection['agent_input_selection']['body']).run(),
                self.captured(policies['development_profile'],'NativeDevelopmentProfileV3'),
                self.captured(self.setup.reservation,'ChannelBudgetReservationV1'),
                self.captured(self.setup.open_capture,'ChannelOpenObservationV1')]
            need(tuple(v.kind for v in self.ordered_prefix)==BOOTSTRAP_ORDER[:-1],
                 'complete original pre-Hello prefix excluding only the peer observation')
            prefix_by_kind={v.kind:v for v in self.ordered_prefix}
            x=HReceiverActivation(_ACTIVATION);self.activation=x;x.bootstrap_owner=self
            x.channel=self.channel;x.admission=admission
            x.policy=prefix_by_kind['NativeContextPolicyV2'];x.reservation=prefix_by_kind['ChannelBudgetReservationV1']
            x.context=a.bootstrap_carrier.body['context'];x.host_publisher=self.publisher
            arm_outputs=Store(self.publisher.outputs.root,a.owner.arms[a.condition],forbidden=self.publisher.outputs.forbidden)
            x.arm_publisher=CanonicalPublisher(a.owner,arm_outputs,condition=a.condition,
                maximum_bytes=self.publisher.maximum_bytes,maximum_members=self.publisher.maximum_members,maximum_depth=self.publisher.maximum_depth)
            x.ledger=self.channel.reservation_ledger;s=a.start_observation
            x.S=a.started_ns;x.J=s.J;x.G=s.G;x.R=s.R;x.E=s.E
            r=x.reservation.body;x.packet_limit=r['packet_limit'];x.logical_limit=r['logical_record_limit']
            x.maximum_sequences=r['maximum_sequences'];x.maximum_publications=c.profile['maximum_files']
            self.channel.receiver_activation=x;x.complete=True;self.prepared=True
            self.receiver=HChannelReceiver(x);return self.receiver
        except BaseException as error:self.retain(error,'prepare_receiver');raise self.raw_first
    def grant_after_original_hello(self,pending):
        need(self.prepared and not self.hello_entered,'one original first Hello grant attempt');self.hello_entered=True
        try:
            a=self.attempt;c=self.channel;x=self.activation
            need(pending is self.receiver.pending and pending.sequence==0 and pending.kind=='BootstrapHelloV3'and
                 pending.raw is c.current_receive_result[0]and pending.packet is not None,
                 'same actual completed authenticated first recvmsg, never a supplied Hello')
            raw,anc,flags,address=c.current_receive_result
            need(len(anc)==1 and len(anc[0][2])==12,'actual already checked original credentials')
            pid,uid,gid=struct.unpack('3i',anc[0][2]);need(pid==c.pid and uid==c.uid,'same actual original worker peer')
            c.worker_anchor.check_live(x.J);namespace={'schema':'four_namespace_identity_v1'}
            for name in ('cgroup','ipc','mnt','net','pid','user','uts'):
                self.publisher.meter.charge('read_bytes',256);self.publisher.meter.charge('work_units',4096)
                self.publisher.meter.charge('retained_bytes',256)
                value=os.readlink('ns/'+name,dir_fd=c.worker_anchor.directory.fd)
                self.native_observations.append(('worker_namespace',name,value));namespace[name]=value
            now=c._now(x.J);host_uid=os.getuid();host_gid=os.getgid()
            self.native_observations.append(('host_credentials',host_uid,host_gid))
            body={'schema':'four_channel_peer_observation_v1','actual_kernel_group':a.group_capture.pin,
                'channel_open':self.setup.open_capture.pin,'context':x.context,'cost_prefix':a.owner.cost_prefix(),
                'credential_source':'SCM_CREDENTIALS_per_packet_plus_original_pidfd_start','host':a.owner.parent.identity,
                'host_gid':host_gid,'host_uid':host_uid,'observed_ns':now,'worker':a.process.identity,
                'worker_gid':gid,'worker_uid':uid,'worker_namespace':namespace}
            self.peer=self.captured(self.publisher.capture(a.native_observations._prefix()+'_CHANNEL_PEER.json',
                'ChannelPeerObservationV1',body),'ChannelPeerObservationV1')
            objects=tuple(self.ordered_prefix+[self.peer]+self.roots)
            for original in objects:original.require_original()
            rows=[{'schema':'four_bootstrap_object_row_v1','ordinal':i,'kind':v.kind,'capture':v.pin}for i,v in enumerate(objects)]
            require_bootstrap_roster_v3(rows)
            table={'schema':'four_bootstrap_object_table_v1','context':x.context,'source_admission':x.context['source_admission'],'rows':rows}
            self.table=self.publisher.capture(a.native_observations._prefix()+'_BOOTSTRAP_TABLE.json','BootstrapObjectTableV1',table)
            mapping=a.host.mapping
            grant={'schema':'four_worker_bootstrap_grant_v1','E_ns':x.E,'G_ns':x.G,'J_ns':x.J,'R_ns':x.R,
                'boot_id':mapping['boot_id'],'channel_peer':self.peer.pin,'channel_reservation':x.reservation.pin,
                'clock_ticks':mapping['clock_ticks'],'context':x.context,'cost_prefix':a.owner.cost_prefix(),
                'host':a.owner.parent.identity,'issued_ns':c._now(x.J),'mapping_source':mapping['source'],
                'object_table':self.table.pin,'object_table_body':table,'original_S_ns':x.S,
                'tick_to_monotonic_offset_ns':mapping['tick_to_monotonic_offset_ns'],'worker':a.process.identity,
                'worker_launch_ack':a.launch_ack.pin}
            validate_native_type('WorkerBootstrapGrantV1',grant)
            x.objects=objects;x.table=self.table;x.grant=grant;self.complete=True;return grant
        except BaseException as error:self.retain(error,'first_hello');raise self.raw_first

def prepare_actual_h_receiver_v3(attempt,publisher):
    return HWorkerBootstrapOwnerV3(attempt,publisher).prepare_receiver()
