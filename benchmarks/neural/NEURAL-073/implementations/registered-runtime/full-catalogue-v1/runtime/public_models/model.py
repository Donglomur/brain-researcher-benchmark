"""Standalone, bounded public inference DTOs; no evaluator import on inference paths.

NumPy 2.4.6 is imported only by predict_raw. project_fitted is evaluator-only;
its relative imports are deferred and never needed in a standalone candidate.
All limits are per-operation logical ceilings, not native RSS/CPU guarantees.
"""
from dataclasses import dataclass
import base64
import binascii
import hashlib
import hmac
import json
import math
import struct
import sys

SCHEMA = 'n073_public_model_v1'
ALGORITHMS = ('ridge', 'centroid', 'linear_ovr_svm', 'rbf_ovr_svm', 'extra_trees')


class PublicModelError(ValueError):
    pass


@dataclass(frozen=True)
class PublicModelLimits:
    max_elements: int
    max_workspace_bytes: int
    max_nodes: int
    max_json_bytes: int


@dataclass(frozen=True)
class NumericArray:
    shape: tuple
    body: bytes


@dataclass(frozen=True)
class PublicNode:
    feature: int
    threshold: float | None
    left: int
    right: int
    probabilities: tuple


@dataclass(frozen=True)
class PublicModel:
    algorithm: str
    classes: int
    features: int
    arrays: tuple
    gamma: float | None = None
    trees: tuple = ()

    def to_dict(self, *, limits):
        return to_dict(self, limits=limits)

    def predict_raw(self, x, *, limits):
        return predict_raw(self, x, limits=limits)


def _limits(limits):
    if type(limits) is not PublicModelLimits or any(
            type(v) is not int or v <= 0 for v in (
                limits.max_elements, limits.max_workspace_bytes,
                limits.max_nodes, limits.max_json_bytes)):
        raise PublicModelError('invalid_limits')


def _keys(obj, keys, role):
    if type(obj) is not dict or len(obj) != len(keys) or set(obj) != set(keys):
        raise PublicModelError('invalid_fields:' + role)


def _integer(value, low, high, role):
    if type(value) is not int or not low <= value <= high:
        raise PublicModelError('invalid_integer:' + role)
    return value


def _number(value, role, positive=False):
    if type(value) not in (int, float):
        raise PublicModelError('invalid_number:' + role)
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise PublicModelError('invalid_number:' + role) from exc
    if not math.isfinite(value) or (positive and value <= 0):
        raise PublicModelError('invalid_number:' + role)
    return value


