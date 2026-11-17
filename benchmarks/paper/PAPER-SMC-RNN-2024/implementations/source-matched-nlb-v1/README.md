# SMC-RNN: complete original MC_Maze 20-ms comparison

This package prepares the original MC_Maze panel and runs the released 36-dimensional SMC-RNN checkpoints through the paper-era inference implementation. Its intended research endpoint is **improvement over the matching original Table 2 SMC-RNN arm**, with all companion metrics retained. Reproduction is calibration. This package alone does not establish either result.

The two arms are the paper's causal-proposal and noncausal-proposal models. Both call `eval_nlb(..., smooth=False)` with 192 particles and 32 repeats. The noncausal arm uses an acausal proposal encoder; the source routine's separate smoothed posterior is not the published output. The causal encoder uses reflect padding near the start, so this source comparison does not establish strictly online operation.

| Arm | Co-bps | Velocity R² | PSTH R² | Forward bps |
|---|---:|---:|---:|---:|
| SMC-RNN causal proposal | .3225 | .8479 | .5927 | .2184 |
| SMC-RNN noncausal proposal | .3407 | .8902 | .5963 | .2417 |
| LFADS, published comparator | .3554 | .8906 | .6002 | .2454 |
| NDT, published comparator | .3597 | .8897 | .6172 | .2442 |

Exceeding SMC-RNN would not establish current SOTA. See the [original paper](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf), supplement B.5/Table 2 and D.7.

## Run the real input path

Create an external staging directory and reserve resources before acquisition. `acquire.py` fetches only the manifest's required code, selected checkpoint files and two NWBs; no released test target is acquired. Payloads must stay outside public Git. `requirements-cpu.txt` records the qualification environment, including its pandas compatibility substitution. A task-local virtual environment is sufficient; no global installation is required.

```sh
python3 -m venv "$SMC_STAGE/venv"
"$SMC_STAGE/venv/bin/python" -m pip install -r requirements-cpu.txt
"$SMC_STAGE/venv/bin/python" acquire.py --destination "$SMC_STAGE" --assets both
"$SMC_STAGE/venv/bin/python" prepare.py \
  --nwb-dir "$SMC_STAGE/nwb/sub-Jenkins" --output "$SMC_STAGE/inputs" --cpu-seconds-remaining 7200
```

Preparation must run under the operator's native execution lease and memory/CPU budget. It uses the unchanged NLB tensor functions, 20-ms resampling and NWB-defined trial splits. Test inference uses train+validation inputs for the decoder and all test trials. Validation preparation uses only training trials for training tensors. Validation targets are generated locally, with a sequential scheduling wrapper around the original PSTH smoothing function to avoid host-wide multiprocessing; **test targets are never generated or staged in the author input tree**.

Loading keeps every original signal field, since native missing-value handling can affect trial inclusion. Memory-only patches release unused frame references and schedule the original full-time Gaussian smoothing followed by original resampling one neuron at a time before the unchanged PSTH condition calculation. `preparation_memory.patch` records the exact changes; authenticated generated and authentic-input controls compare bytes, indices, trial metadata and dtypes.

The observation interval is 35 bins around movement onset, followed by 10 forward-prediction bins. There are 137 held-in and 45 held-out neurons and 108 task conditions in the complete source cohort. Not every condition necessarily has a nonempty scored test PSTH. Preparation records ordered trial/neuron/condition hashes and exact input hashes in each `panel.json`.

## Run the exact author arm

The operator freezes and reviews `protocol.json` before native execution. Start with `--mode characterize`: it loads and strictly checks the actual selected checkpoint, then times the first original chunk from each complete input split with all 192 particles and the original routine. It emits no partial submission and no score. This determines whether complete inference fits the remaining CPU budget.

```sh
"$SMC_STAGE/venv/bin/python" author_predict.py \
  --source "$SMC_STAGE/author" --inputs "$SMC_STAGE/inputs" \
  --arm causal --mode characterize --report "$SMC_STAGE/causal-timing.json" \
  --cpu-seconds-remaining 7200
```

