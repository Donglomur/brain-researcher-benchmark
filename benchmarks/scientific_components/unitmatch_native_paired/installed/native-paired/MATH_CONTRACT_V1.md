# Frozen UnitMatch functional mathematics v1

This is the mathematical contract for an independent reference implementation. Its author must receive this document before any producer, existing metric implementation, other bank or producer-control answers. The independent author may use Python's standard library and independently designed analytic controls. Record all shared dependencies and later shared repairs. Do not inspect the existing UnitMatch implementation. This contract fixes a five-mouse functional proxy, not neuron identity truth.

## Inputs, order and half convention

Production covers five mice in order Mouse1..Mouse5, with total good-unit dimensions534,109,96,59,466 and day counts275/259,61/48,54/42,32/27,268/198. No unit, directed matrix entry or animal is dropped. The mathematical kernels must also accept explicitly invented small operands for engineering checks, without treating those as a production cohort.

Each unit has one source session and cluster identity. Its selected spike-time vector is finite seconds in the original recorded order. Decreasing values are an error; equal adjacent values are allowed. Cluster membership comes from the original recorded identity, never renumbering/sorting/reselecting. Shared raw spike vectors, roster and declared binary64 edge vector are inputs, not independent provenance proof.

For N spikes:
- N<2 produces undefined first and second fingerprints, not41 numerical zeros.
- Otherwise first half is zero-based positions0 through floor(N/2)-1.
- Second half starts at zero-based positionceil(N/2)-1 and continues to N-1.
- Thus even N shares the boundary spike, odd N does not. The independent implementation must preserve this exact convention.
Take successive differences within each half only; do not insert a gap interval between halves.

There are42 strictly increasing finite edges and41 histogram bins. The recorded benchmark edge recipe is [0, 5 * 10**linspace(-4,0,41)] in seconds, evaluated by the currently bound producer numerical profile. The independent bank receives the exact42 admitted float values and labels them shared edge operands; it must not call the producer histogram to obtain counts. Every bin is [left,right), except the last includes its final right edge. An interval exactly at an internal edge goes into the bin starting at that edge. Values outside the outer edges are excluded and counted explicitly; in-range count conservation is required. Do not silently replace this with a MATLAB-colon or independently rounded edge recipe. Exact historical edge/native tolerances remain external qualifications.

## Directed functional correlations

For each first-half unit histogram a and second-half unit histogram b, each of length41, subtract its own arithmetic mean. If either fingerprint is undefined, or either centered sum of squares is zero, correlation is undefined. Otherwise compute the centered dot product divided by the product of Euclidean centered norms, clamping finite rounding overflow into [-1,1]. Preserve the complete ordered N-by-N first-versus-second matrix, including diagonal and both directions; C[i,j] need not equal C[j,i]. Undefined entries are None in portable products, never zero.

Independent arithmetic may use math.fsum/ordinary Python loops and square roots. It must not use NumPy histogram/corrcoef, scipy rankdata, or producer answers. The producer and bank deliberately share the exact raw operands/edge vector; source custody and historical binary equivalence remain unproved. Comparison of finite correlation/AUC results uses an explicit prospective engineering tolerance abs(a-b)<=1e-12+1e-10*max(abs(a),abs(b)), with exact identity/count/definedness agreement. This is not a scientific reproduction tolerance.

## Probability decoder

Each candidate/reference matrix contains every ordered pair including diagonals, as finite non-boolean numbers in [0,1]. For each canonical day1 unit i and day2 unit j, compute (P[i,j]+P[j,i])/2. Sort pairs by descending mean, then ascending original canonical i, then j. Accept only a mean strictly greater than0.5 and only if neither unit has previously been accepted. This is deterministic greedy one-to-one two-day matching, not multi-session UID inference. The independent implementation may derive this directly from the contract.

## AUC and complete per-mouse score

AUC is the probability that a finite positive exceeds a finite negative, with half credit for equality. Filter nonfinite/undefined values separately in each class. If either finite class is empty, AUC is undefined. Counts of both retained classes and excluded support remain explicit. An independent efficient implementation may sort finite negatives and use binary searches; a tiny exhaustive pairwise comparison is a meaningful independent oracle. No interpolation or threshold optimization is performed.

For every ordered C[i,j]:
- Cross-day: positive iff its canonical day1/day2 pair is in the decoded match set; all other cross-day directions are negative.
- Same-day: i==j is within-day positive; all other same-day directions are negative.
Report matches, available_min_day_units, stable_unit_yield=matches/min(day-unit-counts), isi_auc, within_session_isi_auc, finite_cross_match_directions, finite_cross_nonmatch_directions, finite_within_same, finite_within_other and undefined_cross_directions. Also expose undefined-within support if needed without changing the primary metric.

isi_auc_eligible is true exactly when matches>=20, finite matched directions>=40, and cross-day AUC is defined. These are existing operational guards, not significance tests or true-identity labels. A small invented kernel control may be ineligible and still be a valid arithmetic test.

## Pairing and interpretation

Both full A/B methods and all five source-owned native reference outputs are closed before private functional decoding or score feedback. Each arm's improvement requires all five arm/reference mice eligible, strictly higher equal-five-mouse mean AUC, and nondecreasing match count plus finite matched-direction count in every mouse. A missing or undefined mouse blocks that comparison; no reduced-cohort mean. Signed per-mouse effects and B-minus-A on common complete support remain visible. Biological unit is mouse, n=5; report descriptive dispersion/SEM only, no neuron-pooled inference or invented significance threshold.

## Reference API and controls

Author a standalone stdlib module reference_bank.py:
- histograms(spikes, edges): exact two histogram products plus explicit split/outside/count information; undefined fingerprints represented as None.
- correlations(first, second): full directed matrix with None for undefined entries.
- auc(positive, negative): return (value_or_None, finite_positive_count, finite_negative_count).
- decode(probabilities, units): set of canonical (day1_index,day2_index) pairs.
- score(probabilities, units, correlations): report the per-mouse fields above.
Validate input shape/finite/order domains before substantive allocations. API input units is a list of dictionaries with session1/2; cluster identity is retained but not remapped.

Provide meaningful independent analytic controls for even/odd/zero/one-spike cases, all histogram boundaries and final edge, count conservation, constant/undefined histograms, directed correlations, exact AUC ties, greedy tie order and support failures. Do not reproduce the producer implementation or consume producer outputs as expected answers. Record any arithmetic ambiguity rather than changing the metric. Freeze first implementation before sharing it; later corrections must retain that original and disclose what was learned.

Source phase author allocation24MiB reads/6MiB writes. Initial invented-control allocation is at most2MiB cumulative serialized transfers,512KiB retained and8MiB estimated live working payload inside the whole32/8/64 envelope; precharge complete fixture/source/result transfers before execution, retain failed attempts and stop before exceeding. No authentic data/header, MATLAB/native/model/scientific execution, network, Git or shared install. Work only your new owned reference-bank subdirectory.
