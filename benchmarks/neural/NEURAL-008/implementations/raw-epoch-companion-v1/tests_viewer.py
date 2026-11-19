"""Finite generated controls for the raw companion; no work occurs on import.

The selected caller supplies exact source bindings and a fresh generated root.
Two one-turn fake HTTPS exchanges use the real maintained Sender and custody
replay. They qualify neither a provider, token counter nor an original signal.
"""
import base64
import io
import math
from pathlib import Path
import struct
import raw_contract as C
import raw_viewer as V
import raw_provider as P

MAX_GENERATED_BYTES = 1572864
MAX_REQUEST_BYTES = 196608
SECRET = "generated_control_credential_not_an_api_key"


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def rejected(operation, fragment):
    try:
        operation()
    except (ValueError, AssertionError) as exc:
        require(fragment in str(exc), "Unexpected refusal: " + str(exc))
        return {"exception": type(exc).__name__, "reason": str(exc)}
    raise AssertionError("Required rejection did not occur: " + fragment)


def knowledge():
    return {"schema": "sleep007_epoch_shared_knowledge_v1", "provider": "openai",
            "model": "generated-control-model", "revision": "generated-control-only",
            "policy": C.KNOWLEDGE_POLICY, "external_assets": []}


class Clock:
    def __init__(self, index):
        self.index = index
    def __getitem__(self, index):
        require(index == self.index, "Another target clock was accessed")
        return (index * 30 / 3600, 0.0, 1.0)


class GeneratedPerson:
    """Only one full target exists; neighbouring epochs cannot be accessed."""
    def __init__(self, case, index, phase):
        self.case, self.index = case, index
        self.epochs = dict(C.CASES)[case]
        self.clock, self.calls = Clock(index), []
        self.rows = [[(channel + 1) * 0.000008 * math.sin((sample + phase) * math.pi / (25 + channel * 9))
                      for sample in range(C.SAMPLES)] for channel in range(3)]
    def samples(self, start, stop, channels):
        require((start, stop) == (self.index * C.SAMPLES, (self.index + 1) * C.SAMPLES),
                "Another target or incomplete epoch was accessed")
        require(channels in (list(C.CHANNELS[:2]), list(C.CHANNELS)), "Unexpected original channel request")
        self.calls.append(tuple(channels))
        return [list(self.rows[C.CHANNELS.index(name)]) for name in channels]


def request_parts(raw, packet):
    require(0 < len(raw) <= MAX_REQUEST_BYTES, "Generated request byte cap")
    value = C.decode(raw)
    content = value["input"][0]["content"]
    header = C.decode(content[0]["text"])
    require(header["family"] == C.FAMILY and header["condition"] == C.VIEWER_CONDITIONS[packet.modality]
            and header["modality"] == packet.modality
            and header["observation"]["target"] == packet.metadata(), "Exact actual request target/modality")
    geometry = header["public_task"]["epoch_geometry"]
    require(geometry["shape"] == [len(packet.channels), C.SAMPLES]
            and geometry["channels"] == list(packet.channels)
            and header["public_task"]["total_epochs"] == C.TOTAL
            and header["public_task"]["people_count"] == 2, "Complete target and two-person task descriptor")
    images = []
    for item in content[1:]:
        require(item["type"] == "input_image" and item["image_url"].startswith("data:image/png;base64,"),
                "Exact image input")
        png = base64.b64decode(item["image_url"].split(",", 1)[1], validate=True)
        require(png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (1400, 820)
                and len(png) <= 131072, "Maintained complete-canvas generated PNG")
        images.append(png)
    require(1 <= len(images) <= 2, "Only target overview and optional detail")
    if packet.modality == C.EEG:
        require(C.CHANNELS[2] not in content[0]["text"] and C.CHANNELS[2] not in str(value["text"]),
                "EOG absent from request metadata and permitted actions")
        require("complete three-channel" not in value["instructions"], "No false three-channel prompt")
    require(value["tools"] == [] and value.get("previous_response_id") is None, "No tool or previous response input")
    return value, header, images


