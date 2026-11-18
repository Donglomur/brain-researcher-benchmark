"""Finite operator exercise of SVG delivery and fixed descriptive grader controls.

This opens authentic aggregate observations/private references only when called.
The operator package contains both access representations. Viewer participants
must receive only typed index/SVG responses; programme participants receive the
numeric observations. This module does not implement a model/provider sandbox.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


MAX_REPORT_BYTES = 64 * 1024
MAX_EXERCISE_BYTES = 35 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def bounded(path, cap):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and 0 < path.stat().st_size <= cap,
            "ordinary bounded exercise artifact required")
    with path.open("rb") as handle:
        body = handle.read(cap + 1)
    require(0 < len(body) <= cap, "artifact grew beyond bound")
    return body


def exercise_delivery(prepared_directory, completion_sha256, output_directory):
    import delivery
    from exercise_grader import exercise_grader
    from packet import strict_json
    from view import ordered_cells, MAX_SVG_BYTES

    output = Path(output_directory)
    require(output.is_absolute() and output.parent.is_dir()
            and not output.exists() and not output.is_symlink(), "fresh absolute exercise output required")
    for ancestor in (output.parent, *output.parents):
        require(not ancestor.is_symlink() and not (ancestor / ".git").exists(),
                "operator exercise output must remain outside Git in ordinary directories")
    output.mkdir(mode=0o700)
    package = delivery.prepare_bundle(Path(prepared_directory), completion_sha256, output / "bundle")
    manifest_sha = package["manifest"]["sha256"]
    verified = delivery.verify_bundle(output / "bundle", manifest_sha)
    require(package["cells"] == 48 and package["files_written"] == 51
            and package["supported_cells"] + package["unsupported_cells"] == 48
            and package["provider_transport_qualified"] is False,
            "complete scoped observation package required")
    index = delivery.list_cells(output / "bundle", manifest_sha)
    identities = [item[0] for item in ordered_cells()]
    require([cell["cell_id"] for cell in index["cells"]] == identities,
            "typed index must retain every canonical cell")
    views = []
    for identity in identities:
        body = delivery.get_view(output / "bundle", manifest_sha, identity)
        require(type(body) is bytes and 0 < len(body) <= MAX_SVG_BYTES, "bounded typed SVG response required")
        views.append({"cell_id": identity, **pin(body)})
    refused = []
    for identity in ("", "../private/expected-answer.json", identities[0] + ".svg"):
        try:
            delivery.get_view(output / "bundle", manifest_sha, identity)
        except delivery.DeliveryError as error:
            require(str(error) == "exact typed cell ID required", "unexpected selector refusal boundary")
            refused.append(identity)
        else:
            raise ValueError("unlisted/path-like view selector was accepted")
    programme = delivery.read_programme(output / "bundle", manifest_sha)
    original = bounded(Path(prepared_directory) / "participant/observations.json", 16 * 1024 * 1024)
    require(type(programme) is bytes and programme == original,
            "programme observations must be byte-identical to the prepared matched observations")
    grader = exercise_grader(Path(prepared_directory), completion_sha256, output / "private-controls")
    grader_body = bounded(output / "private-controls/REPORT.json", MAX_REPORT_BYTES)
    require(pin(grader_body) == grader["report"], "saved grader-control report differs from return identity")
    grader_record = strict_json(grader_body)
    require(grader_record["supported_cells"] == package["supported_cells"]
            and grader_record["unsupported_cells"] == package["unsupported_cells"],
            "observation and grader support must match")
    require({child.name for child in output.iterdir()} == {"bundle", "private-controls"}
            and all(child.is_dir() and not child.is_symlink() for child in output.iterdir()),
            "unlisted exercise output")
    report = {
        "schema": "neural096-local-delivery-and-grader-exercise/v1", "status": "passed",
        "prepared_completion_sha256": completion_sha256,
        "observation_package": package, "bundle_verification": verified,
        "typed_views": views, "typed_selector_refusals": len(refused),
        "programme_observation": pin(programme), "grader_controls": grader,
        "model_trials": 0, "participant_attempts": 0, "fits": 0,
        "raster_or_provider_transport_qualified": False, "OS_isolation_qualified": False,
        "scientific_inference_qualified": False, "full_task_completed": False,
        "scope": "Local SVG package, typed API and fixed operator grading controls. Deterministic programmed arithmetic does not establish learned neural understanding.",
        "precision": "SVG uses256 colour intensities and finite display geometry; numeric programme observations retain numeric precision. Participant numerical error remains continuous with no relaxed native tolerance.",
        "delivery_boundary": "Operator bundle contains both representations. Native participants must receive only typed index/SVG responses; no programme file, private controls or operator filesystem is delivered to that arm.",
    }
    body = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    require(len(body) <= MAX_REPORT_BYTES, "exercise report exceeds bound")
    total = package["bytes_written"] + grader["bytes_written"] + len(body)
    require(total <= MAX_EXERCISE_BYTES, "exercise artifact cap exceeded")
    descriptor = os.open(output / "REPORT.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(body)
        handle.flush()
        os.fsync(handle.fileno())
    require({child.name for child in output.iterdir()} == {"bundle", "private-controls", "REPORT.json"},
            "unlisted completed exercise output")
    return {"status": "passed", "report": pin(body), "bytes_written": total,
            "files_written": package["files_written"] + grader["files_written"] + 1,
            "typed_views_checked": 48, "typed_selector_refusals": 3,
            "fixed_grader_controls": 9, "model_trials": 0, "participant_attempts": 0,
            "provider_transport_qualified": False, "full_task_completed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared", required=True)
    parser.add_argument("--completion-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(exercise_delivery(args.prepared, args.completion_sha256, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
