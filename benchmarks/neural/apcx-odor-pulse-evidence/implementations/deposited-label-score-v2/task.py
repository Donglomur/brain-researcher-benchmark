"""Successor owner CLI with public prediction admission before target reads.

No candidate process, network request, or Docker operation is launched. Candidate
execution must receive one episode in a separately isolated environment. These
commands reuse unchanged sibling deposited-label kernels, not a new benchmark.
"""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import resource
import sys
import time

# Keep the pinned predecessor source unchanged. Only this successor's score
# entrypoint adds public prediction admission; mathematical kernels stay there.
SOURCE = Path(__file__).absolute().parent
PREDECESSOR = SOURCE.parent / "deposited-label"
sys.path.insert(0, str(SOURCE))
sys.path.insert(1, str(PREDECESSOR))

import participant_core as core
import released_profile as profile
import grader
import json_interface
import native_io
import profile_prepare
import episode_boundary as boundary
import reference_protocol
import score_admission

MIB = 1024**2
MAX_DOCUMENT = 128 * MIB
CONDITIONS = core.CONDITIONS
METHODS = ("candidate", "calibration_mean", "count_ridge", "temporal_ridge")
PROFILE_FILES = tuple(f"{kind}_{condition.upper()}.json"
                      for condition in CONDITIONS for kind in ("PARTICIPANT", "OWNER"))


def absolute(path):
    # Do not resolve away a symlink before the ordinary-file checks see it.
    return Path(path).expanduser().absolute()


def need(value, message):
    if not value:
        raise ValueError(message)


def config():
    path = PREDECESSOR / "config.json"
    value = json_interface.decode(path.read_bytes(), 32768)
    need(value["schema"] == "apcx-portable-config-v1" and value["profile"] == profile.PROFILE,
         "fixed portable configuration")
    need(value["conditions"] == list(CONDITIONS) and value["full_scope"] == {
        "rows": 95072, "trials": 10831, "sessions": 43, "animals": 3,
        "session_unit_pairs": 383, "queries_per_condition": 2199,
        "unresolved_trials": 900, "unresolved_queries_per_condition": 165}, "complete frozen cohort")
    return value


def budget():
    return native_io.Budget({"input_bytes": 1024*MIB, "json_record_bytes": 512*MIB,
                            "output_read_bytes": 1024*MIB, "retained_bytes": 1024*MIB},
                           time.monotonic()+600)


def check(b):
    b.check()
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if sys.platform != "darwin":
        rss *= 1024
    need(rss <= 4*1024*MIB, "observed 4-GiB RSS limit; no successful subset")


def read_bytes(path, b, maximum, expected=None):
    path = absolute(path)
    stat = native_io.ordinary(path)
    need(stat.st_size <= maximum, "whole input-file bound")
    if expected is not None:
        need(stat.st_size == expected["bytes"], "exact input length")
    with native_io.MeteredReader(path, stat.st_size, b) as reader:
        parts = []
        while reader.tell() < reader.size:
            check(b)
            chunk = reader.read(min(65536, reader.size-reader.tell()))
            need(bool(chunk), "complete input EOF")
            parts.append(chunk)
        reader.identity()
    body = b"".join(parts)
    if expected is not None:
        need(hashlib.sha256(body).hexdigest() == expected["sha256"], "exact input SHA-256")
    return body


def read_json(path, b, maximum=MAX_DOCUMENT, expected=None):
    return json_interface.decode(read_bytes(path, b, maximum, expected), maximum)


def fresh_directory(path):
    path = absolute(path)
    need(".." not in path.parts and not any(p.is_symlink() for p in (path, *path.parents)),
         "ordinary fresh output directory")
    path.mkdir(mode=0o700, parents=False, exist_ok=False)
    return path


