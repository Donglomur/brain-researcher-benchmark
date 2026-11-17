"""Prospective separate native-root/worker-entry evidence admission.

These are new source-defined interfaces, never recovered historical reports.
The protected operator V2 selection supplies the independently selected issuer,
procedure, environment and exact report identities before Q1. Q1's six-domain
reports cannot stand in for either domain. No qualification is run here.
"""
import hashlib
from .operator_intake import require,canonical
from .operator_records import _layout
from .early_resources import retain_source_failure

DOMAINS=('native_root','worker_entry')
CASES={'native_root':('root_mounts','root_isolation'),
       'worker_entry':('sealed_carrier','credential_channel','fixed_import','descendant_isolation','control_enforcement')}
def record(fields):return {'record':fields}
def seq(item,maximum):return {'ordered_list':item,'max':maximum}
def literal(value):return {'literal':value}
AUTHORITY=record({'domain':{'enum':list(DOMAINS)},'report':'Pin','qualifier_source':'Pin',
                  'procedure_source':'Pin','environment':'Pin'})
COST=record({'original_attempt':'Text','process':'OriginalProcessIdentity','observed_through_ns':'UInt',
             'observed':'Dimensions','unknown_dimensions':literal([])})
INVOCATION=record({'schema':literal('four_original_native_qualification_invocation_v4'),
    'domain':{'enum':list(DOMAINS)},'attempt':'Text','qualifier_source':'Pin','procedure_source':'Pin',
    'environment':'Pin','source_admission':'Pin','configuration_sha256':'SHA256',
    'process':'OriginalProcessIdentity','started_ns':'UInt'})
ROOT_ROW=record({'root_id':'Text','absolute_mount':'Text','uid':'UInt','device':'UInt','inode':'UInt',
    'mode':'UInt','mount_id':'PositiveUInt','filesystem_flags':'UInt','namespace':'NamespaceIdentityV1',
    'source_qualification':'Pin'})
PROBE=record({'name':'Text','attempt':'Text','ordinal':'UInt',
              'observer_source':'Pin','observed_errno':'UInt','observed_ns':'UInt'})
PHYSICAL_LIMITS=record({'cpu_ns':'PositiveUInt','wall_ns':'PositiveUInt'})
CONTROL_ENFORCEMENT=record({'installed_profile':'Pin','base_development_profile':'Pin',
    'whole_envelope':'Pin','worker_envelope':'Pin','source_admission':'Pin','enforcer_source':'Pin',
    'host_limits':PHYSICAL_LIMITS,'arm_limits':PHYSICAL_LIMITS,
    'host_limit_readback':PHYSICAL_LIMITS,'arm_limit_readback':PHYSICAL_LIMITS,
    'fd_peak_limit':'PositiveUInt','fd_limit_readback':'PositiveUInt',
    'fd_enforcement_kind':literal('RLIMIT_NOFILE_and_original_slot_census'),
    'original_process':'OriginalProcessIdentity','observed_ns':'UInt'})
RESULTS={
 'control_enforcement':CONTROL_ENFORCEMENT,
 'root_mounts':record({'roots':seq(ROOT_ROW,5),'same_namespace_mountinfo':'Pin',
                       'nofollow_components':literal(True),'before_after_identity_equal':literal(True)}),
 'root_isolation':record({'probes':seq(PROBE,3),'selected_roots':'SHA256'}),
 'sealed_carrier':record({'fd':literal(199),'access_mode':literal(0),'seals':literal(15),
    'offset':literal(0),'descriptor_extent':'PositiveUInt','body_extent':'PositiveUInt',
    'eof_bytes':literal(0),'write_errno':'UInt','truncate_errno':'UInt','close_count':literal(1)}),
 'credential_channel':record({'fd':literal(198),'family':literal('AF_UNIX'),
    'socket_type':literal('SOCK_SEQPACKET'),'passcred':literal(True),'nonblocking':literal(True),
    'cloexec':literal(True),'peer':'OriginalProcessIdentity','before_start_ticks':'UInt',
    'after_start_ticks':'UInt','pidfd_ready':literal(False),'namespace':'NamespaceIdentityV1'}),
 'fixed_import':record({'entry_argv':seq('Text',3),'interpreter':'Pin','entry_script':'Pin',
    'fixed_agent_entry_source':'Pin','source_closure':seq('Pin',8192),
    'loaded_source_closure':seq('Pin',8192),'environment':'Pin','unselected_imports':literal([])}),
 'descendant_isolation':record({'probes':seq(PROBE,4),'descendant_fd198_occurrences':literal(0),
    'descendant_fd199_occurrences':literal(0),'foreign_endpoint_accepted':literal(False)})}