class _Extent:
    def __init__(self, limits):
        _limits(limits)
        self.limits = limits
        self.elements = 0
        self.nodes = 0
        self.json_bound = 512

    def check(self):
        # Covers decoded bodies, canonical DTO strings/bytes and Python node
        # bookkeeping conservatively. A worker still needs OS resource limits.
        if self.elements > self.limits.max_elements or self.nodes > self.limits.max_nodes:
            raise PublicModelError('parameter_extent_limit')
        if self.json_bound > self.limits.max_json_bytes:
            raise PublicModelError('encoded_extent_limit')
        if 32*self.elements + 2048*self.nodes + 4*self.json_bound > self.limits.max_workspace_bytes:
            raise PublicModelError('parameter_workspace_limit')

    def array(self, shape):
        if type(shape) not in (list, tuple) or not 1 <= len(shape) <= 2:
            raise PublicModelError('invalid_array_shape')
        for x in shape:
            _integer(x, 1, self.limits.max_elements, 'array_axis')
        n = math.prod(shape)
        self.elements += n
        self.json_bound += 256 + 4*((8*n+2)//3)
        self.check()
        return n

    def tree_nodes(self, count):
        self.nodes += count
        self.elements += 25*count  # Conservative: internal nodes have no probabilities.
        self.json_bound += 1024*count + 16
        self.check()


def _finite_body(body):
    if any(not math.isfinite(x[0]) for x in struct.iter_unpack('<d', body)):
        raise PublicModelError('nonfinite_array')


def _decode_array(value, extent):
    _keys(value, ('dtype', 'shape', 'base64'), 'array')
    if type(value['dtype']) is not str or value['dtype'] != '<f8' or type(value['shape']) is not list:
        raise PublicModelError('invalid_array_codec')
    n = extent.array(value['shape'])
    text = value['base64']
    if type(text) is not str or len(text) != 4*((8*n+2)//3):
        raise PublicModelError('array_encoded_extent')
    try:
        body = base64.b64decode(text, validate=True)
    except (ValueError, TypeError, binascii.Error) as exc:
        raise PublicModelError('invalid_base64') from exc
    if len(body) != 8*n or base64.b64encode(body).decode('ascii') != text:
        raise PublicModelError('noncanonical_array_encoding')
    _finite_body(body)
    return NumericArray(tuple(value['shape']), body)


def _validate_array(value, extent):
    if type(value) is not NumericArray or type(value.shape) is not tuple or type(value.body) is not bytes:
        raise PublicModelError('invalid_numeric_array')
    n = extent.array(value.shape)
    if len(value.body) != 8*n:
        raise PublicModelError('array_body_extent')
    _finite_body(value.body)


def _array_dto(array):
    return {'dtype': '<f8', 'shape': list(array.shape),
            'base64': base64.b64encode(array.body).decode('ascii')}


def _tree_graph(tree, features):
    parents = [0]*len(tree)
    for index, node in enumerate(tree):
        if type(node) is not PublicNode or type(node.probabilities) is not tuple:
            raise PublicModelError('invalid_node_type')
        _integer(node.feature, -1, features-1, 'node_feature')
        if node.feature == -1:
            if node.threshold is not None or type(node.left) is not int or node.left != -1 or type(node.right) is not int or node.right != -1 or len(node.probabilities) != 25:
                raise PublicModelError('invalid_leaf')
            for p in node.probabilities:
                p = _number(p, 'leaf_probability')
                if not 0 <= p <= 1:
                    raise PublicModelError('invalid_leaf_probability')
            if abs(math.fsum(node.probabilities)-1.0) > 1e-12:
                raise PublicModelError('leaf_probability_sum')
        else:
            _number(node.threshold, 'threshold')
            if node.probabilities:
                raise PublicModelError('internal_node_probabilities')
            _integer(node.left, index+1, len(tree)-1, 'left')
            _integer(node.right, index+1, len(tree)-1, 'right')
            if node.left == node.right:
                raise PublicModelError('shared_child')
            parents[node.left] += 1
            parents[node.right] += 1
    if parents[0] != 0 or any(p != 1 for p in parents[1:]):
        raise PublicModelError('unreachable_or_shared_node')


def _tree_from_dto(raw, features, extent):
    if type(raw) is not list or len(raw) != 256:
        raise PublicModelError('tree_count_must_be_256')
    trees = []
    for rawtree in raw:
        if type(rawtree) is not list or not rawtree:
            raise PublicModelError('invalid_tree')
        extent.tree_nodes(len(rawtree))
        nodes = []
        for row in rawtree:
            _keys(row, ('feature','threshold','left','right','probabilities'), 'node')
            if type(row['probabilities']) is not list or len(row['probabilities']) not in (0,25):
                raise PublicModelError('invalid_node_probability_extent')
            nodes.append(PublicNode(row['feature'], None if row['threshold'] is None else _number(row['threshold'],'threshold'),
                                    row['left'], row['right'], tuple(_number(p,'probability') for p in row['probabilities'])))
        tree = tuple(nodes)
        _tree_graph(tree, features)
        trees.append(tree)
    return tuple(trees)


def _layout(model):
    fields = dict(model.arrays)
    if model.algorithm in ('ridge', 'linear_ovr_svm'):
        if set(fields) != {'coefficients','intercept'} or fields['coefficients'].shape != (model.features,25) or fields['intercept'].shape != (25,) or model.gamma is not None or model.trees:
            raise PublicModelError('linear_parameter_layout')
    elif model.algorithm == 'centroid':
        if set(fields) != {'centers'} or fields['centers'].shape != (25,model.features) or model.gamma is not None or model.trees:
            raise PublicModelError('centroid_parameter_layout')
    elif model.algorithm == 'rbf_ovr_svm':
        if set(fields) != {'support_vectors','dual_coefficients','intercept'}:
            raise PublicModelError('rbf_parameter_fields')
        x = fields['support_vectors']
        if len(x.shape) != 2 or x.shape[1] != model.features or fields['dual_coefficients'].shape != (x.shape[0],25) or fields['intercept'].shape != (25,) or model.trees:
            raise PublicModelError('rbf_parameter_layout')
        _number(model.gamma, 'gamma', True)
    elif fields or model.gamma is not None or len(model.trees) != 256:
        raise PublicModelError('tree_parameter_layout')


def _validate(model, limits):
    extent = _Extent(limits)
    if type(model) is not PublicModel or type(model.algorithm) is not str or model.algorithm not in ALGORITHMS or type(model.classes) is not int or model.classes != 25:
        raise PublicModelError('invalid_model')
    _integer(model.features, 1, limits.max_elements, 'features')
    if type(model.arrays) is not tuple or type(model.trees) is not tuple or len(model.arrays) > 3:
        raise PublicModelError('invalid_parameter_containers')
    seen = set()
    for entry in model.arrays:
        if type(entry) is not tuple or len(entry) != 2 or type(entry[0]) is not str or entry[0] not in ('coefficients','intercept','centers','support_vectors','dual_coefficients') or entry[0] in seen:
            raise PublicModelError('invalid_array_parameter')
        seen.add(entry[0])
        _validate_array(entry[1], extent)
    if len(model.trees) > 256:
        raise PublicModelError('tree_count_must_be_256')
    for tree in model.trees:
        if type(tree) is not tuple or not tree:
            raise PublicModelError('invalid_tree')
        extent.tree_nodes(len(tree))
        _tree_graph(tree, model.features)
    _layout(model)
    extent.check()
    return extent


def _dto(model):
    parameters = {key: _array_dto(array) for key, array in model.arrays}
    if model.algorithm == 'rbf_ovr_svm':
        parameters['gamma'] = float(model.gamma)
    if model.algorithm == 'extra_trees':
        parameters['trees'] = [[{'feature': n.feature, 'threshold': None if n.threshold is None else float(n.threshold),
                                'left': n.left, 'right': n.right,
                                'probabilities': [float(p) for p in n.probabilities]} for n in tree] for tree in model.trees]
    return {'schema': SCHEMA, 'algorithm': model.algorithm, 'classes': 25,
            'features': model.features, 'parameters': parameters}


def _canonical(dto, limits):
    body = json.dumps(dto, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
    if len(body) > limits.max_json_bytes:
        raise PublicModelError('canonical_json_extent')
    return body


def to_dict(model, *, limits):
    _validate(model, limits)
    result = _dto(model)
    _canonical(result, limits)
    return result


def _parse(dto, limits):
    extent = _Extent(limits)
    _keys(dto, ('schema','algorithm','classes','features','parameters'), 'model')
    if type(dto['schema']) is not str or dto['schema'] != SCHEMA or type(dto['algorithm']) is not str or dto['algorithm'] not in ALGORITHMS or type(dto['classes']) is not int or dto['classes'] != 25:
        raise PublicModelError('invalid_public_model_header')
    d = _integer(dto['features'], 1, limits.max_elements, 'features')
    algorithm = dto['algorithm']; p = dto['parameters']; gamma = None; trees = ()
    names = {'ridge': ('coefficients','intercept'), 'linear_ovr_svm': ('coefficients','intercept'),
             'centroid': ('centers',), 'rbf_ovr_svm': ('support_vectors','dual_coefficients','intercept','gamma'),
             'extra_trees': ('trees',)}[algorithm]
    _keys(p, names, 'parameters')
    if algorithm == 'extra_trees':
        arrays = (); trees = _tree_from_dto(p['trees'], d, extent)
    else:
        arrays = tuple((key, _decode_array(p[key], extent)) for key in names if key != 'gamma')
        if algorithm == 'rbf_ovr_svm':
            gamma = _number(p['gamma'], 'gamma', True)
    model = PublicModel(algorithm, 25, d, arrays, gamma, trees)
    _layout(model)
    return model


def parameter_digest(dto, *, limits):
    """Digest the canonical validated public payload; no provenance is embedded."""
    model = _parse(dto, limits)
    return hashlib.sha256(_canonical(_dto(model), limits)).hexdigest()


def from_dict(dto, *, expected_parameter_digest, limits):
    """Caller must obtain expected digest from its trusted manifest, separately."""
    if type(expected_parameter_digest) is not str or len(expected_parameter_digest) != 64 or any(c not in '0123456789abcdef' for c in expected_parameter_digest):
        raise PublicModelError('invalid_expected_parameter_digest')
    model = _parse(dto, limits)
    actual = hashlib.sha256(_canonical(_dto(model), limits)).hexdigest()
    if not hmac.compare_digest(actual, expected_parameter_digest):
        raise PublicModelError('parameter_digest_mismatch')
    return model


def project_fitted(state, *, limits):
    """Evaluator-only exact-class projection; never calls private to_dict.

    Private imports are deliberately deferred. Standalone candidate inference
    does not require or mount any private package. Caller separately authenticates
    fit qualification, selected family, transform binding and fitted-state custody.
    """
    _limits(limits)
    from ..transforms.numeric import Ridge, Centroid
    from ..estimators.svm import SVMState
    from ..estimators.trees import ExtraTreesState, TreeNode
    from ..estimators._common import FrozenArray
    extent = _Extent(limits)

    def numpy_array(value):
        np = sys.modules.get('numpy')
        if np is None or np.__version__ != '2.4.6' or type(value) is not np.ndarray or value.dtype != np.dtype('float64'):
            raise PublicModelError('qualified_numpy_state_required')
        extent.array(tuple(value.shape))
        if value.flags.writeable or not value.flags.c_contiguous:
            raise PublicModelError('immutable_contiguous_state_required')
        out = NumericArray(tuple(value.shape), value.astype('<f8',copy=False).tobytes(order='C'))
        _finite_body(out.body)
        return out

    def frozen_array(value):
        if type(value) is not FrozenArray:
            raise PublicModelError('exact_frozen_array_required')
        out = NumericArray(value.shape, value.body)
        _validate_array(out, extent)
        return out

    if type(state) is Ridge:
        a = numpy_array(state.coefficients); b = numpy_array(state.intercept)
        if len(a.shape) != 2 or b.shape != (25,):
            raise PublicModelError('invalid_private_ridge_shape')
        model = PublicModel('ridge',25,a.shape[0],(('coefficients',a),('intercept',b)))
    elif type(state) is Centroid:
        a = numpy_array(state.centers)
        if len(a.shape) != 2:
            raise PublicModelError('invalid_private_centroid_shape')
        model = PublicModel('centroid',25,a.shape[1],(('centers',a),))
    elif type(state) is SVMState:
        if state.production_wrapper is not True or type(state.classes) is not int or state.classes != 25 or state.kernel not in ('linear','rbf'):
            raise PublicModelError('production_svm_required')
        a = frozen_array(state.coefficients); b = frozen_array(state.intercepts)
        if state.kernel == 'linear':
            if state.training_X is not None or state.gamma is not None:
                raise PublicModelError('invalid_private_linear_layout')
            model = PublicModel('linear_ovr_svm',25,state.features,(('coefficients',a),('intercept',b)))
        else:
            x = frozen_array(state.training_X)
            model = PublicModel('rbf_ovr_svm',25,state.features,(('support_vectors',x),('dual_coefficients',a),('intercept',b)),_number(state.gamma,'gamma',True))
    elif type(state) is ExtraTreesState:
        if state.production_wrapper is not True or type(state.classes) is not int or state.classes != 25 or type(state.trees) is not tuple or len(state.trees) != 256:
            raise PublicModelError('production_tree_state_required')
        trees = []
        for tree in state.trees:
            if type(tree) is not tuple or not tree:
                raise PublicModelError('invalid_private_tree')
            extent.tree_nodes(len(tree))
            nodes = []
            for n in tree:
                if type(n) is not TreeNode or type(n.probabilities) is not tuple or len(n.probabilities) not in (0,25):
                    raise PublicModelError('invalid_private_node')
                nodes.append(PublicNode(n.feature,n.threshold,n.left,n.right,n.probabilities))
            trees.append(tuple(nodes))
        model = PublicModel('extra_trees',25,state.features,(),None,tuple(trees))
    else:
        raise PublicModelError('unsupported_private_state_type')
    _validate(model, limits)
    return model


def predict_raw(model, x, *, limits):
    """Direct five-family score math. No private evaluator import or callbacks."""
    extent = _validate(model, limits)
    import numpy as np
    if np.__version__ != '2.4.6':
        raise PublicModelError('qualified_numpy_2_4_6_required')
    if type(x) is not np.ndarray or x.dtype != np.dtype('float64') or x.ndim != 2 or x.shape[0] <= 0 or x.shape[1] != model.features:
        raise PublicModelError('invalid_prediction_matrix')
    if model.algorithm not in ('ridge','centroid') and not x.flags.c_contiguous:
        raise PublicModelError('contiguous_prediction_matrix_required')
    q,d = x.shape
    arrays = dict(model.arrays)
    param = {key: np.frombuffer(a.body,dtype='<f8').reshape(a.shape) for key,a in arrays.items()}
    workspace_elements = x.size + 3*q*25 + extent.elements
    if model.algorithm == 'centroid':
        workspace_elements += 5*(x.size+25*d) + 6*(q+25)
    elif model.algorithm == 'rbf_ovr_svm':
        n = arrays['support_vectors'].shape[0]
        workspace_elements += q*n + n*d
    logical_bytes = 8*workspace_elements + 2048*extent.nodes + 256*8
    if workspace_elements > limits.max_elements or logical_bytes > limits.max_workspace_bytes:
        raise PublicModelError('prediction_workspace_limit')
    if any(not math.isfinite(float(v)) for v in x.flat):
        raise PublicModelError('nonfinite_prediction_input')
    if model.algorithm == 'ridge':
        scores = x @ param['coefficients'] + param['intercept']
    elif model.algorithm == 'centroid':
        def units(a):
            peak = np.max(np.abs(a),axis=1)
            z = a/np.where(peak==0,1,peak)[:,None]
            norm = np.sqrt(np.sum(z*z,axis=1))
            return z/np.where(norm==0,1,norm)[:,None]
        scores = units(x) @ units(param['centers']).T
    elif model.algorithm in ('linear_ovr_svm','rbf_ovr_svm'):
        scores = np.empty((q,25),dtype=np.float64)
        if model.algorithm == 'linear_ovr_svm':
            np.dot(x,param['coefficients'],out=scores)
        else:
            y = param['support_vectors']
            kernel = np.empty((q,y.shape[0]),dtype=np.float64)
            difference = np.empty(y.shape,dtype=np.float64)
            for i in range(q):
                np.subtract(y,x[i],out=difference)
                np.multiply(difference,difference,out=difference)
                np.sum(difference,axis=1,out=kernel[i])
                kernel[i] *= -model.gamma
                np.exp(kernel[i],out=kernel[i])
            if any(not math.isfinite(float(v)) for v in kernel.flat):
                raise PublicModelError('nonfinite_kernel')
            np.dot(kernel,param['dual_coefficients'],out=scores)
        scores += param['intercept']
    else:
        scores = np.empty((q,25),dtype=np.float64)
        for row in range(q):
            leaves = []
            for tree in model.trees:
                index = 0
                while tree[index].feature >= 0:
                    node = tree[index]
                    index = node.left if float(x[row,node.feature]) <= node.threshold else node.right
                leaves.append(tree[index].probabilities)
            for k in range(25):
                p = math.fsum(leaf[k] for leaf in leaves)/len(model.trees)
                scores[row,k] = math.log(max(p,1e-12))
    if any(not math.isfinite(float(v)) for v in scores.flat):
        raise PublicModelError('nonfinite_raw_scores')
    return np.frombuffer(scores.astype('<f8',copy=False).tobytes(order='C'),dtype='<f8').reshape((q,25))
