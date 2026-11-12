"""Certified F12 population PR for the centered Gaussian feature kernel.

This is scientific source, authored but not numerically executed in BUILD ONLY.
Import performs no integration, generation, fitting, or truth calculation.
All integration arithmetic is exact Fraction arithmetic. The one float output is
checked against the rational enclosure by its exact as_integer_ratio value.
See F12_DERIVATION.md for the complete mathematical and termination argument.
"""
from fractions import Fraction
from math import factorial, isfinite

DIMENSIONS = (1, 2, 3, 5, 8)
RADII = ((1, 20), (1, 10), (1, 5), (7, 20), (1, 2), (3, 4))
EVEN_DEGREE = 24
LAST_DEGREE = 25
MAX_POLYNOMIAL_TERMS = 3_000_000
METHOD = 'F12_centered_gaussian_ball_exact_moment_Taylor24_25_v1'


class TruthCertificateError(ValueError):
    """No numerical truth may be issued after a failed source/certificate check."""


def _require(condition, message):
    if not condition:
        raise TruthCertificateError(message)


def _radius(value):
    # Reject binary floats: the sealed grid specifies exact decimal radii.
    if type(value) is Fraction:
        radius = value
    elif type(value) in (tuple, list) and len(value) == 2:
        numerator, denominator = value
        _require(type(numerator) is int and type(denominator) is int and
                 (numerator, denominator) in RADII,
                 'radius integer pair must be one canonical predeclared cell')
        radius = Fraction(numerator, denominator)
    else:
        raise TruthCertificateError('radius must be Fraction or integer pair')
    _require((radius.numerator, radius.denominator) in RADII,
             'radius is outside the six predeclared F12 cells')
    return radius


def _fraction_record(value):
    return {'numerator': str(value.numerator),
            'denominator': str(value.denominator)}


def _interval_record(bounds):
    return {'lower': _fraction_record(bounds[0]),
            'upper': _fraction_record(bounds[1])}


def _count_term(counter):
    counter[0] += 1
    _require(counter[0] <= MAX_POLYNOMIAL_TERMS,
             'predeclared exact-moment term budget exceeded')


