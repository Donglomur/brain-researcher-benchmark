"""Protected grading of complete NEURAL-059 direct probability captures.

Trusted operator code only: preparation and output contain held targets.
No participant invocation, model inference or scientific qualification occurs.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
DELIVERY_SHA256 = "b0bb99a13d380c022442f7fcf6152c96b9178cf46c006a0ef9b71d034b7cd99e"


class GradingError(ValueError):
    """Stable error code without protected operand values."""


def need(condition, code):
    if not condition:
        raise GradingError(code)


def dependencies():
    path = HERE.parent / "direct-probability-v1/delivery.py"
    body = path.read_bytes()
    need(hashlib.sha256(body).hexdigest() == DELIVERY_SHA256,
         "direct_delivery_source_changed")
    spec = importlib.util.spec_from_file_location("_neural059_grading_delivery", path)
    module = importlib.util.module_from_spec(spec)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


def grade_capture(prepared_sessions, capture, *, max_input_bytes, max_packet_bytes,
                  max_response_bytes, max_total_response_bytes):
    """Verify the complete capture, then calculate the original probability scores.

    Replay checks the recorded response bytes, exact observations, full roster,
    four-condition history barrier and preparation hash. It proves consistency
    of the supplied artifacts, not that a participant produced those bytes.
    """
    delivery = dependencies()
    # Bound both objects, including malformed captures, before replay or copying.
    prepared_body = delivery.bounded_json(prepared_sessions, max_input_bytes)
    capture_body = delivery.bounded_json(capture, max_input_bytes)
    need(len(prepared_body) + len(capture_body) <= max_input_bytes,
         "aggregate_input_byte_limit")
    need(type(capture) is dict and type(capture.get("predictions")) is list,
         "capture_schema")
    owner = delivery.DirectCollection(
        prepared_sessions, max_input_bytes=max_input_bytes,
        max_packet_bytes=max_packet_bytes, max_response_bytes=max_response_bytes,
        max_total_response_bytes=max_total_response_bytes)
    for row in capture["predictions"]:
        need(type(row) is dict and type(row.get("response_utf8")) is str,
             "capture_record_schema")
        channel = owner.channel(row.get("session_index"), row.get("condition"))
        channel.observation()
        try:
            response = row["response_utf8"].encode("utf-8")
        except UnicodeError as error:
            raise GradingError("capture_response_utf8") from error
        channel.answer(response)
    replay = owner.finish()
    # Typed canonical equality also rejects changed counters, claims, p_left,
    # pins, unknown fields and bool/int aliases in capture metadata.
    need(delivery.bounded_json(replay, max_input_bytes) == capture_body,
         "capture_replay_mismatch")
    support, _ = delivery.dependencies()
    evaluation = support.evaluation
    by_case = {(row["session_index"], row["condition"], row["case_id"]): row
               for row in replay["predictions"]}
    conditions = []
    for condition in delivery.CONDITIONS:
        sessions, pairs_by_animal = [], {a: [] for a in evaluation.ANIMAL_ORDER}
        all_pairs = []
        for index, prepared in enumerate(prepared_sessions):
            cases = [case for case in prepared["cases"] if case["split"] == "test"]
            pairs, trials = [], []
            for case in cases:
                row = by_case[index, condition, case["case_id"]]
                pairs.append((case["y"], row["p_left"]))
                trials.append({"case_id": case["case_id"], "ordinal": case["ordinal"],
                               "prior_case_id": case["prior_case_id"],
                               "observation": row["observation"], "response": row["response"],
                               "arithmetic": evaluation.trial_score(case["y"], row["p_left"])})
            pairs_by_animal[prepared["subject_id"]].extend(pairs)
            all_pairs.extend(pairs)
            sessions.append({"session_id": prepared["session_id"],
                             "subject_id": prepared["subject_id"], "lab": prepared["lab"],
                             "expected_n": len(cases), "accepted_n": len(pairs),
                             "trials": trials, **evaluation.metrics_from_pairs(pairs)})
        animals = [{"subject_id": animal,
                    "lab": next(r[2] for r in evaluation.ROSTER if r[1] == animal),
                    "session_ids": [r[0] for r in evaluation.ROSTER if r[1] == animal],
                    **evaluation.metrics_from_pairs(pairs_by_animal[animal])}
                   for animal in evaluation.ANIMAL_ORDER]
        macro, reasons = {}, {}
        for metric in evaluation.METRICS:
            values = [animal["scores"][metric] for animal in animals]
            complete = all(value is not None for value in values)
            macro[metric] = math.fsum(values) / 13 if complete else None
            reasons[metric] = None if complete else "requires_all_13_defined_animal_metrics"
        conditions.append({"condition": condition, "sessions": sessions, "animals": animals,
                           "equal_animal_primary": {"scores": macro, "metric_reasons": reasons,
                                                    "denominator": 13},
                           "pooled_trial_secondary": evaluation.metrics_from_pairs(all_pairs)})
    return {"schema": "neural059-direct-grading/v1", "status": "source_only_unqualified",
            "access_condition": "direct_numerical_probability",
            "scientific_qualification": False, "participant_isolation_qualified": False,
            "model_execution_proved": False, "capture_integrity": "exact_replay",
            "prepared_input": replay["prepared_input"],
            "capture_input": delivery.pin(capture_body),
            "expected_responses": replay["expected_responses"],
            "roster": [{"session_id": e, "subject_id": a, "lab": l}
                       for e, a, l in evaluation.ROSTER],
            "conditions": conditions, "contrasts": contrasts(conditions, evaluation),
            "interpretation": "Retrospective conditional prediction; artifact consistency only. "
                              "No F/I/R identity, participant authenticity, matched run-budget "
                              "claim, causal claim or native-versus-tool conclusion."}


def contrasts(conditions, evaluation):
    """Retain paired animals and labs with the frozen conditional spread."""
    lookup = {row["condition"]: row for row in conditions}
    output = []
    draws = tuple(evaluation._draws(evaluation.ANIMAL_ORDER))
    for label, low, high in (("neural", "SH", "SHN"), ("neural", "SBH", "SBHN"),
                             ("privileged_context", "SH", "SBH"),
                             ("privileged_context", "SHN", "SBHN")):
        for metric in evaluation.METRICS:
            values = {}
            for a, b in zip(lookup[low]["animals"], lookup[high]["animals"]):
                x, y = a["scores"][metric], b["scores"][metric]
                values[a["subject_id"]] = (None if x is None or y is None else
                    (y - x if metric in ("balanced_accuracy", "auc") else x - y))

            def retained_mean(animals):
                available = sum(values[a] is not None for a in animals)
                return {"value": math.fsum(values[a] for a in animals) / len(animals)
                        if available == len(animals) else None,
                        "retained_animals": list(animals), "denominator": len(animals),
                        "available_denominator": available,
                        "reason": None if available == len(animals) else
                                  "incomplete_prespecified_retained_support"}

            output.append({"contrast_id": label + ":" + low + ":" + high, "metric": metric,
                           "formula": "loss(low)-loss(high); BA/AUC(high)-BA/AUC(low)",
                           "low_condition": low, "high_condition": high,
                           "animal_values": [{"subject_id": a, "value": values[a]}
                                             for a in evaluation.ANIMAL_ORDER],
                           "complete_equal_animal": retained_mean(evaluation.ANIMAL_ORDER),
                           "leave_one_animal": [{"omitted_animal": a,
                               **retained_mean([x for x in evaluation.ANIMAL_ORDER if x != a])}
                               for a in evaluation.ANIMAL_ORDER],
                           "leave_one_lab": [{"omitted_lab": lab,
                               **retained_mean([a for a in evaluation.ANIMAL_ORDER
                                   if next(r[2] for r in evaluation.ROSTER if r[1] == a) != lab])}
                               for lab in evaluation.LAB_ORDER],
                           "conditional_spread": evaluation._spread(
                               values, evaluation.ANIMAL_ORDER, draws),
                           "interpretation": "Conditional predictive contrast; no causal effect, "
                                             "p-value or binary success rule."})
    return output


def strict_json(path, remaining):
    with open(path, "rb") as stream:
        body = stream.read(remaining + 1)
    need(len(body) <= remaining, "aggregate_input_byte_limit")

    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate_json_key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise GradingError("nonfinite_json_constant")

    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=invalid_constant), body


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("prepared", "capture", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("input", "packet", "response", "total-response", "output"):
        parser.add_argument("--max-" + name + "-bytes", type=int, required=True)
    args = parser.parse_args(argv)
    limits = {"max_" + name + "_bytes": getattr(args, "max_" + name + "_bytes")
              for name in ("input", "packet", "response", "total_response")}
    if min(*limits.values(), args.max_output_bytes) <= 0:
        parser.error("positive explicit byte ceilings required")
    try:
        prepared, prepared_body = strict_json(args.prepared, args.max_input_bytes)
        capture, capture_body = strict_json(args.capture, args.max_input_bytes - len(prepared_body))
        result = grade_capture(prepared, capture, **limits)
        delivery = dependencies()
        result["input_files_in_order"] = [delivery.pin(prepared_body), delivery.pin(capture_body)]
        output = delivery.bounded_json(result, args.max_output_bytes)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(output)
        except BaseException:
            args.output.unlink(missing_ok=True)
            raise
        print(json.dumps({"status": result["status"], **delivery.pin(output)}))
        return 0
    except (ValueError, TypeError, KeyError, OverflowError, OSError, RecursionError):
        # Do not reflect protected values or file paths; preserve the inputs.
        print(json.dumps({"error": "invalid_operand_or_output"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
