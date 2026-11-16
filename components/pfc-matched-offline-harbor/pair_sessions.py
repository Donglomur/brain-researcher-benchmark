"""PFC-only fresh trial plans and complete two-arm artifact freeze.

No subprocess, Harbor import, model, Docker, scoring or feedback delivery occurs.
Native execution/closure must be owned by the already accepted external caller.
"""
from pathlib import Path
import hashlib
import json
import os
import re
import stat
import sys
import tomllib
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paired_materialize as materializer

need = materializer.need
TASK_NAME = 'terminal-bench-science/pfc-conditional-reconstruction'
SUBMISSION = 'artifacts/app/output/submission.jsonl'
CONVENTIONAL = 'artifacts/logs/artifacts'
TRIAL_MAX = 256 * 1024**2
PAIR_READ_MAX = 1024 * 1024**2


def emit(path, value):
    body = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
    need(len(body) <= 2*1024**2 and not os.path.lexists(path), 'bounded fresh metadata')
    with path.open('xb') as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    path.chmod(0o400)
    return {'path':str(path), 'bytes':len(body), 'sha256':hashlib.sha256(body).hexdigest()}


def bind_images(body, agent, verifier):
    """Same two-section binding as the admitted original, for the offline TOML."""
    before = tomllib.loads(body.decode())
    need(before['environment']['network_mode'] == 'no-network'
         and before['verifier']['environment']['network_mode'] == 'no-network'
         and before['verifier'].get('collect', []) == [], 'offline and no pre-freeze collect hook')
    text = body.decode()
    for heading, image, table in (('[environment]\n',agent,before['environment']),
                                  ('[verifier.environment]\n',verifier,before['verifier']['environment'])):
        need(re.fullmatch(r'sha256:[0-9a-f]{64}',image) is not None and image != materializer.BASE
             and 'docker_image' not in table and text.count(heading)==1, 'complete image-only override')
        text = text.replace(heading, heading+'docker_image = "'+image+'"\n', 1)
    after = tomllib.loads(text)
    need(after['environment'].pop('docker_image') == agent
         and after['verifier']['environment'].pop('docker_image') == verifier
         and after == before, 'only complete image bindings changed')
    return text.encode()


def trial_config(task, sessions, name, common_agent, *, source=None):
    return {'task':{'path':str(task),'git_url':None,'git_commit_id':None,'name':None,
                   'ref':None,'overwrite':False,'download_dir':None,'source':None},
        'trial_name':name, 'trials_dir':str(sessions),
        'install_only':False, 'timeout_multiplier':1.0,
        'agent_timeout_multiplier':None,'verifier_timeout_multiplier':None,
        'agent_setup_timeout_multiplier':None,'environment_build_timeout_multiplier':None,
        'agent':{'name':common_agent['name'], 'model_name':common_agent['model_name'],
                 'kwargs':{}, 'env':{}, 'mcp_servers':[], 'skills':[],
                 'import_path':None,'override_timeout_sec':None,'override_setup_timeout_sec':None,
                 'max_timeout_sec':None,'resume_trajectory':False,'load_trajectory':None,
                 'extra_allowed_hosts':[],'n_concurrent':None,'concurrency_group':None},
        'environment':{'type':'docker','import_path':None,'force_build':False,'delete':True,
            'cpu_enforcement_policy':'limit','memory_enforcement_policy':'limit',
            'extra_docker_compose':[],'kwargs':{},'env':{},'mounts':None,'extra_allowed_hosts':[],
            'override_cpus':None,'override_memory_mb':None,'override_storage_mb':None,
            'override_gpus':None,'override_tpu':None},
        'verifier':{'disable':source is None,'override_timeout_sec':900.0,'env':{},'kwargs':{},
                    'import_path':None,'max_timeout_sec':None},
        'artifacts':[],'extra_instruction_paths':[], 'source_trial':source}


