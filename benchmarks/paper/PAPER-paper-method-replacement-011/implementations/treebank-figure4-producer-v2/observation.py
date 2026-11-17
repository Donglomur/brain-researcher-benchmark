"""Private, nonmutating observations of the separately verified author runtime.

This does not authenticate data, installed packages or scientific results. It
records the actual loaded function identities and observed values, without
fitting, predicting, resampling, or calling estimator methods itself.
"""
from collections.abc import Mapping, Sequence
import hashlib
import importlib.metadata
import json
import marshal
import math
from pathlib import Path
import sys
import threading


class ObservationError(RuntimeError):
    pass


AUTHOR_HOOKS = {
    "subject": ("run_time_tests", "run_subject_test", "run_time_tests.py"),
    "electrode": ("run_time_tests", "run_electrode_test", "run_time_tests.py"),
    "sampling": ("data.trial_data_reader", "TrialDataReader.get_aligned_linguistic_control_matrix", "data/trial_data_reader.py"),
    "split": ("tasks.utils", "split_dataset", "tasks/utils.py"),
    "dataset": ("tasks.classification_regression_task", "ClassificationRegressionTask.load_datasets", "tasks/classification_regression_task.py"),
    "runner": ("regression_runner", "RegressionRunnerTestSet.split_and_train_and_test", "regression_runner.py"),
}
DEPENDENCY_HOOKS = {
    "cv_scores": ("sklearn.model_selection._validation", "cross_val_score", "model_selection/_validation.py"),
    "cv_fold": ("sklearn.model_selection._validation", "_fit_and_score", "model_selection/_validation.py"),
    "probabilities": ("sklearn.pipeline", "Pipeline.predict_proba", "pipeline.py"),
}


def _attribute(obj, name, default=None):
    if isinstance(obj, Mapping):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _shape(value):
    shape = getattr(value, "shape", None)
    return None if shape is None else [int(x) for x in shape]


def _function(module_name, qualified_name):
    obj = sys.modules.get(module_name)
    if obj is None:
        raise ObservationError("required module is not already loaded: " + module_name)
    for name in qualified_name.split("."):
        obj = getattr(obj, name)
    seen = set()
    while hasattr(obj, "__wrapped__"):
        if id(obj) in seen:
            raise ObservationError("cyclic function wrapper")
        seen.add(id(obj))
        obj = obj.__wrapped__
    if not hasattr(obj, "__code__"):
        raise ObservationError("Python code object unavailable: " + qualified_name)
    return obj


