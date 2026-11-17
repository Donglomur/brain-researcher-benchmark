"""C13--C20: full captured callers, explicit inert native/provider leaves.

This is harness source, not execution evidence. Production modules are supplied
by the parent's authenticated whole-module loader. No numerical module is used.
"""
import base64
import io
import json
import time
from pathlib import Path, PurePosixPath
from types import SimpleNamespace
from contextlib import ExitStack


class Proxy:
    def __init__(self, original, **values):
        self.original, self.values = original, values
    def __getattr__(self, name):
        if name in self.values:
            return self.values[name]
        return getattr(self.original, name)


def module(ctx, name):
    return ctx.modules['n090native.' + name]


def budget(ctx, events=None, read=4 * 2**20, write=2**20):
    common = module(ctx, 'common')
    original = common.Budget(read, write, time.monotonic() + 120)
    if events is None:
        return original
    class Traced:
        end = original.end
        def read(self, n):
            events.append(('read', n)); original.read(n)
        def write(self, n):
            events.append(('write', n)); original.write(n)
        def tick(self):
            original.tick()
        def report(self):
            return original.report()
    return Traced()


def put(ctx, root, name, body):
    path = root / name
    ctx.put(path, body)
    return path


def contract(ctx, root):
    common = module(ctx, 'common')
    ranks = b''.join(base64.b64encode(bytes([i])) + b' ' + str(i).encode() + b'\n'
                     for i in range(256)) + b'YWI= 256\n'
    members = {}
    for name, body in [('ranks.txt', ranks), ('implementation.txt', b'inert byte-BPE fixture; never imported\n'),
                       ('equivalence.txt', b'invented evidence; not real-model qualification\n')]:
        put(ctx, root, name, body)
        members[name] = {'path': name, **common.pin(body)}
    value = {'schema': 'n090-selected-byte-bpe-framing-v1', 'model': 'inert-model',
             'encoding': 'invented-256-byte-alphabet', 'ranks': members['ranks.txt'],
             'implementation': members['implementation.txt'],
             'equivalence_evidence': members['equivalence.txt'],
             'request_framing_tokens': 2, 'message_framing_tokens': 3}
    raw = common.encoded(value)
    path = put(ctx, root, 'contract.json', raw)
    return {'path': str(path), **common.pin(raw)}


def provider_value(**changes):
    value = {'model': 'inert-model', 'status': 'completed', 'object': 'response',
             'usage': {'input_tokens': 9, 'output_tokens': 2, 'total_tokens': 11},
             'output': [{'type': 'message', 'content': []}]}
    value.update(changes)
    return value


def response_record(common, value, pid=321, **transport_changes):
    transport = {'attempted': True, 'status': 200, 'eof': True,
                 'response_closed': True, 'connection_closed': True, 'retries': 0}
    transport.update(transport_changes)
    reply = {'transport': transport, 'raw_base64': base64.b64encode(common.encoded(value)).decode(),
             'first_error': None, 'secondary': []}
    return {'pid': pid, 'stdout_base64': base64.b64encode(common.encoded(reply)).decode(),
            'stderr_base64': '', 'exit_code': 0}


def broker_fixture(ctx, name):
    common = module(ctx, 'common'); broker = module(ctx, 'broker')
    root = ctx.fixture(name); events = []
    selected = contract(ctx, root)
    cfg = {'model': 'inert-model', 'credential': {'path': 'NEVER_OPENED'},
           'input_tokens': 64, 'output_tokens': 16, 'request_bytes': 4096,
           'response_bytes': 4096, 'max_calls': 2, 'input_contract': selected}
    owner = SimpleNamespace(cfg={'provider': cfg}, root=root)
    iso = SimpleNamespace(owner=owner, root=root, token='a' * 64,
                          normal_end=time.monotonic() + 60, cleanup_end=time.monotonic() + 90,
                          limits={'tool_calls': 2, 'model_tokens': 160},
                          actor=budget(ctx), budget=budget(ctx, events), cleanup_budget=budget(ctx),
                          cgroup=SimpleNamespace(path=Path('/sys/fs/cgroup/n090-inert'), monitor=lambda: None))
    obj = broker.Broker(iso)
    return obj, iso, events


