"""Operator-only joins for the paired SUNS2 extension; no payload IO or sandbox.

All pins/attestations must originate independently of the participant. Plans are
metadata snapshots, not proof of mounts, isolation, budgets or past exposure.
"""
import hashlib
import re
from .constants import ASSISTANCE_CONDITIONS, TASK_SLUG, VIDEO_IDS
from .fold_inputs import (
    _canonical, _json, _keys, _require, _sha, _relative,
    validate_material_manifest, validate_code_manifest, GROUND_TRUTH_COUNTS,
)

EXTENSION_ID = "suns2-paired-outcomes/v1"
_BINDING_KEYS = ("extension_id", "campaign_id", "common_protocol_digest",
                 "condition", "procedure_digest", "fold_index", "held_video",
                 "fresh_state_id")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
_NAMES = ("input_acceptance", "input_chain", "zip_stage", "hdf5_stage",
          "code_bank", "code_acceptance", "papers", "parity_closure", "parity_result")
_PAPERS = (("Main article", "main-paper.pdf"),
           ("Supplementary Information", "supplementary-information.pdf"),
           ("Reporting summary", "reporting-summary.pdf"))
_CUSTODY = ("procedure_frozen_before_folds", "fresh_context_files_caches",
            "no_crossfold_learned_state", "no_crossarm_feedback",
            "no_additional_private_GT_derived_shared_artifacts",
            "both_outcomes_follow_frozen_policy", "all36_freeze_before_feedback")


def validate_campaign_bindings(bindings):
    """Validate externally supplied custody identities, not actual isolation."""
    _require(type(bindings) is list and len(bindings) == 18, "18 bindings required")
    found, states, campaigns, common, procedures = {}, set(), set(), set(), {}
    for item in bindings:
        _keys(item, _BINDING_KEYS, "binding")
        _require(item["extension_id"] == EXTENSION_ID, "wrong extension")
        for key in ("campaign_id", "fresh_state_id"):
            _require(isinstance(item[key], str) and _ID.fullmatch(item[key]),
                     "invalid " + key)
        for key in ("procedure_digest", "common_protocol_digest"):
            _sha(item[key])
        arm, index = item["condition"], item["fold_index"]
        _require(arm in ASSISTANCE_CONDITIONS and type(index) is int
                 and 0 <= index < 9, "arm/fold")
        _require(item["held_video"] == VIDEO_IDS[index], "held video mismatch")
        _require((arm, index) not in found, "duplicate arm/fold")
        _require(item["fresh_state_id"] not in states, "state reused")
        _require(arm not in procedures or procedures[arm] == item["procedure_digest"],
                 "procedure changed across folds")
        procedures[arm] = item["procedure_digest"]
        campaigns.add(item["campaign_id"])
        common.add(item["common_protocol_digest"])
        states.add(item["fresh_state_id"])
        found[arm, index] = dict(item)
    _require(len(campaigns) == len(common) == 1, "campaign/common protocol differs")
    return [found[arm, i] for arm in ASSISTANCE_CONDITIONS for i in range(9)]


def _pinned(data, pin):
    _sha(pin)
    _require(type(data) is bytes and 0 < len(data) <= 65536, "metadata byte bound")
    _require(hashlib.sha256(data).hexdigest() == pin, "untrusted metadata digest")
    return _json(data)


