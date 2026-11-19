"""Generated actual-path controls for the two Figure3b continuous outcomes.

Run standalone after integration: python -I -B test_outcomes.py
The parent source campaign may call configure(legacy_root, artifact_root) first.
All42-cell inputs are invented and remain in memory; no original body is read.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import types
import unittest

HERE = Path(__file__).absolute().parent
LEGACY_ROOT = HERE.parent
OUTCOME_BYTES = 15279
OUTCOME_SHA256 = "e1537d1a69a94e2ee3f64a90c2dc428d81c85d54ce3623866b6f4c44130b1591"
COLLECTION_SHA = "a"*64
SESSIONS = ("p1_1","p1_2","p2_1","p2_2","p3_1","p3_2","p4_1",
            "p5_1","p5_2","p6_1","p7_1","p7_2","p8_1","p8_2")
GENERATED_STOP = 8*1024**2
GENERATED_BYTES = 0
COMPOSITIONS = 0
TEST_SOURCE_BYTES = 0
MODULE = None


def configure(legacy_root, artifact_root):
    """Only test dependency routing; artifact_root intentionally unused."""
    global LEGACY_ROOT, MODULE
    LEGACY_ROOT = Path(legacy_root).absolute()
    MODULE = None


def _load():
    global MODULE, TEST_SOURCE_BYTES
    if MODULE is not None:
        return MODULE
    path = HERE/"outcomes.py"
    if any(p.is_symlink() for p in (path,*path.parents)):
        raise ValueError("No test outcome source symlink")
    fd = os.open(path,os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)|getattr(os,"O_NONBLOCK",0))
    with os.fdopen(fd,"rb") as stream:
        before = os.fstat(stream.fileno())
        if not(stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_size==OUTCOME_BYTES):
            raise ValueError("Exact bounded outcome source")
        raw = stream.read(OUTCOME_BYTES+1)
        TEST_SOURCE_BYTES += len(raw)
        stamp = lambda s:(s.st_dev,s.st_ino,s.st_mode,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
        if not(len(raw)==OUTCOME_BYTES and hashlib.sha256(raw).hexdigest()==OUTCOME_SHA256
               and stamp(before)==stamp(os.fstat(stream.fileno()))==stamp(path.lstat())):
            raise ValueError("Pinned stable actual outcome code")
    module = types.ModuleType("_language_generated_dual_outcomes")
    module.__file__,module.__package__ = str(path),""
    exec(compile(raw,str(path),"exec",dont_inherit=True),module.__dict__)
    MODULE = module
    return module


def _charge(raw):
    global GENERATED_BYTES
    if type(raw) is not bytes or GENERATED_BYTES+len(raw)>GENERATED_STOP:
        raise ValueError("Finite generated serialization reservation")
    GENERATED_BYTES += len(raw)


def _hash(module,value):
    return hashlib.sha256(module.encoded(value)).hexdigest()


def _contexts():
    return [{"session":session,"field":"population","family":"context","layer":5,
             "lag_index":lag,"lag_bins":lag-20} for session in SESSIONS for lag in (17,18,19)]


def _recovery(candidate=None, reference=None, *, reference_ints=False):
    m = _load()
    endpoint = m._load_endpoint(LEGACY_ROOT)
    candidate = [0.0]*42 if candidate is None else candidate
    reference = [0.0]*42 if reference is None else reference
    if len(candidate)!=42 or len(reference)!=42:
        raise ValueError("Bounded complete generated fixture")
    def packet(role, numbers):
        if role=="provided_author_reference" and reference_ints:
            values = list(numbers)
        else:
            values = [None if x is None else float(x) for x in numbers]
        return {"schema":"language-original-figure3b-scores/v1","role":role,
                "selection_sha256":_hash(endpoint,endpoint.selection()),
                "source_support_sha256":m.SOURCE_SUPPORT_SHA256,
                "prediction_run_sha256":COLLECTION_SHA if role=="candidate" else m.REFERENCE_SOURCE_SHA256,
                "scores":[{"context":context,"pearson_r":number}
                          for context,number in zip(_contexts(),values)],
                "execution_qualified":False}
    c,r = packet("candidate",candidate),packet("provided_author_reference",reference)
    comparison = endpoint.compare(c,r)
    value = {
        "schema":"language-selected-figure3b-recovery/v1","scope":"original_figure3b_improvement",
        "collection_sha256":COLLECTION_SHA,
        "authorities":{"jobs":42,"requests":5685,"read_bytes_charged":100,
                       "exact_authority_recovered":True,"scientific_qualification":False},
        "packed":{"jobs":42,"requests":5685,"read_bytes":200,
                  "all_numeric_predictions_recovered":True,"protected_execution_qualified":False,
                  "provider_journal_independently_verified":False,"scientific_qualification":False,
                  "compact_request_identity_join_verified":True,"scope":"original_figure3b_improvement"},
        "result":{"candidate_scores":c,"paired_difference":comparison,
                  "reference_packet_sha256":_hash(endpoint,r),
                  "reference_status":"provided-author-values only; same-stack baseline computation not qualified",
                  "full_224_array_reproduction_executed":False},
        "original_result_arrays":None,"protected_execution_qualified":False,"scientific_qualification":False}
    _charge(m.encoded(value))
    return value


def _compose(value, *, condition="paper_data", collection_sha256=COLLECTION_SHA, recovery_sha256=None):
    global COMPOSITIONS
    m = _load()
    raw = m.encoded(value)
    _charge(raw)
    COMPOSITIONS += 1
    result = m.compose_recovered(value,condition=condition,collection_sha256=collection_sha256,
        recovery_sha256=hashlib.sha256(raw).hexdigest() if recovery_sha256 is None else recovery_sha256,
        source_root=LEGACY_ROOT)
    _charge(m.encoded(result))
    return result


def control_accounting():
    endpoint = {} if MODULE is None else MODULE.source_read_metrics()
    return {"generated_only":True,"test_owned_source_bytes":TEST_SOURCE_BYTES,
            "endpoint_source":endpoint,"generated_serialized_memory_bytes":GENERATED_BYTES,
            "generated_serialized_memory_stop_bytes":GENERATED_STOP,
            "wrapper_counted_composition_attempts":COMPOSITIONS,
            "direct_invalid_tree_admissions_counted":False,"fixture_disk_bytes":0,
            "original_body_bytes":0,"model_fits":0,"network_requests":0,
            "subprocesses":0,"runtime_standard_library_import_reads_metered":False}


class OutcomeControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        cls.endpoint = cls.m._load_endpoint(LEGACY_ROOT)

    def test_01_both_arms_share_all42_zero_difference_cells(self):
        value = _recovery()
        before = self.m.encoded(value)
        arms = [_compose(value,condition=condition) for condition in self.m.CONDITIONS]
        for condition,result in zip(("paper_data","paper_data_author_code"),arms):
            self.assertEqual(result["condition"],condition)
            cells = result["reproduction"]["cells"]
            self.assertEqual([r["context"] for r in cells],_contexts())
            self.assertEqual(len(cells),42)
            self.assertEqual(len(result["reproduction"]["sessions"]),14)
            self.assertEqual(len(result["improvement"]["participants"]),8)
            self.assertEqual(result["reproduction"]["defined_cell_pairs"],42)
            self.assertTrue(all(r["signed_difference"]==0.0 and r["absolute_difference"]==0.0 for r in cells))
            self.assertEqual(result["reproduction"]["equal_session_signed_difference"],0.0)
            self.assertEqual(result["improvement"]["equal_session_paired_mean_delta"],0.0)
            self.assertTrue(result["shared_frozen_candidate_predictions"])
        self.assertEqual(arms[0]["reproduction"],arms[1]["reproduction"])
        self.assertEqual(arms[0]["improvement"],arms[1]["improvement"])
        self.assertEqual(arms[0]["lineage"],arms[1]["lineage"])
        self.assertEqual(self.m.encoded(value),before)

    def test_02_manual_unequal_session_positive_effect_not_equal_people(self):
        candidate = [float(x) for i in range(14) for x in
                     ((Fraction(1,4),Fraction(1,2),Fraction(3,4)) if i<2
                      else (Fraction(0),Fraction(1,4),Fraction(1,2)))]
        reference = [0.0,0.125,0.25]*14
        result = _compose(_recovery(candidate,reference))
        sessions = result["reproduction"]["sessions"]
        self.assertEqual([r["signed_difference"] for r in sessions],[0.375]*2+[0.125]*12)
        expected = Fraction(2,14)*Fraction(3,8)+Fraction(12,14)*Fraction(1,8)
        self.assertEqual(expected,Fraction(9,56))
        self.assertAlmostEqual(result["reproduction"]["equal_session_signed_difference"],float(expected),places=14)
        self.assertAlmostEqual(result["improvement"]["equal_session_paired_mean_delta"],float(expected),places=14)
        self.assertNotAlmostEqual(float(expected),float(Fraction(5,32)),places=10)
        self.assertEqual([r["signed_difference"] for r in result["reproduction"]["cells"][:3]],[.25,.375,.5])
        self.assertAlmostEqual(sum(r["contribution_to_equal_session_delta"]
                                   for r in result["improvement"]["participants"]),float(expected),places=14)

    def test_03_negative_signed_and_positive_absolute_differences(self):
        result = _compose(_recovery([-.25,0.0,.25]*14,[.5]*42))
        cells = result["reproduction"]["cells"]
        self.assertEqual([x["signed_difference"] for x in cells],[-.75,-.5,-.25]*14)
        self.assertEqual([x["absolute_difference"] for x in cells],[.75,.5,.25]*14)
        self.assertEqual(result["reproduction"]["equal_session_signed_difference"],-.5)
        self.assertEqual(result["improvement"]["equal_session_paired_mean_delta"],-.5)
        self.assertIsNone(result["improvement"]["binary_win"])
        self.assertIsNone(result["reproduction"]["binary_reproduction"])

    def test_04_undefined_either_side_propagates_without_dropping(self):
        candidate,reference = [.25]*42,[.125]*42
        candidate[0]=None
        reference[-1]=None
        result = _compose(_recovery(candidate,reference))
        reproduction = result["reproduction"]
        self.assertEqual(len(reproduction["cells"]),42)
        self.assertEqual(reproduction["defined_cell_pairs"],40)
        self.assertEqual(reproduction["defined_session_pairs"],12)
        for index in (0,41):
            self.assertIsNone(reproduction["cells"][index]["signed_difference"])
            self.assertIsNone(reproduction["cells"][index]["absolute_difference"])
        self.assertIsNone(reproduction["sessions"][0]["signed_difference"])
        self.assertIsNone(reproduction["sessions"][-1]["signed_difference"])
        self.assertIsNone(reproduction["equal_session_signed_difference"])
        self.assertIsNone(result["improvement"]["equal_session_paired_mean_delta"])
        self.assertIsNone(result["improvement"]["participants"][0]["contribution_to_equal_session_delta"])
        self.assertIsNone(result["improvement"]["participants"][-1]["contribution_to_equal_session_delta"])

    def test_05_complete_all_undefined_is_not_a_zero_or_partial_success(self):
        result = _compose(_recovery([None]*42,[None]*42))
        self.assertEqual(result["reproduction"]["defined_cell_pairs"],0)
        self.assertEqual(result["reproduction"]["defined_session_pairs"],0)
        self.assertEqual(len(result["reproduction"]["cells"]),42)
        self.assertEqual(len(result["reproduction"]["sessions"]),14)
        self.assertIsNone(result["reproduction"]["candidate_equal_session_mean"])
        self.assertIsNone(result["reproduction"]["provided_author_equal_session_mean"])
        self.assertIsNone(result["reproduction"]["equal_session_signed_difference"])
        self.assertFalse(result["scientific_qualification"])

    def test_06_missing_duplicate_reordered_foreign_candidate_cells_refuse(self):
        base = _recovery()
        for fault in ("missing","duplicate","reordered","foreign_session","wrong_layer","wrong_lag"):
            with self.subTest(fault=fault):
                value = copy.deepcopy(base)
                rows = value["result"]["candidate_scores"]["scores"]
                if fault=="missing":rows.pop()
                elif fault=="duplicate":rows[1]=copy.deepcopy(rows[0])
                elif fault=="reordered":rows[0],rows[1]=rows[1],rows[0]
                elif fault=="foreign_session":rows[0]["context"]["session"]="p9_1"
                elif fault=="wrong_layer":rows[0]["context"]["layer"]=6
                else:rows[0]["context"]["lag_index"]=20
                with self.assertRaises(ValueError):_compose(value)

    def test_07_caller_comparison_scalar_and_session_mutations_refuse(self):
        base = _recovery()
        for fault in ("scalar","participant","missing","duplicate","foreign","candidate_value","reference_value","extra"):
            with self.subTest(fault=fault):
                value = copy.deepcopy(base)
                pair = value["result"]["paired_difference"]
                if fault=="scalar":pair["equal_session_paired_mean_delta"]=.75
                elif fault=="participant":pair["participants"][0]["participant_mean_diagnostic"]=.25
                elif fault=="missing":pair["sessions"].pop()
                elif fault=="duplicate":pair["sessions"][1]=copy.deepcopy(pair["sessions"][0])
                elif fault=="foreign":pair["sessions"][0]["session"]="p9_1"
                elif fault=="candidate_value":pair["sessions"][0]["candidate_lag_correlations"][0]=.25
                elif fault=="reference_value":pair["sessions"][0]["author_lag_correlations"][0]=.25
                else:pair["invented_pass"]=True
                with self.assertRaises(ValueError):_compose(value)

    def test_08_support_reference_and_prediction_identities_refuse_mutation(self):
        base = _recovery()
        for fault in ("support","packet_reference","pair_reference","prediction_run","candidate_role","selection"):
            with self.subTest(fault=fault):
                value = copy.deepcopy(base)
                candidate=value["result"]["candidate_scores"]
                if fault=="support":
                    candidate["source_support_sha256"]="b"*64
                    value["result"]["paired_difference"]["source_support_sha256"]="b"*64
                elif fault=="packet_reference":value["result"]["reference_packet_sha256"]="b"*64
                elif fault=="pair_reference":value["result"]["paired_difference"]["reference_packet_sha256"]="b"*64
                elif fault=="prediction_run":candidate["prediction_run_sha256"]="b"*64
                elif fault=="candidate_role":candidate["role"]="provided_author_reference"
                else:candidate["selection_sha256"]="b"*64
                with self.assertRaises(ValueError):_compose(value)

    def test_09_partial_recovery_and_qualification_promotion_refuse(self):
        base = _recovery()
        changes = [
            ("authorities","jobs",41),("authorities","requests",5684),
            ("authorities","exact_authority_recovered",False),
            ("packed","jobs",41),("packed","requests",True),
            ("packed","all_numeric_predictions_recovered",False),
            ("packed","compact_request_identity_join_verified",False),
            ("packed","provider_journal_independently_verified",True),
            ("packed","protected_execution_qualified",True)]
        for group,key,number in changes:
            with self.subTest(group=group,key=key):
                value=copy.deepcopy(base);value[group][key]=number
                with self.assertRaises(ValueError):_compose(value)
        for fault in ("root_science","original_arrays","candidate_qualified"):
            value=copy.deepcopy(base)
            if fault=="root_science":value["scientific_qualification"]=True
            elif fault=="original_arrays":value["original_result_arrays"]=[]
            else:value["result"]["candidate_scores"]["execution_qualified"]=True
            with self.assertRaises(ValueError):_compose(value)

    def test_10_invalid_numeric_and_bounded_tree_admission_refuse(self):
        base = _recovery()
        for number in (True,1.001,-1.001,float("nan"),float("inf")):
            with self.subTest(number=number):
                value=copy.deepcopy(base)
                value["result"]["candidate_scores"]["scores"][0]["pearson_r"]=number
                with self.assertRaises(ValueError):
                    if type(number) is float and not math.isfinite(number):
                        self.m.compose_recovered(value,condition="paper_data",collection_sha256=COLLECTION_SHA,
                            recovery_sha256="f"*64,source_root=LEGACY_ROOT)
                    else:_compose(value)
        for malformed in ({"oversized":"x"*4097},{"too_many":[None]*129},{"unsupported":object()}):
            with self.assertRaises(ValueError):
                self.m.compose_recovered(malformed,condition="paper_data",collection_sha256=COLLECTION_SHA,
                    recovery_sha256="f"*64,source_root=LEGACY_ROOT)
        cyclic={};cyclic["self"]=cyclic
        with self.assertRaises(ValueError):
            self.m.compose_recovered(cyclic,condition="paper_data",collection_sha256=COLLECTION_SHA,
                recovery_sha256="f"*64,source_root=LEGACY_ROOT)

    def test_11_condition_collection_recovery_hash_and_detachment(self):
        base = _recovery()
        for condition in ("paper_only","author_code",None,True):
            with self.assertRaises(ValueError):_compose(base,condition=condition)
        with self.assertRaises(ValueError):_compose(base,collection_sha256="b"*64)
        with self.assertRaises(ValueError):_compose(base,recovery_sha256="b"*64)
        with self.assertRaises(ValueError):_compose(base,recovery_sha256="A"*64)
        before=self.m.encoded(base)
        result=_compose(base,condition="paper_data_author_code")
        result["reproduction"]["cells"][0]["context"]["session"]="mutated"
        result["improvement"]["sessions"][0]["candidate_lag_correlations"][0]=.9
        self.assertEqual(self.m.encoded(base),before)

    def test_12_original_lineage_and_no_invented_reproduction_threshold(self):
        value=_recovery()
        result=_compose(value)
        self.assertEqual(result["selection"],self.endpoint.selection())
        self.assertEqual(result["selection"]["scope"],"original_figure3b_population_improvement")
        self.assertEqual(result["mode"],"original_figure3b_reproduction_and_improvement")
        self.assertEqual(result["improvement"],value["result"]["paired_difference"])
        self.assertEqual(result["lineage"]["provided_reference_source_sha256"],self.m.REFERENCE_SOURCE_SHA256)
        self.assertEqual(result["lineage"]["source_support_sha256"],self.m.SOURCE_SUPPORT_SHA256)
        self.assertFalse(result["lineage"]["reference_packet_reexecution"])
        self.assertFalse(result["lineage"]["upstream_physical_execution_independently_verified_here"])
        self.assertFalse(result["full_224_array_reproduction_executed"])
        self.assertFalse(result["representation_scope"]["self_FR_579_crosswalk_is_gate_for_this_same_support_comparison"])
        self.assertIsNone(result["reproduction"]["tolerance"])
        self.assertIsNone(result["reproduction"]["binary_reproduction"])
        self.assertIsNone(result["improvement"]["meaningful_effect_criterion"])
        self.assertIsNone(result["improvement"]["uncertainty_method"])
        self.assertEqual(result["additional_model_calls"],0)
        self.assertFalse(result["new_resampling"])
        # compare preserves float values but not an original int JSON spelling.
        # The direct helper must refuse an unreconstructable packet, never guess.
        ambiguous=_recovery(reference=[0]*42,reference_ints=True)
        with self.assertRaisesRegex(ValueError,"reference packet identity"):
            _compose(ambiguous)


if __name__ == "__main__":
    unittest.main()
