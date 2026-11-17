# NEURAL-042: Load-dependent theta–gamma coupling

Investigate whether hippocampal phase–amplitude coupling differs with memory
load and behavioral accuracy after matching trial count, power, firing rate,
probe membership and trial-order strata. Return reproducible numerical artifacts;
a null or unavailable estimate is acceptable. This is a prospective investigation
on a public development cohort, not a hidden discovery or a causal test.

The original source is Daume et al., Nature (2024), DOI
10.1038/s41586-024-07309-z, DANDI000673 snapshot0.240118.2135 and SBCAT code
a25e8cc3f61630a428f190381745257d4506f148. It shares its source with NEURAL-041
and related working-memory tasks. Those are different endpoints, not independent
cohorts. The original paper also tests single-neuron, interregional and population
mechanisms; completing this task would not reproduce all of those claims.

## Inputs and permitted work

An operator must provision the complete44-session/36-patient source, verify LFP
preprocessing and clinical per-wire/per-trial exclusions, and produce packet.json
plus its exact channels/*.npz allowlist. No actual neural packet is in this source
package. Inspect INPUT_SCHEMA.json. Each selected hippocampal wire must have at
least one co-located sorted unit. Include all qualifying wires, regardless of PAC
strength or effect direction. Coverage must identify patients without usable
data; they are never replaced with zero effects.

Each trial contains1000 original400Hz LFP samples in volts from event-relative
[0,2.5)s maintenance, plus mean sorted-unit firing rate over exactly that interval,
load1/3, accuracy0/1, probe-membership0/1, opaque trial IDs and original trial row
0..139. Accuracy is an explicitly permitted grouping variable for this
retrospective investigation, not a hidden prediction target. No probe or response
signal samples, pictures, demographics, whole NWBs, operator exclusion records or
private numerical reference are accessible to the candidate. Original order is
permitted only as the declared drift covariate.

Freeze the candidate program and method before opening the packet. No private
grader feedback or outcome-dependent channel/frequency/interval selection.
The public pac.py tool is permitted in the tools-enabled condition. A separate
no-tools condition would require a separately specified input and execution
contract; this task is not evidence of native LLM signal understanding. These are
all-public development data, so prior exposure cannot be ruled out.

## Frozen numerical protocol

Use all eligible patients, equal wires within session, equal supported sessions
within patient, then equal patients. Do not treat wires/trials as independent
biological replicates. For each patient produce both designs and both contrasts:

* load3 minus load1, using correct trials;
* correct minus incorrect, estimated separately within each load then averaged
  equally across loads. Both load-specific comparisons must be supported.

Within each wire, require at least10 retained pairs in each comparison. Exact
strata are original trial-order quartile (`row0//35`) and probe membership. The
count-only comparator selects equal counts in each stratum by ascending opaque
trial ID. The nuisance-matched design matches log theta power, log gamma power and
log(1+mean firing rate). Standardize each covariate using the pooled two comparison
groups within the stratum (population SD); every paired absolute standardized
difference must be at most0.5. Constant covariates require exact equality. Use
maximum feasible pair count then minimum total squared distance, without
replacement. Stable ID ordering plus pinned SciPy fixes assignment ties. No
caliper loosening, outcome-dependent trimming or minimum-support substitution.
The reported power/rate contrasts expose residual imbalance: matching is a bounded
balance rule, not exact equality or proof of absence of confounding.

Tort modulation index uses18 equal phase bins and pooled trial/sample mean
Hilbert amplitude in each bin, normalized to probabilities. Compute the mean of
30 frequency pairs: low centers4 and6Hz, passband center±1Hz; high centers70:5:140Hz,
passband high center±low center. Use the Hamming windowed-sinc transition heuristic
implemented in pac.kernel. No empty phase bins or zero total amplitude may be
imputed. The exact implementation is public pac.py.

Filter each1000-sample trial independently using its repeated endpoint values
through a kernel half-length and delay-compensated convolution. Hilbert transform
the1000 filtered samples. **This prospective boundary rule differs from the author
demo**, which filters real[-0.5,3]s epochs and trims0.5s. Because probes can begin
before+3s, copying that padding would admit post-maintenance activity. Our rule
excludes it but can still have finite-window edge bias; it has not been validated
against MATLAB or biological data. Early/late halves are mandatory sensitivity
diagnostics, not independent trials.

Use200 surrogates per frequency pair/condition. Seed NumPy with the first8 bytes
of SHA256('neural042-v1:'+identity), interpreted big-endian. Identity strings are
exactly constructed by pac.wire_effects. For trial surrogates, cycle amplitude
trial order by a uniform nonzero offset. This preserves the event-locked envelope
and permits no same-trial pairing; it differs from the author's unrestricted
randperm. For time shifts, circularly shift each amplitude trial independently by
a uniform integer200..800 samples inclusive. This preserves every trial's amplitude
sequence DFT magnitudes while disrupting its phase alignment. It introduces a
wrap seam and is not a test of every possible nonstationarity.

`corrected_mi = observed_mi - mean_trial_surrogate_mi`; it may be negative.
It is **not** the paper's surrogate-SD z-score. Report observed MI, both null means,
MI for each temporal half, theta/gamma power, firing rate, harmonic phase-locking
and waveform asymmetry contrasts. Harmonic phase-locking is the mean magnitude of
exp(i*(round(high/low)*low_phase-high_phase)), averaged across30 pairs. Waveform
asymmetry is the signed difference of positive/negative raw slope energies divided
by their sum (zero if both vanish). These diagnostics are motivated by harmonic
and waveform confounds; neither proves independent theta/gamma generators. They
are not the author's bycycle/nesting implementation. A strong mechanistic claim
requires additional independent validation; the grade does not reward one.

For group corrected-MI summaries require at least2 patients. Use10000 patient
bootstrap resamples with replacement, linear2.5/97.5percentiles, then10000 independent
patient sign flips from the same deterministic stream. Two-sided p=(1+count)/(10001),
seed identity design+':'+contrast. These intervals/p-values are descriptive for
this exposed clinical cohort; four reported analyses are not four independent
discoveries and unadjusted p-values are not familywise claims.

## Output and grading

Write UTF-8 report.json, at most2000000bytes, with exactly the schema fields and
the144 ordered patient rows plus4 group rows. The semantic validator is
private/score.py; public submission.schema.json describes syntax. Booleans are
not numbers, duplicate keys and NaN/Infinity are invalid. Do not omit unavailable
patients: use null metrics and zero support exactly when the qualified reference
has no supported estimate. No code is executed by the artifact grader.

Primary score is mean absolute numerical error in nuisance-matched
surrogate-corrected MI: equal patients within each endpoint, then equal endpoints.
Lower is better. Both endpoints must have reference support; otherwise primary
score is null, not zero. Separate per-unit errors cover other metrics and group
statistics. `all_numeric_claims_match` additionally requires all patient metric
values (rtol1e-6/atol1e-10) and group statistics (atol1e-10) to agree. A zero primary
error alone does not certify the full report. Fixed zero-coupling and count-only
baselines use the identical reference-supported patients. No effect direction,
positive story, causal conclusion, narrative eloquence or SOTA claim earns points.

No baseline/reference PAC has been executed. Runtime/CPU/memory limits remain an
explicit provisioning gate; there is no qualified runner or cost claim. The
buildable dependency recipe and generated tests establish source/interface
behavior only. This artifact is partial until all source, mask, comparator,
reference and independent runtime qualifications are available.
