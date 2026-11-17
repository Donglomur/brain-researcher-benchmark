"""Owner-only relocation of the accepted full120 comparator.

No import-time I/O and no fallback to the historical Mac binding. Numerical
projection/validation and the five comparator files retain their donor bytes.
Only an owner-selected, source-authenticated binding supplies locations.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

from custody import decode, encoded, need, plain, read_pin, write_new
from full120_output import PROFILE, ORIGINAL

CONTRACT_BYTES = 1178
CONTRACT_SHA256 = '7f3d20eb0b136e62061ab76ffdcb1acdbfae7a81aca5b700835d378734115426'
COMPARATOR_NAMES = ('compare_local.py', 'custody.py', 'reporting_core.py',
                    'extended_score.py', 'reporting_resolution.py')
OWNER_KEYS = {'schema', 'profile', 'comparator_root', 'reference', 'python',
              'maximum_attempts'}


def required_read(entry, role, maximum=1048576):
    try:
        return read_pin(entry, maximum)
    except FileNotFoundError as error:
        raise ValueError('missing_owner_operand:' + role) from error


def contract():
    value = decode(required_read({'path': str(Path(__file__).with_name('FULL120_CONTRACT.json')),
                                  'bytes': CONTRACT_BYTES, 'sha256': CONTRACT_SHA256}, 'full120_contract'))
    need(type(value) is dict and set(value) == {'schema', 'profile', 'task', 'original_workbook_sha256',
         'reference', 'comparator_sources', 'criterion_partition', 'maximum_attempts'}, 'full120_contract_keys')
    need(value['schema'] == 'nider_full120_portable_contract_v1' and value['profile'] == PROFILE and
         value['task'] == 'PAPER-EXP-20261113-003' and value['original_workbook_sha256'] == ORIGINAL and
         value['criterion_partition'] == [27, 21, 72] and type(value['maximum_attempts']) is int and
         value['maximum_attempts'] == 1 and set(value['comparator_sources']) == set(COMPARATOR_NAMES),
         'full120_contract_scope')
    return value


def interpreter(entry):
    need(type(entry) is dict and set(entry) == {'path', 'bytes', 'sha256'} and
         type(entry['path']) is str and Path(entry['path']).is_absolute() and
         type(entry['bytes']) is int and 0 < entry['bytes'] <= 8388608 and
         type(entry['sha256']) is str and re.fullmatch('[0-9a-f]{64}', entry['sha256']),
         'full120_python_pin')
    p = plain(entry['path'])
    need(p == Path(sys.executable).resolve() and os.access(p, os.X_OK), 'full120_current_owner_interpreter')
    required_read(entry, 'owner_python', 8388608)
    return str(p)


def admit_owner(entry):
    """Authenticate every operand; this future operation reads private inputs."""
    fixed = contract()
    owner = decode(required_read(entry, 'full120_owner_binding', 65536))
    need(type(owner) is dict and set(owner) == OWNER_KEYS and
         owner['schema'] == 'nider_full120_portable_owner_request_v1' and owner['profile'] == PROFILE and
         type(owner['maximum_attempts']) is int and owner['maximum_attempts'] == 1,
         'full120_owner_request_scope')
    root = plain(owner['comparator_root'])
    need(root.is_dir(), 'missing_owner_operand:comparator_root')
    sources = {name: {'path': str(root / name), **fixed['comparator_sources'][name]}
               for name in COMPARATOR_NAMES}
    for name, pin in sources.items():
        required_read(pin, 'comparator_' + name)
    reference = owner['reference']
    need(type(reference) is dict and set(reference) == {'path', 'bytes', 'sha256'} and
         {k: reference[k] for k in ('bytes', 'sha256')} == fixed['reference'], 'full120_fixed_reference')
    required_read(reference, 'full120_reference', 65536)
    interpreter(owner['python'])
    paths = [str(plain(x['path'])) for x in [entry, reference, owner['python'], *sources.values()]]
    need(len(set(paths)) == len(paths), 'full120_unique_owner_operands')
    return fixed, owner, sources


def owner_lock(fixed, owner, sources):
    return {'schema': 'nider_full120_local_owner_lock_v1', 'task': fixed['task'],
            'modules': {name[:-3]: sources[name] for name in COMPARATOR_NAMES if name != 'compare_local.py'},
            'reference': owner['reference'], 'workbook_sha256': fixed['original_workbook_sha256'],
            'reference_arm': 'A', 'expected_fields': 120}


def prepare_binding(owner_entry, output):
    fixed, owner, sources = admit_owner(owner_entry)
    root = plain(output)
    root.mkdir(mode=0o700)
    lock = write_new(root / 'OWNER_LOCK.json', encoded(owner_lock(fixed, owner, sources)))
    bound = {'schema': 'nider_full120_portable_bound_v1', 'profile': PROFILE,
             'owner_request': owner_entry, 'sources': sources, 'reference': owner['reference'],
             'python': owner['python'], 'maximum_attempts': 1, 'owner_lock': lock,
             'criterion_partition': [27, 21, 72], 'root': str(root)}
    return write_new(root / 'BOUND.json', encoded(bound))


def admit_binding(entry):
    bound = decode(required_read(entry, 'prepared_full120_binding', 65536))
    need(type(bound) is dict and set(bound) == {'schema', 'profile', 'owner_request', 'sources',
         'reference', 'python', 'maximum_attempts', 'owner_lock', 'criterion_partition', 'root'} and
         bound['schema'] == 'nider_full120_portable_bound_v1' and bound['profile'] == PROFILE and
         type(bound['maximum_attempts']) is int and bound['maximum_attempts'] == 1 and
         bound['criterion_partition'] == [27, 21, 72], 'full120_bound_scope')
    fixed, owner, sources = admit_owner(bound['owner_request'])
    root = plain(bound['root'])
    need(plain(entry['path']) == root / 'BOUND.json' and
         bound['owner_lock']['path'] == str(root / 'OWNER_LOCK.json'), 'full120_bound_locations')
    need(bound['sources'] == sources and bound['reference'] == owner['reference'] and
         bound['python'] == owner['python'], 'full120_bound_owner_join')
    lock = required_read(bound['owner_lock'], 'prepared_full120_owner_lock', 65536)
    need(lock == encoded(owner_lock(fixed, owner, sources)), 'full120_bound_lock_join')
    return bound


def pins(entry):
    value = admit_binding(entry)
    return [entry, value['owner_request'], value['owner_lock'], value['reference'],
            value['python'], *value['sources'].values()]


def comparator_argv(binding_entry, response_pin, arm, fresh_output):
    bound = admit_binding(binding_entry)
    need(arm in ('A', 'B') and type(response_pin.get('bytes')) is int and
         0 < response_pin['bytes'] <= 65536, 'comparator_submission_scope')
    required_read(response_pin, 'frozen_candidate_response', 65536)
    root = plain(fresh_output)
    need(root.parent.is_dir() and not root.exists(), 'fresh_comparator_output')
    return [interpreter(bound['python']), '-B', bound['sources']['compare_local.py']['path'],
            bound['owner_lock']['path'], bound['owner_lock']['sha256'], arm,
            response_pin['path'], response_pin['sha256'], str(root)]


def verify_private_comparison(binding_entry, output, arm, candidate_pin):
    bound = admit_binding(binding_entry)
    output = plain(output)
    need(set(p.name for p in output.iterdir()) ==
         {'OWNER_REPORT.json', 'SUMMARY.json', 'INPUT_BINDING.json'}, 'full120_comparison_files')
    def get(name, maximum):
        p = plain(output / name)
        with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            before = os.fstat(stream.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                 before.st_size <= maximum, 'comparison_file_extent')
            b = stream.read(maximum + 1)
            after = os.fstat(stream.fileno())
        current = p.lstat()
        need(len(b) == before.st_size and all(getattr(before, k) == getattr(after, k) ==
             getattr(current, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_mode',
             'st_nlink', 'st_mtime_ns', 'st_ctime_ns')), 'comparison_changed_during_read')
        return decode(b), {'path': str(p), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    report, rpin = get('OWNER_REPORT.json', 262144)
    summary, spin = get('SUMMARY.json', 8192)
    inputs, ipin = get('INPUT_BINDING.json', 8192)
    need(inputs['owner_lock'] == {'path': bound['owner_lock']['path'], 'sha256': bound['owner_lock']['sha256']} and
         inputs['candidate'] == candidate_pin and inputs['owner_selected_arm'] == arm and
         inputs['reference'] == bound['reference'] and inputs['owner_only_reports'] is True,
         'full120_comparison_input_join')
    need(summary['arm'] == arm and summary['fields'] == 120 and summary['reported_real_fields'] == 27 and
         summary['exact_integer_fields'] == 21 and summary['continuous_only_real_fields'] == 72 and
         summary['aggregate_scientific_pass_defined'] is False and len(report['cells']) ==
         report['continuous_total_fields'] == 120 and report['continuous_fields_excluded'] == 0 and
         report['aggregate_binary_pass_defined'] is False, 'full120_comparison_complete_scope')
    return {'report': rpin, 'summary': spin, 'inputs': ipin, 'fields': 120, 'original_only': True,
            'aggregate_scientific_pass_defined': False}
