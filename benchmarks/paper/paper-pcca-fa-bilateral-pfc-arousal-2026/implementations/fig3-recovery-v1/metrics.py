"""Source pCCA-FA endpoint arithmetic, without fitting or native dependencies."""
from __future__ import annotations

import math


class Invalid(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Invalid(message)


def number(value):
    require(type(value) in (int, float), "finite numeric value required")
    require(abs(value) <= 1e100, "numeric magnitude exceeds arithmetic limit")
    require(math.isfinite(value), "finite numeric value required")
    return float(value)


def matrix(value, rows, columns):
    require(type(value) is list and len(value) == rows, "matrix row count")
    require(all(type(row) is list and len(row) == columns for row in value), "matrix column count")
    return [[number(x) for x in row] for row in value]


def spectrum(loadings):
    """Return the normalized covariance spectrum and the source 95% dimension.

    The nonzero spectra of A A.T and A.T A coincide. A bounded Jacobi
    diagonalization of the latter avoids a third-party scientific dependency.
    A selected zero-dimensional component has zero shared dimensionality, as
    in the source. Nonempty all-zero loadings have undefined normalized energy
    and are refused, rather than assigned a fabricated dimension.
    """
    d = len(loadings[0])
    if d == 0:
        return [], 0
    scale = max(abs(x) for row in loadings for x in row)
    require(scale > 0, "nonempty component has zero energy")
    z = [[x / scale for x in row] for row in loadings]
    a = [[math.fsum(row[i] * row[j] for row in z) for j in range(d)] for i in range(d)]
    trace = math.fsum(a[i][i] for i in range(d))
    for _ in range(100):
        off = max((abs(a[i][j]) for i in range(d) for j in range(i + 1, d)), default=0)
        if off <= trace * 2e-15:
            values = sorted((max(0.0, a[i][i]) for i in range(d)), reverse=True)
            total = math.fsum(values)
            values = [v / total for v in values]
            for k in range(d):
                if math.fsum(values[:k + 1]) >= 0.95 - 1e-9:
                    return values, k + 1
            raise Invalid("dimension threshold not reached")
        for p in range(d):
            for q in range(p + 1, d):
                if abs(a[p][q]) <= trace * 2e-16:
                    continue
                tau = (a[q][q] - a[p][p]) / (2 * a[p][q])
                t = math.copysign(1.0, tau) / (abs(tau) + math.hypot(1, tau))
                c = 1 / math.hypot(1, t)
                s = t * c
                app, aqq, apq = a[p][p], a[q][q], a[p][q]
                for k in range(d):
                    if k not in (p, q):
                        ap, aq = a[k][p], a[k][q]
                        a[k][p] = a[p][k] = c * ap - s * aq
                        a[k][q] = a[q][k] = s * ap + c * aq
                a[p][p], a[q][q] = app - t * apq, aqq + t * apq
                a[p][q] = a[q][p] = 0.0
    raise Invalid("spectrum did not converge")


def pccafa_metrics(parameters):
    """Compute the original per-area %sv and d_shared from 30-neuron loadings.

    Candidate dimensions may range from 0 to the full population size; the
    disputed author's CV search range is not imposed on candidate methods.
    W1 and W2 must describe the same shared latent coordinate space.
    """
    require(type(parameters) is dict and set(parameters) == {"W1", "W2", "L1", "L2", "psi1", "psi2"}, "parameter fields")
    loadings = {}
    for name in ("W1", "W2", "L1", "L2"):
        raw = parameters[name]
        require(type(raw) is list and len(raw) == 30 and type(raw[0]) is list, "30 neurons per area required")
        d = len(raw[0])
        require(0 <= d <= 30, "loading dimension exceeds population")
        loadings[name] = matrix(raw, 30, d)
    require(len(loadings["W1"][0]) == len(loadings["W2"][0]), "across-area latent dimensions differ")
    result = {}
    for area in (1, 2):
        noise = parameters[f"psi{area}"]
        require(type(noise) is list and len(noise) == 30, "noise support")
        noise = [number(x) for x in noise]
        require(all(x >= 0 for x in noise), "negative independent variance")
        w, l = loadings[f"W{area}"], loadings[f"L{area}"]
        aw = [math.fsum(x * x for x in row) for row in w]
        al = [math.fsum(x * x for x in row) for row in l]
        total = [x + y + z for x, y, z in zip(aw, al, noise)]
        require(all(t > 0 and math.isfinite(t) for t in total), "invalid total variance")
        for component, diagonal, loading in (("across", aw, w), ("within", al, l)):
            fractions = [100 * x / t for x, t in zip(diagonal, total)]
            _, dimension = spectrum(loading)
            result[f"{component}_{area}"] = {
                "psv_percent": math.fsum(fractions) / 30,
                "dshared": dimension,
            }
    return result
