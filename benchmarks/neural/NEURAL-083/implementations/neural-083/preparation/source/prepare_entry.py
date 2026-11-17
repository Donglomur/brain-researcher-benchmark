"""Full-cohort NEURAL-083 preparation; source inspection never opens neural data.

This direct file and its interpreter are externally pinned trust roots. The
captured original methods are unchanged. No method issues independent admission.
"""
import argparse
import builtins
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

SOURCE_PIN = {'bytes': 2439, 'sha256': '6188e5b0becb3140ac48f0510855e9487c18fb2d20804fe52330ed2a3ce59dc3'}
INVENTORY_PIN = {'bytes': 41063, 'sha256': '4c7713e7e82b9c48f718e0c65811d21e70f42734626cd1af35d2808fe9cb3b44'}
ROSTER = tuple((p, s) for p in range(1, 55) for s in (1, 2))
NUMERIC_BYTES = 200 * 251 * 20 * 4
NAMES = ('protocol', 'delivery_io', 'array_io', 'provision', 'prepare', 'project_mat')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'Exact fields: ' + ','.join(fields))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')


def parse(raw):
    def pairs(rows):
        out = {}
        for k, v in rows:
            need(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: need(False, 'Finite JSON'))


def pin(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def content_pin(value):
    exact(value, ('bytes', 'sha256'))
    need(type(value['bytes']) is int and 0 < value['bytes'] <= 100000000000, 'Positive bounded pin')
    h = value['sha256']
    need(type(h) is str and len(h) == 64 and all(c in '0123456789abcdef' for c in h), 'SHA256 pin')
    return value


def ordinary(value):
    need(type(value) in (str, type(Path())), 'Path operand')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p) == os.path.normpath(str(p)), 'Normalized absolute path')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'No symlink ancestry')
    return p


def descriptor(value):
    exact(value, ('path', 'bytes', 'sha256'))
    ordinary(value['path'])
    content_pin({k: value[k] for k in ('bytes', 'sha256')})
    return value


def only_pin(value):
    return {k: value[k] for k in ('bytes', 'sha256')}


def stamp(s):
    return tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns'))


def read(path, expected, budget=None, identities=None, expected_identity=None):
    path = ordinary(path)
    content_pin(expected)
    if budget:
        budget.read(expected['bytes'] + 1)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == expected['bytes'], 'Pinned ordinary extent')
        need(expected_identity is None or stamp(a) == expected_identity, 'Same independently admitted input identity')
        chunks = []
        left = a.st_size + 1
        while left:
            if budget:
                budget.tick()
            block = os.read(fd, min(left, 65536))
            if not block:
                break
            chunks.append(block)
            left -= len(block)
        body = b''.join(chunks)
        need(stamp(a) == stamp(os.fstat(fd)) == stamp(path.lstat()) and pin(body) == expected, 'Stable exact complete body')
        if identities is not None:
            identities.append(stamp(a))
        return body
    finally:
        os.close(fd)


def load_descriptor(value, budget):
    descriptor(value)
    need(value['bytes'] <= 4000000, 'Metadata member cap')
    return parse(read(value['path'], only_pin(value), budget))


class Budget:
    """Explicit cumulative host reservations, with a separately reserved failure record.

    Native CPU/memory/physical I/O enforcement belongs to the selected supervisor.
    No source-only check creates that qualification.
    """
    def __init__(self, limits, deadline_ns):
        exact(limits, ('read_bytes', 'write_bytes', 'retained_bytes'))
        need(all(type(n) is int and 65536 <= n <= 1000000000000 for n in limits.values()), 'Explicit positive complete-operation limits')
        need(type(deadline_ns) is int and deadline_ns > 0, 'Original monotonic deadline')
        self.limits = limits
        self.deadline_ns = deadline_ns
        self.reads = 0
        self.writes = 65536
        self.failure_used = False
        self.tick()

    def tick(self):
        need(time.monotonic_ns() < self.deadline_ns, 'Original deadline elapsed')

    def read(self, n):
        need(type(n) is int and n >= 0 and self.reads + n <= self.limits['read_bytes'], 'Cumulative read reservation')
        self.reads += n
        self.tick()

    def write(self, n):
        need(type(n) is int and n >= 0 and self.writes + n <= self.limits['write_bytes'], 'Cumulative write reservation')
        self.writes += n
        self.tick()

    def record(self):
        return dict(read_reservations=self.reads, write_reservations=self.writes, failure_reserve_bytes=65536,
                    snapshot_before_enclosing_receipt_publication=True,
                    native_memory_and_cpu_qualified=False, physical_io_measured=False)


