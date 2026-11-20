"""Exact supported metadata adoption for PAPER-paper-method-002 only.

The maintained caller authenticates the historical context with its unchanged
validators before active_context replaces current policy fields. Three root
contracts, historical registry fields and scientific readiness remain intact.
No participant, scientific or provider code is imported or executed here.
"""
from __future__ import annotations

import copy
import hashlib
import json

TASK_ID = "PAPER-paper-method-002"
HOME = "benchmarks/paper/" + TASK_ID
POLICY_HOME = HOME + "/policies/retinal-paired-correction-v1"
COMPONENT_HOME = HOME + "/implementations/retinal-paired-episode-v1"
ADOPTION_PATH = POLICY_HOME + "/ADOPTION.v1.json"
SELECTION_FIELD = "retinal_paired_revision"
SCHEMA = "retinal-paired-supported-adoption/v1"

# Filled once from the selected, closed source postimages before publication.
DESCRIPTOR_PIN = {'path': 'benchmarks/paper/PAPER-paper-method-002/policies/retinal-paired-correction-v1/ADOPTION.v1.json', 'bytes': 46430, 'sha256': 'b79b0febe10ddbb94f7b913c0b0245f30f1e7e953c8ee7019e73b29b1ff8d2e7'}
RETAINED_TASK_PIN = {'path': 'benchmarks/paper/PAPER-paper-method-002/task.json', 'bytes': 35436, 'sha256': '0ca58963c4c07298bc258e3abb6a4a0dea1a2415204c681a78182dbad7978644'}
CURRENT_TASK_PIN = {'path': 'benchmarks/paper/PAPER-paper-method-002/task.json', 'bytes': 39816, 'sha256': 'a759c38019b7c9ae14317e928eb14f9e5e2b7bdef659ea4d640d0c914a48abb6'}
ORIGINAL_PINS = {'improvement': {'path': 'benchmarks/paper/PAPER-paper-method-002/improvement.v1.json', 'bytes': 13085, 'sha256': 'b7c83b20cca52ce0c282953357ea1a3f43592d33791fde4f23f9e8eaaa90e569'}, 'reproduction': {'path': 'benchmarks/paper/PAPER-paper-method-002/reproduction.v2.json', 'bytes': 39693, 'sha256': 'f8ea0d5d631cc9ba32b43a00728913f86bfeaf3bb0430ac663957991c6c723aa'}, 'outcomes': {'path': 'benchmarks/paper/PAPER-paper-method-002/outcomes.v1.json', 'bytes': 1830, 'sha256': '4ee9474081f8324fef74b3b4b61789814cc08ef94471b79ffcdfb543a70d9ee5'}}
ACTIVE_PINS = {'improvement': {'path': 'benchmarks/paper/PAPER-paper-method-002/policies/retinal-paired-correction-v1/improvement.v1.json', 'bytes': 16649, 'sha256': '9dfbd91bdc71e761d38694cca1abafdcfc763797941968181c45e4941f977360'}, 'reproduction': {'path': 'benchmarks/paper/PAPER-paper-method-002/policies/retinal-paired-correction-v1/reproduction.v2.json', 'bytes': 42286, 'sha256': 'e7af5016cb1e34f3bf8129ccabce84ab8dda4c1667ce611eec427ac556e71d37'}, 'outcomes': {'path': 'benchmarks/paper/PAPER-paper-method-002/policies/retinal-paired-correction-v1/outcomes.v1.json', 'bytes': 1905, 'sha256': '2d5fb9d333658449dd8397048fa87d330f91631d8687999b8dcf30fa22d94998'}}
COMPONENT_PINS = {'contract': {'path': 'benchmarks/paper/PAPER-paper-method-002/implementations/retinal-paired-episode-v1/CONTRACT.v1.json', 'bytes': 11818, 'sha256': '1e231c618bd54061a8539928e9560d480037d0edd926980b9627c88ade47b285'}, 'pairing_interface': {'path': 'benchmarks/paper/PAPER-paper-method-002/implementations/retinal-paired-episode-v1/PAIRING_INTERFACE.v1.json', 'bytes': 11101, 'sha256': '2a3c479157a698f64046192d664099432fb03187454b3de13da164023df396a1'}, 'assessment_interface': {'path': 'benchmarks/paper/PAPER-paper-method-002/implementations/retinal-paired-episode-v1/ASSESSMENT_INTERFACE.v1.json', 'bytes': 7906, 'sha256': 'f1f91d585982488e3d475105ca0aad36ec9316afde87567bdce3cbe97c00369a'}}
CANONICAL_DIGESTS = {'original_documents': {'improvement': '1a8fa193634547439ddea5220637ff34ab7faae1e19ffe9bc236bda973f796f2', 'reproduction': 'c5d290e712e5b085063ae3a13c1599def96dd4c44ebb0aedb97f0166206a8497', 'outcomes': '52817ae78d9fa2e6780a98f776b843c5b82baf8e4460fb666b27ead9ba58f3e2'}, 'active_documents': {'improvement': '278b0c152f4849d83e76a78dc9e5875f570f886667854674cd990c34b4a475e0', 'reproduction': '0b3200756a92c3c458551c7d1dc59691197007d6bd4aa957ef1d86a880a53c55', 'outcomes': '989b8c6be79b31859e243342ada56b1994d9e2cb22ed87483037108df2d59e19'}, 'component_documents': {'contract': '0864e7de7089812a9094b9b6f74abb35e8a6a70e1625537c39ce93a0156e7179', 'pairing_interface': '320c53c991d9255fe6013d8c5428d54e82b83c5e5db8ad27aa47e79f6c8ed8ba', 'assessment_interface': 'c0f4323a544424206a59b6235e521e15a7a2313ba5a821244265693ab38bb4e2'}}
DESCRIPTOR_CANONICAL_SHA256 = '710771456c95175b6e562a4b516ec6c44067964253b2842011d79bf9b1a71b8a'


