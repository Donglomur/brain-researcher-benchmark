"""Exact source-owned bank ABI adapters; no scientific implementation is substituted."""
from pathlib import Path
from core import need, encoded, pin, descriptor, canonical, relative
from contracts import CONFIGS, FAMILIES


def reference_dtype(storage):
    need(storage in ('<f8','|b1'), 'exact prepared reference storage dtype')
    return {'<f8':'float64','|b1':'bool'}[storage]


def reference_input(row):
    from worker_common import array_desc
    d = array_desc(row)
    d['dtype'] = reference_dtype(row['dtype'])
    return d


def configuration(implementation, ordinal):
    need(implementation in ('r1', 'r2') and ordinal in CONFIGS, 'exact bank/configuration ordinal')
    family = ordinal[0]; index = int(ordinal[1:])
    if family == 'R':
        exponent = index-6; result = {'family': 'R', 'lambda': 10.**exponent}
        if implementation == 'r1': result['id'] = 'R-'+str(exponent)
    elif family == 'B':
        values = [(l, p, t) for l in (4,16) for p in (1,10) for t in (100,300)]
        l, p, t = values[index]
        result = {'family':'B','leaves':l,'leaf_l2' if implementation == 'r1' else 'l2':p,'trees':t}
        if implementation == 'r1': result['id'] = f'B-{l}-{p}-{t}'
    else:
        w, d, e = [(w,d,e) for w in (16,32) for d in (.001,.1) for e in (80,240)][index]
        result = {'family':'T','width':w,'decay':d,'epochs':e}
        if implementation == 'r1': result['id'] = f'T-{w}-{d}-{e}'
    return result


def decoded(value, implementation):
    if implementation == 'r1':
        need(type(value) is dict and set(value) == {'schema','tree'}
             and value['schema'] == 'neural049_r1_safe_tree_v1', 'R1 exact safe tree')
        return value['tree']
    need(type(value) is dict, 'R2 exact primitive packed object'); return value


def array_members(value, implementation):
    marker = '$array' if implementation == 'r1' else '__primitive_array__'
    result = []
    def walk(x, depth=0):
        need(depth <= 40, 'bounded full safe state tree')
        if type(x) is dict:
            if marker in x:
                need(set(x) == {marker}, 'one safe primitive array wrapper')
                d = x[marker]; need(set(d) == {'path','pin','shape','dtype'}, 'complete array descriptor')
                descriptor(d['pin']); result.append(d)
            else:
                for v in x.values(): walk(v, depth+1)
        elif type(x) is list:
            for v in x: walk(v, depth+1)
        else: need(x is None or type(x) in (str,int,float,bool), 'primitive state leaf')
    walk(value); need(len({x['path'] for x in result}) == len(result), 'each state member named exactly once')
    return result


def primitive(value, implementation):
    marker = '$array' if implementation == 'r1' else '__primitive_array__'
    need(type(value) is dict and set(value) == {marker}, 'actual producer primitive output')
    d = dict(value[marker]); d['dtype'] = {'float64':'<f8','float32':'<f4','int64':'<i8','bool':'|b1','uint8':'|u1'}.get(d['dtype'], d['dtype'])
    return d


def host_descriptor(row, produced):
    prefix = canonical(produced['container_output']); path = canonical(row['path'])
    need(prefix in path.parents, 'artifact belongs to actual exact producer output namespace')
    name = str(path.relative_to(prefix)); need(name in produced['native']['artifacts']
        and row['pin'] == produced['native']['artifacts'][name], 'array joins actual native-captured file')
    return {**row, 'path': str(Path(produced['output'])/relative(name))}


def join_output(produced, request, artifacts, implementation, cap):
    """Only after independent natural native closure; every packed member rejoined."""
    actual = produced['native']['artifacts']; kind = request['operation']
    name = 'result/RESULT.json' if kind == 'predict' else 'result/STATE.json'
    body = artifacts.json(Path(produced['output'])/name, actual[name], cap)
    tree = decoded(body, implementation); members = array_members(tree, implementation)
    expected = {name, 'result/WORK.json', 'result/RECEIPT.json'}
    for member in members:
        d = host_descriptor(member, produced)
        expected.add(str(canonical(member['path']).relative_to(canonical(produced['container_output']))))
        artifacts.capture(d['path'], d['pin'], d['pin']['bytes'], retain=False)
    need(set(actual) == expected, 'complete safe model/output artifact set, no hidden or dropped members')
    receipt = artifacts.json(Path(produced['output'])/'result/RECEIPT.json', actual['result/RECEIPT.json'], cap)
    need(receipt['operation'] == kind and receipt['source_identity'] == request['source_identity']
         and receipt['assigned_days'] == request['assigned_days'] and receipt['assigned_ids'] == request['assigned_ids'],
         'actual full worker assignment/source closure')
    reqkey = 'request' if implementation == 'r1' else 'request_pin'
    need(receipt[reqkey] == produced['request']['pin'], 'receipt to actual REQUEST mount')
    if implementation == 'r1':
        need(receipt['batch'] == request['batch'] and receipt['input_state'] == request.get('state'), 'R1 complete input lineage')
    if kind == 'fit':
        need(tree['meta']['scope'] == request['scope']
             and tree['meta']['configuration'] == request['configuration'],
             'fitted state exact actual training/configuration')
    elif kind == 'predict':
        need(tree['ids'] == request['assigned_ids'], 'all ordered prediction rows')
    return {'document': {'path': str(Path(produced['output'])/name), 'pin': actual[name]},
            'container_document': {'path': produced['container_output']+'/'+name, 'pin': actual[name]},
            'tree': tree, 'arrays': [host_descriptor(d, produced) for d in members], 'receipt': receipt}
