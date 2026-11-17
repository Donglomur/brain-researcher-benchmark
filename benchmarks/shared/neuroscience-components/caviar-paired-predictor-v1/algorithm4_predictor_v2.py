"""Prospective, stdlib implementation of CAVIaR Supplement Algorithm 4.

No fitting, official-beta conversion, response construction or scoring occurs here.
The caller supplies an already fixed, factorized posterior and explicit units.
The paired estimators use the SAME accepted phi vectors. Joint positive-orthant
Gaussian rejection is exact conditional sampling if it completes; exhaustion is
an error, never a partial estimate. See SCIENTIFIC_CONTRACT.json for provenance.
"""
from dataclasses import dataclass
import math
import random

class InvalidInput(ValueError):
    pass

class NumericalFailure(ArithmeticError):
    pass

class SamplingExhausted(RuntimeError):
    """No successful prediction is returned on this failure."""
    def __init__(self, target_id, draw_index, attempts):
        self.target_id, self.draw_index, self.attempts = target_id, draw_index, attempts
        super().__init__(f"positive-orthant rejection exhausted: target={target_id!r}, "
                         f"draw={draw_index}, attempts={attempts}")

@dataclass(frozen=True)
class WeightPosterior:
    mean: float
    standard_deviation: float

@dataclass(frozen=True)
class PowerCurvePosterior:
    mean: tuple[float, float]
    covariance: tuple[tuple[float, float], tuple[float, float]]

@dataclass(frozen=True)
class TargetPosterior:
    target_id: str
    weight: WeightPosterior
    power_curve: PowerCurvePosterior

@dataclass(frozen=True)
class PosteriorMetadata:
    posterior_id: str
    fit_provenance: str
    held_hologram_id: str
    response_unit: str
    stimulation_power_unit: str

@dataclass(frozen=True)
class FixedPosterior:
    metadata: PosteriorMetadata
    targets: tuple[TargetPosterior, ...]

@dataclass(frozen=True)
class PowerInput:
    power_id: str
    # Explicit ID joins; order of these pairs need not match posterior order.
    by_target: tuple[tuple[str, float], ...]

@dataclass(frozen=True)
class HeldHologram:
    hologram_id: str
    powers: tuple[PowerInput, ...]

@dataclass(frozen=True)
class ProspectiveSettings:
    draws: int
    seed: int
    max_phi_attempts_per_target_draw: int

@dataclass(frozen=True)
class PairedPrediction:
    posterior_metadata: PosteriorMetadata
    settings: ProspectiveSettings
    power_ids: tuple[str, ...]
    literal_mean: tuple[float, ...]
    rao_blackwell_mean: tuple[float, ...]
    removed_conditional_covariance_of_mean: tuple[tuple[float, ...], ...]
    phi_attempts: int
    accepted_target_draws: int
    convention: str = "prospective_joint_positive_orthant_q_explicit_weight_sd_v1"

def _real(value, label):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidInput(f"{label}: expected a real int/float, excluding bool")
    try:
        value = float(value)
    except (OverflowError, ValueError) as exc:
        raise InvalidInput(f"{label}: cannot represent as a finite float") from exc
    if not math.isfinite(value):
        raise InvalidInput(f"{label}: nonfinite")
    return value

def _id(value, label):
    if not isinstance(value, str) or not value.strip():
        raise InvalidInput(f"{label}: expected a nonempty string")
    return value

def _tuple(value, length, label):
    if not isinstance(value, tuple) or (length is not None and len(value) != length):
        raise InvalidInput(f"{label}: expected tuple of length {length}")
    return value

def _finite(value, label):
    if not math.isfinite(value):
        raise NumericalFailure(f"{label}: nonfinite intermediate")
    return value

def _sum(values, label):
    try:
        return _finite(math.fsum(values), label)
    except (OverflowError, ValueError) as exc:
        raise NumericalFailure(f"{label}: nonfinite sum") from exc