def owned_directory(path, fresh=False):
    path = ordinary(path)
    parent = path.parent
    s = parent.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid() and s.st_mode & 0o022 == 0, 'Owned nonshared parent')
    if fresh:
        os.mkdir(path, 0o700)
    s = path.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid() and s.st_mode & 0o077 == 0, 'Operator-only owned directory')
    return path


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def put(path, raw, budget, failure=False):
    need(type(raw) is bytes and 0 < len(raw) <= 4000000, 'Bounded product')
    if failure:
        need(not budget.failure_used and len(raw) <= 65536, 'Single pre-reserved failure record')
        budget.failure_used = True
    else:
        budget.write(len(raw))
    path = ordinary(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    try:
        view = memoryview(raw)
        while view:
            n = os.write(fd, view)
            need(n > 0, 'Complete product write')
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    sync(path.parent)
    return pin(raw)


def source_capture(root):
    raw = read(str(root / 'SOURCES.json'), SOURCE_PIN)
    table = parse(raw)
    exact(table, ('schema', 'files'))
    need(table['schema'] == 'neural083_preparation_sources_v1' and len(table['files']) == 10, 'Exact ten original sources')
    bodies = {}
    total = len(raw)
    for name, spec in table['files'].items():
        need(name.startswith(('original/private/', 'original/public/', 'program/')) and '..' not in Path(name).parts, 'Closed source-relative path')
        exact(spec, ('bytes', 'sha256', 'origin'))
        total += spec['bytes']
        need(total <= 100000, 'Fixed source capture bound')
        bodies[name] = read(str(root / name), only_pin(spec))
    entry = ordinary(root / 'prepare_entry.py')
    size = entry.lstat().st_size
    need(0 < size <= 65536, 'Bounded externally trusted entry')
    # External selection of this direct entry precedes execution. This records
    # its stable source identity; it is not a self-authenticating trust grant.
    fd = os.open(entry, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_size == size, 'Ordinary selected entry')
        body = os.read(fd, size + 1)
        need(len(body) == size and stamp(a) == stamp(os.fstat(fd)) == stamp(entry.lstat()), 'Stable selected entry source')
    finally:
        os.close(fd)
    return bodies, total + size, dict(original_manifest=SOURCE_PIN, entry=pin(body))


class LazyArray(types.ModuleType):
    def __init__(self, libraries):
        super().__init__('neural083_original_array_io')
        self.libraries = libraries
        self.loaded = None

    def __getattr__(self, key):
        if self.loaded is None:
            self.loaded = self.libraries.compile('original/public/array_io.py')
        value = getattr(self.loaded, key)
        if key == 'write':
            def write_array(path, arr, cap):
                path = ordinary(path)
                need(path in self.libraries.output_arrays, 'Only planned original array output')
                self.libraries.budget.write(cap)
                return value(path, arr, cap)
            return write_array
        return value


class Libraries:
    """Task-specific captured original imports; array dependency loads only on use."""
    def __init__(self, root, bodies, budget, identity, reads=None):
        self.root, self.bodies, self.budget = root, bodies, budget
        self.identity = identity
        self.reads = {} if reads is None else dict(reads)
        self.outputs = set()
        self.output_arrays = set()
        self.captured_identities = {}
        self.modules = {}
        self.real_import = builtins.__import__
        self.io = self.compile('original/public/delivery_io.py')
        self.original_read = self.io.read
        self.io.read = self.read
        self.original_put = self.io.put
        self.io.put = self.put
        self.modules['delivery_io'] = self.io
        self.modules['protocol'] = self.compile('original/public/protocol.py')
        self.modules['array_io'] = LazyArray(self)
        self.modules['provision'] = self.compile('original/private/provision.py')
        self.prepare = self.compile('original/private/prepare.py')
        self.project = self.compile('original/private/project_mat.py')
        self.common = self.compile('program/common.py')
        self.contracts = self.compile('program/contracts.py')
        bindings = dict(c=self.common, contracts=self.contracts, scientific=self.modules['protocol'])
        self.index = self.compile('program/index.py', **bindings)
        self.store = self.compile('program/store.py', **bindings)

    def compile(self, name, **bindings):
        module = types.ModuleType('neural083_preparation_' + name.replace('/', '_').replace('.', '_'))
        module.__file__ = str(self.root / name)
        imports = dict(vars(builtins), __import__=self.import_source)
        module.__dict__.update(__builtins__=imports, **bindings)
        exec(compile(self.bodies[name], module.__file__, 'exec'), module.__dict__)
        return module

    def import_source(self, name, globals=None, locals=None, fromlist=(), level=0):
        if name in self.modules:
            return self.modules[name]
        if name in NAMES:
            raise ValueError('Uncaptured original namespace')
        if name == 'sys':
            # Only original import-path setup uses sys; it cannot alter host sys.path.
            return types.SimpleNamespace(path=[])
        return self.real_import(name, globals, locals, fromlist, level)

    def read(self, path, cap, expected=None, empty=False, retain=True):
        path = ordinary(path)
        need(path in self.reads and not empty and retain, 'Only explicit pinned preparation inputs')
        descriptor = self.reads[path]
        need(descriptor['bytes'] <= cap and (expected is None or expected == only_pin(descriptor)), 'Original read cap and pin join')
        identities = []
        body = read(descriptor['path'], only_pin(descriptor), self.budget, identities=identities)
        self.captured_identities[path] = identities[0]
        return body

    def put(self, path, value, cap=524288):
        path = ordinary(path)
        need(path in self.outputs, 'Only planned original metadata output')
        raw = self.io.canonical(value)
        need(len(raw) <= cap, 'Original output cap')
        return put(path, raw, self.budget)


def common_request(request, kind):
    common = ('schema', 'source_manifest', 'source_inventory', 'records_root', 'deadline_ns', 'limits')
    extra = ('source_root', 'schema_bindings', 'max_record_output_bytes') if kind == 'project' else ('projection_record', 'identity_key', 'product_root')
    exact(request, common + extra)
    need(request['schema'] == 'neural083_' + kind + '_request_v1', 'Explicit operation schema')
    for key in ('source_manifest', 'source_inventory'):
        descriptor(request[key])
    need(only_pin(request['source_inventory']) == INVENTORY_PIN, 'Exact original provider inventory, never substitute a roster')
    ordinary(request['records_root'])
    if kind == 'project':
        ordinary(request['source_root'])
        n = request['max_record_output_bytes']
        need(type(n) is int and NUMERIC_BYTES + 100000 < n <= 8000000, 'Complete fixed array and metadata provision')
        bindings = request['schema_bindings']
        need(type(bindings) is list and len(bindings) == 108, 'All original schema bindings')
        for (p, s), row in zip(ROSTER, bindings):
            exact(row, ('person', 'session', 'binding'))
            need(type(row['person']) is int and type(row['session']) is int and (row['person'], row['session']) == (p, s), 'Numeric full binding order')
            descriptor(row['binding'])
    else:
        for key in ('projection_record', 'identity_key'):
            descriptor(request[key])
        need(request['identity_key']['bytes'] == 32, 'Exact separately selected private identity key')
        ordinary(request['product_root'])


def source_rows(request, libs):
    # The original provision function still validates against the exact original
    # inventory. Only its fixed IO location is relocated to the explicit operand.
    manifest = request['source_manifest']
    libs.reads[ordinary(manifest['path'])] = manifest
    inventory_location = libs.root / 'original/private/source/MI_ASSETS.json'
    libs.reads[inventory_location] = request['source_inventory']
    rows = libs.modules['provision'].load(manifest['path'])
    need([(r['person'], r['session']) for r in rows] == list(ROSTER) and all(type(r['person']) is int and type(r['session']) is int and type(r['bytes']) is int for r in rows), 'Strict full original numeric roster')
    return rows


def plan(request, kind, libs):
    common_request(request, kind)
    rows = source_rows(request, libs)
    result = dict(schema='neural083_preparation_plan_v1', operation=kind, source_manifest=only_pin(request['source_manifest']),
                  source_inventory=INVENTORY_PIN, records=108, people=54, sessions=2,
                  settings=list(libs.contracts.SETTINGS), arms=list(libs.contracts.ARMS), combined_conditions=2592,
                  native_fit_infer_phases=5184, numeric_payload_bytes=108 * NUMERIC_BYTES,
                  original_source_bytes=sum(r['bytes'] for r in rows), neural_inputs_opened=False)
    if kind == 'project':
        result['calls'] = [dict(person=r['person'], session=r['session'], path=r['path'], source_pin=only_pin(r),
                                binding_pin=only_pin(b['binding']), output=f"person{r['person']:02d}_session{r['session']}")
                           for r, b in zip(rows, request['schema_bindings'])]
    return result, rows


def fail(root, phase, error, completed, budget):
    # Preserve primary exception; do not turn a receipt failure into a successful result.
    try:
        put(root / 'FAILURE.json', encoded(dict(schema='neural083_preparation_failure_v1', phase=phase,
            completed_records=completed, error_type=type(error).__name__, error=str(error)[:8192], resources=budget.record())), budget, failure=True)
    except BaseException as extra:
        error.add_note('Failure receipt could not be published: ' + type(extra).__name__)


def project_all(request, libs):
    agenda, rows = plan(request, 'project', libs)
    budget = libs.budget
    root = ordinary(request['records_root'])
    need(not os.path.lexists(root), 'Fresh complete projection root')
    bindings = [load_descriptor(b['binding'], budget) for b in request['schema_bindings']]
    for binding in bindings:
        exact(binding, ('schema', 'channel_order', 'class_names_field', 'class_codes'))
        need(binding['schema'] == 'neural083_observed_mat_schema_v1' and binding['class_names_field'] in ('class', 'y_class'), 'Original observed schema')
        channels = binding['channel_order']
        need(type(channels) is list and len(channels) == 62 and all(type(x) is str and x for x in channels) and len(set(channels)) == 62, 'Complete observed channel order')
        exact(binding['class_codes'], ('left', 'right'))
        need(all(type(x) is int for x in binding['class_codes'].values()) and binding['class_codes']['left'] != binding['class_codes']['right'], 'Explicit observed semantic code binding')
    source_root = ordinary(request['source_root'])
    need(root != source_root and source_root not in root.parents and root not in source_root.parents, 'Disjoint original and owned output roots')
    need(108 * (request['max_record_output_bytes'] + 100000) + 1000000 <= budget.limits['retained_bytes'], 'Whole projected retained capacity, no cohort reduction')
    for row in rows:
        src = libs.io.resolve(source_root, row['path'])
        libs.reads[ordinary(src)] = dict(path=str(src), **only_pin(row))
    owned_directory(root, fresh=True)
    completed = []
    try:
        for row, binding in zip(rows, bindings):
            budget.tick()
            p, s = row['person'], row['session']
            out = root / f'person{p:02d}_session{s}'
            libs.outputs.add(out / 'record.json')
            libs.output_arrays.add(out / 'epochs.npy')
            result = libs.project.project(libs.io.resolve(source_root, row['path']), only_pin(row), binding, out, p, s, request['max_record_output_bytes'])
            libs.prepare.validate_record(result)
            record_pin = pin(libs.io.canonical(result))
            need(read(str(out / 'record.json'), record_pin, budget) == libs.io.canonical(result), 'Actual projected record matches return value')
            completed.append(dict(person=p, session=s, source_pin=result['source_pin'], schema_binding_pin=result['schema_binding_pin'], record_pin=record_pin, epochs=result['epochs']))
        receipt = dict(schema='neural083_projection_record_v1', source_closure=libs.identity, source_inventory=INVENTORY_PIN,
                       source_manifest=only_pin(request['source_manifest']), records=completed, complete=True,
                       independent_preparation_admission=False, resources=budget.record())
        output_pin = put(root / 'PROJECTION.json', encoded(receipt), budget)
        return dict(schema='neural083_projection_output_v1', projection_record=dict(path=str(root / 'PROJECTION.json'), **output_pin), records=108, independent_preparation_admission=False)
    except BaseException as error:
        fail(root, 'project', error, len(completed), budget)
        raise


def projection_record(request, libs, rows):
    value = load_descriptor(request['projection_record'], libs.budget)
    exact(value, ('schema', 'source_closure', 'source_inventory', 'source_manifest', 'records', 'complete', 'independent_preparation_admission', 'resources'))
    need(value['schema'] == 'neural083_projection_record_v1' and value['complete'] is True and value['independent_preparation_admission'] is False, 'Complete producing record, never independent admission')
    need(value['source_closure'] == libs.identity and value['source_inventory'] == INVENTORY_PIN and value['source_manifest'] == only_pin(request['source_manifest']), 'Exact producing-source and original roster joins')
    need(type(value['records']) is list and len(value['records']) == 108, 'Complete producing support')
    for native, row in zip(rows, value['records']):
        exact(row, ('person', 'session', 'source_pin', 'schema_binding_pin', 'record_pin', 'epochs'))
        need(type(row['person']) is int and type(row['session']) is int and (row['person'], row['session']) == (native['person'], native['session']) and row['source_pin'] == only_pin(native), 'Exact producing row join')
        for k in ('source_pin', 'schema_binding_pin', 'record_pin', 'epochs'):
            content_pin(row[k])
    return value


def assemble_products(records, secret, provenance_pin, libs):
    panel, targets = libs.prepare.make_panel(records, secret)
    index = libs.index.make_index(records, secret, provenance_pin)
    need(panel == libs.contracts.canonical(index), 'Actual original panel/index equality')
    need(len(panel['cases']) == 108 and sum(1 for _ in libs.contracts.schedule(panel)) == 2592, 'Complete scientific programme')
    return dict(index=index, panel=panel, targets=targets)


def array_before_seal(path, expected, libs):
    """Authenticate existing original array bytes before changing any file mode."""
    budget = libs.budget
    fd = os.open(ordinary(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_uid == os.geteuid() and a.st_size == expected['bytes'], 'Owned full ordinary array')
        budget.read(a.st_size)
        digest = hashlib.sha256()
        with os.fdopen(os.dup(fd), 'rb') as stream:
            offset = libs.store.npy_header(stream, (200, 251, 20), budget.read)
            need(a.st_size == offset + NUMERIC_BYTES, 'Full original numeric extent')
            stream.seek(0)
            while block := stream.read(65536):
                budget.tick()
                digest.update(block)
        need(digest.hexdigest() == expected['sha256'] and stamp(a) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'Stable full original array before seal')
        return stamp(a)
    finally:
        os.close(fd)


def seal_file(path, before, budget):
    fd = os.open(ordinary(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        budget.tick()
        need(stamp(os.fstat(fd)) == before == stamp(path.lstat()), 'Same owned file before mode change')
        os.fchmod(fd, 0o400)
        os.fsync(fd)
        budget.tick()
    finally:
        os.close(fd)
    sync(path.parent)


def private_key(value):
    """Admit custody without opening the secret body."""
    path = ordinary(value['path'])
    a = path.lstat()
    parent = path.parent.lstat()
    need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and a.st_uid == os.geteuid() and a.st_size == 32 and a.st_mode & 0o077 == 0,
         'Operator-owned private identity key')
    need(stat.S_ISDIR(parent.st_mode) and parent.st_uid == os.geteuid() and parent.st_mode & 0o077 == 0,
         'Operator-only identity-key parent')
    return stamp(a)


def finalize(request, libs):
    agenda, rows = plan(request, 'finalize', libs)
    budget = libs.budget
    root = owned_directory(request['records_root'])
    product = ordinary(request['product_root'])
    need(not os.path.lexists(product) and root != product and root not in product.parents and product not in root.parents, 'Fresh disjoint protected product root')
    key_identity = private_key(request['identity_key'])
    producing = projection_record(request, libs, rows)
    expected_dirs = {f'person{p:02d}_session{s}' for p, s in ROSTER}
    with os.scandir(root) as it:
        actual = []
        for e in it:
            need(len(actual) < 109, 'Bounded complete records root')
            actual.append(e.name)
    need(set(actual) == expected_dirs | {'PROJECTION.json'}, 'Exact complete projection root; no failure/extra members')
    need(ordinary(request['projection_record']['path']) == root / 'PROJECTION.json', 'Actual original projection record location')
    for row in producing['records']:
        d = root / f"person{row['person']:02d}_session{row['session']}"
        owned_directory(d)
        with os.scandir(d) as it:
            names = []
            for e in it:
                need(len(names) < 2, 'Bounded record directory')
                names.append(e.name)
        need(set(names) == {'record.json', 'epochs.npy'}, 'Exact original record pair')
        libs.reads[d / 'record.json'] = dict(path=str(d / 'record.json'), **row['record_pin'])
    records = libs.prepare.read_records(root, request['source_manifest']['path'])
    for record, captured in zip(records, producing['records']):
        need(record['epochs'] == captured['epochs'] and record['schema_binding_pin'] == captured['schema_binding_pin'], 'Original record to producing capture join')
    need(sum(r['epochs']['bytes'] for r in records) + 8000000 <= budget.limits['retained_bytes'], 'Full canonical plus protected product capacity')
    before = {}
    for row in records:
        path = root / f"person{row['person']:02d}_session{row['session']}" / 'epochs.npy'
        before[path] = array_before_seal(path, row['epochs'], libs)
    # No file mode is changed until every original array has passed admission.
    owned_directory(product, fresh=True)
    completed = 0
    try:
        for row in records:
            d = root / f"person{row['person']:02d}_session{row['session']}"
            seal_file(d / 'epochs.npy', before[d / 'epochs.npy'], budget)
            metadata_stamp = libs.captured_identities[d / 'record.json']
            need(metadata_stamp[3] == 1 and metadata_stamp[5] == os.geteuid(), 'Owned single-link original metadata')
            seal_file(d / 'record.json', metadata_stamp, budget)
            libs.store.authenticate_array(d / 'epochs.npy', row['epochs'], budget)
            os.chmod(d, 0o500)
            sync(d)
            completed += 1
        secret = read(request['identity_key']['path'], only_pin(request['identity_key']), budget, expected_identity=key_identity)
        products = assemble_products(records, secret, only_pin(request['projection_record']), libs)
        del secret
        published = {name: put(product / (name + '.json'), encoded(value), budget) for name, value in products.items()}
        raw_provenance = read(request['projection_record']['path'], only_pin(request['projection_record']), budget)
        published['projection_provenance'] = put(product / 'projection_provenance.json', raw_provenance, budget)
        seal_file(root / 'PROJECTION.json', stamp((root / 'PROJECTION.json').lstat()), budget)
        os.chmod(root, 0o500)
        sync(root)
        result = dict(schema='neural083_preparation_output_v1', canonical=dict(path=str(product / 'index.json'), **published['index']), canonical_root=str(root),
                      projection_provenance=published['projection_provenance'], panel=published['panel'], protected_targets=published['targets'],
                      records=108, query_trials=10800, combined_conditions=2592, independent_preparation_admission=False, resources=budget.record())
        put(product / 'COMPLETE.json', encoded(result), budget)
        os.chmod(product, 0o500)
        sync(product)
        return result
    except BaseException as error:
        fail(product, 'finalize', error, completed, budget)
        raise


def startup():
    need(sys.flags.isolated == 1 and sys.flags.ignore_environment == 1 and sys.flags.no_user_site == 1 and sys.flags.dont_write_bytecode == 1 and sys.dont_write_bytecode is True, 'Direct actual -I -B invocation required')
    value = sys._xoptions.get('pycache_prefix')
    need(type(value) is str and sys.pycache_prefix == value, 'Explicit -X pycache_prefix')
    p = ordinary(value)
    need(not os.path.lexists(p), 'Fresh absent cache prefix')
    s = p.parent.lstat()
    need(stat.S_ISDIR(s.st_mode) and s.st_uid == os.geteuid() and s.st_mode & 0o022 == 0, 'Owned cache parent')
    need(not any(name == n or name.startswith(n + '.') for name in sys.modules for n in NAMES), 'No preloaded original namespaces')


def main():
    startup()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('inspect', 'plan-project', 'plan-finalize', 'project', 'finalize'))
    parser.add_argument('--request', type=Path)
    parser.add_argument('--request-bytes', type=int)
    parser.add_argument('--request-sha256')
    args = parser.parse_args()
    here = Path(__file__).absolute().parent
    bodies, captured, identity = source_capture(here)
    if args.command == 'inspect':
        need(args.request is None and args.request_bytes is None and args.request_sha256 is None, 'Inspect accepts no data operand')
        print(json.dumps(dict(original_source_members=10, source_identity=identity, captured_source_bytes=captured, records=108, people=54, sessions=2, combined_conditions=2592, scientific_execution=False)))
        return
    need(args.request is not None and args.request_bytes is not None and args.request_sha256 is not None, 'Pinned explicit operation request')
    expected = dict(bytes=args.request_bytes, sha256=args.request_sha256)
    need(0 < args.request_bytes <= 262144, 'Bounded request')
    raw = read(str(args.request), expected)
    request = parse(raw)
    kind = 'project' if args.command.endswith('project') else 'finalize'
    common_request(request, kind)
    budget = Budget(request['limits'], request['deadline_ns'])
    budget.read(captured + len(raw) + 13)
    libs = Libraries(here, bodies, budget, identity)
    if args.command.startswith('plan-'):
        result, _ = plan(request, kind, libs)
    elif kind == 'project':
        result = project_all(request, libs)
    else:
        result = finalize(request, libs)
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
