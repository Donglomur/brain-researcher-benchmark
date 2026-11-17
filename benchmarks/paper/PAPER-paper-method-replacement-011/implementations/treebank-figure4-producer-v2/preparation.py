"""Build the named paper-eligibility configuration from published metadata.

No HDF5, transcript/timing arrays, source imports or model operations occur here.
The wrapper is newly authored; it does not assert historical author masking.
"""
from __future__ import annotations

import argparse
import csv
import io
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from custody import (AUTHOR_COMMIT, TASK_ID, canonical_bytes, digest, loads, pinned_metadata,
                     read_bounded, require, verify_checkout, write_json_exclusive, zip_member)


def normalize_label(label):
    require(isinstance(label, str) and label and label == label.strip(), "nonempty electrode label required")
    normalized = label.replace("*", "").replace("#", "").replace("_", "")
    require(normalized, "empty normalized electrode label")
    return normalized


def ordered_contacts(labels, exclusions):
    require(isinstance(labels, list) and labels and isinstance(exclusions, list), "label/exclusion lists required")
    normalized = [normalize_label(value) for value in labels]
    rejected = [normalize_label(value) for value in exclusions]
    require(len(normalized) == len(set(normalized)), "ambiguous normalized electrode labels")
    require(len(rejected) == len(set(rejected)), "duplicate normalized exclusions")
    require(set(rejected) <= set(normalized), "exclusion identity missing from original labels")
    rejected_set = set(rejected)
    return [{"raw_label": raw, "contact": clean, "label_index": index,
             "hdf5_dataset": f"data/electrode_{index}", "excluded": clean in rejected_set,
             "recording_control": clean.startswith("DC") or clean.startswith("TRIG"),
             "exclusion_reason": "published_corrupted_electrodes_entry" if clean in rejected_set else None}
            for index, (raw, clean) in enumerate(zip(labels, normalized))]


def rows_by_contact(rows, context):
    result = {}
    for row in rows:
        require(isinstance(row, dict) and "Electrode" in row, f"{context}: Electrode column required")
        contact = normalize_label(row["Electrode"])
        require(contact not in result, f"{context}: ambiguous normalized anatomical row")
        result[contact] = dict(row)
    return result


def build_manifest(inventory, labels, exclusions, recordings, anatomy, coordinates):
    """Pure metadata join. Production admission of pinned bytes is in prepare()."""
    require(isinstance(inventory, dict) and inventory, "ordered original recording inventory required")
    require(set(labels) == set(inventory) == set(exclusions) == set(anatomy), "subject support differs")
    subjects, eligibility = [], {}
    total_labels = total_excluded = total_controls = excluded_controls = 0
    for subject, runs in inventory.items():
        require(isinstance(runs, list) and runs and len(set(runs)) == len(runs), "ordered unique runs required")
        contacts = ordered_contacts(labels[subject], exclusions[subject])
        atlas = rows_by_contact(anatomy[subject], subject)
        used = set()
        for row in contacts:
            name = row["contact"]
            row["anatomy"] = atlas.get(name)
            row["released_coordinates"] = coordinates.get((subject, name))
            row["map_subject_eligible"] = subject != "sub_5"
            if name in atlas:
                used.add(name)
        recording_rows = []
        for run in runs:
            require((subject, run) in recordings, "missing original recording metadata")
            metadata = recordings[(subject, run)]
            require(isinstance(metadata, dict) and isinstance(metadata.get("filename"), str), "movie filename required")
            recording_rows.append({"run": run, "metadata": metadata,
                                   "hdf5_relative_path": f"all_subject_data/{subject}_{run}.h5",
                                   "timings_relative_path": f"subject_timings/{subject}_{run}_timings.csv"})
        eligibility[subject] = [row["contact"] for row in contacts if not row["excluded"]]
        require(eligibility[subject], "a source subject has no eligible contact")
        subjects.append({"subject": subject, "recordings": recording_rows, "contacts": contacts,
                         "unused_anatomy_rows": sorted(set(atlas) - used)})
        total_labels += len(contacts)
        total_excluded += sum(row["excluded"] for row in contacts)
        total_controls += sum(row["recording_control"] for row in contacts)
        excluded_controls += sum(row["recording_control"] and row["excluded"] for row in contacts)
    require(set(recordings) == {(subject, run) for subject, runs in inventory.items() for run in runs},
            "recording metadata has missing/extra selected identities")
    return {
        "schema": "treebank-figure4-preparation/v2", "task_id": TASK_ID,
        "role": "new_paper_eligibility_configuration_not_historical_mask_attestation",
        "source_commit": AUTHOR_COMMIT, "subjects": subjects,
        "recording_inventory": inventory, "eligibility": eligibility,
        "counts": {"subjects": len(subjects), "recordings": sum(map(len, inventory.values())),
                   "recording_labels": total_labels, "published_exclusions": total_excluded,
                   "recording_controls": total_controls, "neural_labels": total_labels - total_controls,
                   "excluded_controls": excluded_controls, "excluded_neural": total_excluded - excluded_controls,
                   "nominal_eligible_contacts": total_labels - total_excluded},
        "seizure_preparation": {"status": "unverified", "intervals": None,
                                "reason": "No authenticated interval mask or upstream removal receipt is supplied."},
        "scientific_status": "metadata_only_not_original_result_reproduction",
    }


