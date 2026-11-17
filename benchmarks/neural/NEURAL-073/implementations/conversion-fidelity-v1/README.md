# Independent canonical-map fidelity checker

The existing [converter](../registered-runtime/input-conversion-v1/README.md)
produces canonical little-endian float64 maps and conversion records. This
component supplies a second implementation that checks a canonical file against
the original NIfTI bytes. It imports neither that converter nor NiBabel/NumPy.
It performs no acquisition, model fitting, source-label lookup or participant
delivery.

`verify.py` checks every voxel rather than sampling. Its separately implemented
file indexing converts NIfTI's first-axis-fastest storage to the last-axis-fastest
canonical C ordering. It compares the exact float64 bytes after effective scaling,
including negative zero. Matching hashes alone cannot pass: a modified canonical
body with an updated digest still fails its numerical comparison. It independently
checks shape, literal coded sform, spatial unit, scale, payload extent, extension
extents, compression integrity and input/output/evidence bindings.

This repairs a missing independent preparation check. It does **not** establish
authentic conversion, cohort completeness, producer lineage, rights, spatial
registration, reference competence or benchmark performance. The task's complete
9,532-map/13-person/25-protocol endpoint and all four access conditions remain
unchanged. One passing map receipt cannot qualify a smaller panel as that task.

## Supported numerical profile

Both single-file NIfTI-1 and NIfTI-2, both byte orders, and gzip are supported.
The map must be three-dimensional and satisfy the existing minimum geometry.
Signed/unsigned 8-, 16-, 32- and 64-bit integers and float32/float64 are decoded.
Each integer must be exactly representable as float64; effective scaling must
produce finite float64 arithmetic. Identity scaling operations are skipped so
that a stored negative zero is retained. Zero or nonfinite NIfTI slope means
effective slope 1 and intercept 0, matching the declared decoder semantics.

This version requires a finite nonsingular **coded sform**. It verifies the affine
directly from the header; it does not independently reconstruct qform rotations or
derive anatomical orientation codes. A qform-only image is refused, and is never
omitted from a complete-corpus requirement. Similarly, an integer/scale outside
the supported numerical profile requires a separately reviewed verifier extension;
refusal is not evidence that the source map or existing converter is wrong.
Physical units are preserved, including `unknown`; no unit conversion or inferred
physical calibration occurs.

## Explicit input invocation

Use Python 3.11 or later on a POSIX host with descriptor-relative `O_NOFOLLOW` and
`O_DIRECTORY`. No scientific package installation is required. Supply original
and output identities from the reviewed conversion plan and records. The evidence
input is the converter's per-map `conversion/*.json`, not `RESULT.json` or a private
target file. Each path must be absolute and each file must be regular, single-link
and within the explicit read cap. The command emits a JSON receipt to stdout and
leaves inputs unchanged. An error exits nonzero without a passing receipt.

```sh
python3 -I -S -B /ABSOLUTE/conversion-fidelity-v1/verify.py \
  --original /ABSOLUTE/original.nii.gz \
  --original-sha256 REVIEWED_ORIGINAL_SHA256 --original-cap-bytes REVIEWED_CAP \
  --canonical /ABSOLUTE/canonical.f64 \
  --canonical-sha256 REVIEWED_CANONICAL_SHA256 --canonical-cap-bytes REVIEWED_CAP \
  --evidence /ABSOLUTE/conversion.json \
  --evidence-sha256 REVIEWED_EVIDENCE_SHA256 --evidence-cap-bytes REVIEWED_CAP \
  --max-expanded-bytes REVIEWED_EXPANSION_CAP
```

Opening authentic arrays requires the existing coordinated preparation protocol;
this command is an executable component, not new execution authority. The checker
holds the compressed original, expanded original and canonical map in memory; it
does not construct an additional full expected array. Explicit caps are logical
admission bounds, not OS resource limits. Run complete-corpus fidelity only under
an agreed native workload and preserve failed maps in the required denominator.

## Generated controls and source basis

`test_verify.py` uses hand-encoded non-cubic images and checks both versions,
endianness, compression, all spatial units, negative/disabled scaling, signed zero,
and integer/float variants. Counterexamples include reordered values with updated
hashes, wrong units/affine, truncated payloads, illegal offsets/extensions, corrupt
gzip, lossy integer conversion, unknown source pins, and symbolic links. It also
exercises the CLI. Optional `--prior-generated-fixtures` checks the six explicitly
invented artifacts from the prior converter's generated-control directory; it
requires exactly those invented IDs and never admits an authentic catalogue.

During this parallel construction wave all checks run through the shared
`test_pool.py`, with owner `neural_01`, one thread, 1 GiB declared RAM and at most
180 seconds. Test receipts and source pins are in `SOURCE_EVIDENCE.json` and the
external handoff. No authentic map, model or hidden target was read in construction.

Header fields and declared scaling semantics were inspected in the already-held
NiBabel 5.4.2 wheel (SHA-256
`553482c5f1e1034fc312edf6fb7f32236c0056439845d1c29293b7e8c98d4854`), specifically
[`nifti1.py`](https://github.com/nipy/nibabel/blob/5.4.2/nibabel/nifti1.py),
[`nifti2.py`](https://github.com/nipy/nibabel/blob/5.4.2/nibabel/nifti2.py) and
[`volumeutils.py`](https://github.com/nipy/nibabel/blob/5.4.2/nibabel/volumeutils.py).
These are source observations, not a fresh network verification of those URLs.
No new source bytes were downloaded, and the frozen predecessor packages remain
unchanged. The implementation's independent byte arithmetic is intentionally
scoped as above rather than claiming all NiBabel behavior.
