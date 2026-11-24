# Compare the complete original ECG-decoding exports

This operator-side component aligns the original Figure 3C,D published scores,
a supplied author-decoder score export, and candidate exports from both
`paper_data` and `paper_data_author_code`. Every input must contain the same
20 released participant aliases (`0`–`19`), EEG and MEG, and all three source
conditions: `ECG_components`, `ECG_not_rejected`, and `ECG_rejected`.

The existing [published-source importer](../published-decoding-panel-v1/README.md)
already authenticates the 120-score public reference. This component adds the
missing complete comparison arithmetic. It keeps all four score vectors and
six paired differences at each of the 120 coordinates, then reports the mean
and sample SD of each difference separately within each modality/condition.
It never pools modalities or conditions, treats rows as independent people,
changes the Pearson-r endpoint, or turns an incomplete run into a subset score.

These are descriptive exported-score differences. They do not reconstruct the
paper's figure confidence intervals, prescribe a candidate inference method or
set a meaningful-gain threshold. `reproduction`, `improvement`, and
`assistance_effect` remain `null`. A favorable difference is not a qualified
paper result. The new component partially addresses comparison preparation;
the selected endpoint's inference/decision gap remains open.

## Input and execution

Use Python 3.11 or later, standard library only, alongside the existing
`published-decoding-panel-v1/published_panel.py` sibling. No installation,
scientific model, raw recording, native inference, or network access is needed.

The published input is the exact original `dec_r_ecg.csv` with the source hash
and size enforced by that sibling. Each of the other three inputs is an external
JSON file of this form, with **all 120** score records rather than the single
illustrative record shown here:

```json
{
  "schema": "cardiac_decoding_score_export_v1",
  "task_id": "PAPER-ROOT-ADD-016",
  "role": "paper_data",
  "declared_support_sha256": "64 lowercase hex characters",
  "producer_sha256": "64 lowercase hex characters",
  "scores": [
    {"subject_id": "0", "device": "eeg", "condition": "ECG_components", "r": 0.25}
  ]
}
```

`role` must be exactly `author_export`, `paper_data`, or
`paper_data_author_code` for its named input. `producer_sha256` identifies the
export-producing program; it is recorded, not independently authenticated.
`declared_support_sha256` is the hash of an operator-held common support manifest
covering the original recording/session-to-released-ID crosswalk, channel and
ICA condition membership, preprocessing exposure, original temporal partitions,
exclusions and `.r` reduction. All three exports must declare the same digest.
**The manifest and its authentic source joins remain unavailable; a chosen hash
does not supply them.** The comparator checks declaration equality and exact
released coordinate membership only; it cannot verify that a producer actually
used that support. Do not construct substitute folds or invent a crosswalk to
satisfy the interface. Exports are limited to 64 KiB and numeric finite r values
in [-1,1]. Missing/duplicate cells and changed aliases fail the entire comparison.

```sh
python3 -I -S -B compare.py \
  --published /external/evaluator/dec_r_ecg.csv \
  --author-export /external/evaluator/author.json \
  --paper-data /external/evaluator/paper-data.json \
  --paper-data-author-code /external/evaluator/paper-data-author-code.json \
  --out /external/evaluator/paired-report.json
```

The output is created exclusively and includes hashes of the exact input files.
Keep it in evaluator storage: it contains the complete published score vector,
which the current access contract reserves from candidate input packets even
though the source deposit is public. The comparison tool does not construct
participant packets or enforce process isolation. A supplied `author_export`
must not be described as an independently verified author execution on the
basis of this report. Likewise, two labeled access-condition exports do not
prove matched paper/data/tool/resource exposure or causal code assistance.

## Scientific limits and source evidence

The [pinned author decoder](https://github.com/schmidtfa/cardiac_1_f/blob/4562c0dc318930c46b77732b73d85504b2b471c4/notebooks/eeg_meg_1f_trf.py)
extracts backward-model `.r` separately for both modalities and three ICA
conditions (lines 83–95), then plots the separate distributions (lines 158–201).
The [helper](https://github.com/schmidtfa/cardiac_1_f/blob/4562c0dc318930c46b77732b73d85504b2b471c4/utils/trf_utils.py)
uses ECG as the backward-model target. The public score labels and aliases are
bound by the existing [source recovery](../published-decoding-panel-v1/SOURCE_RECOVERY.json).
The new diagnostic contrasts are benchmark comparison arithmetic, not a claimed
author inferential analysis or author-specified improvement criterion.

Original recording identities, the published-ID crosswalk, exact nested folds,
source preprocessing exposure and runtime parity remain unresolved. Native
author execution, candidate execution, protected target custody, matched access
and resource budgets, justified reproduction tolerance, and a predeclared
participant-level uncertainty and six-condition decision are still required.
No canonical contract or historical 655-person association component is changed.

## Generated controls

```sh
python3 -I -S -B test_compare.py -v
```

Controls check complete support, actual within-participant differences and their
sample SD, a condition-specific reversal, order invariance, failed/missing
coordinates, mismatched roles/support, invalid scores, altered published bytes,
and CLI input/output routing. One routing control replaces the published loader
with generated rows explicitly; it is not an authentic source import. These
controls establish comparison behavior only, not scientific performance.
