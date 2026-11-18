"""Fixed synthetic Docker qualification inputs; never executed on the host."""
import hashlib
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


OBSERVATION = canonical({'schema': 'dosei_runtime_generated_observation_v1',
                         'generated_only': True, 'values': [0, 1, -1, 0]})
OBSERVATION_SHA256 = hashlib.sha256(OBSERVATION).hexdigest()
CASE_ID = hashlib.sha256(b'dosei-generated-runtime-qualification-v1').hexdigest()
CANARY = b'GENERATED_HOST_ONLY_DOSEI_CANARY_v1\n'
NAMES = ('runtime', 'readonly_scratch', 'fresh_scratch', 'nonzero', 'flood', 'deadline')


def _legacy_programs(host_canary_path, host_socket_path):
    if not all(type(p) is str and p.startswith('/') and len(p) <= 2048
               and not any(c in p for c in '\r\n\x00') for p in (host_canary_path, host_socket_path)):
        raise ValueError('fixed absolute qualification paths required')
    preamble = '''import resource
resource.setrlimit(resource.RLIMIT_CPU,(2,3))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
import hashlib,json,os,sys
def emit(value):
    print(json.dumps(value,sort_keys=True,separators=(',',':')),flush=True)
observation=open('/input/observation.json','rb').read(65537)
digest=hashlib.sha256(observation).hexdigest()
'''
    runtime = preamble + '''import numpy as np,socket
np.linalg.svd(np.eye(2))
routes=open('/proc/net/route','r').read(65537).splitlines()[1:]
default_route=any(line.split()[1]=='00000000' for line in routes if len(line.split())>1)
connection=socket.socket(socket.AF_INET,socket.SOCK_STREAM);connection.settimeout(0.2)
try:
    connectivity_errno=connection.connect_ex(('192.0.2.1',9))
finally:connection.close()
interface_names=sorted(name for index,name in socket.if_nameindex())
sysfs_entries=[]
with os.scandir('/sys/class/net') as directory:
    for entry in directory:
        if len(sysfs_entries)>=64 or not 0<len(entry.name.encode('utf-8'))<=128:
            raise ValueError('bounded sysfs diagnostic exceeded')
        sysfs_entries.append(entry.name)
emit({'case':'runtime','observation_sha256':digest,'uid':os.getuid(),'gid':os.getgid(),
      'python':sys.version.split()[0],'numpy':np.__version__,'executable':sys.executable,
      'cwd':os.getcwd(),'environment':dict(os.environ),
      'network_interfaces':interface_names,'network_interfaces_source':'socket.if_nameindex',
      'sysfs_directory_entries':sorted(sysfs_entries),
      'default_ipv4_route':default_route,'test_net_connect_errno':connectivity_errno,
      'thread_count':len(os.listdir('/proc/self/task')),
      'input_files':sorted(os.listdir('/input'))})
'''
    inaccessible = ['/var/run/docker.sock', '/run/docker.sock', '/run/containerd/containerd.sock',
                    '/run/podman/podman.sock', '/root/.aws/credentials', '/root/.config/gcloud',
                    '/input/other-case.json', host_canary_path, host_socket_path]
    readonly = preamble + 'paths=' + repr(inaccessible) + '\n' + '''denied={}
for path in ['/input/observation.json','/input/program.py','/dosei-qualification-write']:
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT,0o600)
    except OSError as error:
        denied[path]=error.errno
    else:
        os.close(fd);denied[path]=None
access={}
for path in paths:
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
    except OSError as error:
        access[path]={'accessible':False,'errno':error.errno}
    else:
        os.close(fd);access[path]={'accessible':True,'errno':None}
scratch={}
for path in ['/tmp/dosei-qualification-marker','/work/dosei-qualification-marker']:
    with open(path,'xb') as handle:handle.write(b'generated-scratch')
    scratch[path]=open(path,'rb').read()==b'generated-scratch'
emit({'case':'readonly_scratch','observation_sha256':digest,'write_denials':denied,
      'unmounted_paths':access,'scratch_written':scratch})
'''
    fresh = preamble + '''emit({'case':'fresh_scratch','observation_sha256':digest,
      'prior_scratch_absent':{p:not os.path.exists(p) for p in
         ['/tmp/dosei-qualification-marker','/work/dosei-qualification-marker']},
      'input_files':sorted(os.listdir('/input'))})
'''
    nonzero = preamble + "emit({'case':'nonzero','observation_sha256':digest,'intentional_exit':23})\nsys.exit(23)\n"
    flood = preamble + "emit({'case':'flood','observation_sha256':digest})\npayload=memoryview(b'F'*(2097152+8192))\nwhile payload:payload=payload[os.write(1,payload):]\n"
    deadline = preamble + "emit({'case':'deadline','observation_sha256':digest})\nimport time\ntime.sleep(120)\n"
    result = dict(zip(NAMES, (runtime, readonly, fresh, nonzero, flood, deadline)))
    if sum(len(p.encode('utf-8')) for p in result.values()) + 3*len(OBSERVATION) + len(CANARY) > 65536:
        raise ValueError('generated source and staging byte bound exceeded')
    return result


