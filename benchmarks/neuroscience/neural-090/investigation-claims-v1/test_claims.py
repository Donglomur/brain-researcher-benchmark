"""Invented full-support scalar reports; no neural/model/reference payloads."""
import importlib.util
import itertools
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("claims", Path(__file__).with_name("claims.py"))
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
GROUPS = list(itertools.product(C.AXES, C.MODES, C.TRACKS, C.ARMS))


def loss(g, seed, person, chapter):
    return 1 + g / 1000 + seed * .003 + person * .0001 + chapter * .00001


def f1(g):
    return (.5 + g / 1000) / 39


def job(g, seed, person, chapter, with_track=True):
    (axis, budget), mode, track, arm = GROUPS[g]
    d = dict(axis=axis, budget=budget, mode=mode, arm=arm, person=str(person+1),
             chapter=str(chapter+11), seed=seed, case=f"{axis}/{person+1}/{chapter+11}/{budget}",
             target_exposure="protected" if arm in C.ARMS[:3] else "stimulus_exposed_diagnostic",
             person_condition_exposed=axis == "exposed_person")
    if with_track:
        d["track"] = track
    return d


def chapters():
    for g, seed, person, chapter in itertools.product(range(120), range(10), range(32), range(2)):
        yield dict(job(g, seed, person, chapter), query_rows=person+1,
                   log_loss=loss(g, seed, person, chapter), macro_f1_fixed39=f1(g),
                   per_class_support=[person+1]+[0]*38, per_class_f1=[.5+g/1000]+[0.]*38,
                   absent_class_rule="F1=0 when2TP+FP+FN=0")


def vectors():
    for g, seed in itertools.product(range(120), range(10)):
        (axis, budget), mode, track, arm = GROUPS[g]
        yield dict(axis=axis, budget=budget, mode=mode, track=track, arm=arm, seed=seed,
                   people=[dict(person=str(p+1), log_loss=loss(g, seed, p, .5),
                                macro_f1_fixed39=f1(g)) for p in range(32)],
                   log_loss=loss(g, seed, 15.5, .5), macro_f1_fixed39=f1(g))


def averages():
    for g in range(120):
        (axis, budget), mode, track, arm = GROUPS[g]
        yield dict(axis=axis, budget=budget, mode=mode, track=track, arm=arm,
                   log_loss=loss(g, 4.5, 15.5, .5), macro_f1_fixed39=f1(g))


def paired():
    for g, seed, person, chapter, control in itertools.product(range(0, 120, 5), range(10),
                                                              range(32), range(2), range(1, 5)):
        row = job(g, seed, person, chapter)
        yield dict(row, control=C.ARMS[control],
                   positive_improvement=loss(g+control, seed, person, chapter)-loss(g, seed, person, chapter),
                   contrast_status="protected_primary" if row["axis"] != "exposed_person" and control < 3
                   else "exposed_or_secondary_diagnostic")


def candidate():
    for g, seed, person, chapter in itertools.product(range(0, 120, 10), range(10), range(32), range(2)):
        yield dict(job(g, seed, person, chapter, False),
                   positive_improvement=loss(g+5, seed, person, chapter)-loss(g, seed, person, chapter))


def report():
    return dict(schema="n090-broad-point-report-v1", denominator=dict(C.DENOMINATOR),
                chapter_seed_distribution=chapters(), person_seed_vectors=vectors(),
                ten_seed_averages=averages(), all_four_paired_control_contrasts=paired(),
                candidate_neural_improvement=candidate(),
                primary_axes=["held_chapter","joint_person_held_chapter"], secondary_axis="exposed_person",
                primary_controls=["time_shifted_neural","timing"],
                stimulus_exposed_diagnostics=["acoustic","transcript"], qualification=False,
                uncertainty="finite-cohort point estimates/full distributions only; noCI/pvalue/narrative-population claim",
                probability_rule="q=(1-1e-6)*normalized_admitted_p+1e-6/39; no strict properness in rawp claim")


