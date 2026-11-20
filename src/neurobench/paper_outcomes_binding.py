"""Authenticate one paper task's two declared outcomes without running science.

The registry owns exact current and predecessor bytes.  The original improvement
lineage remains unchanged; the immediately previous current definition is a
separate, immutable predecessor.  The current projection refers to outcome files
by name, so the descriptor may bind its raw task digest without a hash cycle.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import types


VERSION = "paper-outcomes-binding/v1"
OBJECTIVE = "recreate_and_surpass_source_paper_same_task"
HISTORY = "historical/task.pre-outcomes.v1.json"
SNAPSHOT = "docs/provenance/registrations/paper-pre-outcomes-v1.json"
REPRODUCTION = "reproduction.v1.json"
REPRODUCTION_FILES = {"paper-reproduction/v1": REPRODUCTION,
                      "paper-reproduction/v2": "reproduction.v2.json"}
OUTCOMES = "outcomes.v1.json"
RETINAL_PAIRED_TASK = "PAPER-paper-method-002"
RETINAL_PAIRED_FIELD = "retinal_paired_revision"
REGISTRY = "benchmarks/registry.json"
PRIMARY_SUCCESSOR_TASK = "PAPER-SMC-RNN-2024"
SCOPE_POLICY_SUCCESSOR_TASKS = frozenset((
    "PAPER-paper-signal-add-004", "PAPER-paper-method-replacement-008",
    "PAPER-paper-method-replacement-013", "PAPER-paper-method-add-010",
))
REFERENCE_SUCCESSOR_TASKS = frozenset(("PAPER-ROOT-ADD-001", "PAPER-paper-method-029"))
PRIMARY_SUCCESSOR_FIELDS = frozenset(("primary_policy_revision", "primary_improvement_contract"))
MEG_GENERIC_TASK = "PAPER-paper-method-add-010"
MEG_GENERIC_FIELD = "generic_classification_mode"
MEG_GENERIC_MODE_PIN = {
    "path": "benchmarks/paper/PAPER-paper-method-add-010/implementations/paired-program-v1/GENERIC_CLASSIFICATION_MODE.json",
    "bytes": 8877,
    "sha256": "245ed9305cea36d2b1a37268f2bea393c75617dfa2115b2abac2f6ef12634b9f"
}
MEG_GENERIC_BASE_TASK = {
    "path": "benchmarks/paper/PAPER-paper-method-add-010/task.json",
    "bytes": 92570,
    "sha256": "fe1f8de046c5a2ca6aa496ffe665959cba32282a39c349d4f0d20702ad4b953a"
}
MEG_GENERIC_BASE_OUTCOMES = {
    "path": "benchmarks/paper/PAPER-paper-method-add-010/outcomes.v1.json",
    "bytes": 4824,
    "sha256": "67558ec8f67e2269068d703d1b61abd8805f3566675918693b621c0bdf00bb3e"
}
MEG_GENERIC_PUBLIC_TEXT = {
    "description": "An explicitly separate fixed-Generic-feature classification mode uses 188 selected released post-QC scalars from 94 participants and the accepted author-method reference on identical frozen participant folds. It assesses classifier-summary published-precision numerical reproduction and strict exact same-case reference-score exceedance. These scoped outcomes do not populate raw-feature, paired-distribution, AUC, whole-paper or scientific-superiority claims.",
    "pairing_description": "The generic_feature_classification_v1 descriptor defines a narrower executable classifier mode shared by paper+data and paper+data+official-code conditions. Their scientific inputs, frozen cases/folds, primary metric and budgets are matched; only the declared code access differs. Both programmes freeze before fold labels are exposed, and no writable state or feedback crosses the twenty executions. Its published-precision and positive-score flags remain distinct from the broader contracts and from established statistical superiority.",
    "reproduction_description": "The accepted author-method calibration reproduces 64.3% mean accuracy and 9.4pp population fold SD at the paper precision. Candidate published-precision compatibility is computed from exact fold counts and the explicit half-open criterion, with granular discrepancies retained; it is not full-feature or distribution reproduction.",
    "improvement_description": "reference_score_exceeded means a strictly positive exact rational mean-fold accuracy difference from the frozen reference on identical selected cases. Scientific superiority remains unevaluated without a separately selected inferential study; no arbitrary new effect margin or significance threshold is introduced.",
    "catalog_scope_note": "Explicit 188-scalar fixed-Generic classification mode with accepted author-method calibration, exact numerical reproduction/score-exceedance outcomes, and portable 25-method controls. Existing raw-window mode and full-feature/distribution/AUC/whole-paper limitations remain. No AI result, native qualification, SOTA or benchmark-count increase."
}
SOURCE_DECLARATION_GAP_IDS = frozenset(("PAPER-paper-method-011", "PAPER-paper-method-replacement-009"))
SOURCE_DECLARATION_GAP_PATH = "docs/provenance/paper-outcome-source-declaration-gaps.v1.json"
# Initial adoption trusts this independently reviewed record, never a self-pin
# derived from whichever valid-shaped document happens to occupy the path.
SOURCE_DECLARATION_GAP_PIN = {
    "path": SOURCE_DECLARATION_GAP_PATH, "bytes": 27831,
    "sha256": "5e990248b79841bba0d5aa6099c71d357d29e6ba61f70c75a0f2cf63acbdc53a",
}
CONDITIONS = ("paper_data", "paper_data_author_code")
SCOPE_PATH = "docs/provenance/paper-outcome-scope-decisions.v1.json"
SCOPE_VERSION = "paper-outcome-scope-decisions/v1"
UNAVAILABLE = "paper-outcomes-unavailable/v1"
UNAVAILABLE_REASONS = {
    "unavailable_primary_secondary_scope_mismatch": "primary_secondary_scope_mismatch",
    "unavailable_complete_primary_pairing": "full_primary_pairing_unavailable",
}
NORMAL_SCOPE_DISPOSITIONS = frozenset(("same_primary_unqualified", "explicit_primary_selection"))
SCOPE_IDS = frozenset(("PAPER-EXP-20261113-005", "PAPER-FIND-REP-007", "PAPER-FIND-013", "PAPER-CANDIDATE-20261114-PLEXUS"))
SCOPE_ID = re.compile(r"(?:PAPER-[A-Za-z0-9_-]{1,121}|paper-pcca-fa-bilateral-pfc-arousal-2026)\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")
PRESERVED_ROW_FIELDS = (
    "id", "title", "track", "task_directory", "specification_id", "specification_alias",
    "registration_class", "registration_stage", "registry", "track_source",
    "original_specification", "specification_revision", "paper_improvement",
    "scientific_readiness", "submission_readiness", "declared_specification_status",
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def pin(path, raw):
    return {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require_pin(value, path, label):
    need(type(value) is dict and set(value) == {"path", "bytes", "sha256"}, "Closed " + label + " pin required")
    need(value["path"] == path and type(value["bytes"]) is int and value["bytes"] >= 0
         and type(value["sha256"]) is str and SHA.fullmatch(value["sha256"]), "Invalid " + label + " pin")


def engine(reproduction=None):
    """Load only the two fixed, reviewed framework siblings, including under -I.

    Catalog and source checkers are also loaded as standalone files.  A private
    package permits the reproduction engine's relative import without modifying
    sys.path or importing a task implementation.  Executing source directly avoids
    bytecode writes during metadata-only checks.
    """
    version = "paper-reproduction/v1" if reproduction is None else reproduction.get("schema_version") if type(reproduction) is dict else None
    need(version in ("paper-reproduction/v1", "paper-reproduction/v2"), "Unsupported reproduction contract version")
    target = "paper_reproduction" if version == "paper-reproduction/v1" else "paper_reproduction_v2"
    directory = Path(__file__).resolve().parent
    suffix = hashlib.sha256(str(directory).encode()).hexdigest()[:16]
    package_name = "_neurobench_outcomes_" + suffix
    result_name = package_name + "." + target
    if result_name in sys.modules:
        return sys.modules[result_name]
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        package.__package__ = package_name
        package.__path__ = [str(directory)]
        sys.modules[package_name] = package
    created = []
    try:
        for name in ("paper_improvement", "paper_reproduction") + ((target,) if target != "paper_reproduction" else ()):
            if package_name + "." + name in sys.modules:
                continue
            path = directory / (name + ".py")
            need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024,
                 "Expected bounded framework source: " + name)
            spec = importlib.util.spec_from_file_location(package_name + "." + name, path)
            need(spec is not None, "Cannot load paper framework source")
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            created.append(spec.name)
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            setattr(package, name, module)
    except BaseException:
        for name in created:
            sys.modules.pop(name, None)
        raise
    return sys.modules[result_name]


def primary_successor_module(task_id=PRIMARY_SUCCESSOR_TASK):
    """Load only the fixed reviewed metadata selector for the declared task."""
    if task_id == PRIMARY_SUCCESSOR_TASK:
        filename = "paper_primary_successor.py"
    elif task_id == "PAPER-ROOT-ADD-001":
        filename = "paper_language_reference.py"
    elif task_id == "PAPER-paper-method-029":
        filename = "paper_deeprecon_figure2.py"
    elif task_id in SCOPE_POLICY_SUCCESSOR_TASKS:
        filename = "paper_scope_policy_successor.py"
    else:
        raise ValueError("Unsupported primary successor task")
    path = Path(__file__).resolve().with_name(filename)
    name = "_neurobench_primary_successor_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    if name not in sys.modules:
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024,
             "Expected bounded primary successor framework source")
        spec = importlib.util.spec_from_file_location(name, path)
        need(spec is not None, "Cannot load primary successor framework source")
        module = importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        sys.modules[name] = module
    return sys.modules[name]


def endpoint_selection_module():
    """Load only the fixed reviewed metadata-only endpoint selection sibling."""
    path = Path(__file__).resolve().with_name("paper_endpoint_selection.py")
    name = "_neurobench_endpoint_selection_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    if name not in sys.modules:
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024,
             "Expected bounded endpoint selection framework source")
        spec = importlib.util.spec_from_file_location(name, path)
        need(spec is not None, "Cannot load endpoint selection framework source")
        module = importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        sys.modules[name] = module
    return sys.modules[name]


def has_endpoint_selection(row):
    return endpoint_selection_module().has_endpoint_selection(row)


def endpoint_selection_ids(previous_rows):
    return endpoint_selection_module().selection_ids(getattr(previous_rows, "endpoint_selections", None))


def has_primary_successor(row):
    """Check selector shape only; full context must authenticate its content.

    The adopted SMC and four reviewed scope-policy tasks require explicit policy
    selectors. Source-only original rows remain unchanged. Other tasks reject
    these selectors, and a partial pair never falls back to retained policy.
    """
    declared = row.get("paper_outcomes")
    if declared is None:
        return False
    need(type(declared) is dict, "Paper outcome binding must be an object")
    if row.get("id") in SCOPE_POLICY_SUCCESSOR_TASKS | REFERENCE_SUCCESSOR_TASKS:
        return primary_successor_module(row["id"]).has_primary_successor(row)
    selected = PRIMARY_SUCCESSOR_FIELDS & set(declared)
    if row.get("id") != PRIMARY_SUCCESSOR_TASK:
        need(not selected, "Primary successor selectors are restricted to reviewed tasks")
        return False
    need(selected == PRIMARY_SUCCESSOR_FIELDS and "reproduction_contract" in declared,
         "Adopted SMC outcomes require both explicit primary successor selectors and reproduction")
    home = "benchmarks/paper/" + PRIMARY_SUCCESSOR_TASK
    for field, filename in (("primary_policy_revision", "primary-successor.v1.json"),
                            ("primary_improvement_contract", "improvement.temporal-scope.v1.json")):
        require_pin(declared[field], home + "/" + filename, "SMC " + field)
        need(0 < declared[field]["bytes"] <= 65536, "SMC successor metadata must be bounded")
    return True


def has_continuous_outcomes(row):
    """Recognize only the fixed SMC current selector; context proves its bytes."""
    declared = row.get("paper_outcomes")
    if not isinstance(declared, dict) or "continuous_policy_revision" not in declared:
        return False
    need(row.get("id") == PRIMARY_SUCCESSOR_TASK and row.get("track") == "paper",
         "Continuous outcome selection is restricted to the reviewed SMC task")
    need(has_primary_successor(row), "Continuous SMC must retain its temporal predecessor selectors")
    module = primary_successor_module()
    selected = declared["continuous_policy_revision"]
    need(type(selected) is dict and selected.get("path") in (module.CONTINUOUS_DESCRIPTOR, module.OFFICIAL_ASSETS_DESCRIPTOR),
         "SMC continuous revision requires an explicitly reviewed versioned path")
    require_pin(selected, selected["path"], "SMC continuous policy revision")
    need(0 < declared["continuous_policy_revision"]["bytes"] <= 65536,
         "SMC continuous revision must be bounded")
    return True


def declaration_gap_module():
    """Load only the fixed reviewed metadata authenticator, never task code."""
    path = Path(__file__).resolve().with_name("paper_declaration_gaps.py")
    name = "_neurobench_declaration_gaps_" + hashlib.sha256(str(path).encode()).hexdigest()[:16]
    if name not in sys.modules:
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 1024 * 1024,
             "Expected bounded source declaration framework source")
        spec = importlib.util.spec_from_file_location(name, path)
        need(spec is not None, "Cannot load source declaration framework source")
        module = importlib.util.module_from_spec(spec)
        exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        sys.modules[name] = module
    return sys.modules[name]


def has_source_declaration_gap(row):
    """Validate the explicit two-task route; source-only rows stay unbound."""
    declared = row.get("paper_outcomes")
    if declared is None:
        return False
    need(type(declared) is dict, "Paper outcome binding must be an object")
    if has_endpoint_selection(row):
        # coverage/context authenticate the new selection before this former
        # gap can cease being the active primary. Its source record is retained.
        return False
    if row.get("id") not in SOURCE_DECLARATION_GAP_IDS:
        need("source_declaration_gap" not in declared,
             "Source declaration gap selector is restricted to the reviewed two tasks")
        return False
    need(set(declared) == {"schema_version", "previous_specification", "source_declaration_gap"}
         and declared["schema_version"] == VERSION,
         "Adopted source declaration gap requires its exact missing-contract route")
    declaration_gap_module().require_pin(declared["source_declaration_gap"], SOURCE_DECLARATION_GAP_PATH,
        "source declaration record", maximum=declaration_gap_module().MAX_RECORD_BYTES)
    return True


def bind_source_declaration_gaps(previous, record_pin, read_pin):
    """Authenticate this invocation's fixed record and applicable original IDs."""
    required = SOURCE_DECLARATION_GAP_IDS & {identifier for identifier, row in previous.items()
                                           if row.get("track") == "paper"}
    need(bool(required), "Source declaration record must apply to original registered paper tasks")
    module = declaration_gap_module()
    module.require_pin(record_pin, SOURCE_DECLARATION_GAP_PATH, "source declaration record",
                       maximum=module.MAX_RECORD_BYTES)
    document = module.validate_record(read_pin(copy.deepcopy(record_pin), "Paper source declaration gaps"))
    scopes = previous.scope_decisions
    active = (set(scopes["entries"]) | set(scopes.get("same_primary_corrections", {}))) if scopes else set()
    need(not required & active, "Source declaration gaps cannot combine active scope corrections")
    previous.source_declaration_gaps = document
    previous.source_declaration_gap_pin = copy.deepcopy(record_pin)


