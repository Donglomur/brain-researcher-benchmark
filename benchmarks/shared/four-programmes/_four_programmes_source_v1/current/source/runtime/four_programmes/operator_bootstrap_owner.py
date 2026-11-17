"""One verified installed-entry origin; original counters are transferred once."""
import hashlib
import json
from .operator_intake import require,canonical,DIMENSIONS
from .operator_qualification import same_body
from .operator_records import _layout
from .resources import Share,RootResources
from .early_resources import ParentCustody,_PARENT

_PRIOR=object();_ROOT=object()

def _old_body(wrapper):
    raw=(json.dumps(wrapper['body'],sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)+'\n').encode('utf-8')
    d=wrapper['descriptor']
    require(len(raw)==d['bytes'] and hashlib.sha256(raw).hexdigest()==d['sha256'],
            'exact original existing resource encoding, not a new identity projection')
    return wrapper['body']

def _resource_branch(invocation):
    s=invocation.intake.body;resource=s['earlier_resource_input'];programme=resource['programme']
    _layout('OperatorResourceInputV1',resource)
    if programme=='NEURAL-098':
        body=_old_body(resource['resource_projection']);prelaunch=_old_body(resource['prelaunch_selection'])
        subject=_old_body(resource['prelaunch_subject'])
        require(prelaunch['subject']==resource['prelaunch_subject']['descriptor'] and
                subject['resource_subject']==resource['resource_projection']['descriptor'] and
                subject['campaign_id']==body['campaign_id']==s['clock']['campaign_id'],
                'same original earlier N098 subject/resource/campaign')
        from .n098_contract import original_interval,rows_valid
        original_interval(body,subject);rows=rows_valid(body)
        key=('H','N098_STARTUP');require(key in rows,'original N098 startup row, no extra envelope')
        window=subject['startup_window']
        require(window['start_ns']<=invocation.started_wall<window['stop_ns'],'original N098 startup interval')
        return body,resource['resource_projection']['descriptor'],rows[key],window
    body=_old_body(resource['plan'])
    require(body['programme']==programme and body['campaign_id']==s['clock']['campaign_id'],
            'exact original ordinary programme/campaign branch')
    rows=body['adapter_reservations'];r=invocation.launch_anchor['original_reservation']
    matches=[x for x in rows if x['reservation_id']==r['reservation_id']]
    require(len(matches)==1,'one complete selected original H row')
    require(len({x['reservation_id']for x in rows})==len(rows)and
            len({(x['owner_role'],x['stage'])for x in rows})==len(rows),'all original adapter identities unique')
    h=body['hard_envelope']
    require(sum(x['cpu_ns']for x in rows)<=h['cpu_ns'] and
            sum(x['retained_bytes']for x in rows)<=h['retained_storage_bytes'],
            'all original reservations inside unchanged opportunity')
    return body,resource['plan']['descriptor'],matches[0],None

class BootstrapTransferAttempt:
    def __init__(self,invocation):
        self.invocation=invocation;self.custodian=invocation.intake;self.entered=True
        self.resources=None;self.share=None;self.parent=None;self.complete=False
        self.raw_first=None;self.secondaries=[];self.observation=None
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.invocation.retain(error,'same-original bootstrap transfer')