OBS_FIELDS={'schema':literal('four_original_native_qualification_observation_v4'),
 'case':{'enum':[c for values in CASES.values()for c in values]},'invocation':'Pin',
 'observer_source':'Pin','process':'OriginalProcessIdentity','observed_ns':'UInt','result':None}
COMPLETION=record({'schema':literal('four_original_native_qualification_completion_v4'),
 'invocation':'Pin','observations':seq('Pin',5),'attempt':'Text','process':'OriginalProcessIdentity',
 'waited_pid':'PositiveUInt','exit_code':literal(0),'signal':literal(None),
 'started_ns':'UInt','completed_ns':'UInt','cost':COST})
REPORT_FIELDS={'schema':literal('four_native_qualification_report_v4'),'domain':{'enum':list(DOMAINS)},
 'deployment_id':'Text','installed_closure':'Pin','source_admission':'Pin','configuration_sha256':'SHA256',
 'invocation':record({'descriptor':'Pin','body':INVOCATION}),
 'observations':None,'completion':record({'descriptor':'Pin','body':COMPLETION})}

def _wrapper(wrapper,spec):
    _layout(record({'descriptor':'Pin','body':spec}),wrapper)
    raw=canonical(wrapper['body']);d=wrapper['descriptor']
    require(len(raw)==d['bytes']and hashlib.sha256(raw).hexdigest()==d['sha256'],
            'complete selected original native artifact body, not an uninspected alias')
    return wrapper['body']

def validate_native_evidence_bundle_v4(bundle):
    require(type(bundle)is dict and set(bundle)=={'schema','authorities','reports'}and
            bundle['schema']=='four_native_qualification_evidence_bundle_v4','closed native evidence bundle')
    _layout(seq(AUTHORITY,2),bundle['authorities'])
    require([r['domain']for r in bundle['authorities']]==list(DOMAINS),'both independent native domains in fixed order')
    require(type(bundle['reports'])is list and len(bundle['reports'])==2,'both full original reports')
    for domain,wrapper in zip(DOMAINS,bundle['reports']):
        require(type(wrapper)is dict and set(wrapper)=={'descriptor','body'},'complete report wrapper')
        body=wrapper['body'];require(type(body)is dict and set(body)==set(REPORT_FIELDS),'closed complete native report')
        for key,spec in REPORT_FIELDS.items():
            if key!='observations':_layout(spec,body[key])
        require(body['domain']==domain,'native domain order')
        require(type(body['observations'])is list and len(body['observations'])==len(CASES[domain]),'complete fixed case roster')
        _wrapper(body['invocation'],INVOCATION);_wrapper(body['completion'],COMPLETION)
        for case,observation in zip(CASES[domain],body['observations']):
            fields={**OBS_FIELDS,'case':literal(case),'result':RESULTS[case]}
            _wrapper(observation,record(fields))
        # Result variants were validated above; do not introduce an open JSON type.
        d=wrapper['descriptor'];_layout('Pin',d);raw=canonical(body)
        require(len(raw)==d['bytes']and hashlib.sha256(raw).hexdigest()==d['sha256'],'exact complete native report identity')
    return bundle

def _probe_rows(rows,names,source,attempt,started,finished):
    require([p['name']for p in rows]==list(names),'all fixed isolation probes, none omitted')
    for ordinal,p in enumerate(rows):
        require(p['observer_source']==source and p['attempt']==attempt and p['ordinal']==ordinal and
                p['observed_errno']in (1,9,13)and started<=p['observed_ns']<=finished,
                'original source-owned refused probe, no status-only isolation assertion')

