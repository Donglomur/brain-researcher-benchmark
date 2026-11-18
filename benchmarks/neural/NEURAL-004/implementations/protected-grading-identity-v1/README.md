# Protected prediction-slot identity

The full-study controller already constructs the intended person and policy maps.
This correction also enforces their assignment at the protected grader boundary:
208 actor contexts and 52 reference contexts must each occupy their original
source-owned slot exactly once. It is a protected caller contract, not proof that
a participant could bypass the normal controller or its custody checks.

`ReleaseBarrier` now retains defensive immutable copies of the controller's
`(mode, view, person)` and `(reference family, person)` maps. The grader checks each
record against that original assignment before handling its disposition.
Legitimate failed and blocked records still need neither a forecast nor an answer
map. Endpoint, fractional-contrast units, equal-person MSE, reconstruction,
reference comparisons and reasoning scores are unchanged.

The exact source chain includes effective-parent grading/controller,
`EFFECTIVE_PARENT_MANIFEST.json`, `BINDINGS.json`, the entry's binding pin,
`SOURCE_MANIFEST.json`, `QUALIFICATION_SOURCE_FREEZE.json` and the proposed
execution descriptors. The old numerical-and-grading-source-unchanged declaration
is false because grading guards changed. Original source records and downstream
paired-contrast historical evidence remain historical. Operation selection and
runtime/scientific qualification remain false.

From the repository root, run the maintained standard-library controls:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-004/implementations/protected-grading-identity-v1/test_grading_identity.py
```

The ten methods use the real captured package, constructor, register/close/open
path and protected grader. The complete generated fixture has 26 people,
208 actor slots, 52 reference slots and 51 generated trials per panel. A clearly
uncredentialed structural authority double avoids claiming real custody or
authentication. Retained original grading is a regression comparison, not a
scientific comparator. The controls check:

- Exact predecessor output equality for valid and incomplete results, including
  absent answer maps for three failed/blocked contexts.
- Previously accepted policy, actor/reference, reference-family and context-replay
  substitutions, plus a failed/blocked person swap, are now refused.
- A sealed person swap was already refused by the predecessor and stays refused.
- Original slot domains, disjoint context identities, detached source maps,
  equal-person units and the actual source-loader/controller import.

Public CI needs no fixture downloads, third-party packages, credentials or output
directory. Optional `NEURAL004_IDENTITY_EVIDENCE` retains a bounded generated
`results.json` in an explicitly supplied existing empty directory. The private
construction-only `NEURAL004_IDENTITY_BASE_REPO` fallback reads named missing
source blobs from immutable commit `8e9eeddf8327094d631a2f015d9334b9078e98f5`;
normal repository CI uses installed files and does not need that Git object.

These controls execute no whole programme, authentic neural input, model, fit or
provider call. They establish neither native neural understanding nor model
performance. Authentic input admission, independent reference competence,
runtime/custody qualification and human-review reliability are separate retained
prerequisites.
