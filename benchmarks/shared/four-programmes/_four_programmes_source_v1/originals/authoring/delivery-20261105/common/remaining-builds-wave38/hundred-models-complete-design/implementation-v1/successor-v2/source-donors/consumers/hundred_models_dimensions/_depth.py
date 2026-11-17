"""Pure source-domain translation of custom_plotting.py:484–559.

This module preserves the released transformations, including odd endpoints. It
does not establish native dtype/rounding parity, original-data completeness, or
the scientific validity of any input. Call separately for each source ROI/group.
"""

from collections import Counter
from dataclasses import dataclass, replace
from math import floor, isfinite, prod


class DepthDomainError(ValueError):
    """Unsupported or undefined released-source domain; never a repair."""


class DepthLimitError(DepthDomainError):
    """Declared consumer work bound exceeded; no partial result is returned."""


@dataclass(frozen=True)
class Column:
    name: str
    kind: str
    shape: tuple = ()


@dataclass(frozen=True)
class Table:
    columns: tuple
    rows: tuple

    def column_index(self, name):
        for index, column in enumerate(self.columns):
            if column.name == name:
                return index
        raise DepthDomainError("missing_column:" + name)


@dataclass(frozen=True)
class Limits:
    """Consumer counts, not a process-memory reservation or runtime sandbox."""

    max_rows: int = 100_000
    max_scalar_cells: int = 2_000_000
    max_text_characters: int = 2_000_000
    max_aggregate_cells: int = 16_000_000


@dataclass(frozen=True)
class SlowFastGroup:
    model: str
    suffix: str
    source_row_indices: tuple
    retained_integer_layer: int


@dataclass(frozen=True)
class MiddleRound:
    model: str
    input_middle_rows: int
    output_middle_rows: int


@dataclass(frozen=True)
class Adjustment:
    table: Table
    modal_depth: object
    layer_counts: tuple
    slowfast_groups: tuple
    middle_rounds: tuple
    aggregate_cells: int
    native_numeric_parity_qualified: bool = False
    scientific_qualified: bool = False


@dataclass(frozen=True)
class Normalization:
    table: Table
    max_layers: tuple
    zero_max_models: tuple
    native_numeric_parity_qualified: bool = False
    scientific_qualified: bool = False


def _check_limits(limits):
    if type(limits) is not Limits:
        raise DepthDomainError("limits_type")
    for value in vars(limits).values():
        if type(value) is not int or value < 1:
            raise DepthDomainError("limits_positive_integer")


def _finite_real(value):
    return type(value) is float and isfinite(value)


def _array_check(value, shape):
    if not shape:
        if not _finite_real(value):
            raise DepthDomainError("array_requires_finite_float_leaves")
        return
    if type(value) is not tuple or len(value) != shape[0]:
        raise DepthDomainError("array_shape_or_mutability")
    for part in value:
        _array_check(part, shape[1:])


def _width(column):
    return prod(column.shape) if column.kind == "array" else 1


def validate_table(table, limits=Limits()):
    """Validate an explicit semantic profile, without inferring a native dtype.

    text: plain str or None (source missing); integer: exact Python int in the
    portable +/- (2**53-1) domain, no missing; real: finite Python float or None;
    array: fixed nonempty rectangular tuples of finite Python float leaves.
    None is the portable missing sentinel, not an array-like Python value.
    """
    _check_limits(limits)
    if type(table) is not Table or type(table.columns) is not tuple or not table.columns:
        raise DepthDomainError("table_columns")
    names = set()
    for column in table.columns:
        if type(column) is not Column or type(column.name) is not str or not column.name:
            raise DepthDomainError("column_declaration")
        if column.name in names:
            raise DepthDomainError("duplicate_column")
        names.add(column.name)
        if column.kind not in ("text", "integer", "real", "array"):
            raise DepthDomainError("column_kind")
        if type(column.shape) is not tuple:
            raise DepthDomainError("column_shape")
        if column.kind == "array":
            if not column.shape or len(column.shape) > 8 or any(
                type(size) is not int or size < 1 for size in column.shape
            ):
                raise DepthDomainError("nonempty_array_shape_up_to_eight_axes")
        elif column.shape:
            raise DepthDomainError("scalar_column_shape")
    if type(table.rows) is not tuple or not table.rows:
        raise DepthDomainError("empty_or_mutable_rows")
    if len(table.rows) > limits.max_rows:
        raise DepthLimitError("row_limit")
    cells = len(table.rows) * sum(map(_width, table.columns))
    if cells > limits.max_scalar_cells:
        raise DepthLimitError("scalar_cell_limit")
    text_chars = 0
    for row in table.rows:
        if type(row) is not tuple or len(row) != len(table.columns):
            raise DepthDomainError("row_width_or_mutability")
        for column, value in zip(table.columns, row):
            if column.kind == "text":
                if value is not None and type(value) is not str:
                    raise DepthDomainError("text_value")
                text_chars += len(value) if value is not None else 0
            elif column.kind == "integer":
                if type(value) is not int or abs(value) > 2**53 - 1:
                    raise DepthDomainError("portable_exact_integer_domain")
            elif column.kind == "real":
                if value is not None and not _finite_real(value):
                    raise DepthDomainError("finite_real_or_missing")
            else:
                _array_check(value, column.shape)
    if text_chars > limits.max_text_characters:
        raise DepthLimitError("text_character_limit")
    model = table.column_index("Model")
    if table.columns[model].kind != "text" or any(
        type(row[model]) is not str for row in table.rows
    ):
        raise DepthDomainError("model_requires_nonmissing_plain_strings")
    return table


