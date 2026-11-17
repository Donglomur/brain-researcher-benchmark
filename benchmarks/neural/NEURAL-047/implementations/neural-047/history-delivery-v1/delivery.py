"""NEURAL-047 permitted-history direct and typed-viewer transports.

Operator source: never mount this process, panel, or input files in a participant
environment. This transport does not qualify native data or enforce host isolation.
"""
import argparse
import copy
import html
import importlib.util
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
V3 = Path(__file__).resolve().parent.parent / "full-conditional-programme-v3"
_spec = importlib.util.spec_from_file_location(
    "neural047_delivery_source", V3 / "program/__init__.py",
    submodule_search_locations=[str(V3 / "program")])
_package = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _package
_spec.loader.exec_module(_package)
from neural047_delivery_source.legacy import delivery_io as io
from neural047_delivery_source.legacy.scorer_core import public_contract, admit
from neural047_delivery_source.development import validate as validate_fold

MODES = ("direct_observation", "typed_viewer")
CHANNELS = {"N": ("saav_history",), "B": ("velocity", "dv"),
            "NB": ("velocity", "dv", "saav_history")}
CAP = 64000000
PROTOCOL = {
    "schema": "neural047-history-delivery-protocol-v1",
    "history_seconds": 4.8,
    "landmark_seconds": 2.4,
    "observations": "All native samples supplied by the prepared fold; no resampling or normalization.",
    "conditions": "All outer-training examples with labels; all query histories without labels.",
    "target": "Probability of dorsal-positive mean head curvature in the first two native frames after reversal end.",
    "source_scale": "Original processed source values; physical amplitude units are not certified.",
    "viewer_actions": ["catalog", "history", "submit", "abstain"],
    "transport_byte_cap": CAP,
    "maximum_participant_requests": 9999,
    "feedback": "No target, score, correctness feedback, cross-fold or cross-arm memory.",
    "mode_boundary": "Direct observation has no participant tools; typed viewer permits only the listed actions. Host enforcement is external.",
}


def digest(value):
    return io.pin(io.canonical(value))


def validate_context(panel, packet, expected_packet_pin):
    """Check complete train/query membership, including every other worm's cases."""
    public_contract(panel)
    io.check_pin(expected_packet_pin, CAP)
    io.need(digest(packet) == expected_packet_pin, "Trusted prepared packet pin mismatch")
    validate_fold(packet)
    folds = {row["fold_id"]: row for row in panel["folds"]}
    io.need(packet["fold_id"] in folds and packet["packet_id"] == panel["packet_id"],
            "Packet belongs to the selected complete panel")
    fold = folds[packet["fold_id"]]
    io.need(packet["test_group"] == fold["test_group"] and
            [row["case_key"] for row in packet["query"]] == fold["case_keys"],
            "Complete ordered held-worm query support")
    expected_training = {key: f["test_group"] for f in panel["folds"]
                         if f["fold_id"] != packet["fold_id"] for key in f["case_keys"]}
    io.need({row["case_key"]: row["group"] for row in packet["training"]} == expected_training,
            "Every other animal and event required with correct biological group")


def context_receipt(panel, packet, mode, expected_packet_pin):
    io.need(mode in MODES, "Explicit observation condition")
    validate_context(panel, packet, expected_packet_pin)
    receipt = {"schema": "neural047-history-context-v1", "mode": mode,
               "packet_id": packet["packet_id"], "fold_id": packet["fold_id"], "arm": packet["arm"],
               "observations_pin": copy.deepcopy(expected_packet_pin), "protocol_pin": digest(PROTOCOL)}
    receipt["delivery_id"] = digest(receipt)["sha256"]
    return receipt


def number(value):
    # JSON's shortest round-trip representation preserves the supplied float.
    return json.dumps(value, allow_nan=False, separators=(",", ":"))


def direct_document(packet, receipt):
    """Complete exact numeric prompt; too-large contexts fail instead of cropping."""
    lines = ["NEURAL-047: post-reversal direction from permitted history",
             "Condition: direct observation with labeled training examples; no tools.",
             PROTOCOL["target"], PROTOCOL["source_scale"],
             "Time is seconds relative to the still-reversing landmark; only [-4.8, 0] is supplied.",
             "Dorsal label 1 means positive; label 0 means negative. Query labels are withheld.",
             "Supply one p_dorsal in [0,1] per query case, or explicitly abstain for this complete context.",
             "Binding: " + io.canonical(receipt).decode("ascii").strip(), ""]
    channels = CHANNELS[packet["arm"]]
    for section in ("training", "query"):
        lines.append(section.upper())
        for row in packet[section]:
            header = "Case " + row["case_key"]
            if section == "training":
                header += " | animal " + row["group"] + " | dorsal=" + str(row["dorsal"])
            lines += [header, "sample_index\ttime_offset_seconds\t" + "\t".join(channels)]
            features = row["features"]
            for index, t in enumerate(features["time_offset_seconds"]):
                lines.append("\t".join([str(index), number(t)] +
                                       [number(features[c][index]) for c in channels]))
            lines.append("")
    lines += ["Response object:",
              '{"action":"submit","predictions":[{"case_key":"<each query key>","p_dorsal":0.5}]}',
              'Or: {"action":"abstain","reason":"<bounded reason>"}']
    result = "\n".join(lines) + "\n"
    io.need(len(result.encode("utf-8")) <= CAP, "Complete direct context exceeds transport cap; no truncation")
    return result