def artifact():
    values = {}
    for g, ((axis, budget), mode, track, arm) in enumerate(GROUPS):
        base = "/".join((axis,budget,mode,track,arm))
        values["mean/"+base+"/log_loss"] = loss(g, 4.5, 15.5, .5)
        values["mean/"+base+"/macro_f1_fixed39"] = f1(g)
        if arm == "neural":
            for j, control in enumerate(C.ARMS[1:], 1):
                values["neural_gain/"+"/".join((axis,budget,mode,track,control))] = j/1000
            if track == "candidate":
                values["candidate_gain/"+"/".join((axis,budget,mode))] = .005
    return dict(schema="n090-numerical-investigation-v1",
                inference_scope="finite_cohort_point_estimates_only",
                assertions={k:False for k in C.UNSUPPORTED},
                narrative={k:"Present for human review; invented fixture." for k in C.NARRATIVE},
                claims=[dict(id=k,value=v,unit=C.claim_schema()[k]) for k,v in values.items()])


def encoded(doc):
    return json.dumps(doc, allow_nan=False).encode()


def changed_first(rows, update):
    row = next(rows)
    yield dict(row, **update)
    yield from rows


class Controls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # One complete independent arithmetic inverse over all report sections.
        cls.truth = C.expected_claims(report())

    def test_full348_with_unequal_chapter_row_counts(self):
        doc = artifact()
        observed = C.capture_artifact(encoded(doc))
        self.assertEqual(len(observed), 348)
        self.assertEqual(set(observed), set(self.truth))
        for key in observed:
            self.assertTrue(C.close(observed[key], self.truth[key]), key)
        # Unequal numbers of query rows never reweight people.
        self.assertAlmostEqual(self.truth["mean/held_chapter/full/frozen_program/candidate/neural/log_loss"],
                               1.015055, places=12)

    def test_grade_null_false_and_roundoff_keeps_denominator(self):
        doc = artifact()
        gain = next(r for r in doc["claims"] if r["id"].startswith("neural_gain/"))
        gain["value"] *= -1
        doc["claims"][0]["value"] = None
        doc["claims"][1]["value"] += 1e-14
        calls=[]
        result=C.grade(encoded(doc), lambda:(calls.append("once") or report()))
        self.assertEqual(calls, ["once"])
        self.assertEqual(result["denominator"], 348)
        self.assertEqual(result["defined_claims"], 347)
        self.assertEqual(result["numerically_consistent_claims"], 346)
        self.assertIsNone(result["scientific_pass_threshold"])
        self.assertFalse(result["qualitative_reasoning_graded"])
        self.assertFalse(result["campaign_qualified"])

    def test_preprivate_missing_duplicate_units_boolean_nonfinite_unsupported(self):
        variants=[]
        d=artifact();d["claims"].pop();variants.append(d)
        d=artifact();d["claims"][-1]=dict(d["claims"][0]);variants.append(d)
        d=artifact();d["claims"][0]["unit"]="bits";variants.append(d)
        d=artifact();d["claims"][0]["value"]=True;variants.append(d)
        d=artifact();d["assertions"]["causal_effect"]=True;variants.append(d)
        d=artifact();d["narrative"].pop("uncertainty");variants.append(d)
        for d in variants:
            with self.subTest(d=str(d)[:80]):
                with self.assertRaises(C.Invalid):
                    C.grade(encoded(d), lambda:self.fail("private callback before admission"))
        body=encoded(artifact()).replace(b'"value": 1.015055',b'"value": NaN',1)
        if body==encoded(artifact()):
            body=b'{"x":NaN}'
        with self.assertRaises(C.Invalid):
            C.grade(body, lambda:self.fail("private"))
        with self.assertRaises(C.Invalid):
            C.grade(b'{"schema":"a","schema":"b"}',lambda:self.fail("private"))

    def test_missing_final_chapter(self):
        r=report();r["chapter_seed_distribution"]=itertools.islice(chapters(),76799)
        with self.assertRaisesRegex(C.Invalid,"missing"):C.expected_claims(r)

    def test_duplicate_chapter_even_with_complete_declared_denominator(self):
        rows=chapters();first=next(rows)
        r=report();r["chapter_seed_distribution"]=itertools.chain([first,first],rows)
        with self.assertRaisesRegex(C.Invalid,"duplicate"):C.expected_claims(r)

    def test_best_seed_summary_and_missing_person_refused(self):
        r=report();r["person_seed_vectors"]=changed_first(vectors(),{"log_loss":loss(0,9,15.5,.5)})
        with self.assertRaisesRegex(C.Invalid,"person loss"):C.expected_claims(r)
        r=report();first=next(vectors());first["people"].pop()
        r["person_seed_vectors"]=itertools.chain([first],itertools.islice(vectors(),1,None))
        with self.assertRaisesRegex(C.Invalid,"missing"):C.expected_claims(r)

    def test_exposed_diagnostic_cannot_be_called_primary(self):
        r=report();r["primary_controls"]=["acoustic","transcript"]
        with self.assertRaisesRegex(C.Invalid,"estimands"):C.expected_claims(r)
        r=report();r["all_four_paired_control_contrasts"]=changed_first(paired(),{"contrast_status":"exposed_or_secondary_diagnostic"})
        with self.assertRaisesRegex(C.Invalid,"primary"):C.expected_claims(r)

    def test_bad_reference_metric_and_denominator(self):
        for value in [float("nan"),True,-.1]:
            r=report();r["chapter_seed_distribution"]=changed_first(chapters(),{"log_loss":value})
            with self.assertRaises(C.Invalid):C.expected_claims(r)
        r=report();r["denominator"]["seeds"]=True
        with self.assertRaisesRegex(C.Invalid,"denominator"):C.expected_claims(r)

    def test_wrong_signed_pair_and_partial_candidate_support(self):
        r=report();r["all_four_paired_control_contrasts"]=changed_first(paired(),{"positive_improvement":-.001})
        with self.assertRaisesRegex(C.Invalid,"sign"):C.expected_claims(r)
        r=report();r["candidate_neural_improvement"]=itertools.islice(candidate(),7679)
        with self.assertRaisesRegex(C.Invalid,"missing"):C.expected_claims(r)

    def test_zero_true_class_support_requires_zero_f1(self):
        original = chapters()
        row = next(original)
        impossible = list(row["per_class_f1"])
        impossible[1], impossible[0] = impossible[0], 0.0
        # Same macro F1 and every later aggregate; only support/F1 is impossible.
        data = report()
        data["chapter_seed_distribution"] = itertools.chain(
            [dict(row, per_class_f1=impossible)], original)
        with self.assertRaisesRegex(C.Invalid, "zero true class support"):
            C.expected_claims(data)
        # A legitimate present-class F1 with zero absent-class F1 crosses the
        # changed boundary. Deliberately end early to avoid replaying support.
        data = report()
        data["chapter_seed_distribution"] = [row]
        with self.assertRaisesRegex(C.Invalid, "chapter support missing rows"):
            C.expected_claims(data)

    def test_oversized_integer_and_deep_json_fail_closed(self):
        data = artifact()
        data["claims"][0]["value"] = 10**400
        with self.assertRaises(C.Invalid):
            C.capture_artifact(json.dumps(data).encode())
        for body in (b"[" * 1500 + b"0" + b"]" * 1500, b"1" * 5000):
            with self.assertRaises(C.Invalid):
                C.capture_artifact(body)

    def test_artifact_cap_and_explicit_abstention(self):
        with self.assertRaises(C.Invalid):C.capture_artifact(b" "*(C.MAX_ARTIFACT+1))
        d=artifact()
        for row in d["claims"]:row["value"]=None
        values=C.capture_artifact(encoded(d))
        self.assertEqual(len(values),348)
        self.assertTrue(all(v is None for v in values.values()))


if __name__=="__main__":
    unittest.main()