def _number_aggregate(values, agg):
    # Python binary64 summation is explicit; NumPy/Pandas bit parity is untested.
    if agg == "max":
        value = max(values)
    else:
        value = sum(values, 0.0) / len(values)
    if not isfinite(value):
        raise DepthDomainError("nonfinite_intermediate_arithmetic")
    return value


def _array_aggregate(values, shape, agg):
    if not shape:
        return _number_aggregate(values, agg)
    return tuple(
        _array_aggregate(tuple(value[i] for value in values), shape[1:], agg)
        for i in range(shape[0])
    )


def _custom_aggregate(column, values, agg):
    if column.kind == "array":
        return _array_aggregate(values, column.shape, agg)
    # Source nunique() excludes missing, but returns the ORIGINAL FIRST value.
    # This intentionally preserves (None, 'x') -> None versus ('x', None) -> 'x'.
    unique = {value for value in values if value is not None}
    if len(unique) == 1:
        return values[0]
    if column.kind == "integer":
        return values[0]
    if column.kind == "real":
        present = tuple(value for value in values if value is not None)
        return _number_aggregate(present, agg) if present else None
    return None


def _aggregate_rows(columns, rows, agg):
    return tuple(
        _custom_aggregate(column, tuple(row[i] for row in rows), agg)
        for i, column in enumerate(columns)
    )


def _integer_linspace(start, stop, count):
    """Source nonnegative float-step/multiply/add, then floor; no interpolation.

    This states the supported NumPy algorithmic convention, without claiming
    cross-version native operation/rounding parity. The final endpoint is exact.
    """
    if count == 0:
        return ()
    if count == 1:
        return (start,)
    step = float(stop - start) / (count - 1)
    values = [floor(float(i) * step + start) for i in range(count)]
    values[-1] = stop
    return tuple(values)


