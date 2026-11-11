"""Selected prospective readout kernels; numerical dependencies are lazy.

This module neither opens study inputs nor grants authority to use them. Its
array snapshots have explicit coordinates; query EEG is not a model operand.
Owner reservations are cumulative logical allocation charges, not measured
native memory/CPU enforcement. A separately qualified process must supply that.
Original recording-level artifact/ICA processing is not claimed TRAIN-only.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType

from .splits import PERSONS, VIDEO_IDS

TARGET_SHAPE = (127, 150)
ALPHAS = tuple(10.0 ** exponent for exponent in range(-6, 7))
ARMS = MappingProxyType({
    "eye_only": ("eye",),
    "nuisance": ("matched_static", "motion", "acoustic", "timing", "silence"),
    "nuisance_eye": ("matched_static", "motion", "acoustic", "timing", "silence", "eye"),
    "nuisance_dynamic": ("matched_static", "motion", "acoustic", "timing", "silence", "learned_video"),
    "full": ("matched_static", "motion", "acoustic", "timing", "silence", "eye", "learned_video"),
})
ALL_ARMS = ("training_mean", *ARMS, "full_reverse")
SHARED = ("matched_static", "motion", "acoustic", "silence", "learned_video", "learned_video_reversed")
BLOCKS = ("matched_static", "motion", "acoustic", "timing", "silence", "eye", "learned_video")
LEARNED = ("matched_static", "learned_video")
SMALL_SHARED = ("motion", "acoustic", "silence")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def reserve_array(owner, shape, *, itemsize=8, copies=1):
    """Charge before explicit allocations; native workspace needs external caps."""
    size = 1
    for width in shape:
        need(type(width) is int and width >= 0, "Nonnegative explicit array extent")
        size *= width
    owner.reserve("retained_bytes", size * itemsize * copies)


def array_identity(array):
    """Hash exact contiguous values without an unbounded temporary byte string."""
    need(array.flags.c_contiguous and not array.dtype.hasobject, "Contiguous primitive identity")
    header = {"dtype": array.dtype.str, "shape": list(array.shape), "order": "C"}
    digest = hashlib.sha256(json.dumps(header, sort_keys=True, separators=(",", ":")).encode())
    digest.update(b"\n")
    digest.update(memoryview(array).cast("B"))
    return {**header, "value_bytes": int(array.nbytes), "value_sha256": digest.hexdigest()}


def _snapshot(value, shape, owner):
    import numpy as np
    need(type(value) is np.ndarray and value.dtype.kind in "fiu" and not value.dtype.hasobject,
         "Primitive numerical ndarray required")
    need(value.shape == shape and value.flags.c_contiguous, "Exact contiguous supplied shape")
    reserve_array(owner, shape, copies=2)
    result = np.array(value, dtype=np.float64, order="C", copy=True)
    need(np.isfinite(result).all(), "All source coordinates must be finite")
    # Immutable bytes backing prevents a caller from re-enabling writeability.
    payload = result.tobytes(order="C")
    del result
    return np.frombuffer(payload, dtype=np.float64).reshape(shape)


@dataclass(frozen=True)
class FeaturePool:
    video_ids: tuple[int, ...]
    personal_coordinates: tuple[tuple[str, int], ...]
    shared: object
    personal: object
    identities: object


@dataclass(frozen=True)
class StreamFeaturePool(FeaturePool):
    stream: object
    stream_selection_sha256: str


@dataclass(frozen=True)
class TrainingTargets:
    coordinates: tuple[tuple[str, int], ...]
    values: object
    identity: object


def _coordinates(coordinates):
    need(type(coordinates) is tuple and bool(coordinates), "Explicit nonempty coordinate tuple")
    need(all(type(row) is tuple and len(row) == 2 and row[0] in PERSONS and
             type(row[1]) is int and row[1] in VIDEO_IDS for row in coordinates),
         "Canonical person/video coordinates")
    need(len(set(coordinates)) == len(coordinates), "No repeated person/video coordinates")
    return coordinates


def capture_training_targets(coordinates, values, owner):
    """Snapshot ONLY one case's explicit outer FIT targets, in original EEG units."""
    rec = owner.begin("snapshot_outer_fit_targets")
    result = None
    try:
        coordinates = _coordinates(coordinates)
        array = _snapshot(values, (len(coordinates), *TARGET_SHAPE), owner)
        result = TrainingTargets(coordinates, array, MappingProxyType(array_identity(array)))
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def _capture_shared(shared, owner):
    import numpy as np
    need(type(shared) is dict and set(shared) == set(SHARED), "Complete fixed shared feature groups")
    arrays, identities = {}, {}
    for name in SHARED:
        value = shared[name]
        need(type(value) is np.ndarray and value.ndim == 2 and value.shape[1] > 0,
             "Nonempty complete shared block: " + name)
        arrays[name] = _snapshot(value, (1102, int(value.shape[1])), owner)
        identities[name] = array_identity(arrays[name])
    need(arrays["matched_static"].shape == arrays["learned_video"].shape ==
         arrays["learned_video_reversed"].shape == (1102, 15029136),
         "Complete selected seventeen-node S3D activation width; no pooling")
    need(arrays["motion"].shape[1] == 30 * 8 * 8 * 8, "Complete selected motion block")
    need(arrays["acoustic"].shape[1] == 300 * 64 + 30 + 30, "Complete selected acoustic block")
    silence = arrays["silence"]
    need(silence.shape == (1102, 1) and np.all((silence == 0) | (silence == 1)) and
         int(silence.sum()) == 34, "Complete independently joined 34-video silence branch")
    need(np.all(arrays["acoustic"][silence[:, 0] == 1] == 0), "Confirmed silent acoustic values must be zero")
    return arrays, identities


