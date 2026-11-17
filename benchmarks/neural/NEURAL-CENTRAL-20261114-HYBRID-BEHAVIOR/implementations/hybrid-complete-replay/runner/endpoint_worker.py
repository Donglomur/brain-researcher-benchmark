"""Selected full construction worker. No scientific work occurs on import."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--lock-sha256", required=True); args = ap.parse_args()
    here = Path(__file__).absolute().parent; body = (here / "SOURCE_LOCK.json").read_bytes()
    if hashlib.sha256(body).hexdigest() != args.lock_sha256: raise RuntimeError("selected whole source lock")
    lock = json.loads(body)
    for name, pin in lock["files"].items():
        b = (here / name).read_bytes()
        if len(b) != pin["bytes"] or hashlib.sha256(b).hexdigest() != pin["sha256"]: raise RuntimeError("whole selected source")
    sys.path.insert(0, str(here))
    import donor_checked_source as cust
    import donor_create_lifecycle as lifecycle
    import donor_process_closure as closer
    from episode_owner_base import Owner
    from endpoint_guard import endpoint_identity
    from transport_harness import EpisodeFamily
    from endpoint_controls import run_controls
    from consumer import load_accepted_private_cases, MAIN_ROWS, MAIN_ELIGIBLE, MAIN_TRIALS, MAIN_CASE_BYTES, MAIN_CASE_SHA256, GROUPS
    from reference_workflow import fit_all_references, emit
    from collections import Counter
    plan = json.loads((here / "PLAN.json").read_bytes()); plan["source_lock_sha256"] = args.lock_sha256
    out = Path(plan["output"]); signals = []; start = time.monotonic(); deadline = start + plan["worker_seconds"]
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP): signal.signal(sig, lambda s, f: signals.append(s))
    if os.getpid() != os.getpgrp(): raise RuntimeError("separately owned worker group")
    family = None; result = {"schema": "hybrid-complete-endpoint-construction-v1", "status": "FAILED", "error": None,
                            "source_lock_sha256": args.lock_sha256, "authentic_input_attempted": False,
                            "controls": None, "prefix_validation": None, "reference_result": None,
                            "scientific_count_delta": 0, "participant_campaign_run": False}
    try:
        import numpy as np
        cust.need(sys.version_info[:3] == (3, 11, 6) and np.__version__ == "2.2.6", "exact admitted host numerical versions")
        endpoint_identity(plan)
        check = out / "image-preflight"; check.mkdir(mode=0o700)
        owner = Owner(cust, closer, check, here, plan, args.lock_sha256, deadline, signals,
                      plan["operation_token"], lifecycle=lifecycle, cli_group_mode="controller")
        _, raw, _, _ = owner.call(["image", "inspect", "--format", "{{json .}}", plan["image"]])
        info = cust.strict(raw)
        cust.need(info["Id"] == plan["image"] and info["Os"] == "linux" and info["Architecture"] == "arm64", "exact existing admitted image; no pull")
        _, raw, _, _ = owner.call(["ps", "--all", "--quiet", "--no-trunc", "--filter", "label=hybrid.operation=" + plan["operation_token"]])
        cust.need(raw == b"", "fresh exclusive owned container namespace")
        family = EpisodeFamily(plan, here, out, min(deadline, time.monotonic() + plan["controls_seconds"]), signals)
        controls = run_controls(here, out / "controls", family, family.deadline)
        cust.need(controls["all_passed"] and not signals, "complete integrated control gate")
        result["controls"] = {"path": str(out / "controls/CONTROLS.json"), "control_count": controls["control_count"],
                              "real_container_episodes": controls["real_container_episodes"], "tiny_invented_ridge_fits": 800}
        cust.need(time.monotonic() < deadline and not signals, "original complete scientific horizon")
        cust.need(plan["cases"]["bytes"] == MAIN_CASE_BYTES and plan["cases"]["sha256"] == MAIN_CASE_SHA256,
                  "plan operand matches accepted complete consumer identity")
        result["authentic_input_attempted"] = True
        decisions = load_accepted_private_cases(plan["cases"]["path"])
        counts = Counter((d.subject, d.session) for d in decisions)
        trials = {(d.subject, d.session, d.trial) for d in decisions}
        cust.need(len(decisions) == MAIN_ELIGIBLE and len(trials) == MAIN_TRIALS and set(counts) == GROUPS,
                  "complete authentic population after every causal-prefix check")
        prefix = {"schema": "hybrid-complete-authentic-causal-prefix-v1", "source_rows": MAIN_ROWS,
            "eligible_decisions": len(decisions), "complete_trials": len(trials), "groups": len(counts),
            "group_decisions_private": {s + ":" + str(k): counts[(s, k)] for s, k in sorted(GROUPS)},
            "both_codings": "Every accepted ct1/ct2 source-row pair and mismatch declaration checked by the complete authenticated map parser.",
            "all_prefix_clock_visit_blocked_cue_terminal_checks_passed": True,
            "raw_initial_cue_or_JS_order_reconstructed": False, "input": plan["cases"], "count_delta": 0}
        result["prefix_validation"] = emit(out / "CAUSAL_PREFIX.json", prefix)
        references = fit_all_references(decisions, out / "references", deadline)
        reference_body = (out / "references/REFERENCE_RESULT.json").read_bytes()
        result["reference_result"] = {"path": str(out / "references/REFERENCE_RESULT.json"),
            "bytes": len(reference_body), "sha256": hashlib.sha256(reference_body).hexdigest(),
            "complete_outer_folds": references["complete_outer_folds"], "inner_ridge_fits": references["inner_ridge_fits"],
            "final_ridge_fits": references["final_ridge_fits"], "scores": references["scores"],
            "descriptive_grouped_comparisons": references["comparisons_descriptive_not_frontier_claim"]}
        cust.need(time.monotonic() < deadline and not signals, "complete scientific execution before deadline")
        result["status"] = "COMPLETE_PREFIX_AND_TRAIN_ONLY_STATISTICAL_REFERENCES"
    except BaseException as exc:
        result["error"] = {"type": type(exc).__name__, "reason": str(exc)[:2048]}
    finally:
        result["elapsed_seconds"] = time.monotonic() - start; result["signals_received"] = signals
        result["episodes_registered"] = family.count if family is not None else 0
        result["all_registered_episodes_closed"] = family is not None and len(family.rows) == family.count and all(x["complete"] or
            json.loads(Path(x["result"]).read_bytes())["cleanup"]["absent"] for x in family.rows)
        result["stronger_holds"] = ["original Julia/Float32 parity", "raw event/initial-cue reconstruction", "history-sensitive strongest comparator",
            "meaningful frontier criterion", "unmeasured LLM/candidate performance", "full-paper/symbolic/transfer claims", "original source/data rights"]
        emit(out / "RESULT.json", result)
    print(json.dumps({"status": result["status"], "complete": result["error"] is None, "no_retry": True}))
    return 0 if result["status"] == "COMPLETE_PREFIX_AND_TRAIN_ONLY_STATISTICAL_REFERENCES" else 1


if __name__ == "__main__":
    raise SystemExit(main())