def response(action, response_id):
    return C.encode({"object": "response", "id": response_id, "status": "completed", "error": None,
                     "incomplete_details": None, "model": knowledge()["model"], "tools": [], "tool_choice": "none",
                     "parallel_tool_calls": False, "store": False, "background": False, "truncation": "disabled",
                     "previous_response_id": None, "conversation": None, "max_output_tokens": 256,
                     "output": [{"type": "message", "role": "assistant", "status": "completed",
                                 "content": [{"type": "output_text", "text": C.encode({"viewer_action": action}).decode()}]}],
                     "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}})


class FakeResponse:
    status = 200
    def __init__(self, body):
        require(0 < len(body) <= 8192, "Generated response cap")
        self.body = io.BytesIO(body)
    def read(self, count): return self.body.read(min(count, 73))
    def getheader(self, name, default=None): return "identity"
    def close(self): pass


class FakeHTTPS:
    sock = None
    def __init__(self, owner, host, port, timeout, context):
        require(host == "api.openai.com" and port == 443 and timeout > 0 and context.check_hostname,
                "Actual maintained TLS call interface")
        self.owner = owner
    def set_debuglevel(self, level): require(level == 0, "No credential debug output")
    def request(self, method, path, *, body, headers, encode_chunked):
        require((method, path, encode_chunked) == ("POST", "/v1/responses", False), "Actual maintained request interface")
        require(headers["Authorization"] == "Bearer " + SECRET, "Generated credential only")
        request_parts(body, self.owner.packet)
        self.owner.requests.append(body)
    def getresponse(self):
        require(len(self.owner.responses) == 1, "One selected turn; no retries")
        return FakeResponse(self.owner.responses.pop())
    def close(self): pass


class FakeFactory:
    def __init__(self, packet, body):
        self.packet, self.responses, self.requests = packet, [body], []
    def __call__(self, *args, **kwargs): return FakeHTTPS(self, *args, **kwargs)


def run_controls(bindings_descriptor, dependency_root, control_root):
    root = C.ordinary_path(control_root)
    root.mkdir(mode=0o700, parents=False, exist_ok=False)
    # Actual public main/config refusal; malformed pinned metadata cannot reach
    # source loading, token callback, credential lookup, signals or transport.
    from contextlib import redirect_stdout
    bad_operation = C.write_new(root / "malformed-operation.json", b"{}")
    captured = io.StringIO()
    with redirect_stdout(captured):
        exit_code = P.main(["--operation", "run", "--config", bad_operation["path"],
                            "--bytes", str(bad_operation["bytes"]), "--sha256", bad_operation["sha256"]])
    cli_result = C.decode(captured.getvalue())
    require(exit_code == 2 and cli_result == {"status": "refused_or_failed_no_admission",
            "error_type": "ValueError", "scientific_qualification": False}, "Actual malformed operation CLI refusal")
    runtime = V.load_runtime(bindings_descriptor, dependency_root)
    budget = P.checked_budget(runtime, {"max_turns": 1, "max_images": 2,
        "max_history_bytes": MAX_REQUEST_BYTES, "max_request_bytes": MAX_REQUEST_BYTES,
        "max_response_bytes": 8192, "max_total_provider_bytes": 524288,
        "context_tokens": 131072, "output_tokens": 256, "wall_seconds": 30, "image_detail": "original"})
    packets, projections, shared, refusals, noninterference = {}, {}, [], [], []
    original_channels = runtime["original_viewer"].CHANNELS
    original_mode = runtime["original_viewer"].MODE
    for index, (case, _) in enumerate(C.CASES):
        original = GeneratedPerson(case, index, index * 19)
        for modality in C.MODALITIES:
            packet = C.project_epoch(original, index, modality)
            packets[(case, modality)] = packet
            descriptor = C.write_projection(packet, root / (case + "_" + modality))
            projections[(case, modality)] = descriptor
            reread = C.read_projection(descriptor)
            require(reread.metadata() == packet.metadata() and reread.signals_npy == packet.signals_npy,
                    "Real exact-two-file projection roundtrip")
            require(len(packet.signals_npy) == 128 + len(packet.channels) * C.SAMPLES * 8,
                    "No physical excluded-channel bytes")
        require(original.calls == [C.CHANNELS[:2], C.CHANNELS], "EEG producer never requested EOG")
        eeg, full = (packets[(case, m)] for m in C.MODALITIES)
        shared.append(C.check_shared_epoch(eeg, full))
        refusals.append(rejected(lambda: eeg.samples(0, 3000, list(C.CHANNELS)), "Only available"))
        refusals.append(rejected(lambda: C.RawEpochPacket(eeg.metadata(), full.signals_npy), "Bounded exact NPY"))
        metadata = full.metadata(); metadata["clock_features"]["elapsed_hours"] += 1
        changed = C.RawEpochPacket(metadata, full.signals_npy)
        refusals.append(rejected(lambda: C.check_shared_epoch(eeg, changed), "Identical target"))
        session = V.Session(eeg, runtime, 4, (str(index + 1) * 32))
        overview, pngs = session.initial()
        require(overview["overview"]["state"]["channels"] == list(C.CHANNELS[:2]), "Renderer receives two channels")
        first_request = V.request_bytes(session, knowledge()["model"], budget, knowledge())
        request_parts(first_request, eeg)
        perturbed = GeneratedPerson(case, index, index * 19)
        perturbed.rows[2] = [value * -7 + 0.000123 for value in perturbed.rows[2]]
        perturbed_eeg = C.project_epoch(perturbed, index, C.EEG)
        require(perturbed_eeg.metadata() == eeg.metadata() and perturbed_eeg.signals_npy == eeg.signals_npy,
                "EOG-only changes cannot reach EEG-only participant bytes")
        other_session = V.Session(perturbed_eeg, runtime, 4, str(index + 1) * 32)
        other_session.initial()
        other_request = V.request_bytes(other_session, knowledge()["model"], budget, knowledge())
        require(other_request == first_request, "EOG-only changes cannot reach EEG-only image/request bytes")
        noninterference.append({"epoch_id": eeg.epoch_id, "case": C.pin(C.encode(eeg.metadata())),
                                "signals": C.pin(eeg.signals_npy), "request": C.pin(first_request)})
        refusals.append(rejected(lambda: session.handle({"action": "channels", "channels": list(C.CHANNELS)}),
                                 "Original ordered channel"))
        refusals.append(rejected(lambda: session.handle({"action": "window", "start_sample": 2900, "stop_sample": 3100}),
                                 "Window restricted"))
        session.handle({"action": "window", "start_sample": 400, "stop_sample": 900})
        _, _, detail = request_parts(V.request_bytes(session, knowledge()["model"], budget, knowledge()), eeg)
        require(len(detail) == 2 and detail[0] == pngs[0], "Immutable full epoch remains available with detail")
        accepted = session.handle({"action": "respond", "epoch_id": eeg.epoch_id, "probabilities": [0.2] * 5})
        require(accepted["complete_available_channel_epoch"] and accepted["channel_count"] == 2
                and "full_three_channel_epoch_available" not in accepted, "Truthful two-channel first final")
        refusals.append(rejected(lambda: session.handle({"action": "inspect"}), "Epoch closed"))
    runs, mutation_writes = [], 0
    for index, key in enumerate(((C.CASES[0][0], C.EEG), (C.CASES[1][0], C.EEG_EOG))):
        packet = packets[key]
        action = {"action": "respond", "epoch_id": packet.epoch_id, "probabilities": [0.2] * 5}
        factory = FakeFactory(packet, response(action, "resp_generated_n008_" + str(index)))
        token_calls = []
        def generated_bound(raw, deadline):
            request_parts(raw, packet)
            token_calls.append(C.pin(raw))
            return 65536  # Generated accounting control only, never provider capacity proof.
        custody = root / ("custody_" + str(index))
        end = P.run_epoch(runtime, packet, knowledge(), budget, custody, SECRET, generated_bound,
                          session_id=("a" if index == 0 else "b") * 32, http_factory=factory)
        audit = P.audit_session(custody, packet, runtime, knowledge())
        require(len(factory.requests) == len(token_calls) == 1 and not factory.responses,
                "Exactly one generated first-final exchange")
        require(audit["probabilities"] == action["probabilities"] and audit["modality"] == packet.modality
                and audit["family"] == C.FAMILY and audit["condition"] == C.VIEWER_CONDITIONS[packet.modality],
                "Actual custody audit binds target and modality")
        for flag in ("provider_context_qualified", "provider_capacity_qualified", "token_bound_qualified", "scientific_qualification"):
            require(end[flag] is False and audit[flag] is False, "Generated transport cannot self-qualify")
        require("complete_three_channel_epoch" not in end and end["complete_available_channel_epoch"],
                "Truthful modality terminal receipt")
        if index == 0:
            path = custody / "turns/000000/REQUEST.bin"
            retained = path.read_bytes()
            changed = retained[:-1] + bytes([retained[-1] ^ 1])
            path.write_bytes(changed); mutation_writes += len(changed)
            try:
                refusals.append(rejected(lambda: P.audit_session(custody, packet, runtime, knowledge()), "Exact full overview"))
            finally:
                path.write_bytes(retained); mutation_writes += len(retained)
        runs.append({"packet": packet.metadata(), "end": end, "audit": audit,
                     "request": C.pin(factory.requests[0]), "generated_token_calls": token_calls})
    require(runtime["original_viewer"].CHANNELS == original_channels == C.CHANNELS
            and runtime["original_viewer"].MODE == original_mode == "whole_person_raw_viewer_zero_shot",
            "Unchanged S7 viewer channel and condition globals")
    import sys
    require(sys.modules["_n008_upstream_visual_runtime"].CONDITION == "epoch_isolated_raw_viewer_zero_shot_v1",
            "Unchanged upstream S7 epoch condition namespace")
    stored = sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
    result = {"schema": "neural008_raw_epoch_viewer_generated_control_v1", "status": "pass",
              "scope": "two_people_four_generated_projections_two_one_turn_fake_https_sessions",
              "generated_only": True, "original_signal_reads": 0, "real_provider_calls": 0,
              "public_cli_refusal": {"exit_code": exit_code, "result": cli_result},
              "token_capacity_qualified": False, "scientific_qualification": False,
              "shared_epoch_checks": shared, "eog_noninterference": noninterference,
              "refusals": refusals, "runs": runs,
              "retained_bytes_before_result": stored, "mutation_write_bytes": mutation_writes,
              "cumulative_bytes_before_result": stored + mutation_writes,
              "generated_write_cap": MAX_GENERATED_BYTES}
    raw = C.encode(result)
    require(len(raw) <= 65536 and stored + mutation_writes + len(raw) <= MAX_GENERATED_BYTES,
            "Finite generated artifact forecast")
    C.write_new(root / "VIEWER_RESULT.json", raw)
    return result