def _capture_personal(eye_value, timing_value, video_ids, owner):
    import numpy as np
    count = len(video_ids)
    eye = _snapshot(eye_value, (count, 150, 8), owner)
    reserve_array(owner, (count, 150, 12), copies=2)
    expanded = np.empty((count, 150, 12), dtype=np.float64)
    expanded[:, :, :8] = eye
    expanded[:, :, 8:11] = eye[:, :, :3] ** 2
    expanded[:, :, 11] = eye[:, :, 0] * eye[:, :, 1]
    need(np.isfinite(expanded).all(), "Finite prespecified nonlinear ocular features")
    expanded = np.frombuffer(expanded.tobytes(order="C"), dtype=np.float64).reshape(count, 1800)
    timing = _snapshot(timing_value, (count, 26), owner)
    row = MappingProxyType({"raw_eye": eye, "eye": expanded, "timing": timing,
                            "video_ids": video_ids,
                            "index": MappingProxyType({v: i for i, v in enumerate(video_ids)})})
    identities = {"eye_source": array_identity(eye), "eye": array_identity(expanded),
                  "timing": array_identity(timing)}
    return row, identities


def capture_feature_pool(shared, personal, owner, *, video_ids=VIDEO_IDS):
    """Operator-only full input snapshot; no callback or target covariates.

    shared has all six SHARED keys, each (1102,width). personal has exactly six
    persons, each with eye (1102,150,8) and timing (1102,26). Eye order is gaze
    x/y/pupil, their absolute adjacent-sample derivatives, observed/pair fractions.
    Fixed nonlinear terms are x^2,y^2,pupil^2,x*y per bin. The outer worker uses
    capture_case_features instead, so unrelated personal rows are never exposed.
    """
    rec = owner.begin("snapshot_feature_pool")
    result = None
    try:
        need(video_ids == VIDEO_IDS and type(video_ids) is tuple, "Complete ordered 1102 identities")
        need(type(personal) is dict and set(personal) == set(PERSONS), "All six personal feature groups")
        captured_shared, identities = _capture_shared(shared, owner)
        captured_personal = {}
        for person in PERSONS:
            row = personal[person]
            need(type(row) is dict and set(row) == {"eye", "timing"}, "Closed personal feature groups")
            captured_personal[person], identities[person] = _capture_personal(
                row["eye"], row["timing"], VIDEO_IDS, owner)
        coordinates = tuple((person, video) for person in PERSONS for video in VIDEO_IDS)
        result = FeaturePool(video_ids, coordinates, MappingProxyType(captured_shared),
                             MappingProxyType(captured_personal), MappingProxyType(identities))
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def capture_case_features(plan, case, shared, personal_coordinates, eye, timing, owner):
    """Snapshot exactly outer TRAIN+QUERY ocular/timing rows, with no EEG."""
    import numpy as np
    from .splits import validate_outer_case
    rec = owner.begin("snapshot_case_features")
    result = None
    try:
        validate_outer_case(plan, case)
        expected = tuple(case.training_coordinates()) + tuple(case.query_coordinates())
        need(personal_coordinates == expected and type(personal_coordinates) is tuple,
             "Exact ordered outer TRAIN+QUERY personal features")
        eye = _snapshot(eye, (len(expected), 150, 8), owner)
        timing = _snapshot(timing, (len(expected), 26), owner)
        captured_shared, identities = _capture_shared(shared, owner)
        captured_personal = {}
        for person in PERSONS:
            positions = [i for i, coordinate in enumerate(expected) if coordinate[0] == person]
            videos = tuple(expected[i][1] for i in positions)
            reserve_array(owner, (len(positions), 150 * 8 + 26))
            raw_eye = np.ascontiguousarray(eye[positions])
            raw_timing = np.ascontiguousarray(timing[positions])
            captured_personal[person], identities[person] = _capture_personal(raw_eye, raw_timing, videos, owner)
        result = FeaturePool(VIDEO_IDS, expected, MappingProxyType(captured_shared),
                             MappingProxyType(captured_personal), MappingProxyType(identities))
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def restrict_case_features(pool, plan, case, owner):
    """Operator-side scoping; share immutable stimulus blocks, copy permitted rows."""
    import numpy as np
    from .splits import validate_outer_case
    rec = owner.begin("restrict_case_features")
    result = None
    try:
        validate_outer_case(plan, case)
        check_feature_pool(pool)
        expected = tuple(case.training_coordinates()) + tuple(case.query_coordinates())
        personal, identities = {}, {name: pool.identities[name] for name in SHARED}
        for person in PERSONS:
            videos = tuple(video for p, video in expected if p == person)
            row = pool.personal[person]
            need(all(video in row["index"] for video in videos), "Every scoped personal row must exist")
            indices = [row["index"][video] for video in videos]
            reserve_array(owner, (len(indices), 150 * 8 + 26))
            eye = np.ascontiguousarray(row["raw_eye"][indices])
            timing = np.ascontiguousarray(row["timing"][indices])
            personal[person], identities[person] = _capture_personal(eye, timing, videos, owner)
        result = FeaturePool(VIDEO_IDS, expected, pool.shared, MappingProxyType(personal), MappingProxyType(identities))
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def capture_stream_case_features(plan, case, stream, personal_coordinates, eye, timing, owner):
    """Explicit streamed backend, retaining only allowed personal and small blocks."""
    import numpy as np
    from .feature_stream import ActualFeatureStream
    from .splits import validate_outer_case
    rec = owner.begin("snapshot_streamed_case_features")
    result = None
    try:
        validate_outer_case(plan, case)
        need(type(stream) is ActualFeatureStream, "Concrete selected feature producer, never a callback")
        selection_sha = stream.check_selection()
        expected = tuple(case.training_coordinates()) + tuple(case.query_coordinates())
        need(personal_coordinates == expected and type(personal_coordinates) is tuple,
             "Exact ordered outer TRAIN+QUERY personal features")
        eye = _snapshot(eye, (len(expected), 150, 8), owner)
        timing = _snapshot(timing, (len(expected), 26), owner)
        shared, personal, identities = {}, {}, {}
        for name, width in (("motion", 15360), ("acoustic", 19260), ("silence", 1)):
            reserve_array(owner, (1102, width), copies=2)
            values = np.empty((1102, width), dtype=np.float64)
            for start in range(0, width, stream.spec.column_width):
                stop = min(width, start + stream.spec.column_width)
                block = stream.columns(name, start, stop, owner)
                need(block.shape == (1102, stop - start) and np.isfinite(block).all(),
                     "Complete actual feature column block")
                values[:, start:stop] = block
            values = np.frombuffer(values.tobytes(order="C"), dtype=np.float64).reshape(1102, width)
            shared[name] = values
            identities[name] = array_identity(values)
        silence = shared["silence"]
        need(np.all((silence == 0) | (silence == 1)) and int(silence.sum()) == 34 and
             np.all(shared["acoustic"][silence[:, 0] == 1] == 0),
             "Complete joined no-playback branch, not missing-audio imputation")
        for person in PERSONS:
            positions = [i for i, coordinate in enumerate(expected) if coordinate[0] == person]
            videos = tuple(expected[i][1] for i in positions)
            reserve_array(owner, (len(positions), 150 * 8 + 26))
            personal[person], identities[person] = _capture_personal(
                np.ascontiguousarray(eye[positions]), np.ascontiguousarray(timing[positions]), videos, owner)
        identities["stream"] = {"selection_sha256": selection_sha, "first_actual_pass": stream.completed_baseline}
        result = StreamFeaturePool(VIDEO_IDS, expected, MappingProxyType(shared),
                                   MappingProxyType(personal), MappingProxyType(identities),
                                   stream, selection_sha)
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def check_feature_pool(pool):
    need(type(pool) in (FeaturePool, StreamFeaturePool) and pool.video_ids == VIDEO_IDS, "Captured complete feature pool")
    shared_names = SMALL_SHARED if type(pool) is StreamFeaturePool else SHARED
    if type(pool) is StreamFeaturePool:
        from .feature_stream import ActualFeatureStream
        need(type(pool.stream) is ActualFeatureStream and
             pool.stream.check_selection() == pool.stream_selection_sha256, "Unchanged concrete stream selection")
    need(set(pool.shared) == set(shared_names) and set(pool.personal) == set(PERSONS), "Closed captured feature support")
    _coordinates(pool.personal_coordinates)
    need(set(pool.personal_coordinates) == {(person, video) for person in PERSONS
         for video in pool.personal[person]["video_ids"]}, "Exact captured personal row map")
    for name in shared_names:
        array = pool.shared[name]
        need(not array.flags.writeable and array.flags.c_contiguous and
             array_identity(array) == pool.identities[name], "Captured shared values changed: " + name)
    for person in PERSONS:
        row = pool.personal[person]
        need(dict(row["index"]) == {video: index for index, video in enumerate(row["video_ids"])},
             "Unchanged captured personal coordinate index")
        for name in ("raw_eye", "eye", "timing"):
            array = pool.personal[person][name]
            need(not array.flags.writeable and array.flags.c_contiguous and
                 array_identity(array) == pool.identities[person]["eye_source" if name == "raw_eye" else name],
                 "Captured personal values changed")


