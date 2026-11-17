"""Compare generated row identities against pinned author code without fitting.

Requires an independently acquired author figure_4.py supplied as the sole argument.
Only its hash-checked compute function is compiled. No source downloads are made.
"""
import ast
import hashlib
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from sklearn.metrics import roc_curve, auc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import figure4 as f
from test_figure4 import census


class Observations:
    def __init__(self, obs, values):
        self.obs, self.X = obs, values
        self.n_obs = len(obs)

    def __getitem__(self, key):
        mask = np.asarray(key[0])
        return Observations(self.obs.loc[mask].copy(), self.X[mask].copy())


class IdentityScaler:
    def fit_transform(self, values):
        return values


class RecordingClassifier:
    instances = []

    def __init__(self, **kwargs):
        self.instances.append(self)
        self.configuration = kwargs

    def fit(self, values, labels):
        self.train_ids = values[:, 0].astype(int).tolist()
        self.train_labels = labels.astype(int).tolist()
        if len(set(self.train_labels)) != 2:
            raise ValueError("generated single-class classifier control")
        return self

    def predict_proba(self, values):
        self.test_ids = values[:, 0].astype(int).tolist()
        probability = (values[:, 0] % 7) / 6
        return np.column_stack((1 - probability, probability))


def main():
    source = Path(sys.argv[1]).read_bytes()
    assert hashlib.sha256(source).hexdigest() == f.SOURCE_SHA256, "unrecognized author source"
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "compute_auroc_for_guides")
    scope = {"np": np, "pd": pd, "StandardScaler": IdentityScaler,
             "LogisticRegression": RecordingClassifier, "roc_curve": roc_curve, "auc": auc}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "pinned-author-figure4", "exec"), scope)
    data = census(); plan = f.prepare(data)
    compared = 0
    for input_panel, prepared in zip(data["panels"], plan["panels"]):
        # Compute source location expressions independently of implementation helper.
        rows = input_panel["observations"]
        obs = pd.DataFrame(rows)
        if input_panel["family"] == "manual_features":
            obs["loc_id"] = obs["well_id"].astype(str) + "_" + obs["zarr_file"].astype(str)
        else:
            obs["loc_id"] = obs["aggregate_by"].apply(lambda x: "_".join(x.split("_")[:2])) + "_" + obs["well_id"].astype(str)
        RecordingClassifier.instances = []
        result = scope["compute_auroc_for_guides"](Observations(obs, np.arange(len(obs)).reshape(-1, 1)),
                                                  well_id_col="loc_id", plot_curves=False)
        expected_guides = [e["guide_id"] for e in prepared["endpoints"]]
        assert result["guide_id"].tolist() == expected_guides * 2
        assert len(RecordingClassifier.instances) == len(expected_guides) * 2
        for endpoint, models in zip(prepared["endpoints"], zip(RecordingClassifier.instances[::2], RecordingClassifier.instances[1::2])):
            for fold, model in zip(endpoint["folds"], models):
                assert [rows[i]["observation_id"] for i in model.train_ids] == [r["observation_id"] for r in fold["train"]]
                assert model.train_labels == [r["label"] for r in fold["train"]]
                assert [rows[i]["observation_id"] for i in model.test_ids] == [r["observation_id"] for r in fold["test"]]
                probabilities = [(i % 7) / 6 for i in model.test_ids]
                score = f.auroc([r["label"] for r in fold["test"]], probabilities)
                source_score = result[result["guide_id"] == endpoint["guide_id"]]["auroc"].iloc[fold["fold"] - 1]
                assert abs(score - source_score) < 1e-12
                compared += 1
    print(f"Author-code parity passed: {compared} generated guide/donor/family/fold endpoints; no classifier fitting")
    print(f"numpy={np.__version__}; pandas={pd.__version__}")


if __name__ == "__main__":
    main()
