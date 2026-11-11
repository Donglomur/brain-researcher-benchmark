"""Inactive installed Four source inspection and fixed original-owner APIs.

Inspection authenticates source and API definitions without scientific imports.
Typed methods delegate to accepted original factories; they do not create
native, Context, issuer, data or scientific qualification from metadata.
"""
import ast
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from types import ModuleType

SOURCE_LOCK = (207185, '0fd8b6912ec45913ae3930963a8891107cda84fe548e70e91d58dc2f3294155f')
TASKS = ('NEURAL-098', 'PAPER-paper-method-replacement-016')
HELD = ('authoring/delivery-20261105/neural098/public/COHORT.json',
        'authoring/delivery-20261105/neural098/public/source/phase3.txt')
MAX_MEMBER = 1048576
MAX_INSPECTION = 12582912
_LEASE = None


class SourceRefusal(RuntimeError):pass
def need(value, message):
    if not value:raise SourceRefusal(message)
def encoded(value):return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()
def sha(raw):return hashlib.sha256(raw).hexdigest()
def relative(name):
    need(type(name) is str and name and '\\' not in name and not any(c in name for c in '\0\r\n'), 'ordinary source name')
    p = PurePosixPath(name)
    need(not p.is_absolute() and p.as_posix() == name and all(x not in ('', '.', '..') for x in name.split('/')),
         'canonical relative source name')
    return p
def identity(s):return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def source_read(root, name, expected, budget, snapshots):
    # Held names are excluded before any stat/open or alias resolution.
    need(name not in {'originals/' + p for p in HELD}, 'held N098 body remains descriptor-only')
    p = relative(name);size = expected['bytes'];digest = expected['sha256']
    need(type(size) is int and 0 <= size <= MAX_MEMBER and type(digest) is str and len(digest) == 64 and
         all(c in '0123456789abcdef' for c in digest), 'finite exact source pin')
    budget['reserved'] += size + 1;need(budget['reserved'] <= MAX_INSPECTION, 'complete source inspection bound')
    path = root.joinpath(*p.parts)
    need(not any(v.is_symlink() for v in (path, *path.parents)), 'no source symlink ancestry')
    fd = None;first = None;data = bytearray()
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size, 'exact ordinary source extent')
        while len(data) < size:
            block = os.read(fd, min(65536, size - len(data)))
            budget['returned'] += len(block);need(block, 'complete source, never short prefix');data.extend(block)
        extra = os.read(fd, 1);budget['returned'] += len(extra)
        need(not extra and identity(before) == identity(os.fstat(fd)), 'unchanged complete source')
        need(sha(data) == digest, 'exact source body identity')
        snapshots[name] = identity(before)
    except BaseException as error:first = error
    finally:
        if fd is not None:
            try:os.close(fd)
            except BaseException as error:
                if first is None:first = error
                else:budget['cleanup_errors'].append(type(error).__name__)
    if first is not None:raise first
    return bytes(data)


def source_inverse(root, expected):
    seen = set();nodes = 0
    for prefix in ('current', 'originals'):
        stack = [root / prefix]
        while stack:
            with os.scandir(stack.pop()) as entries:
                for entry in entries:
                    nodes += 1
                    p = Path(entry.path)
                    name = p.relative_to(root).as_posix()
                    need(name not in {'originals/' + value for value in HELD}, 'held body cannot enter installed tree')
                    need(nodes <= 4096 and not entry.is_symlink(), 'bounded ordinary source tree')
                    if entry.is_dir(follow_symlinks=False):stack.append(p)
                    else:
                        need(entry.is_file(follow_symlinks=False), 'no special source nodes')
                        seen.add(name)
    need(seen == expected, 'complete source inverse: no omitted or extra module/cache')


