# SenseFOG: complete recording-grid lag controls

This is the accepted V2 target-free control mapper with V3 source-binding identity
for `clinical-sensefog-stn-state`. It emits every original two-second case and
all 20 common-channel lag transforms for all 12 participants. It does not load
signals, labels or models, compute a primary loss, or qualify a benchmark.
`sensefog_pairing.py` and `test_pairing.py` retain their exact accepted bytes.

The API is `build_maps(document, max_cases=...)`. Python 3.11+ Unix standard
library is sufficient. [CONTROL_INTERFACE.json](CONTROL_INTERFACE.json) contains
the complete strict input declaration and unchanged scientific rules. Private
source-contract paths and historical integration receipts are excluded from that
public metadata projection; the code and formulas are unchanged.

An operator authenticates all 12 people, complete recording extents/origins/grids,
continuous acquisition segments, every channel/mask, and training-only lookback
H and dependence L_train before calling the mapper. Every fold uses exactly
the other 11 people. For each native integer-Hz grid, G=max(30*rate,2*H,L_train);
the output always includes +G,-G through +10G,-10G without wrap. Missing H or
L_train produces unsupported rows. One lag applies to every channel and its full
causal support; all-channel mask sequences must match within the same segment.

Case enumeration belongs to each original recording, independently of segments.
Gap/boundary-crossing cases and entirely unobserved recordings stay in the
census as unsupported rows. Grid origins never move to a segment boundary.
Unrepresentable real sampling changes need a source mapping, not omission or
convenient resampling. The generated 1-Hz fixtures are not the clinical rate.

From this directory, in an operator-owned mode-0700 workspace:

```sh
umask 077
python3 -I -S -B sensefog_pairing.py \
  --input COMPLETE_TARGET_FREE.json --expected-input-sha256 FROZEN_SHA256 \
  --output FRESH_MAPS.json --max-input-bytes B --max-output-bytes O --max-cases N
```

Use trusted ordinary input files and independently selected hashes/caps. This
CLI is not a hostile-file/process sandbox: no no-follow/nonblocking claim is
made for this mapper. It materializes input and maps; byte/case caps reject
the entire over-limit operation rather than truncating a population, but do
not enforce OS memory/time ceilings. Outputs are exclusive, caller-umask governed,
and may be partial after failure. There is no automatic retry or atomic publication.

Freeze and reuse the same maps across arms. A later protected loss consumer must
join identical supported cases within person, average within person then equally
across supported people, and disclose people without support. Primary natural
coverage remains separate. Maps are descriptive dependence controls, not
exchangeable permutations, p-values or causal evidence. The exact class dictionary,
clinical clocks, authentic grid/mask/training provenance, physical packets,
primary metric, paired-loss consumer, competent references and uncertainty remain
unqualified. `primary_score` is null and scientific qualification false.

Run only the relocated generated interface checks:

```sh
python3 -I -S -B test_delivery.py
```

The checks exercise the real CLI on an invented complete 12-person boundary
census, retained unsupported cases, cap refusal and source identities. They do
not replay the numerical test campaign. The exact accepted tests remain available;
their direct script mode expects a fresh evidence-output directory, whereas
`test_delivery.py` is self-contained and cleans its temporary fixtures.
Project code/docs are repository-MIT. No clinical/source assets or external
redistribution rights are included, and no task count or readiness increases.