def write_bytes(path, body, b, maximum=MAX_DOCUMENT):
    need(type(body) is bytes, "exact output bytes")
    check(b)  # Check allocations before opening the exclusive output.
    need(len(body) <= maximum, "whole output-file bound")
    b.charge("retained_bytes", len(body))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        need(stream.write(body) == len(body), "short output write")
        stream.flush()
        os.fsync(stream.fileno())
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def write_json(path, value, b, maximum=MAX_DOCUMENT):
    return write_bytes(path, core.canonical(value), b, maximum)


def audit_pair(packets, owners=None):
    """Keep all43 sessions/bothconditions and the same protected observations."""
    need(set(packets) == set(CONDITIONS), "both complete support conditions")
    by_condition = {}
    for condition in CONDITIONS:
        packet = packets[condition]
        profile.audit_public(packet)
        need(packet["invented"] is False and packet["condition"] == condition,
             "authentic deposited-label condition only")
        sessions = {s["session_id"]: s for s in packet["sessions"]}
        need(len(sessions) == 43 and sum(len(s["channel_ids"]) for s in sessions.values()) == 383,
             "all43 sessions and383 session-unit pairs")
        need(sum(len(s["queries"]) for s in sessions.values()) == 2199, "all2199 queries")
        expected = (688, 344) if condition == "matched" else (6482, 2150)
        need(tuple(sum(len(s[k]) for s in sessions.values()) for k in ("calibration", "development"))
             == expected, "complete frozen support counts")
        by_condition[condition] = sessions
        if owners is not None:
            owner = owners[condition]
            grader.validate_owner(owner)
            need(owner["invented"] is False and owner["condition"] == condition
                 and owner["participant_packet_sha256"] == core.digest(packet), "owner/packet binding")
            need(owner["input_trial_count"] == 10831 and owner["required_query_count"] == 2199,
                 "complete owner trial census")
            dispositions = owner["all_trial_dispositions"]
            need(sum(len(d["old_flags_owner_only"]) for d in dispositions) == 95072,
                 "all95072 original trial-unit row dispositions")
            unresolved = [d for d in dispositions if
                          d["diagnostic_reference_owner_only"]["status_owner_only"] == "UNRESOLVED"]
            need(len(unresolved) == 900 and sum(d["required_query"] for d in unresolved) == 165,
                 "all900 unresolved trials including165 protected queries retained")
            need({c["case_id"] for c in owner["cases"]} ==
                 {r["case_id"] for s in sessions.values() for r in s["queries"]}, "owner query join")
    matched, full = (by_condition[c] for c in CONDITIONS)
    need(set(matched) == set(full), "same complete session roster")
    for sid in matched:
        a, f = matched[sid], full[sid]
        need(a["channel_ids"] == f["channel_ids"] and a["queries"] == f["queries"],
             "identical protected signals/channel basis across conditions")
        for split in ("calibration", "development"):
            lookup = {r["case_id"]: r for r in f[split]}
            need(all(lookup.get(r["case_id"]) == r for r in a[split]), "matched support is exact full support subset")
    if owners is not None:
        need(owners["matched"]["cases"] == owners["full_calibration"]["cases"],
             "identical protected targets across conditions")


def finish_bundle(root, b, origin):
    packets = {}; owners = {}; members = {}
    for condition in CONDITIONS:
        for kind, table in (("PARTICIPANT", packets), ("OWNER", owners)):
            name = f"{kind}_{condition.upper()}.json"
            body = read_bytes(root/name, b, MAX_DOCUMENT)
            table[condition] = json_interface.decode(body)
            members[name] = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    audit_pair(packets, owners)
    manifest = {"schema": "apcx-portable-private-bundle-v1", "profile": profile.PROFILE,
                "origin": origin, "members": members, "remaining_holds": list(core.HOLDS),
                "task_count": 1, "conditions": list(CONDITIONS), "public_export_approved": False,
                "candidate_isolation_established_by_this_cli": False}
    return write_json(root/"BUNDLE.json", manifest, b, MIB)