def target_rows(targets, coordinates, owner):
    import numpy as np
    need(type(targets) is TrainingTargets and not targets.values.flags.writeable and
         array_identity(targets.values) == targets.identity, "Captured outer FIT values changed")
    coordinates = _coordinates(coordinates)
    positions = {coordinate: index for index, coordinate in enumerate(targets.coordinates)}
    need(all(coordinate in positions for coordinate in coordinates), "Query target or unknown target request refused")
    reserve_array(owner, (len(coordinates), *TARGET_SHAPE))
    result = np.ascontiguousarray(targets.values[[positions[c] for c in coordinates]])
    return result.reshape(len(coordinates), 127 * 150)


def family_weights(plan, coordinates, owner):
    import numpy as np
    coordinates = _coordinates(coordinates)
    family = {video: item.component_sha256 for item in plan.components for video in item.video_ids}
    counts = {}
    for person, video in coordinates:
        key = (person, family[video])
        counts[key] = counts.get(key, 0) + 1
    persons = tuple(sorted({person for person, _ in coordinates}))
    families = {person: {key[1] for key in counts if key[0] == person} for person in persons}
    reserve_array(owner, (len(coordinates),))
    result = np.array([1.0 / (len(persons) * len(families[person]) * counts[(person, family[video])])
                       for person, video in coordinates], dtype=np.float64)
    need(np.isfinite(result).all() and np.all(result > 0), "Positive complete family weights")
    result /= result.sum()
    result.setflags(write=False)
    return result


@dataclass(frozen=True)
class TargetScale:
    mean: object
    sigma: object


