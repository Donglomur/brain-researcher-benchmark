"""Fresh-process numerical-waveform delivery; no provider or scientific qualification.

The trusted operator owns paths and executable choice. Participant stdout is a
single bounded scalar-response frame, never an operator command or filename.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import struct
import subprocess
import sys
import tempfile
import time
import uuid

HERE = Path(__file__).resolve().parent
PREFIX = struct.Struct("!I")
RESPONSE_CAP = 4096
CLIENT_CAP = 1048576
CONDITIONS = ("legacy_waveform_no_tools", "matched_waveform_programme")
SOURCE_PINS = {
    "complete-direct-condition-v1/delivery.py": (16152, "382dd03d79c7b8c94eba799dd171c0fbfede294eeb9d01a790539c6901bcdc99"),
    "complete-direct-condition-v1/SOURCE_BINDINGS.json": (708, "ee559cbeefa5039bdac526ec416575d78c80d2cba07144a41e649e2f8b69081a"),
    "direct-response/portable/response_contract.py": (2210, "5f992a42a2c29905a792a11a9062ca18cdc0c73581013cc125544bf1f6758700"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def encode(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode()


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite JSON")))


def unlinked(path):
    path = Path(path).absolute()
    require(all(not p.is_symlink() for p in (path, *path.parents)), "Linked path refused")
    return path


def read(path, cap, empty=False):
    path = unlinked(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and (0 if empty else 1) <= before.st_size <= cap, "Bounded ordinary single-link file required")
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        fields = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns, s.st_nlink)
        require(len(body) == before.st_size and fields(before) == fields(after) == fields(path.lstat()),
                "Input changed during capture")
    return body


def write(path, body):
    with Path(path).open("xb") as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    Path(path).chmod(0o400)


def dependencies():
    bodies = {}
    for relative, (size, sha) in SOURCE_PINS.items():
        body = read(HERE.parent / relative, size)
        require(pin(body) == {"bytes": size, "sha256": sha}, "Changed delivery dependency")
        bodies[relative] = body
    loaded = []
    for name, relative in (("delivery", "complete-direct-condition-v1/delivery.py"),
                           ("response", "direct-response/portable/response_contract.py")):
        spec = importlib.util.spec_from_loader("neural077_waveform_" + name, loader=None)
        module = importlib.util.module_from_spec(spec)
        module.__file__ = str(HERE.parent / relative)
        exec(compile(bodies[relative], module.__file__, "exec"), module.__dict__)
        loaded.append(module)
    return tuple(loaded)


@dataclass(frozen=True)
class Limits:
    max_prompt_bytes: int = 1048576
    wall_seconds: float = 300
    campaign_seconds: float = 86400

    def validate(self):
        require(type(self.max_prompt_bytes) is int and 1 <= self.max_prompt_bytes <= 2097152,
                "Prompt cap must be within 1..2097152 bytes")
        for value, maximum in ((self.wall_seconds, 3600), (self.campaign_seconds, 86400)):
            require(type(value) in (int, float) and math.isfinite(value) and 0 < value <= maximum,
                    "Finite positive bounded wall limit required")


class WireFailure(Exception):
    def __init__(self, reason, captured=b""):
        self.reason, self.captured = reason, captured
        super().__init__(reason)


def wait_fd(fd, event, deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise WireFailure("deadline")
    with selectors.DefaultSelector() as selector:
        selector.register(fd, event)
        if not selector.select(remaining):
            raise WireFailure("deadline")


def read_frame(fd, deadline):
    body = bytearray()
    def take(size):
        while len(body) < size:
            try:
                wait_fd(fd, selectors.EVENT_READ, deadline)
                chunk = os.read(fd, size - len(body))
            except BlockingIOError:
                continue
            except WireFailure as exc:
                raise WireFailure(exc.reason, bytes(body)) from None
            if not chunk:
                raise WireFailure("response_eof", bytes(body))
            body.extend(chunk)
    take(PREFIX.size)
    length = PREFIX.unpack(body)[0]
    if not 0 < length <= RESPONSE_CAP:
        raise WireFailure("response_length", bytes(body))
    take(PREFIX.size + length)
    return bytes(body)


def write_frame(fd, body, deadline):
    count = 0
    try:
        while count < len(body):
            wait_fd(fd, selectors.EVENT_WRITE, deadline)
            try:
                count += os.write(fd, body[count:])
            except BlockingIOError:
                continue
    except (OSError, WireFailure):
        raise WireFailure("prompt_not_delivered", body[:count]) from None
    return count


def sandbox_profile(script):
    require(sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file(),
            "macOS sandbox-exec required")
    quoted = json.dumps(str(script))
    return ('(version 1) (deny default) (deny sysctl* process-info* network* process-fork) '
            '(allow process-info* (target self)) (allow process-exec) (allow file-read-metadata) '
            '(allow sysctl-read (sysctl-name "kern.ostype") (sysctl-name "kern.osrelease") '
            '(sysctl-name "kern.version") (sysctl-name "kern.hostname") (sysctl-name "hw.machine")) '
            '(allow file-read-data (literal "/") (subpath "/System") (subpath "/usr") '
            '(subpath "/Library/Frameworks") (literal "/dev/null") (literal "/dev/urandom") '
            '(literal "/dev/random") (literal ' + quoted + '))')


def configuration(client, python, sandbox, limits):
    limits.validate()
    require(sandbox in ("macos", "protocol_only"), "Unknown sandbox")
    client = unlinked(client)
    body = read(client, CLIENT_CAP)
    python = Path(python).resolve(strict=True)
    require(python.is_file() and os.access(python, os.X_OK), "Executable interpreter required")
    if sandbox == "macos":
        require(any(python.is_relative_to(Path(root)) for root in
                    ("/System", "/usr", "/Library/Frameworks")), "Interpreter outside sandbox runtime roots")
    return client, python, {"client": pin(body), "python": str(python), "sandbox": sandbox,
                            "limits": asdict(limits), "provider_context_qualified": False,
                            "provider_tool_policy_qualified": False,
                            "provider_capacity_qualified": False,
                            "memory_limit_enforced": False, "cpu_limit_enforced": False,
                            "private_target_reads": 0, "scientific_qualification": False}


def row_prompt(row, condition, limits):
    require(condition in CONDITIONS, "Unknown waveform condition")
    require(type(row) is dict and set(row) == {"ordinal", "trial_id", "context_sha256", "prompt"},
            "Exact operator context required")
    require(type(row["ordinal"]) is int and 0 <= row["ordinal"] < 400
            and type(row["trial_id"]) is str and 1 <= len(row["trial_id"]) <= 48
            and type(row["prompt"]) is str, "Invalid operator context")
    prompt = row["prompt"].encode("utf-8")
    require(0 < len(prompt) <= limits.max_prompt_bytes and pin(prompt)["sha256"] == row["context_sha256"],
            "Prompt capacity or identity mismatch; truncation forbidden")
    return prompt


def _episode(row, condition, output, client, python, sandbox, limits, expected_client,
             campaign_deadline=None):
    output = unlinked(output)
    output.mkdir(mode=0o700)
    prompt = row_prompt(row, condition, limits)
    _, python, config = configuration(client, python, sandbox, limits)
    require(config["client"] == expected_client, "Client changed after campaign commitment")
    profile = sandbox_profile(client) if sandbox == "macos" else None
    manifest = {"schema": "neural077_waveform_episode_v1", "condition": condition,
                "ordinal": row["ordinal"], "trial_id": row["trial_id"],
                "context_sha256": row["context_sha256"], "episode_id": uuid.uuid4().hex,
                "configuration": config, "sandbox_profile": pin(profile.encode()) if profile else None}
    write(output / "MANIFEST.json", encode(manifest))
    if profile:
        write(output / "sandbox.sb", profile.encode())
    frame = PREFIX.pack(len(prompt)) + prompt
    started = time.monotonic()
    deadline = started + limits.wall_seconds
    if campaign_deadline is not None:
        deadline = min(deadline, campaign_deadline)
    sent = received = b""
    reason, response, child, forced, cleanup, response_complete = None, None, None, False, True, False
    try:
        if deadline <= time.monotonic():
            raise WireFailure("campaign_deadline_not_started")
        with tempfile.TemporaryDirectory(prefix="neural077-waveform-") as cwd:
            command = [str(python), "-I", "-S", "-B", str(client)]
            if profile:
                command = ["/usr/bin/sandbox-exec", "-p", profile, *command]
            child = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, cwd=cwd,
                                     env={"LANG": "C", "LC_ALL": "C"}, close_fds=True, start_new_session=True)
            os.set_blocking(child.stdin.fileno(), False)
            os.set_blocking(child.stdout.fileno(), False)
            try:
                write_frame(child.stdin.fileno(), frame, deadline)
                sent = frame
            except WireFailure as exc:
                sent = exc.captured
                raise
            child.stdin.close()
            try:
                received = read_frame(child.stdout.fileno(), deadline)
                response_complete = True
            except WireFailure as exc:
                received = exc.captured
                raise
            # First complete response frame is final even if its JSON is invalid.
            # Never read a second frame or replace the first response.
            child.stdout.close()
            _, parser = dependencies()
            try:
                parser.parse(received[PREFIX.size:], row["trial_id"])
                response = received[PREFIX.size:].decode("utf-8")
            except (ValueError, TypeError, UnicodeError, RecursionError):
                raise WireFailure("invalid_response") from None
            remaining = min(2.0, deadline - time.monotonic())
            if remaining <= 0:
                raise WireFailure("deadline")
            try:
                child.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                raise WireFailure("client_did_not_exit") from None
            if child.returncode != 0:
                raise WireFailure("client_failed_after_final")
    except WireFailure as exc:
        reason = exc.reason
    except Exception:
        reason = "operator_failure"
    finally:
        if child is not None:
            forced = child.poll() is None
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            except PermissionError:
                if child.poll() is None:
                    child.kill()
            try:
                child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                cleanup = False
            for stream in (child.stdin, child.stdout):
                if not stream.closed:
                    stream.close()
        if not cleanup:
            reason = "client_cleanup_unverified"
        envelope = {key: row[key] for key in ("ordinal", "trial_id", "context_sha256")}
        envelope.update(status="ok" if reason is None else "error",
                        response=response if reason is None else None, error=reason)
        write(output / "INPUT.bin", sent)
        write(output / "OUTPUT.bin", received)
        write(output / "ATTEMPT.json", encode(envelope))
        receipt = {"schema": "neural077_waveform_episode_end_v1", "status": envelope["status"],
                   "reason": reason, "launched": child is not None,
                   "client_pid": child.pid if child else None,
                   "client_exit_code": child.returncode if child else None,
                   "client_forced_stop": forced, "direct_child_reaped": cleanup,
                   "descendant_absence_verified": False, "input": pin(sent), "output": pin(received),
                   "input_complete": sent == frame, "output_complete": response_complete,
                   "manifest": pin(encode(manifest)), "attempt": pin(encode(envelope)),
                   "elapsed_seconds": time.monotonic() - started,
                   "scoring_performed": False, "response_frames_accepted": int(response_complete)}
        write(output / "END.json", encode(receipt))
    return envelope, receipt


def run_episode(row, condition, output, client, python=sys.executable, sandbox="protocol_only", limits=None):
    limits = limits or Limits()
    client, python, config = configuration(client, python, sandbox, limits)
    return _episode(row, condition, output, client, python, sandbox, limits, config["client"])


def contexts(delivery_root, condition):
    delivery, _ = dependencies()
    modules = delivery.dependencies()
    members = delivery.packet_members(unlinked(delivery_root) / "public", modules["exporter"])
    rows = list(delivery.context_rows(members, condition))
    require(len(rows) == 400 and [row["ordinal"] for row in rows] == list(range(400)),
            "Complete original ordered query inventory required")
    return rows


def run_campaign(delivery_root, condition, output, client, python=sys.executable,
                 sandbox="macos", limits=None):
    limits = limits or Limits()
    client, python, config = configuration(client, python, sandbox, limits)
    rows = contexts(delivery_root, condition)
    for row in rows:
        row_prompt(row, condition, limits)
    output = unlinked(output)
    output.mkdir(mode=0o700)
    frozen_client = output / "CLIENT.py"
    body = read(client, CLIENT_CAP)
    require(pin(body) == config["client"], "Client changed before campaign capture")
    write(frozen_client, body)
    # Read-only to the participant; selected only from the committed bytes.
    manifest = {"schema": "neural077_waveform_campaign_v1", "task_id": "NEURAL-077",
                "condition": condition, "queries": 400, "configuration": config,
                "implementation": {"transport.py": pin(read(HERE / "transport.py", 65536))},
                "source_dependencies": {name: {"bytes": item[0], "sha256": item[1]}
                                        for name, item in SOURCE_PINS.items()},
                "retry_policy": "none", "fresh_process_per_query": True,
                "first_response_is_final": True, "provider_context_qualified": False,
                "model_performance_measured": False}
    write(output / "MANIFEST.json", encode(manifest))
    started = time.monotonic()
    receipts = []
    try:
        with (output / "attempts.jsonl").open("xb") as ledger:
            for row in rows:
                envelope, receipt = _episode(row, condition, output / f'{row["ordinal"]:03d}',
                                            frozen_client, python, sandbox, limits, config["client"],
                                            started + limits.campaign_seconds)
                ledger.write(encode(envelope))
                ledger.flush()
                os.fsync(ledger.fileno())
                receipts.append(receipt)
        (output / "attempts.jsonl").chmod(0o400)
        result = {"schema": "neural077_waveform_campaign_end_v1", "status": "complete_attempt_inventory",
                  "queries": 400, "launched": sum(r["launched"] for r in receipts),
                  "successful": sum(r["status"] == "ok" for r in receipts),
                  "failed_or_not_started": sum(r["status"] != "ok" for r in receipts),
                  "attempts": pin(read(output / "attempts.jsonl", 400 * 16384)),
                  "episode_ends": [pin(read(output / f"{i:03d}" / "END.json", 16384)) for i in range(400)],
                  "manifest": pin(encode(manifest)), "elapsed_seconds": time.monotonic() - started,
                  "private_target_reads": 0, "scoring_performed": False}
        write(output / "COMPLETE.json", encode(result))
        return result
    except Exception as exc:
        write(output / "FAILED.json", encode({"status": "campaign_incomplete", "completed_episodes": len(receipts),
                                               "reason": type(exc).__name__, "scoring_performed": False}))
        raise


def audit_episode(path, row, condition, configuration_record):
    path = unlinked(path)
    expected = {"MANIFEST.json", "INPUT.bin", "OUTPUT.bin", "ATTEMPT.json", "END.json"}
    if configuration_record["sandbox"] == "macos":
        expected.add("sandbox.sb")
    require({p.name for p in path.iterdir()} == expected, "Missing or unexpected episode member")
    manifest_body = read(path / "MANIFEST.json", 16384)
    manifest = decode(manifest_body)
    require(set(manifest) == {"schema", "condition", "ordinal", "trial_id", "context_sha256", "episode_id",
                              "configuration", "sandbox_profile"}, "Exact episode manifest required")
    require(manifest["schema"] == "neural077_waveform_episode_v1" and manifest["condition"] == condition
            and manifest["configuration"] == configuration_record
            and all(manifest[key] == row[key] for key in ("ordinal", "trial_id", "context_sha256")),
            "Episode identity/configuration mismatch")
    require(type(manifest["episode_id"]) is str and len(manifest["episode_id"]) == 32
            and all(c in "0123456789abcdef" for c in manifest["episode_id"]), "Invalid episode identity")
    limits = Limits(**configuration_record["limits"])
    prompt = row_prompt(row, condition, limits)
    incoming = read(path / "INPUT.bin", limits.max_prompt_bytes + PREFIX.size, empty=True)
    require(incoming == PREFIX.pack(len(prompt)) + prompt, "Delivered prompt differs from complete original")
    outgoing = read(path / "OUTPUT.bin", RESPONSE_CAP + PREFIX.size, empty=True)
    require(len(outgoing) > PREFIX.size and PREFIX.unpack(outgoing[:PREFIX.size])[0] == len(outgoing) - PREFIX.size,
            "Incomplete response framing")
    _, parser = dependencies()
    parser.parse(outgoing[PREFIX.size:], row["trial_id"])
    attempt_body = read(path / "ATTEMPT.json", 16384)
    expected_attempt = {key: row[key] for key in ("ordinal", "trial_id", "context_sha256")}
    expected_attempt.update(status="ok", response=outgoing[PREFIX.size:].decode("utf-8"), error=None)
    require(decode(attempt_body) == expected_attempt, "Attempt differs from first captured response")
    end = decode(read(path / "END.json", 16384))
    require(set(end) == {"schema", "status", "reason", "launched", "client_pid", "client_exit_code",
                        "client_forced_stop", "direct_child_reaped", "descendant_absence_verified", "input", "output",
                        "input_complete", "output_complete", "manifest", "attempt", "elapsed_seconds",
                        "scoring_performed", "response_frames_accepted"}, "Exact episode end schema required")
    require(end["schema"] == "neural077_waveform_episode_end_v1" and end["status"] == "ok"
            and end["reason"] is None and end["launched"] is True
            and type(end["client_pid"]) is int and end["client_pid"] > 0
            and type(end["client_exit_code"]) is int and end["client_exit_code"] == 0
            and end["client_forced_stop"] is False and end["direct_child_reaped"] is True
            and end["descendant_absence_verified"] is False and end["input_complete"] is True
            and end["output_complete"] is True and end["scoring_performed"] is False
            and type(end["response_frames_accepted"]) is int and end["response_frames_accepted"] == 1,
            "Failed or incomplete process receipt")
    require(type(end["elapsed_seconds"]) in (int, float) and math.isfinite(end["elapsed_seconds"])
            and end["elapsed_seconds"] >= 0, "Invalid elapsed time")
    require(end["input"] == pin(incoming) and end["output"] == pin(outgoing)
            and end["manifest"] == pin(manifest_body) and end["attempt"] == pin(attempt_body), "Episode hash mismatch")
    if configuration_record["sandbox"] == "macos":
        profile = read(path / "sandbox.sb", 8192)
        require(pin(profile) == manifest["sandbox_profile"], "Sandbox profile hash mismatch")
        require(profile == sandbox_profile(path.parent / "CLIENT.py").encode(), "Changed sandbox profile")
    else:
        require(manifest["sandbox_profile"] is None, "Unexpected sandbox profile")
    return expected_attempt, manifest["episode_id"]


def collect(delivery_root, condition, campaign, output):
    campaign = unlinked(campaign)
    rows = contexts(delivery_root, condition)
    manifest_body = read(campaign / "MANIFEST.json", 16384)
    manifest = decode(manifest_body)
    require(set(manifest) == {"schema", "task_id", "condition", "queries", "configuration", "implementation",
                              "source_dependencies", "retry_policy", "fresh_process_per_query", "first_response_is_final",
                              "provider_context_qualified", "model_performance_measured"}, "Exact campaign manifest required")
    require(manifest["schema"] == "neural077_waveform_campaign_v1" and manifest["task_id"] == "NEURAL-077"
            and manifest["condition"] == condition and type(manifest["queries"]) is int and manifest["queries"] == 400
            and manifest["retry_policy"] == "none" and manifest["fresh_process_per_query"] is True
            and manifest["first_response_is_final"] is True and manifest["provider_context_qualified"] is False
            and manifest["model_performance_measured"] is False, "Wrong campaign identity/policy")
    require(manifest["implementation"] == {"transport.py": pin(read(HERE / "transport.py", 65536))}
            and manifest["source_dependencies"] == {name: {"bytes": item[0], "sha256": item[1]}
                                                    for name, item in SOURCE_PINS.items()}, "Campaign source mismatch")
    config = manifest["configuration"]
    require(type(config) is dict and type(config.get("limits")) is dict, "Configuration required")
    limits = Limits(**config["limits"])
    _, _, expected_config = configuration(campaign / "CLIENT.py", config["python"], config["sandbox"], limits)
    require(config == expected_config, "Changed campaign configuration/client")
    expected_members = {f"{i:03d}" for i in range(400)} | {"CLIENT.py", "MANIFEST.json", "attempts.jsonl", "COMPLETE.json"}
    require({p.name for p in campaign.iterdir()} == expected_members, "Incomplete or altered campaign inventory")
    complete = decode(read(campaign / "COMPLETE.json", 131072))
    require(type(complete) is dict and type(complete.get("episode_ends")) is list
            and len(complete["episode_ends"]) == 400, "Complete episode-end commitments required")
    attempts, episodes = [], set()
    for row in rows:
        require(pin(read(campaign / f'{row["ordinal"]:03d}' / "END.json", 16384))
                == complete["episode_ends"][row["ordinal"]], "Changed episode-end receipt")
        attempt, episode = audit_episode(campaign / f'{row["ordinal"]:03d}', row, condition, config)
        require(episode not in episodes, "Repeated episode identity")
        episodes.add(episode)
        attempts.append(attempt)
    ledger = read(campaign / "attempts.jsonl", 400 * 16384)
    require(ledger == b"".join(encode(attempt) for attempt in attempts), "Ledger differs from complete transport records")
    require(set(complete) == {"schema", "status", "queries", "launched", "successful", "failed_or_not_started",
                              "attempts", "episode_ends", "manifest", "elapsed_seconds", "private_target_reads", "scoring_performed"},
            "Exact complete campaign receipt required")
    require(complete["schema"] == "neural077_waveform_campaign_end_v1"
            and complete["status"] == "complete_attempt_inventory"
            and all(type(complete[key]) is int and complete[key] == 400 for key in ("queries", "launched", "successful"))
            and type(complete["failed_or_not_started"]) is int and complete["failed_or_not_started"] == 0
            and complete["private_target_reads"] == 0 and complete["scoring_performed"] is False
            and complete["attempts"] == pin(ledger) and complete["manifest"] == pin(manifest_body),
            "Campaign did not complete every query successfully")
    require(type(complete["elapsed_seconds"]) in (int, float) and math.isfinite(complete["elapsed_seconds"])
            and complete["elapsed_seconds"] >= 0, "Invalid campaign elapsed time")
    delivery, _ = dependencies()
    admitted = delivery.collect(delivery_root, condition, campaign / "attempts.jsonl", output)
    receipt = {"schema": "neural077_waveform_transport_collection_v1", "condition": condition,
               "status": "complete_unscored_transport_collection", "queries": 400,
               "campaign_manifest": pin(manifest_body), "attempts": pin(ledger),
               "submission": admitted["submission"], "configuration": config,
               "local_transcript_replayed": True, "provider_context_qualified": False,
               "provider_tool_policy_qualified": False, "scientific_qualification": False,
               "private_target_reads": 0, "scoring_performed": False}
    write(Path(output) / "TRANSPORT_COMPLETE.json", encode(receipt))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    campaign = commands.add_parser("campaign")
    for name in ("delivery-root", "output", "client", "python"):
        campaign.add_argument("--" + name, required=True)
    campaign.add_argument("--condition", choices=CONDITIONS, required=True)
    campaign.add_argument("--sandbox", choices=("macos", "protocol_only"), default="macos")
    campaign.add_argument("--max-prompt-bytes", type=int, default=1048576)
    campaign.add_argument("--wall-seconds", type=float, required=True)
    campaign.add_argument("--campaign-seconds", type=float, required=True)
    admission = commands.add_parser("collect")
    for name in ("delivery-root", "campaign", "output"):
        admission.add_argument("--" + name, required=True)
    admission.add_argument("--condition", choices=CONDITIONS, required=True)
    args = vars(parser.parse_args(argv))
    action = args.pop("action")
    if action == "campaign":
        args["limits"] = Limits(**{key: args.pop(key) for key in ("max_prompt_bytes", "wall_seconds", "campaign_seconds")})
    try:
        result = run_campaign(**args) if action == "campaign" else collect(**args)
    except (ValueError, OSError, TypeError, KeyError, UnicodeError) as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}))
        return 2
    print(json.dumps(result, allow_nan=False))
    return 0 if action == "collect" or result["failed_or_not_started"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