def _radial_and_sphere(dimension, radius):
    """M_s = E|X|^(2s); S_j = E<U,e>^(2j), U uniform on sphere."""
    radial = [Fraction(dimension, dimension + 2 * s) * radius ** (2 * s)
              for s in range(LAST_DEGREE + 1)]
    sphere = [Fraction(1)]
    for j in range(1, LAST_DEGREE // 2 + 1):
        sphere.append(sphere[-1] * Fraction(2 * j - 1,
                                           dimension + 2 * j - 2))
    return radial, sphere


def _pair_distance_moment(n, radial, sphere, facts, counter):
    """E(||X-Y||^2)^n, exactly integrated over two independent balls."""
    total = Fraction(0)
    for j in range(n // 2 + 1):
        # Odd powers of X.Y integrate to zero by the Y -> -Y symmetry.
        remaining = n - 2 * j
        for a in range(remaining + 1):
            b = remaining - a
            _count_term(counter)
            coefficient = facts[n] // (facts[a] * facts[b] * facts[2 * j])
            total += (coefficient * (2 ** (2 * j)) *
                      radial[a + j] * radial[b + j] * sphere[j])
    return total


def _shared_distance_moment(n, radial, sphere, facts, counter):
    """E(||X-Y||^2+||X-Z||^2)^n for independent uniform-ball X,Y,Z."""
    total = Fraction(0)
    for i in range(n // 2 + 1):
        for j in range((n - 2 * i) // 2 + 1):
            remaining = n - 2 * i - 2 * j
            for a in range(remaining + 1):
                for b in range(remaining - a + 1):
                    c = remaining - a - b
                    _count_term(counter)
                    coefficient = facts[n] // (
                        facts[a] * facts[b] * facts[c] *
                        facts[2 * i] * facts[2 * j])
                    total += (coefficient * (2 ** (a + 2 * i + 2 * j)) *
                              radial[a + i + j] * radial[b + i] *
                              radial[c + j] * sphere[i] * sphere[j])
    return total


def _exponential_interval(moments, exponent_scale, facts):
    """Integrate P_25(q) <= exp(-q) <= P_24(q), q >= 0."""
    partial = Fraction(0)
    upper = None
    for n in range(LAST_DEGREE + 1):
        partial += ((-1) ** n * exponent_scale ** n *
                    moments[n] / facts[n])
        if n == EVEN_DEGREE:
            upper = partial
    # Every integrand is in [0,1]; intersecting exact intervals preserves truth.
    lower = max(Fraction(0), partial)
    upper = min(Fraction(1), upper)
    _require(lower <= upper, 'exact exponential enclosure is inconsistent')
    return lower, upper


def truth(dimension, radius_fraction):
    """Return {'gamma': float, 'certificate': JSON-compatible exact bounds}.

    The caller must be the protected generator/preparation issuer. This function
    is a deterministic scientific producer, not a public participant API. Its
    inputs are only the sealed latent dimension and exact grid radius. It does
    not consume samples, seeds, generated observations, or participant values.
    A typed TruthCertificateError requires a failed preparation; never replace
    failure by dimension, an estimated PR, Monte Carlo, or a different radius.
    """
    _require(type(dimension) is int and dimension in DIMENSIONS,
             'dimension is outside the predeclared F12 support')
    radius = _radius(radius_fraction)
    facts = [factorial(n) for n in range(LAST_DEGREE + 1)]
    radial, sphere = _radial_and_sphere(dimension, radius)
    counter = [0]
    pairs = [_pair_distance_moment(n, radial, sphere, facts, counter)
             for n in range(LAST_DEGREE + 1)]
    shared = [_shared_distance_moment(n, radial, sphere, facts, counter)
              for n in range(LAST_DEGREE + 1)]

    pair_half = _exponential_interval(pairs, Fraction(1, 2), facts)
    pair_full = _exponential_interval(pairs, Fraction(1), facts)
    shared_half = _exponential_interval(shared, Fraction(1, 2), facts)
    mean_kernel = tuple(x / 2 for x in pair_half)
    mean_squared_kernel = tuple(x / 4 for x in pair_full)
    mean_squared_conditional = tuple(x / 4 for x in shared_half)

    # Positive linear Gaussian-kernel features supply independent lower bounds.
    # e^(-radius^2) >= (1-radius^2/2)^2, proved without rounded exponentials.
    exp_lower = (1 - radius * radius / 2) ** 2
    trace_lower = (Fraction(dimension, 2 * (dimension + 2)) *
                   radius * radius * exp_lower)
    square_trace_lower = (Fraction(dimension, 4 * (dimension + 2) ** 2) *
                          radius ** 4 * exp_lower ** 2)
    trace = (max(trace_lower, Fraction(1, 2) - mean_kernel[1]),
             Fraction(1, 2) - mean_kernel[0])
    trace_squared_operator = (
        max(square_trace_lower,
            mean_squared_kernel[0] - 2 * mean_squared_conditional[1] +
            mean_kernel[0] ** 2),
        mean_squared_kernel[1] - 2 * mean_squared_conditional[0] +
        mean_kernel[1] ** 2)
    _require(0 < trace[0] <= trace[1], 'trace enclosure is inconsistent')
    _require(0 < trace_squared_operator[0] <= trace_squared_operator[1],
             'positive denominator enclosure is inconsistent')

    # C is positive trace-class, so PR >= 1. The feature bounds give PR < 4d.
    lower = max(Fraction(1), trace[0] ** 2 / trace_squared_operator[1])
    upper = min(Fraction(4 * dimension),
                trace[1] ** 2 / trace_squared_operator[0])
    _require(0 < lower <= upper, 'participation-ratio enclosure is inconsistent')
    midpoint = (lower + upper) / 2
    try:
        gamma = float(midpoint)
        _require(isfinite(gamma) and gamma > 0, 'nonfinite truth conversion')
        emitted = Fraction(*gamma.as_integer_ratio())
    except (OverflowError, ValueError) as error:
        raise TruthCertificateError('truth conversion failed') from error
    # For all t in [lower,upper], |log(gamma/t)| is at most this rational.
    # log(u) <= u-1; no rounded logarithm enters the certificate.
    error_bound = max(Fraction(0), emitted / lower - 1,
                      upper / emitted - 1)
    _require(error_bound <= Fraction(1, 100_000),
             'absolute logtruth error exceeds the predeclared 1e-5 ceiling')
    qmax = 4 * radius * radius
    remainder_bound = qmax ** LAST_DEGREE / facts[LAST_DEGREE]
    return {'gamma': gamma, 'certificate': {
        'schema': 'finite_F12_rational_population_truth_v1',
        'method': METHOD,
        'dimension': dimension,
        'radius': _fraction_record(radius),
        'kernel': '0.5*exp(-squared_euclidean_distance/2)',
        'distribution': 'independent uniform Euclidean balls centered at zero',
        'target': 'finite_radius_centered_kernel_population_participation_ratio',
        'intrinsic_dimension_is_not_truth': True,
        'mean_kernel': _interval_record(mean_kernel),
        'mean_squared_kernel': _interval_record(mean_squared_kernel),
        'mean_squared_conditional_kernel': _interval_record(mean_squared_conditional),
        'trace_covariance': _interval_record(trace),
        'trace_covariance_squared': _interval_record(trace_squared_operator),
        'analytic_trace_lower': _fraction_record(trace_lower),
        'analytic_denominator_lower': _fraction_record(square_trace_lower),
        'gamma_interval': _interval_record((lower, upper)),
        'emitted_float_exact_fraction': _fraction_record(emitted),
        'absolute_logtruth_error_bound': _fraction_record(error_bound),
        'absolute_logtruth_error_ceiling': _fraction_record(Fraction(1, 100_000)),
        'max_exponential_interval_width': _fraction_record(remainder_bound),
        'Taylor_even_upper_degree': EVEN_DEGREE,
        'Taylor_odd_lower_degree': LAST_DEGREE,
        'polynomial_terms_evaluated': counter[0],
        'polynomial_term_ceiling': MAX_POLYNOMIAL_TERMS,
        'sampling_or_monte_carlo_used': False,
        'scientific_qualification': 'requires independent source and numerical qualification',
    }}
