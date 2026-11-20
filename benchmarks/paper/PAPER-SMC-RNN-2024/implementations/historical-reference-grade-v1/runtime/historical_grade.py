"""One resource-owned historical score job; never a participant execution receipt.

A single child snapshots both frozen predictions, then runs the unchanged scorer
for both arms under one resource envelope. Prior inference failure is preserved.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import time
import types

PYTHON='/usr/local/bin/python3.11'
GRADE_MEMORY=2147483648
CONTROL_MEMORY=536870912  # unreachable retained donor branch; grade-only admission
WORK_SECONDS=720
CLEANUP_SECONDS=60
CPU_SOFT=600
CPU_HARD=605
META_CAP=2097152
THREAD_ENV={k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','VECLIB_MAXIMUM_THREADS','BLIS_NUM_THREADS')}
IMAGE_ID='sha256:cdca0c2ffab6831a5da01d5a17f2aa3778af3ad898878478712ded8cf56f6704'
DAEMON={'Architecture':'aarch64','CgroupDriver':'cgroupfs','CgroupVersion':'2','ID':'7ba82b94-d188-4dc6-9f4b-bb253c1e4a1c','OSType':'linux'}
VERSION={'Version':'28.3.2','ApiVersion':'1.51','Os':'linux','Arch':'arm64'}
HELPERS={'owned_exit.py':{'bytes':8088,'sha256':'d1d4aa36bf3893ee07e16f7086fd123c08d81ec47278efd6be3091c862c59426'},'bounded_capture.py':{'bytes':7749,'sha256':'0a9274a1b08b00ee778143aa5ba35e4a3bf6b27dd6e8ea8838428b0652c0949f'}}
LABEL_PIN={'bytes':2169,'sha256':'9c87d897215caead93206ecaa09ec2a33717609fd84a6e374d8e63f4daa330ef'}
PROVENANCE_PINS={
 'handoff':{'bytes':4838,'sha256':'4efd8c5ca4ed3e44ec2878bb70c07d4f3ad337c85f976d975f0567e960a0608f'},
 'qualification':{'bytes':34121,'sha256':'98908677f63e05966c82e92dfcdf27c4a4bcd688e1faa6366e8efec591d32f9d'},
 'binding':{'bytes':10784,'sha256':'a77fafc5772dbae5ce741037b77e76be1a51de00a6e7f32711fbd1edefeab79b'},
 'runtime_lock':{'bytes':45149,'sha256':'ed45e9fcaa530fa1f3e3849e92a9b9c7bee732248052bf2ed8cd3dc9398734b7'}}
ADAPTER_PIN={'bytes':635,'sha256':'f01e373f3a66beda3b3374e1d4d103e54aca1802b57819bbb5b82b08e3ca6c0c'}
ADAPTER_NAMES={'historical_score.py','historical_grade_child.py','scorer.py','reference_panel.json'}
SOURCE_NAMES={'historical_grade.py','owned_exit.py','bounded_capture.py','label_policy.py'}


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

def label_policy():
    return load_source(Path(__file__).parent/'label_policy.py',LABEL_PIN,'_smc_grade_label_policy')

def validate_actor(actor,private_paths):
    need(type(actor) is dict and set(actor)=={'role','token','operation_id','image_id','image_labels','container_base_labels','image_environment','architecture','entrypoint','arguments','workdir','scratch_dir','readonly_mounts','writable_mounts','uid','gid'},'closed grade actor')
    need(actor['role']=='grade' and actor['uid']==actor['gid']==0 and re.fullmatch('[a-f0-9]{32}',actor['token']),'trusted grade-only profile')
    need(actor['operation_id']=='smc-historical-reference-grade-'+actor['token'],'exact fresh operation identity')
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
    name = 'smc-historical-' + actor['token'] + '-' + actor['role']
    memory = CONTROL_MEMORY if control else GRADE_MEMORY
    pids = 128
    cpu = 900 if control else 600
    args = ['container', 'create', '--pull', 'never', '--name', name,
            '--label', 'codex.smc-historical-reference=' + actor['token'],
            '--label', 'codex.smc-historical-operation=' + actor['operation_id'],
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
    expected_labels['codex.smc-historical-reference'] = actor['token']
    expected_labels['codex.smc-historical-operation'] = actor['operation_id']
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

def source_selection():
    root=ordinary(Path(__file__).parent);row=reference(root/'SOURCE.json');doc=decode(checked(row))
    need(set(doc)=={'schema','files'} and doc['schema']=='smc_historical_grade_runtime_source_v1'
         and set(doc['files'])==SOURCE_NAMES,'exact historical owner source roster')
    for name,expected in doc['files'].items():need(pin(read(root/name))==expected,'frozen historical owner source')
    need(all(doc['files'][k]==v for k,v in HELPERS.items()) and doc['files']['label_policy.py']==LABEL_PIN,'unchanged custody and label helpers')
    return row


def validate_provenance(documents):
    """Typed, limited prior observations; never an invented participant owner."""
    need(set(documents)==set(PROVENANCE_PINS),'exact historical runtime provenance')
    handoff,q,binding,lock=(documents[k] for k in ('handoff','qualification','binding','runtime_lock'))
    need(handoff['schema']=='smc-retained-image-v3-final-handoff/v1'
         and handoff['status']=='scoped_constructor_and_generated_topology_actual_success_independently_accepted_all_known_scopes_closed'
         and handoff['image_id']==q['image_id']==binding['image_id']==IMAGE_ID,'same selected retained image provenance')
    need({k:handoff['final'][k] for k in ('bytes','sha256')}==PROVENANCE_PINS['qualification'],'accepted handoff joins exact actual result')
    need(q['schema']=='smc-retained-image-qualification-result/v1' and q['success'] is True
         and q['errors']==[] and q['owned_calls_closed'] is True and q['owned_cgroup_residual_possible'] is False
         and q['scoped_constructor_and_topology_qualified'] is True
         and q['production_8gib_or_full_task_qualification'] is False and q['image_admitted'] is False
         and q['binding_sha256']==PROVENANCE_PINS['binding']['sha256']
         and q['container_closure']=={'constructor':True,'controller':True,'producer':True}
         and q['daemon']==DAEMON,'closed prior constructor/socket/version/128MiB scope only')
    limits=handoff['scope_limits']
    need(all(limits[k] is False for k in ('image_admission_by_this_agent','original_arrays_models_or_grading',
         'original_image_build_success','production_8GiB_or_full_task_qualification','scientific_or_AI_result'))
         and limits['v1_v2_failures_preserved'] is True,'preserve limited prior result and historical failure')
    need(binding['schema']=='smc-retained-scientific-operator-binding/v1'
         and binding['original_build_success'] is False and binding['image_admitted'] is False
         and binding['base_image_id']=='sha256:4b80bfb662b0b8ef0ed8c816d6c74f1234a586e5f02d063322226f54790b398a'
         and binding['daemon_id']==DAEMON['ID'],'typed retained-image lineage without successful original build')
    image=binding['expected_image_metadata']
    need(image['Id']==IMAGE_ID and image['Os']=='linux' and image['Architecture']=='arm64'
         and image['Parent']==binding['base_image_id'] and not image['Config'].get('Volumes'),'exact selected scientific image metadata')
    label_policy().validate_label_maps(image['Config']['Labels'],binding['effective_container_labels'])
    need(image['Config']['Labels']['codex.smc-runtime-lock']==PROVENANCE_PINS['runtime_lock']['sha256']
         and lock['schema']=='smc-generic-runtime-wheel-lock/v1' and lock['generic_public_only'] is True
         and lock['native_qualification'] is False and len(lock['wheels'])==32,'unchanged locked public numerical software; no new native claim')
    return {'image':image,'container_base_labels':binding['effective_container_labels'],
            'allowed_omitted_config_defaults':binding['allowed_omitted_config_defaults'],
            'expected_semantic_config':binding['expected_semantic_config'],
            'prior_scope':'constructor_socket_version_and_128MiB_generated_topology_only',
            'original_image_build_success':False,'prior_full_scientific_qualification':False}


def validate_child_request(child,adapter_source,report_root):
    need(type(child) is dict and set(child)=={'schema','source','predictions','freezes','panel','protocol','historical_calibration','target','evaluator','output_root','scratch_bytes'}
         and child['schema']=='smc_historical_reference_grade_request_v1','distinct exact historical child request')
    need(child['source']==adapter_source and child['output_root']==str(report_root/'historical')
         and type(child['scratch_bytes']) is int and 0<child['scratch_bytes']<=536870912,'one fresh historical output and whole snapshot ceiling')
    need(set(child['predictions'])==set(child['freezes'])=={'causal','noncausal'},'exact two historical reference arms')
    for rows in (child['predictions'],child['freezes']):
        for row in rows.values():descriptor(row)
    for k in ('panel','protocol','historical_calibration','target','evaluator'):descriptor(child[k])
    return child


def inspect_request(request_path,request_sha256):
    selected=reference(request_path);need(selected['sha256']==request_sha256,'exact selected historical host request')
    request=decode(checked(selected))
    need(type(request) is dict and set(request)=={'schema','source','token','docker','socket','provenance','adapter_source','child_request','output_root'}
         and request['schema']=='smc_historical_grade_host_request_v1','closed historical host request, no participant-owner fields')
    need(request['source']==source_selection(),'selected exact historical host source')
    need(re.fullmatch('[a-f0-9]{32}',request['token']),'fresh 16-byte operation token')
    descriptor(request['docker']);ordinary(request['docker']['path'])
    need(type(request['socket']) is str and request['socket'].startswith('unix:///'),'exact Unix daemon endpoint')
    ordinary(request['socket'][7:]);root=ordinary(request['output_root'])
    need(root.parent.is_dir() and not os.path.lexists(root),'fresh historical host root')
    need(set(request['provenance'])==set(PROVENANCE_PINS),'exact saved provenance roster')
    documents={}
    for key,row in request['provenance'].items():
        need({k:row[k] for k in ('bytes','sha256')}==PROVENANCE_PINS[key],'fixed saved metadata identity')
        documents[key]=decode(checked(row))
    provenance=validate_provenance(documents)
    need(ADAPTER_PIN is not None and {k:request['adapter_source'][k] for k in ('bytes','sha256')}==ADAPTER_PIN,'selected frozen historical adapter source')
    adapter_manifest=decode(checked(request['adapter_source']));adapter_root=ordinary(Path(request['adapter_source']['path']).parent)
    need(set(adapter_manifest)=={'schema','files'} and adapter_manifest['schema']=='smc_historical_reference_grade_source_v1'
         and set(adapter_manifest['files'])==ADAPTER_NAMES,'exact historical scorer source closure')
    for name,expected in adapter_manifest['files'].items():need(pin(read(adapter_root/name))==expected,'frozen historical scoring source')
    child=validate_child_request(decode(checked(request['child_request'])),request['adapter_source'],root/'report')
    # Source work and host admission inspect names/sizes only. No prediction,
    # target or evaluator body is opened here; the child owns snapshot ordering.
    all_inputs=[*child['predictions'].values(),*child['freezes'].values(),*[child[k] for k in ('panel','protocol','historical_calibration','target','evaluator')]]
    for row in all_inputs:
        st=ordinary(row['path']).lstat();need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and st.st_size==row['bytes'],'ordinary exact-size named scientific input')
    need(not any(root.is_relative_to(ordinary(row['path'])) or ordinary(row['path']).is_relative_to(root) for row in all_inputs),'scientific inputs outside fresh writable output')
    return request,child,provenance,selected


def actor_for(request,child,provenance):
    root=Path(request['output_root']);source=Path(request['adapter_source']['path']).parent
    leaves=[*child['predictions'].values(),*child['freezes'].values(),*[child[k] for k in ('panel','protocol','historical_calibration','target','evaluator')]]
    paths=[str(source),request['child_request']['path'],*[row['path'] for row in leaves]]
    readonly=list(dict.fromkeys(paths));endpoint=absolute(request['socket'][7:])
    need(not any(endpoint.is_relative_to(absolute(p)) for p in readonly),'no Docker endpoint exposed to historical grader')
    image=provenance['image']
    actor={'role':'grade','token':request['token'],'operation_id':'smc-historical-reference-grade-'+request['token'],
           'image_id':image['Id'],'architecture':image['Architecture'],'image_labels':image['Config']['Labels'],
           'container_base_labels':provenance['container_base_labels'],'image_environment':image['Config']['Env'],
           'entrypoint':reference(source/'historical_grade_child.py'),
           'arguments':['--request',request['child_request']['path'],'--sha256',request['child_request']['sha256']],
           'workdir':str(root/'report'),'scratch_dir':'/tmp','uid':0,'gid':0,
           'readonly_mounts':[{'source':p,'destination':p} for p in readonly],
           'writable_mounts':[{'source':str(root/'report'),'destination':str(root/'report')}]}
    private=[row['path'] for row in [*child['predictions'].values(),child['target'],child['evaluator']]]
    validate_actor(actor,private)
    return actor,private


def check_daemon(owner,deadline):
    fmt='{"ID":{{json .ID}},"OSType":{{json .OSType}},"Architecture":{{json .Architecture}},"CgroupDriver":{{json .CgroupDriver}},"CgroupVersion":{{json .CgroupVersion}}}'
    result=owner.cli(['info','--format',fmt],deadline,'daemon_identity');validate_process(result)
    need(decode(result['stdout'])==DAEMON,'same current selected daemon endpoint and cgroup metadata')
    result=owner.cli(['version','--format','{{json .Server}}'],deadline,'daemon_version');validate_process(result)
    value=decode(result['stdout']);need(type(value) is dict and {k:value.get(k) for k in VERSION}==VERSION,'exact complete server Version/API/OS/Arch projection')


def validate_image_config(config,retained_config,allowed_defaults,expected_semantic_config):
    """Only the nine source-bound false/empty defaults may be absent."""
    defaults={'AttachStderr':False,'AttachStdin':False,'AttachStdout':False,
              'Domainname':'','Hostname':'','Image':'','OpenStdin':False,'StdinOnce':False,'Tty':False}
    need(all(type(value) is dict for value in (config,retained_config,allowed_defaults,expected_semantic_config)),
         'exact image Config and declared policy objects')
    # Canonical JSON preserves scalar types, unlike Python's False == 0.
    need(encoded(allowed_defaults)==encoded(defaults),'exact nine typed declared Config defaults')
    need(all(key not in retained_config or encoded(retained_config[key])==encoded(value)
             for key,value in defaults.items()),'retained present defaults have exact types and values')
    need(encoded({**allowed_defaults,**retained_config})==encoded(expected_semantic_config),
         'declared semantic Config joins retained immutable Config')
    need(encoded({**allowed_defaults,**config})==encoded(expected_semantic_config),
         'exact semantic Config; only declared default omissions permitted')


def inspect_image(owner,provenance,deadline):
    fmt='{"Id":{{json .Id}},"Os":{{json .Os}},"Architecture":{{json .Architecture}},"Parent":{{json .Parent}},"RootFS":{{json .RootFS}},"Size":{{json .Size}},"Config":{{json .Config}}}'
    result=owner.cli(['image','inspect','--format',fmt,IMAGE_ID],deadline,'historical_image_identity');validate_process(result)
    expected=provenance['image'];observed=decode(result['stdout'])
    fields=('Id','Os','Architecture','Parent','RootFS','Size')
    need(type(observed) is dict and set(observed)==set(fields)|{'Config'}
         and encoded({k:observed[k] for k in fields})==encoded({k:expected[k] for k in fields}),
         'exact typed immutable selected image/parent/layers/size; no undeclared fields')
    validate_image_config(observed['Config'],expected['Config'],
                          provenance['allowed_omitted_config_defaults'],provenance['expected_semantic_config'])


def validate_report(report,child,child_request_sha256):
    """Authenticate complete score metadata only; never open scientific arrays."""
    arms=('causal','noncausal');metrics={'co-bps','vel R2','psth R2','fp-bps'}
    keys={'schema','status','role','request_sha256','source','barrier','started','arms','historical_calibration',
          'dependency_versions','historical_dependency_versions','intentional_environment_variant','full_four_vectors',
          'historical_noncausal_supervisor_success','new_inference_executed','participant_episode_executed','AI_trial_executed',
          'scientific_equivalence','reproduction_claim','improvement_claim','SOTA_claim','printed_checkpoint_row_linkage_established',
          'supervised_completion_qualified_by_this_child','target_exposure','interpretation'}
    need(type(report) is dict and set(report)==keys
         and report['schema']=='smc_historical_reference_score_qualification_v1'
         and report['status']=='both_original_predictions_scored'
         and report['role']=='historical_current_released_checkpoint_calibration_grader_compatibility'
         and report['request_sha256']==child_request_sha256 and report['source']==child['source']
         and report['historical_calibration']==child['historical_calibration']
         and set(report['arms'])==set(arms) and report['full_four_vectors'] is True,'complete typed historical report')
    false_keys=('historical_noncausal_supervisor_success','new_inference_executed','participant_episode_executed',
                'AI_trial_executed','reproduction_claim','improvement_claim','SOTA_claim',
                'printed_checkpoint_row_linkage_established','supervised_completion_qualified_by_this_child')
    need(all(report[k] is False for k in false_keys) and report['scientific_equivalence'] is None
         and report['target_exposure']=='public_original_test_targets_released_2026_01',
         'historical-only scope and old failed supervision remain unchanged')
    versions={'numpy':'1.26.3','scipy':'1.12.0','scikit-learn':'1.5.0','h5py':'3.10.0'}
    need(report['dependency_versions']==versions and report['intentional_environment_variant']==
         {'package':'h5py','historical':'3.11.0','selected':'3.10.0'},'explicit selected numerical environment variant')
    root=Path(child['output_root']);need(report['barrier']['path']==str(root/'BOTH_SNAPSHOTS.json')
         and report['started']['path']==str(root/'STARTED.json'),'exact historical barrier and start paths')
    barrier=decode(checked(report['barrier']));started=decode(checked(report['started']))
    need(started=={'schema':'smc_historical_score_started_v1','request_sha256':child_request_sha256,
         'reference_only':True,'inference_executed':False},'actual historical-only child start')
    need(set(barrier)=={'schema','request_sha256','snapshots','both_complete_original_freezes_validated','target_payload_accessed','source'}
         and barrier['schema']=='smc_historical_both_snapshots_v1' and barrier['request_sha256']==child_request_sha256
         and barrier['source']==child['source'] and set(barrier['snapshots'])==set(arms)
         and barrier['both_complete_original_freezes_validated'] is True and barrier['target_payload_accessed'] is False,
         'both original predictions frozen before target payload access')
    calibration=decode(checked(child['historical_calibration']))
    source=decode(checked(child['source']))
    for arm in arms:
        row=report['arms'][arm];snapshot=barrier['snapshots'][arm];descriptor(snapshot)
        need(set(row)=={'metrics','historical_metrics','signed_delta_from_historical','historical_score_sha256',
             'historical_supervision','snapshot','score_report'} and row['snapshot']==snapshot
             and snapshot['path']==str(root/'snapshots'/(arm+'.h5'))
             and {k:snapshot[k] for k in ('bytes','sha256')}=={k:child['predictions'][arm][k] for k in ('bytes','sha256')},
             'exact complete snapshot identities for both historical references')
        for key in ('metrics','historical_metrics','signed_delta_from_historical'):
            need(set(row[key])==metrics and all(type(v) in (int,float) and math.isfinite(v) for v in row[key].values()),
                 'complete finite four-metric vectors; no selective omission')
        old=calibration['arms'][arm]
        need(row['historical_metrics']==old['observed_metrics'] and row['historical_score_sha256']==old['score_report_sha256']
             and row['historical_supervision']==old['scoring_execution']
             and report['historical_dependency_versions'][arm]==old['scoring_dependency_versions']
             and row['signed_delta_from_historical']=={k:row['metrics'][k]-old['observed_metrics'][k] for k in metrics},
             'descriptive complete deltas and original supervision provenance')
        need(row['score_report']['path']==str(root/(arm+'-score.json')),'exact original arm score metadata path')
        score=decode(checked(row['score_report']));freeze=decode(checked(child['freezes'][arm]))
        need(score['schema']=='smc_nlb_operator_score_v1' and score['arm']==arm and score['role']=='author_calibration'
             and score['method_id']==freeze['method_id'] and score['metrics']==row['metrics']
             and score['submission_sha256']==child['predictions'][arm]['sha256']
             and score['prediction_freeze_sha256']==child['freezes'][arm]['sha256']
             and score['panel_manifest_sha256']==child['panel']['sha256'] and score['protocol_sha256']==child['protocol']['sha256']
             and score['reference_panel_sha256']==source['files']['reference_panel.json']['sha256']
             and score['scorer_sha256']==child['evaluator']['sha256'] and score['target_sha256']==child['target']['sha256']
             and score['dependency_versions']==versions,'actual unchanged scorer arm and scientific identity joins')
    return report


def run_grade(request_path,request_sha256):
    """Exactly one child and one CPU/wall envelope across both reference arms."""
    start=time.monotonic();work_end=start+WORK_SECONDS;final_end=work_end+CLEANUP_SECONDS
    request,child,provenance,request_descriptor=inspect_request(request_path,request_sha256)
    root=ordinary(request['output_root'])
    checked(request['docker'],64*1024**2)
    need(stat.S_ISSOCK(ordinary(request['socket'][7:]).lstat().st_mode),'ordinary selected Docker socket')
    own=load_source(Path(__file__).parent/'owned_exit.py',HELPERS['owned_exit.py'],'_smc_historical_owned_exit')
    capture=load_source(Path(__file__).parent/'bounded_capture.py',HELPERS['bounded_capture.py'],'_smc_historical_capture')
    own.preflight();need(signal.getitimer(signal.ITIMER_REAL)==(0.0,0.0),'no existing host alarm')
    previous=signal.getsignal(signal.SIGALRM)
    def expired(signum,frame):raise TimeoutError('whole historical grade wall ceiling')
    signal.signal(signal.SIGALRM,expired);signal.setitimer(signal.ITIMER_REAL,max(.001,final_end-time.monotonic()))
    owner=None;built=actor=None;cid=None;intended=False;closed={'intended':False,'container_absent':True};error=None;report_descriptor=None
    try:
        root.mkdir(mode=0o700)
        for name in ('calls','report','docker-config'):(root/name).mkdir(mode=0o700)
        write(root/'HOST_REQUEST.json',request)
        owner=OwnedProcesses({'output':str(root),'docker':request['docker'],'socket':request['socket']},own,capture,start)
        actor,private=actor_for(request,child,provenance);built=build_create(actor,private)
        need(time.monotonic()+10<work_end,'remaining historical score work window')
        check_daemon(owner,work_end);inspect_image(owner,provenance,work_end)
        need(owner.inspect(built['name'],work_end) is None,'fresh exact historical container name')
        write(root/'CREATE_INTENT.json',{'actor':actor,'argv':built['argv']});intended=True
        result=owner.cli(built['argv'],work_end,'create_historical_grade');validate_process(result)
        need(re.fullmatch('[a-f0-9]{64}',result['stdout'].strip()),'strict acknowledged historical CID');cid=result['stdout'].strip()
        value=owner.inspect(cid,work_end)
        need(verify_container(value,actor,built)==cid and value['State']['Status']=='created','exact whole-job grade profile before start')
        result=owner.cli(['container','start',cid],work_end,'start_historical_grade');validate_process(result);need(result['stdout'].strip()==cid,'exact historical CID started')
        result=owner.cli(['container','wait',cid],work_end,'wait_historical_grade',WORK_SECONDS);validate_process(result);need(result['stdout'].strip()=='0','successful single child for both scores')
        value=owner.inspect(cid,work_end)
        need(verify_container(value,actor,built)==cid and value['State']['Status']=='exited'
             and value['State']['Running'] is False and value['State']['ExitCode']==0
             and value['State']['OOMKilled'] is False and not value['State']['Error'],'successful whole historical scorer without OOM')
        report_descriptor=reference(Path(child['output_root'])/'REPORT.json')
        validate_report(decode(checked(report_descriptor)),child,request['child_request']['sha256'])
    except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)[:1024]}
    finally:
        try:
            if owner is not None and built is not None:
                closed=cleanup_actor(owner,types.SimpleNamespace(verify_container=verify_container),actor,built,cid,intended,min(final_end-5,time.monotonic()+55))
            elif intended:closed={'container_absent':False,'container_id':cid,'error':'unresolved creation custody'}
        except BaseException as exc:closed={'container_absent':False,'container_id':cid,'error':{'type':type(exc).__name__,'message':str(exc)[:1024]}}
        try:
            calls=[] if owner is None else [decode(checked(row)) for row in owner.calls];outcome=completion(error,closed,calls)
            result={'schema':'smc_historical_grade_host_result_v1',**outcome,'error':error,'closed':closed,
                    'request':request_descriptor,'child_request':request['child_request'],'image_id':IMAGE_ID,
                    'source':source_selection(),'provenance':request['provenance'],
                    'prior_qualification_scope':provenance['prior_scope'],'original_image_build_success':False,
                    'participant_execution_performed':False,'original_inference_owner_reconstructed':False,
                    'both_historical_references_share_one_child_and_budget':True,
                    'bounds':{'memory_bytes':GRADE_MEMORY,'cpu_soft_seconds':CPU_SOFT,'cpu_hard_seconds':CPU_HARD,'work_seconds':WORK_SECONDS,'cleanup_seconds':CLEANUP_SECONDS,'threads':1},
                    'calls':[] if owner is None else owner.calls,'report':report_descriptor if outcome['success'] else None,
                    'elapsed_seconds':time.monotonic()-start}
            need(time.monotonic()<final_end,'final evidence inside whole work+cleanup envelope');write(root/'RESULT.json',result)
        finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',required=True);p.add_argument('--sha256',required=True);a=p.parse_args()
    result=run_grade(a.request,a.sha256)
    raise SystemExit(0 if result['success'] else 1)


if __name__=='__main__':main()
