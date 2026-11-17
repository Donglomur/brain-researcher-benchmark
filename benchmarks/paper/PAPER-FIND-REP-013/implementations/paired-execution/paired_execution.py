"""Purkinje paired final-program execution; no agent, Docker or scoring CLI.

Trusted owner API. Reuses the fixed protected producer and existing paired
grader; it never accepts caller-supplied numerical outputs or closure flags.
"""
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types
import uuid

TASK = 'PAPER-FIND-REP-013'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
CONTRACT = {'bytes':1720,'sha256':'294838ec512339663761aca362748b62e793f98ad1ff492c1eacd11147cfe253'}
PAIRED = ('paired_packet.py',21027,'350cf0d267df967458ea547bb0bcdf92cfb748d9157401e63b9da11243784e29')
DONORS = {
 'common':(4511,'2683ab2a3fe95b54befca2682c516c28de7c343067d022c9d84fe31a04d17747'),
 'durable_evidence':(4252,'f12894f1f200ece3c110f951e280cd22b2bcb806ebfd85c19da8530bae33b79d'),
 'docker_owner':(33811,'e440c11ed3e0fab18a2b76616f09e48f37aece74e7d83206ebb7ba35cef3d3d5'),
 'schema':(2123,'76df29fdab9d70dbcf129788c4201bf75df65c4ce9abd9bf1f5fff334cbc4538'),
 'numeric_score':(9797,'5c80e13c45d04fe7fbecc6f14e2cf2dc45f3a87bcaaf916b46cedcdcac9d732c'),
 'bundle':(2303,'99eff24a35d92b8c5b8b2260a99c9abc268769c63b1deb8214a0def79c957699'),
 'boundary':(10750,'5acd474cfca27bd706dd6b715e5c2027b6f5b2d515470fc42250d78d01b059c8'),
 'bridge':(4942,'dcc0d0b8201c687274f104ff9829876818952bebeedc220b790057b522562df4')}
_TOKEN = object()


def need(value, message):
    if not value:
        raise ValueError(message)


def pin(body):
    return {'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}


def captured_source(path, expected):
    """Read one small exact regular source; no empirical/reference body."""
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path,*path.parents)), 'ordinary_source_path')
    before = path.lstat()
    stamp = lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
         and before.st_size == expected['bytes'] <= 65536, 'source_extent')
    fd = os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        need(stamp(before) == stamp(os.fstat(fd)), 'source_open_identity')
        with os.fdopen(fd,'rb',closefd=False) as stream:
            body = stream.read(expected['bytes']+1)
        need(stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat())
             and pin(body) == expected, 'source_identity')
        return body
    finally:
        os.close(fd)


def _module_graph(bodies, paths):
    """Use authenticated existing modules, without replacing global common/schema."""
    modules = {}
    builtin_import = builtins.__import__
    def selected_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in modules:
            return modules[name]
        return builtin_import(name,globals,locals,fromlist,level)
    for name, body in bodies.items():
        # Dataclass construction needs its own temporary sys.modules entry.
        unique = '_purkinje_pair_' + uuid.uuid4().hex
        module = types.ModuleType(unique)
        module.__file__ = str(paths[name])
        module.__dict__['__builtins__'] = dict(vars(builtins),__import__=selected_import)
        sys.modules[unique] = module
        try:
            exec(compile(body,str(paths[name]),'exec'),module.__dict__)
        finally:
            del sys.modules[unique]
        modules[name] = module
    return modules


class ClosedPair:
    """Only this integration's successful two-arm producer path issues a token."""
    def __init__(self, owner, state, token):
        self._owner, self._state, self._token = owner, state, token


