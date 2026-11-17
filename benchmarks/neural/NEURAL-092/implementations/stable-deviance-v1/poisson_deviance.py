"""Stable scalar Poisson deviance for NEURAL-092's int64 count endpoint.

This numerical component issues no host authority and opens no targets. Both
validation and frozen QUERY consumers must use the same version when integrated.
"""
import math
import sys

MAX_COUNT = 2**63 - 1
MAX_SERIES_TERMS = 32


def deviance_term(y, mu, calls=None):
    """Return 2 * (y log(y / mu) - y + mu), without clipping.

    Counts follow the existing nonnegative signed-int64 plane. Means follow the
    existing positive finite float64 prediction plane. Optional call accounting
    uses the original Calls.enter protocol, including attempted evaluations.
    """
    if calls is not None:
        calls.enter('deviance_row')
    if (type(y) is not int or not 0 <= y <= MAX_COUNT
            or type(mu) is not float or not math.isfinite(mu) or mu <= 0):
        raise ValueError('nonnegative int64 count and positive finite float64 mean required')
    if y == 0:
        value = 2 * mu
    elif y == mu:
        return 0.0
    elif abs(y - mu) < 0.1 * (y + mu):
        # y may be an int64 above 2**53. Avoid rounding y before subtracting:
        # e.g. y=2**63-1 and mu=2**63 differ by one, not zero.
        numerator, denominator = mu.as_integer_ratio()
        delta = (y * denominator - numerator) / denominator
        v = delta / (y + mu)
        square = v * v
        terms = [delta * v]
        term = 2 * y * v
        # log(y/mu) = 2 atanh(v). Its linear term combined with -y+mu
        # equals delta*v; remaining terms have powers v**3, v**5, ... .
        # Here |v| < 0.1, so this series converges without cancellation of
        # the leading quadratic contribution. The hard bound is independent
        # of requested precision or any participant input size.
        total = terms[0]
        for k in range(1, MAX_SERIES_TERMS + 1):
            if calls is not None:
                calls.enter('deviance_series_term')
            term *= square
            terms.append(term / (2 * k + 1))
            updated = math.fsum(terms)
            if updated == total:
                break
            total = updated
        else:
            raise ArithmeticError('bounded deviance series did not converge')
        value = 2 * updated
    else:
        # mu/y cannot overflow because y >= 1. Subnormal ratios lose relative
        # precision even before reaching zero; use separate logarithms for
        # that entire range, not only when division underflows completely.
        ratio = mu / y
        if calls is not None:
            calls.enter('log_scalar')
        if ratio >= sys.float_info.min:
            log_ratio = math.log(ratio)
        else:
            if calls is not None:
                calls.enter('log_scalar')
            log_ratio = math.log(mu) - math.log(y)
        value = 2 * math.fsum((mu, -float(y), -y * log_ratio))
    if not math.isfinite(value) or value < 0:
        raise ArithmeticError('deviance outside finite nonnegative float64 range')
    return value
