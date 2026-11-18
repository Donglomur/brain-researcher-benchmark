"""Inactive operator-hosted EEG presentation and complete 10 Hz response binding.

Only dispatch replies cross the participant boundary. Python objects, support,
factories and final candidates are operator-private; this is not OS isolation.
SVG is an explicit vector representation, not raster/native-image evidence.
"""
from __future__ import annotations

import hashlib
import hmac
import html
import json
import math
from pathlib import Path
import re
import types

ROOT = Path(__file__).resolve().parent
DEPENDENCIES = {
    "seizure-events-v1/core.py": "5b92def65bbfb75368986dff72f66b8a511b077a9f6343b4c5732ab80805b834",
    "edf-causal-window-v1/edf_window.py": "18a09575d432df486c103c87524ee15b8189171200acd7d3fc99146f1f98283d",
}


class Refused(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise Refused(reason)


def integer(value, minimum=1):
    need(type(value) is int and minimum <= value <= 2**53 - 1, "invalid_integer")
    return value


def number(value):
    need(type(value) in (int, float), "invalid_number")
    try:
        need(math.isfinite(value), "invalid_number")
    except OverflowError as error:
        raise Refused("invalid_number") from error
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def sha(value):
    need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value), "invalid_commitment")
    return value


def snapshot(value):
    # Reject non-JSON objects and detach all caller-owned mutable operands.
    try:
        return json.loads(json.dumps(value, allow_nan=False, ensure_ascii=True))
    except (TypeError, ValueError, OverflowError) as error:
        raise Refused("invalid_json") from error


class Dependencies:
    """Trusted deployment path selection; exact bytes are always required."""
    def __init__(self, implementations=None):
        root = Path(implementations) if implementations is not None else ROOT.parent
        modules = []
        for relative, expected in DEPENDENCIES.items():
            path = root / relative
            body = path.read_bytes()
            need(hashlib.sha256(body).hexdigest() == expected, "dependency_changed")
            module = types.ModuleType("_n009_" + path.stem)
            module.__file__ = str(path)
            exec(compile(body, str(path), "exec"), module.__dict__)
            modules.append(module)
        self.core, self.reader = modules


