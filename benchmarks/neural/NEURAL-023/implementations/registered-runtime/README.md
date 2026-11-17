# Across-day finger-velocity decoding

NEURAL-023 asks whether neural activity can predict finger velocity on a later recording day with a declared calibration interval. This local component scores a completed prediction file for Indy 2016-10-05 → 2016-10-06. It uses one animal and one transfer pair.

The public packet contains a bounded source-day segment with spike counts and velocity labels, the first 60 seconds of next-day calibration counts and labels, and later assessment counts without velocity labels. Its three exact file identities are listed in `public_assets.json`. The assessment has 22,091 endpoints, IDs 3010–25100 inclusive, after the fixed calibration/assessment guard. The targets are trailing 20 ms finger velocities in m/s, x then y. Public spike counts use 96 electrodes in 20 ms bins.

Submit an NPZ containing exactly `case_id` with shape `(22091,)` and `velocity_m_s` with shape `(22091, 2)`. Every public ID must appear once. Rows may be reordered because scoring joins by ID. Predictions must be finite. Standard stored or compressed NPZ files and the permitted integer/float widths are supported; see `public_contract.md` for the exact bounded schema.

The primary score is the mean of x and y R². Negative scores are valid. Secondary outputs include per-axis R², MSE, MAE, descriptive clock-block metrics and signed differences against all seven saved reference methods. There is no binary scientific-success threshold. Invalid files and numerical-overflow outcomes receive explicit statuses and null primary scores.

The isolated file-scoring component and ordinary common CLI are locally verified; the [completed CLI scoring receipt](../../../artifacts-build/rtt-submission-cli-integration-001/outer_receipt.json) records the actual scoring and cleanup. The registered local scoring command is:

```sh
python3 tools/neurobench.py score NEURAL-023 --submission /absolute/path/predictions.npz --output /absolute/path/to/repository/artifacts-build/fresh-attempt --review authoring/rtt-transfer-v1/scoring-adapter-v2/REVIEW_FOR_THIS_ATTEMPT.json --other-reserve-bytes 102000000
```

Each invocation needs its own current cost/storage review and fresh output path. The other-reserve value is an example from preparation, not a permanent default. The scorer performs no fit or model call and executes no submitted program. It requires the existing local runtime, acquired packet and pinned reference artifacts; this package is not a self-contained download.

The assessment is exposed development data. A scored prediction file does not establish training/selection provenance, unseen-test generalization, online causal access, population uncertainty or LLM performance. A separately qualified submitted-program path is now registered; the matched investigator and evidence-assessment contract remains unfinished. This component retains the existing task ID and is not a claim that the full benchmark specification is complete.

## Submitted-program path

The registered `neurobench.py run NEURAL-023` command uses the qualified [program wrapper](../../../authoring/rtt-transfer-v1/program-runner-v1-preparation/RESULTS.md). Follow the [public program instructions](../../../authoring/rtt-transfer-v1/program-runner-v1-preparation/PUBLIC_INSTRUCTIONS.md): one committed Python file receives only the declared source, calibration, target-free assessment and public manifest, and writes `predictions.npz`. The producer and output resources are removed before private scoring. Assessment access is a full batch; later assessment counts are allowed.

A future ordinary attempt allocates 90 seconds and requires its own reviewed source/cost/output/reservation record. The [pending attempt template](../../../authoring/rtt-transfer-v1/program-runner-v1-preparation/ORDINARY_REVIEW_TEMPLATE.json) grants no execution. Current known RTT history is 1,360 seconds after qualification. The numerical qualification has run; a separate ordinary common-CLI program attempt has not.
