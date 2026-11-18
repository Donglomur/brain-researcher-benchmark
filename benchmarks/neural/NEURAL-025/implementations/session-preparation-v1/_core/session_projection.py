"""Sequential, exact-session value accessor over one authenticated open MAT.

The controller owns opening, one full hash/header pass, bounded HDF5 callbacks,
file stability, stage computation, output retention and process cleanup. This
module opens no path, imports no reader/runtime, performs no alignment or fit,
and neither closes nor replaces the shared original handle.
"""
import hashlib
import json
import math


SESSION = "cfa24_20220727_160603"
ORIGINAL_SHA256 = "f97834b22135ca1509be34913e29300dd4ebbcc52436173fb1cb63c9afdf29d0"
METADATA_BYTES = 834680
METADATA_SHA256 = "f8ad6940b5a7a6e092e69d5740283c6e03d4c8b04261968a15f7dd7e96ea18e8"
CHUNK_BYTES = 8388608


def make_session_projection(h5_file, admission, metadata, *, limits):
    """Build one accessor; numeric values are first read by read_trial().

    limits must exactly equal the six limits derived from the frozen metadata.
    The controller must pass the unchanged authenticated Mat73 admission module.
    Eligible trials must be requested once each, in original order. Any failed
    request poisons the accessor; there is no retry, skip or partial success.
    """
    return _SessionProjection(h5_file, admission, metadata, limits)