def validate_protocol(protocol, records):
    fields = {"schema", "lookback_ticks", "width_px", "channel_height_px", "max_svg_bytes",
              "max_total_svg_bytes_per_record", "max_actions_per_record", "max_views_per_tick",
              "max_window_samples", "max_window_values", "scales_uv"}
    need(type(protocol) is dict and set(protocol) == fields, "protocol_fields")
    need(protocol["schema"] == "neural009_typed_svg_protocol_v1", "protocol_schema")
    for field in fields - {"schema", "scales_uv"}:
        integer(protocol[field])
    need(protocol["width_px"] >= 2 and protocol["channel_height_px"] >= 2, "plot_geometry")
    need(protocol["max_total_svg_bytes_per_record"] >= protocol["max_svg_bytes"], "total_svg_budget")
    need(protocol["max_actions_per_record"] >= max(r["observed_ticks"] for r in records.values()),
         "budget_cannot_cover_all_answers")
    scales = protocol["scales_uv"]
    need(type(scales) is dict and set(scales) == set(records), "complete_scale_support")
    for identifier, record in records.items():
        bands = scales[identifier]
        need(type(bands) is list and len(bands) == len(record["predictor_channels"]), "scale_channels")
        for band, channel in zip(bands, record["predictor_channels"]):
            need(type(band) is dict and set(band) == {"index", "minimum", "maximum"}, "scale_fields")
            integer(band["index"], 0)
            need(band["index"] == channel["index"], "scale_channel_identity")
            low, high = number(band["minimum"]), number(band["maximum"])
            need(low < high and math.isfinite(high - low), "scale_range")
        # No unbounded native sample buffers before the rendering cap is known.
        span = min(record["native_sample_count"],
                   (protocol["lookback_ticks"] * record["native_sample_rate_hz"] + 9) // 10 + 1)
        need(span <= protocol["max_window_samples"] and
             span * len(bands) <= protocol["max_window_values"], "declared_window_allocation")


def render(window, record, bands, protocol):
    """All selected samples, fixed declared ranges; no filter/crop/auto-scaling."""
    need(type(window) is dict and set(window) == {"schema", "sample_start", "sample_stop",
         "sample_rate_hz", "available_through_tick", "channels"}, "window_fields")
    need(window["schema"] == "neural009_calibrated_causal_window_v1", "window_schema")
    rate = record["native_sample_rate_hz"]
    need(window["sample_rate_hz"] == rate, "window_rate")
    start, stop = window["sample_start"], window["sample_stop"]
    integer(start, 0); integer(stop)
    count = stop - start
    need(0 < count <= protocol["max_window_samples"], "window_extent")
    need(type(window["channels"]) is list and len(window["channels"]) == len(bands), "window_channels")
    width, height = protocol["width_px"], protocol["channel_height_px"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height * len(bands)}" role="img">',
             '<title>Causal calibrated EEG; fixed ranges in microvolts</title>']
    for row, (values, band, selected) in enumerate(zip(window["channels"], bands, record["predictor_channels"])):
        need(type(values) is dict and set(values) == {"channel_index", "label", "unit", "samples"}, "channel_fields")
        need(values["channel_index"] == selected["index"] and values["label"] == selected["label"]
             and values["unit"] == "uV", "channel_identity")
        samples = values["samples"]
        need(type(samples) is list and len(samples) == count, "sample_count")
        points = []
        low, high = band["minimum"], band["maximum"]
        for offset, value in enumerate(samples):
            number(value)
            need(low <= value <= high, "outside_declared_scale")
            x = offset * (width - 1) / max(1, count - 1)
            y = row * height + (high - value) * (height - 1) / (high - low)
            need(math.isfinite(x) and math.isfinite(y), "plot_coordinate")
            points.append(f"{x:.9g},{y:.9g}")
        label = html.escape(selected["label"], quote=True)
        parts.append(f'<g><title>{label}; {low} to {high} uV; sample times {start}/{rate} to {stop-1}/{rate} seconds</title>')
        parts.append('<polyline fill="none" stroke="black" stroke-width="1" points="' + " ".join(points) + '"/></g>')
    parts.append("</svg>")
    result = "".join(parts)
    need(len(result.encode()) <= protocol["max_svg_bytes"], "svg_byte_budget")
    return result


