# Direct neural-signal development condition

The local packet is constructed and checked. It is a new access condition within NEURAL-077; it does not add a benchmark ID or qualify a research study.

- **Question:** return a target-stimulus probability for one EEG epoch.
- **Input:** full 1,024-sample Cz/Pz epochs at 1,024 Hz, rereferenced to P9/P10 and baseline corrected using the first 256 samples; native stored amplitude units.
- **Calibration:** four fixed labeled training examples, identical for every query. The balanced demonstration fraction is not the natural class prior.
- **Cases:** all 400 existing development trials from two people, with opaque identities. The six full training arrays are an auxiliary baseline resource and must not be mounted or included in the direct-model prompt.
- **Response:** exactly `trial_id` and a finite `target_probability` in [0,1]. No reasoning text or extra keys.
- **Scores:** equal-person balanced accuracy at the frozen 0.5 threshold and natural log loss. A partial response set is incomplete; do not silently drop failures or score a ten-request interface check as a full study.

The packet is at `artifacts-build/erp-direct-signal-packet-002/packet/public/`: prompt, demonstrations, 400 queries, response schema and manifest. Numerical serialization is exact. All data are previously exposed development material; this is not concealed assessment.

The complete contexts measure 72,024–77,878 tokens using the pinned local o200k_base vocabulary. The total for 400 fresh contexts is 30,476,768 prompt-text tokens. API message framing and schema overhead remain separate. No LLM calls have run, and the proposed no-tools inference transport has not been empirically qualified. A prompt instruction alone does not enforce no tools.

The [classical-control results](../../../authoring/erp-core-target-v1/direct-pilot-execution-v1/RESULTS.md) retain a failed four-example LDA and a weak full-training reference; these must not be presented as strong, competitive comparators. A more appropriate low-data comparator is proposed but unexecuted. Full-training log-loss improvement against the swap supports alignment sensitivity on these two people, not a neural mechanism or broad generalization.

After a complete model run, the prepared public-only collector accepts 400 JSONL responses:

```bash
.venv-build/bin/python3 authoring/erp-core-target-v1/direct-signal-v1/assemble_predictions.py \
  --manifest artifacts-build/erp-direct-signal-packet-002/packet/public/manifest.json \
  --responses /absolute/complete-responses.jsonl \
  --out /absolute/new-submission.npz
python3 tools/neurobench.py score NEURAL-077 \
  --submission /absolute/new-submission.npz \
  --output /absolute/new-score-directory --dry-run
```

The collector performs no private scoring. Its strict parser and coverage guards have generated checks; a complete real-model-output collection has not run. The existing qualified file scorer accepts this NPZ schema. A fresh scoring allocation and current storage check precede actual execution. Its historical full-channel comparator is not the matched four-demo reference; use the separately declared direct controls when interpreting this condition.

A subsequent no-fit ranking diagnostic gives full-training AUC 0.62148 and few-shot AUC 0.47539. It also finds 190/400 few-shot predictions wrong at at least 99.9999% stated confidence. This is a descriptive check on the same exposed cases; no primary endpoint or threshold changed. Known retained allocation is 1,800 seconds.

The prepared API transport now passes 16 synthetic tests with network and credentials disabled. It has no-tools request fields, a $1 conditional standard-price spending cap, no retries, fixed cases and explicit incomplete-run accounting. Its actual service boundary and scientific model performance are still untested. See [transport preparation](../../../authoring/erp-core-target-v1/direct-inference-preparation-v1/HANDOFF.md).
