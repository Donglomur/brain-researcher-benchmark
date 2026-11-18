"""Join NEURAL-047 observation results to complete operator session audits.

These checks bind saved artifacts; they are not execution attestation, filesystem
isolation, native-input qualification, or evidence of direct/model understanding.
Only an operator may supply the delivery module and frozen expected contexts.
"""
import argparse
import importlib.util
from pathlib import Path


def _key(io, context):
    io.need(type(context) is dict and type(context.get("fold_id")) is str and
            type(context.get("arm")) is str, "Audit context identity")
    return context["fold_id"], context["arm"]


def validate_audit(delivery, expected_context, response, audit):
    """Validate one hash-only audit without reading observations or private gold.

    Intermediate requests/responses are hashes, so this cannot replay the viewer
    or attest that the process actually executed. The trusted operator must retain
    the independently supplied expected context and the actual session artifacts.
    """
    io, cap = delivery.io, delivery.CAP
    io.exact(audit, ["schema", "context", "closed", "response_persisted",
                     "failure_type", "actions", "head_sha256",
                     "accepted_response_payload_bytes"])
    io.need(audit["schema"] == "neural047-observation-transcript-v1" and
            audit["context"] == expected_context == response["context"],
            "Audit, response and frozen operator context must agree")
    io.need(audit["closed"] is True and audit["response_persisted"] is True and
            audit["failure_type"] is None,
            "Only successfully closed and persisted observation sessions may be collected")
    actions = audit["actions"]
    count = response["observation_actions"]
    io.need(type(count) is int and 1 <= count < 10000 and type(actions) is list and
            len(actions) == count + 1, "Complete opening, observations and terminal action required")
    if expected_context["mode"] == "direct_observation":
        io.need(len(actions) == 2, "Direct condition contains opening and terminal response only")
    previous = "0" * 64
    accepted_bytes = 0
    for index, row in enumerate(actions):
        io.exact(row, ["index", "request_pin", "response_pin", "previous", "sha256"])
        io.need(type(row["index"]) is int and row["index"] == index and row["previous"] == previous,
                "Ordered complete audit chain")
        io.check_pin(row["request_pin"], cap)
        io.check_pin(row["response_pin"], cap)
        body = {name: row[name] for name in ("index", "request_pin", "response_pin", "previous")}
        io.need(row["sha256"] == delivery.digest(body)["sha256"], "Audit chain hash mismatch")
        previous = row["sha256"]
        accepted_bytes += row["response_pin"]["bytes"]
    io.need(actions[0]["request_pin"] == delivery.digest({"action": "open"}),
            "Audit starts at the single session opening")
    io.need(actions[-1]["previous"] == response["observation_transcript_sha256"] and
            actions[-1]["response_pin"] == delivery.digest(response) and
            audit["head_sha256"] == previous,
            "Terminal response must be the persisted tail of this audit")
    outcome = response["outcome"]
    if outcome["status"] == "complete":
        terminal_request = {"action": "submit", "predictions": outcome["predictions"]}
    else:
        io.need(outcome["status"] == "abstain", "Known terminal outcome")
        terminal_request = {"action": "abstain", "reason": outcome["reason"]}
    io.need(actions[-1]["request_pin"] == delivery.digest(terminal_request),
            "Terminal action must match the submitted probabilities or explicit abstention")
    io.need(type(audit["accepted_response_payload_bytes"]) is int and
            audit["accepted_response_payload_bytes"] == accepted_bytes and 0 < accepted_bytes <= cap,
            "Complete accepted response byte accounting")
    return {"delivery_id": expected_context["delivery_id"],
            "audit_pin": delivery.digest(audit), "response_pin": delivery.digest(response)}


def collect_audited(delivery, panel, mode, expected_contexts, responses, audits):
    """Collect every required worm/arm, refusing any missing or failed audit.

    The existing collector remains authoritative for the panel, target-free
    response admission and scorer format. Audits add a separate integrity check.
    """
    collection = delivery.collect(panel, mode, expected_contexts, responses)
    io = delivery.io
    io.need(type(audits) is list and len(audits) == len(expected_contexts),
            "Exactly one operator audit for every required context")
    expected = {_key(io, context): context for context in expected_contexts}
    returned = {_key(io, response["context"]): response for response in responses}
    seen, pins = set(), []
    for audit in audits:
        io.need(type(audit) is dict, "Operator audit object")
        key = _key(io, audit.get("context"))
        io.need(key in expected and key not in seen, "No extra, duplicate or foreign-context audits")
        seen.add(key)
        pins.append(validate_audit(delivery, expected[key], returned[key], audit))
    io.need(seen == set(expected), "Complete audit support")
    return {"schema": "neural047-audited-observation-collection-v1", "mode": mode,
            "collection": collection, "operator_audits": pins,
            "qualification": "saved_operator_artifact_integrity_only"}


def collect_paired_audited(delivery, panel, contexts, responses, audits):
    """Keep paired modes separate and require the same complete observations."""
    io = delivery.io
    io.exact(audits, delivery.MODES)
    # This checks mode separation and identical permitted observations before
    # accepting either mode. It never opens a private target callback.
    delivery.collect_paired(panel, contexts, responses)
    return {"schema": "neural047-paired-audited-observation-collections-v1",
            "packet_id": panel["packet_id"], "protocol_pin": delivery.digest(delivery.PROTOCOL),
            "collections": {mode: collect_audited(delivery, panel, mode, contexts[mode],
                                                  responses[mode], audits[mode])
                            for mode in delivery.MODES},
            "qualification": "saved_operator_artifact_integrity_only"}


def _load_delivery():
    source = Path(__file__).resolve().with_name("delivery.py")
    spec = importlib.util.spec_from_file_location("neural047_audited_delivery", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, required=True)
    parser.add_argument("--contexts", type=Path, required=True)
    parser.add_argument("--responses", type=Path, required=True)
    parser.add_argument("--audits", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("direct_observation", "typed_viewer", "paired"), required=True)
    args = parser.parse_args()
    delivery = _load_delivery()
    io, cap = delivery.io, delivery.CAP
    io.need(not io.regular(args.output).exists(), "Fresh operator collection output")
    panel, contexts, responses, audits = [io.json_file(path, cap) for path in
                                          (args.panel, args.contexts, args.responses, args.audits)]
    result = (collect_paired_audited(delivery, panel, contexts, responses, audits)
              if args.mode == "paired" else
              collect_audited(delivery, panel, args.mode, contexts, responses, audits))
    io.put(args.output, result, cap)


if __name__ == "__main__":
    main()