def waveform_svg(times, channels, sample_indices):
    """Fixed physical x-axis, per-channel observed y range, no interpolation claims.

    Exact numerical samples accompany this qualitative polyline. Rendering cannot
    certify physical amplitude units or recover values from pixels alone.
    """
    width, height = 900, 180 * len(channels)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
           '<rect width="100%" height="100%" fill="white"/>']
    for lane, (name, values) in enumerate(channels.items()):
        top = lane * 180
        lo, hi = min(values), max(values)
        # Scale before subtracting so opposite large finite values cannot overflow.
        scale = max(abs(lo), abs(hi), 1.0)
        low, high = lo / scale, hi / scale
        def y(value):
            return top + 90 if high == low else top + 140 - 105 * ((value / scale - low) / (high - low))
        coords = [(70 + 800 * (t + 4.8) / 4.8, y(v)) for t, v in zip(times, values)]
        out += [f'<text x="10" y="{top + 18}" font-size="13">{html.escape(name)}; source scale [{number(lo)}, {number(hi)}]</text>',
                f'<path d="M70 {top + 30} V{top + 145} H870" fill="none" stroke="#777"/>',
                f'<text x="70" y="{top + 166}" font-size="12">-4.8 s</text>',
                f'<text x="850" y="{top + 166}" font-size="12">0 s</text>',
                '<polyline fill="none" stroke="#2455a4" stroke-width="1.5" points="' +
                " ".join(f"{x:.8g},{yv:.8g}" for x, yv in coords) + '"/>']
        for sample, t, value, (x, yv) in zip(sample_indices, times, values, coords):
            title = html.escape(f"sample {sample}; time {number(t)} s; value {number(value)}")
            out.append(f'<circle cx="{x:.8g}" cy="{yv:.8g}" r="2" fill="#2455a4"><title>{title}</title></circle>')
    out.append("</svg>")
    return "".join(out)


