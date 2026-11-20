"""Portable, single-attempt resource owner for the unchanged SMC private grader.

Source selection does not qualify Docker, the image, or numerical execution.
The public entry authenticates this directory and its external prepared runtime.
"""
import ast
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import types

PYTHON = '/usr/local/bin/python3.11'
GRADE_MEMORY = 2147483648
CONTROL_MEMORY = 536870912  # unreachable retained profile branch
WORK_SECONDS = 720
CLEANUP_SECONDS = 60
CPU_SOFT = 600
CPU_HARD = 605
META_CAP = 2097152
THREAD_ENV = {k: '1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')}
RUNNER_PIN = {'bytes':39552,'sha256':'05c2288a251c0dfd12ef7695fe2e446acf6dc7a7e72b7b4bb5848652a04cef6f'}
COMMON_PIN = {'bytes':6105,'sha256':'4e6deab837d498029cba4208b2fa6bdfafb0a3c61fc9dc02b32f32d8f938ae65'}
HELPERS = {'owned_exit.py':{'bytes':8088,'sha256':'d1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426'},'bounded_capture.py':{'bytes':7749,'sha256':'0a9274a1b08b00ee778143aa5ba35e4a3bf6b27dd6e8ea8838428b0652c0949f'}}
LABEL_PIN = {'bytes':2169,'sha256':'9c87d897215caead93206ecaa09ec2a33717609fd84a6e374d8e63f4daa330ef'}
SOURCE_NAMES = {'grade_bound.py','grade_child.py','label_policy.py',*HELPERS}
TARGET_PIN = {'bytes':105927616,'sha256':'f2f434d30193251b58e6a693381fdd185c8fbc0e47d38f8810e65295bc42c865'}
EVALUATOR_PIN = {'bytes':18292,'sha256':'05f49d3cdf7720ae68e0fb76113a9e450e9df3813c6c6837689f23a9be278476'}


def need(ok, message):
    if not ok: raise ValueError(message)


def absolute(value):
    need(type(value) is str and not any(c in value for c in ('\0','\n','\r',',')), 'unambiguous absolute path')
    p=Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p)==value, 'canonical absolute path')
    return p


def ordinary(value):
    p=absolute(str(value))
    need(not any(x.is_symlink() for x in (p,*p.parents)), 'no symlink in named host path')
    return p


def read(value,cap=META_CAP):
    p=ordinary(value);fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        a=os.fstat(f.fileno());need(stat.S_ISREG(a.st_mode) and a.st_nlink==1 and 0<a.st_size<=cap,'bounded ordinary single-link file')
        raw=f.read(cap+1);b=os.fstat(f.fileno());c=p.lstat()
    keys=('st_dev','st_ino','st_mode','st_nlink','st_size','st_mtime_ns','st_ctime_ns')
    need(len(raw)==a.st_size and all(getattr(a,k)==getattr(b,k)==getattr(c,k) for k in keys),'stable complete file read')
    return raw


def decode(raw):
    def unique(items):
        out={}
        for k,v in items:
            need(k not in out,'unique JSON key');out[k]=v
        return out
    return json.loads(raw,object_pairs_hook=unique,parse_constant=lambda _:need(False,'finite JSON'))


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def pin(raw):return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def descriptor(row):
    need(type(row) is dict and set(row)=={'path','bytes','sha256'},'exact file descriptor')
    absolute(row['path']);need(type(row['bytes']) is int and 0<row['bytes']<=512*1024**2 and re.fullmatch('[a-f0-9]{64}',row['sha256']),'finite source identity')
    return row


def checked(row,cap=META_CAP):
    descriptor(row);raw=read(row['path'],cap)
    need(pin(raw)=={k:row[k] for k in ('bytes','sha256')},'authenticated file identity')
    return raw


def reference(path,cap=META_CAP):
    p=ordinary(path);return {'path':str(p),**pin(read(p,cap))}


def write(path,value,cap=META_CAP):
    p=ordinary(path);raw=encoded(value);need(len(raw)<=cap,'bounded metadata publication')
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400)
    with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return {'path':str(p),**pin(raw)}


def load_source(path,expected,name):
    raw=read(path);need(pin(raw)==expected,'fixed helper source identity')
    m=types.ModuleType(name);m.__file__=str(path);exec(compile(raw,str(path),'exec'),m.__dict__)
    return m


def source_selection():
    root=ordinary(Path(__file__).parent);row=reference(root/'SOURCE.json');doc=decode(checked(row))
    need(doc['schema']=='smc_full_panel_grade_sources_v1' and set(doc['files'])==SOURCE_NAMES,'closed portable helper source roster')
    for name,expected in doc['files'].items():
        need(pin(read(root/name))==expected,'selected grade helper bytes')
    need(all(doc['files'][k]==v for k,v in HELPERS.items()) and doc['files']['label_policy.py']==LABEL_PIN,'unchanged process custody and label primitives')
    return row


