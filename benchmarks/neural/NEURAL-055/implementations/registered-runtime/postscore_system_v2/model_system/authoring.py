"""One pre-data F source and the fixed paired I submission; no data analysis."""
import ast
import hashlib
import json

from source_closure import need, parse

MAX_PROGRAM = 131072


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode('utf8')


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def keys(value, names):
    need(type(value) is dict and set(value) == set(names), 'closed authoring specification')


def positive(value, label):
    need(type(value) is int and value > 0, 'positive exact ' + label)
    return value


def recorded_pin(record, role):
    need(record['status'] == 'complete' and record['closed'] is True
         and record['observed_bytes'] == record['expected_bytes'], 'actual complete original publication')
    return {'path': record['path'], 'bytes': record['observed_bytes'],
            'sha256': record['sha256'], 'mode': '0o600', 'role': role}


def validate_spec(spec, session):
    keys(spec, ('prompt', 'max_new_tokens', 'max_rounds', 'response_bytes', 'feedback_bytes',
                'context_bytes', 'F_policy', 'common_dependencies', 'exposure_declaration'))
    need(type(spec['prompt']) is str and spec['prompt'].strip(), 'explicit nonempty authoring prompt')
    for name in ('max_new_tokens', 'max_rounds', 'response_bytes', 'feedback_bytes', 'context_bytes'):
        positive(spec[name], name)
    need(spec['max_rounds'] <= session.budget.limits['model_calls'], 'finite authoring turns inside actual call envelope')
    need(spec['response_bytes'] <= 8388608 and spec['context_bytes'] <= 1048576,
         'original provider wire ceilings')
    keys(spec['F_policy'], ('dependencies', 'services', 'inference_restrictions'))
    need(type(spec['F_policy']['dependencies']) is list and type(spec['F_policy']['services']) is list,
         'explicit complete F dependency and service declaration')
    need(all(type(x) is str and x for x in spec['F_policy']['services'])
         and len(set(spec['F_policy']['services'])) == len(spec['F_policy']['services']),
         'unique declared F services')
    need(session.spec['provider_id'] not in spec['F_policy']['services'],
         'offline authoring text provider is never an online F service')


def source_from_text(text, response_cap):
    """Only static syntax/entry-shape checks; never run submitted code."""
    need(type(text) is str, 'original generated text')
    raw = text.encode('utf8'); need(0 < len(raw) <= response_cap, 'bounded complete original response')
    value = parse(raw); keys(value, ('source',))
    need(type(value['source']) is str, 'one UTF-8 source body')
    body = value['source'].encode('utf8')
    need(0 < len(body) <= MAX_PROGRAM and b'\0' not in body, 'original participant source ceiling')
    tree = ast.parse(body, filename='F.py', mode='exec')
    need(any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'main'
             for node in tree.body), 'explicit top-level main entry for original CLI')
    constants = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and type(n.value) is str}
    need({'fit', 'infer', '--train', '--model-output', '--query', '--model', '--output'} <= constants,
         'literal original fit/infer CLI operands must be present')
    return body


def static_feedback(error, cap):
    """Bounded static feedback only; no arbitrary exception formatting."""
    result = {'kind': type(error).__name__, 'stage': 'static_source_validation',
              'no_data_or_numerical_feedback': True}
    if isinstance(error, SyntaxError):
        result.update(line=error.lineno, offset=error.offset,
                      message=str(error.msg)[:256] if type(error.msg) is str else 'invalid Python syntax')
    elif type(error) is ValueError and len(error.args) == 1 and type(error.args[0]) is str:
        result['message'] = error.args[0][:256]
    else:
        result['message'] = 'invalid bounded source representation'
    raw = encoded(result); need(len(raw) <= cap, 'selected static-feedback byte ceiling')
    return raw.decode('utf8')


