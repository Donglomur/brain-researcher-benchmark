"""Next image/omission onset across the image tables returned by nwb_source.

The table-local ID is deliberately paired with the table name: NWB table IDs
are not assumed to be unique across tables. No label or response is inspected.
"""
from math import isfinite
from numbers import Integral, Real


def next_onsets(tables):
    """Return {(table_name, presentation_id): next_onset_or_None}.

    Include every row before outcome, omission, context or current-duration
    filtering. Retain the predecessor's strictly increasing per-table clock
    requirement, and reject coincident rows across tables as ambiguous source
    presentations rather than silently choosing one representation.
    """
    events = []
    groups = set()
    for table in tables:
        group = table["group"]
        if not isinstance(group, str) or not group or group in groups:
            raise ValueError("Unique nonempty source presentation table names")
        groups.add(group)
        ids, starts = table["ids"], table["starts"]
        if len(ids) != len(starts):
            raise ValueError("Presentation IDs and clocks must align")
        seen = set()
        previous = None
        for sid, onset in zip(ids, starts):
            if isinstance(sid, bool) or not isinstance(sid, Integral):
                raise ValueError("Integral source presentation ID")
            sid = int(sid)
            if sid in seen:
                raise ValueError("Unique presentation IDs within each table")
            seen.add(sid)
            if isinstance(onset, bool) or not isinstance(onset, Real) or not isfinite(onset):
                raise ValueError("Finite native presentation clock")
            onset = float(onset)
            if previous is not None and onset <= previous:
                raise ValueError("Strictly increasing clock within each table")
            previous = onset
            events.append((onset, group, sid))
    if not events:
        raise ValueError("At least one source image/omission presentation")
    events.sort()
    following = {}
    for index, (onset, group, sid) in enumerate(events):
        next_onset = events[index + 1][0] if index + 1 < len(events) else None
        if next_onset == onset:
            raise ValueError("Coincident presentations across source tables")
        following[(group, sid)] = next_onset
    return following


def overlaps_post(onset, next_onset, post_end):
    """Use the unchanged half-open POST endpoint; exact boundary is allowed."""
    return next_onset is not None and next_onset < onset + post_end
