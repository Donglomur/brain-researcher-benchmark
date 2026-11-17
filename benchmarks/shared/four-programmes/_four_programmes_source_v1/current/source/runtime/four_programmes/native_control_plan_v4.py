"""Whole source-derived native control schedule before native preparation.

This is a conservative reservation derivation, not measured feasibility. All
4096 protocol positions, all bootstrap roles/sites, and the complete bounded
launch census remain included. Infeasible profiles refuse; none are truncated.
CPU/wall and total FD limits require separate original enforcer evidence.
"""
import os
import hashlib
import resource
from .common import need
from .operator_intake import canonical
from .early_resources import retain_source_failure
from .backend_native_v3_records import NATIVE_PRIMITIVES
from .worker_context_schema_v3 import BOOTSTRAP_KINDS, BOOTSTRAP_MAX_OBJECTS
from .backend_worker_bootstrap_physical_v3 import INITIAL_READ_BOUND,INITIAL_RETAINED_BOUND,INITIAL_WORK_BOUND,INITIAL_MAXIMUM_FDS

_PLAN=object()
DIMENSIONS=('read_bytes','write_bytes','work_units','process_starts','cpu_ns','wall_ns','retained_bytes')
SEQUENCES=4096;GROUP_NODES=4096;GROUP_PASSES=4;THREAD_LIMIT=4096

