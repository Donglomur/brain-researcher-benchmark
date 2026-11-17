"""Operator-only source-bound feature views; no file I/O or neural query reads."""
import numpy as np

from reference.encoder import MOVEMENT_FEATURES, PROFILES, ReferenceError


def _require(condition, message):
    if not condition:
        raise ReferenceError(message)


def _integer(value, name):
    _require(type(value) in (int, np.int32, np.int64) and value >= 0,
             f"{name} must be a nonnegative integer")
    return int(value)


def _number(value, name):
    _require(type(value) in (int, float, np.int32, np.int64, np.float32, np.float64)
             and np.isfinite(value), f"{name} must be finite numeric")
    return float(value)


def _array(descriptor, arrays_by_path, name):
    _require(type(descriptor) is dict and type(descriptor.get("path")) is str
             and "shape" in descriptor and "dtype" in descriptor,
             f"missing primitive descriptor for {name}")
    _require(descriptor["path"] in arrays_by_path, f"missing admitted array {name}")
    value = arrays_by_path[descriptor["path"]]
    _require(isinstance(value, np.ndarray) and value.dtype.kind in "fiu",
             f"{name} must be a primitive numeric array")
    try:
        dtype = np.dtype(descriptor["dtype"])
    except (ValueError, TypeError) as error:
        raise ReferenceError(f"invalid {name} dtype descriptor") from error
    _require(list(value.shape) == descriptor["shape"] and value.dtype == dtype,
             f"descriptor/body shape or dtype disagreement for {name}")
    return value


def _named(acquisition, arrays_by_path, name):
    _require(type(acquisition.get("arrays")) is dict and name in acquisition["arrays"],
             f"missing mandatory source field {name}")
    return _array(acquisition["arrays"][name], arrays_by_path, name)


def _vector(acquisition, arrays_by_path, name):
    result = _named(acquisition, arrays_by_path, name)
    _require(result.shape == (acquisition["original_trial_count"],),
             f"{name} must use the full original trial axis")
    return result


def _modal(acquisition, modality):
    _require(modality in ("GrC", "CF"), "unknown modality")
    matches = [m for m in acquisition.get("modalities", []) if m.get("name") == modality]
    _require(len(matches) == 1 and matches[0].get("status") == "present",
             "required modality missing/structurally absent")
    _require(_integer(matches[0].get("cell_count"), "cell_count") > 0,
             "empty present cell axis")
    return matches[0]


def _binding(acquisition, arrays_by_path):
    _require(type(acquisition) is dict and _integer(acquisition.get("original_trial_count"),
             "original_trial_count") > 0, "invalid acquisition")
    _require(type(acquisition.get("views")) is list and acquisition["views"],
             "source-nonselected acquisition cannot generate encoding views")
    binding = acquisition.get("encoding_binding")
    _require(type(binding) is dict and binding.get("status") == "authenticated",
             "source clock/unit/identity admission certificate required")
    _require(binding.get("behavior_clock") == "tmpxx" and
             binding.get("rew_pos_clock") == "reward_aligned", "wrong source behavior-clock binding")
    for flag in ("event_clock_join", "omission_clock_join", "target_grid_join", "trial_axis_join"):
        _require(binding.get(flag) is True, f"unresolved source join: {flag}")
    units = binding.get("position_units")
    banned = {"unknown", "unspecified", "none", "n/a", "arbitrary", "a.u."}
    _require(type(units) is list and len(units) == 2 and
             all(type(u) is str and u.strip() and u.strip().lower() not in banned for u in units)
             and units[0] == units[1], "two commensurate authenticated position units required")
    dtb = _number(acquisition.get("dtb_seconds"), "source dtb_seconds")
    certified_dtb = _number(binding.get("dtb_seconds"), "certified dtb_seconds")
    _require(dtb > 0 and dtb == certified_dtb, "source/certificate dtb disagreement")
    clock = _named(acquisition, arrays_by_path, "behavior_clock")
    _require(clock.ndim == 1 and len(clock) >= 2 and np.isfinite(clock).all()
             and np.all(np.diff(clock) > 0), "finite increasing behavior clock required")
    _require(np.allclose(np.diff(clock), dtb, rtol=1e-9, atol=1e-12),
             "native behavior-clock spacing disagrees with source dtb")
    return clock, dtb


