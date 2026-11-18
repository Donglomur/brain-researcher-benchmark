"""Frozen non-learning engineering rule; no observations, labels or state input."""
SAMPLES = 819


def predict(query_count):
    if type(query_count) is not int or query_count not in (6, 72):
        raise ValueError("the original six-query or72full-row support is required")
    # Integers are intentional: JSON0, not0.0. Shared immutable zero values and
    # a shared read-only-in-use row avoid extra in-memory copies. The unchanged
    # collector still serializes every required coordinate's complete vectors.
    row = [0] * SAMPLES
    return [row] * query_count