def inert_group(events):
    class Group:
        def __init__(self, root, name, account, limits):
            self.path = Path(root) / name; self.budget = account; self.identity = None
        def create(self, branch=True):
            events.append(('create', self.path.name, branch)); self.identity = (11, 12); return self
        def kill(self):
            events.append(('kill', self.path.name))
        def finish(self):
            events.append(('finish', self.path.name))
    return Group


def C13(ctx):
    broker = module(ctx, 'broker'); tokens = module(ctx, 'token_budget')
    obj, iso, events = broker_fixture(ctx, 'C13-text-contract')
    effects = []
    iso.owner.command = lambda *a, **k: effects.append('ILLEGAL_DISPATCH')
    for typ in ('input_file', 'input_image', 'item_reference', 'tool_reference'):
        ctx.reject(lambda typ=typ: obj.dispatch({'kind': 'model', 'input': [
            {'role': 'user', 'content': [{'type': typ, 'value': 'invented'}]}]}),
            ValueError, 'text-only messages')
    ctx.reject(lambda: obj.dispatch({'kind': 'model', 'input': [
        {'role': 'user', 'content': 'x', 'previous_response_id': 'invented'}]}),
        ValueError, 'exact role,content')
    ctx.reject(lambda: obj.dispatch({'kind': 'model', 'input': [
        {'role': 'user', 'content': 'x' * 64}]}), ValueError,
        'pre-dispatch conservative input token ceiling')
    ctx.check(obj.tokens == 0 and obj.calls == [] and effects == [],
              'invalid reference or oversized text must precede reservation and provider effect')
    result = tokens.text_input([{'role': 'user', 'content': 'ab'}],
                              iso.owner.cfg['provider']['input_contract'], iso.actor, 64, 'inert-model')
    ctx.check(result['input_token_upper_bound'] == 11 and result['text_only'] is True,
              'actual complete byte alphabet, small merge and fixed framing are parsed')
    ctx.check(result['framing_is_external_qualification'] is True,
              'invented evidence must not claim real model equivalence')