def author_source(session, spec):
    validate_spec(spec, session)
    before = session.budget.cost_point(); history = []
    session.carrier.retain(history)
    instruction = {'instruction': spec['prompt'], 'public_documents': session.public_documents,
                   'exact_response': {'source': 'one complete UTF-8 Python programme as JSON string'},
                   'source_limit_bytes': MAX_PROGRAM,
                   'access': 'public source documents only; no neural/image arrays, statistics, bank results or outcomes',
                   'F_policy': spec['F_policy'], 'source_method_review_still_required': True}
    messages = [{'role': 'user', 'content': encoded(instruction).decode('utf8')}]
    source = None
    for number in range(spec['max_rounds']):
        session.budget.check('before next pre-data F author turn')
        need(len(messages) <= 128 and sum(len(m['content'].encode('utf8')) for m in messages) <= spec['context_bytes'],
             'complete pre-data context fits declared original envelope')
        request = {'label': 'offline-f-%04d' % number, 'messages': messages,
                   'max_new_tokens': spec['max_new_tokens'], 'public_interface': session.public_interface}
        request_record = session.json('AUTHOR_REQUEST_%04d.json' % number, request)
        row = {'turn': number, 'request': recorded_pin(request_record, 'offline_author_request'),
               'status': 'owned_before_model_dispatch', 'response': None, 'static_feedback': None}
        history.append(row)
        # A broker/native failure is fatal. Only successful text can receive a
        # selected static repair; no resetting counters or another backend.
        actual = session.generate(request['label'], messages, spec['max_new_tokens'])
        session.carrier.retain(actual)
        need(type(actual) is dict and {'text', 'usage', 'operation'} <= set(actual), 'actual original model result')
        keys(actual['usage'], ('input_tokens', 'output_tokens'))
        need(all(type(n) is int and n >= 0 for n in actual['usage'].values()), 'known actual original token counts')
        operation = actual['operation']
        need(type(operation) is dict and operation.get('closed') is True
             and type(operation.get('receipt')) is dict and operation.get('usage') == actual['usage'],
             'same closed original model job and durable receipt')
        need(type(actual['text']) is str, 'actual generated text')
        response_raw = actual['text'].encode('utf8')
        need(0 < len(response_raw) <= spec['response_bytes'], 'bounded original author text before publication')
        rr = session.write('AUTHOR_RESPONSE_%04d.json' % number, response_raw)
        row.update(response=recorded_pin(rr, 'offline_author_original_response'),
                   usage=actual['usage'], operation=actual['operation'], status='successful_model_text')
        session.budget.check('after original author text capture')
        try:
            source = source_from_text(actual['text'], spec['response_bytes'])
        except (SyntaxError, ValueError, UnicodeError, RecursionError) as error:
            feedback = static_feedback(error, spec['feedback_bytes'])
            fr = session.write('AUTHOR_FEEDBACK_%04d.json' % number, feedback.encode('utf8'))
            row.update(status='static_source_refused', static_feedback=recorded_pin(fr, 'offline_static_feedback'))
            if number + 1 == spec['max_rounds']:
                raise
            messages = [*messages, {'role': 'assistant', 'content': actual['text']},
                        {'role': 'user', 'content': feedback}]
        else:
            row['status'] = 'static_source_accepted_independent_semantics_unqualified'
            break
    need(source is not None, 'one actual authored F source')
    written = session.write('F.py', source)
    f_descriptor = recorded_pin(written, 'precommitted_F_source')
    receipt = {'schema': 'neural055-original-offline-f-authoring-v1',
               'runtime_source': session.source.identity, 'resource_policy': session.resource_identity,
               'public_interface': session.public_interface,
               'provider_id': session.spec['provider_id'],
               'actual_provider_specifications': session.spec['native_profile']['model_providers'],
               'source': f_descriptor, 'history': history,
               'original_lifetime_origin': session.budget.origin, 'author_loop_start': before,
               'data_exposure': 'no authentic or invented data was supplied to this source author',
               'static_feedback_only': True, 'source_method_review_status': 'external_genuine_review_required',
               'scientific_qualification_claimed': False}
    receipt_record = session.json('OFFLINE_AUTHOR_RECEIPT.json', receipt)
    session.budget.check('after offline author source and receipt publication')
    after = session.budget.cost_point()
    # The immutable closed F-authoring vector is embedded by the subsequent
    # packaging phase, not claimed to include its own future publication.
    closure = {'schema': 'neural055-offline-authoring-closure-v1',
               'artifact_root': str(session.output),
               'receipt': recorded_pin(receipt_record, 'original_offline_author_receipt'),
               'source': f_descriptor, 'origin': session.budget.origin, 'end': after['clock'],
               'costs': {k: after[k] for k in after if k != 'clock'},
               'author_loop_breakdown_not_additional_charge': {
                   k: after[k] - before[k] for k in before if k != 'clock'},
               'wall_seconds': after['clock'] - session.budget.origin,
               'scope': 'original request/source/bootstrap/provider qualification and verification, model authoring, repairs, authored-source and author-receipt publication; later packaging/terminal separately retained',
               'resource_policy': session.resource_identity,
               'host_and_setup_costs': 'included through this completed receipt; provider intervals are breakdowns, never additional summed CPU',
               'native_total_io_and_whole_host_memory_qualified': False}
    session.carrier.retain(closure)
    return source, f_descriptor, closure