def saved_owner_gate(prepared,result_sha256,expected_component_source):
    """Exact retained grading-prefix AST, without its final private grader call.

    Authentication pins the complete runner and common sources first. The sole
    replacement is the terminal return; all closure predicates and the complete
    aggregate validator are retained verbatim. Dependencies occupy a new local
    namespace, never sys.modules or any retained module's globals.
    """
    component=checked(prepared['component_source'])
    need(pin(component)==expected_component_source,'actual facade component identity')
    runner_raw=checked(prepared['owner_entry']);need(pin(runner_raw)==RUNNER_PIN,'unchanged retained runner')
    owner_entry=Path(prepared['owner_entry']['path'])
    common_raw=read(owner_entry.parent/'common.py');need(pin(common_raw)==COMMON_PIN,'unchanged owner metadata primitives')
    overlay=checked(prepared['overlay_source'])
    common=types.ModuleType('_smc_grade_common');common.__file__=str(owner_entry.parent/'common.py')
    exec(compile(common_raw,common.__file__,'exec'),common.__dict__)
    owner_manifest=decode(overlay)
    composition=common.read(owner_entry.parent/'COMPOSITION.json',owner_manifest['files']['COMPOSITION.json'])
    need(set(composition)=={'schema','repository_root','component_root','component_source','episode','retained_owner_source'}
         and composition['schema']=='smc_full_panel_owner_composition_v1'
         and composition['episode']=={'bytes':41057,'sha256':'7becc1746b068699070bc28f16286246427233e1a0082274b01a6ad75bcf8c3a'},
         'unchanged fixed facade and exact overlay composition')
    legacy_source=common.descriptor(composition['component_source'])
    need(legacy_source==expected_component_source,'actual selected full-panel component')
    legacy_raw=read(owner_entry.parent/'legacy.py')
    need(pin(legacy_raw)=={'bytes':2637,'sha256':'472a06c537f86c5b4e3f01cfa38f801262707692c639f6860bd6309b6327b7fd'},
         'unchanged complete full-panel owner adapter')
    # Invoke the unchanged retained source_identity function, not a substitute
    # Boolean or handwritten approximation of its metadata and leaf predicates.
    identity_node=next(n for n in ast.parse(legacy_raw).body
                       if isinstance(n,ast.FunctionDef) and n.name=='source_identity')
    identity_scope={k:common.__dict__[k] for k in ('read','body','need','pin','descriptor')}
    identity_scope.update(HERE=owner_entry.parent,COMPOSITION=composition,LEGACY_SOURCE=legacy_source,
       RUNTIME_FILES={'common.py','legacy.py','cli_custody.py','journal.py','process_owner.py',
          'group_bootstrap.py','trusted_controller.py','owned_episode.py','controller.py','runner.py','cgroup.py','COMPOSITION.json'})
    exec(compile(ast.Module(body=[identity_node],type_ignores=[]),str(owner_entry.parent/'legacy.py')+'#source_identity','exec'),identity_scope)
    source_identity=identity_scope['source_identity']
    owner_source=source_identity()
    need(owner_source==pin(overlay),'source identity remains the independently selected overlay')
    nodes={n.name:n for n in ast.parse(runner_raw).body if isinstance(n,ast.FunctionDef)}
    grading=nodes['grade'];terminal=grading.body[-1]
    need(isinstance(terminal,ast.Return) and isinstance(terminal.value,ast.Call)
         and isinstance(terminal.value.func,ast.Attribute) and terminal.value.func.attr=='_grade_from_owned_pair','exact retained terminal numerical call')
    # Return only already-validated local records. No predicate is removed.
    grading.name='_saved_gate';grading.body[-1]=ast.Return(ast.Tuple(elts=[ast.Name(id=x,ctx=ast.Load()) for x in ('result','invocation','pair_path')],ctx=ast.Load()))
    module=ast.fix_missing_locations(ast.Module(body=[nodes['validate_aggregate_completion'],grading],type_ignores=[]))
    namespace={k:common.__dict__[k] for k in ('CONDITIONS','ordinary','body','pin','read','need','encoded')}
    namespace.update(Path=Path,legacy=types.SimpleNamespace(source_identity=source_identity))
    exec(compile(module,str(owner_entry)+'#saved-grade-prefix','exec'),namespace)
    result,invocation,pair_path=namespace['_saved_gate'](prepared['owner_root'],result_sha256,None,None,None,None)
    need(invocation['output']==prepared['execution_root'] and invocation['owner']==prepared['owner_root']
         and invocation['protocol_path']==prepared['protocol']['path']
         and invocation['protocol_pin']=={k:prepared['protocol'][k] for k in ('bytes','sha256')},'prepared public entry joins actual owner invocation')
    need(not os.path.lexists(Path(invocation['output'])/'GRADE_STARTED.json'),'original single-grade lock remains unused')
    return {'owner_source':owner_source,'owner_result':reference(Path(prepared['owner_root'])/'RESULT.json'),
            'pair_closed':reference(pair_path),'execution_root':invocation['output'],
            'grade_lock':str(Path(invocation['output'])/'GRADE_STARTED.json')}


