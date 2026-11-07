# NEURAL-096: fixed DMFC timing-prior population analysis

This local component scores a complete numerical analysis of the published, already exposed DMFC session. The observation condition is **selected spike counts**, not raw waveforms or produced-interval prediction. It uses the same 177 fixed trials, 40 units and 15 pre-Set bins as the qualified reference. One animal/session does not establish population generalization.

Use the five individually allowlisted public assets in `assets.json`: unchanged `counts.npz`, selected cue metadata, `TASK.md`, `PUBLIC_CONTRACT.json` and the public manifest. The task requires every supplied trial and all eleven oriented output blocks. Follow the full task and contract; do not substitute a different extraction, fit or effect-size objective. No private reference, operator receipt or parent artifact directory belongs in a candidate's inputs.

Submit an ordinary directory containing exactly `submission.json` and, for a complete answer, `submission.npz`. Whole abstention contains JSON only, with an explicit reason. The JSON cap is 32,768 bytes and NPZ cap 524,288 bytes. Extra files—including an old `score.json`—are rejected. Empty JSON is an invalid answer. The scorer captures only these ordinary files and mounts the snapshots individually.

For an ordinary local score call with a fresh per-call review and allocation:

```text
python3 tools/neurobench.py score NEURAL-096 --submission PATH_TO_DIRECTORY --output FRESH_OUTPUT_PATH --review ROOT_REVIEW_JSON --other-reserve-bytes CURRENT_OTHER_RESERVES
```

The whole ordinary call is bounded to 30 seconds on the existing local offline image at 2 CPUs / 4 GiB. Each call needs a new explicitly recorded allocation and fresh output directory. This package depends on the pinned local authoring sources and artifacts; it does not claim general-host portability or rights-cleared public redistribution. No external model or service is invoked.

**Do not build a scalar-only leaderboard.** The qualified double-prior-reversal control had both scalar errors exactly zero while its raw-mean RMSE was about 0.2910329224 and its public arithmetic audit recorded 25,731 failures. The wrong-coefficient control also had zero scalar errors. Always report both scalar errors, all eleven oriented block errors and the public consistency diagnostics together. A positive or larger neural contrast earns no reward. There is no blended scientific-success score or significance threshold.

Finite inaccurate answers remain scored answers. Whole abstention receives zero coverage and null metrics. Unsupported derived arithmetic is explicit rather than clipped. Public validation precedes the private callback, but a file score cannot prove how its producer trained, what it accessed, whether it computed rather than copied, or whether a model understood neural data. Candidate process execution, input-dependence testing, scientific reasoning validation and a broader research study are separate gates.

The numerical file scorer and the ordinary program command are **locally verified**. Six fixed programs passed before registration: the same developer source reconstructed original and synthetically scaled counts, a valid stale answer received numerical errors, and abstention/malformed/missing outputs preserved their intended outcomes. Separate direct-positive and actual common-command abstention runs reproduced their complete scores. See the [program results](../../../authoring/dmfc-timing/context-trajectory-v1/program-cli-v1/RESULTS.md) and [file-scoring results](../../../authoring/dmfc-timing/context-trajectory-v1/scoring-cli-v1/RESULTS.md).

To execute a Python program of at most65,536 bytes:

```text
python3 tools/neurobench.py run NEURAL-096 --program PROGRAM.py --output FRESH_OUTPUT_PATH --review ROOT_REVIEW_JSON --other-reserve-bytes CURRENT_OTHER_RESERVES
```

The program receives the five scientific assets plus a transport instruction. It emits one bounded750,000-byte `submission.bundle.json`, containing base64 JSON and optional NPZ; the instruction defines the exact envelope. The producer is removed before output decoding and private grading. The ordinary call reserves60 seconds total, including a20-second producer window; setup must leave that window intact before the program starts. A valid abstention receives no numerical private-reference reads. Finite inaccurate results remain scored, with no accuracy floor.

This original-only interface uses exposed data and can be solved with memorized answers. The developer scale control establishes input sensitivity of the program and evaluator, not unseen-input generalization or an anti-contamination guarantee for arbitrary models. No fresh LLM evaluation, full assignment contract or research-release qualification follows.