def need(condition, message):
    if not condition:
        raise ValueError("Retinal paired adoption: " + message)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def _pin(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def _json(raw):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique,
                       parse_constant=lambda _: need(False, "nonfinite JSON"))
    need(type(value) is dict, "object metadata required")
    return value


_TOKEN = object()


class Handle:
    """Authenticated bytes are retained privately; properties return copies."""
    __slots__ = ("_snapshot",)

    def __init__(self, token, snapshot):
        need(token is _TOKEN, "handle must come from authenticate")
        object.__setattr__(self, "_snapshot", encode(snapshot))

    def __setattr__(self, name, value):
        raise AttributeError("immutable retinal adoption handle")

    def _value(self, name):
        return _json(self._snapshot)[name]

    @property
    def descriptor(self):
        return self._value("descriptor")

    @property
    def descriptor_pin(self):
        return copy.deepcopy(DESCRIPTOR_PIN)

    @property
    def retained_task(self):
        return _json(self.descriptor["retained_task_raw"])

    @property
    def retained_task_pin(self):
        return copy.deepcopy(RETAINED_TASK_PIN)

    @property
    def current_task_pin(self):
        return copy.deepcopy(CURRENT_TASK_PIN)

    @property
    def original_documents(self):
        return self._value("original_documents")

    @property
    def active_documents(self):
        return self._value("active_documents")

    @property
    def original_pins(self):
        return copy.deepcopy(ORIGINAL_PINS)

    @property
    def active_pins(self):
        return copy.deepcopy(ACTIVE_PINS)

    @property
    def component_pins(self):
        return copy.deepcopy(COMPONENT_PINS)

    @property
    def members(self):
        # Component metadata retains its distinct implementation ownership route.
        return frozenset([ADOPTION_PATH] + [x["path"] for x in ACTIVE_PINS.values()])


