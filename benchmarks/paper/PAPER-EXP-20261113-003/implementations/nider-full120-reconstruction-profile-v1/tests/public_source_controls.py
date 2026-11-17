"""Invented-only public interface controls; no scientific/native/network run.

This file is SOURCE ONLY until a caller selects one bounded invocation.
All fixture numerical values, owner locks, reference documents and cases below
are invented. The public bridge's canonical input checksum is used only to test
its documented identity mapping; no workbook or protected answer is opened.
"""
from contextlib import contextmanager
from copy import deepcopy
from fractions import Fraction
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

SOURCE_PINS = [
  {
    "relative_path": "comparator/compare_local.py",
    "bytes": 6476,
    "sha256": "8177574bc9546a0d3cb81811089c383af8b673b85cc760ff53d3ed97ceb6e1af"
  },
  {
    "relative_path": "comparator/custody.py",
    "bytes": 2321,
    "sha256": "03f29157b2fdee1ee0d2ff02ac32f32c2620cef1b4bb9cc7b52a3b72d70a44b9"
  },
  {
    "relative_path": "comparator/extended_score.py",
    "bytes": 11093,
    "sha256": "1c24ec4f2fc5d722541e9231268af21218672ee9453f309110acecffaf5833bf"
  },
  {
    "relative_path": "comparator/reporting_core.py",
    "bytes": 11862,
    "sha256": "8f87075849eece5320354fb05e5f1fa37eb3f541a0b9d8e924c79f9073e35963"
  },
  {
    "relative_path": "comparator/reporting_resolution.py",
    "bytes": 6105,
    "sha256": "9d403dacee887da9d5dd7eea16741f77bae8d93442f97547cd07724ab220b7f0"
  },
  {
    "relative_path": "runtime/reporting_core.py",
    "bytes": 11862,
    "sha256": "8f87075849eece5320354fb05e5f1fa37eb3f541a0b9d8e924c79f9073e35963"
  },
  {
    "relative_path": "runtime/scientific_score.py",
    "bytes": 8863,
    "sha256": "459e2c50c6737edfcc08add2930cfa8b05a73177debad32bfc5f0654e6b8a69b"
  },
  {
    "relative_path": "runtime/extended_score.py",
    "bytes": 11093,
    "sha256": "1c24ec4f2fc5d722541e9231268af21218672ee9453f309110acecffaf5833bf"
  },
  {
    "relative_path": "runtime/full120_output.py",
    "bytes": 2290,
    "sha256": "0200a3cf769275560aab9e3f7eda4e5a072eb57ce22d1d39bafe9e684ebb71aa"
  },
  {
    "relative_path": "runtime/build_spec.py",
    "bytes": 2757,
    "sha256": "ba029b7761e2b9d989dbea8da8b0c1227b37eb173673a05c5758c0e30a39d96c"
  },
  {
    "relative_path": "runtime/custody.py",
    "bytes": 2321,
    "sha256": "03f29157b2fdee1ee0d2ff02ac32f32c2620cef1b4bb9cc7b52a3b72d70a44b9"
  }
]
MODULE_NAMES = ("custody", "reporting_core", "extended_score", "reporting_resolution")
CONTRASTS = ("quest_self", "amy_quest", "amy_self")
FIELDS = (
    "common_z_estimate", "common_z_se", "common_z_statistic", "common_z_p",
    "common_z_lower", "common_z_upper", "random_z_estimate", "random_z_se",
    "random_z_statistic", "random_z_p", "random_z_lower", "random_z_upper",
    "common_r_estimate", "common_r_lower", "common_r_upper", "random_r_estimate",
    "random_r_lower", "random_r_upper", "Q", "df_Q", "p_Q", "tau", "tau2",
    "se_tau2", "lower_tau", "upper_tau", "lower_tau2", "upper_tau2", "H",
    "lower_H", "upper_H", "I2", "lower_I2", "upper_I2", "k", "k_all", "k_TE",
    "k_study", "N_author_sum", "submitted_rows",
)
PROJECTED = ("random_r_estimate", "random_z_p", "k", "N_author_sum")
BOUNDARIES = (
    ("positive_inside", Fraction(234, 10000), 2, 2),
    ("positive_upper_neighbor", Fraction(251, 10000), 2, 3),
    ("positive_exact_boundary", Fraction(25, 1000), 2, None),
    ("negative_inside", Fraction(-234, 10000), 2, -2),
    ("negative_lower_neighbor", Fraction(-251, 10000), 2, -3),
    ("negative_exact_boundary", Fraction(-25, 1000), 2, None),
    ("zero", Fraction(0), 2, 0),
    ("three_digit_inside", Fraction(2344, 100000), 3, 23),
    ("three_digit_upper_neighbor", Fraction(2351, 100000), 3, 24),
    ("three_digit_exact_boundary", Fraction(235, 10000), 3, None),
)
CONTROL_IDS = (
    "schema.complete120",
    "score.partition27_21_72",
    "score.large_integer_delta",
    "schema.missing_field",
    "schema.extra_field",
    "schema.duplicate_json_field",
    "schema.wrong_arm",
    "schema.wrong_workbook",
    "score.undefined_not_pass",
    "score.metadata_mismatch",
    "bin.positive_inside",
    "bin.positive_upper_neighbor",
    "bin.positive_exact_boundary",
    "bin.negative_inside",
    "bin.negative_lower_neighbor",
    "bin.negative_exact_boundary",
    "bin.zero",
    "bin.three_digit_inside",
    "bin.three_digit_upper_neighbor",
    "bin.three_digit_exact_boundary",
    "owner.valid_pinned_compare",
    "owner.lock_pin",
    "owner.reference_pin",
    "owner.reference_arm",
    "owner.candidate_cannot_select_arm",
    "owner.candidate_cannot_select_workbook",
    "owner.candidate_cannot_supply_reference",
    "owner.candidate_pin",
    "owner.invalid_selected_arm",
    "owner.existing_report",
    "owner.reference_unchanged",
    "owner.changed_reference_changes_score",
    "owner.B_candidate_against_A_reference",
    "bridge.original_canonical_to_delivered",
    "bridge.original_rejects_projection_identity",
    "bridge.derivative_uses_delivered",
    "bridge.derivative_rejects_canonical_identity",
    "procedure.four_cases48_statuses",
    "procedure.missing_case",
    "procedure.duplicate_case",
    "procedure.candidate_cannot_supply_target",
    "procedure.wrong_case_identity",
    "procedure.wrong_arm",
    "procedure.hypothetical_failure_is_local",
    "procedure.original_failure_is_local",
    "procedure.additional108_retained_unscored",
    "build.inert_committed_entrypoint",
    "build.offline_plan_only",
    "build.staging_identity",
    "build.invalid_name",
    "build.relative_owner_root",
)


