# Complete released-proxy evaluator

This standalone, standard-library evaluator implements the **current NEURAL-036 primary endpoint**: equal-mouse history-arm MAE minus joint-arm MAE. It restores executable grading absent from the registered-runtime declaration. It requires all 280 predictions across the seven held-mouse folds and four arms; constants, endpoints, null gains and negative gains remain valid.

The current task and understanding contract are unchanged. The recovered historical scorer called fixed persistence-minus-joint its primary. This implementation explicitly promotes the current contract's learned-history contrast and retains fixed persistence as a separate diagnostic. Historical source, predictions, results and declarations are untouched.

## Operator use

Run `scorer.py` with Python 3.10 or later and these required arguments:

```text
python3 -I -B scorer.py \
  --submission SUBMISSION.json \
  --support SUPPORT.json --support-sha256 SUPPORT_SHA256 \
  --targets TARGETS.json --targets-sha256 TARGETS_SHA256 \
  --output NEW_PRIVATE_REPORT.json
```

Supply paths from the authorized operator packet. Both SHA-256 pins must come from its frozen preparation receipt, independently of the candidate. No packet, targets or numeric predictions are bundled here. The file reader checks bounded regular files, symlinks, content hashes and read identity. Inputs are parsed strictly: duplicate object keys, nonfinite constants and malformed JSON fail. Reports require a fresh path and are created with mode 0600. The exit status is zero for `scored`, two for a reported `invalid_submission` or `operator_error`; failure to create a fresh report raises without reading data. Reports are operator-private because session target prevalence is included.

The evaluator parses the submission, authenticates and validates the target-free support, and validates **every** prediction before opening numeric targets. Target failures and support failures are operator errors, never candidate scores. All scores are conditional on truthful frozen operator provenance: hashes establish byte identity, not source legitimacy, split correctness, clock semantics or runtime isolation.

The original data-only ABIs are preserved:

* `SUPPORT.json`: exactly `{"task_id":"NEURAL-036","folds":{"0":[...],...,"6":[...]}}`. Each fold contains ten unique lowercase 64-hex query IDs. All 70 IDs must be unique across mice. As in the pinned original `build.py`, each consecutive five-ID block belongs to one session and follows block origins 0, 60, 120, 180, 240 seconds. The evaluator does not reconstruct or invent animal/context identities.
* `TARGETS.json`: exactly `{"task_id":"NEURAL-036","targets":{ID:{"target":FRACTION,"persistence":FRACTION},...}}`, with exactly the 70 support IDs. Persistence is the original arithmetic mean of 300 past proxy samples; it is not the learned history arm.
* Submission: exactly `{"task_id":"NEURAL-036","predictions":[...]}` with 280 exact `{fold,arm,id,fraction}` rows. Arms are `joint`, `history`, `reverse`, `shift`. Fractions must be nonboolean finite numbers in [0,1]. Unknown IDs, duplicated rows, additional fields and omissions fail; no clipping or partial scoring occurs.

Per-session MAEs average five queries. Per-mouse MAEs average its two sessions, then seven mice receive equal weight. These equal-sized groups are numerically equivalent to the historical ten-query mouse mean. Output includes every session and mouse, all four arm MAEs, all four signed contrasts against joint, and session mean target fractions. The primary is explicitly named `equal_mouse_history_mae_minus_joint_mae_on_released_proxy`.

The original descriptive uncertainty recipe is retained: 10,000 shared draws of seven whole mice, Python `random.Random(36036)`, linear 2.5/97.5 percentiles, fixed predictions and no refitting. It is not a population-level causal test, multiplicity correction, or training uncertainty estimate. There is no scientific pass threshold.

## Source recovery and limits

[SOURCE_PINS.json](SOURCE_PINS.json) records exact inspected source-code identities and current contract pins. Only source text and prior source audits were opened. Historical SUPPORT, TARGETS, POOL, arrays, fitted models and solver outputs were not opened. No source download, native scientific preparation, candidate inference or authentic scoring was performed.

The inspected historical projection defines main input centers `b+10.05+0.1*j` for 300 samples, earlier shifted centers `b+0.05+0.1*j` for 300 samples, and target centers `b+50.05+0.1*j` for 100 samples. It selects the last source sample at or before each center, without extrapolation. These definitions are provenance for the required packet, not an alternative preparation implemented by this scorer.

The target remains the released `freeze_vec` proxy. Physical freezing/movement polarity and per-animal clock lineage remain unresolved; whole-session denoising/cell selection also preclude a strict online causal claim. Reverse and shifted inputs are diagnostic arms, not exchangeable randomization nulls. Seven selected paired mice are not the entire source release. Original source exposure across related tasks remains relevant.

This is a **source-grounded evaluator component with generated software controls**, not a qualified benchmark or a participant execution route. Authentic packet provenance, preparation, participant isolation, matched fitting budgets, all 28 contexts, baseline competence, real scoring and independent scientific qualification still require their own evidence. Direct observation, viewer and tool-assisted conditions are not implemented by an evaluator.

## Generated controls

`test_scorer.py` uses wholly generated IDs and numbers. It checks hand-computed current versus historical contrasts, session/mouse aggregation, a one-nonzero-mouse bootstrap oracle, shared draws, valid negative outcomes, invalid/missing/duplicate identities, strict JSON, target hash failures, missing hashes, the full-submission-before-target-read barrier, symlinks, size caps and fresh report behavior. Run only through the wave's reviewed lightweight test pool; these tests authorize no authentic data/model workload. Actual execution evidence belongs in the external task handoff.