def fit_target_scale(raw_targets, weights, owner):
    import numpy as np
    need(raw_targets.ndim == 2 and raw_targets.shape[1] == 127 * 150 and
         raw_targets.shape[0] == len(weights), "Complete target fit basis")
    reserve_array(owner, tuple(map(int, raw_targets.shape)), copies=3)
    reserve_array(owner, (127 * 150,), copies=3)
    mean = weights @ raw_targets
    centered = raw_targets - mean
    sigma = np.sqrt(weights @ (centered ** 2))
    constant = np.all(raw_targets == raw_targets[0], axis=0)
    need(not constant.any() and np.isfinite(mean).all() and np.isfinite(sigma).all() and
         np.all(sigma > 0), "Undefined or constant target coordinate makes full case unavailable")
    mean.setflags(write=False)
    sigma.setflags(write=False)
    standardized = centered / sigma
    need(np.isfinite(standardized).all(), "Finite full standardized target matrix")
    return TargetScale(mean, sigma), standardized


@dataclass(frozen=True)
class BlockTransform:
    name: str
    mean: object
    scale: object
    constant: object
    pca_mean: object
    components: object
    output_width: int
    fit_support: tuple


@dataclass(frozen=True)
class StreamBlockTransform:
    name: str
    scores: object
    reversed_scores: object
    output_width: int
    fit_support: tuple
    state_document: object
    state_descriptor: object


def block_rows(pool, name, coordinates, owner, *, reverse=False):
    import numpy as np
    coordinates = _coordinates(coordinates)
    need(name in BLOCKS and (not reverse or name == "learned_video"), "Selected feature block only")
    if name in ("eye", "timing"):
        width = int(pool.personal[coordinates[0][0]][name].shape[1])
        reserve_array(owner, (len(coordinates), width))
        values = np.empty((len(coordinates), width), dtype=np.float64)
        for index, (person, video) in enumerate(coordinates):
            row = pool.personal[person]
            need(video in row["index"], "Personal feature row outside the permitted case")
            values[index] = row[name][row["index"][video]]
        return values
    source_name = "learned_video_reversed" if reverse else name
    array = pool.shared[source_name]
    reserve_array(owner, (len(coordinates), int(array.shape[1])))
    return np.ascontiguousarray(array[[video - 1 for _, video in coordinates]])


def fit_block(pool, name, coordinates, owner, *, writer=None, prefix=None):
    import numpy as np
    coordinates = _coordinates(coordinates)
    if type(pool) is StreamFeaturePool and name in LEARNED:
        from . import dual
        need(writer is not None and writer.owner is owner and type(prefix) is str,
             "Streamed PCA requires the concrete captured-state writer and prefix")
        videos = tuple(sorted({video for _, video in coordinates}))
        result = dual.fit(pool.stream, name, videos, VIDEO_IDS, owner, writer, prefix)
        need(result.video_ids == VIDEO_IDS and result.train_video_ids == videos and
             result.scores.shape == (1102, result.output_width), "Complete actual TRAIN-fitted PCA scores")
        scores = _snapshot(result.scores, (1102, result.output_width), owner)
        reverse_scores = None if result.reversed_scores is None else _snapshot(
            result.reversed_scores, (1102, result.output_width), owner)
        return StreamBlockTransform(name, scores, reverse_scores, result.output_width,
                                    tuple(("shared_video", video) for video in videos),
                                    result.state_document, result.state)
    if name in ("eye", "timing"):
        support = coordinates
    else:
        # A shared stimulus appears exactly once in its fitted scaler/PCA.
        videos = tuple(sorted({video for _, video in coordinates}))
        support = tuple(("shared_video", video) for video in videos)
    source_coordinates = coordinates if name in ("eye", "timing") else tuple((PERSONS[0], video) for _, video in support)
    values = block_rows(pool, name, source_coordinates, owner)
    width = int(values.shape[1])
    reserve_array(owner, tuple(map(int, values.shape)), copies=4)
    reserve_array(owner, (width,), copies=5)
    mean = values.mean(axis=0)
    constant = np.all(values == values[0], axis=0)
    scale = np.sqrt(np.mean((values - mean) ** 2, axis=0))
    need(np.isfinite(mean).all() and np.isfinite(scale).all() and
         np.all(scale[~constant] > 0), "Finite nonconstant feature scale required")
    scale[constant] = 1.0
    standardized = (values - mean) / scale
    standardized[:, constant] = 0.0
    pca_mean, components, output_width = None, None, width
    if name in LEARNED:
        pca_mean = standardized.mean(axis=0)
        centered = standardized - pca_mean
        rank_bound = min(centered.shape)
        reserve_array(owner, (rank_bound, width), copies=2)
        reserve_array(owner, (int(centered.shape[0]), rank_bound))
        _, singular_values, right = np.linalg.svd(centered, full_matrices=False)
        variance = singular_values ** 2
        total = variance.sum()
        need(np.isfinite(total) and total > 0, "Undefined learned PCA variance makes arm unavailable")
        output_width = min(len(variance), int(np.searchsorted(np.cumsum(variance) / total, 0.95, side="right")) + 1)
        components = np.ascontiguousarray(right[:output_width])
        # SVD signs are numerically arbitrary; canonicalize by largest loading,
        # with NumPy argmax's first-index rule for ties.
        signs = np.sign(components[np.arange(output_width), np.argmax(np.abs(components), axis=1)])
        signs[signs == 0] = 1.0
        components *= signs[:, None]
    for array in (mean, scale, constant, pca_mean, components):
        if array is not None:
            array.setflags(write=False)
    return BlockTransform(name, mean, scale, constant, pca_mean, components, output_width, support)


