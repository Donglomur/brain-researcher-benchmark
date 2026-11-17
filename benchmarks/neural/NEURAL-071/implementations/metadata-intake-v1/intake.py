"""Pinned Narratives scan inventory; metadata only, with no recording access."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re


CODE_REVISION = "1736849ff80c80e1c73eda375ccf6497f5e234a9"
RAW_REVISION = "8a5af4022cdd78ed4263fc9b226c065e108bb24a"
SUBJECT_SHA256 = "f7b8dfa2ddc8cbeda1a9fa00636788df1e87c77349e8a65d1f72d85ebcc5882d"
PARTICIPANTS_SHA256 = "87f9d5707855dca2c2283184ed6813dc3c84542409c2a59671db909d756d1d1d"
RAW_PINS = {
    "sub-278": "08cffd4d6146294154e42de5a355fcc29d0ba0196db5705326b4ab6aaef22c13",
    "sub-280": "1671ff5bbb9bc2b1d2c3cdec2127135a445aaca5b9c429233da89b10d2cea902",
}
IDENTITY = r"(?P<person>sub-[0-9]{3})_task-(?P<task>[a-zA-Z0-9]+)(?:_run-(?P<run>[0-9]+))?"
SUFFIX = {
    "confounds": r"_desc-confounds_regressors\.tsv",
    "surface": r"_space-fsaverage6_hemi-(?P<hemisphere>[LR])\.func\.gii",
    "raw": r"_bold\.nii\.gz",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(body):
    return hashlib.sha256(body).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON member")
        result[key] = value
    return result


def scan_identity(path, kind, person):
    """Use explicit entities, retaining run strings; never align source list order."""
    require(type(path) is str and "\\" not in path, "invalid source path")
    parsed = PurePosixPath(path)
    require(".." not in parsed.parts and "." not in path.split("/"), "unsafe source path")
    match = re.fullmatch(IDENTITY + SUFFIX[kind], parsed.name)
    require(match is not None and match["person"] == person, "scan identity/person mismatch")
    if kind != "raw":
        require(len(parsed.parts) >= 4 and parsed.parts[-3:-1] == (person, "func"),
                "source directory/person mismatch")
        require(parsed.parts[-4] == "fmriprep", "unexpected derivative pipeline")
    else:
        require(parsed.parts == ("func", parsed.name), "raw filename must be func-relative")
    sid = person + "_task-" + match["task"]
    if match["run"] is not None:
        sid += "_run-" + match["run"]
    return sid, match.groupdict()


def participant_tasks(body):
    rows = csv.DictReader(io.StringIO(body.decode("utf-8")), delimiter="\t")
    require(rows.fieldnames is not None and {"participant_id", "task"} <= set(rows.fieldnames),
            "participant columns")
    result = {}
    for row in rows:
        person = row["participant_id"]
        require(re.fullmatch(r"sub-[0-9]{3}", person or "") is not None and person not in result,
                "duplicate/invalid participant")
        tasks = row["task"].split(",")
        require(tasks and len(tasks) == len(set(tasks)) and
                all(re.fullmatch(r"[a-zA-Z0-9]+", task) for task in tasks), "participant tasks")
        result[person] = set(tasks)
    return result


def raw_scan_ids(body, person):
    rows = csv.DictReader(io.StringIO(body.decode("utf-8")), delimiter="\t")
    require(rows.fieldnames is not None and "filename" in rows.fieldnames, "raw scan columns")
    names, scans = set(), set()
    for row in rows:
        name = row["filename"]
        require(name not in names, "duplicate raw filename")
        names.add(name)
        if name.startswith("anat/"):
            continue
        sid, _ = scan_identity(name, "raw", person)
        require(sid not in scans, "duplicate raw scan")
        scans.add(sid)
    require(scans, "empty raw scan inventory")
    return scans


def join_inventory(subjects, participants, raw_scans):
    """Pure metadata join; callers must authenticate its bodies before admission."""
    require(type(subjects) is dict and subjects and set(subjects) == set(participants),
            "complete participant membership mismatch")
    require(set(raw_scans) <= set(subjects), "unknown raw scan participant")
    inventory, discrepancies, checks = [], [], []
    for person, subject in sorted(subjects.items()):
        confounds, surfaces = {}, {}
        for path in subject["confounds"]:
            sid, entities = scan_identity(path, "confounds", person)
            require(sid not in confounds, "duplicate confound scan")
            confounds[sid] = (entities, PurePosixPath(path).name)
        require(confounds, "participant without scans")
        for path in subject["bold"]["fsaverage6"]["preproc"]:
            sid, entities = scan_identity(path, "surface", person)
            key = (sid, entities["hemisphere"])
            require(key not in surfaces, "duplicate hemisphere")
            surfaces[key] = PurePosixPath(path).name
        require(set(surfaces) == {(sid, hemi) for sid in confounds for hemi in ("L", "R")},
                "complete bilateral scan membership mismatch")
        tasks = {entities["task"] for entities, _ in confounds.values()}
        if tasks != participants[person]:
            discrepancies.append({"person": person,
                "participants_only": sorted(participants[person] - tasks),
                "derivative_only": sorted(tasks - participants[person])})
        raw_ids = raw_scan_ids(raw_scans[person], person) if person in raw_scans else None
        if raw_ids is not None:
            checks.append({"person": person, "derivative_only": sorted(set(confounds) - raw_ids),
                           "raw_only": sorted(raw_ids - set(confounds)),
                           "raw_scan_count": len(raw_ids)})
        for sid, (entities, confound) in sorted(confounds.items()):
            prefix = "derivatives/fmriprep/" + person + "/func/"
            inventory.append({"scan_id": sid, "person": person, "task_alias": entities["task"],
                "run_entity": entities["run"], "raw_filename": "func/" + sid + "_bold.nii.gz",
                "confounds": prefix + confound,
                "preproc_fsaverage6": {h: prefix + surfaces[(sid, h)] for h in ("L", "R")},
                "raw_membership": "not_checked" if raw_ids is None else
                    ("confirmed" if sid in raw_ids else "absent"),
                "story_family": None, "selected_clean_derivative": None})
    return {"scans": inventory, "participant_task_discrepancies": discrepancies,
            "raw_scan_comparisons": checks,
            "counts": {"people": len(subjects), "scans": len(inventory),
                "surface_files": 2 * len(inventory),
                "task_aliases": len({row["task_alias"] for row in inventory}),
                "raw_scans_checked": sum(row["raw_scan_count"] for row in checks)}}


def compile_inventory(subject_body, participants_body, raw_scans):
    """Accept only the retained official revisions; return an operator inventory."""
    require(digest(subject_body) == SUBJECT_SHA256, "subject metadata source pin")
    require(digest(participants_body) == PARTICIPANTS_SHA256, "participant source pin")
    require(set(raw_scans) == set(RAW_PINS) and
            all(digest(raw_scans[p]) == pin for p, pin in RAW_PINS.items()), "raw scan source pins")
    subjects = json.loads(subject_body, object_pairs_hook=_unique_object)
    report = join_inventory(subjects, participant_tasks(participants_body), raw_scans)
    require(report["counts"]["people"] == 345 and report["counts"]["scans"] == 873,
            "pinned manifest census changed")
    report.update({"schema": "n071-source-scan-inventory-v1",
        "sources": {"subject_meta": {"revision": CODE_REVISION, "sha256": SUBJECT_SHA256},
                    "participants": {"revision": RAW_REVISION, "sha256": PARTICIPANTS_SHA256},
                    "raw_scans": {"revision": RAW_REVISION, "sha256_by_person": RAW_PINS}},
        "source_role": "fMRIPrep preprocessed surface/confound inventory; not clean BOLD targets",
        "limitations": [
            "Filename metadata establishes neither payload existence nor immutable clean-derivative identity.",
            "Only the two supplied raw scan tables were checked; no other raw scan agreement is inferred.",
            "Task aliases are not story families. Family grouping and split eligibility remain unresolved here.",
            "No BOLD, audio, transcript, atlas, target, model or prediction body is read.",
            "This intake does not qualify native preparation, F/I execution or direct neural interpretation."]})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject-meta", required=True, type=Path)
    parser.add_argument("--participants", required=True, type=Path)
    parser.add_argument("--sub-278-scans", required=True, type=Path)
    parser.add_argument("--sub-280-scans", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = compile_inventory(args.subject_meta.read_bytes(), args.participants.read_bytes(),
        {"sub-278": args.sub_278_scans.read_bytes(), "sub-280": args.sub_280_scans.read_bytes()})
    # Operator output stays outside Git; never overwrite an earlier evidence product.
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(json.dumps({"counts": report["counts"], "discrepancies": len(report["participant_task_discrepancies"])}))


if __name__ == "__main__":
    main()
