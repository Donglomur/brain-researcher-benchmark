"""Strict, bounded endpoint validation; this module performs no file I/O.

The retained author readtableRmHyphens source removes all ASCII hyphens
from contacts and joins the two equal halves of an even-piece pair split.
ieeg_getPairXyzs uses case-sensitive contact matching. This gate preserves
those name operations but adds explicit integrity and missingness checks.
It deliberately does not reproduce the author's subsequent mean operation.

Every supplied pair occurrence is validated in order, including repetitions
and reversals. The authenticity and completeness of that supplied list still
require a separate source-census binding. Passing this gate establishes no
coordinate frame, provenance, participant packet readiness, or scientific
qualification. All five participant frame bindings remain unproved.

The source main.m documents sub-1 LA1-LA2 -> Left_Amygdala as a manual
correction after visual CT/T1w inspection. That provenance is recorded here;
this module neither applies that correction nor assigns any anatomical label.
Only a mutable upstream reader wrapper has been authenticated as viewed;
the historical VISTASOFT/backend version and index semantics are unresolved.
No affine, voxel, index, or midpoint function is supplied, including no no-op
transform. Units in millimetres alone would not prove frame equivalence.

Inputs are ordinary built-in lists, dictionaries and strings. Selected
coordinates must be built-in int or float values (never bool); integers are
bounded by MAX_COORDINATE_INTEGER_BITS. Extra row fields and unselected
coordinates are not inspected. No coordinate values are returned.
"""

import math

MAX_ELECTRODES = 4096
MAX_PAIRS = 10000
MAX_NAME_BYTES = 256
MAX_PAIR_BYTES = 513
MAX_COORDINATE_INTEGER_BITS = 1024
_MISSING_NAMES = frozenset(("n/a", "NaN"))


class EndpointValidationError(ValueError):
    """A bounded diagnostic identifying the failed check, never data values."""

    def __init__(self, code, kind, index=None):
        self.code = code
        self.kind = kind
        self.index = index
        location = kind if index is None else kind + "[" + str(index) + "]"
        super().__init__(code + " at " + location)


def _fail(code, kind, index=None):
    raise EndpointValidationError(code, kind, index)


def _bounded_text(value, cap, kind, index):
    if type(value) is not str:
        _fail("text_type", kind, index)
    if not value:
        _fail("empty_name", kind, index)
    # A preliminary character bound prevents encoding an oversized string.
    if len(value) > cap:
        _fail("text_too_large", kind, index)
    try:
        encoded = value.encode("utf-8")
    except UnicodeEncodeError:
        _fail("invalid_utf8", kind, index)
    if len(encoded) > cap:
        _fail("text_too_large", kind, index)
    if value in _MISSING_NAMES:
        _fail("missing_name", kind, index)
    return value


def _contact_name(value, index):
    raw = _bounded_text(value, MAX_NAME_BYTES, "electrode_name", index)
    normalized = raw.replace("-", "")
    _bounded_text(normalized, MAX_NAME_BYTES, "electrode_name", index)
    return normalized


def _pair_names(value, index):
    raw = _bounded_text(value, MAX_PAIR_BYTES, "pair", index)
    pieces = raw.split("-")
    if any(piece == "" for piece in pieces):
        _fail("empty_pair_piece", "pair", index)
    if len(pieces) % 2:
        _fail("odd_pair_piece_count", "pair", index)
    half = len(pieces) // 2
    first = "".join(pieces[:half])
    second = "".join(pieces[half:])
    _bounded_text(first, MAX_NAME_BYTES, "pair_endpoint", index)
    _bounded_text(second, MAX_NAME_BYTES, "pair_endpoint", index)
    if first == second:
        _fail("identical_endpoints", "pair", index)
    return first, second


def _validate_coordinates(row, index):
    for field in ("x", "y", "z"):
        if field not in row:
            _fail("missing_coordinate", "electrode_coordinate", index)
        value = row[field]
        if type(value) is int:
            # Integers are finite without a float conversion; cap magnitude.
            if value.bit_length() > MAX_COORDINATE_INTEGER_BITS:
                _fail("coordinate_integer_too_large", "electrode_coordinate", index)
        elif type(value) is float:
            if not math.isfinite(value):
                _fail("coordinate_not_finite", "electrode_coordinate", index)
        else:
            _fail("coordinate_type", "electrode_coordinate", index)


def validate_endpoints(electrodes: list[dict], stimulation_pairs: list[str]) -> dict:
    """Validate the complete supplied list and return only indices and counts.

    Original electrode-row and pair-occurrence indices are zero-based.
    Global duplicate raw names and normalization collisions are rejected even
    when the affected rows are unselected. Coordinates are checked only for
    selected endpoints; missing or nonfinite unselected coordinates do not
    remove rows or change their indices. Empty lists may report zero support,
    with every provenance/frame/readiness flag still false.
    """
    if type(electrodes) is not list:
        _fail("list_type", "electrodes")
    if type(stimulation_pairs) is not list:
        _fail("list_type", "stimulation_pairs")
    if len(electrodes) > MAX_ELECTRODES:
        _fail("electrode_count_too_large", "electrodes")
    if len(stimulation_pairs) > MAX_PAIRS:
        _fail("pair_count_too_large", "stimulation_pairs")

    raw_names = set()
    normalized_rows = {}
    for row_index, row in enumerate(electrodes):
        if type(row) is not dict:
            _fail("row_type", "electrode", row_index)
        if "name" not in row:
            _fail("missing_name_field", "electrode", row_index)
        raw = row["name"]
        normalized = _contact_name(raw, row_index)
        if raw in raw_names:
            _fail("duplicate_raw_name", "electrode_name", row_index)
        if normalized in normalized_rows:
            _fail("normalization_collision", "electrode_name", row_index)
        raw_names.add(raw)
        normalized_rows[normalized] = row_index

    selected_rows = set()
    validated_pairs = []
    for occurrence, pair in enumerate(stimulation_pairs):
        first, second = _pair_names(pair, occurrence)
        if first not in normalized_rows or second not in normalized_rows:
            _fail("missing_endpoint", "pair", occurrence)
        first_row = normalized_rows[first]
        second_row = normalized_rows[second]
        # Uniqueness and normalized-name checks already imply distinct rows.
        if first_row == second_row:
            _fail("identical_endpoints", "pair", occurrence)
        for row_index in (first_row, second_row):
            if row_index not in selected_rows:
                _validate_coordinates(electrodes[row_index], row_index)
                selected_rows.add(row_index)
        validated_pairs.append({
            "pair_occurrence_index": occurrence,
            "normalized_pair": first + "-" + second,
            "endpoint_row_indices": [first_row, second_row],
        })

    return {
        "endpoint_validation_only": True,
        "coordinate_frame_verified": False,
        "index_transform_applied": False,
        "midpoint_computed": False,
        "labels_computed": False,
        "input_provenance_verified": False,
        "source_census_bound": False,
        "participant_packet_ready": False,
        "scientifically_qualified": False,
        "counts": {
            "electrode_row_count": len(electrodes),
            "pair_occurrence_count": len(stimulation_pairs),
            "endpoint_occurrence_count": 2 * len(stimulation_pairs),
            "distinct_selected_electrode_rows": len(selected_rows),
            "distinct_selected_coordinate_scalar_count": 3 * len(selected_rows),
        },
        "pairs": validated_pairs,
    }
