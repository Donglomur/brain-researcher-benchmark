"""Weighted hinge SVM with an explicit feasible dual and gap certificate.

One iteration is one exact bounded two-coordinate ascent step on the signed dual.
No solver library or opaque success callback is used. Production wrappers require
all 25 classes; explicitly named primitives support invented component controls.
"""
from dataclasses import dataclass, asdict
import math
from ._common import (EstimatorError, NumericBudget, FrozenArray, numpy, matrix,
                      training, empty, finite_number, context, context_dict,
                      strict_keys, production_features)


@dataclass(frozen=True)
class GapCertificate:
    primal: float
    dual: float
    absolute_gap: float
    relative_gap: float
    equality_residual: float
    box_violation: float
    iterations: int
    converged: bool

    def to_dict(self):
        return asdict(self)


def _bias_minimizer(g, alpha, y, budget):
    """Minimize weighted hinge over the unpenalized intercept for fixed w.

Each breakpoint g_i=y_i-f0_i increases the derivative by alpha_i. The total
positive-label alpha mass is the threshold. Deterministic index ties are benign.
"""
    n = len(y)
    budget.charge(n * 8, 'bias_sort_indices')
    budget.tick('bias_sort_input_rows', n)
    order = sorted(range(n), key=lambda k: (float(g[k]), k))
    target = math.fsum(float(alpha[k]) for k in range(n) if y[k] > 0)
    cumulative = 0.0
    for j, k in enumerate(order):
        cumulative = math.fsum((cumulative, float(alpha[k])))
        if cumulative >= target:
            if cumulative == target and j + 1 < n:
                # Avoid overflow in a+b for two large same-sign values.
                return 0.5 * float(g[k]) + 0.5 * float(g[order[j + 1]])
            return float(g[k])
    raise EstimatorError('bias_weight_mass_inconsistent')


def _certificate(K, signed, y, alpha, lambda_, iteration, f0, g, budget, tolerance):
    np = numpy()
    n = len(y)
    budget.tick('certificate_kernel_scalar_products', n * n)
    np.dot(K, signed, out=f0)
    f0 /= lambda_
    for i in range(n):
        g[i] = y[i] - f0[i]
    b = _bias_minimizer(g, alpha, y, budget)
    # signed.T @ K @ signed / lambda = lambda*||w||^2.
    norm_term = math.fsum(float(signed[i]) * float(f0[i]) for i in range(n))
    if not math.isfinite(norm_term) or norm_term < -1e-12:
        raise EstimatorError('invalid_kernel_norm')
    norm_term = max(norm_term, 0.0)
    hinge = math.fsum(float(alpha[i]) * max(0.0, 1.0 - y[i] * (float(f0[i]) + b)) for i in range(n))
    primal = 0.5 * norm_term + hinge
    dual = math.fsum(y[i] * float(signed[i]) for i in range(n)) - 0.5 * norm_term
    equality = abs(math.fsum(float(x) for x in signed))
    violation = max(max(-y[i] * float(signed[i]), y[i] * float(signed[i]) - float(alpha[i]), 0.0) for i in range(n))
    if not all(math.isfinite(x) for x in (primal, dual, b, equality, violation)):
        raise EstimatorError('nonfinite_svm_certificate')
    raw_gap = primal - dual
    scale = max(abs(primal), abs(dual), 1e-12)
    if raw_gap < -1e-10 * scale:
        raise EstimatorError('negative_duality_gap', {'primal': primal, 'dual': dual})
    gap = max(raw_gap, 0.0)
    relative = gap / scale
    converged = relative <= tolerance and equality <= 1e-10 and violation <= 1e-12
    return b, GapCertificate(primal, dual, gap, relative, equality, violation, iteration, converged)


