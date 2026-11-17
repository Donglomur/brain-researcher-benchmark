"""Generated Python frame fixtures only; no scientific packages or models."""
from contextlib import contextmanager
from functools import wraps
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import textwrap
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("treebank_observation", ROOT / "observation.py")
observation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observation)


class ShapeList(list):
    def __init__(self, values, shape):
        super().__init__(values)
        self.shape = shape


class Fixture:
    """Toy functions with source-like names, never the original source bytes."""
    def __init__(self, base):
        self.root = base / "author"
        self.dependency = base / "installed/sklearn"
        self.modules = {}
        self.saved_modules = {}
        self.root.mkdir()
        self.dependency.mkdir(parents=True)
        init = self.dependency / "__init__.py"
        init.write_text("# generated package marker\n")
        package = types.ModuleType("sklearn")
        package.__file__ = str(init)
        self.install("sklearn", package)
        self.pipeline = self.make("sklearn.pipeline", self.dependency / "pipeline.py", '''
            class StoredParameters:
                def __init__(self):
                    self.random_state = 0
                    self.max_iter = 500
                    self.classes_ = [0, 1]
                def get_params(self, *args, **kwargs):
                    raise AssertionError('observer must not call estimator methods')
            class Pipeline:
                def __init__(self, oversized=False):
                    self.steps = [('fixed_stub', StoredParameters())]
                    self.oversized = oversized
                def predict_proba(self, X):
                    return [[0.1, 0.9]] * (10000 if self.oversized else len(X))
        ''')
        self.validation = self.make("sklearn.model_selection._validation", self.dependency / "model_selection/_validation.py", '''
            def _fit_and_score(estimator, X, y, train, test):
                estimator.predict_proba(X)
                return {'test_scores': 0.7, 'fit_time': 0.001}
            def cross_val_score(model, X, y, cv, scoring):
                return [_fit_and_score(Pipeline(), X, y, [0, 1], [2, 3])['test_scores'] for _ in range(cv)]
        ''', {"Pipeline": self.pipeline.Pipeline})
        self.reader = self.make("data.trial_data_reader", self.root / "data/trial_data_reader.py", '''
            class TrialDataReader:
                def __init__(self, trial_data, cache=False):
                    self.trial_data = trial_data
                    self.cache = cache
                def get_aligned_linguistic_control_matrix(self):
                    if self.cache:
                        return ShapeList([], (1, 4, 4096)), {'cached': True}
                    w_df = Namespace(index=[7, 9, 12])
                    word_intervals = [(100, 120), (300, 320), (500, 520)]
                    valid_non_word_intervals = [(1000, 1020), (2000, 2020)]
                    word_idxs = [2, 0]
                    non_word_idxs = [1, 0]
                    samp_frequency = 2048
                    return ShapeList([], (1, 4, 4096)), {'linguistic_content': [True, True, False, False]}
        ''', {"ShapeList": ShapeList, "Namespace": types.SimpleNamespace})
        self.utils = self.make("tasks.utils", self.root / "tasks/utils.py", '''
            def split_dataset(dataset, args):
                train_idxs, val_idxs, test_idxs = [2, 0, 3], [], [1]
                labels = [1, 1, 0, 0]
                train_y, test_y, val_y = [0, 1, 0], [1], []
                saved_data_split_path = str(Path(args.saved_data_split) / args.name / args.subject / '_'.join(args.brain_runs))
                train_X = ShapeList([0, 0, 0], (3, 512))
                test_X = ShapeList([0], (1, 512))
                return train_X, train_y, test_X, test_y, [], val_y
        ''', {"Path": Path, "ShapeList": ShapeList})
        self.task = self.make("tasks.classification_regression_task", self.root / "tasks/classification_regression_task.py", '''
            class ClassificationRegressionTask:
                def __init__(self, cfg):
                    self.cfg = cfg
                def load_datasets(self, data_cfg, cached_seeg_data=None, cached_word_df=None):
                    dataset = Namespace(label2idx_dict={False: 0, True: 1})
                    (self.train_X, self.train_y, self.test_X, self.test_y,
                     self.val_X, self.val_y) = split_dataset(dataset, data_cfg)
                    self.dataset = dataset
        ''', {"Namespace": types.SimpleNamespace, "split_dataset": self.utils.split_dataset})
        self.runner = self.make("regression_runner", self.root / "regression_runner.py", '''
            class RegressionRunnerTestSet:
                def __init__(self, task, oversized=False):
                    self.task = task
                    self.oversized = oversized
                def split_and_train_and_test(self, count):
                    X_train, y_train = self.task.train_X, self.task.train_y
                    X_test, y_test = self.task.test_X, self.task.test_y
                    model = Pipeline()
                    cv_score = cross_val_score(model, X_train, y_train, cv=self.task.cfg.num_repeat, scoring='roc_auc')
                    model = Pipeline(self.oversized)
                    probabilities = model.predict_proba(X_test)
                    cv_score = sum(cv_score) / len(cv_score)
                    return {'test_score': 0.8, 'cv_score': cv_score}
        ''', {"Pipeline": self.pipeline.Pipeline, "cross_val_score": self.validation.cross_val_score})
        self.entry = self.make("run_time_tests", self.root / "run_time_tests.py", '''
            def run_electrode_test(data_cfg, cfg, cached_seeg_data, cached_word_df, count=0):
                task = ClassificationRegressionTask(cfg.task)
                task.load_datasets(data_cfg, cached_seeg_data, cached_word_df)
                runner = RegressionRunnerTestSet(task, cfg.oversized)
                return runner.split_and_train_and_test(count)
            def run_subject_test(data_cfg, brain_runs, electrodes, cfg):
                window_starts = [-1.0, -0.9]
                idx_duration = 512
                result = {}
                for e in electrodes:
                    reader = TrialDataReader(Namespace(subject_id=data_cfg.subject, trial_id='trial000'), cfg.cache)
                    all_data, labels = reader.get_aligned_linguistic_control_matrix()
                    result[e] = {}
                    for i, start in enumerate([0, 204]):
                        cached_seeg_data = ShapeList([], (1, 4, 512))
                        result[e][window_starts[i]] = run_electrode_test(data_cfg, cfg, cached_seeg_data, labels, i)
                return result
        ''', {"ClassificationRegressionTask": self.task.ClassificationRegressionTask,
              "RegressionRunnerTestSet": self.runner.RegressionRunnerTestSet,
              "TrialDataReader": self.reader.TrialDataReader,
              "Namespace": types.SimpleNamespace, "ShapeList": ShapeList})
        self.data_cfg = types.SimpleNamespace(subject="sub_1", brain_runs=["trial000"],
            name="sentence_onset_regression", saved_data_split=str(base / "splits"))
        self.cfg = types.SimpleNamespace(task=types.SimpleNamespace(num_repeat=5), cache=False, oversized=False)

    def install(self, name, module):
        self.saved_modules[name] = sys.modules.get(name)
        sys.modules[name] = module
        self.modules[name] = module

    def make(self, name, path, code, additions=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        text = textwrap.dedent(code)
        path.write_text(text)
        module = types.ModuleType(name)
        module.__file__ = str(path)
        module.__dict__.update(additions or {})
        exec(compile(text, str(path), "exec"), module.__dict__)
        self.install(name, module)
        return module

    def distribution(self, name):
        assert name == "scikit-learn"
        return types.SimpleNamespace(version="generated-fixture", locate_file=lambda relative: self.dependency.parent / relative)

    def run(self):
        return self.entry.run_subject_test(self.data_cfg, ["trial000"], ["A1"], self.cfg)

    def close(self):
        for name, old in self.saved_modules.items():
            if old is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = Fixture(Path(self.temp.name))
        self.distribution_patch = patch.object(observation.importlib.metadata, "distribution", self.fixture.distribution)
        self.distribution_patch.start()

    def tearDown(self):
        sys.setprofile(None)
        sys.settrace(None)
        self.distribution_patch.stop()
        self.fixture.close()
        self.temp.cleanup()

    def observe(self, **kwargs):
        events = []
        observer = observation.SourceObserver(self.fixture.root, events.append, **kwargs)
        observer.subject = "sub_1"
        with observer:
            result = self.fixture.run()
        return result, events, observer

    def test_complete_generated_route_preserves_results_rng_and_hook(self):
        before = random.getstate()
        expected = self.fixture.run()
        result, events, observer = self.observe()
        self.assertEqual(result, expected)
        self.assertEqual(random.getstate(), before)
        self.assertIsNone(sys.getprofile())
        self.assertEqual(observer.summary["completed_window_calls"], 2)
        self.assertEqual(observer.summary["windows_with_unavailable_observations"], 0)
        self.assertEqual(observer.summary["never_observed_events"], [])
        self.assertEqual(len([x for x in events if x["event"] == "training_cv_fold"]), 10)
        # Five CV clone invocations/window are deliberately NOT reported as
        # final held-out invocations.
        self.assertEqual(len([x for x in events if x["event"] == "heldout_probabilities"]), 2)
        prediction = next(x for x in events if x["event"] == "heldout_probabilities")
        self.assertEqual(prediction["class_order"], {"status": "observed", "values": [0, 1]})
        json.dumps(events, allow_nan=False)

    def test_different_input_object_is_not_claimed_as_original_heldout_call(self):
        path = Path(self.fixture.runner.__file__)
        text = path.read_text().replace("model.predict_proba(X_test)", "model.predict_proba(list(X_test))")
        path.write_text(text)
        exec(compile(text, str(path), "exec"), self.fixture.runner.__dict__)
        self.fixture.entry.RegressionRunnerTestSet = self.fixture.runner.RegressionRunnerTestSet
        _, events, observer = self.observe()
        self.assertFalse(any(x["event"] == "heldout_probabilities" for x in events))
        self.assertEqual(observer.summary["windows_with_unavailable_observations"], 2)

    def test_decorated_dependency_functions_are_observed_once(self):
        original_cv = self.fixture.validation.cross_val_score
        original_predict = self.fixture.pipeline.Pipeline.predict_proba
        @wraps(original_cv)
        def decorated_cv(*args, **kwargs):
            return original_cv(*args, **kwargs)
        @wraps(original_predict)
        def decorated_predict(*args, **kwargs):
            return original_predict(*args, **kwargs)
        self.fixture.validation.cross_val_score = decorated_cv
        self.fixture.runner.cross_val_score = decorated_cv
        self.fixture.pipeline.Pipeline.predict_proba = decorated_predict
        _, events, observer = self.observe()
        self.assertEqual(observer.summary["windows_with_unavailable_observations"], 0)
        self.assertEqual(len([x for x in events if x["event"] == "training_cv_scores"]), 2)
        self.assertEqual(len([x for x in events if x["event"] == "heldout_probabilities"]), 2)

    def test_sampling_order_and_processed_index_are_not_original_csv_ids(self):
        _, events, _ = self.observe()
        item = next(x for x in events if x["event"] == "sampling")
        self.assertEqual([x["sample_bounds"] for x in item["positive"]], [[500, 520], [100, 120]])
        self.assertEqual([x["processed_transcript_index"] for x in item["positive"]], [12, 7])
        self.assertEqual([x["candidate_index"] for x in item["negative"]], [1, 0])
        self.assertIn("unavailable", item["original_csv_row_identity"])
        self.assertIsNone(item["context"]["window"])

    def test_observed_split_and_mapping_preserve_boolean_label_types(self):
        path = Path(self.fixture.data_cfg.saved_data_split) / "sentence_onset_regression/sub_1/trial000/splits.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"generated": true}')
        _, events, _ = self.observe()
        split = next(x for x in events if x["event"] == "split")
        self.assertEqual(split["train"], [2, 0, 3])
        self.assertTrue(split["cache_before"]["existed_at_call"])
        self.assertEqual(split["cache_loaded"], "not inferred from file existence")
        mapping = next(x for x in events if x["event"] == "label_mapping")
        self.assertEqual(mapping["mapping"], [{"label": False, "index": 0}, {"label": True, "index": 1}])

    def test_cache_early_return_is_explicitly_unavailable(self):
        self.fixture.cfg.cache = True
        _, events, _ = self.observe()
        sample = next(x for x in events if x["event"] == "sampling")
        self.assertEqual(sample["status"], "unavailable")
        self.assertNotIn("positive", sample)

    def test_no_route_does_not_fabricate_observations(self):
        events = []
        observer = observation.SourceObserver(self.fixture.root, events.append)
        with observer:
            self.fixture.pipeline.Pipeline().predict_proba([0])
        self.assertEqual(observer.summary["completed_window_calls"], 0)
        self.assertIn("heldout_probabilities", observer.summary["never_observed_events"])
        self.assertEqual([x["event"] for x in events], ["observation_started", "observation_finished"])

    def test_subject_mismatch_fails_and_restores_hook(self):
        observer = observation.SourceObserver(self.fixture.root, lambda event: None)
        observer.subject = "sub_9"
        with self.assertRaisesRegex(observation.ObservationError, "subject differs"):
            with observer:
                self.fixture.run()
        self.assertIsNone(sys.getprofile())
        self.assertEqual(observer.summary["status"], "failed")

    def test_callback_budget_failure_is_not_silently_suppressed(self):
        events = []
        def callback(event):
            if event["event"] == "training_cv_scores":
                raise RuntimeError("generated stream budget exceeded")
            events.append(event)
        observer = observation.SourceObserver(self.fixture.root, callback)
        with self.assertRaisesRegex(RuntimeError, "stream budget"):
            with observer:
                self.fixture.run()
        self.assertIsNone(sys.getprofile())
        self.assertEqual(observer.summary["status"], "failed")
        self.assertFalse(any(x["event"] == "window_result" and x["status"] == "observed" for x in events))

    def test_oversized_required_values_are_rejected_not_truncated(self):
        self.fixture.cfg.oversized = True
        events = []
        observer = observation.SourceObserver(self.fixture.root, events.append, max_event_bytes=12000)
        with self.assertRaisesRegex(observation.ObservationError, "budget"):
            with observer:
                self.fixture.run()
        self.assertFalse(any(x["event"] == "heldout_probabilities" for x in events))
        self.assertIsNone(sys.getprofile())

    def test_preexisting_hooks_are_not_replaced(self):
        for setter, getter in ((sys.setprofile, sys.getprofile), (sys.settrace, sys.gettrace)):
            hook = lambda *args: None
            setter(hook)
            try:
                with self.assertRaisesRegex(observation.ObservationError, "preexisting"):
                    with observation.SourceObserver(self.fixture.root, lambda event: None):
                        pass
                self.assertIs(getter(), hook)
            finally:
                setter(None)

    def test_same_function_name_with_wrong_author_path_is_rejected(self):
        other = Path(self.temp.name) / "unrelated.py"
        other.write_text("def split_dataset(*args): return None\n")
        namespace = {}
        exec(compile(other.read_text(), str(other), "exec"), namespace)
        self.fixture.utils.split_dataset = namespace["split_dataset"]
        with self.assertRaisesRegex(observation.ObservationError, "source path mismatch"):
            with observation.SourceObserver(self.fixture.root, lambda event: None):
                pass
        self.assertIsNone(sys.getprofile())

    def test_unverified_dependency_is_explicitly_unavailable(self):
        package = self.fixture.modules["sklearn"]
        other = Path(self.temp.name) / "unverified_init.py"
        other.write_text("# generated different installation\n")
        package.__file__ = str(other)
        _, events, observer = self.observe()
        self.assertEqual(set(observer.unavailable_hooks), {"cv_scores", "cv_fold", "probabilities"})
        self.assertEqual(observer.summary["windows_with_unavailable_observations"], 2)
        item = next(x for x in events if x["event"] == "window_result")
        self.assertIn("heldout_probabilities", item["unavailable_observations"])
        self.assertFalse(any(x["event"] == "heldout_probabilities" for x in events))

    def test_nonfinite_values_are_tagged_without_invalid_json(self):
        observer = observation.SourceObserver(self.fixture.root, lambda event: None)
        self.assertEqual(observer._safe(float("nan")), {"nonfinite": "NaN"})
        self.assertEqual(observer._safe(float("inf")), {"nonfinite": "+Inf"})
        self.assertEqual(observer._safe(float("-inf")), {"nonfinite": "-Inf"})
        with self.assertRaises(observation.ObservationError):
            observer._safe(object())


if __name__ == "__main__":
    unittest.main()
