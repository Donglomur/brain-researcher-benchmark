# Shared numerical summary definition

Use every one of the 655 processed people, all six raw/separately standardized Student-t models and all five parameters per model. MODEL_CONTRACT.json and instructions.md preserve priors, column-wise ddof=0 moments, seeds and sampling prescription. They do not prove correct inference from a submitted summary.

For N retained draws pooled across equal-length chains: mean is sum(values)/N; population SD is sqrt(sum((value-mean)^2)/N). Sort the pooled values; set k=floor(0.94*N). Among indices i=0,...,N-k-1 choose the earliest minimizer of sorted[i+k]-sorted[i]. Report those two endpoints. This is the historical shortest-interval indexing convention, including its discrete endpoint choice.

For optional MCSE, partition each chain independently into consecutive non-overlapping 100-draw batches. With M complete batches and their means b_j, report sqrt(sum((b_j-mean(b))^2)/(M*(M-1))). The prescribed 4 x 2000 retained draws give 80 batches. Missing MCSE/diagnostics use the schema's nulls. None changes the fixed reference-SD primary denominator. Do not drop models, parameters or people based on diagnostics. Raw and zscore fits remain separately inferred; no affine posterior substitution.

Developer executable model/summary helpers are absent from both arms. This common source-informed specification intentionally retains their numerical definitions. Official code access in B is additional assistance, not a change to these targets.
