"""Complete media/provenance/presentation identity joins; descriptors are not authority.

This validates actual supplied ordinary mapping bodies. The historical public
1102-video collection remains development data. No path, receipt or boolean
creates rights, physical synchronization, checkpoint exposure or fresh subjects.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
from pathlib import PurePosixPath
import hashlib
import json

VIDEO_IDS = tuple(range(1, 1103))
SUBJECTS = tuple(f"sub-{i:02d}" for i in range(1, 7))


def need(condition, message):
    if not condition:
        raise ValueError(message)


def descriptor(row, *, cap=100_000_000):
    need(type(row) is dict and set(row) == {"path", "bytes", "sha256"}, "exact ordinary descriptor")
    path = row["path"]
    need(type(path) is str and path and "\\" not in path and not any(ord(c) < 32 for c in path), "plain relative source path")
    p = PurePosixPath(path)
    need(not p.is_absolute() and p.as_posix() == path and all(x not in ("", ".", "..") for x in path.split("/")), "canonical local source path")
    need(type(row["bytes"]) is int and 0 < row["bytes"] <= cap, "bounded nonempty source member")
    digest = row["sha256"]
    need(type(digest) is str and len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), "exact source SHA256")
    return row


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


@dataclass(frozen=True)
class MediaRole:
    video_id: int
    experimental_name: str
    source_path: str
    source_bytes: int
    source_sha256: str
    container: str
    video_stream: int
    audio_stream: int | None
    audio_status: str
    timeline_origin: tuple[int, int]
    max_frames: int
    max_audio_samples: int
    max_width: int
    max_height: int
    provenance_identity: str
    provenance_namespace: str

    @property
    def source_media(self):
        return {"path": self.source_path, "bytes": self.source_bytes, "sha256": self.source_sha256}


@dataclass(frozen=True)
class SourceMap:
    roles: tuple[MediaRole, ...]
    canonical_source_map_sha256: str
    identity_evidence: tuple[tuple[str, str], ...]
    library_versions: tuple[tuple[str, tuple[int, int, int]], ...]
    development_collection: str = "public EEG Moments 1102 videos; not fresh evaluation"

    def by_id(self):
        return {row.video_id: row for row in self.roles}


def validate_source_map(document, observed_identity, observed_audio, family_video_ids=VIDEO_IDS):
    """Join complete mapping and independent identity/audio evidence bodies.

    The caller captures all three bodies through the accepted Owner before this
    call. Evidence means observed records supplied by the data provider; this
    routine checks their internal joins and never labels them a rights grant.
    """
    need(type(document) is dict and set(document) == {"schema", "profile", "evidence", "library_versions", "videos"}, "closed complete media map")
    need(document["schema"] == "neural080_generalization_media_v1", "media map schema")
    need(document["profile"] == "full_source_pts_and_declared_silence_v1", "explicit prospective media profile")
    evidence = document["evidence"]
    need(type(evidence) is dict and set(evidence) == {"experimental_identity", "audio_presence", "provenance_graph"}, "three exact mapping evidence roles")
    for row in evidence.values():
        descriptor(row, cap=16_777_216)
    versions = document["library_versions"]
    need(type(versions) is dict and versions and all(type(k) is str and type(v) is list and len(v) == 3 and all(type(n) is int and n >= 0 for n in v) for k, v in versions.items()), "complete explicit observed FFmpeg versions")
    need(type(observed_identity) is dict and set(observed_identity) == {"schema", "origin", "rows"}, "observed identity schema")
    need(observed_identity["schema"] == "neural080_observed_stimulus_identity_v1" and type(observed_identity["origin"]) is str and observed_identity["origin"], "actual experiment/map origin required")
    need(type(observed_audio) is dict and set(observed_audio) == {"schema", "origin", "rows"}, "observed audio schema")
    need(observed_audio["schema"] == "neural080_observed_audio_presence_v1" and type(observed_audio["origin"]) is str and observed_audio["origin"], "actual original silence-list/presentation origin required")
    identities = observed_identity["rows"]
    audio = observed_audio["rows"]
    rows = document["videos"]
    need(type(rows) is list and type(identities) is list and type(audio) is list, "complete ordered media/evidence rows")
    need(all(type(r) is dict and type(r.get("video_id")) is int for group in (rows, identities, audio) for r in group) and tuple(r.get("video_id") for r in rows) == VIDEO_IDS == tuple(r.get("video_id") for r in identities) == tuple(r.get("video_id") for r in audio), "all1102 actual identities exactly once and in source order")
    need(tuple(sorted(family_video_ids)) == VIDEO_IDS, "family graph and media roster differ")
    roles = []
    source_paths, names = set(), set()
    silent = []
    expected = {"video_id", "experimental_name", "source_media", "format", "video_stream", "audio_stream", "audio_status", "timeline_origin", "max_frames", "max_audio_samples", "max_width", "max_height", "provenance_identity", "provenance_namespace"}
    for row, ident, sound in zip(rows, identities, audio, strict=True):
        need(type(row) is dict and set(row) == expected, "closed media role")
        need(set(ident) == {"video_id", "experimental_name", "source_sha256", "provenance_identity", "provenance_namespace", "original_record_identity"}, "closed actual stimulus identity row")
        need(set(sound) == {"video_id", "experimental_name", "audio_status", "original_silence_list_member", "presentation_audio_status", "original_record_identity"}, "closed actual audio row")
        media = descriptor(row["source_media"])
        name = row["experimental_name"]
        need(type(name) is str and PurePosixPath(name).name == name and PurePosixPath(media["path"]).name == name and name not in names and media["path"] not in source_paths, "unique original filename and source path per video")
        need(ident["experimental_name"] == sound["experimental_name"] == name and ident["source_sha256"] == media["sha256"], "experiment/media/audio identity join")
        provenance = row["provenance_identity"]
        namespace = row["provenance_namespace"]
        need(type(namespace) is str and namespace and ident["provenance_namespace"] == namespace, "actual complete donor namespace join")
        need(type(provenance) is str and provenance and ident["provenance_identity"] == provenance, "actual common provenance identity")
        need(all(type(r["original_record_identity"]) is str and r["original_record_identity"] for r in (ident, sound)), "original source evidence identity required")
        need(row["format"] in ("mov", "matroska"), "selected actual container format")
        need(type(row["video_stream"]) is int and 0 <= row["video_stream"] <= 255, "explicit video stream")
        state = row["audio_status"]
        need(state in ("presented_audio", "presented_silent_no_track") and sound["audio_status"] == state, "observed audio status; unknown is not silence")
        if state == "presented_silent_no_track":
            need(row["audio_stream"] is None and sound["original_silence_list_member"] is True and sound["presentation_audio_status"] == "confirmed_no_playback", "silence needs original list and actual no-playback join")
            silent.append(row["video_id"])
        else:
            need(type(row["audio_stream"]) is int and 0 <= row["audio_stream"] <= 255 and row["audio_stream"] != row["video_stream"], "explicit separate heard-audio stream")
            need(sound["original_silence_list_member"] is False and sound["presentation_audio_status"] == "confirmed_playback", "heard-audio evidence cannot be missing")
        origin = row["timeline_origin"]
        need(type(origin) is list and len(origin) == 2 and all(type(n) is int for n in origin) and origin[1] > 0, "exact rational clip origin")
        Fraction(*origin)
        for field, maximum in (("max_frames", 1000), ("max_audio_samples", 1_000_000), ("max_width", 8192), ("max_height", 8192)):
            need(type(row[field]) is int and 1 <= row[field] <= maximum, "explicit finite native expansion cap: " + field)
        names.add(name);source_paths.add(media["path"])
        roles.append(MediaRole(row["video_id"], name, media["path"], media["bytes"], media["sha256"], row["format"], row["video_stream"], row["audio_stream"], state, tuple(origin), row["max_frames"], row["max_audio_samples"], row["max_width"], row["max_height"], provenance, namespace))
    need(len(silent) == 34, "complete original34 confirmed silent roles required; no inferred silence")
    return SourceMap(tuple(roles), hashlib.sha256(canonical(document)).hexdigest(), tuple((k, v["sha256"]) for k, v in sorted(evidence.items())), tuple((k, tuple(v)) for k, v in sorted(versions.items())))


def load_source_map(root, selection_descriptor, family_video_ids, owner):
    """Capture actual supplied map and evidence; never fetch study assets."""
    from input_owner import capture
    from io_contract import decode
    rec = owner.begin("complete_source_map")
    result = None
    try:
        body = capture(root, descriptor(selection_descriptor, cap=16_777_216), owner, max_bytes=16_777_216)
        selected = decode(body)
        evidence = selected.get("evidence")
        need(type(evidence) is dict and set(evidence) == {"experimental_identity", "audio_presence", "provenance_graph"}, "complete source-map evidence before use")
        identity = decode(capture(root, descriptor(evidence["experimental_identity"], cap=16_777_216), owner, max_bytes=16_777_216))
        audio = decode(capture(root, descriptor(evidence["audio_presence"], cap=16_777_216), owner, max_bytes=16_777_216))
        # The actual full provenance graph is captured by the split compiler;
        # its exact descriptor remains bound here and must match its selection.
        result = validate_source_map(selected, identity, audio, family_video_ids)
    except BaseException as exc:
        owner.failure(rec, exc)
    owner.complete(rec)
    return result
