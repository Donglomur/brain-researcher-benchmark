"""Concrete metadata-only context, assembled into the single constructor."""

COUNTERS = ('read_bytes', 'write_bytes', 'native_cpu_seconds', 'native_processes',
            'host_processes', 'provider_requests', 'provider_tokens', 'stream_bytes', 'tool_processes')
WORKER_ROLES = {
    'preparation': ('common', 'protocol', 'arrays', 'custody', 'outputs', 'preparation', 'preparation_worker'),
    'reference': ('common', 'protocol', 'arrays', 'custody', 'model_io', 'outputs', 'numeric_worker', 'numeric'),
    'issuer': ('common', 'protocol', 'arrays', 'fd_protocol', 'projection_engine', 'issuer_sandbox', 'issuer_worker'),
    'grader': ('common', 'protocol', 'arrays', 'custody', 'outputs', 'metrics', 'grading', 'closure', 'schedule',
               'runtime', 'host_observation', 'candidate_runner', 'transport', 'transport.common', 'transport.provider',
               'transport.process', 'authority'),
}
WORKER_ENTRIES = {'preparation': 'preparation_entry', 'reference': 'numeric_entry', 'issuer': 'issuer_entry', 'grader': 'grade_entry'}
WRITE_DOMAINS = {
    'select-run': ('P',), 'bind-environment': ('P',), 'bind-channel': ('P',),
    'request-launch': ('P',), 'bind-launch': ('P',), 'bind-route': ('Q', 'V'),
    'activate-route': ('V',), 'request-review': ('R',), 'publish-review': ('R', 'P'),
    'admit-approved-review': ('P',), 'respond': ('P',),
}


class AdmissionBudget:
    """Original run clock and conservative metadata charges, never a new clock.

    This constructor admission ledger does not impersonate the later running
    scientific ledger. Its metadata charges also debit the CLI's own envelope.
    """
    def __init__(self, context, run):
        self.context = context
        self.origin = finite(run['origin'], 0)
        self.end = finite(run['normal_endpoint'], 0)
        self.limits = {k: integer(run['whole_limits'][k]) for k in COUNTERS}
        self.used = dict.fromkeys(COUNTERS, 0)
        self.clock = time.monotonic
        self.check_clock()

    def check_clock(self):
        self.context.budget.check()
        need(self.origin < time.monotonic() < self.end, 'unchanged selected run endpoint')

    def charge(self, key, value):
        integer(value)
        self.check_clock()
        need(key in self.used and self.used[key] + value <= self.limits[key], 'metadata admission within selected run limits')
        self.used[key] += value
        if key in ('read_bytes', 'write_bytes'):
            self.context.budget.charge(key, value)
        else:
            need(value == 0, 'constructor cannot spend operational work')

    def snapshot(self):
        return {'original_origin': self.origin, 'original_deadline': self.end,
                'logical_used': dict(self.used), 'limits': dict(self.limits),
                'construction_metadata_only': True, 'physical_IO_or_RSS_measured': False}


