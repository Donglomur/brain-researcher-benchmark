# NLB local scoring adapter verified

The one authorized follow-up passed in **1.641630834 seconds** through the wrapper's final report (**1.640746667 seconds** before its receipt). The previous sandbox-denied attempt remains unchanged and separately charged.

| Verification | Observed result |
|---|---:|
| Existing GLM submission, co-smoothing bits/spike | 0.2122428078418739 |
| Frozen condition/time comparator, bits/spike | 0.26000008329109686 |
| GLM minus fixed comparator | −0.04775727544922295 |
| Target spikes / valid cells | 53,448 / 3,616,200 |
| Empty submission | Rejected before target loading |
| Wrong-shape submission | Rejected before target loading |

Both malformed cases recorded zero target-loader invocations. The valid reference loaded targets once and matched the earlier scores to the prespecified absolute 1e−10 tolerance. Its negative difference is retained. Scientific scores remain continuous; no binary success threshold was introduced. This verifies the local arbitrary-submission parsing/scoring path, not an agent program, training-selection provenance or research admission.

The worker used the exact pinned image in an offline, nonroot, read-only container with only public packet, operator target/comparator and package mounts. No candidate code, raw recording, model service, new fit or download was used. Worker wall time was **0.391230584 seconds**, process CPU including imports **0.485445 seconds**, peak RSS **331,866,112 bytes**, and cgroup peak **389,505,024 bytes**, below the 4 GiB cap. The 28,983,262-byte temporary reference submission existed only in private tmpfs. No prediction or recording payload was retained in the new package. Inner cleanup and the independent outer exact-name inspect both verified the container absent.

The historical reported NLB cycle stays **736.799/900 seconds**. The failed packaging attempt and successful follow-up each charge their complete separately allocated **60 seconds**: known reported stage charges **856.799 seconds**, with no historical reset or lifetime-completeness claim. No further retry occurred.

`benchmarks/neuroscience/neural-017/manifest.json` now marks `verification.status=passed`, `admission.runnable=true` for local prediction-file scoring only, and keeps full-candidate, research and submission admission false. This remains **one existing NEURAL-017 task**, one exposed Jenkins session, 1,721 training and 574 development trials. No animal-population, forecasting, causal, SOTA or native LLM understanding claim follows.

Run from the repository root with the existing local Docker access:

```sh
python3 benchmarks/neuroscience/neural-017/score.py score --submission /absolute/predictions.npz --output /absolute/new-score.json
```

The common registry can dispatch the same entrypoint via `python3 tools/neurobench.py score NEURAL-017 --submission ... --output ...`. Future scoring operations require their own accounting; the completed verification does not authorize unlimited model or evaluation runs.
