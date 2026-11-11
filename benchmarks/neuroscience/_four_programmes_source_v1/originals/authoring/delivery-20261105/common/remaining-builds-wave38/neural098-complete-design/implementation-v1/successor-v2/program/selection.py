"""Closed source/operation/qualification admission; templates are disabled."""
import datetime
import math
import sys
from pathlib import Path
from .custody import descriptor, need, parse, read_pin

CONDITIONS = ('A_F', 'A_I', 'B_F', 'B_I')
OPERATIONS = ('prepare', 'admit-packet', 'derive-reference', 'evaluate', 'collect', 'grade', 'report', 'campaign')
GATES = tuple('G%02d' % i for i in range(1, 19))
CAUTIONS = {
    'C1': 'Broader sustained/transient inference/multiplicity obligation remains open.',
    'C2': 'Signal diagnostics show procedural data dependence, not native LLM understanding.',
    'C3': 'Six same-named sensors share device coordinates, not proven cortical-source alignment; actual head/SSS history required.'}


def inspect(bindings, source_sha):
    return {'schema': 'neural098-complete-programme-inspection-v1', 'task_id': 'NEURAL-098',
            'source_sha256': source_sha, 'conditions': list(CONDITIONS), 'stages': 15,
            'participants': 33, 'support_cells': 2376, 'fits_per_pipeline': 330,
            'accuracy_cells': 1386, 'contrasts': 792, 'open_gates': list(GATES),
            'scientific_cautions': CAUTIONS, 'source_dependency_count': len(bindings['source_files']),
            'scientific_execution': False, 'scientific_qualification': False}


def admit(selection, operation, source_sha):
    keys = {'schema', 'enabled', 'task_id', 'operation', 'whole_source_sha256', 'execution_authority',
            'budget', 'output_parent', 'output_name', 'operands', 'qualifications', 'exposure', 'conditions'}
    need(type(selection) is dict and set(selection) == keys, 'exact whole selection fields')
    need(selection['schema'] == 'neural098-complete-programme-selection-v1'
         and selection['enabled'] is True and selection['task_id'] == 'NEURAL-098', 'disabled/unselected programme')
    need(operation in OPERATIONS and selection['operation'] == operation, 'exact selected operation')
    need(selection['whole_source_sha256'] == source_sha, 'same complete source identity')
    authority = selection['execution_authority']
    need(type(authority) is dict and set(authority) == {'root_selected', 'scientific_execution_selected',
         'operation', 'whole_source_sha256', 'selection_id', 'expires_utc'}, 'explicit root execution authority')
    need(authority['root_selected'] is True and authority['scientific_execution_selected'] is True
         and authority['operation'] == operation and authority['whole_source_sha256'] == source_sha,
         'later root scientific operation selection required')
    need(type(authority['selection_id']) is str and len(authority['selection_id']) == 32
         and all(c in '0123456789abcdef' for c in authority['selection_id']), 'fresh selection identity')
    expiry = datetime.datetime.fromisoformat(authority['expires_utc'].replace('Z', '+00:00'))
    need(expiry.tzinfo is not None and expiry > datetime.datetime.now(datetime.timezone.utc), 'unexpired authority')
    need(type(selection['budget']) is dict and set(selection['budget']) ==
         {'wall_seconds', 'read_bytes', 'write_bytes', 'output_bytes', 'cpu_seconds', 'memory_bytes',
          'stream_bytes', 'pids', 'agent_tokens', 'agent_invocations'}, 'whole resource envelope')
    for k, v in selection['budget'].items():
        need(type(v) is int and 0 < v <= 2**50, 'positive selected resource: ' + k)
    need(type(selection['conditions']) is list and selection['conditions'] == list(CONDITIONS),
         'all four conditions, no favourable subset')
    need(type(selection['qualifications']) is dict and type(selection['operands']) is dict,
         'explicit selected operands/qualifications')
    need(type(selection['exposure']) is dict and selection['exposure'].get('family') == 'cogitate-family'
         and selection['exposure'].get('no_prior_related_hidden_label_claim') is True
         and selection['exposure'].get('fresh_independent_sessions') is True,
         'COGITATE-family and cross-condition exposure admission')
    return selection


def qualification(root, selected, role, source_sha, budget):
    """Selected external assurance is trusted only as explicitly pinned root input.

    It is never manufactured from successful source controls. Actual package
    imports follow source/environment authentication, not the reverse.
    """
    d = selected['qualifications'][role]
    q = parse(read_pin(root, d, 1_048_576, budget))
    fields = {'schema', 'role', 'qualified', 'whole_source_sha256', 'environment_id',
              'immutable_source_tree', 'exclusive_worker', 'native_versions', 'files', 'properties'}
    need(type(q) is dict and set(q) == fields and q['schema'] == 'neural098-runtime-assurance-v1'
         and q['qualified'] is True and q['role'] == role and q['whole_source_sha256'] == source_sha,
         'exact independently qualified selected environment')
    need(q['immutable_source_tree'] is True and q['exclusive_worker'] is True, 'qualified executing-source custody')
    need(type(q['environment_id']) is str and 0 < len(q['environment_id']) <= 256, 'environment identity')
    need(type(q['files']) is list and 0 < len(q['files']) <= 4096, 'complete selected runtime pin set')
    seen = set()
    need(sum(descriptor(x)['bytes'] + 1 for x in q['files']) <= 512_000_000,
         'bounded runtime authentication reservation')
    for x in q['files']:
        need(Path(x['path']).is_absolute() and x['path'] not in seen, 'unique absolute environment operand')
        seen.add(x['path'])
        read_pin(root, x, 256_000_000, budget)
    if role == 'analysis':
        need(str(Path(sys.executable).resolve()) in seen, 'selected actual analysis interpreter')
        need(q['native_versions'] == {'numpy': '2.2.6', 'scipy': '1.15.3',
             'sklearn': '1.6.1', 'pandas': '2.2.3'}, 'fixed analysis native versions')
        import importlib
        for name, version in q['native_versions'].items():
            m = importlib.import_module(name)
            need(m.__version__ == version and str(Path(m.__file__).absolute()) in seen,
                 'selected actual native module identity')
        for x in q['files']:
            read_pin(root, x, 256_000_000, budget)
    return q
