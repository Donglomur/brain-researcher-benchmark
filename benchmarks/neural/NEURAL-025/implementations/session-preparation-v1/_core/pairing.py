"""Finite-valued translation of the author joint-angle and events branches.

This implements no fit, cell ranking, split, inverse kinematics, or score.
Spatial Gaussian arithmetic is explicit; native MATLAB equivalence is untested.
The generic array interface serves controls; authentic trial admission is separate.
"""
import math
import numpy as np


class PairingRefusal(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise PairingRefusal(message)


def array(value, name, ndim, max_elements):
    require(type(value) is np.ndarray and value.dtype == np.dtype('float64'),
            name + ': explicit float64 ndarray required')
    require(value.ndim == ndim and 0 < value.size <= max_elements,
            name + ': bounded dimensions required')
    require(bool(np.isfinite(value).all()), name + ': nonfinite input refused')
    return value


def scalar(value, name):
    require(type(value) in (float, int) and not isinstance(value, bool),
            name + ': ordinary numeric scalar required')
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise PairingRefusal(name + ': finite scalar required') from exc
    require(math.isfinite(result), name + ': finite scalar required')
    return result


def gaussian_full(values, sd):
    """Columnwise spatial filtering with edge-inclusive symmetric extension.

fLen follows gaussFilt1 exactly. np.pad(mode='symmetric') includes the edge
sample; mode='reflect' would implement a different endpoint convention.
Finite-only admission is stricter than the native helper's unspecified NaN
behavior. This is not evidence of imgaussfilt implementation equivalence.
"""
    require(math.isfinite(sd) and sd > 0, 'Positive Gaussian SD required')
    # Reject before ceil/int/kernel allocation, including extreme caller input.
    require(sd <= 16, 'Gaussian support exceeds 129-tap component cap')
    length = math.ceil(sd * 8)
    length += (length + 1) % 2
    radius = length // 2
    offsets = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-0.5 * (offsets / sd) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(values, ((radius, radius), (0, 0)), mode='symmetric')
    result = np.empty_like(values)
    for column in range(values.shape[1]):
        result[:, column] = np.convolve(padded[:, column], kernel, mode='valid')
    require(bool(np.isfinite(result).all()), 'Gaussian arithmetic overflow')
    return result


def pair_trial(events, joint_angles, camera_times, frame_times, roi_lags,
               cycle_ms, sync_ms, lift_ms, shared_camera_step_ms):
    """Return every source preparation stage, preserving input column order.

The shared camera step comes from the first eligible maxCams trial of the
already frozen session census. It is deliberately not recomputed per trial.
All clocks are milliseconds; camera/frame clocks are relative to syncTime.
"""
    events = array(events, 'events', 2, 1000000)
    joint_angles = array(joint_angles, 'joint_angles', 2, 480000)
    camera_times = array(camera_times, 'camera_times', 1, 20000)
    frame_times = array(frame_times, 'frame_times', 1, 20000)
    roi_lags = array(roi_lags, 'roi_lags', 1, 565)
    require(2 <= events.shape[0] <= 20000 and 1 <= events.shape[1] <= 565,
            'Bounded events shape required')
    require(joint_angles.shape == (camera_times.size, 24) and camera_times.size >= 2,
            'Exactly 24 joints and matching camera rows required')
    require(frame_times.size == events.shape[0] and roi_lags.size == events.shape[1],
            'Frame/event and ROI/lag dimensions differ')
    require(bool((np.diff(camera_times) > 0).all()) and
            bool((np.diff(frame_times) > 0).all()), 'Strictly increasing clocks required')
    cycle = scalar(cycle_ms, 'cycle_ms')
    sync = scalar(sync_ms, 'sync_ms')
    lift = scalar(lift_ms, 'lift_ms')
    camera_step = scalar(shared_camera_step_ms, 'shared_camera_step_ms')
    require(cycle >= 10 and camera_step > 0, 'Invalid source time bases')
    require(camera_step >= 15 / 16, 'Camera kernel exceeds bounded support')

    prepared_grid = np.arange(-200, 801, 10, dtype=np.float64)
    padded_grid = np.arange(-270, 871, 10, dtype=np.float64)
    eval_grid = np.arange(-100, 401, 10, dtype=np.float64)
    width = 10.0 / cycle
    require(width > 0, 'Frame-width underflow')
    with np.errstate(over='raise', invalid='raise', divide='raise'):
        try:
            # Keep source operation order: subtract sync before frame origin;
            # add grid/cycle before subtracting each individual ROI lag/cycle.
            relative_event = lift - sync
            frame_zero = 1.0 + (relative_event - frame_times[0]) / cycle
            frame_points = frame_zero + padded_grid / cycle
            coordinates = frame_points[:, None] - roi_lags[None, :] / cycle
            require(bool(np.isfinite(coordinates).all()), 'Nonfinite frame coordinates')
            early_float, late_float = np.floor(coordinates), np.ceil(coordinates)
            require(float(early_float.min()) >= 1 and
                    float(late_float.max()) <= events.shape[0], 'Original frame support missing')
            early = early_float.astype(np.int64) - 1
            late = late_float.astype(np.int64) - 1
            early_weight = np.minimum((late_float - coordinates) / width, 1.0)
            columns = np.arange(events.shape[1])
            neural_padded = (events[early, columns] * early_weight +
                             events[late, columns] * (1.0 - early_weight)) * width
            require(bool(np.isfinite(neural_padded).all()), 'Count-overlap arithmetic overflow')
            neural_smoothed = gaussian_full(neural_padded, 3.5)
            neural_prepared = neural_smoothed[7:108].copy()
            joints_smoothed = gaussian_full(joint_angles, 15.0 / camera_step)
            camera_relative = camera_times + sync - lift
            require(bool(np.isfinite(camera_relative).all()) and
                    bool((np.diff(camera_relative) > 0).all()), 'Invalid event-relative camera clock')
            require(camera_relative[0] <= prepared_grid[0] and
                    camera_relative[-1] >= prepared_grid[-1], 'Original camera support missing')
            joint_prepared = np.empty((101, 24), dtype=np.float64)
            for column in range(24):
                joint_prepared[:, column] = np.interp(prepared_grid, camera_relative,
                                                     joints_smoothed[:, column])
            require(bool(np.isfinite(joint_prepared).all()), 'Interpolation arithmetic overflow')
        except FloatingPointError as exc:
            raise PairingRefusal('Nonfinite floating-point arithmetic') from exc
    return {
        'padded_grid_ms': padded_grid, 'prepared_grid_ms': prepared_grid,
        'evaluation_grid_ms': eval_grid, 'frame_coordinates_one_based': coordinates,
        'early_frame_indices_one_based': early + 1, 'late_frame_indices_one_based': late + 1,
        'neural_padded': neural_padded, 'neural_smoothed_padded': neural_smoothed,
        'neural_prepared': neural_prepared, 'joint_smoothed_full': joints_smoothed,
        'joint_prepared': joint_prepared, 'neural_eval': neural_prepared[10:61].copy(),
        'joint_eval': joint_prepared[10:61].copy(),
    }