def _row(acquisition, arrays_by_path, row):
    row = _integer(row, "source row")
    _require(row < acquisition["original_trial_count"], "row outside original source axis")
    flags = {}
    for name in ("rewarded", "eligible", "eligible_rewarded", "eligible_omitted", "goodMvmt_source"):
        value = _vector(acquisition, arrays_by_path, name)[row]
        _require(np.isfinite(value) and value in (0, 1), f"invalid source flag {name}")
        flags[name] = bool(value)
    length = _number(_vector(acquisition, arrays_by_path, "mvlen")[row], "movement length")
    _require(flags["eligible"] and flags["goodMvmt_source"] and length > 6,
             "query/training row not in complete source-declared eligible support")
    _require(flags["eligible_rewarded"] == (flags["eligible"] and flags["rewarded"]) and
             flags["eligible_omitted"] == (flags["eligible"] and not flags["rewarded"]),
             "source outcome eligibility masks disagree")
    return row, flags["rewarded"], length


def context_categories(acquisition, rewarded):
    """Canonical source-census category tokens; never infer query categories."""
    context = acquisition.get("source_context")
    _require(type(context) is dict and acquisition.get("collection") in ("main", "water"),
             "source collection/context missing")
    delay = _number(context.get("Delay"), "planned source Delay")
    first = context.get("FirstRew")
    _require(type(first) is str and first, "literal source FirstRew required")
    reinforcer = "water" if acquisition["collection"] == "water" else context.get("DAType")
    _require(type(reinforcer) is str and reinforcer, "literal source DAType required")
    _require(type(rewarded) in (bool, np.bool_), "source delivered/omitted boolean required")
    return {"planned_delay": format(delay, ".17g"), "reinforcer": reinforcer,
            "first_reward_order": first,
            "delivered_outcome": "delivered" if rewarded else "omitted"}


def _time_grid(acquisition, arrays_by_path, modality):
    modal = _modal(acquisition, modality)
    grid = _array(modal.get("target_time"), arrays_by_path, "target_time")
    _require(grid.ndim == 1 and len(grid) >= 2 and np.isfinite(grid).all()
             and np.all(np.diff(grid) > 0), "full native target grid invalid")
    if acquisition.get("schema") == "paper_i_joined_acquisition_v1":
        return modal, grid
    descriptor = modal.get("targets")
    # Shape metadata only: query construction must never dereference targets.
    _require(type(descriptor) is dict and descriptor.get("shape") ==
             [acquisition["original_trial_count"], modal["cell_count"], len(grid)],
             "target descriptor does not bind original trial/cell/native-time axes")
    return modal, grid


def _interpolate_missing(clock, values, coordinates):
    result = []
    for coordinate in coordinates:
        if coordinate < clock[0] or coordinate > clock[-1]:
            result.append(None)
            continue
        right = int(np.searchsorted(clock, coordinate, side="left"))
        if right < len(clock) and clock[right] == coordinate:
            value = values[right]
        else:
            left = right - 1
            if not np.isfinite(values[left]) or not np.isfinite(values[right]):
                result.append(None)
                continue
            ratio = (coordinate - clock[left]) / (clock[right] - clock[left])
            value = (1 - ratio) * values[left] + ratio * values[right]
        result.append(float(value) if np.isfinite(value) else None)
    return result