class Session:
    """Trusted single-context state machine; no file/path/code actions exposed."""
    def __init__(self, panel, packet, mode, expected_packet_pin):
        self.receipt = context_receipt(panel, packet, mode, expected_packet_pin)
        self.packet = copy.deepcopy(packet)
        self.closed = False
        self.transcript = []
        self.transcript_hash = "0" * 64
        self.transcript_bytes = 0
        self.action_count = 0
        self.records = {row["case_key"]: (section, row) for section in ("training", "query")
                        for row in self.packet[section]}

    def _record(self, action, response):
        row = {"index": self.action_count, "request_pin": digest(action),
               "response_pin": digest(response), "previous": self.transcript_hash}
        self.transcript_hash = digest(row)["sha256"]
        self.transcript.append({**row, "sha256": self.transcript_hash})
        self.action_count += 1

    def open(self):
        io.need(self.action_count == 0 and not self.closed, "Open exactly once")
        if self.receipt["mode"] == "direct_observation":
            response = {"receipt": self.receipt, "document": direct_document(self.packet, self.receipt)}
        else:
            response = {"receipt": self.receipt, "protocol": PROTOCOL, "catalog": self.catalog()}
        self.transcript_bytes = len(io.canonical(response))
        io.need(self.transcript_bytes <= CAP, "Complete opening exceeds transport cap; no truncation")
        self._record({"action": "open"}, response)
        return copy.deepcopy(response)

    def catalog(self):
        return [{"case_key": key, "role": section, "sample_count": len(row["features"]["time_offset_seconds"]),
                 "channels": list(CHANNELS[self.packet["arm"]]),
                 **({"group": row["group"], "dorsal": row["dorsal"]} if section == "training" else {})}
                for key, (section, row) in self.records.items()]

    def history(self, request):
        io.exact(request, ["action", "case_key", "channels", "start_seconds", "end_seconds"])
        key = request["case_key"]
        io.need(type(key) is str and key in self.records, "Only current-context cases")
        selected = request["channels"]
        io.need(type(selected) is list and selected and all(type(c) is str for c in selected) and
                len(set(selected)) == len(selected) and set(selected) <= set(CHANNELS[self.packet["arm"]]),
                "Unique permitted channels for the selected arm")
        start, end = request["start_seconds"], request["end_seconds"]
        io.need(all(type(t) in (int, float) and math.isfinite(t) for t in (start, end)) and
                -4.8 <= start <= end <= 0, "Past-only physical-time bounds")
        section, row = self.records[key]
        features = row["features"]
        indices = [i for i, t in enumerate(features["time_offset_seconds"]) if start <= t <= end]
        io.need(indices, "Requested interval contains no native sample")
        times = [features["time_offset_seconds"][i] for i in indices]
        values = {c: [features[c][i] for i in indices] for c in selected}
        return {"case_key": key, "role": section, "sample_indices": indices,
                "time_offset_seconds": times, "values": values,
                "svg": waveform_svg(times, values, indices),
                **({"group": row["group"], "dorsal": row["dorsal"]} if section == "training" else {})}

    def _outcome(self, request):
        expected = {row["case_key"] for row in self.packet["query"]}
        if request["action"] == "submit":
            io.exact(request, ["action", "predictions"])
            rows = request["predictions"]
            io.need(type(rows) is list and len(rows) == len(expected), "Every query probability required")
            seen = set()
            for row in rows:
                io.exact(row, ["case_key", "p_dorsal"])
                key, probability = row["case_key"], row["p_dorsal"]
                io.need(type(key) is str and key in expected and key not in seen, "Exact unique query join")
                seen.add(key)
                io.need(type(probability) in (int, float) and math.isfinite(probability) and 0 <= probability <= 1,
                        "Finite dorsal probability, no booleans or normalization")
            tail = {"status": "complete", "predictions": copy.deepcopy(rows)}
        else:
            io.exact(request, ["action", "reason"])
            io.need(type(request["reason"]) is str and 0 < len(request["reason"]) <= 256,
                    "Explicit bounded complete-context abstention")
            tail = {"status": "abstain", "reason": request["reason"]}
        return {"fold_id": self.packet["fold_id"], "arm": self.packet["arm"], **tail}

    def dispatch(self, request):
        io.need(not self.closed and self.action_count > 0, "Open active context required")
        io.need(type(request) is dict and request.get("action") in PROTOCOL["viewer_actions"], "Typed action only")
        action = request["action"]
        io.need(self.receipt["mode"] == "typed_viewer" or action in ("submit", "abstain"),
                "No observation tools in direct condition")
        io.need(self.action_count < 10000, "Bounded single-context action count")
        if action == "catalog":
            io.exact(request, ["action"])
            response = {"catalog": self.catalog()}
        elif action == "history":
            response = self.history(request)
        else:
            outcome = self._outcome(request)
            response = {"schema": "neural047-observation-response-v1", "context": self.receipt,
                        "outcome": outcome, "observation_transcript_sha256": self.transcript_hash,
                        "observation_actions": self.action_count}
        size = len(io.canonical(response))
        io.need(size <= CAP and self.transcript_bytes + size <= CAP,
                "Complete response/transport budget exceeded; no silent truncation")
        self.transcript_bytes += size
        self._record(request, response)
        if action in ("submit", "abstain"):
            self.closed = True
        return copy.deepcopy(response)


def collect(panel, mode, expected_contexts, responses):
    """Join a complete mode's fold/arm outputs using trusted context receipts.

    No private-target argument is accepted; scoring remains the existing separate
    target-last operation. Other modes must be collected and reported separately.
    """
    public_contract(panel)
    io.need(mode in MODES, "Separate direct or viewer collection")
    expected = {(f["fold_id"], arm) for f in panel["folds"] for arm in CHANNELS}
    io.need(type(expected_contexts) is list and type(responses) is list and
            len(expected_contexts) == len(responses) == len(expected), "Complete animal/arm context census")
    bound = {}
    for receipt in expected_contexts:
        io.exact(receipt, ["schema", "mode", "packet_id", "fold_id", "arm", "observations_pin", "protocol_pin", "delivery_id"])
        key = (receipt["fold_id"], receipt["arm"])
        io.need(key in expected and key not in bound and receipt["schema"] == "neural047-history-context-v1" and
                receipt["mode"] == mode and receipt["packet_id"] == panel["packet_id"] and
                receipt["protocol_pin"] == digest(PROTOCOL) and
                receipt["delivery_id"] == digest({k: v for k, v in receipt.items() if k != "delivery_id"})["sha256"],
                "Unique frozen context and observation condition")
        io.check_pin(receipt["observations_pin"], CAP)
        bound[key] = receipt
    outcomes, provenance, seen = [], [], set()
    for response in responses:
        io.exact(response, ["schema", "context", "outcome", "observation_transcript_sha256", "observation_actions"])
        receipt = response["context"]
        io.need(type(receipt) is dict and type(receipt.get("fold_id")) is str and type(receipt.get("arm")) is str,
                "Bound response identity")
        key = (receipt["fold_id"], receipt["arm"])
        io.need(key in bound and key not in seen and receipt == bound[key] and
                response["schema"] == "neural047-observation-response-v1", "No substituted, duplicate or cross-mode output")
        seen.add(key)
        outcome = response["outcome"]
        io.need(type(outcome) is dict and outcome.get("fold_id") == key[0] and outcome.get("arm") == key[1],
                "Outcome matches delivered context")
        io.check_pin({"bytes": 1, "sha256": response["observation_transcript_sha256"]}, 1)
        io.need(type(response["observation_actions"]) is int and 1 <= response["observation_actions"] < 10000,
                "Bounded observation action count")
        outcomes.append(outcome)
        provenance.append({"delivery_id": receipt["delivery_id"], "response_pin": digest(response)})
    submission = {"schema": "neural047-predictions-v1", "packet_id": panel["packet_id"], "outcomes": outcomes}
    admit(panel, submission)
    return {"schema": "neural047-observation-collection-v1", "mode": mode,
            "submission": submission, "context_responses": provenance}