def solve_binary_primitive(K, y, alpha, lambda_, budget, *, max_iterations=100000,
                           tolerance=1e-5):
    """Invented-control/algorithm primitive; not a 25-class production fit.

Returns immutable signed-dual coefficients, intercept and a valid certificate.
Raises with the final certificate if convergence is not certified. Dual variables
beta_i=y_i*a_i satisfy 0<=beta_i<=alpha_i and sum_i a_i=0.
"""
    np = numpy()
    matrix(K, budget, 'kernel')
    n = K.shape[0]
    if K.shape[1] != n or type(y) not in (list, tuple) or len(y) != n or set(y) != {-1, 1}:
        raise EstimatorError('invalid_binary_support')
    if any(type(t) is not int for t in y):
        raise EstimatorError('invalid_binary_labels')
    if (type(alpha) is not np.ndarray or alpha.dtype != np.dtype('float64') or
            alpha.shape != (n,) or not alpha.flags.c_contiguous or
            any(not math.isfinite(float(x)) or x <= 0 for x in alpha)):
        raise EstimatorError('invalid_binary_weights')
    if abs(math.fsum(float(x) for x in alpha) - 1.0) > 1e-12:
        raise EstimatorError('binary_weights_not_normalized')
    lambda_ = finite_number(lambda_, 'lambda', True)
    tolerance = finite_number(tolerance, 'tolerance', True)
    if tolerance > 1e-5 or type(max_iterations) is not int or not 0 <= max_iterations <= 100000:
        raise EstimatorError('invalid_solver_limits')
    # This is an input certificate, not an arbitrary PSD claim. Constructed
    # linear/RBF kernels are PSD mathematically; negative pair curvature refuses.
    for i in range(n):
        if float(K[i, i]) < -1e-12:
            raise EstimatorError('negative_kernel_diagonal')
        for j in range(i):
            scale = max(1.0, abs(float(K[i, j])), abs(float(K[j, i])))
            if abs(float(K[i, j]) - float(K[j, i])) > 1e-12 * scale:
                raise EstimatorError('asymmetric_kernel')
    budget.tick('checked_kernel_entries', n * n)
    a = empty((n,), budget, 'dual_coefficients'); a.fill(0.0)
    g = empty((n,), budget, 'dual_gradient')
    f0 = empty((n,), budget, 'training_margin')
    scratch = empty((n,), budget, 'dual_update')
    lower = empty((n,), budget, 'dual_lower')
    upper = empty((n,), budget, 'dual_upper')
    for i in range(n):
        g[i] = y[i]
        lower[i] = -alpha[i] if y[i] < 0 else 0.0
        upper[i] = alpha[i] if y[i] > 0 else 0.0
    b, cert = _certificate(K, a, y, alpha, lambda_, 0, f0, g, budget, tolerance)
    for iteration in range(1, max_iterations + 1):
        if cert.converged:
            break
        budget.tick('svm_pair_iterations')
        inc = None; dec = None
        for k in range(n):
            if a[k] < upper[k] and (inc is None or g[k] > g[inc]):
                inc = k
            if a[k] > lower[k] and (dec is None or g[k] < g[dec]):
                dec = k
        if inc is None or dec is None:
            raise EstimatorError('no_feasible_dual_pair', cert.to_dict())
        derivative = float(g[inc] - g[dec])
        if inc == dec or derivative <= 0.0:
            b, cert = _certificate(K, a, y, alpha, lambda_, iteration - 1, f0, g, budget, tolerance)
            if cert.converged:
                break
            raise EstimatorError('stationarity_without_gap_certificate', cert.to_dict())
        capacity = min(float(upper[inc] - a[inc]), float(a[dec] - lower[dec]))
        numerator = float(K[inc, inc] + K[dec, dec] - 2.0 * K[inc, dec])
        curvature_scale = max(1.0, abs(float(K[inc, inc])), abs(float(K[dec, dec])), abs(float(K[inc, dec])))
        if numerator < -1e-12 * curvature_scale:
            raise EstimatorError('negative_pair_curvature')
        curvature = max(numerator, 0.0) / lambda_
        step = capacity if curvature == 0.0 else min(capacity, derivative / curvature)
        if not math.isfinite(step) or step <= 0.0:
            raise EstimatorError('dual_pair_stagnation', cert.to_dict())
        old_i = float(a[inc]); old_j = float(a[dec])
        a[inc] = old_i + step; a[dec] = old_j - step
        if a[inc] == old_i and a[dec] == old_j:
            raise EstimatorError('dual_pair_stagnation', cert.to_dict())
        np.subtract(K[:, inc], K[:, dec], out=scratch)
        scratch *= step / lambda_
        np.subtract(g, scratch, out=g)
        budget.tick('dual_gradient_updated_values', n)
        if iteration % 16 == 0 or iteration == max_iterations:
            b, cert = _certificate(K, a, y, alpha, lambda_, iteration, f0, g, budget, tolerance)
    else:
        iteration = max_iterations
    # Always recompute from the actual retained coefficient vector, including
    # an early exit and max_iterations=0. Iteration count is not success.
    b, cert = _certificate(K, a, y, alpha, lambda_, cert.iterations if cert.converged else max_iterations,
                           f0, g, budget, tolerance)
    if not cert.converged:
        raise EstimatorError('svm_not_converged', cert.to_dict())
    return FrozenArray.freeze(a, budget, 'signed_dual'), b, cert