def adjust_layers(table, only_sf=False, limits=Limits()):
    """Translate one released-source group (one ROI and one grouping value).

    Every input row is consumed. Only source-defined grouping/reduction occurs.
    Unique integer Layer per model removes the unresolved unstable-sort tie
    domain. Case-sensitive 'slowfast' matches and lexical suffix order are exact.
    Modal depth one is refused because the released while loop never terminates.
    """
    validate_table(table, limits)
    if type(only_sf) is not bool:
        raise DepthDomainError("only_sf_boolean")
    model_i = table.column_index("Model")
    layer_i = table.column_index("Layer")
    name_i = table.column_index("Layer_FullNames")
    if table.columns[layer_i].kind != "integer":
        raise DepthDomainError("adjust_requires_integer_layer_profile")
    if table.columns[name_i].kind != "text":
        raise DepthDomainError("layer_names_text_profile")
    if any(column.name == "LayerSuffix" for column in table.columns):
        raise DepthDomainError("reserved_source_scratch_column_LayerSuffix")
    seen = set()
    for row in table.rows:
        identity = (row[model_i], row[layer_i])
        if identity in seen:
            raise DepthDomainError("unresolved_native_unstable_layer_sort_tie")
        seen.add(identity)
        if "slowfast" in row[model_i] and type(row[name_i]) is not str:
            raise DepthDomainError("slowfast_suffix_requires_nonmissing_string")
    width = sum(map(_width, table.columns))
    groups = {}
    for index, row in sorted(enumerate(table.rows), key=lambda pair: pair[1][layer_i]):
        groups.setdefault(row[model_i], []).append((index, row))
    sf_trace = []
    collapsed = {}
    work = 0

    def charge(input_rows):
        nonlocal work
        prospective = work + input_rows * width
        if prospective > limits.max_aggregate_cells:
            raise DepthLimitError("aggregate_cell_limit")
        work = prospective

    for model in sorted(groups):
        group = groups[model]
        if "slowfast" not in model:
            collapsed[model] = [row for _, row in group]
            continue
        suffix_groups = {}
        for index, row in group:
            name = row[name_i]
            suffix = (name.split("_lateral")[0].split("_")[-1]
                      if "_lateral" in name else name.split("_")[-1])
            suffix_groups.setdefault(suffix, []).append((index, row))
        model_rows = []
        for suffix in sorted(suffix_groups):
            members = suffix_groups[suffix]
            charge(len(members))
            reduced = list(_aggregate_rows(table.columns, tuple(row for _, row in members), "max"))
            reduced[name_i] = suffix
            model_rows.append(tuple(reduced))
            sf_trace.append(SlowFastGroup(model, suffix, tuple(i for i, _ in members), reduced[layer_i]))
        collapsed[model] = model_rows
    counts = tuple((model, len({row[layer_i] for row in rows})) for model, rows in collapsed.items())
    if only_sf:
        output = Table(table.columns, tuple(row for rows in collapsed.values() for row in rows))
        validate_table(output, limits)
        return Adjustment(output, None, counts, tuple(sf_trace), (), work)
    frequencies = Counter(count for _, count in counts)
    modal = min(count for count, frequency in frequencies.items() if frequency == max(frequencies.values()))
    if modal == 1:
        raise DepthDomainError("source_nontermination_modal_depth_one")
    output_count = sum(2 + min(max(len(rows) - 2, 0), modal - 2) for rows in collapsed.values())
    if output_count > limits.max_rows or output_count * width > limits.max_scalar_cells:
        raise DepthLimitError("adjusted_output_size_limit")
    output_rows = []
    round_trace = []
    for model, rows in collapsed.items():
        middle = rows[1:-1]
        while len(middle) > modal - 2:
            before = len(middle)
            charge(2 * max(before - 1, 0))
            middle = [
                _aggregate_rows(table.columns, (middle[i], middle[i + 1]), "mean")
                for i in range(before - 1)
            ]
            round_trace.append(MiddleRound(model, before, len(middle)))
        middle_indices = _integer_linspace(1, modal - 2, len(middle))
        first = list(rows[0])
        last = list(rows[-1])
        if len(rows) == 1:
            # Source loc[0] and loc[len(group)-1] address the SAME row.
            first[layer_i] = modal - 1
            last[layer_i] = modal - 1
        else:
            first[layer_i] = 0
            last[layer_i] = modal - 1
        output_rows.append(tuple(first))
        for row, new_layer in zip(middle, middle_indices):
            updated = list(row)
            updated[layer_i] = new_layer
            output_rows.append(tuple(updated))
        output_rows.append(tuple(last))
    output = Table(table.columns, tuple(output_rows))
    validate_table(output, limits)
    return Adjustment(output, modal, counts, tuple(sf_trace), tuple(round_trace), work)


def normalize_to_model_depth(table, limits=Limits()):
    """Append source MaxLayer and divide Layer, preserving row order.

    Supported Layer values are finite nonnegative integer/real values. All-zero
    models produce None (source NaN from 0/0), never a repaired zero or endpoint.
    Negative-layer/infinite-division and preexisting MaxLayer domains are refused.
    """
    validate_table(table, limits)
    model_i = table.column_index("Model")
    layer_i = table.column_index("Layer")
    layer_column = table.columns[layer_i]
    if layer_column.kind not in ("integer", "real"):
        raise DepthDomainError("normalize_requires_numeric_layer_profile")
    if any(column.name == "MaxLayer" for column in table.columns):
        raise DepthDomainError("source_merge_collision_MaxLayer")
    if any(row[layer_i] is None or row[layer_i] < 0 for row in table.rows):
        raise DepthDomainError("normalize_requires_nonmissing_nonnegative_layers")
    maxima = {}
    for row in table.rows:
        model, layer = row[model_i], row[layer_i]
        maxima[model] = max(layer, maxima.get(model, layer))
    columns = list(table.columns)
    columns[layer_i] = replace(layer_column, kind="real")
    columns.append(Column("MaxLayer", layer_column.kind))
    new_width = sum(map(_width, columns))
    if len(table.rows) * new_width > limits.max_scalar_cells:
        raise DepthLimitError("normalized_output_size_limit")
    rows = []
    for row in table.rows:
        maximum = maxima[row[model_i]]
        updated = list(row)
        updated[layer_i] = row[layer_i] / maximum if maximum else None
        updated.append(maximum)
        rows.append(tuple(updated))
    output = Table(tuple(columns), tuple(rows))
    validate_table(output, limits)
    return Normalization(output, tuple(sorted(maxima.items())), tuple(sorted(model for model, maximum in maxima.items() if maximum == 0)))
