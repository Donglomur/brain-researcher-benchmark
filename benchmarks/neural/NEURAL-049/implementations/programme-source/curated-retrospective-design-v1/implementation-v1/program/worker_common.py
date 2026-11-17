"""Isolated worker ABI. Parent source/image/role admission remains mandatory."""
from pathlib import Path
import random
from core import Budget, need, capture, parse, encoded, publish, fresh, pin, canonical, relative, integer
from array_io import Limits, load


def start(config):
    need(config.get('qualified_execution') is True, 'unqualified worker refuses before operands')
    budget = Budget(config['origin'], config['deadline'], config['read_cap'], config['write_cap'])
    raw, _ = capture(config['request_path'], config['request_pin'], config['request_cap'], budget, readonly=True)
    request = parse(raw)
    need(request['schema'] == 'neural049_worker_request_v1' and request['source_manifest'] == config['source_manifest']
         and request['origin'] == config['origin'] and request['deadline'] == config['deadline']
         and request['operation'] == config['operation'], 'exact source/request/role/original clock')
    output = canonical(config['output']); need(str(output) == '/output', 'fixed isolated output root')
    budget.tick(); limits = Limits(budget, request['limits'])
    seed = integer(request['seed']); random.seed(seed)
    return request, budget, limits, output


def seed_numpy(seed):
    # Explicitly initializes Python and NumPy legacy RNG only. User code may use
    # passed seed for its own generators; platform/provider entropy is qualified separately.
    import numpy as np
    np.random.seed(seed % (1 << 32))


def array_desc(row, root='/inputs/case'):
    return {'path': str(canonical(root)/relative(row['path'])),
            'pin': {'bytes': row['bytes'], 'sha256': row['sha256']}, 'shape': row['shape'], 'dtype': row['dtype']}


def view(request, limits):
    raw, _ = capture(request['view']['path'], request['view']['pin'], request['view_cap'], limits.budget, readonly=True)
    value = parse(raw)
    need(value['schema'] == 'neural049_case_view_v1' and value['view'] in ('C', 'N', 'NC')
         and value['sample_rate'] == 500, 'minimal complete actor view')
    result = {'view': value['view'], 'train': [], 'query': []}; seen = set(); axis = None
    for role, key in (('train', 'train_parts'), ('query', 'query_parts')):
        for part in value[key]:
            ids = part['ids']; need(type(ids) is list and len(ids) == len(set(ids)) and not seen.intersection(ids), 'complete disjoint actor rows')
            seen.update(ids)
            if axis is None: axis = part['axis']
            need(part['axis'] == axis and axis and len(axis) == len(set(axis)), 'full person channel union')
            expected = {'mask', 'offsets'} | ({'x'} if value['view'] != 'C' else set()) | ({'context'} if value['view'] != 'N' else set())
            need(set(part['arrays']) == expected, 'exact positive view fields')
            arrays = {k: load(array_desc(v), ['/inputs/case'], limits) for k, v in part['arrays'].items()}
            n, c = len(ids), len(axis)
            need(arrays['mask'].shape == (n, c, 5000) and arrays['mask'].dtype.str == '|b1'
                 and arrays['offsets'].shape == (n,) and arrays['offsets'].dtype.str == '<f8', 'full source sample/offset shape')
            need(bool(((arrays['offsets'] >= 0) & (arrays['offsets'] < .002)).all()), 'fractional alignment retained')
            if 'x' in arrays:
                need(arrays['x'].shape == (n, c, 5000) and arrays['x'].dtype.str == '<f8', 'full double neural input')
            if 'context' in arrays: need(arrays['context'].shape == (n, 6) and arrays['context'].dtype.str == '<f8', 'six double context columns')
            row = {'ids': ids, 'axis': axis, **arrays}
            if role == 'train':
                need(set(part['labels']) == {'angle', 'magnitude', 'speed'}, 'all selected training endpoints')
                row['labels'] = {k: load(array_desc(v), ['/inputs/case'], limits) for k, v in part['labels'].items()}
                need(all(y.shape == (n,) and y.dtype.str == '<f8' for y in row['labels'].values()), 'complete training labels')
            else: need('labels' not in part, 'no held labels in actor view')
            result[role].append(row)
    result['axis'] = axis
    if request.get('tool_bank') is not None:
        bank = request['tool_bank']; result['tool'] = {}
        for role in ('train', 'query'):
            ids = [x for p in result[role] for x in p['ids']]
            need(bank[role]['ids'] == ids and bank[role]['in_sample'] is (role == 'train'), 'tool full role support and in-sample status')
            need(set(bank[role]['columns']) == {'angle','magnitude','speed'}, 'all three numeric-only tool endpoints')
            columns = [load(bank[role]['columns'][k], ['/inputs/tool'], limits) for k in ('angle','magnitude','speed')]
            need(all(x.shape == (len(ids),) and x.dtype.str == '<f8' for x in columns), 'complete double scalar tool columns')
            limits.reserve('allocation_bytes', len(ids)*3*8)
            import numpy as np
            result['tool'][role] = np.column_stack(columns)
    limits.budget.tick(); return result


def method(request, budget):
    raw, _ = capture(request['method']['path'], request['method']['pin'], request['method_cap'], budget, readonly=True)
    scope = {'__name__': 'neural049_candidate', '__file__': request['method']['path']}
    budget.tick(); exec(compile(raw, request['method']['path'], 'exec', dont_inherit=True), scope); budget.tick()
    return scope


def finish(output, request, budget, limits, artifacts):
    work = {'schema': 'neural049_worker_work_v1', 'operation': request['operation'], 'source': request['source_manifest'],
            'budget_before_work': budget.record(), 'numeric': limits.record(), 'logical_counters_not_native_telemetry': True}
    artifacts['WORK.json'] = publish(output/'WORK.json', encoded(work), budget, readonly=True)
    receipt = {'schema': 'neural049_worker_receipt_v1', 'operation': request['operation'], 'request': pin(encoded(request)),
               'source': request['source_manifest'], 'artifacts': artifacts, 'origin': budget.origin,
               'deadline': budget.deadline, 'observed_end': budget.tick(), 'natural_process_exit_not_self_certified': True,
               'costs_before_receipt': budget.record()}
    out = publish(output/'RECEIPT.json', encoded(receipt), budget, readonly=True); budget.tick()
    return {'receipt': out, 'costs_after_publication': budget.record()}


def failure(output, error, budget, limits):
    record = {'status': 'failed', 'error': type(error).__name__, 'costs': {'reads': budget.read_bytes, 'writes': budget.write_bytes},
              'numeric': limits.record(), 'unknown_partial_files': True, 'no_retry': True}
    try: publish(output/'FAILURE.json', encoded(record), budget, readonly=True)
    except BaseException as later: record['failure_publication'] = type(later).__name__
    error.failure_record = record