def manifest_at(root, name, sha, b, schema):
    need(type(sha) is str and boundary.HEX.fullmatch(sha), "explicit frozen manifest SHA-256")
    body = read_bytes(root/name, b, MIB)
    need(hashlib.sha256(body).hexdigest() == sha, "trusted manifest identity")
    doc = json_interface.decode(body, MIB)
    need(doc.get("schema") == schema and doc.get("profile") == profile.PROFILE, "manifest kind/profile")
    return doc


def load_bundle(args, b):
    root = absolute(args.bundle)
    manifest = manifest_at(root, "BUNDLE.json", args.bundle_sha256, b, "apcx-portable-private-bundle-v1")
    need(set(manifest["members"]) == set(PROFILE_FILES)
         and manifest["remaining_holds"] == list(core.HOLDS), "whole bundle and unchanged holds")
    return root, manifest


def load_packets(root, manifest, b):
    packets = {c: read_json(root/f"PARTICIPANT_{c.upper()}.json", b,
                           expected=manifest["members"][f"PARTICIPANT_{c.upper()}.json"])
               for c in CONDITIONS}
    audit_pair(packets)
    return packets


def convert(args, b):
    cfg = config()
    source = absolute(args.inputs)
    selected = {k: {"path": str(source/v["name"]), "bytes": v["bytes"], "sha256": v["sha256"]}
                for k, v in cfg["prepared_inputs"].items()}
    output = fresh_directory(args.output)
    store = native_io.OutputStore(output, b, MAX_DOCUMENT)
    profile_prepare.prepare({"prepared_inputs": selected, "observed_rss_soft_stop_bytes": 4*1024*MIB}, b, store)
    return finish_bundle(output, b, "complete_exact_accepted_ROWS_and_COMMAND_DIAGNOSTICS")


def provision(args, b):
    """Reuse already-accepted four packets; no split regeneration or refit."""
    cfg = config(); source = absolute(args.inputs); output = fresh_directory(args.output)
    for name in PROFILE_FILES:
        body = read_bytes(source/name, b, MAX_DOCUMENT, cfg["accepted_profile_inputs"][name])
        json_interface.decode(body)  # Keep strict JSON admission before copying.
        # Accepted hashes bind the original encoding. Integer object keys become
        # strings on decode, so reserialization can change their sorted order.
        write_bytes(output/name, body, b)
    return finish_bundle(output, b, "exact_authentic86_accepted_profile_inputs")


def episodes(args, b):
    root, manifest = load_bundle(args, b); packets = load_packets(root, manifest, b)
    output = fresh_directory(args.output); members = {}
    for condition in CONDITIONS:
        folder = output/condition; folder.mkdir(mode=0o700)
        for e in boundary.from_public_packet(packets[condition]):
            name = f"{condition}/{e['session']['session_id']}.json"
            members[name] = write_json(output/name, e, b, boundary.MAX_EPISODE_BYTES)
    need(len(members) == 86, "all86 session-condition episodes")
    return write_json(output/"EPISODES.json", {"schema": "apcx-complete-episodes-v1",
        "profile": profile.PROFILE, "members": members, "bundle_sha256": args.bundle_sha256,
        "mount_policy": "One episode only per isolated candidate process; never mount this full directory.",
        "candidate_execution_or_isolation_performed": False}, b, MIB)


def complete_responses(path, packets, b, references=False):
    root = absolute(path)
    expected = {f"{c}/{s['session_id']}.json" for c in CONDITIONS for s in packets[c]["sessions"]}
    observed = set()
    need(not root.is_symlink() and root.is_dir(), "ordinary response root")
    for entry in root.iterdir():
        need(entry.name in CONDITIONS and entry.is_dir() and not entry.is_symlink(), "exact response condition directories")
        for f in entry.iterdir():
            native_io.ordinary(f)
            observed.add(f"{entry.name}/{f.name}")
    need(observed == expected, "exact86 response set; no missing/extra episodes")
    result = {}
    for c in CONDITIONS:
        result[c] = {}
        for e in boundary.from_public_packet(packets[c]):
            sid = e["session"]["session_id"]
            response = read_json(root/c/(sid+".json"), b, boundary.MAX_RESULT_BYTES)
            if not references:
                core.exact_keys(response, ("schema", "profile", "condition", "session_id",
                    "participant_packet_sha256", "episode_sha256", "records"))
                need(response["schema"] == "apcx-candidate-session-result-v1" and response["profile"] == profile.PROFILE
                     and response["condition"] == c and response["session_id"] == sid
                     and response["participant_packet_sha256"] == e["participant_packet_sha256"]
                     and response["episode_sha256"] == boundary.digest(e), "candidate response provenance")
                boundary.validate_candidate_records(e, response["records"])
            result[c][sid] = response
    return result