def need(condition, code):
    if not condition:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def invented_sha(label):
    return sha(("INVENTED_PUBLIC_CONTROL:" + label).encode())


def encode(document):
    return (json.dumps(document, separators=(",", ":"), allow_nan=False) + "\n").encode()


def checked_path(value):
    p = Path(value)
    need(p.is_absolute() and ".." not in p.parts, "absolute_plain_path")
    need(not any(q.is_symlink() for q in (p, *p.parents)), "symlink_not_allowed")
    return p


def write_new(path, raw):
    need(type(raw) is bytes and len(raw) <= 262144, "invented_artifact_extent")
    with path.open("xb") as stream:
        stream.write(raw)
    path.chmod(0o600)
    return {"path": str(path), "bytes": len(raw), "sha256": sha(raw)}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    need(spec is not None and spec.loader is not None, "module_loader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@contextmanager
def fresh_module_namespace():
    """Isolate only tested helper names; do not alter their source or behavior."""
    absent = object()
    before = {name: sys.modules.pop(name, absent) for name in MODULE_NAMES}
    try:
        yield
    finally:
        for name in MODULE_NAMES:
            sys.modules.pop(name, None)
            if before[name] is not absent:
                sys.modules[name] = before[name]


def fixture_document(workbook_sha, arm="A"):
    """Schema-valid invented cells, not a fitted or physiologically real result."""
    rows = []
    for contrast in CONTRASTS:
        values = {name: 0 for name in FIELDS}
        values.update(random_z_estimate=0.2, random_z_p=0.01,
                      random_r_estimate=0.2, k=1, k_all=1, k_TE=1,
                      k_study=1, N_author_sum=20, submitted_rows=1)
        n_column = "sample size rating" if contrast == "amy_self" else "sample size quest"
        rows.append({
            "contrast": contrast,
            "settings": {"sm": "ZCOR", "method_tau": "DL",
                         "method_random_ci": "classic", "level": "0.95",
                         "level_ma": "0.95", "common": True, "random": True,
                         "three_level": False, "cluster_supplied": False},
            "tau_interval": {"method": "J", "lower_sign": "", "upper_sign": ""},
            "membership": [{"source_id": "InventedStudy", "source_rows": [1],
                            "retained_row": 1, "author_label": "Invented Study",
                            "n_column": n_column, "contributes_to_k": True}],
            "fields": {name: {"state": "finite", "value": value}
                       for name, value in values.items()},
        })
    return {"schema": "nider_extended_reproduction_submission_v1",
            "task": "PAPER-EXP-20261113-003", "arm": arm,
            "workbook_sha256": workbook_sha, "contrasts": rows}


def changed_cell(document, field, value, contrast=0):
    result = deepcopy(document)
    result["contrasts"][contrast]["fields"][field] = {"state": "finite", "value": value}
    return result


def reject(call, code):
    try:
        call()
    except ValueError as error:
        return str(error) == code
    return False


class Controls:
    def __init__(self):
        self.rows = []

    def check(self, identity, call):
        need(identity in CONTROL_IDS and identity not in {r["id"] for r in self.rows},
             "unique_declared_control")
        try:
            result = call()
            if result is not True:
                raise AssertionError("predicate_not_true")
            row = {"id": identity, "status": "PASS"}
        except Exception as error:
            row = {"id": identity, "status": "FAIL",
                   "error_class": type(error).__name__, "error": str(error)}
        self.rows.append(row)


def schema_and_owner_controls(package, out, suite, compare):
    workbook_sha = invented_sha("owner-workbook")
    document = fixture_document(workbook_sha)
    reference_raw = encode(document)
    reference_pin = write_new(out / "invented-reference.json", reference_raw)
    modules = {}
    by_name = {row["relative_path"]: row for row in SOURCE_PINS}
    for name in MODULE_NAMES:
        relative = "comparator/" + name + ".py"
        entry = by_name[relative]
        modules[name] = {"path": str(package / relative), "bytes": entry["bytes"],
                         "sha256": entry["sha256"]}
    lock = {"schema": "nider_full120_local_owner_lock_v1",
            "task": "PAPER-EXP-20261113-003", "modules": modules,
            "reference": reference_pin, "workbook_sha256": workbook_sha,
            "reference_arm": "A", "expected_fields": 120}
    lock_raw = encode(lock)
    lock_pin = write_new(out / "invented-owner-lock.json", lock_raw)
    ledger = {"conservative_requested_bytes": 0, "authenticated_body_bytes": 0}
    owner = compare.load_owner(lock_pin["path"], lock_pin["sha256"], ledger)
    core = owner["modules"]["reporting_core"]
    validator = owner["modules"]["extended_score"]
    resolution = owner["modules"]["reporting_resolution"]

    def validate(doc, arm="A", workbook=workbook_sha):
        return validator.validate(core.decode_numeric_json(encode(doc)), arm, workbook)

    def result(candidate, reference=document):
        return resolution.compare_validated(validate(candidate), validate(reference))

    validated = validate(document)
    baseline = result(document)
    suite.check("schema.complete120", lambda: len(validated) == 3 and
                set(validator.FIELDS) == set(FIELDS) and len(FIELDS) == 40 and
                sum(len(values) for _, values in validated.values()) == 120)

    def partition():
        rows = baseline["cells"]
        counts = {status: sum(row["status"] == status for row in rows) for status in
                  ("AUTHOR_TABLE_BIN_AGREEMENT", "EXACT_COUNT_AGREEMENT",
                   "HELD_UNREPORTED_DIAGNOSTIC")}
        return (len(rows) == 120 and counts ==
                {"AUTHOR_TABLE_BIN_AGREEMENT": 27, "EXACT_COUNT_AGREEMENT": 21,
                 "HELD_UNREPORTED_DIAGNOSTIC": 72} and
                baseline["continuous_total_fields"] == 120 and
                baseline["continuous_fields_excluded"] == 0 and
                baseline["aggregate_binary_pass_defined"] is False and
                all(row["continuous_error"]["state"] == "FINITE" for row in rows))
    suite.check("score.partition27_21_72", partition)

    def exact_large_integer():
        reference = changed_cell(document, "N_author_sum", 2**60)
        candidate = changed_cell(reference, "N_author_sum", 2**60 + 1)
        rows = result(candidate, reference)["cells"]
        row = next(r for r in rows if r["contrast"] == CONTRASTS[0] and
                   r["field"] == "N_author_sum")
        return (row["status"] == "COUNT_DISAGREEMENT" and
                row["continuous_error"]["absolute_error"] ==
                {"numerator": "1", "denominator": "1"})
    suite.check("score.large_integer_delta", exact_large_integer)

    missing = deepcopy(document)
    del missing["contrasts"][0]["fields"]["Q"]
    extra = deepcopy(document)
    extra["contrasts"][0]["fields"]["invented_extra"] = {"state": "finite", "value": 0}
    duplicate = reference_raw.replace(b'"random_z_p":',
                                     b'"random_z_p":{"state":"finite","value":0.01},"random_z_p":', 1)
    suite.check("schema.missing_field",
                lambda: reject(lambda: validate(missing), "complete_numeric_fields"))
    suite.check("schema.extra_field",
                lambda: reject(lambda: validate(extra), "complete_numeric_fields"))
    suite.check("schema.duplicate_json_field",
                lambda: reject(lambda: core.decode_numeric_json(duplicate), "duplicate_JSON_key"))
    suite.check("schema.wrong_arm",
                lambda: reject(lambda: validate(document, arm="B"), "document_identity"))
    suite.check("schema.wrong_workbook",
                lambda: reject(lambda: validate(document, workbook=invented_sha("wrong")),
                               "document_identity"))

    unavailable = deepcopy(document)
    unavailable["contrasts"][0]["fields"]["Q"] = {"state": "NA"}
    suite.check("score.undefined_not_pass", lambda: any(
        row["contrast"] == CONTRASTS[0] and row["field"] == "Q" and
        row["status"] == "INDETERMINATE_UNDEFINED_VALUE" and
        row["continuous_error"]["state"] == "UNDEFINED"
        for row in result(unavailable, unavailable)["cells"]))
    metadata = deepcopy(document)
    metadata["contrasts"][0]["membership"][0]["author_label"] = "Another Invented Label"
    suite.check("score.metadata_mismatch", lambda: sum(
        not row["exact_metadata_agreement"] for row in result(metadata)["cells"]) == 40)
    for identity, value, decimals, expected in BOUNDARIES:
        suite.check("bin." + identity,
                    lambda identity=identity, value=value, decimals=decimals, expected=expected:
                    resolution.bin_index(value, decimals) == expected and
                    (identity, value, decimals, expected) in BOUNDARIES)
    # Independently enumerated expectations above preserve the ten pre-existing
    # boundary definitions; their source function is checked as a complete set.
    need(tuple(resolution.boundary_control_definitions()) == BOUNDARIES,
         "complete_existing_boundary_population")

    candidate_number = 0
    def compare_document(doc, arm="A", *, expected_sha=None, report_name=None):
        nonlocal candidate_number
        candidate_number += 1
        pin = write_new(out / ("invented-candidate-%02d.json" % candidate_number), encode(doc))
        target = out / (report_name or ("invented-report-%02d" % candidate_number))
        return compare.compare_file(owner, pin["path"], expected_sha or pin["sha256"],
                                    arm, str(target))

    def positive_owner():
        _, summary = compare_document(document)
        return (summary["comparison_completed"] is True and summary["fields"] == 120 and
                summary["reported_real_fields"] == 27 and summary["exact_integer_fields"] == 21 and
                summary["continuous_only_real_fields"] == 72 and
                summary["aggregate_scientific_pass_defined"] is False)
    suite.check("owner.valid_pinned_compare", positive_owner)

    def load_changed_lock(changed, suffix, digest=None):
        pin = write_new(out / ("invented-owner-" + suffix + ".json"), encode(changed))
        with fresh_module_namespace():
            return compare.load_owner(pin["path"], digest or pin["sha256"],
                                      {"conservative_requested_bytes": 0,
                                       "authenticated_body_bytes": 0})
    suite.check("owner.lock_pin", lambda: reject(
        lambda: load_changed_lock(lock, "bad-lock-pin", invented_sha("wrong-lock")),
        "owner_lock_identity"))
    wrong_ref = deepcopy(lock)
    wrong_ref["reference"]["sha256"] = invented_sha("wrong-reference")
    suite.check("owner.reference_pin", lambda: reject(
        lambda: load_changed_lock(wrong_ref, "bad-reference"), "input_identity"))
    wrong_ref_arm = deepcopy(lock)
    wrong_ref_arm["reference_arm"] = "B"
    suite.check("owner.reference_arm", lambda: reject(
        lambda: load_changed_lock(wrong_ref_arm, "bad-reference-arm"), "qualified_reference_scope"))
    suite.check("owner.candidate_cannot_select_arm", lambda: reject(
        lambda: compare_document(fixture_document(workbook_sha, "B"), "A"), "document_identity"))
    suite.check("owner.candidate_cannot_select_workbook", lambda: reject(
        lambda: compare_document(fixture_document(invented_sha("other-workbook"))), "document_identity"))
    forged = deepcopy(document)
    forged["reference"] = {"path": "invented-attacker-reference", "sha256": invented_sha("attacker")}
    suite.check("owner.candidate_cannot_supply_reference", lambda: reject(
        lambda: compare_document(forged), "document_keys"))
    suite.check("owner.candidate_pin", lambda: reject(
        lambda: compare_document(document, expected_sha=invented_sha("wrong-candidate")), "input_identity"))
    suite.check("owner.invalid_selected_arm", lambda: reject(
        lambda: compare_document(document, "C"), "owner_selected_arm"))
    existing = out / "invented-existing-report"
    existing.mkdir(mode=0o700)
    suite.check("owner.existing_report", lambda: reject(
        lambda: compare_document(document, report_name=existing.name), "fresh_private_report_directory"))
    suite.check("owner.reference_unchanged",
                lambda: (out / "invented-reference.json").read_bytes() == reference_raw)

    def changed_owner_reference():
        altered = changed_cell(document, "random_z_estimate", 0.4)
        new_ref = write_new(out / "invented-altered-reference.json", encode(altered))
        new_lock = deepcopy(lock)
        new_lock["reference"] = new_ref
        new_owner = load_changed_lock(new_lock, "altered-reference")
        pin = write_new(out / "invented-fixed-candidate.json", reference_raw)
        details, _ = compare.compare_file(new_owner, pin["path"], pin["sha256"], "A",
                                         str(out / "invented-altered-reference-report"))
        return sum(row["status"] == "AUTHOR_TABLE_BIN_DISAGREEMENT"
                   for row in details["cells"]) == 1
    suite.check("owner.changed_reference_changes_score", changed_owner_reference)
    suite.check("owner.B_candidate_against_A_reference",
                lambda: compare_document(fixture_document(workbook_sha, "B"), "B")[1]["fields"] == 120)


def runtime_controls(package, out, suite):
    custody = load_module("custody", package / "runtime/custody.py")
    core = load_module("reporting_core", package / "runtime/reporting_core.py")
    validator = load_module("extended_score", package / "runtime/extended_score.py")
    bridge = load_module("public_control_full120_output", package / "runtime/full120_output.py")
    scientific = load_module("public_control_scientific_score", package / "runtime/scientific_score.py")
    build = load_module("public_control_build_spec", package / "runtime/build_spec.py")
    cases = []
    full_documents = []
    responses = []
    for index in range(4):
        case = {"case_id": "invented-case-%d" % index,
                "kind": "original" if index == 0 else "procedure",
                "workbook": {"sha256": invented_sha("delivered-projection-%d" % index)},
                "target": {"fields": {
                    key: {"pearson_r": (Fraction(1, 5), Fraction(1, 100)),
                          "p_two_sided": (Fraction(1, 100), Fraction(1, 1000)),
                          "k": (Fraction(1), Fraction(1)),
                          "N": (Fraction(20), Fraction(1))}
                    for key in CONTRASTS}}}
        workbook = bridge.ORIGINAL if index == 0 else case["workbook"]["sha256"]
        document = fixture_document(workbook)
        full_documents.append(document)
        normalized = bridge.normalize(encode(document), case, "A")
        responses.append(scientific.normalize_case_response(normalized, case))
        cases.append(case)
        write_new(out / ("invented-full-case-%d.json" % index), encode(document))
    original = cases[0]
    derivative = cases[1]
    suite.check("bridge.original_canonical_to_delivered", lambda:
                full_documents[0]["workbook_sha256"] == bridge.ORIGINAL and
                bridge.ORIGINAL != original["workbook"]["sha256"] and
                responses[0]["workbook_sha256"] == original["workbook"]["sha256"])
    suite.check("bridge.original_rejects_projection_identity", lambda: reject(
        lambda: bridge.normalize(encode(fixture_document(original["workbook"]["sha256"])),
                                 original, "A"), "document_identity"))
    suite.check("bridge.derivative_uses_delivered", lambda:
                full_documents[1]["workbook_sha256"] == derivative["workbook"]["sha256"] and
                responses[1]["workbook_sha256"] == derivative["workbook"]["sha256"])
    suite.check("bridge.derivative_rejects_canonical_identity", lambda: reject(
        lambda: bridge.normalize(encode(fixture_document(bridge.ORIGINAL)), derivative, "A"),
        "document_identity"))
    submission_raw = scientific.assemble_responses(responses, "A")
    write_new(out / "invented-four-case-submission.json", submission_raw)
    submission = json.loads(submission_raw)
    score = scientific.score_submission(submission_raw, cases, "A")

    def score_doc(doc, arm="A"):
        return scientific.score_submission(encode(doc), cases, arm)

    suite.check("procedure.four_cases48_statuses", lambda:
                len(score["per_case"]) == 4 and
                sum(row["evaluated_fields"] for row in score["per_case"]) == 48 and
                all(len(row["fields"]) == 12 and row["complete_agreement"] for row in score["per_case"]) and
                score["complete_original_and_procedure_agreement"] is True)
    missing = deepcopy(submission)
    missing["cases"].pop()
    suite.check("procedure.missing_case", lambda: reject(
        lambda: score_doc(missing), "complete_four_case_support"))
    duplicate = deepcopy(submission)
    duplicate["cases"][3] = deepcopy(duplicate["cases"][2])
    suite.check("procedure.duplicate_case", lambda: reject(
        lambda: score_doc(duplicate), "unknown_or_duplicate_case"))
    forged = deepcopy(submission)
    forged["target"] = {"fields": "invented-candidate-chosen"}
    suite.check("procedure.candidate_cannot_supply_target", lambda: reject(
        lambda: score_doc(forged), "submission_keys"))
    wrong_case = deepcopy(submission)
    wrong_case["cases"][1]["workbook_sha256"] = invented_sha("forged-case")
    suite.check("procedure.wrong_case_identity", lambda: reject(
        lambda: score_doc(wrong_case), "response_input_identity"))
    suite.check("procedure.wrong_arm", lambda: reject(
        lambda: score_doc(submission, "B"), "submission_identity"))

    def local_failure(index):
        bad = deepcopy(submission)
        bad["cases"][index]["rows"][0]["fields"]["p_two_sided"] = 0.03
        result = score_doc(bad)
        statuses = [row["status"] for case in result["per_case"] for row in case["fields"]]
        failures = [case["case_id"] for case in result["per_case"] if not case["complete_agreement"]]
        return (len(statuses) == 48 and failures == [cases[index]["case_id"]] and
                sum(value not in ("REPORTING_AGREEMENT", "EXACT_COUNT_AGREEMENT")
                    for value in statuses) == 1 and
                result["original_reporting_agreement"] is (index != 0) and
                result["coarse_procedure_agreement"] is (index == 0))
    suite.check("procedure.hypothetical_failure_is_local", lambda: local_failure(1))
    suite.check("procedure.original_failure_is_local", lambda: local_failure(0))

    def additional_fields_unscored():
        for index in range(1, 4):
            complete = validator.validate(core.decode_numeric_json(encode(full_documents[index])),
                                          "A", cases[index]["workbook"]["sha256"])
            if sum(len(values) for _, values in complete.values()) != 120:
                return False
            if len(set(FIELDS) - set(PROJECTED)) * 3 != 108:
                return False
            altered = changed_cell(full_documents[index], "common_z_estimate", 0.7)
            # One deliberately changed unscored diagnostic must not change the
            # twelve-field projection. This does not claim all108 were perturbed.
            if bridge.normalize(encode(altered), cases[index], "A") != bridge.normalize(
                    encode(full_documents[index]), cases[index], "A"):
                return False
        return True
    suite.check("procedure.additional108_retained_unscored", additional_fields_unscored)

    setup_sha = invented_sha("setup-lock")
    invented_files = [{"name": "invented-%02d.tar" % index, "bytes": 1,
                       "sha256": invented_sha("archive-%d" % index)} for index in range(82)]
    fixed = {"expected_staging_files": invented_files, "R_archive_bytes": 40,
             "OS_archive_bytes": 42, "base": "sha256:" + invented_sha("base-image")}
    staging = {"schema": "nider_portable_dependency_staging_v1",
               "setup_lock_sha256": setup_sha, "archive_count": 82,
               "input_scope": "only_locked_dependencies_and_installers",
               "files": invented_files, "archive_body_read_bytes": 82,
               "root": str(out / "invented-staging-not-materialized")}
    plan = build.make_plan(staging, str(out / "invented-owner"), "nider-clean-public-controls",
                           fixed, setup_sha)
    write_new(out / "invented-build-plan.json", encode(plan))
    suite.check("build.inert_committed_entrypoint", lambda:
                'ENTRYPOINT ["/bin/false"]' in plan["commit_argv"] and
                "ENTRYPOINT []" not in plan["commit_argv"] and
                "CMD []" in plan["commit_argv"] and
                "USER 65534:65534" in plan["commit_argv"])
    suite.check("build.offline_plan_only", lambda:
                plan["execution_selected"] is False and plan["acquisition_selected"] is False and
                plan["candidate_inputs_mounted"] == [] and plan["network"] == "none" and
                "--network=none" in plan["create_argv"] and "--pull=never" in plan["create_argv"] and
                plan["platform"] == "linux/arm64" and plan["maximum_attempts"] == 1)
    altered_staging = deepcopy(staging)
    altered_staging["files"].pop()
    suite.check("build.staging_identity", lambda: reject(
        lambda: build.make_plan(altered_staging, str(out / "invented-owner"),
                                "nider-clean-public-controls", fixed, setup_sha),
        "complete_locked_staging_identity"))
    suite.check("build.invalid_name", lambda: reject(
        lambda: build.make_plan(staging, str(out / "invented-owner"), "foreign-build",
                                fixed, setup_sha), "owned_build_name"))
    suite.check("build.relative_owner_root", lambda: reject(
        lambda: build.make_plan(staging, "relative-owner", "nider-clean-public-controls",
                                fixed, setup_sha), "build_owner_root"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=str(Path(__file__).resolve().parent.parent),
                        help="Public package root; defaults to parent of tests/.")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    package = checked_path(args.package)
    out = checked_path(args.output)
    need(package.is_dir() and out.parent.is_dir() and not out.exists(), "fresh_source_output")
    source_reads = 0
    for entry in SOURCE_PINS:
        path = checked_path(str(package / entry["relative_path"]))
        need(path.is_file() and path.stat().st_size == entry["bytes"] <= 16384, "source_extent")
        raw = path.read_bytes()
        source_reads += len(raw)
        need(sha(raw) == entry["sha256"], "source_identity")
    need(len(CONTROL_IDS) == len(set(CONTROL_IDS)), "declared_control_membership")
    out.mkdir(mode=0o700)
    sys.dont_write_bytecode = True
    suite = Controls()
    try:
        compare = load_module("public_control_compare_local", package / "comparator/compare_local.py")
        with fresh_module_namespace():
            schema_and_owner_controls(package, out, suite, compare)
        with fresh_module_namespace():
            runtime_controls(package, out, suite)
        need(tuple(row["id"] for row in suite.rows) == CONTROL_IDS, "complete_ordered_control_membership")
        state = "PASS" if all(row["status"] == "PASS" for row in suite.rows) else "FAIL"
        result = {"schema": "nider_public_invented_controls_v1", "status": state,
                  "declared_controls": len(CONTROL_IDS), "observed_controls": len(suite.rows),
                  "controls": suite.rows, "source_initial_identity_bytes": source_reads,
                  "fixtures": "invented_only_no_scientific_payloads",
                  "full_original_field_partition": [27, 21, 72],
                  "procedure_cases": 4, "procedure_statuses": 48,
                  "hypothetical_additional_unscored_per_case": 108,
                  "native_calls": 0, "network_calls": 0, "subprocess_calls": 0,
                  "new_benchmarks": 0, "submission_ready_established": False}
    except Exception as error:
        result = {"schema": "nider_public_invented_controls_v1", "status": "INCOMPLETE",
                  "declared_controls": len(CONTROL_IDS), "observed_controls": len(suite.rows),
                  "controls": suite.rows, "error_class": type(error).__name__, "error": str(error),
                  "retry": False}
    write_new(out / "RESULTS.json", encode(result))
    print(json.dumps({"status": result["status"], "observed_controls": len(suite.rows),
                      "declared_controls": len(CONTROL_IDS), "output": str(out)}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
