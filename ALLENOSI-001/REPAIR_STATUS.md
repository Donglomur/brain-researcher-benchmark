# Local source-bound repair

This is a one-session descriptive method control on original Allen NWB data,
not the paper's cohort finding or AllenSDK vector-strength gOSI. The custom
two-point estimator, complete all-VISp denominator, optional QC sensitivity,
zero-response policy, exact ties and numeric tolerances are public.

The original DANDI 000021/0.251116.2246 asset is SHA256-pinned and baked offline.
All 133 VISp clusters and 598 nonblank original presentations were processed.
The primary result is 52/133 = 0.39097744360902253; two zero-response units stay
in that denominator. The optional QC-plus-responsiveness result is separately
9/37 = 0.24324324324324326. These same-trial descriptors do not establish neuron
prevalence, an unbiased selectivity estimate, or a causal effect of noise.

Independent histogram-based counting of all 79,534 stimulus and 79,534 baseline
windows agrees exactly with the oracle's source counts. Separately aggregated
means, preferred conditions, OSIs and optional QC decisions agree; maximum
mean-rate difference is 1.43e-14 Hz and maximum OSI difference 2.23e-16. The
checker shares h5py/NumPy and the upstream acquisition/spike sorting, not oracle
or verifier code; this is not independent spike sorting or biological validation.

The genuinely rebuilt reference is bound to original identities and complete
integer counts. Native regression matrix: 314 passed, including primary-only
and independently reconstructed count-output acceptance and coherent false
answers rejected. No prose keywords, directional story or hidden score band.

Final clean-commit Harbor execution and its image regression receipt are tracked
outside the task in tracking/pr_repairs_2026-10-01/pr-157. The native evidence
above is not a claim that those later checks have already run. No Sol/model
difficulty evidence, push, merge or public redistribution is claimed. The archive
CC-BY notice and linked Allen research/noncommercial terms are both preserved;
public/commercial redistribution clearance remains unresolved.