def join_materials(metadata, trusted_sha256):
    """Join nine saved receipts in memory. Caller supplies trusted external pins.

    Returned private manifests bridge existing freeze_procedure/project_fold APIs.
    The operator must separately authorize and revalidate real-file projection.
    This function never opens materials or promotes a receipt to runtime proof.
    """
    _keys(metadata, _NAMES, "metadata")
    _keys(trusted_sha256, _NAMES, "trusted pins")
    d = {k: _pinned(metadata[k], trusted_sha256[k]) for k in _NAMES}
    try:
        a, chain = d["input_acceptance"], d["input_chain"]
        _require(a["schema"] == "suns2-original-nine-input-acceptance/v1"
                 and a["decision"] == "Accept authenticated current-v3 complete input bank and saved readability qualification; no method or benchmark-readiness claim"
                 and a["native_chain"]["sha256"] == trusted_sha256["input_chain"],
                 "input acceptance join")
        for name, stage in (("zip_stage", "zip"), ("hdf5_stage", "hdf5")):
            _require(chain["stage_and_process_pins"][stage]["stage"]["sha256"]
                     == trusted_sha256[name], "input stage pin join")
        z, h = d["zip_stage"]["result"], d["hdf5_stage"]["result"]
        _require(z["status"] == "complete_original_input_ZIP_authenticated"
                 and h["status"] == "complete_schema_and_readability"
                 and h["video_order"] == list(VIDEO_IDS), "unqualified input stage")
        rows = z["members"]
        _require(len(rows) == 19 and len({r["name"] for r in rows}) == 19,
                 "original19 members required")
        members = {r["name"]: r for r in rows}
        expected = {"1P_spike_tempolate.h5"}
        expected.update(v + ".h5" for v in VIDEO_IDS)
        expected.update("GT Masks/FinalMasks_" + v + ".mat" for v in VIDEO_IDS)
        _require(set(members) == expected, "input members differ")
        _require(all(r["source_object_id"] == 49636131 for r in rows),
                 "source object differs")
        video_rows = [r for r in h["files"] if r["role"] == "video"]
        _require(len(video_rows) == 9, "exactly nine video readability rows")
        readable = {r["name"]: r for r in video_rows}
        _require(set(readable) == {v + ".h5" for v in VIDEO_IDS},
                 "full video readability missing")
        videos, masks = [], []
        for v in VIDEO_IDS:
            for role, name, shape, target in (
                ("video", v + ".h5", [6000, 50, 50], videos),
                ("manual_mask", "GT Masks/FinalMasks_" + v + ".mat",
                 [50, 50, GROUND_TRUTH_COUNTS[v]], masks)):
                r = members[name]
                if role == "video":
                    q = readable[name]
                    _require(q["sha256"] == r["sha256"] and q["bytes"] == r["bytes"]
                             and q["schema"]["shape"] == shape
                             and q["schema"]["selected_name"] == "mov"
                             and q["schema"]["dtype"]["description"] == "uint16"
                             and q["readability"]["elements_read"] == 15000000,
                             "video schema/readability join")
                target.append(dict(video_id=v, role=role, path=name,
                                   source_member=name, bytes=r["bytes"],
                                   sha256=r["sha256"], shape=shape))
        material = validate_material_manifest(dict(
            schema="suns2-authenticated-materials/v1", task=TASK_SLUG,
            status="authenticated_original_inputs",
            authentication_receipt_sha256=trusted_sha256["input_acceptance"],
            source=dict(object_id=49636131, version=3, archive_bytes=248562067,
                        archive_sha256=z["archive_sha256"], archive_md5=z["archive_md5"]),
            videos=videos, manual_masks=masks,
            common_support={"temporal_template": "quarantined_pending_provenance"}))
        bank, review = d["code_bank"], d["code_acceptance"]
        _require(bank["schema"] == "suns2-private-code-bank/v3"
                 and review["schema"] == "suns2-semantic-role-acceptance/v1"
                 and review["decision"] == "Accept as method-source artifacts; no embedded answer/weight payloads observed. Public result constants/links disclosed."
                 and review["bank_manifest_sha256"] == trusted_sha256["code_bank"]
                 and bank["release"] == "v1.2.0"
                 and len(bank["files_completed"]) == review["files"] == 89
                 and sum(r["bytes"] for r in bank["files_completed"]) == review["bytes"] == 721097,
                 "official code acceptance join")
        code = validate_code_manifest(dict(
            schema="suns2-official-code-allowlist/v1", task=TASK_SLUG,
            release=bank["release"], commit=bank["commit"],
            source_role="reviewed_official_code_without_answers_or_weights",
            files=bank["files_completed"]))
        p = d["papers"]
        _require(p["schema"] == "suns2-protected-paper-originals/v1"
                 and p["status"] == "three_original_PDF_bodies_authenticated"
                 and len(p["originals"]) == 3, "three authenticated papers required")
        papers = []
        for r, (role, name) in zip(p["originals"], _PAPERS):
            q = r["original"]
            _require(r["role"] == role and q["path"].endswith("/" + name)
                     and type(q["bytes"]) is int and q["bytes"] > 0, "paper role")
            _sha(q["sha256"])
            papers.append(dict(role=role, path="papers/" + name,
                               bytes=q["bytes"], sha256=q["sha256"]))
        _require(sum(r["bytes"] for r in papers) == 9686313, "paper support differs")
        parity = d["parity_closure"]
        f = parity["facts"]
        _require(parity["status"] == "selected_19_file_snapshot_parity_verified"
                 and (f["matching_movies"], f["matching_manual_masks"],
                      f["matching_quarantined_template"], f["different_members"])
                 == (9, 9, 1, 0), "selected snapshot parity absent")
        comparison = d["parity_result"]
        _require(parity["result"]["sha256"] == trusted_sha256["parity_result"]
                 and comparison["schema"] == "suns2-v2-v3-hash-only-comparison/v1"
                 and comparison["status"] == "complete_equal"
                 and comparison["v3_reference_receipt_sha256"] == trusted_sha256["zip_stage"]
                 and comparison["all_19_equal"] is True
                 and comparison["template_quarantined"] is True, "parity receipt join")
        compared = comparison["members"]
        _require(len(compared) == 19 and {r["name"] for r in compared} == expected,
                 "exact19 parity support")
        for r in compared:
            q = members[r["name"]]
            role = ("quarantined_template" if r["name"] == "1P_spike_tempolate.h5"
                    else "ground_truth" if r["name"].startswith("GT Masks/") else "movie")
            _require(r["role"] == role and r["bytes"] == q["bytes"]
                     and r["sha256"] == r["v3_sha256"] == q["sha256"]
                     and r["expanded_sha256_equal"] is True, "parity member join")
        bundle = dict(material=material, code=code, papers=papers,
                      trusted_receipt_pins=dict(trusted_sha256))
        bundle["join_digest"] = hashlib.sha256(_canonical(bundle)).hexdigest()
        return bundle
    except (KeyError, TypeError, IndexError, AttributeError) as exc:
        raise ValueError("malformed retained metadata") from exc