def authenticate(read_pin):
    """Use the maintained exact-raw-pin reader; never trust caller-supplied pins.

    read_pin(pin, label) is the existing maintained callback that authenticates
    raw bytes before returning decoded JSON. Independent canonical checks below
    also refuse altered decoded documents. Paths and raw pins are fixed here.
    """
    need(callable(read_pin) and DESCRIPTOR_PIN is not None, "closed source and maintained reader required")
    descriptor = read_pin(copy.deepcopy(DESCRIPTOR_PIN), "Retinal paired adoption descriptor")
    need(type(descriptor) is dict and _digest(descriptor) == DESCRIPTOR_CANONICAL_SHA256,
         "fixed descriptor content mismatch")
    expected_keys = {"schema_version", "task_id", "component_directory", "retained_task", "retained_task_raw",
                     "current_task", "historical_contracts", "active_contracts", "component_metadata",
                     "projection", "candidate_interface", "scientific_status", "preserved_registry_fields"}
    need(set(descriptor) == expected_keys and descriptor["schema_version"] == SCHEMA
         and descriptor["task_id"] == TASK_ID and descriptor["component_directory"] == COMPONENT_HOME,
         "exact descriptor task/component/schema required")
    need(descriptor["retained_task"] == RETAINED_TASK_PIN and descriptor["current_task"] == CURRENT_TASK_PIN
         and descriptor["historical_contracts"] == ORIGINAL_PINS and descriptor["active_contracts"] == ACTIVE_PINS
         and descriptor["component_metadata"] == COMPONENT_PINS and descriptor["scientific_status"] == "UNQUALIFIED",
         "descriptor predecessor/current/content bindings changed")
    need(type(descriptor["retained_task_raw"]) is str, "exact historical task UTF8 required")
    raw = descriptor["retained_task_raw"].encode("utf-8")
    need(_pin(HOME + "/task.json", raw) == RETAINED_TASK_PIN, "historical raw task snapshot changed")
    historical = _json(raw)
    need(historical.get("id") == TASK_ID and historical.get("track") == "paper",
         "historical task identity mismatch")
    documents = {}
    for category, pins in (("original_documents", ORIGINAL_PINS), ("active_documents", ACTIVE_PINS),
                           ("component_documents", COMPONENT_PINS)):
        documents[category] = {}
        for role, member in pins.items():
            document = read_pin(copy.deepcopy(member), "Retinal paired " + category + " " + role)
            need(type(document) is dict and _digest(document) == CANONICAL_DIGESTS[category][role],
                 "fixed " + category + " " + role + " content mismatch")
            documents[category][role] = document
    original, active = documents["original_documents"], documents["active_documents"]
    for collection in (original, active):
        need(all(value.get("task_id") == TASK_ID for value in collection.values()), "contract task identity mismatch")
    need(active["improvement"]["disposition"] == original["improvement"]["disposition"] == "design_ready"
         and active["reproduction"]["eligibility"] == original["reproduction"]["eligibility"] == "source_unresolved",
         "retinal correction cannot promote contract eligibility")
    for outcome in ("reproduction", "improvement"):
        pair = active["outcomes"]["pairing"][outcome]
        need(pair["status"] == "unresolved" and pair["protocol"] is None,
             "retinal correction cannot instantiate a scientific protocol")
    need(active["outcomes"]["original_task_sha256"] == CURRENT_TASK_PIN["sha256"],
         "active outcomes do not bind exact projected task bytes")
    handle = Handle(_TOKEN, {"descriptor": descriptor, **documents})
    need(_pin(HOME + "/task.json", encode(project(historical, handle))) == CURRENT_TASK_PIN,
         "descriptor/current task projection mismatch")
    return handle


