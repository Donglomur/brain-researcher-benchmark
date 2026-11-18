"""N007 supplied-information audit gate; external operator selection is the trust boundary.

No receipt is created here. An accepted descriptor must come from the trusted
operator, outside candidate outputs. Structural validation alone is not evidence
that an image inventory is complete or that hidden pretraining is matched.
"""
from pathlib import Path, PurePosixPath
import re
import contract as C

EXCLUDED = ("other_person_signals", "labelled_training_people", "task_labels",
            "score_masks", "reference_predictions", "yasa_or_other_trained_model_assets",
            "external_weights", "other_target_answers")
AUDIT_CAP = 32768
INVENTORY_CAP = 64 * 2**20


def plain(value):
    return {key: value[key] for key in ("bytes", "sha256")}


def capture(value, cap):
    C.need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}
           and type(value["path"]) is str and Path(value["path"]).is_absolute(),
           "Exact externally selected evidence descriptor")
    return C.read_exact(value["path"], plain(value), cap)


def _inventory(value, image):
    C.need(type(value) is dict and set(value) == {"schema", "image", "scope", "entries"}
           and value["schema"] == "sleep007_epoch_image_filesystem_inventory_v1"
           and value["image"] == image and value["scope"] == "complete_immutable_image_filesystem",
           "Complete filesystem inventory required; inspect/config metadata is insufficient")
    rows = value["entries"]
    C.need(type(rows) is list and rows, "Nonempty externally reviewed filesystem inventory")
    paths, regular = set(), 0
    for row in rows:
        C.need(type(row) is dict and type(row.get("path")) is str, "Inventory path record")
        path = PurePosixPath(row["path"])
        C.need(path.is_absolute() and str(path) == row["path"] and ".." not in path.parts
               and "\0" not in row["path"] and row["path"] not in paths, "Unique canonical image path")
        paths.add(row["path"])
        if row.get("kind") == "file":
            C.need(set(row) == {"path", "kind", "bytes", "sha256", "purpose"}
                   and type(row["bytes"]) is int and row["bytes"] >= 0
                   and type(row["sha256"]) is str and re.fullmatch("[0-9a-f]{64}", row["sha256"])
                   and row["purpose"] == "execution_dependency",
                   "Image files must be externally reviewed execution dependencies, not task/model assets")
            regular += 1
        elif row.get("kind") == "directory":
            C.need(set(row) == {"path", "kind"}, "Exact directory inventory")
        elif row.get("kind") == "symlink":
            C.need(set(row) == {"path", "kind", "target"} and type(row["target"]) is str
                   and 0 < len(row["target"].encode()) <= 4096 and "\0" not in row["target"],
                   "Exact externally reviewed image symlink")
        else:
            raise ValueError("Unreviewed image member kind")
    C.need(regular > 0, "Actual runtime file inventory required")


def read_selected(descriptor):
    C.need(descriptor is not None, "Externally selected matched-access audit required")
    raw = capture(descriptor, AUDIT_CAP)
    value = C.decode(raw)
    keys = {"schema", "condition", "evidence_origin", "review_scope", "image", "inventory",
            "programme", "source", "knowledge", "generation_provenance", "generation_origin", "generation_review",
            "shared_prior_policy", "additional_assets", "excluded_asset_classes",
            "hidden_pretraining", "model_revision_evidence", "causal_agent_comparison_qualified"}
    C.need(type(value) is dict and set(value) == keys and raw == C.encode(value)
           and value["schema"] == "sleep007_epoch_matched_access_audit_v1"
           and value["condition"] == C.PAIR_CONDITION
           and value["evidence_origin"] == "externally_reviewed_actual_artifacts"
           and value["review_scope"] == "supplied_assets_image_and_programme_creation",
           "Actual externally selected semantic audit required; generated/declaration-only receipts refused")
    C.need(type(value["image"]) is str and re.fullmatch("sha256:[0-9a-f]{64}", value["image"]),
           "Exact reviewed immutable image")
    for key in ("programme", "source", "knowledge", "generation_provenance"):
        C.checked_pin(value[key])
    C.need(value["generation_origin"] in ("provider_capture", "human_authored", "fixed_control")
           and value["shared_prior_policy"] == C.KNOWLEDGE_POLICY
           and value["additional_assets"] == [] and value["excluded_asset_classes"] == list(EXCLUDED)
           and value["hidden_pretraining"] == "unknown"
           and value["model_revision_evidence"] == "declared_identity_not_internal_weights"
           and value["causal_agent_comparison_qualified"] is False,
           "Explicit supplied-asset exclusions and truthful prior/causal limits")
    expected_creation = {"evidence": value["generation_provenance"],
                         "shared_knowledge": value["knowledge"],
                         "programme_frozen_before_target_access": True,
                         "known_input_scope": "shared_declared_prior_and_public_task_only",
                         "task_signal_label_reference_or_prediction_access": False,
                         "task_specific_training_or_fitting": False,
                         "additional_external_assets": [],
                         "programme_embedded_task_or_model_assets": False,
                         "evidence_scope": ("captured_request_response_and_source_lineage"
                                            if value["generation_origin"] == "provider_capture"
                                            else "externally_reviewed_source_and_access_history")}
    C.need(value["generation_review"] == expected_creation,
           "Explicit externally reviewed creation inputs/fitting/assets and source lineage")
    # These are facts asserted by the independently selected external review,
    # not facts inferred here from opaque generation bytes or programme text.
    inventory_raw = capture(value["inventory"], INVENTORY_CAP)
    inventory = C.decode(inventory_raw)
    C.need(inventory_raw == C.encode(inventory), "Canonical reviewed inventory bytes")
    _inventory(inventory, value["image"])
    return {"descriptor": dict(descriptor), "audit": value,
            "scope": "Externally selected supplied-access review; not self-proved inventory completeness or hidden-prior equality"}


