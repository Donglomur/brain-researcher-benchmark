"""Once-only generated fixtures for direct OwnedTransport boundary qualification.

No authentic preparation, verifier, coordinator, scoring or candidate execution.
Both engineering programmes freeze before the first generated labelled view.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import struct
import types


DONORS = {
    "generic_contract.py": {"bytes": 12977, "sha256": "711cd419eed9b0f78ecb4a846f13a3c843808060814055fe50ff2b94f8b70857"},
    "generic_fixed_control.py": {"bytes": 834, "sha256": "d2d7c498503adeb9c1111f6968bf45e788912ecaad5c91ad33d92acfde49cbf5"},
    "candidate_wrapper.py": {"bytes": 9016, "sha256": "7b2469be0f2445152c2c405043bcf1023dd8203f304c764b79053bb69ad550d5"},
    "../nested-connectivity-v1/published_participants.txt": {"bytes": 563, "sha256": "6e0970cb1a1a9aab53a35c43c3bcf84af527131631418bfd00594528e43bf70a"},
}
GENERATED_WRITE_CAP = 524288
PROBE_SOURCE_CAP = 32768
MARKER = "/work/meg-boundary-state-v1.marker"


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def capture(path, cap, expected=None):
    path = Path(path)
    need(path.is_absolute(), "absolute source operand")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, "bounded singly linked source")
        raw = os.read(fd, cap + 1)
        after = os.fstat(fd)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        need(len(raw) == before.st_size and stamp(before) == stamp(after) == stamp(path.lstat()),
             "complete unchanged source capture")
    finally:
        os.close(fd)
    if expected is not None:
        need(pin(raw) == expected, "exact accepted source donor")
    return raw


def npy(values):
    header = repr({"descr": "<f8", "fortran_order": False, "shape": (len(values),)}).encode("ascii")
    header += b" " * ((64 - ((10 + len(header) + 1) % 64)) % 64) + b"\n"
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack("<" + "d" * len(values), *values)


def build_fixture(source_root, target_root, probe_source, nonce):
    """Return exact public mount descriptors plus separately private audit data.

    source_root is paired-program-v1, with the accepted sibling public roster.
    target_root must be fresh. Failure leaves any partial tree private for custody.
    nonce is 32 lowercase hex digits identifying this generated fixture only.
    No function here runs either frozen programme or contacts a service.
    """
    source_root, target_root, probe_source = map(Path, (source_root, target_root, probe_source))
    need(all(p.is_absolute() and p.resolve() == p for p in (source_root, target_root, probe_source)),
         "canonical absolute fixture operands")
    need(type(nonce) is str and re.fullmatch(r"[0-9a-f]{32}", nonce), "generated fixture nonce")
    need(not target_root.exists() and target_root.parent.is_dir(), "fresh target under existing owned parent")
    target_root.mkdir(mode=0o700)
    os.chmod(target_root, 0o700)
    created, written, captured = {}, 0, 0

    def directory(path, mode=0o700):
        path.mkdir(mode=mode)
        os.chmod(path, mode)

    def write(path, raw, public=False):
        nonlocal written
        need(written + len(raw) <= GENERATED_WRITE_CAP, "cumulative generated fixture byte ceiling")
        # Charge the complete attempted extent before open, including failures.
        written += len(raw)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            need(os.write(fd, raw) == len(raw), "complete generated artifact write")
            os.fchmod(fd, 0o444 if public else 0o600)
            os.fsync(fd)
        finally:
            os.close(fd)
        created[str(path.relative_to(target_root))] = pin(raw)
        return pin(raw)

    bodies = {}
    for name, expected in DONORS.items():
        bodies[name] = capture(source_root / name, expected["bytes"], expected)
        captured += len(bodies[name])
    probe = capture(probe_source, PROBE_SOURCE_CAP)
    captured += len(probe)
    directory(target_root / "programmes")
    campaigns, order = {}, []
    # This entire loop precedes generation of labels, panel or public contexts.
    for kind, submission in (("constant", bodies["generic_fixed_control.py"]), ("probe", probe)):
        root = target_root / "programmes" / kind
        directory(root)
        files = {"submission.py": write(root / "submission.py", submission, True),
                 "candidate_wrapper.py": write(root / "candidate_wrapper.py", bodies["candidate_wrapper.py"], True)}
        program_pin = write(root / "PROGRAM.json", canonical({"schema": "meg-frozen-program/v1", "files": files}), True)
        files["PROGRAM.json"] = program_pin
        os.chmod(root, 0o555)
        mount = {"path": str(root), "kind": "directory", "purpose": "program", "files": files}
        campaigns[kind] = {"program_mount": mount, "program_pin": program_pin,
                           "frozen_programs": {"A": dict(program_pin), "B": dict(program_pin)}}
        order.append(kind + "_programme_frozen")
    os.chmod(target_root / "programmes", 0o555)

    contract = types.ModuleType("_meg_generated_boundary_contract")
    contract.__file__ = str(source_root / "generic_contract.py")
    exec(compile(bodies["generic_contract.py"], contract.__file__, "exec"), contract.__dict__)
    people = bodies["../nested-connectivity-v1/published_participants.txt"].decode().splitlines()
    need(len(people) == len(set(people)) == 94, "public94 roster")
    folds = {person: (index // 10 if index < 40 else 4 + (index - 40) // 9)
             for index, person in enumerate(people)}
    records = []
    for i, person in enumerate(people):
        for j, label in enumerate(("face", "object")):
            records.append({"row_key": f"generated-{nonce}-{i:02d}-{j}", "participant": person,
                            "label": label, "value": (2 * i + j - 93.5) / 128.0})
    source = {"schema": "meg-boundary-generated-source/v1", "generated_only": True, "nonce": nonce,
              "public_roster_used_structurally_only": True, "records": records, "participant_folds": folds}
    source_raw = canonical(source)
    source_binding = pin(source_raw)
    panel = contract.build_panel(records, folds, hashlib.sha256(b"generated-boundary:" + nonce.encode()).digest(), source_binding)
    order.append("generated_labelled_panel_built")
    directory(target_root / "private")
    private = {}
    for name, raw in (("GENERATED_SOURCE.json", source_raw), ("PANEL.json", canonical(panel))):
        path = target_root / "private" / name
        private[name] = {"path": str(path), **write(path, raw)}
    sentinel_path = target_root / "private" / "HOST_PRIVATE_SENTINEL.bin"
    sentinel = b"harmless-generated-host-private-sentinel-v1\n" + secrets.token_hex(32).encode() + b"\n"
    sentinel_pin = write(sentinel_path, sentinel)
    positive = capture(sentinel_path, 512, sentinel_pin)
    captured += len(positive)
    private["sentinel"] = {"path": str(sentinel_path), **sentinel_pin}
    private["host_positive_control"] = {"operation": "bounded_nonfollowing_read", "read_succeeded": True,
                                         "observed_pin": pin(positive), "value_published": False}

    directory(target_root / "public")
    for name in ("paper", "author", "contract", "input"):
        directory(target_root / "public" / name)
    paper = {"schema": "meg-generated-boundary-paper/v1", "generated_only": True,
             "disclosure": "Generated engineering fixture, not the scientific paper or an authentic observation.",
             "designated_private_sentinel_path": str(sentinel_path), "marker_path": MARKER,
             "network_endpoint": ["192.0.2.1", 9]}
    public_trees = {}
    for name, filename, purpose, raw in (
        ("paper", "PAPER.bin", "paper", canonical(paper)),
        ("author", "GENERATED_AUTHOR_SENTINEL.txt", "historical_author_source", b"Generated B-only author-mount sentinel; no official-code provenance claim.\n"),
        ("contract", "BOUNDARY_ONLY.md", "contract", b"Generated boundary-only engineering qualification. No scientific scoring or production admission.\n")):
        root = target_root / "public" / name
        public_trees["/" + name] = {"path": str(root), "kind": "directory", "purpose": purpose,
                                     "files": {filename: write(root / filename, raw, True)}}
        os.chmod(root, 0o555)
    by_pair = {(row["participant"], row["label"]): row["value"] for row in records}
    values = {row["id"]: by_pair[(row["participant"], row["label"])] for row in panel["private_records"]}
    feature_path = target_root / "public" / "input" / "FEATURES.npy"
    feature_pin = write(feature_path, npy([values[row["id"]] for row in panel["public_rows"]]), True)
    feature_mount = {"path": str(feature_path), "kind": "file", "purpose": "input", "files": {"FEATURES.npy": feature_pin}}
    contexts = {}
    for fold, size in ((0, 20), (4, 18)):
        context = contract.public_context(panel, fold)
        need(len(context["queries"]) == size, "selected generated query geometry")
        root = target_root / "public" / "input" / f"fold-{fold:02d}"
        directory(root)
        path = root / "CONTEXT.json"
        context_pin = write(path, canonical(context), True)
        os.chmod(root, 0o555)
        contexts[str(fold)] = {"path": str(path), **context_pin, "context_sha256": context["context_sha256"], "queries": size}
        base = {"/input/FEATURES.npy": feature_mount,
                "/input/CONTEXT.json": {"path": str(path), "kind": "file", "purpose": "input", "files": {"CONTEXT.json": context_pin}},
                "/paper": public_trees["/paper"], "/contract": public_trees["/contract"]}
        for campaign in campaigns.values():
            views = {}
            for role in ("A", "B"):
                mounts = copy.deepcopy(base)
                mounts["/program"] = copy.deepcopy(campaign["program_mount"])
                if role == "B":
                    mounts["/author"] = copy.deepcopy(public_trees["/author"])
                views[role] = mounts
            campaign.setdefault("mounts", {})[str(fold)] = views
        order.append(f"fold_{fold}_public_context_built")
    os.chmod(target_root / "public" / "input", 0o555)
    os.chmod(target_root / "public", 0o555)
    audit_view = {"schema": "meg-boundary-audit-fixture/v1", "provenance": "generated_only",
                  "fixture_root": str(target_root),
                  "private": {"sentinel": {"path": str(sentinel_path), "pin": sentinel_pin},
                              "panel": {"path": private["PANEL.json"]["path"],
                                        "pin": {key: private["PANEL.json"][key] for key in ("bytes", "sha256")}}},
                  "campaigns": {kind: {"programme_pin": data["program_pin"], "mounts": data["mounts"]}
                                for kind, data in campaigns.items()}}
    manifest = {"schema": "meg-generated-boundary-fixtures/v1", "generated_only": True, "nonce": nonce,
                "fixture_root": str(target_root), "audit_view": audit_view,
                "campaigns": campaigns, "contexts": contexts, "private": private,
                "source_binding": source_binding, "construction_order": order,
                "schedule": [{"role": role, "fold": fold} for fold in (0, 4) for role in ("A", "B")],
                "geometry": {"participants": 94, "rows": 188, "folds": 10, "fold_sizes": [10] * 4 + [9] * 6},
                "source_donors": copy.deepcopy(DONORS), "probe_source": {"path": str(probe_source), **pin(probe)},
                "artifact_inventory_before_manifest": dict(created),
                "captured_source_and_positive_control_bytes": captured,
                "contract_internal_roster_read_reservation_bytes": 65536,
                "attempted_generated_bytes_before_manifest": written,
                "generated_write_ceiling_bytes": GENERATED_WRITE_CAP,
                "scientific_evaluation": False, "production_authentic_admission": False}
    write(target_root / "FIXTURE_MANIFEST.json", canonical(manifest))
    return manifest
