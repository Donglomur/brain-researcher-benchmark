"""Current-case protocol for AASD's existing two numerical observation modes.

This is trusted operator-side construction software, not an OS sandbox, model
runner, fresh-context guarantee, typed viewer, or direct-neural-understanding test.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re

_BASE = Path(__file__).resolve().parents[1]
_PINS = {
    "observation-delivery-v1/aasd_delivery.py": "ce91a9d48ecec64980158145e8f593c50b6b387593bdc560dd7ef7bf85bdc795",
    "initial-evaluator-v1/aasd_evaluator.py": "ff323a38b5070e8c891f6f13355ab5e404c968aaacab6740971941ca47ffa45a",
}
for _relative, _sha in _PINS.items():
    if hashlib.sha256((_BASE / _relative).read_bytes()).hexdigest() != _sha:
        raise RuntimeError("AASD dependency changed; review and rebind before use")
_spec = importlib.util.spec_from_file_location("aasd_broker_delivery", _BASE / "observation-delivery-v1/aasd_delivery.py")
d = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(d)
ContractError = d.ContractError
ZERO = "0" * 64
OBSERVATION_FIELDS = (
    "schema", "channels", "eeg_unit", "eeg_sample_period_ns",
    "eeg_start_relative_to_target_ns", "target_duration_ns", "eeg_samples",
    "valid_samples", "audio_origin_relative_to_target_ns", "audio_sha256",
)


def _frozen(value):
    """Break caller aliases and reject unsupported/nonfinite JSON values."""
    return json.loads(d.canonical(value))


def _parse(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            d.a.require(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise ContractError("nonfinite JSON constant")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)


class FileStore:
    """Trusted file adapter; the participant never receives this object or root.

    max_artifact_bytes is explicit because the authentic full-audio size has not
    been qualified. Paths and final symlinks are rejected; filesystem isolation
    and concurrent malicious replacement remain the execution service's job.
    """
    def __init__(self, public_root, mode, *, max_artifact_bytes):
        d.a.require(mode in d.MODES, "unsupported numerical mode")
        d.a.integer(max_artifact_bytes, "max_artifact_bytes", 1)
        self.root = Path(public_root).resolve(strict=True)
        self.mode = mode
        self.maximum = max_artifact_bytes

    def __call__(self, kind, identity=None):
        d.a.require(kind in ("index", "packet", "audio"), "unknown resource kind")
        if kind == "index":
            d.a.require(identity is None, "index accepts no identity")
            path = self.root / self.mode / "index.json"
        else:
            d.token(identity)
            path = self.root / self.mode / ("packets" if kind == "packet" else "audio") / (identity + ".json")
        d.a.require(not path.is_symlink(), "symlink artifact refused")
        resolved = path.resolve(strict=True)
        d.a.require(self.root in resolved.parents and resolved == path, "artifact path escaped or changed")
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as stream:
            raw = stream.read(self.maximum + 1)
        d.a.require(len(raw) <= self.maximum, "artifact exceeds admitted bound")
        return _parse(raw)


class Bundle:
    """Frozen evaluator binding plus an operator-owned public-artifact reader."""
    def __init__(self, inventory, binding, mode, read_json):
        d.a.require(mode in d.MODES, "only existing numerical modes are supported")
        self.inventory, self.binding = _frozen(inventory), _frozen(binding)
        self.mode, self.read_json = mode, read_json
        # Reuse the authoritative complete-coverage binding validation. These
        # constants are validation placeholders, never predictions or scores.
        rows = self.binding.get("rows")
        d.a.require(isinstance(rows, list) and rows, "nonempty binding required")
        placeholders = []
        for row in rows:
            d.a.require(isinstance(row, dict) and isinstance(row.get("request_ids"), dict), "invalid binding row")
            placeholders.append({"request_id": row["request_ids"].get(mode), "p_right": 0.5})
        d.join_responses(self.inventory, self.binding, mode, placeholders)
        self.rows = {r["request_ids"][mode]: r for r in rows}
        self.order = sorted(self.rows)
        index = _frozen(read_json("index"))
        d.fields(index, ("schema", "mode", "requests", "response_fields"), "index")
        d.a.require(index["schema"] == "aasd-participant-index-v1" and index["mode"] == mode, "index identity changed")
        d.a.require(index["response_fields"] == ["request_id", "p_right"], "index response contract changed")
        d.a.require(index["requests"] == [{"request_id": rid} for rid in self.order], "index must cover the exact sorted arm")

    def load(self, request_id):
        d.a.require(request_id in self.rows, "unknown current request")
        packet = _frozen(self.read_json("packet", request_id))
        d.fields(packet, ("schema", "request_id", "observation", "audio_resource"), "packet")
        d.a.require(packet["schema"] == "aasd-participant-packet-v1" and packet["request_id"] == request_id, "packet identity changed")
        d.token(packet["audio_resource"])
        observation = packet["observation"]
        d.fields(observation, OBSERVATION_FIELDS, "observation")
        d.a.require(d.digest(observation) == self.rows[request_id]["observation_sha256"], "observation differs from frozen private binding")
        d.a.require(observation["schema"] == "aasd-common-observation-v1", "observation schema changed")
        d.a.require(type(observation["eeg_sample_period_ns"]) is int and observation["eeg_sample_period_ns"] == d.a.SAMPLE_NS, "EEG grid changed")
        d.a.require(type(observation["eeg_start_relative_to_target_ns"]) is int and observation["eeg_start_relative_to_target_ns"] == -d.a.NS // 2, "EEG context origin changed")
        d.a.require(type(observation["target_duration_ns"]) is int and observation["target_duration_ns"] == d.a.NS, "target interval changed")
        d.a.require(observation["valid_samples"] == [True] * 256 and all(type(v) is bool for v in observation["valid_samples"]), "common validity mask changed")
        channels, eeg = observation["channels"], observation["eeg_samples"]
        d.a.require(isinstance(channels, list) and channels and all(isinstance(c, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,15}", c) for c in channels) and len(set(channels)) == len(channels), "invalid electrode identities")
        d.a.require(observation["eeg_unit"] in ("V", "uV"), "unknown EEG units")
        d.a.require(isinstance(eeg, list) and len(eeg) == len(channels) and all(isinstance(row, list) and len(row) == 256 and all(d.finite(v) for v in row) for row in eeg), "common EEG payload changed")
        d.a.integer(observation["audio_origin_relative_to_target_ns"], "audio origin")
        audio = _frozen(self.read_json("audio", packet["audio_resource"]))
        d.fields(audio, ("schema", "sample_rate_hz", "samples"), "audio")
        d.a.require(audio["schema"] == "aasd-stereo-pcm-v1", "audio schema changed")
        d.a.integer(audio["sample_rate_hz"], "audio sample rate", 1)
        samples = audio["samples"]
        d.a.require(isinstance(samples, list) and len(samples) == 2 and all(isinstance(row, list) and row for row in samples) and len(samples[0]) == len(samples[1]) and all(d.finite(v) and -1 <= v <= 1 for row in samples for v in row), "invalid stereo waveform")
        d.a.require(d.digest(audio) == observation["audio_sha256"], "audio differs from frozen observation")
        return packet, audio


class Journal:
    """Append-only-by-protocol answer journal; fail closed after any write error."""
    def __init__(self, path):
        self.path = Path(path)
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        self.previous = ZERO
        self.written_bytes = 0
        try:
            directory = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except BaseException:
            self.close()
            raise

    def commit(self, record):
        d.a.require(self.fd is not None, "journal is closed")
        row = dict(record, previous=self.previous)
        row["record_sha256"] = d.digest(row)
        raw = d.canonical(row) + b"\n"
        try:
            offset = 0
            while offset < len(raw):
                count = os.write(self.fd, raw[offset:])
                d.a.require(count > 0, "journal short write")
                offset += count
                self.written_bytes += count
            os.fsync(self.fd)
        except BaseException:
            self.close()
            raise
        self.previous = row["record_sha256"]
        return row

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class Broker:
    """Allowlisted current-case API; do not expose this Python object to a model."""
    def __init__(self, inventory, binding, mode, read_json, journal_path, *, max_actions_per_case):
        # A valid budget must permit observation, complete audio, and answer.
        d.a.integer(max_actions_per_case, "max_actions_per_case", 3)
        self.bundle = Bundle(inventory, binding, mode, read_json)
        if isinstance(read_json, FileStore):
            path = Path(journal_path).resolve()
            d.a.require(path != read_json.root and read_json.root not in path.parents, "journal must remain outside participant artifacts")
        self.journal = Journal(journal_path)
        self.limit = max_actions_per_case
        self.position, self.actions = 0, 0
        self.current = None
        self.records = []
        self.failed = False
        self.finished = False

    def handle(self, request):
        d.a.require(not self.failed and not self.finished, "session unavailable")
        d.a.require(self.position < len(self.bundle.order), "all answers committed; operator must finish")
        d.a.require(isinstance(request, dict), "request must be an object")
        operation = request.get("operation")
        d.a.require(operation in ("observe", "audio", "answer"), "operation not allowed")
        self.actions += 1
        if self.actions > self.limit:
            self.failed = True
            self.journal.close()
            raise ContractError("current-case action budget exhausted")
        rid = self.bundle.order[self.position]
        if operation == "observe":
            d.fields(request, ("operation",), "observe request")
            if self.current is None:
                self.current = self.bundle.load(rid)
            return copy.deepcopy(self.current[0])
        d.a.require(self.current is not None, "observe the current case first")
        packet, audio = self.current
        if operation == "audio":
            d.fields(request, ("operation", "resource_id"), "audio request")
            d.a.require(request["resource_id"] == packet["audio_resource"], "only current-case audio is available")
            return copy.deepcopy(audio)
        d.fields(request, ("operation", "request_id", "p_right"), "answer request")
        d.a.require(request["request_id"] == rid, "only current-case answer is accepted")
        p = request["p_right"]
        d.a.require(d.finite(p) and 0 <= p <= 1, "probability must be finite and in [0,1]")
        record = {"schema": "aasd-current-case-answer-v1", "sequence": self.position,
                  "request_id": rid, "p_right": float(p),
                  "observation_sha256": self.bundle.rows[rid]["observation_sha256"],
                  "audio_sha256": packet["observation"]["audio_sha256"]}
        try:
            committed = self.journal.commit(record)
        except BaseException:
            self.failed = True
            raise
        self.records.append(committed)
        self.position += 1
        self.current, self.actions = None, 0
        return {"accepted": True}

    def operator_route(self):
        """Evaluator-only routing; never part of handle's participant API."""
        d.a.require(self.position < len(self.bundle.order), "no current route")
        row = self.bundle.rows[self.bundle.order[self.position]]
        return {"participant": row["participant"], "held_mixture_fold": row["held_mixture_fold"]}

    def finish(self):
        d.a.require(not self.failed and not self.finished and self.position == len(self.bundle.order), "complete immutable answers required")
        self.journal.close()
        # Close the journal before exposing predictions to evaluator code. The
        # external runner must separately prove participant-process termination.
        try:
            saved = _read_journal(self.journal.path, len(self.bundle.order))
            d.a.require(saved == self.records, "durable answers differ from committed responses")
            predictions = replay_records(self.bundle, saved)
        except BaseException:
            self.failed = True
            raise
        self.finished = True
        return predictions

    def close(self):
        """Abort without scoring; retain the incomplete journal as evidence."""
        self.journal.close()
        if not self.finished:
            self.failed = True


