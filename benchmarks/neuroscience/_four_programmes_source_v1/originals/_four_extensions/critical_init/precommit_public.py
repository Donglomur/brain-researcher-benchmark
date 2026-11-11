"""Fixed complete template→public interface→ABI→paired-manifest producers.

ScientificTemplate is not an executable census. Only the later final census
can enter the original full census validator after actual programme seals.
All source reads/publication are owned by EarlyOwner, outside these pure
metadata projections; no member/data/header body is opened here.
"""
from .scope import Scope
from .views import validate_pair
from .custody import encode, parse, pin
from four_programmes.common import need, closed, descriptor, bounded_size, same
from four_programmes.precommit_records import validate_type, CONDITIONS
from four_programmes.public_abi_grammar import validate_jobs

_TEMPLATE = object()
_INTERFACE = object()
_ABI = object()

def _preadmit(expected,meter):
    descriptor(expected)
    # The selected complete input extent precedes traversal or allocation.
    # These are logical reservations; physical Python RSS stays unqualified.
    meter.charge('work_units',64*expected['bytes']+4096)
    meter.charge('retained_bytes',16*expected['bytes']+4096)

def _clone(value, meter, expected):
    _preadmit(expected,meter)
    bounded_size(value)
    raw=encode(value)
    need(pin(raw)=={k:expected[k]for k in ('bytes','sha256')},'exact complete selected original metadata bytes')
    return parse(raw)

class ScientificTemplateAdmission:
    __slots__=('body','descriptor','scope','_token')
    def __init__(self,token,body,expected,scope):
        need(token is _TEMPLATE,'fixed original template source admission')
        self.body,self.descriptor,self.scope,self._token=body,expected,scope,token

def admit_template(scope, template, expected, *, meter):
    need(type(scope) is Scope,'actual original captured Scope, never supplied scope flags')
    descriptor(expected)
    body=_clone(template,meter,expected)
    closed(body,('schema','canonical_id','scope_digest','census_body'))
    need(body['schema']=='ci_scientifictemplate_v1' and body['canonical_id']=='PAPER-FIND-050',
         'fixed earlier scientific template wrapper')
    census=body['census_body']
    need(type(census)is dict and census['canonical_id']==body['canonical_id'] and
         census['scope_digest']==body['scope_digest']==scope.digest,'same complete original scope')
    # This is the original metadata/support method, not census.validate and
    # never a numerical recreation of its grids or scientific methods.
    scope.whole_plan(census)
    need(set(census['gate_ids'])=={g['id']for g in scope.gates},'all original gates retained')
    jobs=census['jobs'];need(type(jobs)is list and 0<len(jobs)<=8192,'full earlier finite job programme')
    candidates=[]
    for job in jobs:
        need(job['operation']in ('prepare','independent_reference','native_reference','candidate'),
             'original operation domain')
        need(job['kind']in ('numeric','native','artifact'),'original kind domain')
        if job['operation']=='candidate':
            need('command' not in job and 'command_source_pins' not in job,
                 'only future candidate dispatch fields absent from template')
            candidates.append(job)
    need(candidates,'whole original candidate scope required')
    return ScientificTemplateAdmission(_TEMPLATE,body,dict(expected),scope)

class PublicInterfaceProduct:
    __slots__=('body','template','_token')
    def __init__(self,token,body,template):
        need(token is _INTERFACE,'fixed interface source producer')
        self.body,self.template,self._token=body,template,token

class PublicInterfaceCreator:
    @staticmethod
    def create_v2(template, *, meter):
        need(type(template)is ScientificTemplateAdmission,'actual earlier template admission')
        _preadmit(template.descriptor,meter)
        census=template.body['census_body']
        rows=[{'job_id':j['id'],'kind':j['kind'],'task_expected_outputs':j['expected_outputs']}
              for j in census['jobs']if j['operation']=='candidate']
        body=parse(encode({'schema':'ci_publictaskinterface_v1','scope_digest':template.body['scope_digest'],'jobs':rows}))
        validate_type('PublicTaskInterface',body)
        need([r['job_id']for r in body['jobs']]==[j['id']for j in census['jobs']if j['operation']=='candidate'],
             'complete original candidate order without private template or final census')
        return PublicInterfaceProduct(_INTERFACE,body,template)

