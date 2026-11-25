"""Source-defined DFINE SAE control inputs; no masks, fitting, or inference.

The motor missing-observation Methods specifies zero replacement and the mean
of the last and next available observations. Neighbor averaging is noncausal.
Leading/trailing gaps have no two-sided source rule and are refused, not filled
with an invented boundary convention. This module is a mathematical component,
not authentication of the historical experiment or native numerical parity.
"""

import math


class ImputationError(ValueError):
    """The masked observation interface is invalid."""


class UnresolvedBoundaryError(ImputationError):
    """The paper does not supply the required one-sided boundary rule."""


def impute_sae_observations(masked_rows, mask_bits, method, feature_count):
    """Build one SAE control's inputs from a fixed, already-masked panel.

    ``mask_bits`` uses the existing scorer convention: 1 observed, 0 missing.
    Missing rows must be None, so original dropped neural values never enter
    this function. Observed rows are finite numeric lists. No mask is generated
    or modified. The caller must authenticate its source mask and time ordering.

    Methods match the existing prediction-record IDs: ``sae_zero_smooth`` and
    ``sae_average_smooth``. Return a fresh N-by-feature_count list of floats.
    Float64 Python arithmetic is not a claim about the historical model dtype.
    """
    if method not in ("sae_zero_smooth", "sae_average_smooth"):
        raise ImputationError("unknown SAE control method")
    if type(feature_count) is not int or feature_count < 1:
        raise ImputationError("feature_count must be a positive integer")
    if type(masked_rows) is not list or not masked_rows:
        raise ImputationError("nonempty masked row list required")
    if (type(mask_bits) is not str or len(mask_bits) != len(masked_rows)
            or any(bit not in "01" for bit in mask_bits)):
        raise ImputationError("one binary mask bit per row required")

    result = []
    for bit, row in zip(mask_bits, masked_rows):
        if bit == "0":
            if row is not None:
                raise ImputationError("dropped neural values must be absent")
            result.append(None)
            continue
        if type(row) is not list or len(row) != feature_count:
            raise ImputationError("observed row has wrong feature support")
        values = []
        for value in row:
            if type(value) not in (int, float):
                raise ImputationError("observed values must be numeric, not bool")
            try:
                converted = float(value)
            except (OverflowError, ValueError) as exc:
                raise ImputationError("observed value is not finite") from exc
            if not math.isfinite(converted):
                raise ImputationError("observed value is not finite")
            values.append(converted)
        result.append(values)

    if method == "sae_zero_smooth":
        return [row if row is not None else [0.0] * feature_count
                for row in result]

    if result[0] is None or result[-1] is None:
        raise UnresolvedBoundaryError(
            "neighbor averaging needs source-defined leading/trailing gap rules")

    left = 0
    while left < len(result) - 1:
        right = left + 1
        while result[right] is None:
            right += 1
        if right > left + 1:
            # Every point in a gap uses the same adjacent available endpoints;
            # this is their arithmetic mean, not temporal interpolation and
            # not recursive filling from previously imputed observations.
            # Add before halving when possible: halving each endpoint first
            # can erase a representable subnormal mean. Only same-sign large
            # endpoints need the overflow-safe half-sum fallback.
            mean = []
            for a, b in zip(result[left], result[right]):
                total = a + b
                mean.append(0.5 * total if math.isfinite(total)
                            else 0.5 * a + 0.5 * b)
            for index in range(left + 1, right):
                result[index] = mean.copy()
        left = right
    return result
