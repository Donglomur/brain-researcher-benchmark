"""NEURAL-090 numerical investigation claims; no models, neural arrays or file access.

The caller owns authentic complete report custody. This module validates the
report's complete scalar support and arithmetic, not its execution provenance.
"""
import json
import math
from array import array

AXES = (("held_chapter", "full"), ("held_chapter", "1024"),
        ("joint_person_held_chapter", "0"), ("joint_person_held_chapter", "1024"),
        ("exposed_person", "0"), ("exposed_person", "1024"))
MODES = ("frozen_program", "case_adaptive_equal_inputs_tools_compute")
TRACKS = ("candidate", "reference")
ARMS = ("neural", "time_shifted_neural", "timing", "acoustic", "transcript")
UNSUPPORTED = ("causal_effect", "population_generalization", "independent_visit_generalization",
               "statistical_significance", "LLM_understanding", "SOTA")
NARRATIVE = ("estimand", "uncertainty", "alternative_explanations", "executable_evidence")
DENOMINATOR = dict(people=32, fixed_chapters=2, cases=384, paired_slots=38400,
                   invocations=76800, arms=5, seeds=10)
ABS_TOL = REL_TOL = 1e-12
MAX_ARTIFACT = 262144
MAX_LOSS = math.log(39 / 1e-6)


