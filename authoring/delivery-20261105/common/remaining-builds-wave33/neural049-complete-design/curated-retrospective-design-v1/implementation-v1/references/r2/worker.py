"""Concrete one-operation trusted-reference worker, source/clock bound by owner."""
from pathlib import Path
from .budget import Budget, ReferenceFailure, require, encode
from .contracts import ordinary_ids, environment_check, numpy
from .safeio import (canonical_path, pin_check, read_json, read_array, make_directory,
                     write_json, write_array, pack, unpack, packing_plan, PUBLIC_DTYPES, PRIMITIVES)
from .models import fit, predict
from .features import feature_transform


def typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return set(a) == set(b) and all(typed_equal(a[k], b[k]) for k in a)
    if type(a) in (tuple, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def declared_array(desc, shape=None, dtype=None):
    require(type(desc) is dict and set(desc) == {'path', 'pin', 'shape', 'dtype'}, 'array descriptor fields')
    pin_check(desc['pin'])
    require(type(desc['shape']) is list and 1 <= len(desc['shape']) <= 4 and
            all(type(v) is int and 0 <= v < 2**40 for v in desc['shape']) and
            desc['dtype'] in PUBLIC_DTYPES, 'declared primitive extent')
    if shape is not None:
        require(desc['shape'] == list(shape) and desc['dtype'] == dtype, 'declared complete shape/dtype')
    size = PRIMITIVES[PUBLIC_DTYPES[desc['dtype']]][0]
    for v in desc['shape']:
        size *= v
    require(size+10 <= desc['pin']['bytes'] <= size+65548, 'declared NPY header/payload extent')
    return size


def parts_plan(request, view, fit_operation, budget):
    batch = request['batch']
    require(type(batch) is dict and set(batch) == {'schema', 'parts'} and
            batch['schema'] == 'neural049_numeric_parts_v1', 'ordered-parts batch schema')
    parts = batch['parts']
    require(type(parts) is list and bool(parts), 'explicit all-day parts required')
    days = request['assigned_days']
    require(type(days) is list and days == sorted(set(days)) and bool(days) and
            all(type(d) is int and d > 0 for d in days), 'complete original day assignment')
    ordinary_ids(request['assigned_ids'], 'assigned')
    ids, seen_days, axis, byte_total = [], [], None, 0
    for part in parts:
        expected = {'day', 'ids', 'axis', 'arrays'} | ({'labels'} if fit_operation else set())
        require(type(part) is dict and set(part) == expected, 'part keys/target absence')
        require(type(part['day']) is int and part['day'] > 0, 'original day ordinal')
        seen_days.append(part['day'])
        ordinary_ids(part['ids'], 'part events')
        ordinary_ids(part['axis'], 'part channel axis')
        require(bool(part['axis']), 'nonempty full channel axis')
        if axis is None:
            axis = part['axis']
        require(part['axis'] == axis, 'same complete ordered channel axis')
        ids.extend(part['ids'])
        n, c = len(part['ids']), len(axis)
        names = {'mask', 'offsets'} | ({'x'} if view != 'C' else set()) | ({'context'} if view != 'N' else set())
        require(type(part['arrays']) is dict and set(part['arrays']) == names, 'view-specific operand exclusions')
        for name, desc in part['arrays'].items():
            shape = (n, c, 5000) if name in ('x', 'mask') else ((n, 6) if name == 'context' else (n,))
            byte_total += declared_array(desc, shape, 'bool' if name == 'mask' else 'float64')
        if fit_operation:
            byte_total += declared_array(part['labels'], (n,), 'float64')
    require(seen_days == days and ids == request['assigned_ids'] and len(ids) == len(set(ids)),
            'exact complete ordered day/event assignment before matrix reads')
    if fit_operation:
        scope = request['scope']
        require(scope['training_days'] == days and scope['training_ids'] == ids and scope['axis'] == axis,
                'fit assignment/scope exact join')
    budget.arrays(byte_total*3+65536*len(parts), 'all parts decoder/concatenation reservation',
                  live=byte_total*5+65536*len(parts))
    return parts, ids, axis


def load_parts(request, view, fit_operation, roots, budget):
    parts, ids, axis = parts_plan(request, view, fit_operation, budget)
    retained = sum(declared_array(d) for p in parts for d in p['arrays'].values())
    if fit_operation:
        retained += sum(declared_array(p['labels']) for p in parts)
    budget.retain(retained, 'retain complete input arrays through worker closure')
    np = numpy()
    names = list(parts[0]['arrays'])
    buckets = {name: [] for name in names}
    labels = []
    for part in parts:
        for name in names:
            buckets[name].append(read_array(part['arrays'][name], roots, budget))
        if fit_operation:
            labels.append(read_array(part['labels'], roots, budget))
    batch = {'schema': 'neural049_numeric_batch_v1', 'ids': ids, 'axis': axis, 'x': None, 'context': None}
    for name, values in buckets.items():
        batch[name] = np.concatenate(values, axis=0)
    target = np.concatenate(labels, axis=0) if fit_operation else None
    budget.tick('complete source parts concatenated')
    return batch, target


def state_plan(obj, budget):
    total = 0
    def visit(value, depth=0):
        nonlocal total
        require(depth < 64, 'safe state depth')
        if type(value) is dict:
            if '__primitive_array__' in value:
                require(set(value) == {'__primitive_array__'}, 'safe array marker')
                total += declared_array(value['__primitive_array__'])
            else:
                for x in value.values():
                    visit(x, depth+1)
        elif type(value) is list:
            for x in value:
                visit(x, depth+1)
    visit(obj)
    budget.arrays(total*3+65536, 'entire serialized state array admission', live=total*5+65536)
    budget.retain(total, 'retain complete loaded state alongside complete inputs')


def worker_run(request_path, expected_request_pin, source_identity, origin, deadline, limits, output_root):
    budget = Budget(origin, deadline, limits)
    created, attempted, output = False, [], None
    try:
        path = canonical_path(request_path)
        pin_check(expected_request_pin)
        request = read_json({'path': str(path), 'pin': expected_request_pin}, [path.parent], budget)
        require(type(request) is dict and request.get('schema') == 'neural049_r2_request_v1', 'R2 request schema')
        require(request.get('qualified_execution') is True and type(source_identity) is dict and bool(source_identity)
                and typed_equal(request.get('source_identity'), source_identity), 'independent owner admission/source identity required')
        require(type(request.get('origin')) in (int, float) and type(request.get('deadline')) in (int, float)
                and request['origin'] == origin and request['deadline'] == deadline, 'inherited clock equality')
        environment_check(request.get('environment'))
        common = {'schema', 'operation', 'qualified_execution', 'source_identity', 'origin', 'deadline',
                  'input_roots', 'environment', 'batch', 'assigned_days', 'assigned_ids'}
        op = request.get('operation')
        extra = {'fit': {'scope', 'configuration'}, 'predict': {'state'},
                 'features': {'view', 'training_scope', 'statistics', 'temporal'}}
        require(op in extra and set(request) == common | extra[op], 'operation-specific request fields')
        if op == 'fit':
            require(typed_equal(request['scope'].get('source_identity'), source_identity) and
                    typed_equal(request['scope'].get('environment'), request['environment']), 'fit source/environment join')
            view = request['scope']['view']
        elif op == 'features':
            require(type(request['training_scope']) is bool and type(request['temporal']) is bool and
                    (request['statistics'] is None) == request['training_scope'], 'training-only statistic fitting')
            view = request['view']
        else:
            view = None
        require(type(request['input_roots']) is list and bool(request['input_roots']), 'admitted operand roots')
        roots = [canonical_path(x) for x in request['input_roots']]
        require(all(p.is_dir() for p in roots), 'operand roots directories')
        output = canonical_path(output_root, exists=False)
        require(not output.exists() and all(output != r and output not in r.parents and r not in output.parents for r in roots)
                and output != path and output not in path.parents, 'fresh disjoint output root')
        # State metadata is needed for the view; no state array is loaded until all query membership is checked.
        stored = None
        if op == 'predict':
            stored = read_json(request['state'], roots, budget)
            require(stored.get('schema') == 'neural049_r2_state_v1' and
                    typed_equal(stored['meta']['scope']['source_identity'], source_identity) and
                    typed_equal(stored['meta']['scope']['environment'], request['environment']), 'sealed state source/environment')
            view = stored['meta']['scope']['view']
        require(view in ('C', 'N', 'NC', 'NC_D'), 'view')
        parts_plan(request, view, op == 'fit', budget)
        attempted.append(str(output))
        make_directory(output, budget)
        created = True
        attempted.append(str(output/'arrays'))
        make_directory(output/'arrays', budget)
        environment_check(request['environment'], numerical=True)
        batch, labels = load_parts(request, view, op == 'fit', roots, budget)
        if op == 'fit':
            result = fit(request['scope'], batch, labels, request['configuration'], budget)
        elif op == 'predict':
            state_plan(stored, budget)
            state = unpack(stored, roots, budget)
            result = predict(state, batch, budget)
        else:
            statistics = None
            if request['statistics'] is not None:
                obj = read_json(request['statistics'], roots, budget)
                require(type(obj) is dict and 'statistics' in obj and 'features' in obj, 'saved feature result schema')
                state_plan(obj['statistics'], budget)
                statistics = unpack(obj['statistics'], roots, budget)
            result = feature_transform(batch, view, budget, request['environment'], statistics, request['temporal'])
        packing_plan(result, budget)
        packed = pack(result, output, budget)
        artifact = write_json(output/('STATE.json' if op in ('fit', 'features') else 'RESULT.json'), packed, budget)
        work = write_json(output/'WORK.json', budget.snapshot(), budget)
        receipt = {'schema': 'neural049_r2_worker_receipt_v1', 'operation': op,
                   'source_identity': source_identity, 'request_pin': expected_request_pin,
                   'assigned_days': request['assigned_days'], 'assigned_ids': request['assigned_ids'],
                   'artifact': artifact, 'work': work, 'origin': origin, 'deadline': deadline,
                   'cost_before_receipt_publication': budget.snapshot(),
                   'outer_natural_process_source_and_complete_artifact_closure': 'required independently; not supplied by this receipt'}
        result_descriptor = write_json(output/'RECEIPT.json', receipt, budget)
        budget.tick('worker final post-publication clock')
        return {'receipt': result_descriptor, 'cost_after_publication': budget.snapshot()}
    except BaseException as primary:
        record = {'schema': 'neural049_r2_worker_failure_v1', 'primary': repr(primary)[:2000],
                  'nested': getattr(primary, 'record', None), 'cost_before_failure_publication': budget.snapshot(),
                  'attempted_root_entries': attempted, 'root_creation_returned': created,
                  'partial_output_and_durability': 'uncertain until independent inspection',
                  'no_automatic_retry_or_rollback': True, 'later': []}
        if created:
            try:
                write_json(output/'FAILURE.json', record, budget)
            except BaseException as later:
                record['later'].append({'error': repr(later)[:2000], 'nested': getattr(later, 'record', None)})
        record['final_cost'] = budget.snapshot()
        raise ReferenceFailure('R2 operation failed; preserve all partial state and costs', record) from primary