def marker(name):
    if name not in NAMES: raise ValueError('unknown generated case')
    return canonical({'case': name, 'observation_sha256': OBSERVATION_SHA256}) + b'\n'


def validate_normal(name, result, *, policy, profile, canary_path, socket_path):
    """Fixed-source output checks complement authoritative daemon inspection."""
    if type(result) is not dict or set(result) != {'status', 'text'} or type(result['text']) is not str:
        raise ValueError('typed candidate result required')
    expected_status = 'participant_error' if name == 'nonzero' else 'ok'
    if result['status'] != expected_status or len(result['text'].encode('utf-8')) > 16384:
        raise ValueError('candidate status or output bound differs')
    value = policy.decode(result['text'].encode('utf-8'))
    if (type(value) is not dict or value.get('case') != name or
            value.get('observation_sha256') != OBSERVATION_SHA256):
        raise ValueError('mounted observation output binding differs')
    if name == 'runtime':
        expected = dict(item.split('=', 1) for item in policy.expected_environment(profile))
        environment = value.get('environment')
        if type(environment) is not dict: raise ValueError('effective environment absent')
        # Docker may add only these container-local defaults. No host environment is admitted.
        extras = set(environment)-set(expected)
        if extras-set(('HOME', 'HOSTNAME')) or any(environment.get(k) != v for k,v in expected.items()):
            raise ValueError('unexpected effective candidate environment')
        if 'HOME' in extras and (type(environment['HOME']) is not str or
                not environment['HOME'].startswith('/') or len(environment['HOME']) > 256 or
                any(c in environment['HOME'] for c in '\r\n\x00')):
            raise ValueError('invalid container-local HOME default')
        if 'HOSTNAME' in extras and (type(environment['HOSTNAME']) is not str or
                not 1 <= len(environment['HOSTNAME']) <= 64 or
                any(c not in '0123456789abcdef' for c in environment['HOSTNAME'])):
            raise ValueError('unexpected container hostname')
        exact = {'uid':65534,'gid':65534,'python':'3.12.8','numpy':'2.2.6',
                 'executable':'/usr/local/bin/python3','cwd':'/work',
                 'network_interfaces':['lo'],'default_ipv4_route':False,'thread_count':1,
                 'input_files':['observation.json','program.py']}
        for key,wanted in exact.items():
            if type(value.get(key)) is not type(wanted) or value[key] != wanted:
                raise ValueError('effective runtime differs: '+key)
        if type(value.get('test_net_connect_errno')) is not int or value['test_net_connect_errno'] not in (101,113):
            raise ValueError('external numeric connectivity refusal not observed')
        if value.get('network_interfaces_source') != 'socket.if_nameindex':
            raise ValueError('namespace interface enumeration source differs')
        diagnostic = value.get('sysfs_directory_entries')
        if (type(diagnostic) is not list or len(diagnostic)>64 or
                any(type(name) is not str or not 0<len(name.encode('utf-8'))<=128 or
                    any(c in name for c in '/\x00') for name in diagnostic) or
                diagnostic != sorted(set(diagnostic))):
            raise ValueError('bounded sysfs diagnostic differs')
        if set(value) != set(exact)|{'case','observation_sha256','environment','test_net_connect_errno',
                                    'network_interfaces_source','sysfs_directory_entries'}:
            raise ValueError('unexpected runtime report fields')
    elif name == 'readonly_scratch':
        denied = value.get('write_denials')
        if (type(denied) is not dict or set(denied) !=
                {'/input/observation.json','/input/program.py','/dosei-qualification-write'} or
                any(type(v) is not int or v not in (13,30) for v in denied.values())):
            raise ValueError('read-only write attempt was not refused')
        paths = {'/var/run/docker.sock','/run/docker.sock','/run/containerd/containerd.sock',
                 '/run/podman/podman.sock','/root/.aws/credentials','/root/.config/gcloud',
                 '/input/other-case.json',canary_path,socket_path}
        access = value.get('unmounted_paths')
        if type(access) is not dict or set(access) != paths:
            raise ValueError('unmounted path observations incomplete')
        for item in access.values():
            if (type(item) is not dict or set(item) != {'accessible','errno'} or
                    item['accessible'] is not False or type(item['errno']) is not int or
                    item['errno'] not in (2,13,20)):
                raise ValueError('unmounted path unexpectedly accessible')
        if value.get('scratch_written') != {'/tmp/dosei-qualification-marker':True,
                '/work/dosei-qualification-marker':True} or any(type(v) is not bool for v in value['scratch_written'].values()):
            raise ValueError('allowed scratch write missing')
        if set(value) != {'case','observation_sha256','write_denials','unmounted_paths','scratch_written'}:
            raise ValueError('unexpected readonly report fields')
    elif name == 'fresh_scratch':
        if (value != {'case':name,'observation_sha256':OBSERVATION_SHA256,
                      'prior_scratch_absent':{'/tmp/dosei-qualification-marker':True,
                                              '/work/dosei-qualification-marker':True},
                      'input_files':['observation.json','program.py']} or
                any(type(v) is not bool for v in value['prior_scratch_absent'].values())):
            raise ValueError('fresh scratch or case scope differs')
    elif name == 'nonzero':
        if value != {'case':name,'observation_sha256':OBSERVATION_SHA256,'intentional_exit':23} or type(value['intentional_exit']) is not int:
            raise ValueError('intentional candidate error differs')
    else: raise ValueError('normal-case validator scope')
    return value