def claim(runtime):
    C.need(type(runtime) is dict, "Trusted operation context required")
    value = runtime.get("claim_matched_information", False)
    C.need(type(value) is bool, "Explicit boolean matching claim")
    return value


def check_claim(scope, runtime):
    C.need(type(scope) is dict and set(scope) == {"claim_matched_information", "matched_access_audit"}
           and type(scope["claim_matched_information"]) is bool,
           "Exact immutable comparison scope")
    C.need(scope["claim_matched_information"] == claim(runtime),
           "Frozen comparison claim cannot be promoted or changed")
    if scope["claim_matched_information"]:
        C.checked_pin(scope["matched_access_audit"])
    else:
        C.need(scope["matched_access_audit"] is None, "Ordinary scope cannot imply a matching audit")
    return scope


def selected(runtime):
    if not claim(runtime):
        return None
    C.need(runtime.get("matched_access_audit") is not None,
           "Trusted operator matched-access selection required for a matching claim")
    descriptor = runtime["matched_access_audit"]
    cached = runtime.get("_matched_access")
    if cached is None:
        cached = read_selected(descriptor)
        runtime["_matched_access"] = cached
    C.need(cached["descriptor"] == descriptor, "Selected audit cannot change during a campaign")
    return cached["audit"]


def comparison_scope(runtime):
    selected(runtime)
    return {"claim_matched_information": claim(runtime),
            "matched_access_audit": plain(runtime["matched_access_audit"]) if claim(runtime) else None}


def bind_prepared(runtime, prepared, definition, knowledge):
    check_claim(prepared["comparison_scope"], runtime)
    check_claim(definition["comparison_scope"], runtime)
    scope = comparison_scope(runtime)
    C.need(prepared["comparison_scope"] == definition["comparison_scope"] == scope,
           "Same immutable comparison scope in prepared programme and definition")
    value = selected(runtime)
    if value is None:
        return None
    C.need(prepared["matched_access_audit"] == runtime["matched_access_audit"]
           and definition["matched_access_audit"] == plain(runtime["matched_access_audit"]),
           "Candidate cannot replace the operator-selected audit")
    C.need(prepared["generation_provenance"] is not None, "Explicit programme creation evidence required")
    expected = {"image": definition["image"], "programme": plain(prepared["programme"]),
                "source": plain(prepared["source"]), "knowledge": plain(prepared["knowledge"]),
                "generation_provenance": plain(prepared["generation_provenance"])}
    C.need(all(value[key] == item for key, item in expected.items())
           and value["knowledge"] == C.pin(C.encode(C.checked_knowledge(knowledge))),
           "Exact reviewed image/programme/source/shared-policy/generation lineage")
    return value


def bind_exposure(runtime, request, exposure, boundary_audit):
    value = selected(runtime)
    if value is None:
        return None
    C.need(boundary_audit == runtime["matched_access_audit"]
           and exposure["boundary_audit"] == plain(boundary_audit)
           and request["image"] == exposure["image"] == value["image"]
           and exposure["approved_image_inventory_sha256"] == value["inventory"]["sha256"],
           "Exposure must use the selected image-content and supplied-prior audit")
    return value