class PairExecutor:
    def __init__(self, *, repo, paired_root, producer_root, expected_source):
        self.source = captured_source(Path(__file__), expected_source)
        self.source_pin = pin(self.source)
        self.paired_root = Path(paired_root).absolute()
        paired_body = captured_source(self.paired_root/PAIRED[0],
                                      {'bytes':PAIRED[1],'sha256':PAIRED[2]})
        paths = {n:Path(producer_root).absolute()/(n+'.py') for n in DONORS}
        bodies = {n:captured_source(paths[n],{'bytes':p[0],'sha256':p[1]})
                  for n,p in DONORS.items()}
        self.modules = _module_graph({**bodies,'paired_packet':paired_body},
                                     {**paths,'paired_packet':self.paired_root/PAIRED[0]})
        self.C = self.modules['common']
        self.owner = self.modules['docker_owner']
        self.paired_module = self.modules['paired_packet']
        self.paired = self.paired_module.Paired(repo,self.paired_root/'CONTRACT.json',CONTRACT)
        self.bridge_body = bodies['bridge']
        self.used = False
        self.binding = {'adapter':self.source_pin,'paired_packet':pin(paired_body),
                        'contract':CONTRACT,'producer':{n+'.py':pin(b) for n,b in bodies.items()}}
        need(self.owner.IMAGE == IMAGE, 'fixed_protected_producer_image')
        # Existing paired bootstrap independently pins the same corrected science.
        need(self.paired.contract['science']['scorer'] ==
             {'bytes':DONORS['numeric_score'][0],'sha256':DONORS['numeric_score'][1]},
             'same_revised_numeric_scorer')

    def _matched(self, requests, request_pins):
        need(type(requests) is dict and type(request_pins) is dict
             and set(requests) == set(request_pins) == {'A','B'}, 'complete_pair')
        for c in ('A','B'):
            self.paired.validate_request(requests[c],c)
            need(self.paired_module.pin(self.paired_module.encode(requests[c])) == request_pins[c],
                 'canonical_request_identity')
        a,b = requests['A'],requests['B']
        need(a['pair_id'] == b['pair_id'] and a['context_id'] != b['context_id']
             and all(a[k] == b[k] for k in ('resources','science','contract')),
             'matched_pair_science_contexts_resources')

    def _runtime(self, runtime, authorization, expected, request_pins):
        C = self.C
        need(type(runtime) is dict and set(runtime) ==
             {'image','docker','docker_physical','daemon_socket','daemon_guard'},
             'exact_runtime_selection')
        need(runtime['image'] == IMAGE, 'fixed_original_image_no_substitution')
        need(type(runtime['docker_physical']) is list
             and len(runtime['docker_physical']) == 7
             and all(type(x) is int for x in runtime['docker_physical']),
             'exact_physical_runtime_identity')
        required = {'schema':'purkinje-paired-program-owner-authorization/v1',
                    'task_id':TASK,'selected':True,'source':self.binding,
                    'requests':request_pins,'runtime':runtime,
                    'independent_source_review_accepted':True,
                    'exact_runtime_and_mount_profile_qualified':True,
                    'external_owner_deadline_and_cleanup_selected':True,
                    'current_capacity_and_storage_admitted':True,
                    'unconsumed_attempt_and_prior_costs_admitted':True}
        need(C.pin(C.encode(authorization)) == expected and
             C.encode(authorization) == C.encode(required), 'future_exact_owner_authorization_required')
        # These are trusted root attestations, never self-produced qualification.
        p = C.plain(runtime['docker']); s = p.lstat()
        need(list(C.signature(s)) == runtime['docker_physical'] and
             stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and os.access(p,os.X_OK),
             'unchanged_selected_docker')
        C.plain(runtime['daemon_socket'])
        self.owner.DOCKER = str(p)
        self.owner.DAEMON_SOCKET = Path(runtime['daemon_socket'])
        self.owner.DAEMON_GUARD = runtime['daemon_guard']

    def _stage(self, source, condition, target, budget):
        """Current manifest is the only admission authority; capture each body once."""
        C = self.C; source = C.plain(source)
        inventory = self.paired.inventory(condition)
        need(len(inventory) == (16 if condition == 'A' else 18), 'current_complete_packet')
        need(source.is_dir() and stat.S_IMODE(source.lstat().st_mode) == 0o500,
             'sealed_source_packet')
        dirs = {source:C.signature(source.lstat())}; found = set()
        stack = [source]
        while stack:
            d = stack.pop()
            with os.scandir(d) as entries:
                for entry in entries:
                    p = Path(entry.path); rel = str(p.relative_to(source))
                    if entry.is_dir(follow_symlinks=False):
                        need(rel == 'raw' and p not in dirs and
                             stat.S_IMODE(p.lstat().st_mode) == 0o500,'exact_packet_directory')
                        dirs[p] = C.signature(p.lstat()); stack.append(p)
                    else:
                        need(rel in inventory and rel not in found, 'exact_packet_namespace')
                        found.add(rel)
        need(found == set(inventory), 'full_packet_membership')
        target.mkdir(mode=0o700)
        for name,row in sorted(inventory.items()):
            path = target/name
            path.parent.mkdir(exist_ok=True)
            expected = {k:row[k] for k in ('bytes','sha256')}
            # Explicit descriptor replaces only this route's legacy 600000 cap.
            need(0 < expected['bytes'] <= 5000000,'fixed_packet_member_ceiling')
            raw = C.read(source/name,expected,budget,cap=expected['bytes'],mode=0o400)
            C.write(path,raw,budget,mode=0o444)
        need(all(C.signature(p.lstat()) == stamp for p,stamp in dirs.items()),
             'unchanged_packet_directory')
        if (target/'raw').is_dir():
            (target/'raw').chmod(0o555)
        target.chmod(0o555)
        return target

    def execute_pair(self, *, requests, request_pins, programs, packet_roots,
                     packet_receipts, runtime, owner_authorization,
                     owner_authorization_pin, root, budget, active_deadline):
        """Called only inside a selected external owner; no reference-reader argument.

        programs and packet_receipts are exact locators. Programs are committed
        before packet payloads; only outputs returned by the fixed protected
        producer are frozen. No callback can replace production execution.
        """
        C = self.C; need(not self.used,'one_use_pair_executor'); self.used = True
        self._matched(requests,request_pins)
        for values in (programs,packet_roots,packet_receipts):
            need(type(values) is dict and set(values) == {'A','B'}, 'complete_pair_inputs')
        self._runtime(runtime,owner_authorization,owner_authorization_pin,request_pins)
        need(time.monotonic() < active_deadline < budget.deadline,'active_cleanup_deadlines')
        root = C.plain(root)
        need(not root.exists() and root.parent.is_dir(),'fresh_pair_output')
        for c in ('A','B'):
            p = C.plain(packet_roots[c])
            need(root != p and root not in p.parents and p not in root.parents,
                 'packet_output_separation')
        need(C.plain(packet_roots['A']) != C.plain(packet_roots['B']),'distinct_packets')
        root.mkdir(mode=0o700)
        requests = C.decode(C.encode(requests))
        request_pins = C.decode(C.encode(request_pins))
        committed = {}; receipts = {}; attempts = {}; executions = {}
        # Both programmes are fixed before either candidate executes.
        for c in ('A','B'):
            entry = programs[c]
            expected = self.modules['boundary'].locator(entry,131072)
            need(expected == requests[c]['program'],'exact_requested_program')
            raw = C.read(entry['path'],expected,budget,cap=131072); raw.decode('utf-8')
            committed[c] = C.write(root/(c+'-program.py'),raw,budget)
            e = packet_receipts[c]
            ep = self.modules['boundary'].locator(e,65536)
            need(ep == requests[c]['packet_receipt'],'exact_requested_packet_receipt')
            self.paired.packet_receipt(e['path'],ep,c)
        C.write(root/'PAIR_PROGRAM_COMMIT.json',C.encode({
            'programs':committed,'requests':request_pins,'before_any_candidate':True,
            'before_any_packet_payload':True,'source':self.binding}),budget)
        cli = self.owner.configure_cli(root/'private-cli-config',budget)
        for c in ('A','B'):
            budget.check()
            self.owner.require_configured_cli(cli,budget)
            arm = root/c; arm.mkdir(mode=0o700)
            input_dir = self._stage(packet_roots[c],c,arm/'input',budget)
            task_dir = arm/'task'; task_dir.mkdir(mode=0o700)
            for name in ('TASK.md','SCHEMA.json'):
                row = self.paired.inventory(c)[name]
                data = C.read(input_dir/name,{k:row[k] for k in ('bytes','sha256')},
                              budget,cap=row['bytes'],mode=0o444)
                C.write(task_dir/name,data,budget,mode=0o444)
            task_dir.chmod(0o555)
            program = C.read(committed[c]['path'],requests[c]['program'],budget,cap=131072,mode=0o400)
            wrapper = self.modules['boundary'].render_program(self.bridge_body,program)
            wrapper_entry = C.write(arm/'selected-wrapper.py',wrapper,budget,mode=0o444)
            C.write(arm/'WRAPPER_COMMIT.json',C.encode({
                'program':requests[c]['program'],'bridge':self.binding['producer']['bridge.py'],
                'wrapper':wrapper_entry}),budget)
            # Owner validates exact mounts, natural exit and closure before returning.
            episode = self.owner.require_closed_episode(self.owner.run_candidate(
                root=arm/'candidate',input_dir=input_dir,task_dir=task_dir,
                program=Path(wrapper_entry['path']),budget=budget,active_deadline=active_deadline))
            need(not self.owner.registered_clients(),'all_owned_clients_closed')
            closed = self.owner.require_closed(episode)
            raw = C.read(closed.submission['path'],
                         self.modules['boundary'].locator(closed.submission,self.modules['bundle'].CAP),
                         budget,cap=self.modules['bundle'].CAP,mode=0o400)
            files = self.modules['bundle'].decode(raw)
            captured = arm/'captured'; captured.mkdir(mode=0o700)
            outputs = {n:C.write(captured/n,b,budget) for n,b in sorted(files.items())}
            executions[c] = {'program':requests[c]['program'],'wrapper':wrapper_entry,
                             'wire':closed.submission,'lifecycle':closed.lifecycle,
                             'files':outputs,'producer_closed':True}
            C.write(arm/'EXECUTION_COMMIT.json',C.encode(executions[c]),budget)
            attempts[c] = arm/'sealed-submission'
            receipts[c] = self.paired.freeze(
                requests[c],request_pins[c],packet_receipts[c]['path'],
                requests[c]['packet_receipt'],committed[c]['path'],captured,attempts[c],
                producer_stopped=True)
        need(not self.owner.registered_clients(),'pair_client_closure')
        state = {'requests':requests,'request_pins':request_pins,
                 'attempts':{c:str(p) for c,p in attempts.items()},'receipts':receipts,
                 'executions':executions,'source':self.binding}
        entry = C.write(root/'BOTH_PROGRAMS_CLOSED.json',C.encode(state),budget)
        budget.check()
        return ClosedPair(self,{'state':state,'receipt':entry,'graded':False},_TOKEN)

    def grade_closed_pair(self, closed, *, authority, authority_pin, reference_reader, budget):
        """Reuses unchanged target-last paired admission/scoring after both closures."""
        need(type(closed) is ClosedPair and closed._token is _TOKEN and
             closed._owner is self and not closed._state['graded'],'this_owner_closed_pair_once')
        state = closed._state['state']; receipt = closed._state['receipt']
        need(state['source'] == self.binding,'unchanged_pair_source')
        self.C.read(receipt['path'],self.modules['boundary'].locator(receipt,65536),
                    budget,cap=65536,mode=0o400)
        need(self.C.pin(self.C.encode(state)) ==
             {k:receipt[k] for k in ('bytes','sha256')},'unchanged_closed_pair_state')
        need(not self.owner.registered_clients(),'no_live_owned_client_before_private_grade')
        closed._state['graded'] = True
        return self.paired.compare_closed_pair(
            state['requests'],state['request_pins'],state['attempts'],state['receipts'],
            authority,authority_pin,reference_reader)