def training_gamma(X, weights, factor, budget):
    np = numpy()
    factor = finite_number(factor, 'gamma_factor', True)
    mean = empty((X.shape[1],), budget, 'rbf_training_mean')
    difference = empty((X.shape[1],), budget, 'rbf_variance_difference')
    np.dot(weights, X, out=mean)
    terms = []
    budget.charge(X.shape[0] * 8, 'rbf_variance_terms')
    for i in range(X.shape[0]):
        np.subtract(X[i], mean, out=difference)
        terms.append(float(weights[i]) * float(np.dot(difference, difference)))
    variance = math.fsum(terms)
    if not math.isfinite(variance) or variance < 0:
        raise EstimatorError('invalid_training_variance')
    gamma = factor / max(variance, 1e-12)
    if not math.isfinite(gamma):
        raise EstimatorError('nonfinite_gamma')
    budget.tick('rbf_variance_scalar_values', X.size)
    return gamma


def kernel_matrix(X, Y, kernel, gamma, budget):
    np = numpy()
    result = empty((X.shape[0], Y.shape[0]), budget, 'kernel_matrix')
    if kernel == 'linear':
        np.dot(X, Y.T, out=result)
        budget.tick('linear_kernel_multiply_terms', X.shape[0] * Y.shape[0] * X.shape[1])
    elif kernel == 'rbf':
        difference = empty(tuple(Y.shape), budget, 'rbf_pair_difference')
        for i in range(X.shape[0]):
            np.subtract(Y, X[i], out=difference)
            np.multiply(difference, difference, out=difference)
            np.sum(difference, axis=1, out=result[i])
            result[i] *= -gamma
            np.exp(result[i], out=result[i])
        budget.tick('rbf_kernel_distance_terms', X.shape[0] * Y.shape[0] * X.shape[1])
    else:
        raise EstimatorError('invalid_kernel')
    if any(not math.isfinite(float(x)) for x in result.flat):
        raise EstimatorError('nonfinite_kernel')
    return result


