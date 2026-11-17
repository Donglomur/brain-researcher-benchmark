# Does the released cortical panel support earlier deep-layer activity?

**NEURAL-100 — `neural100_released_panel_draft_v1`.** Analyze authentic auditory cortical spikes to estimate the difference between L6 and L4 population-response onset. Report both source-labeled areas, all eight prespecified conditions, every recording, and animal-level uncertainty. Earlier L6 gives a negative difference. Null or undefined outcomes are valid; an undefined latency is not a zero latency.

This is a new investigation of the released cortical panel, not exact reconstruction of the paper, a causal-pathway intervention test, or the MGN encoding task NEURAL-099. The source is Garcia et al., [*Noncanonical short-latency auditory pathway directly activates deep cortical layers*](https://doi.org/10.1038/s41467-025-61020-9), and [DANDI 001419, version 0.250521.2343](https://dandiarchive.org/dandiset/001419/0.250521.2343). No thalamic, inferior-colliculus, or tracing files enter this task.

## Complete input and its limits

Use **all 47 released cortical click recordings from 41 source participants**. `ROSTER.json` fixes the IDs, grouping and areas. Preserve each source unit, its contact mapping, and each contact's released layer label, including contacts without units and mixed labels at equal depths. The released labels identify 39 A1 and eight A2 recordings. The paper's Figure 1 caption reports 31 A1 and 16 A2 mouse observations; no authoritative reconciliation was found. Do not relabel or select recordings to force agreement. Repeated sessions are not independent animals.

`input/PREPARED.json` binds 47 primitive NPZ files by SHA256. They contain absolute spike timestamps, ragged unit boundaries, unit/contact IDs, native click intervals, contact depths and layer codes. Each original blob is identified by the versioned DANDI inventory and publisher digest. Most selected arrays were retrieved by exact immutable-blob byte ranges; a complete original-file SHA256 was verified only for the engineering exemplar. Selected NPZ hashes are verified. No rate, latency, expected answer or model output is stored in the inputs.

Use the **native NWB trial `start_time`** as the click onset. Every selected interval is a 100-µs pulse, matching the described click duration. Spike times use the native NWB seconds clock. The separate 50-ms `StimulusEvent` timestamp accompanies trial-averaged CSD/LFP; do not add it to absolute spike timestamps. This is an explicit importer convention, not independently verified exporter/electrical-latency provenance. The task does not certify physical timing calibration. CSD and LFP signals are not inputs to this spike-only task and their average traces are not raw trial signals.

## Frozen analysis

For every unit and trial, count spikes in 100 half-open 1-ms bins with edges `trial_start + arange(-50,51)/1000`, using left-edge-inclusive, right-edge-exclusive intervals. Do not round timestamps or shift them to make a favorable onset. Unit-to-contact indices refer to electrode table rows, not electrode identifier values. Each complete [start−50,start+50) ms window must remain at nonnegative native time and must not overlap another click window; the source adapter rejects the full analysis if this cannot be established. This guard is not yet executed on the actual panel.

The 47 released schemas contain **no unit observation intervals**. A missing event therefore cannot certify observed neural silence, recording continuity or complete exposure. Counts and rates here are conditional on an explicit **complete-window observation assumption**. The time guards prevent impossible/overlapping windows but cannot detect undocumented acquisition gaps or per-unit dropout. Preserve this limitation in every scientific interpretation; zero event counts are not proof of observed silence.

Sort trials by their released chronological order. **Even zero-based indices are evaluation trials; odd indices are development trials.** Development trials may only choose contacts for the specified matching control. The primary uses every released unit assigned to the target layer, without a responsive-unit screen. This is a within-recording control split for an investigation, not a claim of prediction in unseen animals. The program and all rules must be frozen before examining outcomes. Participant grouping governs aggregation and uncertainty; never treat units, contacts or trials as animals.

For each layer, average evaluation counts over units and trials and divide by the bin duration to obtain spikes/second/source-unit. The baseline is all complete bins in **[−50,−5) ms**. Compute its mean and sample SD (`ddof=1`) over the population time bins. Search complete bins in **[1,50) ms**. Onset is the left edge of the first run strictly above baseline mean plus three SD that lasts at least 2 ms. No interpolation or smoothing is applied. No units, no evaluation trials, zero baseline SD, or no crossing produces an explicit undefined result. The 0–1 ms exclusion and baseline control do not prove that stimulus artifacts are absent.

These binning, split, baseline, search, persistence and undefined-result conventions are **new benchmark choices**, selected without fitting or inspecting latency results. The paper distinguishes layer-population thresholds from responsive-channel first-spike significance. Do not apply the paper's 3.7-SD responsive-channel selection to the primary population estimate. The released sorted-unit population also is not asserted to equal the paper's original channel-MUA processing.

## Eight conditions, all reported

1. `primary`: the population detector above.
2. `threshold_2_5`: use 2.5 baseline SD, otherwise identical.
3. `threshold_3_5`: use 3.5 baseline SD, otherwise identical.
4. `bins_2ms`: sum adjacent 1-ms counts before rate conversion; use only complete 2-ms baseline/search bins. Persistence remains **2 ms**, so one qualifying 2-ms bin suffices.
5. `boundary_erosion_one_depth`: exclude target-layer contacts within one unique-depth rank of any differently labeled contact, including outside-cortex contacts. Retain original labels; do not impose consensus at tied depths or claim reconstructed anatomical shifts.
6. `baseline_pseudo_onset`: use baseline [−50,−30) and search [−25,0) ms; report latency relative to −25 ms. This measures detector behavior before the click, not a calibrated permutation p-value.
7. `development_snr_bin_contact_matched`: on development trials only, compute each target contact's population SNR: mean rate in [1,20) minus baseline mean, divided by baseline sample SD. Exclude zero-SD or unit-free contacts from matching. Pair L4/L6 contacts in identical strata `(unit_count, floor(SNR/0.5))`, taking equal numbers from each stratum. Break selection order by SHA256 of `100043`, recording ID, contact-ID type and contact ID joined with NUL characters. This balances contact and unit counts and coarse SNR bins, **not exact SNR or biological properties**. No shared strata means unsupported/undefined, not a successful matched result. Never select using evaluation responses.
8. `first_spike_median_descriptive`: for each evaluation trial, find the first occupied population bin in [1,50) ms. Report the median conditional on a spike, and preserve no-spike support in the underlying analysis. This is descriptive, **not** the Chase–Young significance estimator or equivalent to population-threshold onset.

For every condition and recording report L4 onset, L6 onset and `L6−L4`. If either layer is undefined, the difference is undefined. No favorable condition may replace the primary.

## Participant aggregation and uncertainty

Average all repeats within each participant and area first, then average participants equally. An undefined repeat makes that participant's contrast undefined; any undefined participant makes the **full-area mean undefined**. Report a separately labeled observed-only mean without calling it a full-cohort result. Retain every missing/undefined disposition.

Use 1,000 shared whole-participant draws, `numpy.random.Generator(PCG64(100043))`, from the lexicographically sorted union of 41 participant IDs, with replacement and draw size 41. Use this exact same multiplicity schedule for both areas and all conditions. Average each selected participant effect using its multiplicity. A draw with no participant in an area, or an undefined selected participant effect, is undefined. Never redraw or silently condition on successful draws. Report the 2.5th/97.5th percentiles only when the full-area effect and every draw are defined; otherwise report a null interval and the defined-draw count. These are pointwise descriptive intervals, not simultaneous significance declarations.

## Submission and interpretation

Submit the exact JSON schema: all 47 records, eight conditions, both source areas, latency/null dispositions, cohort supports and bootstrap summary. Row order may vary; identity joins may not. Numbers must be finite; undefined values use JSON `null`. A separate `METHODS.md` may explain assumptions and alternative explanations, but its reasoning is not automatically graded by numerical agreement.

The private grader admits the full artifact before reading the packet and independently recomputing the fixed analysis. It reports absolute errors in milliseconds and exact support/null mismatches, without an arbitrary pass threshold. An error over available numeric fields is not a complete-reconstruction claim when support or dispositions differ. Undefined primary means yield no numeric primary error; they do not earn a synthetic zero error. Numeric reconstruction alone does not establish scientific reasoning, input use or biological validity.

Layer assignments are partly response-derived in the source study. The retained MATLAB layer script uses manual inputs and does not reconstruct all release assignments from these inputs. Its optional 12–64 Hz band also differs from the paper's stated 32–64 Hz range. The new boundary exclusion does not resolve these provenance issues. Successful arithmetic would not establish a noncanonical causal pathway, manuscript cohort parity, exact Figure 1 reproduction, SOTA, or empirical qualification of this package.
