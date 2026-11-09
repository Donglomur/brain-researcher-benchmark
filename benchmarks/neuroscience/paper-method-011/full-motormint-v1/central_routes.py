"""Inactive registry proposal and real default/named source-gate composition."""
import types
from pathlib import Path
from central_common import need,pin,encode

INTERFACE='benchmarks/neuroscience/paper-method-011/full-motormint-v1'
REGISTRY='benchmarks/neuroscience/paper-method-011/manifest.json'
CONDITION='full_motormint_v1'
SHARED='shared/'


def registration(sources):
    wrapper=INTERFACE+'/run.py'
    meta={'status':'source_only_unqualified','profile':CONDITION,
        'entrypoint':{'argv':['{python}',wrapper,'--source-bytes',str(sources.manifest_pin['bytes']),
             '--source-sha256',sources.manifest_pin['sha256'],'run','--program','{program}',
             '--output','{output}','--review','{review}','--other-reserve-bytes','{other_reserve_bytes}',
             '--deployment',INTERFACE+'/DEPLOYMENT.json'],
             'sha256':sources.manifest['files']['run.py']['sha256'],'working_directory':'.',
             'program_operand_semantics':'complete balanced full-paper invocation metadata; submitted code stays in isolated original workers'},
        'preferred_source_interface':{'path':INTERFACE,'source':{'path':INTERFACE+'/SOURCE_MANIFEST.json',**sources.manifest_pin}},
        'verification':{'status':'not_run','reason':'Fresh complete native/numerical/input/OS/provider/runtime qualification required'},
        'scope':sources.manifest['scope'],'runtime':{'deployment_status':'unconfigured','execution_enabled':False},
        'canonical_methods':{'inspect':'exact source capture only','prepare':'acyclic actual invocation metadata construction',
          'run':'complete17-module original reference plus balanced paper+data / paper+data+author-code campaign',
          'reference':'retain actual independent-reference execution products from the full paired block',
          'candidate':'retain all full-paper candidate A/B outcomes, including failures and unavailable outputs',
          'collect':'capture original outer/block/campaign/report metadata; protected targets stay in original assessment',
          'grade':'retain original protected per-estimand assessment and uncertainty, with no cross-estimand scalar',
          'report':'render complete original reports with missing support and17gates preserved'},
        'independently_executable_reference_or_candidate_stage':False,
        'source_history_is_runtime_dependency':False}
    return {'schema_version':1,'id':'PAPER-paper-method-011','track':'paper','status':'source_only_unqualified',
        'title':'MotorMINT full nine-dataset paper reproduction and paired-code-access improvement',
        'program_execution':meta,'program_conditions':{CONDITION:'default'},
        'admission':{'runnable':False,'research_qualified':False,'submission_ready':False,
                     'source_implementation_complete':False,'full_candidate_contract_complete':False},
        'holds':['all original9datasets, trial/channel/clock support and missing original extension methods','competent independent reference/numerical agreement',
                 'actual Linux cgroup/Docker/CPython/isolation and whole resource qualification',
                 'full original campaign execution and protected scientific evaluation'],
        'installation':'proposal only; preserve existing unrelated routes and counters against a freshly selected predecessor'}


class SourceView:
    """Exact captured source plus constructed metadata. No dependency fallback.

    This is a source-preflight virtual namespace, not an installed filesystem or
    claim that external exposure histories/dependencies are available or true.
    """
    def __init__(self,root,sources,constructed):
        self.root=Path(root);self.sources=sources;self.constructed=constructed;self.records=[]
    def resolve(self,root,key):
        need(Path(root)==self.root,'one source-preflight root');return self.root/key
    def capture(self,key,cap,expected=None):
        if key in self.constructed:body=self.constructed[key]
        elif SHARED+key in self.sources.files:body=self.sources.files[SHARED+key]
        elif key.startswith(INTERFACE+'/'):
            local=key[len(INTERFACE)+1:]
            body=self.sources.manifest_body if local=='SOURCE_MANIFEST.json' else self.sources.files[local]
        else:raise ValueError('Unselected or deferred source-preflight dependency: '+key)
        need(len(body)<=cap and (expected is None or pin(body)=={k:expected[k] for k in ('bytes','sha256')}),
             'exact bounded constructed-source capture')
        self.sources.meter.charge(read_bytes=len(body)+1,metadata_bytes=2*len(body)+4096,objects=1)
        self.records.append({'path':key,**pin(body)});return body


def source_preflight(sources):
    """Execute actual unchanged shared gate methods on their real producer ABI.
    No exposure admission, source qualification, WORK read/mutation or launch.
    """
    root=Path('/motormint-source-preflight');doc=registration(sources)
    prefpath='authoring/proposed-motormint-source-preference.json'
    preference={'schema':'root_reviewed_program_source_preference_v1',
                'selected_source_interfaces':{'PAPER-paper-method-011':doc['program_execution']['preferred_source_interface']}}
    pref=encode(preference,262144)
    work={'latest_construction_state':{'latest_program_source_selection':{'path':prefpath,**pin(pref)}}}
    wb=encode(work,1835008)
    constructed={prefpath:pref,'authoring/delivery-20261105/WORK_ASSIGNMENTS.json':wb,
                 REGISTRY:encode(doc,131072)}
    view=SourceView(root,sources,constructed)
    key='tools/neurobench_campaign_gate_bounded_v3.py'
    raw=sources.files[SHARED+key]
    sources.meter.charge(metadata_bytes=65*len(raw))
    gate=types.ModuleType('_motormint_actual_shared_gate');gate.__file__=str(root/key);gate.__dict__['_SOURCE_VIEW']=view
    exec(compile(raw,gate.__file__,'exec',dont_inherit=True),gate.__dict__)
    default=gate.preferred_route(root,'PAPER-paper-method-011','run',None,pin(wb)['sha256'],(root/REGISTRY,doc),view=view)
    named=gate.preferred_route(root,'PAPER-paper-method-011','run',CONDITION,pin(wb)['sha256'],(root/REGISTRY,doc),view=view)
    capacity=gate.campaign_capacity_plan(root,{'path':'authoring/delivery-20261105/WORK_ASSIGNMENTS.json',**pin(wb)},view=view)
    need(default['status']==named['status']=='preferred_source_bound','actual default and named preference consumers')
    need(capacity['limits']['construction_work_max_bytes']==1835008
         and capacity['limits']['work_body_bytes']==2097152
         and capacity['dependency_descriptors']==sources.manifest['deferred_dependencies'],
         'unchanged shared capacity and all ten deferred dependencies')
    return {'schema':'motormint_default_named_source_preflight_v1','default':default,'named':named,
            'capacity':capacity,'constructed_registry':pin(constructed[REGISTRY]),
            'constructed_WORK':pin(wb),'source_view_captures':view.records,
            'existing_shared_WORK_read_or_modified':False,'deferred_bodies_read':False,
            'qualification_or_runtime_admission':False,'actual_installed_registry_impact':'requires future observed predecessor'}
