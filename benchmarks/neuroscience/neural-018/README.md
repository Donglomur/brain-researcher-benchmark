# NEURAL-018: population forecasting

This existing assignment is distinct from NEURAL-017 co-smoothing: **query activity stops at+450ms**, and labels are the subsequent 200 ms for all 182 neurons. All 1,721 training / 574 development source trial IDs are retained. Data are referenced lazily; no recording or observation-packet copies are stored here.

The task uses official MC_Maze timing and joint forward-bps, with explicitly permitted condition context. It is condition-assisted local development forecasting, not an official leaderboard result. The historical source is one exposed animal/session. Past-only access to preprocessed spikes is not evidence of biological causality or online spike sorting.

From the repository root with the pinned existing Docker image and local daemon access:

```sh
python3 benchmarks/neuroscience/neural-018/score.py validate --submission /absolute/predictions.npz --output /absolute/new-validation.json
python3 benchmarks/neuroscience/neural-018/score.py score --submission /absolute/predictions.npz --output /absolute/new-score.json
```

The common CLI dispatches the same verified entrypoint. `INSTRUCTIONS.md` defines the arbitrary-submission contract; `assets.json` binds the public/private lazy assets. Public candidates receive only its three public files plus instructions and license. Never mount the complete operator package, workspace, raw NWB, private targets or stored reference arrays into a candidate environment.

Scoring runs trusted code only in a fresh offline nonroot read-only container with 2 CPUs, 4 GiB, two numerical threads and 128 MiB private scratch. It snapshots and hashes the candidate before parsing, validates headers/CRC/public identities before target loading, and never executes candidate code. Each command has a 48-second work deadline and cleanup reserve within 60 seconds. A separate bounded operator driver verifies the actual scoring entrypoint. Validation alone produces no scientific score.

The three frozen baseline results are unfavorable: global training rate −0.00321997, condition/time −0.36381110 and past-activity plus condition −0.71781810 bits/spike. All official/scalar metric checks passed. Their negative results are preserved; no retuning followed within the frozen reference study. The raw primary score and **all three signed comparisons** are reported. There is no binary scientific-success threshold, and beating the weak condition model is not an improvement claim by itself.

This package can qualify a local scoring path while research admission remains false. It does not authenticate agent programs, inner-validation provenance, reasoning quality or strong baseline competence. A better regularized forecast reference needs a separately frozen, explicitly outcome-informed development study. The 180 seconds of fixed-reference allocation are already closed; future scientific runs require their own bounded decision.
