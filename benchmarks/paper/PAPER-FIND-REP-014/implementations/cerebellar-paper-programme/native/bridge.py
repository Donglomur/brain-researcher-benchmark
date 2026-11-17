"""Concrete source assembly and MATLAB argv for future trusted native phases.

Importing this module performs no native/data access. No subprocess runs here:
the owner's reviewed concrete Provider launches the returned absolute argv.
All candidates use their own programs; these wrappers are operator/reference.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

BINDINGS_CANONICAL_SHA256 = 'da0b31f07ffda70b7e6c64c572f185639099168847bcc3b24fed923268cc1a2e'

PREPARATION_FILES = ('nb_i_prepare.m','nb_i_array.m','nb_i_bytes.m',
                     'nb_i_reserve.m','nb_i_hash.m','nb_i_census.m','nb_i_typed.m')
LIMIT_KEYS = {'max_files','max_file_bytes','max_output_bytes',
              'max_metadata_bytes','max_collection_items','max_native_elements'}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def strict(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, 'Duplicate metadata key')
            out[key] = value
        return out
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def leaf(root, relative):
    need(type(relative) is str and relative and not relative.startswith('/'), 'Relative exact source path')
    p = PurePosixPath(relative)
    need(str(p) == relative and all(x not in ('.', '..') for x in p.parts), 'Canonical source path')
    root = Path(root)
    need(root.is_absolute() and root.resolve() == root and not root.is_symlink(), 'Absolute trusted source root')
    current = root
    for component in p.parts:
        current = current / component
        need(not current.is_symlink(), 'No linked source component')
    return current


def capture(root, record, cap):
    need(type(record) is dict and {'path','bytes','sha256'} <= set(record), 'Exact immutable source pin')
    need(type(record['bytes']) is int and 0 <= record['bytes'] <= cap, 'Prospective source extent')
    need(re.fullmatch('[0-9a-f]{64}', record['sha256']) is not None, 'Source SHA256')
    path = leaf(root, record['path'])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == record['bytes'], 'Ordinary exact source body')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(record['bytes'] + 1)
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Stable source identity')
        need(pin(raw) == {k: record[k] for k in ('bytes','sha256')}, 'Exact source bytes/SHA')
        raw.decode('utf-8')
        need(b'\x00' not in raw, 'Text source only')
        return raw
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as error:
            if primary is None:
                raise
            if hasattr(primary, 'add_note'):
                primary.add_note('Source descriptor close failed: ' + repr(error))


def validate_bindings(bindings):
    need(hashlib.sha256(json.dumps(bindings, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest() == BINDINGS_CANONICAL_SHA256, 'Exact immutable original source binding, not caller-selected membership')
    need(bindings.get('schema') == 'filio_i_native_source_bindings_v1', 'Exact native binding schema')
    originals, wrappers = bindings['original_files'], bindings['wrappers']
    need(len(originals) == 42 and len(wrappers) == 9 and len(bindings['helpers']) == 3, 'Full authenticated source scope')
    need(len(bindings['inputs']) == 10 and sum(x['bytes'] for x in bindings['inputs']) == 9549118950, 'Full ten original objects')
    need(set(x['branch'] for x in wrappers) == set(bindings['branches']), 'All original branch bindings')
    need(sum(len(x['targets']) for x in bindings['branches'].values()) == 67, 'All declared native roots')
    targets = [x['target'] for x in originals + wrappers + bindings['helpers']]
    need(len(targets) == len(set(targets)), 'Unique complete source destinations')
    return bindings


def assembly_plan(original_root, helper_root, bindings, helper_pins, role):
    """Return a complete pinned copy plan; no source/body reads or execution."""
    need(role in ('operator', 'reference'), 'Private wrappers exclude A and B')
    validate_bindings(bindings)
    need(type(helper_pins) is dict and set(helper_pins) == set(PREPARATION_FILES), 'Complete reviewed preparation source pins')
    plan = []
    for row in bindings['original_files'] + bindings['wrappers'] + bindings['helpers']:
        plan.append({'root': str(Path(original_root)), 'record': {k: row[k] for k in ('path','bytes','sha256')}, 'target': row['target']})
    for name in PREPARATION_FILES:
        p = helper_pins[name]
        need(set(p) == {'bytes','sha256'}, 'Exact helper pin')
        plan.append({'root': str(Path(helper_root)), 'record': {'path': name, **p}, 'target': name})
    need(len(plan) == 61, 'Whole native source graph')
    return plan


def assemble(workspace, plan, max_read_bytes, max_write_bytes):
    """Populate one new trusted workspace from exact reviewed source bodies.

    No original arrays are read. Copies are exclusive and fully checked. The
    caller journals and retires this workspace even when a copy fails.
    """
    workspace = Path(workspace)
    need(workspace.is_absolute() and workspace.parent.resolve() == workspace.parent and not workspace.exists() and not workspace.is_symlink(), 'Fresh absolute owned workspace')
    need(type(plan) is list and len(plan) == 61, 'Full reviewed source graph')
    total = sum(x['record']['bytes'] for x in plan)
    need(type(max_read_bytes) is int and type(max_write_bytes) is int and total <= min(max_read_bytes,max_write_bytes), 'Complete source copy reservation')
    need(len({x['target'] for x in plan}) == len(plan), 'No duplicate source target')
    captured = [(row, capture(row['root'], row['record'], max_read_bytes)) for row in plan]
    workspace.mkdir(mode=0o700)
    files = []
    for row, raw in captured:
        destination = leaf(workspace, row['target'])
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        primary = None
        try:
            view = memoryview(raw)
            offset = 0
            while offset < len(raw):
                written = os.write(fd, view[offset:])
                need(type(written) is int and 0 < written <= len(raw)-offset, 'Complete source write progress')
                offset += written
            os.fsync(fd)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                os.close(fd)
            except BaseException as error:
                if primary is None:
                    raise
                if hasattr(primary, 'add_note'):
                    primary.add_note('Source copy close failed: ' + repr(error))
        files.append({'path': row['target'], **pin(raw)})
    for directory in sorted({workspace, workspace.parent, *(leaf(workspace, r['target']).parent for r in plan)}, key=lambda p: len(p.parts), reverse=True):
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        primary = None
        try:
            os.fsync(fd)
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                os.close(fd)
            except BaseException as error:
                if primary is None:
                    raise
                if hasattr(primary, 'add_note'):
                    primary.add_note('Source directory close failed: ' + repr(error))
    return {'schema':'filio_i_native_workspace_v1','files':files,
            'logical_read_bytes':total,'logical_write_bytes':total,
            'native_execution':False,'role':'operator_or_reference_only'}


def matlab_string(value):
    need(type(value) is str and value.startswith('/') and not any(ord(c) < 32 for c in value), 'Absolute native path with no control characters')
    return "'" + value.replace("'", "''") + "'"


def launch_spec(action, matlab, workspace, data_root, output_root, role,
                branch=None, limits_path=None, initial_seed=None):
    """Exact argv for a fresh engine-controlled process; never invokes MATLAB."""
    need(role in ('operator','reference'), 'Private native operator/reference role')
    paths = [matlab, workspace, data_root, output_root]
    need(all(type(x) is str and x.startswith('/') for x in paths), 'Absolute approved native locations')
    prefix = 'addpath(' + matlab_string(workspace) + ',' + matlab_string(workspace+'/dependencies') + ');'
    if action == 'prepare':
        need(role == 'operator' and branch is None and initial_seed is None, 'Preparation has no scientific branch or RNG override')
        expression = prefix + 'nb_i_prepare(' + ','.join(matlab_string(x) for x in (data_root,output_root,limits_path)) + ');'
        outputs = ['PREPARED.json', 'all declared primitive NPY files']
    else:
        need(action == 'branch' and role == 'reference' and limits_path is None, 'Exact independent original reference action')
        need(branch in ('MainData','learningCurves_DA','CF_novice','IOChRmine','learningCurves_IOChRmine','IOChRmine_imaging','passiveMFB','gtacr1','learningCurves_gtacr1'), 'Original branch only')
        need(type(initial_seed) is int and 0 <= initial_seed < 2**32, 'Explicit repeatability seed, not historical seed evidence')
        expression = prefix + 'rng(' + str(initial_seed) + ",'twister');nb_run_" + branch + '(' + matlab_string(data_root) + ',' + matlab_string(output_root+'/NATIVE.json') + ');'
        outputs = ['NATIVE.json']
    return {'argv':[matlab,'-batch',expression],'cwd':'/work','action':action,
            'role':role,'required_outputs':outputs,'native_runtime_qualified':False,
            'scientific_execution_authorized':False}


def resolve_variable_owners(files_census):
    """Exact original load(file1);load(file2) last-assignment precedence.

    Only metadata is inspected. Actual loaded classes/axes and immutable file
    identity must also be admitted; names never imply their owner filename.
    """
    need(type(files_census) is list, 'Complete per-file variable census')
    by_name = {}
    for record in files_census:
        need(type(record) is dict and type(record.get('file')) is str and record['file'] not in by_name, 'Unique source-file census')
        by_name[record['file']] = record
    owners = {}
    for index, name in enumerate(('mainData1.mat','mainData2.mat'),1):
        need(name in by_name, 'Both original MainData censuses')
        variables = by_name[name].get('variables')
        need(type(variables) is list and all(type(v) is dict and type(v.get('name')) is str for v in variables), 'Exact source variable names')
        names = [v['name'] for v in variables]
        need(len(names)==len(set(names)), 'Unique variable names within each source file')
        for key in ('micedats1','micedats2','dirTable'):
            if key in names:
                owners[key] = {'file':name,'variable':key,'load_index':index}
    need(set(owners)=={'micedats1','micedats2','dirTable'}, 'All required variables after sequential original loads')
    return owners
