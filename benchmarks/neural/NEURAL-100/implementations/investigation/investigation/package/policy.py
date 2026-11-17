"""Explicit future authority for this separate inactive investigation condition."""
import re
from pathlib import Path
from grading import SCOPE


def selection(s, source):
    keys = {'schema', 'task_id', 'source', 'data_package', 'output', 'program',
            'docker_binary', 'docker_socket', 'image', 'candidate_seconds', 'grade_seconds',
            'memory_bytes', 'grade_memory_bytes', 'cpu_count', 'holder_memory_bytes',
            'host_numpy_version', 'other_future_bytes', 'scope', 'managed_reads',
            'managed_writes', 'retained_bytes', 'whole_seconds', 'method_review',
            'runtime_review', 'execution_selected', 'numeric_grading_authorized',
            'claims_grading_authorized', 'case_adaptive', 'feedback_before_closure'}
    c.need(type(s) is dict and set(s) == keys, 'Exact investigation selection')
    c.need(s['schema'] == 'neural100_investigation_selection_v1'
           and s['task_id'] == 'NEURAL-100' and s['source'] == source and s['scope'] == SCOPE,
           'Selected full47/41/eight-condition source')
    for name in ('execution_selected', 'numeric_grading_authorized', 'claims_grading_authorized'):
        c.need(s[name] is True, 'New explicit authority required: ' + name)
    c.need(s['case_adaptive'] is False and s['feedback_before_closure'] is False,
           'Frozen programme, no intermediate feedback')
    for name in ('candidate_seconds', 'grade_seconds'):
        c.need(type(s[name]) is int and 2 <= s[name] <= 7200, 'Explicit bounded phase seconds')
    for name in ('memory_bytes', 'grade_memory_bytes'):
        c.need(type(s[name]) is int and 536870912 <= s[name] <= 4294967296
               and s[name] % 1048576 == 0, 'Explicit selected native memory')
    c.need(type(s['cpu_count']) is int and s['cpu_count'] == 1
           and type(s['holder_memory_bytes']) is int and s['holder_memory_bytes'] == 1073741824,
           'Explicit existing one-CPU/holder profile; no inferred runtime defaults')
    c.need(type(s['image']) is str and re.fullmatch(r'sha256:[0-9a-f]{64}', s['image']),
           'Immutable existing image')
    c.need(type(s['host_numpy_version']) is str and
           re.fullmatch(r'[0-9]+\.[0-9]+\.[0-9]+', s['host_numpy_version']), 'Selected host NumPy')
    for name, expected in (('managed_reads', c.READS), ('managed_writes', c.WRITES),
                           ('retained_bytes', c.RETAIN),
                           ('whole_seconds', s['candidate_seconds'] + s['grade_seconds'] + 1200)):
        c.need(type(s[name]) is int and s[name] == expected, 'Explicit complete reservation: ' + name)
    c.need(type(s['other_future_bytes']) is int and s['other_future_bytes'] >= 0,
           'Fresh outside reservation operand')
    for name in ('data_package', 'output', 'docker_binary', 'docker_socket'):
        c.need(type(s[name]) is str and Path(s[name]).is_absolute()
               and len(s[name].encode()) <= 512, 'Explicit bounded absolute operand')
        c.path(s[name])
    for name, cap in (('program', 131072), ('method_review', 32768), ('runtime_review', 32768)):
        row = s[name]
        c.need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}
               and type(row['path']) is str and Path(row['path']).is_absolute()
               and len(row['path'].encode()) <= 512, 'Pinned independent operand')
        c.need(c.only_pin(row)['bytes'] <= cap, 'Operand cap')
        c.path(row['path'])
    return s


def reviews(s, budget):
    for name in ('method_review', 'runtime_review'):
        operand = s[name]
        value = c.parse(c.capture(operand['path'], 32768, c.only_pin(operand),
                                 budget.tick, budget.read))
        c.need(type(value) is dict and value.get('task_id') == 'NEURAL-100'
               and value.get('approved') is True and value.get('source') == s['source']
               and value.get('program') == c.only_pin(s['program'])
               and value.get('scope') == SCOPE and value.get('other_future_bytes') == s['other_future_bytes'],
               'Independent source/program/scope/fresh-budget review')
        if name == 'method_review':
            c.need(value.get('schema') == 'neural100_investigation_method_review_v1', 'Method review')
            for key in ('full47_41_eight_conditions', 'unchanged_numerical_estimands',
                        'one_program_before_signal_access', 'both_artifacts_before_private_reference',
                        'odd_only_contact_matching', 'equal_mouse_missingness_and_shared_bootstrap',
                        'independent_full_reference_once', 'no_intermediate_feedback'):
                c.need(value.get(key) is True, 'Required method statement: ' + key)
            c.need(value.get('numerical_agreement_proves_reasoning') is False
                   and value.get('hashes_prove_chronology') is False, 'No stronger scientific claim')
        else:
            c.need(value.get('schema') == 'neural100_investigation_runtime_review_v1', 'Runtime review')
            profile = {k: s[k] for k in ('image', 'candidate_seconds', 'grade_seconds',
                                        'memory_bytes', 'grade_memory_bytes', 'cpu_count',
                                        'holder_memory_bytes', 'host_numpy_version')}
            c.need(value.get('profile') == profile and
                   value.get('native_versions') == {'python': '3.12', 'numpy': '2.2.6', 'h5py': '3.13.0'},
                   'Exact explicitly selected native/host profile')
            c.need(value.get('execution_boundary_qualified_for_this_source') is True
                   and value.get('independent_whole_process_observer_required') is True
                   and value.get('qualification_inherited') is False,
                   'New independent boundary review; no historical qualification transfer')
