"""Fixed public hierarchy packet, one opaque JSON answer and private grader bindings."""
import importlib.util
import json
from pathlib import Path
import sys
from files import HERE, ROOT, ID, need, path as repo, read as ordinary, json_read as read, pin, opaque, descriptor
SHARED=ROOT/'authoring/shared-program-runner-v2'
SUMMARY=ROOT/'authoring/shared-summary-runner-v1'
NAMES=tuple(sorted(('TASK.md','PUBLIC_SCORING.md','OUTPUT_SCHEMA.json','SESSION_MANIFEST.json',
                   'ACQUISITION_CONFIG.json','main.txt','main.pdf','Chiossi_etal_2025_PNAS_data.zip')))
_API=None

def save(source,value,budget,cap=250000):
    body=(json.dumps(value,indent=2,allow_nan=False)+'\n').encode()
    need(len(body)<=cap,'Bounded complete receipt');budget.write(source,body,receipt=True,mode=0o444)
    return pin(body)['sha256']

def module(name,source):
    from files import captured_module
    bindings=read(HERE/'SOURCE_BINDINGS.json')
    return captured_module(bindings[source.name],name,register=True)


def api():
    global _API
    if _API is None:
        import common
        core=common.qualified
        contract=module('contract_profile',HERE/'contract_profile.py');engine=module('engine_profile',HERE/'engine_profile.py')
        module('profile',HERE/'profile.py');unit=module('_hierarchy_central_unit',HERE/'unit.py')
        summary=module('runtime',HERE/'grade_profile.py')
        summary_unit=module('_hierarchy_central_grade_unit',HERE/'grade_unit.py')
        identity=module('_hierarchy_central_identity',HERE/'identity.py')
        from absence import absence
        from profile import runtime
        _API={'BaseEngine':core.BaseEngine,'HostBudget':core.HostBudget,'owner':common.owner,
              'ProfileEngine':engine.ProfileEngine,'contract_profile':contract,'runtime':runtime,
              'run_unit':unit.run_unit,'summary_profile':summary,'SummaryEngine':summary_unit.EvidenceSummaryEngine,
              'run_grade':summary_unit.run_one,'absence':absence,'identity':identity}
    return _API


def assets():
    value=read(HERE/'ASSETS.json')
    need(value['candidate_id']==ID and set(value['public_inputs'])==set(NAMES),'Exact task and public8-file inventory')
    need(set(value['grader_sources'])=={'grader.py','scorer_core.py','generated_checks.py','reference_core.py',
         'OUTPUT_SCHEMA.json','REFERENCES.json'} and set(value['references'])=={'linkages.npz','report.json'},
         'Exact grader-only source and private inventories')
    return value

def public_file_cap(asset):
    need(asset['mount_destination'] in tuple('/input/'+n for n in NAMES),'Only8 reviewed public input files')
    return 770000000 if asset['mount_destination'].endswith('.zip') else 2000000

def expected_unit():
    a=assets()
    return {'unit_id':'submission','candidate_seconds':600,'output_filename':'submission.json','max_output_bytes':4000000,
            'public_inputs':[dict(a['public_inputs'][n],mount_destination='/input/'+n) for n in NAMES]}

def packet():
    unit=expected_unit()
    for item in unit['public_inputs']:
        need(opaque(repo(item['path']),public_file_cap(item))=={k:item[k] for k in ('bytes','sha256')},'Exact public bytes')
    return unit

def runtime_manifest(run):
    committed=read(run/'runtime_manifest_commit.json');raw=ordinary(run/'runtime_manifest.json',32768)
    need(committed['before_any_Docker_resource_creation'] is True and pin(raw)==committed['manifest'],'Pre-resource commitment')
    value=json.loads(raw)
    need(value['candidate_id']==ID and repo(value['program_path'])==run/'program.py' and value['unit']==expected_unit(),
         'One captured program, fixed public-only task')
    return value

def admit_unit(unit,program_sha,run=None):
    need(run is not None and runtime_manifest(run)['unit']==unit and runtime_manifest(run)['program_sha256']==program_sha,
         'Exact captured program/public input interface')
    for item in unit['public_inputs']:public_file_cap(item)

def grade_config(run):
    a=assets();invocation=run/'invocation.json'
    return {'candidate_bytes':4000000,'worker_output_bytes':16384,'full_score_bytes':1000000,
        'grade_output_dir':str((run/'grade').absolute()),'fixed_mounts':{
            **{dest:a['grader_sources'][name] for dest,name in {
                '/source/grader.py':'grader.py','/source/scorer_core.py':'scorer_core.py',
                '/source/reference_core.py':'reference_core.py',
                '/source/generated_checks.py':'generated_checks.py','/source/OUTPUT_SCHEMA.json':'OUTPUT_SCHEMA.json',
                '/source/REFERENCES.json':'REFERENCES.json'}.items()},
            '/source/invocation.json':{'path':str(invocation.relative_to(ROOT)),**pin(ordinary(invocation,16384))},
            **{'/reference/'+name:value for name,value in a['references'].items()}}}


def verify_grade_config(run):
    a=assets();outcome=read(run/'unit/outcome_commit.json')
    need(outcome['unit_status']=='unit_committed' and outcome['all_unit_resources_absent'] is True,
         'Producer ID/name absence and output commitment before private grade')
    need(pin(ordinary(run/'unit/submission.json',4000000))==outcome['output'],'Committed answer unchanged')
    need(read(run/'invocation.json')=={'schema_version':1,'candidate_id':ID,'submission':outcome['output'],
        'output_schema':{k:a['grader_sources']['OUTPUT_SCHEMA.json'][k] for k in ('bytes','sha256')},
        'references':{k:a['grader_sources']['REFERENCES.json'][k] for k in ('bytes','sha256')}},
        'Exact unchanged grader invocation')


def worker_bindings(run):
    verify_grade_config(run)
    result={dest:str(repo(item['path'])) for dest,item in grade_config(run)['fixed_mounts'].items()}
    result['/submission/submission.json']=str(run/'unit/submission.json')
    result['/grade']=str(run/'grade')
    return result