class NativeQualificationAdmissionV4:
    """Private completed verifier product, bound to the original root owner."""
    def __init__(self,token,root,bundle,reports):
        require(token is _QUALIFIED,'fixed complete native evidence verifier')
        self.root=root;self.bundle=bundle;self.reports=reports;self._token=token
        self.bound=len(root.prior_static.invocation.intake.raw)
        self.original_digest=hashlib.sha256(canonical(bundle)).hexdigest()
    def require_original(self):
        root=self.root;parent=root.parent
        if parent.first_raw is not None:raise parent.first_raw
        try:
            root.require_verified_root_v1()
            parent.share.charge('work_units',self.bound*64+4096)
            parent.share.charge('retained_bytes',self.bound*4+4096)
            require(hashlib.sha256(canonical(self.bundle)).hexdigest()==self.original_digest,
                    'unchanged complete original evidence after admission')
            require(self._token is _QUALIFIED and getattr(root,'native_qualification_admission',None)is self and
                    root.prior_static.invocation.intake.body['native_evidence']is self.bundle,
                    'same protected selected native evidence and original verifier product')
            return self
        except BaseException as error:raise retain_source_failure(parent,error,'NativeQualificationAdmissionV4.require_original')

_QUALIFIED=object()
def verify_native_qualification_v4(root):
    from .operator_bootstrap_owner import RootBootstrapAdmission
    require(type(root)is RootBootstrapAdmission,'same actual Q1 root, no supplied report authority')
    parent=root.parent
    if parent.first_raw is not None:raise parent.first_raw
    try:
        root.require_verified_root_v1();prior=root.prior_static;inv=prior.invocation
        require(not getattr(root,'native_qualification_attempted',False),'one native evidence admission including failed original')
        root.native_qualification_attempted=True
        bundle=inv.intake.body['native_evidence'];root.native_qualification_input=bundle
        bound=len(inv.intake.raw);parent.share.charge('work_units',bound*64+4096)
        parent.share.charge('retained_bytes',bound*16+4096)
        validate_native_evidence_bundle_v4(bundle)
        config=prior.configuration;reports={};all_pins=[]
        for domain,authority,wrapper in zip(DOMAINS,bundle['authorities'],bundle['reports']):
            report=wrapper['body'];start=report['invocation']['body'];end=report['completion']['body']
            selected=config['native_root_configuration'if domain=='native_root'else'entry_configuration']
            require(authority['report']==wrapper['descriptor']==selected['native_qualification'],
                    'independently preselected native domain report, never Q1 report substitution')
            require(report['deployment_id']==inv.profile['deployment_id']and
                    report['installed_closure']==inv.profile['installed_closure']and
                    report['source_admission']==config['plan_constants']['source_admission']and
                    report['configuration_sha256']==hashlib.sha256(canonical({k:v for k,v in selected.items()if k!='native_qualification'})).hexdigest(),
                    'exact installed deployment/source and earlier complete native configuration')
            require(start['domain']==domain and start['qualifier_source']==authority['qualifier_source']and
                    start['procedure_source']==authority['procedure_source']and start['environment']==authority['environment']and
                    start['source_admission']==report['source_admission']and start['configuration_sha256']==report['configuration_sha256']and
                    start['process']['source']==authority['qualifier_source'],'independent fixed qualifier procedure/source/environment')
            require(end['invocation']==report['invocation']['descriptor']and end['attempt']==start['attempt']and
                    end['process']==start['process']and end['waited_pid']==start['process']['pid']and
                    end['started_ns']==start['started_ns']<=end['completed_ns']<=inv.intake.first_wall,
                    'complete original qualifier terminal precedes intake, no future receipt')
            cost=end['cost'];require(cost['process']==start['process']and cost['original_attempt']==start['attempt']and
                    start['started_ns']<=cost['observed_through_ns']<=end['completed_ns']and not cost['unknown_dimensions'],'same original qualifier costs')
            require(end['observations']==[r['descriptor']for r in report['observations']],'complete original ordered observation roster')
            observations={}
            for row in report['observations']:
                body=row['body'];require(body['invocation']==report['invocation']['descriptor']and
                    body['observer_source']==authority['procedure_source']and body['process']==start['process']and
                    start['started_ns']<=body['observed_ns']<=end['completed_ns'],'actual same original observation source/process/time')
                observations[body['case']]=body['result'];all_pins.append(row['descriptor'])
            if domain=='native_root':
                observed=observations['root_mounts'];roots=selected['roots']
                require(len(observed['roots'])==len(roots)and observed['roots'],'whole selected root population')
                for actual,wanted in zip(observed['roots'],roots):
                    require(actual['root_id']==wanted['root_id']and actual['absolute_mount']==wanted['absolute_mount']and
                        actual['uid']==wanted['selected_uid']and actual['filesystem_flags']&1 and actual['mount_id']>0 and
                        actual['source_qualification']==selected['source_qualification'],'full actual selected readonly root observation')
                isolate=observations['root_isolation']
                require(isolate['selected_roots']==hashlib.sha256(canonical(roots)).hexdigest(),'complete root isolation subject')
                _probe_rows(isolate['probes'],('symlink_escape','alternate_namespace_write','untrusted_reopen'),
                            authority['procedure_source'],start['attempt'],start['started_ns'],end['completed_ns'])
            else:
                carrier=observations['sealed_carrier'];channel=observations['credential_channel'];loaded=observations['fixed_import']
                require(carrier['descriptor_extent']==carrier['body_extent']and carrier['write_errno']in (1,9)and
                        carrier['truncate_errno']in (1,9),'actual sealed readonly exact extent mutation refusals')
                require(channel['before_start_ticks']==channel['after_start_ticks']and channel['peer']['source']==inv.profile['launcher_source'],
                        'actual original parent channel identity/start, not only PID equality')
                require(loaded['entry_argv']==[selected['interpreter_absolute'],'-I',selected['entry_absolute']]and
                        all(loaded[k]==selected[k]for k in ('interpreter','entry_script','fixed_agent_entry_source','source_closure'))and
                        loaded['loaded_source_closure']==selected['source_closure']and
                        loaded['environment']==config['base_agent_policy']['body']['environment'],
                        'full exact fixed entry/import/environment closure')
                control=observations['control_enforcement'];base=config['base_development_profile']
                require(control['installed_profile']==inv.launch_anchor['installed_profile']and
                    control['base_development_profile']==base['descriptor']and
                    control['whole_envelope']==base['body']['whole_envelope']and
                    control['worker_envelope']==base['body']['worker_envelope']and
                    control['source_admission']==report['source_admission']and
                    control['enforcer_source']==authority['procedure_source']and
                    control['original_process']==start['process']and
                    start['started_ns']<=control['observed_ns']<=end['completed_ns'],
                    'separate actual installed-profile/source/envelope control enforcer observation')
                require(control['host_limits']==control['host_limit_readback']and
                    control['arm_limits']==control['arm_limit_readback']and
                    control['fd_peak_limit']<=control['fd_limit_readback'],
                    'actual nonzero original control physical limits and separate FD peak, not a new grant')
                _probe_rows(observations['descendant_isolation']['probes'],
                    ('child_fd198','child_fd199','parent_proc_reopen','foreign_endpoint'),authority['procedure_source'],
                    start['attempt'],start['started_ns'],end['completed_ns'])
            all_pins.extend((wrapper['descriptor'],report['invocation']['descriptor'],report['completion']['descriptor']))
            reports[domain]=report
        require(len({canonical(x)for x in all_pins})==len(all_pins),'distinct actual original reports and artifact occurrences')
        admitted=NativeQualificationAdmissionV4(_QUALIFIED,root,bundle,reports)
        root.native_qualification_admission=admitted;return admitted
    except BaseException as error:raise retain_source_failure(parent,error,'verify_native_qualification_v4')