def prepare(request):
    h = materializer.load_helpers(); reader = h.Reads(64*1024**2)
    need(type(request) is dict and set(request)=={'schema','execution_selected','pair_manifest',
        'output_root','nonce','images','agent'}, 'exact paired session preparation request')
    need(request['schema']=='PFC_MATCHED_PAIR_SESSIONS_V1' and request['execution_selected'] is True,
         'separate preparation selection')
    need(re.fullmatch('[0-9a-f]{64}',request['nonce']) is not None, 'full owned pair nonce')
    out = h.plain_path(request['output_root'],exists=False)
    need(not os.path.lexists(out),'fresh whole paired session root')
    pin = request['pair_manifest']
    need(set(pin)=={'path','bytes','sha256'}, 'exact completed pair manifest pin')
    mp = h.plain_path(pin['path']); source = mp.parent
    need(source != out and source not in out.parents and out not in source.parents, 'separate source and session roots')
    manifest = h.decode(reader.read(mp, 262144, (pin['bytes'],pin['sha256'])))
    need(manifest['schema']=='PFC_MATCHED_PAIR_CONTEXTS_V1' and manifest['cases']==69
         and manifest['base_image']==materializer.BASE and manifest['official_code_only_B'] is True,
         'matched complete materialization')
    need(manifest['source_manifest_sha256']==materializer.MANIFEST_SHA
         and manifest['packet_identity']==list(h.ASSETS['participant-packet.json']),
         'unchanged accepted source and public packet identities')
    images = request['images']
    need(type(images) is dict and set(images)=={'A','B','verifier'} and len(set(images.values()))==3,
         'three distinct complete task images')
    agent = request['agent']
    need(type(agent) is dict and set(agent)=={'name','model_name'}
         and type(agent['name']) is str and re.fullmatch('[a-zA-Z0-9_-]{1,64}',agent['name'])
         and (agent['model_name'] is None or type(agent['model_name']) is str and 0<len(agent['model_name'])<=256),
         'one identical built-in agent configuration; no custom imports, credentials or resume kwargs')
    need(len(manifest['files'])==54 and len({r['path'] for r in manifest['files']})==54,
         'complete paired source file roster')
    need(h.file_roster(source)=={r['path'] for r in manifest['files']}|{'PAIR_MANIFEST.json'},
         'complete pair namespace before session preparation')
    tasks = {arm:{} for arm in ('A','B')}
    for row in manifest['files']:
        rel = Path(row['path'])
        need(not rel.is_absolute() and '..' not in rel.parts, 'bounded relative materialized member')
        arm, inner = rel.parts[0], '/'.join(rel.parts[1:])
        need(arm in tasks and inner.startswith(materializer.TASK+'/'), 'fixed paired task member')
        name = inner[len(materializer.TASK)+1:]
        tasks[arm][name] = reader.read(source/rel,8388608,(row['bytes'],row['sha256']))
    materializer.validate_pair(tasks['A'],tasks['B'])
    overlays = {}; plans = {}
    for arm in ('A','B'):
        # Reduced source overlay is strictly prebuilt-only: complete assets are
        # in separately admitted images, and never rebuilt from this directory.
        bodies = {n:b for n,b in tasks[arm].items() if '/assets/' not in n}
        need(len(bodies)==15, 'complete source-only execution overlay')
        bodies['task.toml'] = bind_images(bodies['task.toml'], images[arm], images['verifier'])
        policy = b'{"services":{"main":{"pull_policy":"never"},"harbor-docker-egress-control-sidecar":{"pull_policy":"never","cpus":0.25,"mem_limit":"256M","memswap_limit":"256M","pids_limit":64}}}\n'
        bodies['environment/docker-compose.yaml'] = policy
        bodies['tests/docker-compose.yaml'] = policy
        task = out/'tasks'/arm/'pfc-conditional-reconstruction'
        sessions = out/'sessions'/arm
        name = 'pfc-pair-'+request['nonce'][:20]+'-'+arm.lower()
        config = trial_config(task,sessions,name,agent)
        plans[arm] = {'task':str(task),'sessions':str(sessions),'trial_name':name,
            'trial_dir':str(sessions/name),'config':config,'config_path':str(out/'configs'/(arm+'.json')),
            'host_environment_overrides':{'HOME':str(out/'homes'/arm),'TMPDIR':str(out/'tmp'/arm),
                'PYTHON_DOTENV_DISABLED':'1'},'candidate_feedback_permitted':False}
        overlays[arm] = bodies
    need(plans['A']['config']['agent']==plans['B']['config']['agent'],'same model and tool settings')
    out.mkdir(mode=0o700)
    for name in ('configs','sessions/A','sessions/B','homes/A','homes/B','tmp/A','tmp/B'):
        (out/name).mkdir(mode=0o700,parents=True,exist_ok=False)
    rows = []
    for arm in ('A','B'):
        for name,body in sorted(overlays[arm].items()):
            p = Path(plans[arm]['task'])/name;p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
            with p.open('xb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
            p.chmod(0o400); rows.append(materializer.descriptor(str(p.relative_to(out)),body))
        emit(Path(plans[arm]['config_path']),plans[arm]['config'])
    plan = {'schema':'PFC_MATCHED_PAIR_SESSION_PLAN_V1','root':str(out),'nonce':request['nonce'],
        'pair_manifest':pin,'arms':plans,'overlay_files':rows,'images':images,'agent':agent,
        'grading_deferred_until_both_frozen':True,'native_image_and_isolation_admission_required':True,
        'existing_owned_caller_required':True,'native_or_model_calls':0,'new_benchmark_ids':0}
    return emit(out/'PAIR_PLAN.json',plan)


def subset(actual, expected):
    need(type(actual) is dict,'resolved config object')
    for key,value in expected.items():
        if value in ({},None) and key not in actual:
            continue  # Harbor omits empty/default metadata on serialization.
        need(key in actual,'missing selected configuration field '+key)
        if isinstance(value,dict):
            subset(actual[key],value)
            if not value:need(actual[key]=={},'empty selected mapping changed')
        else:need(type(actual[key]) is type(value) and actual[key]==value,'selected field changed '+key)


def trial_inventory(root):
    h=materializer.load_helpers();h.plain_path(root)
    files={};directories=set();total=0
    for name in ('config.json','result.json'):
        p=root/name;h.plain_path(p);s=p.lstat()
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_size<=2*1024**2,'complete bounded trial metadata')
        files[name]=h.stamp(s);total+=s.st_size
    for name in ('agent','artifacts'):
        base=h.plain_path(root/name);need(base.is_dir(),'complete consumed trial directory')
        directories.add(name)
        for directory,dirs,names in os.walk(base,followlinks=False):
            for entry in dirs+names:
                p=Path(directory)/entry;s=p.lstat();rel=str(p.relative_to(root))
                need(not stat.S_ISLNK(s.st_mode),'no alias in consumed trial namespace')
                if stat.S_ISDIR(s.st_mode):directories.add(rel)
                else:
                    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1,'ordinary consumed trial file')
                    need(s.st_size<=128*1024**2,'bounded individual trial file')
                    files[rel]=h.stamp(s);total+=s.st_size
                need(len(files)+len(directories)<=512 and total<=TRIAL_MAX,'bounded complete consumed trial namespace')
    need(not os.path.lexists(root/'steps'),'single-step trial only')
    return files,directories,total


