"""Complete original programme metadata, source admission and phase graph.

No data/model/native imports, process launch, or target access occurs here.
Qualification is operator infrastructure, never a candidate-supplied flag.
"""
from .strict import need, natural, sha, digest, exact_keys, encoded

TASK = "PAPER-ROOT-ADD-020"
CHECKS = {"source_identity", "complete_headers", "physical_clocks", "feature_semantics",
          "response_rate_units",
          "cell_and_face_joins", "inclusion_provenance", "native_numeric_parity",
          "independent_reference_competence", "exposure_isolation", "complete_resource_profile",
          "external_process_closure", "target_access_authority"}
REGIMES = ("calibrated_held_face", "unfamiliar_to_familiar_transfer")
ACTORS = ("A", "B", "reference")
VARIANTS = (("published_geometry", "published_paired964", "STA"),
            ("native_sta", "native_literal", "STA"),
            ("native_ols", "native_literal", "OLS_INTERCEPT"),
            ("formula_sensitivity", "published_paired964", "PAPER_WHITENED"))
CONFIGS = {
    "A_TP_set3": ("A", "TP", 3), "A_AM_set2": ("A", "AM", 2),
    "A_ML_set2": ("A", "ML", 2), "A_PR_set2": ("A", "PR", 2),
    "B_PR_set2": ("B", "PR", 2), "C_AM_set2": ("C", "AM", 2),
    "D_ML_set2": ("D", "ML", 2), "E_PR_set3": ("E", "PR", 3),
    "E_TP_set3": ("E", "TP", 3), "E_AM_set2": ("E", "AM", 2),
    "pooled_TP_set3": ("pooled", "TP", 3), "pooled_AM_set2": ("pooled", "AM", 2),
    "pooled_ML_set2": ("pooled", "ML", 2), "pooled_PR_set2": ("pooled", "PR", 2),
}


def validate_contract(contract):
    need(type(contract) is dict and contract.get("schema") == "paper020_programme_contract_v1"
         and contract.get("task_id") == TASK, "contract", "Exact IT programme contract required")
    cases = contract.get("configurations")
    need(type(cases) is list and len(cases) == 14, "coverage", "Fourteen configurations required")
    seen = {}
    for case in cases:
        name = case.get("configuration")
        need(name in CONFIGS and name not in seen, "coverage", "Exact unique original configurations required")
        expected = CONFIGS[name]
        need((case.get("subject_label"), case.get("region"), case.get("stimulus_set")) == expected,
             "contract", "Source animal/region/stimulus mismatch")
        seen[name] = case
    need(set(seen) == set(CONFIGS), "coverage", "Complete configuration set required")
    roles = contract.get("source_roles")
    need(type(roles) is list and len(roles) == 30 and len({r.get("member") for r in roles}) == 30,
         "coverage", "All thirty distinct original MAT members required")
    counts = {k: sum(r.get("role") == k for r in roles) for k in
              ("face_response", "face_features", "ancillary_screening_response", "screening_labels")}
    need(counts == {"face_response": 14, "face_features": 2, "ancillary_screening_response": 13,
                    "screening_labels": 1}, "coverage", "Exact original source roles required")
    members = {r["member"]: r for r in roles}
    release = contract.get("source_release", {})
    files = release.get("regular_files", {})
    need(type(files) is dict and len(files) == 43 and set(members) <= set(files)
         and len([p for p in files if p.endswith(".mat")]) == 30
         and sum(files.values()) == 118563240
         and release.get("archive_bytes") == 116338858
         and release.get("archive_md5") == "6375131644534cc0d496278b4044323a",
         "source", "Complete 43-file declared original archive required")
    for member, role in members.items():
        need(files[member] == role["declared_bytes"], "source", "MAT/source archive size mismatch")
    for case in cases:
        need(members.get(case["data_member"], {}).get("configuration") == case["configuration"]
             and members.get(case["feature_member"], {}).get("role") == "face_features",
             "contract", "Native caller/member join mismatch")
    need(contract.get("actors") == list(ACTORS) and contract.get("regimes") == list(REGIMES)
         and contract.get("outer_folds") == 6 and contract.get("inner_folds") == 4
         and contract.get("null_repetitions") == 20
         and contract.get("native_modes") == ["static", "time_course"],
         "contract", "Whole accepted study required")
    v = [(x.get("name"), x.get("family"), x.get("method")) for x in contract.get("native_variants", [])]
    need(v == list(VARIANTS), "contract", "All named reproduction/parity variants required")
    primary = {k: v[0] for k, v in CONFIGS.items() if v[0] != "pooled"}
    need(contract.get("primary_population") == primary, "contract", "Actual individual biological weights required")
    return contract