_ISTTC_QC_AUTHORITY = {'resolution_id': 'isttc-staged-qc-prose-v1', 'provenance': {'path': 'benchmarks/paper/PAPER-paper-method-add-004/docs/provenance/empirical-qc-source-resolution.v1.json', 'bytes': 7158, 'sha256': '35909b62820924e97a02282b68a36289a76e3cb6ddff7be88e3212b1b62e7533'}}
_ISTTC_QC_PRIMARY = 'The original empirical unit/session/mouse/area roster, interval coordinates and trial-window draws remain unmaterialized. Existing pinned author source documents staged QC: the broader loader amplitude cutoff 0.1 is followed by an eight-area filter using amplitude_cutoff < 0.01, isi_violations < 0.5 and presence_ratio > 0.9. This resolves the unexplained 0.1-versus-0.01 contrast at source-policy level only. Paper inclusive boundaries versus source strict boundaries, the saved presence-ratio minimum 0.95 and exact historical AllenSDK filtering, authentic 5775-unit/26-mouse membership, complete fit failures and panel-specific masks remain unresolved.'
_ISTTC_QC_BLOCK_BEFORE = 'Allen5775-unit cohort, amplitude-cutoff discrepancy, original mouse IDs and historical trial/window draws remain unresolved.'
_ISTTC_QC_BLOCK_AFTER = 'The original 5775-unit/26-mouse empirical cohort, mouse/session identities, intervals, historical trial draws and panel masks remain unresolved. The pinned downstream <0.01 amplitude filter explains the loader 0.1 threshold; exact boundary and historical presence/AllenSDK selection still require qualification.'
_ISTTC_QC_ACTION_BEFORE = 'Known-timescale synthetic estimation can support an improvement endpoint, but original error semantics, exact baseline aggregates, fitter parity and empirical cohort/window identity remain unresolved. Paper Eq. 21 displays signed REE whereas the registered sensitivity policy uses absolute error; lower signed bias is not automatically greater accuracy. Empirical pseudo-REE uses an estimator-derived reference and cannot establish recovery of true neural timescales. Original signed/absolute REE convention and corresponding baseline aggregates require primary figure-code reconciliation. Original fitter/uncertainty parameterization and NaN/quality masks are not verified against published results. Allen5775-unit cohort, amplitude-cutoff discrepancy, original mouse IDs and historical trial/window draws remain unresolved. Selected finite programme does not cover all duration/trial sensitivity and empirical endpoints. No admitted author rerun, original-task evaluator, meaningful-effect/uncertainty decision or fixed episode access/resource budget.'
_ISTTC_QC_ACTION_AFTER = 'Known-timescale synthetic estimation can support an improvement endpoint, but original error semantics, exact baseline aggregates, fitter parity and empirical cohort/window identity remain unresolved. Paper Eq. 21 displays signed REE whereas the registered sensitivity policy uses absolute error; lower signed bias is not automatically greater accuracy. Empirical pseudo-REE uses an estimator-derived reference and cannot establish recovery of true neural timescales. Original signed/absolute REE convention and corresponding baseline aggregates require primary figure-code reconciliation. Original fitter/uncertainty parameterization and NaN/quality masks are not verified against published results. The original 5775-unit/26-mouse empirical cohort, mouse/session identities, intervals, historical trial draws and panel masks remain unresolved. The pinned downstream <0.01 amplitude filter explains the loader 0.1 threshold; exact boundary and historical presence/AllenSDK selection still require qualification. Selected finite programme does not cover all duration/trial sensitivity and empirical endpoints. No admitted author rerun, original-task evaluator, meaningful-effect/uncertainty decision or fixed episode access/resource budget.'


def _isttc_qc_resolution(entry):
    """Accept only the reviewed iSTTC prose resolution, never arbitrary edits."""
    if entry is None or "source_policy_resolution" not in entry:
        return None
    need(entry.get("task_id") == "PAPER-paper-method-add-004"
         and entry.get("source_policy_resolution") == _ISTTC_QC_AUTHORITY
         and type(entry.get("remaining_source_limits")) is list
         and bool(entry["remaining_source_limits"])
         and entry["remaining_source_limits"][0] == _ISTTC_QC_PRIMARY,
         "Unreviewed iSTTC source-policy resolution")
    return copy.deepcopy(_ISTTC_QC_AUTHORITY["provenance"])


def _project_isttc_qc_resolution(result, entry):
    if _isttc_qc_resolution(entry) is None:
        return
    need(result["blocking_issues"]["retained_secondary_improvement"][2] == _ISTTC_QC_BLOCK_BEFORE
         and result["next_implementation_action"]["retained_secondary_improvement"]["action"] == _ISTTC_QC_ACTION_BEFORE,
         "iSTTC source-policy instruction preimage changed")
    result["blocking_issues"]["retained_secondary_improvement"][2] = _ISTTC_QC_BLOCK_AFTER
    result["next_implementation_action"]["retained_secondary_improvement"]["action"] = _ISTTC_QC_ACTION_AFTER


def _authenticate_isttc_qc_resolution(entry, read_pin):
    record_pin = _isttc_qc_resolution(entry)
    if record_pin is None:
        return None
    record = read_pin(record_pin, "iSTTC staged QC source-policy provenance")
    need(type(record) is dict and record.get("task_id") == "PAPER-paper-method-add-004"
         and record.get("schema") == "isttc_empirical_qc_source_resolution_v1",
         "Invalid iSTTC source-policy provenance")
    return record_pin["path"]


# Exact REVE reporting revision. This changes reporting, never scientific policy.
_REVE_HOME = "benchmarks/paper/PAPER-paper-method-003"
_REVE_OLD_IMPROVEMENT = {"path": _REVE_HOME + "/improvement.v1.json", "bytes": 16334, "sha256": "3b7d04a02c39793f20f907dd1b6e64ce090067decd7effb9ceeea8a2fbcb7408"}
_REVE_IMPROVEMENT = {"path": _REVE_HOME + "/improvement.v1.json", "bytes": 16434, "sha256": "39731c74f06523f789326bf86ed9822543f72b2ff2f8ac85563359fe5fd537c7"}
_REVE_TASK = {"path": _REVE_HOME + "/task.json", "bytes": 18826, "sha256": "5efe0f0b62682a35184be87a91a64ac7c8d9ec78f9076297e80dc78483923423"}
_REVE_OLD_TASK = {"path": _REVE_HOME + "/task.json", "bytes": 18776, "sha256": "b80a91b5b4b4977a9690de2724b52a210987289e5df7e9dba9d0f7ec815613b3"}
_REVE_OUTCOMES = {"path": _REVE_HOME + "/outcomes.v1.json", "bytes": 1458, "sha256": "8068d87ea97656589802b027e11431c33884490b37217528cb3d19cdf37e8685"}
_REVE_RETAINED_IMPROVEMENT = {**_REVE_OLD_IMPROVEMENT, "path": _REVE_HOME + "/historical/improvement.pre-readiness-reporting.v1.json"}
_REVE_RETAINED_OUTCOMES = {"path": _REVE_HOME + "/historical/outcomes.pre-readiness-reporting.v1.json", "bytes": 1333, "sha256": "9e7fe21d4a6b2c9bb01e4228de67e62cd8add6d3b9c196175ce719fdfdf30408"}
_REVE_PENDING = "Candidate outcome pending: no candidate comparison has run; absence of that attempt is not a benchmark-construction blocker."


def has_reve_reporting(row):
    return (row.get("id") == "PAPER-paper-method-003"
            and row.get("specification") == _REVE_TASK)