def _cholesky(curve):
    if not isinstance(curve, PowerCurvePosterior):
        raise InvalidInput("power_curve: expected PowerCurvePosterior")
    mean = tuple(_real(x, "phi mean") for x in _tuple(curve.mean, 2, "phi mean"))
    cov = _tuple(curve.covariance, 2, "phi covariance")
    a, b = (_real(x, "covariance") for x in _tuple(cov[0], 2, "covariance row"))
    c, d = (_real(x, "covariance") for x in _tuple(cov[1], 2, "covariance row"))
    if b != c or a <= 0 or d <= 0:
        raise InvalidInput("covariance must be exactly symmetric with positive diagonal")
    # Scaling avoids squaring a large covariance entry. No jitter or diagonal repair.
    scale = max(a, d)
    aa, bb, dd = a / scale, b / scale, d / scale
    if aa <= 0 or dd <= 0:
        raise InvalidInput("covariance dynamic range is unsupported")
    root_a = math.sqrt(aa)
    off = bb / root_a
    residual = dd - off * off
    if not math.isfinite(residual) or residual <= 0:
        raise InvalidInput("covariance must be numerically strictly positive definite")
    root_scale = math.sqrt(scale)
    chol = (root_a * root_scale, off * root_scale, math.sqrt(residual) * root_scale)
    if not all(math.isfinite(x) for x in chol):
        raise InvalidInput("nonfinite Cholesky factor")
    return mean, chol