def source_reference(acquisition, modality, row):
    """Resolve only an authenticated selected physical row, preserving source clocks."""
    row = _integer(row, "joined row")
    if acquisition.get("schema") != "paper_i_joined_acquisition_v1":
        _require(row < acquisition["original_trial_count"], "source row outside complete axis")
        modal = _modal(acquisition, modality)
        return acquisition, row, list(range(modal["cell_count"]))
    _require(row < acquisition["original_trial_count"] and type(acquisition.get("trial_sources")) is dict,
             "joined row outside authenticated released chronology")
    refs = acquisition["trial_sources"].get(modality)
    _require(type(refs) is list and len(refs) == acquisition["original_trial_count"],
             "complete physical modality source-reference axis")
    ref = refs[row]
    _require(type(ref) is dict and set(ref) == {"source_key", "row", "cell_indices"},
             "selected physical row needs its original source reference")
    sources = acquisition.get("source_acquisitions")
    _require(type(sources) is dict and ref["source_key"] in sources, "authenticated original source collection")
    source = sources[ref["source_key"]]
    _require(source.get("schema") != "paper_i_joined_acquisition_v1", "no recursively invented source joins")
    source_row = _integer(ref["row"], "original source row")
    _require(source_row < source["original_trial_count"], "original source row bound")
    original = _modal(source, modality)
    canonical = _modal(acquisition, modality)
    order = ref["cell_indices"]
    _require(type(order) is list and len(order) == canonical["cell_count"] == original["cell_count"] and
             all(type(i) is int and 0 <= i < original["cell_count"] for i in order) and
             len(set(order)) == len(order), "complete canonical-to-original cell bijection")
    return source, source_row, order


def context_for_row(acquisition, arrays_by_path, modality, row):
    source, source_row, _ = source_reference(acquisition, modality, row)
    _, rewarded, _ = _row(source, arrays_by_path, source_row)
    return context_categories(source, rewarded)


def target_trajectory(acquisition, arrays_by_path, modality, row):
    """Operator-only complete canonical-cell trajectory; never called by a query."""
    source, source_row, order = source_reference(acquisition, modality, row)
    modal, grid = _time_grid(source, arrays_by_path, modality)
    _, common = _time_grid(acquisition, arrays_by_path, modality)
    _require(np.array_equal(grid, common), "exact common physical target grid; no resampling")
    values = _array(modal["targets"], arrays_by_path, "original selected targets")
    _require(values.shape == (source["original_trial_count"], modal["cell_count"], len(grid)),
             "complete original target axes")
    return np.asarray(values[source_row, order, :], dtype=np.float64)


def _joined_training_view(acquisition, arrays_by_path, modality, rows, profile, cell_indices, permutation):
    modal, grid = _time_grid(acquisition, arrays_by_path, modality)
    _require(type(rows) in (list, tuple) and rows, "complete nonempty physical training rows")
    rows = [_integer(row, "physical training row") for row in rows]
    _require(len(set(rows)) == len(rows), "duplicate physical training rows")
    categories = {row: context_for_row(acquisition, arrays_by_path, modality, row) for row in rows}
    if cell_indices is None: cell_indices = list(range(modal["cell_count"]))
    _require(type(cell_indices) in (list, tuple) and cell_indices, "complete selected cell axis")
    cells = [_integer(cell, "canonical cell index") for cell in cell_indices]
    _require(len(set(cells)) == len(cells) and max(cells) < modal["cell_count"], "canonical cell selection")
    if profile == "CM-shuffled":
        _require(type(permutation) is dict and set(permutation) == set(rows) and
                 all(type(value) in (int, np.int32, np.int64) for value in permutation.values()) and
                 set(permutation.values()) == set(rows), "complete physical training-only trajectory bijection")
        availability = acquisition.get("observed_modalities")
        _require(type(availability) is list and len(availability) == acquisition["original_trial_count"],
                 "complete observed-modality availability census")
        _require(all(categories[row] == categories[int(permutation[row])] and
                     availability[row] == availability[int(permutation[row])] for row in rows),
                 "physical trajectory reassignment remains within source context and observed-modality stratum")
        source_rows = [int(permutation[row]) for row in rows]
    else:
        _require(profile in PROFILES and permutation is None, "only shuffled profile accepts a private null")
        source_rows = rows
    trajectories = [target_trajectory(acquisition, arrays_by_path, modality, row)[cells] for row in source_rows]
    _require(all(np.isfinite(values).all() for values in trajectories), "finite complete physical training targets")
    y = np.ascontiguousarray(np.stack(trajectories).transpose(0, 2, 1).reshape(-1, len(cells)))
    records, index = [], []
    for row in rows:
        source, source_row, _ = source_reference(acquisition, modality, row)
        for time_index in range(len(grid)):
            records.append(one_record(acquisition, arrays_by_path, modality, row, time_index, profile))
            index.append({"source_row": row, "source_key": source["key"],
                          "original_source_row": source_row, "time_index": time_index})
    weights = np.full(len(records), 1.0 / len(rows) / len(grid), dtype=np.float64)
    return {"X": records, "Y": y, "weights": weights, "training_mean": weights @ y,
            "private_index": index, "cell_indices": cells, "profile": profile,
            "requires_private_transport_permutation": True,
            "null_ineffective_singleton_rows": [row for row in rows if profile == "CM-shuffled"
                and sum(categories[row] == categories[other] and availability[row] == availability[other]
                        for other in rows) == 1]}


