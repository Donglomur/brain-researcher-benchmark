#!/usr/bin/env python3
"""Task-specific REP012 matched access packets; planning is metadata-only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata

TASK = "PAPER-FIND-REP-012"
PROFILE = "method_assisted_main_text_paired_access_v1"
CATALOG_PIN = {"bytes": 2564, "sha256": "4fffc7d81f920bc896beb3e7f0c693e398e6d67283506b29fc1e9a9bcca32a79"}
TASK_PIN = {'bytes': 3082, 'sha256': 'b6dff061ac16f0e15397d64c628431f74254f19c1df330afa0b549b179bc732c'}
META_CAP = 65536
PAYLOAD_CAP = 8 * 1024 * 1024
TOTAL_CAP = 32 * 1024 * 1024
SCORER_SHA = "b3e9ba4bcc3492b31877399704f5d85f12b3dab01550f8a02be84dca2882b368"
CREDENTIAL = re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[A-Z0-9]{16}|sk-[A-Za-z0-9]{24,}")


def need(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, expected):
    need(type(value) is dict and set(value) == set(expected), "Exact metadata fields required")


def encode(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=2) + "\n").encode()


def decode(body):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, "Duplicate JSON field")
            value[key] = item
        return value
    try:
        return json.loads(body.decode("utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite metadata")))
    except (UnicodeError, RecursionError) as exc:
        raise ValueError("Invalid metadata encoding or nesting") from exc


def sha(value):
    need(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None, "Lowercase SHA256 required")
    return value


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def admit_pin(value, cap=PAYLOAD_CAP):
    keys(value, ("bytes", "sha256"))
    need(type(value["bytes"]) is int and 0 < value["bytes"] <= cap, "Bounded nonempty extent required")
    sha(value["sha256"])
    return value


def path(value, *, inspect=False):
    need(type(value) is str and 0 < len(value) <= 4096 and value == os.path.abspath(value) and str(Path(value)) == value,
         "Canonical absolute path required")
    result = Path(value)
    if inspect:
        need(all(not p.is_symlink() for p in (result, *result.parents)), "Symlink path or ancestry refused")
    return result


def entry(value):
    keys(value, ("path", "bytes", "sha256"))
    path(value["path"])
    return admit_pin({k: value[k] for k in ("bytes", "sha256")})


def read_file(value, expected, cap=PAYLOAD_CAP):
    """One bounded ordinary-file read; does not traverse a selected directory."""
    admit_pin(expected, cap)
    p = path(str(value), inspect=True)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == expected["bytes"],
             "Exact ordinary single-link file required")
        chunks, remaining = [], before.st_size
        while remaining:
            block = os.read(fd, min(remaining, 65536))
            need(bool(block), "Truncated source")
            chunks.append(block)
            remaining -= len(block)
        after = os.fstat(fd)
        attrs = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        need(not os.read(fd, 1) and all(getattr(before, k) == getattr(after, k) for k in attrs),
             "Source changed during read")
        body = b"".join(chunks)
        need(pin(body) == expected, "Selected content identity mismatch")
        return body
    finally:
        os.close(fd)


def package():
    here = Path(__file__).absolute().parent
    catalog = decode(read_file(here / "CATALOG.json", CATALOG_PIN, META_CAP))
    need(catalog["task_id"] == TASK and catalog["profile"] == PROFILE, "Exact packet catalog")
    documents = {"task/" + name: read_file(here / name, value, META_CAP)
                 for name, value in catalog["documents"].items()}
    documents["task/TASK.md"] = read_file(here / "TASK.md", TASK_PIN, META_CAP)
    return catalog, documents


def within(child, parent):
    """Metadata-only ancestry across case/normalization aliases.

    For nonexistent suffixes compare conservative NFD/casefold components below
    the nearest existing physical ancestor. This can reject distinct names on a
    case-sensitive filesystem; it never asserts a hostile-race boundary.
    """
    child, parent = path(str(child), inspect=True), path(str(parent), inspect=True)
    anchor, suffix = parent, []
    while True:
        try:
            st = anchor.lstat()
            break
        except FileNotFoundError:
            need(anchor.parent != anchor, "Existing path ancestor required")
            suffix.insert(0, anchor.name)
            anchor = anchor.parent
    target = (st.st_dev, st.st_ino)
    normalize = lambda parts: tuple(unicodedata.normalize("NFD", part).casefold() for part in parts)
    wanted = normalize(suffix)
    for current in (child, *child.parents):
        try:
            observed = current.lstat()
        except FileNotFoundError:
            continue
        if (observed.st_dev, observed.st_ino) == target:
            remainder = normalize(child.relative_to(current).parts)
            return len(remainder) >= len(wanted) and remainder[:len(wanted)] == wanted
    return False


def exclusions(value):
    keys(value, ("files", "paths"))
    need(type(value["files"]) is list and 1 <= len(value["files"]) <= 128,
         "Explicit excluded private/historical identities required")
    for item in value["files"]:
        admit_pin(item, TOTAL_CAP)
    need(type(value["paths"]) is list and 1 <= len(value["paths"]) <= 128,
         "Explicit excluded private/historical paths required")
    return [path(item) for item in value["paths"]]


def validate_selection_metadata(selection, catalog):
    keys(selection, ("schema_version", "task_id", "profile", "sources", "review", "runtime", "budget", "exclusions"))
    need(type(selection["schema_version"]) is int and selection["schema_version"] == 1 and
         selection["task_id"] == TASK and selection["profile"] == PROFILE, "Exact REP012 finite paired profile")
    fixed = dict(catalog["inputs"])
    fixed.update({"task/author_code/" + name: value for name, value in catalog["official_code"].items()})
    keys(selection["sources"], fixed)
    for name, expected in fixed.items():
        need(entry(selection["sources"][name]) == expected, "Exact accepted material roster")
    entry(selection["review"])
    keys(selection["runtime"], ("identity_sha256", "tool_contract_sha256"))
    for value in selection["runtime"].values():
        sha(value)
    keys(selection["budget"], ("wall_seconds", "cpu_seconds", "memory_bytes", "model_tokens", "network"))
    limits = {"wall_seconds": 86400, "cpu_seconds": 86400, "memory_bytes": 1024 ** 4, "model_tokens": 10000000}
    for field, upper in limits.items():
        value = selection["budget"][field]
        need(type(value) is int and 0 < value <= upper, "Explicit identical positive study allocation required")
    need(selection["budget"]["network"] == "none", "Both conditions are offline")
    forbidden = exclusions(selection["exclusions"])
    rows = [*selection["sources"].values(), selection["review"]]
    for item in rows:
        need(entry(item) not in selection["exclusions"]["files"] and not any(
            within(path(item["path"]), bad) for bad in forbidden),
            "Excluded source/review identity or path")
    review_path = path(selection["review"]["path"])
    for item in selection["sources"].values():
        need(entry(selection["review"]) != entry(item) and
             not within(review_path, path(item["path"])) and not within(path(item["path"]), review_path),
             "Review must be distinct from every article/data/code source before reading")


def validate_selection(selection, review, catalog):
    validate_selection_metadata(selection, catalog)
    keys(review, ("schema_version", "task_id", "profile", "decision", "paper_coverage", "reviewed_inputs",
                  "reviewed_official_code", "official_provenance", "authorized_local_research_use",
                  "contains_private_references", "contains_historical_outputs", "contains_credentials",
                  "denied_files", "denied_paths"))
    need(type(review["schema_version"]) is int and review["schema_version"] == 1 and
         review["task_id"] == TASK and review["profile"] == PROFILE and
         review["decision"] == "approved_exact_candidate_materials_for_local_use", "Independent exact material review required")
    need(review["paper_coverage"] == "author_manuscript_main_text_only", "Do not claim document-complete paper access")
    need(review["reviewed_inputs"] == catalog["inputs"] and
         review["reviewed_official_code"] == catalog["official_code"] and
         review["official_provenance"] == catalog["official_provenance"], "Review must bind the entire immutable roster")
    need(review["authorized_local_research_use"] is True, "Local use requires operator authorization")
    for field in ("contains_private_references", "contains_historical_outputs", "contains_credentials"):
        need(review[field] is False, "Private material, cached outputs and credentials are excluded")
    need(type(review["denied_files"]) is list and 1 <= len(review["denied_files"]) <= 128,
         "Explicit excluded private/historical identities required")
    for value in review["denied_files"]:
        admit_pin(value, TOTAL_CAP)
    need(type(review["denied_paths"]) is list and 1 <= len(review["denied_paths"]) <= 128,
         "Explicit excluded private/historical paths required")
    need(review["denied_files"] == selection["exclusions"]["files"] and
         review["denied_paths"] == selection["exclusions"]["paths"],
         "Review must match independently selected exclusions exactly")
    forbidden = [path(value) for value in review["denied_paths"]]
    source_paths = []
    for item in selection["sources"].values():
        p = path(item["path"])
        need(entry(item) not in review["denied_files"] and not any(within(p, bad) for bad in forbidden),
             "Excluded source identity or path cannot enter a candidate packet")
        source_paths.append(p)
    need(len(set(source_paths)) == len(source_paths), "Distinct selected source paths required")
    need(path(selection["review"]["path"]) not in source_paths, "Operator review is not a candidate material")
    total = 2 * sum(v["bytes"] for v in catalog["inputs"].values()) + sum(
        v["bytes"] for v in catalog["official_code"].values()) + 512 * 1024
    need(total <= TOTAL_CAP, "Both complete packets and metadata must fit the fixed cap")


def prepare(selection, review, catalog, documents):
    validate_selection(selection, review, catalog)
    common = {name: pin(body) for name, body in documents.items()}
    common.update(catalog["inputs"])
    contract = encode(dict(schema_version=1, task_id=TASK, profile=PROFILE,
        method_assisted=True, paper_coverage="author_manuscript_main_text_only",
        supplementary_methods_available=False,
        condition_difference="Only the approved official source files are available in B",
        runtime=selection["runtime"], budget=selection["budget"],
        input_manifest_sha256=catalog["inputs"]["public/input_manifest.json"]["sha256"],
        numerical_scorer_sha256=SCORER_SHA, output_schema=common["task/OUTPUT_SCHEMA.json"],
        scoring_description=common["task/PUBLIC_SCORING.md"],
        feedback_before_both_outputs_frozen=False, private_reference_in_packet=False,
        code_benefit_established=False))
    documents = dict(documents)
    documents["task/CONDITION_CONTRACT.json"] = contract
    common["task/CONDITION_CONTRACT.json"] = pin(contract)
    code = {"task/author_code/" + name: value for name, value in catalog["official_code"].items()}
    plan = dict(schema_version=1, task_id=TASK, profile=PROFILE, metadata_only=True,
                selection_pin=pin(encode(selection)), review_pin=entry(selection["review"]),
                common=common, code_only_B=code, views={"A": common, "B": dict(common, **code)},
                payload_read=False, candidate_execution=False, data_redistribution_approved=False)
    return plan, documents


def output_boundary(output, selection, review, component_dir):
    root = path(str(output), inspect=True)
    blocked = [path(row["path"]) for row in selection["sources"].values()]
    blocked += [path(selection["review"]["path"]), component_dir, *map(path, review["denied_paths"])]
    need(not any(within(root, p) or within(p, root) for p in blocked), "Output overlaps protected/source locations")
    return root


def write_new(target, body, mode=0o444):
    target.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def seal_directories(root):
    dirs = [root] + [p for p in root.rglob("*") if p.is_dir()]
    for p in sorted(dirs, key=lambda x: len(x.parts), reverse=True):
        os.chmod(p, 0o555)


def census(root, expected):
    root = path(str(root), inspect=True)
    need(root.is_dir(), "Complete candidate root required")
    expected_dirs = {"."}
    for name in expected:
        expected_dirs.update(p.as_posix() for p in Path(name).parents)
    seen, stack, directories, seen_dirs = {}, [root], 0, set()
    while stack:
        directory = stack.pop()
        st = directory.lstat()
        need(stat.S_ISDIR(st.st_mode) and stat.S_IMODE(st.st_mode) == 0o555, "Read-only ordinary candidate directory required")
        relative = directory.relative_to(root).as_posix()
        need(relative in expected_dirs, "Unselected candidate directory")
        seen_dirs.add(relative)
        directories += 1
        need(directories <= 32, "Closed directory count")
        with os.scandir(directory) as entries:
            for item in entries:
                p = Path(item.path)
                st = p.lstat()
                need(not stat.S_ISLNK(st.st_mode), "Candidate aliases are excluded")
                if stat.S_ISDIR(st.st_mode):
                    stack.append(p)
                    continue
                name = p.relative_to(root).as_posix()
                need(name in expected and name not in seen, "Unselected candidate file")
                need(stat.S_IMODE(st.st_mode) == 0o444, "Read-only candidate file required")
                seen[name] = pin(read_file(p, expected[name]))
                need(len(seen) <= 64, "Closed candidate file count")
    need(seen == expected and seen_dirs == expected_dirs, "Exact complete candidate inventory required")
    return seen


def verify_pair(root, plan):
    root = path(str(root), inspect=True)
    need({p.name for p in root.iterdir()} <= {"A", "B", "PACKET_RECEIPT.private.json"}, "Unexpected packet-parent member")
    actual = {arm: census(root / arm, plan["views"][arm]) for arm in ("A", "B")}
    need(all(actual["B"][name] == value for name, value in actual["A"].items()) and
         set(actual["B"]) - set(actual["A"]) == set(plan["code_only_B"]), "Exact code-only intervention")
    return actual


def build(output, selection, review, plan, documents, component_dir):
    root = output_boundary(output, selection, review, component_dir)
    need(not root.exists(), "Fresh packet output required")
    # Check all selected paths before creating output. No directory-copy fallback.
    identities = []
    for row in selection["sources"].values():
        p = path(row["path"], inspect=True)
        st = p.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and st.st_size == row["bytes"],
             "Complete ordinary original source set required")
        identities.append((st.st_dev, st.st_ino))
    need(len(set(identities)) == len(identities), "Aliased original sources refused")
    for p in map(path, review["denied_paths"]):
        if p.exists():
            st = p.lstat()
            need((st.st_dev, st.st_ino) not in identities, "Private/historical physical alias refused")
    root.mkdir(mode=0o700)
    for arm in ("A", "B"):
        (root / arm).mkdir(mode=0o700)
    for name, body in documents.items():
        for arm in ("A", "B"):
            write_new(root / arm / name, body)
    copied = 0
    for name, row in selection["sources"].items():
        body = read_file(row["path"], entry(row))
        if name in plan["code_only_B"]:
            need(b"\0" not in body, "Official code must be ordinary UTF-8 text")
            body.decode("utf-8")
            need(CREDENTIAL.search(body) is None, "Credential-like source content refused")
            arms = ("B",)
        else:
            arms = ("A", "B")
        for arm in arms:
            copied += len(body)
            need(copied <= TOTAL_CAP - 512 * 1024, "Pair retention cap")
            write_new(root / arm / name, body)
    for arm in ("A", "B"):
        seal_directories(root / arm)
    views = verify_pair(root, plan)
    receipt = dict(schema_version=1, task_id=TASK, profile=PROFILE,
                   status="complete_exact_paired_candidate_views", plan_pin=pin(encode(plan)),
                   selection_pin=plan["selection_pin"], views=views,
                   private_reference_read=False, candidate_execution=False,
                   matched_code_benefit_established=False,
                   filesystem_boundary="serialized operator-owned; not hostile concurrent sandbox")
    write_new(root / "PACKET_RECEIPT.private.json", encode(receipt), 0o400)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("plan", "build", "verify"))
    parser.add_argument("--selection", required=True)
    parser.add_argument("--selection-bytes", type=int, required=True)
    parser.add_argument("--selection-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        selection = decode(read_file(args.selection, {"bytes": args.selection_bytes,
                                "sha256": args.selection_sha256}, META_CAP))
        catalog, documents = package()
        validate_selection_metadata(selection, catalog)
        review = decode(read_file(selection["review"]["path"], entry(selection["review"]), META_CAP))
        plan, documents = prepare(selection, review, catalog, documents)
        component = Path(__file__).absolute().parent
        output = output_boundary(args.output, selection, review, component)
        need(not within(output, path(args.selection)) and not within(path(args.selection), output),
             "Output cannot overlap operator selection")
        if args.operation == "plan":
            need(output.parent.is_dir() and not output.exists(), "New private plan in existing parent required")
            write_new(output, encode(plan), 0o400)
            result = {"status": "metadata_only_plan", "plan_pin": pin(encode(plan)), "payload_read": False}
        elif args.operation == "build":
            result = build(output, selection, review, plan, documents, component)
            result = {"status": result["status"], "views": {arm: len(rows) for arm, rows in result["views"].items()}}
        else:
            verify_pair(output, plan)
            result = {"status": "both_complete_views_verified", "code_only_difference": True}
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError) as exc:
        print(json.dumps({"status": "refused", "error": type(exc).__name__, "reason": str(exc)[:300]}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
