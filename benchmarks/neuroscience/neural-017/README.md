# NEURAL-017: MC_Maze co-smoothing

A runnable **local prediction-scoring package** for the existing NEURAL-017 candidate. This is one task, not 574 tasks. It reuses the qualified real-data packet, frozen comparator and bounded arbitrary-submission grader. Data remain at their pinned existing paths; this package contains no duplicated recordings or prediction arrays.

## Task

Predict the expected spike count of 45 withheld neurons in every 5-ms bin of each of 574 evaluation reach trials, using the same trial's 137 observed neurons and condition information. Fit/select using the 1,721 labeled training trials only. Each trial has 140 bins (700 ms), from −250 to +445 ms bin-left edges relative to movement onset. The complete observed trial is available: this is retrospective co-smoothing, not forecasting.

`INSTRUCTIONS.md` defines the prediction file. `public/schema.json` describes every public array. `assets.json` binds the exact public packet and operator-private files. Only the public packet and declared public instructions/schema/licenses belong in a candidate environment. Do not mount this whole operator package, the parent workspace, raw NWB, private targets, reference arrays, evaluator or prior results in that environment.

## Run

From the repository root, with the already installed Docker engine and pinned scientific image:

```sh
python3 benchmarks/neuroscience/neural-017/score.py validate --submission /absolute/predictions.npz --output /absolute/validation.json
python3 benchmarks/neuroscience/neural-017/score.py score --submission /absolute/predictions.npz --output /absolute/score.json
```

Outputs must be new paths. The operator scoring command runs trusted code only in a fresh offline nonroot container with a read-only root, exactly pinned inputs, 2 CPUs, 4 GiB memory including bounded 128 MiB temporary scratch, two numerical threads and no image pulls. It never executes candidate Python. An input snapshot is SHA256-bound before parsing. Malformed archives are rejected before private target loading. Each command has a 48-second work deadline and cleanup reserve within 60 seconds; partial/error and cleanup receipts are retained. The separate planned verification additionally has a hard outer watchdog and charges its full 60-second allowance.

Validation emits interface validity only. Scoring emits continuous `primary_metric` (co-smoothing bits/spike), the fixed condition/time score and their signed difference, plus support counts. Higher is better. There is no binary scientific pass floor, no normalized oracle reward and no claim that a valid schema demonstrates good prediction. A negative comparator difference remains a valid scored result. Target-zero support is explicitly undefined. The grader's numerical tie tolerance is a floating-point comparison convention, not a significance threshold.

## Scope and provenance

This is one exposed historical Jenkins macaque recording (2009-09-25), DANDI 000128 release 0.220113.0400, with public validation used as development assessment. Trials/neurons/bins do not create independent animals. The local adapter is not Terminal-Bench admission, a full agent-run contract, cross-animal validation, causal evidence, native LLM neural understanding or a SOTA claim. Prior candidate/source exposure remains documented upstream. Program replay, training-selection provenance and scientific-report quality are separate from this numeric adapter and are not re-certified by scoring an NPZ.

The implementation reuses unchanged qualified `grade.py` and `metrics.py`; their source hashes and existing reference results are in `assets.json`. Data are CC BY 4.0 with attribution; the preserved official NLB source license is MIT. See `public/LICENSES.md`. New integration code follows repository policy.

The old NLB workflow ledger remains 736.799/900 seconds as reported. This packaging verification uses a separately authorized, additive, fully charged 60-second allowance; it neither resets nor claims unused time from that cycle. No new fit/download/agent run is part of verification. Future scoring invocations are separately accounted operations.
