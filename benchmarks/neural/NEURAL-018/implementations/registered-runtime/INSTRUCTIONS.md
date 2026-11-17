# Forecast the next 200 ms of population activity

At the end of the observed **[−250,+450)ms** window, predict expected spike counts in **[+450,+650)ms**, relative to movement onset. Submit all 40 future 5 ms bins for all 182 neurons, held-in 137 followed by held-out 45, on all 574 development trials.

Permitted inputs are the exact three public files in `assets.json`: the existing observed-spike packet, `training_future.npz`, and `public_manifest.json`. The observation packet supplies 1,721 training trials with observed and held-out neurons, and 574 assessment trials with only 137 observed neurons. The added file supplies future counts for the 1,721 training trials only. Trial condition IDs (`trial_type`,`trial_version`) are explicitly permitted for every method. This is a **condition-assisted local task**; the horizon and joint score follow official NLB, but its default tensor input interface is not claimed identical.

Use only training trials for supervised fitting, calibration, hyperparameter choice and stopping. Keep whole trials together in any inner validation. Declare any adaptation that uses assessment observations. The complete observed window is available; all query bins at/after+450ms are forbidden. Raw NWB, development future targets, reference predictions and private scores must not be present in the candidate environment. The operator packet is not a candidate workspace.

Write one `predictions.npz`, at most 34 MiB, containing exactly:

| Field | Contract |
|---|---|
| `expected_counts` | Float32/64, finite and strictly positive, `(574,40,182)`; expected spikes per 5 ms bin, not Hz |
| `trial_ids` | Unique Unicode IDs matching all public `eval_trial_ids` |
| `forecast_unit_ids` | Unique Unicode IDs matching the public forecast population |
| `bin_left_edges_ms` | Exact 40 values: 450,455,…,645 in that order |
| `prediction_units` | Unicode scalar `expected_spikes_per_bin` |
| `panel_fingerprint` | Exact public forecast fingerprint |

Trial and unit axes may be reordered if their IDs describe the arrays correctly. No extra fields, objects, pickle, linked files or archive members. The scorer performs no output clipping or renormalization. Any valid prediction procedure is allowed; no reference-family or positive-gain requirement applies.

The primary score is **joint forward bits per spike**, pooled across all 182 units, 574 trials and 40 future bins. The private evaluation per-neuron mean is only the metric's null normalization, never a legal prediction input. Output includes signed comparisons with all three frozen references: global training rate, condition/time profile, and past-activity plus condition. The condition comparator was fixed before future-label decoding. Beating one weak reference alone is not scientific success; every comparison and the raw score must be retained. No pass floor or oracle reward is defined.

This is one historically public Jenkins macaque session, not 574 biological replicates or an untouched final set. Source-preprocessed past spikes are supplied; online spike sorting and interventional causality are not tested. Source metadata confirmed nonoverlap of every observed+future window and full future recording support without exclusions. Program replay, training provenance, strong-model difficulty and population generalization remain separate qualification requirements.

Data attribution: MC_Maze, DANDI000128 version0.220113.0400, Jenkins2009-09-25, CC BY4.0. Cached official `nlb_tools` source at42f8410b88e12db136910fa2f888b025ea0aa2ae is MIT licensed; see `NLB_LICENSE`.
