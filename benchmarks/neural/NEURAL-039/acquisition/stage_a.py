"""Bounded Movie10 metadata verification; never retrieves an annex payload."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import signal
import socket
import ssl
import stat
import sys
import time
from urllib.parse import urlsplit

REVISION = "96750e7017b30cb02f011c11561a3df897695853"
REPOSITORY = "https://github.com/courtois-neuromod/algonauts_2025.competitors"
PREFIX = "https://raw.githubusercontent.com/courtois-neuromod/algonauts_2025.competitors/" + REVISION + "/"
ORIGINALS = (
    ("sub-01", 92248907, "679e60674df5d669e09467c3a84fbba1", "v2/g2", "40047fdf418dfea06a7435eb2690d750ec99f3eb"),
    ("sub-02", 92262363, "5fc31c031b40e5c032c145816dedeb3d", "V0/G6", "480814bec3bbfdf7a05d62fdeecb6137b16b248f"),
    ("sub-03", 92197356, "3748698c8261e92bf3be29944829543b", "KV/QJ", "cc42fbfc511d72512605886d4455679da19c0602"),
    ("sub-05", 92241379, "1b16eaea10be5a58052b891806cf10e6", "F5/6w", "634e57160c2482ba706e1233fab185f3caf8d99f"),
)
LIMITS = {"requests": 12, "received_http_plaintext_bytes": 16777216,
          "wall_seconds": 300, "address_space_bytes": 536870912,
          "result_bytes": 65536, "header_framing_allowance_bytes": 65536}


class Refusal(Exception):
    pass


def require(condition, code):
    if not condition:
        raise Refusal(code)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(body):
    return hashlib.sha256(body).hexdigest()


def original(subject):
    row = next(x for x in ORIGINALS if x[0] == subject)
    _, size, md5, directory, blob = row
    key = f"MD5E-s{size}--{md5}.h5"
    text = f"../../../.git/annex/objects/{directory}/{key}/{key}".encode("ascii")
    require(hashlib.sha1(b"blob 137\0" + text).hexdigest() == blob, "internal_pointer_pin")
    path = (f"fmri/{subject}/func/{subject}_task-movie10_space-MNI152NLin2009cAsym_"
            "atlas-Schaefer18_parcel-1000Par7Net_bold.h5")
    return {"subject": subject, "source_path": path, "annex_key": key,
            "payload_bytes_declared": size, "payload_md5_declared": md5,
            "pointer_git_blob_sha1": blob}, text


def expected_policy():
    requests = [{"id": "readme", "url": PREFIX + "README.md", "bytes": 25452,
                 "sha256": "cd03b3a9d0b8bee3c95588a5252a5998b1f64624fa35b378b58ed7cf94443896"}]
    for subject, *_ in ORIGINALS:
        item, body = original(subject)
        requests.append({"id": subject, "url": PREFIX + item["source_path"],
                         "bytes": len(body), "sha256": sha(body)})
    return {"schema": "neural039-stagea-request-policy-v1", "task_id": "NEURAL-039",
            "source_commit": REVISION, "method": "GET", "redirects": "reject",
            "retries": 0, "payload_requests": 0, "limits": LIMITS,
            "requests": requests}


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate_json_key")
        value[key] = item
    return value


def parse(body):
    try:
        return json.loads(body, object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(Refusal("json_constant")))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise Refusal("invalid_json") from exc


def ordinary(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink_path")
    return path


def bounded_file(path, cap=131072):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and 0 < before.st_size <= cap, "input_file_kind_or_size")
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(len(body) == before.st_size and stamp(before) == stamp(after)
                == stamp(path.lstat()), "input_file_changed")
        return body


def validate_policy(body):
    value = parse(body)
    require(canonical(value) == canonical(expected_policy()), "request_policy_differs")
    return value


class Budget:
    def __init__(self, limits=None, clock=time.monotonic):
        self.limits = dict(LIMITS if limits is None else limits)
        self.clock = clock
        self.started = clock()
        self.deadline = self.started + self.limits["wall_seconds"]
        self.attempts = 0
        self.received = 0
        self.records = []

    def remaining(self):
        remaining = self.deadline - self.clock()
        require(remaining > 0, "deadline_exhausted")
        return remaining

    def begin(self, request):
        self.remaining()
        require(self.attempts < self.limits["requests"], "request_budget_exhausted")
        self.attempts += 1
        record = {"id": request["id"], "attempt": self.attempts,
                  "http_plaintext_bytes": 0, "body_bytes": 0,
                  "status": None, "verified": False, "cleanup_errors": []}
        self.records.append(record)
        return record

    def allowance(self, record, request):
        self.remaining()
        total = self.limits["received_http_plaintext_bytes"] - self.received
        local = (request["bytes"] + 1 + self.limits["header_framing_allowance_bytes"]
                 - record["http_plaintext_bytes"])
        require(min(total, local) > 0, "receive_budget_exhausted")
        return min(total, local)

    def charge(self, count, record):
        require(type(count) is int and count >= 0, "invalid_byte_count")
        self.received += count
        record["http_plaintext_bytes"] += count
        require(self.received <= self.limits["received_http_plaintext_bytes"], "receive_budget_exhausted")
        self.remaining()


class CountedRaw(io.RawIOBase):
    """Count actual decrypted socket reads, including HTTP framing and headers."""
    def __init__(self, sock, budget, request, record):
        super().__init__()
        self.sock, self.budget, self.request, self.record = sock, budget, request, record
        # Keep the socket's file reference alive when HTTPConnection releases a
        # Connection: close response after its headers, before its body is read.
        self.raw = sock.makefile("rb", buffering=0)

    def readable(self):
        return True

    def readinto(self, buffer):
        allowance = self.budget.allowance(self.record, self.request)
        self.sock.settimeout(min(10.0, self.budget.remaining()))
        data = self.raw.read(min(len(buffer), allowance))
        self.budget.charge(len(data), self.record)
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        try:
            self.raw.close()
        finally:
            super().close()


class ReaderSocket:
    def __init__(self, sock, budget, request, record):
        self.sock, self.budget, self.request, self.record = sock, budget, request, record

    def makefile(self, mode):
        require(mode == "rb", "unexpected_transport_mode")
        return io.BufferedReader(CountedRaw(self.sock, self.budget, self.request, self.record), 4096)


class HTTPTransport:
    @contextmanager
    def open(self, request, budget, record):
        allowed = {x["url"] for x in expected_policy()["requests"]}
        require(request["url"] in allowed, "endpoint_not_allowlisted")
        url = urlsplit(request["url"])
        conn = http.client.HTTPSConnection(url.hostname, 443,
                                          timeout=min(10.0, budget.remaining()),
                                          context=ssl.create_default_context())
        # No urllib redirect handler, proxy environment, cookies or auth support.
        conn.response_class = lambda sock, **kw: http.client.HTTPResponse(
            ReaderSocket(sock, budget, request, record), **kw)
        response = None
        try:
            conn.request("GET", url.path, headers={"Accept-Encoding": "identity",
                         "Connection": "close", "User-Agent": "NEURAL-039-StageA/1"})
            budget.remaining()
            response = conn.getresponse()
            yield response
        finally:
            for obj in (response, conn):
                if obj is not None:
                    try:
                        obj.close()
                    except Exception as exc:
                        record["cleanup_errors"].append(type(exc).__name__[:48])


def fetch(request, transport, budget):
    record = budget.begin(request)
    try:
        with transport.open(request, budget, record) as response:
            record["status"] = response.status
            require(response.status == 200, "http_status_rejected")
            encoding = response.getheader("Content-Encoding", "identity").strip().lower()
            require(encoding == "identity", "content_encoding_rejected")
            length = response.getheader("Content-Length")
            transfer = response.getheader("Transfer-Encoding")
            require(not (length is not None and transfer is not None), "conflicting_http_framing")
            if length is not None:
                require(re.fullmatch(r"[0-9]+", length) is not None
                        and int(length) == request["bytes"], "declared_extent_differs")
            chunks = []
            while record["body_bytes"] <= request["bytes"]:
                budget.remaining()
                part = response.read(min(4096, request["bytes"] + 1 - record["body_bytes"]))
                record["body_bytes"] += len(part)
                budget.remaining()
                if not part:
                    break
                chunks.append(part)
            body = b"".join(chunks)
            require(len(body) == request["bytes"], "body_extent_differs")
            require(sha(body) == request["sha256"], "body_digest_differs")
        require(not record["cleanup_errors"], "transport_cleanup_failed")
        record["verified"] = True
        record["sha256"] = request["sha256"]
        return body
    except Refusal as exc:
        record["failure"] = str(exc)
        raise
    except Exception as exc:
        record["failure"] = "transport_error"
        record["exception_class"] = type(exc).__name__[:48]
        raise Refusal("transport_error") from exc


def resolve_logical_routes(bodies):
    require(b"DataLad" in bodies["readme"] and
            ("datalad install -r -s " + REPOSITORY + ".git").encode() in bodies["readme"],
            "documented_route_not_present")
    routes = []
    for subject, *_ in ORIGINALS:
        item, pointer = original(subject)
        require(bodies[subject] == pointer, "pointer_identity_differs")
        routes.append({**item, "kind": "organizer_datalad_repository_path",
                       "repository": REPOSITORY, "revision": REVISION,
                       "payload_url": None, "payload_sha256": None,
                       "physical_transport_status": "unresolved",
                       "payload_get_authorized": False})
    return routes


def collect(requests, transport, budget):
    """Internal generated-test seam. CLI accepts only expected_policy()."""
    result = {"schema": "neural039-stagea-result-v1", "task_id": "NEURAL-039",
              "source_commit": REVISION, "metadata_complete": False,
              "physical_payload_transport_ready": False, "b_c_admitted": False,
              "routes": [], "failure": None}
    try:
        bodies = {r["id"]: fetch(r, transport, budget) for r in requests}
        result["routes"] = resolve_logical_routes(bodies)
        result["metadata_complete"] = True
        result["status"] = "metadata_verified_physical_transport_unresolved"
    except Refusal as exc:
        result["status"], result["failure"] = "failed", str(exc)
    except Exception as exc:
        result["status"], result["failure"] = "failed", "operator_error"
        result["exception_class"] = type(exc).__name__[:48]
    result["requests"] = budget.records
    result["cost"] = {"attempts": budget.attempts,
                      "received_http_plaintext_bytes": budget.received,
                      "elapsed_seconds": max(0.0, budget.clock() - budget.started)}
    result["limits"] = budget.limits
    result["scope"] = "Four Movie10 subjects/all1000 native parcels/16 strict_v2 development cases unchanged; no full audiovisual or hidden-six-film OOD admission."
    return result


def validate_admission(body, policy_body, source_body, output):
    value = parse(body)
    fields = {"schema", "task_id", "stage", "decision", "operation_id", "source_sha256",
              "policy_sha256", "output", "limits", "runtime_profile"}
    require(type(value) is dict and set(value) == fields, "admission_fields")
    require(value["schema"] == "neural039-stagea-admission-v1" and value["task_id"] == "NEURAL-039"
            and value["stage"] == "A" and value["decision"] == "root_selected_authentic_metadata", "not_admitted")
    require(type(value["operation_id"]) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", value["operation_id"]), "operation_id")
    require(value["source_sha256"] == sha(source_body) and value["policy_sha256"] == sha(policy_body), "admission_source_identity")
    require(value["output"] == str(output) and Path(value["output"]).is_absolute(), "admission_output")
    require(canonical(value["limits"]) == canonical(LIMITS) and value["runtime_profile"] == "linux-rlimit-as-sigalrm-default-v1", "admission_profile")
    return value


def install_limits(resource_module=None, signal_module=signal, platform=sys.platform):
    require(platform == "linux", "linux_runtime_required")
    if resource_module is None:
        import resource as resource_module
    resource_module.setrlimit(resource_module.RLIMIT_AS,
                              (LIMITS["address_space_bytes"],) * 2)
    resource_module.setrlimit(resource_module.RLIMIT_FSIZE, (LIMITS["result_bytes"],) * 2)
    require(resource_module.getrlimit(resource_module.RLIMIT_AS) == (LIMITS["address_space_bytes"],) * 2
            and resource_module.getrlimit(resource_module.RLIMIT_FSIZE) == (LIMITS["result_bytes"],) * 2,
            "resource_limit_not_installed")
    # The OS default action terminates the process; no Python catch or cleanup
    # can swallow the hard deadline. A qualified outer SIGKILL watchdog must
    # bound interpreter startup too, as specified by the admission packet.
    signal_module.signal(signal_module.SIGALRM, signal_module.SIG_DFL)
    signal_module.setitimer(signal_module.ITIMER_REAL, LIMITS["wall_seconds"])


def reserve_output(path):
    path = ordinary(path)
    return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)


def write_result(fd, result):
    body = canonical(result)
    require(len(body) <= LIMITS["result_bytes"], "result_size_exceeded")
    position = 0
    while position < len(body):
        written = os.write(fd, body[position:])
        require(written > 0, "result_short_write")
        position += written
    os.fsync(fd)
    return len(body)


def main(argv=None):
    install_limits()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    output = ordinary(args.output)
    source = bounded_file(__file__)
    policy_body = bounded_file(Path(__file__).with_name("REQUEST_POLICY.json"))
    policy = validate_policy(policy_body)
    admission_body = bounded_file(args.admission)
    admission = validate_admission(admission_body, policy_body, source, output)
    # Fail before any HTTP on non-Linux, existing destination or missing limits.
    fd = reserve_output(output)
    try:
        budget = Budget()
        result = collect(policy["requests"], HTTPTransport(), budget)
        result["operation_id"] = admission["operation_id"]
        result["admission_sha256"] = sha(admission_body)
        result["operator_sha256"] = sha(source)
        result["policy_sha256"] = sha(policy_body)
        write_result(fd, result)
        return 0 if result["metadata_complete"] else 2
    finally:
        os.close(fd)
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Refusal, OSError, MemoryError) as exc:
        print("stage_a refused: " + (str(exc) if isinstance(exc, Refusal) else type(exc).__name__), file=sys.stderr)
        raise SystemExit(2)