def fit_transforms(pool, coordinates, owner, *, writer=None, prefix=None):
    rec = owner.begin("fit_all_feature_transforms")
    result = None
    try:
        result = MappingProxyType({
            name: fit_block(pool, name, coordinates, owner, writer=writer,
                            prefix=None if prefix is None else prefix + "." + name + ".dual")
            for name in BLOCKS})
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def transform_block(pool, transform, coordinates, owner, *, reverse=False):
    import numpy as np
    if type(transform) is StreamBlockTransform:
        coordinates = _coordinates(coordinates)
        source = transform.reversed_scores if reverse else transform.scores
        need(source is not None and (not reverse or transform.name == "learned_video"),
             "Same fitted chronological PCA basis for reversal")
        reserve_array(owner, (len(coordinates), transform.output_width), copies=2)
        values = np.ascontiguousarray(source[[video - 1 for _, video in coordinates]])
        values /= np.sqrt(transform.output_width)
        need(np.isfinite(values).all(), "Complete finite captured PCA scores")
        return values
    values = block_rows(pool, transform.name, coordinates, owner, reverse=reverse)
    reserve_array(owner, tuple(map(int, values.shape)), copies=2)
    values = (values - transform.mean) / transform.scale
    values[:, transform.constant] = 0.0
    if transform.components is not None:
        reserve_array(owner, (len(coordinates), transform.output_width))
        values = (values - transform.pca_mean) @ transform.components.T
    values /= np.sqrt(transform.output_width)
    need(np.isfinite(values).all(), "Finite transform on every supplied coordinate")
    return values


def design(pool, transforms, arm, coordinates, owner, *, reverse=False):
    import numpy as np
    need(arm in ARMS and (not reverse or arm == "full"), "Fixed selected arm")
    groups = ARMS[arm]
    width = sum(transforms[name].output_width for name in groups)
    reserve_array(owner, (len(coordinates), width), copies=2)
    result = np.empty((len(coordinates), width), dtype=np.float64)
    offset = 0
    for name in groups:
        block = transform_block(pool, transforms[name], coordinates, owner,
                                reverse=reverse and name == "learned_video")
        result[:, offset:offset + block.shape[1]] = block
        offset += block.shape[1]
    result /= np.sqrt(len(groups))
    return result


@dataclass(frozen=True)
class RidgePreparation:
    weighted_design: object
    design_mean: object
    target_mean: object
    weighted_targets: object
    gram: object
    target_scale: TargetScale


@dataclass(frozen=True)
class RidgeModel:
    preparation: RidgePreparation
    alpha: float
    dual: object


def prepare_ridge(design_matrix, standardized_targets, weights, target_scale, owner):
    import numpy as np
    nrows, width = map(int, design_matrix.shape)
    need(standardized_targets.shape == (nrows, 127 * 150) and weights.shape == (nrows,), "Aligned complete ridge support")
    reserve_array(owner, (nrows, width), copies=2)
    reserve_array(owner, (nrows, 127 * 150), copies=2)
    reserve_array(owner, (nrows, nrows))
    reserve_array(owner, (width + 127 * 150 + nrows,), copies=2)
    design_mean = weights @ design_matrix
    target_mean = weights @ standardized_targets
    root_weights = np.sqrt(weights)
    weighted_design = (design_matrix - design_mean) * root_weights[:, None]
    weighted_targets = (standardized_targets - target_mean) * root_weights[:, None]
    gram = weighted_design @ weighted_design.T
    need(all(np.isfinite(array).all() for array in (weighted_design, weighted_targets, gram)), "Finite complete weighted ridge preparation")
    for array in (weighted_design, design_mean, target_mean, weighted_targets, gram):
        array.setflags(write=False)
    return RidgePreparation(weighted_design, design_mean, target_mean, weighted_targets, gram, target_scale)


def fit_ridge(preparation, alpha, owner):
    """One actual complete multioutput weighted ridge fit, including intercept."""
    import numpy as np
    rec = owner.begin("fit_ridge_alpha:" + str(alpha))
    result = None
    try:
        need(alpha in ALPHAS, "Selected thirteen-value alpha grid")
        nrows = int(preparation.gram.shape[0])
        reserve_array(owner, (nrows, nrows), copies=2)
        reserve_array(owner, (nrows, 127 * 150), copies=2)
        matrix = np.array(preparation.gram, order="C", copy=True)
        matrix.flat[::nrows + 1] += alpha
        dual = np.ascontiguousarray(np.linalg.solve(matrix, preparation.weighted_targets))
        need(np.isfinite(dual).all(), "Every ridge output must have a finite fitted solution")
        dual.setflags(write=False)
        result = RidgeModel(preparation, float(alpha), dual)
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def predict_original(model, query_design, owner):
    """Return (n,127,150) ORIGINAL EEG units, not standardized predictions."""
    import numpy as np
    preparation = model.preparation
    rows, width = map(int, query_design.shape)
    need(width == preparation.weighted_design.shape[1], "Same fitted feature basis")
    reserve_array(owner, (rows, width))
    reserve_array(owner, (rows, int(model.dual.shape[0])))
    reserve_array(owner, (rows, 127 * 150), copies=3)
    cross = (query_design - preparation.design_mean) @ preparation.weighted_design.T
    standardized = cross @ model.dual + preparation.target_mean
    result = standardized * preparation.target_scale.sigma + preparation.target_scale.mean
    need(np.isfinite(result).all(), "Finite original-unit prediction for every output")
    return np.ascontiguousarray(result.reshape(rows, *TARGET_SHAPE))


def video_losses(original_prediction, raw_targets, scale, owner):
    """Inner selection loss: divide ORIGINAL-unit residual by FIT sigma ONCE."""
    import numpy as np
    expected = (int(raw_targets.shape[0]), 127 * 150)
    need(original_prediction.shape == (expected[0], *TARGET_SHAPE) and raw_targets.shape == expected,
         "Exact complete validation prediction/target support")
    reserve_array(owner, expected, copies=3)
    residual = (raw_targets - original_prediction.reshape(expected)) / scale.sigma
    loss = np.mean(residual ** 2, axis=1)
    need(np.isfinite(loss).all(), "Every validation video loss must be finite")
    return np.ascontiguousarray(loss)