def plan_fold(bundle, bindings, condition, fold_index,
              attestation_bytes, trusted_attestation_sha256, *, common_protocol_bytes):
    """Return private allowlists only; attestation does not create a sandbox.

    Runner must use fresh isolated state and read-only exact file binds, verify
    files against frozen manifests, and prevent all fold/cross-arm carryover.
    Public paper results/code constants remain declared exposure exceptions.
    Procedure digests externally commit both policies for this arm/trial; their
    contents and pre-fold timing are not parsed/proved here. The all36 flag is a
    future policy obligation; the submission adapter supplies the later gate.
    """
    canonical = validate_campaign_bindings(bindings)
    _require(condition in ASSISTANCE_CONDITIONS and type(fold_index) is int
             and 0 <= fold_index < 9, "arm/fold")
    binding = next(x for x in canonical if x["condition"] == condition
                   and x["fold_index"] == fold_index)
    body = {k: v for k, v in bundle.items() if k != "join_digest"}
    _require(hashlib.sha256(_canonical(body)).hexdigest() == bundle["join_digest"],
             "joined materials changed")
    protocol = _pinned(common_protocol_bytes, binding["common_protocol_digest"])
    _keys(protocol, ("schema", "join_digest", "questions_digest", "budget_digest",
                     "feedback_policy", "validation_policy"), "common protocol")
    _require(protocol["schema"] == "suns2-paired-common-protocol/v1"
             and protocol["join_digest"] == bundle["join_digest"]
             and protocol["feedback_policy"] == "all36_before_protected_feedback"
             and protocol["validation_policy"] == "active_training8_only",
             "common material/policy join")
    _sha(protocol["questions_digest"])
    _sha(protocol["budget_digest"])
    a = _pinned(attestation_bytes, trusted_attestation_sha256)
    _keys(a, ("binding", "join_digest", "template_policy") + _CUSTODY, "attestation")
    _require(a["binding"] == binding and a["join_digest"] == bundle["join_digest"],
             "custody binding mismatch")
    _require(all(a[k] is True for k in _CUSTODY), "fresh-state custody unqualified")
    _require(a["template_policy"] in ("template_free", "active_training8_only"),
             "historical/global template excluded")
    m = validate_material_manifest(bundle["material"])
    code = validate_code_manifest(bundle["code"])
    files = list(m["videos"]) + [
        r for r in m["manual_masks"] if r["video_id"] != binding["held_video"]]
    # Copy through canonical JSON: caller mutation cannot add hidden entries later.
    return _json(_canonical(dict(
        schema="suns2-paired-fold-handoff/v1", operator_only=True,
        binding=binding, join_digest=bundle["join_digest"],
        attestation_sha256=trusted_attestation_sha256, template_policy=a["template_policy"],
        data_files=files, papers=bundle["papers"],
        code_files=code["files"] if condition == "paper_data_official_code" else [],
        outcomes=["recreation", "improvement"], mounts_released=False,
        runtime_isolation_verified=False, payload_bytes_read=0,
        public_exposure="Published paper answers and reviewed code constants/links are disclosed.",
        ane_training_label_rules={"paper_default": "Hungarian IoU>=0.5",
                 "named_released": "independent_any IoU>0.3"},
        coordinates="movie[time,row,col] corresponds Masks[col,row,neuron]")))

