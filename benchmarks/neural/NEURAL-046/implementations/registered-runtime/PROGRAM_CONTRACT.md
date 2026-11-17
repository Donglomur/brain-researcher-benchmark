# One fixed program over isolated NEURAL-046 folds

This proposed interface runs one submitted Python source on each of the 13 original source-animal folds. It retains the accepted 2,795 targets, eligibility mask, task and scorer. It does not create new test animals. All animals and the development reference history are exposed; fresh processes do not erase author knowledge or prevent identity-based memorization.

Submit one ordinary UTF-8 Python file, at most 131,072 bytes, and one printable predictor label of at most 80 UTF-8 bytes. The operator commits the exact source bytes/hash and label once, before the first empirical producer. The same source, image and resource profile run in all 13 fresh offline environments, in the frozen source-animal order. No edits, retries, learned checkpoints, outputs or feedback pass from one fold to another. Installed-library imports are permitted inside the offline image; the exact package versions and runtime limits will be published by the separately reviewed runtime. There is no source-import or compile-on-host admission.

Each invocation is:

```
python -I -B /candidate/program.py --input /input/fold.json --identity /input/INPUT_IDENTITY.json --predictor-id LABEL --output /output/predictions.json
```

The only task files visible to that process are the source file, this common program contract and the one fold's `fold.json`, `INPUT_IDENTITY.json`, and `TASK.md`. The process may read its installed environment and use fresh bounded scratch space. The operator does not mount its repository, whole packet directory, original/rotated sibling packets, public all-panel scorer contract, private targets, saved baselines, reference predictions, receipts or earlier outputs. Only the named current fold appears under `/input`; there is no all-fold roster or operator hash in an extra configuration file. The normal track supplies `training_control=original` only.

`TASK.md` defines the target, visible features, units, training/assessment split and scientific limits. Use training responses for fitting and target normalization. All assessment keys must remain present. Algorithms may legitimately ignore training labels, use simple constants, or use any permitted features; matching a ridge reference or demonstrating training-label sensitivity is not an arbitrary-candidate requirement. Process isolation enforces available runtime inputs, not the scientific provenance of a submitted algorithm.

Write exactly one UTF-8 JSON file at `/output/predictions.json`, at most 131,072 bytes. For a complete fold it has exactly these fields:

```json
{
  "schema_version": "neural046-fold-program-output-v1",
  "fold_fingerprint": "<this fold's public payload fingerprint>",
  "packet_fingerprint": "<this fold's public three-file fingerprint>",
  "predictor_id": "<the fixed LABEL>",
  "status": "complete",
  "predictions": [["<asset UUID>", 123, 0.25]]
}
```

Replace the abbreviated predictions with each assessment `(asset_id, cue_event_row0)` exactly once, in any order. These are original source-event row indices, not contiguous cue ordinals. Values may be any finite binary64 JSON numbers, including negative or inaccurate predictions. Do not include mouse/condition columns or response estimates for training rows. Both public fingerprints must match the current input; neither is the operator's all-panel scorer fingerprint.

Fold abstention has the same first five fields with `status="abstain"` and a nonempty printable `reason` of at most 256 UTF-8 bytes in place of `predictions`. There is no row-level abstention or partial complete result. A fold abstention is a request to abstain from the whole panel, because the fixed denominator cannot be reduced.

The validator rejects malformed UTF-8/JSON, duplicate members, extra fields, booleans/null/nonfinite predictions, nonzero numeric literals that round to binary64 zero, invalid Unicode labels, mismatched labels/fingerprints, and missing/duplicate/unknown prediction identities. Numeric token handling must retain the existing scorer's literal-underflow guard before conversion. Ordinary finite binary64 rounding remains allowed. Correctness and prediction accuracy are separate: structurally valid wrong predictions remain gradeable.

A nonzero process exit, timeout, truncated/oversize/missing/malformed result or extra output artifact is an execution/admission failure even if some valid predictions exist. Stdout/stderr are bounded diagnostics, not answer channels. A future runtime will preserve output bytes and admission evidence before asserting success, remove each owned process/container and reap its attachment before starting the next fold, and keep every completed outcome. It will attempt the remaining fixed folds after a handled numerical/output failure when safe and within the granted whole-stage deadline; an unsafe lifecycle state or exhausted deadline stops the panel and explicitly marks unattempted folds. No replacement or selective rerun occurs.

After all producer outcomes are durable and all owned producer resources are absent, the operator determines panel status in this order:

1. **Incomplete:** any failed or unattempted fold. Retain all outcomes and outputs; produce no scoreable aggregate and make no private scorer callback.
2. **Abstained:** every fold ended in a structurally valid complete result or explicit abstention, with at least one abstention. Retain all outcomes; construct whole-panel abstention with the fixed label and a generic bounded reason, and obtain only the existing scorer's nonnumeric abstention result with zero private callback.
3. **Complete:** all 13 outputs are complete. Validate 13 exact fold identities and a disjoint union of exactly 2,795 required assessment keys. Assemble one unchanged `neural046-single-predictor-v1` artifact, in the operator's canonical row order, using its private-to-the-producer all-panel fingerprint. Commit the aggregate before opening the private grading input. Call the unchanged scorer once; retain its full report.

No private metric, target or baseline feedback reaches any producer. The primary score remains equal-source-animal MSE in squared stored dF/F, accompanied by every existing per-animal/condition diagnostic, MAE, bias, numerical-status field and comparison with the five frozen baselines. Overflow/underflow retain the existing nonfinite-score status; do not clip values or rank a favorable subset. Whole abstention is not a numerical score. Code or prose claims about scientific reasoning require separate adjudication.

This is a source-only proposed contract. Its source, parser/aggregation implementation, qualification evidence, runtime limits and budget remain to be separately reviewed and approved. It grants no execution, download, new fit, benchmark registration or model-service authority.