def admit_completed_trial(root, selected, reader):
    h=materializer.load_helpers()
    config=h.decode(reader.read(root/'config.json',262144))
    result=h.decode(reader.read(root/'result.json',2*1024**2))
    subset(config,selected['config']);subset(result['config'],selected['config'])
    for actual in (config,result['config']):
        for role in ('agent','environment','verifier'):
            need(actual[role].get('import_path') is None and actual[role].get('env',{})=={}
                 and actual[role].get('kwargs',{})=={}, 'no additional custom code, environment or resume kwargs')
        need(actual['agent'].get('mcp_servers',[])==[]
             and actual['environment'].get('extra_docker_compose',[])==[], 'no undeclared tools or mounts')
        for role in ('agent','verifier'):
            need(actual[role].get('include_logs',[])==[] and actual[role].get('exclude_logs',[])==[],
                 'no extra log inclusion or exclusion; stock omits empty defaults')
    need(config.get('source_trial') is None and config['verifier']['disable'] is True,
         'fresh original trial with verification disabled')
    need(set(('task_name','trial_name','trial_uri','task_id','task_checksum','config','agent_info')) <= set(result),
         'complete stock result identity fields; stock regrade still validates its full model')
    need(result['task_name']==TASK_NAME and result['trial_name']==selected['trial_name']
         and result.get('exception_info') is None and type(result.get('finished_at')) is str
         and result['finished_at'] and result.get('verifier_result') is None
         and result.get('verifier') is None and result.get('verifier_timing') is None
         and result.get('verifier_start_time') is None and result.get('verifier_end_time') is None,
         'complete original trial without evaluator feedback')
    manifest=h.decode(reader.read(root/'artifacts/manifest.json',262144))
    need(type(manifest) is list,'stock artifact manifest is a list')
    entries={}
    for row in manifest:
        need(type(row) is dict and row.get('service') in (None,'main'),'main-service artifacts only')
        key=row.get('source');need(key not in entries,'unique source artifact coverage');entries[key]=row
    need(set(entries)=={'/app/output/submission.jsonl','/logs/artifacts'},'only fixed and conventional artifact coverage')
    sub=entries['/app/output/submission.jsonl'];conv=entries['/logs/artifacts']
    need(sub.get('destination')==SUBMISSION and sub.get('type')=='file' and sub.get('status')=='ok',
         'successful exact submission artifact coverage')
    need(conv.get('destination')==CONVENTIONAL and conv.get('type')=='directory'
         and conv.get('status') in ('ok','empty') and (root/CONVENTIONAL).is_dir(),
         'complete implicit artifact directory including empty state')
    h.plain_path(root/SUBMISSION);s=(root/SUBMISSION).lstat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and 0<s.st_size<=128*1024**2,
         'bounded ordinary actual submission, not merely a successful trial')