def one_record(acquisition, arrays_by_path, modality, row, time_index, profile):
    """One legal local predictor record; no neural target body is accessed."""
    if acquisition.get("schema") == "paper_i_joined_acquisition_v1":
        source, source_row, _ = source_reference(acquisition, modality, row)
        _, common = _time_grid(acquisition, arrays_by_path, modality)
        _, grid = _time_grid(source, arrays_by_path, modality)
        _require(np.array_equal(grid, common), "exact common target grid before physical query")
        return one_record(source, arrays_by_path, modality, source_row, time_index, profile)
    _require(profile in PROFILES, "unknown profile")
    clock, dtb = _binding(acquisition, arrays_by_path)
    row, rewarded, movement_length = _row(acquisition, arrays_by_path, row)
    _, grid = _time_grid(acquisition, arrays_by_path, modality)
    time_index = _integer(time_index, "target time index")
    _require(time_index < len(grid), "time index outside complete native target grid")
    time = float(grid[time_index])
    delay = _number(_vector(acquisition, arrays_by_path, "rewdel_seconds")[row],
                    "measured event delay")
    true_end = _number(_vector(acquisition, arrays_by_path, "trueend")[row], "source trueend")
    reward_time = _number(_vector(acquisition, arrays_by_path, "rewtimes")[row], "source rewtimes")
    _require(np.isclose(delay, (reward_time - true_end) * dtb, rtol=1e-12, atol=1e-12),
             "source measured-delay/event-clock fields disagree")
    result = {}
    if profile != "M":
        result.update(time=time, measured_delay=delay,
                      categories=context_categories(acquisition, rewarded))
    if profile != "C":
        positions = _named(acquisition, arrays_by_path, "rew_pos")
        _require(positions.shape == (acquisition["original_trial_count"], len(clock), 2),
                 "exact two-component rewAlgn.pos axes required")
        position = np.asarray(positions[row], dtype=np.float64)
        _require(not np.isinf(position).any() and np.isfinite(position).any(axis=0).all(),
                 "mandatory handle component wholly unavailable or infinite")
        velocity = np.empty_like(position)
        velocity[1:] = np.diff(position, axis=0) / dtb
        velocity[0] = (position[1] - position[0]) / dtb
        speed = np.sqrt(np.sum(velocity * velocity, axis=1))
        _require(not np.isinf(velocity).any() and not np.isinf(speed).any(),
                 "behavior derivative arithmetic overflow")
        center = time if modality == "CF" else time - delay
        taps = center + np.arange(-4, 5, dtype=np.float64) / 10
        channels = [position[:, 0], position[:, 1], velocity[:, 0], velocity[:, 1], speed]
        values = [value for channel in channels for value in _interpolate_missing(clock, channel, taps)]
        duration = _number(_vector(acquisition, arrays_by_path, "movement_duration_ms")[row],
                           "source movement duration in milliseconds")
        true_start = _number(_vector(acquisition, arrays_by_path, "truestart")[row], "source truestart")
        _require(duration >= 0 and np.isclose(duration, (true_end - true_start) * dtb * 1000,
                 rtol=1e-12, atol=1e-9), "source movement duration/event fields disagree")
        values += [duration, movement_length]
        result["movement"] = dict(zip(MOVEMENT_FEATURES, values))
    return result


