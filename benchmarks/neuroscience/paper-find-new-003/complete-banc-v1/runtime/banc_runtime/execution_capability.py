"""Separate future wrapper execution capability; source jobs remain unqualified.

Trusted runner inputs are external to the candidate/job wire: capability bytes,
expected authority/evidence/closure pins, and fresh observed runtime facts.
This pure admission module neither grants authority nor observes a live runtime.
The R entry collects real runtime observations itself after preflight admission.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
from .codec import need,parse,pin
from .r_bridge import sha,text,source_members,validate_native_r_job,wire_encode

VERSIONS=('numpy','pandas','bidict','petsc4py','slepc4py')
WRAPPER='R_to_Python_literal_wrapper'


def canonical_path(value):
    text(value)
    value.encode("ascii")
    path=PurePosixPath(value)
    need(value!="/" and not value.startswith("//") and path.is_absolute() and str(path)==value and '..' not in path.parts,
         'canonical absolute qualified-runtime path')
    return value


def runtime_closure(raw):
    need(type(raw) is str,'exact runtime-closure JSON string')
    body=raw.encode('ascii');c=parse(body)
    fields={'schema','conda_environment','python_executable','python_prefix','python_version',
            'package_init_path','calculator_source_path','distribution_versions','files'}
    need(type(c) is dict and set(c)==fields and c['schema']=='banc_python_runtime_closure_v1', 'exact runtime closure')
    need(c['conda_environment']=='r-reticulate' and type(c['python_version']) is str and c['python_version'], 'original wrapper environment/version')
    for k in ('python_executable','python_prefix','package_init_path','calculator_source_path'):canonical_path(c[k])
    versions=c['distribution_versions']
    need(type(versions) is dict and set(versions)==set(VERSIONS) and
         all(type(v) is str and v for v in versions.values()), 'complete independently qualified Python distribution versions')
    need(type(c['files']) is list and c['files'], 'independently qualified complete runtime-file closure')
    paths=[]
    for row in c['files']:
        need(type(row) is dict and set(row)=={'path','bytes','sha256'},'exact qualified runtime file')
        canonical_path(row['path']);sha(row['sha256'])
        need(type(row['bytes']) is int and 0<=row['bytes']<=2**53-1,'exact runtime file size domain')
        paths.append(row['path'])
    need(paths==sorted(set(paths)), 'complete canonical unique runtime-file order')
    bypath={r['path']:r for r in c['files']}
    need(all(c[k] in bypath for k in ('python_executable','package_init_path','calculator_source_path')),
         'interpreter and both actual imported Python source paths must be in the qualified closure')
    literal=source_members()['Python'];actual=bypath[c['calculator_source_path']]
    need((actual['bytes'],actual['sha256'])==(literal['bytes'],literal['sha256']), 'exact captured calculator source in runtime closure')
    return c,pin(body)['sha256']


def admit_execution_description(raw, job, job_payload_sha256, *, program_identity,
        expected_capability_sha256, expected_authority_id, expected_qualification_evidence_sha256,
        expected_runtime_closure_sha256, operation):
    """Preflight all external authority pins before any runtime observation."""
    need(type(raw) is bytes, 'separate execution capability required')
    for value in (program_identity,job_payload_sha256,expected_capability_sha256,
                  expected_qualification_evidence_sha256,expected_runtime_closure_sha256):sha(value)
    need(pin(raw)['sha256']==expected_capability_sha256,'independently selected capability pin')
    validate_native_r_job(job,program_identity=program_identity)
    need(pin(wire_encode(job))['sha256']==job_payload_sha256,'actual canonical source job payload binding')
    need(job['operator_branch']==WRAPPER,'Python-import capability applies only to literal wrapper')
    value=parse(raw)
    fields={'schema','authority_id','program_identity','qualification_scope','qualification_evidence_sha256',
            'runtime_closure_json','runtime_closure_sha256','allowed_job_payload_sha256s','allowed_entrypoints',
            'source_members','python_source_revision','scientific_qualification'}
    need(type(value) is dict and set(value)==fields and value['schema']=='banc_wrapper_execution_capability_v1','exact separate capability')
    need(type(expected_authority_id) is str and expected_authority_id and
         value['authority_id']==expected_authority_id and value['program_identity']==program_identity,
         'external authority and independently selected programme')
    need(value['qualification_scope']=='qualified_exact_python_import_closure_only' and
         value['qualification_evidence_sha256']==expected_qualification_evidence_sha256,
         'separately admitted qualification evidence; no source-job self-qualification')
    need(value['source_members']==source_members() and
         value['python_source_revision']=='6b70294094ebcd97166ab646c5322eed957f8936','exact native/normalizer source and Python revision')
    hashes=value['allowed_job_payload_sha256s'];entries=value['allowed_entrypoints']
    need(type(hashes) is list and hashes and len(hashes)==len(set(hashes)), 'explicit unique allowed wire jobs')
    for h in hashes:sha(h)
    need(job_payload_sha256 in hashes,'capability must name this exact job wire payload')
    need(type(entries) is list and entries and len(entries)==len(set(entries)) and
         set(entries)<= {'influence','sensory'} and operation in entries,'explicit separately selected entrypoint')
    closure,closure_sha=runtime_closure(value['runtime_closure_json'])
    need(closure_sha==value['runtime_closure_sha256']==expected_runtime_closure_sha256,
         'independently qualified complete runtime closure')
    need(value['scientific_qualification'] is False, 'capability cannot close scientific gates')
    return {'capability':value,'capability_sha256':expected_capability_sha256,
            'closure':closure,'job_payload_sha256':job_payload_sha256,'operation':operation}


@dataclass(frozen=True)
class WrapperExecution:
    program_identity: str
    job_payload_sha256: str
    capability_sha256: str
    authority_id: str
    qualification_evidence_sha256: str
    runtime_closure_sha256: str
    operation: str
    scientific_qualification: bool = False


def confirm_execution(description, observed_runtime):
    """Join fresh real observations to the independently qualified closure.

    Tests may supply invented observations to exercise admission; that is not
    an actual qualified runtime. The concrete R entry calls its owned observer.
    """
    need(type(description) is dict and set(description)=={'capability','capability_sha256','closure','job_payload_sha256','operation'},
         'admitted capability description')
    need(observed_runtime==description['closure'],'actual runtime files/source/versions differ from qualification')
    value=description['capability']
    return WrapperExecution(value['program_identity'],description['job_payload_sha256'],description['capability_sha256'],
        value['authority_id'],value['qualification_evidence_sha256'],value['runtime_closure_sha256'],description['operation'])


def require_wrapper_execution(job, job_payload_sha256, execution):
    need(type(execution) is WrapperExecution and execution.program_identity==job['selection']['program_identity'] and
         execution.job_payload_sha256==job_payload_sha256 and execution.scientific_qualification is False,
         'separately admitted wrapper execution capability bound to this job')
    need(job['operator_branch']==WRAPPER and job['qualified_exact_python_import_closure'] is False and
         job['scientific_qualification'] is False,'source description remains unqualified and unchanged')
    return execution
