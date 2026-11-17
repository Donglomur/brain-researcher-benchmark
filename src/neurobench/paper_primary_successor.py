"""Authenticate the one reviewed SMC offline primary-policy successor.

This is metadata selection, not an executor or a scientific admission engine.
The caller authenticates raw JSON through ``read_pin(pin, label)`` and separately
retains the original registry/improvement lineage. No task source is imported.
Only the accepted SMC revision is supported; other revisions require review.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re


TASK = "PAPER-SMC-RNN-2024"
HOME = "benchmarks/paper/" + TASK
VERSION = "paper-primary-successor/v1"
REVISION = "smc-offline-nlb-temporal-scope/v1"
SOURCE_COMMIT = "6428832d5e4fb4f8b7cdbf3961710640bff0280e"
DESCRIPTOR = HOME + "/primary-successor.v1.json"
PROJECTION = HOME + "/docs/temporal-scope-projection.v1.json"
OBJECTIVE = "recreate_and_surpass_source_paper_same_task"
ROOT_DECISION = (2857, "d148a922505b20109b5d45389ac2acc4d748579283389c92bb85003655e234cc")
SHA = re.compile(r"[0-9a-f]{64}\Z")
_SEAL = object()

# Raw identities are independently accepted source bytes. Canonical identities
# also bind the parsed callback result, without requiring reserialization to
# reproduce whitespace. None of these pins is inferred from a working tree.
_APPROVED = {
    "previous_task": ("historical/task.pre-outcomes.v1.json", 6174,
        "5380450592ce4f379a0ecbd9d2da33d2ca8a3a5900a7b3ab5d5a8570ab015824",
        "6ef1ccf60a1d539fcb4e677d482f0f681605704528266af5e41a045bca35fa20"),
    "previous_improvement": ("improvement.v1.json", 11750,
        "e9f6630889c6be51513e917d4225d324d91e6a4de6582cc3860a8018bd4e5a2c",
        "ea412d2f6e36acaee00aa1096cda6c54eaa3fbc230d5f4e5fb71b6ddb752a390"),
    "previous_scientific": ("docs/scientific-contract.json", 3718,
        "a05e587878bab6846ba416cc36b3686613b5e5bfe0802d5fb02a42a47145f7bf",
        "3dca0cadc4e033a6f9c178eca06387abfc0174ef44d6489ff1c9d8af100a8a7f"),
    "primary_improvement": ("improvement.temporal-scope.v1.json", 15763,
        "5f9aac50d4550908d0cca1ccc704d08e1d423f337ed4cf66a65963617171894d",
        "9041947619e7c5d4e1b483914c2825ac6fcd170c39e0a81c2a64b5847a947c0b"),
    "primary_scientific": ("docs/scientific-contract.temporal-scope.v1.json", 7276,
        "235c980c7a8c6db2176cd9f860f44f6634936295625c0e4f4b26ddcf14f47617",
        "43d9828da52c39c2578adaa84bb9005ff9a42e008fbc08f6e4496c66c80972ad"),
    "reproduction": ("reproduction.v1.json", 29485,
        "d616c5c185d9affe390e9818a534d84071b4ae5f54e3cd407edcb777a1161856",
        "46b3a653dbc4ff4abeb1f75eebd5f37a647a7ac03845d61ee9d9a52e86ff7aec"),
    "projection": ("docs/temporal-scope-projection.v1.json", 5663,
        "8ee10e5586f2267f5ac43bef05a8ba7d271e03f19bf28ae670d2f1cde0ae133c",
        "b7a61e4c0ae076254b99fe56e8c493087c2e236f677e83827f8e046ac12245b3"),
}
FIELDS = frozenset(("/title", "/scientific_question", "/primary_outputs",
                    "/input_assets/observation_boundary", "/allowed_candidate_methods",
                    "/holds", "/next_implementation_action"))
# These are the only fields that the preceding shared dual-outcome projection
# may change. Scientific identity, materials, source pins and budgets are not in
# this set. The parent still proves that its generic projection is deterministic.
_GENERIC_FIELDS = frozenset(("objective", "goal", "status_basis", "primary_outputs",
                           "success_criteria", "evaluation", "next_implementation_action",
                           "holds", "admission"))


def _need(condition, message):
    if not condition:
        raise ValueError("SMC primary successor: " + message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _pin(name):
    path, size, digest, _ = _APPROVED[name]
    return {"path": HOME + "/" + path, "bytes": size, "sha256": digest}


def _require_pin(value, path):
    _need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "closed pin required")
    _need(value["path"] == path and type(value["bytes"]) is int
          and 0 < value["bytes"] <= 65536 and type(value["sha256"]) is str
          and SHA.fullmatch(value["sha256"]), "invalid or unbounded metadata pin")


def _source_pin(suffix, size, digest):
    return {"path": HOME + "/implementations/" + suffix, "bytes": size, "sha256": digest}


def candidate_interface():
    """Reviewed source selectors only; no export, execution or admission."""
    return {
        "role": "primary_offline_candidate",
        "prediction_interface": "one_complete_offline_prediction_set",
        "delivery": _source_pin("offline-nlb-outcomes-v1/delivery.py", 12197,
            "3164b4c40c26cf025e749c00f325aff890c22737df2466369f60720770370273"),
        "scorer": _source_pin("offline-nlb-outcomes-v1/scorer.py", 12664,
            "4b47c00312c8a58a3a08afd832a3e75f313ba717e0ffffad50a990496955083f"),
        "policy": _source_pin("offline-nlb-outcomes-v1/policy.py", 6723,
            "1fbcca835f8a9bb09599168c25a8e680f20a6b8d04eceee7093036ff0e0d7d79"),
        "scientific_outcome": "unknown",
        "selection_limit": "Source selectors do not authenticate an episode policy, source comparator, execution or scientific outcome.",
    }


def author_reproduction_routes():
    """Preserved author recipes; never the default primary candidate route."""
    return {
        "role": "author_source_reproduction_and_calibration",
        "recipes": ["causal-proposal", "noncausal-proposal"],
        "delivery": _source_pin("source-matched-nlb-v1/delivery.py", 23723,
            "bf63171f9737e6be6a0c6c7d575c727505f07208cfae6a460876746959a51cf8"),
        "scorer": _source_pin("source-matched-nlb-v1/scorer.py", 15050,
            "48638a595755138b32ff9c228804fd8c19c9ff874cd254f135fc5245ee9a25f8"),
        "protocol": _source_pin("source-matched-nlb-v1/protocol.json", 5849,
            "c8d437ece9c57b9066c5167ad499eada673d425ea17a06a9a20d62410ecbd644"),
        "scientific_outcome": "unknown",
        "selection_limit": "Author calibration is not a qualified submitted AI reproduction; source-matched receipts cannot be relabeled as offline candidate receipts.",
    }


def descriptor(root_decision_text):
    """Return the fixed descriptor; a caller may serialize it for review only."""
    _need(type(root_decision_text) is str and len(root_decision_text) <= ROOT_DECISION[0], "bounded root decision text required")
    raw = root_decision_text.encode("utf-8")
    _need((len(raw), hashlib.sha256(raw).hexdigest()) == ROOT_DECISION, "unreviewed root decision bytes")
    return {
        "schema_version": VERSION, "revision": REVISION, "task_id": TASK,
        "source_commit": SOURCE_COMMIT,
        "predecessor": {"task": _pin("previous_task"),
                        "improvement_contract": _pin("previous_improvement"),
                        "scientific_contract": _pin("previous_scientific")},
        "primary": {"improvement_contract": _pin("primary_improvement"),
                    "scientific_contract": _pin("primary_scientific"),
                    "reproduction_contract": _pin("reproduction")},
        "projection": _pin("projection"),
        "root_decision": {"bytes": len(raw), "sha256": ROOT_DECISION[1], "text": root_decision_text},
        "candidate_interface": candidate_interface(),
        "author_reproduction_routes": author_reproduction_routes(),
        "scientific_outcome": "unknown",
    }


class _Authenticated:
    __slots__ = ("_payload", "_seal")

    def __init__(self, payload, seal):
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_seal", seal)

    def __setattr__(self, name, value):
        raise AttributeError("Authenticated SMC metadata is immutable")

    def __delattr__(self, name):
        raise AttributeError("Authenticated SMC metadata is immutable")

    def _get(self, key):
        return json.loads(self._payload)[key]

    @property
    def primary_improvement(self):
        return self._get("documents")["primary_improvement"]

    @property
    def retained_improvement(self):
        return self._get("documents")["previous_improvement"]

    @property
    def descriptor_pin(self):
        return self._get("descriptor_pin")

    @property
    def candidate_interface(self):
        return self._get("descriptor")["candidate_interface"]

    @property
    def author_reproduction_routes(self):
        return self._get("descriptor")["author_reproduction_routes"]

    @property
    def members(self):
        """Additional metadata pins; reproduction/history are owned by caller."""
        return [self.descriptor_pin, _pin("projection"), _pin("primary_improvement"), _pin("primary_scientific")]


def authenticate(*, revision_pin, primary_pin, reproduction_pin, previous_pin,
                 retained_improvement_pin, read_pin):
    """Authenticate a fixed selector and every JSON input before projection.

    ``read_pin`` must verify the raw path/size/SHA, reject links and ambiguous JSON,
    and enforce the repository-wide read budget. Canonical checks below also
    prevent a callback from substituting another parsed document. Source-code
    selector files are verified by the existing whole-repository source gate,
    not imported or executed by this module.
    """
    _require_pin(revision_pin, DESCRIPTOR)
    for value, name in ((primary_pin, "primary_improvement"),
                        (reproduction_pin, "reproduction"), (previous_pin, "previous_task"),
                        (retained_improvement_pin, "previous_improvement")):
        _require_pin(value, _pin(name)["path"])
        _need(value == _pin(name), "selector does not bind accepted " + name)
    declaration = read_pin(copy.deepcopy(revision_pin), "SMC primary policy revision")
    _need(type(declaration) is dict and type(declaration.get("root_decision")) is dict,
          "revision descriptor required")
    expected = descriptor(declaration["root_decision"].get("text"))
    _need(declaration == expected and _canonical(declaration) == _canonical(expected),
          "revision descriptor differs from reviewed policy")
    documents = {}
    for name in _APPROVED:
        document = read_pin(_pin(name), "SMC successor " + name)
        _need(type(document) is dict and _digest(document) == _APPROVED[name][3],
              "parsed identity mismatch: " + name)
        documents[name] = document
    proposal = documents["projection"]
    _need(proposal.get("schema") == "smc-temporal-task-projection-proposal/v1"
          and proposal.get("task_id") == TASK
          and proposal.get("base_task_raw_sha256") == _pin("previous_task")["sha256"]
          and type(proposal.get("field_replacements")) is dict
          and set(proposal["field_replacements"]) == FIELDS, "unapproved projection fields")
    _need(documents["previous_task"].get("id") == TASK
          and documents["previous_task"].get("track") == "paper"
          and documents["primary_improvement"].get("task_id") == TASK
          and documents["reproduction"].get("task_id") == TASK, "task identity mismatch")
    return _Authenticated(_canonical({"descriptor": declaration, "documents": documents,
                                      "descriptor_pin": revision_pin}), _SEAL)


def project(base_dual_task, authenticated):
    """Apply this revision to the parent's deterministic generic dual projection.

    Build ``base_dual_task`` with the authenticated successor improvement, while
    preserving the previous row and definition for original-lineage validation.
    This function never mutates either argument and never computes a final task
    pin. The caller binds the final serialized task bytes atomically with outcomes.
    """
    _need(type(authenticated) is _Authenticated and authenticated._seal is _SEAL,
          "authenticated successor handle required")
    _need(type(base_dual_task) is dict, "dual projection must be an object")
    documents = authenticated._get("documents")
    previous = documents["previous_task"]
    for key in set(previous) | set(base_dual_task):
        if key not in _GENERIC_FIELDS:
            _need(key in previous and key in base_dual_task
                  and _canonical(base_dual_task[key]) == _canonical(previous[key]), "unrelated projection mutation: " + key)
    _need(base_dual_task.get("objective") == OBJECTIVE, "expected shared dual objective")
    _need(base_dual_task.get("goal") == "Recreate the original findings and separately exceed them on the same source-paper task: "
          + documents["primary_improvement"]["same_task"]["target"]["description"],
          "generic projection must use the selected primary improvement")
    admission = base_dual_task.get("admission")
    _need(type(admission) is dict
          and set(admission) == set(previous["admission"]) | {"delivery_unit", "reason"}
          and all(admission.get(key) is value for key, value in previous["admission"].items())
          and all(admission.get(key) is False for key in ("runnable", "research_qualified", "submission_ready"))
          and admission["delivery_unit"] == "one_registered_paper_task_two_independent_outcomes"
          and admission["reason"] == "Source definitions and binding metadata do not establish execution or either scientific outcome.",
          "admission must preserve every previous false flag")
    evaluation = base_dual_task.get("evaluation")
    expected_evaluation = {
        "objective": OBJECTIVE,
        "contracts": {"reproduction": "reproduction.v1.json", "improvement": "improvement.v1.json"},
        "paired_protocol": "outcomes.v1.json", "information_conditions": ["paper_data", "paper_data_author_code"],
        "outcome_roles": {"reproduction": "first_class_outcome", "improvement": "first_class_outcome"},
        "author_baseline_role": "calibration", "executor_ref": None, "scorer_ref": None,
        "binary_reward_registered": False,
    }
    _need(type(evaluation) is dict and _canonical(evaluation) == _canonical(expected_evaluation),
          "unexpected generic evaluation")
    criteria = base_dual_task.get("success_criteria")
    _need(criteria == [
        "Assess reproduction and improvement independently under reproduction.v1.json and improvement.v1.json; do not combine their scores.",
        "Preserve the original task, full panel, permitted observations, metrics, aggregation and required companion controls.",
        "Reproduction requires a source-grounded computation and independently verified granular outputs; copying published findings alone is insufficient.",
        "Improvement requires the unchanged improvement contract's same-task comparison, uncertainty and admission rules.",
        "Use outcomes.v1.json for the matched information conditions and budgets; a declared contract or admitted receipt is not scientific qualification.",
        "Author-baseline replay remains calibration. Historical reconstruction attempts retain their original scope and are not promoted to new qualified AI reproduction results.",
    ], "unexpected generic criteria")
    result = copy.deepcopy(base_dual_task)
    changes = documents["projection"]["field_replacements"]
    for pointer in FIELDS:
        if pointer == "/input_assets/observation_boundary":
            result["input_assets"]["observation_boundary"] = changes[pointer]
        else:
            result[pointer[1:]] = copy.deepcopy(changes[pointer])
    result["status_basis"] = "The retained status describes design eligibility. The explicit offline primary successor and reproduction each require independent qualification."
    result["success_criteria"][0] = "Assess reproduction and improvement independently under reproduction.v1.json and improvement.temporal-scope.v1.json; do not combine their scores."
    result["success_criteria"][3] = "Improvement requires the explicitly selected offline primary successor's same-task comparison, uncertainty and admission rules."
    result["evaluation"]["contracts"]["improvement"] = "improvement.temporal-scope.v1.json"
    result["evaluation"]["retained_improvement_contract"] = _pin("previous_improvement")
    result["evaluation"]["candidate_interface"] = authenticated.candidate_interface
    result["evaluation"]["author_reproduction_routes"] = authenticated.author_reproduction_routes
    result["provenance"]["retained_pre_outcomes_scientific_contract"] = copy.deepcopy(previous["provenance"]["scientific_contract"])
    result["provenance"]["scientific_contract"] = _pin("primary_scientific")
    result["provenance"]["primary_policy_revision"] = authenticated.descriptor_pin
    return result


# The continuous revision is a fixed SMC policy selection. It deliberately
# retains, and first authenticates, the complete temporal revision above.
CONTINUOUS_VERSION = "smc-continuous-current-binding/v1"
CONTINUOUS_DESCRIPTOR = HOME + "/continuous-outcomes-binding.v1.json"
CONTINUOUS_ARCHIVE = HOME + "/docs/pre-continuous-outcomes-v1/task.json"
CONTINUOUS_SOURCE = "cec4f1bb6646e88670864884d277fa36ddd94821"
CONTINUOUS_ROOT = (5065, "39d1f05ccbcfe49190676dcc2ba6b71ad6218059adc5762ea616df40dee214da")
CONTINUOUS_PACKAGE = HOME + "/implementations/continuous-outcomes-v1/"
_CONTINUOUS_APPROVED = {
    "retained_task": (CONTINUOUS_ARCHIVE, 12119,
        "b88feedacaa4cda6de9a1a3c012c29c5a6a1e48dff92b16e68d0fc1dc130020d",
        "ce8dbb0b80fa79a7b764c2e1974765da2ed6b2c38dbe9ac5ad7f461970e9a208"),
    "source_predecessor": (CONTINUOUS_PACKAGE + "predecessor.task.json", 12119,
        "b88feedacaa4cda6de9a1a3c012c29c5a6a1e48dff92b16e68d0fc1dc130020d",
        "ce8dbb0b80fa79a7b764c2e1974765da2ed6b2c38dbe9ac5ad7f461970e9a208"),
    "policy": (CONTINUOUS_PACKAGE + "policy.json", 6527,
        "1e04f61dedded47ed5de763bb328d2aa15dc2c26e3869b76f68d9af51fea61d0",
        "9608439822105acdcb3e4cc4867652340e1016f40c284ecf415c4d8bc6defc05"),
    "amendment": (CONTINUOUS_PACKAGE + "TASK_AMENDMENT.json", 10611,
        "3e6b72322ec1dbdb3dc01aae807a13619f640d02ada64f672d0b738d651b1b93",
        "f63642b8feca38c1c21ac066a3bb1e0a0503410766f96867074f152401aa3c1e"),
    "proposal": (CONTINUOUS_PACKAGE + "proposed-task.json", 15092,
        "b3306fc5757863b295fd70d3915daee9e5535e7aa6dd92ce2173d25aed91f6e3",
        "6a18cd365b66147dddcd5633cf2ea1339516966abcf16899e046a582463e5b6e"),
    "retained_outcomes": (HOME + "/outcomes.v1.json", 2016,
        "08c2f18db8639516c9cfa91c42956ad704e78a177d87ad687e6779691c7cb088",
        "a373873de3ee628bb8d104fa9db8a552fdff3aa2c09cee867f341c691affacd6"),
}
_CONTINUOUS_FIELDS = frozenset((
    "/admission", "/continuous_outcomes_v1", "/evaluation/candidate_interface",
    "/evaluation/continuous_assessment", "/evaluation/contracts", "/evaluation/operator_entrypoint",
    "/evaluation/paired_protocol", "/evaluation/retained_pre_continuous_contracts",
    "/evaluation/retained_pre_continuous_paired_protocol", "/evaluation/scorer_ref",
    "/holds", "/next_implementation_action", "/primary_outputs", "/provenance/continuous_policy",
    "/provenance/continuous_predecessor", "/resources/participant_access_budget",
    "/resources/participant_resource_budget", "/status_basis", "/success_criteria",
))


def continuous_pin(name):
    path, size, raw_hash, _ = _CONTINUOUS_APPROVED[name]
    return {"path": path, "bytes": size, "sha256": raw_hash}


def continuous_entrypoint():
    return {"path": CONTINUOUS_PACKAGE + "benchmark.py", "bytes": 37418,
            "sha256": "c671872e30cbb5c0723e29dda37d71c66e3175e84420a1cb9dcca813c3574488"}


def continuous_descriptor(root_decision_text):
    _need(type(root_decision_text) is str, "continuous root decision text required")
    raw = root_decision_text.encode("utf-8")
    _need((len(raw), hashlib.sha256(raw).hexdigest()) == CONTINUOUS_ROOT,
          "unreviewed continuous root decision")
    return {"schema_version": CONTINUOUS_VERSION, "task_id": TASK, "source_commit": CONTINUOUS_SOURCE,
            "root_decision": {"text": root_decision_text, "bytes": CONTINUOUS_ROOT[0], "sha256": CONTINUOUS_ROOT[1]},
            "inputs": {name: continuous_pin(name) for name in _CONTINUOUS_APPROVED},
            "retained_temporal_revision": {"path": DESCRIPTOR, "bytes": 6921,
                "sha256": "9b4b13fe3b5bdeee0ac7bcbba9cdd9936c0472e8410b4345108425be53fd80e2"},
            "entrypoint": continuous_entrypoint(), "paired_protocol": None,
            "result_status": "not_attempted", "legacy_binary_admission": "not_applicable"}


class _ContinuousAuthenticated:
    __slots__ = ("_payload", "_seal")

    def __init__(self, payload, seal):
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_seal", seal)

    def __setattr__(self, name, value):
        raise AttributeError("Authenticated SMC continuous metadata is immutable")

    def __delattr__(self, name):
        raise AttributeError("Authenticated SMC continuous metadata is immutable")

    def snapshot(self):
        return json.loads(self._payload)

    @property
    def members(self):
        # Component files already have their artifact owner; never enroll them a
        # second time as task metadata merely because this descriptor reads them.
        return [self.snapshot()["descriptor_pin"], continuous_pin("retained_task")]


def authenticate_continuous(*, revision_pin, temporal, temporal_task, read_pin):
    _need(type(temporal) is _Authenticated and temporal._seal is _SEAL,
          "authenticated retained temporal policy required")
    _require_pin(revision_pin, CONTINUOUS_DESCRIPTOR)
    declaration = read_pin(copy.deepcopy(revision_pin), "SMC continuous policy revision")
    _need(type(declaration) is dict and type(declaration.get("root_decision")) is dict,
          "continuous descriptor required")
    expected = continuous_descriptor(declaration["root_decision"].get("text"))
    _need(_canonical(declaration) == _canonical(expected), "unreviewed continuous descriptor")
    _need(temporal.descriptor_pin == expected["retained_temporal_revision"],
          "continuous selection must preserve exact temporal revision")
    documents = {}
    for name, approved in _CONTINUOUS_APPROVED.items():
        document = read_pin(continuous_pin(name), "SMC continuous " + name)
        _need(type(document) is dict and _digest(document) == approved[3],
              "continuous parsed identity mismatch: " + name)
        documents[name] = document
    _need(_digest(temporal_task) == _CONTINUOUS_APPROVED["retained_task"][3]
          and _canonical(temporal_task) == _canonical(documents["retained_task"])
          and _canonical(documents["source_predecessor"]) == _canonical(temporal_task),
          "continuous preimage must be the authenticated temporal projection")
    _need(documents["retained_outcomes"].get("original_task_sha256") == continuous_pin("retained_task")["sha256"],
          "retained outcomes must remain bound to the temporal task")
    _need(documents["policy"].get("schema") == "smc_continuous_measurement_policy_v1"
          and documents["policy"].get("task_id") == TASK
          and documents["policy"].get("root_adoption_sha256") == CONTINUOUS_ROOT[1],
          "continuous policy identity mismatch")
    return _ContinuousAuthenticated(_canonical({"documents": documents, "descriptor_pin": revision_pin,
                                                "descriptor": declaration}), _SEAL)


def project_continuous(temporal_task, authenticated):
    _need(type(authenticated) is _ContinuousAuthenticated and authenticated._seal is _SEAL,
          "authenticated continuous handle required")
    captured = authenticated.snapshot()
    documents = captured["documents"]
    _need(_canonical(temporal_task) == _canonical(documents["retained_task"]),
          "continuous projection cannot replace its retained task")
    amendment = documents["amendment"]
    _need(amendment.get("schema") == "smc_continuous_task_amendment_proposal_v1"
          and set(amendment.get("set_by_json_pointer", {})) == _CONTINUOUS_FIELDS,
          "unexpected continuous amendment fields")
    result = copy.deepcopy(temporal_task)
    for pointer, value in amendment["set_by_json_pointer"].items():
        keys = pointer[1:].split("/")
        target = result
        for key in keys[:-1]:
            _need(type(target.get(key)) is dict, "continuous projection parent is absent")
            target = target[key]
        target[keys[-1]] = copy.deepcopy(value)
    _need(_canonical(result) == _canonical(documents["proposal"]), "continuous projection differs from accepted proposal")
    # The accepted proposal has sorted JSON keys. Return that exact ordering so
    # the existing binder serializer reproduces b330, without reordering b88.
    raw = (json.dumps(result, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    proposal_pin = continuous_pin("proposal")
    _need(len(raw) == proposal_pin["bytes"] and hashlib.sha256(raw).hexdigest() == proposal_pin["sha256"],
          "continuous raw projection differs from accepted proposal")
    return json.loads(raw)


def continuous_public_selection(authenticated):
    _need(type(authenticated) is _ContinuousAuthenticated and authenticated._seal is _SEAL,
          "authenticated continuous handle required")
    captured = authenticated.snapshot()
    evaluation = captured["documents"]["proposal"]["evaluation"]
    return {"policy": continuous_pin("policy"), "entrypoint": continuous_entrypoint(),
            "revision": captured["descriptor_pin"], "paired_protocol": None, "result_status": "not_attempted",
            "outcomes": ["reproduction", "improvement"], "conditions": ["paper_data", "paper_data_author_code"],
            "continuous_assessment": copy.deepcopy(evaluation["continuous_assessment"]),
            "operator_entrypoint": copy.deepcopy(evaluation["operator_entrypoint"]),
            "candidate_interface": copy.deepcopy(evaluation["candidate_interface"]),
            "author_reproduction_routes": copy.deepcopy(evaluation["author_reproduction_routes"]),
            "retained_temporal": {"role": "retained_pre_continuous_policy_and_outcome_binding",
                "task": continuous_pin("retained_task"), "reproduction": _pin("reproduction"),
                "improvement": _pin("primary_improvement"), "outcomes": continuous_pin("retained_outcomes"),
                "revision": captured["descriptor"]["retained_temporal_revision"]},
            "construction_requires_AI_attempt": False, "legacy_binary_admission": "not_applicable"}
