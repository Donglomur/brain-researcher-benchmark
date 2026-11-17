"""Prospective fixed installed expectation and actual inherited-evidence join.

The installed literal digest is the external trust anchor. This verifier cannot
qualify a deployment, manufacture a report or turn FD payload equality into an
issuer. The full earlier worker-entry report is separately installed and its
closed original invocation/observation/completion evidence is verified here.
"""
import hashlib
import sys
from .common import need
from .backend_json import canonical,parse
from .operator_entry import _code_identity
from .operator_records import _layout
from .native_qualification_v4 import (AUTHORITY,INVOCATION,COMPLETION,OBS_FIELDS,
    RESULTS,CASES,record,literal,_wrapper,_probe_rows)
from . import worker_installed_expectation_data as installed

_ADMISSION=object()
_attempt=None
_FIELDS={'schema','deployment_id','environment','source_admission','installed_closure',
    'launcher_source','entry_selection','entry_configuration','canonical_publisher_source',
    'clock_mapping_source','loaded_sources','qualification_authority','qualification_report','control_selection',
    'initialization_physical_profile'}
_PIN_FIELDS=('environment','source_admission','installed_closure','launcher_source',
    'entry_selection','canonical_publisher_source','clock_mapping_source')

class WorkerPreHelloAdmissionV3:
    def __init__(self,token,physical):
        need(token is _ADMISSION,'fixed installed entry-local issuer')
        self.physical=physical;self.raw=None;self.expected=None;self.digest=None
        self.entered=False;self.complete=False;self.raw_first=None;self.secondaries=[]
        self.loaded=();self.endpoint=None;self.validation_count=0;self.initialization_profile=None
    def retain(self,error):
        if self.raw_first is None:self.raw_first=error
        elif error is not self.raw_first:self.secondaries.append(error)
        self.physical.retain(error,'installed_worker_expectation')
    def require_original(self):
        if self.raw_first is not None:raise self.raw_first
        try:
            p=self.physical;p.require_physical_complete_v3()
            need(_attempt is self and p.prehello_admission is self and self.complete and
                 p.source_qualified and self.raw is installed.EXPECTATION_RAW and
                 self.digest==installed.EXPECTED_SHA256,
                 'same actual once-only installed issuer and retained physical owner')
            # Installed module/class/code identity is observed again; its cost
            # belongs to the same original prepaid arm control vector.
            if self.endpoint is not None:self.endpoint.reserve_source_check(len(self.raw))
            else:
                p._work(len(self.raw)*128+4096);p._retain_bound(len(self.raw)*16+4096)
            self.validation_count+=1
            need(hashlib.sha256(self.raw).hexdigest()==self.digest and
                 canonical(self.expected,installed.MAXIMUM_EXPECTATION_BYTES)==self.raw,
                 'unchanged complete independently installed expectation')
            for module,row in self.loaded:
                need(sys.modules.get(row['module'])is module and module.__file__==row['absolute_file'] and
                     _code_identity(module)==row['loaded_code_sha256'],
                     'same actual loaded original module and executable source identity')
            return self
        except BaseException as error:self.retain(error);raise self.raw_first