def capture_target_scale(scale, writer, prefix):
    return {"mean": writer.array(prefix + ".target_mean.npy", scale.mean.reshape(TARGET_SHAPE)),
            "sigma": writer.array(prefix + ".target_sigma.npy", scale.sigma.reshape(TARGET_SHAPE)),
            "units": "original_eeg", "scorer_residual_sigma_divisions": 1}


def capture_transforms(transforms, writer, prefix):
    result = {}
    for name in BLOCKS:
        transform = transforms[name]
        if type(transform) is StreamBlockTransform:
            state = transform.state_document
            result[name] = {
                "backend": "streamed_dual_certified",
                "fit_support": [list(row) for row in transform.fit_support],
                "input_width": state["input_width"], "output_width": transform.output_width,
                "video_ids": list(VIDEO_IDS), "scores": state["scores"],
                "reversed_scores": state["reversed_scores"],
                "stream_spec_sha256": state["stream_spec_sha256"],
                "audit_state_identity": transform.state_descriptor,
                "certificate_identity": state["certificate"],
                "qualification": state["qualification"],
                "retention": "Actual PC-score bodies; fitted column-stat hashes and metered regeneration in audit state. Column-stat bodies not retained."
            }
            continue
        base = prefix + "." + name
        reserve_array(writer.owner, (len(transform.constant),))
        constant_body = transform.constant.astype("float64")
        state = {"fit_support": [list(item) for item in transform.fit_support],
                 "input_width": len(transform.mean), "output_width": transform.output_width,
                 "constant_encoding": "float64_0_or_1",
                 "mean": writer.array(base + ".mean.npy", transform.mean),
                 "scale": writer.array(base + ".scale.npy", transform.scale),
                 "constant": writer.array(base + ".constant.npy", constant_body),
                 "pca_mean": None, "pca_components": None}
        if transform.components is not None:
            state["pca_mean"] = writer.array(base + ".pca_mean.npy", transform.pca_mean)
            state["pca_components"] = writer.array(base + ".pca_components.npy", transform.components)
        result[name] = state
    return result


def capture_preparation(preparation, writer, prefix):
    return {name: writer.array(prefix + "." + name + ".npy", getattr(preparation, name))
            for name in ("weighted_design", "design_mean", "target_mean", "weighted_targets", "gram")}


def capture_model(model, writer, prefix, preparation_descriptor):
    return {"alpha": model.alpha, "preparation": preparation_descriptor,
            "solver": "numpy.linalg.solve(weighted_centered_gram + alpha*I, weighted_centered_standardized_targets)",
            "dual": writer.array(prefix + ".dual.npy", model.dual), "prediction_units": "original_eeg"}


@dataclass(frozen=True)
class SuppliedDecoder:
    case_id: str
    assignment_sha256: str
    transforms: object
    model: RidgeModel
    fit_coordinates: tuple
    manifest_identity: object


def capture_decoder(model, transform_state, target_scale_descriptor, preparation_state,
                    plan, case, writer, prefix):
    """Retain only the fixed FULL fitted decoder closure, never query outputs."""
    need(model.alpha in ALPHAS and tuple(case.training_coordinates()),
         "Selected full fitted decoder")
    document = {
        "schema": "neural080_full_decoder_v1", "case_id": case.case_id,
        "assignment_sha256": plan.assignment_sha256,
        "fit_coordinates": [list(row) for row in case.training_coordinates()],
        "groups": list(ARMS["full"]), "alpha": model.alpha, "units": "original_eeg",
        "feature_backend": "streamed_dual_certified" if "backend" in transform_state["learned_video"] else "full_svd_materialized",
        "target_scale": target_scale_descriptor,
        "transforms": {name: transform_state[name] for name in ARMS["full"]},
        "model": {name: preparation_state[name]
                  for name in ("weighted_design", "design_mean", "target_mean")},
    }
    document["model"]["dual"] = writer.array(prefix + ".decoder_dual.npy", model.dual)
    return writer.document(prefix + ".FULL_DECODER.json", document)


