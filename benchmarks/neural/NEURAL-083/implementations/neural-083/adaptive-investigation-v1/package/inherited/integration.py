"""Concrete preparation -> unchanged full programme -> protected scoring join.

The operator supplies genuine independent input/method/environment admissions.
Producing a COMPLETE record never issues those admissions. `io` and `owner`
are injected from the authenticated source closure by entry.py.
"""
import base64
import math
import os
from pathlib import Path
import sys
import time

PROGRAM_PIN = {'bytes': 2468, 'sha256': '939101b3ac774f2e258faa3aa45790ab0b7fcc355e56676d9a0e90a69f418897'}
PREP_ENTRY_PIN = {'bytes': 29770, 'sha256': '822f25917057c3df24c3f6bb77ea76f610bb3493f41b1c9524ba2a68040bf1b9'}
SCOPE = dict(records=108, query_trials=10800, combined_conditions=2592)
CAPTURED = ('import base64,sys\n'
            'p=sys.argv[1];b=base64.b64decode(sys.argv[2],validate=True);o=float(sys.argv[3]);'
            'sys.argv=[p,*sys.argv[4:]]\n'
            'exec(compile(b,p,"exec"),{"__name__":"__main__","__file__":p,"ADAPTER_ORIGIN":o})\n')


def programme(root, bodies):
    here = root / 'program'
    m = io.parse(bodies['program/SOURCE_MANIFEST.json'])
    io.need(io.pin(bodies['program/SOURCE_MANIFEST.json']) == PROGRAM_PIN,
            'unchanged original programme manifest')
    selected = {}
    for name, expected in m['files'].items():
        selected[name] = bodies['program/' + name]
        io.need(io.pin(selected[name]) == expected, 'unchanged programme source: ' + name)
    c = io.module(selected['common.py'], here / 'common.py')
    contracts = c.module(selected, 'contracts.py', here, c=c)
    policy = c.module(selected, 'policy.py', here, c=c, contracts=contracts)
    return c, contracts, policy, selected


def read_json(spec, budget, cap=4_000_000):
    return io.parse(io.capture(spec, budget, cap))


def read_only(value):
    with io.held_parent(value) as (parent, leaf, verify):
        s = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
        io.need(s.st_mode & 0o222 == 0 and s.st_uid == os.geteuid(),
                'operator-owned sealed preparation product')
        verify()


def full_preparation(prepared, canonical, panel, contracts):
    """Pure full-support join. This checks consistency, not authentic provenance."""
    io.exact(prepared, ('schema', 'canonical', 'canonical_root', 'projection_provenance',
                       'panel', 'protected_targets', 'records', 'query_trials',
                       'combined_conditions', 'independent_preparation_admission', 'resources'))
    io.need(prepared['schema'] == 'neural083_preparation_output_v1'
            and prepared['independent_preparation_admission'] is False,
            'producing preparation receipt is not independent admission')
    for key, number in SCOPE.items():
        io.need(type(prepared[key]) is int and prepared[key] == number, 'full preparation scope: ' + key)
    io.descriptor(prepared['canonical'])
    for key in ('projection_provenance', 'panel', 'protected_targets'):
        io.only_pin(prepared[key])
    io.path(prepared['canonical_root'])
    computed = contracts.canonical(canonical)
    io.need(computed == panel, 'same complete canonical and original panel')
    io.need(canonical['projection_provenance'] == prepared['projection_provenance'],
            'projection provenance identity')
    io.need(io.pin(io.encoded(canonical)) == io.only_pin(prepared['canonical'])
            and io.pin(io.encoded(panel)) == prepared['panel'], 'exact canonical publication encoding')
    io.need(sum(1 for _ in contracts.schedule(panel)) == 2592, 'both complete programme panels')
    return computed