def _validate_installed(expectation,physical):
    need(type(expectation)is dict and set(expectation)==_FIELDS and
         expectation['schema']=='four_installed_worker_expectation_v2','closed worker-only installed expectation with physical initialization selection')
    for field in _PIN_FIELDS:_layout('Pin',expectation[field])
    need(type(expectation['deployment_id'])is str and expectation['deployment_id'], 'actual installed deployment identity')
    entry=expectation['entry_configuration']
    need(type(entry)is dict and set(entry)=={'interpreter_absolute','entry_absolute','interpreter','entry_script',
         'fixed_agent_entry_source','source_closure'},'complete original fixed entry projection')
    for key in ('interpreter','entry_script','fixed_agent_entry_source'):_layout('Pin',entry[key])
    need(all(type(entry[k])is str and entry[k].startswith('/')for k in ('interpreter_absolute','entry_absolute')),
         'fixed installed absolute interpreter/entry, no PATH')
    need(sys.executable==entry['interpreter_absolute'] and sys.argv==[entry['entry_absolute']] and
         sys.flags.isolated and sys.flags.ignore_environment and sys.flags.no_user_site,
         'actual original installed fixed interpreter and entry invocation')
    rows=expectation['loaded_sources'];need(type(rows)is list and 0<len(rows)<=2048,'finite complete installed closure')
    need([r['module']for r in rows]==sorted(set(r['module']for r in rows)), 'unique ordered complete loaded source roles')
    loaded=[]
    for row in rows:
        need(type(row)is dict and set(row)=={'module','absolute_file','source','loaded_code_sha256'},'closed source row')
        _layout('Pin',row['source']);_layout('SHA256',row['loaded_code_sha256'])
        need(type(row['absolute_file'])is str and row['absolute_file'].startswith('/') and
             row['module'].startswith(__package__+'.'),'fixed installed package source row')
        module=sys.modules.get(row['module'])
        need(module is not None and module.__file__==row['absolute_file'] and
             _code_identity(module)==row['loaded_code_sha256'],'actual earlier loaded code, no dynamic import')
        loaded.append((module,row))
    package_modules=sorted(name for name,mod in tuple(sys.modules.items())if
        name.startswith(__package__+'.') and name!=installed.__name__ and getattr(mod,'__file__',None))
    need(package_modules==[r['module']for r in rows], 'no unselected loaded package dependency')
    need(entry['source_closure']==[r['source']for r in rows], 'complete exact installed source projection')
    authority=expectation['qualification_authority'];_layout(AUTHORITY,authority)
    need(authority['domain']=='worker_entry','separate genuine worker-entry qualification, never Q1')
    wrapper=expectation['qualification_report']
    need(type(wrapper)is dict and set(wrapper)=={'descriptor','body'},'closed original selected report wrapper')
    report=wrapper['body']
    fields={'schema','domain','deployment_id','installed_closure','source_admission','configuration_sha256',
            'invocation','observations','completion'}
    need(type(report)is dict and set(report)==fields and report['schema']=='four_worker_installed_qualification_report_v1'and
         report['domain']=='worker_entry','complete earlier native worker report')
    _layout('Pin',wrapper['descriptor']);raw=canonical(report,installed.MAXIMUM_EXPECTATION_BYTES)
    need(wrapper['descriptor']==authority['report'] and len(raw)==wrapper['descriptor']['bytes']and
         hashlib.sha256(raw).hexdigest()==wrapper['descriptor']['sha256'],'full independently selected report bytes')
    need(report['deployment_id']==expectation['deployment_id']and
         report['installed_closure']==expectation['installed_closure']and
         report['source_admission']==expectation['source_admission']and
         report['configuration_sha256']==hashlib.sha256(canonical(entry,installed.MAXIMUM_EXPECTATION_BYTES)).hexdigest(),
         'exact earlier installed entry configuration and source domain')
    start=_wrapper(report['invocation'],INVOCATION);end=_wrapper(report['completion'],COMPLETION)
    need(start['domain']=='worker_entry'and start['qualifier_source']==authority['qualifier_source']and
         start['procedure_source']==authority['procedure_source']and start['environment']==authority['environment']==expectation['environment']and
         start['source_admission']==expectation['source_admission']and
         start['configuration_sha256']==report['configuration_sha256']and start['process']['source']==authority['qualifier_source'],
         'actual independent qualifier invocation/source/environment')
    need(start['process']['boot_id']==physical.boot and
         end['invocation']==report['invocation']['descriptor']and end['attempt']==start['attempt']and
         end['process']==start['process']and end['waited_pid']==start['process']['pid']and
         end['started_ns']==start['started_ns']<=end['completed_ns']<physical.clock_observations[0],
         'actual original qualifier completion strictly before this worker import')
    cost=end['cost'];need(cost['original_attempt']==start['attempt']and cost['process']==start['process']and
         start['started_ns']<=cost['observed_through_ns']<=end['completed_ns']and not cost['unknown_dimensions'],
         'complete original earlier qualifier cost observation')
    observations=report['observations'];need(type(observations)is list and len(observations)==5 and
         end['observations']==[r['descriptor']for r in observations], 'full original ordered qualification roster')
    results={}
    for case,observation in zip(CASES['worker_entry'],observations):
        b=_wrapper(observation,record({**OBS_FIELDS,'case':literal(case),'result':RESULTS[case]}))
        need(b['invocation']==report['invocation']['descriptor']and b['observer_source']==authority['procedure_source']and
             b['process']==start['process']and start['started_ns']<=b['observed_ns']<=end['completed_ns'],
             'same actual original qualification observation occurrence')
        results[case]=b['result']
    fixed=results['fixed_import'];need(fixed['entry_argv']==[entry['interpreter_absolute'],'-I',entry['entry_absolute']]and
         all(fixed[k]==entry[k]for k in ('interpreter','entry_script','fixed_agent_entry_source','source_closure'))and
         fixed['loaded_source_closure']==entry['source_closure']and fixed['environment']==expectation['environment'],
         'complete genuine qualified loaded source and fixed invocation')
    carrier=results['sealed_carrier'];channel=results['credential_channel']
    need(carrier['descriptor_extent']==carrier['body_extent']and carrier['write_errno']in(1,9)and carrier['truncate_errno']in(1,9)and
         channel['before_start_ticks']==channel['after_start_ticks']and channel['peer']['source']==expectation['launcher_source'],
         'original sealed-carrier and source-selected peer qualification')
    _probe_rows(results['descendant_isolation']['probes'],('child_fd198','child_fd199','parent_proc_reopen','foreign_endpoint'),
                authority['procedure_source'],start['attempt'],start['started_ns'],end['completed_ns'])
    control=results['control_enforcement']
    selected=expectation['control_selection']
    need(type(selected)is dict and set(selected)=={'installed_profile','base_development_profile','whole_envelope','worker_envelope'},
         'closed independently installed original control profile and envelopes')
    for key in selected:
        _layout('Pin',selected[key]);need(control[key]==selected[key],'exact independently installed control '+key)
    need(control['source_admission']==expectation['source_admission']and control['enforcer_source']==authority['procedure_source']and
         control['original_process']==start['process']and start['started_ns']<=control['observed_ns']<=end['completed_ns']and
         control['host_limits']==control['host_limit_readback']and control['arm_limits']==control['arm_limit_readback']and
         control['fd_peak_limit']<=control['fd_limit_readback'],'actual separate physical control qualification, no new allowance')
    from .worker_initialization_profile_v4 import validate_initialization_profile_v4
    control_observation=observations[CASES['worker_entry'].index('control_enforcement')]['descriptor']
    validate_initialization_profile_v4(expectation,control,control_observation,physical)
    d=physical.descriptor
    for left,right in [('source_issuer','launcher_source'),('canonical_publisher_source','canonical_publisher_source'),
                       ('clock_mapping_source','clock_mapping_source'),('entry_selection','entry_selection')]:
        need(d[left]==expectation[right], 'inherited original evidence matches independent installed '+right)
    need(d['context']['source_admission']==expectation['source_admission']and
         d['host']['source']==expectation['launcher_source'], 'actual source-selected original H lineage')
    return tuple(loaded)

