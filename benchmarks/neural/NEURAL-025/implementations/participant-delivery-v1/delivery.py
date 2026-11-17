#!/usr/bin/env python3
"""NEURAL-025 participant views and complete response collection.

Construction on admitted normalized arrays; no native MAT extraction or process
isolation. The existing private scorer remains the sole metric implementation.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np

_SOURCE = Path(__file__).resolve().parents[1] / "train-only-decoding-v1" / "pipeline.py"
_SPEC = importlib.util.spec_from_file_location("neural025_delivery_pipeline", _SOURCE)
p = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = p
_SPEC.loader.exec_module(p)

MODES = ("direct_observation", "typed_viewer", "tool_assisted", "frozen_program")
PACKET_SCHEMA = "calcium_participant_v1"
INDEX_SCHEMA = "calcium_operator_index_v1"
RESPONSE_SCHEMA = "calcium_response_v1"


def _context(context: dict[str, Any], admitted: dict[str, Any], expected: str) -> dict[str, Any]:
    p._sha(expected, "Context identity")
    p.require(p.digest(context) == expected, "Context digest mismatch")
    try:
        p.require(context["schema"] == "calcium_reach_context_v1" and
                  context["task_id"] == p.TASK_ID and
                  context["event_conditioning"] == "retrospective_public_liftTimeDLC",
                  "Wrong public reach context")
        sessions = p._records(context["sessions"], "Context sessions", "session_id")
        p.require(set(sessions) == set(p.SESSIONS), "Context must contain all ten sessions")
        bindings = {row["session_id"]: row for row in admitted["protocol"]["sessions"]}
        result = {}
        for sid, session in admitted["sessions"].items():
            row = sessions[sid]
            p.require(row["source_asset_sha256"] == bindings[sid]["source_asset_sha256"],
                      "Context source binding differs")
            p._sha(row["native_target_mapping_sha256"], "Native direction mapping")
            trials = p._records(row["trials"], "Context trials", "trial_id")
            p.require(set(trials) == set(session["trials"]), "Context trial census differs")
            numbers = []
            for trial in trials.values():
                numbers.append(p.integer(trial["original_trial_number"], "Original trial number", minimum=0))
                p.require(trial["reach_target"] in ("left", "right"), "Unknown reach target")
            p.require(len(set(numbers)) == len(numbers), "Repeated original trial number")
            result[sid] = trials
        return result
    except p.Refusal:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise p.Refusal("Malformed public reach context") from exc


def prepare(dataset: dict[str, Any], protocol: dict[str, Any], context: dict[str, Any], *,
            expected_protocol_sha256: str, expected_context_sha256: str) -> tuple[dict, dict]:
    """Return participant packet and separately retained operator identity index.

    Query targets affect only the private normalized-input binding. ROI selection
    uses training neural samples, with the predecessor's exact ranking/tie rule.
    No model fitting, PCA, source download, or filesystem write occurs here.
    """
    admitted = p.admit(dataset, protocol, expected_protocol_sha256=expected_protocol_sha256)
    p.require(protocol["condition"] == "within_mouse",
              "This paired delivery is scoped to within-mouse held-trial readout")
    labels = _context(context, admitted, expected_context_sha256)
    grid = list(range(protocol["window_ms"][0], protocol["window_ms"][1] + 1, protocol["grid_step_ms"]))
    # Only outcome-independent binding identities are shared with participants.
    packet = {"schema": PACKET_SCHEMA, "task_id": p.TASK_ID,
              "protocol_sha256": expected_protocol_sha256, "condition": "within_mouse",
              "target_field": protocol["target_field"], "target_units": protocol["target_units"],
              "joint_names": list(p.JOINT_NAMES), "time_ms": grid,
              "feature_variant": protocol["feature_variant"],
              "event_conditioning": protocol["event_conditioning"],
              "upstream_exposure_policy": protocol["upstream_exposure_policy"],
              "selection": "training_neural_sd_descending_native_roi_id_tiebreak",
              "cell_budget": protocol["cell_budget"],
              "reference_recipe": {"pca_components": protocol["pca_components"],
                                   "ridge_alpha_sum_loss": protocol["ridge_alpha"]},
              "sessions": []}
    index = {"schema": INDEX_SCHEMA, "task_id": p.TASK_ID,
             "protocol_sha256": expected_protocol_sha256,
             "context_sha256": expected_context_sha256,
             "normalized_input_sha256": admitted["normalized_input_sha256"], "sessions": {}}
    bindings = {row["session_id"]: row for row in protocol["sessions"]}
    for session_number, (sid, session) in enumerate(admitted["sessions"].items(), 1):
        public_sid = f"session-{session_number:02d}"
        training = session["training_ids"]
        x = np.concatenate([session["trials"][tid]["x"] for tid in training])
        with np.errstate(over="raise", invalid="raise", divide="raise"):
            try:
                sd = p._column_rms(p.finite_result(x - p._column_mean(x), "Centered training features"))
            except FloatingPointError as exc:
                raise p.Refusal("Training feature selection exceeds finite numeric domain") from exc
        selected = sorted(range(len(session["roi_ids"])),
                          key=lambda i: (-sd[i], session["roi_ids"][i]))[:protocol["cell_budget"]]
        public = {"session_id": public_sid,
                  "mouse_id": f"mouse-{p.MICE.index(session['mouse']) + 1:02d}",
                  "region": session["region"],
                  "roi_ids": [f"roi-{i + 1:03d}" for i in range(len(selected))],
                  "upstream_temporal_support_ms": list(bindings[sid]["upstream_temporal_support_ms"]),
                  "training": [], "query": []}
        private = {"session_id": sid, "selected_roi_ids": [session["roi_ids"][i] for i in selected],
                   "training": {}, "query": {}}
        for split, ids in (("training", training), ("query", session["evaluation_ids"])):
            # Order is the frozen split order; no sort on target-dependent source strings.
            for number, tid in enumerate(ids, 1):
                case = f"{split}-{number:05d}"
                trial = session["trials"][tid]
                record = {"case_id": case, "reach_target": labels[sid][tid]["reach_target"],
                          "neural": trial["x"][:, selected].tolist()}
                if split == "training":
                    record["targets"] = trial["y"].tolist()
                public[split].append(record)
                private[split][case] = tid
        packet["sessions"].append(public)
        index["sessions"][public_sid] = private
    index["packet_sha256"] = p.digest(packet)
    return packet, index


def _bound_packet(packet: dict, expected: str) -> dict[str, Any]:
    p._sha(expected, "Participant packet identity")
    p.require(p.digest(packet) == expected, "Participant packet digest mismatch")
    p.require(packet.get("schema") == PACKET_SCHEMA and packet.get("task_id") == p.TASK_ID,
              "Wrong participant packet")
    return p._records(packet["sessions"], "Participant sessions", "session_id")


def reference_response(packet: dict, *, expected_packet_sha256: str,
                       frozen_program_sha256: str) -> dict:
    """Participant-side train/predict reference: consumes no operator index/labels.

    The calling operator must freeze code independently. A digest in a response
    is an identity declaration, not verification of the executed process.
    """
    sessions = _bound_packet(packet, expected_packet_sha256)
    p._sha(frozen_program_sha256, "Frozen program identity")
    predictions = {}
    for sid, session in sessions.items():
        train = session["training"]
        model = p.fit_train_only(np.concatenate([row["neural"] for row in train]),
                                 np.concatenate([row["targets"] for row in train]),
                                 roi_ids=session["roi_ids"], cell_budget=packet["cell_budget"],
                                 pca_components=packet["reference_recipe"]["pca_components"],
                                 ridge_alpha=packet["reference_recipe"]["ridge_alpha_sum_loss"])
        predictions[sid] = {row["case_id"]: p.predict(model, row["neural"],
                            roi_ids=session["roi_ids"]).tolist() for row in session["query"]}
    return {"schema": RESPONSE_SCHEMA, "task_id": p.TASK_ID,
            "packet_sha256": expected_packet_sha256, "mode": "frozen_program",
            "frozen_program_sha256": frozen_program_sha256,
            "target_field": packet["target_field"], "target_units": packet["target_units"],
            "joint_names": packet["joint_names"], "time_ms": packet["time_ms"],
            "predictions": predictions}


def collect_response(response: dict, packet: dict, index: dict, *, expected_packet_sha256: str,
                     expected_index_sha256: str, expected_mode: str,
                     expected_program_sha256: str | None = None) -> dict:
    """Reject partial/extra cases, wrong endpoint/grid, identity drift and invalid numbers."""
    sessions = _bound_packet(packet, expected_packet_sha256)
    p._sha(expected_index_sha256, "Operator index identity")
    p.require(p.digest(index) == expected_index_sha256, "Operator index digest mismatch")
    p.require(index.get("schema") == INDEX_SCHEMA and index.get("task_id") == p.TASK_ID and
              index.get("packet_sha256") == expected_packet_sha256, "Wrong paired operator index")
    p.require(expected_mode in MODES, "Unknown access mode")
    try:
        fields = {"schema", "task_id", "packet_sha256", "mode", "target_field", "target_units",
                  "joint_names", "time_ms", "predictions"}
        if expected_mode == "frozen_program":
            fields.add("frozen_program_sha256")
            p._sha(expected_program_sha256, "Expected frozen program identity")
            p.require(response["frozen_program_sha256"] == expected_program_sha256,
                      "Frozen program identity mismatch")
        else:
            p.require(expected_program_sha256 is None, "Program identity belongs only to frozen-program mode")
        p.require(set(response) == fields, "Unexpected or missing response fields")
        p.require(response["schema"] == RESPONSE_SCHEMA and response["task_id"] == p.TASK_ID and
                  response["packet_sha256"] == expected_packet_sha256 and response["mode"] == expected_mode,
                  "Response identity or access mode mismatch")
        for field in ("target_field", "target_units", "joint_names", "time_ms"):
            p.require(response[field] == packet[field], "Response endpoint or grid differs: " + field)
        p.require(all(type(t) is int for t in response["time_ms"]), "Response grid requires integer milliseconds")
        predictions = response["predictions"]
        p.require(isinstance(predictions, dict) and set(predictions) == set(sessions) == set(index["sessions"]),
                  "Complete ten-session predictions required")
        result = {}
        for sid, session in sessions.items():
            expected_cases = {row["case_id"] for row in session["query"]}
            mapping = index["sessions"][sid]
            values = predictions[sid]
            p.require(isinstance(values, dict) and set(values) == expected_cases == set(mapping["query"]),
                      "Complete selected query trials required")
            p.require(mapping["session_id"] not in result, "Repeated native session mapping")
            native = {}
            for case, value in values.items():
                y = p.matrix(value, "Response trajectory")
                p.require(y.shape == (len(packet["time_ms"]), 24), "Complete time-by-24 trajectory required")
                tid = mapping["query"][case]
                p.require(tid not in native, "Repeated native trial mapping")
                native[tid] = y.tolist()
            result[mapping["session_id"]] = native
        return result
    except p.Refusal:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise p.Refusal("Malformed participant response or operator index") from exc


def score_response(dataset: dict, protocol: dict, response: dict, packet: dict, index: dict, *,
                   expected_protocol_sha256: str, expected_packet_sha256: str,
                   expected_index_sha256: str, expected_mode: str,
                   expected_program_sha256: str | None = None) -> dict:
    predictions = collect_response(response, packet, index,
                                   expected_packet_sha256=expected_packet_sha256,
                                   expected_index_sha256=expected_index_sha256,
                                   expected_mode=expected_mode, expected_program_sha256=expected_program_sha256)
    admitted = p.admit(dataset, protocol, expected_protocol_sha256=expected_protocol_sha256)
    p.require(index["protocol_sha256"] == packet["protocol_sha256"] == expected_protocol_sha256 and
              index["normalized_input_sha256"] == admitted["normalized_input_sha256"],
              "Scorer input differs from the frozen paired export")
    return {"mode": expected_mode, "packet_sha256": expected_packet_sha256,
            "metrics": p._score(admitted, predictions),
            "execution_scope": "normalized_participant_delivery_control",
            "process_isolation_verified": False, "scientific_qualification": False}


def trace(packet: dict, action: dict, *, expected_packet_sha256: str) -> dict:
    """Typed observation action for one full-grid neural or training-target trace."""
    sessions = _bound_packet(packet, expected_packet_sha256)
    try:
        p.require(set(action) == {"session_id", "split", "case_id", "signal", "channel"},
                  "Unknown trace action fields")
        p.require(action["split"] in ("training", "query"), "Unknown trace split")
        p.require(action["signal"] in ("neural", "targets"), "Unknown trace signal")
        p.require(action["signal"] != "targets" or action["split"] == "training",
                  "Query targets are not participant observations")
        session = sessions[action["session_id"]]
        cases = p._records(session[action["split"]], "Participant cases", "case_id")
        case = cases[action["case_id"]]
        channels = session["roi_ids"] if action["signal"] == "neural" else packet["joint_names"]
        p.require(action["channel"] in channels, "Unknown trace channel")
        column = channels.index(action["channel"])
        values = [row[column] for row in case[action["signal"]]]
        return {"time_ms": list(packet["time_ms"]), "values": values,
                "channel": action["channel"], "reach_target": case["reach_target"],
                "units": "source_processed_activity" if action["signal"] == "neural" else packet["target_units"]}
    except p.Refusal:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise p.Refusal("Malformed trace request") from exc


def render_trace(packet: dict, action: dict, *, expected_packet_sha256: str) -> str:
    """SVG with every source-grid sample, explicit axes and no raw-array attachment.

    Per-trace display scaling is stated by axis values. Values are not clipped,
    interpolated, smoothed or treated as independent 100-Hz observations.
    """
    row = trace(packet, action, expected_packet_sha256=expected_packet_sha256)
    values = np.asarray(row["values"], dtype=float)
    lo, hi = float(np.min(values)), float(np.max(values))
    # Stable normalization handles large finite values without hi-lo overflow.
    scale = max(abs(lo), abs(hi), 1.0)
    low, high = lo / scale, hi / scale
    ys = np.full(len(values), 140.) if hi == lo else 240. - 200. * ((values / scale - low) / (high - low))
    times = row["time_ms"]
    xs = [90. + 640. * ((t - times[0]) / (times[-1] - times[0])) for t in times]
    points = " ".join(f"{x:.6f},{y:.6f}" for x, y in zip(xs, ys))
    title = html.escape(f"{action['session_id']} / {action['case_id']} / {row['channel']} / {row['reach_target']}")
    units = html.escape(row["units"])
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="310" viewBox="0 0 800 310">'
            f'<rect width="800" height="310" fill="white"/><g fill="black" font-family="sans-serif" font-size="12">'
            f'<text x="90" y="22">{title}</text><text x="4" y="42">{hi:.6g}</text>'
            f'<text x="4" y="244">{lo:.6g}</text><text x="90" y="270">{times[0]} ms</text>'
            f'<text x="690" y="270">{times[-1]} ms</text><text x="90" y="294">{units}; full grid; retrospective lift time</text>'
            f'</g><path d="M90 40V240H730" fill="none" stroke="black"/>'
            f'<polyline points="{points}" fill="none" stroke="#176b9c" stroke-width="1.5"/></svg>')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Participant-only frozen reference; no private scorer input")
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--expected-packet-sha256", required=True)
    parser.add_argument("--frozen-program-sha256", required=True)
    parser.add_argument("--max-input-bytes", required=True, type=int)
    parser.add_argument("--max-output-bytes", required=True, type=int)
    args = parser.parse_args(argv)
    try:
        p.require(0 < args.max_input_bytes < sys.maxsize and 0 < args.max_output_bytes < sys.maxsize,
                  "Byte budgets must be positive and below the platform index limit")
        with args.packet.open("rb") as stream:
            body = p._read_bounded(stream, args.max_input_bytes)
        packet = json.loads(body, object_pairs_hook=p._unique_object,
                            parse_constant=lambda _: (_ for _ in ()).throw(p.Refusal("Nonfinite JSON")))
        result = reference_response(packet, expected_packet_sha256=args.expected_packet_sha256,
                                    frozen_program_sha256=args.frozen_program_sha256)
        output = p.canonical_bytes(result) + b"\n"
        p.require(len(output) <= args.max_output_bytes, "Response exceeds output budget")
        sys.stdout.buffer.write(output)
        return 0
    except (p.Refusal, OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)[:1000]}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