class PublicABIProduct:
    __slots__=('body','interface','interface_pin','_token')
    def __init__(self,token,body,interface,interface_pin):
        need(token is _ABI,'fixed ABI source producer')
        self.body,self.interface,self.interface_pin,self._token=body,interface,interface_pin,token

class PublicABICreator:
    @staticmethod
    def create_v2(interface, interface_pin, grammar_jobs, grammar_pin, *, meter):
        need(type(interface)is PublicInterfaceProduct,'actual earlier interface producer')
        descriptor(interface_pin)
        _preadmit(interface_pin,meter)
        need(pin(encode(interface.body))=={k:interface_pin[k]for k in ('bytes','sha256')},
             'actual completed interface descriptor')
        rows=_clone(grammar_jobs,meter,grammar_pin);validate_jobs(rows)
        public=interface.body['jobs']
        need([r['job_id']for r in rows]==[r['job_id']for r in public], 'every original grammar job in exact public order')
        for row,original in zip(rows,public):
            need(same(row['kind'],original['kind']) and same(row['task_expected_outputs'],original['task_expected_outputs']),
                 'exact original declared output meaning, never inferred from observed result')
        body={'schema':'critical_init_public_candidate_report_abi_v2','scope_digest':interface.body['scope_digest'],
              'task_interface':dict(interface_pin),'conditions':list(CONDITIONS),'report_relative_path':'candidate_report.json',
              'required_fields':['job_id','condition','scope_digest','bundles','identities'],'jobs':rows}
        validate_type('PublicABI',body)
        return PublicABIProduct(_ABI,body,interface,dict(interface_pin))

class PairedViewManifestCreator:
    @staticmethod
    def create_v2(abi, abi_pin, selected_view_rules, view_rules_pin, *, meter):
        need(type(abi)is PublicABIProduct,'actual complete earlier ABI producer')
        descriptor(abi_pin)
        _preadmit(abi_pin,meter)
        need(pin(encode(abi.body))=={k:abi_pin[k]for k in ('bytes','sha256')}, 'actual completed ABI descriptor')
        manifest=_clone(selected_view_rules,meter,view_rules_pin)
        # Existing exact rule body includes every earlier selected member and
        # classification; no descriptors are followed or discovered here.
        validate_pair(manifest)
        need(not any(m['source']==abi_pin for m in manifest['common']+manifest['author_code']),
             'earlier ABI is added exactly once to the common view')
        destination='candidate_report_abi.json'
        need(all(m['destination']!=destination for m in manifest['common']+manifest['author_code']),
             'no overwrite or collision with an original selected member')
        manifest['common'].append({'role':'task','destination':destination,'source':dict(abi_pin)})
        validate_pair(manifest)
        need(sum(m['source']==abi_pin for m in manifest['common'])==1 and
             all(m['source']!=abi_pin for m in manifest['author_code']),'same ABI in both arms before commit')
        return manifest

def require_final_scientific_projection(template, final_census, final_census_pin, *, meter):
    need(type(template)is ScientificTemplateAdmission,'actual earlier whole scientific template')
    projected=_clone(final_census,meter,final_census_pin)
    _preadmit(template.descriptor,meter)
    for job in projected['jobs']:
        if job['operation']=='candidate':
            need('command'in job and 'command_source_pins'in job,'complete actual final candidate dispatch')
            del job['command'];del job['command_source_pins']
    need(encode(projected)==encode(template.body['census_body']),
         'all original scientific fields and unknown original fields exactly preserved by P(final)')
    # This only proves the P(C) relation. The source caller must still invoke
    # original census.validate and require_executable on the final census.
    return True
