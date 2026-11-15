"""APCx prepared-output adapter and owner-only participant construction.

No data access, model execution or work on import. The active authentic primary
remains held. Invented fixtures exercise the same projection and scoring kernels
without turning released quantity or conditional pulse reconstructions into truth.
A projection is not an OS sandbox; no candidate process is launched here.
"""
import hashlib
import hmac
import json
import math
import re

import census_core

CURRENT_CONTRACT_SHA256 = "31deec39ae1c79f26f3c3a5ce36f809c7feede0be07ee328f894063e814ec93e"
ACCEPTED_ROWS_SHA256 = "125ba3aa32a0c7a5b8528eaeb6bef8e2e679526e49213fc1c685ad6264a9f333"
ACCEPTED_REVIEW_SHA256 = "84738a9f7479ea0a1d43859b0075fff97720ff15eff22527287a507e478849a4"
FULL_SCOPE = {"rows": 95072, "trials": 10831, "sessions": 43, "session_unit_pairs": 383}
HOLDS = (
    "EXTERNAL_GOOD_CELLS_BST_ROSTER_AND_ALL_QC_LINEAGE_UNVERIFIED",
    "ORIGINAL_TRIAL_IDS_EXCLUSIONS_AND_CHRONOLOGY_UNAVAILABLE",
    "PHYSICAL_VALVE_DELIVERY_EVENT_LOG_AND_OVERLAP_SEMANTICS_UNAVAILABLE",
    "COMPILER_TO_DEPOSITED_FILE_EXECUTION_LINEAGE_UNPROVEN",
    "SOURCE_ZERO_TICK_VS_PADDING_AND_FIXED_SPIKE_CAP_PROVENANCE",
    "AVAILABLE_RELEASE_NOT_FULL_THREE_ANIMAL_42_SESSION_COUNT_SCOPE",
    "RELEASED_ROW_DISPOSITIONS_REQUIRE_SOURCE_RECONCILIATION",
)
CONDITIONS = ("matched", "full_calibration")
DOCUMENTATION = {
    "schema": "apcx-common-participant-document-v1",
    "endpoint": "Physical odor-valve event count over [0,5) seconds; no surrogate substitution.",
    "neural_observation": "[0.5,5) seconds; first 500 ms are unobserved, not zero-filled.",
    "signal": "90 half-open 50 ms bins by every admitted unit; entries are observed spike counts.",
    "target_boundary": "Physical event counts <=8 low; >=9 high.",
    "split": "Authenticated chronology: floor(0.60*n) calibration, floor(0.20*n) development, remainder protected.",
    "matched_support": "First 16 calibration and first 8 development trials by authenticated chronology.",
    "full_support": "All calibration/development trials; separate evidence-access condition.",
    "queries": "All protected trials; opaque query ordering does not disclose source chronology.",
    "inputs_excluded": "Animal/date/original IDs, reward, choice, correctness, commands, pulse timings, breathing, sniff histograms, target-derived masks and owner diagnostic fields.",
    "scoring": "Complete submission required; negative finite count predictions clipped to zero; animal-macro RMSE primary, no upper clip.",
    "limits": "Three recorded animals; historical public labels and historical QC; no broad population or contamination-free claim.",
    "tools": "Approved train-only algorithms require separate isolated execution; this source launches no candidate.",
}


