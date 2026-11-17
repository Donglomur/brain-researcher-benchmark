"""Construct exact stage requests from a frozen source/interface and real receipts.

Construction is metadata-only and never manufactures authority. Returned drafts
cannot execute until independent external evidence binds every input, parameter,
source digest, output surface and completed predecessor.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .contract import load_contract
from .io import Artifact, ContractError, canonical, capture, decode
from .workflow import COMPONENT, EXTERNAL_INPUT_ROLES, contract_digest


def interface_union(root=None, *, meter=None, contract=None):
    root = Path(root) if root else Path(__file__).parent.parent
    contract = contract or load_contract(root / "contract", meter=meter)
    declarations = {}
    for component in ("preparation", "references", "runtime", "owner"):
        path = root / component / "INTERFACE.json"
        body = capture(path, 2_000_000, meter=meter)
        value = decode(body)
        inputs = value.get("stage_input_keys")
        output_inventory = value.get("stage_outputs")
        principal = value.get("principal_output_keys")
        roles = value.get("input_roles")
        if not all(isinstance(x, dict) for x in (inputs, output_inventory, principal, roles)):
            raise ContractError("concrete stage input/output interface absent: " + component)
        expected = {n for n, module in COMPONENT.items() if module.startswith(component + ".")}
        if set(inputs) != expected or set(output_inventory) != expected or set(principal) != expected:
            raise ContractError("component interface does not cover its exact stages: " + component)
        for stage in sorted(expected):
            if not isinstance(inputs[stage], list) or len(inputs[stage]) != len(set(inputs[stage])):
                raise ContractError("unique exact input key list required")
            inventory, keys = output_inventory[stage], principal[stage]
            if (not isinstance(inventory, list) or not inventory or not isinstance(keys, list)
                    or not keys or len(keys) != len(set(keys))):
                raise ContractError("complete output inventory and unique principal keys required")
            outputs = {}
            seen = set()
            fixed_seen = set()
            for desc in inventory:
                if not isinstance(desc, dict) or ("key" in desc) == ("key_pattern" in desc):
                    raise ContractError("each output needs one exact key or frozen pattern")
                if set(desc) - {"key", "key_pattern", "role", "schema", "condition"}:
                    raise ContractError("unknown output interface descriptor field")
                if any(not isinstance(desc.get(k), str) or not desc[k]
                       for k in ("role", "schema", "condition")):
                    raise ContractError("every output needs role, schema and production condition")
                name = desc.get("key", desc.get("key_pattern"))
                identity = (name, desc["role"], desc["schema"], desc["condition"])
                if (not isinstance(name, str) or not name or identity in seen
                        or ("key" in desc and name in fixed_seen)):
                    raise ContractError("duplicate/empty concrete output declaration")
                seen.add(identity)
                if "key" in desc:
                    fixed_seen.add(name)
                if "key" in desc and name in keys:
                    outputs[name] = {"role": desc["role"], "schema": desc["schema"]}
            if set(outputs) != set(keys):
                raise ContractError("principal outputs must have exact descriptors")
            for name in inputs[stage]:
                if name not in roles or not isinstance(roles[name], str) or not roles[name]:
                    raise ContractError("input role undeclared: " + name)
            declarations[stage] = {"inputs": inputs[stage], "input_roles": {k: roles[k] for k in inputs[stage]},
                                   "outputs": outputs, "output_inventory": inventory,
                                   "parameters": value.get("stage_parameters", {}).get(stage),
                                   "nested_artifact_reads": value.get("nested_artifact_reads", {}).get(stage, []),
                                   "component": component,
                                   "interface_sha256": hashlib.sha256(body).hexdigest()}
    if set(declarations) != set(contract["nodes"]):
        raise ContractError("complete 28-stage concrete interface union required")
    # Resolve each input by an exact key/role on a completed ancestor; no fuzzy
    # filename lookup, same-name substitution, or later-stage artifact.
    bindings = {}
    for stage in contract["order"]:
        bindings[stage] = {}
        for key, role in declarations[stage]["input_roles"].items():
            matches = [(a, key) for a in contract["ancestors"][stage]
                       if key in declarations[a]["outputs"] and declarations[a]["outputs"][key]["role"] == role]
            if len(matches) == 1:
                bindings[stage][key] = {"producer": matches[0][0], "output_key": key, "role": role}
            elif not matches and role in EXTERNAL_INPUT_ROLES.get(stage, set()):
                bindings[stage][key] = {"producer": "external_explicit_input", "output_key": key, "role": role}
            else:
                raise ContractError("missing/ambiguous concrete ancestor for " + stage + ":" + key)
    return {"schema": "neural063_concrete_interface_union_v1", "contract_sha256": contract_digest(contract),
            "stage_order": contract["order"], "stages": declarations, "bindings": bindings,
            "node_count": 28, "entry_predicates": 122}


def compile_request(*, stage, attempt, implementation, interfaces, completions,
                    external_inputs, parameters, output_root, issuers,
                    external_evidence, attempt_expires_at, contract=None):
    contract = contract or load_contract()
    if stage not in contract["nodes"] or interfaces["contract_sha256"] != contract_digest(contract):
        raise ContractError("stage/interface contract mismatch")
    required = contract["ancestors"][stage]
    if set(completions) != required:
        raise ContractError("exact complete ancestor receipt set required to compile")
    receipts, receipt_refs = {}, {}
    for ancestor in contract["order"]:
        if ancestor not in required:
            continue
        ref = Artifact.parse(completions[ancestor])
        if ref.role != "signed_stage_completion" or ref.producer != ancestor:
            raise ContractError("wrong completion descriptor role/producer")
        envelope = decode(capture(ref.path, 4_000_000, descriptor=ref))
        payload = envelope.get("payload", {})
        if (payload.get("attempt") != attempt or payload.get("stage") != ancestor or
                payload.get("contract_sha256") != interfaces["contract_sha256"] or
                payload.get("implementation_sha256") != implementation["sha256"]):
            raise ContractError("receipt metadata belongs to another source/attempt")
        decision=payload.get("content",{})
        if (payload.get("kind")!="completion" or payload.get("evidence_id")!="DONE_"+ancestor or
                decision.get("schema")!="neural063_terminal_publication_v1" or
                decision.get("authority_rule")!="qualified_single_link_kernel_commit_v4" or
                ref.path!=str(Path(output_root)/"journal"/(ancestor+".final.json"))):
            raise ContractError("drafting requires the fixed authoritative terminal descriptor")
        provisional=Artifact.parse(decision["provisional"])
        if (provisional.role!="signed_stage_provisional" or provisional.producer!=ancestor or
                provisional.path!=str(Path(output_root)/"journal"/(ancestor+".candidate.json"))):
            raise ContractError("terminal metadata has no exact provisional body")
        candidate=decode(capture(provisional.path,4_000_000,descriptor=provisional)).get("payload",{})
        if (candidate.get("kind")!="completion_candidate" or candidate.get("evidence_id")!="CANDIDATE_"+ancestor or
                any(candidate.get(k)!=payload.get(k) for k in ("attempt","stage","implementation_sha256","contract_sha256","prerequisites"))):
            raise ContractError("provisional metadata scope differs from terminal decision")
        # Drafting opens metadata only and makes no signature/current-publication
        # claim. authorize_stage later repeats the complete authenticated reader
        # protocol, including the single kernel-commit authority, exact signature,
        # publication-time bounds and current-attempt admission. Telemetry is
        # independent of that authority and cannot revoke a committed fact.
        receipts[ancestor]=dict(candidate["content"],outcome=decision["outcome"],failure=decision["failure"])
        receipt_refs[ancestor] = ref.object()
    inputs = {}
    used_external = set()
    for key, binding in interfaces["bindings"][stage].items():
        producer = binding["producer"]
        if producer == "external_explicit_input":
            if key not in external_inputs:
                raise ContractError("required external input absent: " + key)
            ref = Artifact.parse(external_inputs[key]); used_external.add(key)
        else:
            if binding["output_key"] not in receipts[producer].get("artifacts", {}):
                raise ContractError("actual completed producer omitted required output: " + key)
            ref = Artifact.parse(receipts[producer]["artifacts"][binding["output_key"]])
            if ref.producer != producer:
                raise ContractError("actual output producer changed")
        if ref.role != binding["role"]:
            raise ContractError("actual output role changed: " + key)
        inputs[key] = ref.object()
    if set(external_inputs) != used_external:
        raise ContractError("unrequested external inputs are forbidden")
    expected_external = {e for e in contract["nodes"][stage]["entry_evidence_ids"] if e.startswith("EXT_")}
    if set(external_evidence) != expected_external:
        raise ContractError("exact external entry records required for stage")
    request = {"schema": "neural063_stage_request_v1", "attempt": attempt, "stage": stage,
               "implementation": implementation, "issuers": issuers,
               "evidence": external_evidence, "completions": receipt_refs,
               "inputs": inputs, "parameters": parameters, "output_root": output_root,
               "attempt_expires_at": attempt_expires_at}
    # Do not claim signatures verified: execution performs that check using the
    # separately provisioned trusted issuer keyring before any operational work.
    authority_content = {"operation": "authorized_scientific_stage", "stage": stage,
                         "inputs": inputs,
                         "parameters_sha256": hashlib.sha256(canonical(parameters)).hexdigest(),
                         "output_root": output_root, "attempt_expires_at": attempt_expires_at}
    return {"schema": "neural063_stage_request_draft_v1", "request": request,
            "request_sha256": hashlib.sha256(canonical(request)).hexdigest(),
            "authority_content_to_review": authority_content,
            "missing_authority_content": ["external consent_record"],
            "signatures_verified": False, "scientific_execution": False}
