"""One-window frozen-coefficient predictor; no fitting or hidden-label access.

Arithmetic is binary64 products followed by math.fsum including the intercept.
It is a new deterministic transport implementation, not BLAS bit parity.
"""
import json
import math
import re
import sys

SCHEMA = 'horrocks-frozen-linear-reference-v1'
ARITHMETIC = 'binary64-products-math-fsum-including-intercept-v1'
MODEL_CAP = 1048576


def require(value, reason):
    if not value:
        raise ValueError(reason)


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    def constant(value):
        raise ValueError('nonfinite JSON number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def validate_model(model):
    require(type(model) is dict and set(model) == {
        'schema', 'arithmetic', 'feature_count', 'selected_indices', 'beta', 'intercept'},
        'exact model fields; no owner identity or target metadata')
    require(model['schema'] == SCHEMA and model['arithmetic'] == ARITHMETIC, 'model method')
    n, selected, beta, intercept = (model[k] for k in
        ('feature_count', 'selected_indices', 'beta', 'intercept'))
    require(type(n) is int and 1 <= n <= 984, 'full source feature width')
    require(type(selected) is list and all(type(i) is int and 0 <= i < n for i in selected),
            'selected source positions')
    require(selected == sorted(set(selected)), 'mask true positions in original order')
    require(type(beta) is list and len(beta) == len(selected), 'one beta row per selected unit')
    require(all(type(row) is list and len(row) == 6 for row in beta), 'six ordered classes')
    require(type(intercept) is list and len(intercept) == 6, 'six class intercepts')
    require(all(type(v) is float and math.isfinite(v) for row in beta for v in row)
            and all(type(v) is float and math.isfinite(v) for v in intercept),
            'finite binary64 coefficients')
    require(selected or all(v == 0.0 for v in intercept), 'empty mask is uniform class-one tie')
    return model


def predict(model, counts):
    validate_model(model)
    require(type(counts) is list and len(counts) == model['feature_count'], 'complete query axis')
    require(all(type(v) is int and 0 <= v <= 2147483647 for v in counts), 'nonnegative int32 counts')
    selected, beta = model['selected_indices'], model['beta']
    scores = []
    for k in range(6):
        products = [counts[i] * row[k] for i, row in zip(selected, beta)]
        require(all(math.isfinite(v) for v in products), 'finite binary64 products')
        value = math.fsum([model['intercept'][k], *products])
        require(math.isfinite(value), 'finite class score')
        scores.append(value)
    # Python max returns the first position on exact ties: classes 1 through 6.
    return max(range(6), key=scores.__getitem__) + 1


def serve(model, incoming, outgoing):
    validate_model(model)
    raw = incoming.readline(16385)
    require(0 < len(raw) <= 16384 and raw.endswith(b'\n'), 'one bounded complete request')
    query = strict_json(raw)
    require(type(query) is dict and set(query) == {'schema', 'token', 'counts'}, 'exact wire fields')
    require(query['schema'] == 'horrocks-current-window-v1', 'query schema')
    require(type(query['token']) is str and re.fullmatch('[a-f0-9]{64}', query['token']) is not None,
            'opaque owner token')
    reply = {'token': query['token'], 'prediction': predict(model, query['counts'])}
    outgoing.write((json.dumps(reply, separators=(',', ':')) + '\n').encode())
    outgoing.flush()
    require(incoming.readline(4097) == b'{"schema":"horrocks-window-end-v1"}\n',
            'exact single-window end; no second query')


def main():
    with open('/model/model.json', 'rb') as stream:
        raw = stream.read(MODEL_CAP + 1)
    require(0 < len(raw) <= MODEL_CAP, 'bounded model')
    serve(strict_json(raw), sys.stdin.buffer, sys.stdout.buffer)


if __name__ == '__main__':
    main()
