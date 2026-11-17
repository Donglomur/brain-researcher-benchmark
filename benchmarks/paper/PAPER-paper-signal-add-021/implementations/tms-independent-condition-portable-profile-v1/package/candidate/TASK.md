# TMS Figure 2B: method-specified numerical reconstruction

Reconstruct the four channel maps defined below from the supplied stored neural responses. Return every channel, including explicit undefined values. This task measures implementation of a predeclared method. It does not ask you to infer a method from the paper or establish a new scientific result.

Both conditions receive these same instructions and the same input bytes. Condition B additionally receives the selected original implementation files. Condition A must use only its supplied materials. Network access is disabled. Do not retrieve another repository, install packages, use an external service, or read a hidden answer.

The supplied input is a selected-window projection of stored arrays. It is not a map, interval certificate, target-category mask, model prediction, or reference cache. Positions 0–14 identify stored array positions; physical person matching across conditions is not asserted or needed for these separate condition means.

For each condition, channel, frequency and time:
1. Interpret each finite binary64 input value as its exact real value. Omit NaN entries in that 15-position group; an empty group is undefined.
2. Compute the arithmetic mean of the remaining dB values separately for `pin` and `pout`.
3. Compute `(10^(mean_pout/10) - 10^(mean_pin/10)) / (10^(mean_pin/10) + 10^(mean_pout/10))`. A contrast is undefined if either group is empty.
4. Within each frequency, average the defined contrasts over the 28 selected times. Then average the defined frequency means equally. Do not flatten all time/frequency cells into one weighted mean.
5. An empty final map slot is undefined. Preserve it in the output rather than dropping it.

The four output maps, in order, are NT.delay1, NT.delay2, T.delay1, T.delay2; each contains all 62 channels in the supplied order. The nominal bands are 8–12 Hz and 0.5–1.5 / 3–4 seconds. The original helper selects nearest grid endpoints: source frequency indices 8–14 inclusive, source time indices 53–80 and 119–146 inclusive (zero based). These are the exact selected bins, including endpoint bins outside the nominal numeric ranges. Use the supplied bins; do not apply another band filter.

The input profile admits NaNs and finite values with absolute value at most 1000 dB. Infinity and out-of-domain source values invalidate a complete case upstream; they are not omitted or clipped. Candidate output infinities are invalid. Finite outputs outside [-1,1] are scored as submitted.

Write exactly 2232 bytes to standard output: 248 little-endian binary64 values in map-major/channel-minor order, then 248 one-byte flags (0 for finite, 1 for NaN). A flag must agree with its value. Use stderr for bounded diagnostics; stdout contains only the binary submission. The runtime executes the sealed Python program with isolated mode in an offline container. No candidate code executes in the owner/scorer process.

The owner reports rigorous continuous bounds on absolute residual, pooled and per-map MAE, and maximum absolute error. The numerical oracle is an exact-input real-expression profile. There is no fitted pass threshold, MATLAB floating-evaluation equivalence, inferential claim, or SOTA claim. A category mismatch invalidates a complete submission; no favorable subset is scored. Feedback is withheld until candidate closure. An ingestion receipt is not a score or proof of category agreement.