class Context:
    def __init__(self, instance_desc, run_desc, stage, budget):
        need(stage in WRITE_DOMAINS, 'finite selected metadata stage')
        self.stage, self.budget = stage, budget
        self.instance_descriptor = descriptor(instance_desc)
        self.instance = capture_json(instance_desc, budget)
        exact(self.instance, ('schema', 'task_id', 'root', 'profile', 'root_roles', 'release', 'public_origin',
                             'construction', 'parent_source', 'central_source', 'source_freeze', 'selection',
                             'registry_initial', 'requirements', 'outputs', 'runtime_authorization',
                             'qualification_created', 'scientific_execution'))
        need(self.instance['schema'] == 'neural081_portable_build_result_v1' and self.instance['task_id'] == TASK,
             'complete portable construction result')
        for name in ('runtime_authorization', 'qualification_created', 'scientific_execution'):
            need(self.instance[name] is False, 'construction grants no operational authority')
        self.root = canonical(self.instance['root'])
        self.here = self.root / CENTRAL
        need(instance_desc['path'] == str(self.root / BREL / 'BUILD_RESULT.json'), 'fixed original build-result path')
        self.profile = capture_json(self.instance['profile'], budget, cap=PROFILE_CAP)
        self.roots = _profile(self.profile, self.root)
        need(same(self.roots, self.instance['root_roles']), 'exact profile domains')
        self.source, self.parent, self.construction = (self.instance[k] for k in ('central_source', 'parent_source', 'construction'))
        self._source_cache = {}
        self._metadata_reads = {}
        self._module_cache = {}
        self.run = self.run_descriptor = self.run_root = self._admission_budget = None
        self._validate_instance()
        if run_desc is not None:
            descriptor(run_desc)
            run = self.read(run_desc, scope='operator')
            expected_root = self._run_path(run)
            need(run_desc['path'] == str(expected_root / 'RUN.json'), 'exact selected run location')
            self.run, self.run_descriptor, self.run_root = run, run_desc, expected_root
            self._admission_budget = AdmissionBudget(self, run)
            self.parent_call('authority.run_allocation', run, self._admission_budget)
        need((stage in ('select-run', 'bind-route', 'activate-route')) or self.run is not None,
             'original run required for this metadata stage')
        self.local_gate = self._load_full(CENTRAL + '/portable_gate.py', '_portable_local_gate')

    def _deny(self, path):
        p = canonical(str(path))
        denied = [canonical(v) for k in ('raw', 'secret', 'protected') for v in self.roots[k]]
        denied.append(canonical(self.roots['output']))
        need(not any(p == q or p.is_relative_to(q) or q.is_relative_to(p) for q in denied),
             'constructor never opens raw, key, protected, model or result domains')
        return p

    def _domain_roots(self, scope):
        if scope in ('operator', 'input'):
            return [canonical(v) for v in self.roots['operator']]
        if scope in ('Q', 'R', 'V'):
            return [self.root / {'Q': QREL, 'R': RREL, 'V': VREL}[scope]]
        if scope == 'construction':
            return [self.root / BREL]
        need(scope == 'source', 'declared metadata read scope')
        return []

    def read(self, desc, *, scope, cap=1048576):
        descriptor(desc)
        p = self._deny(desc['path'])
        if scope == 'source':
            allowed = dict(self.fixed_files)
            for key in ('source_freeze', 'selection', 'registry_initial', 'requirements'):
                d = self.instance[key]
                allowed[d['path']] = d
            if p == self.root / JREL:
                cap = min(cap, 131072)
            else:
                need(p.as_posix() in allowed and same(allowed[p.as_posix()], desc), 'exact immutable source metadata pin')
        else:
            need(any(p.is_relative_to(q) for q in self._domain_roots(scope)), 'selected metadata domain before body access')
        value = capture_json(desc, self.budget, cap=cap)
        self._remember(desc)
        return value

    def _remember(self, desc):
        prior = self._metadata_reads.get(desc['path'])
        need(prior is None or same(prior, desc), 'immutable metadata identity during one stage')
        self._metadata_reads[desc['path']] = dict(desc)

    def _validate_instance(self):
        # Only metadata roles are read here. All source bodies subsequently have
        # a literal role and immutable identity before any compile or operation.
        fixed_locs = {'release': 'neural081/PORTABLE_RELEASE.json', 'public_origin': 'neural081/PUBLIC_ORIGIN_MAP.json',
                      'construction': PARENT + '/CONSTRUCTION.json', 'parent_source': PARENT + '/SOURCE_MANIFEST.json',
                      'central_source': CENTRAL + '/SOURCE_MANIFEST.json', 'source_freeze': CENTRAL + '/QUALIFICATION_SOURCE.json',
                      'selection': LREL, 'registry_initial': JREL, 'requirements': BREL + '/REQUIREMENTS.json'}
        for key, rel in fixed_locs.items():
            descriptor(self.instance[key])
            need(self.instance[key]['path'] == str(self.root / rel), 'fixed generated metadata role')
        release = validate_release(capture_json(self.instance['release'], self.budget))
        self.release = release
        c = capture_json(self.construction, self.budget)
        exact(c, ('schema', 'task_id', 'root', 'release', 'public_origin', 'python_bodies', 'context_bodies',
                  'variants', 'construction_only', 'runtime_authorization'))
        active = {name: {'path': str(self.root / name), 'bytes': row['bytes'], 'sha256': row['sha256']}
                  for name, row in release['active_sources'].items()}
        expected_c = {'schema': 'neural081_portable_construction_v1', 'task_id': TASK, 'root': str(self.root),
                      'release': self.instance['release'], 'public_origin': self.instance['public_origin'],
                      'python_bodies': sorted([v for k, v in active.items() if k.endswith('.py')], key=lambda d: d['path']),
                      'context_bodies': sorted([v for k, v in active.items() if k.startswith('neural081/protocol/')], key=lambda d: d['path']),
                      'variants': [{'target': active[v['target']['path']], 'original': v['original']} for v in release['variants']],
                      'construction_only': True, 'runtime_authorization': False}
        need(same(c, expected_c), 'complete acyclic construction lineage')
        p = capture_json(self.parent, self.budget)
        modules = []
        for name in sorted(active):
            if name.startswith(PARENT + '/program/') and name.endswith('.py') and name != PARENT + '/program/entry.py':
                tail = name.split('/program/', 1)[1]
                module = tail[:-12].replace('/', '.') if tail.endswith('/__init__.py') else tail[:-3].replace('/', '.')
                modules.append({'name': module, 'source': active[name]})
        auxiliary = [{'role': r, 'source': active[PARENT + '/references/' + r + '/numeric.py']} for r in ('r1', 'r2')]
        expected_p = {'schema': 'neural081_portable_parent_source_v1', 'task_id': TASK,
                      'entry': active[PARENT + '/program/entry.py'], 'modules': modules,
                      'auxiliary': auxiliary, 'construction': self.construction}
        need(same(p, expected_p), 'literal full parent manifest, all41 modules and two numerics')
        self.parent_document = p
        self.source_files = [p['entry'], *[r['source'] for r in p['modules']], *[r['source'] for r in p['auxiliary']], self.construction]
        fixed = dict(active)
        for key in ('release', 'public_origin', 'construction', 'parent_source'):
            fixed[fixed_locs[key]] = self.instance[key]
        b_desc = {'path': str(self.here / 'BINDINGS.json')}
        manifest = capture_json(self.source, self.budget)
        exact(manifest, ('schema', 'task_id', 'files'))
        need(manifest['schema'] == 'neural081_portable_central_source_v1' and manifest['task_id'] == TASK,
             'portable central manifest')
        names = ('entry.py', 'n081_dispatch.py', 'n081_host.py', 'n081_readback.py', 'n081_routing.py', 'n081_selection.py', 'portable_gate.py', 'BINDINGS.json')
        exact(manifest['files'], names)
        b_desc.update(manifest['files']['BINDINGS.json'])
        self.bindings = capture_json(b_desc, self.budget)
        prior = sorted([v for k, v in fixed.items() if not k.startswith(CENTRAL + '/')], key=lambda d: d['path'])
        need(len(prior) == 63, '63 earlier acyclic identities')
        expected_b = {'schema': 'neural081_portable_central_bindings_v1', 'task_id': TASK, 'parent_manifest': self.parent,
                      'construction': self.construction, 'source_rows': prior,
                      'tools': {'campaign': active['tools/neurobench_campaign.py'], 'campaign_gate': active['tools/neurobench_campaign_gate.py']}}
        need(same(self.bindings, expected_b), 'exact central acyclic source binding')
        for name in names:
            if name != 'BINDINGS.json':
                need(same(manifest['files'][name], {k: active[CENTRAL + '/' + name][k] for k in ('bytes', 'sha256')}), 'central source body identity')
        fixed[CENTRAL + '/BINDINGS.json'] = b_desc
        fixed[CENTRAL + '/SOURCE_MANIFEST.json'] = self.source
        self.rows = {k: {j: v[j] for j in ('bytes', 'sha256')} for k, v in sorted(fixed.items())}
        need(len(fixed) == 72, 'literal complete72 source closure')
        self.fixed_files = {v['path']: v for v in fixed.values()}
        self.manifest = manifest
        freeze = capture_json(self.instance['source_freeze'], self.budget)
        need(same(freeze, {'schema': 'neural081_portable_qualification_source_v1', 'task_id': TASK, 'files': self.rows}), 'exact complete qualification closure')
        own = active['tools/neural081_instance.py']
        need(canonical(str(Path(__file__).absolute())) == canonical(own['path']), 'stage uses genuine installed constructor')
        for desc in self.fixed_files.values():
            capture_bytes(desc, self.budget)
        origin = capture_json(self.instance['public_origin'], self.budget)
        need(origin.get('schema') == 'neural081_complete_public_original_source_manifest_v1' and
             self.instance['public_origin']['bytes'] == 48901 and self.instance['public_origin']['sha256'] ==
             '32705c641e263ac91c5f0b7f5ed60ac42cac9f9af87c07cd74e30cd1bcfee2f5', 'literal public origin')
        need(same({k: self.instance['public_origin'][k] for k in ('bytes', 'sha256')},
                  {k: release['public_manifest'][k] for k in ('bytes', 'sha256')}), 'original source provenance not rebound')

    def source_text(self, relative_path, cap=65536):
        relative(relative_path)
        path = str(self.root / relative_path)
        need(path in self.fixed_files, 'fixed source role only')
        self.budget.hold(4 * self.fixed_files[path]['bytes'] + 4096)
        return capture_bytes(self.fixed_files[path], self.budget, cap=cap).decode('utf-8')

    def _load_full(self, relative_path, name):
        if name in self._module_cache:
            return self._module_cache[name]
        body = self.source_text(relative_path, cap=BODY_CAP)
        # This is only used for the fixed stdlib common/gate/shared helper
        # bodies. No candidate, numerical, provider or scientific module loads.
        need(relative_path in (PARENT + '/program/common.py', CENTRAL + '/portable_gate.py',
                               'tools/neurobench_campaign.py', 'tools/neurobench_campaign_gate.py'), 'fixed metadata module loader')
        reserve = self.budget.hold(24 * len(body.encode()) + 16384)
        module = types.ModuleType(name)
        module.__file__ = str(self.root / relative_path)
        if relative_path == CENTRAL + '/portable_gate.py':
            dependencies = {'common': self._load_full(PARENT + '/program/common.py', '_portable_parent_common'),
                            'n081_shared_gate': self._load_full('tools/neurobench_campaign_gate.py', '_portable_shared_gate')}
            original_import = __import__
            def captured_import(name, globals=None, locals=None, fromlist=(), level=0):
                if level == 0 and name in dependencies:
                    return dependencies[name]
                return original_import(name, globals, locals, fromlist, level)
            import builtins
            module.__dict__['__builtins__'] = {**vars(builtins), '__import__': captured_import}
        try:
            exec(compile(body, module.__file__, 'exec'), module.__dict__)
        except BaseException:
            self.budget.release(reserve)
            raise
        # Retain the conservative source/code/module reservation for this
        # invocation, rather than count only shallow function objects.
        self._module_cache[name] = module
        return module

    def _metadata_functions(self):
        if 'parent_metadata' in self._module_cache:
            return self._module_cache['parent_metadata']
        c = self._load_full(PARENT + '/program/common.py', '_portable_parent_common')
        # Concrete bounded capture bridge replaces only filesystem I/O, keeping
        # the original exact constructors/admission predicates byte-for-byte AST.
        def captured(desc, budget, roots, *, empty=False):
            descriptor(desc)
            need(not empty, 'nonempty metadata only')
            p = self._deny(desc['path'])
            need(any(p == Path(r) or p.is_relative_to(Path(r)) for r in roots), 'original parent selected metadata root')
            need(any(p.is_relative_to(Path(r)) for r in self.roots['operator']) or
                 p.is_relative_to(self.here / 'operator-selections'), 'parent metadata does not acquire operand access')
            budget.check_clock()
            # capture_bytes charges the constructor; debit only the independent
            # original-clock admission ledger here to avoid duplicate charges.
            n = desc['bytes'] + 1
            need(budget.used['read_bytes'] + n <= budget.limits['read_bytes'], 'original metadata read reserve')
            budget.used['read_bytes'] += n
            raw = capture_bytes(desc, self.budget, cap=BODY_CAP)
            self._remember(desc)
            return raw
        c.capture = captured
        def captured_json(d, b, roots):
            reserve = self.budget.hold(80 * d['bytes'] + 16384)
            try:
                value = parse(captured(d, b, roots))
                retained = managed_size(value)
                need(retained <= reserve, 'bounded actual parent metadata parse')
            finally:
                self.budget.release(reserve)
            self.budget.hold(retained)
            return value
        c.capture_json = captured_json
        def selected(relative_path, names, globals_):
            text = self.source_text(relative_path, cap=BODY_CAP)
            self.budget.hold(32 * len(text.encode()) + 16384)
            tree = ast.parse(text)
            nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.Assign)) and
                     ((isinstance(n, ast.FunctionDef) and n.name in names) or
                      (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)))]
            got = {n.name if isinstance(n, ast.FunctionDef) else n.targets[0].id for n in nodes}
            need(got == set(names), 'exact captured metadata definitions')
            exec(compile(ast.Module(body=nodes, type_ignores=[]), str(self.root / relative_path), 'exec'), globals_)
        custody = {'c': c, 'Path': Path}
        selected(PARENT + '/program/custody.py', ('disjoint_roots',), custody)
        auth = {'c': c, 'Path': Path, 'disjoint_roots': custody['disjoint_roots']}
        selected(PARENT + '/program/authority.py', ('ROLES', 'PHASES', 'ACTORS', 'run_allocation', 'admit'), auth)
        authority = types.SimpleNamespace(**auth)
        outer = {'c': c, 'Path': Path, 'authority': authority}
        selected(PARENT + '/program/outer.py', ('launch_request', 'admit_launch'), outer)
        result = {**{'authority.' + k: auth[k] for k in ('run_allocation', 'admit')},
                  **{'outer.' + k: outer[k] for k in ('launch_request', 'admit_launch')}}
        self._module_cache['parent_metadata'] = result
        return result

    def parent_call(self, name, *args, **kwargs):
        functions = self._metadata_functions()
        need(name in functions, 'fixed metadata function, no execute dispatch')
        if name == 'authority.run_allocation':
            need(len(args) == 2 and not kwargs, 'metadata-only run allocation excludes numeric index')
        self.budget.check()
        out = functions[name](*args, **kwargs)
        self.budget.check()
        return out

    def stage_budget(self):
        need(self._admission_budget is not None, 'selected original run required')
        self._admission_budget.check_clock()
        return self._admission_budget

    def _run_path(self, run):
        return canonical(self.roots['operator'][0]) / 'portable-runs' / pin(encode(run))['sha256']

    def select_run(self, run):
        need(self.stage == 'select-run' and self.run is None, 'one fresh run selection')
        budget = AdmissionBudget(self, run)
        self.parent_call('authority.run_allocation', run, budget)
        self.run_root = self._run_path(run)
        base = canonical(self.roots['operator'][0])
        ordinary_ancestors(base)
        need(not self.run_root.exists(), 'fresh separately selected run namespace')
        mkdirs(base, self.run_root, self.budget)
        self.run, self._admission_budget = run, budget
        self.run_descriptor = self.write('P', 'RUN.json', run)
        return self.run_descriptor

    def _write_root(self, domain):
        need(domain in WRITE_DOMAINS[self.stage], 'stage-specific writer domain')
        if domain == 'P':
            need(self.run_root is not None, 'run directory before write')
            return self.run_root
        return self.root / {'Q': QREL, 'R': RREL, 'V': VREL}[domain]

    def write(self, domain, relative_name, value):
        relative(relative_name)
        root = self._write_root(domain)
        if domain in ('Q', 'R'):
            need('/' not in relative_name, 'protected fixed metadata direct children')
        if domain == 'V':
            parts = Path(relative_name).parts
            if len(parts) == 2:
                digest(parts[0])
                need(parts[1] in ('GENERATION.json', 'TRANSACTION.json'), 'fixed registry generation artifact')
            else:
                need(len(parts) == 1 and relative_name.endswith('.json') and
                     any(relative_name.startswith(prefix) for prefix in ('intent-', 'result-', 'failure-', 'constructor-failure-')),
                     'fixed direct transaction observation')
        if domain == 'R':
            need(relative_name != 'APPROVAL_REGISTRY.json', 'constructor never issues approval registry')
        return publish_json(root, root / relative_name, value, self.budget)

    def import_record(self, desc, domain, relative_name):
        relative(relative_name)
        if domain == 'V':
            parts = Path(relative_name).parts
            need(len(parts) == 2 and parts[1] == 'PREIMAGE.json' and desc['path'] == str(self.root / JREL), 'fixed original registry preimage import')
            digest(parts[0])
            self.read(desc, scope='source', cap=131072)
        else:
            need(domain in ('Q', 'R') and '/' not in relative_name, 'fixed direct metadata import')
            self.read(desc, scope='operator')
        root = self._write_root(domain)
        raw = capture_bytes(desc, self.budget)
        copied = publish_bytes(root, root / relative_name, raw, self.budget)
        need(same(pin(raw), {k: copied[k] for k in ('bytes', 'sha256')}), 'exact issued bytes, no synthesized qualifier')
        return {'origin': desc, 'copy': copied}

    def channel_directories(self):
        need(self.stage == 'bind-channel' and self.run_root is not None, 'fixed channel writer')
        channel = self.run_root / 'channel'
        need(not channel.exists(), 'fresh current run channel')
        mkdirs(self.run_root, channel, self.budget)
        for name in ('requests', 'responses'):
            mkdirs(self.run_root, channel / name, self.budget)
        return {'request_root': str(channel / 'requests'), 'response_root': str(channel / 'responses')}

    def stage_record(self, relative_name, cap=1048576):
        """Discover only the two source-owned immutable current-run bindings.

        This is a bounded ordinary metadata capture, not an arbitrary operand
        discovery API. Stage predicates additionally join source/run/inputs.
        """
        need(relative_name in ('selection/OPERANDS.json', 'environment/BINDING.json') and
             self.run_root is not None, 'two fixed current-run resolution records')
        integer(cap, 1, 1048576)
        path = self._deny(self.run_root / relative_name)
        ordinary_ancestors(path)
        size = integer(path.lstat().st_size, 1, cap)
        self.budget.charge('read_bytes', size + 1)
        reserve = self.budget.hold(80 * size + 16384)
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            first = os.fstat(fd)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == size,
                 'ordinary exact resolution metadata')
            with os.fdopen(fd, 'rb', closefd=False) as stream:
                raw = stream.read(size + 1)
            after, named = os.fstat(fd), path.lstat()
            fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
            need(len(raw) == size and all(getattr(first, k) == getattr(after, k) == getattr(named, k) for k in fields),
                 'complete stable current resolution record')
            desc = {'path': str(path), **pin(raw)}
            value = parse(raw)
            retained = managed_size(value) + managed_size(desc)
            need(retained <= reserve, 'bounded resolution metadata')
        finally:
            os.close(fd)
            self.budget.release(reserve)
        self.budget.hold(retained)
        self.budget.check()
        self._remember(desc)
        return {'descriptor': desc, 'document': value}

    def route(self, condition):
        return route_template(self.root, self.source, self.manifest['files']['entry.py']['sha256'], condition)

    def gate_context(self, review=None, invocation_operands=None):
        ctx = {'repo': self.root, 'here': self.here, 'source': self.source, 'parent_source': self.parent,
               'construction': self.construction, 'rows': self.rows, 'manifest': self.manifest, 'budget': self.budget}
        if review is not None:
            ctx['review'] = review
        if invocation_operands is not None:
            ctx['invocation_operands'] = invocation_operands
        return ctx

    def actual_argv(self, condition, program, output, review, other, *, python):
        for p in (program, output, review):
            canonical(p)
        integer(other)
        python = str(canonical(python))
        command = self.route(condition)['argv'][:]
        values = {'{python}': python, '{program}': program, '{output}': output,
                  '{review}': review, '{other_reserve_bytes}': str(other)}
        command = [values.get(v, v) for v in command]
        command[6] = str(self.here / 'entry.py')
        return command

    def generic_qualification(self, registry_doc):
        need(registry_doc.get('id') == TASK, 'one portable task qualification')
        conditions = exact(registry_doc['program_conditions'], (ALIAS,))
        campaign = self._load_full('tools/neurobench_campaign.py', '_portable_original_campaign')
        for condition, meta in (('default', registry_doc['program_execution']), (ALIAS, conditions[ALIAS])):
            need(same(meta['entrypoint'], self.route(condition)) and
                 same(meta['source_freeze'], rel_desc(self.root, self.instance['source_freeze'])), 'actual full task source/route qualification')
            verification = meta.get('verification', {})
            need(verification.get('status') == 'passed', 'actual independently supplied qualification required')
            # Bound every path and parse all three records before the unchanged
            # generic helper can follow a supplied locator. No WORK dependency.
            record_sizes = []
            for role in ('receipt', 'qualification', 'source_binding'):
                rel = relative(verification[role + '_path'])
                path = self.root / rel
                need(path.parent == self.root / QREL, 'fixed protected qualification namespace')
                ordinary_ancestors(path)
                size = integer(path.lstat().st_size, 1, BODY_CAP)
                d = {'path': str(path), 'bytes': size, 'sha256': digest(verification[role + '_sha256'])}
                self.read(d, scope='Q')
                record_sizes.append(size)
            # Conservative logical allowance includes actual helper rereads,
            # one possible maximum failing read and detection bytes. Reserving
            # is retained even if the original helper refuses.
            closure = sum(d['bytes'] + 1 for d in self.fixed_files.values())
            reserve = closure + sum(n + 1 for n in record_sizes) + self.instance['source_freeze']['bytes'] + 1
            reserve += 2 * (self.fixed_files[str(self.root / 'tools/neurobench_campaign_gate.py')]['bytes'] + 1)
            reserve += 2 * (self.manifest['files']['entry.py']['bytes'] + 1) + 16 * 2**20 + 1
            self.budget.charge('read_bytes', reserve)
            transient = self.budget.hold(16 * 2**20 + sum(80 * n for n in record_sizes) + 65536)
            try:
                selected = {**registry_doc, 'program_execution': meta}
                need(campaign.verified_program_runtime(self.root / JREL, selected, self.root) is True,
                     'real unchanged generic qualification predicate')
            finally:
                self.budget.release(transient)
            self.budget.check()
        return True

    def worker_manifest(self, kind, qualification_desc, installed_versions, numeric_source=None):
        need(kind in WORKER_ROLES, 'literal trusted worker kind')
        modules = {row['name']: row['source'] for row in self.parent_document['modules']}
        if kind == 'reference':
            need(numeric_source in [r['source'] for r in self.parent_document['auxiliary']], 'one exact full numerical source')
            modules['numeric'] = numeric_source
        else:
            need(numeric_source is None, 'numeric source only in reference role')
        rows = [{'name': n, 'source': modules[n]} for n in WORKER_ROLES[kind]]
        manifest = {'schema': 'neural081_' + kind + '_source_manifest_v1',
                    'entry': modules[WORKER_ENTRIES[kind]], 'bootstrap': modules['worker_bootstrap'], 'modules': rows,
                    'dependency_qualification': descriptor(qualification_desc), 'installed_versions': installed_versions}
        q = self.read(qualification_desc, scope='operator')
        fields = {
            'preparation': ('schema', 'status', 'source', 'installed_versions', 'image_identity', 'independent_issuer', 'physical_io_enforcement', 'memory_enforcement', 'annotation_authority'),
            'reference': ('schema', 'status', 'numeric_source', 'installed_versions', 'image_identity', 'independent_issuer', 'physical_io_enforcement', 'memory_enforcement'),
            'issuer': ('schema', 'status', 'source', 'source_members', 'installed_versions', 'physical_namespace', 'scm_rights', 'independent_issuer'),
            'grader': ('schema', 'status', 'source', 'source_members', 'installed_versions', 'image_identity', 'independent_issuer', 'protected_custody'),
        }
        exact(q, fields[kind])
        schemas = {'preparation': 'neural081_preparation_environment_qualification_v1', 'reference': 'neural081_numerical_environment_qualification_v1',
                   'issuer': 'neural081_projection_issuer_qualification_v1', 'grader': 'neural081_grader_environment_qualification_v1'}
        # Original reference request.source is the separately selected complete
        # numerical source; other trusted roles bind the parent source.
        need(q['schema'] == schemas[kind] and q['status'] == 'qualified' and
             same(q['numeric_source' if kind == 'reference' else 'source'], numeric_source if kind == 'reference' else self.parent) and
             same(q['installed_versions'], installed_versions), 'actual exact worker environment record')
        if kind == 'preparation':
            binding = self.stage_record('selection/OPERANDS.json')['document']
            need(same(binding['source'], self.parent) and same(binding['run'], self.run_descriptor), 'same input qualification run/source')
            inputs = self.read(binding['input'], scope='operator')
            need(same(q['annotation_authority'], inputs['preparation']['annotation_authority']), 'same actual annotation qualification as original G0 request')
        if kind in ('issuer', 'grader'):
            need(same(q['source_members'], [manifest['entry'], manifest['bootstrap'], *[r['source'] for r in rows]]), 'complete exact worker source roster')
        package_keys = {'preparation': ('numpy', 'mne'), 'reference': ('numpy', 'scipy', 'sklearn'), 'issuer': ('numpy',), 'grader': ('python',)}
        exact(installed_versions, package_keys[kind])
        for value in installed_versions.values():
            need(type(value) is str and value, 'actual selected dependency version')
        if kind == 'reference':
            need(same(installed_versions, {'numpy': '2.2.6', 'scipy': '1.15.3', 'sklearn': '1.6.1'}), 'literal historical dependency versions')
        for name in fields[kind]:
            if name not in ('schema', 'status', 'source', 'numeric_source', 'source_members', 'installed_versions'):
                descriptor(q[name])
        return manifest

    def recheck(self):
        self.budget.check()
        capture_bytes(self.instance_descriptor, self.budget)
        capture_bytes(self.instance['profile'], self.budget)
        for desc in self.fixed_files.values():
            capture_bytes(desc, self.budget)
        for key in ('source_freeze', 'selection'):
            capture_bytes(self.instance[key], self.budget)
        for desc in list(self._metadata_reads.values()):
            capture_bytes(desc, self.budget)
        if self.run_descriptor is not None:
            need(same(self.read(self.run_descriptor, scope='operator'), self.run), 'unchanged original run on completion')
            self.stage_budget().check_clock()
        self.budget.check()

    def activate_registry(self, plan):
        need(self.stage == 'activate-route', 'one-path selected activation stage')
        exact(plan, ('schema', 'task_id', 'construction', 'source', 'registry_path', 'preimage', 'preimage_archive', 'generation', 'record_copies'))
        need(plan['schema'] == 'neural081_portable_registry_transaction_v1' and plan['task_id'] == TASK and
             same(plan['construction'], self.construction) and same(plan['source'], self.source) and
             plan['registry_path'] == str(self.root / JREL), 'exact one-task registry transaction')
        old = descriptor(plan['preimage'])
        need(old['path'] == str(self.root / JREL), 'exact current J preimage')
        need(same(self._metadata_reads.get(old['path']), old),
             'selected J is the exact remembered preimage')
        archived = self.read(plan['preimage_archive'], scope='V')
        previous_raw = capture_bytes(old, self.budget)
        need(same(parse(previous_raw), archived) and same(pin(previous_raw), {k: plan['preimage_archive'][k] for k in ('bytes', 'sha256')}), 'exact archived preimage')
        generation = self.read(plan['generation'], scope='V')
        self.generic_qualification(generation)
        expected = parse(previous_raw)
        for name in ('program_execution',):
            expected[name]['verification'] = generation[name]['verification']
        expected['program_conditions'][ALIAS]['verification'] = generation['program_conditions'][ALIAS]['verification']
        need(same(expected, generation), 'only two explicit verification fields change')
        need(type(plan['record_copies']) is list and len(plan['record_copies']) == 3, 'three separately issued qualification copies')
        for row, role in zip(plan['record_copies'], ('receipt', 'qualification', 'source_binding')):
            exact(row, ('role', 'origin', 'copy'))
            need(row['role'] == role, 'ordered exact qualification roles')
            self.read(row['origin'], scope='operator')
            self.read(row['copy'], scope='Q')
            need(same({k: row['origin'][k] for k in ('bytes', 'sha256')}, {k: row['copy'][k] for k in ('bytes', 'sha256')}), 'unchanged independently issued bytes')
        token = pin(encode(plan))['sha256']
        target, transaction_root = self.root / JREL, self.root / VREL
        ordinary_ancestors(transaction_root)
        ordinary_ancestors(target.parent)
        vfd = os.open(transaction_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        tfd = None

        def close_directory(fd):
            original_error = sys.exc_info()[0] is not None
            try:
                os.close(fd)
            except BaseException:
                if not original_error:
                    raise

        try:
            tfd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            v_identity, t_identity = os.fstat(vfd), os.fstat(tfd)
            need(v_identity.st_dev == t_identity.st_dev, 'same filesystem for atomic V to J replacement')

            def check_directories():
                for path, fd, identity in ((transaction_root, vfd, v_identity),
                                           (target.parent, tfd, t_identity)):
                    ordinary_ancestors(path)
                    named, held = path.lstat(), os.fstat(fd)
                    need(stat.S_ISDIR(named.st_mode) and stat.S_ISDIR(held.st_mode) and
                         (named.st_dev, named.st_ino) == (identity.st_dev, identity.st_ino) ==
                         (held.st_dev, held.st_ino), 'unchanged held transaction directories')

            check_directories()
            intent = self.write('V', 'intent-' + token + '.json',
                                {'schema': 'neural081_portable_registry_intent_v1',
                                 'plan': plan, 'automatic_retry': False})
            temporary = transaction_root / ('.portable-' + token + '.json')
            raw = capture_bytes(plan['generation'], self.budget)
            # All lock/staging/observation bodies are inside V. Only the exact
            # selected J replacement mutates a namespace outside V.
            lock = transaction_root / '.portable-registry.lock'
            check_directories()
            fd = os.open(lock.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=vfd)
            lock_identity = os.fstat(fd)
            os.close(fd)
            changed = False
            try:
                os.fsync(vfd)
                self.budget.check()
                check_directories()
                publish_bytes(transaction_root, temporary, raw, self.budget)
                need(capture_bytes(old, self.budget) == previous_raw,
                     'original preimage immediately before replacement')
                need(same(self._metadata_reads.get(old['path']), old),
                     'only selected remembered J may transition')
                check_directories()
                self.budget.check()
                os.replace(temporary.name, target.name, src_dir_fd=vfd, dst_dir_fd=tfd)
                changed = True
                # Cross-directory rename requires both namespace flushes.
                os.fsync(vfd)
                os.fsync(tfd)
                check_directories()
                self.budget.check()
                current = {'path': str(target), **pin(raw)}
                need(capture_bytes(current, self.budget) == raw, 'exact durable new registry')
                # The original J is retained in the immutable plan/archive.
                # No other remembered read changes; both final rechecks now
                # authenticate this one explicitly selected current identity.
                need(same(self._metadata_reads.get(old['path']), old),
                     'unchanged selected remembered J until durable transition')
                self._metadata_reads[old['path']] = dict(current)
                result = self.write('V', 'result-' + token + '.json',
                                    {'schema': 'neural081_portable_registry_result_v1',
                                     'intent': intent, 'preimage': old, 'postimage': current,
                                     'runtime_executed': False})
                self.budget.check()
                return result
            except BaseException:
                # Keep original intent, temporary and current J as found. Any
                # failed sync/readback/record leaves an unknown result; no retry.
                try:
                    self.write('V', 'failure-' + token + '.json',
                               {'schema': 'neural081_portable_registry_failure_v1',
                                'intent': intent, 'replacement_returned': changed,
                                'final_state_requires_independent_inspection': True,
                                'automatic_retry': False})
                except BaseException:
                    pass
                raise
            finally:
                original_error = sys.exc_info()[0] is not None
                try:
                    check_directories()
                    info = os.stat(lock.name, dir_fd=vfd, follow_symlinks=False)
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size == 0 and
                         (info.st_dev, info.st_ino) == (lock_identity.st_dev, lock_identity.st_ino),
                         'exact owned transaction lock at close')
                    os.unlink(lock.name, dir_fd=vfd)
                    os.fsync(vfd)
                    self.budget.check()
                except BaseException:
                    if not original_error:
                        raise
        finally:
            try:
                if tfd is not None:
                    close_directory(tfd)
            finally:
                close_directory(vfd)
