import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
import evaluator as ev


def packet(panel="transductive"):
    sessions = ["sb025_20191007", "sb026_20191014", "sb028_20191107", "sb030_20200110"]
    metadata = sum((ev.session_metadata(s, ["EC", "IN"] * 4, 8) for s in sessions), [])
    ids = [r["id"] for r in metadata]
    labels = {r["id"]: r["ei_class"] for r in metadata}
    by_subject = {s.split("_")[0]: [i for i in ids if i.startswith(s)] for s in sessions}
    if panel == "transductive":
        splits = [{"id": "neuron-wise", "train": ids[:4] + ids[8:12] + ids[16:20] + ids[24:28],
                   "val": ids[4:6] + ids[12:14] + ids[20:22] + ids[28:30],
                   "test": ids[6:8] + ids[14:16] + ids[22:24] + ids[30:32]}]
    else:
        splits = []
        for subject in (["sb028"] if panel == "inductive_zero_shot" else by_subject):
            test = by_subject[subject]
            train = [i for i in ids if i not in test]
            cv = []
            for val_subject in by_subject:
                if val_subject != subject:
                    val = by_subject[val_subject]
                    cv.append({"train": [i for i in train if i not in val], "val": val})
            splits.append({"id": subject, "train": train, "test": test, "train_cv": cv})
    suffix = {"transductive": "transductive", "inductive_zero_shot": "inductive_zs", "transductive_zero_shot": "transductive_zs"}[panel]
    features = [[-2.0 if labels[i] == "EC" else 2.0, 0.0] for i in ids]
    return {"schema_version": 1, "task_id": ev.TASK_ID, "source_commit": ev.SOURCE_COMMIT,
            "input_role": "generated_engineering_control", "label_level": "ei", "panel": panel,
            "context_variant": "population_context", "class_balance": "weight",
            "provenance": {"split_sha256": "a" * 64, "metadata_sha256": "b" * 64,
                "data_receipt_sha256": "c" * 64, "split_member": f"ei_{suffix}.pkl",
                "split_release": "other_explicit", "split_release_detail": "Generated engineering control, not an author split"},
            "source_session_manifest": sessions, "source_label_mapping": {"EC": "EC", "IN": "IN"}, "label_vocabulary": ["EC", "IN"], "label_map": labels, "metadata": metadata,
            "representation_training_sessions": [s for s in sessions if panel != "inductive_zero_shot" or not s.startswith("sb028")],
            "checkpoints": [{"id": "epoch_1", "epoch": 1, "ids": list(ids), "embeddings": features},
                            {"id": "epoch_2", "epoch": 2, "ids": list(ids), "embeddings": copy.deepcopy(features)}],
            "splits": splits}


class ReadoutTests(unittest.TestCase):
    def test_all_three_panels_and_tie(self):
        for panel in ("transductive", "transductive_zero_shot", "inductive_zero_shot"):
            result = ev.evaluate(packet(panel))
            self.assertEqual(result["metrics"]["accuracy"], 1)
            self.assertEqual(result["metrics"]["macro_f1"], 1)
            self.assertTrue(all(s["checkpoint_index"] == 0 for s in result["selected"]))
            self.assertFalse(result["research_qualified"])
            self.assertTrue(result["holds"])

    def test_selected_test_only_and_pooled_cv(self):
        p = packet("inductive_zero_shot")
        calls = []
        def fake(X, ids, labels, train, test, balance):
            calls.append((X[0][0], frozenset(test)))
            chosen = [i for i in ids if i in test]
            true = [labels[i] for i in chosen]
            return chosen, true, true
        with patch.object(ev, "_fit_predict", side_effect=fake):
            r = ev.evaluate(p)
        self.assertEqual(len(calls), 7)  # two checkpoints x three CV + one selected test
        heldout = frozenset(p["splits"][0]["test"])
        self.assertEqual(sum(test == heldout for _, test in calls), 1)
        self.assertEqual(r["selected"][0]["checkpoint_index"], 0)

    def test_train_only_scaling(self):
        from sklearn.preprocessing import StandardScaler
        p = packet()
        calls = []
        original = StandardScaler.fit
        def record_fit(self, X, *args, **kwargs):
            calls.append(X.copy())
            return original(self, X, *args, **kwargs)
        test_ids = set(p["splits"][0]["test"])
        ids = p["checkpoints"][0]["ids"]
        for checkpoint in p["checkpoints"]:
            for i, uid in enumerate(ids):
                if uid in test_ids:
                    checkpoint["embeddings"][i][1] = 1e9
        with patch.object(StandardScaler, "fit", record_fit):
            result = ev.evaluate(p)
        self.assertEqual(result["metrics"]["accuracy"], 1)
        self.assertTrue(all(float(X[:, 1].max()) == 0 for X in calls))

    def test_id_and_leakage_rejections(self):
        corruptions = [
            lambda p: p["checkpoints"][0]["ids"].pop(),
            lambda p: p["checkpoints"][1]["ids"].reverse(),
            lambda p: p["checkpoints"][0]["embeddings"][0].__setitem__(0, float("nan")),
            lambda p: p["splits"][0]["train"].append(p["splits"][0]["test"][0]),
            lambda p: p["metadata"][0].__setitem__("source_neuron_index", 100),
            lambda p: p["provenance"].__setitem__("split_member", "ei_inductive_zs.pkl"),
            lambda p: p["source_label_mapping"].__setitem__("IN", "wrong-class"),
            lambda p: p["representation_training_sessions"].pop(),
        ]
        for corrupt in corruptions:
            p = packet()
            corrupt(p)
            with self.assertRaises(ev.ContractError):
                ev.validate_packet(p)
        p = packet("inductive_zero_shot")
        p["representation_training_sessions"].append("sb028_20191107")
        with self.assertRaises(ev.ContractError):
            ev.validate_packet(p)
        p = packet("inductive_zero_shot")
        p["source_session_manifest"].append("sb028_20200101")
        p["representation_training_sessions"].append("sb028_20200101")
        with self.assertRaises(ev.ContractError):
            ev.validate_packet(p)
        p = packet("transductive_zero_shot")
        p["splits"].pop()
        with self.assertRaises(ev.ContractError):
            ev.validate_packet(p)

    def test_context_comparison_and_matching(self):
        a = packet()
        b = copy.deepcopy(a)
        b["context_variant"] = "ablated_context"
        for c in b["checkpoints"]:
            c["embeddings"] = [[0.0, 0.0] for _ in c["ids"]]
        result = ev.compare_context(a, b)
        self.assertAlmostEqual(result["context_minus_ablated"]["balanced_accuracy"], 0.5)
        b["provenance"]["split_release"] = "december_2025_current"
        with self.assertRaises(ev.ContractError):
            ev.compare_context(a, b)

    def test_no_resampling_substitution(self):
        if importlib.util.find_spec("imblearn") is None:
            p = packet()
            p["class_balance"] = "resample"
            with self.assertRaisesRegex(ev.ContractError, "imbalanced-learn"):
                ev.evaluate(p)

    def test_session_join(self):
        rows = ev.session_metadata("sb025_20191007", ["EC", "IN", "Pvalb-Tac1"], 3)
        self.assertEqual(rows[2]["id"], "sb025_20191007_u2")
        self.assertEqual(rows[2]["ei_class"], "IN")
        self.assertEqual(rows[2]["subclass"], "Pvalb")
        self.assertEqual(rows[0]["subclass"], "unknown")
        with self.assertRaises(ev.ContractError):
            ev.session_metadata("sb025_20191007", ["EC"], 2)


if __name__ == "__main__":
    unittest.main()