class Cohort:
    """Owner-only state; only the JSON-shaped replies may reach participants.

    A protected external host must supply genuine case isolation and frozen
    recipes. A Python API, HMAC name and caller-owned factory do not provide it.
    """
    def __init__(self, support, policy, protocol, *, expected_support_sha256,
                 expected_policy_sha256, expected_protocol_sha256, recipe_sha256,
                 limits, secret, dependencies=None):
        self._deps = dependencies if dependencies is not None else Dependencies()
        self._core = self._deps.core
        self._support, self._policy, self._protocol, self._limits = map(snapshot, (support, policy, protocol, limits))
        need(digest(self._support) == sha(expected_support_sha256), "support_commitment")
        need(digest(self._protocol) == sha(expected_protocol_sha256), "protocol_commitment")
        self._core.validate_policy(self._policy, expected_policy_sha256)
        self._records = self._core.validate_public_support(self._support, self._limits)
        self._index, _, _ = self._core.source_index()
        validate_protocol(self._protocol, self._records)
        self._recipe = sha(recipe_sha256)
        need(type(secret) is bytes and len(secret) >= 32, "opaque_key")
        self._secret = secret
        self._join = {self._opaque("case", name): name for name in sorted(self._records)}
        need(len(self._join) == 686, "opaque_collision")
        self._state = {name: {"status": "not_started", "ticks": 0, "runs": [],
                              "failure": None, "cleanup_failures": 0}
                       for name in self._records}
        self._active = None
        self._reader = None
        self._segments = 0

    def _opaque(self, role, value):
        return hmac.new(self._secret, (role + "\0" + value).encode(), hashlib.sha256).hexdigest()

    def case_ids(self):
        """Owner schedule: opaque IDs only; source/person mapping stays private."""
        # Do not reveal source-manifest order as an implicit filename lookup.
        return tuple(sorted(self._join))

    def _close(self):
        reader = self._reader
        if reader is not None:
            try:
                reader.close()
            except BaseException as error:
                # Retain ownership for an explicit host cleanup retry. Neither
                # a failed close nor interruption can certify completion.
                if self._active is not None:
                    state = self._state[self._join[self._active]]
                    state["status"] = "failed"
                    state["failure"] = state["failure"] or "reader_cleanup_failed"
                    state["cleanup_failures"] += 1
                if not isinstance(error, Exception):
                    raise
                return False
            self._reader = None
        return True

    def _fail(self, reason):
        case = self._active
        state = self._state[self._join[case]]
        state["status"] = "failed"
        state["failure"] = state["failure"] or reason
        if self._close():
            self._active = None
        return {"case_id": case, "status": "failed",
                "reason": self._state[self._join[case]]["failure"]}

    def abort_active(self):
        """Owner timeout/cancellation hook; no caller-supplied failure text."""
        if self._active is None:
            return {"status": "no_active_case"}
        result = self._fail("operator_aborted")
        result["cleanup_complete"] = self._reader is None
        return result

    def start_edf(self, case_id, path, admitted_row, *, max_edf_bytes):
        """Owner entry point binding the original file to the opaque case.

        The complete source admission/clock/channel-role review is a separate
        prerequisite. Targets in admitted_row never enter a participant reply.
        """
        def open_reader():
            row = snapshot(admitted_row)
            name = self._join[case_id]
            support = self._records[name]
            need(row["recording_id"] == name and
                 row["biological_person"] == support["biological_person"] and
                 row["edf_sha256"] == self._index[name]["publisher_sha256"], "source_case_binding")
            for field in ("native_sample_rate_hz", "native_sample_count", "observed_ticks"):
                need(type(row[field]) is int and row[field] == support[field], "source_support")
            selected = [{"index": i, "label": row["channels"][i]["label"]}
                        for i in row["predictor_channels"]]
            need(selected == support["predictor_channels"], "source_channel_binding")
            return self._deps.reader.RecordWindow(path, row, max_edf_bytes=max_edf_bytes,
                max_window_samples=self._protocol["max_window_samples"],
                max_output_values=self._protocol["max_window_values"])
        return self._start(case_id, open_reader)

    def _start(self, case_id, open_reader):
        """Internal owner seam; factories/objects are never participant inputs."""
        need(self._active is None and self._reader is None and case_id in self._join, "case_not_available")
        name = self._join[case_id]
        state, row = self._state[name], self._records[name]
        need(state["status"] == "not_started", "case_already_attempted")
        self._active = case_id
        state.update(status="active", actions=0, views=0, svg_bytes=0)
        try:
            self._reader = open_reader()
            need(isinstance(self._reader, self._deps.reader.RecordWindow), "reader_type")
            need(self._reader.sample_rate_hz == row["native_sample_rate_hz"] and
                 self._reader.sample_count == row["native_sample_count"] and
                 self._reader.observed_ticks == row["observed_ticks"], "reader_support")
        except Exception:
            return self._fail("source_refused")
        return {"case_id": case_id, "status": "active", "endpoint_tick": 1,
                "observed_ticks": row["observed_ticks"], "evaluation_rate_hz": 10,
                "representation": "inactive_typed_svg_not_native_image"}

    def dispatch(self, request):
        """Closed typed interaction; no candidate code, path, array or scorer API."""
        need(self._active is not None, "no_active_case")
        state = self._state[self._join[self._active]]
        if state["status"] != "active":
            return {"case_id": self._active, "status": "refused", "reason": "case_failed"}
        state["actions"] += 1
        if state["actions"] > self._protocol["max_actions_per_record"]:
            return self._fail("action_budget_exhausted")
        try:
            # Constant-size shallow capture only. Nested/oversized unknown values
            # are never serialized, traversed, copied or returned. JSON-decoder
            # and transport byte limits remain the external host's obligation.
            need(type(request) is dict and len(request) in (4, 5), "request_fields")
            items = tuple(request.items())
            need(len(items) in (4, 5) and all(type(k) is str for k, _ in items), "request_fields")
            request = dict(items)
            case = request.get("case_id")
            need(type(case) is str and len(case) == 64 and case == self._active, "case_identity")
            action = request.get("action")
            need(type(action) is str and len(action) <= 6, "request_action")
            if action == "view":
                need(set(request) == {"action", "case_id", "end_tick", "lookback_ticks"}, "request_fields")
                return self._view(request, state)
            need(action == "answer" and set(request) == {"action", "case_id", "tick", "probability"}, "request_fields")
            return self._answer(request, state)
        except Refused:
            return {"case_id": self._active, "status": "refused", "reason": "invalid_request"}

    def _view(self, request, state):
        row = self._records[self._join[self._active]]
        active = state["ticks"] + 1
        end, lookback = integer(request["end_tick"]), integer(request["lookback_ticks"])
        earliest = max(0, active - self._protocol["lookback_ticks"])
        need(end <= active and lookback <= self._protocol["lookback_ticks"] and
             max(0, end - lookback) >= earliest, "causal_context")
        need(state["views"] < self._protocol["max_views_per_tick"], "view_budget")
        state["views"] += 1
        rate = row["native_sample_rate_hz"]
        start = (max(0, end - lookback) * rate + 9) // 10
        stop = min(row["native_sample_count"], end * rate // 10 + 1)
        try:
            window = self._reader.window(start, stop, available_through_tick=active)
            need(window["sample_start"] == start and window["sample_stop"] == stop and
                 window["available_through_tick"] == active, "window_identity")
            svg = render(window, row, self._protocol["scales_uv"][self._join[self._active]], self._protocol)
            size = len(svg.encode())
            need(state["svg_bytes"] + size <= self._protocol["max_total_svg_bytes_per_record"], "total_svg_budget")
        except Exception:
            return self._fail("presentation_refused")
        state["svg_bytes"] += size
        return {"case_id": self._active, "status": "view", "endpoint_tick": active,
                "view_id": self._opaque("view", self._active + str(state["actions"]) + svg),
                "svg": svg, "representation": "inactive_typed_svg_not_native_image"}

    def _answer(self, request, state):
        tick = integer(request["tick"])
        probability = number(request["probability"])
        need(tick == state["ticks"] + 1 and
             tick <= self._records[self._join[self._active]]["observed_ticks"] and
             0 <= probability <= 1, "answer_support")
        runs = state["runs"]
        if runs and runs[-1][2] == probability:
            runs[-1][1] = tick
        else:
            if self._segments >= self._limits["max_prediction_segments"]:
                return self._fail("segment_budget_exhausted")
            runs.append([tick - 1, tick, probability])
            self._segments += 1
        state.update(ticks=tick, views=0)
        case = self._active
        complete = tick == self._records[self._join[case]]["observed_ticks"]
        if complete:
            if not self._close():
                return {"case_id": case, "status": "failed", "reason": "reader_cleanup_failed"}
            self._active = None
            state["status"] = "complete"
        return {"case_id": case, "status": "accepted", "record_complete": complete,
                "next_endpoint_tick": None if complete else tick + 1}

    def finish(self):
        """Operator-only full ledger and unchanged scorer ABI; no partial scoring."""
        ledger = [{"recording_id": name, "biological_person": self._records[name]["biological_person"],
                   "observed_ticks": self._records[name]["observed_ticks"], **snapshot(self._state[name])}
                  for name in sorted(self._records)]
        if any(row["status"] != "complete" for row in ledger):
            return {"status": "incomplete", "candidate": None, "records": ledger}
        candidate = {"schema": "neural009_candidate_v1", "task_id": "NEURAL-009",
                     "source_index_sha256": self._support["source_index_sha256"],
                     "policy_sha256": digest(self._policy), "support_sha256": digest(self._support),
                     "recipe_sha256": self._recipe, "records": []}
        for row in ledger:
            candidate["records"].append({"recording_id": row["recording_id"],
                "biological_person": row["biological_person"], "fold_id": row["biological_person"],
                "score_runs": row["runs"],
                "predicted_intervals": self._core._derive_intervals(row["runs"], self._policy["threshold"])})
        self._core.prevalidate_candidate(candidate, self._policy, self._support,
                                        expected_policy_sha256=digest(self._policy), limits=self._limits)
        return {"status": "complete_declared_response_support", "candidate": candidate,
                "records": ledger, "scientific_qualification": False, "mode_activated": False}