class ScientificHold(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def finite(x):
    try:
        return type(x) in (int, float) and math.isfinite(x)
    except (OverflowError, ValueError):
        return False


def exact_keys(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError("exact closed schema")


def integer(value, lower=0):
    if type(value) is not int or not lower <= value < 2**31:
        raise ValueError("bounded exact integer")
    return value


def nonempty(value):
    if type(value) is not str or not value or len(value.encode()) > 256:
        raise ValueError("bounded nonempty identity")
    return value


def signal_matrix(matrix):
    if type(matrix) is not list or not 1 <= len(matrix) <= 16384:
        raise ValueError("all-unit matrix required")
    for channel in matrix:
        if type(channel) is not list or len(channel) != 90:
            raise ValueError("all 90 observed bins required")
        for count in channel:
            integer(count)
    return matrix


def current_primary_status():
    return {
        "status": "HELD_AUTHENTIC_PHYSICAL_COUNT_PRIMARY",
        "contract_sha256": CURRENT_CONTRACT_SHA256,
        "accepted_preparation_review_sha256": ACCEPTED_REVIEW_SHA256,
        "all_available_scope_preserved": dict(FULL_SCOPE),
        "remaining_holds": list(HOLDS),
        "unresolved_trials_preserved": 900,
        "observed_release_label_is_physical_truth": False,
        "conditional_reconstruction_is_physical_truth": False,
        "authentic_participant_export_enabled": False,
        "scientific_qualification": False,
        "benchmark_count_delta": 0,
    }


def build_authentic_packet(*args, **kwargs):
    """No caller-supplied ready=True, alternate label or success-only route."""
    raise ScientificHold("Authentic physical-count primary held: " + ";".join(HOLDS))


def assemble_prepared_trials(rows, expected_scope):
    """Consume every accepted prepared ROWS record; produce owner-only trials.

    Caller must authenticate the complete selected prepared file and accepted
    review before invoking this pure adapter. This does not independently decode
    original spikes or certify provenance. No diagnostic/legacy failure is filtered.
    """
    exact_keys(expected_scope, FULL_SCOPE)
    for value in expected_scope.values():
        integer(value, 1)
    trials = {}
    session_units = {}
    seen = 0
    for row in rows:
        if type(row) is not dict or row.get("source_row_zero_based") != seen:
            raise ValueError("complete source-row order")
        if type(row["source_row_zero_based"]) is not int:
            raise ValueError("exact source-row index")
        seen += 1
        if seen > expected_scope["rows"]:
            raise ValueError("whole row scope exceeded")
        identity = row["identity_owner_only"]
        exact_keys(identity, ("Animal", "Session", "Date", "Trial", "Cell"))
        animal, session, date = [nonempty(identity[k]) for k in ("Animal", "Session", "Date")]
        trial, cell = integer(identity["Trial"]), integer(identity["Cell"])
        if row.get("candidate_packet") is not False or row.get("scientific_primary_admitted") is not False:
            raise ValueError("preparation must retain scientific holds")
        labels = row["labels_owner_only"]
        exact_keys(labels, ("Total_pulse", "High_trial", "High_choice", "Correct"))
        integer(labels["Total_pulse"])
        if any(type(labels[k]) is not int or labels[k] not in (0, 1)
               for k in ("High_trial", "High_choice", "Correct")):
            raise ValueError("released label domain")
        spikes = row["spikes_observed_window"]
        if (spikes.get("status") != "OBSERVED_WINDOW_PROJECTION_ONLY"
                or spikes.get("physical_sampling_window") != [0.5, 5.0]
                or spikes.get("first_500ms_observed") is not False
                or spikes.get("unit") != "spike count"
                or spikes.get("explicit_half_open_bin_convention") is not True):
            raise ValueError("fixed observed-window count semantics")
        counts = spikes.get("bins_50ms")
        signal_matrix([counts])
        if sum(counts) != spikes.get("observed_spikes") or spikes.get("violations") != []:
            raise ValueError("complete spike projection unsupported; no row drop")
        flags = row.get("violations")
        if type(flags) is not list or any(type(x) is not str for x in flags):
            raise ValueError("all old flags retained")
        reference = row["command_multiplicity_reference"]
        if (type(reference) is not dict or set(reference)!={"schema","kind","groupable","released_trial_key","diagnostic_sha256"}
                or reference.get("schema") != "apcx-shared-command-reference-v1"
                or reference.get("kind") != "row" or reference.get("groupable") is not True
                or type(reference.get("diagnostic_sha256")) is not str
                or not re.fullmatch("[0-9a-f]{64}",reference["diagnostic_sha256"])
                or reference.get("released_trial_key") != census_core.fingerprint({"animal":animal,"session":session,"released_trial":trial})["sha256"]
                or reference.get("diagnostic_sha256") != row.get("command_multiplicity_digest")):
            raise ValueError("accepted shared diagnostic reference")
        key = (animal, session, trial)
        group = trials.setdefault(key, {
            "animal": animal, "session": session, "date": date, "released_trial": trial,
            "observed_released_labels_owner_only": dict(labels), "units": {},
            "source_rows": [], "old_flags_by_unit": {},
            "diagnostic_reference_owner_only": dict(reference),
            "shared_fields_sha256_owner_only": row["trial_shared_fields_sha256"],
            "physical_count": None, "original_chronology": None,
            "all_qc_roster_authenticated": False, "scientific_holds": list(HOLDS),
        })
        if (group["observed_released_labels_owner_only"] != labels or group["date"] != date
                or group["shared_fields_sha256_owner_only"] != row["trial_shared_fields_sha256"]
                or group["diagnostic_reference_owner_only"] != reference):
            raise ValueError("whole trial shared-metadata conflict")
        if cell in group["units"]:
            raise ValueError("duplicate unit row; no merge")
        group["units"][cell] = list(counts)
        group["source_rows"].append(row["source_row_zero_based"])
        group["old_flags_by_unit"][cell] = list(flags)
        session_units.setdefault((animal, session), set()).add(cell)
    observed = {"rows": seen, "trials": len(trials), "sessions": len(session_units),
                "session_unit_pairs": sum(map(len, session_units.values()))}
    if observed != expected_scope:
        raise ValueError("complete available-scope mismatch")
    owner_trials = []
    for key, trial in sorted(trials.items()):
        roster = sorted(session_units[key[:2]])
        if set(trial["units"]) != set(roster):
            raise ValueError("incomplete released trial-unit support; no subset")
        trial["released_unit_ids_owner_only"] = roster
        trial["spikes_by_unit_90_bins"] = [trial["units"].pop(unit) for unit in roster]
        del trial["units"]
        owner_trials.append(trial)
    return {"schema": "apcx-owner-prepared-trials-v1", "observed_scope": observed,
            "trials": owner_trials, "candidate_export": False, "physical_truth_authenticated": False,
            "original_chronology_authenticated": False, "all_qc_roster_authenticated": False,
            "remaining_holds": list(HOLDS)}


def features(matrix, view="all_50ms", window=None):
    """Fixed features only; no fitted scaling, unit selection or added evidence."""
    signal_matrix(matrix)
    if view == "all_50ms":
        if window is not None: raise ValueError("unexpected window")
        return [v for channel in matrix for v in channel]
    if view == "total":
        if window is not None: raise ValueError("unexpected window")
        return [sum(channel) for channel in matrix]
    if view == "all_500ms":
        if window is not None: raise ValueError("unexpected window")
        return [sum(channel[10*i:10*(i+1)]) for channel in matrix for i in range(9)]
    if view not in ("independent_500ms", "cumulative_500ms") or type(window) is not int or not 0 <= window < 9:
        raise ValueError("closed observed-window contrast")
    start = 10*window if view == "independent_500ms" else 0
    return [sum(channel[start:10*(window+1)]) for channel in matrix]


def opaque(secret, domain, identity):
    if type(secret) is not bytes or len(secret) != 32:
        raise ValueError("owner-only 256-bit pseudonym key")
    return hmac.new(secret, domain.encode() + b"\0" + canonical(identity), hashlib.sha256).hexdigest()


def audit_signal_sessions(session_payloads, condition):
    if condition not in CONDITIONS or type(session_payloads) is not list or not session_payloads:
        raise ValueError("complete nonempty public sessions and condition")
    seen = set(); session_ids = set()
    for s in session_payloads:
        exact_keys(s, ("session_id", "channel_ids", "calibration", "development", "queries"))
        sid = s["session_id"]
        if type(sid) is not str or not re.fullmatch("[0-9a-f]{64}", sid) or sid in session_ids:
            raise ValueError("unique opaque session")
        session_ids.add(sid)
        if len(set(s["channel_ids"])) != len(s["channel_ids"]) or any(
            type(x) is not str or not re.fullmatch("[0-9a-f]{64}", x) for x in s["channel_ids"]):
            raise ValueError("opaque channel basis")
        for split in ("calibration", "development", "queries"):
            for row in s[split]:
                exact_keys(row, ("case_id", "spikes") if split == "queries" else ("case_id", "spikes", "count", "high"))
                cid = row["case_id"]
                if type(cid) is not str or not re.fullmatch("[0-9a-f]{64}", cid) or cid in seen:
                    raise ValueError("unique opaque case")
                seen.add(cid);signal_matrix(row["spikes"])
                if len(row["spikes"]) != len(s["channel_ids"]): raise ValueError("all units retained")
                if split != "queries":
                    integer(row["count"])
                    if type(row["high"]) is not int or row["high"] != int(row["count"] >= 9):
                        raise ValueError("label-derived support category")
        if condition == "matched" and (len(s["calibration"]) != 16 or len(s["development"]) != 8):
            raise ValueError("exact matched support")
        if len(s["queries"]) < 10: raise ValueError("complete protected quota")
    return True