def assemble(args, b, references=False):
    root, manifest = load_bundle(args, b); packets = load_packets(root, manifest, b)
    responses = complete_responses(args.responses, packets, b, references)
    # Both conditions become complete before any owner target is opened.
    selected = {}; selections = {}
    for c in CONDITIONS:
        if references:
            selections[c] = reference_protocol.select_condition(packets[c], responses[c])
            selected[c] = selections[c]["submissions"]
        else:
            records = [r for s in packets[c]["sessions"] for r in responses[c][s["session_id"]]["records"]]
            selected[c] = {"candidate": profile.submission(packets[c], sorted(records, key=lambda r: r["case_id"]))}
    output = fresh_directory(args.output); members = {}
    methods = list(reference_protocol.METHODS) if references else ["candidate"]
    selection_pins = {}
    for c in CONDITIONS:
        if references:
            selection_pins[c] = write_json(output/f"REFERENCE_SELECTION_{c}.json", selections[c], b, 4*MIB)
        for method in methods:
            name = f"{c}__{method}.json"
            members[name] = write_json(output/name, selected[c][method], b, 4*MIB)
    return write_json(output/"FROZEN.json", {"schema": "apcx-complete-frozen-submissions-v1",
        "profile": profile.PROFILE, "members": members, "methods": methods,
        "reference_selection_pins": selection_pins,
        "bundle_sha256": args.bundle_sha256, "conditions": list(CONDITIONS),
        "owner_targets_read_during_assembly": False}, b, MIB)


def score(args, b):
    root, bundle = load_bundle(args, b)
    frozen_root = absolute(args.submissions)
    frozen = manifest_at(frozen_root, "FROZEN.json", args.frozen_sha256, b,
                         "apcx-complete-frozen-submissions-v1")
    methods = frozen["methods"]
    need(methods in (["candidate"], list(reference_protocol.METHODS))
         and frozen["conditions"] == list(CONDITIONS)
         and frozen["bundle_sha256"] == args.bundle_sha256, "fixed complete method/condition binding")
    expected = {f"{c}__{m}.json" for c in CONDITIONS for m in methods}
    need(set(frozen["members"]) == expected, "both conditions and every method frozen")
    # Authenticate every frozen prediction before accessing either owner document.
    submissions = {n: read_json(frozen_root/n, b, 4*MIB, frozen["members"][n]) for n in sorted(expected)}
    selection_pins = frozen["reference_selection_pins"]
    need(set(selection_pins) == (set(CONDITIONS) if methods != ["candidate"] else set()),
         "complete frozen development-selection custody")
    selections = {c: read_json(frozen_root/f"REFERENCE_SELECTION_{c}.json", b, 4*MIB, selection_pins[c])
                  for c in selection_pins}
    for c, selection in selections.items():
        need(selection["submissions"] == {m: submissions[f"{c}__{m}.json"] for m in methods},
             "frozen selection/submission byte-semantics join")
    packets = load_packets(root, bundle, b)
    # A valid file hash only authenticates bytes. Check every complete public
    # query and envelope in both conditions before opening either owner file.
    score_admission.validate_public_submissions(packets, submissions, methods, selections)
    owners = {c: read_json(root/f"OWNER_{c.upper()}.json", b,
                          expected=bundle["members"][f"OWNER_{c.upper()}.json"]) for c in CONDITIONS}
    audit_pair(packets, owners)
    reference_scores = {c: reference_protocol.score_frozen(owners[c], selections[c], selection_pins[c]["sha256"])
                        for c in selections}
    reports = {f"{c}__{m}.json": (reference_scores[c]["reports"][m] if selections else
               grader.grade(owners[c], submissions[f"{c}__{m}.json"])) for c in CONDITIONS for m in methods}
    output = fresh_directory(args.output)
    pins = {name: write_json(output/name, report, b, 4*MIB) for name, report in reports.items()}
    valid = all(r.get("status") == "COMPLETE_DEPOSITED_LABEL_SCORE_ONLY" and r.get("primary_metric") is not None
                for r in reports.values())
    summary = {"schema": "apcx-complete-portable-score-receipt-v1", "profile": profile.PROFILE,
        "status": "COMPLETE_SCOPED_SCORE" if valid else "INVALID_NO_COMPLETE_TASK_SCORE",
        "reports": pins, "bundle_sha256": args.bundle_sha256, "frozen_sha256": args.frozen_sha256,
        "predeclared_primary_differences": {c: v["predeclared_primary_differences"] for c,v in reference_scores.items()},
        "remaining_physical_primary_holds": list(core.HOLDS), "broad_scientific_qualification": False,
        "new_benchmark_count": 0, "candidate_process_isolation_attested_by_this_cli": False}
    pin = write_json(output/"SCORES.json", summary, b, MIB)
    if not valid:
        raise ValueError("Invalid complete submission; failure reports retained, no task score")
    return pin