def admit_fixed_worker_entry_v3():
    global _attempt
    from .backend_worker_bootstrap_physical_v3 import observe_fixed_worker_bootstrap_v3
    need(_attempt is None,'one fixed worker entry admission, including failures')
    physical=observe_fixed_worker_bootstrap_v3()
    owner=WorkerPreHelloAdmissionV3(_ADMISSION,physical);_attempt=owner
    physical.prehello_admission=owner;owner.entered=True
    try:
        physical.require_physical_complete_v3();raw=installed.EXPECTATION_RAW;owner.raw=raw
        need(type(raw)is bytes and 0<len(raw)<=installed.MAXIMUM_EXPECTATION_BYTES and
             type(installed.EXPECTED_SHA256)is str,'independently installed real expectation required')
        physical._work(len(raw)*128+4096);physical._retain_bound(len(raw)*16+4096)
        owner.digest=hashlib.sha256(raw).hexdigest()
        need(owner.digest==installed.EXPECTED_SHA256,'earlier installed expected identity, never FD self-assertion')
        owner.expected=parse(raw,len(raw),maximum_depth=64,maximum_members=len(raw),maximum_string_bytes=len(raw))
        need(canonical(owner.expected,len(raw))==raw,'complete canonical installed projection')
        owner.loaded=_validate_installed(owner.expected,physical)
        from .worker_initialization_profile_v4 import WorkerInitializationPhysicalProfileV4
        owner.initialization_profile=WorkerInitializationPhysicalProfileV4.from_prehello_v4(owner)
        physical._clock()
        physical.source_qualified=True;owner.complete=True
        return owner.require_original()
    except BaseException as error:
        owner.retain(error)
        try:physical.close_all_once()
        except BaseException as later:owner.retain(later)
        raise owner.raw_first