def prepared_inputs(complete, closure, root, bodies, budget):
    """Only metadata here. Protected targets/arrays/identity key are never opened."""
    io.descriptor(complete)
    product = io.path(complete['path']).parent
    io.need(io.path(complete['path']).name == 'COMPLETE.json', 'actual preparation completion product')
    value = read_json(complete, budget)
    io.need(value['canonical']['path'] == str(product / 'index.json'), 'canonical belongs to same product root')
    records = io.path(value['canonical_root'])
    io.need(product != records and product not in records.parents and records not in product.parents,
            'distinct records and protected product roots')
    proof = read_json(closure, budget)
    io.need(proof.get('schema') == 'neural083_integration_preparation_closure_v1'
            and proof.get('operation') == 'finalize'
            and proof.get('complete') == io.only_pin(complete)
            and proof.get('complete_path') == complete['path']
            and proof.get('preparation_entry') == PREP_ENTRY_PIN,
            'exact independently observed finalizer completion')
    natural(proof['child'])
    io.need(proof.get('status') == 'naturally_closed_unqualified'
            and proof.get('independent_input_admission_issued') is False,
            'preparation closure is not an authentic-input review')
    canonical = read_json(value['canonical'], budget)
    panel_spec = dict(path=str(product / 'panel.json'), **value['panel'])
    panel = read_json(panel_spec, budget)
    c, contracts, policy, selected = programme(root, bodies)
    full_preparation(value, canonical, panel, contracts)
    for p in (complete['path'], value['canonical']['path'], panel_spec['path'], records, product):
        read_only(p)
    return dict(value=value, canonical=canonical, panel=panel, complete=complete, closure=closure,
                product=product, records=records, c=c, contracts=contracts, policy=policy,
                selected=selected)


def configuration(prepared, values, contracts):
    """Prepare a reviewable execution configuration before its independent method review."""
    io.exact(values, ('program', 'output', 'preparation_review', 'other_future_bytes', 'limits',
                      'docker_binary', 'docker_socket', 'image', 'memory_bytes',
                      'fit_seconds', 'infer_seconds', 'repository'))
    result = dict(schema='neural083_full_panel_selection_v1', task_id='NEURAL-083',
                  source=PROGRAM_PIN, canonical=prepared['canonical'],
                  canonical_root=prepared['canonical_root'], plan=contracts.numerical_work(), **values)
    return result


def joined_selection(joined, selection, root, budget):
    s = joined['policy'].selection(selection, PROGRAM_PIN)
    io.need(s['canonical'] == joined['value']['canonical']
            and s['canonical_root'] == joined['value']['canonical_root'],
            'selection uses exact prepared records and canonical index')
    io.need(io.path(s['repository']) == root / 'scientific-source',
            'original scorer definitions resolve only to captured legacy source')
    binding = io.parse(joined['selected']['BINDING.json'])
    def capture(p, cap, expected):
        return io.capture(dict(path=str(p), **expected), budget, cap)
    prep_review, method_review = joined['policy'].reviews(s, PROGRAM_PIN, binding, capture)
    io.need(prep_review.get('projection_provenance') == joined['value']['projection_provenance'],
            'independent input review joins actual projection')
    # These checks preserve the old actual admission, including no-query-adaptation
    # review; the producing finalizer is never used to set a review flag.
    out = io.path(s['output'])
    for private in (joined['product'], joined['records']):
        io.need(out != private and out not in private.parents and private not in out.parents,
                'candidate attempt separate from original/protected preparation')
    return s


def natural(record):
    io.need(type(record) is dict, 'actual child record')
    for name in ('started', 'finished', 'normal_end', 'cleanup_end', 'elapsed'):
        number = record.get(name)
        try:
            valid = type(number) in (int, float) and math.isfinite(number)
        except OverflowError:
            valid = False
        io.need(valid,
                'finite non-boolean child clock: ' + name)
    io.need(record['started'] <= record['finished'] < record['normal_end'] < record['cleanup_end']
            and record['elapsed'] >= 0, 'ordered child clocks and nonnegative elapsed')
    io.need(record.get('natural_exit') is True and type(record.get('exit_code')) is int
            and record['exit_code'] == 0 and record.get('process_reaped') is True
            and record.get('process_group_absent') is True
            and record.get('stdout_eof') is True and record.get('stderr_eof') is True
            and record.get('primary_error') is None and record.get('cleanup_errors') == []
            and record['finished'] < record['normal_end'], 'actual natural child/group/stream closure')


def child_failure_record(error):
    """Return the exact actual record attached by this source's child owner."""
    if isinstance(error, owner.ChildFailure):
        return error.record
    record = getattr(error, 'actual_child_record', None)
    return record if type(record) is dict else None


def publish_child(output, record, budget):
    try:
        return io.put(output / 'CHILD.json', io.encoded(record), budget)
    except BaseException as error:
        # Keep the original publication exception as primary; the enclosing
        # failure writer can still retain the exact consumed child prefixes.
        error.actual_child_record = record
        raise


def child_argv(file, body, origin, extra):
    return [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-c', CAPTURED,
            str(file), base64.b64encode(body).decode('ascii'), repr(origin), *extra]