def label_policy():
    return load_source(Path(__file__).parent/'label_policy.py',LABEL_PIN,'_smc_grade_label_policy')


def validate_runtime(runtime,expected_image_id):
    need(type(runtime) is dict and set(runtime)=={'schema','docker','socket','image','readonly_mounts','work_root'}
         and runtime['schema']=='smc_full_panel_grade_runtime_v1','closed portable grade runtime')
    descriptor(runtime['docker']);ordinary(runtime['docker']['path'])
    need(type(runtime['socket']) is str and runtime['socket'].startswith('unix:///'),'explicit Unix Docker endpoint')
    ordinary(runtime['socket'][7:]);ordinary(runtime['work_root'])
    image=runtime['image']
    need(type(image) is dict and set(image)=={'id','architecture','labels','container_base_labels','environment'}
         and image['id']==expected_image_id and re.fullmatch('sha256:[a-f0-9]{64}',image['id'])
         and image['architecture'] in ('arm64','amd64'),'authentic deployment image and explicit Linux architecture')
    need(type(image['labels']) is dict and all(type(k) is type(v) is str for k,v in image['labels'].items())
         and not {'codex.smc-original-full-panel','codex.smc-original-operation'}&set(image['labels']),'exact inherited image labels')
    label_policy().validate_label_maps(image['labels'],image['container_base_labels'])
    env=image['environment'];need(type(env) is list and all(type(x) is str and '=' in x and '\0' not in x for x in env)
         and len({x.split('=',1)[0] for x in env})==len(env),'exact unique inherited image environment')
    need(type(runtime['readonly_mounts']) is list and len(runtime['readonly_mounts'])<=10,'finite explicit grade dependency mounts')
    for p in runtime['readonly_mounts']:ordinary(p)
    return runtime


def build_invocation(prepared,runtime_path,runtime_sha256,owner_result_sha256,target,evaluator,output,scratch_bytes,*,expected_source,expected_image_id):
    source=source_selection();rr=reference(runtime_path);need(rr['sha256']==runtime_sha256,'selected grade runtime')
    runtime=validate_runtime(decode(checked(rr)),expected_image_id)
    need(type(scratch_bytes) is int and 0<scratch_bytes<=536870912,'original finite snapshot ceiling')
    work=ordinary(runtime['work_root']);need(work.parent.is_dir() and not os.path.lexists(work),'fresh grade owner root')
    need(ordinary(output)==work/'report'/'REPORT.json','exact private report output')
    need(not work.is_relative_to(ordinary(prepared['root'])) and not ordinary(prepared['root']).is_relative_to(work),'disjoint grading and prepared roots')
    private={}
    for key,value,expected in (('target',target,TARGET_PIN),('evaluator',evaluator,EVALUATOR_PIN)):
        p=ordinary(value);st=p.lstat();need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==expected['bytes'],'named private input shape; body not read')
        private[key]={'path':str(p),**expected}
    gate=saved_owner_gate(prepared,owner_result_sha256,expected_source)
    invocation={'schema':'smc_full_panel_bounded_grade_invocation_v1','prepared':prepared,'runtime':runtime,'runtime_descriptor':rr,
                'helper_source':source,'expected_component_source':expected_source,'expected_image_id':expected_image_id,
                'owner_result_sha256':owner_result_sha256,'private_files':private,'report_path':str(output),
                'scratch_bytes':scratch_bytes,'token':os.urandom(16).hex(),'gate':gate,
                'bounds':{'memory_bytes':GRADE_MEMORY,'cpu_soft_seconds':CPU_SOFT,'cpu_hard_seconds':CPU_HARD,
                          'work_seconds':WORK_SECONDS,'cleanup_seconds':CLEANUP_SECONDS,'threads':1}}
    actor_for(invocation,{'path':str(work/'REQUEST.json'),'bytes':1,'sha256':'0'*64})
    return invocation


