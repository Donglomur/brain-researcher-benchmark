# Complete optogenetics central-panel artifact scoring

This direct command grades a finished `central_submission.zip` for the existing
`PAPER-FIND-ADD-015` finite profile,
`opto-central-public-protocol-reconstruction-v1`. It calls the unchanged accepted
`central-program-v2/score_core.py`. It covers all 364 Figure2 cells, 52 multi-power
cells and six multi-visual cells: 102 window fields, 128 vector/identity fields
and the complete declared statistical report. It does not redirect the older
canonical 42-field NPZ scorer or introduce a new benchmark ID.

The interface consumes an external artifact. It does not execute participant
code, supervise producers, prove input dependence or provide isolated code
access. The protected program route remains a separate implementation. This
adapter supplies no whole-process time/CPU/memory sandbox, runtime admission or
fresh numerical compatibility result.

## Use the accepted full packet

The participant-facing contract remains the existing files under
`authoring/opto-attenuation-v1/independent-public-candidate-handoff-v2/`:

- `public/TASK.md` and `public/CLARIFICATION.md` define the numerical protocol.
- `public/OUTPUT_SCHEMA.json` fixes all output shapes, identities and report fields.
- `PUBLIC_ALLOWLIST.json` fixes all 18 participant inputs and their commitments.

The complete common packet is 197,968,908 bytes: 13 processed NPZ files totaling
197,623,278 bytes, primitive `input_schema.json`, the unmodified paper XML and
those three public contract files. Obtain the exact accepted files through the
operator's existing source locations or an authorized provider. Provision the
allowlist's complete contents with its declared basenames; do not expose the
parent authoring tree, scorer, private reference, prior outputs or house
reconstruction code. `LOCAL_BINDINGS.json` in the private delivery records the
existing locations and exact metadata authorities. This source task did not
reopen or rehash the processed arrays or recheck external availability.

The existing participant program convention is
`python -I program.py --input INPUT_DIRECTORY --out OUTPUT_DIRECTORY`. Actual
participant execution is outside this artifact adapter. The declared participant
runtime is Python3.12.8, NumPy2.2.6 and SciPy1.15.3. The accepted scientific evidence
is the protocol-guided paper/data condition A. Optional official-code access is
a separately declared condition, not a measured matched A/B result.

The participant returns one ZIP_STORED file, at most 2,700,000 bytes, containing
exactly `windows.npz` (at most 1,400,000), `paired_vectors.npz` (at most 800,000) and
`report.json` (at most 300,000). Both NPZ archives are uncompressed ordinary
C-order primitive arrays with the complete schema. All numeric entries must be
finite; all five identity arrays retain exact public values/order. Preserve both
cross-half orientations and every fixed clipping/baseline sensitivity. No
threshold-edge cells or adverse results are removed.

## Direct operator command

Actual grading requires CPython3.12.8 with NumPy2.2.6 available in that interpreter's
normal installed packages. The adapter checks both versions; grading does not
need SciPy because it compares the submitted report rather than recomputing its
statistical tests. The historical protected grader used image
`sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156`.
That fact does not establish a newly installed host runtime or guarantee that
the historical image remains available. No runtime was installed, probed or run
for this source delivery.

From a repository root containing the accepted source files and this component:

```sh
OPTO_PY=/ABSOLUTE/CPython-3.12.8-with-NumPy-2.2.6/bin/python
OPTO_ROUTE="$PWD/components/opto-central-artifacts/artifact_score.py"
OPTO_CORE="$PWD/authoring/opto-attenuation-v1/central-program-v2/score_core.py"
OPTO_SCHEMA="$PWD/authoring/opto-attenuation-v1/independent-public-candidate-handoff-v2/public/OUTPUT_SCHEMA.json"
OPTO_GOLD="$PWD/artifacts-build/opto-central-paired-001/output"
"$OPTO_PY" -I -B "$OPTO_ROUTE" \
  --core "$OPTO_CORE" --schema "$OPTO_SCHEMA" \
  --submission /ABSOLUTE/central_submission.zip \
  --reference-root "$OPTO_GOLD" \
  --output /ABSOLUTE/private/fresh-score.json
```

