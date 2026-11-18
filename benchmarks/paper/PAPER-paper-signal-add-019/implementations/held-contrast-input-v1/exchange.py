"""Task-specific candidate fitting packets and protected Table 1 output join.

Trusted operator component only. A fresh participant context per packet and
filesystem/process isolation must be provided externally. No fitting occurs.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re

_path = Path(__file__).resolve().parents[1] / "author-law-production-v1" / "producer.py"
_raw = _path.read_bytes()
if len(_raw) != 12238 or hashlib.sha256(_raw).hexdigest() != "6a9e1afd076ca1ffc9931a49f28a488a34ba53168f6fba7ff41b826d3fa4317e":
    raise ValueError("accepted author-law input plan changed")
_spec = importlib.util.spec_from_file_location("decision_times_author_input_plan", _path)
source = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(source)
panel = source.panel
require = panel.require


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def fingerprint(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def detached(value):
    return json.loads(encoded(value))


def finite(value, label):
    require(type(value) in (int, float) and math.isfinite(value), label + ": finite number required")
    return float(value)


def parse_response(raw):
    """Strict parsing for a future transport: no duplicate keys or NaN tokens."""
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate response JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ValueError("nonfinite response JSON token")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


def _case_jobs(prepared, target, condition, mode, omitted):
    """Use all three source law plans, requiring identical fitting operands."""
    selected, laws = {}, {}
    for job in source.fit_jobs({(target, condition): prepared[target, condition]}):
        if job["mode"] != mode or job["omitted_contrast_percent"] != omitted:
            continue
        require(job["law"] in panel.AUTHOR_MODELS, "unknown source law")
        person = job["participant"]
        require(job["law"] not in laws.setdefault(person, set()), "duplicate source law input plan")
        laws[person].add(job["law"])
        # The source digest includes the law label; both label and digest are
        # removed only after the original digest itself has been checked.
        unsigned = {k: v for k, v in job.items() if k != "fit_input_sha256"}
        require(source.digest(unsigned) == job["fit_input_sha256"], "source fit plan digest mismatch")
        operands = {k: v for k, v in unsigned.items() if k != "law"}
        if person in selected:
            require(encoded(operands) == encoded(selected[person]), "source laws disagree on candidate fit inputs")
        else:
            selected[person] = operands
    expected = prepared[target, condition]["participants"]
    require(set(selected) == set(expected) and all(laws[p] == set(panel.AUTHOR_MODELS) for p in expected),
            "incomplete source law/participant input plans")
    return [selected[p] for p in expected]


class OperatorExchange:
    """One source-defined numeric packet and one complete response at a time.

    This object and its bindings/targets belong to the trusted operator. Only
    ``next_packet`` output may be delivered to a candidate. The complete held
    bank must be accepted and sealed before full-data fitting inputs exist.
    This API ordering is not OS isolation or independent chronology evidence.
    """
    def __init__(self, targets, *, run_id, method_id, access_condition, predict_accuracy=False):
        require(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", run_id),
                "bounded opaque run ID required")
        require(isinstance(method_id, str) and 0 < len(method_id) <= 256 and method_id.strip(),
                "frozen method ID required")
        require(access_condition in {"paper_data", "paper_data_author_code"}, "unknown access condition")
        require(type(predict_accuracy) is bool, "predict_accuracy must be boolean")
        self._targets = detached(targets)
        self._prepared = panel.prepare(self._targets)
        self._target_sha = panel.target_digest(self._targets)
        self._run = run_id
        self._method = method_id
        self._access = access_condition
        self._accuracy = predict_accuracy
        self._held_cases = [(t, c, x) for (t, c), item in self._prepared.items() for x in item["contrasts"]]
        self._full_cases = [(t, c, None) for t, c in self._prepared]
        self._phase, self._index = "held_out", 0
        self._pending = None
        self._held, self._full, self._receipts = [], [], []
        self._seal = self._finished = None

    def next_packet(self):
        """Return a detached public packet; repeated reads do not advance it."""
        require(self._phase in {"held_out", "full_data"}, "exchange is finished")
        if self._pending is not None:
            return detached(self._pending["packet"])
        cases = self._held_cases if self._phase == "held_out" else self._full_cases
        require(self._index < len(cases), "seal held predictions first" if self._phase == "held_out" else "all full-data packets answered")
        target, condition, omitted = cases[self._index]
        item = self._prepared[target, condition]
        jobs = _case_jobs(self._prepared, target, condition, self._phase, omitted)
        packet = dict(schema="decision-times-fitting-packet-v1", task_id=panel.legacy.TASK,
            run_id=self._run, method_id=self._method, access_condition=self._access,
            phase=self._phase, case_id=f"{self._phase}-{self._index:04d}",
            target=target, condition=condition,
            units={"contrast": "fraction", "latency": "seconds", "accuracy": "binary_correct"},
            predict_accuracy=self._accuracy if self._phase == "full_data" else False,
            participants=[])
        if self._phase == "full_data":
            require(self._seal is not None, "held predictions have not been sealed")
            packet["held_prediction_commitment"] = self._seal["sha256"]
        rows = {(r["participant"], r["epoch"]): r for r in item["rows"]}
        aliases, queries = [], []
        for pi, job in enumerate(jobs):
            person_id = f"person-{pi:03d}"
            fitting, trial_aliases = [], []
            for ti, (key, x, y) in enumerate(zip(job["fit_trial_keys"], job["contrast_fraction"], job["latency_seconds"])):
                require(tuple(key) in rows, "fit trial missing from original B/H source population")
                original = rows[tuple(key)]
                require(original["participant"] == job["participant"]
                        and original["contrast_percent"] / 100 == x
                        and original["values"][target] / 1000 == y,
                        "source fitting operands disagree with original trial join")
                trial_id = f"trial-{ti:06d}"
                fitting.append(dict(trial_id=trial_id, contrast_fraction=x, latency_seconds=y,
                                    accuracy=int(original["correct"])))
                trial_aliases.append(dict(trial_id=trial_id, original_key=list(key)))
            require(len(fitting) == len(job["fit_trial_keys"]) == len(job["contrast_fraction"]) == len(job["latency_seconds"]),
                    "source fitting vector lengths differ")
            prediction_contrasts = [omitted] if self._phase == "held_out" else job["prediction_contrasts_percent"]
            public_queries = []
            for qi, contrast in enumerate(prediction_contrasts):
                prediction_id = f"{person_id}-query-{qi:03d}"
                public_queries.append(dict(prediction_id=prediction_id, contrast_fraction=contrast / 100))
                queries.append(dict(prediction_id=prediction_id, target=target, condition=condition,
                    participant=job["participant"], contrast_percent=contrast,
                    fit_contrasts_percent=list(job["fit_contrasts_percent"])))
            packet["participants"].append(dict(participant_id=person_id, fitting_trials=fitting, queries=public_queries))
            aliases.append(dict(participant_id=person_id, original_participant=job["participant"], trial_aliases=trial_aliases))
        binding = dict(schema="decision-times-fitting-operator-binding-v1", operator_only=True,
            run_id=self._run, method_id=self._method, access_condition=self._access,
            targets_sha256=self._target_sha, case_id=packet["case_id"], phase=self._phase,
            packet_sha256=fingerprint(packet), participant_aliases=aliases, queries=queries)
        self._pending = dict(packet=packet, binding=binding)
        return detached(packet)

    def operator_binding(self):
        """Private reversible identity map; never include this in participant I/O."""
        require(self._pending is not None, "no pending packet")
        return detached(self._pending["binding"])

    def accept_response(self, response):
        """Validate complete response before mutating state; first answer is final."""
        require(self._pending is not None and self._phase in {"held_out", "full_data"}, "no pending response")
        require(isinstance(response, dict) and set(response) == {"schema", "case_id", "packet_sha256", "predictions"},
                "exact response fields required")
        binding = self._pending["binding"]
        require(response["schema"] == "decision-times-fitting-response-v1"
                and response["case_id"] == binding["case_id"]
                and response["packet_sha256"] == binding["packet_sha256"], "response packet identity mismatch")
        require(isinstance(response["predictions"], list), "predictions must be a list")
        expected = {q["prediction_id"]: q for q in binding["queries"]}
        observed = {}
        accuracy = self._phase == "full_data" and self._accuracy
        fields = {"prediction_id", "latency_seconds"} | ({"probability_correct"} if accuracy else set())
        for row in response["predictions"]:
            require(isinstance(row, dict) and set(row) == fields, "exact prediction fields required")
            key = row["prediction_id"]
            require(isinstance(key, str) and key in expected and key not in observed, "unknown or duplicate prediction identity")
            y = finite(row["latency_seconds"], "latency_seconds")
            output = {k: v for k, v in expected[key].items() if k != "prediction_id"}
            output["latency_ms"] = finite(y * 1000, "latency_ms")
            if accuracy:
                prob = finite(row["probability_correct"], "probability_correct")
                require(0 <= prob <= 1, "probability outside [0,1]")
                output["probability_correct"] = prob
            observed[key] = output
        require(set(observed) == set(expected), "incomplete response prediction coverage")
        accepted = [observed[q["prediction_id"]] for q in binding["queries"]]
        receipt = dict(case_id=binding["case_id"], phase=self._phase,
            packet_sha256=binding["packet_sha256"], operator_binding_sha256=fingerprint(binding),
            response_sha256=fingerprint(response), predictions=len(accepted))
        (self._held if self._phase == "held_out" else self._full).extend(accepted)
        self._receipts.append(receipt)
        self._index += 1
        self._pending = None
        return detached(receipt)

    def seal_held_predictions(self):
        require(self._phase == "held_out" and self._index == len(self._held_cases)
                and self._pending is None, "complete held responses required before seal")
        body = dict(schema="decision-times-held-prediction-commitment-v1", operator_only=True,
            run_id=self._run, method_id=self._method, access_condition=self._access,
            targets_sha256=self._target_sha, held_out_sha256=fingerprint(self._held),
            completed_cases=len(self._held_cases), completed_predictions=len(self._held),
            receipts=detached(self._receipts))
        self._seal = dict(body=body, sha256=fingerprint(body))
        self._phase, self._index = "full_data", 0
        return detached(self._seal)

    def finish(self):
        if self._finished is not None:
            return detached(self._finished)
        require(self._phase == "full_data" and self._index == len(self._full_cases)
                and self._pending is None, "complete full-data companion responses required")
        method = dict(method_id=self._method, targets_sha256=self._target_sha,
            latency_selection="all_responded", time_unit="ms", contrast_unit="percent",
            held_out=detached(self._held), full_data=detached(self._full))
        panel._predictions(method, self._prepared, "held_out")
        panel._predictions(method, self._prepared, "full_data", self._accuracy)
        require(fingerprint(self._held) == self._seal["body"]["held_out_sha256"], "sealed held predictions changed")
        self._finished = dict(schema="decision-times-candidate-input-join-v1", operator_only=True,
            task_id=panel.legacy.TASK, access_condition=self._access,
            candidate=method, held_commitment=detached(self._seal), receipts=detached(self._receipts),
            qualification="numeric_input_export_and_response_join_only", readiness_promoted=False,
            paper_win=None, scientific_qualification=False)
        self._phase = "finished"
        return detached(self._finished)
