# Roster-bound paired preparation

This operator-only successor repairs a specific gap in the preserved preparation:
the previous design validator accepts arbitrary complementary folds and declared
target counts, while its stager never compares the aligned target roster with the
metadata used to select trials. A fold permutation, false LR counts, later-trial
substitution or wrong-area session pointer can therefore pass those checks.

`prepare.py` constructs the original 50 cases from all ten independently pinned
aligned-session metadata records. It verifies each record's exact source asset,
mouse, date and area against the unchanged inventory, then selects the first
chronological `min(N_M1, N_S1)` trials in each LR stratum and assigns that stratum's
ordinal modulo five. Each target must have at least ten trials in both areas.
M1 and S1 trial IDs are separate session identities; this does not pair individual
reaches across days. Design validation compares every case field, including its
aligned-array pin, with that reconstruction.

Staging first validates the full design, then captures and authenticates one
selected aligned NPZ. Its complete trial IDs and LR target labels must equal the
metadata roster, including eligible trials excluded by count matching. It retains
the original 128 calcium features, 141 nuisance features, 51 time points, 24 joint
angles, whole-trial splits and public/private packet ABI. It never fits a model,
changes the measured-target metric, or reads query angles while building a design.

The new CLI requires an operator-owned JSON binding with exactly `schema` and
`sessions`. The schema is `neural026_session_metadata_binding_v1`; `sessions` maps
all ten original session IDs to `{path, bytes, sha256}` descriptors for their
`<session>.json` files. Use the metadata emitted by the existing alignment step.
The operator supplies the binding SHA256 independently of the participant. The
metadata itself contains the aligned NPZ descriptor. Both source inventory and
the existing measured-scorer loader are pinned in the implementation; the latter
authenticates its unchanged protocol, common helpers and bounded NPZ decoder.

```sh
python3 -B prepare.py design \
  --sessions /operator/aligned \
  --metadata-binding /operator/metadata-binding.json \
  --metadata-binding-sha256 EXPECTED_BINDING_SHA256 \
  --output /operator/design.json

python3 -B prepare.py stage-case \
  --sessions /operator/aligned \
  --metadata-binding /operator/metadata-binding.json \
  --metadata-binding-sha256 EXPECTED_BINDING_SHA256 \
  --design /operator/design.json --design-sha256 EXPECTED_DESIGN_SHA256 \
  --case-id cfa17_M1_fold0 \
  --public-output /participant/case \
  --private-output /operator/targets/case
```

All metadata, design, aligned arrays and private outputs remain operator-only.
Only the single staged public folder may be exposed to a participant; another
fold's training labels overlap this fold's query targets. The code checks fresh,
separate output roots but does not provide an execution sandbox. A privileged
operator must enforce the participant boundary and independent pin custody.
The existing reconstruction runner and measured-target scorer remain unchanged;
this addition is not automatically enrolled in either route.

The source cohort and clock interpretation remain those of
[GSK26 commit 815b610](https://github.com/kaufmanlab/GSK26-public/tree/815b610b3beddfed5a3abf611d3a465ab9e4ce5c)
and [Figshare article 28326998 version one](https://figshare.com/articles/dataset/28326998/1).
No source download or authentic preparation was performed for this component.
Hash consistency cannot establish that an operator's alignment was biologically
correct. Full ten-session acquisition, raw MAT alignment and MATLAB parity,
qualified references, protected participant execution and matched candidate
ablations remain outstanding. This is preparation software, not a completed
benchmark or evidence of direct neural interpretation.

`test_prepare.py` uses only generated arrays and metadata. It includes explicit
counterexamples accepted by the predecessor validator, complete paired design
oracles, metadata-only execution, staged array ordering, false target roster
rejection and independent binding/design/array tampering. These checks establish
software behavior only; run them through the project's authorized lightweight
test pool. The code requires the same existing NumPy dependency as its predecessor.
