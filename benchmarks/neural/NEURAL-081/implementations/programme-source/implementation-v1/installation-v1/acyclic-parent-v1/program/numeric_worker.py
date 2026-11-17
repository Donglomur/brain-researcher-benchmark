"""Concrete complete reference operations; trusted scoped input bodies only."""
from pathlib import Path
import common as c
import protocol as p
import arrays
import model_io


def role(desc, access, generation, *, labels):
    r = access.json(desc)
    c.exact(r, ('schema', 'generation', 'view', 'outer_person', 'inner_person_or_FINAL', 'kind', 'people', 'ids', 'windows', 'labels', 'rows'))
    c.need(r['schema'] == 'neural081_role_v1' and r['generation'] == generation and r['view'] in c.VIEWS and r['outer_person'] in c.PEOPLE, 'current exact training role')
    inner = r['inner_person_or_FINAL']
    c.need(inner == 'FINAL' or inner in c.PEOPLE and inner != r['outer_person'], 'proper inner person')
    expected = [x for x in c.PEOPLE if x != r['outer_person'] and x != inner]
    c.need(r['people'] == expected and r['kind'] == ('FINAL' if inner == 'FINAL' else 'INNER'), 'exact outer/inner exclusions')
    c.need(type(r['ids']) is list and len(set(r['ids'])) == len(r['ids']) and len(r['rows']) == len(r['ids']), 'complete unique training roster')
    for ident, row in zip(r['ids'], r['rows']):
        c.ident(ident); c.exact(row, ('canonical_id', 'person'))
        c.need(row['canonical_id'] == ident and row['person'] in expected, 'training row identity/person')
    c.need({x['person'] for x in r['rows']} == set(expected), 'all permitted training people')
    c.need(len(r['windows']) == (len(r['ids']) if r['view'] == 'EEG' else 0), 'complete waveform view')
    for d in r['windows']:
        c.descriptor(d)
    c.descriptor(r['labels'])
    if labels:
        y = access.json(r['labels'])
        c.exact(y, ('schema', 'generation', 'ids', 'labels'))
        c.need(y['schema'] == 'neural081_role_labels_v1' and y['generation'] == generation and y['ids'] == r['ids'], 'exact isolated role-label support')
        c.need(type(y['labels']) is list and len(y['labels']) == len(r['ids']) and all(type(v) is int and v in c.CLASSES for v in y['labels']) and set(y['labels']) == set(c.CLASSES), 'all twelve legitimate training classes')
        for person in expected:
            c.need({label for row, label in zip(r['rows'], y['labels']) if row['person'] == person} == set(c.CLASSES), 'each training person has all classes')
        return r, arrays.numpy().array(y['labels'], dtype='int64')
    return r, None


def feature_rows(windows, n, view, family, numeric, access, limits):
    np = arrays.numpy(); d = 1024 if family == 'TM_LDA' else 320
    c.need(n > 0 and n*d*8 <= limits['max_array_bytes'], 'complete feature allocation')
    batch_size = min(256, n)
    c.need(n*d*8 + batch_size*64*512*16 < limits['max_workspace_bytes'], 'features plus complete source batches')
    result = np.empty((n, d), dtype=np.float64)
    for start in range(0, n, 256):
        count = min(256, n-start); batch = np.zeros((count, 64, 512), dtype=np.float32)
        if view == 'EEG':
            for j in range(count):
                desc = windows[start+j]; access.admit(desc)
                batch[j] = arrays.read(desc, 'float32', [64, 512], access.budget, [Path(desc['path']).parent], max_array_bytes=limits['max_array_bytes'])
        result[start:start+count] = numeric.features(batch, family, limits=limits)
        access.budget.check_clock()
    return result


def result_body(desc, access, generation, source, operation):
    value = access.json(desc)
    c.exact(value, ('schema', 'operation', 'generation', 'numeric_source', 'body'))
    c.need(value['schema'] == 'neural081_reference_result_v1' and value['operation'] == operation and value['generation'] == generation and c.typed_equal(value['numeric_source'], source), 'source/generation/operation result edge')
    return value['body']


def chosen(selection, family):
    rows = selection['selected_temperatures']
    c.need([x['family'] for x in rows] == list(p.FAMILIES), 'complete selected family order')
    return next(x for x in rows if x['family'] == family)


def query(value, generation):
    c.exact(value, ('generation', 'view', 'person', 'ids', 'windows'))
    c.need(value['generation'] == generation and value['view'] in c.VIEWS and value['person'] in c.PEOPLE, 'query generation/view/person')
    ids = value['ids']
    c.need(type(ids) is list and ids == sorted(ids) and len(set(ids)) == len(ids) and len(ids) >= 12, 'complete canonical query order')
    for ident in ids:
        c.ident(ident)
    c.need(len(value['windows']) == (len(ids) if value['view'] == 'EEG' else 0), 'all query waveform support')
    return value