def copy_trial_file(source,destination,expected,book):
    """Bounded streaming copy of one closed PFC trial member, not an executor."""
    h=materializer.load_helpers();h.plain_path(source)
    need(h.stamp(source.lstat())==expected,'source physical identity before freeze')
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    digest=hashlib.sha256();size=0
    with os.fdopen(fd,'rb') as src, destination.open('xb') as dst:
        need(h.stamp(os.fstat(src.fileno()))==expected,'opened frozen source identity')
        while True:
            chunk=src.read(min(1024**2,expected[4]-size+1))
            if not chunk:break
            size+=len(chunk);book[0]+=len(chunk)
            need(size<=expected[4] and book[0]<=PAIR_READ_MAX,'whole bounded freeze reads')
            digest.update(chunk);dst.write(chunk)
        dst.flush();os.fsync(dst.fileno())
        need(size==expected[4] and h.stamp(os.fstat(src.fileno()))==expected,
             'complete unchanged source body')
    need(h.stamp(source.lstat())==expected,'source unchanged after freeze')
    destination.chmod(0o400)
    check=hashlib.sha256()
    with destination.open('rb') as dst:
        while True:
            chunk=dst.read(1024**2)
            if not chunk:break
            book[0]+=len(chunk);need(book[0]<=PAIR_READ_MAX,'whole freeze readback budget');check.update(chunk)
    need(check.digest()==digest.digest(),'complete frozen readback')
    return materializer.descriptor(str(destination),b'') | {'bytes':size,'sha256':digest.hexdigest()}