def decoder_members(document):
    """Pure metadata allowlist for the minimal decoder's exact numeric closure.

    Generated filenames are fixed. Query EEG prediction filenames and unknown
    fields cannot enter this closure. Audit-state identities are provenance only;
    their bodies are retained in the reference archive, not copied as tool inputs.
    """
    from pathlib import PurePosixPath
    top = {"schema", "case_id", "assignment_sha256", "fit_coordinates", "groups",
           "alpha", "units", "feature_backend", "target_scale", "transforms", "model"}
    need(type(document) is dict and set(document) == top, "Closed supplied decoder document")
    case_id = document["case_id"]
    need(type(case_id) is str and case_id in {f"{person}.family-{fold}" for person in PERSONS for fold in range(5)},
         "Canonical decoder case")
    need(document["schema"] == "neural080_full_decoder_v1" and document["units"] == "original_eeg" and
         document["groups"] == list(ARMS["full"]) and type(document["alpha"]) in (int, float) and
         document["alpha"] in ALPHAS and document["feature_backend"] in
         ("full_svd_materialized", "streamed_dual_certified"), "Exact selected decoder recipe")
    coords = document["fit_coordinates"]
    need(type(coords) is list and bool(coords) and
         all(type(row) is list and len(row) == 2 for row in coords), "Closed decoder TRAIN coordinates")
    coordinate_tuple = _coordinates(tuple(tuple(row) for row in coords))
    held_person = case_id.split(".family-")[0]
    persons = tuple(person for person in PERSONS if person != held_person)
    videos = tuple(video for person, video in coordinate_tuple if person == persons[0])
    need(videos == tuple(sorted(set(videos))) and 0 < len(videos) < 1102 and
         coordinate_tuple == tuple((person, video) for person in persons for video in videos),
         "Complete crossed TRAIN-only personal support")
    need(type(document["assignment_sha256"]) is str and len(document["assignment_sha256"]) == 64 and
         all(char in "0123456789abcdef" for char in document["assignment_sha256"]), "Exact family assignment identity")
    members, seen = [], set()

    def member(row, expected_path, shape):
        need(type(row) is dict and set(row) == {"path", "bytes", "sha256"} and
             row["path"] == expected_path and PurePosixPath(expected_path).name == expected_path and
             expected_path not in seen, "Only exact distinct generated decoder state names")
        size = 1
        for extent in shape:
            need(type(extent) is int and extent > 0, "Positive expected decoder extent")
            size *= extent
        need(type(row["bytes"]) is int and 0 < row["bytes"] <= size * 8 + 4108 and
             type(row["sha256"]) is str and len(row["sha256"]) == 64 and
             all(char in "0123456789abcdef" for char in row["sha256"]), "Bounded exact decoder state descriptor")
        seen.add(expected_path)
        members.append((dict(row), shape))

    transforms = document["transforms"]
    need(type(transforms) is dict and set(transforms) == set(ARMS["full"]), "All fixed FULL transforms")
    widths = {"matched_static": 15029136, "learned_video": 15029136, "motion": 15360,
              "acoustic": 19260, "timing": 26, "silence": 1, "eye": 1800}
    output_width = 0
    for name in ARMS["full"]:
        state = transforms[name]
        need(type(state) is dict, "Closed fitted transformation")
        width, out = state.get("input_width"), state.get("output_width")
        need(type(width) is int and width == widths[name] and type(out) is int and 0 < out <= width,
             "Exact selected feature dimensions")
        expected_support = coords if name in ("eye", "timing") else [["shared_video", video] for video in videos]
        need(state.get("fit_support") == expected_support, "Exact permitted scaler support")
        base = case_id + ".outer." + name
        if name in LEARNED and document["feature_backend"] == "streamed_dual_certified":
            need(set(state) == {"backend", "fit_support", "input_width", "output_width", "video_ids",
                 "scores", "reversed_scores", "stream_spec_sha256", "audit_state_identity", "certificate_identity",
                 "retention", "qualification"} and state["backend"] == "streamed_dual_certified" and
                 state["video_ids"] == list(VIDEO_IDS) and out <= len(videos), "Complete compact PCA state")
            need(type(state["stream_spec_sha256"]) is str and len(state["stream_spec_sha256"]) == 64 and
                 all(char in "0123456789abcdef" for char in state["stream_spec_sha256"]) and
                 state["qualification"] == "unqualified conditional arithmetic operands; no native or fullSVD equivalence issued" and
                 state["retention"] == "Actual PC-score bodies; fitted column-stat hashes and metered regeneration in audit state. Column-stat bodies not retained.",
                 "Exact retained source/arithmetic qualification disclosure")
            for key, suffix in (("audit_state_identity", ".DUAL_STATE.json"),
                                ("certificate_identity", ".certificate.json")):
                identity = state[key]
                need(type(identity) is dict and set(identity) == {"path", "bytes", "sha256"} and
                     identity["path"] == base + ".dual" + suffix and
                     type(identity["bytes"]) is int and 0 < identity["bytes"] < 2**63 and
                     type(identity["sha256"]) is str and len(identity["sha256"]) == 64 and
                     all(char in "0123456789abcdef" for char in identity["sha256"]),
                     "Closed audit identity only, never arbitrary payload or query output")
            # Dual's fixed output names are enforced here and in the producer.
            member(state["scores"], base + ".dual.scores.npy", (1102, out))
            if name == "learned_video":
                member(state["reversed_scores"], base + ".dual.reversed_scores.npy", (1102, out))
            else:
                need(state["reversed_scores"] is None, "No static reversal substitution")
        else:
            need(set(state) == {"fit_support", "input_width", "output_width", "constant_encoding",
                 "mean", "scale", "constant", "pca_mean", "pca_components"} and
                 state["constant_encoding"] == "float64_0_or_1", "Closed full fitted feature state")
            for key in ("mean", "scale", "constant"):
                member(state[key], base + "." + key + ".npy", (width,))
            if name in LEARNED:
                need(out <= len(videos), "Complete PCA score extent")
                member(state["pca_mean"], base + ".pca_mean.npy", (width,))
                member(state["pca_components"], base + ".pca_components.npy", (out, width))
            else:
                need(out == width and state["pca_mean"] is None and state["pca_components"] is None,
                     "No nonlearned column reduction")
        output_width += out
    scale = document["target_scale"]
    need(type(scale) is dict and set(scale) == {"mean", "sigma", "units", "scorer_residual_sigma_divisions"} and
         scale["units"] == "original_eeg" and type(scale["scorer_residual_sigma_divisions"]) is int and
         scale["scorer_residual_sigma_divisions"] == 1, "Exact original-unit target transform")
    member(scale["mean"], case_id + ".target_mean.npy", TARGET_SHAPE)
    member(scale["sigma"], case_id + ".target_sigma.npy", TARGET_SHAPE)
    state = document["model"]
    need(type(state) is dict and set(state) == {"weighted_design", "design_mean", "target_mean", "dual"},
         "Minimal fitted-state closure, without query EEG predictions")
    base = case_id + ".outer.full."
    rows = len(coordinate_tuple)
    for key, shape in (("weighted_design", (rows, output_width)), ("design_mean", (output_width,)),
                       ("target_mean", (127 * 150,)), ("dual", (rows, 127 * 150))):
        member(state[key], base + ("decoder_dual" if key == "dual" else key) + ".npy", shape)
    return tuple(row for row, _ in members)


