"""Independent deployment selection and concrete authenticated evidence transport.

The measurement server is an explicit external implementation dependency. This
client does not implement missing kernel/namespace/accounting instrumentation.
No candidate predictions or scientific scores may arrive on this interface.
"""
import os
import socket
import stat
import struct
from ach_util import need,pin,pin_bytes,encode,decode,read_exact,integer,require_pin,exact_fields,finish_owned

class Authority:
    def __init__(self,selection_path,selection_pin,source_pin,ledger,helpers):
        self.ledger,self.helpers=ledger,helpers
        self.selection=decode(read_exact(selection_path,selection_pin,1048576,ledger),1048576)
        s=self.selection
        need(s.get('schema')=='ach_independently_selected_deployment_v1' and s.get('execution_enabled') is True,
             'no independently selected production deployment is installed')
        need(s['controller_source_pin']==source_pin and s['origin_ns']==ledger.origin and
             s['scientific_ns']==ledger.scientific and s['closeout_ns']==ledger.closeout and s['outer_ns']==ledger.outer,
             'same full source closure and original whole-operation clocks')
        for name in ('issuer_receipt_pin','runtime_profile_pin','source_environment_pin','physical_observer_implementation_pin',
                     'measurement_coverage_semantics_pin','historical_authoring_evidence_pin','inputs_pin'):
            require_pin(s[name])
        need(s['measurement_implementation_installed'] is True,'missing observer implementation is not qualification alone')
        # Authentic selection/issuer custody is supplied by the independent
        # launcher, never established by the digest or this Boolean itself.
        self.pin=selection_pin;self.serial=0;self.raw=[];self.journal=None
    def bind_journal(self,journal):
        from ach_journal import Journal
        need(type(journal) is Journal and journal.ledger is self.ledger and self.journal is None,
             'one concrete private original-ledger evidence journal')
        self.journal=journal
    def verify_native(self,qualification,contract):
        need(pin(qualification)==self.selection['native_qualification_pin'] and
             pin(contract)==self.selection['native_contract_pin'],'exact independently selected native component')
        return True
    def validate_inputs(self,inputs):
        need(pin(inputs)==self.selection['inputs_pin'],'all independently selected operation operands')
    def validate_clients(self,provider,observer):
        transport=self.helpers.get('transport')
        need(type(provider) is transport.ProviderClient and type(observer) is transport.ObserverClient,
             'same exact frozen concrete transport namespaces')
        need(provider.admission==observer.admission,'same complete source/authority/deployment across peers')
        d=provider.admission
        need(pin(d)==self.selection['transport_deployment_pin'] and
             d['source_digest']==self.selection['controller_source_pin']['sha256'] and
             d['authority_receipt']==self.selection['issuer_receipt_pin'] and
             d['runtime_source_environment_admission']==self.selection['source_environment_pin'],
             'independently selected complete source/runtime/authority')
        need(provider.ledger is observer.ledger is self.ledger,'same original whole-program ledger')
    def evidence(self,kind,binding,raw,context=None):
        """Actual Unix peer exchange for observations only; no injectable executor."""
        need(kind in ('job','native_overhead','historical_commitment','query_journal','final_controller_seal'),
             'fixed non-scientific evidence operation')
        need(self.journal is not None,'durable private evidence journal before any observation exchange')
        self.serial+=1;s=self.selection;end=self.ledger.closeout if kind!='historical_commitment' else self.ledger.scientific
        cutoff='closeout' if kind!='historical_commitment' else 'scientific';self.ledger.tick(cutoff)
        request={'schema':'ach_independent_measurement_request_v1','kind':kind,'sequence':self.serial,
            'binding_digest':binding,'context':context,'raw_observation_pin':pin(raw),
            'controller_source_pin':s['controller_source_pin'],'authority_pin':self.pin,
            'origin_ns':self.ledger.origin,'scientific_ns':self.ledger.scientific,
            'closeout_ns':self.ledger.closeout,'outer_ns':self.ledger.outer}
        cap=integer(s['measurement_message_bytes'],1);body=encode(request);need(len(body)<=cap,'measurement request cap')
        self.ledger.reserve({'requests':1,'write_bytes':len(body)+8},'independent measurement request',cutoff=cutoff)
        self.journal.append('measurement_exchange_attempt',{'request':request,'raw_observation':raw},cutoff=cutoff)
        # A decoded reply is retained before validation or owned-resource close.
        # Failed validation remains explicitly unvalidated; it is never evidence.
        record=None
        try:
            with self.ledger.live(3*cap,'bounded independent measurement transport',cutoff=cutoff):
                endpoint=s['measurement_endpoint'];status=os.stat(endpoint,follow_symlinks=False)
                need(stat.S_ISSOCK(status.st_mode),'independently installed ordinary measurement socket')
                sock=None;primary=None
                try:
                    sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
                    sock.settimeout(max(.001,(end-self.ledger.clock())/1e9));sock.connect(endpoint)
                    peer=self.helpers.get('transport').peer_identity(sock);expected=s['measurement_peer']
                    need(peer['uid']==expected['uid'] and peer['pid']==expected['pid'],'independent full measurement peer identity')
                    need(peer['pid'] not in (os.getpid(),*s['untrusted_producer_pids']),'measurement authority separate from producers')
                    self.ledger.tick(cutoff);sock.sendall(struct.pack('!Q',len(body))+body)
                    receive=self.helpers.get('transport').receive
                    size=struct.unpack('!Q',receive(sock,8,self.ledger,end,cutoff))[0];need(size<=cap,'measurement reply extent')
                    reply=decode(receive(sock,size,self.ledger,end,cutoff),cap)
                    record={'request':request,'reply':reply,'raw':raw,'validation_status':'received_unvalidated'}
                    self.raw.append(record)
                    exact_fields(reply,('request_pin','source_pin','implementation_pin','profile_pin','coverage_semantics_pin','evidence'),
                                 'typed independent observation reply')
                    need(reply['request_pin']==pin_bytes(body) and reply['source_pin']==s['controller_source_pin'] and
                         reply['implementation_pin']==s['physical_observer_implementation_pin'] and
                         reply['profile_pin']==s['runtime_profile_pin'] and
                         reply['coverage_semantics_pin']==s['measurement_coverage_semantics_pin'],
                         'same actual selected observer implementation and coverage semantics')
                    record['validation_status']='authenticated_selected_source_and_request'
                    self.journal.append('authenticated_measurement_exchange',record,cutoff=cutoff)
                except BaseException as error:
                    primary=error;raise
                finally:
                    finish_owned([('measurement socket close',sock.close)] if sock is not None else [],primary)
            self.ledger.tick(cutoff)
            return reply['evidence'],pin(reply)
        except BaseException as error:
            if record is not None:
                try:error.ach_measurement_exchange=record
                except BaseException:pass
            finish_owned([('measurement exchange failure journal',lambda:self.journal.append(
                'measurement_exchange_failure',{'request_pin':pin_bytes(body),'error_type':type(error).__name__,
                'pending_exchange':record,'logical_accounting':self.ledger.report()},cutoff='closeout'))],error)
            raise

