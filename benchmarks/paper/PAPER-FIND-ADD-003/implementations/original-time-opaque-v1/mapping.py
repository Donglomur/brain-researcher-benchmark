"""Operator-only identity mapping for the original seven-bin time endpoint.

This is a source component, not an execution boundary. In particular, it does
not prevent a candidate from seeing held-out samples as training observations
in another LOO fold. A qualified executor must isolate those folds separately.
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
from pathlib import Path

SCORER_SHA256 = "c090bf302bb18e4a685571388da42662212f50bffdd66c5c7a352746cd2614fa"
PUBLIC_SCHEMA = "h_original_time_opaque_query_v1"
RESPONSE_SCHEMA = "h_original_time_opaque_response_v1"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def content_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def exact_fields(value, names, message):
    require(type(value) is dict and set(value) == set(names), message)


def load_reference(path=None):
    """Authenticate the existing source scorer before executing its definitions."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "original-time-v1" / "score.py"
    path = Path(path)
    with path.open("rb") as handle:
        raw = handle.read(11462)
    require(len(raw) == 11461 and hashlib.sha256(raw).hexdigest() == SCORER_SHA256,
            "Original-time scorer identity changed; independent review required")
    spec = importlib.util.spec_from_file_location("_h_original_time_pinned_score", path)
    require(spec is not None and spec.loader is not None, "Scorer import unavailable")
    module = importlib.util.module_from_spec(spec)
    # Execute the very bytes authenticated above, avoiding a second mutable read.
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


class IdentityPlan:
    """Private full-support plan; only public_fold() is participant-visible.

    The operator supplies a fresh cryptographically random 32-byte secret for
    each independently frozen candidate run. The component cannot establish
    the secret's entropy, source-data authenticity, or private custody.
    """

    def __init__(self, roster, secret):
        require(type(secret) is bytes and len(secret) == 32,
                "An operator-private 32-byte mapping secret is required")
        self._score = load_reference()
        self._roster = json.loads(canonical_bytes(roster))
        self._sessions = self._score.validate_roster(self._roster)
        self._roster_hash = self._score.canonical_hash(self._roster)
        self._folds = {}
        self._source_to_fold = {}
        used = set()

        def token(domain, source):
            result = domain + hmac.new(secret, canonical_bytes(
                ["PAPER-FIND-ADD-003/original-time-opaque/v1", domain, source]),
                hashlib.sha256).hexdigest()
            require(result not in used, "Opaque identity collision")
            used.add(result)
            return result

        for panel in self._score.panel_keys():
            animal, day, cue, control = panel
            for trial in self._sessions[(animal, day)][cue]:
                source = [*panel, trial]
                fold_id = token("f_", source)
                query_to_bin = {token("q_", [*source, actual]): actual
                                for actual in range(1, 8)}
                self._folds[fold_id] = (panel, trial, query_to_bin)
                self._source_to_fold[(*panel, trial)] = fold_id

    def operator_fold_ids(self):
        """Operator dispatch order; never provide a cross-fold data bundle."""
        return tuple(sorted(self._folds))

    def _lookup(self, fold_id):
        require(type(fold_id) is str and fold_id in self._folds,
                "Unknown opaque fold identity")
        return self._folds[fold_id]

    def public_fold(self, fold_id):
        """Seven opaque query IDs in key-dependent order; no signal data joined."""
        _, _, query_to_bin = self._lookup(fold_id)
        return {"schema": PUBLIC_SCHEMA, "fold_id": fold_id,
                "queries": [{"query_id": query_id} for query_id in sorted(query_to_bin)]}

    def operator_binding(self, fold_id):
        """PRIVATE inverse map for later array joining and scorer restoration."""
        panel, trial, query_to_bin = self._lookup(fold_id)
        return {"animal": panel[0], "day": panel[1], "cue": panel[2],
                "control": panel[3], "trial_index": trial,
                "queries": [{"query_id": query_id, "actual_bin": query_to_bin[query_id]}
                            for query_id in sorted(query_to_bin)]}


class Collector:
    """Operator-owned first-final fold collection; never sends score feedback.

    submit(fold_id, response) consumes the known fold even if the response is
    malformed. The independent operator supplies fold_id, not the candidate.
    A malformed or failed fold cannot be retried in this collector.
    """

    def __init__(self, plan):
        require(type(plan) is IdentityPlan, "A private original-time plan is required")
        self._plan = plan
        self._received = {}
        self._finished = None

    def _claim(self, fold_id):
        require(self._finished is None, "Collection already finalized")
        binding = self._plan._lookup(fold_id)
        require(fold_id not in self._received, "Fold already has a final disposition")
        self._received[fold_id] = {"status": "failed", "reason": "Malformed participant response"}
        return binding

    def submit(self, fold_id, response):
        _, _, query_to_bin = self._claim(fold_id)
        exact_fields(response, ("schema", "fold_id", "packet_sha256", "predictions"),
                     "Exact opaque response fields required")
        require(response["schema"] == RESPONSE_SCHEMA and response["fold_id"] == fold_id,
                "Response schema or fold identity mismatch")
        expected_hash = content_hash(self._plan.public_fold(fold_id))
        require(type(response["packet_sha256"]) is str and len(response["packet_sha256"]) == 64 and
                all(c in "0123456789abcdef" for c in response["packet_sha256"]) and
                hmac.compare_digest(response["packet_sha256"], expected_hash),
                "Response does not bind the exact public packet")
        rows = response["predictions"]
        require(type(rows) is list and len(rows) == 7,
                "Exactly seven opaque query predictions required")
        received = {}
        for row in rows:
            exact_fields(row, ("query_id", "predicted_bin"), "Exact prediction fields required")
            query_id, predicted = row["query_id"], row["predicted_bin"]
            require(type(query_id) is str and query_id in query_to_bin and query_id not in received,
                    "Unknown or duplicate query identity")
            require(type(predicted) is int and 1 <= predicted <= 7,
                    "Predicted bins must be integers 1 through 7")
            received[query_id] = predicted
        require(set(received) == set(query_to_bin), "Complete seven-bin support required")
        restored = [None] * 7
        for query_id, actual in query_to_bin.items():
            restored[actual - 1] = received[query_id]
        self._received[fold_id] = {"status": "finite", "predicted_bins": restored}

    def fail(self, fold_id, reason):
        """Seal an operator-observed timeout/failure without inventing predictions."""
        self._claim(fold_id)
        require(type(reason) is str and 0 < len(reason.strip()) <= 1024,
                "A bounded nonempty failure reason is required")
        self._received[fold_id] = {"status": "failed", "reason": reason}

    def finish(self):
        """Restore every original panel/trial, retaining missing trials explicitly."""
        if self._finished is None:
            panels = []
            for panel in self._plan._score.panel_keys():
                animal, day, cue, control = panel
                trials = []
                for trial in self._plan._sessions[(animal, day)][cue]:
                    fold_id = self._plan._source_to_fold[(*panel, trial)]
                    record = self._received.get(fold_id, {
                        "status": "unstarted", "reason": "No final participant response"})
                    trials.append({"trial_index": trial, **record})
                panels.append({"animal": animal, "day": day, "cue": cue,
                               "control": control, "trials": trials})
            self._finished = {"schema": "h_original_time_predictions_v1",
                              "roster_sha256": self._plan._roster_hash, "panels": panels}
        # A caller cannot alter the retained final dispositions through a result.
        return json.loads(canonical_bytes(self._finished))