def build_submission(session, author_spec, i_spec, renderer):
    """Real source producers and actual policy publication, no forged reviews."""
    need(i_spec['model_provider'] == session.spec['provider_id'], 'same explicitly selected model provider ID for F author and I')
    source, f_descriptor, offline = author_source(session, author_spec)
    session.budget.check('before fixed I source rendering')
    rendered = renderer(i_spec, session.public_interface)
    need(type(rendered) is dict and {'source_bytes', 'source_sha256', 'I_policy_fragment'} <= set(rendered),
         'actual fixed I renderer output')
    i_source = rendered['source_bytes']
    need(type(i_source) is bytes and 0 < len(i_source) <= MAX_PROGRAM
         and hashlib.sha256(i_source).hexdigest() == rendered['source_sha256'], 'actual complete emitted I source')
    i_descriptor = recorded_pin(session.write('I.py', i_source), 'precommitted_I_source')
    i_policy = rendered['I_policy_fragment']
    keys(i_policy, ('source_sha256', 'initializer', 'dependencies', 'services', 'inference_restrictions'))
    need(i_policy['source_sha256'] == i_descriptor['sha256']
         and i_policy['initializer'] == 'fresh_full_cell_and_phase_from_permitted_seal', 'exact original I policy binding')
    f_policy = dict(author_spec['F_policy'], source_sha256=f_descriptor['sha256'],
                    initializer='fresh_full_cell_and_phase_from_permitted_seal')
    policy = {'schema': 'neural055-complete-preexposure-policies-v3', 'F': f_policy, 'I': i_policy,
              'common_dependencies': author_spec['common_dependencies'], 'offline_costs': offline,
              'exposure_declaration': author_spec['exposure_declaration'],
              'participant_interface': session.public_interface, 'resource_policy': session.resource_identity}
    raw = encoded(policy); need(len(raw) <= 1048576, 'original complete common-policy ceiling')
    common = recorded_pin(session.write('COMMON_POLICY.json', raw), 'preexposure_common_policy')
    local_submission = {'F': f_descriptor, 'I': i_descriptor, 'common_policy': common}
    prefix = session.output.relative_to(session.operator_root)
    submission = {name: dict(d, path=str(prefix / d['path'])) for name, d in local_submission.items()}
    result = {'schema': 'neural055-f-i-source-bundle-v1', 'artifact_root': str(session.output),
              'operator_root': str(session.operator_root), 'submission': submission,
              'artifact_local_submission': local_submission,
              'public_interface': session.public_interface, 'resource_policy': session.resource_identity,
              'original_cells': {'F': 300, 'I': 300, 'REFERENCE': 360, 'total': 960},
              'offline_authoring_closure': offline, 'pre_exposure_review': 'not_created; genuine independent input required',
              'postscore_implemented': False, 'scientific_qualification_claimed': False}
    session.json('SUBMISSION.json', result)
    session.budget.check('after actual complete F/I source bundle publication')
    return result