def freeze_pair(request):
    h=materializer.load_helpers();reader=h.Reads(8*1024**2)
    need(type(request) is dict and set(request)=={'schema','execution_selected','plan','output_root','closed_arms'},
         'exact paired freeze request')
    need(request['schema']=='PFC_MATCHED_PAIR_FREEZE_V1' and request['execution_selected'] is True,
         'separately selected closed-pair freeze')
    # External existing owner supplies this assertion only after its accepted
    # complete process/container closure checks. This module makes no such query.
    need(request['closed_arms']==['A','B'],'both owned episodes physically closed before freeze')
    pin=request['plan'];plan=h.decode(reader.read(Path(pin['path']),262144,(pin['bytes'],pin['sha256'])))
    need(plan['schema']=='PFC_MATCHED_PAIR_SESSION_PLAN_V1','exact session plan')
    for row in plan['overlay_files']:
        rel=Path(row['path']);need(not rel.is_absolute() and '..' not in rel.parts,'relative session overlay pin')
        reader.read(Path(plan['root'])/rel,1048576,(row['bytes'],row['sha256']))
    out=h.plain_path(request['output_root'],exists=False);need(not os.path.lexists(out),'fresh whole pair freeze root')
    inventories={};roots={}
    for arm in ('A','B'):
        root=h.plain_path(plan['arms'][arm]['trial_dir']);roots[arm]=root
        need(out != root and out not in root.parents and root not in out.parents,'freeze disjoint from live trials')
        admit_completed_trial(root,plan['arms'][arm],reader)
        inventories[arm]=trial_inventory(root)
    need(roots['A']!=roots['B'] and roots['A'] not in roots['B'].parents and roots['B'] not in roots['A'].parents,
         'independent whole original trial roots')
    out.mkdir(mode=0o700);book=[reader.bytes];frozen={}
    for arm in ('A','B'):
        target=out/arm;target.mkdir(mode=0o700)
        files,dirs,total=inventories[arm]
        for relative in sorted(dirs,key=lambda s:(s.count('/'),s)):(target/relative).mkdir(mode=0o700,parents=True,exist_ok=True)
        rows=[]
        for relative,identity in sorted(files.items()):
            rows.append(copy_trial_file(roots[arm]/relative,target/relative,identity,book))
        need(trial_inventory(roots[arm])==inventories[arm],'entire source namespace unchanged during freeze')
        before_metadata=reader.bytes
        admit_completed_trial(target,plan['arms'][arm],reader)
        book[0]+=reader.bytes-before_metadata
        need(book[0]<=PAIR_READ_MAX,'complete freeze plus metadata read ceiling')
        frozen[arm]={'root':str(target),'files':rows,'directories':sorted(dirs),'bytes':total}
    # No regrade config exists until BOTH complete consumed namespaces pass.
    configs={};(out/'regrade-configs').mkdir(mode=0o700);(out/'regrades').mkdir(mode=0o700)
    for arm in ('A','B'):
        original=plan['arms'][arm]
        cfg=trial_config(original['task'],out/'regrades',original['trial_name']+'-grade',plan['agent'],
            source={'action':'regrade','type':'local','path':frozen[arm]['root']})
        configs[arm]=emit(out/'regrade-configs'/(arm+'.json'),cfg)
    receipt={'schema':'PFC_MATCHED_PAIR_FROZEN_V1','source_plan':pin,'arms':frozen,'regrade_configs':configs,
        'both_submissions_frozen_before_grade_configs':True,'streamed_read_bytes':book[0],
        'external_owner_physical_closure_assertion':request['closed_arms'],
        'native_closure_independently_observed_here':False,'grading_performed':False,
        'candidate_feedback_delivered':False,'new_benchmark_ids':0}
    return emit(out/'FROZEN_PAIR.json',receipt)


def main(argv):
    need(len(argv)==2 and argv[0] in ('prepare','freeze'),'prepare|freeze SELECTED_REQUEST.json')
    h=materializer.load_helpers();request=h.decode(h.Reads().read(Path(argv[1]),65536))
    print(json.dumps((prepare if argv[0]=='prepare' else freeze_pair)(request),sort_keys=True))


if __name__=='__main__':
    main(sys.argv[1:])
