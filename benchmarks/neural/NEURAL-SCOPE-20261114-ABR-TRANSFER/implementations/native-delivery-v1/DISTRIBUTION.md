# ABR observation-store distribution

The existing prepared observation store can be released without the evaluator key, target annotations, original native bundle, or private waveform scratch. The public archive has **not** been built or published. This document specifies the next release action; it does not authorize an upload or a participant study.

The proposed data asset contains all 936 target cases from 104 animals, 16,226 traces and 31,689,378 samples. It contains no Manor or Liberman support observations. It preserves the currently prepared observations and opaque case identifiers; it does not regenerate them with a new key.

## Exact observation-only allowlist

Paths are relative to the prepared store root. Preserve these payload bytes exactly:

| Path | Files | Bytes | SHA-256 or binding |
| --- | ---: | ---: | --- |
| `COMPLETE.json` | 1 | 1,737 | `a06e9b1b0bcbb1f8cfb6e8eb345fef85f5821b8f4cd91c54696ac3728b507e1d` |
| `operator/INDEX.json` | 1 | 240,068 | `4d843782531b74deb7cd11ec147b2b6061abb4401b9a35ba0878bffed38fcc72` |
| `operator/ROSTER.json` | 1 | 6,584,673 | `98dccd60e3d541e6653dec8b0d0d25541924f53451f99414e80e7d715191ef2d` |
| `public/COMMON_DOCUMENTATION.txt` | 1 | 3,489 | `455d5777bd6e49162055cbccfff079689517d8934bebc1a6adf4e49ee0c7b754` |
| `public/cases/<case_id>.json` | 936 | 338,405,724 total | Exact `packet_path`, `packet_pin[0]` (bytes) and `packet_pin[1]` (SHA-256) rows in the pinned index |
| **Total payload** | **940** | **345,235,691** | Before archive headers and separate release metadata |

Do not expand a wildcard over the entire store. Derive the 936 case paths from the pinned index and verify every size and hash before packaging. The roster describes opaque case/trace IDs, stimulus, level, sample extents and display axes. It does not contain the protected target annotation, original animal crosswalk, source filename or HMAC key. This is observation-only curation, not a guarantee of anonymity or resistance to matching against public upstream data.

Exclude all `private/` files, including `private/SCRATCH.json` and `private/waveforms.f64le`; the original native-input tree; evaluator target projections; opaque-ID keys and source-identity mappings; participant/session responses and journals; operator evidence; and previously rendered views. Generate images on demand from the complete numeric packets.

The unchanged prepared `COMPLETE.json` includes a hash for omitted private scratch metadata. The existing `open_store`, `load_roster`, case-view and manual initialization-to-seal paths do not open that scratch descriptor. Preserve the manifest; do not delete fields to invent another completion identity.

## Data licence and provenance

The official source is Walter Marcotti and Federico Ceriani, **Mouse ABR dataset (1 month old)**, published 9 June 2025, [Zenodo record 15619100](https://zenodo.org/records/15619100), DOI [10.5281/zenodo.15619100](https://doi.org/10.5281/zenodo.15619100). Its record explicitly declares the dataset under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The companion paper is [DOI 10.1016/j.heares.2025.109328](https://doi.org/10.1016/j.heares.2025.109328).

Preserve this attribution, the licence link, the original title/DOI and a notice describing the changes in the release metadata. Use the source dataset's declared CC BY 4.0 terms for the observation derivative; do not add a benchmark-only restriction to the data. This data-licence statement does not assign a licence to the software package.

Original source archive:

- `MouseABRs.zip`: 138,620,782 bytes.
- Published checksum: MD5 `5ac3c4f4b5c811a686e0044e530f4db7`.
- Authenticated native-source checksum: SHA-256 `3fd7dd1ceed336090fbb517882a15975bd211476d09bde28b9270a7f7b001993`.

State the derivative changes: native files were parsed into complete canonical numeric packets; case and trace identifiers were replaced with existing opaque IDs; evaluator labels, source-identity mappings and private scratch were omitted; display metadata and common instructions were added. All recorded target traces and all 1,953 samples per trace remain present. No physical time/voltage calibration, denoising, subsampling or scientific performance improvement is established by this packaging.

The original admitted native completion identity remains 22,643 bytes / SHA-256 `507b7e77a2a4d09f5056e6191efe34db7092ca4eab70a4880e425ae7eade1972`. It is a provenance dependency, not the public asset's identity. Keep that private manifest and key unchanged. Give the public subset its own release inventory and archive hash.

## Existing reader interface

The code package's pinned `prepare_delivery.py view` operation reads the public store directly. It does not call `prepare` or need the original native root. For example, after setting the source/store/output paths, one case ID from the index, and a finite view deadline:

```sh
python3 -I -S -B "$ABR_SOURCE/prepare_delivery.py" \
  --implementation "$ABR_SOURCE/abr_release.py" \
  --raster "$ABR_SOURCE/raster.py" \
  --documents "$ABR_SOURCE/COMMON_DOCUMENTATION.txt" \
  --deadline-seconds "$ABR_SECONDS" \
  view --store "$ABR_STORE" \
  --store-complete-bytes 1737 \
  --store-complete-sha256 a06e9b1b0bcbb1f8cfb6e8eb345fef85f5821b8f4cd91c54696ac3728b507e1d \
  --case-id "$ABR_CASE_ID" --output "$ABR_VIEW"
```

The manual-session initialization, view, capture, retirement and sealing paths can likewise use this subset plus their own new session outputs. Use the package's `OPERATOR_GUIDE.md` for their exact commands. Scoring remains a separate evaluator operation requiring the protected target projection after all 1,872 first-final slots are sealed. Publishing this observation asset does not publish or activate scoring inputs.

## Next archive operation and subsequent publication

When the release operation is selected, stream the exact 940 allowlisted files from the existing store into a new **uncompressed deterministic USTAR archive**. Use sorted relative paths, regular files only, fixed mode 0444, UID/GID 0, empty user/group names, and mtime 0. Hash every payload while reading; require the accepted byte/hash descriptors and exact file/count totals. Do not rebuild the native bundle, render every case, or reopen the labels/key. Archive construction and its byte accounting are a future operation, not evidence recorded here.

Write a separate `OBSERVATION_RELEASE.json` with the 940-file inventory, payload total, prepared-store completion hash, source archive/DOI/licence attribution, source-package pins, archive size/SHA-256, and explicit exclusions. Keeping the final archive hash outside the archive avoids a self-reference. A future archive/authentication operation can reserve at most 512 MiB of outputs and 1 GiB of source/verification reads. The 940 payload files total 345,235,691 bytes; allowing a 512-byte header and up to 511 bytes of padding per file, two terminal blocks and up to 10,239 bytes of record padding gives a conservative archive upper bound of 346,208,574 bytes, below 347 MB. These are prospective finite bounds, not a current allocation or an observed archive size. Keep the inventory and attribution assets separately bounded.

Uploading is a separate user-authorized root publication action after the archive and manifest exist. Publish the archive, manifest and attribution text as assets of the selected GitHub release, verify the uploaded identities, and then add the real download link to the package README. No current GitHub asset-size limit is assumed here. Neither a release/tag nor a download URL exists as a result of this source-only preparation.

The release retains native sample-index/native-amplitude axes and the task's existing interpretation limits. The annotation code 100 is not newly interpreted as censoring or a physiological threshold. These are release-annotation agreement observations; calibration, expert equivalence, clinical validity and participant/model performance remain unestablished. Existing qualification flags stay unchanged.