@dataclass(frozen=True)
class SVMState:
    kernel: str
    classes: int
    features: int
    lambda_: float
    gamma: float | None
    coefficients: FrozenArray
    intercepts: FrozenArray
    training_X: FrozenArray | None
    certificates: tuple
    fit_context: tuple
    production_wrapper: bool
    full_grid_dimension: int | None = None

    def to_dict(self, budget):
        return {'schema': 'n073_svm_state_v2', 'kernel': self.kernel,
                'family': 'linear_ovr_svm' if self.kernel=='linear' else 'rbf_ovr_svm',
                'full_grid_dimension': self.full_grid_dimension,
                'classes': self.classes, 'features': self.features,
                'lambda': self.lambda_, 'gamma': self.gamma,
                'coefficients': self.coefficients.to_dict(budget),
                'intercepts': self.intercepts.to_dict(budget),
                'training_X': None if self.training_X is None else self.training_X.to_dict(budget),
                'certificates': [c.to_dict() for c in self.certificates],
                'context': context_dict(self.fit_context),
                'production_wrapper': self.production_wrapper}

    @classmethod
    def from_dict(cls, value, budget, *, max_elements):
        strict_keys(value, ['schema','kernel','family','full_grid_dimension','classes','features','lambda','gamma','coefficients',
                            'intercepts','training_X','certificates','context','production_wrapper'], 'svm_state')
        if value['schema'] != 'n073_svm_state_v2' or value['kernel'] not in ('linear','rbf'):
            raise EstimatorError('unsupported_svm_state')
        k=value['classes']; d=value['features']; production=value['production_wrapper']
        if type(k) is not int or not 2<=k<=25 or type(d) is not int or d<=0 or type(production) is not bool:
            raise EstimatorError('invalid_svm_state_dimensions')
        if production and k!=25:
            raise EstimatorError('invalid_production_class_count')
        family='linear_ovr_svm' if value['kernel']=='linear' else 'rbf_ovr_svm'
        if value['family']!=family:
            raise EstimatorError('inconsistent_svm_family')
        lam=finite_number(value['lambda'],'lambda',True)
        gamma=None if value['gamma'] is None else finite_number(value['gamma'],'gamma',True)
        full_D=value['full_grid_dimension']
        checked_context=context(value['context'])
        if production:
            class Width:
                shape=(1,d)
            production_features(Width(),value['context'],family,full_D)
            if lam not in ([1e-5,1e-3,.1,10] if value['kernel']=='linear' else [1e-4,.01,1]):
                raise EstimatorError('serialized_svm_outside_frozen_grid')
        elif full_D is not None:
            raise EstimatorError('primitive_state_has_production_grid_binding')
        coef=FrozenArray.from_dict(value['coefficients'],budget,2,max_elements)
        intercept=FrozenArray.from_dict(value['intercepts'],budget,1,25)
        tx=None if value['training_X'] is None else FrozenArray.from_dict(value['training_X'],budget,2,max_elements)
        if coef.shape[1]!=k or intercept.shape!=(k,):
            raise EstimatorError('svm_state_class_extent')
        if value['kernel']=='linear':
            if coef.shape!=(d,k) or tx is not None or gamma is not None:
                raise EstimatorError('linear_state_extent')
        elif tx is None or tx.shape[1]!=d or coef.shape[0]!=tx.shape[0] or gamma is None:
            raise EstimatorError('rbf_state_extent')
        raw=value['certificates']
        if type(raw) is not list or len(raw)!=k:
            raise EstimatorError('invalid_certificate_count')
        certs=[]
        for x in raw:
            strict_keys(x, GapCertificate.__dataclass_fields__, 'certificate')
            if type(x['iterations']) is not int or not 0<=x['iterations']<=100000 or x['converged'] is not True:
                raise EstimatorError('unqualified_certificate_state')
            for key in ('primal','dual','absolute_gap','relative_gap','equality_residual','box_violation'):
                finite_number(x[key], key)
            if (x['primal']<0 or x['absolute_gap']<0 or not 0<=x['relative_gap']<=1e-5 or
                    not 0<=x['equality_residual']<=1e-10 or not 0<=x['box_violation']<=1e-12):
                raise EstimatorError('invalid_certificate_bounds')
            scale=max(abs(x['primal']),abs(x['dual']),1e-12)
            derived=max(x['primal']-x['dual'],0.0)
            if (x['dual']>x['primal']+1e-10*scale or
                    abs(x['absolute_gap']-derived)>1e-12*scale or
                    abs(x['relative_gap']-derived/scale)>1e-12):
                raise EstimatorError('inconsistent_certificate_objectives')
            certs.append(GapCertificate(**x))
        # This validates structure only. It does not authenticate source lineage
        # or recompute a fit; parent signed/pinned artifact custody is mandatory.
        return cls(value['kernel'],k,d,lam,gamma,coef,intercept,tx,tuple(certs),checked_context,production,full_D)


