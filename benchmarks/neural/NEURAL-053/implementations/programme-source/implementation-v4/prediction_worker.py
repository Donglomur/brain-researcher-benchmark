"""Actual selected query evaluator worker, invoked only by a qualified operator.

The parent must independently admit all160 methods before launching any worker.
This worker rechecks its one exact admission before opening its query artifact.
The parent observes this process's natural completion; the worker cannot issue
its own completed-process admission receipt or approve itself.
"""
import argparse
import json
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from cohort import require
from io_support import Budget, authenticate_file, canonical_bytes, object_digest
from storage import read_json_exact, read_array_exact, write_array_fresh, write_json_fresh
from method.plan import load_plan
from method.admission import TrustedRegistry, execute_admitted, validate_admission
from grading import array_digest, required_case_keys


def run(request, budget):
    require(request.get("schema") == "neural053_prediction_worker_v1" and
            request.get("profile") in ("canonical", "invented_engineering"), "Exact worker request")
    # Operator-pinned approval registry is authenticated before any plan/query
    # body. No registry expected pin is accepted from a candidate namespace.
    registry_pin = request["registry"]
    budget.charge("source_read", registry_pin["bytes"])
    registry = TrustedRegistry.from_file(registry_pin["path"], expected_bytes=registry_pin["bytes"],
                                        expected_sha256=registry_pin["sha256"])
    receipt = read_json_exact(request["receipt"]["path"], request["receipt"], budget)
    bindings = read_json_exact(request["bindings"]["path"], request["bindings"], budget)
    document = read_json_exact(request["plan"]["path"], request["plan"], budget)
    plan = load_plan(document)
    whole_pin = request["whole_method_gate"]
    whole = read_json_exact(whole_pin["path"], whole_pin, budget)
    require(whole.get("schema") == "neural053_whole_method_gate_v1" and
            object_digest(whole) in registry.document()["approved_qualifications"],
            "Operator-approved complete160-method gate required")
    require([tuple(x["context_key"]) for x in whole.get("methods", [])] == list(required_case_keys()),
            "Whole-method gate has every exact candidate/reference context")
    selection_pin = request["reference_selection"]
    selection = read_json_exact(selection_pin["path"], selection_pin, budget)
    require(selection.get("schema") == "neural053_reference_selection_v2" and
            selection.get("selection_phase") == "training_only_before_query" and
            object_digest(selection) == whole.get("reference_selection_sha256"),
            "Exact pre-query primary reference selection in whole-study authority")
    own = next(x for x in whole["methods"] if x["context_key"] == request["context_key"])
    from method.plan import digest as method_digest
    require(own["receipt_sha256"] == method_digest(receipt) and
            own["bindings_sha256"] == method_digest(bindings) and own["plan_sha256"] == plan.digest,
            "Worker method joins whole-study seal")
    require(request["query"]["bytes"] == bindings["artifacts"]["query_artifact"]["bytes"] and
            request["query"]["sha256"] == bindings["artifacts"]["query_artifact"]["sha256"],
            "Worker query operand is the exact operator-bound artifact")
    validate_admission(receipt, bindings, registry, plan, required_profile=request["profile"])
    descriptor_pin = request["query_descriptor"]
    bound_descriptor = bindings["artifacts"]["query_descriptor"]
    require(all(descriptor_pin[k] == bound_descriptor[k] for k in ("bytes", "sha256")),
            "Actual descriptor operand joins independent method admission")
    descriptor = read_json_exact(descriptor_pin["path"], descriptor_pin, budget)
    require(descriptor.get("schema") == "neural053_query_support_v2" and
            descriptor.get("classes") == list(range(1, bindings["class_count"] + 1)) and
            type(descriptor.get("query_ids")) is list and
            len(descriptor["query_ids"]) == bindings["query_rows"] and
            all(type(x) is str and x for x in descriptor["query_ids"]) and
            len(set(descriptor["query_ids"])) == bindings["query_rows"],
            "Exact ordered complete query support, no target metadata")
    require(set(descriptor) == {"schema", "case_id", "classes", "query_ids"},
            "Only opaque query identity and known class support")

    def query_loader():
        return read_array_exact(request["query"]["path"], request["query"],
                                (bindings["query_rows"], bindings["input_dim"]), budget)

    probabilities, admitted = execute_admitted(receipt, bindings, registry, plan, query_loader,
                                               required_profile=request["profile"])
    import numpy as np
    probabilities = np.asarray(probabilities, dtype=np.float32)
    artifact = write_array_fresh(request["output_path"], probabilities, budget)
    authenticate_file(request["query"]["path"], request["query"], budget)
    result = {"schema": "neural053_worker_output_v1", "context_key": request["context_key"],
              "method_admission": admitted, "bindings_digest": object_digest(bindings),
              "probabilities_digest": array_digest(probabilities), "probability_artifact": artifact,
              "reference_selection_digest": object_digest(selection),
              "query_descriptor_digest": object_digest(descriptor),
              "profile": request["profile"], "local_plan_and_engine_unchanged": True,
              "natural_process_completion": "must_be_observed_by_parent_after_exit",
              "scientific_qualification_conferred": False}
    write_json_fresh(request["output_manifest_path"], result, budget)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--request-bytes", required=True, type=int)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--origin-monotonic", required=True, type=float)
    parser.add_argument("--deadline-monotonic", required=True, type=float)
    parser.add_argument("--source-read-cap", required=True, type=int)
    parser.add_argument("--artifact-write-cap", required=True, type=int)
    args = parser.parse_args()
    budget = Budget({"source_read": args.source_read_cap, "artifact_write": args.artifact_write_cap},
                    args.origin_monotonic, args.deadline_monotonic)
    request = read_json_exact(args.request, {"bytes": args.request_bytes, "sha256": args.request_sha256}, budget)
    result = run(request, budget)
    # Compact completion metadata; never print numerical probabilities or answers.
    print(json.dumps({"status": "worker_returned", "profile": result["profile"],
                      "scientific_qualification_conferred": False, "used": budget.used}))


if __name__ == "__main__":
    main()