def require_authority(qualification, contract, operation, verify_operator):
    """Fail before candidate, source-array, model, provider or target operands.

    verify_operator is supplied by trusted operator infrastructure, not candidate
    JSON or CLI flags. This layer does not claim cryptographic identity by itself.
    The installed source qualification is false until separate future admission.
    """
    validate_contract(contract)
    need(type(qualification) is dict and qualification.get("schema") == "paper020_installed_qualification_v1"
         and qualification.get("task_id") == TASK, "qualification", "Installed operator qualification required")
    need(qualification.get("execution_enabled") is True
         and qualification.get("scientific_evaluation_authorized") is True,
         "unqualified", "Authentic operation is not separately qualified and authorized")
    checks = qualification.get("checks")
    need(type(checks) is dict and set(checks) == CHECKS and all(v is True for v in checks.values()),
         "unqualified", "Every original-full admission gate must pass")
    need(operation in qualification.get("allowed_operations", []) and callable(verify_operator),
         "authority", "Trusted operation-specific operator verifier required")
    need(qualification.get("programme_digest") == digest(contract), "authority", "Qualification binds a different programme")
    from .source_identity import implementation_fingerprint
    source_digest = implementation_fingerprint()
    need(qualification.get("implementation_digest") == source_digest,
         "source", "The separately qualified implementation source differs from this installation")
    sha(qualification.get("admission_digest"))
    receipt = qualification.get("operator_receipt")
    need(type(receipt) is dict and verify_operator(receipt, operation, digest(contract),
                                                qualification["admission_digest"], source_digest) is True,
         "authority", "Independent operator receipt was not accepted")
    return qualification["admission_digest"]


def build_plan(contract):
    """All scientific jobs; an inspectable plan is not permission to run them."""
    validate_contract(contract)
    cases = sorted(CONFIGS)
    phases = []
    def add(identifier, kind, dependencies, **fields):
        phases.append({"id": identifier, "kind": kind, "dependencies": dependencies, **fields})
    add("admit", "source_and_exposure_admission", [])
    commits = []
    for actor in ACTORS:
        for track in ("native", "prediction"):
            key = f"commit/{actor}/{track}"
            add(key, "whole_programme_commitment", ["admit"], actor=actor, track=track)
            commits.append(key)
    add("all-policies-committed", "commitment_barrier", commits)
    native_done = []
    for actor in ACTORS:
        context = f"native-context/{actor}"
        add(context, "fresh_native_context", ["all-policies-committed"], actor=actor)
        for case in cases:
            for mode in ("static", "time_course"):
                for variant, family, method in VARIANTS:
                    key = f"native/{actor}/{case}/{mode}/{variant}"
                    add(key, "reproduction", [context], actor=actor, configuration=case,
                        mode=mode, variant=variant, family=family, method=method,
                        requires_literal_matlab=(actor == "reference" and variant in ("native_sta", "native_ols")))
                    native_done.append(key)
    prediction_done = []
    # Controls retain every original case; control identities are not extra tasks.
    for actor in ACTORS:
        for regime in REGIMES:
            for fold in range(6):
                for control in range(-1, 20):
                    tag = "observed" if control == -1 else f"null-{control:02d}"
                    context = f"view/{actor}/{regime}/{fold}/{tag}"
                    add(context, "fresh_training_context", ["all-policies-committed"],
                        actor=actor, regime=regime, outer_fold=fold, control=control,
                        query_features_available=False, configurations=cases)
                    fit_done = []
                    for case in cases:
                        key = f"fit/{actor}/{regime}/{fold}/{tag}/{case}"
                        add(key, "fit", [context], actor=actor, regime=regime, outer_fold=fold,
                            control=control, configuration=case, reference_portfolio=(actor == "reference"))
                        fit_done.append(key)
                    seal = f"seal/{actor}/{regime}/{fold}/{tag}"
                    add(seal, "seal_complete_fit", fit_done, actor=actor, configurations=cases,
                        regime=regime, outer_fold=fold, control=control)
                    queries = f"queries/{actor}/{regime}/{fold}/{tag}"
                    add(queries, "query_features_after_seal", [seal], actor=actor,
                        regime=regime, outer_fold=fold, control=control)
                    for case in cases:
                        key = f"predict/{actor}/{regime}/{fold}/{tag}/{case}"
                        add(key, "predict", [queries, seal], actor=actor, regime=regime, outer_fold=fold,
                            control=control, configuration=case, parameters_read_only=True)
                        prediction_done.append(key)
    add("validate-all", "validate_all_candidate_and_reference_outputs", native_done + prediction_done)
    add("outer-close", "independent_full_process_and_resource_closure", ["validate-all"])
    add("protected-grade", "load_targets_last_and_grade", ["outer-close"])
    identifiers = {x["id"] for x in phases}
    need(len(identifiers) == len(phases), "plan", "Duplicate phase")
    seen = set()
    for phase in phases:
        need(set(phase["dependencies"]) <= seen, "plan", "Noncausal or missing phase dependency")
        seen.add(phase["id"])
    return {"schema": "paper020_complete_phase_plan_v1", "task_id": TASK,
            "programme_digest": digest(contract), "phases": phases,
            "counts": {"configurations": 14, "native_jobs": len(native_done),
                       "prediction_jobs": len(prediction_done), "phases": len(phases),
                       "new_canonical_tasks": 0}, "authentic_qualification": False}


def phase_for(plan, identifier):
    found = [x for x in plan["phases"] if x["id"] == identifier]
    need(len(found) == 1, "plan", "Exact planned phase required")
    return found[0]