def environment():
    # Preserve ordinary runtime environment; strip interpreter/preload/docker overrides.
    return {k: v for k, v in os.environ.items()
            if not k.startswith(('PYTHON', 'LD_', 'DYLD_')) and k not in ('DOCKER_HOST', 'DOCKER_CONTEXT')}


def launch(file, body, args, origin, normal_end, cleanup_end, output, budget):
    """Persist original consumed streams even when the selected child fails."""
    argv = child_argv(file, body, origin, args)
    try:
        result = owner.run(argv, normal_end=normal_end, cleanup_end=cleanup_end,
                           env=environment(), metadata_read=budget.read, stream_cap=65_536)
    except owner.ChildFailure as error:
        result = error.record
        try:
            publish_child(output, result, budget)
        except BaseException as publication:
            error.add_note('Child receipt publication also failed: ' + type(publication).__name__)
        raise
    publish_child(output, result, budget)
    natural(result)
    return result


def prepare(operation, request_spec, root, bodies, output, budget, origin, normal_end, cleanup_end):
    io.need(operation in ('project', 'finalize'), 'exact preparation operation')
    request = read_json(request_spec, budget, 262_144)
    io.need(request.get('schema') == 'neural083_' + operation + '_request_v1', 'same selected preparation request')
    for name in ('records_root', 'product_root', 'source_root'):
        if name in request:
            operand = io.path(request[name])
            io.need(operand != output and operand not in output.parents and output not in operand.parents,
                    'preparation roots separate from the process-owner evidence directory')
    io.need(type(request.get('deadline_ns')) is int and
            origin * 1e9 < request['deadline_ns'] <= normal_end * 1e9,
            'preparation inherits enclosing original deadline')
    cache = output / 'UNUSED-PYCACHE'
    args = [operation, '--request', request_spec['path'], '--request-bytes', str(request_spec['bytes']),
            '--request-sha256', request_spec['sha256']]
    # The original preparation requires an absent -X cache prefix and authenticates
    # its entire captured original source closure. No source/dependency is substituted.
    argv = child_argv(root / 'preparation/prepare_entry.py', bodies['preparation/prepare_entry.py'], origin, args)
    # Only actual preparation needs its independently admitted NumPy/SciPy site
    # environment. Programme ownership, compose and grade remain stdlib hosts.
    argv.remove('-S')
    argv[3:3] = ['-X', 'pycache_prefix=' + str(cache)]
    try:
        child = owner.run(argv, normal_end=normal_end, cleanup_end=cleanup_end,
                          env=environment(), metadata_read=budget.read, stream_cap=65_536)
    except owner.ChildFailure as error:
        try:
            publish_child(output, error.record, budget)
        except BaseException as publication:
            error.add_note('Preparation child receipt also failed: ' + type(publication).__name__)
        raise
    publish_child(output, child, budget)
    natural(child)
    io.need(not os.path.lexists(cache), 'disabled preparation cache remains absent')
    raw = base64.b64decode(child['stdout_base64'], validate=True)
    terminal = io.parse(raw)
    result = dict(schema='neural083_integration_preparation_closure_v1', operation=operation,
                  status='naturally_closed_unqualified', child=child, preparation_entry=PREP_ENTRY_PIN,
                  request=io.only_pin(request_spec), independent_input_admission_issued=False,
                  scientific_qualified=False)
    if operation == 'finalize':
        complete_path = io.path(request['product_root']) / 'COMPLETE.json'
        complete = dict(path=str(complete_path), **io.pin(io.encoded(terminal)))
        io.need(read_json(complete, budget) == terminal, 'terminal equals durable original finalizer result')
        io.need(terminal.get('records') == 108 and terminal.get('combined_conditions') == 2592,
                'full finalizer support')
        result['complete'] = io.only_pin(complete)
        result['complete_path'] = str(complete_path)
    else:
        result['projection_record'] = terminal['projection_record']
    return result