def query_record(acquisition, arrays_by_path, modality, row, time_index, profile):
    return one_record(acquisition, arrays_by_path, modality, row, time_index, profile)


def training_view(acquisition, arrays_by_path, modality, rows, profile,
                  cell_indices=None, permutation=None):
    """Complete training trial trajectories, flattened only after reassignment.

    Caller authenticates roles/purges and privately permutes transport order.
    The private_index and permutation must never enter candidate feature views.
    """
    if acquisition.get("schema") == "paper_i_joined_acquisition_v1":
        return _joined_training_view(acquisition, arrays_by_path, modality, rows, profile, cell_indices, permutation)
    _binding(acquisition, arrays_by_path)
    modal, grid = _time_grid(acquisition, arrays_by_path, modality)
    _require(type(rows) in (list, tuple) and len(rows) > 0, "nonempty authenticated training rows required")
    rows = [_integer(row, "training source row") for row in rows]
    _require(len(set(rows)) == len(rows), "duplicate physical training rows/aliases")
    categories = {}
    for row in rows:
        _, rewarded, _ = _row(acquisition, arrays_by_path, row)
        categories[row] = context_categories(acquisition, rewarded)
    if cell_indices is None:
        cell_indices = list(range(modal["cell_count"]))
    _require(type(cell_indices) in (list, tuple) and len(cell_indices) > 0,
             "nonempty cell axis required")
    cell_indices = [_integer(cell, "cell index") for cell in cell_indices]
    _require(len(set(cell_indices)) == len(cell_indices) and max(cell_indices) < modal["cell_count"],
             "invalid/duplicate cell selection")
    if profile == "CM-shuffled":
        _require(type(permutation) is dict and set(permutation) == set(rows) and
                 all(type(v) in (int, np.int32, np.int64) for v in permutation.values()) and
                 set(permutation.values()) == set(rows), "complete training-only bijection required")
        for destination, source in permutation.items():
            _require(categories[destination] == categories[source],
                     "training permutation crosses discrete source context stratum")
        source_rows = [int(permutation[row]) for row in rows]
    else:
        _require(profile in PROFILES and permutation is None,
                 "only CM-shuffled accepts a training permutation")
        source_rows = rows
    targets = _array(modal["targets"], arrays_by_path, "training targets")
    # Never scan or normalize query rows: select permitted training labels first.
    selected = targets[np.asarray(source_rows)][:, np.asarray(cell_indices), :]
    _require(np.isfinite(selected).all(), "nonfinite required training targets; no row/cell deletion")
    y = np.asarray(selected.transpose(0, 2, 1).reshape(-1, len(cell_indices)), dtype=np.float64)
    records, index = [], []
    for row in rows:
        for time_index in range(len(grid)):
            records.append(one_record(acquisition, arrays_by_path, modality, row, time_index, profile))
            index.append({"source_row": row, "time_index": time_index})
    weights = np.full(len(records), 1.0 / len(rows) / len(grid), dtype=np.float64)
    return {"X": records, "Y": y, "weights": weights,
            "training_mean": weights @ y, "private_index": index,
            "cell_indices": cell_indices, "profile": profile,
            "requires_private_transport_permutation": True,
            "null_ineffective_singleton_rows": [row for row in rows if profile == "CM-shuffled"
                and sum(categories[row] == categories[other] for other in rows) == 1]}
