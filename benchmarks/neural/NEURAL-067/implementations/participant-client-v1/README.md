# NEURAL-067 participant protocol client

This helper makes the existing causal programme ABI usable without reimplementing its binary state framing and per-row handshake. It bundles a participant's method into the single source file already required by `trusted-grading-wiring-v1/CONTRACT.md`. It adds no decoder or scientific comparator, changes no observation, target, metric, population, split or budget, and does not enable a direct-observation condition.

Write `method.py` with two functions:

```python
def fit(train_descriptor_path, arm):
    # Read the permitted TRAIN.json and its thirteen complete NPZ runs.
    # Implement your declared training recipe; serialize your fitted state.
    return fitted_state_bytes

def start(state_bytes, arm):
    # Restore that arm's state afresh for this run.
    def step(observation):
        # Update only declared causal filter/history state. Return Python scalars.
        return [tx, ty, tz, rx, g1, g2, g3]
    return step
```

The sketch names intentional method-specific values; it is not an executable baseline. `fit` must return nonempty `bytes` no larger than 32 MiB. `start` receives the raw opaque body, not the training frame. Convert NumPy results with `.tolist()` before returning predictions. Diagnostics belong on stderr; any stdout printed by the method corrupts the protocol and will be rejected by the host.

The literal state magic is `N067STATE1` followed by newline: eleven bytes including the newline, followed by eight length bytes and 32 digest bytes. This matches the host's actual decoder. The older contract's prose byte count is a typo; the literal magic and framing implementation are unchanged.

From this directory, build a fresh output file:

```sh
python3 bundle.py --method /path/to/method.py --output /path/to/program.py
```

The builder checks Python syntax without executing the method and enforces the existing 1 MiB submitted-source cap. The output contains the helper and method, needs no sibling imports, and accepts the original host's `train --arm ... --train ... --state-stdout` and `predict --arm ... --state ... --protocol neural067_causal_v1` commands. Declare all additional method dependencies; the existing candidate image provides Python and NumPy but this helper does not install anything. Bundle and freeze the whole resulting programme before training/query release; record its digest and the required method disclosure. The helper is optional and carries no extra input or compute entitlement.

`TRAIN.json` supplies `runs` entries with `run`, `n_rows`, `file`, `bytes` and `sha256`; files are relative to its directory. Each NPZ includes `velocity` and `eval_mask`. Neural arms also include `spikes`; clock arms include `time_s` and `trial`. All 13 runs and 135,991 training rows remain required. Filter over complete run rows before choosing mask-true fitting labels. The shifted arm's complete training counts are already rotated by half the full run; do not rotate them again. Query shifted-arm counts are unshifted. Fit/selection remains training-only under the frozen method; this helper does not inspect or validate the fitting recipe.

`step` receives only the current allowed observation: 176 unsigned `spikes` for neural arms, and `elapsed_run_s`, `observed_segment_age_s`, `segment_started_now` for clock arms. The helper checks the arm fields and outputs, sends one matching action, flushes, and only then reads the next frame. It never prefetches future frames, sends a request-next command, or reads targets. The host still owns causal release, durable commits, resource limits, complete 56-block admission and private scoring. The helper is participant code and is not an isolation or method-adherence proof.

Seven output coordinates remain `tx, ty, tz, rx, g1, g2, g3` in native source-position increments per 20-ms sample. No multiplication by 50 or SI conversion is introduced. All fourteen later runs, seven sessions, four information arms and 34,490 rows per arm remain required. No target masks or future lengths are released to the callback. The original session scorer retains negative and undefined outcomes and one-person inference limits.

Generated controls exercise the production host's `converse` across all 56 declared run/arm blocks, with every row count retained; the journal is an in-memory test double. Other controls verify production state decoding, actual helper CLI dispatch and a self-contained bundled program without subprocesses. These establish interface behavior only, not Docker/process isolation, authentic-data execution, causal scientific adherence, native understanding, decoding performance or runtime adequacy. Authentic qualification remains separate.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s . -p 'test_client.py' -v
```

The test finds the existing sibling `trusted-grading-wiring-v1` by default. Candidate-only review may set `NEURAL067_IMPLEMENTATIONS` to the read-only checkout's implementations directory. `SOURCE.json` identifies the exact host dependencies; future ABI changes must update this interoperability fixture deliberately.
