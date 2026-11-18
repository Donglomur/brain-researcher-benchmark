# Original author-law reference producer

This operator-only component fills the fitting bridge between fixed Table 1 targets and the existing `contrast-panel-v2` scorer. It produces all three author-law reference methods over nine targets and both instructions, while retaining separate behavioral and HMP populations. It neither estimates new HMP targets nor changes the candidate's single 18-cell improvement endpoint.

The implementation is **unqualified construction source**. Only generated orchestration tests have run. No authentic EEG, fixed-target payload, optimizer, author model or scientific comparison was executed for this component.

The source calls are grounded in the pinned [original helper](https://github.com/GWeindel/decision-times/blob/76464a9ca15564897e58256081af4b99d08ae8db/utils.py) and [model class](https://github.com/GWeindel/decision-times/blob/76464a9ca15564897e58256081af4b99d08ae8db/models.py). Trial observations are fitted separately for each participant, target and instruction. Each full-data fit and each globally omitted-contrast fit predicts the entire global contrast grid, including contrasts absent from one participant's observations. Trial multiplicity is retained; means do not replace the fitting rows. Contrast percentage points and latency milliseconds are converted to fractions and seconds for the author class, then predictions are converted back. Fechner accuracy comes from the same fitted latency parameters. The original unconstrained linear predictions are not clipped.

`producer.py` verifies the exact task-local parser/scorer dependencies and requires a separately acquired, exact-hash original `models.py`. It executes that verified source from the captured bytes, then calls its original class sequentially. It does not download source, install dependencies, execute notebook outputs, override optimizer bounds or launch joblib workers. It records installed scientific dependency versions; it does not establish their equivalence to the paper's environment. The original class discards some SciPy optimizer diagnostics, so finite predictions and recorded parameters do not prove convergence quality or reference competence. Scientific execution requires a separate admitted resource and source protocol.

After that qualification, an operator can invoke:

```sh
python3 -B benchmarks/paper/PAPER-paper-signal-add-019/implementations/author-law-production-v1/producer.py \
  /external/operator/fixed-targets.json \
  --author-models /external/authenticated-decision-times/models.py \
  --output /external/operator/author-reference-production.json
```

The input is the existing `decision-times-panel-targets-v2` schema. Output schema `decision-times-author-reference-production-v1` includes its fixed-target digest, complete `references` accepted by the existing prediction interface, and per-fit inputs' digests, parameter vectors, training MSE and prediction digests. No partial panel is returned after a fitting failure. The CLI refuses an existing output path. A fit receipt describes this operator's call; it is not an independent execution attestation.

These outputs contain answer-bearing reference predictions and parameters. They must remain operator-private and must never be delivered with the paper or author-code assistance package. Both assistance conditions use the same qualified reference; this producer does not implement participant delivery or candidate isolation.

The generated tests use recording backends and a recording author-class shim, with no optimization. They cover complete 26-person geometry, irregular contrast support, distinct B/H populations, incorrect responses, unequal trial multiplicity, unit conversion, complete prediction coverage, malformed outputs, source-hash refusal and failure before a partial panel is emitted. Run the maintained test command through the project's shared test pool:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-signal-add-019/implementations/author-law-production-v1/tests -v
```

This new command still needs central component-manifest/CI enrollment by the repository integrator. It is not automatically covered by task-local test discovery elsewhere.

Authentic B/H identities, the original 512-Hz HMP target lineage, reference numerical reproduction, optimizer environment, scientific tolerance, protected evaluation, biological uncertainty and the joint 18-cell improvement rule remain unresolved. Table 1 and Results paragraph discrepancies are unchanged. No reproduction pass, paper win, current-SOTA claim or benchmark readiness promotion is assigned.