class Invalid(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Invalid(message)


def finite(value):
    try:
        return type(value) in (float, int) and math.isfinite(value)
    except (OverflowError, ValueError):
        return False


def close(a, b):
    return abs(a - b) <= ABS_TOL + REL_TOL * max(abs(a), abs(b))


def same(actual, expected, label):
    need(finite(actual) and close(actual, expected), label)


def exact_int(value, lo, hi):
    return type(value) is int and lo <= value <= hi


def strings(row):
    need(type(row) is dict, "report row object")
    for name in ("axis", "budget", "mode", "arm", "person", "chapter"):
        need(type(row.get(name)) is str, "literal report identity")
    need((row["axis"], row["budget"]) in AXES and row["mode"] in MODES
         and row["arm"] in ARMS and row["person"] in tuple(map(str, range(1, 33)))
         and row["chapter"] in ("11", "12") and exact_int(row.get("seed"), 0, 9),
         "complete original report identity")
    need(row.get("case") == "/".join((row["axis"], row["person"], row["chapter"], row["budget"])),
         "exact case identity")
    need(type(row.get("person_condition_exposed")) is bool
         and row["person_condition_exposed"] == (row["axis"] == "exposed_person"),
         "person exposure identity")
    need(row.get("target_exposure") == ("protected" if row["arm"] in ARMS[:3]
                                      else "stimulus_exposed_diagnostic"), "arm exposure identity")


def index(row, track=None, arm=None):
    strings(row)
    track = row.get("track") if track is None else track
    arm = row["arm"] if arm is None else arm
    need(type(track) is str and track in TRACKS and arm in ARMS, "track/arm identity")
    # 120 arm groups x 10 seeds x 32 people x 2 chapter directions.
    group = ((AXES.index((row["axis"], row["budget"])) * 2 + MODES.index(row["mode"])) * 2
             + TRACKS.index(track)) * 5 + ARMS.index(arm)
    return ((group * 10 + row["seed"]) * 32 + int(row["person"]) - 1) * 2 + int(row["chapter"]) - 11


def bounded(rows, total, label):
    # Accept existing lists and trusted streaming projections; no unbounded copy.
    count = 0
    try:
        for row in rows:
            need(count < total, label + " extra rows")
            count += 1
            yield row
    except TypeError as exc:
        raise Invalid(label + " iterable required") from exc
    need(count == total, label + " missing rows")


def group_key(axis, budget, mode, track, arm):
    return "/".join((axis, budget, mode, track, arm))


def claim_schema():
    """All 348 claims; conditions are not new tasks or independent samples."""
    result = {}
    for axis, budget in AXES:
        for mode in MODES:
            for track in TRACKS:
                for arm in ARMS:
                    base = group_key(axis, budget, mode, track, arm)
                    result["mean/" + base + "/log_loss"] = "nats_per_prediction"
                    result["mean/" + base + "/macro_f1_fixed39"] = "fraction"
                for control in ARMS[1:]:
                    result["neural_gain/" + group_key(axis, budget, mode, track, control)] = "nats_per_prediction"
            result["candidate_gain/" + "/".join((axis, budget, mode))] = "nats_per_prediction"
    return result


def capture_artifact(body):
    need(type(body) is bytes and 0 < len(body) <= MAX_ARTIFACT, "bounded immutable artifact bytes")
    def pairs(items):
        out = {}
        for key, value in items:
            need(key not in out, "duplicate JSON field")
            out[key] = value
        return out
    def invalid(value):
        raise Invalid("nonfinite JSON constant")
    try:
        doc = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Invalid("UTF-8 JSON required") from exc
    need(type(doc) is dict and set(doc) == {"schema", "inference_scope", "assertions", "narrative", "claims"},
         "exact investigation envelope")
    need(doc["schema"] == "n090-numerical-investigation-v1"
         and doc["inference_scope"] == "finite_cohort_point_estimates_only", "finite-cohort inference scope")
    need(type(doc["assertions"]) is dict and set(doc["assertions"]) == set(UNSUPPORTED)
         and all(type(v) is bool and v is False for v in doc["assertions"].values()),
         "unsupported structured scientific assertion")
    need(type(doc["narrative"]) is dict and set(doc["narrative"]) == set(NARRATIVE)
         and all(type(v) is str and 0 < len(v.strip()) <= 2048 for v in doc["narrative"].values()),
         "all narrative fields present; content remains ungraded")
    schema = claim_schema()
    need(type(doc["claims"]) is list and len(doc["claims"]) == len(schema), "all 348 claims required")
    captured = {}
    for row in doc["claims"]:
        need(type(row) is dict and set(row) == {"id", "value", "unit"}, "exact claim fields")
        key = row["id"]
        need(type(key) is str and key in schema and key not in captured, "unknown or duplicate claim")
        need(row["unit"] == schema[key], "claim unit")
        value = row["value"]
        need(value is None or finite(value), "finite numeric claim or explicit null abstention")
        captured[key] = value
    return captured


def expected_claims(report):
    need(type(report) is dict and report.get("schema") == "n090-broad-point-report-v1",
         "existing complete point-report schema")
    need(type(report.get("denominator")) is dict and set(report["denominator"]) == set(DENOMINATOR)
         and all(type(report["denominator"][k]) is int and report["denominator"][k] == v
                 for k, v in DENOMINATOR.items()), "unaltered complete denominator")
    need(report.get("primary_axes") == ["held_chapter", "joint_person_held_chapter"]
         and report.get("secondary_axis") == "exposed_person"
         and report.get("primary_controls") == ["time_shifted_neural", "timing"]
         and report.get("stimulus_exposed_diagnostics") == ["acoustic", "transcript"],
         "protected/diagnostic estimands")
    need(report.get("qualification") is False, "no campaign qualification")
    need(report.get("uncertainty") ==
         "finite-cohort point estimates/full distributions only; noCI/pvalue/narrative-population claim",
         "unchanged uncertainty")
    need(report.get("probability_rule") ==
         "q=(1-1e-6)*normalized_admitted_p+1e-6/39; no strict properness in rawp claim",
         "unchanged probability rule")
    loss = array("d", [0.0]) * 76800
    f1 = array("d", [0.0]) * 76800
    seen = bytearray(76800)
    for row in bounded(report.get("chapter_seed_distribution"), 76800, "chapter support"):
        i = index(row)
        need(not seen[i], "duplicate chapter identity")
        seen[i] = 1
        n = row.get("query_rows")
        support, per_f1 = row.get("per_class_support"), row.get("per_class_f1")
        need(exact_int(n, 1, 2**53) and type(support) is list and len(support) == 39
             and all(exact_int(x, 0, n) for x in support) and sum(support) == n, "all 39 class supports")
        need(type(per_f1) is list and len(per_f1) == 39
             and all(finite(x) and 0 <= x <= 1 for x in per_f1), "all 39 finite class F1")
        need(all(n > 0 or score == 0 for n, score in zip(support, per_f1)),
             "zero true class support requires exact zero F1")
        need(row.get("absent_class_rule") == "F1=0 when2TP+FP+FN=0", "absent-class convention")
        same(row.get("macro_f1_fixed39"), math.fsum(per_f1) / 39, "fixed39 macro F1")
        need(finite(row.get("log_loss")) and 0 <= row["log_loss"] <= MAX_LOSS + ABS_TOL,
             "finite q log loss in nats")
        loss[i], f1[i] = row["log_loss"], row["macro_f1_fixed39"]
    # Row cardinality + collision-free bounded identity proves full support.
    vectors = bytearray(1200)
    for row in bounded(report.get("person_seed_vectors"), 1200, "person vectors"):
        need(type(row) is dict and exact_int(row.get("seed"), 0, 9), "vector identity")
        axis, budget, mode, track, arm = (row.get(k) for k in ("axis", "budget", "mode", "track", "arm"))
        need((axis, budget) in AXES and mode in MODES and track in TRACKS and arm in ARMS, "vector group")
        g = ((AXES.index((axis, budget)) * 2 + MODES.index(mode)) * 2 + TRACKS.index(track)) * 5 + ARMS.index(arm)
        v = g * 10 + row["seed"]
        need(not vectors[v], "duplicate person vector")
        vectors[v] = 1
        people = bytearray(32)
        for person in bounded(row.get("people"), 32, "person support"):
            need(type(person) is dict and type(person.get("person")) is str
                 and person["person"] in tuple(map(str, range(1, 33))), "person identity")
            p = int(person["person"]) - 1
            need(not people[p], "duplicate person")
            people[p] = 1
            i = (v * 32 + p) * 2
            same(person.get("log_loss"), (loss[i] + loss[i+1]) / 2, "equal chapter loss")
            same(person.get("macro_f1_fixed39"), (f1[i] + f1[i+1]) / 2, "equal chapter F1")
        same(row.get("log_loss"), math.fsum(loss[v*64:(v+1)*64]) / 64, "equal person loss")
        same(row.get("macro_f1_fixed39"), math.fsum(f1[v*64:(v+1)*64]) / 64, "equal person F1")
    means, avg_seen = {}, bytearray(120)
    for row in bounded(report.get("ten_seed_averages"), 120, "ten-seed means"):
        need(type(row) is dict, "mean object")
        axis, budget, mode, track, arm = (row.get(k) for k in ("axis", "budget", "mode", "track", "arm"))
        need((axis, budget) in AXES and mode in MODES and track in TRACKS and arm in ARMS, "mean identity")
        g = ((AXES.index((axis, budget)) * 2 + MODES.index(mode)) * 2 + TRACKS.index(track)) * 5 + ARMS.index(arm)
        need(not avg_seen[g], "duplicate ten-seed group")
        avg_seen[g] = 1
        base = group_key(axis, budget, mode, track, arm)
        for metric, values in (("log_loss", loss), ("macro_f1_fixed39", f1)):
            value = math.fsum(values[g*640:(g+1)*640]) / 640
            same(row.get(metric), value, "all ten seeds, equal chapters/people")
            means["mean/" + base + "/" + metric] = value
    paired_seen = bytearray(61440)
    for row in bounded(report.get("all_four_paired_control_contrasts"), 61440, "paired controls"):
        i = index(row)
        control = row.get("control")
        need(row["arm"] == "neural" and control in ARMS[1:], "neural/control identity")
        g, remainder = divmod(i, 640)
        slot = (g // 5 * 640 + remainder) * 4 + ARMS[1:].index(control)
        need(not paired_seen[slot], "duplicate paired contrast")
        paired_seen[slot] = 1
        c = index(row, arm=control)
        same(row.get("positive_improvement"), loss[c] - loss[i], "control-minus-neural sign")
        status = "protected_primary" if row["axis"] != "exposed_person" and control in ARMS[:3] else "exposed_or_secondary_diagnostic"
        need(row.get("contrast_status") == status, "primary versus exposed contrast")
    candidate_seen = bytearray(7680)
    for row in bounded(report.get("candidate_neural_improvement"), 7680, "candidate/reference contrasts"):
        i = index(row, track="candidate")
        need(row["arm"] == "neural", "candidate contrast arm")
        g, remainder = divmod(i, 640)
        slot = g // 10 * 640 + remainder
        need(not candidate_seen[slot], "duplicate candidate contrast")
        candidate_seen[slot] = 1
        same(row.get("positive_improvement"), loss[index(row, track="reference")] - loss[i],
             "reference-minus-candidate sign")
    for axis, budget in AXES:
        for mode in MODES:
            for track in TRACKS:
                n = means["mean/" + group_key(axis, budget, mode, track, "neural") + "/log_loss"]
                for control in ARMS[1:]:
                    c = means["mean/" + group_key(axis, budget, mode, track, control) + "/log_loss"]
                    means["neural_gain/" + group_key(axis, budget, mode, track, control)] = c - n
            key = "/".join((axis, budget, mode))
            means["candidate_gain/" + key] = (means["mean/" + group_key(axis, budget, mode, "reference", "neural") + "/log_loss"]
                                                - means["mean/" + group_key(axis, budget, mode, "candidate", "neural") + "/log_loss"])
    need(set(means) == set(claim_schema()), "complete 348 expected claims")
    return means


def grade(artifact_bytes, reference_loader):
    submitted = capture_artifact(artifact_bytes)  # Complete capture before trusted callback.
    expected = expected_claims(reference_loader())
    units = claim_schema()
    rows = []
    for key in sorted(expected):
        value, truth = submitted[key], expected[key]
        rows.append(dict(id=key, unit=units[key], value=value, expected=truth,
                         absolute_error=None if value is None else abs(value - truth),
                         within_roundoff=False if value is None else close(value, truth),
                         undefined=value is None))
    return dict(schema="n090-numerical-investigation-grade-v1", claims=rows, denominator=348,
                defined_claims=sum(not r["undefined"] for r in rows),
                numerically_consistent_claims=sum(r["within_roundoff"] for r in rows),
                abs_tolerance=ABS_TOL, rel_tolerance=REL_TOL,
                scientific_pass_threshold=None, qualitative_reasoning_graded=False,
                executable_evidence_validated=False, method_provenance_validated=False,
                original_report_custody_validated=False, campaign_qualified=False,
                human_review_required=["narrative meaning", "alternative explanations", "execution/method provenance"],
                benchmark_count_delta=0)