class PriorStaticAdmission:
    def __init__(self,token,invocation,transfer):
        require(token is _PRIOR and transfer.complete,'actual completed earlier original transfer')
        self.invocation=invocation;self.transfer=transfer;self.parent=transfer.parent
        self.resources=transfer.resources;self.configuration=invocation.intake.body['static_values']
        self.plan_values=None;self.policy_values=None;self.static_selection=None
        self.canonical_publisher_binding=None;self.tool_owner=None;self.native_context_anchor_attempts={}
        self.root_admission=None;self.native_selection_attempted=False
    def require_original(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.invocation.require_observed_entry();self.parent.assert_live()
            require(self.invocation.evidence_verified and self.invocation.prior_static is self and
                    self.invocation.transfer is self.transfer and self.transfer.parent is self.parent and
                    self.transfer.share is self.parent.share and self.transfer.complete and
                    self.parent.first_raw is None,'same actual verified installed-entry original transfer')
            return self
        except BaseException as error:
            raise retain_source_failure(parent,error,'PriorStaticAdmission.require_original')

class RootBootstrapAdmission:
    def __init__(self,token,prior,resource):
        require(token is _ROOT and type(prior)is PriorStaticAdmission,'fixed private root issuer')
        self.prior_static=prior;self.parent=prior.parent;self.phase='verified_root';self.chain=None
        self.hard_envelope=resource['hard_envelope']
        self.schedule=prior.invocation.intake.body['matched_schedule']
        self.native_context_anchor_attempts=prior.native_context_anchor_attempts
        self.static_bind_attempted=False;self.n098_continuation=None
    def require_verified_root_v1(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.prior_static.require_original()
            require(self.prior_static.root_admission is self and
                    self.prior_static.invocation.root_admission is self and
                    self.phase in ('verified_root','static_bound'),'same actual original root admission')
            return self
        except BaseException as error:
            raise retain_source_failure(parent,error,'RootBootstrapAdmission.require_verified_root_v1')
    def require_original_parent_v1(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.require_verified_root_v1();return self.parent
        except BaseException as error:
            raise retain_source_failure(parent,error,'RootBootstrapAdmission.require_original_parent_v1')
    def require_canonical_publisher_binding_v3(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.require_verified_root_v1()
            from .operator_source_binding import CanonicalPublisherSourceBindingV3
            b=self.prior_static.canonical_publisher_binding
            require(type(b)is CanonicalPublisherSourceBindingV3 and b.admission is self,
                    'same actual earlier canonical publisher binding')
            b.require_original();return b
        except BaseException as error:
            raise retain_source_failure(parent,error,'RootBootstrapAdmission.require_canonical_publisher_binding_v3')
    def native_configuration_v1(self):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.require_verified_root_v1()
            # A detached metadata view never becomes a replacement owner.
            return json.loads(canonical(self.prior_static.configuration))
        except BaseException as error:
            raise retain_source_failure(parent,error,'RootBootstrapAdmission.native_configuration_v1')
    def bind_static_chain_once_v1(self,chain):
        from .early_resources import retain_source_failure
        parent=self.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            self.require_verified_root_v1()
            require(not self.static_bind_attempted and self.phase=='verified_root','one original static binding attempt')
            self.static_bind_attempted=True
            try:
                from .early_issuer import StaticInputChain,_STATIC
                from .backend_capture import CapturedRecord
                p=self.prior_static
                require(p.static_selection is not None and type(chain)is StaticInputChain and
                        chain._token is _STATIC and chain.owner is self.parent and
                        self.parent.static_chain_publisher.parent is self.parent,'actual same-owner completed static producer')
                for capture in (chain.subject,chain.policy,chain.profile,chain.plan):
                    require(type(capture)is CapturedRecord and capture.owner is self.parent and
                            capture._attempt.complete is capture and capture._attempt.raw_first is None,
                            'actual completed original static write/readback, no equal Pin reconstruction')
                require({k:v for k,v in chain.subject.body.items()if k!='schema'}==p.plan_values and
                        {k:v for k,v in chain.policy.body.items()if k not in ('schema','subject')}==p.policy_values and
                        chain.policy.body['subject']==chain.subject.pin and
                        chain.profile.body['bootstrap_policy']==chain.policy.pin and
                        chain.plan.body['private_issuer_profile']==chain.profile.pin,
                        'complete acyclic exact current static values')
                self.chain=chain;self.phase='static_bound';return self
            except BaseException as e:
                self.parent.retain(e,'seed_admission','identity_refusal','RootBootstrapAdmission.bind_static_chain_once_v1');raise
        except BaseException as error:
            raise retain_source_failure(parent,error,'RootBootstrapAdmission.bind_static_chain_once_v1')
    def require_same_source_policy(self,parent,policy,profile):
        from .early_resources import retain_source_failure
        owning_parent=self.parent
        if owning_parent.first_raw is not None:raise owning_parent.first_raw
        try:
            self.require_verified_root_v1()
            require(self.phase=='static_bound'and parent is owning_parent and
                    policy==self.chain.policy.body and profile==self.chain.profile.body,
                    'same actual admitted static source policy')
            return self
        except BaseException as error:
            raise retain_source_failure(owning_parent,error,'RootBootstrapAdmission.require_same_source_policy')

def transfer_original_bootstrap_v1(invocation):
    from .operator_entry import InstalledOperatorInvocation
    require(type(invocation)is InstalledOperatorInvocation,'actual installed entry, no wire constructor')
    invocation.require_observed_entry();c=invocation.intake;c.require_transfer_ready()
    require(invocation.evidence_verified and invocation.transfer is None,'full earlier source/domain verification')
    c.transfer_attempted=True;attempt=BootstrapTransferAttempt(invocation);invocation.transfer=attempt
    try:
        body,pin,row,window=_resource_branch(invocation);r=c.reservation;h=body['hard_envelope']
        require(pin==r['original_envelope'] and row['owner_role']=='H' and row['reservation_id']==r['reservation_id'] and
                row['stage']==r['stage'] and all(row[d]==r['limits'][d]for d in DIMENSIONS),
                'exact same existing original row; bootstrap is its bounded component')
        require(c.origin==h['origin_monotonic_ns'] and c.deadline==h['evidence_deadline_ns'] and
                c.origin<h['run_deadline_ns']<=c.deadline and
                invocation.intake.body['clock']['origin_monotonic_ns']==c.origin and
                invocation.intake.body['clock']['evidence_deadline_ns']==c.deadline,
                'same original clock and immutable resource envelope')
        c.observe_clock();require(c.active_span is not None,'actual original active clock span')
        share=Share(row,origin_ns=c.origin,deadline_ns=c.deadline);attempt.share=share
        share.spent=c.logical_counters;share._active=c.active_span
        native=c.native_prefix;share.bootstrap_custodian=c
        share.bootstrap_native_reserved={d:c.launch_anchor['native_preentry_reserved'][d]for d in ('process_starts','cpu_ns','wall_ns')}
        share.bootstrap_native_completed={d:native['completed'][d]for d in ('process_starts','cpu_ns','wall_ns')}
        share.bootstrap_native_slack={d:share.bootstrap_native_reserved[d]-share.bootstrap_native_completed[d]for d in share.bootstrap_native_reserved}
        share.process_starts=native['completed']['process_starts'];share.cpu_ns=native['completed']['cpu_ns'];share.wall_ns=native['completed']['wall_ns']
        if window is not None:share._selected_window=dict(window)
        share._raw_error_history=list((e,None)for e,_site in c.secondaries)
        require(share.spent is c.logical_counters and share.spent.storage is c.spent and
                share._active is c.active_span,'same actual counter storage/span, no begin or reset')
        # Resource plan construction here has no schema/IO effect: all fixed
        # validation was charged to the original custodian before this point.
        if body['programme']!='NEURAL-098':
            resource=RootResources.__new__(RootResources);attempt.resources=resource
            resource.staged=False;resource.plan=body;resource.pin=pin;resource.delegated=False;resource.terminal=None
            resource.rows={(x['owner_role'],x['stage']):x for x in body['adapter_reservations']}
            resource.shares={(row['owner_role'],row['stage']):share}
        else:
            # The existing later StagedN098Resources remains the only
            # scientific owner. This earlier handle holds no delegation API.
            attempt.n098_projection=body;attempt.n098_projection_pin=pin
        s=invocation.intake.body
        selection={'path':invocation.launch_anchor['operator_selection_path'],
                   'bytes':len(c.raw),'sha256':hashlib.sha256(c.raw).hexdigest()}
        parent=ParentCustody(_PARENT,share,clock=s['clock'],identity=s['entry_identity'],
            custody=selection,source=invocation.profile['entry_source'],nonce=s['nonce'])
        attempt.parent=parent;parent.operator_bootstrap_transfer=attempt
        parent.unknown.update(x for x in c.unknown if x in DIMENSIONS)
        attempt.observation={'schema':'four_bootstrap_prefix_transfer_v1','operator_selection':selection,
            'original_attempt':s['attempt_id'],'reservation_id':r['reservation_id'],
            'original_counter_identity':r['original_counter_identity'],'original_origin_ns':c.origin,
            'original_deadline_ns':c.deadline,'before':native,'intake_reserved':dict(c.spent),
            'intake_completed':dict(c.completed),'same_counter_storage':True,'same_active_span':True,
            'fd_close_observed':True,'unknown_dimensions':sorted(x for x in c.unknown if x in DIMENSIONS)}
        attempt.complete=True;c.transferred=True
        prior=PriorStaticAdmission(_PRIOR,invocation,attempt);invocation.prior_static=prior
        root=RootBootstrapAdmission(_ROOT,prior,body);prior.root_admission=root;invocation.root_admission=root
        parent.operator_root_admission=root
        root.require_verified_root_v1();return root
    except BaseException as e:attempt.retain(e);raise attempt.raw_first