def _reve_contract_pin(document):
    # This already-reviewed contract uses the retained ASCII JSON serialization.
    body = (json.dumps(document, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
    return pin(_REVE_IMPROVEMENT["path"], body)


def _reve_corrected_improvement(retained):
    need(_reve_contract_pin(retained) == _REVE_OLD_IMPROVEMENT,
         "REVE retained improvement differs from its exact original bytes")
    result = copy.deepcopy(retained)
    before = "No authentic author-model reproduction or candidate comparison has run."
    after = "No authentic author-model calibration has run."
    need(result["blocking_issues"][2].startswith(before), "REVE original reporting sentence changed")
    result["blocking_issues"][2] = after + result["blocking_issues"][2][len(before):]
    result["disposition_reason"] += " " + _REVE_PENDING
    need(_reve_contract_pin(result) == _REVE_IMPROVEMENT, "REVE selected reporting contract changed")
    return result


def reve_reporting_bundle(read_pin):
    """Authenticate current and retained files separately; never fake an old pin."""
    task = read_pin(_REVE_TASK, "Selected REVE reporting task")
    current = read_pin(_REVE_IMPROVEMENT, "Selected REVE reporting contract")
    outcomes = read_pin(_REVE_OUTCOMES, "Selected REVE reporting outcomes")
    retained = read_pin(_REVE_RETAINED_IMPROVEMENT, "Retained REVE improvement archive")
    old_outcomes = read_pin(_REVE_RETAINED_OUTCOMES, "Retained REVE outcome archive")
    need(pin(_REVE_TASK["path"], encode(task)) == _REVE_TASK,
         "Selected REVE task serialization changed")
    need(current == _reve_corrected_improvement(retained), "REVE reporting revision changed scientific fields")
    expected = copy.deepcopy(old_outcomes)
    expected["original_task_sha256"] = _REVE_TASK["sha256"]
    expected["contracts"]["improvement"] = hashlib.sha256(
        json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    expected["pairing"]["improvement"]["rationale"] += " " + _REVE_PENDING
    need(outcomes == expected, "REVE outcome revision changed beyond reporting identities and rationale")
    return {"current": current, "retained": retained}


def reve_retained_improvement(requested, read_pin):
    """One exact old logical descriptor resolves to its explicit retained archive."""
    if requested != _REVE_OLD_IMPROVEMENT:
        return None
    # The caller already observed a mismatch at the physical current path.
    # Authenticate the complete selected correction before admitting the archive.
    return reve_reporting_bundle(read_pin)["retained"]


def _project_reve_reporting(result, improvement):
    observed = _reve_contract_pin(improvement)
    need(observed in (_REVE_OLD_IMPROVEMENT, _REVE_IMPROVEMENT),
         "Unselected REVE improvement revision")
    if observed == _REVE_OLD_IMPROVEMENT:
        return result
    need(pin(_REVE_OLD_TASK["path"], encode(result)) == _REVE_OLD_TASK,
         "REVE reporting revision changed retained task lineage")
    result["blocking_issues"]["improvement"] = copy.deepcopy(improvement["blocking_issues"])
    result["holds"]["preserved_limits"]["task_specific"] = copy.deepcopy(improvement["blocking_issues"])
    result["next_implementation_action"]["improvement"]["action"] = (
        improvement["disposition_reason"] + " " + " ".join(improvement["blocking_issues"]))
    need(pin(_REVE_TASK["path"], encode(result)) == _REVE_TASK,
         "REVE reporting projection differs from the selected postimage")
    return result


def project_task(previous, row, improvement, scope_entry=None, *, reproduction_version="paper-reproduction/v1",
                 primary_correction=None):
    """Return the reviewed dual-outcome wording, preserving scientific inputs.

    This projection intentionally does not depend on the reproduction contract or
    descriptor digest.  Scientific targets, admissible observations, resources,
    provenance, original histories and the improvement contract remain intact.
    Outcome-specific findings, tolerances and unresolved gaps live in the two
    contracts, not in invented generic scores here.
    """
    need(type(previous) is dict and type(row) is dict and type(improvement) is dict,
         "Paper projection requires metadata objects")
    identifier = row["id"]
    need(reproduction_version in REPRODUCTION_FILES, "Unsupported reproduction projection version")
    reproduction_file = REPRODUCTION_FILES[reproduction_version]
    need(row.get("track") == "paper" and improvement.get("task_id") == identifier,
         "Paper projection task identity mismatch")
    need(previous.get("objective") == "surpass_source_paper_same_task",
         "Pre-outcomes definition must retain its prior improvement objective")
    result = copy.deepcopy(previous)
    target = improvement["same_task"]["target"]["description"]
    result["objective"] = OBJECTIVE
    result["goal"] = "Recreate the original findings and separately exceed them on the same source-paper task: " + target
    result["status_basis"] = "The retained status describes the improvement contract; reproduction eligibility is separate."
    result["primary_outputs"] = [
        "Reproduction: executable submitted analysis and source-native outputs for the complete original finding and companion panel.",
        "Improvement: candidate outputs and a comparison on the same original task under improvement.v1.json.",
        "Separate evidence for both outcomes under matched paper+data and paper+data+author-code conditions.",
    ]
    result["success_criteria"] = [
        "Assess reproduction and improvement independently under " + reproduction_file + " and improvement.v1.json; do not combine their scores.",
        "Preserve the original task, full panel, permitted observations, metrics, aggregation and required companion controls.",
        "Reproduction requires a source-grounded computation and independently verified granular outputs; copying published findings alone is insufficient.",
        "Improvement requires the unchanged improvement contract's same-task comparison, uncertainty and admission rules.",
        "Use outcomes.v1.json for the matched information conditions and budgets; a declared contract or admitted receipt is not scientific qualification.",
        "Author-baseline replay remains calibration. Historical reconstruction attempts retain their original scope and are not promoted to new qualified AI reproduction results.",
    ]
    result["evaluation"] = {
        "objective": OBJECTIVE,
        "contracts": {"reproduction": reproduction_file, "improvement": "improvement.v1.json"},
        "paired_protocol": OUTCOMES,
        "information_conditions": list(CONDITIONS),
        "outcome_roles": {"reproduction": "first_class_outcome", "improvement": "first_class_outcome"},
        "author_baseline_role": "calibration",
        "executor_ref": None, "scorer_ref": None, "binary_reward_registered": False,
    }
    # Preserve the inherited statements verbatim but scope them explicitly.  In
    # particular, an improvement episode may correctly call reconstruction a
    # calibration; that statement must not become a universal reproduction rule.
    for field in ("episode", "blocking_issues"):
        if field in previous:
            result[field] = {"improvement": copy.deepcopy(previous[field]),
                             "reproduction_contract": reproduction_file,
                             "paired_protocol": OUTCOMES}
    if "next_implementation_action" in previous:
        result["next_implementation_action"] = {
            "improvement": copy.deepcopy(previous["next_implementation_action"]),
            "reproduction": "Resolve the task-specific source and execution gaps declared in " + reproduction_file + ".",
            "paired_access": "Verify the matched information conditions and budgets declared in outcomes.v1.json.",
        }
    if "holds" in previous:
        result["holds"] = {
            "preserved_limits": copy.deepcopy(previous["holds"]),
            "interpretation": "Source, observation, exposure and execution limits remain in force. Improvement-only criteria apply only to improvement; reproduction-specific gaps are declared in " + reproduction_file + ".",
            "reproduction_contract": reproduction_file,
        }
    if type(result.get("admission")) is dict:
        result["admission"]["delivery_unit"] = "one_registered_paper_task_two_independent_outcomes"
        result["admission"]["reason"] = "Source definitions and binding metadata do not establish execution or either scientific outcome."
    need(scope_entry is None or primary_correction is None, "A task cannot have both scope correction routes")
    if primary_correction is not None:
        need(primary_correction["task_id"] == identifier
             and primary_correction["disposition"] in NORMAL_SCOPE_DISPOSITIONS
             and (primary_correction["disposition"] != "explicit_primary_selection"
                  or primary_correction.get("adoption_route") == "normal_same_primary_unqualified"),
             "Unexpected same-primary correction")
        result["goal"] = primary_correction["primary_goal"]
        result["primary_scope"] = primary_correction["primary_scope"]
        result["scope_decision"] = {"path": SCOPE_PATH, "task_entry_id": identifier}
        result["source_scope_correction"] = {
            "disposition": "same_primary_unqualified",
            "retained_scope_notes": primary_correction.get("retained_secondary_scope"),
            "retained_source_roles": copy.deepcopy(primary_correction.get("retained_source_roles")),
            "remaining_source_limits": copy.deepcopy(primary_correction["remaining_source_limits"]),
            "scientific_outcome": "unknown",
        }
        if primary_correction["disposition"] == "explicit_primary_selection":
            result["source_scope_correction"]["source_disposition"] = "explicit_primary_selection"
        result["success_criteria"].append(
            "Apply the reviewed same-primary scope correction. A partial component or a prospective extension cannot alone establish the complete primary result; unchanged improvement criteria still apply.")
        result["evaluation"]["scope_disposition"] = "same_primary_unqualified"
        if type(result.get("holds")) is dict:
            result["holds"]["current_primary_source_limits"] = copy.deepcopy(primary_correction["remaining_source_limits"])
            result["holds"]["scope_correction_limit"] = "This scope correction grants no new observation access and changes no improvement metric, criterion or tolerance."
    if scope_entry is not None:
        need(scope_entry["task_id"] == identifier, "Unexpected primary scope correction")
        result["goal"] = scope_entry["primary_goal"]
        result["primary_scope"] = scope_entry["primary_scope"]
        result["retained_secondary_scope"] = scope_entry["retained_secondary_scope"]
        result["scope_decision"] = {"path": SCOPE_PATH, "task_entry_id": identifier}
        result["status_basis"] = "The retained status describes the preserved secondary improvement contract. Primary reproduction and same-result improvement require their own source-grounded eligibility decisions."
        result["primary_outputs"] = [
            "Reproduction: executable analysis and source-native outputs for the corrected primary empirical findings: " + scope_entry["primary_scope"],
            "Primary improvement: unavailable until a source-grounded same-result comparison is independently justified; no new score or direction is implied.",
            "Retained secondary work: " + scope_entry["retained_secondary_scope"],
        ]
        result["success_criteria"] = [
            "Recreate the corrected primary empirical findings with their source-defined populations, complete required panels and controls.",
            "Use an explicitly bound reproduction proposal only within its declared eligibility, comparison and execution limits; copying published findings is insufficient.",
            "The preserved improvement.v1.json retains its declared comparison and coverage. Use retained_secondary_scope for its relationship to the corrected primary findings; satisfying a secondary or partial-component criterion alone does not establish complete primary reproduction or improvement.",
            "The primary same-target outcome bundle is unavailable. Any primary improvement requires an independently justified source-grounded comparison; no replacement metric, direction or tolerance is invented.",
            "Keep the paper+data and paper+data+author-code outcomes separate. All scientific outcomes remain unknown until qualifying original-data execution and independent verification.",
            "Preserve prior task definitions, improvement criteria and useful secondary implementations with their original scopes. Historical attempts and source metadata do not become qualified AI results.",
        ]
        result["evaluation"]["contracts"] = {"reproduction": None, "improvement": None}
        result["evaluation"]["reproduction_proposal"] = "Only a proposal explicitly bound in outcomes.v1.json is adopted."
        result["evaluation"]["retained_secondary_improvement"] = "improvement.v1.json"
        result["evaluation"]["primary_bundle_status"] = scope_entry["paired_bundle_status"]
        if scope_entry["paired_bundle_status"] == "unavailable_complete_primary_pairing":
            result["status_basis"] = "The retained status describes the preserved improvement contract and its declared coverage. Complete primary reproduction and same-result improvement require their own source-grounded eligibility decisions."
            result["primary_outputs"][2] = "Retained source work: " + scope_entry["retained_secondary_scope"]
            result["success_criteria"][5] = "Preserve prior task definitions, improvement criteria and useful retained implementations with their declared coverage. Historical attempts and source metadata do not become qualified AI results."
        for field in ("episode", "blocking_issues"):
            if field in previous:
                result[field] = {"retained_secondary_improvement": copy.deepcopy(previous[field]),
                                 "primary_source_limits": copy.deepcopy(scope_entry["remaining_source_limits"]),
                                 "outcome_availability": OUTCOMES}
        if "next_implementation_action" in previous:
            result["next_implementation_action"] = {
                "retained_secondary_improvement": copy.deepcopy(previous["next_implementation_action"]),
                "primary": "Resolve the corrected primary source limits and establish a source-grounded reproduction interface; separately justify any primary improvement comparison.",
            }
        if "holds" in previous:
            result["holds"] = {"preserved_predecessor_limits": copy.deepcopy(previous["holds"]),
                               "interpretation": "Preserved source, observation, exposure and execution restrictions apply within their retained scope. Secondary or partial-component criteria cannot, alone, qualify or redefine the complete corrected primary findings; retain the exact relationship and coverage stated in retained_secondary_scope.",
                               "primary_source_limits": copy.deepcopy(scope_entry["remaining_source_limits"])}
        _project_isttc_qc_resolution(result, scope_entry)
    if identifier == "PAPER-ROOT-ADD-018":
        # Fixed Figure4 reporting correction; no scientific contract is replaced.
        # Authenticate the original unavailable-scope projection before changing
        # only the seven reviewed reporting fields. Current/history readers still
        # enforce their independent raw-byte identities in context().
        root018_home = "benchmarks/paper/PAPER-ROOT-ADD-018"
        need(scope_entry is not None and primary_correction is None
             and reproduction_version == "paper-reproduction/v2",
             "ROOT018 reporting requires its retained unavailable-scope route")
        need(pin(root018_home + "/historical/task.pre-outcomes.v1.json", encode(previous)) == {
            "path": root018_home + "/historical/task.pre-outcomes.v1.json", "bytes": 18547,
            "sha256": "17ba1586e6e164350bb6d9a6c9346cec4aec9e1dcfe0b312945e6ef65ececf12"},
            "ROOT018 reporting changed its historical task")
        need(pin(root018_home + "/improvement.v1.json", encode(improvement)) == {
            "path": root018_home + "/improvement.v1.json", "bytes": 11757,
            "sha256": "25db16fa1f6872298d80034d01419bc0922878ce6e6d6eefb04fe84081efc193"},
            "ROOT018 reporting changed its retained improvement")
        root018_scope = encode(scope_entry)
        need(len(root018_scope) == 6233 and hashlib.sha256(root018_scope).hexdigest() ==
             "ac542fdc331f83ba3165f29abf65e4efa75202278bb9141c230a0e765371ea71",
             "ROOT018 reporting changed its retained scope entry")
        need(pin(root018_home + "/task.json", encode(result)) == {
            "path": root018_home + "/task.json", "bytes": 24481,
            "sha256": "211be4de10677214ca5dd22345ac454f5ee17db6159afe90af82f358e23e15ba"},
            "ROOT018 reporting changed its original task projection")
        root018_limits = ['Figure 4 is not eligible for the current same-task performance-improvement track from the accepted manuscript and pinned author sources: it reports descriptive expert-OFC cluster/event state-inference findings, not a source-defined performance score or improvement comparison. Smaller p-values, more significant bins and lower training reconstruction error do not establish improvement. This Figure 4 decision does not declare the whole paper ineligible or replace its retained hLDS branch.', 'Figure 4 reproduction remains separately unresolved: the original expert-OFC cluster/event finding is identifiable, but original figure-input production, neuron selection and identity joins, permutation semantics and numerical reference closure are unqualified. The accepted manuscript is not authenticated publisher-version/supplement equivalence; no execution or scientific readiness is established.']
        for root018_field in ("episode", "blocking_issues", "holds"):
            result[root018_field]["primary_source_limits"].extend(root018_limits)
        result["next_implementation_action"]["primary"] = 'Resolve the corrected primary source limits and establish a source-grounded reproduction interface; separately justify any primary improvement comparison. For Figure 4, resolve the original incongruentResponses.mat and info_8comp.mat production/analysis closure for reproduction; preserve its current performance-improvement ineligibility without substituting a metric, split or secondary task.'
        need(pin(root018_home + "/task.json", encode(result)) == {
            "path": root018_home + "/task.json", "bytes": 27454,
            "sha256": "e1fd8bf5ea3970defca67bc992e879d660957f7362fd6476474b6d132b70e5e2"},
            "ROOT018 reporting differs from the reviewed task postimage")
    if identifier == "PAPER-paper-method-003":
        result = _project_reve_reporting(result, improvement)
    return result


class PreviousRows(dict):
    """An authenticated prior roster with separately pinned scope decisions."""
    scope_decisions = None
    scope_pin = None
    source_declaration_gaps = None
    source_declaration_gap_pin = None
    endpoint_selections = None


def read_reproduction(member_pin, home, read_pin):
    """Admit only a fixed filename whose declared schema version agrees."""
    need(type(member_pin) is dict and member_pin.get("path") in
         {home + "/" + filename for filename in REPRODUCTION_FILES.values()},
         "Expected an explicit versioned reproduction filename")
    require_pin(member_pin, member_pin["path"], "reproduction contract")
    document = read_pin(member_pin, "Reproduction contract")
    need(type(document) is dict and document.get("schema_version") in REPRODUCTION_FILES,
         "Unsupported reproduction contract version")
    need(member_pin["path"] == home + "/" + REPRODUCTION_FILES[document["schema_version"]],
         "Reproduction filename must match its declared schema version")
    return document


def scope_decisions(value):
    need(type(value) is dict and value.get("schema_version") == SCOPE_VERSION,
         "Invalid paper scope-decision artifact")
    entries = value.get("entries")
    need(type(entries) is dict and SCOPE_IDS <= set(entries) and len(entries) <= 1000
         and all(type(identifier) is str and SCOPE_ID.fullmatch(identifier) for identifier in entries),
         "Scope decision must retain the adjudicated tasks and explicit bounded paper identities")
    for identifier, entry in entries.items():
        need(type(entry) is dict and entry.get("task_id") == identifier, "Invalid scope-decision task identity")
        _isttc_qc_resolution(entry)
        need(entry.get("projection_action", "revise_primary_scope") == "revise_primary_scope",
             "A passive scope confirmation cannot be an active correction")
        need(entry.get("adoption_route", "full_primary_pairing_unavailable") == "full_primary_pairing_unavailable",
             "Scope decision adoption route differs from its unavailable map")
        need(entry.get("paired_bundle_status") != "unavailable_complete_primary_pairing"
             or entry.get("adoption_route") == "full_primary_pairing_unavailable",
             "Neutral full-primary unavailability requires an explicit reviewed route")
        for field in ("primary_goal", "primary_scope", "retained_secondary_scope"):
            need(type(entry.get(field)) is str and bool(entry[field].strip()), "Missing source-grounded scope field: " + field)
        need(type(entry.get("remaining_source_limits")) is list and all(type(item) is str and item.strip() for item in entry["remaining_source_limits"]), "Invalid remaining source limits")
        need(entry.get("primary_same_task_improvement") == "unavailable_until_independently_justified"
             and entry.get("paired_bundle_status") in UNAVAILABLE_REASONS
             and entry.get("scientific_outcome") == "unknown", "Scope decisions cannot qualify a primary outcome")
    corrections = value.get("same_primary_corrections", {})
    need(type(corrections) is dict and len(entries) + len(corrections) <= 1000
         and not (set(entries) & set(corrections)), "Primary correction routes must be bounded and disjoint")
    for identifier, entry in corrections.items():
        need(type(identifier) is str and SCOPE_ID.fullmatch(identifier)
             and type(entry) is dict and entry.get("task_id") == identifier, "Invalid same-primary correction identity")
        need("source_policy_resolution" not in entry, "iSTTC source-policy resolution requires the unavailable scope route")
        need(entry.get("projection_action", "revise_primary_scope") == "revise_primary_scope",
             "A passive scope confirmation cannot be an active correction")
        need(entry.get("adoption_route", "normal_same_primary_unqualified") == "normal_same_primary_unqualified",
             "Scope decision adoption route differs from its normal correction map")
        for field in ("primary_goal", "primary_scope"):
            need(type(entry.get(field)) is str and bool(entry[field].strip()), "Missing same-primary source field: " + field)
        need(type(entry.get("remaining_source_limits")) is list
             and all(type(item) is str and item.strip() for item in entry["remaining_source_limits"]),
             "Invalid same-primary source limits")
        need(entry.get("disposition") in NORMAL_SCOPE_DISPOSITIONS
             and entry.get("paired_bundle_status") == "same_primary_unqualified"
             and entry.get("scientific_outcome") == "unknown", "Same-primary correction cannot qualify an outcome")
        need(entry.get("disposition") != "explicit_primary_selection"
             or entry.get("adoption_route") == "normal_same_primary_unqualified",
             "Explicit primary selection requires an explicit reviewed normal route")
        notes, roles = entry.get("retained_secondary_scope"), entry.get("retained_source_roles")
        need(notes is None or type(notes) is str and bool(notes.strip()), "Invalid retained source scope notes")
        need(roles is None or type(roles) in (dict, list), "Invalid retained source roles")
    confirmations = value.get("source_gap_confirmations", {})
    need(type(confirmations) is dict and len(entries) + len(corrections) + len(confirmations) <= 1000
         and not ((set(entries) | set(corrections)) & set(confirmations)),
         "Passive confirmations must be bounded and separate from scope corrections")
    for identifier, entry in confirmations.items():
        need(type(identifier) is str and SCOPE_ID.fullmatch(identifier)
             and type(entry) is dict and entry.get("task_id") == identifier
             and entry.get("projection_action") == "none"
             and entry.get("adoption_route", "source_gap_confirmation") == "source_gap_confirmation"
             and entry.get("scientific_outcome", "unknown") == "unknown",
             "Invalid passive source-gap confirmation")
    return value


def coverage(registry, read_pin):
    """Authenticate coverage and immutable prior rows using bounded caller I/O.

    ``read_pin(pin, label)`` must authenticate all raw bytes against the exact
    closed pin and return a strict JSON object.  It must not follow evidence URLs
    or implementation entrypoints.  No registration count is manufactured here.
    """
    rows = registry.get("tasks")
    need(type(rows) is list and all(type(row) is dict for row in rows), "Invalid task roster for paper outcomes")
    meta = registry.get("paper_outcomes")
    if meta is None:
        need(endpoint_selection_module().AUTHORITY_PIN is None,
             "Adopted endpoint authority cannot be omitted from coverage")
        need(not any("paper_outcomes" in row for row in rows), "Paper outcome rows require coverage metadata")
        histories = registry.get("historical_registries", [])
        need(not (type(histories) is list and any(type(item) is dict and item.get("path") == SNAPSHOT
                                                for item in histories)),
             "Enrolled pre-outcomes history requires current paper outcome coverage")
        return None
    base_keys = {"schema_version", "coverage_required", "registered_count", "pre_outcomes_registry"}
    need(type(meta) is dict and base_keys <= set(meta)
         and set(meta) <= base_keys | {"scope_decisions", "source_declaration_gaps", "endpoint_selections"}
         and meta["schema_version"] == VERSION and meta["coverage_required"] is True
         and type(meta["registered_count"]) is int,
         "Invalid paper outcome coverage metadata")
    papers = [row for row in rows if row.get("track") == "paper"]
    need(meta["registered_count"] == len(papers) and len(papers) > 0,
         "Paper outcome coverage count differs from registered paper tasks")
    require_pin(meta["pre_outcomes_registry"], SNAPSHOT, "pre-outcomes registry")
    previous = read_pin(meta["pre_outcomes_registry"], "Pre-outcomes registry")
    need(type(previous) is dict and previous.get("schema_version") == 1
         and previous.get("kind") == "neuroscience_benchmark_registry" and "paper_outcomes" not in previous,
         "Invalid pre-outcomes registry snapshot")
    old_rows = previous.get("tasks")
    need(type(old_rows) is list and all(type(row) is dict and type(row.get("id")) is str for row in old_rows),
         "Invalid pre-outcomes task roster")
    old = PreviousRows((row["id"], row) for row in old_rows)
    current = {row["id"]: row for row in rows}
    need(len(old) == len(old_rows) and len(current) == len(rows)
         and set(old) <= set(current), "Paper outcome binding cannot replace prior task identities")
    old_paper = {identifier for identifier, row in old.items() if row.get("track") == "paper"}
    need(old_paper == {row["id"] for row in papers}, "Paper outcome binding must preserve the entire prior paper roster")
    need(not (SCOPE_IDS & old_paper) or "scope_decisions" in meta, "Corrected primary tasks require their exact public scope decisions")
    if "scope_decisions" in meta:
        require_pin(meta["scope_decisions"], SCOPE_PATH, "scope decisions")
        old.scope_decisions = scope_decisions(read_pin(meta["scope_decisions"], "Paper scope decisions"))
        old.scope_pin = meta["scope_decisions"]
        referenced = (set(old.scope_decisions["entries"]) | set(old.scope_decisions.get("same_primary_corrections", {}))
                      | set(old.scope_decisions.get("source_gap_confirmations", {})))
        need(bool(referenced & old_paper), "Scope decisions must apply to registered paper tasks")
    required_gaps = SOURCE_DECLARATION_GAP_IDS & old_paper
    need(not required_gaps or "source_declaration_gaps" in meta,
         "Adopted source declaration gaps require their exact public record")
    if "source_declaration_gaps" in meta:
        bind_source_declaration_gaps(old, meta["source_declaration_gaps"], read_pin)
    old.endpoint_selections = endpoint_selection_module().authenticate_authority(
        meta.get("endpoint_selections"), old, rows, read_pin)
    selected_endpoint_ids = endpoint_selection_ids(old)
    need(all("paper_outcomes" in row for row in papers)
         and all("paper_outcomes" not in row for row in rows if row.get("track") != "paper"),
         "Paper outcome binding requires exactly every registered paper task")
    for row in papers:
        prior = old[row["id"]]
        need("paper_outcomes" not in prior, "Pre-outcomes row must precede outcome adoption")
        need(has_source_declaration_gap(row) == (row["id"] in required_gaps - selected_endpoint_ids),
             "Original source declaration gap task cannot omit its adopted route")
        successor_selected = has_primary_successor(row)
        has_retinal_paired_revision(row)
        has_continuous_outcomes(row)
        has_meg_generic_classification(row)
        for field in PRESERVED_ROW_FIELDS:
            if field == "title" and row["id"] in selected_endpoint_ids:
                # The sealed authority already authenticated the selected task
                # raw/canonical identity and exact current registration title.
                continue
            if field == "title" and successor_selected and row["id"] == PRIMARY_SUCCESSOR_TASK:
                # This one title is deferred, not accepted: context() must prove
                # the exact reviewed projection after authenticating all pins.
                need(type(row.get("title")) is str and bool(row["title"].strip())
                     and "title" in prior, "SMC title requires current and retained declarations")
                continue
            need((field in row) == (field in prior) and encode(row.get(field)) == encode(prior.get(field)),
                 "Paper outcome binding changed prior " + field + ": " + row["id"])
    return old


def unavailable_summary(identifier):
    return {"task_id": identifier, "task_count": 1, "errors": [],
            "assurance": engine().ASSURANCE,
            "paired_metadata_admitted": {outcome: False for outcome in ("reproduction", "improvement")},
            "cells": [{"outcome": outcome, "condition": condition,
                       "eligibility": "unavailable", "endpoint_eligible": False,
                       "pairing_status": "unavailable", "condition_available": False,
                       "scientific_outcome": "unknown", "receipt": None}
                      for outcome in ("reproduction", "improvement") for condition in CONDITIONS]}


def validate_unavailable(outcomes, reproduction, improvement, row, previous_rows):
    """Authenticate full-primary unavailability without admitting a result."""
    keys = {"schema_version", "task_id", "original_task_sha256", "status", "reason_code", "reason",
            "primary_scope", "retained_secondary_improvement", "root_scope_decision"}
    need(type(outcomes) is dict and set(outcomes) in (keys, keys | {"reproduction_proposal"})
         and outcomes.get("schema_version") == UNAVAILABLE, "Invalid unavailable outcome marker")
    identifier, home = row["id"], row["task_directory"]
    need(getattr(previous_rows, "scope_decisions", None) is not None
         and identifier in previous_rows.scope_decisions["entries"],
         "Unavailable primary scope requires a registered source decision")
    entry = previous_rows.scope_decisions["entries"][identifier]
    need(outcomes["task_id"] == identifier and outcomes["original_task_sha256"] == row["specification"]["sha256"]
         and outcomes["status"] == "unavailable"
         and outcomes["reason_code"] == UNAVAILABLE_REASONS[entry["paired_bundle_status"]]
         and type(outcomes["reason"]) is str and bool(outcomes["reason"].strip())
         and outcomes["primary_scope"] == entry["primary_scope"], "Unavailable marker does not bind its corrected primary scope")
    need(outcomes["root_scope_decision"] == {"path": SCOPE_PATH, "raw_sha256": previous_rows.scope_pin["sha256"],
                                            "task_entry_id": identifier}, "Unavailable marker scope decision mismatch")
    module = engine()
    errors = module.improvement.contract_validate(improvement, task_id=identifier)
    need(not errors, "Invalid retained secondary improvement: " + "; ".join(errors))
    need(outcomes["retained_secondary_improvement"] == {
        "path": "improvement.v1.json", "raw_sha256": row["specification_revision"]["improvement_contract"]["sha256"],
        "contract_digest": module.contract_digest(improvement), "scope_description": entry["retained_secondary_scope"]},
        "Unavailable marker changed the retained secondary contract or scope")
    reproduction_pin = row["paper_outcomes"].get("reproduction_contract")
    need((reproduction is not None) == ("reproduction_proposal" in outcomes) == (reproduction_pin is not None),
         "Unavailable reproduction proposal must be explicitly and exactly bound")
    if reproduction is not None:
        errors = engine(reproduction).contract_validate(reproduction, task_id=identifier)
        need(not errors, "Invalid primary reproduction proposal: " + "; ".join(errors))
        need(reproduction["same_task"]["target"]["description"] == entry["primary_scope"],
             "Reproduction proposal target must match the corrected primary scope")
        need(reproduction["source_paper"]["url"] == improvement["source_paper"]["url"],
             "Primary reproduction proposal must retain its source paper identity")
        need(outcomes["reproduction_proposal"] == {"path": REPRODUCTION_FILES[reproduction["schema_version"]], "raw_sha256": reproduction_pin["sha256"],
                                                   "contract_digest": module.contract_digest(reproduction)},
             "Unavailable reproduction proposal identity mismatch")
    return unavailable_summary(identifier)


# Fixed manuscript-scope correction for ROOT004, composed after ROOT018/REVE.
# These reviewed identities cannot be supplied or broadened by a registry row.
_ROOT004_PINS = {'reproduction': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/reproduction.v1.json', 'bytes': 20870, 'sha256': '39bedb14b8ca60bcc9fa6deaffaac8bcb0b8242281eea2f86c07e6f541df505f'}, 'improvement': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/improvement.manuscript-scope.v1.json', 'bytes': 12059, 'sha256': '07822aa62a166e0a98f1ca405ec16a5dfbcfe9cf30f9144a2186067220ef68b0'}, 'task': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/task.json', 'bytes': 20580, 'sha256': '2b9ac9dc16648c5944f091d9de27db7f1ddc90a76f859d96dc5e3ec25b38c6e7'}, 'outcomes': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/outcomes.v1.json', 'bytes': 1479, 'sha256': '2c89671f94151ac0adbcdfc3a9d3cef553f8d3e2d82fb591fe72968eecac09ff'}, 'retained_reproduction': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/historical/pre-manuscript-scope-v1/reproduction.v1.json', 'bytes': 19274, 'sha256': 'f23d1b1da99a1a9b9c0a2e32246c304d992806ba9146b6e1683e527d3ebc8798'}, 'retained_task': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/historical/pre-manuscript-scope-v1/task.json', 'bytes': 19564, 'sha256': 'be95dae6675a2f636e748add4d35490962b6d6304edc84adda4cc9f842bde1d1'}, 'retained_outcomes': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/historical/pre-manuscript-scope-v1/outcomes.v1.json', 'bytes': 1356, 'sha256': 'f63061cf1c6ea8c018478c02eb3e2b745f5f892e095ccdba4da2a5be03ac5434'}, 'retained_improvement': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/improvement.v1.json', 'bytes': 10441, 'sha256': '1722d35399d677f5b5fd666c082f2ace39a9422ce0da09df1746fcccf8e80cd8'}, 'pre_outcomes': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/historical/task.pre-outcomes.v1.json', 'bytes': 19162, 'sha256': 'a163da4d208b7d4edd3d0d35fa741d951c8319789a620daedeac44e817f0240f'}, 'descriptor': {'path': 'benchmarks/paper/PAPER-ROOT-ADD-004/docs/figure3-manuscript-scope.v1.json', 'bytes': 25376, 'sha256': 'ae144988650ffdf3418797eefecf389b9cf092a0149e94a4cf9d969fffc99fa3'}}
_ROOT004_CANONICAL = {'reproduction': 'c1627e0b5e664eaa34dad98854812df055fc8ff3682e98d1f04c9ddd46b34798', 'improvement': 'ad6c9bcad98b5c902b94881de374001760156152aa7daaba7b529eb88125caae', 'task': 'eded18bfe3b29c3f2c763ada0a7c61eaeec00df4d60fe9121a68a326592baae1', 'outcomes': '17352794a351f996334470dd3287f1917acd5fb81a20c7fb9d5d37282183f36d', 'retained_reproduction': '596fbbc331d354a2d63b1b5accf8ed95837f9702b9e07e0a8441c42be74724c9', 'retained_task': '132a3b83f81c1f4319c3b2947acbc5c4fdaa2469007025e73f6775ab487650cd', 'retained_outcomes': 'c608a97ad2eb6d2f8169e676add1a30e66f342eb958310d2286881780056fd04', 'retained_improvement': '18ee71bd9dc3e311b9902f6eee7418db0b545b26e84b8314b762dc69e707c975', 'pre_outcomes': '7bb39bb595837d73c774bbeb2dcee6968beb724417bc4492ad872334466fe27c', 'descriptor': '2383eacc48e5cd083669a4faeb2b07e4c94884260dadd1dad43e1bdfbd844c94'}