def validate_actor(actor,private_paths):
    need(type(actor) is dict and set(actor)=={'role','token','operation_id','image_id','image_labels','container_base_labels','image_environment','architecture','entrypoint','arguments','workdir','scratch_dir','readonly_mounts','writable_mounts','uid','gid'},'closed grade actor')
    need(actor['role']=='grade' and actor['uid']==actor['gid']==0 and re.fullmatch('[a-f0-9]{32}',actor['token']),'trusted grade-only profile')
    need(actor['operation_id']=='smc-public-grade-'+actor['token'],'exact fresh operation identity')
    need(actor['scratch_dir']=='/tmp','bounded guest scratch');descriptor(actor['entrypoint'])
    label_policy().validate_label_maps(actor['image_labels'],actor['container_base_labels'])
    need(type(actor['arguments']) is list and all(type(x) is str and '\0' not in x for x in actor['arguments']),'exact grade arguments')
    paths=[]
    for key in ('readonly_mounts','writable_mounts'):
        need(type(actor[key]) is list and 1<=len(actor[key])<=16,'finite mount count')
        for m in actor[key]:
            need(set(m)=={'source','destination'} and m['source']==m['destination'],'unchanged absolute proof paths')
            p=ordinary(m['source']);need(str(p) not in ('/','/Users','/home','/root','/tmp','/var','/usr','/proc','/sys','/dev'),'no broad host authority')
            need(not any(p.is_relative_to(Path(q)) or Path(q).is_relative_to(p) for q in ('/tmp','/proc','/sys','/dev','/var/run/docker.sock','/smc-docker.sock')),'no runtime socket or control namespace mounts')
            paths.append(str(p))
    need(len(paths)==len(set(paths)),'unique exact mounts')
    need(all(any(p==m['destination'] for m in actor['readonly_mounts']) for p in private_paths),'exact readonly private file leaves')
    need(not any(absolute(p).is_relative_to(absolute(m['destination'])) for p in private_paths for m in actor['writable_mounts']),'private files never writable')
    need(any(absolute(actor['entrypoint']['path']).is_relative_to(absolute(m['destination'])) for m in actor['readonly_mounts']),'authenticated child mounted readonly')
    need(any(absolute(actor['workdir'])==absolute(m['destination']) for m in actor['writable_mounts']),'exact report work directory')
    return actor


def actor_for(invocation,request):
    runtime=invocation['runtime'];work=Path(runtime['work_root']);prepared=invocation['prepared'];source=Path(invocation['helper_source']['path']).parent
    readonly=[str(source),prepared['root'],request['path'],invocation['runtime_descriptor']['path'],*[r['path'] for r in invocation['private_files'].values()],*runtime['readonly_mounts']]
    need(len(readonly)==len(set(readonly)),'no duplicate selected roots')
    socket_path=absolute(runtime['socket'][7:])
    need(not any(socket_path.is_relative_to(absolute(p)) or absolute(p)==socket_path for p in readonly),'Docker endpoint never exposed to private grader')
    image=runtime['image']
    actor={'role':'grade','token':invocation['token'],'operation_id':'smc-public-grade-'+invocation['token'],
           'image_id':image['id'],'image_labels':image['labels'],'container_base_labels':image['container_base_labels'],'image_environment':image['environment'],'architecture':image['architecture'],
           'entrypoint':reference(source/'grade_child.py'),'arguments':['--request',request['path'],'--sha256',request['sha256'],
                        '--source-sha256',invocation['helper_source']['sha256']],
           'workdir':str(work/'report'),'scratch_dir':'/tmp','uid':0,'gid':0,
           'readonly_mounts':[{'source':p,'destination':p} for p in readonly],
           'writable_mounts':[{'source':prepared['execution_root'],'destination':prepared['execution_root']},
                              {'source':str(work/'report'),'destination':str(work/'report')}]}
    validate_actor(actor,[r['path'] for r in invocation['private_files'].values()]);return actor


def environment(actor):
    values = dict(x.split('=', 1) for x in actor['image_environment'])
    values.update({k: '1' for k in ('PYTHONDONTWRITEBYTECODE', 'OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS',
                                  'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS')})
    values.update(HOME=actor['workdir'], TMPDIR=actor['scratch_dir'], LC_ALL='C',
                  PATH='/usr/local/bin:/usr/bin:/bin', CUDA_VISIBLE_DEVICES='', PYTHONNOUSERSITE='1')
    if actor['role'] == 'control':
        values.update(DOCKER_HOST='unix:///smc-docker.sock', DOCKER_CONFIG=actor['workdir'] + '/docker-config', GOMAXPROCS='1')
    return values

def build_create(actor, private_paths):
    validate_actor(actor, private_paths)
    control = actor['role'] == 'control'
    name = 'smc-original-' + actor['token'] + '-' + actor['role']
    memory = CONTROL_MEMORY if control else GRADE_MEMORY
    pids = 128
    cpu = 900 if control else 600
    args = ['container', 'create', '--pull', 'never', '--name', name,
            '--label', 'codex.smc-original-full-panel=' + actor['token'],
            '--label', 'codex.smc-original-operation=' + actor['operation_id'],
            '--network', 'none', '--read-only', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--user',
            str(actor['uid']) + ':' + str(actor['gid']), '--ipc', 'private',
            '--pids-limit', str(pids), '--memory', str(memory),
            '--memory-swap', str(memory), '--cpus', '1',
            '--ulimit', 'nofile=1024:1024', '--ulimit', 'core=0:0',
            '--ulimit', 'cpu=' + str(cpu) + ':' + str(cpu + 5),
            '--log-driver', 'none', '--restart', 'no', '--shm-size', '16777216',
            '--init=false', '--workdir', actor['workdir']]
    if control:
        args += ['--cap-add', 'SYS_PTRACE', '--cap-add', 'DAC_OVERRIDE',
                 '--security-opt', 'label=disable', '--userns', 'host',
                 '--pid', 'host', '--cgroupns', 'host']
    else:
        # The retained owner creates root-owned0700 proof directories.  Keep
        # those frozen modes; this trusted grader needs exact private-file read
        # access, not a rewritten proof tree or participant privileges.
        args += ['--cap-add', 'DAC_OVERRIDE', '--cgroupns', 'private']
    for key, suffix in (('readonly_mounts', ',readonly'), ('writable_mounts', '')):
        for row in actor[key]:
            args += ['--mount', 'type=bind,src=' + row['source'] + ',dst=' + row['destination'] + suffix]
    if control:
        args += ['--mount', 'type=bind,src=/var/run/docker.sock,dst=/smc-docker.sock',
                 '--mount', 'type=bind,src=/sys/fs/cgroup,dst=/sys/fs/cgroup']
    tmp_bytes = 16777216 if control else 1073741824
    args += ['--tmpfs', '/tmp:rw,nosuid,nodev,noexec,size=' + str(tmp_bytes) + ',mode=1777']
    for key, value in sorted(environment(actor).items()):
        args += ['--env', key + '=' + value]
    args += ['--entrypoint', PYTHON, actor['image_id'], '-I', '-B',
             actor['entrypoint']['path'], *actor['arguments']]
    return {'name': name, 'argv': args, 'memory': memory, 'cpu_seconds': cpu,
            'pids': pids, 'private_grading': not control}