def _decoder_spec(document, plan, case):
    from .splits import validate_outer_case
    validate_outer_case(plan, case)
    decoder_members(document)
    need(document["case_id"] == case.case_id and document["assignment_sha256"] == plan.assignment_sha256 and
         document["fit_coordinates"] == [list(row) for row in case.training_coordinates()],
         "Supplied decoder belongs to this exact outer TRAIN support")
    specifications, width_sum = [], 0
    for name in ARMS["full"]:
        state = document["transforms"][name]
        width, out = state["input_width"], state["output_width"]
        if state.get("backend") == "streamed_dual_certified":
            specifications.append((state["scores"], (1102, out)))
            if state["reversed_scores"] is not None:
                specifications.append((state["reversed_scores"], (1102, out)))
        else:
            for key in ("mean", "scale", "constant"):
                specifications.append((state[key], (width,)))
            if name in LEARNED:
                specifications.extend(((state["pca_mean"], (width,)), (state["pca_components"], (out, width))))
        width_sum += out
    scale = document["target_scale"]
    specifications.extend(((scale["mean"], TARGET_SHAPE), (scale["sigma"], TARGET_SHAPE)))
    state, rows = document["model"], len(tuple(case.training_coordinates()))
    specifications.extend(((state["weighted_design"], (rows, width_sum)), (state["design_mean"], (width_sum,)),
                           (state["target_mean"], (127 * 150,)), (state["dual"], (rows, 127 * 150))))
    return tuple(specifications)


def restore_decoder(document, captured_arrays, plan, case, owner, *, manifest_identity):
    """Restore already captured arrays; load_decoder provides the actual loader."""
    import numpy as np
    specifications = _decoder_spec(document, plan, case)
    need(type(captured_arrays) is dict and set(captured_arrays) ==
         {row["path"] for row, _ in specifications}, "Exactly the captured decoder closure")
    frozen = {}
    for row, shape in specifications:
        frozen[row["path"]] = _snapshot(captured_arrays[row["path"]], shape, owner)

    def array(row):
        return frozen[row["path"]]

    transforms = {}
    for name in ARMS["full"]:
        state = document["transforms"][name]
        if state.get("backend") == "streamed_dual_certified":
            transforms[name] = StreamBlockTransform(
                name, array(state["scores"]),
                None if state["reversed_scores"] is None else array(state["reversed_scores"]),
                state["output_width"], tuple(tuple(row) for row in state["fit_support"]),
                state, state["audit_state_identity"])
            continue
        mask_values = array(state["constant"])
        need(np.all((mask_values == 0) | (mask_values == 1)), "Exact binary constant-column mask")
        reserve_array(owner, (len(mask_values),), itemsize=1)
        constant = mask_values.astype(np.bool_)
        constant.setflags(write=False)
        scale = array(state["scale"])
        need(np.all(scale > 0) and np.all(scale[constant] == 1), "Exact finite positive fitted scaler")
        transforms[name] = BlockTransform(
            name, array(state["mean"]), scale, constant,
            None if state["pca_mean"] is None else array(state["pca_mean"]),
            None if state["pca_components"] is None else array(state["pca_components"]),
            state["output_width"], tuple(tuple(row) for row in state["fit_support"]))
    target_mean = array(document["target_scale"]["mean"]).reshape(127 * 150)
    target_sigma = array(document["target_scale"]["sigma"]).reshape(127 * 150)
    need(np.all(target_sigma > 0), "Every fitted target coordinate has positive TRAIN scale")
    target_scale = TargetScale(target_mean, target_sigma)
    state = document["model"]
    # Prediction uses only these fitted operands. Training-only targets and Gram
    # need not be copied into the supplied decoder's minimal inference closure.
    preparation = RidgePreparation(array(state["weighted_design"]), array(state["design_mean"]),
                                   array(state["target_mean"]), None, None, target_scale)
    model = RidgeModel(preparation, float(document["alpha"]), array(state["dual"]))
    return SuppliedDecoder(case.case_id, plan.assignment_sha256, MappingProxyType(transforms),
                           model, tuple(case.training_coordinates()), MappingProxyType(dict(manifest_identity)))


def load_decoder(root, descriptor, plan, case, owner):
    """Capture exact manifest/array bytes once, then decode those captured bodies."""
    from input_owner import capture
    from .artifacts import capture_array, decode_array
    rec = owner.begin("load_supplied_full_decoder")
    result = None
    try:
        body = capture(root, descriptor, owner, max_bytes=1_048_576)

        def unique_pairs(pairs):
            output = {}
            for key, value in pairs:
                need(key not in output, "Duplicate decoder document field")
                output[key] = value
            return output

        def reject_constant(value):
            raise ValueError("Nonfinite decoder JSON constant: " + value)

        document = json.loads(body, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
        specs = _decoder_spec(document, plan, case)
        arrays = {}
        for row, shape in specs:
            captured = capture_array(root, row, shape, owner)
            arrays[row["path"]] = decode_array(captured, shape, owner)
        result = restore_decoder(document, arrays, plan, case, owner, manifest_identity=descriptor)
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result


def predict_decoder_original(decoder, feature_pool, coordinates, owner):
    """Actual supplied decoder API; never refits or reads EEG."""
    need(type(decoder) is SuppliedDecoder, "Restored fixed supplied decoder")
    check_feature_pool(feature_pool)
    coordinates = _coordinates(coordinates)
    matrix = design(feature_pool, decoder.transforms, "full", coordinates, owner)
    return predict_original(decoder.model, matrix, owner)
