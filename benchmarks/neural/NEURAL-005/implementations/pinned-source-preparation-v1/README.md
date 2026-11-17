# Pinned source preparation for NEURAL-005

This component restores the task's missing portable preparation path from the
eight published author CSVs. It replaces historical container-specific input and
output paths with explicit operator directories, while retaining the original
26-person training / seven-person exposed development split, current-to-next-round
target, positional ERP join, missingness rule, and 50/53/57 feature definitions.
The existing scorer and scientific contract are unchanged.

`source_prepare.py` authenticates all eight files before parsing any table, keeps
their original row positions while joining, and excludes the eight reserved
participants before numerical conversion. It checks all 36 five-round episodes
for each active person, original consecutive trial numbers, accept/reject coding,
and the three published prediction-error equations. Eligibility requires all
seven ERP values on the current round before any view masking. An incomplete
next-round ERP does not exclude the current query; a missing intermediate round
cannot be bridged. The target remains the next consecutive choice in the same
partner episode, never the current choice.

The output must contain exactly 3,254 training rows and the fixed 816 public
development identities. Before any output is written, both numerical payloads
must match the historical admitted artifact hashes exactly. A failed parity check
stops preparation; it does not relax support, change the split, or emit a substitute
panel. These expected hashes were recovered from source metadata without opening
historical private targets or saved predictions.

`features.py` exposes the original deterministic feature vectors. Behavioral and
ERP values retain their source units; no globally standardized source columns or
new scaling are used. History has 25 numerical fields and their 25 missing-value
indicators; prestimulus adds the three baseline ERP terms; all ERP adds all seven
terms. Participant and partner identifiers are not numerical features. The helper
also rejects boolean or nonintegral identity metadata and unexpected fields.

## Operator use

Use Python 3.9 or newer with its standard library. Obtain the eight exact files
listed in `SOURCE_PINS.json` under one source directory. The source revision is
[`4f5767df1516e0ec3c234d51ba36e4b741eb60e8`](https://github.com/jpheffne/2025_epe_eeg/tree/4f5767df1516e0ec3c234d51ba36e4b741eb60e8/data/clean);
the total source payload is 6,675,275 bytes. This component performs no download.

```sh
python3 source_prepare.py --source-dir /operator/source --output /operator/fresh-preparation
```

The output's parent must already exist. The output directory must be new and
outside this repository. It receives mode 0700 and files mode 0600:

- `train.json`: labeled training features, the fixed feature names and training
  participant fold assignment.
- `development_private.json`: operator-only current prefixes with next-round
  targets and original source-row indices. **Never mount this file, or its full
  target-free prefix list, in a candidate environment.** Later prefixes reveal
  earlier targets; a qualified sequential broker must release each only after the
  preceding prediction is committed.
- `preparation.json`: support, source-equation checks, positional-row manifest
  digest and explicit scientific limitations. Its participant coverage is also
  operator-only.

The command prints output sizes and digests, not numerical records. An incomplete
directory left by an I/O failure has no success receipt and must not be admitted.
Existing historical files are neither read nor modified by this path.

## Qualification boundary

The new implementation has generated software controls; authentic preparation
has **not** been executed in this revision. It requires the separately coordinated
native preparation protocol before use on the cached source. Source files are
known locally, but their presence does not count as executed preparation.

The author ERP tables have no independent trial keys. Matching original hashes
and positions authenticates the released mapping, not biological epoch identity.
Offline ERP availability, the exposed development cohort, and the next-round
extension of the paper's same-row analysis retain their existing limitations.
This component neither fits a model nor runs a participant. It does not restore
the full sequential controller or qualify any direct, viewer, tool-assisted, or
frozen-program condition. It does not establish an ERP benefit or causal effect.

## Generated controls

`test_source_prepare.py` uses only invented episodes and a complete invented
41-person source shape. It independently checks arithmetic, all three feature
views, current-only missingness, preserved absolute row indices, reserved-value
exclusion, exact panel membership, source equations, malformed CSVs, source hash
failure, and invalid round transitions. It makes no model or external API calls.
Run through the project shared test pool during parallel construction.

`SOURCE_PINS.json` records the immutable author revision, all eight source hashes,
the unchanged public case-panel hash, expected numerical output hashes, and
historical converter/feature/plan source hashes. No authentic numerical values,
private paths, source rosters or raw artifacts are distributed with this component.