def C14(ctx):
    common = module(ctx, 'common'); broker = module(ctx, 'broker')
    variants = [
        ({'status': 'in_progress'}, {}, 'exact completed model response'),
        ({'model': 'wrong-model'}, {}, 'exact completed model response'),
        ({'usage': None}, {}, 'actual provider usage required'),
        ({'usage': {'input_tokens': 65, 'output_tokens': 0, 'total_tokens': 65}}, {}, 'usage within preselected reservation'),
        ({'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 3}}, {}, 'usage within preselected reservation'),
        ({'output': [{'type': 'web_search_call'}]}, {}, 'no hosted or unmetered tools'),
        ({}, {'eof': False}, 'actual terminal HTTP observations')]
    for index, (changes, transport, reason) in enumerate(variants):
        obj, iso, events = broker_fixture(ctx, 'C14-refusal-' + str(index))
        def command(*args, **kwargs):
            ctx.check(obj.tokens == 80 and len(obj.calls) == 1 and obj.calls[0]['result'] is None,
                      'full model reservation precedes one inert transport effect')
            events.append(('dispatch',)); return response_record(common, provider_value(**changes), **transport)
        iso.owner.command = command
        with ctx.patch(broker, Cgroup=inert_group(events), admit_placement=lambda *a: {'inert': True}):
            ctx.reject(lambda: obj.dispatch({'kind': 'model', 'input': [{'role': 'user', 'content': 'hi'}]}),
                       ValueError, reason)
        ctx.check(obj.tokens == 80 and obj.calls[0]['result'] is None,
                  'refusal preserves charged reservation and no successful result')
        ctx.check(events.index(('dispatch',)) < events.index(('kill', 'provider-1')) < events.index(('finish', 'provider-1')),
                  'actual broker always attempts independent provider retirement before response admission')
    obj, iso, events = broker_fixture(ctx, 'C14-provider-first-failure')
    first = OSError('selected inert provider failure')
    def fail(*args, **kwargs):
        ctx.check(obj.tokens == 80, 'model tokens reserved before failing dispatch'); raise first
    iso.owner.command = fail
    with ctx.patch(broker, Cgroup=inert_group(events)):
        error = ctx.reject(lambda: obj.dispatch({'kind': 'model', 'input': [{'role': 'user', 'content': 'hi'}]}),
                           common.Failure, 'raw first and secondary retained')
    ctx.check(error.first is first and obj.tokens == 80 and obj.calls[0]['result'] is None,
              'exact original provider error and nonrefunded reservation survive')
    iso.limits['model_tokens'] = 80
    ctx.reject(lambda: obj.dispatch({'kind': 'model', 'input': [{'role': 'user', 'content': 'hi'}]}),
               ValueError, 'preselected combined input/output token reservation')
    ctx.check(obj.tokens == 80 and len(obj.calls) == 1,
              'exhausted prospective model grant refuses before a second request is added')
    tool = OSError('selected inert terminal failure')
    def terminal(*args, **kwargs):
        ctx.check(obj.tools == 1, 'tool reservation precedes terminal effect'); raise tool
    iso.container_step = terminal
    error = ctx.reject(lambda: obj.dispatch({'kind': 'tool', 'command': 'inert-command'}),
                       OSError, 'selected inert terminal failure')
    ctx.check(error is tool and obj.tools == 1, 'terminal failure never refunds the selected tool call')
    iso.limits['tool_calls'] = 1
    ctx.reject(lambda: obj.dispatch({'kind': 'tool', 'command': 'inert-command'}),
               ValueError, 'preselected tool call ceiling')
    ctx.check(obj.tools == 1, 'exhausted tool grant cannot redispatch or refund')


def placement_record(common, path, identity, pid):
    return {'schema': 'n090-actual-placement-v1', 'pid': pid, 'cgroup': str(path),
            'identity': list(identity), 'moved': True,
            'readback': '0::/' + str(path.relative_to('/sys/fs/cgroup')),
            'descriptor_closure_known': True, 'first': None, 'secondary': [], 'kernel_prefix_base64': ''}


def place_main(ctx, overflow=False):
    place = module(ctx, 'place_entry'); effects = []; stderr = io.StringIO()
    class P:
        def __init__(self, value): self.value = PurePosixPath(value)
        def __str__(self): return str(self.value)
        @property
        def parents(self): return tuple(P(x) for x in self.value.parents)
        def is_symlink(self): return False
        def relative_to(self, value): return self.value.relative_to(value)
    def opened(path, flags, *args, **kwargs):
        key = str(path); effects.append(('open', key))
        return {'/sys/fs/cgroup/n090-inert': 10, 'cgroup.procs': 11,
                '/proc/self/cgroup': 12, '/fixture/placement.json': 13}[key]
    def write(fd, raw): effects.append(('write', fd, bytes(raw))); return len(raw)
    def dumps(value, **kw):
        result = json.dumps(value, **kw)
        return result + (' ' * 16385 if overflow and kw.get('sort_keys') else '')
    fakeos = Proxy(place.os, getpid=lambda: 321, open=opened,
                   fstat=lambda fd: SimpleNamespace(st_dev=11, st_ino=12),
                   write=write, read=lambda fd, n: b'0::/n090-inert\n',
                   close=lambda fd: effects.append(('close', fd)),
                   fsync=lambda fd: effects.append(('fsync', fd)),
                   execv=lambda arg, argv: effects.append(('exec', arg, tuple(argv))))
    argv = ['trusted-place.py', '/sys/fs/cgroup/n090-inert', '11', '12',
            '/fixture/placement.json', '90', '--', '/inert/python', 'provider.py']
    fakesys = Proxy(place.sys, argv=argv, flags=SimpleNamespace(isolated=1, no_site=1),
                    dont_write_bytecode=True, stderr=stderr)
    with ctx.patch(place, os=fakeos, Path=P, sys=fakesys,
                   time=SimpleNamespace(monotonic=lambda: 1), json=Proxy(json, dumps=dumps)):
        if overflow:
            error = ctx.reject(place.main, SystemExit, '1')
            record = json.loads(stderr.getvalue())
            ctx.check(error.code == 1 and record['first'] == {'where': 'placement-publication', 'type': 'ValueError'},
                      'record cap is the precise selected publication refusal')
            ctx.check(('open', '/fixture/placement.json') not in effects and not any(x[0] == 'exec' for x in effects),
                      'over16KiB record refuses before publication open and exec')
        else:
            place.main()
            ctx.check(any(x[0] == 'exec' for x in effects), 'actual placement main reaches inert exec after closure')
            written = b''.join(x[2] for x in effects if x[0] == 'write' and x[1] == 13)
            record = json.loads(written)
            ctx.check(record['moved'] and record['descriptor_closure_known'] and record['pid'] == 321,
                      'actual placement publication binds held leader and all descriptor closures')
            ctx.check([x[1] for x in effects if x[0] == 'close'] == [11, 10, 12, 13],
                      'procs, directory, readback and record descriptors close before exec')


def C15(ctx):
    common = module(ctx, 'common'); broker = module(ctx, 'broker')
    obj, iso, events = broker_fixture(ctx, 'C15-provider-placement')
    def command(argv, *args, **kwargs):
        ctx.check(('read', 8193) in events and ('write', 16416) in events,
                  'provider placement record/readback/PID transfer is precharged before dispatch')
        ctx.check(argv[1:4] == ['-I', '-S', '-B'] and argv[4].endswith('trusted-place.py')
                  and argv[10] == '--' and argv[-2].endswith('trusted-provider.py'),
                  'actual broker argv uses fixed placement then provider, without preexec callback')
        ctx.check(('create', 'provider-1', False) in events,
                  'provider is a direct-process leaf inside same invocation branch')
        record = placement_record(common, Path(argv[5]), (11, 12), 321)
        put(ctx, iso.root, Path(argv[8]).name, common.encoded(record))
        events.append(('one_inert_http_effect',))
        return response_record(common, provider_value())
    iso.owner.command = command
    with ctx.patch(broker, Cgroup=inert_group(events)):
        result = obj.dispatch({'kind': 'model', 'input': [{'role': 'user', 'content': 'hi'}]})
    ctx.check(result['kind'] == 'model_result' and obj.calls[0]['placement']['pid'] == 321,
              'actual placement validator joins command PID before model result admission')
    ctx.check(events.count(('one_inert_http_effect',)) == 1 and events[-2:] == [('kill', 'provider-1'), ('finish', 'provider-1')],
              'one transport attempt and independent leaf retirement, no retry or remote-cancel claim')
    obj, iso, events = broker_fixture(ctx, 'C15-bad-placement')
    raw_record = response_record(common, provider_value())
    def wrong(argv, *a, **k):
        put(ctx, iso.root, Path(argv[8]).name,
            common.encoded(placement_record(common, Path(argv[5]), (11, 12), 999)))
        return raw_record
    iso.owner.command = wrong
    with ctx.patch(broker, Cgroup=inert_group(events)):
        error = ctx.reject(lambda: obj.dispatch({'kind': 'model', 'input': [{'role': 'user', 'content': 'hi'}]}),
                           common.Failure, 'raw first and secondary retained')
    ctx.check(type(error.first) is ValueError and str(error.first) == 'same actual owned leader placement'
              and error.record['process'] is raw_record and obj.calls[0]['result'] is None,
              'placement refusal preserves exact command result before leaf retirement')
    ctx.check(('kill', 'provider-1') in events and ('finish', 'provider-1') in events,
              'placement failure independently attempts kill and retirement')
    place_main(ctx); place_main(ctx, overflow=True)


class VirtualPath:
    """Only cgroup paths: pure metadata map, never a real kernel path."""
    def __init__(self, value, alive): self.value = PurePosixPath(value); self.alive = alive
    def __str__(self): return str(self.value)
    def __fspath__(self): return str(self.value)
    @property
    def name(self): return self.value.name
    def __truediv__(self, name): return VirtualPath(self.value / name, self.alive)
    def exists(self): return str(self) in self.alive
    def stat(self):
        if not self.exists(): raise FileNotFoundError(str(self))
        return SimpleNamespace(st_dev=11, st_ino=12)


def recovery_fixture(ctx, name):
    common = module(ctx, 'common'); root = ctx.fixture(name); token = 'b' * 64
    folder = root / token; folder.mkdir(mode=0o700); work = folder / 'work'; work.mkdir(mode=0o700)
    campaign = 'c' * 64; cg = '/sys/fs/cgroup/inert/n090-' + token
    put(ctx, root, 'CAMPAIGN.json', common.encoded({'campaign': campaign}))
    put(ctx, folder, 'INTENT.json', common.encoded({'token': token, 'work': str(work), 'cgroup': cg}))
    cfg = {'native': {'custody_root': str(root), 'cgroup_root': '/sys/fs/cgroup/inert',
                     'provider': {'max_calls': 3, 'input_tokens': 64, 'output_tokens': 16},
                     'umount': {'path': '/inert/umount'}},
           'limits': {'actor': {'tool_calls': 2, 'model_tokens': 160}}}
    return root, folder, token, campaign, cg, cfg


def recovery_patches(ctx, alive, events, docker, kernel, finish_error=None):
    controller = module(ctx, 'controller'); owner = module(ctx, 'owner')
    def path(value):
        text = str(value)
        return VirtualPath(text, alive) if text.startswith('/sys/fs/cgroup/') else Path(value)
    class Group:
        def __init__(self, root, name, account, limits):
            self.path = VirtualPath(PurePosixPath(str(root)) / name, alive); self.identity = None
        def kill(self): events.append(('kill', str(self.path)))
        def finish(self):
            events.append(('finish', str(self.path)))
            descendants = [x for x in alive if x.startswith(str(self.path) + '/')]
            if descendants:
                if finish_error is None: raise OSError('inert unselected cgroup descendant')
                raise finish_error
            alive.remove(str(self.path)); return {'inert': True}
    stack = ExitStack()
    stack.enter_context(ctx.patch(controller, Path=path, Cgroup=Group, kernel_body=kernel))
    stack.enter_context(ctx.patch(owner.NativeOwner, docker=docker))
    return stack


def C16(ctx):
    common = module(ctx, 'common'); controller = module(ctx, 'controller')
    for unknown in (False, True):
        root, folder, token, campaign, cg, cfg = recovery_fixture(ctx, 'C16-' + str(unknown))
        put(ctx, folder, 'PROVIDER-1.json', common.encoded({'token': token, 'name': 'provider-1', 'call': 1}))
        alive = {cg, cg + '/provider-1'}
        if unknown: alive.add(cg + '/unselected-sibling')
        events = []; original = OSError('inert unselected cgroup descendant')
        def docker(self, args, *a, **kw):
            events.append(('docker', tuple(args))); return {'stdout_base64': ''}
        with recovery_patches(ctx, alive, events, docker, lambda *a: b'', original):
            if unknown:
                error = ctx.reject(lambda: controller.recovery(cfg, root, budget(ctx), time.monotonic() + 60),
                                   common.Failure, 'raw first and secondary retained')
                ctx.check(error.first is original, 'unknown descendant preserves original finish error')
            else:
                value = controller.recovery(cfg, root, budget(ctx), time.monotonic() + 60)
                ctx.check(value['intents'] == [{'token': token, 'normal_closed': False}],
                          'recovery-only closure is explicitly not a normal campaign result')
        ctx.check(events.index(('finish', cg + '/provider-1')) < events.index(('finish', cg)),
                  'actual recovery retires durable known provider leaf before parent')
        ctx.check(not any(x[0] in ('kill', 'finish') and x[1].endswith('unselected-sibling') for x in events),
                  'unselected sibling is never signalled or recursively removed')
        ctx.check((cg + '/provider-1') not in alive and (not alive if not unknown else cg in alive),
                  'known leaf closure does not silently erase unknown descendant')


def C17(ctx):
    common = module(ctx, 'common'); controller = module(ctx, 'controller')
    root, folder, token, campaign, cg, cfg = recovery_fixture(ctx, 'C17-independent-recovery')
    put(ctx, folder, 'CONTAINER-0.json', common.encoded({'token': 'wrong', 'name': 'bad'}))
    name = 'n090-' + token + '-1'
    put(ctx, folder, 'CONTAINER-1.json', common.encoded({'token': token, 'name': name}))
    events = []; count = [0]; later = OSError('selected inert final mount observation')
    def kernel(*args):
        count[0] += 1
        if count[0] == 3: raise later
        return b''
    def docker(self, args, *a, **kw):
        events.append(('docker', tuple(args)))
        if args[:1] == ['inspect']:
            body = common.encoded([{'Config': {'Labels': {'n090.invocation': token, 'n090.campaign': campaign}}}])
        elif args[:2] == ['ps', '-a'] and any(x.startswith('name=') for x in args): body = b'owned\n'
        else: body = b''
        return {'stdout_base64': base64.b64encode(body).decode()}
    with recovery_patches(ctx, set(), events, docker, kernel):
        error = ctx.reject(lambda: controller.recovery(cfg, root, budget(ctx), time.monotonic() + 60),
                           common.Failure, 'raw first and secondary retained')
    ctx.check(type(error.first) is ValueError and str(error.first) == 'exact owned container name',
              'malformed first durable intent remains actual first refusal')
    ctx.check(error.events[0][0] == 'recover-container-intent:CONTAINER-0.json'
              and error.events[-1] == ('whole-campaign-mount-absence', later),
              'first and subsequent raw recovery failures preserve exact order and identity')
    ctx.check(('docker', ('rm', '-f', name)) in events,
              'one invalid intent does not skip independently selected later container')
    ctx.check(any(x[0] == 'docker' and 'label=n090.campaign=' + campaign in x[1] for x in events),
              'failed final mount observation does not skip independent final daemon probe')


class Names:
    def __init__(self, iterator, closed): self.iterator = iter(iterator); self.closed = closed
    def __iter__(self): return self
    def __next__(self): return SimpleNamespace(name=next(self.iterator))
    def close(self): self.closed.append(True)


def root_names(extra=False):
    for i in range(76800): yield format(i, '064x')
    for i in range(76800): yield 'native-' + format(i, '064x') + '.json'
    yield from ('CAMPAIGN.json', 'captured', 'commands', 'launcher',
                'candidate-frozen_program', 'candidate-case_adaptive_equal_inputs_tools_compute',
                'trusted-provider.py', 'trusted-place.py')
    if extra: yield 'unselected-probe'


def C18(ctx):
    common = module(ctx, 'common'); controller = module(ctx, 'controller')
    for extra in (False, True):
        closed = []; account = budget(ctx, read=16 * 2**20)
        fixed = ('CAMPAIGN.json', 'captured', 'commands', 'launcher',
                 'candidate-frozen_program', 'candidate-case_adaptive_equal_inputs_tools_compute',
                 'trusted-provider.py', 'trusted-place.py')
        metadata_bytes = 76800 * (65 + 77) + sum(len(x.encode()) + 1 for x in fixed)
        ctx.charge('read', metadata_bytes)
        with ctx.patch(common, os=Proxy(common.os, scandir=lambda p: Names(root_names(extra), closed))):
            names, errors = common.bounded_names('/inert-full-roster', 153608, account)
        ctx.check(len(names) == 153608 and len(closed) == 1,
                  'complete153608 roster retained and descriptor closed, without real file population')
        ctx.check(names[0] == '0' * 64 and names[76800].startswith('native-')
                  and names[-1] == 'trusted-place.py', 'all invocation/receipt/fixed-role namespaces included')
        if extra:
            ctx.check(len(errors.events) == 1 and type(errors.events[0][1]) is ValueError
                      and str(errors.events[0][1]) == 'finite complete name inventory plus refused probe',
                      '153609th probe has exact selected inventory refusal')
        else: ctx.check(errors.events == [], 'exact complete roster has no refusal')
        ctx.check(account.reads == metadata_bytes, 'prospective synthetic-name charge matches actual managed reservations')
        del names, errors, account
    root, folder, token, campaign, cg, cfg = recovery_fixture(ctx, 'C18-per-invocation')
    closed = []; caps = []; real_scan = common.os.scandir
    def scan(path):
        if Path(path) == folder: return Names(('junk-' + str(i) for i in range(25)), closed)
        return real_scan(path)
    actual_names = common.bounded_names
    def names(path, cap, account):
        caps.append((str(path), cap)); return actual_names(path, cap, account)
    events = []
    def docker(self, args, *a, **kw): events.append(tuple(args)); return {'stdout_base64': ''}
    with recovery_patches(ctx, set(), events, docker, lambda *a: b''):
        with ctx.patch(common, os=Proxy(common.os, scandir=scan)):
            with ctx.patch(controller, bounded_names=names):
                error = ctx.reject(lambda: controller.recovery(cfg, root, budget(ctx), time.monotonic() + 60),
                                   common.Failure, 'raw first and secondary retained')
    ctx.check((str(folder), 24) in caps and type(error.first) is ValueError
              and str(error.first) == 'finite complete name inventory plus refused probe',
              'actual recovery derives6+4T+5M=24 and counts every nonmatching junk entry')


def output_fixture(ctx, name, corrupt=None):
    common = module(ctx, 'common'); native = module(ctx, 'native')
    root = ctx.fixture(name); work = root / 'work'; work.mkdir(mode=0o700)
    final = work / 'final'; final.mkdir(mode=0o700); captured = root / 'captured'; captured.mkdir(mode=0o700)
    blobs = {'source.pt': b'invented source checkpoint bytes', 'final.pt': b'invented final checkpoint bytes',
             'logical-resource.json': b'{"invented":true}\n'}
    value = {'schema': 'n090-prediction-v1', 'predictions': [],
             'source_checkpoint': common.pin(blobs['source.pt']), 'final_checkpoint': common.pin(blobs['final.pt']),
             'resource_receipt': common.pin(blobs['logical-resource.json'])}
    body = common.encoded(value)
    for filename, raw in blobs.items():
        put(ctx, final, filename, raw if filename != corrupt else b'X' + raw[1:])
    put(ctx, final, 'prediction.json', body)
    iso = native.Isolation.__new__(native.Isolation)
    iso.work = work; iso.root = root; iso.token = 'd' * 64; iso.actor = budget(ctx); iso.budget = budget(ctx)
    iso.owner = SimpleNamespace(captured=captured); iso.returned = None
    return iso, {'path': 'prediction.json', **common.pin(body)}


def C19(ctx):
    common = module(ctx, 'common')
    iso, asset = output_fixture(ctx, 'C19-complete')
    result = iso.capture_output(asset)
    ctx.check(result is iso.returned and result[1].path == 'prediction.json'
              and [x['path'] for x in iso.output_rows] == ['prediction.json', 'source.pt', 'final.pt', 'logical-resource.json'],
              'actual complete four-product capture, no checkpoint deserialization')
    for corrupt in ('final.pt', 'logical-resource.json'):
        iso, asset = output_fixture(ctx, 'C19-' + corrupt, corrupt)
        error = ctx.reject(lambda: iso.capture_output(asset), common.Failure, 'raw first and secondary retained')
        ctx.check(type(error.first) is ValueError and str(error.first) == 'selected whole content identity'
                  and error.record['consumed_prefix'].startswith(b'X'),
                  'changed exact selected product retains raw consumed prefix and pin refusal')
        ctx.check(iso.returned is None and not hasattr(iso, 'receipt'),
                  'partial copied products cannot yield actor result or native receipt')


def closed_fixture(ctx, name):
    common = module(ctx, 'common'); owner_module = module(ctx, 'owner')
    iso, asset = output_fixture(ctx, name); returned = iso.capture_output(asset)
    host = owner_module.NativeOwner.__new__(owner_module.NativeOwner)
    host.root = iso.root; host.cfg = {'image_id': 'sha256:' + 'e' * 64}; host.runtime_pin = common.pin(b'inert-runtime')
    host.budget = budget(ctx)
    iso.owner = host; iso.errors = common.Ledger(); iso.containers = []; iso.commands = []
    iso.closed = False; iso.mounted = False; iso.invocation = 'invented-invocation'; iso.uid = 100000
    iso.normal_budget = iso.budget; iso.cleanup_budget = budget(ctx); iso.normal_end = time.monotonic() + 60
    iso.cleanup_end = time.monotonic() + 90; iso.view = (iso.root / 'view', {'path': 'inert.json', **common.pin(b'view')}, ())
    iso.broker = SimpleNamespace(calls=[], receipt=lambda: {'inert': True}); events = []
    class Group:
        closed = False
        def __init__(self): self.events = []; self.budget = iso.cleanup_budget
        def kill(self): events.append('kill')
        def finish(self): events.append('finish'); self.closed = True; return {'inert': True}
    iso.cgroup = Group()
    return iso, host, returned, events


def C20(ctx):
    common = module(ctx, 'common'); native = module(ctx, 'native')
    iso, host, returned, events = closed_fixture(ctx, 'C20-positive')
    ctx.reject(lambda: host.resource_receipt(iso), ValueError, 'actual complete native retirement before receipt')
    iso.close()
    ctx.check(isinstance(iso, native.Isolation) and iso.returned is returned and events == ['kill', 'finish'],
              'actual Isolation close preserves actor result and independently retires native leaf')
    receipt = host.resource_receipt(iso)
    ctx.check(receipt is iso.receipt and (host.root / receipt.path).is_file(),
              'actual durable native receipt is emitted only after actual close path')
    # A dict is never substituted for either Isolation or held-owner result.
    ctx.check(not isinstance({'closed': True, 'receipt': 'shape'}, native.Isolation),
              'fixture does not treat receipt-shaped mapping as an Isolation proof')
    for flag in ('cgroup', 'mount', 'container', 'descriptor'):
        iso, host, returned, events = closed_fixture(ctx, 'C20-refusal-' + flag)
        iso.closed = True; iso.cgroup.closed = True
        if flag == 'cgroup': iso.cgroup.closed = False
        elif flag == 'mount': iso.mounted = True
        elif flag == 'container': iso.containers = [{'name': 'inert', 'removed': False}]
        else: iso.errors.record('selected-descriptor-close', OSError('inert descriptor uncertainty'))
        ctx.reject(lambda: host.resource_receipt(iso), ValueError, 'actual complete native retirement before receipt')
        ctx.check(not (host.root / ('native-' + iso.token + '.json')).exists() and iso.returned is returned,
                  'every selected closure uncertainty forbids receipt without destroying original result')
    iso, host, returned, events = closed_fixture(ctx, 'C20-compound-close')
    first = OSError('selected inert cgroup kill failure'); second = OSError('selected inert cgroup finish failure')
    def fail_kill(): events.append('kill'); raise first
    def fail_finish(): events.append('finish'); raise second
    iso.cgroup.kill = fail_kill; iso.cgroup.finish = fail_finish
    error = ctx.reject(iso.close, common.Failure, 'raw first and secondary retained')
    ctx.check(error.first is first and error.events == (('cgroup-kill', first), ('cgroup-finish', second))
              and iso.closed and iso.returned is returned and events == ['kill', 'finish'],
              'actual close retains first/secondary identities and tries both independent retirements')
    ctx.reject(lambda: host.resource_receipt(iso), ValueError, 'actual complete native retirement before receipt')


def run(ctx):
    for number in range(13, 21):
        name = 'C' + str(number)
        ctx.case(name, lambda name=name: globals()[name](ctx))
