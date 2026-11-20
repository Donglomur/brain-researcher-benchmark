"""Generated NumPy backend for source-composition tests, never a native model.

The primitive is a 21-coordinate linear predictor with masked L1 objective.
Momentum is deliberately generated (.6/.02), not claimed source Optax parity.
Source streaming, normalization, optimizer call composition and fit methods are
loaded separately and remain the system under test.
"""
import json
import math
from types import SimpleNamespace


def build_backend(np):
    class DeviceArray(np.ndarray):
        def block_until_ready(self):
            return self

    def asarray(value, dtype=None):
        return np.asarray(value, dtype=dtype).view(DeviceArray)

    def flatten(tree):
        leaves = []
        def visit(value):
            if isinstance(value, dict):
                return ('dict', tuple((key, visit(value[key])) for key in value))
            if isinstance(value, list):
                return ('list', tuple(visit(item) for item in value))
            if isinstance(value, tuple):
                return ('tuple', tuple(visit(item) for item in value))
            index = len(leaves)
            leaves.append(value)
            return ('leaf', index)
        return leaves, visit(tree)

    def unflatten(spec, leaves):
        kind, value = spec
        if kind == 'leaf':
            return leaves[value]
        if kind == 'dict':
            return {key: unflatten(child, leaves) for key, child in value}
        items = [unflatten(child, leaves) for child in value]
        return tuple(items) if kind == 'tuple' else items

    def tree_map(function, tree, *others):
        leaves, spec = flatten(tree)
        alternate = []
        for other in others:
            other_leaves, other_spec = flatten(other)
            if spec != other_spec:
                raise ValueError('generated tree mismatch')
            alternate.append(other_leaves)
        return unflatten(spec, [function(leaf, *(group[i] for group in alternate))
                                for i, leaf in enumerate(leaves)])

    def arrays(tree):
        if isinstance(tree, dict):
            return {key: asarray(value, np.float64) for key, value in tree.items()}
        if isinstance(tree, tuple):
            return tuple(arrays(value) for value in tree)
        if isinstance(tree, list):
            return [arrays(value) for value in tree]
        raise TypeError('generated parameter groups')

    def l2_norm(tree):
        return math.sqrt(sum(float(np.sum(np.asarray(leaf) ** 2)) for leaf in flatten(tree)[0]))

    def validate(role, tree):
        for leaf in flatten(tree)[0]:
            value = np.asarray(leaf)
            if value.dtype.kind not in 'iuf' or not bool(np.isfinite(value).all()):
                raise ValueError('generated finite guard: ' + role)

    class GeneratedCodec:
        @staticmethod
        def encode_tree(tree, numpy, tree_util, *, role):
            validate(role, tree)
            leaves, spec = flatten(tree)
            return {'structure': spec, 'leaves': [
                {'shape': list(np.asarray(leaf).shape), 'dtype': np.asarray(leaf).dtype.str,
                 'values': np.asarray(leaf).tolist()} for leaf in leaves]}
        @staticmethod
        def canonical(value):
            return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()

    class Momentum:
        def update(self, gradient, old_state):
            state = tree_map(lambda old, grad: .6 * old + grad, old_state, gradient)
            return tree_map(lambda value: -.02 * value, state), state

    coefficients = ((np.arange(147)[:, None] + 1) *
                    (np.arange(21)[None, :] + 1) % 149 + 1).astype(np.float64) / 149
    observations = []

    def coordinates(parameters):
        return np.concatenate([np.asarray(value).reshape(-1) for value in flatten(parameters)[0]])

    def gradient(*arguments):
        parameters = arguments[:3]
        currents, labels, mask, states = arguments[3:]
        observations.append((tuple(id(group) for group in parameters), id(states)))
        theta = coordinates(parameters)
        features = np.asarray(currents)[:, 0]
        predicted = features[:, None] * (coefficients @ theta)[None, :]
        residual = predicted - labels
        weighted_sign = np.sign(residual) * mask
        loss = np.sum(np.abs(residual) * mask) / len(features)
        derivative = np.sum(features[:, None] * (weighted_sign @ coefficients), axis=0) / len(features)
        leaves, structure = flatten(parameters)
        result, offset = [], 0
        for leaf in leaves:
            count = np.asarray(leaf).size
            result.append(asarray(derivative[offset:offset + count].reshape(np.asarray(leaf).shape)))
            offset += count
        if offset != 21:
            raise ValueError('generated coordinate count')
        return asarray(loss), unflatten(structure, result)

    return SimpleNamespace(
        jnp=SimpleNamespace(asarray=asarray, float64=np.float64),
        tree_util=SimpleNamespace(tree_flatten=flatten, tree_unflatten=unflatten,
                                  tree_leaves=lambda tree: flatten(tree)[0]),
        tree_map=tree_map, arrays=arrays, l2_norm=l2_norm, validate=validate,
        codec=GeneratedCodec, optimizers=(Momentum(), Momentum(), Momentum()),
        optax=SimpleNamespace(apply_updates=lambda old, change: tree_map(lambda a, b: a + b, old, change)),
        gradient=gradient, observations=observations, coordinates=coordinates,
    )