class _SessionProjection:
    def __init__(self, h5_file, admission, metadata, limits):
        self._a = admission
        self._np, self._h5py = admission.np, admission.h5py
        self._require = admission.require
        self._file = h5_file
        require = self._require
        require(type(metadata) is dict, "Frozen metadata object required")
        try:
            body = (json.dumps(metadata, sort_keys=True, separators=(",", ":"),
                               allow_nan=False) + "\n").encode("utf-8")
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("Metadata cannot be encoded in the frozen representation") from exc
        require(len(body) == METADATA_BYTES and
                hashlib.sha256(body).hexdigest() == METADATA_SHA256,
                "Exact complete authenticated metadata receipt required")
        # Keep a private snapshot; caller mutation cannot change future identity,
        # dimensions, eligibility, clocks or budgets after factory admission.
        self._metadata = json.loads(body)
        del body
        m = self._metadata
        require(m["session_id"] == SESSION and
                m["source_binding"]["sha256"] == ORIGINAL_SHA256 and
                m["source_binding"]["published_asset_verified"] is True,
                "Exact source session and original identity required")
        trials = m["trials"]
        census = m["complete_scalar_census"]
        require(len(trials) == 416 and len(census["ordered_original_trials"]) == 416,
                "All 416 original trial identities are required")
        eligible, excluded, plans, identities = [], [], {}, []
        for position, trial in enumerate(trials, 1):
            require(trial["raw_ordinal_one_based"] == position and
                    trial["original_trial_number"] == position and
                    trial["scalar_values"]["trialNumber"] == position and
                    trial["eligibility"] == census["ordered_original_trials"][position - 1] and
                    trial["eligibility"]["trial_number"] == position,
                    "Original ordinal/trial identity/census mismatch")
            selected = trial["eligible_clock_and_shape_inspection"]
            require(type(selected) is bool and
                    selected is trial["eligibility"]["eligible_by_loadLock4Decode"],
                    "Eligibility records disagree")
            identities.append((position, trial["original_trial_number"], selected))
            if not selected:
                excluded.append(position)
                continue
            eligible.append(position)
            require(trial["author_neural_lock_precondition"] is True and
                    trial["author_kinematic_lock_precondition"] is True and
                    trial["scalar_values"]["hasNeuralData"] is True and
                    trial["scalar_values"]["maxCams"] is True,
                    "Frozen eligible trial lacks required source preconditions")
            ev = tuple(trial["events"]["matlab_shape"])
            joint = tuple(trial["jointAngles"]["matlab_shape"])
            frame = tuple(trial["frame_clock"]["matlab_shape"])
            camera = tuple(trial["camera1_clock"]["matlab_shape"])
            require(len(ev) == 2 and ev[0] >= 2 and ev[1] == 565 and
                    len(joint) == 2 and joint[0] >= 2 and joint[1] == 24,
                    "Complete 565 ROI / 24 stored-angle shapes required")
            require(len(frame) == len(camera) == 2 and 1 in frame and 1 in camera and
                    math.prod(frame) == ev[0] == trial["frame_clock"]["count"] and
                    math.prod(camera) == joint[0] == trial["camera1_clock"]["count"],
                    "Recorded event/frame or joint/camera dimensions disagree")
            require(tuple(trial["posXYZ"]["matlab_shape"]) == (joint[0], 3, 25) and
                    trial["camera_count"] == 2,
                    "Frozen pose/camera metadata changed")
            require(trial["padded_neural_frame_bounds"]["within_events_rows"] is True and
                    trial["camera_event_bounds"]["covers_original101_grid"] is True,
                    "Frozen original preparation support required")
            for field, shape in (("events", ev), ("jointAngles", joint)):
                description = trial[field]
                require(description["elements"] == math.prod(shape) and
                        description["dtype"] == "float64" and
                        description["matlab_class"] == "double" and
                        description["values_read"] is False,
                        "Frozen numeric field description changed")
            numeric = math.prod(ev) + math.prod(joint) + math.prod(frame) + math.prod(camera) + 2
            plans[position] = {"events": ev, "joint_angles": joint,
                               "frame_times": frame, "camera_times": camera,
                               "numeric_elements": numeric,
                               "reference_elements": 6 * 416 + trial["camera_count"]}
        require(len(eligible) == 372 and len(excluded) == 44 and
                [trials[i - 1]["original_trial_number"] for i in eligible] ==
                census["selected_trial_numbers"], "Complete ordered 372/44 partition required")
        first_camera = m["first_eligible_max_cams"]
        first_neural = m["first_eligible_neural"]
        require(eligible[0] == 1 and
                first_camera["raw_ordinal_one_based"] == first_camera["original_trial_number"] == 1 and
                first_neural["raw_ordinal_one_based"] == first_neural["original_trial_number"] == 1 and
                first_neural["source_roi_columns"] == m["roi_metadata"]["roi_columns"] == 565 and
                first_camera["clock"] == trials[0]["camera1_clock"],
                "Original first-eligible reference identities changed")
        self._shared_step = first_camera["cam_time_base_ms"]
        require(type(self._shared_step) in (float, int) and
                math.isfinite(self._shared_step) and self._shared_step > 0 and
                self._shared_step == first_camera["clock"]["median_step_ms"],
                "Exact shared first-camera median required")
        shared_elements = m["roi_metadata"]["roi_columns"] + 1
        numeric_elements = shared_elements + sum(p["numeric_elements"] for p in plans.values())
        # Six original-R reference vectors and camera1's 2-camera vector are
        # conservatively charged each call. Scalar M may add at most two refs.
        derived = {
            "max_numeric_elements": numeric_elements,
            "max_reader_elements": numeric_elements + 2 + sum(p["reference_elements"] for p in plans.values()),
            "max_trial_numeric_elements": max(p["numeric_elements"] for p in plans.values()),
            "max_trials": len(trials),
            "max_eligible_trials": len(eligible),
            "max_decoded_chunk_bytes": CHUNK_BYTES,
        }
        require(type(limits) is dict and set(limits) == set(derived) and
                all(type(limits[k]) is int and limits[k] == value for k, value in derived.items()),
                "Limits must exactly equal the metadata-derived session limits")
        self._limits = dict(derived)
        self._plans, self._eligible, self._excluded = plans, tuple(eligible), tuple(excluded)
        self._identities = tuple(identities)
        self._shared_elements = shared_elements
        self._next = 0
        self._attempted = []
        self._completed = []
        self._failed = False
        self._failure = None
        self._numeric_reserved = 0
        self._numeric_finite_decoded = 0
        self._cache_ready = False
        self._lags = None
        self._cycle = None
        self._census_sha256 = admission.digest(census)

        parent = self
        class Guarded(admission.Mat73):
            def _class(self, node):
                parent._attribute(node, "MATLAB_class")
                return super()._class(node)

            def _charge(self, node):
                parent._storage(node)
                return super()._charge(node)

        self._reader = Guarded(h5_file, max_elements=derived["max_reader_elements"], max_records=416)

    def _attribute(self, node, name):
        require, h5py = self._require, self._h5py
        require(name in node.attrs, "Required MATLAB attribute missing")
        handle = node.attrs.get_id(name)
        space = None
        try:
            dtype = handle.dtype
            space = handle.get_space()
            count = space.get_simple_extent_npoints()
            require(h5py.check_dtype(vlen=dtype) is None and not dtype.fields and
                    0 < dtype.itemsize <= 256 and 0 < count <= 256 and
                    count * dtype.itemsize <= 256, "Unbounded MATLAB attribute")
            require(name != "MATLAB_class" or (dtype.kind == "S" and count == 1),
                    "Fixed ASCII MATLAB class required")
        finally:
            if space is not None:
                space.close()
            handle.close()

    def _storage(self, node):
        require, h5py = self._require, self._h5py
        require(isinstance(node, h5py.Dataset), "Dataset required")
        require(not node.is_virtual and not node.external, "Nonlocal dataset refused")
        ref = h5py.check_dtype(ref=node.dtype)
        require(ref is None or ref is h5py.Reference, "Region references refused")
        require(not node.dtype.fields and 0 < node.dtype.itemsize <= 8 and
                (ref is h5py.Reference or (h5py.check_dtype(vlen=node.dtype) is None and
                                         node.dtype.kind in "iufb")), "Unbounded dtype refused")
        plist = node.id.get_create_plist()
        try:
            require(plist.get_nfilters() <= 3 and
                    all(plist.get_filter(i)[0] in {1, 2, 3}
                        for i in range(plist.get_nfilters())), "Unreviewed HDF5 filters")
        finally:
            plist.close()
        require(node.chunks is None or math.prod(node.chunks) * node.dtype.itemsize <= CHUNK_BYTES,
                "Decoded chunk exceeds 8 MiB")
        require("MATLAB_empty" not in node.attrs, "MATLAB empty value-encoded shape refused")

    def _group(self, node):
        self._require(isinstance(node, self._h5py.Group) and self._reader._class(node) == "struct",
                      "MATLAB struct group required")
        return node

    def _selected(self, parent, name, expected_count, position_zero_based):
        require, h5py, reader = self._require, self._h5py, self._reader
        require(type(position_zero_based) is int and 0 <= position_zero_based < expected_count,
                "Explicit in-range original reference position required")
        node = reader._child(self._group(parent), name)
        if (isinstance(node, h5py.Dataset) and h5py.check_dtype(ref=node.dtype) is not None
                and "MATLAB_class" not in node.attrs):
            self._storage(node)
            require(node.ndim == 2 and 1 in node.shape and
                    math.prod(node.shape) == expected_count, "Exact source reference count required")
            # Same order as Mat73 node[()].T.reshape(-1, order='F'), but read
            # exactly one reference. Never materialize another trial's payload.
            reader._charge(node)
            coordinates = ((0, position_zero_based) if node.shape[0] == 1
                           else (position_zero_based, 0))
            ref = node[coordinates]
            reader._nonnull(ref)
            return self._file[ref]
        require(expected_count == 1 and position_zero_based == 0,
                "Reference field required for nonscalar original struct")
        return node

    def _value(self, node, name, shape):
        require, reader = self._require, self._reader
        self._storage(node)
        require(reader._class(node) == "double" and node.dtype.kind == "f" and
                node.dtype.itemsize == 8 and tuple(reversed(node.shape)) == shape,
                "Exact float64 MATLAB shape required before allocation: " + name)
        elements = math.prod(shape)
        require(self._numeric_reserved + elements <= self._limits["max_numeric_elements"],
                "Aggregate decoded numeric value budget exceeded")
        # Reserve the full declared allocation before calling the unchanged
        # reader. Failed reads keep their allowance; accounting becomes inexact.
        self._numeric_reserved += elements
        value = reader._leaf(node)
        require(value.shape == shape and bool(self._np.isfinite(value).all()),
                "Nonfinite or changed numeric projection: " + name)
        self._numeric_finite_decoded += elements
        return value

    def _load_shared(self):
        m = self._group(self._reader._child(self._file, "M"))
        lag_node = self._selected(m, "ROILags", 1, 0)
        lag_shape = tuple(reversed(lag_node.shape))
        self._require(lag_shape in {(1, 565), (565, 1)}, "Exact ROI vector shape required")
        lags = self._value(lag_node, "roi_lags", lag_shape).reshape(-1, order="F")
        cycle = float(self._value(self._selected(m, "cycleDurMs", 1, 0), "cycle_ms", (1, 1))[0, 0])
        expected = self._metadata["roi_metadata"]
        self._require(self._a.digest(lags.tolist()) == expected["roilags_sha256"] and
                      cycle == expected["cycle_duration_ms"], "Shared ROI/cycle binding mismatch")
        lags.setflags(write=False)
        self._lags, self._cycle = lags, cycle
        self._cache_ready = True

    def read_trial(self, ordinal_one_based):
        """Read the next eligible original ordinal, once; failure is terminal."""
        require = self._require
        require(not self._failed, "Accessor already failed; retry or skip is forbidden")
        try:
            require(type(ordinal_one_based) is int and
                    self._next < len(self._eligible) and
                    ordinal_one_based == self._eligible[self._next],
                    "Only the next eligible original ordinal may be read once")
            self._attempted.append(ordinal_one_based)
            original = self._metadata["trials"][ordinal_one_based - 1]
            plan = self._plans[ordinal_one_based]
            shared_need = 0 if self._cache_ready else self._shared_elements
            require(plan["numeric_elements"] <= self._limits["max_trial_numeric_elements"] and
                    self._numeric_reserved + shared_need + plan["numeric_elements"] <=
                    self._limits["max_numeric_elements"], "Trial value allocation exceeds declared limits")
            reader_need = plan["numeric_elements"] + plan["reference_elements"]
            if not self._cache_ready:
                reader_need += self._shared_elements + 2
            require(reader_need <= self._reader.remaining,
                    "Trial cannot fit remaining conservative reader budget")
            numeric_before, reader_before = self._numeric_reserved, self._reader.loaded
            if not self._cache_ready:
                self._load_shared()
            require(self._a.digest(self._lags.tolist()) == self._metadata["roi_metadata"]["roilags_sha256"],
                    "Cached ROI lags changed between trials")
            r = self._group(self._reader._child(self._file, "R"))
            position = ordinal_one_based - 1
            events = self._value(self._selected(r, "events", 416, position), "events", plan["events"])
            joints = self._value(self._selected(r, "jointAngles", 416, position), "joint_angles", plan["joint_angles"])
            frames = self._value(self._selected(r, "frameTimes", 416, position), "frame_times", plan["frame_times"]).reshape(-1, order="F")
            cam = self._group(self._selected(r, "cam", 416, position))
            camera = self._value(self._selected(cam, "times", original["camera_count"], 0),
                                 "camera_times", plan["camera_times"]).reshape(-1, order="F")
            sync = float(self._value(self._selected(r, "syncTime", 416, position), "sync_ms", (1, 1))[0, 0])
            lift = float(self._value(self._selected(r, "liftTimeDLC", 416, position), "lift_ms", (1, 1))[0, 0])
            require(self._a.digest(camera.tolist()) == original["camera1_clock"]["values_sha256"] and
                    self._a.digest(frames.tolist()) == original["frame_clock"]["values_sha256"],
                    "Reread clock values differ from authenticated per-trial metadata")
            require(sync == original["scalar_values"]["syncTime"] and
                    lift == original["scalar_values"]["liftTimeDLC"], "Reread scalar binding mismatch")
            added = self._numeric_reserved - numeric_before
            require(added == shared_need + plan["numeric_elements"], "Exact per-call numeric accounting mismatch")
            projection = {
                "decoded_numeric_bytes": added * 8,
                "decoded_numeric_elements_this_call": added,
                "trial_numeric_elements": plan["numeric_elements"],
                "trial_numeric_bytes": plan["numeric_elements"] * 8,
                "shared_numeric_elements_loaded_this_call": shared_need,
                "source_numeric_bytes_including_shared_cache": (plan["numeric_elements"] + self._shared_elements) * 8,
                "conservatively_charged_reader_elements": self._reader.loaded,
                "reader_elements_this_call": self._reader.loaded - reader_before,
                "original_trial_number": original["original_trial_number"],
                "raw_ordinal_one_based": ordinal_one_based,
                "session_id": SESSION,
                "source_field": "events", "target_field": "jointAngles",
                "all_session_local_roi_columns": 565, "joint_columns_preserved": 24,
                "metadata_sha256": METADATA_SHA256,
                "original_sha256": ORIGINAL_SHA256,
                "camera_values_sha256": original["camera1_clock"]["values_sha256"],
                "frame_values_sha256": original["frame_clock"]["values_sha256"],
                "roi_lags_sha256": self._metadata["roi_metadata"]["roilags_sha256"],
                "shared_first_camera_step_ms": self._shared_step,
                "shared_first_camera_original_trial_number": 1,
                "source_scalar_values": {"cycle_ms": self._cycle, "sync_ms": sync, "lift_ms": lift},
                "inverse_kinematics_executed": False,
                "full_native_eventLockKinematics_executed": False,
            }
            result = {"inputs": (events, joints, camera, frames, self._lags,
                                 self._cycle, sync, lift, self._shared_step),
                      "projection": projection}
            self._completed.append(ordinal_one_based)
            self._next += 1
            return result
        except BaseException as exc:
            self._failed = True
            self._failure = {
                "requested_ordinal": ordinal_one_based if type(ordinal_one_based) is int else None,
                "kind": type(exc).__name__, "detail": str(exc)[:512],
            }
            raise

    @property
    def trial_identities(self):
        """Immutable (ordinal, original trial number, eligible) for all416 rows."""
        return self._identities

    @property
    def accounting(self):
        """Fresh receipt facts; no original payload arrays are retained here."""
        state = "failed" if self._failed else ("complete" if self._next == len(self._eligible) else "ready")
        attempted = set(self._attempted)
        return {
            "state": state, "session_id": SESSION,
            "metadata_sha256": METADATA_SHA256, "complete_census_sha256": self._census_sha256,
            "total_original_trials": 416, "eligible_original_trials": 372,
            "excluded_original_trials": 44, "excluded_original_ordinals": list(self._excluded),
            "attempted_eligible_ordinals": list(self._attempted),
            "completed_eligible_ordinals": list(self._completed),
            "eligible_ordinals_not_attempted": [i for i in self._eligible if i not in attempted],
            "next_expected_ordinal": None if self._failed or self._next == len(self._eligible) else self._eligible[self._next],
            "failure": dict(self._failure) if self._failure is not None else None,
            "numeric_elements_reserved": self._numeric_reserved,
            "numeric_elements_decoded_finite": self._numeric_finite_decoded,
            "decoded_numeric_bytes_or_failure_upper_allowance": self._numeric_reserved * 8,
            "numeric_read_accounting_exact": not self._failed,
            "conservatively_charged_reader_elements": self._reader.loaded,
            "remaining_reader_elements": self._reader.remaining,
            "shared_numeric_values_cached": self._cache_ready,
            "limits": dict(self._limits),
            "posXYZ_values_read": False,
            "whole_file_authentication_owned_by_controller": True,
            "physical_IO_or_native_memory_metered_here": False,
        }