def has_root004_scope(row):
    return (row.get("id") == "PAPER-ROOT-ADD-004"
            and row.get("specification") == _ROOT004_PINS["task"])


def _root004_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _root004_replace(previous, replacements):
    result = copy.deepcopy(previous)
    for replacement in replacements:
        parts = replacement["pointer"].split("/")[1:]
        parent = result
        for part in parts[:-1]:
            parent = parent[int(part)] if type(parent) is list else parent[part]
        key = int(parts[-1]) if type(parent) is list else parts[-1]
        need(_root004_digest(parent[key]) == replacement["before_sha256"],
             "ROOT004 field predecessor differs: " + replacement["pointer"])
        parent[key] = copy.deepcopy(replacement["after"])
    return result


def root004_scope_bundle(read_pin):
    """Authenticate only the fixed scope correction, retaining every prior file."""
    documents = {}
    for name, identity in _ROOT004_PINS.items():
        value = read_pin(copy.deepcopy(identity), "ROOT004 manuscript scope " + name)
        need(_root004_digest(value) == _ROOT004_CANONICAL[name],
             "ROOT004 parsed document identity differs: " + name)
        documents[name] = value
    descriptor = documents["descriptor"]
    need(descriptor["schema_version"] == "root004-manuscript-scope/v1"
         and descriptor["task_id"] == "PAPER-ROOT-ADD-004",
         "ROOT004 source scope identity differs")
    for current, retained in (("reproduction", "retained_reproduction"),
                              ("improvement", "retained_improvement"),
                              ("task", "retained_task"), ("outcomes", "retained_outcomes")):
        need(_root004_replace(documents[retained], descriptor["replacements"][current]) == documents[current],
             "ROOT004 correction exceeds its reviewed field guards: " + current)
    need(documents["reproduction"]["eligibility"] == "source_unresolved"
         and documents["improvement"]["disposition"] == "source_unresolved"
         and documents["improvement"]["comparison"]["direction"] == "higher"
         and "admission_policy" not in documents["reproduction"],
         "ROOT004 source correction cannot promote qualification")
    return documents