def verify_container(value, actor, built):
    need(type(value) is dict, 'owned actor exists')
    h, c = value['HostConfig'], value['Config']
    control = actor['role'] == 'control'
    need(re.fullmatch('[a-f0-9]{64}', value['Id']) and value['Name'] == '/' + built['name']
         and value['Image'] == c['Image'] == actor['image_id'], 'exact actor identity')
    expected_labels = label_policy().validate_label_maps(actor['image_labels'], actor['container_base_labels'])
    expected_labels['codex.smc-original-full-panel'] = actor['token']
    expected_labels['codex.smc-original-operation'] = actor['operation_id']
    need(c['Labels'] == expected_labels and c['User'] == str(actor['uid']) + ':' + str(actor['gid'])
         and c['Entrypoint'] == [PYTHON]
         and c['Cmd'] == ['-I', '-B', actor['entrypoint']['path'], *actor['arguments']],
         'exact inherited and ownership labels and explicit entry command')
    need(c['WorkingDir'] == actor['workdir'] and not c.get('Volumes')
         and sorted(c['Env']) == sorted(k + '=' + v for k, v in environment(actor).items()), 'exact environment and workdir')
    need(h['Memory'] == h['MemorySwap'] == built['memory'] and h['NanoCpus'] == 1000000000
         and h['PidsLimit'] == built['pids'] and h['ReadonlyRootfs'] is True
         and h['Privileged'] is False and h['NetworkMode'] == 'none'
         and h['IpcMode'] == 'private' and h['ShmSize'] == 16777216
         and h['CapDrop'] == ['ALL'] and h['AutoRemove'] is False
         and h['LogConfig']['Type'] == 'none'
         and h['RestartPolicy'] == {'Name': 'no', 'MaximumRetryCount': 0},
         'fixed finite actor resource and isolation profile')
    cap_add = h['CapAdd']
    expected_cap_add = {'CAP_SYS_PTRACE', 'CAP_DAC_OVERRIDE'} if control else {'CAP_DAC_OVERRIDE'}
    need(type(cap_add) is list and all(type(x) is str for x in cap_add)
         and len(cap_add) == len(set(cap_add)) and set(cap_add) == expected_cap_add,
         'exact witnessed capability names; no extra, missing or duplicate capabilities')
    need(h['PidMode'] == ('host' if control else '')
         and h['CgroupnsMode'] == ('host' if control else 'private')
         and h['UsernsMode'] == ('host' if control else ''), 'explicit namespace authority')
    need(h['SecurityOpt'] == (['no-new-privileges:true', 'label=disable'] if control
                              else ['no-new-privileges:true']), 'exact security options')
    need(not h['Devices'] and not h['DeviceRequests'] and not h['PortBindings']
         and not h['VolumesFrom'] and not h['Links'] and not h['ExtraHosts']
         and not h.get('Binds') and not h.get('GroupAdd') and not h.get('DeviceCgroupRules')
         and h.get('Init') is False and h.get('CgroupParent') == '',
         'no unselected devices, network aliases, ports or inherited volumes')
    limits = {r['Name']: (r['Soft'], r['Hard']) for r in h['Ulimits']}
    need(len(limits) == len(h['Ulimits']) and limits == {'nofile': (1024, 1024), 'core': (0, 0),
                    'cpu': (built['cpu_seconds'], built['cpu_seconds'] + 5)}, 'exact finite actor CPU limit')
    expected = {}
    for key, writable in (('readonly_mounts', False), ('writable_mounts', True)):
        for row in actor[key]:
            expected[row['destination']] = (row['source'], writable)
    if control:
        # Exact requested source witnessed in the retained main created profile.
        # The bridge still freshly joins daemon ID/API before any data access.
        expected['/smc-docker.sock'] = ('/var/run/docker.sock', True)
        expected['/sys/fs/cgroup'] = ('/sys/fs/cgroup', True)
    mounts = value['Mounts']
    need(len(mounts) == len(expected) and {m['Destination'] for m in mounts} == set(expected),
         'complete exact bind-mount inventory')
    for row in mounts:
        src, writable = expected[row['Destination']]
        sources = (src, '/host_mnt' + src) if src.startswith('/Users/') else (src,)
        need(row['Type'] == 'bind' and row['Propagation'] == 'rprivate'
             and row['Source'] in sources and row['RW'] is writable, 'exact source/destination/access')
    tmp_bytes = 16777216 if control else 1073741824
    need(h['Tmpfs'] == {'/tmp': 'rw,nosuid,nodev,noexec,size=' + str(tmp_bytes) + ',mode=1777'}, 'exact bounded temporary area')
    return value['Id']

