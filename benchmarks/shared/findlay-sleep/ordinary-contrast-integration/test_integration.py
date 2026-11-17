"""Generated complete-shape controls; never read authentic observations."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import resource
import sys
import tempfile
import time
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SEM = HERE.parent / "findlay-identity-contrast-semantics-source-20261115-v1"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY = load("ordinary_policy_test", SEM / "contrast/ordinary_contrast_policy.py")
POLICY.configure_private_policy({"ordinary_exclusion": {"subject": "invented-excluded-subject", "experiment": "Novelty", "columns": sorted(POLICY.EXCLUDED_COLUMNS)}})
CORE = load("ordinary_core_test", HERE / "ordinary_reconciliation.py")
TAIL = load("ordinary_tail_test", HERE / "census_tail.py")
WORKER = load("ordinary_worker_test", HERE / "worker.py")
CENSUS = load("ordinary_census_test", SEM / "identity/census.py")


def fixture():
    subjects = ["invented-excluded-subject"] + ["invented-subject-%02d" % n for n in range(15)]
    sessions = [(s, "Novelty") for s in subjects] + [(s, "Locomotion") for s in subjects[:13]]
    variables = sorted({v[0] for v in POLICY.DEFINITIONS.values()})
    conditions = {"Early.REC.NREM": 4.0, "Late.REC.NREM": 1.0,
                  "Early.BSL.NREM": 2.0, "Late.BSL.NREM": 0.5}
    measures, contrasts = [], []
    for subject, experiment in sessions:
        for condition, value in conditions.items():
            if (subject, experiment, condition) == ("invented-excluded-subject", "Novelty", "Late.BSL.NREM"):
                continue
            measures.append({"subject": subject, "experiment": experiment, "condition": condition,
                             **{v: value for v in variables}})
        row = {"subject": subject, "experiment": experiment}
        for column, (_, plus, minus) in POLICY.DEFINITIONS.items():
            # Independent hand arithmetic: 4-.5=3.5, 4-1=3,
            # 4-2=2, 2-.5=1.5. These are exact in binary32/64.
            row[column] = conditions[plus] - conditions[minus]
            if (subject, experiment) == ("invented-excluded-subject", "Novelty") and column in POLICY.EXCLUDED_COLUMNS:
                row[column] = None
        contrasts.append(row)
    while len(measures) < 344:
        measures.append({"subject": subjects[-1], "experiment": "Novelty",
                         "condition": "invented-outside-%03d" % len(measures),
                         **{v: 0.0 for v in variables}})
    def fields(names, source):
        return [{"name": n, "type": ("string" if n in ("subject", "experiment", "condition")
                 else "float" if n == "Cortical.SWA" or n.startswith("Cortical.SWA.") else "double"),
                 "nullable": True} for n in names]
    return measures, contrasts, fields(measures[0], True), fields(contrasts[0], False)


class ReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.m, self.t, self.ms, self.ts = fixture()

    def score(self):
        return CORE.reconcile(self.m, self.t, self.ms, self.ts, policy=POLICY)

    def test_complete_783_positions_and_thirteen_exclusions(self):
        out = self.score()
        self.assertEqual(out["status_counts"], {"expected_export_exclusion": 13, "exact_match": 770})
        self.assertTrue(out["all_target_cells_reconciled"])
        self.assertEqual((out["source_rows"], out["target_rows"], len(out["cells"])), (344, 29, 783))
        self.assertFalse(out["scientific_ready"])

    def test_float32_subtraction_is_not_binary64(self):
        for row in self.m:
            if (row["subject"], row["experiment"]) == ("invented-subject-00", "Novelty"):
                if row["condition"] == "Early.REC.NREM": row["Cortical.SWA"] = 100000000.0
                if row["condition"] == "Late.BSL.NREM": row["Cortical.SWA"] = 1.0
        row = next(x for x in self.t if x["subject"] == "invented-subject-00" and x["experiment"] == "Novelty")
        row["Cortical.SWA.Rebound"] = 100000000.0
        out = self.score()
        cell = next(x for x in out["cells"] if x["target_row"] == self.t.index(row) and x["column"] == "Cortical.SWA.Rebound")
        self.assertEqual((cell["status"], cell["reconstructed"]), ("exact_match", 100000000.0))

    def test_wrong_sign_remains_numeric_mismatch(self):
        self.t[-1]["SPW.Rate.REC.Decline"] = -3.0
        out = self.score()
        self.assertEqual(out["status_counts"]["numeric_mismatch"], 1)
        self.assertFalse(out["all_target_cells_reconciled"])
        self.assertEqual(len(out["cells"]), 783)

    def test_finite_exclusion_is_failure_not_imputation(self):
        self.t[0]["SPW.Rate.Rebound"] = 0.0
        self.assertEqual(self.score()["status_counts"]["export_exclusion_mismatch"], 1)

    def test_nan_exclusion_is_not_numerical_match(self):
        self.t[0]["SPW.Rate.Rebound"] = float("nan")
        self.assertEqual(self.score()["expected_exclusions"], 13)

    def test_duplicate_target_cannot_hide_under_exclusion(self):
        self.t[-1] = copy.deepcopy(self.t[0])
        out = self.score()
        self.assertEqual(out["status_counts"]["duplicate_target_key"], 54)
        self.assertNotIn("expected_export_exclusion", out["status_counts"])

    def test_duplicate_source_cannot_hide_under_exclusion(self):
        self.m[-1] = copy.deepcopy(self.m[0])
        out = self.score()
        self.assertGreater(out["status_counts"]["duplicate_source_condition"], 0)
        self.assertFalse(out["all_target_cells_reconciled"])

    def test_invalid_unused_identity_is_retained_failure(self):
        self.m[-1]["subject"] = True
        out = self.score()
        self.assertEqual(out["invalid_source_identity_rows"], [343])
        self.assertFalse(out["all_target_cells_reconciled"])

    def test_invalid_target_identity_retains_every_cell(self):
        self.t[-1]["subject"] = None
        out = self.score()
        self.assertEqual(out["status_counts"]["missing_or_invalid_target_identity"], 27)
        self.assertEqual(len(out["cells"]), 783)

    def test_missing_source_is_not_an_expected_exclusion(self):
        self.m[0]["condition"] = "invented-unrelated-condition"
        self.assertGreater(self.score()["status_counts"]["missing_source_condition"], 0)

    def test_bad_counts_and_missing_columns_refuse_before_arithmetic(self):
        for part in ("m", "t"):
            with self.subTest(part=part):
                original = getattr(self, part); setattr(self, part, original[:-1])
                with self.assertRaises(ValueError): self.score()
                setattr(self, part, original)
        del self.t[0]["SPW.Rate.Rebound"]
        with mock.patch.object(POLICY, "subtract_source_dtype", side_effect=AssertionError("arithmetic forbidden")):
            with self.assertRaises(ValueError): self.score()

    def test_wrong_schema_and_duplicate_schema_refuse(self):
        self.ts.append(copy.deepcopy(self.ts[-1]))
        with self.assertRaises(ValueError): self.score()
        self.ts.pop()
        next(x for x in self.ms if x["name"] == "Cortical.SWA")["type"] = "double"
        with self.assertRaises(ValueError): self.score()

    def test_nonfinite_boolean_and_unrepresentable_values(self):
        for v in (float("inf"), float("nan"), True, 3):
            with self.subTest(v=v):
                self.t[-1]["SPW.Rate.Rebound"] = v
                self.assertEqual(self.score()["status_counts"]["missing_or_nonfinite_value"], 1)
        self.t[-1]["SPW.Rate.Rebound"] = 3.5
        self.t[-1]["Cortical.SWA.Rebound"] = 1.0000000001
        self.assertEqual(self.score()["status_counts"]["unsupported_source_dtype_value"], 1)

    def test_reordered_rows_preserve_keyed_reconciliation(self):
        self.m.reverse();self.t.reverse()
        self.assertEqual(self.score()["status_counts"], {"exact_match": 770, "expected_export_exclusion": 13})


class Budget:
    def __init__(self, *args, **kwargs):
        self.written = {};self.read_bytes = 0;self.write_bytes = 0;self.outputs = []
    def check(self): pass
    def write_json(self, name, value):
        self.written[name] = value
        return {"path": name, "bytes": len(json.dumps(value)), "sha256": "0" * 64}


class CompositionTests(unittest.TestCase):
    def test_real_complete_tail_routes_all_98_and_both_reports(self):
        m, t, ms, ts = fixture()
        names = list(CENSUS.TABLES)
        data = {name: [] for name in names}
        data.update({"condition_measures.pqt": m, "condition_contrasts.pqt": t,
                     "multicortical_condition_measures.pqt": [{"subject": "invented", "experiment": "Novelty", "acronym": "X", "spw_probe": False, "region": "X", "condition": "Early.REC.NREM", "Cortical.iEta": 1.0}],
                     "multicortical_condition_contrasts.pqt": [{"subject": "invented", "experiment": "Novelty", "acronym": "X", "spw_probe": False, "region": "X", "Cortical.iEta.Rebound": 1.0}]})
        reports = {n: {"table": n, "all_decoded_rows_accounted": True, "rows": len(data[n]),
                       "group_rows_total": len(data[n]), "managed_read_bytes": 0, "readiness_gates": [],
                       "schema": ms if n == "condition_measures.pqt" else ts if n == "condition_contrasts.pqt" else []}
                   for n in names}
        prior = {n: {"report": reports[n], "pin": {"path": "invented/"+n}} for n in names}
        ledger = {"members": [{"path": n, "footer_advertised_rows": len(data[n])} for n in names]}
        class Acc:
            def finish(self): return {"census_rows_complete": True}
        class Book:
            ids = list(range(98))
            def new_accumulator(self, identifier): return Acc()
            def tables_for(self, identifier): return names
            def assess_schema(self, identifier): return {"invented": True}
        fake_rules = types.SimpleNamespace(build_rules=lambda *args: Book())
        fake_census = types.SimpleNamespace(TABLES=names, SMALL=CENSUS.SMALL,
            _table_census=lambda root, member, *args: (copy.deepcopy(reports[member["path"]]), data[member["path"]]),
            _default_parquet=lambda *a: self.fail("native decoder forbidden"),
            reconcile_contrasts=CENSUS.reconcile_contrasts)
        budget = Budget()
        result = TAIL.resume_tail(Path("/invented"), ledger, {}, budget, prior,
                                 census_module=fake_census, rules_module=fake_rules,
                                 ordinary_module=CORE, ordinary_policy=POLICY)
        self.assertEqual((result["table_count"], result["family_count"]), (13, 98))
        self.assertEqual(len(budget.written["family-support-98.private.json"]["families"]), 98)
        self.assertEqual(budget.written["condition-reconstruction.private.json"]["numeric_matches"], 770)
        regional = budget.written["multicortical_condition-reconstruction.private.json"]
        self.assertEqual(regional["status_counts"], {"unresolved_source_definition": 1})
        self.assertFalse(result["scientific_ready"])
        self.assertTrue(any(x["scope"] == "multicortical_condition" for x in result["readiness_gates"]))

    def test_worker_passes_real_reconciliation_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            admission = {"request": {"task": {"input_ledger": {}, "published_families": {},
                "data_read_cap": 33554432, "worker_output_cap": 33554432, "prior_attempt": {}, "private_policy": {}}},
                "source_read_bytes": 0, "runtime_join_read_bytes": 0, "receipt_read_bytes": 0,
                "output_root": tmp, "work_deadline": 1e30}
            def ledger(_task, key, *_args):
                return {"member_count": 17, "parquet_member_count": 13, "static_subjects": 16,
                        "static_sessions": 29} if key == "input_ledger" else {}
            def tail(*args, **kw):
                self.assertIs(kw["ordinary_module"], CORE);self.assertIs(kw["ordinary_policy"], POLICY)
                return {"status": "COMPLETE_INTAKE_CENSUS_WITH_GATES", "table_count": 13,
                        "family_count": 98, "all_tables_and_families_accounted": True,
                        "scientific_ready": False, "models_fitted": 0}
            with mock.patch.object(WORKER, "ledger", side_effect=ledger), mock.patch.object(
                    WORKER, "admit_prior", return_value=(Path(tmp), {}, {}, {})):
                result = WORKER.operate(admission, types.SimpleNamespace(Budget=Budget), CENSUS, None,
                    types.SimpleNamespace(resume_tail=tail), lambda: {"invented": True}, CORE, POLICY)
            self.assertEqual(result["all_families"], 98)
            self.assertFalse(result["scientific_qualification"])

    def test_complete_source_graph_pins_new_and_accepted_dependencies(self):
        lock = json.loads((REPO / "components/findlay-complete-preparation/SOURCE_MANIFEST.json").read_text())
        self.assertEqual(len(lock["files"]), 14)
        for path, pin in lock["files"].items():
            body = (REPO / path).read_bytes()
            self.assertEqual((len(body), hashlib.sha256(body).hexdigest()), (pin["bytes"], pin["sha256"]))
        self.assertFalse(lock["execution_authority"])
        self.assertIn(lock["worker"]["path"].rsplit("/",1)[0] + "/ordinary_reconciliation.py", lock["files"])


if __name__ == "__main__":
    started=time.monotonic(); cpu=time.process_time()
    suite=unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"tests": result.testsRun, "passed": result.wasSuccessful(),
        "generated_only": True, "elapsed_seconds": time.monotonic()-started,
        "cpu_seconds": time.process_time()-cpu, "maxrss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "maxrss_units": "bytes" if sys.platform == "darwin" else "KiB",
        "native_imported": any(x in sys.modules for x in ("numpy", "pyarrow", "pandas"))}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