Use `-I -B` for actual grading; `-S` would remove normal site-package discovery
needed by NumPy. Paths must be ordinary and have no symlink ancestors. The score
path must be absent with an existing parent. Partial failed files are preserved;
there is no overwrite, automatic retry or deletion.

Core source is fixed at 22,233 bytes /
`a8a99ffe05eeb2e43b951b2557cc973808f0681fec9e82bcb1afe758e98e4071`;
the complete schema is 106,057 bytes /
`c7fbeee502fe9d37bc265add04e68ce5300229ec5861588e32788d4b822148cc`.
The source is executed from those captured authenticated bytes, without a second
loader read. Arbitrary paths cannot substitute a different scoring contract.

The reference directory provides these exact private files:

| File | Bytes | SHA-256 |
|---|---:|---|
| `windows.npz` | 1154804 | `e5f613eb0104de986662d888e5cafd79cbf071f8c438f2b056cea90373643085` |
| `paired_vectors.npz` | 197066 | `411ee6051939957a2f616ca0dee17ac77dd811594cecbdb47538570addaee775` |
| `report.json` | 24606 | `d87baf65f48631badbbd0e3d84ff824e7f10b0a7f9c0c7b824f4c102e85bdf09` |

The core admits every public ZIP/NPY/report field before invoking the private
loader. Malformed public artifacts cause zero private callbacks and reads. A
successful grade has one callback and three exact reference reads. Reference
failure or a callback/count mismatch is an operator error, never a fabricated
participant score. Even reference-root filesystem inspection is deferred until
that callback. The already accepted reference is reused; no reference-generation
step is required to install the adapter.

The output is the unchanged core score dictionary, capped at 1,000,000 bytes and
written mode0400. All array diagnostics, projected report comparisons and named
continuous metrics remain present. Decimal representations, exact mismatch
counts and overflow/underflow disclosures are preserved. No new aggregate score,
tolerance, significance reward or success floor is added. Keep the score private
under the study's feedback policy: it contains reference-dependent diagnostics.
Standard output is a small artifact identity/count summary with an explicit
`protected_execution_attested: false`. Exit0 means scored, exit2 is public schema
rejection, and exit1 is an operator/intake/runtime failure.

## Evidence and scope

Two historical events must remain distinct:

1. The independent public-paper/data reconstruction's numerical result was
   admitted from a post-closure archive after the original outer operator error.
   All 140,678 window values matched exactly; maximum vector discrepancy was
   9.237055564881302e-14, and 843 report comparisons were retained. Original logs
   and normal terminal score commitment were missing, the original directory
   was unsealed, and the failed log-admission conjunct remains unknown. The
   archive does not retroactively turn that attempt into a successful transport.
2. Corrected v2 transport separately passed an actual malformed-public-input
   control, 40 generated numerical/admission controls, terminal retention and
   cleanup. The successful scientific candidate was not replayed under v2.

This new trusted adapter is neither historical run. Its stdlib interface tests
use invented bytes and a fake core to exercise intake, pin failures, callback
accounting, complete returned-score preservation and output failures. They import
no NumPy, run no accepted scientific arithmetic and provide no new authentic
score. The exact accepted core and its earlier numerical evidence are reused.
Unlike the protected worker, this adapter does not rerun the 40 numerical
controls before every submission; it reports that omission explicitly.

Run the lightweight interface tests from the component directory:

```sh
python3 -I -S -B test_interface.py -v
```

The data are processed exposed development observations. Raw optical processing,
upstream cell selection, verified animal mapping, panel overlap, full Figures4/5,
whole-paper reproduction, model difficulty and SOTA remain outside the accepted
scope. Two published p-values remain unmatched; matching the declared current
reference does not repair that discrepancy. Data are recorded CC BY4.0; article
XML declares CC BY-NC-ND4.0; official-code licensing and external commercial
release remain unresolved. LOESS is not needed by this central route. The
component itself does not distribute the data, article or private reference.

Canonical `neurobench score` still selects the historical 42-field scorer. A
separate additive finite-profile entry can point to this direct command and its
complete accepted evidence while preserving all old manifest fields and flags.
No generic profile switch, protected-runtime success or new benchmark count is
claimed by this delivery.