PROBE_SHA256 = 'f513ed96f8598d5693fa2dc4e2589d18bc5b92f14ea6d88be7f58311e76f3848'
RUNTIME_CAP = 16384
PROBE_CAP = 262144
ENVELOPE_CAP = 524288


def programs(host_canary_path, host_socket_path, *, probe_source):
    """Construct fixed candidate bytes; never compile or run them on the host."""
    if (type(probe_source) is not bytes or len(probe_source) != 20443 or
            hashlib.sha256(probe_source).hexdigest() != PROBE_SHA256):
        raise ValueError('exact embedded probe source required')
    result = _legacy_programs(host_canary_path, host_socket_path)
    runtime = result['runtime']
    if runtime.count("emit({'case':'runtime'") != 1:
        raise ValueError('fixed runtime emission seam differs')
    runtime = runtime.replace("emit({'case':'runtime'", "runtime_output=({'case':'runtime'", 1)
    # One candidate CPU allowance and one wall deadline cover both components.
    prefix = '''import signal
def wall_expired(*_):raise TimeoutError('fresh_runtime_wall_deadline')
signal.signal(signal.SIGALRM,wall_expired)
signal.setitimer(signal.ITIMER_REAL,20)
'''
    tail = '\nprobe_source=' + repr(probe_source) + '\n' + '''
probe_sha=hashlib.sha256(probe_source).hexdigest()
probe_namespace={'__name__':'fixed_embedded_network_probe'}
exec(compile(probe_source,'/input/embedded-network-probe.py','exec'),probe_namespace)
network_state=probe_namespace['run_probe'](
    socket_factory=lambda:socket.socket(socket.AF_NETLINK,socket.SOCK_RAW,0),
    if_nameindex=socket.if_nameindex,read_status=probe_namespace['live_status'],
    uname=lambda:tuple(os.uname()),clock=probe_namespace['time'].monotonic)
def encoded(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
if len(encoded(runtime_output))+1>16384 or len(encoded(network_state))+1>262144:
    raise ValueError('fresh runtime component output cap')
with open('/input/program.py','rb') as handle:program_bytes=handle.read(65537)
if len(program_bytes)>65536:raise ValueError('complete program source cap')
envelope={'schema':'dosei_fresh_runtime_observation_v1','case':'runtime',
    'observation_sha256':digest,'program_sha256':hashlib.sha256(program_bytes).hexdigest(),
    'embedded_probe_sha256':probe_sha,'runtime':runtime_output,'network_state':network_state}
output=encoded(envelope)+b'\\n'
if len(output)>524288:raise ValueError('fresh runtime output cap')
sys.stdout.buffer.write(output);sys.stdout.buffer.flush()
signal.setitimer(signal.ITIMER_REAL,0)
if not network_state.get('collection_complete'):raise SystemExit(1)
'''
    result['runtime'] = prefix + runtime + tail
    if sum(len(p.encode('utf-8')) for p in result.values()) + 3*len(OBSERVATION) + len(CANARY) > 65536:
        raise ValueError('complete generated staging bound exceeded')
    return result