def validate_closed_process(record):
    need(record['cleanup']['cleanup_complete'] is True and record['cleanup']['reaped'] is True
         and record['cleanup']['group_absence_observed'] is True and record['cleanup']['error'] is None
         and record['cleanup']['pid'] == record['pid'] and record['cleanup']['returncode'] == record['returncode']
         and record['capture']['all_eof_observed'] is True and record['capture']['storage_truncated'] is False
         and record['capture']['read_ceiling_exhausted'] is False and record['capture']['closed_without_eof'] is False
         and record['capture']['stream_close_errors'] == [], 'owned process and full stream closure')

def validate_process(record):
    validate_closed_process(record)
    need(record['returncode'] == 0, 'successful owned process')

def exact_missing_container(stderr, name):
    text = stderr.strip(); message = 'No such container: ' + name
    if text in ('Error: ' + message, 'Error response from daemon: ' + message, 'Error: No such object: ' + name):
        return True
    prefix = 'Error response from daemon: '
    if not text.startswith(prefix):
        return False
    try:
        body = decode(text[len(prefix):])
    except (ValueError, TypeError):
        return False
    return type(body) is dict and set(body) == {'message'} and body['message'] == message

def inspect_image(owner, actor, deadline):
    result = owner.cli(['image','inspect','--format','{"Id":{{json .Id}},"Os":{{json .Os}},"Architecture":{{json .Architecture}},"Config":{{json .Config}}}', actor['image_id']], deadline, 'inspect_'+actor['role']+'_image')
    validate_process(result)
    value = decode(result['stdout'])
    need(value['Id'] == actor['image_id'] and value['Os'] == 'linux' and value['Architecture'] == actor['architecture']
         and value['Config']['Labels'] == actor['image_labels']
         and value['Config']['Env'] == actor['image_environment'] and not value['Config'].get('Volumes'), 'exact immutable runtime and image environment')
    return value

def cleanup_actor(owner, profile, actor, built, cid, intended, deadline):
    if not intended: return {'intended':False,'container_absent':True}
    value = owner.inspect(cid or built['name'], deadline)
    if value is None:
        need(cid is not None, 'unacknowledged create cannot close from missing name alone')
        return {'intended':True,'container_id':cid,'container_absent':True}
    found = profile.verify_container(value, actor, built)
    need(cid is None or found == cid, 'same acknowledged container during cleanup')
    if value['State']['Running']:
        result = owner.cli(['container','stop','--time','5',found], deadline, 'stop_owned_'+actor['role'], 15)
        validate_process(result)
        value = owner.inspect(found,deadline)
        need(value is not None and profile.verify_container(value,actor,built) == found and not value['State']['Running'], 'owned stopped actor before plain removal')
    result = owner.cli(['container','rm',found], deadline, 'remove_owned_'+actor['role'])
    validate_process(result)
    need(result['stdout'].strip() == found and owner.inspect(found,deadline) is None, 'exact CID removed and absent')
    return {'intended':True,'container_id':found,'container_absent':True}


