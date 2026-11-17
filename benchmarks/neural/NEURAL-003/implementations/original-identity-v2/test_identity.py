"""Generated source-identity controls; no recordings, fitting or private targets."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from neural003_identity import partition as new
from neural003_identity import reference as ref


def load_predecessor():
    root = ROOT.parent / "causal-reaction-time" / "neural003"
    name = "neural003_identity_predecessor"
    package = types.ModuleType(name)
    package.__path__ = [str(root)]
    sys.modules[name] = package
    for part in ("partition", "prediction_schema", "reference"):
        spec = importlib.util.spec_from_file_location(name + "." + part, root / (part + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return sys.modules[name + ".partition"], module


OLD, OLD_REF = load_predecessor()


def roster(module=new, repeat_trial=False):
    return tuple(module.Trial(person, "session-A", block,
                              "trial-0" if repeat_trial else "trial-" + str(index), instruction)
                 for person in range(26)
                 for index, (block, instruction) in enumerate(
                     (("block-A", "speed"), ("block-B", "accuracy"))))


def observations(trials, arm="contrast_instruction", labels=True):
    return tuple(ref.Observation(t, 20, (0.0,) * 96 if arm == "eeg" else (),
                                 0.5 if labels else None) for t in trials)


class OriginalIdentityControls(unittest.TestCase):
    def test_predecessor_accepts_altered_block_and_instruction(self):
        """Executable counterexample on the retained predecessor, no fitting."""
        fold = OLD.compile_splits(roster(OLD))[0]
        rows = tuple(OLD_REF.Observation(t, 20, (), 0.5)
                     for t in roster(OLD) if t.person != 0)
        for changed in (replace(rows[0].identity, block="changed-block"),
                        replace(rows[0].identity, instruction="accuracy")):
            altered = (replace(rows[0], identity=changed),) + rows[1:]
            admitted = OLD_REF.check_rows(altered, fold.training, True, "contrast_instruction")
            self.assertEqual(admitted[0].identity, changed)

    def test_all_original_fields_and_instruction_are_bound_before_fit(self):
        fold = new.compile_splits(roster())[0]
        for arm in ref.ARMS:
            rows = observations(fold.training, arm)
            for field, value in (("person", 0), ("session", "other-session"),
                                 ("block", "other-block"), ("trial", "other-trial"),
                                 ("instruction", "accuracy")):
                changed = replace(rows[0].identity, **{field: value})
                altered = (replace(rows[0], identity=changed),) + rows[1:]
                with self.subTest(arm=arm, field=field), patch.object(ref, "_fit") as fit:
                    with self.assertRaises(ValueError):
                        ref.fit_reference(altered, fold, arm)
                    fit.assert_not_called()

    def test_query_metadata_and_labels_are_checked_before_prediction(self):
        fold = new.compile_splits(roster())[0]
        for arm in ref.ARMS:
            model = ref.FrozenRidge(arm, 0.1, fold.training, None, None, None, 0.5)
            rows = observations(fold.query, arm, labels=False)
            mutations = (
                replace(rows[0], identity=replace(rows[0].identity, block="other-block")),
                replace(rows[0], identity=replace(rows[0].identity, instruction="accuracy")),
                replace(rows[0], rt_seconds=0.5),
            )
            for changed in mutations:
                with self.subTest(arm=arm, changed=changed), patch.object(ref, "_predict") as predict:
                    with self.assertRaises(ValueError):
                        ref.predict_reference(model, (changed,) + rows[1:], fold)
                    predict.assert_not_called()

    def test_distinct_blocks_keep_repeated_trial_names_without_fabricating_ids(self):
        with self.assertRaisesRegex(ValueError, "duplicate original trial"):
            OLD.compile_splits(roster(OLD, repeat_trial=True))
        folds = new.compile_splits(roster(repeat_trial=True))
        self.assertEqual(len(folds), 26)
        self.assertTrue(all(len(fold.query) == 2 for fold in folds))
        for fold in folds:
            self.assertEqual(tuple(t.trial for t in fold.query), ("trial-0", "trial-0"))
            self.assertEqual(tuple(t.block for t in fold.query), ("block-A", "block-B"))

    def test_whole_person_outer_and_inner_support_is_complete(self):
        source = roster()
        folds = new.compile_splits(source)
        self.assertEqual(folds, new.compile_splits(reversed(source)))
        for held, fold in enumerate(folds):
            self.assertEqual(new.validate_fold(fold), fold)
            expected_train = {t for t in source if t.person != held}
            self.assertEqual(set(fold.training), expected_train)
            self.assertEqual(set(fold.query), {t for t in source if t.person == held})
            self.assertEqual(len(fold.inner), 25)
            for person, train, validation in fold.inner:
                self.assertEqual(set(validation), {t for t in expected_train if t.person == person})
                self.assertEqual(set(train), expected_train - set(validation))
                self.assertFalse(set(train) & set(validation))

    def test_late_malformed_inner_fold_is_rejected_before_any_fit(self):
        fold = new.compile_splits(roster())[0]
        last_person, train, valid = fold.inner[-1]
        first_person, first_train, first_valid = fold.inner[0]
        bad_folds = (
            replace(fold, inner=fold.inner[:-1]),
            replace(fold, inner=fold.inner[:-1] + ((last_person, train[:-1], valid),)),
            replace(fold, inner=fold.inner[:-1] + ((last_person, train, train[:1]),)),
            replace(fold, query=fold.training[:1]),
            replace(fold, held_person=True),
            replace(fold, inner=((True, first_train, first_valid),) + fold.inner[1:]),
            replace(fold, inner=((first_person, first_train,
                                 (replace(first_valid[0], person=True),) + first_valid[1:]),)
                    + fold.inner[1:]),
        )
        for altered in bad_folds:
            with self.subTest(altered=altered), patch.object(ref, "_fit") as fit:
                with self.assertRaises(ValueError):
                    ref.fit_reference(observations(fold.training), altered, "contrast_instruction")
                fit.assert_not_called()

    def test_duplicate_source_identity_and_conflicting_block_metadata_fail(self):
        source = roster()
        faults = (source + (source[0],),
                  source + (replace(source[0], instruction="accuracy"),),
                  source + (replace(source[0], trial="new-trial", instruction="accuracy"),))
        for altered in faults:
            with self.assertRaises(ValueError):
                new.compile_splits(altered)

    def test_admission_restores_order_and_arm_observation_boundary(self):
        fold = new.compile_splits(roster())[0]
        for arm in ref.ARMS:
            rows = observations(fold.training, arm)
            self.assertEqual(ref.check_rows(reversed(rows), fold.training, True, arm), rows)
            invalid = replace(rows[0], eeg=() if arm == "eeg" else (1.0,) * 96)
            with self.assertRaises(ValueError):
                ref.check_rows((invalid,) + rows[1:], fold.training, True, arm)
        one = observations(fold.query)[0]
        changed = replace(one, identity=replace(one.identity, person=25, session="elsewhere",
                                               block="another-block", trial="another-trial"))
        self.assertEqual(ref.features((one,), "contrast_instruction"),
                         ref.features((changed,), "contrast_instruction"))
        self.assertEqual(ref.features((one,), "contrast_instruction"), [(0.2, 0.0, 0.0)])

    def test_valid_reference_orchestration_preserves_all_75_inner_fits(self):
        """Test membership/routing with stubs; numerical fitting is never called."""
        fold = new.compile_splits(roster())[0]
        for arm in ref.ARMS:
            calls = []
            def fitted(rows, actual_arm, alpha):
                calls.append((tuple(r.identity for r in rows), actual_arm, alpha))
                return ref.FrozenRidge(actual_arm, alpha, tuple(r.identity for r in rows),
                                       None, None, None, 0.5)
            def predicted(model, rows):
                self.assertFalse(set(model.training_ids) & {r.identity for r in rows})
                return (0.5,) * len(rows)
            with patch.object(ref, "_fit", side_effect=fitted), patch.object(ref, "_predict", side_effect=predicted):
                model = ref.fit_reference(observations(fold.training, arm), fold, arm)
                result = ref.predict_reference(model, observations(fold.query, arm, labels=False), fold)
            self.assertEqual(len(calls), 76)
            self.assertEqual(tuple(c[2] for c in calls[:-1]),
                             (0.1,) * 25 + (1.0,) * 25 + (10.0,) * 25)
            self.assertEqual(calls[-1], (fold.training, arm, 0.1))
            self.assertEqual(result, (0.5, 0.5))


if __name__ == "__main__":
    unittest.main(verbosity=2)
