"""Closed S2 wire admission; records alone never confer live-owner authority."""
import re
import math
from .common import need, integer, same, bounded_size, descriptor, DependencyUnavailable
from .schema import check
from .precommit_tables import EXTERNAL_SCHEMAS
from .backend_schema_data import RECORDS as BASE_RECORDS, PRIMITIVES as BASE_PRIMITIVES
from .programme_schema_data import OUTPUT_RECORDS, OUTPUT_PRIMITIVES

need(not (set(BASE_RECORDS) & set(OUTPUT_RECORDS)) and
     not (set(BASE_PRIMITIVES) & set(OUTPUT_PRIMITIVES)),
     "disjoint root-adopted output additions preserve all original domains")
RECORDS = {**BASE_RECORDS, **OUTPUT_RECORDS}
PRIMITIVES = {**BASE_PRIMITIVES, **OUTPUT_PRIMITIVES}

DIMENSIONS = tuple(PRIMITIVES['Dimensions']['keys'])
CONDITIONS = tuple(PRIMITIVES['Condition']['values'])
_LIST = re.compile(r'^([A-Za-z][A-Za-z0-9_]*)\[([0-9]+):([0-9]+)\]$')

def scalar_text(value, minimum=1, maximum=4096):
    need(type(value) is str and minimum <= len(value) <= maximum, 'closed bounded scalar text')
    need(all(c != '\0' and not 0xD800 <= ord(c) <= 0xDFFF for c in value),
         'no NUL or lone surrogate')
    return value

def _literal(value, expected):
    need(same(value, expected), 'exact literal including builtin scalar type')

def validate_type(name, value, *, depth=0):
    need(depth <= 64, 'finite precommit type depth')
    if type(name) is dict:
        kind = name['kind']
        if kind == 'literal': _literal(value, name['value'])
        elif kind == 'boolean': need(type(value) is bool, 'exact boolean')
        elif kind == 'enum': need(any(same(value, v) for v in name['values']), 'closed typed enum')
        elif kind == 'nullable':
            if value is not None: validate_type(name['value_type'], value, depth=depth+1)
        else: need(False, 'known fixed inline type')
        return value
    need(type(name) is str, 'source-owned type name')
    if name == 'PreparedSourceClosureArray':
        # Root-adopted nominal target; all 102 base record bodies stay exact.
        return validate_type('Pin[1:8192]', value, depth=depth)
    if name.startswith('literal:'):
        _literal(value, RECORDS[name.split(':', 1)[1]]['schema_literal'])
        return value
    sequence = _LIST.fullmatch(name)
    if sequence:
        member, lo, hi = sequence.groups()
        need(type(value) is list and int(lo) <= len(value) <= int(hi), 'bounded exact sequence')
        for item in value: validate_type(member, item, depth=depth+1)
        return value
    if name in RECORDS:
        fields = RECORDS[name]['fields']
        need(type(value) is dict and set(value) == set(fields), 'all and only closed record fields')
        for key, member in fields.items(): validate_type(member, value[key], depth=depth+1)
        if name == 'Pin': descriptor(value)
        _relations(name, value)
        return value
    if name in EXTERNAL_SCHEMAS:
        check(value, EXTERNAL_SCHEMAS[name])
        # The historical schema did not separately reject lone surrogates.
        _unicode_tree(value, depth)
        if name in ('OriginalWholeEnvelope', 'OriginalWorkerEnvelope'): descriptor(value)
        if name == 'OriginalClock':
            need(value['origin_monotonic_ns'] < value['run_deadline_ns'] <= value['evidence_deadline_ns'],
                 'same finite original clock ordering')
        return value
    need(name in PRIMITIVES, 'fixed complete declared type')
    spec = PRIMITIVES[name]; kind = spec['kind']
    if kind == 'nullable':
        if value is not None: validate_type(spec['value_type'], value, depth=depth+1)
    elif kind == 'integer':
        need(type(value) is int and spec['minimum'] <= value <= spec['maximum'],
             'bounded exact integer, including signed exits; boolean is not an integer')
    elif kind == 'boolean': need(type(value) is bool, 'exact builtin boolean')
    elif kind == 'decimal':
        need(type(value) in (int, float) and math.isfinite(value) and
             spec['minimum'] <= value <= int(spec['maximum']), 'bounded finite builtin decimal')
    elif kind == 'union':
        need(type(value) is dict and type(value.get(spec['discriminator'])) is str,
             'closed union requires its actual schema discriminator')
        matches = [member for member in spec['alternatives']
                   if RECORDS[member]['schema_literal'] == value[spec['discriminator']]]
        need(len(matches) == 1, 'one exact current nominal union branch')
        validate_type(matches[0], value, depth=depth+1)
    elif kind == 'enum': need(any(same(value, v) for v in spec['values']), 'closed enum')
    elif kind == 'string':
        scalar_text(value, spec.get('minimum_length', 0), spec.get('maximum_length', 4096))
        if 'pattern' in spec: need(re.fullmatch(spec['pattern'], value) is not None, 'source-fixed text grammar')
    elif kind == 'closed_map':
        need(type(value) is dict and set(value) == set(spec['keys']), 'closed exact map')
        for item in value.values(): validate_type(spec['values'], item, depth=depth+1)
    elif kind == 'source_selected_external':
        if name == 'OriginalABIJobs':
            from .public_abi_grammar import validate_jobs
            validate_jobs(value)
            _unicode_tree(value, depth)
            return value
        if name == 'OriginalExpectedOutputs':
            # The original census owns this declaration's meaning and permits
            # task-specific JSON. Actual creators must additionally require
            # exact equality with the selected original job; this is shape only.
            bounded_size(value); _unicode_tree(value, depth)
            need(bool(value), 'original nonempty task-specific declaration')
            return value
        # Scientific template/output semantics require their concrete original
        # source consumer. A bounded JSON value is not an implementation of it.
        raise DependencyUnavailable(name, 'requires fixed original scientific/interface consumer admission')
    else: need(False, 'known source-fixed primitive kind')
    return value