class OwnedProcesses:
    """Fixed operation composition of retained ownership/capture primitives."""
    def __init__(self, plan, own, capture, started):
        self.plan, self.own, self.cap = plan, own, capture
        self.start = started; self.work_end = self.start + WORK_SECONDS; self.end = self.start + WORK_SECONDS + CLEANUP_SECONDS
        self.calls = []
        self.env = {'PATH': '/usr/bin:/bin', 'HOME': plan['output'], 'LC_ALL': 'C', **THREAD_ENV,
                    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1', 'CUDA_VISIBLE_DEVICES': ''}

    def run(self, argv, deadline, label, docker=False):
        need(len(self.calls) < 32 and time.monotonic() + 5 < deadline <= self.end, 'finite selected process count/deadline')
        env = dict(self.env)
        if docker:
            env.update(DOCKER_CONFIG=str(Path(self.plan['output']) / 'docker-config'), DOCKER_HOST=self.plan['socket'], GOMAXPROCS='1')
        index = len(self.calls)
        write(Path(self.plan['output']) / 'calls' / ('%02d.INTENT.json' % index),
              {'label': label, 'argv': argv, 'deadline_monotonic': deadline, 'start_new_session': True})
        self.own.preflight()
        proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                close_fds=True, start_new_session=True, env=env, cwd=self.plan['output'])
        observer = capture = None
        result = {'label': label, 'argv': argv, 'pid': proc.pid, 'errors': []}
        try:
            observer = self.own.ExitObserver(proc)
            capture = self.cap.BoundedCapture(proc, retained_per_stream=65536, read_ceiling=131072)
            while time.monotonic() < deadline - 5:
                capture.pump(.025)
                need(not capture.read_ceiling_exhausted, 'bounded process output')
                if observer.wait(time.monotonic()):
                    break
            need(observer.exit_observed, 'owned process deadline')
        except BaseException as error:
            result['errors'].append({'type': type(error).__name__, 'message': str(error)[:512]})
        finally:
            cleanup = self.own.stop_and_reap(proc, observer, min(deadline, time.monotonic() + 3))
            result['cleanup'] = cleanup
            if capture is not None:
                try:
                    need(cleanup['reaped'] is True, 'exclusive reap before EOF drain')
                    capture.finish(proc, min(deadline, time.monotonic() + 2))
                    result.update({k: v.retained().decode('utf-8', errors='strict') for k, v in capture.lanes.items()})
                except BaseException as error:
                    result['errors'].append({'type': type(error).__name__, 'message': str(error)[:512]})
                finally:
                    capture.close()
                    result['capture'] = capture.summary()
            result['returncode'] = proc.returncode
            self.calls.append(write(Path(self.plan['output']) / 'calls' / ('%02d.json' % index), result, 393216))
        need(capture is not None and not result['errors'], 'owned process deadline/capture complete')
        validate_closed_process(result)
        return result

    def cli(self, args, deadline, label, seconds=12):
        return self.run([self.plan['docker']['path'], '--host', self.plan['socket'], *args], min(deadline, time.monotonic() + seconds), label, True)

    def inspect(self, identity, deadline):
        fmt = '{"Id":{{json .Id}},"Name":{{json .Name}},"Image":{{json .Image}},"State":{{json .State}},"Config":{{json .Config}},"HostConfig":{{json .HostConfig}},"Mounts":{{json .Mounts}}}'
        result = self.cli(['container', 'inspect', '--format', fmt, identity], deadline, 'container_inspect')
        if result['returncode']:
            need(result['returncode'] == 1 and not result['stdout'].strip() and exact_missing_container(result['stderr'], identity), 'exact owned container absence')
            return None
        return decode(result['stdout'])

def validate_invocation(invocation):
    need(type(invocation) is dict and set(invocation)=={'schema','prepared','runtime','runtime_descriptor','helper_source','expected_component_source','expected_image_id','owner_result_sha256','private_files','report_path','scratch_bytes','token','gate','bounds'}
         and invocation['schema']=='smc_full_panel_bounded_grade_invocation_v1','closed bounded invocation')
    need(invocation['bounds']=={'memory_bytes':GRADE_MEMORY,'cpu_soft_seconds':CPU_SOFT,'cpu_hard_seconds':CPU_HARD,
          'work_seconds':WORK_SECONDS,'cleanup_seconds':CLEANUP_SECONDS,'threads':1},'unchanged fixed whole-grader bound')
    need(invocation['helper_source']==source_selection(),'same selected public helper source')
    need(decode(checked(invocation['runtime_descriptor']))==invocation['runtime'],'exact external runtime bytes')
    validate_runtime(invocation['runtime'],invocation['expected_image_id'])
    need(re.fullmatch('[a-f0-9]{32}',invocation['token']),'fresh fixed-size operation token')
    need(type(invocation['scratch_bytes']) is int and 0<invocation['scratch_bytes']<=536870912,'finite protected snapshot cap')
    need(invocation['report_path']==str(Path(invocation['runtime']['work_root'])/'report'/'REPORT.json'),'fixed report path')
    need(set(invocation['private_files'])=={'target','evaluator'},'original two private inputs')
    for k,p in (('target',TARGET_PIN),('evaluator',EVALUATOR_PIN)):
        descriptor(invocation['private_files'][k]);need({x:invocation['private_files'][k][x] for x in p}==p,'original scientific private identities')
    gate=saved_owner_gate(invocation['prepared'],invocation['owner_result_sha256'],invocation['expected_component_source'])
    need(gate==invocation['gate'],'saved genuine proof gate unchanged')
    return gate


def completion(error,closed,calls):
    """Pure result admission shared by actual owner and generated controls."""
    calls_closed=True
    for call in calls:
        try:validate_closed_process(call)
        except (ValueError,KeyError,TypeError):calls_closed=False
    absent=type(closed) is dict and closed.get('container_absent') is True
    observed_errors=any(type(c) is not dict or c.get('errors')!=[] for c in calls)
    return {'success':error is None and not observed_errors and absent and calls_closed,
            'status':'closure_unknown' if not absent or not calls_closed else ('failed' if error is not None or observed_errors else 'graded'),
            'container_absent':absent,'calls_closed':calls_closed}