def csv_rows(raw):
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames)), "unique CSV header required")
    rows = list(reader)
    require(all(None not in row and all(value is not None for value in row.values()) for row in rows),
            "malformed CSV width")
    return rows


def subject_id(value):
    require(isinstance(value, str), "coordinate subject must be text")
    if value.startswith("sub_"):
        value = value[4:]
    require(value.isdigit() and 1 <= int(value) <= 10, "invalid coordinate subject")
    return f"sub_{int(value)}"


def assemble(source_checkout, labels_zip, excluded_json, subjects_zip, localization_zip):
    source = verify_checkout(source_checkout)
    inventory_path = Path(source_checkout) / "data/all_trials.json"
    inventory_raw = read_bounded(inventory_path, 65536)
    inventory = loads(inventory_raw)
    require(set(inventory) == {f"sub_{index}" for index in range(1, 11)}, "complete original ten subjects required")
    raw = {"labels": pinned_metadata(labels_zip, "labels"),
           "corrupted": pinned_metadata(excluded_json, "corrupted"),
           "subjects": pinned_metadata(subjects_zip, "subjects"),
           "localization": pinned_metadata(localization_zip, "localization")}
    excluded = loads(raw["corrupted"])
    labels, recordings, anatomy, coordinates, members = {}, {}, {}, {}, []
    with zipfile.ZipFile(io.BytesIO(raw["labels"])) as archive:
        for subject in inventory:
            name = f"electrode_labels/{subject}/electrode_labels.json"
            body = zip_member(archive, name)
            labels[subject] = loads(body)
            members.append({"relative_path": name, "sha256": digest(body), "bytes": len(body)})
    with zipfile.ZipFile(io.BytesIO(raw["subjects"])) as archive:
        for subject, runs in inventory.items():
            for run in runs:
                name = f"subject_metadata/{subject}_{run}_metadata.json"
                body = zip_member(archive, name)
                recordings[(subject, run)] = loads(body)
                members.append({"relative_path": name, "sha256": digest(body), "bytes": len(body)})
    with zipfile.ZipFile(io.BytesIO(raw["localization"])) as archive:
        for subject in inventory:
            name = f"localization/{subject}/depth-wm.csv"
            body = zip_member(archive, name)
            anatomy[subject] = csv_rows(body)
        for row in csv_rows(zip_member(archive, "localization/elec_coords_full.csv")):
            key = (subject_id(row["Subject"]), normalize_label(row["Electrode"]))
            require(key not in coordinates, "ambiguous aggregate coordinates")
            coordinates[key] = row
    manifest = build_manifest(inventory, labels, excluded, recordings, anatomy, coordinates)
    require(manifest["counts"] == {"subjects": 10, "recordings": 26, "recording_labels": 1707,
                                    "published_exclusions": 133, "nominal_eligible_contacts": 1574,
                                    "recording_controls": 19, "neural_labels": 1688,
                                    "excluded_controls": 19, "excluded_neural": 114},
            "authenticated complete metadata support differs")
    example = next(row for subject in manifest["subjects"] if subject["subject"] == "sub_10"
                   for row in subject["contacts"] if row["contact"] == "T1cIf8")
    require(example["label_index"] == 37 and not example["excluded"], "published example binding differs")
    manifest["inputs"] = {key: {"sha256": digest(body), "bytes": len(body)} for key, body in raw.items()}
    manifest["source_file_verification"] = source
    manifest["runtime_metadata_members"] = members
    manifest["inventory_sha256"] = digest(inventory_raw)
    return manifest


def prepare(source_checkout, labels_zip, excluded_json, subjects_zip, localization_zip, output):
    manifest = assemble(source_checkout, labels_zip, excluded_json, subjects_zip, localization_zip)
    output = Path(output).resolve()
    require(not output.is_relative_to(Path(source_checkout).resolve()), "output must be outside author checkout")
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    target = output / "sentence_onset_regression"
    target.mkdir(mode=0o700)
    write_json_exclusive(target / "linear_results.json", manifest["eligibility"])
    write_json_exclusive(output / "prepared.json", manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-checkout", "labels-zip", "excluded-json", "subjects-zip", "localization-zip", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args()
    prepare(args.source_checkout, args.labels_zip, args.excluded_json, args.subjects_zip,
            args.localization_zip, args.output)


if __name__ == "__main__":
    main()