def collect_paired(panel, contexts, responses):
    """Require both modes on every worm/arm and identical permitted observations."""
    io.exact(contexts, MODES)
    io.exact(responses, MODES)
    collections = {mode: collect(panel, mode, contexts[mode], responses[mode]) for mode in MODES}
    pins = [{(r["fold_id"], r["arm"]): r["observations_pin"] for r in contexts[mode]} for mode in MODES]
    io.need(pins[0] == pins[1], "Direct and viewer modes must receive identical complete observations")
    return {"schema": "neural047-paired-observation-collections-v1", "packet_id": panel["packet_id"],
            "protocol_pin": digest(PROTOCOL), "collections": collections}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    session = sub.add_parser("session", help="Trusted JSON-lines controller; participant sees stdout only")
    session.add_argument("--panel", type=Path, required=True)
    session.add_argument("--packet", type=Path, required=True)
    session.add_argument("--expected-packet-sha256", required=True)
    session.add_argument("--expected-packet-bytes", type=int, required=True)
    session.add_argument("--mode", choices=MODES, required=True)
    session.add_argument("--output", type=Path, required=True)
    session.add_argument("--context-output", type=Path, required=True)
    session.add_argument("--transcript-output", type=Path, required=True)
    collection = sub.add_parser("collect")
    collection.add_argument("--panel", type=Path, required=True)
    collection.add_argument("--contexts", type=Path, required=True)
    collection.add_argument("--responses", type=Path, required=True)
    collection.add_argument("--mode", choices=MODES, required=True)
    collection.add_argument("--output", type=Path, required=True)
    paired = sub.add_parser("collect-paired")
    for name in ("panel", "contexts", "responses", "output"):
        paired.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    io.need(not io.regular(args.output).exists(), "Fresh operator output")
    panel = io.json_file(args.panel, CAP)
    if args.command in ("collect", "collect-paired"):
        contexts, responses = io.json_file(args.contexts, CAP), io.json_file(args.responses, CAP)
        result = (collect_paired(panel, contexts, responses) if args.command == "collect-paired"
                  else collect(panel, args.mode, contexts, responses))
        io.put(args.output, result, CAP)
        return
    pin = {"bytes": args.expected_packet_bytes, "sha256": args.expected_packet_sha256}
    paths = [io.regular(p) for p in (args.output, args.context_output, args.transcript_output)]
    io.need(len(set(paths)) == 3 and all(not p.exists() for p in paths), "Distinct fresh operator outputs")
    packet = io.json_file(args.packet, CAP, pin)
    session = Session(panel, packet, args.mode, pin)
    # Retain the trusted context before any participant interaction. Do not derive
    # expected context receipts from submitted response fields during collection.
    io.put(args.context_output, session.receipt, CAP)
    persisted = False
    try:
        print(io.canonical(session.open()).decode("ascii"), end="", flush=True)
        while not session.closed:
            line = sys.stdin.buffer.readline(CAP + 1)
            io.need(line and len(line) <= CAP and line.endswith(b"\n"), "Complete bounded JSON-lines request; EOF is not submission")
            result = session.dispatch(io.decode(line))
            # Persist closed response before acknowledging completion to participant.
            if session.closed:
                io.put(args.output, result, CAP)
                persisted = True
            print(io.canonical(result).decode("ascii"), end="", flush=True)
    finally:
        error = sys.exc_info()[0]
        io.put(args.transcript_output, {
            "schema": "neural047-observation-transcript-v1", "context": session.receipt,
            "closed": session.closed, "response_persisted": persisted,
            "failure_type": error.__name__ if error else None,
            "actions": session.transcript, "head_sha256": session.transcript_hash,
            "accepted_response_payload_bytes": session.transcript_bytes}, CAP)


if __name__ == "__main__":
    main()
