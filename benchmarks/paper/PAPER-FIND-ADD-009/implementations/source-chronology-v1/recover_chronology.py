"""Recover the authentic published decoder chronology; no recording/model I/O.

The table dates are decoder training dates, NOT trial-level data cutoffs. This
component deliberately does not select Fig. 2b trials from a training table.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

TASK_ID = "PAPER-FIND-ADD-009"
CODE_REVISION = "cff4875decd35ff0f98a944035377a25b43ba79c"
PINS = {
    "supplement_pdf": "004d08f6c8a929a15dbcd61af114dcb5a1102652d78d1c8c32415870d510c514",
    "training_config": "00029dbd8352703b715677ab25d8936b6f56d4782d013e7ba5bf297cfeb526be",
    "session_config": "f2978723864a8d696ae9a72b460579e58b50c9a226272526ec7cdbaa1563f9f8",
}
SOURCE_URLS = {
    "supplement_pdf": "https://static-content.springer.com/esm/art%3A10.1038%2Fs41586-025-09127-3/MediaObjects/41586_2025_9127_MOESM1_ESM.pdf",
    "training_config": f"https://github.com/Neuroprosthetics-Lab/brain-to-voice-2025/blob/{CODE_REVISION}/configs/config.yaml",
    "session_config": f"https://github.com/Neuroprosthetics-Lab/brain-to-voice-2025/blob/{CODE_REVISION}/configs/training_data_args.yaml",
}


class SourceError(ValueError):
    """Source version or recovered structure does not match this component."""


def require(condition, message):
    if not condition:
        raise SourceError(message)


def authenticate(sources):
    require(set(sources) == set(PINS), "all three pinned source roles are required")
    for role, content in sources.items():
        require(isinstance(content, bytes), f"{role} must be captured bytes")
        require(hashlib.sha256(content).hexdigest() == PINS[role], f"source hash mismatch: {role}")


def extract_pdf_text(content, executable="pdftotext"):
    """Extract the same authenticated bytes even if the input path changes."""
    require(hashlib.sha256(content).hexdigest() == PINS["supplement_pdf"], "source hash mismatch: supplement_pdf")
    with tempfile.TemporaryDirectory(prefix="voice-chronology-") as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(content)
        result = subprocess.run([executable, "-layout", str(source), "-"],
                                check=True, capture_output=True, timeout=30)
    return result.stdout.decode("utf-8")


def parse_table_text(raw):
    """Parse Poppler's layout text. Parsing alone does not authenticate a source."""
    title = "Supplementary Table 1. Data used for training the brain-to-voice decoder"
    require(raw.count(title) == 1, "expected one Supplementary Table 1")
    table = raw.split(title, 1)[1]
    first_row = re.search(r"(?m)^\s*25\s*$", table)
    require(first_row is not None, "first-session evaluation day is missing")
    body = table[first_row.start():].replace("(1st session)", " ").strip()
    tokens = body.split()
    require(len(tokens) == 14 * 5, "table must contain exactly fourteen complete five-column rows")
    rows = []
    for offset in range(0, len(tokens), 5):
        evaluation, training, gap, sentences, hours = tokens[offset:offset + 5]
        require(all(re.fullmatch(r"[0-9]+", value) for value in (evaluation, training, gap)),
                "invalid day or reported interval")
        require(re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", sentences) is not None,
                "invalid sentence count")
        require(re.fullmatch(r"[0-9]+\.[0-9]", hours) is not None, "hours must retain the source decimal precision")
        day, trained = int(evaluation), int(training)
        require(trained <= day, "decoder training date is after evaluation")
        rows.append({"evaluation_day_post_implant": day,
                     "most_recent_decoder_training_day_post_implant": trained,
                     "reported_days_between_training_and_evaluation": int(gap),
                     "arithmetic_days_between_training_and_evaluation": day - trained,
                     "cumulative_training_sentences": int(sentences.replace(",", "")),
                     "cumulative_training_hours_decimal": hours,
                     "reported_gap_matches_day_subtraction": int(gap) == day - trained})
    days = [row["evaluation_day_post_implant"] for row in rows]
    require(days == sorted(set(days)), "evaluation days must be unique and increasing")
    require(all(a["cumulative_training_sentences"] < b["cumulative_training_sentences"]
                for a, b in zip(rows, rows[1:])), "cumulative sentence counts must increase")
    return rows