def replay_records(bundle, records):
    """Verify a complete saved chain against current pinned observations."""
    d.a.require(isinstance(records, list) and len(records) == len(bundle.order), "journal does not cover complete arm")
    previous, responses = ZERO, []
    for sequence, row in enumerate(records):
        d.fields(row, ("schema", "sequence", "request_id", "p_right", "observation_sha256", "audio_sha256", "previous", "record_sha256"), "answer record")
        d.a.require(row["schema"] == "aasd-current-case-answer-v1" and type(row["sequence"]) is int and row["sequence"] == sequence, "journal ordering changed")
        d.a.require(row["request_id"] == bundle.order[sequence] and row["previous"] == previous, "journal coverage or chain changed")
        body = {k: v for k, v in row.items() if k != "record_sha256"}
        d.a.require(d.digest(body) == row["record_sha256"], "journal record changed")
        packet, _ = bundle.load(row["request_id"])
        d.a.require(row["observation_sha256"] == bundle.rows[row["request_id"]]["observation_sha256"] and row["audio_sha256"] == packet["observation"]["audio_sha256"], "journal input binding changed")
        responses.append({"request_id": row["request_id"], "p_right": row["p_right"]})
        previous = row["record_sha256"]
    return d.join_responses(bundle.inventory, bundle.binding, bundle.mode, responses)


def _read_journal(journal_path, expected_count):
    records = []
    with Path(journal_path).open("rb") as stream:
        while True:
            line = stream.readline(4097)
            if not line:
                break
            d.a.require(len(line) <= 4096 and line.endswith(b"\n"), "oversized or partial journal record")
            d.a.require(len(records) < expected_count, "extra journal records")
            records.append(_parse(line))
    d.a.require(len(records) == expected_count, "incomplete journal")
    return records


def replay_file(inventory, binding, mode, read_json, journal_path):
    bundle = Bundle(inventory, binding, mode, read_json)
    return replay_records(bundle, _read_journal(journal_path, len(bundle.order)))
