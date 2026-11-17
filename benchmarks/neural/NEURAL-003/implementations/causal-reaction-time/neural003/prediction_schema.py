"""Public-output structure is admitted before a private target callback is touched."""
import math

ARMS = ("eeg", "contrast_instruction")


class InvalidPredictionRT(ValueError):
    """Candidate RT admission failed before any private target access."""


def _admit_rt_seconds(value):
    """Return a finite binary64 RT without silently changing an integer input.

    Representability, rather than an arbitrary magnitude cap, is required:
    exactly representable integers above 2**53 remain valid. Built-in floats
    already express binary64 values; arithmetic remains binary64 thereafter.
    """
    if type(value) not in (int, float):
        raise ValueError("RT must be a built-in int or float")
    try:
        converted = float(value)
    except OverflowError:
        raise ValueError("RT must be representable as finite binary64") from None
    if not math.isfinite(converted) or converted <= 0.1:
        raise ValueError("finite total RT above landmark; no arbitrary3s cap")
    if type(value) is int and converted != value:
        raise ValueError("integer RT must be exactly representable as binary64")
    return converted


def admit_predictions(outputs, expected):
    """expected maps each (person, arm) to exact opaque IDs for that isolated view.

    The operator must derive expected from a real private source/view producer.
    Neither these mappings nor an output's claimed arm authenticate isolation.
    """
    keys = {(p, a) for p in range(26) for a in ARMS}
    if type(outputs) is not dict or type(expected) is not dict:
        raise ValueError("exact output and expected mappings")
    if any(type(k) is not tuple or len(k) != 2 or type(k[0]) is not int
               or type(k[1]) is not str for mapping in (outputs, expected) for k in mapping):
        raise ValueError("exact typed person/arm keys")
    if set(outputs) != keys or set(expected) != keys:
        raise ValueError("all26 people x both arms required")
    clean = {}
    for p in range(26):
        if tuple(expected[(p, ARMS[0])]) != tuple(expected[(p, ARMS[1])]):
            raise ValueError("matched query roster across arms")
    for key in sorted(keys):
        ids = tuple(expected[key])
        if (not ids or len(ids) > 20000 or len(set(ids)) != len(ids)
                or any(type(i) is not str or len(i) != 32
                       or any(c not in "0123456789abcdef" for c in i) for i in ids)):
            raise ValueError("unique opaque query IDs")
        rows = outputs[key]
        if type(rows) is not list or len(rows) != len(ids):
            raise ValueError("complete prediction rows")
        values = []
        for ident, row in zip(ids, rows):
            if type(row) is not dict or set(row) != {"trial_id", "rt_seconds"}:
                raise ValueError("exact prediction fields")
            if row["trial_id"] != ident:
                raise ValueError("prediction identity/order")
            try:
                values.append(_admit_rt_seconds(row["rt_seconds"]))
            except ValueError as error:
                raise InvalidPredictionRT(f"invalid candidate prediction RT: {error}") from error
        clean[key] = tuple(values)
    return clean
