# Fixed-region TMS reference construction

This component supplies the two previously unpublished, unchanged authored source
files used to construct the accepted reference for
`PAPER-paper-signal-add-021.fixed-regions-v1`. It completes a source dependency of
the [existing fixed-region profile](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/README.md).
It creates no benchmark ID and changes no endpoint, candidate, scorer or runtime.

`portable_regions.py` is the accepted producer. `projection_verify.py` is the
accepted projection verifier, renamed only as a file: its bytes are unchanged.
The producer imports only its authenticated byte reader and JSON decoder; **do
not invoke the verifier's separate whole-projection-review CLI** for this recipe.
The third dependency is the already published
[behavior statistics source](../../benchmarks/neuroscience/paper-signal-add-021/behavior-v1/reference/behavior_reference.py).
Its historical source-stage docstring does not override the later accepted
complete fixed-region result. No behavioral CSV is needed by this reference
producer. All three dependencies use Python's standard library.

## Complete inputs

Start with the complete, already accepted projection, obtained through an
authorized source. Keep all four ordinary, single-link files in one private
canonical directory without symlink ancestors:

| File | Bytes | SHA-256 |
|---|---:|---|
| `INPUT.json` | 4814 | `a0e3328495f4ba090ba1b2e3b1fe78ed22793ce38a6c78963d9f5637b9b1ab70` |
| `values.f64` | 35616000 | `93e721d490676f232ae2ac11b065294c0e660f267bcdc466080791c91641264c` |
| `pair_counts.u8` | 222600 | `6c0d2c0bb833b9bb8efb1ff72400403abbf92882cb5ae1e96322e246f805b4d8` |
| `missingness.json` | 1428 | `a2d16bef2777c493df79bbdc83cb058908a6cd28b45723e1a0d11cbd83c61e20` |

These total 35,844,842 bytes. Retain the existing accepted projection and support
reviews as separate owner evidence. A hash check alone does not recreate their
provenance review. The producer reads and authenticates `INPUT.json` and
`values.f64`; it does not reread `pair_counts.u8` or `missingness.json`. Those two
files remain required by the complete candidate packet and its existing owner.
Before preparing a deployment, verify all four files against the table using the
owner's existing intake mechanism. Do not replace the manifest, reduce the
tensor, drop positions, or rebuild missingness from reference answers.

Original MAT acquisition and lossless projection are separate upstream steps;
this component does not perform them. No dataset, article, official code,
reference body or original execution evidence is included. The existing
[provisioning instructions](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/PROVISIONING.md)
record the research-asset terms and boundaries. Repository-authored code uses the
repository MIT license; that grants no rights in separately acquired assets.

## Source check and construction command

If the operator already holds the exact accepted protected reference, reuse it.
No reference rerun is required for that deployment. The recipe below supplies
the missing source route for an operator who needs to reconstruct those bytes;
it does not invalidate or refresh the accepted historical result.

From the repository root, this source-only check verifies all three dependency
identities and exercises generated input/pin/output refusals. It reads no
research data, computes no reference statistics and starts no container:

```sh
python3 -I -S -B components/tms-fixed-region-reference/test_delivery.py \
  --behavior-source benchmarks/neuroscience/paper-signal-add-021/behavior-v1/reference/behavior_reference.py
```

For actual reference production, use the separately admitted CPython 3.11.6
environment from the accepted construction profile. A passing source check on
another Python version does not establish numerical compatibility. The selected
candidate image's prior 3.12.16 compatibility is not a new reference-production
runtime admission. The command below is a recipe, with literal placeholders to
replace after the operator supplies the inputs, runtime and bounded execution
window; it is not an execution selection:

```text
/ABSOLUTE/admitted/python3.11 -I -S -B \
  /ABSOLUTE/repository/components/tms-fixed-region-reference/portable_regions.py \
  --input-root /ABSOLUTE/private/accepted-projection \
  --manifest-bytes 4814 \
  --manifest-sha256 a0e3328495f4ba090ba1b2e3b1fe78ed22793ce38a6c78963d9f5637b9b1ab70 \
  --projection-verifier /ABSOLUTE/repository/components/tms-fixed-region-reference/projection_verify.py \
  --behavior-source /ABSOLUTE/repository/benchmarks/neuroscience/paper-signal-add-021/behavior-v1/reference/behavior_reference.py \
  --output /ABSOLUTE/private/fresh-reference/paired_region_reference.private.json
```

Create the output's parent directory privately (mode 0700), use a restrictive
umask, and require an absent output filename before launching. The unchanged
producer uses exclusive creation at the end of computation; it does not provide
an early output-path preflight, whole-process timeout, process supervisor or
hard memory ceiling. Its reader's 120-second deadline covers input reads only.
Use the operator's bounded execution mechanism and retain any failure. Do not
retry automatically or present a partial file as an accepted reference.

The expected complete output is **359,637 bytes**, SHA-256
`ceba59b4702c692c4e6819deb5cf72f8d6ebdb68b2a48228caf1860b266f30d8`.
Compare both length and digest before binding it to the existing portable owner.
A mismatch is a failed compatibility/identity check: retain it and investigate,
without changing that commitment or reporting it as a candidate score. The
accepted local reference was independently checked across all 12 regions,
36 effects and 540 omissions. This delivery reuses that evidence and makes no
claim that a new relocation or host has run successfully.

The output contains protected target values. Keep it, the producer, statistics
helper, verifier, scorer and private evidence outside both candidate mounts.
Use the unchanged [portable plan/build/select interface](../../benchmarks/neuroscience/paper-signal-add-021/fixed-regions-v1/portable/README.md)
to bind the exact reference and all inherited evidence. Reconstructing identical
reference bytes does not supply missing historical acceptance records or admit
a new runtime. Both candidate artifacts must close before protected grading.

The method remains the declared fixed-region reconstruction with all four
conditions and all fifteen jointly ordered source positions, the source-order
pairing assumption, inclusive fixed coordinate bounds, paired sign flips,
bootstrap intervals and the complete 36-effect Holm family. It is distinct from
the paper's primary FieldTrip cluster analysis. This source completion implies
no full-paper reproduction, model difficulty, code-access benefit, SOTA result,
public-data availability or submission-readiness increment.