def capture_source():
    need(sys.dont_write_bytecode, 'source inspection requires python -B')
    root = Path(__file__).absolute().parent
    need(root.resolve() == root and not root.is_symlink(), 'fixed ordinary installed source root')
    budget = {'reserved': 0, 'returned': 0, 'cleanup_errors': []};snapshots = {}
    raw = source_read(root, 'SOURCE_LOCK.json', {'bytes': SOURCE_LOCK[0], 'sha256': SOURCE_LOCK[1]}, budget, snapshots)
    lock = json.loads(raw)
    need(encoded(lock) == raw and lock['schema'] == 'four_complete_inactive_source_lock_v1', 'canonical exact source lock')
    rows = lock['files'];names = [r['path'] for r in rows]
    need(type(rows) is list and len(names) == len(set(names)) and
         lock['current_roles'] == 256 and lock['runtime_tables'] == 2 and
         lock['original_scientific_roles'] == 266 and lock['ordinary_original_bodies'] == 264 and
         lock['qualification_holds'] == 65, 'complete distinct current/scientific source populations')
    need([r['path'] for r in lock['held_descriptor_only']] == list(HELD), 'exact two held identities, never payloads')
    kinds = {kind: [r for r in rows if r['kind'] == kind] for kind in
             ('accepted_current_role', 'exact_runtime_table', 'ordinary_scientific_source', 'extension_projection')}
    need([len(kinds[k]) for k in ('accepted_current_role', 'exact_runtime_table', 'ordinary_scientific_source')] ==
         [256, 2, 264] and len(rows) == sum(map(len, kinds.values())), 'no source role pruned or silently added')
    bodies = {r['path']: source_read(root, r['path'], r, budget, snapshots) for r in rows}
    source_inverse(root, set(names))
    catalogue = json.loads(bodies['current/source/runtime/four_programmes/SOURCE_CATALOG.json'])
    tables = json.loads(bodies['current/source/runtime/four_programmes/SCHEMA_TABLES.json'])
    need(len(catalogue['original_roles']) == 266 and len(catalogue['APIs']) == 47 and
         len(catalogue['programmes']) == 4, 'complete original Four scientific catalogue')
    originals = {r['path'][len('originals/'):]: r for r in kinds['ordinary_scientific_source']}
    ordinary = [];held = [];counts = {}
    for r in catalogue['original_roles']:
        counts[r['programme']] = counts.get(r['programme'], 0) + 1
        if r['body_authenticated'] is False:
            need(r['path'] in HELD, 'only exact historical held body exclusions');held.append(r['path']);continue
        need(r['body_authenticated'] is True and r['path'] in originals, 'every original ordinary source retained')
        selected = originals[r['path']]
        need(all(selected[k] == r[k] for k in ('bytes', 'sha256')), 'same original source byte identity')
        ordinary.append(r['path'])
    need(len(ordinary) == 264 and set(held) == set(HELD) and counts ==
         {'NEURAL-056': 46, 'CriticalInit': 72, 'Hundred Models': 88, 'NEURAL-098': 60},
         'all four original scientific role populations, including held descriptors')
    trees = {};api_definitions = 0;metadata_apis = 0
    for name, a in catalogue['APIs'].items():
        key = 'originals/' + a['path'];need(key in bodies, 'complete original API source body')
        body = bodies[key]
        need(len(body) == a['bytes'] and sha(body) == a['sha256'], 'original API source pin')
        if 'AST_sha256' not in a:
            metadata_apis += 1;continue
        if key not in trees:trees[key] = ast.parse(body, filename=key)
        nodes = [n for n in ast.walk(trees[key]) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                 and n.lineno == a['line'] and n.end_lineno == a['end_line']]
        need(len(nodes) == 1 and sha(ast.dump(nodes[0], include_attributes=False).encode()) == a['AST_sha256'],
             'exact original API definition span and body')
        api_definitions += 1
    need(api_definitions == 46 and metadata_apis == 1, '46 definitions and one metadata API, not47Python definitions')
    # Extension copies bind existing current roles to a real ordinary Store
    # root; they are deployment copies, not extra scientific roles or aliases.
    current = {r['role']: r for r in kinds['accepted_current_role']}
    for r in kinds['extension_projection']:
        original = current[r['source_role']]
        need(r['bytes'] == original['bytes'] and r['sha256'] == original['sha256'] and
             r['path'].startswith('originals/_four_extensions/'), 'exact ordinary extension deployment copy')
    scopes = {task: catalogue['programmes'][task]['scientific_scope'] for task in TASKS}
    need(scopes[TASKS[1]]['reference_jobs'] == 8223 and scopes[TASKS[1]]['condition_rows'] == 335 and
         scopes[TASKS[0]]['people'] == 33 and scopes[TASKS[0]]['conditions'] == ['A_F', 'A_I', 'B_F', 'B_I'] and
         scopes[TASKS[0]]['external_original_parent_files'] == 49, 'complete accepted scientific scopes')
    public = {'schema': 'four_inactive_central_source_inspection_v1', 'current_roles': 256,
        'runtime_tables': 2, 'ordinary_original_bodies': 264, 'original_scientific_roles': 266,
        'extension_deployment_copies': len(kinds['extension_projection']), 'original_API_definitions': 46,
        'original_metadata_APIs': 1, 'held_bodies_opened': False, 'original_modules_imported': False,
        'scope': scopes, 'qualification_holds_open': 65, 'inspection_bytes': budget,
        'runnable': False, 'research_qualified': False, 'submission_ready': False,
        'scientific_or_native_execution': False, 'authority_issued': False}
    return root, lock, catalogue, tables, snapshots, public


