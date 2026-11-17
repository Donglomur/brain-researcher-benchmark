class Refusal(ValueError):
    """Admission refusal, distinct from a scientific outcome."""


def require(condition, message):
    if not condition:
        raise Refusal(message)