def parse_demo_configs(training, sessions):
    """Read only the narrow fields needed to reconcile the pinned example."""
    def integer_field(key):
        values = re.findall(r"(?m)^  " + re.escape(key) + r":\s*(\d+)\s*(?:#.*)?$", training)
        require(len(values) == 1, "expected exactly one demo field: " + key)
        return int(values[0])

    heldout = re.findall(r"# Note: last session (t15_day\d+) \(session_layer (\d+)\) is held out for testing", sessions)
    require(len(heldout) == 1, "expected explicit held-out session comment")
    listed = re.findall(r'- session: "(t15_day\d+)"\s+session_layer: (\d+)', sessions)
    require(len(listed) == 36 and len({row[0] for row in listed}) == 36, "expected all 36 distinct demo sessions")
    model = re.findall(r'save_model_name: "brain2voice_t15_day(\d+)\.tf"', training)
    require(len(model) == 1, "expected one last-training-day model name")
    require(heldout[0][0] not in {row[0] for row in listed}, "held-out session is in training roster")
    return {"heldout_session": heldout[0][0], "heldout_session_layer": int(heldout[0][1]),
            "last_training_day_from_model_name": int(model[0]),
            "total_trials": integer_field("total_trials"),
            "validation_range_start": integer_field("validation_range_start"),
            "validation_range_end": integer_field("validation_range_end"),
            "n_validation_trials": integer_field("n_validation_trials"),
            "training_sessions": [{"session_id": session, "session_layer": int(layer)}
                                  for session, layer in listed]}


def build_report(sources, extracted_text):
    """Build from pinned source bytes and their extracted table text.

    The public recovery entry point obtains text itself; callers of this helper
    must not treat an independently supplied string as authenticated PDF output.
    """
    authenticate(sources)
    rows = parse_table_text(extracted_text)
    demo = parse_demo_configs(sources["training_config"].decode("utf-8"),
                              sources["session_config"].decode("utf-8"))
    heldout_day = int(demo["heldout_session"].removeprefix("t15_day"))
    matches = [row for row in rows if row["evaluation_day_post_implant"] == heldout_day]
    require(len(matches) == 1, "demo held-out day is absent from the source table")
    last = matches[0]
    return {"schema_version": 1, "task_id": TASK_ID,
            "scope": "published-decoder-training-chronology-and-demo-reconciliation",
            "sources": {role: {"url": SOURCE_URLS[role], "sha256": PINS[role], "bytes": len(content)}
                        for role, content in sources.items()},
            "table_rows": rows,
            "inconsistent_reported_gap_rows": [row for row in rows if not row["reported_gap_matches_day_subtraction"]],
            "author_demo": demo,
            "day195_reconciliation": {
                "published_training_sentences": last["cumulative_training_sentences"],
                "demo_total_trials": demo["total_trials"],
                "published_minus_demo_count": last["cumulative_training_sentences"] - demo["total_trials"],
                "training_day_matches_demo_model_name": last["most_recent_decoder_training_day_post_implant"] == demo["last_training_day_from_model_name"],
                "count_difference_interpretation": "unresolved; this is not evidence identifying 131 missing or excluded trials"},
            "qualification": "source-recovery-component-only",
            "supported_outcomes": ["original-paper-reproduction-preparation", "same-task-improvement-preparation"],
            "limits": [
                "The table lists evaluation sessions, including first-session demonstration; it does not identify Fig. 2b blue sessions or the 956 trial IDs.",
                "Decoder training day is not an exact last input-data day. No universal seven-day exclusion rule is derived.",
                "The inconsistent day139 reported gap is retained literally; neither the training day nor the gap is silently repaired.",
                "Training memberships, original decoder artifact mapping, target access and feature frontend remain unbound.",
                "No scientific reproduction, improvement, original waveform inference or closed-loop result was run.",
                "The 240-trial ten-fold biosignal controls, nonspeech/acoustic-contamination controls and fixed-day165 transfer remain separately required."
            ]}


def recover(sources, executable="pdftotext"):
    authenticate(sources)  # reject every source mismatch before launching anything
    return build_report(sources, extract_pdf_text(sources["supplement_pdf"], executable))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--supplement-pdf", required=True, type=Path)
    parser.add_argument("--training-config", required=True, type=Path)
    parser.add_argument("--session-config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--pdftotext", default="pdftotext")
    args = parser.parse_args(argv)
    try:
        paths = {"supplement_pdf": args.supplement_pdf, "training_config": args.training_config,
                 "session_config": args.session_config}
        require(args.output.resolve() not in {p.resolve() for p in paths.values()}, "output cannot replace an input")
        require(not args.output.exists(), "output already exists; choose a new artifact path")
        report = recover({role: path.read_bytes() for role, path in paths.items()}, args.pdftotext)
        with args.output.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    except (SourceError, OSError, UnicodeError, subprocess.SubprocessError) as error:
        parser.exit(2, f"source recovery rejected: {error}\n")


if __name__ == "__main__":
    main()