class JoinedObserver:
    """Raw concrete observer plus independently authenticated missing facts.

    Raw observations, including all unknown dimensions, remain in provenance.
    The new record is an explicit evidence join, never a mutation of raw facts.
    External semantics must cover each declared resource domain and all work.
    """
    DOMAINS=('filesystem','pipes','sockets','network','source_and_hashing','metadata','retention','live_memory')
    def __init__(self,observer,authority):self.raw_client=observer;self.authority=authority;self.joined=[]
    def _accounting(self,evidence,kind):
        exact_fields(evidence,('coverage','resources','isolation','producer_finished_ns','observation_finished_ns'),
                     'complete independent physical observation')
        coverage=evidence['coverage']
        exact_fields(coverage,('domains','process_roster_pin','operation_roster_pin','interval_partition_pin',
                              'partial_attempts_included','final_serialization_included','live_semantics','retained_semantics'),
                     'complete physical measurement coverage')
        need(coverage['domains']==list(self.DOMAINS) and coverage['partial_attempts_included'] is True and
             coverage['final_serialization_included'] is True and
             coverage['live_semantics']=='synchronized_max_over_time_all_attributed_live_bytes' and
             coverage['retained_semantics']=='all_retained_artifacts_at_scope_closure',
             'no cgroup-only/read-counter/peak-sum substitute for full profile')
        for name in ('process_roster_pin','operation_roster_pin','interval_partition_pin'):require_pin(coverage[name])
        resources=evidence['resources'];exact_fields(resources,('read_bytes','write_bytes','retained_bytes','live_bytes'),'measured units are bytes')
        for value in resources.values():integer(value)
        isolation=evidence['isolation'];exact_fields(isolation,('namespace_mount_evidence','source_environment_evidence',
            'no_foreign_custody_evidence'),'actual independently measured isolation evidence')
        for value in isolation.values():require_pin(value)
        for key in ('producer_finished_ns','observation_finished_ns'):integer(evidence[key])
        need(self.authority.ledger.origin<=evidence['producer_finished_ns']<=evidence['observation_finished_ns']<self.authority.ledger.closeout,
             'original producer and observation clocks are distinct')
        return resources
    def close_job(self,context,job_id,result,primary,binding,origin,deadline):
        raw=self.raw_client.close_job(context,job_id,result,primary,binding,origin,deadline)
        evidence,evidence_pin=self.authority.evidence('job',binding,raw,context)
        resources=self._accounting(evidence,'job')
        # Natural exit/EOF/cgroup facts still come from the actual raw supervisor.
        # This join cannot turn a real failed process into a successful one.
        joined={**raw,'resources_complete':True,'resources':resources,'view_isolation_verified':True,
            'unknown_foreign_custody':False,'unknown':[],
            'finished_ns':evidence['producer_finished_ns'],'observation_finished_ns':evidence['observation_finished_ns'],
            'raw_observation_pin':pin(raw),'raw_unknowns':raw.get('unknown'),
            'accounting_and_isolation_evidence_pin':evidence_pin,'evidence_join_not_raw_measurement':True}
        self.joined.append({'raw':raw,'evidence':evidence,'joined':joined});return joined
    def commit_all_programs(self,freeze,origin,deadline):
        raw=self.raw_client.commit_all_programs(freeze,origin,deadline)
        evidence,evidence_pin=self.authority.evidence('historical_commitment',pin(freeze)['sha256'],raw)
        exact_fields(evidence,('freeze_pin','historical_authoring_evidence_pin','source_seal_pin','contexts','no_numeric_exposure_before_seal'),
                     'actual four-context source history')
        need(evidence['freeze_pin']==pin(freeze) and evidence['contexts']==freeze['contexts'] and
             evidence['historical_authoring_evidence_pin']==self.authority.selection['historical_authoring_evidence_pin'] and
             evidence['no_numeric_exposure_before_seal'] is True,'independent exact complete authoring history')
        require_pin(evidence['source_seal_pin'])
        return {**raw,'durable_source_seal':True,'all_four_independently_authored':True,
            'before_numeric_exposure':True,'authoring_views_verified':True,'raw_observation_pin':pin(raw),
            'joined_historical_evidence_pin':evidence_pin,'unknown':[],'raw_unknowns':raw.get('unknown')}
    def close_dispatch(self,binding,origin,deadline):
        raw=self.raw_client.close_dispatch(binding,origin,deadline)
        evidence,evidence_pin=self.authority.evidence('native_overhead',binding,raw)
        resources=self._accounting(evidence,'native_overhead')
        return {**raw,'complete_non_job_accounting':True,'non_job_resources':resources,
            'finished_ns':evidence['producer_finished_ns'],'raw_observation_pin':pin(raw),
            'joined_accounting_evidence_pin':evidence_pin,'raw_unknowns':raw.get('unknown')}
    def record_failure(self,*args):return self.raw_client.record_failure(*args)