def run_grade(invocation):
    """One owned grading attempt. No retries, release files, or private ledger."""
    start=time.monotonic();work_end=start+WORK_SECONDS;final_end=work_end+CLEANUP_SECONDS
    validate_invocation(invocation)
    runtime=invocation['runtime'];root=ordinary(runtime['work_root'])
    need(root.parent.is_dir() and not os.path.lexists(root),'fresh exclusive grading owner root')
    # Docker binary is public runtime software, never a private scientific input.
    checked(runtime['docker'],64*1024**2)
    need(stat.S_ISSOCK(ordinary(runtime['socket'][7:]).lstat().st_mode),'ordinary selected Docker Unix socket')
    own=load_source(Path(__file__).parent/'owned_exit.py',HELPERS['owned_exit.py'],'_smc_grade_owned_exit')
    capture=load_source(Path(__file__).parent/'bounded_capture.py',HELPERS['bounded_capture.py'],'_smc_grade_capture')
    own.preflight()
    need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'no existing host wall timer')
    prior_handler=signal.getsignal(signal.SIGALRM)
    def expired(signum,frame):raise TimeoutError('whole grade owner wall ceiling')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.001,final_end-time.monotonic()))
    owner=None;actor=built=None;cid=None;intended=False;closed={'intended':False,'container_absent':True};error=None;report=None
    try:
        root.mkdir(mode=0o700)
        for name in ('calls','report','docker-config'):(root/name).mkdir(mode=0o700)
        request=write(root/'REQUEST.json',invocation)
        plan={'output':str(root),'docker':runtime['docker'],'socket':runtime['socket']}
        owner=OwnedProcesses(plan,own,capture,start)
        actor=actor_for(invocation,request);private=[r['path'] for r in invocation['private_files'].values()]
        built=build_create(actor,private)
        need(time.monotonic()+10<work_end,'finite remaining grading work window')
        inspect_image(owner,actor,work_end)
        need(owner.inspect(built['name'],work_end) is None,'fresh exact grading container name')
        write(root/'CREATE_INTENT.json',{'actor':actor,'argv':built['argv']})
        intended=True
        result=owner.cli(built['argv'],work_end,'create_grade');validate_process(result)
        need(re.fullmatch('[a-f0-9]{64}',result['stdout'].strip()),'strict created container acknowledgement');cid=result['stdout'].strip()
        value=owner.inspect(cid,work_end)
        need(verify_container(value,actor,built)==cid and value['State']['Status']=='created','exact resource profile before private grading starts')
        result=owner.cli(['container','start',cid],work_end,'start_grade');validate_process(result);need(result['stdout'].strip()==cid,'exact started grading container')
        result=owner.cli(['container','wait',cid],work_end,'wait_grade',WORK_SECONDS);validate_process(result);need(result['stdout'].strip()=='0','successful bounded private grade')
        value=owner.inspect(cid,work_end)
        need(verify_container(value,actor,built)==cid and value['State']['Status']=='exited'
             and value['State']['Running'] is False and value['State']['ExitCode']==0
             and value['State']['OOMKilled'] is False and not value['State']['Error'],'successful stopped grader without OOM')
        report=reference(invocation['report_path'])
        need(os.path.lexists(invocation['gate']['grade_lock']),'unchanged original grade lock was actually consumed')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)[:1024]}
    finally:
        try:
            if owner is not None and built is not None:
                profile=types.SimpleNamespace(verify_container=verify_container)
                closed=cleanup_actor(owner,profile,actor,built,cid,intended,min(final_end-5,time.monotonic()+55))
            elif intended:closed={'container_absent':False,'container_id':cid,'error':'creation custody unresolved'}
        except BaseException as exc:
            closed={'container_absent':False,'container_id':cid,'error':{'type':type(exc).__name__,'message':str(exc)[:1024]}}
        try:
            calls=[] if owner is None else [decode(checked(row)) for row in owner.calls]
            outcome=completion(error,closed,calls)
            final={'schema':'smc_full_panel_bounded_grade_result_v1',**outcome,'error':error,'closed':closed,
                   'bounds':invocation['bounds'],'request':reference(root/'REQUEST.json') if (root/'REQUEST.json').exists() else None,
                   'calls':[] if owner is None else owner.calls,'report':report if outcome['success'] else None,
                   'grade_lock':reference(invocation['gate']['grade_lock']) if os.path.lexists(invocation['gate']['grade_lock']) else None,
                   'native_runtime_qualified_by_this_source':False,'elapsed_seconds':time.monotonic()-start}
            need(time.monotonic()<final_end,'final evidence remains inside total wall envelope')
            write(root/'RESULT.json',final)
        finally:
            signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,prior_handler)
    return final