def _validate(posterior, hologram, settings):
    if not isinstance(posterior, FixedPosterior) or not isinstance(posterior.metadata, PosteriorMetadata):
        raise InvalidInput("expected FixedPosterior with PosteriorMetadata")
    meta = posterior.metadata
    for name in ("posterior_id", "fit_provenance", "held_hologram_id",
                 "response_unit", "stimulation_power_unit"):
        _id(getattr(meta, name), name)
    if not isinstance(hologram, HeldHologram):
        raise InvalidInput("expected HeldHologram")
    if _id(hologram.hologram_id, "hologram_id") != meta.held_hologram_id:
        raise InvalidInput("held hologram does not match declared fitting exclusion")
    if not isinstance(settings, ProspectiveSettings):
        raise InvalidInput("expected ProspectiveSettings")
    for name in ("draws", "seed", "max_phi_attempts_per_target_draw"):
        value = getattr(settings, name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvalidInput(f"{name}: expected int excluding bool")
    # J participates in floating-point averaging; refuse unsupported huge integers
    # before constructing RNG state or beginning any sampling.
    _real(settings.draws, "draws")
    if settings.draws <= 0 or settings.max_phi_attempts_per_target_draw <= 0:
        raise InvalidInput("draws and rejection cap must be positive")
    targets = _tuple(posterior.targets, None, "targets")
    powers = _tuple(hologram.powers, None, "powers")
    if not targets or not powers:
        raise InvalidInput("targets and powers must be nonempty")
    ids, prepared = [], []
    for target in targets:
        if not isinstance(target, TargetPosterior) or not isinstance(target.weight, WeightPosterior):
            raise InvalidInput("target must declare a typed WeightPosterior")
        tid = _id(target.target_id, "target_id")
        if tid in ids:
            raise InvalidInput("duplicate target_id")
        ids.append(tid)
        mu = _real(target.weight.mean, "weight mean")
        sd = _real(target.weight.standard_deviation, "weight standard deviation")
        if sd < 0:
            raise InvalidInput("weight standard deviation must be nonnegative")
        phi_mean, chol = _cholesky(target.power_curve)
        prepared.append((tid, mu, sd, phi_mean, chol))
    power_ids, power_rows = [], []
    for power in powers:
        if not isinstance(power, PowerInput):
            raise InvalidInput("expected PowerInput")
        pid = _id(power.power_id, "power_id")
        if pid in power_ids:
            raise InvalidInput("duplicate power_id")
        power_ids.append(pid)
        by_id = {}
        for pair in _tuple(power.by_target, None, "power by_target"):
            tid, value = _tuple(pair, 2, "target/power pair")
            _id(tid, "paired target_id")
            if tid in by_id:
                raise InvalidInput("duplicate paired target_id")
            value = _real(value, "stimulation power")
            if value < 0:
                raise InvalidInput("stimulation power must be nonnegative")
            by_id[tid] = value
        if set(by_id) != set(ids):
            raise InvalidInput("every power must join exactly every posterior target_id")
        power_rows.append(tuple(by_id[tid] for tid in ids))
    return prepared, tuple(power_ids), tuple(power_rows)

def stable_logistic(logit):
    """Stable for all finite logits; extreme tails may round to exactly 0 or 1."""
    logit = _real(logit, "logit")
    if logit >= 0:
        return 1.0 / (1.0 + math.exp(-logit))
    e = math.exp(logit)
    return e / (1.0 + e)

def _sample_phi(rng, mean, chol, target_id, draw_index, cap):
    for attempt in range(1, cap + 1):
        z0, z1 = rng.normalvariate(0.0, 1.0), rng.normalvariate(0.0, 1.0)
        p0 = _finite(mean[0] + chol[0] * z0, "phi0 draw")
        p1 = _sum((mean[1], chol[1] * z0, chol[2] * z1), "phi1 draw")
        if p0 > 0 and p1 > 0:
            return (p0, p1), attempt
    raise SamplingExhausted(target_id, draw_index, cap)

def _conditional_covariance(mu, sd, probabilities):
    size = len(probabilities)
    if mu == 0:
        return tuple((0.0,) * size for _ in range(size))
    variance = _finite(sd * sd, "weight variance")
    mean_square = _finite(mu * mu, "squared weight mean")
    rows = []
    for a, pa in enumerate(probabilities):
        row = []
        for b, pb in enumerate(probabilities):
            if a == b:
                value = _sum((variance * pa, mean_square * pa * (1 - pa)), "conditional variance")
            else:
                value = _finite(variance * pa * pb, "conditional covariance")
            row.append(value)
        rows.append(tuple(row))
    return tuple(rows)

def predict_paired(posterior, hologram, settings):
    """Return complete literal and Rao-Blackwell J-draw means or raise.

    Independence: target posterior factors, W versus phi, and Bernoulli draws
    across targets/powers conditional on phi. Each target's phi and W are shared
    across powers within draw j. Exact mu==0 gives W=0 regardless of declared SD.

    Order: j, posterior target, rejected/accepted phi normal pair, W normal when
    mu!=0 and SD>0, then one independent uniform per power (including mu==0).
    No I>0 mask is applied; at zero power p=sigmoid(-phi1), generally nonzero.
    Python Random(seed) is prospective; cross-Python-bitstream parity is not promised.
    The covariance output conditions on the actual accepted phi vectors. It omits
    phi uncertainty and is NOT an estimate of total predictive/posterior variance.
    """
    targets, power_ids, powers = _validate(posterior, hologram, settings)
    rng = random.Random(settings.seed)
    k = len(powers)
    literal_mean, rb_mean = [0.0] * k, [0.0] * k
    covariance_mean = [[0.0] * k for _ in range(k)]
    attempts = 0
    inv_j = 1.0 / settings.draws
    for draw in range(settings.draws):
        literal_parts, rb_parts = [[] for _ in range(k)], [[] for _ in range(k)]
        covariance_parts = [[[] for _ in range(k)] for _ in range(k)]
        for n, (tid, mu, sd, phi_mean, chol) in enumerate(targets):
            phi, used = _sample_phi(rng, phi_mean, chol, tid, draw,
                                    settings.max_phi_attempts_per_target_draw)
            attempts += used
            probabilities = tuple(stable_logistic(_finite(phi[0] * row[n] - phi[1], "logit"))
                                  for row in powers)
            if mu == 0:
                weight = 0.0
            elif sd == 0:
                weight = mu
            else:
                weight = _finite(mu + sd * rng.normalvariate(0.0, 1.0), "weight draw")
            for p, probability in enumerate(probabilities):
                spike = rng.random() < probability
                literal_parts[p].append(weight if spike else 0.0)
                rb_parts[p].append(_finite(mu * probability, "conditional mean") if mu != 0 else 0.0)
            conditional = _conditional_covariance(mu, sd, probabilities)
            for a in range(k):
                for b in range(k):
                    covariance_parts[a][b].append(conditional[a][b])
        # Online means avoid overflowing an unnormalized J-fold running sum.
        old_fraction = draw / (draw + 1)
        for p in range(k):
            literal = _sum(literal_parts[p], "literal target sum")
            rb = _sum(rb_parts[p], "conditional target sum")
            literal_mean[p] = _sum((literal_mean[p] * old_fraction, literal / (draw + 1)), "literal mean")
            rb_mean[p] = _sum((rb_mean[p] * old_fraction, rb / (draw + 1)), "Rao-Blackwell mean")
        for a in range(k):
            for b in range(k):
                contribution = _sum(covariance_parts[a][b], "target covariance sum") * inv_j * inv_j
                covariance_mean[a][b] = _sum((covariance_mean[a][b], contribution), "mean covariance")
    return PairedPrediction(posterior.metadata, settings, power_ids, tuple(literal_mean),
                            tuple(rb_mean), tuple(tuple(row) for row in covariance_mean),
                            attempts, settings.draws * len(targets))
