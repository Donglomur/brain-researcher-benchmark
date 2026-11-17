"""Generated software controls only; no source EEG or historical private targets."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("full_cohort_score", HERE / "score.py")
s = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(s)


class FullCohortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gen = "c" * 64
        cls.rows = []
        cls.assets = []
        cls.expected_correct = {}
        cls.answer = {}
        for p in range(1, 55):
            for session in (1, 2):
                for phase_index, phase in enumerate(("train", "test")):
                    cell = []
                    correct = 0
                    for label in range(1, 5):
                        cutoff = (p + session + phase_index + label) % 26
                        correct += cutoff
                        for trial in range(25):
                            identity = hashlib.sha256(
                                f"generated-control:{p}:{session}:{phase}:{label}:{trial}".encode()).hexdigest()
                            cell.append(dict(id=identity, person=p, session=session, phase=phase, label=label))
                            cls.answer[identity] = label if trial < cutoff else label % 4 + 1
                    cls.expected_correct[(p, session, phase)] = correct
                    cell.sort(key=lambda row: row["id"])
                    cls.rows.extend(cell)
                    cls.assets.append(dict(person=p, session=session, phase=phase,
                        signals=dict(path=f"p{p:02d}-s{session}-{phase}.npy", bytes=1600128, sha256="0" * 64),
                        ids=[row["id"] for row in cell]))
        cls.gold = dict(schema="neural084_gold_v1", generation=cls.gen, rows=cls.rows)
        cls.gold_raw = s.io.canonical(cls.gold)
        cls.pool = dict(schema="neural084_pool_v1", generation=cls.gen, assets=cls.assets,
                        gold=dict(path="gold.json", **s.io.pin(cls.gold_raw)))
        cls.pool_raw = s.io.canonical(cls.pool)
        cls.folds = {f"fold{p:03d}": sorted(
            (row for row in cls.rows if row["person"] == p), key=lambda row: row["id"])
            for p in range(1, 55)}
        cls.outputs = {}
        for mode in s.MODES:
            cls.outputs[mode] = {}
            for fold, rows in cls.folds.items():
                predictions = []
                for row in rows:
                    if mode == "constant":
                        scores = [-7.5] * 4
                    else:
                        predicted = cls.answer[row["id"]] if mode == "candidate" else row["label"]
                        scores = [-3.0] * 4
                        scores[predicted - 1] = -0.5
                        if mode == "frequency-permuted":
                            scores = scores[1:] + scores[:1]
                    predictions.append(dict(id=row["id"], scores=scores))
                cls.outputs[mode][fold] = s.io.canonical(dict(schema="neural084_scores_v1",
                    generation=cls.gen, fold=fold, predictions=predictions))

    def test_full_endpoint_and_independent_integer_count_oracle(self):
        calls = []
        def load(mode, fold):
            calls.append((mode, fold))
            return self.outputs[mode][fold]
        def gold(pin):
            self.assertEqual(len(calls), 216)
            self.assertEqual(pin, s.io.pin(self.gold_raw))
            return self.gold_raw
        result = s.grade(self.pool_raw, load, gold)
        candidate = result["modes"]["candidate"]
        self.assertEqual(len(candidate["phases"]), 216)
        self.assertEqual(len(candidate["sessions"]), 108)
        self.assertEqual(len(candidate["people"]), 54)
        self.assertEqual(candidate["support"], [5400] * 4)
        self.assertAlmostEqual(candidate["score"], sum(self.expected_correct.values()) / 21600)
        for row in candidate["phases"]:
            self.assertEqual(row["support"], [25] * 4)
            expected = self.expected_correct[(row["person"], row["session"], row["phase"])]
            self.assertAlmostEqual(row["score"], expected / 100)
            self.assertEqual(sum(row["confusion"][i][i] for i in range(4)), expected)
        for row in candidate["people"]:
            expected = sum(n for (p, _, _), n in self.expected_correct.items() if p == row["person"])
            self.assertAlmostEqual(row["score"], expected / 400)
        for mode, expected in (("cca", 1), ("constant", .25), ("frequency-permuted", 0)):
            self.assertEqual(result["modes"][mode]["score"], expected)
            self.assertAlmostEqual(result["candidate_minus"][mode]["mean"], candidate["score"] - expected)
            self.assertEqual(len(result["candidate_minus"][mode]["people"]), 54)
        self.assertEqual(result["modes"]["constant"]["confusion"], [[5400, 0, 0, 0]] * 4)
        # Operator report contains no trial rows, target values or opaque query IDs.
        self.assertNotIn(self.rows[0]["id"], s.io.canonical(result).decode())

    def test_late_invalid_reference_prevents_any_gold_access(self):
        def load(mode, fold):
            if (mode, fold) == ("frequency-permuted", "fold054"):
                value = s.io.decode(self.outputs[mode][fold])
                value["predictions"][-1]["scores"][-1] = True
                return s.io.canonical(value)
            return self.outputs[mode][fold]
        with self.assertRaises(ValueError):
            s.grade(self.pool_raw, load, lambda _: self.fail("Gold opened before full validation"))

    def test_missing_last_fold_prevents_gold_access(self):
        def load(mode, fold):
            if (mode, fold) == ("candidate", "fold054"):
                raise FileNotFoundError("generated missing fold")
            return self.outputs[mode][fold]
        with self.assertRaises(FileNotFoundError):
            s.grade(self.pool_raw, load, lambda _: self.fail("Gold opened on incomplete cohort"))

    def test_strict_prediction_contract_and_first_tie(self):
        raw = self.outputs["candidate"]["fold001"]
        value = s.io.decode(raw)
        identities = tuple(row["id"] for row in self.folds["fold001"])
        value["predictions"][0]["scores"] = [1, 8, 8, -2]
        self.assertEqual(s.prediction(s.io.canonical(value), self.gen, "fold001", identities)[0], 2)
        mutations = [
            lambda v: v.update(generation="wrong"), lambda v: v.update(fold="fold002"),
            lambda v: v.update(extra=1), lambda v: v["predictions"].pop(),
            lambda v: v["predictions"].reverse(),
            lambda v: v["predictions"][0].update(id=v["predictions"][1]["id"]),
            lambda v: v["predictions"][0].update(extra=1),
            lambda v: v["predictions"][0].update(scores=[0, 1, 2]),
            lambda v: v["predictions"][0].update(scores=[False, 0, 0, 0]),
            lambda v: v["predictions"][0].update(scores=[10**19, 0, 0, 0]),
            lambda v: v["predictions"][0].update(scores=["1", 0, 0, 0]),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutations.index(mutate)):
                changed = copy.deepcopy(value)
                mutate(changed)
                with self.assertRaises(ValueError):
                    s.prediction(s.io.canonical(changed), self.gen, "fold001", identities)
        for bad in (b'{"schema":0,"schema":1}', b"NaN", b"Infinity", b"1e999", b"\xff", b" " * (s.PRED_CAP + 1)):
            with self.subTest(raw=bad[:30]), self.assertRaises(ValueError):
                s.prediction(bad, self.gen, "fold001", identities)

    def test_pool_rejects_reduced_duplicated_or_wrongly_grouped_source(self):
        mutations = [lambda p: p["assets"].pop(),
                     lambda p: p["assets"].reverse(),
                     lambda p: p["assets"][0].update(person=True),
                     lambda p: p["assets"][1].update(ids=p["assets"][0]["ids"]),
                     lambda p: p["gold"].update(path="../gold.json"),
                     lambda p: p["assets"][0]["signals"].update(path="other.npy")]
        for mutate in mutations:
            value = copy.deepcopy(self.pool)
            mutate(value)
            with self.assertRaises(ValueError):
                s.pool_contract(s.io.canonical(value))

    def test_gold_checks_order_identity_support_and_types(self):
        _, _, source_rows, _ = s.pool_contract(self.pool_raw)
        mutations = [lambda g: g.update(generation="wrong"),
                     lambda g: g["rows"].pop(), lambda g: g["rows"].reverse(),
                     lambda g: g["rows"][0].update(label=True),
                     lambda g: g["rows"][0].update(person=2),
                     lambda g: g["rows"][0].update(label=g["rows"][0]["label"] % 4 + 1)]
        for mutate in mutations:
            value = copy.deepcopy(self.gold)
            mutate(value)
            raw = s.io.canonical(value)
            with self.assertRaises(ValueError):
                s.gold_contract(raw, self.gen, source_rows, s.io.pin(raw))
        with self.assertRaises(ValueError):
            s.gold_contract(self.gold_raw, self.gen, source_rows, dict(bytes=1, sha256="0" * 64))

    def test_existing_producer_contracts_accept_the_same_source_objects(self):
        source = HERE.parent / "sequential-programme/sequential-view-v2/program"
        def load(name):
            spec = importlib.util.spec_from_file_location("compat_" + name, source / (name + ".py"))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.c = types.SimpleNamespace(need=s.io.need,
                only_pin=lambda value: {k: value[k] for k in ("bytes", "sha256")})
            return module
        contracts = load("contracts")
        store = load("store")
        store.contracts = contracts
        records, files = store.metadata_join(self.pool, self.gold)
        self.assertEqual(len(records), 21600)
        self.assertEqual(len(files), 216)
        for fold, rows in self.folds.items():
            metadata = dict(generation=self.gen, fold=fold, ids=[r["id"] for r in rows])
            for mode in s.MODES:
                contracts.prediction(self.outputs[mode][fold], metadata)

    def test_cli_existing_source_schemas_and_exclusive_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            (root / "pool.json").write_bytes(self.pool_raw)
            (root / "gold.json").write_bytes(self.gold_raw)
            pin = s.io.pin(self.pool_raw)
            args = ["--pool", str(root / "pool.json"), "--pool-bytes", str(pin["bytes"]),
                    "--pool-sha256", pin["sha256"], "--out", str(root / "report.json")]
            for mode in s.MODES:
                folder = root / mode
                folder.mkdir()
                for fold, raw in self.outputs[mode].items():
                    (folder / (fold + ".json")).write_bytes(raw)
                args += ["--" + mode, str(folder)]
            self.assertEqual(s.main(args), 0)
            report = json.loads((root / "report.json").read_bytes())
            self.assertEqual(report["counts"], dict(people=54, phases=216, queries=21600, modes=4))
            with self.assertRaises(FileExistsError):
                s.main(args)
            (root / "candidate/extra.json").write_text("{}")
            with self.assertRaises(ValueError):
                s.main(args)


if __name__ == "__main__":
    unittest.main(verbosity=2)