def reference(args, b):
    """Explicit opt-in one-session fixed reference, never invoked by provisioning."""
    need(platform.python_version() == "3.12.8", "reference requires the accepted Python3.12.8 version")
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
        need(os.environ.get(name) == "1", "set numerical threads1 before process start")
    episode = read_json(args.episode, b, boundary.MAX_EPISODE_BYTES)
    boundary.validate_episode(episode)
    import numpy as np
    import reference_math
    need(np.__version__ == "2.2.6", "reference requires the accepted NumPy2.2.6 version")
    trace = reference_math.reference_session(episode["session"], np, lambda: check(b))
    response = {"status": "COMPLETE_ONE_SESSION_REFERENCE_TRACE", "condition": episode["condition"],
        "session_id": episode["session"]["session_id"], "participant_packet_sha256": episode["participant_packet_sha256"],
        "input_sha256": boundary.digest(episode), "invented": episode["invented"], "reference": trace}
    return write_json(absolute(args.output), response, b, boundary.MAX_RESULT_BYTES)


def main(argv=None):
    need(sys.platform in ("darwin", "linux"), "portable task supports POSIX macOS/Linux only")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("convert", "provision"):
        p = commands.add_parser(name); p.add_argument("--inputs", required=True); p.add_argument("--output", required=True)
    for name in ("episodes", "assemble", "select-references", "score"):
        p = commands.add_parser(name); p.add_argument("--bundle", required=True); p.add_argument("--bundle-sha256", required=True)
        p.add_argument("--output", required=True)
        if name in ("assemble", "select-references"): p.add_argument("--responses", required=True)
        if name == "score":
            p.add_argument("--submissions", required=True); p.add_argument("--frozen-sha256", required=True)
    p = commands.add_parser("reference"); p.add_argument("--episode", required=True); p.add_argument("--output", required=True)
    args = parser.parse_args(argv); b = budget()
    functions = {"convert": convert, "provision": provision, "episodes": episodes,
                 "assemble": assemble, "select-references": lambda a, z: assemble(a, z, True),
                 "score": score, "reference": reference}
    result = functions[args.command](args, b)
    receipt = core.canonical({"output_pin": result, "managed_bytes": b.used,
        "scope": "deposited Total_pulse conditional task only", "no_candidate_process_launched": True})
    check(b)  # No successful terminal receipt after a late observed resource breach.
    sys.stdout.buffer.write(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
