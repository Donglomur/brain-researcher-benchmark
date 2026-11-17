# Source-derived definition and conditional endpoint

Primary source: [Safaai et al., Nature Neuroscience (2025)](https://www.nature.com/articles/s41593-025-02095-x),
Methods “Triplet statistics and global clustering coefficient” and “Parametric
two-pool model of network structure”, equations 16–17. Indexed primary results
were retained. Direct Nature fetch returned an identity-provider access error;
direct PMC fetch returned a browser check. Neither was bypassed. The publication
links official code at houman1359/Triplets and the Harvard NL1CAQ dataset. Their
existing registered provenance remains unchanged.

For n neurons there are M=n(n−1)/2 pair slots and T=n(n−1)(n−2)/6 unordered
triples. Every pair has an externally supplied signed significance class. Each
triple is classified by the sorted three edge labels. Counting all ten classes
preserves triples containing an independent edge; their sum is exactly T. A
class probability is its count/T. The four all-nonzero classes are available
without conditioning away zero-edge triples. The precise authentic preparation
must establish the same label graph and eligible population before using these
outputs for a published comparison.

For each sign, a closed triple has three edges of that sign; an open triple has
exactly two. The coefficient is C/(C+O), not 3C/(3C+O). If C+O=0, the coefficient
is undefined. Relative coefficients are differences between observed and
shuffled coefficients. This follows the explicit Methods definition; the Results
text also describes a normalization, which must not replace the defined
equation/difference with a ratio.

A supplied permutation maps each pair slot to exactly one existing pair label.
All IE, IL, and independent counts remain unchanged within each session graph.
It need not preserve node degrees: degree-preserving rewiring would be a
different null. The component rejects non-bijections and missing/extra records.
It reports each result and the mean of paired differences. If any coefficient
in a prescribed comparison is undefined, that mean is null with the number of
undefined comparisons; it is never a mean over surviving cases.

An additional analytic diagnostic follows directly from uniform permutation of
the fixed label multiset. If counts are m−,m0,m+ and a motif uses k−,k0,k+ edges,
its probability is C(m−,k−)C(m0,k0)C(m+,k+)/C(M,3). This finite-population formula
is independently derived, not claimed to be the authors' random draw sequence.
It is the expected motif probability for the declared null. Expected clustering
is deliberately not computed as a ratio of expected counts: E[C/(C+O)] is
generally different from E[C]/(E[C]+E[O]).

For the finite two-pool model, q=n/2, m1=m2=C(q,2), mb=q², p1=p+delta1,
p2=p+delta2. Equation 17 is equivalently pb=(p*C(n,2)−p1*m1−p2*m2)/mb.
The four possible node-pool compositions have counts C(q,3), C(q,3),
C(q,2)*q and C(q,2)*q. Their three independent edge probabilities are
(p1,p1,p1), (p2,p2,p2), (p1,pb,pb), (p2,pb,pb). Enumerating all eight outcomes
of these three Bernoulli edges and weighting by each node-composition count/T
gives all four signed motif probabilities exactly. The homogeneous Bernoulli
comparison is C(3,k)p^k(1−p)^(3−k). This does not equate Bernoulli edge sampling
to the empirical fixed-count permutation null. No continuous grid or optimum
is manufactured.

Primary pair-label methods describe the mean conditional interaction information
within the first two seconds after test-cue onset, 1,000 bootstrap replicates,
a sign-directed t test at 0.01, and Holm–Bonferroni correction over pairs. This
operator does not implement or authenticate that upstream procedure. Primary
triplet methods describe 100 bootstrap subsamples and within-session shuffles;
their exact historical sample identities and session-weighting implementation
remain missing. The existing real-data Figure 2–6 entrypoint, estimator/runtime
closure, all 70 file joins, and code-use permission remain unresolved. The
current pinned official tree was inspected only at its root, NPvC and simulation
directory levels plus the complete Ker_Copula subtree; it establishes available
estimator sources, not a complete absence proof for the entire repository.
