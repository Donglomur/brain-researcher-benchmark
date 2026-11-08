"""Original-clock complete phase controller with an independent observer.

Trusted provider/executor and observer implementations require separate qualified
installation. This controller never pretends a callback receipt is OS isolation.
No process, source array, model or target is opened at import time.
"""
import time
from .strict import need, natural, sha, digest
from .programme import build_plan, require_authority


def execute_plan(plan, execute, observe, profile, *, origin_ns, clock=time.monotonic_ns):
    """Generic engine, also used with tiny invented phase graphs in tests.

    The public run_study entry binds only the full production graph. Its external
    executor handles native/candidate/reference stages, and a distinct trusted
    observer must certify actual natural completion and immutable view custody.
    """
    need(callable(execute) and callable(observe) and execute is not observe,
         "provider", "Separate trusted executor and observer required")
    natural(origin_ns, "original monotonic origin")
    required = {"duration_ns", "read_bytes", "write_bytes", "retained_bytes", "live_bytes", "max_phases"}
    need(type(profile) is dict and set(profile) == required, "resource", "Exact complete resource profile required")
    for name, value in profile.items():
        natural(value, name)
    phases = plan["phases"]
    need(profile["max_phases"] == len(phases), "resource", "Profile must cover the complete phase graph")
    deadline = origin_ns + profile["duration_ns"]
    need(origin_ns <= clock() < deadline, "clock", "Original clock is absent or expired")
    done, outputs = {}, {}
    totals = {"read_bytes": 0, "write_bytes": 0, "retained_bytes": 0, "live_bytes": 0}
    sealed = {}
    last_finished = origin_ns
    for phase in phases:
        need(phase["id"] not in done and set(phase["dependencies"]) <= set(done),
             "plan", "Complete causal phase order required")
        need(clock() < deadline, "deadline", "Original whole-study deadline exceeded")
        parents = {k: outputs[k] for k in phase["dependencies"]}
        binding = digest({"phase": phase, "parents": parents, "origin_ns": origin_ns,
                          "programme_digest": plan["programme_digest"], "implementation_digest":plan.get("implementation_digest")})
        # No callback may load targets before this final planned phase.
        if phase["kind"] == "load_targets_last_and_grade":
            need("outer-close" in done and done["outer-close"]["natural_complete"] is True,
                 "closure", "All numerical jobs and external closure must precede targets")
        producer_failure = None
        try:
            result = execute(phase, parents, origin_ns, deadline, binding)
        except Exception as error:
            # The independent operator observer is still invoked to close and
            # log the failed process. Never turn an exception into completion.
            producer_failure = type(error).__name__
            result = {"phase_id":phase["id"], "binding_digest":binding, "artifact":{},
                      "receipt":{"producer_exception_type":producer_failure}}
        receipt = observe(phase, result, origin_ns, deadline, binding)
        need(producer_failure is None, "producer", "Producer raised; observer was invoked, no completion claimed")
        need(type(result) is dict and set(result) == {"phase_id", "binding_digest", "artifact", "receipt"},
             "producer", "Exact complete producer return required")
        need(result["phase_id"] == phase["id"] and result["binding_digest"] == binding,
             "producer", "Producer returned another phase or binding")
        need(type(receipt) is dict and receipt.get("phase_id") == phase["id"]
             and receipt.get("binding_digest") == binding and receipt.get("origin_ns") == origin_ns,
             "observer", "Independent observer binding/original clock required")
        need(receipt.get("natural_complete") is True and receipt.get("exit_code") == 0
             and type(receipt.get("exit_code")) is int and receipt.get("all_descendants_closed") is True,
             "closure", "Natural zero exit and external descendant closure required")
        if phase["kind"] in ("fit", "predict", "reproduction"):
            need(receipt.get("view_isolation_verified") is True
                 and receipt.get("source_seal_unchanged") is True
                 and receipt.get("protected_grading_targets_absent") is True,
                 "isolation", "Independent OS/view and source-custody observation required")
        finish = receipt.get("finished_ns")
        observed_now = clock()
        need(type(finish) is int and type(observed_now) is int
             and last_finished <= finish <= observed_now < deadline,
             "clock", "Phase closure is outside the original clock")
        last_finished = finish
        for key in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes"):
            value = receipt.get(key)
            natural(value, key, zero=True)
            if key == "live_bytes":
                totals[key] = max(totals[key], value)
            else:
                totals[key] += value
            need(totals[key] <= profile[key], "resource", "Complete programme resource bound exceeded")
        artifact = result["artifact"]
        digest(artifact)  # Plain finite metadata, never untrusted executable objects.
        if phase["kind"] == "fit":
            sha(artifact.get("model_digest")); sha(artifact.get("fit_receipt_digest"))
            need(receipt.get("fit_receipt_digest") == artifact["fit_receipt_digest"]
                 and receipt.get("model_digest_after_fit") == artifact["model_digest"],
                 "seal", "Independent observer must bind the actual fitted artifact and closure receipt")
        if phase["kind"] == "seal_complete_fit":
            need(type(artifact) is dict and set(artifact.get("fit_models", {})) == set(phase["configurations"])
                 and set(artifact.get("fit_receipts", {})) == set(phase["configurations"]),
                 "seal", "Every original configuration must fit before query exposure")
            for key, parent in parents.items():
                case = key.rsplit("/", 1)[-1]
                need(case in artifact["fit_models"] and artifact["fit_models"][case] == parent["model_digest"]
                     and artifact["fit_receipts"][case] == parent["fit_receipt_digest"],
                     "seal", "Whole fit seal must bind every actual independently closed model")
            sealed[phase["id"]] = digest(artifact)
        if phase["kind"] == "query_features_after_seal":
            need(len(phase["dependencies"]) == 1 and phase["dependencies"][0] in sealed,
                 "leakage", "Query features require the complete sealed fit")
            need(artifact.get("seal_digest") == sealed[phase["dependencies"][0]],
                 "seal", "Query exposure must bind the complete immutable fit seal")
        if phase["kind"] == "predict":
            seals = [p for p in phase["dependencies"] if p in sealed]
            need(len(seals) == 1, "seal", "Prediction requires its actual completed fit seal")
            seal = outputs[seals[0]]
            case = phase["configuration"]
            need(artifact.get("model_digest") == seal["fit_models"][case]
                 and artifact.get("fit_receipt_digest") == seal["fit_receipts"][case]
                 and receipt.get("model_digest_after_inference") == seal["fit_models"][case],
                 "seal", "Observed inference must preserve the sealed fitted model")
        if phase["kind"] == "independent_full_process_and_resource_closure":
            need(artifact.get("all_outputs_validated") is True and artifact.get("resources_passed") is True
                 and artifact.get("natural_complete") is True and artifact.get("all_descendants_closed") is True,
                 "closure", "Complete independently observed outer closure required")
            for key in ("native_bundle_digest", "prediction_bundle_digest", "expected_bundle_digest", "native_schema_digest"):
                sha(artifact.get(key))
        outputs[phase["id"]] = artifact
        done[phase["id"]] = receipt
    need(len(done) == len(phases) and phases[-1]["kind"] == "load_targets_last_and_grade",
         "coverage", "Complete programme and target-last grade required")
    finished_ns = clock()
    need(type(finished_ns) is int and last_finished <= finished_ns < deadline,
         "deadline", "Final completion reached or exceeded the original strict deadline")
    return {"status": "complete", "programme_digest": plan["programme_digest"], "origin_ns": origin_ns,
            "finished_ns": finished_ns, "phase_count": len(done), "resources": totals,
            "result": outputs[phases[-1]["id"]], "scientific_qualification_claim": False}


def run_study(contract, qualification, verify_operator, execute, observe, profile, *, origin_ns):
    require_authority(qualification, contract, "full_study", verify_operator)
    plan = build_plan(contract)
    plan["implementation_digest"] = qualification["implementation_digest"]
    return execute_plan(plan, execute, observe, profile, origin_ns=origin_ns)