class SourceObserver:
    """Observe one thread's original calls; the callback owns stream custody.

    Import the verified author modules before entering. No scientific values
    are silently truncated: an oversized or unsupported event raises and must
    leave the encompassing run unsuccessful. This is not a memory sandbox.
    """

    def __init__(self, source_root, emit_callback, *, max_event_bytes=1048576):
        self.source_root = Path(source_root).resolve(strict=True)
        if not self.source_root.is_dir() or not callable(emit_callback):
            raise ObservationError("source directory and callback required")
        if type(max_event_bytes) is not int or max_event_bytes < 1024:
            raise ObservationError("positive event budget of at least 1024 bytes required")
        self.callback = emit_callback
        self.max_event_bytes = max_event_bytes
        self.subject = None
        self.bindings = {}
        self.unavailable_hooks = {}
        self.dependency_identity = None
        self.counts = {}
        self.summary = {}
        self._codes = {}
        self._by_role = {}
        self._windows = {}
        self._cache_before = {}
        self._active = False
        self._failure = None
        self._file_hashes = {}
        self._completed_windows = 0
        self._incomplete_windows = 0

    def _file_hash(self, path):
        path = Path(path).resolve(strict=True)
        if path not in self._file_hashes:
            with path.open("rb") as stream:
                raw = stream.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise ObservationError("code-file observation budget exceeded")
            self._file_hashes[path] = hashlib.sha256(raw).hexdigest()
        return self._file_hashes[path]

    def _bind_one(self, role, module_name, name, expected_path):
        fn = _function(module_name, name)
        actual_path = Path(fn.__code__.co_filename).resolve(strict=True)
        expected_path = Path(expected_path).resolve(strict=True)
        if actual_path != expected_path:
            raise ObservationError("function source path mismatch: " + role)
        if fn.__code__ in self._codes:
            raise ObservationError("observation code identity collision")
        self._codes[fn.__code__] = role
        self._by_role[role] = fn.__code__
        self.bindings[role] = {
            "module": module_name,
            "qualified_name": name,
            "filename": str(actual_path),
            "file_sha256": self._file_hash(actual_path),
            "code_sha256": hashlib.sha256(marshal.dumps(fn.__code__)).hexdigest(),
        }

    def _bind(self):
        for role, (module, name, relative) in AUTHOR_HOOKS.items():
            self._bind_one(role, module, name, self.source_root / relative)
        try:
            package = sys.modules.get("sklearn")
            if package is None:
                raise ObservationError("sklearn is not already loaded")
            distribution = importlib.metadata.distribution("scikit-learn")
            installed_init = Path(distribution.locate_file("sklearn/__init__.py")).resolve(strict=True)
            if Path(package.__file__).resolve(strict=True) != installed_init:
                raise ObservationError("loaded sklearn does not match installed distribution path")
            root = installed_init.parent
            self.dependency_identity = {
                "distribution": "scikit-learn",
                "version": str(distribution.version),
                "root": str(root),
                "init_sha256": self._file_hash(installed_init),
                "meaning": "observed installation and code identity, not authenticated wheel provenance",
            }
        except (ObservationError, AttributeError, OSError, importlib.metadata.PackageNotFoundError) as exc:
            for role in DEPENDENCY_HOOKS:
                self.unavailable_hooks[role] = str(exc)
            return
        for role, (module, name, relative) in DEPENDENCY_HOOKS.items():
            try:
                self._bind_one(role, module, name, root / relative)
            except (ObservationError, AttributeError, OSError) as exc:
                self.unavailable_hooks[role] = str(exc)

    def _safe(self, value, depth=0):
        if depth > 20:
            raise ObservationError("event nesting limit exceeded")
        if value is None or type(value) in (str, bool, int):
            return value
        if type(value) is float:
            if math.isfinite(value):
                return value
            return {"nonfinite": "NaN" if math.isnan(value) else ("+Inf" if value > 0 else "-Inf")}
        if isinstance(value, Mapping):
            if len(value) > self.max_event_bytes // 2:
                raise ObservationError("event mapping exceeds budget")
            if any(type(key) is not str for key in value):
                raise ObservationError("event mapping keys must be strings")
            return {key: self._safe(item, depth + 1) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            if len(value) > self.max_event_bytes // 2:
                raise ObservationError("event sequence exceeds budget")
            return [self._safe(item, depth + 1) for item in value]
        # Admitted-runtime NumPy arrays/scalars are converted for private
        # evidence. The module-name check is not a hostile-object sandbox.
        module = type(value).__module__
        if module == "numpy" or module.startswith("numpy."):
            size = getattr(value, "size", 1)
            if int(size) > self.max_event_bytes // 2:
                raise ObservationError("array observation exceeds event budget")
            return self._safe(value.tolist(), depth + 1)
        raise ObservationError("unsupported observed value type: " + module + "." + type(value).__name__)

    def _emit(self, kind, **fields):
        event = self._safe({"event": kind, "subject": self.subject, **fields})
        encoded = json.dumps(event, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        if len(encoded) > self.max_event_bytes:
            raise ObservationError("complete event exceeds byte budget: " + kind)
        self.callback(event)
        self.counts[kind] = self.counts.get(kind, 0) + 1

    def __enter__(self):
        if self._active or self.bindings:
            raise ObservationError("observer instances are single-use")
        if sys.getprofile() is not None or sys.gettrace() is not None:
            raise ObservationError("preexisting profile/trace hook; refusing to replace it")
        self._previous_profile = sys.getprofile()
        self._owner_thread = threading.get_ident()
        self._bind()
        self._emit("observation_started", bindings=self.bindings,
                   unavailable_hooks=self.unavailable_hooks,
                   dependency=self.dependency_identity,
                   thread_scope="current thread only")
        self._active = True
        sys.setprofile(self._profile)
        return self

    def __exit__(self, exc_type, exc, traceback):
        sys.setprofile(self._previous_profile)
        self._active = False
        self.summary = {
            "status": "failed" if exc_type is not None or self._failure else "observed_not_scientifically_qualified",
            "event_counts": dict(self.counts),
            "completed_window_calls": self._completed_windows,
            "windows_with_unavailable_observations": self._incomplete_windows,
            "unavailable_hooks": dict(self.unavailable_hooks),
            "observer_failure": self._failure,
            "never_observed_events": [name for name in (
                "sampling", "split", "label_mapping", "training_cv_scores",
                "training_cv_fold", "heldout_probabilities", "window_result")
                if self.counts.get(name, 0) == 0],
        }
        try:
            self._emit("observation_finished", **self.summary)
        except Exception as finish_error:
            # Preserve the original failure if the remaining stream budget
            # cannot hold this additional failure summary.
            self.summary["finish_event_error"] = str(finish_error)
            if exc_type is None:
                raise
        return False

    def _ancestor(self, frame, role):
        wanted = self._by_role.get(role)
        while frame is not None:
            if frame.f_code is wanted:
                return frame
            frame = frame.f_back
        return None

    def _context(self, frame):
        subject_frame = self._ancestor(frame, "subject")
        if subject_frame is None:
            return None
        local = subject_frame.f_locals
        observed_subject = _attribute(local.get("data_cfg"), "subject")
        if self.subject is not None and observed_subject is not None and self.subject != observed_subject:
            raise ObservationError("declared subject differs from source subject")
        context = {"source_subject": observed_subject, "contact": local.get("e"), "window": None}
        if self._ancestor(frame, "electrode") is not None:
            i = local.get("i")
            windows = local.get("window_starts")
            if i is not None and windows is not None:
                context["window"] = {
                    "index": int(i), "nominal_start": windows[i],
                    "requested_sample_start": local.get("start"),
                    "requested_sample_duration": local.get("idx_duration"),
                    "supplied_shape": _shape(local.get("cached_seeg_data")),
                    "parent_shape": _shape(local.get("all_data")),
                }
        return context

    def _key(self, context):
        window = context.get("window")
        if window is None:
            return None
        return (context["source_subject"], context["contact"], window["index"])

    def _mark(self, context, name):
        key = self._key(context)
        if key is not None:
            counts = self._windows.setdefault(key, {})
            counts[name] = counts.get(name, 0) + 1

    def _model_configuration(self, model):
        steps = vars(model).get("steps", []) if hasattr(model, "__dict__") else []
        result = []
        for name, estimator in steps:
            parameters = {}
            for key, value in vars(estimator).items():
                if key.startswith("_") or key.endswith("_"):
                    continue
                try:
                    parameters[key] = self._safe(value)
                except ObservationError:
                    parameters[key] = {"unavailable": "not a JSON-safe stored parameter", "type": type(value).__name__}
            result.append({"step": name, "class": type(estimator).__module__ + "." + type(estimator).__qualname__,
                           "stored_parameters": parameters})
        return result

    def _class_order(self, model):
        steps = vars(model).get("steps", []) if hasattr(model, "__dict__") else []
        if steps and hasattr(steps[-1][1], "__dict__") and "classes_" in vars(steps[-1][1]):
            return {"status": "observed", "values": vars(steps[-1][1])["classes_"]}
        return {"status": "unavailable", "reason": "final estimator stored classes_ absent"}

    def _sampling(self, frame, value, context):
        local = frame.f_locals
        reader = local.get("self")
        trial = getattr(reader, "trial_data", None)
        base = {"context": context, "run_subject": getattr(trial, "subject_id", None),
                "run_id": getattr(trial, "trial_id", None)}
        required = ("word_idxs", "non_word_idxs", "word_intervals", "valid_non_word_intervals", "w_df")
        if value is None or any(name not in local for name in required):
            self._emit("sampling", status="unavailable", reason="cache return or incomplete sampling frame", **base)
            return
        frame_indices = list(local["w_df"].index)
        positive = [{"candidate_index": int(i), "sample_bounds": local["word_intervals"][i],
                     "processed_transcript_index": frame_indices[i]} for i in local["word_idxs"]]
        negative = [{"candidate_index": int(i), "sample_bounds": local["valid_non_word_intervals"][i]}
                    for i in local["non_word_idxs"]]
        self._emit("sampling", status="observed", positive=positive, negative=negative,
                   concatenation_order=["positive", "negative"],
                   original_csv_row_identity="unavailable: source reset/filtered transcript indices",
                   positive_candidate_count=len(local["word_intervals"]),
                   negative_candidate_count=len(local["valid_non_word_intervals"]),
                   sampling_frequency=local.get("samp_frequency"),
                   result_shape=_shape(value[0]), **base)

    def _split_call(self, frame):
        args = frame.f_locals.get("args")
        root = _attribute(args, "saved_data_split")
        snapshot = {"path": None, "existed_at_call": None}
        if isinstance(root, str):
            runs = _attribute(args, "brain_runs")
            name = _attribute(args, "name")
            subject = _attribute(args, "subject")
            if (isinstance(runs, Sequence) and not isinstance(runs, (str, bytes)) and
                    all(isinstance(run, str) for run in runs) and
                    isinstance(name, str) and isinstance(subject, str)):
                path = Path(root) / name / subject / "_".join(runs) / "splits.json"
                snapshot = {"path": str(path), "existed_at_call": path.exists()}
        self._cache_before[id(frame)] = snapshot

    def _profile(self, frame, event, value):
        if not self._active or threading.get_ident() != self._owner_thread:
            return
        role = self._codes.get(frame.f_code)
        if role is None or event not in ("call", "return"):
            return
        try:
            context = self._context(frame)
            if context is None:
                return
            if event == "call":
                if role == "split":
                    self._split_call(frame)
                return
            local = frame.f_locals
            if role == "sampling":
                self._sampling(frame, value, context)
            elif role == "split":
                required = ("train_idxs", "val_idxs", "test_idxs", "labels", "train_y", "test_y")
                observed = value is not None and all(name in local for name in required)
                self._emit("split", context=context, status="observed" if observed else "unavailable",
                           train=local.get("train_idxs"), validation=local.get("val_idxs"), test=local.get("test_idxs"),
                           dataset_labels=local.get("labels"), train_labels=local.get("train_y"),
                           test_labels=local.get("test_y"), validation_labels=local.get("val_y"),
                           cache_before=self._cache_before.pop(id(frame), None),
                           source_cache_path=local.get("saved_data_split_path"),
                           cache_loaded="not inferred from file existence")
                if observed:
                    self._mark(context, "split")
            elif role == "dataset":
                task = local.get("self")
                dataset = getattr(task, "dataset", None)
                mapping = getattr(dataset, "label2idx_dict", None)
                observed = isinstance(mapping, Mapping)
                self._emit("label_mapping", context=context, status="observed" if observed else "unavailable",
                           mapping=None if not observed else [{"label": key, "index": item} for key, item in mapping.items()])
                if observed:
                    self._mark(context, "label_mapping")
            elif role in ("cv_scores", "cv_fold", "probabilities"):
                runner_frame = self._ancestor(frame.f_back, "runner")
                if runner_frame is None:
                    return
                if role == "cv_scores":
                    if value is not None:
                        self._emit("training_cv_scores", context=context, scores=value, hook=self.bindings[role])
                        self._mark(context, "training_cv_scores")
                elif role == "cv_fold":
                    if self._ancestor(frame.f_back, "cv_scores") is None:
                        return
                    if value is not None and "train" in local and "test" in local:
                        self._emit("training_cv_fold", context=context, train_relative_to_training=local["train"],
                                   validation_relative_to_training=local["test"], result=value, hook=self.bindings[role])
                        self._mark(context, "training_cv_fold")
                elif (local.get("self") is runner_frame.f_locals.get("model") and
                      "X" in local and "X_test" in runner_frame.f_locals and
                      local["X"] is runner_frame.f_locals["X_test"] and
                      self._ancestor(frame.f_back, "cv_fold") is None):
                    if value is not None:
                        self._emit("heldout_probabilities", context=context, probabilities=value,
                                   source_column_used=1, class_order=self._class_order(local["self"]),
                                   observed_call="original final pipeline invocation on original X_test object", hook=self.bindings[role])
                        self._mark(context, "heldout_probabilities")
            elif role == "runner":
                counts = self._windows.pop(self._key(context), {})
                required = ("split", "label_mapping", "training_cv_scores", "heldout_probabilities")
                missing = [name for name in required if counts.get(name, 0) != 1]
                task = getattr(local.get("self"), "task", None)
                folds = _attribute(getattr(task, "cfg", None), "num_repeat")
                if type(folds) is not int or counts.get("training_cv_fold", 0) != folds:
                    missing.append("complete_training_cv_fold_membership")
                self._completed_windows += 1
                self._incomplete_windows += bool(missing)
                self._emit("window_result", context=context,
                           status="observed" if isinstance(value, dict) else "unavailable",
                           scores=value, count=local.get("count"),
                           decimated_train_shape=_shape(local.get("X_train")),
                           decimated_test_shape=_shape(local.get("X_test")),
                           final_model_configuration=self._model_configuration(local.get("model")),
                           observation_counts=counts, unavailable_observations=missing)
        except Exception as exc:
            self._failure = type(exc).__name__ + ": " + str(exc)
            raise