def prediction_panel(output, name, probabilities, ids, metadata, budget):
    np = arrays.numpy(); arrays.exact_array(probabilities, 'float64', [len(ids), 12])
    rows = []
    for ident, values in zip(ids, probabilities):
        c.need(all(0 <= float(v) <= 1 for v in values), 'admitted emitted probability range')
        import math
        c.need(abs(math.fsum(float(v) for v in values)-1) <= 1e-6, 'admitted emitted probability sum')
        rows.append({'id': ident, 'probabilities': values.tolist()})
    pd = c.publish_json(output / (name + '_PREDICTIONS.json'), {'schema': 'neural081_predictions_v1', 'predictions': rows}, budget)
    panel = {'schema': 'neural081_reference_panel_v1', 'predictions': pd, **metadata}
    return c.publish_json(output / (name + '_PANEL.json'), panel, budget)


def execute(request, numeric, numeric_source, access, output):
    c.exact(request, ('schema', 'operation', 'generation', 'source', 'payload', 'limits', 'output_root'))
    c.need(request['schema'] == 'neural081_numeric_request_v1' and c.typed_equal(request['source'], numeric_source) and str(output) == request['output_root'], 'request/source/output join')
    limits = request['limits']; c.exact(limits, ('max_array_bytes', 'max_workspace_bytes', 'max_output_bytes'))
    for value in limits.values():
        c.integer(value, 1)
    op, a, generation, budget, np = request['operation'], request['payload'], request['generation'], access.budget, arrays.numpy()
    if op in ('fit', 'historical'):
        c.exact(a, ('role', 'configuration', 'selection'))
        r, labels = role(a['role'], access, generation, labels=True)
        if op == 'fit':
            c.need(a['configuration'] in numeric.configuration_grid(), 'declared complete configuration')
            family = a['configuration']['family']
        else:
            family = 'HISTORICAL_BP_LDA'
        if r['kind'] == 'FINAL':
            selected = result_body(a['selection'], access, generation, numeric_source, 'select')
            c.need(c.typed_equal(selected['role'], a['role']), 'final-fit exact nine-person selection support')
            if op == 'fit':
                c.need(chosen(selected['selection'], family)['configuration_id'] == a['configuration']['id'], 'selected final configuration only')
        else:
            c.need(a['selection'] is None and op == 'fit', 'inner training has no final-selection or historical path')
        x = feature_rows(r['windows'], len(r['ids']), r['view'], family, numeric, access, limits)
        model = numeric.fit(x, labels, a['configuration'], limits=limits) if op == 'fit' else numeric.fit_historical(x, labels, limits=limits)
        md = model_io.write(model, output / 'model', a['role'], a['selection'], numeric_source, budget)
        result = {'model': md, 'training_role': a['role'], 'configuration': model['configuration'], 'family': family,
                  'view': r['view'], 'outer': r['outer_person'], 'inner': r['inner_person_or_FINAL']}
    elif op in ('infer', 'inner_infer'):
        c.exact(a, ('model', 'query', 'temperature', 'configuration_id'))
        q = query(a['query'], generation)
        model, meta = model_io.read(a['model'], access, limits=limits)
        c.need(c.typed_equal(meta['numeric_source'], numeric_source), 'model numerical source')
        r, _ = role(meta['training_role'], access, generation, labels=False)
        c.need(r['view'] == q['view'] and q['person'] == (r['inner_person_or_FINAL'] if op == 'inner_infer' else r['outer_person']), 'held-person inference boundary')
        c.need(model['n_train'] == len(r['ids']) and model['configuration']['id'] == a['configuration_id'], 'model full support/configuration')
        if op == 'inner_infer':
            c.need(r['kind'] == 'INNER' and a['temperature'] == 1 and meta['selection'] is None, 'inner inductive T1 lineage')
        else:
            c.need(r['kind'] == 'FINAL', 'final inference role')
            selected = result_body(meta['selection'], access, generation, numeric_source, 'select')
            c.need(c.typed_equal(selected['role'], meta['training_role']), 'same selected training support')
            temperature = 1 if model['family'] == 'HISTORICAL_BP_LDA' else chosen(selected['selection'], model['family'])['temperature']
            c.need(type(a['temperature']) in (int, float) and a['temperature'] == temperature, 'previously sealed training-only temperature')
        n = len(q['ids']); c.need(n*12*16 <= limits['max_output_bytes'], 'complete score/probability buffers before allocation')
        scores, probs = np.empty((n, 12), dtype=np.float64), np.empty((n, 12), dtype=np.float64)
        for start in range(0, n, 256):
            count = min(256, n-start)
            x = feature_rows(q['windows'][start:start+count], count, q['view'], model['family'], numeric, access, limits)
            scores[start:start+count] = numeric.predict_scores(model, x, limits=limits)
            probs[start:start+count] = numeric.probabilities(scores[start:start+count], a['temperature'], limits=limits)
        result = {'probabilities_t1' if op == 'inner_infer' else 'probabilities': arrays.write(output / 'PROBABILITIES.npy', probs, budget),
                  'ids': q['ids'], 'person': q['person'], 'view': q['view'], 'model': a['model'],
                  'configuration_id': a['configuration_id'], 'shape': [n, 12], 'temperature': a['temperature']}
        if op == 'inner_infer':
            result['scores'] = arrays.write(output / 'SCORES.npy', scores, budget)
        else:
            result['panel'] = prediction_panel(output, 'REFERENCE', probs, q['ids'],
                {'role': 'reference', 'handle': model['family'], 'view': q['view'], 'person': q['person'],
                 'generation': generation, 'numeric_source': numeric_source, 'model': a['model'],
                 'training_role': meta['training_role'], 'selection': meta['selection']}, budget)
    elif op == 'select':
        c.exact(a, ('role', 'oof', 'assessment_ids'))
        r, labels = role(a['role'], access, generation, labels=True)
        c.need(r['kind'] == 'FINAL', 'selection uses exactly nine training people')
        lookup = dict(zip(r['ids'], labels.tolist())); records = []
        c.need(type(a['oof']) is list and len(a['oof']) == 180, 'all twenty by nine closed inner artifacts')
        # Admit the whole grid before allocating any OOF arrays. Each of the20
        # settings includes each legitimate training row once; nothing is sampled.
        complete_rows = 20*len(r['ids'])
        metadata_bytes = sum(item['bytes'] for item in a['oof'])
        c.need(complete_rows*(2*12*8+8+256) + metadata_bytes*2 + 2**20 < limits['max_workspace_bytes'],
               'complete OOF arrays, ID joins and metadata before loading')
        for item in a['oof']:
            v = result_body(item, access, generation, numeric_source, 'inner_infer')
            c.exact(v, ('scores', 'probabilities_t1', 'ids', 'person', 'view', 'model', 'configuration_id', 'shape', 'temperature'))
            ids = v['ids']; expected = {row['canonical_id'] for row in r['rows'] if row['person'] == v['person']}
            c.need(v['person'] in r['people'] and v['view'] == r['view'] and v['temperature'] == 1 and v['shape'] == [len(ids), 12] and len(set(ids)) == len(ids) and set(ids) == expected, 'complete legitimate training OOF support')
            ys = np.array([lookup[i] for i in ids], dtype=np.int64)
            loaded = {}
            for key in ('scores', 'probabilities_t1'):
                access.admit(v[key]); loaded[key] = arrays.read(v[key], 'float64', [len(ids), 12], budget, [Path(v[key]['path']).parent], max_array_bytes=limits['max_array_bytes'])
            records.append({'configuration_id': v['configuration_id'], 'person': v['person'], 'canonical_ids': ids, 'labels': ys, **loaded})
        selection = numeric.select(records, r['people'], limits=limits)
        priors = {k: v.tolist() for k, v in numeric.analytic_priors(labels, limits=limits).items()}
        ids = a['assessment_ids']
        c.need(type(ids) is list and len(ids) >= 12 and ids == sorted(ids) and len(set(ids)) == len(ids), 'complete canonical assessment IDs without targets')
        for ident in ids:
            c.ident(ident)
        analytic = []
        for name in ('UNIFORM', 'LAPLACE'):
            c.need(len(ids)*12*8 <= limits['max_output_bytes'], 'complete analytic output size')
            values = np.tile(np.array(priors[name.lower()], dtype=np.float64), (len(ids), 1))
            analytic.append(prediction_panel(output, name, values, ids,
                {'role': 'analytic', 'handle': name, 'view': r['view'], 'person': r['outer_person'],
                 'generation': generation, 'numeric_source': numeric_source, 'training_role': a['role']}, budget))
        result = {'selection': selection, 'priors': priors, 'role': a['role'], 'oof': a['oof'],
                  'view': r['view'], 'outer': r['outer_person'], 'analytic_panels': analytic}
    else:
        c.need(False, 'declared numerical operation')
    value = {'schema': 'neural081_reference_result_v1', 'operation': op, 'generation': generation,
             'numeric_source': numeric_source, 'body': result}
    return c.publish_json(output / 'RESULT.json', value, budget)
