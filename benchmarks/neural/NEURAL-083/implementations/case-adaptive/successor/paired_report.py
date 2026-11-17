"""Paired descriptive reporting around the unchanged captured OpenBMI scorer.

Trusted operator route only. Caller authenticates scorer source, admitted
execution and immutable input captures. No source import or target access is
performed at module import. The external_admission Boolean is a precondition,
not proof of execution, chronology, resource enforcement, or P0 semantics.
"""

import math

PANELS = ("frozen_program", "case_adaptive", "reference")
SETTINGS = ("target20", "transfer0", "target100", "other_session20")
ARMS = ("EEG", "CONTEXT", "PERMUTED_EEG")
PRIMARY = "target20/EEG/person_macro_session_macro_balanced_accuracy"


def _need(ok, message):
    if not ok:
        raise ValueError(message)


def _number(value, metric):
    _need(type(value) in (int, float), "Finite original numerical metric")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    _need(finite and value >= 0 and (metric != "balanced_accuracy" or value <= 1),
          "Original metric range")
    return value


def _people_scores(result, people):
    """Validate the small original descriptive outputs, not rescore trials."""
    _need(type(result) is dict and result.get("status") == "scored" and result.get("primary") == PRIMARY and
          result.get("biological_n") == 54, "Unchanged original primary and biological support")
    expected = {setting + "/" + arm for setting in SETTINGS for arm in ARMS}
    table = result.get("per_person")
    _need(type(table) is dict and set(table) == expected, "All original setting/arm person scores")
    normalized = {}
    for key in sorted(expected):
        rows = table[key]
        _need(type(rows) is list and len(rows) == 54, "All 54 people retained")
        mapped = {}
        for row in rows:
            _need(type(row) is dict and set(row) == {"person", "balanced_accuracy", "log_loss"},
                  "Original person metric fields")
            person = row["person"]
            _need(type(person) is str and person in people and person not in mapped, "Exact unique person join")
            mapped[person] = {m: _number(row[m], m) for m in ("balanced_accuracy", "log_loss")}
        _need(set(mapped) == people, "Complete person identity join")
        normalized[key] = mapped
    primary_mean = math.fsum(normalized["target20/EEG"][p]["balanced_accuracy"] for p in sorted(people)) / 54
    _need(abs(_number(result.get("primary_score"), "balanced_accuracy") - primary_mean) <= 1e-12,
          "Original primary agrees with all-person means")
    return normalized


def _contrast(rows, label):
    return {"definition": label, "per_person": rows,
            "balanced_accuracy_mean": math.fsum(row["balanced_accuracy"] for row in rows) / 54,
            "log_loss_improvement_mean": math.fsum(row["log_loss_improvement"] for row in rows) / 54,
            "biological_n": 54}


def compare(panel, bundles, load_targets, scorer, *, external_admission):
    """Admit all three complete panels before one protected target callback.

    ``scorer`` is the unchanged source-captured original module, providing admit
    and score. Its callback receives the same already loaded truth each time;
    the external protected loader is invoked only once. Any abstention preserves
    the whole-panel policy and prevents all protected target access. Original
    scores, references and their descriptive SE values are retained verbatim;
    no new interval, population inference or causal claim is generated here.
    """
    _need(external_admission is True, "Separate independent execution admission required")
    _need(type(bundles) is dict and set(bundles) == set(PANELS), "Exactly three complete panels required")
    abstained = {}
    for name in PANELS:
        _predictions, missing = scorer.admit(panel, bundles[name])
        abstained[name] = len(missing)
    # Even a panel with abstention does not short-circuit admission of the rest.
    if any(abstained.values()):
        return {"schema": "neural083_paired_comparison_v1", "status": "abstained",
                "private_callbacks": 0, "primary_score": None,
                "abstaining_conditions": abstained, "panel_outcomes_required": 1296,
                "scientific_qualified": False, "submission_ready": False}
    truth = load_targets()
    scores = {name: scorer.score(panel, bundles[name], lambda: truth) for name in PANELS}
    # Full input support was already admitted by the captured original scorer.
    people = {row["person"] for row in panel["cases"]}
    _need(len(people) == 54, "Full biological denominator")
    per = {name: _people_scores(scores[name], people) for name in PANELS}
    mode = {}
    for setting in SETTINGS:
        for arm in ARMS:
            key = setting + "/" + arm
            rows = []
            for person in sorted(people):
                frozen = per["frozen_program"][key][person]
                adaptive = per["case_adaptive"][key][person]
                rows.append({"person": person,
                             "balanced_accuracy": adaptive["balanced_accuracy"] - frozen["balanced_accuracy"],
                             "log_loss_improvement": frozen["log_loss"] - adaptive["log_loss"]})
            mode[key] = _contrast(rows, "adaptive minus frozen BA; frozen minus adaptive log loss")
    interaction = {}
    for setting in SETTINGS:
        eeg = {row["person"]: row for row in mode[setting + "/EEG"]["per_person"]}
        context = {row["person"]: row for row in mode[setting + "/CONTEXT"]["per_person"]}
        rows = [{"person": person,
                 "balanced_accuracy": eeg[person]["balanced_accuracy"] - context[person]["balanced_accuracy"],
                 "log_loss_improvement": eeg[person]["log_loss_improvement"] - context[person]["log_loss_improvement"]}
                for person in sorted(people)]
        interaction[setting] = _contrast(rows, "mode advantage on EEG minus mode advantage on separate CONTEXT arm")
    return {"schema": "neural083_paired_comparison_v1", "status": "scored", "private_callbacks": 1,
            "primary": PRIMARY,
            "primary_scores": {name: scores[name]["primary_score"] for name in PANELS},
            "original_scores": scores, "mode_advantage": mode, "mode_by_representation": interaction,
            "original_contrasts_preserved": True, "panel_outcomes_required": 1296,
            "unique_people": 54, "person_sessions": 108, "scientific_success": None,
            "scientific_qualified": False, "submission_ready": False,
            "conditional_eeg_contribution_established": False,
            "cue_independent_intention_established": False,
            "population_inference": False, "confidence_interval": None, "p_value": None,
            "interpretation": "Paired descriptive deployment-strategy and representation contrasts; equal ceilings do not prove equal actual compute."}
