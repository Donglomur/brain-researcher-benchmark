# NEURAL-017 opaque S03 handoff

This source component prepares the original five S03 conditions from the full
opaque public export: 1,721 training trials, 574 query trials, 140 five-ms bins,
137 observed units and 45 withheld units. It supplies source for a narrow preparation entry to
the existing operator. The ordinary physical S02/S03 compiler path is unchanged.

## Original metadata comes first

`complete-operator/nlb/opaque_s03.py::original_metadata` converts the retained
`selection_before_spikes.json` and `TRAIN_SPLIT.json` into the typed physical
support, D0 split and original-rule shuffle commitment required by the existing
operator. Both raw documents have fixed byte identities. Trial IDs, unit IDs and
condition labels follow the existing converter exactly. Original within-split
row order supplies chronology. The exact 340 retained validation identities
are copied, and the other 1,381 training identities remain the fit set. The old
split's RNG recipe is provenance; it is never replayed to select a new split.

The typed derivatives were not claimed to exist historically. This entry
requires an explicitly **prospective** shuffle selection: one separately
selected 32-byte protected seed descriptor and an exact NumPy version. It does
not read or generate the seed. Freeze that seed once before views or scores,
keep it private, and use the same commitment across compared arms. An already
frozen historical shuffle must not be silently relabeled as a new selection.

The accepted helper supplies `original_main` and `main` for selected captured-source callers. The current public registered-runtime bootstrap remains deliberately held because its historical manifest does not select the current numerical overlay. Consequently, the historical `nlb_entry.py opaque-s03-original` and `opaque-s03-prepare` invocation is not a runnable public preparation route. A later independently selected runtime closure is required. The prior private preparation receipts retain their exact original source identities and do not qualify this public composition.

Its three outputs are `original_support.json`, `original_split.json` and
`original_shuffle.json`. The final bounded stdout response supplies their exact
descriptors. A short write, flush failure or elapsed inner budget is a failure;
partial artifacts stay charged and are not silently reused as accepted output.

## Opaque support and the same donor relationship

The helper's `main` entry takes a separately selected descriptor document
covering the three originals, the accepted private binding and export receipt,
the opaque public NPZ descriptor, and the protected shuffle-seed descriptor. It
captures only the five JSON bodies; no NPZ, target, key or seed body is opened.
The accepted source fingerprint and the new opaque fingerprint remain distinct.
The binding's original axis order must exactly equal the physical support.

`prepare` transports original condition labels, chronology and D0 memberships
through the same opaque permutations. It verifies the original source and
export provenance and rejects seed/export-key hash equality. It writes four
private metadata products and `S03_COMPILATION.json` containing one concrete
`prepare/views` action, a resolved worker request and an exact 11-input roster.

At S03 execution, the existing `views.shuffle_map` computes the original donor
map from the physical support and frozen seed/version. The helper conjugates
it into opaque row order:

```text
opaque_donor = inverse_query_order[physical_donor[query_order]]
```

Re-running the random draw against opaque support would change the support
hash and donor relation, even with the same seed. That substitution is refused.
The ordinary project loop still produces all five conditions: intact,
within-condition shuffle, context only, training rate only and metadata neutral.
No support, metric, train/query role or scientific condition is removed.

## Authority and resource boundaries

The compiler output is one S03 preparation job, not an admitted complete
Campaign, S04 review, reference bank or set of qualification E-products. Existing
full-Campaign guards remain active. Downstream opaque-to-physical prediction
restoration and protected scoring require their own explicit integration; this
component does not claim they have run or been admitted. R0–R8 construction and
competence, participant runs, uncertainty and scientific readiness remain open.
SVG/text and tool/programme work are not evidence of native signal understanding.

Each metadata CLI has an inner 60-second software budget. The original stage
permits 2 MiB of reads; the opaque stage permits 4 MiB. Each permits 1 MiB of
writes and 4 KiB of response bytes. Source bootstrap capture and cache-directory
creation happen **before** that inner clock/read ledger. A future actual
operation must separately bound the entire owned process, source capture,
output/failure costs and cleanup; these CLIs do not provide OS isolation.

The source inspector authenticates the 74-row inventory plus its explicit current
numerical overlay, including this helper. The historical `nlb_entry.py` still
refuses current overlay bytes. The separate narrow S03 worker authenticates its
seven dependency files directly; it does not activate the full campaign entry.
Native source adoption is separate.
Owner-writable host export files must be captured and authenticated again on
each future use. In particular, the eventual array worker must decode the exact
authenticated public bytes and validate the new fingerprint, not rely solely
on the export receipt or a pathname.

## Maintained controls

```text
python -I -B benchmarks/neural/NEURAL-017/implementations/opaque-s03-handoff-v1/test_handoff.py
```

The 15 generated methods exercise full metadata support, D0 and chronology,
donor-pair equivalence, the difference from a naive opaque redraw, provenance
refusals, both five-view branches, exact compiler inputs and metadata-only CLI
failure behavior. Synthetic metadata hashes are explicitly substituted in raw
source controls. Archive decoding/serialization in the worker controls is
stubbed. These controls establish source behavior, not authentic data execution,
isolation, runtime provenance, model performance or benchmark readiness.