def project(retained_task, handle):
    """Exact additive current view; every historical wrapped field is retained."""
    need(type(handle) is Handle and type(retained_task) is dict, "authenticated handle and historical task required")
    need(retained_task == handle.retained_task
         and _pin(HOME + "/task.json", encode(retained_task)) == RETAINED_TASK_PIN,
         "retained task differs from selected raw predecessor")
    projection = handle.descriptor["projection"]
    need(set(projection) == {"status_basis", "evaluation_contracts", "paired_protocol", "retinal_paired_correction"},
         "closed projection fields required")
    result = copy.deepcopy(retained_task)
    result["status_basis"] = projection["status_basis"]
    result["evaluation"]["contracts"] = copy.deepcopy(projection["evaluation_contracts"])
    result["evaluation"]["paired_protocol"] = projection["paired_protocol"]
    result["retinal_paired_correction"] = copy.deepcopy(projection["retinal_paired_correction"])
    need(result["retinal_paired_correction"]["descriptor"] == ADOPTION_PATH[len(HOME) + 1:]
         and result["retinal_paired_correction"]["scientific_status"] == "UNQUALIFIED",
         "path-only task-local descriptor required")
    for field in ("episode", "blocking_issues", "next_implementation_action", "holds", "admission", "resources"):
        need(result.get(field) == retained_task.get(field), "historical wrapped task field changed: " + field)
    return result


def active_context(base_context, current_document, handle, *, engine):
    """Reuse an already authenticated historical context and unchanged engines.

    The maintained caller restores the fixed historical row/task and invokes its
    normal context first. This function does not bypass or recreate that logic.
    """
    need(type(handle) is Handle and type(base_context) is dict and callable(engine),
         "authenticated handle, historical context and maintained engine required")
    active = handle.active_documents
    original = handle.original_documents
    need(base_context["previous_row"]["id"] == TASK_ID
         and base_context["improvement_contract"] == original["improvement"]
         and base_context["reproduction_contract"] == original["reproduction"]
         and base_context["outcomes"] == original["outcomes"], "historical normal context differs from fixed predecessors")
    need(base_context["retained_improvement_contract"] == original["improvement"]
         and base_context["retained_improvement_contract_pin"] == ORIGINAL_PINS["improvement"],
         "immutable retained improvement lineage changed")
    expected = project(handle.retained_task, handle)
    need(current_document == expected and _pin(HOME + "/task.json", encode(current_document)) == CURRENT_TASK_PIN,
         "current task does not match exact supported projection")
    reproduction, improvement, outcomes = (active[k] for k in ("reproduction", "improvement", "outcomes"))
    maintained = engine(reproduction)
    errors = maintained.outcomes_validate(outcomes, reproduction, improvement)
    need(not errors, "normal outcome validators refused corrected contracts: " + "; ".join(errors))
    need(outcomes["original_task_sha256"] == CURRENT_TASK_PIN["sha256"], "current outcome identity mismatch")
    summary = maintained.summary(outcomes, reproduction, improvement)
    need(not summary["errors"] and summary["task_count"] == 1, "normal outcome summary invalid")
    need(all(cell["scientific_outcome"] == "unknown" and cell.get("receipt") is None for cell in summary["cells"])
         and not any(summary["paired_metadata_admitted"].values()), "source correction cannot qualify a scientific outcome")
    result = copy.deepcopy(base_context)
    result.update(improvement_contract=improvement, improvement_contract_pin=copy.deepcopy(ACTIVE_PINS["improvement"]),
                  reproduction_contract=reproduction, outcomes=outcomes, summary=summary,
                  primary_policy_revision=copy.deepcopy(DESCRIPTOR_PIN),
                  primary_policy_provenance={"descriptor": copy.deepcopy(DESCRIPTOR_PIN),
                                             "historical_contracts": copy.deepcopy(ORIGINAL_PINS),
                                             "active_contracts": copy.deepcopy(ACTIVE_PINS),
                                             "current_task": copy.deepcopy(CURRENT_TASK_PIN),
                                             "component_metadata": copy.deepcopy(COMPONENT_PINS)},
                  candidate_interface=copy.deepcopy(handle.descriptor["candidate_interface"]))
    result["members"] = set(base_context["members"]) | set(handle.members)
    for field in ("previous_row", "previous_document", "previous_pin", "retained_improvement_contract",
                  "retained_improvement_contract_pin", "availability", "primary_scope_correction", "scope_decision_pin"):
        need(result[field] == base_context[field], "historical context field changed: " + field)
    return result