def _project_root004_scope(projected, documents):
    need(projected == documents["retained_task"]
         and pin(_ROOT004_PINS["retained_task"]["path"], encode(projected)) == _ROOT004_PINS["retained_task"],
         "ROOT004 source correction changed the retained deterministic projection")
    result = _root004_replace(projected, documents["descriptor"]["replacements"]["task"])
    need(result == documents["task"] and pin(_ROOT004_PINS["task"]["path"], encode(result)) == _ROOT004_PINS["task"],
         "ROOT004 source correction changed its selected task projection")
    return result


# Exact NuCLR uncertainty-reporting correction; scientific policy is unchanged.
_NUCLR_HOME = "benchmarks/paper/PAPER-paper-method-replacement-012"
_NUCLR_OLD_IMPROVEMENT = {"path": _NUCLR_HOME + "/improvement.v1.json", "bytes": 14982, "sha256": "f2d4275a29ff41e6a37fd674e3f2f50b2a34a0e7bdf7a8b992bfcc209e2f8f22"}
_NUCLR_IMPROVEMENT = {"path": _NUCLR_HOME + "/improvement.v1.json", "bytes": 15175, "sha256": "0312ae81862130d11a96eb6b59d974cecd96935cdba29461daf7cf4b96e52e2e"}
_NUCLR_TASK = {"path": _NUCLR_HOME + "/task.json", "bytes": 31596, "sha256": "cde7612e71a6133fc3d660b2800d9e4c71ede1a687eec81c611918d323ae8ab8"}
_NUCLR_OUTCOMES = {"path": _NUCLR_HOME + "/outcomes.v1.json", "bytes": 1999, "sha256": "bb76d5fe9ed4946cb8831bc8fce4a937f5136793fcdf7b0562e4772adbd0eabb"}
_NUCLR_RETAINED_IMPROVEMENT = {**_NUCLR_OLD_IMPROVEMENT, "path": _NUCLR_HOME + "/historical/improvement.pre-uncertainty-reporting.v1.json"}
_NUCLR_RETAINED_OUTCOMES = {"path": _NUCLR_HOME + "/historical/outcomes.pre-uncertainty-reporting.v1.json", "bytes": 1999, "sha256": "5f6fd64159dcc2527bd5645c81fe610f52434e2b6a2eff4be151179283e1a6da"}


def has_nuclr_reporting(row):
    declared = row.get("paper_outcomes")
    return (row.get("id") == "PAPER-paper-method-replacement-012"
            and row.get("specification") == _NUCLR_TASK
            and type(declared) is dict and declared.get("outcomes") == _NUCLR_OUTCOMES)


