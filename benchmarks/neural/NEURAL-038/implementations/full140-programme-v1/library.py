"""NEURAL-038 source loading and explicitly separate numerical phase bounds."""
import builtins
import hashlib
from pathlib import Path
import shutil
import time
import types

HERE = Path(__file__).absolute().parent
SOURCE = {'bytes': 2070, 'sha256': 'd40d9c4c5d0cd10c3e286ae4e8f3019ba7f7865a015569f140ccf48a6f07cb61'}
BOOTSTRAP = {'bytes': 1613, 'sha256': 'da3efeb07fe97a3916f1e01df6916b00fe61a55f1bef0ad68fd4f2b174f80977'}
EVALUATOR = 'benchmarks/neural/NEURAL-038/implementations/numerical-investigation-v1'
FILES = ('library.py', 'run.py', 'grade.py', 'DEPENDENCIES.json')
FLOOR = 60 * 2**30
FLOOR_UPLIFT = 40 * 2**30
READS = 64 * 2**20
WRITES = 32 * 2**20
MEMORY = 2**30


def runtime(deadline):
    filename = HERE / 'runtime/bootstrap.py'
    if any(p.is_symlink() for p in (filename, *filename.parents)):
        raise ValueError('Unlinked local source')
    raw = filename.read_bytes()
    if {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} != BOOTSTRAP:
        raise ValueError('Original bootstrap pin')
    module = types.ModuleType('_neural038_original_bootstrap')
    module.__file__ = str(filename)
    exec(compile(raw, module.__file__, 'exec'), module.__dict__)
    common, manifest, bodies, _ = module.load(filename.parent, SOURCE, deadline)
    return common, manifest, bodies, dict(SOURCE)


def source_identity(common):
    return {name: common.pin(common.capture(HERE / name, 262144)) for name in FILES}


def evaluator(repository, common):
    repository = common.path(repository)
    manifest = common.parse(common.capture(HERE / 'DEPENDENCIES.json', 65536))
    names = ('analysis_core', 'scorer_core', 'delivery_io', 'evaluate')
    common.need(manifest['schema'] == 'neural038_current_numerical_dependencies_v1'
                and manifest['accepted_commit'] == '31c05a9d2675c7d4235f7a8a0df88c88981b9395'
                and set(manifest['files']) == {EVALUATOR + '/' + name + '.py' for name in names},
                'Exact accepted current evaluator closure')
    bodies = {name: common.capture(repository / name, 262144, pin) for name, pin in manifest['files'].items()}
    modules = {}

    def load(name):
        if name in modules:
            return modules[name]
        common.need(name in names, 'Fixed evaluator module')
        filename = EVALUATOR + '/' + name + '.py'
        module = types.ModuleType('_neural038_current_' + name)
        module.__file__ = str(repository / filename)
        scope = dict(vars(builtins)); original = builtins.__import__
        def importer(target, globals=None, locals=None, fromlist=(), level=0):
            if level == 0 and target in names:
                return load(target)
            return original(target, globals, locals, fromlist, level)
        scope['__import__'] = importer
        module.__dict__['__builtins__'] = scope
        modules[name] = module
        exec(compile(bodies[filename], module.__file__, 'exec'), module.__dict__)
        return module

    return load('evaluate'), load('delivery_io'), modules


def profile(seconds):
    if type(seconds) is not int or not 1 <= seconds <= 600:
        raise ValueError('Explicit separate numerical duration, 1–600 seconds')
    return {'seconds': seconds, 'memory_bytes': MEMORY, 'numerical_threads': 1,
            'managed_read_cap': READS, 'write_retained_cap': WRITES,
            'authentic_runtime_qualified': False, 'memory_enforcement': 'external supervisor required'}


def disjoint_roots(common, *values):
    paths = [common.path(value) for value in values]
    for position, first in enumerate(paths):
        for second in paths[position + 1:]:
            common.need(first != second and not first.is_relative_to(second) and not second.is_relative_to(first),
                        'Operator data, public source, original output and bridge output are disjoint roots')
    return paths


def authority(value, selection, identity, seconds):
    fields = {'schema', 'numeric_grading_authorized', 'source', 'program', 'wrapper_sources', 'profile',
              'authoring_context_id', 'one_frozen_program', 'public_files', 'primitive_arrays',
              'private_source_visible', 'source_history_attested_by_root'}
    if type(value) is not dict or set(value) != fields:
        raise ValueError('Exact independent numerical authority fields')
    if not (value['schema'] == 'neural038_full140_numerical_authority_v1'
            and value['numeric_grading_authorized'] is True and value['source'] == SOURCE
            and value['program'] == {k: selection['program'][k] for k in ('bytes', 'sha256')}
            and value['wrapper_sources'] == identity and value['profile'] == profile(seconds)
            and type(value['authoring_context_id']) is str and 1 <= len(value['authoring_context_id'].encode()) <= 256
            and value['one_frozen_program'] is True and type(value['public_files']) is int and value['public_files'] == 25
            and type(value['primitive_arrays']) is int and value['primitive_arrays'] == 18
            and value['private_source_visible'] is False and value['source_history_attested_by_root'] is True):
        raise ValueError('Separate source/program/numerical/exposure authority')
    return value


def closed(record):
    if not (type(record) is dict and record.get('natural_exit') is True and type(record.get('exit_code')) is int
            and record['exit_code'] == 0 and record.get('process_reaped') is True
            and record.get('process_group_absent') is True and record.get('streams_closed') is True
            and record.get('timed_out') is False and record.get('kill_sent') is False
            and record.get('error_type') is None and record.get('timer_disable_error', 'missing') is None
            and record.get('timer_restore_error', 'missing') is None):
        raise ValueError('Actual natural zero, reaping, streams, group absence and timer closure')


def floor(common, location, selected_other, legacy_remaining=0, bridge_remaining=WRITES):
    common.need(type(selected_other) is int and selected_other >= FLOOR_UPLIFT + WRITES,
                'Original OTHER includes current floor uplift and numerical reserve')
    other = selected_other - FLOOR_UPLIFT - WRITES
    common.need(shutil.disk_usage(location).free >= FLOOR + other + legacy_remaining + bridge_remaining,
                'Current 60 GiB floor plus other, legacy and numerical holds')


class NumericalBudget:
    """Task-specific managed traffic; conservative caller reservations are not refunded."""
    def __init__(self, common, output, other, end, legacy_remaining=0):
        self.common, self.output, self.other, self.end = common, Path(output), other, end
        self.legacy_remaining = legacy_remaining
        # Includes captured source loading, caller metadata/result readbacks and receipts.
        self.reads, self.writes = 8 * 2**20, 2**20

    def tick(self):
        self.common.before(self.end)

    def read(self, count):
        self.tick()
        self.common.need(type(count) is int and count >= 0 and self.reads + count <= READS, 'Additional numerical reads')
        self.reads += count

    def write(self, count):
        self.tick()
        self.common.need(type(count) is int and count >= 0 and self.writes + count <= WRITES, 'Additional numerical writes')
        self.writes += count
        used = self.common.inventory(self.output, WRITES, 16)[2]
        floor(self.common, self.output, self.other, legacy_remaining=self.legacy_remaining,
              bridge_remaining=max(0, WRITES - used))

    def record(self):
        return {'read_charges_and_reservations': self.reads, 'write_charges_and_reservations': self.writes,
                'physical_IO_measured': False, 'original_producer_costs_excluded_and_retained': True,
                'caller_read_reservation': 8 * 2**20, 'caller_write_reservation': 2**20}
