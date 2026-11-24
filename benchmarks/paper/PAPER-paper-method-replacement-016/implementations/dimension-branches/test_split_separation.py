"""Generated metadata only: train1000 cannot contain known test102 videos."""
import copy
from pathlib import Path
import sys
import unittest

# Permit direct execution with python3 -I -S -B as well as test discovery.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from hundred_models_dimensions import operations as o
from hundred_models_dimensions import program as p
from hundred_models_dimensions import consumers as c
from hundred_models_dimensions import _catalog_gate as g

PIN = "1" * 64
TRAIN = tuple("generated_training_" + str(i).zfill(4) for i in range(1000))


def stimulus_support(ids):
    return o.StimulusSupport(ids, o.canonical_digest(ids, o.SerializationBudget(100_000)), PIN)


def feature_support(ids):
    shapes = (o.LayerShape("layer_a", (128,)), o.LayerShape("layer_b", (128,)))
    return o.FeatureSupport("generated_model", stimulus_support(ids), ("layer_a", "layer_b"),
                            tuple(o.FeatureFile(name + ".npz", name, shapes) for name in ids), PIN)


def brain_support(ids):
    stimuli = stimulus_support(ids)
    return o.BrainSupport(stimuli, tuple(
        o.BrainRecord(subject, roi, (1000, 3, 1), stimuli.order_sha256, PIN)
        for subject in o.SUBJECTS for roi in o.ROIS), PIN)


def run_binding(branch, ids):
    """Complete branch conditions with explicit generated receipt declarations."""
    n, reps = (102, 10) if branch == "figure16" else (1000, 3)
    folders = tuple(name for name, _ in p.METHOD_FOLDERS) if branch == "figure16" else ("generated_train",)
    layers = tuple((name, ("layer_a", "layer_b")) for name, _ in c.membership(branch))
    producer = dict(layers)
    declared = g.pin(b"generated declaration only")
    order = g.pin(g.encoded(list(ids)))
    records = []
    for model, names in layers:
        for folder in folders:
            method = dict(p.METHOD_FOLDERS)[folder] if branch == "figure16" else "pca"
            records.append({"model": model, "folder": folder, "stimulus_order": order,
                "layer_order": g.pin(g.encoded(names)), "producer_layer_order": g.pin(g.encoded(names)),
                "n_stimuli": n, "split_emission_receipt": declared, "operation_contract": declared,
                "score_provenance_receipt": declared,
                "operation_profile": {"pca": "literal_held_script_pca100_fit102",
                    "srp": "explicit_admitted_srp_run_metadata", None: "explicit_admitted_no_reduction_run_metadata"}[method],
                "reduction": {"method": method, "n_samples_estim": 102 if method else None,
                    "n_components": 100 if method == "pca" else None, "max_dim_allowed": None,
                    "standardize_on_dim": None, "distance": "pearson",
                    "sklearn_kwargs_policy": "constructor-only-n_components;other-keywords-omitted"}})
    run = {"schema": "hundred_models_dimension_run_v1", "branch": branch,
        "protocol": g.PROTOCOL_PIN, "evidence_origin": "invented_control",
        "split": {"selection": "test" if branch == "figure16" else "train", "ordered_ids": list(ids),
            "n_stimuli": n, "repetitions": reps, "order_admission": declared},
        "brain": {"subjects": list(p.SUBJECTS), "rois": list(p.ROIS), "n_stimuli": n,
            "repetitions": reps, "average_external": False, "operation_contract": declared,
            "shape_manifest": declared, "noise_ceiling_receipt": declared},
        "base_folder": folders[-1], "comparison_folders": list(folders[:-1]), "conditions": records}
    return run, layers, producer, folders


class SplitSeparationTests(unittest.TestCase):
    def test_disjoint_train_compiles_full_model_and_brain_support(self):
        model = o.compile_model_contract(o.TRAIN_SPLIT, feature_support(TRAIN),
                                        o.literal_script_pca(), budget=o.SerializationBudget(1_000_000))
        brain = o.compile_brain_contract(o.TRAIN_SPLIT, brain_support(TRAIN),
                                        budget=o.SerializationBudget(1_000_000))
        self.assertEqual(model.stimulus_order, TRAIN)
        self.assertEqual(brain.stimulus_order, TRAIN)
        self.assertEqual((model.split.stimuli, model.split.repetitions), (1000, 3))
        self.assertEqual(dict(model.iterator_kwargs)["n_samples_estim"], 102)
        self.assertFalse(model.scientific_qualified)
        self.assertFalse(brain.scientific_qualified)

    def test_train_overlap_rejected_by_both_operation_entrypoints(self):
        # One substituted test video and a padded full test set both keep 1000 unique IDs.
        for ids in (TRAIN[:-1] + (o.TEST_STIMULI[0],), TRAIN[:898] + o.TEST_STIMULI):
            for compiler, support in ((o.compile_model_contract, feature_support(ids)),
                                      (o.compile_brain_contract, brain_support(ids))):
                args = (o.TRAIN_SPLIT, support)
                if compiler is o.compile_model_contract:
                    args += (o.literal_script_pca(),)
                with self.subTest(overlap=len(set(ids) & set(o.TEST_STIMULI)), compiler=compiler.__name__):
                    with self.assertRaisesRegex(o.ContractError, "train_stimuli_overlap_test102"):
                        compiler(*args, budget=o.SerializationBudget(1_000_000))

    def test_unchanged_test_and_training_branch_contracts(self):
        for branch, ids, expected in (("figure16", o.TEST_STIMULI, (102, 10)),
                                      ("figure17", TRAIN, (1000, 3))):
            run, layers, producer, folders = run_binding(branch, ids)
            result = p._run_contract(branch, {"stimuli": list(o.TEST_STIMULI)},
                                     layers, producer, g.encoded(run))
            self.assertEqual(result, (folders, *expected))

    def test_rehashed_overlap_cannot_pass_training_branch_binding(self):
        for ids in (TRAIN[:-1] + (o.TEST_STIMULI[-1],), TRAIN[:898] + o.TEST_STIMULI):
            # Construct every condition with the contaminated order's matching digest.
            run, layers, producer, _ = run_binding("figure17", ids)
            original = copy.deepcopy(run)
            with self.subTest(overlap=len(set(ids) & set(o.TEST_STIMULI))):
                with self.assertRaisesRegex(ValueError, "training stimuli must exclude original test102 IDs"):
                    p._run_contract("figure17", {"stimuli": list(o.TEST_STIMULI)},
                                    layers, producer, g.encoded(run))
            self.assertEqual(run, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