def run(joined, selection_spec, external_output, root, bodies, output, budget, origin):
    selection = joined_selection(joined, read_json(selection_spec, budget, 32_768), root, budget)
    whole = origin + selection['limits']['whole_seconds']
    # The old observer can spend sixty seconds preserving failure evidence after
    # whole. The new owner reserves a further ten seconds for its own cleanup.
    normal_end, cleanup_end = whole + 60, whole + 70
    io.need(cleanup_end + 5 <= budget.deadline, 'enclosing owner includes full old observer failure interval')
    external = io.path(external_output)
    io.need(external.parent == output and not os.path.lexists(external), 'owned fresh external observer receipt')
    attempt = io.path(selection['output'])
    io.need(attempt != output and attempt not in output.parents and output not in attempt.parents,
            'programme attempt separate from process-owner evidence directory')
    args = ['--source-pin', io.encoded(PROGRAM_PIN).decode().strip(),
            '--selection', selection_spec['path'], '--selection-pin', io.encoded(io.only_pin(selection_spec)).decode().strip(),
            '--external-output', str(external)]
    child = launch(root / 'program/observe.py', bodies['program/observe.py'], args,
                   origin, normal_end, cleanup_end, output, budget)
    # This is the original fixed-size durable observer record, read only after
    # actual parent-observed natural closure. It is not inferred from COMPLETE.
    raw = io.observed(external, 8192, budget)
    value = io.parse(raw)
    io.need(value.get('schema') == 'neural083_sequential_external_v2'
            and value.get('status') == 'complete_unqualified'
            and value.get('source') == PROGRAM_PIN
            and value.get('selection') == io.only_pin(selection_spec)
            and value.get('attempt') == selection['output']
            and value.get('full54x2x4x3_both_panels') is True
            and value.get('grading_performed') is False,
            'actual complete original observer and selected full programme')
    return dict(schema='neural083_integration_programme_closure_v1', status='naturally_closed_unqualified',
                source=PROGRAM_PIN, selection=io.only_pin(selection_spec), external=io.pin(raw),
                prepared_complete=io.only_pin(joined['complete']),
                preparation_closure=io.only_pin(joined['closure']), child=child,
                grading_authorized=False, scientific_qualified=False,
                native_closure_basis='unchanged full observer admission; host-group absence alone is insufficient')


def grade(joined, inputs, root, bodies, budget):
    """Run inside the separately owned grade child, after external authorization."""
    io.exact(inputs, ('preparation_complete', 'preparation_closure', 'selection', 'external',
                      'programme_closure', 'root_outer_proof', 'grade_read_limit'))
    closure = read_json(inputs['programme_closure'], budget)
    io.need(closure.get('schema') == 'neural083_integration_programme_closure_v1'
            and closure.get('status') == 'naturally_closed_unqualified'
            and closure.get('source') == PROGRAM_PIN
            and closure.get('prepared_complete') == io.only_pin(joined['complete'])
            and closure.get('preparation_closure') == io.only_pin(joined['closure'])
            and closure.get('selection') == io.only_pin(inputs['selection'])
            and closure.get('external') == io.only_pin(inputs['external'])
            and closure.get('grading_authorized') is False,
            'exact observed programme closure; it never authorized grading')
    natural(closure['child'])
    proof = read_json(inputs['root_outer_proof'], budget, 32_768)
    io.need(proof.get('integration_closure') == io.only_pin(inputs['programme_closure'])
            and proof.get('schema') == 'neural083_outer_observer_admission_v1'
            and proof.get('external') == closure['external']
            and proof.get('selection') == closure['selection']
            and proof.get('source') == PROGRAM_PIN
            and proof.get('grading_authorized') is True,
            'separately selected root grading proof joins actual observed closure')
    for name in ('natural_exit_zero', 'process_reaped', 'process_group_absent',
                 'stdout_eof', 'stderr_eof', 'durably_closed_before_original_deadline'):
        io.need(proof.get(name) is True, 'root proof of actual closure: ' + name)
    selection = joined_selection(joined, read_json(inputs['selection'], budget, 32_768), root, budget)
    c, selected = joined['c'], joined['selected']
    comparison = c.module(selected, 'comparison.py', root / 'program')
    target_spec = dict(path=str(joined['product'] / 'targets.json'), **joined['value']['protected_targets'])
    target_calls = 0
    def targets():
        nonlocal target_calls
        target_calls += 1
        io.need(target_calls == 1, 'one actual protected callback after complete admission')
        read_only(target_spec['path'])
        value = read_json(target_spec, budget)
        io.need(value.get('generation') == joined['canonical']['generation'], 'exact protected generation')
        return value
    result = comparison.protected_grade(c, root / 'program/SOURCE_MANIFEST.json', PROGRAM_PIN,
                                       inputs['selection'], inputs['external'], inputs['root_outer_proof'],
                                       targets, deadline=budget.deadline,
                                       read_limit=inputs['grade_read_limit'])
    io.need(result['private_callbacks'] == target_calls, 'actual target callback accounting')
    result['integration_prepared_complete'] = io.only_pin(joined['complete'])
    result['integration_programme_closure'] = io.only_pin(inputs['programme_closure'])
    result['integration_target_reads'] = target_calls
    result['integration_metadata_costs'] = budget.record()
    return result