Use the actual remaining cumulative budget, including preparation and failed attempts. The initial protocol allows 7,200 CPU seconds, six threads, 8 GiB working RAM and one concurrent native job. Do not relabel a partial run as a paper result or lower the source inference recipe to fit it. A justified compute extension requires the operator's resource decision.

For an authorized complete run, use `--mode predict --output "$SMC_STAGE/causal.h5"` and a new report path. Repeat with `--arm noncausal`. The runner passes `target=None`, explicitly selects the test split and passes the actual CPU device; it does not execute the author's machine-specific main entrypoint, which hardcodes CUDA. The model, particles, repetitions, chunk rule and backward sampling are unchanged. The exact NumPy particle mean is computed within each original chunk before trial concatenation to avoid a multi-gigabyte particle tensor. The source patch and equality controls are retained; repeat averaging is unchanged. Checkpoint directories/configurations are consistent with the released 36D arms; exact correspondence to the printed scores remains an empirical calibration question.

## Freeze predictions, then score separately

`scorer.py freeze` has no target argument. It validates complete prediction shapes, numeric rates and panel identities, then binds predictions, panel and protocol by SHA256. Candidate methods may use any permitted algorithm; they submit the same six scored arrays, optionally also the two train-forward arrays. Author calibration requires all eight native arrays and the 192×32 recipe.

```sh
"$SMC_STAGE/venv/bin/python" scorer.py freeze \
  --submission "$SMC_STAGE/causal.h5" \
  --manifest "$SMC_STAGE/inputs/mc_maze/test/panel.json" --protocol protocol.json \
  --output "$SMC_STAGE/causal-freeze.json" --arm causal \
  --method-id source-c808c76-causal --role author_calibration \
  --seed 20261117 --particles 192 --repeats 32
```

Only after this freeze may a separate evaluator stage the original public target release. Its exact size/hash and provenance are in `data_manifest.json`. Use `scorer.py score --help` for the operator-only target and scorer paths. The scorer requires the canonical release hash and the byte-identical original NLB evaluator; it rejects incomplete arrays, invalid rates, indirect HDF5 links, modified predictions and missing companion metrics. It reports all four scores and signed differences from the published source row. It does not automatically call a positive point difference a paper improvement.

The original targets became public in January 2026. This remains a **publicly exposed original test panel**, even with local access isolation. Keep target files outside candidate environments, never mount them into author training, and never publish authentic arrays, predictions or checkpoint payloads. The separate processes and path checks here are an auditable cooperative interface, not a hostile-code sandbox. Production candidate execution requires an operator-enforced filesystem/container boundary.

Future improvement admission requires completed source calibration, frozen candidate selection and exposure disclosure, and a prespecified uncertainty/companion non-regression decision. Neither a generated scorer fixture nor native chunk timing establishes model quality.

## Provenance and licenses

The [author source](https://github.com/mackelab/smc_rnns/tree/c808c76ad940491b0a14d2671e3884140aa61258) is pinned to the November 2024 paper-era commit and Apache-2.0. Current HEAD is incompatible with the old loader interface. Source and selected checkpoint hashes are listed in `source_manifest.json`; no payload is redistributed here.

[MC_Maze DANDI:000128, version 0.220113.0400](https://doi.org/10.48324/dandi.000128/0.220113.0400) is CC-BY-4.0. Attribution: Mark Churchland and Matthew Kaufman (2022), *MC_Maze: macaque primary motor and dorsal premotor cortex spiking activity during delayed reaching*. The paper cites the Dandiset without a revision; exact published-score calibration is still needed to reconcile that historical version ambiguity.

[NLB tools](https://github.com/neurallatents/nlb_tools/tree/42f8410b88e12db136910fa2f888b025ea0aa2ae) is MIT. The original PyPI 0.0.3 evaluator and tensor code are byte-identical to the target-release revision. A separate target-specific redistribution license was not identified; this package only records provenance for internal staging and does not redistribute the target file. Preserve DANDI attribution.
