"""Exact public tutorial convention; indices are not semantic sleep labels."""


def tutorial_crop_bounds(annotations):
    if len(annotations) < 3:
        raise ValueError("at least three hypnogram annotations required")
    start = float(annotations[1]["onset"]) - 1800.0
    stop = float(annotations[-2]["onset"]) + 1800.0
    if stop <= start:
        raise ValueError("invalid annotation-index crop bounds")
    return start, stop