def fit_svm_primitive(X, y, weights, lambda_, kernel, gamma_factor, fit_context, budget,
                      *, classes, max_iterations=100000, _production=False, _full_grid_dimension=None):
    np=numpy(); n,d=training(X,y,weights,budget,classes)
    ctx=context(fit_context); lambda_=finite_number(lambda_,'lambda',True)
    if kernel not in ('linear','rbf'):
        raise EstimatorError('invalid_kernel')
    if kernel=='linear' and gamma_factor is not None:
        raise EstimatorError('linear_gamma_not_applicable')
    gamma=None if kernel=='linear' else training_gamma(X,weights,gamma_factor,budget)
    K=kernel_matrix(X,X,kernel,gamma,budget)
    signed=empty((n,classes),budget,'ovr_signed_duals')
    intercept=empty((classes,),budget,'ovr_intercepts')
    alpha=empty((n,),budget,'balanced_binary_weights')
    certs=[]
    for k in range(classes):
        positive=math.fsum(float(weights[j]) for j in range(n) if y[j]==k)
        negative=math.fsum(float(weights[j]) for j in range(n) if y[j]!=k)
        budget.charge(n*8,'binary_label_vector')
        yy=tuple(1 if label==k else -1 for label in y)
        for j in range(n):
            alpha[j]=float(weights[j])/(2.0*(positive if y[j]==k else negative))
        result,b,cert=solve_binary_primitive(K,yy,alpha,lambda_,budget,max_iterations=max_iterations)
        np.divide(result.array(),lambda_,out=signed[:,k])
        intercept[k]=b;certs.append(cert);budget.tick('binary_heads_completed')
    if kernel=='linear':
        coefficients=empty((d,classes),budget,'linear_coefficients')
        np.dot(X.T,signed,out=coefficients)
        tx=None
    else:
        coefficients=signed;tx=FrozenArray.freeze(X,budget,'rbf_training_X')
    return SVMState(kernel,classes,d,lambda_,gamma,FrozenArray.freeze(coefficients,budget,'svm_coefficients'),
                    FrozenArray.freeze(intercept,budget,'svm_intercepts'),tx,tuple(certs),ctx,_production,_full_grid_dimension)


def fit_svm(X,y,weights,lambda_,family,gamma_factor,fit_context,budget,*,full_grid_dimension=None):
    """Canonical production family; parent still owns input/environment authority."""
    if family not in ('linear_ovr_svm','rbf_ovr_svm'):
        raise EstimatorError('unknown_canonical_svm_family')
    kernel={'linear_ovr_svm':'linear','rbf_ovr_svm':'rbf'}[family]
    matrix(X,budget)
    production_features(X,fit_context,family,full_grid_dimension)
    allowed=[1e-5,1e-3,.1,10] if kernel=='linear' else [1e-4,.01,1]
    if lambda_ not in allowed or (kernel=='rbf' and gamma_factor not in [.1,1,10]):
        raise EstimatorError('svm_outside_frozen_grid')
    return fit_svm_primitive(X,y,weights,lambda_,kernel,gamma_factor,fit_context,budget,
                             classes=25,max_iterations=100000,_production=True,
                             _full_grid_dimension=full_grid_dimension)


def predict_svm(state,X,budget):
    if type(state) is not SVMState:
        raise EstimatorError('invalid_svm_state_type')
    np=numpy();matrix(X,budget,columns=state.features)
    scores=empty((X.shape[0],state.classes),budget,'svm_predictions')
    if state.kernel=='linear':
        np.dot(X,state.coefficients.array(),out=scores)
    else:
        K=kernel_matrix(X,state.training_X.array(),state.kernel,state.gamma,budget)
        np.dot(K,state.coefficients.array(),out=scores)
    scores+=state.intercepts.array()
    if any(not math.isfinite(float(x)) for x in scores.flat):
        raise EstimatorError('nonfinite_svm_predictions')
    budget.tick('svm_prediction_scores',scores.size)
    return FrozenArray.freeze(scores,budget,'svm_predictions')