def _unicode_tree(value, depth=0):
    need(depth <= 64, 'bounded external metadata depth')
    if type(value) is str: scalar_text(value, 0, 1048576)
    elif type(value) is dict:
        for key, child in value.items():
            scalar_text(key, 0, 4096); _unicode_tree(child, depth+1)
    elif type(value) is list:
        for child in value: _unicode_tree(child, depth+1)

def validate_record(name, value, meter):
    # Complete finite allocation bound is charged before recursive validation.
    meter.charge('work_units', bounded_size(value))
    return validate_type(name, value)

def _relations(name, value):
    if name in OUTPUT_RECORDS:
        from .programme_relations import relations
        relations(name, value)
    if name == 'BackendLimits':
        need(0 < value['microbatch_tokens'] <= value['batch_tokens'] <= value['context_tokens'] and
             value['maximum_generation_requests'] <= 8192 and value['maximum_header_bytes'] <= 65536 and
             value['maximum_response_bytes'] <= 1048576, 'fixed selected finite backend limits')
    elif name == 'BackendSampling':
        need(value['seed'] <= 4294967294 and value['temperature_milli'] <= 2000 and
             value['top_p_milli'] <= 1000 and value['min_p_milli'] <= 1000 and
             value['repeat_penalty_milli'] <= 4000, 'fixed bounded sampler without random sentinel')
    elif name == 'LocalBackendProfile':
        need(value['sampling']['top_k'] <= value['limits']['context_tokens'], 'selected top_k within context')
    elif name in ('BackendAttemptBase', 'BackendAttempt'):
        need(value['initialization_deadline_ns'] <= value['generation_deadline_ns'] < value['shutdown_deadline_ns'],
             'original initialization/generation/protected-shutdown ordering')
        if name == 'BackendAttempt':
            need(value['snapshot_ordinal'] <= 2 and
                 (value['previous_snapshot'] is None) == (value['snapshot_ordinal'] == 0),
                 'at most three ordered completed snapshots; only first lacks predecessor')
            if value['snapshot_stage'] in ('postspawn','postinitialization'):
                need(value['spawn_state'] == 'acknowledged' and value['identity'] is not None and
                     value['identity_observation'] is not None and value['group_observation'] is not None and
                     value['first_error'] is None, 'complete actual original process observations before normal snapshot')
                need(value['state'] == ('spawned' if value['snapshot_stage']=='postspawn' else 'initialized'),
                     'exact normal snapshot phase')
            else: need(value['state'] in ('closed','failed','unknown'), 'terminal source state')
    elif name == 'BackendClosure' and value['status'] == 'complete':
        need(value['purpose']=='planned_protocol_shutdown' and value['exit_code']==0 and
             type(value['exit_code']) is int and value['first_error'] is None and
             not value['forced_group_cleanup'] and value['pending_requests']==0 and
             all(value[key] is not None for key in ('admission','initialization','server_identity',
                 'exit_observation','signal_observation','group_observation','socket_closure','stream_closure')),
             'complete planned server closure requires all actual earlier observations')
    elif name == 'BackendExchangeObservation' and value['status'] == 'complete':
        need(value['started_ns'] is not None and value['finished_ns'] is not None and
             value['response'] is not None and value['first_error'] is None and
             value['finished_ns'] >= value['started_ns'] and
             value['request_complete'] == value['response_complete'] == 'known_closed',
             'complete exchange requires original finished transfer observations')
    elif name in ('PreparationSuccess','PreparationFailure'):
        need([arm['condition'] for arm in value['arms']] == list(CONDITIONS), 'two original preparation arms in fixed order')
        if name == 'PreparationSuccess':
            need(all(arm[key] is not None for arm in value['arms'] for key in
                 ('workspace_observation','state_preparation','request','exposure','launch_request')),
                 'complete preparation captures precede same-handle promotion')
        for arm in value['arms']:
            need([operation['ordinal'] for operation in arm['operations']] == list(range(len(arm['operations']))),
                 'actual contiguous per-arm attempted operation prefix')
            need(all(operation['condition'] == arm['condition'] for operation in arm['operations']),
                 'original per-arm operation ownership')
        need([operation['ordinal'] for operation in value['shared_operations']] == list(range(len(value['shared_operations']))),
             'actual contiguous shared preparation prefix')
    elif name == 'CompletionRequest':
        need(value['prompt_bytes']==len(value['prompt'].encode('utf8')) and
             value['maximum_generated_tokens']==value['sampling']['maximum_generated_tokens'],
             'exact prompt extent and fixed generation count')
    elif name == 'CostPrefix':
        unknown = value['unknown_dimensions']
        need(len(set(unknown)) == len(unknown), 'unique unknown dimensions')
        for key, observed in value['observed'].items():
            need((observed is None) == (key in unknown), 'unknown observation is null, never zero')
        if not value['unfinished_span']:
            need(value['original_active_wall_start_ns'] is None and value['original_active_cpu_start_ns'] is None,
                 'closed span has no invented unfinished start')
    elif name == 'SelectionCapturePrefix':
        need(not value['parse_complete'] or value['complete_body'] is not None, 'parse needs actual complete body')
        need(not value['authenticated'] or value['parse_complete'], 'authentication follows complete parse')
        need(value['read_attempted'] or (value['observed_bytes'] == 0 and value['complete_body'] is None and
             value['retained_prefix'] is None and not value['parse_complete'] and not value['authenticated']),
             'unattempted capture has no observed bytes or body')
        need(value['observed_bytes'] <= value['requested_limit'], 'bounded returned selection bytes')
    elif name == 'PreselectionFailurePrefix':
        need(value['selection_capture']['authenticated'] is False, 'preselection cannot contain authenticated selection')
        need(value['first_error']['ordinal'] == 0, 'original first raw error')
        need([x['ordinal'] for x in value['secondary_errors']] == list(range(1, len(value['secondary_errors'])+1)),
             'actual strict observed secondary order')
    elif name == 'FailurePublication':
        need((value['state'] == 'complete') == (value['prefix_record'] is not None),
             'only complete actual publication supplies a prefix Pin')
    elif name == 'CreationCapture':
        need(not value['complete'] or (value['output'] is not None and value['first_error'] is None and
             value['started_ns'] is not None and value['finished_ns'] is not None and value['publication'] == 'complete'),
             'complete creation requires observed output and original enclosing return')
    elif name == 'MatchedSchedule':
        need(value['earliest_launch_ns'] <= value['latest_launch_ns'] and
             value['latest_launch_ns'] + value['duration_ns'] <= value['common_cutoff_ns'],
             'original absolute equal-duration launch window')
    elif name == 'DevelopmentAttempt':
        if value['spawn_state'] == 'acknowledged':
            need(value['identity'] is not None and value['original_start_ns'] is not None,
                 'acknowledgement requires actual observed identity')
        if value['spawn_state'] == 'not_attempted':
            need(value['identity'] is None and value['original_start_ns'] is None,
                 'unstarted process has no invented identity')
    elif name == 'DevelopmentPairClosure':
        need(value['completion_by_condition'][CONDITIONS[0]] != value['completion_by_condition'][CONDITIONS[1]],
             'two original arm completions')
