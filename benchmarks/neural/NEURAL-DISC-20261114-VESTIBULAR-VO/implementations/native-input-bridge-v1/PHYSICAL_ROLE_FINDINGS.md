The available documents establish the intended cohort and stimulus families, but do not establish any physical field binding in `VO_dataset.mat`. The companion `PHYSICAL_ROLE_EVIDENCE.json` records twelve unresolved roles, exact source identities and the evidence needed to resolve each. No authentic array was read, hashed, decoded or counted for this review.

The paper reports 49 neurons and 35 simultaneous pairs in three animals: D has 11 neurons and 6 pairs, B has 34 and 26, and O has 4 and 3. These counts are reconciliation targets, not an assertion that the cached MAT has already passed a census. The deposit metadata separately names Belle, DJ and Orion. Initials suggest a possible alias relationship, but do not authenticate the mapping to individual recordings. Source: the [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11086886/) cached lines L151–L162 and the [Borealis deposit](https://doi.org/10.5683/SP3/FXFZ2J), version 2.0, description field. The exact cached paper excerpt ends at L162; this is not a review of the full methods section.

The author figure script `Fig3C4SA_G.m` (file 718879, lines 1–4) lists sinusoidal frequencies 0.5, 1, 2, 3, 4, 5, 8 and 17 Hz. Naturalistic stimulation is separately documented. All additional authentic conditions must also be inventoried. Figure S8's summary convention, naturalistic tag −1 and positive sinusoidal frequencies, must not be assumed to be the main file's schema.

The useful evidence and remaining bindings are:

| Role | Documentary evidence | Required original binding |
| --- | --- | --- |
| Animal | Paper D/B/O counts; deposit Belle/DJ/Orion names | Original animal membership and explicit aliases |
| Stable neuron | 49 well-isolated biological neurons | Stable identities across repeated appearances and overlapping pairs |
| Session or recording group | Simultaneous multi-site acquisition | Session IDs, acquisition bounds and shared-presentation membership |
| Genuine pair | 35 simultaneous pairs | Two stable members, shared original acquisition and clock for every pair |
| Condition | Naturalistic and eight sinusoidal frequencies | Original condition codes, amplitudes and any additional conditions |
| Repeat, presentation and waveform | Repeated stimuli and trial variability | Complete boundaries, presentation aliases and waveform identities across groups |
| Spikes | Measured spike trains in the paper | Actual representation, multiplicity, units, clock, orientation and validity |
| Measured velocity | Head-velocity traces; summary thresholds in degrees per second | Measured target field, axis, sign and calibration; distinguish measurement from command |
| Alignment | Recording during stimulation | Common origin, synchronization, offset and any resampling provenance |
| Grid and duration | No measured grid in inspected texts | Complete native coordinates, sample support, duration and masks |
| Eligibility | Figure-specific 41-neuron, repeat, outlier and stationarity rules | Original membership and failure flags; separate decoding eligibility |
| Original paper endpoints | Correlation figures and simulated coding analyses | Actual measured operands and source analysis membership, separately from the decoding task |

Five deposited scripts are simulation analysis helpers. For example, `ii_cfInfo.m` (718878, lines 30–51 and 69–70) reconstructs generated binary spikes and supplies a 1-ms step; `iv_corrStruct.m` (718891, lines 20–39) removes the first simulated trial and uses an 80-ms correlation window. Neither choice is a measured-recording clock, duration or exclusion rule. Their array names cannot become alleged main-file fields. The other fourteen author texts load or describe precomputed figure summaries; none supplies a measured `VO_dataset.mat` loader or the missing biological joins. All nineteen identities are pinned in the JSON. The accepted deposit has no established author Git revision.

Several analysis distinctions must survive construction. Figure 2D's 41 neurons (718857, line 1) cannot replace the full 49-neuron cohort. Figure-summary pairwise combinations cannot replace the 35 genuinely simultaneous pairs. Within-neuron heterogeneity requires at least two trials, and the artificial figures apply an unspecified per-stimulus outlier analysis (718873, lines 1–2; 718888, line 1). Correlation summaries mention weak-stationarity screening without giving exact retained indices (718882, lines 1–2). The Figure 5 README describes noise correlations but then calls the screened quantity signal correlations (718883, lines 1–2); preserve this discrepancy rather than inventing a filter.

The next admitted operation should inventory every original top-level and nested member while preserving MATLAB structure, orientation and identity. That census may reveal candidate paths and embedded metadata. A subsequent evidence-backed join must establish the roles above; structural plausibility alone does not prove biological semantics. If a required clock or measurement description is absent, retain that specific unresolved role. Keep the complete source scope, and do not replace it with a smaller working panel.

This is a documentary construction artifact. It does not close physical-role admission, measured-input preparation, competent references, participant isolation or benchmark readiness. The existing held-repeat measured-velocity MSE remains the decoding endpoint; paper correlation, coding-fraction and information results stay separate. The deposit records CC BY-NC 4.0; author-code redistribution remains unresolved. This package references source identities and paraphrased findings without copying deposited code or scientific payloads.
