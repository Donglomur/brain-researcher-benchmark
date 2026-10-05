# Validation status — local follow-up, 2026-10-01

## Scope

Retained as a **secondary atlas method/easy control**, not Oh et al. (2014)'s
original matrix or injection-unmixed connectivity result. The estimator,
missingness, support denominators, tie conventions and numerical tolerances are
public. Removed the invalid injection-inclusive density comparator, fraction
bands, nonconstant/mixed-indicator requirements and prose keyword gates.

## Original source and limitations

- 37 unmodified official API responses: 91,890,571 bytes, 498 non-transgenic-line
  experiments, 316 summary targets, 157 mapped primary source regions.
- Exact raw bytes, queries, retrieval times and locally measured SHA256 hashes
  are in `environment/source_manifest.json`. Snapshot
  `allen-connectivity-20261001` is a local capture, not an official immutable
  Allen release or independently published checksum anchor.
- 157,326 observed unionizes, 42 absent experiment-target pairs, no duplicate
  keys, invalid measured densities or observed zero-domain records.
  The 42 absent pairs occur in two experiments; they are not zero-imputed.
- Deepest-summary-ancestor mapping is explicit. All current mappings have one
  summary ancestor; the old overwrite rule was fragile, not proven wrong here.
  The target set contains nested MDRN/MDRNd/MDRNv structures.
- Original responses were reacquired during Docker build and every byte pin
  matched. Runtime analysis is network-disabled and uses only baked raw inputs.
- Allen research/noncommercial terms apply. No unrestricted license, commercial
  redistribution clearance or image-publication permission is inferred.

## Executed source-derived analysis

The new bank was generated from the complete original-source receipt, not the
old indicator key or mechanical fixtures.

- Source-target means weight available experiments equally, not sampled pixels.
  Every mean has explicit observed/expected experiment counts.
- 157/157 sources have an estimable mean for every target; underlying experiment
  coverage is nevertheless incomplete. 56 sources are self-maximal:
  `56 / 157 = 0.35668789808917195`.
- No source has a tied maximum or zero maximum on this snapshot. Both branches
  remain supported by mechanical tests; neither is forbidden by the verifier.
- The independent checker rereads/hashes original files, uses reverse-path
  mapping and keyed `math.fsum` aggregation without importing the oracle.
  All source receipts, support counts and full argmax sets agree. Maximum
  matrix difference is 1.1102230246251565e-16; maximum raw density/ratio
  discrepancy is 1.7208456881689926e-15.
- Raw source binding and physical numerator/denominator checks are both required.
  Categorical ties/self flags/zero maxima use unrounded source-derived means,
  independently of the tolerance allowed for serialized numeric outputs.
- Pinned native image, network disabled: **145 authoring tests passed**:
  60 parser/matrix mechanics, 19 oracle/independent numerical fixtures,
  30 staging tests, 5 genuine positive/contract cases and 31 genuine negatives.
  Coherent source scaling/shift/aliasing, missing-as-zero, dropped experiments,
  pixel weighting, wrong denominators, fabricated ties and summary forgeries
  are rejected. Order changes, descriptive extras and free prose are accepted.

## Clean-commit acceptance evidence

After this status file is committed, run the offline Harbor oracle and the
genuine regression matrix in its final image. The authoritative completion
receipt records the exact commit, task digest, image ID, result/config/lock,
oracle/verifier logs and output comparisons. Do not infer that acceptance merely
from the native tests above.

External receipt:
`/home/zijiaochen/projects/brain_researcher_benchmark/tracking/pr_repairs_2026-10-01/pr-149/receipt.json`.
Owned original-source/native/independent evidence:
`/home/zijiaochen/projects/brain-researcher-benchmark-runs/20261001/pr149-*`.

These checks establish source and computational consistency, not a regional
connectivity truth, paper replication, difficulty result or scientific release.
No Sol/frontier trial, push, PR comment or merge is included.