def validate_runtime_component(value, *, policy, profile):
    """Same runtime checks except the old literal interface-name criterion.

    Interface names remain bounded observations and must later join the fresh
    parsed link dump. This function alone cannot qualify the runtime control.
    """
    if type(value) is not dict:
        raise ValueError('runtime object required')
    if value.get('case') != 'runtime' or value.get('observation_sha256') != OBSERVATION_SHA256:
        raise ValueError('mounted observation output binding differs')
    if len(canonical(value))+1 > RUNTIME_CAP:
        raise ValueError('runtime component cap')
    expected = dict(item.split('=', 1) for item in policy.expected_environment(profile))
    environment = value.get('environment')
    if type(environment) is not dict: raise ValueError('effective environment absent')
    extras = set(environment)-set(expected)
    if extras-set(('HOME', 'HOSTNAME')) or any(environment.get(k) != v for k,v in expected.items()):
        raise ValueError('unexpected effective candidate environment')
    if 'HOME' in extras and (type(environment['HOME']) is not str or
            not environment['HOME'].startswith('/') or len(environment['HOME']) > 256 or
            any(c in environment['HOME'] for c in '\r\n\x00')):
        raise ValueError('invalid container-local HOME default')
    if 'HOSTNAME' in extras and (type(environment['HOSTNAME']) is not str or
            not 1 <= len(environment['HOSTNAME']) <= 64 or
            any(c not in '0123456789abcdef' for c in environment['HOSTNAME'])):
        raise ValueError('unexpected container hostname')
    exact = {'uid':65534,'gid':65534,'python':'3.12.8','numpy':'2.2.6',
             'executable':'/usr/local/bin/python3','cwd':'/work',
             'default_ipv4_route':False,'thread_count':1,
             'input_files':['observation.json','program.py']}
    for key,wanted in exact.items():
        if type(value.get(key)) is not type(wanted) or value[key] != wanted:
            raise ValueError('effective runtime differs: '+key)
    if type(value.get('test_net_connect_errno')) is not int or value['test_net_connect_errno'] not in (101,113):
        raise ValueError('external numeric connectivity refusal not observed')
    if value.get('network_interfaces_source') != 'socket.if_nameindex':
        raise ValueError('namespace interface enumeration source differs')
    for key, maximum in (('network_interfaces',15),('sysfs_directory_entries',128)):
        diagnostic = value.get(key)
        if (type(diagnostic) is not list or len(diagnostic)>64 or
                any(type(name) is not str or not 0<len(name.encode('utf-8'))<=maximum or
                    any(c in name for c in '/\x00') for name in diagnostic) or
                diagnostic != sorted(set(diagnostic))):
            raise ValueError('bounded interface diagnostic differs')
    if set(value) != set(exact)|{'case','observation_sha256','environment','test_net_connect_errno',
                                'network_interfaces','network_interfaces_source','sysfs_directory_entries'}:
        raise ValueError('unexpected runtime report fields')
    return value
