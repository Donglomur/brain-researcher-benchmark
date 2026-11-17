"""Authenticate four reviewed primary-policy corrections without executing tasks.

Raw-file authentication and read budgets belong to the caller's ``read_pin``.
This module additionally binds exact accepted parsed identities and complete
policy deltas. It does not qualify a scientific outcome or create a runtime.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re


VERSION = "paper-scope-policy-successor/v1"
TASKS = frozenset(("PAPER-paper-signal-add-004", "PAPER-paper-method-replacement-008",
                   "PAPER-paper-method-replacement-013", "PAPER-paper-method-add-010"))
REVISION_FILE = "docs/provenance/improvement.primary-scope.revision.v1.json"
CURRENT_FILE = "improvement.primary-scope.v1.json"
SCOPE_PIN = {"path": "docs/provenance/paper-outcome-scope-decisions.v1.json",
             "bytes": 523120,
             "sha256": "ba085cfa4294baf51629867997da0c356d21466773884d0412654f2bc75924e2"}
SCOPE_CANONICAL = "2a2a021e74f9dac2eaddabb8ac46df9d1da5649f013d705e27b5573fd1e157b0"
SHA = re.compile(r"[0-9a-f]{64}\Z")
_SEAL = object()
_SECTIONS = ("objective", "goal", "primary_outputs", "success_criteria", "evaluation",
             "episode", "blocking_issues", "holds", "next_implementation_action")
_DOCUMENT_FILES = {"previous_task": "historical/task.pre-outcomes.v1.json",
                   "previous_improvement": "improvement.v1.json",
                   "primary_improvement": CURRENT_FILE, "reproduction": "reproduction.v2.json",
                   "descriptor": REVISION_FILE}
# Final accepted metadata identities only. No discovered or caller-generated pins.
# Each document tuple is (raw byte count, raw SHA256, canonical JSON SHA256).
_APPROVED = {
    "PAPER-paper-signal-add-004": {
        "previous_task": [
            19983,
            "31dae808a16d003f6ee63a3e9bffe040480235ed350b85697feb10956b594b60",
            "3121ea2efc5c44481d4aaf295f1c8abfea12ba5dc1f81127c881fe81559d0d46"
        ],
        "previous_improvement": [
            9707,
            "f2186a72b6c441393b8b6933482c458417c29306a56b50c75d4c4b082c41a317",
            "b31d97db947f199cf424e9c96a2f71cd843e0253e8e4d6b3dfdf4ce35de4c36e"
        ],
        "primary_improvement": [
            10681,
            "d07b3823b52e73ab97f182bda481d4c04a86e06fe34209418d00291eedad4b19",
            "82d47c44073f7914826287a5eb8e9569a83adc5c129f43a9d978b8c5b0ce1cdf"
        ],
        "reproduction": [
            194905,
            "e9945508d512bfc2c4689decd690aa051a5aa12ab01954a23e49751d8b9e924e",
            "12d7026420f220865d2409d51833314504930348336e68a02caa4450da33aed8"
        ],
        "descriptor": [
            8855,
            "2cc2da00586c604daf7f63018cffd6a5bb0b78f7a0ed7b4ea58a61f043864a17",
            "1258319133200d1bc302ee8b7345374a7e89e38ed74c7f4673f7ddd8d399c411"
        ],
        "delta_canonical": "33c5f1ab5639d8cd5570d51171d54824e7d3cb9f23be719439e429eed06f29ed",
        "base_projection_canonical": "0e1aadb044fbe43ba6d4807097e21d9653d7e5441f0f80fad69b78730a2f6eb6",
        "scope_entry_canonical": "edf8734752842596f185af4e56a0ac738c1219180351aa330900ce1ed5ffe5ae",
        "deltas": [
            "/same_task/dataset",
            "/same_task/cohort",
            "/same_task/inputs",
            "/blocking_issues/2",
            "/legacy/notes"
        ]
    },
    "PAPER-paper-method-replacement-008": {
        "previous_task": [
            47399,
            "470c0bb1f3af5a01187f5337d8b3bf22533cb50bf99c002d9c665dcdd16e3b1e",
            "9ba476d12dcb25a28ac020267cff3e1ba2830fad420229340a504bdac9268adc"
        ],
        "previous_improvement": [
            14555,
            "20f24f84a298fe8fbd7141dfafa59bc9213e6c6e642d52f65fa89388a001de10",
            "f49857ee16089d46d8b7e9373239d26bc7ac8a92c6045dcf606d8ed5c3b6160d"
        ],
        "primary_improvement": [
            18320,
            "bd0b8c8c17611f22bdaeb33bdad396814a8c8830b69ef6d3b5ff52824d8bc052",
            "078e2065643f427976f2cdfb5fb0d05731e7801f1f077538e7e21395f1d89b29"
        ],
        "reproduction": [
            136130,
            "b06495f254b2f71398aef55fed862853265a404865e8dbde5d756157b028fbb7",
            "13ce4183b90ecf304408a5936c41e190c8f4e9fa00aae84781c027f1fe08b45b"
        ],
        "descriptor": [
            28736,
            "94d2960efe9e84744f1c2be0124fdb220c28f2fab859ded71f837ca6f453ebd7",
            "212ce903b65f14cbc5e5a32ac1f1897ec0ba0421b6f64acf0c3e34ac38e9b38a"
        ],
        "delta_canonical": "ffd3e5986b0d9b8568d00637d5123b22fd1832c2f23b25ef9c137b9a16bd6d6e",
        "base_projection_canonical": "b9ccc707a4f894eee4513d2069c16c1df70742e14b23c0fc5d8fd58a3c176731",
        "scope_entry_canonical": "a4656a98e8ad7870eb763bc44b92f58aa8d6852e1a9766968238d948b3b10546",
        "deltas": [
            "/disposition_reason",
            "/comparison/primary_metric",
            "/comparison/published_baseline",
            "/comparison/reproduced_author_baseline",
            "/comparison/minimum_effect",
            "/comparison/uncertainty",
            "/comparison/paper_win_requires",
            "/blocking_issues",
            "/episode/improvement_loop",
            "/episode/candidate_freeze",
            "/episode/final_evaluation",
            "/episode/baseline_policy",
            "/same_task/target/description",
            "/same_task/inputs/description",
            "/same_task/metric/description",
            "/same_task/aggregation/description"
        ]
    },
    "PAPER-paper-method-add-010": {
        "previous_task": [
            75099,
            "22a5f813e025c553f27b91519909e4e5e206dcbd056d8dd683b74e943d72efdb",
            "0287ea445af6bc794a8b57364404c90b46f747b5a1b5a7b47eed3cb7b7214f3c"
        ],
        "previous_improvement": [
            10932,
            "78ec7acbf4614488af584c222b0d248061b8f538b630a209d919773b3deda51a",
            "9d76a55ed8eb0124aa5f49e296b4f01f064da3bbdef967a22778cf9d7dbf71db"
        ],
        "primary_improvement": [
            13974,
            "20107674f47771a035c274ad18301cde953cd5556ebd147154a3f474405c42fa",
            "dbb8a5fa7bcfaf8aa854db61328255fa62180b8b91e20b05a28960aec0314738"
        ],
        "reproduction": [
            41382,
            "5ff09b2c2f0c26ea2bd3a472eba972cf9bccf591c8510a4b174c31908f23e74f",
            "2d7d1228002042e38123ca8506bbc151d449891c2c10e4add975e7e7890fac43"
        ],
        "descriptor": [
            13631,
            "94af7e066027a1ead4159e5ae9b70f9ea65b8e5b1040cf90e1c69bc817dfb59e",
            "005071659330dea91926ef03edf2b483f6df75c093ffce5caf759f66ae01eab4"
        ],
        "delta_canonical": "571e01b2dc5021c6f50b52d2a5fb8ee00aab45cedd957402c18820a42905d783",
        "base_projection_canonical": "4c7faa2625654ef3b4dff3c1684ec026ca391011a0b7a9f44ad81232222c0427",
        "scope_entry_canonical": "0abdf8721587cc7633015145dabe676a651904b76faabca9f5d8ce7fc5d3d7ac",
        "deltas": [
            "/comparison/primary_metric",
            "/comparison/paper_win_requires/1",
            "/episode/final_evaluation",
            "/disposition_reason",
            "/comparison/reproduced_author_baseline/description",
            "/comparison/minimum_effect/rationale",
            "/comparison/uncertainty/method",
            "/blocking_issues/1",
            "/blocking_issues/3"
        ]
    },
    "PAPER-paper-method-replacement-013": {
        "previous_task": [
            33493,
            "3ac5ebe881993a87c6ece842ab33c9001f4789d6ec6c063a57533a8d801823c8",
            "dab9973ea729bc18a8aa93072e18cfac97a31aaeb7a02b9d8c2a3f0659caf786"
        ],
        "previous_improvement": [
            12075,
            "008007a42af5337c6fac86d6d8716540c4131c057727d8def353b30338c461ac",
            "6e76e3b0c3598a263b9aaea60ef1599bbc5495b90a350a4702ff62af73b12984"
        ],
        "primary_improvement": [
            13858,
            "fc890306343360f89b5b54ec9f6c33b83d6ef0986320db9d53c94ccf36e631e4",
            "51fddd268a06ccff1d47163f8bd42cd8c63093eebb77657f2c5c2cb5d9edd2ea"
        ],
        "reproduction": [
            39977,
            "c2aa4fa3d973f802d7f455cf3baca23f2e343c2ddcf1bc66e06d6f2d67503809",
            "ed82af23784efae7eb66f77282f589bbe70b85cec5620ddd6f5793f301074c5f"
        ],
        "descriptor": [
            12033,
            "7a4ce612bb415162738a909294fd704b8b47d30f5d2de4f07acc7849cd0fd7bd",
            "becf16c8554f19932a8f926b69ba46a9fb9ad143e79f6e8e7bd069de8a194b15"
        ],
        "delta_canonical": "83fb103283f54dfa058b8880015493680e21dbc9fd4fc977af258f7fd7dd1d6c",
        "base_projection_canonical": "72a8a3e68d5bc67d0b3342b887ceaf7f932c3ada3cc1e1e609566d83e332f0ee",
        "scope_entry_canonical": "269e3c270a503e4570b6eb619007eed2730b3f587b4ccd3434fee0c217dece73",
        "deltas": [
            "/same_task/dataset/description",
            "/same_task/cohort/description",
            "/same_task/inputs/description",
            "/same_task/metric/description",
            "/comparison/paper_win_requires/1",
            "/comparison/paper_win_requires/2",
            "/legacy/notes",
            "/comparison/minimum_effect/rationale"
        ]
    }
}


def _need(condition, message):
    if not condition:
        raise ValueError("Paper scope policy successor: " + message)


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _case(task_id):
    _need(type(task_id) is str and task_id in TASKS, "unsupported task")
    _need(task_id in _APPROVED, "complete policy acceptance is not frozen for this task")
    return _APPROVED[task_id]


def _pin(task_id, name):
    size, digest, _ = _case(task_id)[name]
    return {"path": "benchmarks/paper/" + task_id + "/" + _DOCUMENT_FILES[name],
            "bytes": size, "sha256": digest}


def _require_pin(value, expected):
    _need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "closed raw pin required")
    _need(type(value["path"]) is str and type(value["bytes"]) is int
          and 0 < value["bytes"] <= 1024 * 1024 and type(value["sha256"]) is str
          and SHA.fullmatch(value["sha256"]), "invalid bounded raw pin")
    _need(_canonical(value) == _canonical(expected), "unapproved metadata selector")


def approved_pins(task_id):
    """Return fresh fixed selectors for descriptor construction, never admission."""
    return {name: _pin(task_id, name) for name in _DOCUMENT_FILES}


def has_primary_successor(row):
    """Require both explicit selectors on each of the four adopted task rows.

    Call this only for the four supported IDs; other dispatch belongs to the
    shared binding layer. An unadopted source-only row remains unchanged.
    """
    _need(type(row) is dict and row.get("id") in TASKS, "unsupported registry row")
    declared = row.get("paper_outcomes")
    if declared is None:
        return False
    _need(type(declared) is dict, "outcomes binding must be an object")
    _need({"primary_policy_revision", "primary_improvement_contract", "reproduction_contract"}
          <= set(declared), "adopted task requires explicit current policy and reproduction selectors")
    for field, name in (("primary_policy_revision", "descriptor"),
                        ("primary_improvement_contract", "primary_improvement"),
                        ("reproduction_contract", "reproduction")):
        _require_pin(declared[field], _pin(row["id"], name))
    return True


def descriptor(task_id, reviewed_policy_delta):
    """Construct the single fixed descriptor from its accepted portable payload."""
    case = _case(task_id)
    _need(type(reviewed_policy_delta) is dict
          and _digest(reviewed_policy_delta) == case["delta_canonical"], "unreviewed policy delta")
    return {"schema_version": VERSION, "task_id": task_id,
            "predecessor": {"task": _pin(task_id, "previous_task"),
                            "improvement_contract": _pin(task_id, "previous_improvement")},
            "primary": {"improvement_contract": _pin(task_id, "primary_improvement"),
                        "reproduction_contract": _pin(task_id, "reproduction")},
            "scope_decision": {"artifact": copy.deepcopy(SCOPE_PIN),
                               "map": "same_primary_corrections", "task_entry_id": task_id},
            "reviewed_policy_delta": copy.deepcopy(reviewed_policy_delta)}


def _replacement_target(document, pointer):
    _need(type(pointer) is str and pointer.startswith("/") and "~" not in pointer,
          "unsupported replacement pointer")
    parts = pointer[1:].split("/")
    _need(all(parts), "empty replacement pointer segment")
    current = document
    for part in parts[:-1]:
        if type(current) is dict:
            _need(part in current, "missing replacement ancestor")
            current = current[part]
        else:
            _need(type(current) is list and part.isascii() and part.isdigit()
                  and str(int(part)) == part and int(part) < len(current), "invalid replacement ancestor")
            current = current[int(part)]
    part = parts[-1]
    if type(current) is dict:
        _need(part in current, "missing replacement target")
    else:
        _need(type(current) is list and part.isascii() and part.isdigit()
              and str(int(part)) == part and int(part) < len(current), "invalid replacement target")
        part = int(part)
    return current, part


def _verify_delta(previous, current, changes, accepted_pointers):
    _need(type(changes) is list and len(changes) == len(accepted_pointers), "incomplete policy delta")
    _need([item.get("json_pointer") if type(item) is dict else None for item in changes]
          == list(accepted_pointers), "unapproved policy replacement sequence")
    rebuilt = copy.deepcopy(previous)
    for change in changes:
        _need(set(change) == {"json_pointer", "predecessor_value", "successor_value",
                             "predecessor_value_canonical_sha256", "successor_value_canonical_sha256"},
              "unexpected policy replacement fields")
        target, key = _replacement_target(rebuilt, change["json_pointer"])
        before, after = change["predecessor_value"], change["successor_value"]
        _need(_canonical(target[key]) == _canonical(before), "stale replacement preimage")
        _need(_digest(before) == change["predecessor_value_canonical_sha256"]
              and _digest(after) == change["successor_value_canonical_sha256"], "replacement value identity mismatch")
        target[key] = copy.deepcopy(after)
    _need(_canonical(rebuilt) == _canonical(current), "unreviewed change outside complete policy delta")


class _Authenticated:
    __slots__ = ("_payload", "_seal")

    def __init__(self, payload, seal):
        object.__setattr__(self, "_payload", payload)
        object.__setattr__(self, "_seal", seal)

    def __setattr__(self, name, value):
        raise AttributeError("Authenticated scope-policy metadata is immutable")

    def __delattr__(self, name):
        raise AttributeError("Authenticated scope-policy metadata is immutable")

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
        return None

    @property
    def author_reproduction_routes(self):
        return None

    @property
    def members(self):
        task_id = self._get("task_id")
        return [self.descriptor_pin, _pin(task_id, "primary_improvement")]


def authenticate(*, task_id, revision_pin, primary_pin, reproduction_pin, previous_pin,
                 retained_improvement_pin, read_pin):
    """Authenticate the exact reviewed case and return an immutable metadata handle.

    The callback must authenticate raw paths/bytes/hashes and strict JSON under
    the caller's read budget. It receives fresh pin objects. Canonical checks
    additionally prevent parsed-document substitution. No callback result is kept
    mutable and no task source or scientific execution is invoked.
    """
    case = _case(task_id)
    for value, name in ((revision_pin, "descriptor"), (primary_pin, "primary_improvement"),
                        (reproduction_pin, "reproduction"), (previous_pin, "previous_task"),
                        (retained_improvement_pin, "previous_improvement")):
        _require_pin(value, _pin(task_id, name))
    documents = {}
    for name in _DOCUMENT_FILES:
        document = read_pin(_pin(task_id, name), "scope policy " + name)
        _need(type(document) is dict and _digest(document) == case[name][2],
              "parsed identity mismatch: " + name)
        documents[name] = copy.deepcopy(document)
    declaration = documents["descriptor"]
    expected = descriptor(task_id, declaration.get("reviewed_policy_delta"))
    _need(_canonical(declaration) == _canonical(expected), "unexpected revision descriptor")
    scope = read_pin(copy.deepcopy(SCOPE_PIN), "scope policy accepted source decision")
    _need(type(scope) is dict and _digest(scope) == SCOPE_CANONICAL, "unreviewed scope authority")
    correction = scope.get("same_primary_corrections", {}).get(task_id)
    _need(type(correction) is dict and _digest(correction) == case["scope_entry_canonical"],
          "scope entry identity mismatch")
    old, current, reproduction = (documents[name] for name in
                                 ("previous_improvement", "primary_improvement", "reproduction"))
    _need(all(doc.get("task_id") == task_id for doc in (old, current, reproduction))
          and documents["previous_task"].get("id") == task_id
          and documents["previous_task"].get("track") == "paper", "task identity mismatch")
    _need(current.get("schema_version") == "paper-improvement/v1"
          and reproduction.get("schema_version") == "paper-reproduction/v2"
          and current.get("disposition") in ("source_unresolved", "design_ready")
          and reproduction.get("eligibility") == "source_unresolved", "unexpected scientific disposition")
    _need(current["source_paper"]["url"] == reproduction["source_paper"]["url"], "paper identity mismatch")
    for anchor in ("dataset", "cohort", "target", "inputs", "split", "preprocessing", "metric", "aggregation"):
        _need(current["same_task"][anchor]["description"] == reproduction["same_task"][anchor]["description"],
              "current scientific anchor mismatch: " + anchor)
    _verify_delta(old, current, declaration["reviewed_policy_delta"]["field_replacements"], case["deltas"])
    return _Authenticated(_canonical({"task_id": task_id, "documents": documents,
                                      "scope_entry": correction, "descriptor_pin": revision_pin}), _SEAL)


def project(base_dual_task, authenticated):
    """Replace current instruction selectors, preserving the exact old policy text."""
    _need(type(authenticated) is _Authenticated and authenticated._seal is _SEAL,
          "authenticated successor handle required")
    task_id = authenticated._get("task_id")
    _need(type(base_dual_task) is dict
          and _digest(base_dual_task) == _case(task_id)["base_projection_canonical"],
          "unreviewed generic dual projection or unrelated field mutation")
    documents = authenticated._get("documents")
    previous, current = documents["previous_task"], documents["primary_improvement"]
    scope = authenticated._get("scope_entry")
    result = copy.deepcopy(base_dual_task)
    reproduction_file = _DOCUMENT_FILES["reproduction"]
    result["retained_pre_scope_policy"] = {
        "role": "immutable_predecessor_instructions_not_current_primary_policy",
        "task": _pin(task_id, "previous_task"),
        "improvement_contract": _pin(task_id, "previous_improvement"),
        "sections": {field: copy.deepcopy(previous[field]) for field in _SECTIONS},
        "interpretation": "These exact predecessor instructions and existing legacy records preserve prior scope; the explicit reviewed primary policy governs current improvement.",
    }
    result["status_basis"] = "The retained task status describes predecessor design eligibility. The explicitly selected primary policy and reproduction require independent qualification; neither scientific outcome is established."
    result["primary_outputs"][1] = "Improvement: candidate outputs and a comparison on the same selected original task under " + CURRENT_FILE + "."
    result["success_criteria"][0] = "Assess reproduction and improvement independently under " + reproduction_file + " and " + CURRENT_FILE + "; do not combine their scores."
    result["success_criteria"][3] = "Improvement requires the explicitly selected source-corrected primary policy's same-task comparison, meaningful-effect, uncertainty and admission rules."
    result["success_criteria"][-1] = "Apply the reviewed same-primary scope correction. A partial component or a prospective extension cannot alone establish the complete primary result; the explicitly selected primary improvement criteria apply."
    result["evaluation"]["contracts"]["improvement"] = CURRENT_FILE
    result["evaluation"]["retained_improvement_contract"] = _pin(task_id, "previous_improvement")
    result["evaluation"]["primary_policy_revision"] = authenticated.descriptor_pin
    result["evaluation"]["primary_improvement_contract"] = _pin(task_id, "primary_improvement")
    result["evaluation"]["disposition"] = current["disposition"]
    for field in ("episode", "blocking_issues"):
        result[field] = {"improvement": copy.deepcopy(current[field]),
                         "improvement_contract": CURRENT_FILE,
                         "reproduction_contract": reproduction_file, "paired_protocol": "outcomes.v1.json"}
    result["holds"] = {
        "current_improvement": copy.deepcopy(current["blocking_issues"]),
        "remaining_primary_source_limits": copy.deepcopy(scope["remaining_source_limits"]),
        "improvement_contract": CURRENT_FILE, "reproduction_contract": reproduction_file,
        "interpretation": "Current policy and reproduction source, comparison, uncertainty and execution gaps remain unresolved. Predecessor instruction text is preserved separately and does not override these selected contracts.",
    }
    result["next_implementation_action"] = {
        "improvement": "Resolve the source, comparison, uncertainty and episode gates declared in " + CURRENT_FILE + "; preserve its unresolved criteria and require independent evidence before admission.",
        "reproduction": "Resolve the task-specific source, full-panel and execution gaps declared in " + reproduction_file + ".",
        "paired_access": "Verify the matched information conditions and budgets declared in outcomes.v1.json.",
    }
    return result