class NativeControlPlanV4:
    def __init__(self,token,attempt):
        need(token is _PLAN,'fixed full source control-plan producer')
        self.attempt=attempt;self.owner=attempt.owner;self.contract=attempt.pair.contract
        self.raw_first=None;self.secondaries=[];self.entered=True;self.complete=False;self.ledger=None
        self.input_digest=None;self.input_extent=None;self.source_inputs=None;self.rosters=None;self.formula=None;self.host_vector=None;self.arm_vector=None
        self.enforcement=None;self.fd_iterator=None;self.fd_close_entered=False;self.fd_closed=False
        self.fd_names=[];self.fd_limits=None;self.fd_peak=None
    def retain(self,error,site):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.attempt.retain(error,'NativeControlPlanV4.'+site)
        retain_source_failure(self.owner.parent,error,'NativeControlPlanV4.'+site)
    def _close_fd_iterator(self):
        if self.fd_close_entered:return self.fd_closed
        self.fd_close_entered=True
        try:
            if self.fd_iterator is not None:self.fd_iterator.close()
            self.fd_closed=True;return True
        except BaseException as error:self.retain(error,'fd_census_close');return False
    def _fd_admission(self,additional):
        # Only descriptor names, never their symlink targets or bodies.
        meter=self.owner.host;maximum=self.contract.profile['maximum_files']
        need(type(maximum)is int and 0<maximum<=9007199254740991,'existing selected finite census bound')
        meter.charge('work_units',4096);meter.charge('retained_bytes',4096)
        self.fd_limits=resource.getrlimit(resource.RLIMIT_NOFILE)
        need(type(self.fd_limits)is tuple and len(self.fd_limits)==2 and
             self.fd_limits[0]==self.enforcement['fd_limit_readback'],'actual installed FD envelope equals qualified original readback')
        self.fd_iterator=os.scandir('/proc/self/fd')
        try:
            while True:
                need(len(self.fd_names)<maximum,'full current descriptor census inside original metadata bound')
                meter.charge('work_units',4096);meter.charge('read_bytes',256);meter.charge('retained_bytes',256)
                try:item=next(self.fd_iterator)
                except StopIteration:break
                name=item.name;self.fd_names.append(name)
                need(type(name)is str and name.isdecimal(),'actual proc descriptor name only')
        except BaseException as error:
            self.retain(error,'fd_census');raise self.raw_first
        finally:
            self._close_fd_iterator()
        if self.raw_first is not None:raise self.raw_first
        self.fd_peak=len(self.fd_names)+additional
        need(self.fd_peak<=self.enforcement['fd_peak_limit']<=self.fd_limits[0],
             'complete separate actual installed FD demand, no eighth resource grant')
    def _input_identity(self):
        c=self.contract;a=self.attempt
        self.owner.host.charge('work_units',self.input_extent*128+4096)
        self.owner.host.charge('retained_bytes',self.input_extent*32+4096)
        return hashlib.sha256(canonical({'profile':c.profile,'policy':c.policy,'backend':c.backend,'worker':c.worker,
            'plan':self.owner.plan,'request':a.arm.request.body,'launch':a.arm.launch.body,
            'partitions':self.owner.partitions,'terminal_reserve':self.owner.terminal_reserve})).hexdigest()
    def derive(self):
        try:
            a=self.attempt;c=self.contract;a.require_live_original()
            need(not a.spawn_entered and a.native_channel is None and a.worker_kernel is None,
                 'whole control preflight before kernel/group/channel/carrier effects')
            anchor=c.native_anchor;anchor.require_completed_policy_profile_v3()
            root=anchor.original_admission;qualification=anchor.qualification.require_original()
            observations=qualification.reports['worker_entry']['observations']
            enforcers=[r['body']['result']for r in observations if r['body']['case']=='control_enforcement']
            need(len(enforcers)==1,'mandatory separate original control physical-limit/enforcer evidence')
            self.enforcement=enforcers[0];base=root.prior_static.configuration['base_development_profile']
            need(self.enforcement['base_development_profile']==base['descriptor']and
                 self.enforcement['whole_envelope']==c.profile['whole_envelope']and
                 self.enforcement['worker_envelope']==c.profile['worker_envelope'],
                 'actual unchanged original profile/whole/worker envelope domain')
            self.input_extent=len(root.prior_static.invocation.intake.raw)+a.arm.request.pin['bytes']+a.arm.launch.pin['bytes']+4096
            self.input_digest=self._input_identity()
            p=c.profile;plan=self.owner.plan;policy=anchor.policy_profile_captures['native_context_policy'].body
            maximum=min(p['maximum_metadata_bytes'],p['maximum_request_bytes'],plan['maximum_input_bytes'],plan['maximum_output_bytes'])
            packet=min(65536,maximum,policy['packet_ceiling']);need(packet>0,'positive full original packet intersection')
            need(policy['sequence_ceiling']==SEQUENCES,'all original4096 positions; no shortened workload')
            threads=min(THREAD_LIMIT,c.worker['limits']['pids']);need(threads>0,'original enforced full worker PID/TID bound')
            bootstrap=BOOTSTRAP_KINDS
            publication=tuple(NATIVE_PRIMITIVES['PublicationSite']['values'])
            effects=tuple(NATIVE_PRIMITIVES['EffectSite']['values'])
            need(len(publication)==26 and len(effects)==21,'complete fixed source type/site universe')
            self.rosters={'bootstrap':bootstrap,'publication_sites':publication,'effect_sites':effects,
                          'all_request_sequence_positions':SEQUENCES}
            # Every possible protocol position is independently bounded even
            # when some maxima cannot occur together. This is conservative.
            packets=2*SEQUENCES*packet
            raw_reads=GROUP_PASSES*(GROUP_NODES*2+threads*6)
            raw_bytes=GROUP_PASSES*(GROUP_NODES*2*65536+threads*(4*8192+2*65536))
            raw_files=2*raw_reads # raw bytes and typed inverse capture, each occurrence
            # Each read and capture includes EOF/headroom and fixed metadata
            # overhead, all repeated Store readbacks and bounded parse copies.
            census_bytes=raw_bytes+raw_reads*4096
            bootstrap_bytes=BOOTSTRAP_MAX_OBJECTS*(maximum+4096) # complete fixed prefix plus every allowed root
            # Both endpoint directions admit at most4096 physical attempts.
            # Each attempt has before/after anchored parent stat plus EOF,
            # independently of whether a datagram completes. Source checks
            # are fixed full installed expectation validation occurrences.
            endpoint_stat_bytes=4*SEQUENCES*8194
            source_validation_bytes=16*SEQUENCES*65536
            endpoint_schedule=endpoint_stat_bytes+source_validation_bytes+7*256+32*4096
            publications=SEQUENCES+raw_files+len(bootstrap)+32
            publication_bytes=SEQUENCES*(maximum+4096)+census_bytes+bootstrap_bytes+32*(maximum+4096)
            retained=32*(packets+publication_bytes+endpoint_schedule)+INITIAL_RETAINED_BOUND
            read=8*(packets+publication_bytes+endpoint_schedule)+INITIAL_READ_BOUND
            written=4*(packets+publication_bytes)
            work=128*(read+written+retained)+INITIAL_WORK_BOUND
            logical={'read_bytes':read,'write_bytes':written,'retained_bytes':retained,'work_units':work,'process_starts':0}
            self.formula={'maximum_member_bytes':maximum,'packet_bytes':packet,'sequence_positions':SEQUENCES,
                'launch_nodes':GROUP_NODES,'launch_threads':threads,'launch_passes':GROUP_PASSES,
                'launch_raw_occurrences':raw_reads,'launch_raw_bytes':raw_bytes,'mandatory_files':publications,
                'all_packet_bytes':packets,'all_publication_bytes':publication_bytes,
                'worker_parent_stat_and_EOF_bytes':endpoint_stat_bytes,
                'worker_installed_source_check_bytes':source_validation_bytes,
                'worker_source_check_limit_per_sequence':16,'complete_bootstrap_objects':BOOTSTRAP_MAX_OBJECTS,
                'interpretation':'conservative upper reservation plus separate original direct-meter demand; not measured or lower-bound',
                'original_direct_meter_margin_multiplier':2}
            need(publications<=min(p['maximum_files'],plan['maximum_members']),
                 'whole required publication/launch occurrence schedule fits existing file caps')
            self.host_vector={**logical,**self.enforcement['host_limits']}
            self.arm_vector={**logical,**self.enforcement['arm_limits']}
            need(set(self.host_vector)==set(self.arm_vector)==set(DIMENSIONS),'only original seven resource dimensions')
            for partition,vector in (('host',self.host_vector),(a.condition,self.arm_vector)):
                for dimension,value in vector.items():
                    need(type(value)is int and 0<=value<=9007199254740991,'exact source-derived finite original vector')
                    if dimension in ('cpu_ns','wall_ns'):need(value>0,'no zero or guessed physical prefix')
                    cap=self.owner.partitions[partition][dimension]
                    if partition=='host':cap-=self.owner.terminal_reserve[dimension]
                    need(self.owner.used[partition][dimension]+2*value<=cap,'complete source schedule inside original partition before effects')
            # Count every potential live launch slot, including partially
            # acquired failures, plus retained carrier and fixed import slots.
            self._fd_admission(2*GROUP_NODES+6*threads+128+INITIAL_MAXIMUM_FDS+8)
            self.source_inputs={'profile':c.profile_pin,'policy':c.policy_pin,'request':a.arm.request.pin,
                'launch':a.arm.launch.pin,'pair':a.pair.pair_plan.pin,'enforcer':qualification.original_digest}
            self.complete=True;return self
        except BaseException as error:
            self.retain(error,'derive');self._close_fd_iterator();raise self.raw_first
    def require_original(self):
        if self.owner.parent.first_raw is not None:raise self.owner.parent.first_raw
        try:
            a=self.attempt;a.require_live_original()
            need(a.native_control_plan is self and self.complete and self.raw_first is None and
                 a.pair.contract is self.contract,'same completed actual source-derived plan')
            self.contract.native_anchor.require_completed_policy_profile_v3()
            need(self._input_identity()==self.input_digest,'complete original profile/owner/mandatory caller inputs unchanged')
            need(self.source_inputs=={'profile':self.contract.profile_pin,'policy':self.contract.policy_pin,
                'request':a.arm.request.pin,'launch':a.arm.launch.pin,'pair':a.pair.pair_plan.pin,
                'enforcer':self.contract.native_anchor.qualification.original_digest},'same exact complete original plan inputs')
            return self
        except BaseException as error:self.retain(error,'require_original');raise self.raw_first
    def reserve_channel(self,channel):
        if self.owner.parent.first_raw is not None:raise self.owner.parent.first_raw
        try:
            from .backend_native_reservations import NativeReservationLedger
            self.require_original();need(self.ledger is None and channel.attempt is self.attempt and
                self.attempt.native_channel is channel and not channel.setup_entered,'same actual unentered original channel')
            self.ledger=NativeReservationLedger(channel)
            self.ledger.reserve_control(self.host_vector,self.arm_vector)
            self.ledger.source_control_plan=self;return self.ledger
        except BaseException as error:
            self.retain(error,'reserve_channel');raise self.raw_first

def preflight_native_control_v4(attempt):
    from .development_handles import DevelopmentAttemptHandle
    need(type(attempt)is DevelopmentAttemptHandle,'actual source-owned original attempt before native effects')
    if attempt.owner.parent.first_raw is not None:raise attempt.owner.parent.first_raw
    need(attempt.native_control_plan is None,'one complete plan attempt including failed preflight')
    plan=NativeControlPlanV4(_PLAN,attempt);attempt.native_control_plan=plan
    return plan.derive()