def _nuclr_corrected_improvement(retained):
    need(pin(_NUCLR_OLD_IMPROVEMENT["path"], encode(retained)) == _NUCLR_OLD_IMPROVEMENT,
         "NuCLR retained improvement differs from its exact original bytes")
    result = copy.deepcopy(retained)
    before = "Nine Bugeon macro-F1 panel results, reported as five-training-seed means and standard deviations; EI inductive LOLCAT exceeds NuCLR."
    after = "Nine Bugeon macro-F1 panel results averaged across five training seeds; Table 1 and Table 8 captions identify the accompanying bars as SD, while the paper checklist calls them SEM. Bar type and normalization therefore remain unresolved. The macro-F1 means and panel identities remain valid; EI inductive LOLCAT exceeds NuCLR."
    need(result["task_id"] == "PAPER-paper-method-replacement-012"
         and result["evidence"][0]["id"] == "conference_scores"
         and result["evidence"][0]["supports"] == before,
         "NuCLR uncertainty reporting predecessor changed")
    result["evidence"][0]["supports"] = after
    need(pin(_NUCLR_IMPROVEMENT["path"], encode(result)) == _NUCLR_IMPROVEMENT,
         "NuCLR selected reporting contract changed")
    return result


def nuclr_reporting_bundle(read_pin):
    """Authenticate this exact one-field correction and both retained archives."""
    task = read_pin(copy.deepcopy(_NUCLR_TASK), "Selected NuCLR reporting task")
    current = read_pin(copy.deepcopy(_NUCLR_IMPROVEMENT), "Selected NuCLR reporting contract")
    outcomes = read_pin(copy.deepcopy(_NUCLR_OUTCOMES), "Selected NuCLR reporting outcomes")
    retained = read_pin(copy.deepcopy(_NUCLR_RETAINED_IMPROVEMENT), "Retained NuCLR improvement archive")
    old_outcomes = read_pin(copy.deepcopy(_NUCLR_RETAINED_OUTCOMES), "Retained NuCLR outcome archive")
    need(pin(_NUCLR_TASK["path"], encode(task)) == _NUCLR_TASK,
         "NuCLR reporting changed the original task bytes")
    need(current == _nuclr_corrected_improvement(retained),
         "NuCLR reporting revision changed scientific fields")
    expected = copy.deepcopy(old_outcomes)
    expected["contracts"]["improvement"] = hashlib.sha256(
        json.dumps(current, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    need(outcomes == expected and outcomes["original_task_sha256"] == _NUCLR_TASK["sha256"],
         "NuCLR outcome revision changed beyond the canonical improvement commitment")
    return {"current": current, "retained": retained}


def nuclr_retained_improvement(requested, read_pin):
    """Resolve only the exact old NuCLR pin after authenticating its full bundle."""
    if requested != _NUCLR_OLD_IMPROVEMENT:
        return None
    return nuclr_reporting_bundle(read_pin)["retained"]


def has_meg_generic_classification(row):
    binding = row.get("paper_outcomes")
    if type(binding) is not dict or MEG_GENERIC_FIELD not in binding:
        return False
    need(row.get("id") == MEG_GENERIC_TASK and row.get("track") == "paper"
         and binding[MEG_GENERIC_FIELD] == MEG_GENERIC_MODE_PIN,
         "Generic classification requires the exact selected MEG descriptor")
    return True


def meg_generic_classification_descriptor(read_pin):
    descriptor = read_pin(MEG_GENERIC_MODE_PIN, "MEG Generic classification mode")
    # The published descriptor has the maintained canonical encoding. This
    # second commitment also rejects altered objects supplied by a callback.
    need(type(descriptor) is dict
         and pin(MEG_GENERIC_MODE_PIN["path"], encode(descriptor)) == MEG_GENERIC_MODE_PIN,
         "MEG Generic descriptor differs from its complete selected identity")
    need(descriptor.get("schema") == "meg-generic-classification-mode/v1"
         and descriptor.get("task_id") == MEG_GENERIC_TASK
         and descriptor.get("mode_id") == "generic_feature_classification_v1"
         and descriptor.get("role") == "separately_named_scoped_execution_mode",
         "Invalid MEG Generic classification identity")
    delivery, inputs, scoring = (descriptor["delivery_and_qualification"],
                                 descriptor["input"], descriptor["scoring"])
    need(inputs["selected_rows"] == 188 and inputs["participants"] == 94
         and inputs["raw_to_generic_feature_equivalence_established"] is False
         and inputs["physical_raw_window_timing_reconstructed"] is False
         and scoring["machine_outcomes"]["scientific_superiority_established"] is None
         and scoring["current_sota_claimed"] is False
         and delivery["benchmark_count_increment"] == 0
         and all(delivery[field] is False for field in (
             "authentic_generic_preparation_completed", "native_candidate_runtime_qualified",
             "paired_ai_outcomes_established", "broader_task_admission_changed")),
         "MEG Generic scope cannot grant broader admission or scientific qualification")
    return descriptor


def meg_generic_classification_summary(descriptor):
    result = copy.deepcopy(MEG_GENERIC_PUBLIC_TEXT)
    result.update({
        "mode_id": descriptor["mode_id"], "role": descriptor["role"],
        "descriptor": copy.deepcopy(MEG_GENERIC_MODE_PIN),
        "scientific_question": descriptor["scientific_question"],
        "selected_rows": descriptor["input"]["selected_rows"],
        "participants": descriptor["input"]["participants"],
        "source_labels": copy.deepcopy(descriptor["input"]["source_labels"]),
        "raw_feature_equivalence_established": False,
        "declared_classification_criteria": copy.deepcopy(descriptor["scoring"]["machine_outcomes"]),
        "unpopulated_broader_claims": copy.deepcopy(descriptor["scoring"]["not_populated"]),
        "broader_task_admission_changed": False, "scientific_superiority_established": None,
        "paired_ai_outcomes_established": False, "native_candidate_runtime_qualified": False,
        "benchmark_count_increment": 0, "assurance": descriptor["authority"],
    })
    return result


def project_meg_generic_classification(projected, descriptor):
    need(pin(MEG_GENERIC_BASE_TASK["path"], encode(projected)) == MEG_GENERIC_BASE_TASK,
         "MEG Generic projection requires the exact retained full-primary task")
    result = copy.deepcopy(projected)
    need(type(result.get("evaluation")) is dict
         and "scoped_execution_modes" not in result["evaluation"],
         "MEG Generic projection cannot replace an existing execution mode")
    result["evaluation"]["scoped_execution_modes"] = [meg_generic_classification_summary(descriptor)]
    return result


def validate_meg_generic_outcomes(outcomes):
    retained = copy.deepcopy(outcomes)
    need(type(retained) is dict and "original_task_sha256" in retained,
         "MEG Generic outcomes require the retained task-identity leaf")
    retained["original_task_sha256"] = MEG_GENERIC_BASE_TASK["sha256"]
    need(pin(MEG_GENERIC_BASE_OUTCOMES["path"], encode(retained)) == MEG_GENERIC_BASE_OUTCOMES,
         "MEG Generic outcomes changed beyond the raw task identity")


def meg_generic_classification_adoption(row, document, outcomes, read_pin):
    need(row.get("id") == MEG_GENERIC_TASK and row.get("track") == "paper",
         "MEG Generic adoption cannot select another task")
    descriptor = meg_generic_classification_descriptor(read_pin)
    retained_task = copy.deepcopy(document)
    selected = has_meg_generic_classification(row)
    if selected:
        need(retained_task.get("evaluation", {}).get("scoped_execution_modes")
             == [meg_generic_classification_summary(descriptor)],
             "MEG Generic task changed its selected mode")
        del retained_task["evaluation"]["scoped_execution_modes"]
        validate_meg_generic_outcomes(outcomes)
        need(row.get("specification") == pin(MEG_GENERIC_BASE_TASK["path"], encode(document))
             and row["paper_outcomes"]["outcomes"] == pin(MEG_GENERIC_BASE_OUTCOMES["path"], encode(outcomes))
             and outcomes["original_task_sha256"] == row["specification"]["sha256"],
             "MEG Generic selected current identities differ")
    else:
        need(row.get("specification") == MEG_GENERIC_BASE_TASK
             and row.get("paper_outcomes", {}).get("outcomes") == MEG_GENERIC_BASE_OUTCOMES
             and pin(MEG_GENERIC_BASE_OUTCOMES["path"], encode(outcomes)) == MEG_GENERIC_BASE_OUTCOMES,
             "MEG Generic adoption requires its exact current predecessor")
    projected = project_meg_generic_classification(retained_task, descriptor)
    proposed_outcomes = copy.deepcopy(outcomes)
    proposed_task_pin = pin(MEG_GENERIC_BASE_TASK["path"], encode(projected))
    proposed_outcomes["original_task_sha256"] = proposed_task_pin["sha256"]
    validate_meg_generic_outcomes(proposed_outcomes)
    proposed_row = copy.deepcopy(row)
    proposed_row["specification"] = proposed_task_pin
    proposed_row["paper_outcomes"]["outcomes"] = pin(MEG_GENERIC_BASE_OUTCOMES["path"], encode(proposed_outcomes))
    proposed_row["paper_outcomes"][MEG_GENERIC_FIELD] = copy.deepcopy(MEG_GENERIC_MODE_PIN)
    return proposed_row, projected, proposed_outcomes


def retinal_paired_module():
    """Load the one maintained task-specific metadata adoption implementation."""
    name = "_neurobench_retinal_paired_adoption_v1"
    if name not in sys.modules:
        path = Path(__file__).with_name("paper_retinal_paired_adoption.py")
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        try:
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        except BaseException:
            sys.modules.pop(name, None)
            raise
    return sys.modules[name]


def has_retinal_paired_revision(row):
    declared = row.get("paper_outcomes")
    selected = type(declared) is dict and RETINAL_PAIRED_FIELD in declared
    if selected:
        need(row.get("id") == RETINAL_PAIRED_TASK and row.get("track") == "paper",
             "Retinal paired revision cannot select another task")
        module = retinal_paired_module()
        need(module.DESCRIPTOR_PIN is not None and
             declared[RETINAL_PAIRED_FIELD] == module.DESCRIPTOR_PIN,
             "Retinal paired revision must use its exact selected descriptor")
    return selected


def _retinal_preserved_fields(row, previous_rows):
    need(row.get("id") == RETINAL_PAIRED_TASK and RETINAL_PAIRED_TASK in previous_rows,
         "Retinal paired adoption requires its authenticated predecessor row")
    prior = previous_rows[RETINAL_PAIRED_TASK]
    for field in PRESERVED_ROW_FIELDS:
        need((field in row) == (field in prior) and encode(row.get(field)) == encode(prior.get(field)),
             "Retinal paired adoption changed prior " + field)


def retinal_paired_context(row, document, previous_rows, read_pin, *, improvement_contract=None):
    """Validate retained history normally, then expose the fixed active correction."""
    need(has_retinal_paired_revision(row), "Retinal paired revision must be selected")
    _retinal_preserved_fields(row, previous_rows)
    module = retinal_paired_module()
    handle = module.authenticate(read_pin)
    historical_row = copy.deepcopy(row)
    del historical_row["paper_outcomes"][RETINAL_PAIRED_FIELD]
    historical_row["specification"] = handle.retained_task_pin
    # Recursion removes only this selector; all ordinary historical gates remain.
    historical = context(historical_row, handle.retained_task, previous_rows, read_pin,
                         improvement_contract=improvement_contract)
    projected = module.project(handle.retained_task, handle)
    need(document == projected and row.get("specification") == handle.current_task_pin,
         "Retinal current task differs from its exact supported projection")
    return module.active_context(historical, document, handle, engine=engine)


def adopt_retinal_paired_correction(row, document, previous_rows, read_pin, *, improvement_contract=None):
    """Plan only the reviewed retinal row; never rewrite scientific contracts."""
    need(row.get("id") == RETINAL_PAIRED_TASK and row.get("track") == "paper",
         "Retinal paired adoption cannot select another task")
    _retinal_preserved_fields(row, previous_rows)
    if has_retinal_paired_revision(row):
        bound = context(row, document, previous_rows, read_pin,
                        improvement_contract=improvement_contract)
        return copy.deepcopy(row), copy.deepcopy(document), bound
    module = retinal_paired_module()
    handle = module.authenticate(read_pin)
    need(document == handle.retained_task and row.get("specification") == handle.retained_task_pin,
         "Retinal adoption requires its exact retained current task")
    context(row, document, previous_rows, read_pin, improvement_contract=improvement_contract)
    projected = module.project(document, handle)
    selected = copy.deepcopy(row)
    selected["paper_outcomes"][RETINAL_PAIRED_FIELD] = handle.descriptor_pin
    selected["specification"] = handle.current_task_pin
    bound = context(selected, projected, previous_rows, read_pin,
                    improvement_contract=improvement_contract)
    return selected, projected, bound


def context(row, document, previous_rows, read_pin, *, improvement_contract=None):
    """Validate current bytes and return prior lineage plus separate outcomes.

    Existing initial/historical lineage validators should receive previous_row
    and previous_document.  The exact prior current file is independently pinned
    at previous_pin; no current-path alias is used to impersonate old bytes.
    """
    if previous_rows is None:
        need("paper_outcomes" not in row and document.get("objective") != OBJECTIVE,
             "Unbound dual-outcome definition")
        return None
    if row.get("track") != "paper":
        need("paper_outcomes" not in row, "Neural task cannot carry paper outcome bindings")
        return None
    identifier, home = row["id"], row["task_directory"]
    need(home == "benchmarks/paper/" + identifier, "Paper outcome task home mismatch")
    binding = row.get("paper_outcomes")
    if has_retinal_paired_revision(row):
        return retinal_paired_context(row, document, previous_rows, read_pin,
                                      improvement_contract=improvement_contract)
    meg_generic_selected = has_meg_generic_classification(row)
    selected_endpoint_ids = endpoint_selection_ids(previous_rows)
    endpoint_selected = has_endpoint_selection(row)
    need(endpoint_selected == (identifier in selected_endpoint_ids),
         "Endpoint selection cannot be omitted, substituted, or used without its authority")
    if endpoint_selected:
        return endpoint_selection_module().context(row, document, previous_rows, read_pin, engine,
                                                  improvement_contract=improvement_contract)
    gap_selected = has_source_declaration_gap(row)
    if identifier in SOURCE_DECLARATION_GAP_IDS:
        need(gap_selected, "Original source declaration gap task cannot omit its adopted route")
    if gap_selected:
        return source_declaration_gap_context(row, document, previous_rows, read_pin,
                                              improvement_contract=improvement_contract)
    base_keys = {"schema_version", "previous_specification", "outcomes"}
    successor_selected = has_primary_successor(row)
    continuous_selected = has_continuous_outcomes(row)
    allowed_keys = ((base_keys | {"reproduction_contract"} | PRIMARY_SUCCESSOR_FIELDS,)
                    if successor_selected else (base_keys, base_keys | {"reproduction_contract"}))
    if continuous_selected:
        allowed_keys = tuple(keys | {"continuous_policy_revision"} for keys in allowed_keys)
    if meg_generic_selected:
        need(successor_selected and not continuous_selected, "MEG Generic mode requires its retained primary successor")
        allowed_keys = tuple(keys | {MEG_GENERIC_FIELD} for keys in allowed_keys)
    need(type(binding) is dict and set(binding) in allowed_keys
         and binding["schema_version"] == VERSION, "Invalid paper outcome task binding")
    prior = previous_rows[identifier]
    previous_pin = binding["previous_specification"]
    require_pin(previous_pin, home + "/" + HISTORY, "pre-outcomes definition")
    need(all(previous_pin[key] == prior["specification"][key] for key in ("bytes", "sha256")),
         "Pre-outcomes definition differs from immutable prior registry")
    previous_document = read_pin(previous_pin, "Pre-outcomes definition")
    improvement_pin = row["specification_revision"]["improvement_contract"]
    require_pin(improvement_pin, home + "/improvement.v1.json", "improvement contract")
    reve_reporting = has_reve_reporting(row)
    nuclr_reporting = has_nuclr_reporting(row)
    root004_scope = has_root004_scope(row)
    root004_documents = None
    if root004_scope:
        need(improvement_pin == _ROOT004_PINS["retained_improvement"]
             and binding.get("outcomes") == _ROOT004_PINS["outcomes"]
             and binding.get("reproduction_contract") == _ROOT004_PINS["reproduction"]
             and previous_pin == _ROOT004_PINS["pre_outcomes"]
             and not successor_selected and not continuous_selected,
             "ROOT004 source scope changed its exact retained/current bindings")
        root004_documents = root004_scope_bundle(read_pin)
        need(improvement_contract is None or improvement_contract == root004_documents["retained_improvement"],
             "ROOT004 caller changed the retained improvement")
        retained_improvement, retained_improvement_pin = root004_documents["retained_improvement"], improvement_pin
        improvement, improvement_pin = root004_documents["improvement"], _ROOT004_PINS["improvement"]
    elif nuclr_reporting:
        need(improvement_pin == _NUCLR_OLD_IMPROVEMENT
             and not successor_selected and not continuous_selected,
             "NuCLR reporting changed its retained bindings")
        reporting = nuclr_reporting_bundle(read_pin)
        need(improvement_contract is None or improvement_contract == reporting["retained"],
             "NuCLR caller changed the retained improvement evidence")
        retained_improvement, retained_improvement_pin = reporting["retained"], improvement_pin
        improvement, improvement_pin = reporting["current"], _NUCLR_IMPROVEMENT
    elif reve_reporting:
        need(improvement_pin == _REVE_OLD_IMPROVEMENT
             and binding["outcomes"] == _REVE_OUTCOMES, "REVE reporting selection changed its retained or current bindings")
        reporting = reve_reporting_bundle(read_pin)
        need(improvement_contract is None or improvement_contract == reporting["retained"],
             "REVE caller changed the retained improvement evidence")
        retained_improvement, retained_improvement_pin = reporting["retained"], improvement_pin
        improvement, improvement_pin = reporting["current"], _REVE_IMPROVEMENT
    else:
        improvement = improvement_contract if improvement_contract is not None else read_pin(improvement_pin, "Improvement contract")
        retained_improvement, retained_improvement_pin = improvement, improvement_pin
    scope = getattr(previous_rows, "scope_decisions", None)
    scope_entry = scope["entries"].get(identifier) if scope else None
    source_policy_member = _authenticate_isttc_qc_resolution(scope_entry, read_pin)
    primary_correction = scope.get("same_primary_corrections", {}).get(identifier) if scope else None
    reproduction = read_reproduction(binding["reproduction_contract"], home, read_pin) if "reproduction_contract" in binding else None
    if nuclr_reporting:
        need(scope_entry is None and primary_correction is None,
             "NuCLR reporting cannot combine another source correction")
    if root004_scope:
        need(scope_entry is None and primary_correction is None
             and reproduction == root004_documents["reproduction"],
             "ROOT004 manuscript scope cannot combine another correction")
    successor = None
    if successor_selected:
        successor_module = primary_successor_module(identifier)
        arguments = dict(
            revision_pin=binding["primary_policy_revision"], primary_pin=binding["primary_improvement_contract"],
            reproduction_pin=binding["reproduction_contract"], previous_pin=previous_pin,
            retained_improvement_pin=retained_improvement_pin, read_pin=read_pin)
        if identifier == PRIMARY_SUCCESSOR_TASK:
            need(scope_entry is None and primary_correction is None,
                 "SMC temporal successor cannot combine another primary scope projection")
        elif identifier == "PAPER-paper-method-029":
            need(scope_entry is None and primary_correction is None,
                 "Deeprecon reference recovery cannot combine a primary scope correction")
            need(reproduction is not None and reproduction.get("schema_version") == "paper-reproduction/v1",
                 "Deeprecon reference recovery requires its unchanged v1 reproduction")
            arguments["task_id"] = identifier
        else:
            need(scope_entry is None and primary_correction is not None,
                 "Scope policy successor requires its reviewed normal scope correction")
            need(reproduction is not None and reproduction.get("schema_version") == "paper-reproduction/v2",
                 "Scope policy successor requires the reviewed v2 reproduction")
            require_pin(previous_rows.scope_pin, SCOPE_PATH, "scope policy authority")
            need(previous_rows.scope_pin == successor_module.SCOPE_PIN,
                 "Scope policy successor requires the exact reviewed scope authority")
            arguments["task_id"] = identifier
        successor = successor_module.authenticate(**arguments)
        need(engine().contract_digest(retained_improvement) == engine().contract_digest(successor.retained_improvement),
             "Retained improvement differs from authenticated successor lineage")
        improvement, improvement_pin = successor.primary_improvement, binding["primary_improvement_contract"]
    projection_policy = successor_module.projection_improvement(successor) if identifier == 'PAPER-ROOT-ADD-001' and successor is not None else improvement
    projected = project_task(previous_document, prior, projection_policy, scope_entry,
                             reproduction_version=reproduction["schema_version"] if reproduction is not None else "paper-reproduction/v1",
                             primary_correction=primary_correction)
    if successor is not None:
        projected = successor_module.project(projected, successor)
        if not continuous_selected:
            need(row.get("title") == projected["title"], "Primary successor current title differs from the reviewed successor projection")
    if root004_scope:
        projected = _project_root004_scope(projected, root004_documents)
    meg_generic_descriptor = None
    if meg_generic_selected:
        meg_generic_descriptor = meg_generic_classification_descriptor(read_pin)
        projected = project_meg_generic_classification(projected, meg_generic_descriptor)
    retained_current = pin(home + "/task.json", encode(projected))
    continuous = None
    continuous_selection = None
    current_continuous = None
    if continuous_selected:
        current_continuous = successor_module.current_continuous(
            revision_pin=binding["continuous_policy_revision"], temporal=successor,
            temporal_task=projected, read_pin=read_pin)
        projected, continuous = current_continuous["projected"], current_continuous["current"]
        continuous_selection = current_continuous["selection"]
        need(row.get("title") == projected["title"], "Primary successor current title differs from the reviewed successor projection")
    expected_current = pin(home + "/task.json", encode(projected))
    need(document == projected and row.get("specification") == expected_current,
         "Current paper definition differs from the deterministic dual-outcome projection")
    if identifier == "PAPER-ROOT-ADD-018":
        need(binding["outcomes"] == {
            "path": "benchmarks/paper/PAPER-ROOT-ADD-018/outcomes.v1.json", "bytes": 4745,
            "sha256": "8bd7bc3479aa808556ae84858b06e3f990744d52d71f1f99778c658feeb89ab8"},
            "ROOT018 reporting changed its selected outcomes")
    require_pin(binding["outcomes"], home + "/" + OUTCOMES, "paper outcomes")
    outcomes = read_pin(binding["outcomes"], "Paper outcomes")
    need(type(outcomes) is dict, "Paper outcomes must be an object")
    if meg_generic_selected:
        validate_meg_generic_outcomes(outcomes)
    # The descriptor is authenticated above and owned by its existing implementation
    # artifact; adding it to outcome members would duplicate that ownership route.
    members = {previous_pin["path"], binding["outcomes"]["path"]}
    if reve_reporting:
        members.update((_REVE_RETAINED_IMPROVEMENT["path"], _REVE_RETAINED_OUTCOMES["path"]))
    if nuclr_reporting:
        members.update((_NUCLR_RETAINED_IMPROVEMENT["path"], _NUCLR_RETAINED_OUTCOMES["path"]))
    if root004_scope:
        # The retained improvement remains authenticated by the full scope
        # bundle and owned by the task revision route, not by outcomes twice.
        for root004_name in ("descriptor", "improvement",
                             "retained_task", "retained_reproduction", "retained_outcomes"):
            root004_path = _ROOT004_PINS[root004_name]["path"]
            need(root004_path not in members, "Duplicate ROOT004 source scope member")
            members.add(root004_path)
    if source_policy_member is not None:
        members.add(source_policy_member)
    if "reproduction_contract" in binding:
        members.add(binding["reproduction_contract"]["path"])
    successor_provenance = None
    if successor is not None:
        successor_members = {member["path"]: member for member in successor.members}
        if identifier == PRIMARY_SUCCESSOR_TASK:
            successor_provenance = {
                "projection": successor_members[successor_module.PROJECTION],
                "scientific_contract": successor_members[home + "/docs/scientific-contract.temporal-scope.v1.json"],
            }
        elif identifier in REFERENCE_SUCCESSOR_TASKS:
            successor_provenance = successor.public_provenance
        else:
            successor_provenance = {"scope_decision": copy.deepcopy(previous_rows.scope_pin)}
        for member in successor.members:
            need(member["path"] not in members, "Duplicate primary successor metadata member")
            members.add(member["path"])
    unavailable = outcomes.get("schema_version") == UNAVAILABLE
    need(unavailable == (scope_entry is not None), "Corrected primary scopes cannot use a mixed-scope normal outcome bundle")
    if unavailable:
        result = validate_unavailable(outcomes, reproduction, improvement, row, previous_rows)
    else:
        need(reproduction is not None, "Normal paper outcomes require a reproduction contract")
        module = engine(reproduction)
        selected_language = identifier == 'PAPER-ROOT-ADD-001' and successor_module.is_figure3b(successor)
        if selected_language:
            result = successor_module.figure3b_summary(successor, outcomes, reproduction, improvement, module)
            errors = result['errors']
        else:
            errors = module.outcomes_validate(outcomes, reproduction, improvement)
        need(not errors, "Invalid paper outcome contracts for " + identifier + ": " + "; ".join(errors))
        outcome_identity = retained_current if continuous is not None else expected_current
        need(outcomes["task_id"] == identifier and outcomes["original_task_sha256"] == outcome_identity["sha256"],
             "Paper outcomes must bind the raw current task identity" if not continuous_selected else
             "Retained paper outcomes must bind the exact temporal task identity")
        if primary_correction is not None:
            need(reproduction["eligibility"] == "source_unresolved"
                 and improvement["disposition"] != "improvement_ready",
                 "Reviewed same-primary correction retains unresolved source eligibility")
        if not selected_language:
            result = module.summary(outcomes, reproduction, improvement)
    need(not result["errors"] and result["task_count"] == 1,
         "Invalid independent paper outcome summary")
    retained_temporal_summary = result if continuous is not None else None
    if continuous is not None:
        for handle in current_continuous["handles"]:
            for member in handle.members:
                need(member["path"] not in members, "Duplicate continuous task metadata member")
                members.add(member["path"])
        result = {"task_id": identifier, "task_count": 1, "errors": [],
                  "cells": [{"outcome": outcome, "condition": condition,
                             "eligibility": None, "endpoint_eligible": None,
                             "pairing_status": "uninstantiated", "condition_available": False,
                             "scientific_outcome": "unknown", "receipt": None, "result_status": "not_attempted"}
                            for outcome in ("reproduction", "improvement")
                            for condition in continuous_selection["conditions"]],
                  "paired_metadata_admitted": {"reproduction": False, "improvement": False},
                  "assurance": "Authenticated continuous measurement policy and source routes; no instantiated episode, submitted result, binary pass or scientific qualification."}
    return {"scoped_execution_modes": [meg_generic_classification_summary(meg_generic_descriptor)] if meg_generic_selected else None,
            "reve_reporting_selected": reve_reporting, "nuclr_reporting_selected": nuclr_reporting,
            "previous_row": prior, "previous_document": previous_document, "previous_pin": previous_pin,
            "improvement_contract": improvement, "improvement_contract_pin": improvement_pin,
            "retained_improvement_contract": retained_improvement,
            "retained_improvement_contract_pin": retained_improvement_pin,
            "primary_policy_revision": copy.deepcopy(_ROOT004_PINS["descriptor"]) if root004_scope else continuous_selection["revision"] if continuous else successor.descriptor_pin if successor else None,
            "primary_policy_provenance": {name: copy.deepcopy(_ROOT004_PINS[name]) for name in
                                          ("descriptor", "retained_improvement", "retained_reproduction", "retained_task", "retained_outcomes")} if root004_scope else current_continuous["provenance"] if continuous else successor_provenance,
            "candidate_interface": continuous_selection["candidate_interface"] if continuous else successor.candidate_interface if successor else None,
            "author_reproduction_routes": continuous_selection["author_reproduction_routes"] if continuous else successor.author_reproduction_routes if successor else None,
            "continuous_outcomes_v1": continuous_selection if current_continuous and current_continuous["version"] == 1 else None,
            "continuous_outcomes_v2": continuous_selection if current_continuous and current_continuous["version"] == 2 else None,
            "continuous_policy": continuous.snapshot()["documents"]["policy"] if continuous else None,
            "retained_temporal_summary": retained_temporal_summary,
            "reproduction_contract": reproduction,
            "outcomes": outcomes, "summary": result, "availability": "unavailable" if unavailable else "available",
            "primary_scope_correction": primary_correction,
            "scope_decision_pin": getattr(previous_rows, "scope_pin", None),
            "members": members}


def source_declaration_gap_context(row, document, previous_rows, read_pin, *, improvement_contract=None):
    """Authenticate missing declarations without disabling retained policy."""
    declared, identifier = row["paper_outcomes"], row["id"]
    prior, home = previous_rows[identifier], row["task_directory"]
    record_pin = getattr(previous_rows, "source_declaration_gap_pin", None)
    need(record_pin is not None and encode(declared["source_declaration_gap"]) == encode(record_pin),
         "Source declaration row and global record pins disagree")
    scopes = previous_rows.scope_decisions
    need(not scopes or identifier not in set(scopes["entries"]) | set(scopes.get("same_primary_corrections", {})),
         "Source declaration gaps cannot combine active scope corrections")
    module = declaration_gap_module()
    handle = module.authenticate(record_pin, prior, declared["previous_specification"], read_pin,
                                 improvement_contract=improvement_contract)
    captured = handle.snapshot()
    previous_document, improvement = captured["previous_task"], captured["improvement_contract"]
    errors = engine().improvement.contract_validate(improvement, task_id=identifier)
    need(not errors, "Invalid retained source declaration improvement: " + "; ".join(errors))
    projected = module.project(project_task(previous_document, prior, improvement), handle)
    expected = pin(home + "/task.json", encode(projected))
    need(encode(document) == encode(projected) and encode(row.get("specification")) == encode(expected),
         "Current paper definition differs from the deterministic source declaration projection")
    improvement_pin = {key: captured["entry"]["retained_improvement"][key] for key in ("path", "bytes", "sha256")}
    summary = module.public_summary(handle)
    return {"previous_row": prior, "previous_document": previous_document,
            "previous_pin": captured["previous_specification"],
            "improvement_contract": improvement, "improvement_contract_pin": improvement_pin,
            "retained_improvement_contract": improvement, "retained_improvement_contract_pin": improvement_pin,
            "primary_policy_revision": None, "primary_policy_provenance": None,
            "candidate_interface": None, "author_reproduction_routes": None,
            "reproduction_contract": None, "outcomes": None, "summary": summary,
            "availability": "source_declaration_unavailable", "source_declaration_gap": summary,
            "primary_scope_correction": None, "scope_decision_pin": getattr(previous_rows, "scope_pin", None),
            "members": {captured["previous_specification"]["path"]}}


def public_primary_scope_correction(entry, scope_pin, task_id):
    """Project an authenticated scope entry without adding scientific claims."""
    result = {
        "disposition": "same_primary_unqualified", "primary_goal": entry["primary_goal"],
        "primary_scope": entry["primary_scope"],
        "remaining_source_limits": copy.deepcopy(entry["remaining_source_limits"]),
        "retained_scope_notes": entry.get("retained_secondary_scope"),
        "retained_source_roles": copy.deepcopy(entry.get("retained_source_roles")),
        "root_scope_decision": {"path": SCOPE_PATH, "raw_sha256": scope_pin["sha256"],
                                "task_entry_id": task_id},
        "scientific_outcome": "unknown",
    }
    if entry["disposition"] == "explicit_primary_selection":
        result["source_disposition"] = "explicit_primary_selection"
    return result


def public_summary(row, bound):
    """Expose declarations without treating metadata consistency as performance."""
    binding = row["paper_outcomes"]
    continuous_key = "continuous_outcomes_v2" if bound.get("continuous_outcomes_v2") is not None else "continuous_outcomes_v1"
    if bound.get(continuous_key) is not None:
        continuous = bound[continuous_key]
        return {"schema_version": VERSION, "objective": OBJECTIVE, "availability": "available",
                "previous_specification": copy.deepcopy(binding["previous_specification"]),
                "reproduction_contract": copy.deepcopy(continuous["policy"]),
                "improvement_contract": copy.deepcopy(continuous["policy"]), "outcomes": None,
                "reproduction_eligibility": None, "reproduction_blocking_issues": [],
                "improvement_disposition": "continuous_measurement",
                "cells": copy.deepcopy(bound["summary"]["cells"]),
                "scientific_outcomes": {"reproduction": "unknown", "improvement": "unknown"},
                "assurance": bound["summary"]["assurance"],
                "retained_improvement_contract": copy.deepcopy(bound["retained_improvement_contract_pin"]),
                "retained_improvement_role": "retained_pre_outcomes_policy",
                "primary_policy_revision": copy.deepcopy(bound["primary_policy_revision"]),
                "primary_policy_provenance": copy.deepcopy(bound["primary_policy_provenance"]),
                "candidate_interface": copy.deepcopy(bound["candidate_interface"]),
                "author_reproduction_routes": copy.deepcopy(bound["author_reproduction_routes"]),
                continuous_key: copy.deepcopy(continuous)}
    if bound["availability"] == "source_declaration_unavailable":
        gap = bound["source_declaration_gap"]
        return {"schema_version": VERSION, "objective": OBJECTIVE,
                "availability": gap["availability"],
                "previous_specification": copy.deepcopy(gap["previous_specification"]),
                "original_task": copy.deepcopy(gap["original_task"]),
                "reproduction_contract": None,
                "improvement_contract": copy.deepcopy(bound["improvement_contract_pin"]), "outcomes": None,
                "source_declaration_gap": copy.deepcopy(gap["record"]),
                "reason_code": gap["reason_code"], "reason": gap["reason"], "source_relation": gap["source_relation"],
                "remaining_source_limits": copy.deepcopy(gap["remaining_source_limits"]),
                "reproduction_eligibility": None, "reproduction_blocking_issues": [],
                "scientific_ineligibility_inferred": False,
                "improvement_disposition": gap["improvement_disposition"],
                "improvement_unavailable_by_reproduction_dependency": False,
                "paired_outcome_admission": "unavailable", "cells": copy.deepcopy(gap["cells"]),
                "scientific_outcomes": copy.deepcopy(gap["scientific_outcomes"]), "assurance": gap["assurance"]}
    reproduction = bound["reproduction_contract"]
    result = {"schema_version": VERSION, "objective": OBJECTIVE,
            "availability": bound["availability"],
            "previous_specification": copy.deepcopy(binding["previous_specification"]),
            "reproduction_contract": copy.deepcopy(binding.get("reproduction_contract")),
            "improvement_contract": copy.deepcopy(bound["improvement_contract_pin"]),
            "outcomes": copy.deepcopy(binding["outcomes"]),
            "reproduction_eligibility": reproduction["eligibility"] if reproduction is not None else None,
            "reproduction_blocking_issues": copy.deepcopy(reproduction["blocking_issues"]) if reproduction is not None else [],
            "cells": copy.deepcopy(bound["summary"]["cells"]),
            "scientific_outcomes": {"reproduction": "unknown", "improvement": "unknown"},
            "assurance": bound["summary"]["assurance"]}
    if bound.get("primary_policy_revision") is not None:
        result.update({
            "improvement_disposition": bound["improvement_contract"]["disposition"],
            "retained_improvement_contract": copy.deepcopy(bound["retained_improvement_contract_pin"]),
            "retained_improvement_role": "retained_pre_outcomes_policy",
            "primary_policy_revision": copy.deepcopy(bound["primary_policy_revision"]),
            "primary_policy_provenance": copy.deepcopy(bound["primary_policy_provenance"]),
            "candidate_interface": copy.deepcopy(bound["candidate_interface"]),
            "author_reproduction_routes": copy.deepcopy(bound["author_reproduction_routes"]),
        })
    if bound.get("scoped_execution_modes") is not None:
        result["scoped_execution_modes"] = copy.deepcopy(bound["scoped_execution_modes"])
    if bound["availability"] == "unavailable":
        for field in ("reason_code", "reason", "primary_scope", "retained_secondary_improvement", "root_scope_decision"):
            result[field] = copy.deepcopy(bound["outcomes"][field])
    correction = bound.get("primary_scope_correction")
    if correction is not None:
        result["primary_scope_correction"] = public_primary_scope_correction(
            correction, bound["scope_decision_pin"], row["id"])
    return result