def inspect_source(task):
    need(task in TASKS, 'one of the two original canonical assignments')
    return dict(capture_source()[-1], id=task, counting_unit='one canonical assignment; shared sources are not tasks')


class HostRuntime:
    """Trusted original-owner bridge. No JSON-to-owner reconstruction or grant."""
    def __init__(self, task):
        global _LEASE
        need(task in TASKS and sys.flags.isolated and sys.dont_write_bytecode, 'fresh trusted host with -I -B')
        if _LEASE is None:
            capture = capture_source();root, lock, catalogue, tables, snapshots, public = capture
            need(not any(name == 'four_programmes' or name.startswith('four_programmes.') for name in sys.modules),
                 'no preexisting foreign Four module aliases')
            path = str(root / 'current/source/runtime');old_path = tuple(sys.path);sys.path.insert(0, path)
            module_names = ('common', 'roots', 'source_session', 'resources', 'schema', 'source_catalogue',
                'n098_startup', 'external_runner', 'external_campaigns', 'hm_whole_job_profile_v1',
                'hm_whole_job_controller_v1', 'hm_whole_job_controller_budget_v1', 'hm_whole_job_main_v1',
                'hm_whole_job_native_v1', 'hm_whole_job_host_v1', 'hm_whole_job_outer_v1')
            modules = {name: importlib.import_module('four_programmes.' + name) for name in module_names}
            _LEASE = {'root': root, 'lock': lock, 'catalogue': catalogue, 'tables': tables, 'snapshots': snapshots,
                      'public': public, 'path': path, 'old_path': old_path, 'modules': modules,
                      'owned_modules': {name: module for name, module in sys.modules.items()
                                        if name == 'four_programmes' or name.startswith('four_programmes.')}}
        self.lease = _LEASE;self.task = task;self.sessions = [];self.owners = []
        self.modules = self.lease['modules'];self.root = self.lease['root'];self.catalogue = self.lease['catalogue']
        self.originals = self.root / 'originals';self.require_original()

    def require_original(self):
        need(self.lease is _LEASE and self.task in TASKS and self.modules is self.lease['modules'], 'same original host/source lease')
        need(tuple(sys.path) == (self.lease['path'],) + self.lease['old_path'], 'same fixed trusted source import path')
        for name, original in self.lease['owned_modules'].items():
            need(sys.modules.get(name) is original and type(original) is ModuleType, 'same actual loaded source module')
            path = Path(vars(original).get('__file__', '')).absolute()
            need(path.is_relative_to(self.root / 'current/source/runtime') and
                 path.relative_to(self.root).as_posix() in self.lease['snapshots'], 'actual admitted module origin')
        for name, expected in self.lease['snapshots'].items():
            path = self.root / name
            need(not path.is_symlink() and identity(path.stat()) == expected, 'unchanged installed source extent')
        return self

    def _task(self, selected):
        self.require_original();need(self.task == selected, 'canonical task owns its original API route')

    def source_session(self, meter, *, selected_context, selected_templates, environment):
        self.require_original();m = self.modules
        need(type(meter) is m['resources'].Share, 'actual earlier original source Share')
        package = m['source_session'].BASES[self.task][1]
        expected = m['source_session'].EXTENSIONS[self.task]
        rows = {r['path']: r for r in self.lease['lock']['files']}
        extensions = {}
        for name in expected:
            relative_path = '_four_extensions/' + package + '/' + name + '.py'
            source = rows['originals/' + relative_path]
            extensions[name] = {'path': relative_path, 'bytes': source['bytes'], 'sha256': source['sha256']}
        store = m['common'].Store(self.originals, meter, forbidden=HELD)
        session = m['source_session'].SourceSession(self.task, catalog=self.catalogue, ordinary_store=store,
            extension_sources=extensions, root=self.originals, selected_context=selected_context,
            selected_templates=selected_templates, environment=environment)
        self.sessions.append(session);return session

    def _session(self, session):
        self.require_original()
        need(type(session) is self.modules['source_session'].SourceSession and session in self.sessions and
             session.programme == self.task and not session.closed, 'same admitted original programme source session')

    def n098_bootstrap(self):
        self._task('NEURAL-098')
        return self.modules['n098_startup'].bootstrap_from_selected_root()

    def n098_prelaunch(self, bootstrap, *, adapter_manifest, selected_context, selected_templates, environment):
        self._task('NEURAL-098')
        return self.modules['n098_startup'].admit_n098_prelaunch(bootstrap, catalog=self.catalogue,
            adapter_manifest=adapter_manifest, repo=self.originals, selected_context=selected_context,
            selected_templates=selected_templates, environment=environment)

    def n098_resources(self, admission):
        self._task('NEURAL-098');m = self.modules
        need(type(admission) is m['n098_startup'].PrelaunchAdmission and admission.catalog is self.catalogue and
             Path(admission.repo) == self.originals, 'actual same original N098 prelaunch source/root')
        owner = m['resources'].RootResources.for_prelaunch(admission.resource_pin, admission.prelaunch_selection_pin,
                                                         admission, admission.bootstrap)
        self.owners.append(owner);return owner

    def _n098_owner(self, owner):
        self._task('NEURAL-098')
        need(type(owner) is self.modules['resources'].RootResources and owner in self.owners and owner.staged,
             'same original staged N098 resource owner')

    def n098_start_parked(self, owner):
        self._n098_owner(owner);return owner.start_parked_once()

    def n098_bind_final(self, owner, final_plan, final_plan_pin, final_binding_join, actual_parked_handle):
        self._n098_owner(owner)
        return owner.bind_final_once(final_plan, final_plan_pin, final_binding_join, actual_parked_handle)

    def n098_verify_final_chain(self, owner, join_pin, *, schemas, session, request_catalog, adapter_manifest):
        self._n098_owner(owner);self._session(session)
        return self.modules['n098_startup'].verify_final_chain(owner, join_pin, schemas=schemas, session=session,
            request_catalog=request_catalog, adapter_manifest=adapter_manifest)

    def n098_invoke(self, owner, *, stores, output_store, host):
        self._n098_owner(owner)
        admission = self.modules['external_runner'].bind_n098_external(owner.bound_view)
        need(admission.catalog is self.catalogue and Path(admission.repo) == self.originals,
             'original external N098 entry resolves all source parents under installed originals root')
        return self.modules['external_runner'].run_n098(admission, stores=stores, output_store=output_store,
                                                       host=host, resources=owner)

    def n098_argv(self, binding, selection, *, analysis_python):
        self._task('NEURAL-098')
        return self.modules['external_campaigns'].n098_argv(binding, selection, repo=self.originals,
            catalog=self.catalogue, analysis_python=analysis_python)

    def hm_plan(self, body, *, resource_plan, resource_plan_pin):
        self._task('PAPER-paper-method-replacement-016')
        return self.modules['hm_whole_job_profile_v1'].compile_original_hm_whole_job_plan_v1(
            body, resource_plan=resource_plan, resource_plan_pin=resource_plan_pin)

    def hm_reservations(self, *, resources, plan, host_share):
        self._task('PAPER-paper-method-replacement-016')
        owner = self.modules['hm_whole_job_profile_v1'].create_original_hm_whole_job_reservations_v1(
            resources=resources, plan=plan, host_share=host_share)
        self.owners.append(owner);return owner

    def hm_controller_budget(self, *, session, plan):
        self._task('PAPER-paper-method-replacement-016');self._session(session)
        return self.modules['hm_whole_job_controller_budget_v1'].create_original_hm_whole_controller_budget_v1(session=session, plan=plan)

    def hm_controller_channel(self, *, session, **kwargs):
        self._task('PAPER-paper-method-replacement-016');self._session(session)
        return self.modules['hm_whole_job_controller_v1'].open_original_hm_whole_controller_channel_v1(session=session, **kwargs)

    def hm_host_endpoint(self, *, reservations, **kwargs):
        self._task('PAPER-paper-method-replacement-016')
        need(reservations in self.owners, 'same original reservation owner')
        return self.modules['hm_whole_job_controller_v1'].open_original_hm_whole_controller_endpoint_v1(reservations=reservations, **kwargs)

    def hm_main(self, *, session, **kwargs):
        self._task('PAPER-paper-method-replacement-016');self._session(session)
        owner = self.modules['hm_whole_job_main_v1'].create_original_hm_whole_main_v1(session=session, **kwargs)
        self.owners.append(owner);return owner

    def hm_run_main(self, owner):
        self._task('PAPER-paper-method-replacement-016')
        need(type(owner) is self.modules['hm_whole_job_main_v1'].HMWholeMainV1 and owner in self.owners,
             'same actual original C owner, never serialized state')
        return owner.run_once()

    def hm_campaign(self, *, reservations, session, host, configuration_roots):
        self._task('PAPER-paper-method-replacement-016');self._session(session)
        need(reservations in self.owners, 'same original nonrefundable reservations')
        owner = self.modules['hm_whole_job_native_v1'].open_original_hm_native_campaign_v1(
            reservations=reservations, session=session, host=host, configuration_roots=configuration_roots)
        self.owners.append(owner);return owner

    def hm_run_host(self, campaign):
        self._task('PAPER-paper-method-replacement-016')
        need(type(campaign) is self.modules['hm_whole_job_native_v1'].HMNativeCampaignOwnerV1 and campaign in self.owners,
             'same original actual H campaign')
        flow = self.modules['hm_whole_job_host_v1'].create_original_hm_whole_host_flow_v1(campaign)
        self.owners.append(flow);return flow.run_once()

    def hm_outer(self, **kwargs):
        self._task('PAPER-paper-method-replacement-016')
        # The accepted actual producer explicitly refuses absent genuine H
        # launch/publisher custody; central registration cannot bypass it.
        owner = self.modules['hm_whole_job_outer_v1'].open_original_hm_whole_outer_v1(**kwargs)
        self.owners.append(owner);return owner

    def hm_finish_outer(self, owner):
        self._task('PAPER-paper-method-replacement-016')
        need(type(owner) is self.modules['hm_whole_job_outer_v1'].HMWholeOuterCoordinatorV1 and owner in self.owners,
             'same actual original outer owner')
        return owner.finish_once()


def main(task, argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    need(argv == ['inspect'], 'CLI supports source inspection only; no generic run/score or serialized owner factory')
    print(json.dumps(inspect_source(task), sort_keys=True, indent=2, allow_nan=False));return 0
