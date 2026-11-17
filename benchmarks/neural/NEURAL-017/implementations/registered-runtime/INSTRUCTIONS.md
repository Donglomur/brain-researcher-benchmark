# Predict withheld neural activity

Use `public.npz` to produce strictly positive expected spikes per 5-ms bin for all 574 evaluation trials, 140 bins and 45 withheld units. Training provides 1,721 trials with both observed and withheld populations; evaluation provides only the 137 observed units, conditions, axes and fixed support mask. No evaluation-target labels are available to your method.

Choose any model or prediction procedure. Select all hyperparameters, supervised calibration and early stopping using whole training trials only. Do not split bins of one trial across training/validation groups. Declare any adaptation using evaluation observed-neuron inputs. No private scores, past prediction arrays, raw target-bearing files or online answer lookup may inform this attempt.

Submit one `predictions.npz`, at most 32 MiB, with exactly these fields:

| Field | Required contents |
|---|---|
| `expected_counts` | Real finite strictly positive array `(574,140,45)`, expected spikes per bin, not Hz |
| `trial_ids` | 574 unique Unicode IDs matching `eval_trial_ids` |
| `heldout_unit_ids` | 45 unique Unicode IDs matching the public withheld-unit axis |
| `bin_left_edges_ms` | Exact public 140-element time coordinate, in its original order |
| `prediction_units` | Unicode scalar `expected_spikes_per_bin` |
| `panel_fingerprint` | Exact public Unicode scalar fingerprint |

Trial and unit axes may be reordered if the IDs correctly describe them. No object arrays, extra arrays, linked files or executable payloads. No output clipping/renormalization is performed for you. The scorer accepts arbitrary predictions satisfying this contract; it does not require a reference model, reference coefficients or reference prediction equality.

The primary metric is pooled Poisson co-smoothing bits per spike. Its per-neuron evaluation-target mean is a private normalization only, never a legal predictor. The operator compares your score continuously to a frozen training-only condition/time predictor; negative or zero improvement is legitimate. There is no required gain threshold.

The fixed comparator uses condition/time training profiles shrunk by one pseudo-trial toward the global training rate `(train spike sum+0.5)/(train trial-bin cells+1)`, smoothed by an edge-normalized 60-bin Gaussian with sigma10 bins; unseen conditions fall back to the global rate. Every evaluation condition in this panel has training support. You may implement a condition-based model; the fixed comparator is never chosen after your score.

This is one exposed historical macaque session, not an unseen final benchmark. The whole 700-ms trial is available, so do not interpret the result as forecasting or causal neural information. Avoid population, cross-animal, SOTA or native-understanding claims. Keep the program and a method description for separate reproducibility/provenance review; this package's numeric scorer does not execute or authenticate that program.

Public data attribution: MC_Maze, Jenkins session 2009-09-25, [DANDI000128 version0.220113.0400](https://dandiarchive.org/dandiset/000128/0.220113.0400), CC BY4.0. Source-session IDs are not biological neuron matches across animals. See the public schema and licenses.
